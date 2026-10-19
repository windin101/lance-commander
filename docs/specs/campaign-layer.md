# Campaign layer ("logistics")

Behavioural spec for the **single-player campaign layer between missions**:
campaign state, the mission-group flow, force selection and drop, the mech
lab, purchasing, salvage, repair, pilots and rewards. It is written from a
read of the original source (`reference/mc2-source/Source/`). The main files
are:
- `Code/LogisticsData.cpp/.h`, `Code/LogisticsMissionInfo.cpp`
- `Code/LogisticsVariant.cpp`, `Code/LogisticsComponent.cpp`
- `Code/LogisticsMech.cpp/.h`, `Code/LogisticsPilot.cpp/.h`
- `Code/logistics.cpp`, `Code/MissionBegin.cpp`, `Code/MissionResults.cpp`
- the screens: `Code/MissionSelectionScreen.cpp`, `Code/MechBayScreen.cpp`,
  `Code/MechPurchaseScreen.cpp`, `Code/MechLabScreen.cpp`,
  `Code/PilotReadyScreen.cpp`, `Code/SalvageMechArea.cpp`,
  `Code/PilotReviewArea.cpp`
- `Code/warrior.cpp/.h` and `Code/mission.cpp` for the mission-side pieces

The data comes from `Data/Campaign/campaign.fit`,
`Data/Missions/Purchase*.fit`, `Data/Missions/PurBonus*.fit`,
`Data/Missions/mc2_*.fit`, `Data/Missions/gamesys.fit`,
`Data/Missions/Warriors/PMW*.FIT`, `Data/Objects/Pilots.csv`,
`Data/Objects/compbas.csv` and `Data/Objects/<chassis>.csv`. No code was
copied.

Conventions follow `capture-and-objectives.md`:
- **Quirk** marks faithful but probably unintended behaviour. A
  recommendation sits next to each one.
- **Ambiguity** marks things the source does not settle.
- "Team 0" or "home" is the player.
- "Inventory" is the player's list of owned mechs.
- "Force group" is the subset chosen to deploy.

Objective payouts and win/lose are specified in `capture-and-objectives.md`
(B6). This document only covers what happens to them afterwards.

---

## 1. Campaign state

### 1.1 What the game keeps

The campaign is one singleton (`LogisticsData`) plus a mission-progress
object (`LogisticsMissionInfo`). Between missions it holds:

| State | Shape | Notes |
|---|---|---|
| **C-Bills** | one integer | The only currency. Spent on mechs, loadout changes and salvage. |
| **Campaign position** | current group index, current mission index, per-mission `completed` and `hidden` flags | See §2. |
| **Bonus purchase files** | a list of file paths | Added during missions by the `MakeNewTechnologyAvailable` objective action (see §5.3). |
| **Mech inventory** | a list of owned mechs | Each one is: a pointer to a *variant* (chassis plus component list), an optional pilot, and a force-group slot (0 = not deployed, 1–12 = slot). Paint colours are stored but **not saved**. |
| **Variants** | designer variants (from the chassis CSVs) plus player-created variants | Player variants are named loadouts saved from the mech lab (§4). |
| **Pilots** | a fixed roster loaded from `Pilots.csv` | Per pilot: piloting and gunnery skill (floats), rank, kill counts, missions completed, a missions-played bitmap, medals, 23 specialty-skill flags, and `dead`/`available`/`used` flags. |
| **Component availability** | an `available` flag per component | Recomputed from purchase files; not saved itself (§5). |
| **Tutorial flags** | `FirstTimeResults` (saved); `FirstTimePurchase` and `FirstTimeMechLab` (static, **not** saved despite a comment saying they should be) | MissionBegin.cpp:43–46 |

**Things that are deliberately not tracked:**
- **Damage, armour loss and ammo.** A `LogisticsMech` has no damage fields
  (LogisticsMech.h:73–82). Every mech starts every mission factory-fresh (§7).
- **A component stockpile.** Components are not owned items. A loadout's
  price is simply chassis cost plus the cost of each installed component
  (§4.4). "Buying a component" means paying the cost difference when you
  save a loadout.
- **Pilot wounds.** They are never written to the logistics pilot. Each
  mission reloads them from the profile's `[Status] Wounds`, which is 0 for
  every campaign pilot. Wounds therefore fully heal between missions (§8.5).
- **In-mission support Resource Points.** They are separate from C-Bills and
  are not carried over (§9).

### 1.2 Where the campaign starts

`startNewCampaign` (LogisticsData.cpp:2260) does the following:
1. Clears the inventory.
2. Reloads all pilots from `Pilots.csv`.
3. Parses `campaign.fit`.
4. Selects the first uncompleted mission of group 0.

The `[Campaign]` block in `campaign.fit` holds `GroupCount = 13`,
`CBills = 80000`, `FinalVideo = "cinema5.bik"` and `NameID = 60021`
(LogisticsMissionInfo.cpp:77–128).

**`campaign.fit` contains no starting mechs or pilots.** The starting force is
the player's FIT parts in the first mission, because that mission runs with
`PlayLogistics = 0` (§2.3, §3.4):

| mc2_01 part | CSV / variant | Pilot profile |
|---|---|---|
| Part1 | `Werewolf` variant 0 ("Razorback Prime" in the CSV) | `pmwflash` |
| Part2 | `Bushwacker` variant 0 (Bushwacker Prime) | `pmwhacksaw` |
| Part3 | `Bushwacker` variant 0 | `pmwlongshot` |

When mc2_01 is won, the surviving parts become the inventory (§7.1). The
player therefore enters the first logistics screen with:
- 80000 C-Bills, plus the objective payouts from mc2_01;
- whichever of those three mechs survived (destroyed or disabled ones are
  lost);
- the 15 pilots listed in `Purchase01`/`Purchase02` (§8.1).

Converted data: `game/data/campaign.json` mirrors `campaign.fit` one to one.

**Ambiguity:** if all three starting mechs are lost on mc2_01, the
campaign continues with an empty inventory and 80000 plus payouts. Nothing in
code prevents a soft-lock where the player can afford no mech. A remake
should either guarantee a minimum or allow a restart.

### 1.3 Save games

`LogisticsData::save` (LogisticsData.cpp:1039) writes a FIT file. All values
are written as-is; there is no checksum.

| Block | Keys |
|---|---|
| `Variant<n>` (one per **player-created** variant; written first) | `Chassis` (CSV path), `VariantName`, `ComponentCount`, and `Component<i>`, `Component<i>x`, `Component<i>y`, `Component<i>Location` |
| `Version` | `VersionNumber = 10004` (LogisticsData.cpp:39). A mismatch refuses the load. |
| `General` | `VariantCount`, `PilotCount`, `InventoryCount`, `FirstTimeResults` |
| `General`, continued (LogisticsMissionInfo::save, :458) | `CampaignFile`, `CampaignName`, `PlayerName`, `CBills`, `Group`, `BigMoviePlayed`, `MissionName`, `MissionFileName`, `Mission<k>` (indices of completed missions in the *current* group), `CompletedMissions` |
| `AdditionalPurchaseFiles` | `File<k>` |
| `Pilot<n>` (every roster pilot) | `FileName`, `Rank`, `Gunnery`, `Piloting`, `Kills` (mechs), `VehicleKills`, `InfantryKills`, `MissionsCompleted`, `MissionsPlayed` (byte array), `Dead`, `Medal<i>`, `SpecialtySkill<i>` |
| `Inventory<n>` | `Chassis`, `Variant` (name), `Pilot` (profile file name, or omitted), `Designer` |

Load (LogisticsData.cpp:1104) does the following:
- Rebuilds the campaign from `CampaignFile`.
- Marks the listed missions in the saved group completed. Earlier groups are
  implicitly done.
- If enough missions are complete, unhides the hidden missions (§2.2).
- Re-adds the player variants, pilots and inventory.
- Gives each inventory mech that has a saved pilot the next force-group slot
  (1, 2, 3, …). Mechs without a pilot go to the reserve. The force group is
  therefore "every piloted mech".
- Finally calls `updateAvailability`.

**Where it saves:**
- **Autosave** after the post-mission screens (MissionResults.cpp:113). The
  name comes from the `IDS_AUTOSAVE_NAME` format and the mission name.
- A "final mission" save when the campaign ends (logistics.cpp:150–157).
- Manual save and load from the in-logistics main menu (MainMenu.cpp:527, 553).
- In-mission saves (saveload.cpp:454) also embed this block.

**Quirk:** on load, the current mission becomes the one at index
"number of completed missions" (LogisticsMissionInfo.cpp:425). In a choice
group completed out of order, that index can point at a mission that is
already done. `setNextMission` then refuses it, leaving the previous
selection. **Recommendation:** pick the first uncompleted mission.

**Quirk:** the pilot load loop sets *every* pilot `available`, but
`updateAvailability` corrects it straight after. This is harmless.

**Remake recommendation:** save the same facts as JSON. Also add mech
colours, which the original drops on save.

---

## 2. Campaign structure and mission flow

### 2.1 campaign.fit fields

**Group block** (`[Group<i>]`), LogisticsMissionInfo.cpp:130–181:

| Field | Meaning | Default |
|---|---|---|
| `NumberToComplete` | How many missions of the group must be completed (together with every Mandatory one) before the group advances | −1 |
| `MissionCount` | Number of `Group<i>Mission<j>` blocks | — |
| `OperationFile` | Art FIT for the operation map on the mission-selection screen. Each mission gets a button on it. | `mcl_cm_opplayer.fit` |
| `Video` | Small in-panel briefing video (`.bik`) on the mission-selection screen. Auto-plays the first time the group is shown; afterwards it starts stopped. | required |
| `PreVideo` | Full-screen cinematic, played **once** when the group's logistics is first entered | none |
| `Tune` | Logistics music track id | — |
| `ABLScript` | Optional logistics ABL brain. Groups 0–2 use `Tutorial0..2`, which drive the tutorial pointer animations in logistics. | `"NONE"` |

**Mission block** (`[Group<i>Mission<j>]`), :183–259:

| Field | Meaning | Default if absent |
|---|---|---|
| `FileName` | Mission FIT name (`mc2_NN`) | required |
| `Mandatory` | The group cannot advance until this one is completed | false |
| `Hidden` | Not shown on the operation map until the group's `NumberToComplete` is reached | false |
| `VideoOverride` | Replaces the group `Video` once this mission is unhidden; also used as this mission's video | none |
| `PurchaseFile` | Purchase file name (no extension), resolved to `data\missions\<name>.fit` | `purchase_All` |
| `PlayLogistics` | false = skip the whole pre-mission logistics. The mission loads its own FIT player parts ("quick start"). | **true** |
| `PlaySalvage` | Show the salvage screen after the mission | **true** |
| `PlayPilotPromotion` | Show the pilot review and promotion screen after the mission | **true** |
| `PlayPurchasing` | Enables the mech-bay **Buy** button (purchase screen) **and** the **Change Loadout** button (mech lab) | **true** |
| `PlaySelection` | Only relevant when `PlayLogistics` is false. Shows the mission-selection screen instead of jumping straight to loading. | **false** |
| `CompletePrevious` | Read, never used | — |

Each mission's FIT `[MissionSettings]` also contributes the following
(readMissionInfo, :263–340):

| Setting | Use |
|---|---|
| `MissionName` / resource string | Name on the operation map |
| `Blurb2` | Briefing text |
| `ResourcePoints` | **In-mission** support budget (§9) |
| `AdditionalCBills` | See §9 |
| `DropWeightLimit` | Tonnage limit; default **300** if absent |
| `AirStrikesEnabledDefault`, `MineLayersEnabledDefault`, `ScoutCoptersEnabledDefault`, `SalvageCraftEnabledDefault`, `SensorProbesEnabledDefault`, `RepairVehicleEnabledDefault` | Gate the in-mission support buttons. Default **true**. |
| `ArtilleryPieceEnabledDefault` | Gates the artillery support button. Default **false**. |

`NoVariantsEnabledDefault` appears in many campaign FITs. It is read **only
in multiplayer** (MPParameterScreen.cpp:652). It has no single-player
effect.

### 2.2 Group progression (setMissionComplete, LogisticsMissionInfo.cpp:785)

On a **win**:
1. Mark the current mission completed.
2. Count the completed missions and check whether every Mandatory mission is
   done.
3. If `completed ≥ NumberToComplete` **and** all Mandatory missions are done:
   advance to the next group with mission index 0. If that was the last
   group, the campaign is over (§2.5).
4. If the count is reached but a Mandatory mission is outstanding: **unhide
   every hidden mission** in the group. If one carries a `VideoOverride`, it
   becomes the group video and is marked unseen. The current mission becomes
   the first uncompleted one.
5. Otherwise the current mission becomes the first uncompleted one.

How this plays out in the shipped campaign (`campaign.fit`):
- **Linear groups** (0–4, 6, 9, 11, 12) each hold one Mandatory mission.
- **Choice groups** (5, 7, 8, 10) hold N optional missions plus one Hidden
  Mandatory finale.

| Group | Missions (optional) | Hidden finale | NumberToComplete |
|---|---|---|---|
| 5 | mc2_06, 07, 08 | mc2_09 | 2 |
| 7 | mc2_11, 12 | mc2_13 | 2 |
| 8 | mc2_14, 15, 16 | mc2_17 | 3 |
| 10 | mc2_19, 20, 21 | mc2_22 | 2 |

The `NumberToComplete` count includes the finale. Take group 5: the player
completes 2 of the 3 optional missions. The finale then appears. After that
the player may still play the third optional mission, or go straight to the
finale. Completing the finale makes the count at least 3 (≥ 2) with all
Mandatory missions done, so the group advances.

**Groups 7 and 8 quirk:** `NumberToComplete` equals the number of optional
missions (2 of 2 in group 7, 3 of 3 in group 8). The finale only unhides
after **every** optional mission is done, so the player chooses only the
order, not a subset. Only groups 5 and 10 offer a real choice (2 of 3).

A **loss** changes nothing (§2.4).

### 2.3 Screen order

**Pre-mission ("mission begin")** is a 5×3 grid of screens. Next and Back
move along the middle row; Up and Down move off the mech bay
(MissionBegin.cpp:300–330):

```
                       [Purchase (2,0)]
                             ^ Buy
[Mission Select (0,1)] -> [Briefing (1,1)] -> [Mech Bay (2,1)] -> [Pilot Ready (3,1)] -> [Loading/Launch (4,1)]
                             v Change Loadout
                       [Mech Lab (2,2)]
```

1. **Mission selection** (operation map). One button per **non-hidden**
   mission in the current group; completed missions are disabled. Picking
   one calls `setCurrentMission`, which does the following:
   - applies `AdditionalCBills` (§9);
   - recomputes availability from that mission's purchase file (§5.1);
   - copies the mission's support RP;
   - drops force-group mechs from slot 12 downward until the force fits the
     new drop weight (`removeDeadWeight`, LogisticsData.cpp:780).

   The group `Video` (or `VideoOverride`) plays in a panel.
2. **Briefing.** Objectives and blurb for the selected mission; shows
   C-Bills.
3. **Mech bay.** Builds the force group from the inventory (§3). **Buy**
   goes to Purchase; **Change Loadout** goes to the Mech Lab for the
   selected mech. Both buttons are disabled when `PlayPurchasing` is false
   (MechBayScreen.cpp:581–584).
4. **Pilot ready.** Assign pilots to each force-group mech. **Next/Launch**
   is disabled until every force-group mech has a pilot and there is at
   least one mech (PilotReadyScreen.cpp:366–457).
5. **Loading.** The mission starts.

**When `PlayLogistics` is false** (only mc2_01 in the shipped campaign):
- Coming from "new campaign" or "restart": go straight to Loading. If
  `PlaySelection` is true, show mission selection with an extra **Launch**
  button, then Loading (MissionBegin.cpp:478–495, 181–189;
  MissionSelectionScreen.cpp:189).
- The mission then loads with **all of its FIT player parts**, and the
  inventory is ignored (§3.4).

**Post-mission** (logistics.cpp:130–170, 335–365; MissionResults.cpp):

On a **win** (`mis_PLAYER_WIN_BIG`):
1. Apply the results to the state (§7.1, §8.3, §9).
2. **Salvage screen**, if the mission's `PlaySalvage` is set.
3. **Pilot review**, if `PlayPilotPromotion` is set. It runs a promotion
   pop-up for each pilot who ranked up.
4. **Autosave.**
5. If a new group was entered, its **PreVideo** (full screen, once).
6. Back to **mission selection**.

On a **loss**: no results screens and no state change. The player returns
straight to the **briefing** screen of the same mission with the same force,
ready to retry. If that mission skips logistics, they return to mission
selection when `PlaySelection` is set, otherwise to the main menu
(logistics.cpp:343–356).

**Quirk (which mission's flags apply):** the salvage and promotion skips use
"the previous mission". After completion that is reconstructed by index
(`getPreviousMission`, :1130): mission index − 1 in the current group, else
the last mission of the previous group. In choice groups this is often not
the mission just played. It is harmless in the shipped data, because every
mission after mc2_03 uses the defaults (true). **Recommendation:** record
the mission just played and read its flags directly.

### 2.4 Retry semantics

After a loss:
- C-Bills, inventory, pilots, deaths and kills are all as before the
  mission.
- **Quirk:** bonus purchase files granted *during* the lost attempt stay
  granted, because `addBonusPurchaseFile` runs when the objective fires
  (Objective.cpp:1272). Replaying can also append duplicates.
  **Recommendation:** queue bonus files and commit them only on a win.

### 2.5 Campaign end

When the current group index reaches `GroupCount`:
1. `FinalVideo` (cinema5) plays, then `credits.bik`.
2. A final save is written.
3. The game returns to the main menu (logistics.cpp:141–158, 280–300).

---

## 3. Force selection and drop

### 3.1 Limits

- **Unit cap:** 12 force-group slots (LogisticsData.cpp:601, 1856).
- **Drop weight:** the sum of **chassis tonnage** (not loadout weight) over
  the force group must be ≤ the mission's `DropWeightLimit`. If the field is
  absent, the limit is 300 (LogisticsMissionInfo.cpp:312–316).
  `canAddMechToForceGroup` checks both limits (LogisticsData.cpp:1851).
- **Shipped drop limits:** from 75 t (mc2_14) to 450 t (mc2_24). Full table
  in §10.2.

### 3.2 Mech bay behaviour

- The inventory list shows **reserve** mechs (force-group slot 0), grouped
  by variant.
- **Add:** puts the selected reserve mech in the next free slot, if it fits.
- **Remove:** returns a mech to reserve and also clears its pilot.
- Drag and drop between the list and the slots is equivalent.
- A drop-weight meter shows current/max and previews the add or remove.
- Selecting a mission with a lower limit auto-removes mechs from the highest
  slots downward until the force fits (§2.3).

### 3.3 Pilot assignment

Pilot Ready lists every pilot who is available (in the current purchase or
bonus files, and not dead) and not already assigned. The player assigns one
pilot per force-group mech. There are no weight or class restrictions.

`getBestPilot` ranks pilots by rank, then gunnery, then piloting. It is
**only** used in-mission to crew a mech recovered by the Recovery Team or by
capture (missiongui.cpp:1067, tacordr.cpp:1847). It takes an unused,
available pilot from the reserve. The Recovery Team button is disabled when
no reserve pilot is left (controlGui.cpp:1837).

**Quirk:** in `comparePilots` the "p2 outranks p1" branch repeats the first
test (LogisticsData.cpp:1014–1018), so a lower rank never loses on rank
alone. **Recommendation:** use a plain rank → gunnery → piloting sort.

### 3.4 How the chosen force replaces the FIT player parts

`Logistics::beginMission` (logistics.cpp:455–790) and `Mission::init`
(mission.cpp:2580–2730) decide this.

**When logistics was played (`MISSION_LOAD_SP_LOGISTICS`):**
- Every FIT part with **`CommanderID == 0` that is not pre-destroyed**
  (`Damage < 1.0`) is **not created**, whatever its type (mech or vehicle).
  Its warrior is freed (mission.cpp:2724–2745).
- These parts are kept:
  - parts under other commanders on team 0, i.e. allies (team 2 is
    remapped to team 0 in single player, :2591);
  - pre-destroyed player parts, which stay as wrecks;
  - every enemy part.
- **Drop point.** While reading parts, the position of every team-0 part is
  appended to a drop-zone list. That covers allies and wrecks too, in file
  order. Only **entry 0** is used: the position of the *first* team-0 part
  in the FIT (mission.cpp:2594).
- **Spawn layout.** Force-group mechs, in inventory order, spawn on a ring
  of radius **128 world units** around that point.
  - The first mech goes at +Y.
  - Each next one is rotated by 360°/N, where N is the force size.
  - Every spawned mech's facing is 0.
  - Colours come from player prefs.
  - Source: logistics.cpp:725–770.
  - **Quirk:** a force mech without a pilot is skipped *after* its position
    is computed but *before* the rotation step, so the next mech takes the
    same spot. Launch validation makes this unreachable.
- **Pilot data.** Each spawned mech gets its pilot profile, but gunnery,
  piloting and specialty skills are **overridden** with the logistics
  pilot's current values (`overrideLoadedPilot`, mission.cpp:1157–1163).
  Wounds and personality come from the profile.
- **Loadout.**
  - Designer variants are spawned by variant index.
  - Player-created variants are spawned with the custom component list.
  - Ammo is whatever each weapon's ammo master supplies.
  - The remake's combat side must accept a variant defined by
    `(chassis, component list)`, not only a CSV variant index.

**When logistics was skipped (`MISSION_LOAD_SP_QUICKSTART`):** all FIT
parts load as authored, including the player's. Mech colours come from the
FIT.

**Ambiguity:** the original does not use the per-mission drop-zone list
beyond entry 0. A remake that spreads mechs across several authored
player-part positions would differ visibly. Recommendation: either keep the
ring, or use the authored player-part positions in order and fall back to
the ring when there are more mechs than positions.

---

## 4. Mech lab (loadouts)

### 4.1 Data model

**Chassis** (from `Data/Objects/<name>.csv`; LogisticsVariant.cpp:40–110,
rows and columns 1-based):

| Field | CSV cell | Example (hunchback) |
|---|---|---|
| tonnage (drop weight) | row 3 col 5 | 50 |
| heat capacity (`Heat Index`) | row 4 col 5 | 24 |
| base armour (`Total Armor`) | row 6 col 5 | 80 |
| speed (`MaxRunSpeed`) | row 7 col 5 | 19 |
| base cost (`ChassisC-Bills`) | row 11 col 5 | 24250 |
| max armour | row 12 col 5 | 240 |
| grid width (`LogisticsX`) | row 13 col 2 | 3 |
| grid height (`LogisticsY`) | row 14 col 2 | 4 |
| house id | row 4 col 2 | 1 |
| allowed specials (`Advanced Sensor`, `Optics`, `GlobalSensor`, `ECM`, `ActiveProbe`, `Jump Jets`, `Extended Sensor`) | rows 3–9 col 8 | JJ only |

Variants follow in 97-row blocks starting at row 21:
- the name is at row 23 + 97v, col 2;
- the item rows are 26–96 (+97v), with the component id at col 5, the grid
  x at col 3 and the grid y at col 4.

**Logistics components** (`compbas.csv`; LogisticsComponent.cpp:75–165):
- Only rows with a **logistics icon** (col 24 non-empty and not "0") are
  mech-lab components.
- Engines, actuators, gyros, cockpits and **ammo** rows are excluded
  automatically.
- Ammo is implicit: each weapon carries its ammo master id.
- Fields used:

| Field | Column | Use |
|---|---|---|
| heat | col 6 | Heat it adds to the loadout |
| weight | col 7 | Displayed only |
| damage | col 8 | For heat sinks this is the **capacity added** (4) |
| cost | col 10, labelled `RP`; = C-Bills | Price |
| range class | col 11 | Short/medium/long |
| footprint | `Icon X` × `Icon Y` (cols 28–29) | Width × height in grid cells |

The full list is in §10.4.

### 4.2 Slots

A loadout has three kinds of slot:
- **Body grid**, `LogisticsX × LogisticsY` cells. Every grid component
  occupies a W×H rectangle that must be inside the grid and must not
  overlap another (LogisticsVariant.cpp:596–700). With no explicit
  position, the first free top-left cell is taken, scanning rows, then
  columns.
- **Jump-jet slot.** One special slot, used only if the chassis allows jump
  jets; maximum one jump-jet item. The item "Jump Jets" (id 10) is a single
  component.
- **Head slot.** Holds one sensor and/or one ECM, each only if the chassis
  allows it. **Ambiguity:** no sensor or ECM row in `compbas.csv` has a
  logistics icon, so none is ever offered. The head slot is effectively
  unused in the campaign.

### 4.3 Validation (canAddComponent, LogisticsVariant.cpp:596)

A component can be added only if all of these hold, checked in this order:
1. **Heat:** the loadout's total heat plus the new component's heat is ≤
   **heat capacity**. Heat capacity = chassis `Heat Index` + 4 per installed
   heat sink. (A heat sink has heat 0 and adds 4 to capacity.)
2. **Jump jets:** the chassis must allow them, none may be installed yet,
   and they can only go in the JJ slot.
3. **Grid fit:** the footprint fits at the requested position or anywhere.
4. **Armour plating** (id 25): each one adds **+32** armour. Base armour +
   32 × plates must be ≤ max armour.
5. **Sensor/ECM:** must be allowed and unique.

Removing a component:
- Removing a **heat sink** is refused if it would leave heat above capacity
  (`INSUFFICIENT_HEAT`, :806).
- Removing a component that is **not currently available** is allowed, but
  a warning says it cannot be re-bought (MechLabScreen.cpp:1728–1740).

**Weight is not validated.** The weight check is commented out ("weight no
longer matters", :598). The displayed weight is 20% of tonnage + 7 t + the
component weights (:509). It is informational only.

Designer variants may break these rules; for example "Renard's Atlas" has
heat 46 against a capacity of 43, and 560 armour against a maximum of 432.
The rules apply only to edits.

Displayed stats:
- **Armour:** base + 32 per plate.
- **Jump range:** 5 if any jump jet is fitted, else 0. The source comments
  call this "BOGUS".
- **Speed:** chassis speed mapped through a fixed table to a display value:
  5→17, 10→34, 15→54, 19→65, 23→86, 27→97, 31→119, 35→130
  (LogisticsVariant.cpp:130–160).
- **Optimal range:** the range band with the highest total damage ÷
  recycle.

### 4.4 Cost model

- **Variant price** = chassis base cost + Σ component cost
  (LogisticsVariant.cpp:493).
- **Entering the lab** copies the mech's variant into an editable working
  copy (`setMechToModify`, LogisticsData.cpp:1937).
- The **cost change** shown is new price − original price. It can be
  negative, so stripping weapons refunds their **full** cost.
- **Accept** (MechLabScreen.cpp:1028–1060):
  1. Refused with "insufficient C-Bills" if cost change > C-Bills.
  2. If the edited loadout is identical (same chassis, same component ids in
     the same order) to the variant whose name is in the name box, the mech
     simply switches to that existing variant.
  3. Otherwise a **save-as-name** dialog appears. The name may not clash
     with a designer variant, or with a variant other mechs use
     (`canReplaceVariant`, LogisticsData.cpp:2167).
  4. On accept, the bill is old price refunded, new price charged
     (`acceptMechModifications`, :2033).
  5. The old player variant is deleted if no other mech uses it.
- **Cancel** discards the working copy.
- The **variant drop-down** in the lab lists every variant of the same
  chassis whose components are all currently available. Selecting one
  copies its loadout into the working copy, keeping the current name.
- The mech lab is reachable only when `PlayPurchasing` is set (§2.3).

**Quirk:** the hard-coded name "Renard's Atlas" is always unavailable to the
player (LogisticsVariant.cpp:983, 999). Keep it hidden.

**Remake data gap:** `game/data/chassis/*.json` lacks `LogisticsX`/`Y`
(grid size). `components.json` lacks the icon footprint (`Icon X/Y`) and the
"has logistics icon" flag. The converter must add these. Base armour equals
the sum of `base_armor` values (hunchback: 80). Heat capacity is
`heat_index`. Component C-Bill cost is `rp`.

---

## 5. Purchasing and availability

### 5.1 Purchase files

Format (`Data/Missions/Purchase<NN>.fit`):

```
[Components]  b AllComponents = False   l Component<i> = <compbas id>
[Mechs]       st Mech<i> = "<chassis csv name>"
[Pilots]      st Pilot<i> = "<warrior profile>"
```

`updateAvailability` (LogisticsData.cpp:1476) runs every time a mission is
selected and after every load:
1. All pilots become unavailable.
2. Components listed in the mission's purchase file become available. With
   `AllComponents = True`, all of them do.
3. Every **bonus** file adds its components and pilots (§5.3).
4. Any component in neither the main file nor a bonus file becomes
   unavailable again.
5. **Mechs:** a variant becomes purchasable if its chassis is listed in
   `[Mechs]` **and every component in the variant is available**. This
   includes player-created variants of that chassis.
6. **Pilots:** those listed in `[Pilots]` (and in bonus files) become
   available, as long as they are not dead.
7. "New mechs / weapons / pilots" flags drive a one-time Betty
   notification on the relevant screen.

The files are cumulative by authoring, not by code: each file lists the
complete current tech. The code always takes "current file plus bonus
files". The progression is in §10.3.

**Quirk:** in bonus files, the `[Mechs]` loop stops after the first matching
variant of each chassis (LogisticsData.cpp:1757). No shipped bonus file
lists mechs, so this is harmless.

### 5.2 Buying and selling (MechPurchaseScreen.cpp; LogisticsData.cpp:450–510)

- **What can be bought:** whole mechs only, as purchasable variants (§5.1).
  Price = variant price (§4.4). Rows priced above current C-Bills are
  disabled. There are no stock limits; any number of copies can be bought.
- **A bought mech:** joins the reserve without a pilot.
- **Selling:** only reserve mechs (not force-group mechs) can be sold. The
  refund is the **full variant price (100%)**. There is no depreciation.
- **Accept vs back-out:** the screen snapshots the reserve on entry. Leaving
  without **Accept** sells everything and rebuys the snapshot at the same
  prices, so the net effect is a full revert (:346–370).
- Purchase is reachable only when `PlayPurchasing` is set.

**Remake note:** 100% sell-back plus 100% component refunds in the lab make
C-Bills fully liquid. Total value = C-Bills + Σ inventory variant prices.
This is faithful behaviour; keep it unless a balance pass decides
otherwise.

### 5.3 Bonus technology

The objective action `MakeNewTechnologyAvailable` (`PurchaseFileName =
"data\missions\PurBonusNN.fit"`) appends that file to the campaign's
additional purchase files the moment it executes (Objective.cpp:1255–1276).
The file persists in saves.

| Bonus file | Granted in | Unlocks |
|---|---|---|
| PurBonus08 | mc2_08 | pilot Claymore |
| PurBonus11 | mc2_11 | Swarm LRM5 (123), Clan ER Laser (152), Clan ER Large Laser (150), Clan Pulse Laser (153), Clan Large Pulse Laser (151), Clan ER PPC (154) |
| PurBonus13 | mc2_13 | pilots Payback, Nuke |
| PurBonus19 | mc2_19 | Long Tom Cannon (160) |
| PurBonus20 | mc2_20 | pilots Ghost, Mother, Rooster |
| PurBonus21 | mc2_21 | Thunderbolt Missile (161) |

---

## 6. Salvage

### 6.1 In-mission versus post-mission

There are **two** ways to gain enemy mechs.

**In-mission recovery (free of C-Bills; costs support RP):**
- The **Recovery Team** support unit (enabled by
  `SalvageCraftEnabledDefault`) repairs a **disabled** mech in the field and
  crews it with the best reserve pilot (§3.3).
- Capturing a capturable mech does the same (see
  `capture-and-objectives.md` Part A).
- The recovered mech joins the player's commander and fights for the rest of
  the mission. If it is not disabled or destroyed at the end, it **joins the
  inventory with that pilot and a force-group slot** (§7.1).

**Post-mission salvage screen (costs C-Bills):** shown when `PlaySalvage`
is set.

### 6.2 Salvage screen (SalvageMechArea.cpp:140–320, 390–575)

**Candidates:** every mech object in the mission that is:
- **disabled but not destroyed**, and
- not an air unit (helicopters are excluded),
- **of any team.**

They are listed sorted by variant price, ascending.

The candidate list is built *after* the inventory update (§7.1). The
player's own mechs disabled in the mission were just removed from the
inventory, so **they appear here too, and must be bought back**.
**Ambiguity:** this is what the code says; it is unclear whether the
designers intended it. Keeping it is recommended, because it gives
"disabled" a real meaning distinct from "destroyed".

Each candidate row shows:
- chassis name, variant name, tonnage;
- **salvage price = 80% of the variant's price** (`costToSalvage = 0.8 ×
  getCost`, :398), truncated to an integer for display.

**Interaction:**
- Ticking a row immediately deducts its price; unticking refunds it.
- An unticked row is disabled while its price exceeds current C-Bills.
- There is no tonnage or count limit.
- **Done** commits: every ticked mech is added to the **reserve**, with no
  pilot and no force-group slot, as its designer variant (:304–312).

**Ambiguity:** if a candidate's `variantName` matches no logistics variant,
its price is never computed. Shipped data always matches. A remake should
skip such units.

Destroyed mechs (as opposed to disabled ones) are never salvageable.

---

## 7. Repair, losses and death

### 7.1 Inventory update on a win (setMissionCompleted, LogisticsData.cpp:1308; logistics.cpp:137–140)

1. **Every force-group mech is deleted from the inventory**
   (`removeMechsInForceGroup`). Reserve mechs are untouched.
2. Objective payouts are added (§9).
3. The game walks the player's roster in reverse. For each **BattleMech**
   that meets all of these:
   - under the player's commander,
   - shown on the player's GUI (i.e. it actually joined the player),
   - not airborne,

   it does the following:
   - If it is **neither destroyed nor disabled**, a **fresh** mech of the
     same variant is added to the inventory, with its pilot and the next
     force-group slot (1, 2, …).
   - If it **is** destroyed or disabled, it is not re-added. It is **lost**:
     buy it back via salvage if it was only disabled.
   - Either way, the pilot is updated from the mission (§8.3).

   This covers both the original force and mechs recovered or captured
   during the mission.
4. The force group after a win is therefore "every mech that walked out",
   in the same slots, ready for the next mission.

Step 3 has an unused branch that re-adds survivors found in the inventory.
After step 1, survivors are never found there, so every survivor goes
through the "recovered" branch. The outcome is identical.

### 7.2 Repairs

- **Repairs are free and total.** Re-adding a survivor creates a new mech
  from its variant: full armour, full internals, full ammo.
- There is no repair cost or repair screen, and damage does not carry over.
- The in-mission **Repair Vehicle** support only matters inside a mission.

### 7.3 Destroyed or disabled mechs

| Fate in mission | Inventory after a win | Can the player get it back? |
|---|---|---|
| Survived | Re-added, repaired, same pilot, in force group | — |
| Disabled (including a pilot killed or ejected) | Removed | Yes, salvage at 80% (§6.2) |
| Destroyed | Removed | No |
| Any outcome, mission **lost** | Unchanged (retry) | — |

### 7.4 Pilots of lost mechs

| Warrior status | Effect |
|---|---|
| `DEAD` | Pilot flagged `dead` permanently (saved). Never available again. Listed under "Killed in Action" on the review screen. |
| `EJECTED` | Survives. Gets the normal mission update (skills, kills, `missionsCompleted`). Returns to the reserve roster. |

A pilot can be killed in two ways:
- **By wounds.** At 6 wounds the pilot dies, unless the pre-rolled ejection
  succeeds. The ejection roll is d100 ≤ piloting + 30, and < 95
  (warrior.cpp:1189). Toughness Specialists always escape. A successful
  ejection leaves the pilot at 3 wounds. Source: warrior.cpp:1932–1975.
- **On voluntary ejection.** Ejecting adds 1 wound. A pilot with 6 or more
  wounds after that dies (warrior.cpp:1994–2006).

---

## 8. Pilots

### 8.1 Roster and "hiring"

- **The roster file:** `Data/Objects/Pilots.csv` lists 53 profile names,
  campaign `pmw*` and multiplayer `pmp_*`. Every one is instantiated at
  campaign start (LogisticsData.cpp:186).
- **Initial values from each profile** (`Data/Missions/Warriors/<name>.FIT`):
  name (`DescIndex` string), photo, gunnery, piloting and specialty flags.
  Rank is **recomputed from skills** (§8.4), ignoring the file's `Rank`.
- **There is no hiring cost.** A pilot is usable only while listed in the
  current purchase file or a bonus file, and not dead.
- **Pilots drop out again** if a later purchase file omits them. The shipped
  files only add pilots.
- **Campaign availability over time:**
  - from Purchase01: 15 pilots (Chopper, Cobra, Creep, Dagger, Flash,
    Hacksaw, Hammer, Jinx, Longshot, Meat, PaleRider, Psycho, Shadow,
    Twitch, Worm);
  - Steel from Purchase06;
  - Bubba, Scooter, Venom and Wicked from Purchase19;
  - the bonus pilots in §5.3.

The converted `game/data/pilots.json` holds all 76 profile FITs keyed by
lowercase name. It includes the support-unit crew profiles (PMWRepair,
PMWScout and others), which are not on the roster.

**Quirk:** some profiles spell the sensor specialty as `ReconSpecialist`,
but the code looks for `SensorProfileSpecialist`, so the misspelt key is
silently ignored. All shipped profiles with that key set it to 0. Accept
both spellings, or neither.

### 8.2 Experience during a mission (warrior.cpp)

Skill points accumulate per mission in `skillPoints[skill]`.

**Gunnery** gains, on each kill credited to the pilot (`handleKilledTarget`,
:7033–7098; values from `gamesys.fit [Skills] KillSkillValues`):

| Killed | Points |
|---|---|
| Light mech | 45 |
| Medium mech | 60 |
| Heavy mech | 70 |
| Assault mech | 80 |
| Ground vehicle (only one with path locks) or helicopter | 20 |
| Elemental | 6 |

Turrets, gates and buildings give 0.

**Piloting** gains:
- `Skill Success[PILOTING] = 1.0` on each successful piloting check. The
  only live check is the ejection roll (warrior.cpp:1939–1947).
- `Skill Attempt` values are all 0.

`WeaponHit = 3.0` and `SkillIncreaseCap = 3` are read from `gamesys.fit`
but **never applied**. The hard-coded rules below govern instead.

### 8.3 End-of-mission update (wins only)

For every player mech pilot, whether the mech survived or not
(`MechWarrior::updateMissionSkills` :7224 then `LogisticsPilot::update`
LogisticsPilot.cpp:255):

1. **gunnery += 0.01 × gunnery points**, so a heavy-mech kill is worth
   +0.7.
2. **piloting += 1** ("for coming along"), plus the piloting points.
3. Both skills are capped at **80**.
4. Each skill's gain this mission is capped at **+4.0**. The excess is
   discarded.
5. Kill totals are updated:
   - mech kills = light + medium + heavy + assault;
   - vehicle kills = ground (helicopters count here);
   - infantry kills = elementals.
6. `missionsCompleted += 1`, and the mission's slot is set in
   `missionsPlayed`.
7. A pilot whose status is `DEAD` gets `dead` and `justDied`.
8. **Medals** (stored per pilot, shown on review):
   - **Valor:** 3–6 non-air mech kills this mission.
   - **Uncommon Valor:** 7 or more.
   - **Purple Heart:** any wounds this mission.
   - **Campaign ribbons:** for having played any mission of operation 1
     (mission ids 0–8), 2 (9–16) or 3 (17–23).
   - **"Full" ribbons:** for having played all missions of that operation.
   - **House medals:** for missions id 8, 12 and 21.
9. Specialty flags the warrior held in mission are copied back. This is a
   no-op unless something granted one mid-mission.

The mission id is a running index: the sum of the mission counts of earlier
groups plus the index within the group (LogisticsMissionInfo.cpp:757).

**Consequence for pacing:**
- **Piloting** rises about +1 per mission.
- **Gunnery** rises slowly: an average mission with three medium kills gives
  +1.8.
- A pilot starting at an average of 49.5 (Flash) takes several missions to
  pass 50 and reach Regular.

### 8.4 Ranks and promotion

**Rank** comes from the average of gunnery and piloting
(`turnAverageIntoRank`, LogisticsPilot.cpp:517):

| Average | Rank |
|---|---|
| ≤ 50 | Green |
| > 50 | Regular |
| > 60 | Veteran |
| > 70 | Elite |
| > 79 | Ace |

`gamesys.fit WarriorRankScale` (45/56/66) is **not** used by logistics.

**Promotion** (`promotePilot`, :485) applies when the rank computed from the
pre-mission skills differs from the new one and the new rank is above Green.

**Pilot review screen** (PilotReviewArea.cpp, `PlayPilotPromotion`):
- It lists:
  - "Killed in Action": pilots with `justDied` who were used this mission;
  - "Active Duty": surviving pilots who were used this mission. Each entry
    shows rank, gunnery/piloting meters with this mission's gain
    highlighted, kill icons and new medals.
- Pilots who did not deploy are not shown.
- **Done** is disabled while any promotion is pending.

**Promotion pop-up:**
- Each promoted pilot gets one, and the player must **pick exactly one new
  specialty skill**. The offered list contains every specialty, from the
  Regular tier up to the pilot's new tier, that the pilot does not already
  have (:1497–1560).
- Tiers (FIRST_*_SPECIALTY, warrior.h:244–247):

| Tier | Skills offered |
|---|---|
| Regular (0–7) | Light Mech, Laser, Light AC, Medium AC, SRM, Small Arms, Sensor Profile, Toughness |
| Veteran (8–13) | Medium Mech, Pulse Laser, ER Laser, LRM, Scout, Long Jump |
| Elite (14–19) | Heavy Mech, PPC, Heavy AC, Short Range, Medium Range, Long Range |
| Ace (20–22) | Assault Mech, Gauss, Sharpshooter |

- The combat effects of each specialty belong in the combat spec, not here.
- Jumping two ranks in one mission still grants only **one** pick. This is
  unlikely given the +4 cap.

### 8.5 Wounds and healing

Wounds exist only inside a mission, starting from the profile's
`[Status] Wounds`, which is 0 in shipped data. They are never stored in
logistics, so **every surviving pilot is fully healed for the next
mission.** There is no injury downtime.

### 8.6 Death

- Death is permanent.
- The pilot's record (kills, medals) is saved with `Dead = true`.
- The pilot is excluded from every availability list from then on.
- The pilot's mech was disabled at the moment of death, so it goes to
  salvage (§6.2).

---

## 9. Mission rewards and income

On a win, in this order (LogisticsData.cpp:1308–1330,
LogisticsMissionInfo.cpp:798–801):

1. **`AdditionalCBills`** of the mission is added on completion.
   **Quirk:** `setNextMission` also adds and subtracts it when the player
   changes selection (:660–675). This can double count or go negative when
   switching between missions. Every campaign mission has
   `AdditionalCBills = 0`, so it is moot. **Recommendation:** pay it once
   on completion only.
2. For each player objective whose status is **successful** at mission end,
   its **`ResourcePoints` are added as C-Bills**. This covers primary,
   secondary and hidden objectives alike. Failed or undetermined objectives
   pay nothing. See `capture-and-objectives.md` B6.
3. Salvage spending (§6) and later purchases come out of the result.

**Other sources:**
- 100% sell-back of mechs (§5.2).
- Lab refunds for stripped components (§4.4).

**Not income:**
- `[MissionSettings] ResourcePoints` is the **in-mission support budget**
  (air strikes, recovery team and so on).
- So are RP gained in a mission from captured RP buildings or ordnance
  trucks (bldng.cpp:969, gvehicl.cpp:3141).
- Neither converts to C-Bills.
- A debug key in missiongui.cpp:1113 adds +10000 RP; this is not a feature.

---

## 10. Numbers reference

### 10.1 Rules and rates

| Quantity | Value | Source |
|---|---|---|
| Starting C-Bills | 80000 | campaign.fit `[Campaign] CBills` |
| Groups in campaign | 13 (24 missions) | campaign.fit |
| Default DropWeightLimit | 300 | LogisticsMissionInfo.cpp:314 |
| Max force-group size (SP) | 12 | LogisticsData.cpp:601, 1856 |
| Drop weight counts | chassis tonnage | LogisticsData.cpp:1835–1848 |
| Mech purchase price | chassis base cost + Σ component cost | LogisticsVariant.cpp:493–501 |
| Mech sell price | 100% of variant price | LogisticsData.cpp:487–508 |
| Lab change cost | new price − old price (refunds allowed) | LogisticsData.cpp:2040, 2117; MechLabScreen.cpp:1031–1035 |
| Salvage price | 80% of variant price | SalvageMechArea.cpp:398 |
| Salvage candidates | disabled, not destroyed, not air, any team | SalvageMechArea.cpp:156 |
| Repair cost | 0 (always full repair) | LogisticsMech.h:73–82, LogisticsData.cpp:1370–1388 |
| Armour per plate | +32 | LogisticsVariant.cpp:566, 680 |
| Heat capacity per heat sink | +4 (`compbas` damage col) | LogisticsVariant.cpp:582–593 |
| Max jump-jet items | 1 | LogisticsVariant.cpp:608–611 |
| Displayed weight | 20% of tonnage + 7 + Σ component weight (not enforced) | LogisticsVariant.cpp:509 |
| Gunnery XP per kill | L 45, M 60, H 70, A 80, vehicle/copter 20, elemental 6 points | gamesys.fit `KillSkillValues`; warrior.cpp:7033–7097 |
| Gunnery gain | 0.01 × points | warrior.cpp:7231 |
| Piloting gain | +1 per won mission + 1 per successful ejection check | warrior.cpp:7235–7237, 1939–1947 |
| Skill cap | 80 | warrior.cpp:7228 |
| Max gain per skill per mission | +4.0 | LogisticsPilot.cpp:292–305 |
| Rank thresholds (avg of G and P) | > 50 Regular, > 60 Veteran, > 70 Elite, > 79 Ace | LogisticsPilot.cpp:517–529 |
| Specialty picks per promotion | 1 | PilotReviewArea.cpp:1369–1397 |
| Valor / Uncommon Valor | 3–6 / ≥ 7 non-air mech kills in a mission | LogisticsPilot.cpp:345–355 |
| Death wounds | 6 | warrior.cpp:1933, 1961 |
| Ejection success roll | d100 ≤ piloting + 30 and < 95; always for Toughness | warrior.cpp:1189–1191 |
| Wounds after successful ejection | 3 | warrior.cpp:1945 |
| Spawn ring radius / spacing | 128 world units, 360°/N | logistics.cpp:725, 754 |
| Save version | 10004 | LogisticsData.cpp:39 |

### 10.2 Per-mission settings (from the mission FITs)

"Objective C-Bills (max)" is the sum of every team-0 objective's
`ResourcePoints`. It is an upper bound, because hidden or secondary
objectives may not all be achievable.

| Mission | Drop limit (t) | Support RP at start | Objective C-Bills (max) |
|---|---|---|---|
| mc2_01 | 190 | 22000 | 43000 |
| mc2_02 | 170 | 6000 | 50500 |
| mc2_03 | 190 | 16000 | 58000 |
| mc2_04 | 205 | 16000 | 62500 |
| mc2_05 | 220 | 7000 | 79000 |
| mc2_06 | 260 | 25000 | 69000 |
| mc2_07 | 200 | 6000 | 69000 |
| mc2_08 | 160 | 0 | 69000 |
| mc2_09 | 300 | 30000 | 90000 |
| mc2_10 | 280 | 6000 | 80000 |
| mc2_11 | 160 | 0 | 53000 |
| mc2_12 | 210 | 0 | 79000 |
| mc2_13 | 230 | 0 | 92000 |
| mc2_14 | 75 | 0 | 87000 |
| mc2_15 | 320 | 6000 | 74500 |
| mc2_16 | 320 | 16000 | 78000 |
| mc2_17 | 350 | 0 | 0 |
| mc2_18 | 320 | 16000 | 96000 |
| mc2_19 | 330 | 12000 | 148000 |
| mc2_20 | 320 | 12000 | 94000 |
| mc2_21 | 200 | 23000 | 120000 |
| mc2_22 | 380 | 16000 | 95000 |
| mc2_23 | 300 | 36000 | 147000 |
| mc2_24 | 450 | 10000 | 205000 |

`AdditionalCBills = 0` for all 24 missions.

### 10.3 Purchase-file progression (mechs and components added)

| File | Mech chassis on sale | Components added (compbas ids) | Pilots added |
|---|---|---|---|
| 01 | werewolf, hunchback, bushwacker | 7, 10, 25, 100, 101, 102, 114, 120, 125, 140, 145, 155, 156 | 15 starting pilots |
| 03 | + shootist | — | — |
| 04 | + zeus | 142, 144 | — |
| 05 | + hollander | 99, 104 | — |
| 06 | + highlander | 141, 143, 146 | Steel |
| 09 | + atlas | — | — |
| 10 | **replaced by** anubis, shayu, starslayer | 103, 108, 112 | — |
| 11 | + raven, menshen | — | — |
| 13 | + catapult, laohu | — | — |
| 14 | + cyclops | 109, 110, 111, 113, 130, 135 | — |
| 18 | **replaced by** uller, wolfhound, shadowcat, enfield, vulture, jaegermech | — | — |
| 19 | + madcat | — | Bubba, Scooter, Venom, Wicked |
| 22 | + bloodasp | 139, 147 | — |

Files 02, 07, 08, 12, 15–17, 20, 21, 23 and 24 repeat the previous list.
The chassis on sale change completely at operations 2 and 3, but
components only ever accumulate.

### 10.4 Mech-lab components (compbas.csv; cost in C-Bills, footprint W×H)

| Id | Name | Heat | Cost | W×H | Range |
|---|---|---|---|---|---|
| 7 | Heat Sink (+4 capacity) | 0 | 2000 | 1×1 | — |
| 10 | Jump Jets (JJ slot) | 7 | 6000 | — | — |
| 25 | Armor Plating (+32 armour) | 0 | 3000 | 1×1 | — |
| 99 | Light Gauss Rifle | 1 | 7200 | 2×3 | long |
| 100 | Light Autocannon (AC5) | 1 | 3500 | 2×2 | long |
| 101 | Autocannon (AC10) | 2 | 5300 | 2×3 | medium |
| 102 | Heavy Autocannon (AC20) | 7 | 7100 | 2×4 | short |
| 103 | Light Ultra AC5 | 1 | 5500 | 2×2 | long |
| 104 | Gauss Rifle | 1 | 15300 | 2×4 | long |
| 108 | Ultra AC10 | 4 | 8000 | 2×3 | medium |
| 109 | Clan Heavy Ultra AC20 | 8 | 14200 | 2×4 | short |
| 110 | Clan Light Ultra AC5 | 1 | 7500 | 2×2 | long |
| 111 | Clan Ultra AC10 | 3 | 10200 | 2×3 | medium |
| 112 | Heavy Ultra AC20 | 8 | 11800 | 2×4 | short |
| 113 | Clan Gauss Rifle | 1 | 18500 | 2×4 | long |
| 114 | MG Array | 0 | 900 | 1×1 | short |
| 120 | LRM5 Rack | 2 | 1700 | 1×1 | long |
| 123 | Swarm LRM5 Rack | 2 | 2600 | 1×1 | long |
| 125 | Streak SRM2 Pack | 2 | 2000 | 1×1 | short |
| 130 | Clan LRM5 Rack | 4 | 4500 | 1×1 | long |
| 135 | Clan Streak SRM2 | 2 | 2200 | 1×1 | short |
| 139 | Clan Heavy Laser | 7 | 4700 | 1×1 | short |
| 140 | Large Laser | 8 | 3800 | 1×2 | medium |
| 141 | ER Large Laser | 12 | 5300 | 1×2 | long |
| 142 | Large Pulse Laser | 10 | 5000 | 1×2 | medium |
| 143 | ER Laser | 5 | 3000 | 1×1 | medium |
| 144 | Pulse Laser | 4 | 2000 | 1×1 | short |
| 145 | PPC | 10 | 5700 | 1×3 | medium |
| 146 | ER PPC | 15 | 8000 | 1×3 | long |
| 147 | Clan Heavy Large Laser | 18 | 15000 | 1×2 | medium |
| 150 | Clan ER Large Laser | 12 | 7700 | 1×2 | long |
| 151 | Clan Large Pulse Laser | 10 | 6000 | 1×2 | medium |
| 152 | Clan ER Laser | 5 | 4500 | 1×1 | medium |
| 153 | Clan Pulse Laser | 4 | 2400 | 1×1 | short |
| 154 | Clan ER PPC | 15 | 14900 | 1×3 | long |
| 155 | Flamer Array | 7 | 1800 | 1×1 | short |
| 156 | Laser | 3 | 1700 | 1×1 | short |
| 160 | Long Tom Cannon | 20 | 29300 | 2×5 | long |
| 161 | Thunderbolt Missile | 8 | 16400 | 2×4 | medium |

The per-variant item rows in the chassis CSVs carry an older `C-Bills`
column (for example, Laser 1200). **Logistics ignores it** and prices from
`compbas.csv`.

### 10.5 Example chassis (computed with the rules above)

| Chassis (CSV) | Tons | Grid | Heat cap | Armour base/max | Base cost | Prime price, heat used/cap |
|---|---|---|---|---|---|---|
| werewolf ("Razorback Prime") | 30 | 4×2 | 22 | 80/144 | 22250 | 41750, 19/22 |
| hunchback | 50 | 3×4 | 24 | 80/240 | 24250 | 46750, 20/24 |
| bushwacker | 55 | 4×4 | 27 | 112/272 | 34750 | 56550, 18/27 |
| shootist | 70 | 3×6 | 30 | 130/290 | 36750 | 63550, 24/30 |
| zeus | 80 | 5×4 | 72 | 130/258 | 48000 | 87500, 58/72 |
| atlas | 100 | 6×5 | 43 | 80/432 | 49000 | 106600, 43/43 |

The starting force (Razorback plus 2 Bushwackers) is worth 154850 at
purchase prices. 140 t fits mc2_02's 170 t limit.

---

## 11. Build order for the remake (smallest viable first)

1. **Campaign state + progression + save.**
   - C-Bills, the inventory of `(variant, pilot?, slot)`, the pilot roster
     with skills and flags, the group/mission state machine (§2.2, including
     hidden finales) and bonus files.
   - Wins apply objective payouts and survivor re-add (§7.1); losses retry.
   - JSON save and autosave.
   - Mission 1 runs quick-start from its FIT parts.
2. **Mission select → mech bay → pilot ready → launch.**
   - Operation map, drop-weight and 12-slot validation, pilot assignment.
   - Spawning the chosen force at the first team-0 part position on the
     128-unit ring.
   - Suppressing the FIT's own commander-0 parts (§3.4).
3. **Post-mission results.**
   - The salvage screen (80% buy-back of disabled mechs, any team).
   - The pilot update: XP rules, +4 cap, ranks, medals, death.
   - The pilot review with one specialty pick per promotion.
4. **Purchasing and availability.**
   - Purchase-file parsing and the availability recompute on mission
     select, with whole-mech buy and 100% sell.
5. **Mech lab.**
   - Grid placement with footprints, the heat-capacity, armour-cap and
     single-JJ rules, cost deltas, and named player variants.
   - Spawning custom loadouts in combat.
   - This needs the converter to add the grid size, the component footprint
     and the logistics-visible flag (§4.4).
