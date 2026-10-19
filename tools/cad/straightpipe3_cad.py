#!/usr/bin/env python3
"""CAD rebuild of the long straight pipeline run (appearance straightpipe3), in the original's frame; the
straightpipe1 build (tools/cad/straightpipe1_cad.py, `pipeline`) with a longer run and two supports.

    D=~/craft/solid/mc2/buildings/straightpipe3
    python3 -I tools/cad/straightpipe3_cad.py > $D/straightpipe3.json
    solidcraft-cli run $D/straightpipe3.json --out $D/straightpipe3.obj
    python3 -I tools/art/cad_building.py bake straightpipe3 $D/straightpipe3.obj

Measured from game/assets/objects/straightpipe3.glb: the straightpipe1 pipe and end blocks, the pipe running
z -11.93..11.93 between end blocks at z +-11.93..12.78, through two low trapezoidal supports (3.4 m wide at the
ground, 2.14 m at 0.98 m, z +-3.83..4.69; concrete-coloured, their UVs are degenerate). No cut-outs.
Relief as straightpipe1.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402
from straightpipe1_cad import pipeline  # noqa: E402

B = Builder()
pipeline(B, -11.93, 11.93, ends=[(-12.78, -11.93), (11.93, 12.78)], supports=[(-4.69, -3.83), (3.83, 4.69)], joints=[-6.2, 6.2])
print(B.dump())
