#!/usr/bin/env python3
"""Vehicle kit viewer (LANCE-19): painter's-algorithm orthographic render of a rigid fit's labels.npz (game frame, mm, Z up,
forward = -Y), flat shaded and coloured by part, with a mm grid.

    python3 -I tools/art/v3/veh_view.py WORKDIR out.png [--ppm 0.2] [--step 500] [--only part,part]
        [--views side,top,front,iso:YAW:PITCH] [--xrange xmin,xmax] [--prep unit] [--crop y0,y1,z0,z1]
side = (y right, z up), top = (x right, y up), front = (x right, z up). --prep overlays the unit's veh_prep.json wheel
circles (green) and belt path (yellow) on the first (side) view."""
import argparse, json, sys
from pathlib import Path
import numpy as np
import cv2

PAL = [(230, 90, 70), (70, 160, 230), (90, 200, 110), (230, 190, 60), (190, 100, 220), (80, 210, 210), (240, 140, 60),
       (150, 150, 150), (255, 120, 180), (160, 220, 60)]


def paint(U, Vv, D, shade, col, lo, hi, ppm, step, title, sx=1.0):
    """U, Vv: (n,3) projected vertex coords of each face (mm), D: depth per face (far first)."""
    W = int((hi[0] - lo[0]) * ppm) + 1; H = int((hi[1] - lo[1]) * ppm) + 1
    img = np.full((H, W, 3), 25, np.uint8)
    order = np.argsort(-D)
    px = ((U - lo[0]) * ppm); py = (H - 1 - (Vv - lo[1]) * ppm)
    pts = np.stack([px, py], -1).astype(np.int32)
    cs = np.clip(col * shade[:, None], 0, 255).astype(np.uint8)
    for i in order:
        cv2.fillConvexPoly(img, pts[i], tuple(int(c) for c in cs[i]))
    for gx in np.arange(np.ceil(lo[0] / step) * step, hi[0], step):
        x = int((gx - lo[0]) * ppm); cv2.line(img, (x, 0), (x, H - 1), (60, 60, 60), 1)
        cv2.putText(img, f"{int(gx)}", (x + 2, H - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
    for gy in np.arange(np.ceil(lo[1] / step) * step, hi[1], step):
        y = H - 1 - int((gy - lo[1]) * ppm); cv2.line(img, (0, y), (W - 1, y), (60, 60, 60), 1)
        cv2.putText(img, f"{int(gy)}", (2, y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
    cv2.putText(img, title, (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    return img


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("work"); ap.add_argument("out")
    ap.add_argument("--ppm", type=float, default=0.2); ap.add_argument("--step", type=float, default=500)
    ap.add_argument("--only"); ap.add_argument("--views", default="side,top,front")
    ap.add_argument("--xrange"); ap.add_argument("--prep"); ap.add_argument("--crop")
    a = ap.parse_args()
    w = Path(a.work); z = np.load(w / "labels.npz"); f = json.loads((w / "fit.json").read_text())
    V, F, lab = z["V"], z["F"], z["lab"]; names = f["node_names"]
    if a.only:
        sel = np.isin(np.array(names)[lab], a.only.split(",")); F, lab = F[sel], lab[sel]
    if a.xrange:
        x0, x1 = map(float, a.xrange.split(",")); cx = V[F][:, :, 0].mean(1); sel = (cx >= x0) & (cx <= x1); F, lab = F[sel], lab[sel]
    T = V[F]; N = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-9
    pl = sorted(set(lab.tolist())); col = np.array([PAL[pl.index(l) % len(PAL)][::-1] for l in lab], float)
    ttl = "  ".join(f"{names[l]}={PAL[pl.index(l) % len(PAL)]}" for l in pl[:3])
    outs = []
    for view in a.views.split(","):
        if view == "side":    # looking along -x: sees the +x side
            Q = T[:, :, [1, 2, 0]]; Nq = N[:, [1, 2, 0]]; D = -T[:, :, 0].mean(1)
        elif view == "top":
            Q = T[:, :, [0, 1, 2]]; Nq = N; D = -T[:, :, 2].mean(1)
        elif view == "front":
            Q = T[:, :, [0, 2, 1]]; Nq = N[:, [0, 2, 1]]; D = -T[:, :, 1].mean(1)
        else:
            _, yw, pt = (view.split(":") + ["35", "30"])[:3]
            yw, pt = np.radians(float(yw)), np.radians(float(pt))
            Rz = np.array([[np.cos(yw), -np.sin(yw), 0], [np.sin(yw), np.cos(yw), 0], [0, 0, 1]])
            P3 = T @ Rz.T; Nz = N @ Rz.T
            Q = np.stack([P3[..., 0], P3[..., 2] * np.cos(pt) + P3[..., 1] * np.sin(pt), P3[..., 1] * np.cos(pt) - P3[..., 2] * np.sin(pt)], -1)
            Nq = np.stack([Nz[:, 0], Nz[:, 2] * np.cos(pt) + Nz[:, 1] * np.sin(pt), Nz[:, 1] * np.cos(pt) - Nz[:, 2] * np.sin(pt)], -1)
            D = -Q[:, :, 2].mean(1)
        # shade: facing the viewer (+ third axis toward the viewer for side/top/front: depth axis is Q[...,2], viewer at -inf for D)
        shade = 0.35 + 0.65 * np.clip(0.45 + 0.55 * np.abs(Nq[:, 2]) + 0.15 * Nq[:, 1] - 0.1 * Nq[:, 0], 0, 1)
        lo = (Q[..., 0].min() - 100, Q[..., 1].min() - 100); hi = (Q[..., 0].max() + 100, Q[..., 1].max() + 100)
        if view == "side" and a.crop:
            y0, y1, z0, z1 = map(float, a.crop.split(",")); lo, hi = (y0, z0), (y1, z1)
        img = paint(Q[..., 0], Q[..., 1], D, shade, col, lo, hi, a.ppm, a.step, f"{w.name} {view}  {ttl}")
        if a.prep and view == "side":
            sys.path.insert(0, str(Path(__file__).resolve().parent)); import veh_prep as VP
            cfg = VP.load_cfg(a.prep); Hh0 = img.shape[0]
            pxy = lambda y, zz: (int((y - lo[0]) * a.ppm), Hh0 - 1 - int((zz - lo[1]) * a.ppm))
            for (y, zz, r, *_) in (cfg.get("wheels") or {}).get("list", []):
                cv2.circle(img, pxy(y, zz), int(r * a.ppm), (0, 255, 0), 1)
            tc = cfg.get("tracks") or {}
            if tc.get("mode") == "loop":
                yy, zz, ss, t, L = VP.loop_path(tc, 10.0)
                cv2.polylines(img, [np.array([pxy(y, z_) for y, z_ in zip(yy, zz)], np.int32)], True, (0, 255, 255), 1)
        outs.append(img)
    Hh = max(o.shape[0] for o in outs)
    outs = [np.pad(o, ((0, Hh - o.shape[0]), (0, 4), (0, 0))) for o in outs]
    cv2.imwrite(a.out, np.concatenate(outs, 1))
    print(a.out, [o.shape for o in outs])


if __name__ == "__main__":
    main()
