#!/usr/bin/env python3
"""CAD rebuild of the pipeline end station (appearance endpipe), in the original's frame.

    D=~/craft/solid/mc2/buildings/endpipe
    python3 -I tools/art/cad_building.py openings endpipe > $D/openings.json          (none: the art is opaque)
    python3 -I tools/art/cad_building.py decal endpipe 0 0.036 0.578 0.128 0.615 > $D/decal_vent.json
    python3 -I tools/art/cad_building.py decal endpipe 0 0.172 0.596 0.254 0.631 > $D/decal_label.json
    python3 -I tools/art/cad_building.py decal endpipe 0 0.301 0.547 0.342 0.602 > $D/decal_slats.json
    python3 -I tools/art/cad_building.py decal endpipe 0 0.484 0.18 0.547 0.242 > $D/decal_hole.json
    python3 -I tools/cad/endpipe_cad.py $D > $D/endpipe.json
    solidcraft-cli run $D/endpipe.json --out $D/endpipe.obj
    python3 -I tools/art/cad_building.py bake endpipe $D/endpipe.obj

Measured from game/assets/objects/endpipe.glb (node End): an octagonal hub (x -3.24..5.11, z +-3.24, its +x end drawn
out to a 3.4 m face) with 2.73 m walls and a hipped roof to a 3.4 m square top at 3.92 m; a pipe (a five-sided
prism in the original, top 2.22, bottom 0.52 m) from the hub to an end block (x 11.93..12.78, a trapezoid 3.06 m
at the foot, 1.7 m at the top, 2.73 m high).
Relief: the pipe is round (16 sides, r 0.85 about y 1.37), with flanged collars where it meets hub and block; the
block's painted pipe mouth (r 0.75) is a 35 cm round recess; the roof's painted hatch a raised 2.5 m disc; a ledge
rings the hub at the eaves; the yellow hazard vents are 12 cm recesses, the slatted corner vents 8 cm recesses with
real slats, the red warning plates stand 4 cm proud.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
EAVE, TOP = 2.73, 3.92
OCT = [(-3.24, -1.7), (-1.7, -3.24), (1.7, -3.24), (5.11, -1.7), (5.11, 1.7), (1.7, 3.24), (-1.7, 3.24), (-3.24, 1.7)]  # (x, z)
TOPQ = [(-1.7, -1.65), (-1.65, -1.7), (1.65, -1.7), (1.7, -1.65), (1.7, 1.65), (1.65, 1.7), (-1.65, 1.7), (-1.7, 1.65)]
PY, PR = 1.37, 0.85          # pipe axis height and radius
B = Builder()


def rects(name):
    return json.load(open(D / f"decal_{name}.json"))["rects"]


def ngon(cx, cy, r, k=16, rot=None):
    rot = math.pi / k if rot is None else rot
    return [(cx + r * math.cos(rot + 2 * math.pi * i / k), cy + r * math.sin(rot + 2 * math.pi * i / k)) for i in range(k)]


def offset_poly(poly, d):
    """Outward mitred offset of a convex polygon, given counter-clockwise in (x, -z) i.e. CAD XY."""
    n = len(poly)
    out = []
    for i in range(n):
        p0, p1, p2 = np.array(poly[i - 1]), np.array(poly[i]), np.array(poly[(i + 1) % n])
        e0, e1 = (p1 - p0) / np.linalg.norm(p1 - p0), (p2 - p1) / np.linalg.norm(p2 - p1)
        n0, n1 = np.array([e0[1], -e0[0]]), np.array([e1[1], -e1[0]])
        m = n0 + n1
        m /= np.linalg.norm(m)
        out.append(tuple(p1 + m * d / float(np.dot(m, n0))))
    return out


# ---- hub: octagonal walls, a lofted hipped roof, a ledge at the eaves
hub = B.prism_y("hub", OCT, 0.0, EAVE)
B.loft_y("roof", OCT, EAVE, TOPQ, TOP)
# the ledge: the octagon offset 9 cm (worked in CAD XY = (x, -z), counter-clockwise)
ccw = [(x, -z) for x, z in OCT]
area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ccw, ccw[1:] + ccw[:1]))
if area < 0:
    ccw = ccw[::-1]
B.prism_y("ledge@avg", [(x, -z) for x, z in offset_poly(ccw, 0.09)], EAVE - 0.16, EAVE + 0.02)

# hatch on the top
B.prism_y("hatch", [(x, z) for x, z in ngon(0.1, 0.1, 1.25, 24)], TOP - 0.02, TOP + 0.1)
B.prism_y("hatchlid", [(x, z) for x, z in ngon(0.1, 0.1, 0.95, 24)], TOP + 0.1, TOP + 0.14)

# ---- pipe, collars, end block with its mouth
B.prism_x("pipe", [(z, y) for z, y in ngon(0.0, PY, PR)], 5.0, 11.98)
for k, (xa, xb) in enumerate(((5.11, 5.36), (11.68, 11.93))):
    B.prism_x(f"collar{k}@avg", [(z, y) for z, y in ngon(0.0, PY, PR + 0.12)], xa, xb)
    for j in range(8):  # flange bolts
        a = 2 * math.pi * (j + 0.5) / 8
        B.prism_x(f"bolt{k}_{j}@8c8c84", [(z, y) for z, y in ngon((PR + 0.07) * math.sin(a), PY + (PR + 0.07) * math.cos(a), 0.045, 6)],
                  xa - 0.04 if k == 0 else xa - 0.04, xb + 0.04)
block = B.prism_x("block", [(1.53, 0.0), (0.85, EAVE), (-0.85, EAVE), (-1.53, 0.0)], 11.93, 12.78)
mouth = [o for o in rects("hole") if o["normal"][0] > 0][0]
tool = B.prism_x("mouthcut", [(z, y) for z, y in ngon(mouth["center"][2], mouth["center"][1], 0.62)], 12.43, 12.85)
B.cut(block, tool)
# a raised lip round the mouth
lip_o = ngon(mouth["center"][2], mouth["center"][1], 0.78)
lip_i = ngon(mouth["center"][2], mouth["center"][1], 0.62)
for j in range(16):
    a0, a1, b0, b1 = lip_o[j], lip_o[(j + 1) % 16], lip_i[(j + 1) % 16], lip_i[j]
    B.prism_x(f"lip{j}", [a0, a1, b0, b1], 12.76, 12.83)

# ---- wall details
for o in rects("vent"):
    B.recess(hub, o, 0.12)
    B.sill(f"ventsill{len(B.cmds)}", o, proud=0.08, thick=0.06, overhang=0.04)
for k, o in enumerate(rects("slats")):
    B.recess(hub, o, 0.08)
    n, t, b = (np.array(o[q], float) for q in ("normal", "t", "b"))
    for j in range(3):  # three slats, as painted
        c = np.array(o["center"]) + b * (o["h"] * (0.25 - 0.25 * j)) - n * 0.04
        B.obox(f"slat{k}_{j}@d0d0cc", c, t, b, n, (o["w"] - 0.04, 0.12, 0.05))
for k, o in enumerate(rects("label")):
    n = np.array(o["normal"])
    B.obox(f"label{k}", np.array(o["center"]) + n * 0.015, o["t"], o["b"], o["normal"], (o["w"], o["h"], 0.05))

print(B.dump())
