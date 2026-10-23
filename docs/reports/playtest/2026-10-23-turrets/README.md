# Playtest sweep 2026-10-23 (turrets): after the early-mission diagnosis and I99

Same harness as `../2026-10-23` and `../2026-10-23-fidelity` (24 missions x seeds 1-3, 1800 s, `--jobs 3`).

## Changes since the fidelity sweep
- **Port bugs fixed:**
  - A unit placed on a blocked cell could never move: grid A* refuses a solid start. mc2_04's
    facility Anubis sits inside the weapons facility's footprint. With LOS on, nobody could see or
    reach it, and every run stalled to 1800 s. `SimMap.find_path` now walks out to the nearest
    open cell first.
  - An attacker in reach without a line of fire now walks to a spot that has one
    (`SimWorld._sight_position_path`).
  - Turrets now report ABL `TURRET_CLASS` (30).
- **Harness (bot):** an immobile artillery piece no longer keeps a lost mission open. The
  1800 s "stalls" in mc2_03 and 09 were a lance already dead, with a Long Tom left standing.
- **Bot (I99):**
  - spots enemy turret forts within 300 m;
  - captures their control, or destroys the control or generator, or shoots an unlinked turret;
  - counts covering turrets' firepower when deciding to fall back;
  - drops a Long Tom against forts from outside their guns' reach and sets idle guns on turrets;
  - stall watch: a fight with no damage dealt for 150 s is dropped for 2 min;
  - repair trucks: the lance uses only trucks it can reach, drops a truck on the hurt mech's side
    of any wall, and walks the mech to a truck that can't reach it.

## Wins (of 3)

| mission | 10-23 | fidelity | turrets |
|---|---|---|---|
| mc2_01 | 3 | 3 | 3 |
| mc2_02 | 3 | 1 | 3 |
| mc2_03 | 3 | 0 | 1 |
| mc2_04 | 3 | 0 | 2 |
| mc2_05 | 3 | 2 | 3 |
| mc2_06 | 1 | 2 | 2 |
| mc2_07 | 2 | 0 | 0 |
| mc2_08 | 1 | 0 | 0 |
| mc2_09 | 3 | 0 | 0 |
| mc2_10 | 2 | 0 | 3 |
| mc2_11 | 1 | 0 | 0 |
| mc2_12-14 | 0 | 0 | 0 |
| mc2_15 | 0 | 3 | 3 |
| mc2_16-19 | 0 | 0 | 0 |
| mc2_20 | 0 | 0 | 1 |
| mc2_21 | 3 | 3 | 3 |
| mc2_22-24 | 0 | 0 | 0 |
| **runs won** | 28/72 | 14/72 | **24/72** |
| **missions 2/3+** | 9 | 5 | **8** |
| **runs at the 1800 s cap** | 1 | 17 | 1 |

The lance's top killers in lost runs are now MediumAutoCannonTurret (23), LargePulseCannonTurret (19), Sha Yu,
Highlander, Men Shen. In mc2_09 the Swarm LRM carriers (area-effect blast, hit or miss) are the top killer.
