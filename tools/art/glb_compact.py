#!/usr/bin/env python3
"""Shrink a rigidly skinned HD .glb without changing what it renders.

    python3 -I tools/art/glb_compact.py game/assets/mechs/<asset>_hd.glb [...]

The stl_rig.py / stl_hd.py writers store three unshared vertices per triangle (flat shading) with float
weights and 16-bit joint indices. This welds vertices that are identical in position, normal, UV and joint,
stores JOINTS_0 as unsigned bytes and WEIGHTS_0 as normalized unsigned bytes (core glTF 2.0), and repacks
the binary chunk so only referenced data is kept. Typically about half the size. Idempotent.
"""
import json
import struct
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hd_rig as R  # noqa: E402


def compact(path):
    path = Path(path)
    before = path.stat().st_size
    g, b = R.load_glb(str(path))
    for mesh in g["meshes"]:
        if mesh.get("name") != "hd_body":
            continue
        pr = mesh["primitives"][0]
        at = pr["attributes"]
        P, N, U = (R.read_accessor(g, b, at[k]).astype(np.float32) for k in ("POSITION", "NORMAL", "TEXCOORD_0"))
        J = R.read_accessor(g, b, at["JOINTS_0"]).astype(np.uint16)
        I = R.read_accessor(g, b, pr["indices"]).astype(np.int64)
        key = np.ascontiguousarray(np.c_[P, N, U, J[:, :1].astype(np.float32)]).view(np.dtype((np.void, 4 * 9)))[:, 0]
        uk, first, inv = np.unique(key, return_index=True, return_inverse=True)
        P, N, U, J = P[first], N[first], U[first], J[first]
        I = inv[I]
        W = np.zeros((len(P), 4), np.uint8); W[:, 0] = 255
        joints8 = J.astype(np.uint8) if J.max() < 256 else None
        new = []

        def add(arr, kind, comp, target, normalized=False, minmax=False):
            new.append((arr, kind, comp, target, normalized, minmax))
            return len(new) - 1
        ids = {"POSITION": add(P, "VEC3", 5126, 34962, minmax=True), "NORMAL": add(N, "VEC3", 5126, 34962),
               "TEXCOORD_0": add(U, "VEC2", 5126, 34962),
               "JOINTS_0": add(joints8 if joints8 is not None else J, "VEC4", 5121 if joints8 is not None else 5123, 34962),
               "WEIGHTS_0": add(W, "VEC4", 5121, 34962, normalized=True)}
        idx = add(I.astype(np.uint32), "SCALAR", 5125, 34963)
        base = len(g["accessors"])
        for arr, kind, comp, target, normalized, minmax in new:
            a = np.ascontiguousarray(arr)
            g["bufferViews"].append({"buffer": 0, "byteOffset": 0, "byteLength": a.nbytes, "target": target, "_data": a.tobytes()})
            acc = {"bufferView": len(g["bufferViews"]) - 1, "componentType": comp, "count": int(a.shape[0]), "type": kind}
            if normalized:
                acc["normalized"] = True
            if minmax:
                acc["min"], acc["max"] = a.min(0).tolist(), a.max(0).tolist()
            g["accessors"].append(acc)
        pr["attributes"] = {k: base + v for k, v in ids.items()}
        pr["indices"] = base + idx
    # repack: keep only referenced accessors' views and images' views, in order
    used_acc = set()
    for m in g["meshes"]:
        for pr in m["primitives"]:
            used_acc.update(pr["attributes"].values()); used_acc.add(pr.get("indices"))
            for t in pr.get("targets", []):
                used_acc.update(t.values())
    for an in g.get("animations", []):
        for s in an["samplers"]:
            used_acc.update((s["input"], s["output"]))
    for sk in g.get("skins", []):
        if "inverseBindMatrices" in sk:
            used_acc.add(sk["inverseBindMatrices"])
    used_acc.discard(None)
    acc_map = {old: new for new, old in enumerate(sorted(used_acc))}
    accs = [g["accessors"][i] for i in sorted(used_acc)]
    used_view = sorted({a["bufferView"] for a in accs if "bufferView" in a} | {im["bufferView"] for im in g.get("images", []) if "bufferView" in im})
    view_map = {old: new for new, old in enumerate(used_view)}
    out = bytearray()
    views = []
    for old in used_view:
        v = dict(g["bufferViews"][old])
        data = v.pop("_data", None)
        if data is None:
            off = v.get("byteOffset", 0)
            data = bytes(b[off:off + v["byteLength"]])
        while len(out) % 4:
            out += b"\0"
        v["byteOffset"] = len(out)
        out += data
        views.append(v)
    for a in accs:
        if "bufferView" in a:
            a["bufferView"] = view_map[a["bufferView"]]
    for im in g.get("images", []):
        if "bufferView" in im:
            im["bufferView"] = view_map[im["bufferView"]]
    g["accessors"], g["bufferViews"] = accs, views
    for m in g["meshes"]:
        for pr in m["primitives"]:
            pr["attributes"] = {k: acc_map[v] for k, v in pr["attributes"].items()}
            if "indices" in pr:
                pr["indices"] = acc_map[pr["indices"]]
            for t in pr.get("targets", []):
                for k in t:
                    t[k] = acc_map[t[k]]
    for an in g.get("animations", []):
        for s in an["samplers"]:
            s["input"], s["output"] = acc_map[s["input"]], acc_map[s["output"]]
    for sk in g.get("skins", []):
        if "inverseBindMatrices" in sk:
            sk["inverseBindMatrices"] = acc_map[sk["inverseBindMatrices"]]
    while len(out) % 4:
        out += b"\0"
    g["buffers"] = [{"byteLength": len(out)}]
    js = json.dumps(g, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    path.write_bytes(struct.pack("<III", 0x46546C67, 2, 28 + len(js) + len(out)) + struct.pack("<II", len(js), 0x4E4F534A) + js
                     + struct.pack("<II", len(out), 0x004E4942) + bytes(out))
    return before, path.stat().st_size


if __name__ == "__main__":
    for p in sys.argv[1:]:
        a, b_ = compact(p)
        print(f"{p}: {a / 1e6:.1f} -> {b_ / 1e6:.1f} MB")
