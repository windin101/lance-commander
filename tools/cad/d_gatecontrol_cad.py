#!/usr/bin/env python3
"""CAD rebuild of the desert gate control building (appearance d_gatecontrol), in the original's frame.

    D=~/craft/solid/mc2/buildings/d_gatecontrol
    python3 -I tools/art/cad_building.py openings d_gatecontrol > $D/openings.json
    python3 -I tools/cad/d_gatecontrol_cad.py $D > $D/d_gatecontrol.json
    solidcraft-cli run $D/d_gatecontrol.json --out $D/d_gatecontrol.obj
    python3 -I tools/art/cad_building.py bake d_gatecontrol $D/d_gatecontrol.obj --keep Dish

Measured from game/assets/objects/d_gatecontrol.glb (faces grouped by plane): a two-bay hall (x -2.83..12.05)
of one cross-section: back wall z -0.61 to 5.22 m, a slope to the 7.36 m roof (z -4.05..-9.29), a slope down to
the 4.39 m fascia at z -11.32 that overhangs the front wall (z -9.31) above 2.58 m; three portal frames
(x -2.83..-2.00, 4.09..4.95, 11.13..12.05) whose legs spread to z 2.82 at the back and z -10.88 under the front
overhang (the middle one only at the back); a low west annex (walls x -11.55..-2.83, z -7.22..-2.00, 2.62 m) under
an overhanging roof slab (x -12.05.., z -7.58..-1.64, 3.28 m); a control cab on the first bay: a frustum
(7.36..9.92 m) under an overhanging box (x -2.38..4.47, z -9.62..-3.72, to 11.37 m) with chamfered window slopes
to the 13.16 m roof; on it the dish mount (a true cone, 20 sides, where the original has a pyramid; the Dish is
kept verbatim) and the mast (LOS_antenna, a true cone, 20 sides). Relief: the portal frames run over the roof as
8 cm raised ribs, every cut-out window is a 20 cm recess (doors 25 cm) with a sill under the wall ones, the cab
and annex roofs have 8 cm fields inside their rims.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
B = Builder()


def ngon(cx, cz, r, n=20):
    return [(cx + r * math.cos(2 * math.pi * i / n), cz + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


# ---- the hall: one cross-section (z, y) along x
PROF = [(-9.31, 0.0), (-0.61, 0.0), (-0.61, 5.22), (-4.05, 7.36), (-9.29, 7.36), (-11.32, 4.39), (-11.32, 2.58),
        (-9.31, 2.58)]
hall = B.prism_x("hall", PROF, -2.83, 12.05)
# portal frames: legs and a raised rib over the roof (the roof outline pushed out 8 cm)
RIB = [(-0.61, 2.6), (-0.53, 2.6), (-0.53, 5.26), (-4.03, 7.44), (-9.33, 7.44), (-11.40, 4.41), (-11.40, 2.6)]
for k, (x0, x1) in enumerate([(-2.83, -2.00), (4.09, 4.95), (11.13, 12.05)]):
    B.prism_x(f"leg_b{k}", [(-0.65, 0.0), (2.82, 0.0), (-0.65, 4.36)], x0, x1)
    if k != 1:
        B.prism_x(f"leg_f{k}", [(-10.88, 0.0), (-9.27, 0.0), (-9.27, 2.58)], x0, x1)
    B.prism_x(f"rib{k}", RIB + [(-11.24, 2.6), (-11.24, 4.37), (-9.25, 7.30), (-4.07, 7.30), (-0.69, 5.18), (-0.69, 2.6)],
              x0 - 0.02 if k else x0, x1 + 0.02 if k != 2 else x1)

# ---- west annex
annex = B.box("annex", (-11.55, 0.0, -7.22), (-2.83, 2.62, -2.00))
aroof = B.box("annex_roof", (-12.05, 2.61, -7.58), (-2.83, 3.28, -1.64), chamfer=0.04)
B.cut(aroof, B.box("annex_field", (-11.80, 3.20, -7.33), (-3.05, 3.40, -1.89)))

# ---- control cab
B.loft_y("cab_base", [(-2.00, -9.29), (4.09, -9.29), (4.09, -4.05), (-2.00, -4.05)], 7.30,
         [(-1.61, -8.95), (3.69, -8.95), (3.69, -4.39), (-1.61, -4.39)], 9.92)
cab = B.box("cab", (-2.38, 9.92, -9.62), (4.47, 11.37, -3.72))
top = B.loft_y("cab_top", [(-2.38, -9.62), (4.47, -9.62), (4.47, -3.72), (-2.38, -3.72)], 11.37,
               [(-1.53, -8.88), (3.61, -8.88), (3.61, -4.46), (-1.53, -4.46)], 13.16)
B.cut(top, B.box("cab_field", (-1.25, 13.08, -8.60), (3.33, 13.30, -4.74)))
B.box("cab_ledge", (-2.46, 11.30, -9.70), (4.55, 11.44, -3.64))
B.loft_y("dish_mount", ngon(1.82, -7.44, 0.42), 13.08, ngon(1.82, -7.44, 0.06), 13.98)
B.loft_y("mast", ngon(0.16, -5.95, 0.10), 13.08, ngon(0.16, -5.95, 0.025), 20.83)

# ---- windows
k = 0
for o in json.load(open(D / "openings.json"))["openings"]:
    x, y, z = o["center"]
    if abs(x + 2.83) < 0.05 and y < 2.62 and abs(z + 4.61) < 2.61 + o["w"] / 2:
        continue  # behind the annex
    if y > 11.3:
        tgt = top
    elif x < -2.84:
        tgt = annex
    else:
        tgt = hall
    door = o["h"] > 1.5
    B.recess(tgt, o, 0.25 if door else 0.2)
    if abs(o["normal"][1]) < 0.1 and y < 3 and o["w"] > 0.5:
        B.sill(f"sill{k}", o, proud=0.1, thick=0.07, overhang=0.06)
    k += 1

print(B.dump())
