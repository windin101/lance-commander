"""swarmlrmc prep: cut the SRM launcher off RGriffin65's Semi-Modular Weapons Carrier (SRM) and enlarge/raise it
so it reads like the original's big turntable launcher. Writes hull.stl + launcher.stl (raw mm, Z up) beside this folder.
usage: python3 -I split_launcher.py <in.stl> <outdir> [sx sy sz lift_mm tilt_deg pedestal_r_mm]"""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path.home() / "Code/mc2-remake/tools/art"))
import stl_rig  # noqa: E402

def write_stl(path, T):
    T = np.asarray(T, np.float32)
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    rec = np.zeros(len(T), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    rec["n"], rec["v"] = n, T
    with open(path, "wb") as f:
        f.write(b"\0" * 80); f.write(np.uint32(len(T)).tobytes()); f.write(rec.tobytes())

def cylinder(cx, cy, z0, z1, r, n=6, k=30):
    """Hex pedestal, finely subdivided so it clears stl_hd's min_share (it is a component of its own)."""
    a = np.linspace(0, 2 * np.pi, n, endpoint=False) + np.pi / n
    P = np.c_[cx + r * np.cos(a), cy + r * np.sin(a)]
    T = []
    for i in range(n):
        p, q = P[i], P[(i + 1) % n]
        for u in range(k):
            a0, a1 = p + (q - p) * u / k, p + (q - p) * (u + 1) / k
            for v in range(k):
                b0, b1 = z0 + (z1 - z0) * v / k, z0 + (z1 - z0) * (v + 1) / k
                T += [[[*a0, b0], [*a1, b0], [*a1, b1]], [[*a0, b0], [*a1, b1], [*a0, b1]]]
        T += [[[cx, cy, z1], [*p, z1], [*q, z1]], [[cx, cy, z0], [*q, z0], [*p, z0]]]
    return np.array(T)

T = stl_rig.load_stl(sys.argv[1]); out = Path(sys.argv[2])
sx, sy, sz, lift, tilt, pr = (list(map(float, sys.argv[3:9])) + [1, 1, 1, 0, 0, 0][len(sys.argv[3:9]):]) if len(sys.argv) > 3 else (1, 1, 1, 0, 0, 0)
X0, Z0 = 3.6, 7.3
C = T.mean(1)
m = (C[:, 0] > X0) & (C[:, 2] > Z0)
H, L = T[~m], T[m].copy()
P = L.reshape(-1, 3)
lo, hi = P.min(0), P.max(0)
c = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])
P = (P - c) * [sx, sy, sz]
t = np.radians(tilt)  # tilt about Y: front edge (towards -x, the cab) ... sign chosen by tilt
Ry = np.array([[np.cos(t), 0, np.sin(t)], [0, 1, 0], [-np.sin(t), 0, np.cos(t)]])
P = P @ Ry.T
P[:, 2] += c[2] + lift - min(0, P[:, 2].min())
P[:, :2] += c[:2]
L = P.reshape(-1, 3, 3)
if pr > 0:
    L = np.r_[L, cylinder(c[0], c[1], Z0 - 0.3, c[2] + lift + 0.5, pr)]
write_stl(out / "hull.stl", H); write_stl(out / "launcher.stl", L)
print("launcher", m.sum(), "tris; raw box", lo.round(2), hi.round(2), "-> new", L.reshape(-1, 3).min(0).round(2), L.reshape(-1, 3).max(0).round(2))
