#!/usr/bin/env python3
"""CAD rebuild of the geodesic dome with its equipment tower (appearance geodesicdome), in the original's frame.

    D=~/craft/solid/mc2/buildings/geodesicdome
    python3 -I tools/art/cad_building.py openings geodesicdome > $D/openings.json
    python3 -I tools/art/cad_building.py decal geodesicdome 0 0.163 0.835 0.24 0.935 > $D/decal_door.json
    python3 -I tools/art/cad_building.py decal geodesicdome 0 0.17 0.05 0.24 0.135 > $D/decal_louvre.json
    python3 -I tools/art/cad_building.py decal geodesicdome 0 0.17 0.195 0.245 0.29 > $D/decal_hatch.json
    python3 -I tools/cad/geodesicdome_cad.py $D > $D/geodesicdome.json
    solidcraft-cli run $D/geodesicdome.json --out $D/geodesicdome.obj
    python3 -I tools/art/cad_building.py bake geodesicdome $D/geodesicdome.obj --texel 0.015

Measured from game/assets/objects/geodesicdome.glb (40 dome triangles, matched to named vertices): about
x = 4.355, z = 0: a base decagon r 6.505 m at 0.45 m (vertices every 36 degrees from +x), a zig-zag ring of
five r 5.82 at 3.36 m (-18 + 72k degrees) and five r 5.535 at 3.87 m (18 + 72k), a pentagon r 3.42 at 5.98 m
(-18 + 72k) and the apex at 6.96 m. A 45 cm decagonal pad (r 7.31) with a tongue to z 10.98 carries an
octagonal tower (lofted from its 0.45 m to its 5.59 m outline) joined to the dome by a corridor, and two masts.
Relief: every dome triangle is its own 25 cm panel, outer face on the original facet, with a 20 cm strut
over every edge (the painted frame lines), so the dome reads as a real geodesic frame; the five upper slot windows
are 15 cm recesses with hoods; the two painted doors are 20 cm recesses with their windows a further 5 cm in;
the tower's painted louvres and hatches are recesses with frames and its top a cap plate; the pad's top edge is
chamfered; the masts keep the original's sizes, with a chamfered head.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, axis_angle, cad, cad_dir  # noqa: E402

D = Path(sys.argv[1])
B = Builder()
CX = 4.355


def pol(r, deg, y):
    a = math.radians(deg)
    return np.array([CX + r * math.cos(a), y, r * math.sin(a)])


V = {f"B{k}": pol(6.505, 36 * k, 0.45) for k in range(10)}
for k in range(5):
    V[f"L{k}"] = pol(5.82, -18 + 72 * k, 3.36)
    V[f"H{k}"] = pol(5.535, 18 + 72 * k, 3.87)
    V[f"P{k}"] = pol(3.42, -18 + 72 * k, 5.98)
V["A"] = np.array([CX, 6.96, 0.0])
FACES = []
for k in range(5):
    k1 = (k + 1) % 5
    FACES += [(f"P{k}", f"P{k1}", f"H{k}"), (f"B{2 * k}", f"H{k}", f"B{2 * k + 1}"), (f"L{k}", f"B{2 * k}", f"B{(2 * k - 1) % 10}"),
              (f"L{k}", f"H{k}", f"B{2 * k}"), (f"L{k1}", f"B{2 * k + 1}", f"H{k}"), (f"A", f"P{k1}", f"P{k}"),
              (f"L{k}", f"P{k}", f"H{k}"), (f"L{k1}", f"H{k}", f"P{k1}")]
# the last ring entry above pairs L(k) with H(k-1); fix it to the original's (L0 H4 P0 ...)
FACES = [f for f in FACES if not (f[0].startswith("L") and f[1].startswith("H") and f[2].startswith("P"))]
for k in range(5):
    FACES.append((f"L{k}", f"H{(k - 1) % 5}", f"P{k}"))
assert len(FACES) == 40
CEN = np.array([CX, 0.0, 0.0])
T = 0.25


def outward(a, b, c):
    n = np.cross(b - a, c - a)
    n /= np.linalg.norm(n)
    if n @ ((a + b + c) / 3 - CEN) < 0:
        n = -n
    return n


def plate(name, a, b, c, thick):
    """A triangular panel: outer face on (a, b, c), `thick` deep inward."""
    n = outward(a, b, c)
    u = (b - a) / np.linalg.norm(b - a)
    v = np.cross(n, u)
    pts = [(0.0, 0.0), (np.linalg.norm(b - a), 0.0), (float((c - a) @ u), float((c - a) @ v))]
    sk = B._sketch("XY", 0.0)
    B.c("sketch.line", points=[[round(x * 1000, 2), round(y * 1000, 2)] for x, y in pts], closed=True)
    B.c("sketch.finish")
    B.c("solid.extrude", distance=round(thick * 1000, 2), sketch=sk, body_name=name, operation="new")
    ax, deg = axis_angle(np.c_[cad_dir(u), cad_dir(v), cad_dir(n)])
    if ax is not None:
        B.c("solid.move", bodies=[name], axis=[round(float(x), 6) for x in ax], angle=f"{deg:.4f} deg")
    B.c("solid.move", bodies=[name], translate=cad(a - n * thick))
    return name, n


plates = []
edge_normals = {}
for i, (p, q, r) in enumerate(FACES):
    nm, n = plate(f"panel{i}", V[p], V[q], V[r], T)
    plates.append((nm, n))
    for e in ((p, q), (q, r), (r, p)):
        edge_normals.setdefault(tuple(sorted(e)), []).append(n)

# struts over every edge
for k, ((p, q), ns) in enumerate(sorted(edge_normals.items())):
    a, b = V[p], V[q]
    t = (b - a) / np.linalg.norm(b - a)
    n = np.mean(ns, 0)
    n -= t * (n @ t)
    n /= np.linalg.norm(n)
    bb = np.cross(n, t)
    L = np.linalg.norm(b - a) + 0.12
    B.obox(f"strut{k}", (a + b) / 2 + n * (0.08 - 0.20) / 2, t, bb, n, (L, 0.20, 0.28))

# openings: slot windows (upper facets), doors (painted) with their windows
op = json.load(open(D / "openings.json"))["openings"]


def owner(o):
    n = np.array(o["normal"])
    return max(plates, key=lambda pn: pn[1] @ n)[0]


for k, o in enumerate(op):
    if o["center"][1] > 4.5:
        B.recess(owner(o), o, 0.15)
        B.sill(f"hood{k}", o, proud=0.12, thick=0.06, overhang=0.08, top=True)
for k, o in enumerate(json.load(open(D / "decal_door.json"))["rects"]):
    if o["center"][1] < 0.8:
        continue  # the same art on the pad's edge
    door = dict(o, w=o["w"] - 0.2, h=o["h"] - 0.1)
    tgt = owner(door)
    B.recess(tgt, door, 0.20)
    B.frame(f"dframe{k}", door, width=0.07, proud=0.05)
    for w in op:
        if w["center"][1] < 4.5 and np.array(w["normal"]) @ np.array(o["normal"]) > 0.95:
            B.recess(tgt, w, 0.05, surface_shift=0.20)

# pad: decagon r 7.31 with the tower's tongue, top edge chamfered
deg = [36 * k for k in range(10)]
ring = [pol(7.31, d, 0.0) for d in deg]
poly = []
for i, p in enumerate(ring):
    poly.append((p[0], p[2]))
    if deg[i] == 72:  # walk out along the tongue between the 72 and 108 degree vertices
        poly += [(6.61, 10.98), (2.10, 10.98)]
B.prism_y("pad", [(round(x, 4), round(z, 4)) for x, z in poly], 0.0, 0.45)
mids = [((poly[i][0] + poly[(i + 1) % len(poly)][0]) / 2, 0.45, (poly[i][1] + poly[(i + 1) % len(poly)][1]) / 2) for i in range(len(poly))]
B.c("solid.chamfer", edges=[cad(m) for m in mids], distance=60, body="pad")

# tower (lofted) and corridor
base = [(3.23, 7.19), (5.69, 7.19), (6.37, 7.92), (6.37, 9.97), (5.69, 10.74), (3.09, 10.74), (2.36, 10.11), (2.36, 7.92)]
top = [(3.62, 7.83), (5.25, 7.83), (5.73, 8.34), (5.73, 9.56), (5.25, 10.10), (3.52, 10.10), (3.01, 9.67), (3.01, 8.34)]
tower = B.loft_y("tower", base, 0.45, top, 5.59)
B.prism_x("corridor", [(5.75, 0.45), (7.18, 0.45), (7.66, 3.45), (5.27, 3.45)], 3.73, 5.04)


def offset(poly2, d):
    c = np.mean(poly2, 0)
    return [tuple(c + (np.array(p) - c) * (1 + d / np.linalg.norm(np.array(p) - c))) for p in poly2]


B.prism_y("tower_cap", [(round(x, 4), round(z, 4)) for x, z in offset(top, 0.08)], 5.55, 5.70)
for k, o in enumerate(json.load(open(D / "decal_louvre.json"))["rects"]):
    B.recess(tower, dict(o, w=o["w"] - 0.1, h=o["h"] - 0.1), 0.10)
    B.frame(f"lframe{k}", dict(o, w=o["w"] - 0.1, h=o["h"] - 0.1), width=0.06, proud=0.04)
for k, o in enumerate(json.load(open(D / "decal_hatch.json"))["rects"]):
    h = dict(o, w=o["w"] - 0.2, h=o["h"] - 0.15)
    B.recess(tower, h, 0.06)
    B.frame(f"hframe{k}", h, width=0.06, proud=0.04)

# masts (the original's posts, on the cap)
Y = 5.70
B.box("mast_tall@c8c8c4", (4.59, Y - 0.05, 8.77), (4.89, 10.03, 9.07), chamfer=0.03)
B.box("mast_short@c8c8c4", (3.56, Y - 0.05, 8.77), (3.96, 6.5, 9.07))
B.box("mast_bar@c8c8c4", (3.56, 6.5, 8.77), (4.59, 6.8, 9.07))
B.box("mast_head@c8c8c4", (3.51, 6.8, 8.67), (4.01, 7.31, 9.17), chamfer=0.04)

print(B.dump())
