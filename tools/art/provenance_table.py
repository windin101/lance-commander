#!/usr/bin/env python3
"""Regenerate the per-mech table in docs/art-provenance.md from original/hd/<mech>/provenance.json
and the review verdicts in swarm/state.json, so the table is generated, not remembered.

    python3 -I tools/art/provenance_table.py [--check]

Seeds, turn and fit come from provenance.json. The review column is "approved" unless the mech
has an open swarm issue titled "HD <mech>: <verdict>", in which case it is "redo, <id>: <verdict>".
Notes worth keeping by hand go in NOTES below. --check exits 1 if the file would change.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "art-provenance.md"
HEAD = "| Mech | Concept seed | Mesh seed | Turn | Fit (mean surface distance) | Phase 7 review |"
NAMES = {"urbanmech": "UrbanMech", "jaegermech": "JaegerMech", "bloodasp": "BloodAsp", "shayu": "ShaYu",
         "madcat": "MadCat", "laohu": "LaoHu", "mediumcopter": "Medium copter", "heavycopter": "Heavy copter"}
NOTES = {
    "catapult": "concept lost the cockpit glass",
    "menshen": "automatic orientation check misleading (the concept faces left); front checked by eye",
    "raven": "front checked by eye (automatic check favoured the turned pose)",
    "flea": "front checked by eye (automatic check favoured the turned pose)",
    "werewolf": "re-fitted with --turn; P3 I9: yellow band on the shins",
    "bushwacker": "batch 2 concept (seed 8) replaced the centred-rack drift; fit 0.964 -> 0.436 m",
    "mediumcopter": "uses the vehicle prompt (--prompt vehicles)",
    "heavycopter": "uses the vehicle prompt (--prompt vehicles)",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    state = json.loads((ROOT / "swarm" / "state.json").read_text())
    redo = {}
    for i in state["issues"]:
        if i["status"] == "open" and i["title"].startswith("HD ") and ":" in i["title"]:
            name, verdict = i["title"][3:].split(":", 1)
            if verdict.strip() in ("turn", "reseed_concept", "reseed_mesh", "reject"):  # cosmetic notes (e.g. I9) stay approved
                redo[name.strip().lower()] = f"**redo, {i['id']}**: {verdict.strip()}"
            elif verdict.strip().startswith("look"):  # "HD <asset>: look call ...": built and installed, waiting on Lee's look call
                redo[name.strip().lower()] = f"**look call, {i['id']}**"
    rows = []
    for glb in sorted((ROOT / "game" / "assets" / "mechs").glob("*_hd.glb")):
        m = glb.name[: -len("_hd.glb")]
        pj = ROOT / "original" / "hd" / m / "provenance.json"
        p = json.loads(pj.read_text()) if pj.exists() else {}
        if p.get("kind") == "adapted":  # a licensed third-party model: stl_rig.py (walkers) or stl_hd.py (copters)
            fit = "exact (rigged on the skeleton)" if "stl_rig" in p.get("tool", "stl_rig") else f"{p.get('fit_m', 0):.3f} m (fitted)"
            rows.append(f"| {NAMES.get(m, m.capitalize())} (`{m}`) | adapted | adapted | n/a | {fit} | "
                        f"{redo.get(m, 'approved')}; {p['source']}, {p['licence']}; notice in `{m}_hd.LICENSE.md`, {p.get('tris', '?')} tris |")
            continue
        if p.get("kind") == "cad":  # built in SolidCraft (tools/art/cad_mech.py): no seeds, no fit
            src = f"tools/cad/{m}_hd.py"
            rows.append(f"| {NAMES.get(m, m.capitalize())} (`{m}`) | CAD | CAD | n/a | exact (built on the original pivots) | "
                        f"{redo.get(m, 'approved')}; SolidCraft build from `{src}`, {p.get('tris', '?')} tris |")
            continue
        cs = p.get("concept_seed", "not recorded")
        ms = p.get("mesh_seed", "1234 (default, inferred)")
        turn = "yes" if p.get("turn") else ("no" if "turn" in p else "not recorded")
        fit = f"{p['fit_m']:.3f} m" if p.get("fit_m") is not None else "not recorded"
        review = redo.get(m, "approved")
        if p.get("render_zoom", 1.0) != 1.0:
            review += f"; render zoom {p['render_zoom']:g}"
        if m in NOTES:
            review += f"; {NOTES[m]}"
        rows.append(f"| {NAMES.get(m, m.capitalize())} (`{m}`) | {cs} | {ms} | {turn} | {fit} | {review} |")
    table = "\n".join([HEAD, "|---|---|---|---|---|---|"] + rows)
    s = DOC.read_text()
    start = s.index("| Mech | Concept seed |")
    end = s.index("\n\n", start)
    new = s[:start] + table + s[end:]
    # adapted vehicles and map props (tools/art/stl_hd.py): their own generated table after the Hunyuan vehicle table
    vrows = []
    for glb in sorted((ROOT / "game" / "assets" / "vehicles").glob("*_hd.glb")) + sorted((ROOT / "game" / "assets" / "objects").glob("*_hd.glb")):
        v = glb.name[: -len("_hd.glb")]
        pj = ROOT / "original" / "hd" / v / "provenance.json"
        p = json.loads(pj.read_text()) if pj.exists() else {}
        if p.get("kind") == "adapted":
            vrows.append(f"| {v} | {p.get('source', '')} | {p.get('licence', '')} | {p.get('fit_m', 0):.3f} m | "
                         f"{redo.get(v, 'approved')}; {', '.join(p.get('stl', []))}, {p.get('tris', '?')} tris |")
    vb, ve = "<!-- adapted-vehicles:begin (generated by tools/art/provenance_table.py) -->", "<!-- adapted-vehicles:end -->"
    vtab = (vb + "\nAdapted from licensed 3D-print sculpts by `tools/art/stl_hd.py` (these replace any Hunyuan row above):\n\n"
            "| Vehicle or map prop | Source | Licence | Fit (mean surface distance) | Phase 7 review |\n|---|---|---|---|---|\n" + "\n".join(vrows) + "\n" + ve)
    if vb in new:
        new = new[:new.index(vb)] + vtab + new[new.index(ve) + len(ve):]
    else:
        vs = new.index("| Vehicle | Concept seed |")
        vend = new.index("\n\n", vs)
        new = new[:vend] + "\n\n" + vtab + new[vend:]
    if a.check:
        print("up to date" if new == s else "STALE: run tools/art/provenance_table.py")
        return 0 if new == s else 1
    DOC.write_text(new)
    print(f"wrote {len(rows)} mech rows ({sum(1 for r in rows if 'redo,' in r)} redo)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
