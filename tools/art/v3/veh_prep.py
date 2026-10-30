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


def wheel_width(cfg):
    return cfg["wheels"]["x1"] - cfg["wheels"]["x0"]


def wheel_world(cfg, side, y, z, V):
    """The wheel placed on its axle: side +1 (track_l, +X) is the local frame as is, side -1 turned half a turn about
    the vertical axis (a rotation, so the shared UVs keep their handedness)."""
    W = V + np.array([cfg["wheels"]["x0"], 0, 0])
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
    y, z, rad = wc["list"][int(name[7:])][:3]
    Vw, Fw = make_wheel(rad, wheel_width(cfg), wc.get("seg", 36))
    Vw_ = wheel_world(cfg, side, y, z, Vw)
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
            for (y, zc, rad) in [w[:3] for w in wc["list"]]:
                xs = Cc[:, 0] * sign
                drop |= ((xs > wc["x0"] - 5) & (xs < wc["x1"] + 5) & (Cc[:, 2] < wc.get("zcut", 1e9))
                         & (np.hypot(Cc[:, 1] - y, Cc[:, 2] - zc) < rad + wc.get("pad", 6.0)))
        print(f"hull: {int(drop.sum())} fused wheel faces removed")
        keep = np.ones(len(F), bool); keep[m[drop]] = False
        V2, F2, lab2 = [V], [F[keep]], [lab[keep]]
        off = len(V)
        steer = set(wc.get("steer", []))
        for sign, sname in ((1, "l"), (-1, "r")):
            for i, (y, zc, rad) in enumerate([w[:3] for w in wc["list"]]):
                if i in steer:
                    names.append(f"steer_{sname}{i}"); steer_of[f"wheel_{sname}{i}"] = len(names) - 1
                Vw, Fw = wheel_geometry(cfg, f"wheel_{sname}{i}")
                names.append(f"wheel_{sname}{i}")
                V2.append(Vw); F2.append(Fw + off); lab2.append(np.full(len(Fw), len(names) - 1)); off += len(Vw)
                axles[names[-1]] = [sign * (wc["x0"] + wc["x1"]) / 2, y, zc, rad]
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
