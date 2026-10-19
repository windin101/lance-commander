#!/usr/bin/env python3
"""CAD rebuild of the industrial complex (appearance industrialcomplex), in the original's frame.

    D=~/craft/solid/mc2/buildings/industrialcomplex
    python3 -I tools/art/cad_building.py openings industrialcomplex > $D/openings.json
    python3 -I tools/art/cad_building.py decal industrialcomplex 0 u0 v0 u1 v1 > $D/decal_<name>.json  (see DECALS)
    python3 -I tools/cad/industrialcomplex_cad.py $D > $D/industrialcomplex.json
    solidcraft-cli run $D/industrialcomplex.json --out $D/industrialcomplex.obj
    python3 -I tools/art/cad_building.py bake industrialcomplex $D/industrialcomplex.obj

Measured from game/assets/objects/industrialcomplex.glb: two long wings (x -9.87..-3.82 and 4.64..10.68,
z -12.33..12.58) with outer walls to 11.18 m and monopitch roofs rising to 12.99 m at their inner walls; a middle
block between them (z -11.42..11.67) to 12.08 m with an air-handler box (x -1.1..2.52, z -10.81..-5.38) to 13.59 m;
a lean-to on the west (x -11.68..-9.87, 8.46 m to 9.06 m) and a short one on the east (x 10.68..12.49,
z -7.89..1.05); two lattice columns on the east (1.21 m square, 7.55 to 8.76 m) and a lattice riser on the north
face (x -0.5..1.01) to 13.29 m with a 45-degree foot. The middle block's north face stops at 4.79 m: an open
bay, rebuilt 2 m deep with a dark back wall.
Relief: the clerestory strip windows, the garage door, the middle roof's two fan grilles (with bars), the air
handler's top vent and the west lean-to's lattice panel real recesses; standing-seam ribs on the wing roofs, ridge
flashing and gutters; plinths. The green band and wall panel lines stay paint.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

DECALS = {  # name: (u0, v0, u1, v1) on material 0 of the upscaled atlas
    "grille1": (0.479, 0.211, 0.582, 0.371), "grille2": (0.635, 0.211, 0.742, 0.371), "door": (0.215, 0.293, 0.371, 0.41),
    "lattice": (0.38, 0.762, 0.627, 0.978), "acvent": (0.6, 0.03, 0.75, 0.07),
}
D = Path(sys.argv[1])
WZ0, WZ1, MZ0, MZ1, MY = -12.33, 12.58, -11.42, 11.67, 12.08
YLO, YHI = 11.18, 12.99
BAY = 4.79


def rects(name, keep=lambda r: True):
    return [r for r in json.load(open(D / f"decal_{name}.json"))["rects"] if keep(r)]


B = Builder()
# ---- volumes
west = B.prism_z("west", [(-9.87, 0.0), (-3.82, 0.0), (-3.82, YHI), (-9.87, YLO)], WZ0, WZ1)
east = B.prism_z("east", [(4.64, 0.0), (10.68, 0.0), (10.68, YLO), (4.64, YHI)], WZ0, WZ1)
mid = B.box("mid", (-3.84, 0.0, MZ0), (4.66, MY, MZ1))
lw = B.prism_z("leanw", [(-11.68, 0.0), (-9.86, 0.0), (-9.86, 9.06), (-11.68, 8.46)], MZ0, MZ1)
B.prism_z("leane", [(10.67, 0.0), (12.49, 0.0), (12.49, 8.46), (10.67, 9.06)], -7.89, 1.05)
for k, (z0, z1) in enumerate(((7.42, 8.63), (10.45, 11.65))):
    B.prism_z(f"col{k}", [(10.67, 0.0), (11.89, 0.0), (11.89, 7.55), (10.67, 8.76)], z0, z1)
B.prism_x("riser", [(-12.33, 6.0), (-11.42, 5.1), (-10.81, 5.1), (-10.81, 13.29), (-12.33, 13.29)], -0.5, 1.01)
# the original's north face stops at 4.79 m: an open bay under the middle block, a dark back wall 2 m in
B.box("baycut", (-3.84, -0.1, MZ0 - 0.1), (4.66, BAY, MZ0 + 2.0))
B.cut(mid, "baycut")
B.box("bayback@2a2b2c", (-3.82, 0.0, MZ0 + 1.98), (4.64, BAY, MZ0 + 2.0))
B.box("baylintel@avg", (-3.82, BAY - 0.3, MZ0 - 0.12), (4.64, BAY, MZ0))
ac = B.box("ac", (-1.1, MY - 0.02, -10.81), (2.52, 13.59, -5.38), chamfer=0.05)

# ---- wing roofs: standing-seam ribs, ridge flashing, gutters
for side, (xlo, xhi) in (("w", (-9.87, -3.82)), ("e", (10.68, 4.64))):
    p0, p1 = np.array([xlo, YLO, 0.0]), np.array([xhi, YHI, 0.0])
    t = (p1 - p0) / np.linalg.norm(p1 - p0)
    n = np.array([-t[1], t[0], 0.0]) if t[0] > 0 else np.array([t[1], -t[0], 0.0])
    b = np.cross(n, t)
    L = np.linalg.norm(p1 - p0)
    for k in range(1, 8):
        z = WZ0 + (WZ1 - WZ0) * k / 8
        c = (p0 + p1) / 2 + n * 0.03
        c[2] = z
        B.obox(f"rib{side}{k}@avg", c, t, b, n, (L, 0.1, 0.1))
    sx = 1 if xlo < xhi else -1
    B.box(f"ridge{side}@avg", (min(xhi, xhi - sx * 0.3), YHI - 0.1, WZ0 - 0.05), (max(xhi, xhi - sx * 0.3), YHI + 0.12, WZ1 + 0.05))
    B.box(f"gutter{side}@avg", (min(xlo, xlo - sx * 0.2), YLO - 0.3, WZ0), (max(xlo, xlo - sx * 0.2), YLO + 0.02, WZ1))
for nm, x0, x1, z0, z1 in (("w", -11.68, -3.82, WZ0, WZ1), ("e", 4.64, 12.49, WZ0, WZ1)):
    P = 0.06
    B.box(f"pl_{nm}n", (x0 - P, 0, z0 - P), (x1 + P, 0.4, z0))
    B.box(f"pl_{nm}s", (x0 - P, 0, z1), (x1 + P, 0.4, z1 + P))
B.box("pl_ww", (-11.68 - 0.06, 0, MZ0), (-11.68, 0.4, MZ1))
B.box("pl_ee", (12.49, 0, -7.89), (12.55, 0.4, 1.05))

# ---- clerestory strip windows on the outer walls (those on the inner walls sit below the middle roof)
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    x = o["center"][0]
    if abs(x - (-9.87)) < 0.05:
        tgt = west
    elif abs(x - 10.68) < 0.05:
        tgt = east
    else:
        continue
    B.recess(tgt, o, 0.14)
    B.sill(f"wsill{k}", o, proud=0.12, thick=0.08, overhang=0.06)
    B.sill(f"whood{k}@avg", o, proud=0.1, thick=0.06, overhang=0.06, top=True)

# ---- garage door, roof fan grilles with bars, air-handler vent, lean-to lattice
for k, r in enumerate(rects("door")):
    B.recess(mid, r, 0.3)
    B.sill(f"dlintel{k}", r, proud=0.2, thick=0.15, overhang=0.15, top=True)
for nm in ("grille1", "grille2"):
    o = rects(nm)[0]
    c, w, h = o["center"], o["w"] - 0.4, o["h"] - 0.4
    B.box(f"{nm}_cut", (c[0] - w / 2, MY - 0.12, c[2] - h / 2), (c[0] + w / 2, MY + 0.2, c[2] + h / 2))
    B.cut(mid, f"{nm}_cut")  # shallow: the painted fan blades stay readable
    B.frame(f"{nm}_fr", dict(o, w=w, h=h), width=0.12, proud=0.08)
for o in rects("acvent", lambda r: r["normal"][1] > 0.9 and r["center"][1] > 13.5):
    B.recess(ac, dict(o, w=o["w"] - 0.1, h=o["h"] - 0.1), 0.12)
for k, o in enumerate(rects("lattice", lambda r: abs(r["center"][0] + 11.68) < 0.05 and r["normal"][0] < -0.9)):
    B.recess(lw, dict(o, w=o["w"] - 0.1, h=o["h"] - 0.1), 0.12)

print(B.dump())
