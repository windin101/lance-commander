#!/usr/bin/env python3
"""Playtest sweep: run the autoplay bot over every mission and seed, parse each report.

    python3 -I tools/playtest_sweep.py [--missions mc2_01,mc2_02] [--seeds 1,2,3] [--jobs 4]
                                       [--max-seconds 1800] [--out docs/reports/playtest/<date>]
                                       [--bot-args "--fit-lance"]

The whole sweep holds the shared Godot locks (swarm/locks/godot, as `swarm lock godot` takes
it, and the repo's .godot.lock), so it never runs beside an import or another agent's Godot.

Each run is `godot --headless -s res://tools/autoplay.gd -- <seed> <max> --mission=<m> --damage`
(about 17 s wall). Raw logs go to <out>/logs/<mission>_s<seed>.log; the parsed results to
<out>/results.json, one record per run:

  mission, seed, result (WON|LOST|PLAYING|ERROR), t_end, player_alive, enemies_alive,
  objectives [{index, primary, state, title}], losses [{t, unit, armour, last_hit_by}],
  damage_total, top_attackers [{damage, attacker}], abl_errors, abl_missing, wall_s,
  force (what the bot deployed), support [{t, kind, target}]

and a summary table to stdout. The sweep never edits the game; it is a read-only probe.

Time caps: every mission runs to --max-seconds (1800 s) except those in MISSION_MAX_SECONDS. These
are missions whose walkthrough line is slow by design. mc2_14 (a solo stealth mech) is won by the
guides' stealth line in about an hour, so it gets 4500 s. --flat-cap uses --max-seconds for all.
Each run's cap is in its results.json record ("max_seconds") and in meta.json
("max_seconds_by_mission"), so a gate or a reader can tell a PLAYING at the cap from a stall.
"""

import argparse
import fcntl
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MISSION_MAX_SECONDS = {
    "mc2_14": 4500,  # solo stealth: 1 of 3 seeds won at 3943 s (2026-10-24, I21)
}
GAME = ROOT / "game"
GODOT = "godot"

R_END = re.compile(r"^seed (\d+) end t=(\d+) result=(\w+)\s+player alive (\d+)\s+enemies alive (\d+)")
R_LOST = re.compile(r"^t=\s*([\d.]+)\s+LOST (.+?) \(.*?armour (\d+)%.*?last hit by (.+?)\)$")
R_OBJ = re.compile(r"^\s+obj (\d+) ([Ps])( hidden)?: (.+?)  (.*)$")
R_DMG = re.compile(r"^damage to lance: (\d+) from (\d+) attackers")
R_DEALT = re.compile(r"^damage by lance: (\d+); kills (\d+)")
R_ATT = re.compile(r"^\s{4}\s*(\d+)\s{2}(.+)$")
R_OBJDONE = re.compile(r"^t=\s*([\d.]+)\s+objective done: (.+)$")
R_SUPPORT = re.compile(r"^t=\s*([\d.]+)\s+SUPPORT (\S+) (.*)$")


def parse(text: str) -> dict:
    r = {"result": "ERROR", "t_end": None, "player_alive": None, "enemies_alive": None, "objectives": [],
         "objective_times": [], "losses": [], "damage_total": None, "attackers": None, "top_attackers": [],
         "abl_errors": None, "abl_missing": None, "force": None, "support": [], "damage_dealt": None, "kills": None}
    in_att = False
    for line in text.splitlines():
        if m := R_END.match(line):
            r.update(result=m[3], t_end=int(m[2]), player_alive=int(m[4]), enemies_alive=int(m[5]))
        elif m := R_LOST.match(line):
            r["losses"].append({"t": float(m[1]), "unit": m[2], "armour": int(m[3]), "last_hit_by": m[4]})
        elif m := R_OBJDONE.match(line):
            r["objective_times"].append({"t": float(m[1]), "title": m[2].strip()})
        elif m := R_SUPPORT.match(line):
            r["support"].append({"t": float(m[1]), "kind": m[2], "target": m[3].strip()})
        elif line.startswith("force:"):
            r["force"] = line.split(":", 1)[1].strip()
        elif m := R_DEALT.match(line):
            r.update(damage_dealt=int(m[1]), kills=int(m[2]))
            continue  # the attacker table follows
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


def run_one(mission: str, seed: int, max_s: int, logdir: Path, extra: list, script: str) -> dict:
    t0 = time.time()
    try:
        p = subprocess.run([GODOT, "--headless", "--path", str(GAME), "-s", script, "--",
                            str(seed), str(max_s), f"--mission={mission}", "--damage", *extra],
                           capture_output=True, text=True, timeout=max(1200, max_s // 2))
        out = p.stdout + ("\n--- stderr ---\n" + p.stderr if p.stderr.strip() else "")
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        out += f"\n--- TIMEOUT after {max(1200, max_s // 2)} s ---"
    (logdir / f"{mission}_s{seed}.log").write_text(out)
    rec = parse(out)
    rec.update(mission=mission, seed=seed, wall_s=round(time.time() - t0, 1))
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--missions", help="comma list (default: every game/data/missions/mc2_NN.json)")
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--max-seconds", type=int, default=1800)
    ap.add_argument("--out", default=str(ROOT / "docs" / "reports" / "playtest" / date.today().isoformat()))
    ap.add_argument("--reparse", action="store_true", help="rebuild <out>/results.json from its logs (no Godot)")
    ap.add_argument("--script", default="res://tools/autoplay.gd", help="bot script (A/B against an older bot)")
    ap.add_argument("--bot-args", default="", help="extra autoplay arguments, space separated")
    ap.add_argument("--flat-cap", action="store_true", help="ignore MISSION_MAX_SECONDS: every mission gets --max-seconds")
    a = ap.parse_args()
    extra = a.bot_args.split()
    if a.reparse:
        out = Path(a.out)
        old = {(r["mission"], r["seed"]): r for r in json.loads((out / "results.json").read_text())}
        results = []
        for (mission, seed), r in sorted(old.items()):
            rec = parse((out / "logs" / f"{mission}_s{seed}.log").read_text())
            rec.update(mission=mission, seed=seed, wall_s=r.get("wall_s"))
            results.append(rec)
        (out / "results.json").write_text(json.dumps(results, indent=1) + "\n")
        print(f"reparsed {len(results)} runs -> {out / 'results.json'}")
        return 0
    locks = []
    for path in (ROOT / "swarm" / "locks" / "godot", ROOT / ".godot.lock"):
        path.parent.mkdir(parents=True, exist_ok=True)
        f = open(path, "w")
        print(f"waiting for {path.relative_to(ROOT)} ...", flush=True)
        fcntl.flock(f, fcntl.LOCK_EX)  # released when the process exits
        locks.append(f)
    missions = a.missions.split(",") if a.missions else sorted(
        p.stem for p in (GAME / "data" / "missions").glob("mc2_??.json"))
    seeds = [int(s) for s in a.seeds.split(",")]
    out = Path(a.out)
    (out / "logs").mkdir(parents=True, exist_ok=True)
    jobs = [(m, s) for m in missions for s in seeds]
    cap = {m: a.max_seconds if a.flat_cap else MISSION_MAX_SECONDS.get(m, a.max_seconds) for m in missions}
    print(f"{len(jobs)} runs ({len(missions)} missions x {len(seeds)} seeds), {a.jobs} at a time", flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(a.jobs) as ex:
        results = list(ex.map(lambda j: run_one(j[0], j[1], cap[j[0]], out / "logs", extra, a.script), jobs))
    for r in results:
        r["max_seconds"] = cap[r["mission"]]
    results.sort(key=lambda r: (r["mission"], r["seed"]))
    (out / "results.json").write_text(json.dumps(results, indent=1) + "\n")
    git = lambda *c: subprocess.run(["git", *c], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    import hashlib
    (out / "meta.json").write_text(json.dumps({  # what was measured: other agents change the sim meanwhile
        "commit": git("rev-parse", "--short", "HEAD"), "dirty": git("status", "--short", "game/scripts", "game/data", "game/tools").splitlines(),
        "scripts_diff_sha1": hashlib.sha1(git("diff", "HEAD", "--", "game/scripts").encode()).hexdigest()[:10],
        "bot_sha1": hashlib.sha1((GAME / a.script.removeprefix("res://")).read_bytes()).hexdigest()[:10],
        "seeds": seeds, "max_seconds": a.max_seconds, "max_seconds_by_mission": cap, "bot_args": extra,
        "jobs": a.jobs}, indent=1) + "\n")
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
        print(f"{m:8} " + " ".join(cells) + f"  {won}/{len(seeds)}" + (f"  (cap {cap[m]} s)" if cap[m] != a.max_seconds else ""))
    wins = sum(1 for r in results if r["result"] == "WON")
    errs = sum(1 for r in results if r["result"] == "ERROR")
    print(f"\nwon {wins}/{len(results)} runs; {sum(1 for m in missions if any(by[m][s]['result']=='WON' for s in seeds))}"
          f"/{len(missions)} missions won at least once; {errs} runs errored")
    return 0


if __name__ == "__main__":
    sys.exit(main())
