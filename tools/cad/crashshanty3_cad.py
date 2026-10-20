#!/usr/bin/env python3
"""CAD rebuild of crash shanty 3 (appearance crashshanty3), in the original's frame.

    D=~/craft/solid/mc2/buildings/crashshanty3
    python3 -I tools/art/cad_building.py openings crashshanty3 > $D/openings.json   # only the roof's ragged alpha edge
    python3 -I tools/cad/crashshanty3_cad.py > $D/crashshanty3.json
    solidcraft-cli run $D/crashshanty3.json --out $D/crashshanty3.obj
    python3 -I tools/art/cad_building.py bake crashshanty3 $D/crashshanty3.obj --glass 88,92,98

Everything is derived from the original's faces and their UV mapping by tools/cad/crashshanty_cad.py (walls as
15 cm slabs, the painted black windows and doors as recesses with frames and sills, tan corrugated patches as
proud plates, the roof plating as five overlapping plates with the alpha-cut ragged ends, corner posts).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from crashshanty_cad import build  # noqa: E402

print(build(Path(__file__).name.split("_")[0]).dump())
