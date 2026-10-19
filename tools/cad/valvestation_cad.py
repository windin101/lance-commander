#!/usr/bin/env python3
"""CAD rebuild of the pipeline valve station (appearance valvestation), in the original's frame.

    D=~/craft/solid/mc2/buildings/valvestation
    python3 -I tools/art/cad_building.py openings valvestation > $D/openings.json
    python3 -I tools/art/cad_building.py decal valvestation 0 0.072 0.875 0.306 1.0 > $D/decal_louvre.json
    python3 -I tools/art/cad_building.py decal valvestation 0 0.885 0.927 0.95 1.0 > $D/decal_box.json
    python3 -I tools/art/cad_building.py decal valvestation 0 0.267 0.336 0.365 0.466 > $D/decal_fan.json
    python3 -I tools/cad/valvestation_cad.py $D > $D/valvestation.json
    solidcraft-cli run $D/valvestation.json --out $D/valvestation.obj
    python3 -I tools/art/cad_building.py bake valvestation $D/valvestation.obj --glass 22,24,28

Measured from game/assets/objects/valvestation.glb: a tall block (x -2.84..4.44, z -1.54..9.74, 9.15 m) with a
row of cut-out vent slots at 7.66 m on its -z, -x and +z walls; three 0.74 m pipes leave its +x wall at 7.82 m
(z 0.41, 4.10, 7.79) and bend down onto the crown of a big horizontal main (an eight-sided section x 6.63..11.12,
y 2.05..6.38, i.e. r ~2.2 on an axis at x 8.875, y 4.215, running z -1.54..9.74) on a 2.2 m wide plinth
(x 7.77..9.98, 0..2.05 m).
Relief: the main is a true 32-sided pipe with flanges at both ends and two joint rings; the three pipes are
20-sided with collars at the wall and feet, and a mitred elbow; the vent slot rows are 20 cm recesses (baked
with --glass 22,24,28 so the slots stay black); the painted louvred doors on the -z/+z walls are 15 cm recesses with a sill; the painted cabinet on the
-x wall is a 35 cm proud box; the painted roof fan is a 25 cm raised housing; a parapet rings the roof and a 6 cm
plinth the block.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
B = Builder()
X0, X1, Z0, Z1, H = -2.841, 4.44, -1.544, 9.739, 9.15


def ngon(r, n, cx=0.0, cy=0.0):
    return [(cx + r * math.cos(2 * math.pi * (k + 0.5) / n), cy + r * math.sin(2 * math.pi * (k + 0.5) / n)) for k in range(n)]


B.box("tower", (X0, 0.0, Z0), (X1, H, Z1))
B.box("plinth", (X0 - 0.06, 0.0, Z0 - 0.06), (X1 + 0.06, 0.3, Z1 + 0.06))
# roof parapet (four bars on the roof edge)
p, ph = 0.22, 0.32
for k, (lo, hi) in enumerate([((X0, H, Z0), (X1, H + ph, Z0 + p)), ((X0, H, Z1 - p), (X1, H + ph, Z1)),
                              ((X0, H, Z0 + p), (X0 + p, H + ph, Z1 - p)), ((X1 - p, H, Z0 + p), (X1, H + ph, Z1 - p))]):
    B.box(f"parapet{k}", lo, hi)

for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):  # vent slot rows
    B.recess("tower", o, 0.2)
for k, o in enumerate(json.load(open(D / "decal_louvre.json"))["rects"]):  # louvred doors
    B.recess("tower", o, 0.15)
    B.sill(f"doorsill{k}", o, proud=0.12, thick=0.08, overhang=0.1)
for k, o in enumerate(json.load(open(D / "decal_box.json"))["rects"]):  # wall cabinet
    n = np.array(o["normal"])
    B.obox(f"cabinet{k}", np.array(o["center"]) + n * 0.175, o["t"], o["b"], o["normal"], (o["w"], o["h"], 0.35))
for k, o in enumerate(json.load(open(D / "decal_fan.json"))["rects"]):  # roof fan housing
    n = np.array(o["normal"])
    B.obox(f"fan{k}", np.array(o["center"]) + n * 0.115, o["t"], o["b"], o["normal"], (o["w"], o["h"], 0.25))

# the main
MX, MY, MR = 8.875, 4.215, 2.2
B.prism_z("main", ngon(MR, 32, MX, MY), Z0, Z1)
for k, (a, b) in enumerate(((Z0, Z0 + 0.25), (Z1 - 0.25, Z1), (2.18, 2.3), (5.9, 6.02))):
    B.prism_z(f"main_ring{k}", ngon(MR + (0.09 if k < 2 else 0.05), 32, MX, MY), a, b)
B.box("main_plinth", (7.77, 0.0, Z0), (9.98, 2.05, Z1))

# the three pipes: out of the +x wall at 7.82 m, an elbow ball, down onto the main's crown
PR, PY, PX = 0.37, 7.82, 8.89
MN = np.array([1.0, -1.0, 0.0]) / math.sqrt(2)
MT = np.array([0.0, 0.0, 1.0])
MB = np.cross(MN, MT)
for k, zc in enumerate((0.41, 4.10, 7.79)):
    B.prism_x(f"pipe{k}", ngon(PR, 20, zc, PY), X1, PX + PR + 0.05)
    B.prism_x(f"pipe{k}_collar", ngon(PR + 0.08, 20, zc, PY), X1, X1 + 0.18)
    B.prism_y(f"pipe{k}_down", ngon(PR, 20, PX, zc), MY + MR - 0.3, PY + PR + 0.05)
    B.prism_y(f"pipe{k}_foot", ngon(PR + 0.08, 20, PX, zc), MY + MR - 0.1, MY + MR + 0.12)
    # a mitred elbow: both legs cut on the bisector plane x - y = PX - PY (one box cut each; a SolidCraft sphere
    # tessellates to 45k triangles)
    m = np.array([PX, PY, zc])
    for leg, sgn in ((f"pipe{k}", 1), (f"pipe{k}_down", -1)):
        B.obox(f"mitre_{leg}", m + MN * sgn * 1.0, MT, MB, MN, (2.0, 2.0, 2.0))
        B.cut(leg, f"mitre_{leg}")

print(B.dump())
