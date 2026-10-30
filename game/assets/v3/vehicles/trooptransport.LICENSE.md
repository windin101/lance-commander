# trooptransport.glb (v3) — licence and attribution

The 3D mesh of this HD rework model (`trooptransport.glb`) and its textures (`trooptransport_albedo.png`, `trooptransport_orm.png`,
`trooptransport_normal.png`, `trooptransport_ids.png`, `trooptransport_camo.png`) are an adaptation of:

> **"Packrat, APCs and Heavy APCs for use with Battletech"** by **Pfelpensson**, https://www.thingiverse.com/thing:4592096
> licensed under **Creative Commons Attribution 4.0 International (CC BY 4.0)**,
> https://creativecommons.org/licenses/by/4.0/

## Changes made

Made by `tools/art/v3/v3_mech.py` with the settings in `tools/art/v3/trooptransport.json` (Pipeline A, 2026-10-24): the printed
sculpt was scaled to game size; split into rigid parts on the kit's own part lines (crease-bounded panels);
re-posed part by part from the sculpt's pose into the MechCommander 2 rest pose; modelled joint actuators (drums and
balls) and flat decks added where parts meet; reduced to game density; given a new UV atlas; baked (normal, ambient
occlusion, edges) from the full-detail sculpt in Blender Cycles; and painted with a hand-authored zone mask and baked
wear (chips, grime, dust, soot). The textures are original work made from those bakes.

## Licence of this adaptation

This adaptation (mesh and textures) is licensed under **CC BY 4.0** (https://creativecommons.org/licenses/by/4.0/),
the licence of the original. The skeleton, joint names and animations in the same `.glb` are converted from
Microsoft's 2006 MechCommander 2 Shared Source release and remain under that release's licence
(`docs/MC2-SOURCE-EULA.md`); they are not covered by the Creative Commons licence.

This is an unofficial fan project. Pfelpensson has not endorsed it or this use of their model. The model is provided
as is, without warranties of any kind.

## Notes on the source

Vehicle rework (LANCE-19 batch 6, 2026-10-31), differs from the mech text above: no joints or actuators. The fit is level (`no_icp` in trooptransport_veh.json). Parts split by `tools/art/v3/veh_prep.py` (trooptransport_prep.json). Welded at 3 mm and planar-dissolved at 1.5 degrees, collapse only above 80k faces a part (no Blender collapse on shell soup). Own-geometry wheels (`make_wheel`: tyre drum, recessed rim, hub boss, bolts) where there are wheels; they are part of the derivative. TRACKED: the kit (Pfelpensson's Heavy Track APC, CC BY 4.0) is a solid hull on a flat track skirt, so the belts `track_l`/`track_r` are the lower side slab (faces within 130 mm of the closed belt path; strip 2 x 220 mm) and the six wheels a side are own geometry on its outer face. No turret (the original has none).
