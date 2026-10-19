#!/usr/bin/env python3
"""CAD rebuild of the lookout tower (appearance lookouttower), in the original's frame.

    D=~/craft/solid/mc2/buildings/lookouttower
    python3 -I tools/art/cad_building.py openings lookouttower > $D/openings.json
    python3 -I tools/art/cad_building.py decal lookouttower <mat> u0 v0 u1 v1 > $D/decal_<name>.json  (see DECALS)
    python3 -I tools/cad/lookouttower_cad.py $D > $D/lookouttower.json
    solidcraft-cli run $D/lookouttower.json --out $D/lookouttower.obj
    python3 -I tools/art/cad_building.py bake lookouttower $D/lookouttower.obj

Measured from game/assets/objects/lookouttower.glb (vertices listed by height): a sloping plinth (8.0 x 7.26 m at
the ground, 6.32 x 5.76 m at 3.59 m), a tapered shaft (4.73 x 4.27 m at 3.57 m to 3.11 x 2.80 m at 12.17 m), a
4.72 x 4.29 m cab from 12.10 to 14.56 m and a 6.05 x 5.5 m roof slab, 14.53 to 14.91 m. Relief: the cab's twelve
cut-out windows are 18 cm recesses (the original's lit-window box sits 17-19 cm in) with sills; the shaft's painted
green glazing strips are 10 cm recesses between 8 cm pilasters; each plinth face's door is a 25 cm recess in a
proud frame; a coping caps the plinth; the roof has a chamfered edge, the painted round vent as a real cowl and
the painted box as a 25 cm housing.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, box_edges  # noqa: E402

DECALS = {  # name: (material, u0, v0, u1, v1) in the upscaled atlas, for cad_building.py decal
    "door": (0, 0.781, 0.885, 0.828, 0.995),
    "glass_a": (0, 0.590, 0.03, 0.673, 0.47), "glass_b": (0, 0.825, 0.03, 0.859, 0.47), "glass_c": (0, 0.876, 0.03, 0.910, 0.47),
    "pil_a": (0, 0.551, 0.02, 0.588, 0.485), "pil_b": (0, 0.675, 0.02, 0.709, 0.485),
    "pil_c": (0, 0.783, 0.02, 0.822, 0.485), "pil_d": (0, 0.912, 0.02, 0.944, 0.485),
}
D = Path(sys.argv[1])


def rects(name):
    return json.load(open(D / f"decal_{name}.json"))["rects"]


def rect_poly(x0, x1, z0, z1):
    return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]


B = Builder()
# ---- volumes
base = B.loft_y("plinth", rect_poly(-4.073, 3.918, -3.382, 3.876), 0.0, rect_poly(-3.24, 3.08, -2.63, 3.13), 3.59)
shaft = B.loft_y("shaft", rect_poly(-2.44, 2.29, -2.02, 2.25), 3.57, rect_poly(-1.63, 1.48, -1.28, 1.52), 12.17)
cab = B.box("cab", (-2.42, 12.10, -2.04), (2.30, 14.56, 2.25))
lo, hi = (-3.09, 14.53, -2.64), (2.96, 14.91, 2.86)
B.box("roof", lo, hi, chamfer=0.06)
# coping over the plinth top, 8 cm proud of its edge
B.box("coping", (-3.32, 3.47, -2.71), (3.16, 3.71, 3.21), chamfer=0.04)

# ---- cab windows: 18 cm recesses, panes at the back, a sill under each
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    B.recess(cab, o, 0.18)
    B.sill(f"sill{k}", o, proud=0.10, thick=0.06, overhang=0.04)

# ---- shaft: glazing strips recessed, pilasters proud
for nm in ("glass_a", "glass_b", "glass_c"):
    for o in rects(nm):
        B.recess(shaft, o, 0.10)
for nm in ("pil_a", "pil_b", "pil_c", "pil_d"):
    for k, o in enumerate(rects(nm)):
        n = np.array(o["normal"])
        B.obox(f"{nm}{k}", np.array(o["center"]) + n * 0.03, o["t"], o["b"], o["normal"], (o["w"], o["h"], 0.10))

# ---- plinth doors: 25 cm recess, a frame on three sides (none under the ground)
for k, o in enumerate(rects("door")):
    o = dict(o, h=o["h"] + 0.3, center=(np.array(o["center"]) - np.array(o["b"]) * 0.15).tolist())  # run the cut below the ground
    B.recess(base, o, 0.25)
    n, t, b = (np.array(o[q], float) for q in ("normal", "t", "b"))
    c0 = np.array(o["center"]) + n * 0.025
    w, h, fw = o["w"], o["h"], 0.12
    top = c0 + b * (h / 2 + fw / 2)
    B.obox(f"dframe{k}_t", top, t, b, n, (w + 2 * fw, fw, 0.07))
    for s in (1, -1):
        B.obox(f"dframe{k}_{s + 1}", c0 + t * s * (w / 2 + fw / 2) + b * 0.15, t, b, n, (fw, h - 0.3, 0.07))

# ---- roof: the painted round vent as a cowl, the painted box as a housing
for k, (r, h) in enumerate(((1.0, 0.12), (0.45, 0.32))):
    B.c("solid.cylinder", radius=r * 1000, height=(h + 0.02) * 1000, base=[-896.0, -1000.0, 14890.0], axis=[0, 0, 1],
        body_name=f"vent{k}", operation="new")
B.box("housing", (-1.67, 14.89, -1.12), (0.01, 15.16, -0.44), chamfer=0.03)

print(B.dump())
