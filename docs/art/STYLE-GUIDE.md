# Lance Commander / MC2 Remake — Master Style Guide

**Status: single source of truth for all art, UI, audio and FX.**
Where this guide contradicts any other document, agent prompt, memory note, code constant or earlier asset, **this guide wins**. Contradictions are fixed in the other place, not here (see §19 for the known ones).

**Target:** a modern interpretation of MechCommander 2 that *looks and sounds like* MechWarrior 5: Mercenaries (MW5), with MechWarrior Online (MWO) as secondary reference for mech silhouettes. Style is taken from those games. **No assets, names, logos, fonts, audio or text are taken from them** (PGI / Microsoft / Catalyst copyright). Everything here describes a *look*, to be reproduced from our own or licensed (CC0 / CC-BY / CC-BY-SA) sources.

**Verification note.** Colour values and measurements below are design targets derived from the games' established look, not eyedropped from screenshots. Step 1 of adoption (§20) is to eyedrop privately-held reference screenshots and lock the final hexes. Until then, the values here are authoritative.

---

## 1. Pillars (the five-second test)

Every asset is judged at **RTS camera distance** first, then close-up.

1. **Heavy industrial war machines.** Mechs are 8–12 m tall tanks on legs: massive, hard-surface, weight-first. Never sleek, never cartoon, never sci-fi-clean.
2. **Used, not dirty-for-dirt's-sake.** Chipped paint, scorch, oil streaks, panel wear concentrated where hands, feet and weapons touch. Wear tells a story; it is never uniform noise.
3. **Moody, contrast-led lighting.** Low sun, long shadows, haze, strong silhouettes. Warm key vs cool fill.
4. **Tactical, functional HUD.** Data-dense, thin-line, monochrome-plus-signal-colour. Mil-spec cockpit instrumentation, not a mobile game.
5. **Readability beats realism.** Faction, damage state, selection and threat must read at a glance from the RTS camera.

**Anti-goals:** procedural-noise textures (the v1/v2 failure), flat unlit colour, rainbow palettes, glossy plastic, anime proportions, fantasy ornament, rounded "friendly" UI, bevel/emboss/drop-shadow skeuomorphism.

---

## 2. Colour system

### 2.1 Master UI palette (replaces all earlier palettes)

| Token | Hex | Use |
|---|---|---|
| `ink-900` | `#070A0D` | Deepest background, letterbox |
| `ink-800` | `#0C1117` | Screen background |
| `ink-700` | `#121A22` | Panel fill (80–90% alpha) |
| `ink-600` | `#1B2630` | Raised panel, hovered row |
| `steel-500` | `#3A4854` | Inactive frame lines, dividers |
| `steel-300` | `#7F909C` | Secondary text, inactive icons |
| `steel-100` | `#D5DEE3` | Primary text on dark |
| `white` | `#F2F6F8` | Headline, active value |
| `amber-500` | `#F2A21F` | **Primary brand accent**: titles, selected menu item, active tab, key buttons, contract rewards |
| `amber-300` | `#FFC85A` | Hover/highlight of amber |
| `amber-700` | `#8C5A0C` | Amber pressed/disabled, amber frame at rest |
| `cyan-400` | `#3FC6E0` | **In-mission HUD line colour**, friendly info, targeting base |
| `cyan-glow` | `#3FC6E0` @ 40% | Glow/bloom on HUD lines |
| `ok` | `#4FD38A` | Healthy, complete, armour intact |
| `warn` | `#F2B54A` | Damaged, caution, low ammo |
| `heat` | `#FF7A2F` | Heat, fire, overheating, incoming |
| `crit` | `#FF5A4E` | Critical, destroyed component, enemy, error |
| `friend` | `#5CA0FF` | Allied / player-lance markers |
| `neutral` | `#C9CED2` | Neutral / unaligned |

**Rules**
- **Two accents, two jobs.** *Amber* = menus, mech bay, contracts, campaign (the mercenary-business layer). *Cyan* = in-mission HUD and sensors (the cockpit layer). Never mix them in one frame except a deliberate selected-item highlight.
- Signal colours (`ok / warn / heat / crit`) are **reserved for state**. Never decorative.
- Text on `ink-*` backgrounds ≥ 7:1 contrast for body, ≥ 4.5:1 for 14 px+ labels.
- Maximum **one saturated colour per component**; everything else greyscale or steel.
- Colour is never the only carrier of meaning: pair with shape, icon or text. Damage uses fill-level *and* colour; allegiance uses marker *shape* and colour.

### 2.2 World palette
Overall grade is **desaturated, slightly warm highlights, cool shadows**. Peak saturation sits in faction paint and FX only. Keep terrain saturation ≤ 45% of faction-paint saturation so units pop.

### 2.3 Faction colour schemes (paint, banner, minimap)
Mech paint = **primary + secondary + trim**, plus a small unit-insignia decal. Schemes evoke the lore but are our own originals, not copies of PGI schemes.

| Faction | Primary | Secondary | Trim | Mood |
|---|---|---|---|---|
| Player lance (default) | `#4A5560` gunmetal | `#F2A21F` amber | `#D5DEE3` | Mercenary, practical |
| Enemy / OpFor generic | `#5A2A26` oxblood | `#2A2A2C` charcoal | `#B8B2A6` | Hostile, dull red |
| Red-and-gold realm | `#B0262B` | `#E8C14A` | `#1A1A1A` | Regal, bright |
| Blue-and-silver realm | `#2C4F9E` | `#D8DCE0` | `#E8C14A` | Clean, ordered |
| Crimson-and-black realm | `#7A1D24` | `#1E1E22` | `#C9A646` | Severe |
| Green-and-gold realm | `#2F6B4F` | `#C9A646` | `#1E1E22` | Mercantile |
| Purple realm | `#6E3A8A` | `#D8DCE0` | `#C9A646` | Cold, political |
| Invader clans | `#3E4A44` olive-steel | `#B7792B` bronze | `#0E0E10` | Predatory, angular decals |
| Pirates / bandits | 2–3 clashing earth colours, mismatched patches | | | Scavenged |
| Civilian / industrial | `#C9A230` safety yellow | `#5B6770` | | Machinery |

Licence rule: schemes are labelled by *role* in the UI, never with trademarked house or product names.

### 2.4 Paint damage ramp
Clean → Scuffed → Chipped → Scorched → Breached. Each step adds edge wear (bare metal `#8A8F94`), oil streaks (`#1A1612` @ 40%), scorch (`#0D0D0D` radial from impacts); Breached shows internals (`#3A2B22` cable/rust with `#FF7A2F` ember emissive).

---

## 3. Typography

All fonts **OFL / open licence**. Already bundled and **canonical**: Chakra Petch, Barlow Semi Condensed, Share Tech Mono.

| Role | Font | Style |
|---|---|---|
| Display / screen titles / mission names | **Chakra Petch** SemiBold–Bold | ALL CAPS, tracking +8% |
| Body, descriptions, briefing | **Barlow Semi Condensed** Regular/Medium | Sentence case |
| Labels, buttons, tabs | Barlow Semi Condensed SemiBold | ALL CAPS, tracking +6% |
| Numerals, telemetry, tonnage, heat | **Share Tech Mono** | Tabular figures only |

Scale at 1080p (scale linearly): Title 40 / Section 24 / Subhead 18 / Body 16 / Label 13 / HUD micro 11. Never below 10 px. Line height 1.35 body, 1.1 headings. Left-aligned body, never justified. Numbers right-aligned in columns.

---

## 4. UI foundations

### 4.1 Geometry
- **Chamfered rectangles, not rounded.** 45° cuts of 6 px (small), 10 px (panels), 16 px (hero). Corner radius 0.
- **Thin-line frames:** 1 px inactive (`steel-500`), 2 px active (accent). Corner-tick brackets at 12 px on focused/selected panels.
- Panel fill `ink-700` @ 85% with faint diagonal hatch or scanline at 4% opacity. No gradients except a one-step top-edge fade.
- 8 px grid, 16 px gutters, 48 px outer margin (5% safe area).
- No drop shadows. Depth = alpha, value step, 1 px top-edge highlight.

### 4.2 Iconography
Monoline, 2 px stroke at 32 px, square caps, chamfered joins. Filled variants only for active/equipped. Families: weapon class, equipment, status, chassis class (light/medium/heavy/assault silhouettes), map markers, contract type.
Weapon-class glyph colours (loadout screens only): ballistic `#E0B44A`, energy `#5CC8E8`, missile `#E07A4A`, support `#9BE08A`.

### 4.3 Components
- **Primary button:** amber 2 px frame, `ink-700` fill, amber text; hover amber @ 15% fill + glow; pressed `amber-700`; disabled `steel-500`. Chamfer 6, min height 44.
- **Secondary button:** `steel-300` frame/text; hover → white text.
- **Tabs:** underline style, 3 px amber bar under active, caps.
- **Lists/tables:** no zebra; hover `ink-600`; selected row has 3 px amber left bar. Header caps `steel-300` over a 1 px rule.
- **Sliders/bars:** 6 px track `ink-600`, accent fill, segmented every 10%.
- **Toggles:** square.
- **Tooltips:** `ink-900` @ 95%, 1 px `steel-500`, 8 px padding, 350 ms delay.
- **Modals:** scene dimmed to 55%, centred panel, amber frame, section-tag title bar.
- **Progress:** thin bar with a bright leading pixel; mono % readout.

### 4.4 Motion
- 120–180 ms, ease-out. Panel in: 8 px slide + fade. No bounce or overshoot.
- Screen-entry "boot" flicker (2–3 frames); HUD elements power on sequentially (40 ms stagger).
- Hover: instant colour change + 100 ms glow. Selection brackets snap in over 90 ms.
- "Reduce motion" setting disables flicker, scan and slides.

### 4.5 Layout archetypes
Three-column (list · detail · map); hero + sidebar (mech bay); full-map with floating panels (campaign); modal over dimmed scene.

---

## 5. Screen specifications

1. **Main menu.** Full-bleed slow 3D vignette (mech in drydock or dusk landscape), heavy vignette, grain. Left vertical menu (NEW CAMPAIGN, CONTINUE, SKIRMISH, OPTIONS, EXIT), Chakra Petch 28 px caps; selected item = amber bar + glow + 4 px indent. Our own angular stencil logo top-left. Version tag bottom-left in mono 11.
2. **Campaign / star map.** Dark starfield or planet map; routes thin cyan, contract sites pulsing amber diamonds, safe/owned steady `ok`. Territory = low-alpha hatched regions. Right: planet card with contract list. Top bar: C-Bills, reputation, date, lance status (mono).
3. **Contract board.** List left (employer, type, reward, difficulty, duration), detail centre (briefing, objectives, bonus objectives, salvage rights, payment sliders), mini-map right. Difficulty = 1–5 chevron meter (amber filled / steel empty). Employer crest atop detail.
4. **Briefing.** Terrain-map hero with overlays (objective rings, drop zone, dashed cyan patrol routes); briefing text right with typewriter reveal (30 cps, skippable); VO over a static officer portrait.
5. **Mech bay / loadout.** Centre turntable on a hangar floor, cold overhead key + amber work-lights, light haze. Left: segmented stat bars (tonnage, speed, armour, heat). Right: paper-doll with hardpoints, slot list beneath; weapons table (damage/heat/range/tonnage) in mono. Over-tonnage and over-heat in `crit`. Paint/decal tab with chamfered swatches.
6. **Pilot roster.** Card grid (portrait, callsign, rank, 4-pip skills, injury state). Selected card: brackets + amber frame. Skill tree is a linear chain.
7. **Market / salvage.** Two-pane inventory with category chips. Item cards: icon, name, tonnage, cost. Comparison deltas `ok`/`crit`.
8. **Mission HUD.** See §6.
9. **Debrief.** Banner VICTORY / DEFEAT / PYRRHIC (Chakra Petch 56 caps; `ok`/`crit`/`warn`) with underline sweep. Objectives checklist, kills, damage, salvage and XP count-up (800 ms), repair/rearm table, payout total in amber.
10. **Options.** Tabs Video, Audio, Controls, Gameplay, Accessibility; 56 px rows, label left, control right; HUD colour theme selector.
11. **Loading.** Dark, slow wireframe mech silhouette, mission codename caps, tip line Barlow 16, thin progress bar.
12. **Pause.** Scene dimmed and blurred (~6 px), centred amber-framed panel: RESUME, OBJECTIVES, OPTIONS, ABORT MISSION.

---

## 6. In-mission HUD

**Principles.** Thin cyan line-work at 80% alpha with 40% glow; mono numerals; panels `ink-700` @ 80%. HUD hugs the edges; the centre belongs to the battlefield. Every element is toggleable.

- **Lance panel (bottom-left/centre).** Card per unit: portrait well (`#0E1D28`), callsign, chassis tag, **paper-doll** coloured by section integrity (`ok` → `#C7D952` scratched → `warn` → `crit` → `#383D42` gone), heat bar (cyan → heat → crit), weapon/ammo pips. Selected = bright cyan frame + brackets. Dead = greyed with diagonal slash.
- **Command bar (bottom-right).** 48 px chamfered icon buttons (Move, Attack, Hold, Retreat, Guard, Capture, Support) with hotkey tag in the corner.
- **Mini-map.** Chamfered square radar with sweep line; friendly = `friend` triangles, enemy = `crit` diamonds, neutral = grey squares, objectives = amber rings, fog = darkened hatch; compass strip on top.
- **Objective tracker (top-left).** Short bullets, current objective bold, ticks in `ok`, timer in mono.
- **Target info (top-centre).** Name, chassis, pilot, tonnage, integrity doll, range in metres, threat rank.
- **Selection.** Cyan 2 px ground ring pulsing 0.8 s; box-select = `cyan-400` @ 15% fill, 1 px border.
- **Orders.** Dashed lines with end markers: attack red, move cyan, guard blue.
- **Floating unit bars.** 3 px armour + 2 px structure bar over units, heat chip beside; fade beyond 400 m.
- **Alerts.** Top-centre ticker, caps, 18 px, colour-coded (INCOMING, UNDER FIRE, SENSOR CONTACT, OBJECTIVE COMPLETE) with a matching audio cue.
- **Reticle (if a direct-control view exists).** Thin circle + 4 gap ticks; tightens with lock; `crit` when locked.
- **Targeting.** Lock-on = four corner brackets closing over 200 ms + tone + red tint. Missile warning = red edge pulse + audio. LOS dashed grey blocked, solid clear.
- **Damage feedback.** Hit section flashes white 80 ms then new colour; crit adds spark icon and klaxon; heat > 80% shifts HUD tint toward `heat` and adds edge haze.
- **Density.** "Tactical" (all) and "Minimal" (lance cards + mini-map), cycle on a key.
- **Colour themes (accessibility).** Cyan (default), Amber, Green, White, Colour-blind safe (cyan/orange/white with pattern fills on signal colours).

---

## 7. Portraits

- **Format:** bust, 3/4 view, 512×512 source, muted dark gradient background with rim light; same camera and eye line (top third) for every portrait so rosters align.
- **Style:** gritty digital portrait, slightly desaturated, warm key and cool rim. Not photoreal, not cartoon.
- **Variety:** veteran (scars, grey), rookie, hard-bitten merc, ex-noble, sensor tech, stoic invader-clan type. Mixed gender, ethnicity, age.
- **Wardrobe:** cooling vest with tubing, neurohelmet pushed back or worn, flight suit with patches, dog tags, dressings, grease; unit patch matches lance paint.
- **UI treatment:** inset in `#0E1D28` well with 1 px `steel-500` frame; hover → cyan; wounded = red tint on bottom edge + bandage variant; dead = desaturate + slash.
- **Employers/NPCs:** same lighting, formal dress, background tinted to faction colour.
- **Crests:** 128×128, one-colour-plus-metal heraldic shields, angular, readable at 32 px.
- **Licence:** generated or commissioned originals only, no real-person likeness, provenance logged.

---

## 8. Mechs

### 8.1 Silhouette and proportion
- Silhouette distinct per class: **Light** (lean, bird-legged, exposed), **Medium** (balanced, twisting torso), **Heavy** (broad shoulders, thick legs), **Assault** (monolithic slab torso, huge arms).
- Reverse-jointed legs on light/medium humanoids, tall hip armour, torso as visual mass. Weapons are large and visible: the loadout reads from the model.
- **Lore accuracy is mandatory.** An Atlas must read as *the* Atlas. Use the modern recognisable redesign as the form target, rebuilt from scratch.
- Scale: Locust (20 t) ≈ 8 m, Atlas (100 t) ≈ 12 m; keep relative scale across the roster.

### 8.2 Surface language
- **Hard-surface PBR**: separate armour plates, panel lines, bolts, recessed vents, hydraulic pistons, cable bundles, exposed actuators at joints.
- Panel lines: primary seams 2 mm deep, secondary 1 mm; every plate edge has a light-catching bevel (≥ 2 px at 2K).
- Detail hierarchy: big (armour blocks) → medium (hatches, vents, mounts) → small (bolts, stencils, decals). Big shapes must survive RTS distance.
- Every joint shows a mechanism; armour never intersects at joints in rest pose.

### 8.3 Materials
Painted steel satin (roughness 0.45–0.6); bare metal roughness 0.35–0.45, metalness 1; paint metalness 0; rubber/cable 0.8; cockpit glass dark-tinted. Emissives only on cockpit glow, status lights, weapon ports, heat vents.

### 8.4 Weathering recipe (bake-and-paint)
1. Faction base coat. 2. AO + curvature edge wear to bare metal. 3. Top-down grime and rain streaks, muzzle soot. 4. Biome dust from the knees down. 5. Decals. 6. Damage variants Clean / Scuffed / Chipped / Scorched.

### 8.5 Markings
Stencil text (squared mono), hazard chevrons `#C9A230` on black, serials, lance numbers on shoulder and upper leg, heraldry left shoulder/chest, kill tallies on weapon arms.

### 8.6 Animation
Heavy deliberate gait with hip sway; foot plant with 2-frame hit-pause and dust. Torso twist independent of legs; arms track with slight lag. Turn rate/acceleration scale with tonnage. Idle: vent steam, actuator twitch, running lights. Death: stagger, sparks, collapse by class; limbs can be lost.

### 8.7 Destruction
Breach holes reveal internals; lost arm leaves smoking socket; crippled leg slows; cockpit kill = shutdown (lights out) vs ammo explosion (fireball + debris). Wrecks persist as burning hulks (smoke 90 s, then cooling emissive).

---

## 9. Vehicles, VTOLs, infantry

- **Vehicles:** blocky armour, animated treads, turning road wheels, traversing turrets, barrel recoil. Same panel-line language as mechs, slightly rougher, more mud.
- **VTOL/aerospace:** angular fuselage, `#FF7A2F` engine glow, contrails, flyby audio.
- **Infantry/battle armour:** small, readable; armour as chunky exosuits with jet flame; distinct colour mark at RTS distance.
- **Industrial/neutral:** safety-yellow machinery with hazard markings.
- **Wrecks/props:** deep scorch, ember emissive.

---

## 10. Terrain and environment

**Principles.** High-resolution PBR splat terrain; macro tint variation to break tiling; detail normals up close; displacement on rock; height-blended transitions; distance haze.

| Biome | Ground | Vegetation | Palette | Mood |
|---|---|---|---|---|
| Temperate forest | loam, litter, moss, mud | dense conifer/broadleaf | olive, umber | damp, overcast |
| Desert | sand, hardpan, cracked clay | scrub | ochre, sienna | bleached, hot |
| Arctic | snow, ice, frozen mud | sparse spruce | blue-white, slate | cold, hard light |
| Volcanic | basalt, ash, lava seams | burnt trunks | black, rust, ember | hostile |
| Urban/industrial | concrete, asphalt, rail | weeds | grey, rust, safety yellow | gritty |
| Jungle/swamp | mud, standing water | canopy, ferns | green-teal | humid |
| Alpine | granite, scree | sparse pines | slate, grey-green | stark |

**Ground detail.** Persistent ruts and footprints (decals fading 60–120 s), craters, scorch under fires, debris props, dust trails, mud splash in wet biomes; mechs sink slightly in soft ground.

**Structures.** Concrete-and-steel utility architecture: bunkers, hangars, comms towers, refineries, silos, tanks, barracks, walls, gates, bridges. Vents, stains, rust on roofs; dim amber windows at night. States: pristine → scorched → breached → rubble with rebar and smoke. Destructible scenery: trees snap, walls crumble, barrels and fuel tanks explode.

**Lighting.** Sun 20–45° elevation, warm key `#FFD9A8`, cool sky fill `#7FA5C8`, cascaded shadows (4 splits). Time-of-day set: Dawn, Noon, Dusk, Night, Overcast, Storm. HDR skies with cloud layers, god-rays at dawn/dusk. Exponential fog, biome-tinted, density ~0.0008–0.003, height fog in valleys.
**Post.** Filmic tonemap, subtle bloom on emissives, chromatic aberration ≤ 0.4%, vignette 15%, light grain, teal-shadow/orange-highlight grade, LUT per biome. DoF only in menus/cutscenes.
**Weather.** Rain (streaks, splash, wet roughness, puddle reflections), snow (accumulation tint), sandstorm, ash fall, heat shimmer. Weather also affects sensor range and audio muffling.

---

## 11. Weapons and combat FX

Rules: **big, bright, short, legible.** Weapon class identifiable from FX alone at RTS distance by colour + shape + motion. Additive core, soft alpha trail, brief emissive light on the scene, camera shake on heavy weapons.

| Class | Weapon | Projectile / beam | Muzzle | Impact | Colour |
|---|---|---|---|---|---|
| Energy | Lasers | Continuous 0.5–1 s beam, bright core, soft sheath, slight shimmer | Soft flash | Orange sparks, glowing melt decal | Standard `#FF4A3A`; pulse `#FF9A3A`; ER white core `#7FE7FF` sheath |
| Energy | PPC | Blue-white lightning bolt, arcing tendrils | Arc crown | Crackle, scorch ring | `#8FC8FF` / `#E8F6FF` |
| Ballistic | Autocannon | Fast tracer streak | Large flash + brass | Dirt puffs, sparks | `#FFC85A` |
| Ballistic | Machine gun | Dense short bursts | Rapid small flash | Pings, dust | `#FFE08A` |
| Ballistic | Gauss | Silver slug, distortion ring, sonic crack | Blue capacitor discharge + shock ring | Shatter + crater | `#BFD8FF` |
| Ballistic | Flamer | Orange cone with smoke | Ignition flare | Persistent ground fire | `#FF8A2F` |
| Missile | SRM | Rapid small salvo, white trail | Backblast puffs | Fast orange fireball | `#FFB04A` |
| Missile | LRM | High arcing salvo of 5–20, grey spiral smoke | Cluster puff | Staggered ring of blasts | smoke `#E8E4DA`, blast `#FFB04A` |
| Missile | Streak | Straight guided, blue-white glow | | | `#9FD0FF` |
| Support | Tag / marker / Narc | Dotted beam, ring pulse | | Beacon | `#3FC6E0`; Narc `#B07CFF` |

**Explosions:** flash (additive, 2–4 frames) + fireball (0.4–0.9 s, orange → dark smoke) + debris (sparks and chunks with gravity). Smoke columns persist 5–20 s. Large blasts add shockwave distortion and distance-scaled shake.

**Damage cues.** Armour hit: spark spray, small flash, chip debris. Structure hit: dull red-orange burst, black smoke jet. Component crit: white flash then sustained sparks/fire. Ammo explosion: huge flash, fireball, debris cone, shockwave. Heat: shoulder steam, red-orange vent glow, shimmer. Shutdown: lights fade, steam release. Destruction: staged limb shed, torso collapse, embers, lingering fire. Persistent ground fires light the scene.

**Movement FX.** Foot-dust scaled by weight and surface; jump jets with orange-white flame, smoke trail and ground blast; track dust; rotor wash.

**Support powers.** Artillery marker (violet smoke), air strike (flyby + bomb line), supply drop (pods), sensor sweep (expanding cyan ring).

**Budget.** ≤ 150 particles per typical weapon effect; billboards at range; pooled emitters.

---

## 12. Audio

### 12.1 Pillars
Heavy, physical, mechanical, low-end-led. Big machines sound enormous and slow. Distinct weapons. Rich moody ambience. Radio chatter carries the tactical layer.

### 12.2 Mech
- **Footsteps:** sub 40–80 Hz thump + metal clank + servo whirr; pitch drops with tonnage; surface variants (soil, rock, snow crunch, water splash, concrete, plate). Lights = quick mid-range steps; assaults = rumble with shake.
- **Servos:** pitch tied to motion speed; torso twist = long whine; arm tracking = short pulses.
- **Engine:** layered idle (rumble + turbine whine) rising with throttle.
- **Heat:** rising alarm, warning beeps, critical klaxon; steam hiss on vent.
- **Damage:** panel crunch, hull groan, electrical fizz.
- **Power:** shutdown sweep down; start-up spool with relay clicks.

### 12.3 Weapons
Lasers: bright zap with low tail (large = longer rise/thrum; pulse = staccato). PPC: electrical crack + thunder rumble. Autocannons: punchy report + bolt cycle, AC/20 bass-heavy. Machine guns: tight rattle. Gauss: capacitor whine-up then massive thump-crack. Missiles: launch whoosh, flight whistle, staggered crumps. Flamer: roaring hiss + ignition whump. Impacts: metal clang vs dull thud vs earth burst by surface. Every weapon has **fire**, **flight/loop**, **impact** layers and a distance-filtered tail (muffled beyond 300 m).

### 12.4 UI
Tactile, low-key, mechanical: soft click, very quiet hover tick, select chirp, two-tone ascending confirm, deny buzz, electronic panel swish, typewriter ticks in briefings, electronic ledger tone for C-Bills, klaxon for objectives. No cartoon bloops.

### 12.5 Voice
- **Pilots:** gruff clipped radio ("Copy." "Moving." "Engaging." "Taking fire!" "Target down."), death cry cut by static; each pilot has unique voice and barks.
- **Computer voice:** calm, measured synthetic female for status (heat critical, armour breach, target destroyed, missile lock, reactor shutdown). **Our own voice and name** (`assets/audio/betty` is the folder; the voice must not imitate the MW games' computer).
- **Employer/briefing:** cold corporate for employers, weathered commander for the lance.
- **Radio filter:** band-pass 400–3400 Hz, light bit-crush, squelch tail, static bed.

### 12.6 Music
Menus/campaign: brooding orchestral-electronic hybrid, low strings, analogue pads, sparse piano, 60–80 BPM. Exploration: drones, sub pulses, distant metal percussion. Combat: driving percussion, taiko-like drums, distorted bass, stem layers rising with intensity, fading within 8 s of last contact. Victory: short heroic brass sting. Defeat: descending drones. Music sits −6 dB below SFX in combat and ducks for VO. Original or CC0/CC-BY only.

### 12.7 Ambience
Biome wind, distant artillery, wildlife in calm biomes, industrial hum and alarms in urban, rain/thunder in storm, crackling fires, creaking wrecks. 3D-positioned loops with occlusion.

### 12.8 Mix
Priority: VO > alerts > weapons > footsteps > ambience > music. Ambience ~−20 dB under weapons, UI ~−18 dB. Optional night-mode compressor.

---

## 13. Camera and presentation
RTS camera 55–65° pitch, FOV 40–50, adjustable zoom, 120 ms damping. Optional kill-cam: low-angle dolly, 0.3× slow-mo for 0.8 s on big kills. Cutscenes letterboxed 2.39:1 with grain, skippable. Hangar/photo mode uses a 3-point lighting preset.

## 14. Writing and tone
Terse military-corporate, present tense, precise numbers (tons, metres, C-Bills). Employer text slightly cynical. Caps for headers and labels only. No exclamation marks outside radio barks. All text original; no verbatim PGI/Microsoft/Catalyst lore.

---

## 15. Asset specifications (Godot 4)

| Asset | Spec |
|---|---|
| Mech mesh | 40–80k tris LOD0, LOD1 50%, LOD2 15%, LOD3 impostor; separate mesh per limb; hardpoint nodes; Y-up, metres |
| Vehicle mesh | 10–30k tris LOD0, same ratios |
| Mech textures | 2K (4K assault): Albedo sRGB, Normal OpenGL +Y, ORM (R=AO, G=Rough, B=Metal), Emissive; trim sheet + unique bake |
| Terrain layers | 2K tileable albedo/normal/ORM, ≥ 8 layers per biome, height in alpha |
| Portraits | 512² PNG sRGB |
| UI icons | SVG source → 32/64/128 PNG, 2 px stroke at 32 |
| UI panels | 9-slice with chamfer corners, or shader-drawn |
| FX sprites | 512² flipbooks 4×4 / 8×8, premultiplied alpha |
| Audio | WAV 48 kHz 16-bit source, OGG in build, zero-crossing loops, mono for 3D, stereo for music/ambience |
| Fonts | TTF/OTF, OFL, `assets/fonts/` |
| Naming | `snake_case`, `category_name_variant_##` |

Texel density: mechs 5.12 px/cm, terrain props 2.56 px/cm. Every asset logs **source, licence, author, date, modifications** in `docs/art-provenance.md`; no provenance = gate failure.

---

## 16. Quality bar (ship checklist)

- [ ] Reads at RTS distance (silhouette and colour) before detail is judged.
- [ ] Matches palette, geometry and type rules here.
- [ ] Lore-accurate for the named unit.
- [ ] Hard-surface PBR with believable panel lines and purposeful wear; no uniform noise.
- [ ] Provenance recorded; nothing from PGI / Microsoft / Catalyst.
- [ ] Budget met (tris, texture, particles).
- [ ] Accessible: colour not sole carrier, contrast met, reduced motion respected.
- [ ] Audio layered, loop-clean, within loudness targets, distance-filtered.

## 17. Reference method
Keep MW5/MWO screenshots, trailers and teardowns **outside the repo**. Study silhouettes, value structure, panel layout, colour scheme, FX timing. Redraw, remodel and re-record from scratch. Never trace, rip, extract or reuse game files, fonts, voice lines, music, logos, names or UI graphics. Test: *could this be mistaken for their file?* If yes, change it.

## 18. Do / Don't

| Do | Don't |
|---|---|
| Chamfered 45° corners | Rounded corners, pill buttons |
| Thin cyan HUD lines, amber menus | Rainbow neon, thick outlines |
| Squared condensed type | Script, rounded, comic fonts |
| Moody low-key light, long shadows | Flat bright daylight |
| Heavy slow mech animation | Fast bouncy walks |
| Panel lines, bolts, hydraulics | Smooth blobby shapes |
| Colour + shape for state | Colour alone |
| Short punchy FX with bloom | Long translucent mush |
| Original names and voice | "Betty", BattleMech trademarks, PGI logos |

---

## 19. Known contradictions (this guide wins)

Found in `game/scripts` at time of writing:

1. **Two competing UI palettes.** A green-accent set (`ACCENT #73FF8C`, `PANEL_EDGE`, `BG`, as in `debrief.gd` and menu screens) vs the cyan HUD set (`HUD_EDGE #3FC6E0` etc.). Menus, campaign and debrief move to **amber** (§2.1); the HUD stays cyan. Green is reserved for `ok`.
2. The `HUD_*` constants (`INK #E8F1F4`, `DIM #8FA6B2`, `OK #4FD38A`, `WARN #F2B54A`, `CRIT #FF5A4E`, `HOT #FF7A2F`, `FACE #0E1D28`) are **kept**; rename to the §2.1 tokens when touched.
3. Paper-doll ramp (`SCRATCHED`, `GONE`) is **kept** (§6).
4. Procedural/noise-only v1/v2 art is **superseded** by §8.4 and §10; `docs/art/rework-audit.md` priorities follow this guide.
5. Any note that chassis may be freely reinterpreted: **lore accuracy governs** (§8.1).
6. Faction colours in `paint_scheme.gd` are replaced by §2.3 where they differ.
7. Memory note `mc2-art-direction` and the `game-art` agent prompt must be updated to point here.

## 20. Adoption plan
1. Lock tokens: eyedrop private references, adjust §2.1, commit `game/data/theme/style_tokens.json`, generate a Godot `Theme` from it.
2. Reskin menu → campaign → mech bay → debrief (amber layer); align HUD.
3. Six hero pilot portraits → approve → roll out.
4. Atlas through the §8 recipe as the pilot mech → approve → roll out.
5. Terrain biome kit and lighting/post presets (§10).
6. FX and audio pass per §11–12 with a review sheet per class.
7. Add the §16 checklist to the swarm gates.
