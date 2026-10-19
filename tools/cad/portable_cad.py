#!/usr/bin/env python3
"""CAD rebuild of the portable site cabin (appearance portable), in the original's frame.

    D=~/craft/solid/mc2/buildings/portable
    python3 -I tools/art/cad_building.py openings portable > $D/openings.json
    python3 -I tools/art/cad_building.py decal portable 0 <u0 v0 u1 v1> > $D/decal_<name>.json   (see DECALS)
    python3 -I tools/cad/portable_cad.py $D > $D/portable.json
    solidcraft-cli run $D/portable.json --out $D/portable.obj
    python3 -I tools/art/cad_building.py bake portable $D/portable.obj

Measured from game/assets/objects/portable.glb: a cabin box (x -3.895..2.058, z -11.604..3.007, 0.592 to 3.929 m)
on an inset skirt (x -3.727..1.889, z -11.205..2.549, to 0.632 m); a timber deck at the door (x 2.08..3.95,
z -5.387..-3.216, 0.598 m) with three steps down toward +z and railing cards 1.74 m high.
Relief: the texture's grey-green window bays are 6 cm panels set back between the bolted concrete panels; the
windows (cut-outs) are 12 cm recesses in them with sills; the door is a 14 cm recess; the painted fascia band is a
real 7 cm proud fascia that stands 12 cm above the roof as a parapet; the two pale squares on the roof are
chamfered plant boxes and the small one a low vent; the deck is an open timber deck on corner posts, with treads on
stringers and a two-bar railing on its open sides.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, box_edges  # noqa: E402

DECALS = {  # name: (material, u0, v0, u1, v1) in the upscaled atlas
    "bay1a": (0, 0.299, 0.518, 0.502, 0.703), "bay1b": (0, 0.699, 0.518, 0.902, 0.703),
    "bay2a": (0, 0.299, 0.791, 0.502, 0.977), "bay2b": (0, 0.699, 0.791, 0.902, 0.977),
    "door": (0, 0.756, 0.791, 0.852, 0.977), "ac": (0, 0.414, 0.18, 0.523, 0.29), "vent": (0, 0.664, 0.328, 0.795, 0.387),
}
D = Path(sys.argv[1])
X0, X1, Z0, Z1, YB, YT = -3.895, 2.058, -11.604, 3.007, 0.592, 3.929
BAY = 0.06
B = Builder()


def rects(name):
    return json.load(open(D / f"decal_{name}.json"))["rects"]


body = B.box("body", (X0, YB, Z0), (X1, YT, Z1), chamfer=0.04, chamfer_edges=box_edges((X0, YB, Z0), (X1, YT, Z1), "vertical"))
B.box("skirt", (-3.727, -0.045, -11.205), (1.889, YB + 0.04, 2.549))

# window bays: set back 6 cm, from just above the cabin floor to under the fascia
bays = [o for nm in ("bay1a", "bay1b", "bay2a", "bay2b") for o in rects(nm)]
for o in bays:
    lo_y, hi_y = YB + 0.06, 3.24
    c = list(o["center"])
    c[1] = (lo_y + hi_y) / 2
    B.recess(body, dict(o, center=c, w=o["w"] - 0.06, h=hi_y - lo_y), BAY)

# windows: 12 cm behind the bay panel, with a sill
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    if abs(o["normal"][1]) > 0.5 or o["center"][1] < 1.2:  # the deck's railing cards
        continue
    if o["w"] < 1.0:  # the door's window: part of the door recess
        continue
    B.recess(body, o, 0.12, surface_shift=BAY)
    B.sill(f"sill{k}", o, proud=0.08, thick=0.06, overhang=0.06, surface_shift=BAY)

# door: 14 cm recess in its bay (its window pane comes from the cut-out at the back)
for o in rects("door"):
    lo_y, hi_y = YB + 0.07, 3.0
    c = list(o["center"])
    c[1] = (lo_y + hi_y) / 2
    B.recess(body, dict(o, center=c, w=1.05, h=hi_y - lo_y), 0.14, surface_shift=BAY)

# fascia band, 7 cm proud, rising 12 cm above the roof as a parapet
F, FY0, FY1, IN = 0.07, 3.26, YT + 0.12, 0.12
for k, (lo, hi) in enumerate((((X0 - F, FY0, Z0 - F), (X1 + F, FY1, Z0 + IN)), ((X0 - F, FY0, Z1 - IN), (X1 + F, FY1, Z1 + F)),
                              ((X0 - F, FY0, Z0 + IN), (X0 + IN, FY1, Z1 - IN)), ((X1 - IN, FY0, Z0 + IN), (X1 + F, FY1, Z1 - IN)))):
    B.box(f"fascia{k}", lo, hi)

# roof plant: the pale squares as chamfered boxes, the small one a low vent
for k, o in enumerate(rects("ac")):
    c = np.array(o["center"])
    lo, hi = (c[0] - 0.6, YT, c[2] - 0.58), (c[0] + 0.6, YT + 0.7, c[2] + 0.58)
    lo, hi = lo, (hi[0], YT + 0.45, hi[2])
    B.box(f"plant{k}@avg", lo, hi, chamfer=0.06)
    B.box(f"plantlid{k}@8a8a86", (lo[0] + 0.25, hi[1], lo[2] + 0.25), (hi[0] - 0.25, hi[1] + 0.06, hi[2] - 0.25))
for k, o in enumerate(rects("vent")):
    c = np.array(o["center"])
    B.box(f"vent{k}@avg", (c[0] - 0.3, YT, c[2] - 0.7), (c[0] + 0.3, YT + 0.22, c[2] + 0.7), chamfer=0.04)

# timber deck at the door, block steps, posts and a two-bar railing
DX0, DX1, DZ0, DZ1, DY = 2.084, 3.951, -5.387, -3.216, 0.598
B.box("deck", (X1 - 0.01, DY - 0.1, DZ0), (DX1, DY, DZ1))
TH = 0.05
for k, (y, za, zb) in enumerate(((0.409, DZ1, -3.013), (0.235, -3.013, -2.816), (0.07, -2.816, -2.613))):
    B.box(f"step{k}", (DX0 + 0.08, y - TH, za), (DX1 - 0.08, y, zb))
# stringers: from the deck edge down to the ground at the foot of the steps
d = np.array([0.0, -DY, -2.613 - DZ1])
L = float(np.linalg.norm(d))
t = d / L
n = np.array([1.0, 0.0, 0.0])
b = np.cross(n, t)
for k, x in enumerate((DX0 + 0.05, DX1 - 0.05)):
    c = np.array([x, DY / 2 - 0.08, (DZ1 - 2.613) / 2])
    B.obox(f"stringer{k}", c, t, b, n, (L + 0.1, 0.2, 0.05))
P, RY1 = 0.07, 1.743
for k, (x, z) in enumerate(((DX1 - P / 2, DZ0 + P / 2), (DX1 - P / 2, DZ1 - P / 2), (X1 + P / 2 + 0.02, DZ0 + P / 2),
                            (X1 + P / 2 + 0.02, DZ1 - P / 2))):
    B.box(f"post{k}", (x - P / 2, 0.0, z - P / 2), (x + P / 2, RY1, z + P / 2))
for k, y in enumerate((RY1 - 0.06, 1.15)):
    B.box(f"rail_x{k}", (DX1 - P + 0.015, y, DZ0 + P), (DX1 - 0.015, y + 0.05, DZ1 - P))   # outer side
    B.box(f"rail_z{k}", (X1 + P + 0.02, y, DZ0 + 0.015), (DX1 - P, y + 0.05, DZ0 + P - 0.015))  # far end

print(B.dump())
