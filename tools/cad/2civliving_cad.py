#!/usr/bin/env python3
"""CAD rebuild of the L-shaped single-storey civilian house (appearance 2civliving), in the original's frame.

    D=~/craft/solid/mc2/buildings/2civliving
    python3 -I tools/art/cad_building.py openings 2civliving > $D/openings.json
    python3 -I tools/art/cad_building.py decal 2civliving 0 <u0 v0 u1 v1> > $D/decal_<name>.json  (see DECALS)
    python3 -I tools/cad/2civliving_cad.py $D > $D/2civliving.json
    solidcraft-cli run $D/2civliving.json --out $D/2civliving.obj
    python3 -I tools/art/cad_building.py bake 2civliving $D/2civliving.obj

Measured from game/assets/objects/2civliving.glb (node Box02): L-shaped walls to 2.77 m (outer corners
(-2.53, -2.47) and (10.26, 10.32), inner corner (2.40, 2.60)) under a flat roof slab 2.77..3.09 m that overhangs
them by 0.64 m all round; two 12 cm door steps. Relief: the roof inside a 0.4 m rim is dropped 12 cm (the
painted parapet ring becomes a real one); the five painted roof hatches are 15 cm raised curbs; every cut-out
window is a 15 cm recess with a sill and its painted glazing bars as real mullions; the two painted doors are
10 cm recesses (their small cut-out windows go deeper) under a shallow hood.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

DECALS = {  # name: (material, u0, v0, u1, v1) in the upscaled atlas
    "door1": (0, 0.453, 0.297, 0.553, 0.502), "door2": (0, 0.453, 0.547, 0.553, 0.752),
    "panel0": (0, .110, .071, .191, .152), "panel1": (0, .369, .073, .520, .176), "panel2": (0, .313, .100, .365, .176),
    "panel3": (0, .164, .195, .215, .264), "panel4": (0, .109, .266, .215, .420),
}
D = Path(sys.argv[1])
WALL_TOP, ROOF_TOP = 2.77, 3.094
B = Builder()


def rects(name):
    return json.load(open(D / f"decal_{name}.json"))["rects"]


# ---- volumes
walls = [(-2.53, -2.47), (10.26, -2.47), (10.26, 2.60), (2.40, 2.60), (2.40, 10.32), (-2.53, 10.32)]
slab = [(-3.17, -3.06), (10.94, -3.06), (10.94, 3.19), (3.08, 3.19), (3.08, 10.91), (-3.17, 10.91)]
rim = 0.4
inner = [(-3.17 + rim, -3.06 + rim), (10.94 - rim, -3.06 + rim), (10.94 - rim, 3.19 - rim), (3.08 - rim, 3.19 - rim),
         (3.08 - rim, 10.91 - rim), (-3.17 + rim, 10.91 - rim)]
W = B.prism_y("walls", walls, 0.0, WALL_TOP)
R = B.prism_y("roof", slab, WALL_TOP, ROOF_TOP)
DROP = 0.12
B.cut(R, B.prism_y("roofcut", inner, ROOF_TOP - DROP, ROOF_TOP + 0.05))
# door steps as in the original
B.box("step0", (8.07, 0.0, 2.60), (9.84, 0.12, 3.59))
B.box("step1", (2.40, 0.0, 8.13), (3.52, 0.12, 9.93))

# ---- roof hatches: raised curbs on the dropped roof
for k in range(5):
    for o in rects(f"panel{k}"):
        c = np.array(o["center"], float)
        y0, y1 = ROOF_TOP - DROP, ROOF_TOP + 0.06
        hw, hd = o["w"] / 2 - 0.05, o["h"] / 2 - 0.05
        B.box(f"hatch{k}", (c[0] - hw, y0, c[2] - hd), (c[0] + hw, y1, c[2] + hd))

# ---- doors: 10 cm recess, door bottom on the step, hood over it
doors = []
for nm in ("door1", "door2"):
    for o in rects(nm):
        o = dict(o, w=1.0, h=2.1)
        o["center"] = [o["center"][0], 0.12 + 1.05, o["center"][2]]
        B.recess(W, o, 0.10)
        B.sill(f"hood_{nm}", o, proud=0.35, thick=0.08, overhang=0.15, top=True)
        doors.append(o)


def in_door(o):
    return any(np.linalg.norm(np.array(o["center"]) - np.array(d["center"])) < 1.2 for d in doors)


# ---- windows: 15 cm recess, sill, mullions
DEPTH = 0.15
BAR = 0.06
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    n, t, b = (np.array(o[q], float) for q in ("normal", "t", "b"))
    c = np.array(o["center"], float)
    if in_door(o):
        B.recess(W, o, 0.20)
        continue
    B.recess(W, o, DEPTH)
    B.sill(f"sill{k}", o, proud=0.10, thick=0.06, overhang=0.06)
    bc = c - n * (DEPTH / 2 + 0.02)  # bars run from the pane back to 2 cm behind the wall face
    bd = DEPTH - 0.04
    if o["w"] > 2.0:  # strip window: three panes
        for j, f in enumerate((0.30, 0.73)):
            B.obox(f"mull{k}_{j}", bc + t * (f - 0.5) * o["w"], t, b, n, (BAR, o["h"], bd))
    elif o["h"] > 0.8:  # double-hung: a transom at mid height
        B.obox(f"mull{k}", bc, t, b, n, (o["w"], BAR, bd))

print(B.dump())
