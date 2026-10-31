# artillerypiece.glb (v3) — licence and attribution

The 3D mesh of this HD rework model (`artillerypiece.glb`) and its textures (`artillerypiece_albedo.png`, `artillerypiece_orm.png`,
`artillerypiece_normal.png`, `artillerypiece_ids.png`, `artillerypiece_camo.png`) are an adaptation of:

> **"Long Tom Mobile Artillery LT-MOB-95"** by **RGriffin65**, https://www.thingiverse.com/thing:6974839
> licensed under **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**,
> https://creativecommons.org/licenses/by-sa/4.0/

## Changes made

Made by `tools/art/v3/v3_mech.py` with the settings in `tools/art/v3/artillerypiece.json` (Pipeline A, 2026-10-24): the printed
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

Vehicle rework (LANCE-19 batch 7, 2026-10-31), differs from the mech text above: no joints or actuators. STATIC emplaced gun (the data gives artillerypiece max_velocity 0, 360 degree turret): RGriffin65's Long Tom Mobile Artillery, the DEPLOYED gun trailer (`Artillery_gun_trailer_deployed.stl`; the stowed trailer and the tractor are not used). No v1 fit existed: the kit was fitted from scratch by `tools/art/v3/v3_rigid.py` (level, `no_icp`, yaw 90 from the search). The kit's fused hull, trailer and tracks stay one static part; the cradle (`Artillery_Turret`, turns about the vertical axis through the barrel) and the barrel (`H_BigGun`, the gun: pitches about the trunnion) were cut out by box in `veh_prep.py` (artillerypiece_prep.json). `gun_pitch` [-25, 20] degrees about the kit's raised rest pose (about 48 degrees; the 2001 model rests at about 35). No wheels or belts: the piece never moves. The hull is reduced by collapse (budget 35k, xatlas on 90k faces ran over 17 minutes; a 2.3M-face kit), the cradle and barrel by weld 3 mm + planar dissolve. Revision 2 (Lee): the kit's tracks and road-wheel shells (z < 1090 m outside the centre spine) were REMOVED and replaced by OUR OWN track shells (`make_slab`: a round-ended prism with bevelled edges, two a side) with static own-geometry road wheels (`make_wheel`) on their outer faces (`extras` in artillerypiece_prep.json); the piece never moves. Loose fragments (shells of up to 5000 faces, such as the kit's tow-bar bits) are dropped (`drop_small_shells`). The hull is reduced by collapse to 25k faces.
