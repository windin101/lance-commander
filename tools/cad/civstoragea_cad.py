#!/usr/bin/env python3
"""CAD rebuild of the civilian storage shed (appearance civstoragea), in the original's frame.

    D=~/craft/solid/mc2/buildings/civstoragea
    python3 -I tools/art/cad_building.py openings civstoragea > $D/openings.json
    python3 -I tools/art/cad_building.py decal civstoragea 0 0.245 0.712 0.585 1.0 > $D/decal_door.json
    python3 -I tools/cad/civstoragea_cad.py $D > $D/civstoragea.json
    solidcraft-cli run $D/civstoragea.json --out $D/civstoragea.obj
    python3 -I tools/art/cad_building.py bake civstoragea $D/civstoragea.obj

Measured from game/assets/objects/civstoragea.glb (node Box02): a 7.7 x 11.19 m shed, walls 3.46 m, under three
gables along z (ridges at x = -2.57, 0, 2.57 at 4.2 m, valleys at +-1.28), the roof sheet overhanging 0.4 m at both
ends; a roller door in each end wall (x -1.51..1.75, 2.79 m), and a lamp on an arm above each door.
Relief: the roof is a real 12 cm slab (top on the original surface), eaves carried 10 cm past the walls with a gutter;
its painted seams (0.56 m pitch, from the texture: dark lines at v = 0.0122 + 0.0466 k over the 12 m) are real
standing ridges between the dark lines; the painted 1.17 m concrete plinth stands 6 cm proud with a chamfered top;
corner trims; the side windows are 20 cm recesses with sills and mullions; the roller doors are 30 cm recesses in
a proud frame, their window strips a further 5 cm; the lamps are an arm and a shade.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
X0, X1, Z0, Z1 = -3.85, 3.85, -9.56, 1.63      # walls
RZ0, RZ1 = -9.96, 2.04                          # roof sheet
EAVE, RIDGE, T = 3.46, 4.2, 0.12
XS = [-3.85, -2.57, -1.28, 0.0, 1.28, 2.57, 3.85]
SLOPE = (RIDGE - EAVE) / 1.285
OVER = 0.10                                     # eaves carried past the wall
PLINTH, PROUD = 1.17, 0.06


def zig(dy=0.0, over=0.0):
    """The roof surface (x, y) left to right, shifted up by dy, the eaves run out by `over`."""
    pts = []
    for i, x in enumerate(XS):
        y = (EAVE if i % 2 == 0 else RIDGE) + dy
        if i == 0:
            pts.append((x - over, y - SLOPE * over))
        elif i == len(XS) - 1:
            pts.append((x + over, y - SLOPE * over))
        else:
            pts.append((x, y))
    return pts


B = Builder()
# ---- volumes: walls with the gable ends under the slab, the slab itself
walls = B.prism_z("walls", [(X0, 0.0), (X1, 0.0)] + zig(-T)[::-1], Z0, Z1)
B.prism_z("roof", zig(0.0, OVER) + zig(-T, OVER)[::-1], RZ0, RZ1)

# ---- standing seams between the painted dark lines
pitch_v, phase_v = 0.0466, 0.0122
k = 0
while True:
    v = phase_v + pitch_v * (k + 0.5)
    z = RZ0 + v * (RZ1 - RZ0)
    if z > RZ1 - 0.08:
        break
    if z > RZ0 + 0.08:
        B.prism_z(f"seam{k}", zig(0.022, OVER) + zig(-0.02, OVER)[::-1], z - 0.09, z + 0.09)
    k += 1

# ---- ridge caps: a folded strip along each ridge, over the seam ends
for k, x in enumerate(XS[1::2]):
    w, d = 0.16, 0.05
    B.prism_z(f"ridge{k}@avg", [(x - w, RIDGE - SLOPE * w + 0.01), (x, RIDGE + d), (x + w, RIDGE - SLOPE * w + 0.01),
                                (x + w, RIDGE - SLOPE * w - 0.03), (x, RIDGE - 0.03), (x - w, RIDGE - SLOPE * w - 0.03)],
              RZ0 - 0.02, RZ1 + 0.02)

# ---- gutters along both eaves
ye = EAVE - SLOPE * OVER - T
B.box("gutter_l@8c8c84", (X0 - OVER - 0.2, ye - 0.16, RZ0), (X0 - OVER + 0.02, ye + 0.04, RZ1))
B.box("gutter_r@8c8c84", (X1 + OVER - 0.02, ye - 0.16, RZ0), (X1 + OVER + 0.2, ye + 0.04, RZ1))

# ---- plinth (proud, chamfered top) and corner trims
door = [o for o in json.load(open(D / "decal_door.json"))["rects"] if abs(o["normal"][2]) > 0.9]
dx0 = door[0]["center"][0] - door[0]["w"] / 2
dx1 = door[0]["center"][0] + door[0]["w"] / 2
CH = 0.04
zm, = [(Z0 + Z1) / 2]
B.box("plinth_l", (X0 - PROUD, 0.0, Z0 - PROUD), (X0, PLINTH, Z1 + PROUD), chamfer=CH, chamfer_edges=[(X0 - PROUD, PLINTH, zm)])
B.box("plinth_r", (X1, 0.0, Z0 - PROUD), (X1 + PROUD, PLINTH, Z1 + PROUD), chamfer=CH, chamfer_edges=[(X1 + PROUD, PLINTH, zm)])
for side, (za, zb, ze) in {"f": (Z0 - PROUD, Z0, Z0 - PROUD), "b": (Z1, Z1 + PROUD, Z1 + PROUD)}.items():
    for j, (xa, xb) in enumerate(((X0, dx0 - 0.02), (dx1 + 0.02, X1))):
        B.box(f"plinth_{side}{j}", (xa, 0.0, za), (xb, PLINTH, zb), chamfer=CH, chamfer_edges=[((xa + xb) / 2, PLINTH, ze)])
for k, (x, z) in enumerate(((X0, Z0), (X1, Z0), (X0, Z1), (X1, Z1))):
    sx, sz = (1 if x > 0 else -1), (1 if z > -4 else -1)
    B.box(f"corner{k}", (min(x - sx * 0.1, x + sx * 0.04), PLINTH, min(z - sz * 0.1, z + sz * 0.04)),
          (max(x - sx * 0.1, x + sx * 0.04), ye - 0.02, max(z - sz * 0.1, z + sz * 0.04)))

# ---- side windows: 20 cm recesses, sills, mullions between the panes
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    if abs(o["normal"][0]) < 0.9:
        continue  # the end-wall cut-outs are the roller doors' window strips, below
    B.recess(walls, o, 0.20)
    B.sill(f"sill{k}", o, proud=0.10, thick=0.06, overhang=0.06)
    panes = max(1, round(o["w"] / 0.92))
    for m in range(1, panes):
        c = np.array(o["center"]) + np.array(o["t"]) * (o["w"] * (m / panes - 0.5)) - np.array(o["normal"]) * 0.1
        B.obox(f"mullion{k}_{m}", c, o["t"], o["b"], o["normal"], (0.05, o["h"], 0.2))

# ---- roller doors: 30 cm recesses inside a proud frame, the window strip a further 5 cm
FR = 0.13
for k, o in enumerate(door):
    n, t, b = (np.array(o[q], float) for q in ("normal", "t", "b"))
    c = np.array(o["center"])
    inner = dict(o, center=list(c - b * FR / 2), w=o["w"] - 2 * FR, h=o["h"] - FR)
    B.recess(walls, inner, 0.30)
    top = c + b * (o["h"] / 2 - FR / 2) + n * 0.03
    B.obox(f"dframe{k}_t", top, t, b, n, (o["w"], FR, 0.08))
    for s in (1, -1):
        side = c + t * s * (o["w"] / 2 - FR / 2) + n * 0.03
        B.obox(f"dframe{k}_{'lr'[s > 0]}", side, t, b, n, (FR, o["h"], 0.08))
for o in json.load(open(D / "openings.json"))["openings"]:
    if abs(o["normal"][2]) > 0.9:
        B.recess(walls, o, 0.05, surface_shift=0.30)

# ---- lamps over the doors: an arm out of the gable and a shade
for k, (zw, s) in enumerate(((Z0, -1), (Z1, 1))):
    B.box(f"lamparm{k}@6e6e68", (-0.05, 3.05, min(zw, zw + s * 0.62)), (0.05, 3.15, max(zw, zw + s * 0.62)))
    zc = zw + s * 0.61
    B.loft_y(f"lampshade{k}", [(-0.36, zc - 0.36), (0.36, zc - 0.36), (0.36, zc + 0.36), (-0.36, zc + 0.36)], 2.70,
             [(-0.14, zc - 0.14), (0.14, zc - 0.14), (0.14, zc + 0.14), (-0.14, zc + 0.14)], 3.02)

print(B.dump())
