"""Hollander, image-to-3D route: v2-style work dir for tools/art/v3/v3_mech.py from an aligned, prepared sculpt.
    python3 -I tools/cad/hollander_tripo_workdir.py SCULPT.npz BLOCKOUT.npz [WORKDIR]
Same recipe as tools/cad/starslayer_tripo_workdir.py: label = id of the original mesh node of the nearest blockout part,
majority-smoothed; identity transforms; optional extra solids at pivots that fall outside the armour (EXTRAS, empty for now)."""
import json, sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/art")); sys.path.insert(0, str(Path(__file__).resolve().parent))
import hd_rig as R
from starslayer_tripo_workdir import smooth_labels, ball
from hollander_blockout import NODE

# a plain ball at each forearm pivot showed up as a floating white sphere in motion (the generated pods sit 480 mm off
# their pivots), so there are no extras: the pipeline seats the actuators it can
EXTRAS = []


def main():
    sc = np.load(sys.argv[1]); bk = np.load(sys.argv[2])
    work = Path(sys.argv[3] if len(sys.argv) > 3 else "/mnt/nvme1n1p1/mc2-rework/work/hollander_tripo"); work.mkdir(parents=True, exist_ok=True)
    og, ob = R.load_glb(str(ROOT / "game/assets/mechs/hollander.glb"))
    names = [n.get("name", "") for n in og["nodes"]]
    bP, bF = bk["P"].astype(float), bk["F"]
    t = bP[bF]; ar = np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1)
    rng = np.random.default_rng(7); i = rng.choice(len(bF), 300000, p=ar / ar.sum())
    u, v = rng.random((2, len(i))); f = u + v > 1; u[f], v[f] = 1 - u[f], 1 - v[f]
    S = t[i, 0] + u[:, None] * (t[i, 1] - t[i, 0]) + v[:, None] * (t[i, 2] - t[i, 0])
    node_of = np.array([names.index(NODE[str(n)]) for n in bk["names"]])[bk["part"][i]]
    P, F = sc["P"].astype(float), sc["F"]
    cen = P[F].mean(1)
    d, j = cKDTree(S).query(cen)
    lab = smooth_labels(F, node_of[j], passes=10, min_island=600)
    print("faces", len(F), "median distance to blockout", np.median(d).round(0), "mm")
    Vx, Fx, Lx = [P], [F], [lab]; off = len(P)
    for nm_, kind, c, r in EXTRAS:
        v_, f_ = ball(np.array(c, float), r)
        Vx.append(v_); Fx.append(f_ + off); Lx.append(np.full(len(f_), names.index(nm_))); off += len(v_)
    V, F2, lab2 = np.concatenate(Vx), np.concatenate(Fx), np.concatenate(Lx)
    print({names[p]: int((lab2 == p).sum()) for p in sorted(set(lab2.tolist()))})
    for n in og["nodes"]:
        n.pop("mesh", None); n.pop("skin", None)
    for k in ("images", "textures", "samplers", "materials", "meshes", "skins"):
        og.pop(k, None)
    R.GlbWriter(og, ob).write(str(work / "skel.glb"))
    parent = {str(c): i_ for i_, n in enumerate(og["nodes"]) for c in n.get("children", [])}
    np.savez_compressed(work / "labels.npz", V=V, F=F2, lab=lab2)
    (work / "fit.json").write_text(json.dumps({
        "mech": "hollander", "stl": "image-to-3D sculpt (tools/cad/hollander_tripo_workdir.py)", "joints": "", "kind": "inhouse",
        "node_names": names, "parent": parent, "xform": {str(p): np.eye(4).tolist() for p in sorted(set(lab2.tolist()))},
        "pivots": {}, "legs": {}, "keys": [], "k": 1.0, "H": float(V[:, 2].max())}, indent=1))
    print("->", work)


if __name__ == "__main__":
    main()
