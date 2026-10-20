#!/usr/bin/env python3
"""CAD rebuild of the landed lifeboat (appearance lifeboat), in the original's frame.

    D=~/craft/solid/mc2/buildings/lifeboat
    python3 -I tools/art/cad_building.py openings lifeboat > $D/openings.json   # only the gear cards' gaps
    python3 -I tools/cad/lifeboat_cad.py > $D/lifeboat.json
    solidcraft-cli run $D/lifeboat.json --out $D/lifeboat.obj
    python3 -I tools/art/cad_building.py bake lifeboat $D/lifeboat.obj

Measured from game/assets/objects/lifeboat.glb (one node, 108 triangles): a closed faceted yellow hull
(x +-2.32, y 0.35..1.85, z -1.71..2.86, swept fins up top), a 5-sided open-ended rocket nozzle at the stern
(z -1.92..-2.41, about (0, 1.12), r 0.55..0.63), and two landing-gear alpha cards at x = +-1 (z -0.74..0.28,
y 0..0.63) each painted with two tandem wheels under a strut. The rebuild keeps the hull facet for facet
(tools/cad/aircraft_cad.pyramid_shell), makes the nozzle a true round 24-sided bell with a hollow throat (issue
I77) and replaces the gear cards with real gear (two tyres and hubs on an axle beam, a strut into the hull) in
flat colours. The painted canopy and lights stay painted.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, cad  # noqa: E402
import aircraft_cad as A  # noqa: E402

B = Builder()
comps = A.components("lifeboat")
hull = max(comps, key=len)
A.pyramid_shell(B, "hull", hull)


def ring(r, cx, cy, n=24):
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return [[round((cx + r * np.cos(t)) * 1000, 2), round((cy + r * np.sin(t)) * 1000, 2)] for t in a]


def frustum_z(name, z0, r0, z1, r1, cx, cy, n=24):
    """A round frustum along game z (a ruled loft between two n-gons)."""
    secs = []
    for z, r in ((z0, r0), (z1, r1)):
        B.n_sk += 1
        sk = f"sk{B.n_sk}"
        A._plane(B, sk, np.array(cad((0, 0, z)), float), np.array([1.0, 0, 0]), np.array([0, 0, 1.0]))
        B.c("sketch.line", points=ring(r, cx, cy, n), closed=True)
        B.c("sketch.finish")
        secs.append({"sketch": sk})
    B.c("solid.loft", sections=secs, body_name=name, operation="new")
    return name


def rod(name, base, axis, r, length, n=20):
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ringp = [(r * np.cos(a), r * np.sin(a)) for a in ang]
    x, y, z = base
    if axis == "x":
        return B.prism_x(name, [(z + u, y + v) for u, v in ringp], x, x + length)
    return B.prism_y(name, [(x + u, z + v) for u, v in ringp], y, y + length)


# ---- the stern nozzle: round bell, hollow throat
NX, NY = 0.0, 1.12
frustum_z("nozzle", -1.60, 0.50, -2.41, 0.63, NX, NY)
frustum_z("throat", -2.05, 0.40, -2.46, 0.55, NX, NY)
B.cut("nozzle", "throat")

# ---- landing gear: the cards show two tandem wheels under a strut
R, W = 0.23, 0.18
for side, x in (("l", -1.0), ("r", 1.0)):
    for k, z in enumerate((-0.52, 0.03)):
        rod(f"g{side}{k}_tyre@262626", (x - W / 2, R, z), "x", R, W, 24)
        rod(f"g{side}{k}_hub@b8b4a8", (x - W / 2 - 0.015, R, z), "x", R * 0.5, W + 0.03, 16)
    B.box(f"g{side}_beam@8c8a84", (x - 0.05, R - 0.05, -0.56), (x + 0.05, R + 0.05, 0.07))
    rod(f"g{side}_strut@9a9890", (x, R, -0.245), "y", 0.07, 0.62 - R, 12)
print(B.dump())
