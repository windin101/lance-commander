#!/usr/bin/env python3
"""CAD rebuild of the prison cage (appearance prison), in the original's frame.

    D=~/craft/solid/mc2/buildings/prison
    python3 -I tools/art/cad_building.py openings prison > $D/openings.json
    python3 -I tools/cad/prison_cad.py > $D/prison.json
    solidcraft-cli run $D/prison.json --out $D/prison.obj
    python3 -I tools/art/cad_building.py bake prison $D/prison.obj --keep chainlinks

The original is a cage made entirely of one alpha-cut lattice texture (a 64 px diamond grid, 32 m to the texture,
so a strut lattice 2.83 m apart and about 0.7 m wide): node Prison (an inner two-floor cage x -1.2..7.6, z -7..7,
to 12.1 m, inside an outer cage x -4.5..11.1, z -10.6..10.6 with a sloped roof, battered side skins and a gate
annex at x -20), prisonwall2 (a low lattice wall around the yard, 1.9 m) and chainlinks (the fine chain-link fence
on top of it, 11 m to the texture). The cage is rebuilt as real steel: for every plane of Prison and prisonwall2,
each painted lattice line (u*W + v*H = 22.5 + 32k and u*W - v*H = 22 + 32k texture px, measured from the alpha
profile) is clipped to that plane's triangles and becomes a 0.6 x 0.3 m strut, and every boundary edge of the
plane a 0.5 x 0.32 m frame member; struts on one line in one plane are merged into one bar. The ground plane of
the inner cage (y 0.1) is left out. The chain-link fence stays an alpha card (bake --keep chainlinks): its wire
is 0.2 m apart and has no business being geometry.
"""
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "art"))
from building_cad import Builder  # noqa: E402
from cad_building import Original  # noqa: E402

O = Original("prison")
B = Builder()
W, H = O.images[0].shape[1], O.images[0].shape[0]
FAM = ((np.array([W, H], float), 22.5 * W / 256), (np.array([W, -H], float), 22.0 * W / 256))
PITCH = 32.0 * W / 256
SW, SD = 0.6, 0.3      # strut width in the plane, depth
FW, FD = 0.5, 0.32     # frame member

names = {i: n.get("name") for i, n in enumerate(O.gltf["nodes"])}
planes = defaultdict(list)
for i in range(len(O.tris)):
    if names[O.node[i]] not in ("Prison", "prisonwall2"):
        continue
    n = O.normal[i].copy()
    nz = np.flatnonzero(np.abs(n) > 1e-3)[0]
    if n[nz] < 0:
        n = -n
    d = float(np.dot(n, O.tris[i][0]))
    planes[(tuple(np.round(n, 2)), round(d, 1))].append(i)


def ortho(n, u):
    u = u - n * np.dot(u, n)
    return u / np.linalg.norm(u)


k_bar = 0
for (nk, d), idx in sorted(planes.items()):
    n = np.array(nk, float)
    n /= np.linalg.norm(n)
    pts = O.tris[idx].reshape(-1, 3)
    if np.ptp(pts[:, 1]) < 1e-3 and pts[0, 1] < 0.2:
        continue  # the cage floor on the ground
    # boundary edges of the plane's triangles -> frame members
    cnt = defaultdict(int)
    for i in idx:
        for a, b in ((0, 1), (1, 2), (2, 0)):
            ka = tuple(np.round(O.tris[i][a], 2))
            kb = tuple(np.round(O.tris[i][b], 2))
            cnt[tuple(sorted((ka, kb)))] += 1
    for (pa, pb), c in cnt.items():
        if c != 1:
            continue
        pa, pb = np.array(pa), np.array(pb)
        L = np.linalg.norm(pb - pa)
        if L < 0.6:
            continue
        t = (pb - pa) / L
        b = np.cross(n, t)
        B.obox(f"frame{k_bar}", (pa + pb) / 2, t, b, n, (L + FW, FW, FD))
        k_bar += 1
    # lattice struts
    segs = defaultdict(list)
    for i in idx:
        M = np.c_[O.uvs[i], np.ones(3)]
        if abs(np.linalg.det(M)) < 1e-6:
            continue
        A = np.linalg.solve(M, O.tris[i]).T
        for f, (w, c0) in enumerate(FAM):
            s = O.uvs[i] @ w
            for k in range(int(np.floor((s.min() - c0) / PITCH)), int(np.ceil((s.max() - c0) / PITCH)) + 1):
                c = c0 + k * PITCH
                hits = []
                for a, bb in ((0, 1), (1, 2), (2, 0)):
                    fa, fb = s[a] - c, s[bb] - c
                    if (fa < 0) != (fb < 0):
                        r = fa / (fa - fb)
                        hits.append(O.tris[i][a] + r * (O.tris[i][bb] - O.tris[i][a]))  # not via A: slivers
                if len(hits) == 2 and np.linalg.norm(hits[1] - hits[0]) > 0.05:
                    # key on the world line too: triangles of one plane can map the texture differently
                    dv = (hits[1] - hits[0]) / np.linalg.norm(hits[1] - hits[0])
                    dv = dv if dv[np.argmax(np.abs(dv))] > 0 else -dv
                    q = float(np.dot(hits[0], np.cross(n, dv)))
                    segs[(f, k, tuple(np.round(dv, 1)), round(q, 1))].append((hits[0], hits[1]))
    for key, ss in segs.items():
        dvec = ss[0][1] - ss[0][0]
        dvec /= np.linalg.norm(dvec)
        o = ss[0][0]
        iv = sorted(sorted((float(np.dot(p - o, dvec)), float(np.dot(q - o, dvec)))) for p, q in ss)
        merged = []
        for a, b in iv:
            if merged and a <= merged[-1][1] + 0.05:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        for a, b in merged:
            if b - a < 1.0:
                continue
            bvec = np.cross(n, dvec)
            B.obox(f"strut{k_bar}", o + dvec * (a + b) / 2, dvec, bvec, n, (b - a, SW, SD))
            k_bar += 1
print(B.dump())
print(k_bar, "bars", file=sys.stderr)
