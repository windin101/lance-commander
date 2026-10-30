#!/usr/bin/env python3
"""Hunter (LANCE-18, 2026-10-30): split the two track belts out of the fused hull of the rigid fit.

    python3 -I tools/art/v3/hunter_prep.py

Reads /mnt/nvme1n1p1/mc2-rework/work/hunter_rigid (tools/art/v3/v3_rigid.py) and writes .../hunter_tracks with
two extra parts, track_l (+X) and track_r, riding their own nodes (child of the Hunter root, at the belt's x centre,
so VehicleRig reads the track gauge from them), plus hunter_base.glb: the original model's node tree with those
nodes added, which v3_mech.py's Rig reads (config "base_glb").

The kit models only the visible lower arc of each belt (a chain of link blocks fused to the road wheels and the
hull), so the belt is found geometrically: in the side view (YZ) the belt is the layer of the lower silhouette of
the track-wide x range [770, 1470] mm, one link thick (96 mm normal to the path). Faces whose centroid lies in
that layer go to the track part; the road wheels (the half discs above the belt) stay with the hull."""
import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

HERE = Path(__file__).resolve().parent
ART = HERE.parent
sys.path.insert(0, str(ART))
import hd_rig as R  # noqa: E402

ROOT = ART.parents[1]
SRC = Path("/mnt/nvme1n1p1/mc2-rework/work/hunter_rigid")
DST = Path("/mnt/nvme1n1p1/mc2-rework/work/hunter_tracks")
XLO, XHI = 690.0, 1510.0     # the track-wide band (the belt itself is x 770..1470; the outer skirt is above it)
Y0, Y1 = -3000.0, 1850.0     # the belt's length (the hull nose and tail stick out past it)
THICK = 96.0                 # link thickness normal to the path, mm
ZMAX = 520.0
# Road wheels, idler and sprocket (LANCE-18 rev 2): the kit only models the lower half of each wheel, fused to the hull.
# Axle centres and radii were fitted to the kit's lower arcs (side view, circle fit on the lower envelope); the drum spans
# x 795..1445 mm. The fused half discs are cut from the hull and replaced by full discs of our own geometry.
WHEELS = [(-1978.0, 357.0, 266.0), (-1435.0, 357.0, 266.0), (-874.0, 357.0, 266.0), (-272.0, 357.0, 266.0),
          (272.0, 357.0, 266.0), (832.0, 357.0, 266.0), (-2615.0, 430.0, 215.0), (1397.0, 482.0, 215.0)]   # y, z, R
WX0, WX1 = 795.0, 1445.0
ZCUT = 305.0                  # the half discs lie below the skirt bottom
SEG = 36


def make_wheel(R, w=WX1 - WX0, seg=SEG):
    """A full wheel in its own frame: axle along +x (the outer face at x = w), up +z. Returns (V mm, F). Own geometry,
    built from the kit's wheel proportions: tyre drum with chamfers, a recessed rim with a hub boss, six bolts and one
    bigger marker bolt (so the spin shows)."""
    prof = [(0, 0), (0, .66), (18, .9), (36, 1), (w - 36, 1), (w - 18, .9), (w, .66), (w - 45, .66), (w - 45, .42),
            (w - 15, .42), (w - 15, 0)]
    rows, V = [], []
    for x, f in prof:
        r = f * R
        if r == 0:
            rows.append([len(V)] * seg); V.append((x, 0.0, 0.0)); continue
        ring = []
        for j in range(seg):
            a = 2 * np.pi * j / seg
            ring.append(len(V)); V.append((x, r * np.sin(a), r * np.cos(a)))
        rows.append(ring)
    F = []
    for i in range(len(prof) - 1):
        for j in range(seg):
            a, b, c, d = rows[i][j], rows[i][(j + 1) % seg], rows[i + 1][(j + 1) % seg], rows[i + 1][j]
            F += [(a, b, c), (a, c, d)]
    for k in range(6):          # bolts on the recess face; k = 0 is the marker
        big = k == 0
        a = 2 * np.pi * k / 6
        cy, cz, rb, x0, x1 = 0.54 * R * np.sin(a), 0.54 * R * np.cos(a), (26.0 if big else 16.0), w - 45, (w - 8 if big else w - 22)
        base, top = [], []
        for j in range(8):
            t = 2 * np.pi * j / 8
            base.append(len(V)); V.append((x0, cy + rb * np.sin(t), cz + rb * np.cos(t)))
        for j in range(8):
            t = 2 * np.pi * j / 8
            top.append(len(V)); V.append((x1, cy + rb * np.sin(t), cz + rb * np.cos(t)))
        c = len(V); V.append((x1, cy, cz))
        for j in range(8):
            j2 = (j + 1) % 8
            F += [(base[j], base[j2], top[j2]), (base[j], top[j2], top[j]), (top[j], top[j2], c)]
    V = np.array(V, float); F = np.array(F)
    good = (F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])
    F = F[good]
    T = V[F]
    if np.einsum("ij,ij->i", T[:, 0], np.cross(T[:, 1], T[:, 2])).sum() < 0:     # outward
        F = F[:, ::-1]
    return V, F


def wheel_world(side, y, z, V):
    """The wheel placed on its axle: side +1 (track_l, +X) is the local frame as is, side -1 turned half a turn about
    the vertical axis (a rotation, so the shared UVs keep their handedness)."""
    W = V + np.array([WX0, 0, 0])
    if side < 0:
        W = W * np.array([-1.0, -1.0, 1.0])
    return W + np.array([0.0, y, z]) if side > 0 else W + np.array([0.0, y, 0.0]) + np.array([0, 0, z])


def wheel_names():
    return [f"wheel_{s}{i}" for s in "lr" for i in range(len(WHEELS))]


def belt_envelope(T, C, sign, res=10.0):
    xs = C[:, 0] * sign
    inx = (xs > XLO) & (xs < XHI)
    pts = np.concatenate([T[inx].reshape(-1, 3), C[inx]])
    ys = np.arange(Y0 - 200, Y1 + 200, res)
    iy = np.round((pts[:, 1] - ys[0]) / res).astype(int)
    env = np.full(len(ys), 1e9)
    ok = (iy >= 0) & (iy < len(ys))
    np.minimum.at(env, iy[ok], pts[ok, 2])
    good = env < 1e8
    env = np.interp(ys, ys[good], env[good])
    return inx, ys, env


def classify(T, C, sign):
    inx, ys, env = belt_envelope(T, C, sign)
    slope = np.gradient(ndi.uniform_filter1d(env, 9), 10.0)
    cos = 1 / np.sqrt(1 + np.clip(slope, -3, 3) ** 2)
    tv = np.minimum(THICK / cos, 260)
    cy = np.clip(np.round((C[:, 1] - ys[0]) / 10.0).astype(int), 0, len(ys) - 1)
    return inx & (C[:, 1] > Y0) & (C[:, 1] < Y1) & (C[:, 2] < env[cy] + tv[cy]) & (C[:, 2] < ZMAX)


def main():
    DST.mkdir(parents=True, exist_ok=True)
    z = np.load(SRC / "labels.npz")
    V, F, lab = z["V"], z["F"], z["lab"].copy()
    f = json.loads((SRC / "fit.json").read_text())
    names = list(f["node_names"])
    hull = names.index("Hunter")
    m = np.where(lab == hull)[0]
    T = V[F[m]]
    C = T.mean(1)
    n0 = len(names)
    for sign, nm in ((1, "track_l"), (-1, "track_r")):
        sel = classify(T, C, sign)
        names.append(nm)
        lab[m[sel]] = len(names) - 1
        print(f"{nm}: {int(sel.sum())} faces")
    # cut the fused half discs out of the hull, then add the full wheels (own geometry) as parts wheel_l0.. wheel_r7
    m = np.where(lab == hull)[0]
    Cc = V[F[m]].mean(1)
    drop = np.zeros(len(m), bool)
    for sign in (1, -1):
        for (y, z, rad) in WHEELS:
            xs = Cc[:, 0] * sign
            drop |= (xs > WX0 - 5) & (xs < WX1 + 5) & (Cc[:, 2] < ZCUT) & (np.hypot(Cc[:, 1] - y, Cc[:, 2] - z) < rad + 6)
    print(f"hull: {int(drop.sum())} fused wheel faces removed")
    keep = np.ones(len(F), bool); keep[m[drop]] = False
    V2, F2, lab2 = [V], [F[keep]], [lab[keep]]
    off = len(V)
    axles = {}
    for sign, sname in ((1, "l"), (-1, "r")):
        for i, (y, z, rad) in enumerate(WHEELS):
            Vw, Fw = make_wheel(rad)
            Wv = wheel_world(sign, y, z, Vw)
            names.append(f"wheel_{sname}{i}")
            V2.append(Wv); F2.append(Fw + off); lab2.append(np.full(len(Fw), len(names) - 1)); off += len(Wv)
            axles[names[-1]] = [sign * (WX0 + WX1) / 2, y, z, rad]
    V, F, lab = np.concatenate(V2), np.concatenate(F2), np.concatenate(lab2)
    f["node_names"] = names
    for k in range(n0, len(names)):
        f["parent"][str(k)] = hull
        f["xform"][str(k)] = np.eye(4).tolist()
    (DST / "axles.json").write_text(json.dumps(axles, indent=1))
    np.savez_compressed(DST / "labels.npz", V=V, F=F, lab=lab)
    (DST / "fit.json").write_text(json.dumps(f, indent=1))
    # the node tree: the original's plus the two belt nodes under the Hunter root (glTF metres, x +/-1.12)
    g, b = R.load_glb(str(ROOT / "game/assets/vehicles/hunter.glb"))
    for nm, x in (("track_l", 1.12), ("track_r", -1.12)):
        g["nodes"].append({"name": nm, "translation": [x, 0.0, 0.0]})
        g["nodes"][0].setdefault("children", []).append(len(g["nodes"]) - 1)
    # the baseline glb carries a mesh on the hull and turret nodes and its own images: the v3 build drops them
    for k in ("images", "textures", "samplers", "materials", "skins"):
        g.pop(k, None)
    rt = np.array(g["nodes"][0]["translation"])
    for nm, (ax, ay, az, rad) in axles.items():           # wheel nodes pivot on their axle (glTF metres, relative to the root)
        g["nodes"].append({"name": nm, "translation": (np.array([ax, az, -ay]) / 1000.0 - rt).tolist()})
        g["nodes"][0]["children"].append(len(g["nodes"]) - 1)
    for fn in ("hunter_base.glb", "skel.glb"):   # skel.glb: what v3_mech.v2_setup reads from the work dir
        R.GlbWriter(g, b).write(str(DST / fn))
    print("wrote", DST)


if __name__ == "__main__":
    main()
