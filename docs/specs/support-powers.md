# Support powers and Resource Points

Behavioural spec for the player's **in-mission support powers**: the
"vehicle" tab of the control GUI, the Resource Points (RP) that pay for it,
and the units, strikes and repair rules behind each button. Written from a
read of the original source (`reference/mc2-source/Source/`), chiefly:
- `Code/controlGui.cpp/.h` (buttons, costs, affordability);
- `Code/missiongui.cpp` (targeting, VTOL/Karnov delivery, salvage);
- `Code/artlry.cpp/.h`, `Code/dartlry.h` (air strikes, sensor probes);
- `Code/gvehicl.cpp/.h` (repair truck, minelayer, aerospace spotter);
- `Code/tacordr.cpp`, `Code/mover.cpp` (refit and recover maths);
- `Code/mission.cpp`, `Code/LogisticsData.cpp`, `Code/LogisticsMissionInfo.cpp`
  (RP start, carry-over, per-mission enable flags);
- `Code/ablmc2.cpp` (`callStrike`, `callStrikeEx`).

Data comes from `Data/Missions/gamesys.fit`, `Data/Missions/mc2_01..24.fit`,
`Data/Objects/*.fit` and `Data/Objects/object2.rsp`. The object-type number
of a FIT is its **0-based line index in `object2.rsp`** (line 0 is
`<NULL>`); for example, 182 is `RepairTruck.fit`. No code was copied.

Conventions are the same as `abl-natives.md` §0 and
`capture-and-objectives.md`:
- Positions and `ExtentRadius` values are world units (wu).
- Metres are wu × 0.2. A terrain cell is 128/3 wu (about 8.5 m).
- "Team 0" is the player's team.

**Quirk** marks faithful but probably unintended behaviour, with a
recommendation next to it. **Ambiguity** marks things the source does not
settle.

---

## 1. Resource Points

### 1.1 What they are

The in-mission RP balance is one integer, `LogisticsData::resourcePoints`.
The source comment on it says "C-Bills for buying mechs", but in single
player it is used **only** for the support tab. The campaign purse
(`cBills`) is a separate field (LogisticsData.h:245, :91–94).

### 1.2 Starting amount

At mission load the balance is **set**, not added to. Earlier RP are
discarded.
- `LogisticsData::setCurrentMission` sets it from the mission's
  `[MissionSettings] ResourcePoints` (LogisticsData.cpp:769, via
  LogisticsMissionInfo.cpp:309, :1003).
- `Mission::init` sets it again from the same key (mission.cpp:2110–2122).
- The debug command-line switch `-rps N` overrides it (MechCmd2.cpp:2536,
  mission.cpp:2112). Our build need not support this.

Starting RP per campaign mission, from the shipped FITs:

| Mission | RP | Mission | RP | Mission | RP |
|---|---|---|---|---|---|
| mc2_01 | 22000 | mc2_09 | 30000 | mc2_17 | 0 |
| mc2_02 | 6000 | mc2_10 | 6000 | mc2_18 | 16000 |
| mc2_03 | 16000 | mc2_11 | 0 | mc2_19 | 12000 |
| mc2_04 | 16000 | mc2_12 | 0 | mc2_20 | 12000 |
| mc2_05 | 7000 | mc2_13 | 0 | mc2_21 | 23000 |
| mc2_06 | 25000 | mc2_14 | 0 | mc2_22 | 16000 |
| mc2_07 | 6000 | mc2_15 | 6000 | mc2_23 | 36000 |
| mc2_08 | 0 | mc2_16 | 16000 | mc2_24 | 10000 |

The tutorials: `tut_01`–`tut_03` start with 0, `tut_04`–`tut_05` with
100000. The converted value is in `game/data/missions/*.json` under
`MissionSettings.ResourcePoints`.

### 1.3 Gaining RP during a mission

These are the only single-player sources:

| Source | Amount | Condition | Where |
|---|---|---|---|
| Capture a building whose type has `ResourcePoints > 0` (`RPBuilding`, `GenericRPBuilding`) | +type value (10000) | team change after turn 10; Betty `RESOURCES` | bldng.cpp:959–971 |
| Capture a ground vehicle whose type has `ResourcePoints > 0` (`OrdnanceTruck`) | +type value (4000) | new team is the player's, after turn 10 | gvehicl.cpp:3139–3141 |
| Cancel a support call before it is placed (§2.3) | +full cost | | controlGui.cpp:2018–2022 |
| Salvage craft leaves without recovering its mech (§3.6) | +10000 | | missiongui.cpp:1104–1113 |
| Debug key Ctrl+Alt+Shift+P | balance **set** to 100000 | cheat | mission.cpp:366–369 |

Capture rules, including the quirk that an enemy recapture of an RP
building also pays the player, are in `capture-and-objectives.md` §A4.

Things that do **not** give in-mission RP:
- Destroying units. `RPsForMechsEnabledDefault` is read only by the
  multiplayer setup screen (MPParameterScreen.cpp:664).
- Objective `ResourcePoints`. Those pay campaign **C-Bills** after a win
  (`capture-and-objectives.md` §B6).

### 1.4 Spending, and limits

- **Cost is charged when the button is pressed**, before the player picks
  a target (controlGui.cpp:1966–1975). §2.3 covers refunds.
- A button is disabled while its cost is more than the balance
  (controlGui.cpp:1797–1806). The balance therefore never goes negative
  from the GUI.
- **No cap.** The balance is a 32-bit integer with no ceiling anywhere.
- No per-power cooldown and no per-mission count limit in single player.
  The real limit is "one delivery at a time" (§2.2).
- The RP total is drawn under the tab with the `IDS_RP` format string. It
  can be made to flash for tutorials (`flashRPTotal`, controlGui.cpp:294,
  1919–1937). Each cost is printed under its button.

### 1.5 Carry-over

**None.** Unspent RP are lost at mission end; the next mission overwrites
the balance (§1.2). Mid-mission saves store the current balance
(saveload.cpp:318, :929, :1492). Support units are not carried into
logistics. The one support outcome that does persist is a **salvaged mech**
(§3.6): at mission end, every player-commander BattleMech that is not an
air unit, not destroyed and not disabled is added to the inventory. That
includes mechs recovered during the mission (LogisticsData.cpp:1338–1386).

---

## 2. The support tab

### 2.1 Buttons, costs, units

There are eight vehicle-tab buttons with IDs 100–107. Their costs are
**hard-coded** in the `vehicleCosts` array (controlGui.cpp:80–89, enum at
ControlGui.h:205–216). They are not data-driven.

| # | Button (enum) | In-game power | Cost | Enable flag (`canHave…`) | Delivers |
|---|---|---|---|---|---|
| 0 | `LARGE_AIRSTRIKE` | Air strike | **7000** | `AirStrikesEnabledDefault` | artillery object 248 `artbig.fit` (249 `artsml.fit` without LOS) |
| 1 | `GUARD_TOWER` | Artillery piece | **8000** | `ArtilleryPieceEnabledDefault` | ground vehicle 415 `GuardTower.fit` ("ArtilleryPiece"), pilot `PMWGuardTower` |
| 2 | `SENSOR_PROBE` | Sensor probe | **2000** | `SensorProbesEnabledDefault` | artillery object 250 `artsns.fit` |
| 3 | `REPAIR_VEHICLE` | Repair truck | **6000** | `RepairVehicleEnabledDefault` | ground vehicle 182 `RepairTruck.fit`, pilot `PMWRepair` |
| 4 | `PEGASUS_SCOUT` | Scout copter | **2000** | `ScoutCoptersEnabledDefault` | air "mech" 393 `ScoutCopter.fit`, pilot `PMWScout` |
| 5 | `MINELAYER` | Minelayer | **4000** | `MineLayersEnabledDefault` | ground vehicle 120 `Minelayer.fit`, pilot `PMWMinelayer` |
| 6 | `RECOVERY_TEAM` | Salvage craft (Karnov) | **10000** | `SalvageCraftEnabledDefault` | no unit: Karnov VTOL animation; ID 147 (`MobileHQ.fit`) is only a token |
| 7 | `STOP_VEHICLE` | Cancel | 0 | always | none |

The vehicle IDs and pilot files are in controlGui.cpp:92–115. The button
enum name and the in-game meaning differ for two buttons:
- `GUARD_TOWER` is the **artillery piece**. Its vehicle name string is
  "guardTower", and its FIT `Name` is "ArtilleryPiece".
- `RECOVERY_TEAM` is the **salvage craft**.

Name the powers by their in-game meaning.

There is **no separate "small air strike" button**. The small strike exists
only as the automatic no-line-of-sight downgrade (§3.1). The `smlAirStrike`
branch of `addAirstrike` is unreachable: it tests `LARGE_AIRSTRIKE` twice
(missiongui.cpp:4127–4130).

There is **no repair-bay or "recovery" purchase**. Repair bays are map
buildings (§3.7).

### 2.2 Availability (disable rules, every frame)

`updateVehicleTab` (controlGui.cpp:1794–1880) disables a button when **any**
of these is true:
1. Its cost is more than the balance, unless it is the pressed button or a
   vehicle is being placed.
2. **Another** button is pressed: an air strike, vehicle or salvage call is
   being targeted.
3. **Unit cap.** The force bar has 16 or more icons (`MAX_ICONS`,
   ForceGroupBar.h:21). This disables repair truck, scout, salvage,
   minelayer and artillery piece, but not the air strike or the sensor
   probe.
4. **Salvage only:** no spare pilot is left (`gotPilotsLeft`: an available,
   undead pilot not already in a mech on the map).
5. The mission's enable flag is false (`canHave…`, LogisticsMissionInfo.cpp
   :1180–1215).

While a VTOL or Karnov is flying (`paintingVtol`), `beginVtol` disables all
buttons except Cancel (missiongui.cpp:4450). They come back when the
aircraft leaves (`unPressAllVehicleButtons`, missiongui.cpp:987, :1117).
So **at most one VTOL/Karnov delivery per player runs at a time**. Air
strikes cannot be called during a delivery either. Several air strikes
**can** be stacked back to back, because a strike frees the tab as soon as
it is placed.

**Enable flags.** These come from the mission FIT `[MissionSettings]`
(LogisticsMissionInfo.cpp:319–339). A missing key means enabled, **except**
`ArtilleryPieceEnabledDefault`, which defaults to off. Every shipped
campaign mission, mc2_01–mc2_24, sets **all twelve flags TRUE**. So:
- in the shipped campaign every power is available in every mission;
- there are **no per-campaign or progressive unlocks** in the code;
- the practical gate is the mission's RP budget, which is 0 in six
  missions.

These flags are **multiplayer-only** and are ignored in the campaign:
`NoVariantsEnabledDefault`, `ResourceBuildingsEnabledDefault`,
`RPsForMechsEnabledDefault`, `UnlimitedAmmoEnabledDefault` and
`AllTechEnabledDefault` (MPParameterScreen.cpp:652–664). In single player,
unlimited ammo comes from the **player preference** `UnlimitedAmmo`, which
defaults to TRUE (prefs.cpp:143–145). With it on, every ammo bin is
infinite (mover.cpp:5784–5788).

### 2.3 Press, target, cancel

1. **Press** a button: its cost is deducted, the button shows pressed, and
   the others go disabled (controlGui.cpp:1958–1985). The mode becomes one
   of:
   - *adding artillery* (air strike, sensor probe);
   - *adding vehicle* (repair, scout, minelayer, artillery piece);
   - *adding salvage* (salvage craft).
2. **Click** the map with the left mouse button released, not a drag
   (missiongui.cpp:1314–1336):
   - **Air strike / sensor probe:** any map point. No line of sight is
     needed. The strike is placed at once (§3.1, §3.2).
   - **Vehicle:** the point must be on the map, in **team line of sight**,
     passable and not water (`canAddVehicle`, missiongui.cpp:3638–3662).
     Otherwise the click plays "invalid" and stays in placement mode.
   - **Salvage:** the cursor's target must be a **BattleMech** that is
     **disabled and not destroyed**, at a point in team LOS (`canRecover`,
     missiongui.cpp:3665–3690). The team is **not** checked, so a disabled
     enemy, allied or own mech all qualify.
3. **Cancel** while still in placement mode, with the Cancel button or the
   Stop command (controlGui.cpp:1692–1696): the pressed button's cost is
   refunded in full (controlGui.cpp:2003–2033). **Once a VTOL is in flight,
   Cancel is refused** (controlGui.cpp:1949–1954), and there is no refund.
4. Hotkey actions exist for "press air strike" and "press sensor probe"
   (missiongui.cpp:4692, :4697, :4744; ControlGui.h:252–278).

---

## 3. Each power

### 3.1 Air strike (7000 RP)

**Placement** (`IfaceCallStrike`, artlry.cpp:159–235; `CallArtillery`,
artlry.cpp:99–153):
- The strike lands **exactly** at the clicked point. The random offset of up
  to ±5 tiles in `makeAirStrikeTarget` is commented out
  (missiongui.cpp:2347–2368), and the `randomOffset` argument of
  `CallArtillery` is unused.
- **LOS downgrade:** if the point is **not** in the player team's LOS, the
  big strike becomes the **small** strike, for the same 7000 RP
  (artlry.cpp:185, 210–214). The help text switches between the
  `IDS_AIRSTRIKE_HELP_NO_LOS` and `IDS_AIRSTRIKE_HELP` variants
  (controlGui.cpp:1760–1766).
- An artillery object is created at the point, owned by the player's team
  and commander.

**Timeline**, from `NominalTimeToImpact` = 7.0 s in both `artbig.fit` and
`artsml.fit`:
- t = 0 s: the target marker (`airstrikemarker`) appears with a countdown.
  A GUI click sound plays if the point is in LOS.
- 5.5 s before impact: the incoming-air-strike sound plays
  (artlry.cpp:1034).
- 2.5 s before impact: the bomber fly-over model and contrail start
  (artlry.cpp:938).
- 0 s: the blast effect plays. The object becomes "tangible" for **one
  update**, which applies damage once (artlry.cpp:1043–1088).

**Damage** (`ArtilleryType::handleCollision`, artlry.cpp:527–622;
`handleStaticCollision`, artlry.cpp:670–750):
- **Candidates.** Every existing object in the 3×3 terrain blocks around the
  impact is tested. An object is hit when the 2-D distance between centres
  is less than *(strike `ExtentRadius` + object `ExtentRadius`)*, in world
  units (Collsn.cpp:589–625):
  - big strike: 187 wu ≈ 37 m, plus the target's own extent;
  - small strike: 150 wu ≈ 30 m, plus the target's own extent.
- **Major/minor.** `range` is the 2-D centre distance in metres.
  - `range` ≤ `nominalMajorRange` (25 m): **major** hits.
  - otherwise: **minor** hits.

  | Strike | Damage per hit | Major hits | Minor hits | Major total | Minor total |
  |---|---|---|---|---|---|
  | Big (`artbig.fit`) | 15 | 3 | 2 | 45 | 30 |
  | Small (`artsml.fit`) | 8 | 2 | 1 | 16 | 8 |

- Each hit is a separate shot with its own hit-location roll:
  - normally the **artillery** hit table;
  - when `range` ≤ `MinArtilleryHeadRange` the **death-from-above** table,
    which favours the head. That FIT key is absent, so the code default of
    5 m applies (artlry.cpp:517, 605).
  - Entry angle: the target's facing relative to the impact point.
  - The tables themselves are in `combat-rules.md`.
- **Gates and turrets** are hit only if (range − their "little extent") ≤
  25 m (artlry.cpp:553–582).
- **Immune:** a BattleMech-class unit with air movement that is not shut
  down, which in practice means the **scout copter** in flight
  (artlry.cpp:585–592).
- **No team check.** Strikes damage friendly units and buildings too.
- **Mines:** every laid mine (state 1) within ±4 cells (a 9×9 cell square)
  of the impact detonates with mine splash damage (0) and is marked spent
  (artlry.cpp:686–718).

**Quirks and ambiguities:**
- `nominalMinorRange` = 80 m is read but **never tested**. The real outer
  limit is the extent-radius sum: about 37 m plus the target extent for the
  big strike. A minor hit therefore lands between 25 m and that limit.
  Recommend keeping the extent-sum rule, since it is what shipped.
- `NumExplosions`, `ExplosionDelay*`, `ExplosionOffset*`,
  `ExplosionsPerExplosion` and `ExplosionRandomOffset*` are loaded
  (artlry.cpp:470–514) and **never used**. Damage is a single centred
  check. Use the offsets only to stagger visual blasts, if at all.
  - `artbig.fit` lists 13 offsets but `NumExplosions` = 12, so the last is
    ignored.
- The FIT comment calls `ExtentRadius` "meters", but the collision test
  compares it with world-unit distances. Treat it as world units.
- Frame-rate-dependent "one update of tangibility" is effectively one damage
  pulse. Implement it as a single pulse at impact.

### 3.2 Sensor probe (2000 RP)

- **Placement:** any point, no LOS needed. It is created like a strike
  (`ARTILLERY_SENSOR`, object 250 `artsns.fit`).
- **Arrival:** immediate. `NominalTimeToImpact` = 0 and there is no damage.
  The landing effect plays at once. A water cell selects the water variant
  of the effect (artlry.cpp:775–780).
- **Effect:** the probe creates a team sensor for the player's team
  (artlry.cpp:820–846, 1302–1316).
  - It starts at 800 m (`NominalSensorRange`).
  - It **shrinks linearly to 0 over 120 s** (`NominalSensorTime`):
    range = 800 m × time left ÷ 120 (artlry.cpp:1097–1108).
  - At 0 the sensor is removed and the object deleted (artlry.cpp:1110–1118).
  - The sensor has **no LOS capability** (`setLOSCapability(false)`). It
    gives sensor **contacts** (radar blips) in its radius but does not
    reveal terrain or give visual line of sight.
- No limit on the number of simultaneous probes in single player.

### 3.3 VTOL delivery (repair truck, scout copter, minelayer, artillery piece)

Common to the four vehicle powers (`beginVtol`, missiongui.cpp:4232–4451;
`updateVTol`, :905–990):
1. On a valid click, a **VTOL** model plays its drop-off animation at the
   clicked point, with a dust cloud and a per-type radio/support sample.
2. At animation **frame 145**, the vehicle is created at the clicked point
   on the player's team and commander:
   - via `BringInReinforcement`, missiongui.cpp:4141–4200;
   - with brain `pbrain`, not capturable, and the player's colours.
   - An air unit (the scout copter) is created **shut down**.
3. At **frame 300** the VTOL is removed and the new unit is ordered to
   power up. The tab is released.

The drop-off ASE is 300 frames at 30 fps (`VTOL_Dropoff.ase`
`SCENE_FRAMESPEED 30`). That gives:
- **delivery about 4.8 s** after the click;
- **unit active and tab free about 10 s** after the click.

**Ambiguity:** the playback rate is the appearance's frame rate, which we
assume equals the ASE's 30 fps.

The delivered unit is an ordinary player unit:
- it takes a force-bar icon and counts toward the 16-unit cap;
- it can be killed;
- it is **not** carried into logistics;
- it can be called again for another payment.

### 3.4 Repair truck (6000 RP)

Unit `RepairTruck.fit`:
- 20 t, max speed 15;
- 12 armour on each of its 5 facings, 1 internal structure each;
- `RefitPoints` = 500.

When a type has `RefitPoints > 0`, that number becomes the max and current
armour of the **turret** location. That armour **is the repair pool**
(gvehicl.cpp:1241–1247).

**Order:**
- Select the truck. The REPAIR command shows pressed.
- Click a friendly, non-disabled mover that `needsRefit`, or the mech it is
  already servicing (`canRepair`, missiongui.cpp:4480–4513).
  - `needsRefit` means it is a BattleMech with no current refit partner and
    with any armour or internal-structure deficit, ignoring destroyed arms;
    the source then also checks ammo (mover.cpp:5992–6010).
- This issues `TACTICAL_ORDER_REFIT` (missiongui.cpp:4515–4530).
- **Only BattleMechs can be repaired** (tacordr.cpp:1049).

**Sequence** (tacordr.cpp:1047–1078 setup, 1429–1533 execution):
1. The truck drives to the mech's cell and pairs with it (refit buddies).
   If it is not within `RefitRange` = 30 m when it stops, it re-paths to the
   next cell diagonally.
2. The mech is ordered to **power down**. After **3 s** the next stage
   starts.
3. Every `RefitTime` = **1.0 s** a refit cycle runs (§3.4.1), and the points
   used come off the truck's pool.
4. When the mech is fully repaired, it powers up, the pair is released, and
   the mech gets the radio `REFIT_DONE` and Betty `REPAIR_COMPLETE`.
5. When the pool reaches 0:
   - the mech is powered back up;
   - Betty `REPAIR_GONE` plays;
   - the truck is **disabled** (`POWER_USED_UP`, tacordr.cpp:1515–1516).
     It is a spent hulk.
6. The order ends early if either partner loses its pairing, for example on
   a new order or a death (tacordr.cpp:1431–1432).

#### 3.4.1 Refit cycle (`Mover::refit`, mover.cpp:6585–6758)

Inputs:
- `RefitAmount` = 30, so `areaMax` = 30 ÷ 3 = **10 points**;
- cost factors `RefitVehicleArmorCost` = `RefitVehicleInternalCost` =
  `RefitVehiclePointsToAmmo` = 1.0;
- `pointsAvailable` = the truck's remaining pool.

Each cycle:
1. Count the deficit slots: for each armour location with an armour deficit
   +1, and +1 more if it also has an internal-structure deficit. Skip
   destroyed arms. Call the total *R*.
2. Each deficit slot gets up to 10 ÷ *R* points, converted 1:1 to armour or
   internal structure and capped at that slot's max. So armour and internal
   structure together restore **about 10 points per second**, spread evenly.
   - Restored internal structure recomputes the location's damage state:
     ≤ 0 destroyed, ≤ 50 % partial, else none.
   - Leg and centre-torso state are recomputed.
   - **Destroyed arms are never rebuilt.**
3. Count the ammo types below max, *A*. Each gets up to 10 ÷ *A* points,
   times 1.0, times that ammo's rounds per ton, capped at max. In effect it
   is near-instant. With unlimited ammo on, nothing needs it.
4. Points used are rounded to the nearest 0.25, with a minimum of 0.25 if
   any were used, and come off the pool.
5. The mech is done when nothing is left below max.

**Quirk:** the "three pools" comment suggests 10 each for armour, internal
structure and ammo. In fact armour and internal structure **share** one
10-point budget, and the third third is never spent. Keep that rate.

**Ambiguity:** `RefitBayArmorCost` (2.0), `RefitBayInternalCost` (1.0) and
`RefitBayAmmoCost` (0.2) are loaded from gamesys but **never used**. Bays
use the vehicle factors (§3.7).

### 3.5 Minelayer (4000 RP)

Unit `Minelayer.fit`:
- 30 t, max speed 15;
- 15 armour per side;
- `MineLayer` = **160**, which becomes the turret's armour: the **mine
  stock** (gvehicl.cpp:1253–1258).

**Order:** select the minelayer and the LAYMINES command (ControlGui
`getMines`), then give a move. The move carries `MOVE_MODE_MINELAYING`
(missiongui.cpp:3156–3157). While laying, its throttle is capped at
`MineLayThrottle` = 100 (gvehicl.cpp:2047–2049).

**Laying** (gvehicl.cpp:3605–3637), each update while in minelaying mode and
in a cell different from the last mined one:
1. Accumulate time.
2. Once more than `MineWaitTime` = **0.5 s** has accumulated, mine the
   **current cell** (map mine state 1, visible to all) and reset the timer.
3. Each mine deals **1 damage to the minelayer's own turret**, which uses up
   one unit of stock.

The result is about one mine per cell crossed, at most one per 0.5 s.

**Mine effect:**
- A ground vehicle over **35 t** entering a mined cell takes
  `BaseDamage` = **12**, rolled on the mine hit table. The mine is then
  spent (state 2) and the vehicle re-paths (gvehicl.cpp:1399–1412).
- Minelayers and mine-sweepers are exempt.
- There is **no team check**: own mines hurt own heavy vehicles.
- Weapons and strikes that hit a mined cell detonate it (weaponbolt.cpp:826,
  artlry.cpp:686).

**Ambiguities:**
- **Mechs.** *(Corrected 2026-10-23.)* `BattleMech::mineCheck`
  (mech.cpp:3731-3778, called each update, mech.cpp:5973) sets off a laid mine
  under a mech **over 35 t** that is not jumping: 12 damage in the bottom
  section from a random side, and the mine is spent. (An earlier text search
  missed it because mech.cpp reads as binary to grep.) This matches the
  walkthroughs: light mechs walk through minefields (CB, SOE on mc2_07). The
  pathfinder's `avoidMines` local is set but never read (MCLib/Move.cpp:4391),
  so nobody avoids mines.
- **Running out.** When the stock reaches 0, the 1-point self-hits move on
  to the turret's internal structure. The code has no explicit "out of
  mines" stop.

### 3.6 Salvage craft / Karnov (10000 RP)

This is **the route by which an enemy mech joins the player's force during
a mission**. The ground "recover" vehicle order is dead code: it stops with
"RECOVER TACORDER NO LONGER VALID" (tacordr.cpp:1824). `MobileHQ.fit`
(`RecoverPoints` 1000) is never spawned in single player.

Sequence (missiongui.cpp:992–1118, 4300–4410):
1. On a valid click on a disabled, not destroyed BattleMech, a **Karnov**
   model appears over the target's cockpit node and plays its landing
   animation:
   - `KarnovDropoff.ase`, frames 31–175 at 30 fps, **about 4.8 s**;
   - with a dust cloud and the salvage-craft sound.
2. On reaching hover:
   - the recovery beam effect starts;
   - the "Karnov deploy" sample plays;
   - a timer starts.
3. After `RecoverTime` = **5 s** of hover, if the mech still exists and is
   not destroyed:
   1. Run `Mover::recover` until it reports done (mover.cpp:6767–6900).
      - It restores **internal structure to max** on every location except
        destroyed arms. The 100000-point budget makes it effectively
        complete.
      - It resets every component to full health and un-disabled.
      - It clears critical-hit marks.
   2. If the mech was disabled, set it to **shut down**, un-break its
      sensors, and clear its exploding/death timer.
   3. **Trade** it to the player's team and commander with brain `pbrain`
      and pilot `getBestPilot` (LogisticsData.cpp:906–956):
      - consider every available, undead pilot not in use on the map and
        not assigned to an inventory mech;
      - sort by rank, then gunnery, then piloting. The tonnage argument is
        unused.
      - Mark the chosen pilot used.
   4. Order the mech to **power up**.
4. Then the Karnov lifts off (`KarnovLiftoff.ase`, frames 88–200, **about
   3.7 s**) and is removed, and the tab is released. The whole call takes
   **about 13–14 s**.
5. If the target is destroyed before step 3 (the Karnov is not
   invulnerable cover), the Karnov lifts off with nothing. The balance gets
   back a hard-coded **10000** (missiongui.cpp:1104–1113).

**Quirks:**
- **Armour is not restored**, only internal structure and components. A
  recovered mech arrives with whatever armour it had.
  - Recommend faithful behaviour, which makes the repair truck the
    follow-up.
- The team is not checked, so the player can re-salvage their **own**
  disabled mech. It gets a **new** pilot from the roster, not its original
  ejected one.
- The refund is the literal 10000, not the button cost. Recommend refunding
  the cost.

Recovered mechs count as player units for objectives and losses. They carry
into the post-mission inventory if alive at the end (§1.5). For
post-mission salvage of wrecks, see `capture-and-objectives.md`.

### 3.7 Repair bays (map buildings, free)

These are not a purchase, but they are the other in-mission repair route.
The bay type is `LiaoRepairBay.fit` (object 33):
- "RepairBay", `CanRefit` = t, `MechBay` = true, `DmgLevel` = 360;
- capturable (see `capture-and-objectives.md` §A1).

Bays appear in the converted map objects of mc2_05, 06, 07, 11, 13, 14, 15,
16, 17, 18, 19, 20, 22, 23 and 24. Some maps have 2–3.

**Order:** select mechs that `needsRefit` and right-click a **friendly**
bay. This issues `TACTICAL_ORDER_GETFIXED` (missiongui.cpp:1417, 4532–4566).
Mech bays take mechs only; vehicles would need a non-mech bay.

**Sequence** (tacordr.cpp:1081–1100 setup, 1537–1622 execution):
1. Move onto the bay. Only one unit at a time: the bay's `refitBuddyWID`
   must be free.
2. Power down. After **3 s**, the repair-bay sound plays.
3. Every **1 s**, run the same refit cycle as §3.4.1, with vehicle cost
   factors.
4. When done, start up and walk one tile off, diagonally.

**The bay's pool is its own remaining hit points:** `DmgLevel − damage`
(bldng.h:372). The points used are applied as **damage to the bay**
(bldng.cpp:1649–1660). A bay therefore repairs about 360 points in total and
then is destroyed. Betty `REPAIR_GONE` plays at that point.

### 3.8 Scout copter (2000 RP)

Unit `ScoutCopter.fit` with profile `scoutcopter.csv`:
- a BattleMech-class object with `MoveType` = 1 (air) and `LOSFactor` 1.2;
- 5 t, top speed 31, 40 armour in total, no weapons;
- standard sensors with range 350.

It has no special support code beyond what air movement gives it:
- it can fly over impassable terrain (mover.cpp:4260);
- it is immune to air strikes while flying (§3.1);
- it cannot capture (warrior.cpp:7577);
- it is not counted as a mech for objectives or logistics (Objective.cpp
  :993, LogisticsData.cpp:1347).

Its value is fast, mobile **line of sight**. That is needed for vehicle
drops (§2.3), for full-strength air strikes (§3.1), and for indirect fire
(§3.9). It arrives shut down and powers up when the VTOL leaves.

### 3.8.1 In the remake (2026-10-23, I95, I96)

- **Repair bays** (`SimSupport.order_bay_repair`): right-click a friendly bay with a damaged
  mech selected. The sequence above runs; the bay's pool is `DmgLevel − damage`, burnt as damage.
  A neutral or enemy bay must be captured first. The bot (autoplay) uses it.
- **Artillery piece:** delivered like the repair truck (`data/vehicles/guardtower.json`, pilot
  `PMWGuardTower`). With no brain it fires at the nearest armed enemy in reach, on its own or a
  team mate's sight. **Suppression fire** (2026-10-24): the command panel's Suppression fire
  button (the original's GUARDTOWER, shown with an immobile unit selected) then a right-click on
  the ground sets `suppressionFire` and an attack point from where it stands (doGuardTower,
  missiongui.cpp:5480-5508); it keeps shelling until the button is un-pressed, which clears it
  on every immobile unit (controlGui.cpp:2205-2228), or a Stop (TACTICAL_ORDER_WAIT,
  mover.cpp:3166-3168).
- **Scout copter** (2000 RP, 2026-10-24): `ScoutCopter.fit` on the `scoutcopter` chassis, pilot
  `PMWScout`, created shut down and powered up as the VTOL leaves. The copters (and the missions'
  own Light/Medium/Heavy copters) are air movers: `[MechProfile] MoveType 1` (mech.cpp:675,
  converted as `move_type` in `data/chassis/*.json`). They fly straight over anything
  (mover.cpp:4260), set off no mines (mech.cpp:3739-3741), are immune to strikes in flight
  (artlry.cpp:585-592), can't capture (warrior.cpp:7577) and don't count for "move all surviving
  'Mechs" (Objective.cpp:993, 1017). LOSFactor 1.2. Its sensor is the chassis' Standard Sensors
  (1 m, so visual only); the "range 350" in 3.8 is not in the converted data.
- **Minelayer:** delivered the same way (`minelayer.json`, pilot `PMWMinelayer`). Select it,
  press the command panel's **Lay mines** button (the original's LAYMINES, controlGui.cpp:1110-1117)
  and right-click: its moves lay mines (`SimSupport.order_lay_mines`). M is the original's
  medium-range key again.
- The support row now carries the original's seven tiles in its order: air strike, artillery
  piece, sensor probe, repair truck, scout copter, minelayer, salvage craft.

### 3.9 Artillery piece (8000 RP)

Unit `GuardTower.fit` (object 415, "ArtilleryPiece"):
- 40 t, **immobile** (MaxVelocity 0, which is what makes `isGuardTower`
  true);
- armour front 30 and 22 elsewhere;
- on death, a 50-radius, 5-damage explosion (`ExplosionRadius`,
  `ExplosionDamage`);
- one **Long Tom** cannon (component 160) with ammo 227. Component 160:
  - damage 15, recycle 7.14 s, heat 20, long range;
  - artillery flag set;
  - listed in gamesys `IndirectFireWeaponComponentIndex` and
    `AreaEffectWeaponComponentIndex`, so it fires without its own LOS when
    the team has LOS (warrior.cpp:3404). The area-effect rules belong in
    `combat-rules.md`.

**Orders:**
- Normal attack orders work on targets in range.
- **Suppression fire:** with the piece selected, press the GUARDTOWER
  command and click ground (`doGuardTower`, missiongui.cpp:5481–5508).
  - This sets `suppressionFire` and issues attack-point.
  - With suppression on, the point keeps being shelled. Without it, an
    attack-point order clears after one shot (gvehicl.cpp:4841, 5188,
    5225).
  - A Wait order clears suppression (mover.cpp:3166–3168). Un-pressing the
    button clears it on all the player's immobile units
    (controlGui.cpp:2205–2228).

**Default:** `ArtilleryPieceEnabledDefault` defaults to **off** when the key
is missing (§2.2). Every campaign FIT sets it TRUE.

---

## 4. Non-RP consumables

Single player has no per-mission strike allowance, no charges and no
cooldown timers. All the "consumables" are pools carried on units or
buildings:

| Consumable | Pool | Spent by |
|---|---|---|
| Repair truck refit points | 500, as turret armour | refit cycles; the truck is disabled at 0 |
| Minelayer mines | 160, as turret armour | 1 per mine laid |
| Repair bay refit points | the bay's remaining HP (360) | refit cycles; the bay is destroyed at 0 |
| Mine-sweeper charges | its front armour | 1 per mine swept; it stops sweeping at 0 (gvehicl.cpp:1363–1383). No sweeper is buyable. |

Multiplayer tracks `numAirStrikesUsed` and `numSensorProbesUsed` for stats
only (artlry.cpp:144–148). In multiplayer the server also caps a commander
at **10 live strikes** (artlry.cpp:104–117). Single player has no cap.

---

## 5. AI use

- **Aerospace spotter** (`AeroSpotter.fit`, object 524,
  `AeroSpaceSpotter` = TRUE). This is the **only working AI strike source**.
  It is placed on team 1 in mc2_15, 18, 19 (×2) and 22 (×2).
  - While its current target is within **120 m** (the top of medium range,
    `WeaponRanges Medium`) and in its own LOS, a timer accumulates.
  - Every `StrikeWaitTime` = **10 s** it calls a **big** strike on the
    target's position, with `StrikeTimeToImpact` = **4 s**
    (gvehicl.cpp:3640–3664).
  - The timer is not reset when the target leaves range.
  - The strike damages anything in the radius, including the spotter's own
    side (§3.1).
- **`callStrike` / `callStrikeEx` ABL natives** (ablmc2.cpp:3990–4103).
  They document type numbers 248/249/250 (artillery) and 507/508/509 (air),
  then pass those numbers **straight** to `IfaceCallStrike`. That function
  accepts only the enum values 0, 1 and 2 (small, large, sensor) and
  **returns at once** for anything else (artlry.cpp:167–168).
  - **Both natives are therefore no-ops in the shipped build.** This
    corrects `abl-natives.md` §94, which reads the documented IDs as
    working.
  - Their only campaign call is commented out anyway.
  - If revived:
    - a delay under 2 s means the full 7 s (artlry.cpp:139–140);
    - a clan strike without LOS downgrades to small;
    - a non-clan, non-player call would index commander −1.
  - Recommend implementing `callStrikeEx` as a no-op, or with the enum
    mapping, behind a flag.
- **Enemy support vehicles** appear as ordinary placed units:
  - minelayers ×2 in mc2_07, with brains `mc2_07_E1_NCV1_Minelayer1/2.abl`;
  - a repair truck in mc2_16;
  - ordnance trucks (capture targets worth 4000 RP) in mc2_03, 05, 16
    and 23.

  The AI can issue REFIT and GETFIXED through ABL (`getFixed`,
  `abl-natives.md` §93). The AI never buys support with RP.

---

## 6. Numbers

| Quantity | Value | Source |
|---|---|---|
| Cost: air strike | 7000 | controlGui.cpp:82 |
| Cost: artillery piece (`GUARD_TOWER`) | 8000 | controlGui.cpp:83 |
| Cost: sensor probe | 2000 | controlGui.cpp:84 |
| Cost: repair truck | 6000 | controlGui.cpp:85 |
| Cost: scout copter | 2000 | controlGui.cpp:86 |
| Cost: minelayer | 4000 | controlGui.cpp:87 |
| Cost: salvage craft | 10000 | controlGui.cpp:88 |
| Salvage-fail refund | 10000 (literal) | missiongui.cpp:1113 |
| Vehicle IDs repair/scout/minelayer/salvage/artillery | 182 / 393 / 120 / 147 / 415 | controlGui.cpp:101–108 |
| Unit cap for vehicle powers | 16 icons | ForceGroupBar.h:21; controlGui.cpp:1813–1835 |
| RP building / ordnance truck payout | 10000 / 4000 | RPBuilding.fit; OrdnanceTruck.fit |
| RP capture payout gate | turn > 10 | bldng.cpp:959; gvehicl.cpp:3139 |
| VTOL drop frame / end frame | 145 / 300 (30 fps ⇒ ≈4.8 s / 10 s) | missiongui.cpp:918, 941; VTOL_Dropoff.ase |
| Karnov land / lift-off frames | 31–175 / 88–200 (≈4.8 s / 3.7 s) | KarnovDropoff.ase; KarnovLiftoff.ase |
| `RecoverTime` (Karnov hover before trade) | 5.0 s | gamesys.fit:484; missiongui.cpp:1032 |
| Strike time to impact (player) | 7.0 s | artbig.fit:19; artsml.fit:19; artlry.cpp:766–767 |
| Minimum explicit time to impact | < 2 s ⇒ full 7 s | artlry.cpp:139–140 |
| Incoming sound / bomber start | 5.5 s / 2.5 s before impact | artlry.cpp:1034, 938 |
| Big strike: damage × hits major/minor | 15 × 3 / 15 × 2 | artbig.fit:20–24 |
| Small strike: damage × hits major/minor | 8 × 2 / 8 × 1 | artsml.fit:20–24 |
| Major range | 25 m | artbig.fit:21; artlry.cpp:594 |
| Minor range (unused) | 80 m | artbig.fit:23 |
| Strike extent radius big / small | 187 / 150 wu (≈37 / 30 m) | artbig.fit; artsml.fit; Collsn.cpp:601–608 |
| Head-table radius | 5 m (code default) | artlry.cpp:517, 605 |
| Mines detonated by a strike | ±4 cells (9×9) | artlry.cpp:686–691 |
| LOS-less strike becomes small | yes | artlry.cpp:185, 213 |
| Sensor probe range / duration | 800 m, linear to 0 over 120 s | artsns.fit:27–28; artlry.cpp:1101 |
| Sensor probe LOS capability | none (contacts only) | artlry.cpp:1315 |
| Refit range / cycle / budget | 30 m / 1.0 s / 30 (⇒ 10 armour+IS, 10 ammo) | gamesys.fit:473–475; mover.cpp:6592 |
| Refit cost factors (vehicle) | 1.0 / 1.0 / 1.0 | gamesys.fit:476–478 |
| Refit bay factors (unused) | 2.0 / 1.0 / 0.2 | gamesys.fit:479–481 |
| Power-down before refit | 3 s | tacordr.cpp:1471, 1556 |
| Repair truck pool | 500 | RepairTruck.fit `RefitPoints` |
| Repair bay pool | `DmgLevel` 360 − damage | LiaoRepairBay.fit; bldng.h:372 |
| Minelayer stock | 160 | Minelayer.fit `MineLayer` |
| Mine dwell time per cell | 0.5 s | gamesys.fit:827; gvehicl.cpp:3614 |
| Mine damage / splash / splash range | 12 / 0 / 15 m | gamesys.fit:821–823 |
| Mine trigger weight (vehicles) | > 35 t | gvehicl.cpp:1403 |
| Minelay / minesweep throttle | 100 / 50 | gamesys.fit:825–826 |
| Spotter strike interval / impact delay / range | 10 s / 4 s / 120 m | gamesys.fit:828, 831; gvehicl.cpp:3654–3661 |
| MP live-strike cap | 10 per commander | artlry.cpp:113 |

---

## 7. Systems this needs

- **Support tab state machine:**
  - press, charge, place or cancel;
  - one delivery at a time;
  - disable rules per §2.2.
- **Team line of sight queries** at a point. These are used for vehicle
  drops, salvage and the air-strike downgrade.
- **Strike object:** a timed area pulse with the extent-sum radius, a
  major/minor split, per-hit location rolls and friendly fire. Also the
  mine detonation in a radius.
- **Team sensor with a shrinking radius** that gives contacts but no LOS.
- **Reinforcement spawn** of vehicles and an air "mech" mid-mission, with a
  scripted VTOL/Karnov timeline. Air movement (fly over impassable terrain)
  is needed for the scout copter.
- **Refit pairing order:** move, power down, periodic refit cycles, pool
  burn, disable when empty. It is shared by trucks and bays. Bays use
  building HP as the pool.
- **Mid-mission mover trade** between teams, with pilot assignment from the
  logistics roster and a partial repair (internal structure and components,
  not armour).
- **Mine layer on the map grid:** per-cell mine state, laying and
  vehicle-weight triggers. The mech interaction is still open (§3.5).
- **Suppression-fire flag** on immobile units, plus the indirect-fire and
  area-effect weapon list (Long Tom).
- **Not converted yet:** `game/data/vehicles/` has `repairtruck`,
  `minelayer`, `mobilehq` and `aerospotter`. It lacks:
  - `GuardTower` (the artillery piece);
  - `ScoutCopter` with `scoutcopter.csv`;
  - the three artillery types `artbig`, `artsml` and `artsns`;
  - the `PMW*` support pilots in `Data/Missions/Warriors/`.

---

## 8. Open questions

1. Do mechs trigger or avoid player-laid mines (§3.5)? This needs a mines
   spec covering `MCLib/Move.cpp` mine cells and any trigger outside
   `gvehicl.cpp`.
2. Is the VTOL/Karnov playback rate really 30 fps (§3.3)? Check against the
   appearance's own frame-rate setting in MCLib.
3. The repair truck's `needsRefit` also has an ammo branch (mover.cpp:6008
   onward). With unlimited ammo it never fires. Confirm before relying on
   it.
4. Minelayer behaviour when its 160 stock runs out (§3.5).
