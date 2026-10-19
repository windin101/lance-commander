#!/usr/bin/env python3
"""CAD rebuild of the purification plant (appearance purificationplant), in the original's frame.

    D=~/craft/solid/mc2/buildings/purificationplant
    python3 -I tools/art/cad_building.py openings purificationplant > $D/openings.json
    python3 -I tools/art/cad_building.py decal purificationplant 0 u0 v0 u1 v1 > $D/decal_<name>.json  (see DECALS)
    python3 -I tools/cad/purificationplant_cad.py $D > $D/purificationplant.json
    solidcraft-cli run $D/purificationplant.json --out $D/purificationplant.obj
    python3 -I tools/art/cad_building.py bake purificationplant $D/purificationplant.obj

Measured from game/assets/objects/purificationplant.glb: a pump hall (x -4.18..-1.01, z -11.07..2.32) with walls
to 4.83 m and a 0.35 m 45-degree chamfer to a flat roof at 5.18 m; a tower (x -1.01..2.86, z -11.07..-4.86) to
5.52 m under a hipped cap (0.69 m in) to 6.76 m, with a five-sided stack (centre 0.57, -9.55) to 10.63 m; two
octagonal settling tanks (centres x -8.455, z -0.025 / -8.645, 3.725 m to a corner) with walls leaning in to 2.21 m
and a shallow cone to 2.76 m; two 0.55 m square ducts from the hall down to the tank centres.
Rebuilt round (issue I77): tanks as 24-sided frustums of equal area, the stack and the ducts as 24-sided pipes,
a hub drum and a rim on each tank. Relief: the hall's tank windows 18 cm recesses with sill and lintel, a raised
skylight, the tower's two-pane window and doors real recesses, a plinth, a stack lip, collar and hollow top,
flanges where the ducts meet the hall. Painted red bands and hazard stripes stay paint.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, box_edges  # noqa: E402

DECALS = {  # name: (u0, v0, u1, v1) on material 0 of the upscaled atlas
    "door": (0.586, 0.883, 0.66, 0.986), "bigwin1": (0.4, 0.469, 0.654, 0.66), "bigwin2": (0.693, 0.469, 0.957, 0.66),
    "sky": (0.072, 0.406, 0.146, 0.953), "rvent": (0.234, 0.42, 0.297, 0.605),
}
D = Path(sys.argv[1])
HX0, HX1, HZ0, HZ1, HY, HCH = -4.18, -1.01, -11.07, 2.32, 4.83, 0.35
TX0, TX1, TZ0, TZ1, TY, TTOP, TIN = -1.01, 2.86, -11.07, -4.86, 5.52, 6.76, 0.69
SX, SZ, SR, SY = 0.57, -9.55, 0.62, 10.63
TANKS = ((-8.455, -0.025), (-8.455, -8.645))
R0, R1, RY, HUB, HUBY = 3.53, 3.27, 2.21, 1.1, 2.575


def rects(name, nx=None):
    rs = json.load(open(D / f"decal_{name}.json"))["rects"]
    return [r for r in rs if nx is None or abs(r["normal"][0] - nx) < 0.05]


def ring(cx, cz, r, k=24):
    return [(cx + r * math.cos(2 * math.pi * i / k), cz + r * math.sin(2 * math.pi * i / k)) for i in range(k)]


B = Builder()
# ---- volumes
hall = B.box("hall", (HX0, 0.0, HZ0), (HX1, HY + HCH, HZ1), chamfer=HCH, chamfer_edges=box_edges((HX0, 0, HZ0), (HX1, HY + HCH, HZ1)))
tower = B.box("tower", (TX0, 0.0, TZ0), (TX1, TY, TZ1))
B.loft_y("cap", [(TX0, TZ0), (TX1, TZ0), (TX1, TZ1), (TX0, TZ1)], TY,
         [(TX0 + TIN, TZ0 + TIN), (TX1 - TIN, TZ0 + TIN), (TX1 - TIN, TZ1 - TIN), (TX0 + TIN, TZ1 - TIN)], TTOP)
B.prism_y("stack", ring(SX, SZ, SR), TTOP - 0.05, SY)
B.prism_y("scollar@avg", ring(SX, SZ, SR + 0.1), TTOP - 0.05, TTOP + 0.25)
B.prism_y("slip", ring(SX, SZ, SR + 0.08), SY - 0.25, SY + 0.05)
B.prism_y("shole", ring(SX, SZ, SR - 0.15), SY - 1.2, SY + 0.2)
B.cut("slip", "shole")
B.prism_y("shole2", ring(SX, SZ, SR - 0.15), SY - 1.2, SY + 0.2)
B.cut("stack", "shole2")

# ---- settling tanks: frustum wall, shallow cone, rim, hub drum
for k, (cx, cz) in enumerate(TANKS):
    B.loft_y(f"tank{k}", ring(cx, cz, R0), 0.0, ring(cx, cz, R1), RY)
    B.loft_y(f"cone{k}", ring(cx, cz, R1), RY, ring(cx, cz, HUB), HUBY)
    B.prism_y(f"rim{k}@avg", ring(cx, cz, R1 + 0.07), RY - 0.14, RY + 0.08)
    B.prism_y(f"hub{k}", ring(cx, cz, HUB), HUBY - 0.05, 2.86)
    # duct: down from the hub, then a straight run up to the hall wall
    PR, PY = 0.24, 3.42
    B.prism_y(f"drop{k}", ring(cx, cz, PR), 2.8, PY + PR)
    B.prism_y(f"dropcap{k}@avg", ring(cx, cz, PR + 0.06), 2.8, 2.98)
    x0, x1, y1 = cx - PR * 0.5, HX0 + 0.15, 4.45
    L = math.hypot(x1 - x0, y1 - PY)
    ang = math.degrees(math.atan2(y1 - PY, x1 - x0))
    nm = f"duct{k}"
    B.prism_x(nm, [(cz + PR * math.cos(2 * math.pi * i / 24), PR * math.sin(2 * math.pi * i / 24)) for i in range(24)], 0.0, L)
    B.c("solid.move", bodies=[nm], axis=[0, -1, 0], angle=f"{ang:.4f} deg")  # about game +z
    B.c("solid.move", bodies=[nm], translate=[round(x0 * 1000, 2), 0, round(PY * 1000, 2)])
    fx = HX0 - 0.12
    fy = PY + (fx - x0) * math.tan(math.radians(ang))
    B.prism_x(f"flange{k}@avg", [(cz + (PR + 0.08) * math.cos(2 * math.pi * i / 24), fy + (PR + 0.08) * math.sin(2 * math.pi * i / 24))
                                 for i in range(24)], fx - 0.08, HX0 + 0.02)

# ---- hall: tank windows (the east face behind the tower stays flat), skylight, plinth
for nm in ("bigwin1", "bigwin2"):
    for k, o in enumerate(rects(nm)):
        if o["normal"][0] > 0 and o["center"][2] - o["w"] / 2 < TZ1:
            continue
        o = dict(o, w=o["w"] - 0.2, h=o["h"] - 0.2)
        B.recess(hall, o, 0.18)
        B.sill(f"{nm}_s{k}", o, proud=0.12, thick=0.1, overhang=0.1)
        B.sill(f"{nm}_l{k}", o, proud=0.1, thick=0.1, overhang=0.1, top=True)
for o in rects("sky"):
    c = o["center"]
    lo, hi = (c[0] - o["w"] / 2, HY + HCH - 0.02, c[2] - o["h"] / 2), (c[0] + o["w"] / 2, HY + HCH + 0.2, c[2] + o["h"] / 2)
    B.box("skylight", lo, hi, chamfer=0.1)
P = 0.06
B.box("pl_w", (HX0 - P, 0, HZ0 - P), (HX0, 0.45, HZ1 + P))
B.box("pl_hs", (HX0, 0, HZ1), (HX1 + P, 0.45, HZ1 + P))
B.box("pl_he", (HX1, 0, TZ1), (HX1 + P, 0.45, HZ1))
B.box("pl_n", (HX0, 0, HZ0 - P), (TX1 + P, 0.45, HZ0))
B.box("pl_te", (TX1, 0, TZ0), (TX1 + P, 0.45, TZ1 + P))
B.box("pl_ts", (TX0, 0, TZ1), (TX1, 0.45, TZ1 + P))

# ---- tower: two-pane window on the east face, the doors front and back, a roof hatch, eaves band
ops = [o for o in json.load(open(D / "openings.json"))["openings"] if o["normal"][0] > 0.9]
for k, o in enumerate(ops):
    B.recess(tower, o, 0.12)
c = [o["center"] for o in ops]
zlo = min(o["center"][2] - o["w"] / 2 for o in ops)
zhi = max(o["center"][2] + o["w"] / 2 for o in ops)
o0 = dict(ops[0], center=[TX1, ops[0]["center"][1], (zlo + zhi) / 2], w=zhi - zlo)
B.sill("winsill", o0, proud=0.1, thick=0.08, overhang=0.08)
for k, r in enumerate(rects("door")):
    B.recess(tower, r, 0.22)
    B.sill(f"lintel{k}", r, proud=0.14, thick=0.12, overhang=0.12, top=True)
    B.sill(f"step{k}@avg", dict(r, center=[r["center"][0], 0.08 + r["h"] / 2 + 0.08, r["center"][2]]), proud=0.35, thick=0.16, overhang=0.1)
for o in rects("rvent"):
    c = o["center"]
    z0, z1 = max(c[2] - o["h"] / 2, SZ + SR + 0.25), c[2] + o["h"] / 2
    B.box("hatch", (c[0] - o["w"] / 2, TTOP - 0.02, z0), (c[0] + o["w"] / 2, TTOP + 0.16, z1), chamfer=0.05)
E = 0.1
B.box("eav_n@avg", (TX0, TY - 0.2, TZ0 - E), (TX1 + E, TY, TZ0))
B.box("eav_s@avg", (TX0, TY - 0.2, TZ1), (TX1 + E, TY, TZ1 + E))
B.box("eav_e@avg", (TX1, TY - 0.2, TZ0), (TX1 + E, TY, TZ1))

print(B.dump())
