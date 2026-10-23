#!/usr/bin/env python3
"""HD rework (v2, 2026-10-23) of a CAD-rebuilt map building: tiling PBR materials by region plus baked AO.

    CAD_ARC_SEGMENTS=96 python3 -I tools/cad/<app>_cad.py <openings.json> > <dir>/<app>.json
    solidcraft-cli run <dir>/<app>.json --out <dir>/<app>.obj
    python3 -I tools/art/hd_v2_building.py <app> <dir>/<app>.obj --openings <openings.json> [--work DIR] [--texel 0.02]

The v1 rebuild (tools/art/cad_building.py) baked the original's 128 px art, upscaled, onto the CAD model, so the
walls read as blurred, stretched pixels. Here every face gets a surface type instead, from its CAD body and where it
lies: the corrugated hull is galvanised sheet ("sheet"), the flat end walls painted boards ("panel"), window
recess backs glass, door recess backs a painted door, recess sides and the ribs, sills and hoods painted steel
("trim"), steps concrete. Each type is a tiling set from tools/art/hd_v2_textures.py (game/assets/v2/shared/,
one tile = 2 m; the hull's UVs run along its arc, so streaks run down the curve). A second UV set (the v1 chart
packer) carries an ambient-occlusion bake (Blender Cycles). Output, staged for ArtV2 (never over the installed
_cad.glb): game/assets/v2/objects/<app>.glb (one primitive per surface type, material "v2_<type>"),
<app>_ao.png. ArtV2.dress_object swaps the materials for res://shaders/building_hd.gdshader at load.
Geometry and these textures are new work; the model's dimensions are measured from the Shared Source original,
so the building stays under that release's non-commercial terms.
"""
import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cad_building as CB  # noqa: E402
import hd_rig as R          # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TYPES = ("sheet", "panel", "concrete", "trim", "door", "glass")


def classify(v, faces, body, names, openings):
    fv = v[faces]
    c = fv.mean(1)
    n = np.cross(fv[:, 1] - fv[:, 0], fv[:, 2] - fv[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    t = np.zeros(len(faces), int)
    nm = np.array([names[b].split("@")[0] for b in body])
    hull = nm == "hull"
    t[hull] = TYPES.index("sheet")
    t[hull & (np.abs(n[:, 2]) > 0.95)] = TYPES.index("panel")
    for pre, ty in (("rib", "trim"), ("sill", "trim"), ("hood", "trim"), ("step", "concrete"), ("frame", "trim")):
        t[np.char.startswith(nm, pre)] = TYPES.index(ty)
    for o in openings:
        C, N, T, B = (np.asarray(o[k], float) for k in ("center", "normal", "t", "b"))
        rel = c - C
        inside = (np.abs(rel @ T) < o["w"] / 2 + 0.02) & (np.abs(rel @ B) < o["h"] / 2 + 0.02) & (rel @ N > -0.7) & (rel @ N < 0.05)
        end = abs(N[2]) > 0.9
        door = end and o["h"] > 1.5
        back = inside & hull & ((n @ N) > 0.9)
        side = inside & hull & (np.abs(n @ N) < 0.3)
        t[back] = TYPES.index("door" if door else "glass")
        t[side] = TYPES.index("trim")
    return t, n


def tiling_uv(v, faces, t, n):
    """Per corner, metres / 2. Hull sheet: along z and around the arc (theta about the ground axis); else box map."""
    fv = v[faces]
    uv = np.zeros((len(faces), 3, 2))
    sheet = t == TYPES.index("sheet")
    r = np.hypot(fv[..., 0], fv[..., 1])
    th = np.arctan2(fv[..., 1], fv[..., 0])
    uv[sheet, :, 0] = fv[sheet, :, 2] / 2.0
    uv[sheet, :, 1] = (np.pi / 2 - th[sheet]) * r[sheet].mean(1, keepdims=True) / 2.0
    ax = np.abs(n).argmax(1)
    for f in np.flatnonzero(~sheet):
        a, b = CB.PLANE_AXES[ax[f]]
        uv[f] = fv[f][:, [a, b]] / 2.0
        uv[f, :, 1] *= -1
    return uv


def write_glb(path, v, faces, t, nrm, uv0, uv1, app):
    """One node, one mesh, a primitive per surface type (material v2_<type>), glTF metres Y up."""
    g = {"asset": {"version": "2.0", "generator": "tools/art/hd_v2_building.py"}, "scenes": [{"nodes": [0]}], "scene": 0,
         "nodes": [{"name": app, "mesh": 0}], "meshes": [{"name": app, "primitives": []}], "materials": [],
         "buffers": [], "bufferViews": [], "accessors": []}
    w = R.GlbWriter(g, bytearray())
    for k, ty in enumerate(TYPES):
        sel = np.flatnonzero(t == k)
        if not len(sel):
            continue
        P = v[faces[sel]].reshape(-1, 3)
        N = nrm[sel].reshape(-1, 3)
        U0 = uv0[sel].reshape(-1, 2)
        U1 = uv1[sel].reshape(-1, 2)
        key = np.c_[np.round(P, 5), np.round(N, 3), np.round(U0, 5), np.round(U1, 5)]
        _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
        idx = inv.ravel().astype(np.uint32)
        g["materials"].append({"name": f"v2_{ty}", "pbrMetallicRoughness": {"baseColorFactor": [0.6, 0.6, 0.6, 1],
                               "metallicFactor": 0.0, "roughnessFactor": 0.8}})
        g["meshes"][0]["primitives"].append({"attributes": {
            "POSITION": w.accessor(P[first].astype(np.float32), "VEC3", target=34962, minmax=True),
            "NORMAL": w.accessor(N[first].astype(np.float32), "VEC3", target=34962),
            "TEXCOORD_0": w.accessor(U0[first].astype(np.float32), "VEC2", target=34962),
            "TEXCOORD_1": w.accessor(U1[first].astype(np.float32), "VEC2", target=34962)},
            "indices": w.accessor(idx, "SCALAR", comp=5125, target=34963), "material": len(g["materials"]) - 1})
    w.write(str(path))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("app")
    ap.add_argument("obj")
    ap.add_argument("--openings", required=True)
    ap.add_argument("--work")
    ap.add_argument("--texel", type=float, default=0.02)
    ap.add_argument("--samples", type=int, default=96)
    a = ap.parse_args()
    work = Path(a.work or f"/mnt/nvme1n1p1/mc2-rework/work/{a.app}")
    work.mkdir(parents=True, exist_ok=True)
    v, faces, body, names = CB.load_obj(a.obj)
    v, faces = CB.weld(v, faces)
    hide = CB.hidden_faces(v, faces, body)
    faces, body = faces[~hide], body[~hide]
    openings = json.loads(Path(a.openings).read_text())["openings"]
    t, n = classify(v, faces, body, names, openings)
    share = np.bincount(t, minlength=len(TYPES)) / len(t)
    print(f"{a.app}: {len(faces)} faces ({hide.sum()} hidden dropped); " + ", ".join(f"{ty} {share[i]:.2f}" for i, ty in enumerate(TYPES)))
    nrm = CB.smooth_normals(v, faces, 30.0)
    uv0 = tiling_uv(v, faces, t, n)
    cid, ax = CB.charts(v, faces)
    texel, packed, res = a.texel, None, 1024
    while packed is None:
        packed = CB.pack(v, faces, cid, ax, texel, res)
        texel *= 1.08
    uv1, used = packed
    uv1 = uv1 * [1, -1] + [0, 1]   # glTF v runs down
    print(f"  AO atlas {res} px at {texel / 1.08 * 100:.1f} cm a texel ({used * 100:.0f} % of the height used)")
    # AO bake in Blender on the second UV set (Z up mm for the shared script's frame)
    Pz = np.c_[v[:, 0], -v[:, 2], v[:, 1]] * 1000.0
    Nz = np.stack([nrm[..., 0], -nrm[..., 2], nrm[..., 1]], -1)
    uvb = np.stack([uv1[..., 0], 1 - uv1[..., 1]], -1)   # Blender v up
    np.savez_compressed(work / "rest.npz", P=Pz, F=faces, part=np.zeros(len(faces), int), kind=t, N=Nz, UV=uvb.reshape(-1, 2))
    cmd = ["blender", "-b", "--factory-startup", "--python", str(ROOT / "tools/art/hd_v2_blender.py"), "--",
           "bakeao", str(work / "rest.npz"), str(work), "--tex", str(res), "--samples", str(a.samples), "--ao_dist", "3.0"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not (work / "bake_ao.png").exists():
        raise SystemExit("AO bake failed:\n" + r.stdout[-1500:] + r.stderr[-1500:])
    from PIL import Image
    ao = np.asarray(Image.open(work / "bake_ao.png").convert("L"))
    cover = np.load(work / "bake_cover.npy")
    import hd_v2
    ao = hd_v2.dilate(ao[..., None], cover)[..., 0]
    dst = ROOT / "game/assets/v2/objects"
    dst.mkdir(parents=True, exist_ok=True)
    Image.fromarray(ao).save(dst / f"{a.app}_ao.png", optimize=True)
    imp = dst / f"{a.app}_ao.png.import"
    if not imp.exists():
        imp.write_text(hd_v2.TEX_IMPORT.format(normal=0))
    write_glb(dst / f"{a.app}.glb", v, faces, t, nrm, uv0, uv1, a.app)
    (dst / f"{a.app}.v2.json").write_text(json.dumps({"app": a.app, "made_by": "tools/art/hd_v2_building.py", "obj": a.obj,
        "tris": int(len(faces)), "types": {ty: round(float(share[i]), 3) for i, ty in enumerate(TYPES)},
        "ao_px": res, "licence": "MC2 Shared Source terms (dimensions from the original); textures new work"}, indent=1) + "\n")
    print(f"  -> {dst}/{a.app}.glb, {a.app}_ao.png")


if __name__ == "__main__":
    main()
