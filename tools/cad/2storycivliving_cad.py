#!/usr/bin/env python3
"""CAD rebuild of the two-storey civilian block (appearance 2storycivliving), in the original's frame.

    D=~/craft/solid/mc2/buildings/2storycivliving
    python3 -I tools/art/cad_building.py openings 2storycivliving > $D/openings.json
    python3 -I tools/art/cad_building.py decal 2storycivliving 0 0.201 0.121 0.312 0.279 > $D/decal_hatch.json
    python3 -I tools/cad/2storycivliving_cad.py $D > $D/2storycivliving.json
    solidcraft-cli run $D/2storycivliving.json --out $D/2storycivliving.obj
    python3 -I tools/art/cad_building.py bake 2storycivliving $D/2storycivliving.obj

Measured from game/assets/objects/2storycivliving.glb: a two-storey block (x -2.92..2.92, z -5.82..1.97, to 5.27 m)
under a 28 cm roof slab overhanging 53 cm on the sides and 44/156 cm at the ends (x -3.45..3.45, z -7.38..2.41);
a one-storey annex (x 0..2.92, z -10.12..-5.82, to 2.51 m) under a 26 cm canopy that runs the block's full
width out to z -10.85, an open porch on the -x half. Relief: every cut-out window is a 15 cm recess with a sill;
a 15 cm string course rings the block at the canopy line (2.51 m); the slab has a 15 cm parapet set 5 cm in from its edge; the painted
square on the main roof is a 25 cm hatch curb with a vent box on its inner square, the one on the canopy a
12 cm skylight curb; two slim posts
carry the porch corner. The door painted on the block's -z end sits inside the annex, so it stays painted.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, box_edges  # noqa: E402

D = Path(sys.argv[1])
B = Builder()
MX, MZ0, MZ1, MH = 2.92, -5.82, 1.97, 5.27
main = B.box("main", (-MX, 0.0, MZ0), (MX, MH, MZ1), chamfer=0.03,
             chamfer_edges=box_edges((-MX, 0.0, MZ0), (MX, MH, MZ1), "vertical"))
annex = B.box("annex", (0.0, 0.0, -10.12), (MX, 2.51, MZ0))
B.box("slab", (-3.45, MH, -7.38), (3.45, 5.55, 2.41))
B.box("canopy", (-MX, 2.51, -10.85), (MX, 2.77, MZ0 + 0.02))

# windows: 15 cm recesses with sills; skip the block's -z end behind the annex
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    c, n = o["center"], o["normal"]
    in_annex = c[2] < MZ0 - 0.05 or (abs(c[0]) < 0.05 and c[2] < MZ0) or (c[0] > 2.9 and c[2] < MZ0)
    if abs(c[2] - MZ0) < 0.02 and c[0] > 0 and c[1] < 2.51:
        continue  # behind the annex
    tgt = annex if in_annex else main
    B.recess(tgt, o, 0.15)
    B.sill(f"sill{k}", o, proud=0.08, thick=0.06, overhang=0.06)

# string course at the canopy line, around the block's exposed walls
SC0, SC1, P = 2.51, 2.66, 0.06
B.box("course_px", (MX - 0.01, SC0, MZ0), (MX + P, SC1, MZ1 + P))
B.box("course_nx", (-MX - P, SC0, MZ0), (-MX + 0.01, SC1, MZ1 + P))
B.box("course_pz", (-MX, SC0, MZ1 - 0.01), (MX, SC1, MZ1 + P))

# parapet on the roof slab, 5 cm in from its edge (a face flush with the fascia would copy the roof's edge as streaks)
T, PH, E = 0.15, 5.55 + 0.15, 0.05
X0, X1, Z0, Z1 = -3.45 + E, 3.45 - E, -7.38 + E, 2.41 - E
for k, (lo, hi) in enumerate((((X0, 5.55, Z0), (X1, PH, Z0 + T)), ((X0, 5.55, Z1 - T), (X1, PH, Z1)),
                              ((X0, 5.55, Z0 + T), (X0 + T, PH, Z1 - T)), ((X1 - T, 5.55, Z0 + T), (X1, PH, Z1 - T)))):
    B.box(f"parapet{k}", lo, hi)

# plant room on the main roof, skylight on the canopy (the painted squares)
for o in json.load(open(D / "decal_hatch.json"))["rects"]:
    c = np.array(o["center"])
    hw, hd = o["w"] / 2 - 0.05, o["h"] / 2 - 0.05
    if c[1] > 5:  # a low hatch curb; its top takes the painted square, the vent its inner square
        B.box("plantroom", (c[0] - hw, 5.55, c[2] - hd), (c[0] + hw, 5.8, c[2] + hd), chamfer=0.04)
        B.box("vent", (c[0] - 0.33, 5.8, c[2] - 0.38), (c[0] + 0.33, 6.0, c[2] + 0.38), chamfer=0.03)
    else:
        B.box("skylight", (c[0] - hw, 2.77, c[2] - hd), (c[0] + hw, 2.89, c[2] + hd), chamfer=0.03)

# porch posts under the canopy's open corner
for k, z in enumerate((-10.7, -8.3)):
    B.box(f"post{k}@8c8a84", (-MX + 0.03, 0.0, z - 0.08), (-MX + 0.19, 2.52, z + 0.08))

print(B.dump())
