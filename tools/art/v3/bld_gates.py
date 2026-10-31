#!/usr/bin/env python3
"""v3 gates (LANCE-21): s_/l_/d_ light, medium and heavy gates, three states, LOD0/LOD1, with a moving door.

    python3 -I tools/art/v3/bld_gates.py <app>|all

The original gates (class 22) are 55 m across the wall line (local z -27.7..27.7): wall sections with end posts, a gate post either side of a
13.8 m opening, a lintel and two sliding door leaves. The door leaves are separate glTF nodes "door_l" and "door_r" at their closed positions; the
game slides them along z (ObjectsView.set_gate_open) when the sim opens the gate. Panel styles follow the walls: s plain slabs, l diagonal braces,
d a hexagon lattice band. Destroyed: no door nodes, the opening is clear, rubble and stubs.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bld_hangars as H  # noqa: E402
import bld_walls as W  # noqa: E402
from bld_hangars import Ctx, V, TAU, axis_angle, clad, torn, ridge_keep, ROOT  # noqa: E402
from bld_mesh import Builder  # noqa: E402

END, GAP = 27.7, 6.9
STATES = ("intact", "damaged", "destroyed")


def gate(h_body, h_post, post_w, half_w, door_h, mat, style):
    def build(state, lod, seed):
        c = Ctx(state, lod, seed, breach=(0.0, h_body * 0.5, 14.0, 3.0), ledges=[(h_body, 2.0, 0.8)], ground_h=2.0)
        dl, dr = Ctx(state, lod, seed + 5), Ctx(state, lod, seed + 6)
        b = c.b
        fine = c.fine
        dst, dmg = state == "destroyed", state == "damaged"
        rng = c.rng
        b.box("concrete_dark", (0, 0.2, 0), (2 * half_w + 1.0, 0.4, 2 * END + 1.0))
        for sgn in (-1, 1):
            zin, zout = GAP + 3.0, END - 3.5          # body between the gate post and the end post
            lo, hi = (zin, zout) if sgn > 0 else (-zout, -zin)
            # side wall body: two faces of large panels over a battered base
            tear = torn((hi - lo) * 0.5, h_body * 0.5, 2.6, h_body * 0.3, 0.4) if (dmg and sgn > 0) else None
            kd = ridge_keep(hi - lo, h_body, rng, 0.1, 0.5, 0.1) if dst else None
            for fx in (-1, 1):
                zA, dz = (lo, (0, 0, 1)) if fx < 0 else (hi, (0, 0, -1))
                clad(c, mat, (fx * half_w, 0.4, zA), dz, hi - lo, (0, 1, 0), h_body - 0.4, (fx, 0, 0), "flat", extra=tear or kd, thick=0.16, edge_mat="rust",
                     tear_disp=H.curl(0, 0, 1, 1, 0.12) if tear else None, v_extra=(h_body * 0.3, h_body * 0.7) if tear else ())
                if fine and not dst:
                    skip = (lambda u, v, t=tear: t(u, v)) if tear else None
                    W.panel_face(c, fx, lo, hi, 0.9, h_body, half_w, style, skip, lambda z: h_body, mat)
            if not dst:
                b.box(mat, (0, h_body + 0.12, (lo + hi) / 2), (2 * half_w + 0.5, 0.24, hi - lo + 0.2))
            # end post and gate post (taller), each a battered block with a cap
            for zc, hp, wid in ((sgn * (END - 1.8), h_post, post_w), (sgn * (GAP + 1.5), h_post * 1.08, post_w)):
                hh = hp if not dst else hp * 0.35
                for fx in (-1, 1):
                    clad(c, mat, (fx * wid / 2, 0.4, zc - 1.8), (0, 0, 1), 3.6, (0, 1, 0), hh - 0.4, (fx, 0, 0), "flat", thick=0.1, extra=(lambda u, v, hh=hh: hh * (0.5 + 0.5 * np.abs(np.sin(np.asarray(u) * 1.7))) - np.asarray(v)) if dst else None)
                for zz, nz in ((zc - 1.8, -1), (zc + 1.8, 1)):
                    clad(c, mat, (wid / 2 if nz < 0 else -wid / 2, 0.4, zz), (-1, 0, 0) if nz < 0 else (1, 0, 0), wid, (0, 1, 0), hh - 0.4, (0, 0, nz), "flat", thick=0.1)
                if not dst:
                    b.box(mat, (0, hp + 0.15, zc), (wid + 0.6, 0.3, 4.2))
                    if style == "l":
                        b.revolve(mat, [(wid * 0.7, hp + 0.3), (wid * 0.4, hp + 0.9), (wid * 0.28, hp + 1.2)], 4, th0=math.pi / 4, cz=zc, uref=2.0)
                    elif style == "d":
                        b.box(mat, (0, hp + 0.5, zc), (wid - 0.6, 0.4, 3.0))
        # lintel across the opening
        if not dst:
            b.box(mat, (0, (door_h + h_body) / 2 + 0.2, 0), (2 * half_w + 0.4, h_body - door_h, 2 * GAP + 0.4))
            b.box(mat, (0, h_body + 0.15, 0), (2 * half_w + 0.6, 0.3, 2 * GAP + 0.6))
            b.quad("trim", V([half_w + 0.2, (door_h + h_body) / 2 + 0.2, 0]), V([0, 0, 1.0]), V([0, 1.0, 0]), 2 * GAP, min(0.9, h_body - door_h - 0.3), (0, 0.5, 2 * GAP * 0.3, 0), normal=(1, 0, 0), band=6, col=(1, 0, 0))
        # sliding door leaves: separate nodes "door_l" (z < 0) and "door_r" (z > 0), built at their closed positions
        if not dst:
            for sgn, dc in ((-1, dl), (1, dr)):
                db = dc.b
                z0, z1 = (0.0, GAP) if sgn > 0 else (-GAP, 0.0)
                zc = (z0 + z1) / 2
                db.box("steel", (0, door_h / 2 + 0.2, zc), (0.7, door_h, GAP - 0.1))
                n = int(door_h / 0.5) if fine else 3
                for k in range(n):
                    yy = 0.5 + k * (door_h / n)
                    db.box("galv", (0.38, yy, zc), (0.1, 0.12, GAP - 0.4))
                    db.box("galv", (-0.38, yy, zc), (0.1, 0.12, GAP - 0.4))
                db.quad("trim", V([0.44, door_h * 0.5 + 0.2, zc]), V([0, 0, 1.0]), V([0, 1.0, 0]), GAP - 0.6, 0.9, (0, 0.5, (GAP - 0.6) * 0.3, 0), normal=(1, 0, 0), band=0)
                if dmg and sgn > 0:
                    db.box("rust", (0.45, door_h * 0.5, zc), (0.1, door_h * 0.4, 1.6), axis_angle(V([1.0, 0, 0]), 0.2))
        if dmg:
            for k in range(8 if fine else 3):
                b.box("concrete", (rng.uniform(-half_w * 1.6, half_w * 1.6), 0.4, rng.uniform(8, 20)), (1.0, 0.7, 1.1), axis_angle(V([0, 1.0, 0]), rng.random() * 3))
            c.decal_ground("soot", (0, 14), 8, 9, 0.0, y=0.45)
        if dst:
            for k in range(14 if fine else 5):
                zc = rng.choice([-1, 1]) * rng.uniform(GAP + 2, END - 1)
                b.box("concrete", (rng.uniform(-half_w * 1.8, half_w * 1.8), 0.5, zc), (rng.uniform(1.0, 2.4), rng.uniform(0.6, 1.2), rng.uniform(1.0, 2.2)), axis_angle(V([0, 1.0, 0]), rng.random() * 3))
            for sgn in (-1, 1):
                b.box("steel", (0.5, 0.3, sgn * 3.2), (0.6, 0.35, 5.2), axis_angle(V([1.0, 0, 0]), sgn * 0.25))
            c.decal_ground("soot", (0, 0), 14, 56, 0.0, y=0.45)
        return c, dl, dr
    return build


SPECS = {}
for fac, mat in (("s", "wallconc"), ("l", "wallfacade"), ("d", "wallconc2")):
    SPECS[f"{fac}_lightgate"] = gate(3.5, 4.46, 4.0, 2.0, 4.0, mat, fac)
    SPECS[f"{fac}_mediumgate"] = gate(9.6, 10.2, 6.0, 3.0, 6.5, mat, fac)
    SPECS[f"{fac}_heavygate"] = gate(17.2, 19.0 if fac == "s" else 16.0, 6.0, 3.0, 9.0, mat, fac)


def build_member(app, out):
    fn = SPECS[app]
    info = {"app": app, "made_by": "tools/art/v3/bld_gates.py", "states": {}}
    for si, state in enumerate(STATES):
        res = []
        for lod in (0, 1):
            res.append(fn(state, lod, 5100 + si + sum(map(ord, app))))
        builders = [res[0][0].b, res[1][0].b]
        names = ["lod0", "lod1"]
        if state != "destroyed":
            builders += [res[0][1].b, res[0][2].b]
            names += ["door_l", "door_r"]
        name = app + ("" if state == "intact" else "_" + state)
        st = Builder.write_lods(out / f"{name}.glb", name, builders, names)
        P = np.vstack([v for s_ in res[0][0].b.s.values() for v in s_["P"]])
        info["states"][state] = {"tris_lod0": int(sum(st[0].values())), "tris_lod1": int(sum(st[1].values())),
                                 "bounds_min": np.round(P.min(0), 2).tolist(), "bounds_max": np.round(P.max(0), 2).tolist()}
        print(app, state, info["states"][state]["tris_lod0"], info["states"][state]["tris_lod1"], info["states"][state]["bounds_min"], info["states"][state]["bounds_max"], flush=True)
    (out / f"{app}.v3.json").write_text(json.dumps(info, indent=1) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("app")
    ap.add_argument("--out", default=str(ROOT / "game/assets/v3/objects"))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    for app in (list(SPECS) if a.app == "all" else [a.app]):
        build_member(app, out)


if __name__ == "__main__":
    main()
