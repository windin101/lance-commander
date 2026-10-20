#!/usr/bin/env python3
"""CAD rebuild of the Steiner government hall (appearance s_gov1), in the original's frame.

    D=~/craft/solid/mc2/buildings/s_gov1
    python3 -I tools/art/cad_building.py openings s_gov1 > $D/openings.json
    python3 -I tools/art/cad_building.py decal s_gov1 3 0.38 0.60 0.585 0.99 > $D/decal_door.json
    python3 -I tools/cad/s_gov1_cad.py $D > $D/s_gov1.json
    solidcraft-cli run $D/s_gov1.json --out $D/s_gov1.obj
    python3 -I tools/art/cad_building.py bake s_gov1 $D/s_gov1.obj --max-res 4096

Measured from game/assets/objects/s_gov1.glb (20 shells): a 0.58 m plinth (x +-10.34, z -9.40..9.51) under the
two-storey hall (x -9.75..9.82, z -8.81..8.90, to 11.75 m), its mansard (to 13.33 m, flat x -5.67..5.56,
z +-4.73), the lantern (x -3.57..3.64, z +-3.5, 13.23..17.64 m) under its own mansard (to 19.66 m); two long wings
(x -8.13..-0.92, z +-6.57..29.36, 4.42 m) with hipped roofs (eaves at 4.34 m, x -8.58..-0.47, z to +-29.8, flat
ridge at 6.45 m); a 16 cm plaza with bevelled edges (x -2.77..12.75, z +-21.36) carrying two colonnades of three
columns (x 1.14/5.63/9.97, z +-18.9, 0.15..5.22 m) under a beam (5.23..5.47 m), and two lamp posts at x 11.27.
Relief: every cut-out window is a 22 cm recess with a sill, the court doors are 18 cm recesses, string courses at
the floor line (6.17 m) and the eaves, cornices under each mansard, raised seams and hip rolls on every roof,
round fluted-column shafts (the original's are 4-sided) on round bases and capitals, round lamp posts.
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




def column(name, xc, zc, y0, yb, yc, y1, rb=0.95, rs=0.56, n=20):
    """A round column (20 sides; the original's are 4-sided): a cone base y0..yb, the shaft yb..yc, a cone capital yc..y1."""
    B.loft_y(f"{name}b", ngon(xc, zc, rb, n), y0, ngon(xc, zc, rs + 0.06, n), yb)
    B.prism_y(f"{name}s", ngon(xc, zc, rs, n), yb, yc)
    B.loft_y(f"{name}c", ngon(xc, zc, rs + 0.06, n), yc, ngon(xc, zc, rb, n), y1)


def lamp(name, x, z, dx, dz, y_arm=4.55, y0=0.0):
    """A round lamp post (20 sides) at (x, z) with an arm reaching (dx, dz) to a round lantern head."""
    B.prism_y(f"{name}f", ngon(x, z, 0.14, 20), y0, y0 + 0.15)
    B.prism_y(f"{name}p", ngon(x, z, 0.09, 20), y0 + 0.15, y_arm + 0.1)
    hx, hz = x + dx, z + dz
    B.box(f"{name}a", (min(x, hx) - 0.05, y_arm, min(z, hz) - 0.05), (max(x, hx) + 0.05, y_arm + 0.1, max(z, hz) + 0.05))
    B.loft_y(f"{name}h", ngon(hx, hz, 0.12, 20), y_arm - 0.05, ngon(hx, hz, 0.19, 20), y_arm + 0.32)
    B.loft_y(f"{name}k", ngon(hx, hz, 0.22, 20), y_arm + 0.32, ngon(hx, hz, 0.05, 20), y_arm + 0.45)


# ---- ground: plinth, plaza
B.box("plinth", (-10.34, 0.0, -9.40), (10.34, 0.58, 9.51), chamfer=0.06)
B.loft_y("plaza", rect(-2.77, 12.75, -21.36, 21.36), 0.0, rect(-1.07, 11.78, -20.57, 20.57), 0.16)

# ---- hall, string courses, cornice, mansard
hall = B.box("hall", (-9.75, 0.58, -8.81), (9.82, 11.75, 8.90))
ring("course", -9.75, 9.82, -8.81, 8.90, 6.05, 6.25, 0.10)
ring("cornice", -9.75, 9.82, -8.81, 8.90, 11.45, 11.75, 0.22)
B.loft_y("mansard", rect(-10.26, 10.33, -9.32, 9.49), 11.75, rect(-5.67, 5.56, -4.72, 4.73), 13.33)
roof_seams("mr", (-10.26, 10.33, -9.32, 9.49), (-5.67, 5.56, -4.72, 4.73), 11.75, 13.33, 2.2)

# ---- lantern
lant = B.box("lantern", (-3.57, 13.23, -3.49), (3.64, 17.64, 3.53))
ring("lcorn", -3.57, 3.64, -3.49, 3.53, 17.36, 17.60, 0.16)
B.loft_y("lroof", rect(-4.02, 4.09, -3.94, 3.98), 17.56, rect(-1.29, 1.36, -1.21, 1.24), 19.66)
roof_seams("lr", (-4.02, 4.09, -3.94, 3.98), (-1.29, 1.36, -1.21, 1.24), 17.56, 19.66, 1.4, w=0.1, proud=0.06)

# ---- wings and their hipped roofs
wings = []
for k, sg in enumerate((-1, 1)):
    z0, z1 = sorted((sg * 6.57, sg * 29.36))
    wings.append(B.box(f"wing{k}", (-8.13, 0.0, z0), (-0.92, 4.42, z1)))
    ring(f"wcourse{k}", -8.13, -0.92, z0, z1, 0.0, 0.35, 0.08)
    ez0, ez1 = sorted((sg * 6.12, sg * 29.8))
    rz0, rz1 = sorted((sg * 8.85, sg * 27.15))
    B.loft_y(f"wroof{k}", rect(-8.58, -0.47, ez0, ez1), 4.34, rect(-5.85, -3.2, rz0, rz1), 6.45)
    roof_seams(f"wr{k}", (-8.58, -0.47, ez0, ez1), (-5.85, -3.2, rz0, rz1), 4.34, 6.45, 2.0)

# ---- colonnades
for k, sg in enumerate((-1, 1)):
    zc = sg * 18.91
    for j, xc in enumerate((1.135, 5.635, 9.965)):
        column(f"col{k}{j}", xc, zc, 0.15, 0.50, 4.87, 5.22)
    B.box(f"beam{k}", (-0.58, 5.22, zc - 1.26), (11.78, 5.47, zc + 1.26), chamfer=0.04)

# ---- lamp posts: round post, arm and lantern head leaning out over the court
lamp("lamp0", 11.27, -8.50, 0.0, -0.75, y0=0.16)
lamp("lamp1", 11.27, 8.50, 0.0, 0.75, y0=0.16)

# ---- windows and doors
ops = json.load(open(D / "openings.json"))["openings"]
for k, o in enumerate(ops):
    c = np.array(o["center"])
    if c[1] > 13.0:
        tgt = lant
    elif abs(c[2]) > 9.0:
        tgt = wings[0] if c[2] < 0 else wings[1]
    else:
        tgt = hall
    B.recess(tgt, o, 0.22)
    if o["h"] > 0.6 and c[1] < 13.0:  # no sills on the lantern
        B.sill(f"sill{k}", o, proud=0.10, thick=0.08, overhang=0.08)
door = D / "decal_door.json"
if door.exists():
    for o in json.load(open(door))["rects"]:
        if o["h"] < 1.5:
            continue  # the lamp heads reuse the door texture
        B.recess(hall, o, 0.18)
        B.sill(f"dhood{len(B.cmds)}", o, proud=0.20, thick=0.12, overhang=0.15, top=True)

print(B.dump())
