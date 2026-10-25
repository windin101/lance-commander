# vulture.glb (v3) — licence and attribution

The 3D mesh of this HD rework model (`vulture.glb`) and its textures (`vulture_albedo.png`, `vulture_orm.png`,
`vulture_normal.png`, `vulture_ids.png`, `vulture_camo.png`) are an adaptation of:

> **"Mad Dog Prime, aka Vulture for Battletech"** by **Syllogy**, https://www.printables.com/model/1863972-mad-dog-prime-aka-vulture-for-battletech-syllogy
> licensed under **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)**,
> https://creativecommons.org/licenses/by-nc-sa/4.0/

## Changes made

Made by `tools/art/v3/v3_mech.py` with the settings in `tools/art/v3/vulture.json` (Pipeline A, 2026-10-24): the printed
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

This is an unofficial fan project. Syllogy has not endorsed it or this use of their model. The model is provided
as is, without warranties of any kind.
