#!/usr/bin/env python3
"""Wheel circles of a rigid fit by Hough transform on the side silhouette of the outermost x layer (faces with centroid |x| >= xmax - band).
    python3 -I tools/art/v3/veh_wheelfind.py WORKDIR [band 500] [rmin 150] [rmax 900]   -> prints (y, z, r) mm candidates, +x side"""
import sys, numpy as np, cv2
from pathlib import Path
w = Path(sys.argv[1]); band = float(sys.argv[2]) if len(sys.argv) > 2 else 500; rmin = float(sys.argv[3]) if len(sys.argv) > 3 else 150; rmax = float(sys.argv[4]) if len(sys.argv) > 4 else 900
d = np.load(w / "labels.npz"); V, F = d["V"], d["F"]; T = V[F]; C = T.mean(1)
xm = C[:, 0].max(); sel = (C[:, 0] > xm - band)
T = T[sel]; ppm = 0.25
y0, z0 = T[..., 1].min() - 100, -50.0
W = int((T[..., 1].max() - y0 + 100) * ppm); H = int((T[..., 2].max() + 100) * ppm)
img = np.zeros((H, W), np.uint8)
for t in T:
    cv2.fillConvexPoly(img, np.stack([(t[:, 1] - y0) * ppm, H - 1 - (t[:, 2] - z0) * ppm], 1).astype(np.int32), 255)
edges = cv2.Canny(cv2.GaussianBlur(img, (5, 5), 0), 50, 150)
cs = cv2.HoughCircles(img, cv2.HOUGH_GRADIENT, dp=1, minDist=int(rmin * ppm), param1=100, param2=22, minRadius=int(rmin * ppm), maxRadius=int(rmax * ppm))
print("xmax", round(float(xm)), "band", band)
if cs is not None:
    for x, y, r in sorted(cs[0].tolist()):
        print(f"[{round(x / ppm + y0)}, {round((H - 1 - y) / ppm + z0)}, {round(r / ppm)}]")
