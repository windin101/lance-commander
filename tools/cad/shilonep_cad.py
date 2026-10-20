#!/usr/bin/env python3
"""CAD rebuild of the parked Shilone aerospace fighter (appearance shilonep), in the original's frame.

    D=~/craft/solid/mc2/buildings/shilonep
    python3 -I tools/art/cad_building.py openings shilonep > $D/openings.json
    python3 -I tools/cad/shilonep_cad.py > $D/shilonep.json
    solidcraft-cli run $D/shilonep.json --out $D/shilonep.obj
    python3 -I tools/art/cad_building.py bake shilonep $D/shilonep.obj

Measured from game/assets/objects/shilonep.glb (read by tools/cad/aircraft_cad.py): a closed faceted flying-wing
hull (x +-5.19, z -4.41..3.56, y 0.69..2.18), two canted tail fins (open at the foot, sunk in the hull, to 3.16 m),
and three landing gears drawn as alpha cards (mains at x +-0.79, z -2.33..-1.14; nose at z 1.8..2.36). The rebuild
keeps the hull and fins facet for facet (tools/cad/aircraft_cad.pyramid_shell: each original triangle the base of a
pyramid inside the solid) and adds real gear (struts and tyres in flat colours, since the cards are cut-outs).
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402
import aircraft_cad as A  # noqa: E402

B = Builder()
comps = A.components("shilonep")
for k, c in enumerate(comps):
    if len(c) > 6:  # the hull and the two fins; the 4-triangle gear cards are left out
        A.pyramid_shell(B, f"part{k}_", c, max_depth=0.3)


def rod(name, base, axis, r, length, n=20):
    """An n-gon prism along a game axis ('x' or 'y'), explicit so the triangle count stays low."""
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ring = [(r * np.cos(a), r * np.sin(a)) for a in ang]
    x, y, z = base
    if axis == "x":
        return B.prism_x(name, [(z + u, y + v) for u, v in ring], x, x + length)
    return B.prism_y(name, [(x + u, z + v) for u, v in ring], y, y + length)


def gear(name, x, z, r, w, top):
    rod(f"{name}_tyre@262626", (x - w / 2, r, z), "x", r, w, 20)
    rod(f"{name}_hub@8c8c88", (x - w / 2 - 0.015, r, z), "x", r * 0.55, w + 0.03, 12)
    sx = x + (w / 2 + 0.05) * (np.sign(x) or 1)
    rod(f"{name}_strut@9a9a96", (sx, r, z), "y", 0.05, top - r, 10)
    x0, x1 = sorted((x, sx))
    B.box(f"{name}_axle@9a9a96", (x0 - 0.03, r - 0.035, z - 0.035), (x1 + 0.05, r + 0.035, z + 0.035))


gear("mainl", -0.79, -1.73, 0.27, 0.16, 0.85)
gear("mainr", 0.79, -1.73, 0.27, 0.16, 0.85)
gear("nose", 0.0, 2.07, 0.22, 0.13, 1.0)
print(B.dump())
