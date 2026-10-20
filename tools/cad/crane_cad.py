#!/usr/bin/env python3
"""CAD rebuild of the crane (appearance crane), in the original's frame.

    D=~/craft/solid/mc2/buildings/crane
    python3 -I tools/art/cad_building.py openings crane > $D/openings.json
    python3 -I tools/art/cad_building.py decal crane 0 0.04 0.924 0.092 1.0 > $D/decal_door.json
    python3 -I tools/art/cad_building.py decal crane 0 0.105 0.922 0.16 0.968 > $D/decal_win1.json
    python3 -I tools/art/cad_building.py decal crane 0 0.24 0.922 0.29 0.968 > $D/decal_win2.json
    python3 -I tools/art/cad_building.py decal crane 0 0.31 0.922 0.36 0.968 > $D/decal_win3.json
    python3 -I tools/cad/crane_cad.py $D > $D/crane.json
    solidcraft-cli run $D/crane.json --out $D/crane.obj
    python3 -I tools/art/cad_building.py bake crane $D/crane.obj

Measured from game/assets/objects/crane.glb: a lattice tower drawn as four alpha cards (x -1.25..1.34,
z -1.15..1.28, 0..5.15 m), four 0.96 m cells a face (centres 0.64, 1.92, 3.19, 4.47 m, 1.8 m wide); a cab that is a
frustum of a square turned ~40 degrees, 7.1 m across at 4.32 m to 5.1 m at the flat roof (6.54 m), windows and a
door painted on its sloped faces; a triangular lattice boom (three alpha cards, twelve cells a face) from the cab's
side up to the head at (6.6, 14.2, -6.9); a cable down to a hexagonal hook block (x 6.5..6.75) and a hook.
Relief: the tower is real legs and girts on the cards' painted members; the boom three chords with struts between
the cells and a zigzag diagonal a cell; the windows and door 15 cm recesses with sills, the cab a roof slab with an eave; the cable a rod, the
block a chamfered plate on a sheave, the hook a bent bar.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, cad, cad_dir  # noqa: E402

D = Path(sys.argv[1])
B = Builder()


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def bar(name, p0, p1, w, d=None, up=None):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    b = unit(p1 - p0)
    ref = np.asarray(up, float) if up is not None else (np.array([0.0, 1.0, 0.0]) if abs(b[1]) < 0.9 else np.array([1.0, 0.0, 0.0]))
    t = unit(np.cross(b, ref))
    n = np.cross(t, b)
    return B.obox(name, (p0 + p1) / 2, t, b, n, (w, np.linalg.norm(p1 - p0), d or w))


def ngon(r, k, cx=0.0, cy=0.0):
    return [(cx + r * math.cos(2 * math.pi * (i + 0.5) / k), cy + r * math.sin(2 * math.pi * (i + 0.5) / k)) for i in range(k)]


def cyl(name, base, n, r, h, k=24):
    """A round rod (k-gon prism) along game x or y; solid.cylinder tessellates small radii to thousands of faces."""
    x, y, z = base
    if abs(n[1]) > 0.5:
        return B.prism_y(name, ngon(r, k, x, z), y, y + h)
    return B.prism_x(name, ngon(r, k, z, y), x, x + h)


# ---- tower: legs at the corners on the painted rails, girts on the painted cell borders
X0, X1, Z0, Z1, TT = -1.25, 1.34, -1.15, 1.28, 5.15
LEG = 0.36
for k, (x, z) in enumerate(((X0, Z0), (X1, Z0), (X0, Z1), (X1, Z1))):
    xa, xb = sorted((x, x - math.copysign(LEG, x - 0.05)))
    za, zb = sorted((z, z - math.copysign(LEG, z - 0.06)))
    B.box(f"leg{k}", (xa, 0.0, za), (xb, TT, zb))
GIRTS = [(0.0, 0.16), (1.12, 1.44), (2.40, 2.71), (3.67, 3.99), (4.95, TT)]
GD = 0.14
for j, (y0, y1) in enumerate(GIRTS):
    B.box(f"girt{j}_zf", (X0 + LEG, y0, Z0), (X1 - LEG, y1, Z0 + GD))
    B.box(f"girt{j}_zb", (X0 + LEG, y0, Z1 - GD), (X1 - LEG, y1, Z1))
    B.box(f"girt{j}_xl", (X0, y0, Z0 + LEG), (X0 + GD, y1, Z1 - LEG))
    B.box(f"girt{j}_xr", (X1 - GD, y0, Z0 + LEG), (X1, y1, Z1 - LEG))
# a deck plate on the tower head, under the cab
B.box("towerdeck", (X0 - 0.05, TT - 0.12, Z0 - 0.05), (X1 + 0.05, TT, Z1 + 0.05))

# ---- cab: frustum, roof slab with an eave
BOT = [(-3.44, -0.21), (-0.22, 3.62), (3.6, 0.41), (0.39, -3.42)]
TOP = [(-2.47, -0.12), (-0.14, 2.65), (2.63, 0.32), (0.31, -2.45)]
cab = B.loft_y("cab", BOT, 4.32, TOP, 6.54)
ctr = np.mean(TOP, 0)
eave = [tuple(ctr + (np.array(p) - ctr) * 1.06) for p in TOP]
B.prism_y("roof", eave, 6.54, 6.68)
B.c("solid.chamfer", edges=[cad(((a[0] + b[0]) / 2, 6.68, (a[1] + b[1]) / 2)) for a, b in zip(eave, eave[1:] + eave[:1])],
    distance=50, body="roof")
# a skirt band round the cab's foot
cb = np.mean(BOT, 0)
sk_o = [tuple(cb + (np.array(p) - cb) * 1.012) for p in BOT]
B.prism_y("skirt", sk_o, 4.32, 4.44)

for f in ("win1", "win2", "win3"):
    for k, o in enumerate(json.load(open(D / f"decal_{f}.json"))["rects"]):
        o = dict(o, w=o["w"] - 0.12, h=o["h"] - 0.08)
        B.recess(cab, o, 0.15)
        B.sill(f"sill_{f}{k}", o, proud=0.10, thick=0.06, overhang=0.06)
for k, o in enumerate(json.load(open(D / "decal_door.json"))["rects"]):
    o = dict(o, w=o["w"] - 0.3, h=o["h"] - 0.2, center=list(np.array(o["center"]) + np.array(o["b"]) * 0.0))
    B.recess(cab, o, 0.12)
    B.sill(f"doorhood{k}", o, proud=0.12, thick=0.05, overhang=0.06, top=True)

# ---- boom: three chords, struts between the twelve cells of each face
A0, A1 = np.array([-0.70, 5.39, -1.26]), np.array([6.52, 14.28, -6.84])
B0, B1 = np.array([-0.27, 5.40, -0.74]), np.array([6.65, 14.28, -6.68])
C0, C1 = np.array([1.20, 4.45, -2.34]), np.array([6.68, 13.92, -7.01])
CH = [(A0, A1), (B0, B1), (C0, C1)]
for k, (p0, p1) in enumerate(CH):
    bar(f"chord{k}@1e1e1e", p0, p1, 0.18)
# cell centres along the boom (openings on the A-B card): s = fraction from the foot
S0, S1, NC = 0.055, 0.945, 12
step = (S1 - S0) / (NC - 1)
for j in range(NC + 1):
    s = S0 + step * (j - 0.5)
    s = min(max(s, 0.01), 0.99)
    pts = [p0 + (p1 - p0) * s for p0, p1 in CH]
    for k in range(3):
        bar(f"strut{j}_{k}@1e1e1e", pts[k], pts[(k + 1) % 3], 0.11)
    if j < NC:  # a zigzag diagonal across each face, alternating per cell
        s2 = min(max(S0 + step * (j + 0.5), 0.01), 0.99)
        nxt = [p0 + (p1 - p0) * s2 for p0, p1 in CH]
        for k in range(3):
            a, b = (pts[k], nxt[(k + 1) % 3]) if j % 2 == 0 else (pts[(k + 1) % 3], nxt[k])
            bar(f"diag{j}_{k}@1e1e1e", a, b, 0.07)
# the boom foot pin, through the cab side
bar("boompin@4a4a4a", A0 + (A0 - B0) * 0.3, B0 + (B0 - A0) * 0.3, 0.2)

# ---- cable, hook block, hook
cyl("cable@1e1e1e", (6.62, 5.0, -6.90), (0, 1, 0), 0.06, 13.95 - 5.0)
cyl("sheave@4a4a4a", (6.42, 14.0, -6.88), (1, 0, 0), 0.22, 0.4)
blk = [(-6.53, 3.59), (-6.13, 4.56), (-6.53, 5.03), (-7.27, 5.03), (-7.67, 4.56), (-7.27, 3.59)]
B.prism_x("block", [(z, y) for z, y in blk], 6.5, 6.75)
cyl("blockpin@4a4a4a", (6.44, 4.4, -6.90), (1, 0, 0), 0.12, 0.37)
cyl("hookshank@avg", (6.625, 3.15, -6.95), (0, 1, 0), 0.06, 0.46)
# the hook: a bent bar, a ring of short bars opening toward +z
HC, HR = np.array([6.625, 2.80, -7.0]), 0.28
ring = [HC + HR * np.array([0.0, math.cos(a), math.sin(a)]) for a in np.radians(np.arange(60, 360 + 61, 30))]
for k in range(len(ring) - 1):
    a, b = ring[k], ring[k + 1]
    bar(f"hook{k}@avg", a + (a - b) * 0.08, b + (b - a) * 0.08, 0.09, up=(1, 0, 0))

print(B.dump())
