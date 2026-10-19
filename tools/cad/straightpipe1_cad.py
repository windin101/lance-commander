#!/usr/bin/env python3
"""CAD rebuild of the short straight pipeline run (appearance straightpipe1), in the original's frame. Also the
shared builder for straightpipe2 and straightpipe3 (tools/cad/straightpipe{2,3}_cad.py import `pipeline`).

    D=~/craft/solid/mc2/buildings/straightpipe1
    python3 -I tools/cad/straightpipe1_cad.py > $D/straightpipe1.json
    solidcraft-cli run $D/straightpipe1.json --out $D/straightpipe1.obj
    python3 -I tools/art/cad_building.py bake straightpipe1 $D/straightpipe1.obj

Measured from game/assets/objects/straightpipe1.glb: a pipe of five-sided section (flat underside 1.0 m wide at
0.52 m, shoulders x +-0.81 at 1.568 m, crown 2.215 m; i.e. a pipe of radius ~0.85 on an axis at 1.37 m) running
z -3.42..3.42 between two trapezoidal end blocks (3.07 m wide at the ground, 1.7 m at 2.726 m, 0.85 m deep,
z +-3.41..4.26). The same texture sheet and pipe as cornerpipe. No cut-outs.
Relief (as cornerpipe): a true 20-sided pipe (r 0.845 m) with 20 cm flanges where it meets each end block and
16 cm joint rings, on concrete saddle supports (the original's pipe floats 0.52 m up); end blocks get a 6 cm
plinth and a chamfered cap.
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

H, R, YC = 2.726, 0.845, 1.37


def ngon(r, n, cx=0.0, cy=0.0):
    return [(cx + r * math.cos(2 * math.pi * (k + 0.5) / n), cy + r * math.sin(2 * math.pi * (k + 0.5) / n)) for k in range(n)]


def end_block(B, name, z0, z1):
    B.prism_z(name, [(-1.534, 0.0), (1.534, 0.0), (0.852, H), (-0.852, H)], z0, z1)
    B.prism_z(f"{name}_plinth", [(-1.62, 0.0), (1.62, 0.0), (1.57, 0.3), (-1.57, 0.3)], z0 - 0.06, z1 + 0.06)
    B.prism_z(f"{name}_cap", [(-0.95, H - 0.02), (0.95, H - 0.02), (0.88, H + 0.08), (-0.88, H + 0.08)], z0 - 0.05, z1 + 0.05)


def support(B, name, z0, z1):
    """The original's low trapezoidal pipe support (3.4 m wide at the ground, 2.14 m at 0.98 m)."""
    B.prism_z(f"{name}@8a8780", [(-1.704, 0.0), (1.704, 0.0), (1.07, 0.98), (-1.07, 0.98)], z0, z1)


def pipeline(B, za, zb, ends=(), supports=(), joints=1):
    """Pipe along z from za to zb (za < zb), flanges at both ends, `joints` evenly spaced joint rings (or a list
    of ring z positions), a saddle in every gap between supports wider than 4 m."""
    B.prism_z("pipe", ngon(R, 20, 0.0, YC), za, zb)
    for k, z in enumerate((za, zb - 0.2)):
        B.prism_z(f"pipe_flange{k}", ngon(R + 0.07, 20, 0.0, YC), z, z + 0.2)
    L = zb - za
    zs = joints if isinstance(joints, (list, tuple)) else [za + L * (k + 1) / (joints + 1) for k in range(joints)]
    for k, z in enumerate(zs):
        B.prism_z(f"pipe_ring{k}", ngon(R + 0.07, 20, 0.0, YC), z - 0.08, z + 0.08)
    for k, (z0, z1) in enumerate(ends):
        end_block(B, f"end{k}", z0, z1)
    for k, (z0, z1) in enumerate(supports):
        support(B, f"support{k}", z0, z1)
    # saddles midway between blocked stretches
    stops = sorted([(za, za)] + [tuple(s) for s in supports] + [(zb, zb)])
    n = 0
    for (a0, a1), (b0, b1) in zip(stops, stops[1:]):
        gap = b0 - a1
        if gap < 4.0:
            continue
        for t in ((0.5,) if gap < 9 else (0.3, 0.7)):
            zc = a1 + gap * t
            B.box(f"saddle{n}@8a8780", (-0.65, 0.0, zc - 0.15), (0.65, YC - 0.35, zc + 0.15))
            n += 1


if __name__ == "__main__":
    B = Builder()
    pipeline(B, -3.41, 3.41, ends=[(-4.26, -3.41), (3.41, 4.26)], joints=1)
    print(B.dump())
