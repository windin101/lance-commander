#!/usr/bin/env python3
"""Canopy glass by hand pick (HD rework v2.1, 2026-10-24). Transferring the window from the original model fails:
the sculpts' shapes differ. Instead the sculpt's own window panels are offered as numbered candidates, Lee picks
the numbers (or colours the window roughly on an unmarked sheet), and the pick is stored in the mech's v2 config
as canopy_patches (patch points), so a rebuild reproduces it.

    python3 -I tools/art/canopy_pick.py sheet MECH            # candidates + unmarked sheet -> review/canopy_pick/
    python3 -I tools/art/canopy_pick.py pick MECH 3 5 7       # store candidates 3, 5, 7 in tools/art/hd_v2/MECH.json
    python3 -I tools/art/canopy_pick.py paint MECH marked.png # back-project a rough colouring of the unmarked sheet
                                                              # (pure-ish blue strokes) and store the patches it covers

All views are orthographic in the rig's rest frame (forward -Y, up +Z), centred on the cockpit node: front, 3/4
front (from the mech's left) and top. Patches are the sculpt's planar regions bounded by edges sharper than 20
degrees (the kits model windows as distinct panels). Needs <work>/rest.npz from hd_v2.py's segment stage.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hd_rig as R    # noqa: E402
import hd_v2 as H     # noqa: E402
import stl_rig as S   # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WORK = Path("/mnt/nvme1n1p1/mc2-rework/work")
OUT = Path("/mnt/nvme1n1p1/mc2-rework/review/canopy_pick")
DEG = 20.0
VIEWS = (("front", (0, -1, 0.08)), ("front34", (0.62, -0.75, 0.25)), ("top", (0, -0.2, 1)))
PALETTE = [(1, 0, 1), (0, 0.8, 1), (1, 0.6, 0), (0.2, 1, 0.2), (1, 0.15, 0.15), (0.3, 0.3, 1), (1, 1, 0), (0.6, 0.2, 1),
           (0, 1, 0.6), (1, 0.4, 0.7)]

BLENDER = r'''
import bpy, sys, json, numpy as np
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
a = sys.argv[sys.argv.index("--") + 1:]
z = np.load(a[0]); out = a[1]; mode = a[2]
bpy.ops.wm.read_factory_settings(use_empty=True); scn = bpy.context.scene
P = z["P"] / 1000.0; F = z["F"]
me = bpy.data.meshes.new("m"); me.from_pydata(P.tolist(), [], F.tolist())
C = z["C"]
ca = me.color_attributes.new("c", "FLOAT_COLOR", "CORNER")
ca.data.foreach_set("color", np.repeat(np.c_[C, np.ones(len(C))], 3, 0).astype(np.float32).ravel())
me.color_attributes.active_color = ca
ob = bpy.data.objects.new("m", me); scn.collection.objects.link(ob)
scn.render.engine = "BLENDER_WORKBENCH"; sh = scn.display.shading
if mode == "id":
    sh.light = "FLAT"; sh.show_cavity = False; scn.display.render_aa = "OFF"
else:
    sh.light = "STUDIO"; sh.show_cavity = True
sh.color_type = "VERTEX"; scn.view_settings.view_transform = "Standard"; scn.view_settings.look = "None"
scn.world = bpy.data.worlds.new("w"); scn.render.resolution_x = scn.render.resolution_y = 1000
cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); scn.collection.objects.link(cam); scn.camera = cam
cam.data.type = "ORTHO"; cam.data.ortho_scale = float(z["scale"]) / 1000.0; cam.data.clip_end = 300
tgt = Vector((z["target"] / 1000.0).tolist())
labels = {}
for name, d in json.loads(a[3]):
    dv = Vector(d).normalized(); cam.location = tgt + dv * 60
    cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y" if name == "top" else "Z").to_euler()
    bpy.context.view_layer.update()
    scn.render.filepath = f"{out}_{name}.png"; bpy.ops.render.render(write_still=True)
    labels[name] = [[float(c) for c in world_to_camera_view(scn, cam, Vector((p / 1000.0).tolist()))[:2]] for p in z["label_pts"]]
    labels["_cam_" + name] = [list(r) for r in cam.matrix_world]
labels["_ortho"] = cam.data.ortho_scale
json.dump(labels, open(out + "_labels.json", "w"))
print("DONE")
'''


def run_blender(npz, out, mode):
    script = OUT / "_render.py"
    script.write_text(BLENDER)
    r = subprocess.run(["blender", "-b", "--factory-startup", "--python", str(script), "--", str(npz), str(out), mode,
                        json.dumps(VIEWS)], capture_output=True, text=True)
    if "DONE" not in r.stdout:
        raise SystemExit(r.stdout[-1500:] + r.stderr[-1500:])
    return json.loads(Path(f"{out}_labels.json").read_text())


def load(mech):
    w = WORK / mech
    z = np.load(w / "rest.npz")
    fit = json.loads((w / "fit.json").read_text())
    sk, sb = R.load_glb(str(w / "skel.glb"))
    Wm = R.world_matrices(sk)
    nodes = {n.get("name", ""): i for i, n in enumerate(sk["nodes"])}
    if "cockpit" in nodes:
        ck = S.sc(Wm[nodes["cockpit"]][:3, 3])
    else:
        P = z["P"]; ck = np.array([0.0, P[:, 1].min() * 0.5, P[:, 2].max() * 0.8])
    return w, z, fit, ck


def patches(z):
    P, F, part, kind = z["P"], z["F"], z["part"], z["kind"]
    pid = H.panels(P, F, part * 4 + np.minimum(kind, 3), DEG)
    return pid


def candidates(z, ck, n=10):
    P, F, kind = z["P"], z["F"], z["kind"]
    H_ = float(P[:, 2].max())
    pid = patches(z)
    C = P[F].mean(1)
    nr = np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]])
    A = np.linalg.norm(nr, axis=1) / 2
    nu = nr / (2 * A[:, None] + 1e-12)
    near = (np.linalg.norm(C - ck, axis=1) < 0.16 * H_) & (kind == 0)
    fwd = np.array([0, -1.0, 0.25]); fwd /= np.linalg.norm(fwd)
    rows = []
    for p in np.unique(pid[near]):
        m = (pid == p) & (kind == 0)
        a = A[m].sum()
        if a < 2e-4 * H_ ** 2 or a > 0.02 * H_ ** 2:
            continue
        nm = (nu[m] * A[m, None]).sum(0); nm /= np.linalg.norm(nm) + 1e-12
        f = nm @ fwd
        if f < 0.2:
            continue
        c = (C[m] * A[m, None]).sum(0) / a
        d = np.linalg.norm(c - ck) / (0.16 * H_)
        ext = np.ptp(C[m], 0); flat = ext.min() / (ext.max() + 1e-9)
        score = f * (1 - 0.6 * d) * np.sqrt(a / (0.004 * H_ ** 2)) ** 0.3
        rows.append((score, int(p), c, a))
    rows.sort(key=lambda r: -r[0])
    return pid, rows[:n]


def sheet(mech):
    OUT.mkdir(parents=True, exist_ok=True)
    w, z, fit, ck = load(mech)
    pid, rows = candidates(z, ck)
    H_ = float(z["P"][:, 2].max())
    F = z["F"]
    C = np.tile([0.62, 0.62, 0.62], (len(F), 1))
    for i, (_, p, _, _) in enumerate(rows):
        C[pid == p] = PALETTE[i % len(PALETTE)]
    base = dict(P=z["P"], F=F, target=ck, scale=0.42 * H_, label_pts=np.array([r[2] for r in rows] or [ck]))
    np.savez(OUT / f"{mech}_cand.npz", C=C, **base)
    np.savez(OUT / f"{mech}_plain.npz", C=np.tile([0.62, 0.62, 0.62], (len(F), 1)), **base)
    lab = run_blender(OUT / f"{mech}_cand.npz", OUT / f"{mech}_cand", "shade")
    run_blender(OUT / f"{mech}_plain.npz", OUT / f"{mech}_plain", "shade")
    from PIL import Image, ImageDraw, ImageFont
    font = None
    fp = ROOT / "game/assets/fonts/chakra_petch/ChakraPetch-Bold.ttf"
    if fp.exists():
        font = ImageFont.truetype(str(fp), 30)
    for kind, tag in (("cand", "candidates"), ("plain", "unmarked")):
        S_ = Image.new("RGB", (3000, 1060), (24, 26, 30)); d = ImageDraw.Draw(S_)
        for k, (name, _) in enumerate(VIEWS):
            im = Image.open(OUT / f"{mech}_{kind}_{name}.png").convert("RGB")
            S_.paste(im, (k * 1000, 60))
            if kind == "cand":
                dd = ImageDraw.Draw(S_)
                for i, (x, y) in enumerate(lab[name][:len(rows)]):
                    px, py = k * 1000 + x * 1000, 60 + (1 - y) * 1000
                    dd.text((px - 8, py - 18), str(i + 1), fill=(0, 0, 0), font=font, stroke_width=3, stroke_fill=(255, 255, 255))
            d.text((k * 1000 + 10, 12), f"{mech} {tag}: {name}", fill=(230, 230, 230), font=font)
        S_.save(OUT / f"{mech}_{tag}.png")
    (OUT / f"{mech}_candidates.json").write_text(json.dumps(
        [{"n": i + 1, "patch": p, "point": c.round(1).tolist(), "area_m2": round(a / 1e6, 3)} for i, (_, p, c, a) in enumerate(rows)], indent=1))
    print(OUT / f"{mech}_candidates.png", OUT / f"{mech}_unmarked.png")


def store(mech, points, note):
    cfg = ROOT / f"tools/art/hd_v2/{mech}.json"
    j = json.loads(cfg.read_text())
    j.setdefault("v2", {})["canopy_patches"] = {"deg": DEG, "points": points, "_from": note}
    j["v2"].pop("glass_key", None)
    cfg.write_text(json.dumps(j, indent=1) + "\n")
    print(f"{cfg}: {len(points)} canopy patch points")


def pick(mech, nums):
    cands = json.loads((OUT / f"{mech}_candidates.json").read_text())
    pts = [c["point"] for c in cands if c["n"] in nums]
    store(mech, pts, f"candidates {nums} from {OUT}/{mech}_candidates.png (Lee's pick)")


def paint(mech, png):
    """Back-project blue strokes on the unmarked sheet: face-ID renders from the same cameras, union over views, then
    every patch at least half covered (by area) becomes glass."""
    from PIL import Image
    w, z, fit, ck = load(mech)
    F = z["F"]; P = z["P"]
    ids = np.arange(1, len(F) + 1)
    C = np.c_[(ids >> 16) & 255, (ids >> 8) & 255, ids & 255] / 255.0
    C = np.where(C <= 0.04045, C / 12.92, ((C + 0.055) / 1.055) ** 2.4)
    H_ = float(P[:, 2].max())
    np.savez(OUT / f"{mech}_fid.npz", P=P, F=F, C=C, target=ck, scale=0.42 * H_, label_pts=ck[None])
    run_blender(OUT / f"{mech}_fid.npz", OUT / f"{mech}_fid", "id")
    sheetim = np.asarray(Image.open(png).convert("RGB")).astype(int)
    hit = []
    for k, (name, _) in enumerate(VIEWS):
        panel = sheetim[60:1060, k * 1000:(k + 1) * 1000]
        blue = (panel[..., 2] > 170) & (panel[..., 0] < 120) & (panel[..., 1] < 120)
        a = np.asarray(Image.open(OUT / f"{mech}_fid_{name}.png").convert("RGB")).astype(int)
        fid = ((a[..., 0] << 16) | (a[..., 1] << 8) | a[..., 2]) - 1
        h = fid[blue]; hit.append(h[(h >= 0) & (h < len(F))])
    hit = np.unique(np.concatenate(hit))
    pid = patches(z)
    A = np.linalg.norm(np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]]), axis=1) / 2
    pa = np.bincount(pid, weights=A); ha = np.bincount(pid[hit], weights=A[hit], minlength=len(pa))
    want = np.flatnonzero(ha / np.maximum(pa, 1) >= 0.5)
    Cf = P[F].mean(1)
    pts = []
    for p in want:
        m = np.flatnonzero((pid == p) & (z["kind"] == 0))
        if len(m):
            pts.append(Cf[m[np.argmin(np.linalg.norm(Cf[m] - Cf[m].mean(0), axis=1))]].round(1).tolist())
    store(mech, pts, f"back-projected from {png}")


OUTLINE_DOC = """outlines MECH IMAGE:VIEW[:X0] ...: Lee's closed blue outlines drawn on a 1000 px view (IMAGE, the view's camera
VIEW = front | front34 | top; X0 = the panel's left edge in a 3000 px sheet, 60 px header) -> pane polygons in image
space, stored in the mech's v2.canopy_outlines; hd_v2.py's segment stage knifes them into the mesh where a pane is not
its own face, and paint marks every visible face inside them as glass."""


def outlines(mech, specs):
    from PIL import Image
    from scipy.ndimage import binary_fill_holes, binary_erosion, label
    import cv2
    panes = []
    for spec in specs:
        parts = spec.split(":")
        img, view = parts[0], parts[1]
        x0 = int(parts[2]) if len(parts) > 2 else None
        a = np.asarray(Image.open(img).convert("RGB")).astype(int)
        if x0 is not None:
            a = a[60:1060, x0:x0 + 1000]
        stroke = (a[..., 2] > 170) & (a[..., 0] < 60) & (a[..., 1] < 60)
        filled = binary_fill_holes(stroke)
        inner = binary_erosion(filled, iterations=2)        # the stroke's middle: the pane edge Lee traced
        lab, n = label(inner)
        for k in range(1, n + 1):
            m = (lab == k).astype(np.uint8)
            if m.sum() < 30:
                continue
            cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            c = max(cs, key=cv2.contourArea)
            c = cv2.approxPolyDP(c, 1.2, True)[:, 0, :]
            if len(c) >= 3:
                panes.append({"view": view, "poly": c.astype(float).tolist(), "src": Path(img).name})
    cfg = ROOT / f"tools/art/hd_v2/{mech}.json"
    j = json.loads(cfg.read_text())
    w, z, fit, ck = load(mech)
    H_ = float(z["P"][:, 2].max())
    np.savez(OUT / f"_{mech}_cam.npz", P=z["P"][:3], F=np.array([[0, 1, 2]]), C=np.ones((1, 3)), target=ck,
             scale=0.42 * H_, label_pts=ck[None])
    lab = run_blender(OUT / f"_{mech}_cam.npz", OUT / f"_{mech}_cam", "shade")
    cams = {v: lab["_cam_" + v] for v, _ in VIEWS}   # Blender's camera matrices (m), exactly as the sheets were drawn
    j.setdefault("v2", {})["canopy_outlines"] = {"target": ck.round(1).tolist(), "scale": round(0.42 * H_, 1), "px": 1000,
                                                 "views": dict(VIEWS), "cams": cams, "panes": panes,
                                                 "_from": "Lee's closed outlines (canopy_pick.py outlines), 2026-10-24"}
    j["v2"].pop("canopy_patches", None)
    cfg.write_text(json.dumps(j, indent=1) + "\n")
    print(f"{cfg}: {len(panes)} panes " + ", ".join(f"{p['view']}" for p in panes))


def main():
    cmd, mech = sys.argv[1], sys.argv[2]
    if cmd == "outlines":
        return outlines(mech, sys.argv[3:])
    if cmd == "sheet":
        sheet(mech)
    elif cmd == "pick":
        pick(mech, [int(x) for x in sys.argv[3:]])
    elif cmd == "paint":
        paint(mech, sys.argv[3])


if __name__ == "__main__":
    main()
