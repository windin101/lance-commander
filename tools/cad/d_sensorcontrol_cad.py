#!/usr/bin/env python3
"""CAD rebuild of the desert sensor control building (appearance d_sensorcontrol), in the original's frame.

    D=~/craft/solid/mc2/buildings/d_sensorcontrol
    python3 -I tools/art/cad_building.py openings d_sensorcontrol > $D/openings.json
    python3 -I tools/cad/d_sensorcontrol_cad.py $D > $D/d_sensorcontrol.json
    solidcraft-cli run $D/d_sensorcontrol.json --out $D/d_sensorcontrol.obj
    python3 -I tools/art/cad_building.py bake d_sensorcontrol $D/d_sensorcontrol.obj --keep L_Dish

Measured from game/assets/objects/d_sensorcontrol.glb (faces grouped by plane): a west block (x -12.05..-5.24,
z -2.75..10.34) with walls to 7.58 m and a mono-pitch roof rising to 10.17 m at its east wall; an east annex
(x -5.24..-0.83, z -2.75..10.31) with a roof falling from 7.58 m to 4.33 m at its front, and a raised middle band
(z 4.42..9.20) flat at 7.58 m over the garage door; the tower (x -5.24..2.61, z -1.63..3.19) to 16.65 m and its
overhanging cab (x -6.36..3.73, z -2.41..4.03) to the 20.69 m roof carrying the dish (L_Dish, kept verbatim).
The antenna cluster on the west roof is three alpha cards in the original (two crossed at (-6.46, 6.17), one at
x -8.585): their opaque texels become real parts on the card's plane as in s_sensorcontrol_cad.py (true round
poles, 20 sides, where a rectangle is tall and thin; issue I77). Relief: every cut-out window is a 20 cm recess
(sills under the tall ones), the garage door a 25 cm one with a hood (the gable's paired window stays
flat: one opening spans both panes), the cab roof field an 8 cm recess, a ledge
rings the tower under the cab and a fascia runs along both roof eaves.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "art"))
from building_cad import Builder  # noqa: E402

D = Path(sys.argv[1])
B = Builder()

# ---- west block with its mono-pitch roof
west = B.prism_z("west", [(-12.05, 0.0), (-5.24, 0.0), (-5.24, 10.17), (-12.05, 7.58)], -2.75, 10.34)
B.box("west_fascia", (-12.20, 7.40, -2.85), (-12.00, 7.70, 10.44))
# ---- east annex: falling roof, raised middle band
annex = B.prism_z("annex", [(-5.24, 0.0), (-0.83, 0.0), (-0.83, 4.33), (-5.24, 7.58)], -2.75, 10.31)
band = B.box("annex_band", (-5.24, 0.0, 4.42), (-0.83, 7.58, 9.20))
B.box("annex_fascia0", (-0.88, 4.15, -2.85), (-0.68, 4.45, 4.42))
B.box("annex_fascia1", (-0.88, 4.15, 9.20), (-0.68, 4.45, 10.41))
B.box("band_cap", (-5.24, 7.50, 4.32), (-0.73, 7.66, 9.30))
# ---- tower and cab
tower = B.box("tower", (-5.24, 0.0, -1.63), (2.61, 16.65, 3.19))
cab = B.box("cab", (-6.36, 16.65, -2.41), (3.73, 20.69, 4.03), chamfer=0.04)
B.cut(cab, B.box("cab_field", (-5.96, 20.61, -2.01), (3.33, 20.9, 3.63)))
B.box("ledge", (-5.36, 16.45, -1.75), (2.73, 16.65, 3.31))

# ---- windows
CARD = [(0, -6.46), (2, 6.17), (0, -8.585)]
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    x, y, z = o["center"]
    if o["w"] > 6 or y > 20.6 or (y > 7.0 and any(abs(o["center"][a] - v) < 0.08 for a, v in CARD)):
        continue  # the antenna cards, the dish
    if x > -1 and y > 5:
        continue  # the gable's two-window pair: one rectangle over both panes, a recess loses the mullions
    if y > 16.6:
        tgt = cab
    elif -5.25 < x < 2.65 and -1.65 < z < 3.25 and y > 7.6:
        tgt = tower
    elif x < -5.2:
        tgt = west
    elif 4.4 < z < 9.25:
        tgt = band
    else:
        tgt = annex
    door = o["h"] > 0.78 and y < 2 and abs(o["normal"][0]) > 0.9 and x > -1
    B.recess(tgt, o, 0.25 if door else 0.2)
    if door:
        B.sill(f"hood{k}", o, proud=0.18, thick=0.08, overhang=0.1, top=True)
    elif o["h"] > 0.9 and abs(o["normal"][1]) < 0.1 and y < 16:
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

from cad_building import Original  # noqa: E402

O = Original("d_sensorcontrol")
n_part = 0
for ax, val, sax in ((0, -6.46, 2), (2, 6.17, 0), (0, -8.585, 2)):
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
