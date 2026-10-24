#!/usr/bin/env python3
"""HD rework v3 (Pipeline A, 2026-10-24): a printed CC sculpt -> rigid parts with modelled joints -> game mesh, one UV
atlas, Cycles CPU bakes, a hand-authored 5-zone mask, baked wear layers -> game/assets/v3/<folder>/.

    python3 -I tools/art/v3/v3_mech.py <mech> [--steps fit,segment,joints,pose,lowpoly,bake,mask,wear,write]
        [--work /mnt/nvme1n1p1/mc2-rework/v3/<mech>]

Settings: tools/art/v3/<mech>.json (sculpt, scale, pivots in the sculpt's pose, segmentation hints, joints, mask).
Stages read the previous stages' files in --work, so one stage can be rerun alone:
  fit      The sculpt in game mm (Z up, forward -Y), the MC2 skeleton re-built on the sculpt's own pivots: each part is
           turned rigidly from the sculpt's pose into the MC2 rest pose (bone directions from the original, bone
           lengths from the sculpt), hinges turned only about their hinge axis. fit.json.
  segment  Face labels on the kit's own part lines: confident cores near each bone, then crease-aware geodesic
           growth (crossing a concave crease is expensive), so boundaries follow the seams the kit was built from.
  joints   Closes every part into its own watertight shell and models the joints (see joints.py).
  ...      (see the stage functions)
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import v3_common as C  # noqa: E402
import hd_rig as R     # noqa: E402

ROOT = C.ROOT

# MC2 part (mesh node) -> the joint it rides, the pivot it turns about and the pivot it aims at (None: keep the
# sculpt's orientation). "hinge": the turn from the sculpt's pose is only about the rest-frame X axis.
PARTS = {
    "a-hip":   {"joint": "joint_hip", "pivot": "root", "aim": None},
    "a_torso": {"joint": "joint_torso", "pivot": "torso", "aim": None},
    "a_ruarm": {"joint": "joint_rshoulder", "pivot": "rshoulder", "aim": None},
    "a_rlarm": {"joint": "joint_ruarm", "pivot": "ruarm", "aim": "rgun"},
    "a_rgun":  {"joint": "joint_rgun", "pivot": "rgun", "aim": "rhand", "hinge": "a_rlarm"},
    "a_luarm": {"joint": "joint_lshoulder", "pivot": "lshoulder", "aim": None},
    "a_llarm": {"joint": "joint_luarm", "pivot": "luarm", "aim": "lgun"},
    "a_lgun":  {"joint": "joint_lgun", "pivot": "lgun", "aim": "lhand", "hinge": "a_llarm"},
    "a_luleg": {"joint": "joint_luleg", "pivot": "luleg", "aim": "llleg"},
    "a_llleg": {"joint": "joint_llleg", "pivot": "llleg", "aim": "lankle", "hinge": "a_luleg"},
    "a_lfoot": {"joint": "joint_lankle", "pivot": "lankle", "aim": None},
    "a_ruleg": {"joint": "joint_ruleg", "pivot": "ruleg", "aim": "rlleg"},
    "a_rlleg": {"joint": "joint_rlleg", "pivot": "rlleg", "aim": "rankle", "hinge": "a_ruleg"},
    "a_rfoot": {"joint": "joint_rankle", "pivot": "rankle", "aim": None},
}
# skeleton joint -> pivot key (the joints that carry no part keep the pivot named here)
JOINT_PIVOT = {"joint_root": "root", "joint_hip": "root", "joint_torso": "torso",
               "joint_rshoulder": "rshoulder", "joint_ruarm": "ruarm", "joint_rgun": "rgun", "joint_rhand": "rhand",
               "joint_lshoulder": "lshoulder", "joint_luarm": "luarm", "joint_lgun": "lgun", "joint_lhand": "lhand",
               "joint_luleg": "luleg", "joint_llleg": "llleg", "joint_lankle": "lankle", "joint_lfoot": "lfoot",
               "joint_ruleg": "ruleg", "joint_rlleg": "rlleg", "joint_rankle": "rankle", "joint_rfoot": "rfoot"}


def gl_to_mm(v):
    v = np.asarray(v, float)
    return np.array([v[0], -v[2], v[1]]) * 1000.0


def mm_to_gl(v):
    v = np.asarray(v, float) / 1000.0
    return np.stack([v[..., 0], v[..., 2], -v[..., 1]], -1)


def rot_between(a, b):
    """Smallest rotation turning direction a onto direction b."""
    a = a / np.linalg.norm(a); b = b / np.linalg.norm(b)
    v = np.cross(a, b); c = float(a @ b); s = np.linalg.norm(v)
    if s < 1e-9:
        return np.eye(3) if c > 0 else -np.eye(3)
    k = v / s
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    ang = np.arctan2(s, c)
    return np.eye(3) + np.sin(ang) * K + (1 - np.cos(ang)) * K @ K


def rot_x(ang):
    c, s = np.cos(ang), np.sin(ang)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


ATLAS = {"parts": json.loads(json.dumps(PARTS)), "joint_pivot": dict(JOINT_PIVOT)}


def load_cfg(mech):
    """The mech's settings. A config may declare its own skeleton mapping (anything but the Atlas does):
    "parts" {mesh node: {joint, pivot, aim, hinge?}}, "joint_pivot" {joint node: pivot key}, "segments"
    {part: [[a, b], ...]} (pivot keys or [x, y, z] sculpt mm), "feet" [parts], "part_region" {part: region}.
    The module tables are updated in place, so every stage sees the same mech."""
    p = C.HERE / f"{mech}.json"
    cfg = json.loads(p.read_text())
    cfg["_path"] = str(p)
    import v3_stages as S
    import v3_paint as VP
    if cfg.get("from_v2"):
        parts, pivots, rest, _ = v2_setup(cfg)
        cfg["parts"] = parts
        cfg.setdefault("pivots", {}).update({k: v for k, v in pivots.items() if k not in cfg["pivots"]})
        cfg["joint_pivot"] = {j: j for j in pivots}
    PARTS.clear(); PARTS.update(cfg.get("parts", ATLAS["parts"]))
    JOINT_PIVOT.clear(); JOINT_PIVOT.update(cfg.get("joint_pivot", ATLAS["joint_pivot"]))
    S.JOINTS.clear()
    for part, d in PARTS.items():   # actuator pairs: each part with its parent part, keyed by its pivot
        if d.get("parent"):
            S.JOINTS[d["pivot"]] = (d["parent"], part)
    if not cfg.get("parts"):
        S.JOINTS.update(S.ATLAS_JOINTS)
    if cfg.get("part_region"):
        VP.PART_REGION.clear(); VP.PART_REGION.update(cfg["part_region"])
    return cfg


def skeleton(cfg):
    """The original's node tree: names, parents, rest world positions (game mm) of every node."""
    g, b = R.load_glb(str(ROOT / cfg["base_glb"]))
    W = R.world_matrices(g)
    names = [n.get("name", "") for n in g["nodes"]]
    parent = {}
    for i, n in enumerate(g["nodes"]):
        for c_ in n.get("children", []):
            parent[c_] = i
    pos = {names[i]: gl_to_mm(W[i][:3, 3]) for i in range(len(names))}
    return g, b, names, parent, pos


# --- fit ---------------------------------------------------------------------------------------------------------

def _stage_fit_own(cfg, work):
    P, F, k = C.sculpt_in_game(Path(cfg["stl"]).expanduser(), k=cfg["k"], turn=cfg.get("turn", False), yaw=cfg.get("yaw", 0.0))
    if cfg.get("max_edge_mm"):
        n0 = len(F)
        P, F = C.split_long_edges(P, F, float(cfg["max_edge_mm"]))
        print(f"fit: split long edges {n0} -> {len(F)} faces")
    np.savez(work / "sculpt.npz", P=P, F=F)
    g, b, names, parent, opos = skeleton(cfg)
    piv = {kk: np.array(v, float) for kk, v in cfg["pivots"].items()}
    # 1. per-part rotation from the sculpt's pose into the MC2 rest pose
    Rm = {}
    for part, d in PARTS.items():
        if d["aim"] is None:
            Rm[part] = np.eye(3)
            continue
        js, ja = d["joint"], [j for j, p_ in JOINT_PIVOT.items() if p_ == d["aim"]][0]
        rest_dir = opos[ja] - opos[js]
        sc_dir = piv[d["aim"]] - piv[d["pivot"]]
        if "hinge" in d:   # turn only about the hinge (rest X) after the parent's turn
            q = Rm[d["hinge"]] @ sc_dir
            a1 = np.arctan2(q[2], q[1]); a2 = np.arctan2(rest_dir[2], rest_dir[1])
            Rm[part] = rot_x(a2 - a1) @ Rm[d["hinge"]]
        else:
            Rm[part] = rot_between(sc_dir, rest_dir)
    for part, ang in cfg.get("extra_turn", {}).items():   # {part: [ax, ay, az] degrees}, applied after
        from scipy.spatial.transform import Rotation as Rot
        Rm[part] = Rot.from_euler("xyz", ang, degrees=True).as_matrix() @ Rm[part]
    # 2. rest pivots: walk the joint tree, each child pivot carried by its parent part's rigid turn
    part_of_joint = {d["joint"]: p_ for p_, d in PARTS.items()}
    rest = {}
    order = [i for i in range(len(names)) if names[i] in JOINT_PIVOT]
    def depth(i):
        n_ = 0
        while i in parent:
            i = parent[i]; n_ += 1
        return n_
    order.sort(key=depth)
    for i in order:
        nm = names[i]
        if i not in parent or names[parent[i]] not in JOINT_PIVOT:
            rest[nm] = piv[JOINT_PIVOT[nm]].copy()
            continue
        pj = names[parent[i]]
        pp = part_of_joint.get(pj)
        Rp = Rm[pp] if pp else np.eye(3)
        rest[nm] = rest[pj] + Rp @ (piv[JOINT_PIVOT[nm]] - piv[JOINT_PIVOT[pj]])
    xf = {}
    for part, d in PARTS.items():
        M = np.eye(4)
        M[:3, :3] = Rm[part]
        M[:3, 3] = rest[d["joint"]] - Rm[part] @ piv[d["pivot"]]
        xf[part] = M
    # 3. ground: the lowest foot point of the re-posed sculpt sits on z = 0 (root translation keys follow)
    lab_guess = nearest_bone_labels(P, F, cfg)
    zmin = []
    for part in cfg.get("feet", ["a_lfoot", "a_rfoot"]):
        m = lab_guess == part
        V = P[np.unique(F[m])]
        zmin.append((V @ xf[part][:3, :3].T + xf[part][:3, 3])[:, 2].min())
    drop = float(min(zmin))
    for kk in rest:
        rest[kk] = rest[kk] - [0, 0, drop]
    for part in xf:
        xf[part][2, 3] -= drop
    turn_deg = {p_: float(np.degrees(np.arccos(np.clip((np.trace(M[:3, :3]) - 1) / 2, -1, 1)))) for p_, M in xf.items()}
    fit = {"k": k, "height_mm": float(P[:, 2].max()), "drop_mm": drop,
           "root_rest_mm": rest["joint_root"].tolist(), "original_root_mm": opos["joint_root"].tolist(),
           "rest": {kk: v.tolist() for kk, v in rest.items()},
           "xform": {kk: v.tolist() for kk, v in xf.items()}, "turn_deg": turn_deg}
    (work / "fit.json").write_text(json.dumps(fit, indent=1))
    print("fit: k %.2f, height %.0f mm, ground drop %.0f mm" % (k, fit["height_mm"], drop))
    for p_, t in turn_deg.items():
        print(f"  {p_:8s} turned {t:5.1f} deg")
    lens = {}
    for i in order:
        if i in parent and names[parent[i]] in JOINT_PIVOT:
            a_, b_ = names[parent[i]], names[i]
            lens[b_] = (np.linalg.norm(rest[b_] - rest[a_]), np.linalg.norm(opos[b_] - opos[a_]))
    print("  bone lengths sculpt / original (mm): " + ", ".join(f"{n_[6:]} {a:.0f}/{b:.0f}" for n_, (a, b) in lens.items()))


def bone_segments(cfg):
    """Per part, the bone segments its faces cluster around (sculpt pose): [(a, b)]."""
    p = {k: np.array(v, float) for k, v in cfg["pivots"].items()}
    if "segments" in cfg:
        pt = lambda v: p[v] if isinstance(v, str) else np.asarray(v, float)
        return {part: [(pt(a), pt(b)) for a, b in segs] for part, segs in cfg["segments"].items()}
    segs = {
        "a-hip": [(p["luleg"] * [0.5, 1, 1], p["ruleg"] * [0.5, 1, 1]), (p["root"], p["root"] + [0, 0, -1100])],
        "a_torso": [(p["torso"] + [0, 0, 500], p["torso"] + [0, -300, 5400]),
                    (p["rshoulder"] * [0.75, 1, 1] + [0, 0, -1500], p["lshoulder"] * [0.75, 1, 1] + [0, 0, -1500]),
                    (p["rshoulder"] * [0.75, 1, 1], p["lshoulder"] * [0.75, 1, 1])],
        "a_ruarm": [(p["rshoulder"] + [-300, 0, 0], p["ruarm"] + [-600, 0, 1500])],
        "a_rlarm": [(p["ruarm"] + [-300, 0, 0], p["rgun"])],
        "a_rgun": [(p["rgun"], p["rhand"])],
        "a_luarm": [(p["lshoulder"] + [300, 0, 0], p["luarm"] + [600, 0, 1500])],
        "a_llarm": [(p["luarm"] + [300, 0, 0], p["lgun"])],
        "a_lgun": [(p["lgun"], p["lhand"])],
        "a_luleg": [(p["luleg"], p["llleg"])],
        "a_llleg": [(p["llleg"], p["lankle"])],
        "a_lfoot": [(p["lankle"], p["lfoot"]), (p["lankle"] + [0, 0, -500], p["lankle"] + [0, 1500, -500])],
        "a_ruleg": [(p["ruleg"], p["rlleg"])],
        "a_rlleg": [(p["rlleg"], p["rankle"])],
        "a_rfoot": [(p["rankle"], p["rfoot"]), (p["rankle"] + [0, 0, -500], p["rankle"] + [0, 1500, -500])],
    }
    return segs


def seg_dist(X, a, b):
    ab = b - a
    t = np.clip(((X - a) @ ab) / max(ab @ ab, 1e-9), 0, 1)
    return np.linalg.norm(X - (a + t[:, None] * ab), axis=1)


def nearest_bone_labels(P, F, cfg, return_d=False):
    Cn = P[F].mean(1)
    segs = bone_segments(cfg)
    names = list(segs)
    D = np.stack([np.min([seg_dist(Cn, a, b) for a, b in segs[n]], axis=0) for n in names], 1)
    lab = np.array(names)[D.argmin(1)]
    return (lab, D, names) if return_d else lab


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mech")
    ap.add_argument("--steps", default="fit")
    ap.add_argument("--work")
    a = ap.parse_args()
    import v3_mech as VM   # the stages import v3_mech: keep the per-mech tables in that module, not in __main__
    cfg = VM.load_cfg(a.mech)
    work = Path(a.work or f"/mnt/nvme1n1p1/mc2-rework/v3/{a.mech}")
    work.mkdir(parents=True, exist_ok=True)
    import v3_stages as S
    for st in a.steps.split(","):
        t0 = time.time()
        fn = getattr(VM, f"stage_{st}", None) or getattr(S, f"stage_{st}")
        fn(cfg, work)
        print(f"[{st}] {time.time() - t0:.1f} s")



# --- start from a v2 fit (the per-mech joint fits Lee has already seen: pelvis squared, torso yaw, bone lengths) --

def v2_setup(cfg):
    """Derive parts, joint pivots, sculpt-frame pivots from the v2 work dir cfg["from_v2"] (hd_v2.py fit.json,
    skel.glb): every part node the v2 fit re-posed becomes a v3 part on the same joint."""
    v2 = Path(cfg["from_v2"])
    f = json.loads((v2 / "fit.json").read_text())
    names = f["node_names"]
    g, b = R.load_glb(str(v2 / "skel.glb"))
    Wm = R.world_matrices(g)
    gn = [n.get("name", "") for n in g["nodes"]]
    rest = {gn[i]: gl_to_mm(Wm[i][:3, 3]) for i in range(len(gn)) if gn[i].startswith("joint_")}
    parent = {int(k): v for k, v in f["parent"].items()}
    parts, pivots = {}, {}
    for idx, M_ in f["xform"].items():
        idx = int(idx); nm = names[idx]
        M_ = np.array(M_)
        j = idx if nm.startswith("joint_") else parent[idx]      # the joint the part rides
        jn = names[j]
        pj = parent.get(j)
        par_part = None
        while pj is not None:
            if str(pj) in f["xform"]:
                par_part = names[pj]; break
            kids = [int(c) for c, p in parent.items() if p == pj and str(c) in f["xform"] and not names[int(c)].startswith("joint_")]
            if kids and pj != j:
                par_part = names[kids[0]]; break
            pj = parent.get(pj)
        parts[nm] = {"joint": jn, "pivot": jn, "aim": None, "parent": par_part}
    hip_part = next((p_ for p_, d in parts.items() if d["joint"] == "joint_hip"), None)
    for p_, d in parts.items():   # the torso twists against the pelvis (siblings under joint_root)
        if d["parent"] is None and d["joint"] != "joint_hip":
            d["parent"] = hip_part
        rp = rest.get(jn, gl_to_mm(Wm[gn.index(jn)][:3, 3]))
        Mi = np.linalg.inv(M_)
        pivots[jn] = (Mi[:3, :3] @ rp + Mi[:3, 3]).tolist()
    return parts, pivots, rest, f


def stage_fit(cfg, work, _orig=None):
    if not cfg.get("from_v2"):
        return _stage_fit_own(cfg, work)
    v2 = Path(cfg["from_v2"])
    parts, pivots, rest, f = v2_setup(cfg)
    lab = np.load(v2 / "labels.npz")
    V, F, li = lab["V"], lab["F"], lab["lab"]
    if cfg.get("max_edge_mm"):
        V, F, par = C.split_long_edges(V, F, float(cfg["max_edge_mm"]), parent=np.arange(len(F)))
        li = li[par]
    names = f["node_names"]
    np.savez(work / "sculpt.npz", P=V, F=F)
    np.save(work / "v2lab.npy", np.array([names[i] for i in li]))
    xf = {names[int(k)]: np.array(v) for k, v in f["xform"].items()}
    # ground: lowest foot point on z = 0
    drop = min((V[np.unique(F[np.array([names[i] for i in li]) == p_])] @ xf[p_][:3, :3].T + xf[p_][:3, 3])[:, 2].min()
               for p_ in cfg.get("feet", []))
    rest = {k: (v - [0, 0, drop]).tolist() for k, v in rest.items()}
    for p_ in xf:
        xf[p_][2, 3] -= drop
    fit = {"k": f["k"], "from_v2": str(v2), "drop_mm": float(drop), "rest": rest,
           "xform": {k: v.tolist() for k, v in xf.items()},
           "turn_deg": {p_: float(np.degrees(np.arccos(np.clip((np.trace(M_[:3, :3]) - 1) / 2, -1, 1)))) for p_, M_ in xf.items()}}
    (work / "fit.json").write_text(json.dumps(fit, indent=1))
    print(f"fit (from v2 {v2.name}): {len(F)} faces, {len(parts)} parts, ground drop {drop:.0f} mm")


if __name__ == "__main__":
    main()
