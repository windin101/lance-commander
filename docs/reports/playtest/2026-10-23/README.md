# Playtest sweep 2026-10-23: the autoplay bot plays like a player

`results.json` here is the final sweep (24 missions x seeds 1-3, 1800 s cap, `--jobs 3`,
commit b5738b2 with only the bot and the sweep uncommitted; `meta.json` records it). The gate
(`remake-kit/gates/sweep_balance.py`) reads it: **9 of 24 missions won on at least 2 of 3 seeds**
(was 7). Bar: 2 of 3 on all 24. Steps and A/B sweeps are in `steps/`.

## What the bot does now (`game/tools/autoplay.gd`)

**Force** (`_player_force`; `--fit-lance` keeps the mission's own parts). This is a documented
approximation of a campaign player arriving at the mission, built with the game's own `Campaign`
rules (campaign-layer.md 3, 5, 8, 9). mc2_01 has PlayLogistics 0, so it keeps its FIT lance.
- **C-Bills:** 80000, plus the starting lance's value (sell-back is 100%), plus the primary
  objective payouts of every earlier mission. No losses, no salvage income. Drop weight, not
  money, is the binding limit from mc2_04 on.
- **What's on sale:** the chassis of this and every earlier purchase file (a mech bought earlier
  is still owned), plus the PurBonus files of earlier missions.
- **How the drop weight is filled:** about one mech per 60 t of the limit. Each pick is the
  heaviest affordable chassis within 15 t of an even share of the weight left, in its dearest
  variant. Stock loadouts only: the bot doesn't use the Mech Lab.
- **Pilots:** the best available ones, grown +1 piloting and +2 gunnery per earlier mission
  (capped at 80).

The first version took the heaviest chassis that fit, which gave two Atlases on 200 t. Lances of
"assault + 30 t scouts" lost the scouts first. Against the FIT lances with the same bot
(`steps/4-leash` vs `steps/4-leash-fitlance`), the force choice is neutral: 6 vs 7 missions passing.

| mission | deployed (t of limit, RP) |
|---|---|
| mc2_01 | FIT: Werewolf, 2 Bushwacker (140/190, 22000) |
| mc2_02 | 3 Bushwacker (165/170, 6000) |
| mc2_03 | 2 Shootist, Hunchback (190/190, 16000) |
| mc2_04 | Zeus, Shootist, Bushwacker (205/205, 16000) |
| mc2_05 | Shootist, 2 Bushwacker, Hollander (215/220, 7000) |
| mc2_06 | Zeus, 2 Shootist, Hollander (255/260, 25000) |
| mc2_07 | Zeus, Shootist, Hunchback (200/200, 6000) |
| mc2_08 | 2 Bushwacker, Hunchback (160/160, 0) |
| mc2_09 | 2 Shootist, 2 Bushwacker, Hunchback (300/300, 30000) |
| mc2_10 | Shootist, 3 Bushwacker, Sha Yu (275/280, 6000) |
| mc2_11 | 2 Men Shen, Starslayer (160/160, 0) |
| mc2_12 | 3 Men Shen, Sha Yu (205/210, 0) |
| mc2_13 | Shootist, Catapult, Men Shen, Sha Yu (230/230, 0) |
| mc2_14 | Lao Hu (75/75, 0) |
| mc2_15, mc2_16 | 2 Lao Hu, Shootist, Catapult, Raven (320/320, 6000 / 16000) |
| mc2_17 | 2 Shootist, Catapult, 2 Men Shen, Raven (350/350, 0) |
| mc2_18 | 2 Lao Hu, Shootist, Catapult, Wolfhound (320/320, 16000) |
| mc2_19 | Shootist, Catapult, 2 Vulture, Shadow Cat, + 1 (330/330, 12000) |
| mc2_20 | 2 Mad Cat, Shootist, Catapult, Wolfhound (320/320, 12000) |
| mc2_21 | Zeus, Mad Cat, Shadow Cat (200/200, 23000) |
| mc2_22 | 2 Mad Cat, Shootist, Catapult, Vulture, + 1 (380/380, 16000) |
| mc2_23 | Mad Cat, Shootist, Catapult, Vulture, Razorback (300/300, 36000) |
| mc2_24 | Shootist, 3 Catapult, Vulture, + 3 (450/450, 10000) |

The exact list is the `force` field of each record in `results.json`.

**Objectives** (`_task`, `_obj_task`):
- **Order of work:** active, non-hidden primaries in the designer's order. Specific targets,
  captures and MoveAnyUnitToArea markers come first, then "destroy all / N", extraction last.
  Secondaries are worked only when no primary needs anything. Nearest-first sent mc2_11 to
  objective 3 first, so it was dropped.
- **Hunt targets:** awake and dormant enemies, with walkable ones first. Hovercraft on water are
  skipped.
- **Extraction (I81):** every non-ally mover within 256 m of the point is killed first, then the
  lance moves in.
- **Detours:** RP buildings and ordnance trucks within 700 m are captured first. Unarmed trucks
  close by are shot, unless they can be captured or are within 120 m of a capture target: a fuel
  truck's blast destroyed mc2_03's Mobile HQ.

**Movement and tactics**:
- **Group movement:** each mech moves to a walkable spot around the goal. A mech that gets 90 m
  ahead of the lance centre waits for the rest. A mech whose move leaves it standing four times
  is sent straight at the target.
- **Focus fire:** threats are ranked by DPS per point of health left (mechs x1.5, distance
  penalty). The nearest guns go onto each target until they can strip it in about 12 s. A
  mech keeps its current target if that target scores at least 0.7 of the best.
- **Staying together:** in a fight, a mech more than 160 m from the rest comes back unless its
  target is in reach.
- **Pulling back:** a mech under 30% health goes to the repair truck, or behind the lance, while
  at least half the lance keeps fighting. It rejoins at 70%.
- **Lulls:** with a truck out, the lance waits by it until everyone is above 70%.
- **Falling back:** when out-gunned 1.5:1 and under 60% health, the lance falls back to the last
  quiet spot. This rarely triggers.
- **Heat and running:** heat is left to the sim's fire discipline (level 20). Run stays on.
- **Captures:** the guards within 85 m are cleared first. One mech captures; the others hold
  around it. A capture that stalls is re-issued, then walked in (works around I85).

**Support** (`_use_support`, every call is logged as `SUPPORT ...`):
- **Idle repair trucks** go to the most damaged mech that is out of the fight.
- **Salvage craft:** on disabled mechs within 600 m, our own first, then the heaviest enemy.
- **Repair truck:** called in a lull when a mech is under 75% health (under 60% in a fight,
  dropped behind the lance).
- **Air strike:** on bunches worth at least 2.5 (mech 2, vehicle 1) within strike reach. Never
  within 70 m of our units or of anything we must capture, never within 60 m of a pending strike,
  at most one per 12 s. A truck's 6000 RP is kept in reserve.
- **Sensor probe:** 450 m toward a goal more than 500 m away, only when RP covers two trucks
  and a strike.

**Harness changes:**
- `--trace` prints each job change and capture stall.
- The report adds `damage by lance` and `kills`.
- Allied losses print as `ALLY LOST`, so they no longer count as lance losses.
- With no armed lance unit left for 30 s, the run stops and scores LOST. Only support vehicles
  keep the mission open in that state (B6, I13).

**Sweep changes** (`tools/playtest_sweep.py`):
- The whole sweep holds `swarm/locks/godot` and `.godot.lock`.
- New options: `--script` (A/B against another bot), `--bot-args=...`, and `--reparse`
  (rebuild results.json from the logs).
- `--jobs` defaults to 3.
- `meta.json` records the commit, the dirty files and the bot hash.
- New fields per run: `force`, `support`, `damage_dealt`, `kills`.

## Wins per mission

- **old bot, old sim:** HEAD ea44ac3's autoplay.gd on 2026-10-20, before the I12 hold-fire change.
- **old bot, same sim:** the same old bot on today's sim.
- **new bot:** the final sweep in this directory.

| mission | old bot, old sim | old bot, same sim | new bot | change |
|---|---|---|---|---|
| mc2_01 | 3 | 3 | 3 | |
| mc2_02 | 3 | 3 | 3 | |
| mc2_03 | 3 | 3 | 3 | |
| mc2_04 | 3 | 3 | 3 | |
| mc2_05 | 3 | 3 | 3 | |
| mc2_06 | 0 | 0 | 1 | |
| mc2_07 | 0 | 0 | **2** | passes |
| mc2_08 | 0 | 0 | 1 | |
| mc2_09 | 0 | 0 | **3** | passes |
| mc2_10 | 1 | 1 | **2** | passes |
| mc2_11 | 0 (stalls) | 0 (stalls) | 1 | |
| mc2_12 | 0 | 0 | 0 | |
| mc2_13 | 0 | 0 | 0 | |
| mc2_14 | 0 | 0 | 0 | |
| mc2_15 | 0 | 1 | 0 | |
| mc2_16 | 2 | **0** | 0 | the sim change, not the bot |
| mc2_17 | 0 | 0 | 0 | |
| mc2_18 | 0 | 0 | 0 | |
| mc2_19 | 0 | 0 | 0 | |
| mc2_20 | 0 | 0 | 0 | |
| mc2_21 | 3 | 3 | 3 | |
| mc2_22 | 0 | 0 | 0 | |
| mc2_23 | 0 | 0 | 0 | |
| mc2_24 | 0 | 0 | 0 | |
| **passing** | **7** | **6** | **9** | |

**Effect of other agents' changes:**
- mc2_16 dropped from 2/3 to 0/3 with the *old* bot when the I12 change landed (b3c9790: pilots
  hold fire on idle enemies). So that drop is the sim change, not the bot.
- The Mech Bay, Mech Lab and Pilots commits (a03458e, 3248cff, b5738b2) changed nothing. The
  2026-10-21 run of this bot on b3c9790 (`steps/6-final-2026-10-21`) and this one on b5738b2
  match on all 72 runs.
- No ABL errors or missing natives on any run.

## Missions under 2 of 3: diagnosis

"dealt/taken" is damage by and to the lance; "k" is kills.

- **mc2_06 (1/3). Bot.**
  - "1. Protect the Base HQ" and "2. Destroy all attacking Liao forces": the bot hunts the
    attackers instead of holding the HQ.
  - Lost s1 and s2 with 13-14 enemies left; won s3 (38 k).
  - Needs: guard the protected building until the waves have come.
- **mc2_08 (1/3). Balance.**
  - 160 t, 0 RP, so no support at all. Won s2.
  - s1 and s3 lost after 51-59 kills at 4:1 dealt/taken (1588-1840 / 412-428), with
    "3 - Destroy ATC Tower BETA" open.
  - The lance is worn down by attrition with no repair possible.
- **mc2_11 (1/3). Balance, plus bot variance.**
  - 160 t, 0 RP; the RP-building detour gives one truck.
  - s1 won (2347/701, 26 k). s2 lost at "3 - Capture Steiner HQ" (Zeus 273). s3 lost at 469 s
    on objective 1 (Jagermech).
- **mc2_12 (0/3). Balance.**
  - 210 t, 0 RP, 5 convoy objectives, 65+ enemies.
  - Objective 1 done every seed; all mechs lost by 413-553 s. Enfield is the top attacker
    (181-279), dealt/taken about 1.5:1.
- **mc2_13 (0/3). Balance, plus game bug I85 (worked around).**
  - 230 t, 0 RP, 44 enemies incl. 21 Powered Armor.
  - Reached 2-3 of 6 primaries, 29-40 kills, then lost the lance (Uller, Enfield, Powered Armor).
  - Before the capture workaround, all seeds stalled to 1800 s at Weapons Facility #3 (I85).
- **mc2_14 (0/3). Balance, plus bot.**
  - A solo 75 t mech (the drop limit), 0 RP, against 4 orbital guns across 10 km and 31 patrols.
  - Gun Alpha done on s2 and s3; the mech dies at 251-541 s.
  - A player sneaks round patrols; the bot has no avoidance (I21).
- **mc2_15 (0/3). Balance.**
  - 320 t, 6000 RP. No primary done; the first mech lost at 67-104 s.
  - Legion tanks deal 461-568 every seed, dealt/taken about 1.6:1.
  - Bot factor: it ignores secondaries a/c (operative route, I22).
- **mc2_16 (0/3). Sim change, then bot.**
  - Was 2/3 before I12; now 0/3 with both bots.
  - Objectives 1-2 done; dies during "3. Destroy All Reinforcements" (Madcat, Vulture 250-366),
    with "4. Capture HQ" open.
  - A player would take the HQ and turret controls (secondaries a, b) and hold. The bot doesn't
    use secondaries for advantage (I23).
- **mc2_17 (0/3). Balance (I24).**
  - The I12 fix holds: the battle now starts at about 77 s, after the cinematic.
  - Then 10-11 threats at once incl. the Highlander guards (453-540 dmg), 0 RP. The lance is
    dead by 183-194 s with 2-3 kills.
- **mc2_18 (0/3). Bot.**
  - "1. Defend City" plus "2. Destroy all": 23-29 kills, dealt/taken about 2.7:1, lost at
    491-851 s with 38-44 enemies left.
  - The bot hunts across the city instead of defending it, and skips the recapture secondaries
    (HQ, Power Gen, Sensor, I25).
- **mc2_19 (0/3). Balance.**
  - "Destroy 1/3 of all enemy forces" (82 units) at 330 t / 12000 RP.
  - 16-23 kills, lance dead by 310-414 s.
- **mc2_20 (0/3). Balance, plus bot.**
  - 3 of 6 primaries on s1 and s2 (55 k, dealt/taken 2.8:1), then the lance is ground down.
    Hollander and Zeus deal 300+.
  - s3 runs to 1800 s on salvaged units (PLAYING).
- **mc2_22 (0/3). Balance, or game (unclear).**
  - Lost by 129-436 s: 12 threats within 25 s of the drop. Partisan AA tanks deal 568-1014 damage
    with 4 AC5 each (2 dmg / 3 s); 10 are in the FIT.
  - Probe that settles it: the Partisans' awake and brain state at t=0-30 (`--shots=200`), to see
    whether the patrols should be converging on the drop zone that early.
- **mc2_23 (0/3). Balance (I29).**
  - 300 t / 36000 RP; 32-40 kills, at most 1 of 2 primaries done, 28-41 enemies left.
- **mc2_24 (0/3). Bot, plus balance.**
  - 450 t / 10000 RP: lost at 349-564 s with 0 of 3 primaries; Bushwacker and Legion deal 200-450.
  - The hidden fuel-truck trigger for the rebel attack (I30) is still not fired. The trucks
    aren't near the lance's route, and the bot ignores hidden objectives, as a player would.

## Balance calls for Lee

Not bugs: the game runs these to spec. Whether they should be this hard is Lee's decision.

1. **No-support missions are not winnable for a player's lance at these drop weights:** mc2_08,
   mc2_11, mc2_12, mc2_13, mc2_14 and mc2_17. The six RP-0 missions win 2 of 18 runs between them.
   The lances out-trade the enemy 1.5-4:1 and still lose to attrition. Options: give them support
   RP, reduce the enemy count, or let the drop weight carry more.
2. **mc2_17 betrayal:** about 10 Steiner units incl. Highlander guards hit 350 t, 0 RP, at once,
   right after the cinematic. The lance dies in under 2 minutes. Retune, or accept it as a
   "retreat and survive" mission.
3. **Mass-enemy missions:** mc2_15 (Legion tanks), mc2_19 (82 units, kill 1/3), mc2_20, mc2_22
   (Partisans) and mc2_23. They drop at 300-380 t and lose with 16-55 kills. The question is
   whether the remake's vehicles are tougher or more accurate than the original's (a combat-rules
   check) or the original is simply this hard. If neither: lighter vehicle damage, or fewer early
   awake groups.
4. **mc2_14 solo mission:** 75 t against 31 patrols over 10 km. Only beatable by stealth; keep
   it, or make the patrols sparser.

## Issues

- **Filed:** I85 (P2, sim). A capture order stalls short of the target: the mech stands 37 m
  from mc2_13's Weapons Facility #3 with TO_CAPTURE forever (`_capture_goal`).
- **Updated:** I81 marked fixed in the bot (MoveAnyUnitToArea markers and extraction clearing).
- **Bot limitations still open:** guard or hold for defend objectives (mc2_06, mc2_18), using
  secondaries for advantage (mc2_15, mc2_16), and patrol avoidance (mc2_14). Each is P3
  (I14-I30).

Repro: `godot --headless --path game -s res://tools/autoplay.gd -- <seed> 1800 --mission=<m> --damage [--trace] [--targets] [--fit-lance]`,
run under `swarm lock godot -- flock .godot.lock`.
