#!/usr/bin/env python3
"""Owner map of a rigidly skinned HD mech: every triangle coloured by the skeleton part that moves it.

    python3 -I tools/art/owner_map.py game/assets/mechs/<mech>_hd.glb out.png [--zmin MM --zmax MM] [--anim Walk --t 0.15]

Front, side and back views, game frame (mm, Z up), with a legend: the bind pose, or with --anim the animation
sampled at --t (a fraction of its length; linear keys, nlerp rotations) so the seams that open in motion show. Use it to check where
tools/art/stl_rig.py put each seam: a seam through the middle of a solid block of hull tears when the two parts move
apart in the walk (the torso twists against the pelvis; the arms swing against the torso).
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hd_rig as R  # noqa: E402

PAL = [(230, 25, 75), (60, 180, 75), (255, 225, 25), (0, 130, 200), (245, 130, 48), (145, 30, 180), (70, 240, 240),
       (240, 50, 230), (210, 245, 60), (250, 190, 212), (0, 128, 128), (170, 110, 40), (128, 0, 0), (170, 255, 195),
       (128, 128, 0), (0, 0, 128), (128, 128, 128), (255, 215, 180)]


def view(T, col, u, v, dep, flip, k, lo, hi):
    W, Hh = int((hi[u] - lo[u]) * k) + 20, int((hi[v] - lo[v]) * k) + 20
    im = Image.new("RGB", (W, Hh), "white"); d = ImageDraw.Draw(im)
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    L = np.array([0.4, -0.5, 0.75]); L /= np.linalg.norm(L)
    br = 0.45 + 0.55 * np.abs(n @ L)
    pu = (T[:, :, u] - lo[u]) * k * (1 if flip > 0 else -1) + (10 if flip > 0 else W - 10)
    pv = Hh - 10 - (T[:, :, v] - lo[v]) * k
    for t in np.argsort((T[:, :, dep] * flip).mean(1)):
        c = tuple(int(x * br[t]) for x in col[t])
        d.polygon([(pu[t, 0], pv[t, 0]), (pu[t, 1], pv[t, 1]), (pu[t, 2], pv[t, 2])], fill=c)
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("glb"); ap.add_argument("out")
    ap.add_argument("--zmin", type=float); ap.add_argument("--zmax", type=float)
    ap.add_argument("--px", type=int, default=700, help="height of each view in pixels")
    ap.add_argument("--anim"); ap.add_argument("--t", type=float, default=0.0)
    a = ap.parse_args()
    og, ob = R.load_glb(a.glb)
    mi = next(i for i, m in enumerate(og["meshes"]) if m["name"] == "hd_body")
    node = next(n for n in og["nodes"] if n.get("mesh") == mi)
    pr = og["meshes"][mi]["primitives"][0]
    P = R.read_accessor(og, ob, pr["attributes"]["POSITION"])
    Jt = R.read_accessor(og, ob, pr["attributes"]["JOINTS_0"])[:, 0].astype(int)
    I = R.read_accessor(og, ob, pr["indices"]).reshape(-1, 3)
    joints = og["skins"][node["skin"]]["joints"]
    if a.anim:  # skin: v' = W_pose[j] @ inv(W_bind[j]) @ v, one joint per vertex
        Wb = R.world_matrices(og)
        an = next(x for x in og["animations"] if x["name"] == a.anim)
        dur = max(R.read_accessor(og, ob, sm["input"]).max() for sm in an["samplers"])
        tt = a.t * dur
        for ch in an["channels"]:
            sm = an["samplers"][ch["sampler"]]
            ti, vo = R.read_accessor(og, ob, sm["input"]).reshape(-1), R.read_accessor(og, ob, sm["output"])
            k = np.searchsorted(ti, tt).clip(1, len(ti) - 1) if len(ti) > 1 else 0
            if len(ti) > 1:
                f = float(np.clip((tt - ti[k - 1]) / (ti[k] - ti[k - 1] + 1e-12), 0, 1)); v0, v1 = vo[k - 1], vo[k]
                if ch["target"]["path"] == "rotation" and np.dot(v0, v1) < 0:
                    v1 = -v1
                v = v0 * (1 - f) + v1 * f
            else:
                v = vo[0]
            if ch["target"]["path"] == "rotation":
                v = v / np.linalg.norm(v)
            og["nodes"][ch["target"]["node"]][ch["target"]["path"]] = list(map(float, v))
        Wp = R.world_matrices(og)
        M = np.stack([Wp[joints[j]] @ np.linalg.inv(Wb[joints[j]]) for j in range(len(joints))])[Jt]
        P = np.einsum("nij,nj->ni", M[:, :3, :3], P) + M[:, :3, 3]
    # glTF m Y-up -> game mm Z-up
    V = np.c_[P[:, 0], -P[:, 2], P[:, 1]] * 1000
    T, own = V[I], Jt[I[:, 0]]
    keep = np.ones(len(T), bool)
    if a.zmin is not None:
        keep &= T[:, :, 2].mean(1) >= a.zmin
    if a.zmax is not None:
        keep &= T[:, :, 2].mean(1) <= a.zmax
    T, own = T[keep], own[keep]
    names = [og["nodes"][joints[j]]["name"] for j in range(len(joints))]
    used = sorted(set(own.tolist()))
    col = np.array([PAL[used.index(o) % len(PAL)] for o in own])
    lo, hi = T.reshape(-1, 3).min(0), T.reshape(-1, 3).max(0)
    k = a.px / (hi[2] - lo[2])
    ims = [view(T, col, 0, 2, 1, 1, k, lo, hi),      # front: looking along +Y (forward is -Y), x across
           view(T, col, 1, 2, 0, 1, k, lo, hi),      # side: from +X, forward to the left
           view(T, col, 0, 2, 1, -1, k, lo, hi)]     # back
    leg = 18 * len(used) + 10
    out = Image.new("RGB", (sum(i.width for i in ims) + 180, max(max(i.height for i in ims), leg)), "white")
    x = 0
    for im in ims:
        out.paste(im, (x, 0)); x += im.width
    d = ImageDraw.Draw(out)
    for i, o in enumerate(used):
        d.rectangle([x + 8, 8 + 18 * i, x + 22, 22 + 18 * i], fill=PAL[i % len(PAL)])
        d.text((x + 28, 9 + 18 * i), names[o], fill="black")
    out.save(a.out)
    print(f"{a.out}: {len(T)} tris, {len(used)} parts")


if __name__ == "__main__":
    main()
