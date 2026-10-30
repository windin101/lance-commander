#!/usr/bin/env python3
"""x-extent probes for a rigid fit: histogram of face-centroid x inside a side-view circle (y, z, r), one side (x > 0).
    python3 -I tools/art/v3/veh_probe.py WORKDIR y z r [rmin]"""
import sys, numpy as np
from pathlib import Path
w = Path(sys.argv[1]); y, z, r = map(float, sys.argv[2:5]); rmin = float(sys.argv[5]) if len(sys.argv) > 5 else 0
d = np.load(w / "labels.npz"); C = d["V"][d["F"]].mean(1)
m = (C[:, 0] > 0) & (np.hypot(C[:, 1] - y, C[:, 2] - z) < r) & (np.hypot(C[:, 1] - y, C[:, 2] - z) >= rmin)
x = C[m, 0]
h, e = np.histogram(x, bins=np.arange(0, 3200, 50))
for a, b in zip(e, h):
    if b: print(f"{int(a):5d} {b}")
