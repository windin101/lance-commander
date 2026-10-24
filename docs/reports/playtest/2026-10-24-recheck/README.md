# Playtest sweep 2026-10-24 (re-check): bot issues I14-I30 after Phase 8

This sweep re-checks the bot issues I14-I30 on the 16 missions they name. It uses the same harness as
`../2026-10-23-turrets` (seeds 1-3, 1800 s cap) but runs `--jobs 2`, at commit 30e6aa1 (clean tree).
It is not a full 24-mission sweep: mc2_02-05, 08, 11, 12 and 21 were not run.

## Changes since the turrets sweep
- **Sim fidelity (I88-I97, Phase 8):** turret and torso slew (I93), aimed shots, power down/up and
  eject, explosion damage in 5-point chunks, scout copters flying, and the formation fix (I102).
- **Game fixes:**
  - **I112:** a twist-limited torso turned the short way round the back and stuck at its stop. The
    mech then never fired. This touched every fight with slew on.
  - **I111:** movers that the mission script removes no longer block "destroy all".
- **Bot (step 6):**
  - mc2_17 holds the Steiner base (`HOLD_PLANS`).
  - mc2_14 plays stealth (`STEALTH_PLANS`).
  - Mechs jump in to capture turret controls under fire.
  - Enemies under an enemy fort's guns rank lower when the lance picks targets.

## Wins (of 3)

| mission | turrets (10-23) | re-check (10-24) | issue |
|---|---|---|---|
| mc2_01 | 3 | 3 | I14 |
| mc2_06 | 2 | **3** | I15 |
| mc2_07 | 0 | **2** | I16, I17 |
| mc2_09 | 0 | **1** | I18 |
| mc2_10 | 3 | 3 | I19 |
| mc2_13 | 0 | 0 | I20 |
| mc2_14 | 0 | 0 (2 alive at 1800 s) | I21 |
| mc2_15 | 3 | 3 | I22 |
| mc2_16 | 0 | **2** | I23 |
| mc2_17 | 0 | **3** | I24 |
| mc2_18 | 0 | 0 | I25 |
| mc2_19 | 0 | **2** | I26 |
| mc2_20 | 1 | **2** | I27 |
| mc2_22 | 0 | 0 | I28 |
| mc2_23 | 0 | 0 | I29 |
| mc2_24 | 0 | 0 | I30 |
| **total** | **12/48** | **24/48** | |

## Per issue

### Closed: no longer reproduce

- **I14, mc2_01:** 3/3, won in 241-247 s. The Starslayer fight cost 0-2 light mechs.
- **I15, mc2_06:** 3/3. The bot captures the road-checkpoint turret control. The Sensor Control is
  no longer destroyed by our own air strike, but it is still left uncaptured (secondary a).
- **I16 and I17, mc2_07:** 2/3, with the HQ captured by t=198. The seed-3 loss is the last two mechs
  falling back under a guntower after the Zeus was lost at 108 s. No mech was sent alone across the map.
- **I18, mc2_09:**
  - The campaign force no longer has a Werewolf, and the formation fix (I102) keeps the lance
    together. The lone fast mech never appears.
  - mc2_09 still wins only 1/3. Swarm LRM carriers and LRM turrets do the damage, which is the fort
    problem tracked in I99.
- **I19, mc2_10:** 3/3.
- **I22, mc2_15:** 3/3, 0-2 mechs lost.
- **I23, mc2_16:**
  - 2/3. The winning seeds complete all 6 visible objectives, including the turret and HQ secondaries.
  - Seed 1 lost two Lao Hus to LRM carriers at 342-360 s.
- **I24, mc2_17:** 3/3, won in 1197-1387 s with one mech lost. The bot plays Lee's line: run to the
  Steiner base, capture both turret controls and both bays, and hold.
- **I26, mc2_19:** 2/3.
  - The two sim gaps the issue also named are still there, and now have their own issue, I114:
    - Spotter strikes are missing from the damage table.
    - The spotter has no line-of-sight check.
- **I27, mc2_20:** 2/3, with 6 of 7 objectives done in the wins.

### Still open

- **I20, mc2_13:**
  - 0/3. No objective is done in two seeds.
  - The top attackers are the MediumAutoCannon and Gauss turrets, then the Storm.
  - The lance has no support (0 RP), and its Sha Yu dies first at 117-131 s every seed.
- **I21, mc2_14:**
  - 0/3. Two seeds survive to 1800 s, holding the airport, Gun Alpha and, in one, Omega.
  - Seed 3 lost the Lao Hu to a Werewolf at 350 s.
  - The rest of the mission is long stretches of avoiding patrols.
- **I25, mc2_18:**
  - 0/3, but the lance now kills 37-53 enemies, against a maximum of 22 before. The 25-kill trigger
    fires.
  - It still never retakes the HQ, the power generator or the sensor control. Sha Yu, the LRM
    turrets and the Lao Hu wear it down by 971-1094 s.
- **I28, mc2_22:**
  - 0/3. The whole lance dies by 169-230 s.
  - The Large Pulse Cannon and LRM turret lines around the start area, plus the guards inside it,
    engage as soon as the lance moves for the turret control.
  - Holding the corner (KC's tactic) makes no contact in 1800 s, so the bot needs a better opening
    move. See I99.
- **I29, mc2_23:**
  - 0/3. Secondary b (the town patrols) is done in every seed, and the starport is cleared in seed 3.
  - LRM carriers, MediumAutoCannon turrets, an Atlas and Zeus finish the lance at 332-897 s.
- **I30, mc2_24:**
  - 0/3. The fuel-truck hidden objective now completes in two seeds, which the issue said never
    happened.
  - The lance still dies at the front gate by 222-467 s to Highlanders, Bushwackers and the LRM and
    Long Tom turrets.
  - It loses 3 mechs in the first 100 s every seed.

### Harness

- **I113:** the step-6 mc2_17 sweep once segfaulted inside `AblRuntime._slot` (signal 11, log in
  `crash-I113-mc2_17_s3.log`). The sim is deterministic, and the same seed and code then won in
  1231 s. It did not recur in this sweep's 48 runs. Unexplained.
