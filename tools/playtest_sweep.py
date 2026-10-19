#!/usr/bin/env python3
"""Playtest sweep: run the autoplay bot over every mission and seed, parse each report.

    python3 -I tools/playtest_sweep.py [--missions mc2_01,mc2_02] [--seeds 1,2,3] [--jobs 4]
                                       [--max-seconds 1800] [--out docs/reports/playtest/<date>]

Each run is `godot --headless -s res://tools/autoplay.gd -- <seed> <max> --mission=<m> --damage`
(about 17 s wall). Raw logs go to <out>/logs/<mission>_s<seed>.log; the parsed results to
<out>/results.json, one record per run:

  mission, seed, result (WON|LOST|PLAYING|ERROR), t_end, player_alive, enemies_alive,
  objectives [{index, primary, state, title}], losses [{t, unit, armour, last_hit_by}],
  damage_total, top_attackers [{damage, attacker}], abl_errors, abl_missing, wall_s

and a summary table to stdout. The sweep never edits the game; it is a read-only probe.
"""

import argparse
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAME = ROOT / "game"
GODOT = "godot"

R_END = re.compile(r"^seed (\d+) end t=(\d+) result=(\w+)\s+player alive (\d+)\s+enemies alive (\d+)")
R_LOST = re.compile(r"^t=\s*([\d.]+)\s+LOST (.+?) \(.*?armour (\d+)%.*?last hit by (.+?)\)$")
R_OBJ = re.compile(r"^\s+obj (\d+) ([Ps])( hidden)?: (.+?)  (.*)$")
R_DMG = re.compile(r"^damage to lance: (\d+) from (\d+) attackers")
R_ATT = re.compile(r"^\s{4}\s*(\d+)\s{2}(.+)$")
R_OBJDONE = re.compile(r"^t=\s*([\d.]+)\s+objective done: (.+)$")


def parse(text: str) -> dict:
    r = {"result": "ERROR", "t_end": None, "player_alive": None, "enemies_alive": None, "objectives": [],
         "objective_times": [], "losses": [], "damage_total": None, "attackers": None, "top_attackers": [],
         "abl_errors": None, "abl_missing": None}
    in_att = False
    for line in text.splitlines():
        if m := R_END.match(line):
            r.update(result=m[3], t_end=int(m[2]), player_alive=int(m[4]), enemies_alive=int(m[5]))
        elif m := R_LOST.match(line):
            r["losses"].append({"t": float(m[1]), "unit": m[2], "armour": int(m[3]), "last_hit_by": m[4]})
        elif m := R_OBJDONE.match(line):
            r["objective_times"].append({"t": float(m[1]), "title": m[2].strip()})
        elif m := R_DMG.match(line):
            r.update(damage_total=int(m[1]), attackers=int(m[2]))
            in_att = True
            continue
        elif m := R_OBJ.match(line):
            in_att = False
            r["objectives"].append({"index": int(m[1]), "primary": m[2] == "P", "hidden": bool(m[3]),
                                    "state": m[4].strip(), "title": m[5].strip()})
        elif line.startswith("abl errors:"):
            r["abl_errors"] = line.split(":", 1)[1].strip()
        elif line.startswith("abl natives missing:"):
            r["abl_missing"] = line.split(":", 1)[1].strip()
        if in_att and (m := R_ATT.match(line)):
            r["top_attackers"].append({"damage": int(m[1]), "attacker": m[2].strip()})
    return r


def run_one(mission: str, seed: int, max_s: int, logdir: Path) -> dict:
    t0 = time.time()
    try:
        p = subprocess.run([GODOT, "--headless", "--path", str(GAME), "-s", "res://tools/autoplay.gd", "--",
                            str(seed), str(max_s), f"--mission={mission}", "--damage"],
                           capture_output=True, text=True, timeout=1200)
        out = p.stdout + ("\n--- stderr ---\n" + p.stderr if p.stderr.strip() else "")
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        out += "\n--- TIMEOUT after 1200 s ---"
    (logdir / f"{mission}_s{seed}.log").write_text(out)
    rec = parse(out)
    rec.update(mission=mission, seed=seed, wall_s=round(time.time() - t0, 1))
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--missions", help="comma list (default: every game/data/missions/mc2_NN.json)")
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--max-seconds", type=int, default=1800)
    ap.add_argument("--out", default=str(ROOT / "docs" / "reports" / "playtest" / date.today().isoformat()))
    a = ap.parse_args()
    missions = a.missions.split(",") if a.missions else sorted(
        p.stem for p in (GAME / "data" / "missions").glob("mc2_??.json"))
    seeds = [int(s) for s in a.seeds.split(",")]
    out = Path(a.out)
    (out / "logs").mkdir(parents=True, exist_ok=True)
    jobs = [(m, s) for m in missions for s in seeds]
    print(f"{len(jobs)} runs ({len(missions)} missions x {len(seeds)} seeds), {a.jobs} at a time", flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(a.jobs) as ex:
        results = list(ex.map(lambda j: run_one(j[0], j[1], a.max_seconds, out / "logs"), jobs))
    results.sort(key=lambda r: (r["mission"], r["seed"]))
    (out / "results.json").write_text(json.dumps(results, indent=1) + "\n")
    print(f"done in {time.time() - t0:.0f} s -> {out / 'results.json'}\n")
    print(f"{'mission':8} " + " ".join(f"s{s:<6}" for s in seeds) + " won")
    by = {}
    for r in results:
        by.setdefault(r["mission"], {})[r["seed"]] = r
    for m in missions:
        cells = []
        for s in seeds:
            r = by[m][s]
            cells.append(f"{r['result'][:1]}{(r['t_end'] or 0):>5}s")
        won = sum(1 for s in seeds if by[m][s]["result"] == "WON")
        print(f"{m:8} " + " ".join(cells) + f"  {won}/{len(seeds)}")
    wins = sum(1 for r in results if r["result"] == "WON")
    errs = sum(1 for r in results if r["result"] == "ERROR")
    print(f"\nwon {wins}/{len(results)} runs; {sum(1 for m in missions if any(by[m][s]['result']=='WON' for s in seeds))}"
          f"/{len(missions)} missions won at least once; {errs} runs errored")
    return 0


if __name__ == "__main__":
    sys.exit(main())
