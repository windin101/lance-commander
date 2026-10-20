#!/usr/bin/env python3
"""CAD rebuild of the colonnaded promenade (appearance s_promenade), in the original's frame.

    D=~/craft/solid/mc2/buildings/s_promenade
    python3 -I tools/art/cad_building.py openings s_promenade > $D/openings.json    (none: the art has no cut-outs)
    python3 -I tools/art/cad_building.py decal s_promenade 0 0.29 0.17 0.71 0.98 > $D/decal_panel.json
    python3 -I tools/cad/s_promenade_cad.py $D > $D/s_promenade.json
    solidcraft-cli run $D/s_promenade.json --out $D/s_promenade.obj
    python3 -I tools/art/cad_building.py bake s_promenade $D/s_promenade.obj

Measured from game/assets/objects/s_promenade.glb: a paved plinth (x -4.13..3.87, z -12.78..12.77, 0.46 m) whose
+x edge slopes down to 4.25 (painted as steps), the hall (x -3.88..0.27, z +-12.73) under a cornice slab
(x -4.21..0.81, 4.72..5.69 m), and on the plinth a canopy (x 1.79..3.81, 3.86..4.09 m) on five diamond posts
(centred x 2.74, z -11.25 -5.27 0.0 5.38 11.38) standing on stepped bases. Relief: the painted fluted columns on
the hall's long walls (z +-2.64 +-4.49 +-9.77 +-11.63, 1.42 m wide) become engaged half columns with a capital
block and a base; the dark door panels between them are 15 cm recesses; the free posts become true round columns
(24 sides) with capitals; the step slope becomes three real steps; the roof's painted grey field is a 6 cm
recess in its rim, the cornice gets a drip ledge.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
B = Builder()


def ngon(r, k, cx, cz):
    return [(cx + r * math.cos(2 * math.pi * (i + 0.5) / k), cz + r * math.sin(2 * math.pi * (i + 0.5) / k)) for i in range(k)]


# plinth with three steps down its +x edge (3.87 -> 4.25)
B.prism_z("plinth", [(-4.13, -0.05), (3.87, -0.05), (4.25, -0.05), (4.25, 0.15), (4.12, 0.15), (4.12, 0.31),
                     (3.99, 0.31), (3.99, 0.46), (-4.13, 0.46)], -12.78, 12.77)
hall = B.box("hall", (-3.88, 0.40, -12.73), (0.27, 4.72, 12.74))
corn = B.box("cornice", (-4.21, 4.72, -12.78), (0.81, 5.69, 12.77), chamfer=0.05)
B.cut(corn, B.box("f_roof", (-3.91, 5.63, -12.48), (0.51, 5.9, 12.47)))
B.box("drip", (-4.29, 4.66, -12.84), (0.89, 4.80, 12.83))

# door panels: 15 cm recesses
for o in json.load(open(D / "decal_panel.json"))["rects"]:
    B.recess(hall, o, 0.15)

# engaged columns on the long walls and at the corners of the ends
def column(name, x, z, r, ax_sign, face_x, w):
    B.prism_y(name, ngon(r, 24, x, z), 1.15, 4.19)  # a 24-gon prism: solid.cylinder tessellates to ~5k faces
    B.box(name + "_cap", (min(face_x, face_x + ax_sign * 0.42), 4.19, z - w / 2 - 0.06),
          (max(face_x, face_x + ax_sign * 0.42), 4.72, z + w / 2 + 0.06), chamfer=0.03,
          chamfer_edges=[(face_x + ax_sign * 0.42, 4.19, z)])
    B.box(name + "_base", (min(face_x, face_x + ax_sign * 0.44), 0.46, z - w / 2 - 0.08),
          (max(face_x, face_x + ax_sign * 0.44), 1.15, z + w / 2 + 0.08))

k = 0
for z in (-11.63, -9.77, -4.49, -2.64, 2.64, 4.49, 9.77, 11.63):
    for fx, s in ((0.27, 1), (-3.88, -1)):
        k += 1
        column(f"col{k}", fx - s * 0.36, z, 0.71, s, fx, 1.42)

# free columns under the canopy
for k, z in enumerate((-11.25, -5.27, 0.0, 5.38, 11.38)):
    B.loft_y(f"pbase{k}", [(1.69, z - 1.05), (3.79, z - 1.05), (3.79, z + 1.05), (1.69, z + 1.05)], 0.44,
             [(2.24, z - 0.5), (3.24, z - 0.5), (3.24, z + 0.5), (2.24, z + 0.5)], 0.74)
    B.prism_y(f"post{k}", ngon(0.45, 24, 2.74, z), 0.74, 3.70)
    B.box(f"pcap{k}", (2.19, 3.70, z - 0.55), (3.29, 3.86, z + 0.55), chamfer=0.03,
          chamfer_edges=[(2.74, 3.70, z - 0.55), (2.74, 3.70, z + 0.55), (2.19, 3.70, z), (3.29, 3.70, z)])
B.box("canopy", (1.79, 3.86, -12.78), (3.81, 4.09, 12.77), chamfer=0.03)

print(B.dump())
