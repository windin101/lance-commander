#!/usr/bin/env python3
"""CAD rebuild of the industrial plant (appearance industrialplant), in the original's frame.

    D=~/craft/solid/mc2/buildings/industrialplant
    python3 -I tools/art/cad_building.py openings industrialplant > $D/openings.json
    python3 -I tools/art/cad_building.py decal industrialplant 0 u0 v0 u1 v1 > $D/decal_<name>.json  (see DECALS)
    python3 -I tools/cad/industrialplant_cad.py $D > $D/industrialplant.json
    solidcraft-cli run $D/industrialplant.json --out $D/industrialplant.obj
    python3 -I tools/art/cad_building.py bake industrialplant $D/industrialplant.obj

Measured from game/assets/objects/industrialplant.glb: a brick tower (x -1.39..7.2, z -10.18..-1.45) with walls
to 18.93 m and a 1.45 m 45-degree chamfer to a flat roof at 20.38 m; a low brick hall (x -9.54..3.56,
z -7.27..8.75) with walls to 5.24 m and a 1.46 m chamfer to a roof at 6.7 m; a square elbow duct (z -4.79..-2.46)
rising from the hall roof at x -5.32..-3.13 to 15.87 m and turning into the tower wall above 13.1 m.
The duct stays square (it is an HVAC trunk, not a pipe); its bends are smoothed to six segments. Relief: the hall's
two-pane windows and doors and the tower's louvre band real recesses with sills, the tower's roof grate a recess
under a coping, a raised roof fan housing with two round fan wells, a roof vent, flanges on the duct, plinths.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, box_edges  # noqa: E402

DECALS = {  # name: (u0, v0, u1, v1) on material 0 of the upscaled atlas
    "grate": (0.342, 0.098, 0.488, 0.244), "banner": (0.688, 0.307, 0.953, 0.352), "fanbox": (0.176, 0.342, 0.381, 0.586),
    "fan1": (0.195, 0.36, 0.267, 0.432), "fan2": (0.281, 0.36, 0.353, 0.432), "rvent": (0.088, 0.523, 0.133, 0.576),
    "door": (0.225, 0.762, 0.312, 0.83),
}
D = Path(sys.argv[1])
TX0, TX1, TZ0, TZ1, TY, TCH = -1.39, 7.2, -10.18, -1.45, 18.93, 1.45
HX0, HX1, HZ0, HZ1, HY, HCH = -9.54, 3.56, -7.27, 8.75, 5.24, 1.46
DZ0, DZ1 = -4.79, -2.46


def rects(name, keep=lambda r: True):
    return [r for r in json.load(open(D / f"decal_{name}.json"))["rects"] if keep(r)]


def ring(cx, cz, r, k=24):
    return [(cx + r * math.cos(2 * math.pi * (i + 0.5) / k), cz + r * math.sin(2 * math.pi * (i + 0.5) / k)) for i in range(k)]


def arc(cx, cy, rx, ry, a0, a1, n=6):
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n)))
            for i in range(n + 1)]


B = Builder()
# ---- volumes
tower = B.box("tower", (TX0, 0.0, TZ0), (TX1, TY + TCH, TZ1), chamfer=TCH, chamfer_edges=box_edges((TX0, 0, TZ0), (TX1, TY + TCH, TZ1)))
hall = B.box("hall", (HX0, 0.0, HZ0), (HX1, HY + HCH, HZ1), chamfer=HCH, chamfer_edges=box_edges((HX0, 0, HZ0), (HX1, HY + HCH, HZ1)))
# duct side profile (x, y): outer bend about (-3.13, 13.4), inner bend about (-1.39, 12.52)
prof = [(-5.32, 6.68), (-3.13, 6.68)] + arc(-1.39, 12.52, 1.74, 0.58, 180, 90) + [(TX0 + 0.02, 13.1), (TX0 + 0.02, 15.87)] \
    + arc(-3.13, 13.4, 2.19, 2.47, 90, 180)[:-1]
B.prism_z("duct", prof, DZ0, DZ1)
for k, y in enumerate((6.7, 9.6, 12.0)):
    B.box(f"dflange{k}@avg", (-5.42, y, DZ0 - 0.1), (-3.03, y + 0.22, DZ1 + 0.1))
B.box("dflange_t@avg", (TX0 - 0.3, 12.98, DZ0 - 0.1), (TX0, 15.99, DZ1 + 0.1))

# ---- tower: louvre band, roof grate under a coping, plinth, cornice
for k, o in enumerate(rects("banner")):
    B.recess(tower, dict(o, w=o["w"] - 0.15, h=o["h"] - 0.15), 0.2)
    B.sill(f"bsill{k}", o, proud=0.14, thick=0.1, overhang=0.08)
    B.sill(f"bhood{k}@avg", o, proud=0.12, thick=0.08, overhang=0.08, top=True)
g = rects("grate", lambda r: r["center"][1] > 20)[0]
c, w = g["center"], g["w"]
RT = TY + TCH
B.box("coping", (c[0] - w / 2 - 0.25, RT - 0.02, c[2] - w / 2 - 0.25), (c[0] + w / 2 + 0.25, RT + 0.25, c[2] + w / 2 + 0.25), chamfer=0.05)
B.box("gcut", (c[0] - w / 2 + 0.2, RT - 0.4, c[2] - w / 2 + 0.2), (c[0] + w / 2 - 0.2, RT + 0.5, c[2] + w / 2 - 0.2))
B.cut("coping", "gcut")
B.box("gcut2", (c[0] - w / 2 + 0.2, RT - 0.4, c[2] - w / 2 + 0.2), (c[0] + w / 2 - 0.2, RT + 0.5, c[2] + w / 2 - 0.2))
B.cut(tower, "gcut2")
for k in range(5):  # grate bars
    x = c[0] - w / 2 + 0.2 + (w - 0.4) * (k + 1) / 6
    B.box(f"gbar{k}@avg", (x - 0.06, RT - 0.3, c[2] - w / 2 + 0.2), (x + 0.06, RT - 0.08, c[2] + w / 2 - 0.2))
E = 0.12
for nm, lo, hi in (("n", (TX0 - E, 0, TZ0 - E), (TX1 + E, 0.55, TZ0)), ("s", (HX1, 0, TZ1), (TX1 + E, 0.55, TZ1 + E)),
                   ("e", (TX1, 0, TZ0), (TX1 + E, 0.55, TZ1)), ("w", (TX0 - E, 0, TZ0), (TX0, 0.55, HZ0))):
    B.box(f"tpl_{nm}", lo, hi)
for nm, lo, hi in (("n", (TX0 - E, TY - 0.25, TZ0 - E), (TX1 + E, TY, TZ0)), ("s", (TX0 - E, TY - 0.25, TZ1), (TX1 + E, TY, TZ1 + E)),
                   ("w", (TX0 - E, TY - 0.25, TZ0), (TX0, TY, TZ1)), ("e", (TX1, TY - 0.25, TZ0), (TX1 + E, TY, TZ1))):
    B.box(f"tcor_{nm}@avg", lo, hi)

# ---- hall: windows (one recess per two-pane window), doors, plinth, cornice
ops = json.load(open(D / "openings.json"))["openings"]
doors = rects("door")


def in_door(o):
    return any(np.dot(r["normal"], o["normal"]) > 0.9 and abs(np.dot(np.subtract(o["center"], r["center"]), r["t"])) < r["w"] / 2
               and abs(np.dot(np.subtract(o["center"], r["center"]), r["normal"])) < 0.05 for r in doors)


groups = {}
for o in ops:
    if in_door(o):
        continue
    cc, n, t = np.array(o["center"]), np.array(o["normal"]), np.array(o["t"])
    groups.setdefault((tuple(np.round(n, 2)), round(float(cc @ n), 2), round(float(cc @ t), 1)), []).append(o)
for k, gr in enumerate(groups.values()):
    y0 = min(o["center"][1] - o["h"] / 2 for o in gr)
    y1 = max(o["center"][1] + o["h"] / 2 for o in gr)
    cc = np.array(gr[0]["center"], float)
    cc[1] = (y0 + y1) / 2
    o = dict(gr[0], center=cc.tolist(), h=y1 - y0 + 0.04, w=max(q["w"] for q in gr) + 0.04)
    B.recess(hall, o, 0.14)
    B.sill(f"sill{k}", o, proud=0.1, thick=0.08, overhang=0.06)
for k, r in enumerate(doors):
    B.recess(hall, r, 0.22)
    B.sill(f"lintel{k}", r, proud=0.14, thick=0.12, overhang=0.1, top=True)
    B.sill(f"step{k}@avg", dict(r, center=[r["center"][0], 0.08 + r["h"] / 2 + 0.08, r["center"][2]]), proud=0.4, thick=0.16, overhang=0.1)
for o in ops:
    if in_door(o):
        B.recess(hall, o, 0.06, surface_shift=0.22)
P = 0.06
for nm, lo, hi in (("n", (HX0 - P, 0, HZ0 - P), (TX0, 0.35, HZ0)), ("s", (HX0 - P, 0, HZ1), (HX1 + P, 0.35, HZ1 + P)),
                   ("w", (HX0 - P, 0, HZ0), (HX0, 0.35, HZ1)), ("e", (HX1, 0, TZ1), (HX1 + P, 0.35, HZ1))):
    B.box(f"hpl_{nm}", lo, hi)
for nm, lo, hi in (("n", (HX0 - E, HY - 0.2, HZ0 - E), (TX0, HY, HZ0)), ("s", (HX0 - E, HY - 0.2, HZ1), (HX1 + E, HY, HZ1 + E)),
                   ("w", (HX0 - E, HY - 0.2, HZ0), (HX0, HY, HZ1)), ("e", (HX1, HY - 0.2, TZ1), (HX1 + E, HY, HZ1))):
    B.box(f"hcor_{nm}@avg", lo, hi)

# ---- hall roof: fan housing with two wells, vent
HT = HY + HCH
fb = rects("fanbox")[0]
c = fb["center"]
fan = B.box("fanbox", (c[0] - fb["w"] / 2 + 0.25, HT - 0.02, c[2] - fb["h"] / 2 + 0.25),
            (c[0] + fb["w"] / 2 - 0.25, HT + 0.4, c[2] + fb["h"] / 2 - 0.25), chamfer=0.06)
for nm in ("fan1", "fan2"):
    o = rects(nm)[0]
    B.prism_y(f"{nm}_well", ring(o["center"][0], o["center"][2], o["w"] / 2 - 0.1), HT + 0.15, HT + 0.6)
    B.cut(fan, f"{nm}_well")
    B.prism_y(f"{nm}_hub", ring(o["center"][0], o["center"][2], 0.24, 16), HT + 0.1, HT + 0.32)
o = rects("rvent")[0]
c = o["center"]
B.box("rvent", (c[0] - o["w"] / 2, HT - 0.02, c[2] - o["h"] / 2), (c[0] + o["w"] / 2, HT + 0.35, c[2] + o["h"] / 2), chamfer=0.04)

print(B.dump())
