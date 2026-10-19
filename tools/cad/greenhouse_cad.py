#!/usr/bin/env python3
"""CAD rebuild of the greenhouse (appearance greenhouse), in the original's frame.

    D=~/craft/solid/mc2/buildings/greenhouse
    python3 -I tools/art/cad_building.py decal greenhouse 0 0.385 0.07 0.625 0.27 > $D/decal_roller.json
    python3 -I tools/art/cad_building.py decal greenhouse 0 0.657 0.128 0.743 0.275 > $D/decal_door.json
    python3 -I tools/art/cad_building.py decal greenhouse 0 0.03 0.57 0.97 0.97 > $D/decal_glaze.json
    python3 -I tools/cad/greenhouse_cad.py $D > $D/greenhouse.json
    solidcraft-cli run $D/greenhouse.json --out $D/greenhouse.obj
    python3 -I tools/art/cad_building.py bake greenhouse $D/greenhouse.obj

Measured from game/assets/objects/greenhouse.glb (16 triangles, no cut-outs): a trapezoid prism, x -11.24..2.57
at the ground, a flat 3.13 m crown (x -5.9..-2.77) at 3.88 m, z +-9.22. The texture tiles each half of the length
(u 0.167..0.999 = z 0..9.22, mirrored), so the painted details sit at known z: fan centres at z 0, +-3.68, +-7.36
(x -4.39), glazing bars at z 0, +-1.55, +-2.96, +-4.42, +-5.89, +-7.41. Relief: each glazed slope is a 12 cm deep
frame with the panes at the back and real glazing bars on the painted ones; the five roof fans are 25 cm round
wells with a raised hub; ridge rails along both crown edges; verge boards at the gables; a kerb along each slope
foot; the roller door is a 25 cm recess with a hood, the side door a 12 cm recess with a step.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, cad, cad_dir  # noqa: E402

D = Path(sys.argv[1])
B = Builder()
PROF = [(-11.24, 0.0), (2.57, 0.0), (-2.77, 3.88), (-5.9, 3.88)]
Z1 = 9.22
FAN_Z = (0.0, 3.68, -3.68, 7.36, -7.36)
FAN_X = -4.39
BARS = (0.0, 1.55, 2.96, 4.42, 5.89, 7.41)


def rects(name):
    return json.load(open(D / f"decal_{name}.json"))["rects"]


hall = B.prism_z("hall", PROF, -Z1, Z1)

# ---- glazed slopes: recess the glazing 12 cm, bars rise from the panes to 1 cm proud
DEPTH = 0.12
for k, o in enumerate(rects("glaze")):
    B.recess(hall, o, DEPTH)
    n, t, b = (np.array(o[q], float) for q in ("normal", "t", "b"))
    c = np.array(o["center"], float)
    for zb in sorted(set(BARS + tuple(-z for z in BARS))):
        p = c.copy()
        p[2] = zb
        B.obox(f"bar{k}_{zb:+.2f}", p + n * (0.01 - (DEPTH + 0.01) / 2), t, b, n, (0.09, o["h"], DEPTH + 0.01))

# ---- roof fans: round (24-sided) wells with a raised hub and a rim
def ngon(r, cx, cz, k=24):
    return [(cx + r * math.cos(2 * math.pi * i / k), cz + r * math.sin(2 * math.pi * i / k)) for i in range(k)]


for k, z in enumerate(FAN_Z):
    B.cut(hall, B.prism_y(f"fanwell{k}", ngon(1.1, FAN_X, z), 3.88 - 0.12, 4.1))
    B.prism_y(f"hub{k}", ngon(0.6, FAN_X, z, 16), 3.88 - 0.14, 3.95)
    rim = B.prism_y(f"fanrim{k}@avg", ngon(1.18, FAN_X, z), 3.86, 3.92)
    B.cut(rim, B.prism_y(f"fanrim{k}_core", ngon(1.1, FAN_X, z), 3.8, 4.0))

# ---- ridge rails, kerbs
B.box("rail_l@avg", (-5.98, 3.82, -Z1), (-5.84, 3.96, Z1))
B.box("rail_r@avg", (-2.83, 3.82, -Z1), (-2.69, 3.96, Z1))
B.box("kerb_l@avg", (-11.36, 0.0, -Z1), (-10.96, 0.22, Z1))
B.box("kerb_r@avg", (2.29, 0.0, -Z1), (2.69, 0.22, Z1))


# ---- verge boards round the gable outline (10 cm proud of slopes and crown, 14 cm deep, straddling the gable)
def offset_line(pts, d):
    out = []
    segs = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        L = math.hypot(x1 - x0, y1 - y0)
        segs.append(((x1 - x0) / L, (y1 - y0) / L))
    for i, (x, y) in enumerate(pts):
        ns = [(sy, -sx) for sx, sy in segs[max(0, i - 1):i + 1]]
        mx, my = sum(q[0] for q in ns), sum(q[1] for q in ns)
        m = math.hypot(mx, my)
        mx, my = mx / m, my / m
        k = d / (mx * ns[0][0] + my * ns[0][1])
        out.append((x + mx * k, y + my * k))
    return out


roof = [PROF[1], PROF[2], PROF[3], PROF[0]]
for k, z in enumerate((-Z1, Z1)):
    B.prism_z(f"verge{k}@avg", roof + offset_line(roof, 0.10)[::-1], z - 0.07, z + 0.07)

# ---- gable doors
for k, o in enumerate(rects("roller")):
    B.recess(hall, o, 0.25)
    B.sill(f"rollerhood{k}", o, proud=0.25, thick=0.08, overhang=0.15, top=True)
for k, o in enumerate(rects("door")):
    o = dict(o, w=o["w"] - 0.1, h=o["h"] - 0.05, center=[o["center"][0], o["center"][1] - 0.025, o["center"][2]])
    B.recess(hall, o, 0.12)
    sgn = 1 if o["normal"][2] > 0 else -1
    x = o["center"][0]
    B.box(f"step{k}@8f8b84", (x - 0.65, 0.0, min(sgn * Z1, sgn * (Z1 + 0.5))), (x + 0.65, 0.14, max(sgn * Z1, sgn * (Z1 + 0.5))))

print(B.dump())
