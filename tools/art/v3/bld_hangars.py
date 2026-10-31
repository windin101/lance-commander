#!/usr/bin/env python3
"""v3 quonset huts and hangars (LANCE-21 family 2): quonsetclean, quonset, quonset2, hangar, vehiclehangar, repairbay, portable.

    python3 -I tools/art/v3/bld_hangars.py <app>|all [--out game/assets/v3/objects]

Contract as bld_tanks.py / bld_family.py: <app>.glb, <app>_damaged.glb, <app>_destroyed.glb with nodes lod0 and lod1, <app>.v3.json.
The three quonset variants share one generator (clean / weathered with sandbags / roof dish); the barrel-roofed hall and the hut are
true arcs (the originals' 10-facet and 5-facet polylines become circles through the same eaves and crown). Dimensions come from the
Shared Source originals' bounds and tools/cad/<app>_cad.py. Planar cladding, openings, tears, interiors and wrecks use bld_sheds.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bld_kit import Ctx, axis_angle, TAU  # noqa: E402
from bld_mesh import Builder, unit  # noqa: E402
import bld_sheds as S  # noqa: E402
from bld_sheds import V, clad, slab_sheet, interior_shell, timber, window, roller_door, lamp, debris, broken_boards, torn, ridge_keep, curl, gutter, downpipe, rect_keep  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
LOD_M = 80.0
STATES = ("intact", "damaged", "destroyed")


# =============================================================================================================== barrel hulls
def arch_fns(kind, **kw):
    """cross-section of an arched hull: returns (S, cs) with cs(s) -> (lateral w, height h) for arc length s in 0..S."""
    if kind == "semi":
        R = kw["R"]
        return math.pi * R, (lambda s: (-R * np.cos(np.asarray(s) / R), R * np.sin(np.asarray(s) / R)))
    r, yc, ph = kw["r"], kw["yc"], kw["phi"]
    return 2 * ph * r, (lambda s: (r * np.sin(np.asarray(s) / r - ph), yc + r * np.cos(np.asarray(s) / r - ph)))


def barrel(c, mat, axis, origin, u0, u1, S, cs, keep=None, per=0.0, amp=0.0, thick=0.0, flip_inside=False, tear_disp=None, extra_disp=None,
           inset=0.0, band=0, col=(0, 0, 0), s0=0.0, s1=None, v_extra=(), u_extra=(), fine_s=None, edge_mat="rust", rib_u=False):
    """The hull surface along `axis` (unit, horizontal) from u0 to u1, cross-section cs(s), s in s0..s1, with optional ribs across the
    hull's arc (period per, amplitude amp, geometry at LOD0 only), a clip keep(u, s) and tear/sag displacement."""
    b = c.b
    s1 = S if s1 is None else s1
    ax = unit(axis)
    side = unit(np.cross(V([0, 1.0, 0]), ax))
    org = V(origin, float)
    fine = c.fine
    rib = per > 0 and fine
    ns = int((s1 - s0) / (per / 4)) + 1 if (rib and not rib_u) else max(4, int((s1 - s0) / 0.9))
    if fine_s:
        ns = max(ns, int((s1 - s0) / fine_s))
    nu = int((u1 - u0) / (per / 4)) + 1 if (rib and rib_u) else (3 if keep is None else max(5, int((u1 - u0) / 0.45)))
    us = np.unique(np.round(np.r_[np.linspace(u0, u1, nu + 1), list(u_extra)], 5))
    ss = np.unique(np.round(np.r_[np.linspace(s0, s1, ns + 1), list(v_extra)], 5))
    def pos(u, s):
        w, h = cs(s)
        w = np.asarray(w)[..., None]; h = np.asarray(h)[..., None]
        k = 1.0 - inset / max(1e-6, 1.0)
        pp = org + np.asarray(u)[..., None] * ax + w * side + h * V([0, 1.0, 0])
        return pp
    mid = pos(np.array(0.5 * (u0 + u1)), np.array(0.5 * (s0 + s1)))
    en = 1e-3
    du = pos(np.array(0.5 * (u0 + u1)) + en, np.array(0.5 * (s0 + s1))) - pos(np.array(0.5 * (u0 + u1)) - en, np.array(0.5 * (s0 + s1)))
    ds = pos(np.array(0.5 * (u0 + u1)), np.array(0.5 * (s0 + s1)) + en) - pos(np.array(0.5 * (u0 + u1)), np.array(0.5 * (s0 + s1)) - en)
    n = np.cross(du, ds)
    up_out = (mid - org) * V([1.0, 0, 1.0]) * 0 + V([0, 1.0, 0])
    flip = float(np.dot(n, up_out)) < 0
    if flip_inside:
        flip = not flip
    def disp(u, s, k):
        d = (amp * np.sin(TAU * (np.asarray(u) if rib_u else np.asarray(s)) / per)) if rib else 0.0
        if extra_disp is not None:
            d = d + extra_disp(u, s, k)
        if tear_disp is not None:
            d = d + tear_disp(u, s, k)
        return d
    b.cut_param(mat, pos, us, ss, keep, uv=(lambda u, s: np.stack([u, s], -1)) if rib_u else (lambda u, s: np.stack([s, u], -1)), flip=flip, band=band, col=col, thickness=thick, edge_mat=edge_mat,
                disp=disp if (rib or extra_disp is not None or tear_disp is not None) else None)


def arc_rib(c, axis, origin, u, cs, S, r=0.05, s0=0.0, s1=None, mat="steel", n=28, off=0.04):
    """A tube following the hull arc at station u (a bolted arch rib), pushed outward a little."""
    s1 = S if s1 is None else s1
    ax = unit(axis); side = unit(np.cross(V([0, 1.0, 0]), ax))
    ss = np.linspace(s0, s1, n if c.fine else max(8, n // 3))
    w, h = cs(ss)
    pts = V(origin) + u * ax + np.outer(w, side) + np.outer(h, V([0, 1.0, 0]))
    # outward normal in the section plane
    dw = np.gradient(np.asarray(w, float)); dh = np.gradient(np.asarray(h, float))
    nrm = np.stack([dh, -dw], 1); nrm = nrm / (np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-9)
    nrm = np.where((nrm[:, 1:2] < 0) & (np.asarray(h)[:, None] > 0.2), -nrm, nrm)
    pts = pts + (np.outer(nrm[:, 0], side) + np.outer(nrm[:, 1], V([0, 1.0, 0]))) * off
    c.b.sweep(mat, pts, r, 6 if c.fine else 4, caps=True)


# ======================================================================================================== the quonset huts
def quonset(variant):
    def build(state, lod, seed):
        c = Ctx(state, lod, seed, breach=(3.0, 2.6, -4.0, 2.6), ledges=[(4.2, 2.6, 0.9), (0.9, 0.9, 0.6)], ao_rings=[(0.8, 0.7, 0.35)], ground_h=1.5)
        b = c.b
        fine = c.fine
        dirty = variant != "clean"
        R = {"clean": 4.21, "dirty": 4.25, "dish": 4.24}[variant]
        z0, z1 = {"clean": (-12.67, 4.17), "dirty": (-12.68, 4.15), "dish": (-12.72, 4.18)}[variant]
        L = z1 - z0
        Sx, cs = arch_fns("semi", R=R)
        ax = V([0, 0, 1.0]); org = V([0, 0, 0.0])
        dst = state == "destroyed"
        hull = "hullsheet" if dirty else "hullclean"
        b.box("concrete", (0, 0.1, (z0 + z1) / 2), (2 * R + 0.5, 0.2, L + 0.5))
        # side windows: holes in the hull between the arch ribs, glass behind, a hood above each
        zs = [z0 + 2.2 + 2.5 * k for k in range(6)]
        wins = []
        for zc in zs:
            wins.append((zc - 0.6, 1.4, zc + 0.6, 2.2))                       # left side (s from the left base)
            wins.append((zc - 0.6, Sx - 2.2, zc + 0.6, Sx - 1.4))             # right side
        extra = None
        tdisp = None
        if state == "damaged":
            extra = torn(z0 + L * 0.42, Sx * 0.62, 2.4, 2.0, 0.4)
            tdisp = curl(0, 0, 1, 1, 0.16)
        if dst:
            rng = ridge_keep(L, Sx, c.rng, 0.0, 0.0)
            a = c.rng.random(4) * TAU
            def extra(u, s, a=a):
                low = np.minimum(np.asarray(s), Sx - np.asarray(s))
                top = 1.6 + 1.4 * (0.5 + 0.5 * np.sin((np.asarray(u) - z0) * 0.7 + a[0])) + 0.6 * np.sin((np.asarray(u) - z0) * 2.3 + a[1]) + 0.25 * np.abs(((np.asarray(u) * 2.7) % 2) - 1)
                return top - low
        holes = [] if dst else wins
        if state == "damaged":
            holes = [h_ for h_ in wins if abs((h_[0] + h_[2]) / 2 - (z0 + L * 0.42)) > 2.4 or h_[1] < 3]
        kp = rect_keep(holes, extra) if (holes or extra is not None) else None
        barrel(c, hull, ax, org, z0, z1, Sx, cs, keep=kp, per=0.624, amp=0.045, thick=0.06, tear_disp=tdisp, v_extra=[x for h_ in holes for x in (h_[1], h_[3])],
               u_extra=[x for h_ in holes for x in (h_[0], h_[2])], fine_s=0.5 if kp is not None else None)
        if state != "intact":
            barrel(c, "interior", ax, org, z0, z1, Sx, cs, keep=None, flip_inside=True, inset=0.0, fine_s=0.8) if state == "damaged" else None
            b.disc("interior", (0, 0.22, (z0 + z1) / 2), 0.01, seg=4)
            b.quad("interior", V([0, 0.21, (z0 + z1) / 2]), V([1.0, 0, 0]), V([0, 0, 1.0]), 2 * R - 0.2, L - 0.2, (0, 0, 1, 1), normal=(0, 1, 0))
        # arch ribs at the sheet joints (bolted tubes), tint band at both ends
        for k, u in enumerate(np.arange(z0 + 1.9, z1 - 1.0, 2.5)):
            if dst and k % 2:
                continue
            if state == "damaged" and abs(u - (z0 + L * 0.42)) < 1.6:
                arc_rib(c, ax, org, u, cs, Sx, 0.05, 0.0, Sx * 0.42)
                continue
            arc_rib(c, ax, org, u, cs, Sx, 0.055, mat="steel", off=0.05) if (fine or k % 2 == 0) else None
        if not dst:
            for (ua, ub) in ((z0 + 0.35, z0 + 0.95), (z1 - 0.95, z1 - 0.35)):
                barrel(c, "trim", ax, org, ua, ub, Sx, cs, keep=None, per=0.0, band=6, col=(1, 0, 0), inset=0.0, extra_disp=lambda u, s, k: 0.025 + 0.0 * np.asarray(u))
            for zc in zs:
                for (sc, nside) in ((1.8, -1), (Sx - 1.8, 1)):
                    if state == "damaged" and abs(zc - (z0 + L * 0.42)) < 2.4 and nside == 1:
                        continue
                    w, h = cs(np.array(sc))
                    pt = V([float(w), float(h), zc])
                    nrm = unit(V([float(w), float(h), 0]))
                    b.quad("glass", pt - nrm * 0.14, V([0, 0, 1.0]), unit(np.cross(nrm, V([0, 0, 1.0]))), 1.2, 0.8, (0, 0.8, 1.2, 0), normal=nrm)
                    b.box("steel", pt + nrm * 0.12 + V([0, 0.35, 0]), (0.14, 0.08, 1.5), np.stack([V([0, 0, 1.0]), nrm, unit(np.cross(nrm, V([0, 0, 1.0])))], 1) if False else None)
        # end walls: arch-topped, door and windows, concrete step
        for zz, nz in ((z0, -1), (z1, 1)):
            holes_e = [] if dst else [(R - 0.6, 0.0, R + 0.6, 2.2), (R - 2.8, 1.4, R - 1.9, 2.2), (R + 1.9, 1.4, R + 2.8, 2.2)]
            top = lambda u, v, R=R: np.sqrt(np.maximum(R * R - (np.asarray(u) - R) ** 2, 0)) - np.asarray(v) - 0.12
            ex = top
            if dst:
                ex = (lambda u, v, R=R, z=zz: np.minimum(top(u, v), 1.0 + 1.2 * np.sin(np.asarray(u) * 1.7 + z) + 0.8 * np.sin(np.asarray(u) * 4.1) - np.asarray(v)))
            clad(c, "corrugated", (-R if nz < 0 else R, 0.2, zz), (1, 0, 0) if nz < 0 else (-1, 0, 0), 2 * R, (0, 1, 0), R, (0, 0, nz), "corr", holes=holes_e, extra=ex, thick=0.3 if not dst else 0.06,
                 v_extra=(1.0, 2.0))
            if not dst:
                b.box("galv", (0, 1.15, zz + nz * 0.02), (1.1, 2.3, 0.1)) if False else None
                b.quad("glass", V([0, 1.3, zz - nz * 0.05]) , V([1.0, 0, 0]), V([0, 1.0, 0]), 0.5, 0.5, (0, 0.5, 0.5, 0), normal=(0, 0, nz)) if False else None
                # door leaf in the recess, frame, step and a lamp
                b.box("steel", (0, 1.05, zz - nz * 0.2 + nz * 0.0), (1.1, 2.1, 0.08))
                for dx in (-0.62, 0.62):
                    b.box("steel", (dx, 1.1, zz + nz * 0.0), (0.12, 2.2, 0.35))
                b.box("steel", (0, 2.26, zz), (1.4, 0.14, 0.4))
                b.box("concrete", (0, 0.12, zz + nz * 0.6), (1.6, 0.24, 1.0))
                b.tube("steel", (0.45, 1.05, zz - nz * 0.15), (0.45, 1.15, zz - nz * 0.15), 0.035, 6)
                lamp(c, (0.0, 2.7, zz + nz * 0.05), (0, 0, nz), 0.5)
                for dx in (-2.35, 2.35):
                    b.quad("glass", V([dx, 1.8, zz - nz * 0.14]), V([1.0, 0, 0]), V([0, 1.0, 0]), 0.9, 0.8, (0, 0.8, 0.9, 0), normal=(0, 0, nz))
                    b.box("steel", (dx, 1.36, zz + nz * 0.04), (1.1, 0.08, 0.2))
        # weathering decals along the hull flanks
        if not dst:
            for k, zc in enumerate(np.arange(z0 + 1.5, z1 - 0.5, 2.2)):
                for side in (-1, 1):
                    sc = 2.9 if side < 0 else Sx - 2.9
                    w, h = cs(np.array(sc))
                    nrm = unit(V([float(w), float(h), 0]))
                    if state == "damaged" and side > 0 and abs(zc - (z0 + L * 0.42)) < 2.5:
                        continue
                    c.b.quad("decal", V([float(w), float(h) - 0.7, zc]) + nrm * 0.07, V([0, 0, 1.0]), unit(np.cross(nrm, V([0, 0, 1.0]))), 1.7, 2.6,
                             S_cell("streak_a" if (k + side) % 2 else "streak_b"), normal=nrm)
        # dirty variants: a sandbag wall along both sides, dust and rust bleed
        if dirty:
            n = int(L / 0.55)
            for side in (-1, 1):
                for course in range(3):
                    if dst and course > 0:
                        continue
                    cnt = n if fine else 1
                    for k in range(cnt if fine else 1):
                        if not fine:
                            if course == 0:
                                b.box("sandbag", (side * (R + 0.2), 0.45, (z0 + z1) / 2), (0.55, 0.9, L), None)
                            continue
                        zc = z0 + 0.3 + (k + 0.5 * (course % 2)) * 0.55
                        if zc > z1 - 0.2:
                            continue
                        if state == "damaged" and side > 0 and abs(zc - (z0 + L * 0.42)) < 1.6 and course > 0:
                            continue
                        b.box("sandbag", (side * (R + 0.2 - 0.04 * course), 0.17 + course * 0.28, zc), (0.55, 0.26, 0.5), axis_angle(V([0, 1.0, 0]), c.rng.uniform(-0.12, 0.12)))
        if variant == "dish":
            # equipment box on the roof (top 4.26 m), cone pedestal with a neck, a true round dish with a feed horn
            bx = V([-1.63, 3.62, -8.56])
            if not dst:
                b.box("paint", bx, (3.25, 1.3, 2.74), None)
                b.box("steel", bx + V([0, 0.68, 0]), (3.3, 0.06, 2.8))
                for j in range(5):
                    b.box("steel", bx + V([0.5 * j - 1.0, 0.4, 1.38]), (0.3, 0.04, 0.04))
                b.revolve("steel", [(0.55, 4.26), (0.18, 4.9), (0.18, 5.4)], 20 if fine else 8, cx=-2.09, cz=-8.08, uref=1.0)
                ax_d = unit(V([-0.47, 0.34, 0.81]))
                Rm = axis_angle(unit(np.cross(V([0, 1.0, 0]), ax_d)), math.acos(float(ax_d[1])))
                cen = V([-2.09, 5.71, -8.08])
                b.M = (Rm, cen)
                b.revolve("galv", [(0.0, 0.0), (0.4, 0.03), (0.9, 0.14), (1.41, 0.36)], 32 if fine else 14, uref=2.0)
                b.revolve("steel", [(1.41, 0.36), (1.45, 0.34), (1.45, 0.3), (1.0, 0.0), (0.4, -0.2), (0.0, -0.3)], 32 if fine else 14, uref=2.0)
                b.tube("steel", (0, 0, 0), (0, 1.1, 0), 0.04, 6)
                b.revolve("steel", [(0.12, 1.1), (0.12, 1.3), (0.0, 1.35)], 10, cx=0, cz=0, uref=1.0)
                b.M = None
            else:
                b.box("rust", (-2.0, 0.6, -8.5), (3.0, 0.3, 2.4), axis_angle(V([0, 1.0, 0]), 0.5))
                b.revolve("galv", [(0.0, 0.0), (0.9, 0.14), (1.41, 0.36)], 20, cx=1.5, cz=-6.0, uref=2.0)
        # vents on the crown and a stack
        if not dst:
            for zc in (z0 + 4.0, z0 + 11.0):
                if variant == "dish" and zc < -6.0 and zc > -10.0:
                    continue
                b.revolve("galv", [(0.28, R - 0.1), (0.28, R + 0.2), (0.4, R + 0.28), (0.0, R + 0.45)], 12 if fine else 6, cx=0.0, cz=zc, uref=1.0)
        # state dressing
        if state == "damaged":
            for k in range(6):
                zz = z0 + 3.0 + k * 1.7
                timber(c, (-R + 0.2, 0.3, zz), (-R * 0.4, R * 0.95, zz), 0.1, 0.1, "steel") if k % 2 == 0 else None
            broken_boards(c, (R * 0.7, 2.6, z0 + L * 0.42), 7, (1, 0.3, 0), (1.8, 0.8), (0, 0, 1), 6, "corrugated", (0.8, 1.7))
            c.decal_ground("soot", (R + 1.2, z0 + L * 0.42), 7, 8, 0.0, y=0.25)
        if dst:
            for k in range(5):
                Rm = axis_angle(V([0, 0, 1.0]), c.rng.uniform(-0.6, 0.6)) @ axis_angle(V([1.0, 0, 0]), c.rng.uniform(-0.3, 0.3))
                ctr = V([c.rng.uniform(-1.5, 1.5), 0.6 + 0.3 * k, z0 + 2.0 + k * 3.0])
                b.M = (Rm, ctr - Rm @ ctr)
                barrel(c, hull, ax, org + V([0, 0, 0]), ctr[2] - 1.3, ctr[2] + 1.3, Sx, cs, keep=lambda u, s: 1.2 - np.abs(np.asarray(s) - Sx * (0.3 + 0.1 * k)) , per=0.624, amp=0.04, thick=0.05)
                b.M = None
            debris(c, 12, (-4, 4), (z0, z1), 1.0, ("rust", "galv", "wood"))
            c.decal_ground("soot", (0, (z0 + z1) / 2), 12, 22, 0.0, y=0.25)
        return c
    return build


def S_cell(name):
    from bld_kit import cell_uv
    return cell_uv(name)


# ===================================================================================================================== hangar
def hangar(state, lod, seed):
    WALL[:] = ["paint", "flat"]; ROOF[:] = ["roofclean"]
    c = Ctx(state, lod, seed, breach=(5.0, 11.0, 19.2, 3.5), ledges=[(9.98, 3.2, 0.95), (1.0, 1.0, 0.6)], ao_rings=[(9.98, 1.4, 0.4)], ground_h=2.5)
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
    # roof: standing seams in pairs (1.53 m), two rows of roof lights, torn when damaged, bare arches when destroyed
    lights = []
    for zc in (-8.0, 8.0):
        s_c = (math.asin(zc / r) + ph) * r
        for k in range(5):
            xa = x0 + 4.0 + k * 6.6
            lights.append((xa, s_c - 0.9, xa + 4.0, s_c + 0.9))
    extra = None; tdisp = None
    if state == "damaged":
        extra = torn((x0 + x1) / 2 + 3.0, Sx * 0.3, 6.0, 4.0, 0.7); tdisp = curl(0, 0, 1, 1, 0.3)
    if dst:
        a = c.rng.random(4) * TAU
        def extra(u, s, a=a):
            low = np.minimum(np.asarray(s), Sx - np.asarray(s))
            top = 4.0 + 5.0 * (0.5 + 0.5 * np.sin((np.asarray(u) - x0) * 0.35 + a[0])) + 1.5 * np.sin((np.asarray(u) - x0) * 1.3 + a[1]) + 0.5 * np.abs(((np.asarray(u) * 1.7) % 2) - 1)
            return top - low
    hl = [] if dst else lights
    if state == "damaged":
        hl = [h_ for h_ in lights if not (abs((h_[0] + h_[2]) / 2 - ((x0 + x1) / 2 + 3.0)) < 6 and h_[1] < Sx * 0.5)]
    kp = rect_keep(hl, extra) if (hl or extra is not None) else None
    barrel(c, "seamroof", ax, org, x0, x1, Sx, cs, keep=kp, per=1.53, amp=0.06, thick=0.1, tear_disp=tdisp, u_extra=[x for h_ in hl for x in (h_[0], h_[2])],
           v_extra=[x for h_ in hl for x in (h_[1], h_[3])], fine_s=0.8 if kp is not None else None)
    if state == "damaged":
        barrel(c, "interior", ax, org, x0, x1, Sx, cs, keep=None, flip_inside=True, fine_s=2.0)
    for k, u in enumerate(np.arange(x0 + 1.5, x1, 3.06)):
        if dst and k % 3:
            continue
        arc_rib(c, ax, org, u, cs, Sx, 0.1, mat="steel", n=40, off=0.07) if (fine or k % 2 == 0) else None
    if not dst:
        for (xa, sa, xb, sb) in hl:
            w, h = cs(np.array((sa + sb) / 2))
            nrm = unit(V([float(w), float(h) - yc, 0]) * V([1, 1, 1]))
            nrm = unit(V([float(w), float(h) - yc, 0]))
            b.quad("glass", V([(xa + xb) / 2, float(h), float(w)]) * 0 + V([(xa + xb) / 2, float(h), float(w)]), V([1.0, 0, 0]), unit(V([0, nrm[1] * 0 + 0, 1.0])), xb - xa, 1.6, (0, 1.6, xb - xa, 0), normal=(0, 1, 0)) if False else None
            b.box("glass", V([(xa + xb) / 2, float(h) - 0.1, float(w)]), (xb - xa, 0.05, 1.8), axis_angle(V([1.0, 0, 0]), -math.atan2(float(w), float(h) - yc)))
    # side walls (z = +-19.2) and arched end walls
    wins = [(x - x0 - 1.2, 5.2, x - x0 + 1.2, 7.4) for x in np.arange(x0 + 3.0, x1 - 2.0, 4.8)]
    for sgn in (-1, 1):
        zz = sgn * zh
        tearW = torn(L * 0.55, 4.8, 3.2, 2.6, 0.3) if (state == "damaged" and sgn > 0) else None
        kw = ridge_keep(L, wallh, c.rng, 0.1, 0.5) if dst else None
        clad(c, "paint", (x0 if sgn > 0 else x1, 0.3, zz), (1, 0, 0) if sgn > 0 else (-1, 0, 0), L, (0, 1, 0), wallh - 0.3, (0, 0, sgn), "flat",
             holes=[] if dst else [(a_, b_ - 0.3, c_, d_ - 0.3) for a_, b_, c_, d_ in wins if not (tearW and abs((a_ + c_) / 2 - L * 0.55) < 3.5)], extra=tearW or kw,
             thick=0.12, tear_disp=curl(0, 0, 1, 1, 0.2) if tearW else None, v_extra=(3.0, 6.5) if tearW else ())
        if not dst:
            for x in np.arange(x0 + 3.0, x1 - 2.0, 4.8):
                if tearW and abs(x - x0 - L * 0.55) < 3.5:
                    continue
                window(c, (x, 0, zz), (1, 0, 0), 6.3, 2.4, 2.2, (0, 0, sgn), 1)
            gutter(c, (x0 - 0.2, 10.0, zz + sgn * 0.25), (x1 + 0.2, 10.0, zz + sgn * 0.25), 0.12)
            for xx in (x0 + 1, x1 - 1):
                downpipe(c, xx, zz + sgn * 0.3, 0.3, 9.9, 0.1)
            b.quad("trim", V([(x0 + x1) / 2, 9.2, zz + sgn * 0.04]), V([1.0, 0, 0]), V([0, 1.0, 0]), L, 0.9, (0, 0.5, L * 0.3, 0), normal=(0, 0, sgn), band=6, col=(1, 0, 0))
            for k, xx in enumerate(np.linspace(x0 + 2, x1 - 2, 9)):
                c.decal_wall("streak_a" if k % 2 else "streak_b", (xx, 0, zz), (1, 0, 0), 2.4, 1.0, 9.8, (0, 0, sgn), off=0.05)
    for xx, nx, door in ((x0, -1, (8.0, 6.6)), (x1, 1, (5.0, 6.0))):
        hfun = lambda w, r=r, yc=yc: yc + np.sqrt(np.maximum(r * r - np.asarray(w) ** 2, 0)) - 0.15
        hole = [] if dst else [(zh - door[0] / 2, 0.0, zh + door[0] / 2, door[1])]
        ex = (lambda u, v, hf=hfun: hf(np.asarray(u) - zh) - np.asarray(v))
        if dst:
            ex = (lambda u, v, hf=hfun, xx=xx: np.minimum(hf(np.asarray(u) - zh) - np.asarray(v), 3.0 + 2.0 * np.sin(np.asarray(u) * 0.8 + xx) + 1.0 * np.sin(np.asarray(u) * 2.9) - np.asarray(v)))
        clad(c, "paint", (xx, 0.3, -zh if nx < 0 else zh), (0, 0, 1) if nx < 0 else (0, 0, -1), 2 * zh, (0, 1, 0), 15.6, (nx, 0, 0), "flat", holes=[(a_, b_, c_, d_) for a_, b_, c_, d_ in hole],
             extra=ex, thick=0.4 if hole else 0.1)
        if not dst:
            roller_door(c, (xx, 0.3, 0), (0, 0, 1) if nx < 0 else (0, 0, -1), (nx, 0, 0), door[0], door[1], 0.3)
            b.box("steel", (xx + nx * 0.6, door[1] + 1.1, 0), (1.4, 0.3, door[0] + 1.4), None) if False else None
            b.box("galv", (xx + nx * 0.5, door[1] + 0.9, 0), (1.0, 0.35, door[0] + 1.6))
            for sz in (-1, 1):
                b.box("steel", (xx + nx * 0.2, door[1] / 2, sz * (door[0] / 2 + 0.3)), (0.5, door[1], 0.4))
            # barge trim along the arch rim
            ss = np.linspace(0, Sx, 40 if fine else 14)
            w, h = cs(ss)
            b.sweep("galv", [(xx + nx * 0.1, float(hh) + 0.1, float(ww)) for ww, hh in zip(w, h)], 0.12, 6 if fine else 4)
    for (px, pz) in ((x0, -zh), (x1, -zh), (x0, zh), (x1, zh)):
        if not dst:
            b.box("steel", (px, wallh / 2 + 0.2, pz), (0.5, wallh, 0.5))
    if state == "damaged":
        interior_shell(c, x0, x1, -zh, zh, 9.0)
        for k in range(8):
            xx = x0 + 3 + k * 4.6
            timber(c, (xx, 9.9, zh - 0.5), (xx, 0.4, zh - 0.5), 0.3, 0.3, "steel")
        broken_boards(c, (x0 + L * 0.55, 4.8, zh), 7, (0, 0.2, 1), (3.0, 2.0), (1, 0, 0), 9, "corrugated", (1.5, 3.0))
        c.decal_ground("soot", (x0 + L * 0.55, zh + 3.0), 14, 10, 0.0, y=0.32)
    if dst:
        interior_shell(c, x0, x1, -zh, zh, 1.2)
        for k, xx in enumerate(np.linspace(x0 + 5, x1 - 5, 4)):
            Rm = axis_angle(V([1.0, 0, 0]), c.rng.uniform(-0.35, 0.35)) @ axis_angle(V([0, 0, 1.0]), c.rng.uniform(-0.3, 0.3))
            ctr = V([xx, 1.0 + 0.5 * k, c.rng.uniform(-6, 6)])
            b.M = (Rm, ctr - Rm @ ctr)
            barrel(c, "seamroof", ax, org, xx - 2.8, xx + 2.8, Sx, cs, keep=lambda u, s, k=k: 3.5 - np.abs(np.asarray(s) - Sx * (0.25 + 0.17 * k)), per=1.53, amp=0.06, thick=0.1)
            b.M = None
        for k in range(14):
            a_ = V([c.rng.uniform(x0, x1), 0.5, c.rng.uniform(-zh, zh)])
            timber(c, a_, a_ + V([c.rng.uniform(-6, 6), c.rng.uniform(0.4, 2.0), c.rng.uniform(-6, 6)]), 0.3, 0.3, "steel")
        debris(c, 24, (x0, x1), (-zh, zh), 1.6, ("rust", "galv", "steel"))
        c.decal_ground("soot", ((x0 + x1) / 2, 0), 44, 44, 0.0, y=0.32)
    return c


# =========================================================================================== composite box buildings
WALL = ["corrugated", "corr"]   # per member: wall material and cladding kind (flat panels for the painted / concrete buildings)
ROOF = ["roofing"]


def hall(c, x0, x1, z0, z1, h, mat=None, y0=0.0, holes=None, main=False, roof=None, tint_y=None, dmg_side=1):
    """A clad box: four walls with openings; walls of the main block take the damaged breach; the destroyed state drops everything to stubs."""
    b = c.b
    state = c.state
    dst = state == "destroyed"
    W, D = x1 - x0, z1 - z0
    holes = holes or {}
    for key, (p0, d, Ln, nrm) in {"-z": ((x0, y0, z0), (1, 0, 0), W, (0, 0, -1)), "+z": ((x1, y0, z1), (-1, 0, 0), W, (0, 0, 1)),
                                  "-x": ((x0, y0, z1), (0, 0, -1), D, (-1, 0, 0)), "+x": ((x1, y0, z0), (0, 0, 1), D, (1, 0, 0))}.items():
        hl = [] if dst else holes.get(key, [])
        extra = None; td = None
        if dst:
            extra = ridge_keep(Ln, h, c.rng, 0.08, 0.5)
        elif main and state == "damaged" and key == ("+x" if dmg_side > 0 else "-x"):
            extra = torn(Ln * 0.5, h * 0.45, min(Ln * 0.22, 3.0), h * 0.28, 0.5); td = curl(0, 0, 1, 1, 0.18)
            hl = [q for q in hl if abs((q[0] + q[2]) / 2 - Ln * 0.5) > min(Ln * 0.22, 3.0) + 0.6]
        clad(c, WALL[0], p0, d, Ln, (0, 1, 0), h, nrm, WALL[1], holes=hl, extra=extra, edge_mat=("paint" if WALL[0] in ("facade", "paint", "concrete") else "rust"), thick=0.12 if (hl or extra is not None) else 0.0, tear_disp=td, v_extra=(h * 0.3, h * 0.6) if td else ())
    if main and state == "damaged":
        interior_shell(c, x0, x1, z0, z1, h)
        for k in range(max(3, int(D / 2.0))):
            zz = z0 + 0.8 + k * 2.0
            timber(c, ((x0 + x1) / 2, h + 0.5, zz), (x1 - 0.3, h - 0.1, zz), 0.14, 0.14, "steel")
            timber(c, (x1 - 0.3, h, zz), (x1 - 0.3, y0 + 0.4, zz), 0.14, 0.14, "steel")
    if state != "destroyed" and tint_y is not None:
        for sgn, zz in ((-1, z0), (1, z1)):
            b.quad("trim", V([(x0 + x1) / 2, tint_y, zz + sgn * 0.04]), V([1.0, 0, 0]), V([0, 1.0, 0]), W, 0.5, (0, 0.5, W * 0.3, 0), normal=(0, 0, sgn), band=6, col=(1, 0, 0))
    if state != "destroyed":
        for (px, pz) in ((x0, z0), (x1, z0), (x0, z1), (x1, z1)):
            b.box("steel", (px, y0 + h / 2 + 0.1, pz), (0.3, h, 0.3))
    return None


def flat_roof(c, x0, x1, z0, z1, y, tear=False, sag=False, ribs=False):
    b = c.b
    if c.state == "destroyed":
        return
    ex = None; sg = None; td = None
    if tear:
        ex = torn((x1 - x0) * 0.5, (z1 - z0) * 0.5, min(3.0, (x1 - x0) * 0.2), min(2.5, (z1 - z0) * 0.2), 0.3)
        sg = lambda u, v: -0.3 * np.exp(-(((np.asarray(u) - (x1 - x0) * 0.5) / 2.6) ** 2 + ((np.asarray(v) - (z1 - z0) * 0.5) / 2.0) ** 2))
        td = curl(0, 0, 1, 1, 0.16)
    slab_sheet(c, ROOF[0], (x0 - 0.3, y + 0.06, z0 - 0.3), (1, 0, 0), x1 - x0 + 0.6, (0, 0, 1), z1 - z0 + 0.6, (0, 1, 0), True, 0.06, ex, td, sg, 0.45)
    b.box("galv", ((x0 + x1) / 2, y - 0.04, z0 - 0.3), (x1 - x0 + 0.7, 0.2, 0.12)); b.box("galv", ((x0 + x1) / 2, y - 0.04, z1 + 0.3), (x1 - x0 + 0.7, 0.2, 0.12))


def slope_roof(c, p_low, dirv, L, up_dir, slen, tear=False, normal=None):
    if c.state == "destroyed":
        return
    ex = sg = td = None
    if tear:
        ex = torn(L * 0.5, slen * 0.5, min(2.5, L * 0.2), min(2.0, slen * 0.25), 0.4)
        sg = lambda u, v: -0.25 * np.exp(-(((np.asarray(u) - L * 0.5) / 2.2) ** 2 + ((np.asarray(v) - slen * 0.5) / 1.5) ** 2))
        td = curl(0, 0, 1, 1, 0.15)
    n = unit(np.cross(unit(dirv), unit(up_dir)))
    n = n if n[1] > 0 else -n
    slab_sheet(c, ROOF[0], V(p_low) + n * 0.06, dirv, L, up_dir, slen, n, True, 0.06, ex, td, sg, 0.45)


def collapse(c, x0, x1, z0, z1, hgt, n=4):
    """Fallen roof sheets and timbers over a destroyed block."""
    b = c.b
    for k in range(n):
        Rm = axis_angle(V([1.0, 0, 0]), c.rng.uniform(-0.4, 0.4)) @ axis_angle(V([0, 0, 1.0]), c.rng.uniform(-0.4, 0.4))
        ctr = V([c.rng.uniform(x0 + 1, x1 - 1), 0.5 + 0.3 * k, c.rng.uniform(z0 + 1, z1 - 1)])
        b.M = (Rm, ctr - Rm @ ctr)
        w, dpt = min(4.0, (x1 - x0) * 0.6), min(5.0, (z1 - z0) * 0.6)
        slab_sheet(c, ROOF[0], ctr + V([-w / 2, 0, -dpt / 2]), (1, 0, 0), w, (0, 0, 1), dpt, (0, 1, 0), True, 0.05, None, None, None, 0.45)
        b.M = None
    for k in range(6):
        a_ = V([c.rng.uniform(x0, x1), 0.35, c.rng.uniform(z0, z1)])
        timber(c, a_, a_ + V([c.rng.uniform(-3, 3), c.rng.uniform(0.3, 1.2), c.rng.uniform(-3, 3)]), 0.16, 0.16, "steel")
    debris(c, 8, (x0, x1), (z0, z1), 1.0, ("rust", "galv", "steel"))


def vehiclehangar(state, lod, seed):
    WALL[:] = ["paint", "flat"]; ROOF[:] = ["roofclean"]
    c = Ctx(state, lod, seed, breach=(9.7, 3.6, -1.0, 3.2), ledges=[(7.21, 3.0, 0.95), (3.63, 1.6, 0.8), (0.8, 0.9, 0.6)], ao_rings=[(7.21, 1.4, 0.4), (3.63, 1.0, 0.4)], ground_h=2.0)
    b = c.b
    fine = c.fine
    dst = state == "destroyed"
    X0, X1, Z0, Z1, H = -11.335, 9.729, -7.609, 5.597, 7.21
    b.box("concrete", ((X0 + X1) / 2, 0.12, (Z0 + Z1) / 2 + 0.5), (X1 - X0 + 0.6, 0.24, 28.0 - 4.0), None) if False else None
    b.box("concrete", (-0.8, 0.1, -1.0), (X1 - X0 + 0.8 + 0.0, 0.2, 31.5), None) if False else None
    # main hall: 7.21 m walls, windows on the long sides, mansard roof to a flat at 9.527
    holes = {"-z": [], "+z": [], "-x": [(D, 4.2, D + 1.6, 5.4) for D in (1.2, 4.2, 7.2, 10.2)], "+x": [(D, 4.2, D + 1.6, 5.4) for D in (1.2, 4.2, 7.2, 10.2)]}
    hall(c, X0, X1, Z0, Z1, H, "corrugated", 0.2, holes, True, tint_y=H - 0.6, dmg_side=1)
    if not dst:
        for D in (1.2, 4.2, 7.2, 10.2):
            for wx, nx in ((X0, -1), (X1, 1)):
                if state == "damaged" and nx == 1 and abs(D + 0.8 - 6.5) < 3.6:
                    continue
                window(c, (wx, 0, Z1 - D - 0.8), (0, 0, 1), 5.1, 1.6, 1.2, (nx, 0, 0), 1)
        # mansard: four slopes to a flat at 9.527 (z -5.709..3.865)
        fz0, fz1 = -5.709, 3.865
        flat_roof(c, X0 + 1.7, X1 - 1.7, fz0, fz1, 9.527, tear=(state == "damaged"))
        slope_roof(c, (X0 - 0.3, H + 0.06, Z0 - 0.3), (1, 0, 0), X1 - X0 + 0.6, (0, 2.317, fz0 - Z0 + 0.3), math.hypot(2.317, fz0 - Z0 + 0.3))
        slope_roof(c, (X0 - 0.3, H + 0.06, Z1 + 0.3), (1, 0, 0), X1 - X0 + 0.6, (0, 2.317, fz1 - Z1 - 0.3), math.hypot(2.317, fz1 - Z1 - 0.3))
        for sx, fx in ((X0 - 0.3, X0 + 1.7), (X1 + 0.3, X1 - 1.7)):
            slope_roof(c, (sx, H + 0.06, Z0), (0, 0, 1), Z1 - Z0, (fx - sx, 2.317, 0), math.hypot(fx - sx, 2.317))
        for xx in (-4.0, 0.5, 5.0):
            b.box("steel", (xx, 9.8, -1.0), (0.9, 0.5, 2.4))
        for sx in (X0 - 0.15, X1 + 0.15):
            gutter(c, (sx, H - 0.1, Z0 - 0.2), (sx, H - 0.2, Z1 + 0.2)); downpipe(c, sx, Z1 + 0.1, 0.3, H - 0.2)
    # lean-to on +z (x -10.105..9.21 to z 10.478, eaves 3.63 -> 6.272 against the hall), lean-to on -z (x -1.489..8.082 to z -12.274)
    hall(c, -10.105, 9.21, Z1, 10.478, 3.63, "corrugated", 0.2, {"+z": [(3.0, 0.0, 6.2, 2.8), (9.0, 0.0, 12.2, 2.8), (14.2, 1.0, 15.4, 2.2)]}, False, tint_y=3.0)
    hall(c, -1.489, 8.082, -12.274, Z0, 3.63, "corrugated", 0.2, {"-z": [(1.4, 0.0, 4.6, 2.8)]}, False)
    hall(c, -9.723, -1.294, -11.448, -7.687, 3.66, "corrugated", 0.2, {"-z": [(1.2, 0.0, 2.6, 2.2)]}, False)
    if not dst:
        slope_roof(c, (-10.2, 3.69, Z1), (1, 0, 0), 19.5, (0, 2.64, 10.58 - Z1), math.hypot(2.64, 10.58 - Z1), tear=(state == "damaged"))
        slope_roof(c, (-1.6, 3.69, Z0), (1, 0, 0), 9.8, (0, 2.64, -12.4 - Z0), math.hypot(2.64, -12.4 - Z0))
        flat_roof(c, -9.723, -1.294, -11.448, -7.687, 3.66)
        # roller doors "13": recessed, header, tint
        for (dx, dz, nz) in ((-6.8 + 0.0, 10.478, 1), (-1.5, 10.478, 1), (3.4, -12.274, -1)):
            roller_door(c, (dx + 0.0, 0.2, dz), (1, 0, 0), (0, 0, nz), 3.2, 2.6, 0.2)
        for k, xx in enumerate(np.linspace(-10, 9, 7)):
            c.decal_wall("streak_a" if k % 2 else "streak_b", (xx, 0, 10.478), (1, 0, 0), 2.2, 0.6, 3.5, (0, 0, 1), off=0.05)
        # the duct (x 4.184..5.915) climbs from the -z lean-to over the eaves to 11.9 m and down onto the roof
        path = [(5.05, 3.7, -11.0), (5.05, 3.7, -7.8), (5.05, 11.2, -7.2), (5.05, 11.9, -4.0), (5.05, 11.2, -2.5), (5.05, 9.7, -2.0)]
        b.sweep("galv", path, 0.82, 16 if fine else 8, caps=True)
        for pz in (-9.0, -6.0, -3.5):
            b.tube("steel", (5.05, 0.2, pz), (5.05, 9.0, pz), 0.07, 6) if fine and pz == -9.0 else None
    else:
        collapse(c, X0, X1, Z0, Z1, 7.0, 6)
        collapse(c, -10.1, 9.2, Z1, 10.4, 3.6, 3)
        c.decal_ground("soot", (-0.8, -1.0), 36, 34, 0.0, y=0.25)
    if state == "damaged":
        c.decal_ground("soot", (12.5, -1.0), 8, 8, 0.0, y=0.26)
    return c


def repairbay(state, lod, seed):
    WALL[:] = ["concrete", "flat"]; ROOF[:] = ["roofclean"]
    c = Ctx(state, lod, seed, breach=(-3.6, 3.0, 7.0, 3.0), ledges=[(4.58, 2.6, 0.95), (9.06, 3.0, 0.9)], ao_rings=[(4.58, 1.2, 0.4)], ground_h=2.0)
    b = c.b
    fine = c.fine
    dst = state == "destroyed"
    # repair floor and the striped ramp pad
    b.box("concrete", (0.6, 0.075, 0.0), (8.8, 0.15, 11.0))
    b.quad("trim", V([0.2, 0.36, 0.0]), V([1.0, 0, 0]), V([0, 0, 1.0]), 7.4, 11.0, (0, 0, 7.4 * 0.3, 11.0 * 0.3), normal=(0, 1, 0), band=1)
    # two wings (x -3.66..5.08, z +-5.46..+-9.71, 4.58 m) and the rear block (x 5.08..9.33, 9.06 m)
    wing_h = {"-z": [], "+z": [], "-x": [(1.3, 1.6, 3.1, 3.4), (4.3, 1.6, 6.1, 3.4)], "+x": []}
    hall(c, -3.66, 5.08, 5.46, 9.71, 4.58, "corrugated", 0.2, {"-x": [(0.8 + 2.1 * k, 1.6, 2.2 + 2.1 * k, 3.4) for k in range(2)], "+z": [(1.5, 1.6, 3.5, 3.4), (5.0, 1.6, 7.0, 3.4)]}, True, tint_y=4.0, dmg_side=-1)
    hall(c, -3.66, 5.08, -9.71, -5.46, 4.58, "corrugated", 0.2, {"-z": [(1.5, 1.6, 3.5, 3.4), (5.0, 1.6, 7.0, 3.4)]}, False, tint_y=4.0)
    hall(c, 5.08, 9.33, -9.71, 6.35, 9.06, "corrugated", 0.2, {"+x": [(2.0 + 4.6 * k, 1.5 + 2.1 * r_, 3.6 + 4.6 * k, 2.9 + 2.1 * r_) for k in range(3) for r_ in range(4)], "-x": [(11.0, 0.0, 14.0, 3.2)]}, False, tint_y=8.2)
    hall(c, 5.08, 9.33, -6.55, 0.0, 6.86, "corrugated", 0.2, {}, False)
    if not dst:
        for (x0_, z0_, z1_) in ((-3.66, 5.46, 9.71), (-3.66, -9.71, -5.46)):
            flat_roof(c, x0_, 5.08, z0_, z1_, 4.58, tear=(state == "damaged" and z0_ > 0))
        flat_roof(c, 5.08, 9.33, -9.71, 6.35, 9.06)
        # bay doors at x 4.94: recessed, two leaves
        roller_door(c, (4.94, 0.2, -2.7), (0, 0, 1), (-1, 0, 0), 3.2, 3.6, 0.2)
        roller_door(c, (4.94, 0.2, 2.7), (0, 0, 1), (-1, 0, 0), 3.2, 3.6, 0.2)
        # gantry: a hooded tower on each wing and a tube bridge between them on ring frames
        for sz in (-1, 1):
            tz = sz * 7.55
            b.box("paint", (-0.03, 3.8 + 2.4, tz), (5.58, 4.8 + 0.0, 2.1)) if False else None
            b.box("paint", (-0.03, 5.6 + 0.8, tz), (5.58, 2.2, 2.1))
            b.revolve("galv", [(1.3, 7.74), (1.3, 8.0), (0.5, 8.5), (0.0, 8.7)], 4, th0=math.pi / 4, cx=-0.03, cz=tz, uref=1.0)
            b.box("glass", (-0.03, 6.2, tz - sz * 1.06), (4.8, 1.0, 0.06))
            # beacon lamp: a round lamp on a collar
            b.revolve("steel", [(0.2, 8.7), (0.2, 8.9), (0.3, 9.0), (0.18, 9.25), (0.0, 9.3)], 14 if fine else 6, cx=-0.03, cz=tz, uref=1.0)
        b.sweep("galv", [(-2.6, 6.7, 0.0), (2.55, 6.7, 0.0)], 0.0, 4, caps=False) if False else None
        bridge = [(-2.62, 6.55, z_) for z_ in (-6.5, 6.5)]
        for k, xx in enumerate((-2.0, 0.0, 2.0)):
            ring = [(xx, 6.55 + 1.0 * math.cos(a), 1.0 * 0 + 6.0 * 0) for a in np.linspace(0, TAU, 2)]
        b.sweep("galv", [(-0.03, 6.55, -6.5), (-0.03, 6.55, 6.5)], 0.95, 12 if fine else 6, caps=True)
        for zz in np.linspace(-6.0, 6.0, 5 if fine else 3):
            ring = [(-0.03 + 1.05 * math.cos(a), 6.55 + 1.05 * math.sin(a), zz) for a in np.linspace(0, TAU, 14)]
            b.sweep("steel", ring, 0.05, 5, closed=True)
        for a in np.linspace(0, TAU, 7)[:-1] if fine else ():
            b.tube("steel", (-0.03 + 1.05 * math.cos(a), 6.55 + 1.05 * math.sin(a), -6.0), (-0.03 + 1.05 * math.cos(a), 6.55 + 1.05 * math.sin(a), 6.0), 0.045, 5)
        for k, zz in enumerate(np.linspace(-6, 6, 7)):
            c.decal_wall("streak_a" if k % 2 else "streak_b", (-3.66, 0, zz), (0, 0, 1), 1.8, 0.4, 4.4, (-1, 0, 0), off=0.05) if abs(zz) > 5.46 else None
        # annex lean-to and porch
        slope_roof(c, (9.45, 6.9, -6.55), (0, 0, 1), 6.55, (-4.37, -0.0, 0.0), 4.37) if False else None
    else:
        collapse(c, -3.66, 5.08, 5.46, 9.71, 4.0, 3)
        collapse(c, -3.66, 5.08, -9.71, -5.46, 4.0, 3)
        collapse(c, 5.08, 9.33, -9.71, 6.35, 9.0, 4)
        timber(c, (-0.03, 0.6, -5.0), (-0.03, 1.5, 4.0), 1.8, 1.8, "galv")
        c.decal_ground("soot", (1.0, 0.0), 26, 30, 0.0, y=0.4)
    if state == "damaged":
        c.decal_ground("soot", (-6.0, 7.0), 8, 8, 0.0, y=0.4)
    return c


def portable(state, lod, seed):
    WALL[:] = ["paint", "flat"]; ROOF[:] = ["roofclean"]
    c = Ctx(state, lod, seed, breach=(2.06, 2.4, -4.5, 2.0), ledges=[(3.93, 2.2, 0.9), (0.6, 0.8, 0.6)], ao_rings=[(0.6, 0.6, 0.4)], ground_h=1.4)
    b = c.b
    fine = c.fine
    dst = state == "destroyed"
    x0, x1, z0, z1, y0, y1 = -3.895, 2.058, -11.604, 3.007, 0.592, 3.929
    h = y1 - y0
    # skirt on blocks, cabin of bolted panels with grey-green window bays
    b.box("concrete_dark", ((x0 + x1) / 2, 0.3, (z0 + z1) / 2), (x1 - x0 - 0.3, 0.6, z1 - z0 - 0.9))
    for xx in (x0 + 0.5, x1 - 0.5):
        for zz in np.linspace(z0 + 0.6, z1 - 0.6, 5):
            b.box("concrete", (xx, 0.15, zz), (0.5, 0.3, 0.5))
    wins = [(zz - z0 - 0.7, 0.9, zz - z0 + 0.7, 2.2) for zz in np.linspace(z0 + 1.4, z1 - 1.4, 5)]
    hall(c, x0, x1, z0, z1, h, "paint", y0, {"+x": [(a, b_, c_, d) for a, b_, c_, d in wins], "-x": [(a, b_, c_, d) for a, b_, c_, d in wins[:4]], "-z": [(2.4, 0.0, 3.7, 2.1)]}, True, tint_y=y0 + 2.9, dmg_side=1)
    if not dst:
        for zz in np.linspace(z0 + 1.4, z1 - 1.4, 5):
            if not (state == "damaged" and abs(zz - (z0 + (z1 - z0) * 0.5)) < 2.2):
                window(c, (x1, 0, zz), (0, 0, 1), y0 + 1.55, 1.4, 1.3, (1, 0, 0), 1)
        for zz in np.linspace(z0 + 1.4, z1 - 1.4, 5)[:4]:
            window(c, (x0, 0, zz), (0, 0, 1), y0 + 1.55, 1.4, 1.3, (-1, 0, 0), 1)
        for xx in np.linspace(x0 + 1.0, x1 - 1.0, 4):
            b.box("steel", (xx, y0 + h / 2, z1 + 0.02), (0.1, h, 0.06))
        for zz in np.linspace(z0 + 1.5, z1 - 1.5, 6):
            b.box("steel", (x1 + 0.03, y0 + h / 2, zz), (0.06, h, 0.1))
        # parapet fascia, flat roof with two plant boxes and a vent
        flat_roof(c, x0, x1, z0, z1, y1)
        b.box("trim" if False else "steel", ((x0 + x1) / 2, y1 + 0.2, z0), (x1 - x0 + 0.2, 0.3, 0.1))
        b.box("galv", (-1.8, y1 + 0.55, -2.0), (1.4, 0.9, 1.4)); b.box("galv", (0.6, y1 + 0.5, -7.5), (1.2, 0.8, 1.2)); b.revolve("galv", [(0.15, y1), (0.15, y1 + 0.5), (0.25, y1 + 0.55), (0.0, y1 + 0.7)], 10, cx=0.9, cz=1.5, uref=1.0)
        # door with a timber deck, three steps and a railing
        b.box("galv", (0.0, y0 + 1.05, z0 - 0.1 + 0.0), (1.3, 2.1, 0.1)) if False else None
        b.box("steel", (-1.2 + 3.55 + 0.0, 0.4, -4.3), (1.88, 0.14, 2.2)) if False else None
        for k in range(int(2.2 / 0.2) if fine else 3):
            b.box("boards", (3.02, y0 + 0.02, -5.4 + k * 0.2 + 0.1), (1.9, 0.06, 0.19))
        for (px, pz) in ((2.1, -5.4), (3.9, -5.4), (2.1, -3.2), (3.9, -3.2)):
            timber(c, (px, 0.0, pz), (px, y0, pz), 0.14, 0.14)
        for k in range(3):
            b.box("boards", (3.0, y0 - 0.2 * (k + 1), -3.0 + 0.3 * (k + 1)), (1.8, 0.05, 0.3))
        for sz in (-5.4, -3.2):
            timber(c, (3.9, y0 + 0.9, sz), (2.1, y0 + 0.9, sz), 0.06, 0.06) if False else None
        timber(c, (3.9, y0 + 0.9, -5.4), (3.9, y0 + 0.9, -3.2), 0.06, 0.06); timber(c, (3.9, y0 + 0.5, -5.4), (3.9, y0 + 0.5, -3.2), 0.05, 0.05)
        for k, zz in enumerate(np.linspace(-10.5, 2.5, 6)):
            c.decal_wall("streak_a" if k % 2 else "streak_b", (x1, 0, zz), (0, 0, 1), 1.8, y0 + 0.4, y1, (1, 0, 0), off=0.05)
            c.decal_wall("rust_bleed", (x1, 0, zz + 0.9), (0, 0, 1), 1.0, y0 + 0.2, y0 + 1.4, (1, 0, 0), off=0.05)
    else:
        collapse(c, x0, x1, z0, z1, h, 4)
        c.decal_ground("soot", ((x0 + x1) / 2, (z0 + z1) / 2), 10, 17, 0.0, y=0.3)
    if state == "damaged":
        c.decal_ground("soot", (3.2, -4.5), 6, 6, 0.0, y=0.35)
    return c


MEMBERS = {
    "quonsetclean": (quonset("clean"), "half-cylinder R 4.21 m, z -12.67..4.17 (tools/cad/quonsetclean_cad.py)"),
    "quonset": (quonset("dirty"), "weathered half-cylinder R 4.25 m with sandbags (tools/cad/quonset_cad.py)"),
    "quonset2": (quonset("dish"), "half-cylinder R 4.24 m with a roof dish (tools/cad/quonset2_cad.py)"),
    "hangar": (hangar, "barrel hall x -19..19.2, z +-19.2, crown 15.584 m (tools/cad/hangar_cad.py)"),
    "vehiclehangar": (vehiclehangar, "hall with mansard roof, two lean-tos, store and duct, 11.9 m (tools/cad/vehiclehangar_cad.py)"),
    "repairbay": (repairbay, "two wings, rear block, gantry bridge (tools/cad/repairbay_cad.py)"),
    "portable": (portable, "site cabin 5.95 x 14.6 m with a timber deck (tools/cad/portable_cad.py)"),
}


def build_member(app, out):
    fn, src = MEMBERS[app]
    info = {"app": app, "made_by": "tools/art/v3/bld_hangars.py", "source_dims": src, "states": {}}
    for si, state in enumerate(STATES):
        lods = [fn(state, lod, 4100 + si + sum(map(ord, app))).b for lod in (0, 1)]
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
