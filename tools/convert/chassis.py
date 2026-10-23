"""Chassis CSV (atlas.csv etc.) -> chassis + variants, following
BattleMechType::init (Code/mech.cpp:657) and BattleMech::init(variant)
(Code/mech.cpp:1373).

Addressing is 1-based for rows and columns, like the spreadsheet. Each variant
is a 97-row block: name at row 23+97v, items at rows 26+97v.. (72 slots, the
CompBas# in column 5), crit slots at rows 102+97v.. (12 rows), internal
structure at 114+97v and armour at 115+97v.

Body-location columns use the game's "stupidNewSageColumns" map {2,7,5,6,3,4,8,9}
for head, ctorso, ltorso, rtorso, larm, rarm, lleg, rleg; rear torso armour is
in columns 10-12 (rltorso, rrtorso, rctorso).

Bulk components ("Armor Plating") are not inventory: the game counts them and
adds 32 armour points each, spread by fixed percentages (mech.cpp:1879). The
converter reports the count; the simulation applies the bonus.
"""

import csv
import os

ROWS_PER_VARIANT = 97
MAX_ITEMS = 72
CRIT_ROWS = 12
LOCATIONS = ["head", "ctorso", "ltorso", "rtorso", "larm", "rarm", "lleg", "rleg"]
LOCATION_COLS = [2, 7, 5, 6, 3, 4, 8, 9]
REAR_ARMOR_COLS = {"rltorso": 10, "rrtorso": 11, "rctorso": 12}


class Sheet:
    def __init__(self, rows):
        self.rows = rows

    def cell(self, row, col):
        """1-based row and column; blank when out of range."""
        if row < 1 or row > len(self.rows):
            return ""
        r = self.rows[row - 1]
        return r[col - 1].strip() if 1 <= col <= len(r) else ""

    def num(self, row, col, default=0):
        text = self.cell(row, col)
        try:
            return float(text) if "." in text else int(text)
        except ValueError:
            return default


def _locations(sheet, row):
    out = {loc: sheet.num(row, col) for loc, col in zip(LOCATIONS, LOCATION_COLS)}
    return out


def _armor(sheet, row):
    out = _locations(sheet, row)
    for loc, col in REAR_ARMOR_COLS.items():
        out[loc] = sheet.num(row, col)
    return out


def parse(rows, components_by_id):
    s = Sheet(rows)
    chassis = {
        "name": s.cell(3, 2),
        "tonnage": s.num(3, 5),
        "heat_index": s.num(4, 5),
        "load_index": s.num(5, 5),
        "max_run_speed": s.num(7, 5),
        "torso_yaw_rate": s.num(8, 5),
        "max_torso_yaw": s.num(9, 5),
        "animation": s.cell(10, 2),
        "br": s.num(10, 5),
        "cbills": s.num(11, 5),
        "max_armor": s.num(12, 5),
        "desc_string": s.num(5, 2),
        "abbr_string": s.num(6, 2),
        "allow": {
            s.cell(r, 7).lower().replace(" ", "_"): s.cell(r, 8) == "Yes"
            for r in range(3, 10) if s.cell(r, 7)
        },
        "max_internal": _locations(s, 17),
        "base_armor": _armor(s, 18),
        "variants": [],
    }
    v = 0
    while s.cell(22 + ROWS_PER_VARIANT * v, 1) == "VariantID":
        base = ROWS_PER_VARIANT * v
        items = []
        for i in range(MAX_ITEMS):
            cid = s.num(26 + base + i, 5, 255)
            items.append(cid if cid not in (0, 255) else None)
        crit_slots = {}
        for loc, col in zip(LOCATIONS, LOCATION_COLS):
            slots = []
            for r in range(CRIT_ROWS):
                text = s.cell(102 + base + r, col)
                if text.lstrip("-").isdigit():
                    # The design tool fills every slot; one pointing at an empty item
                    # is a free space (the game maps it to 255, mech.cpp:1720).
                    idx = int(text)
                    slots.append(idx if 0 <= idx < MAX_ITEMS and items[idx] is not None else None)
            crit_slots[loc] = slots
        armor_plates = sum(
            1 for cid in items
            if cid is not None and components_by_id.get(cid, {}).get("form") == "Bulk"
        )
        chassis["variants"].append({
            "index": v,
            "id": s.cell(22 + base, 2),
            "name": s.cell(23 + base, 2),
            "hidden": s.cell(21 + base, 3) == "Hidden" and s.cell(21 + base, 4) == "1",
            "items": items,  # index = item number referenced by crit_slots
            "crit_slots": crit_slots,
            "internal": _locations(s, 114 + base),
            "armor": _armor(s, 115 + base),
            "armor_plates": armor_plates,
        })
        v += 1
    return chassis


def is_chassis_csv(path):
    with open(path, encoding="cp1252", errors="replace") as fh:
        return fh.readline().startswith("BaseChassisInfo")


def load(path, components_by_id):
    with open(path, encoding="cp1252", newline="") as fh:
        return parse(list(csv.reader(fh)), components_by_id)


def mech_profiles(objects_dir):
    """[MechProfile] of the mech object FITs, by profile (= chassis CSV) name, lower case:
    MoveType (0 ground, 1 air: the copters, mech.cpp:675) and LOSFactor (default 1.0)."""
    import fit
    out = {}
    for name in sorted(os.listdir(objects_dir)):
        if not name.lower().endswith(".fit"):
            continue
        try:
            f = fit.parse_file(os.path.join(objects_dir, name))
        except Exception:
            continue
        if f.get("ObjectClass", {}).get("ObjectTypeNum") != 2:
            continue
        prof = f.get("MechProfile", {})
        pname = str(prof.get("ProfileName", "")).lower()
        if pname and pname not in out:
            out[pname] = {"move_type": int(prof.get("MoveType", 0)), "los_factor": float(prof.get("LOSFactor", 1.0))}
    return out
