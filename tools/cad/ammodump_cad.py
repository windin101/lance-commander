#!/usr/bin/env python3
"""CAD rebuild of the ammunition bunker (appearance ammodump), in the original's frame.

    D=~/craft/solid/mc2/buildings/ammodump
    python3 -I tools/art/cad_building.py openings ammodump > $D/openings.json
    python3 -I tools/art/cad_building.py decal ammodump 0 <u0 v0 u1 v1> > $D/decal_<name>.json   (see DECALS)
    python3 -I tools/cad/ammodump_cad.py $D > $D/ammodump.json
    solidcraft-cli run $D/ammodump.json --out $D/ammodump.obj
    python3 -I tools/art/cad_building.py bake ammodump $D/ammodump.obj

Measured from game/assets/objects/ammodump.glb (vertices listed by height): an 0.87 m plinth
(x -2.8..11.32, z -2.79..11.34) under walls sloping 17 degrees in to a 5.77 m top (x -1.2..9.77, z -1.23..9.74)
with a 9 cm roof cap to 5.86 m; front and back a vertical-sided notch (x 1.77..6.74) to the garage-door wall
(z -1.24 / 9.78), its floor a 1.2 m slab with a painted grate; on each side a door booth (to 3.62 m) reached by a
painted stair ramp. Relief: the roof's painted asphalt pad is a 6 cm recess inside a raised rim (the cap overhangs
8 cm, chamfered); the side walls' two painted panel seams are real grooves; the sloped corners are chamfered;
the plinth stands 4 cm proud as a ledge; the stair ramps are five real steps between stringers; the booth doors
are 10 cm recesses under a cap; the garage doors get a proud frame; the grate's four slots are real
recesses (a sign recess and a door hood were tried: the painted sign runs behind the door top and read broken).
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

DECALS = {  # name: (material, u0, v0, u1, v1) in the upscaled atlas, for cad_building.py decal
    "sign": (0, 0.148, 0.045, 0.272, 0.125), "roofpad": (0, 0.04, 0.615, 0.865, 1.0),
    "sidedoor": (0, 0.262, 0.41, 0.355, 0.56), "garagedoor": (0, 0.0, 0.36, 0.24, 0.575),
    "slot_s0": (0, 0.92, 0.646, 0.95, 0.719), "slot_s1": (0, 0.92, 0.730, 0.95, 0.805),
    "slot_s2": (0, 0.92, 0.814, 0.95, 0.889), "slot_s3": (0, 0.92, 0.900, 0.95, 0.973),
}
D = Path(sys.argv[1])
XC = (-2.8 + 11.32) / 2  # the bunker's mirror plane in x


def rects(name):
    return json.load(open(D / f"decal_{name}.json"))["rects"]


B = Builder()

# ---- plinth, 4 cm proud, notched front and back where the door slabs stand
P0, P1, Z0, Z1 = -2.84, 11.36, -2.83, 11.38
plinth = [(P0, Z0), (1.77, Z0), (1.77, -1.24), (6.74, -1.24), (6.74, Z0), (P1, Z0),
          (P1, Z1), (6.74, Z1), (6.74, 9.78), (1.77, 9.78), (1.77, Z1), (P0, Z1)]
B.prism_y("plinth", plinth, 0.0, 0.87)

# ---- sloped walls: a frustum, its four corners chamfered, notched for the doors
lo_r = [(-2.8, -2.79), (11.32, -2.79), (11.32, 11.34), (-2.8, 11.34)]
hi_r = [(-1.2, -1.23), (9.77, -1.23), (9.77, 9.74), (-1.2, 9.74)]
walls = B.loft_y("walls", lo_r, 0.87, hi_r, 5.77)
corners = [((a[0] + b[0]) / 2, (0.87 + 5.77) / 2, (a[1] + b[1]) / 2) for a, b in zip(lo_r, hi_r)]
B.c("solid.chamfer", edges=[[round(c[0] * 1000, 2), round(-c[2] * 1000, 2), round(c[1] * 1000, 2)] for c in corners],
    distance=150, body=walls)
B.cut(walls, B.box("notch_f", (1.77, 0.5, -3.2), (6.74, 6.3, -1.24)))
B.cut(walls, B.box("notch_b", (1.77, 0.5, 9.78), (6.74, 6.3, 11.8)))

# side-wall panel seams (painted at z 1.93 and 6.61): 5 cm grooves, 3 cm deep
for k, (x, n) in enumerate(((-2.0, (-0.958, 0.2866, 0.0)), (10.52, (0.958, 0.2866, 0.0)))):
    for j, z in enumerate((1.93, 6.61)):
        n_ = np.array(n)
        b = np.cross(n_, [0.0, 0.0, 1.0])
        b = b if b[1] > 0 else -b
        t = np.cross(b, n_)
        # a point on the wall plane at mid-height
        y = 3.32
        xw = -2.8 + 1.6 * (y - 0.87) / 4.9 if x < 4 else 11.32 - 1.55 * (y - 0.87) / 4.9
        B.cut(walls, B.obox(f"seam{k}{j}", np.array([xw, y, z]), t, b, n_, (0.05, 5.6, 0.06)))

# ---- roof cap: 8 cm overhang, chamfered, the asphalt pad a 6 cm recess inside the rim
cap = B.box("cap", (-1.33, 5.62, -1.31), (9.85, 5.86, 9.86), chamfer=0.04)
for o in rects("roofpad"):
    if o["center"][1] > 5:
        B.recess(cap, o, 0.06)

# ---- door slabs with the grate's four slots
for side, (za, zb) in (("f", (-2.64, -1.24)), ("b", (9.78, 11.19))):
    s = B.box(f"slab_{side}", (1.77, 0.0, za), (6.74, 1.2, zb))
    for k in range(4):
        for o in rects(f"slot_s{k}"):
            if (o["center"][2] < 4) == (side == "f"):
                B.recess(s, o, 0.08)

# ---- garage doors: the original's 17 cm slab, a proud frame (top and sides) and a hood
for side, (zw, sgn) in (("f", (-1.24, -1.0)), ("b", (9.78, 1.0))):
    zd = zw + sgn * 0.17
    B.box(f"gdoor_{side}", (2.9, 1.2, min(zw, zd)), (5.77, 4.27, max(zw, zd)))
    zf = (min(zw, zw + sgn * 0.26), max(zw, zw + sgn * 0.26))
    B.box(f"gframe_{side}0", (2.74, 1.2, zf[0]), (2.9, 4.42, zf[1]))
    B.box(f"gframe_{side}1", (5.77, 1.2, zf[0]), (5.93, 4.42, zf[1]))
    B.box(f"gframe_{side}2", (2.74, 4.27, zf[0]), (5.93, 4.42, zf[1]))

# ---- side door booths, caps, door recesses, real stairs between stringers
RISE, NSTEP = 1.16 / 5, 5
for side, sgn in (("l", -1.0), ("r", 1.0)):
    def mx(x):  # mirror a left-side x to this side
        return x if sgn < 0 else 2 * XC - x
    xa, xb = sorted((mx(-2.78), mx(-1.4)))
    booth = B.box(f"booth_{side}", (xa, 0.87, 3.31), (xb, 3.62, 5.01))
    xa, xb = sorted((mx(-2.86), mx(-1.6)))
    B.box(f"bcap_{side}", (xa, 3.62, 3.23), (xb, 3.72, 5.09), chamfer=0.03)
    for o in rects("sidedoor"):
        if (o["center"][0] < 4) == (sgn < 0):
            B.recess(booth, dict(o, w=1.12, h=2.1, center=[o["center"][0], 2.33, o["center"][2]]), 0.10)
    run = (3.87 - 2.78) / NSTEP
    for i in range(NSTEP):
        xa, xb = sorted((mx(-3.87 + i * run), mx(-2.78)))
        B.box(f"step_{side}{i}", (xa, 0.0, 3.37), (xb, (i + 1) * RISE, 4.95))
    prof = [(mx(-3.93), 0.0), (mx(-2.78), 0.0), (mx(-2.78), 1.32), (mx(-3.93), 0.12)]
    if sgn > 0:
        prof = prof[::-1]
    for j, (za, zb) in enumerate(((3.31, 3.37), (4.95, 5.01))):
        B.prism_z(f"stringer_{side}{j}", prof, za, zb)

print(B.dump())
