#!/usr/bin/env python3
"""CAD rebuild of the Liao elite barracks (appearance l_elitebarracks), in the original's frame.

    D=~/craft/solid/mc2/buildings/l_elitebarracks
    python3 -I tools/art/cad_building.py openings l_elitebarracks > $D/openings.json
    python3 -I tools/cad/l_elitebarracks_cad.py $D > $D/l_elitebarracks.json
    solidcraft-cli run $D/l_elitebarracks.json --out $D/l_elitebarracks.obj
    python3 -I tools/art/cad_building.py bake l_elitebarracks $D/l_elitebarracks.obj --max-res 4096

Measured from game/assets/objects/l_elitebarracks.glb (four closed shells): the podium (x -12.04..3.53,
z +-21.28 at the ground, leaning in to 4.41 m, then a lip out to 4.69 m) carries a flared parapet ring (outer face
from 4.58 m out to x -12.10..3.60, z +-21.04 at 6.13 m; inner face leaning back to the 4.69 m deck); on the deck
the long barrack block (x -7.05..-0.95, z +-19.49, 2.56..9.15 m) under a two-pitch hipped roof (eave 9.14 m,
break at 9.72 m, ridge x -4.00 at 10.69 m, z +-17.52). Relief: every cut-out window is a 20 cm recess with a
sill, raised seams down both roof pitches, a drip ledge under the eave.
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


# ---- podium and parapet
B.loft_y("podium", rect(-12.04, 3.53, -21.28, 21.28), 0.0, rect(-11.78, 3.27, -20.92, 20.92), 4.41)
B.loft_y("lip", rect(-11.78, 3.27, -20.92, 20.92), 4.41, rect(-12.07, 3.57, -21.16, 21.16), 4.69)
par = B.loft_y("parapet", rect(-11.17, 2.67, -20.35, 20.35), 4.58, rect(-12.10, 3.60, -21.04, 21.04), 6.13)
B.cut(par, B.loft_y("par_in", rect(-10.63, 2.12, -19.96, 19.96), 4.66, rect(-11.01, 2.51, -20.23, 20.23), 6.25))

# ---- barrack block and roof
blk = B.box("block", (-7.05, 2.56, -19.49), (-0.95, 9.15, 19.49))
B.box("drip", (-7.15, 8.98, -19.59), (-0.85, 9.15, 19.59))
ra, rb, rc = (-7.47, -0.53, -19.88, 19.88), (-5.65, -2.35, -18.34, 18.34), (-4.02, -3.98, -17.52, 17.52)
B.loft_y("roof1", rect(*ra), 9.14, rect(*rb), 9.72)
B.loft_y("roof2", rect(*rb), 9.72, rect(*rc), 10.69)
for k, ((ya, a), (yb, b), n) in enumerate([((9.14, ra), (9.72, rb), 21), ((9.72, rb), (10.69, rc), 19)]):
    x0, x1, z0, z1 = a
    u0, u1, v0, v1 = b
    trap_ribs(f"rl{k}_", (x0, ya, z0), (x0, ya, z1), (u0, yb, v0), (u0, yb, v1), n, f0=0.04, f1=0.96)
    trap_ribs(f"rr{k}_", (x1, ya, z1), (x1, ya, z0), (u1, yb, v1), (u1, yb, v0), n, f0=0.04, f1=0.96)

k = 0
for o in json.load(open(D / "openings.json"))["openings"]:
    B.recess(blk, o, 0.2)
    B.sill(f"sill{k}", o, proud=0.1, thick=0.07, overhang=0.05)
    k += 1

print(B.dump())
