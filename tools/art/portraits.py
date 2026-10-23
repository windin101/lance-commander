"""Pilot portraits for the HUD (issue I84): Qwen-Image text-to-image from the feature words
in portraits.json, one deterministic seed per pilot (crc32(profile) + reseed).

    COMFY_SERVER=http://127.0.0.1:8188 python3 tools/art/portraits.py [--only a,b] [--dry-run]
    python3 tools/art/portraits.py --only pmwjinx --reseed 1000   # redo one draw, recorded in the JSON
    python3 tools/art/portraits.py --sheet out.png                # contact sheet of the installed set

Raw 1056x1472 draws go to $PORTRAIT_WORK (default /mnt/nvme1n1p1/claude-scratch/portraits/raw);
the installed file is game/assets/ui/portraits/<profile>.png at 660x920 (33:46, the portrait
well of pilot_portraits.gd). Gender and apparent age come from the original pilot photos and
voice sets; likeness, ethnicity and styling do not (docs/art-provenance.md, Pilot portraits).
"""

import argparse
import json
import os
import sys
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
import comfy  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CFG_PATH = Path(__file__).with_name("portraits.json")
OUT_DIR = ROOT / "game/assets/ui/portraits"
WORK = Path(os.environ.get("PORTRAIT_WORK", "/mnt/nvme1n1p1/claude-scratch/portraits/raw"))


def load_cfg():
    return json.loads(CFG_PATH.read_text())


def seed_for(cfg, name):
    return zlib.crc32(name.encode()) + int(cfg.get("reseed", {}).get(name, 0))


def prompt_for(cfg, name):
    return cfg["prompt"].format(**cfg["pilots"][name])


def negative_for(cfg, name):
    """The shared negative plus a pilot's own `negative_extra` (kept per pilot so a fix for one
    face doesn't change the seeds already approved)."""
    extra = cfg["pilots"][name].get("negative_extra")
    return cfg["negative"] + (", " + extra if extra else "")


def t2i_graph(cfg, prompt, seed, negative):
    s = cfg["sampling"]
    w, h = cfg["size"]
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": cfg["model"], "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": comfy.QWEN["clip"], "type": "qwen_image"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": comfy.QWEN["vae"]}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": negative}},
        "6": {"class_type": "EmptySD3LatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
        "7": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["1", 0], "shift": s["shift"]}},
        "8": {"class_type": "KSampler", "inputs": {"model": ["7", 0], "seed": seed, "steps": s["steps"], "cfg": s["cfg"],
              "sampler_name": s["sampler"], "scheduler": s["scheduler"], "positive": ["4", 0], "negative": ["5", 0],
              "latent_image": ["6", 0], "denoise": 1.0}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "SaveImage", "inputs": {"images": ["9", 0], "filename_prefix": "lc/portrait"}},
    }


def plausible(img):
    """ROCm SDPA sometimes returns flat grey or noise: want contrast, and a dark backdrop at the corners."""
    a = np.asarray(img.convert("L"), dtype=np.float32)
    corners = np.concatenate([a[:40, :40].ravel(), a[:40, -40:].ravel()])
    return a.std() > 25 and corners.mean() < 110


HAAR = os.environ.get("PORTRAIT_HAAR", "/mnt/nvme1n1p1/StabilityMatrix/linux-x64/Data/Packages/ComfyUI/custom_nodes/was-ns/res/haarcascade_frontalface_default.xml")
FACE_W = 0.40   # face box width as a fraction of the crop width
FACE_Y = 0.40   # face box centre as a fraction of the crop height


def find_crop(raw, aspect):
    """Crop box [x, y, w] (h = w * aspect) that puts every face at the same size and place:
    Qwen ignores framing words, so the set is normalised after the draw. OpenCV's frontal-face
    Haar cascade finds the face once; the box is stored in portraits.json so reruns need no detector."""
    import cv2
    g = cv2.imread(str(raw), cv2.IMREAD_GRAYSCALE)
    H, W = g.shape
    faces = cv2.CascadeClassifier(HAAR).detectMultiScale(g, 1.1, 6, minSize=(W // 8, W // 8))
    if not len(faces):
        print(f"  {raw.name}: no face found, using the full frame", flush=True)
        return [0, 0, W]
    fx, fy, fw, fh = max(faces, key=lambda f: f[2])
    w = min(W, H / aspect, fw / FACE_W)
    h = w * aspect
    x = min(max(fx + fw / 2 - w / 2, 0), W - w)
    y = min(max(fy + fh / 2 - FACE_Y * h, 0), H - h)
    return [int(round(x)), int(round(y)), int(round(w))]


def install(cfg, raw, name):
    ow, oh = cfg["output"]
    crops = cfg.setdefault("crop", {})
    key = f"{name}_s{seed_for(cfg, name)}"
    if key not in crops:
        crops[key] = find_crop(raw, oh / ow)
        cfg["crop"] = dict(sorted(crops.items()))
        CFG_PATH.write_text(json.dumps(cfg, indent=1) + "\n")
    x, y, w = crops[key]
    img = Image.open(raw).convert("RGB").crop((x, y, x + w, y + round(w * oh / ow))).resize((ow, oh), Image.LANCZOS)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    img.save(OUT_DIR / f"{name}.png", optimize=True)


def generate(cfg, name, dry=False):
    seed = seed_for(cfg, name)
    prompt = prompt_for(cfg, name)
    raw = WORK / f"{name}_s{seed}.png"
    if dry:
        print(name, seed, raw, "\n  ", prompt)
        return
    WORK.mkdir(parents=True, exist_ok=True)
    if not raw.exists():
        for attempt in range(3):
            img = comfy.images(comfy.run(t2i_graph(cfg, prompt, seed, negative_for(cfg, name))))[0].convert("RGB")
            if plausible(img):
                break
            print(f"  {name}: implausible output on try {attempt + 1}, rerunning", flush=True)
        else:
            raise RuntimeError(f"{name}: no plausible draw for seed {seed}")
        img.save(raw)
        cfg.setdefault("crop", {}).pop(raw.stem, None)  # a new draw needs its own face box
    install(cfg, raw, name)
    print(f"{name} seed {seed} -> {OUT_DIR / (name + '.png')}", flush=True)


def sheet(cfg, out, names, cols=7):
    """Contact sheet: each installed portrait on the HUD portrait well with its cyan frame."""
    tw, th = 220, 307
    pad, lab = 14, 34
    rows = (len(names) + cols - 1) // cols
    W, H = cols * (tw + pad) + pad, rows * (th + lab + pad) + pad
    s = Image.new("RGB", (W, H), (9, 20, 30))
    d = ImageDraw.Draw(s)
    try:
        font = ImageFont.truetype(str(ROOT / "game/assets/fonts/chakra_petch/ChakraPetch-SemiBold.ttf"), 18)
    except OSError:
        font = ImageFont.load_default()
    pilots = json.loads((ROOT / "game/data/pilots.json").read_text())
    for i, n in enumerate(names):
        x, y = pad + (i % cols) * (tw + pad), pad + (i // cols) * (th + lab + pad)
        p = OUT_DIR / f"{n}.png"
        d.rectangle([x - 2, y - 2, x + tw + 1, y + th + 1], outline=(63, 198, 224), width=2)
        if p.exists():
            s.paste(Image.open(p).convert("RGB").resize((tw, th), Image.LANCZOS), (x, y))
        g = pilots[n]["General"]
        d.text((x, y + th + 6), f"{g['Callsign'].upper()}  ({'F' if cfg['pilots'][n]['gender'] == 'woman' else 'M'})", fill=(232, 241, 244), font=font)
    s.save(out)
    print("sheet", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--reseed", type=int)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sheet")
    a = ap.parse_args()
    cfg = load_cfg()
    names = sorted(cfg["pilots"])
    if a.only:
        names = [n for n in a.only.split(",") if n]
    if a.reseed is not None:
        cfg.setdefault("reseed", {}).update({n: a.reseed for n in names})
        cfg["reseed"] = dict(sorted(cfg["reseed"].items()))
        CFG_PATH.write_text(json.dumps(cfg, indent=1) + "\n")
    if a.sheet:
        sheet(cfg, a.sheet, sorted(cfg["pilots"]))
        return
    for n in names:
        generate(cfg, n, a.dry_run)


if __name__ == "__main__":
    main()
