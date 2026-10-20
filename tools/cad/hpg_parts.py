"""Shared parts for the HPG bunker family (hpg_end, hpg_threeway, hpg_walkway), in the originals' frame (game
metres, Y up; tools/cad/building_cad.py). Measured from game/assets/objects/hpg_*.glb, which share one texture:

- hub: a 1.54 m plinth band (x -7.99..8.08, z -8.04..7.99) under a truncated pyramid to a flat roof at 7.44 m
  (x -5.54..5.62, z -5.59..5.54).
- tunnel: a 1.55 m band 12.72 m wide under a sloped-sided section to an 8.68 m flat roof at 6.67 m, ends at +-12.8 m.

Relief (the same on every member, so the pieces still butt together at the tunnel ends, whose section is exact):
the sloped walls stand 8 cm back from the band (a real ledge); the hub's painted roof panel is a 12 cm recess with
round corners and the hips carry a chamfer; the painted dark slots under the tunnel eaves are 18 cm deep recesses;
the painted pilasters between the slope panels are 7 cm proud ribs; the painted roof vents are raised housings with
the painted louvres on top (bake).
"""
import json
import math

import numpy as np

HUB_LO, HUB_HI, HUB_BAND = (-7.99, -8.04), (8.08, 7.99), 1.54
ROOF_LO, ROOF_HI, ROOF_Y = (-5.54, -5.59), (5.62, 5.54), 7.44
T_HALF, T_BAND, T_TOP_HALF, T_TOP = 6.36, 1.55, 4.34, 6.67
LEDGE = 0.08


def rounded_rect(x0, z0, x1, z1, r, n=6):
    pts = []
    for cx, cz, a0 in ((x1 - r, z1 - r, 0), (x0 + r, z1 - r, 90), (x0 + r, z0 + r, 180), (x1 - r, z0 + r, 270)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    return pts


def hub(B):
    (x0, z0), (x1, z1) = HUB_LO, HUB_HI
    (rx0, rz0), (rx1, rz1) = ROOF_LO, ROOF_HI
    B.box("hub_band", (x0, 0.0, z0), (x1, HUB_BAND, z1))
    e = LEDGE
    base = [(x0 + e, z0 + e), (x1 - e, z0 + e), (x1 - e, z1 - e), (x0 + e, z1 - e)]
    top = [(rx0, rz0), (rx1, rz0), (rx1, rz1), (rx0, rz1)]
    pyr = B.loft_y("hub", base, HUB_BAND, top, ROOF_Y)
    # the painted grey roof panel: a 12 cm recess, 0.8 m in from the edge, 1 m corner radius
    i = 0.8
    B.cut(pyr, B.prism_y("roofcut", rounded_rect(rx0 + i, rz0 + i, rx1 - i, rz1 - i, 1.0), ROOF_Y - 0.12, ROOF_Y + 0.05))
    return pyr


def inside_hub(p, margin=0.3):
    """True when a point lies inside the hub (so relief there would be hidden)."""
    x, y, z = p
    if y > ROOF_Y:
        return False
    f = max(0.0, (y - HUB_BAND) / (ROOF_Y - HUB_BAND))
    lo = np.array(HUB_LO) * (1 - f) + np.array(ROOF_LO) * f
    hi = np.array(HUB_HI) * (1 - f) + np.array(ROOF_HI) * f
    return lo[0] + margin < x < hi[0] - margin and lo[1] + margin < z < hi[1] - margin


def tunnel(B, name, axis, s0, s1):
    """A tunnel run along game x or z from s0 to s1 (centred on the other axis)."""
    sec_band = [(-T_HALF, 0.0), (T_HALF, 0.0), (T_HALF, T_BAND), (-T_HALF, T_BAND)]
    sec = [(-T_HALF + LEDGE, T_BAND), (T_HALF - LEDGE, T_BAND), (T_TOP_HALF, T_TOP), (-T_TOP_HALF, T_TOP)]
    if axis == "x":
        B.prism_x(f"{name}_band", [(z, y) for z, y in sec_band], s0, s1)
        return B.prism_x(name, [(z, y) for z, y in sec], s0, s1)
    B.prism_z(f"{name}_band", sec_band, s0, s1)
    return B.prism_z(name, sec, s0, s1)


def rects(D, nm):
    p = D / f"decal_{nm}.json"
    return json.load(open(p))["rects"] if p.exists() else []


def owner(o, tunnels):
    """The tunnel body whose side a slope rect lies on: the one whose axis is across the rect's normal."""
    n = np.array(o["normal"])
    ax = "z" if abs(n[0]) > abs(n[2]) else "x"
    for nm, a in tunnels:
        if a == ax:
            return nm
    return None


def relief(B, D, tunnels, has_hub=True):
    """Slots, pilasters and vents from the decal rects (tools/art/cad_building.py decal, see the scripts)."""
    for s in ("slot0", "slot1", "slot2"):
        for k, o in enumerate(rects(D, s)):
            if has_hub and inside_hub(o["center"], 1.0):
                continue
            # pick the tunnel whose run this slot is on, by its position
            c = np.array(o["center"])
            cands = [nm for nm, a in tunnels if (a == "x" and abs(c[2]) < T_HALF + 0.5) or (a == "z" and abs(c[0]) < T_HALF + 0.5)]
            tgt = owner(o, tunnels) if len(cands) != 1 else cands[0]
            # stop the slot 35 cm short of the hub so no recess wall shows at the junction
            t = np.array(o["t"])
            ks = [k for k in np.linspace(-0.5, 0.5, 101) if not (has_hub and inside_hub(c + t * k * o["w"], -0.35))]
            if len(ks) < 5:
                continue
            a, b = min(ks) * o["w"] + 0.05, max(ks) * o["w"] - 0.05
            B.recess(tgt, dict(o, center=list(c + t * (a + b) / 2), w=b - a, h=0.5), 0.18)
    for s in ("pil0", "pil1"):
        for k, o in enumerate(rects(D, s)):
            if has_hub and inside_hub(o["center"], 0.5):
                continue
            n = np.array(o["normal"])
            B.obox(f"{s}_{k}", np.array(o["center"]) + n * 0.025, o["t"], o["b"], o["normal"], (o["w"] - 0.2, o["h"] - 0.15, 0.1))
    for s in ("vent0", "vent1"):
        for k, o in enumerate(rects(D, s)):
            c = np.array(o["center"])
            t, b = np.array(o["t"]), np.array(o["b"])
            # a low plate under the whole painted white vent, so its louvres stay on top
            w, h = o["w"] * 0.9, o["h"] * 0.9
            lo = c - np.abs(t) * w / 2 - np.abs(b) * h / 2
            hi = c + np.abs(t) * w / 2 + np.abs(b) * h / 2
            nm = B.box(f"{s}_{k}", (lo[0], T_TOP - 0.02, lo[2]), (hi[0], T_TOP + 0.18, hi[2]), chamfer=0.04)
