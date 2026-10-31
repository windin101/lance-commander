# infantry.glb (v3) — licence and attribution

The 3D mesh of this HD rework model (`infantry.glb`) and its textures (`infantry_albedo.png`, `infantry_orm.png`,
`infantry_normal.png`, `infantry_ids.png`, `infantry_camo.png`) are an adaptation of:

> **"Future - Generic Space Infantry Troops"** by **Guy_montag**, https://www.printables.com/model/114328
> licensed under **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)**,
> https://creativecommons.org/licenses/by-nc-sa/4.0/

## Changes made

Made by `tools/art/v3/v3_mech.py` with the settings in `tools/art/v3/infantry.json` (Pipeline A, 2026-10-24): the printed
sculpt was scaled to game size; split into rigid parts on the kit's own part lines (crease-bounded panels);
re-posed part by part from the sculpt's pose into the MechCommander 2 rest pose; modelled joint actuators (drums and
balls) and flat decks added where parts meet; reduced to game density; given a new UV atlas; baked (normal, ambient
occlusion, edges) from the full-detail sculpt in Blender Cycles; and painted with a hand-authored zone mask and baked
wear (chips, grime, dust, soot). The textures are original work made from those bakes.

## Licence of this adaptation

This adaptation (mesh and textures) is licensed under **CC BY-NC-SA 4.0** (https://creativecommons.org/licenses/by-nc-sa/4.0/),
the licence of the original. The skeleton, joint names and animations in the same `.glb` are converted from
Microsoft's 2006 MechCommander 2 Shared Source release and remain under that release's licence
(`docs/MC2-SOURCE-EULA.md`); they are not covered by the Creative Commons licence.

This is an unofficial fan project. Guy_montag has not endorsed it or this use of their model. The model is provided
as is, without warranties of any kind.

## Notes on the source

Infantry rework (LANCE-19, 2026-10-31): a SimVehicle with a skinned-style skeleton (joint_* with Walk and Run). The approved v1 fit (`infantry_veh.json`: scale 1.85, yaw 275, base cut, nudge, parts_box with the legs split along the stride axis) was captured by `v3_rigid.py` and run through the mech path as a rigid unit: one rigid part per original node (Inf_Body, Inf_Lleg/Rleg, Inf_Lfoot/Rfoot, joint_Head, joint_Arms), no actuators. The limbs are plain rigid parts, so hips and shoulders open slightly in the walk. Team colour (style guide §9, Lee 2026-10-31): only the helmet, the shoulder pads (Inf_Body above z 1380 mm) and a chest band (z 1170-1260 mm) take team colour; everything else is a fixed dark armour grey (`fixed_colour` with `except`).
