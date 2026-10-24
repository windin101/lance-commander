"""v3 pipeline stages after fit (see v3_mech.py)."""
import json
import sys
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

sys.path.insert(0, str(Path(__file__).resolve().parent))
import v3_common as C  # noqa: E402

PAL = [(0.92, 0.25, 0.25), (0.35, 0.75, 0.35), (0.25, 0.35, 0.95), (0.98, 0.85, 0.15), (0.9, 0.3, 0.9), (0.2, 0.85, 0.9),
       (1.0, 0.55, 0.1), (0.55, 0.32, 0.12), (0.0, 0.55, 0.55), (0.98, 0.98, 0.98), (0.45, 0.15, 0.65), (0.05, 0.4, 0.15),
       (1.0, 0.65, 0.75), (0.75, 0.9, 0.4), (0.1, 0.1, 0.4), (0.6, 0.45, 0.85)]


def face_graph(P, F):
    """Dual edges (fa, fb), the shared edge's vertex pair, and per dual edge: centroid distance, fold angle (rad),
    concave flag."""
    e = np.c_[F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]].reshape(-1, 2)
    fi = np.repeat(np.arange(len(F)), 3)
    key = np.sort(e, 1)
    o = np.lexsort(key.T[::-1])
    k2, f2 = key[o], fi[o]
    same = (k2[1:] == k2[:-1]).all(1)
    fa, fb, ev = f2[:-1][same], f2[1:][same], k2[:-1][same]
    T = P[F]
    Cn = T.mean(1)
    N = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-12
    ang = np.arccos(np.clip((N[fa] * N[fb]).sum(1), -1, 1))
    concave = ((Cn[fb] - Cn[fa]) * N[fa]).sum(1) > 1e-6
    dist = np.linalg.norm(Cn[fa] - Cn[fb], axis=1)
    return fa, fb, ev, dist, ang, concave, Cn, N


def stage_segment(cfg, work):
    import v3_mech as M
    z = np.load(work / "sculpt.npz"); P, F = z["P"], z["F"]
    fa, fb, ev, dist, ang, concave, Cn, N = face_graph(P, F)
    if (work / "v2lab.npy").exists() and cfg.get("from_v2"):
        names = list(M.PARTS)
        v2l = np.load(work / "v2lab.npy")
        lab = np.array([names.index(x) if x in names else -1 for x in v2l])
        sg = cfg.get("seg", {})
        fa_ = fa
        if (lab < 0).any():   # faces v2 gave to no part: nearest labelled neighbour
            from scipy.spatial import cKDTree
            ok = lab >= 0
            lab[~ok] = lab[ok][cKDTree(Cn[ok]).query(Cn[~ok])[1]]
        for ov in sg.get("boxes", []):
            m = np.all((Cn >= ov["min"]) & (Cn <= ov["max"]), axis=1)
            if "from" in ov:
                m &= np.isin(lab, [names.index(f_) for f_ in ov["from"]])
            lab[m] = names.index(ov["part"])
        return _finish_segment(cfg, work, P, F, fa, fb, ev, ang, concave, lab, names)
    lab0, D, names = M.nearest_bone_labels(P, F, cfg, return_d=True)
    s = np.sort(D, 1)
    core = (s[:, 0] < cfg.get("seg", {}).get("core_ratio", 0.55) * s[:, 1])
    lab_i = D.argmin(1)
    for ov in cfg.get("seg", {}).get("boxes", []):   # {"part", "min", "max"}: force a part's core
        if "from" in ov:
            continue
        m = np.all((Cn >= ov["min"]) & (Cn <= ov["max"]), axis=1)
        lab_i[m] = names.index(ov["part"]); core[m] = True
    sg = cfg.get("seg", {})
    beta = float(sg.get("crease", 2.0))
    cost = dist * np.where(concave & (ang > np.radians(sg.get("min_crease_deg", 20))), np.exp(beta * ang), 1.0) + 1e-3
    n = len(F)
    G = coo_matrix((np.r_[cost, cost], (np.r_[fa, fb], np.r_[fb, fa])), shape=(n, n)).tocsr()
    src = np.flatnonzero(core)
    dmin, pred, srcs = dijkstra(G, directed=False, indices=src, min_only=True, return_predecessors=True)
    lab = np.where(srcs >= 0, lab_i[np.maximum(srcs, 0)], lab_i)
    return _finish_segment(cfg, work, P, F, fa, fb, ev, ang, concave, lab, names)


def _finish_segment(cfg, work, P, F, fa, fb, ev, ang, concave, lab, names):
    sg = cfg.get("seg", {})
    Cn = P[F].mean(1)
    # snap to the kit's part lines: patches bounded by sharp concave creases take their majority label whole
    lab = snap_patches(F, P, fa, fb, ang, concave, lab, np.radians(sg.get("patch_crease_deg", 25)),
                       sg.get("patch_majority", 0.6))
    # then every flat panel (faces joined across edges flatter than panel_deg, convex or not) takes its majority
    # part whole, so no part line runs through the middle of a flat plate
    flat = np.radians(sg.get("panel_deg", 12))
    lab = snap_patches(F, P, fa, fb, np.where(ang < flat, 0.0, np.pi), np.ones(len(ang), bool), lab, flat * 0.5, 0.0)
    for ov in sg.get("boxes", []):   # {"part", "min", "max", "from": [parts]}: relabel after the growth
        if "from" in ov:
            m = np.all((Cn >= ov["min"]) & (Cn <= ov["max"]), axis=1) & np.isin(lab, [names.index(f_) for f_ in ov["from"]])
            lab[m] = names.index(ov["part"])
    lab = majority_smooth(fa, fb, lab, len(F), iters=int(sg.get("smooth_iters", 4)))
    # small islands (a few faces of one part inside another) go to the neighbour they share the longest edge with
    for _ in range(3):
        lab = absorb_islands(F, fa, fb, ev, P, lab, min_faces=int(sg.get("min_island", 60)))
    names_arr = np.array(names)
    np.savez(work / "labels.npz", lab=names_arr[lab], names=names_arr)
    counts = {names[i]: int((lab == i).sum()) for i in range(len(names))}
    print("segment:", ", ".join(f"{k} {v}" for k, v in counts.items()))
    preview_labels(P, F, names_arr[lab], work / "seg", names)


def majority_smooth(fa, fb, lab, n, iters=4):
    """A face whose label differs from at least two of its three neighbours' common label takes it: removes
    single-face teeth along a boundary."""
    nb = np.full((n, 3), -1)
    cnt = np.zeros(n, int)
    for a_, b_ in ((fa, fb), (fb, fa)):
        o = np.argsort(a_, kind="stable")
        a_s, b_s = a_[o], b_[o]
        start = np.searchsorted(a_s, np.arange(n))
        k = np.arange(len(a_s)) - start[a_s]
        ok = k + cnt[a_s] < 3
        nb[a_s[ok], (k + cnt[a_s])[ok]] = b_s[ok]
        cnt += np.bincount(a_s, minlength=n)
    for _ in range(iters):
        L = np.where(nb >= 0, lab[np.maximum(nb, 0)], -1)
        two = (L[:, 0] == L[:, 1]) & (L[:, 0] >= 0)
        c = np.where(two, L[:, 0], np.where((L[:, 1] == L[:, 2]) & (L[:, 1] >= 0), L[:, 1],
                                            np.where((L[:, 0] == L[:, 2]) & (L[:, 0] >= 0), L[:, 0], -1)))
        ch = (c >= 0) & (c != lab)
        if not ch.any():
            break
        lab = np.where(ch, c, lab)
    return lab


def snap_patches(F, P, fa, fb, ang, concave, lab, deg, majority):
    from scipy.sparse.csgraph import connected_components
    n = len(F)
    T = P[F]
    area = 0.5 * np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1)
    join = ~(concave & (ang > deg))
    A = coo_matrix((np.ones(join.sum()), (fa[join], fb[join])), shape=(n, n))
    nc, comp = connected_components(A, directed=False)
    lab = lab.copy()
    nl = lab.max() + 1
    W = coo_matrix((area, (comp, lab)), shape=(nc, nl)).toarray()
    best = W.argmax(1); share = W.max(1) / np.maximum(W.sum(1), 1e-12)
    ok = share[comp] >= majority
    lab[ok] = best[comp[ok]]
    print(f"  patches: {nc}, {int((share >= majority).sum())} snapped whole, faces relabelled {int((ok & (lab != best[comp])).sum())}")
    return lab


def absorb_islands(F, fa, fb, ev, P, lab, min_faces=60):
    from scipy.sparse.csgraph import connected_components
    n = len(F)
    same = lab[fa] == lab[fb]
    A = coo_matrix((np.ones(same.sum()), (fa[same], fb[same])), shape=(n, n))
    nc, comp = connected_components(A, directed=False)
    size = np.bincount(comp)
    small = np.flatnonzero(size < min_faces)
    if len(small) == 0:
        return lab
    elen = np.linalg.norm(P[ev[:, 0]] - P[ev[:, 1]], axis=1)
    lab = lab.copy()
    issmall = np.isin(comp, small)
    for c_ in small:
        m = (comp[fa] == c_) ^ (comp[fb] == c_)
        if not m.any():
            continue
        other = np.where(comp[fa[m]] == c_, lab[fb[m]], lab[fa[m]])
        w = np.bincount(other, weights=elen[m], minlength=lab.max() + 1)
        lab[comp == c_] = int(w.argmax())
    return lab


def preview_labels(P, F, lab, out, names=None, views="front,back,side,rside,q34,q34b"):
    names = list(names if names is not None else np.unique(lab))
    pal = {n: PAL[i % len(PAL)] for i, n in enumerate(names)}
    col = np.array([pal[l] for l in lab])
    np.savez(f"{out}_col.npz", P=P, F=F, col=col)
    C.blender("views", f"{out}_col.npz", out, "--views", views, "--size", "900")
    from PIL import Image, ImageDraw
    ims = [Image.open(f"{out}_{v}.png").convert("RGB") for v in views.split(",")]
    sheet = Image.new("RGB", (sum(i.width for i in ims), ims[0].height + 40), (20, 20, 20))
    x = 0
    for i in ims:
        sheet.paste(i, (x, 40)); x += i.width
    d = ImageDraw.Draw(sheet)
    for k, n in enumerate(names):
        d.rectangle([10 + k * 150, 8, 30 + k * 150, 28], fill=tuple(int(c * 255) for c in pal[n]))
        d.text((34 + k * 150, 12), n, fill=(255, 255, 255))
    sheet.save(f"{out}_sheet.png")
    return f"{out}_sheet.png"


ATLAS_JOINTS = {  # joint pivot key -> (parent part, child part)
    "torso": ("a-hip", "a_torso"),
    "rshoulder": ("a_torso", "a_ruarm"), "ruarm": ("a_ruarm", "a_rlarm"), "rgun": ("a_rlarm", "a_rgun"),
    "lshoulder": ("a_torso", "a_luarm"), "luarm": ("a_luarm", "a_llarm"), "lgun": ("a_llarm", "a_lgun"),
    "luleg": ("a-hip", "a_luleg"), "llleg": ("a_luleg", "a_llleg"), "lankle": ("a_llleg", "a_lfoot"),
    "ruleg": ("a-hip", "a_ruleg"), "rlleg": ("a_ruleg", "a_rlleg"), "rankle": ("a_rlleg", "a_rfoot"),
}
JOINTS = dict(ATLAS_JOINTS)   # set per mech by v3_mech.load_cfg


def contacts(P, F, lab):
    """{(part a, part b) sorted: boundary edge vertex pairs (n, 2)} for every pair of parts sharing an edge."""
    fa, fb, ev, *_ = face_graph(P, F)
    m = lab[fa] != lab[fb]
    out = {}
    for a, b, e in zip(lab[fa[m]], lab[fb[m]], ev[m]):
        out.setdefault(tuple(sorted((str(a), str(b)))), []).append(e)
    return {k: np.array(v) for k, v in out.items()}


def report_contacts(cfg, work):
    z = np.load(work / "sculpt.npz"); P, F = z["P"], z["F"]
    lab = np.load(work / "labels.npz")["lab"]
    piv = {k: np.array(v) for k, v in cfg["pivots"].items()}
    pair_joint = {tuple(sorted(v)): k for k, v in JOINTS.items()}
    for k, es in sorted(contacts(P, F, lab).items(), key=lambda t: -len(t[1])):
        q = P[np.unique(es)]
        j = pair_joint.get(k)
        if j:
            d = np.linalg.norm(q - piv[j], axis=1)
            fit = json.loads((work / "fit.json").read_text())
            ch = JOINTS[j][1]
            ax = np.array(fit["xform"][ch])[:3, :3].T @ np.array(cfg.get("joints", {}).get(j, {}).get("axis", [1, 0, 0]), float)
            dq = q - piv[j]; t = dq @ ax; rad = np.linalg.norm(dq - t[:, None] * ax, axis=1)
            print(f"{k[0]:8s}-{k[1]:8s} joint {j:9s} {len(es):4d} edges  from pivot p50 {np.median(d):5.0f} p90 {np.percentile(d, 90):5.0f} max {d.max():5.0f}"
                  f" | from X axis p50 {np.median(rad):5.0f} p90 {np.percentile(rad, 90):5.0f} max {rad.max():5.0f}, along {t.min():5.0f}..{t.max():5.0f}")
        else:
            print(f"{k[0]:8s}-{k[1]:8s} NOT A JOINT {len(es):4d} edges  centre {q.mean(0).round(-1)} extent {np.ptp(q, 0).round(-1)}")


def zoom(work, name, lab, centre, span, views="front,side", size=900):
    z = np.load(work / "sculpt.npz"); P, F = z["P"], z["F"]
    names = sorted(set(lab.tolist()))
    import v3_mech as M
    names = list(M.PARTS)
    pal = {n: PAL[i % len(PAL)] for i, n in enumerate(names)}
    col = np.array([pal[l] for l in lab])
    np.savez(work / f"{name}_col.npz", P=P, F=F, col=col)
    C.blender("views", work / f"{name}_col.npz", work / name, "--views", views, "--size", str(size),
              "--centre", ",".join(str(v) for v in centre), "--span", str(span))
    return [work / f"{name}_{v}.png" for v in views.split(",")]


# --- joints: closed rigid parts with modelled actuators --------------------------------------------------------

def actuator_f(act):
    """Implicit of an actuator (negative inside): sphere {c, r} or capped cylinder {c, axis, r, half}."""
    c = np.asarray(act["c"], float)
    if act["kind"] == "sphere":
        r = float(act["r"])
        return lambda X: np.linalg.norm(X - c, axis=-1) - r
    a = np.asarray(act["axis"], float); a = a / np.linalg.norm(a)
    r, h = float(act["r"]), float(act["half"])
    def f(X):
        d = X - c
        t = d @ a
        rad = np.linalg.norm(d - t[..., None] * a, axis=-1)
        return np.maximum(rad - r, np.abs(t) - h)
    return f


def clip_outside(V, F, f, iters=24, src=None):
    """Keep the part of the surface (V, F) where f >= 0, cut conformally along f = 0 (crossings found by bisection,
    one vertex per crossed edge, so the cut stays watertight along shared edges). Returns V, F, on_cut (bool per
    vertex: lies on f = 0)."""
    fv = f(V)
    inside = fv < 0
    if not inside.any():
        return (V, F, np.zeros(len(V), bool)) if src is None else (V, F, np.zeros(len(V), bool), src)
    keep_all = ~inside[F].any(1)
    drop_all = inside[F].all(1)
    mixed = np.flatnonzero(~keep_all & ~drop_all)
    newV = [V]
    on = [np.zeros(len(V), bool)]
    cross = {}
    nV = len(V)
    def xpt(i, j):
        nonlocal nV
        key = (i, j) if i < j else (j, i)
        if key in cross:
            return cross[key]
        a, b = V[i], V[j]   # a inside or outside, find f = 0
        fa = fv[i]
        lo, hi = 0.0, 1.0
        for _ in range(iters):
            m = 0.5 * (lo + hi)
            fm = f((a + m * (b - a))[None])[0]
            if (fm < 0) == (fa < 0):
                lo = m
            else:
                hi = m
        p = a + 0.5 * (lo + hi) * (b - a)
        newV.append(p[None]); on.append(np.ones(1, bool))
        cross[key] = nV
        nV += 1
        return cross[key]
    out = [F[keep_all]]
    so = [src[keep_all]] if src is not None else None
    for t in mixed:
        tri = F[t]
        ins = inside[tri]
        poly = []
        for k in range(3):
            i, j = tri[k], tri[(k + 1) % 3]
            if not inside[i]:
                poly.append(i)
            if inside[i] != inside[j]:
                poly.append(xpt(i, j))
        for k in range(1, len(poly) - 1):
            out.append(np.array([[poly[0], poly[k], poly[k + 1]]]))
            if so is not None:
                so.append(src[t:t + 1])
    V2 = np.concatenate(newV)
    on2 = np.concatenate(on)
    F2 = np.concatenate(out)
    used = np.unique(F2)
    remap = -np.ones(len(V2), int); remap[used] = np.arange(len(used))
    if src is not None:
        return V2[used], remap[F2], on2[used], np.concatenate(so)
    return V2[used], remap[F2], on2[used]


def boundary_loops(F):
    """Open boundary loops of a triangle mesh: list of vertex index arrays (ordered)."""
    e = np.c_[F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]].reshape(-1, 2)
    key = np.sort(e, 1)
    u, inv, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    b = e[cnt[inv.ravel()] == 1]          # directed boundary edges (face winding)
    nxt = {}
    for a_, b_ in b:
        nxt.setdefault(int(a_), []).append(int(b_))
    loops, seen = [], set()
    for start in list(nxt):
        if start in seen:
            continue
        loop = [start]; seen.add(start); cur = start
        while True:
            cand = [c for c in nxt.get(cur, []) if c not in seen or c == start]
            if not cand:
                break
            cur = cand[0]
            if cur == start:
                break
            loop.append(cur); seen.add(cur)
        if len(loop) >= 3:
            loops.append(np.array(loop))
    return loops


def earclip(P2):
    import hd_v2 as H
    return H.earclip(P2)


def film_cap(V, loop, sub=3, iters=80):
    """A soap-film cap over a non-planar loop: a fan from the loop's centroid, subdivided, interior vertices relaxed
    toward the mean of their neighbours (the boundary stays fixed), so it spans the loop without folds or spikes.
    Returns (new vertices, faces indexing [V; new vertices])."""
    n = len(loop)
    Q = V[loop]
    c = Q.mean(0)
    Vl = [*Q, c]
    Fl = [[i, (i + 1) % n, n] for i in range(n)]
    fixed = set(range(n))
    Vl = np.array(Vl)
    F_ = np.array(Fl)
    for _ in range(sub):
        cache = {}
        Vlist = list(Vl)
        def mid(i, j):
            k = (min(i, j), max(i, j))
            if k not in cache:
                Vlist.append((Vlist[i] + Vlist[j]) / 2); cache[k] = len(Vlist) - 1
                # a midpoint on a boundary edge (consecutive loop vertices) would add a boundary vertex: keep
                # boundary edges unsplit by splitting only interior edges
            return cache[k]
        nf = []
        for a, b, c_ in F_:
            # boundary edge a-b (both fixed, consecutive) is never split
            bnd = lambda i, j: i in fixed and j in fixed and ((j - i) % n == 1 or (i - j) % n == 1)
            ab = None if bnd(a, b) else mid(a, b)
            bc = None if bnd(b, c_) else mid(b, c_)
            ca = None if bnd(c_, a) else mid(c_, a)
            if ab is None and bc is None and ca is None:
                nf.append([a, b, c_]); continue
            if ab is None:      # split from the opposite vertex
                nf += [[a, b, bc], [a, bc, ca], [ca, bc, c_]]
            elif bc is None:
                nf += [[a, ab, ca], [ab, b, c_], [ab, c_, ca]]
            elif ca is None:
                nf += [[a, ab, c_], [ab, bc, c_], [ab, b, bc]]
            else:
                nf += [[a, ab, ca], [b, bc, ab], [c_, ca, bc], [ab, bc, ca]]
        Vl = np.array(Vlist); F_ = np.array(nf)
    m = len(Vl)
    nb = [set() for _ in range(m)]
    for a, b, c_ in F_:
        nb[a] |= {b, c_}; nb[b] |= {a, c_}; nb[c_] |= {a, b}
    free = np.array([i for i in range(m) if i not in fixed])
    nbl = [list(nb[i]) for i in free]
    for _ in range(iters):
        Vl[free] = np.array([Vl[l].mean(0) for l in nbl])
    # index: loop vertices -> V's indices, the rest are new
    idx = np.empty(m, int)
    idx[:n] = loop
    idx[n:] = len(V) + np.arange(m - n)
    return Vl[n:], idx[F_]


def skirt(V, F, loop, depth, rings=2):
    """Extend the part's own surface past an open loop by `depth` (mm): each loop vertex moves along the in-plane
    continuation of its boundary faces (perpendicular to the boundary edge, away from the face), in `rings` steps.
    Returns new vertices, new faces (indexing [V; new]) and the outer ring's vertex indices."""
    n = len(loop)
    pos = {int(v): k for k, v in enumerate(loop)}
    # boundary faces: the face holding each directed boundary edge loop[k] -> loop[k+1]
    e = np.c_[F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]].reshape(-1, 2)
    fi = np.repeat(np.arange(len(F)), 3)
    lut = {(int(a), int(b)): int(f) for (a, b), f in zip(e, fi) if int(a) in pos and int(b) in pos}
    dirs = np.zeros((n, 3))
    for k in range(n):
        a, b = int(loop[k]), int(loop[(k + 1) % n])
        f = lut.get((a, b))
        if f is None:
            continue
        T = V[F[f]]
        nrm = np.cross(T[1] - T[0], T[2] - T[0]); nrm /= np.linalg.norm(nrm) + 1e-12
        ed = V[b] - V[a]; ed /= np.linalg.norm(ed) + 1e-12
        out = np.cross(ed, nrm)            # in the face plane, perpendicular to the edge
        if (out @ (T.mean(0) - V[a])) > 0:
            out = -out
        dirs[k] += out; dirs[(k + 1) % n] += out
    dirs /= np.linalg.norm(dirs, axis=1, keepdims=True) + 1e-12
    # smooth the directions along the loop so corners don't fold
    for _ in range(2):
        dirs = (np.roll(dirs, 1, 0) + 2 * dirs + np.roll(dirs, -1, 0))
        dirs /= np.linalg.norm(dirs, axis=1, keepdims=True) + 1e-12
    newV, newF = [], []
    prev = np.asarray(loop)
    base = len(V)
    for r in range(1, rings + 1):
        ring = base + (r - 1) * n + np.arange(n)
        newV.append(V[loop] + dirs * depth * r / rings)
        for k in range(n):
            a, b = prev[k], prev[(k + 1) % n]
            a2, b2 = ring[k], ring[(k + 1) % n]
            newF += [[b, a, a2], [b, a2, b2]]
        prev = ring
    return np.concatenate(newV), np.array(newF), prev


def cap_loop(V, loop):
    """Faces closing one boundary loop (wound to face out of the part: reversed against the loop's direction),
    triangulated in the loop's best-fit plane. Returns (faces into V, planarity deviation mm, simple)."""
    import hd_v2 as H
    Q = V[loop]
    mu = Q.mean(0)
    w, vec = np.linalg.eigh(np.cov((Q - mu).T))
    n = vec[:, 0]; e1 = vec[:, 2]; e2 = np.cross(n, e1)
    P2 = np.c_[(Q - mu) @ e1, (Q - mu) @ e2]
    dev = float(np.abs((Q - mu) @ n).max())
    simple = H.simple_polygon(P2)
    span = float(np.sqrt(w[2])) + 1e-9
    newV = np.zeros((0, 3))
    if simple and dev < max(25.0, 0.06 * span):
        T = earclip(P2)
        faces = loop[T][:, ::-1]
    else:
        newV, faces = film_cap(V, loop)
        faces = faces[:, ::-1]
    # orientation: boundary edges run with the part's own faces; a cap face must run against them
    a_, b_ = loop[0], loop[1]
    for f_ in faces:
        for k in range(3):
            if f_[k] == a_ and f_[(k + 1) % 3] == b_:
                faces = faces[:, ::-1]
                break
        else:
            continue
        break
    return faces, dev, simple, newV


def icosphere(sub=4):
    t = (1 + 5 ** 0.5) / 2
    V = np.array([[-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0], [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t],
                  [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1]], float)
    F = np.array([[0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11], [1, 5, 9], [5, 11, 4], [11, 10, 2],
                  [10, 7, 6], [7, 1, 8], [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9], [4, 9, 5], [2, 4, 11],
                  [6, 2, 10], [8, 6, 7], [9, 8, 1]])
    V /= np.linalg.norm(V, axis=1, keepdims=True)
    for _ in range(sub):
        cache = {}
        Vl = list(V)
        def mid(i, j):
            k = (min(i, j), max(i, j))
            if k not in cache:
                m = (Vl[i] + Vl[j]) / 2; Vl.append(m / np.linalg.norm(m)); cache[k] = len(Vl) - 1
            return cache[k]
        nf = []
        for a, b, c in F:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            nf += [[a, ab, ca], [b, bc, ab], [c, ca, bc], [ab, bc, ca]]
        V = np.array(Vl); F = np.array(nf)
    return V, F


def actuator_mesh(act, sides=48):
    """A modelled actuator: a ball, or a drum with chamfered rims and a hub ring on each face (bare-metal
    hardware). Slightly over its implicit (0.4 %), so cut loops lying on the implicit are covered."""
    c = np.asarray(act["c"], float)
    if act["kind"] == "sphere":
        V, F = icosphere(3)
        return c + V * act["r"] * 1.004, F
    a = np.asarray(act["axis"], float); a /= np.linalg.norm(a)
    u = np.cross(a, [0, 0, 1.0] if abs(a[2]) < 0.9 else [1.0, 0, 0]); u /= np.linalg.norm(u); v = np.cross(a, u)
    r, h = act["r"] * 1.004, act["half"] * 1.004
    ch = min(0.08 * r, 0.3 * h)
    # profile (radius, axial) from -h to +h: hub, face, chamfer, rim, chamfer, face, hub
    prof = [(0.0, -h - 0.04 * r), (0.45 * r, -h - 0.04 * r), (0.5 * r, -h), (r - ch, -h), (r, -h + ch),
            (r, h - ch), (r - ch, h), (0.5 * r, h), (0.45 * r, h + 0.04 * r), (0.0, h + 0.04 * r)]
    ang = np.linspace(0, 2 * np.pi, sides, endpoint=False)
    V, F = [], []
    for k, (rr, t) in enumerate(prof):
        for an in ang:
            V.append(c + a * t + rr * (np.cos(an) * u + np.sin(an) * v))
    n = sides
    for k in range(len(prof) - 1):
        for i in range(n):
            a0, a1 = k * n + i, k * n + (i + 1) % n
            b0, b1 = (k + 1) * n + i, (k + 1) * n + (i + 1) % n
            F += [[a0, b0, b1], [a0, b1, a1]]
    V, F = np.array(V), np.array(F)
    # the axial poles are rings of radius 0: weld them
    return weld(V, F)


def weld(V, F, dec=3):
    key = np.round(V, dec)
    u, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    F2 = inv.ravel()[F]
    good = (F2[:, 0] != F2[:, 1]) & (F2[:, 1] != F2[:, 2]) & (F2[:, 2] != F2[:, 0])
    return V[first], F2[good]


def orient_out(V, F):
    """Flip a closed mesh so its signed volume is positive (normals out)."""
    T = V[F]
    vol = np.einsum("ij,ij->i", T[:, 0], np.cross(T[:, 1], T[:, 2])).sum() / 6
    return F if vol >= 0 else F[:, ::-1]


def stage_joints(cfg, work):
    import v3_mech as M
    z = np.load(work / "sculpt.npz"); P, F = z["P"], z["F"]
    lab = np.load(work / "labels.npz")["lab"]
    fit = json.loads((work / "fit.json").read_text())
    rest = {k: np.array(v) for k, v in fit["rest"].items()}
    xf = {k: np.array(v) for k, v in fit["xform"].items()}
    jcfg = cfg.get("joints", {})
    acts = []
    for jk, (par, ch) in JOINTS.items():
        jc = jcfg.get(jk)
        if not jc:
            continue
        joint = M.PARTS[ch]["joint"]
        a = dict(jc); a["joint"] = jk; a["parent"] = par; a["child"] = ch
        a["c"] = (rest[joint] + np.asarray(jc.get("offset", [0, 0, 0]), float)).tolist()
        if a["kind"] == "cyl":
            a["axis"] = jc.get("axis_rest", jc.get("axis", [1, 0, 0]))
        if cfg.get("auto_actuators") and not jc.get("fixed"):
            fit_actuator(a, P, F, xf[ch], float(cfg.get("actuator_out_max", 0.2)))
            if a["outside"] > 0.5:   # the pivot hangs in the air: no housing (the parts' own caps close the seam)
                print(f"  actuator {jk} dropped: the pivot is outside the armour")
                continue
        acts.append(a)
    Vs, Fs, parts, kinds, srcs = [], [], [], [], []
    nv = 0
    report = {"parts": {}, "actuators": []}
    for part in M.PARTS:
        m = lab == part
        if not m.any():
            continue
        used = np.unique(F[m])
        remap = -np.ones(len(P), int); remap[used] = np.arange(len(used))
        V = P[used] @ xf[part][:3, :3].T + xf[part][:3, 3]
        Fp = remap[F[m]]
        sp = np.flatnonzero(m)
        mine = [a for a in acts if part in (a["parent"], a["child"])]
        for a in mine:
            V, Fp, _, sp = clip_outside(V, Fp, actuator_f(a), src=sp)
        for cl in cfg.get("clips", []):   # {"part", "p", "n"} rest frame: drop the part's surface beyond the plane
            if cl["part"] == part:
                p0 = np.asarray(cl["p"], float); nn = np.asarray(cl["n"], float); nn /= np.linalg.norm(nn)
                V, Fp, _, sp = clip_outside(V, Fp, lambda X, p0=p0, nn=nn: -((X - p0) @ nn), src=sp)
        ncap, devs, nonsimple = 0, [], 0
        capF = []
        depth = float(cfg.get("skirt_mm", 250))
        on_act = lambda pts: (np.min([np.abs(actuator_f(a)(pts)) for a in mine], axis=0) < 2.0).all() if mine else False
        skF = []
        for loop in boundary_loops(Fp):
            if on_act(V[loop]):
                continue        # lies on an actuator: the actuator closes it
            nV_, sf, outer = skirt(V, Fp, loop, depth) if depth > 0 else (np.zeros((0, 3)), np.zeros((0, 3), int), loop)
            V = np.r_[V, nV_]
            skF.append(sf)
            cf, dev, simple, nV_ = cap_loop(V, outer)
            V = np.r_[V, nV_]
            capF.append(cf); ncap += 1; devs.append(dev); nonsimple += (not simple)
        capF = [s_ for s_ in skF if len(s_)] + capF
        Fk = [Fp] + capF
        kk = [np.zeros(len(Fp), int)] + [np.ones(len(c), int) for c in capF]
        srcs.append(np.r_[sp, np.full(sum(len(c) for c in capF), -1)])
        Vs.append(V); Fs.append(np.concatenate(Fk) + nv); kinds.append(np.concatenate(kk))
        parts.append(np.full(sum(len(x) for x in Fk), part, object))
        nv += len(V)
        report["parts"][part] = {"faces": int(len(Fp)), "caps": ncap, "cap_dev_mm": [round(d) for d in devs],
                                 "nonsimple_caps": nonsimple}
    for a in acts:
        V, Fa = actuator_mesh(a)
        Fa = orient_out(V, Fa)
        srcs.append(np.full(len(Fa), -1))
        Vs.append(V); Fs.append(Fa + nv); kinds.append(np.full(len(Fa), 2)); parts.append(np.full(len(Fa), a.get("ride", a["child"]), object))
        nv += len(V)
        report["actuators"].append({k: a[k] for k in ("joint", "kind", "r", "c")})
    Pr = np.concatenate(Vs); Fr = np.concatenate(Fs); part_arr = np.concatenate(parts).astype(str); kind = np.concatenate(kinds)
    np.savez(work / "rest.npz", P=Pr, F=Fr, part=part_arr, kind=kind, src=np.concatenate(srcs))
    (work / "rest.json").write_text(json.dumps({"actuators": acts, "report": report}, indent=1, default=float))
    for p_, r_ in report["parts"].items():
        print(f"  {p_:8s} {r_['faces']:6d} faces, {r_['caps']} caps (plane dev {r_['cap_dev_mm']} mm){' NONSIMPLE ' + str(r_['nonsimple_caps']) if r_['nonsimple_caps'] else ''}")
    print(f"joints: {len(Fr)} faces, {len(acts)} actuators")



def preview_rest(work, name="rest", npz="rest.npz", views="front,back,side,rside,q34,q34b", size=800, centre=None, span=None):
    import v3_mech as M
    z = np.load(work / npz)
    names = list(M.PARTS)
    pal = {n: PAL[i % len(PAL)] for i, n in enumerate(names)}
    col = np.array([pal.get(p, (1, 1, 1)) for p in z["part"]])
    col[z["kind"] == 1] = (1.0, 0.0, 0.85)
    col[z["kind"] == 2] = (0.12, 0.12, 0.14)
    np.savez(work / f"{name}_col.npz", P=z["P"], F=z["F"], col=col)
    extra = []
    if centre is not None:
        extra = ["--centre", ",".join(str(v) for v in centre), "--span", str(span)]
    C.blender("views", work / f"{name}_col.npz", work / name, "--views", views, "--size", str(size), "--cull", "0", *extra)
    from PIL import Image
    vs = views.split(",")
    ims = [Image.open(work / f"{name}_{v}.png").convert("RGB") for v in vs]
    cols = 3
    sheet = Image.new("RGB", (size * cols, size * ((len(ims) + cols - 1) // cols)))
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % cols) * size, (i // cols) * size))
    sheet.save(work / f"{name}_sheet.png")
    return work / f"{name}_sheet.png"


# --- the v3 skeleton and posing ------------------------------------------------------------------------------

class Rig:
    """The original's nodes and animations with the v3 rest pivots (fit.json): joint translations re-set from the
    sculpt's bone lengths, root translation keys moved by the root's rest offset. World matrices in glTF metres."""

    def __init__(self, cfg, work):
        import pose_test as PT
        import hd_rig as R
        import v3_mech as M
        fit = json.loads((Path(work) / "fit.json").read_text())
        g, b = R.load_glb(str(C.ROOT / cfg["base_glb"]))
        self.g, self.b = g, b
        names = [n.get("name", "") for n in g["nodes"]]
        self.names = names
        parent = {}
        for i, n in enumerate(g["nodes"]):
            for c_ in n.get("children", []):
                parent[c_] = i
        W0 = R.world_matrices(g)
        rest_gl = {k: M.mm_to_gl(np.array(v)) for k, v in fit["rest"].items()}
        # world rest positions of every node: joints from fit, the rest keep their offset to their parent joint
        self.rest_world = {}
        for i in range(len(names)):
            pass
        new_world = {}
        order = sorted(range(len(names)), key=lambda i: self._depth(i, parent))
        for i in order:
            nm = names[i]
            if nm in rest_gl:
                new_world[i] = rest_gl[nm]
            elif i in parent:
                new_world[i] = new_world[parent[i]] + (W0[i][:3, 3] - W0[parent[i]][:3, 3])
            else:
                new_world[i] = W0[i][:3, 3]
        for nm, pos in cfg.get("hooks", {}).items():   # effect hooks placed on the sculpt (game mm, rest pose)
            if nm in names:
                new_world[names.index(nm)] = M.mm_to_gl(np.array(pos))
        for i in order:
            n = g["nodes"][i]
            if i in parent:
                n["translation"] = (new_world[i] - new_world[parent[i]]).tolist()
            else:
                n["translation"] = new_world[i].tolist()
        self.root_delta = new_world[names.index("joint_root")] - W0[names.index("joint_root")][:3, 3]
        self.an = PT.Animator(g, b)
        ri = names.index("joint_root")
        for k, (tracks, dur) in self.an.anims.items():
            for ti, (node, path, t, v, interp) in enumerate(tracks):
                if node == ri and path == "translation":
                    tracks[ti] = (node, path, t, v + self.root_delta, interp)
        self.W_rest = self.an.world()
        self.parent = parent

    @staticmethod
    def _depth(i, parent):
        d = 0
        while i in parent:
            i = parent[i]; d += 1
        return d

    def part_matrices(self, anim=None, t=0.0):
        """{part: 4x4 in game mm, Z up} taking rest-pose part vertices to the pose (anim, t)."""
        import v3_mech as M
        W = self.an.world(anim, t)
        S_ = np.diag([1.0, 1.0, 1.0, 1.0])
        # mm Z-up <-> gl: x, -z, y
        A = np.array([[1e-3, 0, 0, 0], [0, 0, 1e-3, 0], [0, -1e-3, 0, 0], [0, 0, 0, 1]])   # mm -> gl
        Ainv = np.linalg.inv(A)
        out = {}
        for part, d in M.PARTS.items():
            j = self.names.index(d["joint"])
            out[part] = Ainv @ W[j] @ np.linalg.inv(self.W_rest[j]) @ A
        return out

    def durations(self):
        return {k: dur for k, (tr, dur) in self.an.anims.items()}


def pose_mesh(rig, P, F, part, anim, t):
    Ms = rig.part_matrices(anim, t)
    Q = P.copy()
    vpart = np.empty(len(P), object)
    vpart[F.ravel()] = np.repeat(part, 3)
    for p_, M_ in Ms.items():
        m = vpart == p_
        Q[m] = P[m] @ M_[:3, :3].T + M_[:3, 3]
    return Q


def original_part_points(cfg, part):
    """The original model's mesh vertices for one part node, in its node frame (glTF metres)."""
    import hd_rig as R
    g, b = R.load_glb(str(C.ROOT / cfg["base_glb"]))
    for n in g["nodes"]:
        if n.get("name") == part and "mesh" in n:
            pts = [R.read_accessor(g, b, pr["attributes"]["POSITION"]).astype(float) for pr in g["meshes"][n["mesh"]]["primitives"]]
            return np.concatenate(pts)
    return np.zeros((0, 3))


def ground_fix(rig, cfg, rest_P, rest_F, rest_part):
    """Per root translation key: move the root up or down so the lower foot sole is as high above the ground as the
    original's lower foot at that key (the sculpt's thigh and shin lengths differ from the original's, so the
    original's root height would sink or lift the stance foot). Returns {anim: max |correction| m}."""
    import pose_test as PT
    import hd_rig as R
    g0, b0 = R.load_glb(str(C.ROOT / cfg["base_glb"]))
    an0 = PT.Animator(g0, b0)
    names0 = [n.get("name", "") for n in g0["nodes"]]
    import v3_mech as M
    vpart = np.empty(len(rest_P), object); vpart[rest_F.ravel()] = np.repeat(rest_part, 3)
    whole = lambda k: any(k.startswith(w) for w in ("Fall", "GetUp", "Park", "StandToPark"))
    feet = cfg.get("feet", ["a_lfoot", "a_rfoot"])
    feet0_all = {p: original_part_points(cfg, p) for p in M.PARTS}
    sole_all = {}
    for p in M.PARTS:
        q = rest_P[vpart == p]
        if len(q):
            sole_all[p] = q[q[:, 2] < np.percentile(q[:, 2], 8)] if p in feet else q[::7]
    ri = rig.names.index("joint_root")
    out = {}
    for k, (tracks, dur) in rig.an.anims.items():
        for ti, (node, path, t, v, interp) in enumerate(tracks):
            if node != ri or path != "translation":
                continue
            corr = np.zeros(len(t))
            use = list(M.PARTS) if whole(k) else feet
            feet0 = {p: feet0_all[p] for p in use if len(feet0_all[p])}
            sole = {p: sole_all[p] for p in use if p in sole_all}
            for i, tt in enumerate(t):
                W0 = an0.world(k, tt)
                h0 = min(((W0[names0.index(p)][:3, :3] @ feet0[p].T).T + W0[names0.index(p)][:3, 3])[:, 1].min() for p in feet0)
                Ms = rig.part_matrices(k, tt)
                h1 = min(((sole[p] @ Ms[p][:3, :3].T) + Ms[p][:3, 3])[:, 2].min() for p in sole) / 1000.0
                corr[i] = h0 - h1
            v2 = v.copy(); v2[:, 1] += corr
            tracks[ti] = (node, path, t, v2, interp)
            out[k] = (float(np.abs(corr).max()), float(corr.mean()))
    return out


def preview_poses(cfg, work, poses, name="pose", views="q34,side", size=600, ground=True):
    """Posed rest mesh (caps magenta, actuators dark) for [(anim, t), ...]: one row per pose."""
    import v3_mech as M
    from PIL import Image, ImageDraw
    z = np.load(work / "rest.npz")
    rig = Rig(cfg, work)
    ground_fix(rig, cfg, z["P"], z["F"], z["part"])
    names = list(M.PARTS)
    pal = {n: PAL[i % len(PAL)] for i, n in enumerate(names)}
    col = np.array([pal.get(p, (1, 1, 1)) for p in z["part"]])
    col[z["kind"] == 1] = (1.0, 0.0, 0.85)
    col[z["kind"] == 2] = (0.12, 0.12, 0.14)
    rows = []
    for anim, t in poses:
        Q = pose_mesh(rig, z["P"], z["F"], z["part"], anim, t)
        P2, F2, c2 = Q, z["F"], col
        if ground:   # a thin ground slab at z = 0
            g = np.array([[-6000, -6000, -30], [6000, -6000, -30], [6000, 6000, -30], [-6000, 6000, -30]], float)
            P2 = np.r_[Q, g]; F2 = np.r_[z["F"], [[len(Q), len(Q) + 1, len(Q) + 2], [len(Q), len(Q) + 2, len(Q) + 3]]]
            c2 = np.r_[col, [[0.35, 0.33, 0.3]] * 2]
        np.savez(work / f"{name}_tmp.npz", P=P2, F=F2, col=c2)
        C.blender("views", work / f"{name}_tmp.npz", work / f"{name}_tmp", "--views", views, "--size", str(size),
                  "--cull", "0", "--centre", "0,0,6500", "--span", "15500")
        ims = [Image.open(work / f"{name}_tmp_{v}.png").convert("RGB") for v in views.split(",")]
        row = Image.new("RGB", (size * len(ims), size))
        for i, im in enumerate(ims):
            row.paste(im, (i * size, 0))
        ImageDraw.Draw(row).text((8, 8), f"{anim} t={t:.2f}", fill=(255, 255, 0))
        rows.append(row)
    cols = 2
    sheet = Image.new("RGB", (rows[0].width * cols, size * ((len(rows) + cols - 1) // cols)))
    for i, r in enumerate(rows):
        sheet.paste(r, ((i % cols) * r.width, (i // cols) * size))
    sheet.save(work / f"{name}_sheet.png")
    return work / f"{name}_sheet.png"


def original_mesh(cfg):
    """The original model's node meshes: {part: (V local glTF m, F)}."""
    import hd_rig as R
    g, b = R.load_glb(str(C.ROOT / cfg["base_glb"]))
    out = {}
    for n in g["nodes"]:
        if "mesh" in n:
            Vs, Fs, o = [], [], 0
            for pr in g["meshes"][n["mesh"]]["primitives"]:
                V = R.read_accessor(g, b, pr["attributes"]["POSITION"]).astype(float)
                I = (R.read_accessor(g, b, pr["indices"]).astype(np.int64).reshape(-1, 3) if "indices" in pr
                     else np.arange(len(V)).reshape(-1, 3))
                Vs.append(V); Fs.append(I + o); o += len(V)
            out[n["name"]] = (np.concatenate(Vs), np.concatenate(Fs))
    return out


def preview_original_poses(cfg, work, poses, name="orig", views="q34,side", size=600):
    import pose_test as PT
    import hd_rig as R
    import v3_mech as M
    from PIL import Image, ImageDraw
    g, b = R.load_glb(str(C.ROOT / cfg["base_glb"]))
    an = PT.Animator(g, b)
    names = [n.get("name", "") for n in g["nodes"]]
    meshes = original_mesh(cfg)
    pal = {n: PAL[i % len(PAL)] for i, n in enumerate(M.PARTS)}
    rows = []
    for anim, t in poses:
        W = an.world(anim, t)
        Ps, Fs, cs, o = [], [], [], 0
        for nm, (V, F_) in meshes.items():
            M_ = W[names.index(nm)]
            Q = V @ M_[:3, :3].T + M_[:3, 3]
            Ps.append(np.c_[Q[:, 0], -Q[:, 2], Q[:, 1]] * 1000); Fs.append(F_ + o); o += len(V)
            cs.append(np.tile(pal.get(nm, (0.8, 0.8, 0.8)), (len(F_), 1)))
        g_ = np.array([[-6000, -6000, -30], [6000, -6000, -30], [6000, 6000, -30], [-6000, 6000, -30]], float)
        P2 = np.r_[np.concatenate(Ps), g_]; n0 = o
        F2 = np.r_[np.concatenate(Fs), [[n0, n0 + 1, n0 + 2], [n0, n0 + 2, n0 + 3]]]
        c2 = np.r_[np.concatenate(cs), [[0.35, 0.33, 0.3]] * 2]
        np.savez(work / f"{name}_tmp.npz", P=P2, F=F2, col=c2)
        C.blender("views", work / f"{name}_tmp.npz", work / f"{name}_tmp", "--views", views, "--size", str(size),
                  "--cull", "0", "--centre", "0,0,6500", "--span", "15500")
        ims = [Image.open(work / f"{name}_tmp_{v}.png").convert("RGB") for v in views.split(",")]
        row = Image.new("RGB", (size * len(ims), size))
        for i, im in enumerate(ims):
            row.paste(im, (i * size, 0))
        ImageDraw.Draw(row).text((8, 8), f"ORIGINAL {anim} t={t:.2f}", fill=(255, 255, 0))
        rows.append(row)
    cols = 2
    sheet = Image.new("RGB", (rows[0].width * cols, size * ((len(rows) + cols - 1) // cols)))
    for i, r in enumerate(rows):
        sheet.paste(r, ((i % cols) * r.width, (i // cols) * size))
    sheet.save(work / f"{name}_sheet.png")
    return work / f"{name}_sheet.png"


def preview_part(work, part, name=None, views="front,back,side,rside,top,q34", size=500):
    z = np.load(work / "rest.npz")
    m = z["part"] == part
    used = np.unique(z["F"][m]); remap = -np.ones(len(z["P"]), int); remap[used] = np.arange(len(used))
    col = np.where((z["kind"][m] == 1)[:, None], [1.0, 0.0, 0.85], np.where((z["kind"][m] == 2)[:, None], [0.15, 0.15, 0.17], [0.75, 0.75, 0.72]))
    P = z["P"][used]
    np.savez(work / f"part_tmp.npz", P=P, F=remap[z["F"][m]], col=col)
    name = name or f"part_{part}"
    c = (P.min(0) + P.max(0)) / 2; span = float(np.ptp(P, 0).max()) * 1.15
    C.blender("views", work / "part_tmp.npz", work / name, "--views", views, "--size", str(size), "--cull", "0",
              "--centre", ",".join(f"{v:.0f}" for v in c), "--span", f"{span:.0f}")
    from PIL import Image
    vs = views.split(",")
    sheet = Image.new("RGB", (size * 3, size * ((len(vs) + 2) // 3)))
    for i, v in enumerate(vs):
        sheet.paste(Image.open(work / f"{name}_{v}.png").convert("RGB"), ((i % 3) * size, (i // 3) * size))
    sheet.save(work / f"{name}_sheet.png")
    return work / f"{name}_sheet.png"


def cap_visibility(cfg, work, anims=("Walk", "Run", "Idle"), samples=6, yaws=(0, 90, 180, 270, 45, 225), pitch=40,
                   size=320, rig=None):
    """Share of the mech's pixels that show a cap (a closed-off part line) or an actuator, posed through the
    animations, flat-shaded from the RTS-like views. Returns {anim: (cap share, actuator share)} and per-part cap
    pixel counts."""
    from PIL import Image
    z = np.load(work / "rest.npz")
    if rig is None:
        rig = Rig(cfg, work)
        ground_fix(rig, cfg, z["P"], z["F"], z["part"])
    import v3_mech as M
    names = list(M.PARTS)
    # encode part index in red, kind in green
    pi = np.array([names.index(p) for p in z["part"]])
    col = np.c_[(pi + 1) / 32.0, np.where(z["kind"] == 1, 1.0, np.where(z["kind"] == 2, 0.5, 0.0)), np.full(len(pi), 0.25)]
    durs = rig.durations()
    out, per_part = {}, np.zeros(len(names))
    views = ",".join(f"rts{y}" for y in yaws)
    for an in anims:
        cap = act = tot = 0
        for t in np.linspace(0, durs[an], samples, endpoint=False):
            Q = pose_mesh(rig, z["P"], z["F"], z["part"], an, t)
            np.savez(work / "vis_tmp.npz", P=Q, F=z["F"], col=col)
            C.blender("views", work / "vis_tmp.npz", work / "vis_tmp", "--views", views, "--size", str(size),
                      "--cull", "0", "--flat", "1", "--centre", "0,0,6000", "--span", "16000", "--pitch", str(pitch))
            for y in yaws:
                a = np.asarray(Image.open(work / f"vis_tmp_rts{y}.png").convert("RGB")).astype(int)
                mech = np.abs(a[..., 2] - 137) < 8
                g = a[..., 1]
                cm = mech & (g > 230); am = mech & (g > 140) & (g <= 230)
                cap += cm.sum(); act += am.sum(); tot += mech.sum()
                lin = (a[..., 0][cm] / 255.0)
                lin = np.where(lin <= 0.04045, lin / 12.92, ((lin + 0.055) / 1.055) ** 2.4)
                r = np.round(lin * 32 - 1).astype(int)
                per_part += np.bincount(np.clip(r, 0, len(names) - 1), minlength=len(names))
        out[an] = (cap / max(tot, 1), act / max(tot, 1))
    return out, dict(zip(names, (per_part / max(per_part.sum(), 1)).round(3)))


# --- lowpoly: game mesh and UV atlas -----------------------------------------------------------------------------

def stage_lowpoly(cfg, work):
    import v3_mech as M
    z = np.load(work / "rest.npz")
    names = list(M.PARTS)
    pi = np.array([names.index(p) for p in z["part"]])
    T = z["P"][z["F"]]
    A = 0.5 * np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1)
    total = int(cfg.get("lowpoly", {}).get("faces", 45000))
    # budget per part by sculpt area share
    area = np.bincount(pi, weights=A * (z["kind"] != 2), minlength=len(names))
    budget = np.maximum(300, (total * area / area.sum()).astype(int))
    kind = z["kind"].copy()
    np.savez(work / "lp_in.npz", P=z["P"], F=z["F"], part=pi, kind=kind, budget_part=np.arange(len(names)), budget_faces=budget)
    lp = cfg.get("lowpoly", {})
    C.blender("lowpoly", work / "lp_in.npz", work / "low_geo.npz", "--uv", "none", log=work / "lowpoly.log")
    import subprocess
    py = cfg.get("xatlas_python", "/mnt/nvme1n1p1/mc2-rework/v3/venv/bin/python")
    r = subprocess.run([py, "-I", str(C.HERE / "v3_xatlas.py"), str(work / "low_geo.npz"), str(work / "low.npz"),
                        "--res", str(cfg.get("tex", 2048)), "--padding", str(lp.get("padding", 3)),
                        "--minor", str(lp.get("minor_scale", 0.5))], capture_output=True, text=True)
    print(r.stdout.strip()[-300:], r.stderr.strip()[-800:])
    if False:
      C.blender("lowpoly", work / "lp_in.npz", work / "low.npz", "--uv_angle", str(lp.get("uv_angle", 50)),
              "--minor_scale", str(lp.get("minor_scale", 0.5)), "--margin", str(lp.get("margin", 0.0025)),
              "--shape_method", lp.get("shape_method", "CONCAVE"), "--rotate_method", lp.get("rotate_method", "ANY"),
              log=work / "lowpoly.log")
    lo = np.load(work / "low.npz")
    uv = lo["uv"].reshape(-1, 3, 2)
    uvA = 0.5 * np.abs((uv[:, 1, 0] - uv[:, 0, 0]) * (uv[:, 2, 1] - uv[:, 0, 1]) - (uv[:, 2, 0] - uv[:, 0, 0]) * (uv[:, 1, 1] - uv[:, 0, 1]))
    T2 = lo["P"][lo["F"]] / 1000.0
    A2 = 0.5 * np.linalg.norm(np.cross(T2[:, 1] - T2[:, 0], T2[:, 2] - T2[:, 0]), axis=1)
    res = int(cfg.get("tex", 2048))
    m0 = lo["kind"] == 0
    dens = np.sqrt(uvA[m0].sum() * res * res / A2[m0].sum())
    print(f"lowpoly: {len(lo['F'])} faces; UV coverage {uvA.sum():.2f}; sculpt texel density {dens:.0f} px/m at {res}")


# --- bake -------------------------------------------------------------------------------------------------------

def stage_bake(cfg, work):
    b = cfg.get("bake", {})
    out = work / "bake"
    log = C.blender("bake", work / "low.npz", out, "--hi", work / "rest.npz", "--tex", str(cfg.get("tex", 2048)),
                    "--bevel", str(b.get("bevel_m", 0.035)), "--ao_dist", str(b.get("ao_dist_m", 1.2)),
                    "--ao_samples", str(b.get("ao_samples", 128)), "--cage", str(b.get("cage_m", 0.04)),
                    "--ray", str(b.get("ray_m", 0.15)), "--smooth_deg", str(b.get("smooth_deg", 33)),
                    log=work / "bake.log", timeout=14400)
    print("\n".join(l for l in log.splitlines() if l.startswith("BAKE")))


def stage_paint(cfg, work):
    import v3_paint
    v3_paint.stage_paint(cfg, work)


def lookdev_scheme(cfg, work, scheme_name="player_default", name=None, views="q34,front,q34b", size=900, extra=()):
    import shutil
    import v3_paint as VP
    from PIL import Image
    sch = json.loads((C.ROOT / "game/data/faction_paint.json").read_text())["schemes"][scheme_name]
    if isinstance(extra, dict):
        sch = {**sch, **extra}; extra = ()
    L = work / f"ld_{scheme_name}"; L.mkdir(exist_ok=True)
    VP.composite(work, sch, L / "albedo.png")
    shutil.copy(work / "tex/normal.png", L / "normal.png")
    name = name or f"ld_{scheme_name}"
    C.blender("lookdev", work / "low.npz", work / name, "--maps", L, "--shading", work / "bake/low_shading.npz",
              "--views", views, "--size", str(size), "--samples", "32", "--sun", "3.0", *extra, log=work / "ld.log")
    vs = views.split(",")
    ims = [Image.open(work / f"{name}_{v}.png").convert("RGB") for v in vs]
    sheet = Image.new("RGB", (size * len(ims), size))
    for i, im in enumerate(ims):
        sheet.paste(im, (i * size, 0))
    sheet.save(work / f"{name}_sheet.png")
    return work / f"{name}_sheet.png"


# --- write: the game model and its textures ----------------------------------------------------------------------

def build_glb(cfg, work, out_glb):
    """The original's node tree and 20 animations (v3 rest pivots, ground-fixed root keys) with one mesh per rigid
    part, in its joint's frame (rigid: 100 % on one bone, as the original's own parts), one material."""
    import copy
    import hd_rig as R
    import v3_mech as M
    z = np.load(work / "rest.npz")
    rig = Rig(cfg, work)
    gfix = ground_fix(rig, cfg, z["P"], z["F"], z["part"])
    low = np.load(work / "low.npz")
    sh = np.load(work / "bake/low_shading.npz")
    names = list(M.PARTS)
    g0 = rig.g
    g = {"asset": {"version": "2.0", "generator": "tools/art/v3/v3_mech.py"}, "scene": 0,
         "scenes": [copy.deepcopy(g0["scenes"][0])], "nodes": copy.deepcopy(g0["nodes"]),
         "accessors": [], "bufferViews": [], "meshes": [], "materials": [], "animations": []}
    for n in g["nodes"]:
        n.pop("mesh", None); n.pop("skin", None)
    w = R.GlbWriter(g, bytearray())
    # animations, from the rig's (ground-fixed) tracks, in the original's channel order
    for an0 in g0.get("animations", []):
        name = an0.get("name")
        tracks, dur = rig.an.anims[name]
        an = {"name": name, "channels": [], "samplers": []}
        for node, path, t, v, interp in tracks:
            si = len(an["samplers"])
            an["samplers"].append({"input": w.accessor(np.asarray(t, np.float32).reshape(-1), "SCALAR", minmax=True),
                                   "output": w.accessor(np.asarray(v, np.float32), {3: "VEC3", 4: "VEC4"}[v.shape[1]]),
                                   "interpolation": interp})
            an["channels"].append({"sampler": si, "target": {"node": int(node), "path": path}})
        g["animations"].append(an)
    g["materials"].append({"name": f"v3_{cfg.get('name', 'mech')}", "pbrMetallicRoughness": {"baseColorFactor": [0.6, 0.6, 0.6, 1],
                           "metallicFactor": 0.2, "roughnessFactor": 0.6}})
    W_rest = rig.W_rest
    nrm_c = sh["normal"].reshape(-1, 3, 3)
    uv_c = low["uv"].reshape(-1, 3, 2)
    tris_total = 0
    for k, part in enumerate(names):
        m = low["part"] == k
        if not m.any():
            continue
        j = rig.names.index(part)              # the part's own mesh node (a_*) rides its joint
        Minv = np.linalg.inv(W_rest[j])
        P = mm_to_gl_arr(low["P"][low["F"][m]].reshape(-1, 3))
        P = P @ Minv[:3, :3].T + Minv[:3, 3]
        Nn = mm_to_gl_arr(nrm_c[m].reshape(-1, 3) * 1000.0) @ Minv[:3, :3].T
        Nn /= np.linalg.norm(Nn, axis=1, keepdims=True) + 1e-12
        U = uv_c[m].reshape(-1, 2) * np.array([1.0, -1.0]) + np.array([0.0, 1.0])
        key = np.c_[np.round(P, 5), np.round(Nn, 4), np.round(U, 6)]
        _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
        P, Nn, U = P[first], Nn[first], U[first]
        I = inv.ravel().astype(np.uint32)
        attrs = {"POSITION": w.accessor(P.astype(np.float32), "VEC3", target=34962, minmax=True),
                 "NORMAL": w.accessor(Nn.astype(np.float32), "VEC3", target=34962),
                 "TEXCOORD_0": w.accessor(U.astype(np.float32), "VEC2", target=34962)}
        g["meshes"].append({"name": f"{part}_v3", "primitives": [{"attributes": attrs,
                            "indices": w.accessor(I, "SCALAR", comp=5125, target=34963), "material": 0}]})
        g["nodes"][j]["mesh"] = len(g["meshes"]) - 1
        tris_total += int(m.sum())
    w.write(str(out_glb))
    return {"tris": tris_total, "ground_fix_m": {k: round(v[0], 3) for k, v in gfix.items()}}


def mm_to_gl_arr(P):
    P = np.asarray(P, float) / 1000.0
    return np.c_[P[:, 0], P[:, 2], -P[:, 1]]


IMPORT_TEX = """[remap]

importer="texture"
type="CompressedTexture2D"

[params]

compress/mode=2
compress/high_quality=true
compress/lossy_quality=0.7
compress/uastc_level=0
compress/rdo_quality_loss=0.0
compress/hdr_compression=1
compress/normal_map={normal}
compress/channel_pack=0
mipmaps/generate=true
mipmaps/limit=-1
roughness/mode={rmode}
roughness/src_normal="{rsrc}"
process/channel_remap/red=0
process/channel_remap/green=1
process/channel_remap/blue=2
process/channel_remap/alpha=3
process/fix_alpha_border=false
process/premult_alpha=false
process/normal_map_invert_y=false
process/hdr_as_srgb=false
process/hdr_clamp_exposure=false
process/size_limit={limit}
detect_3d/compress_to=0
"""


def stage_write(cfg, work):
    """game/assets/v3/<folder>/<mech>.glb + textures (+ .import sidecars: BC7 / BC5, mipmaps, specular
    anti-aliasing from the normal map), <mech>.v3.json, <mech>.LICENSE.md."""
    import shutil
    from PIL import Image
    mech = cfg["name"]
    folder = cfg.get("folder", "mechs")
    dst = C.ROOT / "game/assets/v3" / folder
    dst.mkdir(parents=True, exist_ok=True)
    info = build_glb(cfg, work, dst / f"{mech}.glb")
    t = work / "tex"
    sizes = cfg.get("tex_sizes", {"albedo": 2048, "orm": 2048, "normal": 2048, "ids": 1024, "camo": 512})
    for k, sz in sizes.items():
        im = Image.open(t / f"{k}.png")
        if im.size[0] != sz:
            im = im.resize((sz, sz), Image.NEAREST if k == "ids" else Image.LANCZOS)
        im.save(dst / f"{mech}_{k}.png", optimize=True)
        imp = IMPORT_TEX.format(normal=1 if k == "normal" else 2 if k != "albedo" else 0,
                                rmode=2 if k == "orm" else 0,
                                rsrc=f"res://assets/v3/{folder}/{mech}_normal.png" if k == "orm" else "", limit=0)
        if k != "normal":
            imp = imp.replace("compress/normal_map=2", "compress/normal_map=0")
        (dst / f"{mech}_{k}.png.import").write_text(imp)
    stats = json.loads((t / "stats.json").read_text())
    side = {"model": f"{mech}.glb", "made_by": "tools/art/v3/v3_mech.py", "source": cfg["source"], "tris": info["tris"],
            "textures": sizes, "texel_density_px_per_m": cfg.get("_density"), "ground_fix_m": info["ground_fix_m"],
            "paint_stats": stats}
    (dst / f"{mech}.v3.json").write_text(json.dumps(side, indent=1))
    src = cfg["source"]
    (dst / f"{mech}.LICENSE.md").write_text(LICENSE.format(mech=mech, title=src["title"], author=src["author"],
                                                           url=src["url"], cfg=Path(cfg["_path"]).name))
    print(f"write: {dst / (mech + '.glb')} ({info['tris']} tris), textures {sizes}")


LICENSE = """# {mech}.glb (v3) — licence and attribution

The 3D mesh of this HD rework model (`{mech}.glb`) and its textures (`{mech}_albedo.png`, `{mech}_orm.png`,
`{mech}_normal.png`, `{mech}_ids.png`, `{mech}_camo.png`) are an adaptation of:

> **"{title}"** by **{author}**, {url}
> licensed under **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)**,
> https://creativecommons.org/licenses/by-nc-sa/4.0/

## Changes made

Made by `tools/art/v3/v3_mech.py` with the settings in `tools/art/v3/{cfg}` (Pipeline A, 2026-10-24): the printed
sculpt was scaled to game size; split into rigid parts on the kit's own part lines (crease-bounded panels);
re-posed part by part from the sculpt's pose into the MechCommander 2 rest pose; modelled joint actuators (drums and
balls) and flat decks added where parts meet; reduced to game density; given a new UV atlas; baked (normal, ambient
occlusion, edges) from the full-detail sculpt in Blender Cycles; and painted with a hand-authored zone mask and baked
wear (chips, grime, dust, soot). The textures are original work made from those bakes.

## Licence of this adaptation

This adaptation (mesh and textures) is licensed under **CC BY-NC-SA 4.0** (https://creativecommons.org/licenses/by-nc-sa/4.0/),
the licence of the original. The skeleton, joint names and animations in the same `.glb` are converted from
Microsoft's 2006 MechCommander 2 Shared Source release and remain under that release's licence
(`docs/MC2-SOURCE-EULA.md`); they are not covered by the Creative Commons licence.

This is an unofficial fan project. {author} has not endorsed it or this use of their model. The model is provided
as is, without warranties of any kind.
"""


# --- pose test ---------------------------------------------------------------------------------------------------

def stage_pose(cfg, work, samples=12, out_name="pose_test"):
    """Every animation, sampled `samples` times: per joint (parent/child part pair) the seam's separation (how far
    the rest-pose contact points move apart, mm), the new interpenetration (mm, contact points that end up inside
    the partner beyond what they were at rest) and, per animation, the share of the mech's pixels that show a
    closed-off part line (caps) from the RTS camera's pitch. Writes <work>/<out_name>.json and .md."""
    from scipy.spatial import cKDTree
    import pose_test as PT
    import v3_mech as M
    z = np.load(work / "low.npz")
    names = list(M.PARTS)
    P, F = z["P"], z["F"]
    part = np.array(names)[z["part"]]
    rest = np.load(work / "rest.npz")
    rig = Rig(cfg, work)
    ground_fix(rig, cfg, rest["P"], rest["F"], rest["part"])
    T = P[F]
    rng = np.random.default_rng(0)
    # area samples per part (sculpt and caps; actuators count as cover)
    def samples_of(m, n=6000):
        idx = np.flatnonzero(m)
        A = 0.5 * np.linalg.norm(np.cross(T[idx, 1] - T[idx, 0], T[idx, 2] - T[idx, 0]), axis=1)
        pick = rng.choice(idx, size=min(n, len(idx) * 4), p=A / A.sum())
        u = rng.random((len(pick), 2)); s = u.sum(1) > 1; u[s] = 1 - u[s]
        return T[pick, 0] + u[:, :1] * (T[pick, 1] - T[pick, 0]) + u[:, 1:] * (T[pick, 2] - T[pick, 0])
    pts = {p: samples_of(part == p) for p in names}
    pairs = []
    for jk, (pa, ch) in JOINTS.items():
        tb = cKDTree(pts[pa]); d, _ = tb.query(pts[ch], distance_upper_bound=60.0)
        seam = np.isfinite(d)
        if seam.sum() < 10:
            continue
        pairs.append((jk, pa, ch, pts[ch][seam], np.minimum(d[seam], 60.0)))
    res = {}
    durs = rig.durations()
    for an, dur in durs.items():
        ts = np.linspace(0, dur, samples if an in PT.LOCO else max(6, samples // 2))
        rows = {}
        for jk, pa, ch, q0, d0 in pairs:
            sep_max, sep95 = 0.0, 0.0
            for t in ts:
                Ms = rig.part_matrices(an, t)
                Mp, Mc = Ms[pa], Ms[ch]
                qp = pts[pa] @ Mp[:3, :3].T + Mp[:3, 3]
                qc = q0 @ Mc[:3, :3].T + Mc[:3, 3]
                d, _ = cKDTree(qp).query(qc)
                sep = np.maximum(d - d0, 0)
                sep_max = max(sep_max, float(sep.max())); sep95 = max(sep95, float(np.percentile(sep, 95)))
            rows[jk] = {"sep_p95_mm": round(sep95), "sep_max_mm": round(sep_max)}
        res[an] = rows
    vis, per_part = cap_visibility(cfg, work, anims=("Idle", "Walk", "Run", "Jump", "FallForward", "GetUpBack"),
                                   samples=6, rig=rig)
    out = {"joints": res, "cap_pixels": {k: round(v[0] * 100, 2) for k, v in vis.items()},
           "actuator_pixels": {k: round(v[1] * 100, 2) for k, v in vis.items()}, "cap_pixels_by_part": per_part,
           "note": "Parts are closed shells (caps, decks, actuators), so a seam never shows a hole into the model; sep is "
                   "how far a rest contact opens (it then shows the partner's cap or the joint actuator)."}
    (work / f"{out_name}.json").write_text(json.dumps(out, indent=1))
    jks = [p[0] for p in pairs]
    md = ["| animation | " + " | ".join(jks) + " | caps % px |", "|---" * (len(jks) + 2) + "|"]
    for an, rows in res.items():
        md.append(f"| {an} | " + " | ".join(f"{rows[j]['sep_p95_mm']}/{rows[j]['sep_max_mm']}" for j in jks) +
                  f" | {out['cap_pixels'].get(an, '')} |")
    (work / f"{out_name}.md").write_text("Seam separation p95/max (mm) per joint; caps = share of the mech's pixels showing a closed part line (RTS pitch, 6 yaws).\n\n" + "\n".join(md) + "\n")
    print("\n".join(md))


WEAPON_COLS = [(1.0, 0.0, 0.85), (0.1, 0.85, 1.0), (1.0, 0.55, 0.0), (0.2, 1.0, 0.25), (1.0, 1.0, 0.1), (0.6, 0.3, 1.0),
               (1.0, 0.25, 0.25), (0.0, 0.6, 0.45)]


def weapons_check(cfg, work, out=None, textured=None, size=700):
    """Standard review output: the sculpt grey with each weapon in its own highlight colour (and lenses white), in
    aligned front, 3/4, left side, right side and top views; a legend; optional textured renders beside it."""
    import v3_paint as VP
    from PIL import Image, ImageDraw
    wid, lens, rep = VP.weapon_faces(cfg, work)
    np.save(work / "weapon_faces.npy", wid)
    z = np.load(work / "sculpt.npz")
    col = np.full((len(z["F"]), 3), 0.62)
    for k in range(len(rep)):
        col[wid == k] = WEAPON_COLS[k % len(WEAPON_COLS)]
    col[lens] = (1, 1, 1)
    np.savez(work / "wc_col.npz", P=z["P"], F=z["F"], col=col)
    views = ["front", "q34", "side", "rside", "top"]
    names = {"front": "front", "q34": "3/4 front-left", "side": "left side (+X)", "rside": "right side (-X)", "top": "top (front down)"}
    C.blender("views", work / "wc_col.npz", work / "wc", "--views", ",".join(views), "--size", str(size))
    rows = 2 if textured else 1
    W_ = size * len(views)
    sheet = Image.new("RGB", (W_, size * rows + 40 + 26 * ((len(rep) + 2) // 3)), (22, 22, 26))
    d = ImageDraw.Draw(sheet)
    for i, v in enumerate(views):
        sheet.paste(Image.open(work / f"wc_{v}.png").convert("RGB"), (i * size, 0))
        d.text((i * size + 8, 8), names[v], fill=(255, 255, 255))
    if textured:
        for i, f in enumerate(textured[:len(views)]):
            im = Image.open(f).convert("RGB")
            s_ = min(size / im.width, size / im.height)
            im = im.resize((int(im.width * s_), int(im.height * s_)))
            sheet.paste(im, (i * size, size))
    y0 = size * rows + 10
    for k, r in enumerate(rep):
        x, y = (k % 3) * (W_ // 3) + 10, y0 + (k // 3) * 26
        d.rectangle([x, y, x + 18, y + 18], fill=tuple(int(c * 255) for c in WEAPON_COLS[k % len(WEAPON_COLS)]))
        d.text((x + 26, y + 3), f"{r['name']}  ({r['area_m2']} m2)", fill=(255, 255, 255))
    out = out or work / "weapons_check.png"
    sheet.save(out)
    return out, rep


def stage_weapons(cfg, work):
    """Weapon marking check (standard review output per mech): <work>/weapons_check.png."""
    out, rep = weapons_check(cfg, work)
    for r in rep:
        print(f"  weapon {r['name']}: {r['faces']} faces, {r['area_m2']} m2")
    if not rep:
        print("  no weapons configured: send aligned sheets (stage sheets) for outlines")


def stage_sheets(cfg, work):
    """Plain aligned sheets for Lee (weapons, canopy outlines in blue): <work>/sheets/sheet_<view>.png."""
    import v3_paint as VP
    out = VP.make_sheets(work, work / "sheets")
    print("  sheets:", out)


def stage_review(cfg, work):
    import v3_review
    v3_review.stage_review(cfg, work)


def fit_actuator(a, P, F, M_child, out_max=0.2, n=240):
    """Shrink an actuator (radius, and a drum's half length with it) until at most out_max of its surface stands
    outside the sculpt: the joint housing then reads as hardware inside the armour, not a ball stuck on it. Tested in
    the sculpt frame (the child part's inverse rest transform)."""
    rng = np.random.default_rng(1)
    Mi = np.linalg.inv(M_child)
    c = Mi[:3, :3] @ np.asarray(a["c"], float) + Mi[:3, 3]
    if a["kind"] == "cyl":
        ax = Mi[:3, :3] @ np.asarray(a["axis"], float); ax /= np.linalg.norm(ax)
        u = np.cross(ax, [0, 0, 1.0] if abs(ax[2]) < 0.9 else [1.0, 0, 0]); u /= np.linalg.norm(u); v = np.cross(ax, u)
    sub = np.arange(0, len(F), max(1, len(F) // 120000))
    Fs = F[sub] if len(F) > 120000 else F
    r0, h0 = float(a["r"]), float(a.get("half", 0))
    for scale in np.linspace(1.0, 0.3, 8):
        r = r0 * scale
        if a["kind"] == "sphere":
            d = rng.normal(size=(n, 3)); d /= np.linalg.norm(d, axis=1, keepdims=True)
            X = c + d * r
        else:
            h = h0 * (0.6 + 0.4 * scale)
            t = rng.uniform(-h, h, n); ang = rng.uniform(0, 2 * np.pi, n)
            X = c + np.outer(t, ax) + r * (np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v)
        out = 1 - (C.winding(P, F, X) > 0.5).mean()
        if out <= out_max:
            break
    a["r"] = r
    if a["kind"] == "cyl":
        a["half"] = h
    a["outside"] = round(float(out), 2)
    print(f"  actuator {a['joint']}: r {r0:.0f} -> {r:.0f} mm, {out * 100:.0f} % outside")


def canopy_check(cfg, work, out, size=700):
    """The canopy glass (blue) on the plain sculpt in aligned views, named: what Lee checks or re-outlines."""
    import v3_paint as VP
    from PIL import Image, ImageDraw
    z = np.load(work / "sculpt.npz")
    gl = VP.glass_faces_v3(cfg, work)
    col = np.full((len(z["F"]), 3), 0.72)
    if gl is not None:
        col[gl] = (0.1, 0.35, 1.0)
    np.savez(work / "cc_col.npz", P=z["P"], F=z["F"], col=col)
    views = ["front", "q34", "side", "top"]
    names = {"front": "front", "q34": "3/4 front-left", "side": "left side (+X)", "top": "top (front down)"}
    P = z["P"]
    c = P[gl.repeat(1)[:0]] if False else None
    C.blender("views", work / "cc_col.npz", work / "cc", "--views", ",".join(views), "--size", str(size))
    sheet = Image.new("RGB", (size * len(views), size + 30), (22, 22, 26)); d = ImageDraw.Draw(sheet)
    for i, v in enumerate(views):
        sheet.paste(Image.open(work / f"cc_{v}.png").convert("RGB"), (i * size, 30)); d.text((i * size + 8, 8), names[v], fill=(255, 255, 255))
    sheet.save(out)
    return int(gl.sum()) if gl is not None else 0
