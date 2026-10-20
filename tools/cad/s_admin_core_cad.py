#!/usr/bin/env python3
"""CAD rebuild of the administration core block (appearance s_admin_core), in the original's frame.

    D=~/craft/solid/mc2/buildings/s_admin_core
    python3 -I tools/art/cad_building.py openings s_admin_core > $D/openings.json
    python3 -I tools/cad/s_admin_core_cad.py $D > $D/s_admin_core.json
    solidcraft-cli run $D/s_admin_core.json --out $D/s_admin_core.obj
    python3 -I tools/art/cad_building.py bake s_admin_core $D/s_admin_core.obj --max-res 4096 --glass 182,190,198   # the original's lit (white) windows

Measured from game/assets/objects/s_admin_core.glb (triangle dump): a main block (x -17.30..17.89,
z -7.09..6.81, to 12.61 m) on a plinth (x -17.60..18.11, z -7.46..7.18, 0.37 m) under a slab (x -17.60..18.26,
z -7.31..7.11, 12.55..12.92 m); a tower block through it (x -13.23..13.63, z -11.22..2.41, to 18.47 m) on its own
plinth (x -13.76..14.17, z -11.76..2.95) under a slab (x -13.82..14.35, z -11.90..3.04, 18.37..18.81 m); two side
annexes (x -27.88..-17.15 and 17.78..28.50, z -1.62..4.01, to 9.98 m) under slabs (x to -28.39 / 29.02,
z -1.80..4.19, 9.90..10.30 m); two roof vents (louvred frustum 18.77..20.40, box to 21.89, flared cap to 22.41).
Relief: slabs and plinths with chamfered top edges, 6 cm roof fields inside light rims, every cut-out window a
recess with a sill, the painted doors recessed under hoods, louvre slats on the vents.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
B = Builder()


def slab(name, x0, x1, z0, z1, y0, y1, rim=0.4):
    s = B.box(name, (x0, y0, z0), (x1, y1, z1), chamfer=0.05)
    B.cut(s, B.box(f"f_{name}", (x0 + rim, y1 - 0.06, z0 + rim), (x1 - rim, y1 + 0.3, z1 - rim)))
    return s


B.box("plinth", (-17.60, 0.0, -7.46), (18.11, 0.37, 7.18), chamfer=0.05)
B.box("plinth2", (-13.76, 0.0, -11.76), (14.17, 0.37, -7.46), chamfer=0.05,
      chamfer_edges=[(0.2, 0.37, -11.76), (-13.76, 0.37, -9.6), (14.17, 0.37, -9.6)])
main = B.box("main", (-17.30, 0.37, -7.09), (17.89, 12.55, 6.81))
roof = slab("roof", -17.60, 18.26, -7.31, 7.11, 12.55, 12.92)
tower = B.box("tower", (-13.23, 0.37, -11.22), (13.63, 18.37, 2.41))
troof = slab("troof", -13.82, 14.35, -11.90, 3.04, 18.37, 18.81)
annexes = []
for nm, x0, x1, sx0, sx1 in (("annexw", -27.88, -17.30, -28.39, -16.75), ("annexe", 17.89, 28.50, 17.38, 29.02)):
    annexes.append(B.box(nm, (x0, 0.0, -1.62), (x1, 9.90, 4.01)))
    slab(f"{nm}roof", sx0, sx1, -1.80, 4.19, 9.90, 10.30, rim=0.3)

for k, (x0, x1) in enumerate(((-12.97, -7.41), (7.59, 13.15))):
    cx = (x0 + x1) / 2
    cz = (-4.34 + 1.22) / 2
    lo = [(-2.36, -2.36), (2.36, -2.36), (2.36, 2.36), (-2.36, 2.36)]   # 18.77 m, half-size 2.36
    hi = [(-2.78, -2.78), (2.78, -2.78), (2.78, 2.78), (-2.78, 2.78)]   # 20.40 m
    B.loft_y(f"louvre{k}", [(cx + a, cz + b) for a, b in lo], 18.77, [(cx + a, cz + b) for a, b in hi], 20.40)
    B.box(f"vbox{k}", (cx - 2.62, 20.40, cz - 2.62), (cx + 2.62, 21.89, cz + 2.62))
    B.loft_y(f"cap{k}", [(cx + a * 1.0605, cz + b * 1.0605) for a, b in hi], 21.89,
             [(cx + a * 1.1043, cz + b * 1.1043) for a, b in hi], 22.41)
    # louvre slats: four horizontal bars per side on the sloped faces (flat colour of the art under them)
    for j in range(4):
        y = 18.95 + j * 0.40
        r = 2.36 + (y - 18.77) / 1.63 * 0.42 + 0.03
        for s in (-1, 1):
            B.box(f"slat{k}{j}x{s + 1}@avg", (cx + s * r - 0.04, y, cz - r), (cx + s * r + 0.04, y + 0.07, cz + r))
            B.box(f"slat{k}{j}z{s + 1}@avg", (cx - r, y, cz + s * r - 0.04), (cx + r, y + 0.07, cz + s * r + 0.04))

SOLIDS = [((-17.30, 0, -7.09), (17.89, 12.55, 6.81)), ((-13.23, 0, -11.22), (13.63, 18.37, 2.41)),
          ((-27.88, 0, -1.62), (-17.30, 9.9, 4.01)), ((17.89, 0, -1.62), (28.50, 9.9, 4.01))]


def hidden(o):
    p = np.array(o["center"]) + np.array(o["normal"]) * 0.15
    return any(np.all(p > np.array(lo) + 0.02) and np.all(p < np.array(hi) - 0.02) for lo, hi in SOLIDS)


def owner(o):
    x, y, z = o["center"]
    if x < -17.35 or x > 17.95:
        return annexes[0] if x < 0 else annexes[1]
    if y > 12.55 or z < -7.0:
        return tower
    return main


for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    if hidden(o) or abs(o["normal"][1]) > 0.5:
        continue
    B.recess(owner(o), o, 0.15)
    B.sill(f"sill{k}", o, proud=0.10, thick=0.07, overhang=0.06)
for k, o in enumerate(json.load(open(D / "doors.json"))["rects"]):
    if hidden(o) or abs(o["normal"][1]) > 0.5 or o["h"] < 1.2:
        continue
    B.recess(owner(o), o, 0.12)
    B.sill(f"hood{k}", o, proud=0.14, thick=0.08, overhang=0.10, top=True)

print(B.dump())
