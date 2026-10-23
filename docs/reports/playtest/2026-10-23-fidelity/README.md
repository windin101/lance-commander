# Playtest sweep 2026-10-23 (fidelity): after the original-rules pass

Same harness and bot settings as `../2026-10-23` (24 missions x seeds 1-3, 1800 s cap, `--jobs 3`),
run after the fidelity fixes I88-I97 and F6 (uncommitted tree). `results.json` and `logs/` are this run.

Rules changed since `../2026-10-23`: vehicle weapon-node limit (Partisan/Legion 2 shots, O1), half heat
to-hit penalty (H9), unlimited ammo (O2), contacts = 225 m visual LOS + fitted sensors (I90), weapons need
LOS / LRMs a spotter, area-effect Long Tom and Swarm LRM (I91), brain moves walk (I92), engaged AI fires only
at its brain's target (F6), live map turrets with capturable controls (I94), repair bays (I95), artillery
piece, minelayer and mines (I96). The bot now also captures turret controls and bays near its route, uses
friendly bays, and drops a Long Tom against three or more threats.

| mission | 2026-10-23 | this sweep | note |
|---|---|---|---|
| mc2_01 | 3/3 | 3/3 | |
| mc2_02 | 3/3 | 1/3 | SRM pop-up turrets now fire |
| mc2_03 | 3/3 | 0/3 | 2 stalls (PLAYING 1800 s) after losses to AC turrets |
| mc2_04 | 3/3 | 0/3 | SRM turrets kill 2 of 3; lone survivor stalls |
| mc2_05 | 3/3 | 2/3 | |
| mc2_06 | 1/3 | 2/3 | |
| mc2_07 | 2/3 | 0/3 | pulse turrets |
| mc2_08 | 1/3 | 0/3 | |
| mc2_09 | 3/3 | 0/3 | 3 stalls before the HQ |
| mc2_10 | 2/3 | 0/3 | |
| mc2_11 | 1/3 | 0/3 | |
| mc2_12 | 0/3 | 0/3 | |
| mc2_13 | 0/3 | 0/3 | |
| mc2_14 | 0/3 | 0/3 | |
| mc2_15 | 0/3 | **3/3** | Legions limited to 2 shots (I88) |
| mc2_16 | 0/3 | 0/3 | |
| mc2_17 | 0/3 | 0/3 | |
| mc2_18 | 0/3 | 0/3 | |
| mc2_19 | 0/3 | 0/3 | |
| mc2_20 | 0/3 | 0/3 | 3 stalls |
| mc2_21 | 3/3 | 3/3 | |
| mc2_22 | 0/3 | 0/3 | 3 stalls; pulse turrets |
| mc2_23 | 0/3 | 0/3 | |
| mc2_24 | 0/3 | 0/3 | |
| **runs won** | 28/72 | 14/72 | |
| **missions 2/3+** | 9 | 5 | |

**Reading it.** Partisan and Legion are gone from the lance's killers; map turrets are now the top killers
(MediumAutoCannonTurret 28 losses, LargePulseCannonTurret 16, SRMTurret 15, LRMTurret 9 in lost runs). The
game is harder for this bot because the turrets the walkthroughs fight with (or around) now exist, and the
bot still walks into enemy forts. A player destroys generators/controls, jump-captures controls and lures
enemies into captured turrets (docs/research/original-missions.md). Bot follow-up: treat enemy turrets as
threats (avoid or kill their generator/control first), unstick fights against enemies it cannot see.
