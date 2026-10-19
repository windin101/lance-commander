#!/usr/bin/env python3
"""CAD rebuild of the sensor control building (appearance s_sensorcontrol), in the original's frame.

    D=~/craft/solid/mc2/buildings/s_sensorcontrol
    python3 -I tools/art/cad_building.py openings s_sensorcontrol > $D/openings.json
    python3 -I tools/cad/s_sensorcontrol_cad.py $D > $D/s_sensorcontrol.json
    solidcraft-cli run $D/s_sensorcontrol.json --out $D/s_sensorcontrol.obj
    python3 -I tools/art/cad_building.py bake s_sensorcontrol $D/s_sensorcontrol.obj --keep L_Dish

Measured from game/assets/objects/s_sensorcontrol.glb (faces grouped by plane): a low block (x -11.00..0.20,
z -2.60..10.40, 8.80 m) whose west wall stands 1.2 m back below 4 m between three legs; a tower (x -4.20..3.63,
z -1.60..3.20) to 16.65 m, a cab flaring out to 19.43 m (x -5.34..4.76, z -2.23..3.83) and straight to the 20.71 m
roof, carrying the dish (L_Dish, kept verbatim). The antenna cluster on the low block's roof is three alpha cards
in the original (two crossed at (-5.72, 6.67), one at x -1.76): their opaque texels are decomposed into rectangles
(greedy largest-first on a 4 cm grid) and each becomes a real part on the card's plane: a true round pole (20 sides) where
the rectangle is tall and thin (issue I77), a box as deep as it is wide (at most 0.5 m) otherwise; the bake paints
them from the card art (masts, red and gold bands). Relief: every cut-out window is a 20 cm recess (sills under
the tall ones), the tower roof field is an 8 cm recess, a ledge rings the tower at the cab's foot.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "art"))
from building_cad import Builder, cad, cad_dir  # noqa: E402

D = Path(sys.argv[1])
B = Builder()

# ---- low block with the recessed west wall
low = B.box("low", (-9.80, 0.0, -2.60), (0.20, 8.80, 10.40))
upper_w = B.box("low_w", (-11.00, 4.00, -2.60), (-9.80, 8.80, 10.40))
for k, (z0, z1) in enumerate([(-2.60, -1.60), (3.20, 4.40), (9.20, 10.40)]):
    B.box(f"leg{k}", (-11.00, 0.0, z0), (-9.80, 4.00, z1))

# ---- tower and cab
tower = B.box("tower", (-4.20, 0.0, -1.60), (3.63, 16.65, 3.20))
flare = B.loft_y("flare", [(-4.20, -1.60), (3.63, -1.60), (3.63, 3.20), (-4.20, 3.20)], 16.65,
                 [(-5.34, -2.23), (4.76, -2.23), (4.76, 3.83), (-5.34, 3.83)], 19.43)
cab = B.box("cab", (-5.34, 19.43, -2.23), (4.76, 20.71, 3.83), chamfer=0.04)
B.cut(cab, B.box("cab_field", (-4.94, 20.63, -1.83), (4.36, 20.9, 3.43)))
B.box("ledge", (-4.32, 16.50, -1.72), (3.75, 16.70, 3.32))

# ---- windows
CARD = [(0, -5.715), (2, 6.67), (0, -1.755)]
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    c = o["center"]
    if o["w"] > 3.5 or c[1] > 20.6 or any(abs(c[a] - v) < 0.08 for a, v in CARD):
        continue  # the antenna cards, the dish
    x, y, z = c
    if y > 16.6:
        tgt = flare
    elif -4.25 < x < 3.7 and -1.65 < z < 3.25:
        tgt = tower
    elif x < -9.7 and y < 4.0:
        tgt = low
    elif x < -9.7:
        tgt = upper_w
    else:
        tgt = low
    B.recess(tgt, o, 0.2)
    if o["h"] > 1.5 and abs(o["normal"][1]) < 0.1:
        B.sill(f"sill{k}", o, proud=0.1, thick=0.07, overhang=0.06)


# ---- the antenna cards as real parts
def card_mask(O, ax, val, sax, G=0.04):
    sel = np.where((O.normal[:, ax] > 0.99) & (np.abs(O.tris.mean(1)[:, ax] - val) < 0.06))[0]
    T = O.tris[sel].reshape(-1, 3)
    lo, hi = T.min(0), T.max(0)
    ss, ys = np.arange(lo[sax], hi[sax], G) + G / 2, np.arange(lo[1], hi[1], G) + G / 2
    S, Y = np.meshgrid(ss, ys)
    P = np.c_[S.ravel(), Y.ravel()]
    A = np.zeros(len(P))
    for ti in sel:
        t = O.tris[ti][:, [sax, 1]]
        m = np.c_[t[1] - t[0], t[2] - t[0]]
        bc = np.linalg.solve(m, (P - t[0]).T).T
        ins = (bc[:, 0] >= -1e-6) & (bc[:, 1] >= -1e-6) & (bc.sum(1) <= 1 + 1e-6)
        if ins.any():
            uv = O.uvs[ti]
            u = uv[0] + bc[ins, :1] * (uv[1] - uv[0]) + bc[ins, 1:] * (uv[2] - uv[0])
            A[ins] = np.maximum(A[ins], O.sample_image(O.mat_image[O.mat[ti]], u)[:, 3])
    return (A.reshape(S.shape) > 0.5), lo[sax], lo[1], G


def largest_rect(M):
    h = np.zeros(M.shape[1], int)
    best = (0, None)
    for r in range(M.shape[0]):
        h = np.where(M[r], h + 1, 0)
        st = []
        for c in range(len(h) + 1):
            cur = h[c] if c < len(h) else 0
            s = c
            while st and st[-1][1] >= cur:
                s, hh = st.pop()
                a = hh * (c - s)
                if a > best[0] and hh >= 2 and c - s >= 2:
                    best = (a, (r - hh + 1, r + 1, s, c))
            st.append((s, cur))
    return best


def rects(M, min_cells=12):
    M = M.copy()
    out = []
    while True:
        a, r = largest_rect(M)
        if r is None or a < min_cells:
            return out
        r0, r1, c0, c1 = r
        M[r0:r1, c0:c1] = False
        out.append(r)


from cad_building import Original  # noqa: E402

O = Original("s_sensorcontrol")
n_part = 0
for ax, val, sax in ((0, -5.715, 2), (2, 6.67, 0), (0, -1.755, 2)):
    M, s0, y0, G = card_mask(O, ax, val, sax)
    for r0, r1, c0, c1 in rects(M):
        n_part += 1
        sa, sb, ya, yb = s0 + c0 * G, s0 + c1 * G, y0 + r0 * G, y0 + r1 * G
        w, h = sb - sa, yb - ya
        sc = (sa + sb) / 2
        p = [0.0, 0.0, 0.0]
        p[ax], p[sax], p[1] = val, sc, ya
        if h > 4 * w and w < 0.6:
            cx, cz = p[0], p[2]
            B.prism_y(f"ant{n_part}", [(cx + w / 2 * math.cos(2 * math.pi * i / 20), cz + w / 2 * math.sin(2 * math.pi * i / 20))
                                       for i in range(20)], ya, yb)
        else:
            lo, hi = [0.0] * 3, [0.0] * 3
            dep = min(w, h, 0.5)
            lo[ax], hi[ax] = val - dep / 2, val + dep / 2
            lo[sax], hi[sax] = sa, sb
            lo[1], hi[1] = ya, yb
            B.box(f"ant{n_part}", lo, hi)
print(f"{n_part} antenna parts", file=sys.stderr)
print(B.dump())
