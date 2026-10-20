#!/usr/bin/env python3
"""CAD rebuild of the second traffic-control complex (appearance trafcon2), in the original's frame.

    D=~/craft/solid/mc2/buildings/trafcon2
    python3 -I tools/art/cad_building.py openings trafcon2 > $D/openings.json
    python3 -I tools/art/cad_building.py decal trafcon2 0 0.283 0.748 0.426 0.873 > $D/decal_door.json
    python3 -I tools/art/cad_building.py decal trafcon2 0 0.439 0.805 0.488 0.873 > $D/decal_sdoor.json
    python3 -I tools/cad/trafcon2_cad.py $D > $D/trafcon2.json
    solidcraft-cli run $D/trafcon2.json --out $D/trafcon2.obj
    python3 -I tools/art/cad_building.py bake trafcon2 $D/trafcon2.obj --keep Spinny

Measured from game/assets/objects/trafcon2.glb (faces grouped by plane): a hall (z -4.86..12.14; section x -8.4..10.8
on the ground, chamfered 1.6 m at both feet, its -x side sloping in from 7.2 m at x -10 to 16 m at x -4.8); a
link block (x -7.76..10.4, z -28.86..-4.86, 7.2 m, both top edges chamfered to x -5.36 / 8.0) whose -x side
is an arcade under 3.6 m back to x -5.36 on three wedge piers, closed at z -27.66; a tower (x -1.63..7.85,
z -31.51..-22.34, to 21.11 m, its -z foot undercut to z -29.01); a stair housing on the link (x 1.2..4.4,
z -22.46..-12.86, sloping from 7.2 m to 17.2 m); the cab, a frustum flaring from the tower top to x -3.92..9.91,
z -33.57..-20.25 at 26.64 m under a pyramid roof (apex 28.06 m at x 2.8, z -26.77). The searchlight (Spinny) is
kept verbatim. Relief: every cut-out window a 25 cm recess with a sill (the cab's eight panes 30 cm), the hall's
roller door a 30 cm recess with a lintel and its side door a 20 cm recess with a hood (+z end only; the -z ones
are inside the link), the painted light treads on the link's top real 8 cm ribs, parapets on the hall roof and
the stair housing, fascias round the cab roof.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "art"))
from building_cad import Builder  # noqa: E402
from cad_building import Original  # noqa: E402

D = Path(sys.argv[1])
B = Builder()
O = Original("trafcon2")
IM = O.images[0]
RES = IM.shape[0]
LUM = IM[..., :3] @ np.array([0.299, 0.587, 0.114])

hall = B.prism_z("hall", [(-8.4, 0.0), (10.8, 0.0), (12.4, 1.6), (12.4, 16.0), (-4.8, 16.0), (-10.0, 7.2), (-10.0, 1.6)],
                 -4.86, 12.14)
link_hi = B.prism_z("link", [(-7.76, 3.6), (10.4, 3.6), (10.4, 6.0), (8.0, 7.2), (-5.36, 7.2), (-7.76, 6.0)], -28.86, -4.9)
link_lo = B.box("linklo", (-5.36, 0.0, -28.86), (10.4, 3.6, -4.9))
B.box("linkend", (-7.76, 0.0, -28.86), (-5.36, 3.6, -27.66))
for k, zc in enumerate((-9.66, -15.66, -21.66)):
    B.prism_y(f"pier{k}", [(-5.36, zc - 0.6), (-5.36, zc + 0.6), (-6.56, zc)], 0.0, 3.6)
tower = B.prism_x("tower", [(-29.01, 0.0), (-22.34, 0.0), (-22.34, 21.11), (-31.51, 21.11), (-31.51, 6.33)], -1.63, 7.85)
stair = B.prism_x("stair", [(-22.46, 7.2), (-12.86, 7.2), (-18.86, 17.2), (-22.46, 17.2)], 1.2, 4.4)
cab = B.loft_y("cab", [(-1.63, -31.51), (7.85, -31.51), (7.85, -22.34), (-1.63, -22.34)], 21.11,
               [(-3.92, -33.57), (9.91, -33.57), (9.91, -20.25), (-3.92, -20.25)], 26.64)
B.loft_y("roof", [(-3.92, -33.57), (9.91, -33.57), (9.91, -20.25), (-3.92, -20.25)], 26.64,
         [(2.75, -26.82), (2.85, -26.82), (2.85, -26.72), (2.75, -26.72)], 28.06)


def host(c, n):
    if n[1] < -0.2:
        return cab
    if c[2] > -4.9:
        return hall
    if c[2] < -22.3 and -1.7 < c[0] < 7.9:
        return tower
    if c[1] > 7.2:
        return stair
    return link_hi if c[1] > 3.6 else link_lo


k = 0
for o in json.load(open(D / "openings.json"))["openings"]:
    n, c = np.array(o["normal"]), np.array(o["center"])
    if o["w"] < 0.3 or o["h"] < 0.2:
        continue
    t = host(c, n)
    B.recess(t, o, 0.3 if t == cab else 0.25)
    if t != cab and abs(n[1]) < 0.6:
        B.sill(f"sill{k}", o, proud=0.12, thick=0.08, overhang=0.1)
    k += 1
for o in json.load(open(D / "decal_door.json"))["rects"]:
    if o["normal"][2] > 0.5:
        B.recess(hall, o, 0.3)
        B.sill("lintel", o, proud=0.25, thick=0.3, overhang=0.2, top=True)
for o in json.load(open(D / "decal_sdoor.json"))["rects"]:
    if o["normal"][2] > 0.5:
        B.recess(hall, o, 0.2)
        B.sill("doorhood", o, proud=0.4, thick=0.1, overhang=0.15, top=True)

# treads: the light painted bands on the link's flat top -> 8 cm ribs (flat colour of the art under them)
ti = next(i for i, n in enumerate(O.normal) if n[1] > 0.99 and abs(O.tris[i][0][1] - 7.2) < 0.01)
A = np.linalg.solve(np.c_[O.uvs[ti], np.ones(3)], O.tris[ti]).T
uv = O.uvs[ti] * RES
u0, v0 = np.ceil(uv.min(0)).astype(int) + 2
u1, v1 = np.floor(uv.max(0)).astype(int) - 2
light = LUM[v0:v1, u0:u1] > 0.55
nr = 0
for r in range(light.shape[0]):
    if not light[r].mean() > 0.0:
        continue
    if r > 0 and light[r - 1].any() and (light[r] == light[r - 1]).all():
        continue  # same band as the row above: handled when the band started
    # a band: the rows below with the same run pattern
    r1 = r
    while r1 + 1 < light.shape[0] and (light[r1 + 1] == light[r]).all():
        r1 += 1
    if r1 - r + 1 > 8:
        continue  # a plain field, not a tread
    row = light[r]
    xs = np.flatnonzero(np.diff(np.r_[0, row.astype(int), 0]))
    for a, b in zip(xs[::2], xs[1::2]):
        if b - a < 6:
            continue
        P = np.array([A @ [(u0 + uu) / RES, (v0 + vv) / RES, 1] for uu in (a, b) for vv in (r, r1 + 1)])
        lo, hi = P.min(0), P.max(0)
        B.box(f"tread{nr}@avg", (lo[0], 7.2, lo[2]), (hi[0], 7.28, hi[2]))
        nr += 1


def parapet(name, x0, z0, x1, z1, y, h=0.45, t=0.2, inset=0.05):
    a0, a1, b0, b1 = x0 + inset, x1 - inset, z0 + inset, z1 - inset
    for i, (lo, hi) in enumerate((((a0, y, b0), (a1, y + h, b0 + t)), ((a0, y, b1 - t), (a1, y + h, b1)),
                                  ((a0, y, b0 + t), (a0 + t, y + h, b1 - t)), ((a1 - t, y, b0 + t), (a1, y + h, b1 - t)))):
        B.box(f"{name}{i}", lo, hi)


parapet("hallpar", -4.8, -4.86, 12.4, 12.14, 16.0)
parapet("stairpar", 1.2, -22.34, 4.4, -18.86, 17.2, h=0.35, t=0.15)
F, T = 0.22, 0.3
for i, (lo, hi) in enumerate((((-3.92 - F, 26.5, -33.57 - F), (9.91 + F, 26.5 + T, -33.55)),
                              ((-3.92 - F, 26.5, -20.27), (9.91 + F, 26.5 + T, -20.25 + F)),
                              ((-3.92 - F, 26.5, -33.55), (-3.9, 26.5 + T, -20.27)),
                              ((9.89, 26.5, -33.55), (9.91 + F, 26.5 + T, -20.27)))):
    B.box(f"fascia{i}@avg", lo, hi)
B.box("ledge@avg", (-1.83, 20.81, -31.71), (8.05, 21.11, -22.14))
print(B.dump())
print(nr, "treads", file=sys.stderr)
