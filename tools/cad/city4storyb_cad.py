#!/usr/bin/env python3
"""CAD rebuild of the four-storey city block (appearance city4storyb), in the original's frame.

    D=~/craft/solid/mc2/buildings/city4storyb
    python3 -I tools/cad/city4storyb_cad.py > $D/city4storyb.json
    solidcraft-cli run $D/city4storyb.json --out $D/city4storyb.obj
    python3 -I tools/art/cad_building.py bake city4storyb $D/city4storyb.obj

The three city4story* originals are one plain box (x -10.148..7.776, z -10.802..7.123, to 14.184 m, 10 triangles)
with different art. Each wall uses its own 0.5 x 0.5 square of the 512 px texture (u left to right seen from
outside, v from roof line to ground). Its windows are painted (only some panes are cut-outs), so the grid is
given here as texture pixel boxes (columns and rows measured from dark-pane profiles of each wall's square) and
mapped onto the wall by tools/cad/city_facade.py. Relief (city_facade.build_block, as city2storyb): every window a
15 cm recess with a sill, doors a 20 cm recess with a hood and a step, a garage door a 30 cm recess with a
lintel, a cornice at the roof line and a plinth (one flat colour each), a parapet; painted roof plant raised
as housings (flat-coloured sides, painted cap) with true round fan drums.
Art: grey render. The +z wall 5 x 4 windows with a roller garage door over the lower middle three columns; the
-x wall 5 x 4 with a double door (bottom middle); the +x and -z walls share one 5 x 4 square. Roof: two air
units with two black fans each, raised 1 m, a fan drum over each painted fan.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, box_edges  # noqa: E402
from city_facade import Original, build_block, cells, px_box, roof_unit  # noqa: E402

O = Original("city4storyb")
B = Builder()
L = [(18, 37), (67, 85), (118, 137), (170, 189), (223, 241)]
R = [(274, 293), (323, 341), (373, 391), (427, 445), (479, 496)]
ROWS = [(276, 300), (340, 364), (404, 428), (468, 492)]
TOP = [(20, 44), (84, 108), (144, 168), (208, 232)]
garage_cells = [(c, r) for c in (1, 2, 3) for r in (2, 3)]
win = cells(O, (0, 0, 1), L, ROWS, skip=garage_cells) + cells(O, (-1, 0, 0), R, ROWS, skip=[(2, 3)])
win += cells(O, (1, 0, 0), L, TOP) + cells(O, (0, 0, -1), L, TOP)
door = px_box(O, (-1, 0, 0), (361, 463, 411, 512))
garage = px_box(O, (0, 0, 1), (60, 410, 192, 512))
build_block(B, O, win, doors=[door], garages=[garage], box_edges=box_edges)
roof_unit(B, O, "unit0", (277, 106, 381, 231), 1.0, fans=[(306, 135.5, 16.5), (349.5, 135.5, 16.5)])
roof_unit(B, O, "unit1", (384, 106, 486, 231), 1.0, fans=[(414, 135.5, 16.5), (457.5, 135.5, 16.5)])
print(B.dump())
