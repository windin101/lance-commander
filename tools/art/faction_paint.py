#!/usr/bin/env python3
"""Faction paint schemes and the mission-colour -> faction table (HD rework, 2026-10-23).

    python3 -I tools/art/faction_paint.py      # writes game/data/faction_paint.json and prints the unassigned schemes

Each unit in a mission file carries a colour triple (BaseColor, HighlightColor1, HighlightColor2). This maps the
triples of the Davion, Steiner, Liao and bandit forces to one scheme each. The scheme colours are the master style
guide's role schemes (docs/art/STYLE-GUIDE.md 2.3, 2026-10-31), which replaced the earlier reference palettes. Rebels keep their mission colours. A triple is "verified" when a mission's own warrior brain names give the
faction (mc2_17: mc2_17_EC1_Steiner_Boss, mc2_17_a2_Liao_Mech_1 ...), "inferred" when it only appears in missions
whose briefings and objectives name that faction. Every other triple keeps the mission's own colours and is listed
under "unassigned" with the missions it appears in, for Lee to choose schemes later.

Scheme fields (read by game/scripts/world/paint_scheme.gd and the v2 unit shader):
  base, hl1, hl2   colours ("#rrggbb")
  regions          body region -> "base" | "hl1" | "hl2" | "steel"; regions: body, head (cockpit cowl), arms,
                   upper_legs, lower_legs, feet, weapons, plates (large outer armour plates on limbs and shoulders)
  piping, stripe, band   null or "hl1" / "hl2" / "#rrggbb": inset piping along big panels' edges, a thin vertical
                   stripe down the leg plates, a horizontal band across arm and leg plates
  decal            colour of unit numbers and insignia; insignia: true adds a generic shield crest by the number
  pattern          "plain" | "woodland" | "snow" | "urban" (the player's choices) | "thorin" | "arkab" (faction
                   camouflage), drawn in the base-coloured regions; display_name: the force's name for the UI;
                   insignia_shape: the generic crest beside the number (shield, star or chevron; no unit insignia)
"""
import collections
import glob
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PLAIN = {"body": "base", "head": "base", "arms": "base", "upper_legs": "base", "lower_legs": "base",
         "feet": "base", "weapons": "steel", "plates": "base"}
# Schemes follow docs/art/STYLE-GUIDE.md 2.3 (master guide, 2026-10-31; it replaces the 2026-10-23/24 reference
# palettes): base = the guide's primary, hl1 = secondary, hl2 = trim. "role" is the guide's role name; display_name is
# what the UI shows, always the role, never a house or product name (2.3 licence rule). The keys stay as they were
# (davion, steiner, liao, bandits) because tools and tests address schemes by key; ROLE_OF_FACTION below is the
# mapping of MC2's houses and factions to the guide's roles.
ROLE_OF_FACTION = {
    "player": "Player lance",
    "davion": "Red-and-gold realm",
    "steiner": "Blue-and-silver realm",
    "liao": "Green-and-gold realm",
    "bandits": "Pirates",
    # schemes the guide defines that no MC2 mission colour maps to yet (kept ready for the mapping)
    "opfor": "Enemy forces",
    "realm_crimson_black": "Crimson-and-black realm",
    "realm_purple": "Purple realm",
    "clans": "Invader clans",
    "civilian": "Civilian / industrial",
}
SCHEMES = {
    # player lance (default): gunmetal, amber, light steel trim; amber edge piping and band
    "player_default": {"role": "Player lance", "base": "#4a5560", "hl1": "#f2a21f", "hl2": "#d5dee3", "regions": PLAIN,
                       "piping": "hl1", "stripe": None, "band": "hl1", "decal": "#d5dee3", "insignia": False,
                       "pattern": "plain"},
    # enemy / OpFor generic: oxblood, charcoal outer plates, bone trim
    "opfor": {"display_name": "Enemy forces", "role": "Enemy forces", "base": "#5a2a26", "hl1": "#2a2a2c",
              "hl2": "#b8b2a6", "regions": dict(PLAIN, plates="hl1"), "piping": None, "stripe": None, "band": "hl2",
              "decal": "#b8b2a6", "insignia": False, "pattern": "plain"},
    # red-and-gold realm (MC2: Davion): red armour, gold piping and bands, black feet
    "davion": {"display_name": "Red-and-gold realm", "role": "Red-and-gold realm", "base": "#b0262b", "hl1": "#e8c14a",
               "hl2": "#1a1a1a", "regions": dict(PLAIN, feet="hl2"), "piping": "hl1", "stripe": None, "band": "hl1",
               "decal": "#e8c14a", "insignia": True, "insignia_shape": "star", "pattern": "plain"},
    # blue-and-silver realm (MC2: Steiner): blue armour, silver outer plates and head, gold piping
    "steiner": {"display_name": "Blue-and-silver realm", "role": "Blue-and-silver realm", "base": "#2c4f9e",
                "hl1": "#d8dce0", "hl2": "#e8c14a", "regions": dict(PLAIN, head="hl1", plates="hl1"), "piping": "hl2",
                "stripe": None, "band": "hl1", "decal": "#d8dce0", "insignia": True, "insignia_shape": "shield",
                "pattern": "plain"},
    # its commander: gold piping, stripe and band, gold numbers, to stand out
    "steiner_boss": {"display_name": "Blue-and-silver realm", "role": "Blue-and-silver realm", "base": "#2c4f9e",
                     "hl1": "#d8dce0", "hl2": "#e8c14a", "regions": dict(PLAIN, head="hl1", plates="hl1"),
                     "piping": "hl2", "stripe": "hl2", "band": "hl2", "decal": "#e8c14a", "insignia": True,
                     "insignia_shape": "shield", "pattern": "plain"},
    # crimson-and-black realm: crimson armour, black plates, gold piping (no MC2 force maps here yet)
    "realm_crimson_black": {"display_name": "Crimson-and-black realm", "role": "Crimson-and-black realm",
                            "base": "#7a1d24", "hl1": "#1e1e22", "hl2": "#c9a646", "regions": dict(PLAIN, plates="hl1"),
                            "piping": "hl2", "stripe": None, "band": None, "decal": "#c9a646", "insignia": True,
                            "insignia_shape": "chevron", "pattern": "plain"},
    # green-and-gold realm (MC2: Liao): green armour, gold stripes and bands, black feet
    "liao": {"display_name": "Green-and-gold realm", "role": "Green-and-gold realm", "base": "#2f6b4f",
             "hl1": "#c9a646", "hl2": "#1e1e22", "regions": dict(PLAIN, feet="hl2"), "piping": None, "stripe": "hl1",
             "band": "hl1", "decal": "#c9a646", "insignia": True, "insignia_shape": "chevron", "pattern": "plain"},
    # its heir: the same with gold piping
    "liao_son": {"display_name": "Green-and-gold realm", "role": "Green-and-gold realm", "base": "#2f6b4f",
                 "hl1": "#c9a646", "hl2": "#1e1e22", "regions": dict(PLAIN, feet="hl2"), "piping": "hl1",
                 "stripe": "hl1", "band": "hl1", "decal": "#c9a646", "insignia": True, "insignia_shape": "chevron",
                 "pattern": "plain"},
    # purple realm: purple armour, light-steel plates, gold piping (no MC2 force maps here yet)
    "realm_purple": {"display_name": "Purple realm", "role": "Purple realm", "base": "#6e3a8a", "hl1": "#d8dce0",
                     "hl2": "#c9a646", "regions": dict(PLAIN, plates="hl1"), "piping": "hl2", "stripe": None,
                     "band": None, "decal": "#d8dce0", "insignia": True, "insignia_shape": "shield", "pattern": "plain"},
    # invader clans: olive-steel, bronze plates, near-black trim (no MC2 force maps here yet)
    "clans": {"display_name": "Invader clans", "role": "Invader clans", "base": "#3e4a44", "hl1": "#b7792b",
              "hl2": "#0e0e10", "regions": dict(PLAIN, plates="hl1"), "piping": None, "stripe": "hl2", "band": None,
              "decal": "#b7792b", "insignia": True, "insignia_shape": "chevron", "pattern": "plain"},
    # pirates / bandits: the guide gives no hexes ("2-3 clashing earth colours, mismatched patches"): tan, rust and
    # olive in the "arkab" blotch pattern, and rust plates for the mismatched patches
    "bandits": {"display_name": "Pirates", "role": "Pirates", "base": "#c9a77a", "hl1": "#9a5a2a", "hl2": "#5f6a46",
                "regions": dict(PLAIN, plates="hl1"), "piping": None, "stripe": None, "band": None, "decal": "#3a2a1a",
                "insignia": False, "pattern": "arkab"},
    # civilian / industrial: safety yellow, slate plates (the guide names no trim: near-black, as the hazard chevrons)
    "civilian": {"display_name": "Civilian / industrial", "role": "Civilian / industrial", "base": "#c9a230",
                 "hl1": "#5b6770", "hl2": "#1e1e22", "regions": dict(PLAIN, plates="hl1"), "piping": None,
                 "stripe": None, "band": "hl2", "decal": "#1e1e22", "insignia": False, "pattern": "plain"},
}
# triple key: base|hl1|hl2, lower-case hex
TRIPLES = {
    "#004080|#96a7af|#96a7af": ("steiner", "steiner", "verified", "mc2_17 brains (EC1 ... Steiner)"),
    "#ffffff|#9d3226|#000040": ("steiner", "steiner_boss", "verified", "mc2_17_EC1_Steiner_Boss"),
    "#96a7af|#435987|#435987": ("steiner", "steiner", "inferred", "mc2_10 and mc2_23 (Steiner missions), mc2_19, mc2_20"),
    "#96a7af|#435987|#435978": ("steiner", "steiner", "inferred", "mc2_10, the triple above with a one-digit slip"),
    "#ffffff|#435987|#435987": ("steiner", "steiner", "inferred", "mc2_24 (Steiner mission)"),
    "#004080|#a7af96|#96a7af": ("steiner", "steiner", "inferred", "mc2_20 prison guards, the Steiner triple with highlights reordered"),
    "#809267|#f4c28a|#de701f": ("liao", "liao", "verified", "mc2_17 brains (a2_Liao_Mech_1 ...)"),
    "#008040|#f4e9d7|#f4e9d7": ("liao", "liao_son", "verified", "mc2_17 Liao son"),
    "#809267|#de701f|#f4c28a": ("liao", "liao", "inferred", "mc2_07 (a Liao mission), the Liao triple with highlights swapped"),
    "#7d624f|#deb154|#deb154": ("davion", "davion", "inferred", "mc2_12, mc2_16, mc2_20: only in missions whose briefings name Davion"),
    "#c5a783|#ece2c6|#4e4844": ("davion", "davion", "inferred", "mc2_13 and mc2_16 (Davion missions)"),
    "#c5a783|#ece2c6|#808080": ("davion", "davion", "inferred", "mc2_13, the triple above"),
    "#c5a783|#feca32|#feca32": ("davion", "davion", "inferred", "mc2_13 (Davion) power armour"),
    "#a98150|#d2b576|#4e4844": ("davion", "davion", "inferred", "mc2_11 and mc2_20 (Davion missions)"),
    "#b02828|#ddbb50|#000000": ("bandits", "bandits", "inferred", "mc2_01-04, mc2_09: bandit missions"),
    "#e25638|#d2b576|#623100": ("bandits", "bandits", "inferred", "mc2_01, mc2_02, mc2_08: bandit missions"),
    "#e25638|#d2b576|#d2b576": ("bandits", "bandits", "inferred", "mc2_01, mc2_02, mc2_04 (bandit camp guards, infantry ambush)"),
    "#e25638|#d2d576|#623100": ("bandits", "bandits", "inferred", "mc2_05, mc2_08, the first bandit triple with a one-digit slip"),
    "#b02828|#4e4844|#4e4844": ("bandits", "bandits", "inferred", "mc2_03, mc2_09: bandit base guards"),
    "#809267|#ddbb50|#ff8040": ("bandits", "bandits", "inferred", "mc2_04 (a bandit mission): harassers, centipedes, LRM carriers"),
    # the two largest unassigned triples (2026-10-24, medium confidence: unit mix and mission briefings, no brain names)
    "#626934|#e08e52|#b02828": ("liao", "liao", "inferred-medium", "mc2_06 and mc2_18-20: fields Sha Yu (a Liao 'Mech by the Mechlopedia) with Liao vehicle waves; mc2_06 and mc2_19 briefings name Liao"),
    "#626934|#e08e52|#e08e52": ("liao", "liao", "inferred-medium", "mc2_20, the triple above with one highlight"),
    "#004080|#feca32|#feca32": ("steiner", "steiner", "inferred-medium", "blue and gold on Zeus (a Steiner 'Mech), Werewolf, Legion, Bushwacker; mc2_23 and mc2_24 are Steiner missions"),
}
# rebels and every other triple keep the mission's own colours (Lee, 2026-10-23)


def hx(v):
    return "#%06x" % (int(v) & 0xFFFFFF)


def main():
    seen = collections.defaultdict(lambda: {"missions": set(), "units": 0, "teams": set()})
    for mp in sorted(glob.glob(str(ROOT / "game/data/missions/mc2_[0-9][0-9].json"))):
        mis = Path(mp).stem
        fit = json.loads(Path(mp).read_text())
        for i in range(1, int(fit.get("Parts", {}).get("NumParts", 0)) + 1):
            p = fit.get(f"Part{i}")
            if not p:
                continue
            k = f"{hx(p['BaseColor'])}|{hx(p['HighlightColor1'])}|{hx(p['HighlightColor2'])}"
            seen[k]["missions"].add(mis); seen[k]["units"] += 1; seen[k]["teams"].add(int(p.get("TeamID", 0)))
    triples = {k: {"faction": f, "scheme": s, "evidence": ev, "note": note,
                   "missions": sorted(seen[k]["missions"]) if k in seen else []}
               for k, (f, s, ev, note) in TRIPLES.items()}
    unassigned = []
    for k, v in sorted(seen.items(), key=lambda kv: -kv[1]["units"]):
        if k in TRIPLES or v["teams"] == {0}:
            continue   # mapped, or a player team's own (the player scheme replaces those)
        unassigned.append({"triple": k, "units": v["units"], "missions": sorted(v["missions"])})
    out = {"_doc": "tools/art/faction_paint.py (generated): faction schemes and mission colour triples -> faction",
           "roles": ROLE_OF_FACTION, "schemes": SCHEMES, "triples": triples, "unassigned": unassigned}
    (ROOT / "game/data/faction_paint.json").write_text(json.dumps(out, indent=1) + "\n")
    print(f"{len(triples)} triples mapped, {len(unassigned)} unassigned (kept as the missions paint them):")
    for u in unassigned:
        print(f"  {u['triple']}  {u['units']:3d} units  {' '.join(u['missions'])}")


if __name__ == "__main__":
    main()
