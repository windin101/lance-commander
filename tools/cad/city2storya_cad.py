#!/usr/bin/env python3
"""CAD rebuild of the two-storey brick city block (appearance city2storya), in the original's frame.

    D=~/craft/solid/mc2/buildings/city2storya
    python3 -I tools/cad/city2storya_cad.py $D > $D/city2storya.json
    solidcraft-cli run $D/city2storya.json --out $D/city2storya.obj
    python3 -I tools/art/cad_building.py bake city2storya $D/city2storya.obj

city2storya is city2storyb's mesh exactly (x -10.044..7.713, z -7.663..10.094, to 6.946 m, same UV layout) with a
red-brick texture whose windows and double door sit where city2storyb's do, so the walls are city2storyb_cad.py's
(window grid, recesses, sills, door, cornice, plinth, parapet). Only the roof differs: the two painted fans sit
side by side (one raised housing, two fan drums), the equipment row and the small box row along the top edge are
low plant boxes. Roof rectangles are texture pixel boxes (512 px), mapped by tools/cad/city_facade.roof_xz.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, box_edges  # noqa: E402

B = Builder()
X0, X1, Z0, Z1, H = -10.044, 7.713, -7.663, 10.094, 6.946
main = B.box("main", (X0, 0.0, Z0), (X1, H, Z1), chamfer=0.04, chamfer_edges=box_edges((X0, 0.0, Z0), (X1, H, Z1), "vertical"))

LEFT = [1.92, 5.23, 8.81, 12.38, 15.75]
RIGHT = [1.82, 5.27, 8.81, 12.47, 16.08]
UP = np.array([0.0, 1.0, 0.0])
# (normal, origin of u on the wall, u direction, columns)
WALLS = [((0, 0, -1), (X1, 0, Z0), (-1, 0, 0), LEFT), ((0, 0, 1), (X0, 0, Z1), (1, 0, 0), LEFT),
         ((1, 0, 0), (X1, 0, Z1), (0, 0, -1), LEFT), ((-1, 0, 0), (X0, 0, Z0), (0, 0, 1), RIGHT)]


def opening(n, p, w, h):
    n = np.array(n, float)
    return {"center": list(map(float, p)), "normal": n.tolist(), "t": np.cross(UP, n).tolist(), "b": UP.tolist(), "w": w, "h": h}


k = 0
door = None
for n, o, u, cols in WALLS:
    o, u = np.array(o, float), np.array(u, float)
    for ci, d in enumerate(cols):
        for y in (1.72, 5.17):
            if n == (-1, 0, 0) and ci == 2 and y < 3:
                door = opening(n, o + u * 8.95 + UP * 1.15, 2.6, 2.3)
                continue
            win = opening(n, o + u * d + UP * y, 1.03, 1.245)
            B.recess(main, win, 0.15)
            B.sill(f"sill{k}", win, proud=0.09, thick=0.07, overhang=0.07)
            k += 1

B.recess(main, door, 0.2)
B.sill("doorhood", door, proud=0.35, thick=0.1, overhang=0.2, top=True)
B.box("doorstep@8f8b84", (X0 - 0.4, 0.0, -7.663 + 8.95 - 1.25), (X0, 0.15, -7.663 + 8.95 + 1.25))

# cornice at the roof line (25 cm deep, 8 cm proud) and a 30 cm plinth (4 cm proud)
for nm, y0, y1, p in (("cornice@avg", H - 0.3, H - 0.05, 0.08), ("plinth@avg", 0.0, 0.3, 0.04)):
    B.box(f"{nm.split('@')[0]}_mz@{nm.split('@')[1]}", (X0 - p, y0, Z0 - p), (X1 + p, y1, Z0 + 0.01))
    B.box(f"{nm.split('@')[0]}_pz@{nm.split('@')[1]}", (X0 - p, y0, Z1 - 0.01), (X1 + p, y1, Z1 + p))
    B.box(f"{nm.split('@')[0]}_px@{nm.split('@')[1]}", (X1 - 0.01, y0, Z0 + 0.01), (X1 + p, y1, Z1 - 0.01))
    B.box(f"{nm.split('@')[0]}_mx@{nm.split('@')[1]}", (X0 - p, y0, Z0 + 0.01), (X0 + 0.01, y1, Z1 - 0.01))

# parapet, 5 cm in from the roof edge
T, PH, E = 0.2, H + 0.35, 0.05
a0, a1, b0, b1 = X0 + E, X1 - E, Z0 + E, Z1 - E
for i, (lo, hi) in enumerate((((a0, H, b0), (a1, PH, b0 + T)), ((a0, H, b1 - T), (a1, PH, b1)),
                              ((a0, H, b0 + T), (a0 + T, PH, b1 - T)), ((a1 - T, H, b0 + T), (a1, PH, b1 - T)))):
    B.box(f"parapet{i}", lo, hi)


def ngon(r, n, cx, cz):
    return [(cx + r * math.cos(2 * math.pi * (j + 0.5) / n), cz + r * math.sin(2 * math.pi * (j + 0.5) / n)) for j in range(n)]


from city_facade import Original, roof_xz  # noqa: E402

O = Original("city2storya")
# the fan pair: one housing 40 cm high, a fan drum over each painted fan
fx0, fz0, fx1, fz1 = roof_xz(O, (283, 136, 399, 219))
B.box("fanhouse@avg", (fx0 + 0.3, H, fz0 + 0.3), (fx1 - 0.3, H + 0.33, fz1 - 0.3))
B.box("fancap", (fx0 + 0.27, H + 0.33, fz0 + 0.27), (fx1 - 0.27, H + 0.4, fz1 - 0.27))
for k, px in enumerate((311, 371)):
    cx, cz, _, _ = roof_xz(O, (px, 178, px, 178))
    B.prism_y(f"fandrum{k}", ngon(1.45, 24, cx, cz), H + 0.4, H + 0.55)

for nm, box, ph in (("plant", (405, 201, 499, 237), 0.6), ("topbox", (409, 12, 487, 28), 0.35)):
    x0, z0, x1, z1 = roof_xz(O, box)
    B.box(f"{nm}box@avg", (x0 + 0.15, H, z0 + 0.15), (x1 - 0.15, H + ph, z1 - 0.15))
    B.box(f"{nm}cap", (x0 + 0.12, H + ph, z0 + 0.12), (x1 - 0.12, H + ph + 0.08, z1 - 0.12))

print(B.dump())
