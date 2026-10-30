"""Starslayer, image-to-3D route: the v2-style work dir for tools/art/v3/v3_mech.py from an aligned, prepared sculpt.
    python3 -I tools/cad/starslayer_tripo_workdir.py SCULPT.npz BLOCKOUT.npz [WORKDIR]
SCULPT.npz (P, F in the original's rest frame, game mm; tools/art/v3/tripo_eval.py + sculpt_prep.py) is labelled by
the nearest part of the in-house blockout (tools/cad/starslayer_blockout.py, same frame): label = id of the ORIGINAL
mesh node that part replaces.  Transforms are identities (the sculpt already sits in the rest pose); the pipeline's
own segment stage then snaps the labels to the sculpt's panels."""
import json, sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/art")); sys.path.insert(0, str(Path(__file__).resolve().parent))
import hd_rig as R
from starslayer_workdir import NODE   # blockout part -> original node name (importing runs nothing: guarded below)


def smooth_labels(F, lab, passes=10, min_island=600):
    """Seams from the nearest-part rule follow the blockout's overlaps, not the sculpt: majority-vote each face with its
    edge neighbours, then give islands smaller than min_island faces to the label that surrounds them."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    n = len(F)
    e = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), axis=1)
    fi = np.tile(np.arange(n), 3)
    o = np.lexsort((e[:, 1], e[:, 0])); e, fi = e[o], fi[o]
    same = (e[1:] == e[:-1]).all(1)
    a, b = fi[:-1][same], fi[1:][same]
    A = coo_matrix((np.ones(2 * len(a)), (np.r_[a, b], np.r_[b, a])), shape=(n, n)).tocsr()
    K = int(lab.max()) + 1
    lab = lab.copy()
    for _ in range(passes):
        H = np.zeros((n, K)); H[np.arange(n), lab] = 1.0
        V = A @ H + 1.5 * H
        lab = V.argmax(1)
    for _ in range(3):
        for k in np.unique(lab):
            idx = np.flatnonzero(lab == k)
            sub = A[idx][:, idx]
            nc, cc = connected_components(sub, directed=False)
            if nc <= 1:
                continue
            sz = np.bincount(cc)
            big = sz.argmax()
            for c in np.flatnonzero(sz < min_island):
                if c == big:
                    continue
                m = idx[cc == c]
                nb = A[m].nonzero()[1]; nb = nb[lab[nb] != k]
                if len(nb):
                    lab[m] = np.bincount(lab[nb]).argmax()
    return lab


def ball(c, r, n_lat=10, n_lon=16):
    la = np.linspace(0, np.pi, n_lat + 1); lo = np.arange(n_lon) * 2 * np.pi / n_lon
    V = [[0, 0, r]] + [[r * np.sin(a) * np.cos(b), r * np.sin(a) * np.sin(b), r * np.cos(a)] for a in la[1:-1] for b in lo] + [[0, 0, -r]]
    V = np.array(V) + c; F = []
    for j in range(n_lon):
        F.append([0, 1 + j, 1 + (j + 1) % n_lon])
    for i in range(n_lat - 2):
        for j in range(n_lon):
            a, b = 1 + i * n_lon + j, 1 + i * n_lon + (j + 1) % n_lon
            F += [[a, a + n_lon, b], [b, a + n_lon, b + n_lon]]
    last = len(V) - 1
    for j in range(n_lon):
        F.append([last, 1 + (n_lat - 2) * n_lon + (j + 1) % n_lon, 1 + (n_lat - 2) * n_lon + j])
    return V, np.array(F)


def drum_x(c, r, half, n=14):
    a = np.arange(n) * 2 * np.pi / n
    V = [[c[0] + s, c[1] + r * np.cos(t), c[2] + r * np.sin(t)] for s in (-half, half) for t in a]
    V += [[c[0] - half, c[1], c[2]], [c[0] + half, c[1], c[2]]]
    V = np.array(V, float); F = []
    for j in range(n):
        k = (j + 1) % n
        F += [[j, n + j, k], [k, n + j, n + k], [2 * n, k, j], [2 * n + 1, n + j, n + k]]
    return V, np.array(F)


# joints whose pivot falls outside the generated armour get a ball or drum of our own at the pivot, so an actuator can
# close the seam (the right arm hangs 80 mm off its pivot; the right outer toe is a thin shell beside its pivot)
EXTRAS = [("ss_ruarm", "ball", (-2026, 450, 7197), 330), ("joint_rotoe", "drum", (-2136, -170, 188), 130)]


def main():
    sc = np.load(sys.argv[1]); bk = np.load(sys.argv[2])
    work = Path(sys.argv[3] if len(sys.argv) > 3 else "/mnt/nvme1n1p1/mc2-rework/work/starslayer_tripo"); work.mkdir(parents=True, exist_ok=True)
    og, ob = R.load_glb(str(ROOT / "game/assets/mechs/starslayer.glb"))
    names = [n.get("name", "") for n in og["nodes"]]
    # dense area-weighted samples of the blockout, each carrying its part's node id
    bP, bF = bk["P"].astype(float), bk["F"]
    t = bP[bF]; ar = np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1)
    rng = np.random.default_rng(7); i = rng.choice(len(bF), 300000, p=ar / ar.sum())
    u, v = rng.random((2, len(i))); f = u + v > 1; u[f], v[f] = 1 - u[f], 1 - v[f]
    S = t[i, 0] + u[:, None] * (t[i, 1] - t[i, 0]) + v[:, None] * (t[i, 2] - t[i, 0])
    node_of = np.array([names.index(NODE[str(n)]) for n in bk["names"]])[bk["part"][i]]
    P, F = sc["P"].astype(float), sc["F"]
    cen = P[F].mean(1)
    d, j = cKDTree(S).query(cen)
    lab = node_of[j]
    lab = smooth_labels(F, lab, passes=10, min_island=600)
    print("faces", len(F), "median distance to blockout", np.median(d).round(0), "mm, 95 %", np.percentile(d, 95).round(0))
    # the left forearm pod turns about joint_lgun: keep its seam near the pivot. Pod = the box below; luarm/lgun faces
    # inside it ride the pod, lgun faces outside it go back to the slab (the generated pod ran 1.1 m past the pivot)
    cen = P[F].mean(1); lg, la = names.index("ss_lgun"), names.index("ss_luarm")
    inb = ((cen[:, 0] > 1950) & (cen[:, 0] < 3100) & (cen[:, 1] > -2300) & (cen[:, 1] < 650) & (cen[:, 2] > 6100) & (cen[:, 2] < 7150))
    lab = lab.copy(); lab[inb & (lab == la)] = lg; lab[~inb & (lab == lg)] = la
    Vx, Fx, Lx = [P], [F], [lab]; off = len(P)
    for nm_, kind, c, r in EXTRAS:
        v_, f_ = ball(np.array(c, float), r) if kind == "ball" else drum_x(np.array(c, float), r, 260)
        Vx.append(v_); Fx.append(f_ + off); Lx.append(np.full(len(f_), names.index(nm_))); off += len(v_)
    P, F, lab = np.concatenate(Vx), np.concatenate(Fx), np.concatenate(Lx)
    V, F2, lab2 = P, F, lab          # one welded sculpt, a node id per face (the pipeline's segment stage snaps it)
    print({names[p]: int((lab2 == p).sum()) for p in sorted(set(lab2.tolist()))})
    for n in og["nodes"]:
        n.pop("mesh", None); n.pop("skin", None)
    for k in ("images", "textures", "samplers", "materials", "meshes", "skins"):
        og.pop(k, None)
    R.GlbWriter(og, ob).write(str(work / "skel.glb"))
    parent = {str(c): i_ for i_, n in enumerate(og["nodes"]) for c in n.get("children", [])}
    np.savez_compressed(work / "labels.npz", V=V, F=F2, lab=lab2)
    (work / "fit.json").write_text(json.dumps({
        "mech": "starslayer", "stl": "image-to-3D sculpt (tools/cad/starslayer_tripo_workdir.py)", "joints": "", "kind": "inhouse",
        "node_names": names, "parent": parent, "xform": {str(p): np.eye(4).tolist() for p in sorted(set(lab2.tolist()))},
        "pivots": {}, "legs": {}, "keys": [], "k": 1.0, "H": float(V[:, 2].max())}, indent=1))
    print("->", work)


if __name__ == "__main__":
    main()
