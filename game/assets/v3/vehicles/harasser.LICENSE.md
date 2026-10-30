# harasser.glb (v3) — licence and attribution

The 3D mesh of this HD rework model (`harasser.glb`) and its textures (`harasser_albedo.png`, `harasser_orm.png`,
`harasser_normal.png`, `harasser_ids.png`, `harasser_camo.png`) are an adaptation of:

> **"Harasser Hovercraft"** by **RGriffin65**, https://www.thingiverse.com/thing:6734633
> licensed under **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**,
> https://creativecommons.org/licenses/by-sa/4.0/

## Changes made

Made by `tools/art/v3/v3_mech.py` with the settings in `tools/art/v3/harasser.json` (Pipeline A, 2026-10-24): the printed
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

Vehicle rework (LANCE-19, 2026-10-30), differs from the mech text above: no joints or actuators. HOVER craft: no wheels, no tracks. The fit is level (`no_icp` in harasser_veh.json; the v1 ICP pitched the kit 12 degrees nose-down). The kit has TWO box launcher racks; MC2's Harasser has ONE small launcher pod with two weapon nodes (one turret, full traverse). Revision 2 (Lee, 2026-10-30): one launcher was removed (`drop_parts`: the v1 fit's `weapon_02` rack) and the other (`weapon_01`) re-seated on the hull's top centreline over the kit's round deck ring as the part `turret` (a node under the hull, turns about the vertical axis through the ring centre); the two muzzle nodes weapon_01 / weapon_02 are re-parented under it, one per tube row on the rack's front. The rack keeps the kit's raised pose; no `gun` part. Needle triangles left by the kit's simplification were dropped. Welded at 3 mm and planar-dissolved at 8 degrees, no collapse. (Revision 1 had both racks as `turret_l` / `turret_r`.)
