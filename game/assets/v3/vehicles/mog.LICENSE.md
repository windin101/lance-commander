# mog.glb (v3) — licence and attribution

The 3D mesh of this HD rework model (`mog.glb`) and its textures (`mog_albedo.png`, `mog_orm.png`,
`mog_normal.png`, `mog_ids.png`, `mog_camo.png`) are an adaptation of:

> **"Mobile Orbital Gun"** by **RGriffin65**, https://www.thingiverse.com/thing:7180780
> licensed under **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**,
> https://creativecommons.org/licenses/by-sa/4.0/

## Changes made

Made by `tools/art/v3/v3_mech.py` with the settings in `tools/art/v3/mog.json` (Pipeline A, 2026-10-24): the printed
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

Vehicle rework (LANCE-19 batch 2, rev 2 2026-10-30), differs from the mech text above: no joints or actuators. TRACKED; the kit's treads are eight units (four a side: an inner and an outer column for each of the front and rear bogies). Revision 2: each bogie's inner and outer column is ONE belt part, so the model has four belts `track_l0`, `track_l1`, `track_r0`, `track_r1` (the faces within 260 mm of the closed belt path round the bogie's end wheels, over the whole belt width), each on the shared tread strip (two link pitches, 0.415 m; the belts are wide, so the strip's u resolution is coarse); `VehicleRig` takes any `track_l*`/`track_r*` mesh as a belt. The ten wheels a side (`wheel_l0`..`wheel_r9`: five a bogie, on the outer face of the outer column) are OWN GEOMETRY (`make_wheel`: tyre drum, recessed rim, hub boss, bolts) on the kit's axle caps; the kit's cap faces were cut from the hull. This own geometry is part of the CC BY-SA 4.0 derivative. The inner column's road wheels are not modelled (they are inside the belt). The two-part kit (hull+treads `Mobile_Orbital_Gun_.stl` and the stowed turret `Mobile_Orbital_Gun_turret__stowed.stl`) was fitted level (`no_icp`); the turret (`Mog_Turret`) turns about the kit's neck ring, the twin barrels (`Mog_Guns`, carved out of the turret, pivot at the dome front) elevate, `gun_pitch` [-5, 50] (no original value found). The belts and the hull are reduced by collapse (the treads are a dense 1M-face mesh), the rest by weld 3 mm + planar dissolve 8 degrees.
