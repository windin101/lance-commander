# fueltruck.glb (v3) — licence and attribution

The 3D mesh of this HD rework model (`fueltruck.glb`) and its textures (`fueltruck_albedo.png`, `fueltruck_orm.png`,
`fueltruck_normal.png`, `fueltruck_ids.png`, `fueltruck_camo.png`) are an adaptation of:

> **"Fuel Truck"** by **RGriffin65**, https://www.thingiverse.com/thing:7285869
> licensed under **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**,
> https://creativecommons.org/licenses/by-sa/4.0/

## Changes made

Made by `tools/art/v3/v3_mech.py` with the settings in `tools/art/v3/fueltruck.json` (Pipeline A, 2026-10-24): the printed
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

Vehicle rework (LANCE-19 batch 2, 2026-10-30), differs from the mech text above: no joints or actuators. WHEELED: the kit has 3 axles (6 wheels), MC2's fuel truck 4. The 6 wheels (`wheel_l0`..`wheel_r2`) are OWN GEOMETRY (`make_wheel`: tyre drum, recessed rim, hub boss, bolts) on axles fitted to the kit's wheels, which were cut from the hull; the front pair is under `steer_l0`/`steer_r0` pivots. This own geometry is part of the CC BY-SA 4.0 derivative. No turret or gun (the kit and the original have none). Welded at 3 mm and planar-dissolved at 8 degrees, no collapse.
