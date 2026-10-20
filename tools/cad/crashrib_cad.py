#!/usr/bin/env python3
"""CAD rebuild of the wreck piece crashrib (a torn strip of dropship hull with two ribs standing out of it), in the
original's frame.

    D=~/craft/solid/mc2/buildings/crashrib
    python3 -I tools/art/cad_building.py openings crashrib > $D/openings.json
    python3 -I tools/cad/crashrib_cad.py > $D/crashrib.json
    solidcraft-cli run $D/crashrib.json --out $D/crashrib.obj
    python3 -I tools/art/cad_building.py bake crashrib $D/crashrib.obj --glass 40,32,26

Measured from game/assets/objects/crashrib.glb (60 triangles, one node): a double-sided hull skin (x -4.07..-1.15,
z -10.6..10.4) and two double-sided rib frames (x -4.07..3.95, y to 15.0, z -6.3 and 5.6), their torn and holed edges
drawn as alpha cut-outs. tools/cad/crash_cad.py turns every planar patch into an 8 cm plate, extruded inward, cut to the art's own
alpha outline, so the tears are real edges in the metal.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402
from crash_cad import Wreck  # noqa: E402

B = Builder()
W = Wreck(B, "crashrib", eps=0.08).build()
print(W.stats, file=sys.stderr)
print(B.dump())
