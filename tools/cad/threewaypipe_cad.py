#!/usr/bin/env python3
"""CAD rebuild of the three-way pipeline junction (appearance threewaypipe), in the original's frame.
The cornerpipe build (tools/cad/cornerpipe_cad.py) with a third arm; the same texture sheet.

    D=~/craft/solid/mc2/buildings/threewaypipe
    python3 -I tools/art/cad_building.py decal threewaypipe 0 0.025 0.566 0.146 0.645 > $D/decal_plaque.json
    python3 -I tools/art/cad_building.py decal threewaypipe 0 0.156 0.547 0.285 0.64 > $D/decal_cabinet.json
    python3 -I tools/cad/threewaypipe_cad.py $D > $D/threewaypipe.json
    solidcraft-cli run $D/threewaypipe.json --out $D/threewaypipe.obj
    python3 -I tools/art/cad_building.py bake threewaypipe $D/threewaypipe.obj

Measured from game/assets/objects/threewaypipe.glb: a symmetric octagonal junction house (x -5.112..5.112,
z -5.112..3.238, 2.726 m walls, its roof rising to a 3.4 m square flat at 3.919 m), three pipes out of it along -z,
+x and -x (radius ~0.85 on an axis at 1.37 m, 5.11..11.93 m out) into trapezoidal end blocks (3.07 m wide at the
ground, 1.7 m at 2.726 m, 0.85 m deep). The original has no cut-outs.
Relief: the pipes are real 20-sided pipes (r 0.845 m) with 20 cm flanges at both ends and a joint ring at mid-run,
on two saddle supports each (the original's pipe floats 0.52 m up); the junction's roof keeps its facets; the
painted round hatch on its flat is a 28-sided drum with a lid; the painted equipment panels on the two outer walls are 15 cm
proud cabinets and the striped plaques on the three chamfer walls 6 cm plates; a 6 cm plinth rings the house.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, cad  # noqa: E402

D = Path(sys.argv[1])
B = Builder()
H, TOP = 2.726, 3.919
oct_ = [(-1.704, -5.112), (1.704, -5.112), (5.112, -1.704), (5.112, 1.704), (1.704, 3.238), (-1.704, 3.238),
        (-5.112, 1.704), (-5.112, -1.704)]
e, s = 0.08, 1.704
top = [(-s + e, -s), (s - e, -s), (s, -s + e), (s, s - e), (s - e, s), (-s + e, s), (-s, s - e), (-s, -s + e)]
house = B.prism_y("house", oct_, 0.0, H)
B.loft_y("roof", oct_, H, top, TOP)


def ngon(r, n, cx=0.0, cy=0.0):
    """A regular polygon (explicit, so the triangle count stays low; a SolidCraft cylinder tessellates finely)."""
    return [(cx + r * math.cos(2 * math.pi * (k + 0.5) / n), cy + r * math.sin(2 * math.pi * (k + 0.5) / n)) for k in range(n)]


B.prism_y("hatch", ngon(1.3, 28), TOP - 0.02, TOP + 0.17)
B.prism_y("hatchlid", ngon(1.18, 28), TOP + 0.17, TOP + 0.23)


def offset(poly, d):
    """Mitred outward offset of a convex polygon (either winding)."""
    P = np.array(poly)
    c = P.mean(0)
    out = []
    n = len(P)
    for i in range(n):
        a, b, cc = P[i - 1], P[i], P[(i + 1) % n]
        def nrm(p, q):
            t = q - p
            v = np.array([t[1], -t[0]]) / np.linalg.norm(t)
            return v if v @ ((p + q) / 2 - c) > 0 else -v
        n1, n2 = nrm(a, b), nrm(b, cc)
        m = n1 + n2
        m = m / np.linalg.norm(m)
        out.append(tuple(b + m * d / (m @ n1)))
    return out


B.prism_y("plinth", offset(oct_, 0.06), 0.0, 0.3)

# end blocks
B.prism_z("end_z", [(-1.534, 0.0), (1.534, 0.0), (0.852, H), (-0.852, H)], -12.78, -11.928)
B.prism_x("end_x", [(1.534, 0.0), (-1.534, 0.0), (-0.852, H), (0.852, H)], 11.928, 12.78)
B.prism_x("end_mx", [(1.534, 0.0), (-1.534, 0.0), (-0.852, H), (0.852, H)], -12.78, -11.928)

# pipes, flanges, joint rings, saddles
R, YC = 0.845, 1.37
for name, a, b, axis in (("pipe_z", (0, YC, -5.112), (0, YC, -11.928), (0, 0, -1)), ("pipe_x", (5.112, YC, 0), (11.928, YC, 0), (1, 0, 0)),
                         ("pipe_mx", (-5.112, YC, 0), (-11.928, YC, 0), (-1, 0, 0))):
    a, b, axis = np.array(a, float), np.array(b, float), np.array(axis, float)
    L = float(np.linalg.norm(b - a))
    if axis[2]:  # along -z: a z-prism in (x, y)
        B.prism_z(name, ngon(R, 20, 0.0, YC), b[2], a[2])
        for k, (t0, w) in enumerate(((0.0, 0.2), (L - 0.2, 0.2), (L / 2 - 0.08, 0.16))):
            B.prism_z(f"{name}_ring{k}", ngon(R + 0.07, 20, 0.0, YC), a[2] - t0 - w, a[2] - t0)
    else:        # along +-x: an x-prism in (z, y)
        sx = axis[0]
        B.prism_x(name, ngon(R, 20, 0.0, YC), min(a[0], b[0]), max(a[0], b[0]))
        for k, (t0, w) in enumerate(((0.0, 0.2), (L - 0.2, 0.2), (L / 2 - 0.08, 0.16))):
            p0, p1 = a[0] + sx * t0, a[0] + sx * (t0 + w)
            B.prism_x(f"{name}_ring{k}", ngon(R + 0.07, 20, 0.0, YC), min(p0, p1), max(p0, p1))
    side = np.array([axis[2], 0.0, axis[0]])  # horizontal, across the pipe
    for k, t in enumerate((L * 0.27, L * 0.73)):
        c = a + axis * t
        lo = c - side * 0.65 - axis * 0.15
        hi = c + side * 0.65 + axis * 0.15
        B.box(f"{name}_saddle{k}@8a8780", (min(lo[0], hi[0]), 0.0, min(lo[2], hi[2])), (max(lo[0], hi[0]), YC - 0.35, max(lo[2], hi[2])))

# equipment cabinets and plaques
for k, o in enumerate(json.load(open(D / "decal_cabinet.json"))["rects"]):
    n = np.array(o["normal"])
    B.obox(f"cabinet{k}", np.array(o["center"]) + n * 0.065, o["t"], o["b"], o["normal"], (2.5, 1.6, 0.15))
for k, o in enumerate(json.load(open(D / "decal_plaque.json"))["rects"]):
    n = np.array(o["normal"])
    B.obox(f"plaque{k}", np.array(o["center"]) + n * 0.02, o["t"], o["b"], o["normal"], (min(o["w"] - 0.5, 3.0), 1.3, 0.06))

print(B.dump())
