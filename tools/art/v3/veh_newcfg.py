#!/usr/bin/env python3
"""Write tools/art/v3/<unit>.json (the v3_mech.py settings of a rigid vehicle) from the Hunter's, the unit's work dir
(<unit>_tracks, after veh_prep.py) and its approved v1 provenance. Run after veh_prep.py; edit by hand afterwards.
    python3 -I tools/art/v3/veh_newcfg.py <unit> "<title>" <thingId> <stl file name> [seed]"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import veh_prep as VP  # noqa: E402

unit, title, tid, fname = sys.argv[1:5]
seed = int(sys.argv[5]) if len(sys.argv) > 5 else 17
cfg = VP.load_cfg(unit)
d = json.loads((HERE / "hunter.json").read_text())
work = VP.WORKS / f"{unit}_tracks"
f = json.loads((work / "fit.json").read_text())
parts = [f["node_names"][int(k)] for k in f["xform"]]
d["_doc"] = (f"v3 settings for the {unit} (LANCE-19): rigid vehicle, moving parts split out by tools/art/v3/veh_prep.py from "
             f"{unit}_prep.json (work dir {unit}_tracks), fit from tools/art/v3/{unit}_veh.json via v3_rigid.py.")
d["name"] = unit
d["stl"] = f"/home/leeo/craft/solid/mc2/tv_stl/{tid}/x/files/{fname}"
d["source"] = {"title": title, "author": "RGriffin65", "url": f"https://www.thingiverse.com/thing:{tid}",
               "licence": "CC BY-SA 4.0", "file": fname, "notes": cfg.get("notes", "")}
d["base_glb"] = f"/mnt/nvme1n1p1/mc2-rework/work/{unit}_tracks/{unit}_base.glb"
d["from_v2"] = str(work)
d["wear"]["seed"] = seed
d["wear"]["exposure"] = {p: 1.0 for p in parts if p.startswith(("track_", "wheel_"))}
d["part_region"] = {p: ("weapons" if p.startswith(("track_", "wheel_")) else "body") for p in parts}
(HERE / f"{unit}.json").write_text(json.dumps(d, indent=1))
print("wrote", HERE / f"{unit}.json", parts)
