# hollander.glb (v3) — licence and attribution

The 3D mesh of this model (`hollander.glb`) and its textures (`hollander_albedo.png`, `hollander_orm.png`,
`hollander_normal.png`, `hollander_ids.png`, `hollander_camo.png`) are our own work, made for this project
(Lee Osborne, with AI assistance from Claude).

## How it was made

1. An in-house blockout of the MechCommander 2 Hollander on the original skeleton's joints
   (`tools/cad/hollander_blockout.py`, `starslayer_detail.py`).
2. Untextured grey renders of that model (front, left, back), detailed by the local Qwen-Image-Edit model, were the
   input to a mesh generator: **Tripo** (paid plan, Lee's account, 2026-10-31, task
   `3edb6c72-f3eb-49e7-b7be-c29ae63f17f1`, model `v3.1-20260211`, multiview, geometry only). The inputs are our own
   art; no third-party images were uploaded (`tools/art/v3/tripo_gen.py`).
3. The generated sculpt was aligned to the original rest frame, decimated, labelled by the nearest part of our
   blockout and run through Pipeline A (`tools/art/v3/v3_mech.py`, settings `tools/art/v3/hollander.json`): joint
   actuators, one UV atlas, Cycles bakes, zone mask and baked wear. A ball at each forearm pivot is our own
   addition. The textures are original work made from those bakes.

## Licence

The design (silhouette, proportions, joint positions) follows the Shared Source MechCommander 2 Hollander, so this
asset is covered by that release's terms: **Shared Source, non-commercial only** (`docs/MC2-SOURCE-EULA.md`). The
generated mesh is output of a commercial service used under Lee's paid plan; no third-party mesh or art is included.
The skeleton, joint names and animations in the same `.glb` are converted from Microsoft's 2006 MechCommander 2
Shared Source release and remain under that release's licence.

This is an unofficial fan project. The model is provided as is, without warranties of any kind.
