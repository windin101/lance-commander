#!/usr/bin/env python3
"""CAD rebuild of the large fuel tank (appearance largefueltank), in the original's frame.

    D=~/craft/solid/mc2/buildings/largefueltank
    python3 -I tools/art/cad_building.py decal largefueltank 0 <u0 v0 u1 v1> > $D/decal_<name>.json  (see DECALS)
    python3 -I tools/cad/largefueltank_cad.py $D > $D/largefueltank.json
    solidcraft-cli run $D/largefueltank.json --out $D/largefueltank.obj
    python3 -I tools/art/cad_building.py bake largefueltank $D/largefueltank.obj

Measured from game/assets/objects/largefueltank.glb (node BigAssTank): a decagonal drum (corner radius 8.60 m,
centre z -0.02, a corner on +x) from 4.96 to 16.15 m, on a decagonal cone from 3.75 m (radius 5.87), with a
two-step decagonal roof (5.87 m at 17.33, 2.97 m at 18.05, apex 18.30); under it a hexagonal skirt (corners on
+-z, 9.35 m at the ground to 6.82 m at 3.75). A feed pipe runs out along +x (x 5.10..11.94, about 0.83 m round,
axis at 1.37 m) into a tapered pump block (x 11.93..12.78). No cut-outs. Relief: the painted belt panel
(9.00..11.15 m) is set back 10 cm with its three painted brackets per face as real gussets, a stiffener ring under
the belt's dark top line and one under it, rim rings at the drum's top and bottom, the painted bolt rows (four a face
at 11.56 and 5.37 m) as bolt heads; the skirt's painted control panels and red hatches are 8 / 5 cm recesses and its
round ports are real 30 cm sockets; the pipe is a true cylinder with three flanges.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, cad, cad_dir  # noqa: E402

DECALS = {  # name: (material, u0, v0, u1, v1) in the upscaled atlas (only the skirt panels are used for cuts)
    "cp1": (0, .0, .57, .125, .62), "cp2": (0, .0, .665, .13, .79), "cp3": (0, .0, .83, .125, .87),
    "red": (0, .045, .325, .11, .385), "port": (0, .03, .16, .13, .29),
}
D = Path(sys.argv[1])
ZC = -0.02
B = Builder()


def deca(r, rot=0.0):
    return [(r * math.cos(math.radians(36 * k + rot)), ZC + r * math.sin(math.radians(36 * k + rot))) for k in range(10)]


def inset(r, d):  # corner radius of a decagon whose faces sit d further in
    return r - d / math.cos(math.radians(18))


R = 8.60
# ---- volumes
hex0 = [(0.01, -9.28), (8.11, -4.60), (8.11, 4.75), (0.01, 9.43), (-8.09, 4.75), (-8.09, -4.60)]
hex1 = [(0.01, -6.75), (5.92, -3.34), (5.92, 3.49), (0.01, 6.90), (-5.90, 3.49), (-5.90, -3.34)]
skirt = B.loft_y("skirt", hex0, 0.0, hex1, 3.75)
B.loft_y("cone_low", deca(5.87), 3.75, deca(R), 4.96)
YB0, YB1 = 9.00, 11.15
B.prism_y("drum_low", deca(R), 4.96, YB0)
B.prism_y("belt", deca(inset(R, 0.10)), YB0, YB1)
B.prism_y("drum_high", deca(R), YB1, 16.15)
B.loft_y("roof1", deca(R), 16.15, deca(5.87), 17.33)
B.loft_y("roof2", deca(5.87), 17.33, deca(2.97), 18.05)
B.loft_y("roof3", deca(2.97), 18.05, deca(0.25), 18.30)

# ---- rings
for nm, y0, y1, d in (("ring_belt_top", YB1, YB1 + 0.14, 0.10), ("ring_belt_low", YB0 - 0.10, YB0, 0.08),
                      ("rim_top", 16.03, 16.17, 0.08), ("rim_low", 4.96, 5.10, 0.08)):
    B.prism_y(nm, deca(R + d / math.cos(math.radians(18))), y0, y1)

# ---- per face: gussets in the belt, bolt heads
ap = R * math.cos(math.radians(18))
side = 2 * R * math.sin(math.radians(18))
for k in range(10):
    a = math.radians(36 * k + 18)  # face normal direction
    n = np.array([math.cos(a), 0.0, math.sin(a)])
    t = np.array([-math.sin(a), 0.0, math.cos(a)])
    b = np.array([0.0, 1.0, 0.0])
    # obox wants (t, b, n) right-handed: t x b must be n
    if np.dot(np.cross(t, b), n) < 0:
        t = -t
    c0 = np.array([0.0, 0.0, ZC]) + n * ap
    for j, f in enumerate((-0.17, 0.03, 0.22)):  # brackets at u .355 .44 .515 of the face
        B.obox(f"gusset{k}_{j}", c0 + t * f * side + n * -0.05 + b * (YB0 + YB1) / 2, t, b, n, (0.12, YB1 - YB0, 0.12))
    for j, f in enumerate((-0.39, -0.13, 0.13, 0.39)):
        for r, y in enumerate((11.56, 5.37)):
            B.obox(f"bolt{k}_{j}_{r}", c0 + t * f * side + n * 0.03 + b * y, t, b, n, (0.2, 0.2, 0.08))

# ---- skirt: panels and hatches recessed, round ports as sockets
for nm, depth in (("cp1", 0.08), ("cp2", 0.08), ("cp3", 0.08), ("red", 0.05)):
    for o in json.load(open(D / f"decal_{nm}.json"))["rects"]:
        if o["normal"][1] < 0.2:  # the same art on the cone underside: leave it painted
            continue
        o = dict(o, w=o["w"] - 0.1, h=o["h"] - 0.1)
        B.recess(skirt, o, depth)
def ngon(cz, cy, r, k=24):  # (z, y) polygon for prism_x
    return [(cz + r * math.cos(2 * math.pi * i / k), cy + r * math.sin(2 * math.pi * i / k)) for i in range(k)]


for k, o in enumerate(json.load(open(D / "decal_port.json"))["rects"]):  # horizontal 30 cm sockets
    c = o["center"]
    sx = 1 if o["normal"][0] > 0 else -1
    x_face = c[0]
    B.cut(skirt, B.prism_x(f"port{k}", ngon(c[2], c[1], 0.85), min(x_face - sx * 0.35, x_face + sx * 0.4),
                           max(x_face - sx * 0.35, x_face + sx * 0.4)))

# ---- feed pipe, flanges, pump block
PY, PR = 1.37, 0.83
def cyl_x(name, x0, x1, r):  # a 24-sided prism: the kernel's cylinders tessellate to ~1k triangles each
    B.prism_x(name, ngon(0.0, PY, r), x0, x1)
cyl_x("pipe", 5.10, 11.94, PR)
for k, x in enumerate((7.45, 9.70, 11.78)):
    cyl_x(f"flange{k}", x - 0.1, x + 0.1, PR + 0.12)
B.prism_x("pump", [(-1.53, 0.0), (1.53, 0.0), (0.85, 2.73), (-0.85, 2.73)], 11.93, 12.78)
B.box("pump_cap", (11.88, 2.73, -0.95), (12.83, 2.85, 0.95))

print(B.dump())
