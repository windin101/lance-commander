# mobilehq.glb (v3) — licence and attribution

The 3D mesh of this HD rework model (`mobilehq.glb`) and its textures (`mobilehq_albedo.png`, `mobilehq_orm.png`,
`mobilehq_normal.png`, `mobilehq_ids.png`, `mobilehq_camo.png`) are an adaptation of:

> **"Praetorian Mobile HQ"** by **RGriffin65**, https://www.thingiverse.com/thing:6599003
> licensed under **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**,
> https://creativecommons.org/licenses/by-sa/4.0/

## Changes made

Made by `tools/art/v3/v3_mech.py` with the settings in `tools/art/v3/mobilehq.json` (Pipeline A, 2026-10-24): the printed
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

Vehicle rework (LANCE-19 batch 2, 2026-10-30), differs from the mech text above: no joints or actuators. WHEELED. The kit's front wheels and module labels were merged into the hull, the front wheel pair and two rear wheels (`wheel_l0`..`wheel_r2`) are OWN GEOMETRY (`make_wheel`) on axles fitted to the kit; the front pair is under `steer_l0`/`steer_r0`. The radar dish and its post (`hq_radar`, on node hq_radar under the stand) is a separate part; it could spin about the vertical axis, but `VehicleRig` has no radar handling yet. Needle triangles dropped; welded at 3 mm and planar-dissolved at 8 degrees, no collapse.
