# aerospotter.glb (v3) — licence and attribution

The 3D mesh of this HD rework model (`aerospotter.glb`) and its textures (`aerospotter_albedo.png`, `aerospotter_orm.png`,
`aerospotter_normal.png`, `aerospotter_ids.png`, `aerospotter_camo.png`) are an adaptation of:

> **"C3 mobile Radar command unit"** by **RGriffin65**, https://www.thingiverse.com/thing:6874543
> licensed under **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**,
> https://creativecommons.org/licenses/by-sa/4.0/

## Changes made

Made by `tools/art/v3/v3_mech.py` with the settings in `tools/art/v3/aerospotter.json` (Pipeline A, 2026-10-24): the printed
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

Vehicle rework (LANCE-19 batch 3, 2026-10-31), differs from the mech text above: no joints or actuators. The fit is level (`no_icp` in aerospotter_veh.json). The kit's fused hull was split by `tools/art/v3/veh_prep.py` (aerospotter_prep.json). The wheels (`wheel_l0`..) are OWN GEOMETRY (`make_wheel`: tyre drum, recessed rim, hub boss, bolts) on axles fitted to the kit's wheels, which were cut from the hull; this own geometry is part of the CC BY-SA 4.0 derivative. Welded at 3 mm and planar-dissolved at 3 degrees, collapse only above 80k faces a part (no collapse on the shell-soup Hunter route; these hulls are clean). WHEELED, 5 axles: MC2's aerospotter is a TRACKED radar vehicle, the approved v1 source is RGriffin65's wheeled C3 Mobile Radar Command Unit and is kept (Lee to judge). The radar turntable, platform and antenna array above z 3100 are the part `radar` on a new node under the hull, pivot on the turntable axis (44, 1835 mm); the sidecar's `spin` turns it at 30 deg/s (written from aerospotter_prep.json). The front axle is under `steer_l0`/`steer_r0`.
