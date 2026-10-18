"""compbas.csv -> component list, following MasterComponent::initEXCEL
(MCLib/cmponent.cpp:85).

Column order: id, form, name, crits, recycle, heat, tons, damage, BR, RP, range,
8 location columns (No / Yes / count), missile type, fields, special FX, ammo id.
Rows whose form is not in ComponentFormString ("undefined", "Removed") are
rejected by the game and are skipped here.

Quirks kept on purpose:
- heat is truncated to an integer ((unsigned long)atof).
- the "Fields" column (inferno/LBX/artillery bits) is read but never used; the
  only weapon flag the game sets is streak, derived from missile type "ST".
- the recycle and damage columns are reused per form: ammo per ton and
  explosive damage for Ammo, dissipation for HeatSink, range factor for Sensors.
"""

import csv

FORMS = [
    "Simple", "Cockpit", "Sensors", "Actuator", "Engine", "HeatSink", "Weapon",
    "EnergyWeapon", "BallisticWeapon", "MissileWeapon", "Ammo", "JumpJet", "Case",
    "LifeSupport", "Gyroscope", "PowerAmplifier", "ECM", "Probe", "Jammer", "Bulk",
]
WEAPON_FORMS = {"Weapon", "EnergyWeapon", "BallisticWeapon", "MissileWeapon"}
RANGES = ["short", "medium", "long"]
# Body-location order used by the game (MECH_BODY_LOCATION_*).
LOCATIONS = ["head", "ctorso", "ltorso", "rtorso", "larm", "rarm", "lleg", "rleg"]
AMMO_TYPES = {"1": "limited", "SRM": "srm", "LRM": "lrm", "ST": "streak"}


def _num(text, default=0.0):
    """atof semantics: leading number or 0 ("NA", "na", "" -> 0)."""
    text = (text or "").strip()
    out = ""
    for ch in text:
        if ch.isdigit() or ch in ".-+" or (ch in "eE" and out):
            out += ch
        else:
            break
    try:
        return float(out)
    except ValueError:
        return default


def parse_row(row):
    row = row + [""] * (32 - len(row))
    form = row[1].strip()
    if form not in FORMS:
        return None
    rng = row[10].strip().lower()
    if rng in ("0", ""):
        range_type = None
    elif rng in RANGES:
        range_type = rng
    else:
        raise ValueError(f"bad weapon range {rng!r} for component {row[0]}")
    locations = {}
    for i, loc in enumerate(LOCATIONS):
        cell = row[11 + i].strip()
        locations[loc] = -1 if cell == "No" else (0 if cell == "Yes" else int(_num(cell)))
    ammo_type = AMMO_TYPES.get(row[19].strip(), "none")
    recycle, damage = _num(row[4]), _num(row[7])
    comp = {
        "id": int(row[0]),
        "form": form,
        "name": row[2].strip(),
        "crits": int(_num(row[3])),
        "tons": _num(row[6]),
        "br": _num(row[8]),
        "rp": int(_num(row[9])),
        "locations": locations,
    }
    if form in WEAPON_FORMS:
        comp["weapon"] = {
            "damage": damage,
            "recycle": recycle,
            "heat": int(_num(row[5])),
            "range": range_type,
            "ammo_type": ammo_type,
            "streak": ammo_type == "streak",
            "special_fx": int(_num(row[21])),
            "ammo_id": int(_num(row[22])),
        }
    elif form == "Ammo":
        comp["ammo"] = {"per_ton": int(recycle), "explosive_damage": damage}
    elif form == "HeatSink":
        comp["heatsink"] = {"dissipation": damage}
    elif form == "Sensors":
        comp["sensor"] = {"range_factor": damage}
    elif form == "JumpJet":
        comp["jumpjet"] = {"range_mod": damage}
    elif form == "ECM":
        comp["ecm"] = {"effect": damage, "range": recycle}
    elif form in ("Jammer", "Probe"):
        comp[form.lower()] = {"effect": damage}
    return comp


def load(path):
    with open(path, encoding="cp1252", newline="") as fh:
        rows = list(csv.reader(fh))
    out = []
    for row in rows[1:]:  # first line is the header, as loadMasterList skips it
        if not row or not row[0].strip().lstrip("-").isdigit():
            continue
        comp = parse_row(row)
        if comp is not None:
            out.append(comp)
    return out
