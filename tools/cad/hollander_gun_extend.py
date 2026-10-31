"""Hollander: raise and lengthen the generated Gauss barrel with our own CAD segment.   (LANCE-37 follow-up)
    python3 -I tools/cad/hollander_gun_extend.py [WORKDIR] [--tip -7200] [--axis-z 7020]
Reads WORKDIR/labels.npz (V, F, lab per face, node ids; tools/cad/hollander_tripo_workdir.py) and writes it back with:
  - the generated barrel (joint_gun faces forward of y -1950: barrel, jacket, collars, muzzle) detached and lifted so
    its axis runs along the top of the torso (axis z 7020, the receiver's top is 7100);
  - a saddle hull joining the receiver front to the lifted barrel;
  - an extension of our own: slender barrel (r 150), coil collars (r 250) and a muzzle brake out to y = TIP,
    all on joint_gun.
The original's barrel reaches 1.42 torso depths forward of the chest front (tip y -3950, torso y +-1029); ours is
deeper (chest front y -1654, depth 3900), so TIP -7200 matches that ratio."""
import json, sys
from pathlib import Path
import numpy as np
from scipy.spatial import ConvexHull

args = [a for a in sys.argv[1:] if not a.startswith("--")]
opt = {sys.argv[i]: sys.argv[i + 1] for i in range(1, len(sys.argv) - 1) if sys.argv[i].startswith("--")}
work = Path(args[0] if args else "/mnt/nvme1n1p1/mc2-rework/work/hollander_tripo")
tip = float(opt.get("--tip", -7200)); axz = float(opt.get("--axis-z", 7020)); cut = float(opt.get("--cut", -1950))
z = np.load(work / "labels.npz"); V, F, lab = z["V"], z["F"], z["lab"]
names = json.load(open(work / "fit.json"))["node_names"]
g = names.index("joint_gun")
cen = V[F].mean(1)
bar = (lab == g) & (cen[:, 1] < cut)
far = (lab == g) & (cen[:, 1] < -3300)
ax0 = cen[far][:, 2].mean(); axx = cen[far][:, 0].mean()
dz = axz - ax0
print(f"barrel faces {bar.sum()}, axis x {axx:.0f} z {ax0:.0f} -> lift {dz:.0f}")
# detach and lift
idx = np.unique(F[bar]); remap = -np.ones(len(V), int); remap[idx] = len(V) + np.arange(len(idx))
Vn = V[idx].copy(); Vn[:, 2] += dz
V2 = np.concatenate([V, Vn]); F2 = F.copy(); F2[bar] = remap[F[bar]]


def hull(pts):
    pts = np.asarray(pts, float); h = ConvexHull(pts); c = pts.mean(0); out = []
    for s in h.simplices:
        a, b, d = pts[s]; s = list(s)
        if np.dot(np.cross(b - a, d - a), a - c) < 0:
            s = [s[0], s[2], s[1]]
        out.append(s)
    return pts, np.array(out)


def cyl(c, r, half, n=16):
    a = np.arange(n) * 2 * np.pi / n
    return hull([[c[0] + r * np.cos(t), c[1] + s, c[2] + r * np.sin(t)] for s in (-half, half) for t in a])


solids = []
# saddle: from the receiver front (y -1500) to the start of the lifted barrel (y -2100), spanning both
ymin = V[idx][:, 1].max() if False else cut - 200
solids.append(hull([[x, y, zz] for x in (axx - 330, axx + 330) for y in (-2150, -1450) for zz in (6350, axz + 150)]))
solids.append(hull([[x, y, zz] for x in (axx - 520, axx + 520) for y in (-1950, -1500) for zz in (6250, 6900)]))
y_start = float(V[idx][:, 1].min())            # the generated muzzle end, y about -4200
solids.append(cyl((axx, (y_start + tip) / 2, axz), 150, abs(tip - y_start) / 2 + 60))          # slender barrel
for k, y in enumerate(np.linspace(y_start - 650, tip + 700, 4)):
    solids.append(cyl((axx, y, axz), 255, 70))                                                  # coil collars
solids.append(cyl((axx, tip + 120, axz), 215, 160))                                             # muzzle brake
Vs, Fs, Ls = [V2], [F2], [lab]; off = len(V2)
for p, f in solids:
    Vs.append(p); Fs.append(f + off); Ls.append(np.full(len(f), g)); off += len(p)
np.savez_compressed(work / "labels.npz", V=np.concatenate(Vs), F=np.concatenate(Fs), lab=np.concatenate(Ls))
print("tip y", tip, "->", work)
