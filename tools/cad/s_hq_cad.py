#!/usr/bin/env python3
"""CAD rebuild of the headquarters (appearance s_hq), in the original's frame.

    D=~/craft/solid/mc2/buildings/s_hq
    python3 -I tools/art/cad_building.py openings s_hq > $D/openings.json
    python3 -I tools/cad/s_hq_cad.py $D > $D/s_hq.json
    solidcraft-cli run $D/s_hq.json --out $D/s_hq.obj
    python3 -I tools/art/cad_building.py bake s_hq $D/s_hq.obj

Measured from game/assets/objects/s_hq.glb (faces grouped by plane): a main block (x -7.87..2.02, z -12.98..10.83,
6.03 m) under a slab overhanging its long sides (x -9.00..3.01, to 7.95 m) and a glazed roof bar (x -5.31..-0.68,
z -10.13..7.85, to 9.95 m); at its -z end a low annex (x -7.87..-0.80, 6.03 m) and the tower (x -0.80..9.28,
z -19.01..-12.98, 10.82 m) with a cab flaring out to 13.31 m (x -1.60..10.09, z -20.06..-11.93) and straight to
the 16.48 m roof that carries the painted emblem; an east wing (x 2.02..9.61, z -1.93..10.83, 4.04 m) with its own
roof bar (to 5.01 m). Relief: every cut-out window is a recess (20 cm, sills under the tall ones), the roofs'
painted dark fields are 10 cm recesses inside their light rims (the bars stand in them), the slab, cab and wing
carry chamfered top edges, ledges ring the tower at the cab's foot.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
B = Builder()


def field(target, x0, x1, z0, z1, y, rim, depth=0.1):
    B.cut(target, B.box(f"f_{target}", (x0 + rim, y - depth, z0 + rim), (x1 - rim, y + 0.2, z1 - rim)))


main = B.box("main", (-7.87, 0.0, -12.98), (2.02, 6.03, 10.83))
slab = B.box("slab", (-9.00, 6.03, -12.98), (3.01, 7.95, 10.83), chamfer=0.05)
field(slab, -9.00, 3.01, -12.98, 10.83, 7.95, 0.4)
bar = B.box("bar", (-5.31, 7.85, -10.13), (-0.68, 9.95, 7.85), chamfer=0.04)
field(bar, -5.31, -0.68, -10.13, 7.85, 9.95, 0.35)
annex = B.box("annex", (-7.87, 0.0, -19.01), (-0.80, 6.03, -12.98), chamfer=0.04,
              chamfer_edges=[(-4.3, 6.03, -19.01), (-7.87, 6.03, -16.0)])
field(annex, -7.87, -0.80, -19.01, -12.98, 6.03, 0.35)
tower = B.box("tower", (-0.80, 0.0, -19.01), (9.28, 10.82, -12.98))
flare = B.loft_y("flare", [(-0.80, -19.01), (9.28, -19.01), (9.28, -12.98), (-0.80, -12.98)], 10.82,
                 [(-1.60, -20.06), (10.09, -20.06), (10.09, -11.93), (-1.60, -11.93)], 13.31)
cab = B.box("cab", (-1.60, 13.31, -20.06), (10.09, 16.48, -11.93), chamfer=0.05)
field(cab, -1.60, 10.09, -20.06, -11.93, 16.48, 0.4)
for k, (lo, hi) in enumerate([((-0.92, 10.62, -19.13), (9.40, 10.82, -18.99)), ((-0.92, 10.62, -13.00), (9.40, 10.82, -12.86)),
                              ((9.26, 10.62, -19.13), (9.40, 10.82, -12.86)), ((-0.92, 10.62, -19.13), (-0.78, 10.82, -12.86))]):
    B.box(f"ledge{k}", lo, hi)
wing = B.box("wing", (2.02, 0.0, -1.93), (9.61, 4.04, 10.83), chamfer=0.04,
             chamfer_edges=[(5.8, 4.04, -1.93), (5.8, 4.04, 10.83), (9.61, 4.04, 4.4)])
field(wing, 2.02, 9.61, -1.93, 10.83, 4.04, 0.4)
wbar = B.box("wbar", (4.39, 3.94, 0.28), (8.08, 5.01, 8.67), chamfer=0.03)
field(wbar, 4.39, 8.08, 0.28, 8.67, 5.01, 0.3, depth=0.06)

SOLIDS = [((-7.87, 0, -12.98), (2.02, 7.95, 10.83)), ((-0.80, 0, -19.01), (9.28, 10.82, -12.98)),
          ((-7.87, 0, -19.01), (-0.80, 6.03, -12.98)), ((2.02, 0, -1.93), (9.61, 4.04, 10.83))]


def hidden(o):
    p = np.array(o["center"]) + np.array(o["normal"]) * 0.15
    return any(np.all(p > np.array(lo) + 0.02) and np.all(p < np.array(hi) - 0.02) for lo, hi in SOLIDS)


def owner(o):
    x, y, z = o["center"]
    if y > 13.3:
        return cab
    if y > 10.8:
        return flare
    if z < -12.95:
        return tower if x > -0.85 else annex
    if y > 7.95:
        return bar
    if y > 6.03:
        return slab
    if x > 2.0 and z > -1.95:
        return wbar if y > 4.04 else wing
    return main


for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    if hidden(o):
        continue
    B.recess(owner(o), o, 0.2 if o["h"] > 0.6 else 0.12)
    if o["h"] > 1.5 and abs(o["normal"][1]) < 0.1:
        B.sill(f"sill{k}", o, proud=0.1, thick=0.07, overhang=0.06)

print(B.dump())
