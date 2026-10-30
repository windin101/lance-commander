#!/usr/bin/env python3
"""Per-part face count and bounding box (mm, game frame) of a rigid fit. python3 -I veh_bbox.py WORKDIR"""
import sys, json, numpy as np
from pathlib import Path
w = Path(sys.argv[1]); d = np.load(w / "labels.npz"); f = json.loads((w / "fit.json").read_text())
V, F, lab = d["V"], d["F"], d["lab"]
for l in sorted(set(lab.tolist())):
    P = V[np.unique(F[lab == l])]
    print(f"{f['node_names'][l]:18s} {int((lab == l).sum()):7d} faces  min {np.round(P.min(0)).astype(int).tolist()}  max {np.round(P.max(0)).astype(int).tolist()}")
