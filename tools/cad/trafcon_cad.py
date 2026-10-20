#!/usr/bin/env python3
"""CAD rebuild of the traffic-control tower (appearance trafcon), in the original's frame.

    D=~/craft/solid/mc2/buildings/trafcon
    python3 -I tools/art/cad_building.py openings trafcon > $D/openings.json
    python3 -I tools/cad/trafcon_cad.py $D > $D/trafcon.json
    solidcraft-cli run $D/trafcon.json --out $D/trafcon.obj
    python3 -I tools/art/cad_building.py bake trafcon $D/trafcon.obj --keep RotatyBit

Measured from game/assets/objects/trafcon.glb (faces grouped by plane): a core (x -5.62..3.86) whose section rises
from a 19.9 m foot (z -11.97..7.94) with its front sloping back from 6.32 m to z -4.39 at 18.33 m and its back
stepping in to z 4.78 by 6.32 m, to 23.11 m; a buttress wing on +x (z -3.44..0.99, to x 10.49, its top sloping
from 13.8 m to 20.43 m); a glazed bay hung on the back (x -2.46..6.07, z 0.99..7.94, 16.32..20.43 m, its top
edge chamfered); a low annex on -x (x -12.76..-5.6, z -6.13..3.87, 5.6 m); the control cab, a frustum flaring
from the core top to x -8.01..6.21, z -6.76..7.15 at 28.64 m under a low pyramid roof (apex 30.06 m at x -0.9,
z 0.35). The searchlight (RotatyBit) is kept verbatim. Relief: every cut-out window a 25 cm recess with a sill
(the cab's eight cut-out panes 30 cm deep, panes at the back), a ledge round the core at the cab's foot, roof
fascias round the cab roof, parapets on the annex and the bay/wing roof, a plinth band.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, box_edges  # noqa: E402

D = Path(sys.argv[1])
B = Builder()

core = B.prism_x("core", [(-11.97, 0.0), (7.94, 0.0), (7.94, 3.79), (4.78, 6.32), (4.78, 23.11), (-4.39, 23.11),
                          (-4.39, 18.33), (-11.97, 6.32)], -5.62, 3.86)
wing = B.prism_z("wing", [(3.8, 0.0), (10.49, 0.0), (10.49, 13.8), (6.07, 20.43), (3.8, 20.43)], -3.44, 0.99)
bay = B.prism_x("bay", [(0.95, 16.32), (7.94, 16.32), (7.94, 18.54), (6.04, 20.43), (0.95, 20.43)], -2.46, 6.07)
B.join(core, [wing, bay])
annex = B.box("annex", (-12.76, 0.0, -6.13), (-5.58, 5.6, 3.87))
cab = B.loft_y("cab", [(-5.62, -4.39), (3.86, -4.39), (3.86, 4.78), (-5.62, 4.78)], 23.11,
               [(-8.01, -6.76), (6.21, -6.76), (6.21, 7.15), (-8.01, 7.15)], 28.64)
roof = B.loft_y("roof", [(-8.01, -6.76), (6.21, -6.76), (6.21, 7.15), (-8.01, 7.15)], 28.64,
                [(-0.95, 0.3), (-0.85, 0.3), (-0.85, 0.4), (-0.95, 0.4)], 30.06)

k = 0
for o in json.load(open(D / "openings.json"))["openings"]:
    n = np.array(o["normal"])
    c = np.array(o["center"])
    if n[1] < -0.2:  # cab glazing
        B.recess(cab, o, 0.3)
        continue
    tgt = annex if c[0] < -5.7 else core
    B.recess(tgt, o, 0.25)
    if abs(n[1]) < 0.1:
        B.sill(f"sill{k}", o, proud=0.12, thick=0.08, overhang=0.1)
    k += 1

# ledge round the core at the cab's foot, plinth band round the core foot
B.box("ledge_mz@avg", (-5.82, 22.81, -4.59), (4.06, 23.11, -4.38))
B.box("ledge_pz@avg", (-5.82, 22.81, 4.77), (4.06, 23.11, 4.98))
B.box("ledge_mx@avg", (-5.82, 22.81, -4.38), (-5.61, 23.11, 4.77))
B.box("ledge_px@avg", (3.85, 22.81, -4.38), (4.06, 23.11, 4.77))
# fascia round the cab roof edge
F, T = 0.22, 0.3
for i, (lo, hi) in enumerate((((-8.01 - F, 28.5, -6.76 - F), (6.21 + F, 28.5 + T, -6.76 + 0.02)),
                              ((-8.01 - F, 28.5, 7.15 - 0.02), (6.21 + F, 28.5 + T, 7.15 + F)),
                              ((-8.01 - F, 28.5, -6.74), (-8.01 + 0.02, 28.5 + T, 7.13)),
                              ((6.21 - 0.02, 28.5, -6.74), (6.21 + F, 28.5 + T, 7.13)))):
    B.box(f"fascia{i}@avg", lo, hi)


def parapet(name, x0, z0, x1, z1, y, h=0.45, t=0.18, inset=0.04):
    a0, a1, b0, b1 = x0 + inset, x1 - inset, z0 + inset, z1 - inset
    for i, (lo, hi) in enumerate((((a0, y, b0), (a1, y + h, b0 + t)), ((a0, y, b1 - t), (a1, y + h, b1)),
                                  ((a0, y, b0 + t), (a0 + t, y + h, b1 - t)), ((a1 - t, y, b0 + t), (a1, y + h, b1 - t)))):
        B.box(f"{name}{i}", lo, hi)


parapet("annexpar", -12.76, -6.13, -5.62, 3.87, 5.6)
# bay + wing roof at 20.43: an L round the core's corner (x 3.86..6.07 over the wing, z 4.78..6.04 behind)
B.box("baypar0", (-2.42, 20.43, 5.86), (6.03, 20.83, 6.04))
B.box("baypar1", (5.85, 20.43, -3.4), (6.03, 20.83, 5.86))
B.box("baypar2", (3.86, 20.43, -3.4), (5.85, 20.83, -3.22))
B.box("baypar3", (-2.42, 20.43, 4.78), (-2.24, 20.83, 5.86))
# plinth
P = 0.06
for i, (lo, hi) in enumerate((((-5.62 - P, 0, -11.97 - P), (3.86 + P, 0.4, -11.95)), ((-5.62 - P, 0, 7.92), (3.86 + P, 0.4, 7.94 + P)),
                              ((-5.62 - P, 0, -11.95), (-5.6, 0.4, 7.92)), ((3.84, 0, -11.95), (3.86 + P, 0.4, -3.44)),
                              ((3.84, 0, 0.99), (3.86 + P, 0.4, 7.92)), ((10.47, 0, -3.44 - P), (10.49 + P, 0.4, 0.99 + P)))):
    B.box(f"plinth{i}@avg", lo, hi)
print(B.dump())
