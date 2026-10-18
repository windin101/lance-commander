"""Convert the MC2 source release's text data into JSON under game/data/.

Usage: python3 -I tools/convert/convert_all.py [--src reference/mc2-source/Source]

Output is derived from Microsoft's Shared Source release and stays under its
EULA (docs/MC2-SOURCE-EULA.md): non-commercial use only.
"""

import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chassis  # noqa: E402
import components  # noqa: E402
import fit  # noqa: E402
import strings_rc  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "game", "data")
SLICE_MISSIONS = ["mc2_01"]


def write(rel, data):
    path = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False, sort_keys=False)
        fh.write("\n")
    return path


def heat_table(path):
    with open(path, encoding="cp1252", newline="") as fh:
        rows = [r for r in csv.reader(fh) if r and not r[0].startswith("//")]
    keys = ["heat", "shutdown_pct", "ammo_explosion_pct", "move_mod", "fire_mod", "injuries"]
    return [dict(zip(keys, (float(c) if "." in c else int(c) for c in r[:6]))) for r in rows]


HIT_TABLE_SIZE = 3 * 4 * 11  # sections x arcs x armour locations (mech.cpp:568)


def gamesys(path):
    g = fit.parse_file(path)
    # gamesys.fit declares c[131] but the code reads 132 entries. The game's reader
    # stops at the declared count, so the last slot keeps the global array's 0.
    table = g["Mech:FireWeapon"]["HitLocationTable"]
    g["Mech:FireWeapon"]["HitLocationTable"] = table + [0] * (HIT_TABLE_SIZE - len(table))
    return g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(ROOT, "reference", "mc2-source", "Source"))
    src = ap.parse_args().src
    data = os.path.join(src, "Data")
    objects = os.path.join(data, "Objects")
    missions = os.path.join(data, "Missions")
    report = []

    comps = components.load(os.path.join(objects, "compbas.csv"))
    by_id = {c["id"]: c for c in comps}
    write("components.json", comps)
    report.append(f"components: {len(comps)}")

    n = 0
    for name in sorted(os.listdir(objects)):
        path = os.path.join(objects, name)
        if name.lower().endswith(".csv") and chassis.is_chassis_csv(path):
            ch = chassis.load(path, by_id)
            write(f"chassis/{os.path.splitext(name)[0].lower()}.json", ch)
            n += 1
    report.append(f"chassis: {n}")

    write("heat.json", heat_table(os.path.join(objects, "heat.csv")))
    write("gamesys.json", gamesys(os.path.join(missions, "gamesys.fit")))
    write("campaign.json", fit.parse_file(os.path.join(data, "Campaign", "campaign.fit")))

    for m in SLICE_MISSIONS:
        write(f"missions/{m}.json", fit.parse_file(os.path.join(missions, m + ".fit")))
    report.append(f"missions: {', '.join(SLICE_MISSIONS)}")

    warriors = os.path.join(missions, "Warriors")
    pilots = {}
    for name in sorted(os.listdir(warriors)):
        if name.lower().endswith(".fit"):
            pilots[os.path.splitext(name)[0].lower()] = fit.parse_file(os.path.join(warriors, name))
    write("pilots.json", pilots)
    report.append(f"pilot files: {len(pilots)}")

    strings = strings_rc.load(os.path.join(src, "Script1.rc"), os.path.join(src, "resource.h"))
    write("strings.json", {str(k): v for k, v in sorted(strings.items())})
    report.append(f"strings: {len(strings)}")

    print("\n".join(report))


if __name__ == "__main__":
    main()
