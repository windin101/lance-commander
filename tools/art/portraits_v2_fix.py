"""One-off edit passes on finished v2 portraits (Qwen-Image-Edit 2509, 1 MP, same size back).
Originals go to scratch/new_prefix/, results replace scratch/new/<n>.png and master/<n>.png.
    COMFY_SERVER=http://127.0.0.1:8188 python3 tools/art/portraits_v2_fix.py [--only a,b] [--bump N]
"""
import argparse, os, sys, zlib, shutil
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).parent))
import comfy
BASE = Path(os.environ.get("PORTRAIT_BASE", "/mnt/nvme1n1p1/claude-scratch/portraits2"))
KEEP = " Keep exactly the same person, face, hair, clothing, pose, framing and lighting."
GLOW = "Remove the orange glow in the bottom-left corner of the background: make that part of the background the same dark blue-grey gradient as the rest of the background, with no orange or warm light anywhere in the background."
JOBS = {  # key = name or name_what; value = (prompt, negative, source override or None)
 "pmwmeat2": ("Make him broader and heavier-set: a thick neck and a big heavy frame. He wears an olive-grey flight suit with long sleeves down to his wrists (the same olive-grey as a standard flight suit), a high collar, and over it the same black cooling vest with a grey coolant hose running across his chest, plus metal dog tags on a chain. Keep his head exactly the same size and in exactly the same place in the frame, with the same face, bald head and thick black beard, and an even natural skin tone on the neck and face. No bare arms, no cartoon muscles, no exaggerated bulging muscles." + " Same framing and lighting.", "bare arms, sleeveless, bulging muscles, cartoon muscles, exaggerated muscles, smaller head", "orig"),
 "pmwlongshot_tint": ("Remove the warm orange tint at the left edge of the image: make the whole background the same cool dark blue-grey gradient, with no warm light anywhere." + KEEP, "orange glow, warm light on the background", None),
 "pmwvenom_bg": ("Change the background to a muted dark blue-grey gradient, desaturated and slightly lighter toward the top, the same as a neutral studio backdrop; no strongly saturated blue." + KEEP, "saturated blue background", None),
}
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--only", default=""); ap.add_argument("--bump", type=int, default=0)
    a = ap.parse_args()
    for key in [x for x in a.only.split(",") if x] or list(JOBS):
        p, neg, srcmode = JOBS[key]; n = key.split("_")[0].rstrip("2"); src = BASE / "new" / f"{n}.png"
        pre = BASE / "new_prefix"; pre.mkdir(exist_ok=True)
        inp = pre / f"{n}.png" if srcmode == "orig" else pre / f"{key}_pre.png"
        if srcmode != "orig": shutil.copy(src, inp)
        seed = zlib.crc32(n.encode()) + 5200 + a.bump
        im = comfy.images(comfy.run(comfy.edit_graph(comfy.upload(inp), p, neg + ", blurry, text, watermark", seed)))[0].convert("RGB")
        im.resize((660, 920), Image.LANCZOS).save(src, optimize=True)
        im.crop((0, 0, im.width, im.width)).resize((512, 512), Image.LANCZOS).save(BASE / "master" / f"{n}.png")
        print(key, seed, flush=True)
main()
