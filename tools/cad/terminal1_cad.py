#!/usr/bin/env python3
"""CAD rebuild of the spaceport terminal (appearance terminal1), in the original's frame; parts and measurements
in tools/cad/terminal_parts.py.

    D=~/craft/solid/mc2/buildings/terminal1
    python3 -I tools/art/cad_building.py openings terminal1 > $D/openings.json
    python3 -I tools/cad/terminal1_cad.py $D > $D/terminal1.json
    solidcraft-cli run $D/terminal1.json --out $D/terminal1.obj
    python3 -I tools/art/cad_building.py bake terminal1 $D/terminal1.obj --glass 70,96,58
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
print(B.dump())
