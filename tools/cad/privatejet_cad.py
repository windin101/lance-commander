#!/usr/bin/env python3
"""CAD rebuild of the parked private jet (appearance privatejet), in the original's frame.

    D=~/craft/solid/mc2/buildings/privatejet
    python3 -I tools/art/cad_building.py openings privatejet > $D/openings.json
    python3 -I tools/cad/privatejet_cad.py > $D/privatejet.json
    solidcraft-cli run $D/privatejet.json --out $D/privatejet.obj
    python3 -I tools/art/cad_building.py bake privatejet $D/privatejet.obj

Measured from game/assets/objects/privatejet.glb (read by tools/cad/aircraft_cad.py): a closed faceted fuselage
(x +-3.12, nose at z 15.64, tail at z -12.83, two engine nacelles on its back ending in flat faces at z -7.69), thin wedge
wings with up- and down-turned tip fins (x to +-9.72, y 2.10..7.47), two canards, and three landing gears drawn
as alpha cards (mains at x +-2, z -5.8..-2.8; nose at z 9.4..10.8). The rebuild keeps the fuselage, wings, fins and canards
facet for facet (tools/cad/aircraft_cad.pyramid_shell: each original triangle the base of a shallow pyramid inside
the solid; the paper-thin fin faces become 3 cm slabs) and replaces the gear cards with real gear: a tandem bogie
under each main card (the card shows two wheels), a single nose wheel, struts and tyres in flat colours. The
painted exhausts in the nacelle faces stay painted (round nozzles over them doubled the art).
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, cad, cad_dir  # noqa: E402
import aircraft_cad as A  # noqa: E402

B = Builder()
comps = A.components("privatejet")
ctr = [c.reshape(-1, 3).mean(0) for c in comps]
size = [len(c) for c in comps]
hull = comps[int(np.argmax(size))]
wings = [c for c, m in zip(comps, ctr) if abs(m[0]) > 3 and len(c) > 10]
canards = [c for c, m in zip(comps, ctr) if m[2] > 6 and abs(m[0]) > 1 and len(c) <= 6]

A.pyramid_shell(B, "hull", hull)
for k, w in enumerate(wings + canards):
    A.pyramid_shell(B, f"wing{k}_", w)

def rod(name, base, axis, r, length, n=20):
    """An n-gon prism along a game axis ('x', 'y' or 'z'), explicit so the triangle count stays low."""
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ring = [(r * np.cos(a), r * np.sin(a)) for a in ang]
    x, y, z = base
    if axis == "x":
        return B.prism_x(name, [(z + u, y + v) for u, v in ring], x, x + length)
    if axis == "y":
        return B.prism_y(name, [(x + u, z + v) for u, v in ring], y, y + length)
    return B.prism_z(name, [(x + u, y + v) for u, v in ring], z, z + length)


def gear(name, x, z, r, w, top):
    rod(f"{name}_tyre@262626", (x - w / 2, r, z), "x", r, w, 24)
    rod(f"{name}_hub@8c8c88", (x - w / 2 - 0.02, r, z), "x", r * 0.55, w + 0.04, 16)
    sx = x + (w / 2 + 0.1) * (np.sign(x) or 1)
    if top > r:
        rod(f"{name}_strut@9a9a96", (sx, r, z), "y", 0.09, top - r, 10)
    B.box(f"{name}_axle@9a9a96", (min(x, x + (w / 2 + 0.2) * (np.sign(x) or 1)) - 0.05, r - 0.06, z - 0.06),
          (max(x, x + (w / 2 + 0.2) * (np.sign(x) or 1)) + 0.05, r + 0.06, z + 0.06))


# the main cards show two wheels in tandem: a bogie each
for nm, x in (("mainl", -2.0), ("mainr", 2.0)):
    gear(nm + "a", x, -4.86, 0.42, 0.3, 0.42)
    gear(nm + "b", x, -3.76, 0.42, 0.3, 0.42)
    sx = x + 0.25 * np.sign(x)
    B.box(f"{nm}_bogie@9a9a96", (sx - 0.06, 0.36, -4.92), (sx + 0.06, 0.48, -3.70))
    rod(f"{nm}_leg@9a9a96", (sx, 0.42, -4.31), "y", 0.1, 1.65, 10)
gear("nose", 0.0, 10.1, 0.4, 0.26, 2.75)
print(B.dump())
