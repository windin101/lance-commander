#!/usr/bin/env python3
"""Original-vs-kit sheet (LANCE-19): per unit the 2001 model (3/4 and side, through game/scenes/vehicle_gallery.tscn), the kit's rigid fit
(veh_view.py, flat-shaded 3/4 and side) and optionally the built v3 model (3/4 and side), one row each.
    python3 -I tools/art/v3/veh_orig_sheet.py OUT.png unit [unit ...] [--v3] [--w 300]"""
import argparse, json, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
TMP = Path("/mnt/nvme1n1p1/mc2-rework/veh/orig")
SH = [dict(name="t0", yaw=-35, pitch=14, fill=0.85, rig={"turret": 0}), dict(name="side", yaw=-90, pitch=3, fill=0.95, focus=0.4, rig={"turret": 0})]


def gallery(items):
    (TMP / "job.json").write_text(json.dumps({"size": [680, 516], "items": items}))
    subprocess.run([str(Path.home() / "Code/remake-kit/bin/swarm"), "lock", "godot", "--", "flock", ".godot.lock", str(Path.home() / ".local/bin/godot"),
                    "--path", "game", "res://scenes/vehicle_gallery.tscn", "--", "--art-v3", f"--job={TMP / 'job.json'}"],
                   cwd=ROOT, capture_output=True, text=True, timeout=900)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("units", nargs="+"); ap.add_argument("--v3", action="store_true")
    ap.add_argument("--w", type=int, default=300)
    a = ap.parse_args(); TMP.mkdir(parents=True, exist_ok=True)
    gallery([{"path": f"res://assets/vehicles/{u}.glb", "paint_name": u, "folder": "vehicles", "scheme": "player", "out": str(TMP / f"o_{u}"), "shots": SH} for u in a.units])
    if a.v3:
        gallery([{"path": f"res://assets/v3/vehicles/{u}.glb", "paint_name": u + "_v3", "folder": "vehicles", "scheme": "player", "out": str(TMP / f"v_{u}"), "shots": SH} for u in a.units])
    for u in a.units:      # the kit: flat-shaded renders of the rigid fit, one 3/4 and one side view
        for v, nm in (("iso:215:25", "i"), ("side", "s")):
            subprocess.run([sys.executable, "-I", str(ROOT / "tools/art/v3/veh_view.py"), f"/mnt/nvme1n1p1/mc2-rework/work/{u}_rigid", str(TMP / f"k{nm}_{u}.png"),
                            "--ppm", "0.03", "--step", "100000", "--views", v], cwd=ROOT, check=True, capture_output=True)
    w = a.w; h = int(w * 0.76); cols = 4 + (2 if a.v3 else 0)
    S = Image.new("RGB", (w * cols, h * len(a.units)), (20, 20, 24)); d = ImageDraw.Draw(S)
    def fit(im):
        im = im.convert("RGB"); im.thumbnail((w, h), Image.LANCZOS); c = Image.new("RGB", (w, h), (25, 25, 25)); c.paste(im, ((w - im.width) // 2, (h - im.height) // 2)); return c
    for r, u in enumerate(a.units):
        ims = [TMP / f"o_{u}_t0.png", TMP / f"o_{u}_side.png", TMP / f"ki_{u}.png", TMP / f"ks_{u}.png"]
        if a.v3:
            ims += [TMP / f"v_{u}_t0.png", TMP / f"v_{u}_side.png"]
        for k, p in enumerate(ims):
            S.paste(fit(Image.open(p)), (k * w, r * h))
        d.text((6, r * h + 4), f"{u}: 2001 original", fill=(255, 255, 0)); d.text((2 * w + 6, r * h + 4), f"{u}: kit (rigid fit)", fill=(255, 255, 0))
        if a.v3:
            d.text((4 * w + 6, r * h + 4), f"{u}: v3", fill=(255, 255, 0))
    S.save(a.out); print(a.out, S.size)


if __name__ == "__main__":
    main()
