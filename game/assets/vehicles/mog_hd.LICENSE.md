# mog_hd.glb — licence and attribution

The 3D mesh of the HD MOG in `mog_hd.glb` (and its paint mask `mog_hd_paint.bin`) is an adaptation of:

> **"Mobile Orbital Gun"** by **RGriffin65**, https://www.thingiverse.com/thing:7180780
> licensed under **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**, https://creativecommons.org/licenses/by-sa/4.0/

## Changes made

The original STL was modified for use as a game model: loose kit pieces (turret, guns, launchers, rotor) put in place on the hull and display bases, sprues and spare pieces removed; the mesh simplified (vertex clustering); scaled, turned and fitted to the MechCommander 2 model it replaces; each part bound to the game model's moving parts (turret, launcher, rotor); painted by region from the original model's team-colour mask. The changes are made by `tools/art/stl_hd.py`
in this repository (the settings it used: see `original/hd/mog/provenance.json` in the build tree).

## Licence of this adaptation

This adaptation of the mesh is licensed under **CC BY-SA 4.0** (https://creativecommons.org/licenses/by-sa/4.0/), the licence of the original. Nothing in this
project restricts what that licence permits for this mesh. The part hierarchy, pivots and animations in the same `.glb` are converted from Microsoft's 2006 MechCommander 2 Shared Source release and remain under that release's licence
(`docs/MC2-SOURCE-EULA.md`); they are not covered by the Creative Commons licence.

This is an unofficial fan project. RGriffin65 has not endorsed it or this use of their model. The model is provided
as is, without warranties of any kind.
