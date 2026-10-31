# bloodasp.glb (v3) — licence and attribution

The 3D mesh of this model (`bloodasp.glb`) and its textures (`bloodasp_albedo.png`, `bloodasp_orm.png`,
`bloodasp_normal.png`, `bloodasp_ids.png`, `bloodasp_camo.png`) are our own work, made for this project
(Lee Osborne, with AI assistance from Claude).

## How it was made

1. An in-house blockout of the MechCommander 2 Blood Asp on the original skeleton's joints
   (`tools/cad/bloodasp_blockout.py`, `starslayer_detail.py`).
2. Untextured grey renders of that model (front, left, back), detailed by the local Qwen-Image-Edit model, were the
   input to a mesh generator: **Tripo** (paid plan, Lee's account, 2026-11-01, task
   `1969f255-702f-4307-a8ae-16e04f16da29`, model `v3.1-20260211`, 4-view multiview, geometry only). The inputs are our own
   art; no third-party images were uploaded (`tools/art/v3/tripo_gen.py`).
3. The generated sculpt was aligned to the original rest frame, decimated, labelled by the nearest part of our
   blockout (the left outer toe, which the generator lost, is a mirror of the right one; the arm, shoulder-rifle and toe pivots carry pins and collars of our own) and run through Pipeline A (`tools/art/v3/v3_mech.py`, settings `tools/art/v3/bloodasp.json`): joint
   actuators, one UV atlas, Cycles bakes, zone mask and baked wear.  The textures are original work made from those bakes.

## Licence

The design (silhouette, proportions, joint positions) follows the Shared Source MechCommander 2 Blood Asp, so this
asset is covered by that release's terms: **Shared Source, non-commercial only** (`docs/MC2-SOURCE-EULA.md`). The
generated mesh is output of a commercial service used under Lee's paid plan; no third-party mesh or art is included.
The skeleton, joint names and animations in the same `.glb` are converted from Microsoft's 2006 MechCommander 2
Shared Source release and remain under that release's licence.

This is an unofficial fan project. The model is provided as is, without warranties of any kind.
