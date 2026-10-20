#!/usr/bin/env python3
"""CAD rebuild of the gantry (appearance gantry), in the original's frame.

    D=~/craft/solid/mc2/buildings/gantry
    python3 -I tools/art/cad_building.py openings gantry > $D/openings.json
    python3 -I tools/cad/gantry_cad.py $D > $D/gantry.json
    solidcraft-cli run $D/gantry.json --out $D/gantry.obj
    python3 -I tools/art/cad_building.py bake gantry $D/gantry.obj

Measured from game/assets/objects/gantry.glb (node Gantry): a 0.86 m plinth (an L of chamfered corners, x -7.88..8.42,
z -7.88..12.6); a five-sided lattice frame from the plinth to 24.88 m, drawn as double-sided alpha cards (corners
(4.13,-6.17), (-6.17,4.13), (-6.17,-2.31), (-2.31,-6.17)), three cells a face a storey, two storeys; a cab
(x -6.59..-1.45, z -0.59..10.99) from 10.73 to 23.17 m with windows at 19.1 m; a stair tower beside it
(x -10.03..-6.59, z 3.7..9.71) under a roof sloping from 22.31 to 20.59 m; a landing platform (16.73..17.25 m)
off the cab's +x side; two masts (three-sided spikes in the original) from the cab roof to 36.98 m.
Relief: the lattice is real members on the cards' painted frame (posts and girts are the complement of each
face's cut-out cells, so they sit on the paint); the windows are 25 cm recesses with sills and hoods; the cab has
a roof parapet and a cornice, the stair tower a coping on its sloped roof and a plinth course; the platform a
drip edge; the masts are true 24-sided tapered poles with collars.
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
OPEN = json.load(open(D / "openings.json"))["openings"]


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def ngon(r, k, cx=0.0, cz=0.0):
    return [(cx + r * math.cos(2 * math.pi * (i + 0.5) / k), cz + r * math.sin(2 * math.pi * (i + 0.5) / k)) for i in range(k)]


def complement(iv, lo, hi, eps=0.02):
    out, cur = [], lo
    for a, b in sorted(iv):
        if a > cur + eps:
            out.append((cur, a))
        cur = max(cur, b)
    if hi > cur + eps:
        out.append((cur, hi))
    return out


# ---- plinth
PL = [(-4.45, -7.88), (6.28, -7.88), (8.42, -6.59), (8.42, -4.45), (4.13, -4.45), (-4.45, 4.13), (-4.45, 12.6),
      (-6.59, 12.6), (-7.88, 10.56), (-7.88, -4.45)]
B.prism_y("plinth", PL, 0.0, 0.86)

# ---- lattice frame: members are the complement of each face's cells
Y0, Y1, TH = 0.86, 24.88, 0.2
FACES = [((4.13, -6.17), (-6.17, 4.13)), ((-6.17, 4.13), (-6.17, -2.31)), ((-6.17, -2.31), (-2.31, -6.17)),
         ((-2.31, -6.17), (4.13, -6.17))]
for fi, (p, q) in enumerate(FACES):
    p, q = np.array(p), np.array(q)
    L = float(np.linalg.norm(q - p))
    t2 = (q - p) / L
    n2 = np.array([-t2[1], t2[0]])
    cells = set()
    for o in OPEN:
        c = np.array([o["center"][0], o["center"][2]])
        if o["center"][1] > Y1 or abs(float(np.dot(c - p, n2))) > 0.05 or abs(abs(np.dot(np.array([o["normal"][0], o["normal"][2]]), n2)) - 1) > 0.05:
            continue
        s = float(np.dot(c - p, t2))
        cells.add((round(s - o["w"] / 2, 2), round(s + o["w"] / 2, 2), round(o["center"][1] - o["h"] / 2, 2), round(o["center"][1] + o["h"] / 2, 2)))
    cells = sorted(cells)
    cols = sorted({(a, b) for a, b, _, _ in cells})
    t3, n3 = np.array([t2[0], 0.0, t2[1]]), np.array([n2[0], 0.0, n2[1]])
    up = np.array([0.0, 1.0, 0.0])

    def member(name, s0, s1, y0, y1):
        c = np.array([p[0], 0.0, p[1]]) + t3 * (s0 + s1) / 2 + up * (y0 + y1) / 2
        B.obox(name, c, t3, up, np.cross(t3, up), (s1 - s0, y1 - y0, TH))

    for k, (s0, s1) in enumerate(complement(cols, 0.0, L)):
        # corner posts reach 10 cm past the face end so neighbouring faces meet without a gap
        member(f"post{fi}_{k}", s0 - (0.1 if s0 < 0.05 else 0.0), s1 + (0.1 if s1 > L - 0.05 else 0.0), Y0, Y1)
    for k, (s0, s1) in enumerate(cols):
        ys = [(y0, y1) for a, b, y0, y1 in cells if (a, b) == (s0, s1)]
        for j, (y0, y1) in enumerate(complement(ys, Y0, Y1)):
            member(f"girt{fi}_{k}_{j}", s0, s1, y0, y1)

# ---- cab, parapet, cornice, windows
CX0, CX1, CZ0, CZ1, CY0, CY1 = -6.59, -1.45, -0.59, 10.99, 10.73, 23.17
cab = B.box("cab", (CX0, CY0, CZ0), (CX1, CY1, CZ1))
PT = 0.18
B.box("par_n", (CX0, CY1, CZ0), (CX1, CY1 + 0.45, CZ0 + PT))
B.box("par_s", (CX0, CY1, CZ1 - PT), (CX1, CY1 + 0.45, CZ1))
B.box("par_w", (CX0, CY1, CZ0 + PT), (CX0 + PT, CY1 + 0.45, CZ1 - PT))
B.box("par_e", (CX1 - PT, CY1, CZ0 + PT), (CX1, CY1 + 0.45, CZ1 - PT))
B.box("cornice", (CX0 - 0.1, CY1 - 0.3, CZ0 - 0.1), (CX1 + 0.1, CY1 - 0.1, CZ1 + 0.1))
B.box("cab_sill", (CX0 - 0.06, CY0, CZ0 - 0.06), (CX1 + 0.06, CY0 + 0.25, CZ1 + 0.06))
for k, o in enumerate(o for o in OPEN if o["center"][1] > 18 and o["center"][1] < 21):
    B.recess(cab, o, 0.25)
    B.sill(f"wsill{k}", o, proud=0.12, thick=0.08, overhang=0.08)
    B.sill(f"whood{k}", o, proud=0.15, thick=0.06, overhang=0.1, top=True)

# ---- stair tower with a sloped roof, coping and plinth course
SX0, SX1, SZ0, SZ1 = -10.03, -6.59, 3.7, 9.71
B.prism_z("stair", [(SX0, 0.0), (SX1, 0.0), (SX1, 22.31), (SX0, 20.59)], SZ0, SZ1)
sl = (22.31 - 20.59) / (SX1 - SX0)
cp = [(SX0 - 0.12, 20.59 - 0.12 * sl - 0.1), (SX1, 22.31 - 0.1), (SX1, 22.31 + 0.12), (SX0 - 0.12, 20.59 - 0.12 * sl + 0.12)]
B.prism_z("coping", cp, SZ0 - 0.12, SZ1 + 0.12)
B.box("stair_base", (SX0 - 0.08, 0.0, SZ0 - 0.08), (SX1, 0.6, SZ1 + 0.08))

# ---- landing platform with a drip edge
PF = [(-1.45, 6.1), (6.1, 6.1), (2.49, 12.61), (-1.45, 10.99)]
B.prism_y("platform", PF, 16.73, 17.25)
ctr = np.mean(PF, 0)
B.prism_y("platform_drip", [tuple(ctr + (np.array(v) - ctr) * 1.02) for v in PF], 16.63, 16.83)

# ---- masts: tapered 24-sided poles with collars
for k, z in enumerate((5.85, 9.28)):
    x = -4.88
    B.prism_y(f"mastfoot{k}", ngon(0.42, 24, x, z), CY1, CY1 + 0.5)
    B.loft_y(f"mast{k}", ngon(0.3, 24, x, z), CY1 + 0.5, ngon(0.05, 24, x, z), 36.98)
    for j, y in enumerate((27.0, 31.0)):
        f = (y - CY1 - 0.5) / (36.98 - CY1 - 0.5)
        r = 0.3 + f * (0.05 - 0.3)
        B.prism_y(f"collar{k}_{j}@avg", ngon(r + 0.06, 24, x, z), y - 0.1, y + 0.1)

print(B.dump())
