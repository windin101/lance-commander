#!/usr/bin/env python3
"""HD vehicle (or copter) from a licensed third-party sculpt: STL -> simplified, fitted, rigidly skinned, painted.

    python3 -I tools/art/stl_hd.py <asset> --stl model.stl [--stl part2.stl ...] [--kind vehicles|mechs]
        [--joints J.json] [--views V.png] [--install] --source "Title by Author, URL" --licence "CC BY-SA 4.0"

The rigid-asset counterpart of stl_rig.py (which un-poses walking mechs). Printable kits are piles of
overlapping, non-manifold shells, so the Hunyuan path's decimate/unwrap/bake (ComfyUI) shreds them (tried
2026-10-19: spikes everywhere); this works on the triangles directly, like stl_rig.py:
  1. prep: load the STL(s) (mm, Z up). J.json "place" moves a numbered component (see --views) into place;
     "parts" moves a kit's loose piece (turret, launcher) onto the hull
     ([{"file": i, "move": [x, y, z], "rot_z": deg}], i = index of --stl, raw mm); "drop" lists components to
     discard (by the number the --views sheet prints); components under "min_share" (default 0.3 %) of the
     triangles go anyway (sprues, loose pins); "base_cut" (raw z) cuts a display base.
  2. simplify: vertex clustering on a grid sized to reach "faces" triangles (default 40000).
  3. fit to the original model (glTF frame): yaw search (5 deg; "yaw" pins it, "mirror": true allows a mirror)
     with the scale from the ground plan and the bottom on the ground, then rigid ICP ("no_icp": true skips it).
     "scale" multiplies the plan scale.
  4. skin: each triangle follows the original part nearest to it (a turret goes with its turret joint).
     J.json "parts_box": [{"node", "min", "max"} in fitted metres, glTF frame] overrides that.
  5. paint: each triangle votes over its 8 nearest original surface points for the team-paint class (base/hl1/hl2)
     or one of the original mask's own colours (clustered: white liveries, hazard stripes), then a neighbour majority
     pass removes speckle; stl_rig's palette carries the colours. "bounds": true (after the fit) matches the original's
     length, width and height separately; "stretch": [x, y, z] multiplies them; "nudge": [x, y, z] m moves the fit.
  6. write <asset>_hd.glb + _hd_paint.bin to original/hd/<asset>/stl/, or with --install to game/assets/<kind>/
     plus original/hd/<asset>/provenance.json (kind "adapted", source, licence) for tools/art/credits.py.
--views draws the raw components (numbered), the fitted result's paint and parts, and the original's surface.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cad_mech as C  # noqa: E402
import hd_mech  # noqa: E402
import hd_rig as R  # noqa: E402
import stl_rig  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PAL = [(230, 25, 75), (60, 180, 75), (255, 225, 25), (0, 130, 200), (245, 130, 48), (145, 30, 180), (70, 240, 240),
       (240, 50, 230), (210, 245, 60), (250, 190, 212), (0, 128, 128), (170, 110, 40)]


def components(T):
    """Connected components (shared rounded vertices), numbered biggest first."""
    key = np.unique(np.round(T.reshape(-1, 3), 3), axis=0, return_inverse=True)[1].reshape(-1, 3)
    par = np.arange(key.max() + 1)

    def f(x):
        r = x
        while par[r] != r:
            r = par[r]
        while par[x] != r:
            par[x], x = r, par[x]
        return r
    for a, b, c in key:
        ra = f(a)
        par[f(b)] = ra
        par[f(c)] = ra
    lab = np.unique([f(v) for v in key[:, 0]], return_inverse=True)[1]
    order = np.argsort(-np.bincount(lab))
    rank = np.empty_like(order)
    rank[order] = np.arange(len(order))
    return rank[lab]


def _clustered(V, n):
    cell = np.ptp(V, 0).max() / n
    key = np.floor((V - V.min(0)) / cell).astype(np.int64)
    uk, inv = np.unique(key, axis=0, return_inverse=True)
    t = inv.reshape(-1, 3)
    t = t[(t[:, 0] != t[:, 1]) & (t[:, 1] != t[:, 2]) & (t[:, 0] != t[:, 2])]
    t = t[np.unique(np.sort(t, 1), axis=0, return_index=True)[1]]
    return uk, inv, t, cell


def cluster(T, faces):
    """Vertex-clustering simplification of a triangle soup to about `faces` triangles."""
    V = T.reshape(-1, 3)
    lo, hi = 40, 3000
    while hi - lo > 4:
        n = (lo + hi) // 2
        if len(_clustered(V, n)[2]) > faces:
            hi = n
        else:
            lo = n
    uk, inv, t, cell = _clustered(V, lo)
    pos = np.zeros((len(uk), 3))
    np.add.at(pos, inv, V)
    pos /= np.bincount(inv)[:, None]
    return pos[t], cell


def shade(T, col, k_px=420):
    """Three-quarter flat-shaded render of glTF-frame triangles (x, y up, z) with per-triangle colours."""
    a, b = np.radians(35), np.radians(25)
    P = T.reshape(-1, 3)
    P = np.c_[P[:, 0], -P[:, 2], P[:, 1]]
    Rz = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    Rx = np.array([[1, 0, 0], [0, np.cos(b), -np.sin(b)], [0, np.sin(b), np.cos(b)]])
    P = (P @ (Rx @ Rz).T).reshape(-1, 3, 3)
    lo, hi = P.reshape(-1, 3).min(0), P.reshape(-1, 3).max(0)
    k = k_px / max(hi[0] - lo[0], hi[2] - lo[2])
    im = Image.new("RGB", (k_px + 20, k_px + 20), "white")
    d = ImageDraw.Draw(im)
    n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    L = np.array([0.4, -0.5, 0.75])
    L /= np.linalg.norm(L)
    br = 0.45 + 0.55 * np.abs(n @ L)
    for t in np.argsort(P[:, :, 1].mean(1))[::-1]:
        d.polygon([((P[t, i, 0] - lo[0]) * k + 10, k_px + 10 - (P[t, i, 2] - lo[2]) * k) for i in range(3)],
                  fill=tuple(int(c * br[t]) for c in col[t]))
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("asset")
    ap.add_argument("--stl", action="append", required=True)
    ap.add_argument("--kind", default="vehicles", choices=["vehicles", "mechs"])
    ap.add_argument("--joints")
    ap.add_argument("--views")
    ap.add_argument("--source", default="")
    ap.add_argument("--licence", default="")
    ap.add_argument("--install", action="store_true")
    a = ap.parse_args()
    over = json.loads(Path(a.joints).read_text()) if a.joints and Path(a.joints).exists() else {}
    folder = hd_mech.KINDS[a.kind][0]
    og, ob = R.load_glb(str(ROOT / f"game/assets/{folder}/{a.asset}.glb"))
    names = {n.get("name"): i for i, n in enumerate(og["nodes"])}

    # 1. prep
    parts = [stl_rig.load_stl(p) for p in a.stl]
    for spec in over.get("parts", []):
        T = parts[spec["file"]]
        if "rot_z" in spec:
            r = np.radians(spec["rot_z"])
            c = T.reshape(-1, 3).mean(0)
            T = (T - c) @ np.array([[np.cos(r), -np.sin(r), 0], [np.sin(r), np.cos(r), 0], [0, 0, 1]]).T + c
        parts[spec["file"]] = T + np.asarray(spec.get("move", [0, 0, 0]), float)
    T = np.concatenate(parts)
    if "base_cut" in over:
        T = T[T[..., 2].min(1) >= over["base_cut"]]
    comp = components(T)
    share = np.bincount(comp) / len(T)
    for spec in over.get("place", []):  # J.json "place": [{"comp": n, "move": [x, y, z], "rot_z": deg, "rot_x": deg, "rot_y": deg}]
        m = comp == spec["comp"]       # raw mm: put a kit's loose piece (turret, launcher) where it mounts; rotations about its centre
        P_ = T[m].reshape(-1, 3); c_ = P_.mean(0)
        for ax, key_ in ((2, "rot_z"), (0, "rot_x"), (1, "rot_y")):
            if key_ in spec:
                r_ = np.radians(spec[key_]); i, j = [k for k in range(3) if k != ax]
                M = np.eye(3); M[i, i] = M[j, j] = np.cos(r_); M[i, j], M[j, i] = -np.sin(r_), np.sin(r_)
                P_ = (P_ - c_) @ M.T + c_
        T[m] = (P_ + np.asarray(spec.get("move", [0, 0, 0]), float)).reshape(-1, 3, 3)
    keep = (share[comp] >= over.get("min_share", 0.003)) & ~np.isin(comp, over.get("drop", []))
    print(f"{a.asset}: {len(T)} tris, {len(share)} components (largest shares "
          f"{np.round(np.sort(share)[::-1][:8], 3).tolist()}); kept {int(keep.sum())}")
    raw_view = None
    if a.views:
        big = [c for c in range(len(share)) if share[c] >= 0.001][:12]
        raw_view = shade(np.stack([T[..., 0], T[..., 2], -T[..., 1]], -1),
                         np.array([PAL[c % len(PAL)] if c in big else (200, 200, 200) for c in comp]))
        d = ImageDraw.Draw(raw_view)
        for i, c in enumerate(big):
            d.rectangle([4, 4 + 14 * i, 14, 14 + 14 * i], fill=PAL[c % len(PAL)])
            d.text((18, 4 + 14 * i), f"{c}: {share[c] * 100:.1f}%" + ("" if keep[comp == c].any() else " (dropped)"), fill="black")
        # top view (raw mm, x right, y up = raw +Y), each big component's number at its centre: for "parts" moves
        top = Image.new("RGB", (440, 440), "white"); dt = ImageDraw.Draw(top)
        V2 = T[..., :2].reshape(-1, 2); lo2, hi2 = V2.min(0), V2.max(0); k2 = 400 / max(np.ptp(V2, 0))
        for t_ in np.argsort(T[..., 2].mean(1)):
            c_ = comp[t_]
            dt.polygon([((T[t_, i, 0] - lo2[0]) * k2 + 20, 420 - (T[t_, i, 1] - lo2[1]) * k2) for i in range(3)],
                       fill=PAL[c_ % len(PAL)] if c_ in big else (200, 200, 200))
        for c in big:
            cc = T[comp == c].reshape(-1, 3).mean(0)
            dt.text(((cc[0] - lo2[0]) * k2 + 20, 420 - (cc[1] - lo2[1]) * k2), str(c), fill="black")
        dt.text((4, 4), f"top, raw mm: x {lo2[0]:.0f}..{hi2[0]:.0f}, y {lo2[1]:.0f}..{hi2[1]:.0f}, z {T[..., 2].min():.0f}..{T[..., 2].max():.0f}", fill="black")
        raw_top = top
    mounts = []  # J.json "mount": [{"comp": n | [n, ...], "node": original part, "on": "hull" | earlier node, "rot": deg about
    # the vertical, "offset": [x, z] m, "lift": m}]: a kit's loose turret or launcher, seated on the joint it turns on
    for spec in over.get("mount", []):
        cs = spec["comp"] if isinstance(spec["comp"], list) else [spec["comp"]]
        m = np.isin(comp, cs)
        mounts.append((spec, T[m]))
        keep &= ~m
    T = T[keep]

    # 2. simplify (raw mm, Z up)
    faces = int(over.get("faces", 40000))
    tot = len(T) + sum(len(x) for _, x in mounts)
    S, cell = cluster(T, int(faces * len(T) / tot))
    mounts = [(spec, cluster(x, max(800, int(faces * len(x) / tot)))[0]) for spec, x in mounts]
    print(f"  simplified to {len(S)} tris (grid cell {cell:.3f} raw mm)" + (f" + mounts {[len(x) for _, x in mounts]}" if mounts else ""))

    # 3. fit in the glTF frame (x, y up, z); the original is in metres
    G = np.stack([S[..., 0], S[..., 2], -S[..., 1]], -1).reshape(-1, 3)
    samples_all, sample_uv, owners = R.original_samples(og, ob)
    sub = lambda i: [i] + [d for c in og["nodes"][i].get("children", []) for d in sub(c)]
    mounted = [d for spec, _ in mounts for d in sub(names[spec["node"]])]
    samples = samples_all[~np.isin(owners, mounted)] if mounts else samples_all  # fit the hull to the original's hull
    flat = np.arange(len(G)).reshape(-1, 3)
    q = R.area_samples(G, flat, n=30000)
    tree_p = cKDTree(samples)
    plan_p = np.hypot(np.ptp(samples[:, 0]), np.ptp(samples[:, 2]))
    best = None
    for mirror in ((False, True) if over.get("mirror") else (False,)):
        for deg in ([over["yaw"]] if "yaw" in over else range(0, 360, 5)):
            r = R.yaw(deg) @ np.diag([-1.0 if mirror else 1.0, 1, 1])
            qr = q @ r.T
            s = plan_p / np.hypot(np.ptp(qr[:, 0]), np.ptp(qr[:, 2])) * over.get("scale", 1.0)
            qs = qr * s
            t = np.array([(samples[:, 0].max() + samples[:, 0].min()) / 2 - (qs[:, 0].max() + qs[:, 0].min()) / 2,
                          samples[:, 1].min() - qs[:, 1].min(),
                          (samples[:, 2].max() + samples[:, 2].min()) / 2 - (qs[:, 2].max() + qs[:, 2].min()) / 2])
            score = R.chamfer(qs + t, tree_p, samples)
            if best is None or score < best[0]:
                best = (score, r, s, t, deg, mirror)
    score0, r, s, t, deg, mirror = best
    Gf = (G @ r.T) * s + t
    if not over.get("no_icp"):
        _, (Ri, si, ti) = R.icp((q @ r.T) * s + t, samples)
        Gf = si * (Gf @ Ri.T) + ti
        Gf[:, 1] -= Gf[:, 1].min() - samples[:, 1].min()  # keep it on the ground
    Gf = Gf.reshape(-1, 3, 3)
    if mirror:
        Gf = Gf[:, [0, 2, 1]]
    if over.get("bounds") or over.get("stretch"):  # J.json "bounds": true matches length, width and height separately
        V_ = Gf.reshape(-1, 3)                        # (a sculpt stockier than the original); "stretch": [x, y, z] multiplies
        if over.get("bounds"):
            V_ = R.match_bounds(V_, samples, q_surf=R.area_samples(V_, flat, n=30000))
        if over.get("stretch"):
            c_ = np.array([(V_[:, 0].max() + V_[:, 0].min()) / 2, V_[:, 1].min(), (V_[:, 2].max() + V_[:, 2].min()) / 2])
            V_ = (V_ - c_) * np.asarray(over["stretch"], float) + c_
        Gf = V_.reshape(-1, 3, 3)
    if over.get("nudge"):  # J.json "nudge": [x, y, z] m after the fit: the bounds centring is off when a gun sticks out
        Gf = Gf + np.asarray(over["nudge"], float)
    fit = R.chamfer(R.area_samples(Gf.reshape(-1, 3), flat, n=30000), tree_p, samples)
    Wn = R.world_matrices(og)
    forced = np.full(len(Gf), -1)
    placed = {"hull": Gf}
    for spec, X in mounts:  # same scale and turn as the hull; centred on the joint, seated on what is under it
        M = np.stack([X[..., 0], X[..., 2], -X[..., 1]], -1).reshape(-1, 3)
        M = (M @ r.T) * s
        if not over.get("no_icp"):
            M = si * (M @ Ri.T)
        if spec.get("rot"):
            M = M @ R.yaw(spec["rot"]).T
        M = M.reshape(-1, 3, 3)
        if mirror:
            M = M[:, [0, 2, 1]]
        piv = Wn[names[spec["node"]]][:3, 3]
        off = spec.get("offset", [0, 0])
        V_ = M.reshape(-1, 3)
        M = M + np.array([piv[0] + off[0] - (V_[:, 0].max() + V_[:, 0].min()) / 2, 0, piv[2] + off[1] - (V_[:, 2].max() + V_[:, 2].min()) / 2])
        base = placed.get(spec.get("on", "hull"), Gf)
        V_ = M.reshape(-1, 3)
        Bc = base.reshape(-1, 3)
        under = (np.abs(Bc[:, 0] - V_[:, 0].mean()) < 0.35 * np.ptp(V_[:, 0])) & (np.abs(Bc[:, 2] - V_[:, 2].mean()) < 0.35 * np.ptp(V_[:, 2]))
        seat = Bc[under, 1].max() if under.any() else piv[1]
        M[..., 1] += seat + spec.get("lift", 0.0) - V_[:, 1].min()
        placed[spec["node"]] = M
        forced = np.concatenate([forced, np.full(len(M), names[spec["node"]])])
        Gf = np.concatenate([Gf, M])
        print(f"  mount {spec['comp']} -> {spec['node']}: {len(M)} tris at x {piv[0] + off[0]:.2f} z {piv[2] + off[1]:.2f}, seated at y {seat:.2f} m")
    samples = samples_all
    tree_p = cKDTree(samples)  # skin and paint against the whole original
    print(f"  fit: yaw {deg}{' mirrored' if mirror else ''}, {s * 1000:.1f} game mm per raw mm, chamfer {score0:.3f} -> {fit:.3f} m")

    # 4. skin
    Cn = Gf.mean(1)
    near = tree_p.query(Cn)[1]
    owner = owners[near].copy()
    owner[forced >= 0] = forced[forced >= 0]
    for box in over.get("parts_box", []):
        m = (Cn >= box["min"]).all(1) & (Cn <= box["max"]).all(1)
        owner[m] = names[box["node"]]

    # 5. paint (since 2026-10-20): every triangle votes over its 8 nearest original surface points, then a majority pass
    # over its 12 nearest triangles cleans speckle. Team paint is the pure channels (MechPaint); every other colour of
    # the original's mask is kept as itself (up to 8 colour clusters: white liveries, hazard stripes, glass), not snapped
    # to the mechs' metal/dark/glass greys.
    marr = np.asarray(Image.open(hd_mech.paint_source(a.asset, a.kind)).convert("RGB")).astype(float)
    def colour_at(uv_):
        return marr[np.clip((uv_[..., 1] % 1) * marr.shape[0], 0, marr.shape[0] - 1).astype(int),
                    np.clip((uv_[..., 0] % 1) * marr.shape[1], 0, marr.shape[1] - 1).astype(int)]
    def classes(px):
        mx = px.max(-1)
        pure = (mx > 40) & ((px < 0.35 * mx[..., None]).sum(-1) == 2)
        return pure, px.argmax(-1)
    allpx = colour_at(sample_uv)
    pure_s, _ = classes(allpx)
    other = allpx[~pure_s]
    fixed_cols = []
    if len(other):  # k-means on the original's non-team colours
        rng = np.random.default_rng(0)
        pts_ = other[rng.choice(len(other), min(len(other), 20000), replace=False)]
        cent = pts_[rng.choice(len(pts_), min(8, len(pts_)), replace=False)]
        for _ in range(20):
            lab_ = ((pts_[:, None] - cent[None]) ** 2).sum(2).argmin(1)
            cent = np.array([pts_[lab_ == k].mean(0) if (lab_ == k).any() else cent[k] for k in range(len(cent))])
        share_ = np.bincount(lab_, minlength=len(cent)) / len(lab_)
        fixed_cols = [tuple(int(v) for v in c_) for c_, sh in zip(cent, share_) if sh >= 0.02]
    for k, c_ in enumerate(fixed_cols):
        C.PAINT[f"orig{k}"] = c_  # extra palette cells (the palette has 16; base/hl1/hl2/metal/dark/glass use 6)
    fixed = [f"orig{k}" for k in range(len(fixed_cols))] or ["metal"]
    fr = np.array([C.PAINT[k] for k in fixed], float)
    kn = tree_p.query(Cn, k=8)[1]
    px = colour_at(sample_uv[kn])                         # (n, 8, 3)
    pure, ch = classes(px)
    lab = np.where(pure, ch, 3 + ((px[..., None, :] - fr[None, None]) ** 2).sum(-1).argmin(-1))  # 0..2 team, 3.. fixed
    vote = np.apply_along_axis(lambda r_: np.bincount(r_, minlength=3 + len(fixed)).argmax(), 1, lab)
    tri_tree = cKDTree(Cn)
    nb = tri_tree.query(Cn, k=min(12, len(Cn)))[1]
    for _ in range(2):
        vote = np.apply_along_axis(lambda r_: np.bincount(r_, minlength=3 + len(fixed)).argmax(), 1, vote[nb])
    names_ = np.array(["hl1", "hl2", "base"] + fixed, dtype=object)  # argmax channel 0 = R = hl1, 1 = G = hl2, 2 = B = base
    paint = names_[vote]
    print("  parts:", {og["nodes"][o]["name"]: int((owner == o).sum()) for o in sorted(set(owner.tolist()))},
          "paint:", {k: int((paint == k).sum()) for k in C.PAINT if (paint == k).any()})

    # 6. write
    slots = {kk: i for i, kk in enumerate(C.PAINT)}
    uvs = np.repeat(np.array([(((slots[p] % C.GRID) + 0.5) / C.GRID, ((slots[p] // C.GRID) + 0.5) / C.GRID) for p in paint]), 3, axis=0)
    pos = Gf.reshape(-1, 3)
    tris = np.arange(len(pos)).reshape(-1, 3)
    dest = ROOT / f"game/assets/{folder}" if a.install else ROOT / f"original/hd/{a.asset}/stl"
    dest.mkdir(parents=True, exist_ok=True)
    stl_rig.write(og, ob, pos, R.vertex_normals(pos, tris), uvs, np.repeat(owner, 3), tris, slots, dest, a.asset)
    print(f"  {len(tris)} tris -> {dest}")
    if a.views:
        used = sorted(set(owner.tolist()))
        sheet = Image.new("RGB", (440 * 5, 470), "white")
        sheet.paste(raw_view, (0, 0)); sheet.paste(raw_top, (1760, 0))
        sheet.paste(shade(Gf, np.array([C.PAINT[p] for p in paint])), (440, 0))
        sheet.paste(shade(Gf, np.array([PAL[used.index(o) % len(PAL)] for o in owner])), (880, 0))
        S0 = samples[np.random.default_rng(0).choice(len(samples), min(len(samples), 40000), replace=False)]
        sp = 0.01 * np.ptp(samples, 0).max()
        sheet.paste(shade(S0[:, None, :] + np.array([[0, 0, 0], [sp, 0, 0], [0, sp, 0]]), np.full((len(S0), 3), 150)), (1320, 0))
        d = ImageDraw.Draw(sheet)
        d.text((6, 448), "raw components (numbered, biggest first)", fill="black")
        d.text((446, 448), "fitted: paint", fill="black")
        d.text((886, 448), ("parts: " + ", ".join(og["nodes"][o]["name"] for o in used))[:70], fill="black")
        d.text((1326, 448), f"original surface; chamfer {fit:.3f} m", fill="black")
        sheet.save(a.views)
    if a.install:
        work = ROOT / f"original/hd/{a.asset}"
        work.mkdir(parents=True, exist_ok=True)
        (work / "provenance.json").write_text(json.dumps({
            "asset": a.asset, "kind": "adapted", "class": a.kind, "source": a.source, "licence": a.licence,
            "tool": "tools/art/stl_hd.py", "stl": [Path(p).name for p in a.stl], "joints": over,
            "fit_m": round(float(fit), 3), "tris": int(len(tris)), "built_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, indent=2) + "\n")


if __name__ == "__main__":
    main()
