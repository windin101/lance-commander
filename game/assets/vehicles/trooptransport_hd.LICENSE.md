# trooptransport_hd.glb — licence and attribution

The 3D mesh of the HD Troop transport in `trooptransport_hd.glb` (and its paint mask `trooptransport_hd_paint.bin`) is an adaptation of:

> **"Packrat, APCs and Heavy APCs for use with Battletech"** by **Pfelpensson**, https://www.thingiverse.com/thing:4592096
> licensed under **Creative Commons Attribution 4.0 International (CC BY 4.0)**, https://creativecommons.org/licenses/by/4.0/

## Changes made

The original STL was modified for use as a game model: loose kit pieces (turret, guns, launchers, rotor) put in place on the hull and display bases, sprues and spare pieces removed; the mesh simplified (vertex clustering); scaled, turned and fitted to the MechCommander 2 model it replaces; each part bound to the game model's moving parts (turret, launcher, rotor); painted by region from the original model's team-colour mask. The changes are made by `tools/art/stl_hd.py`
in this repository (the settings it used: see `original/hd/trooptransport/provenance.json` in the build tree).

## Licence of this adaptation

This adaptation of the mesh is licensed under **CC BY 4.0** (https://creativecommons.org/licenses/by/4.0/), the licence of the original. Nothing in this
project restricts what that licence permits for this mesh. The part hierarchy, pivots and animations in the same `.glb` are converted from Microsoft's 2006 MechCommander 2 Shared Source release and remain under that release's licence
(`docs/MC2-SOURCE-EULA.md`); they are not covered by the Creative Commons licence.

This is an unofficial fan project. Pfelpensson has not endorsed it or this use of their model. The model is provided
as is, without warranties of any kind.
