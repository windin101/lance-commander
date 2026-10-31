"""Blood Asp: tie each forearm pod to its pivot with geometry of our own.   (LANCE-37 follow-up)
    python3 -I tools/cad/bloodasp_pivot_yokes.py [WORKDIR]
Run after bloodasp_tripo_workdir.py and bloodasp_toe_mirror.py (it edits WORKDIR/labels.npz).
The generated arms, shoulder rifles and toes sit up to a metre off their pivots (1-1.5 m seams in the pose test).
Per side: a pin (cylinder about X, on the pivot, labelled as the pod) joined by a strut to the nearest armour of the pod's main body, and
a collar (cylinder about X, wider than the pin, labelled as the upper arm) joined by a strut to the arm's nearest
armour.  The pin turns inside the collar, a surface of revolution about the hinge axis, so the seam stays closed."""
import json, sys
from pathlib import Path
import numpy as np
from scipy.spatial import ConvexHull
# Generalised from hollander_pivot_yokes.py: for each (child part, parent part, pivot) a pin of the child at the pivot, a collar of the
# parent, and a strut from each to the nearest armour of its part's main body, so the joint stays closed at any hinge angle.
work = Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/nvme1n1p1/mc2-rework/work/bloodasp_tripo")
z = np.load(work / "labels.npz"); V, F, lab = z["V"], z["F"], z["lab"]
names = json.load(open(work / "fit.json"))["node_names"]
cen = V[F].mean(1)


def hull(pts):
    pts = np.asarray(pts, float); h = ConvexHull(pts); c = pts.mean(0); out = []
    for s in h.simplices:
        a, b, d = pts[s]; s = list(s)
        if np.dot(np.cross(b - a, d - a), a - c) < 0:
            s = [s[0], s[2], s[1]]
        out.append(s)
    return pts, np.array(out)


def cylx(c, r, half, n=16):
    a = np.arange(n) * 2 * np.pi / n
    return [[c[0] + s, c[1] + r * np.cos(t), c[2] + r * np.sin(t)] for s in (-half, half) for t in a]


def main_body(label):
    """Centroids of the largest connected piece of a part (the pod body, not a stray island)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    m = np.flatnonzero(lab == label); f = F[m]
    idx = np.unique(f); mp = -np.ones(len(V), int); mp[idx] = np.arange(len(idx)); g = mp[f]
    A = coo_matrix((np.ones(3 * len(g)), (g.ravel(), np.roll(g, 1, 1).ravel())), shape=(len(idx), len(idx)))
    nc, cc = connected_components(A, directed=False)
    big = np.bincount(cc[g[:, 0]]).argmax()
    return cen[m][cc[g[:, 0]] == big]


def boxpts(c, h):
    return [[c[0] + sx * h, c[1] + sy * h, c[2] + sz * h] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]



JOINTS = []
for s_, sd in ((-1, "r"), (1, "l")):
    JOINTS += [(f"ba_{sd}uarm", "ba_torso", (s_ * 2723, 532, 9474), 330), (f"ba_{sd}gun", f"ba_{sd}uarm", (s_ * 4458, 531, 7298), 330),
               (f"joint_{sd}shouldergun", "ba_torso", (s_ * 2000, 488, 9900), 300)]
    for t, x, y in (("btoe", 3297, 1016), ("itoe", 2347, -1282), ("ftoe", 3297, -1782), ("otoe", 4143, -1282)):
        JOINTS.append((f"joint_{sd}{t}", f"ba_{sd}foot", (s_ * x, y, 243), 170))
Vs, Fs, Ls = [V], [F], [lab]; off = len(V)
for child, parent, piv, r in JOINTS:
    P = np.array(piv, float); ci, pi = names.index(child), names.index(parent)
    def nearest(label):
        c = main_body(label); return c[np.linalg.norm(c - P, axis=1).argmin()]
    Nc, Np = nearest(ci), nearest(pi)
    solids = [(ci, cylx(P, r, 300)), (ci, boxpts(Nc, r * 0.8) + cylx(P, r, 200)),
              (pi, cylx(P, r * 1.6, 200)), (pi, boxpts(Np, r * 0.8) + cylx(P, r * 1.6, 200))]
    for label, pts in solids:
        p, f = hull(pts)
        Vs.append(p); Fs.append(f + off); Ls.append(np.full(len(f), label)); off += len(p)
np.savez_compressed(work / "labels.npz", V=np.concatenate(Vs), F=np.concatenate(Fs), lab=np.concatenate(Ls))
print("yokes added for", len(JOINTS), "joints ->", work)
