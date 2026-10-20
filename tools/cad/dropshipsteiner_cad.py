#!/usr/bin/env python3
"""CAD rebuild of the Union-type dropship with the steiner house texture (appearance dropshipsteiner).

dropshipsteiner.glb is the same mesh, UVs and cut-outs as dropshipdavion.glb (checked: identical openings), so this runs
tools/cad/dropshipdavion_cad.py; only the bake differs (it reads dropshipsteiner's own upscaled art):

    D=~/craft/solid/mc2/buildings/dropshipsteiner
    python3 -I tools/art/cad_building.py openings dropshipsteiner > $D/openings.json
    python3 -I tools/cad/dropshipsteiner_cad.py $D > $D/dropshipsteiner.json
    solidcraft-cli run $D/dropshipsteiner.json --out $D/dropshipsteiner.obj
    python3 -I tools/art/cad_building.py bake dropshipsteiner $D/dropshipsteiner.obj --max-res 4096
"""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().with_name("dropshipdavion_cad.py")), run_name="__main__")
