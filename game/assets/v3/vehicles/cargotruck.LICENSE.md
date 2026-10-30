# cargotruck.glb (v3) — licence and attribution

The 3D mesh of this HD rework model (`cargotruck.glb`) and its textures (`cargotruck_albedo.png`, `cargotruck_orm.png`,
`cargotruck_normal.png`, `cargotruck_ids.png`, `cargotruck_camo.png`) are an adaptation of:

> **"SciFi Vehicle Set 2 - Medium Trucks and Buses - 6mm (Truck Scania35p)"** by **Shiaic3D**, https://www.printables.com/model/108619
> licensed under **Creative Commons Attribution 4.0 International (CC BY 4.0)**,
> https://creativecommons.org/licenses/by/4.0/

## Changes made

Made by `tools/art/v3/v3_mech.py` with the settings in `tools/art/v3/cargotruck.json` (Pipeline A, 2026-10-24): the printed
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

Vehicle rework (LANCE-19 batch 5, 2026-10-31), differs from the mech text above: no joints or actuators. RIGHTS: Shiaic3D, SciFi Vehicle Set 2 (Printables 108619), labelled CC BY 4.0; a remix of untraced originals, the shape after a real brand design; rights unverified; Lee accepted the risk on 2026-10-31. The fit is level (`no_icp` in cargotruck_veh.json); the kit is the v1 `scania_sub.stl` (the subdivided `BT-v_Truck-Scania35p-6mm.stl`). WHEELED: tractor and trailer in one fused hull, 5 axles (10 wheels `wheel_l0`..`wheel_r4`, OWN GEOMETRY, `make_wheel`, on axles fitted to the kit's wheel arches; the kit's wheel faces were cut from the hull; this own geometry is part of the derivative); the front pair is under `steer_l0`/`steer_r0`. The container with its red mark is part of the original model; the kit's trailer is a plain box, so no part-level change. The kit's grille carries the embossed brand name "SCANIA" (a real trademark): the vertices of the lettering are pressed flat onto the grille panel (`flatten` in cargotruck_prep.json, `veh_prep.py`); the shape is kept, the mark is gone. No turret or gun. Welded at 3 mm and planar-dissolved at 3 degrees.
