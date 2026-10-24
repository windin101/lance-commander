#!/usr/bin/env python3
"""Review sheets for the HD rework (v2) rollout: renders staged v2 models in the bay studio and lays out one row per
asset with its pose-test and budget figures (from tools/art/hd_v2_rollout.py's table).

    python3 -I tools/art/hd_v2_review.py job   OUT_DIR mechs|vehicles|objects name [name ...]
    (godot --path game res://scenes/art_gallery.tscn -- --job=OUT_DIR/job.json, under the godot lock)
    python3 -I tools/art/hd_v2_review.py sheet OUT_DIR mechs|vehicles|objects name [name ...] [--table T.json]

Per row: front 3/4, rear 3/4, a lab close-up and a front close-up (the canopy) in the default player scheme, a
Steiner-scheme still (a region scheme), and for mechs six frames of the walk; then the figures.
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]


def job(out, folder, names):
    items = []
    for n in names:
        p = f"res://assets/v2/{folder}/{n}.glb"
        shots = [{"name": "a", "yaw": -28}, {"name": "b", "yaw": 152}, {"name": "z", "yaw": -22, "fill": 2.4, "focus": 0.7},
                 {"name": "f", "yaw": 20, "fill": 2.4, "focus": 0.72, "pitch": 12}]
        if folder == "mechs":
            shots.append({"name": "w", "yaw": -40, "fill": 1.6, "focus": 0.45, "anim": "Walk", "times": [k / 6 for k in range(6)]})
        it = {"path": p, "folder": folder, "out": f"{out}/{n}", "shots": shots}
        if folder != "objects":
            it.update({"paint_name": f"{n}_v2", "scheme": "player"})
            items.append(it)
            items.append({"path": p, "folder": folder, "out": f"{out}/{n}_st", "paint_name": f"{n}_v2", "scheme": "steiner",
                          "shots": [{"name": "a", "yaw": -28}]})
        else:
            items.append(it)
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / "job.json").write_text(json.dumps({"size": [640, 640], "items": items}, indent=1))
    print(f"{len(items)} items -> {out}/job.json")


def sheet(out, folder, names, table):
    out = Path(out)
    rows = json.loads(Path(table).read_text()) if table and Path(table).exists() else {}
    t = 220
    cols = 5 + (6 if folder == "mechs" else 0)
    for page in range(0, len(names), 8):
        chunk = names[page:page + 8]
        S = Image.new("RGB", (cols * t + 300, len(chunk) * t), (24, 26, 30))
        d = ImageDraw.Draw(S)
        for r, n in enumerate(chunk):
            tiles = [f"{n}_a", f"{n}_b", f"{n}_z", f"{n}_f", f"{n}_st_a"] + ([f"{n}_w_{k:03d}" for k in range(6)] if folder == "mechs" else [])
            for c, k in enumerate(tiles):
                p = out / f"{k}.png"
                if p.exists():
                    S.paste(Image.open(p).convert("RGB").resize((t, t)), (c * t, r * t))
            row = rows.get(n, {})
            txt = [n, f"pose {'PASS' if row.get('pose_pass') else 'FAIL' if row else '?'}",
                   f"hole {row.get('hole_p95', '?')} pen {row.get('pen_p95', '?')} m",
                   f"sep {row.get('sep_p95', '?')} (joint {row.get('joint_sep_p95', '?')}) m",
                   f"{row.get('tris', '?')} tris, {row.get('tex_mb', '?')} / {row.get('budget_mb', '?')} MB"]
            if row.get("fail_parts"):
                txt.append("fail: " + ", ".join(row["fail_parts"])[:44])
            for j, s in enumerate(txt):
                d.text((cols * t + 8, r * t + 8 + 17 * j), s, fill=(235, 235, 235) if j == 0 else (170, 180, 190))
        p = out / f"sheet_{folder}_{page // 8 + 1:02d}.png"
        S.save(p)
        print(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["job", "sheet"])
    ap.add_argument("out")
    ap.add_argument("folder", choices=["mechs", "vehicles", "objects"])
    ap.add_argument("names", nargs="+")
    ap.add_argument("--table", default=str(ROOT / "swarm/gallery/hd_v2_rollout.json"))
    a = ap.parse_args()
    if a.cmd == "job":
        job(a.out, a.folder, a.names)
    else:
        sheet(a.out, a.folder, a.names, a.table)


if __name__ == "__main__":
    sys.exit(main())
