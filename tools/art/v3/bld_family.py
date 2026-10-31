#!/usr/bin/env python3
"""v3 storage family (LANCE-21): smallfueltank, pipetank, liquidstorage, watertower, grainstorage, civstoragea/b/c.

    python3 -I tools/art/v3/bld_family.py <app>|all [--out game/assets/v3/objects]

Same contract as bld_tanks.py (the pilot, largefueltank): <app>.glb, <app>_damaged.glb, <app>_destroyed.glb with nodes lod0 and
lod1, <app>.v3.json. Dimensions: the Shared Source originals' bounds and tools/cad/<app>_cad.py headers; every round part is a true
surface of revolution. Round tanks use bld_kit.round_tank; sheds and the grain store use planar panels clipped by Builder.cut_param.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bld_kit import Ctx, round_tank, lid_profile, uref, axis_angle, cell_uv, K, TAU  # noqa: E402
from bld_mesh import Builder, rot_y, unit  # noqa: E402
import bld_sheds  # noqa: E402  (detail pass: the sheds and the grain store)

ROOT = Path(__file__).resolve().parents[3]
LOD_M = 80.0
STATES = ("intact", "damaged", "destroyed")


# ===================================================================================================== planar helpers
def panel(c, mat, p0, dirv, L, up, h, normal, keep=None, uvmode="wall", thick=0.0, cell=0.45, band=0, col=(0, 0, 0), swap=False, disp=None):
    """A flat panel from p0 along dirv (L m) and up (h m), facing normal. keep(u, v) clips it (u 0..L, v 0..h)."""
    p0 = np.asarray(p0, float); dirv = unit(dirv); up = unit(up); n = unit(normal)
    if keep is None:
        u_s = (0, 1) if not swap else (1, 0)
        c.b.quad(mat, p0 + dirv * L / 2 + up * h / 2, dirv, up, L, h, (0, h, L, 0) if not swap else (0, L, h, 0), normal=n, col=col, band=band)
        if swap:
            pass
        return
    nu = max(2, int(L / cell)); nv = max(2, int(h / cell))
    us = np.linspace(0, L, nu + 1); vs = np.linspace(0, h, nv + 1)
    pos = lambda u, v: p0 + np.asarray(u)[..., None] * dirv + np.asarray(v)[..., None] * up
    uv = (lambda u, v: np.stack([v, u], -1)) if swap else (lambda u, v: np.stack([u, v], -1))
    flip = float(np.dot(np.cross(dirv, up), n)) < 0
    c.b.cut_param(mat, pos, us, vs, keep, uv=uv, flip=flip, band=band, col=col, thickness=thick, disp=disp)


def slab(c, mat, centre, ax_u, ax_v, L, W, T, col=(0, 0, 0)):
    """A slab with thickness T: L along ax_u, W along ax_v, T along their normal."""
    u, v = unit(ax_u), unit(ax_v)
    n = unit(np.cross(u, v))
    Rm = np.stack([u, n, v], 1)
    c.b.box(mat, centre, (L, T, W), Rm, col=col)


def torn_keep(state, w, h, rng, centre=(0.5, 0.55), size=(0.34, 0.3), ph=0.0, ridge_lo=0.25, ridge_hi=0.7):
    """keep(u, v) for a w x h panel: None intact; a ragged breach (damaged); a jagged low top edge (destroyed)."""
    if state == "intact":
        return None
    if state == "destroyed":
        a = rng.random(5) * TAU
        def keep(u, v):
            u = np.asarray(u)
            top = h * (0.5 * (ridge_lo + ridge_hi) + 0.5 * (ridge_hi - ridge_lo) * (0.55 * np.sin(u / w * 9 + a[0]) + 0.3 * np.sin(u / w * 23 + a[1]) + 0.15 * np.sin(u / w * 47 + a[2])))
            top = top + 0.05 * h * np.abs(((u * 3.1) % 2.0) - 1.0)
            return top - np.asarray(v)
        return keep
    cu, cv = centre[0] * w, centre[1] * h
    au, bv = size[0] * w, size[1] * h
    def keep(u, v):
        du, dv = (np.asarray(u) - cu), (np.asarray(v) - cv)
        g = np.sqrt((du / au) ** 2 + (dv / bv) ** 2)
        phi = np.arctan2(dv / bv, du / au)
        rho = 1 + 0.17 * np.sin(5 * phi + 1 + ph) + 0.1 * np.sin(9 * phi + 2) + 0.06 * np.sin(17 * phi)
        return (g - rho) * min(au, bv) * 0.9
    return keep


def jag_disp(h):
    return lambda u, v, k: np.clip(1 - np.asarray(k) / (0.05 * h + 0.1), 0, 1) ** 2 * (0.03 + 0.06 * np.sin(np.asarray(u) * 9.0) * np.cos(np.asarray(v) * 5.0))


# ======================================================================================================== round members
def tank_small(state, lod, seed):
    c = Ctx(state, lod, seed, breach=(1.5, 4.0, 2.6, 2.0), ledges=[(5.2, 1.4, 0.9), (2.26, 0.9, 0.8)], ao_rings=[(2.26, 0.9, 0.5), (5.39, 0.5, 0.3)], ground_h=1.2)
    p = dict(R=3.29, y0=2.26, y1=5.39, breach_deg=60, welds=[3.7], diamonds=[(200, 3.0, 4.1, 1.0), (20, 3.0, 4.1, 1.0)], ids=[(255, 4.4, 5.0, 1.2)],
             belt=(2.7, 3.55), tint=(4.6, 5.25), tint_dome=(3.18, 5.47, 2.2, 5.9), beads=10,
             lower=[("concrete", [(3.95, 0.0), (3.95, 0.18), (3.3, 0.85)], 2.0), ("paint", [(2.35, 0.85), (2.05, 1.6), (2.3, 2.0), (3.29, 2.26)], 2.0)],
             lid=[(3.29, 5.39), (3.1, 5.55), (1.9, 6.1), (0.0, 6.7)], hatch=None, catwalk=None, ladder_deg=210.0, ladder_top=5.9, lid_rail=None)
    round_tank(c, p)
    b = c.b
    # the riser stack beside the tank: a round pipe to 7.85 m under a cone, with its fan
    rx, rz, rr = 2.83, 0.0, 1.19
    if state == "intact":
        b.revolve("paint", [(rr, 3.0), (rr, 7.85)], 40 if lod == 0 else 24, cx=rx, cz=rz, uref=uref(rr, 2.0))
        b.revolve("galv", [(rr + 0.06, 7.85), (rr * 0.5, 8.35), (0.0, 8.6)], 24, cx=rx, cz=rz, uref=uref(rr, 1.5))
        c.ring("galv", 7.6, 7.85, rr, 0.08, rx, rz, 24)
        c.ring("galv", 5.5, 5.7, rr, 0.07, rx, rz, 24)
        c.decal_rev("valve_tag", 0.2, 1.1, 6.0, 7.0, rr, rx, rz, off=0.03)
    elif state == "damaged":
        ys = np.unique(np.r_[np.linspace(3.0, 7.85, 20)])
        th = math.radians(60)
        keep = lambda t, y: np.where(np.abs((np.asarray(t) - th + math.pi) % TAU - math.pi) * rr < 0.55, np.asarray(y) - 6.0 + 0.4 * np.sin(np.asarray(t) * 7), 1.0)
        b.cut_surface("paint", lambda yy: np.full_like(yy, rr), ys, 40 if lod == 0 else 24, keep, cx=rx, cz=rz, uref=uref(rr, 2.0), thickness=0.06)
        b.revolve("galv", [(rr + 0.06, 7.85), (rr * 0.5, 8.35), (0.0, 8.6)], 24, cx=rx, cz=rz, th0=math.radians(100), th1=math.radians(420), uref=uref(rr, 1.5))
    else:
        b.revolve("paint", [(rr, 3.0), (rr, 4.2)], 24, cx=rx, cz=rz, uref=uref(rr, 2.0))
        ctx = axis_angle(np.array([0, 0, 1.0]), 1.35)
        pc = np.array([rx, 4.2, rz])
        b.M = (ctx, pc - ctx @ pc + np.array([1.4, -1.0, 0.8]))
        b.revolve("paint", [(rr, 4.3), (rr, 7.2)], 18, cx=rx, cz=rz, uref=uref(rr, 2.0))
        b.revolve("rust", [(rr - 0.05, 4.3), (rr - 0.05, 7.2)], 18, cx=rx, cz=rz, flip=True, uref=uref(rr, 1.5))
        b.M = None
    return c


def tank_pipe(state, lod, seed):
    c = Ctx(state, lod, seed, breach=(1.0, 9.0, 4.0, 2.4), ledges=[(11.93, 2.4, 0.95), (4.6, 1.2, 0.8), (3.92, 1.5, 0.8)], ao_rings=[(4.6, 1.8, 0.5)], ground_h=1.5)
    p = dict(R=4.65, y0=4.6, y1=11.93, breach_deg=90, welds=[6.6, 9.9], diamonds=[(200, 6.0, 7.2, 1.3)], ids=[(20, 7.6, 8.6, 1.6)], beads=12,
             belt=(7.1, 9.0), tint=(10.4, 11.5), tint_dome=(4.2, 12.05, 3.0, 12.38), id_digits=(0, 3),
             lower=[("paint", [(3.94, 3.92), (4.65, 4.6)], 2.0)],
             lid=[(4.65, 11.93), (4.2, 12.12), (3.2, 12.38), (2.68, 12.44), (0.0, 12.44)], hatch=(1.7, 12.4, 12.58), catwalk=None, ladder_deg=150.0,
             ladder_top=12.4, lid_rail=None)
    round_tank(c, p)
    b = c.b
    fine = lod == 0
    # pedestal: a boxy base narrowing to a 3.4 m square under the tank
    if state != "destroyed" or True:
        b.box("concrete", (0.935, 1.365, 0.0), (8.35, 2.73, 6.48))
        b.revolve("paint", [(2.4, 3.92), (3.1, 2.73)], 4, th0=math.pi / 4, uref=3.0)
        b.disc("concrete", (0.935, 2.73, 0.0), 0.01, seg=4)
        b.box("galv", (0.935, 2.78, 0.0), (8.55, 0.1, 6.68))
    # the pipe: round, flanged, to a tapered end block
    py, pr = 1.37, 0.80
    pe = 11.93 if state != "destroyed" else 9.0
    b.tube("galv", (5.0, py, 0), (pe, py, 0), pr, 32 if fine else 16)
    for x in (5.6, 8.4, pe - 0.15):
        b.tube("steel", (x - 0.1, py, 0), (x + 0.1, py, 0), pr + 0.13, 32 if fine else 16)
    for x in (6.8, 9.4):
        if x < pe:
            b.box("concrete", (x, 0.28, 0), (0.9, 0.34, 2.0))
    if state != "destroyed":
        b.box("paint", (12.35, 1.3, 0), (0.85, 2.4, 2.2)); b.box("steel", (12.82, 1.37, 0), (0.1, 1.9, 1.9))
    else:
        b.sweep("galv", [(9.0, py, 0), (9.7, py - 0.05, 0.2), (10.5, py - 0.3, 0.7)], pr, 20)
        b.disc("rust", (9.0, py, 0), pr * 0.9, (-1, 0, 0), seg=20)
    b.box("concrete_dark", (10.2, 0.06, 0), (6.4, 0.12, 4.4))
    return c


def tank_liquid(state, lod, seed):
    R = 9.1
    c = Ctx(state, lod, seed, breach=(-1.0, 6.0, -8.0, 3.2), ledges=[(9.83, 3.4, 0.95), (8.75, 1.1, 0.6), (5.17, 1.0, 0.5), (0.305, 1.2, 0.6)], ao_rings=[(9.83, 1.4, 0.35)], ground_h=2.5)
    p = dict(R=R, y0=0.305, y1=9.83, breach_deg=250, welds=[1.84, 5.17, 8.75], diamonds=[(200, 3.0, 4.4, 1.5), (20, 3.0, 4.4, 1.5)], ids=[(300, 5.6, 6.9, 2.4)],
             belt=(6.2, 8.4), tint=(8.9, 9.7), tint_dome=(8.7, 10.35, 7.3, 10.7), beads=18, id_digits=(1, 2),
             lower=[("concrete", [(10.06, 0.0), (9.906, 0.305), (9.3, 0.305)], 2.0)],
             lid=[(R, 9.83), (8.4, 10.59), (4.2, 10.98), (0.0, 11.35)], hatch=(1.5, 11.30, 11.45), catwalk=None, ladder_deg=None, lid_rail=(8.0, 10.65))
    round_tank(c, p)
    b = c.b
    # stair tower on +z and the pipe bridge up to the roof's crown
    if state != "destroyed":
        sk = None
        b.box("paint", (0, 4.95, 8.76), (2.29, 9.9, 1.53))
        b.box("galv", (0, 9.95, 8.76), (2.5, 0.12, 1.75))
        c.decal_wall("hatch", (0, 0, 9.55), (1, 0, 0), 1.3, 0.3, 2.4, (0, 0, 1))
        ax = unit(np.array([0, 12.57 - 10.5, -(10.29 - 0.0) + 0.0]))
        dirv = unit(np.array([0, 11.2 - 10.4, -1.0 * 8.5]))
        p0 = np.array([0, 10.4, 9.0]); p1 = np.array([0, 12.2, -1.9])
        mid = (p0 + p1) / 2; L = np.linalg.norm(p1 - p0)
        d = unit(p1 - p0); side = np.array([1.0, 0, 0]); n = unit(np.cross(d, side))
        b.box("galv", mid + n * 0.0, (1.1, 1.3, L), np.stack([side, n, d], 1))
        b.box("steel", mid + n * 0.7, (1.5, 0.08, L), np.stack([side, n, d], 1))
        if state == "damaged":
            pass
    else:
        b.box("paint", (0, 1.3, 8.9), (2.29, 2.6, 1.53))
    return c


def tank_water(state, lod, seed):
    R, cz = 2.65, 0.89
    c = Ctx(state, lod, seed, breach=(1.0, 6.5, cz + 2.0, 1.6), ledges=[(8.83, 2.0, 0.9), (6.29, 0.9, 0.5), (4.44, 1.0, 0.7)], ao_rings=[(4.44, 1.0, 0.5)], ground_h=2.0)
    b = c.b
    fine = lod == 0
    legs = [(-2.585, -2.556), (2.585, -2.556), (-2.585, 3.475), (2.585, 3.475)]
    if state == "destroyed":
        p = dict(R=R, cz=cz, y0=0.3, y1=4.4, breach_deg=90, welds=[2.0], beads=8, belt=None, tint=None,
                 lower=[], lid=[(R, 4.4), (2.1, 4.9), (0.0, 5.0)], hatch=None, catwalk=None, ladder_deg=None, lid_rail=None)
        round_tank(c, p)
        for (x, z) in legs:
            h = c.rng.uniform(0.5, 1.5)
            b.box("rust", (x, h / 2, z), (0.3, h, 0.3))
        b.box("steel", (0, 0.2, cz + 3.0), (5.4, 0.3, 0.3), axis_angle(np.array([0, 1.0, 0]), 0.5))
        c.decal_ground("soot", (0, cz), 11, 11, 0.0, y=0.045)
        return c
    # the open stand: four angle legs, girts, head beam, deck
    for (x, z) in legs:
        b.box("steel", (x, 2.2, z), (0.3, 4.4, 0.3))
        b.box("steel", (x + (0.12 if x < 0 else -0.12), 2.2, z), (0.08, 4.4, 0.32))
    gy = (0.88, 1.55)
    for yy in (1.2, 3.9):
        for (a, bq) in ((0, 1), (2, 3), (0, 2), (1, 3)):
            pa, pb = legs[a], legs[bq]
            b.box("steel", ((pa[0] + pb[0]) / 2, yy, (pa[1] + pb[1]) / 2), (max(abs(pa[0] - pb[0]), 0.2), 0.32, max(abs(pa[1] - pb[1]), 0.2)))
    if fine or True:
        for (a, bq) in ((0, 1), (2, 3), (0, 2), (1, 3)):
            pa, pb = legs[a], legs[bq]
            for (y0_, y1_) in ((1.4, 3.8),):
                if state == "damaged" and a == 0 and bq == 1:
                    continue
                b.tube("steel", (pa[0], y0_, pa[1]), (pb[0], y1_, pb[1]), 0.04, 6)
                b.tube("steel", (pa[0], y1_, pa[1]), (pb[0], y0_, pb[1]), 0.04, 6)
    b.box("galv", (0, 4.32, 0.46), (5.82, 0.24, 6.68))
    b.box("steel", (0, 4.2, 0.46), (5.9, 0.12, 6.76))
    # the tank
    p = dict(R=R, cz=cz, y0=4.44, y1=8.83, breach_deg=90, welds=[6.29], diamonds=[(270, 6.9, 7.9, 1.0)], ids=[(90, 7.3, 8.3, 1.4)], beads=8, id_digits=(0, 4),
             belt=(5.0, 5.8), tint=(8.0, 8.7), tint_dome=(2.6, 8.9, 2.2, 9.28),
             lower=[("galv", [(1.9, 4.3), (R, 4.44)], 1.5)], lid=[(R, 8.83), (2.11, 9.37), (1.0, 9.5), (0.0, 9.55)], hatch=None, catwalk=None, ladder_deg=None, lid_rail=None)
    round_tank(c, p)
    # ladder at z = -4.06 to the deck and past it
    if state != "destroyed":
        top = 5.6 if state == "damaged" else 9.0
        for sx in (-0.25, 0.25):
            b.tube("steel", (sx, 0.0, -4.06), (sx, top, -4.06), 0.03, 6)
        for k in range(int(top / (0.35 if fine else 0.8))):
            b.tube("steel", (-0.25, 0.3 + k * (0.35 if fine else 0.8), -4.06), (0.25, 0.3 + k * (0.35 if fine else 0.8), -4.06), 0.02, 5, caps=False)
        b.tube("steel", (-0.25, 4.4, -4.06), (-0.25, 4.4, -2.9), 0.03, 6)
        b.tube("steel", (0.25, 4.4, -4.06), (0.25, 4.4, -2.9), 0.03, 6)
    return c


# ====================================================================================================== grain store
def grain(state, lod, seed):
    c = Ctx(state, lod, seed, breach=(2.0, 11.0, -4.1, 3.2), ledges=[(15.1, 2.5, 0.9), (10.21, 2.0, 0.7)], ao_rings=[(10.21, 1.4, 0.4)], ground_h=2.5)
    b = c.b
    fine = lod == 0
    x0, x1, z0, z1, zb = -4.17, 12.68, -4.13, 0.38, 4.13
    W = x1 - x0
    hh = 10.21
    thick = 0.1
    cell = 0.5 if fine else 0.9
    # silos (true round, were hexagons): four, centres z 2.19
    for k, sx in enumerate((-2.03, 2.16, 6.35, 10.54)):
        if state == "destroyed":
            ys = np.unique(np.r_[np.linspace(0, 5.5, 12)])
            hs = 4.0 + 2.5 * c.rng.random()
            rr = 2.0
            keep = lambda t, y, hs=hs, sx=sx: hs + 1.1 * np.sin(np.asarray(t) * 4 + sx) + 0.5 * np.sin(np.asarray(t) * 11) - np.asarray(y)
            b.cut_surface("paint", lambda yy: np.full_like(yy, rr), np.unique(np.r_[np.linspace(0, 6, 24)]), 48 if fine else 28, keep, cx=sx, cz=2.19, uref=uref(rr, 2.0), thickness=0.08, disp=lambda t, y, kk: np.clip(1 - kk / 0.4, 0, 1) ** 2 * 0.15)
            b.disc("interior", (sx, 0.06, 2.19), 1.9, seg=28)
            continue
        if state == "damaged" and k == 1:
            ys = np.unique(np.r_[np.linspace(0, 10.21, 16), np.linspace(5.5, 10.21, 24)])
            thc = math.radians(270)
            def keep(t, y, thc=thc):
                u = ((np.asarray(t) - thc + math.pi) % TAU - math.pi) * 2.0
                g = np.sqrt((u / 1.1) ** 2 + ((np.asarray(y) - 8.2) / 1.7) ** 2)
                return (g - (1 + 0.15 * np.sin(5 * np.arctan2(np.asarray(y) - 8.2, u) + 1))) * 1.0
            b.cut_surface("paint", lambda yy: np.full_like(yy, 2.0), ys, 56 if fine else 28, keep, cx=sx, cz=2.19, uref=uref(2.0, 2.0), thickness=0.08,
                          disp=lambda t, y, kk: np.clip(1 - kk / 0.4, 0, 1) ** 2 * 0.15)
            b.revolve("interior", [(1.92, y) for y in np.linspace(0, 10.21, 10)], 28, cx=sx, cz=2.19, flip=True, uref=uref(1.9, 2.0))
        else:
            b.revolve("paint", [(2.0, y) for y in np.linspace(0, 10.21, 14)], 56 if fine else 28, cx=sx, cz=2.19, uref=uref(2.0, 2.0))
        b.revolve("galv", [(2.05, 10.21), (1.0, 10.9), (0.0, 11.2)], 28, cx=sx, cz=2.19, uref=uref(2.0, 1.5))
        for yy in (2.0, 5.0, 8.4):
            c.ring("galv", yy - 0.05, yy + 0.05, 2.0, 0.07, sx, 2.19, 28)
        c.decal_rev("streak_a", 1.2 + k, 1.4, 6.0, 10.1, 2.0, sx, 2.19, off=0.04)
    c.b.disc("concrete", (0, 0.08, 0.2), 0.01, seg=4)
    # the hall: front wall, side walls, upper back block, mono-pitch roof 15.16 (front) -> 12.17 (back)
    keepf = torn_keep(state, W, 15.1, c.rng, centre=(0.62, 0.45), size=(0.17, 0.3), ridge_lo=0.2, ridge_hi=0.55)
    thickf = 0.12 if keepf else 0.0
    if state != "destroyed":
        panel(c, "paint", (x0, 0, z0), (1, 0, 0), W, (0, 1, 0), 15.16, (0, 0, -1), keep=keepf, thick=thickf, cell=cell, disp=jag_disp(15.1) if keepf else None)
        panel(c, "paint", (x0, 0, z0), (0, 0, 1), z1 - z0, (0, 1, 0), 13.7, (-1, 0, 0))
        panel(c, "paint", (x1, 0, z0), (0, 0, 1), z1 - z0, (0, 1, 0), 13.7, (1, 0, 0))
        panel(c, "paint", (x0, hh, z1), (1, 0, 0), W, (0, 1, 0), 2.0, (0, 0, 1))
        panel(c, "paint", (x0, hh, z1), (0, 0, 1), zb - z1, (0, 1, 0), 3.2, (-1, 0, 0))
        panel(c, "paint", (x1, hh, z1), (0, 0, 1), zb - z1, (0, 1, 0), 3.2, (1, 0, 0))
        panel(c, "paint", (x0, hh, zb), (1, 0, 0), W, (0, 1, 0), 2.0, (0, 0, 1))
        # roof slab, slightly tilted plane
        ctr = np.array([(x0 + x1) / 2, (15.16 + 12.17) / 2 + 0.07, 0.0])
        slope = np.array([0, 12.17 - 15.16, zb - z0])
        if state == "intact":
            slab(c, "corrugated", ctr, (1, 0, 0), slope, W + 0.5, np.linalg.norm(slope) + 0.4, 0.14)
            for k in range(7 if fine else 0):
                xr = x0 + 0.3 + k * (W - 0.6) / 6
                b.box("galv", ctr + np.array([xr - ctr[0], 0.18 - 0.0, 0]), (0.1, 0.1, np.linalg.norm(slope)), np.stack([np.array([1.0, 0, 0]), unit(np.cross(slope, (1, 0, 0))), unit(slope)], 1))
        else:
            # the roof with a torn corner: half a slab and a hanging sheet
            slab(c, "corrugated", ctr + np.array([-W * 0.18, 0, 0]), (1, 0, 0), slope, W * 0.62, np.linalg.norm(slope) + 0.4, 0.14)
            sl = unit(slope)
            hang = np.array([x1 - 0.2 * W + 0.7, 13.3, 1.5])
            Rm = axis_angle(np.array([1.0, 0, 0]), 0.9)
            slab(c, "corrugated", hang, (1, 0, 0), Rm @ slope, W * 0.3, 5.0, 0.12)
        # doors: two 4.8 x 4.2 m recessed doors with hoods
        for dx in (-1.2, 4.0):
            c.decal_wall("hatch", (dx + 2.4, 0, z0), (1, 0, 0), 4.8, 0.0, 4.2, (0, 0, -1), off=0.04)
            b.box("steel", (dx + 2.4, 4.35, z0 - 0.25), (5.2, 0.25, 0.6))
        b.box("concrete", ((x0 + x1) / 2, 0.15, z0 - 0.15), (W + 0.4, 0.3, 0.3))
        for xv in np.linspace(x0 + 1.0, x1 - 1.0, 6 if fine else 3):
            c.decal_wall("panel", (xv, 0, z0), (1, 0, 0), 1.0, 6.6, 7.8, (0, 0, -1), off=0.04) if False else None
        # tint band under the roof edge and a hazard sill
        panel(c, "trim", (x0, 12.1, z0 - 0.02), (1, 0, 0), W, (0, 1, 0), 1.2, (0, 0, -1), keep=None, band=6, col=(1, 0, 0))
        b.revolve("steel", [(0.0, 0.0), (0.0, 0.0)], 4) if False else None
    else:
        # wreck: front wall as a jagged ridge, side wall stubs, collapsed roof lying across the hall
        panel(c, "paint", (x0, 0, z0), (1, 0, 0), W, (0, 1, 0), 15.16, (0, 0, -1), keep=torn_keep("destroyed", W, 7.0, c.rng, ridge_lo=0.3, ridge_hi=0.85), thick=0.1, cell=cell)
        panel(c, "paint", (x0, 0, z0), (0, 0, 1), z1 - z0, (0, 1, 0), 4.0, (-1, 0, 0), keep=torn_keep("destroyed", z1 - z0, 4.0, c.rng, ridge_lo=0.3, ridge_hi=0.9), thick=0.1, cell=cell)
        panel(c, "paint", (x1, 0, zb), (-1, 0, 0), W, (0, 1, 0), 4.0, (0, 0, 1), keep=torn_keep("destroyed", W, 4.0, c.rng, ridge_lo=0.3, ridge_hi=0.9), thick=0.1, cell=cell)
        panel(c, "paint", (x1, 0, z0), (0, 0, 1), z1 - z0, (0, 1, 0), 4.0, (1, 0, 0), keep=torn_keep("destroyed", z1 - z0, 4.0, c.rng, ridge_lo=0.3, ridge_hi=0.9), thick=0.1, cell=cell)
        for k in range(3):
            Rm = axis_angle(np.array([1.0, 0, 0]), c.rng.uniform(-0.5, 0.5)) @ axis_angle(np.array([0, 1.0, 0]), c.rng.uniform(-0.4, 0.4))
            slab(c, "corrugated", (x0 + (k + 0.5) * W / 3, 1.2 + k * 0.4, -1.0 + k), Rm @ np.array([1.0, 0, 0]), Rm @ np.array([0, 0.1, 1.0]), W / 3 + 0.6, 7.0, 0.14)
        for k in range(10):
            b.box("rust", (x0 + c.rng.random() * W, 0.3, z0 + c.rng.random() * 8), (c.rng.uniform(0.5, 2), 0.4, c.rng.uniform(0.5, 1.5)), axis_angle(np.array([0, 1.0, 0]), c.rng.random() * 3))
        c.decal_ground("soot", (4.2, 0.0), 24, 18, 0.0, y=0.045)
        c.decal_ground("oil", (-3.0, -6.0), 7, 7, 0.4, y=0.05)
    return c


# ======================================================================================================== sheds
def roof_planes(c, mat, planes, state, thick=0.12):
    """planes: [(centre, ax_u, ax_v, L, W)] slabs; damaged tears one, destroyed lays them on the ground."""
    b = c.b
    for k, (ctr, au, av, L, Wd) in enumerate(planes):
        if state == "intact":
            slab(c, mat, ctr, au, av, L, Wd, thick)
        elif state == "damaged":
            if k == len(planes) // 2:
                # a torn sheet: the slab with a bite out (two boxes) and a curled flap
                slab(c, mat, ctr + unit(av) * Wd * 0.18, au, av, L, Wd * 0.62, thick)
                fl = axis_angle(np.cross(au, av), 0.7)
                slab(c, mat, ctr - unit(av) * Wd * 0.38 + np.array([0, 0.5, 0]), au, fl @ np.asarray(av, float), L * 0.55, Wd * 0.3, thick)
            else:
                slab(c, mat, ctr, au, av, L, Wd, thick)
        else:
            Rm = axis_angle(np.array([1.0, 0, 0]), c.rng.uniform(-0.5, 0.5)) @ axis_angle(np.array([0, 1.0, 0]), c.rng.uniform(-0.6, 0.6))
            g = np.array([ctr[0] * 0.8 + c.rng.uniform(-0.8, 0.8), 0.25 + 0.3 * k, ctr[2] * 0.8 + c.rng.uniform(-0.8, 0.8)])
            slab(c, mat, g, Rm @ np.array([1.0, 0, 0]), Rm @ np.array([0, 0, 1.0]) * 1.0, L, Wd, thick)


def shed_a(state, lod, seed):
    c = Ctx(state, lod, seed, breach=(3.85, 2.2, 0.0, 2.2), ledges=[(3.46, 2.0, 0.9), (1.17, 0.9, 0.6)], ao_rings=[(3.46, 1.0, 0.4)], ground_h=1.5)
    b = c.b
    fine = lod == 0
    x0, x1, z0, z1, h = -3.85, 3.85, -5.79, 5.4, 3.46
    ln = z1 - z0
    cell = 0.45 if fine else 0.9
    kA = torn_keep(state, ln, h, c.rng, centre=(0.5, 0.55), size=(0.2, 0.34), ridge_lo=0.2, ridge_hi=0.55)
    kB = torn_keep("destroyed" if state == "destroyed" else "intact", ln, h, c.rng, ridge_lo=0.2, ridge_hi=0.6)
    # side walls (the damaged one is breached on +x), end walls with roller doors
    panel(c, "corrugated", (x1, 0, z0), (0, 0, 1), ln, (0, 1, 0), h, (1, 0, 0), keep=kA, thick=0.08, cell=cell, swap=False, disp=jag_disp(h) if kA else None)
    panel(c, "corrugated", (x0, 0, z1), (0, 0, -1), ln, (0, 1, 0), h, (-1, 0, 0), keep=kB, thick=0.08, cell=cell)
    for zz, nz in ((z0, -1), (z1, 1)):
        d = (1, 0, 0) if nz < 0 else (-1, 0, 0)
        sx = x0 if nz < 0 else x1
        kk = torn_keep("destroyed", x1 - x0, h, c.rng, ridge_lo=0.2, ridge_hi=0.6) if state == "destroyed" else None
        panel(c, "corrugated", (sx, 0, zz), d, x1 - x0, (0, 1, 0), h, (0, 0, nz), keep=kk, thick=0.08, cell=cell)
        if state != "destroyed":
            c.decal_wall("hatch", (0.12, 0, zz), (1, 0, 0), 3.3, 0.0, 2.8, (0, 0, nz), off=0.04)
            b.box("steel", (0.12, 2.95, zz + nz * 0.15), (3.8, 0.3, 0.3))
            b.tube("steel", (0.12, 3.2, zz + nz * 0.15), (0.12, 3.2, zz + nz * 0.9), 0.04, 6)
    # concrete plinth and a tint band
    b.box("concrete", (0, 0.3, 0), (7.9, 0.6, 11.0)) if state != "destroyed" else b.box("concrete", (0, 0.3, 0), (7.9, 0.6, 11.0))
    if state != "destroyed":
        panel(c, "trim", (x1 + 0.02, 2.55, z0), (0, 0, 1), ln, (0, 1, 0), 0.7, (1, 0, 0), band=6, col=(1, 0, 0), keep=None) if state == "intact" else None
        for xs in (-2.57, 0.0, 2.57):
            pass
        planes = []
        for sgn in (-1, 1):
            for rx in (-2.57, 0.0, 2.57):
                cx = rx + sgn * 0.64 * 1.0
                a = unit(np.array([0, 4.2 - 3.46, 0]) + np.array([-sgn * 1.28, 0, 0])) if False else None
        # three gables along z: ridges at x = -2.57, 0, 2.57 at 4.2 m, valleys at +-1.28 at 3.46 m
        ridges = (-2.57, 0.0, 2.57)
        for rx in ridges:
            for sgn in (-1, 1):
                xs = rx + sgn * 1.28
                xs = min(max(xs, x0), x1)
                if abs(xs - rx) < 0.3:
                    continue
                cx_ = (rx + xs) / 2
                dxv = xs - rx
                top = np.array([dxv, 3.46 - 4.2, 0.0])
                if state == "destroyed":
                    continue
                if state == "damaged" and rx == 0.0 and sgn == 1:
                    continue
                slab(c, "corrugated", (cx_, (4.2 + 3.46) / 2 + 0.06, 0.0), top, (0, 0, 1), np.linalg.norm(top) + 0.2, ln + 0.8, 0.1)
        if state == "damaged":
            slab(c, "corrugated", (0.64, 4.1, 1.8), (1.28, -0.74, 0), (0, 0, 1), 1.5, 5.0, 0.1)
            slab(c, "corrugated", (1.4, 4.4, -3.8), (1.28, 0.2, 0), (0.5, 0, 1), 1.5, 3.0, 0.1)
        # gutters, corner trims, lamps
        b.box("galv", (x1 + 0.1, 3.4, 0), (0.2, 0.15, ln + 0.8)); b.box("galv", (x0 - 0.1, 3.4, 0), (0.2, 0.15, ln + 0.8))
        for zz, nz in ((z0, -1), (z1, 1)):
            b.tube("steel", (0.12, 3.9, zz + nz * 0.1), (0.12, 3.9, zz + nz * 0.8), 0.03, 6)
    else:
        planes = [((-2.0, 0, 1.0), (1, 0, 0), (0, 0, 1), 3.0, 8.0), ((1.8, 0, -1.5), (1, 0, 0), (0, 0, 1), 3.0, 6.0), ((0.3, 0, 3.0), (1, 0, 0), (0, 0, 1), 3.2, 4.0)]
        roof_planes(c, "corrugated", planes, "destroyed")
        for k in range(9):
            b.box("rust", (c.rng.uniform(-3.5, 3.5), 0.25, c.rng.uniform(-5, 5)), (c.rng.uniform(0.4, 1.4), 0.4, c.rng.uniform(0.4, 1.2)), axis_angle(np.array([0, 1.0, 0]), c.rng.random() * 3))
        c.decal_ground("soot", (0, 0), 13, 17, 0.0, y=0.045)
    if state != "destroyed":
        for sx, sz in ((x0, z0), (x1, z0), (x0, z1), (x1, z1)):
            b.box("steel", (sx, h / 2 + 0.3, sz), (0.2, h, 0.2))
            b.tube("galv", (sx + (0.18 if sx < 0 else -0.18), 0.6, sz), (sx + (0.18 if sx < 0 else -0.18), 3.3, sz), 0.05, 6)
        for zz in (-3.2, -1.1, 1.1, 3.2) if fine else ():
            for wx, nx in ((x1, 1), (x0, -1)):
                if state == "damaged" and nx == 1 and abs(zz) < 2.0:
                    continue
                b.box("steel", (wx + nx * 0.03, 2.2, zz), (0.1, 1.0, 1.7)); b.box("galv", (wx + nx * 0.05, 2.2, zz), (0.08, 0.8, 1.5))
                b.box("steel", (wx + nx * 0.1, 1.68, zz), (0.2, 0.08, 1.9))
        for rx in (-2.57, 0.0, 2.57):
            for k in range(3 if fine else 0):
                zz = -4.0 + k * 4.0
                b.revolve("galv", [(0.28, 4.2), (0.28, 4.55), (0.38, 4.62), (0.0, 4.75)], 12, cx=rx, cz=zz, uref=1.0)
    # run-off decals on the long wall
    if state != "destroyed":
        for k, zz in enumerate(np.linspace(-4.5, 4.5, 5)):
            if state == "damaged" and abs(zz) < 1.5:
                continue
            c.decal_wall("streak_a" if k % 2 else "streak_b", (x1, 0, zz), (0, 0, 1), 2.0, 0.6, 3.4, (1, 0, 0), off=0.03)
    return c


def shed_b(state, lod, seed):
    c = Ctx(state, lod, seed, breach=(3.42, 2.2, -4.0, 2.2), ledges=[(4.01, 2.0, 0.9), (1.18, 0.9, 0.6)], ao_rings=[(4.01, 1.0, 0.4)], ground_h=1.5)
    b = c.b
    fine = lod == 0
    x0, x1, z0, z1, h = -3.12, 3.12, -11.43, 3.26, 4.01
    ln = z1 - z0
    cell = 0.5 if fine else 1.0
    kA = torn_keep(state, ln, h, c.rng, centre=(0.45, 0.5), size=(0.16, 0.34), ridge_lo=0.2, ridge_hi=0.55)
    panel(c, "corrugated", (x1, 0, z0), (0, 0, 1), ln, (0, 1, 0), h, (1, 0, 0), keep=kA, thick=0.08, cell=cell, disp=jag_disp(h) if kA else None)
    kB = torn_keep("destroyed" if state == "destroyed" else "intact", ln, h, c.rng, ridge_lo=0.2, ridge_hi=0.6)
    panel(c, "corrugated", (x0, 0, z1), (0, 0, -1), ln, (0, 1, 0), h, (-1, 0, 0), keep=kB, thick=0.08, cell=cell)
    for zz, nz, sx, d in ((z0, -1, x0, (1, 0, 0)), (z1, 1, x1, (-1, 0, 0))):
        kk = torn_keep("destroyed", x1 - x0, h, c.rng, ridge_lo=0.2, ridge_hi=0.6) if state == "destroyed" else None
        panel(c, "corrugated", (sx, 0, zz), d, x1 - x0, (0, 1, 0), h, (0, 0, nz), keep=kk, thick=0.08, cell=cell)
    b.box("concrete", (0, 0.1, (z0 + z1) / 2), (6.4, 0.2, ln + 0.2))
    if state != "destroyed":
        # three sawtooth bays 4.9 m long: roofs fall from 5.33 (clerestory, +z side) to 4.01
        for k in range(3):
            zb0 = z0 + 0.4 + k * 4.9
            zb1 = zb0 + 4.9
            top = np.array([0, 4.01 - 5.33, 4.9])
            if state == "damaged" and k == 1:
                slab(c, "corrugated", (0, 4.67 + 0.45, (zb0 + zb1) / 2 + 1.4), (1, 0, 0), top * 0.5 + np.array([0, 0.3, 0]), 6.4, 4.0, 0.1)
                continue
            slab(c, "corrugated", (0, (5.33 + 4.01) / 2 + 0.06, (zb0 + zb1) / 2), (1, 0, 0), top, 6.5, np.linalg.norm(top) + 0.1, 0.1)
            # clerestory glazing face
            b.box("steel", (0, 4.5, zb1 + 0.0), (6.3, 1.4, 0.1))
            c.decal_wall("hatch", (0, 0, zb1 + 0.06), (1, 0, 0), 5.0, 3.9, 5.2, (0, 0, 1), off=0.0)
        for k, zz in enumerate((z0 + 2.6, z0 + 7.5, z0 + 12.4)):
            c.decal_wall("hatch", (x0, 0, zz), (0, 0, 1), 3.3, 1.18, 3.6, (-1, 0, 0), off=0.05)
            b.box("concrete", (x0 - 0.35, 0.6, zz), (0.6, 1.18, 3.7))
            b.box("steel", (x0 - 0.12, 3.9, zz), (0.25, 0.5, 3.8))
            for dz in (-1.8, 1.8):
                b.box("steel", (x0 - 0.06, 2.4, zz + dz), (0.12, 2.4, 0.14))
        for k in range(3):
            zb0 = z0 + 0.4 + k * 4.9
            for xr in (np.linspace(-2.6, 2.6, 5) if fine else ()):
                b.box("galv", (xr, 4.67 + 0.14, zb0 + 2.45), (0.08, 0.08, 5.0), np.stack([np.array([1.0, 0, 0]), unit(np.cross([0, 4.01 - 5.33, 4.9], [1, 0, 0])), unit(np.array([0, 4.01 - 5.33, 4.9]))], 1))
        for sx, sz in ((x0, z0), (x1, z0), (x0, z1), (x1, z1)):
            b.box("steel", (sx, h / 2, sz), (0.2, h, 0.2))
        panel(c, "trim", (x1 + 0.02, 3.2, z0), (0, 0, 1), ln, (0, 1, 0), 0.7, (1, 0, 0), band=6, col=(1, 0, 0), keep=None) if state == "intact" else None
        for k, zz in enumerate(np.linspace(-9.0, 1.5, 6)):
            if state == "damaged" and abs(zz + 4.5) < 2.0:
                continue
            c.decal_wall("streak_a" if k % 2 else "streak_b", (x1, 0, zz), (0, 0, 1), 2.0, 0.6, 3.9, (1, 0, 0), off=0.03)
    else:
        planes = [((-1.0, 0, -8.0), (1, 0, 0), (0, 0, 1), 3.2, 5.5), ((1.0, 0, -2.0), (1, 0, 0), (0, 0, 1), 3.2, 5.0), ((0, 0, 1.5), (1, 0, 0), (0, 0, 1), 3.0, 3.5)]
        roof_planes(c, "corrugated", planes, "destroyed")
        for k in range(9):
            b.box("rust", (c.rng.uniform(-3.0, 3.0), 0.25, c.rng.uniform(-10, 2)), (c.rng.uniform(0.4, 1.4), 0.4, c.rng.uniform(0.4, 1.2)), axis_angle(np.array([0, 1.0, 0]), c.rng.random() * 3))
        c.decal_ground("soot", (0, (z0 + z1) / 2), 12, 20, 0.0, y=0.045)
    return c


def shed_c(state, lod, seed):
    c = Ctx(state, lod, seed, breach=(2.24, 4.2, -1.7, 1.6), ledges=[(5.0, 1.8, 0.9), (2.54, 0.9, 0.6)], ao_rings=[(2.54, 1.5, 0.6)], ground_h=1.5)
    b = c.b
    fine = lod == 0
    x0, x1, z0, z1 = -2.24, 2.24, -3.34, 0.10
    ln = z1 - z0
    deck = 2.54
    posts = [(-2.09, -3.20), (2.09, -3.20), (-2.09, -0.04), (2.09, -0.04)]
    for (px, pz) in posts:
        if state == "destroyed" and (px > 0):
            b.box("rust", (px, 0.5, pz), (0.25, 1.0, 0.25), axis_angle(np.array([0, 0, 1.0]), 0.4))
            continue
        b.box("steel", (px, deck / 2, pz), (0.25, deck, 0.25))
    if state != "destroyed":
        for (a, bq) in ((0, 1), (2, 3), (0, 2), (1, 3)):
            pa, pb = posts[a], posts[bq]
            b.tube("steel", (pa[0], 0.3, pa[1]), (pb[0], deck - 0.3, pb[1]), 0.05, 6)
            b.tube("steel", (pa[0], deck - 0.3, pa[1]), (pb[0], 0.3, pb[1]), 0.05, 6)
        b.box("steel", (0, deck - 0.12, (z0 + z1) / 2), (4.7, 0.24, ln + 0.3))
    else:
        b.box("rust", (-0.5, 0.35, -1.7), (4.6, 0.3, 3.5), axis_angle(np.array([0, 0, 1.0]), 0.1))
    # cabin: board walls, -x 5.00 m to +x 5.98 m under a mono-pitch roof
    cell = 0.35 if fine else 0.7
    hx0, hx1 = 5.00, 5.98
    kA = torn_keep(state, ln, 3.0, c.rng, centre=(0.5, 0.5), size=(0.3, 0.3), ridge_lo=0.25, ridge_hi=0.6)
    if state != "destroyed":
        panel(c, "corrugated", (x1, deck, z0), (0, 0, 1), ln, (0, 1, 0), hx1 - deck, (1, 0, 0), keep=kA, thick=0.06, cell=cell, disp=jag_disp(3.0) if kA else None)
        panel(c, "corrugated", (x0, deck, z1), (0, 0, -1), ln, (0, 1, 0), hx0 - deck, (-1, 0, 0), thick=0.06)
        panel(c, "corrugated", (x0, deck, z0), (1, 0, 0), x1 - x0, (0, 1, 0), 2.6, (0, 0, -1))
        panel(c, "corrugated", (x1, deck, z1), (-1, 0, 0), x1 - x0, (0, 1, 0), 2.6, (0, 0, 1))
        c.decal_wall("hatch", (-0.9, 0, z1), (1, 0, 0), 1.28, deck + 0.0, deck + 2.15, (0, 0, 1), off=0.04)
        # mono-pitch roof sheet
        top = np.array([x1 - x0, hx1 - hx0, 0.0])
        if state == "intact":
            slab(c, "galv", (0, (hx0 + hx1) / 2 + 0.06, (z0 + z1) / 2), top, (0, 0, 1), np.linalg.norm(top) + 0.8, ln + 0.9, 0.08)
        else:
            slab(c, "galv", (0, (hx0 + hx1) / 2 + 0.06, (z0 + z1) / 2 + 0.7), top, (0, 0, 1), np.linalg.norm(top) + 0.8, ln * 0.55, 0.08)
            slab(c, "galv", (1.2, 4.2, -2.8), (1, 0.6, 0), (0, 0, 1), 1.8, ln * 0.4, 0.08)
        panel(c, "trim", (x1 + 0.02, deck + 1.9, z0), (0, 0, 1), ln, (0, 1, 0), 0.6, (1, 0, 0), band=6, col=(1, 0, 0)) if state == "intact" else None
    else:
        panel(c, "corrugated", (x0, deck, z1), (0, 0, -1), ln, (0, 1, 0), 1.0, (-1, 0, 0), keep=torn_keep("destroyed", ln, 1.0, c.rng), thick=0.06, cell=0.4)
        for k in range(8):
            b.box("rust", (c.rng.uniform(-2.5, 2.5), 0.2, c.rng.uniform(-3.6, 0.6)), (c.rng.uniform(0.4, 1.2), 0.3, c.rng.uniform(0.3, 1.0)), axis_angle(np.array([0, 1.0, 0]), c.rng.random() * 3))
        slab(c, "galv", (0.3, 0.8, -1.8), (1, 0.3, 0), (0, 0.1, 1), 4.5, 4.0, 0.08)
        c.decal_ground("soot", (0, -1.6), 8, 9, 0.0, y=0.045)
    if state != "destroyed":
        for sx, sz in ((x0, z0), (x1, z0), (x0, z1), (x1, z1)):
            b.box("steel", (sx, deck + 1.5, sz), (0.14, 3.0, 0.14))
        b.box("steel", (-0.9, deck + 1.1, z1 + 0.06), (1.5, 2.3, 0.08)); b.box("steel", (-0.9, deck + 0.04, z1 + 0.14), (1.6, 0.08, 0.3))
        b.box("galv", (x0 - 0.04, deck + 1.9, -1.6), (0.1, 0.8, 1.0)); b.box("steel", (x0 - 0.08, deck + 1.45, -1.6), (0.2, 0.08, 1.2))
        if fine:
            for xr in np.linspace(-2.4, 2.4, 6):
                b.box("galv", (xr, (hx0 + hx1) / 2 + 0.0 + 0.16 + (xr / 2.24) * (hx1 - hx0) / 2, (z0 + z1) / 2), (0.07, 0.07, ln + 0.9), axis_angle(np.array([0, 0, 1.0]), math.atan2(hx1 - hx0, x1 - x0)))
    # stair: nine 39 cm treads between two stringers, z 0.1 -> 3.69
    if state != "destroyed":
        for sx in (-0.63, 0.63):
            b.tube("steel", (sx, deck, 0.1), (sx, 0.0, 3.69), 0.05, 6)
        for k in range(9):
            b.box("grate", (0, deck - 0.28 * (k + 1), 0.1 + 0.4 * (k + 1)), (1.3, 0.05, 0.39))
    return c


MEMBERS = {
    "smallfueltank": (tank_small, "hex tank on a plinth with a riser, bounds x -3.41..3.75, z +-3.9, 8.6 m (tools/cad/smallfueltank_cad.py)"),
    "pipetank": (tank_pipe, "octagonal tank r 4.7 on a pedestal, pipe to x 12.78, 12.44 m (tools/cad/pipetank_cad.py)"),
    "liquidstorage": (tank_liquid, "decagonal tank 9.1 m, stair tower +z, roof bridge, 12.57 m (tools/cad/liquidstorage_cad.py)"),
    "watertower": (tank_water, "open four-leg stand, tank r 2.65 to 8.83, lid 9.37 m (tools/cad/watertower_cad.py)"),
    "grainstorage": (bld_sheds.grain, "hall x -4.17..12.68 with four silos, 15.16 m (tools/cad/grainstorage_cad.py)"),
    "civstoragea": (bld_sheds.shed_a, "7.7 x 11 m triple-gable shed, 4.2 m (tools/cad/civstoragea_cad.py)"),
    "civstorageb": (bld_sheds.shed_b, "sawtooth shed 6.2 x 14.7 m, 5.33 m (tools/cad/civstorageb_cad.py)"),
    "civstoragec": (bld_sheds.shed_c, "stilt cabin 4.5 x 3.4 m, 6.07 m (tools/cad/civstoragec_cad.py)"),
}


def build_member(app, out):
    fn, src = MEMBERS[app]
    info = {"app": app, "made_by": "tools/art/v3/bld_family.py", "source_dims": src, "states": {}}
    for si, state in enumerate(STATES):
        lods = [fn(state, lod, 3100 + si + (hash(app) & 0) + sum(map(ord, app))).b for lod in (0, 1)]
        name = app + ("" if state == "intact" else "_" + state)
        st = Builder.write_lods(out / f"{name}.glb", name, lods)
        P = np.vstack([v for s in lods[0].s.values() for v in s["P"]])
        info["states"][state] = {"tris_lod0": int(sum(st[0].values())), "tris_lod1": int(sum(st[1].values())), "lod_switch_m": LOD_M,
                                 "bounds_min": np.round(P.min(0), 2).tolist(), "bounds_max": np.round(P.max(0), 2).tolist()}
        print(app, state, info["states"][state]["tris_lod0"], info["states"][state]["tris_lod1"], info["states"][state]["bounds_min"], info["states"][state]["bounds_max"], flush=True)
    (out / f"{app}.v3.json").write_text(json.dumps(info, indent=1) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("app")
    ap.add_argument("--out", default=str(ROOT / "game/assets/v3/objects"))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    for app in (MEMBERS if a.app == "all" else [a.app]):
        build_member(app, out)


if __name__ == "__main__":
    main()
