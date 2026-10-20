#!/usr/bin/env python3
"""CAD rebuild of the spotlight control building (appearance s_spotlightcontrol), in the original's frame.

    D=~/craft/solid/mc2/buildings/s_spotlightcontrol
    python3 -I tools/art/cad_building.py openings s_spotlightcontrol > $D/openings.json
    python3 -I tools/cad/s_spotlightcontrol_cad.py $D > $D/s_spotlightcontrol.json
    solidcraft-cli run $D/s_spotlightcontrol.json --out $D/s_spotlightcontrol.obj
    python3 -I tools/art/cad_building.py bake s_spotlightcontrol $D/s_spotlightcontrol.obj --keep Light --glass 104,112,120   # the grey of the hollow cab seen through its band

Measured from game/assets/objects/s_spotlightcontrol.glb (faces grouped by plane): a core (x -0.11..9.65, z -9.53..0.42)
to 3.89 m under a hipped band to 4.62 m, a recessed middle storey (x 1.86..7.72, z -7.55..-1.56) to 6.99 m, the glazed
cab (x -0.32..9.85, z -9.53..0.42) to 10.44 m and an overhanging roof slab (x -1.34..10.87, z -10.52..1.41) to
11.55 m carrying the spotlight's frustum pedestal (to 13.44 m) and the lamp (node Light, kept verbatim). Two wings:
west (x -7.37..-0.11, z -7.26..-1.85) and south (x 1.96..7.58, z 0.42..7.55), 2.9 m, under 0.89 m slabs
(x -8.10..-0.11, z -7.64..-1.47; x 1.56..7.98, z 0.42..8.24), each with a glazed rooftop box (x -7.23..-1.56,
z -5.56..-3.55; x 3.70..5.84, z 1.84..7.39) to 4.68 m. Two low walls (1.1 m) curve round the forecourt.
Relief: every cut-out window is a recess (cab 25 cm, wing grids 20 cm, rooftop boxes 12 cm, sills under the cab's);
the gravel fields on the roof and the wing slabs are 8 cm recesses inside their painted white frames, with the
roof's two conduits, two vent boxes and the grille as real parts; standing seams on the hipped band's painted seams;
the middle storey's painted slats are real ribs; the core's green unit is a real box, its louvre a recess; the roof
slab's top edges chamfered. Feature positions come from the art (tools/art/cad_building.py regions_3d on a texture
rectangle, the same as its `decal` command).
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "art"))
from building_cad import Builder  # noqa: E402
from cad_building import Original, regions_3d  # noqa: E402

D = Path(sys.argv[1])
B = Builder()
O = Original("s_spotlightcontrol")


def decal(u0, v0, u1, v1, keep=lambda r: True):
    def sel(m, img, ix, iy):
        h, w = O.images[img].shape[:2]
        u, v = (ix + 0.5) / w, (iy + 0.5) / h
        return (m == 0) & (u >= u0) & (u <= u1) & (v >= v0) & (v <= v1)
    return [r for r in regions_3d(O, sel) if keep(r)]


def proud(name, r, depth, grow=0.0):
    n, t, b = (np.array(r[k], float) for k in ("normal", "t", "b"))
    c = np.array(r["center"]) + n * (depth / 2 - 0.01)
    return B.obox(name, c, t, b, n, (r["w"] + 2 * grow, r["h"] + 2 * grow, depth + 0.02))


VOL = []


def box(name, lo, hi, **kw):
    VOL.append((np.array(lo), np.array(hi)))
    return B.box(name, lo, hi, **kw)


def hidden(p, eps=0.05):
    p = np.asarray(p)
    return any(np.all(p > lo + eps) and np.all(p < hi - eps) for lo, hi in VOL)


# ---- volumes
core = box("core", (-0.11, 0.0, -9.53), (9.65, 3.89, 0.42))
band = B.loft_y("band", [(-0.11, -9.53), (9.65, -9.53), (9.65, 0.42), (-0.11, 0.42)], 3.89,
                [(1.86, -7.55), (7.72, -7.55), (7.72, -1.56), (1.86, -1.56)], 4.62)
mid = box("mid", (1.86, 4.60, -7.55), (7.72, 6.99, -1.56))
cab = box("cab", (-0.32, 6.99, -9.53), (9.85, 10.44, 0.42))
roof = box("roof", (-1.34, 10.43, -10.52), (10.87, 11.55, 1.41), chamfer=0.06)
B.loft_y("pedestal", [(6.13, -9.54), (9.9, -9.54), (9.9, -5.86), (6.13, -5.86)], 11.55,
         [(6.76, -8.93), (9.27, -8.93), (9.27, -6.47), (6.76, -6.47)], 13.44)
wa = box("wing_w", (-7.37, 0.0, -7.26), (-0.11, 2.9, -1.85))
wb = box("wing_s", (1.96, 0.0, 0.42), (7.58, 2.9, 7.55))
sa = box("slab_w", (-8.10, 2.9, -7.64), (-0.11, 3.79, -1.47))
sb = box("slab_s", (1.56, 2.9, 0.42), (7.98, 3.79, 8.24))
ka = box("sky_w", (-7.23, 3.70, -5.56), (-1.56, 4.68, -3.55))
kb = box("sky_s", (3.70, 3.70, 1.84), (5.84, 4.68, 7.39))
B.prism_y("lowwall0", [(-6.67, -1.9), (-6.67, 3.11), (-5.65, 4.13), (-5.30, 3.76), (-6.16, 2.89), (-6.16, -1.85)], 0.0, 1.1)
B.prism_y("lowwall1", [(-4.02, 5.75), (-3.0, 6.77), (2.01, 6.77), (2.0, 6.26), (-2.78, 6.26), (-3.65, 5.39)], 0.0, 1.1)

# ---- windows
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    x, y, z = o["center"]
    if y > 6.9:
        B.recess(cab, o, 0.25)
        B.sill(f"sill{k}", o, proud=0.12, thick=0.07, overhang=0.08)
    elif y > 3.7:
        B.recess(ka if x < 0 else kb, o, 0.12)
    else:
        B.recess(wa if x < 0 else wb, o, 0.20)

# ---- gravel fields: the roof's and the two slabs' (the rooftop boxes stand in them)
for k, r in enumerate(decal(0.459, 0.028, 0.864, 0.393, keep=lambda r: r["normal"][1] > 0.99 and abs(r["center"][1] - 3.79) < 0.02
                            or r["normal"][1] > 0.99 and abs(r["center"][1] - 11.55) < 0.02)):
    tgt = roof if r["center"][1] > 11 else (sa if r["center"][0] < 0 else sb)
    B.recess(tgt, r, 0.08)
on_roof = lambda r: r["normal"][1] > 0.99 and abs(r["center"][1] - 11.55) < 0.03  # noqa: E731
FY = 11.47  # the field floor
n_p = 0
for (u0, v0, u1, v1), hgt in [((0.479, 0.118, 0.577, 0.128), 0.16), ((0.567, 0.118, 0.577, 0.312), 0.16),
                              ((0.567, 0.302, 0.797, 0.312), 0.16), ((0.787, 0.288, 0.797, 0.312), 0.16),
                              ((0.491, 0.142, 0.546, 0.150), 0.16), ((0.538, 0.142, 0.546, 0.335), 0.16),
                              ((0.538, 0.327, 0.805, 0.335), 0.16),
                              ((0.780, 0.177, 0.817, 0.249), 0.55), ((0.801, 0.288, 0.817, 0.360), 0.45),
                              ((0.477, 0.259, 0.514, 0.360), 0.25)]:
    for r in decal(u0, v0, u1, v1, keep=on_roof):
        n_p += 1
        r = dict(r, center=[r["center"][0], FY, r["center"][2]])
        proud(f"rooftop{n_p}", r, hgt)

# ---- hipped band: standing seams on the painted seams (u 0.154, 0.279, 0.404, 0.529 of the band's 0.003..0.685;
# the set is symmetric to 1 cm, so the faces' u direction does not matter). Narrow texture strips come back empty
# from regions_3d, so these positions are worked out on the faces themselves.
n_s = 0
LO0, HI0, LO1, HI1 = np.array([-0.11, -9.53]), np.array([9.65, 0.42]), np.array([1.86, -7.55]), np.array([7.72, -1.56])
for u in (0.154, 0.279, 0.404, 0.529):
    f = (u - 0.003) / 0.682
    for ax in (0, 1):  # seams across the z faces (ax 0: varying x) and the x faces (ax 1: varying z)
        for side in (0, 1):
            p0, p1 = LO0 + (HI0 - LO0) * f, LO1 + (HI1 - LO1) * f
            q0, q1 = [0.0, 3.89, 0.0], [0.0, 4.62, 0.0]
            o = 1 - ax
            q0[2 * ax], q1[2 * ax] = p0[ax], p1[ax]
            q0[2 * o], q1[2 * o] = (LO0, HI0)[side][o], (LO1, HI1)[side][o]
            q0, q1 = np.array(q0), np.array(q1)
            n_s += 1
            d = q1 - q0
            L = np.linalg.norm(d)
            bdir = d / L
            t = np.zeros(3)
            t[2 * ax] = 1.0
            nrm = np.cross(t, bdir)
            if nrm[1] < 0:
                nrm, t = -nrm, -t
            B.obox(f"seam{n_s}@avg", (q0 + q1) / 2 + nrm * 0.03, t, bdir, nrm, (0.10, L, 0.08))

# ---- middle storey slats (@avg: one colour each, the mean of the art under it), ten across each face
n_r = 0
for k in range(10):
    f = (0.025 + 0.0392 * k) / 0.408
    for x, z, nx, nz in [(1.86 + f * 5.86, -1.56, 0, 1), (1.86 + f * 5.86, -7.55, 0, -1),
                         (1.86, -7.55 + f * 5.99, -1, 0), (7.72, -7.55 + f * 5.99, 1, 0)]:
        n_r += 1
        lo = [x - 0.05 + 0.03 * nx, 4.62, z - 0.05 + 0.03 * nz] if nz == 0 else [x - 0.05, 4.62, z - 0.01 if nz > 0 else z - 0.06]
        hi = [x + 0.05 + 0.03 * nx, 6.99, z + 0.05 + 0.03 * nz] if nz == 0 else [x + 0.05, 6.99, z + 0.06 if nz > 0 else z + 0.01]
        if nz == 0:
            lo[0], hi[0] = (x - 0.01, x + 0.06) if nx > 0 else (x - 0.06, x + 0.01)
        B.box(f"slat{n_r}@avg", lo, hi)

# ---- core walls: the green unit (a real box), the louvre (a recess)
for r in decal(0.233, 0.85, 0.391, 0.996, keep=lambda r: r["center"][1] < 3.9 and abs(r["normal"][1]) < 0.1
               and not hidden(np.array(r["center"]) + np.array(r["normal"]) * 0.3)):
    n_p += 1
    proud(f"unit{n_p}", r, 0.55)
for r in decal(0.556, 0.872, 0.617, 0.983, keep=lambda r: r["center"][1] < 3.9 and abs(r["normal"][1]) < 0.1
               and not hidden(np.array(r["center"]) + np.array(r["normal"]) * 0.3)):
    B.recess(core, r, 0.06)
print(f"{n_p} parts, {n_s} seams, {n_r} slats", file=sys.stderr)
print(B.dump())
