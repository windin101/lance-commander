# ambulance.glb (v3) — licence and attribution

The 3D mesh of this HD rework model (`ambulance.glb`) and its textures (`ambulance_albedo.png`, `ambulance_orm.png`,
`ambulance_normal.png`, `ambulance_ids.png`, `ambulance_camo.png`) are an adaptation of:

> **"FightTech - Small Military Car (HBS) - 6mm"** by **Shiaic3D**, https://www.printables.com/model/108537
> licensed under **Creative Commons Attribution 4.0 International (CC BY 4.0)**,
> https://creativecommons.org/licenses/by/4.0/

## Changes made

Made by `tools/art/v3/v3_mech.py` with the settings in `tools/art/v3/ambulance.json` (Pipeline A, 2026-10-24): the printed
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

Vehicle rework (LANCE-19 batch 6, 2026-10-31), differs from the mech text above: no joints or actuators. The fit is level (`no_icp` in ambulance_veh.json). Parts split by `tools/art/v3/veh_prep.py` (ambulance_prep.json). Welded at 3 mm and planar-dissolved at 1.5 degrees, collapse only above 80k faces a part (no Blender collapse on shell soup). Own-geometry wheels (`make_wheel`: tyre drum, recessed rim, hub boss, bolts) where there are wheels; they are part of the derivative. WHEELED, 3 axles, front pair under `steer_*` pivots. Red cross emblem (protected under the Geneva Conventions) used as in the 2001 original; Lee accepted the risk on 2026-10-31: a red cross on a white circle on both sides and the roof, painted as fixed colours (`fixed_colour` in ambulance.json, not team colour). No turret. The roof's vent louvres under the white disc are pressed flat (`flatten` axis z) so the roof disc reads clean.
