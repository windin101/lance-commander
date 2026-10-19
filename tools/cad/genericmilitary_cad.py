#!/usr/bin/env python3
"""CAD rebuild of the generic military building (appearance genericmilitary), in the original's frame.

    D=~/craft/solid/mc2/buildings/genericmilitary
    python3 -I tools/art/cad_building.py openings genericmilitary > $D/openings.json
    python3 -I tools/art/cad_building.py decal genericmilitary <mat> u0 v0 u1 v1 > $D/decal_<name>.json  (see DECALS)
    python3 -I tools/cad/genericmilitary_cad.py $D > $D/genericmilitary.json
    solidcraft-cli run $D/genericmilitary.json --out $D/genericmilitary.obj
    python3 -I tools/art/cad_building.py bake genericmilitary $D/genericmilitary.obj --keep LOS_Antennae

Measured from game/assets/objects/genericmilitary.glb: a single-storey hall (19.13 x 12.45 m, walls to 4.53 m on a
34 cm plinth band), a 5 x 5 m tower to 7.94 m overlapping its back corner, and an entrance porch (3.94 x 2.71 m slab,
a canopy at 3.69 m on two posts). The antenna on the tower is the original's crossed cut-out cards, kept verbatim
(--keep LOS_Antennae). Relief: every cut-out window a 20 cm recess with a sill; the plinth band 7 cm proud; a 22 cm
parapet round both roofs; the painted string course under each window band a 10 cm ledge; the painted panel joints
real pilasters; the light entrance bay a 30 cm recess with the door's glazing at its back; the roof hatch a raised
housing; the porch canopy real beams and slats on square posts.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

DECALS = {  # name: (material, u0, v0, u1, v1) in the upscaled atlas, for cad_building.py decal
    "ledge_s": (0, 0.19, 0.526, 1.0, 0.540), "ledge_f": (0, 0.19, 0.772, 1.0, 0.786), "ledge_t": (0, 0.0, 0.627, 0.187, 0.642),
    "seam_s0": (0, 0.449, 0.545, 0.464, 0.71), "seam_s1": (0, 0.715, 0.545, 0.73, 0.71),
    "seam_f0": (0, 0.449, 0.79, 0.464, 0.955), "seam_f1": (0, 0.715, 0.79, 0.73, 0.955),
    "bay": (0, 0.461, 0.78, 0.718, 0.96), "hatch": (0, 0.665, 0.295, 0.772, 0.405),
}
D = Path(sys.argv[1])
HALL = ((-8.45, -0.024, -2.53), (10.68, 4.53, 9.92))
TOWER = ((-11.458, -0.024, -4.065), (-6.46, 7.94, 0.94))
BAY_DEPTH = 0.30


def rects(name):
    return json.load(open(D / f"decal_{name}.json"))["rects"]


def inside(p, box, pad=0.05):
    lo, hi = box
    return all(lo[i] + pad < p[i] < hi[i] - pad for i in (0, 2)) and lo[1] < p[1] < hi[1]


def grow(box, d, ytop=None):
    lo, hi = box
    return (lo[0] - d, lo[1], lo[2] - d), (hi[0] + d, ytop if ytop is not None else hi[1], hi[2] + d)


B = Builder()
# ---- volumes
hall = B.box("hall", *HALL)
tower = B.box("tower", *TOWER)
B.box("plinth_hall", *grow(HALL, 0.07, 0.32), chamfer=0.04)
B.box("plinth_tower", *grow(TOWER, 0.07, 0.32), chamfer=0.04)

# parapets, 22 cm wide and 25 cm high, flush with the walls
for nm, (lo, hi) in (("hall", HALL), ("tower", TOWER)):
    (x0, _, z0), (x1, y1, z1) = lo, hi
    w, h = 0.22, 0.25
    for k, (a, b) in enumerate((((x0, z0), (x1, z0 + w)), ((x0, z1 - w), (x1, z1)),
                                ((x0, z0 + w), (x0 + w, z1 - w)), ((x1 - w, z0 + w), (x1, z1 - w)))):
        B.box(f"parapet_{nm}{k}", (a[0], y1, a[1]), (b[0], y1 + h, b[1]), chamfer=0.03)

# ---- entrance bay: 30 cm recess in the front wall
bay = rects("bay")
for o in bay:
    B.recess(hall, o, BAY_DEPTH)
bay_c = np.array(bay[0]["center"]) if bay else None


def in_bay(o):
    if bay_c is None or o["normal"][2] < 0.9:
        return False
    c = np.array(o["center"])
    return abs(c[0] - bay_c[0]) < bay[0]["w"] / 2 and abs(c[1] - bay_c[1]) < bay[0]["h"] / 2


# ---- windows: 20 cm recesses with sills; the door's glazing at the back of the bay; skip the antenna cards
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    c = o["center"]
    if c[1] > 7.9:
        continue
    if in_bay(o):
        B.recess(hall, o, 0.06, surface_shift=BAY_DEPTH)
        continue
    on_tower = c[1] > 4.6
    if not on_tower and inside(c, TOWER, pad=-0.05):
        continue  # a hall window inside the tower
    B.recess(tower if on_tower else hall, o, 0.20)
    B.sill(f"sill{k}", o, proud=0.10, thick=0.06, overhang=0.06)

# ---- string courses (ledges) and panel-joint pilasters
for nm in ("ledge_s", "ledge_f", "ledge_t"):
    for k, o in enumerate(rects(nm)):
        n = np.array(o["normal"])
        if nm != "ledge_t" and inside(o["center"], TOWER, pad=-0.05):
            continue
        B.obox(f"{nm}{k}", np.array(o["center"]) + n * 0.04, o["t"], o["b"], n, (o["w"], 0.12, 0.12))
for nm in ("seam_s0", "seam_s1", "seam_f0", "seam_f1"):
    for k, o in enumerate(rects(nm)):
        n = np.array(o["normal"])
        c = np.array(o["center"])
        if inside(c, TOWER, pad=-0.05) or o["w"] < 0.3:  # under the tower, or a sliver at a wall's end
            continue
        B.obox(f"{nm}_{k}", c + n * 0.04, o["t"], o["b"], n, (0.24, o["h"], 0.12))

# ---- roof hatch
for k, o in enumerate(rects("hatch")):
    if o["normal"][1] > 0.9:
        c = o["center"]
        B.box(f"hatch{k}", (c[0] - o["w"] / 2, c[1] - 0.02, c[2] - o["h"] / 2), (c[0] + o["w"] / 2, c[1] + 0.18, c[2] + o["h"] / 2), chamfer=0.03)

# ---- porch: slab, two square posts, beams and slats under the original canopy plane (3.69 m)
B.box("porch", (-0.84, -0.024, 9.92), (3.10, 0.32, 12.59), chamfer=0.03)
for k, x in enumerate((-0.475, 2.715)):
    B.box(f"post{k}", (x - 0.08, 0.32, 12.06), (x + 0.08, 3.45, 12.22))
for k, z in enumerate((10.0, 12.14)):
    B.box(f"beam{k}", (-0.84, 3.45, z - 0.08), (3.10, 3.57, z + 0.08))
for k in range(8):
    x = -0.84 + 0.06 + k * (3.94 - 0.12) / 7
    B.box(f"slat{k}", (x - 0.06, 3.57, 9.92), (x + 0.06, 3.69, 12.59))

print(B.dump())
