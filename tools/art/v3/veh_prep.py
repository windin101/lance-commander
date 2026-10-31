#!/usr/bin/env python3
"""Vehicle prep for the v3 rollout (LANCE-18 Hunter, generalised in LANCE-19): split the moving parts out of the fused
rigid fit that v3_rigid.py wrote, from tools/art/v3/<unit>_prep.json.

    python3 -I tools/art/v3/veh_prep.py <unit>

Reads /mnt/nvme1n1p1/mc2-rework/work/<unit>_rigid and writes .../<unit>_tracks with
  - optional kit clean-up and re-seating: "merge" {label: part}, "drop_slivers" {min_edge, max_alt} (needle triangles), "split"
    [{from, new, min, max}] (carve a gun out of a part by face-centroid box) and "drop_parts" [name], "shift" [{parts, dx, dy, dz}] mm (the kit's
    mount seats a turret on the highest point under its footprint and centres it on the model's pivot, which floats it or
    slides it off its ring);
  - "nodes": {name: [x, y, z]} moves node pivots (turret ring centre, gun trunnion, muzzles) in the model's node tree;
  - optional belts track_l (+X) and track_r ("tracks"), each riding a node at +-node_x_m (so VehicleRig reads the gauge).
    mode "envelope" (Hunter, a skirted hull: the belt is the layer of the lower side silhouette, one link thick) or "loop"
    (the whole belt is visible: faces within `thick` mm of the closed belt path round the wheel circles `circles`);
  - the wheels ("wheels"): the kit's fused wheels are cut out of the hull (cylinder about each axle; zcut limits the cut to
    the lower half for kits that only model half discs) and replaced by full discs of OUR OWN geometry (make_wheel), as
    parts wheel_l0.. / wheel_r0.. pivoted on their axles. "steer": [wheel indices] puts those wheels (both sides) under
    steer_l<i> / steer_r<i> pivot nodes at the wheel centre.
and <unit>_base.glb: the original model's node tree plus those nodes (v3_mech.py's Rig reads it: config "base_glb")."""
import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

HERE = Path(__file__).resolve().parent
ART = HERE.parent
sys.path.insert(0, str(ART))
import hd_rig as R  # noqa: E402

ROOT = ART.parents[1]
WORKS = Path("/mnt/nvme1n1p1/mc2-rework/work")


def load_cfg(unit):
    return json.loads((HERE / f"{unit}_prep.json").read_text())


def make_wheel(R, w, seg=36):
    """A full wheel in its own frame: axle along +x (the outer face at x = w), up +z. Returns (V mm, F). Own geometry,
    built from the kit's wheel proportions: tyre drum with chamfers, a recessed rim with a hub boss, six bolts and one
    bigger marker bolt (so the spin shows)."""
    prof = [(0, 0), (0, .66), (18, .9), (36, 1), (w - 36, 1), (w - 18, .9), (w, .66), (w - 45, .66), (w - 45, .42),
            (w - 15, .42), (w - 15, 0)]
    rows, V = [], []
    for x, f in prof:
        r = f * R
        if r == 0:
            rows.append([len(V)] * seg); V.append((x, 0.0, 0.0)); continue
        ring = []
        for j in range(seg):
            a = 2 * np.pi * j / seg
            ring.append(len(V)); V.append((x, r * np.sin(a), r * np.cos(a)))
        rows.append(ring)
    F = []
    for i in range(len(prof) - 1):
        for j in range(seg):
            a, b, c, d = rows[i][j], rows[i][(j + 1) % seg], rows[i + 1][(j + 1) % seg], rows[i + 1][j]
            F += [(a, b, c), (a, c, d)]
    for k in range(6):          # bolts on the recess face; k = 0 is the marker
        big = k == 0
        a = 2 * np.pi * k / 6
        cy, cz, rb, x0, x1 = 0.54 * R * np.sin(a), 0.54 * R * np.cos(a), (26.0 if big else 16.0), w - 45, (w - 8 if big else w - 22)
        base, top = [], []
        for j in range(8):
            t = 2 * np.pi * j / 8
            base.append(len(V)); V.append((x0, cy + rb * np.sin(t), cz + rb * np.cos(t)))
        for j in range(8):
            t = 2 * np.pi * j / 8
            top.append(len(V)); V.append((x1, cy + rb * np.sin(t), cz + rb * np.cos(t)))
        c = len(V); V.append((x1, cy, cz))
        for j in range(8):
            j2 = (j + 1) % 8
            F += [(base[j], base[j2], top[j2]), (base[j], top[j2], top[j]), (top[j], top[j2], c)]
    V = np.array(V, float); F = np.array(F)
    good = (F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])
    F = F[good]
    T = V[F]
    if np.einsum("ij,ij->i", T[:, 0], np.cross(T[:, 1], T[:, 2])).sum() < 0:     # outward
        F = F[:, ::-1]
    return V, F


def _orient(V, F):
    """Outward winding for a closed shell (positive signed volume)."""
    V = np.asarray(V, float); F = np.asarray(F)
    T = V[F]
    if np.einsum("ij,ij->i", T[:, 0], np.cross(T[:, 1], T[:, 2])).sum() < 0:
        F = F[:, ::-1]
    return V, F


def _loft(loops, caps=True):
    """Closed shell from a stack of equal-length vertex loops (counter-clockwise from above), bottom and top capped by fans."""
    n = len(loops[0]); V = [p for lp in loops for p in lp]; F = []
    for a in range(len(loops) - 1):
        for j in range(n):
            j2 = (j + 1) % n
            p, q, r, s = a * n + j, a * n + j2, (a + 1) * n + j2, (a + 1) * n + j
            F += [(p, q, r), (p, r, s)]
    if caps:
        for lp_i, flip in ((0, True), (len(loops) - 1, False)):
            c = len(V); V.append(tuple(np.mean(loops[lp_i], axis=0)))
            for j in range(n):
                j2 = (j + 1) % n
                F.append((c, lp_i * n + j2, lp_i * n + j) if flip else (c, lp_i * n + j, lp_i * n + j2))
    return _orient(V, F)


def _rect(cx, cy, z, L, W):
    """Corner loop of an axis-aligned rectangle (L along y, W along x), counter-clockwise from above."""
    return [(cx - W / 2, cy - L / 2, z), (cx + W / 2, cy - L / 2, z), (cx + W / 2, cy + L / 2, z), (cx - W / 2, cy + L / 2, z)]


def make_container(cx, cy, z0, L, W, H, taper=0.22, bevel=70.0, rib_pitch=330.0, rib=34.0, cast=150.0):
    """A cargo container, OUR OWN geometry (LANCE-19 ordnance truck): a tapering box with a bevelled top edge, vertical ribs on both long
    sides and both ends, door seam frames on the +y end and eight corner castings. Returns (V mm, F). z0 = its base."""
    Lt, Wt = L * (1 - taper * 0.6), W * (1 - taper)
    body_top = z0 + H - bevel
    loops = [_rect(cx, cy, z0, L, W), _rect(cx, cy, body_top, Lt, Wt), _rect(cx, cy, z0 + H, Lt - 2 * bevel, Wt - 2 * bevel)]
    parts = [_loft(loops)]

    def side_at(t, sign_axis, axis):
        """Point of the sloped wall at height fraction t, offset from the box centre along `axis` (0 = x, 1 = y)."""
        half = ((W if axis == 0 else L) / 2) * (1 - t) + ((Wt if axis == 0 else Lt) / 2) * t
        return sign_axis * half

    def bar(axis, sgn, off):                         # a slanted rib on a wall: axis 0 = long side (x wall), 1 = end (y wall)
        tt = (body_top - z0) / H
        pts = []
        for t, z in ((0.0, z0 + 40.0), (1.0, body_top - 20.0)):
            f = (z - z0) / (body_top - z0)
            wall = side_at(f, sgn, axis)
            for dn in (0.0, rib):
                for dw in (-45.0, 45.0):
                    if axis == 0:
                        pts.append((cx + wall + sgn * dn, cy + off + dw, z))
                    else:
                        pts.append((cx + off + dw, cy + wall + sgn * dn, z))
        # pts order: bottom (dn0 dw-, dn0 dw+, dn1 dw-, dn1 dw+), top (same)
        b = pts[:4]; t_ = pts[4:]
        loop_b = [b[0], b[1], b[3], b[2]]; loop_t = [t_[0], t_[1], t_[3], t_[2]]
        return _loft([loop_b, loop_t])
    n_long = int(L // rib_pitch)
    for k in range(n_long):
        off = -L / 2 + (k + 0.5) * L / n_long
        for sgn in (1, -1):
            parts.append(bar(0, sgn, off))
    n_end = int(W // rib_pitch)
    for k in range(n_end):
        off = -W / 2 + (k + 0.5) * W / n_end
        for sgn in (1, -1):
            parts.append(bar(1, sgn, off * (1 - taper * 0.5)))
    # door seam frame on the +y end: two tall bars either side of the centre line, a horizontal one at mid height
    for off in (-24.0, 24.0):
        parts.append(bar(1, 1, off))
    # corner castings
    for sx in (-1, 1):
        for sy in (-1, 1):
            for z, f in ((z0, 0.0), (z0 + H - cast - bevel, 1.0)):
                hx = (W / 2 if f == 0.0 else Wt / 2) - cast * 0.2; hy = (L / 2 if f == 0.0 else Lt / 2) - cast * 0.2
                lo = (cx + sx * hx - cast / 2, cy + sy * hy - cast / 2, z)
                parts.append(_loft([_rect(lo[0] + cast / 2, lo[1] + cast / 2, lo[2], cast, cast), _rect(lo[0] + cast / 2, lo[1] + cast / 2, lo[2] + cast, cast, cast)]))
    Vs, Fs, off = [], [], 0
    for V_, F_ in parts:
        Vs.append(V_); Fs.append(F_ + off); off += len(V_)
    return np.concatenate(Vs), np.concatenate(Fs)


def make_slab(x0, x1, y0, y1, z0, z1, bevel=70.0, n=16):
    """A track shell, OUR OWN geometry (LANCE-19): a stadium (round-ended) prism along x, edges bevelled. y0..y1 / z0..z1 is its
    side-view box, x0..x1 its thickness. Returns (V mm, F)."""
    r = (z1 - z0) / 2.0
    cz = (z0 + z1) / 2.0
    pts = []
    for k in range(n + 1):                    # front (y0) semicircle, bottom to top
        a = -np.pi / 2 - np.pi * k / n
        pts.append((y0 + r + r * np.cos(a), cz + r * np.sin(a)))
    for k in range(n + 1):                    # rear (y1) semicircle, top to bottom
        a = np.pi / 2 - np.pi * k / n
        pts.append((y1 - r + r * np.cos(a), cz + r * np.sin(a)))
    pts = np.array(pts)
    cen = np.array([(y0 + y1) / 2.0, cz])

    def ring(x, inset):
        q = cen + (pts - cen) * np.clip(1 - inset / np.maximum(np.linalg.norm(pts - cen, axis=1, keepdims=True), 1.0), 0, 1)
        return [(x, py, pz) for py, pz in q]
    loops = [ring(x0, bevel), ring(x0 + bevel, 0.0), ring(x1 - bevel, 0.0), ring(x1, bevel)]
    return _loft(loops)


def wheel_x(cfg, w):
    """(x0, x1) of one wheel: the entry's own [y, z, r, x0, x1] when it has them (a half-track's front wheel and its track wheels
    differ in width), else the shared wheels.x0 / x1."""
    wc = cfg["wheels"]
    return (float(w[3]), float(w[4])) if len(w) > 4 else (float(wc["x0"]), float(wc["x1"]))


def wheel_width(cfg):
    return cfg["wheels"]["x1"] - cfg["wheels"]["x0"]


def wheel_world(cfg, side, y, z, V, x0=None):
    """The wheel placed on its axle: side +1 (track_l, +X) is the local frame as is, side -1 turned half a turn about
    the vertical axis (a rotation, so the shared UVs keep their handedness)."""
    W = V + np.array([cfg["wheels"]["x0"] if x0 is None else x0, 0, 0])
    if side < 0:
        W = W * np.array([-1.0, -1.0, 1.0])
    return W + np.array([0.0, y, 0.0]) + np.array([0, 0, z])


def wheel_names(cfg):
    n = len(cfg["wheels"]["list"])
    return [f"wheel_{s}{i}" for s in "lr" for i in range(n)]


def wheel_geometry(cfg, name, lifted=False):
    """(V, F) in world mm for the named wheel. lifted=True adds the unit's `lift_mm` ground shift: veh_prep adds it to every vertex
    itself, but veh_lowpoly builds the wheels afresh, so it must lift them too or they sit off their axle node (LANCE-19 fix)."""
    wc = cfg["wheels"]
    side = 1 if name.startswith("wheel_l") else -1
    ent = wc["list"][int(name[7:])]
    y, z, rad = ent[:3]
    x0, x1 = wheel_x(cfg, ent)
    Vw, Fw = make_wheel(rad, x1 - x0, wc.get("seg", 36))
    Vw_ = wheel_world(cfg, side, y, z, Vw, x0)
    if lifted:
        Vw_ = Vw_ + np.array([0.0, 0.0, float(cfg.get("lift_mm", 0.0))])
    return Vw_, Fw


# ---- belts ------------------------------------------------------------------------------------------------------

def belt_envelope(tc, T, C, sign, res=10.0):
    xs = C[:, 0] * sign
    inx = (xs > tc["xlo"]) & (xs < tc["xhi"])
    pts = np.concatenate([T[inx].reshape(-1, 3), C[inx]])
    ys = np.arange(tc["y0"] - 200, tc["y1"] + 200, res)
    iy = np.round((pts[:, 1] - ys[0]) / res).astype(int)
    env = np.full(len(ys), 1e9)
    ok = (iy >= 0) & (iy < len(ys))
    np.minimum.at(env, iy[ok], pts[ok, 2])
    good = env < 1e8
    env = np.interp(ys, ys[good], env[good])
    return inx, ys, env


def classify_envelope(tc, T, C, sign):
    inx, ys, env = belt_envelope(tc, T, C, sign)
    slope = np.gradient(ndi.uniform_filter1d(env, 9), 10.0)
    cos = 1 / np.sqrt(1 + np.clip(slope, -3, 3) ** 2)
    tv = np.minimum(tc["thick"] / cos, 260)
    cy = np.clip(np.round((C[:, 1] - ys[0]) / 10.0).astype(int), 0, len(ys) - 1)
    return inx & (C[:, 1] > tc["y0"]) & (C[:, 1] < tc["y1"]) & (C[:, 2] < env[cy] + tv[cy]) & (C[:, 2] < tc["zmax"])


def loop_path(tc, step=2.0):
    """The closed belt path round the wheel circles (convex hull of the circles grown by `off`), side view (y, z), walked
    counter-clockwise: along the bottom toward +y (the rear), up round the rear wheel, back along the top. Resampled
    every `step` mm. Returns (y, z, s: arclength from the lowest-front point, tangent unit vectors, total length)."""
    from scipy.spatial import ConvexHull
    pts = []
    for (y, z, r) in tc["circles"]:
        a = np.radians(np.arange(0, 360, 3.0))
        pts.append(np.c_[y + (r + tc.get("off", 0.0)) * np.cos(a), z + (r + tc.get("off", 0.0)) * np.sin(a)])
    pts = np.concatenate(pts)
    h = pts[ConvexHull(pts).vertices]                 # counter-clockwise
    i0 = int(np.argmin(h[:, 1] - 0.001 * h[:, 0]))    # lowest, front-most
    h = np.roll(h, -i0, axis=0)
    h = np.r_[h, h[:1]]
    seg = np.hypot(*np.diff(h, axis=0).T)
    s = np.r_[0.0, np.cumsum(seg)]
    L = float(s[-1])
    ss = np.arange(0.0, L, step)
    yy = np.interp(ss, s, h[:, 0]); zz = np.interp(ss, s, h[:, 1])
    t = np.stack([np.roll(yy, -1) - np.roll(yy, 1), np.roll(zz, -1) - np.roll(zz, 1)], 1)
    t /= np.linalg.norm(t, axis=1, keepdims=True)
    return yy, zz, ss, t, L


def classify_loop(tc, T, C, sign):
    from scipy.spatial import cKDTree
    yy, zz, ss, t, L = loop_path(tc)
    xs = C[:, 0] * sign
    inx = (xs > tc["xlo"]) & (xs < tc["xhi"])
    d, _ = cKDTree(np.c_[yy, zz]).query(C[:, 1:3])
    return inx & (d < tc["thick"]) & (C[:, 2] < tc.get("zmax", 1e9))


def place_nodes(g, nodes, reparent=None, reset_rot=None):
    """cfg "nodes": {name: [x, y, z]}: move that node's pivot to this world position (game mm, Z up, forward -Y), keeping
    its children where they are in the world (their local translations are compensated; every ancestor must be unrotated,
    and so must the node itself, or its children's frame would turn)."""
    N = g["nodes"]
    for n_ in N:                                       # "reset_rot": nodes whose own rotation is dropped (a gun node the kit's pose replaces)
        if n_.get("name") in (reset_rot or []):
            n_.pop("rotation", None)
    par = {c: i for i, n in enumerate(N) for c in n.get("children", [])}
    byname = {n.get("name"): i for i, n in enumerate(N)}

    def world(i):
        t = np.zeros(3); first = True
        while i is not None:
            n = N[i]
            r = n.get("rotation")
            assert first or r is None or np.allclose(r, [0, 0, 0, 1], atol=1e-6), f"{n.get('name')} is rotated"
            t = t + np.array(n.get("translation", [0, 0, 0])); i = par.get(i); first = False
        return t
    for nm, newp in (reparent or {}).items():           # keep the world position, change the parent
        i, j = byname[nm], byname[newp]
        w0 = world(i)
        old = par.get(i)
        if old is not None:
            N[old]["children"].remove(i)
        N[j].setdefault("children", []).append(i); par[i] = j
        N[i]["translation"] = (np.array(N[i].get("translation", [0, 0, 0])) + w0 - world(i)).tolist()
    for nm, (x, y, z) in nodes.items():
        i = byname[nm]
        r = N[i].get("rotation")
        assert not N[i].get("children") or r is None or np.allclose(r, [0, 0, 0, 1], atol=1e-6), f"{nm} is rotated and has children"
        w0 = world(i)
        w1 = np.array([x, z, -y]) / 1000.0                 # game mm -> glTF m
        N[i]["translation"] = (np.array(N[i].get("translation", [0, 0, 0])) + (w1 - w0)).tolist()
        for c in N[i].get("children", []):
            N[c]["translation"] = (np.array(N[c].get("translation", [0, 0, 0])) - (w1 - w0)).tolist()
        print(f"node {nm}: pivot moved by {np.round((w1 - w0) * 1000).tolist()} mm (glTF)")


def main(unit=None):
    unit = unit or sys.argv[1]
    cfg = load_cfg(unit)
    SRC, DST = WORKS / f"{unit}_rigid", WORKS / f"{unit}_tracks"
    DST.mkdir(parents=True, exist_ok=True)
    z = np.load(SRC / "labels.npz")
    V, F, lab = z["V"], z["F"], z["lab"].copy()
    f = json.loads((SRC / "fit.json").read_text())
    names = list(f["node_names"])
    hull = names.index(cfg["hull"])
    for src, dst in cfg.get("merge", {}).items():          # kit label -> another part (a nearest-original label that is not a part here)
        lab[lab == names.index(src)] = names.index(dst)
    ds = cfg.get("drop_slivers")
    if ds:                                              # needle triangles left by the kit's simplification
        Tt = V[F]
        e = np.stack([np.linalg.norm(Tt[:, 1] - Tt[:, 0], axis=1), np.linalg.norm(Tt[:, 2] - Tt[:, 1], axis=1),
                      np.linalg.norm(Tt[:, 0] - Tt[:, 2], axis=1)], 1)
        area = 0.5 * np.linalg.norm(np.cross(Tt[:, 1] - Tt[:, 0], Tt[:, 2] - Tt[:, 0]), axis=1)
        bad = (e.max(1) > ds["min_edge"]) & (2 * area / (e.max(1) + 1e-9) < ds["max_alt"])
        print(f"drop_slivers: {int(bad.sum())} needle faces")
        F, lab = F[~bad], lab[~bad]
    new_nodes = []
    for sp in cfg.get("split", []):                      # carve a new part (a gun) out of one by face-centroid box
        Cc = V[F].mean(1)
        sel = (lab == names.index(sp["from"])) & np.all(Cc >= sp["min"], 1) & np.all(Cc <= sp["max"], 1)
        if sp["new"] not in names:                         # a gun node the original model never had: appended under its parent
            names.append(sp["new"]); new_nodes.append((sp["new"], sp["node_parent"], sp.get("pivot")))
            f["parent"][str(len(names) - 1)] = names.index(sp["node_parent"])
        lab[sel] = names.index(sp["new"])
        f["xform"][str(names.index(sp["new"]))] = np.eye(4).tolist()
        print(f"split: {int(sel.sum())} faces of {sp['from']} -> {sp['new']}")
    for fl in cfg.get("flatten", []):                      # "flatten": [{"min", "max", "y": plane}]: embossed marks (a brand name) pressed flat:
        lo_, hi_ = np.asarray(fl["min"], float), np.asarray(fl["max"], float)   # vertices in the box in front of the plane (y < plane) move onto it
        if fl.get("axis") == "z":                          # "axis": "z": a panel pressed flat from both sides onto z = plane (a roof's vent louvres)
            inb = np.all((V >= lo_) & (V <= hi_), 1)
            V = V.copy(); V[inb, 2] = fl["plane"]
            print(f"flatten: {int(inb.sum())} vertices onto z {fl['plane']}")
            continue
        inb = np.all((V >= lo_) & (V <= hi_), 1) & (V[:, 1] < fl["y"])
        V = V.copy(); V[inb, 1] = fl["y"]
        print(f"flatten: {int(inb.sum())} vertices onto y {fl['y']}")
    for db in cfg.get("drop_boxes", []):                   # "drop_boxes": [{"part", "min", "max"}]: faces of the part whose centroid lies in the box
        Cc_ = V[F].mean(1)
        sel_ = (lab == names.index(db["part"])) & np.all(Cc_ >= np.asarray(db["min"], float), 1) & np.all(Cc_ <= np.asarray(db["max"], float), 1)
        print(f"drop_boxes: {int(sel_.sum())} faces of {db['part']}")
        F, lab = F[~sel_], lab[~sel_]
    sss = cfg.get("drop_small_shells") or []                # "drop_small_shells": {"part", "max_faces"} or a list of them: loose bits (floating fragments)
    for ss in (sss if isinstance(sss, list) else [sss]):
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import connected_components
        pm = lab == names.index(ss["part"]); Fh = F[pm]
        g_ = coo_matrix((np.ones(3 * len(Fh)), (Fh.ravel(), np.roll(Fh, 1, 1).ravel())), shape=(len(V), len(V)))
        _, vc_ = connected_components(g_, directed=False); sh_ = vc_[Fh[:, 0]]; cn_ = np.bincount(sh_)
        small_ = (cn_ <= ss["max_faces"])[sh_]
        print(f"drop_small_shells: {int(small_.sum())} faces in {int(np.unique(sh_[small_]).size)} shells")
        keep_ = np.ones(len(F), bool); keep_[np.where(pm)[0][small_]] = False
        F, lab = F[keep_], lab[keep_]
    for dp in cfg.get("drop_parts", []):                  # parts the unit does not have (the Harasser's second launcher)
        keep_ = lab != names.index(dp)
        print(f"drop_parts: {int((~keep_).sum())} faces of {dp}")
        F, lab = F[keep_], lab[keep_]
    for sh in cfg.get("shift", []):                       # re-seat parts: own copies of the vertices, shifted
        ti = [names.index(p) for p in sh["parts"]]
        tf = np.where(np.isin(lab, ti))[0]
        vs = np.unique(F[tf])
        remap = -np.ones(len(V), int); remap[vs] = len(V) + np.arange(len(vs))
        d = np.array([sh.get("dx", 0.0), sh.get("dy", 0.0), sh.get("dz", 0.0)])
        V = np.concatenate([V, V[vs] + d]); F = F.copy(); F[tf] = remap[F[tf]]
        print(f"shift {sh['parts']} by {d.tolist()} mm")
    used = set(lab.tolist())
    for k in list(f["xform"]):                            # a part with no faces left is no part
        if int(k) not in used:
            del f["xform"][k]
    f["xform"] = {k: f["xform"][k] for k in sorted(f["xform"], key=int)}
    m = np.where(lab == hull)[0]
    T = V[F[m]]
    C = T.mean(1)
    n0 = len(names)
    n_orig = n0 - len(new_nodes)
    tc = cfg.get("tracks")
    if tc:
        units = [(u["sign"], u["name"], dict(tc, circles=u["circles"])) for u in tc["units"]] if tc.get("units") else \
            [(1, "track_l", tc), (-1, "track_r", tc)]       # "units": belts of their own (the MOG: track_l0, track_l1, track_r0, track_r1)
        for sign, nm, tcu in units:
            sel = (classify_envelope if tc["mode"] == "envelope" else classify_loop)(tcu, T, C, sign)
            names.append(nm)
            lab[m[sel]] = len(names) - 1
            print(f"{nm}: {int(sel.sum())} faces")
    # cut the fused wheels out of the hull, then add the full wheels (own geometry) as parts wheel_l0.. wheel_r7
    wc = cfg.get("wheels")
    axles, steer_of = {}, {}
    V2, F2, lab2 = [V], [F], [lab]
    if wc:
        m = np.where(lab == hull)[0]
        Cc = V[F[m]].mean(1)
        drop = np.zeros(len(m), bool)
        for sign in (1, -1):
            for w_ in wc["list"]:
                y, zc, rad = w_[:3]
                wx0, wx1 = wheel_x(cfg, w_)
                xs = Cc[:, 0] * sign
                drop |= ((xs > wx0 - 5) & (xs < wx1 + 5) & (Cc[:, 2] < wc.get("zcut", 1e9))
                         & (np.hypot(Cc[:, 1] - y, Cc[:, 2] - zc) < rad + wc.get("pad", 6.0)))
        print(f"hull: {int(drop.sum())} fused wheel faces removed")
        keep = np.ones(len(F), bool); keep[m[drop]] = False
        V2, F2, lab2 = [V], [F[keep]], [lab[keep]]
        off = len(V)
        steer = set(wc.get("steer", []))
        for sign, sname in ((1, "l"), (-1, "r")):
            for i, w_ in enumerate(wc["list"]):
                y, zc, rad = w_[:3]
                wx0, wx1 = wheel_x(cfg, w_)
                if i in steer:
                    names.append(f"steer_{sname}{i}"); steer_of[f"wheel_{sname}{i}"] = len(names) - 1
                Vw, Fw = wheel_geometry(cfg, f"wheel_{sname}{i}")
                names.append(f"wheel_{sname}{i}")
                V2.append(Vw); F2.append(Fw + off); lab2.append(np.full(len(Fw), len(names) - 1)); off += len(Vw)
                axles[names[-1]] = [sign * (wx0 + wx1) / 2, y, zc, rad]
    off_ = sum(len(v_) for v_ in V2)
    for ex in cfg.get("extras", []):          # "extras": own-geometry hull additions, e.g. {"kind": "container", "x", "y", "z0", "len", "wid", "h"} mm
        if ex["kind"] == "slab":                       # own-geometry track shell (and its mirror image)
            Vc, Fc = make_slab(ex["x0"], ex["x1"], ex["y0"], ex["y1"], ex["z0"], ex["z1"], ex.get("bevel", 70.0))
            parts_ = [(Vc, Fc)] + ([_orient(Vc * np.array([-1.0, 1.0, 1.0]), Fc)] if ex.get("mirror") else [])
        elif ex["kind"] == "wheel":                    # static own-geometry road wheel (a hull detail, not a wheel_* part)
            Vw_, Fw_ = make_wheel(ex["r"], ex["x1"] - ex["x0"], 36)
            Vw_ = Vw_ + np.array([ex["x0"], ex["y"], ex["z"]])
            parts_ = [(Vw_, Fw_)] + ([_orient(Vw_ * np.array([-1.0, 1.0, 1.0]), Fw_)] if ex.get("mirror") else [])
        else:
            assert ex["kind"] == "container", ex
            Vc, Fc = make_container(ex.get("x", 0.0), ex["y"], ex["z0"], ex["len"], ex["wid"], ex["h"], ex.get("taper", 0.22))
            parts_ = [(Vc, Fc)]
        for Vc, Fc in parts_:
            V2.append(Vc); F2.append(Fc + off_); lab2.append(np.full(len(Fc), hull)); off_ += len(Vc)
        print(f"extra {ex['kind']}: {sum(len(f_) for _, f_ in parts_)} faces")
    V, F, lab = np.concatenate(V2), np.concatenate(F2), np.concatenate(lab2)
    lift = float(cfg.get("lift_mm", 0.0))     # ground contact: the whole vehicle (geometry, axles, node tree) moves up by this
    if lift:
        V = V + np.array([0.0, 0.0, lift])
        for k in axles:
            axles[k][2] += lift
        print(f"lift {lift} mm")
    f["node_names"] = names
    parts_new = [k for k in range(n0, len(names)) if not names[k].startswith("steer_")]
    for k in range(n0, len(names)):
        nm = names[k]
        w_ = steer_of.get(nm)
        f["parent"][str(k)] = steer_of[nm] if nm in steer_of else hull
        if nm.startswith("steer_"):
            f["parent"][str(k)] = hull
        if k in parts_new:
            f["xform"][str(k)] = np.eye(4).tolist()
    f["xform"] = {k: f["xform"][k] for k in sorted(f["xform"], key=int)}
    (DST / "axles.json").write_text(json.dumps(axles, indent=1))
    np.savez_compressed(DST / "labels.npz", V=V, F=F, lab=lab)
    (DST / "fit.json").write_text(json.dumps(f, indent=1))
    # the node tree: the original's plus the belt nodes under the root (glTF metres, x +/-node_x_m)
    g, b = R.load_glb(str(ROOT / f"game/assets/vehicles/{unit}.glb"))
    root = g["scenes"][0]["nodes"][0]
    assert len(g["nodes"]) == n_orig, (len(g["nodes"]), n_orig)
    for nm, parent, piv in new_nodes:                  # carved-out guns: a node under its parent, pivot at `pivot` (mm, game frame)
        g["nodes"].append({"name": nm, "translation": [0.0, 0.0, 0.0]})
        pi = [i for i, n in enumerate(g["nodes"]) if n.get("name") == parent][0]
        g["nodes"][pi].setdefault("children", []).append(len(g["nodes"]) - 1)
    if tc:
        for nm, x in [(nm_, (1 if nm_.startswith("track_l") else -1) * tc["node_x_m"]) for nm_ in names[n0:] if nm_.startswith("track_")]:
            g["nodes"].append({"name": nm, "translation": [x, 0.0, 0.0]})
            g["nodes"][root].setdefault("children", []).append(len(g["nodes"]) - 1)
    for k in ("images", "textures", "samplers", "materials", "skins"):
        g.pop(k, None)
    if lift:
        tr = g["nodes"][root].setdefault("translation", [0.0, 0.0, 0.0]); tr[1] += lift / 1000.0
    rt = np.array(g["nodes"][root].get("translation", [0, 0, 0]))
    for nm in names[n0:]:
        if nm.startswith("track_"):
            continue
        if nm.startswith("steer_"):
            sname = "wheel_" + nm[6:]
            ax, ay, az, rad = axles[sname]
            g["nodes"].append({"name": nm, "translation": (np.array([ax, az, -ay]) / 1000.0 - rt).tolist()})
            g["nodes"][root].setdefault("children", []).append(len(g["nodes"]) - 1)
        elif nm in steer_of:
            g["nodes"].append({"name": nm, "translation": [0.0, 0.0, 0.0]})
            g["nodes"][len(g["nodes"]) - 2].setdefault("children", []).append(len(g["nodes"]) - 1)
        else:
            ax, ay, az, rad = axles[nm]      # wheel nodes pivot on their axle (glTF metres, relative to the root)
            g["nodes"].append({"name": nm, "translation": (np.array([ax, az, -ay]) / 1000.0 - rt).tolist()})
            g["nodes"][root].setdefault("children", []).append(len(g["nodes"]) - 1)
    place_nodes(g, {k: [v[0], v[1], v[2] + lift] for k, v in cfg.get("nodes", {}).items()}, cfg.get("reparent", {}), cfg.get("reset_rot"))
    assert [n.get("name") for n in g["nodes"][n_orig:]] == names[n_orig:], "glb node order must match fit.json node_names"
    for fn in (f"{unit}_base.glb", "skel.glb"):   # skel.glb: what v3_mech.v2_setup reads from the work dir
        R.GlbWriter(g, b).write(str(DST / fn))
    print("wrote", DST)


if __name__ == "__main__":
    main()
