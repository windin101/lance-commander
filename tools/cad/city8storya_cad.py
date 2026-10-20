#!/usr/bin/env python3
"""CAD rebuild of the eight-storey city tower (appearance city8storya), in the original's frame.

    D=~/craft/solid/mc2/buildings/city8storya
    python3 -I tools/art/cad_building.py openings city8storya > $D/openings.json
    python3 -I tools/cad/city8storya_cad.py > $D/city8storya.json
    solidcraft-cli run $D/city8storya.json --out $D/city8storya.obj
    python3 -I tools/art/cad_building.py bake city8storya $D/city8storya.obj

The original is one plain box (x -7.442..10.315, z -7.536..10.221, to 28.369 m, 18 triangles). Each wall is two
storeys of texture: the upper half (14.18..28.37 m) repeats the top-left 0.5 x 0.5 square of the 512 px atlas on
all four walls, the lower half the bottom-left square, except the +x wall, whose lower half is the bottom-right
square with the entrance. The art is a precast-panel facade: light corner pilasters, then panels of several
sizes divided by dark seams, each carrying double-slit windows. All of it is read from the (upscaled) texture
here, so the script stays reproducible: windows are the dark or lit slit blobs of each square merged in pairs,
the panels are the regions between the dark seams split into rectangles (largest first).
Relief: every panel is a 12 cm plate on the wall (the seams become real grooves), the pilasters 20 cm plates,
every window a recess through its plate with a transom bar at the painted light bar and a sill under it, the
entrance a 25 cm recess with a hood and a step, a cornice band at the dark roof-line band, a plinth, a parapet
on the roof's light rim; roof plant raised: a round 28-sided vent drum, two housings, and the painted pipes as
true round pipes (20 sides).
"""
import math
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, box_edges  # noqa: E402
from city_facade import Original, roof_xz, ngon  # noqa: E402

O = Original("city8storya")
B = Builder()
UP = np.array([0.0, 1.0, 0.0])
IM = O.images[0]
RES = IM.shape[0]
LUM = IM[..., :3] @ np.array([0.299, 0.587, 0.114])
(X0, _, Z0), (X1, H, Z1) = O.lo, O.hi
MID = H / 2

# texture squares: (square, panel field between the pilasters, pilaster x ranges), in 512 px
SQ = {"TL": ((2, 0, 256, 253), (39, 8, 219, 253), ((2, 37), (220, 256))),
      "BL": ((2, 253, 256, 512), (39, 253, 219, 496), ((2, 37), (220, 256))),
      "BR": ((259, 258, 511, 510), (294, 258, 475, 496), ((259, 292), (476, 511)))}
DOOR = (362, 466, 410, 496)  # the entrance in BR


def rects(mask, minside=6, minarea=150):
    m = mask.copy()
    out = []
    while True:
        h = np.zeros(m.shape[1], int)
        best = (0, None)
        for y in range(m.shape[0]):
            h = np.where(m[y], h + 1, 0)
            st = []
            for x in range(m.shape[1] + 1):
                cur = h[x] if x < m.shape[1] else 0
                s = x
                while st and st[-1][1] >= cur:
                    s, hh = st.pop()
                    if hh * (x - s) > best[0] and hh >= minside and x - s >= minside:
                        best = (hh * (x - s), (s, y - hh + 1, x, y + 1))
                st.append((s, cur))
        if best[1] is None or best[0] < minarea:
            return out
        a, b, c, d = best[1]
        out.append(best[1])
        m[b:d, a:c] = False


def facade(key):
    (_, _, _, _), (fx0, fy0, fx1, fy1), _ = SQ[key]
    L = LUM[fy0:fy1, fx0:fx1]
    lab, _ = ndimage.label(L < 0.2)
    seam = np.zeros(L.shape, bool)
    for i, sl in enumerate(ndimage.find_objects(lab)):
        if max(sl[0].stop - sl[0].start, sl[1].stop - sl[1].start) > 26:
            seam[lab == i + 1] = True
    blobs = []
    for msk in (L < 0.16, L > 0.75):
        lb, _ = ndimage.label(msk)
        for sl in ndimage.find_objects(lb):
            h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
            if 6 <= w <= 22 and 2 <= h <= 12:
                blobs.append((sl[1].start, sl[0].start, sl[1].stop, sl[0].stop))
    wins = []
    for b in sorted(blobs, key=lambda b: b[1]):
        for m in wins:
            if min(m[2], b[2]) - max(m[0], b[0]) > 3 and b[1] - m[3] < 7 and b[1] >= m[1]:
                m[:] = [min(m[0], b[0]), m[1], max(m[2], b[2]), max(m[3], b[3])]
                break
        else:
            wins.append(list(b))
    wins = [[a + fx0, b + fy0, c + fx0, d + fy0] for a, b, c, d in wins if d - b >= 12]
    field = ndimage.binary_opening(~ndimage.binary_dilation(seam, iterations=1), np.ones((5, 5)))
    panels = [(a + fx0, b + fy0, c + fx0, d + fy0) for a, b, c, d in rects(field)]
    if key == "BR":
        wins = [w for w in wins if not (w[0] >= DOOR[0] - 2 and w[2] <= DOOR[2] + 2 and w[1] >= DOOR[1] - 2)]
        panels = [p for p in panels if not (p[0] >= DOOR[0] - 2 and p[2] <= DOOR[2] + 2 and p[1] >= DOOR[1] - 2)]
    return wins, panels


def wall_tri(nk, key):
    sq = SQ[key][0]
    for i, n in enumerate(O.normal):
        if np.allclose(n, nk, atol=0.05):
            c = O.uvs[i].mean(0) * RES
            if sq[0] <= c[0] <= sq[2] and sq[1] <= c[1] <= sq[3]:
                return i
    raise KeyError((nk, key))


def px_open(i, box, nk):
    uv = np.c_[O.uvs[i], np.ones(3)]
    A = np.linalg.solve(uv, O.tris[i]).T
    n = np.array(nk, float)
    t = np.cross(UP, n)
    x0, y0, x1, y1 = (c / RES for c in box)
    corners = np.array([A @ [u, v, 1] for u in (x0, x1) for v in (y0, y1)])
    ctr = corners.mean(0)
    ctr = ctr - n * (np.dot(ctr, n) - np.dot(O.tris[i][0], n))
    return {"center": ctr.tolist(), "normal": n.tolist(), "t": t.tolist(), "b": UP.tolist(),
            "w": float(np.ptp(corners @ t)), "h": float(np.ptp(corners[:, 1])), "lo": corners.min(0), "hi": corners.max(0)}


def slab(name, o, thick):
    """A plate on the wall over opening-dict o, thick metres proud."""
    n = np.array(o["normal"])
    c = np.array(o["center"]) + n * thick / 2
    return B.obox(name, c, np.array(o["t"]), UP, n, (o["w"], o["h"], thick))


main = B.box("main", (X0, 0.0, Z0), (X1, H, Z1), chamfer=0.05, chamfer_edges=box_edges((X0, 0.0, Z0), (X1, H, Z1), "vertical"))
PT, PIL = 0.12, 0.2
FAC = {k: facade(k) for k in SQ}
nw = npl = 0
for nk in ((0, 0, 1), (0, 0, -1), (1, 0, 0), (-1, 0, 0)):
    for key in ("TL", "BR" if nk == (1, 0, 0) else "BL"):
        i = wall_tri(nk, key)
        sq, field, pil = SQ[key]
        wins, panels = FAC[key]
        for a, b in pil:  # pilasters run the whole half (the cornice and plinth bands cap them)
            o = px_open(i, (a, sq[1], b, sq[3] if key == "TL" else field[3]), nk)
            slab(f"pilaster{npl}", o, PIL)
            npl += 1
        plates = []
        for p in panels:
            o = px_open(i, p, nk)
            plates.append((p, slab(f"panel{npl}", o, PT)))
            npl += 1
        for w in wins:
            o = px_open(i, w, nk)
            hosts = [nm for p, nm in plates if min(p[2], w[2]) > max(p[0], w[0]) and min(p[3], w[3]) > max(p[1], w[1])]
            for nm in hosts:
                B.recess(nm, o, PT + 0.03, surface_shift=-PT)
            if not hosts:
                B.recess(main, o, 0.12)
            # transom at the painted light bar (brightest row in the middle half of the slit pair)
            rows = LUM[w[1]:w[3], w[0] + 2:w[2] - 2].mean(1)
            q = len(rows) // 4
            r = w[1] + q + int(np.argmax(rows[q:len(rows) - q]))
            ob = px_open(i, (w[0], r - 1, w[2], r + 2), nk)
            n = np.array(nk, float)
            B.obox(f"transom{nw}", np.array(ob["center"]) + n * 0.03, np.array(ob["t"]), UP, n,
                   (ob["w"], max(ob["h"], 0.12), 0.06 + 0.02))
            B.sill(f"sill{nw}", o, proud=0.1, thick=0.07, overhang=0.06, surface_shift=-PT)
            nw += 1
        if key == "BR":
            d = px_open(i, DOOR, nk)
            B.recess(main, d, 0.25)
            B.sill("doorhood", d, proud=0.45, thick=0.12, overhang=0.25, top=True, surface_shift=-PT)
            n, t = np.array(d["normal"]), np.array(d["t"])
            c = np.array(d["center"])
            a = c + t * (d["w"] / 2 + 0.4)
            b = c - t * (d["w"] / 2 + 0.4) + n * 0.6
            lo, hi = np.minimum(a, b), np.maximum(a, b)
            B.box("doorstep@8f8b84", (lo[0], 0.0, lo[2]), (hi[0], 0.15, hi[2]))

# cornice at the dark roof-line band, plinth at the dark foot band
cy = float(H - 8 / 253 * MID)
py = float((512 - 496) / 259 * MID)
for nm, y0, y1, p in (("cornice", cy, H, 0.3), ("plinth", 0.0, py, 0.26)):
    B.box(f"{nm}_mz@avg", (X0 - p, y0, Z0 - p), (X1 + p, y1, Z0 + 0.01))
    B.box(f"{nm}_pz@avg", (X0 - p, y0, Z1 - 0.01), (X1 + p, y1, Z1 + p))
    B.box(f"{nm}_px@avg", (X1 - 0.01, y0, Z0 + 0.01), (X1 + p, y1, Z1 - 0.01))
    B.box(f"{nm}_mx@avg", (X0 - p, y0, Z0 + 0.01), (X0 + 0.01, y1, Z1 - 0.01))

# roof: parapet on the light rim, plant
rx0, rz0, rx1, rz1 = roof_xz(O, (262, 8, 502, 242))
T, PH = 0.28, H + 0.6
for k, (lo, hi) in enumerate((((rx0, H, rz0), (rx1, PH, rz0 + T)), ((rx0, H, rz1 - T), (rx1, PH, rz1)),
                              ((rx0, H, rz0 + T), (rx0 + T, PH, rz1 - T)), ((rx1 - T, H, rz0 + T), (rx1, PH, rz1 - T)))):
    B.box(f"parapet{k}", lo, hi)
cx, cz, _, _ = roof_xz(O, (325, 125, 325, 125))
r = 25 / 254 * (X1 - X0)
B.prism_y("ventdrum", ngon(r, 28, cx, cz), H, H + 0.55)
B.prism_y("ventcap", ngon(r * 0.8, 28, cx, cz), H + 0.55, H + 0.7)
for k, box in enumerate(((404, 38, 464, 98), (404, 146, 464, 206))):
    x0, z0, x1, z1 = roof_xz(O, box)
    B.box(f"housing{k}@avg", (x0 + 0.1, H, z0 + 0.1), (x1 - 0.1, H + 1.0, z1 - 0.1))
    B.box(f"housingcap{k}", (x0 + 0.05, H + 1.0, z0 + 0.05), (x1 - 0.05, H + 1.1, z1 - 0.05), chamfer=0.04)
PR = 0.14
for k, (a, b) in enumerate((((266, 68), (404, 68)), ((266, 177), (404, 177)), ((432, 206), (432, 242)))):
    xa, za, _, _ = roof_xz(O, (*a, *a))
    xb, zb, _, _ = roof_xz(O, (*b, *b))
    ring = [(PR * math.cos(2 * math.pi * (j + 0.5) / 20), PR * math.sin(2 * math.pi * (j + 0.5) / 20)) for j in range(20)]
    yc = H + PR + 0.05
    if abs(xb - xa) > abs(zb - za):
        za = zb = (za + zb) / 2
        B.prism_x(f"pipe{k}", [(za + u, yc + v) for u, v in ring], min(xa, xb), max(xa, xb))
    else:
        xa = xb = (xa + xb) / 2
        B.prism_z(f"pipe{k}", [(xa + u, yc + v) for u, v in ring], min(za, zb), max(za, zb))
print(B.dump())
