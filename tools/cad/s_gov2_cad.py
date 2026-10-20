#!/usr/bin/env python3
"""CAD rebuild of the Steiner government office (appearance s_gov2), in the original's frame.

    D=~/craft/solid/mc2/buildings/s_gov2
    python3 -I tools/art/cad_building.py openings s_gov2 > $D/openings.json
    python3 -I tools/art/cad_building.py decal s_gov2 3 0.38 0.60 0.585 0.99 > $D/decal_door.json
    python3 -I tools/cad/s_gov2_cad.py $D > $D/s_gov2.json
    solidcraft-cli run $D/s_gov2.json --out $D/s_gov2.obj
    python3 -I tools/art/cad_building.py bake s_gov2 $D/s_gov2.obj --max-res 4096

Measured from game/assets/objects/s_gov2.glb (15 shells): the two-storey block (x 0.87..8.53, z -10.49..7.87,
to 8.71 m) under a hipped roof (eaves x 0.23..9.18, z -11.13..8.52, flat top x 2.57..6.83, z -9.29..6.68 at
10.53 m); the entrance pavilion (x -1.81..6.49, z 2.96..10.68, to 7.96 m) on a 26 cm slab, its roof hipped on three
sides and flush against the block on the fourth (to 8.74 m); a bevelled court (x -11.12..-1.62, z 2.72..11.04)
with two pergolas of two columns (x -9.54/-4.54, z 4.0/9.5) under 20 cm beams; an L-shaped 1.3 m garden wall
(x -9.96..0.91, z -9.91..-2.72, 58 cm thick); two lamp posts at x -12.37.
Relief: cut-out windows are 22 cm recesses with sills, the doors 18 cm recesses under a hood, a string course at
the floor line (4.34 m) and cornices under each roof, raised seams and hip rolls on the roofs, a coping on the
wall, round column shafts on round bases and capitals (the original's are 4-sided), round lamp posts.
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

# ---- block, string course, cornice, roof
blk = B.box("block", (0.87, 0.02, -10.49), (8.53, 8.71, 7.87))
ring("course", 0.87, 8.53, -10.49, 7.87, 4.24, 4.44, 0.10)
ring("cornice", 0.87, 8.53, -10.49, 7.87, 8.45, 8.71, 0.20)
B.loft_y("roof", rect(0.23, 9.18, -11.13, 8.52), 8.71, rect(2.57, 6.83, -9.29, 6.68), 10.53)
roof_seams("rf", (0.23, 9.18, -11.13, 8.52), (2.57, 6.83, -9.29, 6.68), 8.71, 10.53, 2.0)

# ---- entrance pavilion on its slab, its three-sided roof
B.box("pslab", (-2.15, -0.07, 2.61), (6.81, 0.19, 10.98), chamfer=0.05)
pav = B.box("pavilion", (-1.81, 0.19, 2.96), (6.49, 7.96, 10.68))
B.box("pcourse0", (-1.91, 5.13, 2.96), (6.59, 5.33, 10.78))
B.box("pcorn0", (-2.0, 7.72, 2.96), (6.68, 7.96, 10.87))
B.loft_y("proof", rect(-2.12, 6.8, 2.65, 10.99), 7.96, rect(0.88, 5.39, 2.65, 7.98), 8.74)

# ---- court, pergolas, garden wall, lamps
B.loft_y("court", rect(-11.12, -1.62, 2.72, 11.04), 0.0, rect(-10.9, -1.84, 2.96, 10.79), 0.18)
for k, (za, zb) in enumerate(((2.94, 5.03), (8.4, 10.49))):
    zc = (za + zb) / 2
    for j, xc in enumerate((-9.535, -4.535)):
        column(f"col{k}{j}", xc, zc, 0.15, 0.65, 4.29, 4.58)
    B.box(f"beam{k}", (-11.19, 4.58, za), (-3.3, 4.79, zb), chamfer=0.03)
B.prism_y("wall", [(-9.96, -9.91), (0.91, -9.91), (0.85, -9.33), (-9.37, -9.33), (-9.37, -2.72), (-9.96, -2.72)], 0.0, 1.2)
B.prism_y("wcope", [(-10.03, -9.98), (0.98, -9.98), (0.92, -9.26), (-9.30, -9.26), (-9.30, -2.65), (-10.03, -2.65)], 1.2, 1.32)
lamp("lamp0", -12.37, 2.95, 0.0, 0.85, y0=-0.04)
lamp("lamp1", -12.34, 10.76, 0.0, -0.85, y0=-0.04)

# ---- windows and doors
PAV = ((-1.81, 0.19, 2.96), (6.49, 7.96, 10.68))
BLK = ((0.87, 0.02, -10.49), (8.53, 8.71, 7.87))


def on_box(c, box, tol=0.06):
    lo, hi = np.array(box[0]), np.array(box[1])
    inside = np.all(c > lo - tol) and np.all(c < hi + tol)
    return inside and (np.abs(c - lo) < tol).any() | (np.abs(c - hi) < tol).any()


def owner(o):
    c = np.array(o["center"])
    return pav if on_box(c, PAV) and not on_box(c, BLK) else blk


ops = json.load(open(D / "openings.json"))["openings"]
for k, o in enumerate(ops):
    B.recess(owner(o), o, 0.22)
    if o["h"] > 0.6:
        B.sill(f"sill{k}", o, proud=0.10, thick=0.08, overhang=0.08)
door = D / "decal_door.json"
if door.exists():
    for k, o in enumerate(json.load(open(door))["rects"]):
        if o["h"] < 1.5:
            continue  # the lamp heads reuse the door texture
        B.recess(owner(o), o, 0.18)
        B.sill(f"dhood{k}", o, proud=0.20, thick=0.12, overhang=0.15, top=True)

print(B.dump())
