#!/usr/bin/env python3
"""CAD rebuild of the tin shack (appearance tinshack), in the original's frame.

    D=~/craft/solid/mc2/buildings/tinshack
    python3 -I tools/art/cad_building.py openings tinshack > $D/openings.json
    python3 -I tools/art/cad_building.py decal tinshack 0 0.660 0.844 0.816 0.986 > $D/decal_door.json
    python3 -I tools/art/cad_building.py decal tinshack 0 0.420 0.700 0.517 0.816 > $D/decal_vent.json
    python3 -I tools/cad/tinshack_cad.py $D > $D/tinshack.json
    solidcraft-cli run $D/tinshack.json --out $D/tinshack.obj
    python3 -I tools/art/cad_building.py bake tinshack $D/tinshack.obj

Measured from game/assets/objects/tinshack.glb: a 14.65 x 8.79 m gabled shed (x -3.17..11.48, z -1.44..7.35,
eaves 3.66 m, ridge 5.86 m at z 2.95) with a lean-to porch roof on +z (3.66 m at the wall to 2.93 m at z 11.16) on
two corner posts; on the -z side a dark boiler annex (x -0.24..2.69, z -2.91..1.49, top 7.33 m) with a sloped plinth,
a box on its slope and a 5-sided stack (y 7.33..8.79) about (1.96, -0.71). Relief: shingle roof as 8 cm sheets
with 15-20 cm overhangs and a ridge cap; the painted roof grille a raised 14 cm hatch; the stack a true round
(24-gon) flue with a capping band and a hollow top (issue I77); windows (cut-outs, upper and lower panes) 12 cm
recesses with sills; the big -x end door (decal) a 15 cm recess under a drip hood; corner trims; square porch posts
and a fascia beam; a ledge round the annex top.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
X0, X1, Z0, Z1 = -3.17, 11.48, -1.44, 7.35
YE, YR, ZR = 3.66, 5.86, 2.95
ZP, YP = 11.16, 2.93
B = Builder()


def ngon(r, cx=0.0, cz=0.0, k=24):
    return [(cx + r * math.cos(2 * math.pi * i / k), cz + r * math.sin(2 * math.pi * i / k)) for i in range(k)]


shed = B.prism_x("shed", [(Z0, 0.0), (Z1, 0.0), (Z1, YE), (ZR, YR), (Z0, YE)], X0, X1)

# ---- windows (pairs of panes) and the end door
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    B.recess(shed, o, 0.12)
    if o["h"] < 0.45:   # the lower pane: sill under it
        B.sill(f"sill{k}", o, proud=0.09, thick=0.05, overhang=0.06)
door = json.load(open(D / "decal_door.json"))["rects"][0]
B.recess(shed, door, 0.15)
B.sill("doorhood", door, proud=0.18, thick=0.07, overhang=0.10, top=True)

# ---- roof sheets, ridge cap, grille hatch
def sheet(name, za, ya, zb, yb, x0, x1, ext_a, ext_b, thick=0.08):
    L = math.hypot(zb - za, yb - ya)
    b = np.array([0.0, yb - ya, zb - za]) / L       # from a to b
    n = np.array([0.0, (zb - za), -(yb - ya)]) / L
    if n[1] < 0:
        n = -n
    t = np.cross(b, n)
    c = np.array([(x0 + x1) / 2, (ya + yb) / 2, (za + zb) / 2]) + b * (ext_b - ext_a) / 2 + n * thick / 2
    return B.obox(name, c, t, b, n, (x1 - x0, L + ext_a + ext_b, thick))


sheet("roofS", Z0, YE, ZR, YR, X0 - 0.15, X1 + 0.15, 0.20, 0.0)
sheet("roofN", ZR, YR, Z1, YE, X0 - 0.15, X1 + 0.15, 0.0, 0.0)
sheet("porch", Z1, YE, ZP, YP, X0, X1, 0.0, 0.10, thick=0.06)
B.prism_x("ridge@avg", [(ZR - 0.35, YR - 0.175 + 0.07), (ZR, YR + 0.16), (ZR + 0.35, YR - 0.175 + 0.07), (ZR, YR - 0.05)],
          X0 - 0.17, X1 + 0.17)
vent = json.load(open(D / "decal_vent.json"))["rects"][0]
n, t, b = (np.array(vent[k], float) for k in ("normal", "t", "b"))
B.obox("hatch", np.array(vent["center"]) + n * 0.10, t, b, n, (vent["w"], vent["h"], 0.14))

# ---- corner trims, porch posts and fascia
for k, (x, z) in enumerate(((X0, Z0), (X1, Z0), (X0, Z1), (X1, Z1))):
    B.box(f"trim{k}", (x - 0.06, 0.0, z - 0.06), (x + 0.06, YE, z + 0.06))
for k, x in enumerate((X0 + 0.15, X1 - 0.15)):
    B.box(f"post{k}", (x - 0.15, 0.0, ZP - 0.30), (x + 0.15, YP - 0.02, ZP))
B.box("fascia", (X0, YP - 0.22, ZP - 0.16), (X1, YP, ZP))

# ---- boiler annex, plinth, box on the slope, ledge
B.prism_x("annex", [(-2.91, 0.0), (1.49, 0.0), (1.49, 6.16), (0.02, 7.33), (-1.44, 7.33), (-1.44, 4.40), (-2.91, 2.93)],
          -0.24, 2.69)
B.prism_x("plinth", [(-3.35, 0.0), (-2.91, 0.0), (-2.91, 2.93), (-3.35, 2.20)], 0.12, 2.32)
B.box("slopebox", (0.20, 3.08, -2.76), (1.66, 5.86, -1.44), chamfer=0.04)
B.box("ledge", (-0.32, 7.27, -1.52), (2.77, 7.39, 0.10))

# ---- the stack: round flue, capping band, hollow top
CX, CZ, RS = 1.96, -0.71, 0.57
B.prism_y("stack", ngon(RS, CX, CZ), 7.33, 8.79)
B.prism_y("band", ngon(RS + 0.06, CX, CZ), 8.57, 8.85)
B.prism_y("flue", ngon(RS - 0.15, CX, CZ), 8.45, 8.95)
B.cut("band", "flue")
B.prism_y("flue2", ngon(RS - 0.15, CX, CZ), 8.45, 8.95)
B.cut("stack", "flue2")

print(B.dump())
