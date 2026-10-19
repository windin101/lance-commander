#!/usr/bin/env python3
"""CAD rebuild of the sensor tower (appearance sensortower), in the original's frame.

    D=~/craft/solid/mc2/buildings/sensortower
    python3 -I tools/art/cad_building.py decal sensortower 0 0.06 0.60 0.62 0.745 > $D/decal_f1.json
    python3 -I tools/art/cad_building.py decal sensortower 0 0.06 0.81 0.62 0.955 > $D/decal_f2.json
    python3 -I tools/cad/sensortower_cad.py $D > $D/sensortower.json
    solidcraft-cli run $D/sensortower.json --out $D/sensortower.obj
    python3 -I tools/art/cad_building.py bake sensortower $D/sensortower.obj --keep Sensorpivot Sensordish

Measured from game/assets/objects/sensortower.glb: a six-sided battered plinth (ground outline to a hexagon at
1.56 m), a square shaft tapering linearly from 2.1 m at 1.54 m to 1.63 m at 15.11 m in three painted tiers;
the pivot and the dish are kept verbatim from the original (with their upscaled art). Relief: the painted
fields either side of each tier's riveted centre bar are 6 cm recesses (mapped from the panel tile), the tier
joints are projecting bands, the shaft top a cap band, the plinth's top a ledge.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
B = Builder()


def ccw(poly):
    a = sum(x0 * -z1 - x1 * -z0 for (x0, z0), (x1, z1) in zip(poly, poly[1:] + poly[:1]))
    return poly if a > 0 else poly[::-1]


def ring(name, poly, y0, y1, proud):
    p = ccw(poly)
    cx, cz = np.mean([a[0] for a in p]), np.mean([a[1] for a in p])
    for i in range(len(p)):
        a, b = np.array(p[i]), np.array(p[(i + 1) % len(p)])
        e = b - a
        L = float(np.linalg.norm(e))
        t = np.array([e[0], 0.0, e[1]]) / L
        n = np.cross(t, [0.0, 1.0, 0.0])
        if ((a + b) / 2 - [cx, cz]) @ n[[0, 2]] < 0:
            n = -n
        bv = np.cross(n, t)
        if bv[1] < 0:
            t, bv = -t, -bv
        c = np.array([(a[0] + b[0]) / 2, (y0 + y1) / 2, (a[1] + b[1]) / 2]) + n * (proud / 2 - 0.02)
        B.obox(f"{name}{i}", c, t, bv, n, (L + 2 * proud, y1 - y0, proud + 0.02))


def sq(y):
    """The shaft's square at height y (linear taper)."""
    f = (y - 1.54) / (15.11 - 1.54)
    x0, x1, z0, z1 = -1.12 + 0.24 * f, 0.98 - 0.23 * f, -1.22 + 0.23 * f, 0.88 - 0.24 * f
    return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]


plinth_lo = [(-1.27, -3.06), (1.13, -3.06), (3.58, 0.45), (2.55, 2.22), (-2.56, 2.24), (-3.58, 0.49)]
plinth_hi = [(-1.08, -1.94), (0.97, -1.94), (1.99, -0.02), (1.50, 1.22), (-1.61, 1.22), (-2.11, -0.02)]
B.loft_y("plinth", plinth_lo, 0.0, plinth_hi, 1.56)
ring("plinth_ledge", plinth_hi, 1.42, 1.56, 0.06)
shaft = B.loft_y("shaft", sq(1.54), 1.54, sq(15.11), 15.11)
for k, y in enumerate((6.06, 10.58)):
    ring(f"band{k}_", sq(y), y - 0.08, y + 0.08, 0.05)
ring("cap", sq(15.0), 14.95, 15.11, 0.08)

fields = [o for f in ("f1", "f2") for o in json.load(open(D / f"decal_{f}.json"))["rects"]
          if abs(o["normal"][1]) < 0.1 and o["center"][1] < 15]
# the +z face's lowest right-hand field is missing from the atlas lookup: mirror its left-hand neighbour
src = next(o for o in fields if o["normal"][2] > 0.9 and abs(o["center"][1] - 3.73) < 0.1)
fields.append(dict(src, center=[-0.15 - src["center"][0], src["center"][1], src["center"][2]], w=0.69))
for o in fields:
    B.recess(shaft, dict(o, h=o["h"] - 0.1), 0.06)

print(B.dump())
