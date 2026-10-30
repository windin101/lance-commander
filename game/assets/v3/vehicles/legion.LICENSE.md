# legion.glb (v3) — licence and attribution

The 3D mesh of this HD rework model (`legion.glb`) and its textures (`legion_albedo.png`, `legion_orm.png`,
`legion_normal.png`, `legion_ids.png`, `legion_camo.png`) are an adaptation of:

> **"Legion MBT"** by **RGriffin65**, https://www.thingiverse.com/thing:6617086
> licensed under **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**,
> https://creativecommons.org/licenses/by-sa/4.0/

## Changes made

Made by `tools/art/v3/v3_mech.py` with the settings in `tools/art/v3/legion.json` (Pipeline A, 2026-10-24): the printed
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

Vehicle rework (LANCE-19 batch 2, 2026-10-30), differs from the mech text above: no joints or actuators. TRACKED. The kit's hull was split by `tools/art/v3/veh_prep.py` (legion_prep.json) into the hull, the turret (`Legion_turret`, turns about its dome centre), the two big barrels with their small flanking ones (`gun`, a node the original lacks: weapon_01 re-parented under it; the original's weapon_02..04 are side pods on the turret and stay on it) and two track belts (the faces within 140 mm of the closed belt path round the wheels). The 7 wheels a side (`wheel_l0`..`wheel_r6`: 6 road wheels and the rear sprocket) are OWN GEOMETRY (`make_wheel`) on axles fitted to the skirt cut-outs; the kit's wheel faces were cut from the hull. Belts on a tread strip of two link pitches (0.44 m). welded at 3 mm and planar-dissolved at 8 degrees, no collapse.
