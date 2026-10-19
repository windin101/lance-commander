#!/usr/bin/env python3
"""CAD rebuild of the single-storey house with a carport roof (appearance singlecivlivingd), in the original's frame.

    D=~/craft/solid/mc2/buildings/singlecivlivingd
    python3 -I tools/art/cad_building.py openings singlecivlivingd > $D/openings.json
    python3 -I tools/art/cad_building.py decal singlecivlivingd 0 0.425 0.105 0.72 0.295 > $D/decal_door.json
    python3 -I tools/cad/singlecivlivingd_cad.py $D > $D/singlecivlivingd.json
    solidcraft-cli run $D/singlecivlivingd.json --out $D/singlecivlivingd.obj
    python3 -I tools/art/cad_building.py bake singlecivlivingd $D/singlecivlivingd.obj --texel 0.012

Measured from game/assets/objects/singlecivlivingd.glb (node Box02 at z - 0.034): a front block (x -1.99..2.01,
z -2.98..-1.08) and a narrower rear block (x -1.38..1.39, to z 2.21) under one 22 cm roof slab (x +-2.08,
z -3.04..4.03) that falls 22 cm from z 2.21 to the front edge and runs flat over a carport on two posts
(x +-1.425, z 3.82) with 23 cm feet; a hexagonal flue (r 0.23 -> 0.16, 2.6 -> 3.42 m) under a hexagonal cone cap
(r 0.39, apex 3.73 m). Relief: the roof's painted boards (along z, 0.46 m apart, from the art) are real planks with
2 cm grooves; every cut-out window is a 15 cm recess with a frame and sill; the painted rear door (decal) is a
10 cm recess with its small window a further 5 cm in; a skirting plinth runs round both blocks; the posts are
round, the feet concrete.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
B = Builder()
RX, RZ0, RZB, RZ1 = 2.08, -3.04, 2.21, 4.03   # roof half-width, front edge, slope break, carport end
YF, YB, TH = 2.26, 2.48, 0.22                 # roof underside at the front edge / behind the break, thickness


def under(z):
    return YF + (YB - YF) * min(1.0, (z - RZ0) / (RZB - RZ0))


# ---- walls (tops inside the roof slab, so bake drops them)
front = B.box("front", (-1.99, 0.0, -2.98), (2.01, 2.48, -1.08))
rear = B.box("rear", (-1.38, 0.0, -1.08), (1.39, 2.55, 2.21))
BLOCKS = {front: ((-1.99, 0.0, -2.98), (2.01, 2.48, -1.08)), rear: ((-1.38, 0.0, -1.08), (1.39, 2.55, 2.21))}
for nm, (lo, hi) in (("plinth_f", ((-2.02, 0.0, -3.01), (2.04, 0.14, -1.08))), ("plinth_r", ((-1.41, 0.0, -1.08), (1.42, 0.14, 2.24)))):
    B.box(nm, lo, hi)

# ---- roof: a base slab 2 cm under the top and planks on it, grooves on the painted board lines
def roof_prof(dt=0.0):
    return [(RZ0, YF), (RZB, YB), (RZ1, YB), (RZ1, YB + TH - dt), (RZB, YB + TH - dt), (RZ0, YF + TH - dt)]


B.prism_x("roof", roof_prof(0.02), -RX, RX)
G = 0.008
edges = [-RX] + [-RX + 0.34 + 0.46 * k for k in range(9)] + [RX]
for k in range(len(edges) - 1):
    a, b = edges[k] + (G if k else 0.0), edges[k + 1] - (G if k < len(edges) - 2 else 0.0)
    B.prism_x(f"plank{k}", roof_prof(0.0), a, b)

# ---- openings
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    c = o["center"]
    if abs(o["normal"][2]) > 0.9 and c[2] > 2.0:
        continue  # the rear door's window: cut with the door below
    tgt = front if c[2] < -1.08 else rear
    # the art runs some windows right to the block's corner: keep 12 cm of wall there for the frame and the
    # recess of the window round the corner
    (bx0, _, bz0), (bx1, _, bz1) = BLOCKS[tgt]
    ax = 0 if abs(o["normal"][2]) > 0.9 else 2
    lo_, hi_ = (bx0, bx1) if ax == 0 else (bz0, bz1)
    ta = [o["t"][0], o["t"][1], o["t"][2]][ax]
    a, b = c[ax] - o["w"] / 2, c[ax] + o["w"] / 2
    a, b = max(a, lo_ + 0.12), min(b, hi_ - 0.12)
    o = dict(o, w=b - a, center=[(a + b) / 2 if ax == 0 else c[0], c[1], (a + b) / 2 if ax == 2 else c[2]])
    B.recess(tgt, o, 0.15)
    B.frame(f"wframe{k}", o, width=0.06, proud=0.04)
    B.sill(f"sill{k}", o, proud=0.10, thick=0.05, overhang=0.08)
for k, o in enumerate(json.load(open(D / "decal_door.json"))["rects"]):
    door = dict(o, w=o["w"] - 0.16, h=o["h"] - 0.08, center=[o["center"][0], o["center"][1] - 0.04 + 0.0, o["center"][2]])
    door["center"][1] = door["h"] / 2 + 0.02
    B.recess(rear, door, 0.10)
    B.frame(f"dframe{k}", door, width=0.07, proud=0.04)
    for j, w in enumerate(json.load(open(D / "openings.json"))["openings"]):
        if abs(w["normal"][2]) > 0.9 and w["center"][2] > 2.0:
            B.recess(rear, w, 0.05, surface_shift=0.10)
    x0, x1 = door["center"][0] - door["w"] / 2 - 0.2, door["center"][0] + door["w"] / 2 + 0.2
    B.box(f"doorstep{k}@6f6b64", (x0, 0.0, 2.21), (x1, 0.12, 2.75))

# ---- carport posts on concrete feet
for k, x in enumerate((-1.425, 1.425)):
    z = 3.82
    B.box(f"foot{k}@6f6b64", (x - 0.125, 0.0, z - 0.125), (x + 0.125, 0.23, z + 0.125), chamfer=0.03)
    B.c("solid.cylinder", radius=60, height=round((YB - 0.23 + 0.02) * 1000, 2), base=[round(x * 1000, 2), round(-z * 1000, 2), 230],
        axis=[0, 0, 1], body_name=f"post{k}", operation="new")

# ---- flue and its cone cap
FX, FZ = 0.0, -0.01


def hexa(r, rot=0.0):
    return [(FX + r * math.cos(rot + a * math.pi / 3), FZ + r * math.sin(rot + a * math.pi / 3)) for a in range(6)]


B.loft_y("flue", hexa(0.23), under(FZ) + TH - 0.05, hexa(0.16), 3.42)
B.loft_y("flue_cap", hexa(0.39), 3.42, hexa(0.03), 3.73)
B.prism_y("flue_collar", hexa(0.27), under(FZ) + TH - 0.02, under(FZ) + TH + 0.06)

print(B.dump())
