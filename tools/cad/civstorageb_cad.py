#!/usr/bin/env python3
"""CAD rebuild of the sawtooth storage shed (appearance civstorageb), in the original's frame.

    D=~/craft/solid/mc2/buildings/civstorageb
    python3 -I tools/art/cad_building.py openings civstorageb > $D/openings.json
    python3 -I tools/art/cad_building.py decal civstorageb <mat> u0 v0 u1 v1 > $D/decal_<name>.json  (see DECALS)
    python3 -I tools/cad/civstorageb_cad.py $D > $D/civstorageb.json
    solidcraft-cli run $D/civstorageb.json --out $D/civstorageb.obj
    python3 -I tools/art/cad_building.py bake civstorageb $D/civstorageb.obj

Measured from game/assets/objects/civstorageb.glb: a 6.24 x 14.69 m shed, walls 4.01 m, under three sawtooth bays
4.9 m long whose roofs fall from 5.33 m (the glazed clerestory, facing +z) to 4.01 m; three loading docks
(0.61 x 3.7 m, top at 1.18 m) along the -x side, one under each roller door. Relief: the roof is a real 8 cm sheet
with 15 cm verges and a 20 cm eave at the back, with standing seams on the painted orange crests (0.46 m pitch,
found by column peaks in the upscaled roof); a drip hood over each clerestory; the clerestory windows 15 cm
recesses with sills; the roller doors 20 cm recesses under a roller-box housing; corner trims; the docks solid
slabs on dark legs.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

DECALS = {  # name: (material, u0, v0, u1, v1) in the upscaled atlas, for cad_building.py decal
    "door0": (0, 0.063, 0.762, 0.278, 0.913), "door1": (0, 0.389, 0.762, 0.604, 0.913), "door2": (0, 0.716, 0.762, 0.93, 0.913),
}
D = Path(sys.argv[1])
X0, X1, Z0, Z1 = -2.81, 3.43, -11.428, 3.263
YW, YR = 4.01, 5.326           # wall top, ridge
HIGH = (3.263, -1.63, -6.53)    # each bay's high (clerestory) edge; it falls 4.9 m toward -z
BAY = 4.9
SEAMS_U = (0.055, 0.105, 0.156, 0.203, 0.252, 0.299, 0.35, 0.396, 0.441, 0.494, 0.538, 0.582, 0.621)


def rects(name):
    return json.load(open(D / f"decal_{name}.json"))["rects"]


B = Builder()
# ---- the shed: one x-prism with the sawtooth profile (z, y)
prof = [(Z0, 0.0), (Z1, 0.0), (Z1, YR), (Z1 - BAY, YW), (-1.63, YR), (-1.63 - BAY, YW), (-6.53, YR), (Z0, YW)]
shed = B.prism_x("shed", prof, X0, X1)

# ---- windows (clerestories) and roller doors
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    B.recess(shed, o, 0.15)
    B.sill(f"sill{k}", o, proud=0.08, thick=0.05, overhang=0.04)
for d in range(3):
    for k, o in enumerate(rects(f"door{d}")):
        B.recess(shed, o, 0.20)
        B.sill(f"rollerbox{d}_{k}@avg", o, proud=0.25, thick=0.30, overhang=0.10, top=True)

# ---- roof sheets, standing seams, drip hoods
L = math.hypot(BAY, YR - YW)
b = np.array([0.0, -(YR - YW) / L, -BAY / L])   # down the slope
n = np.array([0.0, BAY / L, -(YR - YW) / L])    # roof normal
t = np.array([1.0, 0.0, 0.0])
for i, zh in enumerate(HIGH):
    last = i == len(HIGH) - 1
    eave = 0.20 if last else 0.0
    top = np.array([0.0, YR, zh])
    mid = top + b * (L + eave) / 2 + n * 0.04
    mid[0] = (X0 + X1) / 2
    B.obox(f"sheet{i}", mid, t, b, n, (X1 - X0 + 0.30, L + eave, 0.08))
    for k, u in enumerate(SEAMS_U):
        # bays 0 and 2 run u 0.001 -> 0.664 from -x to +x, bay 1 the other way (UVs mirrored)
        f = (u - 0.001) / 0.663
        x = X0 + f * (X1 - X0) if i != 1 else X1 - f * (X1 - X0)
        c = top + b * (L + eave) / 2 + n * 0.10
        c[0] = x
        B.obox(f"seam{i}_{k}", c, t, b, n, (0.06, L + eave, 0.05))
    # drip hood over the clerestory (the front one tops the front wall)
    B.box(f"hood{i}@avg", (X0 - 0.15, YR - 0.02, zh - 0.25), (X1 + 0.15, YR + 0.14, zh + 0.12), chamfer=0.03)

# ---- corner trims
for k, (x, z) in enumerate(((X0, Z0), (X1, Z0), (X0, Z1), (X1, Z1))):
    h = YR if z == Z1 else YW
    B.box(f"corner{k}", (x - 0.07, 0.0, z - 0.07), (x + 0.07, h, z + 0.07))

# ---- loading docks: slabs on dark legs
for k, (za, zb) in enumerate(((-1.06, 2.63), (-5.93, -2.23), (-10.82, -7.12))):
    B.box(f"dock{k}", (-3.424, 0.93, za), (X0, 1.18, zb), chamfer=0.02)
    for j, z in enumerate((za + 0.15, (za + zb) / 2, zb - 0.15)):
        B.box(f"leg{k}_{j}@3c3b38", (-3.36, 0.0, z - 0.08), (-3.20, 0.93, z + 0.08))

print(B.dump())
