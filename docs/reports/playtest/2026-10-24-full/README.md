# Playtest sweep 2026-10-24 (full)

This sweep ran all 24 missions on seeds 1-3 with `--jobs 2`.

- **Caps:** per mission (see `../README.md`). Every mission ran to 1800 s except mc2_14, which ran to
  4500 s. Each run's cap is in `results.json` (`max_seconds`) and in `meta.json`
  (`max_seconds_by_mission`).
- **Tree:** the sweep ran on a clean tree at the step-6 head, plus two bot fixes made after a first
  full pass:
  - A turret control the lance can capture is taken rather than its generator destroyed. Destroying
    the generator had cost mc2_20 its fort: 2/3 to 0/3, isolated by running the re-check bot on the
    current sim.
  - The bot no longer shoots an explosive building when one of our own structures is in the blast.
    On mc2_17 an ammo dump had taken out our repair bay.
- **Gate:** `remake-kit/gates/sweep_balance.py` says **FAIL: 10/24 missions under 2 wins**.

## Changes since the 2026-10-24 re-check

- **Sim fixes:**
  - I114: spotter strikes now follow the original.
  - I115: destroyed buildings explode.
  - I116: a control whose generator is gone sleeps and can't be captured.
  - I117: in single player, team 2 is neutral to the player.
- **Sweep tool:** per-mission time caps.
- **Bot:**
  - Plans for these missions:
    - mc2_13: the guides' route.
    - mc2_14: stealth, including breaking contact and ignoring guards that stand still.
    - mc2_17: hold the base.
    - mc2_18: the guides' capture order, plus an RP reserve.
    - mc2_22: hold the corner with a decoy.
    - mc2_23: tease the starport, then build a reception (spare the last target, Long Toms, mines).
    - mc2_24: the east route, then run for the extraction.
  - Behaviour for every mission:
    - shoot explosive buildings under enemies;
    - air-strike a fort's generator when it sits under its own guns;
    - switch off a fort before working an objective under its guns;
    - jump in to capture turret controls;
    - kill aerospotters first.

## Wins (of 3)

| mission | turrets (10-23) | re-check (10-24) | full (10-24) |
|---|---|---|---|
| mc2_01 | 3 | 3 | 3 |
| mc2_02 | 3 | - | 3 |
| mc2_03 | 1 | - | 2 |
| mc2_04 | 2 | - | 3 |
| mc2_05 | 3 | - | 3 |
| mc2_06 | 2 | 3 | 3 |
| mc2_07 | 0 | 2 | 3 |
| mc2_08 | 0 | - | 0 |
| mc2_09 | 0 | 1 | 0 |
| mc2_10 | 3 | 3 | 3 |
| mc2_11 | 0 | - | 0 |
| mc2_12 | 0 | - | 0 |
| mc2_13 | 0 | 0 | 0 |
| mc2_14 | 0 | 0 | 0 (cap 4500 s) |
| mc2_15 | 3 | 3 | 3 |
| mc2_16 | 0 | 2 | 3 |
| mc2_17 | 0 | 3 | 3 |
| mc2_18 | 0 | 0 | 0 |
| mc2_19 | 0 | 2 | 2 |
| mc2_20 | 1 | 2 | 2 |
| mc2_21 | 3 | - | 3 |
| mc2_22 | 0 | 0 | 0 |
| mc2_23 | 0 | 0 | 0 |
| mc2_24 | 0 | 0 | 1 |
| **runs won** | **24/72** | **24/48** | **40/72** |
| **missions at 2/3 or better** | 9 | 9 of 16 | **14** |

A first full pass, before the two bot fixes above, scored 39/72. There, mc2_14 and mc2_18 each won 1
seed, mc2_17 won 2 and mc2_20 won 0. Those 4 missions swing by a seed on small bot changes.

## Under 2/3, with cause

| mission | won | cause | one line |
|---|---|---|---|
| mc2_08 | 0 | bot | 2 of 4 objectives every seed. The SRM turret forts and Hunter/Flea patrols wear the lance down by 646-683 s (I99). |
| mc2_09 | 0 | bot | LRM turrets are the top killer, then Swarm LRM carriers and Lao Hu; 1-2 of 5 objectives (I99). |
| mc2_11 | 0 | bot | LRM pop-up and AC turret forts. Only objective 3 is done, and 10-11 enemies are left at 952-1045 s (I99). |
| mc2_12 | 0 | balance or bot (to check) | A 205 t, 4-mech, 0 RP lance dies by 242-283 s to Enfields after the convoy objective. That is earlier than 10-23 (388-573 s). An A/B with the re-check bot was cut short because another agent held the Godot lock. |
| mc2_13 | 0 | bot | 3 of 6 objectives every seed. Losses come from Gauss-fort head kills, Ullers and Enfields, with no repair far from the dropship bay (I20). |
| mc2_14 | 0 | bot | Slow stealth line. Seed 3 is still PLAYING at 4500 s with 2 enemies left, seed 2 is lost at 2857 s with 7 left, and seed 1 is lost at 461 s to the Gun Alpha Hunchback (I21). |
| mc2_18 | 0 | bot | The three recaptures are done in 2 seeds, but the lance is worn down by 968-1310 s (Sha Yu, Lao Hu, LRM turrets), and the city's bay is lost. Seed 2 stalled to 1800 s at 22 kills (I25). |
| mc2_22 | 0 | bot | The corner hold works (lance lives 622-877 s, 21-45 kills). Men Shen, Catapults and the Elite Guard finish it (I28). |
| mc2_23 | 0 | bot | The starport is cleared every seed, but the spared last target is usually a mech that dies early, so the waves meet no reception (I29). |
| mc2_24 | 1 | bot | Seed 1 won at 1241 s. Seeds 2-3 die in the base to Hunchbacks and Bushwackers at 469-779 s before the HQ (I30). |

There is no open suspected port bug. The four found during this work (I111, I112, I115-I117) are
fixed. mc2_12 is the one regression to explain: it is either balance or a bot change (I118).
