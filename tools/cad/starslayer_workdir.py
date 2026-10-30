"""Starslayer in-house model, step 3: write the v2-style work dir that tools/art/v3/v3_mech.py reads ("from_v2").
    python3 -I tools/cad/starslayer_workdir.py DETAIL.npz [WORKDIR]
The model is built in the original's rest frame, so every part's xform is the identity and each part carries the
label of the ORIGINAL mesh node it replaces (same names, same joints, same animations)."""
import json, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/art"))
import hd_rig as R

NODE = {"ss_hip": "ss_hip", "ss_torso": "ss_torso", "ss_ruarm": "ss_ruarm", "ss_gun": "ss_gun", "ss_luarm": "ss_luarm",
        "ss_lgun": "ss_lgun", "ss_luleg": "ss_luleg", "ss_ruleg": "ss_ruleg", "ss_llleg": "ss_llleg", "ss_rlleg": "ss_rlleg",
        "ss_lfoot": "ss_lfoot", "ss_rfoot": "ss_rfoot", "toe_li": "joint_litoe", "toe_lo": "joint_lotoe",
        "toe_ri": "joint_ritoe", "toe_ro": "joint_rotoe"}
def main():
    z = np.load(sys.argv[1])
    work = Path(sys.argv[2] if len(sys.argv) > 2 else "/mnt/nvme1n1p1/mc2-rework/work/starslayer"); work.mkdir(parents=True, exist_ok=True)
    og, ob = R.load_glb(str(ROOT / "game/assets/mechs/starslayer.glb"))
    names = [n.get("name", "") for n in og["nodes"]]
    lab = np.array([names.index(NODE[str(z["names"][p])]) for p in z["part"]])
    P, F = z["P"], z["F"]
    # weld per part (each part is its own closed shell; do not merge across parts)
    Vs, Fs, Ls, o = [], [], [], 0
    for p in sorted(set(lab.tolist())):
        m = lab == p
        idx = np.unique(F[m]); mp = {int(a): i for i, a in enumerate(idx)}
        Vr, inv = np.unique(np.round(P[idx], 2), axis=0, return_inverse=True)
        f = np.array([[inv[mp[int(a)]] for a in t] for t in F[m]]) + o
        ok = (f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])
        Vs.append(Vr); Fs.append(f[ok]); Ls += [p] * int(ok.sum()); o += len(Vr)
    V, F, lab = np.concatenate(Vs), np.concatenate(Fs), np.array(Ls)
    # the ground-fix stage takes the soles as the points strictly below the 8th height percentile: a perfectly flat CAD
    # sole has none, so give the lowest 40 mm a deterministic 0.3 mm relief (invisible, keeps v3_stages.py untouched)
    rng = np.random.default_rng(36)
    lo = V[:, 2] < 40
    V[lo, 2] += rng.uniform(0, 0.3, lo.sum())
    for n in og["nodes"]:
        n.pop("mesh", None); n.pop("skin", None)
    for k in ("images", "textures", "samplers", "materials", "meshes", "skins"):   # no Shared Source art in the copy
        og.pop(k, None)
    R.GlbWriter(og, ob).write(str(work / "skel.glb"))
    parent = {str(c): i for i, n in enumerate(og["nodes"]) for c in n.get("children", [])}
    np.savez_compressed(work / "labels.npz", V=V, F=F, lab=lab)
    (work / "fit.json").write_text(json.dumps({
        "mech": "starslayer", "stl": "in-house (tools/cad/starslayer_*.py)", "joints": "", "kind": "inhouse", "node_names": names,
        "parent": parent, "xform": {str(p): np.eye(4).tolist() for p in sorted(set(lab.tolist()))}, "pivots": {}, "legs": {},
        "keys": [], "k": 1.0, "H": float(V[:, 2].max())}, indent=1))
    print(len(F), "tris", len(set(lab.tolist())), "parts ->", work)


if __name__ == "__main__":
    main()
