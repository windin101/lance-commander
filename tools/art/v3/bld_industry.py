#!/usr/bin/env python3
"""v3 industrial plants (LANCE-39): chemical, processing, purification and waste plants, industrial plant/complex, heavy industrial, the three
factories, power generator, transformer and valve stations, relay station, crane, gantry, and the pipe system (straight 1-3, corner, end, three-
and four-way). Dimensions are the Shared Source originals' bounds (game/assets/objects/<app>.glb); identity details (brick towers, tapered stacks,
octagonal silos with chutes, cooling fans on a railed platform, riveted drum with handles, lattice jib, hub-and-flange pipes) are kept.

    python3 -I tools/art/v3/bld_industry.py <app>|pipes|all
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bld_hangars as H  # noqa: E402
import bld_hangars_b as HB  # noqa: E402
from bld_hangars import (Ctx, V, TAU, axis_angle, unit, clad, slab_sheet, timber, debris, torn, curl, ridge_keep, collapse, ROOT)  # noqa: E402

LOD_M = H.LOD_M
_win_orig = HB.window_grid


def _small_windows(c, mat_wall, p0, dirv, L, h, normal, cols, rows, y0=1.0, y1=None, gx=0.5, gy=0.5, state_hole=None):
    """The originals' windows are small framed squares, not bays: shrink each cell's opening about its centre."""
    out = []
    for (a, b_, c_, d_) in _win_orig(c, mat_wall, p0, dirv, L, h, normal, cols, rows, y0, y1, gx, gy, state_hole):
        cx, cy, w, hh = (a + c_) / 2, (b_ + d_) / 2, (c_ - a) * 0.34, (d_ - b_) * 0.44
        out.append((cx - w, cy - hh, cx + w, cy + hh))
    return out


HB.window_grid = _small_windows


def roof_ducts(c, x0, x1, z0, z1, y, mat="palepaint"):
    """Raised pale duct runs in a zigzag over a flat roof, as on the originals' factory roofs."""
    if c.state == "destroyed":
        return
    b = c.b
    W, D = x1 - x0, z1 - z0
    b.box(mat, (x0 + W * 0.45, y + 0.25, z0 + D * 0.3), (W * 0.62, 0.5, 0.45))
    b.box(mat, (x0 + W * 0.76, y + 0.25, z0 + D * 0.55), (0.45, 0.5, D * 0.5))
    b.box(mat, (x0 + W * 0.3, y + 0.25, z0 + D * 0.7), (W * 0.45, 0.5, 0.45))
    b.box(mat, (x0 + W * 0.52, y + 0.35, z0 + D * 0.5), (2.4, 0.7, 1.8))


# ======================================================================================================= pipes
def flange(c, x, z, axis, y0=0.0, h=2.7, w=3.0, t=0.9):
    """An end block with a round opening: a pale block, a dark disc in the face."""
    b = c.b
    sx, sz = (t, w) if axis == "x" else (w, t)
    b.box("palepaint", (x, y0 + h / 2, z), (sx, h, sz))
    b.box("palepaint", (x, y0 + h + 0.12, z), (sx + 0.2, 0.24, sz + 0.2))
    n = (1.0 if axis == "x" else 0.0, 0, 0.0 if axis == "x" else 1.0)
    return n


def pipe_run(c, p0, p1, r, mat="pipegreen", bands=2):
    b = c.b
    p0, p1 = V(p0, float), V(p1, float)
    b.tube(mat, p0, p1, r, 14 if c.fine else 6, caps=True)
    d = unit(p1 - p0)
    L = np.linalg.norm(p1 - p0)
    for k in range(bands if c.fine else 0):
        t = (k + 1) / (bands + 1)
        q = p0 + d * L * t
        b.tube("safetyyellow", q - d * 0.16, q + d * 0.16, r + 0.06, 14, caps=True)


def pipe_arm(c, hub_r, dirv, length, y=1.35, r=1.0, flange_w=3.0, supports=True, gap=None, hubless=False):
    """An arm along dirv (a unit axis vector) from the hub edge to `length`, ending in a flange block. gap=(t0, t1) breaks the pipe (damaged)."""
    b = c.b
    d = V(dirv, float)
    st = c.state
    axis = "x" if abs(d[0]) > 0.5 else "z"
    sgn = d[0] + d[2]
    L_end = length
    start = 0.0 if hubless else hub_r * 0.85
    p_a = d * start + V([0, y, 0])
    p_b = d * (L_end - 0.9) + V([0, y, 0])
    if st == "destroyed":
        # flange stub, two fallen pipe pieces
        fx, fz = (d * (L_end - 0.45))[0], (d * (L_end - 0.45))[2]
        sx, sz = (0.9, flange_w) if axis == "x" else (flange_w, 0.9)
        b.box("palepaint", (fx, 0.55, fz), (sx, 1.1, sz))
        for k in range(2):
            q0 = d * (start + (L_end - start) * (0.2 + 0.4 * k)) + V([c.rng.uniform(-0.5, 0.5) * abs(d[2]), 0.7, c.rng.uniform(-0.5, 0.5) * abs(d[0])])
            q1 = q0 + d * (L_end - start) * 0.28 + V([0, -0.2, 0])
            b.tube("pipegreen", q0, q1, r * 0.95, 10 if c.fine else 5, caps=False)
        return
    flange(c, *(d * (L_end - 0.45))[[0, 2]], axis, 0.0, 2.7, flange_w, 0.9)
    fx = (d * (L_end - 0.45))
    nrm = V([d[0], 0, d[2]])
    b.disc("grate", V([fx[0], y, fx[2]]) - nrm * 0.0 + d * 0.46, r * 0.9, tuple(d), 14 if c.fine else 6)
    if gap is None:
        pipe_run(c, p_a, p_b, r)
    else:
        t0, t1 = gap
        pa2 = d * (start + (L_end - start) * t0) + V([0, y, 0])
        pb2 = d * (start + (L_end - start) * t1) + V([0, y, 0])
        pipe_run(c, p_a, pa2, r)
        pipe_run(c, pb2, p_b, r)
        for q, s in ((pa2, 1), (pb2, -1)):
            b.tube("rust", q - d * 0.05 * s, q + d * 0.01 * s, r + 0.07, 12 if c.fine else 5, caps=False)
        b.disc("grate", pa2 + d * 0.01, r * 0.92, tuple(-d), 12 if c.fine else 5)
        # a sagging dangling end and debris
        pipe_run(c, pb2 + V([0, -0.1, 0]), pb2 - d * 0.0 + V([0, -0.9, 0]) + d * 0.9, r * 0.9, "pipegreen", 0)
    if supports:
        n = max(1, int((L_end - start) / 8.0))
        for k in range(n):
            q = d * (start + (L_end - start) * (k + 0.5) / n)
            sx, sz = (0.8, 2.6) if axis == "x" else (2.6, 0.8)
            b.box("palepaint", (q[0], 0.35, q[2]), (sx, 0.7, sz))


def hub(c, R=3.46, h=3.9, y0=0.0, top="pipegreen"):
    b = c.b
    seg = 8
    if c.state == "destroyed":
        b.revolve("palepaint", [(R, 0.0), (R, 1.0), (R * 0.85, 1.5)], seg, th0=math.pi / 8, uref=2.0)
        return
    b.revolve("palepaint", [(R, y0), (R, y0 + h * 0.72), (R * 0.9, y0 + h * 0.85), (R * 0.82, y0 + h)], seg, th0=math.pi / 8, uref=2.0)
    b.disc(top, (0, y0 + h, 0), R * 0.82, (0, 1, 0), seg)
    b.revolve("steel", [(R * 0.5, y0 + h), (R * 0.5, y0 + h + 0.18), (R * 0.42, y0 + h + 0.2)], 12 if c.fine else 6, uref=1.0)
    for k in range(3 if c.fine else 0):
        b.box("steel", (-1.0 + k * 1.0, y0 + h + 0.08, 1.4), (0.5, 0.12, 1.0))


def pipe_member(arms, bounds_note, straight=None):
    """arms: list of (dir, length). straight: (z0, z1, supports) for the straight pipes (no hub)."""
    def build(state, lod, seed):
        c = Ctx(state, lod, seed, breach=(0, 1.5, 0, 3.0), ledges=[(3.5, 1.5, 0.3)], ground_h=1.5)
        if straight is None:
            hub(c)
            for k, (d, L) in enumerate(arms):
                gap = (0.35, 0.55) if (state == "damaged" and k == 0) else None
                pipe_arm(c, 3.46, d, L, gap=gap)
        else:
            z0, z1 = straight
            L = z1 - z0
            c0 = (z0 + z1) / 2
            # build as an arm pair about the centre: two flanges, a long pipe
            b = c.b
            gap = (0.4, 0.6) if state == "damaged" else None
            for sg, zz in ((-1, z0 + 0.45), (1, z1 - 0.45)):
                if state == "destroyed":
                    b.box("palepaint", (0, 0.55, zz), (3.0, 1.1, 0.9))
                else:
                    flange(c, 0, zz, "z", 0.0, 2.7, 3.0, 0.9)
                    b.disc("grate", V([0, 1.35, zz + sg * -0.46 * -1]), 0.9, (0, 0, -sg), 14 if c.fine else 6) if False else None
            if state == "destroyed":
                for k in range(2):
                    q0 = V([c.rng.uniform(-0.4, 0.4), 0.7, z0 + L * (0.15 + 0.4 * k)])
                    b.tube("pipegreen", q0, q0 + V([c.rng.uniform(-0.3, 0.3), -0.2, L * 0.3]), 0.95, 10 if c.fine else 5, caps=False)
            else:
                pa, pb = V([0, 1.35, z0 + 0.9]), V([0, 1.35, z1 - 0.9])
                if gap is None:
                    pipe_run(c, pa, pb, 1.0, bands=3)
                else:
                    zm0, zm1 = z0 + L * gap[0], z0 + L * gap[1]
                    pipe_run(c, pa, V([0, 1.35, zm0]), 1.0)
                    pipe_run(c, V([0, 1.35, zm1]), pb, 1.0)
                    b.tube("rust", V([0, 1.35, zm0 - 0.02]), V([0, 1.35, zm0 + 0.01]), 1.08, 12, caps=False)
                    pipe_run(c, V([0, 1.25, zm1]), V([0, 0.35, zm1 + 1.2]), 0.9, "pipegreen", 0)
                for k in range(max(1, int(L / 8.0))):
                    zz = z0 + L * (k + 0.5) / max(1, int(L / 8.0))
                    b.box("palepaint", (0, 0.35, zz), (2.6, 0.7, 0.8))
        return c
    return build



# ======================================================================================================= shared building parts
def setw(wall, roof=None):
    H.WALL[:] = list(wall)
    if roof:
        H.ROOF[:] = [roof]


def prism_roof(c, x0, x1, z0, z1, y, rise, ridge="x", mat="slate", over=0.35, hip=False):
    """A ridged roof over the box: two sloped slabs (and gable ends when not hipped). ridge: axis the ridge runs along."""
    b = c.b
    if c.state == "destroyed":
        return
    W, D = x1 - x0, z1 - z0
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    th = 0.22
    if ridge == "x":
        ang = math.atan2(rise, D / 2 + over)
        L = math.hypot(D / 2 + over, rise)
        for sg in (-1, 1):
            b.box(mat, (cx, y + rise / 2 + th / 2, cz + sg * (D / 4 + over / 2)), (W + 2 * over, th, L), axis_angle(V([1.0, 0, 0]), sg * ang))
        for sg in (-1, 1):
            if not hip:
                pass
    else:
        ang = math.atan2(rise, W / 2 + over)
        L = math.hypot(W / 2 + over, rise)
        for sg in (-1, 1):
            b.box(mat, (cx + sg * (W / 4 + over / 2), y + rise / 2 + th / 2, cz), (L, th, D + 2 * over), axis_angle(V([0, 0, 1.0]), -sg * ang))


def cap_slab(c, x0, x1, z0, z1, y, mat="slate", trim="palepaint", t=0.4, over=0.3):
    """A flat roof slab with a pale parapet trim, the originals' dark capped roofs."""
    b = c.b
    if c.state == "destroyed":
        return
    b.box(mat, ((x0 + x1) / 2, y + t / 2, (z0 + z1) / 2), (x1 - x0 + 2 * over, t, z1 - z0 + 2 * over))
    for sg, z in ((-1, z0 - over), (1, z1 + over)):
        b.box(trim, ((x0 + x1) / 2, y + t + 0.1, z), (x1 - x0 + 2 * over + 0.2, 0.3, 0.3))
    for sg, x in ((-1, x0 - over), (1, x1 + over)):
        b.box(trim, (x, y + t + 0.1, (z0 + z1) / 2), (0.3, 0.3, z1 - z0 + 2 * over))


def vessel8(c, cx, cz, R, h, dome=1.2, mat="palepaint", band=None, seg=8, ladder=True, state=None, th_missing=1.57):
    """An octagonal process vessel with a shallow dome roof and an optional green band; damaged: a sector torn open with the dome gone on that side;
    destroyed: a low jagged ring and fallen plates."""
    b = c.b
    st = state or c.state
    fine = c.fine
    sg = seg if fine else seg
    th0 = math.pi / seg
    if st == "destroyed":
        b.revolve(mat, [(R, 0.0), (R, h * 0.22)], sg, cx=cx, cz=cz, th0=th0, th1=th0 + TAU * 0.78, uref=2.0)
        for k in range(5 if fine else 2):
            a = c.rng.uniform(0, TAU)
            q = V([cx + math.cos(a) * R * 0.9, 0.3, cz + math.sin(a) * R * 0.9])
            b.box(mat, q, (c.rng.uniform(1.0, 2.0), 0.3, c.rng.uniform(1.0, 2.2)), axis_angle(V([0, 1.0, 0]), a))
        b.disc("rust", (cx, 0.06, cz), R * 0.95, (0, 1, 0), 8 if fine else 6)
        return
    th1 = th0 + (TAU - th_missing if st == "damaged" else TAU)
    prof = [(R, 0.0), (R, h), (R * 0.93, h + dome * 0.45), (R * 0.55, h + dome * 0.88), (0.0, h + dome)]
    if st == "damaged":
        prof = [(R, 0.0), (R, h)]
        b.revolve(mat, [(R, 0.0), (R, h), (R * 0.93, h + dome * 0.45), (R * 0.55, h + dome * 0.88), (0.0, h + dome)], sg, cx=cx, cz=cz, th0=th0, th1=th1, uref=2.0)
        a_mid = th1 + th_missing / 2
        b.revolve(mat, [(R, 0.0), (R, h * 0.55)], sg, cx=cx, cz=cz, th0=th1, th1=th1 + th_missing, uref=2.0)  # the torn sector stops half way up
        b.disc("grate", (cx, h * 0.5, cz), R * 0.96, (0, 1, 0), 8)
        q = V([cx + math.cos(a_mid) * R * 1.05, h * 0.3, cz + math.sin(a_mid) * R * 1.05])
        b.box("rust", q, (1.6, 0.5, 2.4), axis_angle(V([0, 1.0, 0]), a_mid))
    else:
        b.revolve(mat, prof, sg, cx=cx, cz=cz, th0=th0, th1=th1, uref=2.0)
    if band:
        b.revolve(band, [(R + 0.06, h * 0.34), (R + 0.06, h * 0.5)], sg, cx=cx, cz=cz, th0=th0, th1=th1, uref=2.0)
    if ladder and fine and st != "damaged":
        b.box("steel", (cx + R * 0.93, h / 2, cz), (0.12, h, 0.5))
    if st == "intact":
        b.revolve("steel", [(R * 0.18, h + dome), (R * 0.18, h + dome + 0.25), (0.0, h + dome + 0.35)], 8, cx=cx, cz=cz, uref=1.0)


def cone_stack(c, cx, cz, r0, r1, h, mat="palepaint", lower=None):
    """A tapered stack (cooling-tower cone) with a rim; damaged: the top torn off and leaning beside it; destroyed: a stump and a fallen cone."""
    b = c.b
    fine = c.fine
    sg = 14 if fine else 7
    if c.state == "destroyed":
        b.revolve(mat, [(r0, 0.0), (r0 * 0.9, h * 0.22)], sg, cx=cx, cz=cz, th1=TAU * 0.8, uref=2.0)
        p0 = V([cx + r0 * 1.6, r0 * 0.5, cz + r0 * 1.2])
        b.tube(mat, p0, p0 + V([h * 0.35, 0.2, h * 0.1]), r0 * 0.5, sg, caps=False)
        return
    top = h if c.state == "intact" else h * 0.62
    rt = r0 + (r1 - r0) * (top / h)
    b.revolve(mat, [(r0, 0.0), (rt, top), (rt * 1.07, top + 0.25)], sg, cx=cx, cz=cz, uref=2.0, th1=TAU if c.state == "intact" else TAU * 0.86)
    if c.state == "damaged":
        b.disc("grate", (cx, top * 0.9, cz), rt * 0.95, (0, 1, 0), 8)
        p0 = V([cx + r0 * 1.8, rt * 0.4, cz + r0 * 0.4])
        b.tube(mat, p0, p0 + V([h * 0.25, 0.5, h * 0.12]), rt * 0.85, sg, caps=False)


def tower_lattice(c, cx, cz, w0, w1, h, mat="steel", panels=6, r=0.09, y0=0.0):
    """A four-leg lattice tower, legs tapering from w0 (base) to w1 (top) with cross bracing; damaged: the top third leans over with torn bracing;
    destroyed: a stub and a fallen section."""
    b = c.b
    fine = c.fine
    st = c.state
    h_full = h
    if st == "destroyed":
        h = h * 0.22
    legs = [(sx, sz) for sx in (-1, 1) for sz in (-1, 1)]
    def P(sx, sz, t):
        w = (w0 + (w1 - w0) * t) / 2
        return V([cx + sx * w, y0 + h * t, cz + sz * w])
    cut = 0.62 if st == "damaged" else 1.0
    def section(t_a, t_b):
        for sx, sz in legs:
            b.tube(mat, P(sx, sz, t_a), P(sx, sz, t_b), r, 6 if fine else 4)
        n0, n1 = int(round(t_a * panels)), int(round(t_b * panels))
        for k in range(n0, n1 + 1):
            t = k / panels
            for (a, bb) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
                b.tube(mat, P(*a, t), P(*bb, t), r * 0.6, 4)
            if k < n1 and fine:
                t2 = (k + 1) / panels
                for (a, bb) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
                    b.tube(mat, P(*a, t), P(*bb, t2), r * 0.45, 4)
    section(0.0, cut)
    if st == "damaged":
        piv = P(0, 0, cut)
        Rm = axis_angle(V([0, 0, 1.0]), 0.5)
        b.M = (Rm, piv - Rm @ piv)
        section(cut, 1.0)
        b.M = None
    elif st == "destroyed":
        Rm = axis_angle(V([0, 1.0, 0]), 0.6) @ axis_angle(V([0, 0, 1.0]), 1.45)
        piv = V([cx + w0, y0 + 0.5, cz])
        b.M = (Rm, piv - Rm @ piv)
        h = h_full * 0.4
        section(0.0, 1.0)
        b.M = None


def blk(c, x0, x1, z0, z1, h, wall, y0=0.0, holes=None, grids=None, main=False, roof=None, rise=0.0, ridge="x", roofmat="slate", plant=0, tint=None,
        dmg_side=1, trim="palepaint"):
    """A clad block: window grids / holes, a flat cap or ridged roof, roof plant; the destroyed state keeps stubs and a collapse."""
    setw(wall, roofmat)
    if grids:
        HB.facade_block(c, x0, x1, z0, z1, h, grids, y0, main, tint, dmg_side)
    else:
        H.hall(c, x0, x1, z0, z1, h, None, y0, holes or {}, main, tint_y=tint, dmg_side=dmg_side)
    if c.state == "destroyed":
        collapse(c, x0, x1, z0, z1, h, 3 if c.fine else 1)
        return
    if roof == "flat":
        cap_slab(c, x0, x1, z0, z1, y0 + h, roofmat, trim)
        if c.state == "damaged" and main:
            c.b.box("rust", ((x0 + x1) / 2 + 1.0, y0 + h + 0.55, (z0 + z1) / 2), (min(3.5, (x1 - x0) * 0.4), 0.7, min(3.0, (z1 - z0) * 0.3)), axis_angle(V([0, 0, 1.0]), 0.3))
    elif roof == "gable":
        prism_roof(c, x0, x1, z0, z1, y0 + h, rise, ridge, roofmat)
    if plant and c.state != "destroyed":
        plant_lo(c, x0 + 0.5, x1 - 0.5, z0 + 0.5, z1 - 0.5, y0 + h + 0.4, plant)


def plant_lo(c, x0, x1, z0, z1, y, n=3):
    """Roof plant kept under 1.2 m: AC boxes with fans, round vents, a hatch. (No masts: the originals' roofs are flat and clean-lined.)"""
    b = c.b
    if c.state == "destroyed":
        return
    W, D = x1 - x0, z1 - z0
    for k in range(n):
        ux, uz = x0 + 1.4 + (W - 2.8) * ((0.2 + 0.31 * k) % 0.8), z0 + 1.2 + (D - 2.4) * ((0.25 + 0.37 * k) % 0.8)
        b.box("machgrey", (ux, y + 0.45, uz), (1.6, 0.9, 1.2))
        b.revolve("steel", [(0.45, y + 0.9), (0.45, y + 0.95), (0.0, y + 0.95)], 12 if c.fine else 6, cx=ux, cz=uz, uref=1.0)
    for k in range(2):
        vx, vz = x0 + W * (0.3 + 0.4 * k), z0 + D * (0.55 + 0.2 * k)
        b.tube("galv", (vx, y, vz), (vx, y + 0.7, vz), 0.2, 8 if c.fine else 5)
    b.box("palepaint", (x0 + W * 0.7, y + 0.5, z0 + D * 0.3), (1.6, 1.0, 1.6))


def shell(state, lod, seed, breach, ground_h=2.0):
    return Ctx(state, lod, seed, breach=breach, ledges=[(6.0, 2.0, 0.5)], ao_rings=[(6.0, 1.2, 0.3)], ground_h=ground_h)


# ======================================================================================================= buildings (batch A)
def chemicalplant(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 6.0, -4.8, 4.0))
    # the brick tower with louvred window panels, a dark capped roof, a lean-to annex south of it, and three octagonal silos with green bands
    blk(c, -4.8, 5.8, -9.8, 0.0, 13.2, ("brick", "flat"), grids={"+z": (4, 2), "-x": (3, 2)}, main=True, roof="flat", roofmat="slate", plant=1, tint=7.0)
    blk(c, -4.8, 4.8, 0.0, 3.6, 7.6, ("tealpaint", "flat"), holes={"+z": [(1.0, 0.3, 3.6, 3.2), (5.0, 1.0, 8.4, 3.4)]}, roof="flat", roofmat="slate")
    for (sx, sz, h) in ((9.8, -6.8, 9.8), (9.8, -0.6, 9.3), (9.8, 5.4, 8.8)):
        vessel8(c, sx, sz, 2.6, h - 1.2, 1.2, "palepaint", band="safetyyellow")
    return c


def processingplant(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 6.0, 0.0, 4.0))
    blk(c, -8.4, -1.2, -9.6, 4.8, 6.6, ("tealpaint", "flat"), grids={"-x": (5, 2), "-z": (2, 2)}, main=True, roof="flat", roofmat="slate", plant=3, tint=5.0)
    cone_stack(c, 2.4, -5.4, 2.4, 1.1, 14.2)
    cone_stack(c, 2.4, 1.8, 2.4, 1.1, 14.0)
    blk(c, -7.2, 0.0, 4.8, 9.6, 6.2, ("tealpaint", "flat"), holes={"+z": [(1.5, 0.3, 4.5, 3.6)]}, roof="gable", rise=2.8, ridge="x", roofmat="slate")
    return c


def purificationplant(state, lod, seed):
    c = shell(state, lod, seed, (-8.0, 3.0, -6.0, 3.0))
    vessel8(c, -9.0, -9.0, 3.4, 2.4, 1.6, "palepaint", band="safetyyellow", ladder=False)
    vessel8(c, -9.0, -0.6, 3.4, 2.4, 1.6, "palepaint", band=None, ladder=False, state=("damaged" if state == "damaged" else None))
    blk(c, -4.8, 0.0, -12.0, -6.0, 5.2, ("palepaint", "flat"), holes={"+x": [(1.0, 0.1, 5.0, 3.6)]}, main=True, roof="flat", roofmat="slate", plant=1)
    blk(c, -4.8, 0.0, -3.6, 2.4, 5.0, ("palepaint", "flat"), holes={"+z": [(0.8, 0.1, 4.2, 3.4)]}, roof="flat", roofmat="slate")
    blk(c, 0.2, 2.9, -12.0, -6.0, 6.6, ("brick", "flat"), grids={"+x": (2, 2)}, roof="flat", roofmat="slate")
    # the chimney
    if state != "destroyed":
        c.b.revolve("brick", [(0.9, 6.6), (0.8, 10.2), (0.95, 10.6)], 10 if c.fine else 6, cx=1.5, cz=-10.2, uref=2.0, th1=TAU if state == "intact" else TAU * 0.84)
    return c



def wasteprocessor(state, lod, seed):
    c = shell(state, lod, seed, (-4.0, 2.0, 2.0, 3.0))
    blk(c, -12.0, 4.8, -2.4, 6.2, 4.6, ("palepaint", "flat"), holes={"+z": [(10.5, 0.1, 14.0, 3.3)]}, main=True, roof="flat", roofmat="slate", plant=3, trim="palepaint")
    for k, sx in enumerate((-9.8, -5.2, -0.6)):
        vessel8(c, sx, 9.0, 2.2, 2.0, 0.9, "palepaint", band="safetyyellow", ladder=False, state=("damaged" if (state == "damaged" and k == 1) else None))
        if state != "destroyed":      # the sloped chute from the hall roof into each tank
            c.b.box("palepaint", (sx, 2.5, 6.9), (1.2, 0.18, 3.0), axis_angle(V([1.0, 0, 0]), -0.62))
    return c


def industrialplant(state, lod, seed):
    c = shell(state, lod, seed, (3.0, 9.0, -6.0, 4.0))
    blk(c, -2.4, 8.4, -10.4, -1.0, 19.6, ("brick", "flat"), grids={"+z": (3, 4), "-x": (2, 4)}, main=True, roof="flat", roofmat="slate", plant=0, tint=14.0)
    blk(c, -9.6, -2.4, -8.4, -1.0, 5.2, ("brick", "flat"), grids={"-x": (2, 1), "+z": (2, 1)}, roof="flat", roofmat="slate")
    blk(c, -9.6, 3.6, -1.0, 8.6, 6.8, ("brick", "flat"), grids={"+z": (5, 2), "-x": (3, 2)}, roof="flat", roofmat="slate", plant=3)
    if state != "destroyed":
        c.b.revolve("brick", [(0.5, 5.2), (0.45, 14.4), (0.58, 14.8)], 8 if c.fine else 5, cx=-4.5, cz=-4.2, uref=2.0, th1=TAU if state == "intact" else TAU * 0.8)
    return c


def industrialcomplex(state, lod, seed):
    c = shell(state, lod, seed, (8.0, 6.0, 0.0, 5.0))
    blk(c, -11.4, 11.2, -11.6, 12.0, 9.2, ("palecorr", "corr"), holes={"+z": [(3.0, 0.1, 6.2, 5.4), (9.0, 0.1, 12.2, 5.4)], "-x": [(4.0, 6.0, 18.0, 7.6)]}, main=True, roof="gable", rise=4.4, ridge="z", roofmat="palecorr", dmg_side=1)
    if state != "destroyed":      # the long roof skylight strip along the ridge
        c.b.box("glass", (0.0, 13.7, 0.0), (1.6, 0.25, 18.0)) if state == "intact" else None
        for k in range(5 if c.fine else 2):
            c.b.box("steel", (0.0, 13.9, -9.0 + k * 4.5), (1.8, 0.12, 0.25))
    return c


def heavyindustrial(state, lod, seed):
    c = shell(state, lod, seed, (-2.0, 7.0, 0.0, 4.0))
    blk(c, -9.4, 3.6, -9.4, 9.4, 8.4, ("brick", "flat"), grids={"-x": (4, 2), "+z": (5, 2), "-z": (5, 2)}, main=True, roof="gable", rise=3.2, ridge="z", roofmat="slate")
    blk(c, 3.6, 9.4, -9.4, 9.4, 10.6, ("brick", "flat"), grids={"+x": (4, 3)}, roof="flat", roofmat="slate")
    if state != "destroyed":
        c.b.box("brick", (5.4, 12.6, -0.0), (1.4, 4.2, 14.0))            # the tall fin wall with its capping
        c.b.box("palepaint", (5.4, 14.8, 0.0), (1.8, 0.3, 14.4))
    return c


def factorysm(state, lod, seed):
    c = shell(state, lod, seed, (4.0, 3.0, 0.0, 3.0), 1.5)
    blk(c, -10.2, 19.0, -10.2, 9.4, 4.2, ("palecorr", "flat"), holes={"+z": [(2.0, 0.2, 8.0, 3.2), (11.0, 1.4, 22.0, 2.8)]}, main=True, roof="flat", roofmat="slate", plant=1, trim="palepaint")
    roof_ducts(c, -10.2, 19.0, -10.2, 9.4, 4.2)
    blk(c, -7.4, -1.0, 2.4, 9.4, 7.2, ("palecorr", "flat"), holes={"-x": [(2.0, 4.0, 8.0, 6.2)]}, roof="flat", roofmat="slate", plant=0)
    return c


def factorymd(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 8.0, 0.0, 4.0), 1.5)
    blk(c, -8.0, 8.0, 0.0, 12.4, 11.4, ("palecorr", "corr"), y0=0.0, holes={"+z": [(3.0, 0.1, 8.0, 5.0)]}, main=True, roof="flat", roofmat="slate", plant=2, trim="palepaint")
    blk(c, -8.0, 8.0, -12.4, 0.0, 8.8, ("palecorr", "corr"), holes={"-x": [(2.0, 0.1, 6.0, 4.0)]}, roof="flat", roofmat="slate", plant=1)
    return c


def factorylg(state, lod, seed):
    c = shell(state, lod, seed, (4.0, 7.0, 0.0, 4.0), 1.5)
    blk(c, -14.6, 14.6, 4.6, 8.0, 4.0, ("palecorr", "flat"), grids={"+z": (9, 1)}, roof="flat", roofmat="slate", plant=2)
    blk(c, -14.6, 11.6, -8.0, 4.6, 10.2, ("palecorr", "flat"), holes={"-z": [(8.0, 0.1, 14.0, 6.0)]}, main=True, roof="flat", roofmat="slate", plant=2)
    blk(c, -1.0, 4.6, -5.4, 0.2, 3.8, ("palecorr", "flat"), y0=10.2, roof="flat", roofmat="slate")
    roof_ducts(c, -14.6, 11.6, -8.0, 4.6, 10.2)
    roof_ducts(c, -14.6, 14.6, 4.6, 8.0, 4.0)
    return c


def powergenerator(state, lod, seed):
    c = shell(state, lod, seed, (4.0, 3.0, 4.0, 3.0), 1.5)
    blk(c, -12.4, -5.6, -1.4, 7.0, 3.6, ("palecorr", "flat"), roof="flat", roofmat="palepaint", plant=1, grids={"+z": (2, 1)}, main=True)
    blk(c, 12.0, 20.7, -1.4, 7.0, 3.6, ("palecorr", "flat"), roof="flat", roofmat="palepaint", plant=1, grids={"+z": (2, 1)})
    b = c.b
    if state != "destroyed":      # the central hexagonal generator hall, cyan panels, two tree-shaped antennas on the side blocks
        R = 6.6
        b.revolve("palepaint", [(R, 0.0), (R, 4.4), (R * 0.86, 6.0), (R * 0.62, 6.9)], 6, cx=3.0, cz=3.4, th0=0.0, uref=2.0)
        b.disc("machgrey", (3.0, 6.9, 3.4), R * 0.62, (0, 1, 0), 6)
        for k in range(2):
            b.box("glass", (3.0 - 1.8 + k * 3.6, 3.4, 3.4 - R * 0.87), (2.6, 1.3, 0.12))
            b.box("safetyyellow", (3.0 - 1.8 + k * 3.6, 4.3, 3.4 - R * 0.87), (2.9, 0.18, 0.14))
        for ax_ in (-9.0, 16.4):
            b.tube("steel", (ax_, 4.0, 3.0), (ax_, 5.3, 3.0), 0.12, 6)
            for k in range(4):
                b.tube("steel", (ax_, 4.2 + k * 0.25, 3.0), (ax_ + 0.9 - k * 0.2, 4.4 + k * 0.25, 3.0), 0.05, 4)
                b.tube("steel", (ax_, 4.2 + k * 0.25, 3.0), (ax_ - 0.9 + k * 0.2, 4.4 + k * 0.25, 3.0), 0.05, 4)
    else:
        b.box("concrete_dark", (3.0, 0.5, 3.4), (11.0, 1.0, 11.0))
    return c


def transformerstation(state, lod, seed):
    c = shell(state, lod, seed, (4.0, 5.0, -4.0, 3.5), 1.5)
    b = c.b
    setw(("palepaint", "flat"), "palepaint")
    # railed platform with stairs, two columns of cooling transformers with fan grilles
    b.box("concrete", (4.2, 1.5, -4.3), (16.4, 3.0, 16.4)) if state != "destroyed" else b.box("concrete_dark", (4.2, 0.6, -4.3), (16.4, 1.2, 16.4))
    if state != "destroyed":
        for sx in (-1, 1):
            for sz in (-1, 1):
                pass
        for k in range(10):
            for z in (-12.4, 3.8):
                b.tube("steel", (-3.8 + k * 1.82, 3.0, z), (-3.8 + k * 1.82, 4.1, z), 0.04, 4) if c.fine else None
        b.tube("steel", (-4.0, 4.1, -12.4), (12.4, 4.1, -12.4), 0.05, 4); b.tube("steel", (-4.0, 4.1, 3.8), (12.4, 4.1, 3.8), 0.05, 4)
        b.box("concrete", (10.4, 1.5, -2.0), (3.6, 0.3, 4.0), axis_angle(V([0, 0, 1.0]), 0.62))      # the access ramp
        for z in (-3.8, -0.2):
            b.tube("steel", (10.0, 3.6, z), (12.4, 1.8, z), 0.04, 4)
        for z in (-10.8, -6.8, -2.8, 0.8):
            for xc in (-0.6, 6.8):
                if state == "damaged" and abs(z - -6.8) < 0.1 and xc < 0:
                    b.box("rust", (xc, 3.6, z), (3.6, 1.2, 2.8), axis_angle(V([0, 1.0, 0]), 0.4))
                    continue
                b.box("machgrey", (xc, 3.0 + 2.9, z), (3.6, 5.8, 2.8))
                b.box("palepaint", (xc, 3.0 + 5.9, z), (3.8, 0.2, 3.0))
                b.revolve("steel", [(1.0, 9.0), (1.0, 9.05), (0.0, 9.05)], 12 if c.fine else 6, cx=xc, cz=z, uref=1.0)
                for sg in (-1, 1):
                    b.box("steel", (xc + sg * 1.82, 5.8, z), (0.08, 2.4, 2.0))
    else:
        for k in range(5):
            b.box("rust", (c.rng.uniform(-3, 9), 1.5, c.rng.uniform(-11, 2)), (c.rng.uniform(1.5, 3.2), 1.2, c.rng.uniform(1.4, 2.8)), axis_angle(V([0, 1.0, 0]), c.rng.random() * 3))
    return c


def valvestation(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 6.0, 4.0, 4.0))
    blk(c, -2.8, 4.8, -1.5, 9.7, 9.2, ("palecorr", "corr"), holes={"-x": [(1.5, 0.1, 5.0, 4.0)], "+z": [(1.0, 0.1, 4.0, 3.5)]}, main=True, roof="flat", roofmat="palepaint", plant=2, trim="palepaint")
    b = c.b
    if state != "destroyed":      # the horizontal riveted drum with three handles
        z0, z1 = -0.6, 9.0
        b.tube("machgrey", (8.6, 3.1, z0), (8.6, 3.1, z1), 2.5, 16 if c.fine else 8, caps=True)
        for k in range(8 if c.fine else 0):
            b.tube("steel", (8.6, 3.1, z0 + 0.6 + k * 1.2), (8.6, 3.1, z0 + 0.66 + k * 1.2), 2.56, 16, caps=False)
        for z in (0.6, 4.0, 7.4):
            for sg in (-1, 1):
                b.box("palepaint", (8.6 + sg * 1.5, 5.4, z), (0.3, 1.6, 0.3), axis_angle(V([0, 0, 1.0]), sg * 0.5))
            b.box("palepaint", (8.6, 6.1, z), (3.2, 0.3, 0.4))
        if state == "damaged":
            b.box("rust", (8.6, 3.1, 4.0), (5.0, 3.0, 0.5), axis_angle(V([0, 0, 1.0]), 0.2))
    else:
        b.tube("machgrey", (8.0, 1.5, 0.0), (9.0, 1.0, 6.0), 1.6, 10 if c.fine else 5, caps=False)
    return c


def relaystation(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 6.0, 0.0, 3.0), 1.5)
    blk(c, -4.0, 4.0, -2.8, 2.8, 4.8, ("palecorr", "corr"), holes={"+z": [(2.0, 0.1, 4.0, 3.0)]}, main=True, roof="flat", roofmat="slate", plant=1)
    tower_lattice(c, 0.0, 0.0, 3.0, 0.9, 12.2, "machgrey", 5, 0.13, y0=(4.8 if state != "destroyed" else 0.3))
    if state == "intact":
        c.b.tube("steel", (0, 17.0, 0), (0, 17.0, 0.01), 0.3, 6)
        c.b.revolve("palepaint", [(0.9, 16.2), (0.9, 16.6), (0.0, 17.1)], 10, cx=0.0, cz=0.0, uref=1.0)
        c.b.tube("steel", (0, 17.0, 0), (0, 17.9, 0), 0.05, 4)
    return c


def crane(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 6.0, 0.0, 3.0), 1.5)
    b = c.b
    tower_lattice(c, 0.0, 0.6, 3.2, 2.4, 4.2, "machgrey", 3, 0.09)
    if state != "destroyed":
        b.box("palepaint", (0.0, 5.4, 0.6), (5.4, 2.4, 3.2))
        b.box("safetyyellow", (0.0, 4.35, 0.6), (5.5, 0.3, 3.3))
        b.box("glass", (-0.0, 5.7, 2.25), (3.0, 1.0, 0.1))
        b.box("machgrey", (0.0, 6.7, 0.6), (5.6, 0.3, 3.4))
        if state == "intact":
            jib_a, jib_b = V([0.4, 6.8, -0.4]), V([6.9, 14.1, -7.4])
            for sx in (-0.5, 0.5):
                b.tube("safetyyellow", jib_a + V([sx, 0, sx * 0.5]), jib_b + V([sx * 0.6, 0, sx * 0.3]), 0.2, 6 if c.fine else 4)
            for k in range(0, 9 if c.fine else 4):
                t0, t1 = k / 8, (k + 1) / 8
                q0 = jib_a + (jib_b - jib_a) * t0; q1 = jib_a + (jib_b - jib_a) * t1
                b.tube("machgrey", q0 + V([-0.5 + 0.2 * t0, 0, -0.25 + 0.1 * t0]), q1 + V([0.5 - 0.2 * t1, 0, 0.25 - 0.1 * t1]), 0.09, 4)
            tip = jib_b
            b.tube("steel", tip, tip + V([0.3, -9.0, 0.3]), 0.04, 4)
            b.box("safetyyellow", tip + V([0.3, -9.4, 0.3]), (0.6, 0.7, 0.5))
        else:
            b.tube("safetyyellow", V([0.4, 6.8, -0.4]), V([3.0, 10.4, -3.8]), 0.2, 6)
            b.tube("safetyyellow", V([3.4, 10.4, -3.8]), V([6.6, 5.5, -7.2]), 0.2, 6)
    else:
        b.box("palepaint", (1.4, 0.7, 1.0), (4.0, 1.2, 2.6), axis_angle(V([0, 1.0, 0]), 0.3) @ axis_angle(V([0, 0, 1.0]), 0.12))
        b.tube("safetyyellow", V([-1.0, 0.4, -1.0]), V([-1.0, 1.4, -8.0]), 0.1, 6)
    return c


def gantry(state, lod, seed):
    c = shell(state, lod, seed, (-8.0, 10.0, 6.0, 4.0), 1.5)
    b = c.b
    # the pale control tower with two tall masts; the tall black frame behind it (25 m, grated floors), a lower frame beside it, a bridge between
    blk(c, -10.0, -5.8, 3.0, 12.4, 20.0, ("palecorr", "flat"), holes={"+z": [(0.8, 8.0, 3.2, 12.0)], "-x": [(1.5, 13.0, 7.5, 16.0)]}, main=True, roof="flat", roofmat="machgrey", plant=0)
    def frame(x0, x1, z0, z1, h, n):
        for x in (x0, x1):
            for z in (z0, z1):
                b.tube("machgrey", (x, 0.0, z), (x, h if state != "destroyed" else 3.0, z), 0.25, 6 if c.fine else 4)
        for k in range(n):
            if state == "destroyed" and k > 0:
                break
            yy = 0.4 + k * (h - 0.6) / (n - 1)
            b.box("machgrey", ((x0 + x1) / 2, yy, (z0 + z1) / 2), (x1 - x0, 0.3, z1 - z0))
            if c.fine and state != "destroyed":
                for x in (x0, x1):
                    b.tube("machgrey", (x, yy, z0), (x, yy, z1), 0.1, 4)
    frame(-6.4, 6.4, -7.8, 1.2, 25.0, 6)
    frame(-1.2, 8.4, 3.0, 11.0, 17.0, 4)
    if state != "destroyed":
        b.box("safetyyellow", (-7.9, 12.6, 12.6), (4.4, 0.3, 0.7))
        for ax_ in (-8.8, -7.0):
            b.tube("palepaint", (ax_, 20.4, 7.8), (ax_, 37.0 if state == "intact" else 29.0, 7.8), 0.12, 6 if c.fine else 4)
            b.tube("palepaint", (ax_, 20.4, 7.8), (ax_, 28.0, 7.8), 0.28, 6 if c.fine else 4)
        b.box("machgrey", (-6.4, 24.0, 2.2), (5.0, 0.4, 3.6))
        b.box("safetyyellow", (0.0, 25.2, -3.3), (13.0, 0.3, 0.5))
    return c


BUILD_B = {
    "wasteprocessor": (wasteprocessor, "long hall with roof panels, three octagonal tanks with chutes"),
    "industrialplant": (industrialplant, "tall brick tower, brick wing, annex with roof plant, small chimney"),
    "industrialcomplex": (industrialcomplex, "big pale hall, ridge skylight, doors"),
    "heavyindustrial": (heavyindustrial, "brick L block, slate gable, tall fin wall"),
    "factorysm": (factorysm, "wide low factory with roof tower"),
    "factorymd": (factorymd, "two stepped pale blocks"),
    "factorylg": (factorylg, "broad factory with raised centre box"),
    "powergenerator": (powergenerator, "three modules, hexagonal generator, antennas"),
    "transformerstation": (transformerstation, "railed platform with two columns of cooling transformers"),
    "valvestation": (valvestation, "pale block and riveted drum with handles"),
    "relaystation": (relaystation, "shed with 12 m lattice mast and dish"),
    "crane": (crane, "lattice base, cab, jib and hook"),
    "gantry": (gantry, "control cab, 25 m truss tower, two 37 m masts"),
}

BUILD_A = {
    "chemicalplant": (chemicalplant, "brick tower + annex + three octagonal silos"),
    "processingplant": (processingplant, "teal block, two tapered stacks, gabled front hall"),
    "purificationplant": (purificationplant, "two round tanks, two garage halls, brick block with chimney"),
}

PIPES = {
    "straightpipe1": (pipe_member(None, "", (-4.3, 4.3)), "pipe 8.6 m, flanged ends"),
    "straightpipe2": (pipe_member(None, "", (-12.8, 4.3)), "pipe 17.1 m, flanged ends, saddles"),
    "straightpipe3": (pipe_member(None, "", (-12.8, 12.8)), "pipe 25.6 m, flanged ends, saddles"),
    "endpipe": (pipe_member([((1, 0, 0), 12.8)], ""), "octagonal hub with one flanged arm +x"),
    "cornerpipe": (pipe_member([((1, 0, 0), 12.8), ((0, 0, -1), 12.8)], ""), "hub with arms +x and -z"),
    "threewaypipe": (pipe_member([((1, 0, 0), 12.8), ((-1, 0, 0), 12.8), ((0, 0, -1), 12.8)], ""), "hub with arms +-x and -z"),
    "fourwaypipe": (pipe_member([((1, 0, 0), 12.8), ((-1, 0, 0), 12.8), ((0, 0, -1), 12.8), ((0, 0, 1), 12.8)], ""), "hub with four arms"),
}
H.MEMBERS.update(PIPES)
MEMBERS_ALL = dict(PIPES)
H.MEMBERS.update(BUILD_A)
MEMBERS_ALL.update(BUILD_A)
H.MEMBERS.update(BUILD_B)
MEMBERS_ALL.update(BUILD_B)



# ======================================================================================================= pass 2 (Lee's review): identity details
# Roofs with parapets, vents, AC units, hatches, roof-lights and stains in dark roofing; window grids, louvres, doors and the originals' coloured
# bands on the walls; faceted grey tanks and stacks with seams and band rings; a flat-sided hexagon and a rounded barrel hall.
def _face(key, x0, x1, z0, z1):
    return {"-z": ((x0, z0), (1, 0, 0), (0, 0, -1), x1 - x0), "+z": ((x1, z1), (-1, 0, 0), (0, 0, 1), x1 - x0),
            "-x": ((x0, z1), (0, 0, -1), (-1, 0, 0), z1 - z0), "+x": ((x1, z0), (0, 0, 1), (1, 0, 0), z1 - z0)}[key]


def fpanel(c, mat, key, box, u0, v0, w, h, y0=0.0, off=0.05):
    """A flat panel on a wall face of the block box=(x0, x1, z0, z1): u along the face, v up from the block's base."""
    (px, pz), ud, n, L = _face(key, *box)
    ud, n = V(ud, float), V(n, float)
    ctr = V([px, y0 + v0 + h / 2, pz]) + ud * (u0 + w / 2) + n * off
    c.b.quad(mat, ctr, ud, V([0, 1.0, 0]), w, h, (0, 1, 1, 0), normal=tuple(n))


def louvre(c, key, box, u0, v0, w, h, y0=0.0):
    """A dark vent panel with slats."""
    if c.state == "destroyed":
        return
    fpanel(c, "grate", key, box, u0, v0, w, h, y0, 0.06)
    (px, pz), ud, n, L = _face(key, *box)
    ud, n = V(ud, float), V(n, float)
    for k in range(int(h / 0.42) if c.fine else 0):
        ctr = V([px, y0 + v0 + 0.25 + k * 0.42, pz]) + ud * (u0 + w / 2) + n * 0.13
        sz = (w, 0.1, 0.16) if abs(ud[0]) > 0.5 else (0.16, 0.1, w)
        c.b.box("machgrey", ctr, sz)


def door(c, key, box, u0, w, h, y0=0.0, mat="machgrey"):
    """A door panel: dark leaf, light frame, a hazard kick plate."""
    if c.state == "destroyed":
        return
    fpanel(c, "palepaint", key, box, u0 - 0.2, 0.0, w + 0.4, h + 0.2, y0, 0.05)
    fpanel(c, "grate", key, box, u0, 0.0, w, h, y0, 0.08)
    fpanel(c, "safetyyellow", key, box, u0, 0.0, w, 0.3, y0, 0.1)


def band(c, key, box, v0, h, mat, y0=0.0, u0=0.0, w=None):
    if c.state == "destroyed":
        return
    L = _face(key, *box)[3]
    fpanel(c, mat, key, box, u0, v0, (L - u0) if w is None else w, h, y0, 0.06)


def roll_door(c, key, box, u0, w, h, y0=0.0):
    """A roller shutter: dark leaf with ribs."""
    if c.state == "destroyed":
        return
    fpanel(c, "machgrey", key, box, u0 - 0.15, 0.0, w + 0.3, h + 0.15, y0, 0.05)
    fpanel(c, "grate", key, box, u0, 0.0, w, h, y0, 0.08)
    (px, pz), ud, n, L = _face(key, *box)
    ud, n = V(ud, float), V(n, float)
    for k in range(int(h / 0.5) if c.fine else 0):
        ctr = V([px, y0 + 0.4 + k * 0.5, pz]) + ud * (u0 + w / 2) + n * 0.11
        c.b.box("machgrey", ctr, (w, 0.06, 0.08) if abs(ud[0]) > 0.5 else (0.08, 0.06, w))


def roof2(c, x0, x1, z0, z1, y, ac=2, vents=2, lights=0, pipes=0, hatch=1, seed=0, over=0.25, stain=True, mat="slate", parapet=0.55, trim="palepaint"):
    """A dark roof slab with a parapet and the machinery the RTS camera reads: AC units with fans, vents, roof-lights, pipes, a hatch, stains."""
    if c.state == "destroyed":
        return
    b = c.b
    rng = np.random.default_rng(seed + 17)
    W, D = x1 - x0, z1 - z0
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    b.box(mat, (cx, y + 0.2, cz), (W + 2 * over, 0.4, D + 2 * over), None, col=(0, 0.9, 0))
    for z, sg in ((z0 - over, -1), (z1 + over, 1)):
        b.box(trim, (cx, y + 0.4 + parapet / 2, z), (W + 2 * over + 0.2, parapet, 0.3))
    for x in (x0 - over, x1 + over):
        b.box(trim, (x, y + 0.4 + parapet / 2, cz), (0.3, parapet, D + 2 * over))
    base = y + 0.4
    def spot(i, n):
        return (x0 + 1.6 + (W - 3.2) * ((0.13 + 0.37 * i + 0.11 * (seed % 5)) % 0.9), z0 + 1.4 + (D - 2.8) * ((0.21 + 0.43 * i + 0.07 * (seed % 3)) % 0.9))
    for k in range(ac):
        ux, uz = spot(k, ac)
        b.box("palepaint", (ux, base + 0.55, uz), (1.9, 1.1, 1.5))
        b.revolve("grate", [(0.62, base + 1.12), (0.62, base + 1.16), (0.0, base + 1.16)], 14 if c.fine else 6, cx=ux, cz=uz, uref=1.0)
        b.box("steel", (ux, base + 1.2, uz), (0.12, 0.08, 1.3)) if c.fine else None
    for k in range(vents):
        vx, vz = spot(k + ac + 1, vents)
        b.tube("steel", (vx, base, vz), (vx, base + 0.85, vz), 0.2, 8 if c.fine else 5)
        b.revolve("steel", [(0.34, base + 0.85), (0.3, base + 0.95), (0.0, base + 1.0)], 8 if c.fine else 5, cx=vx, cz=vz, uref=1.0)
    for k in range(lights):
        lx, lz = spot(k + ac + vents + 2, lights)
        b.box("palepaint", (lx, base + 0.18, lz), (2.0, 0.36, 1.2))
        b.box("glass", (lx, base + 0.4, lz), (1.7, 0.1, 0.9))
    for k in range(pipes):
        px_, pz_ = spot(k + 7, pipes)
        b.tube("safetyyellow", (px_, base + 0.35, pz_), (px_ + min(4.0, W * 0.4), base + 0.35, pz_), 0.14, 8 if c.fine else 4)
        for sx_ in (0.0, min(4.0, W * 0.4)):
            b.box("steel", (px_ + sx_, base + 0.15, pz_), (0.15, 0.3, 0.15))
    for k in range(hatch):
        hx, hz = spot(k + 11, hatch)
        b.box("palepaint", (hx, base + 0.4, hz), (1.4, 0.8, 1.4))
        b.box("machgrey", (hx, base + 0.82, hz), (1.6, 0.1, 1.6))
    if stain and c.fine:
        for k in range(3):
            sx_, sz_ = x0 + W * rng.uniform(0.15, 0.85), z0 + D * rng.uniform(0.15, 0.85)
            c.decal_ground(("oil", "streak_a", "streak_b")[k], (sx_, sz_), rng.uniform(2.0, 4.0), rng.uniform(1.5, 3.5), rng.uniform(0, 3), y=base + 0.01)


def blk2(c, x0, x1, z0, z1, h, wall, y0=0.0, grids=None, holes=None, main=False, roof=None, tint=None, dmg_side=1, **roofkw):
    """A clad block with the new roof kit; roof=None leaves it open (the caller adds a gable)."""
    blk(c, x0, x1, z0, z1, h, wall, y0=y0, holes=holes, grids=grids, main=main, roof=None, tint=tint, dmg_side=dmg_side)
    if c.state == "destroyed":
        return
    if roof == "flat":
        roof2(c, x0, x1, z0, z1, y0 + h, **roofkw)
        if c.state == "damaged" and main:
            c.b.box("rust", ((x0 + x1) / 2 + 1.0, y0 + h + 0.9, (z0 + z1) / 2), (min(3.5, (x1 - x0) * 0.4), 0.7, min(3.0, (z1 - z0) * 0.3)), axis_angle(V([0, 0, 1.0]), 0.3))


def vessel2(c, cx, cz, R, h, dome=1.0, band=None, state=None, th_missing=1.57, bands=2):
    """A faceted grey process vessel: octagonal shell with corner seams, band rings, a chamfered top with a manhole; damaged/destroyed as vessel8."""
    st = state or c.state
    I_ = globals()
    vessel8(c, cx, cz, R, h, dome, "tankgrey", band=None, ladder=False, state=state, th_missing=th_missing)
    if st != "intact" or not c.fine and False:
        return
    b = c.b
    th0 = math.pi / 8
    for k in range(8 if c.fine else 0):
        a = th0 + k * TAU / 8
        b.tube("steel", (cx + R * math.cos(a) * 1.01, 0.0, cz + R * math.sin(a) * 1.01), (cx + R * math.cos(a) * 1.01, h, cz + R * math.sin(a) * 1.01), 0.06, 4)
    for j in range(bands):
        y0 = h * (0.3 + 0.28 * j)
        b.revolve("machgrey" if j else (band or "machgrey"), [(R + 0.07, y0), (R + 0.07, y0 + 0.32)], 8, cx=cx, cz=cz, th0=th0, uref=2.0)
    b.revolve("machgrey", [(R * 0.98, h), (R * 0.98, h + 0.18)], 8, cx=cx, cz=cz, th0=th0, uref=2.0)
    b.revolve("steel", [(R * 0.22, h + dome), (R * 0.22, h + dome + 0.22), (R * 0.16, h + dome + 0.3), (0.0, h + dome + 0.32)], 10 if c.fine else 6, cx=cx, cz=cz, uref=1.0)


def stack2(c, cx, cz, r0, r1, h, band=None):
    """A faceted tapered stack: eight flat faces, a lower band and a top rim, seams."""
    b = c.b
    st = c.state
    if st == "destroyed":
        cone_stack(c, cx, cz, r0, r1, h, "tankgrey")
        return
    top = h if st == "intact" else h * 0.62
    rt = r0 + (r1 - r0) * (top / h)
    b.revolve("tankgrey", [(r0, 0.0), (r0 * 0.96, h * 0.42), (rt, top), (rt * 1.1, top + 0.3)], 8, cx=cx, cz=cz, th0=math.pi / 8, uref=2.0, th1=TAU if st == "intact" else TAU * 0.86)
    if band:
        b.revolve(band, [(r0 * 0.97, h * 0.2), (r0 * 0.97 + 0.02, h * 0.34)], 8, cx=cx, cz=cz, th0=math.pi / 8, uref=2.0, th1=TAU if st == "intact" else TAU * 0.86)
    if st == "damaged":
        b.disc("grate", (cx, top * 0.9, cz), rt * 0.95, (0, 1, 0), 8)
        p0 = V([cx + r0 * 1.8, rt * 0.4, cz + r0 * 0.4])
        b.tube("tankgrey", p0, p0 + V([h * 0.25, 0.5, h * 0.12]), rt * 0.85, 8, caps=False)
    if c.fine and st == "intact":
        b.revolve("grate", [(rt * 0.86, top + 0.3), (rt * 0.7, top + 0.32)], 8, cx=cx, cz=cz, th0=math.pi / 8, uref=1.0)


def barrel_roof(c, x0, x1, z0, z1, y, rise, mat="palecorr", seg=14, lights=True):
    """A rounded vault over the box, ridge along z: an arc cross-section in x, extruded z0..z1, with end caps of the same profile."""
    if c.state == "destroyed":
        return
    b = c.b
    W = x1 - x0
    cx = (x0 + x1) / 2
    ts = np.linspace(0, math.pi, seg + 1)
    xs = cx + (W / 2) * np.cos(ts)[::-1] * -1.0
    xs = cx - (W / 2) * np.cos(ts)
    ys = y + rise * np.sin(ts)
    P, N, U, I = [], [], [], []
    for j in range(seg + 1):
        for z in (z0 - 0.3, z1 + 0.3):
            P.append((xs[j], ys[j], z)); U.append((xs[j], z))
            nx, ny = -(W / 2) * math.cos(ts[j]) * -1 * 0 + (xs[j] - cx) / (W / 2) * rise, (ys[j] - y) / rise * (W / 2)
            nn = math.hypot(nx, ny) or 1.0
            N.append((nx / nn, ny / nn, 0.0))
    for j in range(seg):
        a = 2 * j
        I += [(a, a + 1, a + 2), (a + 1, a + 3, a + 2)]
    b.add(mat, np.array(P), np.array(N), np.array(U), I)
    for z, sg in ((z0 - 0.3, -1), (z1 + 0.3, 1)):       # end walls under the vault
        Pe, Ne, Ue, Ie = [(cx - W / 2, y, z)], [(0, 0, sg)], [(x0, y)], []
        for j in range(seg + 1):
            Pe.append((xs[j], ys[j], z)); Ne.append((0, 0, sg)); Ue.append((xs[j], ys[j]))
        for j in range(seg):
            Ie += [(0, j + 1, j + 2)] if sg > 0 else [(0, j + 2, j + 1)]
        Pe.append((cx + W / 2, y, z)); Ne.append((0, 0, sg)); Ue.append((x1, y))
        b.add(mat, np.array(Pe), np.array(Ne), np.array(Ue), Ie)
    for k in range(7 if c.fine else 3):         # ribs
        z = z0 + (z1 - z0) * (k + 0.5) / 7
        for j in range(0, seg, 2 if c.fine else 3):
            q0 = V([xs[j], ys[j] + 0.02, z]); q1 = V([xs[min(j + 2, seg)], ys[min(j + 2, seg)] + 0.02, z])
            b.tube("machgrey", q0, q1, 0.08, 4)
    for k in range(5 if lights else 0):
        b.box("glass", (cx, y + rise + 0.05, z0 + 2.0 + k * (z1 - z0 - 4.0) / 4), (1.6, 0.16, 1.8))


# ----- the buildings
def chemicalplant2(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 6.0, -4.8, 4.0))
    box = (-4.8, 5.8, -9.8, 0.0)
    blk2(c, *box[:2], *box[2:], 13.2, ("brick", "flat"), grids={"+z": (4, 3), "-x": (3, 3), "-z": (4, 2)}, main=True, roof="flat", tint=7.0, ac=2, vents=2, lights=1, hatch=1, seed=seed)
    if state != "destroyed":
        louvre(c, "+z", box, 1.2, 10.0, 8.0, 2.0)                  # the louvred band under the cap, as the original's window panels
        band(c, "-x", box, 6.2, 0.4, "bandgreen")
    abox = (-4.8, 4.8, 0.0, 3.6)
    blk2(c, *abox[:2], *abox[2:], 7.6, ("tealpaint", "flat"), holes={"+z": [(1.0, 0.3, 3.6, 3.2), (5.0, 1.0, 8.4, 3.4)]}, roof="flat", ac=1, vents=1, hatch=0, seed=seed + 3)
    if state != "destroyed":
        roll_door(c, "+z", abox, 1.0, 2.6, 2.9)
        band(c, "+z", abox, 4.6, 0.35, "bandorange")
    for (sx, sz, h) in ((9.8, -6.8, 9.8), (9.8, -0.6, 9.3), (9.8, 5.4, 8.8)):
        vessel2(c, sx, sz, 2.6, h - 1.2, 1.2, "bandgreen", bands=2)
    return c


def processingplant2(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 6.0, 0.0, 4.0))
    box = (-8.4, -1.2, -9.6, 4.8)
    blk2(c, *box[:2], *box[2:], 6.6, ("tealpaint", "flat"), grids={"-x": (5, 2), "-z": (2, 2)}, main=True, roof="flat", tint=5.0, ac=3, vents=2, lights=2, hatch=1, pipes=1, seed=seed)
    if state != "destroyed":
        louvre(c, "-x", box, 2.0, 2.4, 9.0, 1.7)                   # the front grille
        band(c, "-x", box, 4.2, 0.4, "bandorange")
    stack2(c, 2.4, -5.4, 2.4, 1.1, 14.2, "bandorange")
    stack2(c, 2.4, 1.8, 2.4, 1.1, 14.0, "bandorange")
    hb = (-7.2, 0.0, 4.8, 9.6)
    blk2(c, *hb[:2], *hb[2:], 6.2, ("tealpaint", "flat"), holes={"+z": [(1.5, 0.3, 4.5, 3.6)]}, roof=None)
    prism_roof(c, hb[0], hb[1], hb[2], hb[3], 6.2, 2.8, "x", "slate")
    if state != "destroyed":
        door(c, "+z", hb, 1.6, 2.8, 3.2)
        band(c, "+z", hb, 4.4, 0.4, "bandorange")
        louvre(c, "-x", hb, 0.8, 1.2, 3.0, 2.4)
    return c


def purificationplant2(state, lod, seed):
    c = shell(state, lod, seed, (-8.0, 3.0, -6.0, 3.0))
    vessel2(c, -9.0, -9.0, 3.4, 2.4, 1.6, "bandgreen", bands=1)
    vessel2(c, -9.0, -0.6, 3.4, 2.4, 1.6, "bandgreen", state=("damaged" if state == "damaged" else None), bands=1)
    g1 = (-4.8, 0.0, -12.0, -6.0)
    blk2(c, *g1[:2], *g1[2:], 5.2, ("tealpaint", "flat"), main=True, roof="flat", ac=2, vents=1, lights=1, hatch=1, seed=seed)
    g2 = (-4.8, 0.0, -3.6, 2.4)
    blk2(c, *g2[:2], *g2[2:], 5.0, ("tealpaint", "flat"), roof="flat", ac=1, vents=1, hatch=0, seed=seed + 2)
    br = (0.2, 2.9, -12.0, -6.0)
    blk2(c, *br[:2], *br[2:], 6.6, ("brick", "flat"), grids={"+x": (2, 2), "+z": (1, 2)}, roof="flat", ac=1, vents=0, hatch=1, seed=seed + 4)
    if state != "destroyed":
        roll_door(c, "+x", g1, 0.8, 4.4, 3.6)                      # the garage doors
        roll_door(c, "+z", g2, 0.8, 3.4, 3.2)
        band(c, "+x", g1, 4.0, 0.4, "safetyyellow")
        door(c, "+z", br, 0.8, 1.4, 2.4)
        c.b.revolve("brick", [(0.9, 6.6), (0.8, 10.2), (0.95, 10.6)], 10 if c.fine else 6, cx=1.5, cz=-10.2, uref=2.0, th1=TAU if state == "intact" else TAU * 0.84)
        c.b.revolve("machgrey", [(0.97, 9.4), (0.97, 9.8)], 10 if c.fine else 6, cx=1.5, cz=-10.2, uref=2.0)
    return c


def wasteprocessor2(state, lod, seed):
    c = shell(state, lod, seed, (-4.0, 2.0, 2.0, 3.0))
    box = (-12.0, 4.8, -2.4, 6.2)
    blk2(c, *box[:2], *box[2:], 4.6, ("brick", "flat"), holes={}, main=True, roof="flat", ac=3, vents=2, lights=3, pipes=1, hatch=1, seed=seed)
    if state != "destroyed":
        roll_door(c, "+z", box, 10.5, 3.6, 3.4)
        louvre(c, "+z", box, 1.5, 1.2, 4.0, 1.8)
        louvre(c, "+z", box, 6.0, 1.2, 3.0, 1.8)
        band(c, "+z", box, 3.8, 0.3, "safetyyellow")
    for k, sx in enumerate((-9.8, -5.2, -0.6)):
        vessel2(c, sx, 9.0, 2.2, 2.0, 0.9, "bandorange", state=("damaged" if (state == "damaged" and k == 1) else None), bands=1)
        if state != "destroyed":
            c.b.box("tankgrey", (sx, 2.5, 6.9), (1.2, 0.18, 3.0), axis_angle(V([1.0, 0, 0]), -0.62))
    return c


def industrialplant2(state, lod, seed):
    c = shell(state, lod, seed, (3.0, 9.0, -6.0, 4.0))
    t = (-2.4, 8.4, -10.4, -1.0)
    blk2(c, *t[:2], *t[2:], 19.6, ("brick", "flat"), grids={"+z": (3, 5), "-x": (2, 5), "+x": (2, 5)}, main=True, roof="flat", tint=14.0, ac=2, vents=1, lights=0, hatch=1, seed=seed)
    if state != "destroyed":
        band(c, "+z", t, 9.6, 0.5, "safetyyellow")
        louvre(c, "-x", t, 0.8, 16.5, 7.0, 1.8)
    w = (-9.6, -2.4, -8.4, -1.0)
    blk2(c, *w[:2], *w[2:], 5.2, ("brick", "flat"), grids={"-x": (2, 1), "+z": (2, 1)}, roof="flat", ac=1, vents=1, hatch=0, seed=seed + 1)
    a = (-9.6, 3.6, -1.0, 8.6)
    blk2(c, *a[:2], *a[2:], 6.8, ("brick", "flat"), grids={"+z": (5, 2), "-x": (3, 2)}, roof="flat", ac=4, vents=2, lights=1, hatch=1, pipes=1, seed=seed + 2)
    if state != "destroyed":
        door(c, "+z", a, 9.4, 1.5, 2.6)
        for k in range(2):                       # the two roof fans the original shows
            fx = -6.0 + k * 3.4
            c.b.revolve("grate", [(1.0, 7.5), (1.0, 7.6), (0.0, 7.6)], 14 if c.fine else 6, cx=fx, cz=2.6, uref=1.0)
            c.b.revolve("machgrey", [(1.08, 7.3), (1.08, 7.5)], 14 if c.fine else 6, cx=fx, cz=2.6, uref=1.0)
        c.b.revolve("brick", [(0.5, 5.2), (0.45, 14.4), (0.58, 14.8)], 8 if c.fine else 5, cx=-4.5, cz=-4.2, uref=2.0, th1=TAU if state == "intact" else TAU * 0.8)
    return c


def industrialcomplex2(state, lod, seed):
    c = shell(state, lod, seed, (8.0, 6.0, 0.0, 5.0))
    box = (-11.4, 11.2, -11.6, 12.0)
    blk(c, *box[:2], *box[2:], 9.2, ("lightcorr", "corr"), holes={"+z": [(3.0, 0.1, 6.2, 5.4), (9.0, 0.1, 12.2, 5.4)], "-x": [(4.0, 6.0, 18.0, 7.6)]}, main=True, roof=None)
    barrel_roof(c, box[0], box[1], box[2], box[3], 9.2, 4.6, "lightcorr")
    if state != "destroyed":
        band(c, "+z", box, 6.2, 0.4, "safetyyellow")
        for k in range(5):
            c.b.box("glass", (-11.45, 5.4, 8.8 - k * 3.0), (0.12, 1.0, 1.9))     # the clerestory window row on the long side
        door(c, "+z", box, 14.0, 2.0, 3.4)
        door(c, "+z", box, 17.0, 2.0, 3.4)
    return c


def heavyindustrial2(state, lod, seed):
    c = shell(state, lod, seed, (-2.0, 7.0, 0.0, 4.0))
    m = (-9.4, 3.6, -9.4, 9.4)
    blk2(c, *m[:2], *m[2:], 8.4, ("brick", "flat"), grids={"-x": (4, 3), "+z": (5, 3), "-z": (5, 3)}, main=True, roof=None)
    prism_roof(c, m[0], m[1], m[2], m[3], 8.4, 3.2, "z", "slate")
    wg = (3.6, 9.4, -9.4, 9.4)
    blk2(c, *wg[:2], *wg[2:], 10.6, ("brick", "flat"), grids={"+x": (4, 4)}, roof="flat", ac=2, vents=1, lights=1, hatch=1, seed=seed)
    if state != "destroyed":
        c.b.box("brick", (5.4, 12.6, 0.0), (1.4, 4.2, 14.0))
        c.b.box("machgrey", (5.4, 14.8, 0.0), (1.8, 0.3, 14.4))
        door(c, "+z", m, 4.0, 1.4, 2.6)
        for k in range(2):                       # dormers on the slate roof
            c.b.box("brick", (-3.0 - k * 4.4, 9.2, 0.0), (1.6, 1.6, 1.6)); c.b.box("slate", (-3.0 - k * 4.4, 10.1, 0.0), (2.0, 0.25, 2.0))
    return c


def factorysm2(state, lod, seed):
    c = shell(state, lod, seed, (4.0, 3.0, 0.0, 3.0), 1.5)
    m = (-10.2, 19.0, -10.2, 9.4)
    blk2(c, *m[:2], *m[2:], 4.2, ("palecorr", "flat"), holes={"+z": [(2.0, 0.2, 8.0, 3.2), (11.0, 1.4, 22.0, 2.8)]}, main=True, roof="flat", ac=4, vents=3, lights=4, pipes=2, hatch=1, seed=seed, mat="roofdark")
    if state != "destroyed":
        band(c, "+z", m, 3.2, 0.4, "safetyyellow", u0=0.0)
        roll_door(c, "+z", m, 24.0, 3.8, 3.4)
        roof_ducts(c, -10.2, 19.0, -10.2, 9.4, 4.7, "machgrey")
    blk2(c, -7.4, -1.0, 2.4, 9.4, 7.2, ("palecorr", "flat"), holes={"-x": [(2.0, 4.0, 8.0, 6.2)]}, roof="flat", ac=1, vents=0, lights=2, hatch=0, seed=seed + 5, mat="roofdark")
    return c


def factorymd2(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 8.0, 0.0, 4.0), 1.5)
    f = (-8.0, 8.0, 0.0, 12.4)
    blk2(c, *f[:2], *f[2:], 11.4, ("palecorr", "corr"), holes={"+z": [(3.0, 0.1, 8.0, 5.0)]}, main=True, roof="flat", ac=3, vents=2, lights=2, hatch=1, seed=seed, mat="roofdark")
    if state != "destroyed":
        louvre(c, "+z", f, 10.0, 6.0, 4.0, 2.4)
        band(c, "+z", f, 8.8, 0.35, "safetyyellow")
    r = (-8.0, 8.0, -12.4, 0.0)
    blk2(c, *r[:2], *r[2:], 8.8, ("palecorr", "corr"), holes={"-x": [(2.0, 0.1, 6.0, 4.0)]}, roof="flat", ac=2, vents=1, lights=1, hatch=1, seed=seed + 3, mat="roofdark")
    return c


def factorylg2(state, lod, seed):
    c = shell(state, lod, seed, (4.0, 7.0, 0.0, 4.0), 1.5)
    lo = (-14.6, 14.6, 4.6, 8.0)
    blk2(c, *lo[:2], *lo[2:], 4.0, ("palecorr", "flat"), grids={"+z": (9, 1)}, roof="flat", ac=2, vents=2, lights=1, hatch=0, seed=seed, mat="roofdark")
    mn = (-14.6, 11.6, -8.0, 4.6)
    blk2(c, *mn[:2], *mn[2:], 10.2, ("palecorr", "flat"), holes={"-z": [(8.0, 0.1, 14.0, 6.0)]}, main=True, roof="flat", ac=3, vents=2, lights=2, pipes=1, hatch=1, seed=seed + 1, mat="roofdark")
    blk2(c, -1.0, 4.6, -5.4, 0.2, 3.8, ("palecorr", "flat"), y0=10.2, roof="flat", ac=1, vents=0, lights=1, hatch=1, seed=seed + 2, mat="roofdark")
    if state != "destroyed":
        roof_ducts(c, -14.6, 11.6, -8.0, 4.6, 10.9, "machgrey")
        band(c, "-z", mn, 8.4, 0.35, "safetyyellow")
        louvre(c, "-z", mn, 2.0, 2.0, 4.0, 2.0)
    return c


def hex_prism(c, mat, cx, cz, R, y0, y1):
    """A flat-sided hexagonal prism (flat normals), vertices at 0, 60, ... degrees, with a flat top."""
    b = c.b
    vs = [(cx + R * math.cos(k * math.pi / 3), cz + R * math.sin(k * math.pi / 3)) for k in range(6)]
    for k in range(6):
        (x0, z0), (x1, z1) = vs[k], vs[(k + 1) % 6]
        am = (k + 0.5) * math.pi / 3
        n = (math.cos(am), 0.0, math.sin(am))
        P = [(x0, y0, z0), (x1, y0, z1), (x1, y1, z1), (x0, y1, z0)]
        L = math.hypot(x1 - x0, z1 - z0)
        U = [(0, y0), (L, y0), (L, y1), (0, y1)]
        b.add(mat, np.array(P), np.array([n] * 4), np.array(U), [(0, 2, 1), (0, 3, 2)])
    b.disc(mat, (cx, y1, cz), R, (0, 1, 0), 6)


def powergenerator2(state, lod, seed):
    c = shell(state, lod, seed, (4.0, 3.0, 4.0, 3.0), 1.5)
    for (x0, x1, nm) in ((-12.4, -5.6, 0), (12.0, 20.7, 1)):
        bx = (x0, x1, -1.4, 7.0)
        blk2(c, *bx[:2], *bx[2:], 3.6, ("palecorr", "flat"), grids={"+z": (3, 1)}, main=(nm == 0), roof="flat", ac=1, vents=1, lights=0, hatch=1, seed=seed + nm, mat="roofdark")
        if state != "destroyed":
            band(c, "+z", bx, 2.6, 0.3, "safetyyellow")
    b = c.b
    if state != "destroyed":
        R = 6.6          # the central flat-sided hexagonal generator hall (three rectangles at 0, 60 and 120 degrees), cyan panels
        hex_prism(c, "machgrey", 3.0, 4.6, R, 0.0, 3.8)
        hex_prism(c, "palepaint", 3.0, 4.6, R * 0.86, 3.8, 4.6)
        for k in range(6):
            a = k * math.pi / 3 + math.pi / 6
            apothem = R * math.sqrt(3) / 2
            px, pz = 3.0 + math.cos(a) * (apothem + 0.07), 4.6 + math.sin(a) * (apothem + 0.07)
            Ry = axis_angle(V([0, 1.0, 0]), -a)
            b.box("glass", (px, 2.2, pz), (0.12, 1.3, 3.2), Ry)
            b.box("safetyyellow", (px, 3.1, pz), (0.14, 0.2, 4.6), Ry)
        b.revolve("machgrey", [(2.6, 4.5), (2.6, 4.9), (1.8, 5.1)], 6, cx=3.0, cz=4.6, uref=1.0)
        for ax_ in (-9.0, 16.4):
            b.tube("steel", (ax_, 3.6, 3.0), (ax_, 9.4, 3.0), 0.12, 6)
            for k in range(4):
                b.tube("steel", (ax_, 4.6 + k * 0.9, 3.0), (ax_ + 1.0 - k * 0.2, 5.3 + k * 0.9, 3.0), 0.05, 4)
                b.tube("steel", (ax_, 4.6 + k * 0.9, 3.0), (ax_ - 1.0 + k * 0.2, 5.3 + k * 0.9, 3.0), 0.05, 4)
        if state == "damaged":
            b.box("rust", (3.0, 4.9, 4.6), (4.4, 0.7, 3.0), axis_angle(V([0, 0, 1.0]), 0.25))
    else:
        b.box("concrete_dark", (3.0, 0.5, 4.6), (11.0, 1.0, 11.0))
    return c


def transformerstation2(state, lod, seed):
    c = transformerstation(state, lod, seed)
    return c


def valvestation2(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 6.0, 4.0, 4.0))
    bx = (-2.8, 4.8, -1.5, 9.7)
    blk2(c, *bx[:2], *bx[2:], 9.2, ("palecorr", "corr"), holes={"-x": [(1.5, 0.1, 5.0, 4.0)], "+z": [(1.0, 0.1, 4.0, 3.5)]}, main=True, roof="flat", ac=3, vents=1, lights=2, hatch=1, seed=seed, mat="roofdark")
    if state != "destroyed":
        louvre(c, "-x", bx, 6.0, 4.0, 3.5, 3.0)
        band(c, "-x", bx, 7.0, 0.4, "safetyyellow")
    b = c.b
    if state != "destroyed":
        z0, z1 = -0.6, 9.0
        b.tube("machgrey", (8.6, 3.1, z0), (8.6, 3.1, z1), 2.5, 16 if c.fine else 8, caps=True)
        for k in range(8 if c.fine else 0):
            b.tube("steel", (8.6, 3.1, z0 + 0.6 + k * 1.2), (8.6, 3.1, z0 + 0.66 + k * 1.2), 2.56, 16, caps=False)
        for z in (0.6, 4.0, 7.4):
            for sg in (-1, 1):
                b.box("safetyyellow", (8.6 + sg * 1.5, 5.4, z), (0.3, 1.6, 0.3), axis_angle(V([0, 0, 1.0]), sg * 0.5))
            b.box("safetyyellow", (8.6, 6.1, z), (3.2, 0.3, 0.4))
        if state == "damaged":
            b.box("rust", (8.6, 3.1, 4.0), (5.0, 3.0, 0.5), axis_angle(V([0, 0, 1.0]), 0.2))
    else:
        b.tube("machgrey", (8.0, 1.5, 0.0), (9.0, 1.0, 6.0), 1.6, 10 if c.fine else 5, caps=False)
    return c


BUILD_C = {
    "chemicalplant": (chemicalplant2, "brick tower with window rows and louvres, annex, three faceted grey silos with green bands"),
    "processingplant": (processingplant2, "teal block with grille, two faceted stacks with orange bands, gabled front hall"),
    "purificationplant": (purificationplant2, "two grey round tanks, roller-door garages, brick block with banded chimney"),
    "wasteprocessor": (wasteprocessor2, "brick hall with roof lights, roller door, three tanks with chutes"),
    "industrialplant": (industrialplant2, "tall brick tower, annex with two roof fans, chimney"),
    "industrialcomplex": (industrialcomplex2, "rounded barrel hall with roof lights, doors, clerestory"),
    "heavyindustrial": (heavyindustrial2, "brick L block, slate gable with dormers, tall fin wall"),
    "factorysm": (factorysm2, "wide low factory, dark roof with ducts, roof tower"),
    "factorymd": (factorymd2, "two stepped pale blocks, dark roofs, louvres"),
    "factorylg": (factorylg2, "broad factory with raised centre box and ducts"),
    "powergenerator": (powergenerator2, "two modules and a flat-sided hexagonal generator hall"),
    "valvestation": (valvestation2, "pale block with louvres and a riveted drum with yellow handles"),
}
H.MEMBERS.update(BUILD_C)
MEMBERS_ALL.update(BUILD_C)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("app")
    ap.add_argument("--out", default=str(ROOT / "game/assets/v3/objects"))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    names = list(MEMBERS_ALL) if a.app == "all" else (list(PIPES) if a.app == "pipes" else a.app.split(","))
    for app in names:
        H.build_member(app, out)


if __name__ == "__main__":
    main()
