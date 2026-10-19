#!/usr/bin/env python3
"""CAD rebuild of the grain store (appearance grainstorage), in the original's frame.

    D=~/craft/solid/mc2/buildings/grainstorage
    python3 -I tools/art/cad_building.py openings grainstorage > $D/openings.json
    python3 -I tools/art/cad_building.py decal grainstorage 0 .268 .862 .484 1.0 > $D/decal_door1.json
    python3 -I tools/art/cad_building.py decal grainstorage 0 .508 .862 .725 1.0 > $D/decal_door2.json
    python3 -I tools/cad/grainstorage_cad.py $D > $D/grainstorage.json
    solidcraft-cli run $D/grainstorage.json --out $D/grainstorage.obj
    python3 -I tools/art/cad_building.py bake grainstorage $D/grainstorage.obj

Measured from game/assets/objects/grainstorage.glb (node GrainStorage): a hall x -4.17..12.68, z -4.13..0.38,
whose mono-pitch roof falls from 15.16 m (front, z -4.13) to 12.17 m (back, z 4.13); above 10.21 m the hall
reaches back to z 4.13 over four touching hexagonal silos (corner radius 2.09 m, centres x -2.03, 2.16, 6.35,
10.54, z 2.19, 10.21 m tall). Relief: the two painted 4.8 x 4.2 m doors are 25 cm recesses (their louvre strips
cut 40 cm), under a hood; every cut-out vent band is a 15 cm recess with its painted mullions as bars and a drip
hood; the roof's seven painted sheet seams are standing ribs, with verge trims on both gables; the front's
three painted wall seams are battens; the painted bands under the eaves (front) and over the silos (back) are
ledges; the silos' painted panel joints are 12 cm hoops.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
X0, X1 = -4.17, 12.68
ZF, ZM, ZB = -4.13, 0.38, 4.13
YF, YB, YS = 15.16, 12.17, 10.21
B = Builder()

# ---- volumes
hall = B.prism_x("hall", [(ZF, 0.0), (ZM, 0.0), (ZM, YS), (ZB, YS), (ZB, YB), (ZF, YF)], X0, X1)
SR = 2.09
for k, cx in enumerate((-2.03, 2.16, 6.35, 10.54)):
    hexa = [(cx + SR * math.cos(a * math.pi / 3), 2.19 + SR * math.sin(a * math.pi / 3)) for a in range(6)]
    B.prism_y(f"silo{k}", hexa, 0.0, YS)
    hoop = [(cx + (SR + 0.06) * math.cos(a * math.pi / 3), 2.19 + (SR + 0.06) * math.sin(a * math.pi / 3)) for a in range(6)]
    for j, y in enumerate((2.07, 4.08, 6.12, 8.1)):
        B.prism_y(f"hoop{k}_{j}", hoop, y - 0.06, y + 0.06)

# ---- doors: 25 cm recess inside the painted frame, louvres 40 cm, hood over each
doors = []
for nm in ("door1", "door2"):
    for o in json.load(open(D / f"decal_{nm}.json"))["rects"]:
        o = dict(o, w=o["w"] - 0.3, h=o["h"] - 0.15)
        o["center"] = [o["center"][0], o["h"] / 2, o["center"][2]]
        B.recess(hall, o, 0.25)
        B.sill(f"hood_{nm}", o, proud=0.3, thick=0.1, overhang=0.15, top=True)
        doors.append(o)

# ---- vents
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    n, t, b = (np.array(o[q], float) for q in ("normal", "t", "b"))
    c = np.array(o["center"], float)
    if c[1] < 5:  # louvre strip in a door
        B.recess(hall, o, 0.40)
        continue
    depth = 0.15
    B.recess(hall, o, depth)
    B.sill(f"vhood{k}", o, proud=0.14, thick=0.06, overhang=0.06, top=True)
    B.sill(f"vsill{k}", o, proud=0.08, thick=0.05, overhang=0.04)
    bc = c - n * (depth / 2 + 0.02)
    cells = max(1, round(o["w"] / 1.19))
    for j in range(1, cells):
        B.obox(f"vbar{k}_{j}", bc + t * (j / cells - 0.5) * o["w"], t, b, n, (0.06, o["h"], depth - 0.04))
    if o["h"] > 0.65:
        B.obox(f"vbarh{k}", bc, t, b, n, (o["w"], 0.05, depth - 0.04))

# ---- roof: standing seams and verge trims
d = np.array([0.0, YB - YF, ZB - ZF])
L = float(np.linalg.norm(d))
d /= L
nrm = np.array([0.0, -d[2], d[1]]) * -1  # up the roof normal
nrm = nrm if nrm[1] > 0 else -nrm
mid = np.array([0.0, (YF + YB) / 2, (ZF + ZB) / 2])
for k, x in enumerate((-2.02, 0.07, 2.18, 4.29, 6.22, 8.35, 10.44)):
    B.obox(f"rib{k}@avg", mid + np.array([x, 0, 0]) + nrm * 0.03, (1, 0, 0), -d, nrm, (0.1, L - 0.2, 0.1))
for k, x in enumerate((X0 + 0.07, X1 - 0.07)):
    B.obox(f"verge{k}", mid + np.array([x, 0, 0]) + nrm * 0.04, (1, 0, 0), -d, nrm, (0.2, L + 0.1, 0.14))

# ---- wall battens (front) and ledges
for k, (x, y0) in enumerate(((9.43, 1.3), (4.11, 4.35), (-1.29, 4.35))):  # the first runs down to 1.3 m as painted
    B.box(f"batten{k}", (x - 0.05, y0, ZF - 0.04), (x + 0.05, 14.6, ZF + 0.01))
B.box("ledge_front", (X0, 14.8, ZF - 0.15), (X1, 15.14, ZF + 0.01))
B.box("ledge_back", (X0, 11.6, ZB - 0.01), (X1, 12.12, ZB + 0.15))
B.box("ledge_silos", (X0, YS - 0.01, ZB - 0.01), (X1, YS + 0.12, ZB + 0.08))

print(B.dump())
