# Combat rules (Phase 2)

These are the rules as implemented in `game/scripts/sim/`. Each rule cites the
original source (`reference/mc2-source/Source/`) it was derived from.

The code is a clean reimplementation, not a copy. Behaviour is **faithful**
unless it appears under "Deliberate changes", and each change sits behind a
flag in `SimRules`, so parity is one switch away.

Units: distances are metres (the original's `distanceFrom` already returns
metres). Angles are degrees. Facing 0 is north (+y) and increases clockwise.

## To-hit (`Mover::calcAttackChance`, mover.cpp:6197)

1. **Base:** pilot Gunnery. If the shooter is the player's, multiply by
   `PlayerSkills[difficulty]/100`; otherwise by `EnemySkills[difficulty]/100`
   (gamesys `DifficultySettings`). See change C1.
2. **Out of range:** −1 (no shot) when the distance is ≤ min − 12.07 m or
   > long + 12.07 m. The ranges come from gamesys `WeaponRanges`:
   - short 0–60
   - medium 30–120
   - long 60–180

   12.07 m is `MapCellDiagonal`, i.e. 128/3 world units × 1.4142 × 0.2 m.
3. **Disabled or non-mover target:** 100, returned before any other modifier
   or clamp.
4. **Target pilot's chassis specialty:**
   - light (< 40 t): −30
   - medium (40–59 t): −20
   - heavy (60–79 t): −10
   - assault (80–99 t): −10

   A 100-ton target gets no modifier; that's the original's bound and is kept.
5. **Shooter's weapon specialty:** +20 (`WeaponSpecialistModifier`), for the
   component-id groups listed in mover.cpp.
6. **Range specialty:** +15 when the distance falls in the band:
   - short ≤ 60
   - medium 31–120
   - long 61–180

   See change C2.
7. **Aimed shot** at a mech: multiply by the location modifier, then add +20
   for a SharpShooter. The modifiers are:
   - head ×0.08
   - arm ×0.15
   - leg ×0.20
   - torso ×1
8. **Heat:** subtract the heat table's `fire_mod` at the shooter's heat level.
   This is new (H3).
9. **Clamp:** 5–95.

The original has no attacker or target movement modifier: the `modifiers` and
`targetTime` arguments are never read. `TargetMoveModifierTable` is loaded
but unused here.

## Firing (`BattleMech::fireWeapon`, mech.cpp:7991)

- The chance is truncated to an integer. A hit is `RandomNumber(100) < chance`,
  with the roll in 0–99. The weapon then starts recycling:
  `ready_time = now + recycle`.
- **Hit:** spend one round from the weapon's ammo pool, if it uses ammo. The
  damage is the component's `damage`.
  - Missile salvoes deliver the whole CSV damage as one hit, because every
    weapon's ammo-per-shot is 1 (`initEXCEL`).
  - Streaks behave the same on a hit.
- **Miss:** spend ammo unless the weapon is a streak. Streaks that miss cost
  nothing.
- **Aimed hit:** goes to the aimed location. Otherwise use the hit-location
  roll below.
- **Ammo pools** are per ammo-type master id (`calcAmmoTotals`). A shot draws
  from the first non-empty bin (`reduceAmmo`).

## Hit location (`BattleMech::calcHitLocation`, mech.cpp:6609)

- **Section** comes from the attack source. Weapon fire, collisions and
  artillery hit the middle; death-from-above hits the top; mines hit the
  bottom.
- **Arc** comes from `relFacingTo(attacker)`. Negative means the attacker is
  counter-clockwise (left) of the target's facing.
  - front: −45 to 45 inclusive
  - left: −135 to −45, exclusive at both ends
  - right: 45 to 135, exclusive at both ends
  - rear: everything else
- **Roll:** d100 walked through `HitLocationTable[section][arc][11]`
  (gamesys). The 11 armour locations are head, CT, LT, RT, LA, RA, LL, RL,
  rear-CT, rear-LT, rear-RT.

## Damage (`BattleMech::handleWeaponHit`, mech.cpp:7379)

Ignored if the damage is ≤ 0, the location is −1, or the mech is destroyed.

1. **Fallen and disabled mech** (and therefore helpless): add the damage to a
   tally. When the tally exceeds `destructDamage`, the mech is destroyed.
   `destructDamage` defaults to 20; per-chassis values come later from the
   object FITs.
2. **Body location** = `MechArmorToBodyLocation[armour location]` (rear
   torsos map to their torso).
3. **Head hit** of 2 or more damage: the pilot takes 1 wound.
4. **Armour > 0** and not an ammo explosion:
   - **Damage > armour:** the excess goes on, and armour drops to 0 (holed).
     - Excess ≥ internal structure: injure by the internal amount, then
       *transfer* what's left.
     - Excess < internal structure: injure by the excess.
   - **Damage ≤ armour:** armour absorbs it all. An exact match empties the
     armour without holing it.
5. **No armour, or an ammo explosion:**
   - **Internal > 0:** if damage ≥ internal, injure by the internal amount;
     what's left vents to the rear armour (ammo explosion, since every MC2
     mech has CASE everywhere) or transfers. If damage < internal, injure by
     the damage.
   - **Internal = 0:** the damage vents (ammo explosion) or transfers.
6. **Venting:** left side → rear-LT, right side → rear-RT, centre or head →
   rear-CT. Venting only removes armour; any damage beyond it is lost.
7. **Transfer:** use `MechTransferHitTable` (gamesys
   `[1,-1,1,1,2,3,2,3]`): head → CT, side torso → CT, arm → its side torso,
   leg → its side torso. The transfer arrives as a **new hit on the
   destination's front armour**, through the full routine. Overflow past the
   head or CT is lost.

### Injury (`injureBodyLocation`, mech.cpp:7308)

- Internal structure is reduced, with a floor of 0.
- **Location survives:** at ≤ 50% internal it is PARTIAL damage; above that,
  NONE. Then roll for crits.
- **Location reaches 0:** it is destroyed.

### Crits (`calcCriticalHit`, mech.cpp:7023)

- **Count:** roll d100 against `CriticalHitTable = [58,83,97,100]`.
  - < 58: none
  - < 83: 1
  - < 97: 2
  - otherwise a torso (CT, LT or RT) takes 3, and a head or limb is
    **destroyed outright**
- **Each crit** rolls `RandomNumber(total occupied crit spaces)` and walks the
  slots, each weighted by its component's crit size, then hits that item.
  Already-hit slots can be hit again. No crits roll when the location has no
  occupied spaces.

### Component hits (`hitInventoryItem`, mech.cpp:6774)

Every component has 1 health, so one hit disables and destroys it. Effects:

- **Engine:** shutdown death; the mech is disabled.
- **Cockpit:** nothing but a damage effect (`damageHotSpot`). The pilot is not
  hurt. *(Corrected 2026-10-19: this spec first said the pilot dies.)*
- **Ammo bin:** nothing. Both `COMPONENT_FORM_AMMO` cases just `break`, and
  `Mover::ammoExplosion` (pilot +2 wounds, rounds × explosive damage up to 255)
  is never called anywhere in the shipped source. *(Corrected 2026-10-19: this
  spec first said the bin explodes; that made the campaign far deadlier, with
  heavy mechs lost at 20-90 % armour.)* Only our heat model (H*) can blow ammo.
- **Gyro:** piloting check.
- **Leg actuator:** piloting check when hit; when destroyed, a forced check at
  +100. See change C3.
- **Weapon:** disabled.

### Destroying a location (`destroyBodyLocation`, mech.cpp:6959)

- Internal and front armour drop to 0, and every unhit crit slot is hit.
- **Leg:** forced piloting check, so the mech falls.
- **Side torso:** its arm is destroyed too.
- **CT:** the mech is destroyed if this happens at the moment the CT is first
  damaged, or within 5 s of an engine crit; otherwise it shuts down
  (disabled). Both take it out of the fight. The slots are hit *before* this
  check, and the engine sits in the CT, so a CT kill almost always crits the
  engine and explodes. A plain shutdown happens only when the engine was
  already wrecked more than 5 s earlier.

### Pilot (`MechWarrior::injure`, warrior.cpp:1927)

Wounds accumulate. At 6 the pilot dies and the mech is disabled (no
ejection in the slice).

### Piloting check (`pilotingCheck`, mech.cpp)

- **Roll:** d100, with these modifiers:
  - collision: +20
  - leg internal at 0: +100
  - gyro destroyed: +100
  - each hip actuator destroyed: +10
  - forced check: +100
- **Fail** when the roll ≥ the Piloting skill; the mech falls. Only one
  failed check is pending at a time.

## Heat (new: the original's system was never finished)

The original's `updateHeat` (mech.cpp:3561) is compiled out (`#ifdef USEHEAT`).
`heatPerSec` and dissipation are never set, and `calcHeatSinks` says "This
needs to be properly implemented!".

Lance Commander turns heat on, built from the original's own data:

- **H1. Capacity** is the chassis CSV `Heat Index` (e.g. Atlas 43, Cougar 36).
  It is sized so a full alpha strike roughly fills it: the ratio of loadout
  heat to index is 1.00 for the Atlas, Mad Cat, Cougar and Vulture.
- **H2. Heat level** = floor(30 × heat / capacity), clamped to 0–30. It indexes
  `heat.csv` (31 rows):
  - `shutdown_pct`
  - `ammo_explosion_pct`
  - `move_mod`
  - `fire_mod`
  - `injuries`
- **H3. Firing** a weapon adds its CSV `heat` at once, on a hit or a miss.
- **H4. Movement:** each second, add `BodyStateHeat[state]` (gamesys
  `Mech:Heat`) scaled by capacity/30, so the gamesys values stay in "levels
  per second":
  - walking 0.15
  - running 0.3
  - jumping 0.75
- **H5. Dissipation:** `dissipation_rate` × capacity per second.
  - The rate is a tunable, default 0.3 (tuned in Phase 6), so a full bar clears in about 3.3 s.
  - Each working HeatSink component adds its `dissipation` per second.
  - The total is multiplied by gamesys `HeatSinkEfficiency`.
- **H6. Heat check** every `HeatCheckFrequency` (gamesys 1.0 s), while the
  mech is running:
  - level ≥ `HeatShutdown` (gamesys 25): shut down;
  - else roll d100 < `shutdown_pct`: shut down;
  - roll d100 < `ammo_explosion_pct`: a random intact ammo bin explodes (this
    is the original's own unfinished rule);
  - if life support is destroyed, the pilot takes `injuries` wounds.
- **H7. Restart** when shut down and the level falls to `restart_level`
  (default 15). This avoids the original's flicker at the threshold.
- **H8. Speed** is multiplied by `1 − move_mod/200`; at level 30 that's 10%
  speed. The original's column is unitless, so this scale is our choice.

All heat numbers live in `SimRules.heat`, so they can be tuned without code
changes. `SimRules.heat_enabled = false` gives the original no-heat
behaviour.

## Tuning notes

The baselines below come from `game/tools/duel_cli.gd`: 200 seeded runs,
gunnery and piloting 60, both mechs stationary, every ready weapon fired each
0.25 s. With no fire discipline, heat dominates:

| Duel | Heat | Wins | Mean length | Time shut down |
|---|---|---|---|---|
| Atlas v Mad Cat, 90 m | on | 65 / 132 (3 draws) | 108 s | 43% / 78% |
| Atlas v Mad Cat, 90 m | off | 14 / 186 | 47 s | 0 / 0 |
| Hunchback v Raven, 50 m | on | 200 / 0 | 23 s | 0% / 72% |
| Hunchback v Raven, 50 m | off | 189 / 11 | 27 s | 0 / 0 |
| Vulture v Cougar, 90 m | on | 69 / 122 (9 draws) | 97 s | 80% / 83% |

### Phase 6 retune, with fire discipline

Units now hold any weapon that would push them past heat level 20
(`SimWorld.fire_discipline_level`). The duels were rerun with
`game/tools/heat_tune.gd`, which uses the real SimWorld loop at 40 m: 90 runs
each (Hunchback v Raven 50), gunnery 60.

| Duel | Heat off | rate 0.12 | rate 0.2 | **rate 0.3** |
|---|---|---|---|---|
| Atlas v Mad Cat | 90/0, 35 s | 1/89, 99 s | 90/0, 46 s | **90/0, 43 s** |
| Bushwacker v Starslayer | 8/82, 38 s | 84/6, 65 s | 2/88, 40 s | **3/87, 39 s** |
| Vulture v Cougar | 90/0, 27 s | 84/6, 163 s | 90/0, 97 s | **90/0, 30 s** |
| Hunchback v Raven | 49/1, 26 s | 50/0, 30 s | 50/0, 30 s | **50/0, 28 s** |

**Chosen: 0.3.**
- Fights are within about 10% of heat-off, and the outcomes follow the same rankings.
- Hot loadouts still run at levels 16–19 and hold back weapons, so heat shapes the damage output.
- Disciplined units essentially never shut down (≤ 0.3% of ticks).
- At 0.12, heat flipped matchups and slowed some fights six-fold.

A player alpha-strike override, which ignores discipline, is the intended way to
trade overheating risk for burst damage (Phase 7 HUD).

## Deliberate changes

| ID | Original | Lance Commander | Flag |
|---|---|---|---|
| C1 | Both difficulty branches test "is player", so enemies never get `EnemySkills` | Enemies use `EnemySkills` | `fix_enemy_difficulty` |
| C2 | Range-specialist bands are multiplied by `worldUnitsPerMeter` (5.01), so short always applies and long never does | Bands in metres | `fix_range_specialists` |
| C3 | `(loc == LLEG) \|\| (RLEG)` is always true, so any actuator hit forces a piloting check | Leg actuators only | `fix_actuator_check` |
| H* | Heat compiled out | Heat on (above) | `heat_enabled` |
| C4 | The player brain's fire-at-will picks targets by action rating; our auto-fire takes the nearest enemy in reach, which kills capture objectives (mc2_03's mobile HQ) | Auto-fire skips unarmed capturable units; an explicit attack order still engages them | none (SimWorld._pick_target) |
| C5 | An attack order on a target with no path to its cell stands still | The attacker walks to a reachable cell within weapon range (e.g. across deep water) | none (SimWorld._firing_position_path) |
