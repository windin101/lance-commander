#!/usr/bin/env python3
"""CAD rebuild of the medium factory (appearance factorymd), in the original's frame.

    D=~/craft/solid/mc2/buildings/factorymd
    python3 -I tools/art/cad_building.py openings factorymd > $D/openings.json
    python3 -I tools/art/cad_building.py decal factorymd <mat> u0 v0 u1 v1 > $D/decal_<name>.json  (see DECALS)
    python3 -I tools/cad/factorymd_cad.py $D > $D/factorymd.json
    solidcraft-cli run $D/factorymd.json --out $D/factorymd.obj
    python3 -I tools/art/cad_building.py bake factorymd $D/factorymd.obj --max-res 4096 --glass 170,176,182

Measured from game/assets/objects/factorymd.glb: a 15.49 x 25.2 m shed in two halves, the south half
(z 0..12.6) a flat-roofed block to 12.9 m, the north half (z -12.6..0) a monopitch falling from 10.06 m (west) to
7.49 m (east). Relief: the painted siding stripes real ribs, 4 cm proud trapezoids, at the stripe positions read off the
upscaled art (light-stripe peaks along each wall); the two big west doors 30 cm recesses with a frame and a hood,
their louvre slats (the cut-outs) pale glazing at the back (they read as lit slats in the art); the small north door a recess; a parapet round the high
roof, verge trims round the monopitch, a plinth; the roof units (grey box, brown plant box, hatch) real boxes.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

DECALS = {"door": (0, .39, .125, .595, .312), "sdoor": (0, .868, .218, .915, .312), "box1": (1, .186, .748, .225, .791),
          "brown": (1, .645, .733, .752, .83), "sq1": (1, .244, .89, .31, .92)}
D = Path(sys.argv[1])
X0, X1, Z0, Z1, YH = -7.74, 7.74, -12.6, 12.6, 12.9
YW, YE = 10.06, 7.49  # monopitch eaves, west and east


def slope(x):
    return YE + (X1 - x) / (X1 - X0) * (YW - YE)


def rects(name):
    return json.load(open(D / f"decal_{name}.json"))["rects"]


# light siding stripes (game m along the wall), read with a brightness-peak scan of the upscaled art
RIBS = {
    "e_lo": [-11.96, -11.34, -10.3, -9.6, -8.52, -7.72, -7.1, -5.26, -4.52, -3.86, -2.64, -2.02, -1.58, -0.7],
    "e_hi": [0.4, 0.9, 2.26, 2.84, 3.34, 4.48, 5.2, 5.82, 7.0, 7.56, 8.08, 9.94, 10.52, 12.24],
    "w_lo": [-12.24, -10.8, -10.12, -4.12, -2.92, -2.06],
    "w_hi": [0.08, 0.7, 2.06, 2.86, 9.66, 10.34, 11.54, 12.18],
    "w_top": [0.86, 2.12, 2.74, 4.26, 4.82, 5.58, 6.06, 8.14, 9.28, 12.12],
    "s": [-6.58, -5.86, -5.34, -3.88, -3.3, -2.7, -1.5, -0.76, -0.12, 1.22, 1.8, 2.38, 4.34, 4.86, 6.96, 7.56],
    "n": [-7.42, -6.72, -5.1, -4.34, -1.06, 2.28, 2.88],
    "step": [-6.6, -5.92, -4.12, -1.76, 0.04, 0.58, 3.08, 5.0],
}
B = Builder()
lo = B.prism_z("lower", [(X0, 0.0), (X1, 0.0), (X1, YE), (X0, YW)], Z0, 0.0)
hi = B.box("upper", (X0, 0.0, 0.0), (X1, YH, Z1))

doors = rects("door")
door_z = [(d["center"][2] - d["w"] / 2, d["center"][2] + d["w"] / 2, d["center"][1] + d["h"] / 2) for d in doors]
sd = rects("sdoor")[0]
P, W = 0.04, 0.08  # rib proud, half base width


def rib_x(name, x, sgn, z, y0, y1):
    """A trapezoid rib (16 cm at the wall, 8 cm on its face): sloped sides catch the light softly."""
    B.prism_y(name, [(x - sgn * 0.01, z - W), (x + sgn * P, z - W / 2), (x + sgn * P, z + W / 2), (x - sgn * 0.01, z + W)], y0, y1)


def rib_z(name, z, sgn, x, y0, y1):
    B.prism_y(name, [(x - W, z - sgn * 0.01), (x - W / 2, z + sgn * P), (x + W / 2, z + sgn * P), (x + W, z - sgn * 0.01)], y0, y1)


k = 0
for z in RIBS["e_lo"]:
    rib_x(f"rib{k}", X1, 1, z, 0.35, YE - 0.05); k += 1
for z in RIBS["e_hi"]:
    rib_x(f"rib{k}", X1, 1, z, 0.35, YH - 0.05); k += 1
for z in RIBS["w_lo"] + RIBS["w_hi"]:
    y0 = 0.35
    for a, b, top in door_z:
        if a - 0.1 < z < b + 0.1:
            y0 = top + 0.15
    rib_x(f"rib{k}", X0, -1, z, y0, (YW if z < 0 else YW) - 0.05); k += 1
for z in RIBS["w_top"]:
    rib_x(f"rib{k}", X0, -1, z, YW + 0.1, YH - 0.05); k += 1
for x in RIBS["s"]:
    rib_z(f"rib{k}", Z1, 1, x, 0.35, YH - 0.05); k += 1
for x in RIBS["n"]:
    if abs(x - sd["center"][0]) < sd["w"] / 2 + 0.1:
        continue
    rib_z(f"rib{k}", Z0, -1, x, 0.35, slope(x + W / 2) - 0.05); k += 1
for x in RIBS["step"]:
    rib_z(f"rib{k}", 0.0, -1, x, slope(x - W / 2) + 0.05, YH - 0.05); k += 1

# plinth (not across the doors)
B.box("pl_e", (X1, 0, Z0 - 0.06), (X1 + 0.06, 0.35, Z1 + 0.06))
B.box("pl_s", (X0 - 0.06, 0, Z1), (X1 + 0.06, 0.35, Z1 + 0.06))
xs = sorted([(sd["center"][0] - sd["w"] / 2, sd["center"][0] + sd["w"] / 2)])
B.box("pl_n0", (X0 - 0.06, 0, Z0 - 0.06), (xs[0][0], 0.35, Z0))
B.box("pl_n1", (xs[0][1], 0, Z0 - 0.06), (X1 + 0.06, 0.35, Z0))
cuts = sorted(door_z)
zz = [Z0 - 0.06] + [v for a, b, _ in cuts for v in (a, b)] + [Z1 + 0.06]
for i in range(0, len(zz), 2):
    B.box(f"pl_w{i}", (X0 - 0.06, 0, zz[i]), (X0, 0.35, zz[i + 1]))

# parapet round the high roof, verge trims round the monopitch
w, h = 0.22, 0.25
for i, (a, b) in enumerate((((X0, 0.0), (X1, w)), ((X0, Z1 - w), (X1, Z1)), ((X0, w), (X0 + w, Z1 - w)), ((X1 - w, w), (X1, Z1 - w)))):
    B.box(f"parapet{i}", (a[0], YH - 0.02, a[1]), (b[0], YH + h, b[1]), chamfer=0.03)
B.prism_z("verge_n@avg", [(X0 - 0.05, YW - 0.25), (X1 + 0.05, YE - 0.25), (X1 + 0.05, YE + 0.12), (X0 - 0.05, YW + 0.12)], Z0 - 0.06, Z0 + 0.12)
B.box("verge_e@avg", (X1 - 0.12, YE - 0.25, Z0 + 0.12), (X1 + 0.05, YE + 0.12, -0.0))
B.box("verge_w@avg", (X0 - 0.05, YW - 0.25, Z0 + 0.12), (X0 + 0.12, YW + 0.12, -0.0))

# doors: recess, frame, hood; the louvre cut-outs glazing at the back
DD = 0.3
for k, d in enumerate(doors):
    inner = dict(d, w=d["w"] - 0.5, h=d["h"] - 0.25, center=[d["center"][0], d["center"][1] - 0.125, d["center"][2]])
    B.recess(lo if d["center"][2] < 0 else hi, inner, DD)
    B.frame(f"dframe{k}", inner, width=0.14, proud=0.08)
    B.sill(f"dhood{k}@avg", inner, proud=0.3, thick=0.14, overhang=0.3, top=True)
for o in json.load(open(D / "openings.json"))["openings"]:
    B.recess(lo if o["center"][2] < 0 else hi, o, 0.04, surface_shift=DD)
inner = dict(sd, w=sd["w"] - 0.6, h=sd["h"] - 0.3, center=[sd["center"][0], sd["center"][1] - 0.15, sd["center"][2]])
B.recess(lo, inner, 0.15)
B.sill("sdhood@avg", inner, proud=0.2, thick=0.1, overhang=0.12, top=True)

# roof units
for nm, hgt in (("box1", 0.6), ("sq1", 0.15)):
    o = rects(nm)[0]
    c = o["center"]
    B.box(nm, (c[0] - o["w"] / 2, YH - 0.02, c[2] - o["h"] / 2), (c[0] + o["w"] / 2, YH + hgt, c[2] + o["h"] / 2), chamfer=0.04)
o = rects("brown")[0]
c = o["center"]
xa, xb = c[0] - o["w"] / 2 * 0.99, c[0] + o["w"] / 2 * 0.99
B.prism_z("brown", [(xa, slope(xa) - 0.1), (xb, slope(xb) - 0.1), (xb, slope(xa) + 0.7), (xa, slope(xa) + 0.7)],
          c[2] - o["h"] / 2, c[2] + o["h"] / 2)

print(B.dump())
