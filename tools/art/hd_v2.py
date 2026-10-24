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


def part_yaws(parts_pts, og, ob, step=2.0, span=45.0):
    """Per part name: (best yaw in degrees about the vertical that turns the part onto the original's same-named part,
    error at 0, error at best). Both point sets are centred and scaled to the same RMS radius, so only the orientation
    is compared; chamfer both ways on subsamples."""
    pts, uv, own = R.original_samples(og, ob, per_tri=30)
    mm = np.c_[pts[:, 0], -pts[:, 2], pts[:, 1]] * 1000.0
    on = np.array([og["nodes"][o].get("name", "") for o in own])
    out = {}
    for nm, q in parts_pts.items():
        o = mm[on == nm]
        if len(o) < 50 or len(q) < 50:
            continue
        qc = q - q.mean(0); oc = o - o.mean(0)
        oc = oc * np.sqrt((qc ** 2).sum(1).mean() / max((oc ** 2).sum(1).mean(), 1e-9))
        to, rng = cKDTree(oc), np.random.default_rng(0)
        qs = qc[rng.choice(len(qc), min(4000, len(qc)), replace=False)]
        os_ = oc[rng.choice(len(oc), min(4000, len(oc)), replace=False)]
        def err(d):
            a_ = np.radians(d); Rz = np.array([[np.cos(a_), -np.sin(a_), 0], [np.sin(a_), np.cos(a_), 0], [0, 0, 1]])
            qr = qs @ Rz.T
            return to.query(qr)[0].mean() + cKDTree(qr).query(os_)[0].mean()
        cands = np.arange(-span, span + 1e-6, step)
        es = np.array([err(d) for d in cands])
        b = cands[es.argmin()]
        fine = np.arange(b - step, b + step + 1e-6, 0.5)
        ef = np.array([err(d) for d in fine])
        out[nm] = (float(fine[ef.argmin()]), float(err(0.0)), float(ef.min()))
    return out


def correct_part_yaws(cap, xf, over, names_list, only=None, pivots_mm=None):
    """The yaw check (v2.1, 2026-10-24): a printed kit can be posed with its torso or feet turned against the rest of
    it (the Bushwacker's torso and feet by about 30 degrees). Each part's re-posed points are compared with the
    original part; a part off by more than min_deg whose turned fit is clearly better (err_best < 0.9 err_0) is turned
    back about the vertical through its own centre. J.json v2.yaw_fix: {part: degrees} pins, {part: 0} skips."""
    T, owner = cap["T"], np.asarray(cap["owner"])[:len(cap["T"])]
    Cn = T.mean(1)
    pts = {}
    for node, M in xf.items():
        m = owner == node
        if m.sum() > 50:
            pts[names_list[node]] = Cn[m] @ M[:3, :3].T + M[:3, 3]
    v2 = over.get("v2", {})
    yaws = part_yaws(pts, cap["og"], cap["ob"])
    pins = v2.get("yaw_fix", {})
    report = {}
    for node, M in list(xf.items()):
        nm = names_list[node]
        if nm not in yaws and nm not in pins:
            continue
        if only is not None and node not in only and nm not in pins:
            if nm in yaws:
                report[nm] = {"yaw": round(yaws[nm][0], 1), "err0": round(yaws[nm][1], 1), "err": round(yaws[nm][2], 1), "applied": False}
            continue
        d, e0, e1 = yaws.get(nm, (0.0, 1.0, 1.0))
        ok = abs(d) >= float(v2.get("yaw_min_deg", 4.0)) and e1 < float(v2.get("yaw_gain", 0.93)) * e0 \
            and abs(d) < 44.0   # a best turn at the search limit is a shape mismatch, not a pose
        if nm in pins:
            d, ok = float(pins[nm]), float(pins[nm]) != 0.0
        report[nm] = {"yaw": round(d, 1), "err0": round(e0, 1), "err": round(e1, 1), "applied": bool(ok)}
        if not ok:
            continue
        if pivots_mm is not None and nm in pivots_mm:
            c = np.asarray(pivots_mm[nm], float)   # about the part's own joint (an ankle stays on its ankle)
        else:
            c = pts[nm].mean(0)
        a_ = np.radians(d); Rz = np.eye(4)
        Rz[:3, :3] = [[np.cos(a_), -np.sin(a_), 0], [np.sin(a_), np.cos(a_), 0], [0, 0, 1]]
        Tc = np.eye(4); Tc[:3, 3] = c; Ti = np.eye(4); Ti[:3, 3] = -c
        xf[node] = Tc @ Rz @ Ti @ M
    print("  yaw check: " + ", ".join(f"{k} {v['yaw']:+.1f} ({v['err0']:.0f}->{v['err']:.0f})" + (" FIXED" if v["applied"] else "")
                                       for k, v in report.items()))
    return xf, report


def square_pelvis(cap, xf):
    """Make every leg joint's parent and child agree on the pivot in the rest pose (v2.1). stl_rig gives both legs
    the mean bone lengths and keeps the skeleton's hips, so a yawed or uneven sculpt pelvis lands its sockets up to
    half a metre from the thighs' (Bushwacker: 497 mm). Here the pelvis part turns about the waist's vertical axis
    until the hip sockets lie square across the body, the skeleton's hips move to those sockets, each leg keeps its
    own bone lengths, and the root (and its keys) moves so the mean ankle height is unchanged. The waist housing is a
    drum about that same vertical axis, so the pelvis' turn against the torso is hidden by it."""
    og, ob, names, J, KEYS, legs, shift = cap["og"], cap["ob"], cap["names"], cap["J"], cap["KEYS"], cap["legs"], np.asarray(cap["shift"], float)
    W = R.world_matrices(og)
    torso_c = S.sc(W[names["joint_torso"]][:3, 3]) - shift            # waist pivot, sculpt frame
    d = np.asarray(J["l"]["hip"], float) - np.asarray(J["r"]["hip"], float)
    th = np.arctan2(d[1], d[0])
    Rz = np.array([[np.cos(-th), -np.sin(-th), 0], [np.sin(-th), np.cos(-th), 0], [0, 0, 1]])
    def pel(p):
        return Rz @ (np.asarray(p, float) - torso_c) + torso_c + shift
    old_ankle = np.mean([S.sc(W[names[legs[s][-1]]][:3, 3])[2] for s in "lr"])
    def set_world(jn, world_mm):
        """Rest translation of joint jn so its world position is world_mm (game mm, Z up)."""
        i = names[jn]
        par = next(k for k, n in enumerate(og["nodes"]) if i in n.get("children", []))
        Wp = R.world_matrices(og)[par]
        loc = np.linalg.inv(Wp) @ np.r_[S.gl(world_mm)[0], 1.0]
        og["nodes"][i]["translation"] = loc[:3].tolist()
    for s in "lr":
        set_world(legs[s][0], pel(J[s]["hip"]))
        for k in range(1, len(KEYS)):   # each leg's own bone lengths, along the skeleton's own bone directions
            jn = legs[s][k]
            t = np.array(og["nodes"][names[jn]]["translation"], float)
            ln = np.linalg.norm(np.asarray(J[s][KEYS[k]], float) - np.asarray(J[s][KEYS[k - 1]], float)) / 1000.0
            og["nodes"][names[jn]]["translation"] = (t / np.linalg.norm(t) * ln).tolist()
    W = R.world_matrices(og)
    drop = np.mean([S.sc(W[names[legs[s][-1]]][:3, 3])[2] for s in "lr"]) - old_ankle
    if abs(drop) > 0.5:
        og["nodes"][names["joint_root"]]["translation"][1] -= drop / 1000
        for an in og["animations"]:
            for ch in an["channels"]:
                if ch["target"]["path"] == "translation" and og["nodes"][ch["target"]["node"]]["name"] == "joint_root":
                    si = an["samplers"][ch["sampler"]]["output"]
                    acc = og["accessors"][si]; view = og["bufferViews"][acc["bufferView"]]
                    vals = R.read_accessor(og, ob, si).astype(np.float32).copy(); vals[:, 1] -= drop / 1000
                    off = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
                    ob[off:off + vals.nbytes] = vals.tobytes()
    W = R.world_matrices(og)
    tgt = {s: {kk: S.sc(W[names[legs[s][i]]][:3, 3]) for i, kk in enumerate(KEYS)} for s in "lr"}
    cap["tgt"] = tgt
    out = dict(xf)
    for s in "lr":
        nodes_ = [S.part_under(og, names, jn) for jn in legs[s][:-1]] + [S.part_under(og, names, legs[s][-1], f"joint_{s}foot")]
        for k, node in enumerate(nodes_):
            if node is None:
                continue
            M = np.eye(4)
            if k < len(KEYS) - 1:
                a0, a1 = np.asarray(J[s][KEYS[k]], float), np.asarray(J[s][KEYS[k + 1]], float)
                b0, b1 = tgt[s][KEYS[k]], tgt[s][KEYS[k + 1]]
                Rm = S.rot_between(a1 - a0, b1 - b0); M[:3, :3] = Rm; M[:3, 3] = b0 - Rm @ a0
            else:
                M[:3, 3] = tgt[s]["ankle"] - np.asarray(J[s]["ankle"], float)
            out[int(node)] = M
    hip_part = S.part_under(og, names, "joint_hip")
    if hip_part is not None:
        M = np.eye(4); M[:3, :3] = Rz; M[:3, 3] = torso_c + shift - Rz @ torso_c
        out[int(hip_part)] = M
    print(f"  pelvis squared: turned {np.degrees(-th):.1f} deg about the waist; root {-drop:+.0f} mm; each leg on its own bone lengths")
    return out


# ---------------------------------------------------------------------------------------------------------- fit
def run_stl_rig(a, joints_path):
    cap = {}

    def capture(og, ob, pos, normals, uv, owner, tris, slots, dest, mech):
        cap.update(inspect.currentframe().f_back.f_locals)
    orig_write = S.write
    S.write = capture
    argv = sys.argv
    sys.argv = ["stl_rig.py", a.mech, a.stl, "--joints", str(joints_path), "--folder", a.folder]
    try:
        S.main()
    finally:
        sys.argv = argv
        S.write = orig_write
    return cap


def torso_twist_pass(a, work, cap):
    """If the sculpt's upper body is turned against the original torso (the yaw check, v2.1), rerun stl_rig with its
    own "twist" (the upper body turned back before it maps the arm joints), the config's upper-body coordinates turned
    the same way. Writes <work>/joints_twisted.json and returns the new capture, or None."""
    over = json.loads(Path(a.joints).read_text())
    v2 = over.get("v2", {})
    if over.get("twist") or v2.get("torso_twist") == 0:
        return None
    og = cap["og"]; names_l = [n.get("name", "") for n in og["nodes"]]
    T, owner = cap["T"], np.asarray(cap["owner"])[:len(cap["T"])]
    tor = names_l.index("bw_torso") if False else None
    torso_part = S.part_under(og, cap["names"], "joint_torso")
    if torso_part is None or (owner == torso_part).sum() < 50:
        return None
    pts = {names_l[torso_part]: T.mean(1)[owner == torso_part] + np.asarray(cap["shift"], float)}
    d, e0, e1 = part_yaws(pts, og, cap["ob"])[names_l[torso_part]]
    if "torso_twist" in v2:
        d = float(v2["torso_twist"])
    elif not (abs(d) >= float(v2.get("yaw_min_deg", 4.0)) and e1 < float(v2.get("yaw_gain", 0.93)) * e0 and abs(d) < 44):
        print(f"  torso yaw check: {d:+.1f} deg ({e0:.0f}->{e1:.0f}), no twist")
        return None
    zc = max(cap["J"][s_]["hip"][2] for s_ in "lr") + 0.05 * cap["H"]
    c_, s_ = np.cos(np.radians(d)), np.sin(np.radians(d))
    rot = lambda p_: [p_[0] * c_ - p_[1] * s_, p_[0] * s_ + p_[1] * c_] + list(p_[2:])
    o2 = json.loads(json.dumps(over))
    sc = float(over.get("scale", 1.0))
    o2["twist"] = {"deg": d, "z": zc / sc, "keep": v2.get("twist_keep", [])}   # keep: boxes that stay put (a gun already forward)
    for key in ("upper_joints", "arm_tips"):
        for k_, p_ in o2.get(key, {}).items():
            o2[key][k_] = rot(p_)
    for box in o2.get("parts", []):   # boxes can't turn exactly: their centres turn, sizes stay
        cmin, cmax = np.asarray(box["min"], float), np.asarray(box["max"], float); cc = (cmin + cmax) / 2
        cr = np.asarray(rot(list(cc)), float)
        box["min"], box["max"] = (cmin - cc + cr).tolist(), (cmax - cc + cr).tolist()
    jp = work / "joints_twisted.json"
    jp.write_text(json.dumps(o2, indent=1))
    print(f"  torso yaw check: {d:+.1f} deg ({e0:.0f}->{e1:.0f}): stl_rig rerun with twist about z > {zc:.0f} mm")
    return run_stl_rig(a, jp)


def stage_fit(a, work):
    cap = run_stl_rig(a, a.joints)
    cap2 = torso_twist_pass(a, work, cap)
    if cap2 is not None:
        cap = cap2
    over = cap["over"]
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
    if over.get("v2", {}).get("square_pelvis", True) and "joint_hip" in names and "joint_torso" in names:
        xf = square_pelvis(cap, xf)
    names_l = [n.get("name", "") for n in og["nodes"]]
    # end parts only: a foot turns about its ankle without moving any joint; a turned thigh or shin would pull its
    # child joint off the skeleton (reported, left alone); the upper body was handled by torso_twist_pass
    feet, piv_ft = set(), {}
    for s_ in "lr":
        fnode = S.part_under(og, cap["names"], cap["legs"][s_][-1], f"joint_{s_}foot")
        if fnode is not None:
            feet.add(int(fnode)); piv_ft[names_l[fnode]] = np.asarray(cap["tgt"][s_]["ankle"], float)
    xf, yaw_report = correct_part_yaws(cap, xf, over, names_l, only=feet, pivots_mm=piv_ft)
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
        "k": float(cap["k"]), "cut": (float(cap["cut"]) if cap.get("cut") else None), "over": json.loads(json.dumps(over, default=float)),
        "xform": {str(k): v.tolist() for k, v in xf.items()}, "pivots": {str(k): v for k, v in piv.items()},
        "node_names": [n.get("name", "") for n in og["nodes"]], "parent": {str(k): v for k, v in parent.items()},
        "axes": axes, "yaw_check": yaw_report,
        "legs": {s: {"joints": list(legs[s]), "points": {kk: np.asarray(J[s][kk], float).tolist() for kk in KEYS}}
                 for s in "lr"}, "keys": list(KEYS),
    }, indent=1))
    print(f"fit: {nt} stl_rig tris, {len(xf)} parts -> {work}")


def stage_fitglb(a, work):
    """An already rigged HD model (the five Hunyuan mechs: hd_rig.py's rigid skin on the original skeleton) as the
    source: its rest-pose triangles and each one's joint become the sculpt and its labels, with no re-pose. Then the
    same segment, bake, paint and install stages as a printed sculpt. --stl is the _hd.glb."""
    import pose_test as PT
    g, b, Pv, Jv, Wv, I, joints, ibm = PT.load_skinned(a.stl)
    dom = Jv[np.arange(len(Jv)), Wv.argmax(1)]
    T = np.c_[Pv[:, 0], -Pv[:, 2], Pv[:, 1]][I] * 1000.0                      # (nf, 3, 3) mm Z up
    owner = np.array(joints)[dom[I[:, 0]]]
    og, ob = R.load_glb(str(ROOT / f"game/assets/{a.folder}/{a.mech}.glb"))   # the original: skeleton and animations
    names = [n.get("name", "") for n in og["nodes"]]
    hd_names = [n.get("name", "") for n in g["nodes"]]
    owner = np.array([names.index(hd_names[o]) for o in owner])               # same node names in both files
    parent = {c: i for i, n in enumerate(og["nodes"]) for c in n.get("children", [])}
    W = R.world_matrices(og)
    piv = {}
    for node in set(owner.tolist()):
        jn = node if names[node].startswith("joint_") else parent.get(node)
        while jn is not None and not names[jn].startswith("joint_"):
            jn = parent.get(jn)
        if jn is None:
            continue
        pw = S.sc(W[jn][:3, 3])
        piv[int(node)] = {"joint": names[jn], "joint_index": int(jn), "sculpt": pw.tolist(), "game": pw.tolist()}
    legs = {}
    for s_ in "lr":
        chain = [f"joint_{s_}uleg", f"joint_{s_}lleg", f"joint_{s_}ankle"]
        if all(c in names for c in chain):
            legs[s_] = {"joints": chain, "points": dict(zip(("hip", "knee", "ankle"), [S.sc(W[names.index(c)][:3, 3]).tolist() for c in chain]))}
    for n in og["nodes"]:
        n.pop("mesh", None)
    R.GlbWriter(og, ob).write(str(work / "skel.glb"))
    axes = joint_axes(work / "skel.glb")
    np.savez_compressed(work / "fit.npz", T=T, owner=owner, H=float(T[..., 2].max()))
    (work / "fit.json").write_text(json.dumps({
        "mech": a.mech, "stl": a.stl, "joints": a.joints, "kind": "glb", "H": float(T[..., 2].max()), "nt": int(len(T)),
        "xform": {str(k): np.eye(4).tolist() for k in set(owner.tolist())}, "pivots": {str(k): v for k, v in piv.items()},
        "node_names": names, "parent": {str(k): v for k, v in parent.items()}, "legs": legs, "keys": ["hip", "knee", "ankle"],
        "axes": axes, "yaw_check": {}, "over": {}}, indent=1))
    print(f"fitglb: {len(T)} tris from {Path(a.stl).name}, {len(piv)} parts -> {work}")


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
    (work / "rest_preglass.npz").unlink(missing_ok=True)
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


def raw_in_fit_frame(stl, T_fit, fitinfo=None):
    """The raw sculpt's faces in stl_rig's frame: its own transform chain replayed (turn, base cut, scale to the
    original's height, re-centring, x_shift, yaw about the pivot, the upper-body twist), all of which stl_rig applies
    before it splits any triangle, so the result matches its frame exactly."""
    over = (fitinfo or {}).get("over", {})
    raw = S.load_stl(stl)
    if over.get("turn"):
        raw = raw * np.array([-1.0, -1.0, 1.0])
    raw[..., 2] -= raw[..., 2].min()
    cut = (fitinfo or {}).get("cut")
    if cut:
        raw = raw[raw.mean(1)[:, 2] > cut]
        raw[..., 2] -= raw[..., 2].min()
    k = (fitinfo or {}).get("k")
    if k is None:   # older fit.json: scale from the heights
        k = np.ptp(T_fit[..., 2]) / np.ptp(raw[..., 2])
    raw = raw * k
    flat = raw.reshape(-1, 3)
    raw[..., :2] -= (flat[:, :2].min(0) + flat[:, :2].max(0)) / 2
    raw[..., 0] += over.get("x_shift", 0.0)
    if over.get("yaw") or over.get("twist"):
        pv = np.array(over.get("pivot", [0.0, 0.0]), float)
        def rz(P_, deg):
            c_, s_ = np.cos(np.radians(deg)), np.sin(np.radians(deg)); Q = P_.copy()
            x_, y_ = P_[..., 0] - pv[0], P_[..., 1] - pv[1]
            Q[..., 0], Q[..., 1] = pv[0] + x_ * c_ - y_ * s_, pv[1] + x_ * s_ + y_ * c_
            return Q
        raw = rz(raw, float(over.get("yaw", 0.0)))
        raw[..., :2] -= pv; pv = np.zeros(2)
        tw = over.get("twist")
        if tw:
            Cz = raw.mean(1); sel = Cz[:, 2] > tw["z"]
            inbox = lambda b_: (Cz[:, 0] > b_[0]) & (Cz[:, 0] < b_[1]) & (Cz[:, 1] > b_[2]) & (Cz[:, 1] < b_[3]) & (Cz[:, 2] > b_[4]) & (Cz[:, 2] < b_[5])
            for b_ in tw.get("add", []):
                sel |= inbox(b_)
            for b_ in tw.get("keep", []):
                sel &= ~inbox(b_)
            raw[sel] = rz(raw[sel], float(tw["deg"]))
    a_, b_ = raw.reshape(-1, 3), T_fit.reshape(-1, 3)
    err = np.abs(a_.min(0) - b_.min(0)).max() + np.abs(a_.max(0) - b_.max(0)).max()
    assert err < 5.0, f"raw sculpt does not map onto the fit frame ({err:.1f} mm)"
    return raw


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


def alpha_expansion_metric(U, ea, eb, Dpair, lab, sweeps=3):
    """Alpha-expansion with a per-edge metric: Dpair (ne, L, L), the cost of edge k having labels (a, b)."""
    lab = lab.copy(); L = U.shape[1]; r = np.arange(len(ea))
    def energy(l_):
        return U[np.arange(len(l_)), l_].sum() + Dpair[r, l_[ea], l_[eb]].sum()
    e0 = energy(lab)
    for _ in range(sweeps):
        changed = False
        for al in range(L):
            lp, lq = lab[ea], lab[eb]
            A = Dpair[r, lp, lq]; B = Dpair[r, lp, al]; C = Dpair[r, al, lq]; D = np.zeros_like(A)
            d0 = U[np.arange(len(lab)), lab].copy(); d1 = U[:, al].copy()
            np.add.at(d1, ea, np.maximum(C - A, 0)); np.add.at(d0, ea, np.maximum(A - C, 0))
            np.add.at(d1, eb, np.maximum(D - C, 0)); np.add.at(d0, eb, np.maximum(C - D, 0))
            pair = np.maximum(B + C - A - D, 0)
            x = mincut_sink_side(len(lab), d1, d0, ea, eb, pair) & (lab != al)
            if x.any():
                new = lab.copy(); new[x] = al
                e1 = energy(new)
                if e1 < e0 - 1e-9:
                    lab, e0, changed = new, e1, True
        if not changed:
            break
    return lab


def part_motion(work, nodes, xform, samples=6):
    """For each part node: the list of 4x4 maps (game mm, Z up) from the sculpt frame to each sampled locomotion pose
    (Idle, Walk, Run): pose(t) @ inv(rest) @ xform(node), from the fitted skeleton."""
    import pose_test as PT
    g, b = R.load_glb(str(work / "skel.glb"))
    an = PT.Animator(g, b)
    W0 = an.world()
    Zu = np.array([[1, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 0], [0, 0, 0, 1.0]])   # mm Z-up -> m Y-up (rotation part)
    S_ = np.diag([1e-3, 1e-3, 1e-3, 1.0]); Si = np.diag([1e3, 1e3, 1e3, 1.0])
    to_gl, from_gl = Zu @ S_, Si @ np.linalg.inv(Zu)
    poses = [(a_, t_) for a_ in ("Idle", "Walk", "Run") if a_ in an.anims
             for t_ in np.linspace(0, an.anims[a_][1], samples, endpoint=False)]
    Ws = [an.world(a_, t_) for a_, t_ in poses]
    out = {}
    for n in nodes:
        X = xform.get(n, np.eye(4))
        out[n] = np.stack([from_gl @ W[n] @ np.linalg.inv(W0[n]) @ to_gl @ X for W in Ws])
    return out


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
        # a machined ball, not a toy sphere: flattened along the joint axis, with a collar band round its equator and
        # a flat face at each pole, small and mostly inside the adjoining plates
        ax = ax / np.linalg.norm(ax)
        Vs, Fs = icosphere(r, 3)
        al = Vs @ ax
        Vs = Vs - np.outer(al, ax) + np.outer(np.clip(al * 0.8, -0.62 * r, 0.62 * r), ax)
        Vc, Fc = actuator_mesh("hinge", np.zeros(3), ax, r * 1.04, 0.32 * r, sides=sides)
        return np.r_[Vs, Vc] + c, np.r_[Fs, Fc + len(Vs)]
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


def clip_implicit(Vp, Fp, f):
    """Split every triangle the surface f = 0 crosses into pieces on either side, conformingly (one new vertex per
    crossed edge, found by bisection), keeping winding. f: (n, 3) -> (n,), negative inside."""
    s_ = f(Vp) >= 0
    E = np.concatenate([Fp[:, [0, 1]], Fp[:, [1, 2]], Fp[:, [2, 0]]])
    cr = s_[E[:, 0]] != s_[E[:, 1]]
    if not cr.any():
        return Vp, Fp
    uk = np.unique(np.sort(E[cr], 1), axis=0)
    a, b = Vp[uk[:, 0]], Vp[uk[:, 1]]
    sa = s_[uk[:, 0]]
    lo, hi = np.zeros(len(uk)), np.ones(len(uk))
    for _ in range(24):
        mid = (lo + hi) / 2
        same = (f(a + (b - a) * mid[:, None]) >= 0) == sa
        lo, hi = np.where(same, mid, lo), np.where(same, hi, mid)
    newv = a + (b - a) * ((lo + hi) / 2)[:, None]
    key = {(int(x), int(y)): len(Vp) + i for i, (x, y) in enumerate(uk)}
    Vn = np.r_[Vp, newv]
    fs = s_[Fp]
    mixed = fs.any(1) & ~fs.all(1)
    X = Fp[mixed]; S = fs[mixed]
    lone = np.where(S.sum(1) == 1, S.argmax(1), (~S).argmax(1))
    r = np.arange(len(X))
    A, B_, C_ = X[r, lone], X[r, (lone + 1) % 3], X[r, (lone + 2) % 3]
    eid = lambda u, w: np.array([key[(min(int(p), int(q)), max(int(p), int(q)))] for p, q in zip(u, w)], int)
    ab, ac = eid(A, B_), eid(A, C_)
    new = np.concatenate([np.stack([A, ab, ac], 1), np.stack([ab, B_, C_], 1), np.stack([ab, C_, ac], 1)])
    return Vn, np.r_[Fp[~mixed], new]


def earclip(P2):
    """Triangulate a simple polygon (n, 2), either winding. Returns (m, 3) indices. Falls back to a fan for a loop
    that self-intersects (no ear found)."""
    n = len(P2)
    idx = list(range(n))
    area = 0.5 * np.sum(P2[:, 0] * np.roll(P2[:, 1], -1) - np.roll(P2[:, 0], -1) * P2[:, 1])
    sgn = 1.0 if area > 0 else -1.0
    tris = []
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    guard = 0
    while len(idx) > 3 and guard < 4 * n:
        guard += 1
        found = False
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = P2[i0], P2[i1], P2[i2]
            if sgn * cross(a, b, c) <= 1e-9:
                continue
            ok = True
            for j in idx:
                if j in (i0, i1, i2):
                    continue
                p = P2[j]
                if sgn * cross(a, b, p) > 0 and sgn * cross(b, c, p) > 0 and sgn * cross(c, a, p) > 0:
                    ok = False
                    break
            if ok:
                tris.append((i0, i1, i2)); idx.pop(k); found = True
                break
        if not found:
            break
    if len(idx) == 3:
        tris.append(tuple(idx))
    elif len(idx) > 3:
        tris += [(idx[0], idx[k], idx[k + 1]) for k in range(1, len(idx) - 1)]
    return np.array(tris, int).reshape(-1, 3)


def simple_polygon(P2):
    """True if the closed polyline P2 (n, 2) has no two non-adjacent edges crossing (checked on a subsample)."""
    n = len(P2)
    idx = np.arange(0, n, max(1, n // 120))
    Q = P2[idx]; m = len(Q)
    a, b = Q, np.roll(Q, -1, 0)
    def orient(p, q, r):
        return np.sign((q[..., 0] - p[..., 0]) * (r[..., 1] - p[..., 1]) - (q[..., 1] - p[..., 1]) * (r[..., 0] - p[..., 0]))
    for i in range(m):
        j = np.arange(i + 2, m - (1 if i == 0 else 0))
        if not len(j):
            continue
        o1 = orient(a[i], b[i], a[j]); o2 = orient(a[i], b[i], b[j])
        o3 = orient(a[j], b[j], a[i][None]); o4 = orient(a[j], b[j], b[i][None])
        if ((o1 * o2 < 0) & (o3 * o4 < 0)).any():
            return False
    return True


def ribbon_cap(lp, Lp, e1):
    """Close a strung-out or folded loop by stitching its two sides together: split it at its extremes along its main
    axis and zip the two chains by arc length. Every triangle joins nearby points across the loop, so no fan spikes."""
    t = (Lp - Lp.mean(0)) @ e1
    i0, i1 = int(t.argmin()), int(t.argmax())
    n = len(lp)
    A = [(i0 + k) % n for k in range((i1 - i0) % n + 1)]
    B = [(i0 - k) % n for k in range((i0 - i1) % n + 1)]
    def arc(ch):
        d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(Lp[ch], axis=0), axis=1))]
        return d / max(d[-1], 1e-9)
    sa, sb = arc(A), arc(B)
    tris, i, j = [], 0, 0
    while i < len(A) - 1 or j < len(B) - 1:
        if j >= len(B) - 1 or (i < len(A) - 1 and sa[i + 1] <= sb[j + 1]):
            tris.append((lp[A[i]], lp[A[i + 1]], lp[B[j]])); i += 1
        else:
            tris.append((lp[A[i]], lp[B[j + 1]], lp[B[j]])); j += 1
    return np.array(tris, int).reshape(-1, 3)


def cap_loops(Vp, Fp, skip, max_dev=0.08):
    """Close every open boundary loop of a part (Vp, Fp) with a cap ear-clipped on the loop's best-fit plane, wound
    to face out of the part. skip(points) -> True for loops that a housing already covers. Returns cap faces."""
    loops = boundary_loops(Fp, np.ones(len(Fp), bool))
    caps = []
    for lp in loops:
        if len(lp) < 3:
            continue
        Lp = Vp[lp]
        if skip(Lp):
            continue
        c = Lp.mean(0)
        u_, s_, vt = np.linalg.svd(Lp - c, full_matrices=False)
        e1, e2, nrm = vt[0], vt[1], vt[2]
        rad = np.linalg.norm(Lp - c, axis=1).mean()
        # only a nearly flat loop gets a cap: ear-clipping a jagged, folded seam loop gives spikes that stand out of
        # the shell and read as shards in motion; an unclosed loop shows the shader's dark interior instead
        P2 = np.c_[(Lp - c) @ e1, (Lp - c) @ e2]
        rr = np.linalg.norm(Lp - c, axis=1)
        strung = rr.max() > 2.2 * rr.mean()   # a long, strung-out loop: a cone over it fans into spikes
        if strung or s_[2] / np.sqrt(len(Lp)) > max_dev * rad or not simple_polygon(P2):
            t3 = ribbon_cap(lp, Lp, e1)
            fn = np.cross(Vp[t3[:, 1]] - Vp[t3[:, 0]], Vp[t3[:, 2]] - Vp[t3[:, 0]]).sum(0)
            if fn @ (c - Vp[np.unique(Fp)].mean(0)) < 0:
                t3 = t3[:, [0, 2, 1]]
            caps.append(t3)
            continue
        elif False:
            # folded or non-planar loop: a cone to an apex inside the part (toward the part's middle), no projection
            inward = Vp[np.unique(Fp)].mean(0) - c
            inward /= np.linalg.norm(inward) + 1e-9
            apex = c + inward * 0.12 * rad
            Vp = np.r_[Vp, apex[None]]
            ia = len(Vp) - 1
            t3 = np.array([[lp[i], lp[(i + 1) % len(lp)], ia] for i in range(len(lp))])
            # the loop follows the part's winding: the cap runs the other way
            t3 = t3[:, [1, 0, 2]]
            caps.append(t3)
            continue
        tri = earclip(P2)
        if not len(tri):
            continue
        t3 = np.asarray(lp)[tri]
        # boundary_loops follows the part's face winding: a cap that continues the surface is wound against it
        fn = np.cross(Vp[t3[:, 1]] - Vp[t3[:, 0]], Vp[t3[:, 2]] - Vp[t3[:, 0]]).sum(0)
        e0 = Fp[np.isin(Fp, lp).any(1)]
        part_n = np.cross(Vp[e0[:, 1]] - Vp[e0[:, 0]], Vp[e0[:, 2]] - Vp[e0[:, 0]]).sum(0)
        out_dir = c - Vp[np.unique(e0)].mean(0) if np.linalg.norm(part_n) < 1e-9 else -part_n
        t3 = t3 if fn @ (c - Vp.mean(0)) >= 0 or True else t3
        if fn @ (c - Vp[np.unique(Fp)].mean(0)) < 0:
            t3 = t3[:, [0, 2, 1]]
        caps.append(t3)
    return (np.concatenate(caps) if caps else np.zeros((0, 3), int)), Vp


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

    raw = T_fit.copy() if fit.get("kind") == "glb" else raw_in_fit_frame(fit["stl"], T_fit, fit)
    V, F = weld(raw)
    nf = len(F)
    C = V[F].mean(1)
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    farea = np.linalg.norm(fn, axis=1) / 2
    fn = fn / (np.linalg.norm(fn, axis=1, keepdims=True) + 1e-12)
    # initial labels: stl_rig's part of the nearest split triangle
    lab = own_fit[cKDTree(T_fit.mean(1)).query(C)[1]].astype(int)
    lab_v1 = lab.copy()
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
        if m_.sum() < 30:   # a thin part (an upper arm) has no core at 4 % of the height: seed its most inner faces
            own_ = np.flatnonzero((lab == n_) & (seed < 0))
            if len(own_):
                m_ = np.zeros(nf, bool)
                m_[own_[np.argsort(-dist_b[own_])[:max(30, len(own_) // 4)]]] = True
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
    # motion-aware seams (v2.2, 2026-10-24): a seam between parts a and b costs the edge's length times how far the
    # two parts carry that point apart over the locomotion poses (and at rest: a re-pose mismatch). A metric, so the
    # alpha-expansion puts the seams where the parts barely move against each other: next to the pivots, around the
    # plates the print fused across a joint. The geodesic data term keeps the parts where they were otherwise.
    if v2.get("motion_seams", True) and fit.get("kind") != "rigid":
        ids = np.array(sorted(set(lab.tolist())))
        mot = part_motion(work, [int(n) for n in ids], xform)
        mid = (V[va] + V[vb]) / 2
        Q = {}
        for i, n in enumerate(ids):
            Q[i] = np.einsum("tij,ej->tei", mot[int(n)][:, :3, :3], mid) + mot[int(n)][:, None, :3, 3]   # (T, ne, 3)
        Dp = np.zeros((len(mid), len(ids), len(ids)), np.float32)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                d = np.linalg.norm(Q[i] - Q[j], axis=2)
                d = np.percentile(d, 90, axis=0)
                Dp[:, i, j] = Dp[:, j, i] = d
        lam = float(v2.get("motion_weight", 1.0))
        Dp *= (lam * elen / np.median(elen) / (0.01 * H))[:, None, None] * np.exp(-0.7 * crease)[:, None, None]
        li = np.searchsorted(ids, lab)
        Um = U.copy() if U.shape[1] == len(ids) else np.zeros((nf, len(ids)))
        # anchor every part: its seed faces (bone and core seeds) can't change label, or a part whose neighbours move
        # with it in the sampled poses (a thigh between hip and shin) is swallowed whole and its bone drives nothing
        for i, n in enumerate(ids):
            sm_ = seed == n
            Um[sm_] += 1e4
            Um[sm_, i] = 0.0
        li2 = alpha_expansion_metric(Um, fa, fb, Dp, li, sweeps=2)
        print(f"  motion seams: {int((li2 != li).sum())} faces changed part; part sizes " +
              ", ".join(f"{names[n]} {int((li2 == i).sum())}" for i, n in enumerate(ids)))
        lab = ids[li2]
    for rule in v2.get("assign", []):   # per-kit plate splits by hand: {"part": name, "min": [x,y,z], "max": [...]}
        m_ = (C >= rule["min"]).all(1) & (C <= rule["max"]).all(1)       # sculpt frame (labels.npz), optional "from"
        if "from" in rule:
            m_ &= lab == names.index(rule["from"])
        # "part": "v1" gives the faces back to stl_rig's (the v1 model's) part: for a piece the regrowth carried
        # across a fused contact (Werewolf: shin plates the hanging hand touches in the print went to the arm)
        lab[m_] = lab_v1[m_] if rule["part"] == "v1" else names.index(rule["part"])
        print(f"  assign: {int(m_.sum())} faces -> {rule['part']}")
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

    # ---- housings (v2.1, 2026-10-23). A seam stays closed under a joint's rotation only if it lies on a surface the
    # rotation maps onto itself: a sphere about the pivot (ball joints) or a cylinder about the hinge axis (hinges,
    # the waist's twist). So, in the game's rest frame (where every part already sits re-posed and the animations
    # turn about the skeleton's own pivots), each joint gets a housing that holds the whole seam between its two
    # parts: both parts are clipped exactly onto the housing's surface and what lies inside is dropped. Seam
    # placement per kit: the pair is also tried with the faces near the pivot split by the plane through it, at
    # three reaches, and the labelling that needs the smallest housing wins.
    np.savez_compressed(work / "labels.npz", V=V, F=F, lab=lab)   # sculpt-frame labels before the housings (debugging)
    axes = fit.get("axes", {})
    jcfg = v2.get("joints", {})
    hinge_share = float(v2.get("hinge_share", 0.5))   # drums unless the joint is really a ball
    r_cap = float(v2.get("r_cap", 0.032)) * H   # small: caps close the seams, the housing only shows the joint
    r_min = float(v2.get("r_min", 0.018)) * H
    game_of = {}
    def gpos(node, vid):
        if node not in game_of:
            Mx = xform.get(node, np.eye(4)); game_of[node] = V @ Mx[:3, :3].T + Mx[:3, 3]
        return game_of[node][vid]
    def housing_for(pp, node, kind_, c, ax, lab_):
        sel = ((lab_[fa] == pp) & (lab_[fb] == node)) | ((lab_[fa] == node) & (lab_[fb] == pp))
        vs = np.unique(np.r_[va[sel], vb[sel]])
        if not len(vs):
            return None
        pts = np.r_[gpos(pp, vs), gpos(node, vs)]
        rel = pts - c
        if kind_ == "ball":
            return float(np.percentile(np.linalg.norm(rel, axis=1), 99) * 1.03 + 0.004 * H), 0.0
        al = rel @ ax
        pe = np.linalg.norm(rel - al[:, None] * ax, axis=1)
        return float(np.percentile(pe, 99) * 1.03 + 0.004 * H), float(2 * np.percentile(np.abs(al), 99) * 1.03 + 0.01 * H)
    plan = []
    for pp, node in sorted(joint_pairs, key=lambda c_: jdepth(c_[1])):
        jname = piv[node]["joint"]
        cfg = jcfg.get(jname, {})
        if cfg.get("skip") or not (lab == node).any() or not (lab == pp).any():
            print(f"  {jname}: no {'child' if not (lab == node).any() else 'parent'} faces, no housing")
            continue
        c_game = np.asarray(cfg.get("centre_game", piv[node]["game"]), float)
        p0 = np.asarray(piv[node]["sculpt"], float)
        ax_info = axes.get(jname, {"axis": [1, 0, 0], "share": 0.0})
        ax = np.asarray(cfg.get("axis", ax_info["axis"]), float); ax /= np.linalg.norm(ax)   # game frame
        kind_ = cfg.get("type", "hinge" if ax_info["share"] >= hinge_share else "ball")
        nrm = C[lab == node].mean(0) - p0; nrm /= np.linalg.norm(nrm) + 1e-12   # sculpt frame, toward the child
        best = None
        for reach in [None] + [float(x) * H for x in cfg.get("reaches", v2.get("reaches", [0.05, 0.08, 0.11]))]:
            lab_t = lab.copy()
            if reach is not None:
                m_ = ((lab == node) | (lab == pp)) & (np.linalg.norm(C - p0, axis=1) < reach)
                lab_t[m_] = np.where((C[m_] - p0) @ nrm > 0, node, pp)
            h = housing_for(pp, node, kind_, c_game, ax, lab_t)
            if h is None:
                continue
            size = h[0] if kind_ == "ball" else h[0] + 0.25 * h[1]
            if best is None or size < best[0]:
                best = (size, h, reach, lab_t)
        if best is None:
            print(f"  {jname}: {names[pp]} and {names[node]} share no seam, no housing")
            continue
        _, (R_, L_), reach, lab = best
        R_ = float(cfg.get("radius", max(R_, r_min)))
        L_ = float(cfg.get("length", max(L_, 0.8 * R_) if kind_ != "ball" else 0.0))
        if R_ > r_cap:
            print(f"  {jname}: the seam reaches {R_:.0f} mm from the pivot; housing {r_cap:.0f} mm, the rest is capped as a contact")
            R_ = r_cap
        plan.append((pp, node, jname, kind_, c_game, ax, R_, L_, reach))
    # final labels may have moved since an earlier joint was sized: size every housing again on them
    plan2 = []
    for pp, node, jn, k_, c_, ax, R_, L_, reach in plan:
        cfg = jcfg.get(jn, {})
        h = housing_for(pp, node, k_, c_, ax, lab)
        if h and "radius" not in cfg:
            R_ = max(h[0], r_min)
            L_ = float(cfg.get("length", max(h[1], 0.8 * R_))) if k_ != "ball" else 0.0
        R_ = min(R_, r_cap)
        if k_ != "ball":
            L_ = min(L_, float(cfg.get("max_length", v2.get("max_length", 1.6))) * R_)
        plan2.append((pp, node, jn, k_, c_, ax, R_, L_, reach))
    plan = plan2

    def implicit(kind_, c_, ax, R_, L_):
        if kind_ == "ball":
            return lambda X: np.linalg.norm(X - c_, axis=1) - R_
        def f(X):
            rel = X - c_; al = rel @ ax
            return np.maximum(np.linalg.norm(rel - al[:, None] * ax, axis=1) - R_, np.abs(al) - L_ / 2)
        return f

    out_P, out_F, out_part, out_kind = [], [], [], []
    actuators, nv = [], 0
    parts_done = {}
    depth_of = {n_: (jdepth(n_) if n_ in piv else 0) for n_ in set(lab.tolist())}
    for node in sorted(set(lab.tolist()), key=lambda n_: depth_of[n_]):   # parents first: a child trims against them
        m = lab == node
        used = np.unique(F[m].ravel())
        remap = -np.ones(len(V), int); remap[used] = np.arange(len(used))
        Vp, Fp = gpos(node, used), remap[F[m]]
        for pp, ch, jn, k_, c_, ax, R_, L_, reach in plan:
            if node in (pp, ch):
                f = implicit(k_, c_, ax, R_, L_)
                Vp, Fp = clip_implicit(Vp, Fp, f)
                keep = f(Vp[Fp].mean(1)) >= 0
                Fp = Fp[keep]
        # running clearance (v2.1): a moving part keeps none of its faces within `clearance` of a part it moves
        # against (its joint partners and the parts the print fused it to), so outside the housings two parts
        # never touch and nothing can lift off; the trimmed edges are capped below
        clr = float(v2.get("clearance", 0.0)) * H
        if clr > 0:
            movers = [pp for pp, ch, *_ in plan if ch == node] + [a_ for a_, b_ in cuts if b_ == node and (a_, b_) not in joint_pairs]
            for other in movers:
                if other not in parts_done:
                    continue
                oV, oF = parts_done[other]
                tree_o = cKDTree(np.r_[oV, oV[oF].mean(1)])
                cen = Vp[Fp].mean(1)
                near_o = tree_o.query(cen, distance_upper_bound=clr)[0] < clr
                if near_o.any():
                    Fp = Fp[~near_o]
        parts_done[node] = (Vp, Fp)
        # every other open loop (contacts the print fused: a plate pressed on a thigh, an arm on a hip) gets a cap,
        # so parts that move apart show closed surfaces, not holes
        mine = [(implicit(k_, c_, ax, R_, L_)) for pp, ch, jn, k_, c_, ax, R_, L_, reach in plan if node in (pp, ch)]
        on_housing = lambda Q: False   # cap every loop: one lying on a housing is hidden in it anyway, a partial one isn't
        capf = np.zeros((0, 3), int)
        if v2.get("caps", True):
            capf, Vp = cap_loops(Vp, Fp, on_housing)
            if len(capf) and v2.get("cap_inside_test", True):
                # a cap fills a cut through solid material, so it lies inside the watertight sculpt; a cap triangle
                # whose centre is outside it is a shard standing out of the armour: drop it (sculpt frame test)
                Mx = xform.get(node, np.eye(4)); Mi = np.linalg.inv(Mx)
                cc = Vp[capf].mean(1) @ Mi[:3, :3].T + Mi[:3, 3]
                ins = inside_test(cc, V[F])
                far = cKDTree(C).query(cc)[0] > float(v2.get("cap_out_tol", 0.015)) * H   # just outside a surface is fine
                capf = capf[ins | ~far]
        Fall = np.r_[Fp, capf]
        used2 = np.unique(Fall.ravel())
        remap2 = -np.ones(len(Vp), int); remap2[used2] = np.arange(len(used2))
        out_P.append(Vp[used2]); out_F.append(remap2[Fall] + nv); nv += len(used2)
        out_part.append(np.full(len(Fall), node)); out_kind.append(np.r_[np.zeros(len(Fp), int), np.ones(len(capf), int)])
    for pp, ch, jn, k_, c_, ax, R_, L_, reach in plan:
        Vs, Fs = actuator_mesh(k_, c_, ax, R_ * 0.985, L_ * 0.985 if L_ else 0.0)
        out_P.append(Vs); out_F.append(Fs + nv); nv += len(Vs)
        out_part.append(np.full(len(Fs), ch)); out_kind.append(np.full(len(Fs), 3))
        actuators.append({"node": jn, "part": names[ch], "parent": names[pp], "kind": k_, "radius_mm": R_,
                          "length_mm": L_, "centre_game": c_.tolist(), "axis_game": ax.tolist(),
                          "seam_reach_mm": reach})
        print(f"  {jn}: {k_} housing r {R_:.0f} mm" + (f" x {L_:.0f} mm" if k_ != "ball" else "") +
              (f", seam split by the pivot plane within {reach:.0f} mm" if reach else ""))
    Pr = np.concatenate(out_P); Fo = np.concatenate(out_F); part = np.concatenate(out_part); kind = np.concatenate(out_kind)
    P = Pr
    # normals: smooth across edges up to 35 degrees within a part, hard elsewhere (per-corner)
    N = corner_normals(Pr, Fo, part * 4 + np.minimum(kind, 3), float(v2.get("smooth_deg", 35.0)))   # caps smooth apart
    capm = kind == 1                      # cone caps: flat shading, or the fan's smoothed normals draw a star
    fnc = np.cross(Pr[Fo[capm, 1]] - Pr[Fo[capm, 0]], Pr[Fo[capm, 2]] - Pr[Fo[capm, 0]])
    fnc /= np.linalg.norm(fnc, axis=1, keepdims=True) + 1e-12
    N[capm] = fnc[:, None, :]
    np.savez_compressed(work / "rest.npz", P=Pr, F=Fo, part=part, kind=kind, N=N, P_sculpt=P)
    (work / "rest_preglass.npz").unlink(missing_ok=True)
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
    d.text((W_ - (bb[2] - bb[0]) - 0.04 * W_ - bb[0], (H_ - (bb[3] - bb[1])) / 2 - bb[1]), text, fill=255, font=font)
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
    tglass = np.zeros((res, res), bool)   # the texel maps onto the original's canopy glass (v2.1: glass from the original)
    gk = v2.get("glass_key", {})
    def glass_texel(rgb, suv_):
        """Original canopy colours: inside a glass_uv_box (texels of the original texture) if the mech gives one,
        and dark or teal/cyan, never a pure team channel."""
        r_, g_, b_ = (rgb[:, i].astype(int) for i in range(3))
        pure = ((r_ == 0) & (g_ == 0)) | ((r_ == 0) & (b_ == 0)) | ((g_ == 0) & (b_ == 0))
        dark = np.maximum(np.maximum(r_, g_), b_) < int(gk.get("dark_max", 45))
        teal = (g_ > r_ + 12) & (b_ > r_ + 12) & (np.abs(g_ - b_) < 70)
        ok = (dark | teal) & ~(pure & ~dark)
        if gk.get("uv_boxes"):
            px_ = suv_ * [tw, th]
            inb = np.zeros(len(rgb), bool)
            for x0, y0, x1, y1 in gk["uv_boxes"]:
                inb |= (px_[:, 0] >= x0) & (px_[:, 0] < x1) & (px_[:, 1] >= y0) & (px_[:, 1] < y1)
            ok &= inb
        return ok
    sglass = glass_texel(scol, suv)
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
        qn = q if fit.get("kind") in ("rigid", "glb") else lo_o + (q - lo_v) / np.maximum(hi_v - lo_v, 1) * (hi_o - lo_o)
        _, k = cKDTree(spts_mm[sm]).query(qn)
        tz[ys[m], xs[m]] = szone[sm][k]
        tglass[ys[m], xs[m]] = sglass[sm][k]
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
    zone_f[kind == 1] = 4   # caps on cut seams: the same dark, matte metal (no edge chips on their fan)
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
    mask[..., 2] = np.where(zt == 3, 255, np.where(zt == 4, 110, 0))
    mask[..., 3] = 0
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
        hm = sp.get("h", 0.4); wm = hm * 0.62 * len(sp["text"]) + (0.75 * hm if v2.get("insignia", True) else 0.0)
        img = stamp_text(sp["text"], wm, hm)
        if v2.get("insignia", True):   # a generic shield crest left of the number (insignia schemes show it)
            sh = np.zeros_like(img); h_, w_ = sh.shape
            from PIL import Image as _I, ImageDraw as _D
            im_ = _I.new("L", (w_, h_), 0); d_ = _D.Draw(im_)
            s0 = h_ * 0.8; x0 = 0.02 * w_; y0 = 0.1 * h_
            d_.polygon([(x0, y0), (x0 + s0 * 0.7, y0), (x0 + s0 * 0.7, y0 + s0 * 0.55), (x0 + s0 * 0.35, y0 + s0),
                        (x0, y0 + s0 * 0.55)], fill=128)
            img = np.maximum(img, np.asarray(im_, float) / 255.0)
        sel = cover & np.isin(fid, fs)
        q = pos[sel] - c
        u_ = (q @ rt) / 1000.0 / wm + 0.5
        v_ = 0.5 - (q @ up) / 1000.0 / hm
        inb = (u_ >= 0) & (u_ < 1) & (v_ >= 0) & (v_ < 1)
        val = np.zeros(len(u_))
        val[inb] = img[(v_[inb] * img.shape[0]).astype(int), (u_[inb] * img.shape[1]).astype(int)]
        dv = decal[sel]; decal[sel] = np.maximum(dv, val)
        print(f"  decal '{sp['text']}' on {sp['part']} panel {k} ({parea[k] / 1e6:.2f} m2)")
    # 3b. scheme data (v2.1): body regions, inset piping, a leg stripe, a limb band, camouflage noise, soot, glass
    Hm = float(P[:, 2].max())                    # height, mm
    sc_ = Hm / 9000.0                            # sizes below are for a 9 m mech
    REG = {"body": 0, "head": 1, "arms": 2, "upper_legs": 3, "lower_legs": 4, "feet": 5, "weapons": 6, "plates": 7}
    def region_of(nm):
        n_ = nm.lower()
        if any(w in n_ for w in ("gun", "launcher", "missile", "lrmpod", "weapon")):
            return REG["weapons"]
        if "uarm" in n_ or "larm" in n_ or "hand" in n_:
            return REG["arms"]
        if "uleg" in n_:
            return REG["upper_legs"]
        if "lleg" in n_ or "mleg" in n_ or "shin" in n_:
            return REG["lower_legs"]
        if "foot" in n_ or "ankle" in n_:
            return REG["feet"]
        return REG["body"]
    reg_f = np.array([region_of(names[pn]) for pn in part])
    sk, sb = R.load_glb(str(work / "skel.glb"))
    Wsk = R.world_matrices(sk)
    node_mm = {n.get("name", ""): S.sc(Wsk[i][:3, 3]) for i, n in enumerate(sk["nodes"])}
    Cf = P[F].mean(1)
    cockpit = node_mm.get("cockpit")
    if cockpit is not None and fit.get("kind") != "rigid":
        head_m = (reg_f == REG["body"]) & (np.linalg.norm(Cf - cockpit, axis=1) < 0.12 * Hm) & (Cf[:, 2] > cockpit[2] - 0.05 * Hm)
        reg_f[head_m] = REG["head"]
    # outer plates: big panels on the limbs (and the torso's shoulders) that face away from their part's middle
    pid_area = np.zeros(pid.max() + 1); np.add.at(pid_area, pid, farea)
    pc = np.zeros((pid.max() + 1, 3)); np.add.at(pc, pid, Cf * farea[:, None]); pc /= np.maximum(pid_area, 1e-9)[:, None]
    part_c = {pn: Cf[part == pn].mean(0) for pn in np.unique(part)}
    big = pid_area[pid] > 0.25e6 * sc_ ** 2
    outward = np.array([(pnrm[pid[f_]] @ (pc[pid[f_]] - part_c[part[f_]])) for f_ in range(len(F))]) > 0
    limb = np.isin(reg_f, [REG["arms"], REG["upper_legs"], REG["lower_legs"]])
    shoulder = (reg_f == REG["body"]) & (np.abs(Cf[:, 0]) > 0.22 * np.ptp(P[:, 0])) & (Cf[:, 2] > 0.55 * Hm) & (np.abs(fn[:, 0]) > 0.5)
    plate = (big & outward & limb) | (big & shoulder)
    if fit.get("kind") != "rigid":
        reg_f[plate & (kind == 0)] = REG["plates"]
    reg_f[kind == 3] = REG["weapons"]            # housings: steel in every scheme
    # texel lookups at the zones resolution
    zr = int(v2.get("zones_px", res // 2))
    st_ = res // zr
    ys2, xs2 = np.mgrid[st_ // 2:res:st_, st_ // 2:res:st_]
    cov2 = cover[ys2, xs2]
    f2 = np.maximum(fid[ys2, xs2], 0)
    p2 = pos[ys2, xs2]
    zones = np.zeros((zr, zr, 4), np.uint8)
    zones[..., 0] = (reg_f[f2] * 16 + 8).astype(np.uint8)
    # piping: a band 12 to 35 mm in from the edge of every big panel
    edge_pts = []
    pidF = pid
    fa_, fb_, va_, vb_ = face_adjacency(np.unique(np.round(P, 1), axis=0, return_inverse=True)[1].ravel()[F])
    keyP = np.unique(np.round(P, 1), axis=0, return_inverse=True)
    Vk = keyP[0]
    diffp = pidF[fa_] != pidF[fb_]
    for a_, b_ in zip(Vk[va_[diffp]], Vk[vb_[diffp]]):
        n_ = max(2, int(np.linalg.norm(b_ - a_) / (8 * sc_)))
        edge_pts.append(a_ + (b_ - a_) * np.linspace(0, 1, n_)[:, None])
    edge_pts = np.concatenate(edge_pts) if edge_pts else np.zeros((1, 3))
    de = cKDTree(edge_pts).query(p2.reshape(-1, 3))[0].reshape(zr, zr)
    bigp = (pid_area[pid[f2]] > 0.2e6 * sc_ ** 2) & np.isin(reg_f[f2], [REG["body"], REG["arms"], REG["upper_legs"], REG["lower_legs"], REG["plates"], REG["head"]])
    pip = np.clip(1 - np.abs(de - 23 * sc_) / (11 * sc_), 0, 1) * bigp
    zones[..., 1] = (pip * 255).astype(np.uint8)
    # leg stripe: a vertical line down the middle of each big leg panel; limb band: a horizontal band across arm and
    # thigh panels, a third of the way up
    legs_ = np.isin(reg_f[f2], [REG["upper_legs"], REG["lower_legs"], REG["plates"]]) & (pid_area[pid[f2]] > 0.3e6 * sc_ ** 2)
    nP = pnrm[pid[f2]]
    lat = np.cross(nP, [0, 0, 1.0]); lat /= np.linalg.norm(lat, axis=-1, keepdims=True) + 1e-9
    rel_ = p2 - pc[pid[f2]]
    stripe = np.clip(1 - np.abs((rel_ * lat).sum(-1)) / (45 * sc_), 0, 1) ** 0.5 * legs_ * (np.abs(nP[..., 2]) < 0.7)
    zones[..., 2] = ((stripe > 0.25) * 255).astype(np.uint8)
    armsb = np.isin(reg_f[f2], [REG["arms"], REG["upper_legs"], REG["plates"]]) & (pid_area[pid[f2]] > 0.3e6 * sc_ ** 2)
    hgt = np.zeros(pid.max() + 1); np.maximum.at(hgt, pid, Cf[:, 2] - pc[pid][:, 2])
    band = (np.abs(rel_[..., 2] - 0.33 * hgt[pid[f2]]) < 55 * sc_) & armsb & (np.abs(nP[..., 2]) < 0.6)
    zones[..., 3] = (band * 255).astype(np.uint8)
    zones = dilate(zones, cov2)
    # camouflage noise: three octaves of 3D noise at the rest-pose position, so a pattern sits still on a moving part
    cr = int(v2.get("camo_px", 512)); st3 = res // cr
    ys3, xs3 = np.mgrid[st3 // 2:res:st3, st3 // 2:res:st3]
    p3 = pos[ys3, xs3].reshape(-1, 3)
    rng = np.random.default_rng(1234)
    camo = np.zeros((cr * cr, 4))
    for ch, scale in enumerate((0.17 * Hm, 0.09 * Hm, 0.045 * Hm)):
        acc = np.zeros(len(p3))
        for _ in range(14):
            d_ = rng.normal(size=3); d_ /= np.linalg.norm(d_)
            acc += np.sin(p3 @ d_ * (2 * np.pi / scale) * rng.uniform(0.7, 1.4) + rng.uniform(0, 2 * np.pi))
        camo[:, ch] = 0.5 + 0.5 * np.tanh(acc / np.sqrt(14) * 1.1)
    camo[:, 3] = 1.0
    camo = dilate((camo.reshape(cr, cr, 4) * 255).astype(np.uint8), cover[ys3, xs3])
    # soot around muzzles, jump jets and smoke vents
    vents = np.array([v_ for k_, v_ in node_mm.items() if k_.lower().startswith(("weapon_", "jumpjet", "smoke_"))])
    soot = np.zeros((zr, zr))
    if len(vents):
        dv = cKDTree(vents).query(p2.reshape(-1, 3))[0].reshape(zr, zr)
        soot = np.clip(1 - dv / (0.07 * Hm), 0, 1) ** 1.5
    # glass and lights: the panels at the cockpit node that face forward are the canopy; faces at a spotlight are lights
    gl_code = np.zeros(len(F), np.uint8)
    fwd = np.array([0, -1.0, 0])          # model forward (+Z glTF) in this frame
    if cockpit is not None and fit.get("kind") != "rigid":
        # canopy: small forward-facing panels at the cockpit node, the forward-most first, at most ~0.5 m2 in all
        cand = [k_ for k_ in np.unique(pid[(np.linalg.norm(Cf - cockpit, axis=1) < 0.06 * Hm) & (kind == 0)])
                if pnrm[k_] @ fwd > 0.6 and 0.01e6 * sc_ ** 2 < pid_area[k_] < 0.3e6 * sc_ ** 2]
        cand = sorted(cand, key=lambda k_: pc[k_] @ fwd, reverse=True)
        picked, tot = [], 0.0
        for k_ in cand[:int(v2.get("canopy_panels", 3))]:
            if tot + pid_area[k_] > 0.5e6 * sc_ ** 2:
                break
            picked.append(k_); tot += pid_area[k_]
        cand = picked
        for k_ in v2.get("canopy_extra", []):
            cand.append(k_)
        gl_code[np.isin(pid, cand)] = 255
    for k_, v_ in node_mm.items():
        if k_.lower().startswith("spot_") or k_.lower().startswith("light"):
            gl_code[(np.linalg.norm(Cf - v_, axis=1) < 0.025 * Hm) & (kind == 0)] = 100
    # canopy glass from the original (v2.1, 2026-10-24): a face is glass where most of its texels map onto the
    # original's canopy colours, within reach of the cockpit node (stray dark or blue paint elsewhere stays paint)
    gcount = np.zeros(len(F)); tcount = np.zeros(len(F))
    np.add.at(tcount, fid[cover], 1.0)
    np.add.at(gcount, fid[cover & tglass], 1.0)
    share = gcount / np.maximum(tcount, 1)
    gfaces = (share >= float(gk.get("share", 0.5))) & (kind == 0)
    if cockpit is not None and fit.get("kind") != "rigid":
        gfaces &= np.linalg.norm(Cf - cockpit, axis=1) < float(gk.get("reach", 0.12)) * Hm
    if gk.get("frontmost", False) and gfaces.any() and fit.get("kind") != "rigid":
        # the texel mapping says roughly where the window is (x, z); the pane itself is the frontmost forward-facing
        # surface there, so take that window and project it forward onto the sculpt (a bounds mapping drifts along
        # the nose, the window doesn't)
        gx = np.percentile(Cf[gfaces, 0], [10, 90]); gz = np.percentile(Cf[gfaces, 2], [10, 90])
        pad = float(gk.get("pad", 0.01)) * Hm
        fwd_ = np.array([0, -1.0, 0])
        win = (Cf[:, 0] > gx[0] - pad) & (Cf[:, 0] < gx[1] + pad) & (Cf[:, 2] > gz[0] - pad) & (Cf[:, 2] < gz[1] + pad) \
            & (fn @ fwd_ > float(gk.get("min_dot", 0.35))) & (kind == 0)
        if win.any():
            cell = float(gk.get("cell", 0.012)) * Hm
            key_ = np.floor(np.c_[Cf[:, 0], Cf[:, 2]] / cell).astype(int)
            front = np.zeros(len(F), bool)
            idx = np.flatnonzero(win)
            ky = {}
            for i_ in idx:
                k_ = (key_[i_, 0], key_[i_, 1])
                if k_ not in ky or Cf[i_, 1] < Cf[ky[k_], 1]:
                    ky[k_] = i_
            ymin = np.array([Cf[i_, 1] for i_ in ky.values()])
            for i_ in idx:
                k_ = (key_[i_, 0], key_[i_, 1])
                if Cf[i_, 1] < Cf[ky[k_], 1] + float(gk.get("depth", 0.012)) * Hm:
                    front[i_] = True
            gfaces = front
    if gk.get("from_original", False):   # the texel transfer (off: sculpt shapes differ from the originals)
        gl_code[gfaces] = 255
    if "glass" in z.files:   # Lee's outlines (stage glass)
        gl_code[gl_code == 255] = 0
        gl_code[np.asarray(z["glass"], bool)] = 255
    cp_ = None if "glass" in z.files else v2.get("canopy_patches")   # Lee's / the coordinator's pick: planar patches (sharp edges at deg) holding the points
    if cp_:
        pidc = panels(P, F, part * 4 + np.minimum(kind, 3), float(cp_.get("deg", 20)))
        sculpt_ = np.flatnonzero(kind == 0)
        tc = cKDTree(Cf[sculpt_])
        want = {int(pidc[sculpt_[tc.query(np.asarray(q, float))[1]]]) for q in cp_["points"]}
        gl_code[gl_code == 255] = 0
        gl_code[np.isin(pidc, list(want)) & (kind == 0)] = 255
    np.save(work / "glass_faces.npy", np.flatnonzero(gl_code == 255))
    for lt in v2.get("lights", []):   # {"centre": [..], "radius": mm, "code": 100 light | 190 lens, "normal"?: [..]}
        m_ = (np.linalg.norm(Cf - np.asarray(lt["centre"], float), axis=1) < float(lt.get("radius", 250))) & (kind == 0)
        if "normal" in lt:
            dn = np.asarray(lt["normal"], float); dn /= np.linalg.norm(dn)
            m_ &= fn @ dn > float(lt.get("min_dot", 0.6))
        gl_code[m_] = int(lt.get("code", 100))
    for rule in v2.get("lenses", []):   # config: [{"min": [..], "max": [..]}] faces that are sensor lenses (green)
        m_ = (Cf >= rule["min"]).all(1) & (Cf <= rule["max"]).all(1)
        gl_code[m_] = 190
    zone_f[gl_code > 0] = 5
    print(f"paint: regions " + ", ".join(f"{k_} {np.mean(reg_f == v_):.2f}" for k_, v_ in REG.items()) +
          f"; canopy {int((gl_code == 255).sum())} faces, lights {int((gl_code == 100).sum())}")
    gtex = np.where(cover, gl_code[np.maximum(fid, 0)], 0)
    mask[..., 3] = gtex
    for c_ in (0, 1, 2):
        mask[..., c_][gtex > 0] = 0        # glass is never team paint, camo or metal
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
    div = gaussian_filter(div, 1.6)   # the bevel bake is noisy: unsmoothed, every texel reads as an edge (speckle)
    curv = np.clip(0.5 + div * float(v2.get("curv_gain", 10.0)), 0, 1)
    ao = np.asarray(Image.open(work / "bake_ao.png").convert("L"), float) / 255.0
    ao = np.where(cover, gaussian_filter(ao * cover, 1.4) / np.maximum(gaussian_filter(cover.astype(float), 1.4), 1e-3), ao)  # bake noise
    from scipy.ndimage import zoom as _zoom
    def down(a_):   # area-average to the zones resolution (detail is 1024 for a 2048 atlas: the 16 MB budget)
        k_ = res // zr
        return a_.reshape(zr, k_, zr, k_).mean((1, 3))
    covd = down(cover.astype(float))
    detail = np.zeros((zr, zr, 4), np.uint8)
    detail[..., 0] = (np.clip(down(ao * cover) / np.maximum(covd, 1e-6), 0, 1) * 255).astype(np.uint8)
    detail[..., 1] = (np.clip(down(curv * cover) / np.maximum(covd, 1e-6), 0, 1) * 255).astype(np.uint8)
    detail[..., 2] = (np.clip(down(np.clip(decal, 0, 1)), 0, 1) * 255).astype(np.uint8)
    detail[..., 3] = (soot * 255).astype(np.uint8)
    mask = dilate(mask, cover)
    detail = dilate(detail, covd > 0.25)
    Image.fromarray(zones, "RGBA").save(work / "zones.png", optimize=True)
    Image.fromarray(camo, "RGBA").save(work / "camo.png", optimize=True)
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


# -------------------------------------------------------------------------------------------------------- glass
def ortho_camera(target, d, up_top):
    """Blender's camera for canopy_pick.py's views: at target + 60 m along d, -Z toward the target, its Y toward world
    Z (or world Y for the top view, track_quat('-Z', 'Y')). Returns (pos, right, camup) in mm."""
    d = np.asarray(d, float); d /= np.linalg.norm(d)
    pos = np.asarray(target, float) + d * 60000.0
    f = -d
    upw = np.array([0, 1.0, 0]) if up_top else np.array([0, 0, 1.0])
    camup = upw - (upw @ f) * f
    camup /= np.linalg.norm(camup)
    right = np.cross(f, camup)
    return pos, right, camup


def clip_implicit_src(Vp, Fp, f):
    """clip_implicit, also returning for each output face the index of the input face it came from."""
    s_ = f(Vp) >= 0
    fs = s_[Fp]
    mixed = fs.any(1) & ~fs.all(1)
    if not mixed.any():
        return Vp, Fp, np.arange(len(Fp))
    V2, F2 = clip_implicit(Vp, Fp, f)
    src = np.r_[np.flatnonzero(~mixed), np.tile(np.flatnonzero(mixed), 3)]
    return V2, F2, src


def stage_glass(a, work):
    """Canopy glass from Lee's outlines (v2.canopy_outlines, canopy_pick.py outlines): each pane polygon is in the
    image space of one canopy_pick view. A pane that covers most of the sculpt's own planar patches takes those patches
    whole (snap); otherwise the outline is knifed into the mesh (a conforming split, so it stays watertight) and the
    visible faces inside it become the pane. Writes the result into rest.npz ("glass" per face)."""
    fit = json.loads((work / "fit.json").read_text())
    over = json.loads(Path(fit["joints"]).read_text()) if Path(fit["joints"]).exists() else {}
    co = over.get("v2", {}).get("canopy_outlines")
    # always start from the segment stage's mesh (rest_preglass.npz), so a rerun doesn't knife an already knifed mesh
    pre = work / "rest_preglass.npz"
    if not pre.exists():   # stage_segment deletes it whenever it writes a new rest.npz
        import shutil
        shutil.copy2(work / "rest.npz", pre)
    z = dict(np.load(pre))
    z.pop("glass", None)
    P, F, part, kind = z["P"], z["F"], z["part"], z["kind"]
    if not co:
        z["glass"] = np.zeros(len(F), bool); np.savez_compressed(work / "rest.npz", **z); print("glass: no outlines"); return
    H = float(P[:, 2].max())
    tgt = np.asarray(co["target"], float); scale = float(co["scale"]); px = float(co.get("px", 1000))
    from matplotlib.path import Path as MPath
    def cam_of(view):
        if "cams" in co:   # Blender's own matrices (canopy_pick.py): its track_quat roll isn't the textbook look-at
            M = np.asarray(co["cams"][view], float)
            return M[:3, 3] * 1000.0, M[:3, 0], M[:3, 1]
        return ortho_camera(tgt, co["views"][view], view == "top")
    def uv_of(X, cam):
        pos, right, camup = cam
        return np.c_[((X - pos) @ right / scale + 0.5) * px, (0.5 - (X - pos) @ camup / scale) * px]
    def depth_of(X, cam):
        pos, right, camup = cam
        return (X - pos) @ np.cross(camup, right)   # distance in front of the camera (-Z is forward: right x up = +Z back)
    def visible_inside(P, F, kind, poly, cam, d_dir):
        C = P[F].mean(1)
        n = np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]])
        n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
        uv = uv_of(C, cam)
        inside = MPath(poly).contains_points(uv) & (n @ d_dir > 0.05) & (kind == 0)
        idx = np.flatnonzero(inside)
        if not len(idx):
            return np.zeros(len(F), bool)
        dep = depth_of(C[idx], cam)
        # visibility: nothing camera-facing within a few pixels in front of it (frontmost layer)
        pl = np.asarray(poly, float); lo_, hi_ = pl.min(0) - 8, pl.max(0) + 8
        allf = np.flatnonzero((n @ d_dir > 0.05) & (uv >= lo_).all(1) & (uv <= hi_).all(1))
        tr = cKDTree(uv[allf]); dall = depth_of(C[allf], cam)
        vis = np.array([dep[k] <= dall[tr.query_ball_point(uv[i], 6)].min() + 0.015 * H for k, i in enumerate(idx)])
        out = np.zeros(len(F), bool); out[idx[vis]] = True
        return out
    pid = panels(P, F, part * 4 + np.minimum(kind, 3), 20.0)
    A = np.linalg.norm(np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]]), axis=1) / 2
    snap, knife = set(), []
    for pane in co["panes"]:
        cam = cam_of(pane["view"]); d_dir = np.asarray(co["views"][pane["view"]], float); d_dir /= np.linalg.norm(d_dir)
        ins = visible_inside(P, F, kind, pane["poly"], cam, d_dir)
        if not ins.any():
            continue
        pp = np.unique(pid[ins])
        cov = np.array([A[ins & (pid == q)].sum() / A[pid == q].sum() for q in pp])
        big = A[ins].sum()
        main = [q for q, c in zip(pp, cov) if A[ins & (pid == q)].sum() > 0.05 * big]
        if main and all(cov[list(pp).index(q)] >= 0.7 for q in main):
            snap.update(main)
        else:
            knife.append((pane, cam, d_dir))
    glass = np.isin(pid, list(snap)) & (kind == 0)
    nk = 0
    for pane, cam, d_dir in knife:
        poly = np.asarray(pane["poly"], float)
        mp = MPath(poly)
        def f2(X):
            uv = uv_of(X, cam)
            dd = np.full(len(uv), np.inf)
            for i in range(len(poly)):   # distance to each edge segment
                a_, b_ = poly[i], poly[(i + 1) % len(poly)]
                ab = b_ - a_
                t_ = np.clip(((uv - a_) @ ab) / max(ab @ ab, 1e-9), 0, 1)
                dd = np.minimum(dd, np.linalg.norm(uv - (a_ + t_[:, None] * ab), axis=1))
            return np.where(mp.contains_points(uv), -dd, dd) - 0.25
        nf0 = len(F)
        P, F, src = clip_implicit_src(P, F, f2)
        part, kind, glass = part[src], kind[src], glass[src]
        nk += len(F) - nf0
    if knife:
        # which knifed faces are the pane: a real face-ID render per view of the cut mesh, and every face whose visible
        # pixels lie (mostly) inside a pane outline of that view
        sys.path.insert(0, str(ROOT / "tools/art"))
        import canopy_pick as CP
        from PIL import Image
        from matplotlib.path import Path as MPath2
        ids = np.arange(1, len(F) + 1)
        Cc = np.c_[(ids >> 16) & 255, (ids >> 8) & 255, ids & 255] / 255.0
        Cc = np.where(Cc <= 0.04045, Cc / 12.92, ((Cc + 0.055) / 1.055) ** 2.4)
        np.savez(work / "_glass_fid.npz", P=P, F=F, C=Cc, target=tgt, scale=scale, label_pts=tgt[None])
        CP.run_blender(work / "_glass_fid.npz", work / "_glass_fid", "id")
        yy, xx = np.mgrid[0:int(px), 0:int(px)]
        pix = np.c_[xx.ravel() + 0.5, yy.ravel() + 0.5]
        for view in sorted({p_["view"] for p_, _, _ in knife}):
            a_ = np.asarray(Image.open(work / f"_glass_fid_{view}.png").convert("RGB")).astype(int)
            fid = (((a_[..., 0] << 16) | (a_[..., 1] << 8) | a_[..., 2]) - 1).ravel()
            ok = (fid >= 0) & (fid < len(F))
            vis = np.bincount(fid[ok], minlength=len(F))
            inside = np.zeros(len(pix), bool)
            for p_, _, _ in knife:
                if p_["view"] == view:
                    inside |= MPath2(np.asarray(p_["poly"], float)).contains_points(pix)
            inn = np.bincount(fid[ok & inside], minlength=len(F))
            glass |= (vis >= 2) & (inn >= 0.6 * vis) & (kind == 0)
    # strays: a glass island far from the others and tiny (a sliver seen through a gap) is not a pane
    gi = np.flatnonzero(glass)
    if len(gi):
        key = np.unique(np.round(P, 1), axis=0, return_inverse=True)[1].ravel()
        Fk = key[F[gi]]
        e = np.r_[Fk[:, [0, 1]], Fk[:, [1, 2]], Fk[:, [2, 0]]]
        nv = key.max() + 1
        G = coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(nv, nv))
        _, comp = connected_components(G, directed=False)
        fc = comp[Fk[:, 0]]
        Ag = np.linalg.norm(np.cross(P[F[gi, 1]] - P[F[gi, 0]], P[F[gi, 2]] - P[F[gi, 0]]), axis=1) / 2
        ca = np.bincount(fc, weights=Ag)
        cc = np.array([P[F[gi[fc == c]]].reshape(-1, 3).mean(0) if (fc == c).any() else np.zeros(3) for c in range(len(ca))])
        # keep the islands chained to the largest one (each within 0.06 H of a kept island's surface); a big face that
        # shows only a few pixels inside an outline through a gap can sit metres away and still carry real area
        from scipy.spatial import cKDTree as KD_
        isl = [c for c in range(len(ca)) if (fc == c).any()]
        pts = {c: P[F[gi[fc == c]]].reshape(-1, 3) for c in isl}
        # seed: the island nearest the cockpit (outline target), not the largest (Urbanmech: a 3 m-off stray was 49 %)
        big = [c for c in isl if ca[c] >= 0.03 * Ag.sum()] or isl
        seed = min(big, key=lambda c: np.linalg.norm(pts[c] - tgt, axis=1).min())
        kept, todo = {seed}, set(isl) - {seed}
        grew = True
        while grew and todo:
            tree = KD_(np.concatenate([pts[c] for c in kept]))
            near = {c for c in todo if tree.query(pts[c], k=1)[0].min() < 0.06 * H}
            grew = bool(near)
            kept |= near
            todo -= near
        drop = np.isin(fc, sorted(todo))
        glass[gi[drop]] = False
        if drop.any():
            print(f"  glass: dropped {int(drop.sum())} stray faces")
    # zero-area triangles (knife slivers on a collinear seam) hang Blender's Smart UV Project for good (2026-10-24:
    # 112 of them, 40+ min at full CPU, no output); they cover nothing, so drop them
    Ar = np.linalg.norm(np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]]), axis=1) / 2
    keep = Ar > 1e-3
    if not keep.all():
        print(f"  glass: dropped {int((~keep).sum())} zero-area triangles")
        F, part, kind, glass = F[keep], part[keep], kind[keep], glass[keep]
    z.update(P=P, F=F, part=part, kind=kind, glass=glass,
             N=corner_normals(P, F, part * 4 + np.minimum(kind, 3), float(over.get("v2", {}).get("smooth_deg", 35.0))))
    capm = kind == 1
    if capm.any():
        fnc = np.cross(P[F[capm, 1]] - P[F[capm, 0]], P[F[capm, 2]] - P[F[capm, 0]])
        fnc /= np.linalg.norm(fnc, axis=1, keepdims=True) + 1e-12
        z["N"][capm] = fnc[:, None, :]
    np.savez_compressed(work / "rest.npz", **z)
    np.save(work / "glass_faces.npy", np.flatnonzero(glass))
    print(f"glass: {len(co['panes'])} outlines, {len(snap)} patches snapped, {len(knife)} knifed (+{nk} tris), "
          f"{int(glass.sum())} glass faces")


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
    kind_v = np.zeros(len(pos), int)
    kind_v[tris.ravel()] = np.repeat(kind, 3)
    # optional soft band (v2 config "soft_band", a fraction of the height): where the print fused two moving parts,
    # vertices within the band of the other part blend toward it (50/50 at the seam), so a contact can't lift off
    fitc = json.loads((work / "fit.json").read_text())
    overc = json.loads(Path(fitc["joints"]).read_text()) if fitc.get("joints") and Path(fitc["joints"]).exists() else {}
    band = float(overc.get("v2", {}).get("soft_band", 0.0)) * float(pos[:, 1].max())
    w2_node = np.full(len(pos), -1); w2 = np.zeros(len(pos))
    if band > 0:
        names_ = [n.get("name", "") for n in g["nodes"]]
        pairs = [tuple(p_) for p_ in rest.get("joint_pairs", []) + rest.get("contacts", [])]
        for pa_, ch_ in pairs:
            if pa_ not in names_ or ch_ not in names_:
                continue
            A_, B_ = names_.index(pa_), names_.index(ch_)
            for X_, Y_ in ((A_, B_), (B_, A_)):
                mx = (own == X_) & (kind_v != 3); my = (own == Y_) & (kind_v != 3)
                if not mx.any() or not my.any():
                    continue
                d_ = cKDTree(pos[my]).query(pos[mx], distance_upper_bound=band)[0]
                wv = np.where(np.isfinite(d_), 0.5 * (1 - np.minimum(d_, band) / band), 0.0)
                ix = np.flatnonzero(mx)
                better = wv > w2[ix]
                w2[ix[better]] = wv[better]; w2_node[ix[better]] = Y_
        print(f"  soft band {band * 1000:.0f} mm: {int((w2 > 0).sum())} vertices blended")
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
    # rest-pose position as a vertex colour (0..1 over the bounds, extent in the rig sidecar): the shader samples its
    # weathering noise there, in metres, so it is coherent across UV islands and stays put on a moving part
    lo_p, ext_p = pos.min(0), np.maximum(np.ptp(pos, 0), 1e-6)
    colr = np.c_[(pos - lo_p) / ext_p, np.ones(len(pos))]
    attrs = {"POSITION": w.accessor(pos.astype(np.float32), "VEC3", target=34962, minmax=True),
             "COLOR_0": w.accessor(colr.astype(np.float32), "VEC4", target=34962),
             "NORMAL": w.accessor(nrm.astype(np.float32), "VEC3", target=34962),
             "TEXCOORD_0": w.accessor(uv.astype(np.float32), "VEC2", target=34962),
             "JOINTS_0": w.accessor(np.c_[[slot[o] for o in own], [slot.get(int(o2), 0) if o2 >= 0 else 0 for o2 in w2_node],
                                          np.zeros((len(own), 2))].astype(np.uint16), "VEC4", comp=5123, target=34962),
             "WEIGHTS_0": w.accessor(np.c_[1.0 - w2, w2, np.zeros((len(own), 2))].astype(np.float32), "VEC4", target=34962)}
    ind = w.accessor(tris.reshape(-1).astype(np.uint32), "SCALAR", comp=5125, target=34963)
    if not textures:   # the skeleton file still carries the original's texture: not part of a v2 model
        for k_ in ("images", "textures", "samplers"):
            g.pop(k_, None)
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
    n0 = int((kind == 0).sum()); n1 = n0 + int((kind == 1).sum())
    rig = {"model": out_glb.name, "made_by": "tools/art/hd_v2.py", "actuators": acts, "filler_faces": [[n0, nf]],
           "cap_faces": [[n0, n1]],
           "joint_pairs": rest.get("joint_pairs", []), "contacts": rest.get("contacts", []),
           "parts": {names[n]: int((part == n).sum()) for n in joints}, "tris": int(nf),
           "rest_min": lo_p.tolist(), "rest_extent": ext_p.tolist()}
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
    for k in ("mask", "detail", "normal", "zones", "camo"):
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
