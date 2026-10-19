#!/usr/bin/env python3
"""CAD rebuild of the medium straight pipeline run (appearance straightpipe2), in the original's frame; the
straightpipe1 build (tools/cad/straightpipe1_cad.py, `pipeline`) with a longer run and one support.

    D=~/craft/solid/mc2/buildings/straightpipe2
    python3 -I tools/cad/straightpipe2_cad.py > $D/straightpipe2.json
    solidcraft-cli run $D/straightpipe2.json --out $D/straightpipe2.obj
    python3 -I tools/art/cad_building.py bake straightpipe2 $D/straightpipe2.obj

Measured from game/assets/objects/straightpipe2.glb: the straightpipe1 pipe and end blocks, the pipe running
z -11.93..3.41 between end blocks at z 3.41..4.26 and -12.78..-11.93, through one low trapezoidal support
(3.4 m wide at the ground, 2.14 m at 0.98 m, z -4.69..-3.83; its UVs are degenerate, so it is concrete-coloured
like the saddles). No cut-outs. Relief as straightpipe1.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402
from straightpipe1_cad import pipeline  # noqa: E402

B = Builder()
pipeline(B, -11.93, 3.41, ends=[(-12.78, -11.93), (3.41, 4.26)], supports=[(-4.69, -3.83)], joints=2)
print(B.dump())
