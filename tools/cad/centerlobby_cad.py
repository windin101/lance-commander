#!/usr/bin/env python3
"""CAD rebuild of the centre lobby (appearance centerlobby, node "connector"), in the original's frame.

    D=~/craft/solid/mc2/buildings/centerlobby
    python3 -I tools/art/cad_building.py openings centerlobby > $D/openings.json
    python3 -I tools/cad/centerlobby_cad.py > $D/centerlobby.json
    solidcraft-cli run $D/centerlobby.json --out $D/centerlobby.obj
    python3 -I tools/art/cad_building.py bake centerlobby $D/centerlobby.obj --max-res 4096

The original (58 triangles): two wings (x -12.77..-6.67 and 6.67..12.74, z -6..12.74) to 12 m with a hipped top to
a 14 m flat (inset 2 m on the three outer sides), a taller centre block between them (side profile (z, y): a
battered front from (-8, 0) to (-6.92, 12.38), a slope to (-4.38, 14.92), flat to z 10.74, a step down and a slope
to (12.74, 12)), and on the +z side a canted entrance porch (13.34 m wide at the block, 7.94 m at z 15.44, its
top sloping from 12 m to 10 m). Each surface keeps its own texture rectangle, mapped through each triangle's own
UV -> position affine.
Relief: the wings' -z windows (the cut-outs, openings.json) 15 cm recesses with sills, the +z chevron panels a
15 cm recess with a hood, the paired vents on the wing ends and +z faces recessed; on the centre's battered front
the three light pilaster panels 12 cm proud; on the centre roof the slotted plant box, the rack and the painted
pipes raised (pipes round, 20 sides); the porch door a 30 cm recess with a hood and a step.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402
from city_facade import Original, UP, ngon  # noqa: E402,F401

O = Original("centerlobby")
B = Builder()
RES = 512
OPEN = json.load(open(Path.home() / "craft/solid/mc2/buildings/centerlobby/openings.json"))["openings"]


def affine(i):
    return np.linalg.solve(np.c_[O.uvs[i], np.ones(3)], O.tris[i]).T


def tex_open(i, box):
    """Texture pixel box on triangle i's plane -> opening dict (center, normal, t, b, w, h)."""
    A = affine(i)
    n = np.array(O.normal[i], float)
    n /= np.linalg.norm(n)
    t = np.cross(UP, n) if abs(n[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
    t /= np.linalg.norm(t)
    b = np.cross(n, t)
    x0, y0, x1, y1 = (c / RES for c in box)
    P = np.array([A @ [u, v, 1] for u in (x0, x1) for v in (y0, y1)])
    c = P.mean(0)
    c = c - n * np.dot(c - O.tris[i][0], n)
    return {"center": c.tolist(), "normal": n.tolist(), "t": t.tolist(), "b": b.tolist(),
            "w": float(np.ptp(P @ t)), "h": float(np.ptp(P @ b))}


def tri(pred):
    return [i for i in range(len(O.tris)) if pred(np.array(O.normal[i]), O.tris[i].mean(0))]


def plate(name, o, thick):
    n, t, b = (np.array(o[k]) for k in ("normal", "t", "b"))
    return B.obox(name, np.array(o["center"]) + n * thick / 2, t, b, n, (o["w"], o["h"], thick))


# --- masses ----------------------------------------------------------------------------------------------------
WINGS = {"wm": (-12.77, -6.67), "wp": (6.67, 12.74)}
for nm, (a, b) in WINGS.items():
    B.box(nm, (a, 0.0, -6.0), (b, 12.0, 12.74))
    if nm == "wm":
        top = [(-10.77, -4.0), (-6.67, -4.0), (-6.67, 10.74), (-10.77, 10.74)]
    else:
        top = [(6.67, -4.0), (10.74, -4.0), (10.74, 10.74), (6.67, 10.74)]
    B.loft_y(f"{nm}hip", [(a, -6.0), (b, -6.0), (b, 12.74), (a, 12.74)], 12.0, top, 14.0)
B.prism_x("centre", [(-8.0, 0.0), (12.74, 0.0), (12.74, 12.0), (10.74, 14.0), (10.74, 14.92), (-4.38, 14.92), (-6.92, 12.38)], -6.67, 6.67)
B.prism_y("porch", [(-6.67, 12.74), (6.67, 12.74), (3.97, 15.44), (-3.97, 15.44)], 0.0, 12.2)
B.prism_x("porchtop", [(12.6, 0.0), (15.6, 0.0), (15.6, 9.88), (12.6, 12.12)], -7.0, 7.0)  # top slope 10 m -> 12 m
B.c("solid.combine", target="porch", tools=["porchtop"], operation="intersect")

# wings: windows (cut-outs), chevron panels, vents
for k, o in enumerate(OPEN):
    host = "wm" if o["center"][0] < 0 else "wp"
    B.recess(host, o, 0.15)
    B.sill(f"wsill{k}", o, proud=0.09, thick=0.07, overhang=0.05)
seen = []
for k, i in enumerate(tri(lambda n, c: n[2] > 0.9 and abs(c[0]) > 6.7 and c[1] < 12.1)):
    host = "wm" if O.tris[i].mean(0)[0] < 0 else "wp"
    ch = tex_open(i, (338, 12, 402, 100))
    if any(np.allclose(ch["center"], c, atol=0.05) for c in seen):  # a quad's two triangles share one affine
        continue
    seen.append(ch["center"])
    B.recess(host, ch, 0.15)
    B.sill(f"chood{k}", ch, proud=0.16, thick=0.08, overhang=0.1, top=True)
    for j, box in enumerate(((351, 128, 371, 152), (374, 128, 395, 152))):
        B.recess(host, tex_open(i, box), 0.1)
VENTS = ((131, 129, 149, 152), (152, 129, 170, 152), (261, 61, 280, 85), (282, 61, 302, 85))
seen = []
for i in tri(lambda n, c: abs(n[0]) > 0.9 and abs(c[0]) > 12.0):
    for box in VENTS:
        o = tex_open(i, box)
        if any(np.allclose(o["center"], c, atol=0.05) for c in seen):
            continue
        seen.append(o["center"])
        B.recess("wm" if o["center"][0] < 0 else "wp", o, 0.1)

# centre: pilaster panels on the battered front
i = tri(lambda n, c: n[2] < -0.9 and n[1] > 0.05)[0]
for j, box in enumerate(((281, 199, 306, 349), (322, 199, 370, 349), (385, 199, 411, 349))):
    plate(f"pil{j}", tex_open(i, box), 0.12)

# centre roof plant (14.92 m)
H = 14.92
r = tri(lambda n, c: n[1] > 0.9 and c[1] > 14.9)[0]


def roof_box(name, box, h):
    o = tex_open(r, box)
    c = np.array(o["center"])
    hw, hd = o["w"] / 2, o["h"] / 2
    B.box(f"{name}@avg", (c[0] - hw, H, c[2] - hd), (c[0] + hw, H + h, c[2] + hd))
    B.box(f"{name}cap", (c[0] - hw - 0.04, H + h, c[2] - hd - 0.04), (c[0] + hw + 0.04, H + h + 0.08, c[2] + hd + 0.04))


roof_box("plantbox", (176, 183, 232, 227), 0.8)
roof_box("rack", (145, 315, 237, 333), 0.35)


def roof_pt(u, v):
    p = affine(r) @ [u / RES, v / RES, 1]
    return p[0], p[2]


PR = 0.1
for k, (a, b) in enumerate((((125, 190), (125, 318)), ((147, 190), (147, 248)), ((163, 190), (163, 248)),
                            ((147, 251), (226, 251)), ((215, 228), (215, 251)))):
    (ax, az), (bx, bz) = roof_pt(*a), roof_pt(*b)
    yc = H + PR + 0.06
    if abs(ax - bx) > abs(az - bz):
        B.prism_x(f"pipe{k}", ngon(PR, 20, (az + bz) / 2, yc), min(ax, bx), max(ax, bx))
    else:
        B.prism_z(f"pipe{k}", ngon(PR, 20, (ax + bx) / 2, yc), min(az, bz), max(az, bz))

# porch: door, hood, step, plinth
i = tri(lambda n, c: n[2] > 0.9 and c[2] > 15.0)[0]
door = tex_open(i, (133, 393, 215, 505))
B.recess("porch", door, 0.3)
B.sill("doorhood", door, proud=0.5, thick=0.14, overhang=0.25, top=True)
n, t, c = np.array(door["normal"]), np.array(door["t"]), np.array(door["center"])
a, b = c + t * (door["w"] / 2 + 0.4), c - t * (door["w"] / 2 + 0.4) + n * 0.7
lo, hi = np.minimum(a, b), np.maximum(a, b)
B.box("doorstep@8f8b84", (lo[0], 0.0, lo[2]), (hi[0], 0.15, hi[2]))
print(B.dump())
