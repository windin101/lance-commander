# vedette.glb (v3) — licence and attribution

The 3D mesh of this HD rework model (`vedette.glb`) and its textures (`vedette_albedo.png`, `vedette_orm.png`,
`vedette_normal.png`, `vedette_ids.png`, `vedette_camo.png`) are an adaptation of:

> **"FightTech - Vedariant - 6mm (Vedette Flatback hull) and SciFi Vehicle - Aurochs-class Land Crawler - 6mm (Tank-Schrek turret)"** by **Shiaic3D**, https://www.printables.com/model/359188 and https://www.printables.com/model/108536
> licensed under **Creative Commons Attribution 4.0 International (CC BY 4.0)**,
> https://creativecommons.org/licenses/by/4.0/

## Changes made

Made by `tools/art/v3/v3_mech.py` with the settings in `tools/art/v3/vedette.json` (Pipeline A, 2026-10-24): the printed
sculpt was scaled to game size; split into rigid parts on the kit's own part lines (crease-bounded panels);
re-posed part by part from the sculpt's pose into the MechCommander 2 rest pose; modelled joint actuators (drums and
balls) and flat decks added where parts meet; reduced to game density; given a new UV atlas; baked (normal, ambient
occlusion, edges) from the full-detail sculpt in Blender Cycles; and painted with a hand-authored zone mask and baked
wear (chips, grime, dust, soot). The textures are original work made from those bakes.

## Licence of this adaptation

This adaptation (mesh and textures) is licensed under **CC BY 4.0** (https://creativecommons.org/licenses/by/4.0/),
the licence of the original. The skeleton, joint names and animations in the same `.glb` are converted from
Microsoft's 2006 MechCommander 2 Shared Source release and remain under that release's licence
(`docs/MC2-SOURCE-EULA.md`); they are not covered by the Creative Commons licence.

This is an unofficial fan project. Shiaic3D has not endorsed it or this use of their model. The model is provided
as is, without warranties of any kind.

## Notes on the source

Vehicle rework (LANCE-19 batch 4, 2026-10-31), differs from the mech text above: no joints or actuators. The fit is level (`no_icp` in vedette_veh.json). Moving parts split by `tools/art/v3/veh_prep.py` (vedette_prep.json). The wheels (`wheel_*`) are OWN GEOMETRY (`make_wheel`: tyre drum, recessed rim, hub boss, bolts) on axles fitted to the kit's wheels, which were cut from the hull; this own geometry is part of the derivative. Welded at 3 mm and planar-dissolved at 3 degrees, collapse only above the per-part budget (no Blender collapse on shell soup). TRACKED, low-poly 6 mm kit (hull and the Tank-Schrek turret, two STLs); the turret `Vedette Turret` turns about its ring (pivot moved to the turret body centre). Belts `track_l`/`track_r` (faces within 120 mm of the closed belt path; the kit's tracks are plain slabs, so the belt is the slab with a tread strip of 2 x 220 mm); seven wheels a side are own geometry on the slab's outer face. One long gun that is part of the turret (no `gun` part, as in the original). The planar dissolve is 1 degree because the kit is already low-poly.
