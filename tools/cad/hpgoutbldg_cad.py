#!/usr/bin/env python3
"""CAD rebuild of the HPG outbuilding (appearance hpgoutbldg), in the original's frame.

    D=~/craft/solid/mc2/buildings/hpgoutbldg
    python3 -I tools/art/cad_building.py openings hpgoutbldg > $D/openings.json      # none: the art is opaque
    C="python3 -I tools/art/cad_building.py decal hpgoutbldg 0"                         # texture px / 512
    $C 0.0996 0.779 0.248 0.799 > $D/decal_slot1.json   # the three wall slots (and slot2/slot3 below)
    $C 0.273 0.779 0.523 0.799 > $D/decal_slot2.json ; $C 0.545 0.779 0.686 0.799 > $D/decal_slot3.json
    $C 0.779 0.436 0.877 0.484 > $D/decal_grill.json    # courtyard grille
    $C 0.10 0.473 0.186 0.557 > $D/decal_roofgrill.json # roof vent
    $C 0.705 0.03 0.922 0.135 > $D/decal_door.json      # glass doors of the courtyard block
    rbox1..4 = px (155,30,172,52) (176,30,192,52) (215,32,233,52) (290,30,314,92)    # roof equipment boxes
    panel1..4 = px (186..220|224..258|262..296|300..330, 272..313); pad = px (145,152,260,235)
    python3 -I tools/cad/hpgoutbldg_cad.py $D > $D/hpgoutbldg.json
    solidcraft-cli run $D/hpgoutbldg.json --out $D/hpgoutbldg.obj
    python3 -I tools/art/cad_building.py bake hpgoutbldg $D/hpgoutbldg.obj

Measured from game/assets/objects/hpgoutbldg.glb (58 triangles): a U-shaped block open to -z, a 1.51 m upright
plinth (x +-11.53, z -10.78..9.45, the courtyard notch x +-2.65 back to z 0.95), battered walls from it to a flat
roof at 5.86 m (top U: x -10.02..9.83, z -9.26..7.94, notch x -4.06..4.16 back to z 2.46); a 3.21 m block in the
courtyard (x -3.21..3.28, z -6.24..1.58) with the glass doors on its front; two 2.46 m side huts on the plinth
ends (x +-10.97..12.1, z 4.54..6.24).
Relief: the painted wall slots are 15 cm recesses, the courtyard grille a 12 cm recess, the doors a 30 cm recess
in the block; a ledge rings the plinth top, a coping rings the roof; pilasters on the painted wall seams; the
painted cushion panels in the courtyard are 8 cm proud; the courtyard pad a 10 cm recess; the painted roof boxes
and the roof vent are real boxes.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
B = Builder()
PL, TOP = 1.51, 5.86
BOT = [(-11.53, -10.78), (-2.65, -10.78), (-2.65, 0.95), (2.65, 0.95), (2.65, -10.78), (11.53, -10.78), (11.53, 9.45), (-11.53, 9.45)]
TOPP = [(-10.02, -9.26), (-4.06, -9.26), (-4.06, 2.46), (4.16, 2.46), (4.16, -9.26), (9.83, -9.26), (9.83, 7.94), (-10.02, 7.94)]


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def rects(name):
    return json.load(open(D / f"decal_{name}.json"))["rects"]


def proud(name, o, p, shrink=0.0):
    """A plate p proud of the face under a decal rect."""
    n, t, b = (np.array(o[k], float) for k in ("normal", "t", "b"))
    return B.obox(name, np.array(o["center"]) + n * (p / 2 - 0.02), t, b, n, (o["w"] - shrink, o["h"] - shrink, p + 0.02))


def on_slope(name, pb, pt, n, width, p):
    """A strip lying on a battered face from pb (bottom) to pt (top), p proud."""
    pb, pt, n = np.asarray(pb, float), np.asarray(pt, float), unit(n)
    b = unit(pt - pb)
    t = np.cross(b, n)
    return B.obox(name, (pb + pt) / 2 + n * (p / 2 - 0.02), t, b, n, (width, np.linalg.norm(pt - pb) + 0.02, p + 0.02))


def edge_bands(prefix, poly, y0, y1, out, inward=0.0):
    """Boxes along every edge of a counter-clockwise (x, z) polygon, from `inward` inside to `out` outside it."""
    for i in range(len(poly)):
        a, c = np.array(poly[i]), np.array(poly[(i + 1) % len(poly)])
        e = unit(c - a)
        nrm = np.array([e[1], -e[0]])  # outward for this winding (checked below)
        L = np.linalg.norm(c - a)
        mid = (a + c) / 2 + nrm * (out - inward) / 2
        t = np.array([e[0], 0, e[1]])
        n = np.array([nrm[0], 0, nrm[1]])
        B.obox(f"{prefix}{i}", (mid[0], (y0 + y1) / 2, mid[1]), t, np.cross(n, t), n, (L + 2 * out, y1 - y0, out + inward))


# winding: make sure the edge normal (e.y, -e.x) points out of the polygon
def area(poly):
    return sum(x0 * z1 - x1 * z0 for (x0, z0), (x1, z1) in zip(poly, poly[1:] + poly[:1])) / 2


assert area(BOT) > 0 and area(TOPP) > 0  # positive in (x, z): normal (ez, -ex) points outward

# ---- volumes
B.prism_y("plinth", BOT, 0.0, PL)
walls = B.loft_y("walls", BOT, PL, TOPP, TOP)
block = B.box("block", (-3.21, 0.0, -6.24), (3.28, 3.21, 1.58))
for s, (xa, xb) in enumerate(((-12.1, -10.97), (10.97, 12.1))):
    B.box(f"hut{s}", (xa, 0.0, 4.54), (xb, 2.46, 6.24), chamfer=0.06)

# ---- recesses
for k in (1, 2, 3):
    for o in rects(f"slot{k}"):
        B.recess(walls, o, 0.15)
for o in rects("grill"):
    B.recess(walls, o, 0.12)
for o in rects("door"):
    B.recess(block, o, 0.30)
    n, t, b = (np.array(o[q], float) for q in ("normal", "t", "b"))
    B.obox("doorhood", np.array(o["center"]) + b * (o["h"] / 2 + 0.08) + n * 0.12, t, b, n, (o["w"] + 0.3, 0.12, 0.28))
for o in rects("pad"):
    B.recess(block, o, 0.10)

# ---- ledge on the plinth, coping round the roof
edge_bands("ledge", BOT, PL - 0.12, PL + 0.04, 0.10)
edge_bands("coping", TOPP, TOP, TOP + 0.14, 0.03, inward=0.45)

# ---- pilasters on the painted wall seams (battered faces: bottom edge at PL, top edge at TOP)
for sx, (xb, xt) in ((1, (11.53, 9.83)), (-1, (-11.53, -10.02))):
    for z in (-4.19, 3.0):
        on_slope(f"pil_x{sx}_{z}", (xb, PL, z), (xt, TOP, z), (sx * (TOP - PL), abs(xb - xt), 0), 0.55, 0.06)
for x in (-4.15, 4.13):
    on_slope(f"pil_z{x}", (x, PL, 9.45), (x, TOP, 7.94), (0, 0.33, 0.94), 0.55, 0.06)

# ---- courtyard cushion panels, roof boxes and vent
for k in (1, 2, 3, 4):
    for m, o in enumerate(rects(f"panel{k}")):
        proud(f"panel{k}_{m}", o, 0.08, shrink=0.12)
for k, hgt in ((1, 0.25), (2, 0.25), (3, 0.25), (4, 0.35)):
    for m, o in enumerate(rects(f"rbox{k}")):
        proud(f"rbox{k}_{m}", o, hgt)
for o in rects("roofgrill"):
    proud("roofvent", o, 0.4)

print(B.dump())
