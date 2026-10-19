#!/usr/bin/env python3
"""CAD rebuild of the water tower (appearance watertower), in the original's frame.

    D=~/craft/solid/mc2/buildings/watertower
    python3 -I tools/cad/watertower_cad.py $D > $D/watertower.json
    solidcraft-cli run $D/watertower.json --out $D/watertower.obj
    python3 -I tools/art/cad_building.py bake watertower $D/watertower.obj

Measured from game/assets/objects/watertower.glb: the stand is four textured cards (x = +-2.585, z = -2.556 and
3.475) whose cut-outs leave four corner legs, a girt from 0.88 to 1.55 m and a head beam from 3.59 to 4.2 m; a
deck slab (x +-2.91, z -2.88..3.8) from 4.2 to 4.44 m; an octagonal tank (circumradius 2.69 m about z = 0.89)
to 8.83 m under a lid that tapers to 2.11 m at 9.37 m; a ladder card from the ground at z = -4.06 to the deck.
Relief: the legs and beams are real steel members (legs are 8 cm angles on the card planes, 0.77 x 0.9 m as the
cards draw them, lipped at the free edges; beams are a web on the card plane with 20 cm flanges), so the stand is open; the deck has a drip edge; the tank's painted
seams are raised bands (base, mid at 6.29 m, top) and a strap down the middle of each panel; the lid has an eave;
the ladder is two stringers and twelve rungs.
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

B = Builder()
XL, ZF, ZB = 2.585, -2.556, 3.475   # card planes
LW, LDF, LDB = 0.77, 0.902, 0.929   # leg widths along x, and along z at the front / back
DECK0, DECK1 = 4.2, 4.44

# ---- legs: steel angles on the two card planes (as the cards draw them), lipped at the free edges
TH = 0.08
k = 0
for sx in (-1, 1):
    for sz, dz in ((ZF, LDF), (ZB, -LDB)):
        xo, xi = sx * XL, sx * (XL - LW)
        zi = sz + dz
        x0, x1 = sorted((xo, xi))
        z0, z1 = sorted((sz, zi))
        # plate on the z card (spans x), plate on the x card (spans z)
        za, zb = sorted((sz, sz + (TH if dz > 0 else -TH)))
        B.box(f"leg{k}_a", (x0, 0.0, za), (x1, DECK0, zb))
        xa, xb = sorted((xo, xo - sx * TH))
        B.box(f"leg{k}_b", (xa, 0.0, z0), (xb, DECK0, z1))
        # 12 cm lips turned inward at the free edges
        lx0, lx1 = sorted((xi, xi + sx * TH))
        lz0, lz1 = sorted((sz, sz + (0.2 if dz > 0 else -0.2)))
        B.box(f"leg{k}_lipa@avg", (lx0, 0.0, lz0), (lx1, DECK0, lz1))
        mx0, mx1 = sorted((xo, xo - sx * 0.2))
        mz0, mz1 = sorted((zi, zi - (TH if dz > 0 else -TH)))
        B.box(f"leg{k}_lipb@avg", (mx0, 0.0, mz0), (mx1, DECK0, mz1))
        k += 1

# ---- girts and head beams between the legs: a web on the card plane, flanges 20 cm deep top and bottom
for k, (y0, y1) in enumerate(((0.876, 1.554), (3.594, DECK0))):
    for sx in (-1, 1):
        x0, x1 = sorted((sx * XL, sx * (XL - TH)))
        f0, f1 = sorted((sx * XL, sx * (XL - 0.2)))
        B.box(f"beam_x{sx:+d}_{k}", (x0, y0, ZF + LDF), (x1, y1, ZB - LDB))
        for j, (ya, yb) in enumerate(((y0, y0 + 0.06), (y1 - 0.06, y1))):
            if k == 1 and j == 1:
                continue  # the head beam's top flange would sit under the deck
            B.box(f"flange_x{sx:+d}_{k}{j}@avg", (f0, ya, ZF + LDF), (f1, yb, ZB - LDB))
    for nm, z in (("f", ZF), ("b", ZB)):
        sg = 1 if nm == "f" else -1
        z0, z1 = sorted((z, z + sg * TH))
        f0, f1 = sorted((z, z + sg * 0.2))
        B.box(f"beam_{nm}{k}", (-XL + LW, y0, z0), (XL - LW, y1, z1))
        for j, (ya, yb) in enumerate(((y0, y0 + 0.06), (y1 - 0.06, y1))):
            if k == 1 and j == 1:
                continue
            B.box(f"flange_{nm}{k}{j}@avg", (-XL + LW, ya, f0), (XL - LW, yb, f1))

# ---- deck slab with a drip edge
B.box("deck", (-2.91, DECK0, -2.88), (2.91, DECK1, 3.80), chamfer=0.03)
B.box("drip", (-2.95, DECK0 - 0.06, -2.92), (2.95, DECK0 + 0.04, 3.84))

# ---- tank, lid, bands, straps
R0, R1, ZC, T0, T1, TOP = 2.69, 2.11, 0.89, DECK1, 8.83, 9.37


def octa(r):
    return [(r * math.cos(math.radians(45 * i)), ZC + r * math.sin(math.radians(45 * i))) for i in range(8)]


B.prism_y("tank", octa(R0), T0, T1)
B.loft_y("lid", octa(R0), T1, octa(R1), TOP)
B.prism_y("eave", octa(R0 + 0.08), T1 - 0.02, T1 + 0.08)
for k, (y0, y1) in enumerate(((T0, T0 + 0.12), (6.23, 6.35), (T1 - 0.14, T1 - 0.02))):
    B.prism_y(f"band{k}", octa(R0 + 0.04), y0, y1)
ap = R0 * math.cos(math.radians(22.5))
for i in range(8):
    a = math.radians(22.5 + 45 * i)
    n = np.array([math.cos(a), 0.0, math.sin(a)])
    t = np.array([-n[2], 0.0, n[0]])
    c = np.array([0.0, (T0 + T1) / 2, ZC]) + n * (ap + 0.015)
    B.obox(f"strap{i}", c, t, np.cross(n, t), n, (0.1, T1 - T0 - 0.2, 0.05))

# ---- ladder: from (z -4.06, y 0) to (z -2.88, y 4.42), 1.14 m wide
foot, head = np.array([0.0, 0.0, -4.03]), np.array([0.0, DECK1 - 0.02, -2.91])
up = head - foot
L = np.linalg.norm(up)
b = up / L
t = np.array([1.0, 0.0, 0.0])
n = np.cross(t, b)
for k, sx in enumerate((-0.52, 0.52)):
    B.obox(f"stringer{k}@5a5c5e", (foot + head) / 2 + t * sx, t, b, n, (0.07, L, 0.1))
for k in range(12):
    c = foot + up * (k + 0.6) / 12.4
    B.obox(f"rung{k}@6a6c6e", c, t, b, n, (0.98, 0.05, 0.05))

print(B.dump())
