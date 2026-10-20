#!/usr/bin/env python3
"""CAD rebuild of the straight HPG bunker tunnel (appearance hpg_walkway), in the original's frame; the parts and their relief are
tools/cad/hpg_parts.py (shared with the other HPG bunker pieces).

    D=~/craft/solid/mc2/buildings/hpg_walkway
    python3 -I tools/art/cad_building.py decal hpg_walkway 0 <u0 v0 u1 v1> > $D/decal_<name>.json   (DECALS below)
    python3 -I tools/cad/hpg_walkway_cad.py $D > $D/hpg_walkway.json
    solidcraft-cli run $D/hpg_walkway.json --out $D/hpg_walkway.obj
    python3 -I tools/art/cad_building.py bake hpg_walkway $D/hpg_walkway.obj

Measured from game/assets/objects/hpg_walkway.glb: one tunnel run along x, -12.797..12.79 m (P.T_*); 18 triangles, no cut-outs.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402
import hpg_parts as P  # noqa: E402

DECALS = {  # name: (u0, v0, u1, v1) in the shared atlas (material 0)
    "slot0": (0.055, 0.786, 0.305, 0.806), "slot1": (0.352, 0.786, 0.602, 0.806), "slot2": (0.648, 0.786, 0.898, 0.806),
    "pil0": (0.305, 0.78, 0.352, 0.936), "pil1": (0.602, 0.78, 0.648, 0.936),
    "vent0": (0.71, 0.044, 0.803, 0.124), "vent1": (0.75, 0.607, 0.845, 0.688),
}
D = Path(sys.argv[1])
B = Builder()
P.tunnel(B, "tun_x", "x", -12.797, 12.79)
tunnels = [("tun_x", "x")]
P.relief(B, D, tunnels, has_hub=False)
print(B.dump())
