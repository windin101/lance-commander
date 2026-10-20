#!/usr/bin/env python3
"""CAD rebuild of the weapons facility (appearance weaponsfacility), in the original's frame.

    D=~/craft/solid/mc2/buildings/weaponsfacility
    python3 -I tools/art/cad_building.py openings weaponsfacility > $D/openings.json
    python3 -I tools/art/cad_building.py decal weaponsfacility 0 u0 v0 u1 v1 > $D/decal_<name>.json  (see DECALS)
    python3 -I tools/cad/weaponsfacility_cad.py $D > $D/weaponsfacility.json
    solidcraft-cli run $D/weaponsfacility.json --out $D/weaponsfacility.obj
    python3 -I tools/art/cad_building.py bake weaponsfacility $D/weaponsfacility.obj --max-res 4096

Measured from game/assets/objects/weaponsfacility.glb: an L-shaped block (x -12.43..12.43, z 1.92..9.72, and a wing
x 5.36..12.43, z -5.48..1.92) to 6.06 m with four wedge buttresses on its south face (down to 1.19 m at
z 14.37); a 3.77 m compound wall (zero-thickness cards in the original, here 20 cm walls built inward) closing a
yard x -20.57..12.43, z -20.47..1.93; in the yard nine 3.74 m containers in four stacks, five small 1.87 m crates
(three turned, one hanging), and a lattice crane: a 2.59 x 2.43 m tower to 5.15 m, a turned cab (4.32-6.54 m),
a triangular boom to 14.29 m and a vertical hoist mast. Relief: the containers and crates real framed boxes (corner posts
and rails round an inset panel); the tower legs and girts real bars at the original's lattice cut-outs; the boom
three chords with rungs and lacing; the hoist the original's crossed lattice cards rebuilt as a diamond-plan
lattice mast over the hanging crate. The yard floor is a cut-out in the original (terrain shows through): none here. On the block: the louvred vents
recesses with slats and a frame, their red lamps real boxes, the windows and doors recesses (door glazing at the
back), a parapet, a plinth, roof hatches; the yard wall a coping and a kerb. Hazard stripes stay paint.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

DECALS = {"hatch1": (.163, .5, .25, .588), "hatch2": (.46, .5, .548, .588), "hatch3": (.75, .5, .836, .588),
          "louvre1": (.125, .243, .243, .35), "louvre2": (.446, .243, .563, .35), "louvre3": (.773, .243, .89, .35),
          "lamp1": (.172, .21, .197, .236), "lamp2": (.49, .21, .516, .236), "lamp3": (.82, .21, .846, .236),
          "door": (.79, .91, .875, 1.0)}
D = Path(sys.argv[1])
TOP, WALL = 6.06, 3.77
STEEL = "@2b2d30"
B = Builder()
nb = [0]


def rects(name):
    return json.load(open(D / f"decal_{name}.json"))["rects"]


def bar(name, p, q, s):
    """A square bar of side s from p to q (game metres)."""
    p, q = np.array(p, float), np.array(q, float)
    t = (q - p) / np.linalg.norm(q - p)
    up = np.array([0, 1.0, 0]) if abs(t[1]) < 0.9 else np.array([1.0, 0, 0])
    b = np.cross(up, t)
    b /= np.linalg.norm(b)
    n = np.cross(t, b)
    B.obox(name, (p + q) / 2, t, b, n, (np.linalg.norm(q - p), s, s))


def crate(name, c, y0, size, yaw=0.0, rail=0.2):
    """A framed box: an inset panel body plus corner posts and top/bottom rails (yaw in degrees about game y)."""
    a = math.radians(yaw)
    t, b, n = np.array([math.cos(a), 0, -math.sin(a)]), np.array([0, 1.0, 0]), np.array([math.sin(a), 0, math.cos(a)])
    sx, sy, sz = size
    ctr = np.array([c[0], y0 + sy / 2, c[1]])
    B.obox(f"{name}", ctr, t, b, n, (sx - 0.1, sy - 0.02, sz - 0.1))
    k = 0
    for i in (-1, 1):
        for j in (-1, 1):
            B.obox(f"{name}_p{k}", ctr + t * i * (sx - rail) / 2 + n * j * (sz - rail) / 2, t, b, n, (rail, sy, rail)); k += 1
            B.obox(f"{name}_r{k}", ctr + b * i * (sy - rail) / 2 + n * j * (sz - rail) / 2, t, b, n, (sx - 2 * rail, rail, rail)); k += 1
            B.obox(f"{name}_r{k}", ctr + b * i * (sy - rail) / 2 + t * j * (sx - rail) / 2, t, b, n, (rail, rail, sz - 2 * rail)); k += 1


# ---- the block and its wing
main = B.box("main", (-12.43, 0.0, 1.92), (12.43, TOP, 9.72))
wing = B.box("wing", (5.36, 0.0, -5.48), (12.43, TOP, 1.94))
for k, (x0, x1) in enumerate(((-12.43, -11.47), (-4.64, -3.67), (3.64, 4.74), (11.32, 12.43))):
    B.prism_x(f"foot{k}", [(9.7, 0.0), (14.37, 0.0), (14.37, 1.19), (9.7, TOP)], x0, x1)
# parapet (mitred, inward), plinth along the long walls
PL = [(-12.43, 1.92), (-12.43, 9.72), (12.43, 9.72), (12.43, -5.48), (5.36, -5.48), (5.36, 1.92)]
P = np.array(PL)
SGN = -1 if sum(P[i, 0] * P[(i + 1) % len(P), 1] - P[(i + 1) % len(P), 0] * P[i, 1] for i in range(len(P))) < 0 else 1
for i in range(len(P)):
    a, b = P[i], P[(i + 1) % len(P)]
    pa, pb = P[i - 1], P[(i + 2) % len(P)]

    def miter(v, u, w):  # inward offset of vertex v between edges (u->v) and (v->w)
        d1, d2 = (v - u) / np.linalg.norm(v - u), (w - v) / np.linalg.norm(w - v)
        n1, n2 = SGN * np.array([-d1[1], d1[0]]), SGN * np.array([-d2[1], d2[0]])
        m = (n1 + n2) / np.linalg.norm(n1 + n2)
        return v + m * 0.35 / (m @ n1)
    qa, qb = miter(a, pa, b), miter(b, a, pb)
    B.prism_y(f"parapet{i}", [tuple(a), tuple(b), tuple(qb), tuple(qa)], TOP - 0.02, TOP + 0.3)
B.box("plinth_s", (-12.49, 0.0, 9.72), (12.49, 1.2, 9.78))
B.box("plinth_n", (-12.49, 0.0, 1.86), (5.36, 1.2, 1.92))

# louvred vents: recess, slats, frame; red lamps over them (not those inside the wing)
for nm in ("louvre1", "louvre2", "louvre3"):
    for k, o in enumerate(rects(nm)):
        if o["normal"][2] < 0 and o["center"][0] > 5.3:
            continue
        inner = dict(o, w=o["w"] - 0.3, h=o["h"] - 0.3)
        B.recess(main, inner, 0.22)
        B.frame(f"{nm}_{k}f", inner, width=0.12, proud=0.06)
        n, bb = np.array(o["normal"]), np.array(o["b"])
        for s in range(7):
            c = np.array(o["center"]) + bb * (-(inner["h"] / 2) + (s + 0.5) * inner["h"] / 7) - n * 0.1
            B.obox(f"{nm}_{k}s{s}@avg", c, o["t"], o["b"], o["normal"], (inner["w"] + 0.02, 0.07, 0.14))
for nm in ("lamp1", "lamp2", "lamp3"):
    for k, o in enumerate(rects(nm)):
        if o["normal"][2] < 0 and o["center"][0] > 5.3:
            continue
        n = np.array(o["normal"])
        B.obox(f"{nm}_{k}", np.array(o["center"]) + n * 0.07, o["t"], o["b"], o["normal"], (0.4, 0.4, 0.18))
# doors and windows
DD = 0.16
doors = []
for k, o in enumerate(rects("door")):
    o = dict(o, center=[o["center"][0], (o["center"][1] + o["h"] / 2) / 2, o["center"][2]], h=o["center"][1] + o["h"] / 2)
    tgt = main if o["center"][2] > 1.95 else wing
    B.recess(tgt, o, DD)
    B.sill(f"dhood{k}@avg", o, proud=0.18, thick=0.1, overhang=0.12, top=True)
    doors.append((o, tgt))
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    c = np.array(o["center"])
    if abs(o["normal"][1]) > 0.2 or c[0] < -12.6:  # crane lattice cards: rebuilt as bars below
        continue
    hit = [t for d, t in doors if np.allclose(o["normal"], d["normal"], atol=0.05) and np.linalg.norm(c - d["center"]) < 1.5]
    if hit:
        B.recess(hit[0], o, 0.05, surface_shift=DD)
        continue
    tgt = main if c[2] > 1.95 else wing
    B.recess(tgt, o, 0.15)
    B.sill(f"sill{k}", o, proud=0.12, thick=0.07, overhang=0.08)
for nm in ("hatch1", "hatch2", "hatch3"):
    for k, o in enumerate(rects(nm)):
        c = o["center"]
        B.box(f"{nm}_{k}", (c[0] - o["w"] / 2 + 0.1, TOP - 0.02, c[2] - o["h"] / 2 + 0.1), (c[0] + o["w"] / 2 - 0.1, TOP + 0.35, c[2] + o["h"] / 2 - 0.1),
              chamfer=0.05)

# ---- yard: floor, walls (built inward from the original's cards) with coping and kerbs
T = 0.2
for nm, lo, hi in (("wall_w", (-20.57, 0, -20.47), (-20.57 + T, WALL, 1.93)), ("wall_n", (-20.57, 0, -20.47), (12.43, WALL, -20.47 + T)),
                   ("wall_e", (12.43 - T, 0, -20.47), (12.43, WALL, -5.48)), ("wall_sw", (-20.57, 0, 1.93 - T), (-12.43, WALL, 1.93))):
    B.box(nm, lo, hi)
    B.box(nm + "_cap@avg", (lo[0] - 0.06, WALL - 0.04, lo[2] - 0.06), (hi[0] + 0.06, WALL + 0.1, hi[2] + 0.06), chamfer=0.03)
    B.box(nm + "_kerb", (lo[0] - 0.05, 0, lo[2] - 0.05), (hi[0] + 0.05, 0.95, hi[2] + 0.05))

# ---- containers (3.74 m, in stacks) and small crates
G = 0.04
for k, (x0, x1, z0, z1) in enumerate([(-20.48, -16.59, -20.46, -16.72), (-16.59, -12.7, -20.46, -16.72),
                                      (-1.65, 2.18, -20.42, -16.4), (-1.65, 2.18, -16.4, -12.39),
                                      (8.63, 12.37, -20.43, -16.7), (8.63, 12.37, -16.7, -12.96), (8.63, 12.37, -12.96, -9.22),
                                      (8.63, 12.37, -9.22, -5.49), (-1.67, 2.07, -8.17, -4.43)]):
    crate(f"cont{k}", ((x0 + x1) / 2, (z0 + z1) / 2), 0.0, (x1 - x0 - G, 3.75 if k == 8 else 3.73, z1 - z0 - G))
crate("crate0", (7.73, -6.485), 0.0, (1.94, 1.86, 1.97), rail=0.12)
crate("crate1", (7.73, -6.485), 1.88, (1.94, 1.86, 1.97), rail=0.12)
crate("crate2", (-15.44, -10.13), 0.0, (1.865, 1.87, 1.865), yaw=-25, rail=0.12)
crate("crate3", (-9.98, -9.49), 2.8, (1.865, 1.87, 1.865), yaw=-25, rail=0.12)
crate("crate4", (0.07, -5.85), 3.77, (1.865, 1.87, 1.865), yaw=-55, rail=0.12)

# ---- crane: lattice tower, cab, boom, hoist mast
TX0, TX1, TZ0, TZ1, TY = -17.88, -15.29, -3.71, -1.28, 5.15
L = 0.45
for i, x in enumerate((TX0 + L / 2, TX1 - L / 2)):
    for j, z in enumerate((TZ0 + L / 2, TZ1 - L / 2)):
        B.box(f"leg{i}{j}{STEEL}", (x - L / 2, 0.0, z - L / 2), (x + L / 2, TY, z + L / 2))
for k, (y0, y1) in enumerate(((0.0, 0.16), (1.12, 1.44), (2.4, 2.71), (3.67, 3.99), (4.95, TY))):
    B.box(f"girt{k}a{STEEL}", (TX0 + L, y0, TZ0), (TX1 - L, y1, TZ0 + 0.2))
    B.box(f"girt{k}b{STEEL}", (TX0 + L, y0, TZ1 - 0.2), (TX1 - L, y1, TZ1))
    B.box(f"girt{k}c{STEEL}", (TX0, y0, TZ0 + L), (TX0 + 0.2, y1, TZ1 - L))
    B.box(f"girt{k}d{STEEL}", (TX1 - 0.2, y0, TZ0 + L), (TX1, y1, TZ1 - L))
B.loft_y("cab", [(-20.07, -2.77), (-16.86, 1.06), (-13.03, -2.15), (-16.24, -5.98)], 4.32,
         [(-19.1, -2.69), (-16.77, 0.09), (-14.0, -2.24), (-16.33, -5.01)], 6.54)
B.loft_y("cabroof@avg", [(-19.25, -2.7), (-16.78, 0.24), (-13.85, -2.23), (-16.32, -5.16)], 6.5,
         [(-19.1, -2.69), (-16.77, 0.09), (-14.0, -2.24), (-16.33, -5.01)], 6.68)
A0, B0, C0 = np.array([-17.35, 5.39, -3.86]), np.array([-16.9, 5.4, -3.3]), np.array([-15.45, 4.45, -4.93])
A1, B1, C1 = np.array([-10.25, 14.28, -9.56]), np.array([-9.99, 14.28, -9.24]), np.array([-9.97, 13.92, -9.62])
chords = [(A0, A1), (B0, B1), (C0, C1)]
for i, (p, q) in enumerate(chords):
    bar(f"chord{i}{STEEL}", p, q, 0.14)
NS = 12


def at(i, f):
    p, q = chords[i]
    return p + (q - p) * f


for s in range(NS + 1):
    f = s / NS
    for i in range(3):
        j = (i + 1) % 3
        bar(f"rung{s}_{i}{STEEL}", at(i, f), at(j, f), 0.07)
        if s < NS:
            bar(f"lace{s}_{i}{STEEL}", at(i, f), at(j, (s + 1) / NS), 0.06)
# the hoist: a diamond-plan lattice mast (the original's two crossed 1.54 m cards) from the boom head down to the
# hanging crate
MC = [(-10.82, -9.51), (-10.05, -10.28), (-9.28, -9.51), (-10.05, -8.74)]
MY0, MY1, MN = 4.7, 14.23, 12
for i, (x, z) in enumerate(MC):
    bar(f"mast{i}{STEEL}", (x, MY0, z), (x, MY1, z), 0.1)
for s in range(MN + 1):
    y = MY0 + 0.05 + (MY1 - MY0 - 0.1) * s / MN
    for i in range(4):
        (x0, z0), (x1, z1) = MC[i], MC[(i + 1) % 4]
        bar(f"mrung{s}_{i}{STEEL}", (x0, y, z0), (x1, y, z1), 0.06)
        if s < MN:
            y2 = MY0 + 0.05 + (MY1 - MY0 - 0.1) * (s + 1) / MN
            bar(f"mlace{s}_{i}{STEEL}", (x0, y, z0), (x1, y2, z1), 0.05)

print(B.dump())
