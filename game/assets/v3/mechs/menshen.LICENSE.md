# menshen.glb (v3) — licence and attribution

The 3D mesh of this HD rework model (`menshen.glb`) and its textures (`menshen_albedo.png`, `menshen_orm.png`,
`menshen_normal.png`, `menshen_ids.png`, `menshen_camo.png`) are an adaptation of:

> **"Men Shen Omnimech (Gen 3), variant O, re-posed"** by **UnrestedGuy (re-pose: our modification)**, https://www.thingiverse.com/thing:6315062
> licensed under **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)**,
> https://creativecommons.org/licenses/by-nc-sa/4.0/

## Changes made

Made by `tools/art/v3/v3_mech.py` with the settings in `tools/art/v3/menshen.json` (Pipeline A, 2026-10-24): the printed
sculpt was scaled to game size; split into rigid parts on the kit's own part lines (crease-bounded panels);
re-posed part by part from the sculpt's pose into the MechCommander 2 rest pose; modelled joint actuators (drums and
balls) and flat decks added where parts meet; reduced to game density; given a new UV atlas; baked (normal, ambient
occlusion, edges) from the full-detail sculpt in Blender Cycles; and painted with a hand-authored zone mask and baked
wear (chips, grime, dust, soot). The textures are original work made from those bakes.

Before that, our own modification of the sculpt: `tools/art/menshen/repose_menshen.py` kept the print's upright leg,
mirrored it onto the other side so both legs stand in the same neutral pose, drew the toes together toward the
original's footprint (rear claw about half as long), tucked the two weapon pods in by about 0.75 m each and lifted
them 0.4 m. The printed shells are moved rigidly; nothing is cut or stretched. The shells are labelled to the MC2
parts by `tools/art/menshen/menshen_labels.py`. This modified version is shared under the same licence.

## Licence of this adaptation

This adaptation (mesh and textures) is licensed under **CC BY-NC-SA 4.0** (https://creativecommons.org/licenses/by-nc-sa/4.0/),
the licence of the original. The skeleton, joint names and animations in the same `.glb` are converted from
Microsoft's 2006 MechCommander 2 Shared Source release and remain under that release's licence
(`docs/MC2-SOURCE-EULA.md`); they are not covered by the Creative Commons licence.

This is an unofficial fan project. UnrestedGuy (re-pose: our modification) has not endorsed it or this use of their model. The model is provided
as is, without warranties of any kind.
