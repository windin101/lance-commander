#!/usr/bin/env python3
"""v3 rusted and crashed lifeboats, rebuilt from the approved X-38 CRV sculpt (LANCE-39, 2026-11-01).

lifeboat_hd.glb (game/assets/objects, the sculpt the intact lifeboat uses) is "NASA's X-38 CRV" by cryptojones, CC BY 4.0
(https://www.thingiverse.com/thing:3453862); see its row in docs/art-provenance.md and lifeboat_hd.LICENSE.md. This script reads that glb's hd_body
mesh back, welds it, and re-poses it as two weathered members. Nothing else is taken from the sculpt: the paint is the project's own `boatrust` set
plus a baked vertex rust/grime/burn layer, the interior, ribs and debris are new geometry.

lifeboatrusted   the same hull tipped onto one wing (roll + yaw + a sagging nose), faded paint, rust and grime baked on the vertices.
lifeboatcrashed  the hull nose-down in the ground (crumpled nose), one wing sheared off and lying beside it, the dorsal skin torn open over a dark interior with
                 bent ribs; baked char at the tear, the nose and the ground line (the burn language of bld_crash.py).
Both: damaged = more burn, bent beams and scorch patches; destroyed = a charred slab with the hull cut into flattened chunks. LOD1 is the sculpt clustered
(vertex clustering on a grid); LOD0 is the sculpt itself. UVs are planar metres on the sculpt's own (un-posed) frame, split by dominant normal axis, so the
paint stays attached to the hull.

    python3 -I tools/art/v3/bld_lifeboat.py lifeboatrusted|lifeboatcrashed|all
"""
import argparse
import json
import math
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bld_hangars as H  # noqa: E402
from bld_industry import V, TAU, ROOT  # noqa: E402
from bld_kit import Ctx, axis_angle  # noqa: E402
from bld_mesh import unit  # noqa: E402

SCULPT = ROOT / "game/assets/objects/lifeboat_hd.glb"
MASK = ROOT / "game/assets/objects/lifeboat_hd_1.png"
HULL = "boatrust"
AX, AY, AZ = V([1.0, 0, 0]), V([0, 1.0, 0]), V([0, 0, 1.0])


# ------------------------------------------------------------------------------------------------------------------ the sculpt
class Soup:
    """A welded triangle soup: V world positions, L local (sculpt-frame) positions for UV, N smooth normals, T triangles, K per-triangle class."""

    def __init__(self, V_, L, N, T, K):
        self.V, self.L, self.N, self.T, self.K = V_, L, N, T, K

    def sub(self, tri_mask):
        T = self.T[tri_mask]
        used, inv = np.unique(T, return_inverse=True)
        return Soup(self.V[used], self.L[used], self.N[used], inv.reshape(-1, 3), self.K[tri_mask])

    def centroids(self, local=True):
        return (self.L if local else self.V)[self.T].mean(1)

    def xform(self, R, t):
        self.V = self.V @ R.T + t
        self.N = unit(self.N @ R.T)
        return self

    def copy(self):
        return Soup(self.V.copy(), self.L.copy(), self.N.copy(), self.T.copy(), self.K.copy())


def _glb_mesh(path, mesh_name):
    d = Path(path).read_bytes()
    jl = struct.unpack("<I", d[12:16])[0]
    j = json.loads(d[20:20 + jl])
    bl = struct.unpack("<I", d[20 + jl:24 + jl])[0]
    b = d[28 + jl:28 + jl + bl]

    def acc(i):
        a = j["accessors"][i]
        bv = j["bufferViews"][a["bufferView"]]
        nc = {"VEC3": 3, "VEC2": 2, "SCALAR": 1}[a["type"]]
        dt = {5126: "<f4", 5125: "<u4", 5123: "<u2"}[a["componentType"]]
        return np.frombuffer(b, dt, a["count"] * nc, bv.get("byteOffset", 0)).reshape(a["count"], nc)
    m = next(m for m in j["meshes"] if m["name"] == mesh_name)["primitives"][0]
    at = m["attributes"]
    return acc(at["POSITION"]).astype(float), acc(at["NORMAL"]).astype(float), acc(at["TEXCOORD_0"]).astype(float), acc(m["indices"]).reshape(-1, 3).astype(int)


_CACHE = {}


def load_sculpt():
    """The X-38 hull as a Soup in its own frame (x +-2.3, y 0..1.85, z -2.1..3.2, nose +z). Classes: 0 yellow hull, 1 dark (canopy glass, gear), 2 tan nose strip."""
    if "s" in _CACHE:
        return _CACHE["s"].copy()
    P, N, U, I = _glb_mesh(SCULPT, "hd_body")
    pal = np.asarray(Image.open(MASK).convert("RGB"))
    px = pal[np.clip((U[:, 1] * 64).astype(int), 0, 63), np.clip((U[:, 0] * 64).astype(int), 0, 63)].astype(int)
    vc = np.zeros(len(P), int)
    vc[(np.abs(px - [43, 42, 33]).sum(1) < 6)] = 1
    vc[(np.abs(px - [186, 172, 124]).sum(1) < 6)] = 2
    q = np.round(P * 1e4).astype(np.int64)
    _, first, inv = np.unique(q, axis=0, return_index=True, return_inverse=True)
    inv = inv.reshape(-1)
    Pw = P[first]
    Nw = np.zeros_like(Pw)
    np.add.at(Nw, inv, N)
    T = inv[I]
    K = np.zeros(len(T), int)
    c = vc[I]
    K[(c == 1).sum(1) >= 2] = 1
    K[(c == 2).sum(1) >= 2] = 2
    ok = (T[:, 0] != T[:, 1]) & (T[:, 1] != T[:, 2]) & (T[:, 0] != T[:, 2])
    s = Soup(Pw, Pw.copy(), unit(Nw), T[ok], K[ok])
    _CACHE["s"] = s
    return s.copy()


def cluster(s, cell):
    """Vertex clustering on a grid (the LOD1 and wreck meshes). Class stays per triangle; degenerate and duplicate triangles are dropped."""
    key = np.floor(s.L / cell).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    n = inv.max() + 1
    cnt = np.bincount(inv, minlength=n).astype(float)[:, None]
    out = []
    for A in (s.V, s.L, s.N):
        a = np.zeros((n, 3))
        np.add.at(a, inv, A)
        out.append(a / cnt)
    T = inv[s.T]
    ok = (T[:, 0] != T[:, 1]) & (T[:, 1] != T[:, 2]) & (T[:, 0] != T[:, 2])
    T, K = T[ok], s.K[ok]
    srt = np.sort(T, axis=1)
    _, u = np.unique(srt, axis=0, return_index=True)
    u = np.sort(u)
    r = Soup(out[0], out[1], unit(out[2]), T[u], K[u])
    return r.sub(np.ones(len(r.T), bool))


def noise(P, f, ph=0.0):
    """Cheap smooth 0..1 value noise from sine products (pose-independent, deterministic)."""
    x, y, z = P[:, 0] * f, P[:, 1] * f * 1.13, P[:, 2] * f * 0.91
    return 0.5 + 0.5 * np.sin(x + ph) * np.sin(y * 1.3 - z + 2.0 * ph) * np.cos(z * 0.9 + x * 0.4 + 1.7 * ph)


# ------------------------------------------------------------------------------------------------------------------ emission
def emit(c, s, mats, col=None, rust=0.0, seed=0.0):
    """Add a Soup to the Ctx builder: one material per class, planar-metre UVs from the local frame (dominant normal axis), baked rust/grime in COLOR_0.g.
    mats: {class: material}. rust 0..1 scales the grime patches; col an optional extra (n,3) per-vertex colour for the soup's vertices."""
    for k, mat in mats.items():
        t = s.T[s.K == k]
        if not len(t):
            continue
        fn = np.cross(s.L[t[:, 1]] - s.L[t[:, 0]], s.L[t[:, 2]] - s.L[t[:, 0]])
        ax = np.argmax(np.abs(fn), axis=1)
        key = np.stack([t.reshape(-1), np.repeat(ax, 3)], 1)
        uk, inv = np.unique(key, axis=0, return_inverse=True)
        inv = inv.reshape(-1, 3)
        vi, va = uk[:, 0], uk[:, 1]
        P, N, L = s.V[vi], s.N[vi], s.L[vi]
        u = np.where(va == 0, L[:, 1], L[:, 0])
        v = np.where(va == 2, L[:, 1], L[:, 2])
        U = np.stack([u, v], 1)
        cc = np.zeros((len(vi), 3)) if col is None else col[vi]
        if rust > 0 and k != 1:
            cc[:, 1] = np.maximum(cc[:, 1], _grime(P, N, rust, seed))
        c.b.add(mat, P, N, U, inv, 0, cc)


def _grime(P, N, k, seed):
    """Rust and run-off baked into vertex G: broad patches, small blotches, heavier on the underside and low on the hull, never uniform."""
    st = np.array([1.5, 2.2, 0.55])                                       # stretched along the hull: run-off streaks, not spots
    big = np.clip((noise(P * st, 1.0, seed) - 0.3) * 2.0, 0, 1)
    small = np.clip((noise(P * st * 2.7, 1.0, seed + 1.0) - 0.45) * 1.2, 0, 1)
    low = np.clip(1.0 - P[:, 1] / 2.6, 0, 1)
    under = np.clip(-N[:, 1], 0, 1)
    g = k * (0.12 + 0.42 * big + 0.12 * small + 0.25 * low + 0.3 * under)
    return np.clip(g, 0, 0.8)


def burn_fn(c, ends, ground=0.5, gh=1.2, base=0.05):
    """The wreck's baked burn (same shape as bld_crash._wreck_burn): strongest at each hurt point (x, y, z, radius, strength) and along the ground line."""
    boost = 0.3 if c.state == "damaged" else 0.0

    def f(P):
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        nz = 0.62 + 0.38 * np.sin(x * 0.9 + z * 0.5) * np.sin(z * 1.1 - y * 0.8 + 1.3)
        b = ground * np.exp(-np.clip(y, 0, None) / gh)
        for (ex, ey, ez, r, a) in ends:
            d = np.sqrt((x - ex) ** 2 + (y - ey) ** 2 + (z - ez) ** 2)
            b = np.maximum(b, a * np.exp(-(d / r) ** 2))
        return np.clip(b * nz + boost * np.exp(-np.clip(y, 0, None) / 4.0) + base, 0, 1)
    c.b.colfn = f


def pose(R, shift, s0, min_y):
    """R about the origin then a shift in x/z and a lift so the lowest vertex sits at min_y. Returns (R, t)."""
    p = s0.V @ R.T
    t = np.array([shift[0], min_y - p[:, 1].min(), shift[1]])
    return R, t


def _lay_flat(P):
    """Rotation that turns the chunk's thinnest principal axis to vertical (a torn sheet lies on the ground, not on its edge)."""
    u, sv, vt = np.linalg.svd(P - P.mean(0), full_matrices=False)
    n = vt[-1] if vt[-1][1] >= 0 else -vt[-1]
    v = np.cross(n, AY)
    sn, cs = np.linalg.norm(v), float(np.dot(n, AY))
    if sn < 1e-6:
        return np.eye(3)
    return axis_angle(v / sn, math.atan2(sn, cs))


def _gear_drop(s, down=0.0):
    """Sculpt gear (wheels in class 1, the nose strut in the tan class 2) lies below the belly; return a mask of its triangles."""
    cen = s.centroids()
    return ((s.K == 1) | (s.K == 2)) & (cen[:, 1] < 0.45)


# ------------------------------------------------------------------------------------------------------------------ members
def lifeboatrusted(state, lod, seed):
    """x -1.8..2.7, y -0.1..2.3, z -2.4..2.9 (the original's extents): the hull rolled onto its left wing, nose sagging, faded and rusted."""
    c = Ctx(state, lod, seed, breach=(0.5, 1.2, 0.0, 1.4), ledges=[(1.2, 0.5, 0.6)], ground_h=1.5)
    if state == "destroyed":
        return _wreck(c, "boatrust", dx=0.4, tilt=0.5)
    s0 = load_sculpt()
    R = axis_angle(AY, -0.35) @ axis_angle(AX, 0.07) @ axis_angle(AZ, 0.42)
    s0 = s0.sub(~_gear_drop(s0))                                         # gear collapsed under the hull: no wheels or strut left standing
    R, t = pose(R, (0.45, 0.2), s0, -0.06)
    if c.state == "damaged":
        burn_fn(c, [(0.4, 1.1, 0.5, 1.5, 0.9)], ground=0.25)
    s = cluster(s0, 0.12 if c.fine else 0.22)                            # about 4.5k triangles at LOD0, the silhouette kept (thin wings survive 0.12 m cells)
    s.xform(R, t)
    emit(c, s, {0: HULL, 1: "wglass", 2: "steel"}, rust=1.0, seed=3.0)
    if c.state == "damaged":
        bent_beams(c, V([0.4, 1.0, 0.5]) , 2)
    return c


def lifeboatcrashed(state, lod, seed):
    """x -2.6..1.8, y -0.2..1.7, z -2.6..2.7: nose-first into the ground, nose crumpled, the left wing sheared off beside it, the dorsal skin torn open."""
    c = Ctx(state, lod, seed, breach=(-0.2, 1.0, -0.3, 1.5), ledges=[(1.2, 0.5, 0.6)], ground_h=1.5)
    if state == "destroyed":
        return _wreck(c, "boatrust", dx=-0.4, tilt=0.9)
    s0 = load_sculpt()
    cen = s0.centroids()
    L = s0.L
    # nose crumple: pull the front 1.1 m back into a stub with uneven bites (before the pose, in the sculpt frame)
    nz = noise(L, 3.1, 1.0)
    f = np.clip((L[:, 2] - 1.9) / 1.3, 0, 1)
    L2 = L.copy()
    L2[:, 2] = np.where(L[:, 2] > 1.9, 1.9 + (L[:, 2] - 1.9) * (0.55 - 0.25 * f * nz), L[:, 2])
    L2[:, 1] = L[:, 1] * (1.0 - 0.35 * f * nz)
    L2[:, 0] = L[:, 0] * (1.0 - 0.25 * f)
    s0.V = L2.copy()
    s0.L = L2.copy()
    # the left wing breaks off along a ragged line; the dorsal skin tears open aft of the canopy
    edge = -1.25 + 0.3 * (noise(cen, 2.6, 2.0) - 0.5)
    wing = cen[:, 0] < edge
    hole = ((cen[:, 0] + 0.05) / 0.78) ** 2 + ((cen[:, 2] + 0.55) / 1.15) ** 2 < 1.0 + 0.55 * (noise(cen, 4.5, 4.0) - 0.5)
    hole &= (cen[:, 1] > 0.62) & (s0.K == 0)
    gear = _gear_drop(s0)
    keep = ~wing & ~hole & ~gear
    R = axis_angle(AY, 0.45) @ axis_angle(AX, 0.33) @ axis_angle(AZ, 0.16)
    R, t = pose(R, (-0.3, 0.1), s0.sub(keep), -0.35)
    body = s0.sub(keep)
    frag = s0.sub(wing & ~gear)
    body = cluster(body, 0.12 if c.fine else 0.22)
    frag = cluster(frag, 0.12 if c.fine else 0.22)
    body.xform(R, t)
    tear_w = V([-0.05, 0.85, -0.55]) @ R.T + t
    nose_w = V([0.0, 0.5, 2.3]) @ R.T + t
    if c.state == "damaged":
        ends = [(*tear_w, 1.7, 1.0), (*nose_w, 1.6, 1.0)]
    else:
        ends = [(*tear_w, 1.3, 0.95), (*nose_w, 1.4, 0.95)]
    burn_fn(c, ends, ground=0.55)
    emit(c, body, {0: HULL, 1: "wglass", 2: "steel"}, rust=0.9, seed=7.0)
    # the sheared wing lies flat beside the hull, torn edge up, charred
    Rw = axis_angle(AY, -2.4) @ axis_angle(AX, 0.18) @ axis_angle(AZ, 1.35)
    pw = frag.V @ Rw.T
    frag.xform(Rw, np.array([-1.5 - 0.0, 0.0, 0.0]))
    cw = frag.V.mean(0)
    frag.V = frag.V + np.array([-1.7 - cw[0], 0.08 - frag.V[:, 1].min(), 1.3 - cw[2]])
    emit(c, frag, {0: HULL, 1: "wglass", 2: "steel"}, rust=1.0, seed=11.0)
    # torn-open top: a dark interior floor under the hole, ribs bent across it
    fl = [V(p) @ R.T + t for p in [(-0.75, 0.52, -1.7), (0.75, 0.52, -1.7), (-0.75, 0.52, 0.55), (0.75, 0.52, 0.55), (-0.7, 0.6, -1.65), (0.7, 0.6, -1.65), (-0.7, 0.6, 0.5), (0.7, 0.6, 0.5)]]
    from_hull(c, "interior", fl)
    for k in range(4 if c.fine else 2):
        a = V([-0.55 + k * 0.38, 0.6, -1.2 + 0.25 * k]) @ R.T + t
        b2 = a + V([0.12 * (k - 1.5), 0.5 + 0.15 * (k % 2), 0.75 - 0.2 * k])
        c.b.tube("steel", a, b2, 0.045, 5)
    if c.state == "damaged":
        scorch_quad(c, V([-0.2, 1.05, -0.1]) @ R.T + t, 1.5, 1.2)
        bent_beams(c, V([-0.1, 0.8, -0.6]) @ R.T + t, 2)
    return c


def from_hull(c, mat, pts):
    from bld_spaceport import hull
    hull(c, mat, pts)


def scorch_quad(c, p, w, h):
    c.b.quad("scorchblack", V(p) + V([0, 0.05, 0]), V([1.0, 0, 0]), V([0, 0, 1.0]), w, h, (0, 0, 1, 1), normal=(0, 1, 0))


def bent_beams(c, p, n=3, r=0.05, mat="steel"):
    for k in range(n):
        a = V(p) + V([c.rng.uniform(-0.9, 0.9), 0.0, c.rng.uniform(-0.9, 0.9)])
        c.b.tube(mat, a, a + V([c.rng.uniform(-1.0, 1.0), c.rng.uniform(0.5, 1.4), c.rng.uniform(-1.0, 1.0)]), r, 5)


def _wreck(c, mat, dx, tilt):
    """Destroyed: a charred slab with the hull cut into flattened chunks (wings, nose, mid, tail, fin) lying on it, inside the footprint."""
    from bld_spaceport import hull
    rng = c.rng
    hull(c, "concrete_dark", [(dx + x, y, z) for (x, z) in ((-1.8, -1.6), (1.8, -1.6), (1.4, 1.8), (-1.4, 1.8)) for y in (0.0, 0.3)])
    s0 = cluster(load_sculpt(), 0.16 if c.fine else 0.3)
    cen = s0.centroids()
    gear = _gear_drop(s0)
    regions = {
        "wl": (cen[:, 0] < -0.95), "wr": (cen[:, 0] > 0.95),
        "nose": (cen[:, 2] > 1.2) & (np.abs(cen[:, 0]) <= 0.95),
        "fin": (cen[:, 1] > 1.1) & (np.abs(cen[:, 0]) <= 0.95) & (cen[:, 2] <= 1.2),
        "tail": (cen[:, 2] < -0.7) & (cen[:, 1] <= 1.1) & (np.abs(cen[:, 0]) <= 0.95),
        "mid": (cen[:, 2] >= -0.7) & (cen[:, 2] <= 1.2) & (cen[:, 1] <= 1.1) & (np.abs(cen[:, 0]) <= 0.95)}
    slots = {"wl": (-0.9, 0.2), "wr": (1.0, -0.4), "nose": (0.0, 1.2), "fin": (-0.5, -1.1), "tail": (0.6, -1.1), "mid": (0.1, 0.0)}
    taken = np.zeros(len(s0.T), bool)
    for name, m in regions.items():
        m = m & ~taken & ~gear
        taken |= m
        if m.sum() < 4:
            continue
        sc = s0.sub(m)
        a = rng.uniform(0, TAU)
        Rf = _lay_flat(sc.V)
        Rm = axis_angle(AY, a) @ axis_angle(AX, rng.uniform(-tilt, tilt) * 0.3) @ axis_angle(AZ, rng.uniform(-tilt, tilt) * 0.3) @ Rf
        sc.xform(Rm, np.zeros(3))
        cm = sc.V.mean(0)
        sc.V = cm + (sc.V - cm) * 0.8
        sx, sz = slots[name]
        sc.V = sc.V + np.array([dx + sx - cm[0], 0.3 - sc.V[:, 1].min() + rng.uniform(0.0, 0.12), sz - cm[2]])
        sc.K = np.where(sc.K == 1, 0, sc.K)
        emit(c, sc, {0: HULL, 2: "steel"}, rust=1.0, seed=float(len(name)))
    for k in range(3):
        a0 = V([dx + rng.uniform(-1, 1), 0.3, rng.uniform(-1, 1)])
        c.b.tube("steel", a0, a0 + V([rng.uniform(-0.6, 0.6), rng.uniform(0.4, 1.0), rng.uniform(-0.6, 0.6)]), 0.04, 4)
    return c


MEMBERS = {
    "lifeboatcrashed": (lifeboatcrashed, "crashed lifeboat (X-38 sculpt): nose-down, crumpled nose, one wing sheared off, dorsal skin torn open"),
    "lifeboatrusted": (lifeboatrusted, "rusted lifeboat (X-38 sculpt) rolled onto a wing, faded paint and baked rust"),
}
H.MEMBERS.update(MEMBERS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("app")
    ap.add_argument("--out", default=str(ROOT / "game/assets/v3/objects"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for app in (list(MEMBERS) if a.app == "all" else a.app.split(",")):
        H.build_member(app, out)


if __name__ == "__main__":
    main()
