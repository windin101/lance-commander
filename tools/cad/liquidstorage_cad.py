#!/usr/bin/env python3
"""CAD rebuild of the liquid storage tank (appearance liquidstorage), in the original's frame.

    D=~/craft/solid/mc2/buildings/liquidstorage
    python3 -I tools/art/cad_building.py decal liquidstorage 0 0.873 0.141 0.963 0.385 > $D/decal_towerwin.json
    python3 -I tools/cad/liquidstorage_cad.py $D > $D/liquidstorage.json
    solidcraft-cli run $D/liquidstorage.json --out $D/liquidstorage.obj
    python3 -I tools/art/cad_building.py bake liquidstorage $D/liquidstorage.obj

Measured from game/assets/objects/liquidstorage.glb: a decagonal tank (corners on radius 9.144 m, one on -z,
0.305 to 9.83 m) on a decagonal plinth (radius 10.058 at the ground, 9.906 at its top), a 0.76 m roof chamfer to
radius 8.382 at 10.592 m and a shallow cone to 11.354 m; a stair tower on +z (x +-1.143, z 8.0..9.525, to 9.906 m)
and a pointed pipe bridge from it to the roof centre (x +-1.905, z -1.905..10.287, 9.906 to 12.573 m, its end
sloping down over the tower). The original has no cut-outs. Relief: 10 cm corner stiffeners, bands on the
three painted panel joints (1.84, 5.17, 8.75 m) and at the eaves; the painted round cap at the cone's top is a real 0.4 m drum with
a hatch dome (the white disc); the stair tower's glazing is a 10 cm recess with a sill; the bridge's top
edges are chamfered.
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


def deca(r):
    return [(r * math.sin(math.radians(36 * k)), -r * math.cos(math.radians(36 * k))) for k in range(10)]


R_T, Y0, Y1 = 9.144, 0.305, 9.83
B.loft_y("plinth", deca(10.058), 0.0, deca(9.906), Y0)
tank = B.prism_y("tank", deca(R_T), Y0 - 0.01, Y1)
B.loft_y("eaves", deca(R_T), Y1, deca(8.382), 10.592)
B.loft_y("cone", deca(8.382), 10.592, deca(0.35), 11.33)

# panel stiffeners: corner ribs, a mid-height band and an eaves band on every face
up = np.array([0.0, 1.0, 0.0])
AP = R_T * math.cos(math.radians(18))   # apothem
SIDE = 2 * R_T * math.sin(math.radians(18))
for k in range(10):
    a = math.radians(36 * k)
    n = np.array([math.sin(a), 0.0, -math.cos(a)])
    t = np.cross(up, n)
    if k != 5:  # the corner on +z is inside the stair tower
        c = n * (R_T - 0.02) + up * (Y0 + Y1) / 2
        B.obox(f"rib{k}", c + n * 0.05, t, up, n, (0.26, Y1 - Y0, 0.14))
    am = a + math.radians(18)
    nm = np.array([math.sin(am), 0.0, -math.cos(am)])
    tm = np.cross(up, nm)
    for j, (yc, h) in enumerate(((1.84, 0.2), (5.17, 0.24), (8.75, 0.2), (9.68, 0.22))):  # on the painted joints
        B.obox(f"band{k}_{j}", nm * (AP + 0.04) + up * yc, tm, up, nm, (SIDE - 0.1, h, 0.1))

# the painted round cap: a drum with a hatch dome on top
B.c("solid.cylinder", radius=3500, height=450, base=[0, 0, 10950], axis=[0, 0, 1], body_name="cap", operation="new")
B.c("solid.cylinder", radius=1150, height=200, base=[0, 0, 11400], axis=[0, 0, 1], body_name="hatch", operation="new")
B.c("solid.chamfer", edges=[[1150, 0, 11600]], distance=120, body="hatch")

# stair tower and the pointed pipe bridge
tower = B.box("tower", (-1.143, 0.29, 8.001), (1.143, 9.906, 9.525))
bridge = B.prism_x("bridge", [(-1.905, 9.906), (10.287, 9.906), (8.001, 12.573), (-1.905, 12.573)], -1.905, 1.905)
for k, sgn in enumerate((1, -1)):  # the pointed end at -z
    w = B.prism_y(f"nose{k}", [(0.0, -1.905 - 0.01), (sgn * 1.905 + sgn * 0.05, -1.905 - 0.01),
                                (sgn * 1.905 + sgn * 0.05, -0.381)], 9.8, 12.7)
    B.cut(bridge, w)
B.c("solid.chamfer", edges=[[1905, -3000, 12573], [-1905, -3000, 12573]], distance=80, body=bridge)
for o in json.load(open(D / "decal_towerwin.json"))["rects"]:
    o = dict(o, w=1.9, h=o["h"] - 0.3)
    B.recess(tower, o, 0.10)
    B.sill("towersill", o, proud=0.08, thick=0.07, overhang=0.05)

print(B.dump())
