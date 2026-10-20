#!/usr/bin/env python3
"""CAD rebuild of the six-storey pilastered city block (appearance city6storyb), in the original's frame.

    D=~/craft/solid/mc2/buildings/city6storyb
    python3 -I tools/art/cad_building.py openings city6storyb > $D/openings.json
    python3 -I tools/cad/city6storyb_cad.py > $D/city6storyb.json
    solidcraft-cli run $D/city6storyb.json --out $D/city6storyb.obj
    python3 -I tools/art/cad_building.py bake city6storyb $D/city6storyb.obj

The box and its two-quads-a-wall UV layout are in tools/cad/city6_facade.py. Art: grey-green concrete, five window
columns (pane over slit, dark spandrels between) separated by pale pilasters, six rows; the +x wall's lower half is
the entrance with a double door under the middle column. Relief: the pilasters (texture u 42..62, 90..114,
142..166, 194..218 and the two edge strips) proud 7 cm as separate bodies under the cornice, each window a 15 cm
recess with a sill, the door a 20 cm recess with hood and step, cornice, plinth and parapet (city_facade.build_block).
Roof: the painted cooling ring a 32-sided drum with its dark centre cut 30 cm deep, the louvred vent box and the
small box raised, the painted pipes round 20-sided pipes on saddles.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, box_edges  # noqa: E402
from city_facade import build_block  # noqa: E402
import city6_facade as F  # noqa: E402

O = F.Original("city6storyb")
B = Builder()
win = [w for w, *_ in F.windows(O, skip=[("entrance", 2, 2)])]
door = F.px_box(O, (1, 0, 0), "lower", (361, 465, 411, 511))
H = build_block(B, O, win, doors=[door], plinth=F.px_y(O, "lower", 498), box_edges=box_edges)
for nk in F.walls(O):
    for k, (u0, u1) in enumerate(((2, 14), (42, 62), (90, 114), (142, 166), (194, 218), (246, 257))):
        F.pilaster(B, O, f"pil{nk[0]}{nk[2]}_{k}", nk, u0, u1, 0.0, H - 0.3, 0.07)

F.drum(B, O, "ring", (350, 102), 42, H, H + 0.7)
F.drum(B, O, "ringcut", (350, 102), 22, H + 0.4, H + 0.8)
B.cut("ring", "ringcut")
F.drum(B, O, "fanhub", (350, 102), 5, H + 0.35, H + 0.5, sides=20)
F.roof_box(B, O, "vent", (424, 22, 475, 75), H, 0.9)
F.roof_box(B, O, "smallbox", (282, 197, 314, 228), H, 0.5)
PY, PR = H + 0.22, 0.09
for k, (a, b) in enumerate((((350, 50), (424, 50)), ((354, 144), (354, 240)), ((392, 102), (500, 102)), ((437, 102), (437, 239)))):
    F.pipe(B, O, f"pipe{k}", a, b, PR, PY)
    F.saddles(B, O, f"pipe{k}", a, b, PR, PY, H)
F.pipe(B, O, "pipe0riser", (350, 50), (350, 62), PR, PY)
print(B.dump())
