# How the original MC2 campaign missions played

Research for the balance questions in `docs/reports/playtest/2026-10-23/README.md`. It covers what human
players reported about each of the 24 campaign missions of MechCommander 2 (2001), and what that means
for our bot. Compiled 2026-10-23.

## Sources

The tags below are used throughout. Every claim in a mission section is tagged with its source(s).

| Tag | Source | Notes |
|---|---|---|
| **KC** | Kasey Chang, *MechCommander 2 Unofficial Strategy Guide and FAQ*, 30 Aug 2002. GameFAQs FAQ 19037; mirror: <https://the-spoiler.com/OTHER/Microsoft/mechcommander.2.1.html> | Full walkthrough of all 24 missions. It numbers the missions 1–24 in the same order as `mc2_01`…`mc2_24` and documents the `-mission mc2_xx` switch. Lists start RP, drop weight, lance and enemies for each mission. C-bill figures are for Regular. |
| **BK** | Briareos_Kerensky, *FAQ/Walkthrough*, GameFAQs FAQ 14088 (2001–, v3.x). <https://gamefaqs.gamespot.com/pc/914327-mechcommander-2/faqs/14088>, read from the Wayback copy of 2019 (GameFAQs itself returns 403). | Full walkthrough, played on **Regular**. Gives the most exact enemy rosters, wave by wave. Its mission names are campaign-relative (Liao "Mission 4B" = mc2_14). |
| **CB** | "relayer", *Company B MC2 Strategy Guide*, one page per mission: <https://the-spoiler.com/OTHER/Microsoft/mechcommander.2.2/sgm2o17.htm> (pattern `sgm1o1`–`sgm1o9`, `sgm2o10`–`sgm2o17`, `sgm3o18`–`sgm3o24`) | All 24 missions. Played by an experienced player who builds Ace sharpshooters and snowballs on field salvage. The header numbers (RP, weight) have typos in several places, so for those use KC, BK or the data. |
| **SOE** | Standard of Entertainment, *MechCommander 2 Strategy Guide*: <https://standardof.net/games/mechcommander-2/> | Covers Steiner 1–7 and Liao 1–3 only (mc2_01–mc2_13). Written for **Veteran** difficulty and has a video walkthrough per mission. |
| **MK** | The Magnus Kit, "Let's Look At: MechCommander 2", 2016: <https://themagnuskit.squarespace.com/reviews/2016/4/8/lets-look-at-mechcommander-2> | A review. Only general remarks about difficulty. |
| **SR** | speedrun.com MechCommander 2 leaderboards, read through the API (game `nd2e2w5d`): <https://www.speedrun.com/mechcommander_2/levels> | Solo-mission any% records. Almost all were run on Green, v1.0. These are speedruns, not typical play times. |

Things that could not be reached: GameFAQs message boards (403), the MWO forum thread "Remember MechCommander
2?" (bot check), the Sorcerer's Place thread (403), YouTube transcripts. I found no Reddit or Steam threads about
MC2 missions: the game was never sold on Steam or GOG. Sarna.net mission pages only retell the story, so they are
not used.

**How much to trust each mission section.**
- Missions with KC, BK and CB (all 24), plus SOE for 1–13, are **well-sourced on tactics and enemy mix**: two
  to four independent written walkthroughs agree.
- **Thin everywhere:** typical losses and completion times. No source gives casualty rates. Times exist only as
  speedruns.
- **Difficulty compared with other missions:** each author gives an opinion, but there is no community consensus
  to quote. I mark each rating with whose opinion it is.

## What applies to every mission

### Difficulty settings (well-sourced)

- **The levels:** Green, Regular, Veteran and Elite (SR's difficulty variable). KC calls the lowest "Recruit".
  These map to gamesys `DifficultySettings` index 0–3. Our sim's default `difficulty := 1` is **Regular**.
- **What a level changes:** BK played Regular and some missions on Elite. He says the enemy units, AI, drop
  weights and C-bills are the same; "the only real difference is that your weapons are less efficient … the
  damage value is almost halved". He guesses Green multiplies your damage by 1.5–2 and Veteran divides it by 1.5.
  That matches gamesys `PlayerWeapons` 125/100/75/50. [BK]
- **The remake implements to-hit only:** it applies `PlayerSkills` and `EnemySkills` to to-hit
  (`sim_combat.gd:17`). I found no use of `PlayerWeapons` or `EnemyWeapons` in `game/scripts`. That makes no
  difference at Regular, where both are 100.
- **Regular is easy, by every author's account:**
  - SOE: "Regular difficulty is so easy it requires no real special tactics, while Elite … Centipedes and
    Harassers will smash the cockpits of Medium and Heavy mechs … forcing many restarts". SOE wrote its guide for
    Veteran, "no walk in the park".
  - MK: "The game is fairly easy on all of the difficulty settings except for the highest one, borderlines
    unfair", though "some of the later missions are decently challenging".
  - KC: "If the game's too hard, play at an easier difficulty level (yes, you can switch in the middle of a
    campaign)."
- **No author describes any campaign mission as unwinnable** on Regular. The ones they call hard come with a
  stated trick: "if you do this wrong … VERY hard … if you do this right … NOT that hard" (KC on mc2_12; the same
  framing for 15 and 23).

### Tactics every source relies on (well-sourced)

All three full walkthroughs build almost every mission from the same five tools:

1. **Capture turret controls and fight inside your captured turrets.** Lure the enemy into them ("tease them
   out", KC 7.3.1/7.3.2). Destroy the generator or control instead of the turrets.
2. **Capture repair bays and use them instead of repair trucks.** KC: "It's best to capture repair bays and use
   them instead of your RPs".
3. **Fixed artillery (Long Tom, 8000 RP).**
   - BK places 2–4 Long Toms in mc2_03, 06, 10, 12, 15, 16, 18, 19, 22, 23 and 24. KC uses them in 02, 03, 09,
     12, 15, 18, 22 and 23.
   - Players use them to break waves, then let the mechs finish.
   - Minelayers (4000 RP) are used on wave missions: 06, 12, 18 and 23.
4. **Blow fuel tanks and ammo dumps as the enemy passes them.** This is the standard opener in mc2_03, 05, 06,
   07, 08, 13 and 18, and the standard way to kill bosses in 11, 14, 17 and 24.
5. **Capture every RP building and truck first, and spend all RP on field salvage.**
   - RP doesn't carry over between missions (KC 7.8.2).
   - A salvaged mech joins the fight. CB "reinforces in-field": "Drop with 6 mechs, Extract with 15" (mc2_19),
     and a 16-mech force for mc2_22.

**Also used:**
- A **jump-jet mech** in nearly every lance, for jump-capturing controls over walls. KC 7.1.4 / 7.5.4 says
  you can capture a building in mid-air.
- A **sensor or ECM scout.**
- **Height:** "MC2 awards a BIG bonus for shots fired from higher-up" (KC 7.2.2).
- **Hold position** to keep a firing line (KC 7.2.6, CB).
- **Aimed head shots** by sharpshooter pilots, to salvage mechs intact (CB, from mc2_16 on).

KC: "The game relies on trigger points … If you don't do certain things, the enemies do not react, and you can
repair/reload to your heart's content." That is why every guide paces missions as a series of separate fights.

### "No-support" missions are only zero-RP at the start (well-sourced, and checked in our data)

The README treats 8, 11, 12, 13, 14 and 17 as no-support missions. They don't all play that way:

| Mission | Start RP (data) | Capturable RP buildings (data, `maps/*/objects.json`) | Repair bays (data) | What players do |
|---|---|---|---|---|
| mc2_08 | 0 | 5 = 50,000 RP | 0 | "there are FOUR resource buildings around, so you can resurrect a few mechs" [KC]. One is on an island and needs jump jets [KC, SOE, CB]. "try to use no more than one repair track" [KC, CB]. |
| mc2_11 | 0 | 8 = 68,000 RP | 1 | Jump to the island RP building and RP truck at the start [SOE: "necessary to capture 14,000 RPs at the start"]. Take the 5 RP buildings in the Davion base and salvage the 5 Davion mechs in the yard [KC, BK, CB]. |
| mc2_12 | 0 (BK and SOE say 10,000) | 5 = 50,000 RP | 0 | "You should now have 50000 RPs, so drop 2 fixed artillery … Save the rest for a repair track" [KC]. BK drops 4 Long Toms and a repair truck. |
| mc2_13 | 0 | none | 2 | "NO SUPPORT. No salvage, no repair" [KC], but "TWO repair bays on this map" [KC, CB]. It is played from bay to bay and turret fort to turret fort. |
| mc2_14 | 0 | none | 3 | One 75 t jumper. Capture turret forts and repair at three bays [KC, BK, CB]. |
| mc2_17 | 0 | none | 2 | Run to the abandoned Steiner base, take its 2 turret controls and 2 repair bays, and hold [KC, BK, CB]. |

So 8, 11 and 12 are effectively RP missions once the RP buildings are taken: 50–68k RP is 6–8 repair trucks, or
artillery plus repair. 13, 14 and 17 have no RP, but each has 2–3 repair bays and capturable turrets that the
whole plan is built on.

### Remake gaps that bear on this (from the repo, not from the web sources)

I checked these in the code to read the sources against. They are not player reports. I did not edit any code.

- **Turrets don't appear to be simulated.**
  - `SimMission` loads only object class 1, buildings (`sim_mission.gd:202`). Turrets are class 21 in
    `objects.json`, e.g. mc2_22 has 27 LargePulseCannonTurret, 26 LRMTurret and 25 MediumAutoCannonTurret.
  - There is no turret module in `game/scripts/sim/`.
  - The 2026-10-23 sweep logs show no turret damage, even in mc2_13, which all guides describe as full of
    Gauss and AC turret forts.
- **Bandit and Liao turret controls are flagged not capturable.**
  - `BTurretControl.fit` (17 placements across mc2_03, 07, 08, 09) and `LiaoTurretControl.fit` (26 across
    mc2_04, 05, 07, 08, 19, 20, 22) have `capturable: false` in `objects.json`.
  - The original makes a turret's parent building capturable at load (`turret.cpp:551`, cited in
    capture-and-objectives.md A1). `tools/convert/map_objects.py` reads `parent` but doesn't write it out.
  - Players capture these controls in mc2_03, 05, 08, 09, 19 and 22.
- **Not implemented:** repair bays, the artillery piece and the minelayer. `sim_support.gd:9` says "Not yet:
  minelayer, scout copter, artillery piece". I found no repair-bay code.
- **Heat is on for mechs only.** The original's heat was compiled out (combat-rules.md "Heat", change H*). In
  the remake, heat throttles player and enemy mechs but not vehicles (`sim_vehicle.gd:21`) or structures.
- **Ammo is finite.**
  - support-powers.md:188–191 says single-player **unlimited ammo defaults to TRUE** in the original
    (prefs.cpp:143) and makes every bin infinite.
  - `sim_combat.gd:100` always spends ammo, and I found no unlimited-ammo option.
  - KC confirms the player-facing option: weapons "can run out of ammo (if you have turned off 'unlimited
    ammo')".

### Data discrepancies against the guides

Most start-RP and drop-weight figures in KC and BK match our data exactly. The exceptions:

| Mission | Our data | Guides | Comment |
|---|---|---|---|
| mc2_05 | 220 t | BK and SOE: 200 t. KC and CB: 220 t. | Two against two |
| mc2_12 | 0 RP | BK and SOE: 10,000 RP. KC and CB: 0 RP. | Two against two |

SR lists two game versions, 1.0 and 1.1. A version difference is a plausible but **unproven** explanation.
Worth checking against a retail 1.1 `mc2_05.fit` and `mc2_12.fit` if one is available.

---

## Steiner campaign (mc2_01–mc2_09)

KC: "The Steiner campaign is relatively easy as it introduces you to the basics … without too many tricky
missions."

### mc2_01 Scouting Patrol

- **Data:** preset lance (2 Bushwacker, Razorback), 22,000 RP.
- **Forces:** hangar and infantry, Centipedes and LRM carriers, then 2 UrbanMechs and Harassers on the north
  island. The final group on the west island is 3 LRM carriers, 2 Harassers and a Starslayer, which power up
  when you land [BK, KC, CB].
- **Lance/support:** preset. Players save RP so they can salvage the Starslayer at the end [KC, CB].
- **Key tactic:** stay at range against the LRM carriers and kite the UrbanMechs. Bait across the water to
  split the final group [SOE, KC].
- **Difficulty:** "very simple … almost impossible to lose unless you purposely screw up" [KC].
- **Losses/time:** BK lost a Bushwacker to the Starslayer. SR record 2:36 (Green).
- **By difficulty:** nothing mission-specific.
- **Sourcing:** well-sourced (4 guides).

### mc2_02 Reacquisition: Base Gemini

- **Data:** 170 t, 6,000 RP, 5 RP buildings (50k).
- **Forces:** Fire Ants and UrbanMechs, LRM carriers, Harassers, Centipedes, a Partisan at the north gate, and
  SRM turret posts [BK, KC].
- **Lance/support:** 2 Bushwacker + 2 Razorback, or a Starslayer [KC, SOE]. Capture all 5 RP buildings and
  salvage 5 mechs at the end [KC, CB].
- **Key tactic:** take the RP building first. Jump-capture turret controls before the SRM turrets fire. Lure
  defenders out of Gemini North one by one; Long Tom optional [KC, BK, SOE].
- **Difficulty:** easy [all].
- **Losses/time:** SR 2:29 (Green).
- **Sourcing:** well-sourced.

### mc2_03 Ambush & Acquire: Mobile HQ

- **Data:** 190 t, 16,000 RP.
- **Forces:** checkpoint Fire Ants, an UrbanMech, Vedette and Harasser. A convoy of 2 Fire Ants and 2 Vedettes
  escorts the Mobile HQ. The weapons-facility base has 3 Fire Ants, an UrbanMech, Harassers and a Vedette. The
  counterattack is 2 Fire Ants, a Starslayer, an LRM carrier and a Vedette [BK].
- **Lance/support:** Shootist + 2 Bushwacker, or similar [KC]. 1–3 Long Toms on the ridge for the
  counterattack [BK, SOE].
- **Key tactic:** blow the fuel tanks as the defenders reach them; this also kills the turret generators [KC,
  BK]. Ambush the convoy from the hill. Don't capture the AC turrets before the HQ is taken, or they kill it
  [SOE] (cf. our C4 note).
- **Difficulty:** easy–moderate.
- **Losses/time:** SR 5:03 (Green).
- **Sourcing:** well-sourced.

### mc2_04 Search & Destroy: Bandit Convoy

- **Data:** 205 t, 16,000 RP, 3 RP buildings.
- **Forces:** a hill post of 4 Centipedes and 2 LRM carriers with reinforcements. Fire Ant escorts, 2 Sha Yu,
  2 UrbanMechs at the bridge, Harassers and Centipedes. The fort has 2 Anubis. Capturing the facility triggers
  choppers, then mechs and tanks [BK, KC].
- **Lance/support:** Zeus, Shootist, Starslayer [KC]. "stingy RP spending (1 repair only)" and salvage 4 [KC].
- **Key tactic:** hug the lake or water to skip the hill post [BK, SOE]. Take out the generator at the bridge
  fort. A fast mech captures the facility and everyone runs for extraction [KC].
- **Difficulty:** SOE: "where things begin to get hairy, story-wise". Otherwise easy.
- **Losses/time:** SR 2:43.
- **Sourcing:** well-sourced.

### mc2_05 Night Ops: Liao Raid

- **Data:** 220 t (BK and SOE say 200), 7,000 RP, 1 repair bay.
- **Forces:** Anubis pairs, 3 LRM carriers, a Vedette and 2 Partisans at the facility. The river crossing has a
  Storm and 4 Centipedes. The depot has 2 Sha Yu and 2 LRM carriers. The prison fort has Sha Yu, a Storm, LRM
  carriers and Centipedes. "There are many Storm tanks on this map … designed to be heavy mech killers" [SOE,
  BK].
- **Lance/support:** a sensor mech is "far more essential" at night [SOE]. Repair at the captured bay instead
  of trucks [KC].
- **Key tactic:** blow the tank farm. Ford the river in the north instead of taking the bridge [BK, SOE]. Capture
  the LRM turret control above the prison and lure defenders into it [KC, BK, SOE]. A fuel tank at the rear
  gate kills the sortie [BK reader tip, KC].
- **Difficulty:** moderate.
- **Losses/time:** SR 2:28.
- **Sourcing:** well-sourced.

### mc2_06 Defensive Counter: Base Aries

- **Data:** 260 t, 25,000 RP, 2 bays, 10 turret controls.
- **Forces:** four waves.
  - Wave 1 (NE): 2 Sha Yu, 7 LRM carriers, 2 Drillson, 3 Centipedes, 3 Hetzers.
  - Wave 2 (NW): 4 LRM carriers, 2 Starslayers, then 4 attack copters and a Starslayer.
  - Waves 3 and 4 together: W is 3 Storms, a Catapult and 2 Sha Yu; E is 3 Sha Yu and a Catapult [BK]. Many
    Liao mechs carry ECM [KC].
- **Lance/support:** heaviest available (Atlas, Highlander, Zeus) [KC, BK, SOE]. BK puts 4–5 Long Toms outside
  the walls. KC lays a minefield down the NE road.
- **Key tactic:**
  - Grab the sensor and turret controls early, "If you do not capture these positions early on, you will be
    unable to do so later" [SOE].
  - Blow the tank farm on wave 1 [KC].
  - Then fall back into the base and fight with its turrets and 2 repair bays [all].
- **Difficulty:** "a bit tougher than the other two [07, 08], so you may want to do those first" [KC].
- **Losses/time:** SR 7:25. The mission ends the moment the last attacker dies, so spend RP before then [KC, SOE].
- **Bot note:** matches the README diagnosis: hold the HQ, don't hunt.
- **Sourcing:** well-sourced.

### mc2_07 Sector Occupation: Garrison

- **Data:** 200 t, 6,000 RP.
- **Forces:** Vedettes, LRM carriers and troop transports. 2 minelayers lay a field. Catapults guard the chemical
  plant (Storm, pulse turrets). 2 Men Shen (ECM) guard the HQ [BK, KC, SOE].
- **Lance/support:** Highlander + 2 Bushwacker, or light jumpers [KC]. CB takes mechs under 35 t because mines
  don't trigger for light mechs [CB, SOE, KC].
- **Key tactic:** leave the HQ for last. Take the west and north first, then lure the HQ defenders into a fuel
  tank or the pulse-turret base [SOE, KC]. A scout is needed for the "destroy all" secondary.
- **Difficulty:** moderate.
- **Losses/time:** no SR record.
- **Sourcing:** well-sourced.

### mc2_08 Combat Rescue: Claymore (no RP at start)

- **Data:** 160 t, 0 RP, **5 RP buildings = 50k**, no repair bay, 10 Bandit turret controls (flagged not
  capturable in our data).
- **Forces:**
  - Road patrols: UrbanMech, Fire Ant, Harassers, Hetzers.
  - First airbase: SRM turrets and Hunters, 2 Fire Ants, a Starslayer.
  - Second airbase: Ravens, UrbanMechs, Fire Ants, Hunters, Harassers, a Starslayer [BK, KC, CB].
  - Claymore's Atlas joins mid-mission [all].
- **Lance/support:**
  - Highlander + Shootist [KC]. Starslayer + 2 Men Shen [SOE]. Men Shen with Bushwacker/Starslayer [BK].
    4 light/medium [CB].
  - A jumper is required for the island RP building [KC, SOE, CB].
  - "try to use no more than one repair track for the whole mission" [KC]; "You should have been able to do
    this mission with only one Repair Vehicle" [CB].
- **Key tactic:**
  - Lure the first patrol into the fuel tanks [SOE, CB].
  - Don't attack the first airfield from the west wall ("A frontal assault is madness" [BK]). Take the southern
    mini-base and its turret control first. Attack from the high ridge and jump-capture the turret controls
    [BK, CB, KC].
  - Take the second airbase through the "back door", not the pass [KC, SOE].
- **Difficulty:** none of the four authors calls it hard. KC rates mc2_06 the hardest of the 06/07/08 trio.
- **Losses/time:** SR 3:10 (Green).
- **Bot note:**
  - The bot loses 2/3 seeds by attrition at a 4:1 trade, "no repair possible". The original player repairs from
    50k captured RP and fights alongside captured turrets.
  - Fixing that needs RP-building capture on the route and turret capture. The latter is blocked: the Bandit
    controls aren't capturable in our data and turrets aren't simulated.
- **Sourcing:** well-sourced.

### mc2_09 Breach: Bandit Headquarters

- **Data:** 300 t, 30,000 RP, 7 RP buildings (52k).
- **Forces:** Swarm LRM carriers ("Keep moving or take severe leg hits" [KC]), Fire Ants, UrbanMechs, Hunters,
  Hetzers, Partisans and LRM turret posts. The leader is in a custom jumping Lao Hu with 2 Starslayers and
  UrbanMechs [KC, BK, SOE].
- **Lance/support:** heavy (Zeus, Shootist, Highlander, Men Shen) [KC]. Atlas, Zeus, Catapult, Men Shen [BK].
  Fixed artillery for the HQ push [KC]. SR runner: "More airstrike spam. It's a MechCommander's best friend!"
- **Key tactic:** go round the valley defences clockwise, collecting RP. Capture the AC-turret base as bait [SOE].
  Repair everyone before the HQ. Kill the Lao Hu first [KC, BK].
- **Difficulty:** "the toughest challenge so far … this fight is prone to piss you off … Expect to lose some
  mechs" [SOE, Veteran].
- **Losses/time:** SOE expects mech losses to the boss. SR 4:08.
- **Sourcing:** well-sourced.

## Liao campaign (mc2_10–mc2_17)

KC: "Liao also tends to send you on UNSUPPORTED missions, meaning you have minimum or no RPs to call on."

### mc2_10 Liberate: Gulag

- **Data:** 280 t, 6,000 RP, 4 RP buildings.
- **Forces:**
  - Razorback, Hollander, LRM post, Hunchback.
  - At the prison: 2 Hunters, 4 Centipedes, a Razorback, then a Zeus.
  - Reinforcements: 2 heavy copters and an attack copter, then 2 Hunchbacks and 2 Hollanders.
  - Airfield: an Atlas and 3 Centipedes [BK].
- **Lance/support:** heavy/assault [BK], or Zeus, Lao Hu, Bushwacker, Shootist [KC]. Long Toms on the ridge for
  the reinforcements [BK, SOE].
- **Key tactic:** Long Tom the Hunchback/Hollander wave. Capture the SRM turrets against the Atlas [SOE]. The
  prison's survival doesn't matter [SOE, BK].
- **Difficulty:** moderate.
- **Losses/time:** SR 5:33.
- **Sourcing:** well-sourced.

### mc2_11 Facility Assault: Hijack (no RP at start)

- **Data:** 160 t, 0 RP, **8 RP buildings = 68k**, 1 repair bay, 17 turret controls (capturable).
- **Forces:**
  - A sensor net that, if tripped, sends 2 Jagermechs and Drillsons at you [BK, SOE].
  - Wolfhounds, Enfields and Jagermechs around the Davion base.
  - The salvage yard: Shadow Cat, 2 Jagermech, 2 Enfield.
  - Across the river: Shootists at the Steiner facility; Zeus, Hollander, Highlander and Bushwacker at the
    Steiner HQ. Mined fields and a mined centre bridge [BK, KC, CB].
- **Lance/support:** an ECM mech (Men Shen or Raven) is "mandatory" [KC, SOE, BK], plus a jumper. The rest
  comes from salvage: the 5 Davion mechs, paid for by the base's 5 RP buildings [all].
- **Key tactic:**
  - ECM mech kills the two sensor towers while the others wait outside sensor range.
  - Jump-capture the island RP.
  - Lure Davion mechs into captured pulse/AC turrets, or blow the wall fuel tanks onto the Enfields [CB].
  - Salvage the yard mechs, repair at the yard bay.
  - Cross by the north bridge. Hit the Steiner base from the south-west or extraction side and use its ammo
    dumps [all].
- **Difficulty:** "If your mechs are picked up on the enemy radar, you will end up facing an overwhelming force
  … that can easily spell doom on Veteran" [SOE]. CB: "It's difficult with such a light team" if you go in
  the front.
- **Losses/time:** SR 4:17.
- **Bot note:**
  - The bot's mechs walk into the net. The design intends one ECM mech to go first.
  - It also intends the lance to grow by 5 salvaged mechs mid-mission; the bot gets "one truck".
- **Sourcing:** well-sourced.

### mc2_12 Mobile Intercept: Killdeer (no RP at start)

- **Data:** 210 t, 0 RP (BK and SOE say 10,000), **5 RP buildings = 50k**, 2 Davion turret controls
  (capturable).
- **Forces:** four convoys come down one road, each tougher than the last [KC, BK, CB]:
  - A: troop transports, 2 attack copters, 2 Harassers, 3 Hetzers, 2 Wolfhounds.
  - B: 4 Enforcers (= our Enfield), 2 Partisans, 2 Vedettes.
  - C: 4 Jagermechs (CB adds Partisans).
  - D: 4 Hunters and a Vulture.
  - Base guards (Hunters, Jagermech, Wolfhound) and 2 Ullers by the extraction point [BK, SOE].
- **Lance/support:** "at least two jumpjet-equipped mechs" [KC]. 2×55 t + 2×45–50 t [KC]; heavier per BK.
  2 Long Toms + a repair truck [KC]; 4 Long Toms + a repair truck [BK]; minefield in front of the turret
  controls [CB].
- **Key tactic:**
  - Send a scout east for the RP building. Jumpers island-hop west and capture the SW base's turret control and
    its 2 RP buildings [KC, BK, SOE, CB].
  - Dig in at the NW turret fort with artillery and **hold** while the convoys come to you. "Don't hit the convoy
    itself. That fort you captured will take care of them" [KC]. Keep the enemy off the turret control building.
  - Fall back to the main base's defences if needed.
- **Difficulty:** "If you do this wrong, the mission is VERY hard and you'll lose most of your mechs. If you do
  this right, this mission is NOT that hard" [KC]. CB: convoy C (4 Jagermechs) "is a problem … You're probably
  going to lose the turrets".
- **Losses/time:** no SR record. CB fights C at the wall after losing the turrets.
- **Bot note:**
  - The bot hunts the convoys across the map with no RP (it doesn't take the 50k) and no artillery or turrets.
  - The original fight is a static defence of a captured turret fort with 2–4 Long Toms.
  - The README's "65+ enemies, 1.5:1" is what a player who skips the fort would get.
- **Sourcing:** well-sourced.

### mc2_13 Remote Assault: Eclipsed (true no-support)

- **Data:** 230 t, 0 RP, no RP buildings, **2 repair bays**, 12 Davion turret controls (capturable).
- **Forces:**
  - Thor and Ryoken at the Davion dropship.
  - Uller pairs and Storm tanks on patrol.
  - Gauss-turret and AC-turret forts everywhere.
  - Wolfhounds, Enfields and a Jagermech in the craters.
  - 10–20+ Powered Armor at weapons facility B [all four]. "The Gauss Turret bases are incredibly deadly …
    should be avoided at all costs" [SOE].
- **Lance/support:** heavy, about the same speed: Highlander, Lao Hu, Vulture, or Atlas, Lao Hu, Bushwacker
  [KC]; 2 Zeus + Shootist [SOE]. No support at all. "NO SUPPORT. No salvage, no repair, no nothing" [KC], except
  the 2 bays.
- **Key tactic:**
  - Go to the dropship first and **blow the fuel tanks on the Thor and Ryoken** as they charge [all].
  - Take that repair bay and the sensor control.
  - Then capture the Gauss-turret forts one by one with a fast jumper and use them against the patrols [KC, CB,
    SOE].
  - Kill the two generators in the NE crater to drop the HPG turrets [KC, CB].
  - Don't fight the Powered Armor in the open; give it one dedicated mech [CB, BK].
- **Difficulty:** none of the authors calls it unusually hard, provided you use the tanks and forts. SOE:
  "Whatever you bring here needs to withstand and deal some serious punishment."
- **Losses/time:** SR 3:49 (Green).
- **Bot note:**
  - In the remake, the two repair bays and all the turret forts are inert, so this really is no-support. The
    original is not: it has two bays to repair at.
  - The Powered Armor tops our damage table (183), which matches the guides' warning.
  - **Update 2026-10-24:**
    - The bays and forts work, and destroyed buildings now explode (I115), which brings back the
      fuel-tank tactic.
    - The bot follows the guides' order (`ROUTE_PLANS`): the dropship first, shooting the fuel and
      pipe tanks under the Thor and Ryoken; then WF#3, the bay, the sensor control and WF#1. It
      kills a fort's generator before an objective under its guns (the HPG AC turrets hang on the
      2 NE-crater generators), and it doesn't chase targets into enemy arcs.
    - Result: 3 of 6 objectives every seed (was 0-1), but no win yet. The losses come from
      Gauss-fort head kills, the HPG turrets and patrols, with no repair once the lance is far
      from the dropship bay.
- **Sourcing:** well-sourced.

### mc2_14 Covert Ops: Orbital (solo mech)

- **Data:** 75 t, 0 RP, **3 repair bays**, 12 Steiner turret controls (capturable), sensor control.
- **Forces:** mostly light. Harassers, Hunters and attack copters at the airport. Razorbacks, Hetzers, Scimitars,
  Centipedes, LRM carriers. One Hollander, a Hunchback at each of two gun bases, and a Fire Ant [BK, CB, KC].
  "The mobile orbital gun … isn't armed and can't harm you" [CB].
- **Lance/support:**
  - "yep, ONE mech": **Lao Hu** (75 t, jump jets), every source [KC, BK, CB]. BK allows a medium + light pair.
  - No RP. Support is the 3 repair bays and the captured turret forts.
- **Key tactic:**
  - Take the airport first: jump-capture each mini-fort's turret control ("Judge the distance, jump in and land
    next to the control building, hit capture... You should get it before you land" [KC]).
  - Repair at its bay and take the sensor control, which gives "a lot of situation awareness" [KC].
  - From then on watch the patrols on sensors and avoid or ambush them one at a time. Retreat to forts. Hop
    between bays.
  - The Hunchbacks die to ammo dumps or to "hopscotch" between fort levels so their own turrets shoot them [CB,
    KC].
- **Difficulty:** none of the three authors calls it hard. CB calls it "the fun part". The design expects
  stealth, sensors, jump-captures and bay repairs.
- **Losses/time:** no SR record.
- **Bot note:**
  - The remake can't support the intended play: no repair bays, no turrets, and no patrol avoidance (I21).
    - **Update 2026-10-24:** bays, turrets and captures work, and the bot plays the stealth line
      (`STEALTH_PLANS` in `game/tools/autoplay.gd`): it takes the airport first, avoids patrols it
      doesn't out-gun, jump-captures controls under fire, lures attackers into captured turrets and
      hops to bays. It now takes the airport every seed and Gun Alpha (and sometimes Omega) in most of
      them, but no run has won yet. The losses come at the Gun Alpha fort (Hunchback plus turrets).
    - **Later on 2026-10-24:** two more changes. The bot breaks contact back to its last quiet spot
      when no captured fort can turn a fight, and it no longer walks away from guards standing at
      their posts (only from moving patrols). The Lao Hu now survives to 1800 s in 3/3 seeds. Over
      4000 s, one seed won at 3943 s (every objective), one was alive with 5 enemies left, and one
      was lost at 2102 s with 3 enemies left. The stealth line is slow: about an hour of play.
  - The 31 patrols are mostly vehicles that a player meets a few at a time.
  - With bays and turrets, "sparser patrols" is probably unnecessary.
- **Sourcing:** well-sourced (3 guides agree).

### mc2_15 Facility Assault: Legion

- **Data:** 320 t, 6,000 RP, 4 RP buildings (40k), 1 bay, 5 turret controls.
- **Forces:**
  - A partisan (rebel) attack is already in progress up the middle, against a Steiner hill position with LRM
    carriers, 2 Razorbacks, a Shootist and a Hollander [BK, KC, CB].
  - Factory complex: Storms, Highlander, 2 Razorbacks, then a Bushwacker and 4 Razorbacks [BK, CB].
  - Relay: Bushwacker, 2 Hunchbacks, Hetzers.
  - An aerospotter (Shilone bombers).
  - **10–12 Legion tanks** in the town [BK]. KC: "The Legions cannot shoot short-range"; their rear armour is
    weak (the Liao operative's tip).
- **Lance/support:** a scout is needed ("terrain is quite hilly") [KC]. Atlas, Cyclops, Lao Hu, Men Shen [KC],
  or fast mechs [CB]. **Artillery is the trick for the Legions**: "Put them on the hills overlooking the town … LURE
  them back to your fire support units and turrets" [KC]. BK uses Long Toms and only lures with mechs.
- **Key tactic:**
  - Join the partisan fight first. "You can kill quite a few mechs here, as they tend to shoot the rebels
    instead of you" [KC].
  - Collect the 3 factory RP buildings. Bypass the mined LRM-turret valley [KC]. Keep moving under the
    aerospotter.
  - Legions:
    - **lure** them to artillery and turrets [KC, BK];
    - or close to point blank in town, where they can't fire [KC];
    - or bait them with one mech walking backwards in front of a firing line on a ridge [CB: "they are
      stone-cold dumb"].
- **Difficulty:** "This one will be tough if you play it wrong" [KC]. CB: "This firefight is fast and furious";
  "I've never really had much problem with the Legions".
- **Losses/time:** SR 2:52 (Green).
- **Bot note:**
  - First mech lost at 67–104 s. That suggests the bot meets the Steiner hill or factory force head-on, without
    the partisans as a shield.
  - It can't use artillery, so the Legions get a stand-up fight instead of a lure into Long Toms.
  - On the balance question: KC's claim that Legions can't shoot at short range is checkable against our Legion
    weapon min-ranges.
- **Sourcing:** well-sourced.

### mc2_16 Acquisition: Base Hermes

- **Data:** 320 t, 16,000 RP, 4 RP buildings, 2 bays, 7 turret controls.
- **Forces:**
  - Sensor-control guards (copters, Harassers, Drillson). A Shadow Cat at the north base.
  - The main base has vehicles, 2 Ullers and a Vulture.
  - **Two reinforcement convoys:**
    - from the south: a Shadow Cat, Hunter, 2 Wolfhounds, Partisan, LRM carrier, Vulture, Timber Wolf (= Mad
      Cat), Hunter;
    - from the east: Jagermech, 2 Shadow Cats, Vulture and vehicles [BK, CB, KC].
- **Lance/support:** 2 Highlander, Shootist, Lao Hu [KC]; fast heavies [BK]. BK puts 4 Long Toms at the gate.
- **Key tactic:**
  - "You need to enlist the help of turrets" [KC]: capture the sensor control, then the turret posts on the
    convoy roads.
  - Cut the east convoy at the bridge, "forced into single file" [KC], or in a narrow road gap below captured
    turrets [CB].
  - Then lure the base's Mad Cat and Wolfhound out and take the base with jump-captures.
- **Difficulty:** moderate. No author singles it out.
- **Losses/time:** no SR record.
- **Bot note:** matches the README (I23): players use the turret posts and chokepoints against the
  reinforcements, then take the HQ.
- **Sourcing:** well-sourced.

### mc2_17 Honor Guards (betrayal)

- **Data:** 350 t, 0 RP, no RP buildings, **2 repair bays + 2 turret controls + 1 gate control in an abandoned
  Steiner base about 1.3 km east of the drop**. The lance starts at about (−4544, −2795) and the base controls
  sit at about (1470–2240, −1390 to −2030) in world units. No pay: "Nope, you don't get paid for this one" [KC].
- **Forces, by wave** (the sources differ in detail):
  - **Opening chase:**
    - BK: "two Zeuses and one Bushwacker", then a lone Highlander.
    - KC: first wave "2 Zeus and a Highlander, plus misc. smaller Steiner mechs".
    - CB: "2 Zeuses, 3 Highlanders and a Bushwacker, pretty much all at once" plus "a small auxiliary force of
      Razorbacks and Hollanders" from the SE. If you just run and dig in late: "a mass force of 10-12 mechs …
      you won't have any time to repair".
  - **Jason Cho** in a Cyclops [KC, CB; BK writes Highlander] with 3 attack and 3 heavy copters.
  - **Liao revenge wave:** 3 Catapults, 2 Sha Yu, 2 Anubis, Men Shen(s) [BK, CB, KC].
  - **Final wave**, as rebels (LRM carriers, Partisans, Drillsons, Centipedes) arrive in the north: 2 Ravens and
    2 Starslayers vanguard, then a Raven, 2 Starslayers and 2 Lao Hu [BK, CB]. KC: "Lao Hu, Raven, Sha Yu".
- **Lance/support:**
  - Heavy/assault. 2 Lao Hu, Shootist, 2 Catapult or Vulture; or 2 Atlas + Lao Hu/Mad Cat [KC]. "Heavy and
    assault 'Mechs only" [BK].
  - At least one jumper [KC]. Configure for close range [KC].
  - No RP. The base's 2 repair bays are the whole support plan: "Those repair bays can repair a LOT of damage"
    [KC].
- **Key tactic, three variants:**
  1. **Run to the base at once**, every mech on RUN: "As soon as the cutscene stops, RUN for that Steiner base to
     the east … Even in an Atlas … you can make it to the base LONG before the enemy does" [KC]. BK says the
     same ("Immediately follow the suggestion of your Tactical Officer and run to the abandoned … Steiner base in
     the north-east").
     - Then capture both turret controls with the fastest mech, stand between the enemy and the controls, and
       repair at the bays between waves.
     - Use the ammo dump inside the base on the biggest attackers [KC, BK].
  2. **CB's expert line:** hold the hilltop tree line at the drop on Hold Position and head-shoot the
     Zeus/Highlander wave as it climbs. Then go to the base for the later waves. CB calls running first "Fat
     Chance #2" only because it then meets the 10–12-mech mass.
  3. **CB's fallback:** run down to the town behind the drop and use its fuel tanks on the pursuers.
  - At the end, leave the base for the rebels in the NE [KC], or stay put [CB, who says the rebels are "more
    hindrance than help"].
- **Difficulty:**
  - "This is a nasty mission" [KC].
  - "This mission is a doozy … take some big mechs and make out your will"; "this wave is brutal" (the Liao
    Catapult wave); "This mission will surely test your chutzpah" [CB].
  - The hardest Liao mission by all three accounts, but beaten by all three.
  - BK reports a quick-save/quick-load bug in this mission that failed it.
- **Losses/time:** none quantified. No SR record.
- **Bot note:**
  - The bot dies 106–117 s after the battle starts. That is about the time a lance needs to *reach* the base.
  - The designed answer is to run east at once, repair at the 2 bays between waves and fight inside the turrets.
  - **Update 2026-10-24:** the bot now plays this line (`HOLD_PLANS` in `game/tools/autoplay.gd`).
    It runs to the base without stopping to fight, captures both controls and both bays, and holds
    inside the base through every wave. It won 3 of 3 seeds in 1197-1387 s and lost 1 mech.
    Finishing also needed a game fix: movers that the script removes no longer block "destroy all"
    (I111).
  - Before 2026-10-24: the remake couldn't give that answer, because bays and turrets were inert, though the base walls and gate existed as
    buildings.
  - **What the README calls "10–11 threats at once" is what CB describes for a lance that doesn't kill the first
    wave fast.** It is the original's behaviour, not a remake bug.
- **Sourcing:** well-sourced on the tactic (3 guides agree on "run to the base, use the bays and turrets"). Wave
  composition is moderately sourced: the details differ.

## Davion campaign (mc2_18–mc2_24)

KC: "Major Kelly and Baxter hand you the tough jobs but advanced mechs are plentiful."

### mc2_18 Defensive Counter: Bannikburg

- **Data:** 320 t, 16,000 RP, **10 RP buildings = 82k**, 1 bay, 4 turret controls.
- **Forces:**
  - Occupiers: Partisans, Starslayers, Razorbacks, Hetzers, Shootist, 2 Catapults (powered down at an ammo dump),
    2 Hollanders at the bridge, a Highlander with an aerospotter at the tank farm, and 2 Men Shen + 2 Ravens with
    ECM [BK, CB].
  - Then 3–4 attack waves:
    - Liao: 3 Sha Yu + 3 Lao Hu with copters;
    - Razorbacks, Shootists, a Partisan, LRM carriers;
    - 2 Hunchbacks + 4 Sha Yu;
    - Atlas, 2 Hollanders, 2 Catapults [BK, CB].
- **Lance/support:** heavy (90/70/80-tonners, Cyclops, Zeus) [KC]. RP is plentiful: Long Toms "on constant
  barrage on the bridge", minelayers on the banks [KC, BK, CB].
- **Key tactic:**
  - Recapture HQ, power and sensor control (the secondaries "are worth a lot").
  - Then **hold the two bridges** from the forts on each side. "If you can hold the bridges, you can bottle up
    most of the enemy easily" [KC].
  - Shuttle between the bridges and repair in the lulls. Kill the aerospotter by blowing its tank farm [KC, CB].
- **Difficulty:** moderate. "Defend" is an ongoing objective [KC].
- **Losses/time:** no SR record.
- **Bot note:** matches the README (I25): hold the bridges, don't hunt across the city.
  - **Update 2026-10-24:**
    - The waves chain as in the script (mc2_18.abl:357-391). 25 kills start group 0, and group 1
      follows 70 s later. Each later group comes only once the one before it is dead.
    - The bot retakes the HQ, the power generator and the sensor control first, in the guides'
      order. It ranks the aerospotter first in fights and doesn't chase into enemy arcs.
    - Result: all three secondaries in 2/3 seeds, with 50-53 kills and 10 enemies left, but still
      0/3. A hold at the bay stalled: group 2 roams the city out of its reach.
- **Sourcing:** well-sourced.

### mc2_19 Mobile Assault: Mt. Cho

- **Data:** 330 t, 12,000 RP, **15 RP buildings and trucks = 90k**, 1 bay. Its 10 Liao turret controls are not
  capturable in our data.
- **Forces:** the biggest roster in the game.
  - Camo turrets in rock clusters. Many Sha Yu, Razorbacks, Bushwackers, Catapults, Hunchbacks.
  - Powered-down Atlas and Highlander at the bay.
  - Zeus and Hollanders at the airport with 2 aerospotters and 5 Slayer bombers.
  - Swarm LRM carriers and Storms at the weapons facility.
  - A mobile orbital gun with Hunchbacks and Catapults [BK, CB, KC].
- **Lance/support:** Atlas, Cyclops, Lao Hu, Catapult [KC]; assault only plus a Cyclops [BK]. Long Toms to break
  the gun group and the airport [BK].
- **Key tactic:**
  - **Only 1/3 kills is required**, and you can extract any time after. "This mission is hard to do really well,
    but quite doable if you just want to do the bare minimum" [KC].
  - Pick fights in order. Avoid the camo-turret rocks.
  - Lure from hilltops "so you take on ONE mech at a time with all your mechs". Wake the powered-down mechs one
    group at a time [KC, CB].
  - Kill the aerospotters first [KC, CB]. Snowball with field salvage: "Drop with 6 mechs, Extract with 15"
    [CB].
- **Difficulty:** hard to complete fully; easy to pass at the minimum. BK: "lots of C-Bills but it's difficult"
  (the harder of the three optional Davion missions).
- **Losses/time:** SR 4:30 for the minimum (Green, solo mission).
- **Bot note:**
  - The bot gets 16–23 kills of the 82 units, about the 27 needed, then dies. It has no reason to stop.
  - "Extract at 1/3" is the intended minimum, and a player would leave then.
  - Also, the Liao turret controls the guides capture here aren't capturable in our data.
- **Sourcing:** well-sourced.

### mc2_20 Combat Recovery: Dropship

- **Data:** 320 t, 12,000 RP, 11 RP sources (50k), 1 bay. Its 2 Liao turret controls are not capturable in our
  data.
- **Forces:**
  - A Catapult, 2 Hollanders, 3 Anubis patrol.
  - Repair-bay guards: Anubis, 3 Swarm LRM carriers, Starslayer, Zeus.
  - Fixed gun: Zeus, Vedettes, Storm.
  - Men Shen and Hollander patrols.
  - The prison: Shadow Cat, 8 Harassers, and a **powered-down Mad Cat and Vulture**.
  - Mobile gun 1: 2 Highlanders. Mobile gun 2: LRM carriers and 2 Starslayers.
  - At the dropship, **mechs hidden under the water power up** (2 Hollanders + 2 Hunchbacks [BK]; 3 Hunchbacks +
    2 Sha Yu [CB]) [BK, CB, KC].
- **Lance/support:** heavy/assault only [KC, BK]. Plus a scout for the "destroy all" secondary [KC]. "Try to
  preserve your mechs, as repairs are pretty rare" [KC].
- **Key tactic:**
  - Take the SE fixed gun first to get the repair bay, then work round [KC, BK].
  - Or go to the dropship first and hold there against the counterattack [KC].
  - Set up a half-moon before approaching the dropship, for the underwater ambush [CB].
- **Difficulty:** "An other mission for heavy and assault 'Mechs only" [BK]. Moderate.
- **Losses/time:** no SR record.
- **Bot note:**
  - "Hollander and Zeus deal 300+" matches the rosters.
  - Players would get the bay first; the bot has no bays.
- **Sourcing:** well-sourced.

### mc2_21 Night Ops: Scorpio (18-minute timer)

- **Data:** 200 t, 23,000 RP, `TimeLimit` 1080 s, 3 RP sources.
- **Forces:** Hunchback + Hollander, Razorback + Bushwacker patrols, Partisans, Storms, a powered-down Atlas,
  Shootists, a Swarm LRM carrier, 5 powered-down Razorbacks at the barracks (CB: 6), and Atlas and Shootist at
  generator A [BK, CB].
- **Lance/support:** fast: "86 kph or faster" [KC]. Men Shen, Mad Cat, Thor [KC]; Men Shen, Timber Wolves,
  Vultures [BK]; light/medium sharpshooters [CB].
- **Key tactic:** hit-and-run. "Do NOT be locked into a mech-to-mech duel" [KC]. Shoot each ammo-dump group
  once so it chains. Outrun the Atlases [KC, CB].
- **Difficulty:**
  - BK: "mission 2A is easy".
  - CB: "this mission is a certified bitch on wheels".
  - KC: timing is tight ("You SHOULD have at least ONE minute left").
  - The authors disagree.
- **Losses/time:** SR 1:34 on **Veteran** ("Quicker than Regular difficulty, ha!"). The only Primary is
  Extract, so a run can skip everything.
- **Bot note:** the bot wins 3/3. It only needs to reach extraction.
- **Sourcing:** well-sourced.

### mc2_22 Baxter's Gambit

- **Data:** 380 t, 16,000 RP, **15 RP sources = 90k**, 1 bay. Its 5 Liao turret controls are not capturable in
  our data. 27 pulse, 26 LRM and 25 AC turrets in `objects.json`.
- **Forces:**
  - The start is **inside a walled compound in the SW corner**, with "TWO sets of fixed defenses, AND gates, and
    plenty of enemies inside and outside"; gates within LRM range [KC].
  - 7–8 patrol groups of Men Shen/Starslayer, Raven/Anubis, Sha Yu, Bushwacker [BK, KC, CB]. "Beware of ECM
    equipped mechs like Men Shen and Raven moving in without showing on your sensors" [KC].
  - The central base has a dozen Partisans [CB], Lao Hu, Catapults and an Atlas or Highlander [KC].
  - A bridge fort with 4 camo AC turrets.
  - The **Elite Guard**: a Cyclops (the leader), 2–3 Lao Hu, 3–5 Catapults with Swarm LRMs, 2 Anubis, 4 Swarm
    LRM carriers [BK, KC, CB].
  - Aerospotters on the flanks [CB].
- **Lance/support:** heavy/assault (Cyclops, 2 Atlas, Highlander) [KC]; Blood Asps and a Cyclops [BK]; fast Lao
  Hus [CB]. At least one jumper and a scout [KC]. **Long Toms** on the near side of the bridge to make the guard
  cross in single file [BK, KC].
- **Key tactic:**
  - First "disable or capture the northern defenses. THEN use that to get out", then the eastern ones [KC].
  - **Stay in the corner** and tease patrols into the turrets: "If you use the corner they won't bother you" [KC].
    CB: "Lure the Catapults into the dell" first, and "Leave the team in place and send one mech out as decoy".
  - Collect every RP building and truck ("You have A LOT of RPs you can capture" [KC]). Take the central town's
    repair bay. Salvage heavily: CB reaches 106,000 RP and 16 mechs.
  - Fight the Elite Guard through a chokepoint: the bridge with artillery [BK, KC], or the ford with a "Curve of
    Death" firing line [CB]. "The trick in beating Swarm LRM is KEEP MOVING" [KC].
- **Difficulty:** "This one is quite tough, mainly due to the number of enemies" [KC]. "You may lose one or more
  mechs here" (at the Elite Guard) [KC]. CB treats it as the campaign's real test ("if you don't, you won't make
  it out of here alive").
- **Losses/time:** KC expects losses at the guard. No SR record.
- **Bot note:**
  - The bot is dead by 129–436 s to "12 threats within 25 s of the drop", with Partisans the top attacker.
  - The guides say the drop is a walled corner where you deal with the defences first. They say nothing about
    patrols converging on the drop at t=0.
  - That supports the README's suspicion that the early Partisan or patrol aggression is a **remake/game issue**.
    Run the probe the README proposes (`--shots=200`).
  - Separately, the bot has no turrets or artillery for the chokepoint fight the mission is built around.
  - **Update 2026-10-24:**
    - The early rush is not a port bug. The compound's guards (mc2_22_EC1_*.abl) guard their posts
      and attack only movers within 300 m (`setTargetPriority(1, TARGET_PRIORITY_MOVER, 0, 300, ...)`).
      The drop is 400 m or more from them, as KC says ("if you use the corner they won't bother
      you"). The bot was simply walking into them.
    - Found and fixed I116: a building whose generator is destroyed sleeps and can't be captured
      (bldng.cpp:1046).
    - The bot now plays this line (`HOLD_PLANS` mc2_22):
      - at t=0 it air-strikes the northern line's generator (13 turrets hang on it);
      - it holds the drop and sends a decoy out to draw the guards in;
      - it starts the mission once nothing more can be drawn out without walking into a fort's arcs.
    - Result: the lance lives to 622-877 s (was 169-230), with 21-45 kills (was 9-11). The turrets
      are no longer the top killers. Still 0/3: the Men Shen, Catapult and Elite Guard (Cyclops,
      Swarm LRMs) finish it.
- **Sourcing:** well-sourced on tactics. Nothing sourced on t=0 behaviour.

### mc2_23 Liberate: Starport

- **Data:** 300 t, 36,000 RP, 3 RP buildings, **3 repair bays**, 3 turret controls.
- **Forces:**
  - Canyon start: 3 Razorbacks + a Hunchback and 4 LRM carriers.
  - Sensor island: Zeus, Hollander, and Long Tom and LRM turrets.
  - The starport: 2 Atlas, Zeus, 2 Bushwackers, 2 Hollanders, many LRM carriers among the terminals.
  - **Each of 3 dropships has a pair of mechs hidden in the water**: Hunchback/Highlander, Razorback/Highlander,
    Hunchback/Razorback [CB, BK].
  - **Two reinforcement waves**, triggered when the last starport LRM carrier dies [CB, KC]: Hollander, Hunchback
    and 2 Highlanders from the SW; then 3 Razorbacks, 2 Hunchbacks and a Highlander from the E/NW [BK, CB].
- **Lance/support:** heavy/assault only [KC, BK]. KC's plan spends the 36k on **several minelayers**, around the
  western road and the starport's NW edge, plus 3 artillery pieces. BK places 4 Long Toms by each repair bay.
- **Key tactic:**
  - "This one is a true slugfest if you do it WRONG. If you do it right, it is quite simple. The trick is to
    PREPARE a proper reception for the reinforcements BEFORE they arrive" [KC].
  - Tease the starport mechs out a few at a time.
  - Capture the 2 dropship-side repair bays.
  - Leave one LRM carrier (or dropship) alive until the minefield and artillery are ready, then trigger the
    reinforcements into them [KC, CB].
- **Difficulty:** hard if rushed, simple if prepared [KC].
- **Losses/time:** no SR record.
- **Bot note:**
  - The bot fights everything as it meets it: 32–40 kills with 28–41 left. It has no mines, artillery or bays.
  - Also, the reinforcement trigger is the last starport LRM carrier. A bot that kills everything in reach
    triggers the waves early, before it has repaired.
- **Sourcing:** well-sourced.

### mc2_24 Operation Goliath

- **Data:** 450 t, 10,000 RP, 6 RP buildings (60k), 1 bay, 6 turret controls.
- **Forces:**
  - Main gate: Long Tom turrets on both "horns", LRM turrets, 2 Shootists, 2 Highlanders, 4 Bushwackers [BK].
  - Patrols: Bushwacker/Hollander groups. Hunchbacks at the west dropship pit.
  - Zeus/Hunchback teams at the west gate. **6 Legion tanks** by the north repair bay [CB, BK].
  - Powered Armor at the HQ.
  - **Renard's jump-jet Atlas** with Clan Gauss + HAC, escorted by 2 Highlanders + 2 Shootists (BK; KC says 4
    Highlanders). KC: "This game cheated. They gave Renard a JUMP-capable Atlas".
  - Rebels (UrbanMechs, Jagermechs, Swarm carriers) breach the east wall [all].
- **Lance/support:** Cyclops + 4 Blood Asp or Highlander, set up for medium/close range because LOS is short
  [KC, BK]. BK places 4 Long Toms below the HQ for Renard's squad.
- **Key tactic:**
  - "Do NOT assault the main gate" [KC]. Run east out of turret range and follow the rebels in through the east
    breach [KC, BK, CB].
  - Hold the South Gate controls: "South Gate controls must be held. Anything else said here is moot" [CB].
  - Either clear the base first (repair bay, RP, salvage) or rush the HQ.
  - When the HQ and its annexes fall, Renard comes down the hill. Kill him first, then "RUN … for extraction …
    As long as ONE mech reaches the extraction, you win!" [KC].
  - CB mentions a "scurvy, low-down dog cheat": jump straight to the top of the map and shoot the building that
    triggers Renard.
- **Difficulty:** the finale. Hard but well-signposted. "toast everything (best done at RECRUIT level)" [KC]
  suggests the full clear is the hard option.
- **Losses/time:** no SR record. SR campaign any% is **1:58:29** for all mandatory missions (Green, v1.0).
- **Bot note:**
  - The bot dies at 349–564 s with 0 of 3 primaries done, apparently fighting at the front.
  - Players go round to the east breach, which is why "the hidden fuel-truck trigger for the rebel attack (I30)"
    matters: the rebels are the designed way in.
- **Sourcing:** well-sourced.

---

## Summary table

"Rating" is the authors' opinion, on Regular unless noted. "Support" means what players actually had and used,
not the start RP.

| Mission | Rating by players | Key tactic | Support available and used | Notes for our bot | Sourcing |
|---|---|---|---|---|---|
| 01 Scouting Patrol | very easy [KC] | range the LRMs, split the final group | 22k RP; save for salvage | wins 3/3 | strong |
| 02 Base Gemini | easy | RP building first, jump-capture turret controls | 6k + 50k captured RP | wins 3/3 | strong |
| 03 Mobile HQ | easy | blow fuel tanks on defenders; ambush the convoy from the hill; Long Tom the counterattack | 16k + 18k RP | wins 3/3; Bandit turret controls not capturable in data | strong |
| 04 Bandit Convoy | easy | hug the water, take the bridge fort generator, light mech grabs the facility | 16k + 30k RP | wins 3/3 | strong |
| 05 Liao Raid | moderate (night) | sensors; ford north; capture the LRM turret control and lure prison defenders | 7k RP + repair bay | wins 3/3; data 220 t vs 200 t in BK and SOE | strong |
| 06 Base Aries | hardest of 06–08 [KC] | grab sensor and turret controls early, blow the tank farm, hold the base with turrets, 2 bays and Long Toms or mines | 25k + 36k RP, 2 bays | needs a hold/guard mode | strong |
| 07 Garrison | moderate | HQ last, lure into fuel tank or pulse turrets, minefield trick | 6k + 30k RP, 1 bay | 2/3 | strong |
| 08 Claymore | not rated hard | RP buildings for 1 repair truck, flank via the south mini-base, jump-capture turrets | **0 + 50k RP**; one repair truck | not no-support; take the RP. Bandit turret controls not capturable in data | strong |
| 09 Bandit HQ | "toughest so far" [SOE] | clockwise RP route, AC-turret base as bait, kill the Lao Hu boss first | 30k + 52k RP; air strikes | 3/3 | strong |
| 10 Gulag | moderate | Long Tom on the ridge for reinforcements, SRM turrets vs the Atlas | 6k + 34k RP | 2/3 | strong |
| 11 Hijack | hard if the sensor net trips [SOE] | ECM mech kills the sensor towers first; salvage 5 Davion mechs; north bridge | **0 + 68k RP**, 1 bay, salvage | send the ECM mech first; salvage the yard | strong |
| 12 Killdeer | "VERY hard" done wrong, "NOT that hard" done right [KC] | take the RP, capture the turret fort, **hold** it with 2–4 Long Toms (and mines) as convoys come | **0 + 50k RP** (BK and SOE: 10k start) | defend a fort, don't hunt; needs artillery and turrets | strong |
| 13 Eclipsed | moderate with tricks | fuel tanks on Thor/Ryoken, capture Gauss forts, kill generators | **no RP, but 2 repair bays** and capturable forts | bays and turrets missing in remake | strong |
| 14 Orbital | not rated hard | solo Lao Hu: airport first, jump-capture forts, sensor control, avoid patrols, 3 bays | **no RP, 3 bays**, turret forts | bays, turrets, avoidance all missing | strong |
| 15 Legion | "tough if you play it wrong" [KC] | fight beside the partisans; lure the Legions into artillery or turrets, or point-blank in town | 6k + 40k RP, 1 bay | no artillery; check Legion short-range claim | strong |
| 16 Base Hermes | moderate | turret posts and bridge chokepoint vs 2 convoys, then the HQ | 16k + 40k RP, 2 bays | use turrets and secondaries (I23) | strong |
| 17 Honor Guards | hardest Liao mission: "nasty", "a doozy" [KC, CB] | **run east to the abandoned base at once**, take 2 turret controls and 2 bays, hold through 4–5 waves (or head-shoot the first wave on the hill) | **no RP; 2 bays, 2 turret controls, ammo dump** | run to the base; the mass attack is original behaviour | strong (waves: moderate) |
| 18 Bannikburg | moderate | recapture HQ, power and sensor; hold the two bridges with forts, Long Toms, mines | 16k + 82k RP, 1 bay | hold the bridges (I25) | strong |
| 19 Mt. Cho | hard to finish, easy at the minimum [KC, BK] | 1/3 kills then extract; lure one at a time; kill aerospotters; salvage | 12k + 90k RP, 1 bay | extract at 1/3; Liao turret controls not capturable in data | strong |
| 20 Dropship | moderate, heavy only | repair bay first; half-moon before the dropship ambush | 12k + 50k RP, 1 bay | bays missing | strong |
| 21 Scorpio | split: "easy" [BK] / "certified bitch" [CB] | 18-min hit-and-run, only Extract is primary | 23k + 18k RP | wins 3/3 | strong |
| 22 Baxter's Gambit | "quite tough … number of enemies" [KC] | stay in the SW corner, take the N then E defences, tease patrols, salvage to 10–16 mechs, chokepoint the Elite Guard with artillery | 16k + 90k RP, 1 bay | t=0 swarm not described by any player, so probe it; turrets and artillery missing | strong (t=0: none) |
| 23 Starport | "slugfest" rushed, "simple" prepared [KC] | clear the starport piecemeal; mines and artillery in place before triggering the reinforcements | 36k + 30k RP, 3 bays | don't trigger waves early; mines, artillery, bays missing | strong |
| 24 Goliath | finale, hard but signposted | go round to the east breach with the rebels, hold the south gate controls, kill Renard first, any one mech extracts | 10k + 60k RP, 1 bay | rebel trigger I30; avoid the main gate | strong |

## What this means for the balance questions

These are the findings that matter most. Each is spelled out in the sections above.

1. **The no-support framing (README call 1) doesn't match the original.**
   - mc2_08, 11 and 12 start at 0 RP but hold 50k, 68k and 50k RP in capturable buildings. Players fund repair
     trucks, salvage and (in 12) 2–4 Long Toms from them.
   - mc2_13, 14 and 17 have no RP but have 2, 3 and 2 repair bays and capturable turret forts, and every
     walkthrough builds the mission around them.
   - None of the four authors calls 08, 13 or 14 hard. 12 and 17 are hard only "if you do this wrong".
   - So "give them support RP" would change the original's design. The parity fix is to implement repair bays
     and turrets, and to have the bot take RP buildings.
2. **Captured turrets, repair bays, Long Tom artillery and minelayers carry every hard mission in the
   walkthroughs.** In the remake, turrets aren't simulated. Bandit and Liao turret controls aren't capturable in
   `objects.json`: the parent link is dropped. Repair bays, artillery and minelayers aren't implemented. Until
   they are, the bot is playing a harder game than the original from mc2_12 on, whatever its tactics.
3. **mc2_17's betrayal is meant to be survived by running to the abandoned Steiner base about 1.3 km east.**
   - Players take its 2 turret controls and 2 repair bays and hold through 4–5 sequential waves.
   - The "10–12 mechs at once" pile-on is what CB says happens to a lance that doesn't deal with the first wave.
     It is original behaviour, not a bug.
   - Accept it as written, once bays and turrets work, and teach the bot "run to the base".
4. **The mass-enemy missions have scripted answers:**
   - 15: lure the Legions into artillery or turrets, or point-blank in town.
   - 19: only 1/3 kills is required; extract.
   - 22: stay in the walled corner and chokepoint the Elite Guard.
   - 23: prepare mines and artillery before triggering the reinforcements.
   - Players call them tough but beatable on Regular. Regular is widely described as easy (SOE, MK).
   - One unexplained case: no source mentions mc2_22 patrols converging on the drop at t=0, so the README's
     proposed probe is worth running.
5. **Two rules differences make the remake harder than the original for mech lances against vehicles (README
   call 3).**
   - Heat is on for mechs only, while the original had none and vehicles are exempt in ours.
   - Ammo is finite, while the original's single-player default is unlimited for every unit.
   - Both come from our own specs, not from players. A sweep with `heat_enabled = false` and infinite ammo would
     show how much of the 12–24 gap they account for.
   - Smaller items:
     - check mc2_05's drop weight (220 t vs 200 t) and mc2_12's start RP (0 vs 10,000) against a retail 1.1 FIT;
     - check KC's claim that Legions can't fire at short range against our Legion weapon minimum ranges.
