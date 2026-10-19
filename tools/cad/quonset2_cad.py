#!/usr/bin/env python3
"""CAD rebuild of the Quonset hut with a roof dish (appearance quonset2), in the original's frame. Same texture as quonset (the same atlas, sandbags and windows) and the
same hull as tools/cad/quonset_cad.py (approved), on quonset2's own measurements, plus the roof dish.

    D=~/craft/solid/mc2/buildings/quonset2
    python3 -I tools/art/cad_building.py openings quonset2 > $D/openings.json
    python3 -I tools/cad/quonset2_cad.py $D/openings.json > $D/quonset2.json
    solidcraft-cli run $D/quonset2.json --out $D/quonset2.obj
    python3 -I tools/art/cad_building.py bake quonset2 $D/quonset2.obj

Measured from game/assets/objects/quonset2.glb: a 10-facet half-cylinder, radius 4.24 m, z = -12.72 to 4.18, with
quonset's UV layout (crown v 0.001-0.004, 0.1 v a facet), so the corrugation phase is quonset's. On the roof, at
x -3.26..-0.01, z -9.93..-7.19, a green equipment box (top 4.26 m) carries a 3-sided pyramid pedestal and a hexagonal
dish (rim radius 1.41 m about (-2.09, 5.71, -8.08), facing (-0.47, 0.34, 0.81), dished 0.36 m, back 0.64 m). Here
the box gets chamfered top edges and a vent grille, the pedestal is a round cone with a neck, and the dish is a true
round (32-sided) dish with a concave face, a rim lip and a feed horn on its axis (issue I77: round parts are round).
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from building_cad import Builder, cad, cad_dir, axis_angle  # noqa: E402

R, Z0, Z1 = 4.24, -12.723, 4.178
PITCH, TROUGH0, AMP = 0.627, 0.596, 0.03
LIP, INSET = 0.12, 0.18

openings = json.load(open(sys.argv[1]))["openings"]
B = Builder()

# hull: corrugated half-cylinder, ridges along z
arc = math.pi * R
n = int(round(arc / PITCH * 12))
pts = []
for i in range(n + 1):
    th = math.pi * i / n                   # 0 = the +x ground line, pi/2 = crown
    s = abs(math.pi / 2 - th) * R          # arc from the crown
    r = R - AMP * math.cos(2 * math.pi * (s - TROUGH0) / PITCH)  # trough (r = R - AMP) on the painted dark line
    r -= AMP * (1 - min(1.0, th / 0.05, (math.pi - th) / 0.05))  # meet the ground cleanly
    pts.append((r * math.cos(th), max(0.0, r * math.sin(th))))
pts[0] = (pts[0][0], 0.0)
pts[-1] = (pts[-1][0], 0.0)
hull = B.prism_z("hull", pts, Z0, Z1)

# inset end walls: cut a 24-gon half disc of radius R - LIP back INSET from each end
def half_disc(rad, k=24):
    return [(rad * math.cos(math.pi * i / k), rad * math.sin(math.pi * i / k)) for i in range(k + 1)]

for z in (Z0, Z1):
    a, b = (z - 0.05, z + INSET) if z == Z0 else (z - INSET, z + 0.05)
    t = B.prism_z(f"inset{z:+.0f}", [(x, max(y, 0.0) - (0.05 if y < 1e-6 else 0)) for x, y in half_disc(R - LIP)], a, b)
    B.cut(hull, t)

# arch ribs between the side windows, one sheet bay (4.23 m) apart
outer = [(x, y) for x, y in half_disc(R + AMP + 0.06, 48)]
inner = [(x, y) for x, y in half_disc(R - AMP - 0.02, 48)][::-1]
for k, zr in enumerate((-10.62, -6.39, -2.16, 2.07)):
    B.prism_z(f"rib{k}@avg", outer + inner, zr - 0.1, zr + 0.1)

for k, o in enumerate(openings):
    end = abs(o["normal"][2]) > 0.9
    door = end and o["h"] > 1.5
    if end:
        B.recess(hull, o, 0.30 if door else 0.20, surface_shift=INSET)
        if door:  # concrete step in front of the door, 15 cm, on the ground
            zc = o["center"][2]
            sgn = 1 if o["normal"][2] > 0 else -1
            zs = zc - sgn * INSET
            B.box(f"step{k}@8f8b84", (-0.75, 0.0, min(zs, zs + sgn * 0.9)), (0.75, 0.15, max(zs, zs + sgn * 0.9)))
        else:
            B.sill(f"sill{k}", o, proud=0.10, thick=0.07, overhang=0.08, surface_shift=INSET)
    else:
        B.recess(hull, o, 0.20)
        # no hoods: on this darker hull they read as black flags past the far-side silhouette at 40 deg pitch
        B.sill(f"sill{k}", o, proud=0.10, thick=0.06, overhang=0.06)

# ---- roof equipment box (sits into the hull; the hidden part is dropped by the bake)
B.box("ebox", (-3.26, 2.55, -9.93), (-0.01, 4.26, -7.19), chamfer=0.06)
for k in range(5):  # vent louvres on the +z face
    y = 3.35 + 0.15 * k
    B.box(f"louvre{k}@avg", (-2.9, y, -7.19), (-2.0, y + 0.06, -7.13))

# ---- pedestal: round cone with a neck up to the dish back
def ngon(r, cx=0.0, cz=0.0, k=24):
    return [(cx + r * math.cos(2 * math.pi * i / k), cz + r * math.sin(2 * math.pi * i / k)) for i in range(k)]

PX, PZ = -1.62, -8.56
B.loft_y("pedestal", ngon(0.55, PX, PZ), 4.26, ngon(0.16, PX, PZ), 5.20)
F = np.array([-0.47, 0.34, 0.81]); F /= np.linalg.norm(F)
RIM = np.array([-2.09, 5.71, -8.08])
back = RIM - F * 0.60
neck0 = np.array([PX, 5.15, PZ])
d = back - neck0
L = float(np.linalg.norm(d))
B.prism_y("neck", ngon(0.09, k=20), 0.0, L)  # 20-gon prism: solid.cylinder tessellates to ~4k tris
up = np.array([0.0, 0.0, 1.0])


def turn(bodies, f):
    f = cad_dir(f / np.linalg.norm(f))
    ax = np.cross(up, f)
    ang = math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(up, f))))))
    B.c("solid.move", bodies=bodies, axis=[round(float(x), 6) for x in ax / np.linalg.norm(ax)], angle=f"{ang:.4f} deg")


turn(["neck"], d)
B.c("solid.move", bodies=["neck"], translate=cad(neck0))

# ---- the dish: built about the origin with its axis on +y, then turned onto F and moved to the rim centre
RD = 1.41
B.loft_y("dish", ngon(0.14, k=32), -0.64, ngon(RD, k=32), 0.0)
B.loft_y("dishcut", ngon(0.02, k=32), -0.34, ngon(1.55, k=32), 0.05)
B.cut("dish", "dishcut")
B.prism_y("rim", ngon(1.47, k=32), -0.04, 0.01)
B.prism_y("rimhole", ngon(1.40, k=32), -0.06, 0.03)
B.cut("rim", "rimhole")
B.prism_y("horn", ngon(0.035, k=12), -0.34, 0.56)
B.prism_y("feed", ngon(0.11, k=20), 0.56, 0.74)
parts = ["dish", "rim", "horn", "feed"]
turn(parts, F)
B.c("solid.move", bodies=parts, translate=cad(RIM))

print(B.dump())
