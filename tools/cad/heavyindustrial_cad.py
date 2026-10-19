#!/usr/bin/env python3
"""CAD rebuild of the brick heavy-industry block (appearance heavyindustrial), in the original's frame.

    D=~/craft/solid/mc2/buildings/heavyindustrial
    python3 -I tools/art/cad_building.py openings heavyindustrial > $D/openings.json
    python3 -I tools/art/cad_building.py decal heavyindustrial <mat> u0 v0 u1 v1 > $D/decal_<name>.json  (see DECALS)
    python3 -I tools/cad/heavyindustrial_cad.py $D > $D/heavyindustrial.json
    solidcraft-cli run $D/heavyindustrial.json --out $D/heavyindustrial.obj
    python3 -I tools/art/cad_building.py bake heavyindustrial $D/heavyindustrial.obj

Measured from game/assets/objects/heavyindustrial.glb (faces listed with their UVs): a 16.92 x 18.72 m brick block,
walls to 8.86 m, with a 4.68 m wide entrance court cut 4.18 m into the front; a slate mansard (1.44 m in, up to a flat
roof at 11.02 m) that follows the court; an open bay under the back-left corner (5.04 x 5.04 m, ceiling 5.76 m)
holding a hexagonal tank with three wedge brackets; a lean-to porch on the back wall (to 5.22 m); and two raked
ventilator stacks on the roof (4.32 x 3.96 m, 12.46 -> 15.34 m). Relief: each sash window (two cut-outs) one 15 cm
recess with a stone sill, glass and the painted sash bar at its back; the doors 25 cm recesses with their glazing at
the back; the painted dark base a 1.5 m plinth 6 cm proud; a cornice at the eaves; a coping round the flat roof;
the ramp in the court real steps; the stacks' louvres 25 cm recesses; the painted plant box a 0.6 m housing with
two fan cowls, the louvre and the yellow cabinet real boxes. The two Site_Smoke empties are not carried over
(the game does not read them; cad_building.py bake keeps mesh nodes only).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

DECALS = {  # name: (material, u0, v0, u1, v1) in the upscaled atlas, for cad_building.py decal
    "door_front": (0, 0.664, 0.737, 0.752, 0.811), "door_back": (0, 0.82, 0.40, 0.962, 0.532),
    "louvre_stack": (0, 0.654, 0.205, 0.771, 0.298), "plant": (0, 0.098, 0.184, 0.291, 0.41),
    "roof_louvre": (0, 0.086, 0.437, 0.156, 0.481), "cabinet": (0, 0.381, 0.327, 0.415, 0.40),
}
D = Path(sys.argv[1])
X, Z0, Z1 = 8.46, -9.0, 9.72
CX, CZ = 2.34, 5.54          # entrance court: |x| < 2.34, z > 5.54
BX, BZ = -3.42, -3.96        # open bay: x < -3.42, z < -3.96, under 5.76 m
YB, YW, YT = 5.76, 8.86, 11.02
INSET = 1.44
WIN_DEPTH, DOOR_DEPTH = 0.15, 0.25


def rects(name):
    return json.load(open(D / f"decal_{name}.json"))["rects"]


def ccw(poly):
    a = sum(x0 * z1 - x1 * z0 for (x0, z0), (x1, z1) in zip(poly, poly[1:] + poly[:1]))
    return poly if a > 0 else poly[::-1]


def edges(poly):
    """(start, end, outward normal) of each edge of a counter-clockwise (x, z) polygon."""
    out = []
    for (x0, z0), (x1, z1) in zip(poly, poly[1:] + poly[:1]):
        L = math.hypot(x1 - x0, z1 - z0)
        out.append(((x0, z0), (x1, z1), (( z1 - z0) / L, -(x1 - x0) / L), L))
    return out


def band(name, poly, y0, y1, proud, inset=0.0, extend=0.0, avg=False):
    """A bar along every edge of the polygon, from y0 to y1, standing `proud` out (or `inset` in)."""
    for k, ((x0, z0), (x1, z1), (nx, nz), L) in enumerate(edges(poly)):
        mx, mz = (x0 + x1) / 2, (z0 + z1) / 2
        off = (proud - inset) / 2
        c = (mx + nx * off, (y0 + y1) / 2, mz + nz * off)
        t = np.array([(x1 - x0) / L, 0.0, (z1 - z0) / L])
        n = np.array([nx, 0.0, nz])
        b = np.cross(n, t)
        if b[1] < 0:  # keep the box right-handed with b up
            t = -t
            b = np.cross(n, t)
        B.obox(f"{name}{k}" + ("@avg" if avg else ""), c, t, b, n, (L + 2 * extend, y1 - y0, proud + inset))


# footprints, (x, z); the court notch in front, the bay corner at the back left
upper = ccw([(-X, Z0), (X, Z0), (X, Z1), (CX, Z1), (CX, CZ), (-CX, CZ), (-CX, Z1), (-X, Z1)])
lower = ccw([(BX, Z0), (X, Z0), (X, Z1), (CX, Z1), (CX, CZ), (-CX, CZ), (-CX, Z1), (-X, Z1), (-X, BZ), (BX, BZ)])
I = INSET
top = ccw([(-X + I, Z0 + I), (X - I, Z0 + I), (X - I, Z1 - I), (CX + I, Z1 - I), (CX + I, CZ - I), (-CX - I, CZ - I),
           (-CX - I, Z1 - I), (-X + I, Z1 - I)])

B = Builder()
# ---- volumes
low = B.prism_y("lower", lower, 0.0, YB)
up = B.prism_y("upper", upper, YB, YW)
B.loft_y("mansard", upper, YW, top, YT)

# ---- windows: each sash window's two cut-outs as one recess; door glazing at the back of its door
ops = [o for o in json.load(open(D / "openings.json"))["openings"] if abs(o["normal"][1]) < 0.1]
doors = {k: rects(k) for k in ("door_front", "door_back")}


def key(o):
    c, n, t = np.array(o["center"]), np.array(o["normal"]), np.array(o["t"])
    return tuple(np.round(n, 2)), round(float(c @ n), 2), round(float(c @ t), 1)


groups = {}
for o in ops:
    groups.setdefault(key(o), []).append(o)
windows = []
for g in groups.values():
    g.sort(key=lambda o: o["center"][1])
    run = [g[0]]
    for o in g[1:]:
        prev = run[-1]
        if o["center"][1] - o["h"] / 2 - (prev["center"][1] + prev["h"] / 2) < 0.3:
            run.append(o)
        else:
            windows.append(run)
            run = [o]
    windows.append(run)


def merged(run):
    b = np.array(run[0]["b"])
    y0 = min(o["center"][1] - o["h"] / 2 for o in run)
    y1 = max(o["center"][1] + o["h"] / 2 for o in run)
    c = np.array(run[0]["center"], float)
    c[1] = (y0 + y1) / 2
    return dict(run[0], center=c.tolist(), h=y1 - y0, w=max(o["w"] for o in run))


def inside_door(o):
    for nm, rs in doors.items():
        for r in rs:
            if np.dot(r["normal"], o["normal"]) > 0.9 and abs(np.dot(np.subtract(o["center"], r["center"]), r["normal"])) < 0.05:
                d = np.subtract(o["center"], r["center"])
                if abs(d @ np.array(r["t"])) < r["w"] / 2 and abs(d @ np.array(r["b"])) < r["h"] / 2:
                    return nm
    return None


for nm, rs in doors.items():
    for o in rs:
        tgt = "leanto" if nm == "door_back" else low
        if nm == "door_front":
            B.recess(low, o, DOOR_DEPTH)
for k, run in enumerate(windows):
    o = merged(run)
    d = inside_door(o)
    if d:
        B.recess(low if d == "door_front" else "leanto", o, 0.06, surface_shift=DOOR_DEPTH if d == "door_front" else 0.15)
        continue
    B.recess(low if o["center"][1] < YB else up, o, WIN_DEPTH)
    B.sill(f"sill{k}@b8b2a6", o, proud=0.12, thick=0.10, overhang=0.08)

# ---- lean-to porch on the back wall, its door a 15 cm recess
B.prism_x("leanto", [(-9.72, 0.0), (-9.0, 0.0), (-9.0, 5.22), (-9.72, 4.86)], -2.73, 2.81)
for o in doors["door_back"]:
    B.recess("leanto", o, 0.15)
# move the lean-to door glazing (cut before the porch existed in the list above) is handled in the window loop

# ---- plinth, cornice, coping
band("plinth", lower, 0.0, 1.5, 0.06, extend=0.06)
band("cornice", upper, YW - 0.30, YW + 0.02, 0.20, extend=0.20)
band("coping", top, YT, YT + 0.15, 0.0, inset=0.22, avg=False)

# ---- court steps: five 0.29 m risers up to the door sill at 1.44 m
for k in range(5):
    z1 = 9.0 - k * (9.0 - CZ) / 5
    B.box(f"step{k}", (-CX, 0.0, CZ), (CX, 1.44 * (k + 1) / 5, z1))

# ---- open bay: hexagonal tank, two hoops, the original's three wedge brackets
hexa = [(-3.85, -6.55), (-4.93, -8.42), (-7.09, -8.42), (-8.17, -6.55), (-7.09, -4.68), (-4.93, -4.68)]
B.prism_y("tank", hexa, 0.0, YB)
cx, cz = -6.01, -6.55
for k, y in enumerate((1.9, 3.8)):
    B.prism_y(f"hoop{k}@avg", [(cx + (x - cx) * 1.04, cz + (z - cz) * 1.04) for x, z in hexa], y, y + 0.16)
for k, y in enumerate((1.44, 2.88, 4.32)):
    B.prism_y(f"bracket{k}", [(-8.03, -3.96), (-7.31, -5.15), (-8.03, -6.34)], y, y + 0.43)

# ---- ventilator stacks: raked prisms standing on the roof, louvres recessed into the raked face
for k, (za, zb) in enumerate(((-6.12, -2.16), (-1.08, 2.88))):
    s = B.prism_z(f"stack{k}", [(3.96, 10.66), (8.28, 8.93), (8.28, 15.34), (3.96, 12.46)], za, zb)
    for o in rects("louvre_stack"):
        if za < o["center"][2] < zb:
            B.recess(s, o, 0.25)

# ---- roof plant
for o in rects("plant"):
    c, w, h = o["center"], o["w"], o["h"]
    # roof rects: t along x, b along -z (cad_building regions_3d), w along x, h along z
    B.box("plant", (c[0] - w / 2, YT - 0.02, c[2] - h / 2), (c[0] + w / 2, YT + 0.6, c[2] + h / 2), chamfer=0.04)
for k, z in enumerate((-4.44, -1.86)):
    B.c("solid.cylinder", radius=1050.0, height=200.0, base=[1560.0, round(-z * 1000, 1), round((YT + 0.58) * 1000, 1)],
        axis=[0, 0, 1], body_name=f"fan{k}", operation="new")
for nm, hgt in (("roof_louvre", 0.35), ("cabinet", 0.45)):
    for k, o in enumerate(rects(nm)):
        c, w, h = o["center"], o["w"], o["h"]
        B.box(f"{nm}{k}", (c[0] - w / 2, YT - 0.02, c[2] - h / 2), (c[0] + w / 2, YT + hgt, c[2] + h / 2), chamfer=0.03)

print(B.dump())
