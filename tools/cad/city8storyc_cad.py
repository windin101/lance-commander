#!/usr/bin/env python3
"""CAD rebuild of the eight-storey banded city tower (appearance city8storyc), in the original's frame.

    D=~/craft/solid/mc2/buildings/city8storyc
    python3 -I tools/art/cad_building.py openings city8storyc > $D/openings.json
    python3 -I tools/cad/city8storyc_cad.py > $D/city8storyc.json
    solidcraft-cli run $D/city8storyc.json --out $D/city8storyc.obj
    python3 -I tools/art/cad_building.py bake city8storyc $D/city8storyc.obj --max-res 4096

The box and its UV layout are in tools/cad/city8_facade.py. Art: lavender-grey concrete in five vertical bands
(light, dark, light, dark, light; the light ones with a bright edge), a light attic storey across the top under a
dark string course, small light-framed windows on the shared five-column grid, a door with a canopy under the
middle column of the +x wall. Relief: the light bands (texture u 0..51, 101..155, 204..258) and the attic band
(rows 11..46) are 14 cm plates on the wall, the dark bands stay back; a string course at rows 46..51; every window
a recess through its plate (or 12 cm into the wall in a dark band) with a sill; the door a 25 cm recess with a
canopy and a step, cornice band, plinth and parapet. Roof plant raised: the painted square housing, the louvred
grille as a framed box with real slats, three cabinets, and the painted pipes as round 20-sided pipes on saddles.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, box_edges  # noqa: E402
import city8_facade as F  # noqa: E402
import city6_facade as F6  # noqa: E402  (roof helpers: they only use the roof affine)

O = F.Original("city8storyc")
B = Builder()
(X0, _, Z0), (X1, H, Z1) = O.lo, O.hi
PX = (1, 0, 0)
PT = 0.14
CY = F.px_y(O, "upper", 11)
LY0, LY1 = F.px_y(O, "upper", 51), F.px_y(O, "upper", 46)
PY = F.px_y(O, "lower", 497)
main = B.box("main", (X0, 0.0, Z0), (X1, H, Z1), chamfer=0.05, chamfer_edges=box_edges((X0, 0.0, Z0), (X1, H, Z1), "vertical"))
BANDS = ((0, 51), (101, 155), (204, 258))
plates = {}
for nk in F.walls(O):
    for k, (u0, u1) in enumerate(BANDS):
        plates[(nk, k)] = F.strip(B, O, f"band{nk[0]}{nk[2]}_{k}", nk, u0, u1, PY, LY0, PT)
    plates[(nk, "attic")] = F.strip(B, O, f"attic{nk[0]}{nk[2]}", nk, 0, 258, LY1, CY, PT)
for k, (w, half, (ci, ri), nk) in enumerate(F.windows(O, gx=3, gy=(3, 3), skip=[(PX, "lower", 2, 3)])):
    if half == "upper" and ri == 0:
        host = plates[(nk, "attic")]
    elif ci in (0, 2, 4):
        host = plates[(nk, ci // 2)]
    else:
        host = None
    if host:
        B.recess(host, w, PT + 0.03, surface_shift=-PT)
        B.sill(f"sill{k}", w, proud=0.08, thick=0.06, overhang=0.05, surface_shift=-PT)
    else:
        B.recess(main, w, 0.12)
        B.sill(f"sill{k}", w, proud=0.08, thick=0.06, overhang=0.05)
door = F.px_box(O, PX, "lower", (361, 465, 406, 512))
B.recess(plates[(PX, 1)], door, PT + 0.03, surface_shift=-PT)
B.recess(main, door, 0.25)
B.sill("doorcanopy", door, proud=0.7, thick=0.14, overhang=0.25, top=True, surface_shift=-PT)
n, t, c = np.array(door["normal"]), np.array(door["t"]), np.array(door["center"])
a, b = c + t * (door["w"] / 2 + 0.35), c - t * (door["w"] / 2 + 0.35) + n * (0.6 + PT)
lo, hi = np.minimum(a, b), np.maximum(a, b)
B.box("doorstep@8f8b84", (lo[0], 0.0, lo[2]), (hi[0], 0.15, hi[2]))
# the light band's own colour (the texture's corner columns are dark edge lines, so a nearest-surface bake smears)
BANDRGB = "".join(f"{int(round(c * 255)):02x}" for c in O.images[0][60:240, 5:15, :3].reshape(-1, 3).mean(0))
# corner posts fill the notch where two walls' edge plates meet
for k, (cx, cz) in enumerate(((X0, Z0), (X0, Z1), (X1, Z0), (X1, Z1))):
    ex, ez = (cx - PT, cx) if cx == X0 else (cx, cx + PT), (cz - PT, cz) if cz == Z0 else (cz, cz + PT)
    for j, (y0, y1) in enumerate(((PY, LY0), (LY1, CY))):
        B.box(f"corner{k}_{j}@{BANDRGB}", (ex[0], y0, ez[0]), (ex[1], y1, ez[1]))
F.rings(B, O, (("cornice", CY, H, 0.32), ("course", LY0, LY1, 0.24), ("plinth", 0.0, PY, 0.22)))
F.parapet(B, O)

# roof plant
F6.roof_box(B, O, "housing", (288, 32, 347, 92), H, 1.2, inset=0.05)
gx0, gz0, gx1, gz1 = F.roof_xz(O, (291, 175, 338, 220))
B.box("grillframe", (gx0, H, gz0), (gx1, H + 0.45, gz1))
B.box("grillcut", (gx0 + 0.12, H + 0.15, gz0 + 0.12), (gx1 - 0.12, H + 0.6, gz1 - 0.12))
B.cut("grillframe", "grillcut")
for j in range(5):
    x = gx0 + 0.12 + (gx1 - gx0 - 0.24) * (j + 0.5) / 5
    B.box(f"slat{j}", (x - 0.06, H + 0.1, gz0 + 0.12), (x + 0.06, H + 0.42, gz1 - 0.12))
for k, box in enumerate(((403, 167, 420, 222), (427, 167, 443, 222), (451, 167, 467, 222))):
    F6.roof_box(B, O, f"cab{k}", box, H, 1.0, inset=0.02)
PYP, PR = H + 0.22, 0.09
for k, (a, b) in enumerate((((347, 57), (498, 57)), ((347, 70), (498, 70)), ((271, 140), (498, 140)))):
    F6.pipe(B, O, f"pipe{k}", a, b, PR, PYP)
    F6.saddles(B, O, f"pipe{k}", a, b, PR, PYP, H, n=3)
for k, x in enumerate((411, 436, 461)):
    F6.pipe(B, O, f"drop{k}", (x, 140), (x, 167), PR, PYP)
print(B.dump())
