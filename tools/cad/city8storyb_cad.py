#!/usr/bin/env python3
"""CAD rebuild of the eight-storey pilastered city tower (appearance city8storyb), in the original's frame.

    D=~/craft/solid/mc2/buildings/city8storyb
    python3 -I tools/art/cad_building.py openings city8storyb > $D/openings.json
    python3 -I tools/cad/city8storyb_cad.py > $D/city8storyb.json
    solidcraft-cli run $D/city8storyb.json --out $D/city8storyb.obj
    python3 -I tools/art/cad_building.py bake city8storyb $D/city8storyb.obj

The box and its UV layout are in tools/cad/city8_facade.py. Art: grey-green concrete, five window columns (a
light-framed pane-over-slit window, then a dark spandrel, per storey) between plain pilasters, eight storeys; the +x
wall's lower half has a double door under the middle column. Relief: the pilasters (texture u 0..14, 42..62,
90..114, 142..166, 194..218, 246..258) proud 10 cm as separate bodies between plinth and cornice, every window a
15 cm recess (to its painted frame) with a sill, the door a 22 cm recess with a hood and a step, a cornice band at
the dark roof line, a plinth, a parapet on the roof's light rim. Roof (the city6storyb roof art): the painted
cooling ring a 32-sided drum with its dark centre cut 30 cm deep and a fan hub, the louvred vent box and the small
box raised, the painted pipes as round 20-sided pipes on saddles.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, box_edges  # noqa: E402
import city8_facade as F  # noqa: E402
import city6_facade as F6  # noqa: E402  (roof helpers: they only use the roof affine)

O = F.Original("city8storyb")
B = Builder()
(X0, _, Z0), (X1, H, Z1) = O.lo, O.hi
PX = (1, 0, 0)
main = B.box("main", (X0, 0.0, Z0), (X1, H, Z1), chamfer=0.05, chamfer_edges=box_edges((X0, 0.0, Z0), (X1, H, Z1), "vertical"))
for k, (w, *_) in enumerate(F.windows(O, skip=[(PX, "lower", 2, 3)])):
    B.recess(main, w, 0.15)
    B.sill(f"sill{k}", w, proud=0.1, thick=0.07, overhang=0.06)
door = F.px_box(O, PX, "lower", (361, 465, 411, 512))
B.recess(main, door, 0.22)
B.sill("doorhood", door, proud=0.4, thick=0.12, overhang=0.22, top=True)
import numpy as np  # noqa: E402
n, t, c = np.array(door["normal"]), np.array(door["t"]), np.array(door["center"])
a, b = c + t * (door["w"] / 2 + 0.35), c - t * (door["w"] / 2 + 0.35) + n * 0.55
lo, hi = np.minimum(a, b), np.maximum(a, b)
B.box("doorstep@8f8b84", (lo[0], 0.0, lo[2]), (hi[0], 0.15, hi[2]))

CY = F.px_y(O, "upper", 10)
PY = F.px_y(O, "lower", 497)
for nk in F.walls(O):
    for k, (u0, u1) in enumerate(((0, 14), (42, 62), (90, 114), (142, 166), (194, 218), (246, 258))):
        F.strip(B, O, f"pil{nk[0]}{nk[2]}_{k}", nk, u0, u1, PY, CY, 0.10)
F.rings(B, O, (("cornice", CY, H, 0.3), ("plinth", 0.0, PY, 0.2)))
F.parapet(B, O)

F6.drum(B, O, "ring", (350, 102), 42, H, H + 0.7)
F6.drum(B, O, "ringcut", (350, 102), 22, H + 0.4, H + 0.8)
B.cut("ring", "ringcut")
F6.drum(B, O, "fanhub", (350, 102), 5, H + 0.35, H + 0.5, sides=20)
F6.roof_box(B, O, "vent", (424, 22, 475, 75), H, 0.9)
F6.roof_box(B, O, "smallbox", (282, 197, 314, 228), H, 0.5)
PYP, PR = H + 0.22, 0.09
for k, (a, b) in enumerate((((350, 50), (424, 50)), ((354, 144), (354, 240)), ((392, 102), (500, 102)), ((437, 102), (437, 239)))):
    F6.pipe(B, O, f"pipe{k}", a, b, PR, PYP)
    F6.saddles(B, O, f"pipe{k}", a, b, PR, PYP, H)
F6.pipe(B, O, "pipe0riser", (350, 50), (350, 62), PR, PYP)
print(B.dump())
