#!/usr/bin/env python3
"""v3 storage family (LANCE-21 pilot): procedural rebuilds of the MC2 tank buildings, three damage states each.

    python3 -I tools/art/v3/bld_tanks.py largefueltank [--out game/assets/v3/objects]

Writes <app>.glb (intact), <app>_damaged.glb, <app>_destroyed.glb plus <app>.v3.json (tris, bounds, source dims).
Everything is generated from the dimensions measured on the Shared Source original (see tools/cad/<app>_cad.py): the
silhouette keeps the original's footprint and height, but every round part is a true surface of revolution (72
segments), not the original's 6/10 facets. Surfaces use the shared CC0 library (tools/art/v3/bld_materials.py), the
project trim sheet and decal atlas (tools/art/v3/bld_trim.py). Frame: metres, Y up, the original's axes (pipe along +x).
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bld_mesh import Builder, rot_y, unit, TAU  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
SEG = 72
LOD_M = 80.0  # camera distance beyond which the lighter node (lod1) is drawn
K = 0.30  # trim pattern scale: 1 trim metre = 1/K physical metres (hazard chevrons 0.85 m wide, as the original's)
TRIM_TILE = 4.0 / K  # physical metres one trim tile spans along a strip


def uref(r, tile):
    """u scale so a full turn holds a whole number of texture tiles (no seam)."""
    return tile * max(1, round(TAU * r / tile)) / TAU


# decal atlas cells (bld_trim.CELLS), (col,row) of 4x4
CELLS = {"panel": 0, "diamond": 1, "id_plate": 2, "hatch": 3, "arrow": 4, "streak_a": 5, "streak_b": 6, "oil": 7,
         "soot": 8, "rust_bleed": 9, "stripe_corner": 10, "valve_tag": 11}


def cell_uv(name, inset=0.004):
    i = CELLS[name]
    c, r = i % 4, i // 4
    return (c / 4 + inset, r / 4 + inset, (c + 1) / 4 - inset, (r + 1) / 4 - inset)


def digit_uv(d):
    return (d * 102.4 / 1024 + 0.003, 896 / 1024 + 0.004, (d + 1) * 102.4 / 1024 - 0.003, 1.0 - 0.004)


class Tank:
    """Parameters of one tank; build(state) fills a Builder."""

    def __init__(self, **kw):
        self.__dict__.update(dict(R=8.4, cz=-0.02, y_drum0=4.96, y_drum1=16.15, belt=(8.5, 11.15), skirt_r=(8.8, 6.3), y_skirt=3.75,
                                  roof=[(8.4, 16.15), (8.0, 16.62), (7.0, 17.08), (5.87, 17.33), (4.5, 17.72), (2.97, 18.05)],
                                  pipe_y=1.37, pipe_r=0.83, pipe_x=(5.1, 11.94), pump_x=(11.93, 12.78), plinth=9.62, ladder_deg=150.0,
                                  catwalk_y=11.15, catwalk_r=9.45, id_digits=(0, 7)))
        self.__dict__.update(kw)


def build(T: Tank, state: str, seed: int, lod: int = 0) -> Builder:
    SEG = 72 if lod == 0 else 40  # true round either way: 40 segments sag 2.2 cm on the 8.4 m drum
    fine = lod == 0
    b = Builder()
    b.seg_cap = 0 if fine else 4
    rng = np.random.default_rng(seed)
    cz, R = T.cz, T.R
    burnt = {"intact": 0.0, "damaged": 0.55, "destroyed": 0.9}[state]
    breach = (math.radians(58), math.radians(112))  # damaged: the tank shell is torn open here

    def tor(th):  # shortest angular distance from the breach centre
        c = 0.5 * (breach[0] + breach[1])
        return abs((th - c + math.pi) % TAU - math.pi)

    def scorch_at(P):
        """burn amount at points P (n,3): around the breach / over the whole wreck, more near the ground fuel pool."""
        if burnt == 0:
            return np.zeros(len(P))
        x, y, z = P[:, 0], P[:, 1], P[:, 2] - cz
        if state == "destroyed":
            return np.clip(0.85 + 0.3 * np.exp(-y / 6.0) + 0.1 * np.sin(x * 1.3 + z * 0.7), 0, 1)
        th = np.arctan2(z, x)
        d = np.abs((th - 0.5 * (breach[0] + breach[1]) + math.pi) % TAU - math.pi)
        h = np.exp(-((y - 12.0) / 5.0) ** 2)
        return np.clip(np.exp(-(d / 1.1) ** 2) * h * 1.7 + 0.2 * np.exp(-y / 3.0), 0, 1)

    b.colfn = scorch_at
    cwy_, cwr_ = T.catwalk_y, T.catwalk_r

    def ao_at(P, N):
        """Baked ambient occlusion (1 open): ground contact, the skirt, the drum under the catwalk, at the stiffener rings and
        under the eave, the pipe run, every downward face. Cheap analytic stand-in for a ray-cast bake, identical across the family."""
        x, y, z = P[:, 0], P[:, 1], P[:, 2] - cz
        r = np.hypot(x, z)
        ao = 0.6 + 0.4 * np.clip(y / 2.0, 0, 1)
        sk = (r > 5.5) & (y < 3.9)
        ao = np.where(sk, ao * (0.62 + 0.38 * np.clip(y / 3.75, 0, 1)), ao)
        wall = (r > R - 0.3) & (r < R + 0.35)
        ao = np.where(wall & (y > cwy_ - 1.9) & (y < cwy_), ao * (0.4 + 0.6 * np.clip((cwy_ - y) / 1.9, 0, 1)), ao)
        for yr in (T.belt[0], cwy_):
            ao = np.where(wall, ao * (1 - 0.35 * np.exp(-np.abs(y - yr) / 0.35)), ao)
        ao = np.where(wall & (y < T.y_drum1) & (y > 14.8), ao * (1 - 0.3 * np.exp(-(T.y_drum1 - y) / 0.5)), ao)
        ao = np.where((x > 6.5) & (y < T.pipe_y + 0.3), ao * 0.72, ao)
        ao = np.where(N[:, 1] < -0.5, ao * 0.55, ao)
        return np.clip(ao, 0.15, 1.0)

    LEDGES = [(cwy_, 3.0, 1.0), (16.2, 3.6, 0.95), (T.belt[0], 1.5, 0.75), (5.2, 1.3, 0.8), (6.76, 1.1, 0.5), (8.56, 0.9, 0.35),
              (13.6, 1.1, 0.5), (3.9, 1.8, 0.8)]

    def wear_at(P, N):
        """Run-off and grime baked into vertex G: streaks below every ledge, seam and bolt row, a dirty skirt."""
        x, y, z = P[:, 0], P[:, 1], P[:, 2] - cz
        r = np.hypot(x, z)
        th = np.arctan2(z, x)
        g = np.zeros(len(P))
        wall = r > R - 0.5
        for k, (y0, L, a) in enumerate(LEDGES):
            gate = np.clip(0.45 + 1.1 * np.sin(th * (23 + 4 * k) + k) * np.sin(th * 9 + 2 * k), 0, 1)
            d = y0 - y
            g = np.maximum(g, np.where(wall & (d > 0) & (d < L), a * np.clip(1 - d / L, 0, 1) ** 0.8 * gate, 0))
        g = np.where((r > 5.5) & (y < 3.9), np.maximum(g, 0.55 - 0.25 * y / 3.9), g)
        return np.clip(g, 0, 1)

    b.aofn = ao_at
    b.wearfn = wear_at

    def with_xf(Rm, t):
        class Ctx:
            def __enter__(s_): b.M = (np.asarray(Rm), np.asarray(t, float))
            def __exit__(s_, *a): b.M = None
        return Ctx()

    def band_ring(mat, y0, y1, r, th, col=(0, 0, 0), up=True, sg=SEG):
        """A collar: wall r, top and bottom annuli th thick (outwards)."""
        b.revolve(mat, [(r + th, y0), (r + th, y1)], sg, cz=cz, uref=uref(r + th, 2.0), col=col)
        b.disc(mat, (0, y1, cz), r + th, r_in=r - 0.02, seg=sg, col=col)
        b.disc(mat, (0, y0, cz), r + th, (0, -1, 0), r_in=r - 0.02, seg=sg, col=col)

    def rev_pt(r, y):
        return np.array([r, y])

    def decal_rev(cell, th, wid, y0, y1, prof, uv=None, off=0.02, cols=6, rows=2):
        """A decal wrapped onto a cone/cylinder: prof = ((r0, y0), (r1, y1)) the surface line, th the centre angle."""
        (ra, ya), (rb, yb) = prof
        uv = uv or cell_uv(cell)
        P = []; U = []; N = []
        for j in range(rows + 1):
            y = y0 + (y1 - y0) * j / rows
            t = (y - ya) / (yb - ya)
            r = ra + (rb - ra) * t + off
            dr = (rb - ra) / (yb - ya)
            for i in range(cols + 1):
                f = i / cols - 0.5
                a = th + f * wid / r
                P.append((r * math.cos(a), y, cz + r * math.sin(a)))
                n2 = np.array([math.cos(a), -dr, math.sin(a)])
                N.append(unit(n2))
                U.append((uv[0] + (uv[2] - uv[0]) * (i / cols), uv[3] + (uv[1] - uv[3]) * (j / rows)))
        idx = []
        for j in range(rows):
            for i in range(cols):
                a = j * (cols + 1) + i
                idx += [(a, a + 1, a + cols + 1), (a + 1, a + cols + 2, a + cols + 1)]
        b.add("decal", P, N, U, idx)

    def decal_ground(cell, c, w, h, rot=0.0, y=0.04):
        u = np.array([math.cos(rot), 0, math.sin(rot)]); v = np.array([-math.sin(rot), 0, math.cos(rot)])
        b.quad("decal", np.array([c[0], y, c[1]]), u, v, w, h, cell_uv(cell), normal=(0, 1, 0))

    # ================================================================== foundation and skirt
    b.revolve("concrete", [(T.plinth, 0.0), (T.plinth, 0.30)], SEG, cz=cz, uref=uref(T.plinth, 2.0))
    b.revolve("concrete", [(T.plinth, 0.30), (T.plinth - 0.3, 0.40)], SEG, cz=cz, uref=uref(T.plinth, 2.0), voff=0.3)
    b.disc("concrete", (0, 0.40, cz), T.plinth - 0.3, r_in=0.0, seg=SEG, uvs=1.0)
    ra, rb = T.skirt_r
    sk0, sk1 = 0.40, T.y_skirt
    b.revolve("paint", [(ra, sk0), (rb, sk1)], SEG, cz=cz, uref=uref(ra, 2.0), band=0)
    # skirt hoops (galvanised straps) and the bolted flange where the skirt meets the bowl
    for yy in (0.95, 2.6):
        r_at = ra + (rb - ra) * (yy - sk0) / (sk1 - sk0)
        b.revolve("galv", [(r_at + 0.03, yy - 0.09), (r_at + 0.03, yy + 0.09)], SEG, cz=cz, uref=uref(r_at, 1.5))
    # six buttress ribs along the old hex corners (the original's corners sat on +-z; ribs avoid the feed pipe)
    slope = np.array([rb - ra, sk1 - sk0]); L = np.linalg.norm(slope); slope /= L
    for k in range(6):
        th = math.radians(30 + 60 * k)
        rh = np.array([math.cos(th), 0, math.sin(th)]); tg = np.array([-math.sin(th), 0, math.cos(th)]); up = np.array([0, 1.0, 0])
        s_ax = slope[0] * rh + slope[1] * up
        n_ax = slope[1] * rh - slope[0] * up
        mid = (np.array([ra, sk0]) + np.array([rb, sk1])) / 2
        c3 = mid[0] * rh + mid[1] * up + np.array([0, 0, cz]) + n_ax * 0.22
        Rm = np.stack([n_ax, s_ax, tg], 1)
        b.box("paint", c3, (0.45, L, 0.55), Rm)
        b.box("galv", c3 + n_ax * 0.24, (0.06, L, 0.8), Rm)
    # bowl: skirt top out to the drum
    bowl = [(6.3, 3.75), (6.42, 3.95), (6.95, 4.35), (7.75, 4.76), (8.4, 4.96)]
    b.revolve("paint", bowl, SEG, cz=cz, uref=uref(8.0, 2.0))
    band_ring("galv", 3.62, 3.9, 6.25, 0.32)
    # bolt heads on the flange (true small cylinders, 6-sided heads would read as hex nuts, which they are)
    for k in range(36 if fine else 0):
        a = TAU * k / 36
        p = np.array([6.62 * math.cos(a), 3.9, cz + 6.62 * math.sin(a)])
        b.tube("steel", p, p + (0, 0.07, 0), 0.06, 8)

    # skirt furniture: control panels, hatches, flow arrows
    prof_s = ((ra, sk0), (rb, sk1))
    for th_deg, cell, w, y0, y1 in ((30, "panel", 1.3, 1.1, 2.7), (88, "hatch", 1.3, 0.85, 2.85), (118, "hatch", 1.3, 0.85, 2.85),
                                    (-30, "panel", 1.3, 1.1, 2.7), (-90, "hatch", 1.3, 0.85, 2.85), (205, "panel", 1.3, 1.1, 2.7)):
        decal_rev(cell, math.radians(th_deg), w, y0, y1, prof_s)
    decal_rev("diamond", math.radians(55), 1.15, 1.2, 2.35, prof_s)
    decal_rev("diamond", math.radians(-60), 1.15, 1.2, 2.35, prof_s)

    # ================================================================== drum
    cut = state != "intact"
    SD = SEG if not cut else (144 if fine else 64)
    breach_c = 0.5 * (breach[0] + breach[1])

    def ridge(th):  # destroyed: the broken top edge of the shell (metres), long swells plus teeth
        teeth = 0.8 * np.abs(((np.asarray(th) * 9.0 / TAU * 2) % 2.0) - 1.0)
        return 10.3 + 2.1 * np.sin(2.1 * th + 0.7) + 1.1 * np.sin(5.3 * th) + 0.5 * np.sin(11.0 * th + 2.0) + teeth

    def blob(th, y, yc, a, b_, dth=0.0, ph=0.0):
        u = ((np.asarray(th) - breach_c - dth + math.pi) % TAU - math.pi) * R
        v = np.asarray(y) - yc
        g = np.sqrt((u / a) ** 2 + (v / b_) ** 2)
        phi = np.arctan2(v / b_, u / a)
        rho = 1 + 0.17 * np.sin(5 * phi + 1 + ph) + 0.1 * np.sin(9 * phi + 2) + 0.06 * np.sin(17 * phi)
        return (g - rho) * min(a, b_) * 0.9

    if state == "destroyed":
        keep_fn = lambda th, y: ridge(th) - y
    elif state == "damaged":
        keep_fn = lambda th, y: np.minimum(blob(th, y, 12.3, 3.7, 2.7), blob(th, y, 15.7, 1.9, 1.3, 0.35, 1.0))
    else:
        keep_fn = None
    cull = (lambda th, y: float(keep_fn(th, y)) < 0.18) if cut else None

    def disp(th, y, k):  # curled edges: mostly outward, some inward, strongest at the tear
        w = np.clip(1 - k / 0.55, 0, 1) ** 2
        return w * (0.12 + 0.2 * np.sin(th * 43.0 + 1.3) * np.cos(y * 3.1 + th * 7.0))

    def dense_rows(y0, y1, lo, hi, d_lo, d_hi):
        base = np.arange(y0, y1 + 1e-6, d_lo)
        dense = np.arange(lo, hi, d_hi)
        return np.unique(np.round(np.r_[base, dense, y1], 4))

    ur = uref(R, 2.0)
    if not cut:
        rows = np.unique(np.r_[np.arange(T.y_drum0, T.y_drum1 + 1e-6, 0.4), T.y_drum1])
        b.revolve("paint", [(R, y) for y in rows], SD, cz=cz, uref=ur)
    else:
        dlo, dhi = (8.8, 16.15) if state == "damaged" else (8.0, 13.6)
        rows = dense_rows(T.y_drum0, T.y_drum1, dlo, dhi, 0.5, 0.14 if fine else 0.3)
        const = lambda r_: (lambda ys: np.full_like(ys, r_))
        b.cut_surface("paint", const(R), rows, SD, keep_fn, cz=cz, disp=disp, uref=ur, thickness=0.09)
        # the inner face of the shell: whole in the damaged tank (seen through the tear), torn like the outside in the wreck
        if state == "destroyed":
            b.cut_surface("interior", const(R - 0.12), rows, SD, keep_fn, cz=cz, flip=True, uref=uref(R - 0.12, 2.0))
        else:
            b.revolve("interior", [(R - 0.12, y) for y in np.unique(np.r_[np.arange(T.y_drum0, T.y_drum1, 0.5), T.y_drum1])], SD, cz=cz, flip=True, uref=uref(R - 0.12, 2.0))
        b.disc("interior", (0, T.y_drum0 + 0.05, cz), R - 0.12, seg=SEG)
    # weld seams: horizontal rings and 16 vertical beads (beads dropped in the distant LOD)
    def weld_ring(y):
        half = [(R + 0.018 + 0.05 * math.sin(a), y + 0.07 * math.cos(a)) for a in np.linspace(math.pi / 2, -math.pi / 2, 7 if fine else 3)]
        h = 0.14
        cullw = (lambda th, yy: cull(th, y)) if cut else None
        b.revolve("trim", half, SD, cz=cz, cull=cullw, band=3, uref=uref(R, TRIM_TILE) * K, vscale=K * 0.5 / h)
    for y in (6.76, 13.6):
        if state == "destroyed" and y > 9.4:
            continue
        weld_ring(y)
    for k in range(16):
        a = TAU * (k + 0.5) / 16
        ytop = T.y_drum1
        if cut:
            yy = np.arange(T.y_drum0, T.y_drum1, 0.1)
            kk = keep_fn(np.full_like(yy, a), yy)
            if kk[0] < 0.2:
                continue
            bad = np.flatnonzero(kk < 0.25)
            ytop = yy[bad[0]] if len(bad) else T.y_drum1
        b.tube("paint", (R * math.cos(a), T.y_drum0 + 0.02, cz + R * math.sin(a)), ((R + 0.01) * math.cos(a), ytop, cz + (R + 0.01) * math.sin(a)), 0.045, 6, caps=False)

    # hazard belt (trim band 0), proud of the shell between a stiffener ring below and the catwalk above
    y0, y1 = T.belt
    belt_rows = np.linspace(y0, y1, 12)
    if state == "intact":
        b.revolve("trim", [(R + 0.025, y) for y in (y0, y1)], SD, cz=cz, band=0, uref=uref(R, TRIM_TILE) * K, vscale=K)
        band_ring("galv", y0 - 0.12, y0 + 0.1, R, 0.2)
    elif state == "damaged":
        b.cut_surface("trim", lambda ys: np.full_like(ys, R + 0.025), belt_rows, SD, lambda t, y: keep_fn(t, y) - 0.2, cz=cz, band=0,
                      uref=uref(R, TRIM_TILE) * K, vscale=K)
        band_ring("galv", y0 - 0.12, y0 + 0.1, R, 0.2)
    else:
        band_ring("galv", y0 - 0.12, y0 + 0.1, R, 0.2)
    # tint band under the eave, wide enough to read from the RTS camera (faction colour: vertex R = 1)
    if state == "intact":
        b.revolve("trim", [(R + 0.02, 14.5), (R + 0.02, 15.95)], SD, cz=cz, band=6, uref=uref(R, TRIM_TILE) * K, vscale=K, col=(1, 0, 0))
        band_ring("galv", 15.98, 16.2, R, 0.14)
    elif state == "damaged":
        b.cut_surface("trim", lambda ys: np.full_like(ys, R + 0.02), np.linspace(14.5, 15.95, 8), SD, lambda t, y: keep_fn(t, y) - 0.2, cz=cz,
                      band=6, uref=uref(R, TRIM_TILE) * K, vscale=K, col=(1, 0, 0))
        band_ring("galv", 15.98, 16.2, R, 0.14)
    # bolt rows at the foot and the bowl joint (the painted bolts of the original)
    for yy in ((5.37, 8.2) if fine else ()):
        for k in range(96):
            a = TAU * (k + 0.5) / 96
            p = np.array([(R + 0.012) * math.cos(a), yy, cz + (R + 0.012) * math.sin(a)])
            b.tube("steel", p, p + np.array([math.cos(a), 0, math.sin(a)]) * 0.07, 0.05, 6)

    # markings on the drum
    prof_d = ((R, 0), (R, 100))
    if state != "destroyed":
        for th_deg, y0_, y1_ in ((200, 6.0, 7.4), (20, 6.0, 7.4)):
            decal_rev("diamond", math.radians(th_deg), 1.4, y0_, y1_, prof_d, off=0.03, cols=4)
        for th_deg in (75, 255):
            decal_rev("id_plate", math.radians(th_deg), 2.4, 12.2, 13.5, prof_d, off=0.03, cols=8)
            for j, dgt in enumerate(T.id_digits):
                decal_rev("id_plate", math.radians(th_deg) + (-0.34 + 0.68 * j) / R * 0.5 * 2.0 * 0.5, 0.78, 12.35, 13.4, prof_d,
                          uv=digit_uv(dgt), off=0.045, cols=2)
        seam_ok = lambda th_deg, yy_: (not cut) or float(keep_fn(math.radians(th_deg), yy_)) > 1.2
        for k, th_deg in enumerate(range(5, 360, 21)):  # run-off below the catwalk and bolt rows, rust bleeding from the seams
            if seam_ok(th_deg, 9.5):
                decal_rev("streak_a" if k % 2 else "streak_b", math.radians(th_deg + (k * 7) % 9), 2.3, 7.6, 11.0, prof_d, off=0.04, cols=4)
        for k, th_deg in enumerate(range(12, 360, 29)):
            if seam_ok(th_deg, 14.5):
                decal_rev("streak_b" if k % 2 else "streak_a", math.radians(th_deg), 2.6, 12.6, 16.1, prof_d, off=0.04, cols=4)
        for k, th_deg in enumerate(range(0, 360, 17)):
            for yb_, hh_ in ((5.35, 1.7), (6.74, 1.5), (13.6, 1.6)):
                if (k + int(yb_)) % 2 == 0 and seam_ok(th_deg, yb_ - 0.8):
                    decal_rev("rust_bleed", math.radians(th_deg + yb_), 1.6, yb_ - hh_, yb_ + 0.1, prof_d, off=0.05, cols=3)
    else:
        for th_deg in range(0, 360, 40):
            decal_rev("soot", math.radians(th_deg), 4.0, 5.2, 9.5, prof_d, off=0.03, cols=4)

    # ================================================================== catwalk, ladder, roof
    ladder_th = math.radians(T.ladder_deg)
    rh_l = np.array([math.cos(ladder_th), 0, math.sin(ladder_th)])
    tg_l = np.array([-math.sin(ladder_th), 0, math.cos(ladder_th)])
    cwy, cwr = T.catwalk_y, T.catwalk_r
    if state != "destroyed":
        gap0, gap1 = (breach if state == "damaged" else (0, 0))
        # grating ring as two arcs when a section has fallen away
        arcs = [(0, TAU)] if state == "intact" else [(breach[1] + 0.12, breach[0] - 0.12 + TAU)]
        for a0, a1 in arcs:
            n = int((a1 - a0) / TAU * SEG) + 1
            th = np.linspace(a0, a1, n + 1)
            inner = np.stack([(R + 0.12) * np.cos(th), np.full(n + 1, cwy), cz + (R + 0.12) * np.sin(th)], 1)
            outer = np.stack([cwr * np.cos(th), np.full(n + 1, cwy), cz + cwr * np.sin(th)], 1)
            P = np.vstack([inner, outer]); Nn = np.tile((0, 1, 0), (len(P), 1))
            U = P[:, [0, 2]] * 1.0
            idx = [(i, i + 1, n + 1 + i) for i in range(n)] + [(i + 1, n + 2 + i, n + 1 + i) for i in range(n)]
            b.add("grate", P, Nn, U, idx)
            # kick plate and under-flange
            for rr in (cwr, ):
                path = [(rr * math.cos(t), cwy, cz + rr * math.sin(t)) for t in th]
                for i in range(len(th) - 1):
                    pass
            b.revolve("galv", [(cwr, cwy - 0.12), (cwr, cwy + 0.12)], SEG, cz=cz, th0=a0, th1=a1, uref=uref(cwr, 1.5))
            # handrail: top rail, mid rail, posts
            for hh, rt in ((1.1, 0.034), (0.55, 0.026)):
                b.sweep("steel", [(cwr * math.cos(t), cwy + hh, cz + cwr * math.sin(t)) for t in th], rt, 8, caps=True)
            for k in range(int((a1 - a0) / TAU * (56 if fine else 28)) + 1):
                t = a0 + (a1 - a0) * k / max(1, int((a1 - a0) / TAU * (56 if fine else 28)))
                if state == "intact" and abs((t - ladder_th + math.pi) % TAU - math.pi) < 0.1:
                    continue
                p = np.array([cwr * math.cos(t), cwy, cz + cwr * math.sin(t)])
                b.tube("steel", p, p + (0, 1.1, 0), 0.03, 6)
            # under-brackets
            for k in range(24):
                t = a0 + (a1 - a0) * (k + 0.5) / 24
                rh = np.array([math.cos(t), 0, math.sin(t)])
                p0 = np.array([0, cwy - 0.85, cz]) + rh * R
                p1 = np.array([0, cwy - 0.1, cz]) + rh * (cwr - 0.1)
                b.tube("steel", p0, p1, 0.045, 6)
        # a dangling grate panel hanging from a bracket
        if state == "damaged":
            t = breach[0] - 0.25
            rh = np.array([math.cos(t), 0, math.sin(t)]); tg = np.array([-math.sin(t), 0, math.cos(t)])
            Rm = np.stack([rh, np.array([0, 1.0, 0]), tg], 1)
            tilt = np.array([[math.cos(0.9), -math.sin(0.9), 0], [math.sin(0.9), math.cos(0.9), 0], [0, 0, 1]])
            b.box("grate", np.array([0, cwy - 0.7, cz]) + rh * (R + 0.7), (1.2, 0.06, 1.6), Rm @ tilt, uvs=1.0)
    # ladder with safety cage, from the plinth to the roof rail
    lad_off = R + 0.20
    yb, yt = 0.4, 16.75
    if state != "destroyed":
        yt_l = yt if state == "intact" else 9.7 if tor(ladder_th) < 0.6 else yt
        for side in (-1, 1):
            base = rh_l * lad_off + tg_l * 0.24 * side + np.array([0, 0, cz])
            b.tube("steel", base + (0, yb, 0), base + (0, yt_l, 0), 0.028, 8)
        rung = 0.3 if fine else 0.9
        n_r = int((yt_l - yb) / rung)
        for k in range(n_r):
            yy = yb + 0.25 + k * rung
            c0 = rh_l * lad_off + np.array([0, yy, cz])
            b.tube("steel", c0 - tg_l * 0.24, c0 + tg_l * 0.24, 0.02, 6, caps=False)
        for yy in (np.arange(1.2, yt_l, 1.8) if fine else ()):
            c0 = rh_l * (R + 0.02) + np.array([0, yy, cz])
            for side in (-1, 1):
                b.tube("steel", c0 + tg_l * 0.24 * side, c0 + tg_l * 0.24 * side + rh_l * 0.18, 0.025, 6)
        if state == "intact" and fine:
            for yy in np.arange(2.6, min(yt_l, 16.0), 0.9):
                path = []
                for a in np.linspace(-1.9, 1.9, 14):
                    d = math.cos(a) * rh_l + math.sin(a) * tg_l
                    path.append(np.array([0, yy, cz]) + rh_l * lad_off + d * 0.46)
                b.sweep("steel", path, 0.012, 6)
            for a in (-1.9, -0.95, 0, 0.95, 1.9):
                d = math.cos(a) * rh_l + math.sin(a) * tg_l
                p = np.array([0, 0, cz]) + rh_l * lad_off + d * 0.46
                b.tube("steel", p + (0, 2.6, 0), p + (0, 16.0, 0), 0.011, 5)

    # roof
    if state != "destroyed":
        roof_ys = np.array([p[1] for p in T.roof]); roof_rs = np.array([p[0] for p in T.roof])
        if state == "damaged":
            def roof_keep(th, y):  # a torn roof panel above the shell breach
                u = ((np.asarray(th) - breach_c + math.pi) % TAU - math.pi) * 6.0
                g = np.sqrt((u / 2.4) ** 2 + ((np.asarray(y) - 16.75) / 0.75) ** 2)
                return (g - (1 + 0.15 * np.sin(7 * np.arctan2(np.asarray(y) - 16.75, u)))) * 0.7
            ry = np.unique(np.r_[np.linspace(16.15, 18.05, 14), np.linspace(16.4, 17.2, 10)])
            b.cut_surface("paint", lambda ys: np.interp(ys, roof_ys, roof_rs), ry, 96 if fine else 48, roof_keep, cz=cz, uref=uref(8.0, 2.0),
                          disp=lambda th, y, k: np.clip(1 - k / 0.4, 0, 1) ** 2 * 0.1, thickness=0.07)
        else:
            b.revolve("paint", T.roof, SEG, cz=cz, uref=uref(8.0, 2.0))
        # tint ring on the dome, so the faction colour reads from the RTS camera (which sees the roof, not the eave)
        rk = lambda th: (state == "damaged" and tor(th) < math.radians(40))
        b.revolve("trim", [(7.12, 17.12), (5.77, 17.40)], SEG, cz=cz, cull=(lambda th, y: rk(th)), band=6, uref=uref(6.4, TRIM_TILE) * K, vscale=K, col=(1, 0, 0))
        # radial roof ribs
        for k in range(16):
            th = TAU * k / 16
            if state == "damaged" and tor(th) < math.radians(24):
                continue
            pts = [(r * math.cos(th), y + 0.05, cz + r * math.sin(th)) for r, y in T.roof[::-1] if r > 2.9]
            b.sweep("steel", pts, 0.05, 6, caps=True)
        # hatch drum with the hazard top, vent, stack
        b.revolve("galv", [(2.97, 18.02), (2.97, 18.42)], SEG, cz=cz, uref=uref(2.97, 1.5))
        b.disc("trim", (0, 18.42, cz), 2.97, r_in=0.0, seg=SEG, band=1, uvs=K, col=(0, 0, 0))
        b.revolve("steel", [(0.95, 18.42), (0.95, 19.05)], 24, cz=cz, uref=uref(0.95, 1.5))
        b.revolve("steel", [(0.95, 19.05), (1.15, 19.12), (0.7, 19.38), (0.0, 19.5)], 24, cz=cz, uref=uref(1.0, 1.5))
        # manway hatch and a relief vent with a goose-neck
        b.box("steel", (3.8 * math.cos(0.3), 17.9, cz + 3.8 * math.sin(0.3)), (1.1, 0.35, 1.1), rot_y(-0.3))
        p = np.array([5.0 * math.cos(2.0), 17.55, cz + 5.0 * math.sin(2.0)])
        b.sweep("steel", [p, p + (0, 1.1, 0), p + (0.25, 1.45, 0.1), p + (0.55, 1.4, 0.2)], 0.16, 12, caps=True)
        # roof edge handrail
        rr = 8.0
        arc = [(rr * math.cos(t), 16.62 + 1.0, cz + rr * math.sin(t)) for t in np.linspace(0, TAU, SEG + 1)]
        if state == "intact":
            for hh, rt in ((1.0, 0.032), (0.5, 0.025)):
                b.sweep("steel", [(rr * math.cos(t), 16.62 + hh, cz + rr * math.sin(t)) for t in np.linspace(0.12, TAU - 0.0, SEG)], rt, 8, caps=True)
            for k in range(48):
                t = TAU * k / 48
                if t < 0.12:
                    continue
                p = np.array([rr * math.cos(t), 16.58, cz + rr * math.sin(t)])
                b.tube("steel", p, p + (0, 1.04, 0), 0.028, 6)
        else:
            for hh, rt in ((1.0, 0.032),):
                t0, t1 = breach[1] + 0.2, breach[0] - 0.2 + TAU
                b.sweep("steel", [(rr * math.cos(t), 16.62 + hh, cz + rr * math.sin(t)) for t in np.linspace(t0, t1, 56)], rt, 8)
            for k in range(36):
                t = breach[1] + 0.2 + (breach[0] - 0.2 + TAU - breach[1] - 0.2) * k / 35
                p = np.array([rr * math.cos(t), 16.58, cz + rr * math.sin(t)])
                b.tube("steel", p, p + (0, 1.04, 0), 0.028, 6)
    # ================================================================== feed pipe, valve, pump, apron
    py, pr = T.pipe_y, T.pipe_r
    ax = np.array([1.0, 0, 0])
    apron = [8.2, 13.6, -2.5, 2.5]
    b.box("concrete_dark", ((apron[0] + apron[1]) / 2, 0.06, cz), (apron[1] - apron[0], 0.12, apron[3] - apron[2]), uvs=1.0)
    pipe_end = T.pipe_x[1]
    if state == "destroyed":
        pipe_end = 9.2
    b.tube("galv", (T.pipe_x[0], py, cz), (pipe_end, py, cz), pr, 32)
    for x in (7.45, 9.70, T.pipe_x[1] - 0.16):
        if x > pipe_end:
            continue
        b.tube("steel", (x - 0.1, py, cz), (x + 0.1, py, cz), pr + 0.13, 32)
        for k in range(12 if fine else 0):
            a = TAU * k / 12
            q = np.array([x, py + (pr + 0.06) * math.cos(a), cz + (pr + 0.06) * math.sin(a)])
            b.tube("steel", q + (-0.14, 0, 0), q + (0.14, 0, 0), 0.04, 6)
    for x in (6.6, 8.6, 10.6):
        if x > pipe_end:
            continue
        b.box("concrete", (x, 0.3, cz), (0.9, 0.36, 2.0))
        b.box("steel", (x, py - pr - 0.02, cz), (0.9, 0.06, 1.7))
    if state == "destroyed":  # the broken end: a bent stub on the apron
        b.sweep("galv", [(9.2, py, cz), (9.9, py - 0.05, cz + 0.2), (10.7, py - 0.25, cz + 0.6)], pr, 24, caps=True)
        b.disc("rust", (9.2, py, cz), pr * 0.9, (-1, 0, 0), seg=24)
    # gate valve on the pipe
    if state != "destroyed":
        xv = 9.70
        b.box("galv", (xv, py + 1.0, cz), (0.9, 0.9, 0.7))
        b.tube("steel", (xv, py + 1.4, cz), (xv, py + 2.4, cz), 0.07, 10)
        wheel = [(xv + 0.42 * math.cos(a), py + 2.45, cz + 0.42 * math.sin(a)) for a in np.linspace(0, TAU, 28)]
        b.sweep("steel", wheel, 0.035, 8, closed=True, col=(1, 0, 0))
        for k in range(4):
            a = k * math.pi / 2
            b.tube("steel", (xv, py + 2.45, cz), (xv + 0.42 * math.cos(a), py + 2.45, cz + 0.42 * math.sin(a)), 0.02, 6, caps=False, col=(1, 0, 0))
    # pump block: a tapered housing with its flange plate and a motor drum
    px0, px1 = T.pump_x
    if state == "destroyed":
        Rt = np.array([[math.cos(0.35), -math.sin(0.35), 0], [math.sin(0.35), math.cos(0.35), 0], [0, 0, 1]])
        pc = np.array([12.35, 1.2, cz]); ctx = with_xf(Rt, pc - Rt @ pc + np.array([0.3, -0.05, 0.5]))
        ctx.__enter__()
    b.box("paint", ((px0 + px1) / 2, 1.2, cz), (px1 - px0, 2.4, 2.2))
    b.box("steel", (px1 + 0.05, 1.37, cz), (0.1, 1.9, 1.9))
    b.tube("steel", (px1 + 0.1, 1.37, cz), (px1 + 0.35, 1.37, cz), 0.62, 24)
    b.revolve("steel", [(0.5, 0.0), (0.55, 0.9)], 16, cx=(px0 + px1) / 2, cz=cz + 1.9) if state != "destroyed" else None
    if state == "destroyed":
        ctx.__exit__()
    # ground and tank stains
    if state == "destroyed":
        decal_ground("soot", (0.0, cz), 21.0, 21.0, 0.0, y=0.045)
        decal_ground("oil", (4.0, cz + 4.5), 9.0, 9.0, 1.0, y=0.05)
        decal_ground("oil", (-4.5, cz - 3.5), 8.0, 8.0, 2.0, y=0.052)
    elif state == "damaged":
        decal_ground("oil", (3.0, cz + 9.0), 6.0, 6.0, 0.4, y=0.45)
        decal_ground("soot", (3.0, cz + 6.5), 9.0, 9.0, 0.0, y=0.465)
    else:
        decal_ground("oil", (12.0, cz + 0.8), 3.5, 3.5, 0.6, y=0.135)
    # ================================================================== state: wreckage
    if state == "destroyed":
        # tank floor and the burnt stub of the bowl
        b.disc("interior", (0, T.y_drum0 + 0.05, cz), R - 0.12, seg=SEG)
        # roof dome in wedge panels dropped into and over the ring
        dome = [(0.0, 18.3)] + [(r, y) for r, y in T.roof[::-1]] + [(8.4, 16.15)]
        for k in range(7):
            a0 = TAU * k / 7
            half = TAU / 7
            ang = rng.uniform(0.2, 0.9)
            tilt_ax = np.array([-math.sin(a0 + half / 2), 0, math.cos(a0 + half / 2)])
            Rt = _axis_angle(tilt_ax, rng.uniform(-0.4, 0.9) * (1 if k % 2 else -1))
            off = np.array([0.0, rng.uniform(-8.0, -6.6), 0.0]) + np.array([math.cos(a0 + half / 2), 0, math.sin(a0 + half / 2)]) * rng.uniform(-1.8, 1.4)
            cen = np.array([5.0 * math.cos(a0 + half / 2), 17.4, cz + 5.0 * math.sin(a0 + half / 2)])
            ctx = with_xf(Rt, cen - Rt @ cen + off)  # tilt about the wedge's own centre, then drop it into the ring
            ctx.__enter__()
            pts = [(r, y) for r, y in T.roof if r > 0.5]
            b.revolve("paint", pts, 6, cz=cz, th0=a0, th1=a0 + half * 0.92, uref=uref(8.0, 1.5), col=(0, 0, 0))
            b.revolve("rust", [(r - 0.05, y - 0.06) for r, y in pts], 6, cz=cz, th0=a0, th1=a0 + half * 0.92, flip=True, uref=uref(8.0, 1.5))
            ctx.__exit__()
        # curled shell plates around the broken rim
        for k in range(18):
            a = TAU * (k + rng.random() * 0.6) / 18
            hh = ridge(a)
            rh = np.array([math.cos(a), 0, math.sin(a)]); tg = np.array([-math.sin(a), 0, math.cos(a)])
            lean = rng.uniform(0.35, 1.2)
            n_ax = rh * math.cos(lean) + np.array([0, 1, 0]) * math.sin(lean)
            s_ax = -rh * math.sin(lean) + np.array([0, 1, 0]) * math.cos(lean)
            c3 = np.array([0, hh - 0.2, cz]) + rh * (R + 0.05) + s_ax * 0.8
            b.box("paint", c3, (0.05, 1.6, rng.uniform(0.9, 1.8)), np.stack([n_ax, s_ax, tg], 1), col=(0, 0, 0))
            b.box("rust", c3 - n_ax * 0.03, (0.04, 1.62, 1.0), np.stack([n_ax, s_ax, tg], 1))
        # a twisted run of handrail and a fallen ladder section on the ground
        pts = [(R + 2.0 + 0.4 * math.sin(i * 0.7), 0.5 + 0.3 * math.sin(i * 1.3), cz - 3.0 + i * 0.5) for i in range(14)]
        b.sweep("steel", [(x * math.cos(1.2) - z * math.sin(1.2) * 0 + 0.0, y, z) for x, y, z in pts], 0.034, 8)
        lad_base = np.array([-6.0, 0.55, cz - 9.2])
        dirv = unit(np.array([0.5, 0.0, 1.0]))
        for side in (-1, 1):
            q = lad_base + np.cross(dirv, (0, 1, 0)) * 0.24 * side
            b.tube("steel", q, q + dirv * 5.5 + (0, 0.25 * side, 0), 0.028, 8)
        for k in range(16):
            c0 = lad_base + dirv * (0.3 + k * 0.33)
            b.tube("steel", c0 - np.cross(dirv, (0, 1, 0)) * 0.24, c0 + np.cross(dirv, (0, 1, 0)) * 0.24, 0.02, 6)
        # a grate section on the pipe apron and the burnt-out bowl liner
        b.box("grate", (11.0, 0.25, cz + 3.2), (2.0, 0.06, 1.4), _axis_angle(np.array([0, 1.0, 0]), 0.5) @ _axis_angle(np.array([1.0, 0, 0]), 0.25))
        # skirt remains: a ragged top on the bowl ring (plates stand up around the rim)
        for k in range(10):
            a = TAU * (k + rng.random()) / 10
            rh = np.array([math.cos(a), 0, math.sin(a)]); tg = np.array([-math.sin(a), 0, math.cos(a)])
            c3 = np.array([0, 4.96 + 0.3, cz]) + rh * (R - 0.1)
            b.box("rust", c3, (0.06, rng.uniform(0.6, 1.4), rng.uniform(0.7, 1.4)), np.stack([rh, np.array([0, 1, 0]), tg], 1))
    return b


def _axis_angle(ax, a):
    ax = unit(ax); x, y, z = ax
    c, s = math.cos(a), math.sin(a); t = 1 - c
    return np.array([[t * x * x + c, t * x * y - s * z, t * x * z + s * y],
                     [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
                     [t * x * z - s * y, t * y * z + s * x, t * z * z + c]])


FAMILY = {
    "largefueltank": dict(tank=Tank(), src="tools/cad/largefueltank_cad.py (decagonal drum 8.60 m corners, 4.96-16.15 m; hex skirt 9.35 m; feed pipe and pump to x 12.78)"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("app")
    ap.add_argument("--out", default=str(ROOT / "game/assets/v3/objects"))
    ap.add_argument("--states", default="intact,damaged,destroyed")
    a = ap.parse_args()
    spec = FAMILY[a.app]
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    info = {"app": a.app, "made_by": "tools/art/v3/bld_tanks.py", "source_dims": spec["src"], "states": {}}
    for state in a.states.split(","):
        seed = (hash(a.app) & 0) + 2100 + {"intact": 0, "damaged": 1, "destroyed": 2}[state]
        lods = [build(spec["tank"], state, seed, 0), build(spec["tank"], state, seed, 1)]
        name = a.app + ("" if state == "intact" else "_" + state)
        st = Builder.write_lods(out / f"{name}.glb", name, lods)
        P = np.vstack([v for s_ in lods[0].s.values() for v in s_["P"]])
        info["states"][state] = {"tris_lod0": int(sum(st[0].values())), "tris_lod1": int(sum(st[1].values())), "lod_switch_m": LOD_M,
                                 "per_material_lod0": st[0],
                                 "bounds_min": np.round(P.min(0), 2).tolist(), "bounds_max": np.round(P.max(0), 2).tolist()}
        print(state, info["states"][state]["tris_lod0"], info["states"][state]["tris_lod1"], info["states"][state]["bounds_min"], info["states"][state]["bounds_max"])
    (out / f"{a.app}.v3.json").write_text(json.dumps(info, indent=1) + "\n")


if __name__ == "__main__":
    main()
