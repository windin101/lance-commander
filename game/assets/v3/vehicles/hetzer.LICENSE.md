# hetzer.glb (v3) — licence and attribution

The 3D mesh of this HD rework model (`hetzer.glb`) and its textures (`hetzer_albedo.png`, `hetzer_orm.png`,
`hetzer_normal.png`, `hetzer_ids.png`, `hetzer_camo.png`) are an adaptation of:

> **"Hetzer (LRM) for battletech"** by **PrysmaTheMagical**, https://www.thingiverse.com/thing:6459522
> licensed under **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**,
> https://creativecommons.org/licenses/by-sa/4.0/

## Changes made

Made by `tools/art/v3/v3_mech.py` with the settings in `tools/art/v3/hetzer.json` (Pipeline A, 2026-10-24): the printed
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

This is an unofficial fan project. PrysmaTheMagical has not endorsed it or this use of their model. The model is provided
as is, without warranties of any kind.

## Notes on the source

Vehicle rework (LANCE-19 batch 9, 2026-10-31), differs from the mech text above: no joints or actuators. RIGHTS: PrysmaTheMagical, "Hetzer (LRM) for battletech" (Thingiverse 6459522), labelled CC BY-SA 4.0; built from two Cults3D models of unverified licence; rights unverified; Lee accepted the risk on 2026-10-31. The fit is level (`no_icp`, v1 yaw 270). WHEELED, 2 axles, 4 OWN GEOMETRY wheels (`make_wheel`) on the kit's wheel arches (kit wheel faces cut from the hull), front pair under `steer_*`. The kit carries LRM tube banks fixed on the hull top; the original has one cannon and max_turret_yaw 0, so no turret or gun part. Welded at 3 mm, planar-dissolved at 1.5 degrees, collapse above 80k faces.
