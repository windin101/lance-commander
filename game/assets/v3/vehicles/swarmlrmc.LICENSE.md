# swarmlrmc.glb (v3) — licence and attribution

The 3D mesh of this HD rework model (`swarmlrmc.glb`) and its textures (`swarmlrmc_albedo.png`, `swarmlrmc_orm.png`,
`swarmlrmc_normal.png`, `swarmlrmc_ids.png`, `swarmlrmc_camo.png`) are an adaptation of:

> **"Semi-Modular Weapons Carrier"** by **RGriffin65**, https://www.thingiverse.com/thing:7123873
> licensed under **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**,
> https://creativecommons.org/licenses/by-sa/4.0/

## Changes made

Made by `tools/art/v3/v3_mech.py` with the settings in `tools/art/v3/swarmlrmc.json` (Pipeline A, 2026-10-24): the printed
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

Vehicle rework (LANCE-19 batch 3, 2026-10-31), differs from the mech text above: no joints or actuators. The fit is level (`no_icp` in swarmlrmc_veh.json). The kit's fused hull was split by `tools/art/v3/veh_prep.py` (swarmlrmc_prep.json). The wheels (`wheel_l0`..) are OWN GEOMETRY (`make_wheel`: tyre drum, recessed rim, hub boss, bolts) on axles fitted to the kit's wheels, which were cut from the hull; this own geometry is part of the CC BY-SA 4.0 derivative. Welded at 3 mm and planar-dissolved at 3 degrees, collapse only above 80k faces a part (no collapse on the shell-soup Hunter route; these hulls are clean). HALF-TRACK kit (v1's `hull.stl` and `launcher.stl`, made from the SRM variant): one front wheel pair (under `steer_l0`/`steer_r0`) and rear belts (`track_l`, `track_r`: the faces within 120 mm of the closed belt path round the five track wheels; tread strip 2 x 205 mm), where MC2's swarm LRM carrier is a 6-wheel truck. Turntable `srmc_turret`, launcher rack `SRM_Pack` as the gun (`gun_pitch` [-25, 20] about its rear hinge, from the kit's raised rest pose); one launcher as in the original.
