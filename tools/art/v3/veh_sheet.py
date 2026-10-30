#!/usr/bin/env python3
"""Review sheet for v3 vehicles (LANCE-19): game/scenes/vehicle_gallery.tscn renders each unit's rig in several poses, PIL
stitches one labelled sheet (a row per unit).
    python3 -I tools/art/v3/veh_sheet.py OUT.png unit [unit ...] [--cols t0,t90,back,top,wa,wb,steer] [--w 340] [--old]
Columns: t0/t90 3/4 front at turret 0 and 90 deg (gun raised in t90), back = rear 3/4, top = from above with the turret at
45, wa/wb = side close-up of the running gear at two travel positions, steer = steered wheels from above (35 deg)."""
import json, subprocess, sys, argparse
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
TMP = Path("/mnt/nvme1n1p1/mc2-rework/veh/sheet")
SHOTS = {
    "t0": dict(yaw=-35, pitch=14, fill=0.85, rig={"turret": 0}),
    "t90": dict(yaw=-35, pitch=14, fill=0.85, rig={"turret": 90, "gun": "MAX"}),
    "back": dict(yaw=145, pitch=16, fill=0.85, rig={"turret": 0}),
    "top": dict(yaw=-35, pitch=60, fill=0.85, rig={"turret": 45}),
    "wa": dict(yaw=-90, pitch=3, fill=1.25, focus=0.2, rig={"turret": 0, "travel": 0.0}),
    "wb": dict(yaw=-90, pitch=3, fill=1.25, focus=0.2, rig={"turret": 0, "travel": 0.5}),
    "steer": dict(yaw=-35, pitch=48, fill=0.85, rig={"turret": 0, "steer": 35}),
    "wl0": dict(yaw=-90, pitch=0, fill=1.7, focus=0.12, rig={"turret": 0, "travel": 0.0}),
    "wl1": dict(yaw=-90, pitch=0, fill=1.7, focus=0.12, rig={"turret": 0, "travel": 0.5}),
    "st0": dict(yaw=-90, pitch=68, fill=1.1, rig={"turret": 0, "steer": 0}),
    "st1": dict(yaw=-90, pitch=68, fill=1.1, rig={"turret": 0, "steer": 35}),
    "sp0": dict(yaw=-35, pitch=62, fill=2.0, focus=0.8, rig={"spin_time": 0.0}),
    "sp1": dict(yaw=-35, pitch=62, fill=2.0, focus=0.8, rig={"spin_time": 3.0}),
    "sp2": dict(yaw=-35, pitch=62, fill=2.0, focus=0.8, rig={"spin_time": 6.0}),
    "front": dict(yaw=-5, pitch=12, fill=0.85, rig={"turret": 0}),
}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("units", nargs="+")
    ap.add_argument("--cols", default="t0,t90,back,top,wa,wb"); ap.add_argument("--w", type=int, default=340)
    ap.add_argument("--size", type=int, default=680)
    a = ap.parse_args()
    cols = a.cols.split(",")
    TMP.mkdir(parents=True, exist_ok=True)
    items = []
    for u in a.units:
        side = json.loads((ROOT / f"game/assets/v3/vehicles/{u}.v3.json").read_text())
        gp = side.get("gun_pitch", [0, 0])
        shots = []
        for c in cols:
            s = json.loads(json.dumps(SHOTS[c])); s["name"] = c
            if s["rig"].get("gun") == "MAX":
                s["rig"]["gun"] = gp[1]
            shots.append(s)
        items.append({"path": f"res://assets/v3/vehicles/{u}.glb", "paint_name": u + "_v3", "folder": "vehicles", "scheme": "player",
                      "out": str(TMP / u), "shots": shots})
    job = {"size": [a.size, int(a.size * 0.76)], "items": items}
    (TMP / "job.json").write_text(json.dumps(job))
    subprocess.run([str(Path.home() / "Code/remake-kit/bin/swarm"), "lock", "godot", "--", "flock", ".godot.lock", str(Path.home() / ".local/bin/godot"),
                    "--path", "game", "res://scenes/vehicle_gallery.tscn", "--", "--art-v3", f"--job={TMP / 'job.json'}"],
                   cwd=ROOT, capture_output=True, text=True, timeout=900)
    w = a.w; h = int(w * 0.76)
    sheet = Image.new("RGB", (w * len(cols), h * len(a.units)), (20, 20, 24))
    d = ImageDraw.Draw(sheet)
    for r, u in enumerate(a.units):
        for k, c in enumerate(cols):
            p = TMP / f"{u}_{c}.png"
            if p.exists():
                sheet.paste(Image.open(p).convert("RGB").resize((w, h), Image.LANCZOS), (k * w, r * h))
            d.text((k * w + 6, r * h + 4), f"{u} {c}", fill=(255, 255, 255))
    sheet.save(a.out)
    print(a.out, sheet.size)


if __name__ == "__main__":
    main()
