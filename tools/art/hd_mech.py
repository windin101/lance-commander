"""HD mech pipeline, end to end, for one converted mech:

  1. render the original model (three-quarter view, neutral paint, white, padded)
  2. Qwen-Image-Edit 2509 at 512 px -> HD concept (same pose and silhouette)
  3. Hunyuan3D 2.1 -> high-poly mesh -> decimate, unwrap, bake normal and AO maps
  4. hd_rig.py: fit to the original, rig to its joints, transfer the paint mask
  5. install game/assets/mechs/<mech>_hd.glb and <mech>_hd_paint.bin

    python3 -I tools/art/hd_mech.py bushwacker [--seed 7] [--mesh-seed 1234] [--from-step 2]

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
NEUTRAL_PAINT = "-7829368,-12566464,-5592406"  # mid / dark / light grey


def render(mech, work):
    shot = work / "front34.png"
    subprocess.run([GODOT, "--path", str(GAME), "res://scenes/model_viewer.tscn", "--",
                    f"--screenshot={shot}", "--frames=12", "--cam=35,6,42", "--fov=18", "--focus-y=4.6",
                    "--no-ground", "--bg=1,1,1", f"--model=res://assets/mechs/{mech}.glb",
                    f"--paint={mech},{NEUTRAL_PAINT}"], check=True, capture_output=True, timeout=300)
    im = Image.open(shot).convert("RGB").crop((350, 0, 1250, 900)).resize((1024, 1024))
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


def concept(work, seed, tries=4):
    name = comfy.upload(work / "front34_pad.png")
    for k in range(tries):
        img = comfy.images(comfy.run(comfy.edit_graph(name, hd_concept.PROMPT, hd_concept.NEGATIVE, seed + k, size=512)))[0]
        if plausible(img):
            img.convert("RGB").save(work / "concept.png")
            print(f"  concept ok with seed {seed + k}")
            return
        print(f"  seed {seed + k}: degenerate output, retrying")
    raise RuntimeError("no plausible concept image")


def mesh(work, seed):
    name = comfy.upload(work / "concept.png")
    out = comfy.run(comfy.hd_mesh_graph(name, seed, prefix=f"lc/{work.name}"), timeout=3600)
    for o in out.values():
        for kind in ("3d", "images"):
            for f in o.get(kind, []):
                fn = f["filename"]
                tag = "low.glb" if fn.endswith(".glb") else ("normal.png" if "_normal" in fn else "ao.png")
                (work / tag).write_bytes(comfy.fetch(f))


def rig(mech, work):
    paint_src = work / "orig_paint.png"
    paint_src.write_bytes((GAME / "assets" / "mechs" / f"{mech}_paint.bin").read_bytes())
    subprocess.run([sys.executable, "-I", str(Path(__file__).with_name("hd_rig.py")),
                    str(GAME / "assets" / "mechs" / f"{mech}.glb"), str(paint_src), str(work / "low.glb"),
                    str(work / "normal.png"), str(work / "ao.png"), str(work / f"{mech}_hd.glb"),
                    str(work / "hd_paint.png"), "--tex", "1024", "--concept", str(work / "concept.png")], check=True)


def install(mech, work):
    shutil.copyfile(work / f"{mech}_hd.glb", GAME / "assets" / "mechs" / f"{mech}_hd.glb")
    (GAME / "assets" / "mechs" / f"{mech}_hd_paint.bin").write_bytes((work / "hd_paint.png").read_bytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mech")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--mesh-seed", type=int, default=1234)
    ap.add_argument("--from-step", type=int, default=1)
    a = ap.parse_args()
    work = ROOT / "original" / "hd" / a.mech
    work.mkdir(parents=True, exist_ok=True)
    steps = [(1, "render", lambda: render(a.mech, work)), (2, "concept", lambda: concept(work, a.seed)),
             (3, "mesh", lambda: mesh(work, a.mesh_seed)), (4, "rig", lambda: rig(a.mech, work)),
             (5, "install", lambda: install(a.mech, work))]
    for n, label, fn in steps:
        if n >= a.from_step:
            print(f"[{a.mech}] step {n}: {label}", flush=True)
            fn()
    print(f"[{a.mech}] done")


if __name__ == "__main__":
    main()
