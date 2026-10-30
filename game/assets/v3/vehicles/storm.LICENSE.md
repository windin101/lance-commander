# storm.glb (v3) — licence and attribution

The 3D mesh of this HD rework model (`storm.glb`) and its textures (`storm_albedo.png`, `storm_orm.png`,
`storm_normal.png`, `storm_ids.png`, `storm_camo.png`) are an adaptation of:

> **"Storm heavy tank"** by **RGriffin65**, https://www.thingiverse.com/thing:6914336
> licensed under **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**,
> https://creativecommons.org/licenses/by-sa/4.0/

## Changes made

Made by `tools/art/v3/v3_mech.py` with the settings in `tools/art/v3/storm.json` (Pipeline A, 2026-10-24): the printed
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

Vehicle rework (LANCE-19, 2026-10-30), differs from the mech text above: no joints or actuators. The fit is level (`no_icp` in storm_veh.json; the v1 ICP tilted the kit). The kit's fused hull was split by `tools/art/v3/veh_prep.py` (storm_prep.json) into the hull (the kit's tread label merged in), the turret (`TankGTurret`, turns about the vertical axis; re-seated on the hull ring, because the v1 mount had centred its long barrels on the model's turret pivot and floated it 2.7 m aft), the barrels with their housings (`TankGguns`, the gun: elevates about the housing centre) and two track belts (`track_l`, `track_r`: the faces within 100 mm of the closed belt path round the wheels). The seven wheels a side (`wheel_l0`..`wheel_r6`) are OWN GEOMETRY (`make_wheel`: tyre drum, recessed rim, hub boss, bolts) on axles fitted to the kit's wheel circles; the kit's wheel faces were cut from the hull. This own geometry is part of the CC BY-SA 4.0 derivative. 7,701 needle triangles left on the turret by the kit's simplification were dropped. Welded at 3 mm and planar-dissolved at 8 degrees, no collapse; belts on a tread strip of two link pitches (0.425 m) by `veh_lowpoly.py`.
