#!/usr/bin/env python3
"""CAD rebuild of the glazed terminal walkway (appearance walkway, node Terminal), in the original's frame.

    D=~/craft/solid/mc2/buildings/walkway
    python3 -I tools/art/cad_building.py openings walkway > $D/openings.json
    python3 -I tools/art/cad_building.py decal walkway 0 <u0 v0 u1 v1> > $D/decal_<name>.json   (DECALS below)
    python3 -I tools/cad/walkway_cad.py $D > $D/walkway.json
    solidcraft-cli run $D/walkway.json --out $D/walkway.obj
    python3 -I tools/art/cad_building.py bake walkway $D/walkway.obj --glass 96,128,78

Measured from game/assets/objects/walkway.glb: walls x -12.75..12.751, z -6..6 to 6 m under a 45-degree hipped
roof to a flat at 8 m (x -10.75..10.75, z -4..4); a cut-out window band y 2.0..4.6 all round (inner faces at y 2..4.6
show a green floor through it). Relief: every outward cut-out is a 25 cm recess with glass at the back; a
continuous sill ledge under the band and a cornice at the eaves; the painted grey roof panel is a 10 cm recess in a
white rim; the four painted roof units are 0.55 m boxes and the two painted hip hoods 18 cm raised plates.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

DECALS = {"panel": (0.070, 0.068, 0.610, 0.259), "ac0": (0.420, 0.083, 0.457, 0.135), "ac3": (0.560, 0.083, 0.596, 0.135),
          "hood0": (0.41, 0.008, 0.53, 0.058), "hood1": (0.16, 0.270, 0.26, 0.318)}
D = Path(sys.argv[1])
X0, X1, Z, WALL, TOP, XT, ZT = -12.75, 12.751, 6.0, 6.0, 8.0, 10.75, 4.0
B = Builder()


def rects(nm):
    return json.load(open(D / f"decal_{nm}.json"))["rects"]


W = B.box("walls", (X0, 0.0, -Z), (X1, WALL, Z))
R = B.loft_y("roof", [(X0, -Z), (X1, -Z), (X1, Z), (X0, Z)], WALL, [(-XT, -ZT), (XT, -ZT), (XT, ZT), (-XT, ZT)], TOP)
p = rects("panel")[0]
c = np.array(p["center"])
B.cut(R, B.box("panelcut", (c[0] - p["w"] / 2, TOP - 0.10, c[2] - p["h"] / 2), (c[0] + p["w"] / 2, TOP + 0.05, c[2] + p["h"] / 2)))

# windows: the outward-facing cut-outs (the original also lists the inner faces behind them)
DEPTH = 0.25
for o in json.load(open(D / "openings.json"))["openings"]:
    if np.dot(o["center"], o["normal"]) <= 0:
        continue
    B.recess(W, o, DEPTH)

# sill ledge under the band and cornice at the eaves, one bar per side (touching bodies)
for nm, y0, y1, pr in (("sill", 1.96, 2.10, 0.12), ("cornice", WALL - 0.22, WALL - 0.04, 0.08)):
    B.box(f"{nm}_n", (X0 - pr, y0, -Z - pr), (X1 + pr, y1, -Z + 0.02))
    B.box(f"{nm}_s", (X0 - pr, y0, Z - 0.02), (X1 + pr, y1, Z + pr))
    B.box(f"{nm}_w", (X0 - pr, y0, -Z), (X0 + 0.02, y1, Z))
    B.box(f"{nm}_e", (X1 - 0.02, y0, -Z), (X1 + pr, y1, Z))

# roof units: four boxes between the two measured ends
a0, a3 = rects("ac0")[0], rects("ac3")[0]
for k in range(4):
    cx = a0["center"][0] + (a3["center"][0] - a0["center"][0]) * k / 3
    cz = a0["center"][2]
    hw, hd = 0.6, 0.92
    B.box(f"unit{k}", (cx - hw, TOP - 0.10, cz - hd), (cx + hw, TOP + 0.55, cz + hd), chamfer=0.05)

# hip hoods: raised plates on the slope
for nm in ("hood0", "hood1"):
    for o in rects(nm):
        n = np.array(o["normal"])
        B.obox(nm, np.array(o["center"]) + n * 0.08, o["t"], o["b"], o["normal"], (o["w"] * 0.8, o["h"] * 0.85, 0.2))

print(B.dump())
