#!/usr/bin/env python3
"""v3 HPG (hyperpulse generator) station family (LANCE-39): hpgstation, hpgoutbldg, hpg_office, hpg_gen, hpg_end, hpg_threeway, hpg_walkway.
Built to the Shared Source originals' per-part and plan-heightmap measurements (game/tools/orig_parts.gd, orig_bounds.gd, /mnt/nvme1n1p1/mc2-rework/bld/hpg/
hmap.py + prof.py), in the frame the originals' meshes use in game (hpg_office's node offset 7.37, 1.18, -6.09 is applied, so it is built off-origin; none of the
seven has a node scale that touches a mesh). The family's look is the originals': sand-tan hulls with sloped (about 20 degrees) walls on a low plinth, pale
blue-grey roof panels in a tan frame, dark slit windows, a red/blue radio-wave emblem panel, white hatch plates with three slots, and the station's nine-sided
lattice dish on three leaning spires. Windows are separate rectangles, never holes. Reuses bld_industry/bld_military/bld_city helpers. Style guide:
docs/art/STYLE-GUIDE.md section 10.

    python3 -I tools/art/v3/bld_hpg.py <app>|all
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bld_hangars as H  # noqa: E402
from bld_city import rubble  # noqa: E402
from bld_industry import V, TAU, shell, ROOT, axis_angle  # noqa: E402
from bld_kit import cell_uv  # noqa: E402
from bld_mesh import Builder, unit  # noqa: E402

WALL = "tanwall"
PLINTH = "concrete_dark"
PANEL = "palepaint"
DARK = "framedark"
PL = 1.2            # plinth height (the originals' walls start sloping about 1.2 m up)


# ------------------------------------------------------------------------------------------------------------------ sloped faces
class Fc:
    """One planar trapezoid wall face: bl/br bottom corners, tl/tr top corners (left/right seen from outside), `out` the horizontal outward direction. Panels are
    placed by metres from the left edge (u0, w) and metres up the slope (v0, h) so a detail never leaves the face."""

    def __init__(self, c, bl, br, tl, tr, out):
        self.c = c
        self.bl, self.br, self.tl, self.tr = (np.asarray(p, float) for p in (bl, br, tl, tr))
        n = np.cross(self.br - self.bl, self.tl - self.bl)
        n = n / (np.linalg.norm(n) or 1.0)
        if np.dot(n, np.asarray(out, float)) < 0:
            n = -n
        self.n = n
        self.L = float((np.linalg.norm(self.br - self.bl) + np.linalg.norm(self.tr - self.tl)) / 2)
        self.S = float((np.linalg.norm(self.tl - self.bl) + np.linalg.norm(self.tr - self.br)) / 2)

    def pt(self, a, t, off=0.0):
        lo = self.bl + (self.tl - self.bl) * t
        hi = self.br + (self.tr - self.br) * t
        return lo + (hi - lo) * a + self.n * off

    def dirs(self):
        u = unit(self.br - self.bl + self.tr - self.tl)
        v = unit(self.tl - self.bl + self.tr - self.br)
        return u, v

    def quad(self, mat, u0, w, v0, h, off=0.05, col=(0, 0, 0)):
        a0, a1, t0, t1 = u0 / self.L, (u0 + w) / self.L, v0 / self.S, (v0 + h) / self.S
        P = np.array([self.pt(a0, t0, off), self.pt(a1, t0, off), self.pt(a1, t1, off), self.pt(a0, t1, off)])
        U = np.array([(u0, v0), (u0 + w, v0), (u0 + w, v0 + h), (u0, v0 + h)])
        self.c.b.add(mat, P, np.tile(self.n, (4, 1)), U, [(0, 1, 2), (0, 2, 3)], 0, col)

    def draw(self, mat, offs=0.0):
        P = np.array([self.pt(0, 0, offs), self.pt(1, 0, offs), self.pt(1, 1, offs), self.pt(0, 1, offs)])
        U = np.array([(0, 0), (self.L, 0), (self.L, self.S), (0, self.S)])
        self.c.b.add(mat, P, np.tile(self.n, (4, 1)), U, [(0, 1, 2), (0, 2, 3)])

    def ctr(self, u, v, off=0.0):
        return self.pt(u / self.L, v / self.S, off)

    # ---- details
    def ribs(self, n, w=0.5, v1=None, mat=WALL):
        """n vertical pilaster strips between the plinth line and v1, each with a dark gap beside it."""
        if self.c.state == "destroyed":
            return
        v1 = self.S - 0.3 if v1 is None else v1
        for k in range(n):
            u = self.L * (k + 1) / (n + 1) - w / 2
            if self.c.fine:
                self.quad(DARK, u - 0.2, 0.2, 0.2, v1 - 0.2, 0.07)
                self.quad(DARK, u + w, 0.2, 0.2, v1 - 0.2, 0.07)
            self.quad(mat, u, w, 0.2, v1 - 0.2, 0.1)

    def slits(self, n, v0, h, u0=0.8, u1=None, gap=0.5, mat="glassblue", band=True):
        """A row of n dark-blue slit windows, separate rectangles with a pale sill bar under each (fine LOD)."""
        if self.c.state == "destroyed":
            return
        u1 = self.L - 0.8 if u1 is None else u1
        w = (u1 - u0 - gap * (n - 1)) / n
        for k in range(n):
            self.quad(mat, u0 + k * (w + gap), w, v0, h, 0.07)
            if self.c.fine and band:
                self.quad("creamwall", u0 + k * (w + gap) - 0.1, w + 0.2, v0 - 0.2, 0.16, 0.08)

    def hatch(self, u, v, w=1.5, h=2.0):
        """A white plate with three dark slots (the originals' hatch / vent plates)."""
        if self.c.state == "destroyed":
            return
        self.quad("lightroof", u, w, v, h, 0.07)
        if self.c.fine:
            for k in range(3):
                self.quad(DARK, u + 0.22 * w, 0.56 * w, v + h * (0.22 + 0.23 * k), 0.07 * h + 0.02, 0.1)

    def door(self, u, w=1.8, h=2.6, v=0.15):
        if self.c.state == "destroyed":
            return
        self.quad("lightroof", u - 0.15, w + 0.3, v, h + 0.15, 0.07)
        self.quad(DARK, u, w, v, h, 0.1)

    def emblem(self, u, v, w, h):
        """The HPG radio-wave emblem: a dark blue panel, nested blue and red rings with a white core, and a red beam running down to the foot."""
        c = self.c
        if c.state == "destroyed":
            return
        self.quad("framedark", u - 0.2, w + 0.4, v - 0.2, h + 0.4, 0.07)
        self.quad("bluetrim", u, w, v, h, 0.09)
        b = c.b
        uu, vv = self.dirs()
        cx = self.ctr(u + w / 2, v + h * 0.7, 0.12)
        r = w * 0.45
        b.disc("redframe", cx, r, tuple(self.n), 18 if c.fine else 10, uvs=1.0)
        b.disc("lightroof", cx + self.n * 0.02, r * 0.78, tuple(self.n), 18 if c.fine else 10)
        b.disc("bluetrim", cx + self.n * 0.04, r * 0.58, tuple(self.n), 18 if c.fine else 10)
        b.disc("redframe", cx + self.n * 0.06, r * 0.36, tuple(self.n), 14 if c.fine else 8)
        b.disc("lightroof", cx + self.n * 0.08, r * 0.16, tuple(self.n), 10 if c.fine else 6)
        # the beam: a red wedge from the core to the panel foot
        p0 = self.ctr(u + w / 2, v + h * 0.7 - r * 0.4, 0.13)
        p1 = self.ctr(u + w / 2 - w * 0.12, v + 0.4, 0.13)
        p2 = self.ctr(u + w / 2 + w * 0.12, v + 0.4, 0.13)
        p3 = self.ctr(u + w / 2 + w * 0.04, v + h * 0.7 - r * 0.4, 0.13)
        p4 = self.ctr(u + w / 2 - w * 0.04, v + h * 0.7 - r * 0.4, 0.13)
        b.add("redframe", np.array([p4, p3, p2, p1]), np.tile(self.n, (4, 1)), np.array([(0, 0), (1, 0), (1, 3), (0, 3)]), [(0, 1, 2), (0, 2, 3)])

    def scorch(self, a, t, r, streak=True):
        """A scorched hole: a jagged black polygon, bare bent beams across it and soot running up the face (damaged state)."""
        c = self.c
        if c.state != "damaged":
            return
        b = c.b
        uu, vv = self.dirs()
        ctr = self.pt(a, t, 0.08)
        pts = []
        for k in range(10):
            ang = TAU * k / 10
            rr = r * (0.7 + 0.5 * c.rng.random())
            pts.append(ctr + uu * (math.cos(ang) * rr) + vv * (math.sin(ang) * rr * 1.1))
        P = [ctr] + pts
        b.add("scorchblack", np.array(P), np.tile(self.n, (len(P), 1)), np.array([(p[0], p[1] + p[2]) for p in P]), [(0, 1 + k, 1 + (k + 1) % 10) for k in range(10)])
        for k in range(3):
            q0 = ctr + uu * c.rng.uniform(-r * 0.8, r * 0.8) - vv * (r * 0.8) + self.n * 0.05
            q1 = ctr + uu * c.rng.uniform(-r * 0.8, r * 0.8) + vv * (r * 0.8) + self.n * 0.35 * k
            b.tube("steel", q0, q1, 0.07, 4)
        if streak and c.fine:
            for k in range(2):
                p = self.pt(a, t, 0.1) + uu * ((k - 0.5) * r * 0.9) + vv * (r * 2.0)
                b.quad("decal", p, uu, vv, r * 1.3, r * 3.0, cell_uv("streak_a" if k == 0 else "streak_b"), normal=tuple(self.n))


def sbox(c, base, y0, top, y1, mat=WALL, roof=True, rim=0.7, plinth=None, faces=True):
    """A sloped-wall block: a vertical plinth (y0 .. y0+plinth) on `base`, then four sloped faces up to `top` at y1 (rects are (x0, x1, z0, z1)), a tan roof with a
    pale panel inset by `rim`. Returns the four Fc (keys -z +z -x +x) measured from the plinth top, and the roof y."""
    b = c.b
    x0, x1, z0, z1 = base
    tx0, tx1, tz0, tz1 = top
    pl = PL if plinth is None else plinth
    ya = y0 + pl
    F = {}
    if pl > 0:
        b.box(PLINTH, ((x0 + x1) / 2, y0 + pl / 2, (z0 + z1) / 2), (x1 - x0, pl, z1 - z0))
    F["-z"] = Fc(c, (x0, ya, z0), (x1, ya, z0), (tx0, y1, tz0), (tx1, y1, tz0), (0, 0, -1))
    F["+z"] = Fc(c, (x1, ya, z1), (x0, ya, z1), (tx1, y1, tz1), (tx0, y1, tz1), (0, 0, 1))
    F["-x"] = Fc(c, (x0, ya, z1), (x0, ya, z0), (tx0, y1, tz1), (tx0, y1, tz0), (-1, 0, 0))
    F["+x"] = Fc(c, (x1, ya, z0), (x1, ya, z1), (tx1, y1, tz0), (tx1, y1, tz1), (1, 0, 0))
    if faces:
        for f in F.values():
            f.draw(mat)
    if roof:
        P = np.array([(tx0, y1, tz0), (tx1, y1, tz0), (tx1, y1, tz1), (tx0, y1, tz1)])
        b.add(mat, P, np.tile((0, 1, 0), (4, 1)), P[:, [0, 2]], [(0, 1, 2), (0, 2, 3)])
        if rim > 0 and (tx1 - tx0) > 2 * rim + 0.5 and (tz1 - tz0) > 2 * rim + 0.5:
            b.box(PANEL, ((tx0 + tx1) / 2, y1 + 0.03, (tz0 + tz1) / 2), (tx1 - tx0 - 2 * rim, 0.06, tz1 - tz0 - 2 * rim))
            if c.fine:
                roof_lines(c, (tx0 + rim, tx1 - rim, tz0 + rim, tz1 - rim), y1 + 0.06)
    return F, y1


def roof_lines(c, box, y, nx=None, nz=None):
    """Slab joints on a roof panel: thin dark lines in a loose grid, as the originals' roof art."""
    x0, x1, z0, z1 = box
    W, D = x1 - x0, z1 - z0
    nx = max(1, int(W / 5.5)) if nx is None else nx
    nz = max(1, int(D / 5.5)) if nz is None else nz
    for k in range(1, nx):
        c.b.box("machgrey", (x0 + W * k / nx, y + 0.02, (z0 + z1) / 2), (0.1, 0.04, D))
    for k in range(1, nz):
        c.b.box("machgrey", ((x0 + x1) / 2, y + 0.02, z0 + D * k / nz), (W, 0.04, 0.1))


def roof_plate(c, cx, cz, y, w=2.6, d=3.4, rot=0.0):
    """A white roof hatch plate with three dark slots."""
    if c.state == "destroyed":
        return
    R = axis_angle(V([0, 1.0, 0]), rot)
    c.b.box("lightroof", (cx, y + 0.07, cz), (w, 0.14, d), R)
    if c.fine:
        for k in range(3):
            off = R @ V([0, 0, (k - 1) * d * 0.24])
            c.b.box(DARK, (cx + off[0], y + 0.15, cz + off[2]), (w * 0.6, 0.05, d * 0.09), R)


def ruin(c, base, top, y1, n=9, h=2.6):
    """The destroyed state of a sloped block: its plinth and the walls' stubs (cut by the original slope at 1.6 m), charred slab chunks over the footprint."""
    b = c.b
    x0, x1, z0, z1 = base
    tx0, tx1, tz0, tz1 = top
    k = min(1.0, 1.6 / max(y1, 1.0))
    ix0, ix1, iz0, iz1 = x0 + (tx0 - x0) * k, x1 + (tx1 - x1) * k, z0 + (tz0 - z0) * k, z1 + (tz1 - z1) * k
    b.box(PLINTH, ((x0 + x1) / 2, 0.45, (z0 + z1) / 2), (x1 - x0, 0.9, z1 - z0))
    for (cx, cz, sx, sz) in (((x0 + x1) / 2, z0 + 0.4, x1 - x0 - 0.4, 0.8), ((x0 + x1) / 2, z1 - 0.4, x1 - x0 - 0.4, 0.8),
                              (x0 + 0.4, (z0 + z1) / 2, 0.8, z1 - z0 - 1.6), (x1 - 0.4, (z0 + z1) / 2, 0.8, z1 - z0 - 1.6)):
        if sx > 0.3 and sz > 0.3:
            b.box("concrete_dark", (cx, 1.2, cz), (sx, 0.9, sz))
    gx, gz = (x1 - x0) * 0.045, (z1 - z0) * 0.045
    rubble(c, (x0 + gx, x1 - gx, z0 + gz, z1 - gz), h, n)      # the soot decal is 1.2 x the box: shrink it so the wreck stays inside the original's footprint
    for k2 in range(3):                                           # a toppled slab of tan wall
        sx, sz = (x1 - x0) * c.rng.uniform(0.2, 0.35), (z1 - z0) * c.rng.uniform(0.2, 0.3)
        b.box(WALL, (c.rng.uniform(x0 + 1.5, x1 - 1.5), 1.1 + 0.5 * k2, c.rng.uniform(z0 + 1.5, z1 - 1.5)), (sx, 0.35, sz),
              axis_angle(V([0, 1.0, 0]), c.rng.uniform(0, 3.0)) @ axis_angle(V([1.0, 0, 0]), c.rng.uniform(-0.35, 0.35)))


def taper(c, mat, p0, p1, w0, d0, w1, d1, side):
    """A four-sided tapered pillar from p0 (w0 x d0) to p1 (w1 x d1): `side` is the horizontal direction the width runs along."""
    p0, p1 = V(p0), V(p1)
    ax = unit(p1 - p0)
    sd = unit(np.asarray(side, float) - ax * np.dot(side, ax))
    dp = np.cross(ax, sd)
    A = [p0 + sd * w0 / 2 + dp * d0 / 2, p0 - sd * w0 / 2 + dp * d0 / 2, p0 - sd * w0 / 2 - dp * d0 / 2, p0 + sd * w0 / 2 - dp * d0 / 2]
    B = [p1 + sd * w1 / 2 + dp * d1 / 2, p1 - sd * w1 / 2 + dp * d1 / 2, p1 - sd * w1 / 2 - dp * d1 / 2, p1 + sd * w1 / 2 - dp * d1 / 2]
    ctr = (p0 + p1) / 2
    for i in range(4):
        j = (i + 1) % 4
        P = np.array([A[i], A[j], B[j], B[i]])
        n = unit(np.cross(P[1] - P[0], P[3] - P[0]))
        if np.dot(n, P.mean(0) - ctr) < 0:
            n = -n
        c.b.add(mat, P, np.tile(n, (4, 1)), np.array([(0, 0), (1, 0), (1, 8), (0, 8)]), [(0, 1, 2), (0, 2, 3)])
    c.b.add(mat, np.array(A), np.tile(-ax, (4, 1)), np.array([(0, 0), (1, 0), (1, 1), (0, 1)]), [(0, 1, 2), (0, 2, 3)])


# ------------------------------------------------------------------------------------------------------------------ walkway family
def arm(c, axis, near, far, half0, half1, y1=6.7, ends=True):
    """A walkway arm: base half-width half0 and roof half-width half1 about the axis line through the origin, running from `near` to `far` along x (axis "x") or
    z; open vertical ends (they butt against the next piece). Returns its faces by key."""
    if axis == "x":
        base, top = (near, far, -half0, half0), (near, far, -half1, half1)
    else:
        base, top = (-half0, half0, near, far), (-half1, half1, near, far)
    F, y = sbox(c, base, 0.0, top, y1, rim=0.55)
    return F, base, top


def arm_details(c, F, key_long, n_ribs, hatch_u=None, slit=True):
    """Ribs, a dark slit row and optional hatch on one long face of an arm."""
    f = F[key_long]
    if c.state == "destroyed":
        return
    f.ribs(n_ribs, 0.45, v1=f.S - 0.35)
    if slit and f.L > 6:
        f.slits(max(2, n_ribs + 1), f.S * 0.66, 0.5, u0=0.7, u1=f.L - 0.7, gap=0.6, band=False)


def walkway(state, lod, seed):
    c = shell(state, lod, seed, (-4.0, 3.0, -5.0, 3.0), 2.0)
    base = (-12.8, 12.8, -6.4, 6.4)
    top = (-12.8, 12.8, -4.3, 4.3)
    if state == "destroyed":
        ruin(c, base, top, 6.7, 8, 2.2)
        return c
    F, y = sbox(c, base, 0.0, top, 6.7, rim=0.55)
    for k in ("-z", "+z"):
        arm_details(c, F, k, 3)
    F["-x"].quad(DARK, 1.0, 10.4, 0.5, 5.0, 0.04) if False else None
    roof_plate(c, -9.2, -0.2, 6.7, 2.4, 3.2, 0.0)
    roof_plate(c, 9.2, 0.9, 6.7, 2.4, 3.2, 0.0)
    if state == "damaged":
        F["-z"].scorch(0.58, 0.55, 1.6)
        F["+z"].scorch(0.2, 0.42, 1.1)
        from bld_military import roof_scorch
        roof_scorch(c, 3.0, 6.76, 0.8, 1.6)
    return c


# ------------------------------------------------------------------------------------------------------------------ head blocks (end, threeway)
def head(c, y1=7.4):
    base = (-8.1, 8.1, -8.0, 8.0)
    top = (-5.5, 5.6, -5.6, 5.5)
    F, y = sbox(c, base, 0.0, top, y1, rim=0.9)
    return F, base, top


def hpg_end(state, lod, seed):
    c = shell(state, lod, seed, (2.0, 3.0, -7.0, 3.0), 2.0)
    hbase, htop = (-8.1, 8.1, -8.0, 8.0), (-5.5, 5.6, -5.6, 5.5)
    abase, atop = (-12.8, -7.0, -6.4, 6.4), (-12.8, -7.0, -4.3, 4.3)
    if state == "destroyed":
        ruin(c, hbase, htop, 7.4, 8, 2.6)
        ruin(c, abase, atop, 6.7, 3, 1.6)
        return c
    F, y = sbox(c, abase, 0.0, atop, 6.7, rim=0.55)
    for k in ("-z", "+z"):
        arm_details(c, F, k, 1)
    roof_plate(c, -10.0, 0.0, 6.7, 2.2, 3.0, 0.0)
    H_, _ = sbox(c, hbase, 0.0, htop, 7.4, rim=0.9)
    for k in ("-z", "+z"):
        H_[k].ribs(2, 0.5, v1=H_[k].S - 0.4)
        H_[k].slits(3, H_[k].S * 0.7, 0.5, u0=1.2, u1=H_[k].L - 1.2, gap=0.8, band=False)
    H_["+x"].ribs(2, 0.5, v1=H_["+x"].S - 0.4)
    H_["+x"].slits(3, H_["+x"].S * 0.7, 0.5, u0=1.2, u1=H_["+x"].L - 1.2, gap=0.8, band=False)
    if state == "damaged":
        H_["+x"].scorch(0.5, 0.45, 1.7)
        H_["-z"].scorch(0.3, 0.35, 1.2)
        from bld_military import roof_scorch
        roof_scorch(c, 1.0, 7.46, 1.0, 1.8)
    return c


def hpg_threeway(state, lod, seed):
    c = shell(state, lod, seed, (3.0, 3.0, -9.0, 3.0), 2.0)
    hbase, htop = (-8.1, 8.1, -8.0, 8.0), (-5.5, 5.6, -5.6, 5.5)
    abase, atop = (-12.8, -7.0, -6.4, 6.4), (-12.8, -7.0, -4.3, 4.3)
    nbase, ntop = (-6.4, 6.4, -12.8, -7.0), (-4.3, 4.3, -12.8, -7.0)
    sbase, stop = (-6.4, 6.4, 7.0, 12.8), (-4.3, 4.3, 7.0, 12.8)
    if state == "destroyed":
        ruin(c, hbase, htop, 7.4, 8, 2.6)
        for bb, tt in ((abase, atop), (nbase, ntop), (sbase, stop)):
            ruin(c, bb, tt, 6.7, 3, 1.6)
        return c
    Fa, _ = sbox(c, abase, 0.0, atop, 6.7, rim=0.55)
    Fn, _ = sbox(c, nbase, 0.0, ntop, 6.7, rim=0.55)
    Fs, _ = sbox(c, sbase, 0.0, stop, 6.7, rim=0.55)
    for F_, ks in ((Fa, ("-z", "+z")), (Fn, ("-x", "+x")), (Fs, ("-x", "+x"))):
        for k in ks:
            arm_details(c, F_, k, 1)
    roof_plate(c, -10.0, 0.0, 6.7, 2.2, 3.0, 0.0)
    roof_plate(c, 0.0, -10.2, 6.7, 3.0, 2.2, 0.0)
    roof_plate(c, 0.0, 10.2, 6.7, 3.0, 2.2, 0.0)
    H_, _ = sbox(c, hbase, 0.0, htop, 7.4, rim=0.9)
    H_["+x"].ribs(2, 0.5, v1=H_["+x"].S - 0.4)
    H_["+x"].slits(3, H_["+x"].S * 0.7, 0.5, u0=1.2, u1=H_["+x"].L - 1.2, gap=0.8, band=False)
    if state == "damaged":
        H_["+x"].scorch(0.45, 0.45, 1.8)
        Fn["-x"].scorch(0.5, 0.5, 1.2)
        from bld_military import roof_scorch
        roof_scorch(c, 0.0, 7.46, 0.0, 1.8)
    return c


# ------------------------------------------------------------------------------------------------------------------ outbldg
def hpgoutbldg(state, lod, seed):
    """U-plan sloped block: arms x -12.1..-3.0 and 3.0..12.1 (z -10.8..1.5), back bar z 0.5..9.5, roof y 5.9, a low court block between the arms (y 3)."""
    c = shell(state, lod, seed, (10.0, 3.0, -3.0, 3.0), 2.0)
    arms = [((-12.1, -2.6, -10.8, 2.0), (-10.1, -3.6, -9.0, 2.0)), ((2.6, 12.1, -10.8, 2.0), (3.6, 10.1, -9.0, 2.0))]
    bar = ((-12.1, 12.1, 0.5, 9.5), (-10.1, 10.1, 1.7, 7.9))
    court = ((-3.6, 3.6, -7.0, 1.6), (-3.3, 3.3, -6.2, 1.6))
    if state == "destroyed":
        for bb, tt in arms + [bar]:
            ruin(c, bb, tt, 5.9, 5, 2.4)
        ruin(c, court[0], court[1], 3.0, 2, 1.0)
        return c
    PLo = 0.6
    FA = []
    for bb, tt in arms:
        F, _ = sbox(c, bb, 0.0, tt, 5.9, rim=0.7, plinth=PLo)
        FA.append(F)
    Fb, _ = sbox(c, bar[0], 0.0, bar[1], 5.9, rim=0.7, plinth=PLo)
    Fc_, _ = sbox(c, court[0], 0.0, court[1], 3.0, rim=0.45, plinth=0.4)
    # outer walls: ribs and a slit row; the long (x = +-12.1) faces are the signature
    FA[0]["-x"].ribs(3, 0.45, v1=FA[0]["-x"].S - 0.3)
    FA[0]["-x"].slits(4, FA[0]["-x"].S * 0.7, 0.5, u0=0.8, u1=FA[0]["-x"].L - 0.8, gap=0.7, band=False)
    FA[1]["+x"].ribs(3, 0.45, v1=FA[1]["+x"].S - 0.3)
    FA[1]["+x"].slits(4, FA[1]["+x"].S * 0.7, 0.5, u0=0.8, u1=FA[1]["+x"].L - 0.8, gap=0.7, band=False)
    Fb["+z"].ribs(5, 0.45, v1=Fb["+z"].S - 0.3)
    Fb["+z"].slits(6, Fb["+z"].S * 0.7, 0.5, u0=0.8, u1=Fb["+z"].L - 0.8, gap=0.7, band=False)
    FA[0]["-x"].door(FA[0]["-x"].L * 0.92 - 0.9, 1.6, 2.3)
    FA[1]["+x"].emblem(2.2, 0.8, 2.0, 3.8)
    Fc_["-z"].door(Fc_["-z"].L / 2 - 1.2, 2.4, 1.9, v=0.0)
    for F_ in (FA[0], FA[1]):                       # the arm-end walls facing -z
        F_["-z"].hatch(F_["-z"].L / 2 - 0.8, 0.9, 1.6, 2.0)
    # roof conduit runs on the arms: a long white pipe with a stub and a pair of boxes, as the originals' roof art
    for sgn, (tx0, tx1) in ((-1, (-10.1, -3.6)), (1, (3.6, 10.1))):
        cx = (tx0 + tx1) / 2
        c.b.box("lightroof", (cx, 5.9 + 0.12, -3.0), (0.22, 0.2, 9.0))
        c.b.box("lightroof", (cx + sgn * 1.2, 5.9 + 0.12, -7.4), (2.6, 0.2, 0.22))
        c.b.box("lightroof", (cx + sgn * 2.3, 5.9 + 0.35, -7.4), (0.9, 0.7, 0.9))
        c.b.box("lightroof", (cx - sgn * 1.2, 5.9 + 0.35, 0.0), (0.9, 0.7, 0.9))
    roof_plate(c, 5.0, 5.6, 5.9, 1.8, 2.4, 0.0)
    if c.fine:
        for k in range(3):
            c.b.box(DARK, (-1.5 + k * 1.5, 3.04, 0.1), (0.5, 0.06, 1.0))
    if state == "damaged":
        FA[0]["-x"].scorch(0.45, 0.5, 1.8)
        Fb["+z"].scorch(0.7, 0.4, 1.4)
        from bld_military import roof_scorch
        roof_scorch(c, 7.0, 5.96, -2.0, 1.8)
    return c


# ------------------------------------------------------------------------------------------------------------------ generator
def louvre_unit(c, x0, x1, z0, z1, y_eave, y_ridge):
    """A louvred cooling unit: vertical-slat walls to y_eave, a shallow tent roof (ridge along z) of long horizontal slats."""
    b = c.b
    xm = (x0 + x1) / 2
    W, D = x1 - x0, z1 - z0
    b.box("machgrey", ((x0 + x1) / 2, (y_eave + 0.2) / 2, (z0 + z1) / 2), (W - 0.2, y_eave - 0.2, D - 0.2))
    b.box(PLINTH, ((x0 + x1) / 2, 0.2, (z0 + z1) / 2), (W, 0.4, D))
    # tent roof: two sloped quads in light metal with a dark gap, the ridge beam
    for sg in (-1, 1):
        xe = x0 if sg < 0 else x1
        P = np.array([(xe, y_eave, z0), (xe, y_eave, z1), (xm, y_ridge, z1), (xm, y_ridge, z0)])
        n = unit(np.cross(P[1] - P[0], P[3] - P[0]))
        if n[1] < 0:
            n = -n
        b.add("palepaint", P, np.tile(n, (4, 1)), np.array([(0, 0), (D, 0), (D, W / 2), (0, W / 2)]), [(0, 1, 2), (0, 2, 3)])
        if c.fine:
            sl = (y_ridge - y_eave) / (W / 2)
            for k in range(1, 8):
                f = k / 8.0
                xx = xe + (xm - xe) * f
                yy = y_eave + (y_ridge - y_eave) * f
                b.box(DARK, (xx, yy + 0.04, (z0 + z1) / 2), (0.16, 0.08, D - 0.3), axis_angle(V([0, 0, 1.0]), math.atan(sl) * (-sg)))
    b.box("lightroof", (xm, y_ridge + 0.06, (z0 + z1) / 2), (0.5, 0.14, D))
    for ze, sg in ((z0, -1), (z1, 1)):                             # the gable ends: tan triangles
        P = np.array([(x0, y_eave, ze), (x1, y_eave, ze), (xm, y_ridge, ze)])
        b.add(WALL, P, np.tile((0, 0, sg), (3, 1)), P[:, [0, 1]], [(0, 1, 2)])
    # vertical slats on the two long faces (x = x0, x1) and the end faces
    n_x = int(D / 0.9)
    for xe, sg in ((x0, -1), (x1, 1)):
        for k in range(n_x if c.fine else max(2, n_x // 3)):
            zz = z0 + 0.6 + (D - 1.2) * (k + 0.5) / n_x
            b.box("lightroof", (xe + sg * 0.04, (y_eave + 0.4) / 2, zz), (0.2, y_eave - 0.6, 0.38))
    n_z = int(W / 0.9)
    for ze, sg in ((z0, -1), (z1, 1)):
        for k in range(n_z if c.fine else max(2, n_z // 3)):
            xx = x0 + 0.6 + (W - 1.2) * (k + 0.5) / n_z
            b.box("lightroof", (xx, (y_eave + 0.4) / 2, ze + sg * 0.04), (0.38, y_eave - 0.6, 0.2))


def hpg_gen(state, lod, seed):
    """Long block A x -11.5..-2.4 (roof 5.9), block C x -0.5..9.9 z 1.2..10.8 (5.9), a low connector (3), and two louvred cooling units x -1.3..12.2."""
    c = shell(state, lod, seed, (-7.0, 3.0, 2.0, 3.0), 2.0)
    A = ((-11.5, -2.4, -10.8, 10.8), (-10.2, -3.6, -9.3, 9.3))
    C = ((-0.5, 9.9, 1.2, 10.8), (1.5, 8.4, 3.0, 9.3))
    D = ((-3.3, 1.8, 2.4, 8.7), (-3.0, 1.5, 3.0, 8.4))
    units = ((-1.3, 12.2, -10.2, -4.1), (-1.3, 12.2, -3.6, 2.3))
    if state == "destroyed":
        ruin(c, A[0], A[1], 5.9, 7, 2.4)
        ruin(c, C[0], C[1], 5.9, 4, 2.4)
        for (x0, x1, z0, z1) in units:
            ruin(c, (x0, x1, z0, z1), (x0 + 1, x1 - 1, z0 + 1, z1 - 1), 7.0, 4, 2.2)
        return c
    FA, _ = sbox(c, A[0], 0.0, A[1], 5.9, rim=0.7, plinth=0.8)
    FC, _ = sbox(c, C[0], 0.0, C[1], 5.9, rim=0.7, plinth=0.8)
    FD, _ = sbox(c, D[0], 0.0, D[1], 3.0, rim=0.5, plinth=0.4)
    for k in ("-x", "-z", "+z"):
        FA[k].ribs(3 if k == "-x" else 1, 0.45, v1=FA[k].S - 0.3)
    FA["-x"].slits(4, FA["-x"].S * 0.7, 0.5, u0=0.8, u1=FA["-x"].L - 0.8, gap=0.7, band=False)
    FA["-x"].emblem(FA["-x"].L * 0.5 - 1.0, 0.6, 2.0, 3.6)
    FC["+z"].ribs(2, 0.45, v1=FC["+z"].S - 0.3)
    FC["+x"].emblem(FC["+x"].L * 0.5 - 1.0, 0.6, 2.0, 3.6)
    FC["+z"].slits(2, FC["+z"].S * 0.7, 0.5, u0=0.8, u1=FC["+z"].L - 0.8, gap=0.7, band=False)
    FD["+z"].hatch(FD["+z"].L / 2 - 0.8, 0.5, 1.6, 1.8)
    # roof conduit runs on the long block (the originals' white pipe graphics)
    for xx in (-8.4, -5.4):
        c.b.box("lightroof", (xx, 5.9 + 0.12, -2.0), (0.22, 0.2, 14.0))
    c.b.box("lightroof", (-6.9, 5.9 + 0.12, -8.6), (3.0, 0.2, 0.22))
    c.b.box("lightroof", (-6.9, 5.9 + 0.12, 6.4), (3.0, 0.2, 0.22))
    c.b.box("lightroof", (-8.4, 5.9 + 0.35, 6.4), (0.9, 0.7, 0.9))
    c.b.box("lightroof", (-5.4, 5.9 + 0.35, -8.6), (0.9, 0.7, 0.9))
    c.b.box("lightroof", (4.0, 5.9 + 0.12, 6.0), (0.22, 0.2, 5.0))
    c.b.box("lightroof", (6.5, 5.9 + 0.12, 4.0), (4.0, 0.2, 0.22))
    for (x0, x1, z0, z1) in units:
        louvre_unit(c, x0, x1, z0, z1, 7.0, 10.6)
    # the unit's open end: a tan door panel with a pale arch outline on the +z end of the south unit
    if c.fine:
        c.b.box(WALL, (5.4, 3.4, 2.38), (3.4, 6.2, 0.1))
        c.b.box("lightroof", (5.4, 3.4, 2.46), (2.6, 5.4, 0.06))
        c.b.box(DARK, (5.4, 3.0, 2.5), (1.9, 4.6, 0.06))
    if state == "damaged":
        FA["-x"].scorch(0.25, 0.45, 1.8)
        FC["+z"].scorch(0.7, 0.4, 1.3)
        from bld_military import roof_scorch
        roof_scorch(c, -7.0, 5.96, 4.0, 1.8)
    return c


# ------------------------------------------------------------------------------------------------------------------ office (ziggurat)
def _hpg_office(state, lod, seed):
    """The ziggurat, measured in the glb's own frame (node offset applied): plinth y 0..1.1 over x -17.4..0.8, z -2.8..15.2; sloped tier to a plateau at y 10.2 (x -13.2..-3.3,
    z 0.7..12.2); the tower roof y 14.8 (x -9.7..-2.1, z 3.0..9.2) with the emblem prow sloping east to x 3.3; the west wing x -20.2..-15.2 with a flat roof at 5.5."""
    c = shell(state, lod, seed, (-5.0, 10.0, -1.0, 3.0), 2.0)
    B1 = ((-17.4, 0.8, -2.8, 15.2), (-13.2, -3.3, 0.7, 12.2))
    WING = ((-20.2, -14.0, -0.3, 12.7), (-20.2, -15.0, 1.7, 10.7))
    TWR = ((-10.6, -1.9, 2.8, 9.4), (-9.7, -2.1, 3.0, 9.2))
    if state == "destroyed":
        ruin(c, B1[0], B1[1], 10.2, 12, 3.6)
        ruin(c, WING[0], WING[1], 5.5, 4, 2.0)
        # the fallen tower: a charred stump and the prow's slab lying out to the east
        c.b.box("concrete_dark", (-5.5, 1.6, 6.0), (7.0, 2.6, 5.2))
        c.b.box(WALL, (0.5, 0.9, 6.0), (5.0, 0.5, 5.6), axis_angle(V([0, 0, 1.0]), -0.25))
        return c
    F1, _ = sbox(c, B1[0], -1.18, B1[1], 10.2, rim=0.9, plinth=2.28)
    FW, _ = sbox(c, WING[0], -1.18, WING[1], 5.5, rim=0.6, plinth=2.28)
    # tower: sloped walls from the plateau, the east face is the long emblem prow down to the ground
    b = c.b
    base_y = 10.2
    FT, _ = sbox(c, TWR[0], base_y, TWR[1], 14.8, rim=0.8, plinth=0.0, faces=False)
    FT["-z"].draw(WALL)
    FT["+z"].draw(WALL)
    FT["-x"].draw(WALL)
    prow = Fc(c, (3.3, 1.1, 3.0), (3.3, 1.1, 9.2), (-2.1, 14.8, 3.0), (-2.1, 14.8, 9.2), (1, 0, 0))
    prow.draw(WALL)
    # the prow's flanks (triangles) and the plinth under it
    for z in (3.0, 9.2):
        P = np.array([(3.3, 1.1, z), (-2.1, 14.8, z), (-2.1, 1.1, z)])
        b.add(WALL, P, np.tile((0, 0, -1 if z < 5 else 1), (3, 1)), P[:, [0, 1]], [(0, 1, 2)])
    b.box(PLINTH, (2.0, -0.04, 6.1), (2.6, 2.28, 6.2))
    prow.emblem(prow.L / 2 - 1.5, 2.4, 3.0, 9.4)
    prow.door(0.5, 0.9, 1.4, v=0.0) if False else None
    for sg in (-1, 1):                                              # two little white utility boxes at the prow's foot
        b.box("lightroof", (3.1, 1.3, 6.1 + sg * 2.4), (1.1, 1.5, 1.0))
        b.box(DARK, (3.66, 1.3, 6.1 + sg * 2.4), (0.06, 0.8, 0.6))
    # window row: the plateau skirt's two long faces (z), four separate glass rectangles each, as the originals' blue-glass ribbon
    for k, sgn in (("-z", 1), ("+z", 1)):
        f = F1[k]
        f.slits(4, f.S * 0.62, 1.1, u0=f.L * 0.2, u1=f.L * 0.8, gap=0.9, band=True)
    F1["-z"].ribs(2, 0.5, v1=F1["-z"].S - 0.3) if False else None
    FT["-z"].quad(DARK, FT["-z"].L * 0.5 - 2.2, 4.4, 1.6, 0.9, 0.06)       # recessed dark slot high on the tower's long face
    FT["+x"] if "+x" in FT else None
    FW["-x"].slits(3, FW["-x"].S * 0.55, 1.0, u0=1.0, u1=FW["-x"].L - 1.0, gap=0.9, band=False)
    FW["-z"].door(FW["-z"].L * 0.5 - 0.9, 1.8, 2.2, v=0.0) if False else None
    roof_plate(c, -17.6, 5.6, 5.5, 3.0, 3.6, 0.0)
    if state == "damaged":
        F1["-z"].scorch(0.7, 0.4, 2.0)
        F1["+z"].scorch(0.3, 0.45, 1.6)
        prow.scorch(0.5, 0.35, 1.8)
        from bld_military import roof_scorch
        roof_scorch(c, -6.0, 14.86, 6.0, 1.8)
    return c


def hpg_office(state, lod, seed):
    """The glb's node carries (7.37, 1.18, -6.09) and the game applies it, so the model sits at that offset: built in the raw mesh frame (base y -1.18), then shifted.
    The destroyed state is built on the ground and only moved in x / z (collapse and rubble reset the builder's own transform, so it cannot be done while building)."""
    c = _hpg_office(state, lod, seed)
    T = np.array([7.37, 1.1817 if state != "destroyed" else 0.0, -6.08716])
    for surf in c.b.s.values():
        surf["P"] = [P + T for P in surf["P"]]
    return c


# ------------------------------------------------------------------------------------------------------------------ the station
def dish(c, cx, cz, y_c=23.3):
    """A round parabolic lattice dish: rim radius 17.1 at y 30.6, centre y 23.3 (40 segments on the fine LOD, 20 on the far one). Radial ribs and concentric ring
    struts carry a complete pale grille (every cell filled; holes only in the damaged state), so the bowl is an open grille the ground shows through; panels are double-sided (a pale underside). Damaged: a
    wedge of panels torn out and bent ribs."""
    b = c.b
    N = 40 if c.fine else 20
    R_RIM, Y_RIM = 17.1, 30.6
    radii = [2.4, 5.6, 9.2, 13.0, R_RIM]

    def yy(r):
        return y_c + (Y_RIM - y_c) * (r / R_RIM) ** 2

    def pt(r, k, dy=0.0):
        a = TAU * k / N + math.pi
        return np.array([cx + r * math.cos(a), yy(r) + dy, cz + r * math.sin(a)])
    torn = c.state == "damaged"
    for i in range(len(radii) - 1):
        r0, r1 = radii[i], radii[i + 1]
        for k in range(N):
            if torn and ((4 <= k <= 9 and i >= 1) or (k * 7 + i * 3) % 13 == 0):
                continue                                                  # damaged only: a wedge of the grille shot away and a few stray panels
            P = np.array([pt(r0, k), pt(r0, k + 1), pt(r1, k + 1), pt(r1, k)])
            n = unit(np.cross(P[1] - P[0], P[3] - P[0]))
            if n[1] < 0:
                n = -n
            U = P[:, [0, 2]] * 0.8
            b.add("lightroof", P + n * 0.02, np.tile(n, (4, 1)), U, [(0, 1, 2), (0, 2, 3)])
            b.add("lightroof", P - n * 0.02, np.tile(-n, (4, 1)), U, [(0, 1, 2), (0, 2, 3)])
    # radial ribs (every second segment line on the far LOD) and the concentric rings, continuous sweeps
    step = 2 if c.fine else 1
    for k in range(0, N, step):
        path = [pt(r, k, 0.12) for r in [1.9] + radii]
        if torn and k in (6, 8):
            path = [p + np.array([0, 0.9 * max(0.0, (np.hypot(p[0] - cx, p[2] - cz) - 8) / 9), 0]) for p in path]   # bent up
        b.sweep("machgrey", path, 0.17 if c.fine else 0.24, 6 if c.fine else 4, caps=False)
    for r in radii:
        path = [pt(r, k, 0.12) for k in range(N)]
        b.sweep("machgrey", path, 0.4 if r == R_RIM else 0.15, 6 if c.fine else 4, closed=True, caps=False)
    # feed hub, horn and the lugs where the spires land (angles 0, 120, 240)
    b.revolve("steel", [(1.9, 22.0), (2.4, 23.2), (2.4, 23.8), (0.0, 24.0)], 12 if c.fine else 6, cx=cx, cz=cz, uref=1.0)
    b.revolve("lightroof", [(0.9, 24.0), (0.6, 27.0), (0.0, 29.3)], 8 if c.fine else 5, cx=cx, cz=cz, uref=1.0)
    for a in (0.0, TAU / 3, 2 * TAU / 3):
        ca, sa = math.cos(a), math.sin(a)
        b.box("steel", (cx + 17.6 * ca, 31.0, cz + 17.6 * sa), (1.6, 3.0, 1.6), axis_angle(V([0, 1.0, 0]), -a))
        tip = V([cx + 4.0 * ca, 48.6, cz + 4.0 * sa])
        base = V([cx + 18.0 * ca, 32.6, cz + 18.0 * sa])
        taper(c, "creamwall", base, tip, 1.6, 1.0, 0.25, 0.25, (-sa, 0, ca))


def hpgstation(state, lod, seed):
    c = shell(state, lod, seed, (22.0, 5.0, -10.0, 4.0), 2.0)
    PED = ((-8.8, 8.8, -8.8, 8.8), (-5.7, 5.7, -5.7, 5.7))
    HALL = ((14.9, 33.0, -20.9, 20.9), (17.3, 30.6, -19.2, 19.2))
    POD = ((24.5, 41.4, -9.0, 9.0), (26.4, 38.3, -5.9, 5.9))
    b = c.b
    if state == "destroyed":
        ruin(c, HALL[0], HALL[1], 7.0, 9, 2.6)
        ruin(c, POD[0], POD[1], 10.8, 4, 2.4)
        ruin(c, PED[0], PED[1], 16.0, 5, 2.6)
        # the dish has come down: sheets of it lie round the pedestal, bent ribs, a spire on the ground
        for k in range(7):
            a = c.rng.uniform(0, TAU)
            r = c.rng.uniform(5.0, 12.0)
            Rm = axis_angle(V([0, 1.0, 0]), a) @ axis_angle(V([1.0, 0, 0]), c.rng.uniform(-0.35, 0.35))
            ctr = V([r * math.cos(a), 0.9 + 0.3 * (k % 3), r * math.sin(a)])
            b.box("lightroof", ctr, (5.5, 0.1, 4.0), Rm)                       # a fallen sheet of the grille: a thin plate with two ribs on it
            for dz in (-1.3, 1.3):
                b.box("lightroof", ctr + Rm @ V([0, 0.12, dz]), (5.5, 0.14, 0.2), Rm)
        arc = [V([9.0 * math.cos(t), 0.5, 9.0 * math.sin(t)]) for t in np.linspace(0.3, 2.4, 14)]
        b.sweep("lightroof", arc, 0.2, 5, caps=False)                      # a bent ring strut
        for k in range(4):
            a = c.rng.uniform(0, TAU)
            p = V([c.rng.uniform(-9, 9), 0.5, c.rng.uniform(-9, 9)])
            b.tube("steel", p, p + V([math.cos(a) * 6, 0.4, math.sin(a) * 6]), 0.16, 5)
        p = V([-10.0, 0.5, -9.0])
        taper(c, "creamwall", p, p + V([-6.0, 1.5, -9.0]), 1.4, 0.9, 0.3, 0.3, (1, 0, 0))
        return c
    FP, _ = sbox(c, PED[0], 0.0, PED[1], 16.0, rim=0.9, plinth=2.0)
    FH, _ = sbox(c, HALL[0], 0.0, HALL[1], 7.0, rim=0.8, plinth=1.2)
    FO, _ = sbox(c, POD[0], 0.0, POD[1], 10.8, rim=0.8, plinth=1.2)
    # pedestal faces: emblems on -x, -z, +z; a recessed hatch panel on +x
    for k in ("-x", "-z", "+z"):
        f = FP[k]
        f.emblem(f.L / 2 - 1.5, 3.2, 3.0, 8.6)
    FP["+x"].quad(DARK, FP["+x"].L / 2 - 2.6, 5.2, 6.4, 5.8, 0.06)
    FP["+x"].quad("machgrey", FP["+x"].L / 2 - 2.3, 4.6, 6.7, 5.2, 0.08)
    if c.fine:
        for k in range(3):
            FP["+x"].quad(DARK, FP["+x"].L / 2 - 1.6, 3.2, 7.4 + k * 1.2, 0.35, 0.1)
    # neck, pipes
    b.box("steel", (0.0, 19.6, 0.0), (3.4, 7.2, 5.2))
    for k, z in enumerate((-2.0, 0.0, 2.0)):
        b.tube("lightroof", (-1.6, 16.0, z), (-1.6, 22.2, z), 0.35, 8 if c.fine else 5)
    # the two pipes (clamped) running from the pedestal's +x face to the hall
    for z in (-2.2, 2.2):
        b.tube("boatrust", (5.8, 3.6, z), (15.2, 3.6, z), 1.05, 10 if c.fine else 6)
        if c.fine:
            for xx in (8.0, 10.6, 13.2):
                b.revolve("lightroof", [(1.2, 3.1), (1.2, 4.1)], 10, cx=xx, cz=z, uref=1.0) if False else b.box("lightroof", (xx, 3.6, z), (0.5, 2.3, 2.3))
    dish(c, 0.0, 0.0)
    # hall: three white cooling units on each long side, sloped fronts
    for sg in (-1, 1):
        for k in range(3):
            x0 = 19.1 + k * 3.4
            zc = sg * 14.5
            P = [(x0, 7.0, zc - 2.9), (x0 + 3.0, 7.0, zc - 2.9)]
            b.box("lightroof", (x0 + 1.5, 7.0 + 0.9, zc), (3.0, 1.8, 5.8))
            b.box("machgrey", (x0 + 1.5, 7.0 + 1.82, zc), (2.7, 0.08, 5.3))
            if c.fine:
                for j in range(4):
                    b.box(DARK, (x0 + 1.5, 7.0 + 0.9, zc + sg * 2.92), (2.5, 0.12, 0.1)) if j == 0 else None
                b.box(DARK, (x0 + 1.5, 7.0 + 1.2, zc + sg * 2.92), (2.2, 0.5, 0.06))
                b.box(DARK, (x0 + 1.5, 7.0 + 0.5, zc + sg * 2.92), (2.2, 0.35, 0.06))
    roof_plate(c, 22.0, 0.0, 7.0, 3.0, 4.0, 0.0)
    roof_plate(c, 34.5, 0.0, 10.8, 3.2, 3.6, 0.0)
    for k in range(6):                                                # roof conduit between the units, a pipe run to the pod
        pass
    b.box("lightroof", (26.0, 7.14, 0.0), (7.6, 0.22, 0.28))
    b.box("lightroof", (22.0, 7.14, 8.0), (0.28, 0.22, 11.0))
    b.box("lightroof", (22.0, 7.14, -8.0), (0.28, 0.22, 11.0))
    # walls: hall -z/+z faces get ribs and slit rows, hatches at the corners; pod faces get slits; hall -x gets a door
    for k in ("-z", "+z"):
        f = FH[k]
        f.ribs(5, 0.5, v1=f.S - 0.3)
        f.slits(6, f.S * 0.68, 0.5, u0=1.2, u1=f.L - 1.2, gap=0.9, band=False)
        f.hatch(f.L * 0.08, 0.5, 1.5, 2.0)
    FH["-x"].door(FH["-x"].L / 2 - 1.0, 2.0, 2.4, v=0.1)
    for k in ("-z", "+z"):
        f = FO[k]
        f.slits(3, f.S * 0.6, 0.6, u0=1.4, u1=f.L - 1.4, gap=0.9, band=False)
    FO["+x"].ribs(3, 0.5, v1=FO["+x"].S - 0.3)
    if state == "damaged":
        FP["-z"].scorch(0.5, 0.65, 2.0)
        FH["-z"].scorch(0.4, 0.4, 2.0)
        FO["+x"].scorch(0.5, 0.5, 1.8)
        from bld_military import roof_scorch
        roof_scorch(c, 24.0, 7.06, 3.0, 2.2)
        # a bent rib sticks up from the dish rim and one panel is torn away: a dark hole in the bowl
        b.tube("steel", V([-10.0, 31.0, 11.0]), V([-8.0, 34.5, 10.0]), 0.18, 5)
        b.tube("steel", V([-4.0, 30.6, 16.0]), V([-2.0, 33.0, 15.0]), 0.15, 5)
    return c


# ------------------------------------------------------------------------------------------------------------------ outputs
MEMBERS = {
    "hpgstation": (hpgstation, "HPG station: nine-sided lattice dish (r 17.1, rim y 30.6) on three leaning spires (tips y 48.6) over a sloped pedestal, a long hall with cooling units and a stepped control pod"),
    "hpgoutbldg": (hpgoutbldg, "HPG outbuilding: U-plan sloped block x +-12.1, z -10.8..9.5, roof y 5.9, a low court block between the arms"),
    "hpg_office": (hpg_office, "HPG ziggurat (game frame: node offset 7.37, 1.18, -6.09 applied): stepped sloped tiers to a tower at y 14.8 with an emblem prow, a window ribbon, a flat-roofed west wing"),
    "hpg_gen": (hpg_gen, "HPG generator: a long sloped block, a second block with a low connector, two louvred cooling units with tent roofs to y 10.6"),
    "hpg_end": (hpg_end, "HPG end piece: a sloped head block (roof y 7.4) on a walkway arm"),
    "hpg_threeway": (hpg_threeway, "HPG three-way junction: a sloped head block with arms west, north and south"),
    "hpg_walkway": (walkway, "HPG walkway: a 25.6 m sloped arm with ribs, slit windows and two roof hatch plates"),
}


def build_member(app, out):
    fn, src = MEMBERS[app]
    info = {"app": app, "made_by": "tools/art/v3/bld_hpg.py", "source_dims": src, "states": {}}
    for si, state in enumerate(H.STATES):
        lods = [fn(state, lod, 4100 + si + sum(map(ord, app))).b for lod in (0, 1)]
        name = app + ("" if state == "intact" else "_" + state)
        st = Builder.write_lods(out / f"{name}.glb", name, lods)
        P = np.vstack([v for s in lods[0].s.values() for v in s["P"]])
        info["states"][state] = {"tris_lod0": int(sum(st[0].values())), "tris_lod1": int(sum(st[1].values())), "lod_switch_m": H.LOD_M,
                                 "bounds_min": np.round(P.min(0), 2).tolist(), "bounds_max": np.round(P.max(0), 2).tolist()}
        print(app, state, info["states"][state]["tris_lod0"], info["states"][state]["tris_lod1"], info["states"][state]["bounds_min"], info["states"][state]["bounds_max"], flush=True)
    (out / f"{app}.v3.json").write_text(json.dumps(info, indent=1) + "\n")


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
        build_member(app, out)


if __name__ == "__main__":
    main()
