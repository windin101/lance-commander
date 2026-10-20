#!/usr/bin/env python3
"""CAD rebuild of the government hall's grand stair (appearance s_main_stairs), in the original's frame.

    D=~/craft/solid/mc2/buildings/s_main_stairs
    python3 -I tools/art/cad_building.py openings s_main_stairs > $D/openings.json    (none: the art has no cut-outs)
    python3 -I tools/cad/s_main_stairs_cad.py $D > $D/s_main_stairs.json
    solidcraft-cli run $D/s_main_stairs.json --out $D/s_main_stairs.obj
    python3 -I tools/art/cad_building.py bake s_main_stairs $D/s_main_stairs.obj --ao 0.25

Measured from game/assets/objects/s_main_stairs.glb (faces grouped by plane): it hangs below its origin, down a
cliff. A paved landing at 0 m (half hexagon, x -14.44..14.26, z 3.56..14.50) falls as a stepped fan (painted) to an
outer half hexagon at -9.00 m (x -23.84..23.66, to z 21.66), whose three front facets stand on a retaining wall to
-14.26 m; on the axis a straight flight (x -2.56..2.50, from z 14.70 at -0.13 m to z 33.30 at -18.93 m, 45 degrees)
between parapet walls (x -2.99..-2.56 and 2.50..2.93, tops 1.29 m above the treads, down to -22.82 m) and a gate
at its head (two piers x -4.06..-2.43 and 2.49..4.11, z 11.77..15.60, from -2.44 m, each with a cap slab to
1.54 m and a crest to 1.77 m). Relief: the painted steps become real ones, phased to the paint (the stair texture repeats
nine steps a tile, the treads start 7/512 into it): the fan as nine stacked slabs (1 m risers), the flight as a
22-step sawtooth (1.18 m along the slope); the parapets carry a coping, the pier caps a chamfered edge. Bake with --ao 0.25 (the risers sit behind the
original slope and went near black at the default).
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

B = Builder()
PH = 7 / 512  # tile fraction where the first painted tread edge (a nose) lies

inner = np.array([(-14.44, 3.56), (14.26, 3.56), (11.52, 10.32), (4.35, 14.50), (-4.52, 14.50), (-11.70, 10.32)])
outer = np.array([(-23.84, 3.56), (23.66, 3.56), (19.12, 14.75), (7.25, 21.66), (-7.43, 21.66), (-19.30, 14.75)])


def ring(f):
    """The fan's outline at slope fraction f (0 = landing edge, 1 = foot at -9 m)."""
    return [tuple(p) for p in (inner + (outer - inner) * f).round(3)]


# fan: the landing slab, then a slab per step; nose k sits at fraction PH + k/9 on the original slope
noses = [PH + k / 9 for k in range(9)]
tops = [0.0] + [-9.0 * f for f in noses[1:]]
outl = noses
for k in range(9):
    y1 = tops[k]
    y0 = tops[k + 1] if k + 1 < 9 else -9.0
    B.prism_y(f"fan{k}", ring(outl[k]), y0, y1)
B.prism_y("foot", ring(1.0), -9.30, -9.0)  # the last tread, out to the fan's foot
B.prism_y("wall", [(19.12, 14.75), (7.25, 21.66), (-7.43, 21.66), (-19.30, 14.75)], -14.26, -9.0)  # under the front facets only

# the flight: a sawtooth in (z, y), extruded across x -2.56..2.50
p0, p1 = np.array([14.70, -0.13]), np.array([33.30, -18.93])
L = float(np.linalg.norm(p1 - p0))
d = (p1 - p0) / L
step = L / 22.5  # 2.5 tiles of nine steps
prof = []
k = 0
while True:
    s = PH * L / 2.5 + k * step
    if s > L - 0.05:
        break
    z, y = p0 + d * s
    if k == 0:
        prof.append((14.37, round(y, 3)))
    else:
        prof.append((round(prof[-1][0], 3), round(y, 3)))  # foot of the riser under the last nose
    prof.append((round(z, 3), round(y, 3)))  # this nose
    k += 1
zl = prof[-1][0]
prof += [(33.60, prof[-1][1]), (33.60, -19.30), (29.53, -22.82), (10.01, -3.30), (14.37, -0.10)]
# prism_x takes (z, y); the polygon must not repeat its first point
B.prism_x("flight", [(z, y) for z, y in prof], -2.56, 2.50)

wall_zy = [(10.01, -3.30), (14.37, 1.16), (33.90, -18.36), (29.53, -22.82)]
for nm, x0, x1 in (("pwall_l", -2.99, -2.56), ("pwall_r", 2.50, 2.93)):
    B.prism_x(nm, wall_zy, x0, x1)
    B.prism_x(nm + "_cope", [(14.37, 1.16), (14.37, 1.30), (34.04, -18.36), (33.90, -18.36)], x0 - 0.06, x1 + 0.06)

# gate
B.box("post_l", (-4.06, -2.44, 11.77), (-2.43, 1.30, 15.60))
B.box("post_r", (2.49, -2.44, 11.77), (4.11, 1.30, 15.60))
for nm, (a0, a1), (c0, c1) in (("l", (-4.26, -2.23), (-4.05, -2.45)), ("r", (2.28, 4.32), (2.48, 4.08))):
    B.box("cap_" + nm, (a0, 1.30, 11.57), (a1, 1.54, 15.80), chamfer=0.04)
    B.box("crest_" + nm, (c0, 1.54, 11.74), (c1, 1.77, 13.37))

print(B.dump())
