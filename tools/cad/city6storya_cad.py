#!/usr/bin/env python3
"""CAD rebuild of the six-storey concrete-panel city block (appearance city6storya), in the original's frame.

    D=~/craft/solid/mc2/buildings/city6storya
    python3 -I tools/art/cad_building.py openings city6storya > $D/openings.json
    python3 -I tools/cad/city6storya_cad.py > $D/city6storya.json
    solidcraft-cli run $D/city6storya.json --out $D/city6storya.obj
    python3 -I tools/art/cad_building.py bake city6storya $D/city6storya.obj

The box and its two-quads-a-wall UV layout are in tools/cad/city6_facade.py. Art: beige precast panels, a pale
corner pier at each end of every wall (texture u 2..36 and 220..257), three window columns (a square pane over a
slit), six rows; the +x wall's lower half is the entrance quad with a glazed double door under the middle column.
Relief: corner piers proud 7 cm (separate bodies, capped by the cornice), each window a 15 cm recess with a sill,
the door a 20 cm recess with hood and step, cornice, plinth and parapet (city_facade.build_block). Roof: the painted
round vent a 32-sided drum with a lid, the two painted plant squares raised boxes, the three painted pipes round
20-sided pipes on saddles. The painted panel seams stay paint (one boolean each would be ~60 more cuts).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, box_edges  # noqa: E402
from city_facade import build_block  # noqa: E402
import city6_facade as F  # noqa: E402

O = F.Original("city6storya")
B = Builder()
DOOR = ("entrance", 1, 2)
win = [w for w, *_ in F.windows(O, skip=[DOOR])]
door = F.px_box(O, (1, 0, 0), "lower", (364, 467, 409, 508))
H = build_block(B, O, win, doors=[door], plinth=F.px_y(O, "lower", 498), box_edges=box_edges)
for nk in F.walls(O):
    for k, (u0, u1) in enumerate(((2, 36), (220, 257))):
        F.pilaster(B, O, f"pier{nk[0]}{nk[2]}_{k}", nk, u0, u1, 0.0, H - 0.3, 0.07)

F.drum(B, O, "vent", (325, 125), 25, H, H + 0.9)
F.drum(B, O, "ventlid", (325, 125), 27, H + 0.9, H + 1.0)
F.roof_box(B, O, "plant0", (404, 39, 464, 99), H, 1.1)
F.roof_box(B, O, "plant1", (404, 145, 464, 206), H, 1.1)
PY, PR = H + 0.22, 0.09
for k, (a, b) in enumerate((((267, 69), (404, 69)), ((267, 177), (404, 177)), ((432, 206), (432, 240)))):
    F.pipe(B, O, f"pipe{k}", a, b, PR, PY)
    F.saddles(B, O, f"pipe{k}", a, b, PR, PY, H, n=2 if k < 2 else 1)
print(B.dump())
