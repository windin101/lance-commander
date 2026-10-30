# centipede.glb (v3) — licence and attribution

The 3D mesh of this HD rework model (`centipede.glb`) and its textures (`centipede_albedo.png`, `centipede_orm.png`,
`centipede_normal.png`, `centipede_ids.png`, `centipede_camo.png`) are an adaptation of:

> **"Centipede Scout Car (Wheeled)"** by **RGriffin65**, https://www.thingiverse.com/thing:7044273
> licensed under **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**,
> https://creativecommons.org/licenses/by-sa/4.0/

## Changes made

Made by `tools/art/v3/v3_mech.py` with the settings in `tools/art/v3/centipede.json` (Pipeline A, 2026-10-24): the printed
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

Vehicle rework (LANCE-19, 2026-10-30), differs from the mech text above: no joints or actuators. WHEELED kit (8 wheels, four axles). The fit is level (`no_icp` in centipede_veh.json; the v1 ICP tilted it) and lowered 182 mm onto the ground. The kit's fused hull was split by `tools/art/v3/veh_prep.py` (centipede_prep.json) into the hull and the roof turret (`Centipede_turret`: the dome with its antennas, which turns about the vertical axis; the v1 box for it missed once the fit was level). The eight wheels (`wheel_l0`..`wheel_r3`) are OWN GEOMETRY (`make_wheel`: tyre drum, recessed rim, hub boss, bolts) on axles fitted to the kit's wheel domes, which were cut from the hull; the front pair sits under `steer_l0` / `steer_r0` pivot nodes at the wheel centres. This own geometry is part of the CC BY-SA 4.0 derivative. The muzzle node was moved to the nose gun and parented to the hull. Needle triangles left by the kit's simplification were dropped. Welded at 3 mm and planar-dissolved at 8 degrees, no collapse. There is no `gun` part: the kit's only barrels are fixed ball mounts in the nose and tail.
