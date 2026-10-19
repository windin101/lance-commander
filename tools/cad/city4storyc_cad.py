#!/usr/bin/env python3
"""CAD rebuild of the four-storey city block (appearance city4storyc), in the original's frame.

    D=~/craft/solid/mc2/buildings/city4storyc
    python3 -I tools/cad/city4storyc_cad.py > $D/city4storyc.json
    solidcraft-cli run $D/city4storyc.json --out $D/city4storyc.obj
    python3 -I tools/art/cad_building.py bake city4storyc $D/city4storyc.obj

The three city4story* originals are one plain box (x -10.148..7.776, z -10.802..7.123, to 14.184 m, 10 triangles)
with different art. Each wall uses its own 0.5 x 0.5 square of the 512 px texture (u left to right seen from
outside, v from roof line to ground). Its windows are painted (only some panes are cut-outs), so the grid is
given here as texture pixel boxes (columns and rows measured from dark-pane profiles of each wall's square) and
mapped onto the wall by tools/cad/city_facade.py. Relief (city_facade.build_block, as city2storyb): every window a
15 cm recess with a sill, doors a 20 cm recess with a hood and a step, a garage door a 30 cm recess with a
lintel, a cornice at the roof line and a plinth (one flat colour each), a parapet; painted roof plant raised
as housings (flat-coloured sides, painted cap) with true round fan drums.
Art: white ribbon-window block. Three window rows over a plain ground floor: the +z and -z walls 5 x 3, the
-x wall 5 x 3 with a double door in the ground floor, the +x wall its own 5 x 3. A ledge runs round the top of
the ground floor where the art paints one. Roof: an air unit with two black fans and a grille (raised 1 m),
and a grille box (60 cm).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, box_edges  # noqa: E402
from city_facade import Original, build_block, cells, px_box, px_height, roof_unit  # noqa: E402

O = Original("city4storyc")
B = Builder()
L = [(17, 39), (65, 87), (117, 139), (169, 191), (221, 243)]
R = [(273, 294), (322, 343), (372, 393), (425, 446), (477, 498)]
ROWS = [(275, 305), (338, 368), (403, 433)]
win = cells(O, (0, 0, 1), L, ROWS) + cells(O, (0, 0, -1), L, ROWS) + cells(O, (-1, 0, 0), R, ROWS)
win += cells(O, (1, 0, 0), L, [(15, 47), (78, 110), (143, 173)])
door = px_box(O, (-1, 0, 0), (363, 465, 412, 512))
ledge = (px_height(O, (0, 0, 1), 453), px_height(O, (0, 0, 1), 435), 0.12)
build_block(B, O, win, doors=[door], ledges=[ledge], box_edges=box_edges)
roof_unit(B, O, "unit", (342, 23, 440, 139), 1.0, fans=[(370, 47.5, 16.5), (413, 47.5, 16.5)])
roof_unit(B, O, "grille", (288, 161, 347, 215), 0.6, inset=0.1)
print(B.dump())
