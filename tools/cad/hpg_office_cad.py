#!/usr/bin/env python3
"""CAD rebuild of the HPG office ziggurat (appearance hpg_office), in the original's frame.

    D=~/craft/solid/mc2/buildings/hpg_office
    python3 -I tools/art/cad_building.py openings hpg_office > $D/openings.json      # the window band (cut-outs)
    C="python3 -I tools/art/cad_building.py decal hpg_office 0"                       # rects are texture px / 512:
    slot (228,243,323,251)  vent (22,292,95,350)  emblem (16,28,102,222)  annexroof (125,10,205,150)
    kdoor (233,152,258,192)  towerroof (340,55,460,160)
    python3 -I tools/cad/hpg_office_cad.py $D > $D/hpg_office.json
    solidcraft-cli run $D/hpg_office.json --out $D/hpg_office.obj
    python3 -I tools/art/cad_building.py bake hpg_office $D/hpg_office.obj --glass 72,102,134   # the blue of the hollow storey seen through the band

Measured from game/assets/objects/hpg_office.glb (node "HPG Ziggurat", 102 triangles): a 1.54 m plinth (x
-9.86..7.38, z +-8.92) under a battered block to a terrace at 11.41 m (x -5.8..3.92, z +-5.45), its window band a
ring of cut-outs looking into a hollow storey (floor 8.28 m); a leaning tower slab (z +-3.12) from the terrace to
15.94 m (x -2.18..5.32) whose east face runs straight down to a 1.54 m foot at x 10.63 (the emblem face); a west
annex (x -12.8..-9.85, z +-6.41 battered to +-4.38 at 6.72 m); two door kiosks with sloped tops on the east plinth.
Relief: the windows are 30 cm recesses (glass at the back) with sills, so the painted mullions are real; ledges
ring the plinths, copings ring the terrace, the tower top and the annex roof; the painted roof panels are 10 cm
recesses; the tower's slots and west vent are recesses; the emblem is a proud sign plate; kiosk doors recessed.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
B = Builder()
PL = 1.54


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def rects(name):
    return json.load(open(D / f"decal_{name}.json"))["rects"]


def proud(name, o, p, grow=0.0):
    n, t, b = (np.array(o[k], float) for k in ("normal", "t", "b"))
    return B.obox(name, np.array(o["center"]) + n * (p / 2 - 0.02), t, b, n, (o["w"] + grow, o["h"] + grow, p + 0.02))


def edge_bands(prefix, poly, y0, y1, out, inward=0.0, skip=()):
    """Boxes along the edges of a counter-clockwise (x, z) polygon, from `inward` inside to `out` outside it."""
    for i in range(len(poly)):
        if i in skip:
            continue
        a, c = np.array(poly[i]), np.array(poly[(i + 1) % len(poly)])
        e = unit(c - a)
        nrm = np.array([e[1], -e[0]])
        mid = (a + c) / 2 + nrm * (out - inward) / 2
        t, n = np.array([e[0], 0, e[1]]), np.array([nrm[0], 0, nrm[1]])
        B.obox(f"{prefix}{i}", (mid[0], (y0 + y1) / 2, mid[1]), t, np.cross(n, t), n, (np.linalg.norm(c - a) + 2 * out, y1 - y0, out + inward))


def rect(x0, x1, z0, z1):
    return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]  # counter-clockwise in (x, z)


# ---- volumes
M_BOT, M_TOP = rect(-9.86, 7.38, -8.92, 8.92), rect(-5.8, 3.92, -5.45, 5.45)
B.prism_y("plinth", M_BOT, 0.0, PL)
main = B.loft_y("main", M_BOT, PL, M_TOP, 11.41)
A_BOT, A_TOP = rect(-12.8, -7.0, -6.41, 6.41), rect(-12.8, -7.0, -4.38, 4.38)
B.prism_y("aplinth", rect(-12.8, -9.5, -6.41, 6.41), 0.0, PL)
annex = B.loft_y("annex", A_BOT, PL, A_TOP, 6.72)
TOWER = [(7.38, 0.0), (10.63, 0.0), (10.63, PL), (5.32, 15.94), (-2.18, 15.94), (-3.88, 11.41), (3.92, 11.41), (7.38, PL)]
tower = B.prism_z("tower", [(x, y) for x, y in TOWER], -3.12, 3.12)
for s, (za, zb) in enumerate(((-6.91, -5.27), (5.27, 6.9))):
    B.prism_z(f"kiosk{s}", [(6.82, 0.0), (7.92, 0.0), (7.92, 2.36), (6.82, 2.95)], za, zb)
    B.prism_z(f"kioskcap{s}", [(6.74, 2.9), (8.0, 2.31), (8.0, 2.39), (6.74, 3.01)], za - 0.08, zb + 0.08)

# ---- window band: one recess per cut-out pane (outward faces only; the rest are the shell's back faces)
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    if o["normal"][1] <= 0:
        continue
    B.recess(main, o, 0.30)
    B.sill(f"sill{k}", o, proud=0.10, thick=0.07, overhang=0.04)

# ---- tower relief
for o in rects("slot"):
    B.recess(tower, o, 0.15)
for o in rects("vent"):
    B.recess(tower, dict(o, w=o["w"] - 0.3, h=o["h"] - 0.3), 0.15)
for o in rects("emblem"):
    proud("emblem", o, 0.08, grow=0.1)
for o in rects("towerroof"):
    B.recess(tower, o, 0.10)
for o in rects("annexroof"):
    B.recess(annex, o, 0.10)
for o in rects("kdoor"):
    B.recess(f"kiosk{0 if o['center'][2] < 0 else 1}", o, 0.06)

# ---- ledges and copings
edge_bands("ledge", M_BOT, PL - 0.12, PL + 0.04, 0.10)
edge_bands("aledge", rect(-12.8, -9.86, -6.41, 6.41), PL - 0.12, PL + 0.04, 0.10, skip=(1,))
edge_bands("tcoping", M_TOP, 11.41, 11.55, 0.04, inward=0.35)
edge_bands("acoping", rect(-12.8, -7.73, -4.38, 4.38), 6.72, 6.86, 0.04, inward=0.3, skip=(1,))
edge_bands("rcoping", rect(-2.18, 5.32, -3.12, 3.12), 15.94, 16.1, 0.04, inward=0.3)

print(B.dump())
