#!/usr/bin/env python3
"""CAD rebuild of the large factory (appearance factorylg), in the original's frame.

    D=~/craft/solid/mc2/buildings/factorylg
    python3 -I tools/art/cad_building.py openings factorylg > $D/openings.json
    python3 -I tools/art/cad_building.py decal factorylg <mat> u0 v0 u1 v1 > $D/decal_<name>.json  (see DECALS)
    python3 -I tools/cad/factorylg_cad.py $D > $D/factorylg.json
    solidcraft-cli run $D/factorylg.json --out $D/factorylg.obj
    python3 -I tools/art/cad_building.py bake factorylg $D/factorylg.obj --max-res 4096 --glass 170,176,182

Measured from game/assets/objects/factorylg.glb: a hall (x -14.76..9.28, z -8.17..4.36) with walls to 9.21 m and
an off-centre gable roof, ridge at z -5.22, 12.83 m (a long south slope and a steep north one painted as siding),
a vent tower on the south slope (x 0.19..3.89, z -3.8..-0.2) to 14.11 m, and a 4.23 m single-storey wing round its
south and east sides (L plan to x 14.76, z 7.98). Relief: the painted siding stripes on the hall walls real
trapezoid ribs at the stripe positions read off the upscaled art; the two roller doors on the north wall 30 cm
recesses with frames and hoods, their slat cut-outs pale glazing at the back; the wing's louvred fascia a proud
band, its two small doors and louvre vents recesses, the louvre panel a shallow recess; plinths, parapets round
the wing roofs, gutter, string course, ridge cap and gable verges on the hall; the roof units (AC boxes, hatches,
the vent tower's cap) real boxes.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

DECALS = {"door": (0, .39, .125, .595, .312), "door3": (0, .42, .563, .498, .654), "louvre": (0, .068, .722, .40, .792),
          "ac1": (1, .733, .257, .788, .297), "ac2": (1, .742, .411, .794, .445), "box1": (1, .186, .748, .225, .791),
          "sq1": (1, .244, .89, .31, .92)}
D = Path(sys.argv[1])
HX0, HX1, HZ0, HZ1, HY, RZ, RY = -14.76, 9.28, -8.17, 4.36, 9.21, -5.22, 12.83
WY, WX1, WZ1 = 4.23, 14.76, 7.98
WING = [(HX0, HZ1), (HX0, WZ1), (WX1, WZ1), (WX1, HZ0), (HX1, HZ0), (HX1, HZ1)]  # edges 4, 5 against the hall
INNER = (4, 5)


def rects(name, keep=lambda r: True):
    return [r for r in json.load(open(D / f"decal_{name}.json"))["rects"] if keep(r)]


def roof_y(z):  # the long south slope
    return HY + (HZ1 - z) / (HZ1 - RZ) * (RY - HY)


def ring(name, poly, d, y0, y1, skip=()):
    """A band round the plan, d outward (d < 0 inward), one prism per edge; edges in skip are left out and the
    ends next to them are cut square."""
    P = np.array(poly, float)
    area = sum(P[i, 0] * P[(i + 1) % len(P), 1] - P[(i + 1) % len(P), 0] * P[i, 1] for i in range(len(P)))
    s = 1 if area > 0 else -1
    N = [np.array([(P[(i + 1) % len(P)] - P[i])[1], -(P[(i + 1) % len(P)] - P[i])[0]]) * s / np.linalg.norm(P[(i + 1) % len(P)] - P[i])
         for i in range(len(P))]
    for i in range(len(P)):
        if i in skip:
            continue
        j = (i + 1) % len(P)
        ends = []
        for v, other in ((i, (i - 1) % len(P)), (j, j)):
            if other in skip:
                ends.append(P[v] + N[i] * d)
            else:
                m = N[i] + N[other]
                m /= np.linalg.norm(m)
                ends.append(P[v] + m * d / (m @ N[i]))
        B.prism_y(f"{name}{i}", [tuple(P[i]), tuple(P[j]), tuple(ends[1]), tuple(ends[0])], y0, y1)


RIBS = {  # light siding stripes (game m along the wall) from a brightness-peak scan of the upscaled art
    "n": [-12.6, -11.98, -10.38, -8.6, -6.42, -4.52, -2.7, -0.72, 1.14, 3.3, 4.98, 6.56, 7.18, 8.92],
    "s": [-13.26, -10.94, -8.82, -6.96, -4.7, -2.6, -0.6, 1.66, 3.46, 5.52, 7.8],
    "w": [-6.76, -4.48, -2.44, -0.66, 1.54, 3.52],
    "e": [-6.76, -4.48, -2.44, -0.66, 1.54, 3.52],
}
P, W = 0.04, 0.08
B = Builder()
hall = B.prism_x("hall", [(HZ0, 0.0), (HZ1, 0.0), (HZ1, HY), (RZ, RY), (HZ0, HY)], HX0, HX1)
south = B.box("wing_s", (HX0, 0.0, HZ1 - 0.02), (WX1, WY, WZ1))
east = B.box("wing_e", (HX1 - 0.02, 0.0, HZ0), (WX1, WY, HZ1))
tower = B.box("tower", (0.19, 10.75, -3.8), (3.89, 14.11, -0.2))
B.box("tower_cap", (0.07, 13.95, -3.92), (4.01, 14.17, -0.08), chamfer=0.04)

doors = rects("door")
small = rects("door3")


def door_top(axis_val, along, normal):
    for d in doors + small:
        if np.allclose(d["normal"], normal, atol=0.05):
            c = d["center"]
            a = c[0] if abs(normal[2]) > 0.5 else c[2]
            if abs(along - a) < d["w"] / 2 + 0.12:
                return c[1] + d["h"] / 2 + 0.15
    return None


def rib_x(name, x, sgn, z, y0, y1):
    B.prism_y(name, [(x - sgn * 0.01, z - W), (x + sgn * P, z - W / 2), (x + sgn * P, z + W / 2), (x - sgn * 0.01, z + W)], y0, y1)


def rib_z(name, z, sgn, x, y0, y1):
    B.prism_y(name, [(x - W, z - sgn * 0.01), (x - W / 2, z + sgn * P), (x + W / 2, z + sgn * P), (x + W, z - sgn * 0.01)], y0, y1)


k = 0
for x in RIBS["n"]:
    t = door_top(HZ0, x, [0, 0, -1])
    rib_z(f"rib{k}", HZ0, -1, x, t if t else 0.35, HY - 0.05); k += 1
for x in RIBS["s"]:
    rib_z(f"rib{k}", HZ1, 1, x, WY + 0.02, HY - 0.05); k += 1
for z in RIBS["w"]:
    rib_x(f"rib{k}", HX0, -1, z, 0.35, HY - 0.05); k += 1
for z in RIBS["e"]:
    rib_x(f"rib{k}", HX1, 1, z, WY + 0.02, HY - 0.05); k += 1

# hall trim: gutter on the south eave, string course on the north, ridge cap, gable verges, plinths
B.box("gutter@avg", (HX0 - 0.1, HY - 0.28, HZ1), (HX1 + 0.1, HY + 0.06, HZ1 + 0.22))
B.box("course@avg", (HX0 - 0.1, HY - 0.12, HZ0 - 0.12), (HX1 + 0.1, HY + 0.04, HZ0))
B.prism_x("ridge@avg", [(RZ - 0.25, RY - 0.25), (RZ + 0.25, RY - 0.12), (RZ + 0.25, RY + 0.08), (RZ, RY + 0.14), (RZ - 0.25, RY + 0.08)],
          HX0 - 0.1, HX1 + 0.1)
for nm, x0, x1 in (("verge_w@avg", HX0 - 0.1, HX0 + 0.02), ("verge_e@avg", HX1 - 0.02, HX1 + 0.1)):
    B.prism_x(nm, [(HZ0 - 0.1, HY - 0.25), (RZ, RY - 0.22), (HZ1 + 0.1, HY - 0.25), (HZ1 + 0.1, HY + 0.1), (RZ, RY + 0.14),
                   (HZ0 - 0.1, HY + 0.1)], x0, x1)
# hall plinth: west wall, north wall between the doors
B.box("pl_hw", (HX0 - 0.06, 0, HZ0 - 0.06), (HX0, 0.35, HZ1))
xs = sorted((d["center"][0] - d["w"] / 2, d["center"][0] + d["w"] / 2) for d in doors)
cuts = [HX0 - 0.06] + [v for a, b in xs for v in (a, b)] + [HX1]
for i in range(0, len(cuts), 2):
    B.box(f"pl_hn{i}", (cuts[i], 0, HZ0 - 0.06), (cuts[i + 1], 0.35, HZ0))

# the wing: louvred fascia, plinth (gaps at the small doors), parapet
ring("fascia", WING, 0.12, 3.45, WY, skip=INNER)
ring("parapet", WING, -0.22, WY - 0.02, WY + 0.22, skip=INNER)
B.box("pl_s", (HX0 - 0.06, 0, WZ1), (WX1 + 0.06, 0.35, WZ1 + 0.06))
B.box("pl_ws", (HX0 - 0.06, 0, HZ1), (HX0, 0.35, WZ1))
sn = [d for d in small if d["normal"][2] < -0.9][0]
se = [d for d in small if d["normal"][0] > 0.9][0]
B.box("pl_n0", (HX1, 0, HZ0 - 0.06), (sn["center"][0] - sn["w"] / 2, 0.35, HZ0))
B.box("pl_n1", (sn["center"][0] + sn["w"] / 2, 0, HZ0 - 0.06), (WX1 + 0.06, 0.35, HZ0))
B.box("pl_e0", (WX1, 0, HZ0 - 0.06), (WX1 + 0.06, 0.35, se["center"][2] - se["w"] / 2))
B.box("pl_e1", (WX1, 0, se["center"][2] + se["w"] / 2), (WX1 + 0.06, 0.35, WZ1 + 0.06))

# doors: recess, frame, hood; the slat cut-outs pale glazing at the back
DD, SD = 0.3, 0.16
for k, d in enumerate(doors):
    inner = dict(d, w=d["w"] - 0.5, h=d["h"] - 0.25, center=[d["center"][0], d["center"][1] - 0.125, d["center"][2]])
    B.recess(hall, inner, DD)
    B.frame(f"dframe{k}", inner, width=0.14, proud=0.08)
    B.sill(f"dhood{k}@avg", inner, proud=0.3, thick=0.14, overhang=0.3, top=True)
for k, d in enumerate(small):
    lo = d["center"][1] - d["h"] / 2
    o = dict(d, center=[d["center"][0], (d["h"] + lo) / 2, d["center"][2]], h=d["h"] + lo)
    B.recess(east, o, SD)
    B.sill(f"shood{k}@avg", o, proud=0.16, thick=0.1, overhang=0.1, top=True)
    small[k] = o


def in_small(o):
    return any(np.allclose(o["normal"], d["normal"], atol=0.05) and np.linalg.norm(np.array(o["center"]) - d["center"]) < d["w"] / 2 + 0.3
               for d in small)


for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    c = o["center"]
    if abs(c[2] - HZ0) < 0.05 and c[0] < HX1:  # the roller doors' slats
        B.recess(hall, o, 0.04, surface_shift=DD)
    elif in_small(o):
        B.recess(east, o, 0.05, surface_shift=SD)
    else:
        B.recess(east if c[0] > 14 else south, o, 0.16)
        B.sill(f"sill{k}", o, proud=0.12, thick=0.07, overhang=0.08)
for o in rects("louvre"):
    B.recess(south, dict(o, w=o["w"] - 0.1, h=o["h"] - 0.1), 0.08)
    B.frame("lframe", o, width=0.07, proud=0.05)

# roof units on the wing, hatches on the hall slope
for nm, hgt in (("ac1", 0.55), ("ac2", 0.55), ("box1", 0.45), ("sq1", 0.15)):
    for k, o in enumerate(rects(nm)):
        c = o["center"]
        if o["normal"][1] > 0.99:
            B.box(f"{nm}_{k}", (c[0] - o["w"] / 2, WY - 0.02, c[2] - o["h"] / 2), (c[0] + o["w"] / 2, WY + hgt, c[2] + o["h"] / 2), chamfer=0.04)
        else:
            dz = o["h"] * 0.94 / 2
            za, zb = c[2] - dz, c[2] + dz
            B.prism_x(f"{nm}_{k}", [(za, roof_y(za) - 0.1), (zb, roof_y(zb) - 0.1), (zb, roof_y(zb) + hgt), (za, roof_y(za) + hgt)],
                      c[0] - o["w"] / 2, c[0] + o["w"] / 2)

print(B.dump())
