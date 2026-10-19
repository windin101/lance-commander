# cargotruck_hd.glb — licence and attribution

The 3D mesh of the HD Cargo truck in `cargotruck_hd.glb` (and its paint mask `cargotruck_hd_paint.bin`) is an adaptation of:

> **"SciFi Vehicle Set 2 - Medium Trucks and Buses - 6mm"** by **Shiaic3D**, https://www.printables.com/model/108619
> licensed under **Creative Commons Attribution 4.0 International (CC BY 4.0)**, https://creativecommons.org/licenses/by/4.0/

**Rights note.** The uploader says the files in this set are remixes of originals they could not trace. Lee Osborne approved its use on 2026-10-19 on the strength of the licence shown on the page. If you hold rights in the original material and want it removed, please open an issue.

## Changes made

The original STL was modified for use as a game model: loose kit pieces (turret, guns, launchers, rotor) put in place on the hull and display bases, sprues and spare pieces removed; the mesh simplified (vertex clustering); scaled, turned and fitted to the MechCommander 2 model it replaces; each part bound to the game model's moving parts (turret, launcher, rotor); painted by region from the original model's team-colour mask. The changes are made by `tools/art/stl_hd.py`
in this repository (the settings it used: see `original/hd/cargotruck/provenance.json` in the build tree).

## Licence of this adaptation

This adaptation of the mesh is licensed under **CC BY 4.0** (https://creativecommons.org/licenses/by/4.0/), the licence of the original. Nothing in this
project restricts what that licence permits for this mesh. The part hierarchy, pivots and animations in the same `.glb` are converted from Microsoft's 2006 MechCommander 2 Shared Source release and remain under that release's licence
(`docs/MC2-SOURCE-EULA.md`); they are not covered by the Creative Commons licence.

This is an unofficial fan project. Shiaic3D has not endorsed it or this use of their model. The model is provided
as is, without warranties of any kind.
