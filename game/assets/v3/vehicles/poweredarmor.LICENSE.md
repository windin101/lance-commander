# poweredarmor.glb (v3) — licence and attribution

The 3D mesh of this HD rework model (`poweredarmor.glb`) and its textures (`poweredarmor_albedo.png`, `poweredarmor_orm.png`,
`poweredarmor_normal.png`, `poweredarmor_ids.png`, `poweredarmor_camo.png`) are an adaptation of:

> **"Irontold Hawkish Battle Armor (American Mecha)"** by **maggiweber**, https://www.thingiverse.com/thing:5215239
> licensed under **Creative Commons Attribution 4.0 International (CC BY 4.0)**,
> https://creativecommons.org/licenses/by/4.0/

## Changes made

Made by `tools/art/v3/v3_mech.py` with the settings in `tools/art/v3/poweredarmor.json` (Pipeline A, 2026-10-24): the printed
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

This is an unofficial fan project. maggiweber has not endorsed it or this use of their model. The model is provided
as is, without warranties of any kind.

## Notes on the source

Powered armour rework (LANCE-19, 2026-10-31): a SimVehicle with a mech-style skeleton (joint_* with Walk and Run). The approved v1 fit (`stl_rig.py` with ~/craft/solid/mc2/stl/poweredarmor/joints.json, the Standing_01 sculpt) was recaptured by `hd_v2.py poweredarmor --steps fit,segment --folder vehicles`, then built through the mech path (`v3_mech.py`): rigid parts per original node with modelled joint actuators.
