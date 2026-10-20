# privatejet_hd.glb — licence and attribution

The 3D mesh of the HD Private jet in `privatejet_hd.glb` (and its paint mask `privatejet_hd_paint.bin`) is an adaptation of:

> **"Beechcraft Starship replica"** by **gbombadon**, https://www.thingiverse.com/thing:7221055
> licensed under **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)**, https://creativecommons.org/licenses/by-nc-sa/4.0/

## Changes made

The original STL was modified for use as a game model: display bases, sprues and spare pieces removed; the mesh simplified (vertex clustering); scaled, turned and fitted to the footprint and height of the MechCommander 2 map object it replaces, standing on the ground; painted by region from the original model's own colours; kit assembled (fuselage and wing, the two canards placed at the nose), propellers and display base left out; the model, printed nose-up, turned level; stretched per axis (x 0.85, z 1.05); plain landing gear (struts and wheels) added at the original's gear positions. The changes are made by `tools/art/stl_hd.py`
in this repository (the settings it used: see `original/hd/privatejet/provenance.json` in the build tree).

## Licence of this adaptation

This adaptation of the mesh is licensed under **CC BY-NC-SA 4.0** (https://creativecommons.org/licenses/by-nc-sa/4.0/), the licence of the original. Nothing in this
project restricts what that licence permits for this mesh. The node names and placement in the same `.glb` are converted from Microsoft's 2006 MechCommander 2 Shared Source release and remain under that release's licence
(`docs/MC2-SOURCE-EULA.md`); they are not covered by the Creative Commons licence.

This is an unofficial fan project. gbombadon has not endorsed it or this use of their model. The model is provided
as is, without warranties of any kind.
