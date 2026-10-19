# vulture_hd.glb — licence and attribution

The 3D mesh of the HD Vulture in `vulture_hd.glb` (and its paint mask `vulture_hd_paint.bin`) is an
adaptation of:

> **"Mad Dog Prime, aka Vulture for Battletech"** by **Syllogy**
> https://www.printables.com/model/1863972-mad-dog-prime-aka-vulture-for-battletech-syllogy
> (originally released free on MyMiniFactory: https://www.myminifactory.com/object/3d-print-mad-dog-prime-aka-vulture-for-battletech-105382)
> licensed under **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)**,
> https://creativecommons.org/licenses/by-nc-sa/4.0/

## Changes made (2026-10-19)

The original file `mdd-prime5.stl` was modified for use as a game model:

- scaled from the 47.5 mm miniature to game size (×193, 9.17 m tall), centred, feet on the ground;
- cut into 12 rigid parts at its hips, knees, ankles, shoulders and elbows;
- re-posed: the sculpted mid-stride legs were turned at the hip and knee into a standing rest pose;
- seam triangles at the cuts smoothed between parts, and dark cylindrical joint caps added at each cut;
- painted by region (team-colour mask) and bound to the MechCommander 2 Vulture skeleton so the game's
  animations move it.

The tool that makes these changes is `tools/art/stl_rig.py` in this repository.

## Licence of this adaptation

This adaptation of the mesh is licensed under the same licence, **CC BY-NC-SA 4.0**
(https://creativecommons.org/licenses/by-nc-sa/4.0/). Nothing in this project restricts what that
licence permits for this mesh.

The skeleton, joint names and animations in the same `.glb` file are converted from Microsoft's 2006
MechCommander 2 Shared Source release and remain under that release's licence
(`docs/MC2-SOURCE-EULA.md`); they are not covered by the CC licence.

This is an unofficial fan project. Syllogy has not endorsed it or this use of their model. The model
is provided as is, without warranties of any kind.
