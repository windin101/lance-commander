#!/usr/bin/env python3
"""Per-unit HUD paper dolls: the HD model's own silhouette split into its armour locations.

    python3 -I tools/art/paper_doll.py [unit ...] [--sheet swarm/gallery/paper_dolls.png] [--debug DIR]

Writes game/assets/ui/dolls/<unit>_doll.png (an index mask: R = G = B = location index, A = 255 inside the
silhouette; R = 255 and A = 0 outside) and game/assets/ui/dolls/dolls.json (per unit: kind, size, view, and per
location its index, label centroid [x, y] in mask pixels and pixel count). With no unit names it does every
game/assets/mechs/*_hd.glb and game/assets/vehicles/*_hd.glb. Overrides live in tools/art/paper_doll.json.

Mechs (SimMech.Body: 0 head, 1 ctorso, 2 ltorso, 3 rtorso, 4 larm, 5 rarm, 6 lleg, 7 rleg) are drawn from behind
(the pilot's view: the mech's left on screen left) in the rest pose, orthographic, about 256 px tall. The rear
doll is the same mask: SimMech.Armor RCTORSO, RLTORSO, RRTORSO sit on locations 1, 2, 3.
  1. Each triangle is owned by the joint with the largest summed skin weight over its three vertices. Joint names
     are <prefix>_<l|r><part>: foot/leg/ankle/toe -> legs, arm/gun -> arms, missile/launcher/shoulder -> side
     torsos, head -> head (cyclops joint_cy_head, wolfhound joint_head); hip -> centre torso (the pelvis;
     "split_hip": true splits it with the body instead); torso and anything else is "body".
     A joint without a side letter (bushwacker joint_lmlauncher has one, starslayer ss_gun does not) is body.
  2. Rasterised at 4x with a z-buffer (labels, depth, normals), then reduced to 1x by block majority.
  3. Body pixels are split into LT | CT | RT along two seams. Each seam starts from a nominal line at
     ct_frac (0.42) of the way from the centre line to the arm joint on that side (the upper-arm joint's rest
     position; side-torso joints, then the body's own 3rd/97th x percentile when there is no arm) and runs
     top to bottom, moving at most a pixel a row, within +-seam_window (0.35) of the nominal half-width of CT,
     preferring depth jumps and normal creases (panel seams) and slanting in by taper (0.15) towards the hips,
     so CT reads as the usual narrowing column instead of a ruler line.
  4. Head: the head joint's pixels when it exists. Otherwise (or added to them when they are under head_min (12 %)
     of head + CT, the cyclops and highlander heads; "head_from_ct": true ignores the joint) the top of CT: the CT pixels above a horizontal seam
     placed head_frac (0.30) of CT's height down from CT's top (and following the strongest edge within
     +-40 % of that), narrowed to head_width (0.8) of CT's width at that height.
  5. Clean-up: a 4x4 opening ("strand") drops strands up to 3 px wide (antennas), silhouette fragments under
     min_island (12) px or 1 % of the silhouette go (the dashes left of a broken antenna), two passes of a 5x5 and one of a 3x3 majority filter on the labels inside the silhouette, then every
     location keeps its blobs that are >= 15 % of its largest blob (smaller ones join the neighbouring location
     they touch most).
A location with no pixels after all that is a failure: the tool says so; fix it in paper_doll.json.

Vehicles (SimVehicle.Section: 0 front, 1 left, 2 right, 3 rear, 4 turret) and the humanoid vehicles (infantry,
powered armour: SimVehicle in the sim, 5 sections) are drawn in plan view from above, forward up, the vehicle's
left on screen left, the longest side ~256 px. Turret = triangles owned by joints named *turret*, *pod*, *pack*,
*weapon*, *radar* (infantry: head and arms; powered armour: torso and guns), drawn over the hull. The rest is hull:
front = the forward third of the hull's length, rear = the aft third, and the middle third split at the centre
line into left and right (the sim's hit rule is by bearing, so this is a reading aid, not the hit geometry).
Copters (heavycopter, mediumcopter: SimMech chassis with 8 locations and no limbs) are also plan view, rotor
dropped: head = the forward 22 % of the fuselage, legs = the aft 30 % split at the centre line, arms = whatever
sticks out beyond 0.6 of the fuselage's half-width (stub wings, pods), and the rest LT | CT | RT by width.

--sheet draws every doll coloured by location with outlines, names and a 'rear' copy of each mech (torsos only).
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hd_rig as R  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "game/assets/ui/dolls"
MECH_LOCS = ["head", "ctorso", "ltorso", "rtorso", "larm", "rarm", "lleg", "rleg"]
VEH_LOCS = ["front", "left", "right", "rear", "turret"]
HUMANOID = {"infantry", "poweredarmor"}
COPTERS = {"heavycopter", "mediumcopter"}
SS = 4  # supersampling
BODY = 100  # provisional label for torso/hip pixels
EMPTY = 255


# --- model ---------------------------------------------------------------------

def load(path):
    """World-space rest triangles (n, 3, 3), owning joint name per triangle, joint rest positions by name."""
    gltf, binary = R.load_glb(path)
    W = R.world_matrices(gltf)
    names = [n.get("name", "") for n in gltf["nodes"]]
    tris, owner, joints = [], [], {}
    for ni, node in enumerate(gltf["nodes"]):
        if "mesh" not in node:
            continue
        jidx = gltf["skins"][node["skin"]]["joints"] if "skin" in node else None
        if jidx:
            for j in jidx:
                joints[names[j]] = W[j][:3, 3].copy()
        for prim in gltf["meshes"][node["mesh"]]["primitives"]:
            a = prim["attributes"]
            pos = R.read_accessor(gltf, binary, a["POSITION"]).astype(np.float64)
            idx = (R.read_accessor(gltf, binary, prim["indices"]).astype(np.int64).reshape(-1, 3) if "indices" in prim
                   else np.arange(len(pos)).reshape(-1, 3))
            M = W[ni]
            tris.append((pos @ M[:3, :3].T + M[:3, 3])[idx])
            if jidx and "JOINTS_0" in a:
                J = R.read_accessor(gltf, binary, a["JOINTS_0"]).astype(np.int64)
                Wt = R.read_accessor(gltf, binary, a["WEIGHTS_0"]).astype(np.float64)
                nj = len(jidx)
                acc = np.zeros((len(idx), nj))
                for k in range(3):
                    for c in range(J.shape[1]):
                        np.add.at(acc, (np.arange(len(idx)), J[idx[:, k], c]), Wt[idx[:, k], c])
                owner += [names[jidx[j]] for j in acc.argmax(1)]
            else:
                owner += [node.get("name", "")] * len(idx)
    return np.concatenate(tris), np.array(owner), joints


def part_of(name):
    """(side, part) from an MC2 joint name: 'cy_luarm' -> ('l', 'uarm'), 'joint_cy_head' -> ('', 'head')."""
    n = name.lower().replace("-", "_").replace(" ", "")
    part = n.rsplit("_", 1)[-1]
    side = part[0] if part[:1] in ("l", "r") and len(part) > 1 else ""
    return side, part[1:] if side else part


def mech_label(name, ov):
    if name in ov.get("joints", {}):
        return MECH_LOCS.index(ov["joints"][name]) if ov["joints"][name] != "body" else BODY
    side, part = part_of(name)
    if "head" in part:
        return 0
    if side and any(k in part for k in ("foot", "leg", "ankle", "toe")):
        return 6 if side == "l" else 7
    if side and any(k in part for k in ("arm", "gun")):
        return 4 if side == "l" else 5
    if side and any(k in part for k in ("missile", "launcher", "shoulder")):
        return 2 if side == "l" else 3
    if "hip" in part and not ov.get("split_hip"):
        return 1  # the pelvis is centre torso
    return BODY


# --- raster --------------------------------------------------------------------

def raster(T, labels, axes, res_px, margin_px, frame=None):
    """Orthographic z-buffer. axes = (u(xyz)->screen x, v(xyz)->screen y up, d(xyz)->nearer is larger).
    res_px = silhouette size of the longer screen side at 1x; returns label, depth, normal images at SS x."""
    U, V, D = (np.einsum("ntk,k->nt", T, a) for a in axes)
    lo_u, hi_u, lo_v, hi_v = frame if frame is not None else (U.min(), U.max(), V.min(), V.max())
    scale = res_px * SS / max(hi_u - lo_u, hi_v - lo_v)
    m = margin_px * SS
    w = int(np.ceil((hi_u - lo_u) * scale)) + 2 * m
    h = int(np.ceil((hi_v - lo_v) * scale)) + 2 * m
    px = (U - lo_u) * scale + m
    py = (hi_v - V) * scale + m
    nrm = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
    nrm *= np.sign(nrm @ axes[2] + 1e-12)[:, None]  # facing the camera
    lab = np.full((h, w), EMPTY, np.int32)
    zb = np.full((h, w), -np.inf)
    nb = np.zeros((h, w, 3))
    for t in range(len(T)):
        x, y = px[t], py[t]
        x0, x1 = max(0, int(np.floor(x.min()))), min(w - 1, int(np.ceil(x.max())))
        y0, y1 = max(0, int(np.floor(y.min()))), min(h - 1, int(np.ceil(y.max())))
        if x1 < x0 or y1 < y0:
            continue
        det = (x[1] - x[0]) * (y[2] - y[0]) - (x[2] - x[0]) * (y[1] - y[0])
        if abs(det) < 1e-9:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        l1 = ((gx - x[0]) * (y[2] - y[0]) - (x[2] - x[0]) * (gy - y[0])) / det
        l2 = ((x[1] - x[0]) * (gy - y[0]) - (gx - x[0]) * (y[1] - y[0])) / det
        ins = (l1 >= -1e-6) & (l2 >= -1e-6) & (l1 + l2 <= 1 + 1e-6)
        if not ins.any():
            continue
        z = D[t, 0] + l1 * (D[t, 1] - D[t, 0]) + l2 * (D[t, 2] - D[t, 0])
        ys, xs, zs = gy[ins].astype(int), gx[ins].astype(int), z[ins]
        win = zs > zb[ys, xs]
        ys, xs = ys[win], xs[win]
        zb[ys, xs] = zs[win]
        lab[ys, xs] = labels[t]
        nb[ys, xs] = nrm[t]
    return lab, zb, nb, scale / SS


def block_mode(lab, k):
    """Majority label of each k x k block (lab values < 256)."""
    h, w = lab.shape[0] // k, lab.shape[1] // k
    b = lab[:h * k, :w * k].reshape(h, k, w, k).transpose(0, 2, 1, 3).reshape(h, w, k * k)
    vals = np.unique(b)
    counts = np.stack([(b == v).sum(2) for v in vals], 2)
    return vals[counts.argmax(2)]


def block_mean(a, k):
    h, w = a.shape[0] // k, a.shape[1] // k
    return a[:h * k, :w * k].reshape(h, k, w, k, *a.shape[2:]).mean((1, 3))


def edges(depth, nrm, sil):
    """Edge strength 0..1 from depth jumps and normal creases (panel seams) inside the silhouette."""
    d = np.where(sil, depth, np.nan)
    med = np.nanmedian(d) if sil.any() else 0.0
    d = np.where(sil, depth, med)
    gy, gx = np.gradient(d)
    gd = np.hypot(gx, gy)
    gd /= (np.percentile(gd[sil], 95) + 1e-9) if sil.any() else 1
    gn = np.zeros(sil.shape)
    for c in range(3):
        ny, nx = np.gradient(nrm[..., c])
        gn += ny * ny + nx * nx
    gn = np.sqrt(gn)
    gn /= (np.percentile(gn[sil], 95) + 1e-9) if sil.any() else 1
    e = np.clip(np.maximum(gd, gn), 0, 1.5) / 1.5
    return np.where(sil, e, 0.0)


def seam(edge, active, nominal, window, slope_pen=0.15):
    """Top-to-bottom seam: per row a column within nominal[row] +- window, moving <= 1 px per row,
    minimising (1 - edge) + slope_pen * |offset| / window. Rows with no active pixels are free."""
    h, w = edge.shape
    offs = np.arange(-window, window + 1)
    cost = np.zeros((h, len(offs)))
    for r in range(h):
        cols = np.clip(np.round(nominal[r] + offs).astype(int), 0, w - 1)
        c = (1.0 - edge[r, cols]) + slope_pen * np.abs(offs) / max(window, 1)
        cost[r] = np.where(active[r, cols], c, 0.02 * np.abs(offs) / max(window, 1))
    acc = cost.copy()
    back = np.zeros((h, len(offs)), int)
    for r in range(1, h):
        prev = np.stack([np.r_[np.inf, acc[r - 1, :-1]], acc[r - 1], np.r_[acc[r - 1, 1:], np.inf]])
        k = prev.argmin(0)
        back[r] = k - 1
        acc[r] += prev[k, np.arange(len(offs))]
    path = np.zeros(h, int)
    path[-1] = acc[-1].argmin()
    for r in range(h - 1, 0, -1):
        path[r - 1] = path[r] + back[r, path[r]]
    return np.round(nominal + offs[path]).astype(int)


# --- clean-up --------------------------------------------------------------------

def majority(lab, sil, n, passes=3, size=3):
    for _ in range(passes):
        cnt = np.stack([ndimage.uniform_filter((lab == i).astype(np.float32), size) for i in range(n)])
        best = cnt.argmax(0)
        lab = np.where(sil, best, EMPTY)
    return lab


def islands(lab, sil, n, keep_frac=0.15):
    lab = lab.copy()
    for _ in range(3):
        changed = False
        for i in range(n):
            cc, k = ndimage.label(lab == i)
            if k <= 1:
                continue
            sizes = ndimage.sum(np.ones_like(cc), cc, range(1, k + 1))
            for j in np.nonzero(sizes < keep_frac * sizes.max())[0] + 1:
                blob = cc == j
                ring = ndimage.binary_dilation(blob) & ~blob & sil
                vals = lab[ring]
                vals = vals[(vals != i) & (vals < n)]
                if len(vals):
                    lab[blob] = np.bincount(vals).argmax()
                    changed = True
        if not changed:
            break
    return lab


def clean_sil(sil, min_island, strand=4):
    s = ndimage.binary_opening(sil, np.ones((strand, strand), bool))
    cc, k = ndimage.label(s)
    if k:
        sizes = ndimage.sum(np.ones_like(cc), cc, range(1, k + 1))
        s = np.isin(cc, np.nonzero((sizes >= min_island) & (sizes >= 0.01 * sizes.sum()))[0] + 1)
    return s


def nearest_fill(lab, sil, n):
    """Silhouette pixels without a valid label take the nearest labelled one's."""
    bad = sil & ~(lab < n)
    if bad.any() and (lab < n).any():
        _, (iy, ix) = ndimage.distance_transform_edt(~(lab < n), return_indices=True)
        lab = np.where(bad, lab[iy, ix], lab)
    return np.where(sil, lab, EMPTY)


def crop(lab, n, margin):
    ys, xs = np.nonzero(lab < n)
    y0, y1, x0, x1 = ys.min() - margin, ys.max() + margin + 1, xs.min() - margin, xs.max() + margin + 1
    out = np.full((y1 - y0, x1 - x0), EMPTY, lab.dtype)
    sy0, sx0 = max(0, y0), max(0, x0)
    sy1, sx1 = min(lab.shape[0], y1), min(lab.shape[1], x1)
    out[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = lab[sy0:sy1, sx0:sx1]
    return out


# --- mechs -------------------------------------------------------------------------

def joint_debug(T, owner, axes, path):
    """Each joint's triangles in its own colour, named in a legend (for writing overrides)."""
    names = sorted(set(owner))
    lab_t = np.array([names.index(o) for o in owner])
    lab, *_ = raster(T, lab_t, axes, 400, 8)
    lab = block_mode(lab, SS)
    rng = np.random.default_rng(3)
    pal = rng.integers(60, 255, (len(names), 3))
    img = np.zeros(lab.shape + (3,), np.uint8) + 24
    for i in range(len(names)):
        img[lab == i] = pal[i]
    im = Image.new("RGB", (img.shape[1] + 170, max(img.shape[0], 14 * len(names) + 10)), (24, 24, 24))
    im.paste(Image.fromarray(img), (0, 0))
    d = ImageDraw.Draw(im)
    for i, nm in enumerate(names):
        d.rectangle([img.shape[1] + 4, 4 + 14 * i, img.shape[1] + 14, 14 + 14 * i], fill=tuple(int(c) for c in pal[i]))
        d.text((img.shape[1] + 18, 4 + 14 * i), nm, fill=(255, 255, 255))
    im.save(path)


def mech_doll(T, owner, joints, ov, height):
    lab_t = np.array([mech_label(o, ov) for o in owner])
    if ov.get("drop"):
        keep = ~np.isin(owner, ov["drop"])
        T, lab_t, owner = T[keep], lab_t[keep], owner[keep]
    # from behind: screen x = -world x (mech's left, +x, on screen left), up = +y, nearer = -z
    axes = (np.array([-1.0, 0, 0]), np.array([0, 1.0, 0]), np.array([0, 0, -1.0]))
    labs, zb, nb, ppm = raster(T, lab_t, axes, height, 8)
    U = -T[..., 0]
    lo_u = U.min()
    lab = block_mode(labs, SS)
    depth = block_mean(np.where(np.isfinite(zb), zb, np.nan), SS)
    nrm = block_mean(nb, SS)
    sil = clean_sil(lab != EMPTY, ov.get("min_island", 12), ov.get("strand", 4))
    depth = np.where(np.isnan(depth), np.nanmin(depth), depth)
    lab = np.where(sil, lab, EMPTY)
    e = edges(depth, nrm, sil)
    h, w = lab.shape

    def col(x_world):
        return (-x_world - lo_u) * ppm + 8

    # arm anchors: upper-arm joints, else any arm/side-torso joint, else the body's extent
    body3d = lab_t == BODY
    bx = T[body3d][..., 0].ravel() if body3d.any() else T[..., 0].ravel()
    centre = ov.get("centre_x", float(np.median(bx)))
    anchor = {}
    for side, s in (("l", 1), ("r", -1)):
        if f"shoulder_{side}" in ov:
            anchor[side] = ov[f"shoulder_{side}"]
            continue
        cands = []
        for jn, p in joints.items():
            js, jp = part_of(jn)
            if js == side and any(k in jp for k in ("uarm", "arm", "gun", "missile", "launcher", "shoulder")):
                rank = 0 if "uarm" in jp or jp == "arm" else 1
                cands.append((rank, abs(p[0] - centre), p[0]))
        cands.sort()
        if cands and s * (cands[0][2] - centre) > 0:
            anchor[side] = cands[0][2]
        else:
            anchor[side] = float(np.percentile(bx, 97 if s > 0 else 3))
    frac = ov.get("ct_frac", 0.42)
    xl = centre + frac * (anchor["l"] - centre)
    xr = centre + frac * (anchor["r"] - centre)
    body = lab == BODY
    rows = np.nonzero(body.any(1))[0]
    out = lab.copy()
    if len(rows):
        top, bot = rows.min(), rows.max()
        t = np.clip((np.arange(h) - top) / max(bot - top, 1), 0, 1)
        cc = col(centre)
        taper = ov.get("taper", 0.15)
        nom_l = col(xl) + (cc - col(xl)) * taper * t
        nom_r = col(xr) + (cc - col(xr)) * taper * t
        win = max(2, int(ov.get("seam_window", 0.35) * abs(col(xr) - col(xl)) / 2))
        sl = seam(e, body, nom_l, win)
        sr = seam(e, body, nom_r, win)
        C = np.arange(w)[None, :]
        left_side = C < sl[:, None]  # screen left = mech's left
        right_side = C > sr[:, None]
        out = np.where(body & left_side, 2, out)
        out = np.where(body & right_side, 3, out)
        out = np.where(body & ~left_side & ~right_side, 1, out)
    if "arms_from_body" in ov:  # no arm joints (flea): side-torso pixels beyond this fraction of the
        # centre-to-anchor distance are the arms
        # (a number for both sides, or {"l": f, "r": f} for one: the Raven has a left arm joint only)
        f = ov["arms_from_body"]
        f = f if isinstance(f, dict) else {"l": f, "r": f}
        C = np.arange(w)[None, :]
        cc = col(centre)
        if "l" in f:
            out = np.where((out == 2) & (C < cc + f["l"] * (col(anchor["l"]) - cc)), 4, out)
        if "r" in f:
            out = np.where((out == 3) & (C > cc + f["r"] * (col(anchor["r"]) - cc)), 5, out)
    # head
    small = (out == 0).sum() < ov.get("head_min", 0.12) * ((out == 0) | (out == 1)).sum()
    if small or ov.get("head_from_ct"):
        if ov.get("head_from_ct"):
            out[out == 0] = 1
        ct = out == 1
        crow = np.nonzero(ct.any(1))[0]
        if len(crow):
            ctop, cbot = crow.min(), crow.max()
            if "head_box" in ov:  # [x0, y0, x1, y1] as fractions of the CT bounding box
                cols_ct = np.nonzero(ct.any(0))[0]
                c0, c1 = cols_ct.min(), cols_ct.max()
                b = ov["head_box"]
                Y, X = np.mgrid[0:h, 0:w]
                box = ((X >= c0 + b[0] * (c1 - c0)) & (X <= c0 + b[2] * (c1 - c0))
                       & (Y >= ctop + b[1] * (cbot - ctop)) & (Y <= ctop + b[3] * (cbot - ctop)))
                out[ct & box] = 0
            else:
                hf = ov.get("head_frac", 0.30)
                ny = ctop + hf * (cbot - ctop)
                hw = max(2, int(0.4 * hf * (cbot - ctop)))
                band = np.arange(int(ny - hw), int(ny + hw) + 1)
                band = band[(band >= ctop) & (band <= cbot)]
                # the horizontal seam: the row in the band with the strongest edge across CT
                score = [(e[r][ct[r]].mean() if ct[r].any() else 0) - 0.3 * abs(r - ny) / hw for r in band]
                hy = band[int(np.argmax(score))] if len(band) else int(ny)
                cols_at = np.nonzero(ct[hy])[0] if ct[hy].any() else np.nonzero(ct.any(0))[0]
                mid = (cols_at.min() + cols_at.max()) / 2
                half = ov.get("head_width", 0.8) * (cols_at.max() - cols_at.min()) / 2
                X = np.arange(w)[None, :]
                Y = np.arange(h)[:, None]
                out[ct & (Y < hy) & (np.abs(X - mid) <= half)] = 0
    n = 8
    out = np.where(sil, out, EMPTY)
    out[(out >= n) & sil] = EMPTY + 1  # unknown, fill below
    out = nearest_fill(np.where(out == EMPTY + 1, BODY, out), sil, n)
    out = majority(out, sil, n, passes=2, size=5)
    out = majority(out, sil, n, passes=1)
    out = islands(out, sil, n)
    return crop(out, n, 4), e


# --- vehicles --------------------------------------------------------------------------

TURRET_KEYS = ("turret", "pod", "pack", "weapon", "radar")


def plan_doll(T, owner, unit, ov, size):
    """Plan view, forward (+z) up, the vehicle's left (+x) on screen left, nearer = +y."""
    drop = set(ov.get("drop", []))
    if unit in COPTERS:
        drop |= {o for o in set(owner) if "rotor" in o.lower()}
    keep = ~np.isin(owner, list(drop))
    T, owner = T[keep], owner[keep]
    axes = (np.array([-1.0, 0, 0]), np.array([0, 0, 1.0]), np.array([0, 1.0, 0]))
    copter = unit in COPTERS
    if copter:
        lab_t = np.full(len(T), BODY)
    else:
        if "turret" in ov:
            tur_j = set(ov["turret"])
        elif unit == "infantry":
            tur_j = {o for o in set(owner) if "arms" in o.lower()}
        elif unit == "poweredarmor":
            tur_j = {o for o in set(owner) if "gun" in o.lower()}
        else:
            tur_j = {o for o in set(owner) if any(k in o.lower() for k in TURRET_KEYS)}
        lab_t = np.where(np.isin(owner, list(tur_j)), 4, BODY)
    labs, zb, nb, ppm = raster(T, lab_t, axes, size, 8)
    lab = block_mode(labs, SS)
    sil = clean_sil(lab != EMPTY, ov.get("min_island", 12), ov.get("strand", 4))
    lab = np.where(sil, lab, EMPTY)
    h, w = lab.shape
    U, V = -T[..., 0], T[..., 2]
    lo_u, hi_v = U.min(), V.max()
    Y, X = np.mgrid[0:h, 0:w]
    zw = hi_v - (Y - 8) / ppm  # world z of each row
    xw = -((X - 8) / ppm + lo_u)  # world x of each column
    hull_t = lab_t == BODY
    hz = T[hull_t][..., 2].ravel() if hull_t.any() else T[..., 2].ravel()
    hx = T[hull_t][..., 0].ravel() if hull_t.any() else T[..., 0].ravel()
    z0, z1 = np.percentile(hz, 1), np.percentile(hz, 99)
    xc = ov.get("centre_x", float((np.percentile(hx, 1) + np.percentile(hx, 99)) / 2))
    out = lab.copy()
    if copter:
        body = lab == BODY
        L = z1 - z0
        halfw = (np.percentile(hx, 99) - np.percentile(hx, 1)) / 2
        fus = ov.get("fuselage_half", 0.6 * halfw)
        nose = zw > z1 - ov.get("head_frac", 0.22) * L
        tail = zw < z0 + ov.get("tail_frac", 0.30) * L
        left = xw > xc
        dx = np.abs(xw - xc)
        out = np.where(body, 1, out)
        out = np.where(body & (dx > fus / 3) & left, 2, out)
        out = np.where(body & (dx > fus / 3) & ~left, 3, out)
        out = np.where(body & (dx > fus) & left, 4, out)
        out = np.where(body & (dx > fus) & ~left, 5, out)
        out = np.where(body & tail & left, 6, out)
        out = np.where(body & tail & ~left, 7, out)
        out = np.where(body & nose & (dx <= fus), 0, out)
        n = 8
    else:
        # the hull's own footprint (turret left out), so a turret never hides a whole side: the hull keeps a
        # rim of "rim" px (default 7 % of the short side, >= 6) all round, the turret is drawn inside it and wherever it overhangs the hull
        frame = (U.min(), U.max(), V.min(), V.max())
        hl, *_ = raster(T[hull_t], np.zeros(int(hull_t.sum()), int), axes, size, 8, frame) if hull_t.any() else (labs,)
        hull = (block_mode(hl, SS) != EMPTY) & sil
        rim = hull & ~ndimage.binary_erosion(hull, np.ones((3, 3), bool), iterations=int(ov.get("rim", max(6, 0.07 * min(h, w)))))
        third = (z1 - z0) / 3
        sec = np.where(zw >= z1 - third, 0, np.where(zw <= z0 + third, 3, np.where(xw >= xc, 1, 2)))
        tur = (lab == 4) & ~rim
        out = np.where(sil, sec, EMPTY)
        out = np.where(tur, 4, out)
        n = 5
    out = nearest_fill(np.where(out >= n, BODY, out), sil, n)
    out = majority(out, sil, n, passes=2)
    out = islands(out, sil, n)
    return crop(out, n, 4)


# --- output ------------------------------------------------------------------------

PAL_MECH = [(236, 236, 236), (230, 70, 60), (70, 140, 235), (240, 180, 50), (90, 200, 120), (190, 100, 230),
            (60, 200, 210), (240, 120, 180)]
PAL_VEH = [(230, 70, 60), (70, 140, 235), (240, 180, 50), (90, 200, 120), (236, 236, 236)]


def save_mask(lab, n, path):
    rgba = np.zeros(lab.shape + (4,), np.uint8)
    inside = lab < n
    rgba[..., 0] = np.where(inside, lab, 255)
    rgba[..., 1] = np.where(inside, lab, 0)
    rgba[..., 2] = np.where(inside, lab, 0)
    rgba[..., 3] = np.where(inside, 255, 0)
    Image.fromarray(rgba, "RGBA").save(path)


def stats(lab, names):
    locs = {}
    for i, nm in enumerate(names):
        ys, xs = np.nonzero(lab == i)
        locs[nm] = {"index": i, "pixels": int(len(xs)),
                    "centroid": [round(float(xs.mean()), 1), round(float(ys.mean()), 1)] if len(xs) else None}
    return locs


def colour(lab, pal, only=None):
    h, w = lab.shape
    img = np.zeros((h, w, 3), np.uint8) + 24
    for i, c in enumerate(pal):
        m = lab == i
        if only is not None and i not in only:
            img[m] = (70, 70, 70)
        else:
            img[m] = np.array(c) * 0.75
    e = np.zeros((h, w), bool)
    e[:-1] |= lab[:-1] != lab[1:]
    e[1:] |= lab[:-1] != lab[1:]
    e[:, :-1] |= lab[:, :-1] != lab[:, 1:]
    img[e & (lab != EMPTY)] = (10, 10, 10)
    return img


def sheet(units, path):
    font = ImageFont.load_default()
    cells = []
    for name, (lab, kind) in units.items():
        pal = PAL_MECH if kind in ("mech", "copter") else PAL_VEH
        tiles = [colour(lab, pal)]
        if kind == "mech":
            tiles.append(colour(lab, pal, only=(1, 2, 3)))
        hh = max(t.shape[0] for t in tiles)
        ww = sum(t.shape[1] for t in tiles) + 6 * (len(tiles) - 1)
        cell = np.zeros((hh + 16, max(ww, 110), 3), np.uint8) + 24
        x = 0
        for t in tiles:
            cell[16:16 + t.shape[0], x:x + t.shape[1]] = t
            x += t.shape[1] + 6
        im = Image.fromarray(cell)
        ImageDraw.Draw(im).text((2, 2), f"{name} ({kind})", fill=(255, 255, 255), font=font)
        cells.append(im)
    cols = 6
    cw = max(c.width for c in cells) + 10
    rows = [cells[i:i + cols] for i in range(0, len(cells), cols)]
    rh = [max(c.height for c in r) + 10 for r in rows]
    legend = 28
    S = Image.new("RGB", (cw * cols, sum(rh) + legend), (24, 24, 24))
    d = ImageDraw.Draw(S)
    x = 4
    for i, nm in enumerate(MECH_LOCS):
        d.rectangle([x, 6, x + 14, 20], fill=PAL_MECH[i])
        d.text((x + 18, 8), nm, fill=(255, 255, 255), font=font)
        x += 90
    x += 30
    for i, nm in enumerate(VEH_LOCS):
        d.rectangle([x, 6, x + 14, 20], fill=PAL_VEH[i])
        d.text((x + 18, 8), "veh " + nm, fill=(255, 255, 255), font=font)
        x += 100
    y = legend
    for r, hgt in zip(rows, rh):
        for k, c in enumerate(r):
            S.paste(c, (k * cw + 5, y + 5))
        y += hgt
    path.parent.mkdir(parents=True, exist_ok=True)
    S.save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("units", nargs="*")
    ap.add_argument("--sheet", default="swarm/gallery/paper_dolls.png")
    ap.add_argument("--debug", help="also write <unit>_joints.png (each joint's triangles coloured) to this dir")
    ap.add_argument("--height", type=int, default=248, help="mech silhouette height (the mask adds 4 px margins)")
    a = ap.parse_args()
    over = json.loads((Path(__file__).with_suffix(".json")).read_text()) if Path(__file__).with_suffix(".json").exists() else {}
    over = {k: v for k, v in over.items() if not k.startswith("_")}
    files = {p.stem[:-3]: p for p in sorted((REPO / "game/assets/mechs").glob("*_hd.glb"))}
    files.update({p.stem[:-3]: p for p in sorted((REPO / "game/assets/vehicles").glob("*_hd.glb"))})
    todo = a.units or list(files)
    OUT.mkdir(parents=True, exist_ok=True)
    jpath = OUT / "dolls.json"
    db = json.loads(jpath.read_text()) if jpath.exists() else {}
    db.setdefault("units", {})
    db["_about"] = ("Paper-doll index masks from tools/art/paper_doll.py. <unit>_doll.png: R = location index, A = 0 "
                    "outside. Mechs: SimMech.Body order, seen from behind (pilot's view, the mech's left on the left); "
                    "the rear doll is the same mask with Armor RCTORSO/RLTORSO/RRTORSO on locations 1/2/3. Vehicles, "
                    "infantry and powered armour: SimVehicle.Section order, plan view, forward up. Copters: SimMech "
                    "order, plan view. centroid = [x, y] in mask pixels.")
    shown = {}
    bad = []
    for u in todo:
        p = files[u]
        ov = over.get(u, {})
        T, owner, joints = load(p)
        if u in COPTERS:
            kind, names = "copter", MECH_LOCS
            lab = plan_doll(T, owner, u, ov, ov.get("size", 200))
        elif p.parent.name == "mechs":
            kind, names = "mech", MECH_LOCS
            lab, _ = mech_doll(T, owner, joints, ov, ov.get("height", a.height))
        else:
            kind, names = ("humanoid" if u in HUMANOID else "vehicle"), VEH_LOCS
            lab = plan_doll(T, owner, u, ov, ov.get("size", 200 if u in HUMANOID else 248))
        if a.debug:
            Path(a.debug).mkdir(parents=True, exist_ok=True)
            back = (np.array([-1.0, 0, 0]), np.array([0, 1.0, 0]), np.array([0, 0, -1.0]))
            joint_debug(T, owner, back, Path(a.debug) / f"{u}_joints.png")
        if u == "poweredarmor":  # SimVehicle in the sim (5 sections), but skinned like a mech: a mech doll too
            mov = over.get("poweredarmor_mech", {})
            mlab, _ = mech_doll(T, owner, joints, mov, mov.get("height", a.height))
            save_mask(mlab, 8, OUT / "poweredarmor_mech_doll.png")
            mst = stats(mlab, MECH_LOCS)
            db["units"]["poweredarmor_mech"] = {"kind": "mech", "size": [int(mlab.shape[1]), int(mlab.shape[0])],
                                                "view": "behind", "locations": mst, "overrides": sorted(mov)}
            shown["poweredarmor_mech"] = (mlab, "mech")
            if any(v["pixels"] == 0 for v in mst.values()):
                bad.append(("poweredarmor_mech", [k for k, v in mst.items() if v["pixels"] == 0]))
        save_mask(lab, len(names), OUT / f"{u}_doll.png")
        st = stats(lab, names)
        missing = [k for k, v in st.items() if v["pixels"] == 0 and not (kind != "mech" and k == "turret")]
        if missing:
            bad.append((u, missing))
        db["units"][u] = {"kind": kind, "size": [int(lab.shape[1]), int(lab.shape[0])],
                          "view": "behind" if kind == "mech" else "plan", "locations": st,
                          "overrides": sorted(k for k in ov if not k.startswith("_"))}
        shown[u] = (lab, kind)
        print(f"{u:16s} {kind:8s} {lab.shape[1]}x{lab.shape[0]} " +
              " ".join(f"{k}={v['pixels']}" for k, v in st.items()), flush=True)
    db["units"] = dict(sorted(db["units"].items()))
    jpath.write_text(json.dumps(db, indent=1) + "\n")
    if a.sheet:
        allu = {}
        for u in db["units"]:
            if u in shown:
                allu[u] = shown[u]
            elif (OUT / f"{u}_doll.png").exists():
                m = np.array(Image.open(OUT / f"{u}_doll.png"))
                allu[u] = (np.where(m[..., 3] > 0, m[..., 0], EMPTY).astype(np.int32), db["units"][u]["kind"])
        order = sorted(allu, key=lambda k: (allu[k][1] != "mech", allu[k][1], k))
        sheet({k: allu[k] for k in order}, REPO / a.sheet)
    for u, m in bad:
        print(f"FAIL {u}: no pixels for {', '.join(m)}", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
