#!/usr/bin/env python3
"""CAD rebuild of the Liao headquarters (appearance l_hq), in the original's frame.

    D=~/craft/solid/mc2/buildings/l_hq
    python3 -I tools/art/cad_building.py openings l_hq > $D/openings.json
    python3 -I tools/cad/l_hq_cad.py $D > $D/l_hq.json
    solidcraft-cli run $D/l_hq.json --out $D/l_hq.obj
    python3 -I tools/art/cad_building.py bake l_hq $D/l_hq.obj

Measured from game/assets/objects/l_hq.glb (vertices listed by height): an arched hall (z -18.42..9.58) whose
roof overhangs its walls (x -8.35..8.34, 3.92 m) to x -9.96..9.96 and rests on four piers (x -9.96..-8.35 and
8.34..9.96, z -10.42..-8.42 and -0.42..1.58); the roof is a high half-arch on -x (from 3.92 m at x -9.96 to
10.32 m at x 1.17, a clerestory step down to the flat 7.74 m roof) and a low quarter-arch on +x (x 7.04..9.96,
from z -10.42 only, where it meets the tower). The original's arches are 4- and 3-facet polylines; here they are
true curves (Catmull-Rom through the original's vertices, 6 segments a facet; issue I77), so the painted roof
bands stay where they were. The tower (x 1.18..9.96, z -10.38.., its front chamfered to z -20.65 between x 3.18
and 8.00) stands straight to 7.78 m, tapers to 15.08 m and flares out to the 17.75 m cab roof with its painted
helipad. Relief: the painted bands over the piers are 8 cm raised ribs over both arches, every cut-out window is a
20 cm recess (doors 25 cm) with sills under the wall windows, the flat roof and the helipad are 8 cm fields inside
their rims, a ledge rings the tower where it starts to taper.
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


def catmull(pts, k=6):
    """A smooth curve through the points (end tangents mirrored)."""
    P = [np.array(p, float) for p in pts]
    P = [2 * P[0] - P[1]] + P + [2 * P[-1] - P[-2]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for s in range(k):
            t = s / k
            out.append(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-2])
    return [tuple(map(float, p)) for p in out]


def offset(curve, d):
    """Offset a polyline (x, y) by d along its left normal (outward for these arches, drawn left to right)."""
    c = np.array(curve)
    out = []
    for i in range(len(c)):
        a, b = c[max(i - 1, 0)], c[min(i + 1, len(c) - 1)]
        t = (b - a) / np.linalg.norm(b - a)
        out.append(tuple(c[i] + d * np.array([-t[1], t[0]])))
    return out


ARCH_L = catmull([(-9.96, 3.92), (-9.42, 5.89), (-7.84, 7.68), (-5.37, 9.10), (-2.27, 10.01), (1.17, 10.32)])
ARCH_R = catmull([(7.04, 7.74), (8.70, 7.01), (9.79, 5.52), (9.96, 3.93)])

# ---- hall: walls, piers, the two arched roofs
B.box("wall_l", (-8.35, 0.0, -18.42), (1.18, 3.92, 9.58))
B.box("wall_r", (1.18, 0.0, -10.42), (8.34, 3.93, 9.58))
for k, (x0, x1) in enumerate([(-9.96, -8.35), (8.34, 9.96)]):
    for j, (z0, z1) in enumerate([(-10.42, -8.42), (-0.42, 1.58)]):
        B.box(f"pier{k}{j}", (x0, 0.0, z0), (x1, 3.93, z1))
hall_l = B.prism_z("hall_l", ARCH_L + [(1.17, 3.92)], -18.42, 9.58)
hall_r = B.prism_z("hall_r", [(1.17, 3.93), (1.17, 7.74)] + ARCH_R, -10.42, 9.58)
B.cut(hall_r, B.box("flat_field", (1.45, 7.66, -10.14), (6.76, 7.90, 9.30)))
# raised ribs over the piers: each arch's outline pushed out 8 cm
for j, (z0, z1) in enumerate([(-10.42, -8.42), (-0.42, 1.58)]):
    lo = offset(ARCH_L, -0.10)
    hi = offset(ARCH_L, 0.08)
    B.prism_z(f"rib_l{j}", hi + [(1.25, 10.33), (1.25, 10.20)] + lo[::-1], z0, z1)
    lo = offset(ARCH_R, -0.10)
    hi = offset(ARCH_R, 0.08)
    B.prism_z(f"rib_r{j}", [(7.0, 7.64), (7.0, 7.82)] + hi[1:] + lo[::-1][:-1], z0, z1)

# ---- tower
tb = [(1.18, -10.38), (1.18, -18.42), (3.18, -20.65), (8.00, -20.65), (9.96, -18.42), (9.96, -10.38)]
tm = [(1.82, -10.36), (1.82, -17.29), (3.52, -19.14), (7.65, -19.14), (9.34, -17.29), (9.34, -10.36)]
tc = [(0.35, -10.36), (0.35, -17.87), (2.70, -20.41), (8.37, -20.41), (10.69, -17.87), (10.69, -10.36)]
t_base = B.prism_y("tower_base", tb, 0.0, 7.78)
t_mid = B.loft_y("tower_mid", tb, 7.78, tm, 15.08)
t_cab = B.loft_y("tower_cab", tm, 15.08, tc, 17.75)
B.cut(t_cab, B.prism_y("pad_field", inset(tc, 0.35), 17.67, 17.9))
ring("tower_ledge", tb, 7.68, 7.88, 0.10)

# ---- windows
k = 0
for o in json.load(open(D / "openings.json"))["openings"]:
    x, y, z = o["center"]
    n = o["normal"]
    if abs(z + 10.38) < 0.05 and n[2] > 0.9 and y < 7.8:
        continue  # the tower's back wall inside the hall
    in_tower = x > 1.1 and z < -10.37 and not (abs(n[0]) > 0.9 and abs(x - 1.17) < 0.05)
    if in_tower:
        tgt = t_cab if y > 15.08 else t_mid if y > 7.78 else t_base
    elif x < 1.16 or (abs(x - 1.17) < 0.05 and n[0] > 0.9):
        tgt = "wall_l" if y < 3.92 else hall_l
    else:
        tgt = "wall_r" if y < 3.93 else hall_r
    door = o["h"] > 2.3 and y < 3
    B.recess(tgt, o, 0.25 if door else 0.2)
    if not door and abs(n[1]) < 0.1 and o["w"] > 0.5 and not in_tower:
        B.sill(f"sill{k}", o, proud=0.1, thick=0.07, overhang=0.06)
    k += 1

print(B.dump())
