#!/usr/bin/env python3
"""CAD rebuild of the processing plant (appearance processingplant), in the original's frame.

    D=~/craft/solid/mc2/buildings/processingplant
    python3 -I tools/art/cad_building.py openings processingplant > $D/openings.json
    python3 -I tools/art/cad_building.py decal processingplant <mat> u0 v0 u1 v1 > $D/decal_<name>.json  (see DECALS)
    python3 -I tools/cad/processingplant_cad.py $D > $D/processingplant.json
    solidcraft-cli run $D/processingplant.json --out $D/processingplant.obj
    python3 -I tools/art/cad_building.py bake processingplant $D/processingplant.obj

Measured from game/assets/objects/processingplant.glb (faces listed with their UVs): a 9.75 x 17.9 m hall
(x -7.93..1.82, z -8.95..8.95), walls to 5.24 m under a 45-degree hipped roof to a flat top at 6.7 m (1.45 m in);
a dark control block in front (x -5.33..-0.53, z 5.82..11.65) to 8.74 m with a 45-degree slope from 5.82 m at its
front face; and two hexagonal stacks (2.8 m flats, x -1.64..3.97, centred z -4.51 and 1.02), straight to 8.11 m
then tapering to a 1.3 m hexagon at 14.21 m. Relief: each two-pane vent one 15 cm recess with a sill; the doors
25 cm recesses with their glazing 6 cm deeper; the block's five-bar grille and its front windows real recesses;
a dark plinth 6 cm proud; an eaves band; collars where the stacks start to taper and a 1.5 m deep hollow in their
tops; the roof vent, box and hatch and the block's roof vents real boxes. Painted pipes and the orange band stay paint.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

DECALS = {  # name: (material, u0, v0, u1, v1) in the upscaled atlas, for cad_building.py decal
    "door": (0, 0.664, 0.896, 0.718, 0.977), "grille": (0, 0.638, 0.177, 0.703, 0.318),
    "btopvent": (0, 0.54, 0.179, 0.607, 0.217), "btopsq": (0, 0.54, 0.234, 0.607, 0.31),
    "roofvent": (0, 0.098, 0.262, 0.154, 0.344), "roofbox": (0, 0.408, 0.271, 0.485, 0.327),
    "roofsq": (0, 0.352, 0.283, 0.387, 0.322), "fw1": (0, 0.75, 0.148, 0.781, 0.2),
    "fw2": (0, 0.789, 0.148, 0.846, 0.2), "fw3": (0, 0.859, 0.148, 0.887, 0.2), "panel": (0, 0.674, 0.656, 0.703, 0.705),
}
D = Path(sys.argv[1])
HX0, HX1, HZ = -7.93, 1.82, 8.95
YW, YR, RIN = 5.24, 6.7, 1.45
BX0, BX1, BZ0, BZ1, BY, BS = -5.33, -0.53, 5.82, 11.65, 8.74, 5.82
WIN_DEPTH, DOOR_DEPTH = 0.15, 0.25


def rects(name, ny=None, y=None):
    rs = json.load(open(D / f"decal_{name}.json"))["rects"]
    if ny is not None:
        rs = [r for r in rs if abs(r["normal"][1] - ny) < 0.05]
    if y is not None:
        rs = [r for r in rs if abs(r["center"][1] - y) < 0.1]
    return rs


def hexa(cx, cz, rx, rz):
    return [(cx - rx, cz), (cx - rx / 2, cz - rz), (cx + rx / 2, cz - rz), (cx + rx, cz), (cx + rx / 2, cz + rz), (cx - rx / 2, cz + rz)]


B = Builder()
# ---- volumes
hall = B.box("hall", (HX0, 0.0, -HZ), (HX1, YW, HZ))
B.loft_y("roof", [(HX0, -HZ), (HX1, -HZ), (HX1, HZ), (HX0, HZ)], YW,
         [(HX0 + RIN, -HZ + RIN), (HX1 - RIN, -HZ + RIN), (HX1 - RIN, HZ - RIN), (HX0 + RIN, HZ - RIN)], YR)
blk = B.prism_x("block", [(BZ0, 0.0), (BZ1, 0.0), (BZ1, BS), (BZ1 - (BY - BS), BY), (BZ0, BY)], BX0, BX1)

# ---- stacks: hexagonal shafts, tapering tops, collars, hollow tops
stacks = []
for k, cz in enumerate((-4.51, 1.02)):
    cx = 1.165
    s = B.prism_y(f"shaft{k}", hexa(cx, cz, 2.805, 2.43), 0.0, 8.11)
    t = B.loft_y(f"taper{k}", hexa(cx, cz, 2.805, 2.43), 8.11, hexa(cx, cz, 1.295, 1.12), 14.21)
    B.prism_y(f"collar{k}@avg", hexa(cx, cz, 2.805 + 0.12, 2.43 + 0.1), 7.95, 8.25)
    B.prism_y(f"lip{k}", hexa(cx, cz, 1.295 + 0.06, 1.12 + 0.05), 14.05, 14.33)
    B.prism_y(f"hole{k}", hexa(cx, cz, 0.85, 0.74), 12.7, 14.5)
    B.cut(f"lip{k}", f"hole{k}")
    B.prism_y(f"hole{k}b", hexa(cx, cz, 0.85, 0.74), 12.7, 14.5)
    B.cut(t, f"hole{k}b")

# ---- vents (two cut-outs each): one recess with a sill; door glazing at the back of the door recess
ops = [o for o in json.load(open(D / "openings.json"))["openings"] if abs(o["normal"][1]) < 0.1]
doors = rects("door")
groups = {}
for o in ops:
    c, n, t = np.array(o["center"]), np.array(o["normal"]), np.array(o["t"])
    groups.setdefault((tuple(np.round(n, 2)), round(float(c @ n), 2), round(float(c @ t), 1)), []).append(o)
for k, g in enumerate(groups.values()):
    y0 = min(o["center"][1] - o["h"] / 2 for o in g)
    y1 = max(o["center"][1] + o["h"] / 2 for o in g)
    c = np.array(g[0]["center"], float)
    c[1] = (y0 + y1) / 2
    o = dict(g[0], center=c.tolist(), h=y1 - y0, w=max(q["w"] for q in g))
    in_door = any(np.dot(r["normal"], o["normal"]) > 0.9 and abs(np.dot(np.subtract(o["center"], r["center"]), r["t"])) < r["w"] / 2
                  and abs(np.dot(np.subtract(o["center"], r["center"]), r["normal"])) < 0.05 for r in doors)
    if in_door:
        continue
    tgt = blk if BX0 - 0.01 <= c[0] <= BX1 + 0.01 and c[2] > BZ0 else hall
    B.recess(tgt, o, WIN_DEPTH)
    B.sill(f"sill{k}", o, proud=0.10, thick=0.08, overhang=0.06)
for k, r in enumerate(doors):
    B.recess(hall, r, DOOR_DEPTH)
    B.sill(f"lintel{k}", r, proud=0.12, thick=0.12, overhang=0.12, top=True)
for o in ops:
    if any(np.dot(r["normal"], o["normal"]) > 0.9 and abs(np.dot(np.subtract(o["center"], r["center"]), r["t"])) < r["w"] / 2
           and abs(np.dot(np.subtract(o["center"], r["center"]), r["normal"])) < 0.05 for r in doors):
        B.recess(hall, o, 0.06, surface_shift=DOOR_DEPTH)

# ---- control block: grille on the slope, front windows, side panels
for o in rects("grille", ny=0.71):
    B.recess(blk, o, 0.2)
for nm in ("fw1", "fw2", "fw3"):
    for o in rects(nm):
        B.recess(blk, o, 0.10)
        B.sill(f"{nm}_sill", o, proud=0.08, thick=0.06, overhang=0.04)
for k, o in enumerate(rects("panel")):
    n, t, b = (np.array(o[q], float) for q in ("normal", "t", "b"))
    B.obox(f"panel{k}", np.array(o["center"]) + n * 0.03, t, b, n, (o["w"], o["h"], 0.08))

# ---- plinth and eaves band round the hall, plinth round the block
def band(name, lo, hi, y0, y1, proud, avg=False):
    (x0, z0), (x1, z1) = lo, hi
    sfx = "@avg" if avg else ""
    B.box(f"{name}_n{sfx}", (x0 - proud, y0, z0 - proud), (x1 + proud, y1, z0))
    B.box(f"{name}_s{sfx}", (x0 - proud, y0, z1), (x1 + proud, y1, z1 + proud))
    B.box(f"{name}_w{sfx}", (x0 - proud, y0, z0), (x0, y1, z1))
    B.box(f"{name}_e{sfx}", (x1, y0, z0), (x1 + proud, y1, z1))


band("plinth", (HX0, -HZ), (HX1, HZ), 0.0, 0.55, 0.06)
band("eaves", (HX0, -HZ), (HX1, HZ), YW - 0.22, YW + 0.02, 0.16, avg=True)
B.box("bplinth_f", (BX0 - 0.06, 0.0, BZ1), (BX1 + 0.06, 0.55, BZ1 + 0.06))
B.box("bplinth_w", (BX0 - 0.06, 0.0, HZ), (BX0, 0.55, BZ1))
B.box("bplinth_e", (BX1, 0.0, HZ), (BX1 + 0.06, 0.55, BZ1))

# ---- roof furniture
def roofbox(name, o, y, hgt, ch=0.03):
    c, w, h = o["center"], o["w"], o["h"]
    B.box(name, (c[0] - w / 2, y - 0.02, c[2] - h / 2), (c[0] + w / 2, y + hgt, c[2] + h / 2), chamfer=ch)


for nm, hgt in (("roofvent", 0.35), ("roofbox", 0.55), ("roofsq", 0.2)):
    for k, o in enumerate(rects(nm, ny=1.0, y=YR)):
        roofbox(f"{nm}{k}", o, YR, hgt)
for nm, hgt in (("btopvent", 0.4), ("btopsq", 0.25)):
    for k, o in enumerate(rects(nm, ny=1.0, y=BY)):
        roofbox(f"{nm}{k}", o, BY, hgt)
B.box("bcoping@avg", (BX0 - 0.05, BY, BZ0), (BX1 + 0.05, BY + 0.12, BZ0 + 0.2))

print(B.dump())
