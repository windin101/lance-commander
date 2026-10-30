#!/usr/bin/env python3
"""Hunter (LANCE-18) after v3_mech.py's write stage: add the belts' UV strip to game/assets/v3/vehicles/hunter.v3.json
(from hunter_lowpoly.py's tracks.json) and check the glb's node tree: Hunter_Turret, track_l, track_r and the sixteen wheel_* nodes, each with a mesh.

    python3 -I tools/art/v3/hunter_finish.py"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import hd_rig as R  # noqa: E402

ROOT = HERE.parents[2]
WORK = Path("/mnt/nvme1n1p1/mc2-rework/v3/hunter")
DST = ROOT / "game/assets/v3/vehicles"


def main():
    t = json.loads((WORK / "tracks.json").read_text())
    side = json.loads((DST / "hunter.v3.json").read_text())
    strip = [round(t["v0"], 6), round(t["v_len"], 6), t["belt_m"]]
    side["tracks"] = {"track_l": strip, "track_r": strip}
    side["tracks_note"] = ("both belts share one tread strip (v0, v_len, belt_m): hunter_lowpoly.py maps each belt's "
                           "arclength modulo belt_m (2 link pitches) into it, track_l in the left half of the atlas "
                           "strip, track_r in the right; v increases toward the rear on the visible ground run")
    (DST / "hunter.v3.json").write_text(json.dumps(side, indent=1))
    g, b = R.load_glb(str(DST / "hunter.glb"))
    names = {n.get("name"): n for n in g["nodes"]}
    for need in ("Hunter_Turret", "track_l", "track_r"):
        assert need in names and "mesh" in names[need], f"{need}: no mesh"
    wheels = [n["name"] for n in g["nodes"] if n.get("name", "").startswith("wheel_") and "mesh" in n]
    assert len(wheels) == 16, wheels
    print("nodes with meshes:", [n["name"] for n in g["nodes"] if "mesh" in n], "strip", strip)


if __name__ == "__main__":
    main()
