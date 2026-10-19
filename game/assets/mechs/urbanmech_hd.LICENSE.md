# urbanmech_hd.glb — licence and attribution

The 3D mesh of the HD UrbanMech in `urbanmech_hd.glb` (and its paint mask `urbanmech_hd_paint.bin`) is an adaptation of:

> **"UM-R60 Urbanmech for Battletech"** by **Syllogy**, https://www.printables.com/model/1864017
> licensed under **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)**, https://creativecommons.org/licenses/by-nc-sa/4.0/

## Changes made

The original STL was modified for use as a game model: scaled from the miniature to game size and centred, feet on the ground; display base removed where it had one; cut into rigid parts at the hips, knees, ankles and upper body; legs re-posed from the sculpted pose to the MechCommander 2 rest pose (MC2 bone directions, the sculpt's bone lengths); seams smoothed and dark joint caps added at the leg cuts; painted by region (team-colour mask); bound to the MC2 skeleton so the game's animations move it. The changes are made by `tools/art/stl_rig.py`
in this repository (the settings it used: see `original/hd/urbanmech/provenance.json` in the build tree).

## Licence of this adaptation

This adaptation of the mesh is licensed under **CC BY-NC-SA 4.0** (https://creativecommons.org/licenses/by-nc-sa/4.0/), the licence of the original. Nothing in this
project restricts what that licence permits for this mesh. The skeleton, joint names and animations in the same `.glb` are converted from Microsoft's 2006 MechCommander 2 Shared Source release and remain under that release's licence
(`docs/MC2-SOURCE-EULA.md`); they are not covered by the Creative Commons licence.

This is an unofficial fan project. Syllogy has not endorsed it or this use of their model. The model is provided
as is, without warranties of any kind.
