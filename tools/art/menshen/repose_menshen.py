#!/usr/bin/env python3
"""Re-pose UnrestedGuy's "Men Shen Omnimech (Gen 3)" B-O sculpt toward MC2's tall, symmetric stance.   (LANCE-37)
    python3 -I tools/art/menshen/repose_menshen.py IN.stl OUT.stl
CC BY-NC-SA 4.0 sculpt (https://www.thingiverse.com/thing:6315062); this script is our modification, so the output is
CC BY-NC-SA 4.0 as well.  The print is an assembly of 75 separate shells, with the two legs posed differently (one
upright with a long vertical tarsus, the other bent with the foot far forward).  We keep the upright leg, mirror it onto
the other side (so both legs stand in the same neutral pose), bring both feet down to the original's footprint
(forward toes less spread, back toe about half as long), and tuck the weapon pods 3 units in (about 0.75 m per side) and lift them 1.6 units (0.4 m).
Shells are moved rigidly; nothing is cut or stretched, so every panel line and actuator is the author's.
Component numbers are the shells ranked by triangle count (see the comments)."""
import sys
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

src, dst = sys.argv[1], sys.argv[2]
b = open(src, "rb").read(); n = int(np.frombuffer(b[80:84], "<u4")[0])
d = np.frombuffer(b[84:84 + 50 * n], dtype=np.dtype([("n", "<3f4"), ("v", "<9f4"), ("a", "<u2")]))
T = d["v"].reshape(-1, 3, 3).astype(float)
P = T.reshape(-1, 3); u, inv = np.unique(np.round(P, 3), axis=0, return_inverse=True); F = inv.reshape(-1, 3)
A = coo_matrix((np.ones(3 * len(F)), (F.ravel(), np.roll(F, 1, 1).ravel())), shape=(len(u), len(u)))
nc, cc = connected_components(A, directed=False)
fc = cc[F[:, 0]]; sz = np.bincount(fc, minlength=nc)
order = np.lexsort((np.arange(nc), -sz)); rank = np.empty(nc, int); rank[order] = np.arange(nc)   # rank 0 = biggest shell
assert nc == 75, nc
R = rank[fc]                                      # shell rank per face
# Shells are picked by geometry, not by index (ties in triangle count make the ranking unstable):
#   leg      centroid z < 22 and |y| <= 12.5; y > 0 (feet: x < 0) is the upright leg A (keep), the rest the bent leg B (drop)
#   toes     leg shells below z 9.5 that are not tall (the ankle and claw pieces); back claw: centroid x < -14.5
#   pods     the weapon pods and their side blocks: centroid z in 22..33, |y| >= 3.4, over 600 triangles
Y0, KY, X0, KX, TUCK, LIFT = 4.0, 0.55, -14.5, 0.45, 3.0, 1.6
cen = np.array([u[F[R == r]].reshape(-1, 3).mean(0) if (R == r).any() else np.zeros(3) for r in range(nc)])
ext = np.array([np.ptp(u[F[R == r]].reshape(-1, 3), axis=0) if (R == r).any() else np.zeros(3) for r in range(nc)])
cnt = np.bincount(R, minlength=nc)
LEG = {r for r in range(nc) if cen[r, 2] < 22 and abs(cen[r, 1]) <= 12.5}
# the feet of the two legs are told apart by x (leg B's toes lie at x > 5, some of them at y > 0), the rest by the sign of y
LEG_A = {r for r in LEG if (cen[r, 0] < 0 if cen[r, 2] < 9.5 else cen[r, 1] > 0)}
LEG_B = LEG - LEG_A
TOES_A = {r for r in LEG_A if cen[r, 2] < 9.5 and ext[r, 2] < 5}
BACK_TOE = {r for r in TOES_A if cen[r, 0] < X0}
PODS = {r for r in range(nc) if 22 <= cen[r, 2] <= 33 and abs(cen[r, 1]) >= 3.4 and cnt[r] > 600}
print("leg A", len(LEG_A), "leg B", len(LEG_B), "toes", len(TOES_A), "back toe", len(BACK_TOE), "pods", sorted(PODS))


def comp_tris(r):
    return F[R == r]


out_u, out_F = [], []
off = 0


def add(pts, tris):
    global off
    out_u.append(pts); out_F.append(tris + off); off += len(pts)


for r in range(nc):
    if r in LEG_B:
        continue
    f = comp_tris(r); idx = np.unique(f); mp = {int(k): i for i, k in enumerate(idx)}
    pts = u[idx].copy(); tri = np.vectorize(mp.get)(f) if len(f) else f
    if r in TOES_A:
        c = pts.mean(0)
        ty = Y0 + (c[1] - Y0) * KY
        tx = X0 + (c[0] - X0) * KX if r in BACK_TOE else c[0]
        pts[:, 1] += ty - c[1]; pts[:, 0] += tx - c[0]
    if r in PODS:
        pts[:, 1] -= np.sign(pts[:, 1].mean()) * TUCK
        pts[:, 2] += LIFT                         # clear the thigh tops: a thigh swinging under a pod went through it
    add(pts, tri)
    if r in LEG_A:                               # mirror y -> -y, flip the winding
        m = pts.copy(); m[:, 1] *= -1
        add(m, tri[:, [0, 2, 1]])
V = np.concatenate(out_u); FF = np.concatenate(out_F)
tris = V[FF]
nrm = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]); nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
rec = np.zeros(len(FF), dtype=np.dtype([("n", "<3f4"), ("v", "<9f4"), ("a", "<u2")]))
rec["n"] = nrm; rec["v"] = tris.reshape(-1, 9)
with open(dst, "wb") as f:
    f.write(b"Men Shen Gen 3 B-O re-posed; our modification of UnrestedGuy CC BY-NC-SA".ljust(80, b" ")[:80])
    f.write(np.uint32(len(FF)).tobytes()); f.write(rec.tobytes())
print(len(FF), "tris,", len(out_u), "pieces; bbox", V.min(0).round(1), V.max(0).round(1))
