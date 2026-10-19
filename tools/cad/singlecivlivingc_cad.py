#!/usr/bin/env python3
"""CAD rebuild of the small civilian shack (appearance singlecivlivingc), in the original's frame.

    D=~/craft/solid/mc2/buildings/singlecivlivingc
    python3 -I tools/art/cad_building.py openings singlecivlivingc > $D/openings.json
    python3 -I tools/cad/singlecivlivingc_cad.py $D > $D/singlecivlivingc.json
    solidcraft-cli run $D/singlecivlivingc.json --out $D/singlecivlivingc.obj
    python3 -I tools/art/cad_building.py bake singlecivlivingc $D/singlecivlivingc.obj

Measured from game/assets/objects/singlecivlivingc.glb (vertices listed by height): one prism along z
(-2.97..2.35) with a tall +x wall (3.35 m), a three-facet roof (3.35 -> 3.19 at x 0.25 -> 2.45 at x -1.07 -> 1.3 at
x -1.81) that comes down the low -x wall in the same sheeting and overhangs the door gable to z 2.71; a flue leaves
the +x wall at 2.59 m and climbs to a stack (2.4..2.67) with a pyramid cap to 4.45 m.
The texture's lines were mapped back to 3D (texel -> triangle -> barycentric): the roof's painted sheet laps sit at
x 1.314 / 0.704 / 0.25 / -0.433 / -1.07 / -1.288 / -1.572 / -1.81 and y 0.665 / 0.46 down the low wall, the
+x wall's vertical board seams at z = 2.379 - 10.09 v for the painted v rows. Relief: each roof sheet is a real
course, 5 mm at its top and 25 mm at its lap; the +x wall seams are 6 cm battens; a 3 cm proud skirt rings the
base (not across the door); windows are 12 cm recesses with sills (the roof-slope window too), the door a 8 cm
recess with a concrete step; the roof edge is a 6 cm sheet that overhangs the back gable by 10 cm and the +x wall
by 10 cm; corner boards on the +x corners; the flue and stack are real boxes under a lipped pyramid cap.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
ZB, ZF, ZOF = -2.97, 2.35, 2.71   # back gable, front (door) gable, front roof overhang
ZOB = ZB - 0.10
B = Builder()

# ---- shell
prof = [(-1.81, 0.0), (1.84, 0.0), (1.84, 3.35), (0.25, 3.19), (-1.07, 2.45), (-1.81, 1.3)]
shell = B.prism_z("shell", prof, ZB, ZF)

# the roof line, from the +x eave (overhanging 10 cm) down to the skirt on the -x wall
facets = [((1.94, 3.36), (0.25, 3.19)), ((0.25, 3.19), (-1.07, 2.45)), ((-1.07, 2.45), (-1.81, 1.3)), ((-1.81, 1.3), (-1.81, 0.46))]


def nrm(p, q):
    ex, ey = q[0] - p[0], q[1] - p[1]
    L = math.hypot(ex, ey)
    n = np.array([-ey, ex]) / L   # left of p->q; the profile runs clockwise here, so left is outward
    return n if (np.array(p) - [0.0, 1.5]) @ n > 0 else -n


def on(seg, x=None, y=None):
    (px, py), (qx, qy) = seg
    if x is not None:
        return (x, py + (qy - py) * (x - px) / (qx - px))
    return (px + (qx - px) * (y - py) / (qy - py), y)


laps = [  # course boundaries per facet, top to bottom (painted lap lines)
    [facets[0][0], on(facets[0], x=1.314), on(facets[0], x=0.704), facets[0][1]],
    [facets[1][0], on(facets[1], x=-0.433), facets[1][1]],
    [facets[2][0], on(facets[2], x=-1.288), on(facets[2], x=-1.572), facets[2][1]],
    [facets[3][0], (-1.81, 0.665), facets[3][1]],
]

openings = json.load(open(D / "openings.json"))["openings"]
win_roof = [o for o in openings if 0.3 < o["normal"][1] < 0.9][0]
wz = win_roof["center"][2]
WZ0, WZ1 = wz - win_roof["w"] / 2 - 0.16, wz + win_roof["w"] / 2 + 0.16

# 6 cm roof sheet under the line (the edge seen at the overhangs), the steep facet split round its window
for k, (p, q) in enumerate(facets[:3]):
    n = nrm(p, q)
    quad = [p, q, tuple(np.array(q) - n * 0.06), tuple(np.array(p) - n * 0.06)]
    sheet = B.prism_z(f"sheet{k}", quad, ZOB, ZOF)
    if k == 2:
        B.recess(sheet, win_roof, 0.14)
B.recess(shell, win_roof, 0.14)

# the sheet courses: wedges 5 mm at the top, 25 mm at the lap
for k, pts in enumerate(laps):
    zr = (ZOB, ZOF) if k < 3 else (ZB, ZF)
    for j in range(len(pts) - 1):
        p, q = np.array(pts[j]), np.array(pts[j + 1])
        n = nrm(tuple(p), tuple(q))
        poly = [tuple(p), tuple(q), tuple(q + n * 0.025), tuple(p + n * 0.005)]
        # the steep facet's courses (and the wall's top one) stop at the roof window
        lo_s = min(p[1], q[1])
        hits_win = k == 2 and lo_s < win_roof["center"][1] + 0.6
        spans = [(zr[0], WZ0), (WZ1, zr[1])] if hits_win else [zr]
        for s, (za, zb) in enumerate(spans):
            B.prism_z(f"course{k}{j}{s}", poly, za, zb)

# ---- +x wall: battens on the painted board seams, round the window and the flue
win_x = [o for o in openings if o["normal"][0] > 0.9][0]
seam_v = [0.047, 0.096, 0.146, 0.193, 0.236, 0.279, 0.328, 0.375, 0.422, 0.469]
wy0 = win_x["center"][1] - win_x["h"] / 2 - 0.2
wy1 = win_x["center"][1] + win_x["h"] / 2 + 0.2
wzx0 = win_x["center"][2] - win_x["w"] / 2 - 0.2
wzx1 = win_x["center"][2] + win_x["w"] / 2 + 0.2
for k, v in enumerate(seam_v):
    z = 2.379 - 10.09 * v
    ys = [(0.46, 3.33)]
    if wzx0 < z < wzx1:
        ys = [(0.46, wy0), (wy1, 3.33)]
    if -0.48 < z < 0.0:
        ys = [(0.46, 2.5)]
    for j, (ya, yb) in enumerate(ys):
        B.box(f"batten{k}{j}", (1.84, ya, z - 0.03), (1.865, yb, z + 0.03))
for k, z in enumerate((ZB, ZF)):  # corner boards
    za, zb = (z, z + 0.1) if k == 0 else (z - 0.1, z)
    B.box(f"corner{k}", (1.74, 0.46, za - (0.03 if k == 0 else 0)), (1.87, 3.33, zb + (0.03 if k == 1 else 0)))

# ---- skirt, 3 cm proud, 0.46 m high (not across the door)
door_x0, door_x1 = 0.55 - 0.74, 0.55 + 0.74
B.box("skirt_px", (1.84, 0.0, ZB - 0.03), (1.87, 0.46, ZF + 0.03))
B.box("skirt_nx", (-1.84, 0.0, ZB - 0.03), (-1.81, 0.46, ZF + 0.03))
B.box("skirt_b", (-1.84, 0.0, ZB - 0.03), (1.87, 0.46, ZB))
B.box("skirt_f0", (-1.84, 0.0, ZF), (door_x0, 0.46, ZF + 0.03))
B.box("skirt_f1", (door_x1, 0.0, ZF), (1.87, 0.46, ZF + 0.03))

# ---- windows and door
for k, o in enumerate(openings):
    if o is win_roof:
        B.sill(f"sill{k}", o, proud=0.10, thick=0.06, overhang=0.06)
        continue
    if abs(o["normal"][2]) > 0.9 and o["center"][2] > 0:
        continue  # the door's own window: the door recess carries it
    B.recess(shell, o, 0.12)
    B.sill(f"sill{k}", o, proud=0.10, thick=0.06, overhang=0.06)
    if o is win_x:
        B.sill(f"hood{k}", o, proud=0.12, thick=0.05, overhang=0.08, top=True)
door = {"center": [0.55, 1.125, ZF], "normal": [0, 0, 1], "t": [1, 0, 0], "b": [0, 1, 0], "w": 1.18, "h": 2.25}
B.recess(shell, door, 0.08)
B.box("step@8f8b84", (0.55 - 0.7, 0.0, ZF), (0.55 + 0.7, 0.15, ZF + 0.55))

# ---- flue, stack and cap
B.prism_z("flue", [(1.83, 2.59), (2.67, 3.2), (2.67, 4.03), (2.4, 4.03), (2.4, 3.44), (1.83, 3.07)], -0.38, -0.1)
B.box("caplip", (2.15, 4.03, -0.63), (2.92, 4.08, 0.15))
B.loft_y("cap", [(2.15, -0.63), (2.92, -0.63), (2.92, 0.15), (2.15, 0.15)], 4.08,
         [(2.52, -0.25), (2.54, -0.25), (2.54, -0.23), (2.52, -0.23)], 4.45)

print(B.dump())
