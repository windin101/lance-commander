#!/usr/bin/env python3
"""CAD rebuild of the government hall's left wing (appearance s_main_leftwing), in the original's frame.

    D=~/craft/solid/mc2/buildings/s_main_leftwing
    python3 -I tools/art/cad_building.py openings s_main_leftwing > $D/openings.json
    (openings and decal were run with cad_building.CELL = 0.06 m (0.04 for decal), set from a wrapper: the 2 cm
    default ran past a 6 GB cap on these big glazed walls, as query_pairs grows with the square of the density)
    python3 -I tools/art/cad_building.py decal s_main_leftwing 2 0.36 0.52 0.64 1.0 > $D/decal_door.json
    python3 -I tools/cad/s_main_leftwing_cad.py $D > $D/s_main_leftwing.json
    solidcraft-cli run $D/s_main_leftwing.json --out $D/s_main_leftwing.obj
    python3 -I tools/art/cad_building.py bake s_main_leftwing $D/s_main_leftwing.obj

Measured from game/assets/objects/s_main_leftwing.glb (faces grouped by plane): a hall (x -5.72..10.04,
z -10.48..4.01, 9.47 m) under a chamfered roof rim (-5.90..10.22 at 9.38 m in to -5.35..9.67 at 10.01 m), an
attic (x -4.41..8.51, z -7.68..1.22) to 13.49 m under a hipped roof (eaves x -4.71..8.90, z -8.07..1.60; ridge
x -0.38..4.92 at z -3.23, 16.03 m), and a long low gallery to the east (x 9.97..37.91, z -7.22..0.74, 4.46 m)
with its own chamfered rim to 5.00 m. Relief: every cut-out window is a recess (20 cm, sills under the tall
ones), the hall and gallery roofs' flat fields are 8 cm recesses inside the rims, a cornice ledge (flat colour, @avg: sampled, it smeared the vent row behind it) rings the
hall under its rim and the attic under its eaves, a ridge cap tops the hipped roof.
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


hall = B.box("hall", (-5.72, 0.0, -10.48), (10.04, 9.40, 4.01))
rim = B.loft_y("rim", rect(-5.90, 10.22, -10.66, 4.19), 9.38, rect(-5.35, 9.67, -10.12, 3.65), 10.01)
B.cut(rim, B.box("f_hall", (-5.05, 9.93, -9.82), (9.37, 10.2, 3.35)))
B.box("ledge_h@avg", (-5.82, 8.55, -10.58), (10.14, 8.75, 4.11))
attic = B.box("attic", (-4.41, 9.90, -7.68), (8.51, 13.53, 1.22))
B.box("ledge_a@avg", (-4.51, 12.95, -7.78), (8.61, 13.10, 1.32))
# hipped roof: a loft from the eaves to a 4 cm ridge bar
B.loft_y("roof", rect(-4.71, 8.90, -8.07, 1.60), 13.49, rect(-0.38, 4.92, -3.25, -3.21), 16.03)
B.box("ridge", (-0.48, 15.98, -3.33), (5.02, 16.13, -3.13))

gal = B.box("gallery", (9.97, 0.0, -7.22), (37.91, 4.40, 0.74))
grim = B.loft_y("grim", [(9.94, -7.40), (38.09, -7.40), (38.09, 0.92), (9.94, 0.92)], 4.37,
                [(9.97, -6.86), (37.55, -6.86), (37.55, 0.38), (9.97, 0.38)], 5.00)
B.cut(grim, B.box("f_gal", (10.3, 4.92, -6.56), (37.25, 5.2, 0.08)))
B.box("ledge_g@avg", (10.04, 3.70, -7.32), (38.01, 3.88, 0.84))

SOLIDS = [((-5.72, 0, -10.48), (10.04, 9.47, 4.01)), ((9.97, 0, -7.22), (37.91, 4.46, 0.74)),
          ((-4.41, 9.4, -7.68), (8.51, 13.53, 1.22))]


def hidden(o):
    p = np.array(o["center"]) + np.array(o["normal"]) * 0.15
    return any(np.all(p > np.array(lo) + 0.02) and np.all(p < np.array(hi) - 0.02) for lo, hi in SOLIDS)


def owner(o):
    x, y, z = o["center"]
    if y > 9.47:
        return attic
    if x > 10.02:
        return gal
    return hall


for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    if hidden(o) or abs(o["normal"][1]) > 0.3:
        continue
    B.recess(owner(o), o, 0.2 if o["h"] > 0.6 else 0.12)
    if o["h"] > 1.5:
        B.sill(f"sill{k}", o, proud=0.1, thick=0.07, overhang=0.06)

# the painted door (decal_door.json: cad_building.py decal s_main_leftwing 2 0.36 0.52 0.64 1.0, frame included): 15 cm recess
for o in json.load(open(D / "decal_door.json"))["rects"]:
    B.recess(gal, o, 0.15, grow=-0.12)

print(B.dump())
