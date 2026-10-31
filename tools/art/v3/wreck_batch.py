#!/usr/bin/env python3
"""Generate wrecks for a batch of v3 units, then ONE review sheet: in-game at RTS distance (58 deg pitch, 110 m and the 240 m default)
plus studio close-ups.   (LANCE-38)
    python3 -I tools/art/v3/wreck_batch.py mechs atlas hunchback ...       [--out DIR] [--no-gen]
    python3 -I tools/art/v3/wreck_batch.py vehicles hunter storm ...
Needs the Godot import lock (swarm lock godot).  Mech wrecks are shot on mc2_01 as the player's lance, vehicles on a mission that
carries them (data/missions/*_vehicles.json), with dev_force_mission --wreck=<model>."""
import argparse
import glob
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HOME = Path.home()
GODOT = str(HOME / ".local/bin/godot")
SWARM = str(HOME / "Code/remake-kit/bin/swarm")


def godot(*args, timeout=900):
    cmd = [SWARM, "lock", "godot", "--", "flock", str(ROOT / ".godot.lock"), GODOT, *args]
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)


def vehicle_missions():
    out = {}
    for f in sorted(glob.glob(str(ROOT / "game/data/missions/*_vehicles.json"))):
        t = open(f).read()
        for p in glob.glob(str(ROOT / "game/assets/v3/vehicles/*.glb")):
            v = os.path.basename(p)[:-4]
            if not v.endswith("_wreck") and f'"{v}"' in t and v not in out:
                out[v] = os.path.basename(f).replace("_vehicles.json", "")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", choices=("mechs", "vehicles"))
    ap.add_argument("names", nargs="+")
    ap.add_argument("--out", default="/mnt/nvme1n1p1/mc2-rework/wreck/batch")
    ap.add_argument("--no-gen", action="store_true")
    ap.add_argument("--near-only", action="store_true", help="skip the 240 m view")
    a = ap.parse_args()
    O = Path(a.out); O.mkdir(parents=True, exist_ok=True)
    if not a.no_gen:
        for n in a.names:
            r = subprocess.run([sys.executable, "-I", str(ROOT / "tools/art/v3/wreck_mesh.py"), a.folder, n], capture_output=True, text=True)
            print(n, (r.stdout.strip().splitlines() or ["?"])[-1], r.stderr.strip().splitlines()[-1:] if r.returncode else "")
    godot("--headless", "--import", "--path", "game")
    # studio close-ups
    items = [{"path": f"res://assets/v3/{a.folder}/{n}_wreck.glb", "paint_name": f"{n}_v3", "folder": a.folder, "scheme": "player", "out": f"{O}/studio_{n}",
              "shots": [{"name": "a", "yaw": -40, "pitch": 40, "fill": 1.0, "focus": 0.4}, {"name": "b", "yaw": 140, "pitch": 55, "fill": 1.0, "focus": 0.4}]}
             for n in a.names if (ROOT / f"game/assets/v3/{a.folder}/{n}_wreck.glb").exists()]
    (O / "job.json").write_text(json.dumps({"size": [520, 520], "items": items}))
    godot("--path", "game", "res://scenes/art_gallery.tscn", "--", "--art-v3", f"--job={O}/job.json")
    vm = vehicle_missions()
    for n in a.names:
        if a.folder == "mechs":
            mission, lance = "mc2_01", f"--lance={n}:pmwhacksaw"
        else:
            if n not in vm:
                continue
            mission, lance = vm[n], "--lance=atlas:pmwhacksaw"
        for tag, cam in (("near", "-,58,110"), ("far", "-,58,240"))[:1 if a.near_only else 2]:
            godot("--path", "game", "res://scenes/dev_force_mission.tscn", "--", "--art-v3", f"--mission={mission}", lance,
                  "--player-scheme=player_default", f"--wreck={n}", f"--cam-view={cam}", "--no-hud", f"--screenshot={O}/mis_{n}_{tag}.png",
                  "--size=1280x720", "--frames=240")
    from PIL import Image, ImageDraw
    cw, ch = 400, 320
    S = Image.new("RGB", (cw * 4, ch * len(a.names)), (30, 30, 30)); d = ImageDraw.Draw(S)
    for r, n in enumerate(a.names):
        cells = []
        for tag in ("near", "far"):
            p = O / f"mis_{n}_{tag}.png"
            if p.exists():
                im = Image.open(p).convert("RGB"); w, h = im.size
                box = (w // 2 - 320, h // 2 - 256, w // 2 + 320, h // 2 + 256) if tag == "near" else (w // 2 - 160, h // 2 - 128, w // 2 + 160, h // 2 + 128)
                cells.append((f"{n} in game {tag} (58 deg, {'110' if tag == 'near' else '240'} m)", im.crop(box).resize((cw, ch))))
        for v in ("a", "b"):
            p = O / f"studio_{n}_{v}.png"
            if p.exists():
                cells.append((f"{n} studio {v}", Image.open(p).convert("RGB").resize((cw, ch))))
        for c, (lab, im) in enumerate(cells[:4]):
            S.paste(im, (cw * c, ch * r)); d.text((cw * c + 5, ch * r + 5), lab, fill=(255, 255, 0))
    out = O / ("sheet_" + "_".join(a.names[:3]) + ".png")
    S.save(out); print("sheet", out)


if __name__ == "__main__":
    main()
