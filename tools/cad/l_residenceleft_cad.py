#!/usr/bin/env python3
"""CAD rebuild of the woodland residence wing (appearance l_residenceleft), in the original's frame; with
--right it builds l_residenceright, the same building mirrored in z (z -> -0.76 - z, measured).

    D=~/craft/solid/mc2/buildings/l_residenceleft
    python3 -I tools/art/cad_building.py openings l_residenceleft > $D/openings.json
    python3 -I tools/art/cad_building.py decal l_residenceleft 1 0.26 0.04 0.73 0.72 > $D/decal_door.json
    python3 -I tools/cad/l_residenceleft_cad.py $D > $D/l_residenceleft.json
    solidcraft-cli run $D/l_residenceleft.json --out $D/l_residenceleft.obj
    python3 -I tools/art/cad_building.py bake l_residenceleft $D/l_residenceleft.obj
    (l_residenceright: the same with D=.../l_residenceright, the app name changed and --right after $D)

Measured from game/assets/objects/l_residenceleft.glb (vertices listed by height): a wide low block whose
footprint (x -5.66..10.99, z -12.16..16.90) batters in on its west and north (-z) sides to the 8.71 m roof; a
dark rail ring around that roof overhangs it (outer x -5.87..12.64, z -12.50..18.27/18.63, inner x -4.82..11.59,
z -11.20..17.40) to 10.53 m over a gravel roof at 9.64 m; a tall block (x -8.63..10.79, z -1.35..16.31) to 12.49 m
standing out of its west side, with a plinth to 0.70 m, bevelled bands 0.70..2.27 m and 8.73..11.79 m and a
parapet band to the gravel roof; on it a slightly tapering chimney (x -1.64..5.19, z 2.49..8.63) to 19.88 m,
a flared cap to 21.50 m, a concave hip roof (smooth Catmull-Rom curve through the original's three facets) to
23.52 m and a low glazed pyramid to 24.25 m. Relief: the west front's cut-out windows are 15 cm recesses with
sills under the lower row, the ceremonial door (texture decal) a 15 cm recess, both gravel roofs 8 cm fields
inside their rims, the rail's top edges chamfered, a ledge under the chimney cap.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
RIGHT = "--right" in sys.argv
B = Builder()


def Z(z):
    return -0.76 - z if RIGHT else z


def P(poly):  # a plan polygon (x, z), mirrored and reversed so its winding is kept
    q = [(x, Z(z)) for x, z in poly]
    return q[::-1] if RIGHT else q


def rect(x0, x1, z0, z1):
    return P([(x0, z0), (x1, z0), (x1, z1), (x0, z1)])


def box(name, lo, hi, **kw):
    z0, z1 = sorted((Z(lo[2]), Z(hi[2])))
    return B.box(name, (lo[0], lo[1], z0), (hi[0], hi[1], z1), **kw)


# ---- low block (battered west and north sides), rail ring with the gravel roof inside
low = B.loft_y("low", rect(-5.66, 10.99, -12.16, 16.90), 0.0, rect(-4.25, 11.02, -10.52, 16.93), 8.71)
outer = P([(-5.87, -12.50), (12.64, -12.47), (12.64, 18.63), (-5.87, 18.27)])
inner = P([(-4.82, -11.20), (11.59, -11.20), (11.59, 17.36), (-4.82, 17.40)])
rail = B.prism_y("rail", outer, 8.71, 10.53)
B.cut(rail, B.prism_y("rail_in", inner, 9.64, 10.8))
B.cut(rail, B.prism_y("low_field", P([(-4.42, -10.80), (11.19, -10.80), (11.19, 16.96), (-4.42, 17.00)]), 9.56, 9.8))

# ---- tall west block: plinth, bevelled bands, parapet band, gravel roof
o0, o1 = (-8.63, 10.79, -1.35, 16.31), (-8.57, 10.73, -1.29, 16.25)
i0 = (-8.20, 10.36, -0.92, 15.88)
box("plinth", (o0[0], 0.0, o0[2]), (o0[1], 0.70, o0[3]))
B.loft_y("bevel_lo", rect(*i0), 0.70, rect(*o1), 2.27)
wall = box("wall", (o1[0], 2.27, o1[2]), (o1[1], 8.73, o1[3]))
B.loft_y("bevel_hi", rect(*o1), 8.73, rect(*i0), 11.79)
par = box("parapet", (o0[0], 11.79, o0[2]), (o0[1], 12.49, o0[3]))
B.cut(par, box("top_field", (-8.13, 12.41, -0.85), (10.29, 12.7, 15.81)))

# ---- chimney, flared cap, curved roof, glazed pyramid
B.loft_y("chimney", rect(-1.64, 5.19, 2.49, 8.63), 11.42, rect(-1.47, 5.02, 2.66, 8.46), 19.88)
B.prism_y("cap_ledge", rect(-1.59, 5.14, 2.54, 8.58), 19.70, 19.90)
B.loft_y("cap", rect(-1.47, 5.02, 2.66, 8.46), 19.88, rect(-2.69, 6.23, 1.44, 9.67), 21.50)
R = np.array([(21.50, -2.69, 6.23, 1.44, 9.67), (21.90, -1.72, 5.26, 2.41, 8.70), (22.63, -1.07, 4.62, 3.06, 8.06),
              (23.52, -0.83, 4.38, 3.30, 7.81)])
Q = np.vstack([2 * R[0] - R[1], R, 2 * R[-1] - R[-2]])
rings = [R[0]]
for i in range(1, len(R)):
    p0, p1, p2, p3 = Q[i - 1], Q[i], Q[i + 1], Q[i + 2]
    for k in (1, 2, 3):
        t = k / 3
        rings.append(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
for k in range(len(rings) - 1):
    a, b = rings[k], rings[k + 1]
    B.loft_y(f"roof{k}", rect(*a[1:]), a[0], rect(*b[1:]), b[0])
B.loft_y("pyramid", rect(-0.83, 4.38, 3.30, 7.81), 23.52, rect(1.72, 1.82, 5.51, 5.61), 24.25)

# ---- door and windows on the west front
door = json.load(open(D / "decal_door.json"))["rects"][0]
dz = door["center"][2]
B.recess(wall, {"center": [-8.57, 5.25, dz], "normal": [-1.0, 0.0, 0.0], "t": [0.0, 0.0, 1.0 if RIGHT else -1.0],
                "b": [0.0, 1.0, 0.0], "w": door["w"], "h": 5.94}, 0.15)
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    B.recess(wall, o, 0.15)
    if o["center"][1] < 5.0:
        B.sill(f"sill{k}", o, proud=0.1, thick=0.07, overhang=0.06)

print(B.dump())
