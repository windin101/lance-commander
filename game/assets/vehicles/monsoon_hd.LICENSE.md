# monsoon_hd.glb — licence and attribution

The 3D mesh of the HD Monsoon in `monsoon_hd.glb` (and its paint mask `monsoon_hd_paint.bin`) is an adaptation of:

> **"Saracen, Scimitar, and Saladin Hovertanks"** by **UnrestedGuy**, https://www.thingiverse.com/thing:7255716
> licensed under **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)**, https://creativecommons.org/licenses/by-nc-sa/4.0/

## Changes made

The original STL was modified for use as a game model: loose kit pieces (turret, guns, launchers, rotor) put in place on the hull and display bases, sprues and spare pieces removed; the mesh simplified (vertex clustering); scaled, turned and fitted to the MechCommander 2 model it replaces; each part bound to the game model's moving parts (turret, launcher, rotor); painted by region from the original model's team-colour mask; built from the set's Saracen hull and Scimitar standard turret, the turret's long main gun left off (the Monsoon carries short flamers). The changes are made by `tools/art/stl_hd.py`
in this repository (the settings it used: see `original/hd/monsoon/provenance.json` in the build tree).

## Licence of this adaptation

This adaptation of the mesh is licensed under **CC BY-NC-SA 4.0** (https://creativecommons.org/licenses/by-nc-sa/4.0/), the licence of the original. Nothing in this
project restricts what that licence permits for this mesh. The part hierarchy, pivots and animations in the same `.glb` are converted from Microsoft's 2006 MechCommander 2 Shared Source release and remain under that release's licence
(`docs/MC2-SOURCE-EULA.md`); they are not covered by the Creative Commons licence.

This is an unofficial fan project. UnrestedGuy has not endorsed it or this use of their model. The model is provided
as is, without warranties of any kind.
