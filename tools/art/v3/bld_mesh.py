#!/usr/bin/env python3
"""Procedural hard-surface mesh builder for v3 buildings (LANCE-21): true round parts, metre UVs, glTF out.

Frame is the original objects' glTF frame (metres, Y up, ground y = 0). Every surface is one material name; the
loader (game/scripts/world/building_v3.gd) maps the glTF material "bv3_<name>" to the shared library:
  UV0     metres on the surface (tile size is the material's, in shared/buildings/materials.json); trim: metres, UV1.x = band
  UV1     trim band index (x), 0 elsewhere; decals: UV0 is the atlas
  COLOR_0 R faction-tint mask, G extra wear/grime bias, B scorch (burn) amount, A 1
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hd_rig as R  # noqa: E402  (GlbWriter)

TAU = math.tau


def unit(v):
    v = np.asarray(v, float)
    return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-12)


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


class Builder:
    def __init__(self):
        self.s = {}  # material -> dict of lists
        self.seg_cap = 0    # >0: cap tube/sweep segments (distant LOD)
        self.M = None       # (3x3, offset): rigid transform applied to everything added (wreckage poses)
        self.colfn = None   # f(P (n,3)) -> burn amount (n,), merged into COLOR_0.b (never on decals)
        self.wearfn = None  # f(P, N) -> run-off / grime (n,) merged into COLOR_0.g
        self.aofn = None    # f(P, N) -> baked ambient occlusion (n,), 1 = open, COLOR_0.a

    def _surf(self, mat):
        return self.s.setdefault(mat, {"P": [], "N": [], "U": [], "U2": [], "C": [], "I": [], "n": 0})

    def add(self, mat, P, N, U, I, band=0, col=(0, 0, 0)):
        """P (n,3), N (n,3), U (n,2), I (m,3) triangle indices. Winding is fixed against the normals."""
        s = self._surf(mat)
        P = np.asarray(P, float); N = unit(N); I = np.asarray(I, int).reshape(-1, 3)
        gn = np.cross(P[I[:, 1]] - P[I[:, 0]], P[I[:, 2]] - P[I[:, 0]])
        flip = (gn * N[I].sum(1)).sum(1) < 0
        I = I.copy(); I[flip] = I[flip][:, [0, 2, 1]]
        I = I[np.linalg.norm(gn, axis=1) > 1e-12]
        if self.M is not None:
            P = P @ self.M[0].T + self.M[1]
            N = unit(N @ self.M[0].T)
        n = len(P)
        c = np.zeros((n, 4)); c[:, 3] = 1.0
        cc = np.asarray(col, float)
        c[:, :3] = cc if cc.ndim == 2 else np.tile(cc, (n, 1))
        if mat != "decal":
            if self.colfn is not None:
                c[:, 2] = np.maximum(c[:, 2], self.colfn(P))
            if self.wearfn is not None:
                c[:, 1] = np.maximum(c[:, 1], self.wearfn(P, N))
            if self.aofn is not None:
                c[:, 3] = self.aofn(P, N)
        b2 = np.zeros((n, 2)); b2[:, 0] = band
        s["P"].append(P); s["N"].append(N); s["U"].append(np.asarray(U, float))
        s["U2"].append(b2); s["C"].append(c); s["I"].append(I + s["n"]); s["n"] += n

    # ------------------------------------------------------------------ surfaces of revolution
    def revolve(self, mat, prof, seg=72, cx=0.0, cz=0.0, th0=0.0, th1=TAU, cull=None, flip=False, band=0, col=(0, 0, 0),
                uref=None, vscale=1.0, voff=0.0):
        """prof: [(r, y), ...] one smooth polyline (split sharp corners into separate calls). u = angle * uref metres
        (uref defaults to the profile's largest radius), v = arc length along the profile. cull(theta, y)->True drops a quad."""
        prof = np.asarray(prof, float)
        n = len(prof)
        d = np.diff(prof, axis=0)
        seglen = np.linalg.norm(d, axis=1)
        s = np.r_[0, np.cumsum(seglen)]
        # profile normals (outward = (dy, -dr) rotated): for a profile going up with r growing outward -> (dy,-dr)/|.|
        tn = np.stack([d[:, 1], -d[:, 0]], 1) / (seglen[:, None] + 1e-12)
        vn = np.zeros((n, 2)); vn[:-1] += tn; vn[1:] += tn
        vn /= np.linalg.norm(vn, axis=1, keepdims=True) + 1e-12
        if flip:
            vn = -vn
        uref = uref if uref is not None else float(prof[:, 0].max())
        cols = seg + 1
        th = th0 + (th1 - th0) * np.arange(cols) / seg
        P = np.zeros((n, cols, 3)); N = np.zeros((n, cols, 3)); U = np.zeros((n, cols, 2))
        for k, t in enumerate(th):
            c, sn = math.cos(t), math.sin(t)
            P[:, k] = np.stack([cx + prof[:, 0] * c, prof[:, 1], cz + prof[:, 0] * sn], 1)
            N[:, k] = np.stack([vn[:, 0] * c, vn[:, 1], vn[:, 0] * sn], 1)
            U[:, k, 0] = t * uref
            U[:, k, 1] = (s + voff) * vscale
        idx = []
        for i in range(n - 1):
            for k in range(seg):
                if cull is not None:
                    tm = th[k] + (th[1] - th[0]) * 0.5
                    if cull(tm, 0.5 * (prof[i, 1] + prof[i + 1, 1])):
                        continue
                a = i * cols + k; b = a + 1; c2 = a + cols; d2 = c2 + 1
                idx += [(a, b, c2), (b, d2, c2)]
        if idx:
            self.add(mat, P.reshape(-1, 3), N.reshape(-1, 3), U.reshape(-1, 2), idx, band, col)

    def cut_surface(self, mat, rfun, ys, nth, keep, cx=0.0, cz=0.0, th0=0.0, th1=TAU, disp=None, flip=False, uref=1.0,
                    band=0, col=(0, 0, 0), vscale=1.0, voff=0.0, thickness=0.0, edge_mat="rust"):
        """A surface of revolution r = rfun(y) over the rows ys, clipped exactly along keep(theta, y) = 0 (keep > 0 stays).
        keep is a vectorised signed distance-ish field in metres, so the cut is a smooth contour, not a stair of cells.
        disp(theta, y, keep) adds a radial offset (curled edges). thickness > 0 adds the cut edge as a strip of that depth."""
        ys = np.asarray(ys, float)
        th = th0 + (th1 - th0) * np.arange(nth + 1) / nth
        TH, YY = np.meshgrid(th, ys)
        K = keep(TH, YY)
        tris = []   # param-space triangles ((th,y) x3)
        segs = []
        for i in range(len(ys) - 1):
            for j in range(nth):
                c = [(j, i), (j + 1, i), (j + 1, i + 1), (j, i + 1)]
                kv = [K[a, b] for b, a in c] if False else [K[i, j], K[i, j + 1], K[i + 1, j + 1], K[i + 1, j]]
                if min(kv) >= 0:
                    p = [(th[j], ys[i]), (th[j + 1], ys[i]), (th[j + 1], ys[i + 1]), (th[j], ys[i + 1])]
                    tris += [(p[0], p[1], p[2]), (p[0], p[2], p[3])]
                    continue
                if max(kv) <= 0:
                    continue
                pts = [(th[j], ys[i]), (th[j + 1], ys[i]), (th[j + 1], ys[i + 1]), (th[j], ys[i + 1])]
                poly = []; cut = []
                for a in range(4):
                    b2 = (a + 1) % 4
                    if kv[a] >= 0:
                        poly.append(pts[a])
                    if (kv[a] >= 0) != (kv[b2] >= 0):
                        t = kv[a] / (kv[a] - kv[b2])
                        q = (pts[a][0] + (pts[b2][0] - pts[a][0]) * t, pts[a][1] + (pts[b2][1] - pts[a][1]) * t)
                        poly.append(q); cut.append(q)
                for k in range(1, len(poly) - 1):
                    tris.append((poly[0], poly[k], poly[k + 1]))
                if len(cut) >= 2:
                    segs.append((cut[0], cut[1]))
        if not tris:
            return
        T = np.array(tris, float)  # (m,3,2)
        def pos(t, y, rr=0.0):
            r = np.interp(y, ys, rfun(ys)) + rr
            if disp is not None:
                r = r + disp(t, y, keep(t, y))
            return np.stack([cx + r * np.cos(t), y, cz + r * np.sin(t)], -1)
        P = pos(T[..., 0], T[..., 1])
        e = 1e-3
        dt = pos(T[..., 0] + e, T[..., 1]) - pos(T[..., 0] - e, T[..., 1])
        dy = pos(T[..., 0], T[..., 1] + e) - pos(T[..., 0], T[..., 1] - e)
        N = np.cross(dt, dy)
        rad = np.stack([np.cos(T[..., 0]), np.zeros_like(T[..., 0]), np.sin(T[..., 0])], -1)
        sgn = np.sign((N * rad).sum(-1, keepdims=True)); sgn[sgn == 0] = 1
        N = N * sgn * (-1 if flip else 1)
        U = np.stack([T[..., 0] * uref, (T[..., 1] - ys[0]) * vscale + voff], -1)
        m = len(T)
        self.add(mat, P.reshape(-1, 3), N.reshape(-1, 3), U.reshape(-1, 2), np.arange(m * 3).reshape(m, 3), band, col)
        if thickness > 0 and segs:
            S = np.array(segs, float)  # (k,2,2)
            a, b = S[:, 0], S[:, 1]
            mid = (a + b) / 2
            def grad(t, y):
                g_t = (keep(t + 1e-3, y) - keep(t - 1e-3, y)) / 2e-3
                g_y = (keep(t, y + 1e-3) - keep(t, y - 1e-3)) / 2e-3
                r = np.interp(y, ys, rfun(ys))
                tg = np.stack([-np.sin(t), np.zeros_like(t), np.cos(t)], -1)
                return -(g_t / r)[:, None] * tg - g_y[:, None] * np.array([0, 1.0, 0])  # toward the hole
            n_edge = grad(mid[:, 0], mid[:, 1])
            sgnf = -1.0 if flip else 1.0
            oa, ob = pos(a[:, 0], a[:, 1]), pos(b[:, 0], b[:, 1])
            ia, ib = pos(a[:, 0], a[:, 1], -thickness), pos(b[:, 0], b[:, 1], -thickness)
            Pq = np.stack([oa, ob, ib, ia], 1)  # (k,4,3)
            Nq = np.repeat(n_edge[:, None, :], 4, 1)
            L = np.linalg.norm(ob - oa, axis=1)
            Uq = np.stack([np.zeros_like(L), L, L, np.zeros_like(L)], 1)
            Uq = np.stack([Uq, np.stack([np.zeros_like(L), np.zeros_like(L), np.full_like(L, thickness), np.full_like(L, thickness)], 1)], -1)
            kq = len(Pq)
            idx = np.array([(0, 1, 2), (0, 2, 3)])[None] + (np.arange(kq) * 4)[:, None, None]
            self.add(edge_mat, Pq.reshape(-1, 3), Nq.reshape(-1, 3), Uq.reshape(-1, 2), idx.reshape(-1, 3))

    def cut_param(self, mat, pos, us, vs, keep, uv=None, flip=False, band=0, col=(0, 0, 0), thickness=0.0, edge_mat="rust", disp=None):
        """Generic clipped grid: pos(u, v) -> (...,3) over the grid us x vs, clipped exactly along keep(u, v) = 0 (keep > 0 stays),
        used for planar walls and roofs. uv(u, v) -> (...,2) (default metres u, v). Edge strip of `thickness` along -normal."""
        us = np.asarray(us, float); vs = np.asarray(vs, float)
        U, V = np.meshgrid(us, vs)
        Kv = keep(U, V) if keep is not None else np.ones_like(U)
        tris, segs = [], []
        for i in range(len(vs) - 1):
            for j in range(len(us) - 1):
                kv = [Kv[i, j], Kv[i, j + 1], Kv[i + 1, j + 1], Kv[i + 1, j]]
                pts = [(us[j], vs[i]), (us[j + 1], vs[i]), (us[j + 1], vs[i + 1]), (us[j], vs[i + 1])]
                if min(kv) >= 0:
                    tris += [(pts[0], pts[1], pts[2]), (pts[0], pts[2], pts[3])]
                    continue
                if max(kv) <= 0:
                    continue
                poly = []; cut = []
                for a in range(4):
                    b2 = (a + 1) % 4
                    if kv[a] >= 0:
                        poly.append(pts[a])
                    if (kv[a] >= 0) != (kv[b2] >= 0):
                        t = kv[a] / (kv[a] - kv[b2])
                        q = (pts[a][0] + (pts[b2][0] - pts[a][0]) * t, pts[a][1] + (pts[b2][1] - pts[a][1]) * t)
                        poly.append(q); cut.append(q)
                for k in range(1, len(poly) - 1):
                    tris.append((poly[0], poly[k], poly[k + 1]))
                if len(cut) >= 2:
                    segs.append((cut[0], cut[1]))
        if not tris:
            return
        T = np.array(tris, float)
        e = 1e-3
        def n0(u, v):
            du = pos(u + e, v) - pos(u - e, v); dv = pos(u, v + e) - pos(u, v - e)
            n = np.cross(du, dv)
            return n / (np.linalg.norm(n, axis=-1, keepdims=True) + 1e-12)
        def posd(u, v):
            p = pos(u, v)
            if disp is not None:
                u = np.asarray(u, float); v = np.asarray(v, float)
                kk = keep(u, v) if keep is not None else np.ones_like(u)
                p = p + np.asarray(disp(u, v, kk))[..., None] * n0(u, v)
            return p
        def nrm(u, v):
            du = posd(u + e, v) - posd(u - e, v); dv = posd(u, v + e) - posd(u, v - e)
            n = np.cross(du, dv)
            n = n / (np.linalg.norm(n, axis=-1, keepdims=True) + 1e-12)
            return -n if flip else n
        def P_(u, v, off=0.0):
            return posd(u, v) + off * nrm(u, v)
        Pp = P_(T[..., 0], T[..., 1]); Nn = nrm(T[..., 0], T[..., 1])
        Uv = uv(T[..., 0], T[..., 1]) if uv is not None else T
        m = len(T)
        self.add(mat, Pp.reshape(-1, 3), Nn.reshape(-1, 3), np.asarray(Uv).reshape(-1, 2), np.arange(m * 3).reshape(m, 3), band, col)
        if thickness > 0 and segs:
            S = np.array(segs, float); a, b = S[:, 0], S[:, 1]
            oa, ob = P_(a[:, 0], a[:, 1]), P_(b[:, 0], b[:, 1])
            na = nrm(a[:, 0], a[:, 1])
            ia, ib = oa - na * thickness, ob - na * thickness
            mid = (a + b) / 2
            gu = (keep(mid[:, 0] + 1e-3, mid[:, 1]) - keep(mid[:, 0] - 1e-3, mid[:, 1])) / 2e-3
            gv = (keep(mid[:, 0], mid[:, 1] + 1e-3) - keep(mid[:, 0], mid[:, 1] - 1e-3)) / 2e-3
            du = pos(mid[:, 0] + e, mid[:, 1]) - pos(mid[:, 0] - e, mid[:, 1]); dv = pos(mid[:, 0], mid[:, 1] + e) - pos(mid[:, 0], mid[:, 1] - e)
            du = du / (np.linalg.norm(du, axis=1, keepdims=True) + 1e-12); dv = dv / (np.linalg.norm(dv, axis=1, keepdims=True) + 1e-12)
            n_edge = -(gu[:, None] * du + gv[:, None] * dv)
            Pq = np.stack([oa, ob, ib, ia], 1)
            L = np.linalg.norm(ob - oa, axis=1)
            Uq = np.stack([np.stack([np.zeros_like(L), L, L, np.zeros_like(L)], 1), np.stack([np.zeros_like(L), np.zeros_like(L), np.full_like(L, thickness), np.full_like(L, thickness)], 1)], -1)
            kq = len(Pq)
            idx = np.array([(0, 1, 2), (0, 2, 3)])[None] + (np.arange(kq) * 4)[:, None, None]
            self.add(edge_mat, Pq.reshape(-1, 3), np.repeat(n_edge[:, None, :], 4, 1).reshape(-1, 3), Uq.reshape(-1, 2), idx.reshape(-1, 3))

    def disc(self, mat, c, r, normal=(0, 1, 0), seg=48, col=(0, 0, 0), r_in=0.0, band=0, uvs=1.0):
        """Flat disc or annulus; UV planar in metres."""
        nrm = unit(normal)
        a = np.array([1.0, 0, 0]) if abs(nrm[0]) < 0.9 else np.array([0, 0, 1.0])
        t = unit(np.cross(nrm, a)); b = np.cross(nrm, t)
        th = TAU * np.arange(seg) / seg
        ring = lambda rr: np.asarray(c) + rr * (np.outer(np.cos(th), t) + np.outer(np.sin(th), b))
        if r_in > 0:
            P = np.vstack([ring(r), ring(r_in)])
            idx = []
            for k in range(seg):
                k2 = (k + 1) % seg
                idx += [(k, k2, seg + k), (k2, seg + k2, seg + k)]
        else:
            P = np.vstack([ring(r), np.asarray(c)[None]])
            idx = [(k, (k + 1) % seg, seg) for k in range(seg)]
        N = np.tile(nrm, (len(P), 1))
        rel = P - np.asarray(c)
        U = np.stack([rel @ t, rel @ b], 1) * uvs
        self.add(mat, P, N, U, idx, band, col)

    # ------------------------------------------------------------------ tubes and sweeps
    def sweep(self, mat, path, r, seg=10, closed=False, caps=True, col=(0, 0, 0), band=0):
        """A circle of radius r swept along a polyline (parallel transport); u around, v along (metres)."""
        path = np.asarray(path, float)
        if self.seg_cap:
            seg = min(seg, self.seg_cap)
            if len(path) > 24:
                path = path[:: 2]
        m = len(path)
        tan = np.zeros((m, 3))
        for i in range(m):
            a = path[(i + 1) % m] if (closed or i < m - 1) else path[i]
            b = path[i - 1] if (closed or i > 0) else path[i]
            tan[i] = a - b
        tan = unit(tan)
        ref = np.array([0, 1.0, 0]) if abs(tan[0][1]) < 0.9 else np.array([1.0, 0, 0])
        nrm = unit(np.cross(np.cross(tan[0], ref), tan[0]))
        P = np.zeros((m, seg + 1, 3)); N = np.zeros_like(P); U = np.zeros((m, seg + 1, 2))
        acc = 0.0
        for i in range(m):
            if i > 0:
                acc += np.linalg.norm(path[i] - path[i - 1])
                nrm = nrm - tan[i] * (nrm @ tan[i])
                nrm = unit(nrm)
            bin_ = np.cross(tan[i], nrm)
            for k in range(seg + 1):
                a = TAU * k / seg
                dirv = math.cos(a) * nrm + math.sin(a) * bin_
                P[i, k] = path[i] + r * dirv; N[i, k] = dirv
                U[i, k] = (a * r, acc)
        idx = []
        for i in range(m - 1 + (1 if closed else 0)):
            i2 = (i + 1) % m
            for k in range(seg):
                a = i * (seg + 1) + k; b = a + 1; c2 = i2 * (seg + 1) + k; d2 = c2 + 1
                idx += [(a, b, c2), (b, d2, c2)]
        self.add(mat, P.reshape(-1, 3), N.reshape(-1, 3), U.reshape(-1, 2), idx, band, col)
        if caps and not closed:
            for end, sgn in ((0, -1), (m - 1, 1)):
                self.disc(mat, path[end], r, tan[end] * sgn, seg=seg, col=col)

    def tube(self, mat, p0, p1, r, seg=12, caps=True, col=(0, 0, 0)):
        self.sweep(mat, [p0, p1], r, seg, caps=caps, col=col)

    def arc_path(self, y, R_, th0, th1, n, cx=0.0, cz=0.0):
        return [(cx + R_ * math.cos(th0 + (th1 - th0) * i / n), y, cz + R_ * math.sin(th0 + (th1 - th0) * i / n)) for i in range(n + 1)]

    # ------------------------------------------------------------------ boxes
    def box(self, mat, c, size, rot=None, col=(0, 0, 0), band=0, uvs=1.0, skip=()):
        """Axis-aligned unless rot (3x3) is given. Flat faces, UV planar metres. skip: face names to leave out (+x -x +y -y +z -z)."""
        c = np.asarray(c, float); h = np.asarray(size, float) / 2
        rot = np.eye(3) if rot is None else np.asarray(rot)
        faces = {"+x": (0, 1, 2, +1), "-x": (0, 1, 2, -1), "+y": (1, 2, 0, +1), "-y": (1, 2, 0, -1), "+z": (2, 0, 1, +1), "-z": (2, 0, 1, -1)}
        for nm, (ax, ua, va, sg) in faces.items():
            if nm in skip:
                continue
            n = np.zeros(3); n[ax] = sg
            # corners in the face plane
            cs = []
            for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                p = np.zeros(3); p[ax] = sg * h[ax]; p[ua] = su * h[ua]; p[va] = sv * h[va]
                cs.append(p)
            cs = np.array(cs)
            U = np.stack([cs[:, ua], cs[:, va]], 1) * uvs
            P = c + cs @ rot.T
            N = np.tile(rot @ n, (4, 1))
            self.add(mat, P, N, U, [(0, 1, 2), (0, 2, 3)], band, col)

    def quad(self, mat, p, u_ax, v_ax, w, h, uv, normal=None, col=(0, 0, 0), band=0):
        """A flat quad centred on p spanned by unit axes u_ax, v_ax, w x h metres, uv = (u0, v0, u1, v1)."""
        u_ax, v_ax = unit(u_ax), unit(v_ax)
        n = unit(np.cross(u_ax, v_ax)) if normal is None else unit(normal)
        P = np.array([p - u_ax * w / 2 - v_ax * h / 2, p + u_ax * w / 2 - v_ax * h / 2, p + u_ax * w / 2 + v_ax * h / 2, p - u_ax * w / 2 + v_ax * h / 2])
        u0, v0, u1, v1 = uv
        U = np.array([(u0, v1), (u1, v1), (u1, v0), (u0, v0)])
        self.add(mat, P, np.tile(n, (4, 1)), U, [(0, 1, 2), (0, 2, 3)], band, col)

    # ------------------------------------------------------------------ output
    def stats(self):
        return {k: int(sum(len(i) for i in v["I"])) for k, v in self.s.items()}

    @staticmethod
    def write_lods(path, name, builders):
        """One glTF with a node per detail level (lod0, lod1, ...) under one scene root; each node its own mesh."""
        g = {"asset": {"version": "2.0", "generator": "tools/art/v3/bld_mesh.py"}, "scenes": [{"nodes": [0]}], "scene": 0,
             "nodes": [{"name": name, "children": list(range(1, len(builders) + 1))}], "meshes": [], "materials": [],
             "buffers": [], "bufferViews": [], "accessors": []}
        w = R.GlbWriter(g, bytearray())
        stats = []
        for li, bd in enumerate(builders):
            prims = []
            for mat, v in bd.s.items():
                P = np.vstack(v["P"]).astype(np.float32); N = np.vstack(v["N"]).astype(np.float32)
                U = np.vstack(v["U"]).astype(np.float32); U2 = np.vstack(v["U2"]).astype(np.float32)
                C = np.vstack(v["C"]).astype(np.float32); I = np.vstack(v["I"]).astype(np.uint32)
                mi = next((k for k, m in enumerate(g["materials"]) if m["name"] == f"bv3_{mat}"), None)
                if mi is None:
                    g["materials"].append({"name": f"bv3_{mat}", "pbrMetallicRoughness": {"baseColorFactor": [0.6, 0.6, 0.6, 1], "metallicFactor": 0.0, "roughnessFactor": 0.8}, "doubleSided": mat in ("decal", "interior")})
                    mi = len(g["materials"]) - 1
                prims.append({"attributes": {
                    "POSITION": w.accessor(P, "VEC3", target=34962, minmax=True), "NORMAL": w.accessor(N, "VEC3", target=34962),
                    "TEXCOORD_0": w.accessor(U, "VEC2", target=34962), "TEXCOORD_1": w.accessor(U2, "VEC2", target=34962),
                    "COLOR_0": w.accessor(C, "VEC4", target=34962)},
                    "indices": w.accessor(I.reshape(-1), "SCALAR", comp=5125, target=34963), "material": mi})
            g["meshes"].append({"name": f"lod{li}", "primitives": prims})
            g["nodes"].append({"name": f"lod{li}", "mesh": li})
            stats.append(bd.stats())
        w.write(str(path))
        return stats

    def write(self, path, name):
        g = {"asset": {"version": "2.0", "generator": "tools/art/v3/bld_mesh.py"}, "scenes": [{"nodes": [0]}], "scene": 0,
             "nodes": [{"name": name, "mesh": 0}], "meshes": [{"name": name, "primitives": []}], "materials": [],
             "buffers": [], "bufferViews": [], "accessors": []}
        w = R.GlbWriter(g, bytearray())
        for mat, v in self.s.items():
            P = np.vstack(v["P"]).astype(np.float32); N = np.vstack(v["N"]).astype(np.float32)
            U = np.vstack(v["U"]).astype(np.float32); U2 = np.vstack(v["U2"]).astype(np.float32)
            C = np.vstack(v["C"]).astype(np.float32); I = np.vstack(v["I"]).astype(np.uint32)
            g["materials"].append({"name": f"bv3_{mat}", "pbrMetallicRoughness": {"baseColorFactor": [0.6, 0.6, 0.6, 1], "metallicFactor": 0.0, "roughnessFactor": 0.8}, "doubleSided": mat in ("decal", "interior")})
            g["meshes"][0]["primitives"].append({"attributes": {
                "POSITION": w.accessor(P, "VEC3", target=34962, minmax=True), "NORMAL": w.accessor(N, "VEC3", target=34962),
                "TEXCOORD_0": w.accessor(U, "VEC2", target=34962), "TEXCOORD_1": w.accessor(U2, "VEC2", target=34962),
                "COLOR_0": w.accessor(C, "VEC4", target=34962)},
                "indices": w.accessor(I.reshape(-1), "SCALAR", comp=5125, target=34963), "material": len(g["materials"]) - 1})
        w.write(str(path))
        return self.stats()
