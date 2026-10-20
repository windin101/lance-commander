#!/usr/bin/env python3
"""CAD rebuild of the wreck piece crashengine: a torn-off engine pod of the dropship (a faceted nacelle with an open hexagonal exhaust and a fin), in the original's frame.

    D=~/craft/solid/mc2/buildings/crashengine
    python3 -I tools/art/cad_building.py openings crashengine > $D/openings.json
    python3 -I tools/cad/crashengine_cad.py > $D/crashengine.json
    solidcraft-cli run $D/crashengine.json --out $D/crashengine.obj
    python3 -I tools/art/cad_building.py bake crashengine $D/crashengine.obj --glass 40,32,26

Measured from game/assets/objects/crashengine.glb: double-sided hull sheets whose torn edges are alpha cut-outs (material 1)
plus single-sided closed parts. tools/cad/crash_cad.py turns every planar patch into an 8 cm plate cut to the art's own
alpha outline and extruded inward from the original surface (faces the original pairs back to back become
one plate), so the tears are real edges in the metal. The hull is faceted by
design (the dropship is all flat panels), so its octagonal and hexagonal sections keep their facets.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402
from crash_cad import Wreck  # noqa: E402

B = Builder()
W = Wreck(B, "crashengine", eps=0.12, min_hole=0.4, min_area=0.06, all_double=True)
# Lee (2026-10-20): show the machinery. Material 3 is a plain hull sleeve (oval hatch) about 1.3 m outside the upper
# nacelle machinery (material 2); Godot's import LOD always dropped it from the original, so players saw the
# machinery. Leave the sleeve out so the machinery face is the outside, as the original and upscaled rows show.
W.build(select=lambda i: W.o.mat[i] != 3)
print(W.stats, file=sys.stderr)
print(B.dump())
