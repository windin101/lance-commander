#!/usr/bin/env python3
"""CAD rebuild of the meeting hall (appearance meethall), in the original's frame.

    D=~/craft/solid/mc2/buildings/meethall
    python3 -I tools/art/cad_building.py openings meethall > $D/openings.json
    python3 -I tools/art/cad_building.py decal meethall 0 0.146 0.518 0.254 0.612 > $D/decal_door.json
    python3 -I tools/cad/meethall_cad.py $D > $D/meethall.json
    solidcraft-cli run $D/meethall.json --out $D/meethall.obj
    python3 -I tools/art/cad_building.py bake meethall $D/meethall.obj

Measured from game/assets/objects/meethall.glb (node Box01): a hall (x +-6.19, z -10.27..2.09) with 8.84 m walls
under a barrel roof whose six facets sit on a half-ellipse (half-width 6.19, rise 4.03 to 12.87 m); two lean-to
wings (x 6.19..11.55 each side, z -10.27..10.67) sloping from 4.8 to 3.94 m, so the plan is a U round a courtyard
closed by two 3.58 m walls (z 10.38..10.67) either side of a 3.18 m gate; a fanlight cut out of each gable.
Relief: the barrel roof is a true 32-segment half-ellipse with the lapped-sheet steps painted along it (texture
v 0.097..0.28) raised as strips and a ridge cap; the wing roofs are 15 cm slabs with an eave and raised seams on
the twelve painted seam lines; the fanlights are 20 cm half-elliptical recesses with a proud arched frame, a sill
and the centre mullion; windows 15 cm recesses with sills, the courtyard door 20 cm under a hood; the courtyard
walls carry a coping.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
B = Builder()
OPEN = json.load(open(D / "openings.json"))["openings"]
HX, Z0, Z1, WALL, A, RISE = 6.19, -10.27, 2.09, 8.84, 6.19, 4.03
WX, WZ1, WHI, WLO = 11.55, 10.67, 4.8, 3.94


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def arch(a, b, y0, n=32):
    """Half-ellipse from +x to -x (counter-clockwise), centred at (0, y0)."""
    return [(a * math.cos(math.pi * i / n), y0 + b * math.sin(math.pi * i / n)) for i in range(n + 1)]


# ---- hall with the barrel roof
hall = B.prism_z("hall", [(-HX, 0.0), (HX, 0.0)] + arch(A, RISE, WALL)[:-1] + [(-HX, WALL)], Z0, Z1)

# lapped-sheet steps on the painted lines: v -> facet point -> onto the ellipse
FAC = [(0.048, 6.19), (0.115, 5.79), (0.171, 4.71), (0.24, 2.82), (0.324, 0.0)]


def v_to_x(v):
    for (v0, x0), (v1, x1) in zip(FAC, FAC[1:]):
        if v <= v1:
            return x0 + (v - v0) / (v1 - v0) * (x1 - x0)
    return 0.0


for k, v in enumerate((0.097, 0.145, 0.19, 0.237, 0.28)):
    for s in (1, -1):
        x = v_to_x(v)
        th = math.acos(min(1.0, x / A))
        p = np.array([s * A * math.cos(th), WALL + RISE * math.sin(th)])
        n = unit([s * math.cos(th) / A, math.sin(th) / RISE])
        t = np.array([n[1], -n[0]])
        poly = [p - n * 0.02 - t * 0.05, p - n * 0.02 + t * 0.05, p + n * 0.04 + t * 0.05, p + n * 0.04 - t * 0.05]
        B.prism_z(f"lap{k}{'rl'[s > 0]}@avg", [tuple(q) for q in poly], Z0 - 0.04, Z1 + 0.04)
ridge = [(-0.18, WALL + RISE - 0.03), (0.18, WALL + RISE - 0.03), (0.15, WALL + RISE + 0.06), (-0.15, WALL + RISE + 0.06)]
B.prism_z("ridge@avg", ridge, Z0 - 0.06, Z1 + 0.06)

# ---- wings: walls up under a 15 cm roof slab with an eave; seams on the painted lines
T, OV = 0.15, 0.25
sl = (WHI - WLO) / (WX - HX)
seam_v = (0.049, 0.095, 0.143, 0.187, 0.233, 0.275, 0.32, 0.366, 0.413, 0.457, 0.503, 0.548)
for s in (1, -1):
    nm = "wr" if s > 0 else "wl"
    poly = [(s * HX, 0.0), (s * WX, 0.0), (s * WX, WLO - T), (s * HX, WHI - T)]
    if s < 0:
        poly = poly[::-1]
    wing = B.prism_z(f"{nm}_body", poly, Z0, WZ1)
    top = [(s * HX, WHI), (s * (WX + OV), WLO - sl * OV), (s * (WX + OV), WLO - sl * OV - T), (s * HX, WHI - T)]
    if s < 0:
        top = top[::-1]
    B.prism_z(f"{nm}_roof", top, Z0 - OV, WZ1 + OV)
    d = unit([s * (WX - HX), WLO - WHI, 0.0])
    for k, v in enumerate(seam_v):
        z = Z0 + (v - 0.004) / 0.582 * (WZ1 - Z0)
        p0 = np.array([s * HX, WHI, z])
        L = (WX + OV - HX) / abs(d[0])
        nrm = unit(np.cross(d, [0, 0, 1])) * (1 if s > 0 else -1)
        if nrm[1] < 0:
            nrm = -nrm
        B.obox(f"{nm}_seam{k}@avg", p0 + d * L / 2 + nrm * 0.02, d, nrm, np.cross(d, nrm), (L, 0.1, 0.1))
    globals()[nm] = wing

# ---- courtyard walls with a coping, gate gap |x| < 1.59
cw = {}
for s in (1, -1):
    x0, x1 = sorted((s * 1.59, s * HX))
    cw[s] = B.box(f"court{'rl'[s > 0]}", (x0, 0.0, 10.38), (x1, 3.58, 10.67))
    B.box(f"coping{'rl'[s > 0]}@avg", (x0 - 0.05 * (s < 0), 3.58, 10.32), (x1 + 0.05 * (s > 0), 3.7, 10.73))

# ---- fanlights: half-elliptical recess, arched frame, sill, centre mullion
FA, FB, FY = 5.7, 3.3, 9.2
for zf, sgn in ((Z1, 1), (Z0, -1)):
    tag = "f" if sgn > 0 else "b"
    inner = arch(FA, FB, FY)
    za, zb = sorted((zf + sgn * 0.05, zf - sgn * 0.2))
    B.prism_z(f"fantool{tag}", inner, za, zb)
    B.cut(hall, f"fantool{tag}")
    outer = arch(FA + 0.22, FB + 0.18, FY)
    ring = outer + inner[::-1]
    za, zb = sorted((zf - sgn * 0.02, zf + sgn * 0.07))
    B.prism_z(f"fanframe{tag}@avg", ring, za, zb)
    B.box(f"fansill{tag}", (-FA - 0.3, FY - 0.14, min(zf, zf + sgn * 0.12)), (FA + 0.3, FY, max(zf, zf + sgn * 0.12)))
    zc0, zc1 = sorted((zf - sgn * 0.12, zf + sgn * 0.02))
    B.box(f"fanmullion{tag}", (-0.09, FY, zc0), (0.09, FY + FB, zc1))


# ---- windows and the courtyard door
def target(o):
    x, y, z = o["center"]
    n = o["normal"]
    if abs(z - 10.67) < 0.05 or abs(z - 10.38) < 0.05:
        return cw[1] if x > 0 else cw[-1]
    if abs(abs(x) - WX) < 0.05 or (abs(abs(x) - HX) < 0.05 and y < WHI - T and z > Z1):
        return wr if x > 0 else wl  # noqa: F821
    if (abs(z - Z0) < 0.05 or abs(z - WZ1) < 0.05) and abs(x) > HX:
        return wr if x > 0 else wl  # noqa: F821
    return hall


k = 0
for o in OPEN:
    if o["center"][1] > WALL:
        continue
    B.recess(target(o), o, 0.15)
    B.sill(f"sill{k}", o, proud=0.1, thick=0.06, overhang=0.06)
    k += 1
for o in json.load(open(D / "decal_door.json"))["rects"]:
    B.recess(hall, o, 0.2)
    B.sill("doorhood", o, proud=0.3, thick=0.08, overhang=0.15, top=True)

print(B.dump())
