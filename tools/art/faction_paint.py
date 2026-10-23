#!/usr/bin/env python3
"""Faction paint schemes and the mission-colour -> faction table (HD rework, 2026-10-23).

    python3 -I tools/art/faction_paint.py      # writes game/data/faction_paint.json and prints the unassigned schemes

Each unit in a mission file carries a colour triple (BaseColor, HighlightColor1, HighlightColor2). This maps the
triples of the Davion, Steiner, Liao and bandit forces to one scheme each, after Lee's chosen reference palettes in
/mnt/nvme1n1p1/mc2-rework/ref/ucc/ (noted per scheme), and keeps the player's default scheme
(ref/lee_default_scheme_grey_red.png). Rebels keep their mission colours. A triple is "verified" when a mission's own warrior brain names give the
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
SCHEMES = {
    # the player's default (Lee): grey armour, red stripes and inset edge piping
    "player_default": {"base": "#9a9a9a", "hl1": "#d02e11", "hl2": "#4a4a4c", "regions": PLAIN, "piping": "hl1",
                       "stripe": None, "band": "hl1", "decal": "#e8e4dc", "insignia": False, "pattern": "plain"},
    # Davion: follows ref/ucc/la_thorin_color_palette.png: a three-colour blotch camouflage over the whole 'Mech
    # (black-green #242a1f, brown #4b3d23, tan #c2ac69: the "thorin" pattern), gunmetal joints
    "davion": {"display_name": "Davion Regiment", "base": "#4b3d23", "hl1": "#c2ac69", "hl2": "#242a1f",
               "regions": PLAIN, "piping": None, "stripe": None, "band": None, "decal": "#c2ac69", "insignia": True,
               "insignia_shape": "star", "pattern": "thorin"},
    # Steiner: follows ref/ucc/la_lyran_guards_color_palette_REPAINTED_BY_JUSTIN_KASE-1.png: blue the dominant armour
    # (torso, arms, legs), off-white outer plates and head, silver piping, small orange accents (Lee 2026-10-24)
    "steiner": {"display_name": "Steiner Guards", "base": "#d0ccbe", "hl1": "#d06020", "hl2": "#2a4a8a",
                "regions": dict(PLAIN, body="hl2", arms="hl2", upper_legs="hl2", lower_legs="hl2", feet="hl2"), "piping": "#b8bcc2",
                "stripe": None, "band": "hl1", "decal": "#2a4a8a", "insignia": True, "insignia_shape": "shield",
                "pattern": "plain"},
    # a Steiner commander: the same with orange piping and orange numbers, to stand out
    "steiner_boss": {"display_name": "Steiner Guards", "base": "#d0ccbe", "hl1": "#d06020", "hl2": "#2a4a8a",
                     "regions": dict(PLAIN, body="hl2", arms="hl2", upper_legs="hl2", lower_legs="hl2", feet="hl2"), "piping": "hl1",
                     "stripe": "hl1", "band": "hl1", "decal": "#d06020", "insignia": True, "insignia_shape": "shield",
                     "pattern": "plain"},
    # Liao: follows ref/ucc/mccarrons_armored_cavalry_4th_color_palette.png: dark green #003914 with bold white
    # stripes on the shoulders, chest, arms and shins
    "liao": {"display_name": "Liao Armored Cavalry", "base": "#003914", "hl1": "#ffffff", "hl2": "#003914",
             "regions": PLAIN, "piping": None, "stripe": "hl1", "band": "hl1", "decal": "#ffffff", "insignia": True,
             "insignia_shape": "chevron", "pattern": "plain"},
    # Liao's heir: the same with gold piping
    "liao_son": {"display_name": "Liao Armored Cavalry", "base": "#003914", "hl1": "#ffffff", "hl2": "#003914",
                 "regions": PLAIN, "piping": "#c8a050", "stripe": "hl1", "band": "hl1", "decal": "#c8a050",
                 "insignia": True, "insignia_shape": "chevron", "pattern": "plain"},
    # bandits: follows ref/ucc/dracom_arkab_legion_panther_color_palette_REPAINTED_BY_JUSTIN_KASE.png: tans and rust
    # brown with faded dark-green desert blotches (the "arkab" pattern)
    "bandits": {"display_name": "Bandit Legion", "base": "#c9a77a", "hl1": "#9a5a2a", "hl2": "#5f6a46",
                "regions": PLAIN, "piping": None, "stripe": None, "band": None, "decal": "#3a2a1a", "insignia": False,
                "pattern": "arkab"},
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
           "schemes": SCHEMES, "triples": triples, "unassigned": unassigned}
    (ROOT / "game/data/faction_paint.json").write_text(json.dumps(out, indent=1) + "\n")
    print(f"{len(triples)} triples mapped, {len(unassigned)} unassigned (kept as the missions paint them):")
    for u in unassigned:
        print(f"  {u['triple']}  {u['units']:3d} units  {' '.join(u['missions'])}")


if __name__ == "__main__":
    main()
