#!/usr/bin/env python3
"""CAD rebuild of the stilt storage hut (appearance civstoragec), in the original's frame.

    D=~/craft/solid/mc2/buildings/civstoragec
    python3 -I tools/art/cad_building.py openings civstoragec > $D/openings.json
    python3 -I tools/art/cad_building.py decal civstoragec 0 0.192 0.378 0.350 0.613 > $D/decal_door.json
    python3 -I tools/cad/civstoragec_cad.py $D > $D/civstoragec.json
    solidcraft-cli run $D/civstoragec.json --out $D/civstoragec.obj
    python3 -I tools/art/cad_building.py bake civstoragec $D/civstoragec.obj

Measured from game/assets/objects/civstoragec.glb: a 4.48 x 3.44 m board cabin (x +-2.24, z -3.34..0.10) on a
deck at 2.54 m, walls 5.00 m (-x) to 5.98 m (+x) under a mono-pitch corrugated roof sheet (x +-2.64,
z -3.78..0.54, 4.91 -> 6.07 m). It stands on four trestle frames (x = +-2.09, z = -3.20 / -0.04) that the original
paints as X-braced cut-outs, here real 25 cm posts and 12 x 18 cm cross braces; a stair of nine 39 cm treads
between two stringers (x = +-0.63) runs from the deck down to z 3.69. Relief: the door (decal, 1.28 x 2.15 m) a
10 cm recess with a frame and sill; the small -x window a 12 cm recess with a sill (a hood over it read as a box); corner trims; a deck rim beam (one flat colour: sampled, it striped);
the roof a 6 cm sheet with 15 cm verges and standing seams on the painted dark lines (u minima of the roof tile).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
X0, X1, Z0, Z1 = -2.24, 2.24, -3.34, 0.10
YD, YL, YH = 2.54, 5.00, 5.98          # deck, low (-x) and high (+x) wall tops
RX, RZ0, RZ1, RYL, RYH = 2.64, -3.78, 0.54, 4.91, 6.07
SEAMS_U = (0.432, 0.48, 0.525, 0.574, 0.621, 0.668, 0.715, 0.76, 0.807, 0.855, 0.9, 0.947)

B = Builder()
cabin = B.prism_z("cabin", [(X0, YD), (X1, YD), (X1, YH), (X0, YL)], Z0, Z1)

door = json.load(open(D / "decal_door.json"))["rects"][0]
B.recess(cabin, door, 0.10)
B.frame("doorframe", door, width=0.07, proud=0.05)
B.sill("doorsill", door, proud=0.10, thick=0.05, overhang=0.08)
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    if o["center"][1] > 3.0 and abs(o["normal"][0]) > 0.9 and o["normal"][0] < 0:  # the -x window
        B.recess(cabin, o, 0.12)
        B.sill(f"sill{k}", o, proud=0.08, thick=0.05, overhang=0.05)

# corner trims and the deck rim
for k, (x, z) in enumerate(((X0, Z0), (X1, Z0), (X0, Z1), (X1, Z1))):
    h = YL if x < 0 else YH
    B.box(f"trim{k}", (x - 0.06, YD, z - 0.06), (x + 0.06, h - 0.05 if x < 0 else h - 0.02, z + 0.06))
B.box("rim@avg", (X0 - 0.08, YD - 0.20, Z0 - 0.08), (X1 + 0.08, YD + 0.02, Z1 + 0.08))

# roof: sheet, verges, standing seams down the slope
L = math.hypot(2 * RX, RYH - RYL)
b = np.array([-2 * RX, -(RYH - RYL), 0.0]) / L      # down the slope (toward -x)
n = np.array([-(RYH - RYL), 2 * RX, 0.0]) / L       # roof normal
t = np.cross(b, n)
mid = np.array([0.0, (RYL + RYH) / 2, (RZ0 + RZ1) / 2]) + n * 0.03
B.obox("roof", mid, t, b, n, (RZ1 - RZ0, L, 0.06))
for k, z in enumerate((RZ0 + 0.04, RZ1 - 0.04)):
    c = mid + n * 0.05
    c[2] = z
    B.obox(f"verge{k}@avg", c, t, b, n, (0.08, L, 0.10))
for k, u in enumerate(SEAMS_U):
    c = mid + n * 0.055
    c[2] = RZ0 + (u - 0.389) / 0.61 * (RZ1 - RZ0)
    B.obox(f"seam{k}", c, t, b, n, (0.05, L, 0.05))

# trestles: posts and X braces on the four frame planes
PX, PZ = (-2.09, 2.09), (-3.20, -0.04)
for i, x in enumerate(PX):
    for j, z in enumerate(PZ):
        B.box(f"post{i}{j}", (x - 0.125, 0.0, z - 0.125), (x + 0.125, YD - 0.20, z + 0.125))


def brace(name, p, q, normal):
    p, q = np.array(p, float), np.array(q, float)
    tt = (q - p) / np.linalg.norm(q - p)
    nn = np.array(normal, float)
    bb = np.cross(nn, tt)
    B.obox(name, (p + q) / 2, tt, bb, nn, (float(np.linalg.norm(q - p)), 0.18, 0.12))


Y0, Y1 = 0.15, YD - 0.25
for i, x in enumerate(PX):   # side frames, in x = const planes, braces 8 cm outboard of the post centre
    xo = x + (0.06 if x > 0 else -0.06)
    brace(f"bx{i}a", (xo, Y0, PZ[0] + 0.1), (xo, Y1, PZ[1] - 0.1), (1, 0, 0))
    brace(f"bx{i}b", (xo, Y0, PZ[1] - 0.1), (xo, Y1, PZ[0] + 0.1), (1, 0, 0))
for j, z in enumerate(PZ):   # end frames, in z = const planes
    zo = z + (0.06 if z > -1.6 else -0.06)
    brace(f"bz{j}a", (PX[0] + 0.1, Y0, zo), (PX[1] - 0.1, Y1, zo), (0, 0, 1))
    brace(f"bz{j}b", (PX[1] - 0.1, Y0, zo), (PX[0] + 0.1, Y1, zo), (0, 0, 1))

# stair: two stringers and nine treads
for k, x in enumerate((-0.63, 0.63)):
    B.prism_x(f"stringer{k}", [(0.10, YD), (3.69, 0.0), (3.29, 0.0), (0.10, YD - 0.31)][::-1], x - 0.04, x + 0.04)
for k in range(9):
    y = 2.54 - 0.302 * k
    z = 0.11 + 0.38 * k
    B.box(f"tread{k}", (-0.59, y - 0.05, z), (0.59, y, z + 0.39))

print(B.dump())
