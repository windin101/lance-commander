"""Pilot portraits v2 (STYLE-GUIDE 7 / LANCE-32): locked template + per-person words, Qwen-Image t2i.

    COMFY_SERVER=http://127.0.0.1:8188 python3 tools/art/portraits_v2.py [--only a,b] [--reseed N] [--dry-run]

Raw 1248x1472 draws -> $PORTRAIT_WORK (default /mnt/nvme1n1p1/claude-scratch/portraits2/raw).
Installed: game/assets/ui/portraits/<name>.png (660x920, 33:46, what pilot_portraits.gd loads) and a
512x512 guide-format master in $PORTRAIT_WORK/../master. Face-box crops are stored in the JSON.
"""
import argparse, json, os, sys, zlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import portraits as P  # reuse graph, plausibility, Haar finder
import comfy

CFG = Path(__file__).with_name("portraits_v2.json")
WORK = Path(os.environ.get("PORTRAIT_WORK", "/mnt/nvme1n1p1/claude-scratch/portraits2/raw"))
P.FACE_Y = 0.36
P.FACE_W = 0.30


def seed_for(cfg, n):
    return zlib.crc32(n.encode()) + int(cfg["reseed"].get(n, 0))


def run(cfg, n, dry):
    p = cfg["pilots"][n]
    prompt = cfg["prompt"].format(**p)
    neg = cfg["negative"] + (", " + p["negative_extra"] if p.get("negative_extra") else "")
    seed = seed_for(cfg, n)
    raw = WORK / f"{n}_s{seed}.png"
    if dry:
        print(n, seed, "\n ", prompt); return
    WORK.mkdir(parents=True, exist_ok=True)
    if not raw.exists():
        for t in range(3):
            img = comfy.images(comfy.run(P.t2i_graph(cfg, prompt, seed + t * 7919, neg)))[0].convert("RGB")
            if P.plausible(img): break
        else:
            raise RuntimeError(n)
        img.save(raw)
        cfg["crop"].pop(f"{n}_s{seed}", None)
    key = f"{n}_s{seed}"
    if key not in cfg["crop"]:
        cfg["crop"][key] = [96, 0, 1056]  # locked camera: full-height crop, x tweakable per draw in the JSON
        CFG.write_text(json.dumps(cfg, indent=1) + "\n")
    x, y, w = cfg["crop"][key]
    from PIL import Image
    im = Image.open(raw).convert("RGB")
    ow, oh = cfg["output"]
    h = round(w * oh / ow)
    out = Path(os.environ.get("PORTRAIT_OUT", WORK.parent / "new")); out.mkdir(parents=True, exist_ok=True)  # never the game folder until approved
    im.crop((x, y, x + w, y + h)).resize((ow, oh), Image.LANCZOS).save(out / f"{n}.png", optimize=True)
    m = WORK.parent / "master"; m.mkdir(exist_ok=True)
    sq = min(w, im.width - x)  # square master: same face scale, full width of the crop
    im.crop((x, y, x + sq, y + sq)).resize((cfg["master"],) * 2, Image.LANCZOS).save(m / f"{n}.png")
    print(n, seed, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=""); ap.add_argument("--reseed", type=int); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    cfg = json.loads(CFG.read_text())
    names = [n for n in a.only.split(",") if n] or list(cfg["pilots"])
    if a.reseed is not None:
        for n in names: cfg["reseed"][n] = a.reseed
        CFG.write_text(json.dumps(cfg, indent=1) + "\n")
    for n in names: run(cfg, n, a.dry_run)

if __name__ == "__main__":
    main()
