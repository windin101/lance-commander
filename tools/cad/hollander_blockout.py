#!/usr/bin/env python3
"""Hollander in-house model, step 1: the blockout (LANCE-37).  Same route as the Starslayer.

Every part is a convex hull of points in the ORIGINAL game's rest frame (mm, Z up, faces -Y, +X is its left), one per
original mesh node, so each part pivots on the original MC2 skeleton (positions read from game/assets/mechs/hollander.glb).
Built from separate layered volumes (proud shoulder housings, a hip block with skirts, thigh and shin shells, chunky feet)
at an MWO-class silhouette, because an image-to-3D mesher reproduces the input's mass.
    python3 -I tools/cad/hollander_blockout.py OUT.npz [HULLS.npz]
The 35 t Hollander (chassis/hollander.json Prime: one Gauss Rifle and its ammo, no jump jets).
No third-party mesh or art: dimensions come from the original's joints and bounding boxes and from the design below."""
import sys
import numpy as np
from scipy.spatial import ConvexHull

PARTS = {}
NODE = {  # part -> original mesh node name
    "ho_hip": "ho_hip", "ho_torso": "ho_torso", "joint_gun": "joint_gun",
    "ho_ruarm": "ho_ruarm", "ho_rgun": "ho_rgun", "ho_luarm": "ho_luarm", "ho_lgun": "ho_lgun",
    "ho_ruleg": "ho_ruleg", "ho_rmleg": "ho_rmleg", "ho_rfoot": "ho_rfoot", "joint_rtoe": "joint_rtoe",
    "ho_luleg": "ho_luleg", "ho_lmleg": "ho_lmleg", "ho_lfoot": "ho_lfoot", "joint_ltoe": "joint_ltoe"}
JOINT = {"ho_hip": ("joint_hip", (0, 69, 3745)), "ho_torso": ("joint_torso", (0, 0, 4242)), "joint_gun": ("joint_gun", (-601, 62, 6191)),
         "ho_ruarm": ("joint_ruarm", (-1700, 150, 5870)), "ho_rgun": ("joint_rgun", (-2165, 114, 4798)),
         "ho_luarm": ("joint_luarm", (1750, 150, 5870)), "ho_lgun": ("joint_lgun", (2224, 114, 4798)),
         "ho_ruleg": ("joint_ruleg", (-991, 253, 3894)), "ho_rmleg": ("joint_rlleg", (-1328, -1186, 2169)),
         "ho_rfoot": ("joint_rfoot (ankle joint_rankle)", (-1365, 0, 0)), "joint_rtoe": ("joint_rtoe", (-1389, 201, 244)),
         "ho_luleg": ("joint_luleg", (1053, 253, 3894)), "ho_lmleg": ("joint_llleg", (1387, -1186, 2169)),
         "ho_lfoot": ("joint_lfoot (ankle joint_lankle)", (1424, 0, 0)), "joint_ltoe": ("joint_ltoe", (1448, 201, 244))}


def add(part, pts):
    PARTS.setdefault(part, []).append(np.asarray(pts, float))


def bx(c, s):
    c, s = np.array(c, float), np.array(s, float) / 2
    return [c + [sx * s[0], sy * s[1], sz * s[2]] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]


def box(part, x0, x1, y0, y1, z0, z1):
    add(part, [[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)])


def layers(part, *ls):
    add(part, [[x, y, z] for z, x0, x1, y0, y1 in ls for x in (x0, x1) for y in (y0, y1)])


def loft(part, *ls):
    add(part, [[x, y, z] for z, pts in ls for x, y in pts])


def cyl(part, c, r, half, axis="y", n=12):
    a = np.arange(n) * 2 * np.pi / n + np.pi / n
    ring = np.c_[np.cos(a), np.sin(a)] * r
    pts = []
    for s in (-half, half):
        for u, v in ring:
            p = {"x": [s, u, v], "y": [u, s, v], "z": [u, v, s]}[axis]
            pts.append(np.array(c) + p)
    add(part, pts)


def mirror(src, dst, shift=58):
    """Left from right: x -> -x + shift (the original's left joints sit about 58 mm off the mirror of the right)."""
    for p in PARTS[src]:
        q = p.copy(); q[:, 0] = -q[:, 0] + shift
        add(dst, q)


# ------------------------------------------------------------------ pelvis block with skirts (joint_hip)
layers("ho_hip", (4350, -900, 900, -550, 700), (3800, -1150, 1150, -800, 900), (2950, -850, 850, -500, 650))
layers("ho_hip", (4150, -1500, 1500, -850, 1000), (3600, -1550, 1550, -900, 1050))      # hip skirts over the thigh tops
box("ho_hip", -420, 420, -1000, -750, 3000, 4100)                                       # codpiece plate

# ------------------------------------------------------------------ torso (joint_torso): inverted pentagon like the original's chest
layers("ho_torso", (4250, -650, 650, -600, 750), (4900, -950, 950, -850, 950))                       # waist keel
loft("ho_torso", (4850, [(-1000, -1000), (1000, -1000), (1150, 1150), (-1150, 1150)]),
     (5600, [(-1800, -1450), (1800, -1450), (1900, 1350), (-1900, 1350)]),                         # chest, widest, deep
     (6400, [(-1700, -1200), (1700, -1200), (1850, 1450), (-1850, 1450)]),
     (6950, [(-1450, -800), (1450, -800), (1600, 1250), (-1600, 1250)]))
layers("ho_torso", (5000, -1000, 1000, 1300, 1800), (5300, -1150, 1150, 1500, 2150), (6600, -1150, 1150, 1500, 2150), (6900, -950, 950, 1400, 1900))   # engine pack
layers("ho_torso", (6000, 250, 1300, -1600, -150), (6450, 300, 1250, -1650, -100), (7050, 450, 1150, -1200, 100))      # cockpit pod, left-front
box("ho_torso", -1300, -80, -800, 1500, 6850, 7000)                                                    # cradle plate under the rifle

# ------------------------------------------------------------------ the Gauss rifle (joint_gun, pivot (-601, 62, 6191))
# chassis/hollander.json Prime carries ONE weapon: a Gauss Rifle (components.json id 104, ammo 204). In the original
# `joint_gun` is one long spike on the torso top, tip at y -3950, about 380 mm across, widening to a 900 x 1050 mm
# receiver at the torso: slender barrel, magnetic coil collars, muzzle, receiver / capacitor housing with an ammo feed
box("joint_gun", -1049, -153, -650, 1835, 6040, 7095)                                         # receiver / capacitor housing
layers("joint_gun", (6100, -1000, -200, 1500, 1900), (7050, -950, -250, 1500, 1900))         # rear cap
cyl("joint_gun", (-601, -2300, 6420), 150, 1650, "y", 14)                                      # barrel, 300 mm across
for y in (-1100, -1650, -2200, -2750):
    cyl("joint_gun", (-601, y, 6420), 270, 90, "y", 14)                                        # coil collars
cyl("joint_gun", (-601, -3800, 6420), 210, 150, "y", 14)                                       # muzzle
box("joint_gun", -720, -480, 700, 1500, 5750, 6045)                                           # ammo feed into the torso
box("joint_gun", -1000, -200, -1100, -650, 6100, 6400)                                        # forward housing under the barrel

# ------------------------------------------------------------------ arms: shoulder housing + upper arm, plain forearm units (no arm weapons in the loadout)
layers("ho_ruarm", (6350, -2400, -1550, -650, 950), (5600, -2500, -1550, -750, 1000), (4650, -2300, -1700, -450, 750))
layers("ho_rgun", (5250, -2700, -1850, -1900, 300), (4350, -2700, -1850, -1900, 300))
cyl("ho_rgun", (-2275, -2150, 4800), 200, 250, "y", 10)                                         # fist / actuator stub
mirror("ho_ruarm", "ho_luarm"); mirror("ho_rgun", "ho_lgun")

# ------------------------------------------------------------------ legs: thigh shell, shin (raked back, near horizontal), tarsus + heel, toe plate
cyl("ho_ruleg", (-991, 253, 3894), 640, 560, "x", 12)                                          # hip barrel
loft("ho_ruleg", (4350, [(-1550, -550), (-450, -550), (-450, 1050), (-1550, 1050)]),
     (3300, [(-1700, -1200), (-700, -1200), (-700, 800), (-1700, 800)]),
     (2700, [(-1750, -1750), (-900, -1750), (-900, -450), (-1750, -450)]))
cyl("ho_ruleg", (-1328, -1186, 2169), 560, 700, "x", 12)                                       # knee
add("ho_rmleg", bx((-1328, -1186, 2169), (850, 800, 1000)) + bx((-1365, 516, 1905), (750, 700, 800)))
add("ho_rmleg", bx((-1340, -300, 2450), (700, 900, 500)))                                      # top armour shell along the shin
add("ho_rfoot", bx((-1365, 516, 1905), (800, 700, 900)) + bx((-1365, 760, 850), (950, 800, 900)))   # tarsus
add("ho_rfoot", bx((-1365, 450, 340), (1150, 1500, 680)))                                      # heel block
box("ho_rfoot", -1700, -1030, 1100, 1450, 100, 900)                                            # heel spur
add("joint_rtoe", bx((-1389, -350, 240), (1150, 1250, 480)))                                    # toe plate
for p in ("ho_ruleg", "ho_rmleg", "ho_rfoot", "joint_rtoe"):
    mirror(p, p.replace("ho_r", "ho_l").replace("joint_rtoe", "joint_ltoe"))


def hulls():
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
            h = ConvexHull(pts); c = pts.mean(0); F = []
            for s in h.simplices:
                a, b, d = pts[s[0]], pts[s[1]], pts[s[2]]
                s = list(s)
                if np.dot(np.cross(b - a, d - a), a - c) < 0:
                    s = [s[0], s[2], s[1]]
                F.append(s)
            Ps.append(pts); Fs.append(np.array(F) + o); lab += [ci] * len(F); o += len(pts)
    return np.concatenate(Ps), np.concatenate(Fs), np.array(lab), names


if __name__ == "__main__":
    P, F, lab, names = build()
    np.savez(sys.argv[1], P=P, F=F, part=lab, names=np.array(names))
    if len(sys.argv) > 2:
        H = hulls()
        d = {"n": np.array([len(H)]), "names": np.array([h[0] for h in H])}
        for i, (_, V, F_) in enumerate(H):
            d[f"V{i}"], d[f"F{i}"] = V, F_
        np.savez(sys.argv[2], **d)
    print(len(names), "parts", len(F), "tris", P.min(0).round(), P.max(0).round())
