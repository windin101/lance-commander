#!/usr/bin/env python3
"""CAD rebuild of the landed shuttle (appearance shuttle), in the original's frame.

    D=~/craft/solid/mc2/buildings/shuttle
    python3 -I tools/art/cad_building.py openings shuttle > $D/openings.json   # only the gear cards' gaps
    python3 -I tools/cad/shuttle_cad.py > $D/shuttle.json
    solidcraft-cli run $D/shuttle.json --out $D/shuttle.obj
    python3 -I tools/art/cad_building.py bake shuttle $D/shuttle.obj

Measured from game/assets/objects/shuttle.glb (nodes aeroshuttle, 166 triangles, and LandingGear, 12): a closed
faceted fuselage (x +-3.92, y 1.16..6.43, z -9.85..13.97), a hexagonal engine pod on its back (circumradius 2.09
at z -2.58 widening to 2.75 at z -7.42, straight to z -13.16, about (0, 4.10)) ending in a hexagonal nozzle tube
(r 2.09, z -13.09..-13.81), two wedge wings (x +-3.32..+-10, y 3.27..4.17), two tip fins (x +-9.95..+-10.25,
y 1.67..7.41) and three gear alpha cards (mains at x +-4.76, z -3.44..-5.86; nose at x 0, z 9.80..12.22; 3.3 m
tall) painted with a leg, a diagonal brace and two tandem wheels. The rebuild keeps fuselage, wings and fins facet
for facet (tools/cad/aircraft_cad.pyramid_shell), makes the engine pod a true round 24-sided body (issue I77;
radius 2.55, between the hexagon's apothem and its corners, so the painted panels still land on it) with a round
nozzle tube and a 35 cm deep exhaust recess, and replaces the gear cards with real gear in flat colours.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, cad  # noqa: E402
import aircraft_cad as A  # noqa: E402

B = Builder()
comps = A.components("shuttle")
ctr = [c.reshape(-1, 3).mean(0) for c in comps]
ext = [np.ptp(c.reshape(-1, 3), axis=0) for c in comps]
cards = [k for k, e in enumerate(ext) if min(e) < 1e-3 and len(comps[k]) <= 4]
pod = next(k for k, c in enumerate(comps) if c.reshape(-1, 3)[:, 2].min() < -13.5)


def wing_loft(name, tris):
    """A wedge wing (an 8-vertex component with a root and a tip section at constant x) as one ruled loft:
    pyramid_shell let the underside's pyramids poke through the thin leading edge, which baked dark."""
    v = np.unique(tris.reshape(-1, 3).round(4), axis=0)
    secs = []
    for x in (v[:, 0].min(), v[:, 0].max()):
        s = v[np.abs(v[:, 0] - x) < 1e-3]
        c = s.mean(0)
        s = s[np.argsort(np.arctan2(s[:, 1] - c[1], s[:, 2] - c[2]))]
        B.n_sk += 1
        sk = f"sk{B.n_sk}"
        A._plane(B, sk, np.array(cad((x, 0, 0)), float), np.array([0, -1.0, 0]), np.array([0, 0, 1.0]))
        B.c("sketch.line", points=[[round(p[2] * 1000, 2), round(p[1] * 1000, 2)] for p in s], closed=True)
        B.c("sketch.finish")
        secs.append({"sketch": sk})
    B.c("solid.loft", sections=secs, body_name=name, operation="new")


for k, c in enumerate(comps):
    if k in cards or k == pod:
        continue
    v = np.unique(c.reshape(-1, 3).round(4), axis=0)
    if len(v) == 8 and np.ptp(v[:, 0]) > 5:     # the two wings
        wing_loft(f"wing{k}", c)
    else:
        A.pyramid_shell(B, f"part{k}_", c)


def ring(r, cx, cy, n=24):
    a = np.linspace(0, 2 * np.pi, n, endpoint=False) + np.pi / n
    return [[round((cx + r * np.cos(t)) * 1000, 2), round((cy + r * np.sin(t)) * 1000, 2)] for t in a]


def loft_z(name, stations, cx, cy, n=24):
    """Round body along game z through (z, r) stations, one ruled loft per gap (separate touching bodies)."""
    out = []
    for i in range(len(stations) - 1):
        secs = []
        for z, r in stations[i:i + 2]:
            B.n_sk += 1
            sk = f"sk{B.n_sk}"
            A._plane(B, sk, np.array(cad((0, 0, z)), float), np.array([1.0, 0, 0]), np.array([0, 0, 1.0]))
            B.c("sketch.line", points=ring(r, cx, cy, n), closed=True)
            B.c("sketch.finish")
            secs.append({"sketch": sk})
        nm = f"{name}{i}"
        B.c("solid.loft", sections=secs, body_name=nm, operation="new")
        out.append(nm)
    return out


def rod(name, base, axis, r, length, n=20):
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    rp = [(r * np.cos(a), r * np.sin(a)) for a in ang]
    x, y, z = base
    if axis == "x":
        return B.prism_x(name, [(z + u, y + v) for u, v in rp], x, x + length)
    return B.prism_y(name, [(x + u, z + v) for u, v in rp], y, y + length)


# ---- engine pod: round, a band at the step, nozzle tube with a deep exhaust recess
PX, PY = 0.0, 4.10
loft_z("pod", [(-2.58, 1.95), (-7.42, 2.55), (-13.16, 2.55)], PX, PY)
loft_z("band", [(-7.30, 2.60), (-7.60, 2.60)], PX, PY)
loft_z("nozzle", [(-13.09, 2.00), (-13.81, 2.00)], PX, PY)
loft_z("exhaust", [(-13.46, 1.62), (-13.90, 1.62)], PX, PY)
B.cut("nozzle0", "exhaust0")
loft_z("lip", [(-13.70, 2.08), (-13.81, 2.08)], PX, PY)
loft_z("lipcut", [(-13.65, 1.80), (-13.86, 1.80)], PX, PY)
B.cut("lip0", "lipcut0")

# ---- landing gear (cards: a leg, a diagonal brace from the top of the card, two tandem wheels)
R, W = 0.40, 0.30


def gear(nm, x, z_top, z_leg, z_wheels, top, y_brace=1.55):
    for k, z in enumerate(z_wheels):
        rod(f"{nm}{k}_tyre@262626", (x - W / 2, R, z), "x", R, W, 24)
        rod(f"{nm}{k}_hub@b4b4b0", (x - W / 2 - 0.02, R, z), "x", R * 0.5, W + 0.04, 16)
    B.box(f"{nm}_bogie@8c8c88", (x - 0.08, R - 0.08, min(z_wheels) - 0.05), (x + 0.08, R + 0.08, max(z_wheels) + 0.05))
    rod(f"{nm}_leg@a0a09c", (x, R, z_leg), "y", 0.13, top - R, 16)
    a, b = np.array([x, top - 0.1, z_top]), np.array([x, y_brace, z_leg])
    d = b - a
    L = np.linalg.norm(d)
    bv = d / L
    n = np.array([1.0, 0, 0])
    t = np.cross(bv, n)
    B.obox(f"{nm}_brace@8c8c88", (a + b) / 2, t, bv, n, (0.12, L, 0.12))


gear("gl", -4.76, -3.55, -4.70, (-4.05, -5.21), 3.32)
gear("gr", 4.76, -3.55, -4.70, (-4.05, -5.21), 3.32)
gear("gn", 0.0, 11.90, 10.96, (11.62, 10.45), 1.75, y_brace=0.95)
print(B.dump())
