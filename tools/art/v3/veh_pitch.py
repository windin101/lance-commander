#!/usr/bin/env python3
"""Link pitch of a kit's belt: autocorrelation of the face-centroid density along y in a z band of the lower run.
    python3 -I tools/art/v3/veh_pitch.py WORKDIR zlo zhi ylo yhi [xmin xmax]    -> prints the strongest period in 120..500 mm"""
import sys, numpy as np
from pathlib import Path
w = Path(sys.argv[1]); zlo, zhi, ylo, yhi = map(float, sys.argv[2:6])
x0, x1 = (float(sys.argv[6]), float(sys.argv[7])) if len(sys.argv) > 7 else (0, 1e9)
d = np.load(w / "labels.npz"); C = d["V"][d["F"]].mean(1)
m = (C[:, 2] > zlo) & (C[:, 2] < zhi) & (C[:, 1] > ylo) & (C[:, 1] < yhi) & (C[:, 0] > x0) & (C[:, 0] < x1)
h, e = np.histogram(C[m, 1], bins=np.arange(ylo, yhi, 5.0)); h = h - h.mean()
ac = np.correlate(h, h, "full")[len(h) - 1:]; ac /= ac[0]
lag = np.arange(len(ac)) * 5.0
sel = (lag > 120) & (lag < 500)
k = np.argmax(np.where(sel, ac, -9)); print("pitch", lag[k], "mm  corr", round(float(ac[k]), 2), " faces", int(m.sum()))
for kk in np.argsort(-np.where(sel, ac, -9))[:5]: print(" ", lag[kk], round(float(ac[kk]), 2))
p = lag[k]
yy = C[m, 1]; ph = np.mod(yy, p); hh, ee = np.histogram(ph, bins=int(p // 5), range=(0, p))
g = (ee[np.argmin(np.convolve(np.r_[hh, hh, hh], np.ones(5) / 5, "same")[len(hh):2 * len(hh)])] + 2.5)
cands = [g + p * n for n in range(int(np.floor((ylo - g) / p)), int(np.ceil((yhi - g) / p)) + 1)]
print("gap phase", round(float(g), 1), " gap_y near 0:", round(float(min(cands, key=abs)), 1), "(a gap between two links, mm)")
