#!/usr/bin/env python3
"""CAD rebuild of the administrative quarters (appearance s_adminquarter), in the original's frame.

    D=~/craft/solid/mc2/buildings/s_adminquarter
    python3 -I tools/art/cad_building.py openings s_adminquarter > $D/openings.json
    python3 -I tools/cad/s_adminquarter_cad.py $D > $D/s_adminquarter.json
    solidcraft-cli run $D/s_adminquarter.json --out $D/s_adminquarter.obj
    python3 -I tools/art/cad_building.py bake s_adminquarter $D/s_adminquarter.obj --glass 182,190,198   # the original's lit (white) windows

Measured from game/assets/objects/s_adminquarter.glb (triangle dump): a pentagonal plan with a 90-degree prow
at +z (the vertical planes |x| + z = 8.57 run from the ground to the roof). Walls (x +-10.40, back
at z -11.23, to 5.42 m) on a plinth (x +-11.51, back z -12.34, 0.24 m) with a sloped skirt to the wall foot
(0.48 m); a central block (x +-5.88, back z -9.73, to 8.34 m) carrying clerestory windows; a hipped roof sloping
from the block's foot (7.22 m) to eaves at x +-12.66 and z -16.50 (5.57 m), cut by the prow planes; three
square posts set diagonally (half-diagonal 0.90 m, footings 1.58 m) along z -14.43 under the back eave.
Relief: plinth chamfer, roof ribs down each slope, a fascia under the eaves, the block's roof field, the
cut-out windows recessed with sills, the posts with real footings and caps.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
B = Builder()
P = 8.57   # the prow planes: |x| + z = P


def prow_poly(half, back):
    """Pentagon: the prow apex, out to x = +-half along the prow planes, back to z = back."""
    return [(0.0, P), (half, P - half), (half, back), (-half, back), (-half, P - half)]


B.prism_y("plinth", prow_poly(11.51, -12.34), 0.0, 0.24)
B.loft_y("skirt", prow_poly(11.51, -12.34), 0.24, prow_poly(10.40, -11.23), 0.48)
walls = B.prism_y("walls", prow_poly(10.40, -11.23), 0.48, 5.42)
B.prism_y("fascia", prow_poly(12.66, -16.50), 5.42, 5.57)
# hipped roof: a loft with a vertical front far forward, trimmed by the prow planes
roof = B.loft_y("roof", [(-12.66, -16.50), (12.66, -16.50), (12.66, 9.5), (-12.66, 9.5)], 5.57,
                [(-5.88, -9.73), (5.88, -9.73), (5.88, 9.5), (-5.88, 9.5)], 7.22)
trim = B.prism_y("trim", prow_poly(12.66, -16.60), 5.50, 7.30)
B.c("solid.combine", target=roof, tools=[trim], operation="intersect")
core = B.prism_y("core", prow_poly(5.88, -9.73), 5.42, 8.34)
B.cut(core, B.prism_y("corefield", prow_poly(5.48, -9.33), 8.28, 8.60))

# ribs down the slopes, 5 cm proud, 12 cm wide, the flat colour of the art under them
T, H = 0.05, 0.12


def rib(name, a, b):
    """A rib on the roof surface from point a to point b (game coords, both on the slope)."""
    a, b = np.array(a, float), np.array(b, float)
    t = (b - a) / np.linalg.norm(b - a)
    side = np.array([0.0, 0.0, 1.0]) if abs(t[2]) < 0.5 else np.array([1.0, 0.0, 0.0])
    n = np.cross(t, side)
    if n[1] < 0:
        n = -n
    n /= np.linalg.norm(n)
    bb = np.cross(n, t)
    B.obox(name, (a + b) / 2 + n * T / 2, t, bb, n, (float(np.linalg.norm(b - a)), H, T))


def side_y(x):
    return 7.22 - (abs(x) - 5.88) / 6.78 * 1.65


k = 0
for z in np.arange(-15.5, 2.0, 2.0):          # side slopes: ribs along x
    x_in = 5.88 if z >= -9.73 else 5.88 + (-9.73 - z) / 6.77 * 6.78 + 0.15
    x_out = min(12.66, P - z - 0.15)
    if x_out - x_in < 0.6:
        continue
    for s in (1, -1):
        rib(f"rib{k}@avg", (s * x_in, side_y(x_in), z), (s * x_out, side_y(x_out), z))
        k += 1
for x in np.arange(-11.0, 11.5, 2.0):          # back slope: ribs along z
    zt = -9.73 if abs(x) <= 5.88 else -9.73 - (abs(x) - 5.88) / 6.78 * 6.77 - 0.15
    if -16.5 - zt > -0.6:
        continue
    yt = 7.22 - (-9.73 - zt) / 6.77 * 1.65
    rib(f"rib{k}@avg", (x, yt, zt), (x, 5.57, -16.5))
    k += 1

# porch posts: squares set diagonally, on stepped footings, under a cap at the eave
for j, x in enumerate((-10.61, 0.03, 10.61)):
    zc = -14.43

    def dia(r):
        return [(x + r, zc), (x, zc + r), (x - r, zc), (x, zc - r)]
    B.loft_y(f"foot{j}", dia(1.58), 0.0, dia(0.90), 0.47)
    B.prism_y(f"post{j}", dia(0.90), 0.47, 5.30)
    B.prism_y(f"postcap{j}", dia(1.05), 5.30, 5.45)

SOLIDS_Y = 5.42


def owner(o):
    return core if o["center"][1] > 5.6 else walls


for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    if abs(o["normal"][1]) > 0.5:
        continue
    B.recess(owner(o), o, 0.15)
    if o["h"] > 0.5:
        B.sill(f"sill{k}", o, proud=0.10, thick=0.06, overhang=0.05)

print(B.dump())
