#!/usr/bin/env python3
"""CAD rebuild of the bridge parapets (appearance bridge), in the original's frame.

    D=~/craft/solid/mc2/buildings/bridge
    python3 -I tools/cad/bridge_cad.py > $D/bridge.json
    solidcraft-cli run $D/bridge.json --out $D/bridge.obj
    python3 -I tools/art/cad_building.py bake bridge $D/bridge.obj

Measured from game/assets/objects/bridge.glb (node Box01, 34 triangles): two trapezoid parapets, x -12.8..12.8,
1.68 m at the ground narrowing to a 0.72 m top at 1.49 m, their outer faces at z = +-10.51; the deck is a
fully transparent quad (alpha 0), left out (the bake writes one opaque material). The texture tiles every
12.8 m with a painted joint at its middle, so the parapets are 6.4 m precast segments: each is its own body,
its top arrises chamfered 4 cm and its ends chamfered 4 cm so the joints are real V-grooves, with two
drainage scuppers (0.5 x 0.16 m) through its foot.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, cad  # noqa: E402

B = Builder()
SEG = 6.4
CH = 0.04
for side, sgn in (("s", -1), ("n", 1)):
    zo, zi, zto, zti = (sgn * v for v in (10.51, 8.83, 10.03, 9.31))
    prof = [(zo, 0.0), (zi, 0.0), (zti, 1.49), (zto, 1.49)]
    if sgn < 0:
        prof = prof[::-1]
    for k in range(4):
        x0, x1 = -12.8 + k * SEG, -12.8 + (k + 1) * SEG
        nm = B.prism_x(f"seg_{side}{k}", prof, x0, x1)
        xm = (x0 + x1) / 2
        edges = [(xm, 1.49, zto), (xm, 1.49, zti)]
        for xe in (x0, x1):
            edges += [(xe, 1.49, (zto + zti) / 2), (xe, 0.745, (zo + zto) / 2), (xe, 0.745, (zi + zti) / 2)]
        B.c("solid.chamfer", edges=[cad(e) for e in edges], distance=CH * 1000, body=nm)
        for f in (0.25, 0.75):  # scuppers through the foot
            xs = x0 + f * SEG
            B.cut(nm, B.box(f"scup_{side}{k}_{f}", (xs - 0.25, -0.05, min(zo, zi) - 0.3), (xs + 0.25, 0.16, max(zo, zi) + 0.3)))

print(B.dump())
