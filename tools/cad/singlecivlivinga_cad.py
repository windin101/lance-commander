#!/usr/bin/env python3
"""CAD rebuild of the civilian house with the barrel roof (appearance singlecivlivinga), in the original's frame.

    D=~/craft/solid/mc2/buildings/singlecivlivinga
    python3 -I tools/art/cad_building.py openings singlecivlivinga > $D/openings.json
    python3 -I tools/art/cad_building.py decal singlecivlivinga 0 0.855 0.815 0.965 0.998 > $D/decal_door.json
    python3 -I tools/cad/singlecivlivinga_cad.py $D > $D/singlecivlivinga.json
    solidcraft-cli run $D/singlecivlivinga.json --out $D/singlecivlivinga.obj
    python3 -I tools/art/cad_building.py bake singlecivlivinga $D/singlecivlivinga.obj

Measured from game/assets/objects/singlecivlivinga.glb (node Cylinder04; LitWin_* is the night overlay):
a faceted barrel house, its profile in (x, y) [-3.32..3.56 at the ground, battered walls to 1.87 m, two roof
facets to a flat crown at 4.19 m] from z = -3.5 to 3.45; a taller half-barrel (crown 4.91 m) over its -x, -z
quarter; a door porch on the +x side (2.52 m, z -3.5..-1.86); a chimney stack (4.91..6.09 m) with a hexagonal
flue to 7.38 m. Relief: the four roof windows and the two gable window strips (the texture's cut-outs) are
real recesses with sills, the roof windows get small hoods; verge boards follow the roof line at every gable;
gutters run along each eave; a plinth rings the base; the door is a 15 cm recess; the chimney has a cap
slab and a flue rim.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
B = Builder()

MAIN = [(-3.32, 0.0), (3.56, 0.0), (3.22, 1.87), (2.26, 3.36), (0.88, 4.19), (-0.65, 4.19), (-2.03, 3.36), (-2.98, 1.87)]
WING = [(-3.91, 0.0), (0.88, 0.0), (0.88, 4.91), (-0.78, 4.91), (-2.39, 3.93), (-3.51, 2.18)]
MZ0, MZ1, WZ1 = -3.5, 3.45, -0.03


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
    """A strip of width d along the outside of a roof line: the verge board's (x, y) polygon."""
    return line + offset_line(line, d)[::-1]


# ---- volumes: one joined body so every opening cuts the same solid
main = B.prism_z("main", MAIN, MZ0, MZ1)
wing = B.prism_z("wing", WING, MZ0, WZ1)
porch = B.box("porch", (2.8, 0.0, -3.5), (3.94, 2.52, -1.86))
B.join(main, [wing, porch])

# ---- openings: roof windows (15 cm, hood + sill), gable strips (20 cm, sill)
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    if abs(o["normal"][2]) > 0.9:
        B.recess(main, o, 0.20)
        B.sill(f"sill{k}", o, proud=0.10, thick=0.07, overhang=0.08)
    else:
        B.recess(main, o, 0.15)
        B.sill(f"sill{k}", o, proud=0.08, thick=0.06, overhang=0.05)
        B.sill(f"hood{k}", o, proud=0.09, thick=0.05, overhang=0.06, top=True)

# the porch door: the decal is the whole porch face; the door leaf is 0.95 x 2.1 m at its foot
door = json.load(open(D / "decal_door.json"))["rects"][0]
door = dict(door, center=[door["center"][0], 1.06, door["center"][2]], w=0.95, h=2.1)
B.recess(main, door, 0.15)
B.sill("doorhood", door, proud=0.22, thick=0.07, overhang=0.12, top=True)
B.box("doorstep@8f8b84", (3.94, 0.0, -3.3), (4.24, 0.14, -2.11))

# ---- verge boards at the gables (8 cm proud of the roof line, 14 cm deep, straddling the gable)
main_roof = [  # (3.22, 1.87) over the crown to (-2.98, 1.87)
    MAIN[2], MAIN[3], MAIN[4], MAIN[5], MAIN[6], MAIN[7]]
wing_roof = [(0.88, 4.91), (-0.78, 4.91), (-2.39, 3.93), (-3.51, 2.18)]
for k, z in enumerate((MZ0, MZ1)):
    B.prism_z(f"verge_main{k}@avg", band(main_roof, 0.08), z - 0.07, z + 0.07)
for k, z in enumerate((MZ0, WZ1)):
    B.prism_z(f"verge_wing{k}@avg", band(wing_roof, 0.08), z - 0.07, z + 0.07)

# ---- gutters along the eaves (box section, 18 x 14 cm)
B.box("gutter_mx@8a8c8e", (-3.16, 1.74, WZ1), (-2.94, 1.90, MZ1))
B.box("gutter_px@8a8c8e", (3.18, 1.74, -1.86), (3.40, 1.90, MZ1))
B.box("gutter_wing@8a8c8e", (-3.69, 2.05, MZ0), (-3.47, 2.21, WZ1))

# ---- plinth: a 25 cm base course, 4 cm proud of the battered walls
B.box("plinth_mx@avg", (-3.36, 0.0, WZ1), (-3.24, 0.25, MZ1 + 0.04))
B.box("plinth_px@avg", (3.48, 0.0, -1.86), (3.60, 0.25, MZ1 + 0.04))
B.box("plinth_wing@avg", (-3.95, 0.0, MZ0 - 0.04), (-3.83, 0.25, WZ1))
B.box("plinth_back@avg", (-3.36, 0.0, MZ1 - 0.04), (3.60, 0.25, MZ1 + 0.04))
B.box("plinth_front@avg", (-3.95, 0.0, MZ0 - 0.04), (3.98, 0.25, MZ0 + 0.04))

# ---- chimney: stack, a cap slab, the hexagonal flue with a rim
B.box("stack", (-0.53, 4.85, -3.5), (0.73, 6.09, -1.9))
B.box("stackcap@avg", (-0.61, 6.0, -3.58), (0.81, 6.14, -1.82))
cx, cz, r = 0.095, -2.70, 0.485
hexp = [(cx + r * math.cos(a * math.pi / 3), cz + r * math.sin(a * math.pi / 3)) for a in range(6)]
B.prism_y("flue", hexp, 6.1, 7.38)
rr = r + 0.06
B.prism_y("fluerim@avg", [(cx + rr * math.cos(a * math.pi / 3), cz + rr * math.sin(a * math.pi / 3)) for a in range(6)], 7.22, 7.4)

print(B.dump())
