"""v3 mask and wear layers (tools/art/v3/v3_mech.py stages `mask` and `wear`). Everything is authored per texel of the
chassis atlas from the Cycles bakes (bake/: fid, pos, nrm, ao, edge) and per game-mesh face from the settings'
"mask" rules, so it is baked into mipmapped textures: nothing procedural runs per pixel in the game.

Outputs in <work>/tex/ (game names in brackets):
  albedo.png [<mech>_albedo.png]  sRGB RGBA. RGB: what shows where the paint doesn't (bare metal of chips and housings,
                                  grime, dust, soot, glass tint); A: paint coverage (1 = the scheme's paint).
  orm.png    [<mech>_orm.png]     linear RGBA. R ambient occlusion, G roughness, B metallic, A paint shade (panel tone,
                                  cavity darkening, chip lips) that multiplies the scheme colour.
  ids.png    [<mech>_ids.png]     RGBA8, sampled nearest for R. R region code (paint regions 0-7 as
                                  PaintScheme.REGIONS, 8 bare metal, 9 glass, 10 emissive lens), G piping, B stripe,
                                  A limb band.
  camo.png   [<mech>_camo.png]    linear RGBA, object-space pattern fields (R large, G medium, B small blotches) and A
                                  exposure (up-facing, low on the legs) for the mission's dust and snow.
  normal.png [<mech>_normal.png]  the baked tangent-space normal map (bevelled sculpt).
Zones: 0 paint, 1 piping/trim, 2 bare metal, 3 glass, 4 emissive.
"""
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

REGIONS = ["body", "head", "arms", "upper_legs", "lower_legs", "feet", "weapons", "plates"]
R_METAL, R_GLASS, R_EMIT = 8, 9, 10
PART_REGION = {"a-hip": "body", "a_torso": "body", "a_ruarm": "plates", "a_luarm": "plates", "a_rlarm": "arms",
               "a_llarm": "arms", "a_rgun": "arms", "a_lgun": "arms", "a_luleg": "upper_legs", "a_ruleg": "upper_legs",
               "a_llleg": "lower_legs", "a_rlleg": "lower_legs", "a_lfoot": "feet", "a_rfoot": "feet"}


# --- noise (object space, so it is seamless across UV islands) ---------------------------------------------------

def _hash3(ix, iy, iz, seed):
    h = (ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791) ^ (seed * 2654435761)
    h = (h ^ (h >> 13)) * 1274126177
    h = h ^ (h >> 16)
    return (h & 0xFFFFFF).astype(np.float32) / float(0xFFFFFF)


def value_noise(X, scale, seed=0):
    """Smooth value noise in [0, 1] at points X (n, 3) mm, feature size `scale` mm."""
    q = X / scale
    i = np.floor(q).astype(np.int64)
    f = q - i
    f = f * f * (3 - 2 * f)
    out = np.zeros(len(X), np.float32)
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2])
                out += w * _hash3(i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz, seed)
    return out


def fbm(X, scale, octaves=4, seed=0, gain=0.5):
    s, a, tot, out = scale, 1.0, 0.0, np.zeros(len(X), np.float32)
    for o in range(octaves):
        out += a * value_noise(X, s, seed + 17 * o)
        tot += a; s *= 0.5; a *= gain
    return out / tot


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def srgb_to_lin(c):
    c = np.asarray(c, np.float32)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


# --- per game-mesh face classification --------------------------------------------------------------------------

def face_frames(low, fit, names):
    """Per low face: part name, centroid and normal in the rest frame and in the sculpt's own frame."""
    P, F = low["P"], low["F"]
    T = P[F]
    c = T.mean(1)
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    part = np.array(names)[low["part"]]
    cs, ns = c.copy(), n.copy()
    for p in np.unique(part):
        M = np.linalg.inv(np.array(fit["xform"][p]))
        m = part == p
        cs[m] = c[m] @ M[:3, :3].T + M[:3, 3]
        ns[m] = n[m] @ M[:3, :3].T
    return part, c, n, cs, ns


def in_box(X, box):
    lo, hi = np.asarray(box["min"], float), np.asarray(box["max"], float)
    return np.all((X >= lo) & (X <= hi), axis=1)


def chamfer_faces(low, n, max_width=220.0):
    """Faces that are narrow bevels between two larger faces (the kit's chamfered plate edges): 25-65 degrees to two
    neighbours that are themselves 50-130 degrees apart."""
    F = low["F"]
    e = np.c_[F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]].reshape(-1, 2)
    fi = np.repeat(np.arange(len(F)), 3)
    key = np.sort(e, 1)
    o = np.lexsort(key.T[::-1]); k2, f2 = key[o], fi[o]
    same = (k2[1:] == k2[:-1]).all(1)
    a, b = f2[:-1][same], f2[1:][same]
    nb = [[] for _ in range(len(F))]
    for x, y in zip(a, b):
        nb[x].append(y); nb[y].append(x)
    T = low["P"][F]
    ed = np.linalg.norm(np.roll(T, -1, 1) - T, axis=2)
    area = 0.5 * np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1)
    width = 2 * area / np.maximum(ed.max(1), 1e-9)
    out = np.zeros(len(F), bool)
    for f in range(len(F)):
        if width[f] > max_width or len(nb[f]) < 2:
            continue
        ang = [np.degrees(np.arccos(np.clip(n[f] @ n[g], -1, 1))) for g in nb[f]]
        cand = [g for g, an in zip(nb[f], ang) if 25 <= an <= 65]
        if len(cand) < 2:
            continue
        ok = False
        for i in range(len(cand)):
            for j in range(i + 1, len(cand)):
                aa = np.degrees(np.arccos(np.clip(n[cand[i]] @ n[cand[j]], -1, 1)))
                if 50 <= aa <= 130:
                    ok = True
        out[f] = ok
    # grow along connected chamfer strips of the same orientation so a bevel split into triangles stays whole
    return out


_PATCH_CACHE = {}


def sculpt_panels(work, deg=12.0):
    """Flat panels of the sculpt: faces joined across edges flatter than `deg` (any sharp edge separates)."""
    key = ("panel", str(work), deg)
    if key in _PATCH_CACHE:
        return _PATCH_CACHE[key]
    import v3_stages as S
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    z = np.load(work / "sculpt.npz"); P, F = z["P"], z["F"]
    fa, fb, ev, dist, ang, concave, Cn, N = S.face_graph(P, F)
    join = ang < np.radians(deg)
    n = len(F)
    nc, comp = connected_components(coo_matrix((np.ones(join.sum()), (fa[join], fb[join])), shape=(n, n)), directed=False)
    T = P[F]
    A = 0.5 * np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1)
    area = np.bincount(comp, weights=A, minlength=nc)
    cen = np.stack([np.bincount(comp, weights=A * Cn[:, k], minlength=nc) for k in range(3)], 1) / np.maximum(area[:, None], 1e-9)
    _PATCH_CACHE[key] = (comp, area, cen, N)
    return _PATCH_CACHE[key]


def panel_shape(work, deg=12.0):
    """Per flat panel: length and width (mm) from the spread of its vertices along its two in-plane axes."""
    key = ("shape", str(work), deg)
    if key in _PATCH_CACHE:
        return _PATCH_CACHE[key]
    comp, area, cen, N = sculpt_panels(work, deg)
    z = np.load(work / "sculpt.npz"); P, F = z["P"], z["F"]
    nc = len(area)
    L = np.zeros(nc); Wd = np.zeros(nc)
    order = np.argsort(comp, kind="stable")
    starts = np.searchsorted(comp[order], np.arange(nc + 1))
    for c in range(nc):
        fs = order[starts[c]:starts[c + 1]]
        if area[c] < 5e4 or len(fs) < 2:
            continue
        V = P[np.unique(F[fs])]
        mu = V.mean(0)
        w_, vec = np.linalg.eigh(np.cov((V - mu).T) + np.eye(3) * 1e-6)
        t1 = (V - mu) @ vec[:, 2]; t2 = (V - mu) @ vec[:, 1]
        L[c] = np.ptp(t1); Wd[c] = np.ptp(t2)
    _PATCH_CACHE[key] = (L, Wd)
    return L, Wd


def sculpt_patches(work, deg=25.0):
    """Panels of the sculpt: faces joined across every edge except sharp concave creases (where one kit box meets
    another). Returns patch id per sculpt face, patch area, area-weighted centroid (sculpt frame)."""
    import v3_stages as S
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    z = np.load(work / "sculpt.npz"); P, F = z["P"], z["F"]
    fa, fb, ev, dist, ang, concave, Cn, N = S.face_graph(P, F)
    join = ~(concave & (ang > np.radians(deg)))
    n = len(F)
    nc, comp = connected_components(coo_matrix((np.ones(join.sum()), (fa[join], fb[join])), shape=(n, n)), directed=False)
    T = P[F]
    A = 0.5 * np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1)
    area = np.bincount(comp, weights=A, minlength=nc)
    cen = np.stack([np.bincount(comp, weights=A * Cn[:, k], minlength=nc) for k in range(3)], 1) / np.maximum(area[:, None], 1e-9)
    return comp, area, cen, N


def in_box(X, box):
    lo, hi = np.asarray(box["min"], float), np.asarray(box["max"], float)
    return np.all((X >= lo) & (X <= hi), axis=-1)


def texel_sources(work):
    """Per covered texel: low face id, rest face (high) id, sculpt face id (-1 for caps and actuators)."""
    bk = work / "bake"
    fid = np.load(bk / "fid.npy"); hid = np.load(bk / "hid.npy")
    rest = np.load(work / "rest.npz")
    cover = fid >= 0
    h = hid.ravel()[cover.ravel()]
    src = np.where(h >= 0, rest["src"][np.clip(h, 0, None)], -1)
    hkind = np.where(h >= 0, rest["kind"][np.clip(h, 0, None)], -1)
    return cover, fid.ravel()[cover.ravel()], h, src, hkind


def classify_texels(cfg, work, part_name, low_kind, src, hkind, XS, N):
    """Zone (0 paint, 1 piping, 2 bare metal, 3 glass, 4 emissive), region, stripe and band per texel, decided per
    sculpt panel (crease-bounded patch) so every zone edge lies on one of the kit's own panel lines."""
    comp, area, cen, NS = sculpt_patches(work, cfg.get("mask", {}).get("patch_deg", 25.0))
    mc = cfg.get("mask", {})
    n_ = len(src)
    patch = np.where(src >= 0, comp[np.clip(src, 0, None)], -1)
    region = np.array([REGIONS.index(PART_REGION[p]) for p in part_name])
    zone = np.zeros(n_, int)
    hidden = (low_kind != 0) | (hkind > 0)   # a bake ray that missed (hkind -1) keeps the part's paint
    zone[hidden] = 2
    interior = (low_kind == 1) | (hkind == 1)
    stripe = np.zeros(n_, bool); band = np.zeros(n_, bool); pipe_ok = np.zeros(n_, bool)
    snorm = np.where((src >= 0)[:, None], NS[np.clip(src, 0, None)], 0)
    def patches_for(rule):
        m = in_box(cen, rule) if "min" in rule else np.ones(len(area), bool)
        if "max_area_m2" in rule:
            m &= area / 1e6 <= rule["max_area_m2"]
        if "min_area_m2" in rule:
            m &= area / 1e6 >= rule["min_area_m2"]
        return m
    pcomp, parea, pcen, _ = sculpt_panels(work, mc.get("panel_deg", 12.0))
    panel = np.where(src >= 0, pcomp[np.clip(src, 0, None)], -1)
    for rule in mc.get("rules", []):
        if rule.get("level") == "panel":
            m_ = in_box(pcen, rule) if "min" in rule else np.ones(len(parea), bool)
            if "max_area_m2" in rule:
                m_ &= parea / 1e6 <= rule["max_area_m2"]
            if "min_area_m2" in rule:
                m_ &= parea / 1e6 >= rule["min_area_m2"]
            if "max_width_mm" in rule or "min_aspect" in rule:
                Lp, Wp = panel_shape(work, mc.get("panel_deg", 12.0))
                m_ &= (Wp <= rule.get("max_width_mm", 1e9)) & (Lp >= rule.get("min_aspect", 0) * np.maximum(Wp, 1)) & (Lp > 0)
            t = (panel >= 0) & m_[np.clip(panel, 0, None)] & ~hidden
        else:
            pm = patches_for(rule)
            t = (patch >= 0) & pm[np.clip(patch, 0, None)] & ~hidden
        if "parts" in rule:
            t &= np.isin(part_name, rule["parts"])
        if "normal" in rule:
            t &= snorm @ np.asarray(rule["normal"][:3], float) >= rule["normal"][3]
        what = rule["set"]
        if what in REGIONS:
            region[t] = REGIONS.index(what)
        elif what == "stripe":
            stripe |= t
        elif what == "band":
            band |= t
        elif what == "piping":
            pipe_ok |= t
        else:
            zone[t] = {"metal": 2, "glass": 3, "emissive": 4, "paint": 0}[what]
    if cfg.get("glass_outlines") and cfg.get("glass_mode", "patch") == "texel":
        gt = glass_texels(cfg, work, XS, src) & ~hidden
        zone[gt] = 3
    else:
        gl = glass_faces_v3(cfg, work)
        if gl is not None:
            gt = (src >= 0) & gl[np.clip(src, 0, None)] & ~hidden
            if cfg.get("glass_outlines") and cfg.get("glass_hull", True):
                gt = hull_fill(gt, work) & ~hidden
                gt = vote_smooth(gt, work, int(cfg.get("glass_vote_px", 2))) & ~hidden
                if cfg.get("glass_low_faces", True):
                    # snap to the game mesh's own faces: a low face is glass when most of its texels are, so the
                    # pane edge is the mesh edge between the pane floor and its frame wall (straight, no dashes)
                    lf = np.load(work / "bake/fid.npy").ravel()
                    lf = lf[lf >= 0]
                    nlf = int(lf.max()) + 1
                    frac = np.bincount(lf, weights=gt, minlength=nlf) / np.maximum(np.bincount(lf, minlength=nlf), 1)
                    thr = float(cfg.get("glass_low_face_share", 0.5))
                    gt = ((frac[lf] >= thr) | (gt & (frac[lf] >= 0.2))) & ~hidden
            zone[gt] = 3
    if cfg.get("weapons") or cfg.get("lenses"):
        wid, lens, _ = weapon_faces(cfg, work)
        wt = np.where(src >= 0, wid[np.clip(src, 0, None)], -1)
        isw = (wt >= 0) & ~hidden
        region[isw] = REGIONS.index("weapons")
        stripe &= ~isw; band &= ~isw; pipe_ok &= ~isw
        lt = (src >= 0) & lens[np.clip(src, 0, None)] & ~hidden
        zone[lt] = 4
    return zone, region, interior, stripe, band, pipe_ok, patch


# --- texel layers -------------------------------------------------------------------------------------------------

def lowness_g(h):
    return smoothstep(7000.0, 300.0, h)


def dilate_nearest(img, cover, iters=24):
    """Fill the uncovered texels from their nearest covered neighbour (no blending: ids stay exact)."""
    idx = ndimage.distance_transform_edt(~cover, return_distances=False, return_indices=True)
    return img[idx[0], idx[1]]


def stage_paint(cfg, work):
    from PIL import Image
    import v3_mech as M
    bk = work / "bake"
    cover, f, hid, src, hkind = texel_sources(work)
    res = cover.shape[0]
    ii = np.flatnonzero(cover.ravel())
    X = np.load(bk / "pos.npy").astype(np.float32).reshape(-1, 3)[ii]          # rest-pose mm
    N = np.load(bk / "nrm.npy").astype(np.float32).reshape(-1, 3)[ii]
    N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-9
    A = (np.asarray(Image.open(bk / "ao.png").convert("L"), np.float32) / 255.0).ravel()[ii]
    AS = (np.asarray(Image.open(bk / "ao_short.png").convert("L"), np.float32) / 255.0).ravel()[ii]
    E = np.clip(np.load(bk / "edge.npy").astype(np.float32).ravel()[ii], 0, 1)
    ew_img = np.clip(np.load(bk / "edge_wide.npy").astype(np.float32), 0, 1)
    sig = float(cfg.get("wear", {}).get("edge_blur_px", 2.0))
    cw = cover.astype(np.float32)
    ew_b = ndimage.gaussian_filter(ew_img * cw, sig) / np.maximum(ndimage.gaussian_filter(cw, sig), 1e-4)
    EW = np.clip(np.maximum(ew_img, ew_b * 1.6).ravel()[ii], 0, 1)    # a wider wear band, same island only
    names = list(M.PARTS)
    low = np.load(work / "low.npz")
    part_i = low["part"][f]
    part_name = np.array(names)[part_i]
    low_kind = low["kind"][f]
    fit = json.loads((work / "fit.json").read_text())
    XS = X.copy()
    for k, p in enumerate(names):
        m = part_i == k
        if m.any():
            Mi = np.linalg.inv(np.array(fit["xform"][p]))
            XS[m] = X[m] @ Mi[:3, :3].T + Mi[:3, 3]
    zone, region, interior, stripe, band, pipe_ok, patch = classify_texels(cfg, work, part_name, low_kind, src, hkind, XS, N)
    w = cfg.get("wear", {})
    seed = int(w.get("seed", 7))
    height = X[:, 2]
    n_ = len(ii)
    # --- noise fields (object space mm; no feature under ~3 texels at the field's mip level)
    n_big = fbm(X, 900.0, 3, seed)
    n_mid = fbm(X, 320.0, 3, seed + 101)
    n_chip = fbm(X, float(w.get("chip_scale_mm", 220.0)), 3, seed + 202)
    n_streak = fbm(X * np.array([1.0, 1.0, 0.12]), 160.0, 3, seed + 303)   # stretched down: runs
    # --- convexity from the short AO: an edge in the open is convex, one in a crease concave
    convex = smoothstep(0.03, 0.2, EW) * smoothstep(0.8, 0.95, AS)
    concave = smoothstep(0.03, 0.2, EW) * smoothstep(0.75, 0.5, AS)
    expo = np.full(n_, float(w.get("exposure_default", 0.6)), np.float32)
    for p_, v in w.get("exposure", {}).items():
        expo[part_i == names.index(p_)] = v
    expo *= 1.0 + 0.35 * smoothstep(0.6, 0.95, N[:, 2])
    paintable = zone <= 1
    # --- edge chips: bare steel through the paint inside a dark lip of torn paint
    patchy = smoothstep(0.3, 0.7, n_big * 0.6 + n_mid * 0.4)            # some edges stay clean, some are battered
    chip_field = convex * expo * float(w.get("chips", 1.0)) * (0.45 + 1.0 * n_chip) * (0.4 + 0.9 * patchy) - (1.0 - n_mid) * 0.3
    chip = smoothstep(0.24, 0.31, chip_field) * paintable
    lip = smoothstep(0.15, 0.24, chip_field) * (1 - chip) * paintable
    scuff = smoothstep(0.80, 0.86, n_chip * 0.6 + n_mid * 0.4) * smoothstep(0.6, 0.8, n_big) * 0.9 * expo * paintable
    chip = np.maximum(chip, scuff * (1 - convex))
    # --- grime in recesses (long AO), creases (short AO) and runs down vertical faces
    cav = smoothstep(0.8, 0.3, A)
    crease = smoothstep(0.7, 0.4, AS)
    runs = smoothstep(0.55, 0.8, n_streak) * (1 - np.abs(N[:, 2])) * (0.35 + 0.65 * cav) * smoothstep(0.35, 0.65, n_big)
    grime = np.clip((cav * 0.6 + crease * 0.7 + runs * 0.6 + lowness_g(height) * 0.25 * n_big) * float(w.get("grime", 1.0)), 0, 0.92)
    # --- dust and mud from the feet up (rest pose height), more on up-facing faces
    dust_amt = float(w.get("dust", 1.0))
    dust = smoothstep(float(w.get("dust_height_mm", 3200)), 150.0, height) * (0.4 + 0.6 * n_mid) * dust_amt
    dust = np.maximum(dust, smoothstep(0.75, 0.95, N[:, 2]) * smoothstep(0.4, 0.8, n_big) * 0.3 * dust_amt)
    dust = np.clip(dust, 0, 0.8)
    soot = np.zeros(n_, np.float32)
    for s_ in w.get("soot", []):
        d = np.linalg.norm(XS - np.asarray(s_["p"], float), axis=1)
        soot = np.maximum(soot, smoothstep(s_["r"], s_["r"] * 0.2, d) * (0.55 + 0.45 * n_mid))
    # --- colours (linear)
    steel_bright = srgb_to_lin([0.60, 0.60, 0.59])
    gunmetal = srgb_to_lin([0.23, 0.235, 0.245])
    interior_c = srgb_to_lin([0.07, 0.07, 0.075])
    grime_c = srgb_to_lin([0.11, 0.095, 0.08])
    dust_c = srgb_to_lin(w.get("dust_colour", [0.47, 0.42, 0.34]))
    soot_c = srgb_to_lin([0.035, 0.033, 0.032])
    glass_c = srgb_to_lin([0.04, 0.10, 0.13])
    lens_c = srgb_to_lin([0.95, 0.3, 0.12])
    rgb = np.zeros((n_, 3), np.float32)
    alpha = np.ones(n_, np.float32)
    rough = np.full(n_, float(w.get("paint_roughness", 0.6)), np.float32) + (n_mid - 0.5) * 0.1
    metal = np.zeros(n_, np.float32)
    rng = np.random.default_rng(seed)
    tone = 1.0 + (rng.random(int(patch.max()) + 2) - 0.5) * float(w.get("panel_tone", 0.08))
    lowness = smoothstep(9000.0, 500.0, height)                       # the lower body is dirtier
    shade = float(w.get("paint_value", 0.88)) * tone[np.clip(patch, 0, None)] * (0.55 + 0.45 * A) * (0.84 + 0.22 * n_big) * (1 - 0.45 * concave)
    shade *= 0.8 + 0.2 * AS                                              # panel seams and creases stay dark in direct light
    shade *= 1.0 - 0.14 * lowness
    shade *= 1.0 + float(w.get("edge_lighten", 0.22)) * convex          # worn, lighter paint along exposed edges
    bm = zone == 2
    rgb[bm] = gunmetal * (0.8 + 0.4 * n_mid[bm, None])
    rgb[interior] = interior_c
    alpha[bm] = 0
    rough[bm] = 0.36 + 0.2 * n_mid[bm]; metal[bm] = 0.85
    rough[interior] = 0.7; metal[interior] = 0.25
    # metal edges catch light too: bright worn rims on housings
    rim = convex * (zone == 2) * ~interior * 0.6
    rgb = rgb * (1 - rim[:, None]) + steel_bright * rim[:, None] * 0.8
    ch = chip > 0
    rgb = np.where(ch[:, None], steel_bright * (0.85 + 0.3 * n_chip[:, None]), rgb)
    alpha *= 1 - chip
    rough = rough * (1 - chip) + chip * 0.3
    metal = metal * (1 - chip) + chip
    shade *= 1 - float(w.get("lip", 0.4)) * lip
    gl = zone == 3; em = zone == 4
    rgb[gl] = glass_c; alpha[gl] = 0; rough[gl] = 0.05; metal[gl] = 0
    rgb[em] = lens_c; alpha[em] = 0; rough[em] = 0.2; metal[em] = 0
    def overlay(col, k):
        # C = mix(rgb, paint, alpha); a coat of colour col and opacity k over it gives rgb', alpha' below
        nonlocal rgb, alpha
        k = np.clip(k * ~gl * ~em, 0, 1)[:, None]
        a = alpha[:, None]
        den = np.maximum(1 - (1 - k) * a, 1e-4)
        rgb = (k * col + (1 - k) * (1 - a) * rgb) / den
        alpha = ((1 - k) * a)[:, 0]
    overlay(grime_c, grime * float(w.get("grime_opacity", 0.7)))
    rough = np.clip(rough + grime * 0.15, 0, 1)
    overlay(grime_c, smoothstep(0.45, 0.85, n_big) * smoothstep(0.3, 0.7, n_mid) * float(w.get("dirt_patches", 0.35)))
    overlay(dust_c, dust * float(w.get("dust_opacity", 0.55)))
    rough = np.clip(rough + dust * 0.25, 0, 1); metal *= 1 - dust * 0.6
    overlay(soot_c, soot * 0.8)
    rough = np.clip(rough + soot * 0.2, 0, 1)
    # --- piping: the convex edges of the chosen panels (a painted trim line ~7 cm wide along the bevel)
    pip = pipe_ok & (zone == 0)
    rid = np.where(zone == 2, R_METAL, np.where(zone == 3, R_GLASS, np.where(zone == 4, R_EMIT, region)))
    out = work / "tex"; out.mkdir(exist_ok=True)
    def to_img(vals, ch):
        img = np.zeros((res * res, ch), np.float32)
        img[ii] = vals
        return dilate_nearest(img.reshape(res, res, ch), cover)
    alb = to_img(np.c_[lin_to_srgb(rgb), alpha], 4)
    Image.fromarray((np.clip(alb, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(out / "albedo.png")
    orm = to_img(np.c_[np.clip(0.2 + 0.8 * A, 0, 1), np.clip(rough, 0.04, 1), np.clip(metal, 0, 1), np.clip(shade * 0.8, 0, 1)], 4)
    Image.fromarray((orm * 255 + 0.5).astype(np.uint8), "RGBA").save(out / "orm.png")
    ids = to_img(np.c_[rid * 16 + 8, pip * 255, stripe * 255, band * 255], 4)
    # glass gutter: the atlas gutter next to a pane takes the pane's values, so bilinear and mip sampling at a chart
    # edge doesn't pull the frame's grey into the glass (the dashed pane rims, Mad Cat 2026-10-25)
    gimg = np.zeros(res * res, bool); gimg[ii] = gl
    gimg = gimg.reshape(res, res)
    gut = ndimage.binary_dilation(gimg, iterations=4) & ~cover
    if gut.any():
        idx = ndimage.distance_transform_edt(~gimg, return_distances=False, return_indices=True)
        for img_ in (alb, orm, ids):
            img_[gut] = img_[idx[0][gut], idx[1][gut]]
        Image.fromarray((np.clip(alb, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(out / "albedo.png")
        Image.fromarray((orm * 255 + 0.5).astype(np.uint8), "RGBA").save(out / "orm.png")
    Image.fromarray(np.clip(ids, 0, 255).astype(np.uint8), "RGBA").save(out / "ids.png")
    c1 = fbm(X, 1500.0, 3, seed + 404); c2 = fbm(X, 650.0, 3, seed + 505); c3 = fbm(X, 300.0, 2, seed + 606)
    expo_env = np.clip(smoothstep(0.2, 0.9, N[:, 2]) * 0.8 + smoothstep(2500, 300, height) * 0.6, 0, 1)
    cam = to_img(np.c_[c1, c2, c3, expo_env], 4)
    Image.fromarray((np.clip(cam, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").resize((res // 2, res // 2), Image.BILINEAR).save(out / "camo.png")
    import shutil
    shutil.copy(bk / "normal.png", out / "normal.png")
    # layer breakdown for the review sheet
    lay = {"chips": chip, "grime": grime, "dust": dust, "soot": soot, "convex": convex, "concave": concave,
           "zone": zone / 4.0, "region": region / 7.0, "piping": pip.astype(np.float32), "stripe": stripe.astype(np.float32),
           "band": band.astype(np.float32)}
    np.savez_compressed(out / "layers.npz", ii=ii, res=res, **{k: v.astype(np.float16) for k, v in lay.items()})
    stats = {"texels": int(n_), "chip_share": float((chip > 0.5).mean()), "grime_mean": float(grime.mean()),
             "paint_share": float((alpha > 0.5).mean()), "glass_texels": int(gl.sum()), "emissive_texels": int(em.sum()),
             "piping_texels": int(pip.sum()), "stripe_texels": int(stripe.sum()), "band_texels": int(band.sum())}
    (out / "stats.json").write_text(json.dumps(stats, indent=1))
    print("paint:", stats)


# --- preview composite (mirrors game/shaders/unit_v3.gdshader) ---------------------------------------------------

CAMO = {  # sRGB palettes as in unit_v3.gdshader
    "woodland": [(0.30, 0.33, 0.19), (0.13, 0.19, 0.10, 0.56, 0), (0.31, 0.22, 0.13, 0.64, 1), (0.06, 0.07, 0.05, 0.70, 2)],
    "snow": [(0.80, 0.82, 0.84), (0.60, 0.62, 0.65, 0.60, 0), (0.40, 0.42, 0.45, 0.68, 1)],
    "urban": [(0.52, 0.53, 0.54), (0.33, 0.35, 0.39, 0.55, 0), (0.17, 0.18, 0.19, 0.63, 1), (0.70, 0.71, 0.72, 0.72, 2)],
    "thorin": [(0.29, 0.24, 0.14), (0.76, 0.67, 0.41, 0.58, 0), (0.14, 0.165, 0.12, 0.60, 1)],
    "arkab": [(0.79, 0.65, 0.48), (0.6, 0.35, 0.16, 0.6, 0), (0.37, 0.42, 0.27, 0.66, 1)],
}


def paint_colour(hexcol):
    """As MechPaint.paint_colour_v3: a scheme colour as enamel (sRGB in, linear out)."""
    c = np.array([int(hexcol[i:i + 2], 16) / 255.0 for i in (1, 3, 5)])
    return srgb_to_lin(c)


def composite(work, scheme, out_png):
    """The scheme painted over the v3 textures, as the game shader does it (for look-dev renders and sheets)."""
    from PIL import Image
    t = work / "tex"
    alb = np.asarray(Image.open(t / "albedo.png"), np.float32) / 255.0
    orm = np.asarray(Image.open(t / "orm.png"), np.float32) / 255.0
    ids = np.asarray(Image.open(t / "ids.png"))
    cam = np.asarray(Image.open(t / "camo.png").resize(alb.shape[:2][::-1], Image.BILINEAR), np.float32) / 255.0
    col = {k: paint_colour(scheme[k]) for k in ("base", "hl1", "hl2")}
    regions = scheme.get("regions", {})
    rid = ids[..., 0] // 16
    paint = np.zeros(alb.shape[:2] + (3,), np.float32)
    steel = np.zeros(alb.shape[:2], bool)
    camo_on = np.zeros(alb.shape[:2], bool)
    for i, r in enumerate(REGIONS):
        v = regions.get(r, "base")
        m = rid == i
        if v == "steel":
            paint[m] = srgb_to_lin([0.30, 0.305, 0.32]); steel |= m
        else:
            paint[m] = col.get(v, col["base"])
            camo_on |= m & (v == "base")
    pat = scheme.get("pattern", "plain")
    if pat in CAMO:
        pal = CAMO[pat]
        c = np.broadcast_to(srgb_to_lin(pal[0][:3]), paint.shape).copy()
        for cc in pal[1:]:
            m = smoothstep(cc[3] - 0.02, cc[3] + 0.02, cam[..., cc[4]])[..., None]
            c = c * (1 - m) + srgb_to_lin(cc[:3]) * m
        paint = np.where(camo_on[..., None], c, paint)
    def scol(v):
        if v is None or v == "":
            return None
        return col[v] if v in col else paint_colour(v)
    for key, chn in (("band", 3), ("stripe", 2), ("piping", 1)):
        c = scol(scheme.get(key))
        if c is not None:
            m = (ids[..., chn] > 127)[..., None]
            paint = np.where(m, c, paint)
    paint = paint * (orm[..., 3:4] / 0.8)
    rgb = srgb_to_lin(alb[..., :3])
    a = alb[..., 3:4]
    final = rgb * (1 - a) + paint * a
    o2 = orm.copy()
    o2[..., 2] = np.where(steel, np.maximum(orm[..., 2], 0.8 * a[..., 0]), orm[..., 2])
    Image.fromarray((lin_to_srgb(final) * 255 + 0.5).astype(np.uint8)).save(out_png)
    Image.fromarray((o2 * 255 + 0.5).astype(np.uint8)).save(Path(out_png).with_name("orm.png"))
    return out_png


# --- weapons as whole geometry ------------------------------------------------------------------------------------

def front_point(work, x, z, axis=1, side=-1):
    """The sculpt surface point at (x, z) seen from -Y (side=-1) or +Y: first hit along the axis."""
    import v3_common as C
    zz = np.load(work / "sculpt.npz")
    h = C.line_hits(zz["P"], zz["F"], axis, x, z) if axis == 1 else None
    if h is None or len(h) == 0:
        return None
    y = h.min() if side < 0 else h.max()
    return np.array([x, y, z], float)


def weapon_faces(cfg, work):
    """Per sculpt face: weapon index (-1 none) from cfg["weapons"]: [{"name", "parts": [...], "volume": {"min", "max"}
    or {"hull": [[x, y, z], ...]} (sculpt frame, read off the mm-grid views), "inside": 0.6}]. The selection snaps
    to the sculpt's flat panels (faces joined across edges flatter than mask.panel_deg, so bounded by sharp edges):
    a panel with >= `inside` of its area in the volume is the weapon's, whole; anything else is not. A print kit's
    separate shells (connected components) are taken whole the same way. cfg["lenses"]: [{"p", "r"}] -> emissive."""
    from scipy.spatial import Delaunay
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    z = np.load(work / "sculpt.npz"); P, F = z["P"], z["F"]
    lab = np.load(work / "labels.npz")["lab"]
    pcomp, parea, pcen, N = sculpt_panels(work, cfg.get("mask", {}).get("panel_deg", 12.0))
    n = len(P)
    ncc, vcc = connected_components(coo_matrix((np.ones(3 * len(F)), (F.ravel(), np.roll(F, 1, 1).ravel())), shape=(n, n)), directed=False)
    shell = vcc[F[:, 0]]
    T = P[F]; Cn = T.mean(1)
    A = 0.5 * np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1)
    wid = -np.ones(len(F), int)
    report = []
    for k, wpn in enumerate(cfg.get("weapons", [])):
        if "whole_parts" in wpn:   # a weapon that is a whole rigid part of the kit (a launcher box, a gun arm)
            m = np.isin(lab, wpn["whole_parts"]) & (wid < 0)
            wid[m] = k
            report.append({"name": wpn["name"], "faces": int(m.sum()), "area_m2": round(float(A[m].sum()) / 1e6, 2)})
            continue
        if "outlines" in wpn:   # [{"png": Lee's outlined sheet, "view": "front"}, ...] from make_sheets()
            m = np.zeros(len(F), bool)
            for o in wpn["outlines"]:
                m |= outline_faces(work, Path(o["png"]).expanduser(), o["view"])
            m &= wid < 0
            wid[m] = k
            report.append({"name": wpn["name"], "faces": int(m.sum()), "area_m2": round(float(A[m].sum()) / 1e6, 2)})
            continue
        v = wpn["volume"]
        if "hull" in v:
            inside = Delaunay(np.asarray(v["hull"], float)).find_simplex(Cn) >= 0
        else:
            inside = in_box(Cn, v)
        ok = np.isin(lab, wpn["parts"]) if "parts" in wpn else np.ones(len(F), bool)
        m = np.zeros(len(F), bool)
        for grp, ng in ((pcomp, len(parea)), (shell, ncc)):
            tot = np.bincount(grp, weights=A, minlength=ng)
            frac = np.bincount(grp, weights=A * inside * ok, minlength=ng) / np.maximum(tot, 1e-9)
            pick = frac >= wpn.get("inside", 0.6)
            if grp is shell:
                pick &= tot < 0.5 * A.sum()        # only real separate shells, not the fused body
            m |= pick[grp]
        m &= ok & (wid < 0)
        wid[m] = k
        report.append({"name": wpn["name"], "faces": int(m.sum()), "area_m2": round(float(A[m].sum()) / 1e6, 2)})
    lens = np.zeros(len(F), bool)
    for L_ in cfg.get("lenses", []):
        lens |= np.linalg.norm(Cn - np.asarray(L_["p"], float), axis=1) < L_["r"]
    return wid, lens, report


# --- artist outlines (blue on the aligned sheets) -> faces -------------------------------------------------------

SHEET_VIEWS = "front,q34,side,rside,top"


def make_sheets(work, out_dir, size=1400):
    """Plain aligned sheets for an artist to outline weapons (or canopies) in blue: <out>/sheet_<view>.png plus
    sheets.json (camera of each view) and a face-id render per view for the back-projection."""
    import v3_common as C
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    z = np.load(work / "sculpt.npz")
    np.savez(work / "sheet_plain.npz", P=z["P"], F=z["F"], col=np.full((len(z["F"]), 3), 0.72))
    C.blender("views", work / "sheet_plain.npz", out_dir / "sheet", "--views", SHEET_VIEWS, "--size", str(size))
    idx = np.arange(len(z["F"])) + 1
    col = np.c_[(idx >> 16) & 255, (idx >> 8) & 255, idx & 255] / 255.0
    np.savez(work / "sheet_fid.npz", P=z["P"], F=z["F"], col=srgb_to_lin(col))   # the render writes sRGB: exact bytes
    C.blender("views", work / "sheet_fid.npz", work / "sheetfid", "--views", SHEET_VIEWS, "--size", str(size), "--flat", "1")
    import shutil
    shutil.copy(out_dir / "sheet.json", work / "sheetfid.json")
    return out_dir


def outline_faces(work, png, view):
    """Sculpt faces inside the closed blue outlines drawn on sheet_<view> (a copy with blue strokes), visible from
    that camera (face-id render), snapped to whole flat panels (>= 50 % of a panel's visible area inside)."""
    from PIL import Image
    from scipy import ndimage as ndi
    a = np.asarray(Image.open(png).convert("RGB")).astype(int)
    blue = (a[..., 2] > 90) & (a[..., 2] - a[..., 0] > 50) & (a[..., 2] - a[..., 1] > 40)   # Lee's strokes are dark blue too
    filled = ndi.binary_fill_holes(ndi.binary_closing(blue, iterations=2)) & ~blue
    fid = np.asarray(Image.open(work / f"sheetfid_{view}.png").convert("RGB")).astype(int)
    if fid.shape[:2] != a.shape[:2]:
        fid = np.asarray(Image.open(work / f"sheetfid_{view}.png").convert("RGB").resize(a.shape[1::-1], Image.NEAREST)).astype(int)
    ids = (fid[..., 0] << 16) + (fid[..., 1] << 8) + fid[..., 2] - 1
    z = np.load(work / "sculpt.npz"); nF = len(z["F"])
    ok = (ids >= 0) & (ids < nF)
    vis = np.bincount(ids[ok], minlength=nF)
    hit = np.bincount(ids[ok & filled], minlength=nF)
    pcomp, parea, _, _ = sculpt_panels(work)
    pv = np.bincount(pcomp, weights=vis, minlength=len(parea)); ph = np.bincount(pcomp, weights=hit, minlength=len(parea))
    pick = (pv > 0) & (ph >= 0.5 * pv)
    # plus faces mostly inside the outline themselves: a small recessed lens can share a panel with its frame
    return pick[pcomp] | ((vis > 0) & (hit >= 0.6 * vis))


def glass_faces_v3(cfg, work):
    """Canopy glass per sculpt face. "glass_from_v2": the v2 canopy (hd_v2.py stage glass, back-projected from Lee's
    outlines on the same sculpt) carried over by position and snapped to whole flat panels; "glass_outlines":
    [{"png", "view"}] Lee's outlines on the v3 sheets. Mask rules with "set": "glass" still apply on top."""
    key = ("glass", str(work))
    if key in _PATCH_CACHE:
        return _PATCH_CACHE[key]
    out = None
    z = np.load(work / "sculpt.npz"); P, F = z["P"], z["F"]
    if cfg.get("glass_from_v2"):
        from scipy.spatial import cKDTree
        v2 = Path(cfg["from_v2"])
        r = np.load(v2 / "rest.npz")
        gf = np.load(v2 / "glass_faces.npy")
        if len(gf):
            # rest-pose centroids of the glass faces back into the sculpt frame through their part's v2 transform
            f2 = json.loads((v2 / "fit.json").read_text())
            Pr = r["P"][r["F"][gf]].mean(1); pp = r["part"][gf]
            Pg = np.zeros_like(Pr)
            for pi in np.unique(pp):
                Mi = np.linalg.inv(np.array(f2["xform"][str(int(pi))]))
                mm = pp == pi
                Pg[mm] = Pr[mm] @ Mi[:3, :3].T + Mi[:3, 3]
            d, _ = cKDTree(Pg).query(P[F].mean(1))
            hit = d < float(cfg.get("glass_snap_mm", 60))
            pcomp, parea, _, _ = sculpt_panels(work)
            T = P[F]; A = 0.5 * np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1)
            frac = np.bincount(pcomp, weights=A * hit, minlength=len(parea)) / np.maximum(parea, 1e-9)
            out = (frac >= 0.5)[pcomp]
            if cfg.get("glass_mode") == "direct":   # curved canopies (Urbanmech dome slits): the outline's faces
                out = hit.copy()                       # themselves plus small facets they mostly cover: continuous
                small = parea / 1e6 < float(cfg.get("glass_panel_max_m2", 0.05))
                out |= ((frac >= 0.3) & small)[pcomp]
    if cfg.get("glass_outlines") and cfg.get("glass_mode", "patch") == "patch":
        # Lee's outlines pick panes; the pane's own geometry draws the edge: a crease patch (faces joined across
        # edges flatter than glass_patch_deg, so bounded by the recess rim) is glass when >= half of its visible
        # pixels, summed over every outlined view, fall inside an outline (Mad Cat, 2026-10-25)
        from PIL import Image
        nF = len(F); vis = np.zeros(nF); hit = np.zeros(nF)
        for o in cfg["glass_outlines"]:
            m = outline_mask(Path(o["png"]).expanduser(), erode=0)   # the stroke counts: thin slits are mostly line
            fid = np.asarray(Image.open(work / f"sheetfid_{o['view']}.png").convert("RGB")).astype(np.int64)
            ids = (fid[..., 0] << 16) + (fid[..., 1] << 8) + fid[..., 2] - 1
            ok = (ids >= 0) & (ids < nF)
            vis += np.bincount(ids[ok], minlength=nF); hit += np.bincount(ids[ok & m], minlength=nF)
        comp, area, _, _ = sculpt_patches(work, float(cfg.get("glass_patch_deg", 15)))
        pv = np.bincount(comp, weights=vis, minlength=len(area)); ph = np.bincount(comp, weights=hit, minlength=len(area))
        out = ((pv > 0) & (ph >= 0.5 * pv))[comp]
        if (work / "glass_extra.npy").exists():   # pane faces Lee had flattened (stage flatten)
            out |= np.load(work / "glass_extra.npy")
        Cn_ = P[F].mean(1)
        for b in cfg.get("glass_exclude", []):    # Lee's "not glass" calls, sculpt-frame boxes
            out &= ~in_box(Cn_, b)
        # panes that are not recessed (a flat visor in a bigger plate): the faces inside the outline themselves,
        # but only in patches the outline covers a fair share of (no stray faces of the plates around a pane)
        pc, pa, _, _ = sculpt_panels(work, float(cfg.get("glass_panel_deg", 12)))
        qv = np.bincount(pc, weights=vis, minlength=len(pa)); qh = np.bincount(pc, weights=hit, minlength=len(pa))
        out |= ((qv > 0) & (qh >= float(cfg.get("glass_panel_share", 0.35)) * qv))[pc]
        for b in cfg.get("glass_exclude", []):
            out &= ~in_box(P[F].mean(1), b)
        _PATCH_CACHE[key] = out
        return out
    for o in cfg.get("glass_outlines", []):
        m = outline_faces(work, Path(o["png"]).expanduser(), o["view"])
        out = m if out is None else (out | m)
    if cfg.get("glass_outlines") and out is not None:   # smooth the outline's edge: no saw-tooth on faceted domes
        import v3_stages as S
        fa, fb = S.face_graph(P, F)[:2]
        for _ in range(int(cfg.get("glass_smooth", 2))):
            cnt = np.bincount(fa, weights=out[fb], minlength=len(F)) + np.bincount(fb, weights=out[fa], minlength=len(F))
            out = out | (cnt >= 2)    # fill notches only: never drops a small outlined lens
    _PATCH_CACHE[key] = out
    return out


def outline_mask(png, erode=1):
    """Lee's closed blue outlines on a sheet -> filled region (stroke included, then 1 px eroded, so the glass edge
    runs along the middle of his line). Red strokes are review marks, never glass."""
    from PIL import Image
    from scipy import ndimage as ndi
    a = np.asarray(Image.open(png).convert("RGB")).astype(int)
    blue = (a[..., 2] > 90) & (a[..., 2] - a[..., 0] > 50) & (a[..., 2] - a[..., 1] > 40)
    region = ndi.binary_fill_holes(ndi.binary_closing(blue, iterations=2))
    region &= ndi.binary_fill_holes(region & ~blue) | ~blue        # keep only closed outlines (not open scribbles)
    return ndi.binary_erosion(region, iterations=erode) if erode else region


def glass_texels(cfg, work, XS, src):
    """Glass per texel, cut exactly along the outline (texture-space knife): each texel's sculpt-frame position is
    projected into every outlined sheet's camera; it is glass if it falls inside a closed blue outline and its own
    sculpt face is the one that camera sees there (face-id render, 3x3 tolerance), so hidden surfaces behind the
    canopy never pick it up. Edges follow Lee's line, not the triangles."""
    import v3_common as C
    from PIL import Image
    out = np.zeros(len(XS), bool)
    for o in cfg.get("glass_outlines", []):
        png = Path(o["png"]).expanduser(); v = o["view"]
        meta = json.loads((png.parent / "sheet.json").read_text())
        mask = outline_mask(png)
        fid = np.asarray(Image.open(work / f"sheetfid_{v}.png").convert("RGB")).astype(np.int64)
        ids = (fid[..., 0] << 16) + (fid[..., 1] << 8) + fid[..., 2] - 1
        H, W = mask.shape
        px = C.world_to_px(meta, v, XS)
        xi = np.round(px[:, 0] - 0.5).astype(int); yi = np.round(px[:, 1] - 0.5).astype(int)
        ok = (xi >= 1) & (xi < W - 1) & (yi >= 1) & (yi < H - 1)
        inside = np.zeros(len(XS), bool)
        inside[ok] = mask[yi[ok], xi[ok]]
        # visible = the texel lies on (within tol of the plane of) a face the camera sees at or next to its pixel
        zz = np.load(work / "sculpt.npz"); P_, F_ = zz["P"], zz["F"]
        Tn = np.cross(P_[F_[:, 1]] - P_[F_[:, 0]], P_[F_[:, 2]] - P_[F_[:, 0]])
        Tn /= np.linalg.norm(Tn, axis=1, keepdims=True) + 1e-12
        tol = float(cfg.get("glass_depth_tol_mm", 40))
        vis = np.zeros(len(XS), bool)
        k = np.flatnonzero(ok & inside)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                f = ids[yi[k] + dy, xi[k] + dx]
                good = (f >= 0) & (f < len(F_))
                fk = np.clip(f, 0, len(F_) - 1)
                d = np.abs(((XS[k] - P_[F_[fk, 0]]) * Tn[fk]).sum(1))
                vis[k] |= good & (d < tol)
        out |= inside & vis
    out = clean_texel_mask(out, work, int(cfg.get("glass_close_px", 2)))
    print(f"  glass (texel knife): {int(out.sum())} texels from {len(cfg.get('glass_outlines', []))} outlined views")
    return out


def clean_texel_mask(m, work, close_px=2):
    """Close pinholes and fill small holes of a per-texel mask in the atlas, without crossing into uncovered texels
    (other UV islands): closing restricted to the covered area, then holes under 60 texels filled."""
    from scipy import ndimage as ndi
    fid = np.load(work / "bake/fid.npy"); cover = fid >= 0
    ii = np.flatnonzero(cover.ravel())
    img = np.zeros(cover.size, bool); img[ii] = m
    img = img.reshape(cover.shape)
    img = ndi.binary_closing(img, iterations=close_px) & cover
    holes = ndi.binary_fill_holes(img) & ~img
    lab, n = ndi.label(holes)
    if n:
        sz = ndi.sum(holes, lab, np.arange(1, n + 1))
        img |= np.isin(lab, np.flatnonzero(sz < 60) + 1)
    img = ndi.binary_opening(img, iterations=1) | (img & ndi.binary_erosion(img, iterations=1))
    return img.ravel()[ii]


def hull_fill(m, work, min_px=30):
    """Each connected glass region in the atlas filled to its convex hull (inside covered texels): canopy panes are
    convex, so notches where a frame lip or a print facet cut into a pane close, and the pane edge is straight."""
    from scipy import ndimage as ndi
    from scipy.spatial import Delaunay, ConvexHull
    fid = np.load(work / "bake/fid.npy"); cover = fid >= 0
    ii = np.flatnonzero(cover.ravel())
    img = np.zeros(cover.size, bool); img[ii] = m; img = img.reshape(cover.shape)
    lab, n = ndi.label(img)
    out = img.copy()
    for k, sl in enumerate(ndi.find_objects(lab), 1):
        ys, xs = np.nonzero(lab[sl] == k)
        if len(ys) < min_px:
            continue
        pts = np.c_[xs, ys].astype(float)
        try:
            hull = Delaunay(pts[ConvexHull(pts).vertices])
        except Exception:
            continue
        gy, gx = np.mgrid[0:lab[sl].shape[0], 0:lab[sl].shape[1]]
        inside = hull.find_simplex(np.c_[gx.ravel(), gy.ravel()]) >= 0
        sub = out[sl]
        sub |= inside.reshape(sub.shape) & cover[sl] & (fid[sl] >= 0) & ndi.binary_dilation(lab[sl] == k, iterations=12)
    return out.ravel()[ii]


def vote_smooth(m, work, r=2, iters=2):
    """Majority vote of a texel mask over a (2r+1)^2 window of covered texels: the dashed rim where the bake rays
    flip between a pane and its frame wall becomes a straight edge."""
    from scipy import ndimage as ndi
    fid = np.load(work / "bake/fid.npy"); cover = fid >= 0
    ii = np.flatnonzero(cover.ravel())
    img = np.zeros(cover.size, np.float32); img[ii] = m; img = img.reshape(cover.shape)
    cw = cover.astype(np.float32)
    k = 2 * r + 1
    for _ in range(iters):
        num = ndi.uniform_filter(img * cw, k); den = ndi.uniform_filter(cw, k)
        img = ((num / np.maximum(den, 1e-6)) > 0.5).astype(np.float32) * cw
    return img.ravel()[ii] > 0.5
