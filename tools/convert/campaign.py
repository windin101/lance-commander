"""Campaign-layer data (docs/specs/campaign-layer.md): purchase files and the pilot roster.

purchase/<name>.json  {"all_components": bool, "components": [ids], "mechs": [chassis], "pilots": [profiles]}
                      for Purchase01..24 and the PurBonusNN files (names lowercased)
roster.json           ["pmwflash", ...]: Data/Objects/Pilots.csv, the campaign's fixed pilot roster
"""

import os
import re

import fit


def convert_purchase_files(missions_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    names = []
    for f in sorted(os.listdir(missions_dir)):
        if not re.fullmatch(r"(purchase\d+|purbonus\d+)\.fit", f.lower()):
            continue
        p = fit.parse_file(os.path.join(missions_dir, f))
        comps = p.get("Components", {})
        out = {
            "all_components": bool(comps.get("AllComponents", False)),
            "components": [int(v) for k, v in comps.items() if re.fullmatch(r"Component\d+", k)],
            "mechs": [str(v).lower() for k, v in p.get("Mechs", {}).items() if re.fullmatch(r"Mech\d+", k)],
            "pilots": [str(v).lower() for k, v in p.get("Pilots", {}).items() if re.fullmatch(r"Pilot\d+", k)],
        }
        name = os.path.splitext(f)[0].lower()
        names.append(name)
        import json
        with open(os.path.join(out_dir, name + ".json"), "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
    return names


def roster(objects_dir):
    """The campaign pilot roster (Pilots.csv: one profile name per row)."""
    path = os.path.join(objects_dir, "Pilots.csv")
    out = []
    with open(path, encoding="cp1252") as fh:
        for line in fh:
            cell = line.split(",")[0].strip().strip('"')
            if cell and not cell.startswith("//") and cell.lower() != "pilots":
                out.append(cell.lower())
    return out
