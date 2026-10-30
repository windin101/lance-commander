# monsoon.glb (v3) — licence and attribution

The 3D mesh of this HD rework model (`monsoon.glb`) and its textures (`monsoon_albedo.png`, `monsoon_orm.png`,
`monsoon_normal.png`, `monsoon_ids.png`, `monsoon_camo.png`) are an adaptation of:

> **"Saracen, Scimitar, and Saladin Hovertanks"** by **UnrestedGuy**, https://www.thingiverse.com/thing:7255716
> licensed under **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)**,
> https://creativecommons.org/licenses/by-nc-sa/4.0/

## Changes made

Made by `tools/art/v3/v3_mech.py` with the settings in `tools/art/v3/monsoon.json` (Pipeline A, 2026-10-24): the printed
sculpt was scaled to game size; split into rigid parts on the kit's own part lines (crease-bounded panels);
re-posed part by part from the sculpt's pose into the MechCommander 2 rest pose; modelled joint actuators (drums and
balls) and flat decks added where parts meet; reduced to game density; given a new UV atlas; baked (normal, ambient
occlusion, edges) from the full-detail sculpt in Blender Cycles; and painted with a hand-authored zone mask and baked
wear (chips, grime, dust, soot). The textures are original work made from those bakes.

## Licence of this adaptation

This adaptation (mesh and textures) is licensed under **CC BY-NC-SA 4.0** (https://creativecommons.org/licenses/by-nc-sa/4.0/),
the licence of the original. The skeleton, joint names and animations in the same `.glb` are converted from
Microsoft's 2006 MechCommander 2 Shared Source release and remain under that release's licence
(`docs/MC2-SOURCE-EULA.md`); they are not covered by the Creative Commons licence.

This is an unofficial fan project. UnrestedGuy has not endorsed it or this use of their model. The model is provided
as is, without warranties of any kind.

## Notes on the source

Vehicle rework (LANCE-19 batch 6, 2026-10-31), differs from the mech text above: no joints or actuators. The fit is level (`no_icp` in monsoon_veh.json). Parts split by `tools/art/v3/veh_prep.py` (monsoon_prep.json). Welded at 3 mm and planar-dissolved at 1.5 degrees, collapse only above 80k faces a part (no Blender collapse on shell soup). Own-geometry wheels (`make_wheel`: tyre drum, recessed rim, hub boss, bolts) where there are wheels; they are part of the derivative. HOVER: no wheels or tracks. Kit: the Saracen hover chassis (`B-Saracen.stl`, baseless) with the Scimitar Standard turret (`Scimitar_Standard_Turret.stl`), as in the approved v1 build: MC2's Monsoon is a 25 t hover tank with one turret and short flamers, and the Scimitar chassis-and-turret pair is the closest of the three variants in the set (Saracen, Scimitar, Saladin); the turret's long main gun is left off (as in v1). The original's two engine nodes (`Engine1`, `Engine02`) are merged into the hull (the kit's side nacelles are static). The turret `Monsoon_Turret` turns about its neck ring.
