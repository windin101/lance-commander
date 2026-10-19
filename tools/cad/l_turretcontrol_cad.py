#!/usr/bin/env python3
"""CAD rebuild of the green turret control centre (appearance l_turretcontrol), in the original's frame.

    D=~/craft/solid/mc2/buildings/l_turretcontrol
    python3 -I tools/art/cad_building.py openings l_turretcontrol > $D/openings.json
    python3 -I tools/cad/l_turretcontrol_cad.py $D > $D/l_turretcontrol.json
    solidcraft-cli run $D/l_turretcontrol.json --out $D/l_turretcontrol.obj
    python3 -I tools/art/cad_building.py bake l_turretcontrol $D/l_turretcontrol.obj --keep LOS_ant1 LOS_ant2 LOS_ant3

Measured from game/assets/objects/l_turretcontrol.glb (faces grouped by plane): a long block (x -6.91..3.09)
whose front half (z 3.82..10.01) rises to 5.89 m with a two-facet nose and whose rear half (to z -8.10) is 4.01 m
with a two-facet tail notched by the entrance (x -3.58..-0.25); a cross block (x -11.88..-0.23, z -5.20..-1.17,
5.87 m) with a two-facet west end and a bevelled east end; a low transverse block (z 2.73..3.82) with sloped ends;
a hexagonal tower (centre (8.66, -4.57)): a flared skirt to 3.24 m, a tapering shaft to 11.50 m and a bevelled
window cap to 13.75 m carrying the radar pedestal, with a connector to the long block; an L-shaped low wall
(1.3 m) with a gate gap. The tower stays hexagonal: its riveted panel corners and one window per face are the
design (issue I77's exception). The radar bar and the two masts are kept verbatim. Relief: every cut-out window
is a recess (15 cm, sills under the vertical ones), the roofs' painted dark fields are 8 cm recesses inside their
rims, ledges ring the tower at the skirt top and the cap.
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
        B.obox(f"{name}{i}", c, t, bv, n, (L + 2 * proud * 0.6, y1 - y0, proud + 0.02))


def field(target, x0, x1, z0, z1, y, rim, depth=0.08):
    B.cut(target, B.box(f"f_{target}", (x0 + rim, y - depth, z0 + rim), (x1 - rim, y + 0.2, z1 - rim)))


# ---- long block: tall front half, low rear half with the entrance notch
a1 = B.prism_x("front", [(3.82, 0.0), (8.68, 0.0), (10.01, 2.44), (7.42, 5.89), (3.82, 5.89)], -6.91, 3.09)
a2 = B.prism_x("rear", [(-6.93, 0.0), (3.82, 0.0), (3.82, 4.01), (-6.07, 4.01), (-8.10, 1.42)], -6.91, 3.09)
B.cut(a2, B.prism_x("notch", [(-8.4, -0.1), (-6.95, -0.1), (-6.07, 4.01), (-6.07, 4.3), (-8.4, 4.3)], -3.58, -0.25))
field(a1, -6.91, 3.09, 3.82, 7.42, 5.89, 0.45)
field(a2, -6.91, 3.09, -6.07, 2.73, 4.01, 0.45)
# cross block and the low transverse block
cb = B.prism_z("cross", [(-10.72, 0.0), (-0.23, 0.0), (-0.23, 3.98), (-1.23, 5.87), (-9.16, 5.87), (-11.88, 2.39)], -5.20, -1.17)
field(cb, -9.16, -1.23, -5.20, -1.17, 5.87, 0.4)
B.prism_z("band", [(-10.57, 0.0), (6.75, 0.0), (4.36, 4.01), (-8.19, 4.01)], 2.73, 3.82)

# ---- hexagonal tower
CX, CZ = 8.66, -4.57


def hexa(ap):
    r = ap / math.cos(math.pi / 6)
    return [(CX + r * math.cos(math.radians(30 + 60 * k)), CZ + r * math.sin(math.radians(30 + 60 * k))) for k in range(6)]


B.loft_y("skirt", hexa(3.83), 0.0, hexa(2.95), 3.24)
B.loft_y("shaft", hexa(2.95), 3.24, hexa(2.55), 11.50)
cap = B.loft_y("cap", hexa(2.55), 11.50, hexa(2.01), 13.75)
B.cut(cap, B.prism_y("cap_field", inset(hexa(2.01), 0.3), 13.67, 13.9))
ring("skirt_ledge", hexa(2.95), 3.14, 3.34, 0.10)
ring("cap_ledge", hexa(2.555), 11.40, 11.60, 0.10)
B.loft_y("connector", [(3.01, -6.78), (5.71, -6.78), (5.71, -2.36), (3.01, -2.36)], 0.0,
         [(3.01, -6.27), (5.71, -6.27), (5.71, -2.86), (3.01, -2.86)], 3.24)
B.obox("pedestal", (8.66, 14.56, -4.71), (0.88, 0.0, -0.48), (0.0, 1.0, 0.0), np.cross((0.88, 0.0, -0.48), (0.0, 1.0, 0.0)), (1.1, 1.71, 1.0))

# ---- windows
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    x, y, z = o["center"]
    if y > 11:
        tgt = cap
    elif x < -0.2 and -5.25 < z < -1.1:
        tgt = cb
    elif z > 3.8:
        tgt = a1
    else:
        tgt = a2
    B.recess(tgt, o, 0.15)
    if abs(o["normal"][1]) < 0.1 and o["h"] > o["w"]:
        B.sill(f"sill{k}", o, proud=0.1, thick=0.07, overhang=0.06)

# ---- low walls with the gate gap
B.prism_y("wall0", [(11.43, -3.37), (11.90, -3.37), (11.90, 3.55), (10.40, 5.40), (10.06, 5.11), (11.43, 3.41)], 0.0, 1.30)
B.prism_y("wall1", [(8.98, 6.33), (9.29, 6.67), (7.41, 8.17), (2.88, 8.17), (2.88, 7.70), (7.27, 7.70)], 0.0, 1.30)

print(B.dump())
