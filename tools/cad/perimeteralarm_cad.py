#!/usr/bin/env python3
"""CAD rebuild of the perimeter alarm (appearance perimeteralarm), in the original's frame.

    D=~/craft/solid/mc2/buildings/perimeteralarm
    python3 -I tools/art/cad_building.py openings perimeteralarm > $D/openings.json   # none: the art is opaque
    python3 -I tools/cad/perimeteralarm_cad.py $D > $D/perimeteralarm.json
    solidcraft-cli run $D/perimeteralarm.json --out $D/perimeteralarm.obj
    python3 -I tools/art/cad_building.py bake perimeteralarm $D/perimeteralarm.obj

Measured from game/assets/objects/perimeteralarm.glb (nodes perimeteralarm, spinny, Beacon_Red; no animation): a
concrete ground pad (x -3.61..1.74, z +-1.74); a frustum footing (2.46 m square at the ground to 1.76 m at 1.49 m,
capped by a pyramid to 0.7 m at 1.74 m); a 0.7 m square post to 14.08 m (kept square: its art is a box-section post
with a panel per face); four siren horns at 12.27..13.31 m (pyramids from a point 0.19 m off the post axis to a 1.5 x
1.04 m red-rimmed mouth at 1.56 m), the 1.24 m lamp housing (spinny) at 14.06..15.18 m and a red beacon on it; a
control cabinet beside the post (x -3.24..-0.75, z +-0.87, 2.49 m, its outer top edge chamfered to 1.49 m).
Relief: the horns are real frustums with 20 cm deep mouths; collars on the post's two painted joints; the footing's
vent and the cabinet's grille, door and louvre are recesses (12, 10, 12 and 6 cm); the beacon is a true cone
(24 sides) instead of the original's three-sided prism; the housing's round emblem (+-z faces) a 6 cm round recess.
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, cad  # noqa: E402

D = Path(sys.argv[1])
B = Builder()


def ngon(cx, cz, r, n=24):
    return [(cx + r * math.cos(2 * math.pi * i / n), cz + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def sq(h):
    return [(-h, -h), (h, -h), (h, h), (-h, h)]


# ground pad, footing, post
B.box("pad", (-3.61, 0.0, -1.74), (1.74, 0.03, 1.74))
foot = B.loft_y("foot", sq(1.23), 0.0, sq(0.88), 1.49)
B.loft_y("foot_cap", sq(0.88), 1.49, sq(0.35), 1.74)
B.box("post", (-0.35, 1.70, -0.35), (0.35, 14.08, 0.35))
for k, (y0, y1) in enumerate([(9.39, 9.70), (5.27, 5.65)]):
    B.box(f"collar{k}", (-0.42, y0, -0.42), (0.42, y1, 0.42), chamfer=0.03)
# footing vents (the arched grille painted on each sloped face: x -0.63..0.65, y 0..1.28)
s = math.hypot(0.35, 1.49)
for k, (n, t) in enumerate([((0, 0.35 / s, 1.49 / s), (1, 0, 0)), ((0, 0.35 / s, -1.49 / s), (-1, 0, 0)),
                            ((1.49 / s, 0.35 / s, 0), (0, 0, -1)), ((-1.49 / s, 0.35 / s, 0), (0, 0, 1))]):
    n, t = np.array(n), np.array(t, float)
    b = np.cross(n, t)
    yc = 0.70
    off = 1.23 - (1.23 - 0.88) * yc / 1.49  # the face's distance from the axis at yc
    hor = np.array([n[0], 0, n[2]]) / np.linalg.norm([n[0], 0, n[2]])
    c = hor * off + np.array([0, yc, 0]) + t * 0.01
    B.recess(foot, dict(center=list(c), normal=list(n), t=list(t), b=list(b), w=1.10, h=1.15), 0.12)

# siren horns at +x, -z, -x, +z
for k in range(4):
    h = f"horn{k}"
    B.loft_y(h, [(-0.06, -0.06), (0.06, -0.06), (0.06, 0.06), (-0.06, 0.06)], 0.19,
             [(-0.52, -0.75), (0.52, -0.75), (0.52, 0.75), (-0.52, 0.75)], 1.56)
    B.c("solid.move", bodies=[h], axis=[0, 1, 0], angle="90 deg")  # up -> +x
    if k:
        B.c("solid.move", bodies=[h], axis=[0, 0, 1], angle=f"{90 * k} deg")
    B.c("solid.move", bodies=[h], translate=[0, 0, 12790])
    a = math.radians(90 * k)  # CAD rotation about Z by a: game +x -> (cos a, 0, -sin a)
    n = np.array([math.cos(a), 0.0, -math.sin(a)])
    t = np.cross([0.0, 1.0, 0.0], n)
    B.recess(h, dict(center=list(n * 1.56 + np.array([0, 12.79, 0])), normal=list(n), t=list(t), b=[0, 1, 0],
                     w=1.20, h=0.78), 0.20)

# lamp housing, its two round lenses (+-x faces), the beacon
hs = B.box("housing", (-0.62, 14.06, -0.62), (0.62, 15.18, 0.62), chamfer=0.04)
for k, sz in enumerate((1, -1)):  # the round emblem is painted on the +-z faces (texture u 0.885, v 0.917)
    B.c("solid.cylinder", radius=360.0, height=110.0, base=cad((0.0, 14.58, sz * 0.57)), axis=[0, -sz, 0],
        body_name=f"lens{k}", operation="new")
    B.cut(hs, f"lens{k}")
B.loft_y("beacon", ngon(0.03, 0.0, 0.24), 15.18, ngon(0.03, 0.0, 0.14), 15.75)

# control cabinet: the original's profile (x, y), extruded across z +-0.87
cab = B.prism_z("cabinet", [(-0.75, 0.0), (-0.75, 2.49), (-2.24, 2.49), (-3.24, 1.49), (-3.24, 0.0)], -0.87, 0.87)
for sz in (1, -1):
    n = [0, 0, sz]
    t = [sz, 0, 0]
    B.recess(cab, dict(center=[-1.655, 1.03, sz * 0.87], normal=n, t=t, b=[0, 1, 0], w=1.13, h=2.06), 0.12)
B.recess(cab, dict(center=[-3.24, 0.785, -0.02], normal=[-1, 0, 0], t=[0, 0, -1], b=[0, 1, 0], w=1.50, h=1.27), 0.10)
q = 1 / math.sqrt(2)
fr = (0.086 + 0.80) / 2
c = np.array([-3.24 + fr * 1.0, 1.49 + fr * 1.0, -0.02])
B.recess(cab, dict(center=list(c), normal=[-q, q, 0], t=[0, 0, -1], b=[q, q, 0], w=1.43, h=1.0), 0.06)
print(B.dump())
