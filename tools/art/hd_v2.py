#!/usr/bin/env python3
"""HD rework (v2, 2026-10-23): re-segment, articulate, unwrap, bake and paint a printable mech sculpt.

    python3 -I tools/art/hd_v2.py <mech> --stl SCULPT.stl --joints J.json [--steps fit,segment,bake,paint,write]
        [--work /mnt/nvme1n1p1/mc2-rework/work/<mech>] [--tex 2048] [--folder mechs]

Stages (each reads the previous stage's files in --work, so one stage can be rerun alone):
  fit      Runs tools/art/stl_rig.py's fit unchanged (orientation, scale, joints from J.json, MC2 skeleton with the
           sculpt's bone lengths, root drop, the rough per-triangle part labels) and keeps its state: fit.npz + skel.glb.
  segment  Re-cuts the watertight raw sculpt (not stl_rig's split triangles). Each joint's cut is a graph cut over
           the faces near the joint: the boundary prefers concave creases (where the kit's merged pieces meet) and
           stays near the joint, so it runs along the kit's own part lines instead of a plane through the armour.
           Each cut loop then gets (a) a sleeve: the loop extruded into the neighbouring part and narrowed, so a
           rotation shows a dark inner sleeve rather than a hole, (b) a cap, and (c) a ball actuator at the pivot,
           sized to stay inside the rest-pose shell. Parts are re-posed rigidly (stl_rig's leg rotations), normals
           are smoothed per part up to 35 degrees. Writes rest.npz.
  bake     Blender (headless bpy, tools/art/hd_v2_blender.py): Smart UV Project of every part into one atlas at a
           shared texel density, then Cycles bakes of ambient occlusion, a bevelled tangent normal map (rounded
           machined edges), object-space position and the part index. Writes uv.npz and bake_*.png.
  paint    Authors the zone mask in the new UVs from the parts, the bakes and the original's mask: base,
           highlight 1, highlight 2, bare metal, emissive and decals, with curvature from the normal map.
  write    <mech>.glb (the MC2 skeleton, hierarchy and animations, one rigidly skinned mesh), <mech>_mask.png,
           <mech>_bake.png, <mech>_normal.png and <mech>.rig.json (actuators, filler faces) into
           game/assets/v2/<folder>/, where the v2 loaders (ArtV2) find them.
"""
import argparse
import inspect
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix, csr_matrix
from scipy.sparse.csgraph import connected_components, maximum_flow
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hd_rig as R    # noqa: E402
import stl_rig as S   # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def joint_axes(glb):
    """Per joint: the dominant rotation axis of its animation (relative to its parent, rest world frame, game mm
    Z up), the share of the motion about it, and the largest angle. From every animation sampled 24 times."""
    import pose_test as PT
    from scipy.spatial.transform import Rotation as Rot
    g, b = R.load_glb(str(glb))
    an = PT.Animator(g, b)
    W0 = an.world()
    out = {}
    samples = {}
    for name, (tracks, dur) in an.anims.items():
        for t in np.linspace(0, dur, 24):
            W = an.world(name, t)
            for j, n in enumerate(g["nodes"]):
                if not n.get("name", "").startswith("joint_") or j not in an.parent:
                    continue
                pj = an.parent[j]
                rel_t = np.linalg.inv(W[pj]) @ W[j]
                rel_0 = np.linalg.inv(W0[pj]) @ W0[j]
                d = Rot.from_matrix(rel_t[:3, :3] @ np.linalg.inv(rel_0[:3, :3])).as_rotvec()  # in the parent frame
                samples.setdefault(n["name"], []).append(W0[pj][:3, :3] @ d)                 # rest world frame
    for nm, v in samples.items():
        v = np.array(v)
        mag = np.linalg.norm(v, axis=1)
        if mag.max() < np.radians(2):
            continue
        u, sv, vt = np.linalg.svd(v, full_matrices=False)
        ax = vt[0] / np.linalg.norm(vt[0])
        ax_mm = np.array([ax[0], -ax[2], ax[1]])   # glTF Y up -> Z up
        out[nm] = {"axis": ax_mm.tolist(), "share": float(sv[0] ** 2 / (sv ** 2).sum()),
                   "max_deg": float(np.degrees(mag.max())), "p95_deg": float(np.degrees(np.percentile(mag, 95)))}
    return out


# ---------------------------------------------------------------------------------------------------------- fit
def stage_fit(a, work):
    cap = {}

    def capture(og, ob, pos, normals, uv, owner, tris, slots, dest, mech):
        cap.update(inspect.currentframe().f_back.f_locals)
    orig_write = S.write
    S.write = capture
    argv = sys.argv
    sys.argv = ["stl_rig.py", a.mech, a.stl, "--joints", a.joints, "--folder", a.folder]
    try:
        S.main()
    finally:
        sys.argv = argv
        S.write = orig_write
    over = cap["over"]
    for k in ("turn", "yaw", "twist", "base_cut"):
        if over.get(k):
            raise SystemExit(f"hd_v2 fit: J.json '{k}' is not supported yet (the raw sculpt must map to stl_rig's frame by scale and offset)")
    T, nt = cap["T"], len(cap["T"])
    owner = np.asarray(cap["owner"])[:nt]
    og, ob, names = cap["og"], cap["ob"], cap["names"]
    # per node: rigid transform sculpt mm (Z up) -> rest game mm (Z up), as stl_rig's step 4
    shift = np.asarray(cap["shift"], float)
    xf = {}
    for node in set(owner.tolist()):
        M = np.eye(4); M[:3, 3] = shift
        x = cap["xform"].get(node)
        if x and x[0] == "rot":
            _, a0, a1, b0, b1 = x
            Rm = S.rot_between(a1 - a0, b1 - b0)
            M = np.eye(4); M[:3, :3] = Rm; M[:3, 3] = b0 - Rm @ a0
        elif x:
            M = np.eye(4); M[:3, 3] = x[2] - x[1]
        xf[int(node)] = M
    # pivots: every skinned part's joint, in the sculpt frame (legs: the sculpt's own joint points)
    W2 = R.world_matrices(og)
    parent = {c: i for i, n in enumerate(og["nodes"]) for c in n.get("children", [])}
    J, tgt, legs, KEYS = cap["J"], cap["tgt"], cap["legs"], cap["KEYS"]
    piv = {}
    for node in xf:
        jn = node if og["nodes"][node].get("name", "").startswith("joint_") else parent.get(node)  # the part's joint
        while jn is not None and not og["nodes"][jn].get("name", "").startswith("joint_"):
            jn = parent.get(jn)
        if jn is None:
            continue
        nm = og["nodes"][jn]["name"]
        pw = S.sc(W2[jn][:3, 3])
        sp = pw - shift
        for s in "lr":
            for i, kk in enumerate(KEYS):
                if legs[s][i] == nm:
                    sp = np.asarray(J[s][kk], float)
                    pw = np.asarray(tgt[s][kk], float)
            if legs[s][-1] == nm:
                sp = np.asarray(J[s]["ankle"], float); pw = np.asarray(tgt[s]["ankle"], float)
        piv[node] = {"joint": nm, "joint_index": int(jn), "sculpt": sp.tolist(), "game": pw.tolist()}
    # skeleton without the original meshes
    for n in og["nodes"]:
        n.pop("mesh", None)
    w = R.GlbWriter(og, ob)
    w.write(str(work / "skel.glb"))
    axes = joint_axes(work / "skel.glb")
    np.savez_compressed(work / "fit.npz", T=T, owner=owner, H=cap["H"])
    (work / "fit.json").write_text(json.dumps({
        "mech": a.mech, "stl": a.stl, "joints": a.joints, "H": float(cap["H"]), "nt": int(nt),
        "xform": {str(k): v.tolist() for k, v in xf.items()}, "pivots": {str(k): v for k, v in piv.items()},
        "node_names": [n.get("name", "") for n in og["nodes"]], "parent": {str(k): v for k, v in parent.items()},
        "axes": axes,
        "legs": {s: {"joints": list(legs[s]), "points": {kk: np.asarray(J[s][kk], float).tolist() for kk in KEYS}}
                 for s in "lr"}, "keys": list(KEYS),
    }, indent=1))
    print(f"fit: {nt} stl_rig tris, {len(xf)} parts -> {work}")


def stage_fitveh(a, work):
    """Rigid units (vehicles): tools/art/stl_hd.py's fit unchanged, except that the sculpt is not simplified, so the
    full-resolution kit (hi.npz) is the bake source; the game mesh is a Blender decimation of it (stage lowpoly)."""
    import stl_hd as SH
    cap = {}

    def capture(og, ob, pos, normals, uv, owner, tris, slots, dest, mech):
        cap.update(inspect.currentframe().f_back.f_locals)
        cap["owner_v"] = owner
    o_cluster, o_write = SH.cluster, S.write
    SH.cluster = lambda T, faces: (T, 0.0)
    S.write = capture
    argv = sys.argv
    sys.argv = ["stl_hd.py", a.mech, "--stl", a.stl, "--kind", a.folder, "--joints", a.joints]
    try:
        SH.main()
    finally:
        sys.argv = argv; SH.cluster, S.write = o_cluster, o_write
    Gf, owner, og, ob = cap["Gf"], cap["owner"], cap["og"], cap["ob"]
    Pmm = np.stack([Gf[..., 0], -Gf[..., 2], Gf[..., 1]], -1) * 1000.0   # glTF m -> mm Z up
    V, F = weld(Pmm, 2)
    np.savez_compressed(work / "hi.npz", P=V, F=F, part=np.asarray(owner, int))
    for n in og["nodes"]:
        n.pop("mesh", None)
    R.GlbWriter(og, ob).write(str(work / "skel.glb"))
    names = [n.get("name", "") for n in og["nodes"]]
    (work / "fit.json").write_text(json.dumps({"mech": a.mech, "stl": a.stl, "joints": a.joints, "kind": "rigid",
                                               "node_names": names, "H": float(V[:, 2].max())}, indent=1))
    print(f"fitveh: {len(F)} full-resolution tris, parts {sorted(set(names[o] for o in set(owner.tolist())))} -> {work}/hi.npz")


def stage_lowpoly(a, work):
    """Blender decimation (collapse, per part, so no triangle straddles two parts) of hi.npz to --faces triangles,
    smoothed corner normals -> rest.npz (the game mesh) + an empty actuator list."""
    faces = int(getattr(a, "faces", 0) or 24000)
    cmd = ["blender", "-b", "--factory-startup", "--python", str(ROOT / "tools/art/hd_v2_blender.py"), "--",
           "decimate", str(work / "hi.npz"), str(work / "lo.npz"), "--faces", str(faces)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not (work / "lo.npz").exists():
        raise SystemExit("decimate failed:\n" + r.stdout[-2000:] + r.stderr[-2000:])
    z = np.load(work / "lo.npz")
    P, F, part = z["P"], z["F"], z["part"]
    fit = json.loads((work / "fit.json").read_text())
    over = json.loads(Path(fit["joints"]).read_text()) if Path(fit["joints"]).exists() else {}
    N = corner_normals(P, F, part, float(over.get("v2", {}).get("smooth_deg", 35.0)))
    np.savez_compressed(work / "rest.npz", P=P, F=F, part=part, kind=np.zeros(len(F), int), N=N, P_sculpt=P)
    names = fit["node_names"]
    (work / "rest.json").write_text(json.dumps({"actuators": [], "joint_pairs": [], "contacts": [],
                                                "parts": sorted(set(part.tolist())),
                                                "part_names": {str(k): names[k] for k in set(part.tolist())}}, indent=1))
    print(f"lowpoly: {len(F)} tris -> {work}/rest.npz")


# ------------------------------------------------------------------------------------------------------ segment
def weld(T, dec=4):
    V, inv = np.unique(np.round(T.reshape(-1, 3), dec), axis=0, return_inverse=True)
    return V, inv.reshape(-1, 3)


def face_adjacency(F):
    """Edges shared by two faces: (fa, fb, va, vb) with va, vb the shared vertex pair."""
    E = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    fid = np.tile(np.arange(len(F)), 3)
    Es = np.sort(E, axis=1)
    order = np.lexsort((Es[:, 1], Es[:, 0]))
    Es, fid = Es[order], fid[order]
    same = (Es[1:] == Es[:-1]).all(1)
    i = np.flatnonzero(same)
    return fid[i], fid[i + 1], Es[i, 0], Es[i, 1]


def raw_in_fit_frame(stl, T_fit):
    """The raw sculpt's faces in stl_rig's frame (bounding-box match: stl_rig only scales, re-centres and splits)."""
    raw = S.load_stl(stl)
    raw[..., 2] -= raw[..., 2].min()
    a, b = raw.reshape(-1, 3), T_fit.reshape(-1, 3)
    k = np.ptp(b[:, 2]) / np.ptp(a[:, 2])
    off = b.min(0) - a.min(0) * k
    off[:2] = (b[:, :2].min(0) + b[:, :2].max(0)) / 2 - (a[:, :2].min(0) + a[:, :2].max(0)) / 2 * k
    out = raw * k + off
    err = np.abs(out.reshape(-1, 3).min(0) - b.min(0)).max() + np.abs(out.reshape(-1, 3).max(0) - b.max(0)).max()
    assert err < 5.0, f"raw sculpt does not map onto the fit frame ({err:.1f} mm)"
    return out


def graph_cut(nf, src_w, snk_w, ea, eb, ew, hard_src, hard_snk):
    """Min cut: source = parent, sink = child. Returns True where the face goes to the sink."""
    SCALE = 1000.0
    INF = int(1e9)
    s, t = nf, nf + 1
    rows = np.r_[ea, eb, np.full(nf, s), np.arange(nf)]
    cols = np.r_[eb, ea, np.arange(nf), np.full(nf, t)]
    cs = np.where(hard_src, INF, (src_w * SCALE).astype(np.int64))
    ct = np.where(hard_snk, INF, (snk_w * SCALE).astype(np.int64))
    caps = np.r_[(ew * SCALE).astype(np.int64) + 1, (ew * SCALE).astype(np.int64) + 1, cs, ct]
    G = csr_matrix((caps.astype(np.int32 if caps.max() < 2**31 else np.int64), (rows, cols)), shape=(nf + 2, nf + 2))
    G.sum_duplicates()
    flow = maximum_flow(G, s, t)
    res = G - flow.flow
    res.data[res.data < 0] = 0
    res.eliminate_zeros()
    # reachable from source in the residual graph = source side
    reach = np.zeros(nf + 2, bool); reach[s] = True
    frontier = [s]
    res = res.tocsr()
    while frontier:
        nxt = []
        for u in frontier:
            for v in res.indices[res.indptr[u]:res.indptr[u + 1]]:
                if not reach[v]:
                    reach[v] = True; nxt.append(v)
        frontier = nxt
    return ~reach[:nf]


def mincut_sink_side(nn, s_cap, t_cap, ea, eb, ecap):
    """Min s-t cut over nn nodes: s_cap[i] paid if i ends on the sink side, t_cap[i] if on the source side, ecap[k]
    if ea[k] is on the source side and eb[k] on the sink side. Returns True for sink-side nodes."""
    from scipy.sparse.csgraph import breadth_first_order
    SC = 1000.0
    s, t = nn, nn + 1
    rows = np.r_[np.full(nn, s), np.arange(nn), ea]
    cols = np.r_[np.arange(nn), np.full(nn, t), eb]
    cap = np.r_[s_cap, t_cap, ecap] * SC
    keep = cap > 0.5
    G = csr_matrix((np.round(cap[keep]).astype(np.int64).clip(1, 2**31 - 1).astype(np.int32), (rows[keep], cols[keep])),
                   shape=(nn + 2, nn + 2))
    G.sum_duplicates()
    fl = maximum_flow(G, s, t).flow
    res = (G - fl).tocsr()
    res.data[res.data <= 0] = 0
    res.eliminate_zeros()
    reach = np.zeros(nn + 2, bool)
    reach[breadth_first_order(res, s, directed=True, return_predecessors=False)] = True
    return ~reach[:nn]


def alpha_expansion(U, ea, eb, w, lab, sweeps=3):
    """Potts multi-label graph cut. U (nf, L) unary costs, edges (ea, eb) with weights w, lab initial labels
    (indices into U's columns). Returns the labels."""
    lab = lab.copy()
    L = U.shape[1]
    def energy(l_):
        return U[np.arange(len(l_)), l_].sum() + (w * (l_[ea] != l_[eb])).sum()
    e0 = energy(lab)
    for _ in range(sweeps):
        changed = False
        for al in range(L):
            lp, lq = lab[ea], lab[eb]
            A = w * (lp != lq); B = w * (lp != al); C = w * (al != lq); D = np.zeros_like(w)
            d0 = U[np.arange(len(lab)), lab].copy()      # x = 0: keep
            d1 = U[:, al].copy()                         # x = 1: switch to alpha
            np.add.at(d1, ea, np.maximum(C - A, 0)); np.add.at(d0, ea, np.maximum(A - C, 0))
            np.add.at(d1, eb, np.maximum(D - C, 0)); np.add.at(d0, eb, np.maximum(C - D, 0))
            pair = np.maximum(B + C - A - D, 0)
            x = mincut_sink_side(len(lab), d1, d0, ea, eb, pair)
            x &= lab != al
            if x.any():
                new = lab.copy(); new[x] = al
                e1 = energy(new)
                if e1 < e0 - 1e-9:
                    lab, e0, changed = new, e1, True
        if not changed:
            break
    return lab


def inside_test(P, tri):
    """True where P is inside the watertight triangle soup tri (nf, 3, 3): ray parity along three skew directions,
    majority vote (a ray grazing an edge miscounts once at most)."""
    P = np.atleast_2d(P)
    votes = np.zeros(len(P), int)
    v0, e1, e2 = tri[:, 0], tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    for d in (np.array([0.577, 0.611, 0.541]), np.array([-0.62, 0.33, 0.71]), np.array([0.21, -0.83, 0.52])):
        d = d / np.linalg.norm(d)
        pv = np.cross(d, e2); det = (e1 * pv).sum(1)
        ok = np.abs(det) > 1e-12
        inv = np.where(ok, 1.0 / np.where(ok, det, 1), 0)
        for i0 in range(0, len(P), 64):
            q = P[i0:i0 + 64]
            tv = q[:, None, :] - v0[None]
            u = (tv * pv[None]).sum(2) * inv
            qv = np.cross(tv, e1[None])
            v = (qv * d).sum(2) * inv
            t = (qv * e2[None]).sum(2) * inv
            hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 0)
            votes[i0:i0 + 64] += hit.sum(1) % 2
    return votes >= 2


def boundary_loops(F, mask):
    """Closed boundary loops (vertex index lists) of the faces in mask."""
    sub = F[mask]
    E = np.concatenate([sub[:, [0, 1]], sub[:, [1, 2]], sub[:, [2, 0]]])
    Es = np.sort(E, axis=1)
    u, inv, cnt = np.unique(Es, axis=0, return_inverse=True, return_counts=True)
    bd = E[cnt[inv.ravel()] == 1]  # directed boundary edges (face winding)
    nxt = {}
    for x, y in bd:
        nxt.setdefault(int(x), []).append(int(y))
    loops, used = [], set()
    for x0, y0 in bd:
        if (int(x0), int(y0)) in used:
            continue
        loop = [int(x0)]; cur = int(y0); used.add((int(x0), int(y0)))
        while cur != loop[0] and len(loop) < 100000:
            loop.append(cur)
            cand = [c for c in nxt.get(cur, []) if (cur, c) not in used]
            if not cand:
                break
            used.add((cur, cand[0])); cur = cand[0]
        if cur == loop[0] and len(loop) >= 3:
            loops.append(loop)
    return loops


def icosphere(r, sub=3):
    t = (1 + 5 ** 0.5) / 2
    V = [[-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0], [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t],
         [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1]]
    F = [[0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11], [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6],
         [7, 1, 8], [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9], [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1]]
    V = [np.array(v, float) / np.linalg.norm(v) for v in V]
    for _ in range(sub):
        mid = {}
        def m(i, j):
            key = (min(i, j), max(i, j))
            if key not in mid:
                p = V[i] + V[j]; V.append(p / np.linalg.norm(p)); mid[key] = len(V) - 1
            return mid[key]
        F = [f for a_, b_, c_ in F for f in ([a_, m(a_, b_), m(a_, c_)], [b_, m(b_, c_), m(a_, b_)], [c_, m(a_, c_), m(b_, c_)], [m(a_, b_), m(b_, c_), m(a_, c_)])]
    return np.array(V) * r, np.array(F)


def actuator_mesh(kind, c, ax, r, ln, sides=40):
    """Ball: an icosphere. Drum: a cylinder about ax with chamfered rims, a recessed hub and six bolt heads on each
    face, so a knee reads as a machined actuator. Triangles wound outward, (V, F)."""
    if kind == "ball":
        Vs, Fs = icosphere(r, 3)
        return Vs + c, Fs
    ax = ax / np.linalg.norm(ax)
    u = np.cross(ax, [0, 0, 1.0] if abs(ax[2]) < 0.9 else [1.0, 0, 0]); u /= np.linalg.norm(u)
    v = np.cross(ax, u)
    ang = np.linspace(0, 2 * np.pi, sides, endpoint=False)
    ring = lambda rad, x: c + ax * x + rad * (np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v)
    ch = min(0.12 * r, 0.25 * ln)
    h = ln / 2
    # profile from one face's centre to the other: (radius, along)
    prof = [(0.0, -h + 0.03 * r), (0.55 * r, -h + 0.03 * r), (0.6 * r, -h), (r - ch, -h), (r, -h + ch),
            (r, h - ch), (r - ch, h), (0.6 * r, h), (0.55 * r, h - 0.03 * r), (0.0, h - 0.03 * r)]
    Vl, Fl = [], []
    rings = []
    for rad, x in prof:
        if rad == 0.0:
            rings.append([len(Vl)]); Vl.append(c + ax * x)
        else:
            rings.append(list(range(len(Vl), len(Vl) + sides))); Vl.extend(ring(rad, x))
    for a_, b_ in zip(rings[:-1], rings[1:]):
        for i in range(sides):
            j = (i + 1) % sides
            if len(a_) == 1:
                Fl.append([a_[0], b_[j], b_[i]])
            elif len(b_) == 1:
                Fl.append([a_[i], a_[j], b_[0]])
            else:
                Fl += [[a_[i], a_[j], b_[j]], [a_[i], b_[j], b_[i]]]
    Vl, Fl = np.array(Vl), np.array(Fl)
    # bolts: small boxes on both faces
    for sgn in (-1, 1):
        for k in range(6):
            t = 2 * np.pi * (k + 0.5) / 6
            bc = c + ax * sgn * h + 0.78 * r * (np.cos(t) * u + np.sin(t) * v)
            bs = 0.06 * r
            Vb, Fb = icosphere(bs, 1)
            Vb = Vb * np.array([1.0, 1.0, 1.0])
            Fl = np.r_[Fl, Fb + len(Vl)]; Vl = np.r_[Vl, Vb + bc]
    # wind outward from the axis (or along it at the faces)
    n_ = np.cross(Vl[Fl[:, 1]] - Vl[Fl[:, 0]], Vl[Fl[:, 2]] - Vl[Fl[:, 0]])
    m_ = Vl[Fl].mean(1) - c
    al = m_ @ ax
    out = m_ - al[:, None] * ax
    out = np.where((np.linalg.norm(out, axis=1) < 0.58 * r)[:, None], al[:, None] * ax, out)
    flip = (n_ * out).sum(1) < 0
    Fl[flip] = Fl[flip][:, [0, 2, 1]]
    return Vl, Fl


def stage_segment(a, work):
    fit = json.loads((work / "fit.json").read_text())
    fz = np.load(work / "fit.npz")
    T_fit, own_fit, H = fz["T"], fz["owner"], float(fz["H"])
    names = fit["node_names"]
    parent = {int(k): v for k, v in fit["parent"].items()}
    xform = {int(k): np.array(v) for k, v in fit["xform"].items()}
    piv = {int(k): v for k, v in fit["pivots"].items()}
    over = json.loads(Path(fit["joints"]).read_text()) if fit.get("joints") and Path(fit["joints"]).exists() else {}
    v2 = over.get("v2", {})

    raw = raw_in_fit_frame(fit["stl"], T_fit)
    V, F = weld(raw)
    nf = len(F)
    C = V[F].mean(1)
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    farea = np.linalg.norm(fn, axis=1) / 2
    fn = fn / (np.linalg.norm(fn, axis=1, keepdims=True) + 1e-12)
    # initial labels: stl_rig's part of the nearest split triangle
    lab = own_fit[cKDTree(T_fit.mean(1)).query(C)[1]].astype(int)
    fa, fb, va, vb = face_adjacency(F)
    elen = np.linalg.norm(V[va] - V[vb], axis=1)
    # dihedral: concave if the neighbour's centroid lies in front of this face
    cosang = np.clip((fn[fa] * fn[fb]).sum(1), -1, 1)
    ang = np.arccos(cosang)
    concave = ((C[fb] - C[fa]) * fn[fa]).sum(1) > 0
    crease = np.where(concave, ang * 2.5, ang * 0.8)
    ew = elen * (0.04 + 0.96 * np.exp(-3.0 * crease))  # cheap to cut along creases, concave ones most of all

    # joints to re-cut: each part with a parent part, child side = the part under the joint
    # global relabel: crease-aware geodesic region growing. Seeds: the faces nearest each leg bone and the pelvis
    # line, and the cores of stl_rig's upper-body parts (faces well inside a region). Every face then joins the
    # seed it reaches most cheaply over the surface, where crossing a crease (a concave one most of all) is dear,
    # so fronts meet on the kit's part lines and an arm fused to a thigh stays an arm.
    from scipy.sparse.csgraph import dijkstra
    legs_ = fit.get("legs", {})
    seg_of = {}
    for s_, lg in legs_.items():
        pts = [np.asarray(lg["points"][kk], float) for kk in fit["keys"]]
        for k_, jn in enumerate(lg["joints"]):
            node_ = next((n for n, p in piv.items() if p["joint"] == jn), None)
            if node_ is None:
                continue
            a_ = pts[k_]
            b_ = pts[k_ + 1] if k_ + 1 < len(pts) else a_ * np.array([1, 1, 0.15])
            seg_of[node_] = (a_, b_)
    hips = [np.asarray(lg["points"]["hip"], float) for lg in legs_.values()]
    hip_node = next((n for n, p in piv.items() if p["joint"] == "joint_hip"), None)
    if hip_node is not None and len(hips) == 2:
        seg_of[hip_node] = (hips[0] * 0.75 + hips[1] * 0.25, hips[0] * 0.25 + hips[1] * 0.75)
    tree_c = cKDTree(C)
    seed = -np.ones(nf, int); seed_d = np.full(nf, np.inf)
    kseed = int(v2.get("seed_k", 25))
    for n_, (a_, b_) in seg_of.items():
        for t_ in np.linspace(0.15, 0.85, 12):
            q = a_ + t_ * (b_ - a_)
            d_, k_ = tree_c.query(q, k=kseed)
            better = d_ < seed_d[k_]
            seed[k_[better]] = n_; seed_d[k_[better]] = d_[better]
    upper = [n for n in set(lab.tolist()) if n not in seg_of]
    dif = lab[fa] != lab[fb]
    bfaces = np.unique(np.r_[fa[dif], fb[dif]])
    dist_b = cKDTree(C[bfaces]).query(C)[0]
    core = np.isin(lab, upper) & (dist_b > float(v2.get("core", 0.04)) * H)
    for n_ in upper:
        m_ = core & (lab == n_) & (seed < 0)
        seed[m_] = n_
    for n_, box in ((names.index(k), b) for k, b in v2.get("seed_boxes", {}).items()):
        for b in box:  # config: extra seeds, game-frame boxes in the sculpt frame [x0, y0, z0, x1, y1, z1]
            m_ = (C >= b[:3]).all(1) & (C <= b[3:]).all(1)
            seed[m_] = n_
    cost = elen * np.exp(float(v2.get("crease_cost", 2.0)) * crease)
    G = csr_matrix((np.r_[cost, cost], (np.r_[fa, fb], np.r_[fb, fa])), shape=(nf, nf))
    src = np.flatnonzero(seed >= 0)
    dist_, pred_, srcs = dijkstra(G, directed=False, indices=src, min_only=True, return_predecessors=True)
    newlab = np.where(srcs >= 0, seed[np.maximum(srcs, 0)], lab)
    moved = int((newlab != lab).sum())
    print(f"  geodesic regions: {len(src)} seed faces, {moved} faces relabelled")
    # refine: per-label geodesic distance as the data term, crease-weighted Potts smoothness (alpha-expansion), so a
    # thin strut that one front raced along is cut where it is cheapest instead of trailing a strand into a neighbour
    ids = np.array(sorted(set(newlab.tolist())))
    Dg = np.zeros((nf, len(ids)))
    for i, n_ in enumerate(ids):
        Dg[:, i] = dijkstra(G, directed=False, indices=np.flatnonzero(seed == n_), min_only=True)
    Dg[~np.isfinite(Dg)] = 1e3 * H
    sa = np.sqrt(farea) / np.sqrt(np.median(farea))
    U = sa[:, None] * Dg / (float(v2.get("geo_scale", 0.05)) * H)
    U = np.minimum(U, 50.0)
    wpair = float(v2.get("pair_weight", 1.0)) * ew / np.median(elen)
    li = np.searchsorted(ids, newlab)
    li = alpha_expansion(U, fa, fb, wpair, li, sweeps=2)
    lab2 = ids[li]
    print(f"  alpha-expansion refine: {int((lab2 != newlab).sum())} faces changed")
    lab = lab2
    # cuts: every pair of parts that share edges; the child is the deeper joint in the skeleton (siblings: the higher pivot)
    def jdepth(node):
        d, q = 0, piv[node]["joint_index"]
        while q in parent:
            q = parent[q]; d += 1
        return d
    diff = lab[fa] != lab[fb]
    pairs, cnt = np.unique(np.sort(np.c_[lab[fa][diff], lab[fb][diff]], 1), axis=0, return_counts=True)
    cuts = []
    for (x, y), c_ in zip(pairs, cnt):
        if c_ < 8 or x not in piv or y not in piv:
            continue
        kx, ky = (jdepth(x), piv[x]["sculpt"][2]), (jdepth(y), piv[y]["sculpt"][2])
        cuts.append((int(x), int(y)) if ky > kx else (int(y), int(x)))
    cuts.sort(key=lambda c_: jdepth(c_[1]))
    # a joint pair moves about the child's pivot (the parent part is the child's nearest part-owning ancestor joint,
    # or both hang from the same joint: hip and torso under joint_root); any other pair is a contact where the sculpt
    # fused two parts that move apart (an arm resting on a thigh): cut along the crease, cap, no sleeve or actuator
    jpart = {piv[n]["joint_index"]: n for n in piv}
    def anc_part(n):
        q = parent.get(piv[n]["joint_index"])
        while q is not None and q not in jpart:
            q = parent.get(q)
        return jpart.get(q)
    def is_joint(pp_, ch_):
        return anc_part(ch_) == pp_ or parent.get(piv[ch_]["joint_index"]) == parent.get(piv[pp_]["joint_index"])
    joint_pairs = {(p_, c_) for p_, c_ in cuts if is_joint(p_, c_)}
    print("  cuts: " + ", ".join(f"{names[p_]}|{names[c_]}" + ("" if (p_, c_) in joint_pairs else " (contact)") for p_, c_ in cuts))
    rho_default = 0.11 * H
    report = []
    for pp, node in (cuts if v2.get("joint_cuts", False) else []):
        p0 = np.asarray(piv[node]["sculpt"], float)
        child = lab == node
        nrm = C[child].mean(0) - p0
        if np.linalg.norm(nrm) < 1e-6:
            continue
        nrm /= np.linalg.norm(nrm)
        jo = v2.get("cuts", {}).get(names[node], {})
        rho = float(jo.get("radius", rho_default))
        region = ((lab == node) | (lab == pp)) & (np.linalg.norm(C - p0, axis=1) < rho)
        if region.sum() < 10:
            continue
        idx = np.flatnonzero(region)
        loc = -np.ones(nf, int); loc[idx] = np.arange(len(idx))
        inner = region[fa] & region[fb]
        ea, eb, ewr = loc[fa[inner]], loc[fb[inner]], ew[inner]
        # hard constraints: region faces touching outside faces keep that side
        border = (region[fa] ^ region[fb])
        hs = np.zeros(len(idx), bool); ht = np.zeros(len(idx), bool)
        for f_in, f_out in ((fa[border], fb[border]), (fb[border], fa[border])):
            ok = region[f_in]
            fi, fo = f_in[ok], f_out[ok]
            hs[loc[fi[lab[fo] != node]]] = True
            ht[loc[fi[lab[fo] == node]]] = True
        both = hs & ht
        hs[both] = False; ht[both] = False
        sd = (C[idx] - p0) @ nrm + float(jo.get("offset", 0.0))
        sig = float(jo.get("softness", 0.035 * H))
        pr = 1 / (1 + np.exp(-sd / sig))      # prior: 1 = child side
        if (pp, node) not in joint_pairs:      # contact: keep stl_rig's split, move it onto the crease
            pr = np.where(lab[idx] == node, 0.85, 0.15)
        uw = float(jo.get("prior", 0.6)) * np.sqrt(farea[idx]) * 2
        is_child = graph_cut(len(idx), uw * pr, uw * (1 - pr), ea, eb, ewr, hs, ht)
        before = lab[idx].copy()
        lab[idx] = np.where(is_child, node, pp)
        changed = int((lab[idx] != before).sum())
        report.append(f"  cut {names[pp]} | {names[node]}: {len(idx)} faces in reach {rho:.0f} mm, {changed} relabelled")
    # islands: every part's small disconnected pieces go to the neighbour they touch most
    for _ in range(2):
        same = lab[fa] == lab[fb]
        G = coo_matrix((np.ones(same.sum()), (fa[same], fb[same])), shape=(nf, nf))
        ncomp, comp = connected_components(G, directed=False)
        sizes = np.bincount(comp)
        small = np.flatnonzero(sizes[comp] < 150)
        if not len(small):
            break
        for cid in np.unique(comp[small]):
            fs = np.flatnonzero(comp == cid)
            nb_ = np.r_[fb[np.isin(fa, fs)], fa[np.isin(fb, fs)]]
            nb_ = nb_[lab[nb_] != lab[fs[0]]]
            if len(nb_):
                lab[fs] = np.bincount(lab[nb_]).argmax()
    print("\n".join(report))

    # ---- actuators: at each joint the limb's cross-section through the pivot is enclosed by a ball (multi-axis
    # joints) or a drum about the joint's dominant axis (hinges: knees, the launcher; share >= hinge_share). The
    # sculpt inside it is dropped, so any rotation shows actuator, never the cut. Sizes from the section, clamped.
    axes = fit.get("axes", {})
    actuators, act_geo = [], []
    drop = np.zeros(nf, bool)
    jcfg = v2.get("joints", {})
    for pp, node in sorted(joint_pairs, key=lambda c_: jdepth(c_[1])):
        jname = piv[node]["joint"]
        cfg = jcfg.get(jname, {})
        if cfg.get("skip"):
            continue
        p0 = np.asarray(cfg.get("centre", piv[node]["sculpt"]), float)
        M = xform[node]
        ax_info = axes.get(jname, {"axis": [1, 0, 0], "share": 0.0})
        ax = M[:3, :3].T @ np.asarray(ax_info["axis"], float); ax /= np.linalg.norm(ax)
        if "axis" in cfg:   # config: the joint's working axis (sculpt frame), where falls and get-ups blur the measured one
            ax = np.asarray(cfg["axis"], float); ax /= np.linalg.norm(ax)
        kind_ = cfg.get("type", "hinge" if ax_info["share"] >= float(v2.get("hinge_share", 0.9)) else "ball")
        child = (lab == node)
        if not child.any():
            continue
        nrm = C[child].mean(0) - p0
        nrm /= np.linalg.norm(nrm) + 1e-12
        if "normal" in cfg:
            nrm = np.asarray(cfg["normal"], float); nrm /= np.linalg.norm(nrm)
        both = ((lab == node) | (lab == pp)) & (np.linalg.norm(C - p0, axis=1) < float(cfg.get("search", 0.12)) * H)
        # section of those faces by the plane through the pivot
        Tq = V[F[both]]
        dq = (Tq - p0) @ nrm
        Q = []
        for i0, i1 in ((0, 1), (1, 2), (2, 0)):
            cr = (dq[:, i0] * dq[:, i1]) < 0
            tq = dq[cr, i0] / (dq[cr, i0] - dq[cr, i1])
            Q.append(Tq[cr, i0] + (Tq[cr, i1] - Tq[cr, i0]) * tq[:, None])
        Q = np.concatenate(Q) if Q else np.zeros((0, 3))
        if len(Q) < 6:
            print(f"  {jname}: no section through the pivot, no actuator")
            continue
        if not cfg.get("force") and not inside_test(p0[None], V[F])[0]:
            print(f"  {jname}: pivot outside the shell, no actuator")   # a ball there would hang in the air
            continue
        rel = Q - p0
        along = rel @ ax
        perp = np.linalg.norm(rel - along[:, None] * ax, axis=1)
        pct = float(cfg.get("percentile", v2.get("percentile", 65)))
        lo_, hi_ = float(v2.get("r_min", 0.025)) * H, float(cfg.get("r_max", v2.get("r_max", 0.055) * H))
        # the limb's outline around the pivot: in 24 directions in the section plane, the nearest section point
        e1 = np.cross(nrm, ax if abs(nrm @ ax) < 0.95 else [0.0, 0.0, 1.0]); e1 /= np.linalg.norm(e1)
        e2 = np.cross(nrm, e1)
        th = np.arctan2(rel @ e2, rel @ e1)
        sec = ((th + np.pi) / (2 * np.pi) * 24).astype(int) % 24
        dist3 = np.linalg.norm(rel, axis=1)
        nearest = np.array([dist3[sec == k_].min() if (sec == k_).any() else np.nan for k_ in range(24)])
        idx_near = np.array([np.flatnonzero(sec == k_)[dist3[sec == k_].argmin()] for k_ in range(24) if (sec == k_).any()])
        rel, along, perp = rel[idx_near], along[idx_near], perp[idx_near]
        if kind_ == "ball":
            r = float(np.clip(np.percentile(np.linalg.norm(rel, axis=1), pct) * 1.03, lo_, hi_))
            ln = 0.0
        else:
            r = float(np.clip(np.percentile(perp, pct) * 1.03, lo_, hi_))
            ln = float(max(2 * np.percentile(np.abs(along), 80), 0.6 * r))
        r = float(cfg.get("radius", r)); ln = float(cfg.get("length", ln))
        # an actuator may show at the joint, but not stand out of the body: shrink it until at most `protrude` of
        # its surface lies outside the rest-pose shell
        maxout = float(cfg.get("protrude", v2.get("protrude", 0.2)))
        for _ in range(14):
            Vt, _ = actuator_mesh(kind_, p0, ax, r, ln, sides=16) if kind_ != "ball" else (icosphere(r, 2)[0] + p0, None)
            Vt = Vt[::max(1, len(Vt) // 300)]
            if 1 - inside_test(Vt, V[F]).mean() <= maxout:
                break
            r *= 0.9; ln *= 0.95
        if r < lo_ * 0.6:
            print(f"  {jname}: actuator would stand out of the body at any size, none")
            continue
        if kind_ == "ball":
            inside = np.linalg.norm(C - p0, axis=1) < r * 0.97
        else:
            rc = C - p0
            al_c = rc @ ax
            pe_c = np.linalg.norm(rc - al_c[:, None] * ax, axis=1)
            inside = (pe_c < r * 0.97) & (np.abs(al_c) < ln / 2 * 0.97)
        drop |= inside & ((lab == node) | (lab == pp) | bool(cfg.get("drop_any", False)))
        if cfg.get("relabel"):   # config: next to the actuator the plane through the pivot splits the pair, so the seam
            # meets the actuator instead of running off across the armour (a twist joint's waist)
            band = float(cfg.get("relabel_band", 0.6)) * max(r, ln / 2)
            rc = C - p0
            near_ = ((lab == node) | (lab == pp)) & ~inside & (np.abs(rc @ nrm) < band) & \
                    (np.linalg.norm(rc - (rc @ ax)[:, None] * ax, axis=1) < float(cfg.get("relabel_radius", 1.8)) * r)
            lab[near_] = np.where((rc[near_] @ nrm) > 0, node, pp)
            print(f"  {jname}: {int(near_.sum())} faces beside the actuator split by the pivot plane")
        actuators.append({"node": jname, "part": names[node], "parent": names[pp], "kind": kind_, "radius_mm": r,
                          "length_mm": ln, "centre_sculpt": p0.tolist(), "axis_sculpt": ax.tolist(),
                          "share": ax_info.get("share", 0.0)})
        act_geo.append((node, kind_, p0, ax, r, ln))
        print(f"  {jname}: {kind_} r {r:.0f} mm" + (f" length {ln:.0f} mm" if kind_ != "ball" else "") +
              f", {int((inside & ((lab == node) | (lab == pp))).sum())} faces inside dropped")
    keepf = ~drop
    out_P, out_F, out_part, out_kind = [], [], [], []
    nv = 0
    for node in sorted(set(lab[keepf].tolist())):
        m = (lab == node) & keepf
        used = np.unique(F[m].ravel())
        remap = -np.ones(len(V), int); remap[used] = np.arange(len(used)) + nv
        out_P.append(V[used]); out_F.append(remap[F[m]]); out_part.append(np.full(m.sum(), node)); out_kind.append(np.zeros(m.sum(), int))
        nv += len(used)
    for node, kind_, p0, ax, r, ln in act_geo:
        Vs, Fs = actuator_mesh(kind_, p0, ax, r * 0.985, ln)
        out_P.append(Vs); out_F.append(Fs + nv); nv += len(Vs)
        out_part.append(np.full(len(Fs), node)); out_kind.append(np.full(len(Fs), 3))
    P = np.concatenate(out_P); Fo = np.concatenate(out_F); part = np.concatenate(out_part); kind = np.concatenate(out_kind)
    # re-pose rigidly into the rest pose (game mm, Z up)
    vpart = np.zeros(len(P), int); vpart[Fo.ravel()] = np.repeat(part, 3)
    Pr = P.copy()
    for node, M in xform.items():
        sel = vpart == node
        Pr[sel] = P[sel] @ M[:3, :3].T + M[:3, 3]
    for act in actuators:
        node = next(k for k, v in piv.items() if names[k] == act["part"])
        M = xform[node]
        act["centre_game"] = (M[:3, :3] @ np.asarray(act["centre_sculpt"]) + M[:3, 3]).tolist()
        act["axis_game"] = (M[:3, :3] @ np.asarray(act["axis_sculpt"])).tolist()
    # normals: smooth across edges up to 35 degrees within a part, hard elsewhere (per-corner)
    N = corner_normals(Pr, Fo, part, float(v2.get("smooth_deg", 35.0)))
    np.savez_compressed(work / "rest.npz", P=Pr, F=Fo, part=part, kind=kind, N=N, P_sculpt=P)
    (work / "rest.json").write_text(json.dumps({"actuators": actuators, "joint_pairs": [[names[p_], names[c_]] for p_, c_ in sorted(joint_pairs)],
                                                "contacts": [[names[p_], names[c_]] for p_, c_ in cuts if (p_, c_) not in joint_pairs], "parts": sorted(set(part.tolist())),
                                                "part_names": {str(k): names[k] for k in set(part.tolist())}}, indent=1))
    print(f"segment: {len(Fo)} tris ({(kind == 0).sum()} sculpt, {(kind == 1).sum()} cap, {(kind == 2).sum()} sleeve, "
          f"{(kind == 3).sum()} actuator), {len(actuators)} actuators -> {work}/rest.npz")


def corner_normals(P, F, part, deg):
    """Per-corner normals (len(F), 3, 3): area-weighted average of faces around each vertex position whose normal is
    within deg of this face's and that belong to the same part."""
    fn = np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]])
    fa = np.linalg.norm(fn, axis=1, keepdims=True)
    fu = fn / (fa + 1e-12)
    key = np.unique(np.round(P, 2), axis=0, return_inverse=True)[1].ravel()
    corner_key = key[F]                                    # (nf, 3)
    cos_t = np.cos(np.radians(deg))
    order = np.argsort(corner_key.ravel(), kind="stable")
    ck = corner_key.ravel()[order]
    cf = np.repeat(np.arange(len(F)), 3)[order]
    starts = np.r_[0, np.flatnonzero(np.diff(ck)) + 1, len(ck)]
    out = np.zeros((len(F) * 3, 3))
    flat_idx = order
    for s, e in zip(starts[:-1], starts[1:]):
        fs = cf[s:e]
        if e - s == 1:
            out[flat_idx[s]] = fu[fs[0]]; continue
        U = fu[fs]; A = fa[fs, 0]; pt = part[fs]
        sim = (U @ U.T > cos_t) & (pt[:, None] == pt[None, :])
        acc = sim.astype(float) @ (U * A[:, None])
        acc /= np.linalg.norm(acc, axis=1, keepdims=True) + 1e-12
        out[flat_idx[s:e]] = acc
    return out.reshape(len(F), 3, 3)


# --------------------------------------------------------------------------------------------------------- bake
def stage_bake(a, work):
    cmd = ["blender", "-b", "--factory-startup", "--python", str(ROOT / "tools/art/hd_v2_blender.py"), "--",
           "bake", str(work / "rest.npz"), str(work), "--tex", str(a.tex), "--samples", str(getattr(a, "samples", 64))]
    fit = json.loads((work / "fit.json").read_text())
    over = json.loads(Path(fit["joints"]).read_text()) if Path(fit.get("joints", "")).exists() else {}
    if (work / "hi.npz").exists() and over.get("v2", {}).get("bake_from_hi"):
        cmd += ["--hi", str(work / "hi.npz")]   # bake AO and normals from the full-resolution sculpt (a coarse game mesh)
    log = work / "bake.log"
    with open(log, "w") as f:
        r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
    tail = log.read_text().splitlines()[-5:]
    if r.returncode != 0 or not (work / "bake_normal.png").exists():
        raise SystemExit("bake failed:\n" + "\n".join(tail))
    print("bake:", " | ".join(t for t in tail if "BAKED" in t or "UV" in t))


# -------------------------------------------------------------------------------------------------------- paint
ZONES = ("base", "hl1", "hl2", "bare", "dark", "glass")


def classify_original(rgb):
    """Original MC2 paint-mask colours -> zone index: pure red/green/blue are the team channels (hl1, hl2, base);
    greys are bare metal, near-black is dark metal, saturated cyan/teal is glass, other colours stay base."""
    r, g, b = (rgb[..., i].astype(int) for i in range(3))
    z = np.zeros(rgb.shape[:-1], int)
    mx, mn = np.maximum(np.maximum(r, g), b), np.minimum(np.minimum(r, g), b)
    z[(g == 0) & (b == 0) & (r > 0)] = 1
    z[(r == 0) & (b == 0) & (g > 0)] = 2
    grey = (mx - mn < 40) & (mx > 60)
    z[grey] = 3
    z[mx < 45] = 4
    z[(b > 120) & (g > 120) & (r < 90)] = 5
    z[(r == 0) & (g == 0) & (b > 0)] = 0
    return z


def panels(P, F, part, deg=25.0):
    """Faces joined across edges flatter than deg (within one part): the sculpt's armour panels."""
    key = np.unique(np.round(P, 1), axis=0, return_inverse=True)[1].ravel()
    Fk = key[F]
    fa, fb, _, _ = face_adjacency(Fk)
    n = np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    ok = (part[fa] == part[fb]) & ((n[fa] * n[fb]).sum(1) > np.cos(np.radians(deg)))
    G = coo_matrix((np.ones(ok.sum()), (fa[ok], fb[ok])), shape=(len(F), len(F)))
    return connected_components(G, directed=False)[1]


def dilate(img, cover, n=8):
    """Grow covered texels into the gutters so mipmaps don't bleed (img (H, W, C))."""
    from scipy.ndimage import distance_transform_edt
    idx = distance_transform_edt(~cover, return_distances=False, return_indices=True)
    out = img[idx[0], idx[1]]
    return out


def stamp_text(text, w_m, h_m, ppm=400):
    from PIL import Image, ImageDraw, ImageFont
    W_, H_ = int(w_m * ppm), int(h_m * ppm)
    im = Image.new("L", (W_, H_), 0)
    d = ImageDraw.Draw(im)
    font = None
    for fp in (ROOT / "game/assets/fonts/chakra_petch/ChakraPetch-Bold.ttf",):
        if fp.exists():
            font = ImageFont.truetype(str(fp), int(H_ * 0.9))
    font = font or ImageFont.load_default()
    bb = d.textbbox((0, 0), text, font=font)
    d.text(((W_ - (bb[2] - bb[0])) / 2 - bb[0], (H_ - (bb[3] - bb[1])) / 2 - bb[1]), text, fill=255, font=font)
    return np.asarray(im, float) / 255.0


def stage_paint(a, work):
    from PIL import Image
    from scipy.ndimage import gaussian_filter
    fit = json.loads((work / "fit.json").read_text())
    over = json.loads(Path(fit["joints"]).read_text()) if Path(fit["joints"]).exists() else {}
    v2 = over.get("v2", {})
    names = fit["node_names"]
    z = np.load(work / "rest.npz")
    P, F, part, kind = z["P"], z["F"], z["part"], z["kind"]
    pos = np.load(work / "bake_pos.npy").astype(float) * 1000.0     # game mm, Z up
    fid = np.load(work / "bake_fid.npy")
    cover = np.load(work / "bake_cover.npy")
    nrm_os = np.load(work / "bake_nrm.npy").astype(float)
    res = cover.shape[0]
    fid = np.where(cover, np.clip(fid, 0, len(F) - 1), -1)
    # 1. guide: the original's mask, per part by bounding-box mapping onto the original's same-named part
    og, ob = R.load_glb(str(ROOT / f"game/assets/{a.folder}/{a.mech}.glb"))
    spts, suv, sown = R.original_samples(og, ob, per_tri=24)
    spts_mm = np.c_[spts[:, 0], -spts[:, 2], spts[:, 1]] * 1000.0
    tex = np.asarray(Image.open(ROOT / f"game/assets/{a.folder}/{a.mech}_0.png").convert("RGB"))
    th, tw = tex.shape[:2]
    scol = tex[np.clip((suv[:, 1] * th).astype(int), 0, th - 1), np.clip((suv[:, 0] * tw).astype(int), 0, tw - 1)]
    szone = classify_original(scol)
    oname = np.array([og["nodes"][i].get("name", "") for i in sown])
    tz = np.full((res, res), -1)
    ys, xs = np.nonzero(cover)
    tpart = part[fid[ys, xs]]
    for pn in np.unique(tpart):
        nm = names[pn]
        sm = oname == nm
        if not sm.any():
            continue
        vsel = np.unique(F[(part == pn) & (kind == 0)].ravel())
        if not len(vsel):
            continue
        lo_v, hi_v = P[vsel].min(0), P[vsel].max(0)
        lo_o, hi_o = spts_mm[sm].min(0), spts_mm[sm].max(0)
        m = tpart == pn
        q = pos[ys[m], xs[m]]
        # mechs: the sculpt's part is mapped onto the original part's bounds (proportions differ);
        # rigid units are already fitted onto the original (stl_hd), so their texels look up directly
        qn = q if fit.get("kind") == "rigid" else lo_o + (q - lo_v) / np.maximum(hi_v - lo_v, 1) * (hi_o - lo_o)
        _, k = cKDTree(spts_mm[sm]).query(qn)
        tz[ys[m], xs[m]] = szone[sm][k]
    # 2. per face, then per panel: area-weighted majority, so zone edges follow the sculpt's own panel lines
    nz = len(ZONES)
    fz = np.zeros((len(F), nz))
    ok = tz >= 0
    np.add.at(fz, (fid[ok], tz[ok]), 1.0)
    pid = panels(P, F, part, float(v2.get("panel_deg", 25)))
    pz = np.zeros((pid.max() + 1, nz))
    np.add.at(pz, pid, fz)
    zone_f = pz[pid].argmax(1)
    zone_f[pz[pid].sum(1) == 0] = 0
    # rules: actuators bare steel; soles dark
    zone_f[kind == 3] = 4   # actuators: dark gunmetal (bright steel balls read as chrome toys)
    fn = np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]])
    fn /= np.linalg.norm(fn, axis=1, keepdims=True) + 1e-12
    cz = P[F].mean(1)[:, 2]
    zone_f[(fn[:, 2] < -0.7) & (cz < 0.04 * P[:, 2].max())] = 4
    for rule in v2.get("paint", []):   # config: [{"part": name, "zone": "hl1", "min": [..], "max": [..]}]
        m = np.ones(len(F), bool)
        if "part" in rule:
            m &= part == names.index(rule["part"])
        if "min" in rule:
            m &= (P[F].mean(1) >= rule["min"]).all(1)
        if "max" in rule:
            m &= (P[F].mean(1) <= rule["max"]).all(1)
        zone_f[m] = ZONES.index(rule["zone"])
    share = np.bincount(zone_f, minlength=nz) / len(zone_f)
    print("paint: zone share " + ", ".join(f"{ZONES[i]} {share[i]:.2f}" for i in range(nz)))
    zt = np.where(cover, zone_f[np.maximum(fid, 0)], 0)
    mask = np.zeros((res, res, 4), np.uint8)
    mask[..., 0] = np.where(zt == 1, 255, 0)
    mask[..., 1] = np.where(zt == 2, 255, 0)
    mask[..., 2] = np.where(zt == 3, 255, np.where(zt == 4, 110, np.where(zt == 5, 60, 0)))
    mask[..., 3] = np.where(zt == 5, 255, 0)
    # 3. decals: a unit number on the biggest flat panels facing out of the torso sides and the shins' fronts
    decal = np.zeros((res, res))
    parea = np.zeros(pid.max() + 1)
    farea = np.linalg.norm(np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]]), axis=1) / 2
    np.add.at(parea, pid, farea)
    pnrm = np.zeros((pid.max() + 1, 3)); np.add.at(pnrm, pid, fn * farea[:, None])
    pnrm /= np.linalg.norm(pnrm, axis=1, keepdims=True) + 1e-12
    pzone = zone_f[np.unique(pid, return_index=True)[1]] if False else np.array([0])
    spots = v2.get("decals", [{"part": "bw_torso", "dir": [1, 0, 0], "text": "07", "h": 0.42},
                              {"part": "bw_torso", "dir": [-1, 0, 0], "text": "07", "h": 0.42},
                              {"part": "bw_llleg", "dir": [0, -1, 0], "text": "07", "h": 0.32},
                              {"part": "bw_rlleg", "dir": [0, -1, 0], "text": "07", "h": 0.32}])
    used = []
    for sp in spots:
        if sp["part"] not in names:
            continue
        pn = names.index(sp["part"])
        d = np.asarray(sp["dir"], float)
        cand = [k for k in np.unique(pid[(part == pn) & (kind == 0)]) if pnrm[k] @ d > 0.8 and k not in used]
        if not cand:
            continue
        k = max(cand, key=lambda k_: parea[k_])
        used.append(k)
        fs = np.flatnonzero(pid == k)
        c = (P[F[fs]].mean(1) * farea[fs, None]).sum(0) / farea[fs].sum()
        n_ = pnrm[k]
        up = np.array([0, 0, 1.0]) - n_[2] * n_; up /= np.linalg.norm(up) + 1e-12
        rt = np.cross(up, n_)
        hm = sp.get("h", 0.4); wm = hm * 0.62 * len(sp["text"])
        img = stamp_text(sp["text"], wm, hm)
        sel = cover & np.isin(fid, fs)
        q = pos[sel] - c
        u_ = (q @ rt) / 1000.0 / wm + 0.5
        v_ = 0.5 - (q @ up) / 1000.0 / hm
        inb = (u_ >= 0) & (u_ < 1) & (v_ >= 0) & (v_ < 1)
        val = np.zeros(len(u_))
        val[inb] = img[(v_[inb] * img.shape[0]).astype(int), (u_[inb] * img.shape[1]).astype(int)]
        dv = decal[sel]; decal[sel] = np.maximum(dv, val)
        print(f"  decal '{sp['text']}' on {sp['part']} panel {k} ({parea[k] / 1e6:.2f} m2)")
    # 4. curvature from the bevelled normal map: divergence of its tangent-plane tilt (convex edges > 0.5)
    nb = np.asarray(Image.open(work / "bake_normal.png").convert("RGB"), float) / 127.5 - 1.0
    if (work / "bake_normal_true.png").exists():   # sculpt = game mesh: keep only the bevel's rounding
        ntr = np.asarray(Image.open(work / "bake_normal_true.png").convert("RGB"), float) / 127.5 - 1.0
        nm_ = np.dstack([nb[..., :2] - ntr[..., :2], np.ones(nb.shape[:2])])
    else:                                          # baked from the full-resolution sculpt: all of it is detail
        nm_ = np.dstack([nb[..., :2], np.ones(nb.shape[:2])])
    nm_[..., :2] = np.clip(nm_[..., :2] * float(v2.get("bevel_gain", 1.0)), -0.8, 0.8)
    nm_ /= np.linalg.norm(nm_, axis=2, keepdims=True)
    nmap_img = ((nm_ * 0.5 + 0.5) * 255).astype(np.uint8)
    nx, ny = nm_[..., 0], -nm_[..., 1]       # image rows run down, tangent v runs up
    div = np.gradient(nx, axis=1) + np.gradient(ny, axis=0)
    inner = cover & np.roll(cover, 1, 0) & np.roll(cover, -1, 0) & np.roll(cover, 1, 1) & np.roll(cover, -1, 1)
    div = np.where(inner, div, 0.0)
    div = gaussian_filter(div, 0.8)
    curv = np.clip(0.5 + div * float(v2.get("curv_gain", 6.0)), 0, 1)
    ao = np.asarray(Image.open(work / "bake_ao.png").convert("L"), float) / 255.0
    detail = np.zeros((res, res, 4), np.uint8)
    detail[..., 0] = (ao * 255).astype(np.uint8)
    detail[..., 1] = (curv * 255).astype(np.uint8)
    detail[..., 2] = (np.clip(decal, 0, 1) * 255).astype(np.uint8)
    detail[..., 3] = 255
    mask = dilate(mask, cover)
    detail = dilate(detail, cover)
    nmap = dilate(nmap_img, cover)
    Image.fromarray(mask, "RGBA").save(work / "mask.png", optimize=True)
    Image.fromarray(detail, "RGBA").save(work / "detail.png", optimize=True)
    Image.fromarray(nmap, "RGB").save(work / "normal.png", optimize=True)
    # 5. a preview albedo (review paint) for viewers that don't run the game's shader
    team = np.array([[0.45, 0.47, 0.42], [0.62, 0.18, 0.12], [0.85, 0.7, 0.2], [0.55, 0.56, 0.58], [0.16, 0.16, 0.17], [0.2, 0.5, 0.6]])
    alb = team[zt] * (0.35 + 0.65 * ao[..., None])
    alb = np.where(decal[..., None] > 0.5, 0.85, alb)
    Image.fromarray(dilate((np.clip(alb, 0, 1) * 255).astype(np.uint8), cover)).save(work / "preview_albedo.png")
    print(f"paint: mask.png detail.png normal.png preview_albedo.png ({res} px) -> {work}")


# -------------------------------------------------------------------------------------------------------- write
def to_gl(P_mm):
    P = np.asarray(P_mm, float) / 1000.0
    return np.c_[P[..., 0], P[..., 2], -P[..., 1]] if P.ndim == 2 else np.stack([P[..., 0], P[..., 2], -P[..., 1]], -1)


def build_glb(work, out_glb, uv_corner=None, textures=None, folder="mechs"):
    """skel.glb + rest.npz (+ per-corner UVs) -> one rigidly skinned mesh 'hd_body' with the MC2 skeleton and
    animations, plus <out>.rig.json for the pose test and the game (actuators, filler face range)."""
    g, b = R.load_glb(str(work / "skel.glb"))
    z = np.load(work / "rest.npz")
    rest = json.loads((work / "rest.json").read_text())
    P, F, part, kind, N = z["P"], z["F"], z["part"], z["kind"], z["N"]
    order = np.argsort(kind, kind="stable")          # sculpt first, fillers (caps, actuators) last
    F, part, kind, N = F[order], part[order], kind[order], N[order]
    if uv_corner is not None:
        uv_corner = uv_corner.reshape(-1, 3, 2)[order]
    nf = len(F)
    pos = to_gl(P[F].reshape(-1, 3))
    nrm = to_gl(N.reshape(-1, 3) * 1000.0)
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
    uv = uv_corner.reshape(-1, 2) * np.array([1.0, -1.0]) + np.array([0.0, 1.0]) if uv_corner is not None else np.zeros((nf * 3, 2))
    own = np.repeat(part, 3)
    key = np.c_[np.round(pos, 5), np.round(nrm, 3), np.round(uv, 5), own]
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.ravel()
    pos, nrm, uv, own = pos[first], nrm[first], uv[first], own[first]
    tris = inv.reshape(-1, 3)
    # every original part node stays a joint even if it owns no triangles now (the launcher merged into the
    # torso): MechStage frames a model by its bones, and a missing top bone crops the lab's view
    fitj = json.loads((work / "fit.json").read_text())
    extra = {int(k) for k in fitj.get("xform", {})}
    joints = sorted(set(own.tolist()) | extra)
    slot = {n: i for i, n in enumerate(joints)}
    worlds = R.world_matrices(g)
    w = R.GlbWriter(g, b)
    g["meshes"] = []
    g["materials"] = []
    attrs = {"POSITION": w.accessor(pos.astype(np.float32), "VEC3", target=34962, minmax=True),
             "NORMAL": w.accessor(nrm.astype(np.float32), "VEC3", target=34962),
             "TEXCOORD_0": w.accessor(uv.astype(np.float32), "VEC2", target=34962),
             "JOINTS_0": w.accessor(np.c_[[slot[o] for o in own], np.zeros((len(own), 3))].astype(np.uint16), "VEC4", comp=5123, target=34962),
             "WEIGHTS_0": w.accessor(np.c_[np.ones(len(own)), np.zeros((len(own), 3))].astype(np.float32), "VEC4", target=34962)}
    ind = w.accessor(tris.reshape(-1).astype(np.uint32), "SCALAR", comp=5125, target=34963)
    mat = {"name": "hd_v2", "pbrMetallicRoughness": {"baseColorFactor": [0.5, 0.5, 0.5, 1], "metallicFactor": 0.4, "roughnessFactor": 0.6},
           "doubleSided": True}
    if textures:
        g.setdefault("samplers", []).append({"magFilter": 9729, "minFilter": 9987})
        ti = {}
        for k_, png in textures.items():
            g.setdefault("textures", []).append({"source": w.image(png), "sampler": len(g["samplers"]) - 1})
            ti[k_] = len(g["textures"]) - 1
        if "albedo" in ti:
            mat["pbrMetallicRoughness"]["baseColorTexture"] = {"index": ti["albedo"]}
            mat["pbrMetallicRoughness"]["baseColorFactor"] = [1, 1, 1, 1]
        if "normal" in ti:
            mat["normalTexture"] = {"index": ti["normal"]}
        if "ao" in ti:
            mat["occlusionTexture"] = {"index": ti["ao"]}
    g["materials"].append(mat)
    g["meshes"].append({"name": "hd_body", "primitives": [{"attributes": attrs, "indices": ind, "material": 0}]})
    ibm = np.stack([np.linalg.inv(worlds[j]).T.reshape(-1) for j in joints])
    g.setdefault("skins", [])
    g["skins"] = [{"joints": joints, "inverseBindMatrices": w.accessor(ibm.astype(np.float32), "MAT4")}]
    g["nodes"] = [n for n in g["nodes"]]
    for n in g["nodes"]:
        n.pop("mesh", None); n.pop("skin", None)
    g["nodes"].append({"name": "hd_body", "mesh": 0, "skin": 0})
    g["scenes"][0]["nodes"].append(len(g["nodes"]) - 1)
    for k_ in ("images", "textures"):
        if not g.get(k_):
            g.pop(k_, None)
    w.write(str(out_glb))
    import glb_compact
    glb_compact.compact(out_glb)
    names = [n.get("name", "") for n in g["nodes"]]
    acts = []
    for a_ in rest["actuators"]:
        node = names.index(a_["part"])
        c = np.r_[to_gl(np.asarray(a_["centre_game"])[None])[0], 1.0]
        axg = to_gl(np.asarray(a_.get("axis_game", [1, 0, 0]))[None] * 1000.0)[0]
        axl = np.linalg.inv(worlds[node])[:3, :3] @ axg
        acts.append({"node": a_["part"], "joint": a_["node"], "kind": a_["kind"], "radius": a_["radius_mm"] / 1000.0,
                     "length": a_.get("length_mm", 0.0) / 1000.0, "axis": (axl / np.linalg.norm(axl)).tolist(),
                     "centre": (np.linalg.inv(worlds[node]) @ c)[:3].tolist()})
    n0 = int((kind == 0).sum())
    rig = {"model": out_glb.name, "made_by": "tools/art/hd_v2.py", "actuators": acts, "filler_faces": [[n0, nf]],
           "joint_pairs": rest.get("joint_pairs", []), "contacts": rest.get("contacts", []),
           "parts": {names[n]: int((part == n).sum()) for n in joints}, "tris": int(nf)}
    out_glb.with_suffix(".rig.json").write_text(json.dumps(rig, indent=1))
    print(f"write: {out_glb} ({nf} tris, {len(pos)} verts, {len(joints)} parts)")


def stage_write(a, work):
    uvp = work / "uv.npz"
    uv = np.load(uvp)["uv"] if uvp.exists() else None
    if uv is not None and len(uv) != 3 * len(np.load(work / "rest.npz")["F"]):
        uv = None   # stale: the mesh changed since the last bake
    tex = {}
    for k_, fn in (("albedo", "preview_albedo.png"), ("normal", "bake_normal.png"), ("ao", "bake_ao.png")):
        if (work / fn).exists() and uv is not None:
            tex[k_] = (work / fn).read_bytes()
    out = Path(a.out) if getattr(a, "out", None) else work / f"{a.mech}.glb"
    build_glb(work, out, uv, tex or None, a.folder)


# -------------------------------------------------------------------------------------------------------- sheet
def stage_sheet(a, work):
    """Mask and texture breakdown: zones (base grey, hl1 red, hl2 green, bare steel light blue, dark metal navy,
    glass/emissive yellow), AO, curvature, decals, normal map, preview albedo -> <work>/breakdown.png."""
    from PIL import Image, ImageDraw
    m = np.asarray(Image.open(work / "mask.png").convert("RGBA")).astype(int)
    d = np.asarray(Image.open(work / "detail.png").convert("RGBA"))
    zc = np.zeros(m.shape[:2] + (3,), np.uint8) + np.array([150, 150, 145], np.uint8)
    zc[m[..., 2] > 200] = (150, 190, 230)
    zc[(m[..., 2] > 80) & (m[..., 2] <= 200)] = (40, 50, 90)
    zc[m[..., 0] > 128] = (210, 60, 50)
    zc[m[..., 1] > 128] = (60, 190, 70)
    zc[m[..., 3] > 128] = (240, 220, 60)
    cover = np.load(work / "bake_cover.npy")
    zc[~cover] = (20, 20, 22)
    tiles = [("zones", Image.fromarray(zc)), ("AO", Image.fromarray(d[..., 0])), ("curvature", Image.fromarray(d[..., 1])),
             ("decals", Image.fromarray(d[..., 2])), ("normal (edge rounding)", Image.open(work / "normal.png")),
             ("preview paint", Image.open(work / "preview_albedo.png"))]
    t = 512
    S = Image.new("RGB", (3 * t, 2 * (t + 22)), (24, 26, 30))
    dr = ImageDraw.Draw(S)
    for i, (lab, im) in enumerate(tiles):
        x, y = (i % 3) * t, (i // 3) * (t + 22)
        S.paste(im.convert("RGB").resize((t, t)), (x, y + 22))
        dr.text((x + 6, y + 5), f"{a.mech}: {lab}", fill=(230, 230, 230))
    S.save(work / "breakdown.png")
    print("sheet:", work / "breakdown.png")


# ------------------------------------------------------------------------------------------------------ install
TEX_IMPORT = """[remap]

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
roughness/mode=0
roughness/src_normal=""
process/channel_remap/red=0
process/channel_remap/green=1
process/channel_remap/blue=2
process/channel_remap/alpha=3
process/fix_alpha_border=false
process/premult_alpha=false
process/normal_map_invert_y=false
process/hdr_as_srgb=false
process/hdr_clamp_exposure=false
process/size_limit=0
detect_3d/compress_to=0
"""


def stage_install(a, work):
    """Stage the v2 model where ArtV2 finds it: game/assets/v2/<folder>/<name>.glb + maps + rig sidecar + licence.
    Never touches the installed HD model. The textures import VRAM-compressed (BPTC) with mipmaps."""
    import shutil
    dst = ROOT / "game/assets/v2" / a.folder
    dst.mkdir(parents=True, exist_ok=True)
    glb = work / f"{a.mech}.glb"
    build_glb(work, glb, np.load(work / "uv.npz")["uv"], None, a.folder)
    rig = json.loads(glb.with_suffix(".rig.json").read_text())
    z = np.load(work / "rest.npz")
    rig["height_m"] = round(float(z["P"][:, 2].max()) / 1000.0, 2)
    rig["texture_px"] = int(np.load(work / "bake_cover.npy").shape[0])
    shutil.copy2(glb, dst / f"{a.mech}.glb")
    (dst / f"{a.mech}.rig.json").write_text(json.dumps(rig, indent=1) + "\n")
    for k in ("mask", "detail", "normal"):
        shutil.copy2(work / f"{k}.png", dst / f"{a.mech}_{k}.png")
        imp = dst / f"{a.mech}_{k}.png.import"
        if not imp.exists():
            imp.write_text(TEX_IMPORT.format(normal=1 if k == "normal" else 0))
    lic = ROOT / f"game/assets/{a.folder}/{a.mech}_hd.LICENSE.md"
    if lic.exists():
        t = lic.read_text().replace(f"{a.mech}_hd.glb", f"v2/{a.folder}/{a.mech}.glb")
        t = t.replace(f"(and its paint mask `{a.mech}_hd_paint.bin`)", f"(and its maps `{a.mech}_mask.png`, `_detail.png`, `_normal.png`)")
        rigid = json.loads((work / "fit.json").read_text()).get("kind") == "rigid"
        what = ("not simplified by vertex clustering but decimated in Blender (merge, planar dissolve, collapse) from the "
                "full-resolution kit; " if rigid else
                "re-segmented along the sculpt's creases, ball and drum actuators added at the joints; ")
        t = t.replace("## Changes made\n", "## Changes made\n\n(v2, HD rework 2026-10-23, tools/art/hd_v2.py: " + what +
                      "new UVs, baked ambient occlusion and edge normals, a new paint-zone mask and decals. The notes below "
                      "describe the v1 adaptation whose fit the v2 shares.)\n")
        (dst / f"{a.mech}.LICENSE.md").write_text(t)
    print(f"install: {dst}/{a.mech}.glb + maps ({rig['tris']} tris, {rig['texture_px']} px)")


# --------------------------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mech")
    ap.add_argument("--stl", required=True)
    ap.add_argument("--joints", required=True)
    ap.add_argument("--folder", default="mechs")
    ap.add_argument("--work")
    ap.add_argument("--steps", default="fit,segment,bake,paint,write")
    ap.add_argument("--tex", type=int, default=2048)
    ap.add_argument("--out", help="write stage: the .glb path (default <work>/<mech>.glb)")
    ap.add_argument("--faces", type=int, default=0, help="lowpoly stage: game-mesh triangles (vehicles)")
    ap.add_argument("--samples", type=int, default=64)
    a = ap.parse_args()
    work = Path(a.work or f"/mnt/nvme1n1p1/mc2-rework/work/{a.mech}")
    work.mkdir(parents=True, exist_ok=True)
    steps = a.steps.split(",")
    for st in steps:
        t0 = time.time()
        globals()[f"stage_{st}"](a, work)
        print(f"[{st}] {time.time() - t0:.1f} s")


if __name__ == "__main__":
    main()
