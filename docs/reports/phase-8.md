# Phase 8 report: playtest (swarm dry run)

**Run:** 2026-10-19, while phase 7 batch 2 generated on GPU0. Sweep: `tools/playtest_sweep.py` (autoplay bot, 24 missions x 3 seeds, 72 runs, 4 at a time, 560 s). Diagnosis: `remake-kit/workflows/phase-8-playtest.js` (`wf_0330e31a-d44`, 26 agents, 1.70M tokens, 12 min). Results: `docs/reports/playtest/2026-10-19/results.json` + raw logs.

## Sweep

| | |
|---|---|
| runs won | 21 / 72 |
| missions won on every seed | 5 (02 03 04 05 21) |
| won on some seeds | 4 (01 2/3, 10 2/3, 11 1/3, 16 1/3) |
| never won | 15 |
| ABL errors / missing natives | 0 in all 72 runs |

Regressions against the earlier record ("autoplay wins 01 02 04 05 06 10 21"): **mc2_06 now loses on all seeds** (the game bug I10 below), mc2_01 loses seed 2 (bot, I14). mc2_03 now wins on all seeds and was not on the old list.

## Diagnosis: 23 findings for 19 missions

| cause | count | note |
|---|---|---|
| game | 5 | every claim survived an independent refutation attempt |
| balance | 5 | mc2_07, 13, 17, 20, 23: the FIT lance with no support against forces the original campaign expects you to meet with bought 'Mechs and support |
| bot | 13 | nearest-first targeting, no formation, no retreat/regroup, no repair before the last fight, ignores capture objectives, own air strikes |

**Game bugs** (owner sim):
- **I10 P1**: units spawned on off-map edge cells never move (find_path from an unwalkable start cell) — mc2_06's three Liao waves never march on the base, mc2_12's four convoys never leave the spawn. A human holding the base would wait forever.
- **I12 P1**: AI units auto-fire at the nearest enemy regardless of brain — mc2_17's inert cam-dummy Werewolves start the battle 75 s before the scripted betrayal.
- **I11 P2**: FIT parts with Damage >= 1.0 spawn live instead of shut down/disabled — mc2_08 (the link-up Atlas), mc2_11 (five salvage-yard 'Mechs fight the lance), possibly mc2_09.
- **I31 P2** (from the critic): the loss check is inconsistent when only support units survive (mc2_15 LOST on s1/s3, endless PLAYING on s2; similar stalls on 10, 11, 22).

## What the critic changed

- I13 was filed as a bot issue; the critic showed the same end state gives different results by seed, so it was reclassified as I31 (game/bot, P2).
- Two early capture-target losses with no named attacker (mc2_06, mc2_22) were inferred to be the bot's own air strike without proof → I32, with the probe that settles it.
- It flagged seed variance the findings had written up as deterministic (mc2_10, 11, 16) and a claimed per-seed pilot-count nondeterminism. The conductor checked the last one: start counts are identical per seed, the end-of-run count includes scripted spawns → I33 P3, not a bug.
- It noted nobody has shown the sweep would *catch* an ABL error (no negative test). Open.

## Next

1. Fix I10 and I12 (P1, sim), then I11 and I31 — re-run the sweep after each: they plausibly flip mc2_06, 08, 11, 12, 17.
2. Bot work (I14–I30, P3): focus-fire the biggest threat, move as a formation, repair before the final objective, prefer capture objectives, log support calls. These raise the bot's win rate but don't change the game.
3. Balance (5 missions) can only be judged after the campaign layer (purchasing, support) is used by the bot; the original expects it.
4. Add a negative test that a broken ABL script shows up in `abl_errors`.
