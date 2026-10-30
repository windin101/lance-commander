#!/usr/bin/env python3
"""Hunter's lowpoly + UV stage (LANCE-18), in place of v3_stages.stage_lowpoly (which packs every part with xatlas):

    python3 -I tools/art/v3/hunter_lowpoly.py [--skip-decimate]

  1. v3_blender.py lowpoly (merge, planar dissolve at --planar-deg, collapse to the per-part budgets below).
  2. UVs. The hull and the turret are packed by xatlas (v3_xatlas.py) as for every v3 asset, into the top part of the
     2048 atlas (v scaled by 1 - STRIP). The two belts get a *tread strip* along the bottom of the atlas, which is what
     VehicleRig scrolls (unit_v3.gdshader wraps v inside [v0, v0 + v_len]):
       - u across the belt (x), 640 px/m, track_l in the left half, track_r in the right half;
       - v along the belt's path (the side-view arc of the visible track), modulo one strip period of N_LINKS link
         pitches, so every link repeats the same strip texels (the bake keeps the one that wrote last: the links are
         identical blocks). Triangles are split where they cross a period boundary; the boundaries sit mid-link so
         the cut runs across a block.
       - v grows toward the REAR on the ground run (the belt's visible run moves rearward when the tank drives
         forward, and the shader moves the texture toward +v with the scroll).
Writes low_geo.npz, low.npz (P, F, part, kind, uv per corner, v up: the bake convention) and tracks.json (the strip in
glTF UV space, belt_m)."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import v3_common as C  # noqa: E402


WORK = Path("/mnt/nvme1n1p1/mc2-rework/v3/hunter")
BUDGET = {"Hunter": 60000, "Hunter_Turret": 60000, "track_l": 60000, "track_r": 60000}   # no collapse: see decimate()
PLANAR_DEG = 8.0   # weld + dissolve only. Blender's COLLAPSE wrecks this kit's thin overlapping shells (turret: one giant black wedge)
WELD_M = 0.003          # the kit is tessellated at sub-mm on curves: weld at 2 mm or the collapse stalls (turret 332k -> 201k)
RES = 2048
PX_PER_M = 640.0


def decimate():
    z = np.load(WORK / "rest.npz")
    names = ["Hunter", "Hunter_Turret", "track_l", "track_r"]
    keep = np.isin(z["part"], names)                       # the wheels are generated (hunter_prep.make_wheel), not reduced
    pi = np.array([names.index(p) for p in z["part"][keep]])
    budget = np.array([BUDGET[n] for n in names])
    np.savez(WORK / "lp_in.npz", P=z["P"], F=z["F"][keep], part=pi, kind=z["kind"][keep].copy(), budget_part=np.arange(4),
             budget_faces=budget)
    C.blender("lowpoly", WORK / "lp_in.npz", WORK / "low_geo.npz", "--uv", "none", "--planar_deg", PLANAR_DEG, "--weld_m", WELD_M,
              log=WORK / "lowpoly.log")
    print((WORK / "lowpoly.log").read_text())


STRIP_PX = 256          # the tread strip's height in the atlas (bottom rows)
PAD_PX = 2              # inset of the declared strip inside its band
N_LINKS = 2             # link pitches per strip period
PITCH_MM = 220.0        # measured on the kit's ground run (170 mm block + 50 mm gap)
T_MM = N_LINKS * PITCH_MM
GAP_Y = -1842.5         # centre of a gap between two ground-run links (kit frame, mm): the period cuts go here
XIN = 770.0             # the belt's inner edge, |x| mm
SC = (STRIP_PX - 2 * PAD_PX) / T_MM   # px per mm, both ways
COLS = {"A": (0.0, 700.0), "B": (700.0, 700.0), "C0": (1400.0, 140.0), "C1": (1540.0, 140.0)}   # offset, width in mm
BELT_PX = (1400.0 + 280.0) * SC + 6 * 4


def belt_path(Pt):
    """The belt's centre line in the side view: the lower envelope of the track part, resampled every 2 mm in y.
    Returns (y, z, s: arclength from the front end, tangent unit vectors)."""
    ys = np.arange(Pt[:, 1].min(), Pt[:, 1].max(), 10.0)
    iy = np.clip(((Pt[:, 1] - ys[0]) / 10.0).astype(int), 0, len(ys) - 1)
    env = np.full(len(ys), 1e9)
    np.minimum.at(env, iy, Pt[:, 2])
    good = env < 1e8
    env = np.interp(ys, ys[good], env[good])
    from scipy import ndimage as ndi
    env = ndi.uniform_filter1d(env, 5, mode="nearest")
    yy = np.arange(ys[0], ys[-1], 2.0)
    zz = np.interp(yy, ys, env)
    seg = np.hypot(np.diff(yy), np.diff(zz))
    s = np.r_[0.0, np.cumsum(seg)]
    t = np.stack([np.gradient(yy), np.gradient(zz)], 1)
    t /= np.linalg.norm(t, axis=1, keepdims=True)
    return yy, zz, s, t


def clip_tri(pts, ss, lo, hi):
    """Sutherland-Hodgman clip of a polygon (positions pts, values ss) to lo <= s <= hi."""
    def cut(poly, keep_ge, level):
        out = []
        for i in range(len(poly)):
            a, b = poly[i], poly[(i + 1) % len(poly)]
            ina = (a[1] >= level) if keep_ge else (a[1] <= level)
            inb = (b[1] >= level) if keep_ge else (b[1] <= level)
            if ina:
                out.append(a)
            if ina != inb:
                u = (level - a[1]) / (b[1] - a[1])
                out.append((a[0] + (b[0] - a[0]) * u, level))
        return out
    poly = list(zip(pts, ss))
    poly = cut(poly, True, lo)
    if len(poly) >= 3:
        poly = cut(poly, False, hi)
    return poly


def track_uvs(Pt, Ft, sign):
    """Per-corner UVs (bake convention, v up) for one belt; Pt, Ft its low-poly part. Returns (P, F, uv per corner)."""
    from scipy.spatial import cKDTree
    yy, zz, sp, tg = belt_path(Pt)
    tree = cKDTree(np.stack([yy, zz], 1))
    _, ni = tree.query(Pt[:, 1:3])
    sv = sp[ni]
    s_gap = sp[np.argmin(np.abs(yy - GAP_Y))]          # a gap on the ground run: period cuts at s_gap + k*T
    newP, newF, newUV = [], [], []
    base_u = 8.0 + (0.0 if sign > 0 else 1000.0)
    Pn = np.asarray(Pt, float)
    for f in Ft:
        p3 = Pn[f]; s3 = sv[f]
        nrm = np.cross(p3[1] - p3[0], p3[2] - p3[0]); nl = np.linalg.norm(nrm)
        if nl < 1e-9:
            continue
        nrm /= nl
        cen = p3.mean(0)
        _, ci = tree.query(cen[1:3])
        o = np.array([tg[ci][1], -tg[ci][0]])           # outward (down) normal in (y, z)
        no = nrm[1] * o[0] + nrm[2] * o[1]
        if abs(nrm[0]) > 0.7:
            col = "C0" if nrm[0] * sign > 0 else "C1"
        else:
            col = "A" if no > -0.3 else "B"
        k0 = int(np.floor((s3.min() - s_gap) / T_MM)); k1 = int(np.floor((s3.max() - 1e-6 - s_gap) / T_MM))
        for k in range(k0, k1 + 1):
            lo, hi = s_gap + k * T_MM, s_gap + (k + 1) * T_MM
            poly = clip_tri(list(p3), list(s3), lo, hi) if k0 != k1 else list(zip(p3, s3))
            if len(poly) < 3:
                continue
            idx0 = len(newP)
            for pos, sval in poly:
                frac = np.clip((sval - lo) / T_MM, 0.0, 1.0)
                zi = tree.query(pos[1:3])[1] if col in ("C0", "C1") else 0
                off, wid = COLS[col]
                if col in ("A", "B"):
                    d = abs(pos[0]) - XIN
                else:
                    d = np.clip(pos[2] - zz[tree.query(pos[1:3])[1]], 0, wid)
                u = (base_u + off * SC + (6 * 4 / 4) * ("A B C0 C1".split().index(col)) + np.clip(d, 0, wid) * SC) / 2048.0
                v = (PAD_PX + (1.0 - frac) * (STRIP_PX - 2 * PAD_PX)) / 2048.0
                newP.append(pos); newUV.append((u, v))
            for j in range(1, len(poly) - 1):
                newF.append((idx0, idx0 + j, idx0 + j + 1))
    return np.array(newP), np.array(newF), np.array(newUV), s_gap


def uv_pack():
    z = np.load(WORK / "low_geo.npz")
    P, F, part, kind = z["P"], z["F"], z["part"], z["kind"]
    # hull + turret: xatlas, then squeezed into the atlas above the tread strip
    hm = part < 2
    import hunter_prep as HP
    refV, refF = HP.make_wheel(HP.WHEELS[0][2])          # one wheel packed with the body: all 16 wheels share its UVs
    Pb = np.concatenate([P, refV]); Fb = np.concatenate([F[hm], refF + len(P)])
    np.savez(WORK / "low_geo_body.npz", P=Pb, F=Fb, part=np.r_[part[hm], np.full(len(refF), 99)],
             kind=np.zeros(len(Fb), np.int32))
    py = "/mnt/nvme1n1p1/mc2-rework/v3/venv/bin/python"
    r = subprocess.run([py, "-I", str(HERE / "v3_xatlas.py"), str(WORK / "low_geo_body.npz"), str(WORK / "low_body.npz"),
                        "--res", str(RES), "--padding", "4", "--minor", "0.5"], capture_output=True, text=True)
    print(r.stdout.strip()[-200:], r.stderr.strip()[-500:])
    zb = np.load(WORK / "low_body.npz")
    sv = (STRIP_PX + 8) / RES
    uvb = zb["uv"].reshape(-1, 3, 2).copy()
    uvb[..., 1] = sv + uvb[..., 1] * (1.0 - sv)
    isref = zb["part"] == 99
    uv_ref = uvb[isref]
    Ps, Fs, parts, uvs = [P], [zb["F"][~isref]], [zb["part"][~isref]], [uvb[~isref]]
    off = len(P)
    for pi, sign in ((2, 1), (3, -1)):
        m = part == pi
        Pn, Fn, UV, s_gap = track_uvs(P[np.unique(F[m])][np.searchsorted(np.unique(F[m]), np.arange(0))], None, sign) if False else (None, None, None, None)
        used = np.unique(F[m]); remap = -np.ones(len(P), int); remap[used] = np.arange(len(used))
        Pt, Ft = P[used], remap[F[m]]
        Pn, Fn, UV, s_gap = track_uvs(Pt, Ft, sign)
        key = np.round(Pn, 3)
        _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
        Ps.append(Pn[first]); Fs.append(inv[Fn] + off); off += len(first)
        parts.append(np.full(len(Fn), pi)); uvs.append(UV[Fn])
        print(f"track {pi}: {len(Ft)} -> {len(Fn)} faces, {len(first)} verts")
    ax = json.loads((WORK.parent.parent / "work/hunter_tracks/axles.json").read_text())
    for k, nm in enumerate(HP.wheel_names()):             # the sixteen wheels: own geometry, the shared reference UVs
        sign = 1 if nm.startswith("wheel_l") else -1
        y, z, rad = [(a[1], a[2], a[3]) for n2, a in ax.items() if n2 == nm][0]
        Vw, Fw = HP.make_wheel(rad)
        Ps.append(HP.wheel_world(sign, y, z, Vw)); Fs.append(Fw + off); off += len(Vw)
        parts.append(np.full(len(Fw), 4 + k)); uvs.append(uv_ref)
    P2 = np.concatenate(Ps)
    F2 = np.concatenate(Fs); part2 = np.concatenate(parts)
    uv2 = np.concatenate(uvs).reshape(-1, 2).astype(np.float32)
    np.savez_compressed(WORK / "low.npz", P=P2, F=F2, part=part2, kind=np.zeros(len(F2), np.int32), uv=uv2)
    v0 = 1.0 - (PAD_PX + STRIP_PX - 2 * PAD_PX) / RES      # glTF v of the strip's top edge (bake v is up)
    vlen = (STRIP_PX - 2 * PAD_PX) / RES
    strip = {"v0": v0, "v_len": vlen, "belt_m": T_MM / 1000.0, "n_links": N_LINKS, "pitch_mm": PITCH_MM}
    (WORK / "tracks.json").write_text(json.dumps(strip, indent=1))
    print("low.npz:", len(F2), "faces; strip", strip)


if __name__ == "__main__":
    if "--skip-decimate" not in sys.argv:
        decimate()
    uv_pack()
