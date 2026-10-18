"""Step 3 of the HD mech pipeline: fit an HD mesh (Hunyuan3D, decimated + UV-unwrapped)
to the original converted mech, rig it to the original joints, transfer the original
paint mask, and write a skinned .glb that keeps the original hierarchy and animations.

    python3 -I tools/art/hd_rig.py <original.glb> <original_paint.png> <hd_low.glb>
        <normal.png> <ao.png> <out.glb> <out_paint.png> [--tex 1024]

Fitting: yaw search (5 deg steps, with and without an X mirror) scored by symmetric
nearest-surface distance, then ICP with uniform scale (Umeyama). Skinning is rigid:
each HD vertex follows the original mesh part nearest to it in the rest pose.
"""

import argparse
import io
import json
import math
import struct

import numpy as np
from PIL import Image, ImageFilter
from scipy.spatial import cKDTree

COMP = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


# --- glb io -----------------------------------------------------------------

def load_glb(path):
    data = open(path, "rb").read()
    jl = struct.unpack_from("<I", data, 12)[0]
    gltf = json.loads(data[20:20 + jl])
    off = 20 + jl
    bl = struct.unpack_from("<I", data, off)[0]
    return gltf, bytearray(data[off + 8:off + 8 + bl])


def read_accessor(gltf, binary, index):
    acc = gltf["accessors"][index]
    view = gltf["bufferViews"][acc["bufferView"]]
    dtype = COMP[acc["componentType"]]
    width = WIDTH[acc["type"]]
    start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = view.get("byteStride", 0)
    count = acc["count"]
    item = np.dtype(dtype).itemsize * width
    if stride and stride != item:
        raw = np.frombuffer(bytes(binary[start:start + stride * count]), dtype=np.uint8).reshape(count, stride)[:, :item]
        arr = np.frombuffer(raw.tobytes(), dtype=dtype)
    else:
        arr = np.frombuffer(bytes(binary[start:start + item * count]), dtype=dtype)
    return arr.reshape(count, width) if width > 1 else arr.copy()


class GlbWriter:
    def __init__(self, gltf, binary):
        self.gltf = gltf
        self.bin = binary

    def _view(self, data, target=None):
        while len(self.bin) % 4:
            self.bin += b"\0"
        v = {"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(data)}
        if target:
            v["target"] = target
        self.bin += data
        self.gltf["bufferViews"].append(v)
        return len(self.gltf["bufferViews"]) - 1

    def accessor(self, arr, kind, comp=5126, target=None, minmax=False):
        dtype = COMP[comp]
        a = np.ascontiguousarray(arr, dtype=dtype)
        view = self._view(a.tobytes(), target)
        acc = {"bufferView": view, "componentType": comp, "count": int(a.shape[0]), "type": kind}
        if minmax:
            acc["min"] = a.min(axis=0).tolist()
            acc["max"] = a.max(axis=0).tolist()
        self.gltf["accessors"].append(acc)
        return len(self.gltf["accessors"]) - 1

    def image(self, png_bytes):
        view = self._view(png_bytes)
        self.gltf.setdefault("images", []).append({"bufferView": view, "mimeType": "image/png"})
        self.gltf.setdefault("samplers", [{"magFilter": 9729, "minFilter": 9987}])
        self.gltf.setdefault("textures", []).append({"source": len(self.gltf["images"]) - 1, "sampler": 0})
        return len(self.gltf["textures"]) - 1

    def write(self, path):
        self.gltf["buffers"] = [{"byteLength": len(self.bin)}]
        js = json.dumps(self.gltf, separators=(",", ":")).encode()
        js += b" " * ((4 - len(js) % 4) % 4)
        binp = bytes(self.bin) + b"\0" * ((4 - len(self.bin) % 4) % 4)
        with open(path, "wb") as fh:
            fh.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(binp)))
            fh.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
            fh.write(struct.pack("<II", len(binp), 0x004E4942) + binp)


# --- transforms -------------------------------------------------------------

def trs_matrix(node):
    m = np.eye(4)
    if "matrix" in node:
        return np.array(node["matrix"], dtype=float).reshape(4, 4).T
    t = node.get("translation", [0, 0, 0])
    x, y, z, w = node.get("rotation", [0, 0, 0, 1])
    s = node.get("scale", [1, 1, 1])
    r = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    m[:3, :3] = r * np.array(s)
    m[:3, 3] = t
    return m


def world_matrices(gltf):
    parent = {}
    for i, n in enumerate(gltf["nodes"]):
        for c in n.get("children", []):
            parent[c] = i
    cache = {}

    def world(i):
        if i not in cache:
            local = trs_matrix(gltf["nodes"][i])
            cache[i] = world(parent[i]) @ local if i in parent else local
        return cache[i]
    return [world(i) for i in range(len(gltf["nodes"]))]


# --- original surface samples -----------------------------------------------

def original_samples(gltf, binary, per_tri=10, seed=0):
    """Dense rest-pose surface samples: positions, UVs and the owning node index."""
    rng = np.random.default_rng(seed)
    worlds = world_matrices(gltf)
    pts, uvs, owners = [], [], []
    for ni, node in enumerate(gltf["nodes"]):
        if "mesh" not in node:
            continue
        prim = gltf["meshes"][node["mesh"]]["primitives"][0]
        pos = read_accessor(gltf, binary, prim["attributes"]["POSITION"]).astype(float)
        uv = read_accessor(gltf, binary, prim["attributes"]["TEXCOORD_0"]).astype(float)
        pos_w = (worlds[ni] @ np.c_[pos, np.ones(len(pos))].T).T[:, :3]
        tris = pos_w.reshape(-1, 3, 3)
        tuv = uv.reshape(-1, 3, 2)
        r = rng.random((len(tris), per_tri, 2))
        flip = r.sum(axis=2) > 1.0
        r[flip] = 1.0 - r[flip]
        a, b = r[..., 0:1], r[..., 1:2]
        c = 1.0 - a - b
        p = c * tris[:, None, 0] + a * tris[:, None, 1] + b * tris[:, None, 2]
        u = c * tuv[:, None, 0] + a * tuv[:, None, 1] + b * tuv[:, None, 2]
        pts.append(np.concatenate([p.reshape(-1, 3), tris.reshape(-1, 3)]))
        uvs.append(np.concatenate([u.reshape(-1, 2), tuv.reshape(-1, 2)]))
        owners.append(np.full(len(pts[-1]), ni))
    return np.concatenate(pts), np.concatenate(uvs), np.concatenate(owners)


# --- fitting ----------------------------------------------------------------

def yaw(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def chamfer(a, tree_b, b, tree_a=None, n=4000, rng=None):
    rng = rng or np.random.default_rng(0)
    ia = rng.choice(len(a), min(n, len(a)), replace=False)
    ib = rng.choice(len(b), min(n, len(b)), replace=False)
    d1 = tree_b.query(a[ia])[0].mean()
    d2 = (tree_a or cKDTree(a)).query(b[ib])[0].mean()
    return d1 + d2


def initial_fit(q, p):
    """Best yaw/mirror with bbox scale + placement; returns 3x4-ish (R, s, t) and score."""
    tree_p = cKDTree(p)
    hp = p[:, 1].max() - p[:, 1].min()
    best = None
    for mirror in (False, True):
        qm = q * np.array([-1.0 if mirror else 1.0, 1, 1])
        for deg in range(0, 360, 5):
            r = yaw(deg) @ np.diag([-1.0 if mirror else 1.0, 1, 1])
            qr = q @ r.T
            s = hp / (qr[:, 1].max() - qr[:, 1].min())
            qs = qr * s
            t = np.array([(p[:, 0].max() + p[:, 0].min()) / 2 - (qs[:, 0].max() + qs[:, 0].min()) / 2,
                          p[:, 1].min() - qs[:, 1].min(),
                          (p[:, 2].max() + p[:, 2].min()) / 2 - (qs[:, 2].max() + qs[:, 2].min()) / 2])
            score = chamfer(qs + t, tree_p, p)
            if best is None or score < best[0]:
                best = (score, r, s, t, deg, mirror)
    return best


def umeyama(src, dst):
    mu_s, mu_d = src.mean(0), dst.mean(0)
    xs, xd = src - mu_s, dst - mu_d
    cov = xd.T @ xs / len(src)
    u, d, vt = np.linalg.svd(cov)
    sgn = np.eye(3)
    if np.linalg.det(u) * np.linalg.det(vt) < 0:
        sgn[2, 2] = -1
    r = u @ sgn @ vt
    var = (xs ** 2).sum() / len(src)
    s = np.trace(np.diag(d) @ sgn) / var
    t = mu_d - s * r @ mu_s
    return r, s, t


def icp(q, p, iters=30, scale=False):
    """Rigid ICP (rotation + translation); scale only if asked. Free scale shrinks a
    mesh into the target, because nearest-point pairs always pull inward."""
    tree = cKDTree(p)
    cur = q.copy()
    total_r, total_s, total_t = np.eye(3), 1.0, np.zeros(3)
    for _ in range(iters):
        _, idx = tree.query(cur)
        r, s, t = umeyama(cur, p[idx])
        if not scale:
            s = 1.0
            t = p[idx].mean(0) - r @ cur.mean(0)
        cur = (s * (r @ cur.T)).T + t
        total_r, total_s, total_t = r @ total_r, s * total_s, s * (r @ total_t) + t
    return cur, (total_r, total_s, total_t)


# --- paint mask transfer ------------------------------------------------------

def transfer_paint(hd_pos, hd_uv, tris, samples, sample_uv, mask, res):
    """Rasterize the HD UV atlas; each texel takes the original mask colour at the nearest original surface point."""
    tree = cKDTree(samples)
    mw, mh = mask.size
    marr = purify(np.asarray(mask.convert("RGB").filter(ImageFilter.GaussianBlur(1.5))))
    out = np.zeros((res, res, 3), dtype=np.uint8)
    filled = np.zeros((res, res), dtype=bool)
    texel_pos, texel_xy = [], []
    for tri in tris:
        uv = hd_uv[tri] * res
        x0, y0 = np.floor(uv.min(0)).astype(int)
        x1, y1 = np.ceil(uv.max(0)).astype(int)
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, res - 1), min(y1, res - 1)
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        pts = np.c_[xs.ravel(), ys.ravel()]
        a, b, c = uv
        m = np.array([b - a, c - a]).T
        if abs(np.linalg.det(m)) < 1e-9:
            continue
        lam = np.linalg.solve(m, (pts - a).T).T
        inside = (lam[:, 0] >= -0.01) & (lam[:, 1] >= -0.01) & (lam.sum(1) <= 1.01)
        if not inside.any():
            continue
        lam = lam[inside]
        w = np.c_[1 - lam.sum(1), lam]
        texel_pos.append(w @ hd_pos[tri])
        texel_xy.append(pts[inside].astype(int))
    pos = np.concatenate(texel_pos)
    xy = np.concatenate(texel_xy)
    _, idx = tree.query(pos)
    suv = sample_uv[idx]
    px = np.clip((suv[:, 0] * mw).astype(int), 0, mw - 1)
    py = np.clip((suv[:, 1] * mh).astype(int), 0, mh - 1)
    out[xy[:, 1], xy[:, 0]] = marr[py, px]
    filled[xy[:, 1], xy[:, 0]] = True
    for _ in range(6):  # dilate into chart padding so mipmaps don't bleed black
        grow = ~filled & (np.roll(filled, 1, 0) | np.roll(filled, -1, 0) | np.roll(filled, 1, 1) | np.roll(filled, -1, 1))
        if not grow.any():
            break
        src = np.zeros_like(out)
        for sh, ax in ((1, 0), (-1, 0), (1, 1), (-1, 1)):
            nb = np.roll(filled, sh, ax)
            src = np.where((grow & nb)[..., None], np.roll(out, sh, ax), src)
        out[grow] = src[grow]
        filled |= grow
    return Image.fromarray(out)


def smooth_owners(owner, tris, n, iters=3):
    """Majority filter over each vertex's mesh neighbours. An isolated vertex bound to
    the wrong part (e.g. a foot vertex grabbed by the other leg) stretches its
    triangles into spikes once the joints move apart."""
    nbrs = [set() for _ in range(n)]
    for a, b, c in tris:
        nbrs[a].update((b, c))
        nbrs[b].update((a, c))
        nbrs[c].update((a, b))
    cur = owner.copy()
    for _ in range(iters):
        nxt = cur.copy()
        for v in range(n):
            if not nbrs[v]:
                continue
            vals, counts = np.unique(cur[list(nbrs[v])], return_counts=True)
            best = vals[counts.argmax()]
            if counts.max() > len(nbrs[v]) / 2 and best != cur[v]:
                nxt[v] = best
        cur = nxt
    changed = int((cur != owner).sum())
    print(f"skin smoothing reassigned {changed} of {n} vertices")
    return cur


def purify(arr):
    """After blurring, snap paint-dominated texels back to a pure channel so MechPaint
    still recolours them (it only touches pure red, green or blue)."""
    a = arr.astype(float)
    out = arr.copy()
    for ch in range(3):
        rest = np.delete(a, ch, axis=2).max(axis=2)
        dom = a[..., ch] - rest > 40.0  # paint channel clearly leads: blur mixed it with dark detail
        keep = np.zeros_like(a)
        keep[..., ch] = a[..., ch]
        out = np.where(dom[..., None], keep.astype(np.uint8), out)
    return out


def silhouette(pos, tris, yaw_deg, pitch_deg=6.0, res=192):
    """Orthographic silhouette as seen by the concept camera (model viewer: yaw 0 looks
    at the model's front, +yaw orbits clockwise), cropped to its bounding box."""
    y = math.radians(yaw_deg)
    p = math.radians(pitch_deg)
    back = np.array([math.sin(y) * math.cos(p), math.sin(p), math.cos(y) * math.cos(p)])  # camera at focus + back
    right = np.cross([0, 1, 0], back)
    right /= np.linalg.norm(right)
    up = np.cross(back, right)
    xy = np.c_[pos @ right, pos @ up]
    xy = (xy - xy.min(0)) / (xy.max(0) - xy.min(0)).max() * (res - 1)
    img = np.zeros((res, res), dtype=bool)
    for t in tris:
        a, b, c = xy[t]
        x0, y0 = np.floor(np.minimum(np.minimum(a, b), c)).astype(int)
        x1, y1 = np.ceil(np.maximum(np.maximum(a, b), c)).astype(int)
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
        pts = np.c_[xs.ravel(), ys.ravel()].astype(float)
        m = np.array([b - a, c - a]).T
        if abs(np.linalg.det(m)) < 1e-9:
            continue
        lam = np.linalg.solve(m, (pts - a).T).T
        ok = (lam[:, 0] >= 0) & (lam[:, 1] >= 0) & (lam.sum(1) <= 1)
        q = pts[ok].astype(int)
        img[res - 1 - q[:, 1], q[:, 0]] = True
    return _crop_mask(img, res)


def _crop_mask(mask, res):
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return np.zeros((res, res), dtype=bool)
    sub = Image.fromarray((mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1] * 255).astype(np.uint8))
    return np.asarray(sub.resize((res, res))) > 127


def concept_silhouette(path, res=192):
    a = np.asarray(Image.open(path).convert("L")) < 200
    return _crop_mask(a, res)


def iou(a, b):
    return (a & b).sum() / max((a | b).sum(), 1)


def vertex_normals(pos, tris):
    n = np.zeros_like(pos)
    fn = np.cross(pos[tris[:, 1]] - pos[tris[:, 0]], pos[tris[:, 2]] - pos[tris[:, 0]])
    for k in range(3):
        np.add.at(n, tris[:, k], fn)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    return n / np.where(ln > 0, ln, 1)


def png_bytes(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser()
    for a in ("original", "paint", "hd", "normal", "ao", "out", "out_paint"):
        ap.add_argument(a)
    ap.add_argument("--tex", type=int, default=1024)
    ap.add_argument("--concept", help="concept image: picks front vs back where the 3D fit is ambiguous")
    ap.add_argument("--concept-yaw", type=float, default=35.0)
    ap.add_argument("--turn", action="store_true", help="the fit landed backwards: turn the HD mesh 180 degrees")
    args = ap.parse_args()

    og, ob = load_glb(args.original)
    samples, sample_uv, owners = original_samples(og, ob)
    hg, hb = load_glb(args.hd)
    prim = hg["meshes"][0]["primitives"][0]
    q = read_accessor(hg, hb, prim["attributes"]["POSITION"]).astype(float)
    huv = read_accessor(hg, hb, prim["attributes"]["TEXCOORD_0"]).astype(float)
    tris = read_accessor(hg, hb, prim["indices"]).astype(np.int64).reshape(-1, 3)

    score, r0, s0, t0, deg, mirror = initial_fit(q, samples)
    print(f"initial fit: yaw {deg} mirror {mirror} scale {s0:.3f} chamfer {score:.3f} m")
    q0 = (s0 * (r0 @ q.T)).T + t0
    fitted, _ = icp(q0, samples)
    final = chamfer(fitted, cKDTree(samples), samples)
    print(f"after ICP: chamfer {final:.3f} m")
    if mirror:
        tris = tris[:, [0, 2, 1]]  # a mirror flips winding
    if args.concept:
        # Mechs are nearly front/back symmetric, so the 3D fit can land backwards. The concept
        # image shows the HD mesh's true front from the concept camera: keep the turn whose
        # silhouette matches it.
        ref = concept_silhouette(args.concept)
        c = fitted.mean(0)
        flipped = (fitted - c) @ yaw(180.0).T + c
        flipped, _ = icp(flipped, samples)
        keep_iou = iou(silhouette(fitted, tris, args.concept_yaw), ref)
        flip_iou = iou(silhouette(flipped, tris, args.concept_yaw), ref)
        print(f"orientation check vs concept: as fitted {keep_iou:.3f}, turned 180 {flip_iou:.3f}")
        # Diagnostic only: on real mechs this proved unreliable (it turned the Starslayer
        # the wrong way), so the decision is the explicit --turn flag, checked by eye.
    if args.turn:
        c = fitted.mean(0)
        fitted, _ = icp((fitted - c) @ yaw(180.0).T + c, samples)
        print("turned 180 degrees (--turn)")

    _, idx = cKDTree(samples).query(fitted)
    owner = smooth_owners(owners[idx], tris, len(fitted))
    joints = sorted(set(owner.tolist()))
    joint_slot = {n: i for i, n in enumerate(joints)}
    worlds = world_matrices(og)

    paint = transfer_paint(fitted, huv, tris, samples, sample_uv, Image.open(args.paint), args.tex)
    paint.save(args.out_paint)

    w = GlbWriter(og, ob)
    for node in og["nodes"]:
        node.pop("mesh", None)  # the original low-poly parts are replaced by the skinned HD mesh
    normals = vertex_normals(fitted, tris)
    attrs = {
        "POSITION": w.accessor(fitted, "VEC3", target=34962, minmax=True),
        "NORMAL": w.accessor(normals, "VEC3", target=34962),
        "TEXCOORD_0": w.accessor(huv, "VEC2", target=34962),
        "JOINTS_0": w.accessor(np.c_[[joint_slot[o] for o in owner], np.zeros((len(owner), 3))], "VEC4", comp=5123, target=34962),
        "WEIGHTS_0": w.accessor(np.c_[np.ones(len(owner)), np.zeros((len(owner), 3))], "VEC4", target=34962),
    }
    ind = w.accessor(tris.reshape(-1).astype(np.uint32), "SCALAR", comp=5125, target=34963)
    tex_paint = w.image(png_bytes(paint))
    tex_normal = w.image(open(args.normal, "rb").read())
    tex_ao = w.image(open(args.ao, "rb").read())
    og.setdefault("materials", []).append({
        "name": "hd", "pbrMetallicRoughness": {"baseColorTexture": {"index": tex_paint}, "metallicFactor": 0.35, "roughnessFactor": 0.55},
        "normalTexture": {"index": tex_normal}, "occlusionTexture": {"index": tex_ao}})
    og["meshes"].append({"name": "hd_body", "primitives": [{"attributes": attrs, "indices": ind, "material": len(og["materials"]) - 1}]})
    ibm = np.stack([np.linalg.inv(worlds[j]).T.reshape(-1) for j in joints])  # column-major MAT4
    og.setdefault("skins", []).append({"joints": joints, "inverseBindMatrices": w.accessor(ibm, "MAT4")})
    og["nodes"].append({"name": "hd_body", "mesh": len(og["meshes"]) - 1, "skin": len(og["skins"]) - 1})
    og["scenes"][0]["nodes"].append(len(og["nodes"]) - 1)
    w.write(args.out)
    print(f"wrote {args.out}: {len(fitted)} verts, {len(tris)} tris, {len(joints)} joints")


if __name__ == "__main__":
    main()
