# Capture and mission objectives

Behavioural spec for **capture** (buildings, vehicles, salvaged mechs) and the
**mission objective system** (FIT `Team0Objective*` blocks, flags, activation,
win/lose). Written from a read of the original source
(`reference/mc2-source/Source/`), chiefly `Code/Objective.cpp/.h`,
`Code/tacordr.cpp`, `Code/warrior.cpp`, `Code/gameobj.cpp/.h`,
`Code/bldng.cpp/.h`, `Code/gvehicl.cpp/.h`, `Code/turret.cpp`, `Code/gate.cpp`,
`Code/objmgr.cpp`, `Code/mission.cpp`, `Code/team.cpp`, `Code/missiongui.cpp`,
`Code/controlGui.cpp`, `Code/LogisticsData.cpp`, `Code/ablmc2.cpp`. The
data comes from `Data/Missions/mc2_01..24.fit`, `Data/Missions/gamesys.fit`
and `Data/Objects/*.fit`. No code was copied.

Conventions are the same as `abl-natives.md` §0:
- Positions are world units.
- `distanceFrom` distances are 2-D metres (world units × 0.2).
- "Team 0" is the player's team.

**Quirk** marks faithful but probably unintended behaviour, with a
recommendation next to it. **Ambiguity** marks things the source does not
settle.

---

## Part A — Capture

### A1. What can be captured

Capturability is a per-object runtime flag, `CAPTURABLE`. Several things set
it. Nothing in the campaign path ever clears it, except a multiplayer-only HQ
case.

| Source | Applies to | Where |
|---|---|---|
| Building type FIT `[BuildingData] b Capturable = true` | that building type | bldng.cpp:265, 1269 |
| Being the parent ("control building") of a turret | turret controls | turret.cpp:551, objmgr.cpp:977 |
| Being the parent of a gate | gate controls | gate.cpp:265 |
| Being the parent of a child building, **only if** the parent's type is itself capturable | e.g. sensor control → towers | bldng.cpp:737 |
| Ground-vehicle type with `ResourcePoints > 0` | `OrdnanceTruck` (4000 RP) | gvehicl.cpp:917 |
| Objective condition **read** of `CaptureSpecificStructure`, `CaptureOrDestroySpecificStructure`, `CaptureSpecificUnit` or `CaptureOrDestroySpecificEnemyUnit` | the target object, whatever its type says | Objective.cpp:532, 577, 671, 725 |
| ABL `setCapturable(obj, b)` | buildings and ground vehicles only. The bool is **ignored**: it always sets the flag | ablmc2.cpp:3835 |

Some type FITs ship capturable:
- `RPBuilding`, `GenericRPBuilding`, `GenericHQ`, `LiaoRepairBay`,
  `OrdnanceTruckProp`.
- Every `*SensorControl`, `*TurretControl`, `*GateControl` and
  `*SpotlightControl`, plus `bturretcontrol`.

The faction HQs (`DavionHQ`, `LiaoHQ`, `SteinerHQ`) say **`Capturable =
FALSE`**. The same goes for the plain buildings the campaign asks you to
capture: `WeaponsFacility`, `Prison`, `MeetHall`, `RelayStation` and
`LiaoPowerGenerator`. They become capturable **only because an objective
names them**.

**So the objective loader must set the flag on each target it resolves.**
This is load-bearing.

**Worked example (mc2_02 Objective 0).** `CaptureSpecificStructure` at
(4160, 960) resolves to the `objects.json` entry of type 357:
- The type is `RPBuilding.fit`, "HeavyIndustrial", on team 1.
- Its FIT has `Capturable = true` and `ResourcePoints = 10000`.

So it is capturable by type. Capturing it also pays 10 000 in-mission
Resource Points (§A4). The objective's own `ModelID = 357` is just the
briefing model.

**Mechs** can never be captured by the capture order: the order's mech case
does nothing (tacordr.cpp:1192, 1811). `BattleMech::isCaptureable` is declared
but never defined.

The only way a mech changes sides is the **salvage craft** support power.
This is how `CaptureSpecificUnit` on a mech (mc2_11's salvage yard) is meant
to be satisfied:
1. It targets a **disabled** mech the player's team can see, while the
   force bar has room (missiongui.cpp:4453).
2. The VTOL lands and the mech is "traded" to the player's team **and
   commander**, with a new pilot (missiongui.cpp:1069, mission.cpp:1448).
3. The mech then joins the player's force.

The part field `Captureable` (mission.cpp:2659) feeds an unused mech member.
No campaign FIT sets it.

A mover counts as "captured" by objectives simply when its team is the
player's (Objective.cpp:118). The `CAPTURED` object flag is separate (§A6).

### A2. Who may capture, and how (player)

**Cursor** (missiongui.cpp:3784). Over an object that is capturable by the
home team, with at least one unit selected:
- The cursor is **capture** if every selected unit is a ground-moving mech
  that is not blocked (§A3).
- It is **X-capture** (refused) if any selected mech is blocked, or if any
  selected unit is not a ground mech: a vehicle, or a jumping/air mover.

**Click** (`doAttack`, missiongui.cpp:1793):
- A capturable target always produces a **capture** order, never an attack.
  To shoot a capturable building or truck the player must force-fire.
- If any selected unit is not a ground mech, or any selected mech is
  blocked, the whole click is refused with the `INVALID_GUI` sound.
- Otherwise every selected home-commander unit gets `TACTICAL_ORDER_CAPTURE`
  (21) and `BUTTON5` plays.

So **player captures are mech-only**. The engine itself does not check the
unit class: AI vehicles can run the order (§A5).

**Order execution** (tacordr.cpp:1129 on issue, 1726 each update):
1. **On issue.**
   - If the target is not capturable by the capturer's team, is friendly,
     or is already blocked, the order ends at once with radio
     `CANNOT_CAPTURE`.
   - Otherwise it proceeds.
2. **Each update.** The check runs in this order:
   - Target already on the capturer's team: the order completes silently.
   - Any blocker present (§A3): the order **ends**, with `statusCode = 1`
     and radio `CANNOT_CAPTURE`. It does **not** wait. The player must
     clear the area and re-issue.
   - Capturer **within 30 m** of the target's position (2-D,
     centre-to-centre) and the target still capturable: **capture
     happens instantly**. There is no timer or progress bar.
   - Otherwise the unit keeps moving. A building's move goal is an open cell
     next to it; a mover's goal is its position (warrior.cpp:4011). Line of
     fire is ignored while moving to capture (mover.cpp:4822).
3. **The capture itself:**
   - **Building:**
     - its commander becomes the capturer's commander;
     - its team changes to the capturer's team (setup = false);
     - radio `CAPTURED_BUILDING`.
   - **Ground vehicle:** its team changes; radio `CAPTURED_VEHICLE`.
   - **Mech:** nothing (see §A1).

**Ambiguity:** for a large building, the adjacent goal cell may lie more
than 30 m from its centre (RPBuilding's extent radius is 35 m). We
recommend measuring 30 m to the building's footprint edge, or to its centre
plus its extent radius. The source measures to the centre. Check against
mc2_02 in play.

### A3. Capture blockers (`getCaptureBlocker`, gameobj.cpp:2064)

The rule depends on how far the **capturer** is from the target:

- **Capturer within 30 m of the target.** A mover blocks if all of these
  hold:
  - its team is an enemy of the capturer's team;
  - it is not a "marine" (always false for mechs and vehicles);
  - it has at least one weapon;
  - it is within **`BlockCaptureRange` = 75 m of the target** (gamesys
    `Mover:General`);
  - it is not disabled;
  - it is awake.

  No sensor or line-of-sight contact is needed.
- **Capturer farther than 30 m** (the cursor test and the issue-time test).
  Same rule, with two changes:
  - movers with **no team** also count;
  - the capturer's team must currently have them as a **visual or sensor
    contact** (enemy, not disabled).

  So an unseen defender does not stop you issuing the order, but it does
  stop the capture when you arrive.

There is no other perimeter rule for capture:
- Perimeter alarms only raise the AI general alarm (see `abl-natives.md`
  #81).
- The prison flag is dead code ("NOTHING IS EVER A PRISON NOW").

`isCaptureable` itself also requires the following (bldng.cpp:1041,
gvehicl.h:444):
- the `CAPTURABLE` flag;
- the target is not already on the capturing team;
- the target is not destroyed;
- for buildings, the building is **awake**. A child building goes to sleep
  when its parent is disabled, destroyed or asleep (bldng.cpp:910).

A **disabled** (but not destroyed) vehicle is still capturable.

### A4. Consequences of a team change

**Buildings** (`Building::setTeamId`, bldng.cpp:922). In single player,
team 2 maps to 0 and teams > 2 map to 1. Then:
- **Sensor:** a building with a sensor moves it to the new team's sensor
  net. Betty `SENSOR_CAPTURED` plays after turn 5, except for lookout
  towers. This is the "capture sensor control" payoff: the towers follow
  the control (below), so their coverage becomes the player's.
- **Flash:** after turn 10 the building flashes for 5 s at 0.5 s intervals,
  coloured by the new team's relation to the player.
- **Resource Points:** after turn 10, a building type with
  `ResourcePoints > 0` adds that many in-mission RP and plays Betty
  `RESOURCES`.
  - **Quirk:** in single player this fires on *any* team change, so an
    enemy recapture would also pay the player.
  - Recommend: pay only when the new team is the player's.
- **RP building animation:** an RP building plays its "opening" animation
  once it is on team 0 (bldng.cpp:480).
- **Parent sync:** if the building has a parent on another team, the parent
  is set to the same team. Capturing a child captures its control.
- **Children** (turrets, gates and child buildings) adopt the parent's team
  on their own update, as long as the parent is not disabled or destroyed:
  - turret.cpp:640 (turrets only while active);
  - gate.cpp:291;
  - bldng.cpp:890.

  When the new team is not the player's (after turn 5), Betty
  `BUILDING_RECAPTURED` plays. Captured turrets fire for their new owner.
  Captured gates open for the new owner's movers, through area team
  ownership (gate.cpp:270).
- Building capture **does not** set the `CAPTURED` flag (§A6).

**Ground vehicles** (`Mover::setTeamId(team, false)`, mover.cpp:2642;
gvehicl.cpp:3134):
- The vehicle leaves its old team's roster and its pilot's team becomes
  *none*. It is **not** added to the new roster, gets no new commander and
  is not put on the player's GUI.
- With no team, its pilot clears all orders every update
  (warrior.cpp:4845). The vehicle becomes an **inert hulk** carrying the
  new team ID:
  - it is not controllable;
  - it is not part of the player's force for "all player units dead";
  - it is not an "enemy" for the destroy-all/destroy-N counts.
- A vehicle type with `ResourcePoints > 0` adds that many in-mission RP
  when the new team is the player's (after turn 10), with Betty
  `RESOURCES`.
- It is **not** salvage and is not carried into logistics.

**Mechs via salvage craft:** they join the player's force fully (§A1).

### A5. AI capture

- **Target priorities** (warrior.cpp:690):
  - `TARGET_PRIORITY_TURRET_CONTROL` (6) and `TARGET_PRIORITY_GATE_CONTROL`
    (8) pick the **closest** control building that is not friendly and is
    capturable for the pilot's team. No range limit applies, unlike
    `TURRET`.
  - The action is chosen by `calcAction`: a non-own-team building flagged
    as a control building gives **CAPTURE**; any other building gives
    ATTACK.
  - Only one campaign brain uses this: `mc2_06_wv2_1a` (an enemy wave that
    retakes the turret control, 325 m).
- **`coreCapture(obj, params)`** / **`newCapture`** (same native,
  warrior.cpp:5724):
  - `obj` 0 means the last scan target.
  - It returns 1 (done or impossible) if any of these hold:
    - the pilot has no team;
    - the target is missing, not capturable, or friendly;
    - the order's status check already succeeds (it captures if within
      30 m).
  - Otherwise it issues the capture order and returns 0.
  - No campaign brain calls it.
- **`orderCapture(target, params)`:** refuses if the target is friendly or
  currently blocked. It does not check capturability.
- **Goal planning:** the goal planner's capture logic forbids ground
  vehicles and air units (warrior.cpp:7577). It is off by default
  (`useGoalPlan = false`) and can be ignored.
- **`isTeamCapturing(team, target, except)`:** true if any mover of that
  team (team 0 = any) currently has a capture order on the target. The list
  is rebuilt every frame (objmgr.cpp:2595). `pbrain` uses it to skip
  calling for help while capturing.

### A6. Capture-related ABL natives: corrections to `abl-natives.md`

- **`isCaptured(obj)`** reads the object's `CAPTURED` flag. **Only ABL
  `setCaptured(obj)` sets that flag** (ablmc2.cpp:3801). A normal capture
  order never does.
  - In the original, `isCaptured` therefore returns 0 for buildings and
    vehicles the player actually captured, unless a script also called
    `setCaptured`.
  - A ground vehicle or pilot with the flag set stops moving and acting
    (gvehicl.cpp:2194, warrior.cpp:4858).
  - Recommend: faithful. `isCaptured` = flag. Only `miscfunc`'s count
    helper uses it.
- **`objectChangeSides(obj, team)`** calls the base `setTeam`, which **no
  subclass overrides**. It is a **no-op** in the original.
  - Campaign scripts call it on dead buildings (`cfunc.abi:999`, team 0)
    and on remembered building targets (`Orders.ABI:252`, team 1).
  - Implementing it as a real team change would hand destroyed enemy
    buildings to the player, and with them their RP payouts and sensor
    nets.
  - **Recommend: keep it a no-op.**
- **`wasEverCapturable(obj)`** is just "has the `CAPTURABLE` flag". The flag
  is never cleared, so it stays true after capture or death.
- **`isCapturable(obj, team)`** with team −2 means "flag set and not
  destroyed". Otherwise it uses the `isCaptureable` rules in §A3. Argument
  order is obj, then team.
- **`setCapturable(obj, b)`** always sets the flag; `b` is ignored.

### A7. Feedback summary

| Event | Feedback |
|---|---|
| Cursor | `mState_CAPTURE` / `mState_XCAPTURE` |
| Order accepted / refused | `BUTTON5` / `INVALID_GUI` |
| Capture done | pilot radio `CAPTURED_BUILDING` / `CAPTURED_VEHICLE`; building flash; RP building opens |
| Blocked / impossible | pilot radio `CANNOT_CAPTURE` |
| RP gained | Betty `RESOURCES` |
| Sensor changes hands | Betty `SENSOR_CAPTURED` |
| Turret or gate follows parent to a non-player team | Betty `BUILDING_RECAPTURED` |

---

## Part B — Objectives

### B1. File layout and loading

Every campaign mission uses `[Objectives Version] Version = 3`.

**Objective block.** `[Team0Objectives] NumObjectives = N`, then one
`[Team0Objective<i>]` block per objective with these fields:
- `Title` and `Description`, plus resource-string variants;
- `Priority`: 1 primary, anything else secondary;
- `ResourcePoints`;
- `PreviousPrimaryObjectiveMustBeComplete` (legacy name
  `PreviousObjectiveMustBeComplete`);
- `AllPreviousPrimaryObjectivesMustBeComplete`;
- `DisplayMarker`, `MarkerX`, `MarkerY`;
- `HiddenTrigger`;
- `ActivateOnFlag` and `ActivateFlagID` (legacy integer `ActivateFlagIndex`);
- `ResetStatusOnFlag` and `ResetStatusFlagID`;
- model fields for the briefing;
- `NumConditions`, `NumActions`, `NumFailureConditions`,
  `NumFailureActions`.

**Sub-blocks** (Objective.cpp:1627):
- `[Team0Objective<i>Condition<j>]` with `ConditionSpeciesString`;
- `...Action<j>` with `ActionSpeciesString`;
- `...FailureCondition<j>` with `FailureConditionSpeciesString`;
- `...FailureAction<j>` with `FailureActionSpeciesString`.

The integer `ConditionSpecies` is a legacy fallback. Saved games add the
state fields `IsActive`, `ActivationTime`, `IsResolved`, `ResolvedStatus`
and `ChangedStatus`.

**Loading.** Objectives load **after** all movers and buildings exist
(mission.cpp:2804), because targets are resolved by position at read time.

**Unresolved targets.** A sub-block that fails to read is **silently
dropped**: the assert is off in release, and the condition is deleted and
skipped. That includes a target that cannot be resolved.

**Quirk:** an objective whose every condition was dropped has zero
conditions, and a zero-condition objective **succeeds on its first
evaluation** (see B4). mc2_11 O13 "bool 06" ships with zero conditions on
purpose: it sets flag 6 at mission start.

**Optional flag table.** `[Team0BooleanFlags]` (`BooleanString<k>` /
`BooleanValue<k>`) can pre-load flags. No campaign mission has one.

**Nav markers.** `[NavMarkers]` / `[NavMarker<k>] xPos yPos radius` adds
hidden priority-2 objectives at the **end** of the list, so ABL indices are
unaffected (Objective.cpp:2262).

Each nav-marker objective has:
- one `MoveAnyUnitToArea` condition;
- one internal `_RemoveStructure` action.

The action moves the building sitting at exactly (xPos, yPos), a
`navmarker1` prop, off the map to (100000, 100000), so the marker vanishes
when reached. If no building matches exactly, the nav-marker objective is
dropped.

Nav markers are used in mc2_01 (2), mc2_04, mc2_17 and mc2_20.

### B2. Target identification

For specific-unit and specific-structure conditions, the game reads **only**
`PositionX` and `PositionY` (or a saved-game `MoverWID` / `BuildingWID`).

**`CellX`, `CellY`, `Commander`, `Group` and `Mate` are ignored.** They
are editor leftovers.

**Matching:**
- The x and y values must match to a relative tolerance of about 1e-5
  (`areCloseEnough`).
- **Structures:** the first building in object-manager order at that
  position. Team is not checked.
- **Units** (`DestroySpecificEnemyUnit`, `CaptureSpecificUnit`, both
  `CaptureOrDestroy…Unit`): the first mover at that position **whose team
  is not the objective's team**. `GuardSpecificUnit` requires the same team.

**Consequence: mc2_10 O5's six failure conditions are dropped.** They name
the allied convoy, whose parts are team 0 under commander 2. No non-team-0
mover sits at those positions, so all six are dropped and "Protect the
Convoy" can never fail. That is faithful. Recommend matching it, or making
the fix a `SimRules` flag.

Every other specific target in the 24 missions resolves. A survey found two
mc2_10 allied parts sharing a position; first match wins.

Movers must be matched at their **spawn** position. Keep the part's FIT
position unmodified until objectives are read.

### B3. Condition semantics

"Enemy" below means **any mover whose team differs from the objective's
team**. In the campaign, allies are team 0 under commander 2, so they are
not enemies. mc2_24's commander-2 parts are team 2 and would count, but
that mission has no destroy-all or destroy-N condition.

**Shared predicates:**
- **Dead** (`MoverIsDeadOrDisabled`): any of
  - status DISABLED or DESTROYED;
  - pilot DEAD;
  - pilot EJECTED.
- **Withdrawn (fled) movers are *not* dead** for the Destroy\* species.
  Only the unused DeadOrFled\* species count them.
- **Captured mover:** not destroyed, and its team equals the objective's
  team.

A condition reports one of three statuses: **undetermined**, **success** or
**fail**.

| Species (count in campaign) | Success | Fail | Notes |
|---|---|---|---|
| `DestroyAllEnemyUnits` (10) | every enemy mover is dead | never | Every mover in the object manager counts, including ones not yet awake or spawned. A unit that never appears, or that withdraws, blocks it forever. A captured vehicle changes team, so it simply leaves the set. |
| `DestroyNumberOfEnemyUnits` `Num` (6) | the count of enemy movers that are dead now is ≥ Num | never | The count is recomputed from scratch every evaluation, not tallied since start. Disabled movers count. **Captured movers do not count**: they are no longer enemy. Movers that start disabled (part `Damage ≥ 1`) count from frame 1. mc2_09 has 3, so its "Destroy 12" needs 9 kills. Buildings never count. |
| `DestroySpecificEnemyUnit` (301) | target dead, or captured | never | |
| `DestroySpecificStructure` (54) | building destroyed | never | Capture does **not** count. Does not set the capturable flag. |
| `CaptureSpecificUnit` (9) | target's team = objective team | target **destroyed** (or missing) | Disabled is not failure: a disabled vehicle can still be captured, and a disabled mech can be salvaged. Sets the flag on read. |
| `CaptureSpecificStructure` (42) | building's team = objective team | building destroyed | Sets the flag on read. If the building already belongs to the objective's team it succeeds at once: mc2_06 O0 "Protect the Base HQ" names the player's *own* HQ (team 0). That read also makes the player's HQ capturable by the enemy. An enemy recapture leaves it undetermined, not failed. Once success is latched it stays (B4). |
| `CaptureOrDestroySpecificEnemyUnit` (12) | target dead, or captured | never | Sets the flag. All 12 campaign targets are **mechs** (mc2_09, mc2_12), so in practice it means "disable it". |
| `CaptureOrDestroySpecificStructure` (2) | destroyed, or team = objective team | never | Sets the flag. |
| `MoveAnyUnitToArea` `TargetCenterX/Y`, `TargetRadius` (18) | any mover on the player's GUI under the player's commander (vehicles included) is strictly inside the radius | never | World units. Only the player's own units count: no allies, no captured hulks. |
| `MoveAllSurvivingMechsToArea` (18) | see the rules after this table | never | |
| `BooleanFlagIsSet` `FlagID`, `Value` (13) | the team flag table's value for FlagID equals Value | never | A missing flag reads **false**. FlagID is a string ("0", "10", "flag10", "F1"). The legacy integer `FlagIndex` becomes its decimal string. The campaign only tests TRUE. |
| `ElapsedMissionTime` `Time` (2) | mission time ≥ Time | never | **Seconds** of game time (`actualTime`). mc2_17: 3 s. mc2_11: 9 s. |

**`MoveAllSurvivingMechsToArea`** succeeds when both of these hold:
1. Every ground mech on the player's GUI under the player's commander that
   is not dead or fled is inside the radius. Air movers are skipped. No
   survivors also counts: it succeeds vacuously.
2. **No mover under any other commander** that is not dead or fled is
   within `MaxUnitExtractDistance` = **1280 world units** (10 tiles,
   256 m) of the area centre. "Any other commander" includes **allies**.

**Quirk:** a living ally parked at the extraction point blocks extraction.

Unused species, defined for completeness:
- `DestroyEnemyUnitGroup` and the other Group species have no class.
  Treat them as invalid.
- `DeadOrFled*` counts **all** movers, the player's own included. This is a
  bug.
- `GuardSpecificUnit` fails if the unit is destroyed or changes team.
- `GuardSpecificStructure` fails if destroyed or captured away, and
  succeeds once a mission `TimeLimit` passes.
- `MoveAllUnitsToArea` and `MoveAllSurvivingUnitsToArea` are like the mech
  version but include vehicles, skip units being recovered, and have no
  enemy-proximity rule.

### B4. Objective evaluation (`CObjective::Status`, Objective.cpp:1821)

**Inactive or resolved:**
- An **inactive** objective reports undetermined and evaluates nothing.
- A **resolved** objective returns its latched status. It is not
  re-evaluated, so later changes cannot revert it. The one exception is
  ResetStatusOnFlag (B5).

**Otherwise**, all of the following happen in one evaluation:
1. **Success conditions are ANDed.**
   - Any condition reporting fail makes the objective **fail**, and the
     remaining conditions are skipped.
   - Any undetermined condition makes it undetermined.
   - **Zero conditions means success.**
2. **Failure conditions are ANDed.** This runs only if step 1 did not
   already fail and there is at least one failure condition.
   - The objective fails only if **every** failure condition reports
     success.
   - Evaluation stops at the first condition that is not success.
   - Failure **overrides** success in the same evaluation.
3. **On resolution** the status latches.
   - On **success**, Betty `OBJECTIVE_COMPLETE` plays, unless the objective
     is a hidden trigger. The success **actions** then run in list order.
   - On **failure**, Betty `CANNOT_COMP_OBJ` plays (again not for hidden
     triggers). The **failure actions** then run.
   - Actions run exactly once, at that moment.

**Status values** are 0 undetermined ("incomplete"), 1 success and
2 failed. `StatusChangedSuccess/Failed` are read-and-clear "changed since
last asked" bits; ABL `getObjectiveSuccess/Failed` ORs them over every
objective.

### B5. The per-frame sweep (`CObjectives::Status`, Objective.cpp:2116)

**When it runs.** In single player it runs every unpaused frame, after the
mission ABL script, as long as both of these hold:
- the termination countdown has not started;
- the script did not return −1 (mission.cpp:600).

The sweep goes through the objectives in FIT order. For each objective:

**Active objective:**
1. **Reset.** If ResetStatusOnFlag is set and its flag is true, clear the
   flag to false and set the objective back to undetermined. This
   un-resolves it, so its actions can fire again. No campaign mission uses
   it.
2. **Gating:**
   - With **AllPreviousPrimaryObjectivesMustBeComplete**, if any earlier
     *active* primary is not yet a success, the objective reports
     undetermined and is **not evaluated**. Its conditions do not run and
     its actions cannot fire.
   - With **PreviousPrimaryObjectiveMustBeComplete**, the objective
     reports the status of the nearest earlier primary while that primary
     is not a success. No campaign mission uses this.
   - Otherwise the objective is evaluated (B4).
   - Gating applies to secondaries too: mc2_10 O5 is a gated secondary.
3. **Primaries feed the mission result.**
   - A **failed** primary makes the mission status *failed*, and the sweep
     **stops**: later objectives are not evaluated that frame.
   - An undetermined primary makes the mission status undetermined.

**Inactive objective with ActivateOnFlag:**
- A primary keeps the mission status undetermined: "don't end while a
  primary is still hidden".
- If its flag is now true, the objective becomes active, records its
  activation time and opens the objectives panel.
- It is evaluated from the **next** sweep onward.

Secondaries never affect the mission status.

**Quirk: two inconsistencies in the per-objective query.** ABL
`checkObjectiveStatus(n)` uses a separate query (Objective.cpp:1896). It
walks objectives 0..n with the same gating, but:
- earlier *inactive* primaries count as not complete, whereas the sweep
  ignores them;
- it does not stop at an active objective.

Because it calls each earlier objective's evaluator, **checking status can
itself resolve objectives and fire their actions**. Scripts poll it every
frame, so this matters for timing. Recommend: one evaluator, with the query
reading latched or gated state. Keep the side effect: resolving at query
time.

### B6. Mission result (mission.cpp:529–650)

In single player, the following end the mission, each after a **5 s**
countdown:
- **All player units down.** Every mover under the player's commander that
  is on the GUI is disabled or destroyed: **lose**.
- **Objectives resolved.** At least one primary exists and the sweep
  reports a status other than undetermined: success means **win**, failure
  means **lose**.
  - "Success" means every active primary has succeeded and no
    flag-activated primary is still inactive.
  - Secondaries and hidden triggers are irrelevant.
  - One failed primary is an immediate loss.
- **Time limit.** `MissionSettings TimeLimit` (seconds; −1 = none) has
  passed and nothing else has ended the mission: **lose**. Only mc2_21 has
  one: 1080 s = 18 min.

Only `PLAYER_WIN_BIG` (5) and `PLAYER_LOST_BIG` (1) are ever produced. The
SMALL and DRAW results never occur in the campaign.

**The ABL return value.** The mission brain's return value is written into
the termination result every frame, and 9999 aborts the mission. All 24
campaign scripts return `PLAYING` (0), so objectives and the rules above
decide the result.

**Final re-check.** When the countdown finishes and the result is 0 because
the script overwrote it, the result is re-derived:
- win if the sweep reports success now;
- lose otherwise.

**Quirk:** if every player mech dies when all other primaries are done and
the remaining one is a vacuous "move all surviving mechs", that check can
come out as a win. Recommend: all-dead is always a loss.

**Rewards** (LogisticsData.cpp:1308):
- **On a win only**, every objective whose status is success adds its
  `ResourcePoints` as **C-Bills** to the campaign purse. That covers every
  priority, but hidden triggers carry 0.
- The debrief tallies primaries, then secondaries, active and non-hidden
  only (controlGui.cpp:675).
- The objective field is named ResourcePoints but pays **post-mission
  C-Bills**. It is distinct from in-mission Resource Points, which start at
  `MissionSettings ResourcePoints` and grow from RP buildings and trucks
  (§A4).

**Markers:**
- Numeric tac-map markers are drawn at `MarkerX/Y` for active, unresolved
  objectives with `DisplayMarker`.
- Primaries are numbered 1, 2, … in order.
- Secondaries are lettered a, b, … The letter counter advances for **every**
  non-primary, hidden ones included, so letters can skip.

### B7. Flags

**Storage.** Flags are a per-team table from string to bool. A missing key
reads false.

**What sets them:**
1. `SetBooleanFlag` success and failure actions;
2. the optional `[Team0BooleanFlags]` preload;
3. saved games;
4. ResetStatusOnFlag clearing its own flag.

**ABL has no native that reads or writes them.** Scripts communicate with
objectives only through `checkObjectiveStatus` and the success/failed
change bits. That is why the campaign is full of hidden-trigger objectives
with no actions: the scripts poll them.

### B8. Actions

An action fires when its objective resolves: success actions on success,
failure actions on failure.

| Species | Fields | Effect | Campaign use |
|---|---|---|---|
| `SetBooleanFlag` | `FlagID`, `Value` | set the team flag | 45 uses |
| `PlayWAV` | `WAVFileName` | stream a voice-over file (path relative to the game root) | 4: mc2_08 ×1, mc2_11 ×3 |
| `MakeNewTechnologyAvailable` | `PurchaseFileName` | add a bonus purchase file to logistics, unlocking shop items (`data\missions\PurBonusNN.fit`) | 6: mc2_08, 11, 13, 19, 20, 21 |
| `PlayBIK` | `AVIFileName` | play a movie | unused |
| `DisplayTextMessage` | `Message` | chat-line text | unused |
| `DisplayResourceTextMessage` | `ResourceStringID` | chat-line text from a string ID | unused |
| `_RemoveStructure` | position / `BuildingWID` | move a building off the map | internal: nav markers only |

**Ambiguity:** `MakeNewTechnologyAvailable` fires at resolution time, even
if the mission is later lost. Whether the unlock survives a loss depends on
whether logistics state is rolled back on retry. Recommend: commit unlocks
only on a win.

**No campaign mission has a failure action.** Failure conditions appear
only in mc2_10 O5, and are dropped (B2).

### B9. Campaign survey (mc2_01–mc2_24)

**Condition species totals** (success conditions; plus 6 failure
conditions, all `DestroySpecificEnemyUnit` in mc2_10):

| Species | Count | Missions |
|---|---|---|
| DestroySpecificEnemyUnit | 301 | 01 02 03 04 06 10 12 13 14 15 16 17 18 20 22 23 24 |
| DestroySpecificStructure | 54 | 01 03 05 07 08 09 11 13 14 15 19 20 21 22 23 24 |
| CaptureSpecificStructure | 42 | 02 03 04 05 06 07 09 10 11 13 14 16 18 19 20 21 23 |
| MoveAnyUnitToArea | 18 | 01 02 04 08 09 11 15 17 18 20 21 24 |
| MoveAllSurvivingMechsToArea | 18 | 01 04 05 07 08 09 10 11 12 13 14 15 16 19 20 21 22 24 |
| BooleanFlagIsSet | 13 | 02 09 11 24 |
| CaptureOrDestroySpecificEnemyUnit | 12 | 09 12 |
| DestroyAllEnemyUnits | 10 | 06 07 10 14 17 18 19 20 |
| CaptureSpecificUnit | 9 | 03 05 11 23 |
| DestroyNumberOfEnemyUnits | 6 | 06 09 18 19 |
| CaptureOrDestroySpecificStructure | 2 | 11 |
| ElapsedMissionTime | 2 | 11 17 |

**Action totals:** SetBooleanFlag 45, MakeNewTechnologyAvailable 6, PlayWAV 4.
Failure actions: none.

**Activation and gating features:**
- `ActivateOnFlag`: mc2_01 02 03 04 08 09 10 14 17 18 20 23 24.
- `AllPreviousPrimaryObjectivesMustBeComplete`: mc2_01 04 05 07 08 09 10 11
  12 13 14 15 16 19 20 22 24. It is almost always on the extraction
  objective.
- `PreviousPrimaryObjectiveMustBeComplete` and `ResetStatusOnFlag`: never
  used.
- Hidden triggers: most missions.
- Preloaded flags: none.

**Capture targets by type:**

| Building or unit type | Objectives |
|---|---|
| WeaponsFacility | mc2_03 04 05 09 11 ×2 13 ×3 19 21 |
| Faction HQ | 02, 06 (own), 07, 10, 11 (C-or-D), 16, 18, 19 |
| Sensor control | 02 06 11 (C-or-D) 14 16 18 23 |
| RPBuilding | 02, 11 ×5 |
| Turret control | 06, 16 ×3 |
| Gate control | 16 ×2 |
| Prison | 05, 20 |
| LiaoRepairBay | 05 |
| MeetHall | 14 |
| RelayStation | 14 |
| LiaoPowerGenerator | 18 |
| CaptureSpecificUnit: MobileHQ vehicle | mc2_03, mc2_23 |
| CaptureSpecificUnit: OrdnanceTruck ×2 | mc2_05 |
| CaptureSpecificUnit: pre-disabled mechs ×5 | mc2_11 (salvage craft) |

mc2_13 O3's weapons facility is neutral (team −1).

**Per-mission features:**
- **mc2_01:**
  - flag chain 0→2→3→4→5;
  - 2 nav markers;
  - flag-activated, gated extraction.
- **mc2_02:**
  - captures: RP building (pays 10 000 RP), sensor control, Steiner HQ;
  - O5 is a primary that only ANDs flags 3 and 4;
  - O3 and O4 both activate on flag 2.
- **mc2_03:**
  - capture the MobileHQ vehicle (sets flag 0);
  - flag-activated capture of a weapons facility, then a counter-attack.
- **mc2_04:**
  - capture a weapons facility;
  - 1 nav marker;
  - two different hidden area triggers both set flag 0.
- **mc2_05:**
  - three building captures (weapons facility, repair bay, prison);
  - secondary capture of two ordnance trucks (+4000 RP each);
  - no flags.
- **mc2_06:**
  - "Protect HQ" as CaptureSpecificStructure of the player's own HQ plus
    DestroyAll;
  - capture sensor and turret control (secondaries);
  - hidden DestroyNumber 30;
  - enemy AI retakes the turret control.
- **mc2_07:** capture Liao HQ; DestroyAll as a secondary.
- **mc2_08:** O1 fires SetBooleanFlag, PlayWAV and MakeNewTech together.
- **mc2_09:**
  - capture a weapons facility;
  - CaptureOrDestroy Lao Hu (a mech);
  - hidden DestroyNumber 12 (3 enemies start disabled);
  - a four-flag AND trigger sets flag 15, which activates extraction.
- **mc2_10:**
  - secondary capture of Steiner HQ;
  - the only failure conditions (inert, B2), on a gated hidden secondary.
- **mc2_11:**
  - O0 and O1 are secondaries listed before the primaries;
  - 5 RP-building captures in one objective;
  - CaptureOrDestroy of Steiner HQ (primary) and of the sensor control
    (hidden);
  - 5 CaptureSpecificUnit hidden triggers on pre-disabled mechs (salvage
    craft) feed a 5-flag secondary;
  - a zero-condition objective;
  - ElapsedMissionTime 9 s plays the intro WAV;
  - PlayWAV ×3;
  - MakeNewTech on extraction.
- **mc2_12:** 11 CaptureOrDestroy mechs across 4 convoy objectives.
- **mc2_13:**
  - 3 weapons-facility captures (one neutral);
  - MakeNewTech on a hidden "kill the Clan pair" trigger.
- **mc2_14:**
  - "Contact operative" = capture the MeetHall, which sets flag 0 and
    activates 9 objectives;
  - captures: sensor control, relay station;
  - DestroyAll as a secondary.
- **mc2_15:** no capture; hidden triggers.
- **mc2_16:** captures: sensor control, Davion HQ, 3 turret controls,
  2 gate controls.
- **mc2_17:**
  - the primary O0 is ElapsedMissionTime 3 s. It plays "objective
    complete" at 3 s and activates DestroyAll;
  - 1 nav marker.
- **mc2_18:**
  - two DestroyAll primaries;
  - "recapture" HQ, power generator and sensor control;
  - hidden DestroyNumber 36 and 25.
- **mc2_19:**
  - primary DestroyNumber 25, secondaries DestroyNumber 50 and DestroyAll;
  - captures: Liao HQ, weapons facility (+MakeNewTech).
- **mc2_20:**
  - capture the prison (+MakeNewTech);
  - 1 nav marker;
  - DestroyAll as a secondary.
- **mc2_21:**
  - TimeLimit 1080 s;
  - a single primary (extract);
  - capture a weapons facility (+MakeNewTech).
- **mc2_22:** destroy and extract only.
- **mc2_23:** captures: sensor control, MobileHQ vehicle (secondaries).
- **mc2_24:** string flags `flag10`, `flag11` and `F1`; a 2-flag AND
  trigger activates extraction.

### B10. Open questions

1. **The 30 m capture radius for large buildings** (A2). We need to see
   whether original play ever stalls next to a big HQ.
2. **Mover spawn snapping.** Any position adjustment before objectives load
   would break position matching (B2).
3. **The tech-unlock commit point** (B8).
4. **Mission time while paused.** Whether `actualTime` advances while
   paused matters for `ElapsedMissionTime` and the 18-minute limit. The
   sweep itself does not run while paused.
5. **Disabled mechs destroyed after disabling.** mc2_11's disabled
   salvage-yard mechs fail their `CaptureSpecificUnit` triggers if
   destroyed (blown apart after disabling). We need to check whether the
   damage model can take a disabled mech to DESTROYED.
