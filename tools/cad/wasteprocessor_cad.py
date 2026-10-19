#!/usr/bin/env python3
"""CAD rebuild of the waste processor (appearance wasteprocessor), in the original's frame.

    D=~/craft/solid/mc2/buildings/wasteprocessor
    python3 -I tools/art/cad_building.py openings wasteprocessor > $D/openings.json
    python3 -I tools/art/cad_building.py decal wasteprocessor <mat> u0 v0 u1 v1 > $D/decal_<name>.json  (see DECALS)
    python3 -I tools/cad/wasteprocessor_cad.py $D > $D/wasteprocessor.json
    solidcraft-cli run $D/wasteprocessor.json --out $D/wasteprocessor.obj
    python3 -I tools/art/cad_building.py bake wasteprocessor $D/wasteprocessor.obj

Measured from game/assets/objects/wasteprocessor.glb (faces listed with their UVs): a flat-roofed brick shed
15.49 x 7.33 m (x -11.46..4.03, z -2.28..5.05) to 4.5 m; three hexagonal riveted tanks in front (4.86 x 4.21 m,
centred x -10.27, -5.14, -0.01 at z 9.3) to 2.55 m; and three ridged wooden chutes from square hatches high on the
front wall (3.19..3.92 m) down onto the tank tops (CAD: straight triangular prisms). Relief: the clerestory strips and the small window 15 cm recesses
with sills (glass from the cut-outs, the painted mullions kept); the doors 25 cm recesses; the hatches framed; a dark
plinth 5 cm proud; a coping round the roof; the fan housing, the cell row and the four roof blocks real boxes; a rim
round each tank top. The painted roof pipes and the tanks' red band stay paint.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder  # noqa: E402

DECALS = {  # name: (material, u0, v0, u1, v1) in the upscaled atlas, for cad_building.py decal
    "door": (0, 0.793, 0.127, 0.88, 0.258), "roller": (0, 0.105, 0.582, 0.352, 0.77),
    "fanbox": (0, 0.49, 0.578, 0.735, 0.74), "blocks": (0, 0.765, 0.705, 0.94, 0.77),
    "topvent": (0, 0.77, 0.528, 0.935, 0.555),
    "sq": (0, 0.04, 0.287, 0.115, 0.342), "sq2": (0, 0.37, 0.287, 0.445, 0.342), "sq3": (0, 0.705, 0.287, 0.78, 0.342),
}
D = Path(sys.argv[1])
X0, X1, Z0, Z1, YR = -11.46, 4.03, -2.28, 5.05, 4.5
TANKS, TZ, TY = (-10.27, -5.14, -0.01), 9.3, 2.55
WIN_DEPTH, DOOR_DEPTH = 0.15, 0.25


def rects(name):
    return json.load(open(D / f"decal_{name}.json"))["rects"]


def hexa(cx, cz, rx, rz):
    return [(cx - rx, cz), (cx - rx / 2, cz - rz), (cx + rx / 2, cz - rz), (cx + rx, cz), (cx + rx / 2, cz + rz), (cx - rx / 2, cz + rz)]


B = Builder()
shed = B.box("shed", (X0, 0.0, Z0), (X1, YR, Z1))

# ---- windows and doors
for k, o in enumerate(json.load(open(D / "openings.json"))["openings"]):
    B.recess(shed, o, WIN_DEPTH)
    B.sill(f"sill{k}", o, proud=0.10, thick=0.08, overhang=0.06)
for k, nm in enumerate(("door", "roller")):
    for o in rects(nm):
        B.recess(shed, o, DOOR_DEPTH if nm == "door" else 0.3)
        B.sill(f"lintel{k}", o, proud=0.12, thick=0.12, overhang=0.10, top=True)
for nm in ("sq", "sq2", "sq3"):
    for o in rects(nm):
        B.frame(f"hatch_{nm}", o, width=0.08, proud=0.06)

# ---- plinth and roof coping
P, C = 0.05, 0.18
B.box("plinth_n", (X0 - P, 0.0, Z0 - P), (X1 + P, 0.65, Z0))
B.box("plinth_s", (X0 - P, 0.0, Z1), (X1 + P, 0.65, Z1 + P))
B.box("plinth_w", (X0 - P, 0.0, Z0), (X0, 0.65, Z1))
B.box("plinth_e", (X1, 0.0, Z0), (X1 + P, 0.65, Z1))
B.box("coping_n@avg", (X0 - 0.03, YR - 0.02, Z0 - 0.03), (X1 + 0.03, YR + 0.15, Z0 + C))
B.box("coping_s@avg", (X0 - 0.03, YR - 0.02, Z1 - C), (X1 + 0.03, YR + 0.15, Z1 + 0.03))
B.box("coping_w@avg", (X0 - 0.03, YR - 0.02, Z0 + C), (X0 + C, YR + 0.15, Z1 - C))
B.box("coping_e@avg", (X1 - C, YR - 0.02, Z0 + C), (X1 + 0.03, YR + 0.15, Z1 - C))


# ---- roof furniture
def roofbox(name, cx, cz, w, h, hgt, ch=0.03):
    B.box(name, (cx - w / 2, YR - 0.02, cz - h / 2), (cx + w / 2, YR + hgt, cz + h / 2), chamfer=ch)


for o in rects("fanbox"):
    roofbox("fanbox", o["center"][0], o["center"][2], o["w"], o["h"], 0.45, 0.06)
for o in rects("topvent"):
    roofbox("cells", o["center"][0], o["center"][2], o["w"], o["h"], 0.3)
for o in rects("blocks"):  # four blocks in the painted row, at the atlas columns 783-815, 828-865, 875-912, 920-958 px
    u0, u1 = 0.765, 0.94
    for k, (a, b) in enumerate(((783, 815), (828, 865), (875, 912), (920, 958))):
        xa = o["center"][0] - o["w"] / 2 + (a / 1024 - u0) / (u1 - u0) * o["w"]
        xb = o["center"][0] - o["w"] / 2 + (b / 1024 - u0) / (u1 - u0) * o["w"]
        roofbox(f"block{k}", (xa + xb) / 2, o["center"][2], xb - xa, o["h"] * 0.9, 0.5)

# ---- tanks with a rim, and the chutes (lofted from the wall hatch triangle down to the tank top)
for k, cx in enumerate(TANKS):
    B.prism_y(f"tank{k}", hexa(cx, TZ, 2.43, 2.105), 0.0, TY)
    B.prism_y(f"rim{k}@avg", hexa(cx, TZ, 2.43 + 0.05, 2.105 + 0.045), TY - 0.08, TY + 0.1)
    B.prism_y(f"rimcut{k}", hexa(cx, TZ, 2.43 - 0.12, 2.105 - 0.105), TY - 0.2, TY + 0.2)
    B.cut(f"rim{k}@avg", f"rimcut{k}")
    # chute: a ridged triangular prism, 0.84 m wide and 0.73 m tall, from inside the wall hatch tilted 11.7 deg down
    # into the tank top (a loft between the original's two end triangles tessellates into ~2k triangles)
    sk = B._sketch("XZ", 0.0, flip=True)
    B.c("sketch.line", points=[[round((cx - 0.42) * 1000, 2), -290.0], [round((cx + 0.42) * 1000, 2), -290.0],
                               [round(cx * 1000, 2), 440.0]], closed=True)
    B.c("sketch.finish")
    B.c("solid.extrude", distance=4700.0, sketch=sk, body_name=f"chute{k}", operation="new")
    B.c("solid.move", bodies=[f"chute{k}"], axis=[1, 0, 0], angle="11.7 deg")
    B.c("solid.move", bodies=[f"chute{k}"], translate=[0, -4950.0, 3480.0])

print(B.dump())
