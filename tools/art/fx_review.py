#!/usr/bin/env python3
"""Weapon-effects review (I87): record fx-range clips and build a contact sheet.

    # record (Godot runs windowed; wrap in the project's Godot lock):
    swarm lock godot -- flock .godot.lock python3 -I tools/art/fx_review.py record OUT_DIR [families...]
        [--frames-dir /mnt/nvme1n1p1/...] [--extra "--dist=70 --cam=0,40,120"]
    # contact sheet from recorded clips (one frame per family at its peak moment):
    python3 -I tools/art/fx_review.py sheet OUT_DIR sheet.png

Each family is game/scenes/fx_range.tscn (see game/scripts/dev/fx_range.gd) recorded with Godot's movie writer at
30 fps, 1920x1080, then encoded to OUT_DIR/<family>.mp4. Short-range weapons (flamer, mg) are recorded at 70 m.
The AVI frame dumps are large: keep them on disk (--frames-dir), not in /tmp, which is RAM.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
GODOT = os.environ.get("GODOT_BIN", str(Path.home() / ".local/bin/godot"))
FAMILIES = ["laser", "ppc", "autocannon", "gauss", "mg", "missile", "flamer", "artillery", "misses", "water",
            "damage", "death", "vehicle", "building"]
SHORT = {"flamer": "--dist=70", "mg": "--dist=70"}
# (time s, crop x, y, w, h) of a representative frame per family in the default 240 m view
PICKS = {
    "laser": [(11.15, 0, 380, 1920, 280), (6.9, 0, 380, 1920, 280)],
    "ppc": [(1.12, 0, 380, 1920, 280)],
    "autocannon": [(5.5, 0, 380, 1920, 280)],
    "gauss": [(1.15, 0, 380, 1920, 280)],
    "mg": [(1.3, 300, 330, 1320, 380)],
    "missile": [(1.9, 0, 250, 1920, 480)],
    "flamer": [(1.7, 300, 300, 1320, 420)],
    "artillery": [(1.45, 0, 250, 1920, 480)],
    "water": [(13.9, 480, 140, 960, 700)],
    "damage": [(7.5, 1400, 150, 520, 560)],
    "death": [(2.7, 1360, 150, 560, 600), (6.0, 1360, 150, 560, 600)],
    "vehicle": [(1.3, 1300, 150, 620, 600)],
    "building": [(2.2, 480, 140, 960, 700), (9.0, 480, 140, 960, 700)],
}


def record(out, families, frames_dir, extra):
    out.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)
    for f in families:
        avi = frames_dir / f"{f}.avi"
        args = [GODOT, "--path", str(ROOT / "game"), "--resolution", "1280x720", "--write-movie", str(avi), "--fixed-fps", "30",
                "res://scenes/fx_range.tscn", "--", f"--family={f}", "--no-hud", "--freeze"]
        args += (extra or SHORT.get(f, "")).split()
        log = frames_dir / f"{f}.log"
        with open(log, "w") as fh:
            rc = subprocess.run(args, stdout=fh, stderr=subprocess.STDOUT, timeout=600).returncode
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(avi), "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
                        "-pix_fmt", "yuv420p", str(out / f"{f}.mp4")], check=True)
        print(f, "rc", rc, "->", out / f"{f}.mp4")


def grab(clip, t):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "f.png")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(t), "-i", str(clip), "-frames:v", "1", p], check=True)
        return Image.open(p).convert("RGB")


def sheet(out, dst, width=1920):
    tiles = []
    for fam, picks in PICKS.items():
        clip = out / f"{fam}.mp4"
        if not clip.exists():
            continue
        for t, x, y, w, h in picks:
            im = grab(clip, t).crop((x, y, x + w, y + h))
            s = width / 2 / max(w, 1)
            im = im.resize((int(w * s), int(h * s)), Image.LANCZOS)
            ImageDraw.Draw(im).text((8, 6), f"{fam}  t={t}", fill=(255, 255, 0))
            tiles.append(im)
    col_w = width // 2
    cols = [[], []]
    heights = [0, 0]
    for im in tiles:
        c = 0 if heights[0] <= heights[1] else 1
        cols[c].append(im)
        heights[c] += im.size[1] + 4
    canvas = Image.new("RGB", (width + 4, max(heights)), (16, 16, 16))
    for c in range(2):
        y = 0
        for im in cols[c]:
            canvas.paste(im, (c * (col_w + 4), y))
            y += im.size[1] + 4
    canvas.save(dst)
    print(dst, canvas.size)


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("record", "sheet"):
        print(__doc__)
        sys.exit(2)
    out = Path(sys.argv[2])
    if sys.argv[1] == "sheet":
        sheet(out, sys.argv[3] if len(sys.argv) > 3 else str(out / "fx_sheet.png"))
        return
    rest = sys.argv[3:]
    frames_dir = Path("/mnt/nvme1n1p1/fx_review_frames")
    extra = ""
    fams = []
    i = 0
    while i < len(rest):
        if rest[i] == "--frames-dir":
            frames_dir = Path(rest[i + 1])
            i += 2
        elif rest[i] == "--extra":
            extra = rest[i + 1]
            i += 2
        else:
            fams.append(rest[i])
            i += 1
    record(out, fams or FAMILIES, frames_dir, extra)


if __name__ == "__main__":
    main()
