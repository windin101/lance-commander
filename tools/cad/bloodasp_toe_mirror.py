#!/usr/bin/env python3
"""Blood Asp: the Tripo mesh lost the LEFT outer toe (33 sculpt faces, the pipeline then dropped the part).  Replace it with a
mirror of the right outer toe across the centre plane x = -1 (the original's joints are 2 mm off symmetric).
    python3 -I tools/cad/bloodasp_toe_mirror.py [WORKDIR]       (edits WORKDIR/labels.npz, backup labels_before_toe.npz)"""
import json, shutil, sys
from pathlib import Path
import numpy as np
work = Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/nvme1n1p1/mc2-rework/work/bloodasp_tripo")
z = np.load(work / "labels.npz"); V, F, lab = z["V"], z["F"], z["lab"]
names = json.load(open(work / "fit.json"))["node_names"]
l, r = names.index("joint_lotoe"), names.index("joint_rotoe")
shutil.copy(work / "labels.npz", work / "labels_before_toe.npz")
idx = np.unique(F[lab == r]); remap = -np.ones(len(V), int); remap[idx] = len(V) + np.arange(len(idx))
Vn = V[idx].copy(); Vn[:, 0] = -2 - Vn[:, 0]
Fn = remap[F[lab == r]][:, [0, 2, 1]]
keep = lab != l
np.savez_compressed(work / "labels.npz", V=np.concatenate([V, Vn]), F=np.concatenate([F[keep], Fn]), lab=np.concatenate([lab[keep], np.full(len(Fn), l)]))
print("mirrored", len(Fn), "faces into joint_lotoe")
