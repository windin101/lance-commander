#!/usr/bin/env python3
"""CAD-rebuilt map buildings that keep the original artwork: a SolidCraft model with real relief, its
texture baked from the original (4x upscaled) art by nearest-surface transfer.

    python3 -I tools/art/cad_building.py openings <app>               # cut-out windows -> 3D rectangles (JSON)
    python3 -I tools/art/cad_building.py decal <app> <mat> u0 v0 u1 v1 # a painted texture rectangle -> 3D rectangles
    python3 -I tools/art/cad_building.py bake <app> <model.obj> [--keep Coil] [--glass r,g,b] [--texel 0.015]

The original (game/assets/objects/<app>.glb) and its upscaled twin (<app>_hdtex.glb, tools/art/upscale_textures.py)
are the inputs; the SolidCraft model is built in the original's frame (tools/cad/<app>_cad.py: CAD X = glTF x,
CAD Y = -glTF z, CAD Z = glTF y, mm), so no fitting is needed: bake only checks the bounds.

bake: OBJ (mm, Z up, one `o` per body) -> glTF metres, Y up; drops faces that sit inside another body or face the
ground; box-maps every face onto its dominant axis plane, charts (connected faces with the same axis) shelf-packed
into one atlas (~1.5 cm a texel, 2048 px at most); every texel takes the colour of the nearest point on the
original surface (closest point on the original triangle, its UV, that triangle's material's upscaled texture).
Faces behind the original wall (recesses) are darkened by depth (a cheap AO). Original cut-outs (alpha) become
opaque glass where a CAD face is parallel to them (window panes at the back of a recess) and the surrounding
frame colour elsewhere (reveals). A body named <name>@rrggbb keeps that colour (a concrete step), shaded like the art
under it; <name>@avg takes one flat colour, the mean of the art under it (ribs across painted stripes). Writes game/assets/objects/<app>_cad.glb: one opaque material (WebP, EXT_texture_webp), plus any
--keep node copied verbatim from the original with its upscaled texture (e.g. the generator's glowing coil).
The output derives from the Shared Source art and stays under its non-commercial terms.
"""
import argparse
import io
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hd_rig as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OBJ_DIR = ROOT / "game" / "assets" / "objects"


# --- the original ------------------------------------------------------------

class Original:
    """Triangles (world, metres), UVs, per-triangle material and the materials' upscaled RGBA images."""

    def __init__(self, app):
        src = OBJ_DIR / f"{app}_hdtex.glb"
        if not src.exists():
            src = OBJ_DIR / f"{app}.glb"
        self.gltf, self.bin = R.load_glb(str(src))
        g = self.gltf
        self.images = []
        for img in g.get("images", []):
            v = g["bufferViews"][img["bufferView"]]
            o = v.get("byteOffset", 0)
            im = Image.open(io.BytesIO(bytes(self.bin[o:o + v["byteLength"]]))).convert("RGBA")
            self.images.append(np.asarray(im).astype(np.float32) / 255.0)
        self.mat_image = []
        for m in g.get("materials", []):
            t = m.get("pbrMetallicRoughness", {}).get("baseColorTexture", {}).get("index")
            tex = g["textures"][t] if t is not None else {}
            self.mat_image.append(tex.get("source", tex.get("extensions", {}).get("EXT_texture_webp", {}).get("source")))
        worlds = R.world_matrices(g)
        tris, uvs, mats, nodes = [], [], [], []
        for ni, node in enumerate(g["nodes"]):
            if "mesh" not in node or node.get("name", "").lower().startswith(R.OVERLAY_PREFIXES):
                continue
            for prim in g["meshes"][node["mesh"]]["primitives"]:
                if prim.get("material") is None or "TEXCOORD_0" not in prim["attributes"]:
                    continue
                pos = R.read_accessor(g, self.bin, prim["attributes"]["POSITION"]).astype(float)
                uv = R.read_accessor(g, self.bin, prim["attributes"]["TEXCOORD_0"]).astype(float)
                if "indices" in prim:
                    idx = R.read_accessor(g, self.bin, prim["indices"]).astype(int)
                    pos, uv = pos[idx], uv[idx]
                pw = (worlds[ni] @ np.c_[pos, np.ones(len(pos))].T).T[:, :3]
                t = pw.reshape(-1, 3, 3)
                keep = np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1) > 1e-6
                tris.append(t[keep])
                uvs.append(uv.reshape(-1, 3, 2)[keep])
                mats.append(np.full(keep.sum(), prim["material"]))
                nodes.append(np.full(keep.sum(), ni))
        self.tris = np.concatenate(tris)
        self.uvs = np.concatenate(uvs)
        self.mat = np.concatenate(mats)
        self.node = np.concatenate(nodes)
        n = np.cross(self.tris[:, 1] - self.tris[:, 0], self.tris[:, 2] - self.tris[:, 0])
        self.area = 0.5 * np.linalg.norm(n, axis=1)
        self.normal = n / (2 * self.area[:, None])
        self.lo, self.hi = self.tris.reshape(-1, 3).min(0), self.tris.reshape(-1, 3).max(0)

    def samples(self, density=600, seed=0):
        """Area samples (and the triangle each lies on), for the nearest-triangle search."""
        rng = np.random.default_rng(seed)
        which = np.repeat(np.arange(len(self.tris)), np.maximum(np.ceil(self.area * density).astype(int), 3))
        r = rng.random((len(which), 2))
        f = r.sum(1) > 1
        r[f] = 1 - r[f]
        t = self.tris[which]
        p = t[:, 0] + r[:, :1] * (t[:, 1] - t[:, 0]) + r[:, 1:] * (t[:, 2] - t[:, 0])
        return p, which

    def sample_image(self, img_index, uv, bilinear=True):
        im = self.images[img_index]
        h, w = im.shape[:2]
        x = (uv[:, 0] % 1.0) * w - 0.5
        y = (uv[:, 1] % 1.0) * h - 0.5
        if not bilinear:
            return im[np.clip(np.round(y).astype(int), 0, h - 1) % h, np.clip(np.round(x).astype(int), 0, w - 1) % w]
        x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
        fx, fy = (x - x0)[:, None], (y - y0)[:, None]
        x0, x1 = x0 % w, (x0 + 1) % w
        y0, y1 = y0 % h, (y0 + 1) % h
        return (im[y0, x0] * (1 - fx) * (1 - fy) + im[y0, x1] * fx * (1 - fy)
                + im[y1, x0] * (1 - fx) * fy + im[y1, x1] * fx * fy)


def filled_rgb(im, iters=64):
    """The image's RGB with cut-out pixels filled from their opaque neighbours (frame colour for reveals)."""
    rgb = im[..., :3].copy()
    ok = im[..., 3] >= 0.5
    if ok.all() or not ok.any():
        return im
    _, (iy, ix) = ndimage.distance_transform_edt(~ok, return_indices=True)
    rgb = rgb[iy, ix]
    return np.dstack([rgb, im[..., 3]])


# --- texture regions -> 3D ------------------------------------------------------

def raster_tri_uv(uv_px, mask_shape, max_px=1_000_000):
    """Pixel centres inside a triangle given in pixel units (may lie outside the image: wrapped by the caller).
    A triangle whose UVs tile the texture many times is sampled on a coarser stride, at most max_px points:
    a full grid over its bounding box ran to tens of GB and froze the workstation (2026-10-20)."""
    x0, y0 = np.floor(uv_px.min(0)).astype(int)
    x1, y1 = np.ceil(uv_px.max(0)).astype(int)
    step = max(1, int(np.ceil(np.sqrt((x1 - x0 + 1) * (y1 - y0 + 1) / max_px))))
    xs, ys = np.meshgrid(np.arange(x0, x1 + 1, step) + 0.5, np.arange(y0, y1 + 1, step) + 0.5)
    pts = np.c_[xs.ravel(), ys.ravel()]
    a, b, c = uv_px
    m = np.array([b - a, c - a]).T
    if abs(np.linalg.det(m)) < 1e-9:
        return np.zeros((0, 2)), np.zeros((0, 3))
    lam = np.linalg.solve(m, (pts - a).T).T
    inside = (lam[:, 0] >= 0) & (lam[:, 1] >= 0) & (lam.sum(1) <= 1)
    lam = lam[inside]
    return pts[inside], np.c_[1 - lam.sum(1), lam]


CELL = 0.02  # regions_3d point spacing (m): 2 cm keeps every window of the reference set; 5 cm lost small ones, 1 cm still ran past 12 GB


def regions_3d(orig, select, min_area=0.05, link=0.25):
    """select(mat, img_index, ix, iy) -> bool mask of texture pixels; returns the 3D rectangles they cover
    ("pixels" counts 2 cm cells, not texture pixels)."""
    pts, nrm, tri_of = [], [], []
    for ti in range(len(orig.tris)):
        img = orig.mat_image[orig.mat[ti]]
        if img is None:
            continue
        h, w = orig.images[img].shape[:2]
        px, bary = raster_tri_uv(orig.uvs[ti] * [w, h], (h, w))
        if not len(px):
            continue
        ix = np.floor(px[:, 0]).astype(int) % w
        iy = np.floor(px[:, 1]).astype(int) % h
        sel = select(orig.mat[ti], img, ix, iy)
        if not sel.any():
            continue
        # one point per CELL: query_pairs below grows with the square of the point density (s_quetragon ran past 50 GB)
        p3 = np.unique(np.round(bary[sel] @ orig.tris[ti] / CELL).astype(np.int64), axis=0) * CELL
        pts.append(p3)
        nrm.append(np.repeat(orig.normal[ti][None], len(p3), 0))
        tri_of.append(np.full(len(p3), ti))
    if not pts:
        return []
    pts, nrm = np.concatenate(pts), np.concatenate(nrm)
    # connected components in 3D (pixels a few cm apart), separating faces that reuse one texture region
    # link only pixels on (nearly) the same plane, so a window band wrapping a corner splits per wall
    # (facets of a curved roof, < 40 degrees apart, stay together)
    tree = cKDTree(pts)
    pairs = tree.query_pairs(link, output_type="ndarray")
    pairs = pairs[(nrm[pairs[:, 0]] * nrm[pairs[:, 1]]).sum(1) > 0.75]
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    g = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(len(pts), len(pts)))
    ncomp, lab = connected_components(g, directed=False)
    out = []
    for k in range(ncomp):
        p, nn = pts[lab == k], nrm[lab == k]
        n = nn.mean(0)
        n /= np.linalg.norm(n)
        up = np.array([0.0, 1.0, 0.0])
        t = np.cross(up, n)
        if np.linalg.norm(t) < 0.3:  # a roof region: tangent along x
            t = np.array([1.0, 0.0, 0.0]) - n * n[0]
        t /= np.linalg.norm(t)
        b = np.cross(n, t)
        lt, lb, ln = p @ t, p @ b, p @ n
        w, h = lt.max() - lt.min(), lb.max() - lb.min()
        if w * h < min_area or min(w, h) < 0.2:
            continue
        c = t * (lt.max() + lt.min()) / 2 + b * (lb.max() + lb.min()) / 2 + n * ln.max()
        out.append({"center": np.round(c, 3).tolist(), "normal": np.round(n, 4).tolist(), "t": np.round(t, 4).tolist(),
                    "b": np.round(b, 4).tolist(), "w": round(float(w), 3), "h": round(float(h), 3), "pixels": int(len(p))})
    out.sort(key=lambda r: (-r["normal"][1], r["center"][2], r["center"][0], r["center"][1]))
    return out


def cmd_openings(a):
    orig = Original(a.app)
    rects = regions_3d(orig, lambda m, img, ix, iy: orig.images[img][iy, ix, 3] < 0.5)
    print(json.dumps({"app": a.app, "bounds": [orig.lo.round(3).tolist(), orig.hi.round(3).tolist()], "openings": rects}, indent=1))


def cmd_decal(a):
    orig = Original(a.app)
    u0, v0, u1, v1 = a.rect

    def sel(m, img, ix, iy):
        h, w = orig.images[img].shape[:2]
        u, v = (ix + 0.5) / w, (iy + 0.5) / h
        return (m == a.mat) & (u >= u0) & (u <= u1) & (v >= v0) & (v <= v1)
    print(json.dumps({"app": a.app, "decal": [a.mat, u0, v0, u1, v1], "rects": regions_3d(orig, sel)}, indent=1))


# --- the CAD model ---------------------------------------------------------------

def load_obj(path):
    verts, faces, body = [], [], []
    names, cur = [], -1
    for line in open(path):
        if line.startswith("v "):
            verts.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("o "):
            names.append(line[2:].strip())
            cur = len(names) - 1
        elif line.startswith("f "):
            idx = [int(t.split("/")[0]) - 1 for t in line.split()[1:]]
            for k in range(1, len(idx) - 1):
                faces.append([idx[0], idx[k], idx[k + 1]])
                body.append(cur)
    v = np.array(verts, float) / 1000.0
    v = np.c_[v[:, 0], v[:, 2], -v[:, 1]]  # SolidCraft mm Z-up -> glTF m Y-up
    return v, np.array(faces), np.array(body), names


def weld(v, faces, tol=1e-4):
    key = np.round(v / tol).astype(np.int64)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    return v[first], inv.reshape(-1)[faces]


def ray_parity_inside(points, tris, direction=(0.3141, 0.9, 0.1732)):
    """Points inside a closed triangle mesh (odd ray crossings)."""
    d = np.array(direction) / np.linalg.norm(direction)
    v0, e1, e2 = tris[:, 0], tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]
    pv = np.cross(d, e2)
    det = (e1 * pv).sum(1)
    ok = np.abs(det) > 1e-12
    v0, e1, e2, pv, det = v0[ok], e1[ok], e2[ok], pv[ok], det[ok]
    inv = 1.0 / det
    hits = np.zeros(len(points), dtype=int)
    for s in range(0, len(points), 2048):
        p = points[s:s + 2048]
        tv = p[:, None, :] - v0[None]
        u = (tv * pv[None]).sum(2) * inv
        qv = np.cross(tv, e1[None])
        w = (qv * d).sum(2) * inv
        t = (qv * e2[None]).sum(2) * inv
        hit = (u >= 0) & (w >= 0) & (u + w <= 1) & (t > 1e-6)
        hits[s:s + 2048] = hit.sum(1)
    return hits % 2 == 1


def hidden_faces(v, faces, body, eps=0.01):
    """Faces whose outside lies inside another body (a part pressed into a wall) or that face the ground."""
    fv = v[faces]
    n = np.cross(fv[:, 1] - fv[:, 0], fv[:, 2] - fv[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    cen = fv.mean(1) + n * eps
    hide = (n[:, 1] < -0.95) & (fv[:, :, 1].max(1) < 0.05)
    for bi in np.unique(body):
        others = body != bi
        tris = fv[body == bi]
        lo, hi = tris.reshape(-1, 3).min(0) - eps, tris.reshape(-1, 3).max(0) + eps
        cand = np.where(others & ~hide & np.all((cen >= lo) & (cen <= hi), axis=1))[0]
        if len(cand):
            # hidden only if the centre and all three corners (pulled 2 cm toward the centre) are inside:
            # a big wall face only partly covered by another body stays
            inside = ray_parity_inside(cen[cand], tris)
            for k in range(3):
                corner = fv[cand, k] + n[cand] * eps
                d = cen[cand] - corner
                corner = corner + d / np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-9) * 0.02
                inside &= ray_parity_inside(corner, tris)
            hide[cand[inside]] = True
    return hide


def charts(v, faces):
    """Connected faces sharing a dominant axis (and its sign) -> chart id, axis."""
    fv = v[faces]
    n = np.cross(fv[:, 1] - fv[:, 0], fv[:, 2] - fv[:, 0])
    ax = np.abs(n).argmax(1)
    sgn = np.sign(n[np.arange(len(n)), ax])
    key = ax * 2 + (sgn > 0)
    edge_faces = defaultdict(list)
    for fi, f in enumerate(faces):
        for k in range(3):
            e = (min(f[k], f[(k + 1) % 3]), max(f[k], f[(k + 1) % 3]))
            edge_faces[e].append(fi)
    parent = np.arange(len(faces))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for fs in edge_faces.values():
        for i in fs[1:]:
            if key[i] == key[fs[0]]:
                a, b = find(i), find(fs[0])
                if a != b:
                    parent[a] = b
    root = np.array([find(i) for i in range(len(faces))])
    _, cid = np.unique(root, return_inverse=True)
    return cid, ax


PLANE_AXES = {0: (2, 1), 1: (0, 2), 2: (0, 1)}  # dominant axis -> the two world axes it projects onto


def pack(v, faces, cid, ax, texel, res, pad=3):
    """Shelf-pack the charts; returns per-face-corner UVs (0..1) or None if they don't fit."""
    nc = cid.max() + 1
    uvm = np.zeros((len(faces), 3, 2))
    fv = v[faces]
    for f in range(len(faces)):
        a, b = PLANE_AXES[ax[f]]
        uvm[f] = fv[f][:, [a, b]]
    uvm[..., 1] *= -1  # world up reads up in the atlas
    lo = np.full((nc, 2), np.inf)
    hi = np.full((nc, 2), -np.inf)
    np.minimum.at(lo, cid, uvm.min(1))
    np.maximum.at(hi, cid, uvm.max(1))
    size = np.ceil((hi - lo) / texel).astype(int) + 2 * pad
    if (size[:, 0] > res).any():
        return None
    # skyline packing on a 2 px grid: tallest charts first, each at the lowest spot it fits
    g = 2
    sky = np.zeros(res // g, int)
    off = np.zeros((nc, 2), int)
    for c in np.lexsort((-size[:, 0], -size[:, 1])):
        w = -(-size[c, 0] // g)
        win = np.lib.stride_tricks.sliding_window_view(sky, w).max(1)
        x = int(win.argmin())
        y = int(win[x])
        off[c] = (x * g, y)
        sky[x:x + w] = y + size[c, 1]
    if sky.max() > res:
        return None
    y = int(sky.max())
    px = (uvm - lo[cid][:, None]) / texel + pad + off[cid][:, None]
    return px / res, y / res


def closest_on_tris(p, a, b, c):
    """Closest points on triangles (a, b, c) to points p (all (N, 3)); returns points and barycentrics."""
    ab, ac, ap = b - a, c - a, p - a
    d1, d2 = (ab * ap).sum(1), (ac * ap).sum(1)
    bp = p - b
    d3, d4 = (ab * bp).sum(1), (ac * bp).sum(1)
    cp = p - c
    d5, d6 = (ab * cp).sum(1), (ac * cp).sum(1)
    va = d3 * d6 - d5 * d4
    vb = d5 * d2 - d1 * d6
    vc = d1 * d4 - d3 * d2
    denom = va + vb + vc
    denom = np.where(np.abs(denom) < 1e-18, 1e-18, denom)
    v = vb / denom
    w = vc / denom
    bary = np.c_[1 - v - w, v, w]
    # regions outside the face
    r = d1 <= 0
    r &= d2 <= 0
    bary[r] = [1, 0, 0]
    m = (d3 >= 0) & (d4 <= d3)
    bary[m] = [0, 1, 0]
    m2 = (d6 >= 0) & (d5 <= d6)
    bary[m2] = [0, 0, 1]
    e = (vc <= 0) & (d1 >= 0) & (d3 <= 0) & ~r & ~m & ~m2
    t = d1[e] / np.where(d1[e] - d3[e] == 0, 1e-18, d1[e] - d3[e])
    bary[e] = np.c_[1 - t, t, np.zeros_like(t)]
    e2 = (vb <= 0) & (d2 >= 0) & (d6 <= 0) & ~r & ~m & ~m2 & ~e
    t = d2[e2] / np.where(d2[e2] - d6[e2] == 0, 1e-18, d2[e2] - d6[e2])
    bary[e2] = np.c_[1 - t, np.zeros_like(t), t]
    e3 = (va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0) & ~r & ~m & ~m2 & ~e & ~e2
    t = (d4[e3] - d3[e3]) / np.where((d4[e3] - d3[e3]) + (d5[e3] - d6[e3]) == 0, 1e-18, (d4[e3] - d3[e3]) + (d5[e3] - d6[e3]))
    bary[e3] = np.c_[np.zeros_like(t), 1 - t, t]
    q = bary[:, :1] * a + bary[:, 1:2] * b + bary[:, 2:] * c
    return q, bary


def smooth_normals(v, faces, angle=35.0):
    fv = v[faces]
    fn = np.cross(fv[:, 1] - fv[:, 0], fv[:, 2] - fv[:, 0])
    fa = np.linalg.norm(fn, axis=1, keepdims=True)
    fu = fn / np.maximum(fa, 1e-12)
    inc = defaultdict(list)
    for fi, f in enumerate(faces):
        for k in range(3):
            inc[f[k]].append(fi)
    cos = math.cos(math.radians(angle))
    out = np.zeros((len(faces), 3, 3))
    for fi, f in enumerate(faces):
        for k in range(3):
            fs = inc[f[k]]
            sel = [g for g in fs if fu[g] @ fu[fi] >= cos]
            n = fn[sel].sum(0)
            out[fi, k] = n / max(np.linalg.norm(n), 1e-12)
    return out


def cmd_bake(a):
    t0 = __import__("time").time()
    orig = Original(a.app)
    v, faces, body, names = load_obj(a.obj)
    v, faces = weld(v, faces)
    lo, hi = v.min(0), v.max(0)
    print(f"CAD bounds {lo.round(2).tolist()} {hi.round(2).tolist()}; original {orig.lo.round(2).tolist()} {orig.hi.round(2).tolist()}")
    hide = hidden_faces(v, faces, body)
    print(f"{len(faces)} faces, {hide.sum()} hidden or on the ground dropped")
    faces, body = faces[~hide], body[~hide]
    cid, ax = charts(v, faces)
    fv = v[faces]
    fn = np.cross(fv[:, 1] - fv[:, 0], fv[:, 2] - fv[:, 0])
    area = 0.5 * np.linalg.norm(fn, axis=1)
    fn /= np.maximum(2 * area[:, None], 1e-12)
    # atlas: the smallest of 1024 / 2048 that holds the target texel size, else a coarser texel at 2048
    texel, res, packed = a.texel, None, None
    for r in (1024, 2048):
        packed = pack(v, faces, cid, ax, texel, r)
        if packed:
            res = r
            break
    while packed is None:
        texel *= 1.08
        res = a.max_res
        packed = pack(v, faces, cid, ax, texel, res)
    uv, used = packed
    H = res
    while H // 2 >= used * res:  # crop the unused height: a 2:1 atlas where half the square would be empty
        H //= 2
    uv = uv * [1.0, res / H]
    print(f"{cid.max() + 1} charts, atlas {res} x {H} px at {texel * 100:.2f} cm a texel")

    # rasterize the atlas: texel centres -> 3D point and face
    tex_pos, tex_face, tex_xy = [], [], []
    for f in range(len(faces)):
        px, bary = raster_tri_uv(uv[f] * [res, H], (H, res))
        if not len(px):
            continue
        tex_pos.append(bary @ fv[f])
        tex_face.append(np.full(len(px), f))
        tex_xy.append(np.floor(px).astype(int))
    P = np.concatenate(tex_pos)
    F = np.concatenate(tex_face)
    XY = np.clip(np.concatenate(tex_xy), 0, [res - 1, H - 1])
    N = fn[F]

    # nearest original triangle: k nearest area samples, exact closest point on each candidate triangle,
    # back-facing candidates (the other side of a thin wall) penalised
    sp, stri = orig.samples(density=a.density)
    tree = cKDTree(sp)
    K = 8
    _, nb = tree.query(P, k=K)
    cand = stri[nb]                                    # (T, K) triangle ids
    best_d = np.full(len(P), np.inf)
    best_q = np.zeros((len(P), 3))
    best_b = np.zeros((len(P), 3))
    best_t = np.zeros(len(P), int)
    for k in range(K):
        ti = cand[:, k]
        q, bary = closest_on_tris(P, orig.tris[ti, 0], orig.tris[ti, 1], orig.tris[ti, 2])
        d = np.linalg.norm(q - P, axis=1)
        facing = (orig.normal[ti] * N).sum(1)
        score = d + np.where(facing < -0.3, 0.75, 0.0)
        better = score < best_d
        best_d[better], best_q[better], best_b[better], best_t[better] = score[better], q[better], bary[better], ti[better]
    suv = (best_b[:, :, None] * orig.uvs[best_t]).sum(1)
    on = orig.normal[best_t]
    depth = ((best_q - P) * on).sum(1)                 # > 0: the CAD point lies behind the original surface

    filled = [filled_rgb(im) for im in orig.images]
    col = np.zeros((len(P), 3))
    alpha = np.ones(len(P))
    for mi in np.unique(orig.mat[best_t]):
        img = orig.mat_image[mi]
        sel = orig.mat[best_t] == mi
        if img is None:
            col[sel] = 0.5
            continue
        keep = orig.images
        orig.images = filled
        s = orig.sample_image(img, suv[sel])
        orig.images = keep
        col[sel] = s[:, :3]
        alpha[sel] = orig.sample_image(img, suv[sel], bilinear=False)[:, 3]
    glass = np.array([float(x) for x in a.glass.split(",")]) / 255.0
    pane = (alpha < 0.5) & (np.abs((on * N).sum(1)) > 0.7)
    shade = 0.75 + 0.25 * np.clip((P[:, 1] - orig.lo[1]) / max(orig.hi[1] - orig.lo[1], 1), 0, 1)  # panes: darker low down
    col[pane] = glass * (0.85 + 0.3 * ((P[pane] @ np.array([0.37, 0.61, 0.23])) % 1.0 > 0.5))[:, None] * shade[pane, None]
    ao = 1.0 - a.ao * np.clip(depth / a.ao_depth, 0.0, 1.0)
    for bi, nm in enumerate(names):
        if nm.endswith("@avg"):  # one flat colour: the mean of the art under it (a rib across painted stripes)
            sel = body[F] == bi
            if sel.any():
                col[sel] = col[sel].mean(0) * (0.97 + 0.06 * np.random.default_rng(bi).random((sel.sum(), 1)))
        elif "@" in nm:
            hexc = nm.rsplit("@", 1)[1][:6]
            sel = body[F] == bi
            base = np.array([int(hexc[i:i + 2], 16) for i in (0, 2, 4)]) / 255.0
            # keep the original's light and dark variation, on the fixed colour
            lum = col[sel].mean(1, keepdims=True)
            col[sel] = base * (0.8 + 0.4 * np.clip(lum / max(col[sel].mean(), 1e-3), 0.5, 1.5) / 1.5)
    col *= ao[:, None]
    print(f"bake: {len(P)} texels, {pane.sum()} glass, mean |distance| {np.abs(best_d).mean() * 100:.1f} cm, "
          f"95th pct {np.percentile(best_d, 95) * 100:.1f} cm")

    atlas = np.zeros((H, res, 3), np.float32)
    done = np.zeros((H, res), bool)
    atlas[XY[:, 1], XY[:, 0]] = col
    done[XY[:, 1], XY[:, 0]] = True
    # grow charts into their padding (and past it a little) so mips and bilinear lookups don't bleed black
    _, (iy, ix) = ndimage.distance_transform_edt(~done, return_indices=True)
    grown = atlas[iy, ix]
    far = ndimage.distance_transform_edt(~done) > 8
    grown[far] = grown[far].mean(0) if (~far).any() else 0.5
    img = Image.fromarray((np.clip(grown, 0, 1) * 255 + 0.5).astype(np.uint8))
    out_png = Path(a.out or OBJ_DIR / f"{a.app}_cad.glb")
    if a.atlas_png:
        img.save(a.atlas_png)

    # vertices: one per (face corner position, chart, smooth normal)
    cn = smooth_normals(v, faces, a.smooth)
    corner_pos = v[faces].reshape(-1, 3)
    corner_uv = uv.reshape(-1, 2)
    corner_n = cn.reshape(-1, 3)
    key = np.c_[np.round(corner_pos * 1e4), np.round(corner_uv * 1e6), np.round(corner_n * 1e3)].astype(np.int64)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    pos, tuv, nor = corner_pos[first], corner_uv[first], corner_n[first]
    tris = inv.reshape(-1, 3)
    write_glb(out_png, orig, a, pos, nor, tuv, tris, img)
    print(f"wrote {out_png}: {len(pos)} verts, {len(tris)} tris, {out_png.stat().st_size / 1024:.0f} KB "
          f"({__import__('time').time() - t0:.0f} s)")


def write_glb(path, orig, a, pos, nor, uv, tris, albedo):
    name = next((n.get("name") for n in orig.gltf["nodes"] if "mesh" in n), a.app)
    gltf = {"asset": {"version": "2.0", "generator": "lance-commander cad_building"}, "scene": 0,
            "scenes": [{"nodes": [0]}], "nodes": [], "meshes": [], "accessors": [], "bufferViews": [],
            "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 33071, "wrapT": 33071}],
            "images": [], "textures": [], "materials": []}
    w = R.GlbWriter(gltf, bytearray())

    def image(data, mime):
        view = w._view(data)
        gltf["images"].append({"bufferView": view, "mimeType": mime})
        src = len(gltf["images"]) - 1
        if mime == "image/webp":  # glTF EXT_texture_webp, as tools/art/glb_webp.py writes it (Godot imports it)
            gltf["textures"].append({"sampler": 0, "extensions": {"EXT_texture_webp": {"source": src}}})
            gltf["extensionsUsed"] = gltf["extensionsRequired"] = ["EXT_texture_webp"]
        else:
            gltf["textures"].append({"source": src, "sampler": 0})
        return len(gltf["textures"]) - 1
    buf = io.BytesIO()
    albedo.save(buf, "WEBP", quality=a.quality, method=6)
    gltf["materials"].append({"name": "cad", "pbrMetallicRoughness": {"baseColorTexture": {"index": image(buf.getvalue(), "image/webp")},
                              "metallicFactor": 0.0, "roughnessFactor": 1.0}})
    attrs = {"POSITION": w.accessor(pos, "VEC3", target=34962, minmax=True),
             "NORMAL": w.accessor(nor, "VEC3", target=34962),
             "TEXCOORD_0": w.accessor(uv, "VEC2", target=34962)}
    ind = w.accessor(tris.reshape(-1).astype(np.uint32), "SCALAR", comp=5125, target=34963)
    gltf["meshes"].append({"name": name, "primitives": [{"attributes": attrs, "indices": ind, "material": 0}]})
    gltf["nodes"].append({"name": name, "mesh": 0, "children": []})
    # nodes kept from the original as they are (glowing cards, moving parts), with their upscaled textures
    og, ob = orig.gltf, orig.bin
    worlds = R.world_matrices(og)
    img_map = {}
    for ni, node in enumerate(og["nodes"]):
        if node.get("name") not in a.keep or "mesh" not in node:
            continue
        prims = []
        for prim in og["meshes"][node["mesh"]]["primitives"]:
            p = R.read_accessor(og, ob, prim["attributes"]["POSITION"]).astype(np.float32)
            p = (worlds[ni] @ np.c_[p, np.ones(len(p))].T).T[:, :3]
            t = R.read_accessor(og, ob, prim["attributes"]["TEXCOORD_0"]).astype(np.float32)
            src = og["materials"][prim["material"]]
            mi = orig.mat_image[prim["material"]]
            if mi not in img_map:
                iv = og["bufferViews"][og["images"][mi]["bufferView"]]
                o = iv.get("byteOffset", 0)
                im = Image.open(io.BytesIO(bytes(ob[o:o + iv["byteLength"]]))).convert("RGBA")
                b2 = io.BytesIO()
                im.save(b2, "PNG", optimize=True)
                tex = image(b2.getvalue(), "image/png")
                gltf["materials"].append({"name": f"kept_{mi}", "pbrMetallicRoughness": {"baseColorTexture": {"index": tex},
                                          "metallicFactor": 0.0, "roughnessFactor": 1.0},
                                          "alphaMode": src.get("alphaMode", "MASK"), "alphaCutoff": src.get("alphaCutoff", 0.5),
                                          "doubleSided": True})
                img_map[mi] = len(gltf["materials"]) - 1
            at = {"POSITION": w.accessor(p, "VEC3", target=34962, minmax=True), "TEXCOORD_0": w.accessor(t, "VEC2", target=34962)}
            if "NORMAL" in prim["attributes"]:
                nn = R.read_accessor(og, ob, prim["attributes"]["NORMAL"]).astype(np.float32)
                at["NORMAL"] = w.accessor((worlds[ni][:3, :3] @ nn.T).T, "VEC3", target=34962)
            prims.append({"attributes": at, "material": img_map[mi]})
        gltf["meshes"].append({"name": node["name"], "primitives": prims})
        gltf["nodes"].append({"name": node["name"], "mesh": len(gltf["meshes"]) - 1})
        gltf["nodes"][0]["children"].append(len(gltf["nodes"]) - 1)
    if not gltf["nodes"][0]["children"]:
        del gltf["nodes"][0]["children"]
    w.write(str(path))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("openings")
    s.add_argument("app")
    s = sub.add_parser("decal")
    s.add_argument("app")
    s.add_argument("mat", type=int)
    s.add_argument("rect", type=float, nargs=4)
    s = sub.add_parser("bake")
    s.add_argument("app")
    s.add_argument("obj")
    s.add_argument("--out")
    s.add_argument("--keep", nargs="*", default=[])
    s.add_argument("--glass", default="44,58,72")
    s.add_argument("--texel", type=float, default=0.02)
    s.add_argument("--max-res", type=int, default=2048)
    s.add_argument("--density", type=float, default=600)
    s.add_argument("--ao", type=float, default=0.45)
    s.add_argument("--ao-depth", type=float, default=0.45)
    s.add_argument("--smooth", type=float, default=35.0)
    s.add_argument("--quality", type=int, default=88)
    s.add_argument("--atlas-png")
    a = ap.parse_args()
    {"openings": cmd_openings, "decal": cmd_decal, "bake": cmd_bake}[a.cmd](a)


if __name__ == "__main__":
    main()
