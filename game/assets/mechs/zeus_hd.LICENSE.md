# zeus_hd.glb — licence and attribution

The 3D mesh of the HD Zeus in `zeus_hd.glb` (and its paint mask `zeus_hd_paint.bin`) is an adaptation of:

> **"Zeus ZEU-6A"** by **ChewiewookTheVindicator**, https://www.thingiverse.com/thing:7089967
> licensed under **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**, https://creativecommons.org/licenses/by-sa/4.0/

**Rights note.** The uploader says this is a kitbash based on a ZEU-5T by Matt Mason, with a left arm from OSWALDODDITIES' American Mecha model on Cults3D; the licences of those parts are not stated. Lee Osborne approved its use on 2026-10-19 on the strength of the licence shown on the page. If you hold rights in the original material and want it removed, please open an issue.

## Changes made

The original STL was modified for use as a game model: scaled from the miniature to game size and centred, feet on the ground; display base removed where it had one; cut into rigid parts at the hips, knees, ankles and upper body; legs re-posed from the sculpted pose to the MechCommander 2 rest pose (MC2 bone directions, the sculpt's bone lengths); seams smoothed and dark joint caps added at the leg cuts; painted by region (team-colour mask); bound to the MC2 skeleton so the game's animations move it. The changes are made by `tools/art/stl_rig.py`
in this repository (the settings it used: see `original/hd/zeus/provenance.json` in the build tree).

## Licence of this adaptation

This adaptation of the mesh is licensed under **CC BY-SA 4.0** (https://creativecommons.org/licenses/by-sa/4.0/), the licence of the original. Nothing in this
project restricts what that licence permits for this mesh. The skeleton, joint names and animations in the same `.glb` are converted from Microsoft's 2006 MechCommander 2 Shared Source release and remain under that release's licence
(`docs/MC2-SOURCE-EULA.md`); they are not covered by the Creative Commons licence.

This is an unofficial fan project. ChewiewookTheVindicator has not endorsed it or this use of their model. The model is provided
as is, without warranties of any kind.
