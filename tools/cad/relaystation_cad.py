#!/usr/bin/env python3
"""CAD rebuild of the relay station (appearance relaystation), in the original's frame.

    D=~/craft/solid/mc2/buildings/relaystation
    python3 -I tools/art/cad_building.py openings relaystation > $D/openings.json
    python3 -I tools/art/cad_building.py decal relaystation 0 0.212 0.752 0.532 0.996 > $D/decal_roller.json
    python3 -I tools/art/cad_building.py decal relaystation 0 0.575 0.835 0.695 0.996 > $D/decal_door.json
    python3 -I tools/cad/relaystation_cad.py $D > $D/relaystation.json
    solidcraft-cli run $D/relaystation.json --out $D/relaystation.obj
    python3 -I tools/art/cad_building.py bake relaystation $D/relaystation.obj

Measured from game/assets/objects/relaystation.glb (node RelayStation): an 8.14 x 5.56 m hut, walls 3.47 m, under a
roof that slopes from the eaves at x = +-4.07 to a flat top (|x| < 1.97) at 4.99 m; a lattice tower on the flat top,
a frustum from 2.4 m square at 4.99 m to 1.1 m at 16.05 m, drawn in the original as crossed alpha cards (two cards
a face, three X panels a card); four microwave dishes (pentagonal cones in the original) on the tower.
Relief: the tower is a real lattice (legs, seven rings of girts, X bracing on every panel, on the cards' painted
members); the dishes are round plates with a rim, a hub back to the tower and a feed horn; the roof is a 25 cm slab
over the walls with a 15 cm overhang and real standing seams on its seven painted seam lines (texture u 0.291 +
0.0625 k); the painted brick corners are proud piers; windows are 20 cm recesses with sills and mullions; the
roller door a 30 cm recess in a proud frame, the side door 12 cm with its window a further 5 cm; the gable louvre a
10 cm recess.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, cad, cad_dir, axis_angle  # noqa: E402

D = Path(sys.argv[1])
XW, ZW, EAVE, TOP, XT = 4.07, 2.78, 3.47, 4.99, 1.97
T, OVER = 0.25, 0.15
B = Builder()


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def bar(name, p0, p1, w, d=None):
    """A square bar (w x d) from p0 to p1."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    b = unit(p1 - p0)
    ref = np.array([0.0, 1.0, 0.0]) if abs(b[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
    t = unit(np.cross(b, ref))
    n = np.cross(t, b)
    return B.obox(name, (p0 + p1) / 2, t, b, n, (w, np.linalg.norm(p1 - p0), d or w))


def turn_z_to(name, n):
    """Rotate a body built about the CAD Z axis so that axis points along game direction n."""
    a, b = np.array([0.0, 0.0, 1.0]), unit(cad_dir(n))
    v, c = np.cross(a, b), float(np.dot(a, b))
    if np.linalg.norm(v) < 1e-9:
        if c > 0:
            return
        m = np.diag([1.0, -1.0, -1.0])
    else:
        vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
        m = np.eye(3) + vx + vx @ vx / (1 + c)
    ax, deg = axis_angle(m)
    if ax is not None:
        B.c("solid.move", bodies=[name], axis=[round(float(x), 6) for x in ax], angle=f"{deg:.4f} deg")


def cyl(name, base, n, r, h):
    B.c("solid.cylinder", radius=round(r * 1000, 2), height=round(h * 1000, 2), base=cad(base),
        axis=[round(float(x), 6) for x in unit(cad_dir(n))], body_name=name, operation="new")


# ---- roof surface, parametrised by the texture's u (0.231 .. 0.733)
U = [(0.231, -XW, EAVE), (0.381, -XT, TOP), (0.583, XT, TOP), (0.733, XW, EAVE)]


def roof_pt(u):
    for (u0, x0, y0), (u1, x1, y1) in zip(U, U[1:]):
        if u <= u1 + 1e-9:
            f = (u - u0) / (u1 - u0)
            return np.array([x0 + f * (x1 - x0), y0 + f * (y1 - y0)]), unit([-(y1 - y0), x1 - x0])
    raise ValueError(u)


slope = (TOP - EAVE) / (XW - XT)
prof_top = [(-XW - OVER, EAVE - slope * OVER), (-XT, TOP), (XT, TOP), (XW + OVER, EAVE - slope * OVER)]
prof_bot = [(x, y - T) for x, y in prof_top]

# ---- hut: walls up under the slab, the slab
walls = B.prism_z("walls", [(-XW, 0.0), (XW, 0.0)] + [(XW, EAVE - T), (XT, TOP - T), (-XT, TOP - T), (-XW, EAVE - T)], -ZW, ZW)
B.prism_z("roof", prof_top + prof_bot[::-1], -ZW - OVER, ZW + OVER)

# standing seams on the painted seam lines
for k in range(7):
    u = 0.291 + 0.0625 * k
    pts = []
    for du in (-0.004, 0.004):
        p, n = roof_pt(u + du)
        pts.append(p)
    p0, p1 = pts
    _, n = roof_pt(u)
    poly = [tuple(p0 - n * 0.02), tuple(p1 - n * 0.02), tuple(p1 + n * 0.05), tuple(p0 + n * 0.05)]
    B.prism_z(f"seam{k}@avg", poly, -ZW - OVER, ZW + OVER)

# brick corner piers, proud 8 cm, wrapping each corner
P = 0.08
for k, (sx, sz) in enumerate(((1, 1), (-1, 1), (1, -1), (-1, -1))):
    xa, xb = sorted((sx * (XW - 0.44), sx * (XW + P)))
    za, zb = sorted((sz * ZW, sz * (ZW + P)))
    B.box(f"pier{k}a", (xa, 0.0, za), (xb, EAVE - T, zb))
    xa, xb = sorted((sx * XW, sx * (XW + P)))
    za, zb = sorted((sz * (ZW - 0.33), sz * ZW))
    B.box(f"pier{k}b", (xa, 0.0, za), (xb, EAVE - T, zb))

# ---- windows (the hut's cut-outs; the tower's are its lattice)
door = json.load(open(D / "decal_door.json"))["rects"][0]
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    if o["center"][1] > 4.0:
        continue
    if o["w"] < 0.6:  # the side door's window: cut deeper once the door is recessed, below
        continue
    B.recess(walls, o, 0.20)
    B.sill(f"sill{k}", o, proud=0.10, thick=0.06, overhang=0.06)
    B.sill(f"hood{k}", o, proud=0.14, thick=0.05, overhang=0.08, top=True)
    panes = max(1, round(o["w"] / 1.0))
    for m in range(1, panes):
        c = np.array(o["center"]) + np.array(o["t"]) * (o["w"] * (m / panes - 0.5)) - np.array(o["normal"]) * 0.1
        B.obox(f"mullion{k}_{m}", c, o["t"], o["b"], o["normal"], (0.06, o["h"], 0.2))

# ---- doors
FR = 0.25
for o in json.load(open(D / "decal_roller.json"))["rects"]:
    n, t, b = (np.array(o[q], float) for q in ("normal", "t", "b"))
    c = np.array(o["center"])
    B.recess(walls, o, 0.30)
    B.obox("rframe_t", c + b * (o["h"] / 2 + 0.1) + n * 0.03, t, b, n, (o["w"] + 2 * FR, 0.2, 0.08))
    for s in (1, -1):
        B.obox(f"rframe_{'lr'[s > 0]}", c + t * s * (o["w"] / 2 + FR / 2) + n * 0.03 - b * 0.0, t, b, n, (FR, o["h"], 0.08))
n, t, b = (np.array(door[q], float) for q in ("normal", "t", "b"))
c = np.array(door["center"])
inner = dict(door, w=door["w"] - 0.24, h=door["h"] - 0.12, center=list(c - b * 0.06))
B.recess(walls, inner, 0.12)
for o in json.load(open(D / "openings.json"))["openings"]:
    if o["center"][1] < 4.0 and o["w"] < 0.6:
        B.recess(walls, o, 0.05, surface_shift=0.12)
# gable louvre over the window band (+z wall): texture u 0.327..0.415, v 0.27..0.337
lv = dict(center=[0.0, 3.95, ZW], normal=[0, 0, 1], t=[1, 0, 0], b=[0, 1, 0], w=0.92, h=0.78)
B.recess(walls, lv, 0.10)
B.sill("louvre_sill", lv, proud=0.08, thick=0.05, overhang=0.04)

# ---- tower: legs, girts, X bracing on the cards' members
def corner(y, sx, sz):
    f = (y - TOP) / (16.05 - TOP)
    h = 1.2 + f * (0.55 - 1.2)
    return np.array([sx * h, y, sz * h])


LEVELS = [TOP + k * (16.05 - TOP) / 6 for k in range(7)]
CORNERS = [(1, 1), (-1, 1), (-1, -1), (1, -1)]
for k, (sx, sz) in enumerate(CORNERS):
    bar(f"leg{k}@6a6e72", corner(TOP - 0.05, sx, sz), corner(16.12, sx, sz), 0.16)
for j, y in enumerate(LEVELS):
    for k in range(4):
        a, b_ = corner(y, *CORNERS[k]), corner(y, *CORNERS[(k + 1) % 4])
        bar(f"girt{j}_{k}", a, b_, 0.09)
for j in range(6):
    y0, y1 = LEVELS[j], LEVELS[j + 1]
    for k in range(4):
        c0, c1 = CORNERS[k], CORNERS[(k + 1) % 4]
        bar(f"brace{j}_{k}a", corner(y0, *c0), corner(y1, *c1), 0.07)
        bar(f"brace{j}_{k}b", corner(y0, *c1), corner(y1, *c0), 0.07)

# ---- dishes: (apex behind the plate, the five rim points of the original's pentagonal cone)
DISHES = [
    ((-0.64, 10.97, 0.60), [(-1.43, 9.51, 1.12), (-2.12, 10.6, -0.17), (-1.52, 12.3, 0.15), (-0.46, 12.25, 1.64), (-0.41, 10.53, 2.23)]),
    ((0.67, 12.78, 0.41), [(0.97, 11.45, 0.47), (0.6, 12.28, 1.7), (0.99, 13.72, 1.43), (1.6, 13.79, 0.03), (1.41, 12.38, -0.63)]),
    ((-0.56, 12.98, -0.48), [(-0.76, 11.69, -1.0), (0.48, 12.52, -1.31), (0.1, 13.99, -1.22), (-1.38, 14.07, -0.85), (-1.91, 12.65, -0.72)]),
    ((0.37, 15.83, -0.36), [(0.69, 14.56, -0.98), (1.69, 15.3, -0.1), (1.43, 16.79, -0.24), (0.27, 16.98, -1.21), (-0.19, 15.6, -1.67)]),
]
def ngon(r, k, rot=0.0):
    return [(r * math.cos(rot + 2 * math.pi * i / k), r * math.sin(rot + 2 * math.pi * i / k)) for i in range(k)]


def place(name, n, at):
    """A body built about the game y axis at the origin: turn y onto n, move to `at`."""
    turn_z_to(name, n)
    B.c("solid.move", bodies=[name], translate=cad(at))


def rod(name, base, n, r, h, k=8):
    B.prism_y(name, ngon(r, k, math.pi / k), 0.0, h)
    place(name, n, base)


for k, (apex, ring) in enumerate(DISHES):
    ring, apex = np.array(ring), np.array(apex)
    ctr = ring.mean(0)
    n = unit(ctr - apex)
    r = float(np.linalg.norm(ring - ctr, axis=1).mean()) * 0.88
    back = float(np.dot(ctr - apex, n))
    # the plate, a shallow cone behind it (the original's shape), a rim of 16 bars, the hub and the feed horn
    B.prism_y(f"dish{k}", ngon(r, 16), -0.03, 0.03)
    place(f"dish{k}", n, ctr)
    B.loft_y(f"dishback{k}", ngon(r * 0.98, 16), -0.03, ngon(r * 0.35, 16), -back * 0.8)
    place(f"dishback{k}", n, ctr)
    pts = [np.array([x, 0.0, z]) for x, z in ngon(r - 0.02, 16)]
    for i in range(16):
        nm = f"dishrim{k}_{i}@d8d8d4"
        a, b_ = pts[i], pts[(i + 1) % 16]
        d = unit(b_ - a)
        B.obox(nm, (a + b_) / 2 + np.array([0, 0.05, 0]), unit(np.cross(d, [0, 1, 0])), d, -np.cross(unit(np.cross(d, [0, 1, 0])), d) * -1,
               (0.06, float(np.linalg.norm(b_ - a)) + 0.03, 0.06))
        place(nm, n, ctr)
    rod(f"dishhub{k}@6a6e72", apex - n * 0.1, n, 0.2, back * 0.3 + 0.1)
    rod(f"dishfeed{k}@b4b4ae", ctr, n, 0.035, r * 0.55, 6)
    rod(f"dishhorn{k}@b4b4ae", ctr + n * r * 0.55, n, 0.08, 0.12)

print(B.dump())
