#!/usr/bin/env python3
"""CAD rebuild of the loading-dock warehouse (appearance rpbuilding), in the original's frame.

    D=~/craft/solid/mc2/buildings/rpbuilding
    python3 -I tools/art/cad_building.py openings rpbuilding > $D/openings.json
    python3 -I tools/cad/rpbuilding_cad.py $D > $D/rpbuilding.json
    solidcraft-cli run $D/rpbuilding.json --out $D/rpbuilding.obj
    python3 -I tools/art/cad_building.py bake rpbuilding $D/rpbuilding.obj --texel 0.015

Measured from game/assets/objects/rpbuilding.glb (nodes Warehouse, Doors, Doors01): a shed x -10.54..10.56,
z -6.84..6.76, flat roof at 6.80 m; its end bays (x -10.54..-8.81 and 8.84..10.56) are portal frames whose
45 degree buttresses run down to z -10.63 / 10.59 at 2.95 m; two more painted frames (x -4.37..-2.51, 2.56..4.23)
cross roof and walls; 1.95 m loading docks on both ends (x to -12.42 / 12.25) under roller doors (Doors) in the
end walls, and a 5.23 m door (Doors01) in each long wall. The original's cut-out doorways (with an interior box
behind) stay closed here: its doors cover them. Relief: all four frames stand 20 cm proud of roof and walls;
roof seams (raised battens on the painted lines, about 0.95 m apart) and siding drip ledges (about 1.03 m apart)
in the bays; the doors are real chamfered panels with a rail, framed, with lintels over the long-wall doors; the
dock fronts carry the six painted bumpers each as 15 cm blocks and a chamfered edge.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_cad import Builder, box_edges  # noqa: E402

B = Builder()
X0, X1, Z0, Z1, H = -10.54, 10.56, -6.84, 6.76, 6.80
P = 0.20  # frame relief

B.box("shed", (X0, 0.0, Z0), (X1, H, Z1))

# end portal frames with their buttresses (the slope's line carried 20 cm up over the roof)
BZ0, BZ1, BY = -10.63, 10.59, 2.95
end_prof = [(BZ0, 0.0), (BZ1, 0.0), (BZ1, BY), (BZ1 - (H + P - BY), H + P), (BZ0 + (H + P - BY), H + P), (BZ0, BY)]
for nm, (a, b) in (("frame_w", (X0, -8.81)), ("frame_e", (8.84, X1))):
    B.prism_x(nm, end_prof, a, b)
# middle frames: an inverted U over roof and long walls
u_prof = [(Z0 - P, 0.0), (Z0, 0.0), (Z0, H), (Z1, H), (Z1, 0.0), (Z1 + P, 0.0), (Z1 + P, H + P), (Z0 - P, H + P)]
for k, (a, b) in enumerate(((-4.37, -2.51), (2.56, 4.23))):
    B.prism_x(f"frame_m{k}", u_prof, a, b)

BAYS = ((-8.81, -4.37), (-2.51, 2.56), (4.23, 8.84))
# roof seams on the painted lines
for k, zs in enumerate((1.09, 2.10, 3.05, 4.00, 4.95, 5.90, 6.85, 7.67, 8.68, 9.63, 10.58, 11.60, 12.55)):
    z = Z0 + zs
    for j, (a, b) in enumerate(BAYS):
        B.box(f"seam{k}_{j}", (a, H - 0.01, z - 0.04), (b, H + 0.05, z + 0.04))
# siding drip ledges on the long walls' outer bays
for k, y in enumerate((0.98, 2.01, 3.03, 4.06, 5.09, 6.11)):
    for j, (a, b) in enumerate((BAYS[0], BAYS[2])):
        B.box(f"ledge{k}_{j}s", (a, y - 0.03, Z0 - 0.05), (b, y + 0.03, Z0 + 0.01))
        B.box(f"ledge{k}_{j}n", (a, y - 0.03, Z1 - 0.01), (b, y + 0.03, Z1 + 0.05))


def door(name, lo, hi, axis, sgn):
    """A chamfered door panel with a rail at 48 % down (the painted bar)."""
    B.box(name, lo, hi, chamfer=0.03, chamfer_edges=box_edges(lo, hi, "all"))
    y1, y0 = hi[1], lo[1]
    yr = y1 - 0.48 * (y1 - y0)
    out = hi if sgn > 0 else lo
    rl, rh = list(lo), list(hi)
    rl[1], rh[1] = yr - 0.12, yr + 0.12
    if axis == 0:
        rl[2] += 0.15
        rh[2] -= 0.15
        rl[0], rh[0] = (out[0] - 0.01, out[0] + 0.06) if sgn > 0 else (out[0] - 0.06, out[0] + 0.01)
    else:
        rl[0] += 0.15
        rh[0] -= 0.15
        rl[2], rh[2] = (out[2] - 0.01, out[2] + 0.06) if sgn > 0 else (out[2] - 0.06, out[2] + 0.01)
    B.box(name + "_rail", tuple(rl), tuple(rh))


# roller doors in the end walls (Doors), framed
FW = 0.12
for k, (x0, x1, za, zb, sgn) in enumerate(((-10.77, X0, -5.77, -2.35, -1), (-10.77, X0, -1.74, 5.98, -1),
                                           (X1, 10.81, -6.04, 1.67, 1), (X1, 10.81, 2.28, 5.70, 1))):
    door(f"door{k}", (x0, 1.95, za), (x1, 5.58, zb), 0, sgn)
    xf0, xf1 = (x0 - 0.05, x1) if sgn < 0 else (x0, x1 + 0.05)
    B.box(f"dframe{k}_t", (xf0, 5.58, za - FW), (xf1, 5.58 + FW, zb + FW))
    B.box(f"dframe{k}_a", (xf0, 1.95, za - FW), (xf1, 5.58, za))
    B.box(f"dframe{k}_b", (xf0, 1.95, zb), (xf1, 5.58, zb + FW))
# long-wall doors (Doors01) with lintels
for k, (za, zb, sgn) in enumerate(((-7.11, Z0, -1), (Z1, 7.02, 1))):
    door(f"bigdoor{k}", (-2.29, 0.0, za), (2.30, 5.23, zb), 2, sgn)
    zl0, zl1 = (Z0 - 0.3, Z0) if sgn < 0 else (Z1, Z1 + 0.3)
    B.box(f"lintel{k}", (-2.51, 5.23, zl0), (2.56, 5.53, zl1))

# loading docks, chamfered outer top edge, with the painted bumpers
for k, (x0, x1, y1, bump, sgn) in enumerate((
        (-12.42, X0, 1.95, [(-5.65, -4.35), (-3.84, -2.48), (-1.66, -0.4), (0.14, 1.5), (2.15, 3.48), (3.99, 5.35)], -1),
        (X1, 12.25, 1.94, [(-5.41, -4.05), (-3.54, -2.21), (-1.59, -0.2), (0.35, 1.64), (2.39, 3.79), (4.3, 5.59)], 1))):
    xo = x0 if sgn < 0 else x1
    B.box(f"dock{k}", (x0, 0.0, Z0), (x1, y1, 6.75), chamfer=0.06,
          chamfer_edges=[(xo, y1, 0.0), ((x0 + x1) / 2, y1, Z0), ((x0 + x1) / 2, y1, 6.75)])
    for j, (za, zb) in enumerate(bump):
        xa, xb = (xo - 0.15, xo + 0.01) if sgn < 0 else (xo - 0.01, xo + 0.15)
        B.box(f"bumper{k}_{j}", (xa, 1.30, za), (xb, 1.86, zb), chamfer=0.03, chamfer_edges=box_edges((xa, 1.30, za), (xb, 1.86, zb), "all"))

print(B.dump())
