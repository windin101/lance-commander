#!/usr/bin/env python3
"""Wreck art for v3 units: a destroyed variant built from the unit's own parts.   (LANCE-38 pilot)

    python3 -I tools/art/v3/wreck_mesh.py mechs atlas  [--out game/assets/v3/mechs/atlas_wreck.glb]
    python3 -I tools/art/v3/wreck_mesh.py vehicles hunter

Writes <name>_wreck.glb beside the model.  MechView._wreck swaps it in when it exists (else today's scorched freeze).
The wreck is STATIC and already posed:
  mechs     every part at the last frame of FallForward (the pose MechView freezes on), baked into world space;
  vehicles  the rest pose.
Then, per unit kind (recipes below), using only the model's own geometry, UVs and atlases:
  * a limb or the turret torn off and laid beside the hull;
  * armour blown open: the faces of a noisy-edged region are cut from the part, lifted off as a peeled, crumpled plate and
    the hole shows a dark interior frame (struts, a block, cables) built from boxes and tubes on a dark texel of the atlas;
  * dents (noise along the normals) on the big plates;
  * debris: real armour fragments (faces cut from near the blast, with their UVs) scattered on the ground;
  * burn: COLOR_0.r = 1 - burn per vertex (unit_v3.gdshader darkens and roughens by it) and COLOR_0.g = 0 on the interior frame (#3A2B22
    cable/rust with #FF7A2F ember emissive that cools over 90 s: style guide 2.4, 8.7, 9); wreck_smoke_N nodes mark the smoking wounds.
Seeded and deterministic (crc32 of the name): a rerun gives the same wreck.
"""
import argparse
import sys
import zlib
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools/art"))
import hd_rig as R  # noqa: E402
import pose_test as PT  # noqa: E402


# --------------------------------------------------------------------------------------------------- loading
class Part:
    def __init__(self, name, V, N, UV, F, burn=None, inter=None):
        self.name, self.V, self.N, self.UV, self.F = name, V, N, UV, F
        self.burn = np.zeros(len(V)) if burn is None else burn
        self.inter = np.zeros(len(V)) if inter is None else inter   # 1 = interior (cable / rust, ember glow), COLOR_0.g = 1 - inter

    def copy(self):
        return Part(self.name, self.V.copy(), self.N.copy(), self.UV.copy(), self.F.copy(), self.burn.copy(), self.inter.copy())

    def centroids(self):
        return self.V[self.F].mean(1)

    def face_normals(self):
        t = self.V[self.F]
        n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)

    def apply(self, M):
        self.V = self.V @ M[:3, :3].T + M[:3, 3]
        self.N = self.N @ M[:3, :3].T

    def recompute_normals(self):
        t = self.V[self.F]
        fn = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        n = np.zeros_like(self.V)
        for k in range(3):
            np.add.at(n, self.F[:, k], fn)
        self.N = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)


def load_posed(path, anim=None):
    g, b = R.load_glb(str(path))
    if anim:
        an = PT.Animator(g, b)
        W = an.world(anim, an.anims[anim][1])
    else:
        W = R.world_matrices(g)
    parts = {}
    for i, n in enumerate(g["nodes"]):
        if "mesh" not in n:
            continue
        pr = g["meshes"][n["mesh"]]["primitives"][0]
        V = R.read_accessor(g, b, pr["attributes"]["POSITION"]).astype(float)
        N = R.read_accessor(g, b, pr["attributes"]["NORMAL"]).astype(float)
        UV = R.read_accessor(g, b, pr["attributes"]["TEXCOORD_0"]).astype(float)
        F = R.read_accessor(g, b, pr["indices"]).reshape(-1, 3).astype(np.int64)
        p = Part(n["name"], V, N, UV, F)
        p.apply(np.array(W[i]))
        parts[n["name"]] = p
    return g, b, parts


SMOKE = []   # world points where the wreck keeps smoking (blown-open armour, the arm socket)


# --------------------------------------------------------------------------------------------------- helpers
def noise3(p, f=1.0, seed=0):
    """Cheap smooth 3D noise in [-1, 1] (sum of sines with seeded directions)."""
    rng = np.random.default_rng(seed)
    d = rng.normal(size=(6, 3)); d /= np.linalg.norm(d, axis=1, keepdims=True)
    ph = rng.uniform(0, 2 * np.pi, 6); fr = rng.uniform(0.8, 2.2, 6) * f
    return sum(np.sin((p @ d[k]) * fr[k] + ph[k]) for k in range(6)) / 3.0 * 0.5


def rot_axis(axis, ang):
    a = np.asarray(axis, float); a = a / np.linalg.norm(a)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(ang) * K + (1 - np.cos(ang)) * K @ K


def xform(R3, t=(0, 0, 0), about=(0, 0, 0)):
    M = np.eye(4); M[:3, :3] = R3
    M[:3, 3] = np.asarray(about) - R3 @ np.asarray(about) + np.asarray(t)
    return M


def dark_uv(png_albedo, png_orm=None):
    """A UV on a dark, unpainted texel of the atlas (bare metal) for the interior frame."""
    from PIL import Image
    a = np.asarray(Image.open(png_albedo).convert("RGBA"), float) / 255.0
    lum = a[..., :3].mean(2) + 2.0 * a[..., 3]          # alpha = painted: avoid it
    k = 24
    h, w = lum.shape
    m = lum[: h // k * k, : w // k * k].reshape(h // k, k, w // k, k).mean((1, 3))
    y, x = np.unravel_index(np.argmin(m), m.shape)
    return np.array([(x + 0.5) * k / w, (y + 0.5) * k / h])


def sub_part(p, face_mask, name):
    """The faces of p selected by face_mask as their own Part (unique vertices)."""
    f = p.F[face_mask]
    idx = np.unique(f); mp = -np.ones(len(p.V), int); mp[idx] = np.arange(len(idx))
    return Part(name, p.V[idx].copy(), p.N[idx].copy(), p.UV[idx].copy(), mp[f], p.burn[idx].copy(), p.inter[idx].copy())


def drop_faces(p, face_mask):
    """Remove faces (and the vertices only they used)."""
    f = p.F[~face_mask]
    idx = np.unique(f); mp = -np.ones(len(p.V), int); mp[idx] = np.arange(len(idx))
    p.V, p.N, p.UV, p.burn, p.inter, p.F = p.V[idx], p.N[idx], p.UV[idx], p.burn[idx], p.inter[idx], mp[f]


def merge(parts, name, uv=None):
    V, N, UV, F, B, I, o = [], [], [], [], [], [], 0
    for p in parts:
        V.append(p.V); N.append(p.N); UV.append(p.UV); B.append(p.burn); I.append(p.inter); F.append(p.F + o); o += len(p.V)
    return Part(name, np.concatenate(V), np.concatenate(N), np.concatenate(UV), np.concatenate(F), np.concatenate(B), np.concatenate(I))


def prim_box(c, half, R3, uv, burn=0.9):
    V = np.array([[sx, sy, sz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)], float) * half
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    P, F = [], []
    for q in quads:
        o = len(P); P += [V[i] for i in q]; F += [[o, o + 1, o + 2], [o, o + 2, o + 3]]
    P = np.array(P) @ R3.T + c
    p = Part("frame", P, np.zeros_like(P), np.tile(uv, (len(P), 1)), np.array(F), np.full(len(P), burn), np.ones(len(P)))
    p.recompute_normals(); return p


def prim_tube(a, b, r, uv, n=8, burn=0.9):
    a, b = np.asarray(a, float), np.asarray(b, float); ax = b - a; L = np.linalg.norm(ax); ax /= L
    u = np.cross(ax, [0, 1.0, 0]); u = u / np.linalg.norm(u) if np.linalg.norm(u) > 1e-6 else np.array([1.0, 0, 0]); v = np.cross(ax, u)
    t = np.arange(n) * 2 * np.pi / n
    ring = [r * (np.cos(k) * u + np.sin(k) * v) for k in t]
    P = np.array([a + q for q in ring] + [b + q for q in ring] + [a, b])
    F = []
    for j in range(n):
        k = (j + 1) % n
        F += [[j, n + j, k], [k, n + j, n + k], [2 * n, k, j], [2 * n + 1, n + j, n + k]]
    p = Part("frame", P, np.zeros_like(P), np.tile(uv, (len(P), 1)), np.array(F), np.full(len(P), burn), np.ones(len(P)))
    p.recompute_normals(); return p


# --------------------------------------------------------------------------------------------------- damage operations
def blow_open(p, centre, radius, up, seed, uv_dark, lift_deg=32.0, frame=True, depth=0.6):
    """Cut a noisy-edged region from part p (faces facing out, within the radius), peel it up as a plate, build the interior frame.
    Returns the list of extra Parts (plate, frame pieces)."""
    cen = p.centroids(); fn = p.face_normals()
    nz = noise3(cen, 1.3, seed)
    d = np.linalg.norm(cen - centre, axis=1)
    out = fn @ up > 0.15
    sel = (d < radius * (1.0 + 0.5 * nz)) & out
    if sel.sum() < 30:
        return []
    plate = sub_part(p, sel, p.name + "_plate")
    SMOKE.append(np.asarray(centre, float) + up * 0.3)
    drop_faces(p, sel)
    # burn the rim of the hole
    rim = np.exp(-(np.linalg.norm(p.V - centre, axis=1) / (radius * 1.5)) ** 2)
    p.burn = np.maximum(p.burn, np.clip(rim * 1.4, 0, 1))   # the rim goes to 1: embers (unit_v3.gdshader)
    # peel the plate: hinge at its rim point farthest back along a random tangent, tilt up and out, crumple
    n_mean = fn[sel].mean(0); n_mean /= np.linalg.norm(n_mean)
    rng = np.random.default_rng(seed + 7)
    t = np.cross(n_mean, rng.normal(size=3)); t /= np.linalg.norm(t)
    hinge = plate.V[np.argmin(plate.V @ np.cross(n_mean, t))]
    plate.apply(xform(rot_axis(t, np.radians(lift_deg)), t=n_mean * 0.12, about=hinge))
    plate.V += plate.N * (0.06 * noise3(plate.V, 3.0, seed + 11))[:, None]
    plate.recompute_normals()
    plate.burn = np.clip(plate.burn + 0.45, 0, 0.9)
    extra = [plate]
    if frame:
        base = centre - n_mean * depth
        T = t; B = np.cross(n_mean, T)
        R3 = np.stack([T, n_mean, B], 1)
        for k in (-1, 0, 1):                       # ribs across the hole
            extra.append(prim_tube(base + T * (k * radius * 0.55) - B * radius * 0.9, base + T * (k * radius * 0.55) + B * radius * 0.9, 0.06, uv_dark, burn=0.95))
        extra.append(prim_tube(base - T * radius * 0.9 + B * 0.1, base + T * radius * 0.9 - B * 0.15, 0.09, uv_dark, burn=0.95))
        extra.append(prim_box(base - n_mean * 0.1 + T * radius * 0.2, np.array([radius * 0.28, radius * 0.18, radius * 0.22]), R3, uv_dark, 0.95))
        extra.append(prim_box(base - n_mean * 0.05, np.array([radius * 0.95, 0.03, radius * 0.95]), R3, uv_dark, 0.95))   # the glowing bed of the breach
        for k in range(3):                         # cables hanging out of the hole
            a = base + T * rng.uniform(-0.4, 0.4) * radius + B * rng.uniform(-0.3, 0.3) * radius
            b = a + n_mean * rng.uniform(0.3, 0.7) * radius + T * rng.uniform(-0.5, 0.5) * radius
            extra.append(prim_tube(a, b, 0.03, uv_dark, 6, 1.0))
    return extra


def dent(p, amp, freq, seed, mask=None):
    n = noise3(p.V, freq, seed) * amp
    if mask is not None:
        n = n * mask
    p.V = p.V + p.N * n[:, None]
    p.recompute_normals()


def debris_from(parts, centre, radius, count, seed, ground_y=0.0, ring=(2.5, 7.0), keep_away=None, rscale=1.0):
    """Armour fragments: patches of real surface cut from the parts near `centre` and thrown onto the ground."""
    rng = np.random.default_rng(seed)
    out = []
    pool = [p for p in parts if len(p.F)]
    for k in range(count):
        p = pool[rng.integers(len(pool))]
        cen = p.centroids()
        d = np.linalg.norm(cen - centre, axis=1)
        cand = np.flatnonzero(d < radius)
        if len(cand) < 50:
            continue
        c = cen[rng.choice(cand)]
        r = rng.uniform(0.22, 0.5) * rscale
        sel = np.linalg.norm(cen - c, axis=1) < r
        if sel.sum() < 6:
            continue
        frag = sub_part(p, sel, "debris")
        drop_faces(p, sel)
        ang = rng.uniform(0, 2 * np.pi); dist = rng.uniform(*ring)
        target = np.array([centre[0] + np.cos(ang) * dist, ground_y, centre[2] + np.sin(ang) * dist])
        cc = frag.V.mean(0)
        tilt = rot_axis(rng.normal(size=3), rng.uniform(0, 1.0))
        spin = rot_axis([0, 1, 0], rng.uniform(0, 6.28))
        frag.apply(xform(spin @ tilt, t=target - cc, about=cc))
        frag.V[:, 1] += ground_y + 0.04 - frag.V[:, 1].min()
        frag.burn = np.clip(frag.burn + rng.uniform(0.3, 0.6), 0, 0.9)
        frag.recompute_normals()
        out.append(frag)
    return out


def burn_field(parts, centres, radius, base=0.22, seed=0):
    for p in parts:
        b = np.full(len(p.V), base)
        for c in centres:
            b = np.maximum(b, np.exp(-(np.linalg.norm(p.V - c, axis=1) / radius) ** 2))
        b += 0.18 * noise3(p.V, 2.0, seed)
        p.burn = np.clip(np.maximum(p.burn, b), 0, 1) if p.name not in ("debris",) and not p.name.endswith("_plate") else np.minimum(np.maximum(p.burn, b), 0.9)


# --------------------------------------------------------------------------------------------------- recipes
def pick_sites(parts, exclude, n, min_sep, seed, ground_y):
    """Breach sites on surfaces the RTS camera sees (facing up, above the ground): (part, centre) pairs, area-weighted, spread out."""
    rng = np.random.default_rng(seed)
    cands = []
    for name, p in parts.items():
        if name in exclude or len(p.F) == 0:
            continue
        fn = p.face_normals(); cen = p.centroids()
        t = p.V[p.F]; area = 0.5 * np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1)
        ok = (fn[:, 1] > 0.45) & (cen[:, 1] > ground_y + 0.6)
        if ok.sum() < 40:
            continue
        cands.append((name, cen[ok], area[ok]))
    if not cands:
        return []
    names = [c[0] for c in cands]
    w = np.array([c[2].sum() for c in cands])
    out = []
    for _ in range(n * 12):
        if len(out) >= n:
            break
        k = rng.choice(len(cands), p=w / w.sum())
        cen, area = cands[k][1], cands[k][2]
        c = cen[rng.choice(len(cen), p=area / area.sum())]
        if all(np.linalg.norm(c - o[1]) > min_sep for o in out):
            out.append((names[k], c))
    return out


def unit_scale(parts):
    V = np.concatenate([p.V for p in parts.values()])
    return float(np.linalg.norm(V.max(0) - V.min(0)) / 14.0), float(V[:, 1].min())


def recipe_mech(parts, uv_dark, seed, chain, torso, shoulder_hint=None):
    """chain: part names of the limb to tear off (shoulder first); torso: the big upper-body part."""
    up = np.array([0, 1.0, 0])
    sc, ground = unit_scale(parts)
    T = parts[torso]
    hull_c = T.V.mean(0)
    extra = []
    wounds = []
    # 1. the limb: laid on the ground away from the hull
    arm = [parts[n] for n in chain]
    if arm:
        ac = np.concatenate([p.V for p in arm]).mean(0)
        d = ac - hull_c; d[1] = 0; d = d / max(np.linalg.norm(d), 1e-6)
        M = xform(rot_axis([0, 1, 0], np.radians(35)) @ rot_axis(d, np.radians(25)), t=hull_c + d * 7.0 * sc - ac, about=ac)
        for p in arm:
            p.apply(M)
        ymin = min(p.V[:, 1].min() for p in arm)
        for p in arm:
            p.V[:, 1] += ground + 0.05 - ymin
            p.burn = np.clip(p.burn + 0.6, 0, 1)
            dent(p, 0.05 * sc, 2.0, seed + 3)
        if shoulder_hint is not None:   # 2. the smoking socket
            n = (shoulder_hint - hull_c) / max(np.linalg.norm(shoulder_hint - hull_c), 1e-6)
            extra += blow_open(T, shoulder_hint, 1.25 * sc, n, seed + 1, uv_dark, 40.0, depth=0.6 * sc)
            wounds.append(shoulder_hint)
    # 3. several large breaches on the surfaces the RTS camera sees
    sites = pick_sites(parts, set(chain), 5, 2.4 * sc, seed + 2, ground)
    rng = np.random.default_rng(seed + 4)
    for k, (nm, c) in enumerate(sites):
        r = rng.uniform(1.3, 2.1) * sc * (1.15 if nm == torso else 0.8)
        extra += blow_open(parts[nm], c, r, up, seed + 20 + k, uv_dark, rng.uniform(25, 45), depth=0.55 * r)
        wounds.append(c)
    # 4. dents on the big plates
    for n_, p in parts.items():
        if n_ not in chain:
            dent(p, 0.04 * sc, 1.6, seed + 5)
    # 5. debris: a wide spread
    extra += debris_from([p for n_, p in parts.items() if n_ not in chain], wounds[-1] if wounds else hull_c, 4.5 * sc, 18, seed + 9,
                         ground_y=ground, ring=(2.5 * sc, 11.0 * sc))
    burn_field(list(parts.values()) + extra, wounds, 3.4 * sc, 0.6, seed)
    return extra


def recipe_vehicle(parts, uv_dark, seed, hull, turret, tracks, wheels, detach=(), weapons=()):
    """A vehicle blown apart: the turret (or, with none, the cab: the front third of the hull) thrown several metres and turned over,
    the hull listing nose-down, a large breach in its roof with the roof peeled up over an interior frame, a track thrown out or
    wheels knocked off and scattered, a wide debris field.  Burn stays moderate so the paint still shows (scorched, not black)."""
    up = np.array([0, 1.0, 0])
    sc, ground = unit_scale(parts)
    rng = np.random.default_rng(seed)
    H = parts[hull]
    ext = H.V.max(0) - H.V.min(0)
    lax = 0 if ext[0] > ext[2] else 2          # the long horizontal axis
    wax = 2 - lax
    length, width = float(ext[lax]), float(ext[wax])
    hull_c = H.V.mean(0)
    fwd = np.zeros(3); fwd[lax] = 1.0            # "front" = the + end of the long axis
    lat = np.zeros(3); lat[wax] = 1.0
    extra = []
    thrown_names = set(detach) | set(weapons) | ({turret} if turret else set())
    thrown = [parts[n] for n in thrown_names if n in parts]
    if not turret:                              # no turret: the cab / front superstructure goes
        c = H.centroids()[:, lax]
        mask = c > H.V[:, lax].min() + 0.62 * length
        cab = sub_part(H, mask, hull + "_cab")
        drop_faces(H, mask)
        cab.burn = cab.burn + 0.3
        parts[hull + "_cab"] = cab
        thrown = [cab] + thrown
    # 1. nose-down list of the body (hull, wheels, tracks stay together)
    body = [p for n, p in parts.items() if p not in thrown]
    M = xform(rot_axis(lat, np.radians(-9 * (1 if lax == 0 else -1) * 1.0)) @ rot_axis(fwd, np.radians(rng.choice([-1, 1]) * 5)), about=hull_c)
    for p in body:
        p.apply(M)
    ymin = min(p.V[:, 1].min() for p in body)
    for p in body:
        p.V[:, 1] += ground - ymin
    hull_c = H.V.mean(0)
    # 2. the thrown group: turret + guns / cab: several metres out, turned over
    gc = np.concatenate([p.V for p in thrown]).mean(0) if thrown else hull_c
    ang = rng.uniform(0, 2 * np.pi)
    dist = length * 0.7 + 4.0 * sc
    sd = np.zeros(3); sd[lax] = np.cos(ang) * 0.7; sd[wax] = np.sin(ang) * np.sign(np.sin(ang) or 1.0); sd /= np.linalg.norm(sd)
    flip = rot_axis(np.cross(up, sd), np.radians(rng.uniform(140, 175) if turret else rng.uniform(70, 110))) @ rot_axis(up, rng.uniform(0, 6.28))
    T = xform(flip, t=hull_c + sd * dist - gc, about=gc)
    for p in thrown:
        p.apply(T)
    if thrown:
        ym = min(p.V[:, 1].min() for p in thrown)
        for p in thrown:
            p.V[:, 1] += ground + 0.05 - ym
            p.burn = np.clip(p.burn + 0.35, 0, 0.8)
            dent(p, 0.06 * sc, 1.5, seed + 3)
    # 3. a large breach through the roof (peeled up), plus two more on the deck
    wounds = []
    sites = pick_sites({hull: H}, set(), 3, 0.45 * width, seed + 2, ground)
    for k, (nm, c) in enumerate(sites):
        r = (rng.uniform(0.30, 0.40) if k == 0 else rng.uniform(0.18, 0.26)) * width
        extra += blow_open(H, c, r, up, seed + 20 + k, uv_dark, rng.uniform(45, 60) if k == 0 else rng.uniform(30, 45), depth=0.6 * r)
        wounds.append(c)
    dent(H, 0.05 * sc, 1.4, seed + 5)
    # 4. tracks thrown out, or wheels knocked off and scattered
    tn = [n for n in tracks if n in parts]
    for k, n in enumerate(tn):
        tr = parts[n]
        c = tr.V.mean(0); sd2 = np.sign(c[wax] - hull_c[wax]) or 1.0
        out = lat * sd2
        a2 = 28 if k == 0 else 10
        tr.apply(xform(rot_axis(fwd, np.radians(a2 * sd2)), t=out * (width * (0.9 if k == 0 else 0.25)) + fwd * rng.uniform(-1, 1) * length * 0.2, about=c))
        tr.V[:, 1] += ground + 0.03 - tr.V[:, 1].min()
        tr.V += tr.N * (0.12 * sc * noise3(tr.V, 1.0, seed + 8))[:, None]; tr.recompute_normals()
        tr.burn = np.clip(tr.burn + 0.4, 0, 0.8)
    wn = [w for w in wheels if w in parts]
    for k, n in enumerate(wn):
        if k % 2 == 0 or not tn:
            w = parts[n]; c = w.V.mean(0)
            far = rng.uniform(0.6, 1.6) * length
            ang3 = rng.uniform(0, 6.28)
            w.apply(xform(rot_axis(rng.normal(size=3), rng.uniform(0.4, 1.4)), t=np.array([np.cos(ang3) * far, 0, np.sin(ang3) * far]), about=c))
            w.V[:, 1] += ground + 0.03 - w.V[:, 1].min()
            w.burn = np.clip(w.burn + 0.3, 0, 0.8)
    # 5. a wide debris field
    extra += debris_from([H] + ([parts[hull + "_cab"]] if not turret else []), wounds[0] if wounds else hull_c, 0.8 * length, 28, seed + 9,
                         ground_y=ground, ring=(0.5 * length, 2.4 * length), rscale=max(1.0, 0.9 * sc))
    burn_field([p for p in parts.values()] + extra, wounds, 0.35 * length, 0.28, seed)
    return extra


# --------------------------------------------------------------------------------------------------- part-name config
import re

# Auto-detection covers the naming of the 30 mechs and 26 vehicles; CONFIG overrides per unit.
#   mechs:    chain = parts torn off (shoulder first), torso = the upper body part (the one that takes the breaches' anchor)
#   vehicles: hull, turret (None: no turret), detach (other parts thrown: radars)
CONFIG = {
    "flea": {"chain": ["fl_rlleg", "fl_rfoot"], "torso": "fl_torso"},            # no arms: a lower leg goes instead
    "heavycopter": {"chain": ["HC_Rotor"], "torso": "HC_hip"},                    # rotors torn off
    "mediumcopter": {"chain": ["Rotors"], "torso": "MediumCopter"},
    "werewolf": {"chain": ["ww_rarm"], "torso": "ww_torso"},
    "aerospotter": {"hull": "AeroSpotter", "turret": None, "detach": ["radar"]},
    "mobilehq": {"hull": "HQ_Body", "turret": None, "detach": ["hq_radar", "hq_radarstand"]},
    "drillson": {"hull": "LRMHover", "turret": "TF_Turret"},
}


def plan_mech(name, names):
    c = CONFIG.get(name, {})
    torso = c.get("torso") or next((n for n in names if re.search(r"torso2?$", n, re.I)), None) or names[0]
    if "chain" in c:
        return c["chain"], torso
    chain = [n for n in names if re.search(r"_r(u|l)?(arm|gun|missile)$", n) and "shoulder" not in n]
    if not chain:
        chain = [n for n in names if re.search(r"_rlleg$|_rfoot$", n)]
    # shoulder first: the highest part
    return chain, torso


def plan_vehicle(name, names, parts):
    c = CONFIG.get(name, {})
    tracks = [n for n in names if n.startswith("track")]
    wheels = [n for n in names if n.startswith("wheel_")]
    turret = c["turret"] if "turret" in c else next((n for n in names if re.search(r"turret", n, re.I)), None)
    hull = c.get("hull") or max((n for n in names if n != turret and n not in tracks and n not in wheels and n not in c.get("detach", [])
                                 and not re.search(r"gun|pack|pods|radar", n, re.I)), key=lambda n: len(parts[n].F))
    weapons = [n for n in names if n not in (hull, turret) and n not in tracks and n not in wheels and re.search(r"gun|pack|pods|launcher|missile|barrel", n, re.I)]
    return hull, turret, tracks, wheels, c.get("detach", []), weapons


# --------------------------------------------------------------------------------------------------- writing
def write_glb(g, parts, out):
    gl = {"asset": {"version": "2.0", "generator": "tools/art/v3/wreck_mesh.py"}, "scene": 0, "scenes": [{"nodes": []}], "nodes": [],
          "meshes": [], "materials": g["materials"], "accessors": [], "bufferViews": []}
    w = R.GlbWriter(gl, bytearray())
    for p in parts:
        if len(p.F) == 0:
            continue
        col = np.c_[1.0 - np.clip(p.burn, 0, 1), 1.0 - np.clip(p.inter, 0, 1), np.ones(len(p.V)), np.ones(len(p.V))]
        prim = {"attributes": {"POSITION": w.accessor(p.V, "VEC3", 5126, 34962, True), "NORMAL": w.accessor(p.N, "VEC3", 5126, 34962),
                               "TEXCOORD_0": w.accessor(p.UV, "VEC2", 5126, 34962), "COLOR_0": w.accessor(col, "VEC4", 5126, 34962)},
                "indices": w.accessor(p.F.astype(np.uint32).ravel(), "SCALAR", 5125, 34963), "material": 0}
        gl["meshes"].append({"primitives": [prim]})
        gl["nodes"].append({"name": ("wrecked_" + p.name) if p.name.startswith(("wheel_", "track_")) else p.name, "mesh": len(gl["meshes"]) - 1})   # baked, not rigged: keep the rig finders and the wheel-centre test off them
        gl["scenes"][0]["nodes"].append(len(gl["nodes"]) - 1)
    for k, pt in enumerate(SMOKE):   # empty nodes: MechView puts the smoke emitters here
        gl["nodes"].append({"name": f"wreck_smoke_{k}", "translation": [float(x) for x in pt]})
        gl["scenes"][0]["nodes"].append(len(gl["nodes"]) - 1)
    w.write(str(out))


def check(allp, parts, extra, thrown=()):
    """Floating / buried / piercing checks on the finished wreck (printed; a line starting WARN needs a look)."""
    from scipy.spatial import cKDTree
    V = np.concatenate([p.V for p in allp if len(p.V)])
    lo = V[:, 1].min()
    bad = []
    body = [p for p in parts.values()]
    for p in extra:
        if p.name == "debris" and len(p.V) and p.V[:, 1].min() > lo + 0.5:
            bad.append("debris floats %.2f m" % (p.V[:, 1].min() - lo))
    big = max(body, key=lambda p: len(p.F))
    tree = cKDTree(big.V)
    for p in body:
        if p is big or not len(p.V) or p.name not in thrown:   # the fallen pose itself is the animation's; only what we threw is checked
            continue
        d = tree.query(p.V[::20])[0].min()
        if d > 0.0 and p.V[:, 1].min() > lo + 0.6 and d > 1.5:
            bad.append("%s floats %.2f m above ground, %.1f m from the hull" % (p.name, p.V[:, 1].min() - lo, d))
    print("check: lowest y %.3f (the pose's own), %d meshes, %s" % (lo, len(allp), ("WARN " + "; ".join(bad)) if bad else "ok (nothing floating)"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", choices=("mechs", "vehicles"))
    ap.add_argument("name")
    ap.add_argument("--out")
    a = ap.parse_args()
    d = ROOT / "game/assets/v3" / a.folder
    seed = zlib.crc32(a.name.encode())
    SMOKE.clear()
    anim = "FallForward" if a.folder == "mechs" else None
    g, b, parts = load_posed(d / f"{a.name}.glb", anim)
    uv_dark = dark_uv(d / f"{a.name}_albedo.png")
    names = list(parts)
    print("dark texel uv", uv_dark.round(3), "parts", len(parts), sum(len(p.F) for p in parts.values()), "tris")
    if a.folder == "mechs":
        chain, torso = plan_mech(a.name, names)
        chain = sorted(chain, key=lambda n: -parts[n].V[:, 1].max())
        print("chain", chain, "torso", torso)
        sh = None
        if chain:
            top = parts[chain[0]].V[np.argmax(parts[chain[0]].V[:, 1])]
            sh = parts[torso].V[np.argmin(np.linalg.norm(parts[torso].V - top, axis=1))]
        extra = recipe_mech(parts, uv_dark, seed, chain, torso, sh)
    else:
        hull, turret, tracks, wheels, detach, weapons = plan_vehicle(a.name, names, parts)
        print("hull", hull, "turret", turret, "tracks", len(tracks), "wheels", len(wheels), "detach", detach, "weapons", weapons)
        extra = recipe_vehicle(parts, uv_dark, seed, hull, turret, tracks, wheels, detach, weapons)
    out = Path(a.out) if a.out else d / f"{a.name}_wreck.glb"
    allp = list(parts.values()) + extra
    check(allp, parts, extra, tuple(chain) if a.folder == "mechs" else tuple(([turret] if turret else [hull + "_cab"]) + list(detach)))
    write_glb(g, allp, out)
    print("wrote", out, len(allp), "meshes", sum(len(p.F) for p in allp), "tris")


if __name__ == "__main__":
    main()
