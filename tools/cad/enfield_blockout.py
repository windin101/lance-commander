#!/usr/bin/env python3
"""Enfield in-house model, step 1: the blockout (LANCE-37).  Same route as the Anubis.

Every part is a convex hull of points in the ORIGINAL game's rest frame (mm, Z up, faces -Y, +X is its left), one per
original mesh node of game/assets/mechs/enfield.glb, built on the original's own vertices (dimensions-only reference),
inflated into chunky layered volumes, plus our own detail volumes.  chassis/enfield.json Prime (components.json ids):
2x Laser (torso front, weapon_righttorso / weapon_lefttorso), 1 Large Pulse Laser (left forearm), 1 Ultra Autocannon
AC/10 with ammo (the long right forearm).  Tall V-shouldered torso, a tall crest on the head with a spike swept back.
    python3 -I tools/cad/enfield_blockout.py OUT.npz [HULLS.npz]"""
import sys
import numpy as np
from scipy.spatial import ConvexHull
import functools

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


@functools.lru_cache(maxsize=None)
def _orig(node):
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools/art"))
    import hd_rig as R
    og, ob = R.load_glb(str(Path(__file__).resolve().parents[2] / "game/assets/mechs/enfield.glb")); W = R.world_matrices(og)
    names = [n.get("name") for n in og["nodes"]]
    i = names.index(node); n = og["nodes"][i]
    pr = og["meshes"][n["mesh"]]["primitives"][0]
    pp = R.read_accessor(og, ob, pr["attributes"]["POSITION"]).astype(float)
    pw = (np.c_[pp, np.ones(len(pp))] @ W[i].T)[:, :3]
    return np.unique((np.c_[pw[:, 0], -pw[:, 2], pw[:, 1]] * 1000).round(), axis=0)


def inflate(pts, f, about=None):
    pts = np.asarray(pts, float); c = pts.mean(0) if about is None else np.asarray(about, float)
    return c + (pts - c) * np.asarray(f, float)


# ------------------------------------------------------------------ pelvis block with skirts (joint_hip (36, -145, 5616))
H = _orig("en_hip")
add("en_hip", inflate(H, (1.25, 1.2, 1.0), about=(36, 100, 5500)))
layers("en_hip", (5900, -1100, 1100, -700, 700), (5200, -1150, 1150, -750, 800))                      # hip skirts over the thigh tops

# ------------------------------------------------------------------ torso: V-shouldered body, tall crest on the head with the spike swept back
T = _orig("en_torso")
spike = T[T[:, 1] > 3000]                                                      # the swept-back spike's apex
crest = T[(np.abs(T[:, 0]) <= 300) & (T[:, 2] >= 8000) & (T[:, 1] < 3000)]
body = np.array([p for p in T if not any((p == q).all() for q in np.concatenate([crest, spike]))])
add("en_torso", inflate(body, (1.15, 1.2, 1.0), about=(0, body[:, 1].mean(), 7400)))                  # shoulders and chest
add("en_torso", inflate(crest, (1.8, 1.1, 1.05), about=(0, crest[:, 1].mean(), 8400)))                 # the crest, widened
add("en_torso", [[x, y, zz] for x in (-120, 120) for y in (1500, 1750) for zz in (8750, 9100)] + [[float(spike[0, 0]) * 0.4, float(spike[0, 1]), float(spike[0, 2])]])   # the swept-back spike
layers("en_torso", (6150, -450, 450, -650, 650), (6700, -800, 800, -800, 1100))                        # chest keel under the shoulders
layers("en_torso", (6900, -700, 700, 1100, 1900), (8000, -800, 800, 1100, 1900))                      # engine / ammo pack at the back
# the two torso lasers (weapon_righttorso / weapon_lefttorso) and the central sensor block
for x in (-591, 755):
    box("en_torso", x - 130, x + 130, -1700, -1100, 6650, 6930); cyl("en_torso", (x, -1900, 6790), 85, 250, "y", 8)
box("en_torso", -280, 280, -1500, -900, 6250, 6600)                                                   # chin block (weapon_centertorso)
box("en_torso", -350, 350, -1050, -450, 8050, 8750)                                                  # visor block on the head

# ------------------------------------------------------------------ arms: shoulder plates, the long Ultra AC/10 forearm (right), the pulse-laser forearm (left)
for s_, side in ((-1, "r"), (1, "l")):
    add(f"en_{side}uarm", inflate(_orig(f"en_{side}uarm"), (1.35, 1.9, 1.15)))
    add(f"en_{side}gun", inflate(_orig(f"en_{side}gun"), (1.25, 1.0, 1.25)))
cyl("en_rgun", (-2480, -3300, 7000), 125, 520, "y", 10); cyl("en_rgun", (-2160, -3300, 7000), 125, 520, "y", 10)       # twin barrels of the AC/10
box("en_rgun", -2700, -1950, -2900, -2400, 6600, 7250)                                                 # barrel shroud
cyl("en_lgun", (2922, -2800, 6223), 210, 520, "y", 12); cyl("en_lgun", (2922, -3250, 6223), 270, 60, "y", 12)        # large pulse laser

# ------------------------------------------------------------------ legs: distinct thigh, knee, shin, ankle, foot and toes
# Built on the LEFT leg (x > 0) and mirrored to the right (x' = 120 - x, the original's right joints sit 120 mm off the mirror).
# thigh: shell over a visible piston frame; knee: actuator drum and kneecap plate; shin: shell with a calf actuator behind;
# ankle: actuator above a separate foot block and the toes.  Each part stays on its joint.
def rod(part, a, b, r, n=8):
    a, b = np.array(a, float), np.array(b, float); ax = (b - a) / np.linalg.norm(b - a)
    u = np.cross(ax, [0, 0, 1.0]); u = u / np.linalg.norm(u) if np.linalg.norm(u) > 1e-6 else np.array([1.0, 0, 0]); v = np.cross(ax, u)
    t = np.arange(n) * 2 * np.pi / n
    add(part, [p + r * (np.cos(k) * u + np.sin(k) * v) for p in (a, b) for k in t])


HIP, KNEE, ANK = (752, -84, 5342), (1423, 1044, 3676), (1296, -42, 1099)
add("en_luleg", inflate(_orig("en_luleg"), (1.1, 1.0, 1.0)))                                          # core of the thigh
cyl("en_luleg", HIP, 520, 440, "x", 12)                                                              # hip barrel
for dx in (-330, 330):                                                                                # inner frame: two pistons hip -> knee
    rod("en_luleg", (HIP[0] + dx, HIP[1] + 150, HIP[2] - 250), (KNEE[0] + dx, KNEE[1] - 200, KNEE[2] + 300), 110)
add("en_luleg", [[x, y, zz] for x in (520, 1560) for y in (-780, -420) for zz in (4300, 5800)])        # front thigh shell
add("en_luleg", [[x, y, zz] for x in (1050, 1900) for y in (-250, 150) for zz in (3500, 4600)])       # shell over the lower thigh
add("en_luleg", [[x, y, zz] for x in (450, 650) for y in (-500, 900) for zz in (4400, 5600)]); add("en_luleg", [[x, y, zz] for x in (1450, 1650) for y in (-500, 900) for zz in (4400, 5400)])   # side plates
cyl("en_luleg", KNEE, 470, 560, "x", 12)                                                              # knee actuator drum
add("en_llleg", inflate(_orig("en_llleg"), (1.2, 1.2, 1.0)))                                          # core of the shin
add("en_llleg", [[x, y, zz] for x in (1000, 1850) for y in (1500, 1700) for zz in (3250, 4050)])      # kneecap plate (the knee points rearward)
add("en_llleg", [[x, y, zz] for x in (950, 1750) for y in (-520, -120) for zz in (1700, 3500)])       # front shin shell
rod("en_llleg", (KNEE[0], KNEE[1] + 50, KNEE[2] - 150), (ANK[0], ANK[1] + 500, ANK[2] + 450), 170)    # calf actuator behind the shin
add("en_llleg", [[x, y, zz] for x in (1050, 1550) for y in (250, 850) for zz in (1700, 2800)])        # calf housing
cyl("en_llleg", ANK, 380, 500, "x", 12)                                                               # ankle actuator
add("en_lfoot", inflate(_orig("en_lfoot"), (1.2, 1.2, 1.0)))
add("en_lfoot", [[x, y, zz] for x in (800, 1800) for y in (-650, 550) for zz in (15, 700)])           # separate foot block
add("joint_litoe", np.maximum(inflate(_orig("joint_litoe"), (1.4, 1.0, 2.2), about=(0, 0, 100)), [-1e9, -1e9, 15]))
add("joint_lotoe", np.maximum(inflate(_orig("joint_lotoe"), (1.0, 1.4, 2.2), about=(0, 0, 100)), [-1e9, -1e9, 15]))
for p_, q_ in (("en_luleg", "en_ruleg"), ("en_llleg", "en_rlleg"), ("en_lfoot", "en_rfoot"), ("joint_litoe", "joint_ritoe"), ("joint_lotoe", "joint_rotoe")):
    mirror(p_, q_, 120)
# separate shoulder housings on the arm joints
for s_, side, x in ((-1, "r", -1413), (1, "l", 1502)):
    add(f"en_{side}uarm", bx((x, 166, 7425), (780, 900, 900)))

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
