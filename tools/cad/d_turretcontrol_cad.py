#!/usr/bin/env python3
"""CAD rebuild of the desert turret control centre (appearance d_turretcontrol), in the original's frame.

    D=~/craft/solid/mc2/buildings/d_turretcontrol
    python3 -I tools/art/cad_building.py openings d_turretcontrol > $D/openings.json
    python3 -I tools/cad/d_turretcontrol_cad.py $D > $D/d_turretcontrol.json
    solidcraft-cli run $D/d_turretcontrol.json --out $D/d_turretcontrol.obj
    python3 -I tools/art/cad_building.py bake d_turretcontrol $D/d_turretcontrol.obj --keep "small Dish"

Measured from game/assets/objects/d_turretcontrol.glb (vertices listed by height): a main block
(x -8.73..1.68, z -7.70..8.40, 3.79 m) whose chamfered front is battered back to z 6.52; a raised control room on
its roof (to 5.18 m, chamfered to 5.65 m) carrying the small dish (kept verbatim) on a pyramid; a low wing on
-x (2.84 m) and a block at -z (3.24 m), both with battered outer faces; a connector (3.52 m) to the hexagonal
tower (tapering to 11.18 m, a straight window band to 13.36 m), its radar pedestal wedge (14.70 m) and the
spinner bar (15.49 m); two buttresses on the main block's sides joined by the white beam painted across its roof;
an L-shaped low wall with a gate gap and a lamp post. Relief: every cut-out window is a 20 cm recess with a sill
(the front strip split into its flat and chamfer parts), roof fields are 10 cm recesses inside their painted rims,
the painted roof beam is a raised bar, a ledge rings the tower at the window band and the control room's base.
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


def ccw(poly):
    a = sum(x0 * -z1 - x1 * -z0 for (x0, z0), (x1, z1) in zip(poly, poly[1:] + poly[:1]))
    return poly if a > 0 else poly[::-1]


def inset(poly, d):
    """Inward offset of a convex (x, z) polygon by d (mitred)."""
    q = [(x, -z) for x, z in ccw(poly)]
    n = len(q)
    lines = []
    for i in range(n):
        (x0, y0), (x1, y1) = q[i], q[(i + 1) % n]
        ex, ey = x1 - x0, y1 - y0
        L = math.hypot(ex, ey)
        lines.append(((x0 - ey / L * d, y0 + ex / L * d), (ex, ey)))
    out = []
    for i in range(n):
        (pp, e), (qq, f) = lines[i - 1], lines[i]
        det = e[0] * -f[1] + f[0] * e[1]
        t = ((qq[0] - pp[0]) * -f[1] + f[0] * (qq[1] - pp[1])) / det
        out.append((pp[0] + e[0] * t, -(pp[1] + e[1] * t)))
    return out


def ring(name, poly, y0, y1, proud):
    """A projecting band round a polygon's walls: one box per edge, overlapping at the corners."""
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


# ---- main block, battered chamfered front
main_lo = [(-8.73, -7.70), (1.68, -7.70), (1.68, 6.54), (-0.21, 8.40), (-6.84, 8.40), (-8.73, 6.54)]
main_hi = [(-8.73, -7.70), (1.68, -7.70), (1.68, 4.63), (-0.21, 6.52), (-6.84, 6.52), (-8.73, 4.63)]
main = B.loft_y("main", main_lo, 0.0, main_hi, 3.79)
B.cut(main, B.prism_y("main_field", inset(main_hi, 0.32), 3.69, 3.95))
# buttresses and the white beam painted across the roof
B.prism_z("buttress0", [(-10.60, 0.0), (-8.73, 0.0), (-8.73, 3.79), (-9.67, 3.79)], 1.71, 2.66)
B.prism_z("buttress1", [(1.68, 0.0), (3.55, 0.0), (2.62, 3.79), (1.68, 3.79)], 1.71, 2.66)
B.box("beam", (-9.67, 3.69, 1.71), (2.62, 3.95, 2.66))

# ---- control room on the roof
room = B.box("room", (-7.83, 3.69, -6.75), (-2.06, 5.18, -0.13))
B.loft_y("room_top", [(-7.83, -6.75), (-2.06, -6.75), (-2.06, -0.13), (-7.83, -0.13)], 5.18,
         [(-7.23, -6.01), (-2.66, -6.01), (-2.66, -0.88), (-7.23, -0.88)], 5.65)
B.cut("room_top", B.prism_y("room_field", inset([(-7.23, -6.01), (-2.66, -6.01), (-2.66, -0.88), (-7.23, -0.88)], 0.28), 5.57, 5.8))
ring("room_ledge", [(-7.83, -6.75), (-2.06, -6.75), (-2.06, -0.13), (-7.83, -0.13)], 3.79, 3.93, 0.08)
B.loft_y("dish_base", [(-4.28, -2.80), (-3.82, -2.80), (-4.05, -2.48)], 5.55, [(-4.07, -2.73), (-4.05, -2.73), (-4.06, -2.71)], 6.32)

# ---- wing on -x and the block at -z, both battered
B.loft_y("wing", [(-12.47, -7.44), (-8.72, -7.44), (-8.72, -3.10), (-12.47, -3.10)], 0.0,
         [(-11.52, -7.44), (-8.72, -7.44), (-8.72, -3.10), (-11.52, -3.10)], 2.84)
B.loft_y("blocka", [(-3.23, -11.51), (1.50, -11.51), (1.50, -7.72), (-3.23, -7.72)], 0.0,
         [(-3.23, -10.56), (1.50, -10.56), (1.50, -7.72), (-3.23, -7.72)], 3.24)
ring("wing_cap", [(-11.52, -7.44), (-8.72, -7.44), (-8.72, -3.10), (-11.52, -3.10)], 2.74, 2.92, 0.06)
ring("blocka_cap", [(-3.23, -10.56), (1.50, -10.56), (1.50, -7.72), (-3.23, -7.72)], 3.14, 3.32, 0.06)

# ---- connector and tower
B.loft_y("connector", [(1.36, -7.58), (3.15, -7.58), (3.15, -2.70), (1.36, -2.70)], 0.0,
         [(1.36, -7.13), (3.61, -7.13), (3.61, -3.06), (1.36, -3.06)], 3.52)
tb = [(3.15, -7.58), (3.15, -2.70), (7.37, -0.27), (11.59, -2.70), (11.59, -7.58), (7.37, -10.01)]
tt = [(4.54, -6.68), (4.54, -3.42), (7.37, -1.78), (10.20, -3.42), (10.20, -6.68), (7.37, -8.31)]
B.loft_y("tower", tb, 0.0, tt, 11.18)
band = B.prism_y("tower_band", tt, 11.18, 13.36)
B.cut(band, B.prism_y("tower_field", inset(tt, 0.4), 13.26, 13.5))
ring("tower_ledge", tt, 11.08, 11.28, 0.14)
B.prism_x("pedestal", [(-6.12, 13.26), (-4.90, 13.26), (-4.90, 14.70), (-5.27, 14.70)], 6.84, 7.91)
B.prism_y("spinner", [(4.75, -4.97), (10.03, -4.64), (10.08, -5.31), (4.79, -5.65)], 14.70, 15.49)

# ---- windows
ops = json.load(open(D / "openings.json"))["openings"]
SOLIDS = [((-8.73, 0, -7.70), (1.68, 3.79, 6.6)), ((-12.47, 0, -7.44), (-8.72, 2.84, -3.10)),
          ((-3.23, 0, -11.51), (1.50, 3.24, -7.72)), ((1.36, 0, -7.58), (3.15, 3.52, -2.70))]


def hidden(o):
    p = np.array(o["center"]) + np.array(o["normal"]) * 0.15
    return any(np.all(p > np.array(lo) - 0.01) and np.all(p < np.array(hi) + 0.01) for lo, hi in SOLIDS)


def owner(o):
    x, y, z = o["center"]
    if y > 11:
        return band
    if y > 3.8:
        return room
    if x < -8.7:
        return "wing"
    if z < -7.71:
        return "blocka"
    return main


k = 0
for o in ops:
    if hidden(o):
        continue
    if o["w"] > 5 and o["center"][2] > 6:  # the front strip: flat face, then its two chamfers below
        n = np.array([0.0, 1.88, 3.79]) / math.hypot(1.88, 3.79)
        y = o["center"][1]
        o = dict(o, center=[-3.525, y, 8.40 - 1.88 * y / 3.79], normal=list(n), t=[1.0, 0.0, 0.0],
                 b=list(np.cross(n, [1.0, 0.0, 0.0])), w=6.0)
    rec = [o]
    if 0.5 < o["normal"][0] and o["center"][2] > 6:  # the chamfer piece, and its mirror on the -x chamfer
        m = lambda v: [-v[0], v[1], v[2]]
        rec.append(dict(o, center=[-7.05 - o["center"][0] + 0.0, o["center"][1], o["center"][2]],
                        normal=m(o["normal"]), t=[-a for a in m(o["t"])], b=m(o["b"])))
        rec[1]["center"][0] = -3.525 * 2 - o["center"][0]
    for r in rec:
        B.recess(owner(r), r, 0.2)
        if r["center"][1] < 11:
            B.sill(f"sill{k}", r, proud=0.1, thick=0.07, overhang=0.06)
        k += 1

# ---- low wall with a gate gap, lamp post
B.prism_y("wall0", [(7.83, -0.58), (8.33, -1.07), (8.33, 0.92), (7.83, 0.92)], 0.0, 0.95)
B.prism_y("wall1", [(7.83, 1.99), (8.33, 1.99), (8.33, 4.08), (7.83, 3.59)], 0.0, 0.95)
B.box("wall2", (1.63, 0.0, 3.59), (7.83, 0.95, 4.08))
B.prism_y("lamp", [(7.37, 3.30), (7.51, 3.16), (7.65, 3.30), (7.51, 3.44)], 0.0, 4.63)
B.prism_y("lamp_head", [(7.05, 2.92), (7.13, 2.84), (7.59, 3.29), (7.50, 3.38)], 4.63, 4.79)

print(B.dump())
