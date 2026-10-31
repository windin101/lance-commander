#!/usr/bin/env python3
"""v3 military buildings (LANCE-39): headquarters, barracks, gate/sensor/spotlight controls, flags, towers, checkpoints, ammo dumps, tents.
Footprints and heights are the Shared Source originals' (game/tools/orig_top.gd, orig_bounds.gd); built on the industrial + city kits
(bld_industry.py, bld_city.py): dark detailed roofs, windows and doors as separate exact rectangles (never cut holes), faction palettes:
Steiner s_ pale white-grey with teal roofs, Liao l_ green camo vaults, Davion d_ tan. Style guide: docs/art/STYLE-GUIDE.md section 10.

    python3 -I tools/art/v3/bld_military.py <app>|pilot|all
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bld_hangars as H  # noqa: E402
import bld_industry as I  # noqa: E402
import bld_city as C  # noqa: E402
from bld_city import blk2, _wins, rubble, heli_ring  # noqa: E402
from bld_industry import (Ctx, V, TAU, axis_angle, shell, blk, roof2, fpanel, louvre, door, band, barrel_roof, prism_roof, collapse, ROOT)  # noqa: E402


def frustum(c, mat, cx, cz, hw0, hd0, y0, hw1, hd1, y1, open_top=True, drop=None):
    """An axis-aligned square/rect frustum from (hw0, hd0) half-sizes at y0 to (hw1, hd1) at y1: four flat sloped quads (never a revolve, which comes out
    rotated 45 degrees). drop: index 0..3 of a side to omit (a broken tower)."""
    b = c.b
    corners0 = [(cx - hw0, cz - hd0), (cx + hw0, cz - hd0), (cx + hw0, cz + hd0), (cx - hw0, cz + hd0)]
    corners1 = [(cx - hw1, cz - hd1), (cx + hw1, cz - hd1), (cx + hw1, cz + hd1), (cx - hw1, cz + hd1)]
    for k in range(4):
        if drop == k:
            continue
        a0, a1 = corners0[k], corners0[(k + 1) % 4]
        b0, b1 = corners1[k], corners1[(k + 1) % 4]
        P = np.array([(a0[0], y0, a0[1]), (a1[0], y0, a1[1]), (b1[0], y1, b1[1]), (b0[0], y1, b0[1])])
        e1, e2 = P[1] - P[0], P[3] - P[0]
        n = np.cross(e1, e2)
        n = n / (np.linalg.norm(n) or 1.0)
        mid = P.mean(0) - np.array([cx, (y0 + y1) / 2, cz])
        if np.dot(n, mid) < 0:
            n = -n
        idx = [(0, 1, 2), (0, 2, 3)] if np.dot(np.cross(P[1] - P[0], P[2] - P[0]), n) > 0 else [(0, 2, 1), (0, 3, 2)]
        U = np.array([(0, y0), (np.linalg.norm(e1), y0), (np.linalg.norm(e1), y1), (0, y1)])
        b.add(mat, P, np.array([n] * 4), U, idx)
    if not open_top:
        b.box(mat, (cx, y1 - 0.05, cz), (2 * hw1, 0.1, 2 * hd1))


def face_panel(c, mat, cx, cz, hw0, y0, hw1, y1, k, u0, u1, v0, v1, off=0.04, ribs=0, rib_mat=None):
    """A flat panel seated on face k (0..3) of the square frustum (hw0 at y0 -> hw1 at y1): corners by bilinear interpolation of the face (u along
    the face, v up it, both 0..1), pushed `off` outward. ribs: that many thin bars across it."""
    b = c.b
    c0 = [(cx - hw0, cz - hw0), (cx + hw0, cz - hw0), (cx + hw0, cz + hw0), (cx - hw0, cz + hw0)]
    c1 = [(cx - hw1, cz - hw1), (cx + hw1, cz - hw1), (cx + hw1, cz + hw1), (cx - hw1, cz + hw1)]
    a0, a1 = c0[k], c0[(k + 1) % 4]
    d0, d1 = c1[k], c1[(k + 1) % 4]
    def pt(u, v):
        x0_ = a0[0] + (a1[0] - a0[0]) * u; z0_ = a0[1] + (a1[1] - a0[1]) * u
        x1_ = d0[0] + (d1[0] - d0[0]) * u; z1_ = d0[1] + (d1[1] - d0[1]) * u
        return np.array([x0_ + (x1_ - x0_) * v, y0 + (y1 - y0) * v, z0_ + (z1_ - z0_) * v])
    P = np.array([pt(u0, v0), pt(u1, v0), pt(u1, v1), pt(u0, v1)])
    n = np.cross(P[1] - P[0], P[3] - P[0]); n = n / (np.linalg.norm(n) or 1.0)
    out = P.mean(0) - np.array([cx, P[:, 1].mean(), cz])
    if np.dot(n, out) < 0:
        n = -n
    P = P + n * off
    idx = [(0, 1, 2), (0, 2, 3)] if np.dot(np.cross(P[1] - P[0], P[2] - P[0]), n) > 0 else [(0, 2, 1), (0, 3, 2)]
    U = np.array([(0, 0), (1, 0), (1, 1), (0, 1)], float) * 2.0
    b.add(mat, P, np.array([n] * 4), U, idx)
    for r in range(ribs if c.fine else 0):
        v = v0 + (v1 - v0) * (r + 1) / (ribs + 1)
        Q = np.array([pt(u0, v - 0.006), pt(u1, v - 0.006), pt(u1, v + 0.006), pt(u0, v + 0.006)]) + n * (off + 0.03)
        idx2 = [(0, 1, 2), (0, 2, 3)] if np.dot(np.cross(Q[1] - Q[0], Q[2] - Q[0]), n) > 0 else [(0, 2, 1), (0, 3, 2)]
        b.add(rib_mat or "machgrey", Q, np.array([n] * 4), U, idx2)


def wall_of(fac, kind="body"):
    return {"s": ("creamwall", "flat"), "l": ("camogreen", "flat"), "d": ("tanwall", "flat")}[fac]


def ribbon(c, key, box, v0, h, y0=0.0, u0=0.5, u1=None, n=6, gap=0.3, mat="glassblue", trim=None):
    """A long glazed strip: n separate exact-rectangle glass panes in a row (gaps show the wall as mullions), optional pale/blue trim bars above and below."""
    if c.state == "destroyed":
        return
    L = I._face(key, *box)[3]
    u1 = L - 0.5 if u1 is None else u1
    w = (u1 - u0 - gap * (n - 1)) / n
    for k in range(n):
        fpanel(c, mat, key, box, u0 + k * (w + gap), v0, w, h, y0, 0.06)
    if trim and c.fine:
        fpanel(c, trim, key, box, u0 - 0.1, v0 + h, u1 - u0 + 0.2, 0.22, y0, 0.07)
        fpanel(c, trim, key, box, u0 - 0.1, v0 - 0.22, u1 - u0 + 0.2, 0.22, y0, 0.07)


def scorch(c, key, box, uc, vc, r, y0=0.0, streak=True):
    """A dark scorched hole in a wall: a jagged black polygon with bare beams across it and soot running up from it. (Replaces the rust-coloured breach.)"""
    if c.state != "damaged":
        return
    b = c.b
    (px, pz), ud, n, L = I._face(key, *box)
    ud, n = V(ud, float), V(n, float)
    rng = c.rng
    ctr = V([px, y0 + vc, pz]) + ud * uc + n * 0.07
    pts = []
    for k in range(10):
        a = TAU * k / 10
        rr = r * (0.7 + 0.5 * rng.random())
        pts.append(ctr + ud * (math.cos(a) * rr) + V([0, math.sin(a) * rr * 1.1, 0]))
    P = [ctr] + pts
    I_ = [(0, 1 + k, 1 + (k + 1) % 10) for k in range(10)]
    b.add("scorchblack", np.array(P), np.array([tuple(n)] * len(P)), np.array([(p_[0], p_[1]) for p_ in P]), I_)
    for k in range(3):
        q0 = ctr + ud * rng.uniform(-r * 0.8, r * 0.8) + V([0, -r * 0.8, 0]) + n * 0.05
        q1 = ctr + ud * rng.uniform(-r * 0.8, r * 0.8) + V([0, r * 0.8, 0]) + n * 0.05
        b.tube("steel", q0, q1, 0.07, 4)
    if streak and c.fine:
        for k in range(2):
            c.decal_wall("streak_a" if k == 0 else "streak_b", V([px, 0, pz]) + ud * (uc + (k - 0.5) * r * 0.8) , ud, r * 1.3, vc + r * 0.4, vc + r * 3.2, tuple(n), off=0.05)


def roof_scorch(c, cx, y, cz, r, seed=0):
    """A scorched roof hole with bent trusses."""
    if c.state != "damaged":
        return
    b = c.b
    rng = c.rng
    pts = []
    for k in range(9):
        a = TAU * k / 9
        rr = r * (0.7 + 0.5 * rng.random())
        pts.append((cx + math.cos(a) * rr, y, cz + math.sin(a) * rr))
    P = [(cx, y, cz)] + pts
    b.add("scorchblack", np.array(P), np.array([(0, 1, 0)] * len(P)), np.array([(p_[0], p_[2]) for p_ in P]), [(0, 1 + k, 1 + (k + 1) % 9) for k in range(9)])
    for k in range(3):
        a0 = V([cx + rng.uniform(-r, r), y + 0.1, cz + rng.uniform(-r, r)])
        b.tube("steel", a0, a0 + V([rng.uniform(-1.4, 1.4), rng.uniform(0.6, 1.6), rng.uniform(-1.4, 1.4)]), 0.07, 4)


def helipad(c, cx, cz, y, r=3.2, ring="bandorange"):
    """A flat painted helipad on the roof: a pale disc 4 cm proud, an orange ring, a blue-grey H and a small orange mark. Nothing rises above the roof, so it
    cannot read as a dome."""
    if c.state == "destroyed":
        return
    b = c.b
    seg = 28 if c.fine else 12
    b.disc("lightroof", (cx, y + 0.04, cz), r + 0.2, (0, 1, 0), seg)
    b.disc(ring, (cx, y + 0.06, cz), r, (0, 1, 0), seg, r_in=r - 0.4)
    for dx in (-0.9, 0.9):
        b.box("bluetrim", (cx + dx, y + 0.07, cz), (0.35, 0.02, 2.6))
    b.box("bluetrim", (cx, y + 0.07, cz), (1.8, 0.02, 0.35))
    b.disc(ring, (cx + 1.6, y + 0.08, cz - 1.6), 0.5, (0, 1, 0), 8)


def vault_glazed(c, x0, x1, z0, z1, y, rise, bays=5, seg=8, rib="creamwall", glass="glasslight", beds=True, end_glass="creamwall"):
    """A greenhouse vault (ridge along z): pale cream ribs at every bay boundary, high-albedo light-tinted glass strips between them, green planting beds on
    the floor under the glass, cream end walls. A damaged state blows one bay out; the destroyed state has no vault."""
    if c.state == "destroyed":
        return
    b = c.b
    cx = (x0 + x1) / 2
    W = x1 - x0
    ts = np.linspace(0, math.pi, seg + 1)
    xs = cx - (W / 2) * np.cos(ts)
    ys = y + rise * np.sin(ts)
    zb = [z0 + (z1 - z0) * k / bays for k in range(bays + 1)]
    gap = 0.12
    for k in range(bays):
        za, zc = zb[k] + gap, zb[k + 1] - gap
        if c.state == "damaged" and k == 2:
            continue
        for j in range(seg):
            P = [(xs[j], ys[j], za), (xs[j + 1], ys[j + 1], za), (xs[j + 1], ys[j + 1], zc), (xs[j], ys[j], zc)]
            am = (ts[j] + ts[j + 1]) / 2
            nx, ny = -math.cos(am) * rise, math.sin(am) * (W / 2)
            nn = math.hypot(nx, ny) or 1.0
            nrm = (nx / nn, ny / nn, 0.0)
            b.add(glass, np.array(P), np.array([nrm] * 4), np.array([(xs[j], za), (xs[j + 1], za), (xs[j + 1], zc), (xs[j], zc)]), [(0, 1, 2), (0, 2, 3)])
    for z in zb:
        pts = [V([xs[j], ys[j] + 0.03, z]) for j in range(seg + 1)]
        for j in range(seg):
            b.tube(rib, pts[j], pts[j + 1], 0.2, 5)
    for j in range(1, seg):                                              # a ridge purlin and two eave purlins
        pass
    b.tube(rib, V([cx, y + rise + 0.05, z0]), V([cx, y + rise + 0.05, z1]), 0.2, 5)
    if beds:
        for k in range(3):                                               # planting beds under the glass, visible through it
            xb = x0 + W * (0.2 + 0.3 * k)
            b.box("bedgreen", (xb, y + 0.35, (z0 + z1) / 2), (W * 0.16, 0.7, (z1 - z0) - 1.0))
    for z, sg in ((z0, -1), (z1, 1)):
        Pe = [(x0, y, z)] + [(xs[j], ys[j], z) for j in range(seg + 1)] + [(x1, y, z)]
        Ne = [(0, 0, sg)] * len(Pe)
        Ie = [(0, j + 1, j + 2) if sg > 0 else (0, j + 2, j + 1) for j in range(seg)]
        b.add(end_glass if sg > 0 else "creamwall", np.array(Pe), np.array(Ne), np.array([(q[0], q[1]) for q in Pe]), Ie)


def tower_shaft(c, cx, cz, h0, h1, y0, y1, mat="creamwall", band="bluetrim"):
    """A slender tapering square shaft (flat frustum, half-widths h0 -> h1) with blue corner bands and rings."""
    st = c.state
    if st == "destroyed":
        frustum(c, mat, cx, cz, h0, h0, y0, h0 * 0.93, h0 * 0.93, y0 + 2.2, drop=2)
        c.b.box(mat, V([cx + 0.8, 1.0, cz + 2.8]), (h1 * 1.5, h1 * 1.5, 6.0), axis_angle(V([0, 1.0, 0]), 0.5) @ axis_angle(V([0, 0, 1.0]), 0.12))
        return
    top = y1 if st == "intact" else y0 + (y1 - y0) * 0.72
    ht = h0 + (h1 - h0) * (top - y0) / (y1 - y0)
    frustum(c, mat, cx, cz, h0, h0, y0, ht, ht, top)
    if c.fine:
        for sx in (-1, 1):
            for sz in (-1, 1):
                c.b.tube("creamwall", V([cx + sx * h0, y0, cz + sz * h0]), V([cx + sx * ht, top, cz + sz * ht]), 0.22, 4)
        for kk in range(1):
            yb = y0 + (top - y0) * 0.5
            hb = h0 + (h1 - h0) * (yb - y0) / (y1 - y0)
            frustum(c, band, cx, cz, hb + 0.04, hb + 0.04, yb, hb + 0.04, hb + 0.04, yb + 0.3)


def lookouttower(state, lod, seed):
    """Built to the original's measured slices (game/tools/orig_parts.gd): footprint 8.0 x 7.3 at the ground, 6.3 x 5.8 at y 3, a shaft to 4.7 x 4.3 at
    y 12, a cab y 12..14, a roof slab 6.0 x 5.5 at y 14..14.9, a round dish/fixture on top (no helipad)."""
    c = shell(state, lod, seed, (0.0, 8.0, 0.0, 3.0), 2.0)
    b = c.b
    cx, cz = -0.1, 0.25
    box = (-4.1, 3.9, -3.4, 3.9)
    if state != "destroyed":
        frustum(c, "tealwall", cx, cz, 4.0, 3.65, 0.0, 3.3, 3.0, 3.0)                              # the chamfered base: teal-grey, 8.0 x 7.3 -> 6.6 x 6.0 at y 3
        fpanel(c, "grate", "+z", (cx - 3.6, cx + 3.3, cz - 3.3, cz + 3.3), 2.9, 0.0, 1.2, 2.0, 0.0, 0.28)
        b.box("bluetrim", (cx, 2.85, cz + 3.0), (6.8, 0.2, 0.1)) if c.fine else None
    else:
        frustum(c, "tealwall", cx, cz, 4.0, 3.65, 0.0, 3.6, 3.3, 1.6, drop=3)
    tower_shaft(c, cx, cz, 2.95, 2.3, 3.0, 12.0)
    if state != "destroyed":
        top_ = 12.0 if state == "intact" else 3.0 + 9.0 * 0.72
        ht_ = 2.95 + (2.3 - 2.95) * (top_ - 3.0) / 9.0
        for k in range(4):                                                  # the recessed teal-green ribbed centre panel on every face, seated in the wall
            face_panel(c, "tealpanel", cx, cz, 2.95, 3.0, ht_, top_, k, 0.3, 0.7, 0.08, 0.92, 0.04, ribs=7, rib_mat="machgrey")
    if state == "destroyed":
        rubble(c, box, 2.6, 7)
        return c
    y = 12.0 if state == "intact" else 9.4
    cb = (cx - 2.6, cx + 2.6, cz - 2.4, cz + 2.4)
    b.box("tealwall", (cx, y + 1.0, cz), (5.2, 2.0, 4.8))
    for key in ("+z", "-z", "+x", "-x"):
        ribbon(c, key, cb, 0.45, 1.1, y, 0.35, None, 3, 0.2)
    b.box("lightroof", (cx, y + 2.3, cz), (6.0, 0.6, 5.5))                                       # the roof slab, y 14..14.9 in the original
    b.box("bluetrim", (cx, y + 2.05, cz), (6.1, 0.12, 5.6)) if c.fine else None
    b.revolve("machgrey", [(0.5, y + 2.6), (0.5, y + 3.0), (0.2, y + 3.2)], 10 if c.fine else 6, cx=cx + 0.6, cz=cz - 0.3, uref=1.0)   # the dish pedestal
    b.revolve("lightroof", [(1.2, y + 3.0), (0.9, y + 2.9), (0.0, y + 2.75)], 14 if c.fine else 6, cx=cx + 0.6, cz=cz - 0.3, uref=1.0)   # a shallow dish
    if state == "damaged":
        scorch(c, "+z", cb, 2.6, 1.0, 1.0, y)
        b.box("scorchblack", (cx - 1.0, y + 2.65, cz + 0.8), (2.4, 0.15, 2.0), axis_angle(V([0, 1.0, 0]), 0.5) @ axis_angle(V([0, 0, 1.0]), 0.15))
        for k in range(3):
            q = V([cx - 1.8 + k * 1.1, y + 2.6, cz + 0.2])
            b.tube("steel", q, q + V([0.4, 1.3, 0.5]), 0.06, 4)
    return c


def s_hq(state, lod, seed):
    c = shell(state, lod, seed, (-2.0, 6.0, 3.0, 4.0), 2.0)
    wall = wall_of("s")
    rk = dict(mat="lightroof", trim="bluetrim")
    tw = (-2.4, 10.1, -20.1, -9.8)                                   # the control tower block: cream, big glazed bays, raised helipad on the roof
    blk2(c, *tw[:2], *tw[2:], 16.5, wall, roof="flat", ac=1, vents=0, hatch=0, seed=seed, **rk)
    wing = (-9.0, 3.6, -9.8, 10.8)                                   # the long main wing, two storeys, ribbon glazing
    blk2(c, *wing[:2], *wing[2:], 8.0, wall, roof="flat", ac=2, vents=1, lights=0, hatch=1, seed=seed + 2, **rk)
    spine = (-6.0, -1.2, -9.0, 8.0)                                   # the raised glazed lantern along the wing
    blk2(c, *spine[:2], *spine[2:], 2.2, wall, y0=8.0, roof="flat", ac=1, vents=0, lights=0, hatch=0, seed=seed + 3, parapet=0.3, **rk)
    low = (3.6, 10.1, 0.0, 10.8)                                     # the low annex with long glazed strips
    blk2(c, *low[:2], *low[2:], 4.6, wall, roof="flat", ac=1, vents=1, lights=0, hatch=1, seed=seed + 4, **rk)
    if state != "destroyed":
        for key, bx, hh, ns in (("+z", tw, 16.5, 3), ("-z", tw, 16.5, 3), ("+x", tw, 16.5, 4), ("-x", tw, 16.5, 4)):
            for fl in range(3):                                         # tower: three glazed bands with blue trim, as the original's wide bays
                ribbon(c, key, bx, 2.6 + fl * 4.6, 2.6, 0.0, 1.2, None, ns, 0.5, trim="bluetrim")
        for key, bx in (("-x", wing), ("+x", wing)):
            ribbon(c, key, bx, 1.2, 2.4, 0.0, 1.5, None, 7, 0.3, trim="bluetrim")
            ribbon(c, key, bx, 4.6, 2.4, 0.0, 1.5, None, 7, 0.3, trim="bluetrim")
        ribbon(c, "+z", wing, 1.2, 2.4, 0.0, 1.0, None, 4, 0.4, trim="bluetrim")
        for key in ("+x", "+z"):
            ribbon(c, key, low, 1.1, 2.0, 0.0, 1.0, None, 5, 0.3, trim="bluetrim")
        for key in ("-x", "+x"):                                        # lantern clerestory
            ribbon(c, key, spine, 0.4, 1.4, 8.0, 0.8, None, 6, 0.3)
        door(c, "+z", wing, 4.0, 1.8, 2.8)
        helipad(c, 3.9, -15.0, 16.95, 3.4)
        band(c, "+z", wing, 7.0, 0.35, "bluetrim")
    if state == "damaged":
        scorch(c, "+x", tw, 5.2, 9.0, 2.0)
        roof_scorch(c, 2.0, 16.9, -13.0, 1.8)
        scorch(c, "+z", wing, 6.0, 4.5, 1.6)
    return c


def l_gatecontrol(state, lod, seed):
    """Built to the measured slices (orig_parts.gd): hall x -11.2..-0.1, z -12.6..0.4, green planting on a pale-ribbed roof, a stepped glazed front; a chunky
    white 8.4 x 8.4 m tower block (x 2.1..10.5, z -12.3..-3.9) with banded window rows, a rooftop dish and two antenna masts; a low planted terrace in front."""
    c = shell(state, lod, seed, (3.0, 8.0, -7.0, 3.0), 2.0)
    b = c.b
    vb = (-11.2, -0.1, -12.6, 0.4)
    blk(c, *vb[:2], *vb[2:], 2.6, ("creamwall", "flat"), holes={}, main=False, roof=None)
    vault_glazed(c, vb[0], vb[1], vb[2], vb[3], 2.6, 4.4, 6, glass="planting", end_glass="lightroof")
    if state != "destroyed":
        step = (-9.6, -1.7, 0.4, 1.7)                                      # the stepped front: a lower glazed plinth in front of the hall end wall
        b.box("creamwall", (-5.65, 1.2, 1.05), (7.9, 2.4, 1.3))
        ribbon(c, "+z", (-9.6, -1.7, -0.9, 1.7), 0.4, 1.5, 0.0, 0.4, None, 5, 0.25, trim="bluetrim")
        for xk in (-8.2, -5.6, -3.0):                                       # window bays on the hall end wall above the plinth
            fpanel(c, "glassblue", "+z", vb, xk + 11.2 - 0.9, 3.0, 1.8, 1.7, 0.0, 0.06)
        door(c, "+z", step, 3.4, 1.3, 2.0)
    tw = (2.1, 10.5, -12.3, -3.9)                                          # the chunky white control tower block
    blk2(c, *tw[:2], *tw[2:], 11.6, ("lightroof", "flat"), roof="flat", ac=0, vents=0, hatch=0, seed=seed, mat="lightroof", trim="bluetrim")
    if state != "destroyed":
        for key in ("+z", "-z", "+x", "-x"):
            for fl in range(3):                                              # banded window rows
                ribbon(c, key, tw, 2.0 + fl * 3.0, 1.5, 0.0, 0.7, None, 4, 0.35, trim="bluetrim")
        cxx, czz = 6.3, -8.1
        top = 29.3 if state == "intact" else 21.0
        for (ax_, az_) in ((3.5, -4.9), (5.2, -4.9)):                        # twin antenna masts
            b.tube("steel", (ax_, 12.2, az_), (ax_, top, az_), 0.12, 6)
        b.revolve("machgrey", [(0.5, 12.2), (0.5, 12.8), (0.2, 13.0)], 10 if c.fine else 6, cx=cxx, cz=czz, uref=1.0)
        b.revolve("lightroof", [(1.1, 12.9), (0.8, 12.8), (0.0, 12.65)], 14 if c.fine else 6, cx=cxx, cz=czz, uref=1.0)
    else:
        rubble(c, tw, 3.0, 8)
    te = (2.1, 12.4, -3.9, 1.7)                                            # the low planted terrace in front of the tower
    blk(c, *te[:2], *te[2:], 2.4, ("creamwall", "flat"), holes={}, roof=None)
    if state != "destroyed":
        b.box("planting", ((te[0] + te[1]) / 2, 2.5, (te[2] + te[3]) / 2), (te[1] - te[0] - 0.6, 0.3, te[3] - te[2] - 0.6))
        for k in range(5):
            b.box("bedgreen", (te[0] + 1.6 + k * 2.0, 2.8, (te[2] + te[3]) / 2), (1.0, 0.5, te[3] - te[2] - 1.2))
        ribbon(c, "+z", te, 0.5, 1.3, 0.0, 0.5, None, 4, 0.3, trim="bluetrim")
    if state == "damaged":
        scorch(c, "+z", tw, 3.0, 5.0, 1.5)
        roof_scorch(c, 6.3, 11.9, -8.1, 1.8)
    return c


PILOT = {
    "s_hq": (s_hq, "Steiner HQ: control tower with helipad, two-storey main wing, low annex"),
    "l_gatecontrol": (l_gatecontrol, "Liao gate control: camo vault block, glazed control tower with antennas"),
    "lookouttower": (lookouttower, "lookout tower: bunker base, tapering shaft, glazed cab, helipad roof"),
}
H.MEMBERS.update(PILOT)
ALL = dict(PILOT)

# ======================================================================================= group A: HQs and barracks
def pagoda(c, cx, cz, base, h, tiers=3, wall="stonewall", roof="tanroof", y0=0.0):
    """A tiered pagoda: each storey a narrower stone box with red-framed windows, each topped by a flared three-step tan roof that overhangs the storey
    below it (the roof of tier t is wider than the storey of tier t and than the storey above), and a finial."""
    b = c.b
    if c.state == "destroyed":
        b.box(wall, (cx, y0 + 1.2, cz), (base, 2.4, base))
        return
    th = (h - 1.2) / tiers
    for t in range(tiers):
        w = base * (1.0 - 0.2 * t)
        y = y0 + t * th
        b.box(wall, (cx, y + th * 0.4, cz), (w, th * 0.8, w))
        if c.fine:
            for sx in (-1, 1):
                b.box("redframe", (cx + sx * (w / 2 + 0.03), y + th * 0.42, cz), (0.1, th * 0.42, w * 0.62))
                b.box("wglass", (cx + sx * (w / 2 + 0.08), y + th * 0.42, cz), (0.06, th * 0.3, w * 0.5))
                b.box("redframe", (cx, y + th * 0.42, cz + sx * (w / 2 + 0.03)), (w * 0.62, th * 0.42, 0.1))
        yr = y + th * 0.82
        b.box(roof, (cx, yr, cz), (w + 2.8, 0.3, w + 2.8))
        b.box(roof, (cx, yr + 0.3, cz), (w + 1.7, 0.3, w + 1.7))
        b.box(roof, (cx, yr + 0.6, cz), (w + 0.7, 0.3, w + 0.7))
    b.tube("machgrey", V([cx, y0 + h - 1.4, cz]), V([cx, y0 + h, cz]), 0.14, 5)


def octa_tower(c, cx, cz, r, h, y0=0.0, mat="lightroof"):
    """A faceted (octagonal) control tower from two square boxes (0 and 45 degrees; their union is a regular octagon of apothem r): a shaft, a band of dark
    windows near the top, a wider cap, grey bands."""
    b = c.b
    def octo(rr, y, hh, m):                        # a regular octagon of apothem rr: four strips (2rr x 0.83rr) rotated 0, 45, 90, 135 degrees
        for k in range(4):
            b.box(m, (cx, y + hh / 2, cz), (2 * rr, hh, 0.8284 * rr), axis_angle(V([0, 1.0, 0]), k * math.pi / 4))
    if c.state == "destroyed":
        octo(r, y0, 2.4, mat)
        return
    top = h if c.state == "intact" else h * 0.78
    octo(r, y0, top * 0.8, mat)
    octo(r * 1.1, y0 + top * 0.8, top * 0.2, mat)
    if c.fine:
        octo(r * 1.115, y0 + top * 0.84, top * 0.1, "glassblue")                       # the band of windows near the top
        for k in range(2):
            octo(r * 1.02, y0 + top * (0.22 + 0.22 * k), 0.45, "machgrey")


def l_hq(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 6.0, 0.0, 4.0), 2.0)
    b = c.b
    hall = (-10.0, 10.7, -9.0, 9.6)                                          # a cream hall under TWO planted barrel vaults with a flat channel between them
    blk(c, *hall[:2], *hall[2:], 3.6, ("creamwall", "flat"), holes={}, main=True, roof=None)
    if state != "destroyed":
        va = (-10.0, -2.0, -9.0, 9.6)
        vb = (2.7, 10.7, -9.0, 9.6)
        for vx in (va, vb):
            vault_glazed(c, vx[0], vx[1], vx[2], vx[3], 3.6, 4.6, 4, seg=8, glass="planting", beds=False, end_glass="creamwall")
        b.box("lightroof", (0.35, 4.0, 0.3), (4.7, 0.4, 18.6))                                  # the flat channel: pale deck with two grey roof hatches
        for k in range(2):
            b.box("machgrey", (0.35, 4.3, -4.0 + k * 8.4), (3.2, 0.25, 3.6))
        for k in range(5):
            b.box("lightroof", (0.35, 4.0, -9.0 + k * 4.65), (21.0, 0.3, 0.5)) if False else None
        ribbon(c, "+z", hall, 0.6, 1.8, 0.0, 1.0, None, 7, 0.4, trim="lightroof")
        ribbon(c, "-x", hall, 0.6, 1.8, 0.0, 1.5, None, 6, 0.4, trim="lightroof")
        door(c, "+z", hall, 9.0, 1.8, 2.8)
    octa_tower(c, 0.0, -14.8, 5.6, 17.7, mat="steinerwhite")
    if state != "destroyed":
        helipad(c, 0.0, -14.8, 17.95 + 0.3 if False else 18.05, 4.2, ring="bandgreen")
    if state == "damaged":
        scorch(c, "+z", hall, 12.0, 2.0, 1.6)
        roof_scorch(c, 0.0, 18.1, -14.8, 1.8)
    else:
        pass
    if state == "destroyed":
        rubble(c, hall, 3.6, 10)
    return c


def d_hq(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 6.0, 0.0, 4.0), 2.0)
    b = c.b
    wall = ("lightroof", "flat")
    t1 = (-9.7, 9.7, -15.9, -4.0)                                          # the white stepped tower block: lower tier, upper tier, helipad
    blk2(c, *t1[:2], *t1[2:], 8.6, wall, roof="flat", ac=0, vents=0, hatch=0, seed=seed, mat="lightroof", trim="lightroof")
    t2 = (-7.6, 7.6, -14.5, -6.0)
    blk2(c, *t2[:2], *t2[2:], 3.6, wall, y0=8.6, roof="flat", ac=0, vents=0, hatch=0, seed=seed + 1, mat="lightroof", trim="lightroof")
    bays = [((-9.7, 9.7, -4.0, 2.2), 8.0), ((-9.7, 9.7, 2.2, 8.6), 6.4), ((-9.7, 9.7, 8.6, 15.9), 4.8)]   # three bays with sloped, ribbed, yellow-glazed roofs in white frames
    for sb, h in bays:
        blk(c, *sb[:2], *sb[2:], h, wall, holes={}, roof=None)
        if state != "destroyed":
            zl, zh = sb[2], sb[3]
            rise = 1.8
            ang = math.atan2(rise, zh - zl)
            L = math.hypot(zh - zl, rise)
            ctrz, cty = (zl + zh) / 2, h + rise / 2
            b.box("tanroof", (0.0, cty + 0.15, ctrz), (sb[1] - sb[0] - 0.8, 0.22, L - 0.2), axis_angle(V([1.0, 0, 0]), ang))
            for k in range(7 if c.fine else 3):                                  # white rib frames across the glazing
                zk = zl + (zh - zl) * (k + 0.5) / (7 if c.fine else 3)
                yk = h + rise * (1 - (k + 0.5) / (7 if c.fine else 3)) + 0.26
                b.box("lightroof", (0.0, yk, zk), (sb[1] - sb[0] - 0.4, 0.2, 0.2))
            for sx in (-1, 1):
                b.box("lightroof", (sx * (sb[1] - 0.2), cty + 0.2, ctrz), (0.25, 0.3, L), axis_angle(V([1.0, 0, 0]), ang))
            for zz, hh2 in ((zl, h + rise), (zh, h)):                            # white frame walls between the bays so each reads as its own sloped roof
                b.box("lightroof", (0.0, h + hh2 / 2 - h / 2 + 0.0, zz), (sb[1] - sb[0], max(hh2 - h, 0.4) + 0.6, 0.45)) if False else b.box("lightroof", (0.0, h + (hh2 - h) / 2 + 0.2, zz), (sb[1] - sb[0], (hh2 - h) + 0.8, 0.5))
            ribbon(c, "-x", sb, h - 3.0, 1.4, 0.0, 0.6, None, 3, 0.4, mat="wglass")
            ribbon(c, "+x", sb, h - 3.0, 1.4, 0.0, 0.6, None, 3, 0.4, mat="wglass")
    if state != "destroyed":
        for key in ("+x", "-x", "-z"):
            ribbon(c, key, t1, 3.0, 1.6, 0.0, 1.0, None, 5, 0.5, mat="wglass")
        for key in ("+x", "-x"):
            ribbon(c, key, t2, 9.6 - 8.6 + 0.6, 1.4, 8.6, 1.0, None, 4, 0.5, mat="wglass")
        helipad(c, 0.0, -10.2, 12.25, 3.3, ring="bandorange")
        for ax_, az_ in ((4.0, -8.0), (8.0, -6.0)):
            b.tube("steel", (ax_, 12.3, az_), (ax_, 26.3 if state == "intact" else 19.0, az_), 0.1, 5)
        door(c, "+z", bays[2][0], 8.0, 2.0, 3.0)
    else:
        rubble(c, t1, 8.6, 10)
    if state == "damaged":
        scorch(c, "+z", bays[2][0], 4.0, 2.4, 1.5)
        scorch(c, "-x", t1, 6.0, 5.0, 1.8)
        roof_scorch(c, 0.0, 12.3, -10.2, 1.8)
    return c


def s_barracks(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 3.0, 0.0, 3.0), 1.5)
    b = c.b
    box = (-9.5, 9.6, -4.1, 5.2)                                              # long hut on piles, gabled grey corrugated roof along x
    if state != "destroyed":
        for xx in (-8.0, -3.0, 2.0, 7.0):
            for zz in (-3.4, 4.5):
                b.tube("wood", (xx, 0.0, zz), (xx, 0.6, zz), 0.18, 5)
    blk(c, *box[:2], *box[2:], 3.4, ("stonewall", "flat"), y0=0.6 if False else 0.0, holes={}, main=True, roof=None)
    if state != "destroyed":
        prism_roof(c, *box[:2], *box[2:], 3.4, 3.0, "x", "lightcorr", over=0.5)
        door(c, "+x", box, 2.6, 1.4, 2.4)
        door(c, "-z", box, 4.0, 1.2, 2.2)
        for k in range(4):
            fpanel(c, "wglass", "-z", box, 7.5 + k * 2.4, 1.2, 1.2, 1.2, 0.0, 0.07)
        b.box("wood", (9.0, 0.2, 0.55), (1.0, 0.4, 1.6))
    else:
        rubble(c, box, 3.4, 6)
    if state == "damaged":
        scorch(c, "-z", box, 6.0, 1.8, 1.4)
    return c


def s_barracks2(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 3.0, 0.0, 3.0), 1.5)
    b = c.b
    hut = (-2.5, 2.5, -11.9, 11.7)                                           # a hut raised on stilts: deck platform round it, a ladder at one end, segmented roof panels
    sy = 1.8
    if state != "destroyed":
        for xx in (-3.2, 3.5):
            for zz in (-11.0, -5.5, 0.0, 5.5, 11.0):
                b.tube("wood", (xx, 0.0, zz), (xx, sy, zz), 0.16, 5)
        b.box("wood", (0.25, sy, 0.0), (7.5, 0.3, 23.2))
        b.box("machgrey", (3.9, sy + 0.5, 0.0), (0.12, 1.0, 23.0)) if c.fine else None
    blk(c, *hut[:2], *hut[2:], 3.2, ("stonewall", "flat"), y0=sy + 0.15, holes={}, main=True, roof=None)
    if state != "destroyed":
        barrel_roof(c, hut[0] - 0.2, hut[1] + 0.2, hut[2], hut[3], sy + 0.15 + 3.2, 0.9, "lightcorr", lights=False)
        for k in range(9):
            b.box("machgrey", (0.0, sy + 3.9 + 0.2, hut[2] + 1.2 + k * 2.6), (5.0, 0.12, 0.14))
        for k in range(3):
            door(c, "+x", hut, 3.0 + k * 7.0, 1.2, 2.2) if False else fpanel(c, "grate", "+x", hut, 3.0 + k * 7.0, 0.0, 1.2, 2.2, sy + 0.15, 0.08)
        for dz in (-1, 1):                                                   # the ladder at the end of the deck
            b.box("machgrey", (-3.7 if False else 3.2, 0.9, 12.4 if dz > 0 else -12.4), (0.1, 1.8, 0.1)) if False else None
        for sx in (3.0, 3.6):
            b.box("machgrey", (sx, 0.9, 11.9), (0.1, 1.8, 0.1))
        for k in range(5):
            b.box("machgrey", (3.3, 0.3 + k * 0.4, 11.9), (0.7, 0.06, 0.1))
    else:
        rubble(c, hut, 3.2, 6)
    if state == "damaged":
        scorch(c, "-x", hut, 11.0, 2.4 + sy, 1.3, 0.0)
    return c


def l_elitebarracks(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 4.0, 0.0, 3.0), 2.0)
    b = c.b
    pod = (-12.1, 3.6, -21.3, 21.3)
    blk(c, *pod[:2], *pod[2:], 2.2, ("stonewall", "flat"), holes={}, main=True, roof=None)
    pod2 = (-10.6, 2.1, -19.8, 19.8)
    blk(c, *pod2[:2], *pod2[2:], 2.2, ("stonewall", "flat"), y0=2.2, holes={}, roof=None)
    hall = (-8.0, -0.5, -19.2, 19.2)
    blk(c, *hall[:2], *hall[2:], 3.6, ("creamwall", "flat"), y0=4.4, holes={}, roof=None)
    if state != "destroyed":
        b.box("tanroof", (-4.25, 8.4, 0.0), (8.6, 0.4, 40.0))
        prism_roof(c, hall[0], hall[1], hall[2], hall[3], 8.0, 1.8, "z", "tanroof", over=0.5)
        for k in range(18):                                                    # the row of red-framed white windows along the long face
            zc = -17.0 + k * 2.0
            fpanel(c, "redframe", "+x", hall, zc + 19.2 - 0.6, 5.4, 1.2, 1.7, 0.0, 0.06)
            fpanel(c, "wglass", "+x", hall, zc + 19.2 - 0.45, 5.55, 0.9, 1.4, 0.0, 0.09)
        band(c, "+x", pod, 1.6, 0.4, "bluetrim")
    else:
        rubble(c, pod, 2.2, 10)
    if state == "damaged":
        scorch(c, "+x", hall, 19.0, 6.5, 1.8)
        roof_scorch(c, -4.25, 9.0, 4.0, 2.0)
    return c


def l_guardhouse(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 6.0, 0.0, 4.0), 2.0)
    b = c.b
    base = (-9.3, 9.3, -17.2, 17.2)
    blk(c, *base[:2], *base[2:], 4.0, ("stonewall", "flat"), holes={}, main=True, roof=None)
    if state != "destroyed":
        b.box("stonewall", (0.0, 4.15, 0.0), (19.2, 0.3, 35.0))
        for zz in (-13.0, 13.0):
            pagoda(c, -1.0, zz, 5.4, 13.1, 3, y0=4.3)
            pagoda(c, -4.5, zz, 5.0, 17.4, 3, y0=4.3) if False else None
        hall = (-6.5, 4.5, -10.0, 10.0)                                        # the long low hall with a tan stepped roof and a red-framed window row
        b.box("creamwall", (-1.0, 6.4, 0.0), (11.0, 4.4, 20.0))
        b.box("tanroof", (-1.0, 8.8, 0.0), (12.4, 0.4, 21.4))
        b.box("tanroof", (-1.0, 9.4, 0.0), (9.4, 0.4, 18.0))
        for k in range(12):
            zc = -9.0 + k * 1.65
            fpanel(c, "redframe", "+x", (-6.5, 4.5, -10.0, 10.0), zc + 10.0 - 0.6, 5.2, 1.2, 1.7, 4.3, 0.06)
            fpanel(c, "wglass", "+x", (-6.5, 4.5, -10.0, 10.0), zc + 10.0 - 0.45, 5.35, 0.9, 1.4, 4.3, 0.09)
            fpanel(c, "redframe", "-x", (-6.5, 4.5, -10.0, 10.0), zc + 10.0 - 0.6, 5.2, 1.2, 1.7, 4.3, 0.06)
            fpanel(c, "wglass", "-x", (-6.5, 4.5, -10.0, 10.0), zc + 10.0 - 0.45, 5.35, 0.9, 1.4, 4.3, 0.09)
        door(c, "+z", base, 8.0, 1.8, 2.8)
    else:
        pagoda(c, -1.0, -13.0, 5.4, 13.1, 3, y0=4.3)
        rubble(c, base, 4.0, 10)
    if state == "damaged":
        scorch(c, "+z", base, 12.0, 2.0, 1.8)
        roof_scorch(c, -1.0, 9.8, 0.0, 2.2)
    return c


GROUP_A = {
    "l_hq": (l_hq, "Liao HQ: camo hall under two vaults with pale bands, tower with hexagonal helipad"),
    "d_hq": (d_hq, "Davion HQ: cream tower with orange helipad and antennas, three descending tan-roofed bays"),
    "s_barracks": (s_barracks, "Steiner barracks: stone-grey hut on piles, gabled grey roof"),
    "s_barracks2": (s_barracks2, "Steiner long barracks: pale barrel roof, doors along the side"),
    "l_elitebarracks": (l_elitebarracks, "Liao elite barracks: teal podium, long tan-roofed hall, red-framed window row"),
    "l_guardhouse": (l_guardhouse, "Liao guardhouse: stone base with two pagodas and a tan-roofed hall"),
}
H.MEMBERS.update(GROUP_A)
ALL.update(GROUP_A)




# ======================================================================================= group B: controls
def dish(c, cx, y, cz, r=2.6, tilt=0.9, mat="machgrey"):
    """A large angled sensor dish in light grey metal: a bowl (a tilted flat-rimmed slab with a darker centre) on a pedestal."""
    if c.state == "destroyed":
        return
    b = c.b
    b.box("machgrey", (cx, y + 0.7, cz), (1.0, 1.4, 1.0))
    R = axis_angle(V([1.0, 0, 0]), tilt)
    b.box("lightroof", (cx, y + 2.3, cz), (r * 2.2, 0.3, r * 1.9), R)
    b.box("machgrey", (cx, y + 2.45, cz), (r * 1.5, 0.15, r * 1.3), R)
    b.box("machgrey", (cx, y + 2.9, cz - r * 0.5), (0.2, 1.2, 0.2))


def antenna_cluster(c, x0, x1, z0, z1, y, top, n=3):
    """A few light-grey lattice masts (four legs with cross bracing) on the wing roof."""
    if c.state == "destroyed":
        return
    I.tower_lattice(c, x0 + 1.5, z0 + 2.0, 1.6, 0.7, (top - y) * (0.65 if c.state == "damaged" else 1.0), "machgrey", 6, 0.1, y0=y)
    I.tower_lattice(c, x1 - 1.8, z0 + 4.5, 1.4, 0.6, (top - y) * (0.5 if c.state == "damaged" else 0.8), "machgrey", 5, 0.1, y0=y)
    if n > 2:
        I.tower_lattice(c, (x0 + x1) / 2, z1 - 2.0, 1.2, 0.5, (top - y) * 0.55, "machgrey", 4, 0.09, y0=y)


def sensor_control(fac):
    def build(state, lod, seed):
        if fac == "l":
            return l_sensor(state, lod, seed)
        c = shell(state, lod, seed, (0.0, 8.0, 3.0, 4.0), 2.0)
        b = c.b
        wallm = {"s": ("steinerwhite", "flat"), "l": ("creamwall", "flat"), "d": ("lightroof", "flat")}[fac]
        roofm = {"s": "lightcorr", "l": "camogreen", "d": "tanroof"}[fac]
        wing = (-11.0, -1.0, -2.6, 10.4)
        blk(c, *wing[:2], *wing[2:], 9.0 if fac != "d" else 8.0, wallm, holes={}, main=True, roof=None)
        tw = (-1.0, 4.8, -2.6, 2.6)
        blk2(c, *tw[:2], *tw[2:], 19.0, wallm, roof="flat", ac=0, vents=0, hatch=0, seed=seed, mat="lightroof", trim="lightroof")
        if state != "destroyed":
            hw = 9.0 if fac != "d" else 8.0
            b.box(roofm, (-6.0, hw + 0.3, 3.9), (10.8, 0.5, 13.2))
            if fac == "l":
                barrel_roof(c, wing[0], wing[1], wing[2], wing[3], hw, 1.8, "camogreen", lights=False)
            for key in ("-x", "+z"):
                ribbon(c, key, wing, 1.2, 1.6, 0.0, 1.0, None, 4, 0.5, mat="wglass")
                ribbon(c, key, wing, 4.8, 1.6, 0.0, 1.0, None, 4, 0.5, mat="wglass")
            for key in ("+x", "-x", "+z", "-z"):
                for fl in range(4):
                    ribbon(c, key, tw, 2.0 + fl * 4.2, 1.5, 0.0, 0.7, None, 3, 0.35, mat="wglass")
            dish(c, 2.0, 19.4, 0.0, 2.9)
            antenna_cluster(c, -10.0, -2.0, 0.0, 9.0, hw + 0.5, 23.0)
            door(c, "+z", wing, 3.0, 1.8, 2.8)
        else:
            rubble(c, wing, 3.0, 8)
        if state == "damaged":
            scorch(c, "+z", wing, 5.0, 3.0, 1.8)
            scorch(c, "+x", tw, 1.3, 11.0, 1.8)
            roof_scorch(c, 2.0, 19.6, 0.0, 1.5)
        return c
    return build


def l_sensor(state, lod, seed):
    """Liao sensor control: a pale cream tower with a dish, and a curved green-glazed vault wing."""
    c = shell(state, lod, seed, (0.0, 8.0, 3.0, 4.0), 2.0)
    b = c.b
    wing = (-11.0, -1.0, -2.6, 10.4)
    blk(c, *wing[:2], *wing[2:], 3.4, ("creamwall", "flat"), holes={}, main=True, roof=None)
    if state != "destroyed":
        vault_glazed(c, wing[0], wing[1], wing[2], wing[3], 3.4, 5.4, 5, seg=8, glass="glasslight", beds=False, end_glass="creamwall")
    tw = (-1.0, 3.6, -2.6, 2.6)
    blk2(c, *tw[:2], *tw[2:], 19.0, ("creamwall", "flat"), roof="flat", ac=0, vents=0, hatch=0, seed=seed, mat="lightroof", trim="lightroof")
    if state != "destroyed":
        for key in ("+x", "-x", "+z", "-z"):
            for fl in range(4):
                ribbon(c, key, tw, 2.0 + fl * 4.2, 1.5, 0.0, 0.7, None, 2, 0.35, mat="glasslight")
        dish(c, 1.3, 19.4, 0.0, 2.6)
        antenna_cluster(c, -10.0, -2.0, 0.0, 9.0, 9.0, 23.0)
        ribbon(c, "+z", wing, 0.6, 1.6, 0.0, 1.0, None, 4, 0.5, mat="glasslight")
        door(c, "+z", wing, 7.0, 1.6, 2.4)
    else:
        rubble(c, wing, 3.0, 8)
    if state == "damaged":
        scorch(c, "+z", wing, 5.0, 2.0, 1.4)
        scorch(c, "+x", tw, 1.3, 11.0, 1.8)
        roof_scorch(c, 1.3, 19.6, 0.0, 1.5)
    return c


def s_gatecontrol(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 8.0, -4.0, 4.0), 2.0)
    b = c.b
    tw = (-10.2, -2.8, -9.8, -2.4)                                       # the control tower with its black glass hood and mast
    blk2(c, *tw[:2], *tw[2:], 10.0, ("steinerwhite", "flat"), roof=None)
    wing = (-2.8, 12.0, -9.8, 1.8)                                       # the wide low wing with four grey roof hatches
    blk2(c, *wing[:2], *wing[2:], 6.0, ("steinerwhite", "flat"), roof="flat", ac=0, vents=0, hatch=0, lights=0, seed=seed + 2, mat="lightroof", trim="lightroof")
    if state != "destroyed":
        for ix in range(2):
            for iz in range(2):                                                 # glazed roof panels: blue glass in white frames
                px, pz = -0.2 + ix * 6.8, -7.0 + iz * 6.2
                b.box("lightroof", (px, 6.45, pz), (5.8, 0.2, 5.0))
                b.box("glassblue", (px, 6.58, pz), (5.2, 0.12, 4.4))
                for k in (-1, 0, 1):
                    b.box("lightroof", (px + k * 1.7, 6.66, pz), (0.14, 0.1, 4.4))
        def octo2(rr, y, hh, m):
            for k in range(4):
                b.box(m, (-6.5, y + hh / 2, -6.1), (2 * rr, hh, 0.8284 * rr), axis_angle(V([0, 1.0, 0]), k * math.pi / 4))
        for k in range(3):                                                      # the faceted hood: three stepped octagonal rings of black slanted glass between white sills
            octo2(3.7 - k * 0.6, 10.0 + k * 1.1, 0.9, "scorchblack")
            octo2(3.85 - k * 0.6, 10.9 + k * 1.1, 0.2, "lightroof")
        b.box("machgrey", (-6.5, 13.6, -6.1), (5.2, 0.3, 5.2))
        b.tube("steel", (-6.5, 13.7, -6.1), (-6.5, 21.9 if state == "intact" else 16.0, -6.1), 0.09, 5)
        for key in ("+z", "-z", "+x", "-x"):
            ribbon(c, key, tw, 4.5, 2.0, 0.0, 0.8, None, 3, 0.4, mat="wglass")
        ribbon(c, "+z", wing, 1.2, 2.0, 0.0, 1.0, None, 5, 0.5, mat="wglass")
        ribbon(c, "+x", wing, 1.2, 2.0, 0.0, 1.0, None, 3, 0.5, mat="wglass")
        door(c, "+z", wing, 10.5, 1.8, 2.8)
    else:
        rubble(c, tw, 4.0, 6)
    if state == "damaged":
        scorch(c, "+z", wing, 6.0, 3.0, 1.8)
        roof_scorch(c, 5.0, 6.7, -4.0, 1.8)
    return c


def d_gatecontrol(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 6.0, -4.0, 4.0), 2.0)
    b = c.b
    tw = (-4.0, 4.0, -9.4, -1.4)                                         # the central white tower block with a stepped hood, mast and flag
    blk2(c, *tw[:2], *tw[2:], 9.0, ("lightroof", "flat"), roof=None)
    rw = (4.0, 12.1, -11.3, 2.8)                                         # the big tan vault on the east, a low tan lean-to on the west
    blk(c, *rw[:2], *rw[2:], 4.0, ("lightroof", "flat"), holes={}, roof=None)
    lw = (-12.1, -4.0, -8.0, -2.0)
    blk(c, *lw[:2], *lw[2:], 3.0, ("lightroof", "flat"), holes={}, roof=None)
    if state != "destroyed":
        barrel_roof(c, rw[0], rw[1], rw[2], rw[3], 4.0, 3.4, "tanroof", lights=False)
        for k in range(5):
            b.box("lightroof", (8.05, 6.0, -11.0 + k * 3.4), (8.6, 0.25, 0.3))
        b.box("tanroof", (-8.05, 3.3, -5.0), (8.6, 0.4, 6.8))
        frustum(c, "lightroof", 0.0, -5.4, 4.1, 4.1, 9.0, 2.6, 2.6, 12.0)
        frustum(c, "lightroof", 0.0, -5.4, 2.4, 2.4, 12.0, 1.4, 1.4, 13.2)
        b.tube("steel", (0.2, 13.2, -5.4), (0.2, 20.8 if state == "intact" else 15.0, -5.4), 0.09, 5)
        dish(c, 0.0, 13.2, -5.4, 1.2, 0.5)
        for key in ("+z", "-z", "+x", "-x"):
            ribbon(c, key, tw, 4.0, 1.8, 0.0, 0.8, None, 3, 0.4, mat="wglass")
        ribbon(c, "+z", rw, 0.8, 1.6, 0.0, 1.0, None, 3, 0.4, mat="wglass")
        door(c, "+z", rw, 4.0, 1.8, 2.6)
    else:
        rubble(c, tw, 3.0, 8)
    if state == "damaged":
        scorch(c, "+z", tw, 4.0, 3.5, 1.8)
        scorch(c, "+z", rw, 6.0, 2.0, 1.4)
    return c


def s_spotlightcontrol(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 6.0, -4.0, 4.0), 2.0)
    b = c.b
    up = (-3.5, 10.9, -10.5, 0.5)                                         # the tall upper block with a big blue-grey roof and a pale light fixture in the corner
    blk2(c, *up[:2], *up[2:], 10.5, ("steinerwhite", "flat"), roof="flat", ac=0, vents=0, hatch=0, lights=0, seed=seed, mat="roofdark", trim="lightroof")
    low = (-8.1, 3.5, -4.0, 8.2)                                          # the lower wing with a ribbed grey-green roof
    blk(c, *low[:2], *low[2:], 4.4, ("steinerwhite", "flat"), holes={}, roof=None)
    if state != "destroyed":
        b.box("tanroof", (-2.3, 4.7, 2.1), (12.4, 0.5, 13.0))
        b.box("machgrey", (-2.3, 5.1, 2.1), (12.0, 0.2, 12.5)) if False else None
        for k in range(3):
            b.box("lightroof", (3.5 + k * 2.2, 10.9, -2.2), (1.6, 0.14, 0.5))
        b.box("bluetrim", (3.5, 10.8, -7.0), (10.0, 0.06, 0.5))
        b.box("bluetrim", (-1.0, 10.8, -4.0), (0.5, 0.06, 6.8))
        b.box("lightroof", (10.0, 11.1, -8.6), (1.8, 1.4, 1.8))
        b.box("creamwall", (10.0, 12.2, -8.6), (1.2, 1.2, 1.2), axis_angle(V([0, 1.0, 0]), 0.6))
        for key in ("+x", "-x", "-z"):
            ribbon(c, key, up, 2.5, 1.8, 0.0, 1.0, None, 4, 0.5, mat="wglass")
            ribbon(c, key, up, 6.5, 1.8, 0.0, 1.0, None, 4, 0.5, mat="wglass")
        ribbon(c, "+z", low, 1.0, 1.6, 0.0, 1.0, None, 4, 0.5, mat="wglass")
        door(c, "-x", low, 4.0, 1.4, 2.4)
    else:
        rubble(c, up, 5.0, 8)
    if state == "damaged":
        scorch(c, "+x", up, 5.0, 5.0, 1.8)
        roof_scorch(c, 4.0, 10.9, -5.0, 1.8)
    return c


def l_spotlightcontrol(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 6.0, -4.0, 4.0), 2.0)
    b = c.b
    octa_tower(c, 5.3, -5.3, 5.3, 9.0, y0=0.0, mat="creamwall")             # the faceted white tower with a dark glazed ring and a flat roof with a light fixture
    vw = (1.5, 9.0, -0.4, 7.3)
    blk(c, *vw[:2], *vw[2:], 2.4, ("creamwall", "flat"), holes={}, roof=None)
    if state != "destroyed":
        vault_glazed(c, vw[0], vw[1], vw[2], vw[3], 2.4, 2.6, 3, seg=6, glass="planting", beds=False, end_glass="creamwall")
        octa = lambda rr, y, hh, m: [b.box(m, (5.3, y + hh / 2, -5.3), (2 * rr, hh, 0.8284 * rr), axis_angle(V([0, 1.0, 0]), k * math.pi / 4)) for k in range(4)]
        octa(5.45, 5.4, 1.8, "scorchblack")                                  # the dark glazed ring at the top of the tower
        octa(5.6, 7.2, 0.5, "lightroof")
        octa(5.3, 9.0, 0.4, "lightroof")
        for k in range(2):
            b.box("machgrey", (4.0 + k * 3.0, 9.5, -5.0 + k * 1.0), (2.4, 0.2, 1.6))
        b.box("creamwall", (8.6, 9.9, -8.2), (1.6, 1.2, 1.6), axis_angle(V([0, 1.0, 0]), 0.6))
        b.tube("steel", (-6.8, 0.0, -2.0), (-6.8, 16.3 if state == "intact" else 10.0, -2.0), 0.08, 5)
        b.box("lightroof", (-4.5, 0.4, 2.5), (5.0, 0.3, 0.3)) if False else None
        door(c, "+z", vw, 3.0, 1.4, 2.2)
    else:
        rubble(c, (0.0, 10.6, -10.6, 0.0), 3.0, 6)
    if state == "damaged":
        scorch(c, "+z", (0.0, 10.6, -10.6, 0.0), 5.0, 3.5, 1.8)
        roof_scorch(c, 5.3, 9.5, -5.3, 1.8)
    return c


GROUP_B = {
    "s_gatecontrol": (s_gatecontrol, "Steiner gate control: white tower with black glass hood and mast, wide low wing with four grey hatches"),
    "d_gatecontrol": (d_gatecontrol, "Davion gate control: central white tower with hood and mast, tan vault east, tan lean-to west"),
    "s_sensorcontrol": (sensor_control("s"), "Steiner sensor control: tall white tower with a dish, low wing with an antenna forest"),
    "l_sensorcontrol": (sensor_control("l"), "Liao sensor control: tall tower with a dish, camo vault wing with an antenna forest"),
    "d_sensorcontrol": (sensor_control("d"), "Davion sensor control: tall tower with a dish, tan-roofed wing with an antenna forest"),
    "s_spotlightcontrol": (s_spotlightcontrol, "Steiner spotlight control: tall upper block with a blue-grey roof and light fixture, low ribbed wing"),
    "l_spotlightcontrol": (l_spotlightcontrol, "Liao spotlight control: faceted white tower with a dark glazed ring, camo vault wing"),
}
H.MEMBERS.update(GROUP_B)
ALL.update(GROUP_B)


# ======================================================================================= group C: towers, prison, weapons facility, generic military, checkpoint, alarm, ammo dump
def chain_fence(c, p0, p1, h, y0=0.0):
    """A chain-link panel between two ground points (x, z): the alpha 'chain' material on a flat panel, seen from both sides, with posts."""
    if c.state == "destroyed":
        return
    b = c.b
    a, e = V([p0[0], 0, p0[1]], float), V([p1[0], 0, p1[1]], float)
    L = float(np.linalg.norm(e - a))
    d = (e - a) / (L or 1.0)
    mid = (a + e) / 2 + V([0, y0 + h / 2, 0])
    n = V([-d[2], 0, d[0]])
    for sg in (1, -1):
        b.quad("chain", mid + n * 0.02 * sg, d, V([0, 1.0, 0]), L, h, (0, 0, L / 1.2, h / 1.2), normal=tuple(n * sg))
    for k in range(int(L / 4.0) + 1):
        q = a + d * min(L, k * 4.0)
        b.tube("machgrey", V([q[0], y0, q[2]]), V([q[0], y0 + h + 0.2, q[2]]), 0.07, 4)


def sensortower(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 6.0, 0.0, 3.0), 2.0)
    b = c.b
    cx, cz = 0.0, -0.45
    if state != "destroyed":
        frustum(c, "stonewall", cx, cz, 3.6, 2.9, 0.0, 1.2, 1.0, 2.4)                        # the flared base
        top = 12.6 if state == "intact" else 9.0
        frustum(c, "stonewall", cx, cz, 1.2, 1.0, 2.4, 0.95, 0.8, top)                        # the slender panelled shaft
        for k in range(4):
            face_panel(c, "tealpanel", cx, cz, 1.2, 2.4, 0.95, top, k, 0.3, 0.7, 0.08, 0.95, 0.03, ribs=5, rib_mat="machgrey")
        b.box("lightroof", (cx, top + 0.2, cz), (2.2, 0.4, 2.2))
        if state == "intact":
            R = axis_angle(V([1.0, 0, 0]), 0.9)
            b.box("lightroof", (cx, 14.0, cz + 0.4), (4.6, 0.3, 4.2), R)                         # the big angled sensor dish
            b.box("machgrey", (cx, 14.1, cz + 0.4), (3.2, 0.15, 2.8), R)
        else:
            b.box("lightroof", (cx + 0.6, top + 1.0, cz + 0.6), (3.6, 0.3, 3.2), axis_angle(V([1.0, 0, 0]), 0.5) @ axis_angle(V([0, 0, 1.0]), 0.4))
    else:
        frustum(c, "stonewall", cx, cz, 3.6, 2.9, 0.0, 3.0, 2.5, 1.8, drop=2)
        b.box("lightroof", (2.0, 0.7, 1.5), (3.6, 0.3, 3.0), axis_angle(V([0, 1.0, 0]), 0.6) @ axis_angle(V([0, 0, 1.0]), 0.3))
        rubble(c, (-3.6, 3.6, -3.1, 2.2), 2.0, 4)
    if state == "damaged":
        scorch(c, "+z", (-1.5, 1.5, -1.5, 1.5), 1.5, 6.0, 0.8, 0.0) if False else None
    return c


def prison(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 4.0, 0.0, 3.0), 2.0)
    b = c.b
    blk(c, -19.4, 10.6, -10.4, 28.1, 1.9, ("stonewall", "flat"), holes={}, roof=None) if False else None
    if state != "destroyed":
        for (p0, p1) in (((-19.0, -10.0), (10.2, -10.0)), ((10.2, -10.0), (10.2, 27.7)), ((10.2, 27.7), (-19.0, 27.7)), ((-19.0, 27.7), (-19.0, -10.0))):
            chain_fence(c, p0, p1, 3.6, 2.0)
            mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
            L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
            ang = math.atan2(p1[0] - p0[0], p1[1] - p0[1])
            b.box("stonewall", (mid[0], 0.95, mid[1]), (0.5, 1.9, L), axis_angle(V([0, 1.0, 0]), ang))        # the low concrete kerb wall under the fence
    blk(c, -4.2, 10.8, -10.3, 10.3, 8.0, ("stonewall", "flat"), holes={}, main=True, roof=None)                  # the cell block with a lattice roof
    if state != "destroyed":
        b.box("scorchblack", (3.3, 8.1, 0.0), (15.2, 0.3, 20.8))
        for k in range(8):
            b.box("lightroof", (-0.5 + k * 1.9, 8.4, 0.0), (0.3, 0.25, 20.8))
        for k in range(8):
            b.box("lightroof", (3.3, 8.45, -9.0 + k * 2.6), (15.2, 0.25, 0.3))
        for key in ("+x", "-x", "+z", "-z"):
            ribbon(c, key, (-4.2, 10.8, -10.3, 10.3), 2.6, 1.0, 0.0, 1.0, None, 6, 0.4, mat="wglass")
        b.box("stonewall", (11.5, 6.0, -11.0), (2.4, 12.0, 2.4))                                                 # a guard tower in the corner
        b.box("lightroof", (11.5, 12.2, -11.0), (3.4, 0.5, 3.4))
        ribbon(c, "+z", (10.3, 12.7, -12.2, -9.8), 8.2, 2.2, 0.0, 0.2, None, 2, 0.2, mat="wglass")
    else:
        rubble(c, (-4.2, 10.8, -10.3, 10.3), 8.0, 10)
    if state == "damaged":
        scorch(c, "+z", (-4.2, 10.8, -10.3, 10.3), 7.0, 3.5, 1.8)
        roof_scorch(c, 3.3, 8.3, 0.0, 2.4)
    return c


def weaponsfacility(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 4.0, 0.0, 3.0), 2.0)
    b = c.b
    s1 = (-20.6, 12.4, -1.5, 9.7)                                            # the long bunker with hazard bands, sawtooth foot bays and four roof hatches
    s2 = (6.0, 12.4, -14.0, -1.5)
    for sb in (s1, s2):
        blk(c, *sb[:2], *sb[2:], 5.0, ("stonewall", "flat"), holes={}, main=(sb is s1), roof=None)
    if state != "destroyed":
        for sb in (s1, s2):
            b.box("lightroof", ((sb[0] + sb[1]) / 2, 5.15, (sb[2] + sb[3]) / 2), (sb[1] - sb[0] + 0.6, 0.3, sb[3] - sb[2] + 0.6))
            b.box("machgrey", ((sb[0] + sb[1]) / 2, 5.4, (sb[2] + sb[3]) / 2), (sb[1] - sb[0] - 1.0, 0.2, sb[3] - sb[2] - 1.0))
        for k in range(4):
            b.box("lightroof", (-17.0 + k * 9.0, 5.6, 4.0), (2.0, 0.3, 2.0))
        for k in range(4):                                                      # the sawtooth foot bays in front of the long bunker
            xk = -17.0 + k * 9.0
            b.box("stonewall", (xk, 1.6, 12.0), (3.0, 3.2, 4.8), axis_angle(V([0, 1.0, 0]), 0.0))
            b.box("safetyyellow", (xk, 0.5, 14.3), (3.0, 0.5, 0.2))
        band(c, "+z", s1, 0.4, 0.8, "safetyyellow")
        band(c, "+x", s2, 0.4, 0.8, "safetyyellow")
        ribbon(c, "+z", s1, 2.6, 1.2, 0.0, 1.0, None, 8, 0.6, mat="wglass")
        door(c, "+z", s1, 30.0, 1.6, 2.6)
        b.box("scorchblack", (-4.0, 0.1, -10.0), (32.0, 0.1, 20.0))            # the black yard floor, wall on two sides
        b.box("scorchblack", (-4.0, 1.2, -20.3), (33.0, 2.4, 0.5))
        b.box("scorchblack", (-20.0, 1.2, -9.0), (0.5, 2.4, 22.0))
        rng = np.random.default_rng(3)
        for k in range(9):                                                     # crates
            b.box("bandorange" if k % 3 else "rust", (-17.0 + (k % 5) * 3.6 + rng.random() * 1.2, 0.9, -14.0 + (k // 5) * 4.2 + rng.random()), (2.2, 1.8, 2.2), axis_angle(V([0, 1.0, 0]), rng.random() * 3))
        b.box("machgrey", (-18.0, 1.4, -4.0), (3.0, 2.8, 3.0))                 # the yard crane: cab, lattice jib
        b.tube("machgrey", (-18.0, 2.8, -4.0), (-14.0, 14.3 if state == "intact" else 9.0, -9.0), 0.2, 5)
        b.tube("machgrey", (-17.2, 2.8, -4.0), (-13.4, 14.3 if state == "intact" else 9.0, -9.0), 0.2, 5)
    else:
        rubble(c, s1, 5.0, 10)
        rubble(c, s2, 5.0, 6)
    if state == "damaged":
        scorch(c, "+z", s1, 12.0, 2.8, 1.8)
        roof_scorch(c, -8.0, 5.7, 4.0, 2.4)
    return c


def genericmilitary(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 4.0, 3.0, 3.0), 2.0)
    b = c.b
    m = (-11.5, 10.7, -0.4, 12.6)                                            # a wide low block with a blue-grey roof and a roof hatch, plus a corner stair tower with antenna
    blk2(c, *m[:2], *m[2:], 6.2, ("stonewall", "flat"), roof="flat", ac=0, vents=0, hatch=1, lights=0, seed=seed, mat="tealpanel", trim="stonewall")
    t = (-11.5, -6.5, -4.1, -0.4)
    blk2(c, *t[:2], *t[2:], 8.4, ("stonewall", "flat"), roof="flat", ac=0, vents=0, hatch=0, seed=seed + 1, mat="tealpanel", trim="stonewall")
    if state != "destroyed":
        for key in ("+z", "+x", "-x"):
            ribbon(c, key, m, 1.2, 1.4, 0.0, 1.0, None, 6, 0.6, mat="wglass")
        ribbon(c, "+z", m, 4.0, 1.0, 0.0, 1.0, None, 6, 0.6, mat="wglass")
        b.box("machgrey", (1.0, 6.9, 9.0), (2.6, 0.3, 2.6))
        for k in range(5):
            b.box("machgrey", (-1.5 + k * 0.7, 0.3 + k * 0.3, 13.3), (0.7, 0.2, 1.4))   # the entrance stair
        door(c, "+z", m, 11.0, 1.8, 2.8)
        top = 13.7 if state == "intact" else 10.0
        I.tower_lattice(c, -9.0, -2.2, 1.0, 0.5, top - 8.8, "machgrey", 4, 0.08, y0=8.8)
    else:
        rubble(c, m, 6.2, 8)
    if state == "damaged":
        scorch(c, "+z", m, 4.0, 3.0, 1.6)
        roof_scorch(c, 2.0, 6.7, 6.0, 1.8)
    return c


def milcheckpoint(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 1.0, 0.0, 1.5), 1.0)
    b = c.b
    b.box("machgrey", (3.7, 0.75, 0.0), (0.8, 1.5, 0.7))                         # the gate holder post
    b.box("scorchblack", (3.7, 1.55, 0.0), (0.9, 0.1, 0.8))
    if state != "destroyed":
        n = 8 if c.fine else 4
        for k in range(n):                                                         # the hazard-striped boom, lowered across the road
            x = -2.9 + k * (6.2 / n)
            b.box("safetyyellow" if k % 2 == 0 else "scorchblack", (x + 0.4, 1.1, 0.0), (6.2 / n, 0.22, 0.22))
        b.box("machgrey", (-2.8, 0.5, 0.0), (0.3, 1.0, 0.3))
    else:
        b.box("safetyyellow", (-0.5, 0.15, 0.4), (3.0, 0.2, 0.22), axis_angle(V([0, 1.0, 0]), 0.5))
        b.box("scorchblack", (1.5, 0.12, -0.3), (2.0, 0.2, 0.22), axis_angle(V([0, 1.0, 0]), -0.3))
    return c


def perimeteralarm(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 4.0, 0.0, 2.0), 1.5)
    b = c.b
    px, pz = -0.9, 0.0
    if state != "destroyed":
        b.box("machgrey", (px, 0.4, pz), (2.0, 0.8, 2.0))
        top = 12.4 if state == "intact" else 8.0
        b.tube("machgrey", (px, 0.8, pz), (px, top, pz), 0.45, 8 if c.fine else 5)
        b.box("machgrey", (-2.6, 1.3, 0.0), (1.8, 1.8, 1.6))                          # the cabinet at the foot
        for k in range(3):                                                             # three red horn speakers round the head
            a = k * TAU / 3
            b.box("redframe", (px + math.cos(a) * 1.2, top - 0.2, pz + math.sin(a) * 1.2), (1.2, 1.0, 1.2), axis_angle(V([0, 1.0, 0]), a))
        b.box("machgrey", (px, top + 0.8, pz), (1.6, 1.4, 1.6))
        b.box("redframe", (px, top + 1.8, pz), (0.6, 0.5, 0.6))
    else:
        b.box("machgrey", (px, 0.4, pz), (2.0, 0.8, 2.0))
        b.tube("machgrey", (px, 0.5, pz), (px + 6.0, 0.8, pz + 2.0), 0.45, 6, caps=True)
        b.box("redframe", (px + 6.6, 0.9, pz + 2.1), (1.0, 0.8, 1.0))
    return c


def ammodump(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 3.0, 0.0, 2.5), 1.5)
    b = c.b
    cx, cz = 4.25, 4.25
    if state != "destroyed":
        frustum(c, "lightroof", cx, cz, 8.1, 7.0, 0.0, 6.6, 5.5, 5.2)                 # the sloped-sided bunker
        b.box("lightroof", (cx, 5.35, cz), (13.4, 0.3, 11.2))
        b.box("machgrey", (cx, 5.52, cz), (12.0, 0.1, 9.8))
        for sx in (-1, 1):                                                              # the red corner triangles and the H on the roof
            for sz in (-1, 1):
                b.box("redframe", (cx + sx * 5.2, 5.6, cz + sz * 4.0), (1.6, 0.05, 1.6), axis_angle(V([0, 1.0, 0]), math.pi / 4))
        b.box("lightroof", (cx, 5.6, cz), (0.5, 0.05, 2.6))
        b.box("lightroof", (cx - 1.1, 5.6, cz), (0.5, 0.05, 1.4))
        b.box("lightroof", (cx + 1.1, 5.6, cz), (0.5, 0.05, 1.4))
        for k in range(4):                                                              # hazard stripe band round the base
            for sd in (-1, 1):
                face_panel(c, "safetyyellow" if k % 2 == 0 else "scorchblack", cx, cz, 8.1, 0.0, 6.6, 5.2, 0 if sd < 0 else 2, 0.05 + k * 0.24, 0.05 + k * 0.24 + 0.12, 0.3, 0.5, 0.04)
        fpanel(c, "grate", "+z", (-3.9, 12.4, -2.8, 11.3), 8.0, 0.0, 2.2, 2.9, 1.2, 0.2) if False else None
        door(c, "+x", (-3.9, 12.4, -2.8, 11.3), 3.5, 2.6, 2.8)
        for k in range(4):
            b.box("machgrey", (12.9, 0.3 + k * 0.35, 3.0), (0.8, 0.12, 2.6))
    else:
        frustum(c, "lightroof", cx, cz, 8.1, 7.0, 0.0, 7.2, 6.2, 1.6, drop=1)
        rubble(c, (-3.9, 12.4, -2.8, 11.3), 3.0, 8)
    if state == "damaged":
        scorch(c, "+x", (-3.9, 12.4, -2.8, 11.3), 8.0, 3.0, 1.6)
        roof_scorch(c, cx, 5.6, cz, 2.4)
    return c


GROUP_C = {
    "sensortower": (sensortower, "slender panelled tower on a flared base with a big angled dish"),
    "prison": (prison, "fenced prison yard with a lattice-roofed cell block and a corner guard tower"),
    "weaponsfacility": (weaponsfacility, "L-shaped hazard-banded bunker around a crate yard with a crane"),
    "genericmilitary": (genericmilitary, "wide low block with a blue-grey roof, stair tower and antenna"),
    "milcheckpoint": (milcheckpoint, "hazard-striped boom gate and holder post"),
    "perimeteralarm": (perimeteralarm, "pole with three red horn speakers, beacon and cabinet"),
    "ammodump": (ammodump, "sloped-sided hazard-banded bunker with a marked roof and a door"),
}
H.MEMBERS.update(GROUP_C)
ALL.update(GROUP_C)


# ======================================================================================= group D: flags, tents, netting
def emblem(c, fac, cx, y, z, w, h, nz=1):
    """A faction mark from simple geometry (no emblem art exists in the project; style guide 2.3 palettes): Steiner (blue-silver) a silver ring with a gold bar,
    Liao (green-gold) a gold triangle, Davion (red-gold) a gold disc with eight rays. Drawn on the +z face (nz=1) at the given centre."""
    b = c.b
    zz = z + 0.05 * nz
    if fac == "s":
        b.disc("lightroof", (cx, y, zz), min(w, h) * 0.38, (0, 0, nz), 20 if c.fine else 10)
        b.disc("glassblue", (cx, y, zz + 0.01 * nz), min(w, h) * 0.27, (0, 0, nz), 20 if c.fine else 10)
        b.box("bandorange", (cx, y, zz + 0.02 * nz), (w * 0.55, h * 0.12, 0.02))
    elif fac == "l":
        P = np.array([(cx - w * 0.3, y - h * 0.28, zz), (cx + w * 0.3, y - h * 0.28, zz), (cx, y + h * 0.32, zz)])
        b.add("bandorange", P, np.array([(0, 0, nz)] * 3), np.array([(p_[0], p_[1]) for p_ in P]), [(0, 1, 2)] if nz > 0 else [(0, 2, 1)])
    else:
        b.disc("bandorange", (cx, y, zz), min(w, h) * 0.24, (0, 0, nz), 16 if c.fine else 8)
        for k in range(8):
            a_ = k * TAU / 8
            b.box("bandorange", (cx + math.cos(a_) * min(w, h) * 0.33, y + math.sin(a_) * min(w, h) * 0.33, zz), (min(w, h) * 0.16, min(w, h) * 0.05, 0.02), axis_angle(V([0, 0, 1.0]), a_))


def flag(fac):
    cloth = {"s": "glassblue", "l": "bandgreen", "d": "flagcloth"}[fac]
    def build(state, lod, seed):
        c = shell(state, lod, seed, (0.0, 4.0, 0.0, 1.0), 1.0)
        b = c.b
        if state == "destroyed":
            b.tube("machgrey", (0.0, 0.1, 0.0), (3.0, 0.3, 0.6), 0.1, 5)
            b.box(cloth, (3.5, 0.15, 0.8), (1.6, 0.05, 1.2), axis_angle(V([0, 1.0, 0]), 0.5))
            return c
        top = 9.8 if state == "intact" else 7.0
        b.tube("machgrey", (0.0, 0.0, 0.0), (0.0, top, 0.0), 0.1, 6)
        b.box(cloth, (1.0, top - 1.1, 0.0), (2.0, 2.0, 0.06))
        emblem(c, fac, 1.0, top - 1.1, 0.03, 2.0, 2.0, 1)
        emblem(c, fac, 1.0, top - 1.1, -0.03, 2.0, 2.0, -1)
        if state == "damaged":
            b.box("scorchblack", (1.7, top - 1.8, 0.05), (0.7, 0.9, 0.06))
        return c
    return build


def l_banner(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 4.0, 0.0, 1.0), 1.0)
    b = c.b
    if state == "destroyed":
        b.box("bandgreen", (0.0, 0.1, 0.0), (5.6, 0.05, 1.6), axis_angle(V([0, 1.0, 0]), 0.3))
        return c
    top = 13.8 if state == "intact" else 9.5
    b.box("lightroof", (0.0, top - 0.2, 0.0), (5.6, 0.2, 0.2))
    for sx in (-2.7, 2.7):
        b.tube("machgrey", (sx, top - 0.3, 0.0), (sx, 0.0, 0.0), 0.08, 4)
    b.box("bandgreen", (0.0, top / 2 - 0.4, 0.0), (5.0, top - 0.8, 0.06))
    emblem(c, "l", 0.0, top * 0.72, 0.03, 4.0, 4.0, 1)
    emblem(c, "l", 0.0, top * 0.72, -0.03, 4.0, 4.0, -1)
    if state == "damaged":
        b.box("scorchblack", (1.2, 1.4, 0.05), (1.8, 2.4, 0.06))
    return c


def tent(kind):
    """Green canvas tents: a ridge-roofed box with a door; htent adds red-cross discs; hqtent is a T of two ridges; longtent a long single ridge."""
    def build(state, lod, seed):
        c = shell(state, lod, seed, (0.0, 1.5, 0.0, 1.5), 1.0)
        b = c.b
        def gable(x0, x1, z0, z1, wall_h=1.2, rise=2.0):
            w, d = x1 - x0, z1 - z0
            cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
            ang = math.atan2(rise, w / 2)
            L = math.hypot(w / 2, rise)
            for sg in (-1, 1):
                b.box("canvas", (cx + sg * (w / 4 - 0.02), wall_h + rise / 2 + 0.03, cz), (L + 0.12, 0.08, d + 0.2), axis_angle(V([0, 0, 1.0]), -sg * ang))
            for sz in (-1, 1):
                b.box("canvas", (cx, wall_h / 2, cz + sz * d / 2), (w, wall_h, 0.08))
            for sx in (-1, 1):
                b.box("canvas", (cx + sx * w / 2, wall_h / 2, cz), (0.08, wall_h, d))
            for sz in (-1, 1):                                                   # gable end walls: a triangle filling the A under the ridge
                zz = cz + sz * d / 2
                P = np.array([(cx - w / 2, wall_h, zz), (cx + w / 2, wall_h, zz), (cx, wall_h + rise, zz)])
                b.add("canvas", P, np.array([(0, 0, sz)] * 3), np.array([(p_[0], p_[1]) for p_ in P]), [(0, 1, 2)] if sz > 0 else [(0, 2, 1)])
            return (cx, cz, w, d)
        def gable_x(x0, x1, z0, z1, wall_h=1.1, rise=2.0):
            """A ridge-along-x tent: slopes fall toward +-z, triangular gable ends at x0 and x1."""
            w, d = x1 - x0, z1 - z0
            cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
            ang = math.atan2(rise, d / 2)
            L = math.hypot(d / 2, rise)
            for sg in (-1, 1):
                b.box("canvas", (cx, wall_h + rise / 2 + 0.03, cz + sg * (d / 4 - 0.02)), (w + 0.2, 0.08, L + 0.12), axis_angle(V([1.0, 0, 0]), sg * ang))
            for sx in (-1, 1):
                b.box("canvas", (cx + sx * w / 2, wall_h / 2, cz), (0.08, wall_h, d))
                xx = cx + sx * w / 2
                P = np.array([(xx, wall_h, cz - d / 2), (xx, wall_h, cz + d / 2), (xx, wall_h + rise, cz)])
                b.add("canvas", P, np.array([(sx, 0, 0)] * 3), np.array([(p_[2], p_[1]) for p_ in P]), [(0, 1, 2)] if sx < 0 else [(0, 2, 1)])
            for sz in (-1, 1):
                b.box("canvas", (cx, wall_h / 2, cz + sz * d / 2), (w, wall_h, 0.08))
        if state == "destroyed":
            rng = np.random.default_rng(seed)
            for k in range(4):
                b.box("canvas", (rng.uniform(-3, 3), 0.1 + 0.05 * k, rng.uniform(-3, 3)), (rng.uniform(2, 4), 0.06, rng.uniform(2, 3)), axis_angle(V([0, 1.0, 0]), rng.random() * 3))
            b.box("scorchblack", (0.0, 0.03, 0.0), (5.0, 0.04, 6.0))
            return c
        if kind in ("tent", "htent"):
            cx, cz, w, d = gable(-3.6, 3.6, -4.1, 4.0, 1.1, 2.1)
            fpanel(c, "machgrey", "+z", (-3.6, 3.6, -4.1, 4.0), 5.8, 0.0, 0.7, 1.7, 0.0, 0.06)
            if kind == "htent":
                ang = math.atan2(2.1, 3.6)
                for sx in (-1, 1):                                              # a red-cross disc on each slope
                    cxs = sx * 1.8
                    ys = 1.1 + 2.1 * (1 - 1.8 / 3.6) + 0.07
                    R = axis_angle(V([0, 0, 1.0]), sx * ang)
                    b.box("lightroof", (cxs, ys, 0.0), (2.4, 0.04, 2.4), R)
                    b.box("redframe", (cxs, ys + 0.03, 0.0), (1.8, 0.04, 0.5), R)
                    b.box("redframe", (cxs, ys + 0.03, 0.0), (0.5, 0.04, 1.8), R)
        elif kind == "hqtent":
            gable_x(-8.1, 8.1, -0.4, 5.8, 1.1, 2.1)                              # the wide bar, ridge along x
            gable(-2.9, 2.9, -5.8, -0.4, 1.1, 2.1)                              # the stem toward -z, ridge along z
        else:
            gable_x(-8.1, 8.1, -3.6, 3.5, 1.1, 2.1)
        if state == "damaged":
            b.box("scorchblack", (1.0, 3.0, 0.5), (2.0, 0.1, 1.6), axis_angle(V([0, 0, 1.0]), 0.3))
        return c
    return build


def camonetting(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 2.0, 0.0, 1.0), 1.0)
    b = c.b
    if state == "destroyed":
        b.box("netgreen", (0.0, 0.08, 0.0), (6.5, 0.05, 9.0), axis_angle(V([0, 1.0, 0]), 0.3))
        b.tube("machgrey", (-3.0, 0.1, -5.0), (-2.0, 0.3, 4.0), 0.06, 4)
        return c
    hs = (4.6, 3.2, 2.4, 3.6) if state == "intact" else (4.6, 3.2, 1.0, 2.4)                 # four poles at different heights, a draped net between them
    pts = [(-3.4, -6.2), (3.4, -6.2), (3.4, 6.2), (-3.4, 6.2)]
    for (x, z), h in zip(pts, hs):
        b.tube("machgrey", (x, 0.0, z), (x, h, z), 0.07, 4)
    for k in range(6):
        t = k / 5.0
        y = hs[0] + (hs[3] - hs[0]) * t
        y2 = hs[1] + (hs[2] - hs[1]) * t
        b.box("netgreen", (0.0, (y + y2) / 2 - 0.1, -6.2 + 12.4 * t), (6.9, 0.07, 2.4), axis_angle(V([0, 0, 1.0]), math.atan2(y2 - y, 6.8)))
    return c


GROUP_D = {
    "s_flag": (flag("s"), "Steiner flag: pole to 9.8 m, blue cloth with emblem"),
    "l_flag": (flag("l"), "Liao flag: pole to 9.8 m, green cloth with emblem"),
    "d_flag": (flag("d"), "Davion flag: pole to 9.8 m, orange cloth with emblem"),
    "l_banner": (l_banner, "Liao banner: tall green hanging banner on a top rail"),
    "tent": (tent("tent"), "green canvas ridge tent"),
    "htent": (tent("htent"), "ridge tent with red-cross discs"),
    "hqtent": (tent("hqtent"), "T-shaped HQ tent, two ridges"),
    "longtent": (tent("longtent"), "long single-ridge tent"),
    "camonetting": (camonetting, "camouflage net on four uneven poles"),
}
H.MEMBERS.update(GROUP_D)
ALL.update(GROUP_D)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("app")
    ap.add_argument("--out", default=str(ROOT / "game/assets/v3/objects"))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    names = list(ALL) if a.app == "all" else (list(PILOT) if a.app == "pilot" else a.app.split(","))
    for app in names:
        H.build_member(app, out)


if __name__ == "__main__":
    main()
