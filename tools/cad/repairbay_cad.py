#!/usr/bin/env python3
"""CAD rebuild of the repair bay (appearance repairbay), in the original's frame.

    D=~/craft/solid/mc2/buildings/repairbay
    python3 -I tools/art/cad_building.py openings repairbay > $D/openings.json
    python3 -I tools/cad/repairbay_cad.py $D > $D/repairbay.json
    solidcraft-cli run $D/repairbay.json --out $D/repairbay.obj
    python3 -I tools/art/cad_building.py bake repairbay $D/repairbay.obj

Measured from game/assets/objects/repairbay.glb: two 8.74 x 4.25 m wings (x -3.66..5.08, z +-5.46..+-9.71, 4.58 m)
flank the repair floor (y 0.15) and its striped pad (Ramp, y 0.33-0.37, x -3.5..3.91); behind them a 9.06 m block
(x 5.08..9.33, z -9.71..6.35, its -z corner cut back to (9.33, -6.55)), a lean-to annex on +x (z -6.55..0, 9.06 ->
6.86 m) and a sloped porch on +z (x 5.08..7.91, 5.59 -> 3.66 m); the bay doors (Doors) at x 4.94. The LOS_Gantry:
a hooded tower on each wing (x -2.82..2.76, z +-6.50..+-8.60, 6.64 m, hip to 7.74 m) and between them a hexagonal
tube bridge (bottom 5.62 m, x -2.62..2.56, sides to 6.44, top 7.54 at x -1.66..1.46) whose panels are alpha truss
cut-outs: here real members (six chords, three ring frames, deck and top stringers), solid striped side plates and
closed end collars (z +-5.21..+-6.50, the dark frame of the art, one flat colour: sampled, their end faces took the towers' glass). Green beacons (3-sided in the original) are round
16-gon lamps on collars (issue I77). Relief: windows 15 cm recesses with sills, the bay doors a 20 cm recess,
parapets on the block and wing roofs, the repair pad a real 20 cm plinth with chamfered ends, corner trims.
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


def ngon(r, cx=0.0, cz=0.0, k=16):
    return [(cx + r * math.cos(2 * math.pi * i / k), cz + r * math.sin(2 * math.pi * i / k)) for i in range(k)]


def bar(name, p, q, n, depth, thick):
    """A bar from p to q (game m), its depth across along b = n x t, thickness along n."""
    p, q = np.array(p, float), np.array(q, float)
    t = (q - p) / np.linalg.norm(q - p)
    n = np.array(n, float)
    b = np.cross(n, t)
    return B.obox(name, (p + q) / 2, t, b, n, (float(np.linalg.norm(q - p)), depth, thick))


# ---- volumes
YW, YB = 4.58, 9.06
wings = [B.box("wingS", (-3.66, 0.0, -9.71), (5.08, YW, -5.45)), B.box("wingN", (-3.66, 0.0, 5.46), (5.08, YW, 9.71))]
BLOCK = [(5.08, -9.71), (9.33, -6.55), (9.33, 6.35), (5.08, 6.35)]
block = B.prism_y("block", BLOCK, 0.0, YB)
annex = B.prism_z("annex", [(9.33, 0.0), (12.19, 0.0), (12.19, 6.86), (9.33, YB)], -6.55, 0.0)
porch = B.prism_x("porch", [(6.35, 0.0), (9.36, 0.0), (9.36, 3.66), (6.35, 5.59)], 5.08, 7.91)

# ---- windows, bay doors
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    c, n = o["center"], o["normal"]
    if c[0] < 4.9:
        continue   # gantry truss cut-outs: built as members below
    x, z = c[0], c[2]
    tgt = porch if z > 6.4 else annex if x > 9.4 or (abs(z + 6.55) < 0.02 and x > 9.3) or (abs(z) < 0.02 and x > 9.3) else block
    # keep the outward copy of each cut-out only (the art is double sided)
    if tgt == block and abs(x - 5.08) < 0.02 and n[0] > 0:
        continue
    if tgt == block and abs(x - 9.33) < 0.02 and n[0] < 0:
        continue
    B.recess(tgt, o, 0.15)
    B.sill(f"sill{k}", o, proud=0.10, thick=0.06, overhang=0.06)
door = {"center": [5.08, 1.23, -3.41], "normal": [-1, 0, 0], "t": [0, 0, 1], "b": [0, 1, 0], "w": 2.68, "h": 1.84}
B.recess(block, door, 0.20)
B.sill("doorhood@avg", door, proud=0.20, thick=0.10, overhang=0.12, top=True)

# ---- parapets and corner trims
def parapet(prefix, poly, y, h=0.25, th=0.20):
    ctr = np.mean(poly, axis=0)
    for i in range(len(poly)):
        (x0, z0), (x1, z1) = poly[i], poly[(i + 1) % len(poly)]
        e = np.array([x1 - x0, 0.0, z1 - z0])
        L = np.linalg.norm(e)
        inward = np.array([-(z1 - z0), 0.0, x1 - x0]) / L
        if np.dot(inward, np.array([ctr[0] - x0, 0, ctr[1] - z0])) < 0:
            inward = -inward
        m = np.array([(x0 + x1) / 2, y + h / 2, (z0 + z1) / 2]) + inward * th / 2
        B.obox(f"{prefix}{i}", m, e / L, np.array([0.0, 1.0, 0.0]), np.cross(e / L, [0.0, 1.0, 0.0]), (L + th, h, th))


parapet("parB", BLOCK, YB)
parapet("parS", [(-3.66, -9.71), (5.08, -9.71), (5.08, -5.45), (-3.66, -5.45)], YW, h=0.18, th=0.15)
parapet("parN", [(-3.66, 5.46), (5.08, 5.46), (5.08, 9.71), (-3.66, 9.71)], YW, h=0.18, th=0.15)
for k, (x, z, h) in enumerate(((-3.66, -9.71, YW), (-3.66, -5.45, YW), (-3.66, 5.46, YW), (-3.66, 9.71, YW),
                               (9.33, 6.35, YB), (12.19, 0.0, 6.86), (12.19, -6.55, 6.86))):
    B.box(f"trim{k}", (x - 0.07, 0.0, z - 0.07), (x + 0.07, h - 0.03, z + 0.07))

# ---- repair floor and pad
B.box("floor", (-3.62, 0.0, -5.45), (5.08, 0.15, 5.46))
B.box("pad", (-3.50, 0.15, -5.40), (3.91, 0.35, 5.40), chamfer=0.12,
      chamfer_edges=[(-3.50, 0.35, 0.0), (3.91, 0.35, 0.0)])

# ---- gantry towers
TOWER = [(-2.82, 4.50), (2.76, 4.50), (2.76, 6.64), (1.66, 7.74), (-1.86, 7.74), (-2.82, 6.64)]
for k, (z0, z1) in enumerate(((-8.60, -6.50), (6.50, 8.60))):
    B.prism_z(f"tower{k}", TOWER, z0, z1)
    B.box(f"towerbase{k}@avg", (-2.92, 4.50, z0 - 0.10), (2.86, 4.72, z1 + 0.10))

# ---- the truss bridge
HEX = [(-2.62, 5.62), (2.56, 5.62), (2.56, 6.44), (1.46, 7.54), (-1.66, 7.54), (-2.62, 6.44)]
ZE = 6.50
for k, (x, y) in enumerate(HEX):
    B.box(f"chord{k}", (x - 0.10, y - 0.10, -5.21), (x + 0.10, y + 0.10, 5.21))
for j, zr in enumerate((-2.81, -0.18, 2.59)):
    for i in range(6):
        (xa, ya), (xb, yb) = HEX[i], HEX[(i + 1) % 6]
        bar(f"ring{j}_{i}", (xa, ya, zr), (xb, yb, zr), (0, 0, 1), 0.18, 0.30)
for k, (x, y) in enumerate(((-1.54, 5.62), (-0.55, 5.62), (-0.55, 7.54))):
    B.box(f"stringer{k}", (x - 0.09, y - 0.07, -5.21), (x + 0.09, y + 0.07, 5.21))
for k, x in enumerate((2.56, -2.62)):
    B.box(f"side{k}", (x - 0.05, 5.62, -5.21), (x + 0.05, 6.44, 5.21))
for k, (z0, z1) in enumerate(((-ZE, -5.21), (5.21, ZE))):
    B.prism_z(f"collar{k}@2f3033", [(x + (0.06 if x > 0 else -0.06), y + (0.06 if y > 7 else -0.06)) for x, y in HEX], z0, z1)

# ---- beacons: round lamps on collars
for k, (x, y, z) in enumerate(((8.83, YB, -5.73), (8.83, YB, 5.64), (-1.48, 7.74, -7.75), (1.10, 7.74, -7.75),
                               (-1.48, 7.74, 7.85), (1.10, 7.74, 7.85))):
    B.prism_y(f"lampbase{k}", ngon(0.30, x, z), y, y + 0.10)
    B.loft_y(f"lamp{k}", ngon(0.24, x, z), y + 0.10, ngon(0.15, x, z), y + 0.62)

print(B.dump())
