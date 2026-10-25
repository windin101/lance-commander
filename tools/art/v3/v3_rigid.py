#!/usr/bin/env python3
"""Rigid units for Pipeline A (v3): copters now, vehicles next (2026-10-25).

    python3 -I tools/art/v3/v3_rigid.py <unit> --stl A.stl [--stl B.stl] --joints tools/art/v3/<unit>_veh.json
        [--kind mechs|vehicles]

Fits a licensed kit to the MC2 model with tools/art/stl_hd.py exactly as the approved v1 build did (its "joints"
settings: mounts, part boxes, yaw, scale), but captures stl_hd's state before it simplifies or writes anything
(the same capture hd_v2's fitveh uses): the full-resolution fitted triangles, the MC2 part each one rides, and the
original's node tree. Those are written as a v2-style work dir, /mnt/nvme1n1p1/mc2-rework/work/<unit>_rigid:

  labels.npz  V, F (game rest frame, mm, Z up), lab (node index per face)
  fit.json    node_names, parent, xform (identity per part node: the sculpt is already in the rest pose), k, H
  skel.glb    the original's node tree and animations, meshes and images dropped

so tools/art/v3/v3_mech.py runs on it with "from_v2" and "rigid": true (no ground drop, no leg regrow, no actuators,
no ground fix in the write stage) and every later stage (segment, lowpoly, bake, paint, write, review) is shared
with the mechs. Node names stay the original's, so its animations (rotor spin on Joint_bladerot, flight on
joint_root) and weapon nodes keep working.
"""
import argparse
import inspect
import json
import sys
from pathlib import Path

import numpy as np

ART = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ART))
import hd_rig as R  # noqa: E402
import stl_hd as SH  # noqa: E402
import stl_rig  # noqa: E402


def weld(T, dec=2):
    V, inv = np.unique(np.round(T.reshape(-1, 3), dec), axis=0, return_inverse=True)
    F = inv.reshape(-1, 3)
    good = (F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])
    return V, F, good


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("unit")
    ap.add_argument("--stl", action="append", required=True)
    ap.add_argument("--joints", required=True)
    ap.add_argument("--kind", default="mechs")
    a = ap.parse_args()
    work = Path(f"/mnt/nvme1n1p1/mc2-rework/work/{a.unit}_rigid"); work.mkdir(parents=True, exist_ok=True)
    cap = {}

    def capture(og, ob, pos, normals, uv, owner, tris, slots, dest, mech):
        cap.update(inspect.currentframe().f_back.f_locals)
    o_cluster, o_write = SH.cluster, stl_rig.write
    SH.cluster = lambda T, faces: (T, 0.0)      # keep the kit at full resolution: it is the bake source
    stl_rig.write = capture
    argv = sys.argv
    sys.argv = ["stl_hd.py", a.unit, "--kind", a.kind, "--joints", a.joints] + sum((["--stl", s] for s in a.stl), [])
    try:
        SH.main()
    finally:
        sys.argv = argv; SH.cluster, stl_rig.write = o_cluster, o_write
    Gf, owner, og, ob = cap["Gf"], np.asarray(cap["owner"], int), cap["og"], cap["ob"]
    Pmm = np.stack([Gf[..., 0], -Gf[..., 2], Gf[..., 1]], -1) * 1000.0      # glTF m -> game mm, Z up
    V, F, good = weld(Pmm)
    F, lab = F[good], owner[good]
    names = [n.get("name", "") for n in og["nodes"]]
    for n in og["nodes"]:
        n.pop("mesh", None); n.pop("skin", None)
    for k in ("images", "textures", "samplers", "materials", "meshes", "skins"):   # no Shared Source art in the copy
        og.pop(k, None)
    R.GlbWriter(og, ob).write(str(work / "skel.glb"))
    parent = {str(c): i for i, n in enumerate(og["nodes"]) for c in n.get("children", [])}
    parts = sorted(set(lab.tolist()))
    np.savez_compressed(work / "labels.npz", V=V, F=F, lab=lab)
    (work / "fit.json").write_text(json.dumps({
        "mech": a.unit, "stl": a.stl, "joints": a.joints, "kind": "rigid", "node_names": names, "parent": parent,
        "xform": {str(p): np.eye(4).tolist() for p in parts}, "pivots": {}, "legs": {}, "keys": [],
        "k": 1.0, "H": float(V[:, 2].max())}, indent=1))
    print(f"rigid fit: {len(F)} tris, parts {[names[p] for p in parts]} -> {work}")


if __name__ == "__main__":
    main()
