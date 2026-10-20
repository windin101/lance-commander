#!/usr/bin/env python3
"""CAD rebuild of the small factory (appearance factorysm), in the original's frame.

    D=~/craft/solid/mc2/buildings/factorysm
    python3 -I tools/art/cad_building.py openings factorysm > $D/openings.json
    python3 -I tools/art/cad_building.py decal factorysm <mat> u0 v0 u1 v1 > $D/decal_<name>.json  (see DECALS)
    python3 -I tools/cad/factorysm_cad.py $D > $D/factorysm.json
    solidcraft-cli run $D/factorysm.json --out $D/factorysm.obj
    python3 -I tools/art/cad_building.py bake factorysm $D/factorysm.obj --max-res 4096

Measured from game/assets/objects/factorysm.glb: a flat-roofed hall (walls to 4.24 m) on a nine-sided plan
(x -9.86..19.29, z -10.38..11.19) whose north-west corner is cut back along two diagonal walls; a canopy at 3.66 m
along the cut-back walls on four posts; a roof monitor (x -7.77..-1.46, z 2.57..9.95) to 5.79 m with a hipped top
to 7.35 m. Relief: the painted louvred fascia (top 0.8 m of every wall) a 12 cm proud band, the dark foot a plinth,
a mitred parapet round the roof, the cut-out louvres real recesses with sills, the doors (two under the canopy,
one on the south wall) recesses with their glazing at the back, the louvre panel on the west wall a shallow
recess; the roof plant (a brown plant box, three AC units, a hatch) real boxes, the canopy a slab with an edge
beam; the monitor an eave lip. Roof pipes stay paint.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

DECALS = {  # name: (material, u0, v0, u1, v1) on the upscaled atlas
    "plant": (1, .458, .378, .630, .469), "ac1": (1, .733, .257, .788, .297), "ac2": (1, .742, .411, .794, .445),
    "ac3": (1, .296, .5, .327, .539), "hatch": (1, .81, .517, .881, .589),
    "doors": (0, .05, .91, .19, .99), "doors2": (0, .215, .91, .355, .99), "door3": (0, .42, .563, .498, .654),
    "louvre": (0, .068, .722, .40, .792),
}
D = Path(sys.argv[1])
TOP = 4.24
PLAN = [(-9.86, 0.82), (-2.58, 0.82), (3.29, -3.49), (5.52, -10.38), (14.4, -10.38), (14.4, -3.51), (19.29, -3.51),
        (19.29, 11.19), (-9.86, 11.19)]


def rects(name):
    return json.load(open(D / f"decal_{name}.json"))["rects"]


def offset(poly, d):
    """Mitred offset of a closed (x, z) polygon, d > 0 outward."""
    P = np.array(poly, float)
    area = sum(P[i, 0] * P[(i + 1) % len(P), 1] - P[(i + 1) % len(P), 0] * P[i, 1] for i in range(len(P)))
    s = 1 if area > 0 else -1
    out = []
    for i in range(len(P)):
        a, b, c = P[i - 1], P[i], P[(i + 1) % len(P)]
        n1 = np.array([(b - a)[1], -(b - a)[0]]) * s / np.linalg.norm(b - a)
        n2 = np.array([(c - b)[1], -(c - b)[0]]) * s / np.linalg.norm(c - b)
        m = n1 + n2
        m /= np.linalg.norm(m)
        out.append(b + m * d / max(0.3, m @ n1))
    return out, s


def ring(name, poly, d, y0, y1, skip=()):
    """A mitred band round the plan, d outward (d < 0: inward), as one prism per wall; skip = wall indices."""
    off, _ = offset(poly, d)
    P = np.array(poly, float)
    for i in range(len(P)):
        if i in skip:
            continue
        j = (i + 1) % len(P)
        q = [tuple(P[i]), tuple(P[j]), tuple(off[j]), tuple(off[i])]
        B.prism_y(f"{name}{i}", q, y0, y1)


B = Builder()
hall = B.prism_y("hall", PLAN, 0.0, TOP)
# fascia over the painted louvred band, a plinth under the dark foot (not along the door wall), a parapet
ring("fascia", PLAN, 0.12, 3.45, TOP)
ring("plinth", PLAN, 0.06, 0.0, 0.3, skip=(1, 7))
B.prism_y("plinth7a", [(19.29, 11.19), (14.1, 11.19), (14.1, 11.25), (19.35, 11.25)], 0.0, 0.3)
B.prism_y("plinth7b", [(12.4, 11.19), (-9.86, 11.19), (-9.92, 11.25), (12.4, 11.25)], 0.0, 0.3)
ring("parapet", PLAN, -0.22, TOP - 0.02, TOP + 0.22)

# ---- canopy along the cut-back walls, on four posts, with an edge beam
CAN = [(-9.86, 0.82), (-8.95, -1.64), (-3.23, -1.64), (1.17, -5.03), (2.87, -10.37), (5.52, -10.38), (3.29, -3.49),
       (-2.58, 0.82)]
B.prism_y("canopy", CAN, 3.52, 3.66)
edge = CAN[:5]
for k in range(len(edge) - 1):
    a, b = np.array(edge[k]), np.array(edge[k + 1])
    t = (b - a) / np.linalg.norm(b - a)
    n = np.array([t[1], -t[0]])  # outward (away from the hall)
    p0, p1 = a, b
    B.prism_y(f"cbeam{k}@avg", [tuple(p0), tuple(p1), tuple(p1 - n * 0.16), tuple(p0 - n * 0.16)], 3.3, 3.68)
for k, (x, z) in enumerate(((-8.78, -1.5), (-3.2, -1.5), (1.28, -4.96), (3.1, -10.3))):
    B.box(f"post{k}@avg", (x - 0.09, 0.0, z - 0.09), (x + 0.09, 3.3, z + 0.09))

# ---- doors (recesses, glazing at the back), louvres, west louvre panel
door_depth = 0.18
doors = rects("doors") + rects("doors2") + rects("door3")
for k, o in enumerate(doors):
    lo = o["center"][1] - o["h"] / 2
    o = dict(o, center=[o["center"][0], (lo + o["h"] + 0.0) / 2 + 0.0, o["center"][2]], h=o["h"] + lo)  # to the ground
    B.recess(hall, o, door_depth)
    B.sill(f"dhood{k}@avg", o, proud=0.16, thick=0.1, overhang=0.1, top=True)
    doors[k] = o


def in_door(o):
    c = np.array(o["center"])
    for d in doors:
        if np.allclose(o["normal"], d["normal"], atol=0.05) and np.linalg.norm(c - np.array(d["center"])) < d["w"] / 2 + 0.2:
            return True
    return False


for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    if in_door(o):
        B.recess(hall, o, 0.05, surface_shift=door_depth)
        continue
    B.recess(hall, o, 0.16)
    B.sill(f"sill{k}", o, proud=0.12, thick=0.07, overhang=0.08)
for o in rects("louvre"):
    B.recess(hall, dict(o, w=o["w"] - 0.1, h=o["h"] - 0.1), 0.08)
    B.frame("lframe", o, width=0.07, proud=0.05)

# ---- roof plant
for nm, hgt in (("plant", 0.75), ("ac1", 0.55), ("ac2", 0.55), ("ac3", 0.55), ("hatch", 0.18)):
    for k, o in enumerate(rects(nm)):
        c = o["center"]
        B.box(f"{nm}{k}", (c[0] - o["w"] / 2, TOP - 0.02, c[2] - o["h"] / 2), (c[0] + o["w"] / 2, TOP + hgt, c[2] + o["h"] / 2),
              chamfer=0.04)

# ---- roof monitor: walls, hipped top, an eave lip
MX0, MX1, MZ0, MZ1, MY = -7.77, -1.46, 2.57, 9.95, 5.79
B.box("monitor", (MX0, TOP - 0.02, MZ0), (MX1, MY, MZ1))
B.loft_y("hip", [(MX0, MZ0), (MX1, MZ0), (MX1, MZ1), (MX0, MZ1)], MY,
         [(-5.71, 4.11), (-3.52, 4.11), (-3.52, 8.42), (-5.71, 8.42)], 7.35)
B.box("eave@avg", (MX0 - 0.12, MY - 0.12, MZ0 - 0.12), (MX1 + 0.12, MY, MZ1 + 0.12))

print(B.dump())
