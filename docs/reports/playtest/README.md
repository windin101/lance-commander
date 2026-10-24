# Playtest sweeps

Each dated folder is one run of `tools/playtest_sweep.py`: the autoplay bot (`game/tools/autoplay.gd`)
plays each mission on several seeds. A folder holds:

- `results.json`: one record per run.
- `meta.json`: the commit, the bot's hash, the seeds and the time caps.
- `logs/`: the raw logs.
- `README.md`: the hand-written findings.

The balance gate (`remake-kit/gates/sweep_balance.py`) reads the newest `results.json`. A mission
passes when it is won on 2 of 3 seeds.

## Time caps

- A run that hasn't ended by its cap is scored PLAYING, which counts as no win.
- The default cap is 1800 s of game time.
- Some missions' winning line is slow by design. They get a longer cap from `MISSION_MAX_SECONDS`
  in the sweep tool:

| mission | cap | why |
|---|---|---|
| mc2_14 | 4500 s | Solo stealth mech: the guides' line (take the airport, avoid patrols, hop between bays) takes about an hour. One of 3 seeds won at 3943 s on 2026-10-24 (I21). |

- Each run records its cap as `max_seconds` in `results.json`. `meta.json` lists them all under
  `max_seconds_by_mission`.
- `--flat-cap` gives every mission `--max-seconds` instead.
- Folders made before 2026-10-24 ran every mission at 1800 s.
