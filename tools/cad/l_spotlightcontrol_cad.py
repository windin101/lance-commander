#!/usr/bin/env python3
"""CAD rebuild of the woodland spotlight control post (appearance l_spotlightcontrol), in the original's frame.

    D=~/craft/solid/mc2/buildings/l_spotlightcontrol
    python3 -I tools/art/cad_building.py openings l_spotlightcontrol > $D/openings.json
    python3 -I tools/cad/l_spotlightcontrol_cad.py $D > $D/l_spotlightcontrol.json
    solidcraft-cli run $D/l_spotlightcontrol.json --out $D/l_spotlightcontrol.obj
    python3 -I tools/art/cad_building.py bake l_spotlightcontrol $D/l_spotlightcontrol.obj --keep light

Measured from game/assets/objects/l_spotlightcontrol.glb (vertices listed by height): an octagonal tower
(x 0.56..10.56, z -10.58..-0.58, corners cut 2 m) to 6.63 m, a cab band battered in to 8.76 m (x 1.71..9.41)
and a roof slab flaring back out to 10.50 m (x 0.97..10.15), carrying a square lamp base (x 6.01..8.01,
z -8.49..-6.49 to 6.34..7.68 at 11.36 m) under the lamp (node `light`, kept verbatim). The octagon is the
design (a faceted control tower), so it keeps its facets. Two lean-to quonset huts against the tower: A
(x -7.27..0.57, z -8.01..-3.19) and B (x 3.20..8.01, z -0.58..7.27), each a wall to 1.88 m on the outer side,
a quarter arch to a flat top at 4.00 m and a straight wall on the yard side; the original's two roof facets
are rebuilt as a smooth curve (cubic through the original's middle vertex, 16 segments). A 1 m yard wall in
two pieces closes the yard; two antenna masts (LOS_Ant1) stand on hut B, rebuilt as true 20-sided cones.
Relief: every cut-out window or door is a 15 cm recess with a sill under the yard-side windows (vents painted on the tower behind
the huts are skipped), a cornice at the
cab band's foot and a fascia at the roof slab's eave, the roof top an 8 cm field inside its rim, raised ribs
over each hut's arch (flat-coloured), a coping on the yard wall.
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


def offset(poly, d):
    """Convex polygon (x, z) offset outward by d (inward if d < 0)."""
    P = np.array(poly, float)
    n = len(P)
    area = sum(P[i, 0] * P[(i + 1) % n, 1] - P[(i + 1) % n, 0] * P[i, 1] for i in range(n))
    s = 1 if area > 0 else -1
    lines = []
    for i in range(n):
        a, b = P[i], P[(i + 1) % n]
        e = (b - a) / np.linalg.norm(b - a)
        nrm = np.array([e[1], -e[0]]) * s  # outward
        lines.append((a + nrm * d, e))
    out = []
    for i in range(n):
        (p1, e1), (p2, e2) = lines[i - 1], lines[i]
        m = np.c_[e1, -e2]
        t = np.linalg.solve(m, p2 - p1)
        out.append(tuple(p1 + e1 * t[0]))
    return out


def octa(x0, x1, z0, z1, c):
    return [(x0, z1 - c), (x0, z0 + c), (x0 + c, z0), (x1 - c, z0), (x1, z0 + c), (x1, z1 - c), (x1 - c, z1), (x0 + c, z1)]


# ---- tower, cab band, roof slab, lamp base
o_lo = octa(0.56, 10.56, -10.58, -0.58, 2.0)
o_cab = octa(1.71, 9.41, -9.43, -1.73, 1.54)
o_top = octa(0.97, 10.15, -10.17, -0.99, 1.84)
tower = B.prism_y("tower", o_lo, 0.0, 6.63)
cab = B.loft_y("cab", o_lo, 6.63, o_cab, 8.76)
slab = B.loft_y("slab", o_cab, 8.76, o_top, 10.50)
B.cut(slab, B.prism_y("roof_field", offset(o_top, -0.42), 10.42, 10.6))
B.prism_y("cornice", offset(o_lo, 0.08), 6.55, 6.71)
B.prism_y("fascia", offset(o_top, 0.04), 10.30, 10.52)
B.loft_y("lamp_base", [(6.01, -8.49), (8.01, -8.49), (8.01, -6.49), (6.01, -6.49)], 10.42,
         [(6.34, -8.17), (7.68, -8.17), (7.68, -6.82), (6.34, -6.82)], 11.36)


# ---- quonset huts: outer wall to 1.88, smooth quarter arch to the 4.00 m top
def arch(outer, inner, sgn, k=16, off=0.0, kk=0.40):
    """(s, y) profile; s runs across the hut, sgn = direction from outer toward inner."""
    r_s, r_y = 2.89, 2.12
    P0 = np.array([outer, 1.88])
    P1 = np.array([outer, 1.88 + kk * r_y])
    P2 = np.array([outer + sgn * (r_s - kk * r_s), 4.0])
    P3 = np.array([outer + sgn * r_s, 4.0])
    pts = []
    for i in range(k + 1):
        t = i / k
        p = (1 - t) ** 3 * P0 + 3 * (1 - t) ** 2 * t * P1 + 3 * (1 - t) * t * t * P2 + t ** 3 * P3
        if off:
            dp = 3 * (1 - t) ** 2 * (P1 - P0) + 6 * (1 - t) * t * (P2 - P1) + 3 * t * t * (P3 - P2)
            nrm = np.array([-dp[1], dp[0]]) * sgn
            nrm = nrm / np.linalg.norm(nrm)
            if nrm[1] < 0:
                nrm = -nrm
            p = p + nrm * off
        pts.append((float(p[0]), float(p[1])))
    return pts


def hut_profile(outer, inner, sgn):
    return [(inner, 0.0), (outer, 0.0)] + arch(outer, inner, sgn) + [(inner, 4.0)]


def rib_profile(outer, inner, sgn, proud=0.07):
    a = arch(outer, inner, sgn, off=proud)
    b = arch(outer, inner, sgn)
    a = [(outer - sgn * proud, 1.80)] + a + [(inner, 4.0 + proud)]
    return a + [(inner, 4.0)] + b[::-1] + [(outer, 1.80)]


# hut A runs along x; its profile is (z, y), outer side z -8.01, yard side z -3.19
hutA = B.prism_x("hutA", hut_profile(-8.01, -3.19, 1), -7.27, 0.56)
# hut B runs along z; profile (x, y), outer side x 8.01, yard side x 3.20
hutB = B.prism_z("hutB", hut_profile(8.01, 3.20, -1), -0.58, 7.27)
for k, x in enumerate((-7.27, -4.70, -2.10)):
    B.prism_x(f"ribA{k}@avg", rib_profile(-8.01, -3.19, 1), x, x + 0.16)
for k, z in enumerate((1.90, 4.50, 7.11)):
    B.prism_z(f"ribB{k}@avg", rib_profile(8.01, 3.20, -1), z, z + 0.16)

# ---- yard wall (two pieces) with a coping
w1 = [(-7.18, -3.21), (-7.18, 2.16), (-5.16, 4.18), (-4.86, 3.93), (-6.75, 2.02), (-6.75, -3.21)]
w2 = [(-4.21, 5.15), (-2.19, 7.17), (3.32, 7.17), (3.32, 6.74), (-2.05, 6.74), (-3.96, 4.85)]
B.prism_y("wall1", w1, 0.0, 0.92)
B.prism_y("wall2", w2, 0.0, 0.92)
B.prism_y("coping1", [(-7.22, -3.19), (-7.22, 2.18), (-5.17, 4.24), (-4.80, 3.93), (-6.71, 2.00), (-6.71, -3.19)], 0.92, 1.0)
B.prism_y("coping2", [(-4.27, 5.15), (-2.21, 7.21), (3.30, 7.21), (3.30, 6.70), (-2.03, 6.70), (-3.94, 4.79)], 0.92, 1.0)


# ---- antenna masts (true cones)
def circle(cx, cz, r, n=20):
    return [(cx + r * math.cos(2 * math.pi * i / n), cz + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


B.loft_y("mast0", circle(3.97, 5.81, 0.15), 4.0, circle(3.97, 5.81, 0.025), 16.30)
B.loft_y("mast1", circle(3.97, 4.52, 0.13), 4.0, circle(3.97, 4.52, 0.025), 8.48)
B.prism_y("mast_foot", circle(3.97, 5.81, 0.24), 3.98, 4.12)

# ---- windows and doors
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    x, y, z = o["center"]
    if (abs(x - 0.56) < 0.05 and -8.01 < z < -3.19 and y < 4.0) or (abs(z + 0.58) < 0.05 and 3.2 < x < 8.01 and y < 4.0):
        continue  # vents painted on the tower behind a hut's roof
    if y > 6.6:
        tgt = cab if y < 8.76 else slab
    elif 0.5 < x < 10.6 and -10.6 < z < -0.55 and not (x < 3.3 and z > -3.2):
        tgt = tower
    elif z < -3.1 and x < 0.6:
        tgt = hutA
    else:
        tgt = hutB
    B.recess(tgt, o, 0.15)
    if o["h"] > 2.0 and (o["normal"][2] > 0.9 and x < 0.6 or o["normal"][0] < -0.9 and x > 3.0):  # yard-side windows
        B.sill(f"sill{k}", o, proud=0.1, thick=0.07, overhang=0.06)

print(B.dump())
