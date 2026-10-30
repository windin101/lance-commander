#!/usr/bin/env python3
"""Evaluate an image-to-3D sculpt (Tripo or any other) against the in-house Starslayer and two v3 mechs.   LANCE-16 prep
    python3 -I tools/art/v3/tripo_eval.py MESH.glb|MESH.npz [--ref REF.npz] [--out DIR] [--name starslayer]
        [--mechs hunchback,bushwacker]
1. loads the mesh (GLB: glTF metres, Y up -> game mm Z up; or an npz with P, F in game mm);
2. aligns it to the original rest frame: tries the 24 proper axis rotations (scaled to the reference height),
   keeps the lowest chamfer, then similarity ICP (Umeyama scale, 40 iterations) against REF, the in-house blockout
   (tools/cad/starslayer_blockout.py output, already in the original's rest frame);
3. renders ONE sheet: rows = candidate, in-house v3 Starslayer, v3 mechs; columns = front, side, 3/4, left-knee
   close-up, gun-arm close-up (Blender Workbench via v3_blender.py, same camera for every row);
4. prints the alignment (rotation, scale, chamfer in mm) and writes OUT/aligned.npz (P, F; labels by nearest part
   when REF carries a `part` array: the plan for Pipeline A segmentation).
Keep MESH and OUT outside the repo when the mesh is a free-tier download (not ours): /mnt/nvme1n1p1/mc2-rework/tripo_poc/.
"""
import argparse
import itertools
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools/art"))
BLENDER = "blender"


def load_mesh(p: Path):
    if p.suffix == ".npz":
        z = np.load(p); return z["P"].astype(float), z["F"].astype(int)
    import hd_rig as R
    g, b = R.load_glb(str(p))
    W = R.world_matrices(g)
    PP, FF, o = [], [], 0
    for i, n in enumerate(g["nodes"]):
        if "mesh" not in n:
            continue
        for pr in g["meshes"][n["mesh"]]["primitives"]:
            pp = R.read_accessor(g, b, pr["attributes"]["POSITION"]).astype(float)
            pw = (np.c_[pp, np.ones(len(pp))] @ W[i].T)[:, :3]
            ii = R.read_accessor(g, b, pr["indices"]).reshape(-1, 3) if "indices" in pr else np.arange(len(pp)).reshape(-1, 3)
            PP.append(np.c_[pw[:, 0], -pw[:, 2], pw[:, 1]] * 1000.0); FF.append(ii + o); o += len(pp)
    return np.concatenate(PP), np.concatenate(FF).astype(int)


def sample(P, F, n=20000, seed=0, ret_idx=False):
    t = P[F]; a = np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1)
    rng = np.random.default_rng(seed)
    i = rng.choice(len(F), n, p=a / a.sum()); u, v = rng.random((2, n)); f = u + v > 1; u[f], v[f] = 1 - u[f], 1 - v[f]
    q = t[i, 0] + u[:, None] * (t[i, 1] - t[i, 0]) + v[:, None] * (t[i, 2] - t[i, 0])
    return (q, i) if ret_idx else q


def rotations():
    out = []
    for perm in itertools.permutations(range(3)):
        for s in itertools.product((1, -1), repeat=3):
            M = np.zeros((3, 3))
            for r, (c, sg) in enumerate(zip(perm, s)):
                M[r, c] = sg
            if np.linalg.det(M) > 0:
                out.append(M)
    return out


def umeyama(A, B):
    ma, mb = A.mean(0), B.mean(0)
    H = (A - ma).T @ (B - mb) / len(A)
    U, S, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(U @ Vt)); D = np.diag([1, 1, d])
    R = Vt.T @ D @ U.T
    s = (S * np.diag(D)).sum() / ((A - ma) ** 2).sum(1).mean()
    return s, R, mb - s * R @ ma


def chamfer(A, tb, B, ta):
    return 0.5 * (tb.query(A)[0].mean() + ta.query(B)[0].mean())


def align(P, F, ref, rF):
    A0, B = sample(P, F, seed=1), sample(ref, rF, seed=2)
    tb = cKDTree(B); h = B[:, 2].max() - B[:, 2].min()
    best = None
    for M in rotations():
        A = A0 @ M.T
        s = h / (A[:, 2].max() - A[:, 2].min())
        A = A * s; A = A - [A[:, 0].mean() - B[:, 0].mean(), A[:, 1].mean() - B[:, 1].mean(), A[:, 2].min() - B[:, 2].min()]
        c = chamfer(A, tb, B, cKDTree(A))
        if best is None or c < best[0]:
            best = (c, M, s)
    c, M, s = best
    A = A0 @ M.T * s
    A = A - [A[:, 0].mean() - B[:, 0].mean(), A[:, 1].mean() - B[:, 1].mean(), A[:, 2].min() - B[:, 2].min()]
    S, R, T = 1.0, np.eye(3), np.zeros(3)   # accumulated similarity on top of the initial one
    cur = A.copy()
    for _ in range(40):
        idx = tb.query(cur)[1]
        s2, R2, t2 = umeyama(cur, B[idx])
        cur = s2 * cur @ R2.T + t2
    cA = chamfer(cur, tb, B, cKDTree(cur))
    # full transform P -> aligned, recovered by least squares on the sample points
    s_f, R_f, t_f = umeyama(A0, cur)
    return (s_f, R_f, t_f), c, cA


def render(P, F, tag, W, views, centre=None, span=None, size=480):
    npz = W / f"_{tag}.npz"
    np.savez(npz, P=P, F=F, col=np.full((len(F), 3), 0.68))
    args = ["views", str(npz), str(W / f"r_{tag}"), "--size", str(size), "--views", ",".join(views)]
    if centre is not None:
        args += ["--centre", ",".join(map(str, centre)), "--span", str(span)]
    r = subprocess.run([BLENDER, "-b", "--factory-startup", "--python", str(HERE / "v3_blender.py"), "--"] + args, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(r.stderr[-1500:])


def joint_check(Pa, F, name, W):
    """Can the aligned mesh ride the original skeleton? For every original joint (rest pose, game mm): the distance to
    the nearest mesh surface and whether the joint lies inside the closed volume (voxel fill at 80 mm)."""
    import hd_rig as R
    from scipy import ndimage as ndi
    g, b = R.load_glb(str(ROOT / "game/assets/mechs" / f"{name}.glb"))
    Wm = R.world_matrices(g)
    S = sample(Pa, F, 400000, 5); tr = cKDTree(S)
    vox = 80.0; lo = S.min(0) - 2 * vox
    grid = np.zeros(tuple(((S.max(0) - lo) / vox).astype(int) + 3), bool)
    grid[tuple(((S - lo) / vox).astype(int).T)] = True
    grid = ndi.binary_dilation(grid, iterations=1)
    outside = ndi.label(~grid)[0]; out_id = outside[0, 0, 0]
    rows = []
    for i, n in enumerate(g["nodes"]):
        nm = n.get("name", "")
        if not nm.startswith("joint_") or nm in ("joint_root", "joint_rgun", "joint_lhand", "joint_rshouldergun", "joint_lfoot", "joint_rfoot"):
            continue
        p = Wm[i][:3, 3]; p = np.array([p[0], -p[2], p[1]]) * 1000.0
        d = tr.query(p)[0]
        gi = tuple(np.clip(((p - lo) / vox).astype(int), 0, np.array(grid.shape) - 1))
        inside = outside[gi] != out_id
        rows.append((nm, d, bool(inside)))
    print("joint check (distance from the original joint to the nearest mesh surface, mm; inside = in the closed volume):")
    for nm, d, ins in rows:
        print(f"  {nm:18s} {d:6.0f}  {'inside' if ins else 'OUTSIDE (in a gap between volumes)'}")
    print(f"  median {np.median([r[1] for r in rows]):.0f} mm, max {max(r[1] for r in rows):.0f} mm, {sum(r[2] for r in rows)}/{len(rows)} inside")
    (W / "joint_check.txt").write_text("\n".join(f"{nm} {d:.0f} {'inside' if ins else 'outside'}" for nm, d, ins in rows))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mesh")
    ap.add_argument("--ref", default="/mnt/nvme1n1p1/mc2-rework/work/starslayer_in/block.npz")
    ap.add_argument("--out", default="/mnt/nvme1n1p1/mc2-rework/tripo_poc/starslayer/eval")
    ap.add_argument("--name", default="starslayer")
    ap.add_argument("--mechs", default="hunchback,bushwacker")
    ap.add_argument("--extra", action="append", default=[], help="LABEL=aligned.npz: an earlier, already aligned run to show as an extra row (repeatable)")
    a = ap.parse_args()
    W = Path(a.out); W.mkdir(parents=True, exist_ok=True)
    P, F = load_mesh(Path(a.mesh))
    rz = np.load(a.ref); ref, rF = rz["P"].astype(float), rz["F"].astype(int)
    (s, R, t), c0, c1 = align(P, F, ref, rF)
    Pa = s * P @ R.T + t
    print(f"align: scale {s:.5f} (mesh units -> game mm), chamfer {c0:.0f} -> {c1:.0f} mm, bbox {Pa.min(0).round()} {Pa.max(0).round()}")
    print("rotation:\n", R.round(3))
    np.savez(W / "aligned.npz", P=Pa, F=F)
    if "part" in rz.files:   # Pipeline A labels: nearest blockout part (ids -> original node names via rz['names'])
        pts, si = sample(ref, rF, 40000, 3, True)
        tr = cKDTree(pts); lab_s = rz['part'][si]
        cen = Pa[F].mean(1); lab = lab_s[tr.query(cen)[1]]
        np.save(W / "labels_nearest_part.npy", lab)
        print("labels by nearest blockout part:", {str(rz['names'][k]): int((lab == k).sum()) for k in np.unique(lab)})
    sys.path.insert(0, str(ROOT / "tools/art"))
    joint_check(Pa, F, a.name, W)
    import fit_check as FC
    rows = [("candidate (aligned)", Pa, F)]
    for ex in a.extra:
        lab_, f_ = ex.split("=", 1); z_ = np.load(f_); rows.append((lab_, z_["P"], z_["F"]))
    rows.append(("in-house v3 Starslayer", *FC.original_mesh(a.name, "v3/mechs")))
    for m in a.mechs.split(","):
        rows.append((f"v3 {m}", *FC.original_mesh(m, "v3/mechs")))
    from PIL import Image, ImageDraw
    cols = [("front", None), ("side", None), ("q34", None), ("knee", ((1617, -145, 3342), 3200)), ("arm", ((-2650, -1200, 7190), 4600))]
    S = Image.new("RGB", (480 * 5, 480 * len(rows) + 0), (60, 60, 60)); d = ImageDraw.Draw(S)
    for r, (lab_, PP, FF) in enumerate(rows):
        render(PP, FF, f"r{r}", W, ["front", "side", "q34"], (0, 0, 4900), 11000)
        render(PP, FF, f"k{r}", W, ["q34"], cols[3][1][0], cols[3][1][1])
        render(PP, FF, f"a{r}", W, ["q34"], cols[4][1][0], cols[4][1][1])
        files = [W / f"r_r{r}_front.png", W / f"r_r{r}_side.png", W / f"r_r{r}_q34.png", W / f"r_k{r}_q34.png", W / f"r_a{r}_q34.png"]
        for c, f in enumerate(files):
            S.paste(Image.open(f).convert("RGB"), (480 * c, 480 * r))
            d.text((480 * c + 6, 480 * r + 6), f"{lab_}: {cols[c][0]}", fill=(255, 255, 0))
    S.save(W / "eval_sheet.png"); S.resize((S.width * 2 // 3, S.height * 2 // 3)).save(W / "eval_sheet_s.png")
    print("sheet:", W / "eval_sheet_s.png")


if __name__ == "__main__":
    main()
