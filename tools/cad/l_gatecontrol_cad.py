#!/usr/bin/env python3
"""CAD rebuild of the arched gate control building (appearance l_gatecontrol), in the original's frame.

    D=~/craft/solid/mc2/buildings/l_gatecontrol
    python3 -I tools/art/cad_building.py openings l_gatecontrol > $D/openings.json
    python3 -I tools/cad/l_gatecontrol_cad.py $D > $D/l_gatecontrol.json
    solidcraft-cli run $D/l_gatecontrol.json --out $D/l_gatecontrol.obj
    python3 -I tools/art/cad_building.py bake l_gatecontrol $D/l_gatecontrol.obj --keep base Dish LOS_Ant

Measured from game/assets/objects/l_gatecontrol.glb (faces grouped by plane): a hall (x -11.18..-0.06,
z -12.57..0.43) whose roof is flat from the east wall to x -4.34 at 8.68 m and then a faceted arch down to the
west eave (-11.16, 4.02): the facets lie on a circle of radius 7.32 m about (-4.34, 1.36), rebuilt here as a true
curve (24 segments, issue I77); the west wall stands 1 m back under the eave between three legs; a connector with
a sloped roof (to 4.02 m) joins the tower (x 2.93..9.66, z -12.33..-4.65, chamfered front corners) whose front
batters back from 4.05 m to 9.05 m, a glazed cab flaring out to 11.14 m and a bevelled roof to 11.97 m; a
quarter-round lean-to (radius 2.71 m about (9.66, 1.34)) on the tower's +x side. The dish, its base and the
masts are kept verbatim. Relief: every cut-out window or slot is a recess (15-20 cm, sills under the hall's tall
windows), the painted white rims of the arch (both gables and the bay joint at z -6.07) are raised 8 cm ribs, the
tower roof field is a 8 cm recess inside its rim, a ledge rings the tower under the cab.
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


def ccw(poly):
    a = sum(x0 * -z1 - x1 * -z0 for (x0, z0), (x1, z1) in zip(poly, poly[1:] + poly[:1]))
    return poly if a > 0 else poly[::-1]


def inset(poly, d):
    q = [(x, -z) for x, z in ccw(poly)]
    n = len(q)
    lines = []
    for i in range(n):
        (x0, y0), (x1, y1) = q[i], q[(i + 1) % n]
        ex, ey = x1 - x0, y1 - y0
        L = math.hypot(ex, ey)
        lines.append(((x0 - ey / L * d, y0 + ex / L * d), (ex, ey)))
    out = []
    for i in range(n):
        (pp, e), (qq, f) = lines[i - 1], lines[i]
        det = e[0] * -f[1] + f[0] * e[1]
        t = ((qq[0] - pp[0]) * -f[1] + f[0] * (qq[1] - pp[1])) / det
        out.append((pp[0] + e[0] * t, -(pp[1] + e[1] * t)))
    return out


# ---- hall: flat roof east, true arch west
CX, CY, RAD = -4.34, 1.36, 7.32
A1 = math.atan2(4.02 - CY, -11.16 - CX)


def roof(off, k=24):
    """The roof line from the east wall to the west eave, offset outward by off."""
    pts = [(-0.06, 8.68 + off)]
    for i in range(k + 1):
        a = math.pi / 2 + (A1 - math.pi / 2) * i / k
        pts.append((CX + (RAD + off) * math.cos(a), CY + (RAD + off) * math.sin(a)))
    return pts


prof = [(-10.17, 0.0), (-0.06, 0.0)] + roof(0.0) + [(-10.17, 4.02)]
hall = B.prism_z("hall", prof, -12.57, 0.43)
for k, (z0, z1) in enumerate([(-12.57, -11.51), (-6.71, -5.43), (-0.64, 0.43)]):
    B.box(f"leg{k}", (-11.18, 0.0, z0), (-10.17, 4.02, z1))
rib = roof(0.08) + roof(-0.02)[::-1]
for k, (z0, z1) in enumerate([(-12.60, -12.27), (-6.27, -5.87), (0.13, 0.46)]):
    B.prism_z(f"rib{k}", rib, z0, z1)

# ---- connector and tower
B.prism_z("connector", [(-0.07, 0.0), (2.93, 0.0), (2.93, 2.64), (-0.07, 4.02)], -11.51, -6.71)
p_lo = [(2.93, -12.33), (9.66, -12.33), (9.66, -6.07), (8.91, -4.65), (3.69, -4.65), (2.93, -6.07)]
p_up = [(2.93, -12.33), (9.66, -12.33), (9.66, -6.90), (8.91, -5.72), (3.69, -5.72), (2.93, -6.90)]
p_cab = [(2.07, -12.33), (10.49, -12.33), (10.49, -6.20), (9.54, -4.43), (3.02, -4.43), (2.07, -6.20)]
p_roof = [(2.93, -12.33), (9.66, -12.33), (9.66, -7.42), (8.91, -6.00), (3.69, -6.00), (2.93, -7.42)]
t_lo = B.prism_y("tower_lo", p_lo, 0.0, 4.05)
t_up = B.loft_y("tower_up", p_lo, 4.05, p_up, 9.05)
cab = B.loft_y("cab", p_up, 9.05, p_cab, 11.14)
rf = B.loft_y("roof", p_cab, 11.14, p_roof, 11.97)
B.cut(rf, B.prism_y("roof_field", inset(p_roof, 0.45), 11.89, 12.1))
ring = [((2.80, 8.90, -12.45), (2.94, 9.12, -6.9)), ((9.65, 8.90, -12.45), (9.79, 9.12, -6.9)),
        ((3.69, 8.90, -5.86), (8.91, 9.12, -5.70))]
for k, (lo, hi) in enumerate(ring):
    B.box(f"ledge{k}", lo, hi)
# quarter-round lean-to on +x
lean = [(9.66, 0.0), (12.37, 0.0)] + [(9.66 + 2.71 * math.cos(a), 1.34 + 2.71 * math.sin(a))
                                       for a in np.linspace(0, math.pi / 2, 17)]
B.prism_z("leanto", lean, -12.34, -6.07)

# ---- windows
SOLIDS = [((-11.18, 0, -12.57), (-0.06, 8.68, 0.43)), ((2.93, 0, -12.33), (9.66, 9.05, -4.65)),
          ((-0.07, 0, -11.51), (2.93, 2.6, -6.71)), ((9.66, 0, -12.34), (12.37, 1.3, -6.07))]


def hidden(o):
    p = np.array(o["center"]) + np.array(o["normal"]) * 0.15
    return any(np.all(p > np.array(lo) + 0.02) and np.all(p < np.array(hi) - 0.02) for lo, hi in SOLIDS)


def owner(o):
    x, y, z = o["center"]
    if x < -0.03:
        return hall
    if y > 11.13:
        return rf
    if y > 9.05:
        return cab
    if y > 4.05:
        return t_up
    return t_lo


for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    if hidden(o):
        continue
    tall = o["h"] > 2.0
    B.recess(owner(o), o, 0.2 if tall else 0.12)
    if tall and abs(o["normal"][1]) < 0.1:
        B.sill(f"sill{k}", o, proud=0.1, thick=0.07, overhang=0.06)

print(B.dump())
