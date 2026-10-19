#!/usr/bin/env python3
"""CAD rebuild of the sensor-control HQ (appearance d_hq), in the original's frame.

    D=~/craft/solid/mc2/buildings/d_hq
    python3 -I tools/art/cad_building.py openings d_hq > $D/openings.json
    python3 -I tools/art/cad_building.py decal d_hq 0 0.08 0.78 0.29 0.985 > $D/decal_door.json
    python3 -I tools/cad/d_hq_cad.py $D > $D/d_hq.json
    solidcraft-cli run $D/d_hq.json --out $D/d_hq.obj
    python3 -I tools/art/cad_building.py bake d_hq $D/d_hq.obj

Measured from game/assets/objects/d_hq.glb (vertices listed by height): a tower (11.3 x 7.95 m, its front sloping
back above 7.58 m) under an overhanging 3.9 m control cab to 17.74 m; a hall (11.3 x 23.8 m) with a mono-pitch
roof rising from 7.58 to 10.17 m; an annex down the hall's side whose roof falls from 7.58 to 4.33 m, with a flat
2-storey end. Relief: every cut-out window a 25 cm recess (from the texture), the roller door a 30 cm recess;
the four painted roof bands of hall and annex are real portal frames (20 cm proud over walls and roof); a ledge
rings the tower where its front starts to slope; the cab has a 40 cm parapet; gutters run along both low eaves;
the five antenna masts are hexagonal posts instead of crossed cards.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
Y0 = 0.04  # the original sits 4 cm up (node SensorControl)
B = Builder()


def offset_convex(poly, d):
    """Outward offset of a convex polygon (counter-clockwise), mitred; vertices under the ground clamp to it."""
    n = len(poly)
    lines = []
    for i in range(n):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
        ex, ey = x1 - x0, y1 - y0
        L = math.hypot(ex, ey)
        nx, ny = ey / L, -ex / L
        lines.append(((x0 + nx * d, y0 + ny * d), (ex, ey)))
    out = []
    for i in range(n):
        (p, e), (q, f) = lines[i - 1], lines[i]
        det = e[0] * -f[1] + f[0] * e[1]
        t = ((q[0] - p[0]) * -f[1] + f[0] * (q[1] - p[1])) / det
        out.append((p[0] + e[0] * t, max(0.0, p[1] + e[1] * t)))
    return out


# ---- volumes
tower_prof = [(-15.87, 0.0), (-7.92, 0.0), (-7.92, 13.86), (-14.2, 13.86), (-15.85, 7.58)]  # (z, y)
tower = B.prism_x("tower", tower_prof, -9.14, 2.16)
cab = B.box("cab", (-9.68, 13.86, -14.95), (2.72, 17.74, -7.17))
hall_prof = [(-9.14, 0.0), (2.16, 0.0), (2.16, 10.17), (-9.14, 7.58)]  # (x, y), counter-clockwise
hall = B.prism_z("hall", hall_prof, -7.92, 15.87)
annex_prof = [(2.16, 0.0), (9.68, 0.0), (9.68, 4.33), (2.16, 7.58)]
annex = B.prism_z("annex", annex_prof, -7.92, 8.37)
annex_end = B.box("annex_end", (2.16, 0.0, 8.37), (9.68, 7.58, 14.62))

# one body for the walls, so every opening cuts the same solid
B.join(tower, [cab, hall, annex, annex_end])

# ---- openings: windows 25 cm, panes at the back; skip the masts' cut-out cards
for o in json.load(open(D / "openings.json"))["openings"]:
    if o["w"] < 0.3 or o["h"] < 0.2:
        continue
    B.recess(tower, o, 0.25)
for o in json.load(open(D / "decal_door.json"))["rects"]:  # the roller door(s)
    B.recess(tower, o, 0.30)


def portal(prof, d):
    """An inverted U round a [bottom-left, bottom-right, top-right, top-left] wall-and-roof profile."""
    o = offset_convex(prof, d)
    return [o[0], o[3], o[2], o[1], prof[1], prof[2], prof[3], prof[0]]


# ---- portal frames on the four painted roof bands (hall and annex)
for k, (za, zb) in enumerate(((-7.92, -6.69), (-0.46, 0.81), (7.1, 8.37), (14.62, 15.87))):
    B.prism_z(f"frame_hall{k}", portal(hall_prof, 0.2), za + 0.15, zb - 0.15)
    if zb <= 8.37:
        B.prism_z(f"frame_annex{k}", portal(annex_prof, 0.2), za + 0.15, zb - 0.15)

# ---- ledge round the tower at the slope break, cab parapet, gutters
B.box("ledge", (-9.39, 7.43 + Y0 - 0.04, -16.1), (2.41, 7.73, -7.92))
for k, (lo, hi) in enumerate((((-9.68, 17.74, -14.95), (2.72, 18.14, -14.75)), ((-9.68, 17.74, -7.37), (2.72, 18.14, -7.17)),
                              ((-9.68, 17.74, -14.75), (-9.48, 18.14, -7.37)), ((2.52, 17.74, -14.75), (2.72, 18.14, -7.37)))):
    B.box(f"parapet{k}", lo, hi)
B.box("gutter_hall@8c8c84", (-9.42, 7.36, -7.92), (-9.14, 7.6, 15.87))
B.box("gutter_annex@8c8c84", (9.68, 4.11, -7.92), (9.96, 4.35, 8.37))

# ---- antenna masts: hexagonal posts on the original masts' axes
for k, (x, z, y0, y1) in enumerate(((9.135, 13.97, 7.58, 23.28), (9.135, 11.76, 7.58, 18.35), (7.23, 13.97, 7.58, 15.13),
                                    (2.155, -10.175, 17.74, 26.4), (2.155, -12.385, 17.74, 24.39))):
    r = 0.07
    B.prism_y(f"mast{k}@b4b4ae", [(x + r * math.cos(a * math.pi / 3), z + r * math.sin(a * math.pi / 3)) for a in range(6)], y0 - 0.1, y1)

print(B.dump())
