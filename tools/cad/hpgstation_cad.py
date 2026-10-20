#!/usr/bin/env python3
"""CAD rebuild of the HPG station (appearance hpgstation), in the original's frame.

    D=~/craft/solid/mc2/buildings/hpgstation
    python3 -I tools/art/cad_building.py openings hpgstation > $D/openings.json      # none: the art is opaque
    C="python3 -I tools/art/cad_building.py decal hpgstation 0"                       # rects are texture px / 1024:
    ppanel (370,607,522,748)  console (28,35,200,197)  eslot (680,406,840,415)  ezslot (750,847,912,857)
    ecush1..4 (380..414|416..450|452..487|490..524, 404..443)  kdoor (672,320,700,362)  fan (385,45,530,195)
    pipes (224,30,350,165)
    python3 -I tools/cad/hpgstation_cad.py $D > $D/hpgstation.json
    solidcraft-cli run $D/hpgstation.json --out $D/hpgstation.obj
    python3 -I tools/art/cad_building.py bake hpgstation $D/hpgstation.obj --max-res 4096

Measured from game/assets/objects/hpgstation.glb (node HPGStation, 276 triangles): a battered pedestal (plinth
1.88 m, x +-8.81, z -8.62..9, to 16.12 m at x -5.89..5.59, z +-5.51) with a battered neck to 23.25 m carrying the
dish: a nine-sided bowl (underside apex 21.75 m, rim r 17.09 at 30.57 m, inner wall from r 7.17 at 25.61 m, a feed
cone to 29.34 m) with three tapered feed struts (at 0, 120, 240 degrees, brackets 1.5 m thick) meeting near a
point at 48.56 m. East of it a low battered hall (x 15.56..32.24, z +-20.9, roof 7.04 m) carrying six equipment
units with sloped ends, a taller battered block across it (x 23.81..41.44, z -8.62..9, roof 10.88 m), a link
(x 8.81..15.56) with its roof at 6.06 m, and two door kiosks on the east plinth.
Relief: the dish, its feed cone and the painted pipes on the link roof are round (36 / 24 sides, Lee I77) instead
of the original's nine facets and flat paint; nine radial ribs and a rim band on the bowl; the pedestal's grey
panel, the block's console and the fan grille round the neck are 10-15 cm recesses, the block's slots 15 cm; the
block's cushion panels 8 cm proud; ledges ring every plinth, copings ring the roofs.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, cad  # noqa: E402

D = Path(sys.argv[1])
B = Builder()


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def rects(name):
    return json.load(open(D / f"decal_{name}.json"))["rects"]


def proud(name, o, p, shrink=0.0):
    n, t, b = (np.array(o[k], float) for k in ("normal", "t", "b"))
    return B.obox(name, np.array(o["center"]) + n * (p / 2 - 0.02), t, b, n, (o["w"] - shrink, o["h"] - shrink, p + 0.02))


def rect(x0, x1, z0, z1):
    return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]  # counter-clockwise in (x, z)


def edge_bands(prefix, poly, y0, y1, out, inward=0.0, skip=()):
    for i in range(len(poly)):
        if i in skip:
            continue
        a, c = np.array(poly[i]), np.array(poly[(i + 1) % len(poly)])
        e = unit(c - a)
        nrm = np.array([e[1], -e[0]])
        mid = (a + c) / 2 + nrm * (out - inward) / 2
        t, n = np.array([e[0], 0, e[1]]), np.array([nrm[0], 0, nrm[1]])
        B.obox(f"{prefix}{i}", (mid[0], (y0 + y1) / 2, mid[1]), t, np.cross(n, t), n, (np.linalg.norm(c - a) + 2 * out, y1 - y0, out + inward))


def ring(r, n=36, phase=0.0, cx=0.0, cz=0.0):
    return [(cx + r * math.cos(phase + 2 * math.pi * k / n), cz + r * math.sin(phase + 2 * math.pi * k / n)) for k in range(n)]


def battered(name, bot, y0, top, y1, plinth_y0=0.0):
    B.prism_y(f"{name}_plinth", bot, plinth_y0, y0)
    return B.loft_y(name, bot, y0, top, y1)


# ---- pedestal, neck, link, hall, block, units, kiosks
P_BOT, P_TOP = rect(-8.81, 8.81, -8.62, 9.0), rect(-5.89, 5.59, -5.51, 5.51)
ped = battered("pedestal", P_BOT, 1.88, P_TOP, 16.12)
B.loft_y("neck", rect(-2.25, 2.25, -3.0, 3.0), 16.12, rect(-0.75, 0.75, -2.25, 2.25), 23.4)
L_BOT, L_TOP = rect(8.81, 15.56, -6.83, 6.85), rect(7.69, 17.02, -5.01, 4.8)
link = battered("link", L_BOT, 1.83, L_TOP, 6.06)
H_BOT, H_TOP = rect(15.56, 32.24, -20.9, 20.9), rect(17.37, 30.19, -19.09, 19.09)
hall = battered("hall", H_BOT, 1.82, H_TOP, 7.04)
E_BOT, E_TOP = rect(23.81, 41.44, -8.62, 9.0), rect(26.74, 38.22, -5.51, 5.51)
blk = battered("block", E_BOT, 1.88, E_TOP, 10.88)
for k, (xa, xb) in enumerate(((19.09, 21.14), (23.11, 25.16), (26.86, 28.91))):
    for s in (1, -1):
        prof = [(11.61, 7.0), (17.74, 7.0), (15.11, 9.23), (11.61, 9.23)]
        B.prism_x(f"unit{k}{'pm'[s < 0]}", [(s * z, y) for z, y in (prof if s > 0 else prof[::-1])], xa, xb)
        B.prism_x(f"unitcap{k}{'pm'[s < 0]}", [(s * z, y) for z, y in ([(11.51, 9.2), (15.21, 9.2), (15.21, 9.33), (11.51, 9.33)] if s > 0 else
                                                                       [(11.51, 9.33), (15.21, 9.33), (15.21, 9.2), (11.51, 9.2)])], xa - 0.08, xb + 0.08)
for s, (za, zb) in enumerate(((-17.5, -15.45), (15.45, 17.5))):
    B.box(f"kiosk{s}", (31.74, 0.0, za), (33.11, 2.95, zb), chamfer=0.05)

# ---- the dish: round bowl (36 sides), the vertex radii of the nine-sided original pulled in 3 %
K = 0.97
B.loft_y("dish_under", ring(0.3), 21.75, ring(11.58 * K), 25.61)
dish = B.loft_y("dish", ring(11.58 * K), 25.61, ring(17.09 * K), 30.57)
slope = (17.09 - 7.17) * K / (30.57 - 25.61)
B.loft_y("bowl_cut", ring(7.17 * K - 0.25 * slope), 25.36, ring(7.17 * K + 0.85 * slope + 0.0), 31.42)
B.cut(dish, "bowl_cut")
B.loft_y("feed_cone", ring(7.17 * K + 0.1, 24), 25.3, ring(0.35, 24), 29.34)
# rim band and nine radial ribs on the facet seams (vertices at 20 + 40 k degrees)
B.loft_y("rim_band", ring(17.09 * K + 0.12), 30.27, ring(17.09 * K + 0.12), 30.75)
B.loft_y("rim_cut", ring(17.09 * K - 0.3), 30.2, ring(17.09 * K - 0.3), 30.8)
B.cut("rim_band", "rim_cut")
for k in range(9):
    a = math.radians(20 + 40 * k)
    d = np.array([math.cos(a), 0.0, -math.sin(a)])  # game (x, z) = (r cos a, -r sin a) mirrors fine: nine-fold
    p0 = np.array([0.0, 25.61, 0.0]) + d * 7.17 * K
    p1 = np.array([0.0, 30.57, 0.0]) + d * 17.09 * K
    b = unit(p1 - p0)
    t = unit(np.cross(b, [0.0, 1.0, 0.0]))
    n = np.cross(t, b)
    B.obox(f"dishrib{k}", (p0 + p1) / 2 + n * 0.05, t, b, n, (0.3, np.linalg.norm(p1 - p0) - 0.4, 0.2))

# ---- feed struts: a bracket plate and a tapered strut per arm, built at 0 degrees and turned about the axis
BRACKET = [(6.75, 24.56), (17.81, 26.81), (18.56, 32.81), (17.06, 32.06), (16.31, 28.31), (12.0, 27.75)]
for k, ang in enumerate((0, 120, 240)):
    br = B.prism_z(f"bracket{k}", BRACKET, -0.75, 0.75)
    e = unit(np.array([18.56 - 17.06, 32.81 - 32.06]))
    secs = []
    for (ox, oy), u0, u1, hw in (((17.06, 32.06), 0.0, 1.677, 0.75), ((3.94 - e[0] * 0.15, 48.56 - e[1] * 0.15), 0.0, 0.3, 0.22)):
        B.n_sk += 1
        sk = f"sk{B.n_sk}"
        B.c("sketch.create", plane={"origin": cad((ox, oy, 0.0)), "x_dir": [round(e[0], 6), 0, round(e[1], 6)], "y_dir": [0, 1, 0]}, name=sk)
        B.c("sketch.line", points=[[u0 * 1000, -hw * 1000], [u1 * 1000, -hw * 1000], [u1 * 1000, hw * 1000], [u0 * 1000, hw * 1000]], closed=True)
        B.c("sketch.finish")
        secs.append({"sketch": sk})
    B.c("solid.loft", sections=secs, body_name=f"strut{k}", operation="new")
    if ang:
        B.c("solid.move", bodies=[br, f"strut{k}"], axis=[0, 0, 1], angle=f"{ang} deg")

# ---- pipes on the link roof: two 24-sided cylinders along x, half sunk
for k, z in enumerate((-1.89, 1.81)):
    B.prism_x(f"pipe{k}", [(z + 1.25 * math.cos(2 * math.pi * j / 24), 6.31 + 1.25 * math.sin(2 * math.pi * j / 24)) for j in range(24)][::-1], 8.2, 16.7)

# ---- recesses and plates
for o in rects("ppanel"):
    if o["center"][0] < 10:
        B.recess(ped, o, 0.15)
for o in rects("console"):
    B.recess(blk, dict(o, w=o["w"] - 0.2, h=o["h"] - 0.2), 0.10)
for nm in ("eslot", "ezslot"):
    for o in rects(nm):
        B.recess(blk, o, 0.15)
for k in (1, 2, 3, 4):
    for o in rects(f"ecush{k}"):
        proud(f"ecush{k}", o, 0.08, shrink=0.12)
for s, o in enumerate(rects("kdoor")):
    B.recess(f"kiosk{0 if o['center'][2] < 0 else 1}", dict(o, w=min(o["w"], 1.5), h=o["h"] - 0.1), 0.08)
B.prism_y("fan_cut", ring(4.0, 32, cx=-0.23, cz=-0.07), 16.02, 16.3)
B.cut(ped, "fan_cut")

# ---- ledges and copings
edge_bands("pledge", P_BOT, 1.76, 1.92, 0.10, skip=(1,))
edge_bands("hledge", H_BOT, 1.70, 1.86, 0.10)
edge_bands("eledge", E_BOT, 1.76, 1.92, 0.10, skip=(3,))
edge_bands("pcope", P_TOP, 16.12, 16.26, 0.04, inward=0.4)
edge_bands("hcope", H_TOP, 7.04, 7.18, 0.04, inward=0.4)
edge_bands("ecope", E_TOP, 10.88, 11.02, 0.04, inward=0.4)

print(B.dump())
