#!/usr/bin/env python3
"""Rig a (posed) third-party mech sculpt onto an MC2 mech's skeleton.

    python3 -I tools/art/stl_rig.py <mech> <model.stl> [--joints J.json] [--diag D.png] [--install]
        [--source "Title by Author, URL"] [--licence "CC BY-NC-SA 4.0"] [--dump seams.npz]

General version of tools/art/stl_rig_vulture.py (which keeps the Vulture's hand-read joints).
  1. Load the STL (mm, Z up, forward -Y; "turn": true in J.json turns it 180 degrees), cut off a display
     base if one spans the gap between the feet, scale to the original model's height, centre it.
  2. Find each leg's hip, knee and ankle: the hip just above the crotch (the lowest height where the gap
     between the legs closes), the ankle above the foot, the knee at the point of the leg's traced centre
     line farthest from the hip-ankle line. J.json overrides any of them ([y, z] in game mm; x comes from the
     mesh, or [x, y, z] pins x too, e.g. where an arm hangs beside the hip). --diag draws them on side views; check it before trusting a build. A skeleton with a middle leg
     joint (joint_<s>mleg: Catapult, Cyclops, Ryoken, Werewolf) has a fourth point, "heel" (MC2's joint_<s>lleg,
     between the knee and the ankle): by default on the knee-ankle line at the original's length ratio. "x_max" per leg (|x|, game mm,
     applied above "x_max_z", default the knee) keeps a low-hanging arm out of that leg (Highlander's left arm); "parts"
     boxes give upper-body triangles to a named part where the nearest-part mapping splits a posed arm.
     "z_top" per leg (game mm) replaces the leg's top (default hip + 3 % of the height) and "x_min" (applied above
     "x_min_z", default the knee; "x_min_low" below it) its inner |x|, for thigh armour that rises above a low hip bearing (Shadow Cat).
  3. Skeleton: MC2's leg bone directions with the sculpt's lengths. joint_root's rest height and every
     animation's root keys drop with the hip. Upper-body joints move with the sculpt's upper-body bounds.
  4. Legs: per triangle, nearest bone; thigh and shin turned about their upper joint onto the new bone, the
     foot moved to the new ankle. Upper body: nearest original part, after the original's upper body is
     mapped onto the sculpt's bounds. Seams majority-smoothed, islands < 40 tris rejoined, joint caps added.
     Seam rules (defaults since 2026-10-19; check them with tools/art/owner_map.py, rest and --anim Walk):
     - long triangles are split to <= 2 % of the height first ("split_long" mm), so fan slivers stay local;
     - leg triangles are cut exactly at each joint plane, and near a joint the plane picks the part;
     - leg parts never take upper-body triangles ("upper_skip_legs": false restores the old rule);
     - pelvis cap: the pelvis owns nothing above the hips + 4 % of the height ("pelvis_top" z mm), because the
       torso twists against it in the walk;
     - arm chains: joint_<s>uarm -> joint_<s>gun ("arms": {"l": [...]} to change, {} for none; "arm_tips"
       {"l": [x, y, z]} for the far end, default the gun part's farthest mapped point). Within "arm_reach"
       (default 12 % of the height) of the chain, the joint planes pick the part; arm parts keep nothing
       farther than twice that (strays go to the body). "upper_joints" moves a misplaced pivot.
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
    n = struct.unpack_from("<I", data, 80)[0] if len(data) >= 84 else -1
    if 84 + 50 * n != len(data):
        if data.lstrip()[:5].lower() == b"solid":  # ASCII STL (some uploads): the "vertex x y z" lines, three per facet
            import re
            v = np.array(re.findall(rb"vertex\s+(\S+)\s+(\S+)\s+(\S+)", data), dtype=float)
            if len(v) and len(v) % 3 == 0:
                return v.reshape(-1, 3, 3)
        raise SystemExit(f"{path}: not a plain binary or ASCII STL")
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


def box_tris(lo, hi):
    """Closed axis-aligned box, (12, 3, 3) triangles wound outward."""
    c = [np.array([hi[0] if i & 1 else lo[0], hi[1] if i & 2 else lo[1], hi[2] if i & 4 else lo[2]]) for i in range(8)]
    quads = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    return np.array([[c[a], c[b], c[d]] for a, b, cc, d in quads for (b, d) in ((b, cc), (cc, d))])


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


def split_by_plane(T, p, n, mask):
    """Split every masked triangle that crosses the plane (point p, normal n) into pieces on either side, keeping
    winding. A cut through a sculpt's long triangles is then exact, so no triangle straddles two parts (slivers)."""
    d = (T - p) @ n                                     # (t, 3) signed distances
    cross = mask & (d.max(1) > 1e-6) & (d.min(1) < -1e-6)
    if not cross.any():
        return T
    X, D = T[cross], d[cross]
    pos = D > 0
    lone = np.where(pos.sum(1) == 1, pos.argmax(1), (~pos).argmax(1))   # the vertex alone on its side
    r = np.arange(len(X))
    a, b, c = X[r, lone], X[r, (lone + 1) % 3], X[r, (lone + 2) % 3]
    da, db, dc = D[r, lone], D[r, (lone + 1) % 3], D[r, (lone + 2) % 3]
    ab = a + (b - a) * (da / (da - db))[:, None]
    ac = a + (c - a) * (da / (da - dc))[:, None]
    new = np.concatenate([np.stack([a, ab, ac], 1), np.stack([ab, b, c], 1), np.stack([ab, c, ac], 1)])
    return np.concatenate([T[~cross], new])


def chain_planes(P):
    """Cut planes for a joint chain P[0..k]: at P[0] along the first bone, at interior joints on the bisector of the
    two bones, at P[k] along the last bone (what lies past it is the end part, e.g. the foot)."""
    u = [(P[i + 1] - P[i]) / np.linalg.norm(P[i + 1] - P[i]) for i in range(len(P) - 1)]
    out = [u[0]]
    for i in range(1, len(P) - 1):
        b = u[i - 1] + u[i]
        out.append(b / np.linalg.norm(b) if np.linalg.norm(b) > 1e-6 else u[i])
    out.append(u[-1])
    return out


def split_long(T, L):
    """Halve every triangle along its longest edge until no edge is longer than L (same units as T)."""
    out = []
    while len(T):
        e = np.stack([np.linalg.norm(T[:, 1] - T[:, 0], axis=1), np.linalg.norm(T[:, 2] - T[:, 1], axis=1),
                      np.linalg.norm(T[:, 0] - T[:, 2], axis=1)], 1)
        long_ = e.max(1) > L
        out.append(T[~long_]); T = T[long_]; k = e[long_].argmax(1)
        a = T[np.arange(len(T)), k]; b = T[np.arange(len(T)), (k + 1) % 3]; c = T[np.arange(len(T)), (k + 2) % 3]
        m = (a + b) / 2
        T = np.concatenate([np.stack([a, m, c], 1), np.stack([m, b, c], 1)]) if len(T) else T
    return np.concatenate(out)


def merge_mleg_anims(og, ob, names, s):
    """J.json "merge_mleg": freeze joint_<s>mleg at its rest rotation in every animation and fold its motion into
    uleg and lleg, so uleg -> lleg is one rigid thigh. uleg turns (least rotation from its own key) so the
    hip-to-lleg chord points where the original's did; lleg keeps the original's world orientation, so the shin
    and foot move exactly as before. Keys are rewritten in place (same times)."""
    from scipy.spatial.transform import Rotation as Rot, Slerp
    u, m, l = (names[f"joint_{s}{p}"] for p in ("uleg", "mleg", "lleg"))
    nd = og["nodes"]
    rest = lambda j: np.array(nd[j].get("rotation", [0.0, 0.0, 0.0, 1.0]), float)
    tm, tl = np.array(nd[m]["translation"], float), np.array(nd[l]["translation"], float)
    c_new = tm + Rot.from_quat(rest(m)).apply(tl)   # rest chord in uleg's frame (uniform scaling keeps directions)
    for an in og["animations"]:
        ch = {}
        for c in an["channels"]:
            if c["target"]["path"] == "rotation" and c["target"]["node"] in (u, m, l):
                smp = an["samplers"][c["sampler"]]
                ch[c["target"]["node"]] = (R.read_accessor(og, ob, smp["input"]).astype(float).ravel(), smp["output"])
        if m not in ch:
            continue
        if u not in ch or l not in ch:
            print(f"  merge_mleg: {an.get('name')} {s}: no uleg/lleg track, mleg left as is"); continue
        def track(j):
            t, o = ch[j]
            q = R.read_accessor(og, ob, o).astype(float).copy()
            for i in range(1, len(q)):
                if q[i] @ q[i - 1] < 0:
                    q[i] = -q[i]
            if len(t) == 1:
                return lambda x: Rot.from_quat(np.repeat(q, len(x), 0))
            sl = Slerp(t, Rot.from_quat(q))
            return lambda x: sl(np.clip(x, t[0], t[-1]))
        fu, fm, fl = track(u), track(m), track(l)
        qm0 = Rot.from_quat(rest(m))
        def solve(x):
            qu, qm, ql = fu(x), fm(x), fl(x)
            d = qu.apply(tm + qm.apply(tl)); cur = qu.apply(np.tile(c_new, (len(x), 1)))
            ax = np.cross(cur, d); sn = np.linalg.norm(ax, axis=1); cs = (cur * d).sum(1)
            rv = ax / np.maximum(sn, 1e-12)[:, None] * np.arctan2(sn, cs)[:, None]
            qu2 = Rot.from_rotvec(rv) * qu
            return qu2, (qu2 * qm0).inv() * qu * qm * ql
        new = {u: solve(ch[u][0])[0].as_quat(), l: solve(ch[l][0])[1].as_quat(), m: np.tile(rest(m), (len(ch[m][0]), 1))}
        for j, vals in new.items():
            acc = og["accessors"][ch[j][1]]; view = og["bufferViews"][acc["bufferView"]]
            assert acc["componentType"] == 5126 and acc["count"] == len(vals)
            vals = vals.astype(np.float32); off = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
            ob[off:off + vals.nbytes] = vals.tobytes()


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
        for kk, col in (("hip", (220, 0, 0)), ("knee", (0, 150, 0)), ("heel", (170, 0, 170)), ("ankle", (0, 0, 220))):
            if kk not in J[s]:
                continue
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
    ap.add_argument("--dump", help="write the sculpt-frame triangles, owners and arm chains to this .npz (debugging seams)")
    ap.add_argument("--source", default=""); ap.add_argument("--licence", default="CC BY-NC-SA 4.0")
    ap.add_argument("--folder", default="mechs", help="game/assets/<folder>: mechs, or vehicles for walking infantry units (powered armour)")
    a = ap.parse_args()
    over = json.loads(Path(a.joints).read_text()) if a.joints and Path(a.joints).exists() else {}
    # J.json "scale" (since 2026-10-20): multiplies the fit-to-height scale, for a sculpt whose highest point is not
    # the mech's top (an open launcher lid). Every game-mm value in J.json is read as measured at scale 1 and scaled
    # with it, so joints read off an earlier build's diag sheets stay valid. Angles, raw-unit and boolean keys are kept.
    SC = float(over.get("scale", 1.0))
    if SC != 1.0:
        KEEP = {"turn", "base_cut", "yaw", "deg", "scale", "arms", "upper_skip_legs", "merge_mleg", "faces", "x_sign"}
        def scl(o, key=None):
            if key in KEEP:
                return o
            if isinstance(o, dict):
                return {k_: scl(v_, k_) for k_, v_ in o.items()}
            if isinstance(o, list):
                return [scl(v_, key) for v_ in o]
            if isinstance(o, (int, float)) and not isinstance(o, bool):
                return o * SC
            return o
        over = scl(over)

    glb = ROOT / f"game/assets/{a.folder}/{a.mech}.glb"
    og, ob = R.load_glb(str(glb))
    # skeleton name variants (since 2026-10-20, Anubis): a four-joint leg named uleg -> lleg -> lleg2 -> ankle is read as
    # uleg -> mleg -> lleg -> ankle, and the misspelt joint_lanke as joint_lankle; the original names are put back before writing
    renamed = {}
    nm0 = {n.get("name") for n in og["nodes"]}
    for i, n in enumerate(og["nodes"]):
        nm = n.get("name", "")
        for s_ in "lr":
            if f"joint_{s_}lleg2" in nm0 and nm == f"joint_{s_}lleg":
                renamed[i] = (nm, f"joint_{s_}mleg")
            elif nm == f"joint_{s_}lleg2":
                renamed[i] = (nm, f"joint_{s_}lleg")
        if nm == "joint_lanke" and "joint_lankle" not in nm0:
            renamed[i] = (nm, "joint_lankle")
    for i, (old, new) in renamed.items():
        og["nodes"][i]["name"] = new
    if renamed:
        print("  skeleton names read as:", {o: n for o, n in renamed.values()})
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
    k = H_o / T[..., 2].max() * SC
    T = T * k
    flat = T.reshape(-1, 3)
    T[..., :2] -= (flat[:, :2].min(0) + flat[:, :2].max(0)) / 2
    T[..., 0] += over.get("x_shift", 0.0)  # J.json: game mm, centres legs that the bbox (an outstretched arm) puts off-centre
    if over.get("yaw") or over.get("twist"):  # J.json, for a sculpt posed mid-turn (Ryoken), game mm / degrees about +Z:
        # "yaw" turns the whole model about "pivot" [x, y] (the hip midpoint) to square the pelvis to +X; "twist"
        # {"deg", "z", "add": [[x0,x1,y0,y1,z0,z1]...], "keep": [...]} then turns the upper body (centroid above z,
        # plus the add boxes, minus the keep boxes; boxes in the yawed frame with the pivot at the origin) to square the torso.
        pv = np.array(over.get("pivot", [0.0, 0.0]), float)
        def rz(P, deg):
            c_, s_ = np.cos(np.radians(deg)), np.sin(np.radians(deg)); Q = P.copy()
            x_, y_ = P[..., 0] - pv[0], P[..., 1] - pv[1]
            Q[..., 0], Q[..., 1] = pv[0] + x_ * c_ - y_ * s_, pv[1] + x_ * s_ + y_ * c_
            return Q
        T = rz(T, float(over.get("yaw", 0.0)))
        T[..., :2] -= pv; pv = np.zeros(2)  # twist boxes are in this pivot-centred frame
        tw = over.get("twist")
        if tw:
            Cz = T.mean(1); sel = Cz[:, 2] > tw["z"]
            inbox = lambda b: (Cz[:, 0] > b[0]) & (Cz[:, 0] < b[1]) & (Cz[:, 1] > b[2]) & (Cz[:, 1] < b[3]) & (Cz[:, 2] > b[4]) & (Cz[:, 2] < b[5])
            for b in tw.get("add", []):
                sel |= inbox(b)
            for b in tw.get("keep", []):
                sel &= ~inbox(b)
            T[sel] = rz(T[sel], float(tw["deg"]))
    over.setdefault("split_long", 0.02 * T[..., 2].max())  # default since 2026-10-19: STL exports carry long fan slivers (1.5k in the
    # Bushwacker) that span two parts; whole, they swing out as spikes when a part is re-posed. "split_long": 0 turns it off.
    if over.get("split_long"):  # J.json: split triangles longer than this (game mm) so that a long sliver spanning
        T = split_long(T, float(over["split_long"]))  # two parts (a flat panel across a shoulder) cannot trail a strand
    H, W = T[..., 2].max(), np.ptp(T[..., 0])
    Cn = T.mean(1); nt = len(T)
    print(f"{a.mech}: {nt} tris, x{k:.1f}, {W/1000:.2f} x {np.ptp(T[..., 1])/1000:.2f} x {H/1000:.2f} m" + (f", base cut at {cut:.2f}" if cut else ""))

    if a.views:
        views_sheet(T, a.views, H, a.mech)
    # 2. joints
    J = detect(T, H, W)
    V = T.reshape(-1, 3)
    # J.json "merge_mleg": true keeps a four-joint skeleton on three points (hip, knee = joint_<s>lleg, ankle), for a
    # sculpt with one rigid thigh (Ryoken): uleg -> mleg -> lleg is scaled as one piece and mleg is frozen in every
    # animation, its motion folded into uleg and lleg (merge_mleg_anims), so nothing bends mid-thigh or mid-shin.
    merge = "joint_lmleg" in names and bool(over.get("merge_mleg"))
    mid = "joint_lmleg" in names and not merge     # four-joint leg: uleg (hip) -> mleg (knee) -> lleg (heel) -> ankle
    KEYS = ("hip", "knee", "heel", "ankle") if mid else ("hip", "knee", "ankle")
    if mid:
        w0 = lambda n: sc(W0[names[n]][:3, 3])
        a_ = np.linalg.norm(w0("joint_llleg") - w0("joint_lmleg"))
        b_ = np.linalg.norm(w0("joint_lankle") - w0("joint_llleg"))
        frac = a_ / (a_ + b_)
    for s, sign in (("l", 1), ("r", -1)):
        if mid:
            J[s] = {"hip": J[s]["hip"], "knee": J[s]["knee"], "ankle": J[s]["ankle"]}
            for kk in ("hip", "knee", "ankle"):   # overrides first, so the default heel follows them
                if kk in over.get(s, {}):
                    *x_, y, z = over[s][kk]   # [y, z], or [x, y, z] to pin x too
                    near = (V[:, 0] * sign > 0.06 * W) & (np.hypot(V[:, 1] - y, V[:, 2] - z) < 450)
                    J[s][kk] = np.array([x_[0] if x_ else V[near, 0].mean() if near.any() else J[s][kk][0], y, z])
            J[s]["heel"] = J[s]["knee"] + frac * (J[s]["ankle"] - J[s]["knee"])
            J[s] = {kk: J[s][kk] for kk in KEYS}
        for kk in KEYS:
            if kk in over.get(s, {}):
                *x_, y, z = over[s][kk]   # [y, z], or [x, y, z] to pin x too
                near = (V[:, 0] * sign > 0.06 * W) & (np.hypot(V[:, 1] - y, V[:, 2] - z) < 450)
                J[s][kk] = np.array([x_[0] if x_ else V[near, 0].mean() if near.any() else J[s][kk][0], y, z])
    if a.diag:
        diag_sheet(T, J, a.diag, H, a.mech)
    for s in "lr":
        print(f"  {s}: " + "  ".join(f"{kk} [{J[s][kk][1]:.0f}, {J[s][kk][2]:.0f}]" for kk in KEYS))

    # 3. skeleton
    legs = {s: ((f"joint_{s}uleg", f"joint_{s}mleg", f"joint_{s}lleg", f"joint_{s}ankle") if mid else
                (f"joint_{s}uleg", f"joint_{s}lleg", f"joint_{s}ankle")) for s in "lr"}
    seg = [np.mean([np.linalg.norm(J[s][KEYS[i]] - J[s][KEYS[i - 1]]) for s in "lr"]) for i in range(1, len(KEYS))]
    thigh, shin = seg[0], sum(seg[1:])
    ankle_h = np.mean([J[s]["ankle"][2] for s in "lr"])
    for s in "lr":
        for jn, ln in zip(legs[s][1:], seg):
            if merge and jn == f"joint_{s}lleg":  # the whole uleg -> lleg chord gets the thigh length
                from scipy.spatial.transform import Rotation as Rot
                mn, lnn = og["nodes"][names[f"joint_{s}mleg"]], og["nodes"][names[jn]]
                tm, tl = np.array(mn["translation"]), np.array(lnn["translation"])
                f_ = ln / 1000 / np.linalg.norm(tm + Rot.from_quat(mn.get("rotation", [0, 0, 0, 1])).apply(tl))
                mn["translation"], lnn["translation"] = (tm * f_).tolist(), (tl * f_).tolist()
                continue
            t = np.array(og["nodes"][names[jn]]["translation"])
            og["nodes"][names[jn]]["translation"] = (t / np.linalg.norm(t) * ln / 1000).tolist()
    drop = np.mean([sc(R.world_matrices(og)[names[legs[s][-1]]][:3, 3])[2] for s in "lr"]) - ankle_h
    og["nodes"][names["joint_root"]]["translation"][1] -= drop / 1000
    for an in og["animations"]:
        for ch in an["channels"]:
            if ch["target"]["path"] == "translation" and og["nodes"][ch["target"]["node"]]["name"] == "joint_root":
                si = an["samplers"][ch["sampler"]]["output"]
                acc = og["accessors"][si]; view = og["bufferViews"][acc["bufferView"]]
                vals = R.read_accessor(og, ob, si).astype(np.float32).copy(); vals[:, 1] -= drop / 1000
                off = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
                ob[off:off + vals.nbytes] = vals.tobytes()
    if merge:
        for s in "lr":
            merge_mleg_anims(og, ob, names, s)
    W2 = R.world_matrices(og)
    tgt = {s: {kk: sc(W2[names[legs[s][i]]][:3, 3]) for i, kk in enumerate(KEYS)} for s in "lr"}
    shift = np.mean([tgt[s]["hip"] - J[s]["hip"] for s in "lr"], axis=0)

    # upper body: map the original's upper body (rest) onto the sculpt's upper body (game frame)
    hip_old = np.mean([sc(W0[names[legs[s][0]]][:3, 3])[2] for s in "lr"])
    up_parts = {i: p for i, p in parts0.items() if p[:, 2].mean() > hip_old - 0.03 * H_o}
    if over.get("upper_skip_legs", True):  # never give upper-body triangles to a leg part (default since 2026-10-19:
        # a high thigh mesh, the Bushwacker's or Ryoken's, otherwise claims torso and arm pieces, which the thigh's
        # re-pose then throws out as shards around the waist). J.json "upper_skip_legs": false restores the old rule. (a thigh mesh at hip
        # height, Ryoken's horizontal ry_<s>uleg, otherwise claims gun and torso pieces near it)
        leg_nodes = {part_under(og, names, f"joint_{s}{j}") for s in "lr" for j in ("uleg", "mleg", "lleg", "ankle", "foot")}
        up_parts = {i: p for i, p in up_parts.items() if i not in leg_nodes}
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
    for jn, p_ in over.get("upper_joints", {}).items():  # J.json: {"joint_luarm": [x, y, z]} (game mm, before the shift): rest
        # world position of an upper-body joint, where the bounds mapping misplaces it (a gun arm posed far forward
        # stretches the bounds and drags the shoulder off the sculpt's own; Zeus). Its joint children keep their world position.
        i = names[jn]; Wn = R.world_matrices(og)
        par = next(k for k, n in enumerate(og["nodes"]) if i in n.get("children", []))
        old, new = sc(Wn[i][:3, 3]), np.asarray(p_, float) + shift
        og["nodes"][i]["translation"] = gl(new - sc(Wn[par][:3, 3]))[0].tolist()
        for c in og["nodes"][i].get("children", []):
            if og["nodes"][c].get("name", "").startswith("joint_"):
                og["nodes"][c]["translation"] = (np.asarray(og["nodes"][c]["translation"]) + gl(old - new)[0]).tolist()

    # 3b. clean cuts: split the triangles that cross each leg joint's plane (and each arm joint's, with J.json "arms"),
    # so every part boundary is an exact plane rather than a fringe of whole triangles (the sliver shards at hips and knees)
    LEG_R = 0.10 * H
    leg_planes = {s: chain_planes([J[s][kk] for kk in KEYS]) for s in "lr"}
    arm_chain = {}
    Wn = R.world_matrices(og)
    arms_ = over.get("arms")   # J.json "arms": {"l": ["joint_luarm", "joint_lgun"], ...}; default (since 2026-10-19) the
    if arms_ is None:          # upper arm -> gun chain every MC2 mech has; "arms": {} turns arm chains off
        arms_ = {s: [f"joint_{s}uarm", f"joint_{s}gun"] for s in "lr" if f"joint_{s}uarm" in names and f"joint_{s}gun" in names}
    for s, chain in arms_.items():
        pts_ = [sc(Wn[names[jn]][:3, 3]) - shift for jn in chain]   # pivots from upper_joints (or the bounds mapping), sculpt frame
        tip = over.get("arm_tips", {}).get(s)                       # optional [x, y, z]: the far end of the last part
        if tip is None:  # default: the point of the last part's mapped original mesh farthest from its pivot
            lp = part_under(og, names, chain[-1])
            if lp in up_parts:
                q = norm(up_parts[lp]) - shift
                tip = q[np.linalg.norm(q - pts_[-1], axis=1).argmax()]
        if tip is not None:
            pts_.append(np.asarray(tip, float))
        if len(pts_) >= 2:
            arm_chain[s] = (chain, pts_, chain_planes(pts_))
    for s, sign in (("l", 1), ("r", -1)):
        for kk, nrm in zip(KEYS, leg_planes[s]):
            Cq = T.mean(1)
            m = (Cq[:, 0] * sign > -0.02 * W) & (np.linalg.norm(Cq - J[s][kk], axis=1) < 1.3 * LEG_R)
            T = split_by_plane(T, J[s][kk], nrm, m)
        if s in arm_chain:
            _, pts_, pls = arm_chain[s]
            for p_, nrm in zip(pts_[:len(arm_chain[s][0])], pls):
                Cq = T.mean(1)
                T = split_by_plane(T, p_, nrm, (Cq[:, 0] * sign > -0.02 * W) & (np.linalg.norm(Cq - p_, axis=1) < 0.16 * H))
    Cn = T.mean(1); nt = len(T); V = T.reshape(-1, 3)
    print(f"  clean cuts: {nt} tris after splitting at the joint planes")

    # 4. assign triangles
    owner = np.full(nt, -1)
    xform = {}
    for s, sign in (("l", 1), ("r", -1)):
        j = J[s]
        o_ = over.get(s, {})  # J.json "z_top" / "x_min" (game mm): top z of the leg, and its inner |x| above x_min_z
        # (default the knee), for thigh armour that rises above a low hip bearing beside the pelvis (Shadow Cat)
        # "x_min_low" is the inner |x| below x_min_z (negative: across the centre line, for a toed-in foot)
        lo_ = Cn[:, 2] < o_.get("x_min_z", j["knee"][2])
        legm = (Cn[:, 0] * sign > np.where(lo_, o_.get("x_min_low", 0.04 * W), o_.get("x_min", 0.04 * W))) \
            & (Cn[:, 2] < o_.get("z_top", j["hip"][2] + 0.03 * H))
        if "x_max" in over.get(s, {}):  # J.json: |x| limit (game mm) above x_max_z (default the knee), keeping a
            hi = Cn[:, 2] > over[s].get("x_max_z", j["knee"][2])  # low-hanging arm out of the leg
            legm &= ~hi | (Cn[:, 0] * sign < over[s]["x_max"])
        for y0, y1, z0, z1 in over.get(s, {}).get("not_leg", []):  # J.json: [y0, y1, z0, z1] boxes (game mm) kept out of the leg
            legm &= ~((Cn[:, 1] > y0) & (Cn[:, 1] < y1) & (Cn[:, 2] > z0) & (Cn[:, 2] < z1))
        d = np.stack([seg_dist(Cn, j[KEYS[i]], j[KEYS[i + 1]]) for i in range(len(KEYS) - 1)] +
                     [np.where(Cn[:, 2] < j["ankle"][2] + 0.02 * H, 0, 1e9) + seg_dist(Cn, j["ankle"], j["ankle"] * [1, 1, 0])], 1)
        which = d.argmin(1)
        # near a joint its cut plane decides between the two parts it joins (nearest-bone stays the rule elsewhere);
        # at the hip, what lies on the body side of the plane leaves the leg
        for ji, (kk, nrm) in enumerate(zip(KEYS, leg_planes[s])):
            near = legm & (np.linalg.norm(Cn - j[kk], axis=1) < LEG_R)
            past = (Cn - j[kk]) @ nrm > 0
            if ji == 0:
                legm &= ~(near & ~past)
            else:
                pair = near & ((which == ji - 1) | (which == ji))
                which[pair & past] = ji
                which[pair & ~past] = ji - 1
        nodes_ = [part_under(og, names, jn) for jn in legs[s][:-1]] + [part_under(og, names, legs[s][-1], f"joint_{s}foot")]
        for kk, node in enumerate(nodes_):
            if node is None:
                continue
            owner[legm & (which == kk)] = node
            xform[node] = ("rot", j[KEYS[kk]], j[KEYS[kk + 1]], tgt[s][KEYS[kk]], tgt[s][KEYS[kk + 1]]) \
                if kk < len(KEYS) - 1 else ("move", j["ankle"], tgt[s]["ankle"])
    ids = list(up_parts)
    pts = np.concatenate([norm(up_parts[i]) for i in ids])
    lab = np.concatenate([[i] * len(up_parts[i]) for i in ids])
    free = owner < 0
    owner[free] = lab[cKDTree(pts).query(Cn[free] + shift)[1]]
    # pelvis cap (default since 2026-10-19): the pelvis parts (under joint_hip, not legs) own nothing higher than the
    # hip joints plus 4 % of the height. MC2 twists joint_torso against joint_hip in the walk, so a pelvis share of the
    # hull that the bounds mapping draws through a solid block tears open (the Bushwacker's waist). J.json "pelvis_top":
    # absolute z (game mm) to move the cap.
    hip_i = names.get("joint_hip")
    if hip_i is not None:
        sub = lambda i: [i] + [d for c in og["nodes"][i].get("children", []) for d in sub(c)]
        pel = [i for i in ids if i in sub(hip_i)]
        rest_ = [i for i in ids if i not in pel]
        if pel and rest_:
            cap = over.get("pelvis_top", max(J[s]["hip"][2] for s in "lr") + 0.04 * H)
            m = free & np.isin(owner, pel) & (Cn[:, 2] > cap)
            pts2 = np.concatenate([norm(up_parts[i]) for i in rest_])
            lab2 = np.concatenate([[i] * len(up_parts[i]) for i in rest_])
            owner[m] = lab2[cKDTree(pts2).query(Cn[m] + shift)[1]]
            print(f"  pelvis cap z={cap:.0f}: {int(m.sum())} tris moved off the pelvis")
    # J.json "upper": [{"node": name, "z_min"/"z_max"/"ax_min"/"ax_max"(|x|)/"y_min"/"y_max": game mm}, ...]: later
    # rules win; they re-own upper-body triangles where the bounds mapping splits one sculpt block across parts
    for rule in over.get("upper", []):
        m = free.copy()
        for key_, col, op in (("z_min", 2, np.greater_equal), ("z_max", 2, np.less), ("y_min", 1, np.greater_equal),
                              ("y_max", 1, np.less)):
            if key_ in rule:
                m &= op(Cn[:, col], rule[key_])
        if "ax_min" in rule:
            m &= np.abs(Cn[:, 0]) >= rule["ax_min"]
        if "ax_max" in rule:
            m &= np.abs(Cn[:, 0]) < rule["ax_max"]
        if "x_sign" in rule:
            m &= Cn[:, 0] * rule["x_sign"] > 0
        owner[m] = names[rule["node"]]
    for box in over.get("parts", []):  # J.json: {"node", "min": [x,y,z], "max": [x,y,z]} (game mm, before the shift):
        inb = free & (Cn >= box["min"]).all(1) & (Cn <= box["max"]).all(1)  # upper-body tris in the box go to that
        if "from" in box:  # optional: only the tris the mapping gave to this part
            inb &= owner == names[box["from"]]
        owner[inb] = names[box["node"]]  # part (an arm posed far from the original's, e.g. the Highlander's hanging one)
    # arm chains (J.json "arms"): within reach of the chain, the joint planes decide the part, replacing the bounds
    # mapping that splits a posed arm across the original's parts (shoulder and elbow tears)
    for s, sign in (("l", 1), ("r", -1)):
        if s not in arm_chain:
            continue
        chain, pts_, pls = arm_chain[s]
        parts_ = [part_under(og, names, jn) for jn in chain]
        parent = next(k for k, n in enumerate(og["nodes"]) if names[chain[0]] in n.get("children", []))
        body = part_under(og, names, og["nodes"][parent]["name"]) or part_under(og, names, "joint_torso")
        reach = np.min([seg_dist(Cn, pts_[i], pts_[i + 1]) for i in range(len(pts_) - 1)], axis=0)
        # strict: an arm part owns what lies within reach of its chain, or within twice the reach where the bounds
        # mapping already gave it to the arm (a tall gun pod); its scattered pieces farther out on the hull (torso
        # top, hull sides) go to the body, or they tear off when the arm swings
        sub = lambda i: [i] + [d for c in og["nodes"][i].get("children", []) for d in sub(c)]
        arm_nodes = [i for i in sub(names[chain[0]]) if i in ids]
        rch = over.get("arm_reach", 0.12 * H)
        cand = free & (Cn[:, 0] * sign > -0.02 * W) & ((reach < rch) | ((reach < 2 * rch) & np.isin(owner, arm_nodes)))
        stray = free & ~cand & np.isin(owner, arm_nodes)
        if body is not None:
            owner[stray] = body
        seg_i = np.zeros(nt, int)
        for p_, nrm in zip(pts_[:len(chain)], pls):
            seg_i += ((Cn - p_) @ nrm > 0).astype(int)
        for k_ in range(len(chain) + 1):
            m = cand & (seg_i == k_)
            node = body if k_ == 0 else parts_[k_ - 1]
            if node is not None:
                owner[m] = node
        print(f"  arm {s}: {int(cand.sum())} tris on the {' -> '.join(chain)} chain, {int(stray.sum())} strays to the body; "
              f"pivots {[list(np.round(p_).astype(int)) for p_ in pts_]}")

    if a.dump:
        np.savez(a.dump, T=T, owner=owner, names=np.array([n.get("name", "") for n in og["nodes"]]),
                 arms=json.dumps({s_: [c[0], [list(map(float, q)) for q in c[1]]] for s_, c in arm_chain.items()}))
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
        for kk in KEYS:
            paint[np.linalg.norm(Cn - J[s][kk], axis=1) < 0.04 * H] = "metal"
    caps, cap_owner = [], []
    for s in "lr":
        nodes_ = [part_under(og, names, jn) for jn in legs[s][:-1]] + [part_under(og, names, legs[s][-1], f"joint_{s}foot")]
        for jn, child in zip(KEYS, nodes_):
            if child is not None:
                r = float(np.clip(0.045 * H, 230, 470)) * (0.65 if jn == "ankle" else 1.0)
                caps.append(drum(tgt[s][jn], r, float(np.clip(0.08 * W, 380, 760)))); cap_owner += [child] * len(caps[-1])
    for c in over.get("cores", []):  # J.json: {"node", "min", "max"} (game mm, before the shift, like "parts"): a dark
        # closed box inside a hollow shell, so a seam crack shows shadow, not the sky behind it (Ryoken's torso/pod split)
        caps.append(box_tris(np.array(c["min"], float) + shift, np.array(c["max"], float) + shift)); cap_owner += [names[c["node"]]] * 12
    caps = np.concatenate(caps)
    out = np.concatenate([out, caps]); owner = np.concatenate([owner, cap_owner])
    paint = np.concatenate([paint, ["dark"] * len(caps)])

    pos = gl(out.reshape(-1, 3))
    slots = {kk: i for i, kk in enumerate(C.PAINT)}
    uv = np.repeat(np.array([(((slots[p] % C.GRID) + 0.5) / C.GRID, ((slots[p] // C.GRID) + 0.5) / C.GRID) for p in paint]), 3, axis=0)
    tris = np.arange(len(pos)).reshape(-1, 3)
    dest = ROOT / f"game/assets/{a.folder}" if a.install else ROOT / f"original/hd/{a.mech}/stl"
    dest.mkdir(parents=True, exist_ok=True)
    for i, (old, new) in renamed.items():  # the game's skeleton keeps its own names
        og["nodes"][i]["name"] = old
    write(og, ob, pos, R.vertex_normals(pos, tris), uv, np.repeat(owner, 3), tris, slots, dest, a.mech)
    if a.install:
        work = ROOT / f"original/hd/{a.mech}"; work.mkdir(parents=True, exist_ok=True)
        (work / "provenance.json").write_text(json.dumps({"asset": a.mech, "kind": "adapted", "class": a.folder, "source": a.source, "licence": a.licence,
            "tool": "tools/art/stl_rig.py", "joints": a.joints, "tris": int(len(tris)), "built_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, indent=2) + "\n")
    print(f"  thigh {thigh:.0f} shin {shin:.0f} mm" + (f" (knee-heel {seg[1]:.0f}, heel-ankle {seg[2]:.0f})" if mid else "") + f", root -{drop:.0f} mm; {moved} island tris rejoined; {len(tris)} tris -> {dest}")


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
    import glb_compact  # weld + byte joints/weights: about half the size, identical render (since 2026-10-20)
    glb_compact.compact(dest / f"{mech}_hd.glb")
    (dest / f"{mech}_hd_paint.bin").write_bytes(R.png_bytes(palette))


if __name__ == "__main__":
    main()
