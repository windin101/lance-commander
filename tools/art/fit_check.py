#!/usr/bin/env python3
"""Fit check for the v2 mech rework: the original, the installed v1 model and the v2 rest mesh side by side, front and
top, plus the upper body's yaw by principal axes against the original's.

    python3 -I tools/art/fit_check.py MECH [MECH ...] [--out sheet.png]

Each row: original front, original top, v1 front, v1 top, v2 front, v2 top (orthographic, same camera per column).
The chamfer yaw check in hd_v2.py's fit (part_yaws) missed a 49 deg torso turn on the Shadowcat and turned the Flea
the wrong way, so this sheet is the gate before canopy sheets go to Lee: look at the top views. The printed
"upper-body yaw" is the angle of the main horizontal axis of everything above 62 % of the height (sculpt minus
original); trust it only when the axis is clear (ratio well above 1.5).
"""
import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/art"))
import canopy_pick as C  # noqa: E402
import hd_rig as R  # noqa: E402

SCRATCH = Path("/mnt/nvme1n1p1/mc2-rework/work/_fit_check")


def original_mesh(mech, folder="mechs"):
    og, ob = R.load_glb(str(ROOT / f"game/assets/{folder}/{mech}.glb"))
    W = R.world_matrices(og)
    PP, FF, o = [], [], 0
    for i, n in enumerate(og["nodes"]):
        if "mesh" not in n:
            continue
        pr = og["meshes"][n["mesh"]]["primitives"][0]
        pp = R.read_accessor(og, ob, pr["attributes"]["POSITION"]).astype(float)
        pw = (np.c_[pp, np.ones(len(pp))] @ W[i].T)[:, :3]
        PP.append(np.c_[pw[:, 0], -pw[:, 2], pw[:, 1]] * 1000.0)
        ii = R.read_accessor(og, ob, pr["indices"]).reshape(-1, 3) if "indices" in pr else np.arange(len(pp)).reshape(-1, 3)
        FF.append(ii + o)
        o += len(pp)
    return np.concatenate(PP), np.concatenate(FF)


def upper_yaw(P, F, zlo):
    c = P[F].mean(1)
    A = np.linalg.norm(np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]]), axis=1) / 2
    m = c[:, 2] > zlo
    q, w = c[m, :2], A[m]
    mu = (q * w[:, None]).sum(0) / w.sum()
    d = q - mu
    ev, V = np.linalg.eigh((d * w[:, None]).T @ d / w.sum())
    a = np.degrees(np.arctan2(V[1, 1], V[0, 1]))
    return (a + 90) % 180 - 90, ev[1] / max(ev[0], 1e-9)


def render(P, F, target, scale, out):
    np.savez(SCRATCH / "_m.npz", P=P, F=F, C=np.tile([0.62, 0.62, 0.62], (len(F), 1)), target=target, scale=scale,
             label_pts=target[None])
    C.run_blender(SCRATCH / "_m.npz", out, "shade")
    return [Image.open(f"{out}_{v}.png").convert("RGB").resize((400, 400)) for v in ("front", "top")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mechs", nargs="+")
    ap.add_argument("--out", default=str(C.OUT / "fit_check.png"))
    a = ap.parse_args()
    SCRATCH.mkdir(parents=True, exist_ok=True)
    rows = []
    for m in a.mechs:
        _, z, _, _ = C.load(m)
        P2, F2 = z["P"], z["F"]
        H = float(P2[:, 2].max())
        Po, Fo = original_mesh(m)
        meshes = [("orig", Po, Fo)]
        v1 = SCRATCH / f"{m}_v1.npz"
        r = subprocess.run([sys.executable, "-I", str(ROOT / "tools/art/pose_test.py"), str(ROOT / f"game/assets/mechs/{m}_hd.glb"),
                            "--pose", "Idle@0", "--pose-out", str(v1)], capture_output=True, text=True)
        if v1.exists() and r.returncode == 0:
            q = np.load(v1)
            meshes.append(("v1", q["P"], q["F"]))
        meshes.append(("v2", P2, F2))
        tgt, sc = np.array([0.0, 0.0, 0.5 * H]), 1.1 * H
        tiles = []
        for tag, P, F in meshes:
            tiles += render(P, F, tgt, sc, SCRATCH / f"{m}_{tag}")
        ao, ro = upper_yaw(Po, Fo, 0.62 * H)
        a2, r2 = upper_yaw(P2, F2, 0.62 * H)
        d = (a2 - ao + 90) % 180 - 90
        flag = "  CHECK" if abs(d) > 10 and min(ro, r2) > 1.5 else ""
        print(f"{m}: upper-body yaw v2 - original {d:+.1f} deg (axis ratio {ro:.1f} / {r2:.1f}){flag}")
        row = Image.new("RGB", (400 * 6, 400), (54, 54, 54))
        for i, t in enumerate(tiles):
            row.paste(t, (400 * (i if len(meshes) == 3 or i < 2 else i + 2), 0))
        rows.append(row)
    out = Image.new("RGB", (2400, 400 * len(rows)))
    for i, r_ in enumerate(rows):
        out.paste(r_, (0, 400 * i))
    out.save(a.out)
    print(a.out)


if __name__ == "__main__":
    main()
