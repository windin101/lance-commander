#!/usr/bin/env python3
"""CAD rebuild of the Liao palace corner tower (appearance l_palacetwr), in the original's frame.

    D=~/craft/solid/mc2/buildings/l_palacetwr
    python3 -I tools/art/cad_building.py openings l_palacetwr > $D/openings.json
    python3 -I tools/cad/l_palacetwr_cad.py $D > $D/l_palacetwr.json
    solidcraft-cli run $D/l_palacetwr.json --out $D/l_palacetwr.obj
    python3 -I tools/art/cad_building.py bake l_palacetwr $D/l_palacetwr.obj

Measured from game/assets/objects/l_palacetwr.glb (three closed shells): a plinth (x -6.14..6.61,
z -6.62..9.37, to 0.43 m), the walls set back 73 cm (x -5.41..5.87, z ..8.64) to 7.45 m, a hipped eave roof
from the plinth's footprint up to the flat deck at 8.64 m (x -3.80..4.26, z ..7.02; the back face is vertical),
the windowed cab (x -3.50..3.88, z -0.61..6.78) to 11.68 m and its four-tier pagoda cap to 14.83 m. Relief:
every cut-out window is a 20 cm recess with a sill, raised seams down the three eave slopes and the cap's first
tier, a 10 cm drip ledge under the eaves, the deck sunk 6 cm inside a rim.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
B = Builder()
ZB = -6.62  # back wall (the original's is skewed 13 cm over its width)


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


B.box("plinth", (-6.14, -0.09, ZB), (6.61, 0.43, 9.37))
walls = B.box("walls", (-5.41, 0.43, ZB), (5.87, 7.45, 8.64))
B.box("drip0", (-5.51, 7.29, ZB), (5.97, 7.45, 8.74))
eave = B.loft_y("eave", rect(-6.14, 6.61, ZB, 9.37), 7.45, rect(-3.80, 4.26, ZB, 7.02), 8.64)
B.cut(eave, B.box("deck_field", (-3.55, 8.58, ZB + 0.25), (4.01, 8.8, 6.77)))
# seams: front (+z), left (-x), right (+x) slopes
trap_ribs("rf", (-6.14, 7.45, 9.37), (6.61, 7.45, 9.37), (-3.80, 8.64, 7.02), (4.26, 8.64, 7.02), 9)
trap_ribs("rl", (-6.14, 7.45, ZB), (-6.14, 7.45, 9.37), (-3.80, 8.64, ZB), (-3.80, 8.64, 7.02), 10, f0=0.05)
trap_ribs("rr", (6.61, 7.45, 9.37), (6.61, 7.45, ZB), (4.26, 8.64, 7.02), (4.26, 8.64, ZB), 10, f1=0.95)

cab = B.box("cab", (-3.50, 8.58, -0.61), (3.88, 11.68, 6.78))
tiers = [(11.68, (-4.49, 4.87, -1.60, 7.76)), (12.04, (-3.23, 3.61, -0.34, 6.51)),
         (12.85, (-2.34, 2.71, 0.56, 5.61)), (13.93, (-1.62, 1.99, 1.28, 4.89)), (14.83, (-1.44, 1.81, 1.46, 4.71))]
for k in range(4):
    (ya, ra), (yb, rb) = tiers[k], tiers[k + 1]
    B.loft_y(f"cap{k}", rect(*ra), ya, rect(*rb), yb)
# seams on the cap's second tier (the steep one), all four faces
(ya, (x0, x1, z0, z1)), (yb, (u0, u1, v0, v1)) = tiers[1], tiers[2]
trap_ribs("c0", (x0, ya, z1), (x1, ya, z1), (u0, yb, v1), (u1, yb, v1), 4, w=0.08, proud=0.05, f0=0.2, f1=0.8)
trap_ribs("c1", (x1, ya, z0), (x0, ya, z0), (u1, yb, v0), (u0, yb, v0), 4, w=0.08, proud=0.05, f0=0.2, f1=0.8)
trap_ribs("c2", (x0, ya, z0), (x0, ya, z1), (u0, yb, v0), (u0, yb, v1), 4, w=0.08, proud=0.05, f0=0.2, f1=0.8)
trap_ribs("c3", (x1, ya, z1), (x1, ya, z0), (u1, yb, v1), (u1, yb, v0), 4, w=0.08, proud=0.05, f0=0.2, f1=0.8)

k = 0
for o in json.load(open(D / "openings.json"))["openings"]:
    B.recess(cab, o, 0.2)
    B.sill(f"sill{k}", o, proud=0.1, thick=0.07, overhang=0.06)
    k += 1

print(B.dump())
