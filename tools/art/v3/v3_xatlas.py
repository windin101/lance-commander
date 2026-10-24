"""UV atlas for the v3 game mesh with xatlas (pip `xatlas`, run with a Python that has it, e.g.
/mnt/nvme1n1p1/mc2-rework/v3/venv/bin/python):

    python v3_xatlas.py LOW_GEO.npz OUT.npz --res 2048 --padding 3 --minor 0.5

Each (part, kind) group is its own mesh, so charts never cross parts or kinds; contact caps and actuators are
added at --minor scale so they take less of the atlas. OUT.npz: P, F, part, kind, uv (per corner, v up)."""
import argparse
import numpy as np
import xatlas

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("out")
ap.add_argument("--res", type=int, default=2048)
ap.add_argument("--padding", type=int, default=3)
ap.add_argument("--minor", type=float, default=0.5)
ap.add_argument("--max-cost", type=float, default=2.0)
ap.add_argument("--normal-dev", type=float, default=2.0)
ap.add_argument("--brute", type=int, default=0)
ap.add_argument("--hidden", help="npy per face: UV scale (1 = full density) for faces rarely seen")
a = ap.parse_args()
z = np.load(a.src)
P, F, part, kind = z["P"] / 1000.0, z["F"], z["part"], z["kind"]
scale_face = np.load(a.hidden) if a.hidden else np.ones(len(F))
if len(scale_face) != len(F):   # from a different decimation: ignore (stage glassdensity regenerates it)
    print("uv scale ignored: face count changed"); scale_face = np.ones(len(F))
atlas = xatlas.Atlas()
groups = []
for p in np.unique(part):
    for k in np.unique(kind[part == p]):
        for hs in np.unique(scale_face[(part == p) & (kind == k)]):
            m = np.flatnonzero((part == p) & (kind == k) & (scale_face == hs))
            used = np.unique(F[m]); remap = -np.ones(len(P), int); remap[used] = np.arange(len(used))
            s = (a.minor if k != 0 else 1.0) * hs
            atlas.add_mesh((P[used] * s).astype(np.float32), remap[F[m]].astype(np.uint32))
            groups.append(m)
ap2 = {}
co = xatlas.ChartOptions()
co.max_cost = a.max_cost
co.normal_deviation_weight = a.normal_dev
co.max_iterations = 4
po = xatlas.PackOptions()
po.resolution = a.res
po.padding = a.padding
po.bilinear = True
po.rotate_charts = True
po.bruteForce = bool(a.brute)
atlas.generate(co, po)
uv = np.zeros((len(F), 3, 2), np.float32)
for i, m in enumerate(groups):
    vmap, idx, uvs = atlas[i]
    uv[m] = uvs[idx]
print(f"XATLAS charts {atlas.chart_count} atlas {atlas.width}x{atlas.height} utilization {float(np.atleast_1d(atlas.utilization)[0]):.3f}")
np.savez_compressed(a.out, P=z["P"], F=F, part=part, kind=kind, uv=uv.reshape(-1, 2))
