#!/usr/bin/env python3
"""Anubis: replace the mech's LEFT (+x) wing assembly with a mirror of the right one.   (LANCE-37 defect fix)
    python3 -I tools/cad/anubis_mirror_wing.py [WORKDIR]
Tripo saw the front, left and back views, so one wing came out thinner, with a ragged top edge and a misaligned tube
grid.  Faces of the torso part in the wing region (|x - 14| >= 590, z > 6000, y > -500) on the left are dropped, and the
right wing's faces are copied across the centre plane x = 14 with the winding flipped, labelled torso like the rest.
Reads and rewrites WORKDIR/labels.npz (backup labels_before_mirror.npz)."""
import json, shutil, sys
from pathlib import Path
import numpy as np

work = Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/nvme1n1p1/mc2-rework/work/anubis_tripo")
X0, T, ZMIN, YMIN = 14.0, 590.0, 6000.0, -500.0
z = np.load(work / "labels.npz"); V, F, lab = z["V"], z["F"], z["lab"]
tor = json.load(open(work / "fit.json"))["node_names"].index("AN_torso")
C = V[F].mean(1)
reg = (lab == tor) & (C[:, 2] > ZMIN) & (C[:, 1] > YMIN)
left = reg & (C[:, 0] - X0 >= T); right = reg & (X0 - C[:, 0] >= T)
print("left wing faces dropped", int(left.sum()), "right wing faces mirrored", int(right.sum()))
shutil.copy(work / "labels.npz", work / "labels_before_mirror.npz")
idx = np.unique(F[right]); remap = -np.ones(len(V), int); remap[idx] = len(V) + np.arange(len(idx))
Vn = V[idx].copy(); Vn[:, 0] = 2 * X0 - Vn[:, 0]
Fn = remap[F[right]][:, [0, 2, 1]]
keep = ~left
V2 = np.concatenate([V, Vn]); F2 = np.concatenate([F[keep], Fn]); L2 = np.concatenate([lab[keep], np.full(len(Fn), tor)])
np.savez_compressed(work / "labels.npz", V=V2, F=F2, lab=L2)
print("->", work)
