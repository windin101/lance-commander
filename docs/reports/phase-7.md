# Phase 7 report: HD art (swarm dry run)

**Started:** 2026-10-19. **Mode:** supervised, one phase at a time; the conductor role was played by the main session for this first run.

## Plan

State at start (from `swarm show`): HD mechs 13/30, vehicles 3/28, buildings 7/34 (needed counts derived from the 24 mission files). First gate run: tests pass (125 cases), import size pass (0.33 GB), **provenance fail** (3 HD assets without a row, 7 without fit data) → issue I1.

Decisions: D1 (which batch first) superseded once it was found that another session's `hd_batch.py` chain is generating the remaining mech concepts on GPU0. **D2 (Lee): review + record the chain's mech outputs as they land, no GPU0 use.**

Work list for this run (`workflows/phase-7-hd-review.js`, 3 groups, 13 installed mechs):

1. Backfill `original/hd/<asset>/provenance.json` with a step-4-only re-fit (`hd_rig` is seeded, so the fit is reproducible; nothing is reinstalled).
2. Review sheet per group (`hd_review.py hd --render`, under the godot lock), local-llm orientation pre-screen on original vs HD front views, then the sheet judged by eye.
3. Provenance rows for approvals; a P2 issue with a repro for everything else.
4. Critic: rows, issues, sheets, and the provenance gate's own line.

Then `swarm phase gate 7`. The gate cannot pass while the other chain keeps installing mechs without rows, so the expected outcome of this run is a smaller failing set and a working loop, not a passed gate.

## Result

### Review batch 1 (workflow `wf_2391523b-26b`, 2026-10-19)

10 agents, 534k tokens, 7 min wall-clock; plus the conductor's own checks.

| result | mechs |
|---|---|
| approved (7) | catapult, hollander, menshen, raven, zeus, flea, werewolf (after `--turn`) |
| redo (6) | bushwacker I8, starslayer I3, highlander I6, hunchback I7 (concept drift); urbanmech I4, jaegermech I2 (mesh debris) |
| P3 | werewolf I9 (paint-mask band on the shins) |

Gate after the batch: **PASSED** (tests 125/125, all 23 HD meshes with provenance rows and fit data, imported 0.33 GB). I1 closed.

What the swarm found that the by-hand process missed: **three milestone-1 mechs fail review** (bushwacker, starslayer, urbanmech) and werewolf was installed backwards. The critic was the most valuable stage: it caught a blind approval (bushwacker judged with the original tile missing), a wrong concept seed carried into provenance.json (werewolf 7 → 21), and rows not updated for redo assets. The reviewers' local-llm orientation pre-screen disagreed with the eye on 4 of 13 and was right on 1 (werewolf); treat it as a hint, never a verdict.

Pipeline fixes made during the batch: `hd_mech.py` writes `provenance.json` (concept seed, mesh seed, turn, fit after ICP — the first version took the pre-ICP chamfer, fixed); the provenance gate accepts `` `asset_id` `` in a row name.

### Not done / next

- The gate passing does **not** finish phase 7: approved is 7/30 mechs, 0/28 vehicles, 0/34 buildings. Phase 7's done-gate needs a coverage check (approved == needed) and "no open P2 owned by game-art"; to add.
- The 6 redos need GPU0, which another session's `hd_batch.py` chain still holds; queued until its logs say ALLDONE (C9).
- Mesh seed 1234 is inferred for every pre-change mech, not logged.

