# Terrain and world rendering

How the remake draws the ground, water, sky and atmosphere, and why. Step 1 of the 2026-10-20 world-art
plan: draw the original data the way MechCommander 2 drew it, before adding any new art.

## What the original data is

All of it is in the Shared Source release; nothing larger exists there (checked 2026-10-20, retail ISO too).

| Asset | Size | Notes |
|---|---|---|
| Colour map `<mission>.burnin.jpg` | 1280 or 1536 px for a 2.56 km map (2 m/px) | the editor baked the sun's shading and cast shadows into it ("burn-in", `terrtxm2.cpp` `burnInShadows`) |
| Detail `<mission>.detail.tga` | 128 px RGBA | dark grey, blended with its own alpha (about 10-20 %), tiled `DetailTextureTilingFactor` |
| Water `<mission>.water.tga` | 128 px | tiled `WaterTextureTilingFactor`, plus 16 sparkle frames `water0000..0015` (64 px) |
| Road, runway, cement tiles | 64 px | a small overlay layer over the colour map (not drawn yet) |
| Sky | 21 skies, 2 x 256 px textures each | `[TheSky] SkyNumber` |
| Terrain mesh | one vertex per 25.6 m | no LOD |

## How the remake draws it now

- **Ground** (`game/shaders/terrain.gdshader`): the colour map as painted, unlit, as the original drew it
  (`quad.cpp:1439-1441`). Lighting it again (as before) darkened and muddied it: mission 14 came out a flat
  red slab. The sun only adds the dynamic shadows of what stands on the ground; the ground casts none (its
  hills are shaded in the map). Steep slopes keep the painted rock and gain a light triplanar grain.
- **Sun**: the original's formula (`Camera.cpp:1505-1509`): toward the light =
  `(cos(yaw+45), sin(yaw+45), sin(pitch))` in MC2's x east / y north / z up, so dynamic shadows fall the way
  the painted ones do. The old rotation put mission 1's sun south-west instead of north-east.
- **Tone curve**: linear (the original had none). Map objects are matte (no specular), as the original lit
  them; ambient energy 1.75 stands in for the original's per-object ambient taken from the ground's light.
- **Textures**: mipmaps on for every map texture (they were off: distant ground shimmered).
- **Sky**: a panorama per SkyNumber, built from the original's skybox textures by `tools/art/env_textures.py`.
- **Fog**: the mission's `FogColor`; depth haze that follows the zoom (the original's 600-800 m haze); the
  mission's height fog where `FogStart`/`FogFull` are set.
- **Water**: the mission's own AlphaShallow/Middle/Deep at 1 and 3 x AlphaDepth, the water texture's colour,
  and the 16-frame sparkle at 8 fps. Shallows are lifted a little so the bed reads.

- **Roads, runways, bridges, cement** (`terrain_view.gd` `_overlay_layer`): the original's overlay layer. The
  map stores one overlay per terrain quad as a runtime slot (from 255, in textures.fit's [OverlayTypeN] order;
  the rough set 285-292 is skipped as the original did); `tools/art/env_textures.py` packs the 461 overlay
  tiles and the three cement tiles into `assets/terrain/overlays.png` with `overlays.json` mapping slots to
  cells. Cement types 10/13/18, 14/15/19 and 16/17/20 use cement 1, 2 and 3, faded in from the cement vertices.
- **Weather** (`weather_view.gd`): rain streaks around the camera, a dimmer sun and ambient while it rains, and
  double lightning flashes at the mission's `BaseLighteningChance` (mc2_10 rains; mc2_19 has lightning only).

## Step 2: ground detail and the world edge

- **Ground detail** (`tools/art/ground_detail.py`, `terrain.gdshader`): five CC0 materials from ambientCG
  (grass Grass004, dirt Ground037, rock Rock058, sand Ground054, snow Snow006) reduced to grain (luminance
  high-passed, 128 = no change) and normal maps, in two texture arrays. The map data has no usable ground
  types (almost every vertex is "undefined"), so the shader picks the class from the colour map's own colour
  (hue, saturation, brightness about 16 m around) plus slope for rock. Only grain and sun-side relief are added;
  the colour stays the colour map's, so every map keeps its look. Off on cement and road tiles.
  Tile sizes are 16-34 m: at the RTS camera (90-450 m away) grain of real-world grass scale is smaller than a
  pixel and mips it away to grey, so the detail is metre-scale structure, not blades. It fades out from 150 m
  to 700 m from the camera.
- **Edge skirt**: a ring of ground runs 3 km out from the map border, sharing the terrain material (the colour
  map's edge pixels stretch outward) and sinking below the water line, and the sea runs out with it where the
  border is under water. Scenery only: the sim and camera stay inside the map.
- **Not done: tessellation.** The sim's height lookup is bilinear on the 25.6 m grid and mechs stand on it; a
  smoother or displaced visual surface would float or bury units. Worth doing only with the sim sharing the
  same surface.

## Step 3: trees

- `tools/art/trees.py` builds an HD tree for each of the 36 original tree types: a tapered bark trunk, branches
  and a crown of leaf-cluster cards (conifer tiers with an inner fill layer, broadleaf ellipsoid crowns, willow
  curtains, palm fronds, bare dead trees, and the tc1 clumps as stands of 5-7 trees). Each keeps its original's
  height, width and leaf colour (tinted from the original texture), so maps keep their palettes. 90-900 tris.
- Foliage comes from CC0 Poly Haven textures (fir sprigs, jacaranda fronds, pine bark) composited into a 2 x 2
  atlas of 512 px cells. `leaves.gdshader`: alpha cut-out (raised with distance so mips do not thin crowns),
  crown normals (volume lighting, no back-face flip), height-scaled wind phased by position.
- `objects_view.gd` draws every tree of a type as one MultiMesh for bark and one for leaves (about 24,000 trees
  across the maps, tens of draw calls per map instead of thousands of scenes). Destroying a tree drops its
  leaves and breaks the trunk to a stump. `--no-hd` shows the original cards.
- Not done: mesh LODs (the cards are cheap and auto-decimation mangles them).

## Step 4: ground marks, and HD object textures

- `decals_view.gd` + `tools/art/decals.py`: each mech's own footprint shape (from the original's 16 px cells,
  redrawn at 128 px as a pressed print) at every footfall, fading after 90 s (360 max); craters where shots miss
  and air strikes land, scorch under every wreck (160 max); a ring on the water where a mech wades. Decals
  project onto render layer 2, which only the terrain and skirt are on.
- Buildings, props and walls: the converter now reads multi/sub-object materials (I62: 140 models were white).
  `tools/art/upscale_textures.py` 4x upscales every object's texture and the road/runway atlas with
  RealESRGAN x4plus (BSD-3) into `<app>_hdtex.glb` / `overlays_hd.webp`; `tools/art/glb_webp.py` stores them as
  JPEG (opaque) or WebP with alpha (cut-outs), 43 MB for 457 models. `--no-hd` shows the originals.

## Not yet

Mine decals (the remake does not draw mines). Then step 2 (more
ground resolution: terrain-type materials blended under the colour map, tessellation, an edge skirt) and
step 3 (new vegetation with LODs, shadows, wind and instancing).

## Terrain polish pilot (2026-11-01)

Water, shore, ground transitions and vegetation for the v3 terrain; provenance in `docs/art-provenance.md`.

- **Water** (`shaders/water_v3.gdshader`): the ground under each pixel is rebuilt from the depth buffer, so vertical and ray depth, the shoreline and the contact with anything wading are exact, whatever the 25.6 m mesh does. Beer-Lambert absorption of the lit scene behind it (the bed shows through the shallows), a scattered shallow-to-deep colour from the mission's own water tint, three world-space normal layers that flatten with distance, sun glints and sky reflection from the PBR pipeline (low roughness, Fresnel), and depth-driven foam (a lacy contact line plus slow waves running up the beach, rings round wading units). The old plane: `--old-water`.
- **Shore, ground side** (`terrain_v3.gdshader`, `water_y`): a beach of the palette's dust/scree layers, a darker smoother wet band, a sandy bed. Fades on steep ground.
- **Transitions**: B-spline class weights, tempered height blend, warm (not grey) wear/dusty/worn shifts from blurred noise, luminance-only macro variation. The "scabs" were three things: sharp thresholds on the noise's fine octaves, grey-shifted patches on green, and a per-channel macro ratio that turned a layer's dirt flecks cool violet.
- **Vegetation** (`terrain_dress_v3.gd`, `grass.gdshader`): blade-clump cover to 320 m, shrubs, filler trees thickening the forests (scenery only), a rebuilt palm crown.
- **Flags**: `--old-water`, `--no-shore`, `--splat-bilinear`, `--no-vegetation`, `--no-fillers`, `--no-terrain-dress`.
- Known limit: the shoreline follows the 25.6 m mesh's facets (the sim walks on that grid, so a finer visual surface would float or bury units); foam softens it but a narrow channel still reads angular.

## Terrain polish round 3: dead trees, shoreline, understorey (2026-11-01)

Piloted on mc2_01, mc2_11 and mc2_16; provenance in `docs/art-provenance.md`.

- **Dead trees** (`tools/art/trees_dead.py`): all 13 dead or leafless types are grown (flared gnarled trunk, limbs, branches, twig sprays), three variants per type, per-instance lean and stretch, weathered silver bark. The old ones were seven straight sticks that read as black lines at RTS range. The twig material raises alpha with the mip level much harder than live foliage (`lod_boost`), or the lace thins out and the trees vanish at 300 m.
- **Shoreline: render-only refinement, not a shader distance field.** A shader-side field cannot work: the water plane is hidden wherever a facet of the opaque 25.6 m mesh pokes above the waterline, so the angular edge comes from the terrain mesh itself. `TerrainView._refine_shore` replaces the quads within 1.8 m of the water level by 8 x 8 sub-quads (3.2 m) of a Catmull-Rom bicubic. Catmull-Rom interpolates the grid vertices, so the surface agrees with the sim exactly at every vertex, and a weight that fades to 0 at 1.8 m from the waterline makes the seam to the untouched mesh the same straight line (no cracks). The deviation from the sim's bilinear surface is soft-limited to 0.7 m, which is also the most a unit can float or sink in the band. Normals come from the analytic bicubic gradient, blended into the main mesh's smooth vertex normals where the weight goes to 0. `SimMap.height_at` is untouched. Measured: mc2_01 846 quads, 108k triangles, 240 ms to build; mc2_11 1,215 quads, 156k triangles, 340 ms. Off: `--no-shore-mesh`.
- **Shore dressing**: reed clumps, pebbles and a few rocks on the waterline (`terrain_plants_v3.gd` `_shore`), per-palette weights.
- **Understorey** (`terrain_plants_v3.gd`, `shaders/plants.gdshader`, `tools/art/terrain/plants_atlas.py`): bushes, ferns, wildflowers, dry scrub, hedgerows. Placement is by habitat noise and thickets with bare gaps between, never an even speckle; hedges are chains of elongated bushes laid along the paved edge (4.5-6.5 m outside the apron SDF) and along smoothed meadow/ground boundaries, gated by noise into stretches with gaps; everything keeps off paving, roads, snow, rock and scree, footprints of non-tree objects and tree trunks. Per palette: temperate gets all of it, moorland dark shrubs and ferns, stony and arid dry scrub, snow a few dark shrubs, industrial a little scrub, lunar nothing.
- Flags: `--no-plants`, `--no-hedges`, `--no-shore-dress`, `--no-shore-mesh`.
- Known gaps: hedges do not follow the overlay roads (only paved edges and class boundaries); the shore mesh is 25.6 m quads refined to 3.2 m, so a channel narrower than about 6 m still reads as a short run of segments.

## Terrain polish rollout, batch 1: mc2_02 to mc2_07 (2026-11-02)

Checked each map before (HEAD~2, the pre-polish look) and after at the RTS default, the wide view and one close feature shot. Two shared fixes and one per-map data key came out of it.

- **Night and airless fill for the dressing** (`shaders/grass.gdshader`, `plants.gdshader`, `leaves.gdshader`, the new `scatter_v3.gdshader`). On a night map the ground is lit almost only by its own `EMISSION = albedo * shadow_fill` floor (`terrain_v3.gdshader`); bushes, ferns, tufts, shrubs, rocks and pebbles had no such floor and came out pure black (mc2_05: black blobs the size of a bush, black specks everywhere, black shore rocks). Each now has a `fill` uniform set from the ground material's `shadow_fill` (`TerrainDressV3.ground_fill()`, so a map's own `shadow_fill` in palettes.json drives both), and emits `(albedo + tint * 0.6) * fill`. Rocks, pebbles and debris moved from a `StandardMaterial3D` to `scatter_v3.gdshader` (vertex colour albedo plus the floor). Day maps change by well under one level (pilots 01, 11, 16 re-shot against HEAD: mean abs difference 0.28-0.44 of 255). The dress's shrubs use their own duplicate of the tree leaf material so live trees are untouched.
- **Per-map `layer_albedo_scale`** (palettes.json `maps.<m>.layer_albedo_scale`, written to `terrain_v3.json` by `terrain_pack.py`, applied in `TerrainView._v3_material` by palette slot name, multiplied into the shader's `albedo_scale[]`). The pale gravel and dust patches on olive grass (mc2_04, mc2_07) read as grey scabs; scaling the scree and dust layers (0.7 and 0.65) brings their value down to the grass's so they read as ground variation. A first round at dust 0.8 changed almost nothing; the value difference has to nearly close. `test/terrain_rollout_test.gd` checks that the json matches palettes.json, that keys are slot names and that the factors stay in 0.4-1.2.
- **Looked at and left alone**: the warm shift (`warm_k`) adds about +4 to +6 b* on the temperate maps; halving it per map changed almost nothing, so the yellow comes from the palette and the approved grass, not the shift. The offshore shelf on mc2_07 has a hard straight lip because the bed has one (a 25.6 m facet step in the heights); averaging the scattered-colour depth over 14 m only softened it a little and was dropped.
- Perf (`--perf=8`, 300 m RTS view, wall/GPU mean ms): mc2_07 2.93/2.47 before, 3.90/3.46 after; mc2_03 2.23/1.88 before, 2.70/2.39 after.

## Terrain polish rollout, batch 2: mc2_08, 09, 10, 12, 13, 14 (2026-11-02)

Same method as batch 1 (before = the commit under 73e173ea). Four faults, one shared fix and four per-map data keys.

- **Shore band only beside water** (shared, `TerrainView.shore_near_texture`, `terrain_v3.gdshader` `shore_near`). The beach and wet band applied to every flat patch within 4 m above the water level, however far from any water. On mc2_09 (desert basin, water at 10 m) dry craters at that height rendered as glowing pale ovals with stippled rims. A per-vertex distance transform to the nearest vertex under the water level becomes an R8 texture (1 within 30 m, 0 beyond 90 m) that multiplies the beach and wet weights. Real shores are unchanged (checked on 01, 02, 04, 06, 07, 11, 16 against `--shore-anywhere`, which restores the old behaviour).
- **Per-map water keys** (palettes.json `maps.<m>`, copied to `terrain_v3.json` by `terrain_pack.py`, read in `TerrainView._water_v3_params`): `water_absorb_k` scales the absorption (a brown bed under a shallow shelf, mc2_08, showed as mud; 7 lets the water's own teal show), `water_reflect` scales the sky reflection and `water_glow` adds the scattered colour as light (mc2_14's sunset sky painted the sea orange; 0.5 and 0.8 give a dark teal sea with a trace of warm sky). Defaults (1, 1, 0) leave every other map as it was.
- **Per-map `cover_gain`** (`terrain_dress_v3.gd`): the dressing's value follows the ground's `albedo_gain` with a 0.3 floor; mc2_12's ground is 0.13, so grass and flowers read as pale confetti. `cover_gain` 0.1 overrides the floor for that map.
- **Checked and fine**: mc2_13 (lunar) has no vegetation and `warm_k` 0 (mean b* about 0); mc2_14's paving and its lane and edge markings are intact; mc2_10's rain, pine fillers and dead trees read well.
- Tried and dropped: per-map `tint_strength` and `dusty_strength` did nothing to the mc2_09 ovals (the shore band was the cause); a lifted and greyed underwater bed turned mc2_08 milky grey instead of teal.

## Terrain polish rollout, batch 3: mc2_15, 17, 18, 19, 20, 21, 22, 23, 24 (2026-11-02)

Same method as batches 1 and 2 (before = the commit under 73e173ea), shot at the RTS default, the wide view and one close feature (a shore on 17, 19 and 24). One fault, one shared knob and five per-map data keys. The water is a separate pass (below).

- **Pale mint bush discs on dark ground** (mc2_15, 17, 18, 21, 23; also the grass tufts on 21 and 23). The night/airless floor added in batch 1 emits `(albedo + tint * 0.6) * fill`. The ground's own floor is `albedo * fill` with the albedo scaled by `albedo_gain` (0.095-0.3 on these maps), but the dressing's colour is floored at 0.3 gain, so the tint term made bushes flat pale-green discs on dark brown ground. New per-map `plant_fill_tint` (palettes.json `maps.<m>`, copied by `terrain_pack.py`, read in `TerrainDressV3.plant_fill_tint`, uniform `fill_tint` in `plants.gdshader` and `grass.gdshader`, default 0.6 = batch 1 behaviour, limits 0-0.6): 0 on the five maps above leaves the floor at `albedo * fill`, and the bushes and tufts come out dark green like the ground. Setting it to 0 everywhere is wrong: mc2_05 (night, fill small) goes back to pure black bushes, which is why it is a key and not a shared change. Tried first and dropped: `cover_gain` 0.1-0.2 on the same maps (changes the dressing's day value too and still left pale discs).
- **Regression**: with the key absent the output is unchanged. Re-shot against HEAD at 300 m: mc2_01, 11, 16 mean abs difference 0.07-0.11 of 255 (same noise level as batch 1's check), mc2_12 0.7, mc2_05 and mc2_10 differ only by drifting cloud shadow and rain.
- **Checked and fine**: no scree/dust scabs (mc2_22's grey scabs are gone, the ground is now olive and even), no vegetation on the mc2_18 city paving, apron or roads, no snow vegetation, mc2_20's and mc2_24's tree crowns are normal, mc2_24 road and shore dress clean, mc2_19's dusk snow edge has no halo.
- **Not fixed here (water pass)**: mc2_17 and mc2_19 water is a dark murky olive/teal, mc2_24 is dark navy, and mc2_17's foam is a wide lacy white mat over the shallow slope.
- Perf (`--perf=8`, 300 m RTS view, wall/GPU mean ms): mc2_24 3.08/1.44 before, 3.13/1.54 after; mc2_19 3.28/1.46 before, 3.28/1.71 after.

## Water pass (2026-11-02)

Six maps had a sea that was not teal (08 flat murky green, 14 brown-olive deep, 17 olive-brown with a foam mat, 19 near black, 24 dark navy, 07 a lip on the shelf). The water colour is no longer derived from the map's water.tga mean for those maps: each gets explicit colours as data. Maps without the new keys are untouched (shader defaults reproduce the old path; regression shots differ only by foam/grass animation, which is `TIME`-driven).

- **New keys** (palettes.json `maps.<m>`, copied by hand into `terrain_v3.json`, read in `TerrainView._water_v3_params`; limits and the palettes/json match are in `terrain_rollout_test.gd`):
  - `water_shallow_col`, `water_deep_col`: hex sRGB; both set switches the shader to art mode (`art`), where the scattered colour is also added as emission (`water_emit`, default 0.35) so a night, dusk or sunset light cannot turn it brown or black.
  - `water_deep_m`: depth at which the colour is 63 % deep. A lake that is shallow over its whole bay (17) needs 2.5, an open sea 7-12.
  - `water_foam` (strength, default 1) and `water_foam_m`: the foam band is at most this many metres wide **on the ground**. The shader reads the bed slope from screen derivatives of the rebuilt bed and stretches the depth axis of the foam by it (`sc = slope * foam_max_m`, capped at 1), so a steep shore is exactly the pilot's foam and a gentle shelf gets a thin line. Before, the depth-wander noise (+-1 m) turned into 20 m of foam on a 5 % slope.
  - `water_depth_soft_m`: the depth that drives the colour is averaged over a 12-tap ring of that many metres, and the bed seen through water deeper than ~2 m is read from a blurred mip. The 25.6 m facet steps of the bed no longer print as colour blocks. It softens the lip on 07 but does not remove it: the shelf drop is real geometry.
  - Existing `water_reflect` / `water_glow` / `water_absorb_k` unchanged; art maps use `water_reflect` 0.25-0.5 and `water_absorb_k` 2-6 (murkier water lets the artist's colour take over from a dark bed sooner).
- **Values**: 08 `#38b8b4`/`#07455f`; 14 `#38bcb6`/`#08405c` with reflect 0.25, glow 0.5; 17 `#4cc9c6`/`#0b4a62`; 19 `#2a9aa2`/`#0c4a62` (emit 0.6, foam 0.8); 24 `#35b4b6`/`#0a3f5c`; 07 only `water_depth_soft_m` 40.
- **Sky reflection** is only scaled (`water_reflect`), not tinted; mc2_14's brown deep sea was the scatter colour from water.tga plus the sunset reflection, and explicit navy with reflect 0.25 removes it.
- **Review method trap**: `--cam-view` with a focus left the camera following the lance and edge-scroll on, so a mouse resting at the window edge changed the framing between runs. `force_mission.gd` now clears `following` and `edge_scroll` for a focused view; before/after pairs are only comparable with that fix.
- **Second round, one water family (Lee, 2026-11-02)**: mc2_03, 11, 12, 15 and 20 read slate grey and joined the teal set. All of them (and 08, 14, 17, 24) now share one family: shallow `#38b8b4`-`#3fb8b4`, deep `#08425e`-`#08405c`, `water_emit` 0.22-0.45, `water_foam_m` 3-4, reflect 0.12-0.3. Per-map lighting still decides how bright it lands (03 at night stays dark navy, 12 and 11 are lighter). 17 and 24 were pulled down toward 08/14 (17 lost its minty shallow, `water_reflect` 0.12; 24 deep colour `#08425e`).
- **mc2_17 stays flat**: lowering `water_reflect` to 0.12 and `water_deep_m` to 3 gave no extra variation; the bay is a shelf of 3-5 m over most of the view, so the colour has saturated everywhere except a thin rim at the shore.
- **mc2_15's stepped edge** is the depth where the bay's bed passes from shallow to 5 m deep, in 25.6 m facet teeth (25.6 m grid, about 50 m wide on screen). `water_depth_soft_m` 14 and 40 and a longer `water_deep_m` (10) did not remove it. It needs a render-only smoothing of the underwater heights in the terrain mesh (extend `_refine_shore`'s bicubic band down to ~6 m below the water level), not a shader change.
- **mc2_14's pale streaks fanning from the beach** were the bed showing through the shallows (the burnt-in shadow streaks of the colour map lit by the sunset), not foam or reflection; `water_absorb_k` 2 -> 4 fades them (one key).

### Water pass round 3 (2026-11-02): smooth seabed, teal on 05, 16, 18, 22, 23

- **Seabed smoothing** (render only, `TerrainView._refine_shore`, off with `--no-sea-smooth`): the shore's Catmull-Rom bicubic carries on below the waterline, so the 25.6 m facets of a shelf (the sawtooth depth contours on mc2_15) become a smooth bed. The weight is 1 from the shore band down to `SEA_FULL_M` (6 m) below the water and fades to 0 over `SEA_FADE_M` (3 m), so a quad deeper than 9 m is untouched and the seam is closed. The departure from the sim's surface may grow from 0.7 m at the shore to `SEA_MAX_DEV` (2.5 m) only as the bed gets deeper, and is always below 0.85 of the depth: nothing under water comes out of it, and the above-water ground, the shore band, `SimMap.height_at`, pathing and objects are untouched (`test_sea_bed_smoothing_stays_below_the_water_level_and_closes_its_seam`). The analytic slope for the normals includes the changing limit.
- **Traps found**: (1) a coarser 4 x 4 grid for deep quads left black cracks at the seam with the 8 x 8 shore quads (a slit shows the void under the ground), so every refined quad is 8 x 8; (2) leaving flat deep quads on the sim's own triangles (to save 128 triangles each) kept the sawtooth, because the sim mesh's hard-edged normals light the bed, and a 6 cm edge mismatch cut hairline slits; so nothing is skipped and the cost is load time (about 0.2-1.3 s on lake maps: mc2_20 4.5k quads, 365k vertices).
- **mc2_20's dark block** is a real cliff in the bed (a 25.6 m wide step); smoothing rounds its corners and `water_deep_m` 14 widens the colour ramp.
- **Teal on 05, 16, 18, 22, 23**: the same family (`#38b8b4` / `#08425e`, deep_m 7, absorb 3, foam_m 4, soft 14), emit 0.3, reflect 0.3 (18: 0.1, which removes the white sky streak on its 612 m view; the sun glint in its close shot stays).
