#!/usr/bin/env python3
"""CAD rebuild of the hub (appearance hub), in the original's frame.

    D=~/craft/solid/mc2/buildings/hub
    python3 -I tools/art/cad_building.py openings hub > $D/openings.json
    python3 -I tools/cad/hub_cad.py > $D/hub.json
    solidcraft-cli run $D/hub.json --out $D/hub.obj
    python3 -I tools/art/cad_building.py bake hub $D/hub.obj --max-res 4096

The original (98 triangles): a 24 m square base (x -12..12.01, z -12..12) to 8 m, a hipped skirt up to an
upper block (x -7.8..8, z -8..8) at 11 m, the block to 14 m, a tapering tower (7.7 x 8 m to 5.6 m square) to
24 m, and on each side a trapezoid entrance facade 0.7-0.8 m proud (17.2 m wide at the foot, 13.6 m at 7 m).
Every surface keeps its own texture rectangle (walls mirrored about the centre), mapped here through each
triangle's own UV -> position affine.
Relief: the upper block's ribbon windows (the cut-outs, openings.json) 15 cm recesses with sills and a parapet;
the base's painted light panels 6 cm plates and an eave ledge under the skirt; on each facade the chevron panel
a 20 cm recess with hood and sill, the two tapered pylons 20 cm proud, the slim pillars 12 cm proud, a plinth;
the tower's louvre a recess with three slats, its three small vents as set-in boxes, a base band, the dark roof hatch a
raised slab; the two small roof boxes in each quadrant of the 14 m roof raised.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, box_edges  # noqa: E402
from city_facade import Original, UP  # noqa: E402

O = Original("hub")
B = Builder()
RES = 512
OPEN = json.load(open(Path.home() / "craft/solid/mc2/buildings/hub/openings.json"))["openings"]


def affine(i):
    return np.linalg.solve(np.c_[O.uvs[i], np.ones(3)], O.tris[i]).T


def tex_open(i, box):
    """Texture pixel box on triangle i's plane -> opening dict (center, normal, t, b, w, h)."""
    A = affine(i)
    n = np.array(O.normal[i], float)
    n /= np.linalg.norm(n)
    t = np.cross(UP, n) if abs(n[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
    t /= np.linalg.norm(t)
    b = np.cross(n, t)
    x0, y0, x1, y1 = (c / RES for c in box)
    P = np.array([A @ [u, v, 1] for u in (x0, x1) for v in (y0, y1)])
    c = P.mean(0)
    c = c - n * np.dot(c - O.tris[i][0], n)
    return {"center": c.tolist(), "normal": n.tolist(), "t": t.tolist(), "b": b.tolist(),
            "w": float(np.ptp(P @ t)), "h": float(np.ptp(P @ b))}


def faces(pred):
    """Triangles matching pred(normal, centroid), one per distinct UV affine (a quad's two triangles share one)."""
    out, seen = [], []
    for i in range(len(O.tris)):
        if not pred(O.normal[i], O.tris[i].mean(0)):
            continue
        A = affine(i)
        if any(np.allclose(A, S, atol=1e-3) for S in seen):
            continue
        seen.append(A)
        out.append(i)
    return out


def on_tri(i, o):
    """Is the opening's centre inside triangle i's quad region? (the UV box is mirrored onto every half)"""
    return True


SIDES = [(0, 0, 1), (1, 0, 0), (0, 0, -1), (-1, 0, 0)]


def side(nk):
    return lambda n, c: np.allclose(n, nk, atol=0.02)


# --- the masses ------------------------------------------------------------------------------------------------
BX0, BX1, BZ0, BZ1 = -12.0, 12.01, -12.0, 12.0
UX0, UX1, UZ0, UZ1 = -7.8, 8.0, -8.0, 8.0
B.box("base", (BX0, 0.0, BZ0), (BX1, 8.0, BZ1), chamfer=0.05, chamfer_edges=box_edges((BX0, 0.0, BZ0), (BX1, 8.0, BZ1), "vertical"))
B.loft_y("skirt", [(BX0, BZ0), (BX1, BZ0), (BX1, BZ1), (BX0, BZ1)], 8.0, [(UX0, UZ0), (UX1, UZ0), (UX1, UZ1), (UX0, UZ1)], 11.0)
up = B.box("upper", (UX0, 11.0, UZ0), (UX1, 14.0, UZ1))
B.loft_y("tower", [(-3.8, -4.0), (3.89, -4.0), (3.89, 4.0), (-3.8, 4.0)], 14.0, [(-2.8, -2.8), (2.8, -2.8), (2.8, 2.8), (-2.8, 2.8)], 24.0)

# upper block: ribbon windows (cut-outs), parapet
for k, o in enumerate(OPEN):
    if 11.0 < o["center"][1] < 14.0:
        B.recess(up, o, 0.15)
        B.sill(f"usill{k}", o, proud=0.1, thick=0.07, overhang=0.05)
T, PH = 0.22, 14.35
for k, (lo, hi) in enumerate((((UX0, 14.0, UZ0), (UX1, PH, UZ0 + T)), ((UX0, 14.0, UZ1 - T), (UX1, PH, UZ1)),
                              ((UX0, 14.0, UZ0 + T), (UX0 + T, PH, UZ1 - T)), ((UX1 - T, 14.0, UZ0 + T), (UX1, PH, UZ1 - T)))):
    B.box(f"parapet{k}", lo, hi)
# eave ledge under the skirt
p = 0.14
for nm, lo, hi in (("mz", (BX0 - p, 7.75, BZ0 - p), (BX1 + p, 8.0, BZ0 + 0.01)), ("pz", (BX0 - p, 7.75, BZ1 - 0.01), (BX1 + p, 8.0, BZ1 + p)),
                   ("px", (BX1 - 0.01, 7.75, BZ0 + 0.01), (BX1 + p, 8.0, BZ1 - 0.01)), ("mx", (BX0 - p, 7.75, BZ0 + 0.01), (BX0 + 0.01, 8.0, BZ1 - 0.01))):
    B.box(f"eave_{nm}@avg", lo, hi)


def plate(name, o, thick):
    n, t, b = (np.array(o[k]) for k in ("normal", "t", "b"))
    return B.obox(name, np.array(o["center"]) + n * thick / 2, t, b, n, (o["w"], o["h"], thick))


# base walls: the painted light panels as plates (both mirrored halves of every wall)
k = 0
for nk in SIDES:
    for i in faces(lambda n, c, nk=nk: np.allclose(n, nk, atol=0.02) and c[1] < 8.0 and abs(np.dot(c, nk)) < 12.05):
        for box in ((8, 305, 178, 343), (8, 368, 98, 408)):
            plate(f"bpanel{k}", tex_open(i, box), 0.06)
            k += 1

# facades
FAC = {(0, 0, 1): (12.0, 12.7), (1, 0, 0): (12.01, 12.79), (0, 0, -1): (-12.74, -12.0), (-1, 0, 0): (-12.74, -12.0)}
for nk, (a, b) in FAC.items():
    tag = {(0, 0, 1): "pz", (1, 0, 0): "px", (0, 0, -1): "mz", (-1, 0, 0): "mx"}[nk]
    if nk[2]:
        B.prism_z(f"facade_{tag}", [(-8.6, 0.0), (8.6, 0.0), (6.8, 7.0), (-6.8, 7.0)], a, b)
    else:
        B.prism_x(f"facade_{tag}", [(-8.6, 0.0), (8.6, 0.0), (6.8, 7.0), (-6.8, 7.0)], a, b)
    i = faces(lambda n, c, nk=nk: np.allclose(n, nk, atol=0.02) and abs(np.dot(c, nk)) > 12.3)[0]
    A = affine(i)
    n = np.array(nk, float)
    panel = tex_open(i, (97, 36, 247, 130))
    B.recess(f"facade_{tag}", panel, 0.2)
    B.sill(f"fhood_{tag}", panel, proud=0.18, thick=0.1, overhang=0.1, top=True)
    B.sill(f"fsill_{tag}", panel, proud=0.12, thick=0.08, overhang=0.06)
    for j, box in enumerate(((72, 36, 82, 128), (260, 36, 270, 128))):
        plate(f"fpillar_{tag}{j}", tex_open(i, box), 0.12)
    plate(f"fplinth_{tag}@avg", tex_open(i, (7, 130, 343, 141)), 0.15)
    # tapered pylons: outer edge slanted, inner edge plumb (texture polygons), 20 cm proud
    for j, poly in enumerate((((46, 12), (55, 12), (55, 131), (20, 131)), ((292, 12), (300, 12), (328, 131), (292, 131)))):
        P = [A @ [u / RES, v / RES, 1] for u, v in poly]
        if nk[2]:
            z0, z1 = (b, b + 0.2) if nk[2] > 0 else (a - 0.2, a)
            B.prism_z(f"pylon_{tag}{j}", [(q[0], q[1]) for q in P], z0, z1)
        else:
            x0, x1 = (b, b + 0.2) if nk[0] > 0 else (a - 0.2, a)
            B.prism_x(f"pylon_{tag}{j}", [(q[2], q[1]) for q in P], x0, x1)

# tower: louvre with slats, small vents, base band, roof hatch
for k, i in enumerate(faces(lambda n, c: 14.0 < c[1] < 24.0 and abs(n[1]) < 0.5)):
    lv = tex_open(i, (276, 239, 367, 279))
    B.recess("tower", lv, 0.2)
    n, t, b = (np.array(lv[q]) for q in ("normal", "t", "b"))
    for j in range(3):
        c = np.array(lv["center"]) + b * lv["h"] * (j - 1) / 3.4 - n * 0.1
        B.obox(f"slat{k}_{j}", c, t, b, n, (lv["w"] - 0.02, 0.07, 0.16))
    for j, box in enumerate(((277, 355, 294, 366), (309, 355, 334, 366), (348, 355, 367, 366))):
        o = tex_open(i, box)  # a small plate cut into its own recess: a vent as a dark box set in the face
        n, t, b = (np.array(o[q]) for q in ("normal", "t", "b"))
        B.obox(f"vent{k}_{j}", np.array(o["center"]) + n * 0.02, t, b, n, (o["w"], o["h"], 0.08))
    plate(f"tband{k}@avg", tex_open(i, (251, 383, 396, 416)), 0.1)
hi = faces(lambda n, c: n[1] > 0.9 and c[1] > 23.0)[0]
plate("hatch", tex_open(hi, (404, 187, 495, 280)), 0.15)

# 14 m roof: two small boxes in each quadrant
for k, i in enumerate(faces(lambda n, c: n[1] > 0.9 and 13.9 < c[1] < 14.1)):
    for j, box in enumerate(((381, 84, 407, 106), (409, 112, 432, 134))):
        o = tex_open(i, box)
        c = np.array(o["center"])
        hw, hd = o["w"] / 2, o["h"] / 2
        B.box(f"rbox{k}_{j}@avg", (c[0] - hw, 14.0, c[2] - hd), (c[0] + hw, 14.5, c[2] + hd))
        B.box(f"rboxcap{k}_{j}", (c[0] - hw - 0.04, 14.5, c[2] - hd - 0.04), (c[0] + hw + 0.04, 14.58, c[2] + hd + 0.04))
print(B.dump())
