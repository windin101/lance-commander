"""Shared parts of the two spaceport terminals (terminal1_cad.py, terminal2_cad.py), in the originals' frame.

Measured from game/assets/objects/terminal1.glb / terminal2.glb (nodes Terminal, Externals, Stairs; Terminal is
byte-identical in both): a 25.5 x 12 m hall (x +-12.75, z +-6), walls to 6 m with a cut-out glass band (y 2..4.6,
eight windows a long wall, four an end wall) in front of a green-painted inner box; a hipped roof to a flat top
(x +-10.75, z +-4) at 8 m with a dark inset field (four rooftop units and their conduits painted on it) and a
painted mount plate on each long slope. Externals: a leaning wedge mast from the +z slope (x -6..-4) to 15.8 m with
a floodlight head (a frustum facing out and down); Stairs: a 2 m flight (x -10..-8) from a door vestibule (y 1.8..4.8,
z 6..8) down to z 12.54. terminal2 adds a second mast and flight turned 180 degrees about y (its flight to z -12.75).
Relief: the windows are 25 cm recesses (glass at the back) with a continuous sill and lintel; a fascia at the eaves,
hip ridge caps; the roof field a 10 cm recess with the four units as real boxes and the conduits as real runs;
the mount plates proud 6 cm; the mast a real tapered wedge, the head a frustum with a 12 cm lens recess; the
flight has real treads between solid stringers (the original's painted side panels), the vestibule door a 20 cm
recess under a hood.
"""
import json
import math

import numpy as np

from building_cad import Builder, cad, cad_dir, axis_angle

XW, ZW, WALL, TOP, XT, ZT = 12.75, 6.0, 6.0, 8.0, 10.75, 4.0


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def rot_y_to(a):
    """Rotation (game frame) about game x taking +y onto a (a has no x component)."""
    a = unit(a)
    ang = math.atan2(a[2], a[1])  # +y towards +z
    c, s = math.cos(ang), math.sin(ang)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]]), ang


def turned(B, name, base, a, poly0, poly1, length):
    """A loft of two polygons (local x, local z, game metres), local y along the game direction a from base."""
    R, ang = rot_y_to(a)
    B.loft_y(name, poly0, 0.0, poly1, length)
    # game rotation about +x by ang (y towards z) = CAD rotation about +X by ang (Z towards -Y = game +z)
    B.c("solid.move", bodies=[name], axis=[1, 0, 0], angle=f"{math.degrees(ang):.4f} deg")
    B.c("solid.move", bodies=[name], translate=cad(base))
    return R


def local(R, base, pts):
    """World points -> local (x, z) of the turned frame (y dropped)."""
    loc = (R.T @ (np.asarray(pts, float) - base).T).T
    return [(round(p[0], 4), round(p[2], 4)) for p in loc]


def bar(B, name, p0, p1, w, d=None):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    b = unit(p1 - p0)
    ref = np.array([0.0, 1.0, 0.0]) if abs(b[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
    t = unit(np.cross(b, ref))
    n = np.cross(t, b)
    return B.obox(name, (p0 + p1) / 2, t, b, n, (w, np.linalg.norm(p1 - p0), d or w))


def ux(u):  # roof texture u -> x (flat top: u 0.059 -> -10.75, 0.621 -> 10.75)
    return -10.75 + (u - 0.059) / 0.562 * 21.5


def vz(v):  # roof texture v -> z (0.060 -> -4, 0.268 -> 4)
    return -4.0 + (v - 0.060) / 0.208 * 8.0


def hall(B, D):
    walls = B.box("walls", (-XW, 0.0, -ZW), (XW, WALL, ZW))
    for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
        c, n = np.array(o["center"]), np.array(o["normal"])
        if np.dot(n, c) <= 0:  # each window is listed for the outer wall and the inner box: keep the outward one
            continue
        B.recess(walls, o, 0.25)
    # continuous sill and lintel round the glass band, a fascia at the eaves
    for side, (lo, hi) in enumerate([((-XW - 0.12, 1.92, ZW), (XW + 0.12, 2.04, ZW + 0.12)),
                                      ((-XW - 0.12, 1.92, -ZW - 0.12), (XW + 0.12, 2.04, -ZW)),
                                      ((XW, 1.92, -ZW), (XW + 0.12, 2.04, ZW)), ((-XW - 0.12, 1.92, -ZW), (-XW, 2.04, ZW))]):
        B.box(f"sill{side}", lo, hi)
        B.box(f"lintel{side}", (lo[0], 4.6, lo[2]), (hi[0], 4.7, hi[2]))
        B.box(f"fascia{side}", (lo[0] - 0.03 * (lo[0] < -XW), 5.82, lo[2] - 0.03 * (lo[2] < -ZW)),
              (hi[0] + 0.03 * (hi[0] > XW), 6.0, hi[2] + 0.03 * (hi[2] > ZW)))
    roof = B.loft_y("roof", [(-XW, -ZW), (XW, -ZW), (XW, ZW), (-XW, ZW)], WALL,
                    [(-XT, -ZT), (XT, -ZT), (XT, ZT), (-XT, ZT)], TOP)
    for k, (sx, sz) in enumerate(((1, 1), (-1, 1), (1, -1), (-1, -1))):
        bar(B, f"hip{k}", (sx * XW, WALL, sz * ZW), (sx * XT, TOP, sz * ZT), 0.18)
    # the dark roof field: a 10 cm recess
    FX0, FX1, FZ0, FZ1 = ux(0.069), ux(0.611), vz(0.069), vz(0.259)
    B.cut(roof, B.box("field", (FX0, TOP - 0.10, FZ0), (FX1, TOP + 0.2, FZ1)))
    fy = TOP - 0.10
    for k, (u0, u1) in enumerate([(0.424, 0.457), (0.468, 0.504), (0.515, 0.551), (0.564, 0.595)]):
        B.box(f"unit{k}", (ux(u0), fy, vz(0.088)), (ux(u1), fy + 0.7, vz(0.136)), chamfer=0.05)
    # conduits (u, v) polylines on the field floor
    runs = [[(0.433, 0.136), (0.433, 0.168), (0.074, 0.168)],
            [(0.481, 0.136), (0.481, 0.183), (0.183, 0.183), (0.183, 0.257)],
            [(0.527, 0.136), (0.527, 0.198), (0.214, 0.198), (0.214, 0.257)],
            [(0.573, 0.136), (0.573, 0.214), (0.488, 0.214), (0.488, 0.257)]]
    W2 = 0.10
    for r, run in enumerate(runs):
        for s, ((ua, va), (ub, vb)) in enumerate(zip(run, run[1:])):
            xa, xb = sorted((ux(ua), ux(ub)))
            za, zb = sorted((vz(va), vz(vb)))
            B.box(f"conduit{r}_{s}", (xa - W2, fy, za - W2), (xb + W2, fy + 0.15, zb + W2))
    # painted mount plates on the long slopes, proud 6 cm
    s45 = 1 / math.sqrt(2)
    for k, (x0, x1, sz) in enumerate([(-6.7, -3.3, 1), (3.3, 6.7, -1)]):
        n = np.array([0.0, s45, sz * s45])
        c = np.array([(x0 + x1) / 2, (WALL + TOP) / 2, sz * (ZW + ZT) / 2]) + n * 0.02
        t = np.array([1.0, 0.0, 0.0])
        B.obox(f"plate{k}", c, t, np.cross(n, t), n, (x1 - x0, 2.6, 0.08))


def mast(B, k, flip):
    """The +z mast and floodlight (terminal1's); flip turns it 180 degrees about y."""
    f = np.array([-1.0, 1.0, -1.0]) if flip else np.array([1.0, 1.0, 1.0])
    P = lambda *p: np.array(p) * f  # noqa: E731
    # wedge: base triangle on the slope (sunk 0.4 m into the roof), top edge at 15.8 m
    b_back, b_l, b_r = P(-5.0, 7.6, 4.0), P(-6.0, 6.0, 5.6), P(-4.0, 6.0, 5.6)
    t_l, t_r = P(-5.4, 15.8, 8.0), P(-4.6, 15.8, 8.0)
    base = (b_back + b_l + b_r) / 3
    top = (t_l + t_r) / 2
    a = top - base
    sink = unit(a) * 0.5
    R, _ = rot_y_to(a)
    L = np.linalg.norm(a) + 0.5
    p0 = local(R, base, [b_back - sink, b_l - sink, b_r - sink])
    p1 = local(R, base, [top + (b_back - base) * 0.25 + sink * 0, t_l, t_r])
    tri0 = [(x, z) for x, z in p0]
    tri1 = [(x, z) for x, z in p1]
    turned(B, f"mast{k}", base - sink, a, tri0, tri1, L)
    # floodlight head: back rectangle (0.8 x 0.59) to front (2 x 2.0), axis out and down
    bc = (P(-5.4, 15.75, 7.42) + P(-4.6, 16.21, 7.79)) / 2
    fc = (P(-6.0, 13.87, 8.47) + P(-4.0, 15.42, 9.73)) / 2
    a2 = fc - bc
    R2, _ = rot_y_to(a2)
    bpts = local(R2, bc, [P(-5.4, 15.75, 7.42), P(-4.6, 15.75, 7.42), P(-4.6, 16.21, 7.79), P(-5.4, 16.21, 7.79)])
    fpts = local(R2, bc, [P(-6.0, 13.87, 8.47) - a2, P(-4.0, 13.87, 8.47) - a2, P(-4.0, 15.42, 9.73) - a2, P(-6.0, 15.42, 9.73) - a2])
    head = f"head{k}"
    turned(B, head, bc, a2, bpts, fpts, np.linalg.norm(a2))
    n = unit(a2)
    t = np.array([1.0, 0.0, 0.0]) * f[0]
    bb = unit(np.cross(n, t))
    if bb[1] < 0:
        bb = -bb
        t = -t
    B.recess(head, dict(center=list(fc), normal=list(n), t=list(t), b=list(bb), w=1.45, h=1.4), 0.12)
    return head


def flight(B, k, flip, z_end):
    """Vestibule and flight (terminal1's, x -10..-8, down to z_end > 0); flip turns it 180 degrees about y."""
    sg = -1.0 if flip else 1.0
    X0, X1 = (-10.0, -8.0) if not flip else (8.0, 10.0)
    zf = lambda z: sg * z  # noqa: E731
    # vestibule box (y 1.8..4.8, z 6..8) with a door recess and hood on its outer face
    vb = B.box(f"vest{k}", (X0, 1.8, min(zf(6.0), zf(8.0))), (X1, 4.8, max(zf(6.0), zf(8.0))))
    n = np.array([0.0, 0.0, sg])
    door = dict(center=[(X0 + X1) / 2, 3.75, zf(8.0)], normal=list(n), t=[sg, 0, 0], b=[0, 1, 0], w=1.45, h=1.8)
    B.recess(vb, door, 0.20)
    B.sill(f"hood{k}", door, proud=0.30, thick=0.08, overhang=0.15, top=True)
    # stringers: the original's side panels, 12 cm thick
    side = [(8.0, 1.8), (8.0, 3.8), (z_end, 1.0), (z_end, 0.0), (z_end - 1.6, 0.0)]
    poly = [(zf(z), y) for z, y in side]
    if flip:
        poly = poly[::-1]
    for s, (xa, xb) in enumerate([(X0, X0 + 0.12), (X1 - 0.12, X1)]):
        B.prism_x(f"stringer{k}_{s}", poly, xa, xb)
    # treads: a sawtooth between the stringers, nosings on the original's tread plane
    n_st = 14
    run = (z_end - 8.0) / n_st
    rise = 2.8 / n_st
    pts = [(8.0, 2.8)]
    for i in range(n_st):
        z0, y0 = 8.0 + i * run, 2.8 - i * rise
        pts += [(z0 + run, y0), (z0 + run, y0 - rise)]
    pts[-1] = (z_end, 0.0)
    pts += [(z_end - 1.6, 0.0), (8.0, 1.8)]
    poly = [(zf(z), y) for z, y in pts]
    if flip:
        poly = poly[::-1]
    B.prism_x(f"treads{k}", poly, X0 + 0.12, X1 - 0.12)
