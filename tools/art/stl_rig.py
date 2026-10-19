#!/usr/bin/env python3
"""Rig a (posed) third-party mech sculpt onto an MC2 mech's skeleton.

    python3 -I tools/art/stl_rig.py <mech> <model.stl> [--joints J.json] [--diag D.png] [--install]
        [--source "Title by Author, URL"] [--licence "CC BY-NC-SA 4.0"]

General version of tools/art/stl_rig_vulture.py (which keeps the Vulture's hand-read joints).
  1. Load the STL (mm, Z up, forward -Y; "turn": true in J.json turns it 180 degrees), cut off a display
     base if one spans the gap between the feet, scale to the original model's height, centre it.
  2. Find each leg's hip, knee and ankle: the hip just above the crotch (the lowest height where the gap
     between the legs closes), the ankle above the foot, the knee at the point of the leg's traced centre
     line farthest from the hip-ankle line. J.json overrides any of them ([y, z] in game mm; x comes from the
     mesh). --diag draws them on side views; check it before trusting a build.
  3. Skeleton: MC2's leg bone directions with the sculpt's lengths. joint_root's rest height and every
     animation's root keys drop with the hip. Upper-body joints move with the sculpt's upper-body bounds.
  4. Legs: per triangle, nearest bone; thigh and shin turned about their upper joint onto the new bone, the
     foot moved to the new ankle. Upper body: nearest original part, after the original's upper body is
     mapped onto the sculpt's bounds. Seams majority-smoothed, islands < 40 tris rejoined, joint caps added.
  5. Paint by region; write <mech>_hd.glb + <mech>_hd_paint.bin to original/hd/<mech>/stl/, or with
     --install to game/assets/mechs (plus original/hd/<mech>/provenance.json, kind "adapted").
"""
import argparse
import json
import struct
import sys
import time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cad_mech as C  # noqa: E402
import hd_rig as R    # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def load_stl(path):
    data = Path(path).read_bytes()
    n = struct.unpack_from("<I", data, 80)[0]
    if 84 + 50 * n != len(data):
        raise SystemExit(f"{path}: not a plain binary STL")
    rec = np.frombuffer(data, dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]), count=n, offset=84)
    return rec["v"].astype(float)


def sc(v_gl):   # glTF m Y-up -> mm Z-up
    v = np.asarray(v_gl, float)
    return np.array([v[0], -v[2], v[1]]) * 1000.0


def gl(v_sc):   # mm Z-up -> glTF m Y-up (rows)
    v = np.atleast_2d(np.asarray(v_sc, float)) / 1000.0
    return np.c_[v[:, 0], v[:, 2], -v[:, 1]]


def rot_between(a, b):
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    v, c = np.cross(a, b), float(a @ b)
    if np.linalg.norm(v) < 1e-9:
        return np.eye(3)
    k = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + k + k @ k / (1 + c)


def seg_dist(p, a, b):
    ab = b - a
    t = np.clip(((p - a) @ ab) / (ab @ ab), 0, 1)
    return np.linalg.norm(p - (a + t[:, None] * ab), axis=1)


def drum(c, r, ln, sides=16):
    """Closed prism along X centred on c (mm, Z up), (n, 3, 3) triangles wound outward."""
    ang = np.linspace(0, 2 * np.pi, sides, endpoint=False)
    ring = np.c_[np.cos(ang), np.sin(ang)] * r
    x0, x1 = c[0] - ln / 2, c[0] + ln / 2
    P = lambda x, i: np.array([x, c[1] + ring[i % sides, 0], c[2] + ring[i % sides, 1]])
    e0, e1 = np.array([x0, c[1], c[2]]), np.array([x1, c[1], c[2]])
    tris = []
    for i in range(sides):
        tris += [[P(x0, i), P(x1, i + 1), P(x1, i)], [P(x0, i), P(x0, i + 1), P(x1, i + 1)],
                 [e0, P(x0, i), P(x0, i + 1)], [e1, P(x1, i + 1), P(x1, i)]]
    tris = np.array(tris)
    for t in tris:  # make each face point away from the drum's axis (or out of its ends)
        n = np.cross(t[1] - t[0], t[2] - t[0]); m = t.mean(0)
        out = np.array([np.sign(m[0] - c[0]) if abs(n[0]) > 0.9 * np.linalg.norm(n) else 0, m[1] - c[1], m[2] - c[2]])
        if n @ out < 0:
            t[[1, 2]] = t[[2, 1]]
    return tris


def mesh_parts(og, ob, W):
    out = {}
    for i, n in enumerate(og["nodes"]):
        if "mesh" in n:
            prim = og["meshes"][n["mesh"]]["primitives"][0]
            p = R.read_accessor(og, ob, prim["attributes"]["POSITION"]).astype(float)
            pw = (np.c_[p, np.ones(len(p))] @ W[i].T)[:, :3]
            out[i] = np.c_[pw[:, 0], -pw[:, 2], pw[:, 1]] * 1000.0
    return out


def part_under(og, names, *joints):
    for jn in joints:
        if jn in names:
            for c in og["nodes"][names[jn]].get("children", []):
                if "mesh" in og["nodes"][c]:
                    return c
    return None


def detect(T, H, W):
    P = np.concatenate([T.reshape(-1, 3), T.mean(1)])
    step = 0.01 * H
    strip = np.abs(P[:, 0]) < 0.05 * W
    zc = next((z for z in np.arange(0.12 * H, 0.75 * H, step) if (strip & (np.abs(P[:, 2] - z) < step)).sum() > 6), 0.45 * H)
    J = {}
    for s, sign in (("l", 1), ("r", -1)):
        side = P[:, 0] * sign > 0.06 * W
        def centre(z, near=None, rad=None):
            m = side & (np.abs(P[:, 2] - z) < 1.5 * step)
            if near is not None:
                m &= np.hypot(P[:, 0] - near[0], P[:, 1] - near[1]) < rad
            return P[m].mean(0) if m.sum() > 3 else None
        foot = side & (P[:, 2] < 0.05 * H)
        fc = P[foot].mean(0) if foot.any() else np.array([sign * 0.25 * W, 0.0, 0.0])
        ankle = centre(0.11 * H, fc, 0.3 * W)
        ankle = ankle if ankle is not None else fc + [0, 0, 0.11 * H]
        hip = centre(zc + 0.04 * H)
        hip = hip if hip is not None else np.array([sign * 0.2 * W, 0.0, zc + 0.04 * H])
        line, prev = [], ankle
        for z in np.arange(ankle[2] + 2 * step, hip[2] - step, 2 * step):
            c = centre(z, prev, 0.22 * W)
            if c is not None:
                line.append(c); prev = c
        line = np.array(line) if line else np.array([(hip + ankle) / 2])
        # knee: the breakpoint of the best two-segment fit hip -> knee -> ankle (robust to armour bulges,
        # which pull a max-deviation pick onto the shin pod)
        pts = np.vstack([line, hip])
        best, knee = None, (hip + ankle) / 2
        for c in line[2:-2] if len(line) > 5 else line:
            err = np.minimum(seg_dist(pts, hip, c), seg_dist(pts, c, ankle)).sum()
            if best is None or err < best:
                best, knee = err, c
        J[s] = {"hip": hip, "knee": knee, "ankle": ankle}
    return J


def shade_render(T, u, v, dep, flip, lo_u, hi_u, top, k, Hp, light=(0.4, -0.5, 0.75)):
    """Flat-shaded painter's-algorithm render of triangles T onto the (u, v) plane; dep*flip is toward the viewer."""
    from PIL import Image, ImageDraw
    Wp = int((hi_u - lo_u) * k) + 1
    im = Image.new("RGB", (Wp, Hp), (255, 255, 255)); d = ImageDraw.Draw(im)
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    L = np.array(light); L = L / np.linalg.norm(L)
    br = (60 + 180 * np.abs(n @ L)).astype(int)
    order = np.argsort((T[:, :, dep] * flip).mean(1))       # far first
    pu = (T[:, :, u] - lo_u) * k; pv = Hp - 10 - T[:, :, v] * k
    for t in order:
        c = int(br[t]); d.polygon([(pu[t, 0], pv[t, 0]), (pu[t, 1], pv[t, 1]), (pu[t, 2], pv[t, 2])], fill=(c, c, c))
    return im, d


def diag_sheet(T, J, path, H, title=""):
    from PIL import Image, ImageDraw
    P = np.concatenate([T.reshape(-1, 3), T.mean(1), (T[:, 0] + T[:, 1]) / 2])
    tiles = []
    for s, sign in (("l", 1), ("r", -1)):
        Cn = T.mean(1)
        legT = T[(Cn[:, 0] * sign > 0.04 * np.ptp(T[..., 0])) & (Cn[:, 2] < 0.62 * H)]   # fixed crop: a wrong hip stays in frame
        lo, hi = legT[..., 1].min() - 300, legT[..., 1].max() + 300
        k = 600 / (0.64 * H)
        Hp = 620
        im, d = shade_render(legT, 1, 2, 0, sign, lo, hi, 0, k, Hp)
        Wp = im.width
        for gy in range(int(np.ceil(lo / 250) * 250), int(hi), 250):
            d.line([((gy - lo) * k, 0), ((gy - lo) * k, Hp)], fill=(255, 150, 150) if gy % 1000 == 0 else (255, 215, 215))
            if gy % 500 == 0:
                d.text(((gy - lo) * k + 2, Hp - 22), str(gy), fill=(190, 0, 0))
        for gz in range(0, int(H) + 1, 250):
            d.line([(0, Hp - 10 - gz * k), (Wp, Hp - 10 - gz * k)], fill=(150, 150, 255) if gz % 1000 == 0 else (215, 215, 255))
            if gz % 500 == 0:
                d.text((2, Hp - 10 - gz * k - 12), str(gz), fill=(0, 0, 190))
        pts = []
        for kk, col in (("hip", (220, 0, 0)), ("knee", (0, 150, 0)), ("ankle", (0, 0, 220))):
            x0, y0 = (J[s][kk][1] - lo) * k, Hp - 10 - J[s][kk][2] * k
            pts.append((x0, y0))
            d.ellipse([x0 - 7, y0 - 7, x0 + 7, y0 + 7], outline=col, width=3)
            d.text((x0 + 9, y0 - 6), f"{kk} [{J[s][kk][1]:.0f}, {J[s][kk][2]:.0f}]", fill=col)
        d.line(pts, fill=(255, 120, 0), width=2)
        d.text((4, 4), f"{title} {s} leg (forward = left)", fill=(0, 0, 0))
        tiles.append(im)
    sheet = Image.new("RGB", (sum(t.width for t in tiles) + 10, 620), "white")
    x = 0
    for t in tiles:
        sheet.paste(t, (x, 0)); x += t.width + 10
    sheet.save(path)


def views_sheet(T, path, H, title=""):
    """Whole-model side (forward on the left) and front views on a 500 mm grid: check facing, base, scale."""
    from PIL import Image, ImageDraw
    P = np.concatenate([T.reshape(-1, 3), T.mean(1)])
    tiles = []
    for name, u, dep, flip in (("side, seen from +X (forward = left)", 1, 0, 1), ("front, seen from -Y", 0, 1, -1)):
        lo, hi = T[..., u].min() - 300, T[..., u].max() + 300
        k = 600 / (H + 300); Hp = 620
        im, d = shade_render(T, u, 2, dep, flip, lo, hi, 0, k, Hp)
        Wp = im.width
        for gu in range(int(np.ceil(lo / 500) * 500), int(hi), 500):
            d.line([((gu - lo) * k, 0), ((gu - lo) * k, Hp)], fill=(255, 200, 200))
            if gu % 1000 == 0: d.text(((gu - lo) * k + 2, Hp - 22), str(gu), fill=(190, 0, 0))
        for gz in range(0, int(H) + 1, 500):
            d.line([(0, Hp - 10 - gz * k), (Wp, Hp - 10 - gz * k)], fill=(200, 200, 255))
            if gz % 1000 == 0: d.text((2, Hp - 22 - gz * k), str(gz), fill=(0, 0, 190))
        d.text((4, 4), f"{title}: {name}", fill=(0, 0, 0))
        tiles.append(im)
    sheet = Image.new("RGB", (sum(t.width for t in tiles) + 10, 620), "white"); x = 0
    for t in tiles:
        sheet.paste(t, (x, 0)); x += t.width + 10
    sheet.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mech"); ap.add_argument("stl")
    ap.add_argument("--joints"); ap.add_argument("--diag"); ap.add_argument("--views"); ap.add_argument("--install", action="store_true")
    ap.add_argument("--source", default=""); ap.add_argument("--licence", default="CC BY-NC-SA 4.0")
    a = ap.parse_args()
    over = json.loads(Path(a.joints).read_text()) if a.joints and Path(a.joints).exists() else {}

    glb = ROOT / f"game/assets/mechs/{a.mech}.glb"
    og, ob = R.load_glb(str(glb))
    names = {n.get("name"): i for i, n in enumerate(og["nodes"])}
    W0 = R.world_matrices(og)
    parts0 = mesh_parts(og, ob, W0)
    allp = np.concatenate(list(parts0.values()))
    H_o = np.ptp(allp[:, 2])

    # 1. load, orient, base, scale
    T = load_stl(a.stl)
    if over.get("turn"):
        T = T * np.array([-1.0, -1.0, 1.0])
    T[..., 2] -= T[..., 2].min()
    H0 = T[..., 2].max(); Cn0 = T.mean(1)
    cut = over.get("base_cut")  # raw STL units
    if cut is None:
        low = Cn0[:, 2] < 0.04 * H0
        mid = np.abs(Cn0[:, 0] - np.median(Cn0[:, 0])) < 0.04 * np.ptp(T[..., 0])
        if (low & mid).sum() > 20:
            cut = float(np.sort(Cn0[low, 2])[int(0.98 * low.sum())]) + 0.002 * H0
    if cut:
        T = T[T.mean(1)[:, 2] > cut]; T[..., 2] -= T[..., 2].min()
    k = H_o / T[..., 2].max()
    T = T * k
    flat = T.reshape(-1, 3)
    T[..., :2] -= (flat[:, :2].min(0) + flat[:, :2].max(0)) / 2
    H, W = T[..., 2].max(), np.ptp(T[..., 0])
    Cn = T.mean(1); nt = len(T)
    print(f"{a.mech}: {nt} tris, x{k:.1f}, {W/1000:.2f} x {np.ptp(T[..., 1])/1000:.2f} x {H/1000:.2f} m" + (f", base cut at {cut:.2f}" if cut else ""))

    if a.views:
        views_sheet(T, a.views, H, a.mech)
    # 2. joints
    J = detect(T, H, W)
    V = T.reshape(-1, 3)
    for s, sign in (("l", 1), ("r", -1)):
        for kk in ("hip", "knee", "ankle"):
            if kk in over.get(s, {}):
                y, z = over[s][kk]
                near = (V[:, 0] * sign > 0.06 * W) & (np.hypot(V[:, 1] - y, V[:, 2] - z) < 450)
                J[s][kk] = np.array([V[near, 0].mean() if near.any() else J[s][kk][0], y, z])
    if a.diag:
        diag_sheet(T, J, a.diag, H, a.mech)
    for s in "lr":
        print(f"  {s}: " + "  ".join(f"{kk} [{J[s][kk][1]:.0f}, {J[s][kk][2]:.0f}]" for kk in ("hip", "knee", "ankle")))

    # 3. skeleton
    legs = {s: (f"joint_{s}uleg", f"joint_{s}lleg", f"joint_{s}ankle") for s in "lr"}
    thigh = np.mean([np.linalg.norm(J[s]["knee"] - J[s]["hip"]) for s in "lr"])
    shin = np.mean([np.linalg.norm(J[s]["ankle"] - J[s]["knee"]) for s in "lr"])
    ankle_h = np.mean([J[s]["ankle"][2] for s in "lr"])
    for s in "lr":
        for jn, ln in ((legs[s][1], thigh), (legs[s][2], shin)):
            t = np.array(og["nodes"][names[jn]]["translation"])
            og["nodes"][names[jn]]["translation"] = (t / np.linalg.norm(t) * ln / 1000).tolist()
    drop = np.mean([sc(R.world_matrices(og)[names[legs[s][2]]][:3, 3])[2] for s in "lr"]) - ankle_h
    og["nodes"][names["joint_root"]]["translation"][1] -= drop / 1000
    for an in og["animations"]:
        for ch in an["channels"]:
            if ch["target"]["path"] == "translation" and og["nodes"][ch["target"]["node"]]["name"] == "joint_root":
                si = an["samplers"][ch["sampler"]]["output"]
                acc = og["accessors"][si]; view = og["bufferViews"][acc["bufferView"]]
                vals = R.read_accessor(og, ob, si).astype(np.float32).copy(); vals[:, 1] -= drop / 1000
                off = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
                ob[off:off + vals.nbytes] = vals.tobytes()
    W2 = R.world_matrices(og)
    tgt = {s: {kk: sc(W2[names[legs[s][i]]][:3, 3]) for i, kk in enumerate(("hip", "knee", "ankle"))} for s in "lr"}
    shift = np.mean([tgt[s]["hip"] - J[s]["hip"] for s in "lr"], axis=0)

    # upper body: map the original's upper body (rest) onto the sculpt's upper body (game frame)
    hip_old = np.mean([sc(W0[names[legs[s][0]]][:3, 3])[2] for s in "lr"])
    up_parts = {i: p for i, p in parts0.items() if p[:, 2].mean() > hip_old - 0.03 * H_o}
    O = np.concatenate(list(up_parts.values()))
    hip_new = np.mean([tgt[s]["hip"][2] for s in "lr"])
    S = Cn[Cn[:, 2] + shift[2] > hip_new - 0.03 * H] + shift
    O_lo, O_hi, S_lo, S_hi = O.min(0), O.max(0), S.min(0), S.max(0)
    norm = lambda p: S_lo + (p - O_lo) / (O_hi - O_lo + 1e-9) * (S_hi - S_lo)
    torso = names["joint_torso"]
    def move(i, parent_world_new):  # every joint under the torso follows the mapping
        for c in og["nodes"][i].get("children", []):
            cn = og["nodes"][c]
            if not cn["name"].startswith("joint_"):
                continue
            new_w = norm(sc(W0[c][:3, 3]))
            cn["translation"] = gl(new_w - parent_world_new)[0].tolist()
            move(c, new_w)
    move(torso, sc(R.world_matrices(og)[torso][:3, 3]))

    # 4. assign triangles
    owner = np.full(nt, -1)
    xform = {}
    for s, sign in (("l", 1), ("r", -1)):
        j = J[s]
        legm = (Cn[:, 0] * sign > 0.04 * W) & (Cn[:, 2] < j["hip"][2] + 0.03 * H)
        d = np.stack([seg_dist(Cn, j["hip"], j["knee"]), seg_dist(Cn, j["knee"], j["ankle"]),
                      np.where(Cn[:, 2] < j["ankle"][2] + 0.02 * H, 0, 1e9) + seg_dist(Cn, j["ankle"], j["ankle"] * [1, 1, 0])], 1)
        which = d.argmin(1)
        nodes_ = [part_under(og, names, legs[s][0]), part_under(og, names, legs[s][1]),
                  part_under(og, names, legs[s][2], f"joint_{s}foot")]
        for kk, node in enumerate(nodes_):
            if node is None:
                continue
            owner[legm & (which == kk)] = node
            xform[node] = ("rot", j["hip"], j["knee"], tgt[s]["hip"], tgt[s]["knee"]) if kk == 0 else \
                          ("rot", j["knee"], j["ankle"], tgt[s]["knee"], tgt[s]["ankle"]) if kk == 1 else \
                          ("move", j["ankle"], tgt[s]["ankle"])
    ids = list(up_parts)
    pts = np.concatenate([norm(up_parts[i]) for i in ids])
    lab = np.concatenate([[i] * len(up_parts[i]) for i in ids])
    free = owner < 0
    owner[free] = lab[cKDTree(pts).query(Cn[free] + shift)[1]]

    # seams: majority smoothing, then rejoin islands < 40 tris
    key = np.unique(np.round(V, 1), axis=0, return_inverse=True)[1].reshape(-1, 3)
    vt = {}
    for t in range(nt):
        for v in key[t]:
            vt.setdefault(v, []).append(t)
    for _ in range(3):
        vm = {v: np.bincount(owner[ts]).argmax() for v, ts in vt.items()}
        new = owner.copy()
        for t in range(nt):
            cand = [vm[v] for v in key[t]]
            b = max(set(cand), key=cand.count)
            if cand.count(b) >= 2:
                new[t] = b
        if (new == owner).all():
            break
        owner = new
    moved = 0
    for node in set(owner.tolist()):
        par = {}
        def f(x):
            while par.setdefault(x, x) != x:
                par[x] = par[par[x]]; x = par[x]
            return x
        idx = np.flatnonzero(owner == node)
        for t in idx:
            r0 = f(("t", t))
            for v in key[t]:
                par[f(("v", v))] = r0
        comps = {}
        for t in idx:
            comps.setdefault(f(("t", t)), []).append(t)
        for c in comps.values():
            if len(c) < 40:
                nb = [owner[u] for t in c for v in key[t] for u in vt[v] if owner[u] != node]
                if nb:
                    owner[c] = max(set(nb), key=nb.count); moved += len(c)

    out = T + shift
    for node, x in xform.items():
        m = owner == node
        if x[0] == "rot":
            _, a0, a1, b0, b1 = x
            out[m] = (T[m] - a0) @ rot_between(a1 - a0, b1 - b0).T + b0
        else:
            out[m] = T[m] - x[1] + x[2]

    # 5. paint
    paint = np.array(["base"] * nt, dtype=object)
    for node in set(owner.tolist()):
        nm = og["nodes"][node]["name"].lower()
        m = owner == node
        if any(w_ in nm for w_ in ("missile", "launcher")):
            paint[m] = "hl1"
        if "gun" in nm and m.any():
            idx = np.flatnonzero(m)
            paint[idx[Cn[idx, 1] < np.percentile(Cn[idx, 1], 10)]] = "dark"
    paint[Cn[:, 2] < 0.035 * H] = "dark"
    for s in "lr":
        for kk in ("hip", "knee", "ankle"):
            paint[np.linalg.norm(Cn - J[s][kk], axis=1) < 0.04 * H] = "metal"
    caps, cap_owner = [], []
    for s in "lr":
        nodes_ = [part_under(og, names, legs[s][0]), part_under(og, names, legs[s][1]), part_under(og, names, legs[s][2], f"joint_{s}foot")]
        for jn, child in zip(("hip", "knee", "ankle"), nodes_):
            if child is not None:
                r = float(np.clip(0.045 * H, 230, 470)) * (0.65 if jn == "ankle" else 1.0)
                caps.append(drum(tgt[s][jn], r, float(np.clip(0.08 * W, 380, 760)))); cap_owner += [child] * len(caps[-1])
    caps = np.concatenate(caps)
    out = np.concatenate([out, caps]); owner = np.concatenate([owner, cap_owner])
    paint = np.concatenate([paint, ["dark"] * len(caps)])

    pos = gl(out.reshape(-1, 3))
    slots = {kk: i for i, kk in enumerate(C.PAINT)}
    uv = np.repeat(np.array([(((slots[p] % C.GRID) + 0.5) / C.GRID, ((slots[p] // C.GRID) + 0.5) / C.GRID) for p in paint]), 3, axis=0)
    tris = np.arange(len(pos)).reshape(-1, 3)
    dest = ROOT / "game/assets/mechs" if a.install else ROOT / f"original/hd/{a.mech}/stl"
    dest.mkdir(parents=True, exist_ok=True)
    write(og, ob, pos, R.vertex_normals(pos, tris), uv, np.repeat(owner, 3), tris, slots, dest, a.mech)
    if a.install:
        work = ROOT / f"original/hd/{a.mech}"; work.mkdir(parents=True, exist_ok=True)
        (work / "provenance.json").write_text(json.dumps({"asset": a.mech, "kind": "adapted", "source": a.source, "licence": a.licence,
            "tool": "tools/art/stl_rig.py", "joints": a.joints, "tris": int(len(tris)), "built_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, indent=2) + "\n")
    print(f"  thigh {thigh:.0f} shin {shin:.0f} mm, root -{drop:.0f} mm; {moved} island tris rejoined; {len(tris)} tris -> {dest}")


def write(og, ob, pos, normals, uv, owner, tris, slots, dest, mech):
    from PIL import Image
    palette = Image.new("RGB", (C.CELL * C.GRID, C.CELL * C.GRID), (128, 128, 128))
    for kk, i in slots.items():
        palette.paste(Image.new("RGB", (C.CELL, C.CELL), C.PAINT[kk]), ((i % C.GRID) * C.CELL, (i // C.GRID) * C.CELL))
    joints = sorted(set(owner.tolist()))
    slot = {n: i for i, n in enumerate(joints)}
    worlds = R.world_matrices(og)
    w = R.GlbWriter(og, ob)
    for node in og["nodes"]:
        node.pop("mesh", None)
    attrs = {"POSITION": w.accessor(pos, "VEC3", target=34962, minmax=True), "NORMAL": w.accessor(normals, "VEC3", target=34962),
             "TEXCOORD_0": w.accessor(uv, "VEC2", target=34962),
             "JOINTS_0": w.accessor(np.c_[[slot[o] for o in owner], np.zeros((len(owner), 3))], "VEC4", comp=5123, target=34962),
             "WEIGHTS_0": w.accessor(np.c_[np.ones(len(owner)), np.zeros((len(owner), 3))], "VEC4", target=34962)}
    ind = w.accessor(tris.reshape(-1).astype(np.uint32), "SCALAR", comp=5125, target=34963)
    tex = w.image(R.png_bytes(palette))
    og.setdefault("samplers", []).append({"magFilter": 9728, "minFilter": 9728})
    og.setdefault("textures", [])[-1]["sampler"] = len(og["samplers"]) - 1
    og.setdefault("materials", []).append({"name": "hd_stl", "pbrMetallicRoughness": {"baseColorTexture": {"index": tex}, "metallicFactor": 0.35, "roughnessFactor": 0.55}})
    og["meshes"].append({"name": "hd_body", "primitives": [{"attributes": attrs, "indices": ind, "material": len(og["materials"]) - 1}]})
    ibm = np.stack([np.linalg.inv(worlds[j]).T.reshape(-1) for j in joints])
    og.setdefault("skins", []).append({"joints": joints, "inverseBindMatrices": w.accessor(ibm, "MAT4")})
    og["nodes"].append({"name": "hd_body", "mesh": len(og["meshes"]) - 1, "skin": len(og["skins"]) - 1})
    og["scenes"][0]["nodes"].append(len(og["nodes"]) - 1)
    w.write(str(dest / f"{mech}_hd.glb"))
    (dest / f"{mech}_hd_paint.bin").write_bytes(R.png_bytes(palette))


if __name__ == "__main__":
    main()
