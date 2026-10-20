#!/usr/bin/env python3
"""CAD rebuild of the Steiner timber barracks hut (appearance s_barracks), in the original's frame.

    D=~/craft/solid/mc2/buildings/s_barracks
    python3 -I tools/art/cad_building.py openings s_barracks > $D/openings.json
    python3 -I tools/art/cad_building.py decal s_barracks 1 0.15 0.19 0.33 0.52 > $D/decal_door.json
    python3 -I tools/art/cad_building.py decal s_barracks 1 0.65 0.19 0.82 0.35 > $D/decal_win.json
    python3 -I tools/cad/s_barracks_cad.py $D > $D/s_barracks.json
    solidcraft-cli run $D/s_barracks.json --out $D/s_barracks.obj
    python3 -I tools/art/cad_building.py bake s_barracks $D/s_barracks.obj

Measured from game/assets/objects/s_barracks.glb (7 shells): a gabled timber hut raised on four corner posts
(x -9.22..-8.83 / 8.94..9.33, z +-3.35..3.83, to 5.04 m); walls x -9.11..9.21, z +-3.68 from the floor at 1.0 m to
the eaves at 4.76 m, gables to 7.27 m; a 10 cm roof (eaves x -9.47..9.58, z +-4.06 at 4.65 m, ridge 7.39 m); a
ramp to the door on the +z side (x +-0.95, z 3.66..5.22).
Relief: the painted door is a 12 cm recess in a proud frame, the barred windows 8 cm recesses with sills, a sill
beam under the walls, real steps instead of the ramp, a ridge cap, barge boards on the gables and corrugation
ribs along both roof slopes (one flat colour, the mean of the art under each).
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
    """A round column: a cone base y0..yb, the shaft yb..yc, a cone capital yc..y1 (the original's are 4-sided)."""
    B.loft_y(f"{name}b", ngon(xc, zc, rb), y0, ngon(xc, zc, rs + 0.06), yb)
    B.c("solid.cylinder", radius=round(rs * 1000), height=round((yc - yb) * 1000), base=[round(xc * 1000), round(-zc * 1000), round(yb * 1000)],
        axis=[0, 0, 1], body_name=f"{name}s", operation="new")
    B.loft_y(f"{name}c", ngon(xc, zc, rs + 0.06), yc, ngon(xc, zc, rb), y1)


def lamp(name, x, z, dx, dz, y_arm=4.55, y0=0.0):
    """A round lamp post at (x, z) with an arm reaching (dx, dz) to a round lantern head."""
    B.c("solid.cylinder", radius=140, height=150, base=[round(x * 1000), round(-z * 1000), round(y0 * 1000)], axis=[0, 0, 1], body_name=f"{name}f", operation="new")
    B.c("solid.cylinder", radius=90, height=round((y_arm + 0.1 - y0 - 0.15) * 1000), base=[round(x * 1000), round(-z * 1000), round((y0 + 0.15) * 1000)],
        axis=[0, 0, 1], body_name=f"{name}p", operation="new")
    hx, hz = x + dx, z + dz
    B.box(f"{name}a", (min(x, hx) - 0.05, y_arm, min(z, hz) - 0.05), (max(x, hx) + 0.05, y_arm + 0.1, max(z, hz) + 0.05))
    B.c("solid.cylinder", radius=170, height=360, base=[round(hx * 1000), round(-hz * 1000), round((y_arm + 0.01) * 1000)], axis=[0, 0, 1],
        body_name=f"{name}h", operation="new")


X0, X1, Z, YF, YE, YG = -9.11, 9.21, 3.68, 1.0, 4.76, 7.27
hut = B.prism_x("hut", [(Z, YF), (Z, YE), (0.0, YG), (-Z, YE), (-Z, YF)], X0, X1)
RX0, RX1 = -9.47, 9.58
B.prism_x("roof", [(4.06, 4.65), (0.0, 7.39), (-4.06, 4.65), (-3.99, 4.55), (0.0, 7.27), (3.99, 4.55)], RX0, RX1)
B.prism_x("ridge", [(0.16, 7.29), (0.0, 7.47), (-0.16, 7.29), (0.0, 7.36)], RX0 - 0.02, RX1 + 0.02)
# corrugation ribs along each slope
slope = np.array([0.0, 7.39 - 4.65, -4.06])
L = np.linalg.norm(slope)
for s, sg in enumerate((1, -1)):
    for i in range(1, 9):
        f = i / 9
        z, y = sg * 4.06 * (1 - f), 4.65 + 2.74 * f
        n = np.array([0.0, 4.06, sg * 2.74]) / np.hypot(4.06, 2.74)
        t = np.array([1.0, 0.0, 0.0])
        b = np.cross(n, t)
        B.obox(f"rib{s}{i}@avg", np.array([(RX0 + RX1) / 2, y, z]) + n * 0.025, t, b, n, (RX1 - RX0, 0.07, 0.05))
# barge boards up both gable edges
for e, x in enumerate((RX0 - 0.03, RX1 + 0.03)):
    for s, sg in enumerate((1, -1)):
        p0, p1 = np.array([x, 4.50, sg * 4.12]), np.array([x, 7.42, 0.0])
        t = (p1 - p0) / np.linalg.norm(p1 - p0)
        n = np.array([1.0 if e else -1.0, 0.0, 0.0])
        b = np.cross(n, t)
        B.obox(f"barge{e}{s}", (p0 + p1) / 2, t, b, n, (np.linalg.norm(p1 - p0), 0.24, 0.06))
# corner posts (square timber), sill beam
for k, (xa, xb) in enumerate(((-9.22, -8.83), (8.94, 9.33))):
    for j, (za, zb) in enumerate(((-3.83, -3.35), (3.35, 3.83))):
        B.box(f"post{k}{j}", (xa, -0.04, za), (xb, 5.04, zb))
ring("sillbeam", X0, X1, -Z, Z, 0.82, 1.06, 0.07)
# steps up to the door
for i in range(4):
    z0 = 3.75 + 0.37 * i
    B.box(f"step{i}", (-0.95, 0.0, z0), (0.96, 1.0 - 0.25 * i, z0 + 0.39))
    B.box(f"tread{i}", (-0.97, 1.0 - 0.25 * i - 0.04, z0 - 0.02), (0.98, 1.0 - 0.25 * i + 0.02, z0 + 0.41))

# door and windows
for name, depth in (("door", 0.12), ("win", 0.08)):
    f = D / f"decal_{name}.json"
    if not f.exists():
        continue
    for k, o in enumerate(json.load(open(f))["rects"]):
        if abs(o["normal"][1]) > 0.5 or o["center"][1] < YF + 0.2:
            continue
        B.recess(hut, o, depth)
        if name == "door":
            B.frame(f"dframe{k}", o, width=0.10, proud=0.05)
        else:
            B.sill(f"wsill{k}", o, proud=0.10, thick=0.06, overhang=0.06)

print(B.dump())
