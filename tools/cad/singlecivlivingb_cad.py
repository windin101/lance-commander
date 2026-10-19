#!/usr/bin/env python3
"""CAD rebuild of the long civilian house with the barrel roof (appearance singlecivlivingb), in the original's frame.
The singlecivlivinga build (tools/cad/singlecivlivinga_cad.py) on this model's measurements; the same texture sheet.

    D=~/craft/solid/mc2/buildings/singlecivlivingb
    python3 -I tools/art/cad_building.py openings singlecivlivingb > $D/openings.json
    python3 -I tools/art/cad_building.py decal singlecivlivingb 0 0.855 0.815 0.965 0.998 > $D/decal_door.json
    python3 -I tools/cad/singlecivlivingb_cad.py $D > $D/singlecivlivingb.json
    solidcraft-cli run $D/singlecivlivingb.json --out $D/singlecivlivingb.obj
    python3 -I tools/art/cad_building.py bake singlecivlivingb $D/singlecivlivingb.obj

Measured from game/assets/objects/singlecivlivingb.glb (node Cylinder04; LitWin_* is the night overlay): a faceted
barrel house, its profile in (x, y) [-3.47..3.61 at the ground, battered walls to 1.84 m, two roof facets to a flat
crown at 4.14 m] from z = -11.1 to 2.62; a taller half-barrel (crown 4.84 m) over its -x side from z -7.67 to -0.81;
a porch on the +x side (x 2.83..4.0, z -5.84..-2.63, 2.48 m) painted with two doors; a chimney stack on the wing's
crown (x -0.6..0.7, z -5.82..-2.66, 4.84..6.01 m) with two hexagonal flues (r 0.48 m) to 7.29 m.
Relief: the roof windows and the two gable window strips (the texture's cut-outs) are real recesses with sills, the
roof windows get small hoods (two cut-outs on the main roof hidden inside the wing are skipped); verge boards follow
the roof line at every gable; gutters run along each eave; a plinth rings the base; both porch doors are 15 cm
recesses under a hood with a step; the chimney has a cap slab and each flue a rim.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
B = Builder()

MAIN = [(-3.47, 0.0), (3.61, 0.0), (3.26, 1.84), (2.28, 3.32), (0.86, 4.14), (-0.72, 4.14), (-2.14, 3.32), (-3.12, 1.84)]
WING = [(-4.07, 0.0), (0.86, 0.0), (0.86, 4.84), (-0.85, 4.84), (-2.51, 3.88), (-3.66, 2.15)]
MZ0, MZ1, WZ0, WZ1 = -11.1, 2.62, -7.67, -0.81
PX0, PX1, PZ0, PZ1, PH = 2.83, 4.0, -5.84, -2.63, 2.48


def offset_line(pts, d):
    """Offset an open polyline (x, y) to its left by d (outward for a counter-clockwise roof line), mitred."""
    segs = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        ex, ey = x1 - x0, y1 - y0
        L = math.hypot(ex, ey)
        segs.append((ex / L, ey / L))
    out = []
    for i, (x, y) in enumerate(pts):
        if i == 0:
            nx, ny = segs[0][1], -segs[0][0]
            out.append((x + nx * d, y + ny * d))
        elif i == len(pts) - 1:
            nx, ny = segs[-1][1], -segs[-1][0]
            out.append((x + nx * d, y + ny * d))
        else:
            (ax, ay), (bx, by) = segs[i - 1], segs[i]
            n1 = (ay, -ax)
            n2 = (by, -bx)
            mx, my = n1[0] + n2[0], n1[1] + n2[1]
            m = math.hypot(mx, my)
            mx, my = mx / m, my / m
            k = d / (mx * n1[0] + my * n1[1])
            out.append((x + mx * k, y + my * k))
    return out


def band(line, d):
    return line + offset_line(line, d)[::-1]


def in_wing(c):
    """Is a point inside the wing's volume (convex profile, z range)?"""
    if not (WZ0 < c[2] < WZ1):
        return False
    P = WING
    s = 0
    for (x0, y0), (x1, y1) in zip(P, P[1:] + P[:1]):
        cr = (x1 - x0) * (c[1] - y0) - (y1 - y0) * (c[0] - x0)
        if cr < -1e-6:
            return False
    return True


# ---- volumes: one joined body so every opening cuts the same solid
main = B.prism_z("main", MAIN, MZ0, MZ1)
wing = B.prism_z("wing", WING, WZ0, WZ1)
porch = B.box("porch", (PX0, 0.0, PZ0), (PX1, PH, PZ1))
B.join(main, [wing, porch])

# ---- openings: gable strips (20 cm, sill), roof windows (15 cm, hood + sill)
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    if in_wing(o["center"]):
        continue
    if abs(o["normal"][2]) > 0.9:
        B.recess(main, o, 0.20)
        B.sill(f"sill{k}", o, proud=0.10, thick=0.07, overhang=0.08)
    else:
        B.recess(main, o, 0.15)
        B.sill(f"sill{k}", o, proud=0.08, thick=0.06, overhang=0.05)
        B.sill(f"hood{k}", o, proud=0.09, thick=0.05, overhang=0.06, top=True)

# the porch doors: each decal is half the porch face; the door leaf is 0.95 x 2.1 m at its foot
for k, door in enumerate(json.load(open(D / "decal_door.json"))["rects"]):
    door = dict(door, center=[door["center"][0], 1.06, door["center"][2]], w=0.95, h=2.1)
    B.recess(main, door, 0.15)
    B.sill(f"doorhood{k}", door, proud=0.22, thick=0.07, overhang=0.12, top=True)
    z = door["center"][2]
    B.box(f"doorstep{k}@8f8b84", (PX1, 0.0, z - 0.6), (PX1 + 0.3, 0.14, z + 0.6))

# ---- verge boards at the gables
main_roof = MAIN[2:]
wing_roof = WING[2:]
for k, z in enumerate((MZ0, MZ1)):
    B.prism_z(f"verge_main{k}@avg", band(main_roof, 0.08), z - 0.07, z + 0.07)
for k, z in enumerate((WZ0, WZ1)):
    B.prism_z(f"verge_wing{k}@avg", band(wing_roof, 0.08), z - 0.07, z + 0.07)

# ---- gutters along the eaves (box section, 22 x 16 cm), broken where the wing and the porch meet the eave
for k, (z0, z1) in enumerate(((MZ0, WZ0), (WZ1, MZ1))):
    B.box(f"gutter_mx{k}@8a8c8e", (-3.30, 1.71, z0), (-3.08, 1.87, z1))
for k, (z0, z1) in enumerate(((MZ0, PZ0), (PZ1, MZ1))):
    B.box(f"gutter_px{k}@8a8c8e", (3.22, 1.71, z0), (3.44, 1.87, z1))
B.box("gutter_wing@8a8c8e", (-3.84, 2.02, WZ0), (-3.62, 2.18, WZ1))

# ---- plinth: a 25 cm base course, 4 cm proud
for k, (z0, z1) in enumerate(((MZ0 - 0.04, WZ0), (WZ1, MZ1 + 0.04))):
    B.box(f"plinth_mx{k}@avg", (-3.51, 0.0, z0), (-3.39, 0.25, z1))
for k, (z0, z1) in enumerate(((MZ0 - 0.04, PZ0), (PZ1, MZ1 + 0.04))):
    B.box(f"plinth_px{k}@avg", (3.53, 0.0, z0), (3.65, 0.25, z1))
B.box("plinth_wing@avg", (-4.11, 0.0, WZ0), (-3.99, 0.25, WZ1))
B.box("plinth_back@avg", (-3.51, 0.0, MZ1 - 0.04), (3.65, 0.25, MZ1 + 0.04))
B.box("plinth_front@avg", (-3.51, 0.0, MZ0 - 0.04), (3.65, 0.25, MZ0 + 0.04))
B.box("plinth_porch@avg", (PX1 - 0.04, 0.0, PZ0 - 0.04), (PX1 + 0.04, 0.25, PZ1 + 0.04))

# ---- chimney: stack, a cap slab, two hexagonal flues with rims
B.box("stack", (-0.6, 4.78, -5.82), (0.7, 6.01, -2.66))
B.box("stackcap@avg", (-0.68, 5.92, -5.9), (0.78, 6.06, -2.58))
cx, r = -0.06, 0.48
for k, cz in enumerate((-5.08, -3.4)):
    B.prism_y(f"flue{k}", [(cx + r * math.cos(a * math.pi / 3), cz + r * math.sin(a * math.pi / 3)) for a in range(6)], 6.02, 7.29)
    rr = r + 0.06
    B.prism_y(f"fluerim{k}@avg", [(cx + rr * math.cos(a * math.pi / 3), cz + rr * math.sin(a * math.pi / 3)) for a in range(6)], 7.13, 7.31)

print(B.dump())
