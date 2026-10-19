#!/usr/bin/env python3
"""HD trees (world-rendering step 3): procedural trees on CC0 Poly Haven foliage, one per original tree type.

    python3 -I tools/art/trees.py [--src ~/craft/solid/mc2/tree_cc0] [--only pine1,oak1]

The originals are 10-33 triangle alpha cards with 128 px textures. Each HD tree keeps its original's size,
crown shape and leaf colour (sampled from the original texture, so every map keeps its palette) and is built
from a tapered bark trunk, branches and a crown of leaf-cluster cards whose normals point out of the crown (soft,
volume-like lighting). Writes:
  game/assets/trees/leaves.png   leaf atlas, 2 x 2 cells of 512 px: 0 conifer branch (fir sprigs), 1 broadleaf
                                 cluster (jacaranda fronds), 2 palm frond, 3 willow curtain
  game/assets/trees/bark.png     tiling bark (pine bark)
  game/assets/trees/<appearance>.glb   meshes "bark" and "leaves" (COLOR_0 = tint), metres, Y up, base at 0
Drawn with MultiMesh by game/scripts/world/objects_view.gd; wind and alpha in game/shaders/leaves.gdshader.
Sources: Poly Haven fir_tree_01, pine_tree_01 and jacaranda_tree textures, CC0 1.0 (polyhaven.com).
"""
import argparse
import json
import math
import os
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hd_rig as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "game/assets/trees"
CELL = 512

# appearance -> (kind, params). Sizes come from the original model (measured at build time).
TYPES = {
    "pine1": ("conifer", {"tiers": 10}), "pine2": ("conifer", {"tiers": 12}), "pine3": ("conifer", {"tiers": 14}),
    "pine1dead": ("conifer_dead", {}), "pine2dead": ("conifer_dead", {}), "pine3dead": ("conifer_dead", {}),
    "oak1": ("broadleaf", {"crown": (0.95, 0.62), "trunk_h": 0.38, "cards": 70}),
    "oak2": ("broadleaf", {"crown": (0.95, 0.6), "trunk_h": 0.4, "cards": 50}),
    "oak3": ("broadleaf", {"crown": (0.95, 0.6), "trunk_h": 0.4, "cards": 55}),
    "maple1": ("broadleaf", {"crown": (0.9, 0.7), "trunk_h": 0.32, "cards": 45}),
    "maple2": ("broadleaf", {"crown": (0.85, 0.75), "trunk_h": 0.3, "cards": 45}),
    "maple3": ("broadleaf", {"crown": (0.9, 0.65), "trunk_h": 0.35, "cards": 45}),
    "birch1": ("broadleaf", {"crown": (0.75, 0.6), "trunk_h": 0.45, "cards": 30, "bark": (0.95, 0.93, 0.88)}),
    "birch2": ("broadleaf", {"crown": (0.75, 0.6), "trunk_h": 0.45, "cards": 30, "bark": (0.95, 0.93, 0.88)}),
    "birch3": ("broadleaf", {"crown": (0.75, 0.6), "trunk_h": 0.45, "cards": 34, "bark": (0.95, 0.93, 0.88)}),
    "jungletree1": ("broadleaf", {"crown": (1.0, 0.55), "trunk_h": 0.45, "cards": 45}),
    "jungletree2": ("broadleaf", {"crown": (1.0, 0.5), "trunk_h": 0.5, "cards": 60}),
    "willow1": ("willow", {}), "willow2": ("willow", {}), "willow3": ("willow", {}),
    "oak1dead": ("broadleaf_dead", {}), "oak2dead": ("broadleaf_dead", {}), "oak3dead": ("broadleaf_dead", {}),
    "maple1dead": ("broadleaf_dead", {}), "maple2dead": ("broadleaf_dead", {}), "maple3dead": ("broadleaf_dead", {}),
    "willow1dead": ("broadleaf_dead", {}), "willow2dead": ("broadleaf_dead", {}), "willow3dead": ("broadleaf_dead", {}),
    "birch3dead": ("broadleaf_dead", {"bark": (0.95, 0.93, 0.88)}),
    "palm1": ("palm", {}), "palms": ("palm_group", {}),
    "tc1_1": ("clump", {"seed": 1}), "tc1_2": ("clump", {"seed": 2}), "tc1_3": ("clump", {"seed": 3}),
    "tc1_4": ("clump", {"seed": 4}),
}


# --- atlas -------------------------------------------------------------------

def rgba(src, asset, diff, alpha):
    d = Image.open(f"{src}/{asset}/{diff}.png").convert("RGB")
    a = Image.open(f"{src}/{asset}/{alpha}.png").convert("L").resize(d.size)
    im = d.copy()
    im.putalpha(a)
    return im


def pieces(im, box, min_px=1500):
    """The separate sprigs / fronds in a region of an RGBA texture (connected alpha components)."""
    W, H = im.size
    crop = im.crop((int(box[0] * W), int(box[1] * H), int(box[2] * W), int(box[3] * H)))
    a = np.asarray(crop)[..., 3] > 100
    lab, n = ndimage.label(a)
    out = []
    for sl in ndimage.find_objects(lab):
        sub = crop.crop((sl[1].start, sl[0].start, sl[1].stop, sl[0].stop))
        if np.asarray(sub)[..., 3].astype(bool).sum() > min_px:
            out.append(sub)
    return out


def paste(canvas, piece, cx, cy, size, angle):
    p = piece.copy()
    s = size / max(p.size)
    p = p.resize((max(1, int(p.width * s)), max(1, int(p.height * s))), Image.LANCZOS).rotate(angle, expand=True, resample=Image.BICUBIC)
    canvas.alpha_composite(p, (int(cx - p.width / 2), int(cy - p.height / 2)))


def build_atlas(src):
    rng = np.random.default_rng(7)
    fir = rgba(src, "fir_tree_01", "twig_diff", "twig_alpha")
    sprigs = pieces(fir, (0.17, 0.0, 1.0, 0.8))
    jac = rgba(src, "jacaranda_tree", "leaves_diff", "leaves_alpha")
    fronds = pieces(jac, (0.0, 0.0, 1.0, 1.0), min_px=8000)
    print(f"atlas sources: {len(sprigs)} fir sprigs, {len(fronds)} jacaranda fronds")
    cells = []
    # 0 conifer branch: sprigs along a line from the trunk (left) outward, drooping, shrinking
    c = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
    for i in range(46):
        t = rng.random()
        x = 20 + t * 470
        y = CELL / 2 + (rng.random() - 0.5) * (260 - 200 * t) + 30 * t
        paste(c, sprigs[rng.integers(len(sprigs))], x, y, 200 - 110 * t, rng.uniform(-60, 60) - 90)
    cells.append(c)
    # 1 broadleaf cluster: fronds radiating from the centre, a rounded blob
    c = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
    for i in range(30):
        ang = rng.uniform(0, 360)
        r = rng.uniform(0, 120)
        paste(c, fronds[rng.integers(len(fronds))], CELL / 2 + r * math.cos(math.radians(ang)),
              CELL / 2 + r * math.sin(math.radians(ang)), rng.uniform(230, 330), ang)
    cells.append(c)
    # 2 palm frond: the longest frond along the cell, left (base) to right (tip)
    c = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
    big = max(fronds, key=lambda p: max(p.size))
    for k, (dy, s) in enumerate(((0, 1.0), (-60, 0.8), (60, 0.8))):
        p = big.copy()
        if p.height > p.width:
            p = p.rotate(90, expand=True)
        p = p.resize((int(CELL * 0.98 * s), int(CELL * 0.98 * s * p.height / p.width)), Image.LANCZOS)
        c.alpha_composite(p, (int(CELL * (1 - 0.98 * s) / 2), int(CELL / 2 - p.height / 2 + dy)))
    cells.append(c)
    # 3 willow curtain: fronds hanging from the top edge
    c = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
    for i in range(28):
        paste(c, fronds[rng.integers(len(fronds))], rng.uniform(30, CELL - 30), rng.uniform(140, 340),
              rng.uniform(260, 380), 90 + rng.uniform(-12, 12))
    cells.append(c)
    atlas = Image.new("RGBA", (2 * CELL, 2 * CELL), (0, 0, 0, 0))
    means = []
    for i, c in enumerate(cells):
        a = np.asarray(c).astype(float)
        m = a[..., 3] > 128
        means.append(a[m][:, :3].mean(0))
        # bleed colour into the transparent texels so mips don't darken the edges
        rgb = Image.fromarray(a[..., :3].astype(np.uint8))
        filled = rgb.filter(ImageFilter.MaxFilter(9))
        rgb_out = np.where(m[..., None], a[..., :3], np.asarray(filled))
        cc = Image.fromarray(np.dstack([rgb_out, a[..., 3]]).astype(np.uint8), "RGBA")
        atlas.paste(cc, ((i % 2) * CELL, (i // 2) * CELL))
    OUT.mkdir(parents=True, exist_ok=True)
    atlas.save(OUT / "leaves.png")
    bark = Image.open(f"{src}/pine_tree_01/bark_diff.png").convert("RGB").resize((512, 512), Image.LANCZOS)
    bark.save(OUT / "bark.png")
    return [m.tolist() for m in means]


# --- geometry -----------------------------------------------------------------

class Mesh:
    def __init__(self):
        self.p, self.n, self.uv, self.c, self.i = [], [], [], [], []

    def quad(self, corners, uvs, normals, col):
        b = len(self.p)
        self.p += corners
        self.uv += uvs
        self.n += normals
        self.c += [col] * 4
        self.i += [b, b + 1, b + 2, b, b + 2, b + 3]

    def tube(self, a, b, ra, rb, col, sides=7, uv_v=1.0):
        """A tapered cylinder from a to b."""
        a, b = np.asarray(a, float), np.asarray(b, float)
        ax = b - a
        L = np.linalg.norm(ax)
        d = ax / (L + 1e-9)
        u = np.cross(d, [0, 0, 1] if abs(d[1]) > 0.9 else [0, 1, 0])
        u /= np.linalg.norm(u)
        v = np.cross(d, u)
        base = len(self.p)
        for k in range(sides + 1):
            t = 2 * math.pi * k / sides
            dirn = u * math.cos(t) + v * math.sin(t)
            for end, r in ((a, ra), (b, rb)):
                self.p.append((end + dirn * r).tolist())
                self.n.append(dirn.tolist())
                self.uv.append([k / sides * max(1, round(2 * math.pi * ra / 1.2)), (0 if end is a else L) / 2.0 * uv_v])
                self.c.append(col)
        for k in range(sides):
            i0 = base + 2 * k
            self.i += [i0, i0 + 2, i0 + 1, i0 + 1, i0 + 2, i0 + 3]


def cell_uv(cell, flip=False):
    u0, v0 = (cell % 2) * 0.5, (cell // 2) * 0.5
    e = 0.004
    uv = [[u0 + e, v0 + e], [u0 + 0.5 - e, v0 + e], [u0 + 0.5 - e, v0 + 0.5 - e], [u0 + e, v0 + 0.5 - e]]
    return uv[::-1] if flip else uv


def card(mesh, centre, right, up, w, h, cell, col, normal_from=None, anchor="centre"):
    """A leaf card; normals point out of the crown (from normal_from) for soft volume lighting."""
    c, r, u = np.asarray(centre, float), np.asarray(right, float), np.asarray(up, float)
    r /= np.linalg.norm(r)
    u /= np.linalg.norm(u)
    if anchor == "left":  # the card starts at the centre point (a branch from the trunk)
        c = c + r * w / 2
    if anchor == "top":
        c = c - u * h / 2
    pts = [c - r * w / 2 - u * h / 2, c + r * w / 2 - u * h / 2, c + r * w / 2 + u * h / 2, c - r * w / 2 + u * h / 2]
    if normal_from is None:
        nrm = [np.cross(r, u).tolist()] * 4
    else:
        nrm = []
        for p in pts:
            n_ = p - np.asarray(normal_from, float)
            n_ = n_ / (np.linalg.norm(n_) + 1e-9) * 0.7 + np.array([0, 0.3, 0])
            nrm.append((n_ / np.linalg.norm(n_)).tolist())
    mesh.quad([p.tolist() for p in pts], cell_uv(cell), nrm, col)


def rot_y(v, a):
    c, s = math.cos(a), math.sin(a)
    return np.array([c * v[0] + s * v[2], v[1], -s * v[0] + c * v[2]])


def conifer(bark, leaves, H, W, leaf, bark_col, rng, at=(0, 0, 0), tiers=9, dead=False):
    at = np.asarray(at, float)
    bark.tube(at + [0, -0.6, 0], at + [0, H, 0], max(0.12, H * 0.022), 0.03, bark_col)
    if dead:
        for k in range(10):
            y = H * rng.uniform(0.25, 0.9)
            a = rng.uniform(0, 2 * math.pi)
            L = (1 - y / H) * W * 0.45 + 0.4
            d = rot_y(np.array([1.0, -0.15, 0]), a)
            bark.tube(at + [0, y, 0], at + [0, y, 0] + d * L, 0.06, 0.015, bark_col, sides=4)
        return
    for t in range(tiers):
        f = t / (tiers - 1)
        y = H * (0.16 + 0.82 * f)
        R_ = (W / 2) * (1.0 - f) ** 1.05 + 0.25
        n = max(4, int(round(10 - 5 * f)))
        for layer, (rs, ws, droop) in enumerate(((1.0, 1.0, 0.42), (0.6, 0.85, 0.25))):  # outer branches + inner fill
            dark = 1.0 if layer == 0 else 0.7
            col = [leaf[0] * dark, leaf[1] * dark, leaf[2] * dark, 1.0]
            for k in range(n):
                a = 2 * math.pi * (k + rng.random() * 0.6 + 0.5 * layer) / n + t * 0.7
                right = rot_y(np.array([1.0, -droop - 0.2 * f, 0]), a)
                up = rot_y(np.array([0, 0.25, 1.0]), a)
                card(leaves, at + [0, y + 0.3 * layer, 0], right, up, R_ * 1.2 * rs, R_ * 1.0 * ws, 0, col,
                     normal_from=at + [0, y - R_ * 0.5, 0], anchor="left")
    for a in (0.0, math.pi / 2):  # the top: two crossed upright cards
        card(leaves, at + [0, H * 0.94, 0], rot_y(np.array([0, 1.0, 0]), 0), rot_y(np.array([1.0, 0, 0]), a),
             H * 0.16, W * 0.18, 0, leaf, normal_from=at + [0, H * 0.8, 0])


def broadleaf(bark, leaves, H, W, leaf, bark_col, rng, at=(0, 0, 0), crown=(0.95, 0.6), trunk_h=0.4, cards=50, dead=False):
    at = np.asarray(at, float)
    rx, ry = W / 2 * crown[0] * 0.85, H * crown[1] / 2 * 0.9
    cy = H - ry
    r0 = max(0.15, H * 0.03)
    bark.tube(at + [0, -0.6, 0], at + [0, H * trunk_h + 0.5, 0], r0, r0 * 0.75, bark_col)
    limbs = []
    for k in range(5 if not dead else 7):
        a = 2 * math.pi * k / 5 + rng.uniform(-0.4, 0.4)
        top = at + [0, cy, 0] + rot_y(np.array([rx * rng.uniform(0.35, 0.7), ry * rng.uniform(-0.1, 0.55), 0]), a)
        bark.tube(at + [0, H * trunk_h, 0], top, r0 * 0.6, r0 * 0.15, bark_col, sides=5)
        limbs.append(top)
    if dead:
        for top in limbs:
            for j in range(2):
                tip = top + rng.normal(0, 1, 3) * [rx * 0.3, ry * 0.3, rx * 0.3] + [0, ry * 0.2, 0]
                bark.tube(top, tip, r0 * 0.12, 0.02, bark_col, sides=4)
        return
    centre = at + [0, cy, 0]
    for k in range(cards):
        # points on and inside the crown ellipsoid, more at the shell
        d = rng.normal(0, 1, 3)
        d /= np.linalg.norm(d)
        s = rng.uniform(0.55, 1.0) ** 0.5
        p = centre + d * [rx * s, ry * s, rx * s]
        if p[1] < at[1] + H * trunk_h:
            p[1] = at[1] + H * trunk_h + rng.uniform(0, ry * 0.3)
        out = (p - centre)
        out /= np.linalg.norm(out) + 1e-9
        right = np.cross(out, [0, 1, 0])
        if np.linalg.norm(right) < 0.1:
            right = np.array([1.0, 0, 0])
        right = right / np.linalg.norm(right) + rng.normal(0, 0.3, 3)
        up = np.cross(right, out) + rng.normal(0, 0.3, 3)
        size = (rx + ry) * rng.uniform(0.55, 0.8)
        card(leaves, p, right, up, size, size, 1, leaf, normal_from=centre)


def willow(bark, leaves, H, W, leaf, bark_col, rng, at=(0, 0, 0)):
    broadleaf(bark, leaves, H, W, leaf, bark_col, rng, at, crown=(0.75, 0.45), trunk_h=0.45, cards=26)
    at = np.asarray(at, float)
    rx = W / 2 * 0.9
    centre = at + [0, H * 0.72, 0]
    for k in range(22):  # the hanging curtain around the crown edge
        a = 2 * math.pi * k / 22 + rng.uniform(-0.1, 0.1)
        top = at + rot_y(np.array([rx * rng.uniform(0.75, 1.0), H * rng.uniform(0.8, 0.95), 0]), a)
        tangent = rot_y(np.array([0, 0, 1.0]), a)
        hang = H * rng.uniform(0.45, 0.65)
        card(leaves, top, tangent, np.array([0, 1.0, 0]) + rot_y(np.array([0.15, 0, 0]), a), rx * 0.9, hang, 3, leaf,
             normal_from=centre, anchor="top")


def palm(bark, leaves, H, W, leaf, bark_col, rng, at=(0, 0, 0)):
    at = np.asarray(at, float)
    lean = rng.uniform(0, 2 * math.pi)
    prev = at + [0, -0.5, 0]
    segs = 6
    for s in range(1, segs + 1):  # a curved trunk
        f = s / segs
        cur = at + [0, H * 0.9 * f, 0] + rot_y(np.array([H * 0.08 * f * f, 0, 0]), lean)
        bark.tube(prev, cur, 0.28 - 0.1 * f, 0.26 - 0.1 * f, bark_col, sides=6)
        prev = cur
    crown = prev
    for k in range(9):
        a = 2 * math.pi * k / 9 + rng.uniform(-0.15, 0.15)
        L = W * rng.uniform(0.45, 0.6)
        right = rot_y(np.array([1.0, rng.uniform(-0.55, -0.25), 0]), a)
        up = rot_y(np.array([0, 0.3, 1.0]), a)
        card(leaves, crown, right, up, L, L * 0.45, 2, leaf, normal_from=crown - [0, 1.0, 0], anchor="left")


def build(app, kind, prm, H, W, leaf, means, seed):
    rng = np.random.default_rng(seed)
    bark, leaves = Mesh(), Mesh()
    bark_col = list(prm.get("bark", (0.62, 0.56, 0.5))) + [1.0]
    cell = {"conifer": 0, "conifer_dead": 0, "broadleaf": 1, "broadleaf_dead": 1, "willow": 3, "palm": 2, "palm_group": 2, "clump": 1}[kind]
    ref = np.asarray(means[cell])
    gain = {0: 0.62}.get(cell, 1.2)  # conifers read darker, as the originals do
    tint = np.clip(np.asarray(leaf, float) / ref * gain, 0.15, 2.0).tolist() + [1.0]
    if kind == "conifer":
        conifer(bark, leaves, H, W, tint, bark_col, rng, tiers=prm.get("tiers", 9))
    elif kind == "conifer_dead":
        conifer(bark, leaves, H, W, tint, bark_col, rng, dead=True)
    elif kind == "broadleaf":
        broadleaf(bark, leaves, H, W, tint, bark_col, rng, crown=prm.get("crown", (0.95, 0.6)),
                  trunk_h=prm.get("trunk_h", 0.4), cards=prm.get("cards", 50))
    elif kind == "broadleaf_dead":
        broadleaf(bark, leaves, H, W, tint, bark_col, rng, dead=True)
    elif kind == "willow":
        willow(bark, leaves, H, W, tint, bark_col, rng)
    elif kind == "palm":
        palm(bark, leaves, H, W, tint, bark_col, rng)
    elif kind == "palm_group":
        for k, (dx, dz, s) in enumerate(((0, 0, 1.0), (3.2, 1.5, 0.8), (-2.6, 2.4, 0.9))):
            palm(bark, leaves, H * s, W * 0.45 * s, tint, bark_col, rng, at=(dx, 0, dz))
    elif kind == "clump":  # a stand of 5-7 trees in the original clump's footprint, mostly broadleaf
        n = int(rng.integers(5, 8))
        for k in range(n):
            a = 2 * math.pi * k / n + rng.uniform(-0.3, 0.3)
            r = W * 0.32 * rng.uniform(0.3, 1.0) if k else 0.0
            at = (r * math.cos(a), 0, r * math.sin(a))
            h = H * rng.uniform(0.55, 0.95)
            if rng.random() < 0.3:
                conifer(bark, leaves, h, h * 0.45, (np.asarray(tint) * [0.85, 0.95, 0.85, 1]).tolist(), bark_col, rng, at=at)
            else:
                broadleaf(bark, leaves, h, h * rng.uniform(0.7, 0.95), tint, bark_col, rng, at=at, cards=34)
    return bark, leaves


# --- glb ----------------------------------------------------------------------

def write_glb(path, meshes):
    gl = {"asset": {"version": "2.0", "generator": "mc2-remake tools/art/trees.py"}, "scene": 0, "scenes": [{"nodes": []}],
          "nodes": [], "meshes": [], "buffers": [{}], "bufferViews": [], "accessors": []}
    binary = bytearray()

    def acc(arr, kind, comp, target, minmax=False):
        a = np.ascontiguousarray(arr)
        while len(binary) % 4:
            binary.append(0)
        gl["bufferViews"].append({"buffer": 0, "byteOffset": len(binary), "byteLength": a.nbytes, "target": target})
        x = {"bufferView": len(gl["bufferViews"]) - 1, "componentType": comp, "count": int(a.shape[0]), "type": kind}
        if minmax:
            x["min"], x["max"] = a.min(0).tolist(), a.max(0).tolist()
        gl["accessors"].append(x)
        binary.extend(a.tobytes())
        return len(gl["accessors"]) - 1
    for name, m in meshes:
        if not m.i:
            continue
        prim = {"attributes": {"POSITION": acc(np.array(m.p, np.float32), "VEC3", 5126, 34962, True),
                               "NORMAL": acc(np.array(m.n, np.float32), "VEC3", 5126, 34962),
                               "TEXCOORD_0": acc(np.array(m.uv, np.float32), "VEC2", 5126, 34962),
                               "COLOR_0": acc(np.array(m.c, np.float32), "VEC4", 5126, 34962)},
                "indices": acc(np.array(m.i, np.uint32), "SCALAR", 5125, 34963)}
        gl["meshes"].append({"name": name, "primitives": [prim]})
        gl["nodes"].append({"name": name, "mesh": len(gl["meshes"]) - 1})
        gl["scenes"][0]["nodes"].append(len(gl["nodes"]) - 1)
    while len(binary) % 4:
        binary.append(0)
    gl["buffers"][0]["byteLength"] = len(binary)
    js = json.dumps(gl).encode()
    js += b" " * (-len(js) % 4)
    Path(path).write_bytes(struct.pack("<III", 0x46546C67, 2, 28 + len(js) + len(binary)) + struct.pack("<II", len(js), 0x4E4F534A)
                           + js + struct.pack("<II", len(binary), 0x004E4942) + bytes(binary))


def original_size_and_leaf(app):
    g, b = R.load_glb(str(ROOT / f"game/assets/objects/{app}.glb"))
    P = np.concatenate([R.read_accessor(g, b, p["attributes"]["POSITION"]) for m in g["meshes"] for p in m["primitives"]])
    H = float(P[:, 1].max())
    W = float(max(np.ptp(P[:, 0]), np.ptp(P[:, 2])))
    im = np.asarray(Image.open(ROOT / f"game/assets/objects/{app}_0.png").convert("RGBA")).reshape(-1, 4).astype(float)
    leaf = im[(im[:, 3] > 128) & (im[:, 1] >= im[:, 0] * 0.8)]
    col = leaf[:, :3].mean(0) if len(leaf) > 50 else np.array([45.0, 52.0, 34.0])
    return H, W, col


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.expanduser("~/craft/solid/mc2/tree_cc0"))
    ap.add_argument("--only")
    a = ap.parse_args()
    means = build_atlas(a.src)
    only = set(a.only.split(",")) if a.only else None
    report = {}
    for k, (app, (kind, prm)) in enumerate(TYPES.items()):
        if only and app not in only:
            continue
        H, W, leaf = original_size_and_leaf(app)
        bark, leaves = build(app, kind, prm, H, W, leaf, means, seed=1000 + k + prm.get("seed", 0) * 17)
        write_glb(OUT / f"{app}.glb", [("bark", bark), ("leaves", leaves)])
        report[app] = {"kind": kind, "height_m": round(H, 1), "width_m": round(W, 1), "tris": (len(bark.i) + len(leaves.i)) // 3}
        print(f"{app:12} {kind:15} H {H:5.1f} W {W:5.1f} tris {report[app]['tris']}")
    (OUT / "trees.json").write_text(json.dumps({"types": report, "sources": "Poly Haven fir_tree_01, pine_tree_01, jacaranda_tree textures (CC0 1.0)"}, indent=1) + "\n")


if __name__ == "__main__":
    main()
