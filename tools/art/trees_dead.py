#!/usr/bin/env python3
"""Dead and leafless HD trees for tools/art/trees.py (terrain polish round 3, 2026-11-01).

The first dead trees were a bark tube with 7-9 straight sticks: thin black lines at RTS range. These are grown:
a gnarled, tapering, base-flared trunk, primary limbs, secondary branches and twigs as connected tube paths
(parallel-transport rings, shared vertices), with sprays of bare twigs (alpha cards from `twigs.png`) at the branch
tips and along the finer branches, so the crown has a lace-like mass and a shadow instead of three black lines.

    grow_dead(kind, H, W, rng, bark, twigs, variant) -> fills two trees.Mesh objects
      bark   tube paths, UV on `bark_dead.png` (weathered silver-grey, from the CC0 Poly Haven pine bark)
      twigs  crossed cards on `twigs.png` (2 cells of 512 px: 0 a long twig spray, 1 a dense fan), drawn
             procedurally by `make_twig_atlas` (no third-party image)

Styles: oak (wide gnarled limbs), maple (upright limbs), willow (arching limbs that droop), birch (slender pale
leader with short upswept branches), pine (a snag: straight, broken top, drooping dead branch stubs).
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


# --- textures -------------------------------------------------------------------------------------------------

def make_twig_atlas(path, seed=11):
    """twigs.png (1024 x 512): two 512 px cells of bare twig sprays growing from the left edge to the right,
    dark grey-brown (the shader tints it per tree), thick enough that mips keep a coverage."""
    rng = np.random.default_rng(seed)
    S = 4   # supersample
    W = 512 * S

    def draw_spray(im, ox, dense):
        d = ImageDraw.Draw(im)

        def twig(x, y, ang, length, width, depth):
            if length < 10 * S or depth > 5:
                return
            pts = [(x, y)]
            n = 6
            a = ang
            for _ in range(n):
                a += rng.normal(0, 0.10)
                x += math.cos(a) * length / n
                y += math.sin(a) * length / n
                pts.append((x, y))
            w = max(2, int(width))
            for i in range(n):
                wi = max(2, int(width * (1 - 0.7 * i / n)))
                d.line([pts[i], pts[i + 1]], fill=(255, 255, 255, 255), width=wi)
            kids = (3 if dense else 2) if depth < 3 else 1
            for k in range(kids):
                t = rng.uniform(0.25, 0.9)
                px = pts[0][0] + (pts[-1][0] - pts[0][0]) * t
                py = pts[0][1] + (pts[-1][1] - pts[0][1]) * t
                side = 1 if (k + depth) % 2 == 0 else -1
                twig(px, py, a + side * rng.uniform(0.4, 0.95), length * rng.uniform(0.35, 0.6), width * 0.62, depth + 1)
            twig(pts[-1][0], pts[-1][1], a + rng.normal(0, 0.25), length * 0.45, width * 0.6, depth + 1)

        base_y = 256 * S
        if dense:   # a fan: several leaders at spread angles
            for ang in np.linspace(-0.85, 0.85, 5):
                twig(8 * S, base_y, ang, 330 * S, 11 * S, 0)
        else:       # a long spray along one axis
            twig(8 * S, base_y, rng.normal(0, 0.05), 470 * S, 13 * S, 0)
            twig(100 * S, base_y, -0.5, 190 * S, 9 * S, 1)
            twig(150 * S, base_y, 0.5, 190 * S, 9 * S, 1)

    atlas = Image.new("RGBA", (1024, 512), (0, 0, 0, 0))
    for cell in range(2):
        im = Image.new("RGBA", (W, W), (0, 0, 0, 0))
        draw_spray(im, 0, dense=bool(cell))
        a = np.asarray(im.resize((512, 512), Image.LANCZOS))[..., 3].astype(float) / 255.0
        a = np.clip(a * 1.25, 0, 1)
        # colour: weathered grey-brown with a little variation along the card, so a spray is not a flat silhouette
        yy, xx = np.mgrid[0:512, 0:512]
        v = 0.50 + 0.18 * np.sin(xx / 61.0 + cell * 2.0) * np.cos(yy / 47.0) + rng.normal(0, 0.03, (512, 512))
        rgb = np.stack([v * 0.92, v * 0.88, v * 0.82], -1)
        rgb = np.clip(rgb, 0, 1)
        out = np.dstack([rgb * 255, a * 255]).astype(np.uint8)
        atlas.paste(Image.fromarray(out, "RGBA"), (cell * 512, 0))
    arr = np.asarray(atlas).copy()
    # bleed colour into the transparent texels so mips do not pull the edge dark or to white
    rgb = Image.fromarray(arr[..., :3]).filter(ImageFilter.MaxFilter(9))
    m = arr[..., 3] > 20
    arr[..., :3] = np.where(m[..., None], arr[..., :3], np.asarray(rgb))
    Image.fromarray(arr, "RGBA").save(path, optimize=True)


def make_dead_bark(src_bark, path):
    """bark_dead.png: the live bark tile, bleached to a weathered silver-grey with darker cracks and a slight
    vertical streaking, so dead wood reads as pale against dark ground."""
    im = Image.open(src_bark).convert("RGB").resize((512, 512), Image.LANCZOS)
    a = np.asarray(im).astype(float) / 255.0
    g = a @ np.array([0.30, 0.59, 0.11])
    g = (g - g.min()) / (g.max() - g.min() + 1e-6)
    g = np.clip(0.3 + 0.55 * g, 0, 1)
    rng = np.random.default_rng(5)
    n = rng.normal(0, 1, (64, 8))
    streak = np.asarray(Image.fromarray(((n - n.min()) / (n.max() - n.min()) * 255).astype(np.uint8)).resize(a.shape[1::-1], Image.BICUBIC)).astype(float) / 255.0
    g = g * (0.78 + 0.35 * streak)
    rgb = np.stack([g * 1.0, g * 0.86, g * 0.7], -1)
    Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(path, optimize=True)


# --- geometry -------------------------------------------------------------------------------------------------

def _norm(v):
    return v / (np.linalg.norm(v) + 1e-9)


def _perp(d):
    a = np.array([0.0, 0.0, 1.0]) if abs(d[1]) > 0.9 else np.array([0.0, 1.0, 0.0])
    return _norm(np.cross(d, a))


def tube_path(m, pts, radii, col_a, col_b=None, sides=6, v_scale=1.0, cap=None, wobble=0.0, rng=None):
    """A connected, tapered tube along `pts` (rings share vertices; frames by parallel transport). `wobble` makes each
    ring an irregular, gnarled section. `cap` (radius factor) closes the last ring with a flat disc (a broken top)."""
    pts = [np.asarray(p, float) for p in pts]
    n = len(pts)
    base = len(m.p)
    u = None
    cum = 0.0
    col_b = col_a if col_b is None else col_b
    for i in range(n):
        if i == 0:
            t = _norm(pts[1] - pts[0])
        elif i == n - 1:
            t = _norm(pts[-1] - pts[-2])
        else:
            t = _norm(pts[i + 1] - pts[i - 1])
        if u is None:
            u = _perp(t)
        else:
            u = _norm(u - t * np.dot(u, t))
        v = np.cross(t, u)
        if i:
            cum += float(np.linalg.norm(pts[i] - pts[i - 1]))
        f = i / max(1, n - 1)
        col = [col_a[j] * (1 - f) + col_b[j] * f for j in range(4)]
        phase = rng.uniform(0, 6.28) if rng is not None else 0.0
        urep = max(1, round(2 * math.pi * float(radii[0]) / 1.1))
        for k in range(sides + 1):
            ang = 2 * math.pi * k / sides
            rr = float(radii[i])
            if wobble and rng is not None:
                rr *= 1.0 + wobble * math.sin(3 * ang + phase + i * 1.3) * 0.6
            d = u * math.cos(ang) + v * math.sin(ang)
            m.p.append((pts[i] + d * rr).tolist())
            m.n.append(d.tolist())
            m.uv.append([k / sides * urep, cum / 1.8 * v_scale])
            m.c.append(col)
    for i in range(n - 1):
        for k in range(sides):
            a = base + i * (sides + 1) + k
            b = a + 1
            c = a + (sides + 1)
            d = c + 1
            m.i += [a, c, b, b, c, d]
    if cap:
        t = _norm(pts[-1] - pts[-2])
        c0 = len(m.p)
        m.p.append((pts[-1] + t * 0.02).tolist())
        m.n.append(t.tolist())
        m.uv.append([0.5, cum / 1.8])
        m.c.append(col_b)
        ring = base + (n - 1) * (sides + 1)
        for k in range(sides):
            m.i += [ring + k, c0, ring + k + 1]


def _fix_winding(m, start):
    """Flip triangles whose geometric normal opposes their vertex normals (the tube winding is built blind)."""
    P = np.asarray(m.p)
    N = np.asarray(m.n)
    for j in range(start, len(m.i), 3):
        a, b, c = m.i[j:j + 3]
        gn = np.cross(P[b] - P[a], P[c] - P[a])
        if np.dot(gn, N[a] + N[b] + N[c]) < 0:
            m.i[j + 1], m.i[j + 2] = m.i[j + 2], m.i[j + 1]


def twig_spray(tw, p, d, size, tint, normal_from, rng, cell=None, roll=None):
    """Two cards crossed at 90 degrees along direction d, starting at p (the spray grows out of a branch)."""
    d = _norm(np.asarray(d, float))
    c = (0 if rng.random() < 0.8 else 1) if cell is None else cell
    u0, v0 = c * 0.5, 0.0
    e = 0.004
    uv = [[u0 + e, 1 - e], [u0 + 0.5 - e, 1 - e], [u0 + 0.5 - e, v0 + e], [u0 + e, v0 + e]]   # image row 0 at v=0 -> flip v
    uv = [[a, 1.0 - b] for a, b in uv]
    p0 = _perp(d)
    p1 = _norm(np.cross(d, p0))
    ang = rng.uniform(0, math.pi) if roll is None else roll
    up_a = p0 * math.cos(ang) + p1 * math.sin(ang)
    up_b = np.cross(d, up_a)
    for up in (up_a, up_b):
        w, h = size, size * 0.95
        pts = [p + d * 0.0 - up * h / 2, p + d * w - up * h / 2, p + d * w + up * h / 2, p + up * h / 2]
        nrm = []
        for q in pts:
            nn = q - np.asarray(normal_from, float)
            nn = nn / (np.linalg.norm(nn) + 1e-9) * 0.6 + np.array([0, 0.4, 0])
            nrm.append((nn / np.linalg.norm(nn)).tolist())
        tw.quad([q.tolist() for q in pts], uv, nrm, tint)


class Style:
    """How one kind of dead tree grows."""
    def __init__(self, **kw):
        self.trunk_frac = 0.4        # height of the trunk before the limbs, fraction of H
        self.n_limbs = 5
        self.limb_elev = (35, 65)    # degrees from vertical
        self.limb_len = 0.5          # primary limb length, fraction of H
        self.grav = 0.0              # bend per metre-ish (negative droops)
        self.wobble = 0.22           # direction noise per segment
        self.child_ang = (28, 60)
        self.child_len = 0.62
        self.depth = 2
        self.r_trunk = 0.034         # base radius, fraction of H
        self.taper = 0.22            # tip/base radius of the trunk
        self.twig_density = 1.0
        self.twig_tint = (0.52, 0.42, 0.31, 1.0)
        self.leader = False          # trunk continues as a straight leader (birch, pine)
        self.break_top = False
        self.kids_per = 3
        self.spray = 1.5
        self.__dict__.update(kw)


STYLES = {
    "oak": Style(trunk_frac=0.34, n_limbs=5, limb_elev=(55, 82), limb_len=0.62, grav=-0.04, wobble=0.34, r_trunk=0.046,
                 taper=0.30, child_ang=(30, 70), kids_per=3, spray=1.05),
    "maple": Style(trunk_frac=0.44, n_limbs=6, limb_elev=(22, 52), limb_len=0.52, grav=0.05, wobble=0.22, r_trunk=0.032,
                   taper=0.22, child_ang=(24, 50), kids_per=3, spray=1.3),
    "willow": Style(trunk_frac=0.36, n_limbs=6, limb_elev=(40, 66), limb_len=0.62, grav=-0.22, wobble=0.26, r_trunk=0.040,
                    taper=0.26, child_ang=(26, 56), kids_per=3, spray=1.05, child_len=0.7),
    "birch": Style(trunk_frac=0.55, n_limbs=7, limb_elev=(22, 46), limb_len=0.34, grav=0.02, wobble=0.12, r_trunk=0.020,
                   taper=0.12, child_ang=(24, 44), depth=2, leader=True, kids_per=2, spray=1.0,
                   twig_tint=(0.62, 0.52, 0.42, 1.0)),
    "pine": Style(trunk_frac=0.18, n_limbs=0, wobble=0.05, r_trunk=0.026, taper=0.16, leader=True, break_top=True,
                  depth=2, kids_per=2, spray=1.0, twig_tint=(0.5, 0.4, 0.3, 1.0)),
}


def _rotate_about(v, axis, ang):
    axis = _norm(axis)
    c, s = math.cos(ang), math.sin(ang)
    return v * c + np.cross(axis, v) * s + axis * np.dot(axis, v) * (1 - c)


def grow_dead(style_name, H, W, rng, bark, twigs, bark_col, variant=0):
    S = STYLES[style_name]
    b0, t0 = len(bark.i), len(twigs.i)
    pale = bark_col[0] > 0.9   # birch keeps its white bark
    wood_lo = np.array(bark_col[:3]) * (0.55 if not pale else 0.8)
    wood_hi = np.array(bark_col[:3]) * (1.15 if not pale else 1.0)
    col_base = list(np.clip(wood_lo, 0, 1.2)) + [1.0]
    col_top = list(np.clip(wood_hi, 0, 1.2)) + [1.0]
    tint = list(S.twig_tint)
    centre = np.array([0.0, H * 0.62, 0.0])

    def branch(p0, d0, length, r0, depth, sides):
        nseg = int(np.clip(round(length / 2.6), 2, 4))
        pts = [np.asarray(p0, float)]
        d = _norm(np.asarray(d0, float))
        dirs = []
        for _ in range(nseg):
            d = _norm(d + rng.normal(0, S.wobble, 3) * 0.6 + np.array([0, S.grav / max(1, nseg) * 2.2, 0]))
            dirs.append(d)
            pts.append(pts[-1] + d * length / nseg)
        radii = [r0 * (1 - (1 - 0.18) * (i / nseg)) for i in range(nseg + 1)]
        tube_path(bark, pts, radii, col_base if depth == 0 else col_top, col_top, sides=sides, rng=rng, wobble=0.25 if depth < 2 else 0.0)
        # children
        if depth < S.depth and r0 > 0.02:
            nk = (S.kids_per if depth == 0 else max(2, S.kids_per - 1))
            for j in range(nk):
                s = rng.uniform(0.28, 0.95)
                idx = min(nseg - 1, int(s * nseg))
                f = s * nseg - idx
                pp = pts[idx] * (1 - f) + pts[idx + 1] * f
                dd = dirs[idx]
                rr = radii[idx] * (1 - f) + radii[idx + 1] * f
                ax = _perp(dd)
                ax = _rotate_about(ax, dd, rng.uniform(0, 2 * math.pi))
                ang = math.radians(rng.uniform(*S.child_ang))
                cd = _rotate_about(dd, ax, ang)
                cd = _norm(cd + np.array([0, S.grav * 0.5, 0]))
                clen = length * (1 - 0.55 * s) * S.child_len * rng.uniform(0.8, 1.1)
                branch(pp, cd, max(0.5, clen), max(0.012, rr * 0.62), depth + 1, 3 if depth + 1 >= 2 else 4)
        # twig sprays at the tip, and along the finer branches
        if depth >= S.depth - 1 and S.twig_density > 0:   # (depth - 1 branches carry a spray at the tip too)
            twig_spray(twigs, pts[-1] - dirs[-1] * 0.2, dirs[-1], S.spray * rng.uniform(0.8, 1.15) * (1.0 if depth == S.depth else 0.7),
                       tint, centre, rng)
            if depth == S.depth and length > 1.4 and rng.random() < 0.2 * S.twig_density:
                sd = _rotate_about(dirs[0], _perp(dirs[0]), math.radians(rng.choice([-1, 1]) * 40))
                twig_spray(twigs, pts[nseg // 2], sd, S.spray * 0.7, tint, centre, rng)

    # --- trunk: a gnarled, tapering, leaning path with a flared base
    th = H * (S.trunk_frac if not S.leader else (0.9 if style_name == "birch" else 0.82))
    if style_name == "pine":
        th = H * rng.uniform(0.78, 0.93)
    r0 = max(0.13, H * S.r_trunk)
    nseg = 9
    lean = _norm(np.array([rng.normal(), 0.0, rng.normal()]))
    leanamt = rng.uniform(0.01, 0.05) * th
    pts, radii = [], []
    for i in range(nseg + 1):
        f = i / nseg
        wob = rng.normal(0, S.wobble * 0.22 * (1.0 if style_name != "pine" else 0.3), 2)
        p = np.array([wob[0] * th * 0.05, th * f, wob[1] * th * 0.05]) + lean * leanamt * f * f * 2
        pts.append(p)
        flare = 1.0 + 0.32 * math.exp(-f * 12.0)
        radii.append(r0 * (1 - (1 - S.taper) * f ** 0.8) * flare)
    pts[0] = pts[0] + [0, -0.5, 0]
    trunk_sides = 8
    tube_path(bark, pts, radii, col_base, col_top, sides=trunk_sides, cap=0.9 if S.break_top else None, wobble=0.5, rng=rng)
    # roots: short buttress tubes
    for k in range(4):
        a = rng.uniform(0, 2 * math.pi) + k * 1.6
        d = np.array([math.cos(a), -0.35, math.sin(a)])
        q0 = pts[1] * 0.3 + [0, 0.15, 0]
        rl = r0 * rng.uniform(1.8, 3.0)
        tube_path(bark, [q0, q0 + d * rl * 0.5 + [0, 0.05, 0], q0 + d * rl + [0, -0.12, 0]],
                  [r0 * 0.62, r0 * 0.42, r0 * 0.12], col_base, col_base, sides=5, rng=rng)

    # --- limbs
    if S.n_limbs:
        a0 = rng.uniform(0, 2 * math.pi)
        for k in range(S.n_limbs):
            f = rng.uniform(0.78, 1.0) if not S.leader else rng.uniform(0.35, 0.95)
            idx = int(f * nseg)
            idx = min(idx, nseg - 1)
            p = pts[idx]
            r_here = radii[idx]
            a = a0 + k * 2.399 + rng.normal(0, 0.25)
            elev = math.radians(rng.uniform(*S.limb_elev))
            d = np.array([math.sin(elev) * math.cos(a), math.cos(elev), math.sin(elev) * math.sin(a)])
            L = H * S.limb_len * rng.uniform(0.75, 1.1) * (1.0 if not S.leader else (1.1 - 0.9 * f))
            branch(p, d, max(1.0, L), r_here * rng.uniform(0.5, 0.65), 0, 5)
        # the trunk's own top breaks into 2-3 leaders (broadleaf styles)
        if not S.leader:
            top = pts[-1]
            for k in range(3):
                a = a0 + k * 2.1 + rng.normal(0, 0.3)
                elev = math.radians(rng.uniform(S.limb_elev[0] * 0.5, S.limb_elev[0] * 0.9 + 10))
                d = np.array([math.sin(elev) * math.cos(a), math.cos(elev), math.sin(elev) * math.sin(a)])
                branch(top, d, H * (1 - S.trunk_frac) * rng.uniform(0.55, 0.8), radii[-1] * 0.8, 0, 5)
    if style_name == "pine":   # a snag: dead branch stubs down the trunk, long and drooping low, shorter and stiff high
        nb = int(rng.integers(11, 15))
        for k in range(nb):
            f = 0.22 + 0.7 * (k + rng.random() * 0.6) / nb
            f = min(f, 0.97)
            idx = min(nseg - 1, int(f * nseg))
            p = pts[idx] * (1 - (f * nseg - idx)) + pts[idx + 1] * (f * nseg - idx)
            a = k * 2.399 + rng.uniform(-0.4, 0.4)
            drop = -0.25 - 0.3 * (1 - f)
            d = _norm(np.array([math.cos(a), drop, math.sin(a)]))
            L = (0.55 + 3.6 * (1 - f)) * (W / 4.6) * rng.uniform(0.6, 1.15)
            if rng.random() < 0.25:
                L *= 0.3   # broken stub
            branch(p, d, L, max(0.03, radii[idx] * 0.35), S.depth - 1, 4)
    if style_name == "birch":
        pass
    _fix_winding(bark, b0)
    _fix_winding(twigs, t0)
