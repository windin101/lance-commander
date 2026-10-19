#!/usr/bin/env python3
"""The Vulture build (2026-10-19, hand-read joints); the general tool is stl_rig.py. Rig Syllogy's posed Mad Dog STL onto MC2's Vulture skeleton.

    python3 -I tools/art/stl_rig_vulture.py ~/craft/solid/mc2/vulture_stl/game_tris_mm.npy

Input: the STL's triangles scaled to game size (mm, Z up, forward -Y; made from mdd-prime5.stl,
CC BY-NC-SA, Syllogy). Steps:
  1. skeleton: MC2's leg bone directions with the STL's bone lengths (short thigh), so the hip drops
     and every animation's joint_root height keys drop with it; feet stay on the ground;
  2. segment: each leg vertex goes to its nearest STL bone (thigh / shin / foot), the rest by region;
  3. un-pose: each thigh and shin is turned about its proximal joint onto the new rest bone, each
     foot is moved (not turned) to its new ankle, so the STL's mid-stride becomes MC2's rest pose;
  4. write vulture_hd.glb (rigid skin, like cad_mech.py) and the paint palette.
The STL joint centres below were read off gridded side projections (see the session notes).
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cad_mech as C  # noqa: E402
import hd_rig as R    # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
# STL joints (y, z) in mm from the gridded side projections; x is measured from the mesh
STL_J = {"l": {"hip": (200, 4150), "knee": (250, 2400), "ankle": (-2150, 850)},
         "r": {"hip": (150, 4150), "knee": (1900, 3650), "ankle": (2000, 950)}}
LEG_X = {"l": (600, 2600), "r": (-2800, -600)}
NODES = {"l": ("vu_luleg", "vu_llleg", "vu_lfoot", "joint_llleg", "joint_lankle"),
         "r": ("vu_ruleg", "vu_rlleg", "vu_rfoot", "joint_rlleg", "joint_rankle")}
ANKLE_H = 900.0  # STL ankle centre above the sole


def sc_to_gl(v):   # mm Z-up -> m Y-up (glTF)
    v = np.asarray(v, float) / 1000.0
    return np.c_[v[..., 0], v[..., 2], -v[..., 1]] if v.ndim > 1 else np.array([v[0], v[2], -v[1]])


def gl_to_sc(v):
    v = np.asarray(v, float)
    return np.array([v[0], -v[2], v[1]]) * 1000.0


def rot_between(a, b):
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    v, c = np.cross(a, b), float(a @ b)
    if np.linalg.norm(v) < 1e-9:
        return np.eye(3)
    k = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + k + k @ k * (1 / (1 + c))


def seg_dist(p, a, b):
    ab = b - a
    t = np.clip(((p - a) @ ab) / (ab @ ab), 0, 1)
    return np.linalg.norm(p - (a + t[:, None] * ab), axis=1)


def main():
    T = np.load(sys.argv[1]).astype(float)          # (n, 3, 3) mm Z-up
    V = T.reshape(-1, 3)
    og, ob = R.load_glb(str(ROOT / "game/assets/mechs/vulture.glb"))
    names = {n.get("name"): i for i, n in enumerate(og["nodes"])}
    W0 = R.world_matrices(og)
    hip_mc2 = gl_to_sc(W0[names["joint_luleg"]][:3, 3])

    # STL joints in 3D: x from the mesh points near each joint in the side plane
    J = {}
    for s in "lr":
        J[s] = {}
        xs = (V[:, 0] > LEG_X[s][0]) & (V[:, 0] < LEG_X[s][1])
        for k, (y, z) in STL_J[s].items():
            near = xs & (np.hypot(V[:, 1] - y, V[:, 2] - z) < 450)
            J[s][k] = np.array([V[near, 0].mean(), y, z])
    thigh = np.mean([np.linalg.norm(J[s]["knee"] - J[s]["hip"]) for s in "lr"])
    shin = np.mean([np.linalg.norm(J[s]["ankle"] - J[s]["knee"]) for s in "lr"])

    # 1. skeleton: MC2 directions, STL lengths
    tgt = {}
    for s in "lr":
        uleg, lleg, foot, j_knee, j_ankle = NODES[s]
        d_th = np.array(og["nodes"][names[j_knee]]["translation"])   # glTF, parent-local (rest rotations are identity)
        d_sh = np.array(og["nodes"][names[j_ankle]]["translation"])
        og["nodes"][names[j_knee]]["translation"] = (d_th / np.linalg.norm(d_th) * thigh / 1000).tolist()
        og["nodes"][names[j_ankle]]["translation"] = (d_sh / np.linalg.norm(d_sh) * shin / 1000).tolist()
    W1 = R.world_matrices(og)
    drop = gl_to_sc(W1[names["joint_lankle"]][:3, 3])[2] - ANKLE_H    # how far the new ankle sits above the target
    for n in ("joint_root",):
        og["nodes"][names[n]]["translation"][1] -= drop / 1000
    for a in og["animations"]:
        for ch in a["channels"]:
            if ch["target"]["path"] == "translation" and og["nodes"][ch["target"]["node"]]["name"] == "joint_root":
                acc = og["accessors"][a["samplers"][ch["sampler"]]["output"]]
                vals = R.read_accessor(og, ob, a["samplers"][ch["sampler"]]["output"]).astype(np.float32).copy()
                vals[:, 1] -= drop / 1000
                view = og["bufferViews"][acc["bufferView"]]
                off = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
                ob[off:off + vals.nbytes] = vals.tobytes()
    W = R.world_matrices(og)
    for s in "lr":
        uleg, lleg, foot, j_knee, j_ankle = NODES[s]
        tgt[s] = {"hip": gl_to_sc(W[names["joint_" + s + "uleg"]][:3, 3]), "knee": gl_to_sc(W[names[j_knee]][:3, 3]),
                  "ankle": gl_to_sc(W[names[j_ankle]][:3, 3])}
    print(f"thigh {thigh:.0f} mm, shin {shin:.0f} mm; root lowered {drop:.0f} mm; new hip z {tgt['l']['hip'][2]:.0f}")

    # STL hip -> new hip: the whole upper body moves with this offset
    off = np.mean([tgt[s]["hip"] - J[s]["hip"] for s in "lr"], axis=0)

    # 2+3. segment and un-pose, per TRIANGLE (by its centroid), so no triangle spans two parts
    Cn = T.mean(1)                                  # (n, 3) centroids
    nt = len(Cn)
    owner_t = np.full(nt, -1)
    outT = T + off
    xform = {}
    for s in "lr":
        uleg, lleg, foot, *_ = NODES[s]
        j = J[s]
        legs = (Cn[:, 0] > LEG_X[s][0]) & (Cn[:, 0] < LEG_X[s][1]) & (Cn[:, 2] < j["hip"][2] + 350)
        d = np.stack([seg_dist(Cn, j["hip"], j["knee"]), seg_dist(Cn, j["knee"], j["ankle"]),
                      np.where(Cn[:, 2] < j["ankle"][2] + 250, 0, 1e9) + seg_dist(Cn, j["ankle"], j["ankle"] + [0, -1000, -800])], 1)
        which = d.argmin(1)
        for k, (node, a0, a1, b0, b1) in enumerate([(uleg, j["hip"], j["knee"], tgt[s]["hip"], tgt[s]["knee"]),
                                                    (lleg, j["knee"], j["ankle"], tgt[s]["knee"], tgt[s]["ankle"]),
                                                    (foot, None, None, None, None)]):
            m = legs & (which == k)
            owner_t[m] = names[node]
            xform[names[node]] = (a0, a1, b0, b1, j["ankle"], tgt[s]["ankle"])
    up, ax = Cn[:, 2], np.abs(Cn[:, 0])
    arm = (owner_t < 0) & (ax > 1750) & (up > 4300)
    for side, sign in (("l", 1), ("r", -1)):
        mine = arm & (np.sign(Cn[:, 0]) == sign)
        owner_t[mine & (up >= 6000)] = names[f"vu_{side}uarm"]
        owner_t[mine & (up < 6000)] = names[f"vu_{side}gun"]
    owner_t[(owner_t < 0) & (up < 5400)] = names["vu_hip"]
    owner_t[owner_t < 0] = names["vu_torso"]

    # majority filter over triangles that share a vertex: seam triangles join their neighbours' part
    key = np.unique(np.round(T.reshape(-1, 3), 1), axis=0, return_inverse=True)[1].reshape(-1, 3)
    for _ in range(3):
        votes = {}
        for t in range(nt):
            for v in key[t]:
                votes.setdefault(v, []).append(owner_t[t])
        vmaj = {v: max(set(o), key=o.count) for v, o in votes.items()}
        new = owner_t.copy()
        for t in range(nt):
            cand = [vmaj[v] for v in key[t]]
            best = max(set(cand), key=cand.count)
            if cand.count(best) >= 2:
                new[t] = best
        changed = int((new != owner_t).sum()); owner_t = new
        if not changed: break
    print("seam smoothing: last pass changed", changed, "triangles")

    # loose fragments: islands of a part (< 40 tris) that the cut left touching another part join it
    def islands(mask_idx):
        par = {}
        def f(a):
            while par.setdefault(a, a) != a:
                par[a] = par[par[a]]; a = par[a]
            return a
        for t in mask_idx:
            r0 = f(("t", t))
            for v in key[t]:
                par[f(("v", v))] = r0
        groups = {}
        for t in mask_idx:
            groups.setdefault(f(("t", t)), []).append(t)
        return list(groups.values())
    vert_tris = {}
    for t in range(nt):
        for v in key[t]:
            vert_tris.setdefault(v, []).append(t)
    moved = 0
    for node in set(owner_t.tolist()):
        for g in islands(np.flatnonzero(owner_t == node)):
            if len(g) >= 40:
                continue
            nb = [owner_t[u] for t in g for v in key[t] for u in vert_tris[v] if owner_t[u] != node]
            if nb:
                owner_t[g] = max(set(nb), key=nb.count); moved += len(g)
    print(f"fragments: {moved} triangles rejoined their neighbours")

    for node, (a0, a1, b0, b1, ank_s, ank_t) in xform.items():
        m = owner_t == node
        if a0 is not None:
            Rm = rot_between(a1 - a0, b1 - b0)
            outT[m] = (T[m] - a0) @ Rm.T + b0
        else:
            outT[m] = T[m] - ank_s + ank_t

    # paint by region, per triangle, in the STL's own frame
    paint_t = np.array(["base"] * nt, dtype=object)
    box = (np.abs(Cn[:, 0]) > 450) & (np.abs(Cn[:, 0]) < 1650) & (Cn[:, 2] > 6850)
    paint_t[box] = "hl1"
    gun = np.isin(owner_t, [names["vu_lgun"], names["vu_rgun"]])
    paint_t[gun & (Cn[:, 1] < -2700)] = "dark"
    feet = np.isin(owner_t, [names["vu_lfoot"], names["vu_rfoot"]])
    paint_t[feet & (Cn[:, 2] < 300)] = "dark"
    paint_t[Cn[:, 2] > 8100] = "metal"
    for s_ in "lr":
        for k in ("hip", "knee", "ankle"):
            paint_t[np.linalg.norm(Cn - J[s_][k], axis=1) < 380] = "metal"

    # joint caps: a metal drum on each cut, along the bend axis (X), sized from the seam itself
    seam_of = {}
    for v, ts in vert_tris.items():
        os_ = set(owner_t[ts].tolist())
        if len(os_) > 1:
            seam_of.setdefault(frozenset(os_), []).append(v)
    allv = T.reshape(-1, 3)
    pos_of_key = {}
    for t in range(nt):
        for c_, v in enumerate(key[t]):
            pos_of_key.setdefault(v, T[t, c_])
    cap_T, cap_owner = [], []
    for s_ in "lr":
        uleg, lleg, foot, *_ = NODES[s_]
        for joint, a, b, child in (("hip", None, uleg, uleg), ("knee", uleg, lleg, lleg), ("ankle", lleg, foot, foot)):
            pts = np.array([pos_of_key[v] for k_, vs in seam_of.items() if names[b] in k_ and (a is None or names[a] in k_)
                            for v in vs] or [J[s_][joint]])
            near = pts[np.linalg.norm(pts - J[s_][joint], axis=1) < 1100]
            if len(near) < 4:
                near = np.array([J[s_][joint]])
            r = float(np.clip(np.percentile(np.hypot(near[:, 1] - J[s_][joint][1], near[:, 2] - J[s_][joint][2]), 85) + 0, 230, 470))
            ln = float(np.clip(np.ptp(near[:, 0]) * 0.75, 380, 760))
            ctr = tgt[s_][joint]
            cap_T.append(drum(ctr, r, ln)); cap_owner += [names[child]] * len(cap_T[-1])
            print(f"cap {s_} {joint}: r {r:.0f} mm, length {ln:.0f} mm, {len(near)} seam points")
    cap_T = np.concatenate(cap_T)
    outT = np.concatenate([outT, cap_T])
    owner_t = np.concatenate([owner_t, np.array(cap_owner)])
    paint_t = np.concatenate([paint_t, np.array(["dark"] * len(cap_T), dtype=object)])
    out = outT.reshape(-1, 3)

    pos = sc_to_gl(out)
    slots = {k: i for i, k in enumerate(C.PAINT)}
    uv_t = np.array([(((slots[p] % C.GRID) + 0.5) / C.GRID, ((slots[p] // C.GRID) + 0.5) / C.GRID) for p in paint_t])
    uv = np.repeat(uv_t, 3, axis=0)
    owner_v = np.repeat(owner_t, 3)   # one part per triangle, so no triangle is torn across two joints
    tris = np.arange(len(pos)).reshape(-1, 3)
    normals = R.vertex_normals(pos, tris)
    write(og, ob, pos, normals, uv, owner_v, tris, slots)


def drum(c, r, ln, sides=16):
    """A closed prism along X centred on c (mm, Z up), as (n, 3, 3) triangles wound outward."""
    a = np.linspace(0, 2 * np.pi, sides, endpoint=False)
    ring = np.c_[np.cos(a), np.sin(a)] * r
    x0, x1 = c[0] - ln / 2, c[0] + ln / 2
    P = lambda x, i: np.array([x, c[1] + ring[i % sides, 0], c[2] + ring[i % sides, 1]])
    tris = []
    for i in range(sides):
        tris += [[P(x0, i), P(x1, i), P(x1, i + 1)], [P(x0, i), P(x1, i + 1), P(x0, i + 1)]]
        tris += [[np.array([x0, c[1], c[2]]), P(x0, i + 1), P(x0, i)], [np.array([x1, c[1], c[2]]), P(x1, i), P(x1, i + 1)]]
    tris = np.array(tris)
    for t in tris:  # wind outward
        n = np.cross(t[1] - t[0], t[2] - t[0]); m = t.mean(0)
        out = m - np.array(c); out[0] = (m[0] - c[0]) * 4 if abs(n[0]) > abs(n[1]) + abs(n[2]) else 0
        if n @ out < 0:
            t[[1, 2]] = t[[2, 1]]
    return tris


def write(og, ob, pos, normals, uv, owner, tris, slots):
    from PIL import Image
    palette = Image.new("RGB", (C.CELL * C.GRID, C.CELL * C.GRID), (128, 128, 128))
    for k, i in slots.items():
        palette.paste(Image.new("RGB", (C.CELL, C.CELL), C.PAINT[k]), ((i % C.GRID) * C.CELL, (i // C.GRID) * C.CELL))
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
    og["textures"][-1]["sampler"] = len(og["samplers"]) - 1
    og.setdefault("materials", []).append({"name": "hd_stl", "pbrMetallicRoughness": {"baseColorTexture": {"index": tex}, "metallicFactor": 0.35, "roughnessFactor": 0.55}})
    og["meshes"].append({"name": "hd_body", "primitives": [{"attributes": attrs, "indices": ind, "material": len(og["materials"]) - 1}]})
    ibm = np.stack([np.linalg.inv(worlds[j]).T.reshape(-1) for j in joints])
    og.setdefault("skins", []).append({"joints": joints, "inverseBindMatrices": w.accessor(ibm, "MAT4")})
    og["nodes"].append({"name": "hd_body", "mesh": len(og["meshes"]) - 1, "skin": len(og["skins"]) - 1})
    og["scenes"][0]["nodes"].append(len(og["nodes"]) - 1)
    out = ROOT / "game/assets/mechs"
    w.write(str(out / "vulture_hd.glb"))
    (out / "vulture_hd_paint.bin").write_bytes(R.png_bytes(palette))
    counts = {og["nodes"][j]["name"]: int((owner == j).sum() // 3) for j in joints}
    print("wrote vulture_hd.glb:", len(tris), "tris;", ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))


if __name__ == "__main__":
    main()
