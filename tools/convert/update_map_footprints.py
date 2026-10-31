#!/usr/bin/env python3
"""Add the special-area footprints and the gate stats to the already converted map JSON (standard library only).

    python3 -I tools/convert/update_map_footprints.py [--src reference/mc2-source/Source]

convert_all does the same through terrain.convert / map_objects.type_table; this updates game/data/maps/<m>/special_areas.json and the gate
types in objects.json (damage_level, open_radius) without redoing the models and textures.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fit  # noqa: E402
import terrain  # noqa: E402
from packet import PacketFile  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "game", "data")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(ROOT, "reference", "mc2-source", "Source"))
    args = ap.parse_args()
    objects = os.path.join(args.src, "Data", "Objects")
    missions = os.path.join(args.src, "Data", "Missions")
    gate_stats = {}
    files = {f.lower(): f for f in os.listdir(objects)}
    for m in sorted(os.listdir(os.path.join(OUT, "maps"))):
        tpath = os.path.join(OUT, "maps", m, "terrain.json")
        pak = os.path.join(missions, m + ".pak")
        if not (os.path.exists(tpath) and os.path.exists(pak)):
            continue
        areas = terrain.read_special_areas(PacketFile.open(pak))
        with open(os.path.join(OUT, "maps", m, "special_areas.json"), "w") as fh:
            json.dump(areas, fh, separators=(",", ":"))
        opath = os.path.join(OUT, "maps", m, "objects.json")
        data = json.load(open(opath))
        for t in data["types"].values():
            if t.get("class") != 22:
                continue
            fname = files.get(str(t.get("file", "")).lower())
            gd = fit.parse_file(os.path.join(objects, fname)).get("GateData", {}) if fname else {}
            t["damage_level"] = gd.get("DmgLevel", t.get("damage_level", 0))
            t["open_radius"] = gd.get("OpenRadius", 0.0)
            gate_stats[t["appearance"]] = [t["damage_level"], t["open_radius"]]
        json.dump(data, open(opath, "w"), indent=1)
        print(m, "special areas", len(areas))
    print("gates:", gate_stats)


if __name__ == "__main__":
    main()
