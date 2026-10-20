#!/usr/bin/env python3
"""CAD rebuild of the Union-type dropship with the liao house texture (appearance dropshipliao).

dropshipliao.glb is the same mesh, UVs and cut-outs as dropshipdavion.glb (checked: identical openings), so this runs
tools/cad/dropshipdavion_cad.py; only the bake differs (it reads dropshipliao's own upscaled art):

    D=~/craft/solid/mc2/buildings/dropshipliao
    python3 -I tools/art/cad_building.py openings dropshipliao > $D/openings.json
    python3 -I tools/cad/dropshipliao_cad.py $D > $D/dropshipliao.json
    solidcraft-cli run $D/dropshipliao.json --out $D/dropshipliao.obj
    python3 -I tools/art/cad_building.py bake dropshipliao $D/dropshipliao.obj --max-res 4096
"""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().with_name("dropshipdavion_cad.py")), run_name="__main__")
