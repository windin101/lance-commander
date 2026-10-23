#!/usr/bin/env python3
"""Pose test for a skinned HD unit: drive every animation in the .glb and measure each joint's seam.

    python3 -I tools/art/pose_test.py MODEL.glb [--samples 24] [--json out.json] [--max-gap 0.03] [--max-pen 0.25]
        [--filler-tail N] [--anims Idle,Walk]

Seams are the places where two rigid parts touch in the rest pose: vertices of different parts (dominant joint)
within 1 mm of each other, plus each part's open boundary edges that lie within 1 mm of another part. For every
animation, sampled at --samples times, the mesh is skinned exactly as glTF does it (LINEAR / STEP samplers, slerp)
and per joint we measure:
  gap: how far a seam vertex has moved away from everything that could cover it, i.e. the distance from the posed
       seam vertex to the nearest surface point of any other part, fillers (joint caps, actuators) included. A seam
       vertex inside an analytic actuator (sidecar "actuators": ball or hinge, see hd_v2.py) counts as covered.
  pen: interpenetration, the depth of a part's surface points (near the joint) inside the other part, read from
       the nearest surface point's normal; reported as the 95th percentile (thin shells make the sign noisy).
Fillers are faces that exist only to hide seams: the sidecar's "filler_faces" ranges (hd_v2.py writes
<model>.rig.json beside the .glb), or --filler-tail N for the last N triangles (stl_rig.py's joint caps).
Exit status 1 if any joint's gap p95 (95th percentile over its seam vertices, worst pose) is over --max-gap
(metres) or its pen p95 over --max-pen. The single worst vertex (gap max) is reported too.
Locomotion animations (Idle, Walk, Run, transitions, limps) are reported apart from the falls and get-ups.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation as Rot, Slerp

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hd_rig as R  # noqa: E402

LOCO = {"Idle", "Walk", "Run", "STtoWK", "WKtoST", "WKtoRN", "RNtoWK", "LimpLeft", "LimpRight", "HitFront", "HitBack",
        "HitLeft", "HitRight", "ParkToStand", "StandToPark", "Jump"}


def trs(t, r, s):
    m = np.eye(4)
    m[:3, :3] = Rot.from_quat(r).as_matrix() * np.asarray(s)[None, :]
    m[:3, 3] = t
    return m


class Animator:
    def __init__(self, g, b):
        self.g, self.b = g, b
        self.nodes = g["nodes"]
        self.parent = {}
        for i, n in enumerate(self.nodes):
            for c in n.get("children", []):
                self.parent[c] = i
        self.rest = [(np.array(n.get("translation", [0, 0, 0]), float), np.array(n.get("rotation", [0, 0, 0, 1]), float),
                      np.array(n.get("scale", [1, 1, 1]), float)) for n in self.nodes]
        self.order = []
        seen = set()
        def visit(i):
            if i in seen:
                return
            if i in self.parent:
                visit(self.parent[i])
            seen.add(i); self.order.append(i)
        for i in range(len(self.nodes)):
            visit(i)
        self.anims = {}
        for an in g.get("animations", []):
            tracks = []
            dur = 0.0
            for c in an["channels"]:
                s = an["samplers"][c["sampler"]]
                t = R.read_accessor(g, b, s["input"]).astype(float).ravel()
                v = R.read_accessor(g, b, s["output"]).astype(float)
                dur = max(dur, t[-1])
                tracks.append((c["target"]["node"], c["target"]["path"], t, v, s.get("interpolation", "LINEAR")))
            self.anims[an.get("name", f"anim{len(self.anims)}")] = (tracks, dur)

    def world(self, anim=None, time=0.0):
        loc = [list(r) for r in self.rest]
        if anim is not None:
            for node, path, t, v, interp in self.anims[anim][0]:
                k = {"translation": 0, "rotation": 1, "scale": 2}.get(path)
                if k is None:
                    continue
                if len(t) == 1 or time <= t[0]:
                    val = v[0]
                elif time >= t[-1]:
                    val = v[-1]
                else:
                    i = int(np.searchsorted(t, time) - 1)
                    f = (time - t[i]) / max(t[i + 1] - t[i], 1e-9)
                    if interp == "STEP":
                        val = v[i]
                    elif k == 1:
                        q0, q1 = v[i], v[i + 1] * (1 if v[i] @ v[i + 1] >= 0 else -1)
                        val = Slerp([0, 1], Rot.from_quat([q0, q1]))(f).as_quat()
                    else:
                        val = v[i] * (1 - f) + v[i + 1] * f
                loc[node][k] = np.asarray(val, float)
        W = [None] * len(self.nodes)
        for i in self.order:
            m = trs(*loc[i])
            W[i] = W[self.parent[i]] @ m if i in self.parent else m
        return W


def load_skinned(path):
    g, b = R.load_glb(str(path))
    for ni, n in enumerate(g["nodes"]):
        if "mesh" in n and "skin" in n:
            pr = g["meshes"][n["mesh"]]["primitives"][0]
            at = pr["attributes"]
            P = R.read_accessor(g, b, at["POSITION"]).astype(float)
            J = R.read_accessor(g, b, at["JOINTS_0"]).astype(int)
            Wt = R.read_accessor(g, b, at["WEIGHTS_0"]).astype(float)
            if Wt.max() > 1.5:
                Wt = Wt / 255.0
            I = R.read_accessor(g, b, pr["indices"]).astype(np.int64).reshape(-1, 3)
            sk = g["skins"][n["skin"]]
            ibm = R.read_accessor(g, b, sk["inverseBindMatrices"]).astype(float).reshape(-1, 4, 4).transpose(0, 2, 1)
            return g, b, P, J, Wt, I, sk["joints"], ibm
    raise SystemExit(f"{path}: no skinned mesh")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("glb")
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--json")
    ap.add_argument("--max-gap", type=float, default=0.03)
    ap.add_argument("--max-pen", type=float, default=0.25)
    ap.add_argument("--filler-tail", type=int, default=0)
    ap.add_argument("--anims", default="")
    ap.add_argument("--pose", help="ANIM@T: write the posed mesh to --pose-out (.npz) and stop")
    ap.add_argument("--pose-out")
    ap.add_argument("--debug", help="ANIM@T (as printed, e.g. Idle@2.83): mark that pose's open seams in --pose-out")
    a = ap.parse_args()
    g, b, P, J, Wt, I, joints, ibm = load_skinned(a.glb)
    side = Path(a.glb).with_suffix(".rig.json")
    rig = json.loads(side.read_text()) if side.exists() else {}
    nt = len(I)
    filler = np.zeros(nt, bool)
    for lo, hi in rig.get("filler_faces", []):
        filler[lo:hi] = True
    if a.filler_tail:
        filler[-a.filler_tail:] = True
    dom = J[np.arange(len(J)), Wt.argmax(1)]            # dominant skin slot per vertex
    fdom = dom[I[:, 0]]
    names = [g["nodes"][j].get("name", str(j)) for j in joints]
    an = Animator(g, b)

    # surface samples per face: centroid and three edge midpoints, with the face's vertices for skinning weights
    bary = np.array([[1 / 3, 1 / 3, 1 / 3], [.5, .5, 0], [0, .5, .5], [.5, 0, .5]])
    def samples(faces):
        return faces, bary
    # seam vertices: sculpt vertices with another part's sculpt or filler surface within 1 mm at rest
    rest_pts = np.einsum("kj,fjd->fkd", bary, P[I]).reshape(-1, 3)
    rest_part = np.repeat(fdom, len(bary))
    rest_fill = np.repeat(filler, len(bary))
    vert_tree = cKDTree(P)
    seam = {}
    sculpt_v = np.zeros(len(P), bool); sculpt_v[I[~filler].ravel()] = True
    # pairs of coincident vertices of different parts
    pairs = vert_tree.query_pairs(0.001, output_type="ndarray")
    pairs = pairs[(dom[pairs[:, 0]] != dom[pairs[:, 1]]) & sculpt_v[pairs[:, 0]] & sculpt_v[pairs[:, 1]]]
    for i, j in pairs:
        for v in (i, j):
            seam.setdefault(int(dom[v]), set()).add(int(v))
    # open boundary edges of each part's sculpt faces: a closed sculpt shell has none, so every one is a cut line
    key = np.unique(np.round(P, 4), axis=0, return_inverse=True)[1].ravel()
    sf = np.flatnonzero(~filler)
    E = np.concatenate([I[sf][:, [0, 1]], I[sf][:, [1, 2]], I[sf][:, [2, 0]]])
    Ep = np.tile(fdom[sf], 3)
    Ek = np.c_[np.sort(key[E], axis=1), Ep]
    u, inv, cnt = np.unique(Ek, axis=0, return_inverse=True, return_counts=True)
    is_open = cnt[inv.ravel()] == 1
    # (T-junctions left by split_long also read as open edges: keep only open vertices within 8 cm of another part
    # or a filler at rest, which is where a cut lies)
    ov, op = E[is_open].ravel(), np.repeat(Ep[is_open], 2)
    if len(ov):
        tr = cKDTree(rest_pts)
        for v, part in zip(ov, op):
            idx = tr.query_ball_point(P[v], 0.08)
            if any(rest_part[k] != part or rest_fill[k] for k in idx):
                seam.setdefault(int(part), set()).add(int(v))
    seam = {s: np.array(sorted(v)) for s, v in seam.items() if len(v) >= 3}
    # with the sidecar's joint pairs, a part's seam is only the cut it shares with its joint partner (parent or child);
    # contact patches (an arm fused to a thigh in the print) separate by design and are reported apart
    partner = {}
    jn = {g["nodes"][j].get("name", ""): k for k, j in enumerate(joints)}
    for pa_, ch_ in rig.get("joint_pairs", []):
        if pa_ in jn and ch_ in jn:
            partner.setdefault(jn[ch_], set()).add(jn[pa_]); partner.setdefault(jn[pa_], set()).add(jn[ch_])
    if partner:
        rt = cKDTree(rest_pts)
        for s_ in list(seam):
            vs = seam[s_]
            others = rest_part != s_
            d_, k_ = cKDTree(rest_pts[others]).query(P[vs])
            near_part = rest_part[others][k_]
            keep = np.isin(near_part, list(partner.get(s_, ())))
            seam[s_] = vs[keep]
            if keep.sum() < 3:
                del seam[s_]

    acts = rig.get("actuators", [])
    if a.pose:  # write the skinned mesh at one pose for a look (mm, Z up, as hd_v2's rest.npz) and stop
        an_, t_ = a.pose.split("@")
        W = an.world(an_, float(t_))
        M = np.stack([W[j] @ ibm[k] for k, j in enumerate(joints)])
        Vp = np.einsum("vk,vkij,vj->vi", Wt, M[J], np.c_[P, np.ones(len(P))])[:, :3]
        Pz = np.c_[Vp[:, 0], -Vp[:, 2], Vp[:, 1]] * 1000.0
        Fn = np.cross(Pz[I[:, 1]] - Pz[I[:, 0]], Pz[I[:, 2]] - Pz[I[:, 0]])
        Fn /= np.linalg.norm(Fn, axis=1, keepdims=True) + 1e-12
        np.savez(a.pose_out, P=Pz, F=I, part=np.array(joints)[fdom], kind=np.where(filler, 3, 0), N=np.repeat(Fn[:, None], 3, 1))
        print("pose ->", a.pose_out)
        return 0

    def depth_in(pts, surf, nrm):
        """Depth of pts below the surface (k=4 nearest samples must agree the point is behind them), capped at 0.3 m."""
        dd, kk = cKDTree(surf).query(pts, k=4)
        behind = (((pts[:, None, :] - surf[kk]) * nrm[kk]).sum(2) < 0).all(1)
        return np.where(behind & (dd[:, 0] < 0.3), dd[:, 0], 0.0)
    Fn0 = np.cross(P[I[:, 1]] - P[I[:, 0]], P[I[:, 2]] - P[I[:, 0]])
    Fn0 /= np.linalg.norm(Fn0, axis=1, keepdims=True) + 1e-12
    Sn0 = np.repeat(Fn0, len(bary), 0)
    rest_tree = cKDTree(rest_pts)
    near_of, rest_depth = {}, {}
    for s, vs in seam.items():
        nb = np.zeros(len(rest_pts), bool)
        nb[np.unique(np.concatenate(rest_tree.query_ball_point(P[vs][::max(1, len(vs) // 400)], 0.6)))] = True
        near_of[s] = nb
        mine, oth = nb & (rest_part == s) & ~rest_fill, nb & (rest_part != s) & ~rest_fill
        rest_depth[s] = depth_in(rest_pts[mine], rest_pts[oth], Sn0[oth]) if mine.any() and oth.any() else 0.0
    node_of = {n.get("name"): i for i, n in enumerate(g["nodes"])}
    anims = [x for x in an.anims if not a.anims or x in a.anims.split(",")]
    res = {}
    dbg_gap = np.zeros(len(P)); dbg_V = P.copy()
    for name in anims:
        dur = an.anims[name][1]
        for t in np.linspace(0, dur, a.samples) if dur > 0 else [0.0]:
            W = an.world(name, t)
            M = np.stack([W[j] @ ibm[k] for k, j in enumerate(joints)])
            Vp = np.einsum("vk,vkij,vj->vi", Wt, M[J], np.c_[P, np.ones(len(P))])[:, :3]
            Sp = np.einsum("kj,fjd->fkd", bary, Vp[I]).reshape(-1, 3)
            Fn = np.cross(Vp[I[:, 1]] - Vp[I[:, 0]], Vp[I[:, 2]] - Vp[I[:, 0]])
            Fn /= np.linalg.norm(Fn, axis=1, keepdims=True) + 1e-12
            Sn = np.repeat(Fn, len(bary), 0)
            for s, vs in seam.items():
                q = Vp[vs]
                near = near_of[s]
                other = near & ((rest_part != s) | rest_fill)
                if partner:
                    other = near & (np.isin(rest_part, list(partner.get(s, ()))) | rest_fill)
                if not other.any():
                    continue
                d = cKDTree(Sp[other]).query(q)[0]
                for act in acts:  # analytic actuators: a seam vertex inside one is covered
                    Wa = W[node_of[act["node"]]]
                    ctr = (Wa @ np.r_[act["centre"], 1.0])[:3]
                    if act["kind"] == "ball":
                        d[np.linalg.norm(q - ctr, axis=1) <= act["radius"]] = 0.0
                    else:
                        ax = Wa[:3, :3] @ np.asarray(act["axis"], float); ax /= np.linalg.norm(ax)
                        rel = q - ctr; along = rel @ ax
                        perp = np.linalg.norm(rel - along[:, None] * ax, axis=1)
                        d[(perp <= act["radius"]) & (np.abs(along) <= act["length"] / 2)] = 0.0
                if a.debug and f"{name}@{t:.2f}" == a.debug:
                    dbg_gap[vs] = np.maximum(dbg_gap[vs], d)
                    dbg_V[:] = Vp
                gap = float(d.max())
                gap95 = float(np.percentile(d, 95))
                # interpenetration: this part's sculpt points near the seam inside the other parts' sculpt surface
                pen = 0.0
                mine, oth = near & (rest_part == s) & ~rest_fill, near & (rest_part != s) & ~rest_fill
                if mine.any() and oth.any():
                    # new interpenetration caused by the pose: depth now minus depth at rest (overlaps by design cancel)
                    dep = depth_in(Sp[mine], Sp[oth], Sn[oth])
                    pen = float(np.percentile(np.maximum(dep - rest_depth[s], 0.0), 95))
                r = res.setdefault(names[s], {"gap_max": 0.0, "gap_at": "", "loco_gap_max": 0.0, "pen_p95": 0.0,
                                              "loco_pen_p95": 0.0, "seam_verts": int(len(vs))})
                r["gap_p95"] = max(r.get("gap_p95", 0.0), gap95)
                if name in LOCO:
                    r["loco_gap_p95"] = max(r.get("loco_gap_p95", 0.0), gap95)
                if gap > r["gap_max"]:
                    r["gap_max"], r["gap_at"] = gap, f"{name}@{t:.2f}"
                r["pen_p95"] = max(r["pen_p95"], pen)
                if name in LOCO:
                    r["loco_gap_max"] = max(r["loco_gap_max"], gap)
                    r["loco_pen_p95"] = max(r["loco_pen_p95"], pen)
    if a.debug:  # the posed mesh, faces at seam vertices that opened more than 5 cm marked (kind 3), for hd_v2's preview
        Pz = np.c_[dbg_V[:, 0], -dbg_V[:, 2], dbg_V[:, 1]] * 1000.0
        Fn = np.cross(Pz[I[:, 1]] - Pz[I[:, 0]], Pz[I[:, 2]] - Pz[I[:, 0]]); Fn /= np.linalg.norm(Fn, axis=1, keepdims=True) + 1e-12
        bad = (dbg_gap[I] > 0.05).any(1)
        np.savez(a.pose_out, P=Pz, F=I, part=np.array(joints)[fdom], kind=np.where(bad, 3, np.where(filler, 1, 0)), N=np.repeat(Fn[:, None], 3, 1))
        print(f"debug {a.debug}: {int(bad.sum())} faces at open seams -> {a.pose_out}")
    fail = []
    print(f"{Path(a.glb).name}: {nt} tris, {len(seam)} seamed parts, {len(anims)} animations x {a.samples} samples")
    print(f"  {'part':18s} {'gap p95':>8s} {'loco':>7s} {'gap max':>8s} {'pen p95':>8s} {'loco':>7s}  worst")
    for n, r in sorted(res.items(), key=lambda x: -x[1].get("gap_p95", 0)):
        bad = r.get("gap_p95", 0) > a.max_gap or r["pen_p95"] > a.max_pen
        if bad:
            fail.append(n)
        print(f"  {n:18s} {r.get('gap_p95', 0):8.3f} {r.get('loco_gap_p95', 0):7.3f} {r['gap_max']:8.3f} {r['pen_p95']:8.3f} "
              f"{r['loco_pen_p95']:7.3f}  {r['gap_at']}" + ("  FAIL" if bad else ""))
    out = {"model": str(a.glb), "tris": nt, "max_gap": a.max_gap, "max_pen": a.max_pen, "joints": res, "fail": fail}
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1))
    print("PASS" if not fail else f"FAIL: {', '.join(fail)}")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
