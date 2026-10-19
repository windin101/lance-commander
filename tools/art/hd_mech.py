"""HD mech pipeline, end to end, for one converted mech:

  1. render the original model (three-quarter view, neutral paint, white, padded)
  2. Qwen-Image-Edit 2509 at 512 px -> HD concept (same pose and silhouette)
  3. Hunyuan3D 2.1 -> high-poly mesh -> decimate, unwrap, bake normal and AO maps
  4. hd_rig.py: fit to the original, rig to its joints, transfer the paint mask
  5. install game/assets/mechs/<mech>_hd.glb and <mech>_hd_paint.bin

    python3 -I tools/art/hd_mech.py bushwacker [--seed 7] [--mesh-seed 1234] [--from-step 2] [--turn]
    python3 -I tools/art/hd_mech.py harasser --kind vehicles
    python3 -I tools/art/hd_mech.py quonset --kind objects   (static: no rig, colour texture)

ComfyUI must run with --use-split-cross-attention on this machine's ROCm nightly:
with PyTorch SDPA the Qwen edit intermittently returns garbage. Working files go
to original/hd/<mech>/ (gitignored). The outputs are AI-derived from the Shared
Source art and stay under its non-commercial terms.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comfy  # noqa: E402
import hd_concept  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
GAME = ROOT / "game"
GODOT = shutil.which("godot") or str(Path.home() / ".local/bin/godot")
# Another session may run Godot in this repo at the same time: every Godot run here takes this
# lock (flock(1)) so the two never overlap. Keep each run short.
GODOT_LOCK = ROOT / ".godot.lock"
NEUTRAL_PAINT = "-7829368,-12566464,-5592406"  # mid / dark / light grey


KINDS = {
    # folder, camera "yaw,pitch,distance", focus height (m), concept prompt
    "mechs": ("mechs", "35,6,42", "4.6", hd_concept.PROMPT),
    "vehicles": ("vehicles", "35,14,26", "1.6", hd_concept.VEHICLE_PROMPT),
    "objects": ("objects", None, None, hd_concept.BUILDING_PROMPT),  # framed from the model's bounds
}


def bounds(glb):
    """Axis-aligned extent of a converted model (all position accessors, unscaled nodes)."""
    import json
    import struct
    data = glb.read_bytes()
    gltf = json.loads(data[20:20 + struct.unpack_from("<I", data, 12)[0]])
    acc = [a for a in gltf["accessors"] if len(a.get("min", [])) == 3]
    lo = [min(a["min"][k] for a in acc) for k in range(3)]
    hi = [max(a["max"][k] for a in acc) for k in range(3)]
    return lo, hi


def framing(mech, kind):
    folder, cam, focus, _ = KINDS[kind]
    if cam:
        return cam, focus, None
    lo, hi = bounds(GAME / "assets" / folder / f"{mech}.glb")
    size = max(h - l for h, l in zip(hi, lo))
    # fov 18 shows about 0.32 x distance vertically; mechs use about 4.6 x their height
    centre = [(h + l) / 2 for h, l in zip(hi, lo)]
    return f"35,20,{3.6 * size:.1f}", f"{centre[1]:.2f}", f"{centre[0]:.2f},{centre[2]:.2f}"


def paint_source(mech, kind):
    folder = KINDS[kind][0]
    if kind == "objects":
        return GAME / "assets" / folder / f"{mech}_0.png"  # the colour texture itself
    mask = GAME / "assets" / folder / f"{mech}_paint.bin"
    # A few converted mechs (flea, laohu, jaegermech, vulture, the copters) have no _paint.bin;
    # the mask is the same image as the model's own texture, so use that.
    return mask if mask.exists() else GAME / "assets" / folder / f"{mech}_0.png"


def touches_edge(im, margin=6):
    """True if the subject reaches the border of the crop (a tall mech cut off at the top)."""
    import numpy as np
    a = np.asarray(im.convert("L"))
    edge = np.concatenate([a[:margin].ravel(), a[:, :margin].ravel(), a[:, -margin:].ravel()])
    return (edge < 235).mean() > 0.002


def render(mech, work, kind, cam_override=None, focus_override=None):
    folder = KINDS[kind][0]
    cam, focus, xz = framing(mech, kind)
    cam, focus = cam_override or cam, focus_override or focus  # e.g. the copters fly at 23.5 m
    shot = work / "front34.png"
    yaw, pitch, dist = (float(v) for v in cam.split(","))
    for zoom in (1.0, 1.25, 1.5, 1.8):  # tall mechs (Atlas, Highlander) overflow the standard mech framing
        paint = [] if kind == "objects" else [f"--paint={mech},{NEUTRAL_PAINT}"]
        subprocess.run(["flock", str(GODOT_LOCK), GODOT, "--path", str(GAME), "res://scenes/model_viewer.tscn", "--",
                        f"--screenshot={shot}", "--frames=12", f"--cam={yaw:g},{pitch:g},{dist * zoom:.1f}", "--fov=18",
                        f"--focus-y={float(focus) * (1 if focus_override else zoom):.2f}", "--no-ground", "--bg=1,1,1", f"--model=res://assets/{folder}/{mech}.glb",
                        ] + ([f"--focus-xz={xz}"] if xz else []) + paint, check=True, capture_output=True, timeout=1800)
        crop = Image.open(shot).convert("RGB").crop((350, 0, 1250, 900))
        if kind == "objects" or not touches_edge(crop):
            break
        print(f"  subject touches the frame at zoom {zoom}: backing off")
    (work / "render_zoom.txt").write_text(f"{zoom}\n")
    # the exact camera used, so review renders of the HD model frame it the same way
    fy = float(focus) * (1 if focus_override else zoom)
    (work / "render_cam.txt").write_text(f"{yaw:g},{pitch:g},{dist * zoom:.1f} {fy:.2f}\n")
    im = crop.resize((1024, 1024))
    pad = Image.new("RGB", (1024, 1024), (255, 255, 255))
    pad.paste(im.resize((680, 680)), (172, 172))  # margin: the edit tends to zoom in
    pad.save(work / "front34_pad.png")


def plausible(img):
    """Reject the degenerate outputs this ROCm build sometimes returns (flat grey, noise):
    a real concept has a white background with a substantial dark, varied subject."""
    import numpy as np
    a = np.asarray(img.convert("L"), dtype=float)
    subject = a < 200
    return a.std() > 30 and 0.05 < subject.mean() < 0.7 and a[subject].std() > 15


def concept(work, seed, kind, tries=4, prompt_kind=None):
    prompt = KINDS[prompt_kind or kind][3]  # the copters are mech models with the vehicle prompt
    name = comfy.upload(work / "front34_pad.png")
    for k in range(tries):
        # Unload first: on this ROCm build the third edit in a row on a warm server came back all
        # black (NaN) every time; a cold model load each edit avoided it.
        comfy.api("/free", {"unload_models": True, "free_memory": True})
        img = comfy.images(comfy.run(comfy.edit_graph(name, prompt, hd_concept.NEGATIVE, seed + k, size=512)))[0]
        if plausible(img):
            img.convert("RGB").save(work / "concept.png")
            print(f"  concept ok with seed {seed + k}")
            return
        img.convert("RGB").save(work / f"concept_rejected_s{seed + k}.png")  # look before blaming the prompt
        if max(img.convert("L").getextrema()) == 0:
            # All black is NaN in the server (seen after two good edits, on split attention), not a bad seed:
            # every later seed comes back black too until ComfyUI is restarted.
            raise RuntimeError("ComfyUI returned an all-black image: restart the server, then rerun")
        print(f"  seed {seed + k}: degenerate output, retrying")
    raise RuntimeError("no plausible concept image")


def mesh(work, seed, kind):
    name = comfy.upload(work / "concept.png")
    algorithm = "basic" if kind == "objects" else "surface net"  # see comfy.hd_mesh_graph
    out = comfy.run(comfy.hd_mesh_graph(name, seed, prefix=f"lc/{work.name}", algorithm=algorithm), timeout=3600)
    for o in out.values():
        for kind in ("3d", "images"):
            for f in o.get(kind, []):
                fn = f["filename"]
                tag = "low.glb" if fn.endswith(".glb") else ("normal.png" if "_normal" in fn else "ao.png")
                (work / tag).write_bytes(comfy.fetch(f))


def rig(mech, work, kind, turn=False):
    folder = KINDS[kind][0]
    paint_src = work / "orig_paint.png"
    paint_src.write_bytes(paint_source(mech, kind).read_bytes())
    subprocess.run([sys.executable, "-I", str(Path(__file__).with_name("hd_rig.py")),
                    str(GAME / "assets" / folder / f"{mech}.glb"), str(paint_src), str(work / "low.glb"),
                    str(work / "normal.png"), str(work / "ao.png"), str(work / f"{mech}_hd.glb"),
                    str(work / "hd_paint.png"), "--tex", "1024", "--concept", str(work / "concept.png")] + (["--turn"] if turn else [])
                   + (["--static"] if kind == "objects" else []), check=True)


def install(mech, work, kind):
    folder = KINDS[kind][0]
    shutil.copyfile(work / f"{mech}_hd.glb", GAME / "assets" / folder / f"{mech}_hd.glb")
    if kind == "objects":
        return  # the colour texture is embedded; there is no team paint mask
    (GAME / "assets" / folder / f"{mech}_hd_paint.bin").write_bytes((work / "hd_paint.png").read_bytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mech")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--mesh-seed", type=int, default=1234)
    ap.add_argument("--from-step", type=int, default=1)
    ap.add_argument("--to-step", type=int, default=5)
    ap.add_argument("--kind", choices=sorted(KINDS), default="mechs")
    ap.add_argument("--prompt", choices=sorted(KINDS), help="concept prompt of another kind (copters: vehicles)")
    ap.add_argument("--cam", help="render camera yaw,pitch,distance (default: the kind's)")
    ap.add_argument("--focus-y", help="render focus height in m (default: the kind's)")
    ap.add_argument("--turn", action="store_true", help="the fit landed backwards (check the front view by eye)")
    a = ap.parse_args()
    work = ROOT / "original" / "hd" / a.mech
    work.mkdir(parents=True, exist_ok=True)
    steps = [(1, "render", lambda: render(a.mech, work, a.kind, a.cam, a.focus_y)), (2, "concept", lambda: concept(work, a.seed, a.kind, prompt_kind=a.prompt)),
             (3, "mesh", lambda: mesh(work, a.mesh_seed, a.kind)), (4, "rig", lambda: rig(a.mech, work, a.kind, a.turn)),
             (5, "install", lambda: install(a.mech, work, a.kind))]
    for n, label, fn in steps:
        if a.from_step <= n <= a.to_step:
            print(f"[{a.mech}] step {n}: {label}", flush=True)
            fn()
    print(f"[{a.mech}] done")


if __name__ == "__main__":
    main()
