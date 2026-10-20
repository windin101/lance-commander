#!/usr/bin/env python3
"""CAD rebuild of the orbital defence turret (appearance orbitalturret), in the original's frame.

    D=~/craft/solid/mc2/buildings/orbitalturret
    python3 -I tools/art/cad_building.py decal orbitalturret 0 0.0 0.34 0.12 0.5 > $D/decal_plateL.json
    python3 -I tools/art/cad_building.py decal orbitalturret 0 0.38 0.34 0.5 0.5 > $D/decal_plateR.json
    python3 -I tools/cad/orbitalturret_cad.py $D > $D/orbitalturret.json
    solidcraft-cli run $D/orbitalturret.json --out $D/orbitalturret.obj
    python3 -I tools/art/cad_building.py bake orbitalturret $D/orbitalturret.obj --texel 0.015

Measured from game/assets/objects/orbitalturret.glb (Base, Mog_Turret, Mog_Guns; no cut-outs, no animation):
a square plinth frustum (x -3.73..12.14, z -3.65..12.22 at the ground to x -2.62..11.02, z -2.54..11.11 at 3.1 m),
a pedestal frustum to 6.08 m, the turret (x 0.93..7.47, a five-sided profile in z, 6.37..8.78 m) floating 0.29 m
above it, two gun mantlets and two tapered five-sided barrels pitched up toward +z (to 18.3 m).
The barrels are meant to be round (Lee, I77): 24-sided cones on the original's axes (r 0.90 -> 0.52 m).
Relief: the painted corner plates on the plinth are 6 cm plates with two round bolt heads each, a skirt at the
pedestal foot (on the painted seam line), a slewing ring that fills the gap under the turret, a collar at each
barrel root and a bore in each muzzle.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, cad, cad_dir  # noqa: E402

D = Path(sys.argv[1])
B = Builder()


def sq(x0, z0, x1, z1):
    return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]


def ngon(cx, cz, r, n=24, a0=0.0):
    return [(cx + r * math.cos(math.radians(a0 + 360.0 * k / n)), cz + r * math.sin(math.radians(a0 + 360.0 * k / n))) for k in range(n)]


def cone(name, p0, p1, r0, r1, n=24):
    """A 24-sided frustum from p0 (radius r0) to p1 (r1): lofted upright at the origin, then turned onto its axis."""
    L = float(np.linalg.norm(np.subtract(p1, p0)))
    B.loft_y(name, ngon(0.0, 0.0, r0, n), 0.0, ngon(0.0, 0.0, r1, n), L)
    d = cad_dir(np.subtract(p1, p0) / L)
    ax = np.cross([0.0, 0.0, 1.0], d)
    ang = math.degrees(math.acos(max(-1.0, min(1.0, d[2]))))
    if np.linalg.norm(ax) > 1e-9:
        B.c("solid.move", bodies=[name], axis=[round(float(v), 6) for v in ax / np.linalg.norm(ax)], angle=f"{ang:.4f} deg")
    B.c("solid.move", bodies=[name], translate=cad(p0))
    return name


# ---- volumes
B.loft_y("plinth", sq(-3.73, -3.65, 12.14, 12.22), 0.0, sq(-2.62, -2.54, 11.02, 11.11), 3.1)
B.loft_y("pedestal", sq(-0.04, 0.05, 8.44, 8.53), 3.1, sq(0.63, 0.72, 7.77, 7.86), 6.08)
TURRET = [(0.02, 6.37), (8.27, 6.37), (7.24, 8.78), (4.15, 8.78), (0.53, 7.58)]
B.prism_x("turret", TURRET, 0.93, 7.47)
MANTLET = [(9.04, 7.07), (5.02, 7.42), (4.8, 8.26), (5.33, 8.93), (8.32, 9.73)]
B.prism_x("mantlet0", MANTLET, 1.28, 3.68)
B.prism_x("mantlet1", MANTLET, 4.77, 7.18)

# ---- barrels on the original's axes (pentagon centroids), with a root collar and a muzzle bore
for k, x in enumerate((2.48, 5.98)):
    p0, p1 = np.array([x, 8.22, 8.68]), np.array([x, 10.76, 18.2])
    ax = (p1 - p0) / np.linalg.norm(p1 - p0)
    L = np.linalg.norm(p1 - p0)
    cone(f"barrel{k}", p0, p1, 0.90, 0.52)
    r_at = lambda s: 0.90 + (0.52 - 0.90) * s / L  # noqa: E731
    cone(f"collar{k}@avg", p0 + ax * 0.55, p0 + ax * 1.05, r_at(0.55) + 0.1, r_at(1.05) + 0.1)
    cone(f"muzzle{k}", p1 - ax * 0.7, p1 - ax * 0.02, 0.6, 0.6)
    B.cut(f"muzzle{k}", cone(f"bore{k}", p1 - ax * 0.45, p1 + ax * 0.1, 0.3, 0.3, n=20))
    B.cut(f"barrel{k}", cone(f"bore{k}b", p1 - ax * 0.45, p1 + ax * 0.1, 0.3, 0.3, n=20))

# ---- slewing ring in the 0.29 m gap under the turret, skirt on the pedestal foot
B.prism_y("ring@3e423c", ngon(4.2, 4.15, 3.1, n=32), 6.06, 6.39)
skirt = B.prism_y("skirt", sq(-0.16, -0.07, 8.56, 8.65), 3.08, 3.36)
B.cut(skirt, B.prism_y("skirt_core", sq(0.3, 0.4, 8.1, 8.2), 3.0, 3.45))

# ---- corner plates with bolt heads on the plinth slopes
plates = json.load(open(D / "decal_plateL.json"))["rects"] + json.load(open(D / "decal_plateR.json"))["rects"]
for k, o in enumerate(plates):
    n, t, b = (np.array(o[q], float) for q in ("normal", "t", "b"))
    c = np.array(o["center"], float)
    w, h = o["w"] * 0.73, o["h"] * 0.92
    inward = t if (np.array([4.2, c[1], 4.28]) - c) @ t > 0 else -t  # off the corner edge, which leans in
    B.obox(f"plate{k}", c + inward * 0.31 + n * 0.02, t, b, n, (w, h, 0.08))
    for j, f in enumerate((0.34, 0.78)):
        bc = c + b * (h / 2 - f * h) + n * 0.06
        cone(f"bolt{k}_{j}@2c2a26", bc, bc + n * 0.09, 0.2, 0.17, n=12)

print(B.dump())
