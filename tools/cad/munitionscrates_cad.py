#!/usr/bin/env python3
"""CAD rebuild of the munitions crate stack (appearance munitionscrates), in the original's frame.

    D=~/craft/solid/mc2/buildings/munitionscrates
    python3 -I tools/art/cad_building.py decal munitionscrates 0 0.54 0.835 0.642 0.922 > $D/decal_label.json
    python3 -I tools/cad/munitionscrates_cad.py $D > $D/munitionscrates.json
    solidcraft-cli run $D/munitionscrates.json --out $D/munitionscrates.obj
    python3 -I tools/art/cad_building.py bake munitionscrates $D/munitionscrates.obj --texel 0.01

Measured from game/assets/objects/munitionscrates.glb: three crates on the ground (x -4.25..-1.39, -1.39..1.41,
1.41..4.2; z -0.85..0.84; 1.34 m high) and a fourth on the middle one, to 2.71 m. Every face shares one texture
(sides: hazard band over two plank panels; ends: one panel; lid: a framed plank top with the label).
Relief, from the texture's proportions: each crate is a core 5 cm inside the original faces, with 10 cm corner
posts, a 10.5 cm bottom rail, the 49 cm hazard band as a rail, a 27 cm centre post on the long sides, all flush
with the original surface; the panels are five planks each, 2 cm behind the frame, with 1.5 cm gaps on the
painted grooves; the lid has the painted rim (13-25 cm) and five planks along x, split on its painted grooves. The
side labels are placards over the plank gaps.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])

B = Builder()
F = 0.05      # frame depth (core inset)
PL = 0.03     # plank depth (planks stand 2 cm behind the frame face)
POST, RAIL, BAND, MID = 0.10, 0.105, 0.49, 0.27
GAP = 0.015
# the painted plank grooves, metres down from the top of a 1.34 m face (texture column profile)
GROOVES = (0.645, 0.845, 0.93, 1.095)
# the lid: rim widths (z0, z1, x0, x1 sides) and its grooves (game z), from the lid texture
RIM = (0.25, 0.13, 0.165, 0.23)
LID_GROOVES = (-0.379, -0.106, 0.276, 0.549)
crates = [(-4.25, -1.39, 0.0, 1.34), (-1.39, 1.41, 0.0, 1.35), (1.41, 4.2, 0.0, 1.34), (-1.39, 1.41, 1.35, 2.71)]
Z0, Z1 = -0.85, 0.84


def planks(name, lo_u, hi_u, y0, y1, face, depth, top):
    """Planks from y0 to y1 across [lo_u, hi_u] on a face ('x', x_plane, sign) or ('z', z_plane, sign), split on
    the painted grooves (top = the face's top, the grooves scale with its height)."""
    cuts = [top - g * (top - y0 + RAIL) / 1.34 for g in GROOVES]
    edges = [y0] + sorted(cuts) + [y1]
    for i in range(len(edges) - 1):
        a = edges[i] + (GAP / 2 if i else 0)
        h = edges[i + 1] - (GAP / 2 if i < len(edges) - 2 else 0) - a
        axis, plane, sgn = face
        d0, d1 = sorted((plane, plane - sgn * depth))
        if axis == "z":
            B.box(f"{name}_{i}", (lo_u, a, d0), (hi_u, a + h, d1))
        else:
            B.box(f"{name}_{i}", (d0, a, lo_u), (d1, a + h, hi_u))


for c, (x0, x1, y0, y1) in enumerate(crates):
    n = f"c{c}"
    H = y1 - y0
    B.box(f"{n}core", (x0 + F, y0, Z0 + F), (x1 - F, y1 - F, Z1 - F))
    for k, (px, pz) in enumerate(((x0, Z0), (x1, Z0), (x0, Z1), (x1, Z1))):
        ax0, ax1 = sorted((px, px + (POST if px == x0 else -POST)))
        az0, az1 = sorted((pz, pz + (POST if pz == Z0 else -POST)))
        B.box(f"{n}post{k}", (ax0, y0, az0), (ax1, y1 - F, az1))
    # rails on the four faces: bottom rail and hazard band, between the corner posts
    for k, (axis, plane, sgn, u0, u1) in enumerate((("z", Z0, -1, x0 + POST, x1 - POST), ("z", Z1, 1, x0 + POST, x1 - POST),
                                                   ("x", x0, -1, Z0 + POST, Z1 - POST), ("x", x1, 1, Z0 + POST, Z1 - POST))):
        d0, d1 = sorted((plane, plane - sgn * F))
        for j, (a, b) in enumerate(((y0, y0 + RAIL), (y1 - BAND, y1 - F))):
            if axis == "z":
                B.box(f"{n}rail{k}{j}", (u0, a, d0), (u1, b, d1))
            else:
                B.box(f"{n}rail{k}{j}", (d0, a, u0), (d1, b, u1))
        pa, pb = y0 + RAIL, y1 - BAND
        if axis == "z":  # long side: centre post, two plank panels
            xm = (x0 + x1) / 2
            B.box(f"{n}mid{k}", (xm - MID / 2, pa, d0), (xm + MID / 2, pb, d1))
            planks(f"{n}pl{k}a", u0, xm - MID / 2, pa, pb, (axis, plane, sgn), PL, y1)
            planks(f"{n}pl{k}b", xm + MID / 2, u1, pa, pb, (axis, plane, sgn), PL, y1)
        else:
            planks(f"{n}pl{k}", u0, u1, pa, pb, (axis, plane, sgn), PL, y1)
    # lid: rim flush with the original top, planks along x 2 cm below it
    ra, rb, rc, rd = RIM
    for k, (lo, hi) in enumerate((((x0, y1 - F, Z0), (x1, y1, Z0 + ra)), ((x0, y1 - F, Z1 - rb), (x1, y1, Z1)),
                                  ((x0, y1 - F, Z0 + ra), (x0 + rc, y1, Z1 - rb)), ((x1 - rd, y1 - F, Z0 + ra), (x1, y1, Z1 - rb)))):
        B.box(f"{n}rim{k}", lo, hi)
    edges = [Z0 + ra] + list(LID_GROOVES) + [Z1 - rb]
    for i in range(len(edges) - 1):
        a = edges[i] + (GAP / 2 if i else 0)
        b = edges[i + 1] - (GAP / 2 if i < len(edges) - 2 else 0)
        B.box(f"{n}lid{i}", (x0 + rc, y1 - F, a), (x1 - rd, y1 - (F - PL), b))

# the painted labels are placards: 1.5 cm plates over the plank gaps, 0.5 cm behind the frame face
for k, o in enumerate(json.load(open(D / "decal_label.json"))["rects"]):
    n = np.array(o["normal"], float)
    B.obox(f"label{k}", np.array(o["center"]) - n * 0.0125, o["t"], o["b"], o["normal"], (o["w"] - 0.03, o["h"] - 0.03, 0.015))

print(B.dump())
