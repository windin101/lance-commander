# partisan.glb (v3) — licence and attribution

The 3D mesh of this HD rework model (`partisan.glb`) and its textures (`partisan_albedo.png`, `partisan_orm.png`,
`partisan_normal.png`, `partisan_ids.png`, `partisan_camo.png`) are an adaptation of:

> **"Partisan Heavy Tank"** by **RGriffin65**, https://www.thingiverse.com/thing:6943425
> licensed under **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**,
> https://creativecommons.org/licenses/by-sa/4.0/

## Changes made

Made by `tools/art/v3/v3_mech.py` with the settings in `tools/art/v3/partisan.json` (Pipeline A, 2026-10-24): the printed
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

Vehicle rework (LANCE-19, 2026-10-30), differs from the mech text above: no joints or actuators. The fit is level and raised 165 mm so the belts rest on the ground (`no_icp` in partisan_veh.json; the v1 ICP pitched the kit). The kit's fused hull was split by `tools/art/v3/veh_prep.py` (partisan_prep.json) into the hull, the turret (`Partisan Turret`, turns about the vertical axis; its pivot moved to the centre of the kit's turret ring), the four barrels (`gun`, a node the original model lacks: the weapon nodes were re-parented under it; the barrels elevate about the turret's trunnion line) and two track belts (`track_l`, `track_r`: the faces within 110 mm of the closed belt path round the wheels). The seven wheels a side (`wheel_l0`..`wheel_r6`) are OWN GEOMETRY (`make_wheel`: tyre drum, recessed rim, hub boss, bolts) on axles fitted to the kit's half discs, which were cut from the hull. This own geometry is part of the CC BY-SA 4.0 derivative. 3,404 needle triangles left by the kit's simplification were dropped. Welded at 3 mm and planar-dissolved at 8 degrees, no collapse; belts on a tread strip of two link pitches (0.485 m) by `veh_lowpoly.py`.
