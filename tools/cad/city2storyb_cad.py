#!/usr/bin/env python3
"""CAD rebuild of the two-storey city block (appearance city2storyb), in the original's frame.

    D=~/craft/solid/mc2/buildings/city2storyb
    python3 -I tools/art/cad_building.py openings city2storyb > $D/openings.json
    python3 -I tools/art/cad_building.py decal city2storyb 0 0.545 0.05 0.675 0.225 > $D/decal_fan1.json
    python3 -I tools/art/cad_building.py decal city2storyb 0 0.545 0.265 0.675 0.44 > $D/decal_fan2.json
    python3 -I tools/art/cad_building.py decal city2storyb 0 0.79 0.385 0.975 0.46 > $D/decal_boxes.json
    python3 -I tools/cad/city2storyb_cad.py $D > $D/city2storyb.json
    solidcraft-cli run $D/city2storyb.json --out $D/city2storyb.obj
    python3 -I tools/art/cad_building.py bake city2storyb $D/city2storyb.obj

Measured from game/assets/objects/city2storyb.glb (node City2StoryA; LitWin_City2Story is the night overlay): a plain
box, x -10.044..7.713, z -7.663..10.094, to 6.946 m. Its walls use only the bottom quarter of the texture (v 0.748..1):
the -z, +x and +z walls its left half, the -x wall its right half with the double door. Each wall paints two rows of
five two-pane windows (1.03 x 1.245 m, centres 1.72 and 5.17 m); only some panes are cut-outs (openings.json), so the
window grid is placed from the cut-outs' positions: columns 1.92, 5.23, 8.81, 12.38, 15.75 m along the left-half
walls' u, 1.82, 5.27, 8.81, 12.47, 16.08 m along the -x wall, whose lower middle column is the double door.
Relief: every window is a 15 cm recess with a sill (painted and cut-out panes alike), the double door a 20 cm recess
with a hood and a step; a cornice at the roof line and a plinth ring the walls; the roof gets a parapet, the two
painted fan squares are raised housings with a fan drum and the painted equipment row a low plant box (their sides
one flat colour, @avg, under a thin painted cap: box-mapped sides streaked the roof art).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, box_edges  # noqa: E402

D = Path(sys.argv[1])
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


# fan housings: the painted square raised 40 cm, a 15 cm fan drum on top
for i, f in enumerate(("fan1", "fan2")):
    o = json.load(open(D / f"decal_{f}.json"))["rects"][0]
    c = np.array(o["center"])
    hw, hd = o["w"] / 2 - 0.35, o["h"] / 2 - 0.35
    # sides one flat colour (box-mapped sides would streak the roof art), a thin painted cap on top
    B.box(f"fanhouse{i}@avg", (c[0] - hw, H, c[2] - hd), (c[0] + hw, H + 0.33, c[2] + hd))
    B.box(f"fancap{i}", (c[0] - hw - 0.03, H + 0.33, c[2] - hd - 0.03), (c[0] + hw + 0.03, H + 0.4, c[2] + hd + 0.03))
    B.prism_y(f"fandrum{i}", ngon(min(hw, hd) * 0.85, 24, c[0], c[2]), H + 0.4, H + 0.55)

o = json.load(open(D / "decal_boxes.json"))["rects"][0]
c = np.array(o["center"])
pw, pd = o["w"] / 2 - 0.2, o["h"] / 2 - 0.2
B.box("plantbox@avg", (c[0] - pw, H, c[2] - pd), (c[0] + pw, H + 0.6, c[2] + pd))
B.box("plantcap", (c[0] - pw - 0.03, H + 0.6, c[2] - pd - 0.03), (c[0] + pw + 0.03, H + 0.68, c[2] + pd + 0.03))

print(B.dump())
