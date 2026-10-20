#!/usr/bin/env python3
"""CAD rebuild of the administration wing (appearance s_admin_wing), in the original's frame.

    D=~/craft/solid/mc2/buildings/s_admin_wing
    python3 -I tools/art/cad_building.py openings s_admin_wing > $D/openings.json
    python3 -I tools/cad/s_admin_wing_cad.py $D > $D/s_admin_wing.json
    solidcraft-cli run $D/s_admin_wing.json --out $D/s_admin_wing.obj
    python3 -I tools/art/cad_building.py bake s_admin_wing $D/s_admin_wing.obj --glass 182,190,198   # the original's lit (white) windows

Measured from game/assets/objects/s_admin_wing.glb (faces grouped by plane): a long block, plinth
(0..0.43 m) and roof slab (5.94..6.37 m) over x -5.70..5.70 by z -22.05..31.40, walls 0.3 m inside it
(x +-5.35, z -21.75..31.10); a gabled skylight along z (x +-3.72, z -7.48..17.06, 6.32..8.29 m).
Relief: plinth and slab with chamfered top edges, a 6 cm roof field inside a 0.35 m rim, a kerb and ridge on
the skylight, glazing bars across it, every cut-out window a recess with a sill.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, box_edges  # noqa: E402

D = Path(sys.argv[1])
B = Builder()
X0, X1, Z0, Z1 = -5.70, 5.70, -22.05, 31.40

plinth = B.box("plinth", (X0, 0.0, Z0), (X1, 0.43, Z1), chamfer=0.05)
walls = B.box("walls", (-5.35, 0.43, -21.75), (5.35, 5.94, 31.10))
roof = B.box("roof", (X0, 5.94, Z0), (X1, 6.37, Z1), chamfer=0.05)
B.cut(roof, B.box("field", (X0 + 0.35, 6.31, Z0 + 0.35), (X1 - 0.35, 6.6, Z1 - 0.35)))
B.box("kerb", (-3.87, 6.25, -7.63), (3.87, 6.45, 17.21), chamfer=0.03)
B.prism_z("skylight", [(-3.72, 6.45), (3.72, 6.45), (0.0, 8.29)], -7.48, 17.06)
B.box("ridge@50545a", (-0.09, 8.20, -7.56), (0.09, 8.36, 17.14))
# glazing bars down each slope between the eight painted panes (a dark frame colour)
for k in range(9):
    z = -7.48 + 0.06 + k * (17.06 - -7.48 - 0.12) / 8
    for s, nm in ((1, "r"), (-1, "l")):
        # a thin rafter on top of each slope: a quad prism hugging the slope 4 cm proud
        B.prism_z(f"raf{k}{nm}@50545a", [(0.0, 8.29), (s * 3.72, 6.45), (s * 3.76, 6.49), (0.0, 8.34)][::s], z - 0.05, z + 0.05)

for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    if abs(o["normal"][1]) > 0.5 or not (0.43 < o["center"][1] < 5.94):
        continue
    B.recess(walls, o, 0.15)
    B.sill(f"sill{k}", o, proud=0.10, thick=0.06, overhang=0.05)

print(B.dump())
