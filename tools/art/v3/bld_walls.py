#!/usr/bin/env python3
"""v3 walls, fences and barriers (LANCE-21 family 3).

    python3 -I tools/art/v3/bld_walls.py <app>|all

Fence runs: the maps lay fence pieces end to end along local -z (z 0 .. -L). Every piece carries a post at z = 0 and a mid post, and only a
thin end rod at z = -L (buried in the next piece's post), so a run shows one post per joint and no gaps or doubles. Walls are laid in the
originals' frame (post block at -z, body to +17.1). Same contract as the other families: <app>.glb, _damaged, _destroyed with lod0/lod1.
Chain-link and mesh are an alpha texture on a flat panel (material "chain", building_v3_fence.gdshader), so a segment is a few dozen
triangles at LOD1. Dimensions are measured from the Shared Source originals' bounds; geometry and textures are new work.
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bld_hangars as H  # noqa: E402
from bld_hangars import (Ctx, V, TAU, axis_angle, unit, clad, timber, debris, torn, curl, ridge_keep, rect_keep, ROOT)  # noqa: E402


def rot_about(c, Rm, pivot):
    c.b.M = (Rm, V(pivot, float) - Rm @ V(pivot, float))


def chain_panel(c, z0, z1, y0, y1, state="intact", tear=None, sag=None, dispf=None):
    """A chain-link panel in the plane x = 0 from z0 to z1 (u along +z), y0 to y1; tear is a keep(u, v) with u from 0, v from 0."""
    L, h = z1 - z0, y1 - y0
    pos = lambda u, v: V([0, 0, z0], float) + np.asarray(u)[..., None] * V([0, 0, 1.0]) + (np.asarray(v)[..., None] + y0) * V([0, 1.0, 0])
    nu = max(3, int(L / 0.6)) if tear is not None else 2
    nv = max(3, int(h / 0.5)) if tear is not None else 2
    us = np.linspace(0, L, nu + 1); vs = np.linspace(0, h, nv + 1)
    c.b.cut_param("chain", pos, us, vs, tear, uv=lambda u, v: np.stack([u, v], -1), flip=True, thickness=0.0, disp=dispf)


def post(c, x, z, h, r=0.055, cap=True, mat="steel", base=True):
    b = c.b
    b.tube(mat, (x, 0.0, z), (x, h, z), r, 8 if c.fine else 4, caps=True)
    if cap:
        b.revolve("steel", [(r + 0.012, h - 0.04), (r + 0.012, h + 0.02), (0.0, h + 0.07)], 8 if c.fine else 4, cx=x, cz=z, uref=0.3)
    if base:
        b.box("concrete", (x, 0.04, z), (0.22, 0.08, 0.22))


def chain_fence(L, h, kind="wire"):
    def build(state, lod, seed):
        c = Ctx(state, lod, seed, breach=(0.0, h * 0.5, -L / 2, 1.8), ledges=[(h, 0.7, 0.6)], ao_rings=[], ground_h=0.5)
        b = c.b
        fine = c.fine
        dst, dmg = state == "destroyed", state == "damaged"
        rng = c.rng
        y0, y1 = 0.12, h
        # intact geometry: panel, top and bottom rails, tension wire, posts at z = 0 and the middle, a thin end rod at z = -L
        def run(z0, z1, lean=0.0, pivot_z=None, with_post0=True, torn_panel=None, sag_panel=None):
            if lean:
                rot_about(c, axis_angle(V([0, 0, 1.0]), lean), (0, 0, pivot_z if pivot_z is not None else z1))
            chain_panel(c, z0, z1, y0, y1, state, torn_panel, None, sag_panel)
            b.tube("steel", (0, y1, z0), (0, y1, z1), 0.032, 8 if fine else 4)
            b.tube("steel", (0, y0, z0), (0, y0, z1), 0.026, 6 if fine else 4)
            if fine:
                b.tube("steel", (0, 0.45, z0), (0, 0.45, z1), 0.012, 4)
            b.M = None
        if not (dmg or dst):
            run(-L, 0.0)
            post(c, 0, 0.0, h + 0.1)
            post(c, 0, -L / 2, h + 0.1)
            b.tube("steel", (0, 0, -L), (0, h, -L), 0.03, 4)
            if fine:
                for k in range(1, 5):                                  # wire ties
                    pass
        elif dmg:
            # the far half stands, the near half leans over with a torn panel; one post tilted, the top rail bent
            tr = torn(L * 0.25, (y1 - y0) * 0.45, 1.5, 0.9, 0.5)
            run(-L, -L / 2)
            run(-L / 2, 0.0, lean=0.42, pivot_z=0.0, torn_panel=tr)
            post(c, 0, -L / 2, h + 0.1)
            rot_about(c, axis_angle(V([0, 0, 1.0]), 0.42), (0, 0, 0))
            post(c, 0, 0.0, h + 0.1)
            b.M = None
            b.tube("steel", (0, 0, -L), (0, h, -L), 0.03, 4)
            # a snapped top rail end hanging down
            b.sweep("steel", [(0, y1, -L / 2), (0.05, y1 - 0.2, -L / 2 + 0.6), (0.2, y1 - 0.9, -L / 2 + 0.9)], 0.03, 6)
        else:
            # down: the panel lies on the ground beside the stumps, torn, with a few wires trailing
            tr = torn(L * 0.4, (y1 - y0) * 0.5, 1.4, 0.8, 1.0)
            rot_about(c, axis_angle(V([0, 0, 1.0]), 1.45), (0, 0.05, 0))
            chain_panel(c, -L, -L / 2 - 0.2, y0, y1, state, None)
            b.tube("steel", (0, y1, -L), (0, y1, -L / 2 - 0.2), 0.032, 8 if fine else 4)
            b.M = None
            rot_about(c, axis_angle(V([0, 0, 1.0]), -1.2), (0, 0.05, 0))
            chain_panel(c, -L / 2 + 0.3, 0.0, y0, y1, state, tr)
            b.tube("steel", (0, y1, -L / 2 + 0.3), (0, y1, 0.0), 0.032, 8 if fine else 4)
            b.M = None
            for zz, hh in ((0.0, 0.9), (-L / 2, 0.5), (-L, 0.4)):
                post(c, 0, zz, hh, cap=False)
            b.tube("steel", (0, 0.1, -L / 2 - 0.4), (0.9, 0.12, -L / 2 + 0.7), 0.05, 6)
            for k in range(3 if fine else 1):
                b.sweep("steel", [(0.3 * k, 0.05, -2.0 - k), (0.5 + 0.2 * k, 0.15, -2.6 - k), (0.2 * k, 0.05, -3.4 - k)], 0.012, 4)
            c.decal_ground("soot", (0.0, -L / 2), 3.0, L * 0.9, 0.0, y=0.03)
        return c
    return build


def razor_fence(L):
    def build(state, lod, seed):
        h = 4.6
        c = Ctx(state, lod, seed, breach=(0.0, 2.5, -L / 2, 2.2), ledges=[(h, 0.8, 0.5)], ground_h=0.6)
        b = c.b
        fine = c.fine
        dst, dmg = state == "destroyed", state == "damaged"
        rng = c.rng
        nslats = 9 if fine else 4
        def slats(z0, z1, lean=0.0, piv=0.0, skip=()):
            if lean:
                rot_about(c, axis_angle(V([0, 0, 1.0]), lean), (0, 0, piv))
            for k in range(nslats):
                if k in skip:
                    continue
                yy = 0.3 + k * (h - 0.3) / nslats
                b.box("fencesteel", (0, yy + 0.2, (z0 + z1) / 2), (0.1, 0.4 * (9 / nslats if not fine else 1.0), z1 - z0), axis_angle(V([0, 0, 1.0]), 0.0))
            b.M = None
        def top(z0, z1, lean=0.0, piv=0.0, droop=False):
            if lean:
                rot_about(c, axis_angle(V([0, 0, 1.0]), lean), (0, 0, piv))
            for sgn in (-1, 1):
                dy = -0.5 if (droop and sgn > 0) else 0.0
                b.tube("fencesteel", (0, h, z0), (0.0, h, z1), 0.03, 4)
                b.tube("fencesteel", (0.0, h, (z0 + z1) / 2), (sgn * 0.8, h + 0.7 + dy, (z0 + z1) / 2), 0.03, 4) if False else None
                p0, p1 = V([0, h, z0]), V([sgn * 0.85, h + 0.75 + dy, z0])
                b.tube("fencesteel", p0, p1, 0.03, 4)
                b.tube("fencesteel", V([0, h, z1]), V([sgn * 0.85, h + 0.75 + dy, z1]), 0.03, 4)
                # mesh strip between the arms and a razor coil along the tip
                pos = lambda u, v, sgn=sgn, dy=dy, z0=z0: V([0, h, z0]) + np.asarray(u)[..., None] * V([0, 0, 1.0]) + np.asarray(v)[..., None] * V([sgn * 0.85, 0.75 + dy, 0.0])
                b.cut_param("chain", pos, np.array([0.0, z1 - z0]), np.array([0.0, 1.0]), None, uv=lambda u, v: np.stack([u, v], -1), flip=(sgn > 0))
                n = int((z1 - z0) / 0.12) if fine else 8
                path = [(sgn * 0.85 + 0.0 + 0.14 * math.cos(i * 1.2), h + 0.75 + dy + 0.14 * math.sin(i * 1.2), z0 + (z1 - z0) * i / n) for i in range(n + 1)]
                b.sweep("fencesteel", path, 0.012, 4)
            b.M = None
        if not (dmg or dst):
            slats(-L, 0.0); top(-L, 0.0)
            for zz in (0.0, -L / 2):
                b.box("fencesteel", (0, h / 2 + 0.05, zz), (0.22, h + 0.1, 0.22)); b.box("fenceconc", (0, 0.1, zz), (0.5, 0.2, 0.5))
            b.box("fencesteel", (0, h / 2, -L), (0.1, h, 0.1))
        elif dmg:
            slats(-L, -L / 2); top(-L, -L / 2)
            slats(-L / 2, 0.0, lean=0.5, piv=0.0, skip=(2, 3, 6)); top(-L / 2, 0.0, lean=0.5, piv=0.0, droop=True)
            b.box("fencesteel", (0, h / 2 + 0.05, -L / 2), (0.22, h + 0.1, 0.22)); b.box("fenceconc", (0, 0.1, -L / 2), (0.5, 0.2, 0.5))
            rot_about(c, axis_angle(V([0, 0, 1.0]), 0.5), (0, 0, 0)); b.box("fencesteel", (0, h / 2 + 0.05, 0.0), (0.22, h + 0.1, 0.22)); b.M = None
            b.box("fencesteel", (0, h / 2, -L), (0.1, h, 0.1))
        else:
            for zz, hh in ((0.0, 1.2), (-L / 2, 0.7), (-L, 0.5)):
                b.box("fencesteel", (0, hh / 2, zz), (0.22, hh, 0.22), axis_angle(V([1.0, 0, 0]), rng.uniform(-0.3, 0.3)))
            for k in range(nslats):
                zc = -L + rng.uniform(0.5, L - 0.5)
                b.box("fencesteel", (rng.uniform(-0.7, 0.7), 0.1 + 0.12 * (k % 3), zc), (0.1, 0.4, rng.uniform(2.0, 4.0)), axis_angle(V([0, 1.0, 0]), rng.uniform(-0.4, 0.4)) @ axis_angle(V([0, 0, 1.0]), rng.uniform(-0.3, 0.3)))
            rot_about(c, axis_angle(V([0, 0, 1.0]), 1.3), (0, 0, 0))
            top(-L * 0.9, -L * 0.5)
            b.M = None
            c.decal_ground("soot", (0.0, -L / 2), 3.0, L * 0.9, 0.0, y=0.03)
        return c
    return build


def wood_fence(L, h=2.2, kind="wood"):
    def build(state, lod, seed):
        c = Ctx(state, lod, seed, breach=(0.0, 1.0, -L / 2, 1.6), ledges=[(h, 0.8, 0.7), (0.5, 0.4, 0.6)], ground_h=0.5)
        b = c.b
        fine = c.fine
        dst, dmg = state == "destroyed", state == "damaged"
        rng = c.rng
        npl = int(L / 0.22)
        def planks(z0, z1, lean=0.0, piv=0.0, miss=(), jag=False):
            if lean:
                rot_about(c, axis_angle(V([0, 0, 1.0]), lean), (0, 0, piv))
            n = max(2, int((z1 - z0) / 0.22))
            if not fine:
                b.quad("palewood", V([0.0, h / 2, (z0 + z1) / 2]), V([0, 0, 1.0]), V([0, 1.0, 0]), z1 - z0, h, (0, h, z1 - z0, 0), normal=(1, 0, 0))
                b.quad("palewood", V([0.0, h / 2, (z0 + z1) / 2]), V([0, 0, -1.0]), V([0, 1.0, 0]), z1 - z0, h, (0, h, z1 - z0, 0), normal=(-1, 0, 0))
                b.M = None
                return
            for k in range(n):
                if k in miss:
                    continue
                zc = z0 + (k + 0.5) * (z1 - z0) / n
                top_ = h - (rng.uniform(0.0, 0.7) if jag and k % 3 == 0 else 0.0)
                b.box("palewood", (0, top_ / 2, zc), (0.04, top_, (z1 - z0) / n - 0.02), axis_angle(V([1.0, 0, 0]), rng.uniform(-0.02, 0.02)) if (jag or dmg) else None)
            b.M = None
        def rails(z0, z1, lean=0.0, piv=0.0):
            if lean:
                rot_about(c, axis_angle(V([0, 0, 1.0]), lean), (0, 0, piv))
            for yy in (0.4, h - 0.4):
                b.box("wood", (0.06, yy, (z0 + z1) / 2), (0.05, 0.1, z1 - z0))
            b.M = None
        def wpost(z, hh, lean=0.0):
            if lean:
                rot_about(c, axis_angle(V([0, 0, 1.0]), lean), (0, 0, z))
            b.box("wood", (0.06, hh / 2, z), (0.12, hh, 0.12))
            b.box("galv", (0.06, hh + 0.02, z), (0.16, 0.04, 0.16))
            b.M = None
        if not (dmg or dst):
            planks(-L, 0.0); rails(-L, 0.0)
            wpost(0.0, h + 0.15); wpost(-L / 2, h + 0.15)
            b.box("wood", (0.06, h / 2, -L), (0.08, h, 0.08))
        elif dmg:
            planks(-L, -L / 2, miss=(3, 7)); rails(-L, -L / 2)
            planks(-L / 2, 0.0, lean=0.35, piv=0.0, miss=(2, 5, 6), jag=True); rails(-L / 2, 0.0, lean=0.35, piv=0.0)
            wpost(-L / 2, h + 0.15); wpost(0.0, h + 0.15, lean=0.35)
            b.box("wood", (0.06, h / 2, -L), (0.08, h, 0.08))
        else:
            for zz, hh in ((0.0, 1.0), (-L / 2, 0.6), (-L, 0.5)):
                b.box("wood", (0.06, hh / 2, zz), (0.12, hh, 0.12), axis_angle(V([1.0, 0, 0]), rng.uniform(-0.25, 0.25)))
            for k in range(int(npl * 0.6) if fine else 4):
                zc = -L + rng.uniform(0.2, L - 0.2)
                b.box("palewood", (rng.uniform(-0.8, 0.8), 0.05 + 0.04 * (k % 3), zc), (0.04, rng.uniform(0.5, 2.0), 0.2), axis_angle(V([0, 1.0, 0]), rng.uniform(-1.4, 1.4)) @ axis_angle(V([0, 0, 1.0]), 1.5))
            rot_about(c, axis_angle(V([0, 0, 1.0]), 1.4), (0, 0, 0))
            planks(-L * 0.45, 0.0, miss=(2, 4, 7), jag=True); rails(-L * 0.45, 0.0)
            b.M = None
            c.decal_ground("soot", (0.0, -L / 2), 3.0, L * 0.9, 0.0, y=0.03)
        for k in range(int(L / 1.4)):
            c.decal_wall("streak_a" if k % 2 else "streak_b", (0.07, 0, -0.7 - k * 1.4), (0, 0, -1), 1.2, 0.1, h, (1, 0, 0), off=0.02) if (fine and not dst) else None
        return c
    return build


def shanty_fence(L=8.5, h=2.3):
    def build(state, lod, seed):
        c = Ctx(state, lod, seed, breach=(0.0, 1.2, -L / 2, 1.6), ledges=[(h, 0.8, 0.9)], ground_h=0.5)
        b = c.b
        dst, dmg = state == "destroyed", state == "damaged"
        for zz in (0.0, -L / 2, -L):
            timber(c, (0.0, 0.0, zz), (0.0, h + 0.1 if not dst else 0.7, zz), 0.14, 0.14, "wood")
        if not dst:
            ex = torn(L * 0.6, h * 0.5, 1.5, 0.8, 0.7) if dmg else None
            clad(c, "darksheet", (0.06, 0.0, 0.0), (0, 0, -1), L, (0, 1, 0), h, (1, 0, 0), "corr", extra=ex, thick=0.04, tear_disp=curl(0, 0, 1, 1, 0.12) if dmg else None, v_extra=(h * 0.3, h * 0.7) if dmg else ())
            clad(c, "darksheet", (-0.06, 0.0, -L), (0, 0, 1), L, (0, 1, 0), h, (-1, 0, 0), "corr", extra=ex and None, thick=0.0)
            for yy in (0.4, h - 0.3):
                b.box("wood", (0.12, yy, -L / 2), (0.05, 0.1, L)) if False else None
        else:
            for k in range(5):
                Rm = axis_angle(V([1.0, 0, 0]), c.rng.uniform(-0.5, 0.5)) @ axis_angle(V([0, 1.0, 0]), c.rng.uniform(-0.6, 0.6))
                b.M = (Rm, V([c.rng.uniform(-0.7, 0.7), 0.15 + 0.08 * k, -1.2 - 1.5 * k]) - Rm @ V([0, 0, 0]))
                b.box("corrugated", (0, 0, 0), (0.05, 0.1, 0.1)) if False else clad(c, "darksheet", (0, 0, -0.9), (0, 0, 1), 1.8, (1, 0, 0), 1.0, (0, 1, 0), "flat")
                b.M = None
            c.decal_ground("soot", (0.0, -L / 2), 3.0, L * 0.9, 0.0, y=0.03)
        return c
    return build


# ================================================================================================ barriers
def sandbag_wall(L=8.4, courses=3, bunker=False):
    def build(state, lod, seed):
        c = Ctx(state, lod, seed, breach=(0.0, 0.5, 0.0, 1.8), ledges=[(0.9, 0.5, 0.5)], ground_h=0.4)
        b = c.b
        fine = c.fine
        dst, dmg = state == "destroyed", state == "damaged"
        rng = c.rng
        def bag(p, yaw, scale=1.0, tilt=0.0, mat="sandbag"):
            Rm = axis_angle(V([0, 1.0, 0]), yaw) @ axis_angle(V([1.0, 0, 0]), tilt)
            b.box(mat, p, (0.62 * scale, 0.24 * scale, 0.36 * scale), Rm, col=(0, rng.uniform(0, 0.4), 0))
        if not bunker:
            n = int(L / 0.7)
            for course in range(courses):
                if not fine:
                    if course < (courses if not (dmg or dst) else (2 if dmg else 1)):
                        b.box("sandbag", (0, 0.13 + course * 0.26, 0), (0.62, 0.26, L - (0.35 if course % 2 else 0)))
                    continue
                for k in range(n):
                    z = -L / 2 + 0.35 + k * 0.7 + (0.35 if course % 2 else 0.0)
                    if z > L / 2 - 0.2:
                        continue
                    if dst:
                        if course > 0 or rng.random() < 0.25:
                            continue
                        bag((rng.uniform(-0.5, 0.5), 0.1, z + rng.uniform(-0.3, 0.3)), rng.uniform(-0.7, 0.7) + math.pi / 2, 0.95, rng.uniform(-0.3, 0.3))
                        continue
                    if dmg and course >= 2 and abs(z) < 2.0:
                        continue
                    if dmg and course == 1 and abs(z) < 0.9:
                        continue
                    bag((rng.uniform(-0.03, 0.03), 0.13 + course * 0.26, z), math.pi / 2 + rng.uniform(-0.06, 0.06), 1.0)
            if dmg or dst:
                for k in range(8 if fine else 2):
                    bag((rng.uniform(-0.8, 0.8), 0.1, rng.uniform(-2.0, 2.0)), rng.uniform(0, 3), 0.95, rng.uniform(-0.4, 0.4))
        else:
            # a horseshoe of bags (open to +x): radius 3.1 about (0.8, 0), 3 courses, with a firing slot cut in the middle
            R_ = 3.1
            nb = int(math.pi * R_ / 0.68)
            for course in range(courses):
                for k in range(nb if fine else 0):
                    a = -math.pi / 2 - 0.0 + (k + 0.5 * (course % 2)) * math.pi / nb + math.pi
                    ang = a
                    if dst and (course > 0 or rng.random() < 0.3):
                        continue
                    if dmg and course == 2 and (k % 3 == 0 or k > nb * 0.6):
                        continue
                    p = (0.8 + R_ * math.cos(ang), 0.14 + course * 0.28, R_ * math.sin(ang))
                    bag(p, -ang + math.pi / 2 + rng.uniform(-0.05, 0.05), 1.1)
            if not fine and dst:
                for k in range(5):
                    b.box("sandbag", (0.8 + R_ * math.cos(math.pi + k * 0.5), 0.12, R_ * math.sin(math.pi + k * 0.5)), (0.6, 0.24, 0.4), axis_angle(V([0, 1.0, 0]), k))
            if not fine:
                b.revolve("sandbag", [(R_ + 0.2, 0.0), (R_ + 0.2, 0.8)], 12, cx=0.8, cz=0.0, th0=math.pi / 2, th1=math.pi * 1.5, uref=1.0) if not dst else None
                b.revolve("sandbag", [(R_ - 0.2, 0.0), (R_ - 0.2, 0.8)], 12, cx=0.8, cz=0.0, th0=math.pi / 2, th1=math.pi * 1.5, uref=1.0, flip=True) if not dst else None
            if not dst:
                b.tube("steel", (-1.4, 0.95, -0.1), (-2.0, 1.05, 0.0), 0.04, 6)
                b.box("steel", (-1.2, 0.9, 0.0), (0.5, 0.15, 0.3))
        for k in range(3 if fine else 0):
            c.decal_ground("oil", (rng.uniform(-0.4, 0.4), rng.uniform(-L / 3, L / 3)), 0.9, 0.9, rng.random() * 3, y=0.03)
        return c
    return build


def tripod_barricade(units=5, spacing=1.7):
    def build(state, lod, seed):
        c = Ctx(state, lod, seed, ledges=[], ground_h=0.4)
        b = c.b
        fine = c.fine
        dst, dmg = state == "destroyed", state == "damaged"
        rng = c.rng
        for k in range(units):
            z = (k - (units - 1) / 2) * spacing
            if dst and k % 2:
                continue
            lean = 0.0
            if dmg and k in (1, 3):
                lean = 0.55 + 0.1 * k
            if dst:
                lean = 1.3
            rot_about(c, axis_angle(V([1.0, 0, 0]), lean * (1 if k % 2 else -1)) @ axis_angle(V([0, 1.0, 0]), 0.0), (0, 0, z)) if lean else None
            for (dx, dz) in ((0.0, 0.7), (0.0, -0.7), (-0.5, 0.0)):
                p0 = V([0.0 + 0.0, 0.05, z + dz]); p1 = V([-0.2 - dx * 0.3, 1.8, z - dz * 0.05])
                nseg = 6 if fine else 3
                for q in range(nseg):
                    a0, a1 = p0 + (p1 - p0) * q / nseg, p0 + (p1 - p0) * (q + 1) / nseg
                    if q % 2 == 0:
                        b.tube("trim", a0, a1, 0.075, 6 if fine else 4, caps=False, col=(1, 0, 0)) if False else b.sweep("trim", [a0, a1], 0.075, 6 if fine else 4, caps=False, col=(1, 0, 0), band=6)
                    else:
                        b.tube("steel", a0, a1, 0.075, 6 if fine else 4, caps=False)
            b.tube("steel", (-0.1, 1.5, z - 0.5), (-0.1, 1.5, z + 0.5), 0.04, 6) if fine else None
            b.M = None
        if dst or dmg:
            for k in range(3 if fine else 1):
                b.box("trim", (rng.uniform(-0.8, 0.5), 0.07, rng.uniform(-3, 3)), (0.15, 0.15, 1.3), axis_angle(V([0, 1.0, 0]), rng.random() * 3.0))
        c.decal_ground("soot", (0, 0), 3.0, 8.0, 0.0, y=0.03) if dst else None
        return c
    return build


def metal_barricade(L=8.4):
    """The original is an A-frame of corrugated sheet: two sloped panels meeting at a 1.7 m ridge, 3 m across, 8.4 m long (run along x)."""
    def build(state, lod, seed):
        c = Ctx(state, lod, seed, breach=(0.0, 0.8, -0.7, 1.4), ledges=[(1.7, 1.0, 0.7)], ground_h=0.4)
        b = c.b
        fine = c.fine
        dst, dmg = state == "destroyed", state == "damaged"
        rng = c.rng
        slen = math.hypot(1.65, 1.5)
        def panel(sgn, tear=False, M=None):
            n = (0, 1.5, -1.65 * sgn) if True else None
            n = (0, 1.5, -1.65) if sgn < 0 else (0, 1.5, 1.65)
            up = (0, 1.65, 1.5) if sgn < 0 else (0, 1.65, -1.5)
            ex = torn(L * 0.4, slen * 0.5, 1.5, 0.6, 0.4) if tear else None
            sg = (lambda u, v: -0.18 * np.exp(-(((np.asarray(u) - L * 0.4) / 1.6) ** 2 + ((np.asarray(v) - slen * 0.5) / 0.7) ** 2))) if tear else None
            if M is not None:
                b.M = M
            H.slab_sheet(c, "roofclean", V([-L / 2, 0.05, sgn * 1.5]), (1, 0, 0), L, up, slen, n, True, 0.05, ex, curl(0, 0, 1, 1, 0.12) if tear else None, sg, 0.45)
            b.M = None
        def frame(m=None):
            for k in range(5 if fine else 2):
                x = -L / 2 + 0.2 + k * (L - 0.4) / (4 if fine else 1)
                b.tube("steel", (x, 0.05, -1.5), (x, 1.68, 0.0), 0.04, 5)
                b.tube("steel", (x, 1.68, 0.0), (x, 0.05, 1.5), 0.04, 5)
            b.tube("steel", (-L / 2, 1.7, 0.0), (L / 2, 1.7, 0.0), 0.06, 6)
        if not (dmg or dst):
            panel(-1); panel(1); frame()
            for sx in (-1, 1):
                tri = [(sx * L / 2, 0.05, -1.5), (sx * L / 2, 0.05, 1.5), (sx * L / 2, 1.7, 0.0)]
                P = V(tri); b.add("steel", P, np.tile(V([sx, 0, 0], float), (3, 1)), P[:, [2, 1]], [(0, 1, 2)])
        elif dmg:
            panel(-1, tear=True); frame()
            Rm = axis_angle(V([1.0, 0, 0]), 0.5)
            panel(1, M=(Rm, V([0, 1.7, 0.0]) - Rm @ V([0, 1.7, 0.0])))
            b.box("steel", (L / 2, 0.8, 0), (0.05, 1.6, 3.0)) if False else None
        else:
            panel(-1, M=(axis_angle(V([1.0, 0, 0]), -0.9), V([0, 0.6, -0.8])))
            Rm = axis_angle(V([1.0, 0, 0]), 1.3)
            panel(1, M=(Rm, V([0, 0.0, 1.5]) - Rm @ V([0, 0.0, 1.5]) + V([0, 0.0, 0.5])))
            for k in range(4):
                x = -L / 2 + 1 + k * 2.2
                b.tube("steel", (x, 0.05, -1.5), (x + 0.2, 0.9 + 0.3 * k % 2, -1.2), 0.04, 5)
            c.decal_ground("soot", (0, 0), 9.5, 4.0, 0.0, y=0.03)
        return c
    return build


def sawhorse(state, lod, seed):
    c = Ctx(state, lod, seed, ground_h=0.3)
    b = c.b
    dst = state == "destroyed"
    if dst:
        for k in range(3):
            b.box("trim", (c.rng.uniform(-0.5, 0.5), 0.05, c.rng.uniform(-0.4, 0.4)), (1.5, 0.08, 0.12), axis_angle(V([0, 1.0, 0]), c.rng.random() * 3))
        return c
    lean = 0.4 if state == "damaged" else 0.0
    if lean:
        rot_about(c, axis_angle(V([0, 0, 1.0]), lean), (0.8, 0, 0))
    for sz in (-0.5, 0.5):
        for sx in (-0.7, 0.7):
            b.tube("steel", (sx, 0.0, sz), (sx * 0.4, 1.15, sz * 0.2), 0.04, 5)
    for yy in (1.1, 0.85):
        b.box("trim", (0, yy, 0), (1.6, 0.16, 0.05), None)
    b.M = None
    return c


def smallbarricade(state, lod, seed):
    return tripod_barricade(3, 1.6)(state, lod, seed)


# ======================================================================================================== concrete walls
def wall(h_body, h_post, post_w, body_w, post_z, body_z, mat="concrete", seams=4, name=""):
    """A wall piece in the originals' frame: a post block at z in post_z (x +-post_w/2) and the body along body_z (x +-body_w/2)."""
    def build(state, lod, seed):
        zp0, zp1 = post_z
        zb0, zb1 = body_z
        lb = zb1 - zb0
        c = Ctx(state, lod, seed, breach=(0.0, h_body * 0.5, (zb0 + zb1) / 2, 3.2), ledges=[(h_body, 2.0, 0.9), (h_post, 2.0, 0.9)], ao_rings=[(h_body, 1.2, 0.35)], ground_h=2.0)
        b = c.b
        fine = c.fine
        dst, dmg = state == "destroyed", state == "damaged"
        rng = c.rng
        bw = body_w / 2
        pw = post_w / 2
        # footing and the post: a battered block with a capped top, a recess band and a tint band
        b.box("concrete_dark", (0, 0.25, (zb0 + zp0) / 2 if False else (zp0 + zp1) / 2), (post_w + 0.5, 0.5, zp1 - zp0 + 0.5))
        b.box("concrete_dark", (0, 0.25, (zb0 + zb1) / 2), (body_w + 0.4, 0.5, lb + 0.4))
        hp = h_post if not dst else h_post * 0.35
        pk = (lambda u, v, hp=hp: hp * (0.55 + 0.45 * np.abs(np.sin(np.asarray(u) * 1.7 + 0.4))) - np.asarray(v)) if dst else None
        for sgn in (-1, 1):
            clad(c, mat, (sgn * pw, 0.5, zp0 if sgn < 0 else zp1), (0, 0, 1) if sgn < 0 else (0, 0, -1), zp1 - zp0, (0, 1, 0), h_post - 0.5, (sgn, 0, 0), "flat", extra=pk, thick=0.1, edge_mat="rust")
        for zz, nz in ((zp0, -1), (zp1, 1)):
            clad(c, mat, (pw if nz < 0 else -pw, 0.5, zz), (-1, 0, 0) if nz < 0 else (1, 0, 0), post_w, (0, 1, 0), h_post - 0.5, (0, 0, nz), "flat", extra=pk, thick=0.1, edge_mat="rust")
        if not dst:
            b.box("concrete_dark", (0, h_post + 0.12, (zp0 + zp1) / 2), (post_w + 0.3, 0.25, zp1 - zp0 + 0.3))
            b.box("trim", (0, h_post * 0.72, (zp0 + zp1) / 2), (post_w + 0.04, 0.5, zp1 - zp0 + 0.04), None, band=6, col=(1, 0, 0)) if False else None
            b.quad("trim", V([pw + 0.03, h_post * 0.75, (zp0 + zp1) / 2]), V([0, 0, 1.0]), V([0, 1.0, 0]), zp1 - zp0, 0.55, (0, 0.5, (zp1 - zp0) * 0.3, 0), normal=(1, 0, 0), band=6, col=(1, 0, 0))
            b.quad("trim", V([-pw - 0.03, h_post * 0.75, (zp0 + zp1) / 2]), V([0, 0, -1.0]), V([0, 1.0, 0]), zp1 - zp0, 0.55, (0, 0.5, (zp1 - zp0) * 0.3, 0), normal=(-1, 0, 0), band=6, col=(1, 0, 0))
            for j in range(3):
                b.box("concrete_dark", (0, h_post * (0.25 + 0.25 * j), (zp0 + zp1) / 2), (post_w + 0.12, 0.18, zp1 - zp0 + 0.12))
        # the body: two clad faces, a coping, expansion joints and buttress pilasters; breach cut when damaged, ridge when destroyed
        tear = torn(lb * 0.5, h_body * 0.5, min(4.0, lb * 0.18), h_body * 0.32, 0.4) if dmg else None
        kd = ridge_keep(lb, h_body, rng, 0.08, 0.42, 0.1) if dst else None
        for sgn in (-1, 1):
            clad(c, mat, (sgn * bw, 0.5, zb0 if sgn < 0 else zb1), (0, 0, 1) if sgn < 0 else (0, 0, -1), lb, (0, 1, 0), h_body - 0.5, (sgn, 0, 0), "flat", extra=tear or kd, thick=0.18, edge_mat="rust",
                 tear_disp=curl(0, 0, 1, 1, 0.12) if tear else None, v_extra=(h_body * 0.3, h_body * 0.7) if tear else ())
        if not dst:
            b.box("concrete_dark", (0, h_body + 0.1, (zb0 + zb1) / 2), (body_w + 0.3, 0.22, lb + 0.2))
            for k in range(1, seams if fine else 0):
                zz = zb0 + lb * k / seams
                b.box("concrete_dark", (0, h_body / 2 + 0.25, zz), (body_w + 0.22, h_body - 0.5, 0.3))
            for j in range(1, 3 if fine else 0):
                b.box("concrete_dark", (0, h_body * j / 3, (zb0 + zb1) / 2), (body_w + 0.2, 0.3, lb))
            for sgn in (-1, 1):
                c.decal_wall("streak_a", (sgn * (bw + 0.02), 0, zb0 + lb * 0.3), (0, 0, 1) if sgn > 0 else (0, 0, -1), 3.0, h_body * 0.2, h_body, (sgn, 0, 0), off=0.04) if fine else None
                c.decal_wall("rust_bleed", (sgn * (bw + 0.02), 0, zb0 + lb * 0.75), (0, 0, 1) if sgn > 0 else (0, 0, -1), 2.5, h_body * 0.3, h_body * 0.7, (sgn, 0, 0), off=0.04) if fine else None
        if dmg:
            for k in range(10 if fine else 4):
                b.tube("steel", (rng.uniform(-bw * 0.8, bw * 0.8), h_body * 0.45 + rng.uniform(-1.5, 1.5), (zb0 + zb1) / 2 + rng.uniform(-2.5, 2.5)),
                       (rng.uniform(-bw * 0.8, bw * 0.8), h_body * 0.45 + rng.uniform(0, 1.8), (zb0 + zb1) / 2 + rng.uniform(-2.5, 2.5)), 0.04, 5)
            interior_n = None
            b.box("interior", (0, h_body * 0.5, (zb0 + zb1) / 2), (body_w - 0.4, h_body - 0.6, lb - 0.4)) if False else None
        if dmg or dst:
            n = int(14 + h_body * 1.5) if fine else int(5 + h_body * 0.4)
            for k in range(n):
                sz = (rng.uniform(0.6, 1.6) * (h_body ** 0.3), rng.uniform(0.4, 1.0) * (h_body ** 0.3), rng.uniform(0.6, 1.4) * (h_body ** 0.3))
                zc = (zb0 + zb1) / 2 + rng.uniform(-lb * (0.25 if dmg else 0.45), lb * (0.25 if dmg else 0.45))
                b.box("concrete" if k % 3 else "concrete_dark", (rng.uniform(-bw * 1.8, bw * 1.8), sz[1] / 2 + 0.2, zc), sz,
                      axis_angle(V([0, 1.0, 0]), rng.random() * 3.0) @ axis_angle(V([1.0, 0, 0]), rng.uniform(-0.3, 0.3)))
            c.decal_ground("soot", (0, (zb0 + zb1) / 2), body_w * 3.5, lb * 0.9, 0.0, y=0.52)
        if dst:
            for k in range(8):
                b.tube("steel", (rng.uniform(-bw, bw), 0.5, (zb0 + zb1) / 2 + rng.uniform(-lb * 0.4, lb * 0.4)), (rng.uniform(-bw, bw), 0.5 + rng.uniform(0.6, 2.2), (zb0 + zb1) / 2 + rng.uniform(-lb * 0.4, lb * 0.4)), 0.035, 5)
        return c
    return build


def post_only(h_post, post_w, post_z, mat="concrete"):
    def build(state, lod, seed):
        w = wall(h_post, h_post, post_w, post_w, post_z, (post_z[1] + 0.2, post_z[1] + 0.3), mat)
        return w(state, lod, seed)
    return build



# ============================================================================== second pass: identity fixes
def pillow(c, centre, size, yaw=0.0, tilt=0.0, sag=0.0, mat="sandbag", nu=8, nv=5):
    """A canvas sandbag: a pillowed superellipsoid, flattened on the bottom, with a sagging top; true volume, soft normals."""
    a, bb, cc = size[0] / 2, size[1] / 2, size[2] / 2
    th = np.linspace(0, TAU, nu + 1)
    ph = np.linspace(-math.pi / 2, math.pi / 2, nv + 1)
    P = np.zeros((nv + 1, nu + 1, 3)); N = np.zeros_like(P)
    for j, f in enumerate(ph):
        for i, t in enumerate(th):
            ex = 0.45
            cx = np.sign(math.cos(t)) * abs(math.cos(t)) ** ex
            cz = np.sign(math.sin(t)) * abs(math.sin(t)) ** ex
            r_ = math.cos(f) ** 0.6
            y = np.sign(math.sin(f)) * abs(math.sin(f)) ** 0.7
            top_sag = -sag * max(0.0, y) * (1 - (cx ** 2 + cz ** 2) / 2)
            P[j, i] = (a * r_ * cx, bb * (y if y > -0.7 else -0.7 - 0.0) + top_sag * bb, cc * r_ * cz)
            N[j, i] = (r_ * cx / a, y / bb if y > 0 else y * 0.5 / bb, r_ * cz / cc)
    Rm = axis_angle(V([0, 1.0, 0]), yaw) @ axis_angle(V([1.0, 0, 0]), tilt)
    Pw = np.asarray(centre, float) + (P.reshape(-1, 3) @ Rm.T)
    Nw = N.reshape(-1, 3) @ Rm.T
    idx = []
    for j in range(nv):
        for i in range(nu):
            q = j * (nu + 1) + i
            idx += [(q, q + 1, q + nu + 1), (q + 1, q + nu + 2, q + nu + 1)]
    c.b.add(mat, Pw, Nw, np.stack([P.reshape(-1, 3)[:, 0], P.reshape(-1, 3)[:, 2]], 1), idx, col=(0, c.rng.uniform(0, 0.35), 0))


def sandbag_wall(L=8.4, courses=3, bunker=False):
    def build(state, lod, seed):
        c = Ctx(state, lod, seed, breach=(0.0, 0.5, 0.0, 1.8), ledges=[(0.9, 0.5, 0.5)], ground_h=0.4)
        b = c.b
        fine = c.fine
        dst, dmg = state == "destroyed", state == "damaged"
        rng = c.rng
        bag = lambda p, yaw, sc=1.0, tilt=0.0, sag=0.25: pillow(c, p, (0.7 * sc, 0.3 * sc, 0.42 * sc), yaw, tilt, sag)
        if not bunker:
            n = int(L / 0.64)
            for course in range(courses):
                if not fine:
                    if course < (courses if not (dmg or dst) else (2 if dmg else 1)):
                        b.box("sandbag", (0, 0.14 + course * 0.27, 0), (0.66, 0.28, L - (0.35 if course % 2 else 0)))
                    continue
                for k in range(n):
                    z = -L / 2 + 0.35 + k * 0.64 + (0.32 if course % 2 else 0.0)
                    if z > L / 2 - 0.2:
                        continue
                    if dst:
                        if course > 0 or rng.random() < 0.3:
                            continue
                        bag((rng.uniform(-0.5, 0.5), 0.12, z + rng.uniform(-0.3, 0.3)), rng.uniform(-0.7, 0.7) + math.pi / 2, 0.95, rng.uniform(-0.3, 0.3), 0.1)
                        continue
                    if dmg and course >= 2 and abs(z) < 2.0:
                        continue
                    if dmg and course == 1 and abs(z) < 0.9:
                        continue
                    bag((rng.uniform(-0.03, 0.03), 0.15 + course * 0.26, z), math.pi / 2 + rng.uniform(-0.08, 0.08), rng.uniform(0.96, 1.04))
            if dmg or dst:
                for k in range(8 if fine else 2):
                    bag((rng.uniform(-0.8, 0.8), 0.12, rng.uniform(-2.0, 2.0)), rng.uniform(0, 3), 0.95, rng.uniform(-0.4, 0.4), 0.1)
        else:
            # five angled straight runs round a gun slit (open toward +x), bags laid along each run; the middle run has a 0.5 m slit
            pts = [(3.7, -4.2), (1.3, -4.2), (-0.8, -1.9), (-0.8, 1.9), (1.3, 4.2), (3.7, 4.2)]
            for (ax_, az_), (bx_, bz_) in zip(pts[:-1], pts[1:]):
                seglen = math.hypot(bx_ - ax_, bz_ - az_)
                ang = math.atan2(bz_ - az_, bx_ - ax_)
                nb = max(2, int(seglen / 0.66))
                for course in range(courses):
                    for k in range(nb if fine else 0):
                        t = (k + 0.5 + (0.5 if course % 2 else 0.0)) / nb
                        if t > 1.0:
                            continue
                        x, z = ax_ + (bx_ - ax_) * t, az_ + (bz_ - az_) * t
                        if abs(ax_ - (-0.8)) < 0.01 and abs(bx_ - (-0.8)) < 0.01 and abs(z) < 0.45 and course == 1:
                            continue                      # the gun slit
                        if dst and (course > 0 or rng.random() < 0.3):
                            continue
                        if dmg and course == 2 and (k % 3 == 0):
                            continue
                        bag((x, 0.15 + course * 0.26, z), -ang + rng.uniform(-0.07, 0.07), 1.05)
            if not fine and not dst:
                for (ax_, az_), (bx_, bz_) in zip(pts[:-1], pts[1:]):
                    seglen = math.hypot(bx_ - ax_, bz_ - az_)
                    ang = math.atan2(bz_ - az_, bx_ - ax_)
                    b.box("sandbag", ((ax_ + bx_) / 2, 0.42, (az_ + bz_) / 2), (0.72, 0.84, seglen), axis_angle(V([0, 1.0, 0]), -ang + math.pi / 2))
            if not dst:
                b.tube("steel", (-0.3, 0.62, -0.1), (-1.6, 0.66, 0.0), 0.04, 6)
                b.box("steel", (-0.2, 0.55, 0.0), (0.5, 0.14, 0.26))
            if dst and not fine:
                for k in range(5):
                    b.box("sandbag", (0.8 + 3.1 * math.cos(math.pi + k * 0.5), 0.12, 3.1 * math.sin(math.pi + k * 0.5)), (0.6, 0.24, 0.4), axis_angle(V([0, 1.0, 0]), k))
        for k in range(3 if fine else 0):
            c.decal_ground("oil", (rng.uniform(-0.4, 0.4), rng.uniform(-L / 3, L / 3)), 0.9, 0.9, rng.random() * 3, y=0.03)
        return c
    return build


def wood_fence(L, h=2.2, kind="wood"):
    """The original is a pale corrugated sheet panel on posts (despite the name)."""
    def build(state, lod, seed):
        c = Ctx(state, lod, seed, breach=(0.0, 1.0, -L / 2, 1.6), ledges=[(h, 0.8, 0.6), (0.5, 0.4, 0.6)], ground_h=0.5)
        b = c.b
        dst, dmg = state == "destroyed", state == "damaged"
        rng = c.rng
        zs = (0.0, -L / 2, -L)
        for zz in zs:
            lean = 0.3 if (dmg and zz == 0.0) else 0.0
            if lean:
                rot_about(c, axis_angle(V([0, 0, 1.0]), lean), (0.0, 0.0, zz))
            hh = h + 0.12 if not dst else (0.8 if zz == -L / 2 else 0.5)
            b.box("steel" if False else "wood", (0.0, hh / 2, zz), (0.14, hh, 0.14), axis_angle(V([1.0, 0, 0]), rng.uniform(-0.25, 0.25)) if dst else None)
            if not dst:
                b.box("galv", (0.0, hh + 0.02, zz), (0.2, 0.04, 0.2))
            b.M = None
        if not dst:
            ex = torn(L * 0.2, h * 0.5, 1.4, 0.7, 0.4) if dmg else None
            if dmg:
                rot_about(c, axis_angle(V([0, 0, 1.0]), 0.3), (0.0, 0.0, 0.0))
                clad(c, "palesheet", (0.08, 0.0, 0.0), (0, 0, -1), L / 2, (0, 1, 0), h, (1, 0, 0), "corr", extra=ex, thick=0.04, tear_disp=curl(0, 0, 1, 1, 0.12), v_extra=(h * 0.3, h * 0.7))
                clad(c, "palesheet", (-0.08, 0.0, -L / 2), (0, 0, 1), L / 2, (0, 1, 0), h, (-1, 0, 0), "corr", thick=0.0)
                b.M = None
                clad(c, "palesheet", (0.08, 0.0, -L / 2), (0, 0, -1), L / 2, (0, 1, 0), h, (1, 0, 0), "corr", thick=0.0)
                clad(c, "palesheet", (-0.08, 0.0, -L), (0, 0, 1), L / 2, (0, 1, 0), h, (-1, 0, 0), "corr", thick=0.0)
            else:
                clad(c, "palesheet", (0.08, 0.0, 0.0), (0, 0, -1), L, (0, 1, 0), h, (1, 0, 0), "corr", thick=0.0)
                clad(c, "palesheet", (-0.08, 0.0, -L), (0, 0, 1), L, (0, 1, 0), h, (-1, 0, 0), "corr", thick=0.0)
                b.box("galv", (0.0, h + 0.03, -L / 2), (0.2, 0.06, L))
        else:
            for k in range(5):
                Rm = axis_angle(V([1.0, 0, 0]), rng.uniform(-0.5, 0.5)) @ axis_angle(V([0, 1.0, 0]), rng.uniform(-0.6, 0.6))
                b.M = (Rm, V([rng.uniform(-0.7, 0.7), 0.15 + 0.08 * k, -1.2 - 1.5 * k]))
                clad(c, "palesheet", (0, 0, -0.9), (0, 0, 1), 1.8, (1, 0, 0), 1.0, (0, 1, 0), "flat")
                b.M = None
            c.decal_ground("soot", (0.0, -L / 2), 3.0, L * 0.9, 0.0, y=0.03)
        return c
    return build


def shanty_fence(L=8.5, h=2.3):
    """Ragged, mismatched dark sheets and boards, with gaps and a varied skyline."""
    def build(state, lod, seed):
        c = Ctx(state, lod, seed, breach=(0.0, 1.2, -L / 2, 1.6), ledges=[(h, 0.8, 0.9)], ground_h=0.5)
        b = c.b
        fine = c.fine
        dst, dmg = state == "destroyed", state == "damaged"
        rng = np.random.default_rng(seed + 11)
        z = 0.0
        pieces = []
        while z > -L + 0.2:
            w = float(rng.uniform(0.5, 1.4)); w = min(w, z + L - 0.05)
            pieces.append((z - w / 2, w, float(rng.uniform(1.2, 2.7)), float(rng.uniform(-0.07, 0.07)), int(rng.integers(0, 3))))
            z -= w + float(rng.uniform(0.0, 0.2))
        mats = ("darksheet", "darkboards", "darksheet")
        for zz in (0.0, -L * 0.35, -L * 0.7, -L + 0.1):
            hh = h + 0.35 if not dst else 0.7
            b.box("darkboards", (0.0, hh / 2, zz), (0.16, hh, 0.16), axis_angle(V([1.0, 0, 0]), rng.uniform(-0.2, 0.2)) if dst else None)
        for k, (zc, w, hgt, lean, mi) in enumerate(pieces):
            if dst and k % 3:
                continue
            if dmg and k in (2, 3):
                hgt *= 0.45
            if dst:
                Rm = axis_angle(V([0, 0, 1.0]), 1.45) @ axis_angle(V([0, 1.0, 0]), rng.uniform(-0.6, 0.6))
                b.M = (Rm, V([rng.uniform(-0.6, 0.6), 0.1 + 0.06 * (k % 4), zc]))
                b.box(mats[mi], (0, hgt / 2, 0), (0.04, hgt, w))
                b.M = None
                continue
            rot_about(c, axis_angle(V([0, 0, 1.0]), lean), (0.0, 0.0, zc))
            xoff = 0.09 * ((k % 2) * 2 - 1)
            if mi == 1 or not fine:
                b.box("darkboards", (xoff, hgt / 2, zc), (0.05, hgt, w))
            else:
                clad(c, "darksheet", (xoff + 0.03, 0.0, zc + w / 2), (0, 0, -1), w, (0, 1, 0), hgt, (1, 0, 0), "corr", thick=0.04)
                clad(c, "darksheet", (xoff - 0.03, 0.0, zc - w / 2), (0, 0, 1), w, (0, 1, 0), hgt, (-1, 0, 0), "corr", thick=0.0)
                b.box("darksheet", (xoff, hgt, zc), (0.07, 0.04, w)) if False else None
            b.M = None
        if dst:
            c.decal_ground("soot", (0.0, -L / 2), 3.0, L * 0.9, 0.0, y=0.03)
        return c
    return build


def panel_face(c, sgn, zb0, zb1, y0, y1, hx, style, keepf, topfn, mat="concrete"):
    """Large cast-concrete panels (2.8 to 3.4 m modules) with deep bevelled joints on one face of a wall body (x = sgn * hx); the l_ walls get a
    raised X brace on each panel. keepf(u, v) < 0.4 drops a panel (breach); topfn(z) is the wall's top height there."""
    b = c.b
    rng = c.rng
    L = zb1 - zb0
    hh_all = y1 - y0
    pw_ = {"s": 5.2, "l": 4.6, "d": 5.0}[style] + 0.2 * hh_all   # the originals show about 2-3 big modules per section
    npan = max(1, int(round(L / pw_)))
    w = L / npan
    rows = max(1, int(round((y1 - y0) / (pw_ * 0.9))))
    ch = (y1 - y0) / rows
    for j in range(rows):
        for k in range(npan):
            za, zb = zb0 + k * w, zb0 + (k + 1) * w
            zc = (za + zb) / 2
            yc = y0 + (j + 0.5) * ch
            if yc - ch / 2 > float(topfn(zc)) - 0.3:
                continue
            u = (zc - zb0) if sgn < 0 else (zb1 - zc)
            if keepf is not None and float(keepf(u, yc)) < 0.5:
                continue
            col = (0, rng.uniform(0.0, 0.3), 0)
            hh = min(ch, float(topfn(zc)) - (y0 + j * ch)) if (y0 + (j + 1) * ch) > float(topfn(zc)) else ch
            if hh < 0.8:
                continue
            ycc = y0 + j * ch + hh / 2
            # panel slab and a smaller, proud second slab: the deep bevelled joint reads as a shadow gap
            b.box(mat, (sgn * (hx + 0.08), ycc, zc), (0.16, hh - 0.34, w - 0.34), None, col=col)
            b.box(mat, (sgn * (hx + 0.18), ycc, zc), (0.1, hh - 0.9, w - 0.9), None, col=col)
            if style == "l" and hh > 1.5:
                d_ = math.hypot(w - 0.9, hh - 0.9)
                ang = math.atan2(hh - 0.9, w - 0.9)
                for sg in (-1, 1):
                    Rm = axis_angle(V([1.0, 0, 0]), sg * ang)
                    b.box(mat, (sgn * (hx + 0.4), ycc, zc), (0.16, 0.5, d_), Rm, col=col)


def wall(h_body, h_post, post_w, body_w, post_z, body_z, mat="concrete", seams=4, name=""):
    """A wall piece in the originals' frame: a post block at z in post_z (x +-post_w/2) and the body along body_z (x +-body_w/2)."""
    def build(state, lod, seed):
        zp0, zp1 = post_z
        zb0, zb1 = body_z
        lb = zb1 - zb0
        c = Ctx(state, lod, seed, breach=(0.0, h_body * 0.5, (zb0 + zb1) / 2, 3.2), ledges=[(h_body, 2.0, 0.9), (h_post, 2.0, 0.9)], ao_rings=[(h_body, 1.2, 0.35)], ground_h=2.0)
        b = c.b
        fine = c.fine
        dst, dmg = state == "destroyed", state == "damaged"
        rng = c.rng
        bw = body_w / 2
        pw = post_w / 2
        # footing and the post: a battered block with a capped top, a recess band and a tint band
        b.box("concrete_dark", (0, 0.25, (zb0 + zp0) / 2 if False else (zp0 + zp1) / 2), (post_w + 0.5, 0.5, zp1 - zp0 + 0.5))
        b.box("concrete_dark", (0, 0.25, (zb0 + zb1) / 2), (body_w + 0.4, 0.5, lb + 0.4))
        hp = h_post if not dst else h_post * 0.35
        pk = (lambda u, v, hp=hp: hp * (0.55 + 0.45 * np.abs(np.sin(np.asarray(u) * 1.7 + 0.4))) - np.asarray(v)) if dst else None
        for sgn in (-1, 1):
            clad(c, mat, (sgn * pw, 0.5, zp0 if sgn < 0 else zp1), (0, 0, 1) if sgn < 0 else (0, 0, -1), zp1 - zp0, (0, 1, 0), h_post - 0.5, (sgn, 0, 0), "flat", extra=pk, thick=0.1, edge_mat="rust")
        for zz, nz in ((zp0, -1), (zp1, 1)):
            clad(c, mat, (pw if nz < 0 else -pw, 0.5, zz), (-1, 0, 0) if nz < 0 else (1, 0, 0), post_w, (0, 1, 0), h_post - 0.5, (0, 0, nz), "flat", extra=pk, thick=0.1, edge_mat="rust")
        if not dst:
            b.box("concrete_dark", (0, h_post + 0.12, (zp0 + zp1) / 2), (post_w + 0.3, 0.25, zp1 - zp0 + 0.3))
            b.box("trim", (0, h_post * 0.72, (zp0 + zp1) / 2), (post_w + 0.04, 0.5, zp1 - zp0 + 0.04), None, band=6, col=(1, 0, 0)) if False else None
            b.quad("trim", V([pw + 0.03, h_post * 0.75, (zp0 + zp1) / 2]), V([0, 0, 1.0]), V([0, 1.0, 0]), zp1 - zp0, 0.55, (0, 0.5, (zp1 - zp0) * 0.3, 0), normal=(1, 0, 0), band=6, col=(1, 0, 0))
            b.quad("trim", V([-pw - 0.03, h_post * 0.75, (zp0 + zp1) / 2]), V([0, 0, -1.0]), V([0, 1.0, 0]), zp1 - zp0, 0.55, (0, 0.5, (zp1 - zp0) * 0.3, 0), normal=(-1, 0, 0), band=6, col=(1, 0, 0))
            for j in range(3):
                b.box("concrete_dark", (0, h_post * (0.25 + 0.25 * j), (zp0 + zp1) / 2), (post_w + 0.12, 0.18, zp1 - zp0 + 0.12))
        # the body: two clad faces, a coping, expansion joints and buttress pilasters; breach cut when damaged, ridge when destroyed
        tear = torn(lb * 0.5, h_body * 0.5, min(4.0, lb * 0.18), h_body * 0.32, 0.4) if dmg else None
        kd = ridge_keep(lb, h_body, rng, 0.08, 0.42, 0.1) if dst else None
        for sgn in (-1, 1):
            clad(c, mat, (sgn * bw, 0.5, zb0 if sgn < 0 else zb1), (0, 0, 1) if sgn < 0 else (0, 0, -1), lb, (0, 1, 0), h_body - 0.5, (sgn, 0, 0), "flat", extra=tear or kd, thick=0.18, edge_mat="rust",
                 tear_disp=curl(0, 0, 1, 1, 0.12) if tear else None, v_extra=(h_body * 0.3, h_body * 0.7) if tear else ())
        if not dst:
            b.box("concrete_dark", (0, h_body + 0.1, (zb0 + zb1) / 2), (body_w + 0.3, 0.22, lb + 0.2))
            for k in range(1, seams if fine else 0):
                zz = zb0 + lb * k / seams
                b.box("concrete_dark", (0, h_body / 2 + 0.25, zz), (body_w + 0.22, h_body - 0.5, 0.3))
            for j in range(1, 3 if fine else 0):
                b.box("concrete_dark", (0, h_body * j / 3, (zb0 + zb1) / 2), (body_w + 0.2, 0.3, lb))
            for sgn in (-1, 1):
                c.decal_wall("streak_a", (sgn * (bw + 0.02), 0, zb0 + lb * 0.3), (0, 0, 1) if sgn > 0 else (0, 0, -1), 3.0, h_body * 0.2, h_body, (sgn, 0, 0), off=0.04) if fine else None
                c.decal_wall("rust_bleed", (sgn * (bw + 0.02), 0, zb0 + lb * 0.75), (0, 0, 1) if sgn > 0 else (0, 0, -1), 2.5, h_body * 0.3, h_body * 0.7, (sgn, 0, 0), off=0.04) if fine else None
        if dmg:
            for k in range(10 if fine else 4):
                b.tube("steel", (rng.uniform(-bw * 0.8, bw * 0.8), h_body * 0.45 + rng.uniform(-1.5, 1.5), (zb0 + zb1) / 2 + rng.uniform(-2.5, 2.5)),
                       (rng.uniform(-bw * 0.8, bw * 0.8), h_body * 0.45 + rng.uniform(0, 1.8), (zb0 + zb1) / 2 + rng.uniform(-2.5, 2.5)), 0.04, 5)
            interior_n = None
            b.box("interior", (0, h_body * 0.5, (zb0 + zb1) / 2), (body_w - 0.4, h_body - 0.6, lb - 0.4)) if False else None
        if dmg or dst:
            n = int(14 + h_body * 1.5) if fine else int(5 + h_body * 0.4)
            for k in range(n):
                sz = (rng.uniform(0.6, 1.6) * (h_body ** 0.3), rng.uniform(0.4, 1.0) * (h_body ** 0.3), rng.uniform(0.6, 1.4) * (h_body ** 0.3))
                zc = (zb0 + zb1) / 2 + rng.uniform(-lb * (0.25 if dmg else 0.45), lb * (0.25 if dmg else 0.45))
                b.box("concrete" if k % 3 else "concrete_dark", (rng.uniform(-bw * 1.8, bw * 1.8), sz[1] / 2 + 0.2, zc), sz,
                      axis_angle(V([0, 1.0, 0]), rng.random() * 3.0) @ axis_angle(V([1.0, 0, 0]), rng.uniform(-0.3, 0.3)))
            c.decal_ground("soot", (0, (zb0 + zb1) / 2), body_w * 3.5, lb * 0.9, 0.0, y=0.52)
        if dst:
            for k in range(8):
                b.tube("steel", (rng.uniform(-bw, bw), 0.5, (zb0 + zb1) / 2 + rng.uniform(-lb * 0.4, lb * 0.4)), (rng.uniform(-bw, bw), 0.5 + rng.uniform(0.6, 2.2), (zb0 + zb1) / 2 + rng.uniform(-lb * 0.4, lb * 0.4)), 0.035, 5)
        return c
    return build


def post_only(h_post, post_w, post_z, mat="concrete"):
    def build(state, lod, seed):
        w = wall(h_post, h_post, post_w, post_w, post_z, (post_z[1] + 0.2, post_z[1] + 0.3), mat)
        return w(state, lod, seed)
    return build



# ============================================================================== second pass: identity fixes
def pillow(c, centre, size, yaw=0.0, tilt=0.0, sag=0.0, mat="sandbag", nu=8, nv=5):
    """A canvas sandbag: a pillowed superellipsoid, flattened on the bottom, with a sagging top; true volume, soft normals."""
    a, bb, cc = size[0] / 2, size[1] / 2, size[2] / 2
    th = np.linspace(0, TAU, nu + 1)
    ph = np.linspace(-math.pi / 2, math.pi / 2, nv + 1)
    P = np.zeros((nv + 1, nu + 1, 3)); N = np.zeros_like(P)
    for j, f in enumerate(ph):
        for i, t in enumerate(th):
            ex = 0.45
            cx = np.sign(math.cos(t)) * abs(math.cos(t)) ** ex
            cz = np.sign(math.sin(t)) * abs(math.sin(t)) ** ex
            r_ = math.cos(f) ** 0.6
            y = np.sign(math.sin(f)) * abs(math.sin(f)) ** 0.7
            top_sag = -sag * max(0.0, y) * (1 - (cx ** 2 + cz ** 2) / 2)
            P[j, i] = (a * r_ * cx, bb * (y if y > -0.7 else -0.7 - 0.0) + top_sag * bb, cc * r_ * cz)
            N[j, i] = (r_ * cx / a, y / bb if y > 0 else y * 0.5 / bb, r_ * cz / cc)
    Rm = axis_angle(V([0, 1.0, 0]), yaw) @ axis_angle(V([1.0, 0, 0]), tilt)
    Pw = np.asarray(centre, float) + (P.reshape(-1, 3) @ Rm.T)
    Nw = N.reshape(-1, 3) @ Rm.T
    idx = []
    for j in range(nv):
        for i in range(nu):
            q = j * (nu + 1) + i
            idx += [(q, q + 1, q + nu + 1), (q + 1, q + nu + 2, q + nu + 1)]
    c.b.add(mat, Pw, Nw, np.stack([P.reshape(-1, 3)[:, 0], P.reshape(-1, 3)[:, 2]], 1), idx, col=(0, c.rng.uniform(0, 0.35), 0))


def sandbag_wall(L=8.4, courses=3, bunker=False):
    def build(state, lod, seed):
        c = Ctx(state, lod, seed, breach=(0.0, 0.5, 0.0, 1.8), ledges=[(0.9, 0.5, 0.5)], ground_h=0.4)
        b = c.b
        fine = c.fine
        dst, dmg = state == "destroyed", state == "damaged"
        rng = c.rng
        bag = lambda p, yaw, sc=1.0, tilt=0.0, sag=0.25: pillow(c, p, (0.7 * sc, 0.3 * sc, 0.42 * sc), yaw, tilt, sag)
        if not bunker:
            n = int(L / 0.64)
            for course in range(courses):
                if not fine:
                    if course < (courses if not (dmg or dst) else (2 if dmg else 1)):
                        b.box("sandbag", (0, 0.14 + course * 0.27, 0), (0.66, 0.28, L - (0.35 if course % 2 else 0)))
                    continue
                for k in range(n):
                    z = -L / 2 + 0.35 + k * 0.64 + (0.32 if course % 2 else 0.0)
                    if z > L / 2 - 0.2:
                        continue
                    if dst:
                        if course > 0 or rng.random() < 0.3:
                            continue
                        bag((rng.uniform(-0.5, 0.5), 0.12, z + rng.uniform(-0.3, 0.3)), rng.uniform(-0.7, 0.7) + math.pi / 2, 0.95, rng.uniform(-0.3, 0.3), 0.1)
                        continue
                    if dmg and course >= 2 and abs(z) < 2.0:
                        continue
                    if dmg and course == 1 and abs(z) < 0.9:
                        continue
                    bag((rng.uniform(-0.03, 0.03), 0.15 + course * 0.26, z), math.pi / 2 + rng.uniform(-0.08, 0.08), rng.uniform(0.96, 1.04))
            if dmg or dst:
                for k in range(8 if fine else 2):
                    bag((rng.uniform(-0.8, 0.8), 0.12, rng.uniform(-2.0, 2.0)), rng.uniform(0, 3), 0.95, rng.uniform(-0.4, 0.4), 0.1)
        else:
            # five angled straight runs round a gun slit (open toward +x), bags laid along each run; the middle run has a 0.5 m slit
            pts = [(3.7, -4.2), (1.3, -4.2), (-0.8, -1.9), (-0.8, 1.9), (1.3, 4.2), (3.7, 4.2)]
            for (ax_, az_), (bx_, bz_) in zip(pts[:-1], pts[1:]):
                seglen = math.hypot(bx_ - ax_, bz_ - az_)
                ang = math.atan2(bz_ - az_, bx_ - ax_)
                nb = max(2, int(seglen / 0.66))
                for course in range(courses):
                    for k in range(nb if fine else 0):
                        t = (k + 0.5 + (0.5 if course % 2 else 0.0)) / nb
                        if t > 1.0:
                            continue
                        x, z = ax_ + (bx_ - ax_) * t, az_ + (bz_ - az_) * t
                        if abs(ax_ - (-0.8)) < 0.01 and abs(bx_ - (-0.8)) < 0.01 and abs(z) < 0.45 and course == 1:
                            continue                      # the gun slit
                        if dst and (course > 0 or rng.random() < 0.3):
                            continue
                        if dmg and course == 2 and (k % 3 == 0):
                            continue
                        bag((x, 0.15 + course * 0.26, z), -ang + rng.uniform(-0.07, 0.07), 1.05)
            if not fine and not dst:
                for (ax_, az_), (bx_, bz_) in zip(pts[:-1], pts[1:]):
                    seglen = math.hypot(bx_ - ax_, bz_ - az_)
                    ang = math.atan2(bz_ - az_, bx_ - ax_)
                    b.box("sandbag", ((ax_ + bx_) / 2, 0.42, (az_ + bz_) / 2), (0.72, 0.84, seglen), axis_angle(V([0, 1.0, 0]), -ang + math.pi / 2))
            if not dst:
                b.tube("steel", (-0.3, 0.62, -0.1), (-1.6, 0.66, 0.0), 0.04, 6)
                b.box("steel", (-0.2, 0.55, 0.0), (0.5, 0.14, 0.26))
            if dst and not fine:
                for k in range(5):
                    b.box("sandbag", (0.8 + 3.1 * math.cos(math.pi + k * 0.5), 0.12, 3.1 * math.sin(math.pi + k * 0.5)), (0.6, 0.24, 0.4), axis_angle(V([0, 1.0, 0]), k))
        for k in range(3 if fine else 0):
            c.decal_ground("oil", (rng.uniform(-0.4, 0.4), rng.uniform(-L / 3, L / 3)), 0.9, 0.9, rng.random() * 3, y=0.03)
        return c
    return build


def wood_fence(L, h=2.2, kind="wood"):
    """The original is a pale corrugated sheet panel on posts (despite the name)."""
    def build(state, lod, seed):
        c = Ctx(state, lod, seed, breach=(0.0, 1.0, -L / 2, 1.6), ledges=[(h, 0.8, 0.6), (0.5, 0.4, 0.6)], ground_h=0.5)
        b = c.b
        dst, dmg = state == "destroyed", state == "damaged"
        rng = c.rng
        zs = (0.0, -L / 2, -L)
        for zz in zs:
            lean = 0.3 if (dmg and zz == 0.0) else 0.0
            if lean:
                rot_about(c, axis_angle(V([0, 0, 1.0]), lean), (0.0, 0.0, zz))
            hh = h + 0.12 if not dst else (0.8 if zz == -L / 2 else 0.5)
            b.box("steel" if False else "wood", (0.0, hh / 2, zz), (0.14, hh, 0.14), axis_angle(V([1.0, 0, 0]), rng.uniform(-0.25, 0.25)) if dst else None)
            if not dst:
                b.box("galv", (0.0, hh + 0.02, zz), (0.2, 0.04, 0.2))
            b.M = None
        if not dst:
            ex = torn(L * 0.2, h * 0.5, 1.4, 0.7, 0.4) if dmg else None
            if dmg:
                rot_about(c, axis_angle(V([0, 0, 1.0]), 0.3), (0.0, 0.0, 0.0))
                clad(c, "palesheet", (0.08, 0.0, 0.0), (0, 0, -1), L / 2, (0, 1, 0), h, (1, 0, 0), "corr", extra=ex, thick=0.04, tear_disp=curl(0, 0, 1, 1, 0.12), v_extra=(h * 0.3, h * 0.7))
                clad(c, "palesheet", (-0.08, 0.0, -L / 2), (0, 0, 1), L / 2, (0, 1, 0), h, (-1, 0, 0), "corr", thick=0.0)
                b.M = None
                clad(c, "palesheet", (0.08, 0.0, -L / 2), (0, 0, -1), L / 2, (0, 1, 0), h, (1, 0, 0), "corr", thick=0.0)
                clad(c, "palesheet", (-0.08, 0.0, -L), (0, 0, 1), L / 2, (0, 1, 0), h, (-1, 0, 0), "corr", thick=0.0)
            else:
                clad(c, "palesheet", (0.08, 0.0, 0.0), (0, 0, -1), L, (0, 1, 0), h, (1, 0, 0), "corr", thick=0.0)
                clad(c, "palesheet", (-0.08, 0.0, -L), (0, 0, 1), L, (0, 1, 0), h, (-1, 0, 0), "corr", thick=0.0)
                b.box("galv", (0.0, h + 0.03, -L / 2), (0.2, 0.06, L))
        else:
            for k in range(5):
                Rm = axis_angle(V([1.0, 0, 0]), rng.uniform(-0.5, 0.5)) @ axis_angle(V([0, 1.0, 0]), rng.uniform(-0.6, 0.6))
                b.M = (Rm, V([rng.uniform(-0.7, 0.7), 0.15 + 0.08 * k, -1.2 - 1.5 * k]))
                clad(c, "palesheet", (0, 0, -0.9), (0, 0, 1), 1.8, (1, 0, 0), 1.0, (0, 1, 0), "flat")
                b.M = None
            c.decal_ground("soot", (0.0, -L / 2), 3.0, L * 0.9, 0.0, y=0.03)
        return c
    return build


def shanty_fence(L=8.5, h=2.3):
    """Ragged, mismatched dark sheets and boards, with gaps and a varied skyline."""
    def build(state, lod, seed):
        c = Ctx(state, lod, seed, breach=(0.0, 1.2, -L / 2, 1.6), ledges=[(h, 0.8, 0.9)], ground_h=0.5)
        b = c.b
        fine = c.fine
        dst, dmg = state == "destroyed", state == "damaged"
        rng = np.random.default_rng(seed + 11)
        z = 0.0
        pieces = []
        while z > -L + 0.2:
            w = float(rng.uniform(0.5, 1.4)); w = min(w, z + L - 0.05)
            pieces.append((z - w / 2, w, float(rng.uniform(1.2, 2.7)), float(rng.uniform(-0.07, 0.07)), int(rng.integers(0, 3))))
            z -= w + float(rng.uniform(0.0, 0.2))
        mats = ("darksheet", "darkboards", "darksheet")
        for zz in (0.0, -L * 0.35, -L * 0.7, -L + 0.1):
            hh = h + 0.35 if not dst else 0.7
            b.box("darkboards", (0.0, hh / 2, zz), (0.16, hh, 0.16), axis_angle(V([1.0, 0, 0]), rng.uniform(-0.2, 0.2)) if dst else None)
        for k, (zc, w, hgt, lean, mi) in enumerate(pieces):
            if dst and k % 3:
                continue
            if dmg and k in (2, 3):
                hgt *= 0.45
            if dst:
                Rm = axis_angle(V([0, 0, 1.0]), 1.45) @ axis_angle(V([0, 1.0, 0]), rng.uniform(-0.6, 0.6))
                b.M = (Rm, V([rng.uniform(-0.6, 0.6), 0.1 + 0.06 * (k % 4), zc]))
                b.box(mats[mi], (0, hgt / 2, 0), (0.04, hgt, w))
                b.M = None
                continue
            rot_about(c, axis_angle(V([0, 0, 1.0]), lean), (0.0, 0.0, zc))
            xoff = 0.09 * ((k % 2) * 2 - 1)
            if mi == 1 or not fine:
                b.box("darkboards", (xoff, hgt / 2, zc), (0.05, hgt, w))
            else:
                clad(c, "darksheet", (xoff + 0.03, 0.0, zc + w / 2), (0, 0, -1), w, (0, 1, 0), hgt, (1, 0, 0), "corr", thick=0.04)
                clad(c, "darksheet", (xoff - 0.03, 0.0, zc - w / 2), (0, 0, 1), w, (0, 1, 0), hgt, (-1, 0, 0), "corr", thick=0.0)
                b.box("darksheet", (xoff, hgt, zc), (0.07, 0.04, w)) if False else None
            b.M = None
        if dst:
            c.decal_ground("soot", (0.0, -L / 2), 3.0, L * 0.9, 0.0, y=0.03)
        return c
    return build


def panel_face(c, sgn, zb0, zb1, y0, y1, hx, style, keepf, topfn, mat="concrete"):
    """Large cast-concrete panels (2.8 to 3.4 m modules) with deep bevelled joints on one face of a wall body (x = sgn * hx); the l_ walls get a
    raised X brace on each panel. keepf(u, v) < 0.4 drops a panel (breach); topfn(z) is the wall's top height there."""
    b = c.b
    rng = c.rng
    L = zb1 - zb0
    hh_all = y1 - y0
    pw_ = {"s": 5.2, "l": 4.6, "d": 5.0}[style] + 0.2 * hh_all   # the originals show about 2-3 big modules per section
    npan = max(1, int(round(L / pw_)))
    w = L / npan
    rows = max(1, int(round((y1 - y0) / (pw_ * 0.9))))
    ch = (y1 - y0) / rows
    for j in range(rows):
        for k in range(npan):
            za, zb = zb0 + k * w, zb0 + (k + 1) * w
            zc = (za + zb) / 2
            yc = y0 + (j + 0.5) * ch
            if yc - ch / 2 > float(topfn(zc)) - 0.3:
                continue
            u = (zc - zb0) if sgn < 0 else (zb1 - zc)
            if keepf is not None and float(keepf(u, yc)) < 0.5:
                continue
            col = (0, rng.uniform(0.0, 0.3), 0)
            hh = min(ch, float(topfn(zc)) - (y0 + j * ch)) if (y0 + (j + 1) * ch) > float(topfn(zc)) else ch
            if hh < 0.8:
                continue
            ycc = y0 + j * ch + hh / 2
            # panel slab and a smaller, proud second slab: the deep bevelled joint reads as a shadow gap
            b.box(mat, (sgn * (hx + 0.08), ycc, zc), (0.16, hh - 0.34, w - 0.34), None, col=col)
            b.box(mat, (sgn * (hx + 0.18), ycc, zc), (0.1, hh - 0.9, w - 0.9), None, col=col)
            if style == "l" and hh > 1.5:
                d_ = math.hypot(w - 0.9, hh - 0.9)
                ang = math.atan2(hh - 0.9, w - 0.9)
                for sg in (-1, 1):
                    Rm = axis_angle(V([1.0, 0, 0]), sg * ang)
                    b.box(mat, (sgn * (hx + 0.4), ycc, zc), (0.16, 0.5, d_), Rm, col=col)


def hex_frames(c, sgn, zb0, zb1, y0, y1, hx, keepf, mat="concrete"):
    """The d_ walls' lower band: a raised honeycomb lattice of hexagon frames."""
    b = c.b
    H_ = y1 - y0
    r = max(0.8, min(1.5, H_ / 4.0))
    dz, dy = 1.5 * r * 1.02, math.sqrt(3) * r * 1.02
    ncol = int((zb1 - zb0) / dz) + 1
    for i in range(ncol):
        zc = zb0 + 0.8 + i * dz
        if zc > zb1 - 0.5:
            continue
        for j in range(int(H_ / dy) + 1):
            yc = y0 + 0.5 * dy + j * dy + (dy / 2 if i % 2 else 0.0)
            if yc + dy * 0.45 > y1:
                continue
            u = (zc - zb0) if sgn < 0 else (zb1 - zc)
            if keepf is not None and float(keepf(u, yc)) < 0.5:
                continue
            for e in range(6):
                a = e * math.pi / 3 + math.pi / 6
                pz, py = zc + r * 0.88 * math.cos(a), yc + r * 0.88 * math.sin(a)
                b.box("concrete", (sgn * (hx + 0.16), py, pz), (0.26, 0.4, r * 0.95), axis_angle(V([1.0, 0, 0]), -(a + math.pi / 2)))


def wall(h_body, h_post, post_w, body_w, post_z, body_z, mat="concrete", seams=4, name="", style="s"):
    """A wall piece in the originals' frame: a battered post with an inset panel, and a body of large cast-concrete panels with deep joints.
    s: plain slabs and a flat coping. l: green-grey panels with a raised X brace, a body that steps down from the post (angled shoulder), a tall
    post with a chamfered cap. d: pale upper panels over a lower band carrying a raised honeycomb frame, a ribbed post."""
    # slim posts (Lee): the originals' blocks read as narrow knobbed posts, so the block is narrower than the original's footprint
    K = 0.75
    zmid = (post_z[0] + post_z[1]) / 2
    post_z = (zmid - (post_z[1] - post_z[0]) * K / 2, zmid + (post_z[1] - post_z[0]) * K / 2)
    post_w = post_w * K
    def build(state, lod, seed):
        zp0, zp1 = post_z
        zb0, zb1 = zp1, body_z[1]
        lb = zb1 - zb0
        c = Ctx(state, lod, seed, breach=(0.0, h_body * 0.5, (zb0 + zb1) / 2, 3.2), ledges=[(h_body, 2.0, 0.8), (h_post, 2.0, 0.8)], ao_rings=[(h_body, 1.2, 0.3)], ground_h=2.0)
        b = c.b
        fine = c.fine
        dst, dmg = state == "destroyed", state == "damaged"
        rng = c.rng
        bw = body_w / 2
        pw = post_w / 2
        flare = 0.3 + 0.03 * h_body
        hb = 0.2 * h_body
        base_y = 0.4
        # l_: the body steps down away from the post along a 45-degree shoulder
        drop = 0.22 * h_body if style == "l" else 0.0
        zs0, zs1 = zb0 + 2.0, zb0 + 2.0 + drop
        def topfn(z):
            if style != "l":
                return h_body
            return h_body - drop * np.clip((np.asarray(z) - zs0) / max(zs1 - zs0, 1e-3), 0, 1)
        b.box("concrete_dark", (0, 0.2, (zp0 + zb1) / 2), (post_w + 0.6, 0.4, zb1 - zp0 + 0.6))
        tear = H.torn(lb * 0.5, h_body * 0.5, min(4.0, lb * 0.18), h_body * 0.32, 0.4) if dmg else None
        kd = ridge_keep(lb, h_body, rng, 0.08, 0.42, 0.1) if dst else None
        keepf = tear or kd
        def topkeep(sgn):
            if style != "l":
                return None
            return lambda u, v: topfn(zb0 + u if sgn < 0 else zb1 - u) - (v + base_y + hb)
        for sgn in (-1, 1):
            zA, dz = (zb0, (0, 0, 1)) if sgn < 0 else (zb1, (0, 0, -1))
            clad(c, mat, (sgn * (bw + flare), base_y, zA), dz, lb, (-sgn * flare, hb, 0), hb, (sgn, 0.3, 0), "flat")
            tk = topkeep(sgn)
            def ex(u, v, k=keepf, tk=tk, o=base_y + hb):
                r = None
                if k is not None:
                    r = k(u, v + o)
                if tk is not None:
                    t = tk(u, v)
                    r = t if r is None else np.minimum(r, t)
                return r
            clad(c, mat, (sgn * bw, base_y + hb, zA), dz, lb, (0, 1, 0), h_body - base_y - hb, (sgn, 0, 0), "flat", extra=ex if (keepf is not None or tk is not None) else None, thick=0.18, edge_mat="rust",
                 tear_disp=curl(0, 0, 1, 1, 0.12) if tear else None, v_extra=(h_body * 0.3, h_body * 0.7) if tear else ())
        clad(c, mat, (bw + flare, base_y, zb1), (-1, 0, 0), body_w + 2 * flare, (0, 1, 0), h_body - base_y, (0, 0, 1), "flat", extra=(lambda u, v: (h_body - base_y) * 0.4 - np.asarray(v)) if dst else None, thick=0.1)
        if not dst:
            for sgn in (-1, 1):
                skip = None
                if tear:
                    skip = lambda u, v, t=tear: t(u, v - (base_y + hb))
                y_up = base_y + hb
                if style == "d":
                    band = base_y + hb + 0.38 * (h_body - hb - base_y)
                    if fine:
                        panel_face(c, sgn, zb0, zb1, band, h_body, bw, "d", skip, topfn, mat)
                        hex_frames(c, sgn, zb0, zb1, y_up, band, bw, skip, mat)
                    b.box(mat, (sgn * (bw + 0.06), band, (zb0 + zb1) / 2), (0.16, 0.22, lb))
                elif fine:
                    panel_face(c, sgn, zb0, zb1, y_up, h_body, bw, style, skip, topfn, mat)
            if not fine:                                                           # LOD1: joints read as stripes and a few boxes
                nm = max(2, int(round(lb / (5.2 + 0.2 * h_body))))   # the originals show a few big modules; joints are thin pale bevels
                for k in range(1, nm):
                    zz = zb0 + k * lb / nm
                    b.box(mat, (0, (topfn(zz) + base_y + hb) / 2, zz), (body_w + 0.5, topfn(zz) - base_y - hb, 0.3), None, col=(0, 1.0, 0))
                if style != "d":
                    b.box(mat, (0, base_y + hb + (h_body - base_y - hb) * 0.55, (zb0 + zb1) / 2), (body_w + 0.36, 0.34, lb), None, col=(0, 0.6, 0))  # a raised belt course
        # coping
        if not dst:
            if style == "s":
                b.box(mat, (0, h_body + 0.14, (zb0 + zb1) / 2), (body_w + 0.6, 0.28, lb + 0.2))
            elif style == "l":
                b.box(mat, (0, h_body + 0.1, (zb0 + (zs0)) / 2), (body_w + 0.4, 0.22, zs0 - zb0 + 0.1))
                ang = math.atan2(drop, zs1 - zs0)
                b.box(mat, (0, h_body - drop / 2 + 0.1, (zs0 + zs1) / 2), (body_w + 0.4, 0.22, math.hypot(zs1 - zs0, drop)), axis_angle(V([1.0, 0, 0]), ang))
                b.box(mat, (0, h_body - drop + 0.1, (zs1 + zb1) / 2), (body_w + 0.4, 0.22, zb1 - zs1 + 0.1))
            else:
                b.box(mat, (0, h_body + 0.1, (zb0 + zb1) / 2), (body_w + 0.5, 0.2, lb + 0.2))
                b.box(mat, (0, h_body + 0.3, (zb0 + zb1) / 2), (body_w - 0.5, 0.2, lb))
            for sgn in (-1, 1):
                c.decal_wall("streak_a", (sgn * (bw + 0.05), 0, zb0 + lb * 0.3), (0, 0, 1) if sgn > 0 else (0, 0, -1), 3.0, h_body * 0.2, h_body, (sgn, 0, 0), off=0.3) if fine else None
        # ---- the post: battered, with bands, an inset (emblem-less) panel, a faction cap
        hp = h_post if not dst else h_post * 0.4
        pk = (lambda u, v, hp=hp: hp * (0.5 + 0.5 * np.abs(np.sin(np.asarray(u) * 1.7 + 0.4))) - np.asarray(v)) if dst else None
        pflare = 0.35 + 0.02 * h_post
        pmat = "wallpost_" + style   # bright post blocks against the body, as the originals' capped blocks read
        hpb = 0.22 * h_post
        pwid = zp1 - zp0
        for sgn in (-1, 1):
            zA, dz = (zp0, (0, 0, 1)) if sgn < 0 else (zp1, (0, 0, -1))
            clad(c, pmat, (sgn * (pw + pflare), base_y, zA), dz, pwid, (-sgn * pflare, hpb, 0), hpb, (sgn, 0.3, 0), "flat")
            ph = max(1.8, h_post * 0.22)
            hh = [] if dst else [(pwid / 2 - 0.9, h_post * 0.55 - base_y - hpb, pwid / 2 + 0.9, h_post * 0.55 - base_y - hpb + ph)]
            clad(c, pmat, (sgn * pw, base_y + hpb, zA), dz, pwid, (0, 1, 0), h_post - base_y - hpb, (sgn, 0, 0), "flat", holes=hh, extra=pk, thick=0.14, edge_mat="paint")
            if not dst:
                zc = (zp0 + zp1) / 2
                yc = base_y + hpb + hh[0][1] + ph / 2
                b.quad(pmat, V([sgn * (pw - 0.12), yc, zc]), V([0, 0, 1.0]), V([0, 1.0, 0]), 1.8, ph, (0, 1, 1, 0), normal=(sgn, 0, 0))
                if style == "d":
                    for r_ in range(-2, 3):
                        if r_ == 0:
                            continue
                        b.box(pmat, (sgn * (pw + 0.07), (base_y + h_post) / 2, zc + r_ * pwid * 0.18), (0.14, h_post - base_y - 0.8, 0.22))
        clad(c, pmat, (-pw - pflare, base_y, zp0), (1, 0, 0), post_w + 2 * pflare, (0, 1, 0), h_post - base_y, (0, 0, -1), "flat", thick=0.0)
        if not dst:
            zc = (zp0 + zp1) / 2
            for j in range(1, 3):
                b.box(pmat, (0, base_y + h_post * 0.3 * j, zc), (post_w + 0.2, 0.2, pwid + 0.2))
            rk = max(post_w, pwid) * 0.5                                           # a slim round-topped knob cap
            b.box(pmat, (0, h_post + 0.1, zc), (post_w + 0.3, 0.2, pwid + 0.3))
            b.revolve(pmat, [(rk * 0.8, h_post + 0.2), (rk * 0.78, h_post + 0.42), (rk * 0.6, h_post + 0.66), (rk * 0.3, h_post + 0.84), (0.0, h_post + 0.9)], 8 if fine else 5, cz=zc, uref=2.0)
        if dmg or dst:
            for k in range(10 if fine else 4):
                b.tube("steel", (rng.uniform(-bw * 0.8, bw * 0.8), h_body * 0.45 + rng.uniform(-1.5, 1.5), (zb0 + zb1) / 2 + rng.uniform(-2.5, 2.5)),
                       (rng.uniform(-bw * 0.8, bw * 0.8), h_body * 0.45 + rng.uniform(0, 1.8), (zb0 + zb1) / 2 + rng.uniform(-2.5, 2.5)), 0.04, 5)
            n = int(14 + h_body * 1.5) if fine else int(5 + h_body * 0.4)
            for k in range(n):
                sz = (rng.uniform(0.6, 1.6) * (h_body ** 0.3), rng.uniform(0.4, 1.0) * (h_body ** 0.3), rng.uniform(0.6, 1.4) * (h_body ** 0.3))
                zc = (zb0 + zb1) / 2 + rng.uniform(-lb * (0.25 if dmg else 0.45), lb * (0.25 if dmg else 0.45))
                b.box("concrete" if k % 3 else "concrete_dark", (rng.uniform(-bw * 1.8, bw * 1.8), sz[1] / 2 + 0.2, zc), sz, axis_angle(V([0, 1.0, 0]), rng.random() * 3.0) @ axis_angle(V([1.0, 0, 0]), rng.uniform(-0.3, 0.3)))
            c.decal_ground("soot", (0, (zb0 + zb1) / 2), body_w * 3.5, lb * 0.9, 0.0, y=0.45)
        return c
    return build


def post_only(h_post, post_w, post_z, mat="concrete", style="s"):
    def build(state, lod, seed):
        return wall(h_post * 0.4, h_post, post_w, post_w * 0.5, post_z, (post_z[1], post_z[1] + 0.01), mat, 1, "", style)(state, lod, seed)
    return build


MEMBERS = {}
SPECS = {
    "wirefence": (chain_fence(8.6, 3.2), "chain-link panel 8.6 m x 3.2 m (originals' bounds)"),
    "wirefencediag": (chain_fence(12.1, 3.2), "chain-link panel 12.1 m x 3.2 m"),
    "razorwirefence": (razor_fence(8.6), "slatted screen with razor-wire arms 8.6 m x 5.5 m"),
    "razorwirefencediag": (razor_fence(12.1), "slatted screen with razor-wire arms 12.1 m"),
    "woodenfence": (wood_fence(8.6, 2.2), "plank fence 8.6 m x 2.2 m"),
    "woodenfencediag": (wood_fence(12.2, 2.2), "plank fence 12.2 m"),
    "shantyfence": (shanty_fence(8.5, 2.3), "corrugated-sheet fence 8.5 m x 2.3 m"),
    "sandbagwall": (sandbag_wall(8.4), "sandbag wall 8.4 m x 0.9 m"),
    "sandbagbunker": (sandbag_wall(8.4, 3, True), "sandbag horseshoe bunker"),
    "tripodbarricade": (tripod_barricade(5, 1.7), "five hazard-striped tripods over 8.4 m"),
    "smallbarricade": (smallbarricade, "three tripods"),
    "sawhorsebarricade": (sawhorse, "sawhorse 1.6 m"),
    "corrigatedmetalbarricade": (metal_barricade(8.4), "corrugated-sheet barricade 8.4 m x 1.7 m"),
}
# faction walls: body height, post height, post width, body width, post z span, body z span (from the originals' bounds)
for fac, mat in (("s", "wallconc"), ("l", "wallfacade"), ("d", "wallconc2")):
    SPECS[f"{fac}_lightwall"] = (wall(3.5, 4.46, 4.0, 3.0, (-10.6, -6.5), (-4.0, 17.1), mat, 4, "", fac), "light wall: post block + 21 m body, 3.5 m / 4.5 m")
    SPECS[f"{fac}_mediumwall"] = (wall(9.6, 11.2, 6.0, 4.0, (-11.5, -5.5), (-3.0, 17.1), mat, 4, "", fac), "medium wall: 9.6 m body, 11.2 m post")
    SPECS[f"{fac}_heavywall"] = (wall(17.2, 17.76, 6.0, 4.0, (-11.5, -5.5), (-3.0, 17.1), mat, 5, "", fac), "heavy wall: 17.2 m body, 17.8 m post")
SPECS["s_lightpost"] = (post_only(4.46, 4.0, (-10.6, -6.5), "wallconc", "s"), "light post block")
SPECS["l_lightpost"] = (post_only(4.46, 4.0, (-10.6, -6.5), "wallfacade", "l"), "light post block")
SPECS["d_lightpost"] = (post_only(4.46, 4.6, (-10.8, -6.2), "wallconc2", "d"), "light post block")
for fac, mat in (("s", "wallconc"), ("l", "wallfacade"), ("d", "wallconc2")):
    SPECS[f"{fac}_mediumpost"] = (post_only(11.2, 6.0, (-11.5, -5.5), mat, fac), "medium post block")
    SPECS[f"{fac}_heavypost"] = (post_only(17.76, 6.0, (-11.5, -5.5), mat, fac), "heavy post block")
SPECS["l_mediumpost"] = SPECS.pop("l_mediumpost")

H.MEMBERS.update({k: (v[0], v[1]) for k, v in SPECS.items()})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("app")
    ap.add_argument("--out", default=str(ROOT / "game/assets/v3/objects"))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    for app in (list(SPECS) if a.app == "all" else a.app.split(",")):
        H.build_member(app, out)


if __name__ == "__main__":
    main()
