"""Review sheets for the HD mech pipeline (hd_mech.py), one row per mech.

    python3 -I tools/art/hd_review.py concepts hunchback zeus ...  -> original/hd/review_concepts.png
    python3 -I tools/art/hd_review.py hd hunchback zeus ... [--render] [--out sheet.png]

`concepts`: the padded render that went to the edit | the concept that came back.
`hd`: original render | concept | HD model from the concept camera (yaw 35, the mech's front three-quarter)
| HD model from behind (yaw 215). The front check is by eye: the HD's yaw-35 view must show the same face as
the original's. If it shows the back, rerun `hd_mech.py <mech> --from-step 4 --turn`.
`--render` (re)renders the installed `<mech>_hd.glb` in the model viewer first (imports the project once),
under the shared Godot lock (`.godot.lock`), because another session may be running Godot in the repo.
"""

import argparse
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hd_mech  # noqa: E402

ROOT = hd_mech.ROOT
GAME = hd_mech.GAME
WORK = ROOT / "original" / "hd"
CELL = 300


def godot(args, timeout=1800):
    return subprocess.run(["flock", str(hd_mech.GODOT_LOCK), hd_mech.GODOT] + args, capture_output=True, timeout=timeout)


def render_hd(mech, yaw, out):
    cf = WORK / mech / "render_cam.txt"  # the exact camera hd_mech.render used: "yaw,pitch,dist focus_y"
    zf = WORK / mech / "render_zoom.txt"  # older renders: only the zoom it backed off to
    z = 1.0 if cf.exists() else (float(zf.read_text()) if zf.exists() else 1.0)
    cam, focus = cf.read_text().split() if cf.exists() else ("35,6,42", "4.6")
    _, pitch, dist = cam.split(",")
    godot(["--path", str(GAME), "res://scenes/model_viewer.tscn", "--", f"--screenshot={out}", "--frames=12",
           f"--cam={yaw},{pitch},{float(dist) * z:.1f}", "--fov=18", f"--focus-y={float(focus) * z:.2f}", "--no-ground", "--bg=1,1,1",
           f"--model=res://assets/mechs/{mech}_hd.glb", f"--paint={mech}_hd,{hd_mech.NEUTRAL_PAINT}"])


def cell(path, crop=None):
    if not path.exists():
        im = Image.new("RGB", (CELL, CELL), (90, 0, 0))
        ImageDraw.Draw(im).text((10, 10), "missing", fill=(255, 255, 255))
        return im
    im = Image.open(path).convert("RGB")
    if crop:
        im = im.crop(crop)
    return im.resize((CELL, CELL))


def sheet(rows, labels, heads, out):
    w, h = CELL * len(heads), CELL * len(rows)
    im = Image.new("RGB", (w + 110, h + 20), (255, 255, 255))
    d = ImageDraw.Draw(im)
    for c, t in enumerate(heads):
        d.text((110 + c * CELL + 5, 4), t, fill=(0, 0, 0))
    for r, (cells, lab) in enumerate(zip(rows, labels)):
        d.text((5, 20 + r * CELL + CELL // 2), lab, fill=(0, 0, 0))
        for c, cim in enumerate(cells):
            im.paste(cim, (110 + c * CELL, 20 + r * CELL))
    im.save(out)
    print("wrote", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["concepts", "hd"])
    ap.add_argument("mechs", nargs="+")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    view = (350, 0, 1250, 900)  # the viewer frame, cropped as hd_mech.render does
    if a.mode == "concepts":
        rows = [[cell(WORK / m / "front34_pad.png"), cell(WORK / m / "concept.png")] for m in a.mechs]
        sheet(rows, a.mechs, ["render (edit input)", "concept"], a.out or WORK / "review_concepts.png")
        return
    if a.render:
        godot(["--headless", "--import", "--path", str(GAME)])
        for m in a.mechs:
            render_hd(m, 35, WORK / m / "hd_front34.png")
            render_hd(m, 215, WORK / m / "hd_back34.png")
    rows = [[cell(WORK / m / "front34.png", view), cell(WORK / m / "concept.png"),
             cell(WORK / m / "hd_front34.png", view), cell(WORK / m / "hd_back34.png", view)] for m in a.mechs]
    sheet(rows, a.mechs, ["original yaw 35", "concept", "HD yaw 35 (must match)", "HD yaw 215 (back)"],
          a.out or WORK / "review_hd.png")


if __name__ == "__main__":
    main()
