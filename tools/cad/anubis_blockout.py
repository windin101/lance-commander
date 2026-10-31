#!/usr/bin/env python3
"""Anubis in-house model, step 1: the blockout (LANCE-37).  Same route as the Starslayer and Hollander.

Every part is a convex hull of points in the ORIGINAL game's rest frame (mm, Z up, faces -Y, +X is its left), one per
original mesh node of game/assets/mechs/anubis.glb, so each part pivots on the original skeleton.  Built from separate
layered volumes at an MWO-class silhouette (an image-to-3D mesher reproduces the input's mass).
chassis/anubis.json Prime (components.json ids): 4x LRM5 rack (the two tall angled "ear" boxes on the torso top,
weapon_lefttorso / weapon_righttorso at z 7200, two racks stacked in each), one Large Laser (weapon_centertorso: under the
snout), jump jets (jumpjet_back, rear of the torso), extended sensors (a mast on the head); plain forearm units.
    python3 -I tools/cad/anubis_blockout.py OUT.npz [HULLS.npz]"""
import sys
import numpy as np
from scipy.spatial import ConvexHull

PARTS = {}
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


# ------------------------------------------------------------------ pelvis with skirts (joint_hip (-7, 405, 4477))
layers("AN_hip", (4900, -700, 700, -350, 1050), (4350, -900, 900, -450, 1250), (3800, -650, 650, -400, 1000))
layers("AN_hip", (4700, -1200, 1200, -500, 1300), (4000, -1250, 1250, -550, 1350))                 # hip skirts over the thigh tops
box("AN_hip", -420, 420, -650, -450, 3900, 4800)                                                    # codpiece plate

# ------------------------------------------------------------------ torso, ears, head, arms: the original's own hull points, inflated
# The silhouette is the jackal: a low pointed snout between and below two tall wing boxes swept back behind the head, a
# torso leaning forward over the hips.  We take the vertices of the original meshes (game/assets/mechs/anubis.glb) and
# build chunky hulls on them (scaled about each group's centre), so the lean, the wing flare and the arm splay are the
# original's by construction; the detail volumes on top (LRM faces, laser, jump jets, sensor, engine pack) are ours.
import functools


@functools.lru_cache(maxsize=None)
def _orig(node):
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/art")) if False else None
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools/art"))
    import hd_rig as R
    og, ob = R.load_glb(str(Path(__file__).resolve().parents[2] / "game/assets/mechs/anubis.glb")); W = R.world_matrices(og)
    names = [n.get("name") for n in og["nodes"]]
    i = names.index(node); n = og["nodes"][i]
    pr = og["meshes"][n["mesh"]]["primitives"][0]
    pp = R.read_accessor(og, ob, pr["attributes"]["POSITION"]).astype(float)
    pw = (np.c_[pp, np.ones(len(pp))] @ W[i].T)[:, :3]
    return np.unique((np.c_[pw[:, 0], -pw[:, 2], pw[:, 1]] * 1000).round(), axis=0)


def inflate(pts, f, about=None):
    pts = np.asarray(pts, float); c = pts.mean(0) if about is None else np.asarray(about, float)
    return c + (pts - c) * np.asarray(f, float)


T = _orig("AN_torso")
ear = T[(T[:, 2] >= 6400) & (np.abs(T[:, 0]) >= 700) & (T[:, 1] >= 400)]
head = T[(T[:, 1] < -100) | ((np.abs(T[:, 0]) < 500) & (T[:, 2] > 6300) & (T[:, 1] < 200))]
body = np.array([p for p in T if not any((p == q).all() for q in np.concatenate([ear, head]))])
for sx in (-1, 1):
    e = ear[np.sign(ear[:, 0]) == sx]
    base = (sx * 1230, e[:, 1].mean(), 6445)
    add("AN_torso", inflate(e, (1.2, 1.2, 1.2), about=base))                                              # the wing, 20 % larger about its base
    # root: a solid yoke from the wing base across the shoulder top into the body, so there is no daylight under the wing
    add("AN_torso", [[sx * x, y, zz] for x in (250, 1800) for y in (330, 1600) for zz in (5950, 6800)])
add("AN_torso", inflate(head, (1.55, 1.25, 1.15), about=(0, head[:, 1].mean(), 6000)))                       # head and long snout, filled out
add("AN_torso", [[x, y, zz] for x in (-620, 620) for y in (-1450, -300) for zz in (5250, 6250)])             # solid front block under the visor
add("AN_torso", [[x, y, zz] for x in (-420, 420) for y in (-1650, -1300) for zz in (5350, 5950)])            # muzzle mass
add("AN_torso", [[x, y, zz] for x in (-480, 480) for y in (-1100, -150) for zz in (6000, 6600)])             # cockpit visor
add("AN_torso", inflate(body, (1.35, 1.0, 1.0), about=(0, body[:, 1].mean(), 5600)))                          # lean body between the wings
layers("AN_torso", (5150, -850, 850, -700, 1050), (5700, -1000, 1000, -400, 1500))                          # belly plating under the chest
layers("AN_torso", (5300, -650, 650, 1500, 2100), (5500, -700, 700, 1650, 2250), (6600, -700, 700, 1650, 2250), (6900, -600, 600, 1550, 2000))   # engine pack between the wings
for sx in (-1, 1):
    cyl("AN_torso", (sx * 420, 1900, 5100), 190, 170, "z", 10)                                               # jump-jet nozzles
cyl("AN_torso", (0, -1600, 5000), 150, 500, "y", 12); box("AN_torso", -300, 300, -1250, -550, 4800, 5250)   # large laser under the chin
cyl("AN_torso", (200, 250, 7000), 45, 520, "z", 8); box("AN_torso", 110, 290, 60, 440, 6620, 6780)           # extended-sensor mast on the head
# the four LRM5 racks: two per wing, five tubes each (3 + 2), on the front face of each wing
for sx in (-1, 1):
    for zc in (6950, 7600):
        yf = 419 + (zc - 6641) * 450 / 1178 - 130
        xc = sx * (1300 - (zc - 6900) * 0.2)
        for dx, dz in ((-230, 130), (0, 130), (230, 130), (-115, -130), (115, -130)):
            cyl("AN_torso", (xc + dx, yf, zc + dz), 110, 75, "y", 8)

# ------------------------------------------------------------------ arms: the original's splayed shoulder, upper arm and forearm blade with its pointed spikes
for s_, side in ((-1, "r"), (1, "l")):
    U = _orig(f"AN_{side}uarm"); G = _orig(f"AN_{side}gun")
    add(f"AN_{side}uarm", inflate(U, (1.0, 1.9, 1.35)))
    add(f"AN_{side}gun", inflate(G, (1.0, 1.0, 1.3)))
    # a chunky forearm block at the elbow so the blade does not read paper-thin
    add(f"AN_{side}gun", bx((s_ * 2150, 650, 5199), (700, 1100, 780)))

# ------------------------------------------------------------------ legs: thigh, knee-to-heel member, heel-to-ankle shin, foot, two toes (wide splayed stance)
cyl("AN_ruleg", (-551, 604, 4236), 540, 460, "x", 12)                                               # hip barrel
loft("AN_ruleg", (4750, [(-1000, 100), (-250, 100), (-250, 1150), (-1000, 1150)]),
     (3650, [(-1450, -500), (-700, -500), (-700, 950), (-1450, 950)]),
     (3000, [(-1500, -650), (-700, -650), (-700, 300), (-1500, 300)]))
cyl("AN_ruleg", (-1028, -123, 3233), 470, 540, "x", 12)                                              # knee
add("AN_ruleg2", bx((-1028, -123, 3233), (800, 750, 850)) + bx((-1485, 1223, 2625), (750, 750, 800)))
add("AN_ruleg2", bx((-1260, 550, 3100), (700, 900, 450)))                                           # upper armour shell on the member
add("AN_rlleg", bx((-1485, 1223, 2625), (700, 700, 750)) + bx((-1766, 363, 738), (750, 750, 650)))  # shin
add("AN_rlleg", bx((-1650, 800, 1750), (850, 750, 950)))                                            # calf armour
add("AN_rfoot", bx((-1766, 363, 738), (800, 800, 800)) + bx((-1766, 640, 330), (1000, 1250, 640)))  # ankle and heel block
add("joint_AN_ritoe", bx((-1854, -650, 210), (600, 1250, 420)))                                    # inner (forward) toe plate
add("joint_AN_rotoe", bx((-2850, 330, 190), (1230, 560, 380)))                                      # outer (side) toe plate
for p, q in (("AN_ruleg", "AN_luleg"), ("AN_ruleg2", "AN_luleg2"), ("AN_rlleg", "AN_llleg"), ("AN_rfoot", "AN_lfoot"),
             ("joint_AN_ritoe", "joint_AN_litoe"), ("joint_AN_rotoe", "joint_AN_lotoe")):
    mirror(p, q, 20)

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
