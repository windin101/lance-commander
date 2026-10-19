#!/usr/bin/env python3
"""CAD rebuild of the chemical plant (appearance chemicalplant), in the original's frame.

    D=~/craft/solid/mc2/buildings/chemicalplant
    python3 -I tools/art/cad_building.py openings chemicalplant > $D/openings.json
    python3 -I tools/art/cad_building.py decal chemicalplant 0 u0 v0 u1 v1 > $D/decal_<name>.json  (see DECALS)
    python3 -I tools/cad/chemicalplant_cad.py $D > $D/chemicalplant.json
    solidcraft-cli run $D/chemicalplant.json --out $D/chemicalplant.obj
    python3 -I tools/art/cad_building.py bake chemicalplant $D/chemicalplant.obj

Measured from game/assets/objects/chemicalplant.glb: an L-shaped 0.28 m concrete pad; a brick tower (x -3.38..6.72,
z -9.66..-1.49) with walls to 12.82 m and a 1.38 m 45-degree chamfer to a flat roof at 14.2 m; a lean-to annex
(x 0.02..5.68, z -1.49..2.67) from 5.54 m at its front to 8.31 m at the tower; three hexagonal silos (flats at
x 7.46 / 12.07, centres z -6.945, -0.795, 5.355) to 8.69 m under a hexagonal cap to a 1.065 m flat at 9.92 m;
a 5.82 m box (x 8.81..10.79, z -5.1..3.45) linking them.
Rebuilt round (issue I77): the silos as 24-sided cylinders and caps of equal area. Relief: the tower's louvres,
banner window, door panels and windows, the annex doors and windows and the silo hatches real recesses; a raised
roof fan housing with two round fan wells; a cornice and plinth on the tower; the annex roof a slab with eaves;
rims where the silo caps start. The green silo band and signs stay paint.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, box_edges  # noqa: E402

DECALS = {  # name: (u0, v0, u1, v1) on material 0 of the upscaled atlas
    "fanbox": (0.088, 0.078, 0.322, 0.244), "fan1": (0.113, 0.107, 0.18, 0.175), "fan2": (0.197, 0.107, 0.264, 0.175),
    "louv1": (0.742, 0.565, 0.83, 0.675), "louv2": (0.86, 0.565, 0.947, 0.675), "banner": (0.674, 0.088, 0.947, 0.146),
    "tdoor": (0.82, 0.425, 0.92, 0.51), "adoor": (0.38, 0.86, 0.473, 0.986), "hatch": (0.148, 0.933, 0.205, 0.986),
}
D = Path(sys.argv[1])
TX0, TX1, TZ0, TZ1, TY, TCH = -3.38, 6.72, -9.66, -1.49, 12.82, 1.38
AX0, AX1, AZ1, AYF, AYB = 0.02, 5.68, 2.67, 5.54, 8.31
SX, SZS, SR, SY, SRT, STOP = 9.765, (-6.945, -0.795, 5.355), 2.42, 8.69, 1.12, 9.92
PAD = 0.28


def rects(name, keep=lambda r: True):
    return [r for r in json.load(open(D / f"decal_{name}.json"))["rects"] if keep(r)]


def ring(cx, cz, r, k=24):
    return [(cx + r * math.cos(2 * math.pi * (i + 0.5) / k), cz + r * math.sin(2 * math.pi * (i + 0.5) / k)) for i in range(k)]


def in_annex(c):
    return AX0 - 0.05 < c[0] < AX1 + 0.05 and c[2] > TZ1 - 0.05 and c[1] < AYB


B = Builder()
# ---- volumes
B.prism_y("pad", [(-3.79, -9.94), (12.4, -9.94), (12.4, 8.35), (7.13, 8.35), (7.13, 3.36), (-3.79, 3.36)], 0.0, PAD)
tower = B.box("tower", (TX0, PAD - 0.02, TZ0), (TX1, TY + TCH, TZ1), chamfer=TCH,
              chamfer_edges=box_edges((TX0, 0, TZ0), (TX1, TY + TCH, TZ1)))
annex = B.prism_x("annex", [(TZ1 - 0.02, PAD - 0.02), (AZ1, PAD - 0.02), (AZ1, AYF), (TZ1 - 0.02, AYB)], AX0, AX1)
u = np.array([TZ1 - AZ1, AYB - AYF]); L = np.linalg.norm(u); u /= L; n = np.array([-u[1], u[0]])
if n[1] < 0:
    n = -n
a0 = np.array([AZ1, AYF]) - u * 0.3
a1 = np.array([TZ1 + 0.01, AYB])
B.prism_x("aroof", [tuple(a0), tuple(a1), tuple(a1 + n * 0.16), tuple(a0 + n * 0.16)], AX0 - 0.2, AX1 + 0.2)
B.box("link", (8.81, PAD - 0.02, -5.1), (10.79, 5.82, 3.45))
B.box("linkcap@avg", (8.73, 5.82, -5.1), (10.87, 5.95, 3.45))
for k, cz in enumerate(SZS):
    B.prism_y(f"silo{k}", ring(SX, cz, SR), PAD - 0.02, SY)
    B.loft_y(f"scap{k}", ring(SX, cz, SR), SY, ring(SX, cz, SRT), STOP)
    B.prism_y(f"srim{k}@avg", ring(SX, cz, SR + 0.07), SY - 0.16, SY + 0.06)
    B.prism_y(f"shatch{k}", ring(SX, cz, 0.55), STOP - 0.02, STOP + 0.22)

# ---- tower relief: cornice, plinth, louvres, banner window, door panels, windows
E = 0.12
for nm, lo, hi in (("n", (TX0 - E, TY - 0.3, TZ0 - E), (TX1 + E, TY, TZ0)), ("s", (TX0 - E, TY - 0.3, TZ1), (TX1 + E, TY, TZ1 + E)),
                   ("w", (TX0 - E, TY - 0.3, TZ0), (TX0, TY, TZ1)), ("e", (TX1, TY - 0.3, TZ0), (TX1 + E, TY, TZ1))):
    B.box(f"cornice_{nm}@avg", lo, hi)
P = 0.06
B.box("pl_n", (TX0 - P, PAD, TZ0 - P), (TX1 + P, PAD + 0.5, TZ0))
B.box("pl_w", (TX0 - P, PAD, TZ0), (TX0, PAD + 0.5, TZ1 + P))
B.box("pl_e", (TX1, PAD, TZ0), (TX1 + P, PAD + 0.5, TZ1 + P))
for nm in ("louv1", "louv2"):
    for o in rects(nm):
        B.recess(tower, dict(o, w=o["w"] - 0.1, h=o["h"] - 0.1), 0.2)
        B.sill(f"{nm}_{o['normal'][0]:+.0f}", o, proud=0.12, thick=0.1, overhang=0.06)
for k, o in enumerate(rects("banner", lambda r: r["normal"][2] < 0 or r["center"][1] > AYB)):
    B.recess(tower, dict(o, w=o["w"] - 0.15, h=o["h"] - 0.15), 0.15)
    B.sill(f"bsill{k}", o, proud=0.12, thick=0.1, overhang=0.08)
for k, o in enumerate(rects("tdoor", lambda r: r["normal"][2] < 0)):
    B.recess(tower, o, 0.15)
    B.sill(f"tlintel{k}", o, proud=0.14, thick=0.12, overhang=0.1, top=True)
ops = [o for o in json.load(open(D / "openings.json"))["openings"] if not in_annex(o["center"]) or o["center"][2] > AZ1 - 0.05]
for k, o in enumerate(ops):
    c = o["center"]
    if abs(o["normal"][2]) > 0.9 and abs(c[2] - TZ0) < 0.05:  # panes in the front door panel
        B.recess(tower, o, 0.06, surface_shift=0.15)
    elif abs(o["normal"][0]) > 0.9 and abs(abs(c[0] - 1.67) - 5.05) < 0.05:  # tower side windows
        B.recess(tower, o, 0.12)
        if o["h"] < 0.5:
            B.sill(f"wsill{k}", o, proud=0.1, thick=0.07, overhang=0.06)
    elif abs(o["normal"][2]) > 0.9 and abs(c[2] - AZ1) < 0.05:  # annex front windows
        B.recess(annex, o, 0.12)
        if o["h"] < 0.5:
            B.sill(f"asill{k}", o, proud=0.1, thick=0.07, overhang=0.06)
    elif abs(o["normal"][0]) > 0.9 and (abs(c[0] - AX0) < 0.05 or abs(c[0] - AX1) < 0.05):  # annex door panes
        B.recess(annex, o, 0.06, surface_shift=0.15)
for k, o in enumerate(rects("adoor")):
    B.recess(annex, dict(o, w=o["w"] - 0.3, h=o["h"] - 0.1), 0.15)
    B.sill(f"alintel{k}", o, proud=0.14, thick=0.12, overhang=0.0, top=True)

# ---- roof fan housing with two fan wells
fb = rects("fanbox", lambda r: r["center"][1] > 10)[0]
c = fb["center"]
fan = B.box("fanbox", (c[0] - fb["w"] / 2 + 0.3, TY + TCH - 0.02, c[2] - fb["h"] / 2 + 0.3),
            (c[0] + fb["w"] / 2 - 0.3, TY + TCH + 0.45, c[2] + fb["h"] / 2 - 0.3), chamfer=0.06)
for nm in ("fan1", "fan2"):
    o = rects(nm, lambda r: r["center"][1] > 10)[0]
    B.prism_y(f"{nm}_well", ring(o["center"][0], o["center"][2], o["w"] / 2 - 0.08), TY + TCH + 0.2, TY + TCH + 0.6)
    B.cut(fan, f"{nm}_well")
    B.prism_y(f"{nm}_hub", ring(o["center"][0], o["center"][2], 0.22, 16), TY + TCH + 0.15, TY + TCH + 0.38)

# ---- silo hatches (the hex flats sit 11.5 cm inside the round wall); the link's own
for k, o in enumerate(rects("hatch")):
    on_link = abs(abs(o["center"][0] - SX) - 0.99) < 0.05
    if on_link:
        B.recess("link", o, 0.12)
    else:
        sid = int(np.argmin([abs(o["center"][2] - cz) for cz in SZS]))
        B.recess(f"silo{sid}", o, 0.25, surface_shift=-0.13)

print(B.dump())
