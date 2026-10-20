#!/usr/bin/env python3
"""CAD rebuild of crash shanty 1 (appearance crashshanty1), in the original's frame.

    D=~/craft/solid/mc2/buildings/crashshanty1
    python3 -I tools/art/cad_building.py openings crashshanty1 > $D/openings.json   # only the roof's ragged alpha edge
    python3 -I tools/cad/crashshanty1_cad.py > $D/crashshanty1.json
    solidcraft-cli run $D/crashshanty1.json --out $D/crashshanty1.obj
    python3 -I tools/art/cad_building.py bake crashshanty1 $D/crashshanty1.obj --glass 88,92,98

Everything is derived from the original's faces and their UV mapping by tools/cad/crashshanty_cad.py (walls as
15 cm slabs, the painted black windows and doors as recesses with frames and sills, tan corrugated patches as
proud plates, the roof plating as five overlapping plates with the alpha-cut ragged ends, corner posts).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from crashshanty_cad import build  # noqa: E402

print(build(Path(__file__).name.split("_")[0]).dump())
