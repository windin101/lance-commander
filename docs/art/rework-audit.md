# HD model and texture rework: phase 0 audit and the phase 3 pilot

Started 2026-10-23 from Lee's verdict: the HD models look bad in game, in the Mech Bay and the Mech Lab close-ups.
The sculpts are fine. What's wrong is the articulation (plane cuts, rigid per-triangle skinning, stub caps) and the
texturing (no UVs: the original's 128 px mask projected and recoloured onto a palette, so colours are flat and the
two highlights hardly show). Buildings are the original boxes with upscaled 128 px art.

## What is installed today (382 assets)

- **Mechs (30):** 22 are printable sculpts rigged by `stl_rig.py`, 1 by `stl_rig_vulture.py`, 2 copters by `stl_hd.py`,
  and 5 are Hunyuan3D meshes (BloodAsp, Enfield, Hollander, Menshen, Starslayer). The sculpts have 70k to 206k
  triangles with palette UVs, so each colour is one flat texel of a 128 px palette. The Hunyuan five have real UVs with
  2048 px normal and AO maps, but their meshes are soft.
- **Vehicles (28):** all of them are printable sculpts adapted by `stl_hd.py`, vertex-clustered to about 40k
  triangles, with the same palette UVs. Clustering is what makes the faceted, "crumpled" look in close-ups (the LRM
  carrier's launcher tubes are lost).
- **Objects (324 appearances; 493 object .glb files with the 169 damage variants):** 151 are the original meshes
  with 4x-upscaled textures (`_hdtex`), 137 are SolidCraft rebuilds with the original art baked on (`_cad`), and 36
  are trees drawn by `trees.py` as MultiMesh, which are out of scope.
- **A loader bug the audit found:** `objects_view.gd` and `mech_stage.gd` prefer `_cad`, then `_hdtex`, then `_hd`.
  The 7 approved sculpt props (three dropships, the lifeboat, the private jet, the Shilone and the Slayer) also have
  an `_hdtex.glb`, so their sculpt `_hd.glb` never loads. Not fixed here: Lee decides (see Decisions).
- **Sources:** the 60 sculpts' downloads (zips, STLs and SOURCE.txt) are staged on
  `/mnt/nvme1n1p1/mc2-sources/<kind>/<name>/` (`tools/art/stage_sources.py`, `index.json`). They were all still in
  `~/craft/solid/mc2`, so nothing was re-downloaded. The script can fetch Printables models if a copy goes missing.
- **Contact sheets:** `/mnt/nvme1n1p1/mc2-rework/audit/sheet_{mech,vehicle,object}_NN.png`, made by
  `tools/art/rework_sheet.py` from `game/scenes/art_gallery.tscn`. Each row has three turntable stills in the bay
  studio plus a close-up at Mech Lab distance (fill 2.4).

## Priority

The score is visibility x frequency x quality deficit (`rework_audit.py priority()`):

- **Visibility:** mech 3, vehicle 2, object 1, with objects scaled by size.
- **Frequency:** log placements plus the square root of the missions an asset appears in. Every mech gets +3,
  because the bay, lab and market show them all.
- **Deficit:** +1 for palette UVs, +1 for plane-cut rigs, +0.8 for Hunyuan meshes, +0.6 for original meshes, and
  +0.4 for objects with textures under 512 px.

1. **Mechs (do all 22 sculpts; the 5 Hunyuan ones need sculpts first):** werewolf, bushwacker, hunchback, catapult,
   shayu, flea, highlander, anubis, urbanmech, zeus, shootist, raven, madcat, jaegermech, atlas, uller, laohu,
   shadowcat, wolfhound, vulture, mediumcopter, thor, cyclops, heavycopter, ryoken.
2. **Vehicles:** poweredarmor (rigged like a mech), lrmc, centipede, harasser, vedette, partisan, hunter, hetzer,
   storm, infantry, cargotruck, swarmlrmc, then the rest.
3. **Buildings** (by placements x size; walls and fences top the raw score but are small and simple):
   quonsetclean, l_turretgenerator, portable, lookouttower, rpbuilding, genericmilitary, geodesicdome,
   mediumautocannonturret, ammodump, truckprop, singlecivlivingb, s_turretcontrol, longtent, singlecivlivinga, 2civliving.
4. **Walls and fences** (s/l/d light, medium and heavy walls, wire and razor-wire fences, sandbags): one tiling-material
   pass over the whole family at once, as for the buildings.

## The pilot pipeline (phase 3 applied to three assets)

The pilots are staged in `game/assets/v2/` and load only with the `ArtV2` dev switch on. Full commands and licences
are in `docs/art-provenance.md` under "HD rework v2".

### Articulation

`tools/art/hd_v2.py`, stages `fit` and `segment`:

1. `stl_rig.py`'s fit runs unchanged (state captured from its `write()` call), then the watertight raw sculpt is
   re-segmented. Seeds are placed along each leg bone and the pelvis line, and in the cores of stl_rig's upper-body
   parts. Multi-source Dijkstra then grows regions over the face graph, where crossing a crease is costly. An
   alpha-expansion graph cut refines the result. The seams then follow the kit's own panel lines and concave
   junctions, not a plane through the armour.
2. **Actuators.** A crease seam opens at any rotation; only a surface of revolution about the joint axis stays
   closed. So at each joint the sculpt inside an actuator is dropped.
   - The actuator is a ball for multi-axis joints, or a drum about the dominant animated axis. That axis is the PCA
     of every animation's rotation vectors: knees and the launcher are hinges, and the waist is a drum about the
     twist axis.
   - It is sized to the limb's section at the pivot, then shrunk until at most 20 % of it stands out of the body.
   - Where the pivot lies outside the shell, there is no actuator.
   - The shader shades back faces dark, so an opening shows the inside of the part, not the far side of the mech.
3. **Pose test:** `tools/art/pose_test.py`. It drives every animation in the .glb exactly as glTF skins it. It
   measures each joint's seam opening (seam vertices to the nearest covering surface, with analytic actuators
   counted as cover) and new interpenetration against the rest pose.

### Textures

Stages `bake` and `paint`:

1. **UVs and bakes.** Blender 5.2 headless runs Smart UV Project (one atlas, shared texel density), then Cycles bakes
   AO, a bevelled-edge normal map (only bevel minus true normal, so STL facets don't stripe), position, face index and
   coverage.
2. **Zone mask.** The original's own mask is mapped by part (bounding box to bounding box for mechs, direct for fitted
   vehicles). Each crease panel then takes its area-weighted majority, so zone edges follow the sculpt's panels. Zones:
   base, highlight 1, highlight 2, bare steel, dark metal, glass/emissive. Unit-number decals go on the largest flat
   panels, and curvature comes from the edge normals.
3. **Shader.** `game/shaders/unit_hd.gdshader`, one for mechs and vehicles. It takes the team paint from the mission's
   three colours (via `MechPaint.apply`, which now recognises a `_v2` name). On top it adds:
   - chipped edges from curvature, broken up by a tiling grunge texture, and grime from AO;
   - panel lines, scorch blotches and stencil decals;
   - emissive lights, and the wreck burn (`MechView._scorch` handles ShaderMaterial);
   - the per-mission dust and snow layer (`game/data/unit_weather.json` via `MechPaint.set_environment_for`).

   Wear and panel lines fade out between 35 and 110 m from the camera, so the RTS view doesn't sparkle.

### Buildings

`tools/art/hd_v2_building.py`:

- The CAD model is rebuilt with true arcs (`CAD_ARC_SEGMENTS=96`; v1 output unchanged).
- Faces are classified by CAD body and the openings: galvanised sheet, painted end wall, trim, door, glass, concrete.
- Each surface type gets a tiling procedural PBR set (`tools/art/hd_v2_textures.py`).
- AO is baked on a second UV set. `ArtV2.dress_object` swaps the materials for `building_hd.gdshader` at load.

### Vehicles

Stage `fitveh`: `stl_hd.py`'s fit, without the vertex clustering. The 653k-triangle kit is decimated in Blender
(merge, planar dissolve, gentle collapse) to 150k, which is visually lossless. Godot's import LODs serve the RTS
camera.

## Pilot results

- **Pose test, Bushwacker, locomotion animations, gap p95 (m, worst pose), v1 → v2:**

  | Part | v1 | v2 |
  |---|---|---|
  | luarm | 1.47 | 0.64 |
  | lgun | 1.26 | 0.73 |
  | torso | 1.05 | 0.52 |
  | ruleg | 0.92 | 0.32 |
  | luleg | 0.77 | 0.51 |
  | lfoot | 0.48 | 0.16 |
  | llleg | 0.47 | 0.17 |
  | hip | 0.43 | 0.53 |
  | rfoot | 0.37 | 0.22 |
  | rlleg | 0.29 | 0.28 |

  - Every joint still fails the 3 cm gate. The test measures how far a seam vertex is from anything that could cover
    it, and the dark interiors hide most of the openings in the renders.
  - The remaining openings are at the waist, the hip/thigh seams and the arm on the gun side. They need actuators
    that cover the whole limb section, so either visibly bigger joints or kit-specific seam placement.
  - The interpenetration figure saturates near its 0.3 m cap on both versions. It is not a usable gate yet.
- **Performance, mc2_23** (4 Bushwackers, 18 LRM carriers, a Quonset block), 20 s at 1920x1080, RTS camera:
  - GPU 1.36 to 1.80 ms (v1) against 1.51 to 1.52 ms (v2).
  - CPU frame time is dominated by the other agent's sim sweeps on the machine, so it isn't comparable.
- **Texture memory, VRAM-compressed (BPTC), with mipmaps:**
  - Bushwacker: 3 x 2048² ≈ 16.8 MB.
  - LRM carrier: 3 x 1024² ≈ 4.2 MB.
  - Quonset: AO 1024² ≈ 1.4 MB, plus shared building sets ≈ 3.5 MB.
  - Budget proposal: 16 MB per mech type, 4 MB per vehicle type, 2 MB plus the shared sets per building.

<!-- audit:begin -->
Generated by `tools/art/rework_audit.py` from the installed assets and the 24 missions' parts and objects.json. 30 mechs, 28 vehicles, 324 objects. Full data: `swarm/gallery/rework_audit.json`.

### Mechs

| # | Asset | Pipeline | Source / licence | Tris | UV | Textures | Placed (missions) | Sculpt on disk | Priority |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `werewolf` | STL sculpt (stl_rig) | ["Werewolf Battlemech" by UnrestedGuy](https://www.thingiverse.com/thing:6992277), CC BY-NC-SA 4.0 | 165021 | palette | 128, 64 | 76 (20) | yes | 103.5 |
| 2 | `bushwacker` | STL sculpt (stl_rig) | ["BSW-X1, X2 & S2 Bushwacker for Battletech" by Syllogy](https://www.printables.com/model/1863885), CC BY-NC-SA 4.0 | 114618 | palette | 128, 64 | 40 (19) | yes | 94.8 |
| 3 | `hunchback` | STL sculpt (stl_rig) | ["HBK-4G Hunchback for Battletech" by Syllogy](https://www.printables.com/model/1863925), CC BY-NC-SA 4.0 | 115502 | palette | 128, 64 | 40 (16) | yes | 93.2 |
| 4 | `catapult` | STL sculpt (stl_rig) | ["CPLT-C1 Catapult Alternative Art for Battletech" by Syllogy](https://www.printables.com/model/1863887), CC BY-NC-SA 4.0 | 159648 | palette | 128, 64 | 35 (12) | yes | 89.1 |
| 5 | `shayu` | STL sculpt (stl_rig) | ["Sha Yu Battlemech" by UnrestedGuy](https://www.thingiverse.com/thing:6498513), CC BY-NC-SA 4.0 | 158624 | palette | 128, 64 | 38 (10) | yes | 88.8 |
| 6 | `flea` | STL sculpt (stl_rig) | ["FLE-4 Flea for Battletech" by Syllogy](https://www.printables.com/model/1863913), CC BY-NC-SA 4.0 | 119176 | palette | 128, 64 | 42 (7) | yes | 87.7 |
| 7 | `highlander` | STL sculpt (stl_rig) | ["HGN-732 Highlander for Battletech" by Syllogy](https://www.printables.com/model/1863932), CC BY-NC-SA 4.0 | 115710 | palette | 128, 64 | 22 (12) | yes | 83.3 |
| 8 | `anubis` | STL sculpt (stl_rig) | ["Anubis Battlemech" by UnrestedGuy](https://www.thingiverse.com/thing:7387482), CC BY-NC-SA 4.0 | 125014 | palette | 128, 64 | 27 (8) | yes | 83.0 |
| 9 | `urbanmech` | STL sculpt (stl_rig) | ["UM-R60 Urbanmech for Battletech" by Syllogy](https://www.printables.com/model/1864017), CC BY-NC-SA 4.0 | 139270 | palette | 128, 64 | 27 (7) | yes | 82.2 |
| 10 | `zeus` | STL sculpt (stl_rig) | ["Zeus ZEU-6A" by ChewiewookTheVindicator](https://www.thingiverse.com/thing:7089967), CC BY-SA 4.0 | 126781 | palette | 128, 64 | 21 (10) | yes | 81.4 |
| 11 | `shootist` | STL sculpt (stl_rig) | ["Shootist Battlemech" by UnrestedGuy](https://www.thingiverse.com/thing:7263860), CC BY-NC-SA 4.0 | 136513 | palette | 128, 64 | 17 (8) | yes | 77.3 |
| 12 | `raven` | STL sculpt (stl_rig) | ["RVN-1X Raven for Battletech" by Syllogy](https://www.printables.com/model/1863995), CC BY-NC-SA 4.0 | 103582 | palette | 128, 64 | 18 (7) | yes | 77.1 |
| 13 | `madcat` | STL sculpt (stl_rig) | ["Timberwolf Prime, aka Madcat for Battletech" by Syllogy](https://www.printables.com/model/1864016), CC BY-NC-SA 4.0 | 139446 | palette | 128, 64 | 14 (8) | yes | 74.9 |
| 14 | `jaegermech` | STL sculpt (stl_rig) | ["JM6-S4 Jagermech for Battletech" by Syllogy](https://www.printables.com/model/1863950), CC BY-NC-SA 4.0 | 131402 | palette | 128, 64 | 14 (6) | yes | 73.2 |
| 15 | `atlas` | STL sculpt (stl_rig) | ["AS7-D Atlas for Battletech" by Syllogy](https://www.printables.com/model/1863870), CC BY-NC-SA 4.0 | 185538 | palette | 128, 64 | 10 (8) | yes | 70.9 |
| 16 | `uller` | STL sculpt (stl_rig) | ["BattleTech Kit Fox (Uller) Alt Config V" by MiniHulkMechs](https://www.thingiverse.com/thing:6431420), CC BY-NC-SA 4.0 | 205852 | palette | 128, 64 | 12 (4) | yes | 69.3 |
| 17 | `laohu` | STL sculpt (stl_rig) | ["Lao Hu Battlemech" by UnrestedGuy](https://www.thingiverse.com/thing:6505435), CC BY-NC-SA 4.0 | 183846 | palette | 128, 64 | 10 (5) | yes | 68.2 |
| 18 | `shadowcat` | STL sculpt (stl_rig) | ["Shadowcat Prime for Battletech" by Syllogy](https://www.printables.com/model/1863998), CC BY-NC-SA 4.0 | 108266 | palette | 128, 64 | 10 (5) | yes | 68.2 |
| 19 | `wolfhound` | STL sculpt (stl_rig) | ["WFL-1-P Wolfhound for Battletech" by Syllogy](https://www.printables.com/model/1864059), CC BY-NC-SA 4.0 | 109232 | palette | 128, 64 | 10 (4) | yes | 67.1 |
| 20 | `vulture` | STL sculpt (stl_rig_vulture) | CC BY-NC-SA 4.0 | 48694 | palette | 128, 64 | 6 (4) | yes | 61.3 |
| 21 | `mediumcopter` | STL sculpt (stl_hd) | ["Hawk Moth" by RGriffin65](https://www.thingiverse.com/thing:6599138), CC BY-SA 4.0 | 39740 | palette | 128, 64 | 32 (11) | yes | 58.2 |
| 22 | `hollander` | Hunyuan3D | MC2 Shared Source (NC) | 16397 | unwrapped | 2048, 2048, 1024, 128 | 36 (15) | n/a | 54.8 |
| 23 | `thor` | STL sculpt (stl_rig) | ["Summoner Prime, AKA Thor for Battletech" by Syllogy](https://www.printables.com/model/1864004), CC BY-NC-SA 4.0 | 129304 | palette | 128, 64 | 3 (3) | yes | 52.8 |
| 24 | `starslayer` | Hunyuan3D | MC2 Shared Source (NC) | 8732 | unwrapped | 2048, 2048, 1024, 128 | 27 (12) | n/a | 51.5 |
| 25 | `cyclops` | STL sculpt (stl_rig) | ["CP-10-Z Cyclops for Battletech" by Syllogy](https://www.printables.com/model/1863895), CC BY-NC-SA 4.0 | 114240 | palette | 128, 64 | 3 (2) | yes | 51.4 |
| 26 | `menshen` | Hunyuan3D | MC2 Shared Source (NC) | 11578 | unwrapped | 2048, 2048, 1024, 128 | 21 (8) | n/a | 47.9 |
| 27 | `heavycopter` | STL sculpt (stl_hd) | ["Balac VTOL" by RGriffin65](https://www.thingiverse.com/thing:6758723), CC BY-SA 4.0 | 39675 | palette | 128, 64 | 9 (5) | yes | 44.6 |
| 28 | `enfield` | Hunyuan3D | MC2 Shared Source (NC) | 12395 | unwrapped | 2048, 2048, 1024, 128 | 15 (3) | n/a | 42.5 |
| 29 | `ryoken` | STL sculpt (stl_rig) | ["Stormcrow Prime, AKA Ryoken for Battletech" by Syllogy](https://www.printables.com/model/1863997), CC BY-NC-SA 4.0 | 70736 | palette | 128, 64 | 1 (1) | yes | 40.5 |
| 30 | `bloodasp` | Hunyuan3D | MC2 Shared Source (NC) | 13636 | unwrapped | 2048, 2048, 1024, 128 | 2 (1) | n/a | 27.5 |

### Vehicles

| # | Asset | Pipeline | Source / licence | Tris | UV | Textures | Placed (missions) | Sculpt on disk | Priority |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `poweredarmor` | STL sculpt (stl_rig) | ["Irontold Hawkish Battle Armor (American Mecha)" by maggiweber](https://www.thingiverse.com/thing:5215239), CC BY 4.0 | 104712 | palette | 64, 64 | 59 (6) | yes | 42.8 |
| 2 | `lrmc` | STL sculpt (stl_hd) | ["Heavy LRM Carrier" by RGriffin65](https://www.thingiverse.com/thing:7132255), CC BY-SA 4.0 | 39513 | palette | 128, 64 | 121 (19) | yes | 36.4 |
| 3 | `centipede` | STL sculpt (stl_hd) | ["Centipede Scout Car (Wheeled)" by RGriffin65](https://www.thingiverse.com/thing:7044273), CC BY-SA 4.0 | 39686 | palette | 64, 64 | 80 (16) | yes | 33.4 |
| 4 | `harasser` | STL sculpt (stl_hd) | ["Harasser Hovercraft" by RGriffin65](https://www.thingiverse.com/thing:6734633), CC BY-SA 4.0 | 48823 | palette | 128, 64 | 83 (13) | yes | 32.8 |
| 5 | `vedette` | STL sculpt (stl_hd) | ["FightTech - Vedariant - 6mm" and "SciFi Vehicle - Aurochs-class Land Crawler - 6mm" (its Tank-Schrek turret) by Shiaic3D](https://www.printables.com/model/359188), CC BY 4.0 | 10496 | palette | 128, 64 | 57 (14) | yes | 30.9 |
| 6 | `partisan` | STL sculpt (stl_hd) | ["Partisan Heavy Tank" by RGriffin65](https://www.thingiverse.com/thing:6943425), CC BY-SA 4.0 | 39060 | palette | 128, 64 | 46 (11) | yes | 28.9 |
| 7 | `hunter` | STL sculpt (stl_hd) | ["Hunter Light Tank" by RGriffin65](https://www.thingiverse.com/thing:6935510), CC BY-SA 4.0 | 49521 | palette | 128, 64 | 43 (8) | yes | 27.5 |
| 8 | `hetzer` | STL sculpt (stl_hd) | ["Hetzer (LRM) for battletech" by PrysmaTheMagical](https://www.thingiverse.com/thing:6459522), CC BY-SA 4.0 | 28683 | palette | 128, 64 | 38 (9) | yes | 27.1 |
| 9 | `storm` | STL sculpt (stl_hd) | ["Storm heavy tank" by RGriffin65](https://www.thingiverse.com/thing:6914336), CC BY-SA 4.0 | 38938 | palette | 128, 64 | 32 (11) | yes | 26.8 |
| 10 | `infantry` | STL sculpt (stl_hd) | ["Future - Generic Space Infantry Troops" by Guy_montag](https://www.printables.com/model/114328), CC BY-NC-SA 4.0 | 13002 | palette | 64, 64 | 39 (4) | yes | 25.3 |
| 11 | `cargotruck` | STL sculpt (stl_hd) | ["SciFi Vehicle Set 2 - Medium Trucks and Buses - 6mm" by Shiaic3D](https://www.printables.com/model/108619), CC BY 4.0 | 59581 | palette | 128, 64 | 28 (8) | yes | 25.1 |
| 12 | `swarmlrmc` | STL sculpt (stl_hd) | ["Semi-Modular Weapons Carrier" by RGriffin65](https://www.thingiverse.com/thing:7123873), CC BY-SA 4.0 | 38437 | palette | 128, 64 | 27 (6) | yes | 24.1 |
| 13 | `drillson` | STL sculpt (stl_hd) | ["Drillson Support Hover" by RGriffin65](https://www.thingiverse.com/thing:6743061), CC BY-SA 4.0 | 39466 | palette | 128, 64 | 22 (8) | yes | 23.8 |
| 14 | `fueltruck` | STL sculpt (stl_hd) | ["Fuel Truck" by RGriffin65](https://www.thingiverse.com/thing:7285869), CC BY-SA 4.0 | 69507 | palette | 128, 64 | 17 (9) | yes | 22.7 |
| 15 | `monsoon` | STL sculpt (stl_hd) | ["Saracen, Scimitar, and Saladin Hovertanks" by UnrestedGuy](https://www.thingiverse.com/thing:7255716), CC BY-NC-SA 4.0 | 19234 | palette | 128, 64 | 16 (6) | yes | 21.2 |
| 16 | `trooptransport` | STL sculpt (stl_hd) | ["Packrat, APCs and Heavy APCs for use with Battletech" by Pfelpensson](https://www.thingiverse.com/thing:4592096), CC BY 4.0 | 11918 | palette | 128, 64 | 13 (4) | yes | 19.2 |
| 17 | `legion` | STL sculpt (stl_hd) | ["Legion MBT" by RGriffin65](https://www.thingiverse.com/thing:6617086), CC BY-SA 4.0 | 39642 | palette | 128, 64 | 14 (2) | yes | 18.5 |
| 18 | `ordnancetruck` | STL sculpt (stl_hd) | ["Utility Truck" by RGriffin65](https://www.thingiverse.com/thing:6831725), CC BY-SA 4.0 | 38858 | palette | 128, 64 | 11 (4) | yes | 18.3 |
| 19 | `ambulance` | STL sculpt (stl_hd) | ["FightTech - Small Military Car (HBS) - 6mm" by Shiaic3D](https://www.printables.com/model/108537), CC BY 4.0 | 10366 | palette | 128, 64 | 7 (3) | yes | 15.5 |
| 20 | `aerospotter` | STL sculpt (stl_hd) | ["C3 mobile Radar command unit" by RGriffin65](https://www.thingiverse.com/thing:6874543), CC BY-SA 4.0 | 38972 | palette | 128, 64 | 6 (4) | yes | 15.2 |
| 21 | `armoredcar` | STL sculpt (stl_hd) | ["Light Wheeled APC" by RGriffin65](https://www.thingiverse.com/thing:7358113), CC BY-SA 4.0 | 39903 | palette | 128, 64 | 7 (2) | yes | 14.8 |
| 22 | `jeep` | STL sculpt (stl_hd) | ["SciFi Vehicle Set 1 - Cars - 6mm" by Shiaic3D](https://www.printables.com/model/108620), CC BY 4.0 | 8310 | palette | 64, 64 | 5 (3) | yes | 13.8 |
| 23 | `mog` | STL sculpt (stl_hd) | ["Mobile Orbital Gun" by RGriffin65](https://www.thingiverse.com/thing:7180780), CC BY-SA 4.0 | 38984 | palette | 256, 64 | 4 (3) | yes | 12.8 |
| 24 | `mobilehq` | STL sculpt (stl_hd) | ["Praetorian Mobile HQ" by RGriffin65](https://www.thingiverse.com/thing:6599003), CC BY-SA 4.0 | 39837 | palette | 128, 64 | 3 (3) | yes | 11.5 |
| 25 | `truck` | STL sculpt (stl_hd) | ["Flatbed Truck" by RGriffin65](https://www.thingiverse.com/thing:7279963), CC BY-SA 4.0 | 38740 | palette | 128, 64 | 3 (3) | yes | 11.5 |
| 26 | `apc` | STL sculpt (stl_hd) | ["Light Wheeled APC" by RGriffin65](https://www.thingiverse.com/thing:7358113), CC BY-SA 4.0 | 39903 | palette | 128, 64 | 4 (1) | yes | 11.3 |
| 27 | `minelayer` | STL sculpt (stl_hd) | ["Minelayer" by RGriffin65](https://www.thingiverse.com/thing:6916656), CC BY-SA 4.0 | 39518 | palette | 128, 64 | 2 (1) | yes | 8.3 |
| 28 | `repairtruck` | STL sculpt (stl_hd) | ["Savior Recovery/Repair vehicle" by RGriffin65](https://www.thingiverse.com/thing:6786889), CC BY-SA 4.0 | 39700 | palette | 128, 64 | 1 (1) | yes | 6.0 |

### Objects (top 60 by priority; the rest are in the JSON)

| # | Asset | Pipeline | Source / licence | Tris | UV | Textures | Placed (missions) | Sculpt on disk | Priority |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `s_lightwall` | original mesh + upscaled texture | MC2 Shared Source (NC) | 62 | unwrapped | 512 | 866 (10) | n/a | 36.3 |
| 2 | `l_lightwall` | original mesh + upscaled texture | MC2 Shared Source (NC) | 42 | unwrapped | 512 | 483 (7) | n/a | 32.8 |
| 3 | `wirefence` | original mesh + upscaled texture | MC2 Shared Source (NC) | 4 | unwrapped | 256 | 1467 (19) | n/a | 32.8 |
| 4 | `razorwirefence` | original mesh + upscaled texture | MC2 Shared Source (NC) | 8 | unwrapped | 256 | 1550 (16) | n/a | 32.3 |
| 5 | `s_mediumwall` | original mesh + upscaled texture | MC2 Shared Source (NC) | 98 | unwrapped | 512 | 423 (7) | n/a | 32.2 |
| 6 | `d_lightwall` | original mesh + upscaled texture | MC2 Shared Source (NC) | 32 | unwrapped | 512 | 335 (5) | n/a | 30.4 |
| 7 | `l_mediumwall` | original mesh + upscaled texture | MC2 Shared Source (NC) | 58 | unwrapped | 512 | 248 (5) | n/a | 29.0 |
| 8 | `sandbagwall` | original mesh + upscaled texture | MC2 Shared Source (NC) | 30 | unwrapped | 256 | 488 (16) | n/a | 27.6 |
| 9 | `s_heavywall` | original mesh + upscaled texture | MC2 Shared Source (NC) | 106 | unwrapped | 512 | 219 (1) | n/a | 26.5 |
| 10 | `wirefencediag` | original mesh + upscaled texture | MC2 Shared Source (NC) | 4 | unwrapped | 256 | 130 (6) | n/a | 26.4 |
| 11 | `longtent` | original mesh + upscaled texture | MC2 Shared Source (NC) | 28 | unwrapped | 512 | 86 (17) | n/a | 25.7 |
| 12 | `rock_gfield1` | original mesh + upscaled texture | MC2 Shared Source (NC) | 51 | unwrapped | 512 | 101 (5) | n/a | 24.9 |
| 13 | `l_heavywall` | original mesh + upscaled texture | MC2 Shared Source (NC) | 58 | unwrapped | 512 | 142 (1) | n/a | 24.5 |
| 14 | `rock_gfield2` | original mesh + upscaled texture | MC2 Shared Source (NC) | 51 | unwrapped | 512 | 80 (6) | n/a | 24.2 |
| 15 | `rock_dfield1` | original mesh + upscaled texture | MC2 Shared Source (NC) | 50 | unwrapped | 512 | 122 (1) | n/a | 23.8 |
| 16 | `d_mediumwall` | original mesh + upscaled texture | MC2 Shared Source (NC) | 40 | unwrapped | 512 | 95 (2) | n/a | 23.3 |
| 17 | `hqtent` | original mesh + upscaled texture | MC2 Shared Source (NC) | 42 | unwrapped | 512 | 56 (14) | n/a | 23.3 |
| 18 | `woodenfence` | original mesh + upscaled texture | MC2 Shared Source (NC) | 12 | unwrapped | 512 | 679 (13) | n/a | 23.2 |
| 19 | `truckprop` | original mesh + upscaled texture | MC2 Shared Source (NC) | 76 | unwrapped | 512 | 137 (19) | n/a | 23.1 |
| 20 | `rock_gfield3` | original mesh + upscaled texture | MC2 Shared Source (NC) | 50 | unwrapped | 512 | 56 (7) | n/a | 22.9 |
| 21 | `rock_dfield2` | original mesh + upscaled texture | MC2 Shared Source (NC) | 50 | unwrapped | 512 | 86 (1) | n/a | 22.2 |
| 22 | `mediumautocannonturret` | original mesh + upscaled texture | MC2 Shared Source (NC) | 60 | unwrapped | 512, 512 | 143 (11) | n/a | 22.0 |
| 23 | `rock_dfield3` | original mesh + upscaled texture | MC2 Shared Source (NC) | 50 | unwrapped | 512 | 70 (1) | n/a | 21.3 |
| 24 | `sandbagbunker` | original mesh + upscaled texture | MC2 Shared Source (NC) | 64 | unwrapped | 256 | 94 (13) | n/a | 21.1 |
| 25 | `streetlight` | original mesh + upscaled texture | MC2 Shared Source (NC) | 14 | unwrapped | 512 | 468 (10) | n/a | 21.0 |
| 26 | `tripodbarricade` | original mesh + upscaled texture | MC2 Shared Source (NC) | 40 | unwrapped | 512 | 283 (19) | n/a | 20.9 |
| 27 | `razorwirefencediag` | original mesh + upscaled texture | MC2 Shared Source (NC) | 8 | unwrapped | 256 | 42 (4) | n/a | 20.6 |
| 28 | `quonsetclean` | SolidCraft CAD + baked original texture | MC2 Shared Source (NC) | 3522 | unwrapped | 2048 | 262 (20) | n/a | 20.5 |
| 29 | `cargotruckprop` | original mesh + upscaled texture | MC2 Shared Source (NC) | 96 | unwrapped | 512 | 74 (16) | n/a | 20.4 |
| 30 | `corrigatedmetalbarricade` | original mesh + upscaled texture | MC2 Shared Source (NC) | 14 | unwrapped | 512 | 223 (18) | n/a | 20.1 |
| 31 | `d_heavywall` | original mesh + upscaled texture | MC2 Shared Source (NC) | 40 | unwrapped | 512 | 53 (1) | n/a | 20.0 |
| 32 | `s_lightgate` | original mesh + upscaled texture | MC2 Shared Source (NC) | 154 | unwrapped | 512, 512 | 29 (7) | n/a | 19.9 |
| 33 | `fueltruckprop` | original mesh + upscaled texture | MC2 Shared Source (NC) | 98 | unwrapped | 512 | 60 (16) | n/a | 19.7 |
| 34 | `dumpster` | original mesh + upscaled texture | MC2 Shared Source (NC) | 24 | unwrapped | 256 | 176 (20) | n/a | 19.4 |
| 35 | `hazmat` | original mesh + upscaled texture | MC2 Shared Source (NC) | 42 | unwrapped | 128 | 194 (17) | n/a | 19.1 |
| 36 | `junk4` | original mesh + upscaled texture | MC2 Shared Source (NC) | 98 | unwrapped | 512 | 17 (12) | n/a | 18.9 |
| 37 | `rock_clump03` | original mesh + upscaled texture | MC2 Shared Source (NC) | 61 | unwrapped | 512 | 41 (1) | n/a | 18.9 |
| 38 | `rock_gclump2` | original mesh + upscaled texture | MC2 Shared Source (NC) | 50 | unwrapped | 512 | 26 (5) | n/a | 18.8 |
| 39 | `extractionmarker` | original mesh + upscaled texture | MC2 Shared Source (NC) | 2 | unwrapped | 512 | 17 (17) | n/a | 18.7 |
| 40 | `l_turretgenerator` | SolidCraft CAD + baked original texture | MC2 Shared Source (NC) | 2361 | unwrapped | 2048, 512 | 133 (23) | n/a | 18.6 |
| 41 | `rock_gclump1` | original mesh + upscaled texture | MC2 Shared Source (NC) | 49 | unwrapped | 512 | 22 (6) | n/a | 18.4 |
| 42 | `ordnancetruckprop` | original mesh + upscaled texture | MC2 Shared Source (NC) | 104 | unwrapped | 512 | 48 (11) | n/a | 18.1 |
| 43 | `tent` | original mesh + upscaled texture | MC2 Shared Source (NC) | 20 | unwrapped | 512 | 124 (18) | n/a | 17.9 |
| 44 | `spotlight` | original mesh + upscaled texture | MC2 Shared Source (NC) | 117 | unwrapped | 512 | 28 (4) | n/a | 17.6 |
| 45 | `geodesicdome` | SolidCraft CAD + baked original texture; **sculpt _hd.glb shadowed** | MC2 Shared Source (NC) | 2185 | unwrapped | 2048 | 95 (19) | n/a | 17.5 |
| 46 | `s_mediumgate` | original mesh + upscaled texture | MC2 Shared Source (NC) | 202 | unwrapped | 512, 512 | 16 (7) | n/a | 17.3 |
| 47 | `crateswithtarp` | original mesh + upscaled texture | MC2 Shared Source (NC) | 20 | unwrapped | 512 | 437 (23) | n/a | 17.0 |
| 48 | `junk2` | original mesh + upscaled texture | MC2 Shared Source (NC) | 68 | unwrapped | 512 | 25 (15) | n/a | 16.9 |
| 49 | `genericmilitary` | SolidCraft CAD + baked original texture; **sculpt _hd.glb shadowed** | MC2 Shared Source (NC) | 1251 | unwrapped | 2048, 512 | 81 (17) | n/a | 16.8 |
| 50 | `junk3` | original mesh + upscaled texture | MC2 Shared Source (NC) | 52 | unwrapped | 512 | 27 (13) | n/a | 16.8 |
| 51 | `portable` | SolidCraft CAD + baked original texture; **sculpt _hd.glb shadowed** | MC2 Shared Source (NC) | 1110 | unwrapped | 2048 | 153 (18) | n/a | 16.8 |
| 52 | `rpbuilding` | SolidCraft CAD + baked original texture | MC2 Shared Source (NC) | 1655 | unwrapped | 2048 | 73 (19) | n/a | 16.8 |
| 53 | `lookouttower` | SolidCraft CAD + baked original texture; **sculpt _hd.glb shadowed** | MC2 Shared Source (NC) | 3610 | unwrapped | 2048 | 127 (19) | n/a | 16.7 |
| 54 | `rock_gformation3` | original mesh + upscaled texture | MC2 Shared Source (NC) | 40 | unwrapped | 512 | 18 (5) | n/a | 16.5 |
| 55 | `woodencrates` | original mesh + upscaled texture | MC2 Shared Source (NC) | 24 | unwrapped | 512 | 357 (22) | n/a | 16.5 |
| 56 | `ammodump` | SolidCraft CAD + baked original texture | MC2 Shared Source (NC) | 578 | unwrapped | 2048 | 98 (16) | n/a | 16.4 |
| 57 | `rock_gformation2` | original mesh + upscaled texture | MC2 Shared Source (NC) | 52 | unwrapped | 512 | 15 (5) | n/a | 16.4 |
| 58 | `slayerp` | original mesh + upscaled texture; **sculpt _hd.glb shadowed** | ["ASF Koroshiya" by Siberian_troll](https://www.thingiverse.com/thing:5478516), CC BY-NC-SA 4.0 | 134 | unwrapped | 512 | 14 (6) | yes | 16.4 |
| 59 | `liquidstorage` | SolidCraft CAD + baked original texture | MC2 Shared Source (NC) | 1234 | unwrapped | 2048 | 62 (17) | n/a | 16.1 |
| 60 | `relaystation` | SolidCraft CAD + baked original texture | MC2 Shared Source (NC) | 2402 | unwrapped | 2048 | 68 (19) | n/a | 16.1 |
<!-- audit:end -->
