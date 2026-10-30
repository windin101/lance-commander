# lrmc.glb (v3) — licence and attribution

The 3D mesh of this HD rework model (`lrmc.glb`) and its textures (`lrmc_albedo.png`, `lrmc_orm.png`,
`lrmc_normal.png`, `lrmc_ids.png`, `lrmc_camo.png`) are an adaptation of:

> **"Heavy LRM Carrier"** by **RGriffin65**, https://www.thingiverse.com/thing:7132255
> licensed under **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**,
> https://creativecommons.org/licenses/by-sa/4.0/

## Changes made

Made by `tools/art/v3/v3_mech.py` with the settings in `tools/art/v3/lrmc.json` (Pipeline A, 2026-10-24): the printed
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

Vehicle rework (LANCE-19, 2026-10-30), differs from the mech text above: no joints or actuators. TRACKED kit: MC2's lrmc is a wheeled truck, but the approved v1 source is RGriffin65's tracked Heavy LRM Carrier and is kept. The fit is level (no ICP, `no_icp` in lrmc_veh.json; the v1 ICP pitched it 15 degrees). The kit's fused hull was split by `tools/art/v3/veh_prep.py` (lrmc_prep.json) into the hull, the turret ring (`lrmc_turret`, turns about the vertical axis), the LRM rack (`LrmPods`, the gun: elevates about its rear trunnion) and two track belts (`track_l`, `track_r`: the faces within 130 mm of the closed belt path round the wheels). The nine wheels a side (four road wheels, front and rear end wheels, three return rollers; `wheel_l0`..`wheel_r8`) are OWN GEOMETRY (`make_wheel`: tyre drum, recessed rim, hub boss, bolts) on axles fitted to the kit's wheel circles; the kit's wheel faces were cut from the hull. This own geometry is part of the CC BY-SA 4.0 derivative. The model's turret, rack and muzzle pivots were moved to the kit's turret ring and rack (node positions in the glb). Welded at 3 mm and planar-dissolved at 8 degrees, no collapse; belts on a tread strip of two link pitches (0.58 m) by `veh_lowpoly.py`.
