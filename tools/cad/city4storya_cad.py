#!/usr/bin/env python3
"""CAD rebuild of the four-storey city block (appearance city4storya), in the original's frame.

    D=~/craft/solid/mc2/buildings/city4storya
    python3 -I tools/cad/city4storya_cad.py > $D/city4storya.json
    solidcraft-cli run $D/city4storya.json --out $D/city4storya.obj
    python3 -I tools/art/cad_building.py bake city4storya $D/city4storya.obj

The three city4story* originals are one plain box (x -10.148..7.776, z -10.802..7.123, to 14.184 m, 10 triangles)
with different art. Each wall uses its own 0.5 x 0.5 square of the 512 px texture (u left to right seen from
outside, v from roof line to ground). Its windows are painted (only some panes are cut-outs), so the grid is
given here as texture pixel boxes (columns and rows measured from dark-pane profiles of each wall's square) and
mapped onto the wall by tools/cad/city_facade.py. Relief (city_facade.build_block, as city2storyb): every window a
15 cm recess with a sill, doors a 20 cm recess with a hood and a step, a garage door a 30 cm recess with a
lintel, a cornice at the roof line and a plinth (one flat colour each), a parapet; painted roof plant raised
as housings (flat-coloured sides, painted cap) with true round fan drums.
Art: red brick. The +z and -z walls 5 x 4 windows, the -x wall the same with a single door (bottom middle), the
+x wall blank brick with a top row of five. Roof: the painted fan pair and equipment row of city2storya.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, box_edges  # noqa: E402
from city_facade import Original, build_block, cells, px_box, px_height, roof_xz, ngon  # noqa: E402

O = Original("city4storya")
B = Builder()
L = [(18, 37), (67, 85), (119, 137), (170, 190), (223, 241)]
R = [(275, 293), (322, 341), (373, 391), (427, 445), (479, 497)]
ROWS = [(276, 300), (340, 364), (404, 428), (468, 493)]
win = cells(O, (0, 0, 1), L, ROWS) + cells(O, (0, 0, -1), L, ROWS) + cells(O, (-1, 0, 0), R, ROWS, skip=[(2, 3)])
win += cells(O, (1, 0, 0), L, [(19, 45)])
door = px_box(O, (-1, 0, 0), (362, 466, 410, 512))
H = build_block(B, O, win, doors=[door], plinth=px_height(O, (0, 0, 1), 495), box_edges=box_edges)

fx0, fz0, fx1, fz1 = roof_xz(O, (283, 136, 399, 219))
B.box("fanhouse@avg", (fx0 + 0.3, H, fz0 + 0.3), (fx1 - 0.3, H + 0.33, fz1 - 0.3))
B.box("fancap", (fx0 + 0.27, H + 0.33, fz0 + 0.27), (fx1 - 0.27, H + 0.4, fz1 - 0.27))
for k, px in enumerate((311, 371)):
    cx, cz, _, _ = roof_xz(O, (px, 178, px, 178))
    B.prism_y(f"fandrum{k}", ngon(1.45, 24, cx, cz), H + 0.4, H + 0.55)
for nm, box, ph in (("plant", (405, 201, 499, 237), 0.6), ("topbox", (409, 12, 487, 28), 0.35)):
    x0, z0, x1, z1 = roof_xz(O, box)
    B.box(f"{nm}box@avg", (x0 + 0.15, H, z0 + 0.15), (x1 - 0.15, H + ph, z1 - 0.15))
    B.box(f"{nm}cap", (x0 + 0.12, H + ph, z0 + 0.12), (x1 - 0.12, H + ph + 0.08, z1 - 0.12))
print(B.dump())
