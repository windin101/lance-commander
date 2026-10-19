#!/usr/bin/env python3
"""Install a CAD-built HD mech (SolidCraft OBJ) on the original mech's skeleton.

    python3 -I tools/art/cad_mech.py vulture ~/craft/solid/mc2/vulture_cad/vulture_hd.obj [--out-dir game/assets/mechs]

Every OBJ object is named "<node>.<piece>__<paint>" (tools/cad/<mech>_hd.py does this). The pieces
become one mesh, each vertex skinned 100% to <node>, so the original model's animations drive it
unchanged (the same rigid skinning hd_rig.py gives a Hunyuan mesh, but exact: no fitting, no guessing
which part a vertex belongs to). Faces are flat-shaded. <paint> picks a block of a small palette
texture, which is also the MechPaint mask: base, hl1 and hl2 are pure blue, red and green, so the
mission's team colours replace them; metal, dark and glass are fixed greys the team paint leaves alone.

Writes <mech>_hd.glb and <mech>_hd_paint.bin, and original/hd/<mech>/provenance.json (kind "cad").
"""
import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hd_rig as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PAINT = {  # MechPaint: pure channels are team paint (value -> shade); the rest keep their colour
    "base": (0, 0, 205), "hl1": (205, 0, 0), "hl2": (0, 205, 0),
    "metal": (112, 115, 122), "dark": (46, 48, 54), "glass": (38, 72, 104),
}
CELL, GRID = 16, 4  # 4 x 4 blocks of 16 px: a 64 px palette


def load_obj(path):
    verts, objs, cur = [], defaultdict(list), None
    for line in open(path):
        if line.startswith("v "):
            verts.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("o "):
            cur = line[2:].strip()
        elif line.startswith("f "):
            idx = [int(t.split("/")[0]) - 1 for t in line.split()[1:]]
            objs[cur].extend([idx[0], idx[k], idx[k + 1]] for k in range(1, len(idx) - 1))
    v = np.array(verts, float) / 1000.0
    return np.c_[v[:, 0], v[:, 2], -v[:, 1]], objs  # SolidCraft mm Z-up -> glTF m Y-up


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mech")
    ap.add_argument("obj")
    ap.add_argument("--out-dir", default=str(ROOT / "game" / "assets" / "mechs"))
    a = ap.parse_args()
    og, ob = R.load_glb(str(ROOT / "game" / "assets" / "mechs" / f"{a.mech}.glb"))
    names = {n.get("name"): i for i, n in enumerate(og["nodes"])}
    verts, objs = load_obj(a.obj)

    slots = {k: i for i, k in enumerate(PAINT)}
    palette = Image.new("RGB", (CELL * GRID, CELL * GRID), (128, 128, 128))
    for k, i in slots.items():
        palette.paste(Image.new("RGB", (CELL, CELL), PAINT[k]), ((i % GRID) * CELL, (i // GRID) * CELL))

    pos, uv, owner, unknown = [], [], [], set()
    counts = defaultdict(int)
    for name, tris in objs.items():
        node_name, _, rest = name.partition(".")
        paint = rest.rpartition("__")[2] if "__" in rest else "base"
        if node_name not in names or paint not in slots:
            unknown.add(name)
            continue
        i = slots[paint]
        u = (((i % GRID) + 0.5) * CELL / (CELL * GRID), ((i // GRID) + 0.5) * CELL / (CELL * GRID))
        tv = verts[np.array(tris).reshape(-1)]          # unshared: flat shading
        pos.append(tv)
        uv.append(np.tile(u, (len(tv), 1)))
        owner.append(np.full(len(tv), names[node_name]))
        counts[node_name] += len(tris)
    if unknown:
        raise SystemExit(f"objects with no matching node or paint: {sorted(unknown)[:10]}")
    pos, uv, owner = np.concatenate(pos), np.concatenate(uv), np.concatenate(owner)
    tris = np.arange(len(pos)).reshape(-1, 3)
    normals = R.vertex_normals(pos, tris)

    joints = sorted(set(owner.tolist()))
    slot = {n: i for i, n in enumerate(joints)}
    worlds = R.world_matrices(og)
    w = R.GlbWriter(og, ob)
    for node in og["nodes"]:
        node.pop("mesh", None)  # the original low-poly parts are replaced
    attrs = {
        "POSITION": w.accessor(pos, "VEC3", target=34962, minmax=True),
        "NORMAL": w.accessor(normals, "VEC3", target=34962),
        "TEXCOORD_0": w.accessor(uv, "VEC2", target=34962),
        "JOINTS_0": w.accessor(np.c_[[slot[o] for o in owner], np.zeros((len(owner), 3))], "VEC4", comp=5123, target=34962),
        "WEIGHTS_0": w.accessor(np.c_[np.ones(len(owner)), np.zeros((len(owner), 3))], "VEC4", target=34962),
    }
    ind = w.accessor(tris.reshape(-1).astype(np.uint32), "SCALAR", comp=5125, target=34963)
    tex = w.image(R.png_bytes(palette))
    og.setdefault("samplers", []).append({"magFilter": 9728, "minFilter": 9728})  # nearest: crisp palette blocks
    og.setdefault("textures", [])
    og["textures"][-1]["sampler"] = len(og["samplers"]) - 1
    og.setdefault("materials", []).append({"name": "hd_cad", "pbrMetallicRoughness": {
        "baseColorTexture": {"index": tex}, "metallicFactor": 0.35, "roughnessFactor": 0.55}})
    og["meshes"].append({"name": "hd_body", "primitives": [{"attributes": attrs, "indices": ind, "material": len(og["materials"]) - 1}]})
    ibm = np.stack([np.linalg.inv(worlds[j]).T.reshape(-1) for j in joints])
    og.setdefault("skins", []).append({"joints": joints, "inverseBindMatrices": w.accessor(ibm, "MAT4")})
    og["nodes"].append({"name": "hd_body", "mesh": len(og["meshes"]) - 1, "skin": len(og["skins"]) - 1})
    og["scenes"][0]["nodes"].append(len(og["nodes"]) - 1)

    out = Path(a.out_dir)
    w.write(str(out / f"{a.mech}_hd.glb"))
    (out / f"{a.mech}_hd_paint.bin").write_bytes(R.png_bytes(palette))
    work = ROOT / "original" / "hd" / a.mech
    work.mkdir(parents=True, exist_ok=True)
    prov = {"asset": a.mech, "kind": "cad", "source": str(a.obj), "parts": dict(counts), "tris": len(tris),
            "built_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (work / "provenance.json").write_text(json.dumps(prov, indent=2) + "\n")
    print(f"wrote {out / (a.mech + '_hd.glb')}: {len(tris)} tris on {len(joints)} parts; "
          + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
