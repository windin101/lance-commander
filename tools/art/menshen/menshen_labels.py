#!/usr/bin/env python3
"""Menshen: label the v2 sculpt by whole shells instead of stl_rig's per-triangle nearest bone.   (LANCE-37)
    python3 -I tools/art/menshen/menshen_labels.py [WORK]       (WORK = /mnt/nvme1n1p1/mc2-rework/work/menshen)
The Gen 3 print is an assembly of separate shells, and stl_rig's triangle labels gave the 'hip' part the toes and bits of
both legs (1.1 m torso seams in the pose test).  Each shell goes to one part by its centroid, in the v2 frame (x lateral,
-y forward, z up; joints from tools/art/hd_v2/menshen.json):
  arms     z < 8000, |x| > 1700 (the weapon pods and their side blocks) -> ms_<side>uarm
  torso    z > 5200 otherwise (the hull), and the two nose rods at the front (y < -3000, z 4300..5200), which stl_rig's nearest-bone
           rule had given to the thighs: they then swung through the hull
  hip      z 4300..5200, |x| < 1000 and within 1.5 m of the hip joint in y (the hull's lower nose plates are torso)
  foot     z < 1300
  legs     the rest, by the nearest bone segment in the y-z plane: hip-knee ms_*uleg, knee-heel ms_*mleg, heel-ankle ms_*lleg
Writes WORK/labels.npz (backup labels_stl_rig.npz)."""
import json, shutil, sys
from pathlib import Path
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

W = Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/nvme1n1p1/mc2-rework/work/menshen")
z = np.load(W / "labels.npz"); V, F = z["V"], z["F"]
names = json.load(open(W / "fit.json"))["node_names"]
J = json.load(open(Path(__file__).resolve().parents[1] / "hd_v2/menshen.json"))["l"]
hip, knee, heel, ankle = (np.array(J[k], float) for k in ("hip", "knee", "heel", "ankle"))
n = len(V); A = coo_matrix((np.ones(3 * len(F)), (F.ravel(), np.roll(F, 1, 1).ravel())), shape=(n, n))
nc, cc = connected_components(A, directed=False); fc = cc[F[:, 0]]
cen = np.array([V[F[fc == c]].reshape(-1, 3).mean(0) for c in range(nc)])
cnt = np.bincount(fc, minlength=nc)


def seg_dist(p, a, b):
    t = np.clip(np.dot(p - a, b - a) / np.dot(b - a, b - a), 0, 1); return np.linalg.norm(p - (a + t * (b - a)))


new = np.zeros(nc, int); why = {}
for c in range(nc):
    x, y, zc = cen[c]; s = "l" if x > 0 else "r"
    if zc < 8000 and abs(x) > 1700 and zc > 4300 and cnt[c] > 150:
        part = f"ms_{s}uarm"
    elif zc > 5200 or (y < -3000 and zc > 4300 and abs(x) < 1000):   # the two nose rods (shells 14 and 55 of the print) belong to the hull
        part = "ms_torso"
    elif 4300 <= zc <= 5200 and abs(x) < 1000 and abs(y - hip[0]) < 1500:
        part = "ms_hip"
    elif zc < 1300:
        part = f"ms_{s}foot"
    else:
        p = np.array([y, zc])
        d = {f"ms_{s}uleg": seg_dist(p, hip, knee), f"ms_{s}mleg": seg_dist(p, knee, heel), f"ms_{s}lleg": seg_dist(p, heel, ankle)}
        part = min(d, key=d.get)
    new[c] = names.index(part); why[c] = part
shutil.copy(W / "labels.npz", W / "labels_stl_rig.npz")
np.savez_compressed(W / "labels.npz", V=V, F=F, lab=new[fc])
import collections
print(collections.Counter(why.values()))
