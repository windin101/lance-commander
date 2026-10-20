#!/usr/bin/env python3
"""CAD rebuild of the two-storey shopfront city block (appearance city2storyc), in the original's frame.

    D=~/craft/solid/mc2/buildings/city2storyc
    python3 -I tools/art/cad_building.py openings city2storyc > $D/openings.json
    python3 -I tools/cad/city2storyc_cad.py > $D/city2storyc.json
    solidcraft-cli run $D/city2storyc.json --out $D/city2storyc.obj
    python3 -I tools/art/cad_building.py bake city2storyc $D/city2storyc.obj

city2storyc is city2storya's box (x -10.044..7.713, z -7.663..10.094, to 6.946 m, 10 triangles) with its walls on
other parts of the 512 px texture: the -z and +z walls the band v 0.494..0.746 left half, the +x wall the same band's
right half (the graffiti mural), the -x wall the bottom right quarter (a row of windows over two shopfronts and a
glazed double door). Only the upper storey has windows on the band walls (five 2 m tall two-pane windows, the
city4story column spacing); their ground floor is blank brick over a dark 0.6 m plinth. Window, shopfront and door
boxes are texture pixel boxes mapped onto the wall by tools/cad/city_facade.py; relief by city_facade.build_block
(windows 15 cm recesses with sills, the door a 20 cm recess with hood and step, the shopfronts 30 cm recesses with
a lintel, cornice, plinth, parapet). Roof: the painted fan pair raised as one housing with two round fan drums,
the two painted equipment boxes raised, and the two painted white pipes as round 20-sided pipes (an elbow collar at the bend) on low saddles.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, box_edges, cad, cad_dir  # noqa: E402
from city_facade import Original, build_block, cells, px_box, px_height, roof_xz, ngon  # noqa: E402

O = Original("city2storyc")
B = Builder()
L = [(18, 38), (67, 86), (118, 138), (169, 189), (222, 242)]
R = [(274, 294), (322, 342), (374, 394), (426, 446), (478, 497)]
win = cells(O, (0, 0, 1), L, [(263, 300)]) + cells(O, (0, 0, -1), L, [(263, 300)])
win += cells(O, (1, 0, 0), R, [(263, 300)]) + cells(O, (-1, 0, 0), R, [(390, 428)])
door = px_box(O, (-1, 0, 0), (364, 466, 408, 512))
shops = [px_box(O, (-1, 0, 0), (272, 463, 359, 498)), px_box(O, (-1, 0, 0), (413, 463, 500, 498))]
H = build_block(B, O, win, doors=[door], garages=shops, plinth=px_height(O, (0, 0, 1), 371), box_edges=box_edges)

fx0, fz0, fx1, fz1 = roof_xz(O, (281, 133, 404, 222))
B.box("fanhouse@avg", (fx0 + 0.3, H, fz0 + 0.3), (fx1 - 0.3, H + 0.33, fz1 - 0.3))
B.box("fancap", (fx0 + 0.27, H + 0.33, fz0 + 0.27), (fx1 - 0.27, H + 0.4, fz1 - 0.27))
for k, px in enumerate((313, 371)):
    cx, cz, _, _ = roof_xz(O, (px, 175, px, 175))
    B.prism_y(f"fandrum{k}", ngon(1.45, 24, cx, cz), H + 0.4, H + 0.55)
for nm, box, ph, curb in (("topbox", (428, 37, 471, 80), 0.9, (423, 31, 476, 82)), ("plant", (429, 203, 472, 237), 0.7, None)):
    x0, z0, x1, z1 = roof_xz(O, box)
    if curb:
        c0, d0, c1, d1 = roof_xz(O, curb)
        B.box(f"{nm}curb@avg", (c0, H, d0), (c1, H + 0.15, d1))
    B.box(f"{nm}box@avg", (x0, H, z0), (x1, H + ph, z1))
    B.box(f"{nm}cap", (x0 - 0.03, H + ph, z0 - 0.03), (x1 + 0.03, H + ph + 0.08, z1 + 0.03))

# the two white pipes: from the fan housing's side along x, then along z into the plant box
PR, PY = 0.11, H + 0.3


def ring(r, cx, cy, n=20):
    return ngon(r, n, cx, cy)


for k, (y0, xc, ye) in enumerate(((151, 463, 203), (162, 439, 203))):
    ax, az, _, _ = roof_xz(O, (404, y0, 404, y0))
    bx, _, _, _ = roof_xz(O, (xc, y0, xc, y0))
    _, ez, _, _ = roof_xz(O, (xc, ye, xc, ye))
    B.prism_x(f"pipe{k}a", ring(PR, az, PY), ax - 0.3, bx - PR)
    B.prism_z(f"pipe{k}b", ring(PR, bx, PY), az + PR, ez + 0.05)
    B.prism_y(f"pipe{k}elbow", ring(PR * 1.35, bx, az), PY - PR * 1.35, PY + PR * 1.35)
    for j, t in enumerate((0.35, 0.75)):
        sx, sz = ax + (bx - ax) * t, az
        B.box(f"pipe{k}saddle{j}@8f8b84", (sx - 0.08, H, sz - 0.14), (sx + 0.08, PY - PR + 0.02, sz + 0.14))
print(B.dump())
