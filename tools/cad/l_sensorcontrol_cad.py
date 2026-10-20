#!/usr/bin/env python3
"""CAD rebuild of the woodland sensor control building (appearance l_sensorcontrol), in the original's frame.

    D=~/craft/solid/mc2/buildings/l_sensorcontrol
    python3 -I tools/art/cad_building.py openings l_sensorcontrol > $D/openings.json
    python3 -I tools/cad/l_sensorcontrol_cad.py $D > $D/l_sensorcontrol.json
    solidcraft-cli run $D/l_sensorcontrol.json --out $D/l_sensorcontrol.obj
    python3 -I tools/art/cad_building.py bake l_sensorcontrol $D/l_sensorcontrol.obj --keep L_Dish L_Sdish

Measured from game/assets/objects/l_sensorcontrol.glb (vertices listed by height): the s_sensorcontrol plan with
a curved roof: a low block (x -9.80..0.20, z -2.60..10.40) flat at 8.80 m east of x -4.20 and a two-facet arch
down to the west eave (-11.00, 4.00), whose vertices lie on a circle of radius 7.22 m about (-4.20, 1.58) with a
level tangent at its crown, rebuilt as a true curve (24 segments, issue I77); the west wall stands 1.2 m back
below 4 m between three legs. The tower (x -4.20..2.60, z -1.60..3.20, a chamfered nose to x 3.60) stands
straight to 8.78 m, its front battered back to x 0.80 at 16.65 m; a glazed cab flares out to 19.57 m and a
bevelled roof closes it at 20.57 m carrying the two dishes (L_Dish, L_Sdish, kept verbatim). The antenna cluster
is two alpha cards (z 7.22, z 9.70): their opaque texels become real parts on the card's plane as in
s_sensorcontrol_cad.py (true round poles, 20 sides). Relief: every cut-out window or door is a 20 cm recess
(sills under the tall wall ones), raised 8 cm ribs over the arch at the legs' painted bands, the cab roof field
an 8 cm recess, a ledge where the tower's front starts to batter and one at the cab's foot.
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

# ---- low block: flat east, true arch west, recessed west wall between legs
CX, CY, RAD = -4.20, 1.583, 7.217
A1 = math.atan2(4.00 - CY, -11.00 - CX)


def roof(off, k=24):
    pts = []
    for i in range(k + 1):
        a = math.pi / 2 + (A1 - math.pi / 2) * i / k
        pts.append((CX + (RAD + off) * math.cos(a), CY + (RAD + off) * math.sin(a)))
    return pts


arc = roof(0.0)
arc[-1] = (-11.00, 4.00)
low = B.prism_z("low", [(-9.80, 0.0), (0.20, 0.0), (0.20, 8.80)] + arc + [(-9.80, 4.00)], -2.60, 10.40)
for k, (z0, z1) in enumerate([(-2.60, -1.60), (3.20, 4.40), (9.20, 10.40)]):
    B.box(f"leg{k}", (-11.00, 0.0, z0), (-9.80, 4.00, z1))
rib = [(0.20, 8.88), (-4.20, 8.88)] + roof(0.08)[1:] + roof(-0.02)[::-1] + [(0.20, 8.78)]
for k, (z0, z1) in enumerate([(-2.64, -1.60), (3.20, 4.40), (9.20, 10.44)]):
    B.prism_z(f"rib{k}", rib, z0, z1)

# ---- tower, cab and roof (hexagonal plans: the chamfered nose is the design)
def hexa(x0, x1, x2, z0, z1, za, zb):
    return [(x0, z0), (x1, z0), (x2, za), (x2, zb), (x1, z1), (x0, z1)]


p0 = hexa(-4.20, 2.60, 3.60, -1.60, 3.20, -0.60, 2.20)
p1 = hexa(-4.20, -0.20, 0.80, -1.60, 3.20, -0.60, 2.20)
p2 = hexa(-5.08, 0.79, 2.15, -2.46, 4.06, -1.10, 2.70)
p3 = hexa(-4.08, 0.38, 1.15, -1.46, 3.06, -0.69, 2.29)
t_lo = B.prism_y("tower_lo", p0, 0.0, 8.78)
t_up = B.loft_y("tower_up", p0, 8.78, p1, 16.65)
cab = B.loft_y("cab", p1, 16.65, p2, 19.57)
rf = B.loft_y("roof", p2, 19.57, p3, 20.57)
B.cut(rf, B.prism_y("roof_field", hexa(-3.68, 0.20, 0.85, -1.06, 2.66, -0.50, 2.10), 20.49, 20.7))
B.prism_y("ledge0", hexa(-4.32, 2.65, 3.72, -1.72, 3.32, -0.65, 2.25), 8.70, 8.90)
B.prism_y("ledge1", hexa(-4.32, -0.15, 0.92, -1.72, 3.32, -0.65, 2.25), 16.50, 16.70)

# ---- windows
CARD = [(2, 7.22), (2, 9.70)]
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    c = o["center"]
    if o["w"] > 3.5 or c[1] > 20.6 or any(abs(c[a] - v) < 0.08 for a, v in CARD):
        continue  # the antenna cards, the dishes
    x, y, z = c
    if y > 16.6:
        tgt = cab
    elif -4.25 < x < 3.7 and -1.65 < z < 3.25 and y > 8.8:
        tgt = t_up
    elif -4.25 < x < 3.7 and -1.65 < z < 3.25:
        tgt = t_lo
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

O = Original("l_sensorcontrol")
n_part = 0
for ax, val, sax in ((2, 7.22, 0), (2, 9.70, 0)):
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
            B.prism_y(f"ant{n_part}@62666c", [(cx + w / 2 * math.cos(2 * math.pi * i / 20), cz + w / 2 * math.sin(2 * math.pi * i / 20))
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
