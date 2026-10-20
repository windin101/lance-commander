#!/usr/bin/env python3
"""CAD rebuild of the spaceport terminal (appearance terminal2: terminal2 with a second mast and flight turned 180 degrees about y), in the original's frame; parts and measurements
in tools/cad/terminal_parts.py.

    D=~/craft/solid/mc2/buildings/terminal2
    python3 -I tools/art/cad_building.py openings terminal2 > $D/openings.json
    python3 -I tools/cad/terminal2_cad.py $D > $D/terminal2.json
    solidcraft-cli run $D/terminal2.json --out $D/terminal2.obj
    python3 -I tools/art/cad_building.py bake terminal2 $D/terminal2.obj --glass 70,96,58
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402
import terminal_parts as T  # noqa: E402

D = Path(sys.argv[1])
B = Builder()
T.hall(B, D)
T.mast(B, 0, flip=False)
T.flight(B, 0, flip=False, z_end=12.54)
T.mast(B, 1, flip=True)
T.flight(B, 1, flip=True, z_end=12.75)
print(B.dump())
