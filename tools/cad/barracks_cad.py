#!/usr/bin/env python3
"""CAD rebuild of the barracks bunker (appearance barracks), in the original's frame.

    D=~/craft/solid/mc2/buildings/barracks
    python3 -I tools/art/cad_building.py openings barracks > $D/openings.json
    python3 -I tools/art/cad_building.py decal barracks 0 <u0 v0 u1 v1> > $D/decal_<name>.json  (see DECALS)
    python3 -I tools/cad/barracks_cad.py $D > $D/barracks.json
    solidcraft-cli run $D/barracks.json --out $D/barracks.obj
    python3 -I tools/art/cad_building.py bake barracks $D/barracks.obj

Measured from game/assets/objects/barracks.glb: a 0.43 m skirt (x -4.2..4.22, z -12.46..3.85) under a sloping
frustum to a flat roof at 3.5 m (x -2.79..2.81, z -11.11..2.5), and two door porches (1.8 x 1.9 m, 2.52 m high)
on the ends. Relief: the six painted green wall panels are 4 cm recesses with the windows (the texture's
cut-outs) 15 cm deep inside them and a sill under each; the porch doors are 8 cm recesses with their window
another 6 cm in, a canopy slab over each; the three roof hatches are raised 18 cm curbs; a coping runs round
the roof edge and the skirt top has a drip ledge.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

DECALS = {"door": (0, 0.868, 0.812, 0.975, 0.995), "panel": (0, 0.30, 0.52, 0.50, 0.70),
          "panel2": (0, 0.70, 0.52, 0.905, 0.70), "hatch": (0, 0.415, 0.18, 0.522, 0.287),
          "hatch2": (0, 0.665, 0.328, 0.795, 0.39)}
D = Path(sys.argv[1])


def rects(name):
    return json.load(open(D / f"decal_{name}.json"))["rects"]


B = Builder()
X0, X1, Z0, Z1 = -4.2, 4.22, -12.46, 3.85
TX0, TX1, TZ0, TZ1 = -2.79, 2.81, -11.11, 2.5
SK, TOP = 0.43, 3.5
B.box("skirt", (X0, 0.0, Z0), (X1, SK, Z1))
body = B.loft_y("body", [(X0, Z0), (X1, Z0), (X1, Z1), (X0, Z1)], SK, [(TX0, TZ0), (TX1, TZ0), (TX1, TZ1), (TX0, TZ1)], TOP)
# drip ledge on the skirt top, 6 cm proud
B.box("ledge", (X0 - 0.06, SK - 0.06, Z0 - 0.06), (X1 + 0.06, SK, Z1 + 0.06))

# wall panels: 4 cm recesses (inset by 10 cm so the riveted posts between stay full)
for nm in ("panel", "panel2"):
    for o in rects(nm):
        B.recess(body, dict(o, w=o["w"] - 0.2, h=o["h"] - 0.3), 0.04)
# windows 15 cm into the panel, sills under them
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    if abs(o["normal"][2]) > 0.9:
        continue  # the door windows are cut below
    B.recess(body, o, 0.15, surface_shift=0.04)
    B.sill(f"sill{k}", o, proud=0.10, thick=0.06, overhang=0.08, surface_shift=0.04)

# porches, door recesses with their window, canopies
for k, (za, zb) in enumerate(((-12.74, -10.84), (2.26, 4.17))):
    p = B.box(f"porch{k}", (-0.89, 0.0, za), (0.91, 2.52, zb))
    front = za if k == 0 else zb
    sgn = -1 if k == 0 else 1
    zc0, zc1 = sorted((front + sgn * 0.25, front - sgn * 0.6))
    B.box(f"canopy{k}", (-1.04, 2.52, zc0), (1.06, 2.64, zc1))
for o in rects("door"):
    porch = "porch0" if o["normal"][2] < 0 else "porch1"
    B.recess(porch, o, 0.08)
for o in json.load(open(D / "openings.json"))["openings"]:
    if abs(o["normal"][2]) > 0.9:
        porch = "porch0" if o["normal"][2] < 0 else "porch1"
        B.recess(porch, o, 0.06, surface_shift=0.08)

# coping round the roof edge (12 cm high, 25 cm wide), roof hatches as 18 cm curbs
w, h = 0.25, 0.12
for k, (lo, hi) in enumerate((((TX0, TOP, TZ0), (TX1, TOP + h, TZ0 + w)), ((TX0, TOP, TZ1 - w), (TX1, TOP + h, TZ1)),
                              ((TX0, TOP, TZ0 + w), (TX0 + w, TOP + h, TZ1 - w)), ((TX1 - w, TOP, TZ0 + w), (TX1, TOP + h, TZ1 - w)))):
    B.box(f"coping{k}@8a8674", lo, hi)
for k, o in enumerate(rects("hatch") + rects("hatch2")):
    c = np.array(o["center"])
    hw = (o["w"] / 2, o["h"] / 2)
    t = np.abs(np.array(o["t"]))
    ex, ez = (hw[0], hw[1]) if t[0] > 0.5 else (hw[1], hw[0])
    B.box(f"hatch{k}", (c[0] - ex, TOP, c[2] - ez), (c[0] + ex, TOP + 0.18, c[2] + ez), chamfer=0.04)

print(B.dump())
