#!/usr/bin/env python3
"""v3 crash-site family (mc2_09 and any map placing them): crashnose, crashwing, crashtail, crashengine, crashrib, crashshanty1..3.

The crash* pieces are sections of one big wrecked dropship (pale blue-grey hull plating, charred torn edges, exposed ribs); crashshanty* are the salvage huts
built beside it from hull panels. Built to the Shared Source originals' per-part bounds and plan/side outlines (/mnt/nvme1n1p1/mc2-rework/bld/crash/dump.py and
wire.py read the glb with each node's translation applied: crashnose +3.125 z, crashwing -2.795 x / +1.661 z, the radar node on the nose, the shanties a few cm).
No original has a root scale, so the mesh size is the in-game size. Pieces are modelled directly in that frame (no wrapper).

State rules: intact = the wreck as placed (weathered, charred torn edges, rust runs); damaged adds fresh scorch, bent beams and a few glowing embers; destroyed
is a flattened charred debris field inside the footprint with a low, recognisable remnant (the keel trough, the fallen fin, the engine drum on its side...).

    python3 -I tools/art/v3/bld_crash.py <app>[,<app>]|all
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bld_hangars as H  # noqa: E402
from bld_industry import V, TAU, ROOT  # noqa: E402
from bld_kit import Ctx, axis_angle  # noqa: E402
from bld_mesh import unit  # noqa: E402
from bld_spaceport import hull, lathe_z  # noqa: E402

HULL = "crashhull"        # pale blue-grey weathered hull paint
HULL2 = "crashhull2"         # lighter panels and white patches
HULL3 = "crashhull3"          # darker blue-grey panels
CHAR = "framedark"          # burnt plating (near-black paint set; every CHAR surface is also baked fully burnt)
FRINGE = "greybrick"        # the blistered, melted white edge of a tear
RIB = "steel"
RUST = "rust"
GLASS = "wglass"


class CCtx(Ctx):
    """A Ctx whose builder bakes every CHAR surface fully burnt and leaves FRINGE surfaces unburnt (so the pale melted edge stays pale against the char)."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        orig = self.b.add
        bld = self.b

        def add(mat, P, N, U, I, band=0, col=(0, 0, 0)):
            if mat == CHAR:
                col = (0, 0, 1.0)
            if mat == FRINGE:
                keep, bld.colfn = bld.colfn, None
                orig(mat, P, N, U, I, band, col)
                bld.colfn = keep
                return
            orig(mat, P, N, U, I, band, col)
        self.b.add = add


def _wreck_burn(c, ends, ground=0.42, gh=2.4):
    """The wreck's baked burn: strongest at each torn end (x, y, z, radius, strength) and along the ground contact line, broken up by noise; damaged adds more on top."""
    if c.state == "destroyed":
        return
    prev = c.b.colfn
    boost = 0.3 if c.state == "damaged" else 0.0

    def f(P):
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        nz = 0.62 + 0.38 * np.sin(x * 0.9 + z * 0.5) * np.sin(z * 1.1 - y * 0.8 + 1.3)
        b = ground * np.exp(-np.clip(y, 0, None) / gh)
        for (ex, ey, ez, r, a) in ends:
            d = np.sqrt((x - ex) ** 2 + (y - ey) ** 2 + (z - ez) ** 2)
            b = np.maximum(b, a * np.exp(-(d / r) ** 2))
        b = np.clip(b * nz + boost * np.exp(-np.clip(y, 0, None) / 7.0) + 0.07, 0, 1)
        return np.maximum(b, prev(P)) if c.state == "damaged" else b
    c.b.colfn = f


# ------------------------------------------------------------------------------------------------------------------ geometry helpers
def A(*p):
    return np.array(p, float)


def poly(c, mat, pts, ref, tile=1.0):
    """A flat convex polygon (fan) with its normal pointing away from the point `ref`; UV planar in metres."""
    pts = np.asarray(pts, float)
    n = np.zeros(3)
    for i in range(len(pts)):
        n += np.cross(pts[i], pts[(i + 1) % len(pts)])
    if np.linalg.norm(n) < 1e-9:
        return
    n = unit(n)
    if np.dot(n, pts.mean(0) - np.asarray(ref, float)) < 0:
        n = -n
    u = unit(pts[1] - pts[0])
    v = np.cross(n, u)
    rel = pts - pts[0]
    U = np.stack([rel @ u, rel @ v], 1) * tile
    c.b.add(mat, pts, np.tile(n, (len(pts), 1)), U, [(0, k, k + 1) for k in range(1, len(pts) - 1)])


def quadg(c, mat, p00, p10, p11, p01, ref, nu=1, nv=1, flip=False):
    """A planar-ish quad as an nu x nv grid of cells (so the baked burn / AO gradient has vertices to ride on); outward away from ref."""
    p00, p10, p11, p01 = map(lambda q: np.asarray(q, float), (p00, p10, p11, p01))
    n = unit(np.cross(p10 - p00, p01 - p00) + np.cross(p11 - p10, p01 - p10))
    if np.dot(n, (p00 + p11) / 2 - np.asarray(ref, float)) < 0:
        n = -n
    if flip:
        n = -n
    Lu, Lv = np.linalg.norm(p10 - p00), np.linalg.norm(p01 - p00)
    P, U = [], []
    for j in range(nv + 1):
        for i in range(nu + 1):
            s, t = i / nu, j / nv
            P.append((1 - t) * ((1 - s) * p00 + s * p10) + t * ((1 - s) * p01 + s * p11))
            U.append((s * Lu, t * Lv))
    idx = []
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            idx += [(a, a + 1, a + nu + 2), (a, a + nu + 2, a + nu + 1)]
    c.b.add(mat, np.array(P), np.tile(n, (len(P), 1)), np.array(U), idx)


def loft(c, rings, mats, ref=None, cell=6.0, closed=True, flip=False):
    """Quads between consecutive rings (same point count, convex). mats: one material or a list per edge. Cells are cut to about `cell` metres on the fine LOD."""
    rings = [np.asarray(r, float) for r in rings]
    n = len(rings[0])
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        r_ = (a.mean(0) + b.mean(0)) / 2 if ref is None else ref
        for k in range(n if closed else n - 1):
            k2 = (k + 1) % n
            m = mats[k] if isinstance(mats, (list, tuple)) else mats
            Lu = np.linalg.norm(a[k2] - a[k])
            Lv = np.linalg.norm(b[k] - a[k])
            if c.fine:
                quadg(c, m, a[k], a[k2], b[k2], b[k], r_, max(1, int(Lu / cell + 0.5)), max(1, int(Lv / cell + 0.5)), flip)
            else:
                quadg(c, m, a[k], a[k2], b[k2], b[k], r_, 1, 1, flip)


def ragged(c, mat, a0, a1, b0, b1, ref, n, fmin=0.4, ref2=None):
    """A torn edge: a solid band along a0..a1, then n uneven teeth (random widths, some stubby and some long, tips bent outward off the skin) reaching toward
    b0..b1, each with a pale blistered fringe over its outer end. ref2 draws the back faces too (for sheets seen from both sides)."""
    a0, a1, b0, b1 = map(lambda q: np.asarray(q, float), (a0, a1, b0, b1))
    rng = c.rng
    n = n if c.fine else max(2, n // 2 + 1)
    w = rng.uniform(0.3, 2.2, n)
    s = np.concatenate([[0.0], np.cumsum(w) / w.sum()])
    fb = fmin * 0.5
    A_ = lambda t: a0 + (a1 - a0) * t
    B_ = lambda t: b0 + (b1 - b0) * t
    nrm = unit(np.cross(a1 - a0, (b0 + b1) / 2 - (a0 + a1) / 2))
    if np.linalg.norm(nrm) < 1e-6:
        nrm = A(0, 1.0, 0)
    if np.dot(nrm, (a0 + a1) / 2 - np.asarray(ref, float)) < 0:
        nrm = -nrm
    refs = [(ref, 1.0)] + ([(ref2, -1.0)] if ref2 is not None else [])
    poly(c, mat, [A_(0), A_(1), A_(1) + (B_(1) - A_(1)) * fb, A_(0) + (B_(0) - A_(0)) * fb], ref)
    if ref2 is not None:
        poly(c, mat, [A_(0), A_(1), A_(1) + (B_(1) - A_(1)) * fb, A_(0) + (B_(0) - A_(0)) * fb], ref2)
    for i in range(n):
        s0, s1 = s[i], s[i + 1]
        sm = s0 + (s1 - s0) * rng.uniform(0.2, 0.8)
        r_ = rng.random()
        f = (rng.uniform(0.12, 0.35) if r_ < 0.35 else rng.uniform(0.4, 0.7) if r_ < 0.75 else rng.uniform(0.85, 1.0))
        if not c.fine and i % 2 == 0:
            f = 1.0
        p0, p1 = A_(s0) + (B_(s0) - A_(s0)) * fb, A_(s1) + (B_(s1) - A_(s1)) * fb
        tip = A_(sm) + (B_(sm) - A_(sm)) * f
        tlen = np.linalg.norm(tip - (p0 + p1) / 2)
        tip = tip + nrm * rng.uniform(0.0, 0.25) * tlen + (a1 - a0) * rng.uniform(-0.06, 0.06) * (s1 - s0) * 8
        poly(c, mat, [p0, p1, tip], ref)
        if ref2 is not None:
            poly(c, mat, [p0, p1, tip], ref2)
        if tlen > 0.5:
            q0, q1 = p0 + (tip - p0) * 0.58, p1 + (tip - p1) * 0.58
            off = nrm * 0.05
            poly(c, FRINGE, [q0 + off, q1 + off, tip + off], ref)
            if ref2 is not None:
                poly(c, FRINGE, [q0 - off, q1 - off, tip - off], ref2)


def circ(center, axis, R, n=6, phase=0.0, sx=1.0, sy=1.0, up=(0, 1.0, 0)):
    """n points on a (scaled) circle about `center` in the plane perpendicular to `axis`; the first lies along `up` x axis (phase rotates it)."""
    axis = unit(axis)
    u = unit(np.cross(up, axis)) if abs(np.dot(unit(up), axis)) < 0.99 else A(1.0, 0, 0)
    v = np.cross(axis, u)
    return np.array([np.asarray(center, float) + R * (sx * math.cos(phase + TAU * k / n) * u + sy * math.sin(phase + TAU * k / n) * v) for k in range(n)])


def beam(c, mat, p0, p1, r=0.2):
    c.b.tube(mat, A(*p0), A(*p1), r, 5 if c.fine else 4)


def frame_ring(c, ring, r=0.22, mat=RIB):
    ring = np.asarray(ring, float)
    for k in range(len(ring)):
        beam(c, mat, ring[k], ring[(k + 1) % len(ring)], r)


def slab(c, mat, p0, p1, p2, p3, t, ref=None):
    """A thin plate: the quad p0..p3 (counter-clockwise from the outside) pushed `t` metres to its inside, as a closed convex solid."""
    P = [np.asarray(q, float) for q in (p0, p1, p2, p3)]
    n = unit(np.cross(P[1] - P[0], P[3] - P[0]))
    hull(c, mat, P + [q - n * t for q in P])


def plate_box(c, mat, ctr, size, yaw=0.0, tilt=0.0, roll=0.0):
    R = axis_angle(V([0, 1.0, 0]), yaw) @ axis_angle(V([1.0, 0, 0]), tilt) @ axis_angle(V([0, 0, 1.0]), roll)
    c.b.box(mat, ctr, size, R)


def ember(c, p, w=0.6, n=(0, 1, 0)):
    """A glowing ember patch in a tear (damaged only): an emissive quad on the char."""
    if c.state != "damaged":
        return
    n = unit(n)
    t = unit(np.cross(n, (0, 1.0, 0.3)))
    c.b.quad("lamp_red", np.asarray(p, float) + n * 0.12, t, np.cross(n, t), w, w * 0.7, (0, 0, 1, 1), normal=tuple(n))


def soot(c, p, w, h, rot=0.0, y=0.3):
    c.decal_ground("soot", (p[0], p[1]), w, h, rot, y=y)


def arc_rib(c, ctr, ax_u, ax_v, R, a0, a1, r=0.2, mat=RIB, n=8):
    """A bent frame rib: a tube along a circular arc (centre ctr, in the plane spanned by unit vectors ax_u, ax_v, angles a0..a1)."""
    ctr, ax_u, ax_v = map(lambda q: np.asarray(q, float), (ctr, ax_u, ax_v))
    n = n if c.fine else max(3, n // 2)
    path = [ctr + R * (math.cos(a0 + (a1 - a0) * i / n) * ax_u + math.sin(a0 + (a1 - a0) * i / n) * ax_v) for i in range(n + 1)]
    c.b.sweep(mat, path, r, 5 if c.fine else 4, caps=True)


def debris_field(c, boxes, n, hmax=3.0, mats=(CHAR, HULL3, CHAR, RUST), size=(1.6, 5.0)):
    """Flat charred hull plates and chunks scattered inside the (x0, x1, z0, z1) boxes (each plate kept wholly inside its box), plus a scorched ground pad."""
    rng = c.rng
    boxes = [tuple(b) for b in boxes]
    areas = np.array([(b[1] - b[0]) * (b[3] - b[2]) for b in boxes])
    for b in boxes:
        c.b.box("concrete_dark", ((b[0] + b[1]) / 2, 0.1, (b[2] + b[3]) / 2), (b[1] - b[0], 0.2, b[3] - b[2]))
    cnt = n if c.fine else max(4, n // 2)
    for k in range(cnt):
        b = boxes[int(rng.choice(len(boxes), p=areas / areas.sum()))]
        sx, sz = rng.uniform(*size), rng.uniform(*size)
        r = math.hypot(sx, sz) / 2 + 0.3
        if (b[1] - b[0]) < 2 * r or (b[3] - b[2]) < 2 * r:
            sx, sz = min(sx, (b[1] - b[0]) - 0.8), min(sz, (b[3] - b[2]) - 0.8)
            r = math.hypot(sx, sz) / 2 + 0.2
        x = rng.uniform(b[0] + r, max(b[0] + r, b[1] - r)) if b[1] - b[0] > 2 * r else (b[0] + b[1]) / 2
        z = rng.uniform(b[2] + r, max(b[2] + r, b[3] - r)) if b[3] - b[2] > 2 * r else (b[2] + b[3]) / 2
        hh = rng.uniform(0.15, 0.4)
        lift = rng.uniform(0.2, min(hmax * 0.35, 1.4)) * (rng.random() ** 2)
        plate_box(c, mats[k % len(mats)], (x, 0.2 + lift + hh / 2, z), (sx, hh, sz), rng.uniform(0, 3.1), rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3))
    for k in range(3 if c.fine else 1):
        b = boxes[int(rng.choice(len(boxes), p=areas / areas.sum()))]
        a0 = A(rng.uniform(b[0] + 1, b[1] - 1), 0.3, rng.uniform(b[2] + 1, b[3] - 1))
        beam(c, RIB, a0, a0 + A(rng.uniform(-0.8, 0.8), rng.uniform(1.0, 2.4), rng.uniform(-0.8, 0.8)), 0.12)
    for b in boxes:
        soot(c, ((b[0] + b[1]) / 2, (b[2] + b[3]) / 2), b[1] - b[0], b[3] - b[2], 0.0, y=0.24)


def panel_seams(c, a, b, ref, w=0.1, mat=RIB):
    """A seam / hull strap along the edge a..b: a thin proud bar (fine LOD only)."""
    if not c.fine:
        return
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = unit(b - a)
    n = unit(a - np.asarray(ref, float))
    side = unit(np.cross(d, n))
    hull(c, mat, [a + side * w, a - side * w, b + side * w, b - side * w, a + n * 0.1 + side * w * 0.6, a + n * 0.1 - side * w * 0.6,
                  b + n * 0.1 + side * w * 0.6, b + n * 0.1 - side * w * 0.6])


# ------------------------------------------------------------------------------------------------------------------ shanties
def _wall_patch(c, p, nrm, ax_u, w, h, mat):
    """A salvaged panel laid on a wall: a quad just proud of it."""
    nrm = unit(nrm)
    c.b.quad(mat, np.asarray(p, float) + nrm * 0.05, unit(ax_u), (0, 1.0, 0), w, h, (0, 0, 1, 1), normal=tuple(nrm))


def _opening(c, p, nrm, ax_u, w, h, door=False):
    nrm = unit(nrm)
    mat = CHAR if door else GLASS
    c.b.quad(mat, np.asarray(p, float) + nrm * 0.07, unit(ax_u), (0, 1.0, 0), w, h, (0, 0, 1, 1), normal=tuple(nrm))
    t = unit(ax_u)
    for s in (-1, 1):                                                                       # frame posts
        hull(c, RIB, [np.asarray(p, float) + t * s * (w / 2 + 0.05) + nrm * k + (0, yy, 0) for k in (0.0, 0.12) for yy in (-h / 2, h / 2)])
    hull(c, RIB, [np.asarray(p, float) + t * s * (w / 2 + 0.1) + nrm * k + (0, h / 2 + 0.05 + e, 0) for s in (-1, 1) for k in (0.0, 0.12) for e in (0, 0.08)])


SCRAP = [HULL, HULL2, HULL3, RUST, "corrugated", CHAR, "boards", RUST, HULL3, "corrugated", HULL]


def _patchwork(c, ring_bot, ring_top, ctr, n):
    """Scrap nailed over each wall: overlapping plates of mismatched hull, rust, corrugated and boards, each skewed and some overhanging the corners or the eave,
    plus a group of slats with gaps and now and then a tarp."""
    rng = c.rng
    up = A(0, 1.0, 0)
    for wl in range(4):
        k2 = (wl + 1) % 4
        a, b2 = ring_bot[wl], ring_bot[k2]
        d = unit(b2 - a)
        nrm = unit(np.cross(up, d))
        if np.dot(nrm, a - ctr) < 0:
            nrm = -nrm
        L = np.linalg.norm(b2 - a)
        top = min(ring_top[wl][1], ring_top[k2][1])
        for i in range(n):
            w, h = rng.uniform(1.0, 2.8), rng.uniform(0.8, 2.0)
            h = min(h, top + 0.25)
            u = rng.uniform(w / 2 - 0.35, L - w / 2 + 0.35)
            v = rng.uniform(h / 2 - 0.1, max(h / 2, top - h / 2 + 0.3))
            ang = rng.uniform(-0.22, 0.22)
            d2 = d * math.cos(ang) + up * math.sin(ang)
            up2 = -d * math.sin(ang) + up * math.cos(ang)
            R = np.column_stack([d2, up2, np.cross(d2, up2)])
            mat = SCRAP[(wl * 3 + i + int(rng.integers(0, 4))) % len(SCRAP)]
            c.b.box(mat, a + d * u + up * v + nrm * (0.06 + 0.013 * i), (w, h, 0.07), R)
        # slats with gaps: a dark backing and vertical boards a hand apart
        if wl % 2 == 0 or c.fine:
            sw, sh = 5 if c.fine else 3, min(1.9, top - 0.3)
            u0 = rng.uniform(0.6, max(0.7, L - 0.45 * sw - 0.6))
            c.b.box(CHAR, a + d * (u0 + 0.19 * sw) + up * (sh / 2 + 0.1) + nrm * 0.1, (0.38 * sw, sh, 0.05), np.column_stack([d, up, nrm]))
            for q in range(sw):
                hh = sh - rng.uniform(0.0, 0.5)
                c.b.box("boards", a + d * (u0 + 0.38 * q) + up * (hh / 2 + 0.1) + nrm * 0.15, (0.27, hh, 0.05), np.column_stack([d, up, nrm]))
        if wl == 1:                                                                           # a tarp tied over part of a wall, sagging at the bottom
            tw, th = rng.uniform(1.8, 2.6), min(1.6, top - 0.5)
            c.b.box("canvas", a + d * (L * 0.5) + up * (top * 0.5) + nrm * 0.2, (tw, th, 0.04), np.column_stack([d, up, nrm]) @ axis_angle(V([0, 0, 1.0]), 0.12))


def _roof_plates(c, rect, ang, y_at, n, mats=None, extra=0.35):
    """A sagging, patched roof: n overlapping plates laid on the roof plane (pitch `ang` about x, height y_at(z) at the plate centre), each skewed, of
    mismatched scrap, overhanging the rectangle by up to `extra`, with a tarp thrown over one corner."""
    rng = c.rng
    x0, x1, z0, z1 = rect
    mats = mats or [CHAR, RUST, HULL3, "corrugated", CHAR, HULL, "corrugated", RUST]
    for i in range(n):
        w, d = rng.uniform(2.0, 3.8), rng.uniform(1.8, 3.2)
        x = rng.uniform(x0 + w / 2 - extra, x1 - w / 2 + extra)
        z = rng.uniform(z0 + d / 2 - extra, z1 - d / 2 + extra)
        sag = 0.14 * (1 - min(1.0, math.hypot((x - (x0 + x1) / 2) / (x1 - x0) * 2, (z - (z0 + z1) / 2) / (z1 - z0) * 2)))
        R = axis_angle(V([1.0, 0, 0]), -ang) @ axis_angle(V([0, 1.0, 0]), rng.uniform(-0.3, 0.3)) @ axis_angle(V([1.0, 0, 0]), rng.uniform(-0.07, 0.07)) @ axis_angle(V([0, 0, 1.0]), rng.uniform(-0.07, 0.07))
        c.b.box(mats[i % len(mats)], (x, y_at(z) + 0.25 - sag + 0.012 * i, z), (w, 0.07, d), R)
    tx, tz = x1 - 1.2, z0 + 1.1
    R = axis_angle(V([1.0, 0, 0]), -ang) @ axis_angle(V([0, 1.0, 0]), 0.5)
    c.b.box("canvas", (tx, y_at(tz) + 0.36, tz), (2.6, 0.04, 2.0), R)


def _shanty_walls(c, ring_bot, ring_top, mats, patches, windows, door):
    """The four walls of a hut from a bottom and a top ring of 4 points (counter-clockwise seen from above), with salvaged patches and openings.
    patches: [(wall, u0, v0, w, h, mat)], windows: [(wall, u, v, w, h)], door: (wall, u, w, h)."""
    ctr = ring_bot.mean(0) + (0, 1.5, 0)
    for k in range(4):
        k2 = (k + 1) % 4
        a, b = ring_bot[k], ring_bot[k2]
        at, bt = ring_top[k], ring_top[k2]
        quadg(c, mats[k], a, b, bt, at, ctr, max(1, int(np.linalg.norm(b - a) / 2.8 + 0.5)) if c.fine else 1, 2 if c.fine else 1)
    _patchwork(c, ring_bot, ring_top, ctr, 6 if c.fine else 3)
    for (wl, u0, v0, w, h, mat) in patches:
        k2 = (wl + 1) % 4
        a, b = ring_bot[wl], ring_bot[k2]
        d = unit(b - a)
        nrm = unit(np.cross((0, 1.0, 0), d))
        if np.dot(nrm, a - ctr) < 0:
            nrm = -nrm
        L = np.linalg.norm(b - a)
        top = ring_top[wl][1] + (ring_top[k2][1] - ring_top[wl][1]) * ((u0 + w / 2) / L)
        if v0 + h > top - 0.05:
            h = max(0.3, top - 0.05 - v0)
        if c.fine or mat == CHAR:
            _wall_patch(c, a + d * (u0 + w / 2) + (0, v0 + h / 2, 0), nrm, d, w, h, mat)
    for (wl, u, v, w, h) in windows:
        k2 = (wl + 1) % 4
        a, b = ring_bot[wl], ring_bot[k2]
        d = unit(b - a)
        nrm = unit(np.cross((0, 1.0, 0), d))
        if np.dot(nrm, a - ctr) < 0:
            nrm = -nrm
        _opening(c, a + d * u + (0, v, 0), nrm, d, w, h)
    if door:
        wl, u, w, h = door
        k2 = (wl + 1) % 4
        a, b = ring_bot[wl], ring_bot[k2]
        d = unit(b - a)
        nrm = unit(np.cross((0, 1.0, 0), d))
        if np.dot(nrm, a - ctr) < 0:
            nrm = -nrm
        _opening(c, a + d * u + (0, h / 2, 0), nrm, d, w, h, door=True)


def _roof_slab(c, mat, pts_top, t=0.2, patch=None):
    """A roof as a closed slab under the plane through pts_top (4 corners)."""
    P = [np.asarray(q, float) for q in pts_top]
    hull(c, mat, P + [q - (0, t, 0) for q in P])


def _shanty_wreck(c, w, d, roof_mat=CHAR):
    """A collapsed hut: scorched floor, two leaning wall sheets, the roof sheet fallen across, rubble."""
    b = c.b
    rng = c.rng
    b.box("concrete_dark", (0, 0.1, 0), (w, 0.2, d))
    sx, sz = w * 0.5 - 0.35, d * 0.5 - 0.35
    plate_box(c, HULL, (-sx * 0.3, 0.9, -sz + 0.1), (w * 0.6, 1.5, 0.15), 0.1, 0.35, 0.0)
    plate_box(c, HULL3, (sx - 0.1, 0.8, sz * 0.3), (0.15, 1.3, d * 0.55), 0.2, 0.0, 0.3)
    plate_box(c, roof_mat, (0.2, 0.75, 0.1), (w * 0.62, 0.15, d * 0.55), 0.3, 0.1, -0.12)
    for k in range(3 if c.fine else 1):
        plate_box(c, (CHAR, RUST, HULL3)[k % 3], (rng.uniform(-sx, sx), 0.3, rng.uniform(-sz, sz)), (rng.uniform(0.8, 1.6), 0.12, rng.uniform(0.7, 1.4)), rng.uniform(0, 3), rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3))
    for k in range(2):
        beam(c, RIB, A(-sx + k * 2 * sx, 0.2, -sz), A(-sx + k * 2 * sx + rng.uniform(-0.3, 0.3), 1.5 + k * 0.4, -sz + rng.uniform(-0.3, 0.3)), 0.08)
    c.decal_ground("soot", (0, 0), w * 1.0, d * 1.0, 0.0, y=0.24)


def _shanty_damaged(c, p, nrm_ax=(1, 0, 0)):
    if c.state != "damaged":
        return
    c.b.box("scorchblack", (p[0], p[1], p[2]), (0.06, 1.3, 1.6) if abs(nrm_ax[0]) > 0 else (1.6, 1.3, 0.06))
    for k in range(2):
        beam(c, RIB, A(p[0], p[1] - 0.6, p[2] + (k - 0.5) * 0.9), A(p[0] + c.rng.uniform(-0.5, 0.5), p[1] + 1.2, p[2] + (k - 0.5) * 0.9 + c.rng.uniform(-0.4, 0.4)), 0.05)
    ember(c, (p[0] + 0.05, p[1] - 0.3, p[2]), 0.5, (1, 0, 0) if abs(nrm_ax[0]) > 0 else (0, 0, 1))


def crashshanty1(state, lod, seed):
    """x +-3.5, z +-3.5, y 0..4.3: a salvage hut, walls x +-2.8 z +-2.8 from 2.1 m (front, -z) to 4.0 m (back) under a black mono-pitch roof overhanging to +-3.5."""
    c = CCtx(state, lod, seed, breach=(2.8, 1.8, 0.0, 2.0), ledges=[(3.2, 1.6, 0.35)], ground_h=3.0)
    if state == "destroyed":
        _shanty_wreck(c, 5.6, 5.6)
        return c
    bot = np.array([(-2.8, 0, -2.8), (2.8, 0, -2.8), (2.8, 0, 2.8), (-2.8, 0, 2.8)], float)
    top = np.array([(-2.8, 2.1, -2.8), (2.8, 2.1, -2.8), (2.8, 4.0, 2.8), (-2.8, 4.0, 2.8)], float)
    # walls: 0 = -z (front, low) 1 = +x (door side) 2 = +z (back, tall) 3 = -x (windows)
    _shanty_walls(c, bot, top, [HULL, HULL3, HULL, HULL2],
                  [(0, 0.2, 0.2, 2.6, 1.5, HULL2), (0, 3.1, 0.4, 2.1, 1.3, HULL3), (1, 0.3, 0.3, 2.3, 1.7, HULL2), (1, 3.1, 1.0, 2.2, 2.4, "corrugated"),
                   (2, 0.2, 0.3, 2.4, 2.8, HULL3), (2, 2.9, 0.4, 2.5, 3.0, HULL2), (2, 0.5, 2.7, 4.6, 0.9, "corrugated"),
                   (3, 0.3, 0.2, 2.2, 1.7, "corrugated"), (3, 3.2, 0.3, 2.1, 2.5, HULL3)],
                  [(3, 1.4, 1.35, 1.0, 0.8), (3, 4.2, 1.5, 1.0, 0.9)], (1, 1.5, 1.1, 2.0))
    _roof_slab(c, CHAR, [(-3.5, 1.9, -3.5), (3.5, 1.9, -3.5), (3.5, 4.3, 3.5), (-3.5, 4.3, 3.5)], 0.22)
    _roof_plates(c, (-3.5, 3.5, -3.5, 3.5), math.atan(0.343), lambda z: 3.1 + 0.343 * z, 7 if c.fine else 4)
    for sx in (-1, 1):
        beam(c, RIB, A(sx * 2.8, 2.0, -2.8), A(sx * 2.8 + sx * 0.1, 3.0, -2.8), 0.1)
        beam(c, RIB, A(sx * 2.8, 4.0, 2.8), A(sx * 2.7, 5.0, 2.9), 0.1)
    _shanty_damaged(c, (2.86, 1.4, -0.8))
    return c


def crashshanty2(state, lod, seed):
    """x -2.8..2.9, z -2.5..3.0, y 0..4.3: a lean-to; a steep front plate from the ground (z -2.5) up to 2.7 m at z -0.8, then a black roof rising to 4.3 at z 3.0."""
    c = CCtx(state, lod, seed, breach=(2.5, 2.0, 0.5, 2.0), ledges=[(3.5, 1.6, 0.35)], ground_h=3.0)
    if state == "destroyed":
        _shanty_wreck(c, 5.4, 5.2)
        return c
    # walls: ring in plan at the base is x +-2.5, z -2.5..2.6; the sloped front leans from the ground to (z -0.8, y 2.7)
    ctr = A(0, 1.8, 0.5)
    side = [(-2.5, 0.0, -2.5), (-2.5, 0.0, 2.6), (-2.5, 4.0, 2.6), (-2.5, 2.7, -0.8)]
    for sx, m in ((-1, HULL2), (1, HULL3)):
        pts = [(sx * x, y, z) for (x, y, z) in side]
        poly(c, m, pts, ctr + A(sx * 5, 0, 0))
    quadg(c, HULL, A(-2.5, 0, 2.6), A(2.5, 0, 2.6), A(2.5, 4.0, 2.6), A(-2.5, 4.0, 2.6), ctr, 2 if c.fine else 1, 2 if c.fine else 1)         # back wall (+z)
    quadg(c, HULL3, A(-2.5, 0, -2.5), A(2.5, 0, -2.5), A(2.5, 2.7, -0.8), A(-2.5, 2.7, -0.8), ctr, 2 if c.fine else 1, 2 if c.fine else 1)  # sloped front
    _roof_slab(c, CHAR, [(-2.9, 2.8, -0.8), (2.9, 2.8, -0.8), (2.9, 4.3, 3.0), (-2.9, 4.3, 3.0)], 0.22)
    _roof_plates(c, (-2.9, 2.9, -0.8, 3.0), math.atan(0.395), lambda z: 2.8 + 0.395 * (z + 0.8), 6 if c.fine else 3)
    for (u, v, w, h, m) in ((-1.2, 0.8, 2.0, 1.2, HULL2), (1.4, 1.6, 1.8, 1.1, "corrugated"), (0.3, 1.2, 1.6, 1.0, RUST)):         # scrap on the steep front plate
        k_ = 0.63
        quadg(c, m, A(u - w / 2, v - h / 2, -2.5 + (v - h / 2) * k_ - 0.06), A(u + w / 2, v - h / 2, -2.5 + (v - h / 2) * k_ - 0.06),
              A(u + w / 2, v + h / 2, -2.5 + (v + h / 2) * k_ - 0.06), A(u - w / 2, v + h / 2, -2.5 + (v + h / 2) * k_ - 0.06), ctr - A(0, 0, 4))
    rb = np.array([(2.5, 0, -0.8), (2.5, 0, 2.6), (-2.5, 0, 2.6), (-2.5, 0, -0.8)], float)
    _patchwork(c, rb, rb + A(0, 3.5, 0), ctr, 5 if c.fine else 3)
    for (z, u, w, h) in ((-1.55, 0.0, 1.0, 1.9),):                                               # door in the +x wall near the front
        _opening(c, A(2.56, h / 2, 1.0), A(1, 0, 0), A(0, 0, 1), w, h, door=True)
    _opening(c, A(-2.56, 1.9, 1.8), A(-1, 0, 0), A(0, 0, 1), 1.0, 0.8)
    _opening(c, A(-2.56, 1.9, -0.3), A(-1, 0, 0), A(0, 0, 1), 0.9, 0.7)
    if c.fine:                                                                                   # a bent hull sheet leaned against the side
        plate_box(c, HULL2, (3.05, 1.1, -1.3), (0.1, 2.0, 1.9), 0.0, 0.0, 0.32)
    _shanty_damaged(c, (2.56, 1.6, -0.2))
    return c


def crashshanty3(state, lod, seed):
    """x -3.0..3.1, z -3.2..3.2, y 0..2.3: a low flat-roofed hut, walls x -2.4..2.5, z +-2.6 to 2.3 m, a pale patchwork roof overhanging to +-3.1."""
    c = CCtx(state, lod, seed, breach=(2.5, 1.2, 0.0, 2.0), ledges=[(2.1, 1.2, 0.3)], ground_h=2.5)
    if state == "destroyed":
        _shanty_wreck(c, 5.0, 5.2, HULL3)
        return c
    bot = np.array([(-2.4, 0, -2.6), (2.5, 0, -2.6), (2.5, 0, 2.6), (-2.4, 0, 2.6)], float)
    top = bot + (0, 2.3, 0)
    _shanty_walls(c, bot, top, [HULL, HULL3, HULL2, HULL],
                  [(0, 0.2, 0.2, 2.3, 1.4, HULL2), (0, 2.7, 0.3, 2.0, 1.5, "corrugated"), (1, 0.3, 0.2, 2.5, 1.5, "corrugated"), (1, 3.0, 0.3, 2.0, 1.6, HULL3),
                   (2, 0.3, 0.3, 2.2, 1.6, HULL3), (2, 2.8, 0.2, 2.0, 1.8, "corrugated"), (3, 0.2, 0.3, 2.4, 1.7, HULL2), (3, 3.1, 0.3, 1.9, 1.5, HULL3)],
                  [(0, 1.1, 1.2, 1.1, 0.9), (0, 3.6, 1.2, 1.1, 0.9)], (3, 2.6, 1.1, 1.9))
    _roof_slab(c, CHAR, [(-3.0, 2.3, -3.2), (3.1, 2.3, -3.2), (3.1, 2.3, 3.2), (-3.0, 2.3, 3.2)], 0.22)
    _roof_plates(c, (-3.0, 3.1, -3.2, 3.2), 0.0, lambda z: 2.3, 8 if c.fine else 4, [HULL, HULL3, "corrugated", HULL2, RUST, HULL3, CHAR, "corrugated"], 0.4)
    _shanty_damaged(c, (2.56, 1.1, 0.3))
    return c


# ------------------------------------------------------------------------------------------------------------------ crashnose
CXN = -3.65
# (bw, yb, sw, ys, shw, ysh, cw, yc): half-widths about x = CXN of the barrel's eight corners at each station (read off the original's vertices)
NOSE_ST = [
    (-6.4, (9.45, -1.4, 10.45, 1.2, 8.45, 6.1, 3.65, 8.5)),
    (-1.7, (11.25, -1.4, 12.85, 2.5, 10.15, 9.3, 3.65, 12.1)),
    (4.4, (11.75, -1.4, 13.65, 3.3, 10.65, 10.7, 3.65, 13.7)),
    (19.3, (11.75, -1.4, 13.65, 3.4, 10.65, 10.7, 3.65, 13.75)),
]
NOSE_LIP = [(-6.85, 0.0), (6.85, 0.0), (6.6, 1.0), (5.4, 2.3), (3.65, 3.0), (-3.65, 3.0), (-5.4, 2.3), (-6.6, 1.0)]     # the chin at z -9.9


def nose_ring(z, p):
    bw, yb, sw, ys, shw, ysh, cw, yc = p
    return np.array([(CXN - bw, yb, z), (CXN + bw, yb, z), (CXN + sw, ys, z), (CXN + shw, ysh, z), (CXN + cw, yc, z), (CXN - cw, yc, z), (CXN - shw, ysh, z), (CXN - sw, ys, z)], float)


def _nose_extension(c, rear, ref):
    """The torn aft end: black teeth from the z = 19.3 ring out to z about 24.9 on the lower facets, short pale teeth on the roof facets."""
    r = rear
    far = lambda q, dz: q + A(0, 0, dz)
    ragged(c, CHAR, r[0], r[1], far(r[0], 5.6), far(r[1], 5.6), ref, 9, 0.45)
    ragged(c, CHAR, r[1], r[2], far(r[1], 5.6), far(r[2], 5.0), ref, 3, 0.4)
    ragged(c, CHAR, r[7], r[0], far(r[7], 5.0), far(r[0], 5.6), ref, 3, 0.4)
    ragged(c, CHAR, r[2], r[3], far(r[2], 4.2), far(r[3], 3.6), ref, 4, 0.3)
    ragged(c, CHAR, r[6], r[7], far(r[6], 3.6), far(r[7], 5.0), ref, 4, 0.3)
    for (i, j) in ((3, 4), (4, 5), (5, 6)):
        ragged(c, HULL, r[i], r[j], far(r[i], 4.6), far(r[j], 4.6), ref, 5, 0.3)


def _nose_rim(c, ring):
    """A flange band round the torn rear ring (z = -6.4) pierced by round lightening holes: what the rear view shows."""
    cen = ring.mean(0)
    for k in range(8):
        a, b2 = ring[k], ring[(k + 1) % 8]
        a2, b3 = cen + (a - cen) * 0.84, cen + (b2 - cen) * 0.84
        hull(c, HULL2, [a, b2, a2, b3, a + A(0, 0, 0.5), b2 + A(0, 0, 0.5), a2 + A(0, 0, 0.5), b3 + A(0, 0, 0.5)])
        if c.fine and k not in (3, 4, 5):
            m = (a + b2) / 2 * 0.5 + (a2 + b3) / 2 * 0.5 + A(0, 0, 0.52)
            for f in (-0.22, 0.22):
                c.b.disc(RIB, m + (b2 - a) * f, 0.5, (0, 0, 1), 8)


def _facet_pane(c, a0, a1, b0, b1, s0, s1, t0, t1, ref, mat=GLASS):
    """A pane on a sub-rectangle (s along a0..a1, t from the a-edge to the b-edge) of a loft facet, just proud of it."""
    P = lambda s_, t_: (1 - t_) * ((1 - s_) * a0 + s_ * a1) + t_ * ((1 - s_) * b0 + s_ * b1)
    q = [P(s0, t0), P(s1, t0), P(s1, t1), P(s0, t1)]
    n = unit(np.cross(q[1] - q[0], q[3] - q[0]))
    if np.dot(n, q[0] - np.asarray(ref, float)) < 0:
        n = -n
    poly(c, mat, [x + n * 0.07 for x in q], ref)


def _nose_windows(c, r_a, r_b):
    """The cockpit glazing: panes on the sloping crown and shoulder facets between the z = -6.4 and z = -1.7 rings, mullions as gaps."""
    ref = A(CXN, 4.0, 2.0)
    for k, n in ((4, 5), (3, 2), (5, 2), (2, 2), (6, 2)):
        if not c.fine and k in (2, 6):
            continue
        for i in range(n):
            w = 1.0 / n
            _facet_pane(c, r_a[k], r_a[(k + 1) % 8], r_b[k], r_b[(k + 1) % 8], i * w + 0.06, (i + 1) * w - 0.06, 0.18, 0.5 if k in (2, 6) else 0.62, ref)


def _nose_radar(c):
    b = c.b
    seg = 10 if c.fine else 6
    b.revolve(HULL3, [(0.0, 13.7), (1.0, 13.7), (0.9, 14.5), (0.45, 15.0), (0.0, 15.0)], seg, cx=-3.3, cz=14.2, uref=1.0)
    beam(c, RIB, A(-3.3, 14.8, 14.2), A(-4.2, 17.0, 14.8), 0.18)
    P = [A(-8.1, 17.1, 15.9), A(-4.2, 18.1, 16.8), A(-1.3, 18.1, 11.8), A(-1.6, 17.0, 11.2), A(-5.3, 14.9, 14.8)]
    hull(c, HULL2, [q + (0, dy, 0) for q in P for dy in (0.0, 0.28)])
    hull(c, HULL3, [A(-4.3, 15.4, 14.8), A(-3.5, 15.4, 14.3), A(-3.3, 13.8, 16.6), A(-4.3, 13.8, 14.7)])


def _nose_details(c):
    """Seam straps down the barrel's corners and across its roof, a hatch and an emblem plate on the +x side, and the lamp pair."""
    ref = A(CXN, 6, 6)
    for k in range(8):                                                                 # longitudinal straps at the facet corners
        panel_seams(c, nose_ring(18.9, NOSE_ST[0][1])[k], nose_ring(-1.7, NOSE_ST[2][1])[k], ref, 0.12)
    for z in (14.0, 9.0):                                                              # transverse straps over the roof and shoulders
        r = nose_ring(z, NOSE_ST[1][1])
        for k in (2, 3, 4, 5, 6):
            panel_seams(c, r[k], r[(k + 1) % 8], ref, 0.09)
    r = nose_ring(11.5, NOSE_ST[1][1])
    n_ = unit(np.cross(r[3] - r[2], A(0, 0, 1.0)))
    if np.dot(n_, r[2] - ref) < 0:
        n_ = -n_
    mid = (r[2] + r[3]) / 2 + n_ * 0.06
    t_ = unit(r[3] - r[2])
    c.b.quad(HULL3, mid + A(0, 0, 1.0), A(0, 0, 1.0), t_, 2.6, 2.2, (0, 0, 1, 1), normal=tuple(n_))
    c.b.quad("lamp_off", mid + A(0, 0, -1.6) + t_ * 0.8, A(0, 0, 1.0), t_, 0.7, 0.7, (0, 0, 1, 1), normal=tuple(n_))
    c.b.quad("lamp_off", mid + A(0, 0, -2.5) + t_ * 0.8, A(0, 0, 1.0), t_, 0.7, 0.7, (0, 0, 1, 1), normal=tuple(n_))


def crashnose(state, lod, seed):
    """x -17.3..10, y -1.4..18.1, z -9.9..24.9 (in game, node +3.125 z): a faceted barrel; the cockpit end (-z) slopes down to a chin under a window band, the
    aft end (+z) is torn off: a burnt black lower half, a flange ring pierced with round holes and ragged teeth beyond it; a radar fin on the roof."""
    c = CCtx(state, lod, seed, breach=(CXN, 4.0, 17.5, 10.0), ledges=[(10.7, 4.0, 0.35), (3.4, 3.0, 0.3)], ground_h=4.0)
    _wreck_burn(c, [(CXN, 4.0, 21.5, 15.0, 0.95), (CXN, 6.0, 2.0, 9.0, 0.1)])
    b = c.b
    ref = A(CXN, 6.0, 6.0)
    if state == "destroyed":
        _nose_wreck(c)
        return c
    rings = [nose_ring(z, p) for z, p in NOSE_ST]
    lip = np.array([(CXN + x, y, -9.9) for (x, y) in NOSE_LIP], float)
    mats = [HULL3, HULL, HULL2, HULL, HULL2, HULL, HULL2, HULL]
    loft(c, [lip, rings[0]], [HULL3, HULL3, HULL, HULL, HULL2, HULL, HULL, HULL3], ref, cell=5.0)
    poly(c, HULL3, lip, A(CXN, 5, 30))
    loft(c, rings[0:3], mats, ref, cell=5.5)
    # the long barrel; aft of z 13 the lower facets are burnt black, the roof stays pale to the ragged end
    mid = [nose_ring(13.0, NOSE_ST[2][1])]
    loft(c, [rings[2], mid[0]], mats, ref, cell=6.0)
    loft(c, [mid[0], rings[3]], [CHAR, CHAR, CHAR, HULL, HULL2, HULL, CHAR, CHAR], ref, cell=5.0)
    for k in (0, 1, 2, 6, 7):                                                    # pale teeth reaching into the burn from the front
        ragged(c, HULL if k % 2 else HULL3, mid[0][k] * 1.0005, mid[0][(k + 1) % 8] * 1.0005, mid[0][k] + A(0, 0, 3.6), mid[0][(k + 1) % 8] + A(0, 0, 3.6), ref, 3, 0.2)
    _nose_windows(c, rings[0], rings[1])
    quadg(c, CHAR, *[rings[3][i] for i in (0, 1, 4, 5)], A(CXN, 5, -30), 1, 1)
    poly(c, CHAR, rings[3], A(CXN, 5, -30))
    _nose_extension(c, rings[3], A(CXN, 4.0, 5.0))
    _nose_rim(c, rings[3])
    if c.fine:
        frame_ring(c, rings[3], 0.2, RUST)
    for k in range(2):
        arc_rib(c, A(CXN, 2.0, 21.0), A(1.0, 0, 0), A(0, 1.0, 0), 9.5, 0.2 + k * 0.5, 1.2 + k * 0.5, 0.2, RIB, 8)
    _nose_radar(c)
    _nose_details(c)
    if state == "damaged":
        for k in range(3):
            soot(c, (CXN + (k - 1) * 3.0, 12.0 + k * 3.5), 8.0, 6.0, 0.4 * k, y=12.6 - 0.15 * k)
        for (x, y, z) in ((CXN - 3.0, 4.0, 22.5), (CXN + 2.0, 2.0, 23.2), (CXN + 5.0, 1.8, 21.8)):
            beam(c, RIB, A(x, y, z), A(x + c.rng.uniform(-1.2, 1.2), y + c.rng.uniform(1.5, 3.2), z + c.rng.uniform(0.5, 2.0)), 0.18)
        ember(c, (CXN - 1.5, 2.5, 24.4), 1.4, (0, 0, 1))
        ember(c, (CXN + 3.5, 1.5, 23.8), 1.1, (0, 0, 1))
        ember(c, (CXN - 7.0, 1.4, 23.4), 0.9, (-1, 0, 1))
    return c


def _nose_wreck(c):
    """The keel trough: a low hull bottom with ragged side stumps, bent frame ribs, plates, a fallen roof panel; inside x -17.3..10, z -9.9..24."""
    ref = A(CXN, 8, 6)
    rings = [nose_ring(z, p) for z, p in NOSE_ST]
    low = []
    for z, p in ((19.0, NOSE_ST[3][1]), (4.4, NOSE_ST[2][1]), (-1.7, NOSE_ST[1][1]), (-6.4, NOSE_ST[0][1])):
        r = nose_ring(z, p)
        low.append(np.array([r[7] * A(1, 0, 1) + A(0, 1.2 + 2.2 * (z > 0), 0), r[0], r[1], r[2] * A(1, 0, 1) + A(0, 1.2 + 2.2 * (z > 0), 0)]))
    loft(c, low, [CHAR, HULL3, CHAR], ref, cell=6.0, closed=False)
    for sx in (-1, 1):
        for z0, z1 in ((19.0, 4.4), (4.4, -6.4)):
            a = nose_ring(z0, NOSE_ST[3][1] if z0 > 10 else NOSE_ST[2][1] if z0 > 0 else NOSE_ST[1][1])
            b_ = nose_ring(z1, NOSE_ST[2][1] if z1 > 0 else NOSE_ST[0][1])
            i = 2 if sx > 0 else 6
            ragged(c, CHAR, a[i] * A(1, 0, 1) + A(0, 1.2 + 2.2 * (z0 > 0), z0 * 0), b_[i] * A(1, 0, 1) + A(0, 1.2 + 2.2 * (z1 > 0), 0),
                   a[i] * A(1, 0, 1) + A(0, 3.6 + 1.4 * (z0 > 0), 0) + A(-sx * 0.8, 0, 0), b_[i] * A(1, 0, 1) + A(0, 3.0, 0) + A(-sx * 0.8, 0, 0), ref, 6, 0.3)
    poly(c, CHAR, [low[0][1], low[0][2], low[-1][2], low[-1][1]], A(CXN, 20, 6))
    for k, z in enumerate((17.0, 11.0, 5.0, -1.0)):                                       # frame ribs left standing in the trough
        arc_rib(c, A(CXN, 1.8, z), A(1.0, 0, 0), A(0, 1.0, 0), 10.0 + 0.5 * (k % 2), 0.0, 0.5, 0.18, RIB, 4)
        arc_rib(c, A(CXN, 1.8, z), A(1.0, 0, 0), A(0, 1.0, 0), 10.0 + 0.5 * (k % 2), 2.64, 3.14159, 0.18, RIB, 4)
    debris_field(c, [(-16.0, 9.0, -9.0, 24.0)], 22, 3.0)
    plate_box(c, HULL, (CXN, 1.1, 8.0), (9.0, 0.3, 7.0), 0.3, 0.1, 0.18)
    plate_box(c, HULL2, (CXN + 2, 0.7, 15.0), (7.0, 0.3, 4.5), -0.2, -0.1, 0.1)
    _nose_radar_wreck(c)


def _nose_radar_wreck(c):
    hull(c, HULL2, [A(-8.0, 0.6, 12.0), A(-2.0, 0.6, 12.5), A(-4.0, 1.2, 16.0), A(-8.0, 0.9, 15.0), A(-8.0, 0.9, 12.0), A(-2.0, 0.9, 12.5)])


# ------------------------------------------------------------------------------------------------------------------ crashrib
RIB_BLADE_LOW = [(-1.1, -2.0), (0.6, -0.2), (-1.6, 5.1), (-4.1, 5.1)]
RIB_BLADE_MID = [(-4.1, 5.1), (-1.6, 5.1), (0.6, 10.3), (-1.1, 12.1)]
RIB_BLADE_TIP = [(0.6, 10.3), (3.9, 15.0), (-1.1, 12.1)]


def crashrib(state, lod, seed):
    """x -4.1..3.9, y -2..15, z -10.6..10.4: a curved hull-wall segment (flat centre panel z +-5.9, wings folded back to -4.1 at 5.1 m high) with two bent frame
    blades at z +-6 reaching 15 m, each with lightening holes; the wall's top edge torn and burnt."""
    c = CCtx(state, lod, seed, breach=(-1.5, 9.0, 0.0, 9.0), ledges=[(12.0, 5.0, 0.35)], ground_h=5.0)
    _wreck_burn(c, [(-1.0, 11.0, 0.0, 9.0, 0.95), (-1.0, 0.0, 0.0, 7.0, 0.5)], 0.7)
    b = c.b
    if state == "destroyed":
        _rib_wreck(c)
        return c
    # the wall: a centre panel and two angled wings, each a closed slab 0.5 thick (inside = +x)
    t = A(0.5, 0, 0)
    cen = [A(-1.1, -2.0, -5.9), A(-1.1, -2.0, 5.9), A(-1.1, 9.0, 5.9), A(-1.1, 9.0, -5.9)]
    hull(c, HULL2, cen + [q + t for q in cen])
    for sz in (-1, 1):
        wing = [A(-1.1, -2.0, sz * 5.9), A(-4.1, 5.1, sz * 10.5), A(-1.1, 9.0, sz * 5.9)]
        hull(c, HULL2, wing + [q + t for q in wing] + [A(-1.1, 2.0, sz * 5.9) + t * 2])
        w2 = [A(-4.1, 5.1, sz * 10.5), A(-1.1, 9.0, sz * 5.9), A(-1.1, 12.1, sz * 5.9)]
        ragged(c, CHAR, A(-4.1, 5.1, sz * 10.5), A(-1.1, 9.0, sz * 5.9), A(-4.1, 6.4, sz * 10.5), A(-1.1, 12.1, sz * 5.9), A(5.0, 5, 0), 4, 0.3, ref2=A(-8.0, 5, 0))
    ragged(c, RUST, A(-1.1, 9.0, -5.9), A(-1.1, 9.0, 5.9), A(-1.1, 12.1, -5.9), A(-1.1, 12.1, 5.9), A(5.0, 5, 0), 11, 0.2, ref2=A(-8.0, 5, 0))
    ragged(c, CHAR, A(-1.12, 9.0, -5.9), A(-1.12, 9.0, 5.9), A(-1.12, 10.6, -5.9), A(-1.12, 10.6, 5.9), A(5.0, 5, 0), 7, 0.3, ref2=A(-8.0, 5, 0))
    ragged(c, HULL, A(-1.1, 6.4, -5.9), A(-1.1, 6.4, 5.9), A(-1.1, 10.3, -5.9), A(-1.1, 10.3, 5.9), A(5.0, 5, 0), 7, 0.3, ref2=A(-8.0, 5, 0))
    # exposed edge strap and rust runs
    if c.fine:
        for z in (-5.9, 5.9):
            beam(c, RUST, A(-1.0, -2.0, z), A(-1.0, 9.0, z), 0.18)
        for k in range(3):
            panel_seams(c, A(-1.15, -1.9 + k * 3.6, -5.8), A(-1.15, -1.9 + k * 3.6, 5.8), A(8.0, 5, 0), 0.08)
    # two bent frame blades with lightening holes
    for zc in (-6.0, 6.0):
        for pts, mat in ((RIB_BLADE_LOW, HULL2), (RIB_BLADE_MID, HULL2), (RIB_BLADE_TIP, HULL2)):
            hull(c, mat, [A(x, y, zc + dz) for (x, y) in pts for dz in (-0.35, 0.35)])
        if c.fine:
            for (hx, hy) in ((-1.1, 0.4), (-2.4, 2.6), (-3.0, 4.6), (-2.2, 7.0), (-1.0, 9.4), (0.8, 11.8)):
                for sgn in (-1, 1):
                    c.b.disc(GLASS, (hx, hy, zc + sgn * 0.37), 0.5, (0, 0, sgn), 8)
    # struts tying the blades to the wall
    for y in (1.5, 6.5):
        beam(c, RIB, A(-1.0, y, -6.0), A(-1.0, y, 6.0), 0.2)
    if state == "damaged":
        for k in range(3):
            soot(c, (-0.5, -4.5 + k * 4.5), 4.0, 5.5, 0.1 * k, y=0.35)
        for z in (-3.0, 1.5, 4.5):
            beam(c, RIB, A(-1.0, 12.0, z), A(-0.4 + c.rng.uniform(-1, 1), 14.2, z + c.rng.uniform(-1, 1)), 0.15)
        ember(c, (-1.7, 11.4, -2.0), 1.2, (-1, 0, 0))
        ember(c, (-1.7, 10.4, 3.0), 0.9, (-1, 0, 0))
        ember(c, (-4.4, 5.8, 8.8), 0.8, (-1, 0, 0))
    return c


def _rib_wreck(c):
    """The wall fallen forward: a low charred slab with the blades lying beside it, inside x -4.1..3.9, z -10.6..10.4."""
    t = A(0.6, 0, 0)
    hull(c, CHAR, [A(-3.6, 0.2, -8.0), A(-3.6, 0.2, 8.0), A(3.0, 0.2, 8.0), A(3.0, 0.2, -8.0), A(-3.6, 0.7, -8.0), A(-3.6, 0.7, 8.0), A(3.0, 0.9, 8.0), A(3.0, 0.9, -8.0)])
    hull(c, HULL3, [A(-3.0, 0.9, -5.0), A(-3.0, 0.9, 5.0), A(1.5, 1.6, 4.0), A(1.5, 1.6, -4.0), A(-3.0, 1.2, -5.0), A(-3.0, 1.2, 5.0), A(1.5, 1.9, 4.0), A(1.5, 1.9, -4.0)])
    for zc, zr in ((-6.0, -1), (6.0, 1)):
        hull(c, HULL2, [A(-3.5, 0.4, zc - 0.35), A(-3.5, 0.4, zc + 0.35), A(3.5, 0.4, zc - 0.35), A(3.5, 0.4, zc + 0.35), A(-3.5, 1.8, zc - 0.35), A(-3.5, 1.8, zc + 0.35), A(3.0, 2.5, zc - 0.35), A(3.0, 2.5, zc + 0.35)])
    for k, z in enumerate((-7.0, -2.0, 3.0)):
        arc_rib(c, A(0.0, 0.3, z), A(1.0, 0, 0), A(0, 1.0, 0), 3.4, 0.4, 2.6, 0.15, RIB, 6)
    debris_field(c, [(-3.8, 3.6, -10.0, 9.8)], 8, 2.0, size=(1.2, 3.2))


# ------------------------------------------------------------------------------------------------------------------ crashengine
ENG_BASE = A(6.3, -3.0, -8.3)            # bottom centre of the nacelle (buried)
ENG_TOP = A(6.45, 15.4, -0.7)            # centre of the mouth rim
ENG_AX = unit(ENG_TOP - ENG_BASE)


def _eng_ring(t, R):
    """A hexagonal ring on the nacelle's axis at fraction t (0 base .. 1 rim) with corner radius R; corner 0 faces -x."""
    return circ(ENG_BASE + (ENG_TOP - ENG_BASE) * t, ENG_AX, R, 6, math.pi, up=(0, 0, 1.0))


def crashengine(state, lod, seed):
    """x -11.5..11.9, y -5..18.6, z -12.5..3.5: a leaning hexagonal engine nacelle (about 20 degrees to +z), pale blue with a burnt black belt, an open bright mouth with a
    dark rim at the top and a black pylon spike leaning out to -x."""
    c = CCtx(state, lod, seed, breach=(6.0, 8.0, -4.0, 9.0), ledges=[(15.0, 6.0, 0.4), (8.0, 3.0, 0.3)], ground_h=6.0)
    _wreck_burn(c, [(6.0, 6.0, -4.0, 8.5, 0.98), (6.0, 15.0, 0.0, 6.0, 0.45), (-8.0, 8.0, -9.0, 8.0, 0.9)], 0.85)
    b = c.b
    if state == "destroyed":
        _engine_wreck(c)
        return c
    ref = ENG_BASE + (ENG_TOP - ENG_BASE) * 0.5
    ts = [0.0, 0.26, 0.38, 0.62, 0.74, 1.0]
    Rs = [6.5, 6.3, 6.2, 5.9, 5.6, 5.2]
    rings = [_eng_ring(t, R) for t, R in zip(ts, Rs)]
    loft(c, rings[0:2], [HULL, HULL3, HULL, HULL2, HULL, HULL3], ref, cell=6.0)             # lower pale skin
    loft(c, rings[1:4], CHAR, ref, cell=6.0)                                                 # burnt belt
    loft(c, rings[3:6], [HULL2, HULL, HULL3, HULL, HULL2, HULL], ref, cell=6.0)              # upper pale skin to the rim
    # ragged transition: pale teeth reaching up into the belt from below, down into it from above
    for k in range(6):
        k2 = (k + 1) % 6
        lo_a, lo_b = _eng_ring(0.26, 6.33)[k], _eng_ring(0.26, 6.33)[k2]
        hi_a, hi_b = _eng_ring(0.5, 6.1)[k], _eng_ring(0.5, 6.1)[k2]
        ragged(c, (HULL, HULL3)[k % 2], lo_a, lo_b, hi_a, hi_b, ref, 3, 0.2)
        up_a, up_b = _eng_ring(0.62, 5.93)[k], _eng_ring(0.62, 5.93)[k2]
        dn_a, dn_b = _eng_ring(0.46, 6.1)[k], _eng_ring(0.46, 6.1)[k2]
        ragged(c, (HULL2, HULL)[k % 2], up_a, up_b, dn_a, dn_b, ref, 3, 0.2)
    # mouth: a dark rim, bright lining, a deep dark throat
    rim_o, rim_i = _eng_ring(1.0, 5.2), _eng_ring(1.0, 4.4)
    for k in range(6):
        k2 = (k + 1) % 6
        poly(c, RIB, [rim_o[k], rim_o[k2], rim_i[k2], rim_i[k]], ref + A(0, -30, 0))
    inner = [_eng_ring(1.0, 4.4), _eng_ring(0.86, 4.3), _eng_ring(0.72, 4.0)]
    loft(c, inner, HULL2, None, cell=6.0, flip=True)
    # the throat: a dim, warm ember glow with a falloff (amber centre, deep orange ring, charred rim), no glow once destroyed
    poly(c, CHAR, inner[2], ref - A(0, 60, 0))
    poly(c, "lamp_ember2", _eng_ring(0.72, 3.3) + A(0, 0.04, 0), ref - A(0, 60, 0))
    poly(c, "lamp_ember", _eng_ring(0.72, 1.9) + A(0, 0.08, 0), ref - A(0, 60, 0))
    # engine ribs inside the mouth and bell fins
    if c.fine:
        for k in range(6):
            beam(c, RIB, rim_i[k], _eng_ring(0.78, 3.6)[k], 0.14)
    poly(c, HULL3, rings[0], ref + A(0, 40, 0))
    # panel straps up the corners, a round hatch panel
    if c.fine:
        for k in range(6):
            panel_seams(c, rings[0][k] * 0.99 + rings[1][k] * 0.01, rings[1][k], ref, 0.12)
            panel_seams(c, rings[3][k], rings[5][k], ref, 0.12)
        for kk in (0, 3):
            ctr = (_eng_ring(0.82, 5.5)[kk] + _eng_ring(0.82, 5.5)[(kk + 1) % 6]) / 2
            nrm = unit(ctr - (ENG_BASE + (ENG_TOP - ENG_BASE) * 0.82))
            c.b.disc(HULL3, ctr + nrm * 0.06, 1.4, tuple(nrm), 12)
    # pale debris lattice over the burnt belt: thin bars up the corners' faces and cross bars between them
    for k in range(6):
        k2 = (k + 1) % 6
        for lv in range(5 if c.fine else 3):
            u = (lv + 0.5) / (5 if c.fine else 3)
            for (t0, t1) in ((0.29, 0.47),):
                pa = _eng_ring(t0, 6.4)[k] * (1 - u) + _eng_ring(t0, 6.4)[k2] * u
                pb = _eng_ring(t1, 6.2)[k] * (1 - u) + _eng_ring(t1, 6.2)[k2] * u
                if (lv + k) % 3 != 2:
                    c.b.tube(HULL2, pa, pb, 0.07, 3, caps=False)
        for ti in range(3 if c.fine else 2):
            t = 0.31 + 0.07 * ti
            q0, q1 = _eng_ring(t, 6.4 - 0.4 * (t - 0.3))[k], _eng_ring(t, 6.4 - 0.4 * (t - 0.3))[k2]
            if (ti + k) % 4 != 1:
                c.b.tube(HULL2, q0, q1, 0.07, 3, caps=False)
    # the pylon: a thin black leaning blade from the nacelle's base out to its tip at -x
    tip, base1, base2 = A(-10.0, 18.6, -6.7), A(1.2, -0.9, -8.5), A(-11.3, 6.6, -11.6)
    nrm = unit(np.cross(base1 - tip, base2 - tip))
    hull(c, CHAR, [tip, base1, base2] + [q + nrm * 0.35 for q in (tip, base1, base2)] + [A(-11.1, 6.9, -11.7)])
    if c.fine:
        beam(c, RIB, A(-11.0, 7.0, -11.7), A(-10.0, 18.4, -6.8), 0.14)
    ragged(c, CHAR, base1, tip, base1 + A(-3.0, 3.0, 0), tip + A(-2.4, 0.5, -1.5), A(0, 5, -9), 7, 0.4, ref2=A(-10, 5, 5))
    ragged(c, CHAR, base2, tip, base2 + A(-1.6, 0.4, -0.6), tip + A(-1.4, -0.4, -0.2), A(0, 5, -9), 5, 0.4, ref2=A(-10, 5, 5))
    if state == "damaged":
        for k in range(4):
            soot(c, (6.0 + c.rng.uniform(-4, 4), -4.5 + c.rng.uniform(-4, 4)), 6.0, 5.0, 0.3 * k, y=0.35)
        for k in range(3):
            q = _eng_ring(0.45, 6.2)[k * 2]
            beam(c, RIB, q, q + A(c.rng.uniform(-1, 1), c.rng.uniform(1.2, 3.0), c.rng.uniform(-1, 1)), 0.16)
        ember(c, tuple(_eng_ring(0.4, 6.25)[1]), 1.4, (0, 0, 1))
        ember(c, tuple(_eng_ring(0.5, 6.1)[4]), 1.2, (0, 0, 1))
        ember(c, tuple(_eng_ring(0.34, 6.25)[2]), 1.0, (1, 0, 0))
    return c


def _engine_wreck(c):
    """The nacelle fallen on its side: a hexagonal drum along x with a ragged break, the mouth ring open at +x, a keel plate and debris; x -11.5..11.9, z -12.5..3.5."""
    ctr = A(0.0, 3.8, -5.0)
    ax = A(1.0, 0, 0)
    ref = ctr
    rings = [circ(ctr + ax * x, ax, 4.4 - 0.1 * i, 6, 0.0, up=(0, 1.0, 0)) for i, x in enumerate((-7.0, -3.0, 1.0, 5.0, 8.5))]
    loft(c, rings[2:5], [HULL, HULL3, HULL2, HULL, CHAR, HULL3], ref, cell=6.0)
    loft(c, rings[0:3], [CHAR, CHAR, CHAR, HULL, CHAR, CHAR], ref, cell=6.0)
    ragged(c, CHAR, rings[0][2], rings[0][3], rings[0][2] + A(-2.5, 0, 0), rings[0][3] + A(-2.5, 0, 0), ref, 3, 0.3)
    ragged(c, CHAR, rings[0][1], rings[0][2], rings[0][1] + A(-3.5, 0, 0), rings[0][2] + A(-3.5, 0, 0), ref, 3, 0.3)
    poly(c, CHAR, rings[0], ctr + ax * 40)
    rim_o, rim_i = circ(ctr + ax * 10.0, ax, 4.4, 6), circ(ctr + ax * 10.0, ax, 3.6, 6)
    loft(c, [rings[4], rim_o], HULL, ref, cell=6.0)
    for k in range(6):
        poly(c, RIB, [rim_o[k], rim_o[(k + 1) % 6], rim_i[(k + 1) % 6], rim_i[k]], ctr - ax * 40)
    poly(c, CHAR, rim_i, ctr - ax * 40)
    debris_field(c, [(-11.0, 11.5, -12.0, -9.0), (-11.0, -8.0, -9.0, 3.0), (8.5, 11.5, -9.0, 3.0), (-6.0, 8.0, -0.5, 3.0)], 14, 2.0, size=(1.2, 3.4))
    hull(c, CHAR, [A(-1.0, 0.2, -11.0), A(-1.0, 0.2, -2.0), A(11.0, 0.2, -2.0), A(11.0, 0.2, -11.0), A(-1.0, 0.6, -10.5), A(-1.0, 0.6, -2.5), A(10.5, 0.7, -2.5), A(10.5, 0.7, -10.5)])
    tip, base1, base2 = A(-10.0, 5.6, -6.7), A(1.2, 0.4, -8.5), A(-11.3, 0.8, -11.6)
    hull(c, CHAR, [tip, base1, base2, tip + A(0, 0.35, 0), base1 + A(0, 0.35, 0), base2 + A(0, 0.35, 0)])


# ------------------------------------------------------------------------------------------------------------------ crashtail
TAIL_C0, TAIL_C1 = A(0.0, -1.1, -5.5), A(0.0, 13.3, 1.4)       # centres of the burnt dome's base and crown


def _tail_ring(y, R, n=12):
    t = (y - TAIL_C0[1]) / (TAIL_C1[1] - TAIL_C0[1])
    ctr = TAIL_C0 + (TAIL_C1 - TAIL_C0) * t
    return np.array([ctr + A(R * 1.06 * math.cos(TAU * k / n), 0, R * math.sin(TAU * k / n)) for k in range(n)])


def crashtail(state, lod, seed):
    """x -15.4..15.7, y -1.1..39.1, z -19.4..27.6: a burnt dome on the ground with a torn upper rim, a pale drum cap with a spoked face on top, two long prongs reaching
    along the ground to +z, a torn panel standing on +x and the tall swept fin leaning out to -x (39 m)."""
    c = CCtx(state, lod, seed, breach=(0.0, 12.0, 4.0, 13.0), ledges=[(21.0, 5.0, 0.35), (13.0, 5.0, 0.3)], ground_h=8.0)
    _wreck_burn(c, [(0.0, 8.0, -2.0, 16.0, 1.0), (-10.0, 6.0, 0.0, 12.0, 0.8), (11.0, 12.0, 4.0, 9.0, 0.85), (0.0, 17.0, 14.0, 9.0, 0.5)], 0.8)
    b = c.b
    if state == "destroyed":
        _tail_wreck(c)
        return c
    n = 12 if c.fine else 8
    ys = [-1.1, 6.0, 11.4, 13.3]
    Rs = [14.4, 11.7, 8.6, 3.0]
    rings = [_tail_ring(y, R, n) for y, R in zip(ys, Rs)]
    ref = A(0.0, 5.0, -1.0)
    loft(c, rings, [CHAR] * n, ref, cell=7.0)
    # pale remnants of the skin low on the -z side, torn upward into the burn
    for k in range(n):
        if math.sin(TAU * k / n) < 0.1:
            a, bb = _tail_ring(-1.0, 14.45, n)[k], _tail_ring(-1.0, 14.45, n)[(k + 1) % n]
            a2, b2 = _tail_ring(7.0, 11.4, n)[k], _tail_ring(7.0, 11.4, n)[(k + 1) % n]
            ragged(c, HULL, a, bb, a2, b2, ref, 3, 0.25)
    poly(c, CHAR, rings[3], ref + A(0, -30, 0))
    # the open +z flank: bent frame ribs rising from the ground
    for k, x in enumerate((-9.0, -3.0, 3.0, 9.0)):                                    # ribs of the open +z flank, as arcs of the dome
        ya = [1.0, 5.0, 9.0, 12.0]
        pts = [A(x * (1 - 0.06 * i), ya[i], 1.0 + 7.5 * (1 - (ya[i] / 14.0)) * (1 - abs(x) / 20.0) + (1.0 if i == 0 else 0)) for i in range(4)]
        c.b.sweep(RIB, pts, 0.2, 5 if c.fine else 4, caps=True)
    # the pale cap: an elliptical drum with a spoked face toward +z
    lathe_z(c, HULL, [(11.3, 6.7, 4.4, 17.3), (13.0, 6.9, 4.5, 17.3), (16.0, 6.9, 4.5, 17.3), (18.0, 6.2, 4.0, 17.3), (18.5, 5.4, 3.5, 17.3)], 14 if c.fine else 8, cap_front=True, cap_back=True)
    c.b.disc(HULL3, (0.0, 17.3, 18.53), 2.0, (0, 0, 1), 10 if c.fine else 6)
    for k in range(6 if c.fine else 3):
        th = TAU * k / 6
        c.b.box(RIB, (math.cos(th) * 3.2, 17.3 + math.sin(th) * 2.2, 18.62), (2.6, 0.3, 0.1), axis_angle(V([0, 0, 1.0]), th * 0.8))
    # two prongs along the ground from the cap to +z
    for sx in (-1, 1):
        top = [A(sx * 5.1, 14.2, 17.6), A(sx * 1.8, 12.9, 18.4)]
        tip = [A(sx * 5.0, 0.2, 27.6), A(sx * 1.7, -1.2, 26.9)]
        hull(c, HULL, [q + A(0, d, 0) for q in top + tip for d in (-0.45, 0.45)])
        if c.fine:
            panel_seams(c, (top[0] + top[1]) / 2 + A(0, 0.5, 0), (tip[0] + tip[1]) / 2 + A(0, 0.5, 0), A(0, -10, 10), 0.1)
    # the torn panel standing on +x
    pan = [A(11.9, 11.8, -3.4), A(15.7, 17.8, -0.7), A(15.4, 25.9, 10.6), A(12.6, 22.1, 11.5), A(7.5, 15.8, 13.2), A(8.5, 11.5, 1.9)]
    nrm = unit(np.cross(pan[1] - pan[0], pan[3] - pan[0]))
    hull(c, HULL, pan + [q - nrm * 0.5 for q in pan])
    # the fin: a long swept blade, root low on -x, tip 39 m up
    fin = [A(-11.7, 5.9, 5.8), A(-8.5, 5.7, -6.0), A(-7.1, 6.1, -6.3), A(-15.4, 31.0, -0.7), A(-15.1, 39.1, 10.7), A(-10.0, 11.0, 9.0)]
    fn = unit(np.cross(fin[3] - fin[1], fin[4] - fin[1]))
    hull(c, HULL, fin + [q + fn * 0.6 for q in fin])
    if c.fine:
        for (t, w) in ((0.28, 1.4), (0.5, 1.2), (0.7, 1.0)):                        # panel hatches and seams on the fin face
            p = A(-9.5, 5.9, 0.0) * (1 - t) + A(-15.2, 33.0, 6.0) * t
            c.b.quad(HULL3, p + fn * 0.65, unit(A(0.2, 1.0, 0.1)), unit(np.cross(fn, A(0.2, 1.0, 0.1))), w * 1.4, w * 1.8, (0, 0, 1, 1), normal=tuple(fn))
        panel_seams(c, A(-11.0, 6.5, 4.0) + fn * 0.6, A(-15.0, 37.5, 9.5) + fn * 0.6, A(0, 10, 0) + fn * -30, 0.15)
    if state == "damaged":
        for k in range(4):
            soot(c, (c.rng.uniform(-6, 6), c.rng.uniform(-14, 6)), 9.0, 7.0, 0.35 * k, y=0.4)
        for q in ((-6.0, 11.0, 1.0), (4.0, 12.0, 2.0), (9.0, 8.0, 4.0)):
            beam(c, RIB, A(*q), A(q[0] + c.rng.uniform(-2, 2), q[1] + c.rng.uniform(2.0, 4.5), q[2] + c.rng.uniform(-1.5, 1.5)), 0.2)
        ember(c, (9.0, 9.0, 4.0), 1.6, (1, 0, 0))
        ember(c, (-5.0, 11.0, 4.8), 1.3, (0, 0, 1))
        ember(c, (1.0, 12.4, 3.0), 1.2, (0, 1, 0))
    return c


def _tail_wreck(c):
    """A flattened ring of burnt dome plating, the pale drum cap on its side, the fin fallen along -x and the prongs; inside x -15.4..15.7, z -19.4..27.6."""
    ref = A(0.0, 3.0, -4.0)
    n = 12 if c.fine else 8
    r0 = np.array([A(1.06 * 14.2 * math.cos(TAU * k / n), 0.15, -5.5 + 13.6 * math.sin(TAU * k / n)) for k in range(n)])
    r1 = np.array([A(1.06 * 13.0 * math.cos(TAU * k / n), 2.6 + 0.8 * math.sin(k * 1.7), -5.0 + 12.4 * math.sin(TAU * k / n)) for k in range(n)])
    loft(c, [r0, r1], CHAR, ref, cell=7.0)
    for k in range(n):
        if k % 2 == 0:
            ragged(c, CHAR, r1[k], r1[(k + 1) % n], r1[k] + A(0, 1.6, 0), r1[(k + 1) % n] + A(0, 1.6, 0), ref, 3, 0.2, ref2=A(0, 3, -5) * 1.0 + A(0, -20, 0))
    hull(c, CHAR, [A(x, y, z) for (x, z) in ((-10.0, -14.0), (10.0, -14.0), (11.0, 4.0), (-11.0, 4.0)) for y in (0.15, 0.6)])
    lathe_z(c, HULL, [(-3.0, 4.0, 2.2, 2.4), (0.5, 4.2, 2.4, 2.4), (4.0, 3.6, 2.0, 2.2)], 10 if c.fine else 6)                     # the cap on its side
    c.b.M = (axis_angle(V([0, 1.0, 0]), 0.0), V([0.0, 0.0, 14.0]))
    lathe_z(c, HULL, [(-3.0, 4.0, 2.2, 2.4), (0.5, 4.2, 2.4, 2.4), (4.0, 3.6, 2.0, 2.2)], 10 if c.fine else 6)
    c.b.M = None
    fin = [A(-11.0, 0.4, -12.0), A(-9.0, 0.4, -12.0), A(-12.5, 0.4, 20.0), A(-14.5, 0.5, 21.0), A(-13.0, 1.3, 8.0), A(-10.0, 1.3, -8.0)]
    hull(c, HULL, fin)
    hull(c, HULL, [A(-10.0, 0.3, 4.0), A(-13.0, 0.3, 4.0), A(-14.0, 1.6, 12.0), A(-11.0, 1.6, 12.0), A(-11.0, 0.3, 4.0), A(-12.5, 0.3, 14.0)])
    for sx in (-1, 1):
        hull(c, HULL, [A(sx * 5.0, 0.3, 14.0), A(sx * 1.8, 0.3, 14.0), A(sx * 5.0, 0.9, 27.0), A(sx * 1.7, 0.9, 26.8), A(sx * 5.0, 1.2, 14.0), A(sx * 1.8, 1.2, 14.0)])
    pan = [A(12.0, 0.3, -3.0), A(15.0, 0.3, -1.0), A(15.0, 1.4, 10.0), A(9.0, 1.1, 12.0), A(9.0, 0.3, 2.0)]
    hull(c, HULL2, pan)
    for k, x in enumerate((-8.0, 0.0, 8.0)):
        arc_rib(c, A(x, 0.2, -4.0), A(0, 0, 1.0), A(0, 1.0, 0), 5.0, 0.3, 2.4, 0.18, RIB, 6)
    debris_field(c, [(-14.0, -11.0, -18.0, 20.0), (-9.0, 14.0, 14.5, 26.0), (-14.0, 14.0, -19.0, -15.0), (8.0, 15.0, -14.0, 14.0)], 18, 2.4, size=(1.5, 4.2))


# ------------------------------------------------------------------------------------------------------------------ crashwing
WING_FX, WING_YC = -4.5, 1.4          # fuselage block centre (x) and centre height; its tube lies along z
POD_C = A(8.5, 2.5, 0.0)              # the wing-root pod: a hexagonal tube along z, open toward -z


def _wing_ring(z, hx=7.0, hy=8.4, k=1.0):
    """A hexagon (corners at the sides) of the fuselage block at station z, in the x-y plane."""
    return np.array([(WING_FX - hx * 0.5 * k, WING_YC + hy * k, z), (WING_FX + hx * 0.5 * k, WING_YC + hy * k, z), (WING_FX + hx * k, WING_YC, z),
                     (WING_FX + hx * 0.5 * k, WING_YC - hy * k, z), (WING_FX - hx * 0.5 * k, WING_YC - hy * k, z), (WING_FX - hx * k, WING_YC, z)], float)


def _pod_ring(z, R=6.5):
    return np.array([POD_C + A(R * math.cos(TAU * k / 6), R * 0.9 * math.sin(TAU * k / 6), z) for k in range(6)], float)


def crashwing(state, lod, seed):
    """x -11.6..41.6, y -7..14.8, z -12.5..19: a hexagonal fuselage block lying along z (torn and open at -z), the wing-root pod beside it (a hexagonal tube with a
    bright open mouth at -z and a white gun dome at +z), twin gun barrels and domes on the block, and the long swept wing blade rising 12 m to its tip at +x."""
    c = CCtx(state, lod, seed, breach=(-2.0, 4.0, -6.0, 11.0), ledges=[(9.8, 4.0, 0.35)], ground_h=8.0)
    _wreck_burn(c, [(-4.5, 2.0, -12.5, 14.0, 0.95), (10.0, 4.0, 6.0, 9.0, 0.35), (30.0, 8.0, 8.0, 13.0, 0.3)])
    b = c.b
    if state == "destroyed":
        _wing_wreck(c)
        return c
    ref = A(WING_FX, WING_YC, 2.0)
    zs = [-12.5, -6.5, 2.0, 15.5]
    rings = [_wing_ring(z) for z in zs]
    # edges: 0 top 1 upper right 2 lower right 3 bottom 4 lower left 5 upper left
    loft(c, rings[1:4], [HULL2, HULL, HULL3, HULL3, HULL3, HULL], ref, cell=6.5)
    loft(c, rings[0:2], [CHAR] * 6, ref, cell=6.5)
    r1b = _wing_ring(-6.55, k=1.003)
    for k in (0, 1, 5, 4):
        k2 = (k + 1) % 6
        ragged(c, HULL, r1b[k], r1b[k2], r1b[k] + A(0, 0, -3.4), r1b[k2] + A(0, 0, -3.4), ref, 3, 0.25)
    r_lip = _wing_ring(-12.5)
    if c.fine:
        frame_ring(c, _wing_ring(-12.45, k=0.97), 0.22, RUST)
        frame_ring(c, _wing_ring(-9.0, k=0.99), 0.2, RIB)
        for k in range(6):
            beam(c, RIB, _wing_ring(-12.45, k=0.97)[k], _wing_ring(-6.5, k=0.99)[k], 0.14)
    poly(c, CHAR, _wing_ring(-6.4, k=0.99), A(WING_FX, WING_YC, -40))
    poly(c, HULL, rings[3], A(WING_FX, WING_YC, -40))
    # the pod: pale hexagonal tube, bright lining and dark rim at the open -z end, a white gun dome on the +z face
    pz = [-7.0, -2.0, 6.0, 15.5]
    prings = [_pod_ring(z, R) for z, R in zip(pz, (6.5, 6.5, 6.4, 6.2))]
    pref = A(POD_C[0], POD_C[1], 4.0)
    loft(c, prings, [HULL, HULL2, HULL, HULL3, HULL3, HULL3], pref, cell=6.5)
    rim_o, rim_i = _pod_ring(-7.0, 6.5), _pod_ring(-7.0, 5.6)
    for k in range(6):
        poly(c, RIB, [rim_o[k], rim_o[(k + 1) % 6], rim_i[(k + 1) % 6], rim_i[k]], A(POD_C[0], POD_C[1], 40))
    lin = [_pod_ring(-7.0, 5.6), _pod_ring(-4.0, 5.5), _pod_ring(-1.0, 5.2)]
    loft(c, lin, HULL2, None, cell=6.5, flip=True)
    poly(c, HULL2, lin[2], A(POD_C[0], POD_C[1], 40))
    poly(c, HULL, prings[3], pref)
    dome_r = 4.0
    seg = 12 if c.fine else 7
    c.b.M = (np.eye(3), A(POD_C[0], POD_C[1] + 0.2, 0.0))
    lathe_z(c, HULL2, [(15.5, 3.6, 3.3, 0.0), (17.0, 3.1, 2.8, 0.0), (18.4, 1.7, 1.5, 0.0), (19.0, 0.0, 0.0, 0.0)], seg)
    c.b.M = None
    # root fairing between pod and wing, the wing blade
    root = [A(14.5, 1.5, -3.8), A(14.5, 2.9, -3.8), A(14.5, 4.4, 13.3), A(14.5, 5.8, 13.3)]
    tip = [A(39.8, 12.0, 4.8), A(41.6, 13.8, 5.0), A(40.0, 14.0, 12.0), A(41.4, 14.8, 11.9)]
    hull(c, HULL, root + tip + [A(12.0, 0.8, -3.8), A(12.0, 5.2, 13.3), A(12.0, 0.3, 4.0)])
    if c.fine:
        for t in (0.25, 0.5, 0.75):
            a_ = (root[1] * (1 - t) + tip[0] * t) + A(0, 0.06, 0)
            b_ = (root[3] * (1 - t) + tip[3] * t) + A(0, 0.06, 0)
            panel_seams(c, a_, b_, A(a_[0], -50, a_[2]), 0.12)
        for t, w in ((0.35, 3.2), (0.65, 2.6)):                                                       # lighter patch panels on the blade
            p = (root[1] * (1 - t) + tip[0] * t + root[3] * (1 - t) + tip[3] * t) / 2
            c.b.box(HULL2, p + A(0, 0.1, 0), (w, 0.06, w * 1.2), axis_angle(V([0, 0, 1.0]), 0.34))
    # guns on the block: twin barrels along z, housings, two small domes at the +z end
    for gx in (-8.3, -5.0):
        beam(c, HULL3, A(gx, 10.4, -6.6), A(gx, 10.4, 6.1), 0.5)
        c.b.box(HULL2, (gx, 9.9, 2.5), (1.5, 1.0, 3.4))
    c.b.box(HULL2, (-6.65, 10.5, 3.0), (5.6, 0.9, 2.8))
    for (gx, gz, r) in ((-8.2, 13.6, 1.9), (-4.6, 13.6, 1.9)):
        c.b.revolve(HULL2, [(0.0, 9.8), (r, 9.8), (r, 9.8 + r * 0.4), (r * 0.75, 9.8 + r * 0.85), (0.0, 9.8 + r)], seg, cx=gx, cz=gz, uref=2.0)
    if state == "damaged":
        for k in range(4):
            soot(c, (c.rng.uniform(-8, 10), c.rng.uniform(-10, 14)), 9.0, 8.0, 0.4 * k, y=0.4)
        for q in ((-9.0, 3.0, -12.0), (-3.0, 2.0, -12.0), (-6.0, 8.5, -11.0)):
            beam(c, RIB, A(*q), A(q[0] + c.rng.uniform(-1.5, 1.5), q[1] + c.rng.uniform(1.5, 3.5), q[2] - c.rng.uniform(0.5, 1.5)), 0.2)
        ember(c, (-5.0, 3.0, -12.7), 1.8, (0, 0, -1))
        ember(c, (-9.0, 6.0, -12.6), 1.2, (0, 0, -1))
        ember(c, (-1.0, 0.0, -12.6), 1.0, (0, 0, -1))
    return c


def _wing_wreck(c):
    """A flattened fuselage block (low torn wall stubs and a charred floor), the pod's drum on its side, the wing blade fallen flat along +x, the gun domes and
    barrels lying loose; x -11.6..41.6, z -12.5..19.1."""
    ref = A(-4.5, 2.0, 2.0)
    hull(c, CHAR, [A(x, y, z) for (x, z) in ((-11.0, -11.5), (2.5, -11.5), (2.5, 15.0), (-11.0, 15.0)) for y in (0.2, 0.6)])
    for x in (-11.0, 2.5):
        ragged(c, CHAR, A(x, 0.5, -11.5), A(x, 0.5, 15.0), A(x, 3.4, -11.5), A(x, 3.4, 15.0), ref, 8, 0.25, ref2=A(x * 3, 2.0, 2.0))
    for z in (-11.0, 14.5):
        arc_rib(c, A(-4.5, 0.2, z), A(1.0, 0, 0), A(0, 1.0, 0), 7.0, 0.25, 2.9, 0.2, RIB, 8)
    hull(c, HULL, [A(12.0, 0.3, -3.8), A(12.0, 0.3, 13.3), A(41.0, 0.3, 11.0), A(40.0, 0.3, 3.0), A(12.0, 1.2, -3.8), A(12.0, 1.2, 13.3), A(41.0, 0.9, 11.0), A(40.0, 0.9, 3.0)])
    hull(c, HULL2, [A(12.5, 1.2, 0.0), A(12.5, 1.2, 12.0), A(30.0, 1.0, 10.0), A(30.0, 1.0, 5.0), A(12.5, 1.5, 0.0), A(30.0, 1.4, 5.0)])
    ctr = A(8.5, 3.2, 3.0)
    ax = A(0, 0, 1.0)
    rg = [circ(ctr + ax * z, ax, 3.4 - 0.1 * i, 6, 0.0) for i, z in enumerate((-4.0, 0.0, 4.0, 8.0))]
    loft(c, rg, [HULL, HULL2, HULL, CHAR, HULL3, HULL], ctr, cell=6.0)
    poly(c, CHAR, rg[0], ctr + ax * 40)
    for k, x in enumerate((-8.2, -5.0)):
        beam(c, HULL3, A(x, 1.0, -7.0 + 3.0 * k), A(x + 0.5, 1.1, 5.0), 0.5)
    seg = 10 if c.fine else 6
    c.b.revolve(HULL2, [(0.0, 0.2), (3.0, 0.2), (2.8, 1.2), (1.8, 2.0), (0.0, 2.3)], seg, cx=18.0, cz=14.8, uref=2.0)
    c.b.revolve(HULL2, [(0.0, 0.2), (1.9, 0.2), (1.7, 1.0), (0.0, 1.6)], seg, cx=-6.0, cz=14.0, uref=2.0)
    debris_field(c, [(-11.0, 2.5, -12.0, 18.5), (2.5, 15.0, -9.0, 4.0), (12.0, 41.0, -3.5, 14.0)], 24, 1.8, size=(1.4, 4.0))

# ------------------------------------------------------------------------------------------------------------------ registry
MEMBERS = {
    "crashnose": (crashnose, "wrecked dropship nose: faceted barrel, cockpit window band, torn visor, charred ragged rear, radar fin"),
    "crashtail": (crashtail, "wrecked dropship tail: burnt dome, spoked drum cap, two ground prongs, torn side panel and a 39 m swept fin"),
    "crashwing": (crashwing, "wrecked dropship wing: hexagonal fuselage stub open at one end, gun barrels and domes, long swept wing blade"),
    "crashrib": (crashrib, "wrecked dropship hull rib: curved wall segment with two bent frame blades and lightening holes"),
    "crashengine": (crashengine, "wrecked engine nacelle: leaning hexagonal tube with a burnt belt, bright open mouth and a black pylon spike"),
    "crashshanty1": (crashshanty1, "salvage hut: mono-pitch black roof, hull-panel walls, windows and a door"),
    "crashshanty2": (crashshanty2, "salvage lean-to: steep front plate, black roof"),
    "crashshanty3": (crashshanty3, "low flat-roofed salvage hut with a patchwork hull roof"),
}
H.MEMBERS.update(MEMBERS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("app")
    ap.add_argument("--out", default=str(ROOT / "game/assets/v3/objects"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    names = list(MEMBERS) if a.app == "all" else a.app.split(",")
    for app in names:
        H.build_member(app, out)


if __name__ == "__main__":
    main()
