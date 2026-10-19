#!/usr/bin/env python3
"""CAD rebuild of the pipe-head tank (appearance pipetank), in the original's frame.

    D=~/craft/solid/mc2/buildings/pipetank
    python3 -I tools/art/cad_building.py openings pipetank > $D/openings.json      (none: the art has no cut-outs)
    python3 -I tools/cad/pipetank_cad.py > $D/pipetank.json
    solidcraft-cli run $D/pipetank.json --out $D/pipetank.obj
    python3 -I tools/art/cad_building.py bake pipetank $D/pipetank.obj --texel 0.015

Measured from game/assets/objects/pipetank.glb (one mesh, faces listed with their UVs; painted features placed with
`cad_building.py decal pipetank 0 u0 v0 u1 v1`): an octagonal tank (flats 4.72 m, 4.60 -> 11.93 m) with a bevelled
underside (to flats 3.94 at 3.92 m) and a bevelled lid (to flats 2.68 at 12.44 m); under it a pedestal x -3.24..5.11,
z -3.24..3.24, 2.73 m high, cut off at the corners and narrowing to a 3.4 m square at 3.92 m; from its +x face a
five-sided pipe (y 0.52..2.22) runs to a tapered end block x 11.93..12.78. Relief: the painted hazard windows are
10 cm recesses on all eight flats; the painted band seams above and below them are 4 cm proud rings; the lid's
painted hatch is a raised chamfered disc; the pipe is round (r 0.80) with flanges at both ends, and its painted
bore in the end block a real 30 cm hole.
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, cad, cad_dir  # noqa: E402

B = Builder()


def octagon(f, s=None, cx=0.0, cz=0.0):
    s = f * math.tan(math.pi / 8) if s is None else s
    return [(cx + x, cz + z) for x, z in ((-s, -f), (s, -f), (f, -s), (f, s), (s, f), (-s, f), (-f, s), (-f, -s))]


# ---- pedestal: cut-corner block, then a frustum up to the tank's underside
base = [(-1.7, -3.24), (1.7, -3.24), (5.11, -1.7), (5.11, 1.7), (1.7, 3.24), (-1.7, 3.24), (-3.24, 1.7), (-3.24, -1.7)]
B.prism_y("pedestal", base, 0.0, 2.73)
sq = [(-1.65, -1.7), (1.65, -1.7), (1.7, -1.65), (1.7, 1.65), (1.65, 1.7), (-1.65, 1.7), (-1.7, 1.65), (-1.7, -1.65)]
B.loft_y("pedestal_top", base, 2.73, sq, 3.92)

# ---- tank: bevelled underside, walls, bevelled lid
B.loft_y("tank_under", octagon(3.94, 1.63), 3.92, octagon(4.72, 1.96), 4.60)
B.prism_y("tank", octagon(4.72, 1.96), 4.60, 11.93)
B.loft_y("tank_lid", octagon(4.72, 1.96), 11.93, octagon(2.68, 1.11), 12.44)
# hatch on the lid
B.c("solid.cylinder", radius=2150, height=80, base=cad((-0.04, 12.44 - 0.01, -0.02)), axis=[0, 0, 1],
    body_name="hatch", operation="new")
B.c("solid.chamfer", edges=[cad((-0.04 + 2.15, 12.51, -0.02))], distance=30, body="hatch")
# seam rings
for k, y in enumerate((6.20, 10.78)):
    B.prism_y(f"ring{k}", octagon(4.76, 1.97), y - 0.04, y + 0.04)
# hazard windows: 10 cm recesses on the eight flats
for k in range(8):
    a = -math.pi / 2 + k * math.pi / 4          # outward normal angle in (x, z)
    n = np.array([math.cos(a), 0.0, math.sin(a)])
    b = np.array([0.0, 1.0, 0.0])
    t = np.cross(b, n)
    o = {"center": (n * 4.72 + b * 8.37).tolist(), "normal": n.tolist(), "t": t.tolist(), "b": b.tolist(),
         "w": 3.42, "h": 1.50}
    B.recess("tank", o, 0.10)

# ---- pipe, flanges and the end block with its bore
PY, PR = 1.30, 0.80
B.c("solid.cylinder", radius=PR * 1000, height=(11.95 - 5.0) * 1000, base=cad((5.0, PY, 0.0)),
    axis=[1, 0, 0], body_name="pipe", operation="new")
for k, x in enumerate((5.11, 11.78)):
    B.c("solid.cylinder", radius=920, height=150, base=cad((x, PY, 0.0)), axis=[1, 0, 0],
        body_name=f"flange{k}", operation="new")
B.prism_x("endblock", [(-1.53, 0.0), (1.53, 0.0), (0.85, 2.73), (-0.85, 2.73)], 11.93, 12.78)
B.c("solid.cylinder", radius=600, height=350, base=cad((12.78 - 0.30, 1.14, 0.07)), axis=[1, 0, 0],
    body_name="bore", operation="new")
B.cut("endblock", "bore")

print(B.dump())
