#!/usr/bin/env python3
"""CAD rebuild of the Union-type dropship (appearance dropshipdavion; dropshipsteiner and dropshipliao are the same
mesh with another house's texture and run this script through their own wrappers), in the original's frame.

    D=~/craft/solid/mc2/buildings/dropshipdavion
    python3 -I tools/art/cad_building.py openings dropshipdavion > $D/openings.json
    python3 -I tools/cad/dropshipdavion_cad.py $D > $D/dropshipdavion.json
    solidcraft-cli run $D/dropshipdavion.json --out $D/dropshipdavion.obj
    python3 -I tools/art/cad_building.py bake dropshipdavion $D/dropshipdavion.obj --max-res 4096

Measured from game/assets/objects/dropshipdavion.glb (node Dropship; LitWin_Dropship is the night overlay): a
12-sided hull, vertices at 15 + 30k degrees, rings (y, vertex radius) 1.74/11.30, 16.54/15.37, 21.51/15.37,
27.03/13.56, 32.01/7.68 and the apex at 34.67. Four landing pods on the diagonals (a six-sided leg to 7.43 m that
tapers to a 2.35 x 2.54 m top at 13.68 m, flat against the hull side), four triangular struts from the hull to the
pods, and four ramp doors on the axes (a wedge rooted in the hull with a 0.86 m raised, 45-degree chamfered panel).
The hull is meant to be round (Lee, I77): a 36-sided body through the original's ring heights at the vertex radius,
so it is nowhere behind the original facets (bake's depth AO stays off) and the painted bands line up ring for ring.
Relief: belts at the four upper rings, seam ribs at the original's 12 facet edges (16.5..27 m, where the art's
panels meet), the cut-out portholes as 15 cm recesses (glass at the back), a lip ring round the emblem.
The pods, struts and doors keep their flat faces: they are armoured plate, faceted by design.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, cad, cad_dir  # noqa: E402

D = Path(sys.argv[1])
B = Builder()
N = 36  # vertices at 15 + 10k: the original's 12 vertex directions, and every porthole on a facet centre
RINGS = [(1.74, 11.30), (16.54, 15.37), (21.51, 15.37), (27.03, 13.56), (32.01, 7.68)]
APEX = 34.67


def ngon(r, n=N, a0=15.0):
    return [(r * math.cos(math.radians(a0 + 360.0 * k / n)), r * math.sin(math.radians(a0 + 360.0 * k / n))) for k in range(n)]


def poly(r):  # (x, z) list for the prism helpers; counter-clockwise from above is (x, -z) in CAD, fine either way
    return [(x, z) for x, z in ngon(r)]


def rot(p, deg):
    a = math.radians(deg)
    x, y, z = p
    return (x * math.cos(a) - z * math.sin(a), y, x * math.sin(a) + z * math.cos(a))


def hull_r(y):
    for (y0, r0), (y1, r1) in zip(RINGS, RINGS[1:] + [(APEX, 0.0)]):
        if y0 <= y <= y1:
            return r0 + (r1 - r0) * (y - y0) / (y1 - y0), (y0, r0, y1, r1)
    return RINGS[0][1], RINGS[0] + RINGS[1]


def section(pts):
    """A planar polygon given in game coordinates -> a sketch on its own plane (for solid.loft)."""
    P = np.array([cad(p) for p in pts], float)
    o = P[0]
    xd = P[1] - P[0]
    xd /= np.linalg.norm(xd)
    nrm = np.cross(P[1] - P[0], P[2] - P[0])
    k = 2
    while np.linalg.norm(nrm) < 1e-6:
        k += 1
        nrm = np.cross(P[1] - P[0], P[k] - P[0])
    nrm /= np.linalg.norm(nrm)
    yd = np.cross(nrm, xd)
    B.n_sk += 1
    name = f"sk{B.n_sk}"
    B.c("sketch.create", plane={"origin": [round(float(v), 3) for v in o], "x_dir": [round(float(v), 6) for v in xd],
                                "y_dir": [round(float(v), 6) for v in yd]}, name=name)
    B.c("sketch.line", points=[[round(float((q - o) @ xd), 2), round(float((q - o) @ yd), 2)] for q in P], closed=True)
    B.c("sketch.finish")
    return name


def loft(name, *secs):
    B.c("solid.loft", sections=[{"sketch": section(s)} for s in secs], body_name=name, operation="new")
    return name


# ---- hull: five 36-sided bands through the original rings
for k, ((y0, r0), (y1, r1)) in enumerate(zip(RINGS, RINGS[1:])):
    if abs(r0 - r1) < 1e-6:
        B.prism_y(f"hull{k}", poly(r0), y0, y1)
    else:
        B.loft_y(f"hull{k}", poly(r0), y0, poly(r1), y1)
B.loft_y("cap", poly(RINGS[-1][1]), RINGS[-1][0], poly(0.05), APEX)


def belt(name, y, r, h=0.18, proud=0.07):
    outer = B.prism_y(name, poly(r + proud), y - h / 2, y + h / 2)
    B.cut(outer, B.prism_y(f"{name}_core", poly(r - 0.6), y - h, y + h))


for k, (y, r) in enumerate(RINGS[1:]):
    belt(f"belt{k}@avg", y, r)

# ---- seam ribs on the original facet edges, 16.5..27 m
for a in range(15, 360, 30):
    for (y0, r0), (y1, r1) in ((RINGS[1], RINGS[2]), (RINGS[2], RINGS[3])):
        p0 = np.array(rot((r0, y0 + 0.1, 0.0), a))
        p1 = np.array(rot((r1, y1 - 0.1, 0.0), a))
        t = p1 - p0
        L = np.linalg.norm(t)
        t /= L
        out = np.array(rot((1.0, 0.0, 0.0), a))
        n = out - t * (out @ t)
        n /= np.linalg.norm(n)
        b = np.cross(n, t)
        B.obox(f"rib{a}_{y0:.0f}@avg", (p0 + p1) / 2 + n * 0.02, t, b, n, (L, 0.16, 0.08))

# ---- portholes: the cut-outs on the hull as recesses, re-seated on the round surface
ops = json.load(open(D / "openings.json"))["openings"]
for o in ops:
    c = np.array(o["center"], float)
    if c[1] < 15.0 or o["w"] > 1.5:  # pods' foot slits (ground level) and the long window strip stay painted glass
        continue
    phi = math.atan2(c[2], c[0])
    r, (y0, r0, y1, r1) = hull_r(c[1])
    radial = np.array([math.cos(phi), 0.0, math.sin(phi)])
    n = radial * (y1 - y0) + np.array([0.0, r0 - r1, 0.0])
    n /= np.linalg.norm(n)
    t = np.array([-math.sin(phi), 0.0, math.cos(phi)])
    b = np.cross(n, t)
    if b[1] < 0:
        t = -t
        b = -b
    centre = np.array([r * math.cos(phi) * math.cos(math.radians(5.0)), c[1], r * math.sin(phi) * math.cos(math.radians(5.0))])
    target = "hull1" if 16.54 <= c[1] < 21.51 else "hull2" if 21.51 <= c[1] < 27.03 else "hull3"
    B.recess(target, dict(o, center=centre.tolist(), normal=n.tolist(), t=t.tolist(), b=b.tolist()), 0.15)

# ---- emblem lip
belt("emblemlip@avg", RINGS[-1][0] + 0.05, RINGS[-1][1], h=0.14, proud=0.06)

# ---- landing pods (diagonals), struts and ramp doors (axes); local frame u = radial, v = tangential
POD0 = [(16.23, -3.755), (16.23, 3.755), (20.71, 3.755), (22.94, 1.70), (22.94, -1.70), (20.71, -3.755)]
POD_MID = [(16.23, -3.42), (16.23, 3.42), (20.27, 3.42), (22.35, 1.53), (22.35, -1.53), (20.27, -3.42)]
POD_TOP = [(16.23, -1.27), (16.23, 1.27), (18.58, 1.27), (18.58, 0.42), (18.58, -0.42), (18.58, -1.27)]


def local(u, y, v, a):
    return rot((u, y, v), a)


for k, a in enumerate((45, 135, 225, 315)):
    bot = [local(u, 0.02, v, a) for u, v in POD0]
    mid = [local(u, 7.43, v, a) for u, v in POD_MID]
    top = [local(u, 13.68, v, a) for u, v in POD_TOP]
    loft(f"pod{k}", bot, mid)
    loft(f"podtop{k}", mid, top)
    s_in = [local(11.56, 11.13, 0.86, a), local(11.56, 11.13, -0.86, a), local(11.55, 4.71, 0.0, a)]
    s_out = [local(16.27, 8.56, 0.86, a), local(16.27, 8.56, -0.86, a), local(16.26, 2.14, 0.0, a)]
    loft(f"strut{k}", s_in, s_out)

# door, in the +x frame: wedge (x, y) at z = +-5.57, raised panel 0.86 m proud with 45-degree sides
WEDGE = [(5.32, 3.65), (10.9, 1.32), (14.87, 16.65), (9.07, 18.15)]
d = np.array([14.87 - 10.9, 16.65 - 1.32])
d /= np.linalg.norm(d)
nn = np.array([d[1], -d[0]])
for k, a in enumerate((0, 90, 180, 270)):
    sec = lambda z: [local(x, y, z, a) for x, y in WEDGE]  # noqa: E731
    loft(f"door{k}", sec(-5.57), sec(5.57))
    base0, base1 = np.array([10.9, 1.32]), np.array([14.87, 16.65])
    lo = [base0 - nn * 0.02, base1 - nn * 0.02]
    hi = [base0 + nn * 0.86 + d * 0.85, base1 + nn * 0.86 - d * 0.85]
    sa = [local(*lo[0], -5.57, a), local(*lo[0], 5.57, a), local(*lo[1], 5.57, a), local(*lo[1], -5.57, a)]
    sb = [local(*hi[0], -4.71, a), local(*hi[0], 4.71, a), local(*hi[1], 4.71, a), local(*hi[1], -4.71, a)]
    loft(f"doorpanel{k}", [(p[0], p[1], p[2]) for p in sa], [(p[0], p[1], p[2]) for p in sb])

print(B.dump())
