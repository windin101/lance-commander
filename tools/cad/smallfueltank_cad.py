#!/usr/bin/env python3
"""CAD rebuild of the small fuel tank (appearance smallfueltank), in the original's frame.

    D=~/craft/solid/mc2/buildings/smallfueltank
    python3 -I tools/art/cad_building.py decal smallfueltank 0 0.0 0.58 0.5 1.0 > $D/decal_haz.json
    python3 -I tools/art/cad_building.py decal smallfueltank 0 0.2 0.075 0.36 0.205 > $D/decal_fan.json
    python3 -I tools/art/cad_building.py decal smallfueltank 0 0.52 0.46 0.72 0.68 > $D/decal_eye.json
    python3 -I tools/cad/smallfueltank_cad.py $D > $D/smallfueltank.json
    solidcraft-cli run $D/smallfueltank.json --out $D/smallfueltank.obj
    python3 -I tools/art/cad_building.py bake smallfueltank $D/smallfueltank.obj

Measured from game/assets/objects/smallfueltank.glb (no cut-outs): hexagons pointed along z. A sloped plinth
(radius 4.19 m at the ground to 3.32 at 0.85 m), a recessed neck (2.35 m, to 1.46 m), the tank flaring out
to 3.29 m at 2.26 m, walls to 5.39 m, a six-sided cone to 6.7 m; beside it an irregular hexagonal riser
(x 1.64..4.02) to 7.85 m with its own cone to 8.6 m. Relief: the hazard-striped panels are 5 cm recessed
panels in a frame, with a band ledge above them, a skirt lip and an eave lip; ridge ribs on both cones;
the neck's six vents and the riser's fan are real recesses; a lip caps the plinth and the riser.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
B = Builder()
Y0 = 0.03


def hexa(r, cx=0.0, cz=0.0):
    """Hexagon pointed along z (vertices at +-z), counter-clockwise in (x, z) seen from above."""
    return [(cx + r * math.sin(math.radians(a)), cz - r * math.cos(math.radians(a))) for a in range(0, 360, 60)]


def rects(name):
    return json.load(open(D / f"decal_{name}.json"))["rects"]


def ridge_ribs(name, poly, y0, apex, y1, w=0.12, proud=0.06):
    """A bar on each cone ridge, from an eave vertex to the apex."""
    for k, (x, z) in enumerate(poly):
        p0, p1 = np.array([x, y0, z]), np.array([apex[0], y1, apex[1]])
        t = p1 - p0
        L = np.linalg.norm(t)
        t /= L
        out = np.array([x - apex[0], 0.0, z - apex[1]])
        out /= np.linalg.norm(out)
        n = out - t * (out @ t)
        n /= np.linalg.norm(n)
        b = np.cross(n, t)
        B.obox(f"{name}{k}@avg", (p0 + p1) / 2 + n * (proud / 2 - 0.02), t, b, n, (L * 0.97, w, proud + 0.04))


# ---- volumes
B.loft_y("plinth", hexa(4.19), Y0, hexa(3.32), 0.85)
B.prism_y("neck", hexa(2.35), 0.80, 1.46)
B.loft_y("skirt", hexa(2.35), 1.46, hexa(3.29), 2.26)
tank = B.prism_y("tank", hexa(3.285), 2.26, 5.39)
B.loft_y("roof", hexa(3.285), 5.39, hexa(0.04), 6.7)
RISER = [(1.64, -0.66), (2.83, -1.65), (4.02, -0.66), (4.02, 0.72), (2.83, 1.68), (1.64, 0.72)]
riser = B.prism_y("riser", RISER, Y0, 7.85)
B.loft_y("riserroof", RISER, 7.85, [(2.83 + (x - 2.83) * 0.03, z * 0.03) for x, z in RISER], 8.6)

# ---- relief on the tank: framed hazard panels, band ledge, lips
for o in rects("haz"):
    o = dict(o, center=[o["center"][0], o["center"][1] - 0.03, o["center"][2]])
    B.recess(tank, o, 0.05, grow=-0.14)


def ring(name, r_out, r_in, y0, y1, poly=None):
    """A hexagonal ring (a slab with the core cut out, so no buried caps take atlas space)."""
    outer = B.prism_y(name, hexa(r_out), y0, y1)
    B.cut(outer, B.prism_y(f"{name}_core", hexa(r_in), y0 - 0.05, y1 + 0.05))


ring("band@avg", 3.36, 3.2, 4.13, 4.27)
ring("eave@avg", 3.38, 3.2, 5.27, 5.43)
ring("skirtlip@avg", 3.34, 3.2, 2.2, 2.3)
ring("plinthlip@avg", 3.40, 3.2, 0.80, 0.90)
ridge_ribs("rib", hexa(3.285), 5.39, (0.0, 0.0), 6.7)
ridge_ribs("riserrib", RISER, 7.85, (2.83, 0.0), 8.6, w=0.09, proud=0.05)
lip = B.prism_y("riserlip@avg", [(2.83 + (x - 2.83) * 1.06, z * 1.06) for x, z in RISER], 7.76, 7.9)
B.cut(lip, B.prism_y("riserlip_core", [(2.83 + (x - 2.83) * 0.94, z * 0.94) for x, z in RISER], 7.7, 7.95))

# ---- the neck's six vents (8 cm) and the riser's fan (15 cm, only the outward face)
for k, o in enumerate(rects("eye")):
    B.recess("neck", o, 0.08)
for o in rects("fan"):
    if o["normal"][0] > 0.9:
        B.recess(riser, dict(o, w=1.12, h=1.62), 0.15)

print(B.dump())
