#!/usr/bin/env python3
"""CAD rebuild of the corrugated shed (appearance shack), in the original's frame.

    D=~/craft/solid/mc2/buildings/shack
    python3 -I tools/art/cad_building.py openings shack > $D/openings.json
    python3 -I tools/art/cad_building.py decal shack 0 0.2 0.745 0.345 0.94 > $D/decal_door.json
    python3 -I tools/cad/shack_cad.py $D > $D/shack.json
    solidcraft-cli run $D/shack.json --out $D/shack.obj
    python3 -I tools/art/cad_building.py bake shack $D/shack.obj --texel 0.012

Measured from game/assets/objects/shack.glb: a box x -3.043..3.022, z -2.867..2.854, eaves at 2.84 m, a gable
roof whose ridge runs along z at x = -0.01, 3.863 m (the gables face +-z). Relief, all on lines the texture
paints: the walls are real corrugated sheet (3 cm troughs on the dark lines sampled along each wall at 0.4 m, about
0.32 m apart), cover strips on the painted panel seams (x = -0.01 on the gables, z = -0.08 on the long walls) and
corner angles; the roof is lapped sheet (2 cm steps on its painted lap lines, 0.42 m apart down the slope) with
a 15 cm overhang, a ridge cap and barge boards; the cut-out window bands are 15 cm recesses with frames and
sills; the painted door (decal) is a 12 cm recess over a two-tread concrete step.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
X0, X1, Z0, Z1 = -3.043, 3.022, -2.867, 2.854
EAVE, RIDGE, XR = 2.84, 3.863, -0.01
AMP, HW, SL = 0.03, 0.04, 0.03  # trough depth, trough half-width (bottom), slope run

# trough centres (dark lines at y = 0.4 m, tools: sample the art along each wall)
T_ZFACE = [X0 + s for s in (0.18, 0.51, 0.76, 1.09, 1.39, 1.70, 2.00, 2.36, 2.66, 3.40, 3.70, 4.03, 4.36, 4.64, 4.97, 5.30, 5.55, 5.88)]
T_XPOS = [Z0 + s for s in (0.34, 0.67, 1.01, 1.32, 1.65, 1.99, 2.30, 3.30, 3.64, 4.00, 4.36, 4.67, 5.03, 5.38)]
T_XNEG = [Z0 + s for s in (0.34, 0.67, 1.01, 1.35, 1.63, 1.97, 2.31, 3.41, 3.75, 4.09, 4.47, 4.76, 5.14)]
LAPS = (0.32, 0.72, 1.11, 1.53, 1.96, 2.33, 2.75)  # roof lap lines, metres down the slope from the ridge

B = Builder()


def run_s(troughs, start, sign):
    """Trough coordinates -> distances along a wall that starts at `start` and runs in direction `sign`."""
    return [(t - start) * sign for t in troughs]


def wall(p0, p1, along, nrm):
    (ax, az), (bx, bz) = p0, p1
    L = math.hypot(bx - ax, bz - az)
    tx, tz = (bx - ax) / L, (bz - az) / L
    pts = [p0]
    for s in sorted(along):
        for ds, d in ((-HW - SL, 0), (-HW, AMP), (HW, AMP), (HW + SL, 0)):
            u = s + ds
            pts.append((round(ax + tx * u - nrm[0] * d, 4), round(az + tz * u - nrm[1] * d, 4)))
    return pts


foot = []
foot += wall((X0, Z0), (X1, Z0), run_s(T_ZFACE, X0, 1), (0, -1))     # -z gable
foot += wall((X1, Z0), (X1, Z1), run_s(T_XPOS, Z0, 1), (1, 0))       # +x long wall
foot += wall((X1, Z1), (X0, Z1), run_s(T_ZFACE, X1, -1), (0, 1))     # +z gable
foot += wall((X0, Z1), (X0, Z0), run_s(T_XNEG, Z1, -1), (-1, 0))     # -x long wall
walls = B.prism_y("walls", foot, 0.0, RIDGE)
# hollow: a 25 cm wall, so the roof-plane top is a narrow ring rather than a fan of slivers over the whole plan
B.cut(walls, B.box("hollow", (X0 + 0.25, -0.1, Z0 + 0.25), (X1 - 0.25, RIDGE + 1, Z1 - 0.25)))

# gables: cut everything above the two roof planes
kl, kr = (RIDGE - EAVE) / (XR - X0), (RIDGE - EAVE) / (X1 - XR)
E = 0.3
gable_cut = [(X0 - E, EAVE - kl * E), (XR, RIDGE), (X1 + E, EAVE - kr * E), (X1 + E, RIDGE + 1), (X0 - E, RIDGE + 1)]
B.cut(walls, B.prism_z("gablecut", gable_cut, Z0 - 0.3, Z1 + 0.3))

# a core filling the hollow up to the roof planes: bake then drops the inner wall faces (each face hidden by the other)
ci = 0.25
B.prism_z("core", [(X0 + ci, 0.0), (X1 - ci, 0.0), (X1 - ci, EAVE + kr * ci), (XR, RIDGE), (X0 + ci, EAVE + kl * ci)], Z0 + ci, Z1 - ci)

# windows (cut-out bands) and the door
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    B.recess(walls, o, 0.15)
    B.frame(f"wframe{k}", o, width=0.07, proud=0.04)
    B.sill(f"sill{k}", o, proud=0.10, thick=0.05, overhang=0.10)
for k, o in enumerate(json.load(open(D / "decal_door.json"))["rects"]):
    B.recess(walls, o, 0.12)
    B.frame(f"dframe{k}", o, width=0.06, proud=0.03)
    zc, w = o["center"][2], o["w"]
    yb = o["center"][1] - o["h"] / 2
    B.box(f"step{k}a@8f8b84", (X0 - 0.50, 0.0, zc - w / 2 - 0.15), (X0, yb / 2, zc + w / 2 + 0.15))
    B.box(f"step{k}b@8f8b84", (X0 - 0.25, yb / 2, zc - w / 2 - 0.15), (X0, yb, zc + w / 2 + 0.15))

# corner angles and seam cover strips (on the painted light strips)
C, P = 0.12, 0.03
for k, (cx, cz, sx, sz) in enumerate(((X0, Z0, -1, -1), (X1, Z0, 1, -1), (X1, Z1, 1, 1), (X0, Z1, -1, 1))):
    xa = cx - P if sx < 0 else cx + P - C
    za = cz - P if sz < 0 else cz + P - C
    B.box(f"corner{k}", (xa, 0.0, za), (xa + C, EAVE, za + C))
for k, z in enumerate((Z0, Z1)):
    sg = 1 if z > 0 else -1
    B.box(f"seamz{k}", (XR - 0.07, 0.0, min(z, z + sg * P)), (XR + 0.07, RIDGE - 0.05, max(z, z + sg * P)))
for k, x in enumerate((X0, X1)):
    sg = 1 if x > 0 else -1
    B.box(f"seamx{k}", (min(x, x + sg * P), 0.0, -0.15), (max(x, x + sg * P), EAVE - 0.02, -0.01))

# roof: lapped sheet on the original planes, 15 cm overhang at the eaves, 12 cm at the gables
OV, TH, LAP = 0.15, 0.06, 0.02


def roof_side(x_eave, k):
    """Top points from the ridge down to the eave (x, y) and the slope's unit vector."""
    sgn = 1 if x_eave > XR else -1
    L = math.hypot(x_eave - XR, RIDGE - EAVE)
    ux, uy = (x_eave - XR) / L, (EAVE - RIDGE) / L        # down the slope
    nx, ny = -uy * sgn, ux * sgn                            # outward (up) normal
    if ny < 0:
        nx, ny = -nx, -ny
    top = []
    for s in LAPS:
        for ds, h in ((-0.002, TH + LAP), (0.002, TH)):
            u = s + ds
            top.append((XR + ux * u + nx * h, RIDGE + uy * u + ny * h))
    u = L + OV
    top.append((XR + ux * u + nx * (TH + LAP), RIDGE + uy * u + ny * (TH + LAP)))
    bottom_eave = (XR + ux * u, RIDGE + uy * u)
    return top, bottom_eave, (nx, ny)


ZA, ZB = Z0 - 0.12, Z1 + 0.12
TRIM = "b4ae9c"  # edge flashings get a fixed colour: their nearest original point is the roof's atlas edge (u = 1),
                 # where bake's bilinear lookup wraps into the hazard stripe on the far side of the atlas
full = []
for side, xe in (("l", X0), ("r", X1)):
    top, be, (nx, ny) = roof_side(xe, None)
    L = math.hypot(xe - XR, RIDGE - EAVE)
    ux, uy = (xe - XR) / L, (EAVE - RIDGE) / L
    wall_top = (XR + ux * L + nx * (TH + LAP), RIDGE + uy * L + ny * (TH + LAP))
    wall_bot = (xe, EAVE)
    prof = [(XR, RIDGE), (XR, RIDGE + TH + LAP)] + top[:-1] + [wall_top, wall_bot]
    eave = [wall_bot, wall_top, top[-1], be]
    if side == "l":
        prof, eave = prof[::-1], eave[::-1]
    B.prism_z(f"roof_{side}", [(round(x, 4), round(y, 4)) for x, y in prof], Z0, Z1)
    B.prism_z(f"eave_{side}@{TRIM}", [(round(x, 4), round(y, 4)) for x, y in eave], ZA, ZB)
    full.append((prof, eave))
# verges: the roof's lapped profile carried 12 cm past each gable
for k, (za, zb) in enumerate(((ZA, Z0), (Z1, ZB))):
    for side, (prof, eave) in zip("lr", full):
        B.prism_z(f"verge{k}{side}@{TRIM}", [(round(x, 4), round(y, 4)) for x, y in prof], za, zb)
# ridge cap: a shallow inverted V over the ridge
cap_h = RIDGE + TH + LAP
B.prism_z(f"ridgecap@{TRIM}", [(XR - 0.28, cap_h - 0.28 * kl + 0.005), (XR, cap_h + 0.06), (XR + 0.28, cap_h - 0.28 * kr + 0.005),
                       (XR + 0.28, cap_h - 0.28 * kr - 0.03), (XR, cap_h + 0.02), (XR - 0.28, cap_h - 0.28 * kl - 0.03)], ZA - 0.02, ZB + 0.02)
# barge boards along the gable edges, under the roof's overhang
for k, z in enumerate((Z0, Z1)):
    sg = 1 if z > 0 else -1
    za, zb = sorted((z + sg * 0.005, z + sg * 0.06))
    band = [(X0 - OV * 0.9, EAVE - kl * OV * 0.9), (XR, RIDGE), (X1 + OV * 0.9, EAVE - kr * OV * 0.9),
            (X1 + OV * 0.9, EAVE - kr * OV * 0.9 - 0.16), (XR, RIDGE - 0.16), (X0 - OV * 0.9, EAVE - kl * OV * 0.9 - 0.16)]
    B.prism_z(f"barge{k}@{TRIM}", band, za, zb)

print(B.dump())
