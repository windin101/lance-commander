#!/usr/bin/env python3
"""CAD rebuild of the Liao guard house (appearance l_guardhouse), in the original's frame.

    D=~/craft/solid/mc2/buildings/l_guardhouse
    python3 -I tools/art/cad_building.py openings l_guardhouse > $D/openings.json
    python3 -I tools/cad/l_guardhouse_cad.py $D > $D/l_guardhouse.json
    solidcraft-cli run $D/l_guardhouse.json --out $D/l_guardhouse.obj
    python3 -I tools/art/cad_building.py bake l_guardhouse $D/l_guardhouse.obj --max-res 4096

Measured from game/assets/objects/l_guardhouse.glb (19 closed shells, mirrored in z for the two towers): the stone
core (x -3.90..3.73, z +-15.42) to 7.19 m with low end blocks (x +-7.79, z -13.72..13.89, 2.37 m); the battered
window walls (x +-9.32 at the ground to +-8.32 at 3.91 m, z -12.37..12.20) under a hipped eave roof (3.91..4.89 m),
a short second tier (4.82..5.66 m) and its hipped roof to 6.86 m; the long roof deck flares from 7.19 m to its
parapet (x -5.72..5.56, z +-17.25, 8.03..8.87 m; field at 8.24 m). On it two pagoda towers (z -13.36..-8.71 and
8.91..13.57): windowed cab 8.17..10.98 m, eave, a second storey, eave, a lantern and a spire to 17.45 m.
Relief: every cut-out window is a 20 cm recess (15 cm in the towers) with sills on the battered walls, raised
seams down both hipped roofs and the tower eaves, the deck sunk inside its parapet.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
B = Builder()


def rect(x0, x1, z0, z1):
    return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]


def trap_ribs(name, a0, a1, b0, b1, n, w=0.12, proud=0.06, f0=0.1, f1=0.9):
    """Raised seams on a planar trapezoid slope: bottom edge a0-a1, top edge b0-b1 (game points)."""
    a0, a1, b0, b1 = (np.array(p, float) for p in (a0, a1, b0, b1))
    nn = np.cross(a1 - a0, b0 - a0)
    nn /= np.linalg.norm(nn)
    if nn[1] < 0:
        nn = -nn
    for k in range(n):
        s = f0 + (f1 - f0) * k / max(n - 1, 1)
        p, q = a0 + (a1 - a0) * s, b0 + (b1 - b0) * s
        t = q - p
        L = float(np.linalg.norm(t))
        t /= L
        tx = np.cross(t, nn)
        c = (p + q) / 2 + nn * (proud / 2 - 0.02)
        B.obox(f"{name}{k}@avg", c, tx, t, nn, (w, L - 0.05, proud + 0.02))


def hip_ribs(name, ya, ra, yb, rb, nx, nz, **kw):
    """Seams on all four faces of a hipped frustum between rect ra at ya and rb at yb (x0, x1, z0, z1)."""
    x0, x1, z0, z1 = ra
    u0, u1, v0, v1 = rb
    trap_ribs(f"{name}a", (x0, ya, z1), (x1, ya, z1), (u0, yb, v1), (u1, yb, v1), nx, **kw)
    trap_ribs(f"{name}b", (x1, ya, z0), (x0, ya, z0), (u1, yb, v0), (u0, yb, v0), nx, **kw)
    trap_ribs(f"{name}c", (x0, ya, z0), (x0, ya, z1), (u0, yb, v0), (u0, yb, v1), nz, **kw)
    trap_ribs(f"{name}d", (x1, ya, z1), (x1, ya, z0), (u1, yb, v1), (u1, yb, v0), nz, **kw)


# ---- the long hall
B.box("core", (-3.90, 0.0, -15.42), (3.73, 7.19, 15.42))
B.box("ends", (-7.79, 0.0, -13.72), (7.79, 2.37, 13.89))
walls = B.loft_y("walls", rect(-9.32, 9.32, -12.37, 12.20), 0.0, rect(-8.32, 8.32, -12.37, 12.20), 3.91)
B.box("eave1", (-8.60, 3.91, -12.65), (8.60, 4.33, 12.48))
r1a, r1b = (-8.60, 8.60, -12.65, 12.48), (-6.84, 6.84, -10.89, 10.72)
B.loft_y("roof1", rect(*r1a), 4.33, rect(*r1b), 4.89)
hip_ribs("s1", 4.33, r1a, 4.89, r1b, 3, 16, w=0.12, proud=0.05, f0=0.12, f1=0.88)
B.loft_y("tier2", rect(-6.43, 6.58, -10.46, 10.42), 4.82, rect(-6.15, 6.30, -10.18, 10.14), 5.66)
r2a, r2b = (-6.64, 6.78, -10.82, 10.77), (-4.75, 4.89, -8.78, 8.73)
B.loft_y("roof2", rect(*r2a), 5.65, rect(*r2b), 6.86)
hip_ribs("s2", 5.65, r2a, 6.86, r2b, 3, 12, w=0.12, proud=0.05, f0=0.12, f1=0.88)
B.loft_y("deck_flare", rect(-5.16, 4.99, -16.69, 16.69), 7.19, rect(-5.72, 5.56, -17.25, 17.25), 8.03)
deck = B.box("deck", (-5.72, 8.03, -17.25), (5.56, 8.87, 17.25))
B.cut(deck, B.box("deck_field", (-5.37, 8.24, -16.89), (5.20, 9.0, 16.89)))

# ---- the two pagoda towers (mirrored in z)
cabs = {}
for s, (za, zb) in (("n", (-13.36, -8.71)), ("s", (8.91, 13.57))):
    def zz(a, b):  # the north tower's z range a..b, mirrored for the south one (the original is 18 cm off)
        return (a, b) if s == "n" else (-b + 0.20, -a + 0.20)
    cabs[s] = B.box(f"cab_{s}", (-2.05, 8.17, za), (2.22, 10.98, zb))
    e1a, e1b = (-2.96, 3.13) + zz(-14.23, -7.84), (-2.05, 2.22) + zz(-13.36, -8.71)
    B.loft_y(f"eave_{s}1", rect(*e1a), 10.98, rect(*e1b), 11.68)
    hip_ribs(f"t{s}1", 10.98, e1a, 11.68, e1b, 4, 4, w=0.07, proud=0.04)
    B.box(f"store_{s}", (-1.65, 11.68, zz(-12.99, -9.08)[0]), (1.82, 13.86, zz(-12.99, -9.08)[1]))
    e2a, e2b = (-2.22, 2.39) + zz(-13.52, -8.55), (-1.25, 1.42) + zz(-12.61, -9.46)
    B.loft_y(f"eave_{s}2", rect(*e2a), 13.86, rect(*e2b), 14.50)
    hip_ribs(f"t{s}2", 13.86, e2a, 14.50, e2b, 3, 3, w=0.06, proud=0.04)
    B.box(f"lantern_{s}", (-0.91, 14.49, zz(-12.29, -9.78)[0]), (1.08, 16.04, zz(-12.29, -9.78)[1]))
    sp = [(16.05, (-1.47, 1.64) + zz(-12.82, -9.25)), (16.46, (-0.51, 0.68) + zz(-11.91, -10.16)),
          (16.95, (-0.11, 0.28) + zz(-11.54, -10.53)), (17.45, (0.06, 0.10) + zz(-11.06, -11.02))]
    for k in range(3):
        B.loft_y(f"spire_{s}{k}", rect(*sp[k][1]), sp[k][0], rect(*sp[k + 1][1]), sp[k + 1][0])

k = 0
for o in json.load(open(D / "openings.json"))["openings"]:
    x, y, z = o["center"]
    if y < 4:
        B.recess(walls, o, 0.2)
        B.sill(f"sill{k}", o, proud=0.1, thick=0.07, overhang=0.05)
    else:
        B.recess(cabs["n" if z < 0 else "s"], o, 0.15)
    k += 1

print(B.dump())
