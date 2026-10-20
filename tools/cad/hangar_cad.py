#!/usr/bin/env python3
"""CAD rebuild of the aircraft hangar (appearance hangar), in the original's frame.

    D=~/craft/solid/mc2/buildings/hangar
    python3 -I tools/art/cad_building.py openings hangar > $D/openings.json
    python3 -I tools/art/cad_building.py decal hangar 0 0.09 0.79 0.49 0.99 > $D/decal_bigdoor.json
    python3 -I tools/art/cad_building.py decal hangar 0 0.11 0.49 0.32 0.66 > $D/decal_shutter.json
    python3 -I tools/cad/hangar_cad.py $D > $D/hangar.json
    solidcraft-cli run $D/hangar.json --out $D/hangar.obj
    python3 -I tools/art/cad_building.py bake hangar $D/hangar.obj

Measured from game/assets/objects/hangar.glb: a barrel-roofed hall, x -19.0..19.2 (the arched ends), z -19.2..19.2
(9.984 m side walls), the roof a 5-facet polyline (13.584 m at z +-12, a 15.584 m flat between z +-4). The facets
lie on a circle, so the roof is a true arc here (radius 35.71 m through the eaves and the 15.584 m crown, within
22 cm of every original facet). Relief: the painted standing seams (pairs of dark lines 1.53 m apart, read from
the texture through the original's UVs) are 30 cm x 8 cm ribs over the curved slopes, interrupted at the two rows
of roof lights; the roof lights (the texture's cut-outs) are recesses with sills; barge trims round both arched
ends and corner posts; a gutter along each eave; the big door (-x end) a 40 cm recess under a hood, the +x
shutter a 30 cm recess, the wall windows 15 cm recesses with sills.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
B = Builder()
X0, X1, ZW, YE, YT = -19.0, 19.2, 19.2, 9.984, 15.584
R = (ZW ** 2 + (YT - YE) ** 2) / (2 * (YT - YE))
YC = YT - R
TE = math.asin(ZW / R)  # eave angle from the crown


def arc(r, a0, a1, step=math.radians(2.5)):
    """(z, y) points of radius r, angle a (from the crown, + toward +z) from a0 to a1."""
    n = max(2, int(math.ceil(abs(a1 - a0) / step)))
    return [(r * math.sin(a0 + (a1 - a0) * i / n), YC + r * math.cos(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def ang(z):
    return math.asin(z / R)


hall = B.prism_x("hall", [(-ZW, 0.0), (ZW, 0.0)] + arc(R, TE, -TE), X0, X1)


def band(name, r0, r1, a0, a1, x0, x1):
    return B.prism_x(name, arc(r1, a0, a1) + arc(r0, a1, a0), x0, x1)


# barge trims round the arched ends, and corner posts under them
for k, (x0, x1) in enumerate(((X0, X0 + 0.3), (X1 - 0.3, X1))):
    band(f"barge{k}@avg", R - 0.1, R + 0.14, -TE, TE, x0, x1)
    for s in (-1, 1):
        zo = s * (ZW - 0.0)
        B.box(f"post{k}{'pm'[s > 0]}@avg", (x0, 0.0, min(zo, zo - s * 0.3)), (x1, YE - 0.02, max(zo, zo - s * 0.3)))
# gutters along the eaves
for s in (-1, 1):
    zo = s * ZW
    B.box(f"gutter{'pm'[s > 0]}", (X0 + 0.3, YE - 0.25, min(zo, zo + s * 0.22)), (X1 - 0.3, YE + 0.02, max(zo, zo + s * 0.22)))

# standing seams: rib centres between the painted line pairs; curved slopes only (the crown strip is plain)
SEAMS = [-17.3, -15.72, -14.15, -12.62, -11.22, -9.65, -8.1, -6.5, -5.0, -3.58, -2.02, -0.45, 1.1, 2.65, 4.05, 5.6,
         7.2, 8.75, 10.3, 11.7, 13.25, 14.82, 16.4, 17.95]
ops = json.load(open(D / "openings.json"))["openings"]
roof_lights = [o for o in ops if o["normal"][1] > 0.5]
win_x = sorted({round(o["center"][0], 2) for o in roof_lights})
for k, x in enumerate(SEAMS):
    segs = [(-TE + 0.004, ang(-4.0))]
    if any(abs(x - wx) < 1.5 for wx in win_x):
        segs += [(ang(4.0), ang(8.25)), (ang(15.55), TE - 0.004)]
    else:
        segs += [(ang(4.0), TE - 0.004)]
    for j, (a0, a1) in enumerate(segs):
        band(f"rib{k}_{j}", R - 0.02, R + 0.08, a0, a1, x - 0.15, x + 0.15)

# roof lights: recesses in the arc (which lies 6-11 cm outside the original facets there) with sills
for k, o in enumerate(roof_lights):
    B.recess(hall, o, 0.34, surface_shift=-0.12)
    B.sill(f"rlsill{k}", o, proud=0.1, thick=0.07, overhang=0.05, surface_shift=-0.12)

# the big door on the -x end: 40 cm recess, hood above
bd = json.load(open(D / "decal_bigdoor.json"))["rects"][0]
c = list(bd["center"]); c[1] = 4.75
bd = dict(bd, center=c, h=9.5)
B.recess(hall, bd, 0.4)
B.sill("doorhood", bd, proud=0.35, thick=0.2, overhang=0.2, top=True)
# shutter on the +x end
sh = json.load(open(D / "decal_shutter.json"))["rects"][0]
c = list(sh["center"]); c[1] = 4.04
sh = dict(sh, center=c, h=8.08)
B.recess(hall, sh, 0.3)
B.sill("shutterhood", sh, proud=0.25, thick=0.12, overhang=0.12, top=True)

# wall windows
for k, o in enumerate(o for o in ops if abs(o["normal"][1]) < 0.5):
    B.recess(hall, o, 0.15)
    B.sill(f"sill{k}", o, proud=0.1, thick=0.07, overhang=0.06)

print(B.dump())
