# lifeboat_hd.glb — licence and attribution

The 3D mesh of the HD Lifeboat in `lifeboat_hd.glb` (and its paint mask `lifeboat_hd_paint.bin`) is an adaptation of:

> **"NASA's X-38 CRV"** by **cryptojones**, https://www.thingiverse.com/thing:3453862
> licensed under **Creative Commons Attribution 4.0 International (CC BY 4.0)**, https://creativecommons.org/licenses/by/4.0/

## Changes made

The original STL was modified for use as a game model: display bases, sprues and spare pieces removed; the mesh simplified (vertex clustering); scaled, turned and fitted to the footprint and height of the MechCommander 2 map object it replaces, standing on the ground; painted by region from the original model's own colours; the model, printed nose-up, turned level; stretched per axis to the original's footprint (x 1.2, y 0.87, z 0.87); plain landing gear (struts and wheels) added at the original's wheel positions. The changes are made by `tools/art/stl_hd.py`
in this repository (the settings it used: see `original/hd/lifeboat/provenance.json` in the build tree).

## Licence of this adaptation

This adaptation of the mesh is licensed under **CC BY 4.0** (https://creativecommons.org/licenses/by/4.0/), the licence of the original. Nothing in this
project restricts what that licence permits for this mesh. The node names and placement in the same `.glb` are converted from Microsoft's 2006 MechCommander 2 Shared Source release and remain under that release's licence
(`docs/MC2-SOURCE-EULA.md`); they are not covered by the Creative Commons licence.

This is an unofficial fan project. cryptojones has not endorsed it or this use of their model. The model is provided
as is, without warranties of any kind.
