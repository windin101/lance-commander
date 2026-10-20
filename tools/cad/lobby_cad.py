#!/usr/bin/env python3
"""CAD rebuild of the glass lobby (appearance lobby), in the original's frame.

    D=~/craft/solid/mc2/buildings/lobby
    python3 -I tools/art/cad_building.py openings lobby > $D/openings.json
    python3 -I tools/cad/lobby_cad.py > $D/lobby.json
    solidcraft-cli run $D/lobby.json --out $D/lobby.obj
    python3 -I tools/art/cad_building.py bake lobby $D/lobby.obj --max-res 4096

The original (66 triangles, double-sided panels) is a glass atrium: x -12.75..12.76, side profile (z, y)
(-4.2, 0) (12.61, 0) (12.61, 12) (2, 12) (-4.2, 6): a solid lower block (z 2..12.61, to 6 m) with a grass roof
garden at 6 m and a shop front on its atrium side, a glazed front wall (z -4.2, to 6 m), a glazed slope from
(z -4.2, 6 m) to (z 2, 12 m), a glazed roof at 12 m and glazed side walls; the 124 panes are alpha cut-outs, so
one sees the paving floor, the shop front and the garden through them. Rebuilt the same way, so it stays see-through:
every glazed panel is a 20 cm slab with each pane cut right through (the slab between the panes becomes real
mullions and transoms), the lower block solid, the floor a 10 cm paving slab, the rear wall solid with its
chevron panel a 15 cm recess with a hood and its small door and vent recessed.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402
from city_facade import Original  # noqa: E402

O = Original("lobby")
B = Builder()
OPEN = json.load(open(Path.home() / "craft/solid/mc2/buildings/lobby/openings.json"))["openings"]
X0, X1, ZF, ZM, ZB = -12.75, 12.76, -4.2, 2.0, 12.61
T = 0.2
SL = np.array([0.0, 0.72, -0.7]) / np.linalg.norm([0.0, 0.72, -0.7])  # the slope's outward normal

# side walls: the whole side profile as a slab, inside the original's outer plane
prof = [(ZF, 0.0), (ZB, 0.0), (ZB, 12.0), (ZM, 12.0), (ZF, 6.0)]
B.prism_x("side_px", prof, X1 - T, X1)
B.prism_x("side_mx", prof, X0, X0 + T)
XI0, XI1 = X0 + T, X1 - T
B.box("front", (XI0, 0.0, ZF), (XI1, 6.0, ZF + T))
d = -SL * T
B.prism_x("slope", [(ZF, 6.0), (ZM, 12.0), (ZM + d[2], 12.0 + d[1]), (ZF + d[2], 6.0 + d[1])], XI0, XI1)
B.box("roof", (XI0, 12.0 - T, ZM), (XI1, 12.0, ZB - 0.4))
B.box("rear", (XI0, 6.0, ZB - 0.4), (XI1, 12.0, ZB))  # thicker: the chevron recess must not break through
B.box("lower", (XI0, 0.0, ZM), (XI1, 6.0, ZB))
B.box("paving", (XI0, 0.0, ZF + T), (XI1, 0.1, ZM))


def host(o):
    """The slab an outward-facing pane belongs to (None for the inner faces of the double-sided panels)."""
    n, c = np.array(o["normal"]), np.array(o["center"])
    if abs(n[0]) > 0.9:
        return ("side_px" if c[0] > 0 else "side_mx") if n[0] * c[0] > 0 else None
    if n[1] > 0.9:
        return "roof"
    if np.dot(n, SL) > 0.99:
        return "slope"
    if n[2] < -0.9 and abs(c[2] - ZF) < 0.05:
        return "front"
    return None


k = 0
for o in OPEN:
    h = host(o)
    if h:
        B.recess(h, o, T + 0.15)
        k += 1
assert k == 62, k


# rear wall relief (outer face, z = 12.61): chevron panel, door, vent
def affine(i):
    return np.linalg.solve(np.c_[O.uvs[i], np.ones(3)], O.tris[i]).T


def rear_open(box, upper):
    i = next(i for i, n in enumerate(O.normal) if n[2] > 0.9 and abs(O.tris[i][0][2] - ZB) < 0.05
             and (O.tris[i][:, 1].mean() > 6.0) == upper)
    A = affine(i)
    P = np.array([A @ [u / 512, v / 512, 1] for u in (box[0], box[2]) for v in (box[1], box[3])])
    c = P.mean(0)
    c[2] = ZB
    return {"center": c.tolist(), "normal": [0.0, 0.0, 1.0], "t": [1.0, 0.0, 0.0], "b": [0.0, 1.0, 0.0],
            "w": float(np.ptp(P[:, 0])), "h": float(np.ptp(P[:, 1]))}


seen = []
for upper, box, depth in ((True, (241, 99, 391, 192), 0.15), (False, (297, 228, 312, 247), 0.15), (False, (319, 228, 345, 240), 0.1)):
    o = rear_open(box, upper)
    # the wall is mirrored about x = 0: the same texture box lands on both halves
    for sx in (1, -1):
        oo = dict(o, center=[o["center"][0] * sx, o["center"][1], ZB])
        tgt = "rear" if upper else "lower"
        B.recess(tgt, oo, depth)
        if upper:
            B.sill(f"hood{sx}", oo, proud=0.2, thick=0.1, overhang=0.12, top=True)
            B.sill(f"sill{sx}", oo, proud=0.14, thick=0.08, overhang=0.08)
print(B.dump())
