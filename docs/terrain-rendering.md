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
