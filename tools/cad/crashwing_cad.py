#!/usr/bin/env python3
"""CAD rebuild of the wreck piece crashwing: a wing and engine section of the dropship (faceted nacelles with open exhausts, a gun turret, and a long swept wing), in the original's frame.

    D=~/craft/solid/mc2/buildings/crashwing
    python3 -I tools/art/cad_building.py openings crashwing > $D/openings.json
    python3 -I tools/cad/crashwing_cad.py > $D/crashwing.json
    solidcraft-cli run $D/crashwing.json --out $D/crashwing.obj
    python3 -I tools/art/cad_building.py bake crashwing $D/crashwing.obj --glass 40,32,26

Measured from game/assets/objects/crashwing.glb: double-sided hull sheets whose torn edges are alpha cut-outs (material 1)
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
W = Wreck(B, "crashwing", eps=0.12, min_hole=0.4, min_area=0.06, all_double=True).build()
print(W.stats, file=sys.stderr)
print(B.dump())
