#!/usr/bin/env python3
"""The original's per-weapon effect definitions, as the baseline for game/data/weapon_fx.json.

    python3 -I tools/art/weapon_fx_original.py [--src reference/mc2-source/Source/Data] [--write]

Chain (verified against the Shared Source): component weapon.special_fx -> Objects/Effects.csv row (column 0 =
effect id; columns 1-3 and 5 name the gosFX trail/bolt effect, muzzle flare, hit and miss effects in
Effects/mc2.fx; column 4 = the weapon-bolt object number) -> line N of Objects/object2.rsp (line 0 is <NULL>)
-> the bolt's FIT. A [BeamProjectileData] bolt is a held beam (BeamDuration s, BulgeWidth, MidEdgeRGB = core,
MiddleRGB = glow, RGB as written); a [BoltProjectileData] bolt is a flying streak (ProjectileLength, BulgeWidth,
Velocity in world units/s, Front/MidEdge/Middle/Back colours, which the editor wrote as BGR and
weaponbolt.cpp:304-309 swaps; ArcEffect/ArcHeight lob it; AreaEffectRadius splashes). World units are 0.2 m
(MCLib/Terrain.cpp:63). Only numbers and names are taken, no art.

--write merges the result into game/data/weapon_fx.json as each entry's "original" block and leaves every other
key (the hand-tuned look) alone. Without it, prints the table.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/convert"))
import fit  # noqa: E402

M_PER_WU = 0.2


def hexrgb(v, bgr):
    v = int(v) & 0xFFFFFF
    r, g, b = (v >> 16) & 255, (v >> 8) & 255, v & 255
    if bgr:
        r, b = b, r
    return "#%02x%02x%02x" % (r, g, b)


def _hex_fix(path, f):
    """fit.py reads 0x... as 0 (atol semantics); the bolt FITs write most colours in hex."""
    for line in open(path, encoding="cp1252"):
        line = fit.strip_comment(line).strip()
        m = fit.STATEMENT.match(line)
        if m and m.group(5).strip().lower().startswith("0x"):
            for block in f.values():
                if m.group(4) in block:
                    block[m.group(4)] = int(m.group(5).strip().rstrip(";"), 16)
    return f


def bolt(path):
    f = _hex_fix(path, fit.parse_file(str(path)))
    if "BeamProjectileData" in f:
        d = f["BeamProjectileData"]
        return {"kind": "beam", "fit": path.name, "beam_s": d.get("BeamDuration", 0.0),
                "width_m": round(d.get("BulgeWidth", 1.0) * M_PER_WU, 3), "core": hexrgb(d.get("MidEdgeRGB", 0xFFFFFF), False),
                "glow": hexrgb(d.get("MiddleRGB", 0xFFFFFF), False), "texture": d.get("TextureName", ""),
                "uv_rate": d.get("UVAnimRate", 0.0), "uv_repeat": d.get("UVRepeat", 1.0), "unit_len_m": round(d.get("UnitLength", 1.0) * M_PER_WU, 2),
                "wiggle": d.get("BeamWiggle", 0.0)}
    d = f["BoltProjectileData"]
    out = {"kind": "bolt", "fit": path.name, "length_m": round(d.get("ProjectileLength", 0.0) * M_PER_WU, 2),
           "width_m": round(d.get("BulgeWidth", 1.0) * M_PER_WU, 3), "speed_mps": round(d.get("Velocity", 0.0) * M_PER_WU, 1),
           "front": hexrgb(d.get("FrontRGB", 0), True), "mid_edge": hexrgb(d.get("MidEdgeRGB", 0), True),
           "middle": hexrgb(d.get("MiddleRGB", 0), True), "back": hexrgb(d.get("BackRGB", 0), True),
           "after_hit_s": d.get("AfterHitTime", 0.0)}
    if d.get("ArcEffect"):
        out["arc_m"] = round(d.get("ArcHeight", 0.0) * M_PER_WU, 1)
    if d.get("PointLight"):
        out["light"] = hexrgb(d.get("LightRGB", 0), True)
    if d.get("AreaEffectRadius"):
        out["area_m"] = round(d["AreaEffectRadius"] * M_PER_WU, 1)
    if d.get("GosEffectId"):
        out["gos_trail"] = d["GosEffectId"]
    return out


def table(src):
    objects = src / "Objects"
    rows = list(csv.reader(open(objects / "Effects.csv", encoding="cp1252", newline="")))
    rsp = [l.strip() for l in open(objects / "object2.rsp", encoding="cp1252")]
    files = {p.name.lower(): p for p in objects.iterdir()}
    comps = json.load(open(ROOT / "game/data/components.json"))
    used = {}
    for c in comps:
        w = c.get("weapon")
        if w:
            used.setdefault(int(w["special_fx"]), []).append(c["name"])
    out = {}
    # The effect id is the data row's index (row 0, "No Weapon Here", is id 0 although its first cell says 3).
    for sid, r in enumerate(rows[1:]):
        if len(r) < 6 or sid not in used:
            continue
        e = {"weapons": sorted(used[sid]), "trail": r[1], "flare": r[2], "hit": r[3], "miss": r[5]}
        obj = int(r[4])
        if 0 < obj < len(rsp) and rsp[obj].lower() in files:
            e.update(bolt(files[rsp[obj].lower()]))
        out[str(sid)] = e
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(ROOT / "reference/mc2-source/Source/Data"))
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    t = table(Path(a.src))
    if not a.write:
        print(json.dumps(t, indent=1))
        return
    dst = ROOT / "game/data/weapon_fx.json"
    data = json.load(open(dst)) if dst.exists() else {"weapons": {}}
    for sid, orig in t.items():
        data.setdefault("weapons", {}).setdefault(sid, {})["original"] = orig
    dst.write_text(json.dumps(data, indent="\t") + "\n")
    print("wrote", dst, len(t), "weapons")


if __name__ == "__main__":
    main()
