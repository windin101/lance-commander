#!/usr/bin/env python3
"""v3 Liao palace and residence family (LANCE-39): l_palacetwr, l_palacewing, l_palacecore, l_palacegate, l_residencecore, l_residenceleft, l_residenceright.
Built to the Shared Source originals' in-game extents (the glb node offsets applied by shifted(): residence_core -1.59 x, residence_left -1.10 x, residence_Right -1.08 x /
-0.76 z; none of the seven has a node scale) from per-part and 1 m slice measurements (game/tools/orig_parts.gd, orig_bounds.gd). The look is the approved Liao
pieces' (bld_military.py l_hq / l_guardhouse / l_elitebarracks): stonewall podiums, teal bands, red-framed windows, tan roofs. The palace's identity is its
roofs: flared, concave, overhanging pagoda tiers (flare()) with a raised fascia and hip ridge lines. Windows are separate rectangles, never holes.
Style guide: docs/art/STYLE-GUIDE.md section 10.

    python3 -I tools/art/v3/bld_liaopalace.py <app>|all
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bld_hangars as H  # noqa: E402
from bld_city import rubble  # noqa: E402
from bld_industry import V, TAU, shell, blk, fpanel, ROOT, axis_angle  # noqa: E402
from bld_military import scorch, roof_scorch  # noqa: E402

STONE = ("concrete_dark", "flat")


# ------------------------------------------------------------------------------------------------------------------ roof kit
def _rect(box, grow=0.0):
    x0, x1, z0, z1 = box
    return [(x0 - grow, z0 - grow), (x1 + grow, z0 - grow), (x1 + grow, z1 + grow), (x0 - grow, z1 + grow)]


def _frust(c, mat, pa, ya, pb, yb, skip=()):
    """Sloped quads between two rectangles (same vertex order; side k runs from vertex k to k+1: 0 = -z, 1 = +x, 2 = +z, 3 = -x); skip omits sides."""
    pa = np.asarray(pa, float)
    pb = np.asarray(pb, float)
    cen = pa.mean(0)
    for k in range(4):
        if k in skip:
            continue
        k2 = (k + 1) % 4
        P = np.array([(pa[k][0], ya, pa[k][1]), (pa[k2][0], ya, pa[k2][1]), (pb[k2][0], yb, pb[k2][1]), (pb[k][0], yb, pb[k][1])])
        n = np.cross(P[1] - P[0], P[3] - P[0])
        n = n / (np.linalg.norm(n) or 1.0)
        if np.dot(n, P.mean(0) - np.array([cen[0], (ya + yb) / 2, cen[1]])) < 0:
            n = -n
        idx = [(0, 1, 2), (0, 2, 3)] if np.dot(np.cross(P[1] - P[0], P[2] - P[0]), n) > 0 else [(0, 2, 1), (0, 3, 2)]
        L = float(np.linalg.norm(P[1] - P[0]))
        Hh = float(np.linalg.norm(P[3] - P[0]))
        c.b.add(mat, P, np.array([n] * 4), np.array([(0, 0), (L, 0), (L, Hh), (0, Hh)]), idx)


def _lerp(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(4))


def flare(c, outer, y0, inner, y1, mat="tanroof", skip=(), cap=0.3, k=0.5, hips=True, fascia=0.45, cap_mat="tanroof", hf=0.30):
    """One pagoda tier: a concave (flared) overhanging roof, shallow at the eaves and steeper toward the ridge, from the eave rectangle `outer` at y0 to the flat
    top rectangle `inner` at y1, a raised teal fascia round the eave, hip ridge lines, a flat cap slab on top. Returns the y of the cap's top."""
    if c.state == "destroyed":
        return y1
    mid = _lerp(outer, inner, k)
    ym = y0 + hf * (y1 - y0)
    _frust(c, mat, _rect(outer), y0, _rect(mid), ym, skip)
    _frust(c, mat, _rect(mid), ym, _rect(inner), y1, skip)
    if cap > 0:
        x0, x1, z0, z1 = inner
        c.b.box(cap_mat, ((x0 + x1) / 2, y1 + cap / 2, (z0 + z1) / 2), (x1 - x0, cap, z1 - z0))
    if fascia > 0 and c.fine:
        x0, x1, z0, z1 = outer
        for s in (0, 1):
            if (2 if s else 0) not in skip:
                zz = z1 if s else z0
                c.b.box("tealpanel", ((x0 + x1) / 2, y0 + fascia / 2 - 0.05, zz), (x1 - x0 + 0.12, fascia, 0.14))
            if (1 if s else 3) not in skip:
                xx = x1 if s else x0
                c.b.box("tealpanel", (xx, y0 + fascia / 2 - 0.05, (z0 + z1) / 2), (0.14, fascia, z1 - z0 + 0.12))
    elif fascia > 0:
        x0, x1, z0, z1 = outer
        c.b.box("tealpanel", ((x0 + x1) / 2, y0 + 0.1, (z0 + z1) / 2), (x1 - x0 - 0.1, 0.2, z1 - z0 - 0.1))
    if hips and c.fine:
        po, pm, pi = _rect(outer), _rect(mid), _rect(inner)
        for j in range(4):
            if j in skip or (j - 1) % 4 in skip:
                continue
            a = V([po[j][0], y0 + 0.08, po[j][1]])
            m = V([pm[j][0], ym + 0.08, pm[j][1]])
            t = V([pi[j][0], y1 + 0.08, pi[j][1]])
            c.b.tube("tealpanel", a, m, 0.12, 4)
            c.b.tube("tealpanel", m, t, 0.12, 4)
    return y1 + cap


def storey(c, box, y0, y1, mat="tealwall", trim=True):
    """A plain wall box (teal) between two heights, with a pale-stone foot line and a dark head band on the fine LOD."""
    if c.state == "destroyed":
        return
    x0, x1, z0, z1 = box
    c.b.box(mat, ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), (x1 - x0, y1 - y0, z1 - z0))
    if trim and c.fine:
        c.b.box("tealpanel", ((x0 + x1) / 2, y1 - 0.2, (z0 + z1) / 2), (x1 - x0 + 0.12, 0.4, z1 - z0 + 0.12))


def win(c, key, box, u0, v0, w, h, y0=0.0):
    """A red-framed window: a frame rectangle and a dark glass rectangle in front of it (u along the face from its start, v up from y0)."""
    if c.state == "destroyed":
        return
    fpanel(c, "redframe", key, box, u0 - 0.2, v0 - 0.2, w + 0.4, h + 0.4, y0, 0.05)
    fpanel(c, "wglass", key, box, u0, v0, w, h, y0, 0.09)


def wrow(c, key, box, n, v0, w, h, y0=0.0, inset=1.0, rows=1, pitch=3.2):
    """n windows evenly along a face, `rows` rows."""
    if c.state == "destroyed":
        return
    L = {"-z": box[1] - box[0], "+z": box[1] - box[0], "-x": box[3] - box[2], "+x": box[3] - box[2]}[key]
    step = (L - 2 * inset) / n
    w = min(w, step * 0.62)
    for r in range(rows):
        for i in range(n):
            win(c, key, box, inset + (i + 0.5) * step - w / 2, v0 + r * pitch, w, h, y0)


def red_door(c, key, box, u0, w, h, y0=0.0, v0=0.0):
    """An ornate red double door: red leaf, gold lintel and handle bars (the originals' red panels with gold scrollwork)."""
    if c.state == "destroyed":
        return
    fpanel(c, "safetyyellow", key, box, u0 - 0.35, v0, w + 0.7, h + 0.5, y0, 0.05)
    fpanel(c, "redframe", key, box, u0 - 0.1, v0, w + 0.2, h + 0.2, y0, 0.08)
    if c.fine:
        fpanel(c, "safetyyellow", key, box, u0 + w / 2 - 0.08, v0, 0.16, h, y0, 0.11)
        for s in (-1, 1):
            fpanel(c, "safetyyellow", key, box, u0 + w / 2 + s * w * 0.22 - 0.1, v0 + h * 0.38, 0.2, h * 0.28, y0, 0.12)


def podium(c, box, h, y0=0.0, main=False, cornice=True, over=0.0, cor_h=0.9):
    """A stone podium (stonewall block) with a teal cornice band that overhangs it by `over`."""
    x0, x1, z0, z1 = box
    blk(c, x0, x1, z0, z1, h, STONE, y0=y0, holes={}, main=main, roof=None)
    if c.state == "destroyed":
        return
    if cornice:
        c.b.box("roofdark", ((x0 + x1) / 2, y0 + h + cor_h / 2, (z0 + z1) / 2), (x1 - x0 + 2 * over, cor_h, z1 - z0 + 2 * over))
        if c.fine:
            c.b.box("bluetrim", ((x0 + x1) / 2, y0 + h + 0.12, (z0 + z1) / 2), (x1 - x0 + 2 * over + 0.2, 0.24, z1 - z0 + 2 * over + 0.2))


def deck(c, box, y, t=0.3, mat="concrete", parapet=0.0, skip=()):
    """A flat grey stone roof deck, optionally with a low stone parapet round it."""
    if c.state == "destroyed":
        return
    x0, x1, z0, z1 = box
    c.b.box(mat, ((x0 + x1) / 2, y + t / 2, (z0 + z1) / 2), (x1 - x0, t, z1 - z0))
    if parapet > 0:
        for s in (0, 1):
            if (2 if s else 0) not in skip:
                c.b.box("roofdark", ((x0 + x1) / 2, y + t + parapet / 2, z1 if s else z0), (x1 - x0, parapet, 0.5))
            if (1 if s else 3) not in skip:
                c.b.box("roofdark", (x1 if s else x0, y + t + parapet / 2, (z0 + z1) / 2), (0.5, parapet, z1 - z0))


def dentils(c, box, y, h=0.45, step=1.6):
    """A row of small dark blocks under a cornice (the originals' dentil band), fine LOD only."""
    if c.state == "destroyed" or not c.fine:
        return
    x0, x1, z0, z1 = box
    nx = max(2, int((x1 - x0) / step))
    nz = max(2, int((z1 - z0) / step))
    for k in range(nx):
        xx = x0 + (k + 0.5) * (x1 - x0) / nx
        for zz in (z0, z1):
            c.b.box("tealwall", (xx, y, zz), (0.7, h, 0.3))
    for k in range(nz):
        zz = z0 + (k + 0.5) * (z1 - z0) / nz
        for xx in (x0, x1):
            c.b.box("tealwall", (xx, y, zz), (0.3, h, 0.7))


def beams(c, pts, n=3, r=0.09):
    """Bent steel beams sticking out of a damaged spot (damaged state only)."""
    if c.state != "damaged":
        return
    rng = c.rng
    for (x, y, z) in pts:
        for _ in range(n):
            a = V([x + rng.uniform(-0.8, 0.8), y, z + rng.uniform(-0.8, 0.8)])
            d = V([rng.uniform(-1.6, 1.6), rng.uniform(0.8, 2.0), rng.uniform(-1.6, 1.6)])
            c.b.tube("steel", a, a + d, r, 4)
            c.b.tube("steel", a + d, a + d * 1.5 + V([0, -0.5, 0.4]), r, 4)             # bent over at the tip


def soot(c, key, box, u0, v0, w, h, y0=0.0):
    if c.state != "damaged":
        return
    fpanel(c, "scorchblack", key, box, u0, v0, w, h, y0, 0.07)


def fallen_tier(c, cx, cz, w, y=0.0, n=1):
    """Destroyed: a toppled tan pagoda roof tier lying on the rubble, charred timbers across it."""
    if c.state != "destroyed":
        return
    rng = c.rng
    for k in range(n):
        R = axis_angle(V([1.0, 0, 0]), rng.uniform(-0.45, 0.45)) @ axis_angle(V([0, 0, 1.0]), rng.uniform(-0.45, 0.45)) @ axis_angle(V([0, 1.0, 0]), rng.uniform(0, 3.0))
        c.b.box("tanroof", (cx + rng.uniform(-w * 0.2, w * 0.2), y + 1.4 + 0.5 * k, cz + rng.uniform(-w * 0.2, w * 0.2)), (w, 0.5, w * 0.8), R)
        c.b.box("scorchblack", (cx, y + 1.18 + 0.5 * k, cz), (w * 0.9, 0.08, w * 0.7), R) if False else None
    for k in range(4 if c.fine else 1):
        a = V([cx + rng.uniform(-w * 0.5, w * 0.5), 0.9, cz + rng.uniform(-w * 0.5, w * 0.5)])
        c.b.tube("scorchblack", a, a + V([rng.uniform(-2.5, 2.5), rng.uniform(0.2, 1.0), rng.uniform(-2.5, 2.5)]), 0.2, 5)


def ruin(c, box, h, n=12):
    """Charred rubble kept inside the footprint (the rubble chunks are up to 3.4 m long and tilted, so the box is shrunk to keep them in)."""
    x0, x1, z0, z1 = box
    g = min(1.9, (x1 - x0) * 0.2, (z1 - z0) * 0.2)
    rubble(c, (x0 + g, x1 - g, z0 + g, z1 - g), h, n)


# ------------------------------------------------------------------------------------------------------------------ l_palacetwr
def l_palacetwr(state, lod, seed):
    """Measured (game frame): x -6.1..6.6, z -6.7..9.4, top 14.8. A low stone plinth, a teal panelled wall and dark dentil band to y 7, a wide flared eave skirt on
    three sides (the -z third is a flat grey terrace with a parapet), an offset lantern (x -3.3..3.7, z -0.4..6.6, y 8.7..11.7) with three red-framed windows a side
    under a second flared roof (eaves x -4.5..4.9, z -1.6..7.8 at 11.4) that tops out in a flat cap at 14.8."""
    c = shell(state, lod, seed, (0.0, 4.0, 2.0, 3.0), 2.0)
    b = c.b
    F = (-6.1, 6.6, -6.7, 9.4)
    body = (-5.6, 6.1, -6.2, 8.9)
    podium(c, F, 1.4, main=True, cornice=False)
    if state != "destroyed":
        storey(c, (body[0], body[1], body[2], body[3]), 1.4, 5.2, "tealwall", trim=False)
        storey(c, (body[0] + 0.12, body[1] - 0.12, body[2] + 0.12, body[3] - 0.12), 5.2, 7.0, "tealpanel", trim=False)
        if c.fine:
            for key, bx, n in (("+z", body, 6), ("-z", body, 6), ("-x", body, 7), ("+x", body, 7)):
                L = (bx[1] - bx[0]) if key in ("+z", "-z") else (bx[3] - bx[2])
                for i in range(n):                                             # the panel seams of the lower wall
                    fpanel(c, "tealpanel", key, bx, (i + 0.5) * L / n - 0.06, 1.4, 0.12, 3.8, 0.0, 0.05)
        dentils(c, (body[0], body[1], body[2], body[3]), 6.0, 0.5)
        # eave skirt: three sloped sides to the lantern, the -z third a flat parapeted terrace
        flare(c, F, 7.0, (-3.9, 4.4, -1.0, 7.1), 8.7, skip=(0,), cap=0.0, k=0.5)
        deck(c, (F[0] + 0.1, F[1] - 0.1, F[2] + 0.1, -0.9), 7.0, 0.8, "concrete", parapet=0.55, skip=(2,))
        # lantern
        LW = (-3.3, 3.7, -0.4, 6.6)
        storey(c, LW, 8.7, 11.7, "tealwall")
        for key in ("-z", "+z", "-x", "+x"):
            wrow(c, key, LW, 3, 0.65, 1.3, 1.9, 8.7, inset=0.5)
        for (px, pz) in ((LW[0], LW[2]), (LW[1], LW[2]), (LW[0], LW[3]), (LW[1], LW[3])):
            b.box("redframe", (px, 10.2, pz), (0.3, 3.0, 0.3))
        flare(c, (-4.5, 4.9, -1.6, 7.8), 11.4, (-1.4, 1.8, 1.5, 4.7), 14.5, cap=0.3, k=0.5)
        if c.fine:
            b.tube("tealpanel", V([0.2, 14.8, 3.1]), V([0.2, 15.0, 3.1]), 0.15, 5)
    else:
        podium(c, (-5.6, 6.1, -6.2, 8.9), 3.0, y0=1.4, cornice=False)
        ruin(c, F, 5.0, 14)
        fallen_tier(c, 0.3, 3.0, 5.0, y=1.0)
    if state == "damaged":
        scorch(c, "+z", body, 6.0, 3.4, 1.7)
        scorch(c, "-x", body, 6.0, 4.2, 1.3, y0=0.0)
        roof_scorch(c, 1.2, 8.8, 4.5, 1.9)
        roof_scorch(c, 0.4, 14.9, 3.1, 1.0)
        beams(c, [(1.2, 8.8, 4.5), (-2.4, 7.6, -3.0)])
        soot(c, "+z", LW, 1.0, 0.2, 2.2, 2.6, 8.7)
    return c


# ------------------------------------------------------------------------------------------------------------------ l_palacewing
def l_palacewing(state, lod, seed):
    """Measured: x -18.3..12.6, z -10.6..11.4, top 29.3. A stone base to y 8, a flared teal dentil cornice band to 12.6 (the widest part, x to 12.6 and z +-11),
    a grey deck, an upper stone storey (x -12.6..9.7, z -7.7..8.5, y 12.6..21.6) whose upper half is a red-framed window band, under a flared tan hip roof
    (eaves x -13.1..10.6, z -8.6..9.4 at 21.6) to a flat top at 27.3 with a small vent block at x -7.3."""
    c = shell(state, lod, seed, (0.0, 6.0, 0.0, 4.0), 2.0)
    b = c.b
    base = (-18.3, 11.8, -9.8, 10.6)
    podium(c, base, 8.2, main=True, cornice=False)
    UB = (-12.6, 9.7, -7.7, 8.5)
    if state != "destroyed":
        cor = (-18.3, 12.6, -10.6, 11.4)
        b.box("roofdark", ((cor[0] + cor[1]) / 2, 10.0, (cor[2] + cor[3]) / 2), (cor[1] - cor[0] - 0.7, 3.6, cor[3] - cor[2] - 0.7))
        b.box("tealwall", ((cor[0] + cor[1]) / 2, 12.3, (cor[2] + cor[3]) / 2), (cor[1] - cor[0], 0.7, cor[3] - cor[2]))
        b.box("tealwall", ((cor[0] + cor[1]) / 2, 8.45, (cor[2] + cor[3]) / 2), (cor[1] - cor[0] - 0.3, 0.5, cor[3] - cor[2] - 0.3))
        dentils(c, (cor[0] + 0.2, cor[1] - 0.2, cor[2] + 0.2, cor[3] - 0.2), 11.4, 0.7, 1.7)
        if c.fine:
            for k in range(14):                                                 # vertical seams of the band
                xx = cor[0] + 1.2 + k * (cor[1] - cor[0] - 2.4) / 13
                for zz in (cor[2] + 0.34, cor[3] - 0.34):
                    b.box("tealwall", (xx, 9.9, zz), (0.35, 2.2, 0.1))
        deck(c, (base[0], 11.6, base[2], base[3]), 12.6, 0.2, "concrete") if False else None
        deck(c, (cor[0] + 0.5, cor[1] - 0.5, cor[2] + 0.5, cor[3] - 0.5), 12.6, 0.25, "concrete", parapet=0.6)
        storey_stone = blk(c, UB[0], UB[1], UB[2], UB[3], 4.8, STONE, y0=12.85, holes={}, roof=None)
        storey(c, (UB[0] + 0.05, UB[1] - 0.05, UB[2] + 0.05, UB[3] - 0.05), 17.65, 21.6, "tealwall", trim=False)
        for key, n in (("-z", 7), ("+z", 7), ("-x", 3), ("+x", 3)):
            wrow(c, key, UB, n, 0.55, 1.5, 2.6, 17.65, inset=0.9)
        for px in np.linspace(UB[0], UB[1], 8):
            for zz in (UB[2], UB[3]):
                b.box("redframe", (px, 19.6, zz), (0.28, 4.0, 0.28))
        for px in (UB[0], UB[1]):
            for zz in np.linspace(UB[2], UB[3], 4):
                b.box("redframe", (px, 19.6, zz), (0.28, 4.0, 0.28))
        b.box("roofdark", ((UB[0] + UB[1]) / 2, 21.7, (UB[2] + UB[3]) / 2), (UB[1] - UB[0] + 0.3, 0.4, UB[3] - UB[2] + 0.3))
        yt = flare(c, (-13.1, 10.6, -8.6, 9.4), 21.9, (-9.6, 7.0, -4.5, 5.3), 27.3, cap=0.3, k=0.5)
        b.box("machgrey", (-7.3, yt + 0.7, 0.0), (3.7, 1.4, 3.6))
        b.box("tanroof", (-7.3, yt + 1.5, 0.0), (4.3, 0.25, 4.2))
        if c.fine:
            b.tube("tealpanel", V([-9.6, 27.45, 0.0]), V([7.0, 27.45, 0.0]), 0.16, 5)       # the ridge line along the top
    else:
        podium(c, (-12.6, 9.7, -7.7, 8.5), 3.5, y0=0.0, cornice=False) if False else None
        ruin(c, base, 8.0, 22)
        ruin(c, UB, 6.0, 10)
        fallen_tier(c, -4.0, 0.0, 9.0, y=1.0, n=2)
    if state == "damaged":
        scorch(c, "+z", base, 8.0, 5.0, 2.0)
        scorch(c, "-z", UB, 11.0, 4.5, 2.2, y0=12.85) if False else None
        scorch(c, "-z", UB, 11.0, 3.4, 2.0, y0=17.65)
        scorch(c, "+x", UB, 6.0, 2.6, 1.5, y0=12.85)
        roof_scorch(c, -2.0, 24.6, 3.0, 2.4)
        beams(c, [(-2.0, 24.6, 3.0), (6.0, 12.7, -4.0)])
        soot(c, "+z", UB, 4.0, 0.4, 3.0, 3.4, 17.65)
    return c


# ------------------------------------------------------------------------------------------------------------------ l_palacecore
def l_palacecore(state, lod, seed):
    """Measured: x -11.2..11.2, z -27.4..17.7, top 46.7. A stone podium (x +-10.4, z -26.7..5.8, y 0..16.4) with a teal cornice and a red double door over a stair
    that climbs from z 17.7; a grey deck; a hall at the rear (walls y 17.4..26.6, windows on both long faces) under the big flared roof (eaves z -27.4..-3.3 at
    26.6, sloping to the front, the rear wall rising as a cliff) to y 34, then a dark band, a second flared roof (eaves +-7.4 at 36.8), a lantern, a third roof and
    a finial at 46.7."""
    c = shell(state, lod, seed, (0.0, 12.0, 4.0, 4.0), 2.0)
    b = c.b
    P = (-10.4, 10.4, -26.7, 5.8)
    podium(c, P, 8.6, main=True, cornice=False)
    HW = (-7.4, 7.4, -26.2, -4.5)
    # stair: steps from the podium front down to the ground, with cheek walls
    n = 9 if c.fine else 4
    if state != "destroyed":
        run = 17.7 - 5.8
        for i in range(n):
            z0_ = 5.8 + i * run / n
            h_ = 8.4 * (1 - (i + 0.5) / n)
            b.box("lightroof", (0.0, h_ / 2, z0_ + run / n / 2), (8.6, h_, run / n))
            if c.fine:
                b.box("concrete_dark", (-5.0, h_ / 2 + 0.45, z0_ + run / n / 2), (1.4, h_ + 0.9, run / n))
                b.box("concrete_dark", (5.0, h_ / 2 + 0.45, z0_ + run / n / 2), (1.4, h_ + 0.9, run / n))
        if not c.fine:
            b.box("concrete_dark", (-5.0, 4.5, 11.8), (1.4, 9.0, 11.9)) if False else None
        # the teal pavilion storey on the stone base (y 8.6..16.4), the cornice flaring out over it, the upper deck
        storey(c, (P[0] + 0.05, P[1] - 0.05, P[2] + 0.05, P[3] - 0.05), 8.6, 16.4, "tealwall", trim=False)
        if c.fine:
            for key in ("-x", "+x", "-z"):
                L = (P[1] - P[0]) if key == "-z" else (P[3] - P[2])
                for i in range(1, 8 if key != "-z" else 5):
                    fpanel(c, "tealpanel", key, P, i * L / (8 if key != "-z" else 5) - 0.07, 0.0, 0.14, 7.4, 8.6, 0.05)
            fpanel(c, "safetyyellow", "+z", P, 0.0, 0.0, 20.8, 0.18, 8.45, 0.06)
        b.box("roofdark", (0.0, 16.9, (P[2] + 6.6) / 2), (22.4, 1.0, 6.6 - P[2]))
        if c.fine:
            b.box("bluetrim", (0.0, 16.5, (P[2] + 6.6) / 2), (22.6, 0.22, 6.8 - P[2]))
            dentils(c, (-10.8, 10.8, P[2] + 0.3, 6.2), 16.1, 0.5, 1.9)
        deck(c, (-10.4, 10.4, -4.5, 5.8), 17.35, 0.3, "concrete", parapet=0.5, skip=(0,))
        red_door(c, "+z", P, 8.4, 4.0, 6.0, 0.0, v0=8.7)                        # the lower red door at the stair head
        if c.fine:
            fpanel(c, "safetyyellow", "+z", P, 7.7, 15.2, 5.4, 0.3, 0.0, 0.08)
        # the hall
        storey(c, HW, 17.65, 26.6, "tealwall")
        for key, nn in (("-x", 6), ("+x", 6)):
            wrow(c, key, HW, nn, 2.7, 1.5, 2.8, 17.65, inset=1.3)
        wrow(c, "+z", HW, 3, 2.7, 1.5, 2.8, 17.65, inset=1.0)
        red_door(c, "+z", HW, 5.4, 3.2, 5.2, 17.65, v0=0.0)
        for px in np.linspace(HW[0], HW[1], 5):
            b.box("redframe", (px, 22.3, HW[3] + 0.02), (0.3, 8.6, 0.3))
        flare(c, (-8.1, 8.1, -27.4, -3.3), 26.7, (-6.4, 6.4, -25.0, -14.0), 34.0, cap=0.3, k=0.5)
        # dark band with small windows, second roof, lantern, third roof, finial
        TB = (-6.2, 6.2, -25.2, -15.0)
        storey(c, TB, 34.3, 37.0, "tealpanel")
        for key, nn in (("+z", 3), ("-x", 3), ("+x", 3)):
            wrow(c, key, TB, nn, 0.55, 1.1, 1.6, 34.3, inset=0.7)
        flare(c, (-7.4, 7.4, -26.6, -14.7), 36.9, (-3.0, 3.0, -24.4, -19.6), 39.5, cap=0.25, k=0.5)
        LN = (-2.6, 2.6, -24.0, -19.8)
        storey(c, LN, 39.75, 42.2, "tealwall")
        for key in ("+z", "-x", "+x"):
            wrow(c, key, LN, 2 if key == "+z" else 2, 0.5, 0.9, 1.3, 39.75, inset=0.5)
        flare(c, (-4.6, 4.6, -26.2, -17.6), 42.0, (-1.0, 1.0, -22.8, -21.0), 45.4, cap=0.25, k=0.5)
        b.tube("machgrey", V([0.0, 45.5, -21.9]), V([0.0, 46.7, -21.9]), 0.14, 5)
        if c.fine:
            b.box("tealpanel", (0.0, 45.9, -21.9), (0.9, 0.18, 0.9))
    else:
        ruin(c, P, 10.0, 26)
        ruin(c, (-8.1, 8.1, -27.0, -4.0), 8.0, 12)
        fallen_tier(c, 0.0, -15.0, 9.0, y=2.2, n=2)
        for i in range(3):
            b.box("concrete_dark", (0.0, 0.8 * (3 - i) * 0.5, 7.5 + i * 2.0), (6.0, 0.8 * (3 - i), 2.0))
    if state == "damaged":
        scorch(c, "-x", P, 9.0, 7.0, 2.4, y0=0.0)
        scorch(c, "-x", HW, 10.0, 3.0, 1.8, y0=17.65)
        roof_scorch(c, 0.0, 30.0, -17.0, 2.6)
        roof_scorch(c, 0.0, 17.8, 0.0, 1.8)
        beams(c, [(0.0, 30.0, -17.0), (3.0, 17.7, 0.5)])
        soot(c, "+z", HW, 0.5, 0.4, 2.2, 6.0, 17.65)
    return c


# ------------------------------------------------------------------------------------------------------------------ l_palacegate
def l_palacegate(state, lod, seed):
    """Measured: x -29.2..29.2, z -6.0..3.8, top 14.1. Two long low stone walls (z -2.7..2.8, y 0..4.7, flat walk with a teal cornice) either side of a gatehouse
    (x +-9.7, z -5.8..3.8) with an arched passage, a teal band, a flared tan eave roof and a smaller second tier with a ridge at 14.1."""
    c = shell(state, lod, seed, (0.0, 6.0, 0.0, 4.0), 2.0)
    b = c.b
    GH = (-9.5, 9.5, -5.8, 3.6)
    for s in (-1, 1):
        wall = (9.3 if s > 0 else -29.2, 29.2 if s > 0 else -9.3, -2.55, 2.55)
        blk(c, *wall, 3.4, STONE, holes={}, main=(s > 0), roof=None)
        if state != "destroyed":
            xm = (wall[0] + wall[1]) / 2
            b.box("roofdark", (xm, 3.9, 0.0), (wall[1] - wall[0] + 0.1, 0.9, 5.4))
            b.box("concrete_dark", (xm, 4.5, 0.0), (wall[1] - wall[0] - 0.4, 0.3, 4.6))
            if c.fine:
                b.box("bluetrim", (xm, 3.45, 0.0), (wall[1] - wall[0] + 0.2, 0.2, 5.6))
                for k in range(int((wall[1] - wall[0]) / 3.6)):                    # buttress pilasters on both faces
                    xx = wall[0] + 1.8 + k * 3.6
                    for zz in (-2.62, 2.62):
                        b.box("concrete_dark", (xx, 1.7, zz), (0.9, 3.4, 0.25))
    if state != "destroyed":
        # gatehouse: two piers and a lintel round the arched passage (x +-4.3, arch top 5.4)
        for s_ in (-1, 1):                                                         # piers, then stepped corbel courses that close the passage into an arch
            x0, x1 = (4.6, 9.5) if s_ > 0 else (-9.5, -4.6)
            blk(c, x0, x1, GH[2], GH[3], 4.0, STONE, holes={}, roof=None)
        for (ya, yb, hw) in ((4.0, 4.9, 3.9), (4.9, 5.7, 2.8), (5.7, 6.4, 1.5), (6.4, 7.0, 0.0)):
            for s_ in (-1, 1):
                xa, xb = (hw, 4.6) if s_ > 0 else (-4.6, -hw)
                if xb - xa > 0.05:
                    b.box("concrete_dark", ((xa + xb) / 2, (ya + yb) / 2, (GH[2] + GH[3]) / 2), (xb - xa, yb - ya, GH[3] - GH[2]))
            if hw == 0.0:
                b.box("concrete_dark", (0.0, (ya + yb) / 2, (GH[2] + GH[3]) / 2), (3.0, yb - ya, GH[3] - GH[2]))
        b.box("roofdark", (0.0, 7.5, (GH[2] + GH[3]) / 2), (19.0, 1.0, GH[3] - GH[2] + 0.5))
        if c.fine:
            b.box("bluetrim", (0.0, 7.05, (GH[2] + GH[3]) / 2), (19.2, 0.2, GH[3] - GH[2] + 0.7))
            for s in (-1, 1):
                red_door(c, "+z", GH, 0.0, 0.1, 0.1, 0.0) if False else None
            dentils(c, (-9.4, 9.4, GH[2] + 0.1, GH[3] - 0.1), 6.9, 0.4, 1.8)
            for s_ in (-1, 1):                                                     # red posts framing the passage on both faces
                for zz in (GH[2] - 0.02, GH[3] + 0.02):
                    b.box("redframe", (s_ * 4.75, 2.0, zz), (0.35, 4.0, 0.15))
        # roof: lower flared eave tier, upper tier ridge
        flare(c, (-9.9, 9.9, -6.0, 3.8), 8.0, (-5.2, 5.2, -3.4, 1.4), 10.7, cap=0.25, k=0.5)
        storey(c, (-4.6, 4.6, -3.0, 1.0), 10.9, 12.0, "tealpanel")
        flare(c, (-5.2, 5.2, -3.6, 1.6), 11.8, (-3.5, 3.6, -2.5, -0.5), 14.0, cap=0.15, k=0.5)
        if c.fine:
            b.tube("tealpanel", V([-3.5, 14.2, -1.5]), V([3.6, 14.2, -1.5]), 0.14, 5)
            for sx in (-1, 1):
                wrow(c, "+z", (-4.6, 4.6, -3.0, 1.0), 2, 0.1, 1.0, 0.7, 10.9, inset=0.9) if sx > 0 else None
    else:
        for s in (-1, 1):
            x0, x1 = (4.3, 9.5) if s > 0 else (-9.5, -4.3)
            blk(c, x0, x1, GH[2], GH[3], 3.0, STONE, holes={}, roof=None)
        ruin(c, GH, 6.0, 12)
        fallen_tier(c, 0.0, -1.0, 7.0, y=0.5)
        for s in (-1, 1):
            ruin(c, (14.0 if s > 0 else -29.0, 29.0 if s > 0 else -14.0, -2.5, 2.5), 2.0, 5)
    if state == "damaged":
        scorch(c, "+z", GH, 3.0, 3.0, 1.7)
        scorch(c, "-z", GH, 15.0, 4.0, 1.5, y0=0.0) if False else None
        roof_scorch(c, 2.0, 10.9, -0.5, 1.6)
        beams(c, [(2.0, 10.9, -0.5), (18.0, 4.7, 0.0)])
        soot(c, "+z", GH, 5.0, 0.2, 2.0, 5.0, 0.0)
    return c


# ------------------------------------------------------------------------------------------------------------------ l_residencecore
def l_residencecore(state, lod, seed):
    """Measured (node offset applied): x -15.2..11.9, z -11.9..11.4, top 20.1. A stone base y 0..8 (x -12.3..11.1, z -11.1..10.6) with a stair on the -x face to a red
    door, a teal panelled wall y 8..14 with red-framed windows, a wide concave flared tan roof (eaves 22.8 x 23.2 at y 14) to a flat grey top at y 20 (x -4.2..5.6)."""
    c = shell(state, lod, seed, (-12.0, 4.0, 0.0, 3.0), 2.0)
    b = c.b
    B = (-12.3, 11.1, -11.1, 10.6)
    podium(c, B, 8.0, main=True, cornice=False)
    if state != "destroyed":
        W = (-11.9, 10.7, -10.7, 10.2)
        storey(c, W, 8.2, 14.0, "tealwall", trim=False)
        b.box("roofdark", ((B[0] + B[1]) / 2, 8.2, (B[2] + B[3]) / 2), (B[1] - B[0] + 0.3, 0.45, B[3] - B[2] + 0.3))
        if c.fine:
            b.box("safetyyellow", ((B[0] + B[1]) / 2, 7.7, (B[2] + B[3]) / 2), (B[1] - B[0] + 0.12, 0.15, B[3] - B[2] + 0.12))
            for key, bx in (("-x", W), ("+x", W), ("-z", W), ("+z", W)):           # the panel seams of the teal wall
                L = (bx[1] - bx[0]) if key in ("-z", "+z") else (bx[3] - bx[2])
                for i in range(1, 6):
                    fpanel(c, "tealpanel", key, bx, i * L / 6 - 0.06, 0.2, 0.12, 5.4, 8.2, 0.05)
        # -x front: door, stair, two triple windows
        red_door(c, "-x", B, 8.0, 5.2, 7.2, 0.0, v0=0.4)
        for s in range(2):
            for k in range(3):
                win(c, "-x", W, 1.4 + s * 12.4 + k * 2.2, 1.6, 1.3, 3.0, 8.2)
        red_door(c, "+x", B, 8.2, 5.2, 7.2, 0.0, v0=0.4)                          # a second red door on the +x face
        for i in range(4):                                                         # steps up to the door
            b.box("lightroof", (-12.3 - 0.8 - (3 - i) * 0.0 - 0.0 - (i * 0.0), 0.35 * (4 - i) / 2 + 0.0, 0.0), (1.6, 0.35 * (4 - i), 9.0 - i * 0.0)) if False else None
        for i in range(3):
            b.box("lightroof", (-12.3 - 0.7 * (i + 0.5), 0.55 * (3 - i) / 2, 0.0), (0.7, 0.55 * (3 - i), 9.6))
        # concave flared roof
        flare(c, (-10.9, 11.9, -11.9, 11.4), 14.0, (-4.2, 5.6, -5.5, 5.1), 19.8, cap=0.3, k=0.66, hf=0.2, cap_mat="concrete")
    else:
        ruin(c, B, 8.0, 18)
        fallen_tier(c, 0.0, 0.0, 8.0, y=1.5, n=2)
    if state == "damaged":
        scorch(c, "+z", B, 8.0, 3.5, 2.0)
        scorch(c, "-z", W, 14.0, 2.5, 1.7, y0=8.2) if False else None
        scorch(c, "+x", B, 14.0, 4.0, 1.9)
        roof_scorch(c, 2.0, 18.5, 2.0, 2.4)
        beams(c, [(2.0, 18.5, 2.0), (-8.0, 14.2, -6.0)])
        soot(c, "+x", B, 4.0, 8.4, 3.0, 5.0, 0.0)
    return c


# ------------------------------------------------------------------------------------------------------------------ l_residenceleft / right
def residence_side(state, lod, seed, sg):
    """Measured (node offset applied; right is the left mirrored in z, sg = +1 left, -1 right): x -7.5..13.7, z -12.5..18.6 (left), top 24.2. A stone body
    (z -12.2..16.9 low terrace part, z -1.3..16.3 taller part to y 12) with teal cornices, a flat grey deck, a stone tower (x -0.6..6.3, z 2.4..8.7, y 12..19.6) and a
    small flared pagoda cap (eaves x -1.6..7.3, z 1.4..9.7 at y 21, flat top at 24)."""
    c = shell(state, lod, seed, (4.0, 8.0, 5.0 * sg, 3.0), 2.0)
    b = c.b

    def Z(z0, z1):
        return (min(sg * z0, sg * z1), max(sg * z0, sg * z1))
    z_lo = Z(-12.2, 16.9)
    base = (-7.5, 12.1) + z_lo
    podium(c, base, 8.0, main=True, cornice=False)
    tall = (-7.5, 11.8) + Z(-1.3, 16.3)
    if state != "destroyed":
        # lower cornice over the whole body, the taller block above it
        cor = (-7.5, 13.7) + Z(-12.5, 18.6)
        b.box("roofdark", ((cor[0] + cor[1]) / 2, 8.55, (cor[2] + cor[3]) / 2), (cor[1] - cor[0], 1.1, cor[3] - cor[2]))
        b.box("tealwall", ((cor[0] + cor[1]) / 2, 9.25, (cor[2] + cor[3]) / 2), (cor[1] - cor[0] + 0.1, 0.3, cor[3] - cor[2] + 0.1))
        if c.fine:
            dentils(c, (cor[0] + 0.2, cor[1] - 0.2, cor[2] + 0.2, cor[3] - 0.2), 7.85, 0.5, 1.7)
        deck(c, (cor[0] + 0.3, cor[1] - 0.3, cor[2] + 0.3, cor[3] - 0.3), 9.4, 0.25, "concrete", parapet=0.8)
        blk(c, tall[0] + 0.3, tall[1] - 0.3, tall[2] + 0.3, tall[3] - 0.3, 2.4, STONE, y0=9.65, holes={}, roof=None)
        b.box("roofdark", ((tall[0] + tall[1]) / 2, 12.2, (tall[2] + tall[3]) / 2), (tall[1] - tall[0] + 0.3, 0.55, tall[3] - tall[2] + 0.3))
        deck(c, (tall[0] + 0.2, tall[1] - 0.2, tall[2] + 0.2, tall[3] - 0.2), 12.4, 0.25, "concrete", parapet=0.7)
        if c.fine:
            for i in range(5):                                                      # the red stripes on the walls
                zz = (tall[2] + tall[3]) / 2
                b.box("redframe", (tall[0] + 0.28, 6.0, zz + (i - 2) * 3.4 * sg), (0.12, 8.0, 0.22)) if False else None
            for zz in (-8.0, -4.0):
                b.box("redframe", (-7.52, 5.5, sg * zz), (0.12, 4.0, 0.3))
        # entrance and windows on the +z (left) / -z (right) end face of the tall block, facing the court
        zc = lambda zl: base[3] - sg * zl                      # u along the -x face (starts at z1, runs toward -z)
        red_door(c, "-x", base, zc(9.4) - 1.7, 3.4, 6.2, 0.0, v0=0.4)
        for k in range(3):
            win(c, "-x", base, zc(2.6 + (k - 1) * 2.0) - 0.7, 2.0, 1.4, 3.6, 0.0)
        # tower
        T = (-0.6, 6.3) + Z(2.4, 8.7)
        blk(c, T[0], T[1], T[2], T[3], 7.4, STONE, y0=12.65, holes={}, roof=None)
        b.box("roofdark", ((T[0] + T[1]) / 2, 20.35, (T[2] + T[3]) / 2), (T[1] - T[0] + 0.7, 0.7, T[3] - T[2] + 0.7))
        flare(c, (-1.6, 7.3) + Z(1.4, 9.7), 20.7, (1.3, 4.4) + Z(4.1, 7.0), 23.7, cap=0.4, k=0.5, cap_mat="concrete")
        if c.fine:
            b.tube("tealpanel", V([2.85, 24.1, sg * 5.55]), V([2.85, 24.2, sg * 5.55]), 0.2, 5)
    else:
        ruin(c, base, 8.0, 20)
        ruin(c, tall, 6.0, 10)
        fallen_tier(c, 2.8, sg * 5.5, 5.5, y=1.5)
    if state == "damaged":
        k = "+z" if sg > 0 else "-z"
        scorch(c, k, base, 6.0, 3.5, 1.9)
        scorch(c, "+x", base, (8.0 if sg > 0 else 20.0), 3.0, 1.6)
        roof_scorch(c, 5.0, 12.5, sg * 9.0, 1.8)
        roof_scorch(c, 2.8, 23.9, sg * 5.5, 0.9)
        beams(c, [(5.0, 12.5, sg * 9.0), (-3.0, 9.5, sg * -6.0)])
        soot(c, k, base, 2.0, 0.4, 2.5, 6.0, 0.0)
    return c


def l_residenceleft(state, lod, seed):
    return residence_side(state, lod, seed, 1)


def l_residenceright(state, lod, seed):
    return residence_side(state, lod, seed, -1)


def shifted(fn, shift):
    """The residence glbs' nodes carry a translation that the game applies to the original (residence_core -1.5893 x, residence_left -1.0951 x, residence_Right
    -1.0791 x / -0.7584 z; the palace nodes have none and none of the seven has a scale), so those three are shifted likewise after building (collapse and rubble
    reset the builder's own transform, so it cannot be done while building)."""
    T = np.array(shift, float)

    def build(state, lod, seed):
        c = fn(state, lod, seed)
        for surf in c.b.s.values():
            surf["P"] = [P + T for P in surf["P"]]
        return c
    return build


MEMBERS = {
    "l_palacetwr": (l_palacetwr, "Liao palace tower: stone plinth, teal dentil wall, wide flared eaves, offset red-framed lantern under a second flared roof"),
    "l_palacewing": (l_palacewing, "Liao palace wing: stone base, flared teal cornice band, red-framed window storey under a flared tan hip roof"),
    "l_palacecore": (l_palacecore, "Liao palace core: stone podium with stair and red doors, hall, and a stack of flared pagoda roofs to a finial"),
    "l_palacegate": (l_palacegate, "Liao palace gate: two long stone walls and an arched gatehouse under two flared roof tiers"),
    "l_residencecore": (shifted(l_residencecore, (-1.5893, 0.0, 0.0)), "Liao residence core: stone base with red door, teal wall, wide concave flared roof"),
    "l_residenceleft": (shifted(l_residenceleft, (-1.0951, 0.0, 0.0)), "Liao residence left: terraced stone body, stone tower, small flared pagoda cap"),
    "l_residenceright": (shifted(l_residenceright, (-1.07914, 0.0, -0.75842)), "Liao residence right: l_residenceleft mirrored in z"),
}
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
        H.build_member(app, out)


if __name__ == "__main__":
    main()
