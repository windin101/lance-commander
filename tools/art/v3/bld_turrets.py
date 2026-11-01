#!/usr/bin/env python3
"""v3 turret family (LANCE-39): gun turrets, their control centres and generators as v3 buildings.

    python3 -I tools/art/v3/bld_turrets.py <app>|all [--out game/assets/v3/objects]

Same contract as bld_family.py (<app>.glb, <app>_damaged.glb, <app>_destroyed.glb, <app>.v3.json; nodes lod0/lod1 per part;
surfaces bv3_<material> on the shared library) with one addition the kit did not need: a glTF NODE TREE.
    Base            the pedestal (static)
    Turret          yaws: ObjectsView.set_turret_yaw turns this node about its own origin (the original's pivot)
      Gun           pitches (rotation about X); carries the weapon (barrels, racks)
      Pop           (pop-up emplacements) rises out of the ground: ObjectsView.set_turret_pop
Every part is built in its own node's frame; Model/write_tree subtract each node's world pivot on the way out, so the baked
burn / run-off / AO (which are functions of world position) still see world coordinates. The wreck has no moving parts.
Dimensions: the Shared Source originals' node bounds (Turret x/y/z extents, Base 4.6 m square by 4 m) and, for the control
centres, tools/cad/<app>_cad.py (which measured the original's vertices). All geometry is new.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bld_kit import Ctx, axis_angle, cell_uv, TAU  # noqa: E402
from bld_mesh import Builder, unit, R  # noqa: E402  (R = hd_rig, the GlbWriter)
from bld_family import panel, torn_keep, jag_disp  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
LOD_M = 80.0
STATES = ("intact", "damaged", "destroyed")


# ===================================================================================================== model tree
class _Shim:
    def __init__(self, b):
        self.b = b


class Model:
    """A node tree whose nodes each own a Builder. build(local coordinates) -> world positions via Builder.M for the hooks."""

    def __init__(self, c: Ctx):
        self.c = c
        self.nodes = {}
        self.order = []

    def node(self, name, parent=None, t=(0.0, 0.0, 0.0), world=True):
        """A node at translation t from its parent. world=False: a wreck part that is placed by hand (its Builder.M is the pose)."""
        b = Builder()
        b.seg_cap = self.c.b.seg_cap
        b.colfn, b.wearfn, b.aofn = self.c.b.colfn, self.c.b.wearfn, self.c.b.aofn
        if self.c.state == "destroyed":  # charred through: blackened metal and concrete, as the vehicle wrecks (burn ~0.9-1.0 everywhere)
            b.colfn = lambda P: np.clip(0.93 + 0.07 * np.sin(P[:, 0] * 2.3 + P[:, 2] * 1.9 + P[:, 1] * 0.7), 0.0, 1.0)
        wt = np.asarray(t, float) + (self.nodes[parent]["wt"] if parent else 0.0)
        if world:
            b.M = (np.eye(3), wt.copy())
        self.nodes[name] = {"name": name, "t": np.asarray(t, float), "wt": wt, "b": b, "parent": parent, "kids": []}
        if parent:
            self.nodes[parent]["kids"].append(name)
        self.order.append(name)
        return b


def _material(g, name, mat):
    mi = next((k for k, m in enumerate(g["materials"]) if m["name"] == f"bv3_{mat}"), None)
    if mi is None:
        g["materials"].append({"name": f"bv3_{mat}", "pbrMetallicRoughness": {"baseColorFactor": [0.6, 0.6, 0.6, 1], "metallicFactor": 0.0, "roughnessFactor": 0.8},
                               "doubleSided": mat in ("decal", "interior", "chain")})
        mi = len(g["materials"]) - 1
    return mi


CHAR = {k: "roofdark" for k in ("whitecity", "concrete", "paint", "palepaint", "greybrick", "facadeblue", "brickcity", "bandgreen", "tealwall")}
CHAR.update({k: "slate" for k in ("concrete_dark", "tankgrey", "machgrey", "steel", "galv", "grate", "wglass", "bandorange", "safetyyellow", "corrugated")})


def write_tree(path, name, models, remap=None):
    """models: [Model for lod0, Model for lod1] with identical node trees. One glTF; each node has lodN mesh children."""
    g = {"asset": {"version": "2.0", "generator": "tools/art/v3/bld_turrets.py"}, "scenes": [{"nodes": [0]}], "scene": 0,
         "nodes": [{"name": name, "children": []}], "meshes": [], "materials": [], "buffers": [], "bufferViews": [], "accessors": []}
    w = R.GlbWriter(g, bytearray())
    ids = {}
    m0 = models[0]
    for nm in m0.order:  # parents are created before their kids
        n = m0.nodes[nm]
        node = {"name": nm, "translation": [round(float(x), 5) for x in n["t"]], "children": []}
        g["nodes"].append(node)
        ids[nm] = len(g["nodes"]) - 1
        (g["nodes"][ids[n["parent"]]] if n["parent"] else g["nodes"][0])["children"].append(ids[nm])
        for li, mdl in enumerate(models):
            bd = mdl.nodes[nm]["b"]
            if not bd.s:
                continue
            prims = []
            wt = n["wt"] if bd.M is not None else np.zeros(3)  # a hand-posed wreck part is already in the root frame
            groups = {}
            for mat, v in bd.s.items():  # a wreck is charred: every surface maps to a dark matte set (CHAR), same-set surfaces merge
                groups.setdefault(remap(mat) if remap else mat, []).append(v)
            for mat, vs in groups.items():
                P = (np.vstack([p_ for v in vs for p_ in v["P"]]) - wt).astype(np.float32)
                N = np.vstack([p_ for v in vs for p_ in v["N"]]).astype(np.float32)
                U = np.vstack([p_ for v in vs for p_ in v["U"]]).astype(np.float32); U2 = np.vstack([p_ for v in vs for p_ in v["U2"]]).astype(np.float32)
                C = np.vstack([p_ for v in vs for p_ in v["C"]]).astype(np.float32)
                # indices in each surface are already relative to that surface's own vertex list; offset them in the merged list
                I_, base = [], 0
                for v in vs:
                    I_.append(np.vstack(v["I"]).astype(np.uint32) + base)
                    base += int(sum(len(p_) for p_ in v["P"]))
                I = np.vstack(I_)
                prims.append({"attributes": {
                    "POSITION": w.accessor(P, "VEC3", target=34962, minmax=True), "NORMAL": w.accessor(N, "VEC3", target=34962),
                    "TEXCOORD_0": w.accessor(U, "VEC2", target=34962), "TEXCOORD_1": w.accessor(U2, "VEC2", target=34962),
                    "COLOR_0": w.accessor(C, "VEC4", target=34962)},
                    "indices": w.accessor(I.reshape(-1), "SCALAR", comp=5125, target=34963), "material": _material(g, nm, mat)})
            g["meshes"].append({"name": f"{nm}_lod{li}", "primitives": prims})
            g["nodes"].append({"name": f"lod{li}_{nm}", "mesh": len(g["meshes"]) - 1})  # unique: Godot renames duplicates, and set_lods matches lod0*/lod1*
            node["children"].append(len(g["nodes"]) - 1)
    for n in g["nodes"]:
        if not n.get("children"):
            n.pop("children", None)
    w.write(str(path))
    return [{nm: mdl.nodes[nm]["b"].stats() for nm in mdl.order} for mdl in models]


def settle(m, names, floor=0.2):
    """Drop (or raise) the hand-posed wreck parts together until the lowest vertex of the group sits at y = floor."""
    ys = [np.vstack(v["P"])[:, 1].min() for nm in names for v in m.nodes[nm]["b"].s.values()]
    dy = floor - min(ys)
    for nm in names:
        for v in m.nodes[nm]["b"].s.values():
            for P in v["P"]:
                P[:, 1] += dy


def world_bounds(model):
    """Union of every node's vertices in the root frame (a node built with M has them in world already)."""
    Ps = [np.vstack([p for s in n["b"].s.values() for p in s["P"]]) for n in model.nodes.values() if n["b"].s]
    P = np.vstack(Ps)
    return P.min(0), P.max(0)


# ===================================================================================================== geometry helpers
def pg(n, r, ph=0.0):
    return [(r * math.cos(ph + TAU * i / n), r * math.sin(ph + TAU * i / n)) for i in range(n)]


def _ear_clip(poly):
    """Triangulate a simple 2D polygon: indices (i, j, k) into poly."""
    p = np.asarray(poly, float); n = len(p)
    idx = list(range(n))
    area = sum(p[i][0] * p[(i + 1) % n][1] - p[(i + 1) % n][0] * p[i][1] for i in range(n))
    if area < 0:
        idx.reverse()
    cross = lambda a, b, c: (p[b][0] - p[a][0]) * (p[c][1] - p[a][1]) - (p[b][1] - p[a][1]) * (p[c][0] - p[a][0])
    def inside(q, a, b, c):
        return cross(a, b, q) >= -1e-9 and cross(b, c, q) >= -1e-9 and cross(c, a, q) >= -1e-9
    tris = []
    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        for k in range(len(idx)):
            a, b, c = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            if cross(a, b, c) <= 1e-9:
                continue
            if any(inside(o, a, b, c) for o in idx if o not in (a, b, c)):
                continue
            tris.append((a, b, c)); idx.pop(k)
            break
        else:
            break
    if len(idx) == 3:
        tris.append(tuple(idx))
    return tris


def prism(b, mat, poly, w0, w1, poly1=None, axis="y", cap_top=True, cap_bot=False, col=(0, 0, 0), band=0):
    """Flat-shaded prism over a simple (possibly concave) outline. poly in the plane perpendicular to `axis`: y -> (x, z);
    x -> (z, y); z -> (x, y). poly1 (same length) is the far end's outline for a taper (battered walls, sloped roofs)."""
    poly = np.asarray(poly, float)
    p1 = poly if poly1 is None else np.asarray(poly1, float)
    n = len(poly)
    if axis == "y":
        mp = lambda u, v, w: np.array([u, w, v])
    elif axis == "x":
        mp = lambda u, v, w: np.array([w, v, u])
    else:
        mp = lambda u, v, w: np.array([u, v, w])
    sgn = 1.0 if sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n)) > 0 else -1.0
    dist = 0.0
    for i in range(n):
        j = (i + 1) % n
        P = np.array([mp(*poly[i], w0), mp(*poly[j], w0), mp(*p1[j], w1), mp(*p1[i], w1)])
        e = poly[j] - poly[i]
        out2 = np.array([e[1], -e[0]]) * sgn  # outward in the 2D plane
        out3 = mp(out2[0], out2[1], 0.0) - mp(0, 0, 0.0)
        nr = np.cross(P[1] - P[0], P[3] - P[0])
        if np.linalg.norm(nr) < 1e-9:
            nr = np.cross(P[2] - P[1], P[3] - P[1])
        if np.dot(nr, out3) < 0:
            nr = -nr
        nr = unit(nr)
        L = float(np.linalg.norm(P[1] - P[0])); H = float(np.linalg.norm(P[3] - P[0]))
        if L < 1e-6:
            continue
        b.add(mat, P, np.tile(nr, (4, 1)), [(dist, 0), (dist + L, 0), (dist + L, H), (dist, H)], [(0, 1, 2), (0, 2, 3)], band, col)
        dist += L
    tr = _ear_clip(poly)
    for pl, w, up in ((p1, w1, True), (poly, w0, False)):
        if (up and not cap_top) or (not up and not cap_bot):
            continue
        P = np.array([mp(*q, w) for q in pl])
        nrm = mp(0, 0, 1.0 if up else -1.0)
        U = np.array([(q[0], q[1]) for q in pl])
        b.add(mat, P, np.tile(nrm, (n, 1)), U, tr, band, col)


def slab(b, mat, x0, x1, y0, y1, z0, z1, col=(0, 0, 0), skip=()):
    b.box(mat, ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), (x1 - x0, y1 - y0, z1 - z0), col=col, skip=skip)


def decal(b, cell, p, u_ax, v_ax, w, h, normal):
    b.quad("decal", np.asarray(p, float), np.asarray(u_ax, float), np.asarray(v_ax, float), w, h, cell_uv(cell), normal=normal)


def win(b, p, tangent, w, h, normal, off=0.04, mat="wglass"):
    """A dark window quad on a wall, p the wall point at its centre."""
    n = unit(normal)
    b.quad(mat, np.asarray(p, float) + n * off, tangent, (0, 1, 0), w, h, (0, 0, 1, 1), normal=n)


def edges(poly):
    """(a, b, outward normal) for each edge of a simple xz polygon (outward from the signed area)."""
    p = np.asarray(poly, float); n = len(p)
    sgn = 1.0 if sum(p[i][0] * p[(i + 1) % n][1] - p[(i + 1) % n][0] * p[i][1] for i in range(n)) > 0 else -1.0
    out = []
    for i in range(n):
        a, b2 = p[i], p[(i + 1) % n]
        t = (b2 - a) / (np.linalg.norm(b2 - a) + 1e-12)
        out.append((a, b2, np.array([t[1], -t[0]]) * sgn))
    return out


def walls(c, b, mat, poly, y0, y1, state, rng, torn=(), ridge=(0.3, 0.7), cell=None, skip=(), col=(0, 0, 0)):
    """Vertical walls over a convex outline, one planar panel per edge (exactly clipped when torn). In the destroyed state every
    wall has a jagged top at ridge*height; in the damaged state the walls named in `torn` have a ragged breach."""
    cell = cell or (0.45 if c.fine else 1.2)
    h = y1 - y0
    for i, (a, b2, n) in enumerate(edges(poly)):
        if i in skip:
            continue
        L = float(np.linalg.norm(b2 - a))
        p0 = np.array([a[0], y0, a[1]]); d = np.array([b2[0] - a[0], 0, b2[1] - a[1]]) / L
        nn = np.array([n[0], 0, n[1]])
        if state == "intact" or (state == "damaged" and i not in torn):
            keep = None
        elif state == "destroyed":
            keep = torn_keep("destroyed", L, h, rng, ridge_lo=ridge[0], ridge_hi=ridge[1])
        else:
            keep = torn_keep("damaged", L, h, rng, centre=(0.5, 0.5), size=(0.34, 0.3), ph=float(i))
        panel(_Shim(b), mat, p0, d, L, (0, 1, 0), h, nn, keep=keep, thick=0.14 if keep else 0.0, cell=cell,
              disp=jag_disp(h) if keep else None, col=col)


def rubble(b, rng, n, cx, cz, r, y, size=(0.5, 1.4), mat="concrete"):
    for _ in range(n):
        a = rng.random() * TAU; d = r * math.sqrt(rng.random())
        s = size[0] + (size[1] - size[0]) * rng.random()
        Rm = axis_angle(rng.normal(size=3), rng.random() * 2.2)
        b.box(mat, (cx + d * math.cos(a), y + s * 0.4, cz + d * math.sin(a)), (s, s * (0.35 + 0.4 * rng.random()), s * (0.6 + 0.6 * rng.random())), Rm)


# ===================================================================================================== pedestal (Base)
def pedestal(m: Model, c: Ctx, state, ap=2.3, H=4.0):
    """The armoured emplacement under a turret, 4.6 m square by 4 m like the original's Base: a concrete plinth, an octagonal
    body of panels, a steel collar and the slew ring the turret sits on."""
    b = m.node("Base")
    fine = c.fine
    ph = math.pi / 8
    a_body = ap - 0.15
    oct_b = pg(8, ap / math.cos(ph), ph)
    oct_in = pg(8, a_body / math.cos(ph), ph)
    prism(b, "concrete_dark", oct_b, 0.0, 0.5, cap_top=True)
    walls(c, b, "concrete", oct_in, 0.5, 3.2, state, c.rng, torn=(1, 2), ridge=(0.35, 0.8))
    if state != "destroyed":
        prism(b, "interior", pg(8, 1.9 / math.cos(ph), ph), 0.5, 3.2, cap_top=False)  # seen through a breach
        prism(b, "tankgrey", pg(8, 2.25 / math.cos(ph), ph), 3.2, 3.6, cap_top=True)
        b.revolve("steel", [(1.75, 3.6), (1.75, 3.85), (1.6, 4.0)], 40 if fine else 20, uref=1.0)
        b.disc("steel", (0, 4.0, 0), 1.6, seg=40 if fine else 20)
        if fine:
            for k in range(12):  # slew-ring bolts
                th = TAU * k / 12
                b.tube("galv", (1.68 * math.cos(th), 3.85, 1.68 * math.sin(th)), (1.68 * math.cos(th), 3.93, 1.68 * math.sin(th)), 0.05, 6)
            # access hatch (a dark recessed door) and an ID plate on the +z flank, hazard corners on the plinth
            win(b, (0.0, 1.7, a_body), (1, 0, 0), 1.05, 1.8, (0, 0, 1), off=0.03, mat="steel")
            win(b, (0.0, 1.7, a_body), (1, 0, 0), 0.8, 1.5, (0, 0, 1), off=0.06, mat="roofdark")
            decal(b, "id_plate", (1.1, 2.5, a_body + 0.03), (1, 0, 0), (0, 1, 0), 0.7, 0.35, (0, 0, 1))
            decal(b, "stripe_corner", (-1.3, 0.75, ap + 0.01), (1, 0, 0), (0, 1, 0), 1.0, 0.5, (0, 0, 1))
    else:
        b.disc("interior", (0, 1.6, 0), 1.9, seg=8 if not fine else 12)
        rubble(b, c.rng, 10 if fine else 5, 0.3, 0.2, 1.7, 0.5)
        for (x, z, s) in ((-1.9, -1.6, 1.1), (2.0, 1.2, 0.9), (0.6, -2.4, 0.8)):  # collapsed collar / slew ring chunks
            b.box("tankgrey", (x, 0.7, z), (s, 0.5, s * 0.8), axis_angle((0.1, 1, 0.2), x))
    return b


# ===================================================================================================== gun heads
def turntable(t, seg, r=1.9):
    t.revolve("steel", [(r, 0.0), (r, 0.3), (r - 0.2, 0.4)], seg, uref=1.0)
    t.disc("steel", (0, 0.4, 0), r - 0.2, seg=seg)


def halo(b, kind, p):
    """An additive camera-facing glow quad at p (node frame): four near-coincident points, UV = the corner; the shader pushes the corners out in view space
    (shaders/building_v3_halo.gdshader). Dim by day, full at night (BuildingV3.set_night). Intact weapons only: a damaged or destroyed one has no halo."""
    p = np.asarray(p, float)
    P = np.array([p + (-0.01, -0.01, 0), p + (0.01, -0.01, 0), p + (0.01, 0.01, 0), p + (-0.01, 0.01, 0)])
    b.add("halo_" + kind, P, np.tile((0, 0, 1.0), (4, 1)), np.array([(0, 0), (1, 0), (1, 1), (0, 1)]), [(0, 1, 2), (0, 2, 3)])


def tube_mouths(g, cx, cy, zf, pw, ph, pattern, r=0.17, fine=True, skip=lambda x, y: False):
    """Dark tube mouths with a galv rim on a panel face at z = zf. pattern: normalised (-0.5..0.5) panel positions."""
    for ux, uy in pattern:
        x, y = cx + ux * pw, cy + uy * ph
        if skip(x, y):
            continue
        g.disc("galv", (x, y, zf + 0.012), r + 0.07, (0, 0, 1), seg=10 if fine else 6, r_in=r - 0.02)
        g.disc("roofdark", (x, y, zf + 0.006), r, (0, 0, 1), seg=10 if fine else 6)


QUINCUNX = [(-0.27, -0.27), (0.27, -0.27), (0.0, 0.0), (-0.27, 0.27), (0.27, 0.27)]
GRID23 = [(sx * 0.25, (k - 1) * 0.3) for sx in (-1, 1) for k in range(3)]


def rack(c, g, x0, x1, yc, hh, z0, z1, zf, flare, pattern, hit=False, sx=1, body="whitecity", r=0.17):
    """A launcher rack as the originals have them: a tall box with a flared front plate carrying two stacked panels of tube mouths."""
    fine = c.fine
    xm = (x0 + x1) / 2
    skip = ("+x",) if hit and sx > 0 else (("-x",) if hit else ())
    g.box(body, (xm, yc, (z0 + z1) / 2), (x1 - x0, 2 * hh, z1 - z0), skip=skip)
    prism(g, body, [(x0, yc - hh), (x1, yc - hh), (x1, yc + hh), (x0, yc + hh)], z1, zf,
          [(x0, yc - hh - flare), (x1, yc - hh - flare), (x1, yc + hh + flare), (x0, yc + hh + flare)], axis="z", cap_top=True, cap_bot=False)
    if hit:  # the outer wall torn open: ragged panel over a dark inside
        xo = x1 if sx > 0 else x0
        keep = torn_keep("damaged", z1 - z0, 2 * hh, c.rng, centre=(0.6, 0.55), size=(0.4, 0.34))
        panel(_Shim(g), body, np.array([xo, yc - hh, z0]), (0, 0, 1), z1 - z0, (0, 1, 0), 2 * hh, (sx, 0, 0), keep=keep, thick=0.1,
              cell=0.3 if fine else 0.7, disp=jag_disp(2 * hh))
        g.box("roofdark", (xm - sx * 0.3, yc, (z0 + z1) / 2), (0.3, 2 * hh * 0.9, (z1 - z0) * 0.9))
    ph = hh + flare
    for sy in (-1, 1):
        cy = yc + sy * ph / 2
        tube_mouths(g, xm, cy, zf, x1 - x0, ph * 0.85, pattern, r, fine, skip=(lambda x, y: hit and sy > 0 and abs(x - (x1 if sx > 0 else x0)) < 0.5))
    g.box("steel", (xm, yc, zf - 0.02), (x1 - x0 + 0.06, 0.1, 0.06))  # the seam between the two panels
    if fine:
        for zz in (z0 + 0.7, z0 + 2.2):  # orange hazard bands round the rack
            g.box("bandorange", (xm, yc, zz), (x1 - x0 + 0.08, 2 * hh + 0.08, 0.45))
        decal(g, "stripe_corner", (xm, yc + hh + 0.075, z1 - 0.6), (1, 0, 0), (0, 0, 1), 0.9, 0.5, (0, 1, 0))


def head_mac(m, c, state, parent=None, t=(0.0, 4.0, 0.0)):
    fine = c.fine
    tb = m.node("Turret", parent, t=t)
    g = m.node("Gun", "Turret", t=(0.0, 1.97, 2.2))
    seg = 40 if fine else 18
    turntable(tb, seg, 1.9)
    prof = [(-2.0, 0.35), (2.1, 0.35), (2.6, 1.2), (2.3, 2.0), (1.2, 2.8), (-1.2, 2.8), (-2.0, 2.3)]  # (z, y)
    prism(tb, "tankgrey", prof, -1.15, 1.15, axis="x", cap_top=True, cap_bot=True)
    for sx in (-1, 1):  # side skirts (flank armour) with raised ribs
        slab(tb, "machgrey", 1.15 if sx > 0 else -1.3, 1.3 if sx > 0 else -1.15, 0.5, 2.0, -1.8, 1.9)
        if fine:
            for k in range(5):
                slab(tb, "steel", 1.25 if sx > 0 else -1.35, 1.35 if sx > 0 else -1.25, 0.55, 1.95, -1.6 + 0.8 * k, -1.5 + 0.8 * k)
    slab(tb, "machgrey", -0.95, 0.95, 0.7, 2.2, -3.7, -1.9)  # rear bustle: the ammunition box
    if fine:
        for k in range(3):
            slab(tb, "steel", -1.0, 1.0, 0.7, 2.2, -3.4 + 0.6 * k, -3.3 + 0.6 * k)
        decal(tb, "id_plate", (0.0, 1.5, -3.71), (1, 0, 0), (0, 1, 0), 0.7, 0.35, (0, 0, -1))
        decal(tb, "arrow", (0.0, 2.82, 0.6), (1, 0, 0), (0, 0, 1), 0.7, 0.7, (0, 1, 0))
        slab(tb, "galv", -0.9, -0.2, 2.76, 2.8, -1.2, -0.3)
    tb.revolve("steel", [(0.5, 2.62), (0.5, 2.72), (0.38, 2.8)], 14, cx=0.7, cz=-0.9, uref=1.0)
    tb.disc("steel", (0.7, 2.8, -0.9), 0.38, seg=14)
    slab(g, "steel", -1.1, 1.1, -0.75, 0.55, 0.0, 0.6)  # mantlet
    for x, side in ((-0.62, "L"), (0.62, "R")):
        broken = state == "damaged" and side == "R"
        g.tube("steel", (x, 0.0, 0.5), (x, 0.0, 3.0), 0.38, 14 if fine else 8)
        if not broken:
            g.tube("steel", (x, 0.0, 3.0), (x, 0.0, 5.4), 0.21, 12 if fine else 6)
            g.tube("steel", (x, 0.0, 5.1), (x, 0.0, 5.8), 0.32, 12 if fine else 6)
            g.disc("roofdark", (x, 0.0, 5.801), 0.16, (0, 0, 1), seg=10 if fine else 6)
            if fine:
                for zz in (1.2, 2.2):
                    g.tube("galv", (x, 0.0, zz), (x, 0.0, zz + 0.18), 0.44, 14)
                slab(g, "paint", x - 0.25, x + 0.25, 0.34, 0.85, 0.2, 1.3)
                g.tube("galv", (x, 0.0, 3.0), (x, 0.0, 3.4), 0.3, 10)
        else:
            g.sweep("steel", [(x, 0.0, 3.0), (x + 0.1, -0.15, 3.5), (x + 0.3, -0.5, 3.9)], 0.3, 10 if fine else 6)
            g.disc("rust", (x + 0.3, -0.5, 3.9), 0.28, (0.3, -0.5, 0.8), seg=9)


def head_lrm(m, c, state, parent=None, t=(0.0, 4.0, 0.0)):
    """Two tall racks, each a 1.25 x 2.83 m box 4.2 m long with a front plate that flares to 4.3 m (read off the original's
    vertices), two stacked panels of five tubes per rack: 20 tubes. The racks are the Gun node (they pitch)."""
    fine = c.fine
    tb = m.node("Turret", parent, t=t)
    g = m.node("Gun", "Turret", t=(0.0, 2.4, 0.2))
    turntable(tb, 40 if fine else 18, 1.9)
    prof = [(-1.9, 0.4), (1.5, 0.4), (1.5, 2.0), (0.6, 2.95), (-1.3, 2.95), (-1.9, 2.2)]
    prism(tb, "tankgrey", prof, -0.84, 0.84, axis="x", cap_top=True, cap_bot=True)
    tb.revolve("steel", [(0.5, 2.95), (0.5, 3.05), (0.4, 3.3)], 14, cz=-0.6, uref=1.0)
    tb.disc("steel", (0, 3.3, -0.6), 0.4, seg=14)
    if fine:
        decal(tb, "id_plate", (0.0, 2.97, 0.4), (1, 0, 0), (0, 0, 1), 0.6, 0.35, (0, 1, 0))
    for sx in (-1, 1):
        x0, x1 = (0.84, 2.09) if sx > 0 else (-2.09, -0.84)
        rack(c, g, x0, x1, 0.0, 1.415, -2.18, 1.99, 3.04, 0.74, QUINCUNX, hit=(state == "damaged" and sx > 0), sx=sx)


def head_srm(m, c, state, parent=None, t=(0.0, 4.0, 0.0)):
    fine = c.fine
    tb = m.node("Turret", parent, t=t)
    g = m.node("Gun", "Turret", t=(0.0, 2.15, 0.1))
    turntable(tb, 40 if fine else 18, 1.9)
    prof = [(-1.3, 0.4), (1.3, 0.4), (1.3, 1.9), (0.5, 2.5), (-1.0, 2.5), (-1.3, 2.0)]
    prism(tb, "tankgrey", prof, -1.25, 1.25, axis="x", cap_top=True, cap_bot=True)
    tb.revolve("steel", [(0.45, 2.5), (0.45, 2.6), (0.35, 2.85)], 14, cz=-0.4, uref=1.0)
    tb.disc("steel", (0, 2.85, -0.4), 0.35, seg=14)
    for sx in (-1, 1):
        x0, x1 = (1.2, 3.1) if sx > 0 else (-3.1, -1.2)
        rack(c, g, x0, x1, 0.0, 1.5, -1.4, 1.2, 1.55, 0.2, GRID23, hit=(state == "damaged" and sx > 0), sx=sx, r=0.15)


def head_pulse(m, c, state, parent=None, t=(0.0, 4.0, 0.0)):
    """Twin pulse lasers as the original: a green-capped hull, two white sleeves open on top over a glowing green core, and pointed
    white lens tips. The core and lens are `bandgreen` / `wglass` (no emissive set exists for weapon ports yet: green by day, the
    lens lights with the night windows)."""
    fine = c.fine
    tb = m.node("Turret", parent, t=t)
    g = m.node("Gun", "Turret", t=(0.0, 1.3, 1.8))
    turntable(tb, 36 if fine else 16, 1.6)
    prof = [(-3.0, 0.4), (2.2, 0.4), (2.2, 1.6), (0.8, 2.2), (-2.0, 2.2), (-3.0, 1.5)]
    prism(tb, "tankgrey", prof, -1.1, 1.1, axis="x", cap_top=True, cap_bot=True)
    prism(tb, "bandgreen", [(-2.9, 1.5), (-2.0, 2.22), (0.8, 2.22), (2.1, 1.62), (2.1, 1.3), (-2.9, 1.3)], -1.12, 1.12, axis="x", cap_top=True, cap_bot=True)
    slab(tb, "whitecity", -1.4, -1.1, 0.5, 1.6, -2.4, 1.5); slab(tb, "whitecity", 1.1, 1.4, 0.5, 1.6, -2.4, 1.5)
    if fine:
        for k in range(3):
            slab(tb, "steel", -0.9, 0.9, 2.2, 2.28, -2.6 + 0.35 * k, -2.45 + 0.35 * k)  # vents on the roof
    slab(g, "steel", -1.45, 1.45, -0.7, 0.7, 0.0, 0.5)
    for sx in (-1, 1):
        x = sx * 0.85
        broken = state == "damaged" and sx > 0
        L = 2.6 if broken else 4.6
        # the open sleeve: two white rails and a floor, the green core lying in it
        for ex in (-0.34, 0.34):
            g.box("whitecity", (x + ex, 0.1, 0.5 + L / 2), (0.14, 0.55, L))
        g.box("whitecity", (x, -0.2, 0.5 + L / 2), (0.82, 0.16, L))
        g.tube("bandgreen" if broken or state == "damaged" else "lamp_laser_dim", (x, 0.02, 0.5), (x, 0.02, 0.5 + L), 0.26, 12 if fine else 6)     # the core glows (dim emissive); a hit one is dead
        if fine:
            for k in range(4):
                g.box("steel", (x, 0.16, 0.9 + k * (L - 0.6) / 3), (0.9, 0.62, 0.12))
        if broken:
            g.sweep("whitecity", [(x, 0, 0.5 + L), (x + 0.1, -0.2, 0.5 + L + 0.5), (x + 0.3, -0.55, 0.5 + L + 0.9)], 0.3, 8)
            g.disc("rust", (x + 0.3, -0.55, 0.5 + L + 0.9), 0.28, (0.3, -0.55, 0.8), seg=9)
            continue
        z = 0.5 + L
        for k, r in enumerate((0.42, 0.34, 0.24, 0.13, 0.04)):  # the pointed lens tip; its third ring is the emitter lens (emissive, with a halo while intact)
            lens = "lamp_laser" if state != "damaged" else "lamp_laser_dim"
            g.tube(lens if k == 2 else "whitecity", (x, 0.0, z + 0.34 * k), (x, 0.0, z + 0.34 * (k + 1) + 0.02), r, 12 if fine else 6)
        if state != "damaged":
            halo(g, "laser", (x, 0.0, z + 0.34 * 2.6))
        g.disc("wglass", (x, 0.0, z + 0.02), 0.3, (0, 0, -1), seg=12 if fine else 6)


def head_gauss(m, c, state, parent=None, t=(0.0, 4.0, 0.0)):
    """Gauss rifle as the original: a hexagonal sensor column with a cyan cap, a big upright hexagonal coil plate with a glowing cyan
    core standing off to the +x side (the turret is off-centre), and a long white barrel rising across the front."""
    fine = c.fine
    tb = m.node("Turret", parent, t=t)
    g = m.node("Gun", "Turret", t=(0.2, 2.0, 0.4))
    g.M = (axis_angle((1, 0, 0), -0.25), g.M[1])
    turntable(tb, 40 if fine else 18, 1.9)
    prof = [(-2.4, 0.4), (1.9, 0.4), (1.9, 2.0), (0.6, 2.5), (-1.6, 2.5), (-2.4, 1.8)]
    prism(tb, "tealwall", prof, -1.2, 1.2, axis="x", cap_top=True, cap_bot=True)
    # sensor column
    prism(tb, "palecorr", pg(6, 0.8, 0.0), 2.4, 4.0, [(0.7 * x, 0.7 * y) for x, y in pg(6, 0.8, 0.0)], cap_top=True)
    tb.revolve("facadeblue", [(0.7, 4.0), (0.62, 4.18), (0.2, 4.3)], 12, uref=1.0)
    tb.disc("wglass", (0, 4.3, 0), 0.22, seg=12)
    # the coil plate, upright, normal along +x, centred at y 2.6, z 0.2 (cracked and dull when damaged)
    dish_x = 1.95
    hexp = lambda r, yc=2.6, zc=0.2: [(zc + q[0], yc + q[1]) for q in pg(6, r, math.pi / 6)]
    prism(tb, "tealwall", hexp(1.75), dish_x, dish_x + 0.4, axis="x", cap_top=True, cap_bot=True)
    prism(tb, "facadeblue" if state != "damaged" else "rust", hexp(1.2), dish_x + 0.4, dish_x + 0.46, axis="x", cap_top=True, cap_bot=False)
    if state != "damaged":      # the coil core glows cyan (dim emissive, a lamp-set material)
        prism(tb, "lamp_gauss_dim", hexp(0.7), dish_x + 0.46, dish_x + 0.5, axis="x", cap_top=True, cap_bot=False)
    else:                       # cracked: a small dead-dim patch of the core still lit
        prism(tb, "lamp_gauss_dim", hexp(0.32, 2.35, 0.45), dish_x + 0.46, dish_x + 0.49, axis="x", cap_top=True, cap_bot=False)
    if fine:
        for k in range(6):  # bolts round the rim
            a = math.pi / 6 + TAU * k / 6
            tb.tube("steel", (dish_x + 0.4, 2.6 + 1.5 * math.sin(a), 0.2 + 1.5 * math.cos(a)), (dish_x + 0.5, 2.6 + 1.5 * math.sin(a), 0.2 + 1.5 * math.cos(a)), 0.07, 6)
    # the barrel: white sleeve, cyan coil rings, a cyan muzzle ring
    broken = state == "damaged"
    L = 3.6 if broken else 6.0
    g.tube("whitecity", (0, 0, 0.0), (0, 0, L), 0.42, 14 if fine else 8)
    g.tube("steel", (0, 0, -0.8), (0, 0, 0.2), 0.55, 12 if fine else 8)
    for z in ((1.0, 2.2, 3.4, 4.6) if not broken else (1.0, 2.2)):
        g.tube("facadeblue", (0, 0, z), (0, 0, z + 0.22), 0.52, 14 if fine else 8)
    if not broken:
        g.tube("facadeblue", (0, 0, L - 0.1), (0, 0, L + 0.25), 0.5, 14 if fine else 8)
        g.disc("lamp_gauss", (0, 0, L + 0.26), 0.3, (0, 0, 1), seg=12 if fine else 6)      # the muzzle lens: emissive, with a halo
        halo(g, "gauss", (0, 0, L + 0.3))
    else:
        g.disc("rust", (0, 0, L), 0.4, (0, 0, 1), seg=9)


def head_longtom(m, c, state, parent=None, t=(0.0, 4.0, 0.0)):
    """Long Tom: a heavy cradle and one very long barrel, elevated 12.5 degrees at rest; the Gun node carries the barrel."""
    fine = c.fine
    tb = m.node("Turret", parent, t=t)
    g = m.node("Gun", "Turret", t=(0.0, 2.4, -1.0))
    g.M = (axis_angle((1, 0, 0), -0.22), g.M[1])
    turntable(tb, 40 if fine else 18, 1.9)
    prof = [(-2.6, 0.4), (1.2, 0.4), (1.2, 2.2), (0.2, 2.8), (-1.8, 2.8), (-2.6, 2.0)]
    prism(tb, "tankgrey", prof, -1.4, 1.4, axis="x", cap_top=True, cap_bot=True)
    for sx in (-1, 1):
        slab(tb, "steel", sx * 1.0 - 0.2, sx * 1.0 + 0.2, 2.2, 3.4, -1.4, 0.2)  # trunnion cheeks
    seg = 18 if fine else 8
    broken = state == "damaged"
    g.tube("steel", (0, 0, -1.2), (0, 0, 3.0), 0.62, seg)  # recoil housing
    g.tube("galv", (0, 0, 3.0), (0, 0, 13.6 if not broken else 7.0), 0.42, seg)
    if not broken:
        g.tube("steel", (0, 0, 12.9), (0, 0, 14.4), 0.62, seg)  # muzzle brake
        g.disc("roofdark", (0, 0, 14.401), 0.3, (0, 0, 1), seg=12 if fine else 6)
        if fine:
            for k in range(4):
                g.tube("machgrey", (0, 0, 4.0 + 2.2 * k), (0, 0, 4.25 + 2.2 * k), 0.52, 14)
    else:
        g.sweep("galv", [(0, 0, 7.0), (0.1, -0.3, 8.2), (0.2, -0.9, 9.2)], 0.4, 8)
        g.disc("rust", (0.2, -0.9, 9.2), 0.38, (0.2, -0.9, 1.0), seg=9)


HEADS = {"mac": head_mac, "lrm": head_lrm, "srm": head_srm, "pulse": head_pulse, "gauss": head_gauss, "longtom": head_longtom}


# ===================================================================================================== wrecks of a head
def _frag(m, name, Rm, pos):
    b = m.node(name, world=False)
    b.M = (Rm, np.asarray(pos, float))
    return b


def wreck_head(m, c, kind, pos=(2.4, 1.0, 0.8), yaw=0.6, sink=0.3):
    """The head thrown off its ring and collapsed: a hull with its roof peeled back, the weapon torn into fragments. Everything
    is charred through (Model.node), no moving nodes. Fragments are placed in the root frame and settled onto the rubble."""
    rng = c.rng
    Rm = axis_angle((0.3, 0.1, 1.0), 1.15) @ axis_angle((0, 1, 0), yaw)
    t = _frag(m, "Turret", Rm, pos)
    prof = {"mac": [(-2.0, 0.35), (2.1, 0.35), (2.6, 1.2), (2.3, 1.5), (-2.0, 1.5)],
            "lrm": [(-1.9, 0.4), (1.5, 0.4), (1.5, 1.4), (-1.9, 1.4)],
            "srm": [(-1.3, 0.4), (1.3, 0.4), (1.3, 1.3), (-1.3, 1.3)],
            "pulse": [(-3.0, 0.4), (2.2, 0.4), (2.2, 1.2), (-3.0, 1.2)],
            "gauss": [(-4.8, 0.4), (1.5, 0.4), (1.5, 1.4), (-4.8, 1.4)],
            "longtom": [(-2.6, 0.4), (1.2, 0.4), (1.2, 1.4), (-2.6, 1.4)]}[kind]
    hw = {"mac": 1.15, "lrm": 0.84, "srm": 1.25, "pulse": 1.1, "gauss": 1.2, "longtom": 1.4}[kind]
    prism(t, "tankgrey", prof, -hw, hw, axis="x", cap_top=True, cap_bot=True)
    # the peeled roof: a bent plate hanging off one side, the ragged top of the hull
    roof = _frag(m, "Roof", axis_angle((0.2, 0.3, 1.0), 0.7) @ axis_angle((0, 1, 0), yaw + 1.0), (pos[0] - 1.4, pos[1] + 0.9, pos[2] + 2.2))
    roof.box("tankgrey", (0, 0, 0), (2.0, 0.18, 2.6))
    roof.box("rust", (0, -0.1, 0), (1.6, 0.05, 2.2))
    # weapon fragments
    k = 0
    def part(pos_, ang, axis=(0.3, 1, 0.1)):
        nonlocal k
        k += 1
        return _frag(m, f"Gun_{k}", axis_angle(axis, ang), pos_)
    if kind == "mac":
        g = part((pos[0] - 2.2, 0.6, pos[2] + 3.5), 0.5); g.tube("steel", (0, 0, 0), (0, 0, 3.4), 0.38, 10); g.tube("steel", (0, 0, 3.4), (0, 0, 5.2), 0.21, 8)
        g = part((pos[0] + 0.5, 0.5, pos[2] + 4.8), 2.0); g.tube("steel", (0, 0, 0), (0, 0, 2.2), 0.38, 10); g.disc("rust", (0, 0, 2.2), 0.36, (0, 0, 1), seg=9)
    elif kind in ("lrm", "srm"):
        w, h, L = (1.25, 2.83, 4.2) if kind == "lrm" else (1.9, 3.0, 2.6)
        g = part((pos[0] - 2.6, h / 2 * 0.5, pos[2] + 2.0), 0.5); g.box("whitecity", (0, 0, 0), (w, h, L)); g.box("roofdark", (0, 0, L / 2), (w * 0.8, h * 0.8, 0.1))
        g = part((pos[0] - 1.0, 0.6, pos[2] - 3.4), 2.3, (1, 0.2, 0.3)); g.box("whitecity", (0, 0, 0), (w, h * 0.6, L * 0.6)); g.box("rust", (0, h * 0.3, 0), (w * 0.9, 0.06, L * 0.5))
    elif kind == "pulse":
        g = part((pos[0] - 2.2, 0.7, pos[2] + 3.0), 0.6); g.tube("steel", (0, 0, 0), (0, 0, 3.0), 0.5, 10); g.tube("galv", (0, 0, 3.0), (0, 0, 4.4), 0.3, 8)
        g = part((pos[0] + 1.0, 0.5, pos[2] + 5.0), 1.9); g.tube("steel", (0, 0, 0), (0, 0, 1.8), 0.5, 10)
    elif kind == "gauss":
        g = part((pos[0] - 2.0, 0.6, pos[2] + 4.0), 0.4); g.box("steel", (0.2, 0, 2.0), (0.34, 0.5, 4.0)); g.box("steel", (-0.2, 0, 2.0), (0.34, 0.5, 4.0)); g.box("galv", (0, 0, 1.2), (1.3, 1.3, 0.4))
    else:
        g = part((pos[0] - 1.2, 0.5, pos[2] + 6.5), 0.3); g.tube("galv", (0, 0, 0), (0, 0, 8.0), 0.42, 10)
        g = part((pos[0] + 1.8, 0.5, pos[2] + 9.5), 2.4); g.tube("galv", (0, 0, 0), (0, 0, 3.4), 0.42, 10); g.disc("rust", (0, 0, 3.4), 0.4, (0, 0, 1), seg=9)
    settle(m, [n for n in m.order if n in ("Turret", "Roof") or n.startswith("Gun_")], sink)


# ===================================================================================================== gun turrets on a pedestal
def make_turret(kind, brs):
    def fn(state, lod, seed):
        c = Ctx(state, lod, seed, breach=brs, ledges=[(6.8, 1.2, 0.4)], ao_rings=[(4.0, 0.5, 0.4)], ground_h=1.5)
        m = Model(c)
        pedestal(m, c, state)
        if state == "destroyed":
            wreck_head(m, c, kind)
        else:
            HEADS[kind](m, c, state)
        return m, None
    return fn


# ===================================================================================================== pop-up emplacements
POP_RISE_M = 8.4  # the original's TurretRoot sits 12.4 m down, its turret 8.4 m below the ground; popped up the turret stands on it


def make_popup(kind, deck_mat, brs=(0.0, 0.5, 0.0, 2.0)):
    """A hatch in the ground with two door leaves (pop_door_l / pop_door_r, hinged at the outer edges) and a lift (`Pop`) that
    carries the Turret (yaw) and Gun (pitch) nodes below ground; ObjectsView.set_turret_pop raises it (POP_RISE_M)."""
    def fn(state, lod, seed):
        c = Ctx(state, lod, seed, breach=brs, ledges=[(0.6, 0.8, 0.3)], ao_rings=[(0.0, 0.6, 0.3)], ground_h=0.8)
        m = Model(c)
        fine = c.fine
        dead = state == "destroyed"
        b = m.node("Base")
        # a low armoured hatch: a pad with a steel frame, two near-flush dark door leaves with hazard edges (opening x +-3.6, z +-2.2)
        door_mat = "steel" if deck_mat == "concrete" else deck_mat
        pad_mat = "concrete_dark" if deck_mat == "concrete" else deck_mat
        for sz in (-1, 1):
            slab(b, pad_mat, -3.6, 3.6, -0.1, 0.12, sz * 2.2 if sz > 0 else -4.2, 4.2 if sz > 0 else -2.2)
        slab(b, "concrete_dark", -3.6, -3.35, -2.0, 0.0, -2.2, 2.2); slab(b, "concrete_dark", 3.35, 3.6, -2.0, 0.0, -2.2, 2.2)
        slab(b, "concrete_dark", -3.6, 3.6, -2.0, 0.0, -2.2, -1.95); slab(b, "concrete_dark", -3.6, 3.6, -2.0, 0.0, 1.95, 2.2)
        b.box("roofdark", (0, -1.95, 0), (7.2, 0.05, 4.4))
        if not dead:
            for sz in (-1, 1):  # the frame round the opening and its hazard strip
                slab(b, "steel", -3.6, 3.6, 0.1, 0.17, sz * 2.2 - 0.18 if sz > 0 else -2.2, sz * 2.2 + 0.0 if sz > 0 else -2.2 + 0.18)
            slab(b, "steel", -3.6, -3.4, 0.1, 0.17, -2.2, 2.2); slab(b, "steel", 3.4, 3.6, 0.1, 0.17, -2.2, 2.2)
            if fine:
                for sz in (-1, 1):
                    decal(b, "stripe_corner", (-2.0, 0.125, sz * 2.9), (1, 0, 0), (0, 0, 1), 1.6, 0.6, (0, 1, 0))
                    decal(b, "stripe_corner", (2.0, 0.125, sz * 2.9), (-1, 0, 0), (0, 0, 1), 1.6, 0.6, (0, 1, 0))
                decal(b, "id_plate", (3.0, 0.125, -3.6), (1, 0, 0), (0, 0, 1), 0.8, 0.45, (0, 1, 0))
        if dead:
            rubble(b, c.rng, 8 if fine else 4, 0.0, 3.2, 2.6, 0.2, (0.5, 1.2))
            rubble(b, c.rng, 6 if fine else 3, 0.0, -3.2, 2.6, 0.2, (0.5, 1.2))
            wreck_head(m, c, kind, pos=(1.0, -0.8, 0.0), yaw=0.4, sink=-1.5)
            door = _frag(m, "pop_door_r", axis_angle((0.1, 1, 0.3), 0.9) @ axis_angle((1, 0, 0), 1.1), (4.8, 0.7, 1.5))
            door.box(door_mat, (0, 0, 0), (3.6, 0.25, 4.4)); door.box("rust", (0, -0.13, 0), (3.2, 0.05, 4.0))
            return m, None
        for nm, sx in (("pop_door_l", -1), ("pop_door_r", 1)):
            d = m.node(nm, t=(sx * 3.6, 0.12, 0.0))
            x0, x1 = (0.0, 3.6) if sx < 0 else (-3.6, 0.0)
            xi = x1 if sx < 0 else x0  # the inner edge, at the seam
            hit = state == "damaged" and sx > 0
            if hit:
                keep = torn_keep("damaged", 3.6, 4.4, c.rng, centre=(0.35, 0.5), size=(0.34, 0.3))
                panel(_Shim(d), door_mat, np.array([x0, 0.08, -2.2]), (1, 0, 0), 3.6, (0, 0, 1), 4.4, (0, 1, 0), keep=keep, thick=0.14, cell=0.3 if fine else 0.8, disp=jag_disp(4.4))
                slab(d, "concrete_dark", x0, x1, -0.12, 0.0, -2.2, 2.2)
            else:
                slab(d, door_mat, x0, x1, -0.12, 0.08, -2.2, 2.2)
                if fine:
                    for k in range(3):  # raised ribs across the leaf
                        slab(d, "machgrey", x0 + 0.15, x1 - 0.15, 0.08, 0.11, -1.6 + 1.6 * k, -1.5 + 1.6 * k)
                    decal(d, "stripe_corner", (xi - (0.45 if sx < 0 else -0.45), 0.085, 0.0), (1, 0, 0), (0, 0, 1), 0.7, 4.0, (0, 1, 0))
        pop = m.node("Pop", t=(0.0, 0.0, 0.0))
        ph = math.pi / 8
        prism(pop, "concrete_dark", pg(8, 2.3 / math.cos(ph), ph), -12.4, -8.4, cap_top=True)
        pop.revolve("steel", [(1.4, -8.4), (1.4, -8.3)], 24 if fine else 12, uref=1.0)
        HEADS[kind](m, c, state, parent="Pop", t=(0.0, -8.4, 0.0))
        return m, None
    return fn


# ===================================================================================================== orbital turret, gun tower
def orbital(state, lod, seed):
    """The orbital defence turret: a square plinth and pedestal (original Base, x -3.7..12.1, z -3.6..12.2, 6.1 m), a big five-sided
    turret and two long tapered barrels. Its Turret node pivots at the pedestal's centre (4.2, 6.4, 4.2)."""
    c = Ctx(state, lod, seed, breach=(4.2, 7.5, 4.2, 3.5), ledges=[(6.1, 1.5, 0.4)], ao_rings=[(3.1, 1.0, 0.4)], ground_h=3.0)
    fine = c.fine
    m = Model(c)
    b = m.node("Base")
    plin0 = [(-3.73, -3.65), (12.14, -3.65), (12.14, 12.22), (-3.73, 12.22)]
    plin1 = [(-2.62, -2.54), (11.02, -2.54), (11.02, 11.11), (-2.62, 11.11)]
    prism(b, "concrete_dark", plin0, 0.0, 3.1, plin1, cap_top=True)
    ped0 = [(-1.2, -1.2), (9.6, -1.2), (9.6, 9.6), (-1.2, 9.6)]
    ped1 = [(-0.4, -0.4), (8.8, -0.4), (8.8, 8.8), (-0.4, 8.8)]
    if state == "destroyed":
        walls(c, b, "concrete", ped0, 3.1, 6.08, state, c.rng, ridge=(0.2, 0.6), cell=1.2)
        rubble(b, c.rng, 14 if fine else 6, 4.2, 4.2, 6.0, 3.1, (0.8, 2.2))
        wreck_head(m, c, "gauss", pos=(7.8, 3.6, 4.0), yaw=0.2, sink=0.4)
        return m, None
    prism(b, "concrete", ped0, 3.1, 6.08, ped1, cap_top=True)
    b.revolve("steel", [(3.6, 6.08), (3.6, 6.36)], 40 if fine else 20, cx=4.2, cz=4.2, uref=1.0)
    b.disc("steel", (4.2, 6.36, 4.2), 3.6, seg=40 if fine else 20)
    if fine:
        for (x, z) in ((-2.6, -2.5), (10.9, -2.5), (10.9, 11.0), (-2.6, 11.0)):
            decal(b, "stripe_corner", (x + (0.9 if x < 0 else -0.9), 3.13, z + (0.9 if z < 0 else -0.9)), (1, 0, 0), (0, 0, 1), 1.4, 1.4, (0, 1, 0))
    tb = m.node("Turret", t=(4.2, 6.4, 4.1))
    g = m.node("Gun", "Turret", t=(0.0, 1.1, 0.7))
    g.M = (axis_angle((1, 0, 0), -0.27), g.M[1])
    prof = [(-4.1, 0.0), (4.2, 0.0), (4.2, 1.4), (2.6, 2.4), (-2.0, 2.4), (-4.1, 1.4)]  # (z, y) five-sided
    prism(tb, "tankgrey", prof, -3.3, 3.3, axis="x", cap_top=True, cap_bot=True)
    if fine:
        slab(tb, "machgrey", -3.5, -3.3, 0.3, 1.8, -3.0, 3.0); slab(tb, "machgrey", 3.3, 3.5, 0.3, 1.8, -3.0, 3.0)
        decal(tb, "arrow", (0.0, 2.42, -0.5), (1, 0, 0), (0, 0, 1), 1.4, 1.4, (0, 1, 0))
        for k in range(3):
            slab(tb, "grate", -1.0 + k * 0.8, -0.6 + k * 0.8, 2.4, 2.5, -3.0, -1.2)
    slab(g, "steel", -3.3, 3.3, -1.0, 1.0, 0.0, 0.8)
    for sx in (-1, 1):
        x = sx * 1.65
        hit = state == "damaged" and sx > 0
        g.tube("steel", (x, 0, 0.7), (x, 0, 3.2), 0.95, 24 if fine else 10)
        L2 = 8.0 if not hit else 5.5
        g.sweep("galv", [(x, 0, 3.2), (x, 0, 3.2 + L2 * 0.5), (x, 0, 3.2 + L2)], 0.9, 24 if fine else 10) if False else g.revolve("galv", [(0.9, 3.2), (0.52, 3.2 + L2)], 24 if fine else 10, cx=0, cz=0, uref=1.0) if False else None
        # a tapered barrel: a cone along +z as stacked tubes
        for k in range(6 if not hit else 4):
            z0 = 3.2 + L2 * k / 6
            g.tube("galv", (x, 0, z0), (x, 0, z0 + L2 / 6 + 0.02), 0.9 - 0.38 * (k + 0.5) / 6, 24 if fine else 10)
        if not hit:
            g.tube("steel", (x, 0, 3.2 + L2 - 0.5), (x, 0, 3.2 + L2 + 0.4), 0.62, 24 if fine else 10)
            g.disc("roofdark", (x, 0, 3.2 + L2 + 0.401), 0.35, (0, 0, 1), seg=16 if fine else 8)
        else:
            g.disc("rust", (x, 0, 3.2 + L2 * 4 / 6 + 0.1), 0.6, (0, 0, 1), seg=12)
    return m, None


def guntower(state, lod, seed):
    """A slim near-black tapering column (original Base: x +-1.9 at the foot, 11.6 m) under a wide square cab with a louvred skirt and a
    flat roof; the gun yaws on the cab (node Turret at y 10.85). The original's barrel points +x at rest, so this one does too."""
    c = Ctx(state, lod, seed, breach=(0.0, 8.0, 1.0, 2.5), ledges=[(9.0, 2.0, 0.4)], ao_rings=[(9.0, 1.0, 0.4)], ground_h=3.0)
    fine = c.fine
    m = Model(c)
    b = m.node("Base")
    foot = [(-1.9, -1.9), (1.9, -1.9), (1.9, 1.9), (-1.9, 1.9)]
    neck = [(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)]
    dead = state == "destroyed"
    if dead:
        prism(b, "slate", foot, 0.0, 3.0, [(-1.6, -1.6), (1.6, -1.6), (1.6, 1.6), (-1.6, 1.6)], cap_top=False)
        walls(c, b, "slate", [(-1.6, -1.6), (1.6, -1.6), (1.6, 1.6), (-1.6, 1.6)], 3.0, 7.0, "destroyed", c.rng, ridge=(0.2, 0.7), cell=0.8 if fine else 2.0)
        rubble(b, c.rng, 10 if fine else 5, 0.0, 0.0, 3.4, 0.2, (0.6, 1.6))
        wreck_head(m, c, "mac", pos=(2.8, 0.8, 0.8), yaw=0.8, sink=0.2)
        return m, None
    # the column: battered from the foot to the neck, near black; a torn flank when damaged
    prism(b, "roofdark", foot, 0.0, 9.0, neck, cap_top=False)
    if fine:
        for sx, sz in ((1, 0), (-1, 0), (0, 1), (0, -1)):  # braces up each face
            mid0 = np.array([sx * 1.9, 0.0, sz * 1.9]); mid1 = np.array([sx * 1.0, 9.0, sz * 1.0])
            nrm = np.array([sx, 0.0, sz])
            b.tube("steel", mid0 + nrm * 0.05, mid1 + nrm * 0.05, 0.07, 5)
        win(b, (0.0, 1.6, 1.88), (1, 0, 0), 0.8, 1.5, (0, 0, 1), off=0.04, mat="steel")
    if state == "damaged":
        b.box("rust", (0.6, 5.6, 1.45), (1.2, 1.6, 0.18), axis_angle((0.2, 0.3, 1.0), 0.5))
    # the cab: louvred skirt widening to the full cab, a plain box, a roof slab with a pale rim
    cab_lo = [(-1.4, -1.4), (1.4, -1.4), (1.4, 1.4), (-1.4, 1.4)]
    cab_hi = [(-1.9, -1.9), (1.9, -1.9), (1.9, 1.9), (-1.9, 1.9)]
    prism(b, "tankgrey", cab_lo, 9.0, 9.9, cab_hi, cap_top=False)
    if fine:
        for k in range(4):
            for sgn, ax in ((1, 0), (-1, 0), (1, 1), (-1, 1)):
                pass
        for yy in (9.25, 9.5, 9.75):
            b.box("steel", (0, yy, 0), (3.2 + 0.5 * (yy - 9.0), 0.05, 3.2 + 0.5 * (yy - 9.0)))
    walls(c, b, "palecorr", cab_hi, 9.9, 11.0, "intact", c.rng, cell=2.0)
    prism(b, "machgrey", [(-2.1, -2.1), (2.1, -2.1), (2.1, 2.1), (-2.1, 2.1)], 11.0, 11.3, cap_top=True)
    ring_band(b, "whitecity", [(-2.1, -2.1), (2.1, -2.1), (2.1, 2.1), (-2.1, 2.1)], 10.95, 11.35, 0.06)
    tb = m.node("Turret", t=(0.0, 10.85, 0.0))
    seg = 14 if fine else 8
    tb.box("steel", (1.0, 0.0, 0.0), (1.2, 0.5, 0.7))
    hit = state == "damaged"
    tb.tube("whitecity", (1.5, 0.0, 0.0), (2.6, 0.0, 0.0), 0.2, seg)
    if not hit:
        tb.tube("steel", (2.6, 0.0, 0.0), (3.2, 0.0, 0.0), 0.12, seg)
    else:
        tb.disc("rust", (2.6, 0.0, 0.0), 0.2, (1, 0, 0), seg=9)
    return m, None


# ===================================================================================================== generators and spotlight
def generator(long_):
    """The turret power generator: a hexagonal hood along x on stepped end caps (x -4.1..12.7); the full power generator
    (x -12.4..20.7) is the same hood twice as long with two pylon spikes. Each end cap is a sloped block."""
    def fn(state, lod, seed):
        c = Ctx(state, lod, seed, breach=(4.0, 3.5, 4.5, 3.0), ledges=[(5.4, 1.5, 0.4)], ao_rings=[(2.0, 1.0, 0.3)], ground_h=2.5)
        fine = c.fine
        m = Model(c)
        b = m.node("PowerGenerator")
        x0, x1 = (0.7, 7.85) if not long_ else (-3.5, 11.9)
        xa, xb = (-4.1, 12.7) if not long_ else (-12.4, 20.7)
        zc = 4.45
        hexa = [(zc - 4.4, 0.0), (zc + 4.4, 0.0), (zc + 4.4, 3.0), (zc + 2.6, 5.4), (zc - 2.6, 5.4), (zc - 4.4, 3.0)]  # (z, y)
        dead = state == "destroyed"
        if dead:
            hexa = [(zc - 4.4, 0.0), (zc + 4.4, 0.0), (zc + 4.4, 1.6), (zc + 1.0, 2.4), (zc - 3.0, 1.9), (zc - 4.4, 1.2)]
        prism(b, "machgrey", hexa, x0, x1, axis="x", cap_top=True, cap_bot=False)
        for (xs, xe) in ((x0, xa), (x1, xb)):
            lo = [(zc - 3.6, 0.0), (zc + 3.6, 0.0), (zc + 3.6, 2.2 if not dead else 1.2), (zc - 3.6, 2.2 if not dead else 1.2)]
            sg = 1 if xe > xs else -1
            xm_ = xs + 0.6 * (xe - xs)
            prism(b, "concrete_dark", lo, xs, xm_, axis="x", cap_top=True)
            prism(b, "concrete", [(zc - 3.6, 0.0), (zc + 3.6, 0.0), (zc + 3.6, 2.2 if not dead else 1.2), (zc - 3.6, 2.2 if not dead else 1.2)], xm_, xe,
                  [(zc - 2.8, 0.0), (zc + 2.8, 0.0), (zc + 2.8, 1.6 if not dead else 0.8), (zc - 2.8, 1.6 if not dead else 0.8)], axis="x", cap_top=True)
        if not dead:
            if fine:
                decal(b, "id_plate", (x0 + 1.6, 5.43, zc), (1, 0, 0), (0, 0, 1), 1.0, 0.5, (0, 1, 0))
                for k in range(4):
                    slab(b, "grate", x0 + 0.8 + k * 1.5, x0 + 1.6 + k * 1.5, 5.4, 5.5, zc - 1.0, zc + 1.0)
            for sz in (-1, 1):  # lit panels on the hood's slopes (night: amber like the other windows)
                for k in range(2 if not long_ else 4):
                    xx = x0 + 1.7 + k * 3.4
                    n_ = np.array([0, 0.8, sz * 0.6]); n_ = n_ / np.linalg.norm(n_)
                    b.quad("wglass", np.array([xx, 4.2, zc + sz * 3.5]) + n_ * 0.05, (1, 0, 0), (0, sz * 0.6, -0.8 * (-1) * 0 + 0.8) if False else np.array([0, 0.6, -sz * 0.8]) * -1, 2.2, 2.6, (0, 0, 1, 1), normal=n_)
            if long_:
                for xp in (-8.0, 15.5):  # the spiked coil stacks at each end
                    for k in range(5):
                        r0 = 2.0 - 0.28 * k
                        b.revolve("galv", [(r0, 2.2 + 1.5 * k), (r0 * 0.55, 2.2 + 1.5 * k + 0.8), (r0 * 0.9, 2.2 + 1.5 * k + 1.0)], 16 if fine else 8, cx=xp, cz=zc, uref=1.0)
                    b.tube("steel", (xp, 9.4, zc), (xp, 10.0, zc), 0.12, 6)
            if state == "damaged":
                b.box("rust", (x0 + 3.2, 5.6, zc + 1.2), (2.2, 0.15, 1.8), axis_angle((0.2, 0, 1), 0.5))
        else:
            rubble(b, c.rng, 10 if fine else 5, (x0 + x1) / 2, zc, 4.0, 1.0, (0.6, 1.5), "machgrey")
        return m, None
    return fn


def spotlight(state, lod, seed):
    """Searchlight as the original: a squat olive pedestal, a slim pale pole to 15.2 m, a yoke and a lamp head (a barrel 3.8 m long, lens
    to -z, a short hood) on the L_SpotRotar / L_SpotBattery nodes."""
    c = Ctx(state, lod, seed, breach=(0.0, 14.0, 0.0, 2.0), ledges=[(15.2, 2.0, 0.3)], ao_rings=[(15.2, 1.0, 0.3)], ground_h=3.0)
    fine = c.fine
    m = Model(c)
    b = m.node("L_SpotLight")
    dead = state == "destroyed"
    ped0 = [(-1.5, -1.8), (1.5, -1.8), (1.5, 1.8), (-1.5, 1.8)]
    ped1 = [(-0.75, -0.9), (0.75, -0.9), (0.75, 0.9), (-0.75, 0.9)]
    prism(b, "pipegreen", ped0, 0.0, 4.2 if not dead else 2.0, ped1 if not dead else [(-1.2, -1.45), (1.2, -1.45), (1.2, 1.45), (-1.2, 1.45)], cap_top=True)
    if fine:
        decal(b, "id_plate", (0.0, 1.6, 1.0 + 0.0), (1, 0, 0), (0, 1, 0), 0.8, 0.4, (0, 0, 1)) if False else None
        win(b, (0.0, 1.8, 1.7), (1, 0, 0), 1.0, 1.8, (0, 0.18, 1), off=0.05, mat="machgrey")
    if dead:
        rubble(b, c.rng, 6, 0.0, 0.0, 2.5, 0.2, (0.5, 1.2), "galv")
        b.tube("palecorr", (0.0, 2.0, 0.0), (3.5, 2.6, 1.5), 0.3, 6)
        fr = _frag(m, "L_SpotRotar", axis_angle((0.2, 0.1, 1.0), 1.4), (3.2, 0.6, 0.8))
        fr.box("steel", (0, 0, 0), (1.6, 0.5, 1.4)); fr.tube("slate", (0, 0, -1.0), (0, 0, 2.0), 1.1, 10)
        settle(m, ["L_SpotRotar"], 0.4)
        return m, None
    top = 15.2
    b.box("palecorr", (0.0, (4.2 + top) / 2, 0.0), (0.7, top - 4.2, 0.7))
    if fine:
        for yy in (5.5, 8.0, 10.5, 13.0):
            b.box("steel", (0, yy, 0), (0.9, 0.12, 0.9))
    if state == "damaged":
        b.box("rust", (0.45, 9.0, 0.0), (0.18, 3.0, 0.5), axis_angle((0.1, 0, 1.0), 0.2))
    ro = m.node("L_SpotRotar", t=(0.0, 15.2, 0.17))
    ro.revolve("steel", [(0.9, 0.0), (0.9, 0.35), (0.6, 0.45)], 14 if fine else 8, uref=1.0)
    ro.box("machgrey", (0, 0.9, 0.0), (1.4, 0.8, 0.6))
    ro.box("steel", (-0.8, 1.55, -0.3), (0.2, 1.4, 1.0)); ro.box("steel", (0.8, 1.55, -0.3), (0.2, 1.4, 1.0))  # the yoke arms
    bat = m.node("L_SpotBattery", "L_SpotRotar", t=(0.0, 1.8, -0.48))
    hit = state == "damaged"
    bat.tube("palecorr", (0, 0, -1.5), (0, 0, 1.2), 1.15, 16 if fine else 8)       # the lamp barrel
    bat.tube("steel", (0, 0, 1.2), (0, 0, 1.6), 1.0, 16 if fine else 8)            # the rear cap
    bat.tube("whitecity", (0, 0, -1.5), (0, 0, -1.74), 1.3, 16 if fine else 8)      # the front bezel
    bat.disc("wglass" if not hit else "rust", (0, 0, -1.76), 1.05, (0, 0, -1), seg=16 if fine else 8)  # the lens
    if fine:
        for k in range(4):
            bat.tube("steel", (0, 0, -0.9 + 0.55 * k), (0, 0, -0.8 + 0.55 * k), 1.2, 14)
    return m, None


# ===================================================================================================== control centres from the CAD scripts
class _Replay:
    """Stands in for tools/cad/building_cad.Builder: records the prisms, lofts and boxes a CAD script places (cuts, recesses,
    sills and raw solid commands are ignored; the solids named as cut tools are dropped) so v3 can rebuild the same massing."""
    def __init__(self):
        self.ops, self.tools = [], set()
    def prism_y(self, name, poly, y0, y1): self.ops.append(("py", name, [tuple(q) for q in poly], y0, y1)); return name
    def prism_x(self, name, poly, x0, x1): self.ops.append(("px", name, [tuple(q) for q in poly], x0, x1)); return name
    def prism_z(self, name, poly, z0, z1): self.ops.append(("pz", name, [tuple(q) for q in poly], z0, z1)); return name
    def loft_y(self, name, p0, y0, p1, y1): self.ops.append(("ly", name, [tuple(q) for q in p0], y0, [tuple(q) for q in p1], y1)); return name
    def box(self, name, lo, hi, **k): self.ops.append(("bx", name.split("@")[0], tuple(lo), tuple(hi))); return name
    def obox(self, name, c, t, b_, n, size): self.ops.append(("ob", name, tuple(c), tuple(t), tuple(b_), tuple(n), tuple(size))); return name
    def cut(self, target, tool): self.tools.add(tool)
    def join(self, *a, **k): pass
    def recess(self, *a, **k): pass
    def sill(self, *a, **k): pass
    def frame(self, *a, **k): pass
    def c(self, *a, **k): pass
    def dump(self, *a, **k): return ""


def replay_cad(app):
    """Run tools/cad/<app>_cad.py against the recorder and return its ops."""
    import builtins
    import io
    import runpy
    import types
    rec = _Replay()
    fake = types.ModuleType("building_cad")
    fake.Builder = lambda: rec
    fake.cad = lambda *a, **k: None
    fake.cad_dir = lambda *a, **k: Path(".")
    old_mod = sys.modules.get("building_cad")
    sys.modules["building_cad"] = fake
    real_open = builtins.open
    def fake_open(f, *a, **k):
        if str(f).endswith(".json") and not Path(f).exists():
            return io.StringIO('{"rects": [], "openings": []}')
        return real_open(f, *a, **k)
    builtins.open = fake_open
    argv = sys.argv
    sys.argv = ["x", "/nonexistent"]
    try:
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            runpy.run_path(str(ROOT / "tools/cad" / f"{app}_cad.py"), run_name="__replay__")
    finally:
        builtins.open = real_open
        sys.argv = argv
        if old_mod is None:
            sys.modules.pop("building_cad", None)
        else:
            sys.modules["building_cad"] = old_mod
    return rec


def control(app, wall_mat, roof_mat, trim_mat, extras=None, spin=("spinner", "dish", "radar", "ant", "mast", "lamp")):
    extras = extras or {}
    cache = {}
    def fn(state, lod, seed):
        if "r" not in cache:
            cache["r"] = replay_cad(app)
        rec = cache["r"]
        c = Ctx(state, lod, seed, breach=(8.0, 9.0, -3.0, 3.5), ledges=[(4.0, 1.4, 0.5), (6.3, 1.4, 0.4)], ao_rings=[(4.0, 0.9, 0.4)], ground_h=3.0)
        fine = c.fine
        m = Model(c)
        b = m.node(app)
        dead = state == "destroyed"
        rng = c.rng
        cell = 0.8 if fine else 2.0
        wi = 0
        for op in rec.ops:
            name = op[1]
            low = name.lower()
            if name in rec.tools or "field" in low:
                continue
            if op[0] == "py":
                poly, y0, y1 = op[2], op[3], op[4]
                h = y1 - y0
                if h < 0.5:
                    if not dead:
                        prism(b, roof_mat if h > 0.1 else trim_mat, poly, y0, y1, cap_top=True)
                    continue
                if any(k in low for k in spin) or h > 8 and max(np.ptp([q[0] for q in poly]), np.ptp([q[1] for q in poly])) < 0.8:
                    if not dead:
                        prism(b, "galv", poly, y0, y1, cap_top=True)
                    continue
                if "wall" in low and h <= 1.5:
                    prism(b, "concrete", poly, y0, y1 if not dead else y0 + 0.6, cap_top=True)
                    continue
                if h >= 2.5 and len(poly) >= 3:
                    walls(c, b, wall_mat, poly, y0, y1, state, rng, torn=(wi % len(poly),), ridge=(0.2, 0.65), cell=cell)
                    if not dead:
                        prism(b, roof_mat, poly, y1, y1 + 0.08, cap_top=True)
                        try:
                            prism(b, "tankgrey", inset(poly, 0.6), y1 + 0.08, y1 + 0.12, cap_top=True)
                        except Exception:
                            pass
                        ring_band(b, trim_mat, poly, y1 - 0.6, y1 - 0.2, 0.12)
                        pc = np.mean(poly, 0)
                        if fine and abs(0.5 * sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))) > 25:
                            slab(b, "grate", pc[0] - 1.6, pc[0] - 0.4, y1 + 0.12, y1 + 0.22, pc[1] - 0.5, pc[1] + 0.5)
                            slab(b, "machgrey", pc[0] + 0.6, pc[0] + 1.8, y1 + 0.12, y1 + 0.5, pc[1] - 0.6, pc[1] + 0.6)
                            b.tube("steel", (pc[0] + 3.0, y1 + 0.12, pc[1] + 0.5), (pc[0] + 3.0, y1 + 0.55, pc[1] + 0.5), 0.35, 10)
                        if fine and h >= 4.0:
                            for i, (a, b2, n) in enumerate(edges(poly)):
                                if state == "damaged" and i == wi % len(poly):
                                    continue
                                Lw = float(np.linalg.norm(b2 - a))
                                if Lw > 2.4:
                                    mid = (a + b2) / 2; t = (b2 - a) / Lw
                                    win(b, (mid[0], y0 + h * 0.62, mid[1]), (t[0], 0, t[1]), min(Lw * 0.5, 2.6), 1.3, (n[0], 0, n[1]), off=0.03)
                    else:
                        b.disc("roofdark", (np.mean([q[0] for q in poly]), y0 + 1.0, np.mean([q[1] for q in poly])), 1.8, seg=8)
                    wi += 1
                else:
                    prism(b, wall_mat, poly, y0, y1, cap_top=not dead or h < 1)
            elif op[0] in ("px", "pz"):
                poly, w0, w1 = op[2], op[3], op[4]
                if dead:  # a ragged low stump of the extrusion
                    poly = [(q[0], min(q[1], 1.2 + 0.9 * (((i * 37) % 5) / 4.0)) if q[1] > 1.0 else q[1]) for i, q in enumerate(poly)]
                prism(b, trim_mat if "slab" in low else wall_mat, poly, w0, w1, axis="x" if op[0] == "px" else "z", cap_top=True, cap_bot=True)
            elif op[0] == "ly":
                p0, y0, p1, y1 = op[2], op[3], op[4], op[5]
                h = y1 - y0
                if dead and h > 3.0:
                    walls(c, b, wall_mat, p0, y0, y1, "destroyed", rng, ridge=(0.12, 0.5), cell=cell)
                    continue
                prism(b, wall_mat if h > 1.5 else ("whitecity" if "skirt" in low else "concrete_dark"), p0, y0, y1, p1, cap_top=True)
                if fine and h >= 3.0 and not dead:
                    q0, q1 = np.asarray(p0, float), np.asarray(p1, float)
                    for i in range(len(q1)):  # vertical ribs up each face of the tapering tower
                        a0, b0, a1, b1 = q0[i], q0[(i + 1) % len(q0)], q1[i], q1[(i + 1) % len(q1)]
                        nrm = edges(p1)[i][2]
                        for f in (0.33, 0.67):
                            lo = a0 + (b0 - a0) * f; hi = a1 + (b1 - a1) * f
                            b.tube("steel", (lo[0] + nrm[0] * 0.05, y0 + 0.2, lo[1] + nrm[1] * 0.05), (hi[0] + nrm[0] * 0.05, y1 - 0.2, hi[1] + nrm[1] * 0.05), 0.06, 4)
                    ring_band(b, "whitecity", p1, y1 - 1.7, y1 - 0.5, 0.1)
                if fine and h >= 3.0 and not dead:
                    for i, (a, b2, n) in enumerate(edges(p1)):
                        Lw = float(np.linalg.norm(b2 - a))
                        if Lw > 1.5 and not (state == "damaged" and i == wi % len(p1)):
                            mid = (a + b2) / 2; t = (b2 - a) / Lw
                            win(b, (mid[0], y0 + 0.78 * h, mid[1]), (t[0], 0, t[1]), min(Lw * 0.55, 3.0), 1.2, (n[0], 0, n[1]), off=0.04)
                    wi += 1
            elif op[0] == "bx":
                lo, hi = np.array(op[2]), np.array(op[3])
                if dead and (hi[1] - lo[1]) < 0.5:
                    continue
                mt = "galv" if any(k in low for k in spin) else (wall_mat if hi[1] - lo[1] > 1.5 else (roof_mat if hi[1] - lo[1] > 0.1 else "grate"))
                b.box(mt, (lo + hi) / 2, hi - lo)
            elif op[0] == "ob":
                if dead:
                    continue
                cc, t_, b_, n_, sz = map(np.array, op[2:7])
                b.box("machgrey", cc, sz, np.stack([t_, b_, n_], 1))
        if not dead:
            for (x, z, y0_, y1_) in extras.get("masts", []):
                b.tube("galv", (x, y0_, z), (x, y1_, z), 0.07, 6)
            for (cx, cy, cz, sx_, sy_, sz_, ang) in extras.get("bars", []):
                Rm = axis_angle((0, 1, 0), ang)
                b.box("whitecity", (cx, cy, cz), (sx_, sy_, sz_), Rm)
                b.box("wglass", (cx, cy - 0.05, cz), (sx_ * 0.9, sy_ * 0.25, sz_ + 0.04), Rm)  # the lit strip along the bar
            for (x, y, z) in extras.get("dishes", []):
                b.revolve("steel", [(0.9, y), (0.5, y + 0.35), (0.05, y + 0.45)], 14, cx=x, cz=z, uref=1.0)
        else:
            rubble(b, rng, 14 if fine else 6, 0.0, 0.0, 9.0, 1.0, (0.7, 1.8))
            for (cx, cy, cz, sx_, sy_, sz_, ang) in extras.get("bars", []):
                b.box("slate", (cx * 0.6, 0.4, cz * 0.6 + 3.0), (sx_, sy_, sz_), axis_angle((0, 1, 0), ang + 1.0))
        return m, None
    return fn


# ===================================================================================================== s_turretcontrol
S_HALL_LO = [(-4.65, -2.39), (-4.65, -7.07), (-8.7, -9.41), (-12.75, -7.07), (-12.75, -2.39), (-8.7, -0.06)]
S_HALL_HI = [(-5.08, -2.64), (-5.08, -6.82), (-8.7, -8.91), (-12.32, -6.82), (-12.32, -2.64), (-8.7, -0.56)]
S_LOBE_L = [(-7.35, 4.13), (-1.89, 4.13), (-1.89, 9.38), (-4.29, 10.69), (-7.16, 10.66), (-9.15, 8.86), (-9.2, 5.94)]
S_LOBE_R = [(-1.89, 4.13), (3.57, 4.13), (5.24, 5.94), (5.26, 8.86), (3.38, 10.66), (0.32, 10.69), (-1.89, 9.38)]
S_TOWER_B = [(6.15, -6.41), (6.15, -2.73), (9.34, -0.89), (12.53, -2.73), (12.53, -6.41), (9.34, -8.26)]
S_TOWER_T = [(6.5, -6.22), (6.5, -2.93), (9.34, -1.29), (12.19, -2.93), (12.19, -6.22), (9.34, -7.86)]
S_FIG8 = [(-7.35, 4.13), (3.57, 4.13), (5.24, 5.94), (5.26, 8.86), (3.38, 10.66), (0.32, 10.69), (-1.89, 9.38), (-4.29, 10.69), (-7.16, 10.66), (-9.15, 8.86), (-9.2, 5.94)]


def inset(poly, d):
    """Inward offset of a convex xz polygon (mitred)."""
    p = np.asarray(poly, float); n = len(p)
    ed = edges(p)
    lines = [(a - nn * d, (b2 - a)) for a, b2, nn in ed]
    out = []
    for i in range(n):
        (p0, e), (q0, f) = lines[i - 1], lines[i]
        det = e[0] * f[1] - e[1] * f[0]
        t = ((q0[0] - p0[0]) * f[1] - (q0[1] - p0[1]) * f[0]) / det
        out.append((p0[0] + e[0] * t, p0[1] + e[1] * t))
    return out


def ring_band(b, mat, poly, y0, y1, proud):
    for a, b2, n in edges(poly):
        L = float(np.linalg.norm(b2 - a))
        if L < 0.05:
            continue
        mid = (a + b2) / 2 + n * proud / 2
        t = (b2 - a) / L
        Rm = np.stack([np.array([t[0], 0, t[1]]), [0, 1, 0], np.array([n[0], 0, n[1]])], 1)
        b.box(mat, (mid[0], (y0 + y1) / 2, mid[1]), (L + 2 * proud, y1 - y0, proud), Rm)


def s_control(state, lod, seed):
    c = Ctx(state, lod, seed, breach=(9.3, 11.0, -4.0, 3.5), ledges=[(3.97, 1.4, 0.5), (6.26, 1.4, 0.4), (13.47, 1.6, 0.4)],
            ao_rings=[(3.97, 0.9, 0.4), (5.64, 0.9, 0.3)], ground_h=3.0)
    fine = c.fine
    m = Model(c)
    rng = c.rng
    b = m.node("S_TurretControl")
    cell = 0.8 if fine else 2.0
    dead = state == "destroyed"
    # --- central block and its roof slab, with the dark field and grilles on it
    slab(b, "whitecity", -7.24, 3.46, 0.0, 3.27, -8.47, 4.68)
    if not dead:
        slab(b, "whitecity", -7.39, 3.61, 3.27, 3.97, -9.45, 4.68)
        b.box("machgrey", (-1.9, 3.975, -2.4), (9.0, 0.02, 11.0))
        if fine:
            for (x0, x1, z0, z1) in ((-4.0, -1.9, -7.3, -6.7), (-6.4, -4.4, 2.0, 2.6)):
                slab(b, "grate", x0, x1, 3.97, 4.07, z0, z1)
            slab(b, "galv", -1.79, 0.95, 3.97, 4.1, -4.70, -4.38)  # the L-shaped pipe
            slab(b, "galv", 0.62, 0.95, 3.97, 4.1, -4.70, 3.05)
            prism(b, "machgrey", [(-5.61, -1.82), (-2.31, -1.82), (-2.31, 1.52), (-5.61, 1.52)], 3.97, 5.08,
                  [(-5.14, -1.35), (-2.78, -1.35), (-2.78, 1.04), (-5.14, 1.04)])
            for x, top in ((-4.58, 12.57), (-3.41, 15.99)):
                b.tube("galv", (x, 5.0, -0.74), (x, top, -0.74), 0.07, 6)
    else:
        slab(b, "whitecity", -7.39, 3.61, 3.27, 3.6, -9.45, -2.0)  # the slab sagged, half fallen in
        rubble(b, rng, 12 if fine else 6, -2.0, 0.0, 4.0, 3.2, (0.6, 1.8), "concrete")
    # --- hexagonal hall: battered skirt, straight walls, roof field
    prism(b, "concrete_dark", S_HALL_LO, 0.0, 2.74, S_HALL_HI, cap_top=False)
    walls(c, b, "whitecity", S_HALL_HI, 2.74, 6.26, state, rng, torn=(1,), ridge=(0.25, 0.65), cell=cell)
    if not dead:
        prism(b, "tankgrey", S_HALL_HI, 6.26, 6.34, cap_top=True)
        prism(b, "machgrey", inset(S_HALL_HI, 0.72), 6.34, 6.38, cap_top=True)
        ring_band(b, "whitecity", S_HALL_HI, 2.64, 2.84, 0.12)
        if fine:
            for i, (a, b2, n) in enumerate(edges(S_HALL_HI)):
                if state == "damaged" and i == 1:
                    continue
                if np.linalg.norm(b2 - a) > 3.0:
                    mid = (a + b2) / 2; t = (b2 - a) / np.linalg.norm(b2 - a)
                    for k in (-1, 1):
                        p = mid + t * k * 1.1
                        win(b, (p[0], 4.7, p[1]), (t[0], 0, t[1]), 1.2, 1.3, (n[0], 0, n[1]), off=0.03)
    else:
        b.disc("interior", (-8.7, 3.4, -4.7), 3.8, seg=10)
    # --- figure-of-eight block, two lobes, cornice, roof fields
    for k, poly in enumerate((S_LOBE_L, S_LOBE_R)):
        walls(c, b, "whitecity", poly, 0.0, 5.87, state, rng, torn=(2,) if k == 1 else (), ridge=(0.3, 0.7), cell=cell)
        if not dead:
            prism(b, "tankgrey", poly, 5.87, 5.95, cap_top=True)
            prism(b, "machgrey", inset(poly, 0.45), 5.95, 5.99, cap_top=True)
            if fine:
                cx = np.mean(poly, 0)
                slab(b, "grate", cx[0] - 1.2, cx[0] + 1.2, 5.99, 6.09, cx[1] - 0.3, cx[1] + 0.3)
        else:
            b.disc("interior", (np.mean(poly, 0)[0], 2.0, np.mean(poly, 0)[1]), 3.0, seg=10)
    if not dead:
        ring_band(b, "paint", S_FIG8, 5.04, 5.64, 0.15)
        if fine:
            for (x, z, nx, nz, w) in ((-4.0, 4.13, 0, -1, 3.0), (1.0, 4.13, 0, -1, 3.0)):  # garage doors on the front
                pass
            for x in (-4.4, 0.9):
                win(b, (x, 1.6, 4.13), (1, 0, 0), 2.9, 3.0, (0, 0, -1), off=0.03, mat="tankgrey")
                win(b, (x, 1.6, 4.13), (1, 0, 0), 2.5, 2.7, (0, 0, -1), off=0.06, mat="interior")
    # --- tower: base, connector, taper, window band, roof field, pedestal, radar
    prism(b, "whitecity", S_TOWER_B, 0.0, 3.67, cap_top=False)
    slab(b, "whitecity", 3.31, 6.15, 0.0, 3.67, -6.41, -2.73)
    prism(b, "concrete_dark", S_TOWER_B, 3.67, 9.39, S_TOWER_T, cap_top=False)
    t_state = "destroyed" if dead else state
    walls(c, b, "whitecity", S_TOWER_T, 9.39, 13.47, t_state, rng, torn=(1, 2), ridge=(0.0, 0.0) if False else (0.12, 0.4), cell=cell)
    if dead:
        for k in range(6):
            pass
        rubble(b, rng, 9 if fine else 4, 9.3, -4.5, 3.5, 3.6, (0.7, 1.6))
    else:
        prism(b, "tankgrey", S_TOWER_T, 13.47, 13.55, cap_top=True)
        prism(b, "machgrey", inset(S_TOWER_T, 0.52), 13.55, 13.59, cap_top=True)
        ring_band(b, "paint", S_TOWER_T, 9.29, 9.49, 0.15)
        pa = [(8.2, -6.26), (10.47, -6.26), (10.47, -4.83), (8.2, -4.83)]
        pb = [(8.52, -6.01), (10.15, -6.01), (10.15, -5.08), (8.52, -5.08)]
        prism(b, "machgrey", pa, 13.59, 15.51, pb, cap_top=True)
        for i, (a, b2, n) in enumerate(edges(S_TOWER_T)):
            if state == "damaged" and i in (1, 2):
                continue
            mid = (a + b2) / 2; t = (b2 - a) / np.linalg.norm(b2 - a)
            Lw = float(np.linalg.norm(b2 - a))
            for k in (-1, 1):
                p = mid + t * k * Lw * 0.22
                win(b, (p[0], 11.45, p[1]), (t[0], 0, t[1]), Lw * 0.36, 1.8, (n[0], 0, n[1]), off=0.04)
    # --- the radar bar on its pedestal (its own node: it can be made to turn)
    if not dead:
        rd = m.node("Radar", "S_TurretControl", t=(9.36, 15.51, -5.58))
        ang = -0.104 if state != "damaged" else -0.104 + 0.5
        Rm = axis_angle((0, 1, 0), ang)
        if state == "damaged":
            rd.M = (Rm @ axis_angle((1, 0, 0), 0.12), rd.M[1])  # bent, hanging off its mount
        else:
            rd.M = (Rm, rd.M[1])
        rd.box("steel", (0, 0.25, 0), (5.76, 0.5, 1.2))
        rd.box("galv", (0, 0.72, 0), (2.6, 0.95, 0.62))
        rd.tube("galv", (-0.55, -0.4, 0), (-0.55, 0.0, 0), 0.14, 8)
    else:
        rd = m.node("Radar", "S_TurretControl", t=(9.36, 15.51, -5.58), world=False)
        rd.M = (axis_angle((0.2, 1, 0.1), 0.9) @ axis_angle((1, 0, 0), 1.4), np.array([12.0, 0.7, -3.5]))
        rd.box("steel", (0, 0.25, 0), (5.76, 0.5, 1.2))
        rd.box("galv", (0, 0.72, 0), (2.6, 0.95, 0.62))
        settle(m, ["Radar"], 0.1)
    # --- the two low walls
    for poly in ([(11.11, -2.35), (11.66, -2.35), (11.66, 4.69), (11.28, 6.63), (10.77, 6.36), (11.11, 4.69)],
                 [(5.11, 8.04), (9.56, 8.04), (9.94, 8.59), (5.11, 8.59)]):
        prism(b, "concrete", poly, 0.0, 1.2 if not dead else 0.6, cap_top=True)
    return m, None


# ===================================================================================================== members
MEMBERS = {
    "mediumautocannonturret": (make_turret("mac", (0.9, 6.0, 0.4, 1.8)), "Base 4.6 m square by 4 m, Turret x +-1.3, y 4..6.8, z -3.7..8.0 (original node bounds); twin autocannon"),
    "lrmturret": (make_turret("lrm", (1.5, 6.4, 0.6, 1.8)), "Turret x +-2.1, y 4..8.5, z -2..3.2: two racks 1.25 x 2.83 x 4.2 m, flared front to 4.3 m, 2 x 5 tubes each"),
    "srmturret": (make_turret("srm", (2.0, 6.0, 0.4, 1.8)), "Turret x +-3.1, y 4..7.8, z -1.3..1.5: two wide pods, 2 x 6 tubes each"),
    "pulselaserturret": (make_turret("pulse", (1.0, 5.2, 0.4, 1.8)), "Turret x +-1.7, y 4..6.2, z -3..7.7: twin pulse-laser emitters"),
    "gaussturret": (make_turret("gauss", (0.5, 6.0, 0.4, 1.8)), "Turret x -1.2..2.8, y 4.1..8.3, z -4.8..6.0: rail barrel in coil housings, capacitor stack"),
    "longtomturret": (make_turret("longtom", (0.0, 6.0, 0.4, 1.8)), "Turret x +-1.4, y 4..9.8, z -2.6..13.4: one long elevated barrel on a cradle"),
    "orbitalturret": (orbital, "Base x -3.7..12.1, z -3.6..12.2, 6.1 m; turret y 6.4..8.8; two tapered barrels to z 18.3, y 11.3 (tools/cad/orbitalturret_cad.py)"),
    "guntower": (guntower, "Base x +-1.9, 11.6 m tall; Turret node at the cab, barrel along +x like the original"),
    "lrmpopup": (make_popup("lrm", "concrete"), "Doorbase 7.2 x 8.4 m, four door slabs to 1.2 m, TurretRoot 12.4 m down (original nodes); lrm head"),
    "srmpopup": (make_popup("srm", "concrete"), "as lrmpopup; srm head"),
    "autocannonpopup": (make_popup("mac", "concrete"), "as lrmpopup; autocannon head"),
    "autocannoncamo2": (make_popup("mac", "bandgreen"), "as autocannonpopup, camouflage deck 2"),
    "autocannoncamo4": (make_popup("mac", "greybrick"), "as autocannonpopup, camouflage deck 4"),
    "srmcamo2": (make_popup("srm", "bandgreen"), "as srmpopup, camouflage deck 2"),
    "s_turretcontrol": (s_control, "x -12.8..12.5, y 0..16.6, z -9.4..10.7 (tools/cad/s_turretcontrol_cad.py): hall, fig-8 block, tower, radar"),
    "l_turretcontrol": (control("l_turretcontrol", "facadegreen", "machgrey", "steel", {"masts": [(1.05, 1.55, 4.0, 15.9), (1.5, 1.55, 4.0, 10.4)], "bars": [(8.75, 15.75, -4.35, 4.7, 0.6, 0.9, -0.55)]}), "x -11.9..12.5, y 0..16.1, z -9..10 (tools/cad/l_turretcontrol_cad.py massing)"),
    "d_turretcontrol": (control("d_turretcontrol", "whitecity", "tankgrey", "steel", {"masts": [(-3.9, -2.7, 6.9, 12.0)], "dishes": [(-4.1, 6.4, -2.65)]}), "x -12.5..11.6, y 0..15.5, z -11.5..8.4 (tools/cad/d_turretcontrol_cad.py massing)"),
    "bturretcontrol": (control("bturretcontrol", "pipegreen", "tealwall", "steel", {"masts": [(-8.2, -8.2, 6.7, 17.7)], "bars": [(9.35, 18.3, -5.3, 0.9, 0.6, 7.2, 0.1)]}), "x -12.5..12.7, y 0..18.8, z -12.3..9.3 (tools/cad/bturretcontrol_cad.py massing)"),
    "l_turretgenerator": (generator(False), "PowerGenerator x -4.1..12.7, z -1.8..10.7, y to 5.4: hexagonal hood on stepped end caps"),
    "spotlight": (spotlight, "L_SpotLight 3 x 15.2 x 3.6 m, rotor to 17.2, battery to 18.7"),
}


def build_member(app, out):
    fn, src = MEMBERS[app]
    info = {"app": app, "made_by": "tools/art/v3/bld_turrets.py", "source_dims": src, "states": {}}
    for si, state in enumerate(STATES):
        seed = 3900 + si + sum(map(ord, app))
        models = [fn(state, lod, seed)[0] for lod in (0, 1)]
        name = app + ("" if state == "intact" else "_" + state)
        st = write_tree(out / f"{name}.glb", name, models, (lambda mt: mt if mt in ("rust", "interior", "decal", "roofdark", "slate") else CHAR.get(mt, "roofdark")) if state == "destroyed" else None)
        mn, mx = world_bounds(models[0])
        tri = lambda s: int(sum(sum(d.values()) for d in s.values()))
        info["states"][state] = {"tris_lod0": tri(st[0]), "tris_lod1": tri(st[1]), "lod_switch_m": LOD_M,
                                 "nodes": models[0].order, "bounds_min": np.round(mn, 2).tolist(), "bounds_max": np.round(mx, 2).tolist()}
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
