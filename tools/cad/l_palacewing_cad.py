#!/usr/bin/env python3
"""CAD rebuild of the Liao palace wing (appearance l_palacewing), in the original's frame.

    D=~/craft/solid/mc2/buildings/l_palacewing
    python3 -I tools/art/cad_building.py openings l_palacewing > $D/openings.json
    python3 -I tools/cad/l_palacewing_cad.py $D > $D/l_palacewing.json
    solidcraft-cli run $D/l_palacewing.json --out $D/l_palacewing.obj
    python3 -I tools/art/cad_building.py bake l_palacewing $D/l_palacewing.obj --max-res 4096

Measured from game/assets/objects/l_palacewing.glb (three closed shells; the -x end at x -18.28 / -13.13 is a
flat face where the wing meets the keep): the stone base (x ..11.85, z -9.84..10.63) to 5.96 m flares out to
x ..12.57, z -10.56..11.35 at 8.92 m, stands to 12.15 m and is chamfered back to the 13.15 m terrace; the upper
block (x -12.31..9.84, z -7.83..8.61) rises to 22.43 m under a mansard roof (eave x ..10.64, z -8.64..9.42, then
tiers at 23.24, 24.59, 26.30 and the 27.37 m flat top) with a roof vent box to 29.31 m. Relief: every cut-out
window is a 20 cm recess with a sill, raised seams down the two steep mansard tiers, a 10 cm drip ledge under the
eave, a ledge where the base starts to flare, the terrace and roof fields sunk inside their rims.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
B = Builder()
XW = -18.28  # the flat end against the keep (base); the upper block's is at -13.13


def rect(x0, x1, z0, z1):
    return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]


def trap_ribs(name, a0, a1, b0, b1, n, w=0.12, proud=0.06, f0=0.1, f1=0.9):
    """Raised seams on a planar trapezoid slope: bottom edge a0-a1, top edge b0-b1 (game points)."""
    a0, a1, b0, b1 = (np.array(p, float) for p in (a0, a1, b0, b1))
    nn = np.cross(a1 - a0, b0 - a0)
    nn /= np.linalg.norm(nn)
    if nn[1] < 0:
        nn = -nn
    for k in range(n):
        s = f0 + (f1 - f0) * k / max(n - 1, 1)
        p, q = a0 + (a1 - a0) * s, b0 + (b1 - b0) * s
        t = q - p
        L = float(np.linalg.norm(t))
        t /= L
        tx = np.cross(t, nn)
        c = (p + q) / 2 + nn * (proud / 2 - 0.02)
        B.obox(f"{name}{k}@avg", c, tx, t, nn, (w, L - 0.05, proud + 0.02))


# ---- base
B.box("base", (XW, 0.0, -9.84), (11.85, 5.96, 10.63))
B.box("ledge0", (XW, 5.80, -9.94), (11.95, 5.96, 10.73))
B.loft_y("flare", rect(XW, 11.85, -9.84, 10.63), 5.96, rect(XW, 12.57, -10.56, 11.35), 8.92)
B.box("band", (XW, 8.92, -10.56), (12.57, 12.15, 11.35))
terr = B.loft_y("terrace", rect(XW, 12.57, -10.56, 11.35), 12.15, rect(XW, 11.58, -9.56, 10.36), 13.15)
B.cut(terr, B.box("terr_field", (XW + 0.3, 13.09, -9.26), (11.28, 13.3, 10.06)))

# ---- upper block and mansard
XU = -13.13
walls = B.box("walls", (XU, 13.13, -7.83), (9.84, 22.43, 8.61))
B.box("drip", (XU, 22.27, -7.93), (9.94, 22.44, 8.71))
tiers = [(22.44, (XU, 10.64, -8.64, 9.42)), (23.24, (XU, 9.57, -7.56, 8.34)), (24.59, (XU, 8.22, -6.21, 7.00)),
         (26.30, (XU, 6.96, -4.95, 5.74)), (27.37, (XU, 6.51, -4.50, 5.29))]
for k in range(4):
    (ya, ra), (yb, rb) = tiers[k], tiers[k + 1]
    nm = B.loft_y(f"roof{k}", rect(*ra), ya, rect(*rb), yb)
    if k == 3:
        B.cut(nm, B.box("roof_field", (XU + 0.3, 27.31, -4.20), (6.21, 27.5, 4.99)))
for k in (1, 2):
    (ya, (x0, x1, z0, z1)), (yb, (u0, u1, v0, v1)) = tiers[k], tiers[k + 1]
    trap_ribs(f"rf{k}_", (XU, ya, z0), (x1, ya, z0), (XU, yb, v0), (u1, yb, v0), 9, f0=0.06, f1=0.92)
    trap_ribs(f"rb{k}_", (x1, ya, z1), (XU, ya, z1), (u1, yb, v1), (XU, yb, v1), 9, f0=0.08, f1=0.94)
    trap_ribs(f"rx{k}_", (x1, ya, z0), (x1, ya, z1), (u1, yb, v0), (u1, yb, v1), 5)
B.box("vent", (-9.15, 27.2, -1.76), (-5.44, 29.31, 1.85), chamfer=0.08)

k = 0
for o in json.load(open(D / "openings.json"))["openings"]:
    B.recess(walls, o, 0.2)
    B.sill(f"sill{k}", o, proud=0.1, thick=0.08, overhang=0.06)
    k += 1

print(B.dump())
