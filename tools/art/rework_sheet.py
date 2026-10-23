#!/usr/bin/env python3
"""Quality contact sheets for the HD rework audit (renders by game/scenes/art_gallery.tscn).

    python3 -I tools/art/rework_sheet.py job  OUT_DIR [--kinds mech,vehicle,object] [--only a,b]   # writes OUT_DIR/job.json
    (godot --path game res://scenes/art_gallery.tscn -- --job=OUT_DIR/job.json, under the godot lock)
    python3 -I tools/art/rework_sheet.py sheet OUT_DIR                                          # writes OUT_DIR/sheet_<kind>_<n>.png

Per asset: three turntable stills (front 3/4, side, rear 3/4) in the Mech Bay studio and a close-up of the upper
body at Mech Lab close-up distance (fill 2.4: what a 1440p lab panel shows of a 10 m mech), with the audit's
pipeline, triangle count, UV status and priority under each row. The asset list and order come from
swarm/gallery/rework_audit.json (tools/art/rework_audit.py).
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAINT = [-3638744, -12566464, -10851768]  # the review paint used by veh_compare.sh
SHOTS = [{"name": "a", "yaw": -28, "fill": 0.9}, {"name": "b", "yaw": 62, "fill": 0.9},
         {"name": "c", "yaw": 152, "fill": 0.9}, {"name": "z", "yaw": -22, "fill": 2.4, "focus": 0.7}]


def job(out, kinds, only):
    rows = json.loads((ROOT / "swarm/gallery/rework_audit.json").read_text())
    items = []
    for r in rows:
        if r["kind"] not in kinds or (only and r["name"] not in only) or r["pipeline"].startswith("HD tree"):
            continue
        res = "res://" + r["file"].removeprefix("game/")
        folder = {"mech": "mechs", "vehicle": "vehicles"}.get(r["kind"], "objects")
        it = {"path": res, "folder": folder, "out": str(Path(out) / f"{r['kind']}_{r['name']}"), "shots": SHOTS}
        if r["kind"] != "object":
            it["paint"] = PAINT
            it["paint_name"] = Path(res).stem
        items.append(it)
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / "job.json").write_text(json.dumps({"size": [480, 480], "items": items}, indent=1))
    print(f"{len(items)} items -> {out}/job.json")


def sheet(out, per=12):
    from PIL import Image, ImageDraw
    out = Path(out)
    rows = json.loads((ROOT / "swarm/gallery/rework_audit.json").read_text())
    for kind in ("mech", "vehicle", "object"):
        rs = [r for r in rows if r["kind"] == kind and (out / f"{kind}_{r['name']}_a.png").exists()]
        rs.sort(key=lambda r: -r["priority"])
        for page in range(0, len(rs), per):
            chunk = rs[page:page + per]
            tw = 240
            S = Image.new("RGB", (4 * tw + 260, len(chunk) * (tw + 4)), (24, 26, 30))
            d = ImageDraw.Draw(S)
            for i, r in enumerate(chunk):
                y = i * (tw + 4)
                for k, s in enumerate("abcz"):
                    p = out / f"{kind}_{r['name']}_{s}.png"
                    if p.exists():
                        S.paste(Image.open(p).convert("RGB").resize((tw, tw)), (k * tw, y))
                tex = ",".join(str(t) for t in r["textures"][:3])
                txt = [f"#{page + i + 1} {r['name']}", r["pipeline"][:34], f"{r['tris']} tris, UV {r['uv']}", f"tex {tex}",
                       f"placed {r['placements']} in {r['missions']} missions", f"priority {r['priority']}",
                       (r.get("licence") or "")[:34]]
                for j, t in enumerate(txt):
                    d.text((4 * tw + 8, y + 8 + 16 * j), t, fill=(230, 230, 230) if j == 0 else (170, 180, 190))
            p = out / f"sheet_{kind}_{page // per + 1:02d}.png"
            S.save(p)
            print(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["job", "sheet"])
    ap.add_argument("out")
    ap.add_argument("--kinds", default="mech,vehicle,object")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    if a.cmd == "job":
        job(a.out, a.kinds.split(","), set(filter(None, a.only.split(","))))
    else:
        sheet(a.out)


if __name__ == "__main__":
    sys.exit(main())
