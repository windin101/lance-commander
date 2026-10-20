#!/usr/bin/env python3
"""CAD rebuild of the HPG generator (appearance hpg_gen), in the original's frame.

    D=~/craft/solid/mc2/buildings/hpg_gen
    python3 -I tools/art/cad_building.py openings hpg_gen > $D/openings.json      # none: the art is opaque
    C="python3 -I tools/art/cad_building.py decal hpg_gen 0"                       # rects are texture px / 512:
    slot1..3 (55..127|139..259|270..338, 134..141)   cush0..6 (113,146,181,213,247,281,315,345 | 18..55)
    roofpanel (408,18,490,318)   vent (258,408,310,485)   door (35,440,80,482)
    python3 -I tools/cad/hpg_gen_cad.py $D > $D/hpg_gen.json
    solidcraft-cli run $D/hpg_gen.json --out $D/hpg_gen.obj
    python3 -I tools/art/cad_building.py bake hpg_gen $D/hpg_gen.obj

Measured from game/assets/objects/hpg_gen.glb (94 triangles): two battered blocks on 1.51 m plinths (A: x
-11.53..-2.65, z +-10.78, roof 5.86; B: x 1.03..9.92, z 2.21..10.79, upright on its -z side), a 3.28 m link
block between them (x -3.28..1.81, z 2.41..8.65), and the generator hall: two gabled bays (z -10.22..-3.98 and
-3.98..2.26), eaves 6.71 / ridge 10.61, every vertical corner and gable end chamfered 0.93 m (end eaves 6.17,
apex 9.53). The hall's long walls and roof are painted louvres (texture v 0.488 + 0.023 k).
Relief: the louvres are real slats (trapezoid, 6 cm proud) on every white band, a ridge cap and eave gutters on
each bay; block A's wall slots are 15 cm recesses and its cushion panels 8 cm proud; the painted roof panels of
both blocks are 10 cm recesses inside their tan borders; ledges ring the plinths; the link block's door is a 25 cm
recess and its roof vent a real housing.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, cad  # noqa: E402

D = Path(sys.argv[1])
B = Builder()
PL, TOP = 1.51, 5.86


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def rects(name):
    return json.load(open(D / f"decal_{name}.json"))["rects"]


def proud(name, o, p, shrink=0.0):
    n, t, b = (np.array(o[k], float) for k in ("normal", "t", "b"))
    return B.obox(name, np.array(o["center"]) + n * (p / 2 - 0.02), t, b, n, (o["w"] - shrink, o["h"] - shrink, p + 0.02))


def loft_z(name, prof0, z0, prof1, z1):
    """An (x, y) profile at game z0 lofted to another (same vertex count) at z1."""
    secs = []
    for prof, z in ((prof0, z0), (prof1, z1)):
        B.n_sk += 1
        sk = f"sk{B.n_sk}"
        B.c("sketch.create", plane={"origin": cad((0, 0, z)), "x_dir": [1, 0, 0], "y_dir": [0, 0, 1]}, name=sk)
        B.c("sketch.line", points=[[round(x * 1000, 2), round(y * 1000, 2)] for x, y in prof], closed=True)
        B.c("sketch.finish")
        secs.append({"sketch": sk})
    B.c("solid.loft", sections=secs, body_name=name, operation="new")
    return name


def edge_bands(prefix, poly, y0, y1, out, skip=()):
    for i in range(len(poly)):
        if i in skip:
            continue
        a, c = np.array(poly[i]), np.array(poly[(i + 1) % len(poly)])
        e = unit(c - a)
        nrm = np.array([e[1], -e[0]])
        mid = (a + c) / 2 + nrm * out / 2
        t, n = np.array([e[0], 0, e[1]]), np.array([nrm[0], 0, nrm[1]])
        B.obox(f"{prefix}{i}", (mid[0], (y0 + y1) / 2, mid[1]), t, np.cross(n, t), n, (np.linalg.norm(c - a) + 2 * out, y1 - y0, out))


def rib(name, p, n, z0, z1, base=0.36, face=0.24, h=0.06, sink=0.02):
    """A trapezoid slat on an (x, y) surface point p with outward normal n, running along z."""
    p, n = np.asarray(p, float), unit(n)
    t = np.array([-n[1], n[0]])
    poly = [p - t * base / 2 - n * sink, p + t * base / 2 - n * sink, p + t * face / 2 + n * h, p - t * face / 2 + n * h]
    return B.prism_z(name, [tuple(q) for q in poly], z0, z1)


# ---- battered blocks (counter-clockwise in x, z; B's -z side upright against the hall)
A_BOT = [(-11.53, -10.78), (-2.65, -10.78), (-2.65, 10.78), (-11.53, 10.78)]
A_TOP = [(-10.02, -9.26), (-4.06, -9.26), (-4.06, 9.26), (-10.02, 9.26)]
B_BOT = [(1.03, 2.21), (9.92, 2.21), (9.92, 10.79), (1.03, 10.79)]
B_TOP = [(2.44, 2.21), (8.4, 2.21), (8.4, 9.27), (2.44, 9.27)]
B.prism_y("plinthA", A_BOT, 0.0, PL)
blockA = B.loft_y("blockA", A_BOT, PL, A_TOP, TOP)
B.prism_y("plinthB", B_BOT, 0.0, PL)
blockB = B.loft_y("blockB", B_BOT, PL, B_TOP, TOP)
link = B.box("link", (-3.28, 0.0, 2.41), (1.81, 3.28, 8.65))

def offset(poly, d):
    """Mitred outward offset of a convex counter-clockwise (x, y) polygon; vertices below the ground clamp to it."""
    n = len(poly)
    out = []
    for i in range(n):
        p0, p1, p2 = (np.array(poly[(i + j) % n], float) for j in (-1, 0, 1))
        n0, n1 = (lambda e: np.array([e[1], -e[0]]) / np.linalg.norm(e))(p1 - p0), (lambda e: np.array([e[1], -e[0]]) / np.linalg.norm(e))(p2 - p1)
        m = n0 + n1
        q = p1 + m / np.dot(m, n1) * d
        out.append((q[0], max(0.0, q[1])))
    return out


def band(prof, out, inn):
    """The profile's outline except its ground edge, as a band from inn inside to out outside."""
    o, i = offset(prof, out), offset(prof, -inn)
    chain = list(range(1, len(prof))) + [0]  # bottom-right .. round the top .. bottom-left
    return [o[j] for j in chain] + [i[j] for j in chain[::-1]]


# ---- generator hall: two chamfered gabled bays
F = [(-1.32, 0.0), (12.19, 0.0), (12.19, 6.71), (5.43, 10.61), (-1.32, 6.71)]
I = [(-0.39, 0.0), (11.25, 0.0), (11.25, 6.17), (5.43, 9.53), (-0.39, 6.17)]
BAYS = ((-10.22, -9.29, -4.92, -3.98), (-3.98, -3.05, 1.32, 2.26))
for k, (za, z0, z1, zb) in enumerate(BAYS):
    B.prism_z(f"bay{k}", F, z0, z1)
    loft_z(f"bay{k}_e0", I, za, F, z0)
    loft_z(f"bay{k}_e1", F, z1, I, zb)

# louvre slats on the painted white bands: roof (v 0.48 ridge .. 0.708 eave), walls (v 0.477 eave .. 0.703 ground)
V = [0.4883, 0.5117, 0.5332, 0.5566, 0.5801, 0.6035, 0.627, 0.6504, 0.6758, 0.6973]
RIDGE = np.array([5.43, 10.61])
for k, (za, z0, z1, zb) in enumerate(BAYS):
    for j, v in enumerate(V):
        f = (v - 0.48) / (0.708 - 0.48)
        for s, eave in (("r", np.array([12.19, 6.71])), ("l", np.array([-1.32, 6.71]))):
            d = eave - RIDGE
            n = np.array([-d[1], d[0]]) if s == "r" else np.array([d[1], -d[0]])
            rib(f"slat{k}{s}{j}", RIDGE + d * f, n, z0, z1)
        y = 6.71 * (1 - (v - 0.477) / (0.703 - 0.477))
        if 0.3 < y < 6.45:
            rib(f"wslat{k}r{j}", (12.19, y), (1, 0), z0, z1)
            rib(f"wslat{k}l{j}", (-1.32, y), (-1, 0), z0, z1)
    # barge boards over the slat ends where each bay meets its chamfered ends
    for e, zz in enumerate((z0, z1)):
        B.prism_z(f"barge{k}{e}", band(F, 0.12, 0.04), zz - 0.12, zz + 0.12)
    # ridge cap and eave gutters
    B.prism_z(f"ridge{k}", [(5.43 - 0.35, 10.61 - 0.2 - 0.02), (5.43 + 0.35, 10.61 - 0.2 - 0.02), (5.43 + 0.3, 10.61 + 0.08),
                            (5.43 - 0.3, 10.61 + 0.08)], z0 - 0.05, z1 + 0.05)
    for s, x in ((1, 12.19), (-1, -1.32)):
        B.box(f"gutter{k}{'rl'[s < 0]}@8c8c84", (min(x, x + s * 0.22), 6.5, z0), (max(x, x + s * 0.22), 6.74, z1))

# ---- block relief
for k in (1, 2, 3):
    for o in rects(f"slot{k}"):
        B.recess(blockA if o["center"][0] < 0 else blockB, o, 0.15)
for k in range(7):
    for m, o in enumerate(rects(f"cush{k}")):
        proud(f"cush{k}_{m}", o, 0.08, shrink=0.14)
for o in rects("roofpanel"):
    B.recess(blockA if o["center"][0] < 0 else blockB, o, 0.10)
edge_bands("ledgeA", A_BOT, PL - 0.12, PL + 0.04, 0.10)
edge_bands("ledgeB", B_BOT, PL - 0.12, PL + 0.04, 0.10, skip=(0,))
for o in rects("door"):
    if o["normal"][2] > 0:  # the -z door faces the hall 15 cm away
        B.recess(link, o, 0.25)
for o in rects("vent"):
    proud("vent", o, 0.3, shrink=0.2)

print(B.dump())
