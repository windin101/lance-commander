#!/usr/bin/env python3
"""In-mission comparison sheet (LANCE-19): game/scenes/vehicle_mission_shots.tscn shoots one close view of each model on the
real mission boot path, once with the v3 model and once with --no-art-v3 (the previous HD art); PIL puts v3 next to old.
    python3 -I tools/art/v3/veh_mission_sheet.py OUT.png [--mission mc2_16] [--models lrmc,centipede,harasser,partisan,storm]"""
import argparse, subprocess
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
TMP = Path("/mnt/nvme1n1p1/mc2-rework/veh/mission")


def shoot(tag, extra, a):
    subprocess.run([str(Path.home() / "Code/remake-kit/bin/swarm"), "lock", "godot", "--", "flock", ".godot.lock", str(Path.home() / ".local/bin/godot"),
                    "--path", "game", "res://scenes/vehicle_mission_shots.tscn", "--", f"--mission={a.mission}", f"--models={a.models}",
                    f"--out={TMP / tag}", "--no-hud", f"--dist={a.dist}", "--pitch=38", "--yaw=25"] + extra,
                   cwd=ROOT, capture_output=True, text=True, timeout=900)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("--mission", default="mc2_16")
    ap.add_argument("--models", default="lrmc,centipede,harasser,partisan,storm"); ap.add_argument("--dist", type=float, default=38)
    ap.add_argument("--w", type=int, default=520)
    a = ap.parse_args()
    TMP.mkdir(parents=True, exist_ok=True)
    shoot("v3", [], a); shoot("old", ["--no-art-v3"], a)
    models = a.models.split(","); w = a.w; h = int(w * 0.75)
    sheet = Image.new("RGB", (w * 2, h * len(models)), (20, 20, 24)); d = ImageDraw.Draw(sheet)
    for r, m in enumerate(models):
        for k, tag in enumerate(("v3", "old")):
            p = TMP / f"{tag}_{m}.png"
            if p.exists():
                im = Image.open(p).convert("RGB"); W, H = im.size
                cw, ch = int(W * 0.5), int(H * 0.5)      # the unit is at the screen centre
                im = im.crop(((W - cw) // 2, (H - ch) // 2, (W + cw) // 2, (H + ch) // 2)).resize((w, h), Image.LANCZOS)
                sheet.paste(im, (k * w, r * h))
            d.text((k * w + 6, r * h + 4), f"{m}  {'v3' if tag == 'v3' else 'previous art (--no-art-v3)'}", fill=(255, 255, 255))
    sheet.save(a.out); print(a.out, sheet.size)


if __name__ == "__main__":
    main()
