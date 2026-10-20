#!/usr/bin/env python3
"""CAD rebuild of the woodland residence core (appearance l_residencecore), in the original's frame.

    D=~/craft/solid/mc2/buildings/l_residencecore
    python3 -I tools/art/cad_building.py openings l_residencecore > $D/openings.json
    python3 -I tools/art/cad_building.py decal l_residencecore 1 0.26 0.04 0.73 0.72 > $D/decal_door.json
    python3 -I tools/cad/l_residencecore_cad.py $D > $D/l_residencecore.json
    solidcraft-cli run $D/l_residencecore.json --out $D/l_residencecore.obj
    python3 -I tools/art/cad_building.py bake l_residencecore $D/l_residencecore.obj

Measured from game/assets/objects/l_residencecore.glb (vertices listed by height): a plinth (x -12.60..10.30,
z -11.85..11.38, 0.57 m) under the walls (x -11.85..9.55, z -11.11..10.64) to 14.65 m, masonry below 8.85 m and
glazing above; a hipped roof whose eave (14.59 m) overhangs to the plinth's edge and whose six facets curve up
concave to a flat cap (x -5.76..3.99, z -5.55..5.08) at 20.07 m, rebuilt as a smooth curve (Catmull-Rom through
the original's rings, 3 segments a facet), so the painted roof bands stay where they were. On the west front a
door vestibule (x -13.51..-11.30, z -4.42..4.09, 9.25 m) under a canopy (8.88..9.54 m) with a vent box and cap
above it, and a landing (1.72 m) reached by a ramp the original only paints as steps. Relief: the ramp is seven
real steps, the front door (texture decal, 4.29 x 7.16 m) and the red rear door panel are 15 cm recesses, every
cut-out window is a 15 cm recess with a sill under the lower row, a 20 cm fascia under the eave, a ledge rings
the walls at the masonry's top, the roof cap is an 8 cm field inside its rim, the plinth's top edge is chamfered.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
B = Builder()


def rect(x0, x1, z0, z1):
    return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]


# ---- plinth, walls, ledge, fascia
B.box("plinth", (-12.60, 0.0, -11.85), (10.30, 0.57, 11.38), chamfer=0.08)
walls = B.box("walls", (-11.85, 0.0, -11.11), (9.55, 14.65, 10.64))
B.box("ledge", (-11.91, 8.80, -11.17), (9.61, 8.92, 10.70))
B.box("fascia", (-12.52, 14.39, -11.85), (10.30, 14.59, 11.38))

# ---- the curved hip roof: Catmull-Rom through the original's rings (y, x0, x1, z0, z1)
R = np.array([(14.59, -12.52, 10.30, -11.85, 11.38), (15.26, -9.99, 8.19, -9.75, 9.28), (15.94, -8.76, 6.74, -8.30, 7.83),
              (16.67, -7.61, 5.53, -7.08, 6.61), (17.64, -6.63, 4.56, -6.11, 5.64), (19.02, -5.95, 4.07, -5.63, 5.16),
              (20.07, -5.76, 3.99, -5.55, 5.08)])
P = np.vstack([2 * R[0] - R[1], R, 2 * R[-1] - R[-2]])
rings = [R[0]]
for i in range(1, len(R)):
    p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
    for k in (1, 2, 3):
        t = k / 3
        rings.append(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
for k in range(len(rings) - 1):
    a, b = rings[k], rings[k + 1]
    top = B.loft_y(f"roof{k}", rect(*a[1:]), a[0], rect(*b[1:]), b[0])
B.cut(top, B.prism_y("cap_field", rect(-5.46, 3.69, -5.25, 4.78), 19.99, 20.2))

# ---- west front: vestibule, canopy, vent box, landing and steps
vest = B.box("vestibule", (-13.51, 0.0, -4.42), (-11.30, 9.25, 4.09))
B.box("canopy", (-13.84, 8.88, -4.67), (-11.06, 9.54, 4.34), chamfer=0.04)
B.box("vent", (-13.35, 9.33, -2.21), (-11.55, 11.86, 1.80))
B.box("vent_cap", (-13.68, 11.74, -2.46), (-11.22, 12.31, 2.13), chamfer=0.04)
B.box("landing", (-14.18, 0.0, -5.16), (-11.71, 1.72, 4.75))
N = 7
for k in range(N):
    x0 = -16.79 + (2.61 / N) * k
    B.box(f"step{k}", (x0, 0.0, -5.16), (-14.18, 1.72 * (k + 1) / N, 4.75))

# ---- doors and windows
door = json.load(open(D / "decal_door.json"))["rects"]
for o in door:
    if o["normal"][0] < 0:
        B.recess(vest, o, 0.15)
    else:
        o = dict(o, w=o["w"] - 0.3, h=o["h"] - 0.2)
        B.recess(walls, o, 0.15)
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    B.recess(walls, o, 0.15)
    if o["center"][1] < 11.5:
        B.sill(f"sill{k}", o, proud=0.1, thick=0.07, overhang=0.06)

print(B.dump())
