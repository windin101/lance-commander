#!/usr/bin/env python3
"""CAD rebuild of the Liao palace keep (appearance l_palacecore), in the original's frame.

    D=~/craft/solid/mc2/buildings/l_palacecore
    python3 -I tools/art/cad_building.py openings l_palacecore > $D/openings.json
    python3 -I tools/cad/l_palacecore_cad.py $D > $D/l_palacecore.json
    solidcraft-cli run $D/l_palacecore.json --out $D/l_palacecore.obj
    python3 -I tools/art/cad_building.py bake l_palacecore $D/l_palacecore.obj --max-res 4096

Measured from game/assets/objects/l_palacecore.glb (nine closed shells): the lower hall (x -10.43..10.38,
z -15.69..5.78, 16.59 m) under a parapet slab (x +-11.24, 16.60..17.76 m, its field at 17.13 m); the keep
(x +-7.48, z -26.74..-3.92) to 27.57 m; over it the big roof (x +-8.1, vertical back at z -27.37, front slope
from z -3.29 at 27.57 m to z -13.96 at 34.13 m), a dark clerestory (x +-6.76, z -26.02..-15.30) to 37.72 m, the
upper roof slope (z -14.68 -> -22.34, 37.73..41.59 m), the lantern (x +-2.96, z -25.98..-19.39) to 44.23 m and
the three-tier pagoda cap to 46.65 m. Two stair ramps (the front one from the ground to the hall door at 9.54 m,
the upper one from the slab to the keep door at 19.33 m) are real steps here (flat-coloured from the art under
each: dark risers, light treads with a nosing). Relief: every cut-out window is a 20 cm recess with a sill under the lower row, ledges ring the hall at
9.44 m and the keep at 16.11 m, raised seams run down both roof slopes, the parapet field is sunk 60 cm.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
B = Builder()


def ring(name, x0, x1, z0, z1, y0, y1, proud):
    """A projecting band round an axis box's four walls."""
    p = proud
    B.box(f"{name}0", (x0 - p, y0, z0 - p), (x1 + p, y1, z0 + 0.02))
    B.box(f"{name}1", (x0 - p, y0, z1 - 0.02), (x1 + p, y1, z1 + p))
    B.box(f"{name}2", (x0 - p, y0, z0), (x0 + 0.02, y1, z1))
    B.box(f"{name}3", (x1 - 0.02, y0, z0), (x1 + p, y1, z1))


def slope_ribs(name, x0, x1, n, za, ya, zb, yb, w=0.14, proud=0.07):
    """Raised seams down a roof slope that runs from (za, ya) to (zb, yb), spread over x0..x1."""
    t = np.array([0.0, yb - ya, zb - za])
    L = float(np.linalg.norm(t))
    t /= L
    nn = np.array([0.0, t[2], -t[1]])
    if nn[1] < 0:
        nn = -nn
    tx = np.array([1.0, 0.0, 0.0])
    if np.dot(np.cross(tx, t), nn) < 0:
        t = -t
    for k in range(n):
        x = x0 + (x1 - x0) * (k + 1) / (n + 1)
        c = np.array([x, (ya + yb) / 2, (za + zb) / 2]) + nn * (proud / 2 - 0.02)
        B.obox(f"{name}{k}@avg", c, tx, t, nn, (w, L - 0.1, proud + 0.02))


def stairs(name, x0, x1, z_top, y_top, z_bot, y_bot, n):
    """Steps from (z_bot, y_bot) up to a wall at z_top (y_top): each step a box down to y_bot, a tread plate on top."""
    s = 1 if z_bot > z_top else -1
    for k in range(n):
        y = y_bot + (y_top - y_bot) * (k + 1) / n
        z = z_bot + (z_top - z_bot) * k / n
        lo, hi = sorted([z, z_top])
        B.box(f"{name}{k}@7c7c7a", (x0, y_bot, lo), (x1, y - 0.04, hi))
        z1 = z_bot + (z_top - z_bot) * (k + 1) / n
        a, b = sorted([z - s * 0.03, z1])
        B.box(f"{name}t{k}@b4b4b0", (x0, y - 0.04, a), (x1, y, b))  # the tread with its nosing


# ---- the lower hall and its parapet slab
hall = B.box("hall", (-10.43, 0.0, -15.69), (10.38, 16.59, 5.78))
ring("hall_ledge", -10.43, 10.38, -15.69, 5.78, 9.36, 9.52, 0.10)
slab = B.box("slab", (-11.24, 16.60, -16.50), (11.19, 17.76, 6.59))
B.cut(slab, B.box("slab_field", (-10.80, 17.13, -16.06), (10.75, 17.9, 6.15)))

# ---- the keep
keep = B.box("keep", (-7.48, 0.0, -26.74), (7.45, 27.57, -3.92))
ring("keep_ledge", -7.48, 7.45, -26.74, -3.92, 16.03, 16.19, 0.10)

# ---- roofs
B.prism_x("roof1", [(-27.37, 27.57), (-3.29, 27.57), (-13.96, 34.13), (-27.37, 34.13)], -8.11, 8.08)
slope_ribs("rib1_", -8.11, 8.08, 5, -3.29, 27.57, -13.96, 34.13)
B.box("clere", (-6.76, 34.13, -26.02), (6.74, 37.72, -15.30))
B.prism_x("roof2", [(-26.65, 37.73), (-14.68, 37.73), (-22.34, 41.59), (-26.60, 41.59)], -7.39, 7.37)
slope_ribs("rib2_", -7.39, 7.37, 4, -14.68, 37.73, -22.34, 41.59)
B.box("lantern", (-2.96, 39.88, -25.98), (2.97, 44.23, -19.39))


def rect(x0, x1, z0, z1):
    return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]


tiers = [(44.23, (-3.59, 3.60, -26.61, -18.76)), (44.68, (-2.24, 2.25, -25.26, -20.11)),
         (45.31, (-1.52, 1.53, -24.54, -20.83)), (46.65, (-0.53, 0.55, -23.55, -21.82))]
for k in range(3):
    (ya, ra), (yb, rb) = tiers[k], tiers[k + 1]
    B.loft_y(f"cap{k}", rect(*ra), ya, rect(*rb), yb)

# ---- stairs: front (ground -> hall door), upper (slab -> keep door)
stairs("stepf", -6.68, 6.97, 5.79, 9.54, 17.75, -0.07, 30)
stairs("stepu", -4.54, 4.31, -3.97, 19.33, 0.37, 16.96, 8)

# ---- windows
k = 0
for o in json.load(open(D / "openings.json"))["openings"]:
    B.recess(keep, o, 0.2)
    if o["center"][1] < 24:
        B.sill(f"sill{k}", o, proud=0.1, thick=0.08, overhang=0.06)
    k += 1

print(B.dump())
