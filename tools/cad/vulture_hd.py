#!/usr/bin/env python3
"""Generate the SolidCraft script for the CAD HD Vulture (Mad Dog), part by part on MC2's skeleton.

    python3 -I tools/cad/vulture_hd.py > ~/craft/solid/mc2/vulture_cad/vulture_hd.json
    solidcraft-cli run ~/craft/solid/mc2/vulture_cad/vulture_hd.json --out ~/craft/solid/mc2/vulture_cad/vulture_hd.obj
    python3 -I tools/art/cad_mech.py vulture ~/craft/solid/mc2/vulture_cad/vulture_hd.obj

Styling: a modern Mad Dog interpretation after Syllogy's "Mad Dog Prime, aka Vulture"
(printables.com/model/1863972, CC BY-NC-SA), used as a visual reference only; no geometry is
taken from it. Placement: every piece sits on the pivot of the original part it replaces, read
from game/assets/mechs/vulture.glb, so the original 16 animations drive it unchanged.

Frame: SolidCraft mm, Z up, forward = -Y (glTF +Z). Bodies are named "<node>.<piece>__<paint>";
paint is base | hl1 | hl2 (MechPaint team channels blue, red, green) or metal | dark | glass.
"""
import json
import math
import sys

# pivots (mm, Z up, forward -Y) from vulture.glb rest pose; see the module docstring
P = {
    "torso": (-28, 189, 5523), "hip": (8, 162, 5530),
    "l": {"uarm": (1739, 1607, 7496), "gun": (2874, 1594, 6332), "uleg": (1573, -27, 5235), "lleg": (1792, 1150, 3167),
          "foot": (2142, -590, 962), "itoe": (1701, -1189, 179), "otoe": (2560, -1205, 179), "btoe": (2143, -271, 189)},
    "r": {"uarm": (-1842, 1607, 7519), "gun": (-2999, 1594, 6333), "uleg": (-1583, -27, 5235), "lleg": (-1802, 1150, 3167),
          "foot": (-2153, -590, 962), "itoe": (-1712, -1189, 179), "otoe": (-2549, -1205, 179), "btoe": (-2148, -271, 189)},
}
NODE = {"l": {"uarm": "vu_luarm", "gun": "vu_lgun", "uleg": "vu_luleg", "lleg": "vu_llleg", "foot": "vu_lfoot",
              "itoe": "joint_litoe", "otoe": "joint_lotoe", "btoe": "joint_lbtoe"},
        "r": {"uarm": "vu_ruarm", "gun": "vu_rgun", "uleg": "vu_ruleg", "lleg": "vu_rlleg", "foot": "vu_rfoot",
              "itoe": "joint_ritoe", "otoe": "joint_rotoe", "btoe": "joint_rbtoe"}}

cmds = []
n_sk = [0]


def c(command, **params):
    cmds.append({"command": command, "params": params})


def box(name, center, size, chamfer=0.0, rot=None):
    """Chamfered box. rot = [(axis, deg), ...] applied about the box centre, in order."""
    lx, ly, lz = size
    c("solid.box", length=lx, width=ly, height=lz, center=[0, 0, 0], body_name=name)
    if chamfer:
        hx, hy, hz = lx / 2, ly / 2, lz / 2
        edges = [[sx * hx, 0, sz * hz] for sx in (1, -1) for sz in (1, -1)] + \
                [[0, sy * hy, sz * hz] for sy in (1, -1) for sz in (1, -1)] + \
                [[sx * hx, sy * hy, 0] for sx in (1, -1) for sy in (1, -1)]
        c("solid.chamfer", edges=edges, distance=min(chamfer, 0.45 * min(size)), body=name)
    for axis, deg in rot or []:
        c("solid.move", bodies=[name], axis=axis, angle=f"{deg} deg")
    c("solid.move", bodies=[name], translate=list(center))


def prism(name, axis, center, radius, length, sides=10, rot=None, cut_into=None):
    """Regular prism along x or y (low-poly cylinder), centred on `center`; cut_into bores it into a body."""
    n_sk[0] += 1
    sk = f"sk{n_sk[0]}"
    if axis == "x":
        c("sketch.create", plane="YZ", offset=-length / 2, name=sk)
        c("sketch.polygon.inscribed", center=[0, 0], radius=radius, sides=sides)
    else:  # y: plane at +L/2, a positive distance extrudes toward -y
        c("sketch.create", plane="XZ", offset=length / 2, flip=True, name=sk)
        c("sketch.polygon.inscribed", center=[0, 0], radius=radius, sides=sides)
    c("sketch.finish")
    if cut_into:
        # cut tools are built in place, so no rotation and the sketch sits at the real position
        cmds.pop(); cmds.pop(); cmds.pop()
        if axis == "x":
            c("sketch.create", plane="YZ", offset=center[0] - length / 2, name=sk)
            c("sketch.polygon.inscribed", center=[center[1], center[2]], radius=radius, sides=sides)
        else:
            c("sketch.create", plane="XZ", offset=center[1] + length / 2, flip=True, name=sk)
            c("sketch.polygon.inscribed", center=[center[0], center[2]], radius=radius, sides=sides)
        c("sketch.finish")
        c("solid.extrude", distance=length, sketch=sk, operation="cut", targets=[cut_into])
        return
    c("solid.extrude", distance=length, sketch=sk, body_name=name)
    for ax, deg in rot or []:
        c("solid.move", bodies=[name], axis=ax, angle=f"{deg} deg")
    c("solid.move", bodies=[name], translate=list(center))


def along(a, b):
    """Midpoint, length and the X-axis angle that turns +Y onto the YZ direction a->b."""
    mid = [(a[i] + b[i]) / 2 for i in range(3)]
    dy, dz = b[1] - a[1], b[2] - a[2]
    return mid, math.hypot(dy, dz), math.degrees(math.atan2(dz, dy))


def add(v, d):
    return [v[0] + d[0], v[1] + d[1], v[2] + d[2]]


# ---------------- torso: cockpit spine and the two missile boxes ----------------
T = "vu_torso"
box(f"{T}.spine__base", (0, -200, 6750), (1150, 3400, 2500), 260)
box(f"{T}.ridge__hl1", (0, -100, 8040), (480, 2800, 220), 80)
box(f"{T}.nose__base", (0, -2050, 7250), (1000, 1350, 1150), 280, rot=[([1, 0, 0], -14)])
box(f"{T}.canopy__glass", (0, -2600, 7520), (660, 440, 400), 120, rot=[([1, 0, 0], -14)])
box(f"{T}.chin__dark", (0, -2000, 6350), (760, 900, 320), 100)
box(f"{T}.back_vent__metal", (0, 1500, 6700), (1050, 560, 1100), 150)
for i, z in enumerate((6450, 6800, 7150)):
    box(f"{T}.vent_slat{i}__dark", (0, 1800, z), (900, 80, 150), 30)
for s in (1, -1):
    sx = "l" if s > 0 else "r"
    bx = s * 1300
    box(f"{T}.missile_box_{sx}__base", (bx, 300, 7750), (1250, 2000, 1950), 170)
    for col in (-1, 0, 1):          # 3 x 5 honeycomb of tubes bored into the front face (y = -700)
        for row in range(5):
            prism(None, "y", (bx + col * 360 + (row % 2) * 60 * s, -530, 7060 + row * 340), 125, 400, sides=8,
                  cut_into=f"{T}.missile_box_{sx}__base")
    box(f"{T}.ammo_{sx}__hl2", (bx + s * 660, 450, 7600), (110, 1400, 1200), 40)
    box(f"{T}.box_top_{sx}__hl1", (bx, 300, 8760), (900, 1500, 120), 40)
prism(f"{T}.antenna__metal", "x", (0, 1100, 8200), 34, 70, sides=6)
box(f"{T}.antenna_mast__metal", (0, 1100, 8850), (60, 60, 1300), 0)

# ---------------- hip ----------------
H = "vu_hip"
prism(f"{H}.barrel__base", "x", (0, 250, 5150), 470, 2250, sides=12)
for s in (1, -1):
    prism(f"{H}.joint_{'l' if s > 0 else 'r'}__metal", "x", (s * 1290, 250, 5150), 540, 330, sides=12)
box(f"{H}.crotch__base", (0, -480, 5120), (900, 700, 700), 160)
box(f"{H}.crotch_plate__hl1", (0, -850, 5150), (600, 90, 420), 30)

# ---------------- limbs, per side ----------------
for sx, s in (("l", 1), ("r", -1)):
    p, nd = P[sx], NODE[sx]

    # upper arm (shoulder actuator, arm block, pauldron)
    ua, n = p["uarm"], nd["uarm"]
    prism(f"{n}.shoulder__metal", "x", add(ua, (s * 380, 0, 0)), 420, 760)
    box(f"{n}.arm__base", add(ua, (s * 900, -10, -620)), (900, 900, 1650), 170)
    box(f"{n}.pauldron__hl1", add(ua, (s * 870, -60, 150)), (1150, 1100, 560), 180)

    # forearm gun pod (elbow, forearm, shroud, twin barrels)
    g, n = p["gun"], nd["gun"]
    prism(f"{n}.elbow__metal", "x", add(g, (0, 0, 0)), 400, 520)
    box(f"{n}.forearm__base", add(g, (s * 160, -1350, -90)), (880, 2600, 920), 170)
    box(f"{n}.forearm_plate__hl1", add(g, (s * 520, -1200, -60)), (90, 1900, 520), 30)
    box(f"{n}.shroud__hl2", add(g, (s * 130, -2780, -90)), (580, 420, 580), 100)
    for k in (-1, 1):
        prism(f"{n}.barrel{'ab'[k > 0]}__metal", "y", add(g, (s * 130 + k * 150, -3150, -90)), 85, 520, sides=8)

    # thigh: hip -> knee
    uleg, knee, n = p["uleg"], p["lleg"], nd["uleg"]
    mid, ln, ang = along(uleg, knee)
    box(f"{n}.thigh__base", (uleg[0] * 0.5 + knee[0] * 0.5, mid[1], mid[2]), (860, ln + 380, 1080), 200, rot=[([1, 0, 0], ang)])
    box(f"{n}.thigh_plate__hl1", (uleg[0] * 0.5 + knee[0] * 0.5 + s * 380, mid[1], mid[2]), (110, ln * 0.7, 700), 40, rot=[([1, 0, 0], ang)])

    # shin: knee -> ankle, with the big Mad Dog shin armour and a piston
    foot, n = p["foot"], nd["lleg"]
    prism(f"{n}.knee__metal", "x", knee, 470, 640, sides=12)
    mid, ln, ang = along(knee, foot)
    sxm = knee[0] * 0.5 + foot[0] * 0.5
    box(f"{n}.shin__metal", (sxm, mid[1], mid[2]), (560, ln + 200, 640), 120, rot=[([1, 0, 0], ang)])
    t = 0.62  # armour sits on the lower shin
    arm_c = (knee[0] + t * (foot[0] - knee[0]), knee[1] + t * (foot[1] - knee[1]), knee[2] + t * (foot[2] - knee[2]))
    box(f"{n}.shin_armour__base", arm_c, (1250, 1750, 1400), 380, rot=[([1, 0, 0], ang)])
    box(f"{n}.knee_pad__hl1", add(knee, (0, -380, 120)), (820, 520, 760), 180)
    box(f"{n}.shin_stripe__hl1", (arm_c[0] + s * 640, arm_c[1], arm_c[2]), (80, 1150, 560), 30, rot=[([1, 0, 0], ang)])
    prism(f"{n}.piston__metal", "y", (sxm, mid[1] + 260, mid[2] + 200), 95, ln * 0.8, sides=8, rot=[([1, 0, 0], ang)])

    # foot: ankle and foot block
    n = nd["foot"]
    prism(f"{n}.ankle__metal", "x", foot, 330, 620, sides=12)
    box(f"{n}.foot__base", add(foot, (0, -260, -440)), (1000, 1250, 640), 170)

    # toes: two forward claws and a rear spur, each its own part
    for key, tip in (("itoe", (s * -800, -1160)), ("otoe", (s * 840, -1145)), ("btoe", (0, 1100))):
        base, n = p[key], nd[key]
        yaw = math.degrees(math.atan2(tip[1], tip[0])) + 90  # turn -Y onto the tip direction
        L = math.hypot(*tip)
        box(f"{n}.toe__base", (base[0] + tip[0] / 2, base[1] + tip[1] / 2, 200), (470, L + 200, 380), 120, rot=[([0, 0, 1], yaw)])
        box(f"{n}.claw__dark", (base[0] + tip[0] * 1.02, base[1] + tip[1] * 1.02, 140), (320, 420, 260), 100, rot=[([0, 0, 1], yaw)])

json.dump({"commands": cmds}, sys.stdout, indent=0)
print(file=sys.stderr, end=f"{len(cmds)} commands\n")
