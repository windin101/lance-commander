#!/usr/bin/env python3
"""CAD rebuild of the six-storey bayed city block (appearance city6storyc), in the original's frame.

    D=~/craft/solid/mc2/buildings/city6storyc
    python3 -I tools/art/cad_building.py openings city6storyc > $D/openings.json
    python3 -I tools/cad/city6storyc_cad.py > $D/city6storyc.json
    solidcraft-cli run $D/city6storyc.json --out $D/city6storyc.obj
    python3 -I tools/art/cad_building.py bake city6storyc $D/city6storyc.obj

The box and its two-quads-a-wall UV layout are in tools/cad/city6_facade.py. Art: pale grey render, five window
columns, six rows; a top storey band (texture rows 0..60) over a white string course, and below it two dark vertical
bays per wall (u 50..100 and 155..205) holding the second and fourth window columns; the +x wall's lower half is
the entrance with a wide door under the middle column. Relief: the bays recessed 20 cm from the plinth up to the
string course (one cut each), their windows a further 15 cm in, the other windows 15 cm recesses, all with sills;
the string course a ledge, the door a 20 cm recess with hood and step, cornice, plinth and parapet
(city_facade.build_block). Roof: the painted skylight square, louvred vent and three tall cabinets raised, the
painted pipes round 20-sided pipes on saddles.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, box_edges  # noqa: E402
from city_facade import build_block  # noqa: E402
import city6_facade as F  # noqa: E402

O = F.Original("city6storyc")
B = Builder()
BAYS, DEPTH = ((50, 100), (155, 205)), 0.2
ws = F.windows(O, skip=[("entrance", 2, 2)])
inbay = [w for w, reg, (ci, ri), nk in ws if ci in (1, 3) and not (reg == "upper" and ri == 0)]
flat = [w for w, reg, (ci, ri), nk in ws if not (ci in (1, 3) and not (reg == "upper" and ri == 0))]
door = F.px_box(O, (1, 0, 0), "lower", (360, 465, 408, 512))
plinth = F.px_y(O, "lower", 498)
top = F.px_y(O, "upper", 66)
H = build_block(B, O, flat, doors=[door], plinth=plinth, box_edges=box_edges,
                ledges=[(top, F.px_y(O, "upper", 59), 0.06)])
for nk in F.walls(O):
    for u0, u1 in BAYS:
        bay = F.px_box(O, nk, "upper", (u0, 100, u1, 120))
        bay["center"][1], bay["h"] = (plinth + top) / 2, top - plinth
        B.recess("main", bay, DEPTH)
for k, w in enumerate(inbay):
    B.recess("main", w, 0.15, surface_shift=DEPTH)
    B.sill(f"baysill{k}", w, proud=0.09, thick=0.07, overhang=0.07, surface_shift=DEPTH)

F.roof_box(B, O, "skylight", (289, 31, 347, 91), H, 0.8)
F.roof_box(B, O, "vent", (291, 174, 340, 220), H, 0.6)
for k, (x0, x1) in enumerate(((404, 420), (427, 444), (451, 468))):
    F.roof_box(B, O, f"cabinet{k}", (x0, 167, x1, 222), H, 1.6)
PY, PR = H + 0.22, 0.09
for k, (a, b) in enumerate((((347, 58), (500, 58)), ((347, 69), (500, 69)), ((275, 141), (414, 141)),
                            ((414, 141), (414, 167)), ((436, 141), (500, 141)), ((436, 141), (436, 167)))):
    F.pipe(B, O, f"pipe{k}", a, b, PR, PY)
    if k in (0, 1, 2, 4):
        F.saddles(B, O, f"pipe{k}", a, b, PR, PY, H)
print(B.dump())
