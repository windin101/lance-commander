#!/usr/bin/env python3
"""CAD rebuild of the parked Slayer aerofighter prop (appearance slayerp), in the original's frame.

    D=~/craft/solid/mc2/buildings/slayerp
    python3 -I tools/art/cad_building.py openings slayerp > $D/openings.json
    python3 -I tools/cad/slayerp_cad.py $D > $D/slayerp.json
    solidcraft-cli run $D/slayerp.json --out $D/slayerp.obj
    python3 -I tools/art/cad_building.py bake slayerp $D/slayerp.obj

Measured from game/assets/objects/slayerp.glb (node Slayer, 134 triangles): a hexagonal-section fuselage, nose
at z 10.01, sections at z 8.6, 5.07 and 1.3 (to 4.94 m high), tapering to a spine at z -8.19 and a tail spike at
z -12.83; two engine pods beside it (x 2.04..4.18 at z 1.3) from a slanted intake face (z 5.07 inboard, 4.28
outboard) to the exhaust face at z -8.2; swept wings from x 3.23 to 11.47 (y ~2.5..3.4); fins at x +-6.48
(alpha-free cards, 2.9..6.13 m); diamond-section wingtip pods at x +-11.39 from z -3.2 to -11.37; gear legs
drawn on alpha cards (rear at x -2.95 / 3.18, nose at x 0).
Relief: the hull is the original's sections lofted as solids (fuselage, pods and wings real volumes, not
cards); the intakes are 35 cm recesses; each exhaust face carries two round nozzles with a 30 cm bore (on the
two painted rings); fins are 14 cm plates; the wingtip pods true 24-sided bodies of revolution; the gear real
struts, drag braces and wheels.
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, cad, cad_dir  # noqa: E402

B = Builder()


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def section(origin, xd, yd, pts):
    """A closed polygon sketched on the plane through game point `origin` spanned by game directions xd, yd."""
    B.n_sk += 1
    nm = f"sk{B.n_sk}"
    B.c("sketch.create", plane={"origin": cad(origin), "x_dir": [round(float(v), 6) for v in unit(cad_dir(xd))],
                                "y_dir": [round(float(v), 6) for v in unit(cad_dir(yd))]}, name=nm)
    B.c("sketch.line", points=[[round(u * 1000, 2), round(v * 1000, 2)] for u, v in pts], closed=True)
    B.c("sketch.finish")
    return nm


def loft(name, secs):
    B.c("solid.loft", sections=[{"sketch": s} for s in secs], body_name=name, operation="new")
    return name


def zsec(z, pts):  # (x, y) at game z
    return section((0, 0, z), (1, 0, 0), (0, 1, 0), pts)


def xsec(x, pts):  # (z, y) at game x
    return section((x, 0, 0), (0, 0, 1), (0, 1, 0), pts)


def ngon(r, k, cx=0.0, cy=0.0):
    return [(cx + r * math.cos(2 * math.pi * (i + 0.5) / k), cy + r * math.sin(2 * math.pi * (i + 0.5) / k)) for i in range(k)]


def hexa(top, ux, uy, ly, bot):
    return [(0.0, top), (-ux, uy), (-ux, ly), (0.0, bot), (ux, ly), (ux, uy)]


def tiny(cx, cy, r=0.06):
    return [(cx, cy + r), (cx - r, cy + r / 2), (cx - r, cy - r / 2), (cx, cy - r), (cx + r, cy - r / 2), (cx + r, cy + r / 2)]


# ---- fuselage: ruled lofts between the original's sections
S = [(10.01, tiny(0.0, 2.12)), (8.6, hexa(3.48, 0.98, 2.92, 1.79, 1.22)), (5.07, hexa(4.47, 1.63, 3.53, 1.64, 0.74)),
     (1.3, hexa(4.94, 2.04, 3.76, 1.41, 0.23)), (-8.19, hexa(3.99, 0.75, 3.65, 2.23, 2.15)), (-12.83, tiny(0.0, 3.53))]
secs = [zsec(z, p) for z, p in S]
for k in range(len(S) - 1):
    loft(f"fus{k}", [secs[k], secs[k + 1]])

for s in (1, -1):
    tag = "r" if s > 0 else "l"
    # ---- engine pod: slanted intake face -> z 1.3 -> exhaust face at z -8.2
    fx = unit([s * 2.14, 0.0, -0.79])
    w = 2.28
    front = section((s * 1.63, 0.0, 5.07), fx, (0, 1, 0), [(0.0, 3.53), (w, 3.29), (w, 2.23), (0.0, 1.64)])
    mid = zsec(1.3, [(s * 2.04, 3.76), (s * 4.18, 3.53), (s * 4.18, 1.99), (s * 2.04, 1.41)])
    rear = zsec(-8.2, [(s * 0.75, 3.65), (s * 3.36, 3.41), (s * 3.36, 2.82), (s * 0.75, 2.23)])
    pa = loft(f"pod{tag}a", [front, mid])
    loft(f"pod{tag}b", [mid, rear])
    # intake recess on the slanted face
    nrm = unit(np.cross(np.array([0.0, 1.0, 0.0]), fx)) * (1 if s > 0 else -1)
    if nrm[2] < 0:
        nrm = -nrm
    c = np.array([s * 1.63, 0.0, 5.07]) + fx * (w / 2) + np.array([0.0, 2.62, 0.0])
    B.recess(pa, {"center": list(c), "normal": list(nrm), "t": list(fx), "b": [0, 1, 0], "w": w - 0.45, "h": 0.8}, 0.35)
    # exhaust nozzles on the two painted rings
    for j, nx in enumerate((1.42, 2.62)):
        nm = f"nozzle{tag}{j}"
        B.prism_z(nm, ngon(0.42, 24, s * nx, 2.98), -8.55, -8.15)
        B.prism_z(f"bore{tag}{j}", ngon(0.31, 24, s * nx, 2.98), -8.6, -8.25)
        B.cut(nm, f"bore{tag}{j}")
        B.prism_z(f"cone{tag}{j}@3a3c3e", ngon(0.16, 24, s * nx, 2.98), -8.35, -8.2)
    # ---- wing: root at x 3.23, tip at x 11.47, sections in (z, y)
    root = xsec(s * 3.23, [(2.01, 2.47), (-0.35, 3.41), (-6.88, 2.94)])
    tip = xsec(s * 11.47, [(-4.4, 2.78), (-5.22, 3.1), (-7.62, 2.89)])
    loft(f"wing{tag}", [root, tip])
    # ---- fin: a 14 cm plate on the card
    fin = [(-2.02, 2.9), (-7.05, 2.9), (-8.62, 6.13), (-6.18, 6.13)]
    B.prism_x(f"fin{tag}", fin, s * 6.48 - 0.07, s * 6.48 + 0.07)
    # ---- wingtip pod: a body of revolution (24 sides) along z, axis at y 2.9
    px = s * 11.39
    a = zsec(-3.2, ngon(0.04, 24, px, 2.9))
    b = zsec(-4.72, ngon(0.76, 24, px, 2.9))
    cc = zsec(-7.76, ngon(0.76, 24, px, 2.9))
    d = zsec(-11.37, ngon(0.04, 24, px, 2.9))
    loft(f"tipnose{tag}", [a, b])
    loft(f"tipbody{tag}", [b, cc])
    loft(f"tiptail{tag}", [cc, d])
    B.prism_z(f"tipband{tag}@avg", ngon(0.8, 24, px, 2.9), -4.9, -4.75)

# ---- gear: rear legs on the cards at x -2.95 / 3.18, nose leg at x 0
WR, WW = 0.45, 0.32
for k, x in enumerate((-2.95, 3.18)):
    B.prism_y(f"rstrut{k}@5a5e62", ngon(0.12, 20, x, -4.35), WR, 2.6)
    B.prism_x(f"rwheel{k}@2a2a2a", ngon(WR, 24, -4.35, WR), x - WW / 2, x + WW / 2)
    B.prism_x(f"rhub{k}@8a8e92", ngon(0.2, 20, -4.35, WR), x - WW / 2 - 0.03, x + WW / 2 + 0.03)
    p0, p1 = np.array([x, 1.3, -4.35]), np.array([x, 2.5, -3.1])
    bb = unit(p1 - p0)
    B.obox(f"rbrace{k}@5a5e62", (p0 + p1) / 2, np.array([1.0, 0.0, 0.0]), bb, np.cross([1.0, 0.0, 0.0], bb), (0.12, float(np.linalg.norm(p1 - p0)), 0.12))
B.prism_y("nstrut@5a5e62", ngon(0.1, 20, 0.0, 6.15), 0.4, 1.6)
for k, x in enumerate((-0.2, 0.2)):
    B.prism_x(f"nwheel{k}@2a2a2a", ngon(0.4, 24, 6.15, 0.4), x - 0.12, x + 0.12)
B.prism_x("naxle@8a8e92", ngon(0.08, 16, 6.15, 0.4), -0.34, 0.34)

print(B.dump())
