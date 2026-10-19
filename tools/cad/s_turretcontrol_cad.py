#!/usr/bin/env python3
"""CAD rebuild of the turret control centre (appearance s_turretcontrol), in the original's frame.

    D=~/craft/solid/mc2/buildings/s_turretcontrol
    python3 -I tools/art/cad_building.py openings s_turretcontrol > $D/openings.json
    python3 -I tools/art/cad_building.py decal s_turretcontrol <mat> <u0 v0 u1 v1> > $D/decal_<name>.json   (see DECALS)
    python3 -I tools/cad/s_turretcontrol_cad.py $D > $D/s_turretcontrol.json
    solidcraft-cli run $D/s_turretcontrol.json --out $D/s_turretcontrol.obj
    python3 -I tools/art/cad_building.py bake s_turretcontrol $D/s_turretcontrol.obj

Measured from game/assets/objects/s_turretcontrol.glb (vertices listed by height): a central block
(x -7.24..3.46, z -8.47..4.68) under a 0.7 m roof slab to 3.97 m that overhangs the front by 1 m; on its -x side a
hexagonal hall (battered skirt from the ground to 2.74 m, straight walls to 6.26 m); in front a figure-of-eight
block (12-gon, to 5.87 m); on its +x side a hexagonal tower (base and connector to 3.67 m, tapering to 9.39 m, a
window band to 13.47 m) carrying a radar pedestal (to 15.51 m) and the radar bar (to 16.64 m); a roof vent with two
masts on the central roof; two low walls (1.2 m). The roofs' painted dark fields (mapped back to 3D from the
roof atlas) are 12 cm recesses inside their light rims, the figure-of-eight's split in two lobes with the painted
divider between; the grilles and the L-shaped pipe on the roofs are raised; every cut-out window is a recess
(20-25 cm, sills under the hall's), the T-windowed panels and wall vents are recesses; the painted cornice of the
figure-of-eight, a ledge at the hall's batter and at the tower's window band are real projecting bands; the roof
slab overhangs the central block's sides by 15 cm over its painted fascia; the masts are hexagonal posts instead
of crossed cards.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

DECALS = {  # name: (material, u0, v0, u1, v1), for cad_building.py decal
    "cfield": (1, 0.035, 0.035, 0.5, 0.575), "grilleA": (1, 0.26, 0.07, 0.45, 0.12), "grilleB": (1, 0.105, 0.475, 0.23, 0.53),
    "lobegrille": (1, 0.13, 0.77, 0.29, 0.83), "lobegrille2": (1, 0.44, 0.77, 0.6, 0.83),
    "gdoor": (0, 0.12, 0.71, 0.356, 0.95), "ventA": (0, 0.205, 0.525, 0.26, 0.595), "ventB": (0, 0.83, 0.49, 0.885, 0.59),
    "smallwin": (0, 0.06, 0.49, 0.15, 0.64),
}
D = Path(sys.argv[1])
B = Builder()


def rects(name):
    return json.load(open(D / f"decal_{name}.json"))["rects"]


def ccw(poly):
    """(x, z) polygon counter-clockwise seen from above (+y): signed area in (x, -z) positive."""
    a = sum(x0 * -z1 - x1 * -z0 for (x0, z0), (x1, z1) in zip(poly, poly[1:] + poly[:1]))
    return poly if a > 0 else poly[::-1]


def inset(poly, d):
    """Inward offset of a convex (x, z) polygon by d (mitred)."""
    p = ccw(poly)
    q = [(x, -z) for x, z in p]  # to a right-handed plane
    n = len(q)
    lines = []
    for i in range(n):
        (x0, y0), (x1, y1) = q[i], q[(i + 1) % n]
        ex, ey = x1 - x0, y1 - y0
        L = math.hypot(ex, ey)
        nx, ny = -ey / L, ex / L  # inward (left of a ccw edge)
        lines.append(((x0 + nx * d, y0 + ny * d), (ex, ey)))
    out = []
    for i in range(n):
        (pp, e), (qq, f) = lines[i - 1], lines[i]
        det = e[0] * -f[1] + f[0] * e[1]
        t = ((qq[0] - pp[0]) * -f[1] + f[0] * (qq[1] - pp[1])) / det
        out.append((pp[0] + e[0] * t, -(pp[1] + e[1] * t)))
    return out


def ring(name, poly, y0, y1, proud):
    """A projecting band round a polygon's walls: one box per edge, overlapping at the corners."""
    p = ccw(poly)
    cx, cz = np.mean([a[0] for a in p]), np.mean([a[1] for a in p])
    for i in range(len(p)):
        a, b = np.array(p[i]), np.array(p[(i + 1) % len(p)])
        e = b - a
        L = float(np.linalg.norm(e))
        if L < 0.05:
            continue
        t = np.array([e[0], 0.0, e[1]]) / L
        n = np.cross(t, [0.0, 1.0, 0.0])
        mid = (a + b) / 2
        if (mid - [cx, cz]) @ n[[0, 2]] < 0:
            n = -n
        bvec = np.cross(n, t)
        if bvec[1] < 0:
            t = -t
            bvec = -bvec
        c = np.array([mid[0], (y0 + y1) / 2, mid[1]]) + n * (proud / 2 - 0.02)
        B.obox(f"{name}{i}", c, t, bvec, n, (L + 2 * proud, y1 - y0, proud + 0.02))


# ---- central block and its roof slab
B.box("central", (-7.24, 0.0, -8.47), (3.46, 3.27, 4.68))
slab = B.box("slab", (-7.39, 3.27, -9.45), (3.61, 3.97, 4.68))
for o in rects("cfield"):
    B.recess(slab, o, 0.12)
for nm in ("grilleA", "grilleB"):
    for k, o in enumerate(rects(nm)):
        c = np.array(o["center"])
        B.box(f"{nm}{k}", (c[0] - o["w"] / 2, 3.83, c[2] - o["h"] / 2), (c[0] + o["w"] / 2, 4.05, c[2] + o["h"] / 2))
# the L-shaped pipe (from the roof atlas: x = -5.362 + 21.0 (u - 0.1), z = -7.106 + 23.525 (v - 0.1))
B.box("pipe0", (-1.79, 3.83, -4.70), (0.95, 4.08, -4.38))
B.box("pipe1", (0.62, 3.83, -4.70), (0.95, 4.08, 3.05))
B.box("pipeend0", (-1.95, 3.83, -4.90), (-1.45, 4.16, -4.18))
B.box("pipeend1", (0.45, 3.83, 2.95), (1.12, 4.16, 3.50))
# roof vent and its masts
B.loft_y("vent", [(-5.61, -1.82), (-2.31, -1.82), (-2.31, 1.52), (-5.61, 1.52)], 3.84,
         [(-5.14, -1.35), (-2.78, -1.35), (-2.78, 1.04), (-5.14, 1.04)], 5.08)
for k, (x, top) in enumerate(((-4.58, 12.57), (-3.41, 15.99))):
    r = 0.08
    B.prism_y(f"mast{k}@b4b4ae", [(x + r * math.cos(a * math.pi / 3), -0.74 + r * math.sin(a * math.pi / 3)) for a in range(6)], 5.0, top)
for nm, depth in (("ventA", 0.08), ("ventB", 0.08), ("smallwin", 0.10)):
    for o in rects(nm):
        if abs(o["normal"][1]) > 0.5:
            continue
        B.recess("central", o, depth)

# ---- hexagonal hall: battered skirt, straight walls, ledge, roof field
hall_lo = [(-4.65, -2.39), (-4.65, -7.07), (-8.7, -9.41), (-12.75, -7.07), (-12.75, -2.39), (-8.7, -0.06)]
hall_hi = [(-5.08, -2.64), (-5.08, -6.82), (-8.7, -8.91), (-12.32, -6.82), (-12.32, -2.64), (-8.7, -0.56)]
B.loft_y("hall_skirt", hall_lo, 0.0, hall_hi, 2.74)
hall = B.prism_y("hall", hall_hi, 2.74, 6.26)
B.cut(hall, B.prism_y("hall_field", inset(hall_hi, 0.72), 6.14, 6.4))
ring("hall_ledge", hall_hi, 2.64, 2.84, 0.12)

# ---- figure-of-eight block, two lobes
lobe_l = [(-7.35, 4.13), (-1.89, 4.13), (-1.89, 9.38), (-4.29, 10.69), (-7.16, 10.66), (-9.15, 8.86), (-9.2, 5.94)]
lobe_r = [(-1.89, 4.13), (3.57, 4.13), (5.24, 5.94), (5.26, 8.86), (3.38, 10.66), (0.32, 10.69), (-1.89, 9.38)]
for nm, poly in (("lobe_l", lobe_l), ("lobe_r", lobe_r)):
    B.prism_y(nm, poly, 0.0, 5.87)
    B.cut(nm, B.prism_y(f"{nm}_field", inset(poly, 0.45), 5.75, 6.0))
for nm in ("lobegrille", "lobegrille2"):
    for k, o in enumerate(rects(nm)):
        c = np.array(o["center"])
        B.box(f"{nm}{k}", (c[0] - o["w"] / 2, 5.73, c[2] - o["h"] / 2), (c[0] + o["w"] / 2, 5.95, c[2] + o["h"] / 2))
fig8 = [(-7.35, 4.13), (3.57, 4.13), (5.24, 5.94), (5.26, 8.86), (3.38, 10.66), (0.32, 10.69), (-1.89, 9.38),
        (-4.29, 10.69), (-7.16, 10.66), (-9.15, 8.86), (-9.2, 5.94)]
ring("cornice", fig8, 5.04, 5.64, 0.15)
for o in rects("gdoor"):
    if o["w"] < 1.5 or o["center"][2] < 4.5:
        continue  # the slivers wrapping a corner, and the face hidden behind the central block
    tgt = "lobe_l" if o["center"][0] < -1.89 else "lobe_r"
    B.recess(tgt, dict(o, w=o["w"] - 0.3, h=o["h"] - 0.2), 0.15)

# ---- tower
tb = [(6.15, -6.41), (6.15, -2.73), (9.34, -0.89), (12.53, -2.73), (12.53, -6.41), (9.34, -8.26)]
tt = [(6.5, -6.22), (6.5, -2.93), (9.34, -1.29), (12.19, -2.93), (12.19, -6.22), (9.34, -7.86)]
B.prism_y("tower_base", tb, 0.0, 3.67)
B.box("connector", (3.31, 0.0, -6.41), (6.15, 3.67, -2.73))
B.loft_y("tower_taper", tb, 3.67, tt, 9.39)
band = B.prism_y("tower_band", tt, 9.39, 13.47)
B.cut(band, B.prism_y("tower_field", inset(tt, 0.52), 13.35, 13.6))
ring("tower_ledge", tt, 9.29, 9.49, 0.15)
ring("connector_cap", [(3.31, -6.41), (6.15, -6.41), (6.15, -2.73), (3.31, -2.73)], 3.57, 3.67, 0.06)
B.loft_y("pedestal", [(8.2, -6.26), (10.47, -6.26), (10.47, -4.83), (8.2, -4.83)], 13.40,
         [(8.52, -6.01), (10.15, -6.01), (10.15, -5.08), (8.52, -5.08)], 15.51)
# radar bar, 6 degrees off x: a 5.76 x 1.2 bar with a 0.62 m wide hump
ang = math.degrees(math.atan2(-(-5.88 + 6.48 - 0.0), 5.73))  # game dz/dx = +0.104 -> CAD angle about Z
bar_c = (9.36, -5.58)
B.prism_z("radar", [(-2.88, 15.51), (2.88, 15.51), (2.88, 16.01), (-2.88, 16.01)], -0.6, 0.6)
B.prism_z("radar_hump", [(-1.33, 15.95), (1.33, 15.95), (1.15, 16.64), (-1.15, 16.64)], -0.31, 0.31)
for nm in ("radar", "radar_hump"):
    B.c("solid.move", bodies=[nm], axis=[0, 0, 1], angle=f"{ang:.3f} deg")
    B.c("solid.move", bodies=[nm], translate=[bar_c[0] * 1000, -bar_c[1] * 1000, 0])

# ---- windows
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    y = o["center"][1]
    if y > 9:
        B.recess(band, o, 0.25)
    elif 4 < y < 6:
        B.recess(hall, o, 0.20)
        B.sill(f"sill{k}", o, proud=0.12, thick=0.08, overhang=0.08)

# ---- low walls
B.prism_y("wall0", [(11.11, -2.35), (11.66, -2.35), (11.66, 4.69), (11.28, 6.63), (10.77, 6.36), (11.11, 4.69)], 0.0, 1.2)
B.prism_y("wall1", [(5.11, 8.04), (9.56, 8.04), (9.94, 8.59), (5.11, 8.59)], 0.0, 1.2)

print(B.dump())
