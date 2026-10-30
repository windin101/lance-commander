#!/usr/bin/env python3
"""Starslayer in-house model, step 1: the blockout (LANCE-36).

Every part is a convex hull of hand-placed points in the ORIGINAL game's rest frame (mm, Z up, the mech faces -Y,
+X is its left), so each part pivots on the original MC2 skeleton's joint (positions read from
game/assets/mechs/starslayer.glb) and the original animations drive it unchanged.  Masses are sized to a modern
(MWO-class, chunky) silhouette, not to the original's thin low-poly limbs.

    python3 -I tools/cad/starslayer_blockout.py OUT.npz          # P, F, part (per face), names
No Hunyuan, no third-party mesh: dimensions come from the original's joints and bounding boxes (our own
data, Shared Source terms) and from the design below.  Written by Claude for Lee, 2026-10-30.
"""
import sys
import numpy as np
from scipy.spatial import ConvexHull

PARTS = {}          # part name (original mesh node) -> list of hull point arrays
JOINT = {           # part -> the original skeleton joint that carries it (pivot in game mm)
    "ss_hip": ("joint_hip", (-12, 253, 4951)),
    "ss_torso": ("joint_torso", (-56, 260, 5348)),
    "ss_ruarm": ("joint_ruarm", (-2026, 450, 7197)),
    "ss_gun": ("joint_rshoulder", (-1286, 398, 8296)),
    "ss_luarm": ("joint_luarm", (1752, 466, 7657)),
    "ss_lgun": ("joint_lgun", (2495, 466, 6641)),
    "ss_luleg": ("joint_luleg", (1337, 268, 4925)), "ss_ruleg": ("joint_ruleg", (-1359, 268, 4925)),
    "ss_llleg": ("joint_llleg", (1617, -145, 3342)), "ss_rlleg": ("joint_rlleg", (-1640, -145, 3342)),
    "ss_lfoot": ("joint_lfoot (ankle joint_lankle)", (1688, -210, 137)), "ss_rfoot": ("joint_rfoot (ankle joint_rankle)", (-1711, -210, 137)),
    "toe_li": ("joint_litoe", (1263, -170, 188)), "toe_lo": ("joint_lotoe", (2112, -170, 188)),
    "toe_ri": ("joint_ritoe", (-1286, -170, 188)), "toe_ro": ("joint_rotoe", (-2136, -170, 188)),
}


def add(part, pts):
    PARTS.setdefault(part, []).append(np.asarray(pts, float))


def rect(cx, cy, z, w, d, dx=0.0, dy=0.0):
    """Four corners of a w (x) by d (y) rectangle centred (cx, cy) at height z."""
    return [[cx - w / 2 + dx, cy - d / 2 + dy, z], [cx + w / 2 + dx, cy - d / 2 + dy, z],
            [cx + w / 2 + dx, cy + d / 2 + dy, z], [cx - w / 2 + dx, cy + d / 2 + dy, z]]


def box(part, x0, x1, y0, y1, z0, z1):
    add(part, [[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)])


def layers(part, *ls):
    """ls: (z, x0, x1, y0, y1) layers, lofted."""
    add(part, [[x, y, z] for z, x0, x1, y0, y1 in ls for x in (x0, x1) for y in (y0, y1)])


def cyl(part, c, r, half, axis="y", n=10):
    """Prism of radius r about axis through c, c +- half along it."""
    a = np.arange(n) * 2 * np.pi / n + np.pi / n
    ring = np.c_[np.cos(a), np.sin(a)] * r
    pts = []
    for s in (-half, half):
        for u, v in ring:
            p = {"x": [s, u, v], "y": [u, s, v], "z": [u, v, s]}[axis]
            pts.append(np.array(c) + p)
    add(part, pts)


def mirror(src, dst, swap=None):
    for p in PARTS[src]:
        q = p.copy(); q[:, 0] *= -1
        add(dst, q)


def poly(part, z, pts):
    """pts: (x, y) outline at height z (for lofted hulls of an arbitrary polygon)."""
    return [[x, y, z] for x, y in pts]


def loft(part, *ls):
    add(part, sum((poly(part, z, pts) for z, pts in ls), []))


# ---------------------------------------------------------------- pelvis (ss_hip), joint_hip 4951 + hip skirts
layers("ss_hip", (5450, -1350, 1350, -650, 1000), (4750, -1750, 1750, -750, 1150), (4150, -1000, 1000, -550, 800))
for sx in (1, -1):   # hip sockets and skirt plates over the thighs
    cyl("ss_hip", (sx * 1350, 268, 4925), 700, 560, "x", 12)
    layers("ss_hip", (5250, sx * 900, sx * 2150, -900, 1150), (4550, sx * 900, sx * 2250, -1000, 1250))
box("ss_hip", -450, 450, -950, -650, 4300, 5100)     # front codpiece plate

# ---------------------------------------------------------------- torso (ss_torso), joint_torso 5348
# an inverted pentagon in front view: narrow keel at the waist, broad swept-back shoulders; deep in side view
layers("ss_torso", (5350, -800, 800, -600, 900), (6150, -600, 600, -900, 1100))                   # keel / waist
loft("ss_torso", (6100, [(-550, -950), (550, -950), (700, 1100), (-700, 1100)]),
     (6900, [(-1300, -1300), (1300, -1300), (1950, 1000), (1500, 1750), (-1500, 1750), (-1950, 1000)]),
     (7700, [(-1650, -1650), (1650, -1650), (2050, 800), (1600, 1950), (-1600, 1950), (-2050, 800)]),   # shoulders swept back
     (8350, [(-1500, -1450), (1500, -1450), (1900, 700), (1450, 1900), (-1450, 1900), (-1900, 700)]),
     (8800, [(-1100, -950), (1100, -950), (1350, 700), (1000, 1700), (-1000, 1700), (-1350, 700)]))
layers("ss_torso", (6300, -1000, 1000, 1700, 2000), (6500, -1150, 1150, 1900, 2350),            # reactor pack
       (8000, -1150, 1150, 1900, 2350), (8300, -1000, 1000, 1700, 2100))
layers("ss_torso", (8300, -950, 950, -1700, 400), (8800, -850, 850, -1700, 450), (9050, -520, 520, -1250, 250))   # head hump on the forward slope
layers("ss_torso", (8950, -130, 130, -300, 700), (9930, -50, 50, 350, 750))                       # crest fin
for z in (6635, 6948):  # weapon ports left chest (weapon_lefttorso / weapon_centertorso)
    cyl("ss_torso", (850, -1550, z), 300, 380, "y", 8)
cyl("ss_torso", (-900, -1450, 6800), 240, 300, "y", 8)

# ---------------------------------------------------------------- right arm (ss_ruarm), joint_ruarm (-2026, 450, 7197)
layers("ss_ruarm", (6600, -2900, -2050, -250, 1300), (7200, -3150, -2050, -350, 1350), (7800, -2900, -2150, -250, 1250))   # shoulder housing
box("ss_ruarm", -3250, -2150, -2450, -250, 6700, 7700)              # forearm cannon body
cyl("ss_ruarm", (-2650, -2900, 7190), 300, 450, "y", 12)             # barrel
cyl("ss_ruarm", (-2650, -3250, 7190), 380, 120, "y", 12)             # muzzle brake
# ---------------------------------------------------------------- right shoulder gun (ss_gun), joint_rshoulder (-1286, 398, 8296)
box("ss_gun", -1750, -820, -1700, 900, 8100, 8950)                   # launcher body
layers("ss_gun", (8100, -1700, -850, 900, 1950), (8950, -1600, -900, 900, 1700))   # rear housing
cyl("ss_gun", (-1286, -2050, 8480), 260, 350, "y", 10)               # barrel
# ---------------------------------------------------------------- left arm: slab (ss_luarm) + weapon pod (ss_lgun)
layers("ss_luarm", (7000, 2000, 2900, -550, 1000), (8000, 1950, 3000, -700, 1150), (8700, 2000, 2900, -500, 1000))
layers("ss_luarm", (8300, 1900, 3050, -750, 1200), (8800, 2050, 2900, -550, 1050), (9000, 2300, 2700, -250, 800))   # pauldron
layers("ss_lgun", (6300, 2050, 3100, -1450, 600), (7000, 2100, 3150, -1500, 650))
# elbow ball: the pod turns about joint_lgun, so its root is a sphere about the pivot, seated in a socket on the slab
a_, b_ = np.meshgrid(np.linspace(0.15, np.pi - 0.15, 6), np.arange(12) * np.pi / 6)
add("ss_lgun", np.array([2495, 466, 6641]) + 470 * np.c_[(np.sin(a_) * np.cos(b_)).ravel(), (np.sin(a_) * np.sin(b_)).ravel(), np.cos(a_).ravel()])
layers("ss_luarm", (6250, 1950, 3050, -500, 1000), (7050, 1950, 3050, -550, 1050))   # socket
for dx, dz in ((-200, 120), (200, 120), (0, -160)):
    cyl("ss_lgun", (2600 + dx, -1850, 6660 + dz), 130, 400, "y", 8)

# ---------------------------------------------------------------- legs (left, mirrored): thigh / shin / foot / toes
cyl("ss_luleg", (1337, 268, 4925), 600, 560, "x", 12)                  # hip barrel
loft("ss_luleg", (5400, [(900, -500), (2150, -500), (2150, 1000), (900, 1000)]),                  # thigh: forward-raked, 1.3 m wide
     (4400, [(900, -900), (2200, -900), (2200, 650), (900, 650)]),
     (3500, [(1000, -1000), (2200, -1000), (2200, 300), (1000, 300)]))
cyl("ss_luleg", (1617, -145, 3342), 540, 700, "x", 12)                 # knee
# shin: a long parallelogram raked back from the knee to the heel (the original's zig-zag)
loft("ss_llleg", (3500, [(1100, -700), (2150, -700), (2150, 250), (1100, 250)]),
     (2700, [(1150, -250), (2100, -250), (2100, 650), (1150, 650)]),
     (1850, [(1250, 250), (2000, 250), (2000, 1100), (1250, 1100)]))
loft("ss_llleg", (3300, [(1300, 100), (1950, 100), (1950, 500), (1300, 500)]),      # calf armour sweeping out the back
     (2300, [(1350, 700), (1950, 700), (1950, 1550), (1350, 1550)]),
     (1750, [(1400, 800), (1900, 800), (1900, 1400), (1400, 1400)]))
layers("ss_lfoot", (2050, 1350, 2050, 300, 1000), (900, 1250, 2150, -50, 900))                 # ankle strut
layers("ss_lfoot", (900, 1150, 2250, -450, 1050), (150, 1100, 2300, -500, 1250), (0, 1100, 2300, -450, 1315))   # foot block / heel
box("toe_li", 1050, 1475, -1450, -100, 0, 420); box("toe_lo", 1900, 2325, -1450, -100, 0, 420)
for src in ("ss_luleg", "ss_llleg", "ss_lfoot"):
    mirror(src, src.replace("ss_l", "ss_r"))
for a, b in (("toe_li", "toe_ri"), ("toe_lo", "toe_ro")):
    mirror(a, b)
# the tip of each toe is narrower: wedge by replacing the box front corners
for t in ("toe_li", "toe_lo", "toe_ri", "toe_ro"):
    p = PARTS[t][0]; xc = p[:, 0].mean()
    front = p[:, 1] < -1000
    p[front, 0] = xc + (p[front, 0] - xc) * 0.6; p[front, 2] = np.where(p[front, 2] > 100, 260, p[front, 2])


def hulls():
    """Every hull as (part, V, F) with outward triangles: the input of tools/cad/starslayer_detail.py."""
    out = []
    for name in PARTS:
        for pts in PARTS[name]:
            h = ConvexHull(pts)
            V = pts[h.vertices]; rm = {int(k): i for i, k in enumerate(h.vertices)}
            c = V.mean(0); F = []
            for sm in h.simplices:
                a, b, d = pts[sm[0]], pts[sm[1]], pts[sm[2]]
                f = [rm[int(i)] for i in sm]
                if np.dot(np.cross(b - a, d - a), a - c) < 0:
                    f = [f[0], f[2], f[1]]
                F.append(f)
            out.append((name, V, np.array(F)))
    return out


def build():
    Ps, Fs, lab, names, o = [], [], [], list(PARTS), 0
    for ci, name in enumerate(names):
        for pts in PARTS[name]:
            h = ConvexHull(pts)
            v = pts[h.vertices]; remap = {int(k): i for i, k in enumerate(h.vertices)}
            c = pts.mean(0)
            F = []
            for s, eq in zip(h.simplices, h.equations):
                s = [remap[int(i)] for i in s] if False else list(s)
                a, b, d = pts[s[0]], pts[s[1]], pts[s[2]]
                n = np.cross(b - a, d - a)
                if np.dot(n, a - c) < 0:
                    s = [s[0], s[2], s[1]]
                F.append(s)
            Ps.append(pts); Fs.append(np.array(F) + o); lab += [ci] * len(F); o += len(pts)
    return np.concatenate(Ps), np.concatenate(Fs), np.array(lab), names


if __name__ == "__main__":
    P, F, lab, names = build()
    np.savez(sys.argv[1], P=P, F=F, part=lab, names=np.array(names))
    if len(sys.argv) > 2:   # hulls for the detail pass
        H = hulls()
        d = {"n": np.array([len(H)]), "names": np.array([h[0] for h in H])}
        for i, (_, V, F_) in enumerate(H):
            d[f"V{i}"], d[f"F{i}"] = V, F_
        np.savez(sys.argv[2], **d)
    print(len(names), "parts", len(F), "tris", P.min(0).round(), P.max(0).round())
