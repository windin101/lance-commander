#!/usr/bin/env python3
"""CAD rebuild of the vehicle hangar (appearance vehiclehangar), in the original's frame.

    D=~/craft/solid/mc2/buildings/vehiclehangar
    python3 -I tools/art/cad_building.py openings vehiclehangar > $D/openings.json
    python3 -I tools/art/cad_building.py decal vehiclehangar 0 <u0 v0 u1 v1> > $D/decal_<name>.json   (see DECALS)
    python3 -I tools/cad/vehiclehangar_cad.py $D > $D/vehiclehangar.json
    solidcraft-cli run $D/vehiclehangar.json --out $D/vehiclehangar.obj
    python3 -I tools/art/cad_building.py bake vehiclehangar $D/vehiclehangar.obj

Measured from game/assets/objects/vehiclehangar.glb: a hall (x -11.335..9.729, z -7.609..5.597) with 7.21 m walls
and a mansard roof (slopes to a flat at 9.527 m, z -5.709..3.865); a lean-to on +z (x -10.105..9.21, to z 10.478,
3.63 m eaves sloping up to a 6.272 m flat); a lean-to on -z (x -1.489..8.082, to z -12.274, the same section);
a 3.66 m flat-roofed store beside it (x -9.723..-1.294, z -11.448..-7.687); and a duct (x 4.184..5.915) that
climbs from the -z lean-to over the hall's eaves to 11.9 m and back down onto the hall roof.
Relief: the painted standing seams of every roof slope are real 8 cm ribs, on the seam positions read from the
texture (the dark lines, mapped through the original's UVs); the two "13" roller doors are 35 cm recesses
under a header; the two side doors 18 cm recesses; the cut-out windows 15 cm recesses with sills; the painted
skylight strips on the three flat roofs are 20 cm curbs.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

DECALS = {"rollerdoor": (0, 0.566, 0.30, 0.934, 0.556), "door": (0, 0.705, 0.13, 0.758, 0.215),
          "skylight": (0, 0.244, 0.02, 0.612, 0.1)}
# dark seam lines on the roof slopes (x, m), from the texture through the original's UVs
SEAMS_HALL_BACK = [-10.66, -9.61, -8.66, -7.81, -6.76, -5.81, -4.96, -3.91, -3.01, -1.96, -0.96, -0.21, 0.59, 1.34, 2.14,
                   2.89, 3.79, 4.54, 5.24, 5.99, 6.89, 8.09, 8.94]
SEAMS_HALL_FRONT = [-10.61, -9.56, -8.71, -7.61, -6.76, -5.76, -4.76, -3.86, -2.76, -1.91, -1.01, -0.01, 0.99, 2.04, 3.04,
                    3.99, 4.99, 5.89, 6.94, 7.89, 8.94]
SEAMS_LEAN_FRONT = [-9.84, -9.24, -8.49, -7.64, -6.89, -6.09, -5.29, -4.44, -3.64, -2.84, -2.04, -1.24, -0.54, 0.31, 1.11,
                    1.91, 2.71, 3.51, 4.36, 5.16, 5.96, 6.71, 7.56, 8.31, 8.91]
D = Path(sys.argv[1])
B = Builder()


def rects(name):
    return json.load(open(D / f"decal_{name}.json"))["rects"]


HX0, HX1 = -11.335, 9.729
hall = B.prism_x("hall", [(-7.609, 0.0), (5.597, 0.0), (5.597, 7.208), (3.865, 9.527), (-5.709, 9.527), (-7.609, 7.208)], HX0, HX1)
lean_f = B.prism_x("lean_front", [(5.519, 0.0), (10.478, 0.0), (10.478, 3.63), (7.984, 6.272), (5.519, 6.272)], -10.105, 9.21)
lean_b = B.prism_x("lean_back", [(-12.274, 0.0), (-7.644, 0.0), (-7.644, 6.272), (-10.099, 6.272), (-12.274, 3.63)], -1.489, 8.082)
store = B.box("store", (-9.723, 0.0, -11.448), (-1.294, 3.663, -7.687))
B.prism_x("duct", [(-9.736, 6.2), (-8.024, 6.2), (-8.024, 9.1), (-7.469, 10.318), (-5.32, 10.323), (-4.909, 9.567),
                   (-3.076, 9.541), (-4.53, 11.873), (-8.255, 11.895), (-9.736, 9.1)], 4.184, 5.915)


def ribs(name, xs, p0, p1, normal):
    """Standing seams: 8 cm ribs from p0 to p1 (z, y) on a slope, at each x."""
    a, b_ = np.array([0.0, p0[1], p0[0]]), np.array([0.0, p1[1], p1[0]])
    d = b_ - a
    L = float(np.linalg.norm(d))
    b = d / L
    t = np.array([1.0, 0.0, 0.0])
    n = np.cross(t, b)
    if n @ np.array(normal) < 0:
        t = -t
        n = -n
    for k, x in enumerate(xs):
        c = (a + b_) / 2 + n * 0.03 - b * 0.08  # stops 16 cm short of the ridge, so no end shows above it
        c[0] = x
        B.obox(f"{name}{k}", c, t, b, n, (0.09, L - 0.2, 0.1))


ribs("rib_hb", SEAMS_HALL_BACK, (-7.609, 7.208), (-5.709, 9.527), (0, 0.63, -0.77))
ribs("rib_hf", SEAMS_HALL_FRONT, (5.597, 7.208), (3.865, 9.527), (0, 0.6, 0.8))
ribs("rib_lf", SEAMS_LEAN_FRONT, (10.478, 3.63), (7.984, 6.272), (0, 0.69, 0.73))
ribs("rib_lb", [x for x in SEAMS_HALL_BACK if -1.35 < x < 7.95 and not 4.0 < x < 6.1], (-12.274, 3.63), (-10.099, 6.272),
     (0, 0.64, -0.77))

# roller doors: 35 cm recesses up to a 30 cm header, with a hood over them
for k, o in enumerate(rects("rollerdoor")):
    top = 6.9
    c = list(o["center"])
    c[1] = top / 2 - 0.02
    od = dict(o, center=c, w=10.0, h=top + 0.04)
    B.recess(hall, od, 0.35)
    B.sill(f"hood{k}", dict(od, h=top - 0.04 + 0.04), proud=0.25, thick=0.12, overhang=0.15, top=True)

for k, o in enumerate(rects("door")):
    tgt = lean_b if o["center"][0] > 0 else lean_f
    c = list(o["center"])
    c[1] = 1.15
    B.recess(tgt, dict(o, center=c, w=1.1, h=2.3), 0.18)
    B.sill(f"doorhood{k}", dict(o, center=c, w=1.1, h=2.3), proud=0.3, thick=0.08, overhang=0.15, top=True)

for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    c = np.array(o["center"])
    if c[2] > 10.4 or (c[2] > 5.5 and abs(c[0]) > 9):
        tgt = lean_f
    elif -9.8 < c[0] < -1.3 and c[2] < -7.6:
        tgt = store
    else:
        tgt = lean_b
    B.recess(tgt, o, 0.15)
    B.sill(f"sill{k}", o, proud=0.08, thick=0.07, overhang=0.06)

# skylight curbs on the flat roofs
for k, o in enumerate(rects("skylight")):
    c = np.array(o["center"])
    hw, hd = o["w"] / 2 - 0.25, o["h"] / 2 - 0.2
    if c[0] > 3.0 and c[2] < -7:   # the -z lean-to's flat: keep clear of the duct
        hw -= 0.0
    B.box(f"skylight{k}", (c[0] - hw, c[1], c[2] - hd), (c[0] + hw, c[1] + 0.2, c[2] + hd), chamfer=0.04)

print(B.dump())
