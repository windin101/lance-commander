#!/usr/bin/env python3
"""CAD rebuild of the power generator (appearance powergenerator), in the original's frame.

    D=~/craft/solid/mc2/buildings/powergenerator
    python3 -I tools/art/cad_building.py openings powergenerator > $D/openings.json
    python3 -I tools/art/cad_building.py decal powergenerator <mat> u0 v0 u1 v1 > $D/decal_<name>.json  (see DECALS)
    python3 -I tools/cad/powergenerator_cad.py $D > $D/powergenerator.json
    solidcraft-cli run $D/powergenerator.json --out $D/powergenerator.obj
    python3 -I tools/art/cad_building.py bake powergenerator $D/powergenerator.obj --keep Coil LOS_PwerSpike --glass 20,60,70

Same atlas and core as l_turretgenerator (tools/cad/l_turretgenerator_cad.py: the shelled hexagonal hood with its
slots, the stepped end caps, the panel frames), 0.10 m further -x (node PowerGenerator at x + 4.0). In place of
the turret generator's wings the caps run on as prisms (to x -4.00 / 12.29), then a low battered connector
(2.53 m) to an end block each side (5.9 x 9.4 m, 2.79 m walls, a four-sided chamfer to a 4.80 m top). The
blocks' painted louvres (chamfers and walls) are 12 cm recesses, the duct a raised run, the cabinet a 35 cm box;
details on a block face hidden by the connector are left out. The two insulator spikes on each block
(LOS_PwerSpike, alpha-cut disc cards) and the glowing coil are kept verbatim from the original.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

DECALS = {  # name: (material, u0, v0, u1, v1) in the upscaled atlas, for cad_building.py decal (as l_turretgenerator)
    "louvre0": (0, 0.648, 0.297, 0.732, 0.35), "louvre1": (0, 0.75, 0.297, 0.836, 0.35), "louvre2": (0, 0.852, 0.297, 0.936, 0.35),
    "sidelouvre": (0, 0.88, 0.405, 0.947, 0.46), "duct": (0, 0.645, 0.422, 0.85, 0.437),
    "cabinet": (0, 0.607, 0.45, 0.685, 0.54), "panels": (2, 0.0, 0.42, 0.66, 1.0),
}
D = Path(sys.argv[1])
TX, TZ = 4.0, 0.08228


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

# cap extensions, battered connectors and the end blocks
B.prism_x("ext_l", [(0.88, 0.0), (8.06, 0.0), (6.26, 3.11), (2.67, 3.11)], -4.00, -2.10)
B.prism_x("ext_r", [(0.88, 0.0), (8.06, 0.0), (6.26, 3.11), (2.67, 3.11)], 10.39, 12.29)
CON = [(1.54, 0.0), (7.39, 0.0), (5.93, 2.53), (3.00, 2.53)]
B.prism_x("con_l", CON, -6.47, -4.00)
B.prism_x("con_r", CON, 12.29, 14.75)
ENDS = {"l": ((-12.37, -6.46, -0.24, 9.19), (-11.72, -6.93, 0.68, 8.18)),
        "r": ((14.75, 20.66, -0.15, 9.29), (15.22, 20.01, 0.78, 8.28))}
for side, ((x0, x1, z0, z1), (tx0, tx1, tz0, tz1)) in ENDS.items():
    B.box(f"end_{side}", (x0, 0.0, z0), (x1, 2.79, z1))
    B.loft_y(f"endtop_{side}", [(x0, z0), (x1, z0), (x1, z1), (x0, z1)], 2.79,
             [(tx0, tz0), (tx1, tz0), (tx1, tz1), (tx0, tz1)], 4.80)


def owner(o):
    """(wall, chamfer) bodies of the end block a detail sits on; None where the connector hides it."""
    x, y, z = o["center"]
    n = o["normal"]
    side = "l" if x < -6.3 else "r" if x > 14.6 else None
    if side is None:
        return None, None
    inner = (side == "l" and n[0] > 0.5) or (side == "r" and n[0] < -0.5)
    if inner and y < 2.6:
        half = max(o["w"], o["h"]) / 2
        lo, hi = 1.54 + 1.46 * y / 2.53, 7.39 - 1.46 * y / 2.53
        if z + half > lo - 0.1 and z - half < hi + 0.1:
            return None, None
    return f"end_{side}", f"endtop_{side}"


for nm in ("louvre0", "louvre1", "louvre2", "sidelouvre"):
    for o in rects(nm):
        wall, top_ = owner(o)
        if wall is None:
            continue
        B.recess(top_ if abs(o["normal"][1]) > 0.2 else wall, o, 0.12)
for k, o in enumerate(rects("duct")):
    if owner(o)[0]:
        n = np.array(o["normal"])
        B.obox(f"duct{k}@avg", np.array(o["center"]) + n * 0.08, o["t"], o["b"], o["normal"], (o["w"], o["h"], 0.18))
for k, o in enumerate(rects("cabinet")):
    if owner(o)[0]:
        n = np.array(o["normal"])
        B.obox(f"cabinet{k}", np.array(o["center"]) + n * 0.165, o["t"], o["b"], o["normal"], (o["w"], o["h"], 0.35))

# hood panels: raised bolted frame (35 cm bars, 10 cm proud) and the slots through the shell
for k, o in enumerate(rects("panels")):
    inner = dict(o, w=o["w"] - 0.7, h=o["h"] - 0.7)
    B.frame(f"pframe{k}", inner, width=0.35, proud=0.10)
for o in json.load(open(D / "openings.json"))["openings"]:
    if abs(o["center"][0] - 4.06) > 1.0:
        continue  # the spikes' disc cards, kept verbatim
    B.recess(hood, o, 0.6, round_ends=True)

print(B.dump())
