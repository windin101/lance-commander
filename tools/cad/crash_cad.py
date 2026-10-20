"""Helpers for the CAD rebuilds of the crashed-dropship wreck pieces (crashnose, crashrib, crashengine, crashtail,
crashwing): the originals are open, double-sided hull sheets whose torn edges are alpha cut-outs (material 1, the
burnt-edge texture), plus a few single-sided closed parts. The rebuild turns every planar patch of the original into
a real plate:

  * each patch is rasterised in its own plane at `res` (4 cm), every texel looks up the original's alpha through the
    triangle that covers it, and the opaque region's outline (cv2 contours, simplified to ~`eps`) becomes the plate's
    outline, so the torn edges are cut into the metal instead of painted on a flat card; holes larger than
    `min_hole` m2 stay holes (a profile picked by a point inside the metal), smaller ones are painted by the bake;
  * a patch with no cut-out keeps its exact loop, so neighbouring plates share edges (they weld and shade smoothly
    in the bake); only one whose triangles frame a hole is traced like a cut one (5 cm), so the opening stays open;
  * with all_double (used by every wreck) every face becomes a plate `thick` thick, extruded from the original surface
    toward its piece's centroid, so the outer face is the original's and plates meeting at a crease close it exactly;
    the originals pair many faces back to back (two single-sided faces, or a double-sided one over a single-sided
    one), and a patch whose vertex set was already built is skipped. (Without all_double, single-sided faces become
    one-sided surface patches.) Note: Godot's auto-LOD on the *original* .glb drops some of those paired panels at
    viewer distances (crashengine's oval hull panel over the machinery), so the original row of the comparison sheet
    shows less hull than the authored mesh has; generate_lods=false shows the panel.

Bodies are separate (they only touch); tools/art/cad_building.py bake drops the faces hidden inside a neighbour.
"""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "art"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cad_building import Original  # noqa: E402
from building_cad import cad, cad_dir  # noqa: E402
import aircraft_cad as A  # noqa: E402


def _seg_cross(p, q, r, s):
    d = (q[0] - p[0]) * (s[1] - r[1]) - (q[1] - p[1]) * (s[0] - r[0])
    if abs(d) < 1e-12:
        return False
    t = ((r[0] - p[0]) * (s[1] - r[1]) - (r[1] - p[1]) * (s[0] - r[0])) / d
    u = ((r[0] - p[0]) * (q[1] - p[1]) - (r[1] - p[1]) * (q[0] - p[0])) / d
    return 1e-6 < t < 1 - 1e-6 and 1e-6 < u < 1 - 1e-6


def simple(poly):
    n = len(poly)
    if n < 3:
        return False
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            if _seg_cross(poly[i], poly[(i + 1) % n], poly[j], poly[(j + 1) % n]):
                return False
    return True


def _simplify(cnt, res, eps):
    for e in (eps, eps * 1.5, eps * 2.2, eps * 3.3, eps * 5):
        ap = cv2.approxPolyDP(cnt, e / res, True).reshape(-1, 2).astype(float)
        if len(ap) >= 3 and simple([tuple(p) for p in ap]):
            return ap
    return None


class Wreck:
    def __init__(self, B, app, thick=0.08, res=0.04, eps=0.05, min_area=0.03, min_hole=0.12, flip_single=False, all_double=False):
        self.B, self.o = B, Original(app)
        self.thick, self.res, self.eps, self.min_area, self.min_hole = thick, res, eps, min_area, min_hole
        self.n = 0
        self.flip_single = flip_single
        self.seen = set()
        self.src = {}
        self.stats = {"plates": 0, "cut_plates": 0, "holes": 0, "verts": 0}
        o = self.o
        # connected component of every original triangle, and its centroid: plates are extruded toward it
        comps = A.components(app)
        cen = {}
        for c in comps:
            m = c.reshape(-1, 3).mean(0)
            for t in c:
                cen[tuple(np.round(t.mean(0), 4))] = m
        self.comp_c = np.array([cen.get(tuple(np.round(t.mean(0), 4)), o.tris.reshape(-1, 3).mean(0)) for t in o.tris])
        self.dbl = np.array([bool(o.gltf["materials"][m].get("doubleSided")) or all_double for m in o.mat])

    def alpha_at(self, k, uv):
        mi = self.o.mat[k]
        img = self.o.mat_image[mi]
        if img is None:
            return np.ones(len(uv))
        return self.o.sample_image(img, uv, bilinear=True)[:, 3]

    def build(self, select=None, skip=None):
        """Plates for the original triangles where select(tri_index) is true."""
        idx = np.arange(len(self.o.tris))
        if select is not None:
            idx = idx[[select(i) for i in idx]]
        tris = self.o.tris[idx]
        # group into planar patches, keeping the original triangle indices
        key = lambda p: tuple(np.round(p, 3))
        nrm = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
        area2 = np.linalg.norm(nrm, axis=1)
        good = area2 > 1e-6
        nrm[good] /= area2[good, None]
        left = set(np.where(good)[0].tolist())
        while left:
            i = left.pop()
            grp = [i]
            vk = {key(p) for p in tris[i]}
            changed = True
            while changed:
                changed = False
                for j in list(left):
                    if nrm[j] @ nrm[i] > 0.995 and abs((tris[j] - tris[i][0]) @ nrm[i]).max() < 0.02 and \
                            self.dbl[idx[j]] == self.dbl[idx[i]] and len({key(p) for p in tris[j]} & vk) >= 2:
                        grp.append(j)
                        vk |= {key(p) for p in tris[j]}
                        left.discard(j)
                        changed = True
            ks = [idx[g] for g in grp]
            sig = tuple(sorted({key(p) for k in ks for p in self.o.tris[k]}))
            if self.dbl[ks[0]] and sig in self.seen:  # the back of a plate already built (originals pair faces)
                continue
            self.seen.add(sig)
            self.patch(ks, nrm[i])
        return self

    def patch(self, ks, n):
        o, res = self.o, self.res
        self._ks = list(ks)
        self._cc = self.comp_c[ks].mean(0)
        self._pc = o.tris[ks].reshape(-1, 3).mean(0)
        T = o.tris[ks]
        org = T[0, 0]
        xd = T[0, 1] - T[0, 0]
        xd /= np.linalg.norm(xd)
        yd = np.cross(n, xd)
        P2 = np.stack([(T - org) @ xd, (T - org) @ yd], -1)       # (m, 3, 2)
        lo = P2.reshape(-1, 2).min(0) - 2 * res
        hi = P2.reshape(-1, 2).max(0) + 2 * res
        W, H = np.ceil((hi - lo) / res).astype(int) + 1
        gx, gy = np.meshgrid(lo[0] + (np.arange(W) + 0.5) * res, lo[1] + (np.arange(H) + 0.5) * res)
        pts = np.c_[gx.ravel(), gy.ravel()]
        alpha = np.zeros(len(pts))
        cover = np.zeros(len(pts), bool)
        for t, k in enumerate(ks):
            a, b, c = P2[t]
            v0, v1 = b - a, c - a
            den = v0[0] * v1[1] - v0[1] * v1[0]
            if abs(den) < 1e-12:
                continue
            d = pts - a
            u = (d[:, 0] * v1[1] - d[:, 1] * v1[0]) / den
            w = (v0[0] * d[:, 1] - v0[1] * d[:, 0]) / den
            ins = (u >= -1e-6) & (w >= -1e-6) & (u + w <= 1 + 1e-6) & ~cover
            if not ins.any():
                continue
            uv = o.uvs[k][0] * (1 - u[ins] - w[ins])[:, None] + o.uvs[k][1] * u[ins][:, None] + o.uvs[k][2] * w[ins][:, None]
            alpha[ins] = self.alpha_at(k, uv)
            cover |= ins
        cut = cover & (alpha < 0.5)
        dbl = bool(self.dbl[ks[0]])
        # a patch without cut-outs keeps straight edges (fine simplification), and keeps any hole its triangles
        # leave (a frame round an opening: the loop of its outer boundary alone would close the opening)
        eps = self.eps if cut.any() else min(self.eps, 0.05)
        if not cut.any():
            # exact loop, so neighbouring plates share their edges (they weld and shade smoothly in the bake), unless
            # the triangles frame a hole the loop would close
            cm = cover.reshape(H, W).astype(np.uint8)
            cs, hh = cv2.findContours(cm, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
            framed = hh is not None and any(h[3] != -1 and cv2.contourArea(c) * res * res >= self.min_hole
                                            for c, h in zip(cs, hh[0]))
            loops = [] if framed else A.patches(T)
            if loops and all(len(lp) >= 3 for _, lp in loops):
                for _, loop in loops:
                    pl = [[float((q - org) @ xd), float((q - org) @ yd)] for q in loop]
                    if simple([tuple(q) for q in pl]):
                        self.plate(org, xd, yd, n, pl, [], dbl, cutout=False)
                return
        mask = (cover & (alpha >= 0.5)).reshape(H, W).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
        cnts, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        if hier is None:
            return
        hier = hier[0]
        to_m = lambda q: [[float(lo[0] + (x + 0.5) * res), float(lo[1] + (y + 0.5) * res)] for x, y in q]
        for ci, cnt in enumerate(cnts):
            if hier[ci][3] != -1:
                continue
            if cv2.contourArea(cnt) * res * res < self.min_area:
                continue
            if 2 * cv2.contourArea(cnt) / max(cv2.arcLength(cnt, True), 1) * res < 0.06:
                continue  # a strip under ~6 cm wide (the edge of a cut-out): it reads as a stray bright line
            outer = _simplify(cnt, res, eps)
            if outer is None:
                continue
            holes = []
            ch = hier[ci][2]
            while ch != -1:
                if cv2.contourArea(cnts[ch]) * res * res >= self.min_hole:
                    hp = _simplify(cnts[ch], res, eps)
                    if hp is not None:
                        holes.append(hp)
                ch = hier[ch][0]
            # a point well inside the metal (outer minus kept holes), for the profile pick
            reg = np.zeros_like(mask)
            cv2.fillPoly(reg, [outer.astype(np.int32)], 1)
            for hp in holes:
                cv2.fillPoly(reg, [hp.astype(np.int32)], 0)
            dt = cv2.distanceTransform(reg, cv2.DIST_L2, 3)
            yy, xx = np.unravel_index(dt.argmax(), dt.shape)
            pick = to_m([(xx, yy)])[0] if holes else None
            self.plate(org, xd, yd, n, to_m(outer), [to_m(h) for h in holes], dbl, cutout=bool(cut.any()), pick=pick)

    def plate(self, org, xd, yd, n, outer, holes, dbl, cutout, pick=None):
        B = self.B
        self.n += 1
        nm = f"plate{self.n}"
        self.src[nm] = self._ks
        if not dbl and self.flip_single:
            yd = -yd
            outer = [[x, -y] for x, y in outer]
            holes = [[[x, -y] for x, y in h] for h in holes]
            pick = None if pick is None else [pick[0], -pick[1]]
        oC = np.array(cad(org))
        xC, yC = cad_dir(xd), cad_dir(yd)
        zC = np.cross(xC, yC)
        B.n_sk += 1
        sk = f"sk{B.n_sk}"
        B.c("sketch.create", plane={"origin": oC.round(2).tolist(), "x_dir": xC.round(6).tolist(),
                                    "y_dir": yC.round(6).tolist()}, name=sk)
        mm = lambda pl: [[round(x * 1000, 2), round(y * 1000, 2)] for x, y in pl]
        if not dbl:  # a surface patch faces by its loop's winding: counter-clockwise in (xd, yd) faces along n
            sa = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(outer, outer[1:] + outer[:1]))
            if sa < 0:
                outer = outer[::-1]
        B.c("sketch.line", points=mm(outer), closed=True)
        for h in holes:
            B.c("sketch.line", points=mm(h), closed=True)
        B.c("sketch.finish")
        prof = [{"point": [round(pick[0] * 1000, 2), round(pick[1] * 1000, 2)]}] if holes else None
        if dbl:
            # inward: the plate's outer face lies on the original surface, so plates meeting at a crease close it
            # exactly (no edge standing proud, no crack); the original sheet's two sides are one plate
            outward = float(np.asarray(n) @ (self._pc - self._cc)) >= 0
            p = {"distance": round(self.thick * 1000, 2), "sketch": sk, "body_name": nm, "operation": "new",
                 "direction": "negative" if outward else "positive"}
            if prof:
                p["profiles"] = prof
            B.c("solid.extrude", **p)
        else:
            # a single-sided face stays a one-sided sheet: the original relies on back-face culling (cut-away walls
            # that show the machinery behind them from outside), which a closed plate would block
            p = {"sketch": sk, "body_name": nm}
            if prof:
                p["profiles"] = prof
            B.c("surface.patch", **p)
        self.stats["plates"] += 1
        self.stats["cut_plates"] += cutout
        self.stats["holes"] += len(holes)
        self.stats["verts"] += len(outer) + sum(len(h) for h in holes)
        return nm
