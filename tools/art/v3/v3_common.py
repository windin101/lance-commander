"""Shared helpers for the v3 HD pipeline (tools/art/v3): sculpt loading in the game frame, Blender calls, grids."""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))
BLENDER = os.environ.get("BLENDER", "/usr/bin/blender")


def load_stl(path):
    """Binary STL -> (V, F) welded on position."""
    import stl_rig as S
    T = S.load_stl(str(path))
    V, inv = np.unique(np.round(T.reshape(-1, 3), 4), axis=0, return_inverse=True)
    return V, inv.reshape(-1, 3).astype(np.int64)


def sculpt_in_game(path, height_mm=None, k=None, turn=False, yaw=0.0):
    """The sculpt in game millimetres, Z up, forward -Y, feet on z=0, centred on its bounding box in x and y.
    Scale by k (game mm per sculpt mm), or to height_mm."""
    V, F = load_stl(path)
    lo, hi = V.min(0), V.max(0)
    if k is None:
        k = height_mm / (hi[2] - lo[2])
    P = (V - [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]]) * k
    if turn:
        P[:, :2] *= -1
    if yaw:
        a = np.radians(yaw); c, s_ = np.cos(a), np.sin(a)
        P[:, :2] = P[:, :2] @ np.array([[c, s_], [-s_, c]])
        P[:, 0] -= (P[:, 0].min() + P[:, 0].max()) / 2; P[:, 1] -= (P[:, 1].min() + P[:, 1].max()) / 2
    return P, F, k


def blender(*args, log=None, timeout=7200):
    cmd = [BLENDER, "-b", "--factory-startup", "--python", str(HERE / "v3_blender.py"), "--", *map(str, args)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if log:
        Path(log).write_text(r.stdout + r.stderr)
    if r.returncode != 0:
        sys.stderr.write(r.stdout[-3000:] + r.stderr[-3000:])
        raise SystemExit(f"blender {args[0]} failed")
    return r.stdout


def grid_overlay(png, meta, view, step=500, label_every=1000, out=None):
    """Draw a world-millimetre grid on an orthographic view (v3_blender.py views meta)."""
    from PIL import Image, ImageDraw
    im = Image.open(png).convert("RGB")
    m = meta[view]
    s = m["size"]; ppm = s / m["span_mm"]
    r = np.array(m["right"]); u = np.array(m["up"]); c = np.array(m["centre_mm"])
    dr = ImageDraw.Draw(im)
    # horizontal axis = world along r, vertical = along u
    def axis_name(v):
        i = int(np.argmax(np.abs(v)))
        return "xyz"[i], np.sign(v[i])
    an, asg = axis_name(r); bn, bsg = axis_name(u)
    cr = c @ r; cu = c @ u
    half = m["span_mm"] / 2
    for val in np.arange(np.floor((cr - half) / step) * step, cr + half + step, step):
        x = (val - cr) * ppm + s / 2
        major = abs(val) % label_every < 1e-6
        dr.line([(x, 0), (x, s)], fill=(255, 120, 120) if major else (255, 200, 200), width=1)
        if major:
            dr.text((x + 2, s - 14), f"{an}{val * asg:+.0f}", fill=(200, 0, 0))
    for val in np.arange(np.floor((cu - half) / step) * step, cu + half + step, step):
        y = s / 2 - (val - cu) * ppm
        major = abs(val) % label_every < 1e-6
        dr.line([(0, y), (s, y)], fill=(120, 120, 255) if major else (200, 200, 255), width=1)
        if major:
            dr.text((2, y + 2), f"{bn}{val * bsg:+.0f}", fill=(0, 0, 200))
    im.save(out or png)
    return im


def world_to_px(meta, view, p):
    m = meta[view]; s = m["size"]; ppm = s / m["span_mm"]
    r = np.array(m["right"]); u = np.array(m["up"]); c = np.array(m["centre_mm"])
    p = np.atleast_2d(p)
    return np.c_[(p @ r - c @ r) * ppm + s / 2, s / 2 - (p @ u - c @ u) * ppm]


def line_hits(P, F, axis, a, b):
    """Coordinates along `axis` (0, 1, 2) where the line through (a, b) in the other two axes crosses the mesh."""
    o = [i for i in range(3) if i != axis]
    T = P[F]
    A = T[:, :, o[0]] - a; B = T[:, :, o[1]] - b
    # 2D barycentric containment of the origin
    x0, y0 = A[:, 0], B[:, 0]; x1, y1 = A[:, 1], B[:, 1]; x2, y2 = A[:, 2], B[:, 2]
    d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    ok = np.abs(d) > 1e-12
    d = np.where(ok, d, 1)
    l0 = ((y1 - y2) * (-x2) + (x2 - x1) * (-y2)) / d
    l1 = ((y2 - y0) * (-x2) + (x0 - x2) * (-y2)) / d
    l2 = 1 - l0 - l1
    m = ok & (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
    t = l0[m] * T[m, 0, axis] + l1[m] * T[m, 1, axis] + l2[m] * T[m, 2, axis]
    return np.sort(t)


def slice_segments(P, F, axis, c, lab=None):
    """Segments where the plane coord[axis] = c cuts the mesh: (n, 2, 3) points, and the face label per segment."""
    T = P[F]
    s = T[:, :, axis] - c
    m = (s.min(1) < 0) & (s.max(1) > 0)
    idx = np.nonzero(m)[0]
    segs = []
    for i in idx:
        t, d = T[i], s[i]
        pts = []
        for a, b in ((0, 1), (1, 2), (2, 0)):
            if (d[a] < 0) != (d[b] < 0):
                u = d[a] / (d[a] - d[b])
                pts.append(t[a] + u * (t[b] - t[a]))
        if len(pts) == 2:
            segs.append(pts)
    segs = np.array(segs).reshape(-1, 2, 3)
    return segs, (lab[idx] if lab is not None else None)


def draw_slices(P, F, axis, values, out, lab=None, pal=None, lo=None, hi=None, ppm=0.12, marks=()):
    """One image per slice value, side by side: the cross-section outline (coloured by label), mm grid every 500."""
    from PIL import Image, ImageDraw
    o = [i for i in range(3) if i != axis]
    lo = np.array(lo if lo is not None else P[:, o].min(0)); hi = np.array(hi if hi is not None else P[:, o].max(0))
    w, h = ((hi - lo) * ppm).astype(int) + 20
    tiles = []
    for c in values:
        im = Image.new("RGB", (w, h), (30, 30, 34)); dr = ImageDraw.Draw(im)
        def px(p):
            return (10 + (p[0] - lo[0]) * ppm, h - 10 - (p[1] - lo[1]) * ppm)
        for g in np.arange(np.ceil(lo[0] / 500) * 500, hi[0], 500):
            dr.line([px((g, lo[1])), px((g, hi[1]))], fill=(70, 70, 90) if g % 1000 else (110, 80, 80))
        for g in np.arange(np.ceil(lo[1] / 500) * 500, hi[1], 500):
            dr.line([px((lo[0], g)), px((hi[0], g))], fill=(70, 70, 90) if g % 1000 else (80, 80, 120))
        segs, sl = slice_segments(P, F, axis, c, lab)
        for k, sg in enumerate(segs):
            col = (230, 230, 230) if sl is None or pal is None else tuple(int(v * 255) for v in pal.get(int(sl[k]), (1, 1, 1)))
            dr.line([px(sg[0][o]), px(sg[1][o])], fill=col, width=2)
        for m in marks:
            if abs(m[axis] - c) < 400:
                q = px(np.asarray(m)[o]); dr.ellipse([q[0] - 5, q[1] - 5, q[0] + 5, q[1] + 5], outline=(255, 60, 60), width=2)
        dr.text((5, 5), f"{'xyz'[axis]}={c:.0f}  axes {'xyz'[o[0]]}->,{'xyz'[o[1]]}^ grid 500", fill=(255, 255, 0))
        tiles.append(im)
    W_ = sum(t.width for t in tiles); sheet = Image.new("RGB", (W_, h)); x = 0
    for t in tiles:
        sheet.paste(t, (x, 0)); x += t.width
    sheet.save(out)
    return sheet


def winding(P, F, X, chunk=24):
    """Generalised winding number of points X (n, 3) against the closed mesh (P, F): ~1 inside, ~0 outside."""
    T = P[F]
    out = np.zeros(len(X))
    for s in range(0, len(X), chunk):
        x = X[s:s + chunk][:, None, None, :]
        a = T[None] - x                       # (c, nf, 3, 3)
        la = np.linalg.norm(a, axis=-1)
        A, B, Cc = a[..., 0, :], a[..., 1, :], a[..., 2, :]
        det = np.einsum("...i,...i", A, np.cross(B, Cc))
        den = la[..., 0] * la[..., 1] * la[..., 2] + np.einsum("...i,...i", A, B) * la[..., 2] + \
            np.einsum("...i,...i", B, Cc) * la[..., 0] + np.einsum("...i,...i", Cc, A) * la[..., 1]
        out[s:s + chunk] = (2 * np.arctan2(det, den)).sum(1) / (4 * np.pi)
    return out


def split_long_edges(P, F, max_len, rounds=12, parent=None):
    """Conforming refinement: every edge longer than max_len is split at its midpoint (one shared vertex per edge),
    faces re-triangulated by how many of their edges split (1 -> 2, 2 -> 3, 3 -> 4). Flat geometry is unchanged;
    long fan slivers of a printed STL become small triangles that segmentation boundaries can follow."""
    P = np.asarray(P, float); F = np.asarray(F, np.int64)
    par = np.arange(len(F)) if parent is None else np.asarray(parent)
    for _ in range(rounds):
        e = np.sort(np.c_[F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]].reshape(-1, 2), 1)
        L = np.linalg.norm(P[e[:, 0]] - P[e[:, 1]], axis=1)
        if L.max() <= max_len:
            break
        key = e[:, 0] * (len(P) + 1) + e[:, 1]
        long_ = L > max_len
        uk, inv = np.unique(key[long_], return_inverse=True)
        # midpoint per unique long edge
        ea = uk // (len(P) + 1); eb = uk % (len(P) + 1)
        mid_idx = len(P) + np.arange(len(uk))
        P = np.r_[P, (P[ea] + P[eb]) / 2]
        m = -np.ones(len(key), np.int64)
        m[np.flatnonzero(long_)] = mid_idx[inv]
        m = m.reshape(-1, 3)              # per face: midpoint on edge (0,1), (1,2), (2,0) or -1
        Lf = L.reshape(-1, 3)
        out = []; po = []
        cnt = (m >= 0).sum(1)
        out.append(F[cnt == 0]); po.append(par[cnt == 0])
        for k in range(3):                # one split edge k: (v_k, v_k+1)
            sel = (cnt == 1) & (m[:, k] >= 0)
            a, b, c = F[sel, k], F[sel, (k + 1) % 3], F[sel, (k + 2) % 3]
            mm = m[sel, k]
            out += [np.c_[a, mm, c], np.c_[mm, b, c]]; po += [par[sel], par[sel]]
        sel = cnt == 3
        a, b, c = F[sel, 0], F[sel, 1], F[sel, 2]
        mab, mbc, mca = m[sel, 0], m[sel, 1], m[sel, 2]
        out += [np.c_[a, mab, mca], np.c_[mab, b, mbc], np.c_[mca, mbc, c], np.c_[mab, mbc, mca]]; po += [par[sel]] * 4
        for k in range(3):                # two split edges: the unsplit edge is k
            sel = (cnt == 2) & (m[:, k] < 0)
            a, b, c = F[sel, k], F[sel, (k + 1) % 3], F[sel, (k + 2) % 3]   # unsplit a-b
            mbc, mca = m[sel, (k + 1) % 3], m[sel, (k + 2) % 3]
            out += [np.c_[mbc, c, mca]]; po += [par[sel]]
            # quad a, b, mbc, mca: split along the shorter diagonal
            d1 = np.linalg.norm(P[a] - P[mbc], axis=1); d2 = np.linalg.norm(P[b] - P[mca], axis=1)
            s1 = d1 <= d2
            out += [np.c_[a, b, mbc][s1], np.c_[a, mbc, mca][s1], np.c_[a, b, mca][~s1], np.c_[b, mbc, mca][~s1]]
            ps = par[sel]; po += [ps[s1], ps[s1], ps[~s1], ps[~s1]]
        F = np.concatenate([o for o in out if len(o)]); par = np.concatenate([q for q, o in zip(po, out) if len(o)])
    if parent is not None:
        return P, F, par
    return P, F
