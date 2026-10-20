#!/usr/bin/env python3
"""CAD rebuild of the turret control centre (appearance bturretcontrol), in the original's frame.

    D=~/craft/solid/mc2/buildings/bturretcontrol
    python3 -I tools/art/cad_building.py openings bturretcontrol > $D/openings.json
    python3 -I tools/cad/bturretcontrol_cad.py $D > $D/bturretcontrol.json
    solidcraft-cli run $D/bturretcontrol.json --out $D/bturretcontrol.obj
    python3 -I tools/art/cad_building.py bake bturretcontrol $D/bturretcontrol.obj

Measured from game/assets/objects/bturretcontrol.glb (faces grouped by plane): a 0.32 m plinth
(x -11.03..5.13, z -9.94..9.28) under the main block, battered back to its 4.58 m roof (x -9.21..2.95,
z -7.74..7.14); a louvred vent box running through it (x -11.38..5.38, z 2.83..5.10, 3.67 m), its ends showing
on both sides; a corner block at -x -z (plinth x -12.46..-5.61, z -12.26..-5.72, battered to 4.71 m, then straight
to 6.75 m) carrying two masts (true cones, 20 sides; antennae_PAB in the original, 13.15 m and 17.68 m); a connector
(x 2.06..7.10, z -7.74..-2.83, 3.87 m) to the hexagonal tower (tapering from x 5.91..12.73 to 6.98..11.66 at
12.79 m, a straight window band to 16.12 m), its radar pedestal wedge (17.75 m), a round pivot and the spinner bar
(Spinner_PAB, 17.82..18.84 m); an L-shaped low wall (1.15 m) with a gate gap. Relief: every cut-out window is a
20 cm recess with a sill (the vent ends 10 cm), the roofs' fields are 10 cm recesses inside their painted rims,
a ledge rings the tower at the band and the corner block where it turns straight.
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


def ngon(cx, cz, r, n=20):
    return [(cx + r * math.cos(2 * math.pi * i / n), cz + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


# ---- main block on its plinth
B.box("plinth", (-11.03, 0.0, -9.94), (5.13, 0.32, 9.28))
main_lo = [(-11.03, -9.94), (5.13, -9.94), (5.13, 9.28), (-11.03, 9.28)]
main_hi = [(-9.21, -7.74), (2.95, -7.74), (2.95, 7.14), (-9.21, 7.14)]
main = B.loft_y("main", main_lo, 0.32, main_hi, 4.58)
B.cut(main, B.prism_y("main_field", inset(main_hi, 0.3), 4.48, 4.75))
vent = B.box("vent", (-11.38, 0.0, 2.83), (5.38, 3.67, 5.10))

# ---- corner block with the masts
B.box("corner_plinth", (-12.46, 0.0, -12.26), (-5.61, 0.32, -5.72))
c_hi = [(-11.82, -11.83), (-6.19, -11.83), (-6.19, -6.15), (-11.82, -6.15)]
B.loft_y("corner_low", [(-12.46, -12.26), (-5.61, -12.26), (-5.61, -5.72), (-12.46, -5.72)], 0.32, c_hi, 4.71)
corner = B.box("corner", (-11.82, 4.71, -11.83), (-6.19, 6.74, -6.15))
B.cut(corner, B.prism_y("corner_field", inset(c_hi, 0.25), 6.64, 6.9))
ring("corner_ledge", c_hi, 4.62, 4.80, 0.07)
for k, (x, top) in enumerate([(-8.52, 13.15), (-7.84, 17.68)]):
    B.loft_y(f"mast{k}", ngon(x, -8.20, 0.13), 6.64, ngon(x, -8.20, 0.035), top)

# ---- connector and tower
B.box("connector", (2.06, 0.0, -7.74), (7.10, 3.87, -2.83))
tb = [(5.91, -7.20), (5.91, -3.26), (9.32, -1.29), (12.73, -3.26), (12.73, -7.20), (9.32, -9.17)]
tt = [(6.98, -6.58), (6.98, -3.88), (9.32, -2.53), (11.66, -3.88), (11.66, -6.58), (9.32, -7.93)]
tower = B.loft_y("tower", tb, 0.0, tt, 12.79)
band = B.prism_y("tower_band", tt, 12.79, 16.12)
B.cut(band, B.prism_y("tower_field", inset(tt, 0.35), 16.02, 16.3))
ring("tower_ledge", tt, 12.69, 12.89, 0.14)
B.prism_x("pedestal", [(-6.53, 16.02), (-5.06, 16.02), (-5.06, 17.75), (-5.50, 17.75)], 8.68, 9.97)
B.prism_y("pivot", ngon(9.33, -5.35, 0.28), 17.70, 17.86)
B.box("spinner", (8.87, 17.82, -8.95), (9.80, 18.84, -1.75), chamfer=0.05)

# ---- low wall with a gate gap
B.box("wall0", (2.90, 0.0, 7.25), (10.99, 1.15, 7.84))
B.prism_y("wall1", [(10.38, -2.06), (10.99, -2.65), (10.99, 2.55), (10.38, 2.55)], 0.0, 1.15)
B.box("wall2", (10.38, 0.0, 5.31), (10.99, 1.15, 7.25))

# ---- windows
k = 0
for o in json.load(open(D / "openings.json"))["openings"]:
    x, y, z = o["center"]
    if y > 12:
        tgt = band
    elif y > 4.7:
        tgt = corner
    elif o["h"] < 0.3:
        B.recess(vent, o, 0.1)
        continue
    else:
        tgt = main
    B.recess(tgt, o, 0.2)
    if o["w"] > 0.5 and y < 12:
        B.sill(f"sill{k}", o, proud=0.1, thick=0.07, overhang=0.06)
    k += 1

print(B.dump())
