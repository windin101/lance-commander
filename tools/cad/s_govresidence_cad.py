#!/usr/bin/env python3
"""CAD rebuild of the Steiner governor's residence (appearance s_govresidence), in the original's frame.

    D=~/craft/solid/mc2/buildings/s_govresidence
    python3 -I tools/art/cad_building.py openings s_govresidence > $D/openings.json
    python3 -I tools/art/cad_building.py decal s_govresidence 3 0.38 0.60 0.585 0.99 > $D/decal_door.json
    python3 -I tools/cad/s_govresidence_cad.py $D > $D/s_govresidence.json
    solidcraft-cli run $D/s_govresidence.json --out $D/s_govresidence.obj
    python3 -I tools/art/cad_building.py bake s_govresidence $D/s_govresidence.obj --max-res 4096

Measured from game/assets/objects/s_govresidence.glb (6 shells): the one-storey hall (x -11.02..10.99, z +-9.58,
to 3.94 m; the entrance bay x +-3.36 on the -z front) under a mansard rim (eaves x +-11.88, z +-10.46, to a flat
roof x +-10.41, z +-8.99 at 5.56 m); two L-shaped 1.3 m garden walls (75 cm thick) framing the forecourt
(x -8.79..-2.64 and 2.57..8.72, z -21.01..-9.55), the paved path (x +-1.52, z -20.93..-7.38) and a lamp post at
(-4.42, -18.27).
Relief: cut-out windows are 22 cm recesses with sills, the door an 18 cm recess under a hood, a plinth course and a cornice, raised seams and hip rolls on the mansard, a coping round
the flat roof, a wall coping, a raised kerbed path, a round lamp post.
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
N = 24


def ngon(cx, cz, r, n=N):
    return [(cx + r * math.cos(2 * math.pi * (k + 0.5) / n), cz + r * math.sin(2 * math.pi * (k + 0.5) / n)) for k in range(n)]


def rect(x0, x1, z0, z1):
    return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]


def ring(name, x0, x1, z0, z1, y0, y1, p, colour=""):
    B.box(f"{name}0{colour}", (x0 - p, y0, z0 - p), (x1 + p, y1, z0 + 0.02))
    B.box(f"{name}1{colour}", (x0 - p, y0, z1 - 0.02), (x1 + p, y1, z1 + p))
    B.box(f"{name}2{colour}", (x0 - p, y0, z0 + 0.02), (x0 + 0.02, y1, z1 - 0.02))
    B.box(f"{name}3{colour}", (x1 - 0.02, y0, z0 + 0.02), (x1 + p, y1, z1 - 0.02))


def roof_seams(name, lo, hi, y0, y1, spacing, w=0.12, proud=0.07):
    """Raised seams down the four slopes of a hipped frustum (lo/hi = (x0, x1, z0, z1) at y0/y1) and hip rolls."""
    L = [np.array([lo[0], y0, lo[2]]), np.array([lo[1], y0, lo[2]]), np.array([lo[1], y0, lo[3]]), np.array([lo[0], y0, lo[3]])]
    H = [np.array([hi[0], y1, hi[2]]), np.array([hi[1], y1, hi[2]]), np.array([hi[1], y1, hi[3]]), np.array([hi[0], y1, hi[3]])]
    k = 0
    normals = []
    for s in range(4):
        a0, a1, b0, b1 = L[s], L[(s + 1) % 4], H[s], H[(s + 1) % 4]
        n = np.cross(a1 - a0, b0 - a0)
        n /= np.linalg.norm(n)
        if n[1] < 0:
            n = -n
        normals.append(n)
        cnt = int(np.linalg.norm(a1 - a0) / spacing)
        for i in range(1, cnt):
            f = i / cnt
            p0, p1 = a0 + (a1 - a0) * f, b0 + (b1 - b0) * f
            # keep seams on the trapezoid: skip those that would leave the slope near the hips
            fl = np.linalg.norm(b1 - b0) / np.linalg.norm(a1 - a0)
            if not (0.5 - fl / 2 + 0.02 < f < 0.5 + fl / 2 - 0.02):
                continue
            t = (p1 - p0) / np.linalg.norm(p1 - p0)
            bb = np.cross(n, t)
            B.obox(f"{name}s{k}", (p0 + p1) / 2 + n * proud / 2, t, bb, n, (np.linalg.norm(p1 - p0), w, proud))
            k += 1
    for s in range(4):  # hip rolls along the four corners
        p0, p1 = L[s], H[s]
        n = normals[s] + normals[(s - 1) % 4]
        n /= np.linalg.norm(n)
        t = (p1 - p0) / np.linalg.norm(p1 - p0)
        n = n - t * (n @ t)
        n /= np.linalg.norm(n)
        bb = np.cross(n, t)
        B.obox(f"{name}h{s}", (p0 + p1) / 2 + n * 0.04, t, bb, n, (np.linalg.norm(p1 - p0) + 0.1, 0.22, 0.16))




def column(name, xc, zc, y0, yb, yc, y1, rb=0.95, rs=0.56):
    """A round column (24 sides; the original's are 4-sided): a cone base y0..yb, the shaft yb..yc, a cone capital yc..y1."""
    B.loft_y(f"{name}b", ngon(xc, zc, rb), y0, ngon(xc, zc, rs + 0.06), yb)
    B.prism_y(f"{name}s", ngon(xc, zc, rs), yb, yc)
    B.loft_y(f"{name}c", ngon(xc, zc, rs + 0.06), yc, ngon(xc, zc, rb), y1)


def lamp(name, x, z, dx, dz, y_arm=4.55, y0=0.0):
    """A round lamp post (20 sides) at (x, z) with an arm reaching (dx, dz) to a round lantern head."""
    B.prism_y(f"{name}f", ngon(x, z, 0.14, 20), y0, y0 + 0.15)
    B.prism_y(f"{name}p", ngon(x, z, 0.09, 20), y0 + 0.15, y_arm + 0.1)
    hx, hz = x + dx, z + dz
    B.box(f"{name}a", (min(x, hx) - 0.05, y_arm, min(z, hz) - 0.05), (max(x, hx) + 0.05, y_arm + 0.1, max(z, hz) + 0.05))
    B.loft_y(f"{name}h", ngon(hx, hz, 0.12, 20), y_arm - 0.05, ngon(hx, hz, 0.19, 20), y_arm + 0.32)
    B.loft_y(f"{name}k", ngon(hx, hz, 0.22, 20), y_arm + 0.32, ngon(hx, hz, 0.05, 20), y_arm + 0.45)

# ---- hall, plinth course, cornice, entrance bay, mansard rim, flat roof coping
hall = B.box("hall", (-11.02, 0.01, -9.58), (10.99, 3.94, 9.58))
ring("plinth", -11.02, 10.99, -9.58, 9.58, 0.0, 0.40, 0.08)
ring("cornice", -11.02, 10.99, -9.58, 9.58, 3.70, 3.94, 0.18)
B.loft_y("mansard", rect(-11.88, 11.88, -10.46, 10.46), 3.94, rect(-10.41, 10.41, -8.99, 8.99), 5.56)
roof_seams("mr", (-11.88, 11.88, -10.46, 10.46), (-10.41, 10.41, -8.99, 8.99), 3.94, 5.56, 2.2)
ring("coping", -10.30, 10.30, -8.88, 8.88, 5.56, 5.70, 0.11)


# ---- garden walls with copings, path, lamp
for k, sg in enumerate((-1, 1)):
    xo, xi, xe = sg * 8.755, sg * 8.005, sg * 2.605
    poly = [(xo, -21.01), (xe, -21.01), (xe, -20.26), (xi, -20.26), (xi, -9.55), (xo, -9.55)]
    if sg > 0:
        poly = poly[::-1]
    B.prism_y(f"gwall{k}", poly, 0.0, 1.2)
    B.prism_y(f"gcope{k}", poly, 1.2, 1.32)
B.box("path", (-1.52, 0.0, -20.93), (1.52, 0.07, -9.50))
B.box("kerb0", (-1.66, 0.0, -20.93), (-1.52, 0.12, -9.50))
B.box("kerb1", (1.52, 0.0, -20.93), (1.66, 0.12, -9.50))
lamp("lamp0", -4.42, -18.27, 0.85, 0.0)

# ---- windows and door
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    B.recess(hall, o, 0.22)
    if o["h"] > 0.6:
        B.sill(f"sill{k}", o, proud=0.10, thick=0.08, overhang=0.08)
door = D / "decal_door.json"
if door.exists():
    for k, o in enumerate(json.load(open(door))["rects"]):
        if o["h"] < 1.5:
            continue  # the lamp heads reuse the door texture
        B.recess(hall, o, 0.18)
        B.sill(f"dhood{k}", o, proud=0.20, thick=0.12, overhang=0.15, top=True)

print(B.dump())
