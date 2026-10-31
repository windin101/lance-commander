#!/usr/bin/env python3
"""v3 civilian and city buildings (LANCE-39): the 2/4/6/8-storey city blocks (variants a, b, c), the single and two-storey civilian houses,
shacks, greenhouse, barracks and meeting hall. Footprints, heights and layouts from the Shared Source originals' meshes (game/tools/orig_top.gd,
orig_bounds.gd). Built on the industrial kit (bld_industry.py: dark detailed roofs, window grids, louvres, doors, bands).

    python3 -I tools/art/v3/bld_city.py <app>|all
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bld_hangars as H  # noqa: E402
import bld_industry as I  # noqa: E402
from bld_industry import (Ctx, V, TAU, axis_angle, shell, blk, blk2 as _blk2, roof2, fpanel, louvre, door, band, roll_door, barrel_roof, prism_roof,  # noqa: E402
                          setw, collapse, ROOT)

import bld_hangars_b as HB  # noqa: E402


def _city_windows(c, mat_wall, p0, dirv, L, h, normal, cols, rows, y0=1.0, y1=None, gx=0.5, gy=0.5, state_hole=None):
    """The city blocks' paired framed windows: bigger than the industrial ones (about 60 % of each cell)."""
    out = []
    for (a, b_, c_, d_) in I._win_orig(c, mat_wall, p0, dirv, L, h, normal, cols, rows, y0, y1, gx, gy, state_hole):
        cx, cy, w, hh = (a + c_) / 2, (b_ + d_) / 2, (c_ - a) * WFRAC[0], (d_ - b_) * WFRAC[1]
        out.append((cx - w, cy - hh, cx + w, cy + hh))
    return out


WFRAC = [0.34, 0.42]
FRAME_T = [0.16]
import bld_mesh as _BM  # noqa: E402
_quad = _BM.Builder.quad


def _quad_wglass(self, mat, *a, **k):
    """Facade window glass is the matte near-black, night-lit wglass material (a glossy glass mirrors the sky and reads pale from above)."""
    return _quad(self, "wglass" if mat == "glass" else mat, *a, **k)


_BM.Builder.quad = _quad_wglass
import bld_sheds as _SH  # noqa: E402
_grid_axes = _SH.grid_axes


def _grid_axes_mid(L, h, nu, holes=(), v_extra=(), u_extra=(), fine_v=None):
    """grid_axes plus a grid line through the middle of every hole: a hole whose corners are the only vertices on it can fall between samples and
    stay uncut (the upper rows of the 4-storey blocks were solid panels with frames drawn on them)."""
    mids_u = [(hh[0] + hh[2]) / 2 for hh in holes]
    mids_v = [(hh[1] + hh[3]) / 2 for hh in holes]
    return _grid_axes(L, h, nu, holes, tuple(v_extra) + tuple(mids_v), tuple(u_extra) + tuple(mids_u), fine_v)


STOREY = 3.55
FOOT = {2: (-10.0, 7.7, -7.7, 10.1), 4: (-10.1, 7.8, -10.8, 7.1), 6: (-6.9, 10.9, -10.7, 7.0), 8: (-7.4, 10.3, -7.5, 10.2)}
HEIGHT = {2: 7.8, 4: 14.2, 6: 21.3, 8: 28.4}


def heli_ring(c, cx, cz, r, y):
    """A roof marking: a pale ring with a cross (the originals' 6 and 8 storey roofs)."""
    if c.state == "destroyed":
        return
    b = c.b
    b.revolve("palepaint", [(r, y), (r - 0.35, y)], 24 if c.fine else 10, cx=cx, cz=cz, uref=2.0)
    b.box("palepaint", (cx, y + 0.01, cz), (r * 1.5, 0.03, 0.35))
    b.box("palepaint", (cx, y + 0.01, cz), (0.35, 0.03, r * 1.5))


def _wins(c, box, h, spec, main=False, y0=0.0):
    """Windows as exact rectangles: a solid wall slab, one dark-glass quad per window (matte wglass, flush 5 cm off the wall) inside four thin pale
    frame boxes that stand 10 cm proud (so the glass reads recessed). Regular spacing from the cols x rows of `spec` ({face: (cols, rows)}). LOD1
    keeps the glass and drops the frames. Nothing is cut out of the wall, so nothing can come out as a diamond."""
    if c.state == "destroyed":
        return
    b = c.b
    for key, (cols, rows) in spec.items():
        (px, pz), ud, n, L = I._face(key, *box)
        ud, n = V(ud, float), V(n, float)
        gx = max(0.9, L * 0.07)
        cw = (L - 2 * gx) / cols
        ch = (h - 1.8) / rows
        ww = min(cw * 0.5, 1.6)
        wh = min(ch * 0.55, 1.9)
        for i in range(cols):
            uc = gx + (i + 0.5) * cw
            for j in range(rows):
                vc = 0.9 + (j + 0.5) * ch
                if main and c.state == "damaged" and key == "+x" and abs(uc - L * 0.5) < min(L * 0.22, 3.0) + ww and abs(vc - h * 0.45) < h * 0.28 + 1.0:
                    continue
                ctr = V([px, y0 + vc, pz]) + ud * uc
                b.quad("wglass", ctr + n * 0.05, ud, V([0, 1.0, 0]), ww, wh, (0, 1, 1, 0), normal=tuple(n))
                if c.fine:
                    t = 0.1
                    for du, dv, sw, sh in ((-(ww / 2 + t / 2), 0.0, t, wh + 2 * t), (ww / 2 + t / 2, 0.0, t, wh + 2 * t), (0.0, wh / 2 + t / 2, ww, t), (0.0, -(wh / 2 + t / 2), ww, t)):
                        q = ctr + ud * du + V([0, dv, 0]) + n * 0.06
                        size = (sw, sh, 0.12) if abs(ud[0]) > 0.5 else (0.12, sh, sw)
                        b.box("palepaint", q, size)


def blk2(c, x0, x1, z0, z1, h, wall, y0=0.0, grids=None, **kw):
    """industrial blk2 with the windows made by _wins instead of holes cut through the wall."""
    _blk2(c, x0, x1, z0, z1, h, wall, y0=y0, grids=None, **kw)
    if grids:
        _wins(c, (x0, x1, z0, z1), h, grids, kw.get("main", False), y0)


def frames(c, box, h, cols, rows, faces=("+z", "-z", "+x", "-x"), y0=0.0, t=None):
    t = FRAME_T[0] if t is None else t
    """Pale window frames round the facade windows (the originals' white frames read at the RTS camera)."""
    if c.state == "destroyed" or not c.fine:
        return
    for key in faces:
        L = I._face(key, *box)[3]
        for (a, b_, c_, d_) in _city_windows(c, None, None, None, L, h, None, cols, rows, 1.0, h - 0.9):
            w, hh = c_ - a, d_ - b_
            fpanel(c, "palepaint", key, box, a - t, b_ - t, t, hh + 2 * t, y0, 0.09)
            fpanel(c, "palepaint", key, box, c_, b_ - t, t, hh + 2 * t, y0, 0.09)
            fpanel(c, "palepaint", key, box, a, b_ - t, w, t, y0, 0.09)
            fpanel(c, "palepaint", key, box, a, d_, w, t, y0, 0.09)


def pilasters(c, box, h, cols, mat="palepaint", w=0.5, every=1):
    """Vertical pale strips between window columns on all four faces."""
    if c.state == "destroyed" or not c.fine:
        return
    x0, x1, z0, z1 = box
    for key in ("-z", "+z", "-x", "+x"):
        L = I._face(key, *box)[3]
        for k in range(0, cols + 1, every):
            u = L * k / cols
            fpanel(c, mat, key, box, max(0.0, u - w / 2), 0.4, w, h - 0.8, 0.0, 0.07)


def rubble(c, box, h, n=18):
    """A collapsed block seen from above: a heap of charred slab chunks and wall pieces filling the footprint, two fallen floor slabs, rebar, soot."""
    if c.state != "destroyed":
        return
    b = c.b
    x0, x1, z0, z1 = box
    rng = c.rng
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    W, D = x1 - x0, z1 - z0
    for k in range(n if c.fine else n // 3):
        ph = max(0.0, 1.0 - 1.6 * math.hypot((rng.uniform(x0, x1) - cx) / W, 0))      # heaps peak toward the middle
        x = rng.uniform(x0 + 1.0, x1 - 1.0); z = rng.uniform(z0 + 1.0, z1 - 1.0)
        hh = min(h * 0.18, 1.2 + 2.4 * (1.0 - math.hypot((x - cx) / (W / 2), (z - cz) / (D / 2)) * 0.8))
        sz = (rng.uniform(1.4, 3.4), max(0.5, hh), rng.uniform(1.2, 3.0))
        b.box("concrete_dark" if k % 3 else "rust", (x, sz[1] / 2 + 0.1, z), sz,
              axis_angle(V([0, 1.0, 0]), rng.random() * 3.0) @ axis_angle(V([1.0, 0, 0]), rng.uniform(-0.35, 0.35)))
    for k in range(2):                                                                 # fallen floor slabs, leaning on the heap
        sx, sz_ = W * rng.uniform(0.35, 0.5), D * rng.uniform(0.3, 0.45)
        b.box("concrete", (cx + rng.uniform(-W * 0.15, W * 0.15), 1.5 + k * 0.7, cz + rng.uniform(-D * 0.15, D * 0.15)), (sx, 0.35, sz_),
              axis_angle(V([0, 1.0, 0]), rng.uniform(-0.6, 0.6)) @ axis_angle(V([1.0, 0, 0]), rng.uniform(-0.3, 0.3)) @ axis_angle(V([0, 0, 1.0]), rng.uniform(-0.3, 0.3)))
    for k in range(10 if c.fine else 3):
        a = V([rng.uniform(x0 + 1, x1 - 1), 1.0, rng.uniform(z0 + 1, z1 - 1)])
        b.tube("steel", a, a + V([rng.uniform(-1.5, 1.5), rng.uniform(1.0, 3.0), rng.uniform(-1.5, 1.5)]), 0.05, 4)
    c.decal_ground("soot", (cx, cz), W * 1.2, D * 1.2, 0.0, y=0.12)


def city_tower(floors, var):
    def build(state, lod, seed):
        x0, x1, z0, z1 = FOOT[floors]
        h = HEIGHT[floors]
        box = FOOT[floors]
        c = shell(state, lod, seed, ((x0 + x1) / 2 + 3.0, h * 0.5, (z0 + z1) / 2, 4.0), 2.0)
        cols = {2: 5, 4: 6, 6: 7, 8: 8}[floors]
        WFRAC[:] = [0.34, 0.42] if floors <= 4 else ([0.36, 0.42] if floors == 6 else [0.36, 0.38])
        wall = {"a": ("brickcity", "flat"), "b": ("greybrick", "flat"), "c": ("whitecity", "flat")}[var]
        if floors >= 6:
            wall = {"a": ("facadeblue", "flat"), "b": ("facadegreen", "flat"), "c": ("facadeblue", "flat")}[var]
        if floors == 2 and var == "c":
            wall = ("brickcity", "flat")
        if floors == 4 and var == "c":
            wall = ("whitecity", "flat")
        rk = dict(ac=2 + floors // 4, vents=2, lights=1 + (floors >= 6), hatch=1, seed=seed, mat="roofdark")
        if floors == 4 and var == "b":
            rk.update(ac=4)
        blk2(c, x0, x1, z0, z1, h, wall, grids={f: (cols, floors) for f in ("+z", "-z", "+x", "-x")}, main=True, roof="flat", **rk)
        rubble(c, box, h, 8 + 4 * floors)
        if state != "destroyed":
            fine = c.fine
            if floors <= 4:
                band(c, "+z", box, 1.0, 0.35, "palepaint")        # a ground-floor string course
                if floors == 4 and var == "c":
                    for k in range(1, floors):                     # the clapboard banding of the white block
                        band(c, "+z", box, k * STOREY + 0.2, 0.2, "palepaint")
                        band(c, "-x", box, k * STOREY + 0.2, 0.2, "palepaint")
                if floors == 4 and var == "b":
                    roll_door(c, "+z", box, 2.0, 4.0, 3.4)         # the garage door
                if floors == 2 and var == "c":
                    band(c, "+z", box, h - 0.7, 0.7, "facadegreen")    # green eaves band
                    fpanel(c, "bandorange", "+z", box, 3.0, 0.8, 5.0, 1.8, 0.0, 0.08)  # the graffiti panel
                    fpanel(c, "safetyyellow", "+z", box, 4.0, 1.4, 3.0, 0.7, 0.0, 0.09)
                door(c, "-z", box, 4.0, 1.5, 2.6)
            else:
                pilasters(c, box, h, cols, "palepaint", 0.6 if var != "a" else 0.35, every=1 if var != "a" else cols)
                door(c, "+z", box, 7.0, 2.0, 3.0)
                band(c, "+z", box, 3.6, 0.3, "palepaint")
                heli_ring(c, (x0 + x1) / 2, (z0 + z1) / 2, 4.0 if floors == 6 else 3.2, h + 0.43)
                if var == "c":
                    for k in range(cols // 2):                      # dark vertical window bands
                        fpanel(c, "grate", "+z", box, 1.2 + k * 5.4, 1.0, 1.4, h - 2.2, 0.0, 0.06)
        return c
    return build


def civ_house_barrel(long_b):
    """singlecivlivinga / b: low walls under a riveted barrel vault with white dormer windows and a chimney stack (two on b)."""
    def build(state, lod, seed):
        x0, x1 = -3.9, 3.9
        z0, z1 = (-11.1, 2.6) if long_b else (-3.5, 3.4)
        c = shell(state, lod, seed, (0.0, 3.0, (z0 + z1) / 2, 3.0), 1.5)
        box = (x0, x1, z0, z1)
        blk(c, x0, x1, z0, z1, 3.0, ("lightcorr", "flat"), holes={"+z": [(1.0, 0.2, 2.2, 2.4)], "-x": [(1.5, 0.8, 3.5, 2.2)]}, main=True, roof=None)
        if state != "destroyed":
            barrel_roof(c, x0, x1, z0, z1, 3.0, 3.3, "lightcorr")
            b = c.b
            n = 2 if not long_b else 2
            for k in range(n):
                zc = z0 + (z1 - z0) * (k + 0.5) / n
                for sx in (-1, 1):
                    b.box("palepaint", (sx * 2.7, 5.2, zc), (0.7, 1.9, 2.4), axis_angle(V([0, 0, 1.0]), -sx * 0.5))
                    b.box("wglass", (sx * 3.07, 5.25, zc), (0.12, 1.4, 1.9), axis_angle(V([0, 0, 1.0]), -sx * 0.5))
            for k in range(1 if not long_b else 2):
                zc = z0 + 1.5 + k * 2.0 if long_b else z0 + 2.2
                b.box("machgrey", (0.0, 7.0, zc if long_b else z0 + 2.4), (1.0, 2.0, 1.0)); b.box("steel", (0.0, 8.2, zc if long_b else z0 + 2.4), (1.2, 0.2, 1.2))
            door(c, "+z", box, 1.6, 1.0, 2.2)
            for key in ("-z", "+z"):                                  # the glazed end walls: a pale-framed glass band under the vault
                fpanel(c, "palepaint", key, box, 2.2 if key == "+z" else 0.6, 1.0, 5.0 if key == "-z" else 3.0, 1.5, 0.0, 0.07)
                fpanel(c, "wglass", key, box, 2.35 if key == "+z" else 0.75, 1.15, 4.7 if key == "-z" else 2.7, 1.2, 0.0, 0.09)
        return c
    return build


def civ_c(state, lod, seed):
    c = shell(state, lod, seed, (0.5, 2.0, 0.0, 2.5), 1.5)
    box = (-1.8, 2.9, -3.0, 2.7)
    blk2(c, *box[:2], *box[2:], 4.4, ("tealwall", "flat"), grids={"+x": (1, 1)}, main=True, roof="flat", ac=1, vents=0, hatch=1, seed=seed, mat="roofdark", parapet=0.3)
    if state != "destroyed":
        door(c, "+z", box, 0.6, 1.2, 2.4)
        fpanel(c, "bandorange", "+z", box, 2.4, 1.2, 1.8, 0.9, 0.0, 0.07)      # the sign board
        c.b.revolve("brick", [(0.9, 4.8), (0.1, 5.8)], 8, cx=2.0, cz=-2.2, uref=1.0)   # the lamp hat on the roof corner
    return c


def civ_d(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 2.0, 0.5, 2.5), 1.5)
    box = (-2.1, 2.1, -3.0, 0.8)
    blk2(c, *box[:2], *box[2:], 2.9, ("tealwall", "flat"), holes={"+z": [(0.6, 0.2, 1.8, 2.2), (2.4, 0.9, 3.4, 2.0)]}, main=True, roof="flat", ac=0, vents=0, hatch=0, seed=seed, mat="roofdark", parapet=0.2)
    if state != "destroyed":
        b = c.b
        for sx in (-1.9, 1.9):                  # the patchwork canopy on four poles
            for sz in (-2.8, 3.9):
                b.tube("machgrey", (sx, 0.0, sz), (sx, 3.4, sz), 0.1, 6)
        b.box("tinroof", (0.0, 3.45, 0.55), (4.4, 0.2, 7.2))
        b.box("rust", (0.8, 3.58, 1.5), (2.2, 0.05, 2.4))
        b.tube("steel", (-1.0, 3.6, -1.5), (-1.0, 4.3, -1.5), 0.45, 8)
        door(c, "+z", box, 0.6, 1.2, 2.2)
    return c


def civ2(state, lod, seed):
    """2civliving: a single-storey L: a long arm along +x and a short one along +z."""
    c = shell(state, lod, seed, (4.0, 1.5, 0.0, 3.0), 1.5)
    a = (-3.4, 11.2, -3.4, 3.6)
    blk2(c, *a[:2], *a[2:], 3.0, ("tealwall", "flat"), grids={"+z": (6, 1), "-z": (6, 1)}, main=True, roof="flat", ac=2, vents=1, lights=2, hatch=1, seed=seed, mat="roofdark", parapet=0.4)
    bq = (-3.4, 2.4, 3.6, 11.2)
    blk2(c, *bq[:2], *bq[2:], 3.0, ("tealwall", "flat"), grids={"-x": (3, 1), "+x": (3, 1)}, roof="flat", ac=1, vents=1, lights=1, hatch=0, seed=seed + 2, mat="roofdark", parapet=0.4)
    if state != "destroyed":
        door(c, "+z", a, 10.0, 1.4, 2.4)
        band(c, "+z", a, 2.3, 0.3, "palepaint")
    return c


def civ2story(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 3.5, -3.0, 3.0), 1.5)
    m = (-3.4, 3.4, -8.4, 2.4)
    blk2(c, *m[:2], *m[2:], 5.6, ("tealwall", "flat"), grids={"+x": (3, 2), "-x": (3, 2), "+z": (2, 2)}, main=True, roof="flat", ac=2, vents=1, lights=2, hatch=1, seed=seed, mat="roofdark", parapet=0.5)
    blk2(c, -3.0, 3.0, -10.8, -8.4, 3.0, ("tealwall", "flat"), holes={"-z": [(1.0, 0.8, 2.2, 2.2)]}, roof="flat", ac=0, vents=1, hatch=0, seed=seed + 4, mat="roofdark", parapet=0.3)
    if state != "destroyed":
        door(c, "+z", m, 2.6, 1.5, 2.5)
        band(c, "+z", m, 3.0, 0.3, "palepaint")
    return c


def shack(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 2.0, 0.0, 2.5), 1.5)
    box = (-3.0, 3.0, -2.9, 2.9)
    blk(c, *box[:2], *box[2:], 2.9, ("lightcorr", "corr"), main=True, roof=None, holes={})
    if state != "destroyed":
        prism_roof(c, *box[:2], *box[2:], 2.9, 1.1, "x", "lightcorr")
        for k in range(3):                      # the three yellow-framed windows on the gable face
            fpanel(c, "safetyyellow", "+z", box, 0.6 + k * 1.8, 1.0, 1.2, 1.0, 0.0, 0.07)
            fpanel(c, "glass", "+z", box, 0.75 + k * 1.8, 1.15, 0.9, 0.7, 0.0, 0.09)
        door(c, "-z", box, 2.3, 1.2, 2.2)
        c.b.box("machgrey", (1.5, 3.9, 0.0), (0.6, 0.9, 0.6))
    return c


def tinshack(state, lod, seed):
    c = shell(state, lod, seed, (4.0, 3.0, 4.0, 3.0), 1.5)
    box = (-3.2, 11.5, -3.3, 11.2)
    blk(c, *box[:2], *box[2:], 3.4, ("tinroof", "corr"), main=True, roof=None, holes={"+z": [(2.0, 0.1, 5.0, 2.8)]})
    if state != "destroyed":
        b = c.b
        ang = math.atan2(4.6, box[3] - box[2])          # a long mono-pitch tin roof rising to the back
        L = math.hypot(4.6, box[3] - box[2]) + 0.8
        b.box("tinroof", ((box[0] + box[1]) / 2, 3.4 + 2.3, (box[2] + box[3]) / 2), (box[1] - box[0] + 0.8, 0.25, L), axis_angle(V([1.0, 0, 0]), ang))
        b.box("machgrey", (0.5, 7.8, -2.4), (1.4, 2.0, 1.4)); b.box("steel", (0.5, 8.9, -2.4), (1.7, 0.2, 1.7))
        b.box("wglass", (4.0, 6.0, 0.6), (2.0, 0.1, 1.2), axis_angle(V([1.0, 0, 0]), ang))
        door(c, "+z", box, 2.4, 1.6, 2.6)
    return c


def greenhouse(state, lod, seed):
    c = shell(state, lod, seed, (-4.0, 2.0, 0.0, 3.0), 1.5)
    x0, x1, z0, z1 = -11.3, 2.5, -9.2, 9.2
    b = c.b
    if state == "destroyed":
        for k in range(6):
            b.tube("steel", (x0 + k * 2.6, 0.0, z0), (x0 + k * 2.6, 1.2 + (k % 3) * 0.6, z0), 0.06, 4)
        collapse(c, x0, x1, z0, z1, 1.5, 2)
        return c
    b.box("concrete", ((x0 + x1) / 2, 0.45, (z0 + z1) / 2), (x1 - x0 + 0.4, 0.9, z1 - z0 + 0.4))
    for sg in (-1, 1):
        b.box("pipegreen", ((x0 + x1) / 2, 1.5, (z0 + z1) / 2 + sg * (z1 - z0) / 2), (x1 - x0, 1.2, 0.08))     # glazed side walls
    b.box("pipegreen", (x0, 1.5, (z0 + z1) / 2), (0.08, 1.2, z1 - z0)); b.box("pipegreen", (x1, 1.5, (z0 + z1) / 2), (0.08, 1.2, z1 - z0))
    prism_roof(c, x0, x1, z0, z1, 2.4, 1.5, "z", "facadegreen", over=0.15)
    cx = (x0 + x1) / 2
    ang = math.atan2(1.5, (x1 - x0) / 2 + 0.15)
    for k in range(13 if c.fine else 5):                          # glazing bars across both slopes
        z = z0 + (z1 - z0) * k / (12 if c.fine else 4)
        for sx in (-1, 1):
            b.box("palepaint", (cx + sx * ((x1 - x0) / 4 + 0.07), 2.4 + 0.75 + 0.2, z), (math.hypot((x1 - x0) / 2 + 0.15, 1.5), 0.08, 0.12), axis_angle(V([0, 0, 1.0]), -sx * ang))
    if state == "damaged":
        b.box("rust", (cx + 2.0, 4.0, 2.0), (2.6, 0.3, 3.0), axis_angle(V([0, 0, 1.0]), 0.5))
    for k in range(5):                                            # roof fans along the ridge
        z = z0 + 2.2 + k * 3.5
        b.revolve("grate", [(0.8, 4.1), (0.8, 4.18), (0.0, 4.18)], 14 if c.fine else 6, cx=cx, cz=z, uref=1.0)
        b.revolve("machgrey", [(0.9, 3.95), (0.9, 4.1)], 14 if c.fine else 6, cx=cx, cz=z, uref=1.0)
    door(c, "-z", (x0, x1, z0, z1), 5.0, 3.0, 2.6)
    return c


def barracks(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 2.0, -4.0, 3.0), 1.5)
    box = (-4.2, 4.2, -12.7, 4.2)
    blk2(c, *box[:2], *box[2:], 3.2, ("lightcorr", "flat"), grids={"+x": (5, 1), "-x": (5, 1)}, main=True, roof="flat", ac=2, vents=1, lights=3, hatch=1, seed=seed, mat="roofdark", parapet=0.35)
    if state != "destroyed":
        door(c, "+z", box, 3.0, 1.6, 2.5)
        band(c, "+x", box, 2.4, 0.3, "safetyyellow")
        c.b.box("machgrey", (4.6, 1.2, -4.0), (0.6, 1.6, 1.8))
    return c


def meethall(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 6.0, -5.0, 4.0), 2.0)
    hall = (-6.0, 5.6, -10.6, 2.4)
    blk(c, *hall[:2], *hall[2:], 7.0, ("palecorr", "corr"), holes={"+z": [(3.0, 0.1, 7.0, 3.6)], "-x": [(2.0, 4.0, 11.0, 5.4)]}, main=True, roof=None)
    barrel_roof(c, hall[0], hall[1], hall[2], hall[3], 7.0, 5.6, "palecorr")
    for (x0, x1, nm) in ((-11.8, -6.0, 0), (5.6, 11.8, 1)):
        w = (x0, x1, -10.6, 10.6)
        blk2(c, *w[:2], *w[2:], 4.4, ("palecorr", "corr"), holes={"+z": [(0.8, 0.1, 3.4, 3.0)]}, roof="flat", ac=2, vents=2, lights=3, hatch=1, seed=seed + nm, mat="roofdark", parapet=0.4)
    if state != "destroyed":
        b = c.b
        b.revolve("machgrey", [(2.3, 7.6), (2.3, 7.7), (2.0, 7.7)], 16 if c.fine else 8, cx=0.0, cz=2.6, uref=1.0)   # the round window on the hall's front
        for k in range(4):
            b.box("glass", (-2.4 + k * 1.6, 6.0, 2.5), (1.0, 0.5, 0.1))
    return c


CIV = {}
for fl in (2, 4, 6, 8):
    for v in "abc":
        CIV[f"city{fl}story{v}"] = (city_tower(fl, v), f"{fl}-storey city block, variant {v}")
CIV.update({
    "singlecivlivinga": (civ_house_barrel(False), "riveted barrel-vault house with dormers and a stack"),
    "singlecivlivingb": (civ_house_barrel(True), "long barrel-vault house, two stacks"),
    "singlecivlivingc": (civ_c, "container-style teal shed with sign and lamp hat"),
    "singlecivlivingd": (civ_d, "small house under a patchwork canopy on four poles"),
    "2civliving": (civ2, "single-storey L-shaped teal block"),
    "2storycivliving": (civ2story, "two-storey teal block with an annex"),
    "shack": (shack, "corrugated gabled shack, yellow-framed windows"),
    "tinshack": (tinshack, "tin shed with a long mono-pitch roof and chimney"),
    "greenhouse": (greenhouse, "glazed greenhouse, ridge roof fans"),
    "barracks": (barracks, "low concrete barracks with roof lights"),
    "meethall": (meethall, "barrel-vault hall with two low wings"),
})
H.MEMBERS.update(CIV)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("app")
    ap.add_argument("--out", default=str(ROOT / "game/assets/v3/objects"))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    for app in (list(CIV) if a.app == "all" else a.app.split(",")):
        H.build_member(app, out)


if __name__ == "__main__":
    main()
