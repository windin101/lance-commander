# drillson.glb (v3) — licence and attribution

The 3D mesh of this HD rework model (`drillson.glb`) and its textures (`drillson_albedo.png`, `drillson_orm.png`,
`drillson_normal.png`, `drillson_ids.png`, `drillson_camo.png`) are an adaptation of:

> **"Drillson Support Hover"** by **RGriffin65**, https://www.thingiverse.com/thing:6743061
> licensed under **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**,
> https://creativecommons.org/licenses/by-sa/4.0/

## Changes made

Made by `tools/art/v3/v3_mech.py` with the settings in `tools/art/v3/drillson.json` (Pipeline A, 2026-10-24): the printed
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

Vehicle rework (LANCE-19 batch 2, 2026-10-30), differs from the mech text above: no joints or actuators. HOVER craft: no wheels or tracks. The fit is level and square (`no_icp`, yaw 90 in drillson_veh.json; the v1 fit's yaw 85 left it skewed). The kit's fused hull was split by `tools/art/v3/veh_prep.py` (drillson_prep.json) into the hull and the launcher turret (`TF_Turret`, turns about the vertical axis through its centre; the original's TF_Missilepods node has no part of its own, the kit has one launcher box). Needle triangles dropped; welded at 3 mm and planar-dissolved at 8 degrees, no collapse. The data gives the Drillson max_turret_yaw 0, so the turret only turns if the sim asks.
