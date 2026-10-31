#!/usr/bin/env python3
"""v3 hangar, vehiclehangar and repairbay, second pass (LANCE-21 family 2): keep the originals' identity.

    python3 -I tools/art/v3/bld_hangars_b.py hangar|vehiclehangar|repairbay|all

hangar: barrel hall with two rows of large dark skylight bays (2 x 2 panes in frames) over a grey-white ribbed roof, pale panelled side walls
with a long window band, dark big door and shutter on the arched ends. vehiclehangar: the ribbed (finned) sloped roofs round a pale flat top,
the big recessed door with its painted "13", window strips, duct arch. repairbay: the multi-storey complex: tall block with window grids, lower
annexes, two hooded gantry towers with beacons, a dark open truss bridge with striped plates over the striped pad, roof plant. Destroyed states
keep structure: standing arch ribs or steel frames, collapsed roof sections. Overrides the first-pass builders in bld_hangars.py.
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bld_hangars as H  # noqa: E402
from bld_hangars import (Ctx, V, TAU, axis_angle, unit, barrel, arc_rib, arch_fns, clad, slab_sheet, interior_shell, timber, window, roller_door,  # noqa: E402
                         debris, broken_boards, torn, ridge_keep, curl, gutter, downpipe, rect_keep, collapse, ROOT)
from bld_kit import cell_uv  # noqa: E402
from bld_kit import digit_uv  # noqa: E402


def skylight(c, p, ax_u, ax_v, w, h, frame="paint", panes=(2, 2), tilt_n=None):
    """Glass pane group behind an opening: p the opening centre on the roof surface, ax_u/ax_v its in-plane axes, tilt_n the outward normal."""
    b = c.b
    n = unit(tilt_n) if tilt_n is not None else unit(np.cross(ax_u, ax_v))
    u, v = unit(ax_u), unit(ax_v)
    b.quad("glass", V(p) - n * 0.2, u, v, w, h, (0, h, w, 0), normal=n)
    Rm = np.stack([u, v, n], 1)
    for i in range(1, panes[0]):
        b.box(frame, V(p) + u * (-w / 2 + w * i / panes[0]) - n * 0.12, (0.1, h, 0.1), Rm)
    for j in range(1, panes[1]):
        b.box(frame, V(p) + v * (-h / 2 + h * j / panes[1]) - n * 0.12, (w, 0.1, 0.1), Rm)


# ============================================================================================================== hangar
def hangar(state, lod, seed):
    H.WALL[:] = ["facade", "flat"]; H.ROOF[:] = ["roofclean"]
    c = Ctx(state, lod, seed, breach=(5.0, 6.0, 19.2, 3.5), ledges=[(9.98, 3.2, 0.9), (1.0, 1.0, 0.6)], ao_rings=[(9.98, 1.4, 0.4)], ground_h=2.5)
    b = c.b
    fine = c.fine
    x0, x1, zh = -19.0, 19.2, 19.2
    L = x1 - x0
    wallh = 9.984
    r = 35.71; yc = 15.584 - r; ph = math.asin(zh / r)
    Sx, cs = arch_fns("arc", r=r, yc=yc, phi=ph)
    ax = V([1.0, 0, 0]); org = V([0, 0, 0.0])
    dst = state == "destroyed"
    b.box("concrete", ((x0 + x1) / 2, 0.15, 0), (L + 0.8, 0.3, 2 * zh + 0.8))
    # two rows of large skylight bays: five per slope, 5 m x 3.6 m, 2 x 2 panes, at about a quarter of the arc from each eave
    bays = []
    for frac in (0.2, 0.8):
        for k in range(5):
            xa = x0 + 2.0 + k * 7.4
            bays.append((xa, frac * Sx - 2.4, xa + 6.0, frac * Sx + 2.4))
    extra = None; tdisp = None
    if state == "damaged":
        extra = H.torn((x0 + x1) / 2 + 3.0, Sx * 0.48, 5.0, 3.6, 0.7); tdisp = curl(0, 0, 1, 1, 0.3)
    if dst:
        a = c.rng.random(4) * TAU
        def extra(u, s, a=a):
            low = np.minimum(np.asarray(s), Sx - np.asarray(s))
            top = 3.5 + 4.0 * (0.5 + 0.5 * np.sin((np.asarray(u) - x0) * 0.35 + a[0])) + 1.2 * np.sin((np.asarray(u) - x0) * 1.3 + a[1]) + 0.5 * np.abs(((np.asarray(u) * 1.7) % 2) - 1)
            return top - low
    hl = [] if dst else bays
    if state == "damaged":
        hl = [q for q in bays if not (abs((q[0] + q[2]) / 2 - ((x0 + x1) / 2 + 3.0)) < 6 and 0.3 * Sx < (q[1] + q[3]) / 2 < 0.7 * Sx)]
    kp = rect_keep(hl, extra) if (hl or extra is not None) else None
    barrel(c, "hangarroof", ax, org, x0, x1, Sx, cs, keep=kp, per=1.53, amp=0.07, thick=0.1, tear_disp=tdisp, rib_u=True,
           u_extra=[x for q in hl for x in (q[0], q[2])], v_extra=[x for q in hl for x in (q[1], q[3])], fine_s=0.8 if kp is not None else None)
    if state == "damaged":
        barrel(c, "interior", ax, org, x0, x1, Sx, cs, keep=None, flip_inside=True, fine_s=2.0)
    # arch frames: standing in the wreck, bolted ribs on the roof otherwise
    stations = list(np.arange(x0 + 1.5, x1, 3.06))
    for k, u in enumerate(stations):
        if dst and k % 2:
            continue
        arc_rib(c, ax, org, u, cs, Sx, 0.12 if dst else 0.1, mat="steel", n=48 if fine else 16, off=0.0 if dst else 0.07, s0=0.0, s1=Sx if not dst else Sx * (0.55 + 0.25 * ((k * 7) % 5) / 4))
    if not dst:
        for q in hl:
            w_ = q[2] - q[0]
            sc = (q[1] + q[3]) / 2
            wx, hy = cs(np.array(sc))
            nrm = unit(V([0, float(hy) - yc, float(wx)]))
            tang = unit(np.cross(nrm, V([1.0, 0, 0])))
            skylight(c, V([(q[0] + q[2]) / 2, float(hy), float(wx)]), V([1.0, 0, 0]), tang, w_, q[3] - q[1], "paint", (3, 2), nrm)
            b.box("paint", V([(q[0] + q[2]) / 2, float(hy), float(wx)]) + nrm * 0.1, (w_ + 0.3, 0.1, 0.2), np.stack([V([1.0, 0, 0]), nrm, tang], 1)) if False else None
    # panelled side walls with a long window band; pale, seams every 3.2 m
    band_h = (1.9, 3.3)
    bandx = [(x - x0 - 2.5, band_h[0] - 0.3, x - x0 + 2.5, band_h[1] - 0.3) for x in np.arange(x0 + 3.2, x1 - 2.0, 6.3)]
    for sgn in (-1, 1):
        zz = sgn * zh
        tearW = H.torn(L * 0.55, 4.8, 3.2, 2.6, 0.3) if (state == "damaged" and sgn > 0) else None
        kw = ridge_keep(L, wallh, c.rng, 0.1, 0.5) if dst else None
        hh = [] if dst else [q for q in bandx if not (tearW and abs((q[0] + q[2]) / 2 - L * 0.55) < 4.0)]
        clad(c, "facade", (x0 if sgn > 0 else x1, 0.3, zz), (1, 0, 0) if sgn > 0 else (-1, 0, 0), L, (0, 1, 0), wallh - 0.3, (0, 0, sgn), "flat", holes=hh, extra=tearW or kw,
             thick=0.15, edge_mat="paint", tear_disp=curl(0, 0, 1, 1, 0.2) if tearW else None, v_extra=(3.0, 6.5) if tearW else ())
        if not dst:
            for q in hh:
                cx = x0 + (q[0] + q[2]) / 2 if sgn > 0 else x1 - (q[0] + q[2]) / 2
                b.quad("glass", V([cx, band_h[0] + 0.7, zz - sgn * 0.14]), V([1.0, 0, 0]), V([0, 1.0, 0]), q[2] - q[0], 1.4, (0, 1, 1, 0), normal=(0, 0, sgn))
                for m in range(1, 4):
                    b.box("paint", (cx - (q[2] - q[0]) / 2 + (q[2] - q[0]) * m / 4, band_h[0] + 0.7, zz - sgn * 0.08), (0.08, 1.4, 0.1))
            for xs in np.arange(x0 + 3.2, x1 - 1.0, 3.2):                          # panel seams
                if fine:
                    b.box("paint", (xs, wallh / 2 + 0.3, zz + sgn * 0.03), (0.09, wallh - 0.3, 0.06))
            b.box("steel", ((x0 + x1) / 2, 0.55, zz + sgn * 0.05), (L, 0.5, 0.12))         # dark base
            gutter(c, (x0 - 0.2, 10.0, zz + sgn * 0.25), (x1 + 0.2, 10.0, zz + sgn * 0.25), 0.12)
            for xx in (x0 + 1, x1 - 1):
                downpipe(c, xx, zz + sgn * 0.3, 0.3, 9.9, 0.1)
            b.quad("trim", V([(x0 + x1) / 2, 9.2, zz + sgn * 0.05]), V([1.0, 0, 0]), V([0, 1.0, 0]), L, 0.7, (0, 0.5, L * 0.3, 0), normal=(0, 0, sgn), band=6, col=(1, 0, 0))
            for k, xx in enumerate(np.linspace(x0 + 2, x1 - 2, 9)):
                c.decal_wall("streak_a" if k % 2 else "streak_b", (xx, 0, zz), (1, 0, 0), 2.4, 1.0, 9.8, (0, 0, sgn), off=0.07)
    for xx, nx, door in ((x0, -1, (16.0, 8.6)), (x1, 1, (5.0, 6.0))):
        hfun = lambda w, r=r, yc=yc: yc + np.sqrt(np.maximum(r * r - np.asarray(w) ** 2, 0)) - 0.15
        hole = [] if dst else [(zh - door[0] / 2, 0.0, zh + door[0] / 2, door[1])]
        ex = (lambda u, v, hf=hfun: hf(np.asarray(u) - zh) - np.asarray(v))
        if dst:
            ex = (lambda u, v, hf=hfun, xx=xx: np.minimum(hf(np.asarray(u) - zh) - np.asarray(v), 2.5 + 2.0 * np.sin(np.asarray(u) * 0.8 + xx) + 1.0 * np.sin(np.asarray(u) * 2.9) - np.asarray(v)))
        clad(c, "facade", (xx, 0.3, -zh if nx < 0 else zh), (0, 0, 1) if nx < 0 else (0, 0, -1), 2 * zh, (0, 1, 0), 15.6, (nx, 0, 0), "flat", holes=hole, extra=ex, thick=0.4 if hole else 0.1, edge_mat="paint")
        if not dst:
            roller_door(c, (xx, 0.3, 0), (0, 0, 1) if nx < 0 else (0, 0, -1), (nx, 0, 0), door[0], door[1], 0.3)
            b.box("galv", (xx + nx * 0.5, door[1] + 0.9, 0), (1.0, 0.35, door[0] + 1.6))
            for sz in (-1, 1):
                b.box("steel", (xx + nx * 0.2, door[1] / 2, sz * (door[0] / 2 + 0.3)), (0.5, door[1], 0.4))
            ss = np.linspace(0, Sx, 40 if fine else 14)
            w, h = cs(ss)
            b.sweep("paint", [(xx + nx * 0.1, float(hh) + 0.1, float(ww)) for ww, hh in zip(w, h)], 0.14, 6 if fine else 4)
    for (px, pz) in ((x0, -zh), (x1, -zh), (x0, zh), (x1, zh)):
        if not dst:
            b.box("paint", (px, wallh / 2 + 0.2, pz), (0.5, wallh, 0.5))
    if state == "damaged":
        interior_shell(c, x0, x1, -zh, zh, 9.0)
        for k in range(8):
            xx = x0 + 3 + k * 4.6
            timber(c, (xx, 9.9, zh - 0.5), (xx, 0.4, zh - 0.5), 0.3, 0.3, "steel")
        broken_boards(c, (x0 + L * 0.55, 4.8, zh), 7, (0, 0.2, 1), (3.0, 2.0), (1, 0, 0), 9, "paint", (1.5, 3.0))
        c.decal_ground("soot", (x0 + L * 0.55, zh + 3.0), 14, 10, 0.0, y=0.32)
    if dst:
        interior_shell(c, x0, x1, -zh, zh, 1.2)
        # a standing steel frame (columns and eave beams) with the first arches, and collapsed roof sections leaning on it
        for xx in np.arange(x0 + 1.5, x1, 6.12):
            for sz in (-1, 1):
                timber(c, (xx, 0.3, sz * (zh - 0.3)), (xx, 8.0 + c.rng.uniform(-1.5, 1.0), sz * (zh - 0.3)), 0.4, 0.4, "steel")
        for sz in (-1, 1):
            timber(c, (x0 + 1.5, 7.6, sz * (zh - 0.3)), (x0 + 1.5 + 18.0, 7.2, sz * (zh - 0.3)), 0.3, 0.3, "steel")
        for k, xx in enumerate(np.linspace(x0 + 6, x1 - 6, 4)):
            Rm = axis_angle(V([1.0, 0, 0]), c.rng.uniform(-0.45, 0.45)) @ axis_angle(V([0, 0, 1.0]), c.rng.uniform(-0.2, 0.2))
            ctr = V([xx, 1.2 + 0.7 * k, c.rng.uniform(-8, 8)])
            b.M = (Rm, ctr - Rm @ ctr)
            barrel(c, "hangarroof", ax, org, xx - 3.2, xx + 3.2, Sx, cs, keep=lambda u, s, k=k: 4.0 - np.abs(np.asarray(s) - Sx * (0.22 + 0.19 * k)), per=1.53, amp=0.07, thick=0.1, rib_u=True)
            b.M = None
        for k in range(10):
            a_ = V([c.rng.uniform(x0, x1), 0.5, c.rng.uniform(-zh, zh)])
            timber(c, a_, a_ + V([c.rng.uniform(-6, 6), c.rng.uniform(0.4, 2.0), c.rng.uniform(-6, 6)]), 0.3, 0.3, "steel")
        debris(c, 22, (x0, x1), (-zh, zh), 1.6, ("rust", "galv", "steel"))
        c.decal_ground("soot", ((x0 + x1) / 2, 0), 44, 44, 0.0, y=0.32)
    return c


# ====================================================================================================== vehicle hangar
def finned(c, p_low, dirv, L, up_dir, slen, gap=0.9, fin=0.22):
    """A ribbed (finned) roof slope: a darker galvanised sheet with pale ribs running down the slope."""
    if c.state == "destroyed":
        return
    n = unit(np.cross(unit(dirv), unit(up_dir)))
    n = n if n[1] > 0 else -n
    slab_sheet(c, "finroof", V(p_low) + n * 0.06, dirv, L, up_dir, slen, n, False, 0.08, None, None, None, 0.9)
    if c.fine:
        d, u = unit(dirv), unit(up_dir)
        Rm = np.stack([d, n, u], 1)
        for k in range(int(L / gap)):
            c.b.box("paint", V(p_low) + d * (gap * (k + 0.5)) + u * slen / 2 + n * (0.06 + fin / 2), (0.1, fin, slen), Rm)


def vehiclehangar(state, lod, seed):
    H.WALL[:] = ["facade", "flat"]; H.ROOF[:] = ["roofclean"]
    c = Ctx(state, lod, seed, breach=(9.7, 3.6, -1.0, 3.2), ledges=[(7.21, 3.0, 0.9), (3.63, 1.6, 0.8), (0.8, 0.9, 0.6)], ao_rings=[(7.21, 1.4, 0.4), (3.63, 1.0, 0.4)], ground_h=2.0)
    b = c.b
    fine = c.fine
    dst = state == "destroyed"
    X0, X1, Z0, Z1, HH = -11.335, 9.729, -7.609, 5.597, 7.21
    cx0 = (X0 + X1) / 2
    strips = lambda W, n=3, y=(2.2, 3.1): [(1.0 + k * (W - 2.0) / n, y[0], 1.0 + k * (W - 2.0) / n + (W - 2.0) / n - 0.6, y[1]) for k in range(n)]
    holes = {"-x": strips(Z1 - Z0, 3), "+x": strips(Z1 - Z0, 3), "-z": [], "+z": []}
    # the big recessed door with its painted "13" on the -z end of the hall: dark leaf, slats, a number plate
    if not dst:
        holes["-z"] = [(X1 - X0 - 11.5, 0.0, X1 - X0 - 5.5, 6.2)]
    H.hall(c, X0, X1, Z0, Z1, HH, None, 0.2, holes, True, tint_y=HH - 0.6, dmg_side=1)
    if not dst:
        dc = X1 - 8.5
        roller_door(c, (dc, 0.2, Z0), (1, 0, 0), (0, 0, -1), 6.0, 6.0, 0.2, tint=False)
        b.box("steel", (dc, 6.6, Z0 - 0.15), (6.8, 0.35, 0.5))
        c.decal_wall("id_plate", (dc, 0, Z0), (-1, 0, 0), 3.0, 3.2, 5.0, (0, 0, -1), off=0.32)
        for j, d in enumerate((1, 3)):
            c.decal_wall("id_plate", (dc + (0.6 if j else -0.6) * -1 * -1, 0, Z0), (-1, 0, 0), 0.9, 3.5, 4.7, (0, 0, -1), uv=digit_uv(d), off=0.34)
        for k, (wx, nx) in enumerate(((X0, -1), (X1, 1))):
            for (a, b_, c_, d_) in strips(Z1 - Z0, 3):
                if state == "damaged" and nx == 1 and abs((a + c_) / 2 - 6.5) < 3.2:
                    continue
                zc = Z1 - (a + c_) / 2 if False else Z0 + (a + c_) / 2
                b.quad("glass", V([wx - nx * 0.14, 0.2 + (b_ + d_) / 2, zc]), V([0, 0, 1.0]), V([0, 1.0, 0]), c_ - a, d_ - b_, (0, 1, 1, 0), normal=(nx, 0, 0))
        # roofs: four finned mansard slopes round a pale flat top with a parapet, skylight curbs and the duct arch
        fz0, fz1 = -5.709, 3.865
        sl = H.slope_roof
        finned(c, (X0 - 0.3, HH + 0.06, Z0 - 0.3), (1, 0, 0), X1 - X0 + 0.6, (0, 2.317, fz0 - Z0 + 0.3), math.hypot(2.317, fz0 - Z0 + 0.3))
        finned(c, (X0 - 0.3, HH + 0.06, Z1 + 0.3), (1, 0, 0), X1 - X0 + 0.6, (0, 2.317, fz1 - Z1 - 0.3), math.hypot(2.317, fz1 - Z1 - 0.3))
        for sx, fx in ((X0 - 0.3, X0 + 1.7), (X1 + 0.3, X1 - 1.7)):
            finned(c, (sx, HH + 0.06, Z0), (0, 0, 1), Z1 - Z0, (fx - sx, 2.317, 0), math.hypot(fx - sx, 2.317))
        H.flat_roof(c, X0 + 1.7, X1 - 1.7, fz0, fz1, 9.527, tear=(state == "damaged"))
        for (px, pz, w_, d_) in ((cx0, fz0 + 0.1, X1 - X0 - 3.0, 0.3), (cx0, fz1 - 0.1, X1 - X0 - 3.0, 0.3)):
            b.box("paint", (px, 9.7, pz), (w_, 0.35, d_))
        for (px, pz, w_, d_) in ((X0 + 1.8, -1.0, 0.3, fz1 - fz0), (X1 - 1.8, -1.0, 0.3, fz1 - fz0)):
            b.box("paint", (px, 9.7, pz), (w_, 0.35, d_))
        for xx in (-4.5, 0.0, 4.5):
            b.box("paint", (xx, 9.9, -1.0), (2.0, 0.4, 3.2)); b.quad("glass", V([xx, 10.12, -1.0]), V([1.0, 0, 0]), V([0, 0, 1.0]), 1.7, 2.9, (0, 1, 1, 0), normal=(0, 1, 0))
        for k in range(3):
            b.box("steel", (X0 + 3 + k * 5.5, 9.9, fz1 - 0.9), (0.9, 0.7, 0.9)); b.tube("steel", (X0 + 3 + k * 5.5, 10.2, fz1 - 0.9), (X0 + 3 + k * 5.5, 11.0, fz1 - 0.9), 0.06, 6)
        # duct arch: a rectangular arch from the -z lean-to over the eaves to 11.9 m and down on the roof
        for dz in (-0.7, 0.7):
            b.box("paint", (5.05, 6.0, -6.0 + dz), (1.7, 11.8, 0.5)) if False else None
        b.box("paint", (5.05, 7.8, -9.0), (1.7, 8.2, 1.0)); b.box("paint", (5.05, 11.4, -6.5), (1.7, 1.0, 5.0)); b.box("paint", (5.05, 10.7, -4.0), (1.7, 2.4, 1.0))
        b.box("steel", (5.05, 11.95, -6.5), (1.9, 0.1, 5.2))
        for sx in (X0 - 0.15, X1 + 0.15):
            gutter(c, (sx, HH - 0.1, Z0 - 0.2), (sx, HH - 0.2, Z1 + 0.2)); downpipe(c, sx, Z1 + 0.1, 0.3, HH - 0.2)
    # lean-tos: low walls, finned slopes rising to flat tops, doors, window strips
    H.hall(c, -10.105, 9.21, Z1, 10.478, 3.63, None, 0.2, {"+z": [(1.0, 1.8, 4.5, 2.8), (5.5, 1.8, 9.0, 2.8), (10.0, 1.8, 13.5, 2.8), (14.5, 1.8, 18.0, 2.8)] if not dst else []}, False, tint_y=3.0)
    H.hall(c, -1.489, 8.082, -12.274, Z0, 3.63, None, 0.2, {"-z": [(1.4, 1.8, 3.4, 2.8), (5.0, 1.8, 7.0, 2.8)] if not dst else []}, False)
    H.hall(c, -9.723, -1.294, -11.448, -7.687, 3.66, None, 0.2, {"-z": [(1.2, 0.0, 2.6, 2.2)] if not dst else []}, False)
    if not dst:
        for (xa, xb, za, zb) in ((-10.2, 9.3, Z1, 10.58), (-1.6, 8.2, Z0, -12.4)):
            sgn = 1 if za > 0 else -1
            finned(c, (xa, 3.69, za), (1, 0, 0), xb - xa, (0, 2.64, zb - za), math.hypot(2.64, zb - za))
        H.flat_roof(c, -9.723, -1.294, -11.448, -7.687, 3.66)
        for k, xx in enumerate(np.linspace(-10, 9, 7)):
            c.decal_wall("streak_a" if k % 2 else "streak_b", (xx, 0, 10.478), (1, 0, 0), 2.2, 0.6, 3.5, (0, 0, 1), off=0.07)
    else:
        # wreck: the hall's steel frame standing (columns, eave beams), the big door frame, roof slopes down across the floor, the duct fallen
        for xx in np.linspace(X0 + 0.4, X1 - 0.4, 6):
            for zz in (Z0 + 0.3, Z1 - 0.3):
                timber(c, (xx, 0.3, zz), (xx, 4.0 + c.rng.uniform(-0.8, 3.2), zz), 0.35, 0.35, "steel")
        for zz in (Z0 + 0.3, Z1 - 0.3):
            timber(c, (X0 + 0.4, 5.6, zz), (X0 + 12.0, 5.2, zz), 0.3, 0.3, "steel")
        for k, (xx, zz) in enumerate(((-6, -3), (2, -2), (6, 3), (-4, 3))):
            Rm = axis_angle(V([1.0, 0, 0]), c.rng.uniform(-0.5, 0.5)) @ axis_angle(V([0, 0, 1.0]), c.rng.uniform(-0.5, 0.5))
            ctr = V([xx, 1.0 + 0.5 * k, zz])
            b.M = (Rm, ctr - Rm @ ctr)
            slab_sheet(c, "finroof", ctr + V([-3.0, 0, -1.4]), (1, 0, 0), 6.0, (0, 0, 1), 2.8, (0, 1, 0), False, 0.08, None, None, None, 0.9)
            for q in range(6):
                b.box("paint", ctr + V([-2.6 + q * 1.0, 0.18, 0]), (0.1, 0.22, 2.8))
            b.M = None
        H.collapse(c, -10.1, 9.2, Z1, 10.4, 3.6, 2)
        timber(c, (5.05, 0.6, -9), (5.05, 1.2, 2.0), 1.7, 1.0, "paint")
        c.decal_ground("soot", (-0.8, -1.0), 36, 34, 0.0, y=0.25)
    if state == "damaged":
        c.decal_ground("soot", (12.5, -1.0), 8, 8, 0.0, y=0.26)
    return c


# ============================================================================================================== repairbay
def window_grid(c, mat_wall, p0, dirv, L, h, normal, cols, rows, y0=1.0, y1=None, gx=0.5, gy=0.5, state_hole=None):
    """holes for a facade window grid (list of rects)"""
    y1 = h - 0.9 if y1 is None else y1
    cw = (L - 2 * gx) / cols
    ch = (y1 - y0) / rows
    return [(gx + k * cw + 0.15, y0 + r_ * ch + 0.15, gx + (k + 1) * cw - 0.15, y0 + (r_ + 1) * ch - 0.15) for k in range(cols) for r_ in range(rows)]


def facade_block(c, x0, x1, z0, z1, h, grids, y0=0.2, main=False, tint=None, dmg_side=1):
    """A block with window grids on the faces given in `grids` ({face: (cols, rows)}) and dark glass behind each opening."""
    b = c.b
    dst = c.state == "destroyed"
    W, D = x1 - x0, z1 - z0
    holes = {}
    for key, (cols, rows) in grids.items():
        Ln = D if key in ("+x", "-x") else W
        holes[key] = [] if dst else window_grid(c, None, None, None, Ln, h, None, cols, rows, 1.0, h - 0.9)
    H.hall(c, x0, x1, z0, z1, h, None, y0, holes, main, tint_y=tint, dmg_side=dmg_side)
    if not dst:
        for key, hl in holes.items():
            for (a, b_, c_, d_) in hl:
                if main and c.state == "damaged" and key == ("+x" if dmg_side > 0 else "-x") and abs((a + c_) / 2 - D_(key, W, D) * 0.5) < min(D_(key, W, D) * 0.22, 3.0) + 0.6:
                    continue
                wc = (a + c_) / 2; hc = y0 + (b_ + d_) / 2
                if key == "+x":
                    pos, nrm, ax = V([x1 - 0.14, hc, z0 + wc]), (1, 0, 0), V([0, 0, 1.0])
                elif key == "-x":
                    pos, nrm, ax = V([x0 + 0.14, hc, z1 - wc]), (-1, 0, 0), V([0, 0, 1.0])
                elif key == "-z":
                    pos, nrm, ax = V([x0 + wc, hc, z0 + 0.14]), (0, 0, -1), V([1.0, 0, 0])
                else:
                    pos, nrm, ax = V([x1 - wc, hc, z1 - 0.14]), (0, 0, 1), V([1.0, 0, 0])
                b.quad("glass", pos, ax, V([0, 1.0, 0]), c_ - a, d_ - b_, (0, 1, 1, 0), normal=nrm)


def D_(key, W, D):
    return D if key in ("+x", "-x") else W


def roof_plant(c, x0, x1, z0, z1, y, n=4):
    """parapet, AC units with fans, round vents, a stair bulkhead, light poles."""
    b = c.b
    if c.state == "destroyed":
        return
    W, D = x1 - x0, z1 - z0
    for (cx, cz, w, d) in ((0.5, 0.5, W - 0.2, 0.35), (0.5, D - 0.5, W - 0.2, 0.35)):
        b.box("paint", (x0 + cx + (W - 1) / 2 + 0.0, y + 0.25, z0 + cz + 0.0), (W - 0.2, 0.4, 0.35))
    for (cx, cz) in ((0.5, 0.5), (W - 0.5, 0.5)):
        pass
    b.box("paint", (x0 + 0.4, y + 0.25, (z0 + z1) / 2), (0.35, 0.4, D)); b.box("paint", (x1 - 0.4, y + 0.25, (z0 + z1) / 2), (0.35, 0.4, D))
    rng = c.rng
    for k in range(n):
        ux, uz = x0 + 1.2 + (W - 2.4) * (0.2 + 0.6 * ((k * 0.37) % 1)), z0 + 1.2 + (D - 2.4) * (0.15 + 0.7 * ((k * 0.61) % 1))
        b.box("steel", (ux, y + 0.5, uz), (1.4, 0.9, 1.1))
        b.revolve("steel", [(0.4, y + 0.95), (0.4, y + 1.0), (0.0, y + 1.0)], 12 if c.fine else 6, cx=ux, cz=uz, uref=1.0)
        b.box("galv", (ux, y + 0.35, uz + 0.58), (1.2, 0.6, 0.05))
    for k in range(3):
        vx, vz = x0 + 2.0 + k * (W - 4.0) / 2, z0 + D * 0.5 + (k - 1) * 1.1
        b.tube("galv", (vx, y, vz), (vx, y + 0.9, vz), 0.22, 10 if c.fine else 5)
        b.revolve("galv", [(0.3, y + 0.9), (0.0, y + 1.1)], 10 if c.fine else 5, cx=vx, cz=vz, uref=1.0)
    b.box("paint", (x0 + W * 0.3, y + 0.9, z0 + D * 0.75), (1.8, 1.5, 1.8))
    for px, pz in ((x0 + 0.6, z0 + 0.6), (x1 - 0.6, z1 - 0.6)):
        b.tube("steel", (px, y, pz), (px, y + 2.6, pz), 0.04, 5)
        b.revolve("steel", [(0.12, y + 2.6), (0.12, y + 2.7), (0.0, y + 2.8)], 8, cx=px, cz=pz, uref=1.0)


def gantry_tower(c, tx, tz, sgn, y):
    """A hooded tower: a chamfered cab with a rounded hood, vents, a beacon and a glazed front."""
    b = c.b
    if c.state == "destroyed":
        return
    b.box("paint", (tx, y + 1.0, tz), (5.58, 2.0, 2.1))
    b.box("paint", (tx, y + 2.15, tz), (5.0, 0.4, 1.7))
    b.revolve("paint", [(0.95, y + 2.3), (0.9, y + 2.7), (0.0, y + 2.95)], 14 if c.fine else 8, cx=tx - 1.6, cz=tz, uref=2.0)
    b.revolve("paint", [(0.95, y + 2.3), (0.9, y + 2.7), (0.0, y + 2.95)], 14 if c.fine else 8, cx=tx + 1.6, cz=tz, uref=2.0)
    b.box("glass", (tx, y + 1.2, tz - sgn * 1.07), (4.6, 0.9, 0.06))
    for k in range(5 if c.fine else 2):
        b.box("steel", (tx + 2.9, y + 0.5 + k * 0.28, tz), (0.06, 0.12, 1.4))
    for dx in (-2.4, 2.4):
        b.revolve("steel", [(0.14, y + 2.4), (0.14, y + 2.55), (0.22, y + 2.65), (0.1, y + 2.85), (0.0, y + 2.9)], 12 if c.fine else 6, cx=tx + dx, cz=tz + sgn * 0.7, uref=1.0)


def repairbay(state, lod, seed):
    H.WALL[:] = ["facade", "flat"]; H.ROOF[:] = ["roofclean"]
    c = Ctx(state, lod, seed, breach=(-3.6, 3.0, 7.0, 3.0), ledges=[(4.58, 2.6, 0.9), (9.06, 3.0, 0.9)], ao_rings=[(4.58, 1.2, 0.4)], ground_h=2.0)
    b = c.b
    fine = c.fine
    dst = state == "destroyed"
    b.box("concrete", (0.6, 0.075, 0.0), (8.8, 0.15, 11.0))
    b.quad("trim", V([0.2, 0.36, 0.0]), V([1.0, 0, 0]), V([0, 0, 1.0]), 7.4, 11.0, (0, 0, 7.4 * 0.3, 11.0 * 0.3), normal=(0, 1, 0), band=1)
    # the tall block: 9.06 m, many window bands, dark glass; a lower annex and a porch
    facade_block(c, 5.08, 9.33, -9.71, 6.35, 9.06, {"+x": (7, 4), "-x": (7, 4), "+z": (2, 4), "-z": (2, 4)}, 0.2, False, tint=8.4)
    facade_block(c, 5.08, 9.33, -6.55, 0.0, 6.86, {}, 0.2, False)
    facade_block(c, -3.66, 5.08, 5.46, 9.71, 4.58, {"+z": (3, 2), "-x": (2, 2), "+x": (2, 2)}, 0.2, True, tint=4.0, dmg_side=-1)
    facade_block(c, -3.66, 5.08, -9.71, -5.46, 4.58, {"-z": (3, 2), "-x": (2, 2), "+x": (2, 2)}, 0.2, False, tint=4.0)
    if not dst:
        for (x0_, z0_, z1_) in ((-3.66, 5.46, 9.71), (-3.66, -9.71, -5.46)):
            H.flat_roof(c, x0_, 5.08, z0_, z1_, 4.58, tear=(state == "damaged" and z0_ > 0))
        # tall block: a pitched glazed-and-ribbed roof section on the left half, flat plant roof on the right
        H.flat_roof(c, 5.08, 9.33, -9.71, 6.35, 9.06)
        roof_plant(c, 5.08, 9.33, -9.71, 6.35, 9.06, 5)
        roof_plant(c, -3.66, 5.08, 5.46, 9.71, 4.58, 2)
        roof_plant(c, -3.66, 5.08, -9.71, -5.46, 4.58, 2)
        # lower annex: a sloped glazed roof with frames (the original's glazed roof-light structure)
        sl = V([0.0, 6.86 - 5.0, 0.0])
        for k in range(3):
            zc = -5.6 + k * 2.1
            skylight(c, V([7.2, 6.9, zc]), V([0, 0, 1.0]), V([1.0, 0, 0]), 1.9, 3.8, "paint", (1, 3), V([0, 1.0, 0]))
        # bay doors, two leaves, a hazard frame
        roller_door(c, (4.94, 0.2, -2.7), (0, 0, 1), (-1, 0, 0), 3.2, 3.6, 0.2)
        roller_door(c, (4.94, 0.2, 2.7), (0, 0, 1), (-1, 0, 0), 3.2, 3.6, 0.2)
        for sz in (-1, 1):
            gantry_tower(c, -0.03, sz * 7.55, sz, 4.58)
        # the dark open truss bridge: four chords, ring frames and diagonals, orange-white striped side plates and closed end collars
        yb = 6.55
        for (dy, dx) in ((0.95, 0.95), (0.95, -0.95), (-0.95, 0.95), (-0.95, -0.95)):
            b.tube("steel", (-0.03 + dx, yb + dy, -6.5), (-0.03 + dx, yb + dy, 6.5), 0.09, 6)
        for zz in np.linspace(-6.0, 6.0, 7 if fine else 3):
            ring = [(-0.03 + 0.95, yb + 0.95, zz), (-0.03 - 0.95, yb + 0.95, zz), (-0.03 - 0.95, yb - 0.95, zz), (-0.03 + 0.95, yb - 0.95, zz)]
            b.sweep("steel", ring, 0.06, 5, closed=True)
        for k in range(6 if fine else 2):
            z0_ = -6.0 + k * 2.0
            b.tube("steel", (-0.98, yb - 0.95, z0_), (-0.98, yb + 0.95, z0_ + 2.0), 0.05, 5)
            b.tube("steel", (0.92, yb + 0.95, z0_), (0.92, yb - 0.95, z0_ + 2.0), 0.05, 5)
        for sx in (-1, 1):
            b.quad("trim", V([-0.03 + sx * 0.97, yb, 0.0]), V([0, 0, 1.0]), V([0, 1.0, 0]), 11.0, 0.9, (0, 0.45, 11.0 * 0.3, 0), normal=(sx, 0, 0), band=0)
        for sz in (-1, 1):
            b.box("steel", (-0.03, yb, sz * 5.8), (2.1, 2.1, 0.5))
        for k, zz in enumerate(np.linspace(-9.0, 5.0, 8)):
            c.decal_wall("streak_a" if k % 2 else "streak_b", (9.33, 0, zz), (0, 0, 1), 1.8, 0.8, 8.8, (1, 0, 0), off=0.07)
        for k, zz in enumerate(np.linspace(-8.0, 5.0, 5)):
            c.decal_wall("rust_bleed", (9.33, 0, zz), (0, 0, 1), 1.2, 0.6, 2.6, (1, 0, 0), off=0.07)
    else:
        # wreck: the tall block's steel frame and floor slabs standing, tower caps and the truss bridge down, roof sections fallen
        for xx in (5.2, 9.2):
            for zz in np.linspace(-9.6, 6.2, 5):
                timber(c, (xx, 0.3, zz), (xx, 5.0 + c.rng.uniform(-1.0, 3.5), zz), 0.4, 0.4, "steel")
        for yy in (3.2, 6.0):
            for zz in (-9.6, 6.2):
                timber(c, (5.2, yy, zz), (9.2, yy + c.rng.uniform(-0.4, 0.2), zz), 0.3, 0.3, "steel")
            b.box("concrete_dark", (7.2, yy, -1.4), (4.1, 0.25, 11.0 + c.rng.uniform(-2, 0)), axis_angle(V([0, 0, 1.0]), c.rng.uniform(-0.08, 0.08)))
        for sz in (-1, 1):
            timber(c, (-0.03, 0.8, sz * 7.0), (c.rng.uniform(-1, 1), 1.4, sz * 4.0), 1.8, 1.4, "paint")
        b.sweep("steel", [(-3.0, 0.8, -4.0), (-1.0, 0.6, -1.0), (2.0, 0.7, 2.0), (3.5, 0.7, 4.0)], 0.5, 6)
        for k in range(10):
            a_ = V([c.rng.uniform(-3.5, 9.0), 0.4, c.rng.uniform(-9, 9)])
            timber(c, a_, a_ + V([c.rng.uniform(-3, 3), c.rng.uniform(0.2, 1.0), c.rng.uniform(-3, 3)]), 0.18, 0.18, "steel")
        H.collapse(c, -3.66, 5.08, 5.46, 9.71, 4.0, 2)
        H.collapse(c, -3.66, 5.08, -9.71, -5.46, 4.0, 2)
        H.collapse(c, 5.08, 9.33, -9.71, 6.35, 9.0, 3)
        c.decal_ground("soot", (1.0, 0.0), 26, 30, 0.0, y=0.4)
    if state == "damaged":
        c.decal_ground("soot", (-6.0, 7.0), 8, 8, 0.0, y=0.4)
    return c


H.MEMBERS.update({
    "hangar": (hangar, H.MEMBERS["hangar"][1]),
    "vehiclehangar": (vehiclehangar, H.MEMBERS["vehiclehangar"][1]),
    "repairbay": (repairbay, H.MEMBERS["repairbay"][1]),
})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("app")
    ap.add_argument("--out", default=str(ROOT / "game/assets/v3/objects"))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    for app in (["hangar", "vehiclehangar", "repairbay"] if a.app == "all" else [a.app]):
        H.build_member(app, out)


if __name__ == "__main__":
    main()
