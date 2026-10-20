#!/usr/bin/env python3
"""CAD rebuild of the government hall's right wing (appearance s_main_rightwing), in the original's frame.

    D=~/craft/solid/mc2/buildings/s_main_rightwing
    python3 -I tools/art/cad_building.py openings s_main_rightwing > $D/openings.json
    (openings and decal were run with cad_building.CELL = 0.06 m (0.04 for decal), set from a wrapper: the 2 cm
    default ran past a 6 GB cap on these big glazed walls, as query_pairs grows with the square of the density)
    python3 -I tools/art/cad_building.py decal s_main_rightwing 2 0.36 0.52 0.64 1.0 > $D/decal_door.json
    python3 -I tools/cad/s_main_rightwing_cad.py $D > $D/s_main_rightwing.json
    solidcraft-cli run $D/s_main_rightwing.json --out $D/s_main_rightwing.obj
    python3 -I tools/art/cad_building.py bake s_main_rightwing $D/s_main_rightwing.obj

Measured from game/assets/objects/s_main_rightwing.glb (faces grouped by plane): a block (x -11.72..3.84,
z -9.82..3.75, 15.09 m) under a hipped roof from eaves at 14.95 m (x -12.09..4.21, z -10.20..4.13) to a flat top
at 17.59 m (x -8.24..0.36, z -6.04..0.30); on its +z side a porch (x -9.20..1.45, z 3.69..5.56, 6.48 m) under a
lean-to roof hipped up to 8.27 m against the wall, and in front of it an entrance (x -7.68..-0.03, z 5.51..11.10,
3.01 m) under a chamfered rim (to 3.55 m). Relief: every cut-out window is a recess (20 cm, sills under the tall
ones), a cornice ledge (flat colour, @avg: sampled, it smeared the vent row behind it) under the eaves and a string course at the floor line, the roof top's flat field and the
entrance roof's field are 8 cm recesses inside their rims, the door is a 15 cm recess.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
B = Builder()


def rect(x0, x1, z0, z1):
    return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]


main = B.box("main", (-11.72, 0.0, -9.82), (3.84, 15.0, 3.75))
roof = B.loft_y("roof", rect(-12.09, 4.21, -10.20, 4.13), 14.95, rect(-8.24, 0.36, -6.04, 0.30), 17.59)
B.cut(roof, B.box("f_roof", (-7.84, 17.51, -5.64), (-0.04, 17.8, -0.10)))
B.box("ledge_r@avg", (-11.84, 14.40, -9.94), (3.96, 14.60, 3.87))
B.box("course@avg", (-11.80, 7.45, -9.90), (3.92, 7.60, 3.83))
porch = B.box("porch", (-9.20, 0.0, 3.69), (1.45, 6.48, 5.56))
B.loft_y("proof", rect(-9.20, 1.44, 3.69, 5.56), 6.47, rect(-7.09, -0.67, 3.69, 3.73), 8.27)
ent = B.box("entrance", (-7.68, 0.0, 5.51), (-0.03, 2.95, 11.10))
erim = B.loft_y("erim", rect(-7.85, 0.15, 5.50, 11.28), 2.92, rect(-7.33, -0.38, 5.54, 10.74), 3.55)
B.cut(erim, B.box("f_ent", (-7.03, 3.47, 5.6), (-0.68, 3.7, 10.44)))

SOLIDS = [((-11.72, 0, -9.82), (3.84, 15.09, 3.75)), ((-9.2, 0, 3.69), (1.45, 6.48, 5.56)),
          ((-7.68, 0, 5.51), (-0.03, 3.01, 11.1))]


def hidden(o):
    p = np.array(o["center"]) + np.array(o["normal"]) * 0.15
    return any(np.all(p > np.array(lo) + 0.02) and np.all(p < np.array(hi) - 0.02) for lo, hi in SOLIDS)


def owner(o):
    x, y, z = o["center"]
    if z > 5.5 and y < 3.0:
        return ent
    if z > 3.7 and y < 6.5:
        return porch
    return main


for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    if hidden(o) or abs(o["normal"][1]) > 0.3:
        continue
    B.recess(owner(o), o, 0.2 if o["h"] > 0.6 else 0.12)
    if o["h"] > 1.5:
        B.sill(f"sill{k}", o, proud=0.1, thick=0.07, overhang=0.06)

# the painted door (decal_door.json: cad_building.py decal s_main_rightwing 2 0.36 0.52 0.64 1.0, frame included): 15 cm recess
for o in json.load(open(D / "decal_door.json"))["rects"]:
    B.recess(ent, o, 0.15, grow=-0.12)

print(B.dump())
