#!/usr/bin/env python3
"""v3 Steiner government / admin complex (LANCE-39): s_main (+ leftwing, rightwing, stairs), s_admin_entry / _wing / _core, s_adminquarter, s_gov1, s_gov2,
s_govresidence, s_promenade, s_quetragon. Built to the Shared Source originals' per-part slices and plan heightmaps (game/tools/orig_parts.gd, orig_bounds.gd,
/mnt/nvme1n1p1/mc2-rework/bld/steiner/hmap.py), in the frame the originals' meshes use (the glb root's own scale is not applied in game). Reuses the military
family's helpers (ribbon, scorch, roof_scorch, frustum) and the Steiner materials (creamwall, bluetrim, lightroof, glassblue, tealwall). Windows are separate
exact rectangles (glass quads plus sill bars), never holes. Style guide: docs/art/STYLE-GUIDE.md section 10.

    python3 -I tools/art/v3/bld_steinergov.py <app>|all
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bld_hangars as H  # noqa: E402
import bld_industry as I  # noqa: E402
from bld_city import blk2, rubble  # noqa: E402
from bld_industry import V, TAU, shell, fpanel, door, band, ROOT  # noqa: E402
from bld_military import frustum, ribbon, scorch, roof_scorch  # noqa: E402

WALL = ("steinerwhite", "flat")
TEAL = ("tealwall", "flat")


# ------------------------------------------------------------------------------------------------------------------ geometry helpers
def _centroid(poly):
    return np.mean(np.asarray(poly, float), axis=0)


def poly_ext(c, mat, poly, y0, y1, top=None):
    """A convex polygon (x, z points) extruded from y0 to y1: flat side quads, an up-facing fan on top (top = its material)."""
    b = c.b
    poly = np.asarray(poly, float)
    cen = _centroid(poly)
    n = len(poly)
    for k in range(n):
        a, d = poly[k], poly[(k + 1) % n]
        e = d - a
        L = float(np.hypot(*e)) or 1.0
        nx, nz = e[1] / L, -e[0] / L
        if (a[0] - cen[0]) * nx + (a[1] - cen[1]) * nz < 0:
            nx, nz = -nx, -nz
        P = np.array([(a[0], y0, a[1]), (d[0], y0, d[1]), (d[0], y1, d[1]), (a[0], y1, a[1])])
        U = np.array([(0, y0), (L, y0), (L, y1), (0, y1)])
        b.add(mat, P, np.array([(nx, 0, nz)] * 4), U, [(0, 1, 2), (0, 2, 3)])
    if top:
        P = [(cen[0], y1, cen[1])] + [(p[0], y1, p[1]) for p in poly]
        b.add(top, np.array(P), np.array([(0, 1, 0)] * len(P)), np.array([(p[0], p[2]) for p in P]), [(0, 1 + k, 1 + (k + 1) % n) for k in range(n)])


def poly_frustum(c, mat, pa, ya, pb, yb):
    """Sloped quads between two polygons with the same vertex order (a hip roof over any convex plan)."""
    b = c.b
    pa = np.asarray(pa, float)
    pb = np.asarray(pb, float)
    cen = _centroid(pa)
    n = len(pa)
    for k in range(n):
        k2 = (k + 1) % n
        P = np.array([(pa[k][0], ya, pa[k][1]), (pa[k2][0], ya, pa[k2][1]), (pb[k2][0], yb, pb[k2][1]), (pb[k][0], yb, pb[k][1])])
        nn = np.cross(P[1] - P[0], P[3] - P[0])
        nn = nn / (np.linalg.norm(nn) or 1.0)
        if np.dot(nn, P.mean(0) - np.array([cen[0], (ya + yb) / 2, cen[1]])) < 0:
            nn = -nn
        L = float(np.linalg.norm(P[1] - P[0]))
        H_ = float(np.linalg.norm(P[3] - P[0]))
        b.add(mat, P, np.array([nn] * 4), np.array([(0, 0), (L, 0), (L, H_), (0, H_)]), [(0, 1, 2), (0, 2, 3)])


def rect_poly(box, grow=0.0):
    x0, x1, z0, z1 = box
    return [(x0 - grow, z0 - grow), (x1 + grow, z0 - grow), (x1 + grow, z1 + grow), (x0 - grow, z1 + grow)]


def hip(c, box, y, rise, inset, over=0.4, mat="tealwall", cap="lightroof", trim=True, cap_t=0.3):
    """A hipped teal roof on a rectangle: eaves over the wall box by `over` at y, a flat pale top `inset` (x, z) in from the wall at y + rise, a blue trim
    line along the eave (fine LOD). Returns the y of the flat top."""
    if c.state == "destroyed":
        return y
    ix, iz = (inset, inset) if np.isscalar(inset) else inset
    x0, x1, z0, z1 = box
    pa = rect_poly(box, over)
    pb = [(x0 + ix, z0 + iz), (x1 - ix, z0 + iz), (x1 - ix, z1 - iz), (x0 + ix, z1 - iz)]
    poly_frustum(c, mat, pa, y, pb, y + rise)
    if trim and c.fine:
        f = 0.14
        pc = [(a[0] + (bb[0] - a[0]) * f, a[1] + (bb[1] - a[1]) * f) for a, bb in zip(pa, pb)]
        poly_frustum(c, "bluetrim", [(p[0], p[1]) for p in rect_poly(box, over + 0.05)], y - 0.05, [(p[0], p[1]) for p in pc], y + rise * f)
    c.b.box(cap, ((x0 + x1) / 2, y + rise + cap_t / 2, (z0 + z1) / 2), (x1 - x0 - 2 * ix, cap_t, z1 - z0 - 2 * iz))
    return y + rise + cap_t


def wblock(c, box, h, y0=0.0, roof=None, main=False, seed=0, wall=WALL, **kw):
    x0, x1, z0, z1 = box
    if c.state == "destroyed" and min(x1 - x0, z1 - z0) < 4.0:      # too thin for the collapse kit: a charred low stub
        c.b.box("concrete_dark", ((x0 + x1) / 2, y0 + 0.6, (z0 + z1) / 2), (x1 - x0, 1.2, z1 - z0))
        return
    blk2(c, x0, x1, z0, z1, h, wall, y0=y0, roof=roof, main=main, ac=0, vents=0, hatch=0, lights=0, seed=seed, mat="lightroof", trim="bluetrim", parapet=0.3, **kw)


def wins(c, key, box, y0, rows, cols, v0=1.4, pitch=3.4, wh=2.2, ww=1.4, inset=1.4, mat="glassblue", sill=True):
    """cols x rows of separate glass rectangles on one face (each at most 70 % of its cell, so none can touch), with a pale sill bar under each on the fine LOD."""
    if c.state == "destroyed":
        return
    L = I._face(key, *box)[3]
    span = L - 2 * inset
    if span <= 0.5:
        return
    step = span / cols
    w = min(ww, step * 0.7)
    for j in range(rows):
        for i in range(cols):
            u = inset + (i + 0.5) * step - w / 2
            fpanel(c, mat, key, box, u, v0 + j * pitch, w, wh, y0, 0.06)
            if sill and c.fine:
                fpanel(c, "bluetrim", key, box, u - 0.15, v0 + j * pitch - 0.2, w + 0.3, 0.18, y0, 0.08)


def columns(c, pts, y0, y1, r=0.4, mat="creamwall"):
    if c.state == "destroyed":
        return
    for (x, z) in pts:
        c.b.tube(mat, (x, y0, z), (x, y1, z), r, 8 if c.fine else 5)


def slab(c, box, y, t, mat="lightroof", trim="bluetrim"):
    """A thin flat slab (canopy roof, paving) with a pale edge fascia on the fine LOD."""
    x0, x1, z0, z1 = box
    c.b.box(mat, ((x0 + x1) / 2, y + t / 2, (z0 + z1) / 2), (x1 - x0, t, z1 - z0))
    if trim and c.fine and t > 0.3:
        c.b.box(trim, ((x0 + x1) / 2, y + 0.12, z0), (x1 - x0 + 0.1, 0.22, 0.12))
        c.b.box(trim, ((x0 + x1) / 2, y + 0.12, z1), (x1 - x0 + 0.1, 0.22, 0.12))


def ruin(c, box, h, n=10):
    rubble(c, box, h, max(3, n // 3))


# ------------------------------------------------------------------------------------------------------------------ s_main complex
def s_main(state, lod, seed):
    """Measured: rear slab x +-21.3, z -11..5.4, walls to y 20, hip to y 24, glazed lantern to 26.9; front block z 5.3..13.6; central pavilion x +-4.4 to z 20.3
    (roof 19); porch to z 24.1 (11); two wings h 9 either side (x 4.4..12.3)."""
    c = shell(state, lod, seed, (0.0, 12.0, 5.0, 6.0), 2.0)
    b = c.b
    slabbox = (-21.2, 21.2, -11.0, 5.3)
    wblock(c, slabbox, 20.0, main=True, seed=seed)
    wblock(c, (-19.4, 19.4, 5.3, 13.6), 17.6, roof="flat", seed=seed + 1)
    wblock(c, (-4.4, 4.4, 13.6, 20.3), 17.9, roof="flat", seed=seed + 2)
    wblock(c, (-3.8, 3.8, 20.3, 24.1), 10.2, roof="flat", seed=seed + 3)
    wblock(c, (-12.3, -4.4, 13.6, 20.3), 8.5, roof="flat", seed=seed + 4)
    wblock(c, (4.4, 12.3, 13.6, 20.3), 8.5, roof="flat", seed=seed + 5)
    if state != "destroyed":
        ytop = hip(c, slabbox, 20.0, 4.0, (3.0, 2.4), over=0.1)
        lant = (-17.9, 17.9, -9.1, 2.1)
        frustum(c, "tealwall", 0.0, -3.5, 17.9, 5.6, ytop - 0.3, 15.9, 4.8, 26.5)
        b.box("tealpanel", (0.0, 26.7, -3.5), (31.8, 0.4, 9.6))
        if c.fine:
            for k in range(17):
                b.box("bluetrim", (-15.2 + k * 1.9, 26.95, -3.5), (0.16, 0.12, 9.6))
        for key in ("-z", "+x", "-x"):
            wins(c, key, slabbox, 0.0, 4, {"-z": 12, "+x": 4, "-x": 4}[key], v0=2.0, pitch=4.4, wh=2.6, ww=1.5, inset=2.0)
        for key, bx in (("-x", (-19.4, 19.4, 5.3, 13.6)), ("+x", (-19.4, 19.4, 5.3, 13.6))):
            wins(c, key, bx, 0.0, 3, 3, v0=2.2, pitch=4.8, wh=2.6, ww=1.4, inset=1.2)
        wins(c, "+z", (-19.4, -12.3, 5.3, 13.6), 0.0, 3, 3, v0=2.2, pitch=4.8, wh=2.6, ww=1.3, inset=0.8)
        wins(c, "+z", (12.3, 19.4, 5.3, 13.6), 0.0, 3, 3, v0=2.2, pitch=4.8, wh=2.6, ww=1.3, inset=0.8)
        wins(c, "+z", (-4.4, 4.4, 13.6, 20.3), 0.0, 3, 2, v0=2.4, pitch=5.0, wh=3.0, ww=1.6, inset=0.9)
        for bx in ((-12.3, -4.4, 13.6, 20.3), (4.4, 12.3, 13.6, 20.3)):
            wins(c, "+z", bx, 0.0, 2, 2, v0=1.6, pitch=3.4, wh=2.2, ww=1.3, inset=1.0)
        door(c, "+z", (-3.8, 3.8, 20.3, 24.1), 2.3, 3.2, 3.8)
        band(c, "+z", (-19.4, 19.4, 5.3, 13.6), 15.2, 0.4, "bluetrim")
        band(c, "-z", slabbox, 19.0, 0.5, "bluetrim")
    else:
        for bx, hh in ((slabbox, 20.0), ((-19.4, 19.4, 5.3, 13.6), 14.0), ((-4.4, 4.4, 13.6, 24.1), 10.0)):
            ruin(c, bx, hh, 14)
    if state == "damaged":
        scorch(c, "+x", slabbox, 8.0, 8.0, 2.4)
        scorch(c, "-z", slabbox, 28.0, 6.0, 1.8)
        roof_scorch(c, 8.0, 24.4, -4.0, 2.4)
    return c


def s_main_leftwing(state, lod, seed):
    """Tower block x -5.9..10.2 (walls y 0..10, hip to 16, ridge a thin line along z) plus a long low wing x 10..38.1, z -7..0.9 (flat roof, y 5)."""
    c = shell(state, lod, seed, (4.0, 8.0, -3.0, 4.0), 2.0)
    tower = (-5.4, 9.7, -10.1, 3.7)
    wblock(c, tower, 10.0, main=True, seed=seed)
    low = (9.6, 37.7, -6.9, 0.5)
    wblock(c, low, 4.6, roof="flat", seed=seed + 1)
    if state != "destroyed":
        hip(c, tower, 10.0, 5.6, (5.0, 5.8), over=0.4, cap_t=0.4)
        for key in ("-z", "+z", "-x"):
            wins(c, key, tower, 0.0, 2, {"-z": 4, "+z": 4, "-x": 3}[key], v0=1.6, pitch=4.4, wh=2.8, ww=1.3, inset=1.2)
        wins(c, "+x", tower, 0.0, 2, 3, v0=1.6, pitch=4.4, wh=2.8, ww=1.3, inset=1.2)
        for key in ("-z", "+z"):
            ribbon(c, key, low, 1.2, 1.6, 0.0, 1.0, None, 9, 0.8, trim="bluetrim")
        door(c, "+x", low, 2.6, 1.4, 2.4)
        band(c, "+z", tower, 6.6, 0.4, "bluetrim")
    else:
        ruin(c, tower, 8.0, 10)
        ruin(c, low, 3.0, 12)
    if state == "damaged":
        scorch(c, "+z", tower, 7.0, 4.5, 1.6)
        roof_scorch(c, 20.0, 5.0, -3.2, 2.0)
    return c


def s_main_rightwing(state, lod, seed):
    """Main block x -11.6..3.8, z -9.8..3.8, walls to 14, mansard to 17.6 under a flat grey top; a front annex x -7.7..0, z 5.5..11.3 (low, y 4) with a hipped
    teal porch z 3.7..5.6 at y 6..8."""
    c = shell(state, lod, seed, (-4.0, 8.0, -3.0, 5.0), 2.0)
    main = (-11.6, 3.8, -9.8, 3.8)
    wblock(c, main, 14.0, main=True, seed=seed)
    annex = (-7.7, -0.0, 5.5, 11.3)
    porch = (-8.8, 1.1, 3.8, 5.7)
    wblock(c, annex, 4.0, roof="flat", seed=seed + 1)
    wblock(c, porch, 6.0, seed=seed + 2)
    if state != "destroyed":
        hip(c, main, 14.0, 3.4, 3.5, over=0.5)
        hip(c, porch, 6.0, 1.8, (0.6, 0.55), over=0.3, trim=False)
        for key in ("-z", "+x", "-x"):
            wins(c, key, main, 0.0, 3, {"-z": 4, "+x": 4, "-x": 4}[key], v0=1.6, pitch=4.2, wh=2.8, ww=1.4, inset=1.3)
        wins(c, "+z", (-11.6, -8.8, -9.8, 3.8), 0.0, 3, 1, v0=1.6, pitch=4.2, wh=2.8, ww=1.2, inset=0.7)
        wins(c, "+z", (1.1, 3.8, -9.8, 3.8), 0.0, 3, 1, v0=1.6, pitch=4.2, wh=2.8, ww=1.2, inset=0.7)
        door(c, "+z", annex, 2.8, 1.6, 2.4)
        band(c, "-z", main, 12.6, 0.4, "bluetrim")
    else:
        ruin(c, main, 11.0, 12)
        ruin(c, annex, 3.0, 4)
    if state == "damaged":
        scorch(c, "-x", main, 6.0, 5.0, 1.8)
        roof_scorch(c, -4.0, 17.5, -3.0, 1.8)
    return c


def s_main_stairs(state, lod, seed):
    """A stepped descent: a pale plaza at y 0 (z 3.6..15, x +-14.4) falling away in ten treads to x +-23.8 at y -10 (front tip z 21.7), then a straight stair
    down to y -19 at z 34. Two low pylons (y 1.8) flank its head."""
    c = shell(state, lod, seed, (0.0, 0.0, 12.0, 5.0), 2.0)
    b = c.b
    P0 = [(-14.4, 3.6), (14.3, 3.6), (14.3, 10.5), (7.5, 15.0), (-7.5, 15.0), (-14.4, 10.5)]
    P10 = [(-23.8, 3.6), (23.7, 3.6), (23.7, 6.5), (4.6, 21.7), (-4.6, 21.7), (-23.8, 6.5)]
    n = 10 if c.fine else 6
    ks = [round(10.0 * k / n) for k in range(n + 1)] if n < 10 else list(range(11))
    for k in sorted(set(ks)):
        t = k / 10.0
        poly = [(a[0] + (d[0] - a[0]) * t, a[1] + (d[1] - a[1]) * t) for a, d in zip(P0, P10)]
        top = "lightroof"
        poly_ext(c, "steinerwhite" if k else "lightroof", poly, -k - 1.2, -k + (0.0 if k else 0.25), top=top)
    # the central flight: boxes stepping down z 15..34
    steps = 16 if c.fine else 8
    z_a, z_b = 14.8, 33.9
    y_a, y_b = -2.6, -18.8
    dz = (z_b - z_a) / steps
    for k in range(steps):
        zc = z_a + (k + 0.5) * dz
        yt = y_a + (y_b - y_a) * (k + 1) / steps
        hbox = 2.6
        b.box("lightroof", (0.0, yt - hbox / 2, zc), (5.9, hbox, dz + 0.02))
        if c.fine:
            b.box("creamwall", (-3.2, yt - hbox / 2 + 0.2, zc), (0.5, hbox + 0.4, dz + 0.02))
            b.box("creamwall", (3.2, yt - hbox / 2 + 0.2, zc), (0.5, hbox + 0.4, dz + 0.02))
    if state != "destroyed":
        for sx in (-1, 1):
            b.box("creamwall", (sx * 2.95, 0.9, 13.6), (3.2, 1.8, 4.2))
            b.box("bluetrim", (sx * 2.95, 1.85, 13.6), (3.5, 0.15, 4.5))
            b.tube("lightroof", (sx * 2.95, 1.8, 13.6), (sx * 2.95, 3.4, 13.6), 0.12, 5)
    else:
        rubble(c, (-14.0, 14.0, 4.0, 14.5), 3.0, 8)
    if state == "damaged":
        b.box("scorchblack", (-6.0, 0.28, 8.0), (4.0, 0.06, 3.0), None)
        b.box("scorchblack", (8.0, 0.28, 6.5), (3.0, 0.06, 2.2), None)
        b.box("steel", (2.95, 2.1, 13.6), (3.0, 0.4, 0.4), None)
    return c


# ------------------------------------------------------------------------------------------------------------------ admin trio
def s_admin_entry(state, lod, seed):
    """A cross-plan entry hall: centre x +-10.6, z -8.2..5.6; arms x +-7.2 to z -15.2 and to 12.7; flat roof at y 6 with a glazed skylight (y 7) at the middle."""
    c = shell(state, lod, seed, (0.0, 3.0, 0.0, 4.0), 2.0)
    b = c.b
    centre = (-10.6, 10.6, -8.2, 5.6)
    north = (-7.2, 7.2, -15.2, -8.2)
    south = (-7.2, 7.2, 5.6, 12.7)
    for k, bx in enumerate((centre, north, south)):
        wblock(c, bx, 5.8, roof="flat", main=(k == 0), seed=seed + k, wall=TEAL)
    if state != "destroyed":
        for key in ("-x", "+x"):
            ribbon(c, key, centre, 1.5, 1.8, 0.0, 0.7, None, 5, 0.9, trim="bluetrim", mat="steinerwhite")
        for bx in (north, south):
            for key in ("-x", "+x"):
                ribbon(c, key, bx, 1.5, 1.8, 0.0, 0.7, None, 3, 0.9, trim="bluetrim", mat="steinerwhite")
        ribbon(c, "-z", north, 1.5, 1.8, 0.0, 0.9, None, 3, 1.0, trim="bluetrim", mat="steinerwhite")
        ribbon(c, "+z", south, 1.5, 1.8, 0.0, 0.9, None, 3, 1.0, trim="bluetrim", mat="steinerwhite")
        ribbon(c, "-z", centre, 1.5, 1.8, 0.0, 0.9, None, 2, 1.0, trim="bluetrim", mat="steinerwhite")
        ribbon(c, "+z", centre, 1.5, 1.8, 0.0, 0.9, None, 2, 1.0, trim="bluetrim", mat="steinerwhite")
        door(c, "+z", south, 5.9, 1.4, 2.4)
        b.box("lightroof", (0.0, 6.9, 0.0), (1.8, 1.1, 4.0))                   # the skylight lantern
        b.box("glassblue", (0.0, 7.5, 0.0), (1.4, 0.15, 3.6))
        band(c, "-z", centre, 4.4, 0.35, "lightroof")
    else:
        for bx in (centre, north, south):
            ruin(c, bx, 4.0, 8)
    if state == "damaged":
        scorch(c, "+x", centre, 7.0, 2.0, 1.5)
        roof_scorch(c, 4.5, 6.4, -3.0, 1.8)
    return c


def s_admin_wing(state, lod, seed):
    """A long low block x +-5.7, z -22.1..31.4, walls y 6 with a long white glazing strip, a raised glazed clerestory (x +-2.5, z -7.5..17.1) to y 8.3."""
    c = shell(state, lod, seed, (0.0, 3.0, 4.0, 5.0), 2.0)
    b = c.b
    box = (-5.4, 5.4, -21.8, 31.1)
    wblock(c, box, 5.8, roof="flat", main=True, seed=seed, wall=TEAL)
    if state != "destroyed":
        for key in ("-x", "+x"):
            ribbon(c, key, box, 3.2, 1.3, 0.0, 1.0, None, 14, 1.0, trim="bluetrim", mat="steinerwhite")
        ribbon(c, "-z", box, 2.6, 1.6, 0.0, 1.0, None, 3, 0.7, trim="bluetrim", mat="steinerwhite")
        ribbon(c, "+z", box, 2.6, 1.6, 0.0, 1.0, None, 3, 0.7, trim="bluetrim", mat="steinerwhite")
        cl = (-2.5, 2.5, -7.5, 17.1)
        b.box("lightroof", (0.0, 7.2, (cl[2] + cl[3]) / 2), (5.0, 2.4, cl[3] - cl[2]))
        b.box("lightroof", (0.0, 8.35, (cl[2] + cl[3]) / 2), (5.4, 0.2, cl[3] - cl[2] + 0.4))
        for key in ("-x", "+x"):
            ribbon(c, key, cl, 0.7, 1.0, 6.0, 0.8, None, 9, 0.5, trim="bluetrim", mat="steinerwhite")
        door(c, "-x", box, 18.0, 1.4, 2.4)
    else:
        ruin(c, box, 4.0, 14)
    if state == "damaged":
        scorch(c, "+x", box, 18.0, 2.6, 1.6)
        roof_scorch(c, 1.0, 6.4, 24.0, 2.0)
    return c


def s_admin_core(state, lod, seed):
    """Two flat side wings (x +-17.8..28.2, z -1.7..3.9, y 9.5); a middle block x +-17.8, z -8..7 to y 13; an upper block x +-14.2, z -12..3.9 to y 19; two
    rooftop pavilions (x -13.4..-6.6 / 6.2..13, z -4.6..1.4) to y 22.4."""
    c = shell(state, lod, seed, (0.0, 8.0, 0.0, 6.0), 2.0)
    b = c.b
    lw, rw = (-28.2, -17.0, -1.7, 3.9), (17.0, 28.2, -1.7, 3.9)
    mid = (-17.8, 17.8, -8.0, 7.0)
    up = (-14.2, 14.0, -11.9, 3.9)
    p1, p2 = (-13.4, -6.6, -4.6, 1.4), (6.2, 13.0, -4.6, 1.4)
    for k, bx in enumerate((lw, rw)):
        wblock(c, bx, 9.3, roof="flat", seed=seed + k, wall=TEAL)
    wblock(c, mid, 12.6, roof="flat", main=True, seed=seed + 2, wall=TEAL)
    wblock(c, up, 18.6, roof="flat", seed=seed + 3, wall=TEAL)
    for k, bx in enumerate((p1, p2)):
        wblock(c, bx, 2.9, y0=19.0, roof="flat", seed=seed + 4 + k, wall=TEAL)
    if state != "destroyed":
        for bx in (lw, rw):
            for key in ("-z", "+z"):
                ribbon(c, key, bx, 1.4, 1.4, 0.0, 0.8, None, 4, 0.8, trim="bluetrim", mat="steinerwhite")
            ribbon(c, "-x" if bx is lw else "+x", bx, 1.4, 1.4, 0.0, 0.8, None, 2, 0.8, trim="bluetrim", mat="steinerwhite")
        for key in ("-x", "+x", "+z"):
            ribbon(c, key, mid, 3.2, 1.6, 0.0, 1.2, None, {"-x": 5, "+x": 5, "+z": 12}[key], 0.9, trim="bluetrim", mat="steinerwhite")
            ribbon(c, key, mid, 8.2, 1.6, 0.0, 1.2, None, {"-x": 5, "+x": 5, "+z": 12}[key], 0.9, trim="bluetrim", mat="steinerwhite")
        for key in ("-z", "-x", "+x"):
            ribbon(c, key, up, 14.0, 2.0, 0.0, 1.2, None, {"-z": 10, "-x": 5, "+x": 5}[key], 0.9, trim="bluetrim", mat="steinerwhite")
            ribbon(c, key, up, 9.4, 1.6, 0.0, 1.2, None, {"-z": 10, "-x": 5, "+x": 5}[key], 0.9, trim="bluetrim", mat="steinerwhite")
        for bx in (p1, p2):
            b.box("lightroof", ((bx[0] + bx[1]) / 2, 22.6, (bx[2] + bx[3]) / 2), (3.2, 0.3, 2.6))
            b.box("glassblue", ((bx[0] + bx[1]) / 2, 22.8, (bx[2] + bx[3]) / 2), (3.0, 0.1, 2.4))
        door(c, "+z", mid, 16.2, 1.6, 2.6)
        band(c, "-z", up, 13.1, 0.4, "lightroof")
    else:
        for bx, hh in ((mid, 11.0), (up, 16.0), (lw, 7.0), (rw, 7.0)):
            ruin(c, bx, hh, 14)
    if state == "damaged":
        scorch(c, "+x", mid, 3.0, 6.0, 1.9)
        scorch(c, "-z", up, 7.0, 10.0, 2.2)
        roof_scorch(c, -10.0, 22.4, -1.6, 1.6)
    return c


def s_adminquarter(state, lod, seed):
    """A pentagon plan: rectangle x +-12.2, z -16..-1.8 plus a wedge to a point at z 8.5; walls y 6, a wide sloped teal canopy-roof rising to a raised flat
    top (y 8) over x +-6.6, z -13..-2.5 and the tip; an arcade of columns along the right side."""
    c = shell(state, lod, seed, (0.0, 4.0, -6.0, 4.0), 2.0)
    b = c.b
    wall = [(-12.2, -16.0), (12.2, -16.0), (12.2, -1.8), (0.0, 8.5), (-12.2, -1.8)]
    if state != "destroyed":
        poly_ext(c, "steinerwhite", wall, 0.0, 6.0, top="lightroof")
        eave = [(-12.7, -16.5), (12.7, -16.5), (12.7, -1.6), (0.0, 9.0), (-12.7, -1.6)]
        inner = [(-6.6, -13.0), (6.6, -13.0), (6.6, -2.5), (0.0, 7.2), (-6.6, -2.5)]
        poly_frustum(c, "tealwall", eave, 6.0, inner, 8.0)
        poly_ext(c, "steinerwhite", inner, 6.0, 8.0, top="lightroof")
        if c.fine:
            poly_frustum(c, "bluetrim", eave, 5.95, [(e[0] + (i[0] - e[0]) * 0.12, e[1] + (i[1] - e[1]) * 0.12) for e, i in zip(eave, inner)], 6.2)
        for sx in (-1, 1):                                                 # the arcade: columns along both flanks of the wedge
            columns(c, [(sx * 11.9, -4.0 + k * 0.0) for k in range(1)], 0.0, 6.0, 0.45)
        columns(c, [(12.0, -14.5), (12.0, -10.0), (12.0, -5.5)], 0.0, 6.0, 0.4)
        columns(c, [(-12.0, -14.5), (-12.0, -10.0), (-12.0, -5.5)], 0.0, 6.0, 0.4)
        box = (-12.2, 12.2, -16.0, -1.8)
        for key in ("-z", "-x", "+x"):
            wins(c, key, box, 0.0, 1, {"-z": 8, "-x": 4, "+x": 4}[key], v0=1.6, pitch=3.0, wh=2.4, ww=1.5, inset=1.3)
        door(c, "+x", box, 8.0, 1.4, 2.6)
    else:
        poly_ext(c, "concrete_dark", wall, 0.0, 1.6, top="concrete_dark")
        rubble(c, (-12.2, 12.2, -16.0, -1.8), 4.0, 12)
    if state == "damaged":
        scorch(c, "-z", (-12.2, 12.2, -16.0, -1.8), 8.0, 2.8, 1.6)
        roof_scorch(c, 0.0, 8.3, -8.0, 1.8)
    return c


# ------------------------------------------------------------------------------------------------------------------ government buildings
def s_gov1(state, lod, seed):
    """Central palace x +-15.2, z +-13.7, walls to y 18, hip to 21 with a stepped tower (hip 21..27.4, shaft to 29.6, cap to 30.6); a long narrow wing along
    z (x -13.6..-4.5, z +-14.7..45.6, walls 7.5, hip to 10); a paved plaza x 0.5..19.8, z +-33 with two flat canopies on columns (y 8) at each end."""
    c = shell(state, lod, seed, (0.0, 10.0, 0.0, 6.0), 2.0)
    b = c.b
    core = (-15.2, 15.3, -13.7, 13.8)
    wblock(c, core, 18.0, main=True, seed=seed)
    wn, ws = (-13.6, -4.6, -45.6, -13.7), (-13.6, -4.6, 13.8, 45.6)
    wblock(c, wn, 7.4, seed=seed + 1)
    wblock(c, ws, 7.4, seed=seed + 2)
    if state != "destroyed":
        hip(c, core, 18.0, 3.0, 3.3, over=0.8)
        y = 21.3
        frustum(c, "tealwall", 0.0, 0.0, 8.8, 7.3, 21.0, 6.3, 6.1, 27.4)
        b.box("lightroof", (0.0, 27.5, 0.0), (12.6, 0.3, 12.2))
        b.box("creamwall", (0.0, 28.5, 0.0), (10.0, 2.2, 9.6))
        if c.fine:
            for sx, sz in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
                b.tube("bluetrim", (sx * 5.0, 27.6, sz * 4.8), (sx * 5.0, 29.6, sz * 4.8), 0.2, 5)
        frustum(c, "tealwall", 0.0, 0.0, 5.4, 5.2, 29.6, 2.0, 1.9, 30.6)
        for wbx in (wn, ws):
            hip(c, wbx, 7.4, 2.4, (3.0, 2.0), over=0.4, trim=False)
        for key in ("-z", "+z", "-x", "+x"):
            wins(c, key, core, 0.0, 3, {"-z": 8, "+z": 8, "-x": 7, "+x": 7}[key], v0=1.6, pitch=5.6, wh=3.4, ww=1.5, inset=1.5)
        for key in ("-x", "+x"):
            wins(c, key, wn, 0.0, 1, 12, v0=2.0, pitch=3.0, wh=3.0, ww=1.4, inset=1.5)
            wins(c, key, ws, 0.0, 1, 12, v0=2.0, pitch=3.0, wh=3.0, ww=1.4, inset=1.5)
        door(c, "+x", core, 12.2, 2.6, 3.4)
        band(c, "-x", core, 15.8, 0.5, "bluetrim")
        band(c, "+x", core, 15.8, 0.5, "bluetrim")
        slab(c, (0.5, 19.6, -33.0, 33.0), 0.0, 0.3, "creamwall", None)
        for z0_, z1_ in ((-33.0, -26.0), (26.0, 33.0)):                          # the two canopies
            slab(c, (1.0, 18.0, z0_, z1_), 7.7, 0.5)
            columns(c, [(x, z) for x in (2.0, 9.5, 17.0) for z in (z0_ + 0.8, z1_ - 0.8)], 0.0, 7.7, 0.4)
        b.box("creamwall", (19.2, 0.6, 0.0), (1.2, 1.2, 52.0))
    else:
        ruin(c, core, 16.0, 22)
        ruin(c, wn, 6.0, 12)
        ruin(c, ws, 6.0, 12)
        rubble(c, (0.5, 18.0, -33.0, -26.0), 4.0, 3)
    if state == "damaged":
        scorch(c, "+x", core, 14.0, 7.0, 2.6)
        scorch(c, "-z", core, 10.0, 11.0, 2.2)
        roof_scorch(c, -8.0, 21.3, -6.0, 2.0)
        scorch(c, "+x", wn, 12.0, 3.0, 1.5)
    return c


def s_gov2(state, lod, seed):
    """Main block x -3.1..5.2, z -8.6..10.4 (walls to 8, hip to 10.5), a front wing x -5..3, z 4.9..12.6 (y 7.5); a forecourt canopy (y 5, two strips) on columns
    x -16..-7 with paving between; an L-shaped low wall at the back."""
    c = shell(state, lod, seed, (0.0, 4.0, 3.0, 5.0), 2.0)
    b = c.b
    main = (-3.1, 5.1, -8.6, 10.4)
    wblock(c, main, 8.0, main=True, seed=seed)
    wing = (-5.0, -3.1, 4.9, 12.6)
    wing2 = (-3.1, 3.0, 10.4, 12.6)
    wblock(c, wing, 7.0, roof="flat", seed=seed + 1)
    wblock(c, wing2, 7.0, roof="flat", seed=seed + 2)
    if state != "destroyed":
        hip(c, main, 8.0, 2.3, (2.6, 2.6), over=0.5)
        for key in ("-z", "+x", "-x"):
            wins(c, key, main, 0.0, 2, {"-z": 3, "+x": 7, "-x": 7}[key], v0=1.4, pitch=3.6, wh=2.6, ww=1.2, inset=1.2)
        wins(c, "-x", wing, 0.0, 2, 3, v0=1.4, pitch=3.4, wh=2.4, ww=1.2, inset=0.8)
        wins(c, "+z", (-3.1, 3.0, 10.4, 12.6), 0.0, 2, 2, v0=1.4, pitch=3.4, wh=2.4, ww=1.2, inset=0.8)
        door(c, "+z", wing2, 1.4, 1.6, 2.6)
        for z0_, z1_ in ((3.9, 7.1), (9.9, 13.1)):
            slab(c, (-16.0, -7.4, z0_, z1_), 4.5, 0.5)
            columns(c, [(x, z) for x in (-15.2, -11.7, -8.2) for z in (z0_ + 0.5, z1_ - 0.5)], 0.0, 4.5, 0.3)
        slab(c, (-15.6, -6.5, 7.1, 9.9), 0.0, 0.2, "creamwall", None)
        b.box("creamwall", (-14.4, 0.55, -5.5), (1.4, 1.1, 7.6))
        b.box("creamwall", (-10.5, 0.55, -8.3), (9.6, 1.1, 1.4))
    else:
        ruin(c, main, 7.0, 10)
        ruin(c, (-5.0, 3.0, 4.9, 12.6), 5.0, 6)
        rubble(c, (-16.0, -7.4, 3.9, 7.1), 2.5, 3)
    if state == "damaged":
        scorch(c, "+x", main, 8.0, 3.0, 1.6)
        scorch(c, "-z", main, 4.0, 4.5, 1.3)
        roof_scorch(c, 1.0, 10.8, 2.0, 1.6)
    return c


def s_govresidence(state, lod, seed):
    """(Original root scale 0.2154, built at that size.) Palace block x +-51, z -44.5..44.5, walls to y 18, wide hip (eaves x +-55.2) to a flat grey top at 25.8; a forecourt to z -97.6 with two long 6 m side
    walls, a gapped back wall, a central paved walk and a tall flagpole."""
    c = shell(state, lod, seed, (0.0, 10.0, -44.0, 8.0), 2.0)
    b = c.b
    blk_ = (-51.0, 51.0, -44.5, 44.5)
    wblock(c, blk_, 18.0, main=False, seed=seed)
    if state != "destroyed":
        hip(c, blk_, 18.0, 7.4, (6.6, 6.6), over=4.1, cap_t=0.4)
        if c.fine:
            b.box("bluetrim", (0.0, 25.65, -41.6), (84.0, 0.3, 0.3))
            b.box("bluetrim", (0.0, 25.65, 41.6), (84.0, 0.3, 0.3))
        for key, cols in (("-z", 24), ("+z", 24), ("-x", 20), ("+x", 20)):
            wins(c, key, blk_, 0.0, 2, cols, v0=3.4, pitch=7.2, wh=5.2, ww=3.0, inset=3.0)
        door(c, "-z", blk_, 48.6, 6.0, 8.0)
        band(c, "-z", blk_, 5.2, 0.4, "bluetrim")
        band(c, "-z", blk_, 11.2, 0.4, "bluetrim")
        for (x0_, x1_, z0_, z1_) in ((-40.8, -38.2, -97.6, -44.5), (37.9, 40.5, -97.6, -44.5), (-40.8, -12.0, -97.6, -95.0), (12.0, 40.5, -97.6, -95.0)):
            b.box("creamwall", ((x0_ + x1_) / 2, 3.0, (z0_ + z1_) / 2), (x1_ - x0_, 6.0, z1_ - z0_))
            b.box("bluetrim", ((x0_ + x1_) / 2, 6.1, (z0_ + z1_) / 2), (x1_ - x0_ + 0.2, 0.2, z1_ - z0_ + 0.2))
        slab(c, (-7.5, 9.0, -97.0, -44.5), 0.0, 0.25, "lightroof", None)
        b.tube("steel", (-18.2, 0.0, -84.8), (-18.2, 21.8, -84.8), 0.7, 6)
        b.box("bluetrim", (-17.4, 21.0, -84.8), (1.6, 1.0, 0.05))
    else:
        ruin(c, blk_, 14.0, 60)
        for (x0_, x1_, z0_, z1_) in ((-40.8, -38.2, -97.6, -44.5), (37.9, 40.5, -97.6, -44.5)):
            b.box("concrete_dark", ((x0_ + x1_) / 2, 1.0, (z0_ + z1_) / 2), (x1_ - x0_, 2.0, z1_ - z0_))
    if state == "damaged":
        scorch(c, "-z", blk_, 20.0, 8.0, 3.0)
        scorch(c, "+x", blk_, 40.0, 9.0, 3.0)
        scorch(c, "-z", blk_, 75.0, 12.0, 2.4)
        roof_scorch(c, 15.0, 25.9, 10.0, 3.2)
    return c


def s_promenade(state, lod, seed):
    """A long colonnade x -4.2..4.2, z +-12.8: a glazed back wall x -4.2..-3.6 under a flat roof (x -4.2..0.8, y 5..5.7) on a column row, and a lower thin
    canopy (x 1.7..3.9, y 4) on its own columns."""
    c = shell(state, lod, seed, (0.0, 3.0, 0.0, 4.0), 1.5)
    b = c.b
    if state != "destroyed":
        slab(c, (-4.2, 4.2, -12.8, 12.7), 0.0, 0.2, "lightroof", None)
        b.box("tealpanel", (-3.9, 2.5, 0.0), (0.4, 5.0, 25.4))
        if c.fine:
            for k in range(9):
                b.box("bluetrim", (-3.8, 2.5, -12.6 + k * 3.15), (0.5, 5.0, 0.18))
        slab(c, (-4.2, 0.8, -12.8, 12.7), 5.0, 0.7)
        slab(c, (1.7, 3.9, -12.8, 12.7), 3.6, 0.4)
        zs = [-12.0 + k * 3.0 for k in range(9)]
        columns(c, [(0.0, z) for z in zs], 0.2, 5.0, 0.38)
        columns(c, [(3.4, z) for z in zs], 0.2, 3.6, 0.2)
    else:
        b.box("concrete_dark", (0.0, 0.1, 0.0), (8.2, 0.2, 25.2))
        rubble(c, (-4.0, 3.8, -12.5, 12.5), 2.0, 8)
        for k in range(3):
            b.tube("concrete_dark", (0.0, 0.2, -9.0 + k * 9.0), (1.4, 1.0, -8.4 + k * 9.0), 0.38, 6)
    if state == "damaged":
        for k in (3, 6):                                                    # two columns broken off, a scorched gap in the roof
            pass
        b.box("scorchblack", (-1.8, 5.75, 1.0), (2.6, 0.06, 4.0), None)
        b.box("scorchblack", (-3.85, 2.5, 7.5), (0.1, 3.2, 3.4), None)
        for k in range(3):
            q = V([-1.0 + k * 0.6, 5.7, 1.0 + k])
            b.tube("steel", q, q + V([0.3, 1.2, 0.4]), 0.07, 4)
    return c


def s_quetragon(state, lod, seed):
    """A chevron ring of three convex wings (an outer arc to x -16.6, ends at z +-33) with walls to y 12.5 and a wide hip to a flat 19 top; to its right a paved
    court (x 6..53, z +-14.8) with two long flat canopies (y 10.3, x 17..45, z 6.4..11.8 and -11.8..-6.4) on columns, and lamp posts."""
    c = shell(state, lod, seed, (-8.0, 8.0, 0.0, 8.0), 2.0)
    b = c.b
    north = [(13.4, -33.1), (-2.6, -27.0), (-8.6, -23.0), (-12.6, -15.0), (-16.6, -6.0), (7.4, -5.0), (15.4, -13.0), (15.4, -30.0)]
    south = [(x, -z) for (x, z) in north]
    centre = [(-16.6, -6.0), (7.4, -6.0), (7.4, 6.0), (-16.6, 6.0)]
    pieces = (north, south, centre)
    if state != "destroyed":
        _chevron_ring(c)
        slab(c, (7.4, 53.0, -14.8, 14.8), 0.0, 0.3, "creamwall", None)
        for z0_, z1_ in ((-11.8, -6.4), (6.4, 11.8)):
            slab(c, (17.0, 45.0, z0_, z1_), 9.8, 0.6)
            columns(c, [(x, z) for x in (18.0, 26.0, 34.0, 42.0, 44.2) for z in (z0_ + 0.6, z1_ - 0.6)], 0.0, 9.8, 0.4)
        for z_ in (-10.0, 10.0):
            b.tube("steel", (49.4, 0.0, z_), (49.4, 10.0, z_), 0.16, 5)
            b.box("lightroof", (49.4, 10.1, z_), (0.7, 0.2, 0.7))
        b.box("lightroof", (22.0, 0.6, 0.0), (30.0, 0.6, 3.0)) if False else None
    else:
        for poly in pieces:
            poly_ext(c, "concrete_dark", poly, 0.0, 1.8, top="concrete_dark")
        rubble(c, (-15.0, 13.0, -30.0, -8.0), 6.0, 14)
        rubble(c, (-15.0, 13.0, 8.0, 30.0), 6.0, 14)
        rubble(c, (-15.0, 6.0, -8.0, 8.0), 6.0, 8)
        slab(c, (7.4, 53.0, -14.8, 14.8), 0.0, 0.3, "concrete_dark", None)
    if state == "damaged":
        b.box("scorchblack", (-14.0, 8.0, -3.0), (0.1, 3.4, 3.4), None)
        b.box("scorchblack", (-6.0, 19.5, -22.0), (3.0, 0.06, 2.4), None)
        for k in range(3):
            q = V([-6.0 + k, 19.4, -22.0 + k])
            b.tube("steel", q, q + V([0.4, 1.4, 0.5]), 0.07, 4)
        b.box("scorchblack", (4.0, 9.0, 6.0), (6.0, 0.6, 0.6), None) if False else None
    return c


QO = [(13.4, -33.1), (-2.6, -27.0), (-8.6, -23.0), (-12.6, -15.0), (-16.6, -6.0), (-16.6, 6.0), (-12.6, 15.0), (-8.6, 23.0), (-2.6, 27.0), (13.4, 33.1)]
QI = [(15.4, -30.0), (15.4, -22.0), (15.4, -13.0), (7.4, -5.0), (7.4, -2.0), (7.4, 2.0), (7.4, 5.0), (15.4, 13.0), (15.4, 22.0), (15.4, 30.0)]


def _ring_walls(c, mat, poly, y0, y1):
    """Side quads of a closed, not necessarily convex plan; outward normals from the polygon's winding."""
    pts = np.asarray(poly, float)
    n = len(pts)
    area = 0.5 * sum(pts[k][0] * pts[(k + 1) % n][1] - pts[(k + 1) % n][0] * pts[k][1] for k in range(n))
    for k in range(n):
        a, d = pts[k], pts[(k + 1) % n]
        e = d - a
        L = float(np.hypot(*e)) or 1.0
        nx, nz = (e[1] / L, -e[0] / L) if area > 0 else (-e[1] / L, e[0] / L)
        P = np.array([(a[0], y0, a[1]), (d[0], y0, d[1]), (d[0], y1, d[1]), (a[0], y1, a[1])])
        c.b.add(mat, P, np.array([(nx, 0, nz)] * 4), np.array([(0, y0), (L, y0), (L, y1), (0, y1)]), [(0, 1, 2), (0, 2, 3)])


def _up_quad(c, mat, p0, p1, p2, p3):
    """A roof quad given by four 3D points, normal forced upward."""
    P = np.array([p0, p1, p2, p3], float)
    nn = np.cross(P[1] - P[0], P[3] - P[0])
    nn = nn / (np.linalg.norm(nn) or 1.0)
    if nn[1] < 0:
        nn = -nn
    L = float(np.linalg.norm(P[1] - P[0]))
    H_ = float(np.linalg.norm(P[3] - P[0]))
    c.b.add(mat, P, np.array([nn] * 4), np.array([(0, 0), (L, 0), (L, H_), (0, H_)]), [(0, 1, 2), (0, 2, 3)])


def _chevron_ring(c):
    """One continuous bent roof over the whole ring: ten stations run from the north tip round the apex to the south tip, each pairing an outer-wall point
    with an inner-wall point; the ridge points sit at 38 % and 62 % across each pair, so the flat top turns at every bend with mitred joints and every slope
    quad shares its edges with its neighbours (no separate hips, no seams). Walls y 0..12.5, eaves 12.5, flat top 19."""
    ring = QO + QI[::-1]
    _ring_walls(c, "steinerwhite", ring, 0.0, 12.5)
    ye, yr = 12.5, 19.0
    n = len(QO)
    EL = [np.array([p[0], ye, p[1]]) for p in QO]
    ER = [np.array([p[0], ye, p[1]]) for p in QI]
    RL = [e + (r - e) * 0.38 + np.array([0, yr - ye, 0]) * 0 for e, r in zip(EL, ER)]
    RR = [e + (r - e) * 0.62 for e, r in zip(EL, ER)]
    for lst in (RL, RR):
        for q in lst:
            q[1] = yr
    for i in range(n - 1):
        _up_quad(c, "tealwall", EL[i], EL[i + 1], RL[i + 1], RL[i])          # the outer slope
        _up_quad(c, "tealwall", ER[i], ER[i + 1], RR[i + 1], RR[i])          # the inner slope
        top = np.array([0, 0.3, 0])
        _up_quad(c, "lightroof", RL[i] + top, RL[i + 1] + top, RR[i + 1] + top, RR[i] + top)
        if c.fine:
            f = 0.12
            for E, R in ((EL, RL), (ER, RR)):
                _up_quad(c, "bluetrim", E[i] - np.array([0, 0.05, 0]), E[i + 1] - np.array([0, 0.05, 0]), E[i + 1] + (R[i + 1] - E[i + 1]) * f, E[i] + (R[i] - E[i]) * f)
    for k in (0, n - 1):                                                      # the two tips: a hip across the end of the strip
        _up_quad(c, "tealwall", EL[k], ER[k], RR[k], RL[k])
    for i in range(n - 1):
        _edge_windows(c, QO[i], QO[i + 1], 12.5)
        _edge_windows(c, QI[i], QI[i + 1], 12.5, flip=True)


def _edge_windows(c, a, d, h, flip=False):
    """Two rows of glass quads along an arbitrary wall edge a -> d (x, z), skipping nothing: each at most 70 % of its cell."""
    if c.state == "destroyed":
        return
    a = np.asarray(a, float)
    d = np.asarray(d, float)
    e = d - a
    L = float(np.hypot(*e))
    if L < 4.0:
        return
    t = e / L
    nrm = np.array([t[1], -t[0]])
    # outward = away from the plan's centroid region (x < 0 side of the ring)
    mid = (a + d) / 2
    if np.dot(nrm, mid - np.array([-2.0, 0.0])) < 0:
        nrm = -nrm
    if flip:
        nrm = -nrm
    n3 = V([nrm[0], 0.0, nrm[1]])
    u3 = V([t[0], 0.0, t[1]])
    cols = max(2, int((L - 2.0) / 3.4))
    step = (L - 2.0) / cols
    w = min(1.5, step * 0.7)
    for row in range(2):
        for i in range(cols):
            p = V([a[0], 0.0, a[1]]) + u3 * (1.0 + (i + 0.5) * step) + V([0, 2.2 + row * 4.8 + 1.1, 0]) + n3 * 0.06
            c.b.quad("glassblue", p, u3, V([0, 1.0, 0]), w, 2.3, (0, 1, 1, 0), normal=tuple(n3))
            if c.fine:
                c.b.quad("bluetrim", p + V([0, -1.3, 0]) + n3 * 0.02, u3, V([0, 1.0, 0]), w + 0.3, 0.18, (0, 1, 1, 0), normal=tuple(n3))


def scaled(fn, sc, shift=(0.0, 0.0, 0.0)):
    """The originals' glb roots carry a scale in game (s_gov1 0.6436, s_govresidence 0.2154, s_quetragon 0.5348, s_adminquarter y 0.7047); the v3 models have no
    root transform, so the finished mesh is scaled (and shifted by the node's translation: s_gov2 sits +3.5, -2.04 off its origin) to what the player sees. Designed at the glb's mesh size, scaled after (collapse and rubble reset the
    builder's own transform, so it cannot be done while building)."""
    S = np.array(sc, float)
    T = np.array(shift, float)

    def build(state, lod, seed):
        c = fn(state, lod, seed)
        for surf in c.b.s.values():
            surf["P"] = [P * S + T for P in surf["P"]]
            surf["N"] = [(N / S) / np.linalg.norm(N / S, axis=1, keepdims=True) for N in surf["N"]]
        return c
    return build


MEMBERS = {
    "s_main": (s_main, "Steiner main hall: tall glazed-lantern slab, front block, portico and wings"),
    "s_main_leftwing": (s_main_leftwing, "Steiner main hall left wing: hip-roofed tower block and a long low annex"),
    "s_main_rightwing": (s_main_rightwing, "Steiner main hall right wing: mansard block with a low front annex"),
    "s_main_stairs": (s_main_stairs, "Steiner main hall stairs: stepped plaza descending to a long flight"),
    "s_admin_entry": (s_admin_entry, "Steiner admin entry hall: cross plan with a skylight"),
    "s_admin_wing": (s_admin_wing, "Steiner admin wing: long low block with a glazed clerestory"),
    "s_admin_core": (scaled(s_admin_core, [1.0, 1.0, 1.0], (0.31534, 0.0, 0.09164)), "Steiner admin core: stepped block with rooftop pavilions"),
    "s_adminquarter": (scaled(s_adminquarter, [1.0, 0.7047, 1.0]), "Steiner admin quarter: pentagon plan under a sloped teal canopy roof"),
    "s_gov1": (scaled(s_gov1, [0.6436] * 3), "Steiner government hall 1: palace with stepped tower, a long wing and a canopied plaza"),
    "s_gov2": (scaled(s_gov2, [1.0, 1.0, 1.0], (3.49652, 0.0, -2.04046)), "Steiner government hall 2: hipped block, front wing, forecourt canopy"),
    "s_govresidence": (scaled(s_govresidence, [0.2154] * 3), "Steiner governor's residence: huge hipped palace and walled forecourt"),
    "s_promenade": (s_promenade, "Steiner promenade: long colonnade with a glazed back wall"),
    "s_quetragon": (scaled(s_quetragon, [0.5348] * 3), "Steiner Quetragon: chevron ring building with a paved court and canopies"),
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
