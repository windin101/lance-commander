#!/usr/bin/env python3
"""CAD rebuild of the administration entrance block (appearance s_admin_entry), in the original's frame.

    D=~/craft/solid/mc2/buildings/s_admin_entry
    python3 -I tools/art/cad_building.py openings s_admin_entry > $D/openings.json
    python3 -I tools/cad/s_admin_entry_cad.py $D > $D/s_admin_entry.json
    solidcraft-cli run $D/s_admin_entry.json --out $D/s_admin_entry.obj
    python3 -I tools/art/cad_building.py bake s_admin_entry $D/s_admin_entry.obj --glass 182,190,198   # the original's lit (white) windows

Measured from game/assets/objects/s_admin_entry.glb (faces grouped by plane): a cross-shaped plan, two
overlapping arms. Plinth (0..0.31 m) and roof slab (5.04..5.56 m) share one outline: x -6.92..6.92 by
z -15.20..12.72, and x -10.62..10.62 by z -7.70..6.28. The walls stand 0.51 m inside it (x +-6.41 by
z -14.69..12.22, x +-10.21 by z -7.18..5.77, 0.32..5.06 m). A gabled skylight (x +-2.80, z -1.86..1.77, ridge
along z at 7.04 m) sits on the roof. Relief: plinth and slab with chamfered top edges, a 6 cm roof field inside
a 0.35 m rim, a kerb round the skylight, the painted doors recessed 12 cm under a hood, any cut-out a recess.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, cad  # noqa: E402

D = Path(sys.argv[1])
B = Builder()

ARMS = [((-6.92, -15.20), (6.92, 12.72)), ((-10.62, -7.70), (10.62, 6.28))]
WALL = [((-6.41, -14.69), (6.41, 12.22)), ((-10.21, -7.18), (10.21, 5.77))]


def cross(a, b):
    """Outline of two crossing rectangles (a long along z, b long along x), counter-clockwise in (x, z)."""
    (ax0, az0), (ax1, az1) = a
    (bx0, bz0), (bx1, bz1) = b
    return [(ax0, az0), (ax1, az0), (ax1, bz0), (bx1, bz0), (bx1, bz1), (ax1, bz1), (ax1, az1), (ax0, az1),
            (ax0, bz1), (bx0, bz1), (bx0, bz0), (ax0, bz0)]


def top_edges(poly, y, convex_only=True):
    """Midpoints of the outline's edges at height y (game coords, CAD-converted by the chamfer call)."""
    n = len(poly)
    return [((poly[i][0] + poly[(i + 1) % n][0]) / 2, y, (poly[i][1] + poly[(i + 1) % n][1]) / 2) for i in range(n)]


def chamfer(body, poly, y, d):
    B.c("solid.chamfer", edges=[cad(e) for e in top_edges(poly, y)], distance=round(d * 1000, 2), body=body)


plinth = B.prism_y("plinth", cross(*ARMS), 0.0, 0.31)
chamfer(plinth, cross(*ARMS), 0.31, 0.05)
walls = B.prism_y("walls", cross(*WALL), 0.31, 5.04)
roof = B.prism_y("roof", cross(*ARMS), 5.04, 5.56)
chamfer(roof, cross(*ARMS), 5.56, 0.05)
# roof field: the dark membrane inside a light rim, 6 cm down
rim = 0.35
field = B.prism_y("field", cross(((ARMS[0][0][0] + rim, ARMS[0][0][1] + rim), (ARMS[0][1][0] - rim, ARMS[0][1][1] - rim)),
                                 ((ARMS[1][0][0] + rim, ARMS[1][0][1] + rim), (ARMS[1][1][0] - rim, ARMS[1][1][1] - rim))),
                  5.50, 5.80)
B.cut(roof, field)
# skylight: kerb plus a gable along z
B.box("kerb", (-2.95, 5.46, -2.01), (2.95, 5.70, 1.92), chamfer=0.03)
B.prism_z("skylight", [(-2.80, 5.70), (2.80, 5.70), (0.0, 7.04)], -1.86, 1.77)
B.box("ridge", (-0.08, 6.96, -1.94), (0.08, 7.10, 1.85))

for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    if abs(o["normal"][1]) > 0.5 or o["center"][1] < 0.3 or o["center"][1] > 5.1:
        continue
    B.recess(walls, o, 0.15)
for k, o in enumerate(json.load(open(D / "doors.json"))["rects"]):
    if abs(o["normal"][1]) > 0.5 or o["h"] < 1.2:
        continue
    B.recess(walls, o, 0.12)
    B.sill(f"hood{k}", o, proud=0.14, thick=0.08, overhang=0.10, top=True)

print(B.dump())
