#!/usr/bin/env python3
"""CAD rebuild of the weathered Quonset hut (appearance quonset), in the original's frame. Same hull and UV layout
as quonsetclean (tools/cad/quonsetclean_cad.py, the approved pilot) with its own rusty, sandbagged texture.

    D=~/craft/solid/mc2/buildings/quonset
    python3 -I tools/art/cad_building.py openings quonset > $D/openings.json
    python3 -I tools/cad/quonset_cad.py $D/openings.json > $D/quonset.json
    solidcraft-cli run $D/quonset.json --out $D/quonset.obj
    python3 -I tools/art/cad_building.py bake quonset $D/quonset.obj

Measured from game/assets/objects/quonset.glb: a 10-facet half-cylinder, radius 4.25 m about the ground line,
from z = -12.68 to 4.15. The painted corrugation runs lengthwise with a 0.627 m pitch, its dark troughs at
0.049 + 0.0469 k in v (row minima of the upscaled hull, the same phase as quonsetclean), i.e. 0.596 + 0.627 k m of
arc from the crown: the hull is that profile as real ridges, 6 cm deep. Ends: the wall sits 18 cm inside a 12 cm lip
of the hull; the door is a 30 cm recess with a concrete step; windows (from the texture's cut-outs) are 20 cm
recesses with sills; 6 cm arch ribs ring the hull between the side windows, at
the painted sheet joints. The sandbags stay painted.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

R, Z0, Z1 = 4.25, -12.68, 4.152
PITCH, TROUGH0, AMP = 0.627, 0.596, 0.03
LIP, INSET = 0.12, 0.18

openings = json.load(open(sys.argv[1]))["openings"]
B = Builder()

# hull: corrugated half-cylinder, ridges along z
arc = math.pi * R
n = int(round(arc / PITCH * 12))
pts = []
for i in range(n + 1):
    th = math.pi * i / n                   # 0 = the +x ground line, pi/2 = crown
    s = abs(math.pi / 2 - th) * R          # arc from the crown
    r = R - AMP * math.cos(2 * math.pi * (s - TROUGH0) / PITCH)  # trough (r = R - AMP) on the painted dark line
    r -= AMP * (1 - min(1.0, th / 0.05, (math.pi - th) / 0.05))  # meet the ground cleanly
    pts.append((r * math.cos(th), max(0.0, r * math.sin(th))))
pts[0] = (pts[0][0], 0.0)
pts[-1] = (pts[-1][0], 0.0)
hull = B.prism_z("hull", pts, Z0, Z1)

# inset end walls: cut a 24-gon half disc of radius R - LIP back INSET from each end
def half_disc(rad, k=24):
    return [(rad * math.cos(math.pi * i / k), rad * math.sin(math.pi * i / k)) for i in range(k + 1)]

for z in (Z0, Z1):
    a, b = (z - 0.05, z + INSET) if z == Z0 else (z - INSET, z + 0.05)
    t = B.prism_z(f"inset{z:+.0f}", [(x, max(y, 0.0) - (0.05 if y < 1e-6 else 0)) for x, y in half_disc(R - LIP)], a, b)
    B.cut(hull, t)

# arch ribs between the side windows, one sheet bay (4.23 m) apart
outer = [(x, y) for x, y in half_disc(R + AMP + 0.06, 48)]
inner = [(x, y) for x, y in half_disc(R - AMP - 0.02, 48)][::-1]
for k, zr in enumerate((-10.62, -6.39, -2.16, 2.07)):
    B.prism_z(f"rib{k}@avg", outer + inner, zr - 0.1, zr + 0.1)

for k, o in enumerate(openings):
    end = abs(o["normal"][2]) > 0.9
    door = end and o["h"] > 1.5
    if end:
        B.recess(hull, o, 0.30 if door else 0.20, surface_shift=INSET)
        if door:  # concrete step in front of the door, 15 cm, on the ground
            zc = o["center"][2]
            sgn = 1 if o["normal"][2] > 0 else -1
            zs = zc - sgn * INSET
            B.box(f"step{k}@8f8b84", (-0.75, 0.0, min(zs, zs + sgn * 0.9)), (0.75, 0.15, max(zs, zs + sgn * 0.9)))
        else:
            B.sill(f"sill{k}", o, proud=0.10, thick=0.07, overhang=0.08, surface_shift=INSET)
    else:
        B.recess(hull, o, 0.20)
        # no hoods: on this darker hull they read as black flags past the far-side silhouette at 40 deg pitch
        B.sill(f"sill{k}", o, proud=0.10, thick=0.06, overhang=0.06)

print(B.dump())
