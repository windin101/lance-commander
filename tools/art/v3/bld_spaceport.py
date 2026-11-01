#!/usr/bin/env python3
"""v3 spaceport / airfield family (LANCE-39): rpbuilding, terminal1, terminal2, walkway, lobby, centerlobby, hub, dropshipdavion / liao / steiner, shuttle,
privatejet, lifeboat, lifeboatcrashed, lifeboatrusted, and the lamps runwaylight, redbeaconlight, bluebeaconlight, greenbeaconlight.

Built to the Shared Source originals' per-part slices and plan heightmaps (game/tools/orig_parts.gd, /mnt/nvme1n1p1/mc2-rework/bld/steiner/hmap.py), in the frame
the originals' meshes use. None of these originals carries a root scale (checked with /mnt/nvme1n1p1/mc2-rework/bld/spaceport/nodes.py), so the mesh size is the
in-game size. Windows are separate rectangles (glass quads), never holes. Lamps use the emissive `lamp_*` materials and the additive `halo_*` quad
(game/scripts/world/building_v3.gd, shaders/building_v3_halo.gdshader): modest by day, glowing at night.

    python3 -I tools/art/v3/bld_spaceport.py <app>[,<app>]|all
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bld_hangars as H  # noqa: E402
import bld_lifeboat as LB  # noqa: E402
from bld_industry import V, TAU, shell, fpanel, door, band, ROOT  # noqa: E402
from bld_kit import Ctx, axis_angle  # noqa: E402
from bld_mesh import unit, rot_y  # noqa: E402
from bld_military import scorch, roof_scorch, frustum, ribbon  # noqa: E402
from bld_steinergov import wins, slab, columns  # noqa: E402

WALL = "steinerwhite"
FRAME = "framedark"


# ------------------------------------------------------------------------------------------------------------------ geometry helpers
def hull(c, mat, pts, band_=0):
    """A convex solid from points: flat-shaded triangles with outward normals, planar metre UVs."""
    pts = np.asarray(pts, float)
    try:
        h = ConvexHull(pts)
    except Exception:                                    # a flat point set: give it a 12 cm thickness along its thinnest direction
        u, sv, vt = np.linalg.svd(pts - pts.mean(0))
        nrm = vt[-1]
        pts = np.vstack([pts + nrm * 0.06, pts - nrm * 0.06])
        h = ConvexHull(pts)
    for s, eq in zip(h.simplices, h.equations):
        P = pts[s]
        n = eq[:3]
        ax = int(np.argmax(np.abs(n)))
        ua, va = [a for a in range(3) if a != ax]
        c.b.add(mat, P, np.tile(n, (3, 1)), np.stack([P[:, ua], P[:, va]], 1), [(0, 1, 2)], band_)


def rotated(pts, ang, cx=0.0, cz=0.0):
    """Points turned about the vertical axis through (cx, cz) by ang (radians)."""
    R = rot_y(ang)
    p = np.asarray(pts, float) - np.array([cx, 0, cz])
    return p @ R.T + np.array([cx, 0, cz])


def lathe_z(c, mat, st, seg=14, cap_front=True, cap_back=True):
    """A lofted elliptical tube along z. st = [(z, rx, ry, cy), ...] in increasing z; rx / ry may be 0 at an end (a point)."""
    n = len(st)
    th = np.linspace(0, TAU, seg, endpoint=False)
    P = np.zeros((n, seg, 3))
    for j, (z, rx, ry, cy) in enumerate(st):
        P[j, :, 0] = rx * np.cos(th)
        P[j, :, 1] = cy + ry * np.sin(th)
        P[j, :, 2] = z
    for j in range(n - 1):
        for k in range(seg):
            k2 = (k + 1) % seg
            q = np.array([P[j, k], P[j, k2], P[j + 1, k2], P[j + 1, k]])
            cen = np.array([0.0, (st[j][3] + st[j + 1][3]) / 2, (st[j][0] + st[j + 1][0]) / 2])
            nn = np.cross(q[1] - q[0], q[3] - q[0])
            if np.linalg.norm(nn) < 1e-9:
                nn = np.cross(q[2] - q[0], q[3] - q[0])
            if np.linalg.norm(nn) < 1e-9:
                continue
            nn = nn / np.linalg.norm(nn)
            if np.dot(nn, q.mean(0) - cen) < 0:
                nn = -nn
            U = np.array([(k * 0.5, q[0][2]), (k * 0.5 + 0.5, q[1][2]), (k * 0.5 + 0.5, q[2][2]), (k * 0.5, q[3][2])])
            c.b.add(mat, q, np.tile(nn, (4, 1)), U, [(0, 1, 2), (0, 2, 3)])
    for j, sg, want in ((0, -1, cap_back), (n - 1, 1, cap_front)):
        z, rx, ry, cy = st[j]
        if want and rx > 0.05 and ry > 0.05:
            ring = P[j]
            Q = np.vstack([[0, cy, z], ring])
            c.b.add(mat, Q, np.tile((0, 0, sg), (len(Q), 1)), Q[:, :2], [(0, 1 + k, 1 + (k + 1) % seg) for k in range(seg)])


def prism_zy(c, mat, x0, x1, pts):
    """A convex (z, y) outline extruded between x0 and x1 (an angled end piece)."""
    pts = np.asarray(pts, float)
    hull(c, mat, [(x, y, z) for (z, y) in pts for x in (x0, x1)])


def _in(lo, hi, rng, w):
    """A centre for something w wide inside lo..hi (the middle when it does not fit)."""
    a, b_ = lo + w / 2, hi - w / 2
    return (lo + hi) / 2 if b_ <= a else rng.uniform(a, b_)


def wall_stub_ring(c, box, hmax=2.0):
    """Charred broken wall stubs round a footprint (destroyed states): inside the footprint only."""
    x0, x1, z0, z1 = box
    rng = c.rng
    n = 6 if c.fine else 3
    for z in (z0 + 0.3, z1 - 0.3):
        for k in range(n):
            w = min(rng.uniform(2.0, 4.5), (x1 - x0) - 0.6)
            hh = rng.uniform(0.6, hmax)
            c.b.box("concrete_dark", (_in(x0, x1, rng, w), hh / 2, z), (w, hh, 0.5))
    for x in (x0 + 0.3, x1 - 0.3):
        for k in range(max(2, n // 2)):
            w = min(rng.uniform(2.0, 4.0), (z1 - z0) - 0.6)
            hh = rng.uniform(0.6, hmax)
            c.b.box("concrete_dark", (x, hh / 2, _in(z0, z1, rng, w)), (0.5, hh, w))


def charred_rubble(c, box, hmax=3.0, n=14):
    """A heap of burnt slab chunks, wall pieces and bent rebar filling the footprint, every piece kept inside it (with its rotation allowance)."""
    b = c.b
    x0, x1, z0, z1 = box
    rng = c.rng
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    W, D = x1 - x0, z1 - z0
    for k in range(n if c.fine else max(4, n // 3)):
        sx, sz = rng.uniform(1.2, 3.2), rng.uniform(1.0, 2.8)
        r = math.hypot(sx, sz) / 2 + 0.2
        x = _in(x0 + r, x1 - r, rng, 0.01)
        z = _in(z0 + r, z1 - r, rng, 0.01)
        hh = min(hmax * 0.5, 0.6 + 1.6 * (1.0 - math.hypot((x - cx) / (W / 2), (z - cz) / (D / 2)) * 0.8)) * rng.uniform(0.7, 1.1)
        b.box("concrete_dark" if k % 3 else "rust", (x, hh / 2 + 0.3, z), (sx, max(0.4, hh), sz), axis_angle(V([0, 1.0, 0]), rng.random() * 3.0) @ axis_angle(V([1.0, 0, 0]), rng.uniform(-0.25, 0.25)))
    for k in range(2):
        sx, sz = min(W * 0.3, 6.0), min(D * 0.3, 5.0)
        r = math.hypot(sx, sz) / 2 + 0.2
        b.box("concrete", (_in(x0 + r, x1 - r, rng, 0.01), 1.6 + k * 0.6, _in(z0 + r, z1 - r, rng, 0.01)), (sx, 0.3, sz), axis_angle(V([0, 1.0, 0]), rng.uniform(-0.5, 0.5)) @ axis_angle(V([1.0, 0, 0]), rng.uniform(-0.2, 0.2)))
    for k in range(8 if c.fine else 3):
        a = V([_in(x0 + 1, x1 - 1, rng, 0.01), 1.0, _in(z0 + 1, z1 - 1, rng, 0.01)])
        b.tube("steel", a, a + V([rng.uniform(-1.0, 1.0), rng.uniform(1.0, 2.6), rng.uniform(-1.0, 1.0)]), 0.05, 4)
    c.decal_ground("soot", (cx, cz), W * 1.0, D * 1.0, 0.0, y=0.45)


def wreck_building(c, box, h, n=12, stubs=2.0):
    x0, x1, z0, z1 = box
    c.b.box("concrete_dark", ((x0 + x1) / 2, 0.2, (z0 + z1) / 2), (x1 - x0, 0.4, z1 - z0))
    wall_stub_ring(c, box, stubs)
    charred_rubble(c, (x0 + 0.6, x1 - 0.6, z0 + 0.6, z1 - 0.6), min(h * 0.4, 4.0), n)


def scorch_patch(c, p, n, w, h, tang):
    """A flat soot-black quad on a surface at point p with normal n (damaged states)."""
    if c.state != "damaged":
        return
    n = unit(n)
    c.b.quad("scorchblack", V(p) + n * 0.07, tang, np.cross(n, tang), w, h, (0, 0, 1, 1), normal=tuple(n))


def bent_beams(c, p, n=3, r=0.09, mat="steel"):
    if c.state != "damaged":
        return
    for k in range(n):
        a = V(p) + V([c.rng.uniform(-1.2, 1.2), 0.0, c.rng.uniform(-1.2, 1.2)])
        c.b.tube(mat, a, a + V([c.rng.uniform(-1.4, 1.4), c.rng.uniform(0.8, 2.0), c.rng.uniform(-1.4, 1.4)]), r, 5)


# ------------------------------------------------------------------------------------------------------------------ rpbuilding
def rpbuilding(state, lod, seed):
    """Resource-point warehouse. Measured (heightmap + per-1 m slices): roof flat at y 6.84 over x -11.4..11.4, z -7.3..7.3 with the long walls to z +-7;
    two bevelled end pieces at x +-(9.0..11.4) that run the full depth z +-10.6 and slope from the roof height to 3.5 at their ends; a low 2 m skirt to
    x +-12.4. Roof panels are brown-tan ribbed sheet between pale bands (ribs run along x). The model keeps the original's own axes."""
    c = shell(state, lod, seed, (0.0, 3.0, 7.0, 3.0), 1.5)
    b = c.b
    body = (-11.4, 11.4, -7.0, 7.0)
    if state == "destroyed":
        wreck_building(c, (-11.4, 11.4, -7.0, 7.0), 6.8, 10, 2.4)
        for sx in (-1, 1):
            prism_zy(c, "concrete_dark", sx * 9.0 if sx > 0 else -11.4, sx * 11.4 if sx > 0 else -9.0, [(-10.6, 0), (10.6, 0), (10.6, 0.9), (-10.6, 0.9)])
        return c
    for z_, sg in ((-7.0, -1), (7.0, 1)):                                           # tan-brown cast walls in panels with pale pilaster strips
        pass
    b.box("tanwall", (0, 3.0, 0), (22.8, 6.0, 14.0))
    b.box("palepaint", (0, 0.3, 0), (23.2, 0.6, 14.4))
    for sg in (-1, 1):
        for xc in (-8.0, -3.0, 3.0, 8.0) if c.fine else ():
            b.box("palepaint", (xc, 3.0, sg * 7.05), (0.5, 6.0, 0.15))
        b.box("brownstep" if False else "roofbrown", (0, 0.3, sg * 7.9), (22.0, 0.6, 1.8))     # the low tiled step in front of each long face
        # a central double door in a pale frame with two small windows, flanked by long ribbed plates
        b.box("palepaint", (0, 3.0, sg * 7.08), (5.6, 4.6, 0.1))
        b.box("wglass", (0, 2.7, sg * 7.14), (3.6, 3.6, 0.06))
        b.box("palepaint", (0, 2.7, sg * 7.19), (0.16, 3.6, 0.05))
        for xw in (-1.3, 1.3):
            b.box("bandorange", (xw, 2.9, sg * 7.2), (0.8, 0.9, 0.04))
        for xc in (-7.4, 7.4):
            b.box("palepaint", (xc, 3.2, sg * 7.08), (6.6, 4.0, 0.08))
            if c.fine:
                for k in range(6):
                    b.box("tanwall", (xc, 1.6 + k * 0.62, sg * 7.14), (6.4, 0.2, 0.06))
        b.box("safetyyellow", (0, 0.9, sg * 7.06), (22.4, 0.22, 0.05)) if c.fine else None
    # roof: eave slab, pale bands and three ribbed brown panels
    b.box("palepaint", (0, 6.35, 0), (23.0, 0.7, 14.8))
    for xb in (-3.0, 3.0):
        b.box("palepaint", (xb, 6.9, 0), (1.2, 0.2, 14.6))
    for x0_, x1_ in ((-9.0, -3.6), (-2.4, 2.4), (3.6, 9.0)):
        xc = (x0_ + x1_) / 2
        b.box("tanwall", (xc, 6.8, 0), (x1_ - x0_, 0.16, 14.4))
        nr = 16 if c.fine else 8
        for k in range(nr):                                                         # the ribs: sheet corrugations running along x
            b.box("palepaint", (xc, 6.98, -6.9 + k * 13.8 / (nr - 1)), (x1_ - x0_ - 0.1, 0.13, 0.42 if c.fine else 0.8))
    for xb in (-9.0, 9.0):
        b.box("palepaint", (xb, 6.9, 0), (0.8, 0.2, 14.6))
    for sx in (-1, 1):                                                              # bevelled end pieces, a low skirt and a stair-step ramp beyond them
        xa, xb = (9.0, 11.4) if sx > 0 else (-11.4, -9.0)
        prism_zy(c, "palepaint", xa, xb, [(-10.6, 0), (10.6, 0), (10.6, 3.4), (7.2, 6.84), (-7.2, 6.84), (-10.6, 3.4)])
        for sz in (-1, 1):
            hull(c, "lightroof", [(x, y, sz * z) for x in (xa + 0.35, xb - 0.35) for (z, y) in ((7.3, 6.5), (10.45, 3.45), (10.45, 3.8), (7.3, 6.9))])
        hull(c, "palepaint", [(x, y, z) for x in ((11.4, 12.4) if sx > 0 else (-12.4, -11.4)) for (y, z) in ((0, -6.5), (0, 6.5), (2.0, 6.5), (2.0, -6.5))] if False else
             [(x, y, z) for x, y in (((11.4, 0), (12.4, 0), (11.4, 2.0)) if sx > 0 else ((-11.4, 0), (-12.4, 0), (-11.4, 2.0))) for z in (-6.5, 6.5)])
        if c.fine:
            for k in range(6):
                b.box("steel", (sx * 10.2, 7.1, -5.5 + k * 2.2), (1.6, 0.14, 0.5))     # roof vent grilles on the end pieces' tops
    if c.state == "damaged":
        scorch(c, "+z", (-11.4, 11.4, -7.0, 7.0), 6.0, 2.8, 2.0)
        roof_scorch(c, -2.0, 7.1, -2.0, 2.2)
        bent_beams(c, (-2.0, 7.0, -2.0), 3)
    return c


# ------------------------------------------------------------------------------------------------------------------ terminals / walkway / lobby / hub
def _terminal_body(c, state):
    b = c.b
    X, Z = 12.75, 6.0
    if state == "destroyed":
        wreck_building(c, (-X, X, -Z, Z), 8.0, 11, 1.8)
        return
    b.box("concrete", (0, 0.3, 0), (2 * X, 0.6, 2 * Z))
    b.box("camogreen", (0, 2.4, 0), (2 * X - 0.8, 3.6, 2 * Z - 0.8))                # the glazed ground storey (green interior behind dark mullions)
    for sg in (-1, 1):
        for k in range(9 if c.fine else 5):
            xk = -X + 0.4 + k * (2 * X - 0.8) / (8 if c.fine else 4)
            b.box(FRAME, (xk, 2.4, sg * (Z - 0.4)), (0.28, 3.7, 0.28))
        b.box(FRAME, (0, 0.7, sg * (Z - 0.38)), (2 * X - 0.6, 0.3, 0.3))
        for k in range(8):                                                           # lit panes (amber at night) in each bay of the green storey
            b.box("wglass", (-X + 1.8 + k * 3.3, 2.4, sg * (Z - 0.3)), (2.2, 1.5, 0.06))
        b.box(FRAME, (0, 4.1, sg * (Z - 0.38)), (2 * X - 0.6, 0.3, 0.3))
    for sg in (-1, 1):
        for k in range(4 if c.fine else 2):
            zk = -Z + 0.4 + k * (2 * Z - 0.8) / (3 if c.fine else 1)
            b.box(FRAME, (sg * (X - 0.4), 2.4, zk), (0.28, 3.7, 0.28))
    b.box(WALL, (0, 5.2, 0), (2 * X, 2.2, 2 * Z))                                   # white fascia band
    for sg in (-1, 1):
        b.box("bluetrim", (0, 4.2, sg * (Z + 0.04)), (2 * X + 0.1, 0.22, 0.12))
    ytop = 6.3
    frustum(c, WALL, 0.0, 0.0, X, Z, ytop, X - 1.1, Z - 1.0, 7.9)                  # bevelled hat
    b.box("lightroof", (0, 8.0, 0), (2 * (X - 1.1), 0.25, 2 * (Z - 1.0)))
    if c.fine:                                                                       # roof plant: four units and a pipe run to them
        for k in range(4):
            b.box("palepaint", (5.2 + k * 1.9, 8.55, -1.8), (1.2, 0.9, 1.2))
        b.tube("steel", (-10.5, 8.3, 0.4), (4.4, 8.3, 0.4), 0.14, 6)
        b.tube("steel", (4.4, 8.3, 0.4), (4.4, 8.3, -1.8), 0.14, 6)
        b.box("machgrey", (-6.0, 8.2, 2.0), (6.0, 0.12, 2.6))
    for sg in (-1, 1):                                                               # wall plates on the fascia
        for k in range(5):
            b.box("palepaint", (-9.5 + k * 4.8, 5.2, sg * (Z + 0.06)), (3.4, 1.5, 0.1))
    if c.state == "damaged":
        scorch(c, "+z", (-X, X, -Z, Z), 8.0, 2.4, 2.2)
        roof_scorch(c, 2.0, 8.2, 0.5, 2.0)
        bent_beams(c, (2.0, 8.1, 0.5), 3)


def _mast(c, x, sg):
    """The tilted spotlight mast: a tapered square duct leaning out over the side from the roof edge to a lamp head at y 14.7."""
    b = c.b
    if c.state == "destroyed":
        return
    p0, p1 = V([x, 6.0, 4.0 * sg]), V([x, 14.2, 9.0 * sg])
    d = unit(p1 - p0)
    side = V([1.0, 0, 0])
    up = unit(np.cross(d, side))
    pts = []
    for p, w in ((p0, 0.95), (p1, 0.5)):
        for sx in (-1, 1):
            for su in (-1, 1):
                pts.append(p + side * (sx * w) + up * (su * w))
    hull(c, "tealwall", pts)
    head = p1 + V([0, 0.4, 0.2 * sg])
    ang = axis_angle(V([1.0, 0, 0]), 0.6 * sg)
    b.box("palepaint", head, (2.4, 1.5, 1.7), ang)
    b.box("glasslight", head + V([0, 0.55, 0.9 * sg]), (2.0, 0.5, 0.12), ang)


def _stairs(c, x, zfar, zroof, rise, w=2.0, steps=10):
    """A straight flight rising from zfar (ground) to zroof (top, height rise)."""
    if c.state == "destroyed":
        return
    b = c.b
    sg = 1 if zfar > zroof else -1
    for k in range(steps):
        zc = zfar - sg * (k + 0.5) * abs(zfar - zroof) / steps
        hh = rise * (k + 1) / steps
        b.box("concrete", (x, hh / 2, zc), (w, hh, abs(zfar - zroof) / steps))
    for sx in (-1, 1):
        b.tube("steel", (x + sx * (w / 2 - 0.05), 1.0, zfar), (x + sx * (w / 2 - 0.05), rise + 1.0, zroof), 0.05, 4)
    b.box("concrete", (x, rise - 0.1, zroof - sg * 0.5), (w, 0.3, 1.0))


def terminal1(state, lod, seed):
    c = shell(state, lod, seed, (-6.0, 4.0, 6.0, 3.0), 2.0)
    _terminal_body(c, state)
    _mast(c, -4.99, 1)
    _stairs(c, -9.0, 12.5, 6.0, 4.8)
    return c


def terminal2(state, lod, seed):
    c = shell(state, lod, seed, (4.0, 4.0, -6.0, 3.0), 2.0)
    _terminal_body(c, state)
    _mast(c, -4.99, 1)
    _mast(c, 4.98, -1)
    _stairs(c, -9.0, 12.7, 6.0, 4.8)
    _stairs(c, 9.0, -12.7, -6.0, 4.8)
    return c


def walkway(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 4.0, 6.0, 3.0), 2.0)
    _terminal_body(c, state)
    return c


def lobby(state, lod, seed):
    """x +-12.8, z -4.2..12.6: a white lower storey (to 5.5) under a black-framed glass hall (open grid roof over a green floor): flat at 12 from z 1 to the
    front, sloping down to a black back wall at 7 over z -4.2..1."""
    c = shell(state, lod, seed, (0.0, 8.0, 12.6, 3.0), 2.0)
    b = c.b
    X, Z0, Z1 = 12.8, -4.2, 12.6
    zc, D = (Z0 + Z1) / 2, Z1 - Z0
    if state == "destroyed":
        wreck_building(c, (-X, X, Z0, Z1), 9.0, 12, 2.6)
        return c
    b.box("concrete", (0, 0.3, zc), (2 * X, 0.6, D))
    b.box(WALL, (0, 3.0, zc), (2 * X - 0.4, 5.4, D - 0.4))
    for sg, z in ((-1, Z0), (1, Z1)):
        for k in range(6):
            b.box("palepaint", (-10.0 + k * 4.0, 3.0, z - sg * 0.18), (3.0, 4.0, 0.1))
        for k in (0, 2, 4):
            b.box("wglass", (-10.0 + k * 4.0, 1.6, z - sg * 0.1), (1.2, 0.7, 0.06))
    ytop, ylo, yb = 12.0, 7.0, 5.5
    zk = 1.0
    b.box("camogreen", (0, yb + 0.25, zc), (2 * X - 0.8, 0.1, D - 0.8))               # the green floor seen through the open roof
    b.box(FRAME, (0, (yb + ylo) / 2 + 0.2, Z0 + 0.2), (2 * X - 0.4, ylo - yb + 0.4, 0.4))   # solid black back wall
    cols = 8 if c.fine else 4
    xs_ = [-X + 0.2 + i * (2 * X - 0.4) / cols for i in range(cols + 1)]
    for xk in xs_:
        b.tube(FRAME, (xk, yb, Z1 - 0.2), (xk, ytop, Z1 - 0.2), 0.14, 5)
        b.tube(FRAME, (xk, ytop, Z1 - 0.2), (xk, ytop, zk), 0.12, 5)
        b.tube(FRAME, (xk, ytop, zk), (xk, ylo, Z0 + 0.2), 0.12, 5)
    for y in (yb + 0.1, 8.8, ytop):
        b.box(FRAME, (0, y, Z1 - 0.2), (2 * X - 0.4, 0.28, 0.28))
    for j in range(5 if c.fine else 3):                                             # roof cross bars, flat part
        zz = zk + j * (Z1 - 0.2 - zk) / (4 if c.fine else 2)
        b.box(FRAME, (0, ytop, zz), (2 * X - 0.4, 0.22, 0.22))
    for j in range(3):                                                              # roof cross bars, sloping part
        t = (j + 1) / 4
        b.box(FRAME, (0, ytop + (ylo - ytop) * t, zk + (Z0 + 0.2 - zk) * t), (2 * X - 0.4, 0.22, 0.22))
    # the front face glass: separate light panes in the frame; side faces likewise
    for i in range(cols):
        xc = (xs_[i] + xs_[i + 1]) / 2
        for (y0_, y1_) in ((yb + 0.3, 8.7), (8.9, ytop - 0.2)):
            b.box("glasslight", (xc, (y0_ + y1_) / 2, Z1 - 0.16), ((xs_[1] - xs_[0]) - 0.3, y1_ - y0_, 0.04))
    for sg in (-1, 1):
        xs = sg * (X - 0.2)
        for zq in np.linspace(Z0 + 0.2, Z1 - 0.2, 6 if c.fine else 3):
            hy = ytop if zq >= zk else ylo + (ytop - ylo) * (zq - Z0 - 0.2) / (zk - Z0 - 0.2)
            b.tube(FRAME, (xs, yb, zq), (xs, hy, zq), 0.12, 5)
        b.tube(FRAME, (xs, ytop, Z1 - 0.2), (xs, ytop, zk), 0.14, 5)
        b.tube(FRAME, (xs, ytop, zk), (xs, ylo, Z0 + 0.2), 0.14, 5)
        b.tube(FRAME, (xs, 8.8, Z1 - 0.2), (xs, 8.8, zk), 0.1, 4)
        b.box("glasslight", (xs, 8.8, (zk + Z1) / 2), (0.04, 5.6, Z1 - zk - 0.6))
    if c.state == "damaged":
        scorch(c, "+z", (-X, X, Z0, Z1), 6.0, 2.6, 2.2)
        scorch_patch(c, (-7.0, 8.9, Z1 - 0.1), (0, 0, 1), 5.0, 3.5, (1, 0, 0))
        bent_beams(c, (3.0, ytop, 6.0), 4)
    return c


def centerlobby(state, lod, seed):
    """x +-12.8, z -8..15.4: white block, vertical edges chamfered 3 m, walls to y 9.5 then a 45 degree shoulder in to a 13 deck; a 14 ring and a 15 centre
    block on top; tapered chamfered stems at both ends."""
    c = shell(state, lod, seed, (0.0, 8.0, 12.0, 3.0), 2.0)
    b = c.b
    if state == "destroyed":
        wreck_building(c, (-12.6, 12.6, -6.0, 12.0), 13.0, 14, 3.0)
        wall_stub_ring(c, (-6.0, 6.0, 12.0, 15.2), 1.2)
        return c
    def oct_(x, z0, z1, ch):
        return [(-x, z0 + ch), (-x + ch, z0), (x - ch, z0), (x, z0 + ch), (x, z1 - ch), (x - ch, z1), (-x + ch, z1), (-x, z1 - ch)]
    lo = oct_(12.6, -6.0, 12.0, 1.6)
    hull(c, WALL, [(x, y, z) for (x, z) in lo for y in (0.0, 10.6)])
    top = oct_(10.3, -3.8, 9.8, 1.2)
    hull(c, WALL, [(x, 10.6, z) for (x, z) in lo] + [(x, 13.0, z) for (x, z) in top])
    b.box("concrete", (0, 0.25, 3.0), (25.4, 0.5, 18.2))
    b.box("lightroof", (0, 13.3, 3.0), (19.2, 0.5, 14.0))
    b.box("lightroof", (0, 14.1, 3.0), (13.6, 1.2, 12.0))
    if c.fine:
        for k in range(5):
            b.box("machgrey", (-3.0 + k * 1.5, 14.9, -2.0), (0.5, 0.3, 0.9))
        b.box("machgrey", (1.0, 14.8, 4.0), (6.0, 0.2, 4.5))
        b.tube("steel", (-5.5, 14.8, 8.0), (3.5, 14.8, 8.0), 0.15, 6)
    prism_zy(c, WALL, -6.0, 6.0, [(12.0, 0), (15.4, 0), (15.4, 9.0), (12.0, 13.0)])
    prism_zy(c, WALL, -6.0, 6.0, [(-6.0, 0), (-8.0, 0), (-8.0, 10.5), (-6.0, 13.0)])
    # plates: a big inset panel with diagonal ribs on each chamfer, window pairs low on the end faces, light seams
    for sx in (-1, 1):
        for sz in (-1, 1):
            zc = -6.0 + 3.0 / 2 if sz < 0 else 12.0 - 3.0 / 2
            ctr = V([sx * (12.6 - 1.5) + sx * 0.05, 4.8, zc + (-0.0)])
            n = unit(V([sx, 0, sz]))
            tg = V([-n[2], 0, n[0]])
            q = V([sx * 11.55, 4.8, (-5.0 if sz < 0 else 11.0)]) + n * 0.1
            b.quad("palepaint", q, tg, V([0, 1.0, 0]), 3.4, 6.2, (0, 0, 1, 1), normal=tuple(n))
            if c.fine:
                for k in range(5):
                    b.quad("machgrey", q + n * 0.03 + V([0, -2.6 + k * 1.3, 0]), tg, V([0, 1.0, 0]), 3.0, 0.14, (0, 0, 1, 1), normal=tuple(n))
    for z_, sg in ((-6.0, -1), (12.0, 1)):
        b.box("palepaint", (0, 5.0, z_ + sg * 0.05), (9.0, 7.0, 0.1))
        b.box("wglass", (-8.6, 1.6, z_ + sg * 0.1), (1.0, 0.8, 0.06))
        b.box("wglass", (8.6, 1.6, z_ + sg * 0.1), (1.0, 0.8, 0.06))
        b.box("wglass", (-7.2, 1.6, z_ + sg * 0.1), (1.0, 0.8, 0.06))
        b.box("wglass", (7.2, 1.6, z_ + sg * 0.1), (1.0, 0.8, 0.06))
        b.box("palepaint", (0, 5.0, z_ + sg * 0.1), (7.0, 5.4, 0.06))
    for sx in (-1, 1):
        b.box("palepaint", (sx * 12.64, 6.0, 4.5), (0.1, 5.0, 4.0))
        for k in range(3):
            b.box("wglass", (sx * 12.68, 7.0 + 0.0, 3.0 + k * 1.5), (0.06, 3.6, 0.5))
    if c.state == "damaged":
        scorch(c, "+z", (-12.6, 12.6, -6.0, 12.0), 3.0, 4.0, 2.2)
        roof_scorch(c, 2.0, 14.8, 4.0, 2.2)
        bent_beams(c, (2.0, 14.8, 4.0), 3)
    return c


def hub(state, lod, seed):
    """x, z +-12.7: a stepped octagonal base (8 at the rim, 10, 11), a 14 m block and a straight 24 m vent tower with a louvred cap; dark window pairs round the base."""
    c = shell(state, lod, seed, (0.0, 8.0, 12.7, 3.0), 2.0)
    b = c.b
    if state == "destroyed":
        wreck_building(c, (-12.2, 12.2, -12.2, 12.2), 14.0, 16, 3.0)
        b.box("concrete_dark", (0, 1.0, 0), (6.0, 2.0, 6.0))
        return c
    def octa(r, ch, y0, y1, mat):
        pts = []
        for (sx, sz) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            pts += [(sx * r, sz * (r - ch)), (sx * (r - ch), sz * r)]
        hull(c, mat, [(x, y, z) for (x, z) in pts for y in (y0, y1)])
    octa(12.7, 3.2, 0.0, 8.2, WALL)
    octa(11.2, 3.0, 8.2, 10.2, "lightroof")
    octa(9.6, 2.6, 10.2, 11.3, WALL)
    b.box("lightroof", (0, 12.7, 0), (16.4, 3.2, 17.0))
    b.box("palepaint", (0, 14.2, 0), (13.0, 0.6, 13.0))
    b.box("steinerwhite", (0, 19.0, 0), (8.8, 9.6, 8.8))                                # the vent tower
    for sg in (-1, 1):
        for k in range(3):
            b.box("palepaint", (0, 16.2 + k * 3.0, sg * 4.45), (7.0, 0.5, 0.1))
            b.box("palepaint", (sg * 4.45, 16.2 + k * 3.0, 0), (0.1, 0.5, 7.0))
    b.box("lightroof", (0, 23.7, 0), (10.0, 1.0, 10.0))
    b.box("machgrey", (0, 24.2, 0), (7.6, 0.3, 7.6))
    for sg in (-1, 1):                                                                  # louvres on the cap
        for k in range(4):
            b.box("grate", (0, 23.5, sg * 5.05), (7.0, 0.14, 0.1))
            b.box("grate", (sg * 5.05, 23.5, 0), (0.1, 0.14, 7.0))
    for sg in (-1, 1):
        for k in range(3):
            xk = -7.5 + k * 7.5
            b.box("palepaint", (xk, 4.0, sg * 12.72), (4.6, 5.0, 0.1))
            b.box("wglass", (xk - 0.8, 2.4, sg * 12.78), (0.9, 0.9, 0.06))
            b.box("wglass", (xk + 0.8, 2.4, sg * 12.78), (0.9, 0.9, 0.06))
            b.box("palepaint", (sg * 12.72, 4.0, xk), (0.1, 5.0, 4.6))
            b.box("wglass", (sg * 12.78, 2.4, xk - 0.8), (0.06, 0.9, 0.9))
            b.box("wglass", (sg * 12.78, 2.4, xk + 0.8), (0.06, 0.9, 0.9))
    if c.fine:
        for k in range(8):
            b.box("palepaint", (-6.0 + k * 1.7, 11.6, 6.8), (1.2, 0.5, 0.9))
    if c.state == "damaged":
        scorch(c, "+z", (-12.7, 12.7, -12.7, 12.7), 8.0, 4.0, 2.4)
        roof_scorch(c, 5.0, 14.5, 4.0, 2.0)
        bent_beams(c, (5.0, 14.5, 4.0), 3)
    return c


# ------------------------------------------------------------------------------------------------------------------ dropships
EMBLEM = {"dropshipdavion": "davion", "dropshipliao": "liao", "dropshipsteiner": "steiner"}


def _dropship(app, hullmat):
    def build(state, lod, seed):
        c = Ctx(state, lod, seed, breach=(10.0, 20.0, 10.0, 5.0), ledges=[(16.5, 5.0, 0.5), (30.0, 6.0, 0.4)], ao_rings=[(16.0, 3.0, 0.3)], ground_h=6.0)
        b = c.b
        seg = 16 if c.fine else 16
        if state == "destroyed":
            _ds_wreck(c, hullmat)
            return c
        lower = [(0.0, 3.0), (10.0, 3.0), (11.8, 4.6), (12.6, 8.0), (12.5, 12.5), (12.4, 16.3)]
        upper = [(12.4, 16.3), (13.4, 17.2), (14.2, 20.5), (14.4, 25.5), (13.2, 30.0), (9.8, 33.4), (6.6, 34.7)]
        b.revolve("machgrey", lower, seg, uref=12.0)
        b.revolve(hullmat, upper, seg, uref=14.0)
        b.revolve("steel", [(12.5, 16.15), (13.6, 16.4), (13.6, 17.0), (12.6, 17.2)], seg, uref=13.0)
        b.disc(hullmat, (0, 34.7, 0), 6.6, (0, 1, 0), seg)
        _ds_emblem(c, EMBLEM[app])
        # window rows and belt lights
        th_w = [TAU * (k + 0.5) / 16 for k in range(16)]
        for row, (yy, rr) in enumerate(((21.4, 14.33), (24.4, 14.42))):
            for th in th_w:
                ctr = V([rr * math.cos(th), yy, rr * math.sin(th)]) + V([math.cos(th), 0, math.sin(th)]) * 0.07
                tg = V([-math.sin(th), 0, math.cos(th)])
                b.quad("wglass", ctr, tg, V([0, 1.0, 0]), 1.9, 0.9, (0, 0, 1, 1), normal=(math.cos(th), 0, math.sin(th)))
        if c.fine:
            for k in range(32):
                th = TAU * k / 32
                b.box("steinerwhite", (13.9 * math.cos(th), 18.3, 13.9 * math.sin(th)), (0.5, 0.4, 0.5), axis_angle(V([0, 1.0, 0]), -th))
            for k in range(8):                                                       # hull plates and hatches on the lower skirt
                th = TAU * k / 8 + 0.2
                ctr = V([11.1 * math.cos(th), 11.2, 11.1 * math.sin(th)])
                b.box("palepaint", ctr, (0.2, 3.8, 3.2), axis_angle(V([0, 1.0, 0]), -th) @ axis_angle(V([0, 0, 1.0]), 0.0))
        # lower-hull armour bands, four door panels and four leg pods (hull-coloured, wide, dark footpads)
        for yy in (8.4, 12.8):
            b.revolve("steel", [(12.55 + (0.1 if yy < 10 else 0.0), yy - 0.2), (12.9, yy - 0.1), (12.9, yy + 0.1), (12.6, yy + 0.2)], seg, uref=12.0)
        for q in range(4):
            ang = q * math.pi / 2
            ca, sa = math.cos(ang), math.sin(ang)
            for (yy, hh, ww, mat) in ((8.2, 6.2, 5.2, "palepaint"), (8.0, 5.2, 4.2, "grate")):
                ctr = V([12.7 * ca, yy, 12.7 * sa]) + V([ca, 0, sa]) * (0.12 if mat == "palepaint" else 0.2)
                b.quad(mat, ctr, V([-sa, 0, ca]), V([0, 1.0, 0]), ww, hh, (0, 0, 1, 1), normal=(ca, 0, sa))
            ang += math.pi / 4                                                         # the four pods stand at the diagonals, the door panels on the axes
            ca, sa = math.cos(ang), math.sin(ang)
            leg = [(11.2, 3.5, -2.8), (11.2, 3.5, 2.8), (12.4, 15.5, -2.4), (12.4, 15.5, 2.4), (21.0, 0.4, -2.9), (21.0, 0.4, 2.9), (15.0, 0.4, -2.9), (15.0, 0.4, 2.9),
                   (17.0, 14.0, -2.4), (17.0, 14.0, 2.4), (19.0, 7.0, -2.8), (19.0, 7.0, 2.8)]
            if state == "damaged" and q == 1:
                leg = [(x, y, z + (0.0 if y > 10 else 1.4)) for (x, y, z) in leg]
            P = np.array([(r * ca - t * sa, y, r * sa + t * ca) for (r, y, t) in leg])
            hull(c, hullmat, P)
            foot = [(14.6, 0.0, -3.3), (21.0, 0.0, -3.3), (21.0, 0.7, -3.0), (14.6, 0.7, -3.0), (14.6, 0.0, 3.3), (21.0, 0.0, 3.3), (21.0, 0.7, 3.0), (14.6, 0.7, 3.0)]
            hull(c, "steel", np.array([(r * ca - t * sa, y, r * sa + t * ca) for (r, y, t) in foot]))
            if c.fine:
                for k in range(3):
                    ctr = V([16.2 * ca - (-2.0 + k * 2.0) * sa, 8.0, 16.2 * sa + (-2.0 + k * 2.0) * ca])
                    b.box("machgrey", ctr, (0.2, 2.8, 1.2), axis_angle(V([0, 1.0, 0]), -ang))
                    b.box("palepaint", ctr + V([ca, 0, sa]) * 0.0 + V([0, 4.4, 0]), (0.2, 1.4, 1.6), axis_angle(V([0, 1.0, 0]), -ang))
        # ramp door on the front hull (+z), hazard frame
        b.box("safetyyellow", (0, 7.0, 12.9), (3.8, 4.4, 0.16), axis_angle(V([1.0, 0, 0]), -0.0))
        b.box("grate", (0, 7.0, 12.98), (3.2, 3.8, 0.1))
        if c.state == "damaged":
            for (th, yy, rr_) in ((0.9, 24.0, 4.0), (3.5, 21.0, 3.2)):
                n = V([math.cos(th), 0, math.sin(th)])
                scorch_patch(c, V([14.4 * math.cos(th), yy, 14.4 * math.sin(th)]), n, rr_ * 1.6, rr_ * 1.3, (-math.sin(th), 0, math.cos(th)))
                ctr = V([14.3 * math.cos(th), yy, 14.3 * math.sin(th)])
                for k in range(3):
                    a = ctr + V([0, -rr_ * 0.4, 0]) + V([-math.sin(th), 0, math.cos(th)]) * rng_u(c, rr_ * 0.6)
                    c.b.tube("steel", a, a + n * rng_u(c, 1.0, 0.6) + V([0, rng_u(c, 1.4, 0.2), 0]), 0.12, 5)
            roof_scorch(c, 2.5, 34.8, 2.0, 2.4)
        return c
    return build


def rng_u(c, a, lo=None):
    return c.rng.uniform(-a, a) if lo is None else c.rng.uniform(lo, a)


def _ds_emblem(c, kind):
    b = c.b
    y = 34.76
    if kind == "davion":
        b.disc("flagcloth", (0, y, 0), 5.4, (0, 1, 0), 24 if c.fine else 12)
        b.disc("safetyyellow", (0, y + 0.03, 0), 2.6, (0, 1, 0), 16 if c.fine else 8)
        for k in range(8):
            th = TAU * k / 8
            b.box("safetyyellow", (3.7 * math.cos(th), y + 0.03, 3.7 * math.sin(th)), (2.4, 0.04, 0.55), axis_angle(V([0, 1.0, 0]), -th))
    elif kind == "liao":
        b.disc("steinerwhite", (0, y, 0), 5.6, (0, 1, 0), 24 if c.fine else 12)
        tri = [(0, y + 0.03, -4.4), (4.0, y + 0.03, 3.0), (-4.0, y + 0.03, 3.0)]
        P = np.array(tri)
        b.add("tealpaint", P, np.tile((0, 1.0, 0), (3, 1)), P[:, [0, 2]], [(0, 1, 2)])
        b.box("scorchblack", (0.4, y + 0.05, 0.2), (0.6, 0.04, 6.0), axis_angle(V([0, 1.0, 0]), 0.5))
    else:
        b.disc("steinerwhite", (0, y, 0), 5.6, (0, 1, 0), 24 if c.fine else 12)
        b.box("flagcloth", (0, y + 0.05, 0.3), (3.6, 0.04, 3.2))
        for k in range(4):
            b.box("flagcloth", (-1.35 + k * 0.9, y + 0.05, -1.7), (0.8, 0.04, 1.3))
        b.box("machgrey", (-1.0, y + 0.05, 2.9), (3.0, 0.04, 1.2), axis_angle(V([0, 1.0, 0]), 0.3))


def _ds_wreck(c, hullmat):
    """A burnt-out stump of the lower hull, split open on one side, with its fallen legs and plates, inside radius 17."""
    b = c.b
    seg = 28 if c.fine else 14
    prof = [(12.0, 0.3), (12.3, 3.0), (12.1, 6.0), (11.0, 8.4), (9.2, 9.6)]
    cull = lambda th, y: (0.4 < (th % TAU) < 2.2 and y > 3.5) or (3.6 < (th % TAU) < 4.2 and y > 6.5)
    b.revolve("machgrey", prof, seg, cull=cull, uref=12.0)
    b.revolve("interior", prof, seg, cull=cull, flip=True, uref=12.0)
    b.disc("concrete_dark", (0, 0.3, 0), 11.8, (0, 1, 0), seg)
    rng = c.rng
    for k in range(5 if c.fine else 2):                                                # collapsed deck plates and ribs
        a = rng.uniform(0, TAU)
        r = rng.uniform(2.0, 9.0)
        b.box("machgrey", (r * math.cos(a), 1.2 + 0.6 * k, r * math.sin(a)), (rng.uniform(3, 6), 0.35, rng.uniform(2.5, 5)),
              axis_angle(V([0, 1.0, 0]), a) @ axis_angle(V([1.0, 0, 0]), rng.uniform(-0.4, 0.4)))
    for q in range(4):                                                                 # legs: two standing broken, two fallen
        ang = q * math.pi / 2 + math.pi / 4 + (0.0 if q < 2 else 0.25)
        P = np.array([(r * math.cos(ang) - t * math.sin(ang), y, r * math.sin(ang) + t * math.cos(ang)) for (r, y, t) in
                      [(13.0, 0.0, -2.4), (13.0, 0.0, 2.4), (17.0, 0.0, -2.6), (17.0, 0.0, 2.6), (15.0, 5.0 if q < 2 else 1.2, -1.8), (15.0, 5.0 if q < 2 else 1.2, 1.8)]])
        hull(c, "machgrey", P)
        hull(c, "steel", np.array([(r * math.cos(ang) - t * math.sin(ang), y, r * math.sin(ang) + t * math.cos(ang)) for (r, y, t) in
                                   [(14.0, 0.0, -3.0), (17.4, 0.0, -3.0), (17.4, 0.5, -3.0), (14.0, 0.5, -3.0), (14.0, 0.0, 3.0), (17.4, 0.0, 3.0), (17.4, 0.5, 3.0), (14.0, 0.5, 3.0)]]))
    for k in range(8 if c.fine else 3):
        a = rng.uniform(0, TAU)
        r = rng.uniform(6.0, 14.5)
        c.b.tube("steel", (r * math.cos(a), 0.5, r * math.sin(a)), (r * math.cos(a) + rng.uniform(-2, 2), rng.uniform(1.5, 4.5), r * math.sin(a) + rng.uniform(-2, 2)), 0.12, 4)
    c.decal_ground("soot", (0, 0), 30.0, 30.0, 0.0, y=0.5)


# ------------------------------------------------------------------------------------------------------------------ aircraft
def shuttle(state, lod, seed):
    """x +-10.3, z -13.8..14.0 (nose +z), y 1.2..7.4 on gear to 0: a broad white-grey fuselage with a blue panel line, swept wings ending in tall tip fins, a big
    engine cluster aft and a stub nose."""
    c = Ctx(state, lod, seed, breach=(3.0, 4.0, -2.0, 3.0), ledges=[(4.0, 2.0, 0.3)], ground_h=3.0)
    b = c.b
    if state == "destroyed":
        _craft_wreck(c, 10.0, 14.0, "palepaint", 1.6)
        return c
    seg = 14 if c.fine else 8
    lathe_z(c, "palepaint", [(-9.5, 2.5, 1.9, 3.9), (-4.0, 2.9, 2.2, 3.9), (4.0, 2.7, 2.0, 3.8), (9.0, 1.9, 1.4, 3.5), (12.0, 1.1, 0.9, 3.2), (14.0, 0.15, 0.15, 3.0)], seg)
    lathe_z(c, "machgrey", [(-13.2, 1.8, 1.8, 4.0), (-12.0, 2.6, 2.6, 4.0), (-9.5, 2.7, 2.6, 4.0), (-9.4, 2.4, 2.1, 3.9)], seg)
    lathe_z(c, "steel", [(-13.8, 1.3, 1.3, 4.0), (-13.2, 1.9, 1.9, 4.0)], seg, cap_front=False)
    for sx in (-1, 1):                                                                # swept wings, root chord long, tips back at z -10, upturned tip fins
        w = [(sx * 2.0, 3.1, 8.0), (sx * 10.3, 2.7, -6.0), (sx * 10.3, 2.7, -10.4), (sx * 2.0, 3.1, -9.0)]
        hull(c, "palepaint", [(x, y + dy, z) for (x, y, z) in w for dy in (-0.15, 0.25)])
        hull(c, "bluetrim", [(sx * 3.4, 3.2, 3.0), (sx * 9.6, 2.9, -5.0), (sx * 9.6, 2.9, -7.0), (sx * 3.4, 3.2, -3.0)] + [(sx * 3.4, 3.45, 3.0), (sx * 9.6, 3.1, -5.0), (sx * 9.6, 3.1, -7.0), (sx * 3.4, 3.45, -3.0)])
        hull(c, "palepaint", [(sx * 10.0, 2.7, -6.0), (sx * 10.3, 2.7, -10.4), (sx * 10.2, 7.4, -9.4), (sx * 10.2, 7.4, -8.2), (sx * 10.0, 4.0, -5.6)])
        hull(c, "bluetrim", [(sx * 10.0, 5.0, -8.0), (sx * 10.45, 5.0, -8.0), (sx * 10.2, 6.5, -9.2), (sx * 10.45, 6.5, -9.2)])
        for k in range(5 if c.fine else 2):
            b.box("wglass", (sx * 2.7, 4.2, 2.0 + k * 1.4), (0.08, 0.5, 0.8))
    b.box("machgrey", (0, 5.85, -3.0), (3.4, 0.4, 9.0))
    if c.fine:
        for k in range(6):
            b.box("steel", (0, 6.1, -7.0 + k * 1.6), (3.0, 0.12, 0.5))
    hull(c, "wglass", [(-0.3, 4.6, 12.4), (0.3, 4.6, 12.4), (-1.6, 4.4, 9.4), (1.6, 4.4, 9.4), (-0.4, 4.8, 12.0), (0.4, 4.8, 12.0), (-1.4, 5.0, 9.6), (1.4, 5.0, 9.6)])
    for z_ in (11.0, -3.0):                                                           # gear: one nose strut, two main bogies
        for sx in ((0.0,) if z_ > 5 else (-2.8, 2.8)):
            b.tube("steel", (sx, 2.6, z_), (sx, 0.6, z_), 0.14, 5)
            b.tube("machgrey", (sx - 0.3, 0.45, z_), (sx + 0.3, 0.45, z_), 0.45, 8 if c.fine else 5)
    if c.state == "damaged":
        scorch_patch(c, V([2.95, 3.9, -3.0]), (1, 0, 0), 4.0, 2.2, (0, 0, 1))
        roof_scorch(c, 0.0, 6.1, 1.5, 1.6)
        bent_beams(c, (0.0, 6.0, 1.5), 3)
    return c


def privatejet(state, lod, seed):
    """x +-9.7, z -12.8..15.6 (nose +z), y to 7.5: slim mauve-and-white fuselage, swept delta wings with upturned winglet fins, twin aft engines, porthole row."""
    c = Ctx(state, lod, seed, breach=(1.0, 3.0, 2.0, 3.0), ledges=[(3.0, 2.0, 0.3)], ground_h=3.0)
    b = c.b
    if state == "destroyed":
        _craft_wreck(c, 9.2, 14.0, "jetmauve", 1.4)
        return c
    seg = 12 if c.fine else 7
    lathe_z(c, "jetmauve", [(-12.8, 0.7, 0.7, 2.8), (-9.0, 1.4, 1.5, 2.9), (0.0, 1.5, 1.7, 2.9), (8.0, 1.2, 1.3, 2.7), (13.0, 0.5, 0.5, 2.4), (15.6, 0.05, 0.05, 2.3)], seg)
    lathe_z(c, "steinerwhite", [(-5.0, 1.46, 0.9, 2.3), (4.0, 1.5, 0.9, 2.25)], seg, cap_front=False, cap_back=False) if False else None
    for sx in (-1, 1):
        w = [(sx * 1.2, 2.6, 5.0), (sx * 9.7, 2.5, -9.8), (sx * 9.7, 2.5, -12.8), (sx * 1.2, 2.6, -7.5)]
        hull(c, "jetmauve", [(x, y + dy, z) for (x, y, z) in w for dy in (-0.12, 0.2)])
        hull(c, "steinerwhite", [(x, y - 0.1 + dy, z) for (x, y, z) in [(sx * 1.4, 2.5, 4.0), (sx * 9.2, 2.45, -9.0), (sx * 9.2, 2.45, -10.0), (sx * 1.4, 2.5, -6.0)] for dy in (-0.14, 0.0)])
        hull(c, "jetmauve", [(sx * 9.7, 2.5, -9.8), (sx * 9.7, 2.5, -12.8), (sx * 9.5, 7.5, -12.2), (sx * 9.5, 7.5, -11.4)])                  # winglet fin
        hull(c, "steinerwhite", [(sx * 0.7, 3.0, -5.0), (sx * 2.5, 3.0, -5.0), (sx * 2.5, 4.2, -5.0), (sx * 0.9, 4.0, -5.0), (sx * 0.7, 3.0, -10.5), (sx * 2.5, 3.0, -10.5), (sx * 2.5, 4.0, -10.5), (sx * 0.9, 3.9, -10.5)])  # engine nacelle
        b.box("machgrey", (sx * 1.7, 3.5, -10.6), (1.5, 1.1, 0.12))
        hull(c, "jetmauve", [(sx * 0.3, 3.8, -8.5), (sx * 3.8, 3.5, -11.0), (sx * 3.8, 3.5, -12.8), (sx * 0.3, 3.9, -12.8)])                       # tail plane
        for k in range(7 if c.fine else 3):
            b.box("wglass", (sx * 1.52, 3.0, 8.0 - k * 1.45), (0.07, 0.5, 0.6))
        for z_, sxx in ((8.0, 0.0), (-4.0, -1.5), (-4.0, 1.5)):
            pass
    for sx in (-1, 1):
        hull(c, "steinerwhite", [(sx * 1.2, 2.8, 8.2), (sx * 4.6, 2.8, 5.0), (sx * 4.6, 2.8, 4.2), (sx * 1.2, 2.8, 5.0)] + [(sx * 1.2, 3.0, 8.0), (sx * 4.4, 3.0, 4.8), (sx * 4.4, 3.0, 4.3), (sx * 1.2, 3.0, 5.2)])
    hull(c, "wglass", [(-0.5, 3.0, 12.2), (0.5, 3.0, 12.2), (-0.8, 3.0, 10.2), (0.8, 3.0, 10.2), (-0.4, 3.45, 12.0), (0.4, 3.45, 12.0), (-0.75, 3.45, 10.3), (0.75, 3.45, 10.3)])
    for z_, sx in ((9.0, 0.0), (-3.0, -3.2), (-3.0, 3.2)):                           # gear
        b.tube("steel", (sx, 2.2, z_), (sx, 0.4, z_), 0.12, 5)
        b.tube("machgrey", (sx - 0.3, 0.35, z_), (sx + 0.3, 0.35, z_), 0.35, 8 if c.fine else 5)
    if c.state == "damaged":
        scorch_patch(c, V([1.55, 3.0, 0.0]), (1, 0, 0), 3.4, 1.8, (0, 0, 1))
        bent_beams(c, (-6.0, 2.9, -5.0), 3)
    return c


def _lifeboat_hull(c, mat, wear=False, scale=1.0):
    b = c.b
    # a triangular arrowhead: pointed nose at +z, wing tips swept back and up, a raised spine and canopy
    P = [(0.0, 0.45, 2.9), (-1.0, 0.4, -2.0), (1.0, 0.4, -2.0), (-2.3, 1.1, -1.7), (2.3, 1.1, -1.7), (-2.3, 1.7, -2.0), (2.3, 1.7, -2.0), (0.0, 1.0, 1.6), (-0.9, 1.15, -1.9), (0.9, 1.15, -1.9)]
    hull(c, mat, P)
    hull(c, "wglass", [(-0.25, 0.95, 1.6), (0.25, 0.95, 1.6), (-0.55, 1.05, 0.0), (0.55, 1.05, 0.0), (-0.2, 1.18, 1.4), (0.2, 1.18, 1.4), (-0.45, 1.25, 0.1), (0.45, 1.25, 0.1)])
    lathe_z(c, "machgrey", [(-2.9, 0.75, 0.75, 0.95), (-2.0, 0.55, 0.55, 0.95), (-1.8, 0.7, 0.7, 0.95)], 10 if c.fine else 6, cap_front=True)
    lathe_z(c, "steel", [(-2.8, 0.6, 0.6, 0.95), (-2.4, 0.78, 0.78, 0.95)], 10 if c.fine else 6, cap_front=False)
    if c.fine:
        for sx in (-1, 1):
            b.box("bluetrim", (sx * 1.2, 0.95, -0.4), (0.5, 0.1, 1.6), axis_angle(V([0, 1.0, 0]), -sx * 0.3))
    for sx, z_ in ((-1.2, -1.0), (1.2, -1.0), (0.0, 1.6)):
        b.tube("steel", (sx, 0.45, z_), (sx, 0.0, z_), 0.07, 4)
        b.box("machgrey", (sx, 0.05, z_), (0.35, 0.1, 0.35))


def lifeboat(state, lod, seed):
    """x +-2.3, z -2.4..2.9, y 0..1.8: yellow arrowhead escape craft with a canopy, an engine bell aft and a small landing gear."""
    c = Ctx(state, lod, seed, breach=(0.0, 1.0, 0.0, 1.4), ledges=[(1.2, 0.5, 0.3)], ground_h=1.5)
    if state == "destroyed":
        _lifeboat_wreck(c, "boatyellow")
        return c
    _lifeboat_hull(c, "boatyellow")
    if c.state == "damaged":
        scorch_patch(c, V([0.0, 1.38, 0.8]), (0, 1, 0), 1.4, 1.2, (1, 0, 0))
        bent_beams(c, (0.0, 1.3, -0.5), 2, 0.04)
    return c


def _lifeboat_wreck(c, mat, dx=0.0):
    b = c.b
    rng = c.rng
    hull(c, "concrete_dark", [(dx + x, y, z) for (x, z) in ((-1.8, -1.6), (1.8, -1.6), (1.4, 1.8), (-1.4, 1.8)) for y in (0.0, 0.35)])
    for k in range(5 if c.fine else 2):
        a = rng.uniform(0, TAU)
        r = rng.uniform(0.3, 1.5)
        b.box(mat, (dx + r * math.cos(a), 0.4 + 0.1 * k, r * math.sin(a)), (rng.uniform(0.8, 1.6), 0.14, rng.uniform(0.7, 1.4)),
              axis_angle(V([0, 1.0, 0]), a) @ axis_angle(V([1.0, 0, 0]), rng.uniform(-0.4, 0.4)))
    for k in range(3):
        a0 = V([dx + rng.uniform(-1, 1), 0.3, rng.uniform(-1, 1)])
        b.tube("steel", a0, a0 + V([rng.uniform(-0.6, 0.6), rng.uniform(0.4, 1.0), rng.uniform(-0.6, 0.6)]), 0.04, 4)
    lathe_z(c, "scorchblack", [(-2.2, 0.6, 0.6, 0.55), (-1.6, 0.5, 0.5, 0.55)], 8, cap_front=True)


def _craft_wreck(c, span, length, mat, hh):
    """A broken-backed hull lying inside the footprint: a charred keel slab, a split fuselage section, a wing stump and plates."""
    b = c.b
    rng = c.rng
    hull(c, "concrete_dark", [(x, y, z) for (x, z) in ((-span * 0.7, -length * 0.55), (span * 0.7, -length * 0.55), (span * 0.5, length * 0.6), (-span * 0.5, length * 0.6)) for y in (0.0, 0.3)])
    lathe_z(c, mat, [(-length * 0.5, 1.3, hh * 0.8, hh * 0.9), (-length * 0.1, 1.5, hh, hh), (length * 0.15, 1.3, hh * 0.85, hh * 0.85)], 10 if c.fine else 6)
    b.M = (axis_angle(V([0, 1.0, 0]), 0.35) @ axis_angle(V([1.0, 0, 0]), -0.2), V([2.0, 0.0, length * 0.3]))
    lathe_z(c, mat, [(length * 0.2, 1.1, hh * 0.7, hh * 0.7), (length * 0.55, 0.8, hh * 0.5, hh * 0.55)], 10 if c.fine else 6)
    b.M = None
    hull(c, mat, [(x, y, z) for (x, z) in ((-1.0, -1.0), (-span * 0.7, -length * 0.35), (-span * 0.75, -length * 0.45), (-1.0, -3.0)) for y in (0.5, 0.75)])
    for k in range(6 if c.fine else 2):
        a = rng.uniform(0, TAU)
        r = rng.uniform(2.0, span * 0.6)
        b.box(mat if k % 2 else "machgrey", (r * math.cos(a) * 0.8, 0.5 + 0.2 * (k % 3), r * math.sin(a) * length / span * 0.7), (rng.uniform(1.5, 3.0), 0.12, rng.uniform(1.0, 2.5)),
              axis_angle(V([0, 1.0, 0]), a) @ axis_angle(V([1.0, 0, 0]), rng.uniform(-0.4, 0.4)))
    for k in range(6 if c.fine else 2):
        a0 = V([rng.uniform(-span * 0.5, span * 0.5), 0.4, rng.uniform(-length * 0.4, length * 0.4)])
        b.tube("steel", a0, a0 + V([rng.uniform(-1, 1), rng.uniform(0.8, 2.2), rng.uniform(-1.5, 1.5)]), 0.08, 4)
    c.decal_ground("soot", (0, 0), span * 1.6, length * 1.2, 0.0, y=0.32)


# ------------------------------------------------------------------------------------------------------------------ lamps
def _lamp(kind, tall):
    """A runway / beacon lamp: a round steel plinth, a short stem and an emissive lens dome under an additive halo quad. `kind` = white|red|blue|green."""
    def build(state, lod, seed):
        c = Ctx(state, lod, seed, breach=(0.0, 0.3, 0.0, 0.4), ledges=[], ground_h=0.6)
        b = c.b
        seg = 12 if c.fine else 6
        R = 0.3
        b.revolve("steel", [(0.0, 0.0), (R + 0.06, 0.0), (R + 0.06, 0.12), (R, 0.18), (0.0, 0.18)], seg, uref=0.3)
        h0 = 0.18
        if tall:
            b.tube("machgrey", (0, h0, 0), (0, h0 + 0.5, 0), 0.1, 8 if c.fine else 5)
            b.revolve("steel", [(0.0, h0 + 0.5), (0.24, h0 + 0.5), (0.24, h0 + 0.58), (0.0, h0 + 0.58)], seg, uref=0.2)
            h0 += 0.58
        lamp = "lamp_" + kind
        if state == "destroyed":
            lamp = "lamp_off"
            b.revolve(lamp, [(0.3, h0), (0.28, h0 + 0.12), (0.14, h0 + 0.2)], seg, th0=0.0, th1=TAU * 0.6, uref=0.3)
            b.box("scorchblack", (0.0, 0.01, 0.0), (1.1, 0.02, 1.1))
            return c
        ph = 0.0
        if state == "damaged":                                                      # cracked housing, lens knocked sideways
            b.M = (axis_angle(V([1.0, 0, 0]), 0.35), V([0.0, 0.0, 0.0]))
        b.revolve(lamp, [(0.0, h0), (0.3, h0), (0.3, h0 + 0.06), (0.26, h0 + 0.2), (0.17, h0 + 0.3), (0.0, h0 + 0.34)], seg, uref=0.3)
        b.revolve("steel", [(0.31, h0 - 0.02), (0.31, h0 + 0.06), (0.34, h0 + 0.06), (0.34, h0 - 0.02)], seg, uref=0.3)       # lens ring
        b.M = None
        if state == "damaged":
            b.box("scorchblack", (0.0, 0.01, 0.0), (0.9, 0.02, 0.9))
        else:
            ctr = V([0.0, h0 + 0.3, 0.0])                                           # additive halo: four near-coincident points, UV = corner
            P = np.array([ctr + V([-0.01, -0.01, 0]), ctr + V([0.01, -0.01, 0]), ctr + V([0.01, 0.01, 0]), ctr + V([-0.01, 0.01, 0])])
            b.add("halo_" + kind, P, np.tile((0, 0, 1.0), (4, 1)), np.array([(0, 0), (1, 0), (1, 1), (0, 1)]), [(0, 1, 2), (0, 2, 3)])
        return c
    return build


# ------------------------------------------------------------------------------------------------------------------ registry
def scaled_noop(fn):
    return fn


MEMBERS = {
    "rpbuilding": (rpbuilding, "resource-point warehouse: brown-tan ribbed roof panels, bevelled full-depth end pieces"),
    "terminal1": (terminal1, "spaceport terminal with one tilted spotlight mast and a stair"),
    "terminal2": (terminal2, "spaceport terminal with two masts and two stairs"),
    "walkway": (walkway, "spaceport glazed walkway block"),
    "lobby": (lobby, "spaceport lobby: white base under a black-framed glass hall"),
    "centerlobby": (centerlobby, "spaceport centre lobby: tall stepped white block with chamfered stems"),
    "hub": (hub, "spaceport hub: stepped octagonal base under a vent tower"),
    # "dropshipdavion": (_dropship("dropshipdavion", "hulldavion"), "Davion dropship: egg hull, four legs, red sunburst cap"),  # shelved: the approved HD sculpt is used
    # "dropshipliao": (_dropship("dropshipliao", "hullliao"), "Liao dropship: egg hull, four legs, teal triangle cap"),  # shelved: the approved HD sculpt is used
    # "dropshipsteiner": (_dropship("dropshipsteiner", "hullsteiner"), "Steiner dropship: egg hull, four legs, red fist cap"),  # shelved: the approved HD sculpt is used
    "shuttle": (shuttle, "aero shuttle: delta wings, aft engine cluster, tail fin"),
    # "privatejet": (privatejet, "private jet: slim mauve fuselage, swept wings with winglet fins"),  # shelved: the approved HD sculpt is used
    # "lifeboat": (lifeboat, "yellow arrowhead lifeboat"),  # shelved: the approved HD sculpt is used
    "lifeboatcrashed": (LB.lifeboatcrashed, "crashed lifeboat (X-38 sculpt, tools/art/v3/bld_lifeboat.py): nose-down, torn open"),
    "lifeboatrusted": (LB.lifeboatrusted, "rusted lifeboat (X-38 sculpt, tools/art/v3/bld_lifeboat.py) tipped on a wing"),
    "runwaylight": (_lamp("white", False), "runway lamp: low plinth, warm white emissive lens, halo"),
    "redbeaconlight": (_lamp("red", True), "red beacon lamp on a stem, emissive lens, halo"),
    "bluebeaconlight": (_lamp("blue", True), "blue beacon lamp on a stem, emissive lens, halo"),
    "greenbeaconlight": (_lamp("green", True), "green beacon lamp on a stem, emissive lens, halo"),
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
