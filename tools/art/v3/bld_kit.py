#!/usr/bin/env python3
"""v3 building kit (LANCE-21 family rollout): shared pieces for the procedural buildings of tools/art/v3/bld_*.py.

Ctx        one building in one state/LOD: a Builder with the baked burn, run-off and AO hooks, decal helpers.
round_tank a parameterised vertical tank (drum, belt, catwalk, ladder, domed lid) with the three states: intact, a shell torn
           open with curled edges (Builder.cut_surface), and a wreck (jagged ring, collapsed lid wedges). largefueltank,
           the pilot, is bld_tanks.py; the other round members call this.
wall/roof  planar panels with the same exact cut (Builder.cut_param) for the sheds.
Frame: metres, Y up, the original's axes. All geometry is new; dimensions are measured from the Shared Source originals.
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bld_mesh import Builder, rot_y, unit, TAU  # noqa: E402

K = 0.30
CELLS = {"panel": 0, "diamond": 1, "id_plate": 2, "hatch": 3, "arrow": 4, "streak_a": 5, "streak_b": 6, "oil": 7,
         "soot": 8, "rust_bleed": 9, "stripe_corner": 10, "valve_tag": 11}


def uref(r, tile):
    return tile * max(1, round(TAU * r / tile)) / TAU


def cell_uv(name, inset=0.004):
    i = CELLS[name]
    c, r = i % 4, i // 4
    return (c / 4 + inset, r / 4 + inset, (c + 1) / 4 - inset, (r + 1) / 4 - inset)


def digit_uv(d):
    return (d * 102.4 / 1024 + 0.003, 896 / 1024 + 0.004, (d + 1) * 102.4 / 1024 - 0.003, 1.0 - 0.004)


def axis_angle(ax, a):
    ax = unit(ax); x, y, z = ax
    c, s = math.cos(a), math.sin(a); t = 1 - c
    return np.array([[t * x * x + c, t * x * y - s * z, t * x * z + s * y],
                     [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
                     [t * x * z - s * y, t * y * z + s * x, t * z * z + c]])


class Ctx:
    def __init__(self, state, lod, seed, breach=None, ledges=(), ao_rings=(), ground_h=2.0):
        self.state, self.lod = state, lod
        self.fine = lod == 0
        self.rng = np.random.default_rng(seed)
        self.b = Builder()
        self.b.seg_cap = 0 if self.fine else 4
        self.breach = breach            # (x, y, z, radius): where the damaged state is hurt
        self.ledges = list(ledges)      # (y, run-off length, strength): run-off streaks below a ledge or eave
        self.ao_rings = list(ao_rings)  # (y, length, strength): occlusion below an overhang
        self.ground_h = ground_h
        self.b.colfn = self._burn
        self.b.wearfn = self._wear
        self.b.aofn = self._ao

    def _burn(self, P):
        if self.state == "intact":
            return np.zeros(len(P))
        y = P[:, 1]
        if self.state == "destroyed":
            return np.clip(0.85 + 0.3 * np.exp(-y / 6.0) + 0.1 * np.sin(P[:, 0] * 1.3 + P[:, 2] * 0.7), 0, 1)
        if self.breach is None:
            return np.zeros(len(P))
        bx, by, bz, br = self.breach
        d = np.sqrt((P[:, 0] - bx) ** 2 + (y - by) ** 2 + (P[:, 2] - bz) ** 2)
        return np.clip(np.exp(-(d / (1.4 * br)) ** 2) * 1.7 + 0.2 * np.exp(-y / 3.0), 0, 1)

    def _wear(self, P, N):
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        g = np.zeros(len(P))
        wall = np.abs(N[:, 1]) < 0.6
        for k, (y0, L, a) in enumerate(self.ledges):
            gate = np.clip(0.45 + 1.1 * np.sin(x * (2.6 + 0.4 * k) + z * 1.9 + k) * np.sin(z * 2.2 - x * 1.3 + 2 * k), 0, 1)
            d = y0 - y
            g = np.maximum(g, np.where(wall & (d > 0) & (d < L), a * np.clip(1 - d / L, 0, 1) ** 0.8 * gate, 0))
        g = np.maximum(g, np.where(wall, 0.45 * np.clip(1 - y / 3.0, 0, 1), 0))
        return np.clip(g, 0, 1)

    def _ao(self, P, N):
        y = P[:, 1]
        ao = 0.6 + 0.4 * np.clip(y / self.ground_h, 0, 1)
        for (y0, L, s) in self.ao_rings:
            d = y0 - y
            ao = np.where((d > 0) & (d < L) & (np.abs(N[:, 1]) < 0.6), ao * (1 - s * np.clip(1 - d / L, 0, 1)), ao)
        ao = np.where(N[:, 1] < -0.5, ao * 0.55, ao)
        return np.clip(ao, 0.15, 1.0)

    # ---------------------------------------------------------------- decals
    def decal_rev(self, cell, th, wid, y0, y1, R, cx=0.0, cz=0.0, uv=None, off=0.03, cols=4, rows=2):
        uv = uv or cell_uv(cell)
        P, U, N = [], [], []
        for j in range(rows + 1):
            y = y0 + (y1 - y0) * j / rows
            r = R + off
            for i in range(cols + 1):
                a = th + (i / cols - 0.5) * wid / r
                P.append((cx + r * math.cos(a), y, cz + r * math.sin(a)))
                N.append((math.cos(a), 0, math.sin(a)))
                U.append((uv[0] + (uv[2] - uv[0]) * (i / cols), uv[3] + (uv[1] - uv[3]) * (j / rows)))
        idx = []
        for j in range(rows):
            for i in range(cols):
                a = j * (cols + 1) + i
                idx += [(a, a + 1, a + cols + 1), (a + 1, a + cols + 2, a + cols + 1)]
        self.b.add("decal", P, N, U, idx)

    def decal_wall(self, cell, c, u_ax, w, y0, y1, normal, uv=None, off=0.03):
        """A flat decal on a vertical wall: c the point on the wall at the decal's horizontal centre, u_ax along the wall."""
        c = np.asarray(c, float); n = unit(normal)
        self.b.quad("decal", c + n * off + np.array([0, (y0 + y1) / 2, 0]), np.asarray(u_ax, float), np.array([0, 1.0, 0]), w, y1 - y0,
                    uv or cell_uv(cell), normal=n)

    def decal_ground(self, cell, c, w, h, rot=0.0, y=0.04):
        u = np.array([math.cos(rot), 0, math.sin(rot)]); v = np.array([-math.sin(rot), 0, math.cos(rot)])
        self.b.quad("decal", np.array([c[0], y, c[1]]), u, v, w, h, cell_uv(cell), normal=(0, 1, 0))

    def ring(self, mat, y0, y1, r, th, cx=0.0, cz=0.0, seg=None, col=(0, 0, 0)):
        sg = seg or self.seg
        self.b.revolve(mat, [(r + th, y0), (r + th, y1)], sg, cx=cx, cz=cz, uref=uref(r + th, 2.0), col=col)
        self.b.disc(mat, (cx, y1, cz), r + th, r_in=r - 0.02, seg=sg, col=col)
        self.b.disc(mat, (cx, y0, cz), r + th, (0, -1, 0), r_in=r - 0.02, seg=sg, col=col)

    seg = 72


# =====================================================================================================================
def round_tank(c: Ctx, p: dict):
    """p: R, cx, cz, y0, y1 (drum), lower [(mat, profile, tile)], lid [(r, y)...] from (R, y1), lid_mat, belt (ya, yb)|None,
    tint (ya, yb)|None, tint_dome (r0, y0, r1, y1)|None, welds [y], diamonds [(deg, ya, yb, w)], ids [(deg, ya, yb, w)], catwalk
    (y, r)|None, ladder_deg|None, ladder_top, lid_rail (r, y)|None, hatch (r, y, top_y)|None, breach_deg, id_digits."""
    b = c.b
    state, fine = c.state, c.fine
    R, cx, cz = p["R"], p.get("cx", 0.0), p.get("cz", 0.0)
    y0, y1 = p["y0"], p["y1"]
    H = y1 - y0
    SEG = 72 if fine else 40
    c.seg = SEG
    cut = state != "intact"
    SD = SEG if not cut else (144 if fine else 64)
    thc = math.radians(p.get("breach_deg", 85))
    uR = uref(R, 2.0)
    cwy = p["catwalk"][0] if p.get("catwalk") else None

    for mat, prof, tile in p.get("lower", []):
        b.revolve(mat, prof, SEG, cx=cx, cz=cz, uref=uref(max(r for r, _ in prof), tile))
    if p.get("floor_disc"):
        fd = p["floor_disc"]
        b.disc(fd[0], (cx, fd[2], cz), fd[1], seg=SEG)

    def ridge(th):
        teeth = 0.07 * H * np.abs(((np.asarray(th) * 9.0 / TAU * 2) % 2.0) - 1.0)
        return y0 + H * (0.46 + 0.19 * np.sin(2.1 * th + 0.7) + 0.1 * np.sin(5.3 * th) + 0.045 * np.sin(11.0 * th + 2.0)) + teeth

    def blob(th, y, yc, a, b_, dth=0.0, ph=0.0):
        u = ((np.asarray(th) - thc - dth + math.pi) % TAU - math.pi) * R
        v = np.asarray(y) - yc
        g = np.sqrt((u / a) ** 2 + (v / b_) ** 2)
        phi = np.arctan2(v / b_, u / a)
        rho = 1 + 0.17 * np.sin(5 * phi + 1 + ph) + 0.1 * np.sin(9 * phi + 2) + 0.06 * np.sin(17 * phi)
        return (g - rho) * min(a, b_) * 0.9

    if state == "destroyed":
        keep = lambda th, y: ridge(th) - y
    elif state == "damaged":
        keep = lambda th, y: np.minimum(blob(th, y, y0 + 0.66 * H, 0.44 * R, 0.245 * H), blob(th, y, y0 + 0.96 * H, 0.23 * R, 0.116 * H, 0.35, 1.0))
    else:
        keep = None

    def disp(th, y, k):
        w = np.clip(1 - k / (0.05 * H), 0, 1) ** 2
        return w * (0.011 * H + 0.018 * H * np.sin(th * 43.0 + 1.3) * np.cos(y * 3.1 / (H / 11.2) + th * 7.0))

    # ---- drum
    if not cut:
        rows = np.unique(np.r_[np.arange(y0, y1, H / 28), y1])
        b.revolve("paint", [(R, y) for y in rows], SD, cx=cx, cz=cz, uref=uR)
    else:
        dlo, dhi = (y0 + 0.34 * H, y1) if state == "damaged" else (y0 + 0.27 * H, y0 + 0.78 * H)
        rows = np.unique(np.round(np.r_[np.arange(y0, y1, H / 22), np.arange(dlo, dhi, H / (80 if fine else 37)), y1], 4))
        const = lambda r_: (lambda ys: np.full_like(ys, r_))
        b.cut_surface("paint", const(R), rows, SD, keep, cx=cx, cz=cz, disp=disp, uref=uR, thickness=0.008 * H)
        if state == "destroyed":
            b.cut_surface("interior", const(R - 0.1), rows, SD, keep, cx=cx, cz=cz, flip=True, uref=uref(R - 0.1, 2.0))
        else:
            b.revolve("interior", [(R - 0.1, y) for y in np.unique(np.r_[np.arange(y0, y1, H / 22), y1])], SD, cx=cx, cz=cz, flip=True, uref=uref(R - 0.1, 2.0))
        b.disc("interior", (cx, y0 + 0.05, cz), R - 0.1, seg=SEG)
    cullk = (lambda th, y: float(keep(th, y)) < 0.18) if cut else None
    kk = (lambda t, y: keep(t, y) - 0.2) if cut else None

    # ---- welds, beads
    TT = 4.0 / K
    for y in p.get("welds", []):
        if state == "destroyed" and y > y0 + 0.5 * H:
            continue
        half = [(R + 0.018 + 0.05 * math.sin(a), y + 0.07 * math.cos(a)) for a in np.linspace(math.pi / 2, -math.pi / 2, 7 if fine else 3)]
        b.revolve("trim", half, SD, cx=cx, cz=cz, cull=(lambda th, yy, y=y: cullk(th, y)) if cut else None, band=3, uref=uref(R, TT) * K, vscale=K * 0.5 / 0.14)
    for k in range(p.get("beads", 12)):
        a = TAU * (k + 0.5) / p.get("beads", 12)
        ytop = y1
        if cut:
            yy = np.arange(y0, y1, H / 100)
            kv = keep(np.full_like(yy, a), yy)
            if kv[0] < 0.2:
                continue
            bad = np.flatnonzero(kv < 0.25)
            ytop = yy[bad[0]] if len(bad) else y1
        b.tube("steel", (cx + R * math.cos(a), y0 + 0.02, cz + R * math.sin(a)), (cx + (R + 0.01) * math.cos(a), ytop, cz + (R + 0.01) * math.sin(a)), 0.004 * H + 0.02, 6, caps=False)

    # ---- belt and tint band
    def band(mat, ya, yb, bandi, col):
        rs = np.linspace(ya, yb, 12)
        if not cut:
            b.revolve("trim", [(R + 0.025, ya), (R + 0.025, yb)], SD, cx=cx, cz=cz, band=bandi, uref=uref(R, TT) * K, vscale=K, col=col)
        elif state == "damaged":
            b.cut_surface("trim", lambda ys: np.full_like(ys, R + 0.025), rs, SD, kk, cx=cx, cz=cz, band=bandi, uref=uref(R, TT) * K, vscale=K, col=col)
    if p.get("belt"):
        ya, yb = p["belt"]
        band("trim", ya, yb, 0, (0, 0, 0))
        c.ring("galv", ya - 0.12, ya + 0.1, R, 0.2, cx, cz)
    if p.get("tint"):
        ya, yb = p["tint"]
        band("trim", ya, yb, 6, (1, 0, 0))
        if state != "destroyed":
            c.ring("galv", y1 - 0.17, y1 + 0.05, R, 0.14, cx, cz)
    if fine:
        for yy in p.get("bolts", []):
            for k in range(int(R * 9)):
                a = TAU * (k + 0.5) / int(R * 9)
                q = np.array([cx + (R + 0.012) * math.cos(a), yy, cz + (R + 0.012) * math.sin(a)])
                b.tube("steel", q, q + np.array([math.cos(a), 0, math.sin(a)]) * 0.07, 0.05, 6)

    # ---- markings
    ok = lambda deg, yy: (not cut) or float(keep(math.radians(deg), yy)) > 1.2
    if state != "destroyed":
        for deg, ya, yb, w in p.get("diamonds", []):
            c.decal_rev("diamond", math.radians(deg), w, ya, yb, R, cx, cz, off=0.03)
        for deg, ya, yb, w in p.get("ids", []):
            c.decal_rev("id_plate", math.radians(deg), w, ya, yb, R, cx, cz, off=0.03, cols=8)
            for j, dgt in enumerate(p.get("id_digits", (0, 7))):
                c.decal_rev("id_plate", math.radians(deg) + (-0.17 + 0.34 * j) * w / R * 0.5, w * 0.32, ya + 0.12 * (yb - ya), yb - 0.1 * (yb - ya), R, cx, cz, uv=digit_uv(dgt), off=0.045, cols=2)
        step = max(14, int(360 / max(6, R * 2.4)))
        for k, deg in enumerate(range(5, 360, step)):
            top = cwy if cwy else y1 - 0.04 * H
            if ok(deg, top - 0.2 * H):
                c.decal_rev("streak_a" if k % 2 else "streak_b", math.radians(deg + (k * 7) % 9), 0.27 * R, top - 0.32 * H, top - 0.02, R, cx, cz, off=0.04)
        for k, deg in enumerate(range(0, 360, step * 2 // 1 + 3)):
            for yb_ in p.get("welds", [])[:2]:
                if (k + int(yb_)) % 2 == 0 and ok(deg, yb_ - 0.8):
                    c.decal_rev("rust_bleed", math.radians(deg + yb_), 0.19 * R, yb_ - 0.15 * H, yb_ + 0.01 * H, R, cx, cz, off=0.05, cols=3)
    else:
        for deg in range(0, 360, 40):
            c.decal_rev("soot", math.radians(deg), 0.5 * R, y0 + 0.02 * H, y0 + 0.42 * H, R, cx, cz, off=0.03)

    # ---- catwalk and ladder
    lad = p.get("ladder_deg")
    lth = math.radians(lad) if lad is not None else None
    if p.get("catwalk") and state != "destroyed":
        cwy, cwr = p["catwalk"]
        arcs = [(0, TAU)] if state == "intact" else [(thc + math.radians(34) , thc - math.radians(34) + TAU)]
        for a0, a1 in arcs:
            n = int((a1 - a0) / TAU * SEG) + 1
            th = np.linspace(a0, a1, n + 1)
            inn = np.stack([cx + (R + 0.12) * np.cos(th), np.full(n + 1, cwy), cz + (R + 0.12) * np.sin(th)], 1)
            out = np.stack([cx + cwr * np.cos(th), np.full(n + 1, cwy), cz + cwr * np.sin(th)], 1)
            P = np.vstack([inn, out])
            idx = [(i, i + 1, n + 1 + i) for i in range(n)] + [(i + 1, n + 2 + i, n + 1 + i) for i in range(n)]
            b.add("grate", P, np.tile((0, 1, 0), (len(P), 1)), P[:, [0, 2]] * 1.0, idx)
            b.revolve("galv", [(cwr, cwy - 0.12), (cwr, cwy + 0.12)], SEG, cx=cx, cz=cz, th0=a0, th1=a1, uref=uref(cwr, 1.5))
            for hh, rt in ((1.1, 0.034), (0.55, 0.026)):
                b.sweep("steel", [(cx + cwr * math.cos(t), cwy + hh, cz + cwr * math.sin(t)) for t in th], rt, 8, caps=True)
            npost = max(8, int((a1 - a0) / TAU * cwr * 4.5 * (1 if fine else 0.5)))
            for k in range(npost + 1):
                t = a0 + (a1 - a0) * k / npost
                if lth is not None and state == "intact" and abs((t - lth + math.pi) % TAU - math.pi) < 0.1:
                    continue
                q = np.array([cx + cwr * math.cos(t), cwy, cz + cwr * math.sin(t)])
                b.tube("steel", q, q + (0, 1.1, 0), 0.03, 6)
            for k in range(int(cwr * 1.4) if fine else int(cwr * 0.7)):
                t = a0 + (a1 - a0) * (k + 0.5) / (cwr * 1.4 if fine else cwr * 0.7)
                rh = np.array([math.cos(t), 0, math.sin(t)])
                b.tube("steel", np.array([cx, cwy - 0.85, cz]) + rh * R, np.array([cx, cwy - 0.1, cz]) + rh * (cwr - 0.1), 0.045, 6)
    if lth is not None and state != "destroyed":
        rh = np.array([math.cos(lth), 0, math.sin(lth)]); tg = np.array([-math.sin(lth), 0, math.cos(lth)])
        off = R + 0.2
        top = p.get("ladder_top", y1 + 0.6)
        if state == "damaged" and abs((lth - thc + math.pi) % TAU - math.pi) < 0.6:
            top = y0 + 0.55 * H
        yb = 0.4
        base = np.array([cx, 0, cz])
        for side in (-1, 1):
            q = base + rh * off + tg * 0.24 * side
            b.tube("steel", q + (0, yb, 0), q + (0, top, 0), 0.028, 8)
        rung = 0.3 if fine else 0.9
        for k in range(int((top - yb) / rung)):
            yy = yb + 0.25 + k * rung
            q = base + rh * off + (0, yy, 0)
            b.tube("steel", q - tg * 0.24, q + tg * 0.24, 0.02, 6, caps=False)
        for yy in (np.arange(1.2, top, 1.8) if fine else ()):
            q = base + rh * (R + 0.02) + (0, yy, 0)
            for side in (-1, 1):
                b.tube("steel", q + tg * 0.24 * side, q + tg * 0.24 * side + rh * 0.18, 0.025, 6)
        if state == "intact" and fine:
            for yy in np.arange(2.6, min(top, y1 - 0.1), 0.9):
                path = [base + rh * off + (0, yy, 0) + (math.cos(a) * rh + math.sin(a) * tg) * 0.46 for a in np.linspace(-1.9, 1.9, 14)]
                b.sweep("steel", path, 0.012, 6)

    # ---- lid, hatch, rail, tint on the dome
    lid = p["lid"]
    if state != "destroyed":
        lys = np.array([q[1] for q in lid]); lrs = np.array([q[0] for q in lid])
        order = np.argsort(lys)
        if state == "damaged":
            def roof_keep(th, y):
                u = ((np.asarray(th) - thc + math.pi) % TAU - math.pi) * R * 0.7
                yc = lys.min() + 0.35 * (lys.max() - lys.min())
                g = np.sqrt((u / (0.29 * R)) ** 2 + ((np.asarray(y) - yc) / max(0.08 * H, 0.3)) ** 2)
                return (g - (1 + 0.15 * np.sin(7 * np.arctan2(np.asarray(y) - yc, u)))) * 0.7
            ry = np.unique(np.r_[np.linspace(lys.min(), lys.max(), 14), np.linspace(lys.min() + 0.05, lys.min() + 0.5 * (lys.max() - lys.min()), 10)])
            b.cut_surface(p.get("lid_mat", "paint"), lambda ys: np.interp(ys, lys[order], lrs[order]), ry, 96 if fine else 48, roof_keep, cx=cx, cz=cz, uref=uref(R, 2.0),
                          disp=lambda th, y, k: np.clip(1 - k / 0.4, 0, 1) ** 2 * 0.1, thickness=0.07)
        else:
            b.revolve(p.get("lid_mat", "paint"), lid, SEG, cx=cx, cz=cz, uref=uref(R, 2.0))
        if p.get("hatch"):
            hr, hy, htop = p["hatch"]
            b.revolve("galv", [(hr, hy - 0.03), (hr, htop)], SEG, cx=cx, cz=cz, uref=uref(hr, 1.5))
            b.disc("trim", (cx, htop, cz), hr, seg=SEG, band=1, uvs=K)
            b.revolve("steel", [(hr * 0.32, htop), (hr * 0.32, htop + 0.22 * hr)], 24, cx=cx, cz=cz, uref=uref(hr * 0.32, 1.5))
            b.revolve("steel", [(hr * 0.32, htop + 0.22 * hr), (hr * 0.4, htop + 0.24 * hr), (hr * 0.2, htop + 0.34 * hr), (0, htop + 0.38 * hr)], 24, cx=cx, cz=cz, uref=uref(hr * 0.3, 1.5))
        if p.get("tint_dome"):
            r0, ya_, r1, yb_ = p["tint_dome"]
            r1 = r0 + 0.5 * (r1 - r0); yb_ = ya_ + 0.5 * (yb_ - ya_)  # a narrow ring: the dome reads calm from above
            rk = lambda th: (state == "damaged" and abs((th - thc + math.pi) % TAU - math.pi) < math.radians(40))
            b.revolve("trim", [(r0, ya_), (r1, yb_)], SEG, cx=cx, cz=cz, cull=(lambda th, y: rk(th)), band=6, uref=uref((r0 + r1) / 2, TT) * K, vscale=K, col=(1, 0, 0))
        if p.get("lid_rail"):
            rr, ry_ = p["lid_rail"]
            nposts = max(12, int(rr * 5.5 * (1 if fine else 0.5)))
            t0, t1 = (0.12, TAU) if state == "intact" else (thc + 0.6, thc - 0.6 + TAU)
            for hh, rt in ((1.0, 0.032), (0.5, 0.025)):
                b.sweep("steel", [(cx + rr * math.cos(t), ry_ + hh, cz + rr * math.sin(t)) for t in np.linspace(t0, t1, SEG)], rt, 8, caps=True)
            for k in range(nposts):
                t = t0 + (t1 - t0) * k / nposts
                q = np.array([cx + rr * math.cos(t), ry_ - 0.04, cz + rr * math.sin(t)])
                b.tube("steel", q, q + (0, 1.04, 0), 0.028, 6)

    # ---- the wreck
    if state == "destroyed":
        lyr = [(r, y) for r, y in lid if r > 0.3]
        for k in range(7):
            a0 = TAU * k / 7; half = TAU / 7
            tilt_ax = np.array([-math.sin(a0 + half / 2), 0, math.cos(a0 + half / 2)])
            Rt = axis_angle(tilt_ax, c.rng.uniform(-0.4, 0.9) * (1 if k % 2 else -1))
            off = np.array([0.0, c.rng.uniform(-0.72, -0.58) * H, 0.0]) + np.array([math.cos(a0 + half / 2), 0, math.sin(a0 + half / 2)]) * c.rng.uniform(-0.16, 0.12) * R
            ymid = lid[len(lid) // 2][1]
            cen = np.array([cx + 0.6 * R * math.cos(a0 + half / 2), ymid, cz + 0.6 * R * math.sin(a0 + half / 2)])
            b.M = (Rt, cen - Rt @ cen + off)
            b.revolve(p.get("lid_mat", "paint"), lyr, 6, cx=cx, cz=cz, th0=a0, th1=a0 + half * 0.92, uref=uref(R, 2.0))
            b.revolve("rust", [(r - 0.05, y - 0.06) for r, y in lyr], 6, cx=cx, cz=cz, th0=a0, th1=a0 + half * 0.92, flip=True, uref=uref(R, 2.0))
            b.M = None
        for k in range(max(8, int(R * 2))):
            a = TAU * (k + c.rng.random() * 0.6) / max(8, int(R * 2))
            hh = float(ridge(a))
            rh = np.array([math.cos(a), 0, math.sin(a)]); tg = np.array([-math.sin(a), 0, math.cos(a)])
            lean = c.rng.uniform(0.35, 1.2)
            n_ax = rh * math.cos(lean) + np.array([0, 1, 0]) * math.sin(lean)
            s_ax = -rh * math.sin(lean) + np.array([0, 1, 0]) * math.cos(lean)
            c3 = np.array([cx, hh - 0.02 * H, cz]) + rh * (R + 0.05) + s_ax * 0.07 * H
            Rm = np.stack([n_ax, s_ax, tg], 1)
            b.box("paint", c3, (0.05, 0.14 * H, c.rng.uniform(0.08, 0.16) * R), Rm)
            b.box("rust", c3 - n_ax * 0.03, (0.04, 0.142 * H, 0.09 * R), Rm)
        c.decal_ground("soot", (cx, cz), 2.5 * R, 2.5 * R, 0.0, y=0.045)
        c.decal_ground("oil", (cx + 0.4 * R, cz + 0.45 * R), R, R, 1.0, y=0.05)
        c.decal_ground("oil", (cx - 0.5 * R, cz - 0.4 * R), 0.9 * R, 0.9 * R, 2.0, y=0.052)
    elif state == "damaged":
        c.decal_ground("oil", (cx + 0.3 * R * math.cos(thc), cz + 1.1 * R * math.sin(thc)), 0.7 * R, 0.7 * R, 0.4, y=0.45)
        c.decal_ground("soot", (cx + 0.3 * R * math.cos(thc), cz + 0.8 * R * math.sin(thc)), 1.0 * R, 1.0 * R, 0.0, y=0.465)
    else:
        c.decal_ground("oil", (cx + 1.05 * R, cz), 0.35 * R, 0.35 * R, 0.6, y=0.135)


def lid_profile(R, y1, rise, steps=6, r_end=0.0, shape=1.0):
    """A shallow domed lid from (R, y1): rise metres up, ending at radius r_end."""
    pts = []
    for i in range(steps + 1):
        t = i / steps
        r = R + (r_end - R) * t
        y = y1 + rise * (1 - (1 - t) ** (2.0 * shape)) if shape else y1 + rise * t
        pts.append((r, y))
    return pts
