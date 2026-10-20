#!/usr/bin/env python3
"""CAD rebuild of the government hall's centre block (appearance s_main), in the original's frame.

    D=~/craft/solid/mc2/buildings/s_main
    python3 -I tools/art/cad_building.py openings s_main > $D/openings.json
    (openings and decal were run with cad_building.CELL = 0.06 m (0.04 for decal), set from a wrapper: the 2 cm
    default ran past a 6 GB cap on these big glazed walls, as query_pairs grows with the square of the density)
    python3 -I tools/cad/s_main_cad.py $D > $D/s_main.json
    solidcraft-cli run $D/s_main.json --out $D/s_main.obj
    python3 -I tools/art/cad_building.py bake s_main $D/s_main.obj

Measured from game/assets/objects/s_main.glb (faces grouped by plane): the hall (x -21.28..21.23, z -11.00..5.41,
20.34 m, a paved roof terrace), an upper storey (x -18.59..17.88, z -9.31..2.32, to 24.73 m), a clerestory
(x -15.97..15.19, z -8.00..1.00, to 26.08 m) under a low hipped roof (eaves x -16.31..15.52, z -8.37..1.36; ridge
x -13.49..12.71 at z -3.50, 26.88 m). In front, a two-storey wing: arcaded ground floor (x -18.38..18.33,
z 5.20..13.07, 7.77 m) under a cove that flares out to a ledge at 9.27 m (x +-19.5, to z 14.31), the upper floor
(x -19.17..19.12, to z 13.92, 16.58 m) under a sloped roof edge, a parapet (to 18.27 m) and a capped flat roof at
18.95 m. On the axis a faceted portico (half octagon to z 20.29, 7.77 m, cove to 9.27 m) with the entrance passage
(x +-3.37, from z 14.12) cut into it, the emblem bay above (x -3.51..3.48, to z 21.05, 16.58 m, same roof edge and
parapet) and a balcony slab (x -3.92..3.84, z 20.34..24.09, 9.25..11.11 m). Relief: every cut-out window is a
recess (20 cm, sills under the tall ones), the hall carries a cornice ledge (flat colour, @avg: sampled, it smeared the vent row behind it) under its terrace, the upper storey a
string course, the clerestory roof a ridge cap, the balcony a chamfered top edge.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, box_edges  # noqa: E402

D = Path(sys.argv[1])
B = Builder()


def rect(x0, x1, z0, z1):
    return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]


hall = B.box("hall", (-21.28, 0.0, -11.00), (21.23, 20.34, 5.41))
B.box("cornice@avg", (-21.40, 19.55, -11.12), (21.35, 19.80, 5.30))
upper = B.box("upper", (-18.59, 20.30, -9.31), (17.88, 24.73, 2.32))
B.box("course@avg", (-18.69, 23.95, -9.41), (17.98, 24.10, 2.42))
clere = B.box("clere", (-15.97, 24.70, -8.00), (15.19, 26.08, 1.00))
B.loft_y("croof", rect(-16.31, 15.52, -8.37, 1.36), 26.07, rect(-13.49, 12.71, -3.52, -3.48), 26.88)
B.box("ridge", (-13.59, 26.83, -3.60), (12.81, 26.98, -3.40))

# front wing
wlow = B.box("wing_low", (-18.38, 0.0, 5.20), (18.33, 7.77, 13.07))
B.loft_y("wcove", rect(-18.93, 18.88, 5.20, 13.65), 7.76, rect(-19.53, 19.48, 5.20, 14.31), 9.27)
wup = B.box("wing_up", (-19.17, 9.25, 5.20), (19.12, 16.58, 13.92))
B.loft_y("wedge", rect(-19.51, 19.46, 5.20, 14.29), 16.57, rect(-18.17, 18.12, 5.20, 12.84), 17.22)
B.box("wpara", (-18.17, 17.20, 5.20), (18.12, 18.27, 12.84))
B.loft_y("wcap", rect(-18.30, 18.25, 5.20, 12.98), 18.26, rect(-17.74, 17.69, 5.20, 12.38), 18.95)

# portico: half octagon with the entrance passage
wall = [(-10.73, 12.97), (-9.72, 16.65), (-7.02, 19.33), (-3.34, 20.29), (3.34, 20.29), (7.02, 19.33),
        (9.72, 16.65), (10.73, 12.97)]
cove0 = [(-11.31, 12.97), (-10.23, 16.94), (-7.31, 19.84), (-3.34, 20.88), (3.34, 20.88), (7.31, 19.84),
         (10.23, 16.94), (11.31, 12.97)]
cove1 = [(-11.97, 12.97), (-10.80, 17.27), (-7.64, 20.40), (-3.34, 21.53), (3.34, 21.53), (7.64, 20.40),
         (10.80, 17.27), (11.97, 12.97)]
port = B.prism_y("portico", wall, 0.0, 7.77)
B.cut(port, B.box("passage", (-3.37, -0.1, 14.12), (3.36, 7.77, 20.6)))
B.loft_y("pcove", cove0, 7.72, cove1, 9.27)
# emblem bay
bay = B.box("bay", (-3.51, 9.25, 11.94), (3.48, 16.58, 21.05))
B.loft_y("bedge", rect(-3.88, 3.85, 11.94, 21.42), 16.57, rect(-2.43, 2.40, 11.94, 19.97), 17.22)
B.box("bpara", (-2.43, 17.20, 11.94), (2.40, 18.27, 19.97))
B.loft_y("bcap", rect(-2.57, 2.55, 11.94, 20.11), 18.26, rect(-1.98, 1.95, 11.94, 19.51), 18.95)
B.box("balcony", (-3.92, 9.25, 20.34), (3.84, 11.11, 24.09), chamfer=0.06,
      chamfer_edges=[(-0.04, 11.11, 24.09), (-3.92, 11.11, 22.2), (3.84, 11.11, 22.2)])

SOLIDS = [((-21.28, 0, -11), (21.23, 20.34, 5.41)), ((-18.38, 0, 5.2), (18.33, 7.77, 13.07)),
          ((-19.17, 9.27, 5.2), (19.12, 16.58, 13.92)), ((-3.51, 9.27, 11.94), (3.48, 16.58, 21.05)),
          ((-18.59, 20.3, -9.31), (17.88, 24.73, 2.32))]


def hidden(o):
    p = np.array(o["center"]) + np.array(o["normal"]) * 0.15
    return any(np.all(p > np.array(lo) + 0.02) and np.all(p < np.array(hi) - 0.02) for lo, hi in SOLIDS)


def owner(o):
    x, y, z = o["center"]
    if y > 24.2:
        return clere
    if y > 20.3:
        return upper
    if z < 5.3:
        return hall
    if y > 9.2:
        return bay if abs(x) < 3.6 and z > 13.9 else wup
    if z > 13.0 and abs(x) < 11.5:
        return port
    return wlow


for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    if hidden(o) or abs(o["normal"][1]) > 0.3:
        continue
    B.recess(owner(o), o, 0.2 if o["h"] > 0.6 else 0.12)
    if o["h"] > 1.5:
        B.sill(f"sill{k}", o, proud=0.1, thick=0.07, overhang=0.06)

print(B.dump())
