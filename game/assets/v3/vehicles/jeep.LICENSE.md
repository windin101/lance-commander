# jeep.glb (v3) — licence and attribution

The 3D mesh of this HD rework model (`jeep.glb`) and its textures (`jeep_albedo.png`, `jeep_orm.png`,
`jeep_normal.png`, `jeep_ids.png`, `jeep_camo.png`) are an adaptation of:

> **"SciFi Vehicle Set 1 - Cars - 6mm (ORV 1.04)"** by **Shiaic3D**, https://www.printables.com/model/108620
> licensed under **Creative Commons Attribution 4.0 International (CC BY 4.0)**,
> https://creativecommons.org/licenses/by/4.0/

## Changes made

Made by `tools/art/v3/v3_mech.py` with the settings in `tools/art/v3/jeep.json` (Pipeline A, 2026-10-24): the printed
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

Vehicle rework (LANCE-19 batch 7, 2026-10-31), differs from the mech text above: no joints or actuators. RIGHTS: Shiaic3D, SciFi Vehicle Set 1 (Printables 108620, the ORV 1.04 file), labelled CC BY 4.0; part of a set that includes remixes of untraced originals; rights unverified; Lee accepted the risk on 2026-10-31. The fit is level (`no_icp`; v1 had no joints). WHEELED, 2 axles, 4 OWN GEOMETRY wheels (`make_wheel`) on axles fitted to the kit's wheel arches (kit wheel faces cut from the hull; part of the derivative), the front pair under `steer_*`. No turret or gun. No brand marks found on the mesh. Welded at 3 mm, planar-dissolved at 1.5 degrees.
