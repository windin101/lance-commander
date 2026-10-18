# MC2 remake: feasibility and route choice

Date: 2026-10-18. Status: **decided 2026-10-18.**
- **Route:** B, the Godot 4 rewrite.
- **Title:** "Lance Commander – Battle for the Sphere".
- **Order:** follow the campaign order, starting with mc2_01.
- **Heat:** on.

Phases 0 (scaffold) and 1 (FIT/CSV/strings converters) are done.
- **Phase 2**, the combat and heat sim, is done (docs/specs/combat-rules.md).
- **Phase 3**, terrain and pathing, is done:
  - mc2_01's 100×100 heightmap and 300×300 cell map come from the .pak.
  - The terrain uses the original colour map, with depth-faded water.
  - Pathing is AStarGrid2D with the original's move costs.
  - Placed objects (`.pak` packet 1) move to Phase 5.
- **Phase 4**, mech models, is done:
  - The four mc2_01 mechs (Bushwacker, Werewolf, Starslayer, UrbanMech) are converted from ASE to .glb, with 20 gesture animations each plus forward and backward wrecks.
  - A JSON sidecar per model holds the gesture speeds, foot-down frames and weapon nodes.
  - Team colours use the original paint-mask rule (MechPaint).
- **Phase 5**, units in the world, is done:
  - SimWorld steps at a fixed 10 Hz with move, attack and hold orders, path following, auto-fire every 0.25 s with heat discipline, and projectile flight.
  - The mission loader spawns the 6 mechs, with pilots from their Warrior profiles.
  - mc2_01's 1,000 map objects render: 66 converted models, with alpha-cut foliage.
  - Views: interpolated animated mechs, beams, tracers, missiles and impacts, and wreck swaps.
  - RTS input: click or box select, right-click to move or attack, H to hold.
  - Mechs turn in place to engage targets outside their torso arc.
- **Phase 6** is done. mc2_01 is completable:
  - **Units:** a SimUnit base for SimMech, SimVehicle (gvehicl.cpp rules: 5 sections, no transfer or crits, turret arcs, hover pathing, LRM-carrier death splash) and SimStructure (DmgLevel). All 23 vehicles and infantry spawn.
  - **Objectives:** SimObjectives runs the FIT objective and flag chain, with win/lose after 5 s.
  - **AI:** SimBrain is a state machine (guard, patrol, idle or powered down, power-up, ambush, attack, return fire, help calls) configured from data/brains/mc2_01.json. That file is transcribed from the mission's ABL brains, with source pointers.
  - **Heat:** retuned to dissipation 0.3 with fire discipline.
  - **Check:** tools/autoplay.gd wins in about 4 minutes on three seeds.
- **Slice scope (found in Phase 4):** mc2_01 also fields ground vehicles: 4 Centipedes, 4 Harassers, 7 LRM carriers and 8 infantry. Their rules (`gvehicl.cpp`) and models are new work, to fold into Phases 5 and 6.

Goal: a free, non-commercial, modernised remake of MechCommander 2 (2001) with new graphics and updated gameplay. It gets its own name, with no Microsoft or BattleTech branding (see "Licence ground rules").
The first milestone is one playable mission: one map, a 4v4 lance, objectives, basic AI and modern visuals.

References (read-only, untrusted, gitignored):

- `reference/mc2-source`: Microsoft's 2006 Shared Source release (1.8 GB).
- `reference/alariq-mc2`: alariq's OpenGL/Linux port of that release (57 MB, shallow clone).
- Lee's retail copy, needed only for the cutscene videos.

---

## 1. What the source release contains

Almost all of the game's data is present, mostly in text or open formats, along with every C++ loader for it.

| Category | Where | Format | Converter effort |
|---|---|---|---|
| Missions, campaign, pilots, object types, UI layouts | `Source/Data/{Missions,Campaign,Objects,Art}` | FIT: typed INI (`st FileName = "mc2_01"`), parser `MCLib/Inifile.cpp:161` | Easy |
| Mech, vehicle and weapon stats | `Source/Data/Objects/*.csv` (41 chassis), `compbas.csv` | CSV with odd multi-block layouts, `MCLib/csvfile.cpp` | Easy |
| Strings | `Source/Script1.rc` (~3990 `IDS_*`) | RC STRINGTABLE | Easy |
| Audio | `Source/Data/Sound` (1770 .wav, 342 MB) | WAV | Easy (native import) |
| Textures, sprites, UI art | `Source/Data/{Textures,Art,TGL/128}` | TGA/JPG | Easy (native import) |
| 3D models and animations | `Source/Data/TGL` (2947 .ase + .ini LOD lists) | 3ds Max ASCII export, `MCLib/msl.cpp:366` | Medium |
| Terrain | mission `.pak` packet 0: N×N 32-byte vertices (`MCLib/Vertex.h:32`) | Binary but fixed | Medium |
| Placed objects, path data | `.pak` packets 1 and 4 (`Code/objmgr.cpp:781`) | Packed C structs; path data can be regenerated | Medium–hard |
| Effects | `Data/Effects/mc2.fx` | gosFX binary | Hard; rebuild effects natively instead |
| Fonts | `.d3f` | Undocumented (GameOS not included) | Substitute TTFs |
| AI scripts | 991 `.abl` (953 per-unit brains, 36 mission scripts) | ABL, a Pascal-like language | Hard (see §3) |
| Cutscene videos | **missing** (`cinema1-5.bik`, `PILOTnn`) | Bink | Needs the retail copy |

Also included:

- The full MFC mission editor (`Source/Editor/`). It documents the mission `.pak` layout, e.g. `EditorData.cpp:~1330`.
- The ASE→TGL converter.
- A standalone ABL compiler.

Not included:

- The GameOS library (renderer, fonts, video), so the release can't be built as shipped.
- Networking, which is stubbed out.

## 2. Game-logic shape (the rules reference)

`Code/` is about 153k lines and `MCLib/` about 218k. A vertical slice needs about 25–35k lines of it as reference. The logic to port (`mech`, `mover`, `warrior`, `objective`) is under 15k lines.

Combat, with pointers:

- **To-hit:** `Mover::calcAttackChance` (mover.cpp:6197).
  - Base is pilot gunnery, plus or minus specialist and difficulty modifiers. Out-of-range shots are impossible.
  - Aimed head and limb shots take multipliers from `gamesys.fit`.
  - The result is clamped to 5–95.
- **Hit or miss is decided at fire time** (mech.cpp:7991); the projectile is only a visual delay. Non-streak missiles land half their count.
- **Hit location:**
  - Arc comes from the attacker's bearing: front ±45°, side 45–135°, otherwise rear.
  - A d100 is then rolled against `MechHitLocationTable` (`gamesys.fit:573`; mech.cpp:6609).
- **Damage:** `handleWeaponHit` (mech.cpp:7379).
  - Armour takes damage first, then internal structure. Overflow transfers inward via `MechTransferHitTable` (arm → side torso → centre torso).
  - Crits roll against `CriticalHitTable`.
  - Ammo explosions skip armour; CASE vents to the rear.
  - A head hit injures the pilot.
- **Heat is compiled out.** `updateHeat` sits under `#ifdef USEHEAT`, which nothing defines. Weapon pacing is pure recycle time. That leaves room for a gameplay update: switch heat back on, as an option.

AI is a hybrid:

- **ABL brains** are finite-state machines (`init`/`update`/`state patrol…`). They run every 2.25 s, react to pilot events, and call "core orders" from `corebrain.abx` and `orders.abx`.
- **C++ tactics** do the rest: `MechWarrior::combatDecisionTree` (warrior.cpp:3472) handles weapon choice and firing, with combat ticks every 0.25 s.
- **The mission script** runs every frame, and its return value decides win or lose.

Update order: `Mission::update`, mission.cpp:317. The steps run in this order:

1. LOS reset
2. Camera and terrain
3. PathManager
4. ObjectManager (each mover runs control → AI)
5. Sensors
6. Collisions
7. Mission ABL
8. Win/lose checks

The timestep is variable and locked to rendering.

**Coupling:** tight.

- Mech movement speed is read from the walk animation (mech.cpp:5898).
- mech.cpp makes about 169 `appearance` calls, and the simulation reads the global terrain object.
- The original can't run headless.
- The formulas themselves are pure and data-driven, so they port cleanly.

## 3. The two routes

### A. Upgrade the C++ port (alariq/mc2)

What you get:

- A complete campaign that has been played through on Linux and Windows, with bugs and crashes fixed.
- Exact original behaviour.
- A data pipeline that doesn't need the retail copy.

What it costs:

- **Renderer:** lighting and transforms still run on the CPU, and terrain and mech triangles are pre-lit (mclib/terrain.cpp, txmmgr.cpp). Shadows are the old projected kind, and the GPU lighting path is disabled (`tgl.cpp:97`).
  - PBR lighting and shadow maps mean rewriting the renderer, not polishing it.
- **UI:** layouts are fixed-pixel per resolution (640/1024/1280/1600/1920, `keyboardref.cpp:41`), with `screenWidth == 800` checks scattered through the code. Modern scaling means rewriting the UI.
- **Codebase:** about 390k lines of C++11 on a Win32 emulation layer, in a DirectX 7-era design.
- **Upstream:** dormant ("finished for now"), and its README rejects LLM-generated contributions. You'd maintain a private fork.
- **Licence:** labelled GPL-3, but EULA §3(E) says derived source may be distributed *only* under Microsoft's licence. The fork would be bound by the Shared Source terms anyway.

### B. Godot 4 rewrite (the Race Into Space pattern), recommended

What you get:

- Modern rendering for free: PBR, shadows, SSAO, GPU particles, resolution-independent UI.
- A clean, headless, testable simulation, with tooling and conventions you already use on race-into-space.
- Gameplay changes are easy, because we own every line.

What it costs:

- The rules must be re-derived from the reference code. The pointers above make that tractable, and only the slice's subset is needed first.
- The look won't match the original exactly. That's acceptable, since the point is a modern remake.
- Converters are needed for FIT, CSV, ASE and terrain. Each one is easy or medium.

**Recommendation: B.** The things you want to change (graphics, UI, gameplay) are exactly the parts the C++ port would have to rewrite anyway. In route A you keep the 2001 architecture and still do most of a rewrite. In route B the reference code is the spec, and alariq's port is a second reference for "how it actually behaves".

## 4. Proposed design for route B

- **Engine:** Godot 4.7.2, already installed at `~/.local/opt/godot-4.7.2-stable`, in GDScript.
- **Simulation:**
  - `game/scripts/sim/` holds RefCounted classes with no scene tree.
  - It runs a fixed 10 Hz tick (AI brains every 2.25 s, combat every 0.25 s, as in the original), with interpolation for rendering.
  - It's seeded and deterministic, so tests and fingerprints work as they do on race-into-space.
  - Movement speed comes from per-chassis tables, not from the animation.
- **Data:**
  - `tools/convert/*.py` reads `reference/` and writes JSON and glTF into `game/data/` and `game/assets/`.
  - Original-derived files stay non-commercial under the EULA, and `MANIFEST.md` records their provenance.
- **AI:** rewrite the core orders (patrol, guard, attack, escort, withdraw) and the event handlers as GDScript state machines. Per-unit "brains" become small data files that pick an order and parameters.
  - Don't port the ABL interpreter (extra-large effort).
  - A later option is a transpiler for the 36 mission scripts.
- **Rendering:**
  - Terrain is generated from the original heightfield, with modern splat textures.
  - Mechs start as the original ASE meshes converted to glTF, to prove the pipeline. New HD models of the BattleTech designs replace them later, which is the medium-risk route Lee chose.
- **Heat:** off by default for parity, with an option to turn it on as a gameplay update.

## 5. Vertical-slice plan (milestone 1: one mission)

Suggested mission: **mc2_01**, the first campaign mission. Its script is the smallest and it uses the core orders only. Confirm when phase 1 runs.

| Phase | Deliverable | Size |
|---|---|---|
| 0 | Repo, Godot project, gdUnit4, `run_tests.sh`; `.gitignore` for reference/ | S |
| 1 | Converters: FIT/CSV → JSON (stats, weapons, pilots, `gamesys.fit` tables); strings | S |
| 2 | Headless combat core: to-hit, hit location, armour/structure transfer, crits, ammo, recycle; tests against hand-checked cases from the C++ | M |
| 3 | Terrain: mc2_01 `.pak` packet 0 → heightmap mesh + textures; Godot nav or AStarGrid2D pathing | M |
| 4 | Models: ASE → glTF for the slice's mechs (walk, fire and death animations) | M |
| 5 | Units in the world: selection, move and attack orders, RTS camera, projectiles and effects | M |
| 6 | AI: patrol, guard and attack, plus event handlers; mission objectives and win/lose | M |
| 7 | HUD: force bar, unit icons with damage paper-dolls, tactical minimap | M–L |
| 8 | Visual pass: lighting, shadows, post-processing; first HD art | M |

Out of scope for milestone 1: the campaign and logistics layer (mech lab, salvage, purchasing; extra-large for full parity), multiplayer, the editor and the videos.

## 6. Licence ground rules (unchanged by this research)

- **Never commercial.** No sales, no paid access, nothing behind a payment.
- **Names:** no "MechCommander" (Microsoft trademark) and no "BattleTech" in the title, logo or branding.
- **Notices:** keep the EULA notices, and ship `EULA.md` alongside any original-derived data.
- **Our code vs the data:** our own GDScript is a clean reimplementation, written from reading the reference, not by copying code.
  - Converted original data and art stay under the EULA's non-commercial terms.
  - New HD art of BattleTech designs relies on fan-project tolerance.
- **Upstream:** don't submit anything to alariq/mc2.

## 7. Open questions for Lee

1. Route B (Godot rewrite) or route A (C++ port)?
2. Working title? It needs to avoid both trademarks.
3. Is mc2_01 the right slice mission, or is there a favourite?
4. Heat: keep the original's no-heat rules, or turn heat on as the first gameplay change?
