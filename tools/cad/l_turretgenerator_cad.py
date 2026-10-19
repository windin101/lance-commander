#!/usr/bin/env python3
"""CAD rebuild of the turret power generator (appearance l_turretgenerator), in the original's frame.

    D=~/craft/solid/mc2/buildings/l_turretgenerator
    python3 -I tools/art/cad_building.py openings l_turretgenerator > $D/openings.json
    python3 -I tools/art/cad_building.py decal l_turretgenerator <mat> u0 v0 u1 v1 > $D/decal_<name>.json  (see DECALS)
    python3 -I tools/cad/l_turretgenerator_cad.py $D > $D/l_turretgenerator.json
    solidcraft-cli run $D/l_turretgenerator.json --out $D/l_turretgenerator.obj
    python3 -I tools/art/cad_building.py bake l_turretgenerator $D/l_turretgenerator.obj --keep Coil --glass 20,60,70

Measured from game/assets/objects/l_turretgenerator.glb (node PowerGenerator at x + 4.104, z + 0.082):
a hexagonal hood (x -3.43..3.74 local, flat top at 5.41 m, 60 degree slopes) on stepped, sloping end caps,
between two equipment wings (2.32 x 8 m, 3.14 m walls, chamfered to a 4.09 m top). The hood is a real
25 cm shell: its six rounded slots (the texture's cut-outs) go through it, so the glowing coil card (kept from the
original) shows inside, over a floor at 2.57 m as in the original. Its three bolted panels get a raised
frame. The wings' painted louvres are 12 cm recesses, the duct a raised run, the cabinet a 35 cm box.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

DECALS = {  # name: (material, u0, v0, u1, v1) in the upscaled atlas, for cad_building.py decal
    "louvre0": (0, 0.648, 0.297, 0.732, 0.35), "louvre1": (0, 0.75, 0.297, 0.836, 0.35), "louvre2": (0, 0.852, 0.297, 0.936, 0.35),
    "sidelouvre": (0, 0.88, 0.405, 0.947, 0.46), "duct": (0, 0.645, 0.422, 0.85, 0.437),
    "cabinet": (0, 0.607, 0.45, 0.685, 0.54), "panels": (2, 0.0, 0.42, 0.66, 1.0),
}
D = Path(sys.argv[1])
TX, TZ = 4.10448, 0.08228


def rects(name):
    return json.load(open(D / f"decal_{name}.json"))["rects"]


def loc(z, y):
    return (z + TZ, y)


B = Builder()
# hood: hexagonal prism, shelled 25 cm with the bottom open
hood_prof = [loc(-1.85, 0), loc(1.27, 5.41), loc(7.5, 5.41), loc(10.62, 0)]
hood = B.prism_x("hood", hood_prof, -3.43 + TX, 3.74 + TX)
B.c("solid.shell", faces=[[(TX) * 1000, -(4.4 + TZ) * 1000, 0.0]], thickness=250, direction="inside", body=hood)
# interior floor as in the original (2.57 m), seen through the slots
B.box("floor", (-3.3 + TX, 0.0, 1.4 + TZ), (3.6 + TX, 2.57, 7.37 + TZ))

# stepped end caps, lofted between the original's profiles
mid = [(-0.81, 0.0), (1.79, 4.51), (6.98, 4.51), (9.58, 0.0)]
end = [(0.79, 0.0), (2.59, 3.11), (6.18, 3.11), (7.98, 0.0)]
top = [(-1.85, 0.0), (1.27, 5.41), (7.5, 5.41), (10.62, 0.0)]
for side, (xa, xb, xc) in {"l": (-3.43, -4.78, -6.13), "r": (3.74, 5.08, 6.44)}.items():
    for k, (pa, xa_, pb, xb_) in enumerate(((top, xa, mid, xb), (mid, xb, end, xc))):
        # loft between two (z, y) hexagons at two x: sketch them as x-prism ends via loft_x
        B.n_sk += 1
        a = f"sk{B.n_sk}"
        B.c("sketch.create", plane="YZ", offset=round((xa_ + TX) * 1000, 2), name=a)
        B.c("sketch.line", points=[[round(-(z + TZ) * 1000, 2), round(y * 1000, 2)] for z, y in pa], closed=True)
        B.c("sketch.finish")
        B.n_sk += 1
        b = f"sk{B.n_sk}"
        B.c("sketch.create", plane="YZ", offset=round((xb_ + TX) * 1000, 2), name=b)
        B.c("sketch.line", points=[[round(-(z + TZ) * 1000, 2), round(y * 1000, 2)] for z, y in pb], closed=True)
        B.c("sketch.finish")
        B.c("solid.loft", sections=[{"sketch": a}, {"sketch": b}], body_name=f"cap_{side}{k}", operation="new")

# wings: 3.14 m box with a lofted, chamfered top to 4.09 m
for side, (x0, x1, z0, z1, tx0, tx1, tz0, tz1) in {
        "l": (-4.11, -1.79, 0.50, 8.49, -3.64, -2.18, 1.28, 7.63),
        "r": (10.36, 12.69, 0.58, 8.57, 10.76, 12.21, 1.36, 7.72)}.items():
    w = B.box(f"wing_{side}", (x0, 0.0, z0), (x1, 3.14, z1))
    B.loft_y(f"wingtop_{side}", [(x0, z0), (x1, z0), (x1, z1), (x0, z1)], 3.14,
             [(tx0, tz0), (tx1, tz0), (tx1, tz1), (tx0, tz1)], 4.09)


def owner(c, n=None):
    """The wing a detail sits on; None for the hood, or for a wing face turned to the hood (behind the caps)."""
    x = c[0]
    if n is not None and ((x < 4 and n[0] > 0.5) or (x > 4 and n[0] < -0.5)):
        return None, None
    if x < -1.7:
        return "wing_l", "wingtop_l"
    if x > 10.3:
        return "wing_r", "wingtop_r"
    return None, None


# louvres: 12 cm recesses (wall ones into the box, chamfer ones into the lofted top)
for nm in ("louvre0", "louvre1", "louvre2", "sidelouvre"):
    for o in rects(nm):
        wall, top_ = owner(o["center"], o["normal"])
        if wall is None:
            continue
        tgt = top_ if abs(o["normal"][1]) > 0.2 else wall
        B.recess(tgt, o, 0.12)
for k, o in enumerate(rects("duct")):
    if owner(o["center"], o["normal"])[0]:
        n = np.array(o["normal"])
        B.obox(f"duct{k}@avg", np.array(o["center"]) + n * 0.08, o["t"], o["b"], o["normal"], (o["w"], o["h"], 0.18))
for k, o in enumerate(rects("cabinet")):
    if owner(o["center"], o["normal"])[0]:
        n = np.array(o["normal"])
        B.obox(f"cabinet{k}", np.array(o["center"]) + n * 0.165, o["t"], o["b"], o["normal"], (o["w"], o["h"], 0.35))

# hood panels: raised bolted frame (35 cm bars, 10 cm proud) and the slots through the shell
for k, o in enumerate(rects("panels")):
    inner = dict(o, w=o["w"] - 0.7, h=o["h"] - 0.7)
    B.frame(f"pframe{k}", inner, width=0.35, proud=0.10)
for o in json.load(open(D / "openings.json"))["openings"]:
    B.recess(hood, o, 0.6, round_ends=True)

print(B.dump())
