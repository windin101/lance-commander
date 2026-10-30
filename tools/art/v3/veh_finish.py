#!/usr/bin/env python3
"""Vehicle finish (LANCE-18 Hunter, generalised in LANCE-19), after v3_mech.py's write stage: add the belts' UV strip, the
gun's pitch range and the notes to game/assets/v3/vehicles/<unit>.v3.json (strip from veh_lowpoly.py's tracks.json,
the rest from tools/art/v3/<unit>_prep.json "sidecar") and check the glb's node tree: every part named in the config has
a mesh, the wheels, steer pivots and belts are all there.

    python3 -I tools/art/v3/veh_finish.py <unit>"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import hd_rig as R  # noqa: E402
import veh_prep as VP  # noqa: E402

ROOT = HERE.parents[2]
DST = ROOT / "game/assets/v3/vehicles"


def main(unit):
    cfg = VP.load_cfg(unit)
    work = Path(f"/mnt/nvme1n1p1/mc2-rework/v3/{unit}")
    side = json.loads((DST / f"{unit}.v3.json").read_text())
    tc = cfg.get("tracks")
    if tc:
        t = json.loads((work / "tracks.json").read_text())
        strip = [round(t["v0"], 6), round(t["v_len"], 6), t["belt_m"]]
        belts = [u["name"] for u in tc["units"]] if tc.get("units") else ["track_l", "track_r"]
        side["tracks"] = {b_: strip for b_ in belts}
        side["tracks_note"] = ("both belts share one tread strip (v0, v_len, belt_m): veh_lowpoly.py maps each belt's "
                               "arclength modulo belt_m (%d link pitches) into it, track_l in the left half of the atlas "
                               "strip, track_r in the right; v increases toward the rear on the visible ground run" % t["n_links"])
    sc = cfg.get("sidecar", {})
    for k, v in sc.items():
        side[k] = v
    (DST / f"{unit}.v3.json").write_text(json.dumps(side, indent=1))
    g, b = R.load_glb(str(DST / f"{unit}.glb"))
    names = {n.get("name"): n for n in g["nodes"]}
    need = cfg.get("require_meshes", [])
    for nm in need + ([u["name"] for u in tc["units"]] if tc and tc.get("units") else ["track_l", "track_r"] if tc else []):
        assert nm in names and "mesh" in names[nm], f"{nm}: no mesh"
    wheels = [n["name"] for n in g["nodes"] if n.get("name", "").startswith("wheel_") and "mesh" in n]
    want = 2 * len(cfg["wheels"]["list"]) if cfg.get("wheels") else 0
    assert len(wheels) == want, (len(wheels), want)
    steers = [n["name"] for n in g["nodes"] if n.get("name", "").startswith("steer_")]
    assert len(steers) == 2 * len(cfg.get("wheels", {}).get("steer", [])), steers
    print("nodes with meshes:", [n["name"] for n in g["nodes"] if "mesh" in n], "steer", steers, "strip", side.get("tracks"))


if __name__ == "__main__":
    main(sys.argv[1])
