# minelayer.glb (v3) — licence and attribution

The 3D mesh of this HD rework model (`minelayer.glb`) and its textures (`minelayer_albedo.png`, `minelayer_orm.png`,
`minelayer_normal.png`, `minelayer_ids.png`, `minelayer_camo.png`) are an adaptation of:

> **"Minelayer"** by **RGriffin65**, https://www.thingiverse.com/thing:6916656
> licensed under **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**,
> https://creativecommons.org/licenses/by-sa/4.0/

## Changes made

Made by `tools/art/v3/v3_mech.py` with the settings in `tools/art/v3/minelayer.json` (Pipeline A, 2026-10-24): the printed
sculpt was scaled to game size; split into rigid parts on the kit's own part lines (crease-bounded panels);
re-posed part by part from the sculpt's pose into the MechCommander 2 rest pose; modelled joint actuators (drums and
balls) and flat decks added where parts meet; reduced to game density; given a new UV atlas; baked (normal, ambient
occlusion, edges) from the full-detail sculpt in Blender Cycles; and painted with a hand-authored zone mask and baked
wear (chips, grime, dust, soot). The textures are original work made from those bakes.

## Licence of this adaptation

This adaptation (mesh and textures) is licensed under **CC BY-SA 4.0** (https://creativecommons.org/licenses/by-sa/4.0/),
the licence of the original. The skeleton, joint names and animations in the same `.glb` are converted from
Microsoft's 2006 MechCommander 2 Shared Source release and remain under that release's licence
(`docs/MC2-SOURCE-EULA.md`); they are not covered by the Creative Commons licence.

This is an unofficial fan project. RGriffin65 has not endorsed it or this use of their model. The model is provided
as is, without warranties of any kind.

## Notes on the source

Vehicle rework (LANCE-19 batch 4, 2026-10-31), differs from the mech text above: no joints or actuators. The fit is level (`no_icp` in minelayer_veh.json). Moving parts split by `tools/art/v3/veh_prep.py` (minelayer_prep.json). The wheels (`wheel_*`) are OWN GEOMETRY (`make_wheel`: tyre drum, recessed rim, hub boss, bolts) on axles fitted to the kit's wheels, which were cut from the hull; this own geometry is part of the derivative. Welded at 3 mm and planar-dissolved at 3 degrees, collapse only above the per-part budget (no Blender collapse on shell soup). TRACKED: belts `track_l`/`track_r` (faces within 110 mm of the closed belt path round the seven wheels a side; strip 2 x 185 mm). The kit has a hexagonal tower on the deck and a rear plough arm, both static (the original is a low flat tracked hull with a tower and a plough; the rig has no part for them).
