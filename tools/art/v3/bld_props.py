#!/usr/bin/env python3
"""v3 map props (LANCE-39): streetlight, crates, barrels, hazmat tank, dumpster, geodesic dome, ammo crates, lockers, resource-point warehouse, traffic-
control tower, bridge rails, motorcycle, stop sign, junk pile. Sizes from the Shared Source originals (game/tools/orig_parts.gd). Vehicle props reuse the
committed v3 vehicles and mechpiece_* the mech wreck parts at load (objects_view.gd, mech_pieces.gd), so they are not built here.

    python3 -I tools/art/v3/bld_props.py <app>|all
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bld_hangars as H  # noqa: E402
import bld_industry as I  # noqa: E402
import bld_military as M  # noqa: E402
from bld_industry import Ctx, V, TAU, axis_angle, shell, ROOT  # noqa: E402
from bld_military import frustum, fpanel, scorch, rubble, ribbon, door, band  # noqa: E402
from bld_industry import blk  # noqa: E402
from bld_city import blk2  # noqa: E402


def small(state, lod, seed):
    return Ctx(state, lod, seed, breach=(0.0, 1.0, 0.0, 1.5), ledges=[], ground_h=1.0)


def ruin(c, x0, x1, z0, z1, n=5, mat="scorchblack"):
    b = c.b
    rng = c.rng
    for k in range(n):
        b.box(mat if k % 2 else "rust", (rng.uniform(x0, x1), 0.15 + 0.1 * k % 0.4, rng.uniform(z0, z1)), (rng.uniform(0.4, 1.2), 0.3, rng.uniform(0.4, 1.0)), axis_angle(V([0, 1.0, 0]), rng.random() * 3))


def streetlight(state, lod, seed):
    c = small(state, lod, seed)
    b = c.b
    if state == "destroyed":
        b.tube("machgrey", V([0, 0.15, 0]), V([5.0, 0.3, 1.5]), 0.12, 6)
        b.box("lightroof", (5.2, 0.25, 1.6), (0.9, 0.2, 0.5))
        b.box("machgrey", (0, 0.2, 0), (0.6, 0.4, 0.6))
        return c
    top = 8.3 if state == "intact" else 7.0
    b.box("machgrey", (0.0, 0.3, 0.1), (0.7, 0.6, 0.7))
    b.tube("machgrey", V([0, 0.5, 0.1]), V([0, top, 0.1]), 0.14, 8 if c.fine else 5)
    b.tube("machgrey", V([0, top, 0.1]), V([0.25, top + 0.25, 0.1]), 0.1, 5)
    b.box("lightroof", (0.05, top + 0.2, 0.1), (0.9, 0.18, 0.55), axis_angle(V([0, 0, 1.0]), 0.12 if state == "damaged" else 0.0))
    b.box("glasslight", (0.05, top + 0.08, 0.1), (0.7, 0.05, 0.4))
    return c


def crates(tarp):
    def build(state, lod, seed):
        c = small(state, lod, seed)
        b = c.b
        if state == "destroyed":
            ruin(c, -2.4, 2.4, -0.7, 0.7, 7, "scorchblack")
            b.box("boards", (-1.0, 0.2, 0.1), (1.5, 0.3, 1.1), axis_angle(V([0, 1.0, 0]), 0.4))
            return c
        for k, x in enumerate((-1.4, 1.4)):                                  # two stacks of two crates
            for lvl in range(2):
                tilt = (0.1 if (state == "damaged" and lvl == 1 and k == 1) else 0.0)
                b.box("boards", (x, 0.85 + lvl * 1.7, 0.0), (2.7, 1.7, 1.6), axis_angle(V([0, 1.0, 0]), tilt))
                if c.fine:
                    for sz in (-1, 1):
                        b.box("steel", (x, 0.85 + lvl * 1.7, sz * 0.82), (2.5, 0.12, 0.05))
                        b.box("steel", (x, 0.85 + lvl * 1.7, sz * 0.82), (0.12, 1.5, 0.05))
        if tarp:
            b.box("bandgreen", (0.0, 3.45, 0.0), (5.7, 0.1, 1.7))
            b.box("bandgreen", (0.0, 2.8, 0.88), (5.7, 1.3, 0.06))
            b.box("bandgreen", (0.0, 2.8, -0.88), (5.7, 1.3, 0.06))
        return c
    return build


def barrels(burning):
    def build(state, lod, seed):
        c = small(state, lod, seed)
        b = c.b
        spots = [(0.0, 0.0)] if burning else [(-0.2, -1.0), (-0.1, 0.0), (0.0, 1.0)]
        for (x, z) in spots:
            if state == "destroyed":
                b.revolve("scorchblack", [(0.55, 0.0), (0.5, 0.35)], 8, cx=x, cz=z, th1=TAU * 0.8, uref=1.0)
                continue
            seg = 8
            b.revolve("safetyyellow", [(0.55, 0.0), (0.55, 1.4)], seg, cx=x, cz=z, uref=1.0, th0=math.pi / 8)
            b.revolve("scorchblack", [(0.57, 0.35), (0.57, 0.8)], seg, cx=x, cz=z, uref=1.0, th0=math.pi / 8)
            for k in range(4 if c.fine else 0):
                a0 = k * math.pi / 2 + 0.2
                b.box("safetyyellow", (x + math.cos(a0) * 0.58, 0.58, z + math.sin(a0) * 0.58), (0.18, 0.4, 0.05), axis_angle(V([0, 1.0, 0]), -a0))
            b.disc("safetyyellow" if not burning else "scorchblack", (x, 1.42, z), 0.5, (0, 1, 0), seg)
            if burning:
                b.disc("bandorange", (x, 1.45, z), 0.38, (0, 1, 0), 8)
        return c
    return build


def hazmat(state, lod, seed):
    c = small(state, lod, seed)
    b = c.b
    if state == "destroyed":
        b.revolve("scorchblack", [(2.4, 0.0), (2.2, 1.4)], 6, th1=TAU * 0.75, uref=2.0)
        ruin(c, -2.5, 2.5, -2.5, 2.5, 6)
        return c
    h = 5.8
    b.revolve("machgrey", [(2.5, 0.0), (2.5, 2.4), (2.3, 4.6), (1.2, 5.6), (0.0, 5.8)], 6, uref=2.0)
    b.revolve("scorchblack", [(2.52, 0.0), (2.52, 1.3)], 6, uref=2.0)
    b.revolve("safetyyellow", [(2.53, 1.3), (2.53, 1.7)], 6, uref=2.0)
    for k in range(6 if c.fine else 0):
        a = k * TAU / 6
        b.box("machgrey", (math.cos(a) * 2.3, 3.4, math.sin(a) * 2.3), (0.3, 3.0, 0.3), axis_angle(V([0, 1.0, 0]), -a))
    if state == "damaged":
        b.box("scorchblack", (1.2, 3.0, 2.0), (1.6, 1.6, 0.3), axis_angle(V([0, 1.0, 0]), 0.6))
    return c


def dumpster(state, lod, seed):
    c = small(state, lod, seed)
    b = c.b
    if state == "destroyed":
        b.box("scorchblack", (0.0, 0.3, 0.0), (5.6, 0.6, 3.6))
        ruin(c, -3.0, 3.0, -2.0, 2.0, 5)
        return c
    b.box("bluetrim", (0.0, 1.4, 0.0), (6.0, 2.8, 4.0))
    b.box("scorchblack", (0.0, 2.85, 0.0), (5.4, 0.12, 3.4))
    b.box("bluetrim", (-1.6, 3.8 if state == "intact" else 3.2, -0.4), (2.6, 0.12, 3.8), axis_angle(V([0, 0, 1.0]), 0.0 if state == "intact" else 0.35))
    for k in range(4 if c.fine else 0):
        b.box("machgrey", (-2.6 + k * 1.7, 1.4, 2.03), (0.1, 2.6, 0.06))
    return c


def icosphere(freq):
    """Vertices and faces of an icosahedron subdivided `freq` times along its edges (frequency 2 = 80 faces), projected to the unit sphere."""
    t = (1 + 5 ** 0.5) / 2
    vs = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t), (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    fs = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6),
          (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    V_ = [np.array(v, float) / np.linalg.norm(v) for v in vs]
    out = []
    for (a, b, c) in fs:
        A, B, C = V_[a], V_[b], V_[c]
        def pt(i, j):
            q = A + (B - A) * i / freq + (C - A) * j / freq
            return q / np.linalg.norm(q)
        for i in range(freq):
            for j in range(freq - i):
                out.append((pt(i, j), pt(i + 1, j), pt(i, j + 1)))
                if i + j < freq - 1:
                    out.append((pt(i + 1, j), pt(i + 1, j + 1), pt(i, j + 1)))
    return out


def geodesicdome(state, lod, seed):
    """A faceted geodesic dome (icosahedron frequency 2, flat shaded): tan-grey facets, darker strut tubes along every edge, a door box and a relay mast tower."""
    c = small(state, lod, seed)
    b = c.b
    cx, cz = 4.35, 2.0
    if state == "destroyed":
        b.revolve("scorchblack", [(7.0, 0.0), (6.0, 1.4)], 10, cx=cx, cz=cz, th1=TAU * 0.7, uref=3.0)
        ruin(c, -2.0, 11.0, -6.0, 10.0, 9)
        return c
    R, top = 7.4, 10.0 if state == "intact" else 7.0
    tris = []
    for (A, B_, C) in icosphere(2 if c.fine else 1):
        cen = (A + B_ + C) / 3
        if cen[1] < 0.02:
            continue
        if state == "damaged" and cen[0] > 0.45 and cen[2] > 0.2:      # a few facets blown out on the east side
            continue
        tris.append((A, B_, C))
    def P(v):
        return V([cx + v[0] * R, max(v[1], 0.0) * top + 0.4, cz + v[2] * R])
    done = set()
    for (A, B_, C) in tris:
        pa, pb, pc = P(A), P(B_), P(C)
        n = np.cross(pb - pa, pc - pa)
        n = n / (np.linalg.norm(n) or 1.0)
        if np.dot(n, (pa + pb + pc) / 3 - V([cx, top * 0.4, cz])) < 0:
            n = -n
            pb, pc = pc, pb
        b.add("lightroof", np.array([pa, pb, pc]), np.array([n] * 3), np.array([(p_[0], p_[2]) for p_ in (pa, pb, pc)]), [(0, 1, 2)])
        for u, w in ((pa, pb), (pb, pc), (pc, pa)):
            key = tuple(sorted((tuple(np.round(u, 2)), tuple(np.round(w, 2)))))
            if key not in done:
                done.add(key)
                b.tube("tealwall", u, w, 0.14, 4)
    b.revolve("machgrey", [(R + 0.1, 0.0), (R + 0.1, 0.5)], 10, cx=cx, cz=cz, uref=3.0)
    b.box("machgrey", (cx + 2.5, 1.3, cz + R * 0.95), (2.0, 2.4, 1.2))                     # the little door block
    b.box("lightroof", (-1.6, 3.0, -4.0), (1.6, 6.0, 1.6))                                   # the relay mast tower beside it
    b.box("steinerwhite", (-1.6, 4.2, -4.0), (1.7, 0.3, 1.7))
    b.tube("machgrey", V([-1.6, 6.0, -4.0]), V([-1.6, 8.8 if state == "intact" else 7.0, -4.0]), 0.1, 4)
    return c


def munitionscrates(state, lod, seed):
    c = small(state, lod, seed)
    b = c.b
    if state == "destroyed":
        ruin(c, -4.0, 4.0, -0.8, 0.8, 6)
        return c
    for k, x in enumerate((-2.9, 0.0, 2.9)):
        b.box("boards", (x, 0.7, 0.0), (2.8, 1.4, 1.5))
        b.box("safetyyellow", (x, 0.7, 0.77), (2.6, 0.25, 0.04))
        b.box("redframe", (x - 0.5, 0.7, 0.8), (0.4, 0.3, 0.04))
        if k != 1 or state == "damaged":
            continue
        b.box("boards", (x, 2.0, 0.0), (2.8, 1.2, 1.5))
    return c


def lockers(state, lod, seed):
    c = small(state, lod, seed)
    b = c.b
    if state == "destroyed":
        ruin(c, -1.8, 1.8, -0.4, 0.4, 4)
        return c
    for k in range(4):
        x = -1.45 + k * 0.97
        b.box("machgrey", (x, 1.2, 0.0), (0.92, 2.4, 0.8))
        b.box("grate", (x, 1.7, 0.41), (0.5, 0.6, 0.03))
        b.box("scorchblack", (x + 0.3, 1.1, 0.41), (0.06, 0.3, 0.04))
    if state == "damaged":
        b.box("scorchblack", (0.4, 1.4, 0.43), (0.8, 1.2, 0.04))
    return c


def rpbuilding(state, lod, seed):
    """Resource-point warehouse: a long ribbed-roof body (ribs along z) with angled bevelled end pieces at the +-x ends, brown-tan roof, pale blue-grey end pieces,
    a door with a canopy on the +z face. The footprint is the original's 24.6 x 21.2 m, long axis x."""
    c = shell(state, lod, seed, (0.0, 3.0, 0.0, 3.0), 1.5)
    b = c.b
    bx = (-10.8, 10.8, -10.6, 10.6)
    R90 = axis_angle(V([0, 1.0, 0]), math.pi / 2)
    b.M = (R90, np.zeros(3))                                                         # the in-game original's ribs run along the other axis: turn the model a quarter
    blk(c, *bx[:2], *bx[2:], 5.4, ("steinerwhite", "flat"), holes={}, main=True, roof=None)
    if state != "destroyed":
        for k in range(3):                                                           # ribbed roof strips along z, each raised, with dark seams
            xc = -7.2 + k * 7.2
            b.box("tanroof", (xc, 5.9, 0.0), (6.6, 0.7, 21.6))
            if c.fine:
                for m in range(8):
                    b.box("scorchblack", (xc - 3.0 + m * 0.85, 6.28, 0.0), (0.12, 0.08, 21.4))
        for sx in (-1, 1):                                                           # the angled bevelled end pieces: slabs sloping down and out from the body
            ang = math.atan2(3.6, 1.6)
            b.box("lightroof", (sx * 11.0, 3.6, 0.0), (4.1, 0.5, 21.0), axis_angle(V([0, 0, 1.0]), -sx * (math.pi / 2 - ang)))
            b.box("tanroof", (sx * 11.0, 3.45, 0.0), (3.6, 0.3, 17.0), axis_angle(V([0, 0, 1.0]), -sx * (math.pi / 2 - ang)))
        door(c, "+z", bx, 9.5, 3.4, 3.4)
        b.box("tanroof", (0.0, 3.9, 11.4), (5.2, 0.25, 1.6))
        ribbon(c, "+z", bx, 3.6, 0.9, 0.0, 1.0, None, 4, 0.6, mat="wglass")
        band(c, "+z", bx, 0.3, 0.4, "safetyyellow")
    else:
        rubble(c, bx, 5.4, 9)
    if state == "damaged":
        scorch(c, "+z", bx, 5.0, 2.8, 2.0)
    return c


def trafcon(state, lod, seed):
    c = shell(state, lod, seed, (0.0, 12.0, 0.0, 3.0), 2.0)
    b = c.b
    blk2(c, -12.5, 8.0, -12.0, 6.0, 10.0, ("steinerwhite", "flat"), roof="flat", ac=0, vents=0, hatch=0, lights=0, seed=seed, mat="lightroof", trim="lightroof", main=True)
    blk2(c, -8.5, 5.0, -9.0, 3.0, 8.0, ("steinerwhite", "flat"), y0=10.0, roof="flat", ac=0, vents=0, hatch=0, lights=0, seed=seed + 1, mat="lightroof", trim="lightroof")
    blk2(c, -5.5, 2.0, -6.5, 0.5, 8.0, ("steinerwhite", "flat"), y0=18.0, roof="flat", ac=0, vents=0, hatch=0, lights=0, seed=seed + 2, mat="lightroof", trim="lightroof")
    if state != "destroyed":
        for fl, bx, y0 in ((0, (-12.5, 8.0, -12.0, 6.0), 0.0), (1, (-8.5, 5.0, -9.0, 3.0), 10.0), (2, (-5.5, 2.0, -6.5, 0.5), 18.0)):
            for key in ("+z", "-z", "+x", "-x"):
                ribbon(c, key, bx, 4.0 if fl == 0 else 3.0, 1.6, y0, 1.0, None, 3, 0.5, mat="glassblue")
        frustum(c, "scorchblack", -1.5, -3.0, 2.8, 2.8, 26.0, 2.0, 2.0, 27.4)
        b.box("lightroof", (-1.5, 28.0, -3.0), (3.2, 0.8, 3.2))
        b.revolve("machgrey", [(0.9, 28.4), (0.9, 29.2), (0.0, 29.6)], 10, cx=-1.5, cz=-3.0, uref=1.0)
        b.box("machgrey", (-1.5, 30.0, -3.0), (0.5, 0.5, 0.5))
    if state == "damaged":
        scorch(c, "+z", (-12.5, 8.0, -12.0, 6.0), 7.0, 5.0, 2.0)
    return c


def bridge(state, lod, seed):
    c = small(state, lod, seed)
    b = c.b
    for x in (-12.4, 12.4):
        if state == "destroyed":
            b.box("concrete", (x * 0.98, 0.5, 0.0), (0.8, 1.0, 18.0), axis_angle(V([0, 1.0, 0]), 0.1))
            continue
        b.box("concrete", (x, 0.75, 0.0), (0.8, 1.5, 21.0))
        b.box("lightroof", (x, 1.6, 0.0), (1.0, 0.2, 21.0))
        for k in range(5):
            b.box("machgrey", (x, 0.2, -9.6 + k * 4.8), (1.0, 0.4, 0.5))
    return c


def motorcycle(state, lod, seed):
    c = small(state, lod, seed)
    b = c.b
    if state == "destroyed":
        ruin(c, -0.5, 0.5, -1.0, 1.0, 3)
        return c
    for z in (-1.0, 1.0):
        b.revolve("scorchblack", [(0.55, -0.1), (0.55, 0.1)], 14 if c.fine else 8, cx=0.05, cz=z, uref=1.0) if False else b.tube("scorchblack", V([-0.15, 0.55, z]), V([0.25, 0.55, z]), 0.55, 12, caps=True)
    b.box("bandgreen", (0.05, 0.9, -0.1), (0.7, 0.5, 1.6))
    b.box("bandorange", (0.05, 1.15, 0.6), (0.7, 0.2, 0.7))
    b.tube("machgrey", V([0.05, 1.2, 0.9]), V([0.05, 1.2, 1.25]), 0.08, 4)
    if state == "damaged":
        b.box("scorchblack", (0.05, 1.0, -0.6), (0.5, 0.2, 0.6))
    return c


def stopsign(state, lod, seed):
    c = small(state, lod, seed)
    b = c.b
    if state == "destroyed":
        b.tube("machgrey", V([0, 0.1, 0]), V([2.4, 0.2, 0.4]), 0.06, 4)
        b.box("redframe", (2.6, 0.1, 0.4), (0.8, 0.05, 0.8))
        return c
    b.tube("machgrey", V([0, 0, 0]), V([0, 2.2, 0]), 0.06, 5)
    b.box("redframe", (0.0, 2.45, 0.05), (0.8, 0.8, 0.05), axis_angle(V([0, 0, 1.0]), math.pi / 4 if False else 0.0))
    b.box("redframe", (0.0, 2.45, 0.05), (0.8, 0.8, 0.05), axis_angle(V([0, 0, 1.0]), math.pi / 4))
    b.box("lightroof", (0.0, 2.45, 0.09), (0.45, 0.1, 0.02))
    return c


def junkpile(state, lod, seed):
    c = small(state, lod, seed)
    b = c.b
    rng = c.rng
    for k in range(9 if c.fine else 5):
        b.box(("rust", "machgrey", "scorchblack", "boards")[k % 4], (rng.uniform(-1.2, 2.6), 0.4 + rng.random() * (1.2 if state != "destroyed" else 0.3), rng.uniform(-2.6, 3.0)),
              (rng.uniform(0.6, 1.5), rng.uniform(0.5, 1.4), rng.uniform(0.6, 1.4)), axis_angle(V([0, 1.0, 0]), rng.random() * 3) @ axis_angle(V([1.0, 0, 0]), rng.uniform(-0.5, 0.5)))
    b.box("machgrey", (1.4, 1.2, 0.5), (0.3, 3.0, 2.0), axis_angle(V([0, 0, 1.0]), 0.5))
    return c


PROPS = {
    "streetlight": (streetlight, "pole to 8.3 m with a lamp head"),
    "crateswithtarp": (crates(True), "two stacks of two crates under a green tarp"),
    "woodencrates": (crates(False), "two stacks of two wooden crates"),
    "barrels": (barrels(False), "three hazard-banded drums"),
    "burningtrashbarrel": (barrels(True), "one drum with an orange fire disc"),
    "hazmat": (hazmat, "faceted grey storage tank with a hazard band"),
    "dumpster": (dumpster, "blue dumpster with a hinged lid"),
    "geodesicdome": (geodesicdome, "glazed geodesic dome with ribs and a relay mast"),
    "munitionscrates": (munitionscrates, "ammo crates with hazard strips"),
    "lockers": (lockers, "a row of four grey lockers"),
    "trafcon": (trafcon, "stepped traffic-control tower with glazed bands and a dish"),
    "bridge": (bridge, "two concrete bridge rails"),
    "motorcycle": (motorcycle, "green bike with an orange seat"),
    "stopsign": (stopsign, "post with an octagonal red sign"),
    "junkpile": (junkpile, "pile of scrap"),
}
H.MEMBERS.update(PROPS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("app")
    ap.add_argument("--out", default=str(ROOT / "game/assets/v3/objects"))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    for app in (list(PROPS) if a.app == "all" else a.app.split(",")):
        H.build_member(app, out)


if __name__ == "__main__":
    main()
