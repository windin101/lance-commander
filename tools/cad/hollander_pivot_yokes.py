"""Hollander: tie each forearm pod to its pivot with geometry of our own.   (LANCE-37 follow-up)
    python3 -I tools/cad/hollander_pivot_yokes.py [WORKDIR]
Run after hollander_tripo_workdir.py and hollander_gun_extend.py (it edits WORKDIR/labels.npz).
The generated forearm pods hang 270 to 480 mm off joint_rgun / joint_lgun, the arm's elbow hinge (it turns only about X,
70 degrees at most), so a pod swung off its upper arm in the last FallForward frame, which the game freezes on a wreck.
Per side: a pin (cylinder about X, on the pivot, labelled as the pod) joined by a strut to the nearest armour of the pod's main body, and
a collar (cylinder about X, wider than the pin, labelled as the upper arm) joined by a strut to the arm's nearest
armour.  The pin turns inside the collar, a surface of revolution about the hinge axis, so the seam stays closed."""
import json, sys
from pathlib import Path
import numpy as np
from scipy.spatial import ConvexHull

work = Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/nvme1n1p1/mc2-rework/work/hollander_tripo")
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


# the nearest-blockout labelling gave the middle of each forearm to the upper arm, leaving the pod's muzzle block as an
# island 1.2 m from its pivot: faces of the upper arm that lie inside the forearm box belong to the pod
for side, lo, hi in (("l", (1550, -2300, 4300), (2700, 700, 5300)), ("r", (-2900, -2300, 4300), (-1650, 700, 5300))):
    inb = np.all((cen >= lo) & (cen <= hi), axis=1) & (lab == names.index(f"ho_{side}uarm"))
    print(side, "faces moved from the upper arm to the pod:", int(inb.sum()))
    lab = lab.copy(); lab[inb] = names.index(f"ho_{side}gun")
Vs, Fs, Ls = [V], [F], [lab]; off = len(V)
for side, piv in (("r", (-2165, 114, 4798)), ("l", (2224, 114, 4798))):
    P = np.array(piv, float)
    pod, arm = names.index(f"ho_{side}gun"), names.index(f"ho_{side}uarm")
    def nearest(label):
        c = main_body(label); return c[np.linalg.norm(c - P, axis=1).argmin()]
    Np, Ap = nearest(pod), nearest(arm)
    print(side, "pod nearest", Np.round(), "arm nearest", Ap.round())
    solids = [(pod, cylx(P, 190, 430)),
              (pod, boxpts(Np, 170) + cylx(P, 190, 300)),
              (arm, cylx(P, 310, 230)),
              (arm, boxpts(Ap, 170) + cylx(P, 310, 230))]
    for label, pts in solids:
        p, f = hull(pts)
        Vs.append(p); Fs.append(f + off); Ls.append(np.full(len(f), label)); off += len(p)
np.savez_compressed(work / "labels.npz", V=np.concatenate(Vs), F=np.concatenate(Fs), lab=np.concatenate(Ls))
print("yokes added ->", work)
