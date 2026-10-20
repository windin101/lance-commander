"""Shared builder for the three crash shanties (crashshanty1/2/3): huts knocked together from wreck plating,
all three mapping one 128 px texture (game/assets/objects/crashshanty*_0.png).

The originals are 10-14 triangles: planar wall quads and a roof sheet whose ragged edges are alpha cut-outs (the
grey plate stack in the texture's right half). Everything here is derived from the original's own faces and
their UV mapping, so the three rebuilds share one code path:

  * walls: each vertical (or leaning) wall quad becomes a 15 cm slab built inward from the original surface;
  * windows and doors (the five opaque black squares painted in the texture) become 10 cm recesses wherever a
    wall maps them, with a plank frame round each and a sill under the windows;
  * the tan corrugated patches painted in the texture become 2.5 cm plates proud of the wall (or roof);
  * plating faces (the roof, shanty2's leaning back sheet) become five overlapping 5 cm plates, one per painted
    plate row (the dark seams in the texture at v .343/.432/.537/.637), alternate rows raised 3 cm, each plate's
    ends following the alpha outline of its row so the ragged edge survives as real geometry;
  * square corner posts where two walls meet.

Positions come from the UV->world affine of each original face, so the relief lands on the painted feature.
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "art"))
from building_cad import Builder  # noqa: E402
from cad_building import Original  # noqa: E402
import aircraft_cad as A  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TEX = ROOT / "game" / "assets" / "objects" / "crashshanty1_hdtex_0.png"

# painted black windows/doors (u0, v0, u1, v1), found by thresholding the texture (max channel < 25, opened 9 px)
OPENINGS = [(0.115, 0.328, 0.211, 0.420), (0.256, 0.328, 0.352, 0.422), (0.191, 0.811, 0.287, 1.000),
            (0.604, 0.834, 0.703, 0.938), (0.771, 0.836, 0.865, 0.936)]
# plate rows of the roof plating (texture v), split at the dark seams
ROWS = [0.262, 0.343, 0.432, 0.537, 0.637, 0.738]
PLATING_U0 = 0.5          # the plating occupies u > 0.5, v < 0.75


def clip(poly, quad):
    """Sutherland-Hodgman: polygon (UV) clipped to a convex polygon (UV, either winding)."""
    q = np.asarray(quad, float)
    area = 0.5 * np.sum(q[:, 0] * np.roll(q[:, 1], -1) - np.roll(q[:, 0], -1) * q[:, 1])
    if area < 0:
        q = q[::-1]
    out = [np.asarray(p, float) for p in poly]
    for i in range(len(q)):
        a, b = q[i], q[(i + 1) % len(q)]
        e = b - a
        side = lambda p: e[0] * (p[1] - a[1]) - e[1] * (p[0] - a[0])  # noqa: E731
        inp, out = out, []
        for j in range(len(inp)):
            p, r = inp[j], inp[(j + 1) % len(inp)]
            sp, sr = side(p), side(r)
            if sp >= 0:
                out.append(p)
            if (sp >= 0) != (sr >= 0):
                out.append(p + (r - p) * (sp / (sp - sr)))
        if not out:
            return []
    return out


def faces(app):
    """Original planar faces, double-sided pairs merged: dicts with normal (outward), world loop, UV loop, affine."""
    o = Original(app)
    ctr = o.tris.reshape(-1, 3).mean(0)
    groups = []
    for k in range(len(o.tris)):
        n = o.normal[k]
        d = n @ o.tris[k].mean(0)
        for g in groups:
            if abs(abs(g["n"] @ n) - 1) < 1e-3 and abs(g["n"] @ o.tris[k].mean(0) - g["d"]) < 0.02:
                g["k"].append(k)
                break
        else:
            groups.append({"n": n, "d": d, "k": [k]})
    out = []
    for g in groups:
        P = o.tris[g["k"]].reshape(-1, 3)
        U = o.uvs[g["k"]].reshape(-1, 2)
        P, idx = np.unique(P.round(4), axis=0, return_index=True)
        U = U[idx]
        n = g["n"] / np.linalg.norm(g["n"])
        if n @ (P.mean(0) - ctr) < 0:
            n = -n
        # affine world = M @ [u, v, 1]
        M, *_ = np.linalg.lstsq(np.c_[U, np.ones(len(U))], P, rcond=None)
        # order the loop round the centroid in the plane
        t = P[1] - P[0]
        t /= np.linalg.norm(t)
        b = np.cross(n, t)
        c = P.mean(0)
        order = np.argsort(np.arctan2((P - c) @ b, (P - c) @ t))
        out.append({"n": n, "loop": P[order], "uv": U[order], "M": M})
    return out


def to_world(f, uv):
    return np.c_[np.asarray(uv, float), np.ones(len(uv))] @ f["M"]


def is_plating(f):
    c = f["uv"].mean(0)
    return c[0] > PLATING_U0 and c[1] < 0.75


def rect_dict(f, r, shift=0.0):
    """A UV rectangle on face f -> opening dict (center, normal, t, b, w, h) for Builder.recess/sill/frame."""
    u0, v0, u1, v1 = r
    p = to_world(f, [(u0, v0), (u1, v0), (u0, v1), ((u0 + u1) / 2, (v0 + v1) / 2)])
    tu, tv = p[1] - p[0], p[2] - p[0]
    n = f["n"]
    # wall 'up' is whichever of the two UV axes is more vertical
    if abs(tv[1]) < abs(tu[1]):
        tu, tv = tv, tu
    if tv[1] < 0:
        tv = -tv
    w, h = np.linalg.norm(tu), np.linalg.norm(tv)
    b = tv / h
    t = np.cross(b, n)
    return {"center": (p[3] + n * shift).tolist(), "normal": n.tolist(), "t": t.tolist(), "b": b.tolist(), "w": float(w), "h": float(h)}


def tan_panels():
    """Polygons (UV) of the tan corrugated patches painted on the texture."""
    a = np.asarray(Image.open(TEX)).astype(int)
    h, w = a.shape[:2]
    tan = (a[..., 0] > a[..., 2] + 18) & (a[..., 3] > 128)
    tan = ndimage.binary_closing(ndimage.binary_opening(tan, np.ones((5, 5))), np.ones((7, 7)))
    lab, _ = ndimage.label(tan)
    out = []
    for k, s in enumerate(ndimage.find_objects(lab)):
        m = lab == k + 1
        if m.sum() < 1500 or s[0].start < 0.26 * h:   # the wood fence strip along the top is not used here
            continue
        cs, _ = cv2.findContours(ndimage.binary_erosion(m, np.ones((5, 5))).astype(np.uint8), cv2.RETR_EXTERNAL,
                                 cv2.CHAIN_APPROX_SIMPLE)
        c = max(cs, key=cv2.contourArea)
        ap = cv2.approxPolyDP(c, 4, True)[:, 0, :]
        out.append([((x + 0.5) / w, (y + 0.5) / h) for x, y in ap])
    return out


def row_outline(v0, v1, n_sub=4, inset=0.004):
    """The plate row between v0 and v1 as a polygon (UV) whose ends follow the alpha edge."""
    a = np.asarray(Image.open(TEX))[..., 3] > 128
    h, w = a.shape
    left, right = [], []
    for k in range(n_sub):
        va, vb = v0 + (v1 - v0) * k / n_sub, v0 + (v1 - v0) * (k + 1) / n_sub
        band = a[int(va * h):max(int(vb * h), int(va * h) + 1), int(PLATING_U0 * w):]
        cols = np.where(band.mean(0) > 0.7)[0]
        u_l = PLATING_U0 + (cols.min() + 1) / w + inset
        u_r = PLATING_U0 + (cols.max()) / w - inset
        vm = (va + vb) / 2
        left.append((u_l, vm))
        right.append((u_r, vm))
    left = [(left[0][0], v0)] + left + [(left[-1][0], v1)]
    right = [(right[0][0], v0)] + right + [(right[-1][0], v1)]
    return left + right[::-1]


def build(app, wall=0.15, recess=0.10, plate=0.05, step=0.03, overlap=0.04):
    B = Builder()
    fs = faces(app)
    walls = [f for f in fs if not is_plating(f) and abs(f["n"][1]) < 0.3]
    plating = [f for f in fs if is_plating(f)]
    panels = tan_panels()

    for i, f in enumerate(walls):
        name = f"wall{i}"
        A.slab(B, name, f["n"], [p - f["n"] * wall / 2 for p in f["loop"]], wall)
        for j, r in enumerate(OPENINGS):
            quad = [(r[0], r[1]), (r[2], r[1]), (r[2], r[3]), (r[0], r[3])]
            cl = clip(quad, f["uv"])
            if not cl or abs(cv2.contourArea(np.float32(cl))) < 0.6 * (r[2] - r[0]) * (r[3] - r[1]):
                continue
            o = rect_dict(f, r)
            door = np.asarray(o["center"])[1] - o["h"] / 2 < 0.15
            B.recess(name, o, recess)
            B.frame(f"frame{i}_{j}", o, width=0.07, proud=0.04)
            if not door:
                B.sill(f"sill{i}_{j}", o, proud=0.10, thick=0.06, overhang=0.08)
        for j, pg in enumerate(panels):
            cl = clip(pg, f["uv"])
            if len(cl) < 3 or abs(cv2.contourArea(np.float32(cl))) < 0.002:
                continue
            A.slab(B, f"patch{i}_{j}", f["n"], [p + f["n"] * 0.0125 for p in to_world(f, cl)], 0.025)

    for i, f in enumerate(plating):
        for r in range(len(ROWS) - 1):
            v0 = ROWS[r] - (overlap / 2 if r % 2 else 0) / 6
            v1 = ROWS[r + 1] + (overlap / 2 if r % 2 else 0) / 6
            cl = clip(row_outline(v0, v1), f["uv"])
            if len(cl) < 3 or abs(cv2.contourArea(np.float32(cl))) < 0.002:
                continue
            lift = plate / 2 + (step if r % 2 else 0.0)
            A.slab(B, f"plate{i}_{r}", f["n"], [p + f["n"] * lift for p in to_world(f, cl)], plate)
        for j, pg in enumerate(panels):
            cl = clip(pg, f["uv"])
            if len(cl) < 3 or abs(cv2.contourArea(np.float32(cl))) < 0.002:
                continue
            A.slab(B, f"board{i}_{j}", f["n"], [p + f["n"] * (plate + step + 0.02) for p in to_world(f, cl)], 0.04)

    # corner posts where two walls share a ground corner
    corners = {}
    for f in walls:
        for p in f["loop"]:
            if p[1] < 0.05:
                corners.setdefault((round(p[0], 1), round(p[2], 1)), []).append(f)
    for k, (key, fl) in enumerate(corners.items()):
        if len(fl) < 2:
            continue
        x, z = key
        top = min(max(q[1] for q in f["loop"] if abs(q[0] - x) < 0.1 and abs(q[2] - z) < 0.1) for f in fl)
        out = sum(f["n"] for f in fl)
        out = out / np.linalg.norm(out) * 0.03
        B.box(f"post{k}@avg", (x + out[0] - 0.08, 0.0, z + out[2] - 0.08), (x + out[0] + 0.08, top - 0.02, z + out[2] + 0.08))
    return B
