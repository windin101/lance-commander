# ABL natives (game functions called by the original scripts)

Behavioural spec for the "native" functions that MechCommander 2's ABL scripts
call, written so they can be reimplemented against our own simulation
(`game/scripts/sim/`) and registered on the interpreter
(`game/scripts/abl/abl_runtime.gd`, `register_native`).

Everything here was derived from reading the original source
(`reference/mc2-source/Source/`), chiefly `Code/ablmc2.cpp` (implementations
and the registration table in `initABL`), `Code/warrior.cpp/.h`,
`Code/tacordr.cpp/.h`, `Code/unitdesg.h`, `Code/objmgr.cpp`,
`Code/mission.cpp`, `Code/Contact.cpp`, `Code/team.cpp`, `Code/group.cpp`,
`Code/trigger.cpp`, `MCLib/Move.h` and `MCLib/Ablxstmt.cpp`, plus the ABL
libraries in `game/data/abl/` (`corebrain.abx`, `miscfunc.abx`,
`orders.abx`, `*.abi`). No code was copied. Where the original is buggy or
unclear this says so; **"Quirk"** marks behaviour that is faithful but probably
unintended, and the recommendation for our build sits next to it.

## 0. Conventions

**Units.**
- Positions passed to and from ABL are original **world units**: x east,
  y north, z elevation. This is the same space as the mission FIT's
  `PositionX/Y`, the patrol points hard-coded in the brains, and our mission
  JSON.
- Every distance a native returns or takes is **metres**, and is 2-D (z is
  ignored): metres = world units × 0.2.
- A map cell is 128/3 world units (≈ 8.53 m). There are 3 cells per terrain
  vertex.
- World to cell is `col = trunc((x − left) × 3/128)` and
  `row = trunc((top − y) × 3/128)`. The map is centred on the origin, so
  `left = −side/2` and `top = +side/2`.

**ABL angles** (the `ANGLE_*` constants):
- 0 = south, 90 = east, 180 = north, −90 = west.
- Positive angles turn counter-clockwise.
- `combat-rules.md` measures facing clockwise from north. To convert, use
  `ours = 180 − abl` (mod 360).

**Registration strings.** Each native is registered with a parameter string
and a return string, e.g. `"iRb" → "i"`. The codes are:

| Code | Meaning |
|---|---|
| `i` | integer |
| `r` | real |
| `b` | boolean |
| `C` | string (char array) |
| `I` | integer array, by reference |
| `R` | real array, by reference |
| `*` | any numeric type, coerced |
| `?` | anything |

A missing return string means the native returns nothing.

**Argument order.** The implementation pops arguments in declaration order,
so the first ABL argument is the first value it consumes. When this spec says
`f(a, b)`, that is the order the script writes them.

**Order-flagged natives.** The registration table marks some natives as
*orders*:
- `coremoveto`, `coremovetoobject`, `corepower`, `coreattack`, `corecapture`,
  `corescan`, `corecontrol`, `coreeject`
- their `new…` aliases (`newmoveto`, `newmovetoobject`, `newpower`,
  `newattack`, `newcapture`, `newscan`, `newcontrol`)

Section 2.7 explains what that changes. All other natives, including the
`order…` family (`ordermoveto`, `orderattackobject`, …), are ordinary
functions.

**Context.** Several natives act on implicit "current" objects: the current
object, current warrior, current contact and current alarm (§2.3).

---

## 1. Object IDs

ABL refers to every game object by an integer **part ID**. One number space
covers single objects, units (squads or lances), teams and commanders. Each
native decides how to treat a number by which range it falls in.

### 1.1 Special values

| Value | Meaning |
|---|---|
| `-1` | **The current object**: the mover whose brain is running (`CUR_OBJECT_ID = -1` in the .abi files). In the **mission script** there is no current object, so `-1` resolves to nothing. |
| `0` | **No object.** It never resolves to anything. Some natives give it a special meaning: `coreAttack(0, …)`, `coreMoveToObject(0, …)` and `coreCapture/Scan/Control(0, …)` mean "use the last scan result, or scan now" (§2.6). `setTarget(x, 0)` clears the target. `orderAttackObject(0, …)` clears attack orders. |
| *(no "current target" alias)* | There is **no** ID that means "my current target". Scripts fetch it with `getTarget(-1)`. |

### 1.2 Numeric ranges (from `unitdesg.h`)

| Range | What it is | How it resolves |
|---|---|---|
| 1 – 511 | "unit" IDs (`MIN/MAX_UNIT_PART_ID`); natives that accept groups test this range first | see 1.4 |
| 492 – 499 | commander IDs (`OBJ_ID_FIRST/LAST_COMMANDER`) | group natives **abort with a fatal error** on these; nothing in the campaign uses them |
| 500 – 508 (511) | **team** IDs: team index = id − 500 (`MIN_TEAM_PART_ID`) | the team's roster of movers |
| 512 – 4095 | **mover** part IDs (`MIN/MAX_MOVER_PART_ID`) | single mover |
| ⊂ 2050 – 3550 | movers created at runtime (reinforcements, `newMech`/`newVehicle`), allocated sequentially from 2050 | single mover |
| ≤ 4095, counting down | marines/infantry spawned from buildings: `4095 − n` | single mover |
| 4096 – … | **terrain objects**: buildings, turrets, gates, trees, walls | single object |
| 512000 – 521999 | train cars (`MIN_TRAIN_PART_ID`); unimplemented in the original (fatal) | n/a |
| 525000 – 525999 | camera drones | n/a |

Team indices in single player:
- 0 = player (`PLAYER_FORCE`/`OBJ_TEAM_1` = 500).
- 1 = enemy/Clan (`CLAN_FORCE` = 501).
- 2 = allied (`ALLIED_FORCE` = 502).

On load, single player folds every part whose FIT `TeamID` is 2 into team 0.
So allies are on team 0, under a different commander.

### 1.3 Movers: 512 + commander·192 + group·12 + mate

For each commander *c*, the mission FIT has blocks `[Commander<c>Group:<g>]`,
numbered g = 0, 1, … Each block holds `Mates = p0,…,p11`: twelve FIT part
numbers, where 0 means an empty slot. The mover built from `[Part<p>]` in mate
slot *m* gets:

```
partId = 512 + c × (16 × 12) + g × 12 + m        // 16 groups × 12 mates per commander
```

Examples:
- `mc2_01`, Part1 (Commander0Group:0, slot 0) = 512.
- Part4 (Commander1Group:0, slot 0) = 704.
- Part16 (Commander1Group:1, slot 0) = 716.
- `mc2_01` tests `objectStatus(708)`, which is Commander1Group:0, slot 4
  (Part8).

A mover that appears in no group never gets an ID. It keeps 0 and cannot be
addressed. Removed movers have their ID reset to 0.

**The FIT part number is not the part ID.** Neither is the `[Warrior<n>]`
index. Our loader must compute the ID from the group blocks.

**Quirk: the .abi constants disagree with the code.** `misconst.abi` and
`unitconst.abi` were written for **32** groups per commander. They use
`MAX_MOVER_GROUPS = 32`, `CLAN_VEHICLE0_STAR0 = 896` and
`ALLIED_VEHICLE0_LANCE0 = 1280`, and `miscfunc.abx: getVehicleID/VehicleID`
uses the same layout. The shipped C++ uses **16**, so in the real game those
constants point at the wrong movers. Only `PLAYER_VEHICLE*_LANCE0` (512, 513,
used by `mc2_08`) is used in campaign scripts, and it is correct either way.
Recommendation: implement the C++ formula (16) and treat the .abi
per-vehicle constants as legacy.

### 1.4 Unit IDs (1 – 511 outside the team and commander ranges)

These IDs mean different things in different natives. Copy the distinction
exactly:

1. **Squad match (the default).** Most group-aware natives collect every
   mover whose **squad ID** equals the number:
   - `objectStatus`, `inArea`, `distanceToObject/Position`, `setTarget`,
     `getUnitMates`, `isCaptured`, `getObjectActive`, `objectExists`, and
     others.
   - The squad ID is the FIT part's `SquadNum` field. In `mc2_01`, Part1 has
     `SquadNum = 2` and Part4 has `SquadNum = 8`.
   - Mission scripts use literal squad numbers, e.g. `getUnitMates(101, …)`
     and `objectstatus(120)`.
   - IDs 500–508 instead return the team roster.
2. **Commander-group lookup (only `objectStatusCount`).** The ID is decoded
   as a commander group:

   | ID range | Commander and group |
   |---|---|
   | 16 – 31 | commander 0 (player), group id − 16 (`PlayerLance0` = 16) |
   | 165 – 180 | commander 1, group id − 165 (`ClanStar0`) |
   | 329 – 344 | commander 2, group id − 329 (`AlliedLance0`) |
   | 500 – 508 | team |

   Any other unit ID does nothing.

   **Quirk:** `misconst.abi` defines `PLAYER_LANCE0 = 1`, not 16. So
   `isAlive(PLAYER_LANCE0)` etc. in `miscfunc.abx` count nothing.
3. **"Treat as unsupported."** Several natives return a neutral value for any
   1–511 ID: `getTarget` → 0, `getChallenger` → 0, `getTacOrder` → 0,
   `orderMoveToObject` → 1, `orderAttackObject` → 1 (no order),
   `objectCommander` → −1.

`getUnitMates(objectId)` with a **mover** ID returns that mover's
**commander group** (§1.3), not its squad.

### 1.5 Terrain objects (buildings, turrets, gates, trees)

```
partId = 4096 + cellRow × 720 + cellCol        // 720 = MAX_MAP_CELL_WIDTH
```

- `cellRow` and `cellCol` are the map cell containing the object's position,
  using the world-to-cell rule in §0. For a building this is its placement
  point, not every cell of its footprint.
- Decode with `row = (id − 4096) div 720` and `col = (id − 4096) mod 720`.
  Example: `mc2_01` uses 76991 → row 101, col 175. The native
  `getterrainobjectpartid(row, col)` returns exactly this value.
- The comment in `unitdesg.h` describing a block/vertex/item formula, and the
  ceiling 464895, are obsolete. The 720 formula is the one in use, and a
  large map can exceed 464895.
- **Collisions:** two terrain objects in the same cell, such as a tree beside
  a building, share an ID. Lookup returns whichever is first in the object
  manager's list. Keep the original's order (load order, collidable objects
  first) or prefer buildings, turrets and gates over trees.

### 1.6 How lookup resolves an ID

`getObject(id)`:
- `-1` → the current object.
- Otherwise a linear search for an object whose part ID matches **and that
  currently exists** (its `exists` flag is set).
- `0` → nothing.

Consequences:
- An object that was set non-existent (FIT `Exists = 0`, removed, or never
  spawned) is invisible to every single-object native. `objectStatus` then
  returns −1, `getObjectPosition` returns (0,0,0), and so on.
- **Quirk:** `objectCreate` looks the object up the same way, so it can never
  revive a non-existent object.
- Destroyed and disabled objects still exist, so they keep resolving.

Warrior IDs are a separate space. The mission FIT's `[Warrior<n>]` blocks are
numbered 1…N, and `[Part<p>] Pilot = n` assigns warrior *n* to that part.
Only `playSpeech`, `selectWarrior`, `setRadio` and `getWarriorStatus` take
warrior indices, where `-1` means the current warrior. `getPilotID(obj)`
returns the index.

---

## 2. Execution model

### 2.1 Warrior brains

- Each mover has a pilot (MechWarrior). The pilot has one brain module, named
  by the FIT `Brain` field, e.g. `mc2_01_pat1_1.abl`, or `pbrain` for the
  player's units.
- Every frame, a mover's AI update calls the pilot's decision tree when all of
  these hold:
  - the mover is **awake** (`Active`)
  - it is not disabled
  - the pilot is alive and has not ejected
  - its team ≥ 0
- **Player units are also AI-controlled.** They run `pbrain`, and player
  commands reach the brain as tactical orders.

The decision tree does the following each frame, in this order:
1. If the current tactical order is accomplished (§2.7), clear it.
2. Refresh weapon status for the current target.
3. Drop the current target if it is destroyed, or if it is disabled and the
   target was not marked *obliterate*.
4. **Run the brain if `scenarioTime ≥ brainUpdate`**, and only if
   `brainsEnabled[team]`. Then `brainUpdate += 2.25 s`
   (`BrainUpdateFrequency`).
   - The first run is staggered: `brainUpdate` starts at
     `(warriorCreationIndex mod 30) × 0.2 s`.
   - Nothing in the source schedules an extra or early brain run.
5. `checkAlarms`: for each alarm raised this frame, apply its built-in game
   effect. If the brain defines the matching handler function (§2.5), call it
   immediately.
6. Promote any newly issued tactical order: alarm order > player order >
   general (brain) order.

**One brain run:**
- Set the context (§2.3).
- Reset the pilot-event cursor.
- Execute the module. For an `fsm`, that means the current state.
- **Single player, non-player commanders only:** run the *goal planner*. It
  turns the "main goal" left by the last `core*` order into a concrete
  tactical order, routing around walls and gates. For our sim it is enough to
  execute the core order directly; see the flag in §5.
- Clear all pilot-event history (§2.4).

The module's integer return value is ignored.

### 2.2 Mission script

- One module per mission: `missionN.abl`, `module … : integer`.
- It runs **every frame while the game is not paused**, after all objects,
  sensors and collisions have updated.
- There is no current object or warrior (§2.3).
- Its return value is written to the mission's termination result every
  frame. The values are `PLAYING`/`PLAYER_*` (§4). The special value 9999
  aborts the mission.
  - Separately, the game starts a 5-second end countdown by itself when every
    player mover on the GUI is disabled or destroyed.
  - After the countdown, if the result is still 0, the result is taken from
    the objectives.
- Mission scripts communicate with brains through `eternal` variables, e.g.
  `patrol1_triggered` in `mc2_01`. That is interpreter state, not a native.
- If the mission script defines `handlemessage`, it is only used in
  multiplayer.

### 2.3 Context

Before running a brain or an alarm handler, the engine sets:
- **current object** = the pilot's mover
- **current warrior** = the pilot
- **current group** = the mover's commander group
- **current contact** = none
- **current alarm** = the alarm code (handlers only)

Everything is cleared afterwards.

Natives that use the current warrior **crash in the original if called from
the mission script**: `getIntegerMemory`, `setTargetPriority`,
`getNextPilotEvent`, `core*`, `order*`, `setWillHelp`, `requestHelp`, and
others. Our build should return a neutral value and log instead.

`selectContact` sets the current contact, which later contact natives read.

### 2.4 Pilot event queue (`getNextPilotEvent`)

Events are the engine's **pilot alarms**:
- Each alarm keeps two trigger lists of up to **15** entries: *this frame*
  and *history since the last brain run*.
- Raising an alarm appends its trigger value to both lists. If either list is
  full, the trigger is silently dropped.
- The frame list is cleared after `checkAlarms` each frame.
- The history list is cleared at the **end of each brain run**.

So a brain sees every event raised since its previous run, about 2.25 s'
worth, including events raised after the brain ran last frame.

**Reading the queue:**
- `getNextPilotEvent(params)` walks the alarm codes **in ascending numeric
  order** from a cursor that is reset at the start of each brain run.
- It returns the next code whose history is non-empty and advances past it.
- `params[0..k−1]` receives that alarm's whole trigger list.
- When nothing is left it returns **−1** (`PILOT_EVENT_NONE`).
- Each code is returned **at most once per run**, with all its triggers
  together. It is not one entry per occurrence.
- `params` needs to be at least 15 integers. Scripts declare `integer[20]`.
  Entries past the trigger count are left untouched.

**Trigger conversion.** For object-type alarms, each stored trigger is a
reference to an object, and it is converted to a **part ID** on read. A
trigger whose object no longer exists is **skipped**, so the list can come
back shorter. The other alarms pass their raw value through.

| Code | Event (ABL name) | Raised when | params hold |
|---|---|---|---|
| 0 | `PILOT_EVENT_TARGETED` | a mech, vehicle or turret fires at this mover (any side) | attacker part IDs |
| 1 | `PILOT_EVENT_HIT` | this mover is hit | attacker part ID; or a negative weapon id for mines/artillery (raw); a hit with no attacker stores 0, and 0 is then dropped by the conversion |
| 2 | `PILOT_EVENT_DAMAGED` | damage-taken-rate check fires | raw damage rate |
| 3 | `PILOT_EVENT_FRIENDLY_KILLED` | a mate in my **commander group** is destroyed, or its pilot dies | mate part ID |
| 4 | `PILOT_EVENT_FRIENDLY_CRIPPLED` | a group mate is crippled | mate part ID |
| 5 | `PILOT_EVENT_FRIENDLY_DESTROYED` | never raised in the source | n/a |
| 6 | `PILOT_EVENT_CRIPPLED` | own vehicle incapacitated | raw (66) |
| 7 | `PILOT_EVENT_DESTROYED` | own vehicle destroyed | killer part ID |
| 8 | `PILOT_EVENT_WITHDRAWN` | own vehicle withdrew | raw 0 |
| 9 | `PILOT_EVENT_ATTACK_ORDER` | `requestHelp` assigned me a target (§3) | target part ID |
| 10 | `PILOT_EVENT_COLLISION` | rammed or collided (a hit with a negative non-weapon id) | other object's part ID |
| 11 | `PILOT_EVENT_GUARD_RADIUS_BREACH` | never raised in MC2 | n/a |
| 12 | `PILOT_EVENT_TARGET_KILLED` | this mover destroyed something | victim part ID |
| 13 | `PILOT_EVENT_MATE_FIRED_WEAPON` | a commander-group mate fired | mate part ID |
| 14 | `PILOT_EVENT_PLAYER_ORDER` | a player tactical order was executed | raw tac-order code |
| 15 | `PILOT_EVENT_NO_MOVEPATH` | pathfinding failed or was cleared | raw `Rtn_*` code (−1 … −14, §4) |
| 16 | `PILOT_EVENT_GATE_CLOSING` | a gate is closing on me | raw |
| 17 | `PILOT_EVENT_FIRED_WEAPON` | I fired | target part ID |
| 18 | `PILOT_EVENT_NEW_MOVER` | a mover was added mid-mission | **Quirk:** a raw internal handle, not a part ID; treat as "some mover" |

The handler-only alarms (codes 6–8) are mostly consumed by the engine itself.
Campaign brains only test codes 0, 9, 17 and (rarely) 1. A minimal
implementation needs TARGETED, HIT, ATTACK_ORDER and FIRED_WEAPON.

### 2.5 Alarm handler functions

If a brain module defines a function with one of these exact (lower-case)
names, the engine calls it **in the same frame** the alarm is raised, after
the alarm's built-in effect. Only `pbrain.abl` defines them; it uses six.

| Code | Handler name |
|---|---|
| 0 | `handletargetofweaponfire` |
| 1 | `handlehitbyweaponfire` |
| 2 | `handledamagetakenrate` |
| 3 | `handledeathofmate` |
| 4 | `handlecripplingoffriendlyvehicle` |
| 5 | `handledestructionoffriendlyvehicle` |
| 6 | `handleincapacitationofvehicle` |
| 7 | `handledestructionofvehicle` |
| 8 | `handlewithdraw` |
| 9 | `handleattackorder` |
| 10 | `handlecollision` |
| 11 | `handleguardbreach` |
| 12 | `handlekilledtarget` |
| 13 | `handlematefiredweapon` |
| 14 | `handleplayerorder` |
| 15 | `handlenomovepath` |
| 16 | `handlegateclosing` |
| 17 | `handlefiredweapon` |
| 18 | `handlenewmover` |

Inside a handler, `getAlarmTriggers(list)` returns that alarm's **history**
triggers, converted as in §2.4. That means every trigger since the last brain
run, not only this frame's.

### 2.6 Target priorities and scanning

Each pilot has a **target priority list** of up to 20 entries. Each entry is
`{type, p1, p2, p3}`.

**Setting entries.** `setTargetPriority(index, type, p1, p2, p3)` writes
entry `index`. It grows the list size to `index + 1` and always returns 0.
There is no bounds check: index ≥ 20 corrupts memory in the original, so
clamp it. Brains normally write 0, 1, … and then a `TARGET_PRIORITY_NONE`
terminator.

**When the list is read.** **Only during a scan**:
- `newScan/coreScan(0, criteria)`.
- Any core order given target 0 when there is no remembered scan target:
  `coreAttack(0)`, `coreMoveToObject(0)`, `coreCapture(0)`,
  `coreControl(0)`.
- The `corebrain` orders `corePatrol`, `coreWait`, `coreGuard`,
  `coreEscort` and `coreAttackTactic` scan on every execution.

Ordinary combat (firing at whatever is in range while moving) uses the
separate **current target** (`setTarget`/`getTarget`), not this list.

**How a scan works.** It walks the entries in order. The first entry that
yields a target wins: the scan stores it as the *last scan target* (read by
`getLastScan`) and returns a positive value. If no entry matches, the scan
stores 0 and returns 0.

- `NONE` (0): **stops the scan** with no target.
- `GAMEOBJECT` (1):
  - p1 = specific part ID, or 0
  - p2 = engage radius in metres, measured from me
  - p3 = contact criteria

  Matches object p1 if it is within p2. If p3 ≠ 0 and the object is a mover,
  it must also meet criteria p3 (§3 `getContacts`). With p1 = 0 this entry
  never matches; the "pick any" branch is disabled in the original.
- `MOVER` (2): same parameters as GAMEOBJECT. If p1 = 0, picks the
  **closest** mover among my team's contacts that meet p3, skipping the
  player's marines. Then requires distance < p2 and, if p3 ≠ 0, criteria p3.
  - p3 must be non-zero when p1 = 0; the original raises a fatal error
    otherwise.
- `BUILDING` (3):
  - p1 = specific part ID, or 0
  - p2 = engage radius in metres
  - p3 = −1, meaning "any enemy building"

  With p1 = 0 and p3 = −1, picks the closest enemy building that is not
  destroyed and not a wall. It must be within p2. Any other p3 with p1 = 0 is
  a fatal error.
- `CURTARGET` (4): keep fighting what I am already fighting.
  - p1 = −1 (disengage centre = me; other values were planned to mean
    "reference point" but also use me)
  - p2 = disengage radius in metres
  - p3 = criteria, or 0

  The candidate is the current tactical order's target. A disabled order
  target counts only if obliterate is set. If there is no order target, the
  current target is used. The candidate matches while its distance is < p2
  and, for movers, it meets p3.
- `TURRET` (5): picks the closest turret not on a friendly team. It matches
  within p2. **Quirk:** if that turret is out of range, the scan **stops**
  with no target instead of trying later entries.
- `TURRET_CONTROL` (6) / `GATE_CONTROL` (8): picks the closest capturable,
  non-friendly turret or gate control building. There is no range check.
- `GATE`, `SALVAGE`, `MECHBAY`, `LOCATION`, `EVENT_*`, `SKIP`: no-ops (fall
  through to the next entry).

**Quirk: the ARMED bit alternates.** On every evaluation of a GAMEOBJECT or
MOVER entry, the original **adds** 128 (`CONTACT_CRITERIA_ARMED`, "don't
target unarmed movers") to the stored p3. The bit therefore toggles between
consecutive scans; higher bits are ignored. Recommendation: OR in 128 once,
which is the evident intent.

Engage and disengage radii compare 2-D metres from the scanning mover.

**What a scan returns.** The scan result is an internal object handle, not a
part ID. Scripts only test it with `> 0` and use `getLastScan` to get the
part ID. So returning the part ID is safe.

### 2.7 Tactical orders and "order" statements

A pilot has one **current tactical order**. Each order has:
- a code (§4 `TACTICAL_ORDER_*`)
- an origin: player 0, commander 1, self 2
- a target
- move parameters: waypoint, run, wait, jump, face-object, keep-moving
- attack parameters: type, method, range band, aim location, pursue,
  obliterate, tactic

**When an order is accomplished** (`status` = 1 means done):

| Order | Done when |
|---|---|
| WAIT | game time > the wait's end time |
| MOVETO_POINT | the mover is in the **same map cell** as the goal; with *wait* set it then turns into a WAIT and keeps going |
| MOVETO_OBJECT | the mover is in the same cell as the goal **position computed when the order was given**: the target's position for movers, an open cell next to it for buildings. It does not track a moving target. |
| ATTACK_OBJECT | the target is destroyed, or disabled without *obliterate* |
| POWERUP | the vehicle status is NORMAL |
| POWERDOWN, GUARD, WITHDRAW, ATTACK_POINT, HOLD_FIRE | never done |
| STOP, EJECT | done immediately |
| MOVETO_OBJECT, ATTACK_OBJECT | done if the target reference no longer resolves |

**Core orders** (`core*`, `new*`). Each call builds the order and then
returns one of:
- **1 = finished or impossible.** The order is already satisfied, or it
  cannot be given: no target, no weapons, wrong vehicle class.
- **0 = in progress.** Either an equal order is already current (nothing
  changes), or the call cleared the old order, issued this one as the
  pilot's *general* (brain) order, and requested a path. If
  `TACORDER_PARAM_DONT_SET_ORDER` is set, it only moves and leaves the
  current order in place.

Calling the same core order every brain tick is the normal pattern. The
"equal order" check makes repeats free.

**What the interpreter does with order natives.** It applies these rules only
when an order-flagged native is called **as a statement** inside an `order`
or `state` body. In an expression, e.g. `x = newScan(…)`, it behaves like a
normal function. The rules come from `Ablxstmt.cpp`:
- If the call returns **0**, the enclosing order or state returns
  immediately. Statements after it are not executed this tick.
- If it returns non-zero, the call site is marked *done*. On later executions
  of the same body, a done call site is **skipped**: the native is not called
  (it sees `ABLi_getSkipOrder()` true) and the call evaluates to 1. Skipping
  continues until the module resets its order flags: `resetOrders`, a state
  transition, or `setPilotState` with no current state.
- Every `core*` native first checks the skip flag and returns 1 without doing
  anything.
- Sequences like `coreMoveTo(a); coreMoveTo(b);` therefore run as "go to a,
  then b". `resetOrders(1)` at the end of a state restarts the sequence.
- The skip check also exists in the `order*` natives, but they are not
  order-flagged, so it is always false there.

**`order*` natives (old MC1 style).** They return the raw order **status**:
- `TACORDER_FAILURE` (0) means the order was issued and is not yet done.
- `TACORDER_SUCCESS` (1) means it was already satisfied, or there was no
  target.

They issue the order as the general order, with origin "commander".

### 2.8 Brain memory cells

- Each pilot has **60** cells (indices 0–59; the original does no bounds
  check).
- Each cell is a single 32-bit slot that holds **either** an integer or a
  real (a union). `setRealMemory(i, x)` followed by `getIntegerMemory(i)`
  reads the raw bits, so store a tagged value or keep separate int and real
  views.
- All cells start as integer 0.
- At mission load, the FIT pre-fills them:
  - `[Warrior<n>] NumCells = k`.
  - Then `[Warrior<n>Cell<j>]` for j = 0…k−1, each with `Cell = index`,
    `MemType` (0 = integer, 1 = real) and `Value`.
  - Example, `mc2_01` Warrior4: cell 2 = real 150.0, cells 9 and 28 =
    int 0.
  - `NumStaticVars` / `[Warrior<n>Static<j>]` (type, Name, Value) set
    **static variables** of the brain by name instead. That is interpreter
    state.
- Cell meanings are a convention of the brain libraries (`oconst.abi`:
  `I_SITUATION` = 0 … `R_MOVE_Y` = 39, and target list cells 40–49). The
  engine does not interpret them.

  **One exception:** `createInfantry` writes the spawning building's part ID
  into cell 0 of the new infantry pilot.

### 2.9 Other per-pilot state touched by natives

- **Current target** (`setTarget`/`getTarget`): the target fired on
  opportunistically. It is auto-cleared when the target is destroyed, when it
  is disabled (unless obliterate), or when it becomes friendly.
- **willHelp**: default true. It makes the pilot eligible for `requestHelp`
  assignments.
- **challenger**: a per-mover "who has called dibs on me" reference, used by
  `CONTACT_CRITERIA_NOT_CHALLENGED`.
- **escapesThruEjection**: rolled at load, true if `d100 ≤ Piloting + 30` and
  the roll is < 95, or always true for Toughness specialists. When pilot
  wounds reach 6, a pilot with it set ejects and survives; otherwise the
  pilot dies.
- **move area** (`setMoveArea`): restricts where attack positioning may move
  the unit.
- **debug strings**: 5 slots × 80 chars.

---

## 3. Natives

Entries are in campaign call-count order. **[P]** = presentation only (camera,
sound, music, video, UI, debug): safe to stub with the stated default.
**[SYS:x]** = needs sim system *x*, which we may not have (§5).
"obj" = an object ID per §1; "unit-aware" = also accepts unit and team IDs
(§1.4, squad match unless stated).

1. **`setDebugString(obj, slot, text)`** `iiC` → none. **[P]** Stores `text` in
   debug slot `slot` (0–4) of obj's pilot, shown in the debug overlay.
   Missing obj or pilot: ignored.
2. **`getObjectPosition(obj, out real[3])`** `iR` → none. Writes the world
   position x, y, z (z = terrain elevation). Unknown or non-existent obj:
   writes 0,0,0.
3. **`setTargetPriority(index, type, p1, p2, p3)`** `iiiii` → i. Sets entry
   `index` of the current pilot's priority list. Returns 0. Semantics in
   §2.6.
4. **`coreAttack(target, params)`** `ii` → i, **order**.
   1. Returns 1 if the vehicle has no weapons (unless ramming), clearing
      attack orders.
   2. target 0 → use the last scan target, scanning first if there is none.
      If the result is still null, return 1.
   3. Otherwise build ATTACK_OBJECT from the params bits: PURSUE, OBLITERATE,
      JUMP, DONT_KEEP_MOVING, the attack-method bits (DFA/RAM), the range
      bits (RAMMING/LONGEST/OPTIMAL/SHORT/MEDIUM/LONG; default OPTIMAL), the
      aim bits (HEAD/LEG/ARM) and the tactic bits (FLANK_*, STOP_AND_FIRE,
      which forces pursue, TURRET, which forces no pursue, JOUST).
   4. Return 1 if the order is already satisfied (target destroyed, or
      disabled without obliterate). Return 0 if an equal order is current.
   5. Otherwise make it the general order, set current target = target, and
      return 0. Pursue makes the unit move to keep the target in range;
      without pursue, move orders are cleared.
5. **`getTarget(obj)`** `i` → i. The part ID of obj's pilot's current target,
   or 0 (also 0 for unit IDs, or if obj is not a mover).
6. **`getWeapons(out int[], kind)`** `Ii` → i, current object only. Fills
   the component ("master") IDs of the current mover's weapons and returns
   the count. kind 0 = all weapons; kind 1 = only those not disabled and with
   ammo left. Non-mover: 0. Brains mostly use the count (0 → eject or power
   down).
7. **`getTime`** → r. Mission time in seconds. It is game time and does not
   advance while paused.
8. **`corePower(up)`** `b` → i, **order**.
   - Returns 1 for non-mechs, for disabled mechs, when powering up and
     already NORMAL, and when powering down and already SHUTDOWN.
   - Otherwise clears move and attack orders, starts the startup (if the
     mech has cooled enough) or the shutdown, issues POWERUP/POWERDOWN, and
     returns 0.
   - The vehicle passes through STARTING_UP/SHUTTING_DOWN (§4 statuses).
9. **`objectClass(obj)`** `i` → i. The engine object class (§4: mech 2,
   vehicle 3, elemental 4, building 16, tree-building 27, turret 30, gate
   31, …), or −1 if not found. Brains test `objectClass(-1) == 2` to choose
   eject over power-down.
10. **`getNextPilotEvent(out int[])`** `I` → i. Next pilot event code and its
    trigger list, or −1. See §2.4.
11. **`requestHelp(enemy, friendCentre real[3], friendRadius, enemyCentre
    real[3], enemyRadius, priority)`** `iRrRri` → r (always 0.0).
    **[SYS: threat rating]**
    1. Requires the current pilot to have a team, and `enemy` to be a mover
       on a different team.
    2. **Helpers** = movers that meet all of these:
       - on the caller's team
       - (single player, home team only) under the caller's commander
       - existing, not disabled, with at least one functional weapon
       - within `friendRadius` m of `friendCentre`
       - with willHelp = true
       - if `priority ≤ 0`, also currently without a tactical order
    3. **Targets** = members of the enemy's team that pass the same filters
       around `enemyCentre`/`enemyRadius` (ignoring orders).
       **Quirk:** this means targets must also have willHelp set.
    4. Sort both lists by threat rating, descending.
    5. Assign each helper in turn to the defender with the lowest
       (attacker threat sum ÷ defender threat) ratio; ties go to the larger
       sum.
    6. Raise **ATTACK_ORDER** on each helper with its assigned target.
    7. Brains react next tick (`coreAttack(params[0])`).
12. **`coreEject`** → i, **order**.
    - Non-mech or disabled: 1.
    - If the current order is already EJECT: 0.
    - Otherwise clears orders, performs the ejection (the pilot leaves and
      the mech goes inert), issues EJECT, and returns 1.
    - **[SYS: ejection]**
13. **`setIntegerMemory(cell, value)`** `ii` → none. Writes a cell (§2.8).
14. **`playDigitalMusic(id)`** `i` → i (0). **[P]** Switches the mission
    music track to `id`. The mission scripts use their own `*Tune*` variables
    and `misconst` music IDs (8 victory, 9 defeat, 10/11 objective
    success/fail).
15. **`objectStatus(obj)`** `i` → i, unit-aware.
    - Single object: its status 0–5 (§4), or −1 if not found or not
      existing.
    - Unit or team: `OBJECT_STATUS_DISABLED` (1) if no member is alive.
      Alive means status not DISABLED/DESTROYED and pilot not WITHDRAWN.
      Otherwise NORMAL (0).
    - Never returns 6–8 (WITHDRAWN/INACTIVE/NONEXIST); those exist only as
      `objectStatusCount` tally slots.
16. **`checkObjectiveStatus(n)`** `i` → i. **[SYS: objectives]** The status
    of the player team's *n*-th objective (0-based, in FIT order
    `Team0Objective<n>`): 0 incomplete, 1 success, 2 failed. Out of range: 0.
    The objective system evaluates the FIT conditions and actions itself.
17. **`getLogisticsTime`** → r. **[P]** Wall-clock milliseconds, from the
    system timer, not game time. Movie and tutorial sequences use it for
    real-time delays (`currentTime > 3000`). Any monotonic millisecond clock
    works.
18. **`getRelativePositionToObject(obj, angle, dist, flags, out real[3])`**
    `irriR` → none. A point `dist` metres from obj.
    - Direction:
      - flags bit 1 (`ABS`) set: absolute ABL angle (0 = south, 90 = east,
        180 = north).
      - otherwise: relative to obj's facing. The base vector is the facing
        vector **negated**, so 180 = straight ahead and 0 = behind.
    - Placement on blocked terrain:
      - bit 2 (`PASSABLE_START`): walk from obj toward the point in
        half-cell steps and stop at the last passable cell.
      - without it: if the point is blocked, walk back toward obj until a
        passable cell.
      - bit 4 is unused here.
    - z = terrain elevation.
    - Unknown obj: the output is left untouched.
    - **Quirk:** it treats any object as a mover; buildings have no facing,
      so always pass ABS for non-movers.
19. **`setDebugWindow(window, obj)`** `ii` → i. **[P]** Binds a debug window
    to obj. Returns obj, or 0 if not found. Scripts call `(-1, -1)`.
20. **`getCurrentMusicId`** → i. **[P]** The track currently playing. The
    mission music code uses it to avoid restarting a track. Return the last
    id passed to `playDigitalMusic` (or −1).
21. **`getPlayerInCombat`** → b. True if any warrior under the **player's
    commander** currently has a current target. Drives combat music.
22. **`setRealMemory(cell, value)`** `ir` → none. Writes a real into a cell.
23. **`setMoveArea(centre real[3], radius)`** `Rr` → none.
    - Current mover only.
    - Restricts the attack-positioning goal search to cells within `radius`
      metres of `centre` (guard-an-area behaviour).
    - `radius ≤ 0` (scripts pass −1.0) removes the restriction.
    - **[SYS: attack positioning]**; if our pursue logic has no goal search,
      clamp the pursue destination to the circle.
24. **`playWave(file, type)`** `Ci` → i (0). **[P]** Plays a voice-over or
    support WAV by path, e.g. `"data\sound\mc2_01.WAV"`. `type` is ignored.
    It replaces any voice-over already playing.
25. **`playSoundEffect(id)`** `i` → i (0). **[P]** One-shot UI/world SFX by
    sound ID (`GENERAL_ALARM_SOUND` 18, `PERIMETER_ALARM_SOUND` 20, …).
26. **`getIntegerMemory(cell)`** `i` → i. Reads a cell.
27. **`getSensorsActive`** → b. **[SYS: sensors]** True while any enemy of
    the player team is a contact (visual or sensor) of the player team. It is
    reset at each player-team sensor sweep. It starts true. Drives
    sensor-contact music.
28. **`getContactId`** → i. The part ID of the current contact (set by
    `selectContact`), else 0.
29. **`playVideo(file)`** `C` → i (0). **[P]** Plays a full-screen Bink movie,
    e.g. `"V3G.bik"`, through the mission interface.
30. **`setCameraGoalPosition(pos real[3], seconds)`** `Rr` → none. **[P]**
    Glides the camera's look-at point to `pos` over `seconds`.
31. **`getId`** → i. The current object's part ID, or 0 in the mission
    script.
32. **`orderMoveTo(pos real[3], run)`** `Rb` → i.
    - Issues MOVETO_POINT (origin commander, run → fast) and requests a path.
    - Returns 1 if already in the goal cell, else 0.
    - Does not clear the current target.
33. **`setCameraGoalRotation(rot real[3], seconds)`** `Rr` → none. **[P]**
    The rotation vector is (pitch/projection angle, yaw, altitude). It glides
    over `seconds`.
34. **`setWillHelp(flag)`** `b` → b. Sets the current pilot's willHelp and
    returns the previous value.
35. **`coreMoveTo(pos real[3], params)`** `Ri` → i, **order**.
    - Uses x, y (z forced to 0; NaN coordinates abort in the original).
    - Reads params bits RUN, JUMP, WAIT, LAY_MINES, ESCAPE_TILE,
      DONT_SET_ORDER and DONT_KEEP_MOVING (keep-moving is on by default).
    - Returns 1 if already in the goal cell, and 0 if the same move is
      current.
    - Otherwise clears the current order, sets the move goal, requests a
      path, issues MOVETO_POINT, and returns 0.
    - A move clears attack orders, but not the current target. The unit
      still shoots at it while moving.
36. **`selectContact(type, obj)`** `ii` → i. Makes obj the current contact if
    it is a mover that is a contact of the caller's team (any contact status
    ≠ NONE). Returns 0 on success, 1 if not a contact, and −1 if the current
    object is not a mover. `type` is ignored; scripts pass 1. **[SYS:
    sensors]**
37. **`getMissionLost`** → b. True if the termination result is 1 or 2
    (`PLAYER_LOST_BIG/SMALL`).
38. **`getMissionWon`** → b. True if the termination result is ≥ 4
    (`PLAYER_WIN_SMALL/BIG`) and is not −1. Note that the termination result
    is also what the mission script returned last frame.
39. **`setTarget(attacker, target)`** `ii` → none, unit-aware on `attacker`.
    Sets the current target of the attacker's pilot (each member's, for a
    unit), and recalculates fire ranges. target 0 or unknown → clears it.
    This issues no tactical order.
40. **`setCameraPosition(pos real[3])`** `R` → none. **[P]** Snaps the camera
    look-at point.
41. **`getRealMemory(cell)`** `i` → r. Reads a cell as a real.
42. **`setCameraRotation(rot real[3])`** `R` → none. **[P]** Snaps the
    rotation: x = projection angle, y = yaw, z = altitude (clamped to the
    camera's limits).
43. **`addTriggerArea(r1, c1, r2, c2, type, param)`** `iiiiii` → i. **[SYS:
    trigger areas]**
    - Registers a cell rectangle: rows `r1 ≤ row < r2`, cols
      `c1 ≤ col < c2`.
    - Returns a handle 1–15. More than 15 areas is a fatal error; up to 16
      slots exist and slot 0 is unused.
    - Every time any mover's position updates, each area whose rectangle
      contains the mover's cell is **latched** "hit" if:
      - type 1 (MOVER): param ≤ 0 means any mover; otherwise that specific
        mover. **Quirk:** param is compared with an internal handle, not a
        part ID. `mc2_15` passes 1; treat param > 0 as a part ID and flag
        that mission for testing.
      - type 2 (TEAM): mover team == param.
      - type 3 (GROUP): group id == param.
      - type 4 (COMMANDER): commander == param.
    - Scripts build the rectangle from `convertCoords` output ± N cells.
44. **`isTriggerAreaHit(handle)`** `i` → b. Whether the area has latched; the
    latch stays set until `resetTriggerArea`. False for a removed or invalid
    handle.
45. **`convertCoords(mode, world real[3], cell int[2])`** `iRI` → i (0).
    - mode 0: world → cell, writing `cell[0]` = row and `cell[1]` = col
      (formula in §0).
    - Otherwise: cell → world, writing the cell centre into `world` with
      z = 0.
    - Out-of-map cells give 0,0,0.
46. **`isPlayingVoiceOver`** → b. **[P]** True while the voice-over channel
    (playWave) is playing. Mission tutorials wait on it, so it must
    eventually go false. If audio is stubbed, return false.
47. **`distanceToObject(a, b)`** `ii` → r, unit-aware on `a`.
    - 2-D metres between a and b.
    - For a unit `a`, the minimum over its existing, awake members.
    - −1.0 if either is not found, or if the unit has no eligible member.
48. **`orderAttackObject(obj, type, method, range, pursue)`** `iiiib` → i.
    - Unit IDs: returns 1 and does nothing.
    - obj ≤ 0 or not found: clears attack orders and returns 1.
    - No weapons and not ramming: returns 1.
    - Otherwise issues ATTACK_OBJECT. `type` is 1 destroy, 2 disable, 3
      conserving ammo. `method` is 0 ranged, 1 DFA, 2 ram. `range` uses the
      FireRangeType numbers (§4); scripts pass −1 = optimal. `pursue` 0/1.
    - Sets the current target. Returns 0 if issued, and 1 if already
      satisfied.
    - **Quirk:** when the unit's fire range is set to "current", pursue is
      forced off.
49. **`objectRemove(obj)`** `i` → i.
    - Removes a **mover** completely from the mission. If it is the current
      object, removal waits until its update finishes. Returns 0.
    - Non-movers: 1.
    - **Quirk:** if obj is not found, the original pushes nothing (a stack
      bug). Return 1.
50. **`distanceToPosition(obj, pos real[3])`** `iR` → r, unit-aware. 2-D
    metres from obj to (pos.x, pos.y); NaN components count as 0. Unit:
    minimum over existing, awake members. −1.0 if not found.
51. **`orderMoveToObject(obj, run)`** `ib` → i.
    - Unit IDs: 1.
    - Not found: 1 (no order).
    - Otherwise issues MOVETO_OBJECT. The goal is the target's position for
      movers, and an open cell next to the object otherwise (for buildings,
      in its adjacent area). It requests a path.
    - Returns 0 if issued, and 1 if already there.
52. **`getContactRelativePosition(out range, out angle)`** `rr` → i.
    - Range in metres and bearing in degrees from the current object to the
      current contact.
    - The bearing is relative to the current object's facing, in the
      object's relative-facing convention (signed, −180…180). The
      `corebrain` tactics bucket it in 45° sectors. The exact sign
      convention is **ambiguous** in the source; verify by testing.
    - Returns 0 if there is a contact. Otherwise returns 1, with range −1
      and angle 0.
53. **`endMovieMode`** → none. **[P]** Leaves letterboxed cinematic mode;
    the GUI and commands come back.
54. **`orderWait(seconds, clearTarget)`** `rb` → i.
    - Issues WAIT for trunc(`seconds`), clears move and attack orders, and
      clears the current target if `clearTarget` is set.
    - Returns the status: 1 if the wait time has already elapsed, which is
      true for 0.0. Scripts use `orderWait(0.0, FALSE)` to mean "stop here,
      keep target".
55. **`objectStatusCount(unit, inout tally int[9])`** `iI` → none.
    - **Adds** to the tally; it does not clear it. Callers zero the slots
      they read.
    - Each member is counted in exactly one slot:
      - **8** if the mover does not exist
      - else **7** if it is not awake (inactive)
      - else **6** if its pilot has WITHDRAWN
      - else its status (0–5)
    - Accepts:
      - commander-group IDs 16–31, 165–180 and 329–344
      - teams 500–508
      - a single object (adds 1 to `tally[status]`)
    - Other unit IDs: no effect (see §1.4).
56. **`getObjectDamage(obj)`** `i` → i.
    - **Terrain objects only** (buildings, turrets, …): floor(damage ÷
      damage capacity × 100), or 100 if the capacity is 0.
    - Movers and unknown objects: 0.
    - Scripts test `> 0` for "has been shot".
57. **`getContacts(out int[], criteria, sort)`** `Iii` → i. **[SYS:
    sensors]**
    - Fills the part IDs of the movers that the **current object's team
      sensor** tracks and that meet `criteria` (bitmask, §4), and returns the
      count.
    - Criteria rules:
      - contact status must be ≠ NONE
      - VISUAL_OR_SENSOR: visual or any sensor quality
      - VISUAL: visual only
      - SENSOR: a sensor quality
      - NOT_CHALLENGED: no challenger
      - NOT_DISABLED
      - ENEMY: the mover's team is hostile to mine
      - ARMED/"THREAT" (128): at least one functional weapon
      - GUARD_BREACH (4): ignored
    - Removed movers are never contacts.
    - Sort: 0 none, 1 by combat value descending, 2 by distance ascending.
    - Only `pbrain`/`orders` use it.
58. **`getTacOrder(obj, out time, out int[])`** `irI` → i.
    - Returns the current tactical order code of obj's pilot, or 0, and sets
      `time` to when it was issued.
    - params:

      | Index | Contents |
      |---|---|
      | [0] | code |
      | [1] | origin (0 player, 1 commander, 2 self) |
      | [2] | unit order 0/1 |
      | [3] | target part ID, or 0 |
      | [4] | target object class |
      | [5] | sub-order 0/1 |
      | [6] | selection index |

    - Then, by order type:

      | Order | [7] | [8] | [9] | [10] | [11] | [12] | [13] |
      |---|---|---|---|---|---|---|---|
      | MOVETO_POINT / GUARD | run | wait | goal x | goal y | goal z | | |
      | MOVETO_OBJECT | run | wait | face-object | | | | |
      | ATTACK_OBJECT | run | attack type | method | range | aim location | pursue | obliterate |

      Goal coordinates are integers.
    - Always: [17] = main-goal action (0 none, 1 undecided, 2 move,
      3 attack, 4 capture, 5 guard) and [18] = main-goal object part ID.
    - Other slots are untouched. The array must hold ≥ 19 entries.
    - `pbrain` uses [1], [5] and [17] to detect player orders.
    - Unit IDs: 0.
59. **`getUnitMates(id, out int[])`** `iI` → i.
    - Unit or team ID: the members' part IDs (squad match, or roster).
    - Mover ID: the members of its **commander group**.
    - Returns the count, or 0.
60. **`getAlarmTriggers(out int[])`** `I` → i. In an alarm handler, the
    current alarm's history triggers as part IDs (§2.5). It has no meaning
    elsewhere.
61. **`setEject(flag)`** `b` → b. Sets the current pilot's
    escapes-through-ejection flag (§2.9) and returns the previous value.
    **[SYS: pilot wounds/ejection]**
62. **`objectSide(obj)`** `i` → i. Same as `objectTeam`: `500 + teamIndex`,
    or −1 if not found. **Quirk:** an object with no team (index −1) returns
    **499**.
63. **`newScan(obj, criteria)`** `ii` → i, **order**-flagged, but always used
    in expressions.
    - obj ≠ 0: checks whether that object is "seen". For a mover, it must be
      a contact meeting `criteria`. For anything else, the caller must have
      line of sight to it. If seen, it becomes the scan target and the call
      returns positive; otherwise 0.
    - obj = 0: runs the target-priority scan (§2.6). `criteria` is passed
      through but unused by the list walk; each entry carries its own.
    - Returns > 0 (a handle) or 0. Use `getLastScan` for the part ID.
    - **[SYS: sensors]**
64. **`getCameraRotation(out real[3])`** `R` → none. **[P]** Returns
    (projection angle, yaw, **0**). The altitude is not returned, which is
    why scripts patch `[2]` before setting it back.
65. **`fadeToColor(argb, seconds)`** `ir` → none. **[P]** Fades the screen
    to colour `argb` (0xAARRGGBB as an integer; 4278190080 = opaque black,
    0 = clear). **Quirk:** the time is truncated to whole seconds, so 0.1 is
    instant.
66. **`setMovieMode`** → none. **[P]** Enters cinematic mode: letterbox, GUI
    hidden, player commands blocked.
67. **`forceMovieEnd`** → i. **[P]** 1 if the player pressed Esc to skip the
    current cinematic, else 0. Scripts must then call `endMovieMode`.
68. **`setPilotState(stateHandle)`** `i` → i.
    - If a state is currently executing: transitions the fsm to
      `stateHandle` (like `trans`), and returns the current state's handle.
    - Otherwise: resets order flags, stores the handle as the pilot's brain
      state, and returns the previous one.
    - `corePatrol`/`coreGuard` call it with a handle from `getStateHandle`.
      This is interpreter-level.
69. **`coreMoveToObject(obj, params)`** `ii` → i, **order**.
    - Like `coreMoveTo`, but toward an object: obj 0 → the scan target, and
      1 if none.
    - The goal is the mover's position, or an offset open cell for
      non-movers.
    - Bits: RUN, JUMP, FACE_OBJECT, LAY_MINES, DONT_SET_ORDER,
      DONT_KEEP_MOVING. For non-movers it steps adjacent.
    - Returns 1 if already in the goal cell, else 0.
    - Brains use it with `requestShelter` to retreat into buildings.
70. **`getUnitStatus(obj)`** `i` → r. Health percentage 0–100:
    - **Movers:** weapon effectiveness ÷ max × armour factor × pilot-wound
      factor.
      - Mech armour factor: the product of per-region terms:
        - head: 0.4 + 0.6 × fraction
        - centre torso (front or rear, whichever has less): 0.5 + 0.5 × f
        - side torsos: 0.75 + 0.25 × f
        - arms: 0.75 + 0.25 × f
        - legs: 0.75 + 0.25 × f
      - Vehicle armour factor: the product over the four facings of
        0.4 + 0.6 × f.
      - Wound factor by wounds 0–6: 1, .95, .85, .75, .5, .3, 0.
      - 0 if destroyed or disabled.
    - **Terrain objects:** (capacity − damage) ÷ capacity.
    - Not found: 0.
71. **`objectTeam(obj)`** `i` → i. `500 + teamIndex` (see `objectSide`).
    Mission scripts compare it with `OBJ_TEAM_*`.
72. **`getCameraPosition(out real[3])`** `R` → none. **[P]** The camera
    look-at point.
73. **`getMissionStatus`** → i. 0 (PLAYING) until the end-of-mission
    countdown has started, then the termination result (1–5).
74. **`newMoveToObject(obj, params)`** — alias of `coreMoveToObject`.
75. **`requestShelter(range)`** `*` → i.
    - Collects up to 10 buildings within `range` metres of the current
      object.
    - Returns the part ID of one chosen **at random**, or 0 if there are
      none.
    - No team, damage or type filter.
76. **`stopVoiceOver`** → none. **[P]** Stops the voice-over/support channel.
77. **`getCurrentBRValue(obj)`** `i` → i. The object's current combat value
    (battle rating), or −1 if not found. **[SYS: CV/battle rating]**; use the
    unit's cost or tonnage-derived BR.
78. **`objectTypeId(obj)`** `i` → i. The object's type number: the FIT
    `ObjectNumber` / object-table ID (e.g. `misconst` `APC_TYPE` 402,
    `RAVEN_TYPE` 48), or −1 if not found.
79. **`getWeaponRanges(obj, out real[3])`** `iR` → none. For a mover:
    [0] min, [1] optimal and [2] max fire range in metres. Otherwise
    0,0,0.
80. **`setRevealed(team, radius, pos real[2|3])`** `i*R` → none. **[SYS: fog
    of war]**
    - Marks terrain within `radius` (world units; the source passes it
      straight to the map) of `pos` as explored for `team`.
    - Then forces every team's sensors to rescan.
    - **Quirk:** the campaign passes `objectSide(Me)` (500+), but the code
      expects a raw team index. Normalise: if team ≥ 500, subtract 500.
      team −1 → no reveal.
81. **`getGeneralAlarm`** → i. 0/1 global flag. **[SYS: perimeter alarms]**
    - It is set when an enemy mover stays near a perimeter-alarm building
      longer than that building's alarm timer. Until then, the alarm only
      pings.
    - It never clears by itself. `setGeneralAlarm` clears it, and mission
      start resets it.
82. **`isCaptured(obj)`** `i` → i, unit-aware. For a single object, 1 if it
    has been captured, else 0. For a unit, the number of captured members.
    **[SYS: capture]**
83. **`inArea(id, centre real[3], radius, minIn)`** `iRri` → b. **[SYS: none
    beyond positions]**
    - Single object:
      - `minIn == 0` → always true.
      - Otherwise true if obj exists, is awake, is not disabled or destroyed,
        and is within `radius` m (2-D).
    - Unit with `minIn == −1`: true if at least one member is not disabled,
      **and** every member that is not disabled, exists and is awake is
      within the radius.
    - Unit with `minIn == N > 0`: true once N members that exist, are awake
      and are not disabled or destroyed are inside the radius.
    - Wrapped by `miscfunc` `isWithinArea` (−1) and `inHotSpot` (1).
84. **`inCallout`** → b. **[P]** True while the tutorial "callout" animation
    (the mouse pointer flying to a GUI button) is running. Returns true if
    there is no mission interface. Tutorials wait on it; stub as false.
85. **`getChallenger(obj)`** `i` → i. The part ID of the mover that claimed
    obj (§2.9), else 0. Units: 0.
86. **`setChallenger(victim, challenger)`** `ii` → i.
    - Sets the victim mover's challenger. Challenger 0 clears it.
    - Returns 0 on success, −1 if challenger is a unit ID, and −2 if the
      victim is not a mover.
87. **`playSpeech(warrior, message)`** `ii` → i (0). **[P]** Plays radio
    message `message` (`RADIO_*` id, e.g. 25 under airstrike, 26 move
    blocked) in that pilot's voice. warrior −1 = the current pilot.
88. **`requestTarget(centre real[3], radius)`** `Rr` → i.
    - Friendlies: the caller's team (and commander, for the home team),
      armed, with willHelp, within the radius.
    - Enemies: any hostile, armed, non-disabled movers within the radius.
    - Returns the part ID of the enemy the caller should take, using the same
      ratio balancing as `requestHelp` (§11), or 0 if there are no enemies.
    - **Quirk:** the "who is attacking whom" tally has an indexing bug and
      effectively ignores existing assignments, so it returns the
      weakest-ratio defender, which tends to be the last in threat order.
    - **Quirk:** returns nothing if the caller has no team. Return 0.
    - **[SYS: threat rating]**
89. **`clearTacOrder`** → none. Clears the current pilot's tactical order.
    Move goal and target state follow the normal clear: a NO_MOVEPATH
    alarm with −14 is raised.
90. **`getLastScan`** → i. The part ID of the last scan target (§2.6), else
    0.
91. **`isTeamCapturing(team, target, except)`** `iii` → b. **[SYS:
    capture]**
    - `team` is 500-based; 0 = any team.
    - True if that team has a capture in progress on target.
    - `except` is ignored.
92. **`orderWithdraw`** → i.
    - Current pilot only. Marks the vehicle as withdrawing, issues WITHDRAW,
      and runs to the computed withdraw goal (map edge / exit).
    - **Quirk:** the original leaves two values on the stack. The intended
      return is 0 (or −2 with no pilot).
    - **[SYS: withdrawal]**
93. **`getFixed(fixee, bay, params)`** `iii` → i. **[SYS: repair bays]**
    - Sends a mech or vehicle to a friendly repair bay.
    - Returns:

      | Code | Meaning |
      |---|---|
      | 0 | order issued |
      | −1 | order failed |
      | 1 | bay out of refit points |
      | 2 | wrong bay type |
      | 3 | bay already repairing this unit |
      | 4 | bay busy with another unit |
      | 5 | unit already being repaired elsewhere |
      | 6 | does not need repair |
      | 7 | fixee is not a mech or vehicle |
      | 8 | bay is not a refit building |
      | 9 | different sides |

    - **Quirk:** vehicles are also checked against the mech-bay flag, so a
      vehicle bay returns 2.
94. **`callStrikeEx(type, target, x, y, z, clan, delay)`** `iirrrbr` →
    none. **[SYS: air/artillery strikes]**
    - Calls a strike after `delay` seconds (clamped ≥ 0).
    - Strike types: 248 big artillery, 249 small artillery, 250 sensor
      artillery, 507 big air, 508 small air, 509 sensor air.
    - The strike lands on `target` if it is found, else at (x, y) at
      terrain height.
    - **Quirk:** target −1 means the caller itself.
    - The only campaign call is in commented-out `corebrain` code;
      low priority.
95. **`orderDeployElementals(params)`** `i` → none. A **no-op** in the
    shipped build: the elementals feature is compiled out. Its only call is
    in commented-out code.
96. **`isTeamTargeting(team, target, except)`** `iii` → b.
    - Intended: true if any member of team (500-based, except mover
      `except`) has `target` as its current target. team 0: true if target
      has any attackers counted from the player's units.
    - **Quirk:** the original compares part IDs against internal handles, so
      it effectively never matches. Implement the intent.
97. **`getObjectActive(obj)`** `i` → i, unit-aware. 1 if obj is awake, else
    0. For a unit, the number of awake members.
98. **`isCapturable(obj, team)`** `ii` → b. **[SYS: capture]** team −2: obj
    has the capturable flag and is not destroyed. Otherwise: obj can be
    captured by that team, per the engine's capture rules.
99. **`setInvulnerable(flag)`** `b` → none. Tutorial switch: while set,
    **player-team mechs ignore all weapon hits**. That covers mechs only,
    not vehicles. It also suppresses the friendly-unit damage UI.
100. **`objectChangeSides(obj, teamIndex)`** `ii` → none.
     - Moves obj to team `teamIndex`, a **raw** index (0, 1, …), not
       500-based. The two campaign calls pass 0 and 1.
     - A unit ID is a fatal error.
     - **[SYS: team change]** (used for capture).
101. **`getFireRanges(out real[4])`** `R` → none. The global fire-range
     bands from gamesys (`WeaponRanges`): short, medium and long upper
     bounds (60/120/180 m in `combat-rules.md`), and [3] = 250.
102. **`wasEverCapturable(obj)`** `i` → b. Whether obj has the capturable
     flag, regardless of state.
103. **`setObjectDamage(obj, percent)`** `ii` → none.
     - Raises obj's damage to `percent` (capped at 100) of its capacity, by
       applying an unattributed hit of (target − current + 1) points.
     - It can only add damage, and does nothing for percent ≤ 0.
     - It is designed for terrain objects, using the building damage model.
       On a mover it applies a generic hit.
     - Example: `mc2_*` destroys building 76991 with 100.

---

## 4. Constants

Values are copied from `game/data/abl/*.abi` / `*.abx` and checked against
the engine enums. Where they disagree, the engine value is what natives
actually return.

**PILOT_EVENT_*** (`corebrain.abx`; equals the engine alarm enum):

| Value | Name |
|---|---|
| −1 | NONE |
| 0 | TARGETED |
| 1 | HIT |
| 2 | DAMAGED |
| 3 | FRIENDLY_KILLED |
| 4 | FRIENDLY_CRIPPLED |
| 5 | FRIENDLY_DESTROYED |
| 6 | CRIPPLED |
| 7 | DESTROYED |
| 8 | WITHDRAWN |
| 9 | ATTACK_ORDER (alias MORALE_BREAK) |
| 10 | COLLISION |
| 11 | GUARD_RADIUS_BREACH |
| 12 | TARGET_KILLED |
| 13 | MATE_FIRED_WEAPON |
| 14 | PLAYER_ORDER |
| 15 | NO_MOVEPATH |
| 16 | GATE_CLOSING |
| 17 | FIRED_WEAPON (alias CONTACT) |
| 18 | NEW_MOVER |

**TARGET_PRIORITY_*:**

| Value | Name |
|---|---|
| 0 | NONE |
| 1 | GAMEOBJECT |
| 2 | MOVER |
| 3 | BUILDING |
| 4 | CURTARGET |
| 5 | TURRET |
| 6 | TURRET_CONTROL |
| 7 | GATE |
| 8 | GATE_CONTROL |
| 9 | SALVAGE |
| 10 | MECHBAY |
| 11 | LOCATION |
| 12 | EVENT_TARGETED |
| 13 | EVENT_HIT |
| 14 | EVENT_DAMAGED |
| 15 | EVENT_MATE_DIED |
| 16 | EVENT_FRIENDLY_DISABLED |
| 17 | EVENT_FRIENDLY_DESTROYED |
| 18 | EVENT_FRIENDLY_WITHDRAWS |
| 19 | SKIP |

The list holds at most 20 entries.

**CONTACT_CRITERIA_*** (bitmask; legacy `CT_*` in `oconst`/`cconst` alias
these):

| Value | Name |
|---|---|
| 0 | NONE |
| 1 | ENEMY (`CT_ENEMY`) |
| 2 | VISUAL (`CT_LOS`) |
| 4 | GUARD_BREACH (ignored) |
| 8 | NOT_CHALLENGED |
| 16 | SENSOR (`CT_SENSOR_TRACE`) |
| 32 | VISUAL_OR_SENSOR |
| 64 | NOT_DISABLED |
| 128 | THREAT in ABL = ARMED in the engine (≥ 1 working weapon) |

**CONTACT_SORT_*** (`CS_*`): 0 NONE, 1 CV (descending), 2 DISTANCE
(ascending).

**Contact status** (engine; what `getContactStatus` returns): 0 none, 1–4
sensor contact quality 1–4, 5 visual. The `cconst.abi` `CONTACT_STATUS_*`
(0 none, 1 LOS, 2 sensors, 3 team info) is a legacy layout that no native
returns.

**TACORDER_PARAM_*** (`corebrain.abx`; engine `Move.h`):

| Value | Name |
|---|---|
| 0 | NONE |
| 1 | RUN |
| 2 | WAIT |
| 4 | FACE_OBJECT |
| 8 | LAY_MINES |
| 16 | PURSUE |
| 32 | OBLITERATE |
| 64 | ESCAPE_TILE |
| 128 | SCAN |
| 256 | ATTACK_DFA |
| 512 | ATTACK_RAMMING (engine only; missing from ABL) |
| 1024 | RANGE_RAMMING |
| 2048 | RANGE_LONGEST |
| 4096 | RANGE_OPTIMAL |
| 8192 | RANGE_SHORT |
| 16384 | RANGE_MEDIUM |
| 32768 | RANGE_LONG |
| 65536 | AIM_HEAD |
| 131072 | AIM_LEG |
| 262144 | AIM_ARM |
| 524288 | DONT_SET_ORDER |
| 1048576 | JUMP |
| 2097152 | DONT_KEEP_MOVING |
| 4194304 | FLANK_RIGHT |
| 8388608 | FLANK_LEFT |
| 16777216 | FLANK_REAR |
| 33554432 | STOP_AND_FIRE |
| 67108864 | TURRET |
| 134217728 | JOUST |

Field masks: attack method `0x300`, range `0xFC00`, aim `0x70000`, tactic
`0xFC00000`. Within a field the bits are exclusive values, so test with
equality, not "any bit set". `corebrain` combines flags with `+` and its
`setFlag` helper.

**TACTICAL_ORDER_*** (engine order; the `pbrain` copy matches for 0–19):

| Value | Name |
|---|---|
| 0 | NONE |
| 1 | WAIT |
| 2 | MOVETO_POINT |
| 3 | MOVETO_OBJECT |
| 4 | JUMPTO_POINT |
| 5 | JUMPTO_OBJECT |
| 6 | TRAVERSE_PATH |
| 7 | PATROL_PATH |
| 8 | ESCORT |
| 9 | FOLLOW |
| 10 | GUARD |
| 11 | STOP |
| 12 | POWERUP |
| 13 | POWERDOWN |
| 14 | WAYPOINTS_DONE (`pbrain` calls it FORMATION) |
| 15 | EJECT |
| 16 | ATTACK_OBJECT |
| 17 | ATTACK_POINT |
| 18 | HOLD_FIRE |
| 19 | WITHDRAW |
| 20 | SCRAMBLE |
| 21 | CAPTURE |
| 22 | REFIT |
| 23 | GETFIXED |
| 24 | LOAD_INTO_CARRIER |
| 25 | DEPLOY_ELEMENTALS |
| 26 | RECOVER |

`TACORDER_FAILURE` = 0 (not done), `TACORDER_SUCCESS` = 1.

**ORDER_ORIGIN_*:** 0 PLAYER, 1 COMMANDER, 2 SELF.

**Goal actions** (`getTacOrder` [17]): 0 NONE, 1 UNDECIDED, 2 MOVE, 3 ATTACK,
4 CAPTURE, 5 GUARD.

**Attack parameters** (`orderAttackObject`):
- type: 0 none, 1 TO_DESTROY, 2 TO_DISABLE, 3 conserving ammo
  (`ATTACK_TO_SALVAGE` = 3 in ABL).
- method: 0 RANGED, 1 DFA, 2 RAM.
- range (engine FireRangeType): −4 default, −3 ramming, −2 longest,
  −1 OPTIMAL, 0 SHORT, 1 MEDIUM, 2 LONG, 3 current. ABL calls 3 `EXTREME`.

**Object class** (`objectClass` return; engine `dobjclass.h`):

| Value | Class |
|---|---|
| −1 | not found |
| 0 | base |
| 1 | terrain |
| 2 | BATTLEMECH |
| 3 | GROUNDVEHICLE |
| 4 | ELEMENTAL |
| 5 | explosion |
| 6 | fire |
| 7 | ARTILLERY |
| 8 | mover |
| 9 | gameobject |
| 10 | big gameobject |
| 11 | component |
| 12 | weapon |
| 13 | projectile |
| 14 | laser |
| 15 | PPC |
| 16 | **BUILDING** |
| 17 | smoke |
| 18 | bullet |
| 19 | debris |
| 20 | map icon |
| 21 | TREE |
| 22 | TERRAINOBJECT |
| 23 | MINE |
| 24 | BRIDGE |
| 25 | jet |
| 26 | proj-laser |
| 27 | TREEBUILDING |
| 28 | camera drone |
| 29 | train car |
| 30 | TURRET |
| 31 | GATE |
| 32 | klieg light |
| 33 | weapon bolt |

ABL names: `MECH_CLASS` 2, `VEHICLE_CLASS` 3, `ELEMENTAL_CLASS` 4,
`TURRET_CLASS` 30. **Quirk:** `BUILDING_CLASS` is 15 in
`misconst`/`cconst` and 17 in `oconst`. Both are wrong (the engine returns
16), so scripts comparing against `BUILDING_CLASS` never match. Keep 16;
don't "fix" the constant.

**Object status** (`objectStatus`; tally slots):

| Value | Status |
|---|---|
| 0 | NORMAL |
| 1 | DISABLED |
| 2 | DESTROYED |
| 3 | STARTING_UP |
| 4 | SHUTTING_DOWN |
| 5 | SHUTDOWN |
| 6 | WITHDRAWN (tally only) |
| 7 | INACTIVE (tally only, not awake; `oconst` calls it INVISIBLE) |
| 8 | NONEXIST (tally only) |

−1 means not found.

**Warrior status** (`getWarriorStatus`): 0 normal, 1 withdrawing,
2 withdrawn, 3 ejected, 4 dead, 5 MIA, 6 captured, 7 basecamp.

**Objectives** (`checkObjectiveStatus`): status 0 INCOMPLETE, 1 SUCCESS,
2 FAILED (`INVALIDSTATUS` 9999 is ABL only). Type: −1 invisible, 0 primary,
1 secondary, 2 other.

**Scenario results** (mission script return, `getMissionStatus`):

| Value | Name |
|---|---|
| 0 | PLAYING |
| 1 | PLAYER_LOST_BIG |
| 2 | PLAYER_LOST_SMALL |
| 3 | PLAYER_DRAW |
| 4 | PLAYER_WIN_SMALL |
| 5 | PLAYER_WIN_BIG |
| 9999 | abort |

**NO_MOVEPATH codes** (`oconst` `Rtn_*` = engine `MOVEPATH_ERR_*`):

| Value | Meaning |
|---|---|
| −1 | no goal |
| −2 | goal object gone |
| −3 | invalid goal |
| −4 | already there |
| −5 | long-range movement disabled |
| −6 | LR start blocked |
| −7 | no LR path |
| −8 | no SR path |
| −9 | stopped early (close enough) |
| −10 | timed out waiting for a blocker |
| −11 | bridge/door out |
| −12 | bridge/door blocked |
| −13 | escaping tile |
| −14 | tac order cleared |

**Relative-position flags:** 1 ABS, 2 PASSABLE_START, 4 PASSABLE_GOAL. ABL
always passes 2.

**ABL angles:** `ANGLE_SOUTH` 0, `SOUTHEAST` 45, `EAST` 90, `NORTHEAST` 135,
`NORTH` 180, `NORTHWEST` −135, `WEST` −90, `SOUTHWEST` −45.

**Pilot states** (brain convention, `corebrain`): 0 IDLE, 1 MISSION,
2 RETREAT, 3 PATROL, 4 ATTACK, 5 RETREAT_BUILDING.

**Patrol state array** (`corePatrol`):

| Index | Contents |
|---|---|
| [0] | type (0 linear, 1 looping) |
| [1] | point count |
| [2] | cycles (−1 = forever) |
| [3] | direction (0 forward, 1 backward) |
| [4] | current point (−1 = pick nearest) |
| [5] | current cycle |
| [6] | scan criteria |
| [7] | scan result |
| [8] | contact type |

`MAX_PATROL_POINTS` = 60.

**Tactics** (`coreAttackTactic`): 0 OPTIMAL/DEFAULT, 1 REAR, 2 JOUST,
3 HIT_AND_RUN, 4 SWARM, 5 DFA_RANDOM, 6 RAM_RANDOM, 7 RAM, 8 LONG, 9 MEDIUM,
10 SHORT, 11 NO_PURSUIT, 12 STOP_AND_ATTACK, 13 RUN_AWAY, 14 CIRCLE,
15 LEFT_FLANK, 16 RIGHT_FLANK, 17 CALL_STRIKE, 18 IN_YOUR_FACE,
19 DEPLOY_ELEMENTALS, 20 FIRE_FROM_HERE. Only OPTIMAL, FIRE_FROM_HERE, REAR,
LEFT/RIGHT_FLANK, JOUST and STOP_AND_ATTACK are live code. The rest are
commented out and fall through.

**Weapons status:** `WEAPONS_STATUS_CANNOT_FIRE` −1, `NO_TARGET` −2,
`OUT_OF_RANGE` −3. Per weapon: `NOT_READY` −1, `OUT_OF_AMMO` −2,
`OUT_OF_RANGE` −3, `NOT_LOCKED` −4, `NO_CHANCE` −5, `TOO_HOT` −6.

**Teams and units:**
- `OBJ_TEAM_1` … `OBJ_TEAM_7` = 500 … 506.
- `PLAYER_FORCE` 500, `CLAN_FORCE` 501, `ALLIED_FORCE` 502 (`misconst`).
  **Quirk:** `cconst`/`ubinit` swap allied and clan.
- `misconst` `PLAYER_LANCE0..7` = 1–8 (the engine's lance base is 16),
  `CLAN_STAR0..7` = 165–172, `ALLIED_LANCE0..7` = 329–336.
- `MIN/MAX_MOVER_PART_ID` 512/4095.

**Timers:** `SCENARIO_TIMER_1..7` = 7–13, `EXIT_TIMER` 14,
`PERIMETER_ALARM_TIMER` 13.

**Brain cells** (`oconst.abi`): `I_SITUATION` 0, `R_MIN_ACTION` 1,
`R_ENGAGE_RADIUS` 2, `R_DISENGAGE_RADIUS` 3, `R_ATTACK_RANGE` 4, …,
`I_MOVE_SPEED` 9, …, `I_HITS` 18, …, `I_TACTIC` 28, …, `R_MOVE_Y` 39. Target
list: IDs in 40–44, modifiers in 45–49.

**Sounds and music** (`misconst`): `GENERAL_ALARM_SOUND` 18,
`PERIMETER_ALARM_SOUND` 20, `HPG_SOUND` 44. `VICTORY_MUSIC` 8,
`DEFEAT_MUSIC` 9, `OBJECTIVE_SUCCESS_MUSIC` 10, `OBJECTIVE_FAIL_MUSIC` 11.

---

## 5. Sim systems the natives need

Systems likely to be missing or partial, with the natives that depend on
them:

| System | Natives | Notes |
|---|---|---|
| Per-team sensor/contact status (none / sensor q1–4 / visual) | `getContacts`, `selectContact`, `getContactId`/`RelativePosition`, `newScan`/`coreScan`, the target-priority MOVER and CURTARGET entries, `getSensorsActive` | Highest priority after orders: every patrol and guard brain scans every tick. Minimum: visual = line of sight within visual range from any team member; sensor = within a sensor-equipped member's range. |
| Pilot alarm/event queue | `getNextPilotEvent`, `getAlarmTriggers` | Raised from combat: fired at (TARGETED), hit, fired weapon, killed target, mate events, move-path failure. |
| Tactical-order layer with done-status and the general/player/alarm precedence | all `core*` and `order*`, `getTacOrder`, `clearTacOrder` | |
| Goal planner / attack positioning | `coreAttack` pursue, `setMoveArea` | Can be approximated by "move toward the target until in optimal range, staying inside the move area". |
| Threat rating and combat value (BR) | `requestHelp`, `requestTarget`, `getCurrentBRValue`, contact sort by CV | |
| Objectives evaluator (FIT `Team0Objective<n>` conditions/actions) | `checkObjectiveStatus`, mission end | |
| Trigger areas | `addTriggerArea`, `isTriggerAreaHit` | Simple: check on each mover cell change. |
| Capture | `isCaptured`, `isCapturable`, `wasEverCapturable`, `isTeamCapturing`, `objectChangeSides` | |
| Perimeter alarm buildings | `getGeneralAlarm` | |
| Ejection and pilot wounds | `coreEject`, `setEject`, `getUnitStatus` wound factor | |
| Power up/down with heat cooldown | `corePower` | |
| Withdrawal to the map edge | `orderWithdraw` | |
| Repair bays | `getFixed` | |
| Air/artillery strikes | `callStrikeEx` | Only reachable from dead code. |
| Elementals | `orderDeployElementals` | No-op in the original as well. |
| Fog of war / explored map | `setRevealed` | |
| Squad IDs and commander-group part IDs at mission load | everything that takes an ID | §1.3–1.4; the loader must keep `SquadNum` and compute group part IDs. |

**Presentation layer only** (stub safely):
- `setDebugString`, `setDebugWindow`
- music: `playDigitalMusic`, `getCurrentMusicId`
- sound: `playSoundEffect`, `playWave`, `playSpeech`, `isPlayingVoiceOver`,
  `stopVoiceOver`
- `playVideo`
- camera: get/set position and rotation, and their goal variants
- movie mode: `setMovieMode`, `endMovieMode`, `forceMovieEnd`, `fadeToColor`
- `inCallout`
- `getLogisticsTime`, which needs a millisecond wall clock

Stubs must return values that let the scripts progress:
- `isPlayingVoiceOver` → false
- `inCallout` → false
- `forceMovieEnd` → 0
- `getCurrentMusicId` → the last id set
