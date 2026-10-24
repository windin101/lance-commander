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
8. **Heat:** subtract the heat table's `fire_mod` at the shooter's heat level,
   times `heat_fire_mod_factor` (0.5). This is new (H3, softened by H9).
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

## Line of sight and contacts (I90, I91; 2026-10-23)

**Sight** (`GameObject::lineOfSight`, gameobj.cpp:1846-1990; `Team::lineOfSight`,
team.cpp:1071-1260; `SimWorld.line_of_sight`, `SimMap.line_of_sight`):
- **Visual range:** 225 m (`VisualRangeTable` is 9 at every altitude, × 25 m), +20% for a
  Scout pilot, × the type's `LOSFactor` (the artillery piece 1.2).
- **Sight points:** a mover sights from its lowest weapon node's height above the ground
  (mover.cpp:3442-3498), a turret from its first weapon node (turret.cpp:1235), a building
  from half its height. The heights are the shapes' bind-pose node heights
  (`tools/convert/los_heights.py` → `data/los_heights.json`); pop-up turrets, whose guns sit
  below ground in the bind pose, use the 15 wu (3 m) fallback.
- **The walk:** from the centre of the shooter's cell to the centre of the target's cell, in
  steps of 1/1.5 cell. The sight line is compared with the terrain plus each cell's local
  (object) height, 4 m per step of the map's height bits. A step under a non-forest top blocks
  at once. A step under a forest cell's top counts a tree, and `MaxTreeLOSBlock` (6) steps
  block, which is about 4 forest cells. The walk ends early, visible, once it is within the
  target's extent plus half a cell. Movers have no extent here (their appearance radius is not
  converted). For a building the original passes its appearance radius; the port uses the
  building's footprint instead (the raised cells joined to its own, out to 40 m,
  `SimWorld.sight_radius`), or the walk would stop on the building's own roof.
- **Cost:** each viewer/target pair is cached for 0.5 s (`SIGHT_PERIOD`); the original
  recomputes every frame.

**Contacts** (`SensorSystem::calcContactStatus`, Contact.cpp:257-350; `SimWorld.is_contact`).
A team's contact is a mover that is not disabled and that one of its working sensors finds:
- **Visual:** line of sight within visual range from a team mover. The viewer needs a working
  sensor component; vehicles carry Vehicle Sensors (range 0), so they are visual only.
- **Sensor:** within a team mover's fitted sensor range (compbas.csv: Standard 1 m, Extended
  400, Advanced 550, Cyclops 800), or a team sensor tower's (`SensorRange`, e.g. 550 m). A
  tower's sensor fails when its control building is destroyed (bldng.cpp:878-885), and towers
  take their control's team, so capturing a sensor control gives its towers.
- A target that is **shut down** or carries a working **ECM** suite has no sensor signature:
  only visual contact finds it.
- Sensor probes (support-powers.md 3.2) add sensor contacts.
- Not modelled: contact quality (sensor 1-4 vs visual), ECM fields shrinking enemy sensors
  (`ecmEffect`), lookout towers.
- `SimRules.original_contacts = false` restores the old placeholder (any team mover within
  500 m).

**Fire** (`calcWeaponsStatus`, warrior.cpp:3396-3414): a weapon fires only with line of sight
to the target. Indirect-fire weapons (gamesys `IndirectFireWeaponComponentIndex`: LRM5, Swarm
LRM5, LRM, Long Tom) may also fire when any team mover that is not disabled or shut down sees
the target (`Team::teamLineOfSight`, team.cpp:762-810). `SimRules.line_of_sight = false`
turns it off. A pursuing attacker in range but without a line of fire keeps closing
(`SimWorld._can_fire_on`); the original's attack tactic moves on a NOT_LOCKED weapon status.
A target that changes sides (a captured turret or building) is dropped. An attacker already
in reach but without a line of fire walks to the nearest reachable spot in reach that has one
(`SimWorld._sight_position_path`), else closes on the target.

**Units placed on blocked cells** (mc2_04's facility Anubis sits inside the weapons facility's
impassable footprint) walk out to the nearest open cell first (`SimMap.find_path`). Grid A*
refuses a solid start, which froze such units and, with line of sight on, left attackers
unable to see or reach them (fixed 2026-10-23).

**Area-effect weapons** (weaponbolt.cpp:762-794; gamesys `AreaEffectWeaponComponentIndex`):
the Long Tom and the Swarm LRM do their damage by an explosion at the target, hit or miss, with
their bolt's `AreaEffectDamage` / `AreaEffectRadius` (Long Tom 15 in 187 wu = 37 m; Swarm LRM 3
in 120 wu = 24 m). A miss explodes 25 wu (5 m) off the target (gvehicl.cpp:4883-4892). Every
mover in the radius takes the damage at an artillery-style hit location; buildings within the
radius plus their extent take it whole; turrets only within their little extent
(carnage.cpp:343-436). Damage is applied as one chunk. Flag `area_effect_weapons`.

## Group moves and attack positions (2026-10-24)

**Group move** (`MoverGroup::calcMoveGoals`, group.cpp:401-526; called from
missiongui.cpp:2473-2496): each selected unit gets its own goal cell. A uniform-cost flood over
the passable cells of a 61 x 61 window, outward from the clicked cell; a cell is taken if no
taken goal has marked it as a neighbour, and each taken goal marks its 8 neighbours. The first
goal is the click, the next ones about two cells (17 m) out. **Quirk kept:** the neighbour
marking uses `nCol = curRow + dc` (group.cpp:483), so only goals on the window's diagonal mark
the right cells and later goals can be adjacent. `SimWorld.group_move_goals`; CommandInput
hands the goals out in selection order.

**Attack position** (`Mover::calcMoveGoal`, mover.cpp:4364-4900, through
`MechWarrior::calcMovePath`, warrior.cpp:2735-2860). A pursuing attacker walks to a goal cell
and fires from it (and on the way), rather than stopping at the first point in reach. On a
61 x 61 cell map round the target, cells score:
- +500 on the ring at the pilot's fire range: FIRERANGE_OPTIMAL (the player's default,
  mover.cpp:2219), the optimal range of `calcOptimalRange` (mover.cpp:5826-5884): the gamesys
  `OptimalRangePoints` point (20/45/100/100/160 m) covered by the most damage per second, ties by
  `OptimalRangeTieTable`; 32 bearings (`initOptimalCells(32)`);
- −500 beyond the longest weapon's reach and inside the shortest weapon's minimum;
- +100 in the 3 x 3 round the target for a non-player order;
- −1 per cell (Manhattan) from the attacker, −100 on a group mate's goal (mover.cpp:4612-4630);
- −10000 where it can't stand, and on its own cell when it must move somewhere else.

The 60 best cells are tried in order and the first with a line of sight to the target wins
(mover.cpp:4805-4830). A new goal is picked when the target has moved two cells, or on arrival
without a line of fire, at most every 2 s. So a lance ordered onto one target fans out side by
side on the fire ring, about a cell apart, instead of queueing in one file. Not ported:
`calcBestGoalFromTarget` (when no candidate sees the target, the best-scoring cell is used),
area-connectivity weights (the path search decides), path locks (units may overlap in passing).
Friendly units never block a line of sight, here or in the original (Team::lineOfSight reads
terrain and cell heights only). Flag `attack_goals`.

## Torso and turret slew, vehicle acceleration (I93, 2026-10-24)

- **Twist:** a mech's torso and a vehicle's turret turn toward the current target (or the order
  target) at their yaw rate when it is outside the fire arc, and back to the front with no target
  (`BattleMech::updateTorso`, mech.cpp:4580-4623; `GroundVehicle::updateTurret`,
  gvehicl.cpp:2130-2156), never past the twist limit (`MaxTorsoYaw` / `MaxTurretYaw`,
  gvehicl.cpp:2937-2961). Rates: chassis `TorsoYawRate` (360 deg/s on every mech, 0 on the
  copters, which must turn their body), vehicle `MaxTurretYawRate` (90-180, the Partisan 120,
  the artillery piece 720).
  A twist-limited torso turns the straight way through the front, never round the back, because the
  original doesn't wrap torsoRelFacing (mech.cpp:4590-4600). Our first version wrapped it, which
  left torsos stuck against their stop (I112, 2026-10-24).
- **Lock:** a weapon fires only when the target is within FireArc/2 (12.5 deg) of the torso or
  turret (`weaponLocked`, gvehicl.cpp:4283, mech.cpp:7342), not of the whole twist range.
- **Acceleration:** a vehicle's speed rises by `MaxAccel` per second (gvehicl.cpp:934,
  2977-2993; `max_accel` in `data/vehicles/*.json`: most 5, Harasser and Monsoon 15, Legion 0.5,
  mobile orbital gun 0.1). Stopping at a goal stays immediate. Mechs' gait changes are not
  modelled.
- Flag `slew`. Arena (40 fights, 4 mechs at 150 m): 4 Partisans' damage 17 -> 22 per minute,
  fights 26 -> 22 s; 6 Harassers 84 -> 25 per minute (they turn their hulls), fights 9 -> 13 s.

## Building explosions (I115, 2026-10-24)

- A destroyed building blows up with its type's `ExplosionDamage` and `ExplosionRadius`. The blast
  has no owner: `createExplosion(BUILDING_EXPLOSION_ID, NULL, hitNode, explDamage, explRadius)`
  (bldng.cpp:205-211, 1256-1257, 1476-1488).
  - LargeFuelTank, SmallFuelTank and AmmoDump: 30 damage, 300 wu (60 m).
  - FuelPipe: 20 damage, 225 wu.
- Movers take the blast in 5-point chunks. A nearby tank takes it whole and can chain.
- A building placed destroyed (FIT damage & 0x0f) is set to its damage level without a blast
  (objmgr.cpp:1171-1173).

## Player controls from the original (2026-10-24)

The command table is missiongui.cpp:195-310; the palette's buttons are ControlGui::Commands
(ControlGui.h:179-201). Added:
- **Force fire, F** (`forceShot`, missiongui.cpp:3208-3240): the next right-click attacks
  whatever is under the cursor, a friend or a building included (`force_target`), or, on open
  ground, the point (TACTICAL_ORDER_ATTACK_POINT). From the current position when C is armed.
- **Attack point** (`SimWorld.order_attack_point`): fire every weapon in reach at the point (its
  line of sight, or a team mate's for indirect fire). Area-effect shells blast there; a shot into
  a mined cell sets the mine off (gvehicl.cpp:4821-4828). One volley ends the order
  (gvehicl.cpp:4838-4842) unless suppression is on (step 5).
- **Range keys S / M / L** and buttons (attackShort/Medium/Long, missiongui.cpp:1896-1931; the
  SHORT/MED/LONG_RANGE buttons): the next attack stands at the ordered fire range of
  `getOrderedFireRange` (mover.cpp:5888-5918): half the width of the weapon range band, which
  with gamesys WeaponRanges is 30, 45 and 60 m (the original's own arithmetic, kept). With an
  explicit range the attack goal drops its "beyond maximum range" penalty (mover.cpp:4473).
  Held keys apply while down; the buttons are a radio group; neither set means
  FIRERANGE_OPTIMAL.
- **Waypoints, Ctrl** (WAYPOINT_KEY = left Ctrl, missiongui.cpp:842; addQueuedTacOrder
  warrior.cpp:1555-1590; executeTacOrderQueue 1698-1708, 4890-4906): orders given with Ctrl held
  are queued (up to 16) and shown as markers; releasing Ctrl starts them, each when the unit is
  idle. A direct order clears the queue. Looping patrols are not ported.
- **Death from above** (BattleMechType::handleCollision, mech.cpp:819-925): a mech landing
  within a cell of an enemy mover hits it for jumper tonnage / 10 + 0.5 in its top section and
  takes the same in its legs. The original refuses a jump order clicked on a unit
  (`doJump`, missiongui.cpp:1961-2000), so the player jumps onto the ground beside or under the
  enemy. AI DFA through TACORDER_PARAM_ATTACK_DFA (warrior.cpp:5582) is not ported. Flag `dfa`.
- **Lay mines** is a palette button again (LAYMINES), so M is the medium-range key as in the
  original.
- **Aimed shots, Numpad 2 / 5 / 8 held + right-click** an enemy ground 'Mech (aimLeg / aimArm /
  aimHead, missiongui.cpp:217-219, 2109-2265): an attack order with `aimLocation` (the left leg or
  arm unless it is gone, then the right; the head unless destroyed; refused otherwise). Its
  weapons (not the area-effect ones) roll the aimed to-hit (head x0.08, arm x0.15, leg x0.20,
  +20 SharpShooter) and land on that location (warrior.cpp:3418-3421, 3500-3503).
- **Power down / up, PgDn / PgUp** (missiongui.cpp:2273-2289): an ordered shutdown of the
  selection (heat doesn't restart it) and back up.
- **Eject, End held + right-click** your own 'Mech (missiongui.cpp:2303-2318, doEject 5384-5394):
  the pilot ejects and the 'Mech is disabled; refused while the player is invulnerable.
- Kept ours: A is alpha strike, not the original's energy-weapons-only (Lee, 2026-10-24).

## Who an engaged AI shoots (F6, I12)

`combatDecisionTree` (warrior.cpp:3472-3540) fires only at the pilot's last target, the one its
brain (or the player) last attacked, and drops it beyond the pilot's `attackRadius` (gamesys
`DefaultAttackRadius`, 275 m) unless a combat order is running. A unit with a brain therefore
has no fire-at-will fallback. Units without a brain (support deliveries) still fire at the
nearest armed enemy in reach. Flag `brain_target_only`.

## Brain move speed (I92)

A brain's move order runs only when its script asks (`corePatrol` adds `TACORDER_PARAM_RUN`
when `CoreRun` is set, corebrain.abx:235-237); it sets the pilot's `moveRun`
(warrior.cpp:5314, 5974). An attack order carries no speed (`coreAttack` ignores RUN,
warrior.cpp:5574), so the unit approaches at its last move's pace. Units walk by default.
Flag `brain_walk`.

## Turrets (I94; turret.cpp)

Map turrets (object class 21) are `SimTurret` structures:
- **Data** from the type FIT's `[TurretData]` (TurretType::init, turret.cpp:129-235): up to
  four weapons, `PilotSkill`, `AttackRadius` (world units; it replaces the extent radius,
  turret.cpp:2142), `MaxTurretYawRate`, `DmgLevel`, `LittleExtent`.
- **Target:** the closest enemy mech or vehicle that is not disabled, inside the attack radius
  (TurretType::handleCollision, turret.cpp:238-316). No contact is needed. The target is
  dropped when it leaves the radius or is disabled. The port looks for a new target every
  0.5 s rather than every frame (cost: up to 78 turrets per map).
- **Aim:** the gun turns at the yaw rate and is ready within ±10° (turret.cpp:684-708,
  960-970). The pop-up gesture must open first: one second for every type (its frames are not
  converted).
- **Fire** (Turret::fireWeapon, turret.cpp:1352-1600): line of sight from the turret, or a team
  mate's for an indirect-fire weapon; otherwise no shot and no recycle. To-hit is the type's
  pilot skill, +50 against a target that stands still, minus the target pilot's chassis
  specialty (floor 5). No difficulty scaling, no range tolerance and no upper clamp. A hit does
  the weapon's damage. Area-effect weapons blast as above.
- **Damage:** shots at a turret always hit (a non-mover); it is destroyed at `DmgLevel`.
- **Control building:** a turret's placement names its parent cell (objmgr.cpp:970-991). The
  parent becomes a capturable control building, whatever its type says. The turret takes the
  control's team while the control stands (turret.cpp:636-646), so capturing the control turns
  its turrets. When the control is destroyed, disabled or asleep, the turret powers down for
  good (turret.cpp:617-633).
- Teams: placements of team 2 (allies) join team 0 and higher teams team 1 (turret.cpp:366-381,
  bldng.cpp:930-937); buildings follow the same rule.

## Mines (I96; mech.cpp:3731-3778, gvehicl.cpp:1355-1420)

A mech or vehicle **over 35 t** entering a cell with a laid mine sets it off: 12 damage
(gamesys `[Mine] BaseDamage`), for a mech in the bottom section from a random side. The mine is
spent. Jumping mechs, minelayers and mine sweepers don't set mines off; there is no team check.
The maps' own mines (mc2_07, 11, 15, 22) come from the cell mine bits. A blast in a mined cell
sets the mine off (weaponbolt.cpp:826). *(This corrects support-powers.md 3.5, which found no
mech trigger: `BattleMech::mineCheck` has one.)*

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
- **H9. Softened to-hit penalty** (I89, Lee's call on 2026-10-23). Heat stays on
  for every mech on both sides, but only half of `fire_mod` comes off the
  to-hit: `SimRules.heat_fire_mod_factor = 0.5` (8.5 at level 8, 22.5 at 16,
  28.5 at 20). Why: vehicles have no heat, so the full penalty taxed the
  player's all-mech lance hardest. The 2026-10-23 fidelity check measured the
  lance at 62-78% hits with the full penalty and 75-87% with heat off, and
  mc2_19 went from 0/3 to 2/3 wins with heat off
  (`docs/reports/fidelity/2026-10-23-combat.md` F2). The other options were to
  tax vehicles too, or to turn heat off. 1.0 restores the full penalty and 0.0
  removes it.

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
| C4 | The player brain's fire-at-will picks targets by action rating and skips a zero rating; our auto-fire takes the nearest enemy in reach, which killed mc2_03's mobile HQ directly and through exploding fuel trucks in its convoy | The player's auto-fire skips unarmed units (trucks, transports, mobile HQs); an explicit attack order still engages them. AI units take an unarmed target when nothing armed is in reach (their brains scan any enemy mover), so lone support vehicles cannot stall a mission (I31) | none (SimWorld._pick_target) |
| C5 | An attack order on a target with no path to its cell stands still | The attacker walks to a reachable cell within weapon range (e.g. across deep water) | none (SimWorld._firing_position_path) |

## Kept original rules

These are the original's behaviour, including its bugs, copied on purpose. Each
sits behind a `SimRules` flag that is on by default, so the remake's "fixed"
version is one switch away.

| ID | Original | Flag (default on) |
|---|---|---|
| O1 | **Vehicle weapon nodes** (I88, F1; Lee chose to copy the original on 2026-10-23). `GroundVehicle::fireWeapon` asks the appearance for the least-used weapon node (`GVAppearance::getWeaponNode`, Gvactor.cpp:578-660; ties go to the first). Nodes are numbered after the 2 smoke nodes, so Weapon_01-04 are 2-5. In single player it refuses the shot when the node is above 3 or still recycling (0.25 s, `BASE_NODE_RECYCLE_TIME`), with no recycle or ammo spent (gvehicl.cpp:4601-4618). Nodes the shape lacks are dropped when the unit is first updated (Gvactor.cpp:466-474, mover.cpp:3454-3466). Effects: a 1- or 2-node vehicle fires at most 1 or 2 weapons per 0.25 s. A 3- or 4-node shape gets stuck on Weapon_03 for good once Weapon_01 and 02 have fired once each, so the Partisan and the Legion (TankK), the only 4-node shapes, fire two shots per mission. Node counts come from each appearance's ASE (`weapon_nodes` in `data/vehicles/*.json`, `tools/convert/vehicles.py`). | `vehicle_weapon_nodes` |
| O2 | **Unlimited ammo** (I97). The single-player preference `UnlimitedAmmo` defaults to TRUE (logmain.cpp:53, 404-406). `calcAmmoTotals` then makes every pool `UNLIMITED_SHOTS` (mover.cpp:5784-5788), and no shot is deducted. Every unit on every side has it. The HUD shows ∞ for ammo weapons, as the original's info window drops the count (InfoWindow.cpp:658-662). With the flag off, bins run dry as described under "Firing". | `unlimited_ammo` |
