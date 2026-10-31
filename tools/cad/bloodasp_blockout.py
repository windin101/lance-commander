#!/usr/bin/env python3
"""Blood Asp in-house model, step 1: the blockout (LANCE-37).  Same route as the Enfield.

Parts are convex hulls in the ORIGINAL game's rest frame (mm, Z up, faces -Y, +X is its left), one per original mesh node
of game/assets/mechs/bloodasp.glb, built on the original's own vertices (dimensions-only reference), inflated into chunky
layered volumes plus our own detail.  chassis/bloodasp.json Prime (components.json ids): 2x Clan Gauss Rifle with ammo (the two
long shoulder-mounted rifles, joint_*shouldergun, tips at y -5519), 2x Clan Heavy Large Laser and 2x Clan Heavy Laser (the
long forearm units ba_*gun, weapon_*arm), 3x Clan Streak SRM2 (torso front).  A 90 t assault mech: wide shoulders, a
hunched forward lean, four splayed claw toes per foot.
    python3 -I tools/cad/bloodasp_blockout.py OUT.npz [HULLS.npz]"""
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
    og, ob = R.load_glb(str(Path(__file__).resolve().parents[2] / "game/assets/mechs/bloodasp.glb")); W = R.world_matrices(og)
    names = [n.get("name") for n in og["nodes"]]
    i = names.index(node); n = og["nodes"][i]
    pr = og["meshes"][n["mesh"]]["primitives"][0]
    pp = R.read_accessor(og, ob, pr["attributes"]["POSITION"]).astype(float)
    pw = (np.c_[pp, np.ones(len(pp))] @ W[i].T)[:, :3]
    return np.unique((np.c_[pw[:, 0], -pw[:, 2], pw[:, 1]] * 1000).round(), axis=0)


def inflate(pts, f, about=None):
    pts = np.asarray(pts, float); c = pts.mean(0) if about is None else np.asarray(about, float)
    return c + (pts - c) * np.asarray(f, float)


def rod(part, a, b, r, n=8):
    a, b = np.array(a, float), np.array(b, float); ax = (b - a) / np.linalg.norm(b - a)
    u = np.cross(ax, [0, 0, 1.0]); u = u / np.linalg.norm(u) if np.linalg.norm(u) > 1e-6 else np.array([1.0, 0, 0]); v = np.cross(ax, u)
    t = np.arange(n) * 2 * np.pi / n
    add(part, [p + r * (np.cos(k) * u + np.sin(k) * v) for p in (a, b) for k in t])


# ------------------------------------------------------------------ pelvis with skirts (joint_hip (-11, -87, 6275))
add("ba_hip", inflate(_orig("ba_hip"), (1.25, 1.2, 1.0)))
layers("ba_hip", (6900, -1300, 1300, -900, 1000), (6100, -1500, 1500, -1000, 1200))                  # hip skirts over the thigh tops

# ------------------------------------------------------------------ torso: wide shoulders, hump, front SRM boxes, head blister (joint_torso (12, -63, 7538))
T = _orig("ba_torso")
add("ba_torso", inflate(T, (1.15, 1.15, 1.0), about=(0, T[:, 1].mean(), 8800)))
layers("ba_torso", (7600, -1100, 1100, -800, 900), (8200, -2000, 2000, -1500, 1500))                  # belly under the chest
layers("ba_torso", (8300, -1500, 1500, 1500, 2700), (10200, -1400, 1400, 1500, 2700))                 # engine hump at the back
for x in (-1250, 0, 1250):                                                                            # 3x Streak SRM2: a box with two tube openings
    box("ba_torso", x - 330, x + 330, -2650, -2100, 8700, 9300)
    for dx in (-130, 130):
        cyl("ba_torso", (x + dx, -2750, 9000), 95, 90, "y", 8)
box("ba_torso", -480, 480, -1700, -900, 9300, 10100)                                                  # head blister / cockpit
box("ba_torso", -330, 330, -2250, -1750, 7900, 8500)                                                  # chin sensor block (weapon_centertorso)

# ------------------------------------------------------------------ the two Gauss rifles on the shoulders: long barrels, coil collars, receivers
for side, s_ in (("r", -1), ("l", 1)):
    P_ = f"joint_{side}shouldergun"; cx = s_ * 1990
    box(P_, cx - 430, cx + 430, -1500, 1700, 9750, 10900)                                               # receiver block on the shoulder (chunky only here)
    add(P_, inflate(_orig(P_), (1.0, 0.45, 0.5), about=(cx, 0, 10300)))                                  # the original's own rear section, trimmed to the receiver
    cyl(P_, (cx, -3500, 10300), 250, 2000, "y", 12)                                                     # long slim level barrel, tip y -5500
    for y in (-2200, -3000, -3800, -4600):
        cyl(P_, (cx, y, 10300), 270, 90, "y", 12)                                                       # slight coil collars
    cyl(P_, (cx, -5500, 10300), 230, 110, "y", 12)                                                      # muzzle

# ------------------------------------------------------------------ arms: shoulder block, forearm units carrying a Heavy Large Laser and a Heavy Laser
for side, s_ in (("r", -1), ("l", 1)):
    add(f"ba_{side}uarm", inflate(_orig(f"ba_{side}uarm"), (1.25, 1.9, 1.3)))
    add(f"ba_{side}gun", inflate(_orig(f"ba_{side}gun"), (1.2, 1.0, 1.25)))
    x = s_ * 4630
    cyl(f"ba_{side}gun", (x - s_ * 250, -3600, 7100), 260, 330, "y", 12)                                # heavy large laser barrel
    cyl(f"ba_{side}gun", (x + s_ * 250, -3500, 7100), 190, 330, "y", 10)                                # heavy laser barrel
    box(f"ba_{side}gun", x - 520, x + 520, -3000, -2200, 6650, 7550)                                    # laser housing

# ------------------------------------------------------------------ legs: thigh shell over pistons, knee drum, shin, ankle, foot block, four claw toes
HIP, KNEE, ANK = (748, -413, 6097), (2008, 2271, 4679), (3472, 226, 1877)
add("ba_luleg", inflate(_orig("ba_luleg"), (1.15, 1.0, 1.0)))
cyl("ba_luleg", HIP, 640, 520, "x", 12)                                                              # hip barrel
for dx in (-380, 380):                                                                                # inner frame: pistons hip -> knee
    rod("ba_luleg", (HIP[0] + dx, HIP[1] + 200, HIP[2] - 300), (KNEE[0] + dx * 0.6, KNEE[1] - 300, KNEE[2] + 300), 130)
add("ba_luleg", [[x, y, zz] for x in (400, 1700) for y in (-1500, -900) for zz in (5000, 6600)])      # front thigh shell
add("ba_luleg", [[x, y, zz] for x in (1200, 2300) for y in (1000, 1500) for zz in (4800, 5900)])      # shell over the lower thigh
cyl("ba_luleg", KNEE, 560, 650, "x", 12)                                                              # knee actuator drum
add("ba_llleg", inflate(_orig("ba_llleg"), (1.2, 1.2, 1.0)))
add("ba_llleg", [[x, y, zz] for x in (2000, 3000) for y in (-500, -100) for zz in (2600, 4400)])      # front shin shell
rod("ba_llleg", (KNEE[0] + 100, KNEE[1] + 300, KNEE[2] - 200), (ANK[0] - 200, ANK[1] + 700, ANK[2] + 700), 200)    # calf actuator
cyl("ba_llleg", ANK, 440, 560, "x", 12)                                                               # ankle actuator
add("ba_lfoot", inflate(_orig("ba_lfoot"), (1.2, 1.2, 1.0)))
add("ba_lfoot", [[x, y, zz] for x in (2700, 4200) for y in (-900, 800) for zz in (10, 900)])         # separate foot block
for t in ("lbtoe", "litoe", "lftoe", "lotoe"):
    T_ = _orig(f"joint_{t}"); c_ = T_.mean(0)
    add(f"joint_{t}", np.maximum(inflate(T_, (1.0, 1.0, 1.0), about=c_) * 1.0 + 0, [-1e9, -1e9, -3]))
    # solid claw: the original's own wedge points plus a thick base block, so it is a claw and not a blade
    add(f"joint_{t}", [[c_[0] + dx, c_[1] + dy, z] for dx in (-260, 260) for dy in (-260, 260) for z in (-3, 480)])
for p_, q_ in (("ba_luleg", "ba_ruleg"), ("ba_llleg", "ba_rlleg"), ("ba_lfoot", "ba_rfoot"), ("joint_lbtoe", "joint_rbtoe"),
               ("joint_litoe", "joint_ritoe"), ("joint_lftoe", "joint_rftoe"), ("joint_lotoe", "joint_rotoe")):
    mirror(p_, q_, -2)

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
