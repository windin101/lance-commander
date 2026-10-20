#!/usr/bin/env python3
"""CAD rebuild of the Steiner long barracks hut on its deck (appearance s_barracks2), in the original's frame.

    D=~/craft/solid/mc2/buildings/s_barracks2
    python3 -I tools/art/cad_building.py openings s_barracks2 > $D/openings.json
    python3 -I tools/art/cad_building.py decal s_barracks2 2 0.15 0.19 0.33 0.52 > $D/decal_door.json
    python3 -I tools/art/cad_building.py decal s_barracks2 2 0.65 0.19 0.82 0.35 > $D/decal_win.json
    python3 -I tools/cad/s_barracks2_cad.py $D > $D/s_barracks2.json
    solidcraft-cli run $D/s_barracks2.json --out $D/s_barracks2.obj
    python3 -I tools/art/cad_building.py bake s_barracks2 $D/s_barracks2.obj

Measured from game/assets/objects/s_barracks2.glb (7 shells): a 24 cm deck (x -3.62..3.82, z -11.93..11.72, top
2.17 m) on four 35 cm posts; the hut (x -2.34..2.37, z -11.26..11.06, walls 2.18..5.04 m) with a chamfered roof to
5.65 m (flat x -1.72..1.75); a ladder down from the deck's +x edge (z 10.13..11.73) to the ground at x 4.08.
Relief: the painted doors are 12 cm recesses in proud frames, the barred windows 8 cm recesses with sills, raised
roof bands on the painted panel joints over the whole roof profile, fascia boards under the chamfer, deck edge beams and
a real ladder (two rails and rungs) instead of the cut-out card.
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


X0, X1, Z0, Z1, YD, YE, YR = -2.34, 2.37, -11.26, 11.06, 2.18, 5.04, 5.65
hut = B.prism_z("hut", [(X0, YD), (X1, YD), (X1, YE), (1.75, YR), (-1.72, YR), (X0, YE)], Z0, Z1)
# deck, edge beams, posts
B.box("deck", (-3.62, 1.93, -11.93), (3.82, 2.17, 11.72))
ring("deckedge", -3.62, 3.82, -11.93, 11.72, 1.78, 2.20, 0.05)
for k, (xa, xb) in enumerate(((-2.34, -1.99), (2.02, 2.37))):
    for j, (za, zb) in enumerate(((-11.26, -10.93), (10.74, 11.06))):
        B.box(f"post{k}{j}", (xa, 0.0, za), (xb, 1.93, zb))
# roof bands at the panel joints, following the roof profile, and fascia boards
# on the painted panel joints: the roof texture runs u 0..5 from z 11.06 to -11.26, a joint every 1/3 u
nb = 15
for i in range(nb + 1):
    z = min(Z1 - 0.06, max(Z0 + 0.06, Z1 - (Z1 - Z0) * i / nb))
    p = 0.05
    B.prism_z(f"band{i}", [(X0 - p, YE - 0.12), (X0, YE - 0.12), (X0, YE), (-1.72, YR), (1.75, YR), (X1, YE), (X1, YE - 0.12),
                            (X1 + p, YE - 0.12), (X1 + p, YE + 0.02), (1.77, YR + p), (-1.74, YR + p), (X0 - p, YE + 0.02)], z - 0.06, z + 0.06)
for k, x in enumerate((X0, X1)):
    sg = -1 if k == 0 else 1
    B.box(f"fascia{k}", (min(x, x + sg * 0.07), YE - 0.20, Z0), (max(x, x + sg * 0.07), YE - 0.04, Z1))
# ladder from the deck edge to the ground
top, bot = np.array([3.84, 2.17]), np.array([4.10, -0.03])
for r, zr in enumerate((10.25, 11.61)):
    t = np.array([bot[0] - top[0], bot[1] - top[1], 0.0])
    Lr = np.linalg.norm(t)
    t /= Lr
    n = np.array([0.0, 0.0, 1.0])
    b = np.cross(n, t)
    B.obox(f"rail{r}", np.array([(top[0] + bot[0]) / 2, (top[1] + bot[1]) / 2, zr]), t, b, n, (Lr + 0.1, 0.08, 0.06))
for i in range(7):
    f = (i + 0.5) / 7
    x, y = top[0] + (bot[0] - top[0]) * f, top[1] + (bot[1] - top[1]) * f
    B.box(f"rung{i}", (x - 0.025, y - 0.025, 10.25), (x + 0.025, y + 0.025, 11.61))

# doors and windows
for name, depth in (("door", 0.12), ("win", 0.08)):
    f = D / f"decal_{name}.json"
    if not f.exists():
        continue
    for k, o in enumerate(json.load(open(f))["rects"]):
        c = np.array(o["center"])
        if abs(o["normal"][1]) > 0.5 or c[1] < YD + 0.2 or not (X0 - 0.05 < c[0] < X1 + 0.05):
            continue
        B.recess(hut, o, depth)
        if name == "door":
            B.frame(f"dframe{k}", o, width=0.10, proud=0.05)
        else:
            B.sill(f"wsill{k}", o, proud=0.10, thick=0.06, overhang=0.06)

print(B.dump())
