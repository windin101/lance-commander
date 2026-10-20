#!/usr/bin/env python3
"""CAD rebuild of the quetragon (appearance s_quetragon: a half-octagon hall with a colonnaded plaza), in the
original's frame.

    D=~/craft/solid/mc2/buildings/s_quetragon
    python3 -I tools/art/cad_building.py openings s_quetragon > $D/openings.json
    python3 -I tools/cad/s_quetragon_cad.py $D > $D/s_quetragon.json
    solidcraft-cli run $D/s_quetragon.json --out $D/s_quetragon.obj
    python3 -I tools/art/cad_building.py bake s_quetragon $D/s_quetragon.obj --max-res 4096

Measured from game/assets/objects/s_quetragon.glb (vertices grouped by height): the hall is a C-shaped band
(five outer and five inner corners, open towards +x), every storey the same ten-corner ring at a different
offset: a plinth skirt from the eave outline at the ground to the wall line at 0.62 m, walls to 6.30 m, a
sloped soffit out to the eave (6.93 m), a mansard slope in to a terrace (7.65 m), a clerestory band (to
9.00 m), a soffit out to 9.29 m and a gabled top hipped at both ends to a ridge at 10.16 m. The plaza: a slab
(x 2.46..26.76, z -6.14..6.29, 0.47 m) with a sloped stepped border out to x 0.76..28.46, z -7.93..8.07 at the
ground; six diagonal-square columns (half-diagonal 0.70 m, bases and capitals 1.24 m, 0.43..5.50 m) at x 10.52,
16.52, 22.52 and z -4.95 / 5.05 carrying two pergola slabs (x 9.01..24.01, 5.51..5.75 m); two lamps at x 25.90.
Relief: ribs down the mansard and the top roof (the flat colour of the art under them), the cut-out windows
recessed with sills, a fascia lip on both eaves, the lamps as round poles with lanterns.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
B = Builder()


def ring(outer, inner):
    return outer + inner


R_EAVE = ring([(8.83, -17.71), (-3.67, -12.53), (-8.85, -0.02), (-3.67, 12.48), (8.83, 17.67)],
              [(8.83, 5.98), (4.59, 4.22), (2.83, -0.02), (4.59, -4.27), (8.83, -6.02)])
R_WALL = ring([(8.39, -17.06), (-3.12, -11.97), (-8.07, -0.02), (-3.12, 11.93), (8.39, 17.01)],
              [(8.17, 6.42), (4.03, 4.78), (2.04, -0.02), (4.03, -4.82), (8.17, -6.46)])
R_TER = ring([(7.46, -15.65), (-2.62, -11.48), (-7.37, -0.02), (-2.62, 11.43), (7.46, 15.61)],
             [(7.46, 6.90), (3.54, 5.27), (1.35, -0.02), (3.54, -5.32), (7.46, -6.94)])
R_CL = ring([(5.76, -13.11), (-1.32, -10.18), (-5.53, -0.02), (-1.32, 10.13), (5.76, 13.07)],
            [(5.76, 8.03), (2.24, 6.57), (-0.49, -0.02), (2.24, -6.62), (5.76, -8.08)])
R_TOP = ring([(6.33, -13.97), (-1.76, -10.61), (-6.15, -0.02), (-1.76, 10.57), (6.33, 13.92)],
             [(6.33, 7.65), (2.68, 6.14), (0.12, -0.02), (2.68, -6.18), (6.33, -7.69)])
RIDGE = [(4.88, -10.23), (0.46, -8.40), (-3.01, -0.02), (0.46, 8.35), (4.88, 10.18)]
# the ridge as a thin ring, 3 cm either side, paired corner for corner with R_TOP (inner corners run backwards)
R_RIDGE = []
for i, (x, z) in enumerate(R_TOP):
    rx, rz = RIDGE[i] if i < 5 else RIDGE[9 - i]
    d = np.array([x - rx, z - rz])
    d = d / np.linalg.norm(d) * 0.03
    R_RIDGE.append((rx + d[0], rz + d[1]))

B.loft_y("plinth", R_EAVE, 0.0, R_WALL, 0.62)
walls = B.prism_y("walls", R_WALL, 0.62, 6.30)
B.loft_y("soffit", R_WALL, 6.30, R_EAVE, 6.93)
B.loft_y("mansard", R_EAVE, 6.93, R_TER, 7.65)
clere = B.prism_y("clere", R_CL, 7.65, 9.00)
B.loft_y("soffit2", R_CL, 9.00, R_TOP, 9.29)
B.loft_y("top", R_TOP, 9.29, R_RIDGE, 10.16)

# ribs: thin bars lying on a sloped quad, from its lower edge to its upper edge
T, H = 0.05, 0.12
n_rib = 0


def rib(a, b, along):
    global n_rib
    a, b = np.array(a, float), np.array(b, float)
    t = (b - a) / np.linalg.norm(b - a)
    n = np.cross(t, along)
    if n[1] < 0:
        n = -n
    n /= np.linalg.norm(n)
    bb = np.cross(n, t)
    n_rib += 1
    B.obox(f"rib{n_rib}@avg", (a + b) / 2 + n * T / 2, t, bb, n, (float(np.linalg.norm(b - a)), H, T))


def ribs(lo_ring, y0, hi_ring, y1, spacing, edges):
    for i in edges:
        j = (i + 1) % len(lo_ring)
        a0, a1 = np.array(lo_ring[i]), np.array(lo_ring[j])
        b0, b1 = np.array(hi_ring[i]), np.array(hi_ring[j])
        n = max(1, int(round(np.linalg.norm(b1 - b0) / spacing)))
        along = np.array([a1[0] - a0[0], 0.0, a1[1] - a0[1]])
        for k in range(1, n):
            s = k / n
            pa, pb = a0 + (a1 - a0) * s, b0 + (b1 - b0) * s
            rib((pa[0], y0, pa[1]), (pb[0], y1, pb[1]), along)


SLOPES = [0, 1, 2, 3, 5, 6, 7, 8]          # ring edges along the band (4 and 9 are the end caps)
ribs(R_EAVE, 6.93, R_TER, 7.65, 2.2, SLOPES + [4, 9])
ribs(R_TOP, 9.29, R_RIDGE, 10.16, 2.2, SLOPES)

# the plaza: a slab with a sloped border, columns, pergolas, lamps
B.loft_y("plaza", [(0.76, -7.93), (28.46, -7.93), (28.46, 8.07), (0.76, 8.07)], 0.0,
         [(2.46, -6.14), (26.76, -6.14), (26.76, 6.29), (2.46, 6.29)], 0.47)
for j, (x, z) in enumerate([(x, z) for x in (10.52, 16.52, 22.52) for z in (-4.95, 5.05)]):
    def dia(r):
        return [(x + r, z), (x, z + r), (x - r, z), (x, z - r)]
    B.loft_y(f"base{j}", dia(1.24), 0.43, dia(0.70), 0.78)
    B.prism_y(f"col{j}", dia(0.70), 0.78, 5.15)
    B.loft_y(f"capital{j}", dia(0.70), 5.15, dia(1.24), 5.50)
for k, (z0, z1) in enumerate(((-6.22, -3.71), (3.73, 6.24))):
    B.box(f"pergola{k}", (9.01, 5.50, z0), (24.01, 5.75, z1), chamfer=0.03)
for k, zc in enumerate((-5.41, 5.17)):
    B.box(f"lampbase{k}", (25.69, 0.47, zc - 0.18), (26.11, 0.62, zc + 0.18))
    B.c("solid.cylinder", radius=60, height=4220, base=[25900, round(-zc * 1000), 620], axis=[0, 0, 1],
        body_name=f"lamppole{k}", operation="new")
    B.box(f"lantern{k}", (25.66, 4.84, zc - 0.30), (26.14, 5.27, zc + 0.30), chamfer=0.03)


def owner(o):
    return clere if o["center"][1] > 7.6 else walls


for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    if abs(o["normal"][1]) > 0.5 or o["center"][0] > 9.0:
        continue
    B.recess(owner(o), o, 0.15)
    if o["h"] > 0.5 and o["center"][1] < 6.3:
        B.sill(f"sill{k}", o, proud=0.10, thick=0.06, overhang=0.05)

print(B.dump())
