#!/usr/bin/env python3
"""CAD rebuild of the transformer station (appearance transformerstation), in the original's frame.

    D=~/craft/solid/mc2/buildings/transformerstation
    python3 -I tools/art/cad_building.py openings transformerstation > $D/openings.json
    python3 -I tools/cad/transformerstation_cad.py > $D/transformerstation.json
    solidcraft-cli run $D/transformerstation.json --out $D/transformerstation.obj
    python3 -I tools/art/cad_building.py bake transformerstation $D/transformerstation.obj --texel 0.015

Measured from game/assets/objects/transformerstation.glb (one mesh, faces listed with their UVs; painted rectangles
placed with `cad_building.py decal transformerstation 0 u0 v0 u1 v1`): a concrete plinth x -4.07..12.55,
z -12.56..4.01, 2.59 m high, with a ramp (x 10.23..12.55) falling from z -4.24 to the ground at z 4.01; two switch
cabinets 3.75 x 11.84 m (x -1.97..1.78 and 4.33..8.09, z -10.16..1.68) up to 7.50 m, fans painted on their ends;
two louvred cooler units on each (2.16 x 4.08 m, 7.52 -> 8.96 m); a 1.98 m railing card round the plinth top,
down the ramp's outer side and along its inner edge (x 9.96). Relief: the railing is real (handrail, bottom rail,
posts, balusters at 0.22 m) in one flat colour, since the original is an alpha card; the cabinets' painted doors are
3 cm plates, their dark foot (to 3.45 m) a 12 cm toe-kick, their roofs a 6 cm coping; the coolers' louvres are 12 cm
recesses with four raked slats each, and the units chamfered on low feet; the plinth's dark top band a coping
6 cm proud; the ramp carries anti-slip ribs.
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, box_edges  # noqa: E402

B = Builder()
PX0, PX1, PZ0, PZ1, PH = -4.07, 12.55, -12.56, 4.01, 2.59
RX0, RZ0 = 10.23, -4.24          # ramp: x 10.23..12.55, top at z -4.24, foot at z 4.01
SLOPE = PH / (PZ1 - RZ0)

# ---- plinth, ramp and coping
B.prism_y("plinth", [(PX0, PZ0), (PX1, PZ0), (PX1, RZ0), (RX0, RZ0), (RX0, PZ1), (PX0, PZ1)], 0.0, PH)
B.prism_x("ramp", [(RZ0, 0.0), (PZ1, 0.0), (RZ0, PH)], RX0, PX1)
C, CY = 0.06, 2.39
for k, (lo, hi) in enumerate((((PX0 - C, CY, PZ0 - C), (PX1 + C, PH, PZ0)),
                              ((PX0 - C, CY, PZ0), (PX0, PH, PZ1 + C)),
                              ((PX0, CY, PZ1), (RX0 + C, PH, PZ1 + C)),
                              ((PX1, CY, PZ0), (PX1 + C, PH, RZ0)),
                              ((RX0, CY, RZ0), (RX0 + C, PH, PZ1)))):
    B.box(f"coping{k}", lo, hi)
# anti-slip ribs across the ramp, lying on the slope
t = np.array([0.0, -PH, PZ1 - RZ0]) / math.hypot(PH, PZ1 - RZ0)
n = np.array([0.0, (PZ1 - RZ0), PH]) / math.hypot(PH, PZ1 - RZ0)
xa, xb = RX0 + 0.12, PX1 - 0.12
for k in range(13):
    s = 0.45 + k * 0.6
    c = np.array([(xa + xb) / 2, PH, RZ0]) + t * s + n * 0.02
    B.obox(f"rib{k}@avg", c, np.array([1.0, 0, 0]), np.cross(n, [1.0, 0, 0]), n, (xb - xa, 0.08, 0.04))

# ---- cabinets: toe-kick, body, coping, door plates
KY, K = 3.45, 0.12
CZ0, CZ1, CY1 = -10.16, 1.68, 7.50
DOORS = [(-9.34, 0.70), (-8.30, 0.77), (-6.61, 1.81), (-4.96, 0.77), (-3.58, 0.77), (-1.95, 1.84), (-0.34, 0.77), (0.78, 0.73)]
for ci, (x0, x1, dy, dh) in enumerate(((-1.97, 1.78, 5.37, 3.39), (4.33, 8.09, 5.34, 3.49))):
    B.box(f"kick{ci}", (x0 + K, PH, CZ0 + K), (x1 - K, KY, CZ1 - K))
    B.box(f"cab{ci}", (x0, KY, CZ0), (x1, CY1, CZ1))
    B.box(f"cabtop{ci}", (x0 - 0.04, CY1, CZ0 - 0.04), (x1 + 0.04, CY1 + 0.06, CZ1 + 0.04), chamfer=0.03)
    for side, xs in ((-1, x0), (1, x1)):
        for k, (zc, w) in enumerate(DOORS):
            xa_, xb_ = (xs - 0.03, xs + 0.005) if side < 0 else (xs - 0.005, xs + 0.03)
            B.box(f"door{ci}_{side}_{k}", (xa_, dy - dh / 2, zc - w / 2), (xb_, dy + dh / 2, zc + w / 2))

# ---- cooler units with louvres
UY0, UY1 = 7.52, 8.96
LZ = (-8.12, -6.21, -2.29, -0.39)
for ui, (ux0, ux1) in enumerate(((-1.17, 0.99), (5.13, 7.29))):
    for uj, (uz0, uz1) in enumerate(((-9.19, -5.11), (-3.37, 0.71))):
        nm = f"unit{ui}{uj}"
        B.box(f"foot{ui}{uj}", (ux0 + 0.08, CY1 + 0.06, uz0 + 0.08), (ux1 - 0.08, UY0 + 0.02, uz1 - 0.08))
        B.box(nm, (ux0, UY0, uz0), (ux1, UY1, uz1), chamfer=0.06)
        for side, xs in ((-1, ux0), (1, ux1)):
            nn = np.array([float(side), 0, 0])
            tt = np.array([0, 0, -float(side)])
            for zc in LZ:
                if not (uz0 < zc < uz1):
                    continue
                o = {"center": [xs, 8.26, zc], "normal": nn.tolist(), "t": tt.tolist(), "b": [0, 1.0, 0], "w": 1.7, "h": 1.1}
                B.recess(nm, o, 0.12)
                # four raked slats, falling outward
                ang = math.radians(35)
                bb = np.array([0, math.cos(ang), 0]) + nn * math.sin(ang) * -1
                bb /= np.linalg.norm(bb)
                n2 = np.cross(tt, bb)
                for s in range(4):
                    y = 8.26 - 0.55 + 0.1375 + s * 0.275
                    c = np.array([xs - side * 0.07, y, zc])
                    B.obox(f"slat{ui}{uj}_{side + 1}_{LZ.index(zc)}_{s}@6a6c6e", c, tt, bb, n2,
                           (1.68, 0.2, 0.02))

# ---- railings: handrail, bottom rail, posts and balusters (one flat colour)
RL = "@8e9296"
YB0, YB1, YT0, YT1 = 2.83, 2.97, 4.45, 4.57   # bottom rail, handrail
RW = 0.08
RXW, RXE, RZS, RZN, RXI = -3.76, 12.27, -12.24, 3.69, 9.96
runs = [((RXW, RZS), (RXE, RZS)), ((RXW, RZS), (RXW, RZN)), ((RXW, RZN), (RXI, RZN)), ((RXI, RZ0), (RXI, RZN)),
        ((RXE, RZS), (RXE, RZ0))]
pk = 0
bk = 0
seen = set()
for k, ((ax, az), (bx, bz)) in enumerate(runs):
    lo_x, hi_x, lo_z, hi_z = min(ax, bx), max(ax, bx), min(az, bz), max(az, bz)
    h = RW / 2
    for nm, (y0, y1) in (("hand", (YT0, YT1)), ("bot", (YB0, YB1))):
        B.box(f"{nm}{k}{RL}", (lo_x - h, y0, lo_z - h), (hi_x + h, y1, hi_z + h))
    L = max(hi_x - lo_x, hi_z - lo_z)
    npost = max(1, round(L / 2.7))
    for i in range(npost + 1):
        f = i / npost
        x, z = ax + (bx - ax) * f, az + (bz - az) * f
        if (round(x, 2), round(z, 2)) in seen:
            continue
        seen.add((round(x, 2), round(z, 2)))
        B.box(f"post{pk}{RL}", (x - 0.05, PH, z - 0.05), (x + 0.05, YT0, z + 0.05))
        pk += 1
    nb = round(L / 0.22)
    for i in range(1, nb):
        f = i / nb
        x, z = ax + (bx - ax) * f, az + (bz - az) * f
        B.box(f"bal{bk}{RL}", (x - 0.024, YB1, z - 0.024), (x + 0.024, YT0, z + 0.024))
        bk += 1
# the sloped railing down the ramp's outer side
d = np.array([0.0, -(PH - 0.10), (RZN - RZ0)])
L = float(np.linalg.norm(d))
tt = d / L
nn = np.array([1.0, 0, 0])
bb = np.cross(nn, tt)
if bb[1] < 0:
    bb = -bb
for nm, off in (("rhand", (YT0 + YT1) / 2 - PH), ("rbot", (YB0 + YB1) / 2 - PH)):
    c = np.array([RXE, PH + off, RZ0]) + d / 2
    B.obox(f"{nm}{RL}", c, tt, bb, np.cross(tt, bb), (L + 0.03, 0.12, RW))
nb = round((RZN - RZ0) / 0.22)
for i in range(1, nb + 1):
    f = i / nb
    z = RZ0 + (RZN - RZ0) * f
    yg = PH - (z - RZ0) * SLOPE
    if i % 12 == 0 or i == nb:
        B.box(f"rpost{i}{RL}", (RXE - 0.05, yg - 0.02, z - 0.05), (RXE + 0.05, yg + (YT0 - PH), z + 0.05))
    else:
        B.box(f"rbal{i}{RL}", (RXE - 0.024, yg + (YB1 - PH), z - 0.024), (RXE + 0.024, yg + (YT0 - PH), z + 0.024))

print(B.dump())
