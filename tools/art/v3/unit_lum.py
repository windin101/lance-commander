#!/usr/bin/env python3
"""Unit brightness check (v3 vs v1): the same mission frame with and without --no-art-v3, framed on the player's first unit
(dev_force_mission.tscn --focus-lance). The units are the pixels where the two renders differ (the unit meshes are re-rendered flat magenta (--mask-units) for an exact silhouette); the report is mean luminance of the unit pixels, v3 / v1.

    python3 -I tools/art/v3/unit_lum.py mc2_23 mc2_05 ... [--dist 50] [--out DIR]
"""
import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]


def lum(a):
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def shot(mission, v1, out, dist, pitch=55, yaw=30, extra=()):
    cmd = ["flock", str(ROOT / ".godot.lock"), str(Path.home() / ".local/bin/godot"), "--minimized", "--no-focus", "--path", str(ROOT / "game"), "res://scenes/dev_force_mission.tscn", "--",
           f"--mission={mission}", "--focus-lance", f"--cam-view={yaw},{pitch},{dist}", f"--screenshot={out}", "--frames=90", "--size=960x600", *extra]
    if v1:
        cmd.append("--no-art-v3")
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=240)


def silhouette(path):
    a = np.asarray(Image.open(path).convert("RGB").resize((960, 600), Image.NEAREST)).astype(float)
    m = (a[..., 0] - a[..., 1] > 45) & (a[..., 2] - a[..., 1] > 45)  # flat magenta units (--mask-units)
    m[:, :140] = False; m[:130, :] = False; m[430:, 300:560] = False  # the HUD panels
    return m


def compare(p3, p1, s3):
    a3 = np.asarray(Image.open(p3).convert("RGB").resize((960, 600))).astype(float)
    a1 = np.asarray(Image.open(p1).convert("RGB").resize((960, 600))).astype(float)
    m = silhouette(s3)
    n = int(m.sum())
    if n < 300:
        return None
    return lum(a3)[m], lum(a1)[m]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("missions", nargs="+")
    ap.add_argument("--dist", type=float, default=100)
    ap.add_argument("--yaws", type=float, nargs="*", default=[30, 210])
    ap.add_argument("--out", default="/mnt/nvme1n1p1/claude-scratch/unitlum")
    ap.add_argument("--extra", nargs="*", default=[])
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    for mis in a.missions:
        v3s, v1s = [], []
        for yw in a.yaws:
            p3, p1, sl = out / f"{mis}_{int(yw)}_v3.png", out / f"{mis}_{int(yw)}_v1.png", out / f"{mis}_{int(yw)}_sil.png"
            shot(mis, False, p3, a.dist, yaw=yw, extra=a.extra); shot(mis, True, p1, a.dist, yaw=yw, extra=a.extra)
            shot(mis, False, sl, a.dist, yaw=yw, extra=[*a.extra, "--mask-units"])
            r = compare(p3, p1, sl)
            if r is not None:
                v3s.append(r[0]); v1s.append(r[1])
        if not v3s:
            print(mis, "no unit pixels found", flush=True)
            continue
        l3, l1 = np.concatenate(v3s), np.concatenate(v1s)
        print(mis, f"v3 {l3.mean():.1f}  v1 {l1.mean():.1f}  ratio {l3.mean() / max(l1.mean(), 1e-6):.2f}  ({len(l3)} px)", flush=True)


if __name__ == "__main__":
    main()
