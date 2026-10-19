#!/usr/bin/env python3
"""CAD rebuild of the gate control building (appearance s_gatecontrol), in the original's frame.

    D=~/craft/solid/mc2/buildings/s_gatecontrol
    python3 -I tools/art/cad_building.py openings s_gatecontrol > $D/openings.json
    python3 -I tools/cad/s_gatecontrol_cad.py $D > $D/s_gatecontrol.json
    solidcraft-cli run $D/s_gatecontrol.json --out $D/s_gatecontrol.obj
    python3 -I tools/art/cad_building.py bake s_gatecontrol $D/s_gatecontrol.obj --keep Base Base01 LOS_Antennae

Measured from game/assets/objects/s_gatecontrol.glb (faces grouped by plane): a tower (x -9.35..-3.00,
z -7.39..-1.30, to 10.37 m) under an overhanging control-room cap (x -10.19..-2.19, z -9.38..0.63, a vertical
parapet to 12.05 m, then a glazed frustum to the 14.01 m roof); an antenna plinth frustum on the roof; a wing on +x
(x -3..12): a ground floor whose front and back walls are recessed 1.3 m between three piers (z -9.04..0.80, the
walls at -8.09 and -0.53), a 1.17 m slab overhanging it (z -9.81..1.81, to 5.62 m) and a glazed upper bar
(z -7.37..-3.75, to 7.31 m). The dish (Base, Base01) and the antenna masts are kept verbatim. Relief: every cut-out
window is a recess (15 cm in the cap's sloped glazing, 20 cm elsewhere, sills under the upper bar's), the painted
roof fields are 10 cm recesses inside their light rims (split by the painted divider over the middle pier), the
slab and cap carry chamfered top edges, a ledge rings the tower under the cap.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, box_edges  # noqa: E402

D = Path(sys.argv[1])
B = Builder()


def field(target, x0, x1, z0, z1, y, rim, depth=0.1):
    B.cut(target, B.box(f"f_{target}_{x0:.1f}_{z0:.1f}", (x0 + rim, y - depth, z0 + rim), (x1 - rim, y + 0.2, z1 - rim)))


# ---- tower and control-room cap
tower = B.box("tower", (-9.35, 0.0, -7.39), (-3.00, 10.37, -1.30))
cap = B.box("cap", (-10.19, 10.37, -9.38), (-2.19, 12.05, 0.63), chamfer=0.04)
glaze = B.loft_y("glaze", [(-10.19, -9.38), (-2.19, -9.38), (-2.19, 0.63), (-10.19, 0.63)], 12.05,
                 [(-8.96, -7.39), (-3.41, -7.39), (-3.41, -1.36), (-8.96, -1.36)], 14.01)
field(glaze, -8.96, -3.41, -7.39, -1.36, 14.01, 0.3)
for k, (lo, hi) in enumerate([((-9.47, 10.05, -7.51), (-2.88, 10.37, -1.18))]):
    B.box(f"ledge{k}", lo, hi)
B.loft_y("plinth", [(-8.49, -6.87), (-6.54, -6.87), (-6.54, -4.76), (-8.49, -4.76)], 14.01,
         [(-8.20, -6.45), (-6.84, -6.45), (-6.84, -5.18), (-8.20, -5.18)], 15.17)

# ---- wing: recessed ground floor between piers, slab, upper bar
core = B.box("core", (-3.0, 0.0, -8.09), (12.0, 4.45, -0.53))
for k, (x0, x1) in enumerate([(-3.0, -2.02), (3.97, 5.04), (10.88, 12.0)]):
    B.box(f"pier_f{k}", (x0, 0.0, -0.53), (x1, 4.45, 0.80))
    B.box(f"pier_b{k}", (x0, 0.0, -9.04), (x1, 4.45, -8.09))
slab = B.box("slab", (-3.0, 4.45, -9.81), (12.0, 5.62, 1.81), chamfer=0.05,
             chamfer_edges=[(4.5, 5.62, -9.81), (4.5, 5.62, 1.81), (12.0, 5.62, -4.0)])
bar = B.box("bar", (-3.0, 5.62, -7.37), (12.0, 7.31, -3.75), chamfer=0.04,
            chamfer_edges=[(4.5, 7.31, -7.37), (4.5, 7.31, -3.75), (12.0, 7.31, -5.56)])
for x0, x1 in ((-3.0, 4.5), (4.5, 12.0)):
    field(slab, x0, x1, -3.75, 1.81, 5.62, 0.45)
    field(slab, x0, x1, -9.81, -7.37, 5.62, 0.45)
    field(bar, x0, x1, -7.37, -3.75, 7.31, 0.4)

# ---- windows
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    c, n = o["center"], o["normal"]
    if abs(c[0] + 3.0) < 0.05 and n[0] < -0.5:
        continue  # behind the tower
    if c[1] > 12:
        B.recess(glaze, o, 0.15)
    elif c[1] > 5.6:
        B.recess(bar, o, 0.2)
        B.sill(f"sill{k}", o, proud=0.1, thick=0.07, overhang=0.06)
    else:
        B.recess(core, o, 0.2)

print(B.dump())
