"""Memorial portraits (STYLE-GUIDE 7, LANCE-32 follow-up, Lee 2026-11-01): the same pilot in dress uniform and a
peaked cap, frontal, eyes to camera, a gentle smile, black and white with a black border. Replaces the old
"desaturate + slash" dead-pilot idea.

Qwen-Image-Edit 2509 at 1 MP redraws the clean portrait (game/assets/ui/portraits/<n>.png) in dress uniform in colour;
the greyscale conversion and the border are done here in code so every memorial is consistent.

    COMFY_SERVER=http://127.0.0.1:8188 python3 tools/art/portraits_v3_memorial.py [--only pmwsteel,pmwflash] [--bump N]
        [--install] [--sheet OUT.png]

Raw colour edits -> $PORTRAIT3/memorial_raw/<n>_s<seed>.png, finished -> $PORTRAIT3/memorial/<n>_memorial.png
(--install copies the finished files into game/assets/ui/portraits/). Seed = crc32(name) + 7000 + bump(name), bumps
in portraits_v3.json "memorial_bump" (a bad draw is a bump for that one name, never a batch rerun).
"""
import argparse, json, os, sys, zlib, shutil
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw
sys.path.insert(0, str(Path(__file__).parent))
import comfy

ROOT = Path(__file__).resolve().parents[2]
GAME = ROOT / "game/assets/ui/portraits"
CFG = Path(__file__).with_name("portraits_v3.json")
BASE = Path(os.environ.get("PORTRAIT3", "/mnt/nvme1n1p1/claude-scratch/portraits3"))
SIZE = (660, 920)
BORDER = 22  # px of black frame, at the installed size

PROMPT = ("Redraw this exact same person in a formal military dress uniform portrait, keeping the same face, the same facial features, "
          "the same skin tone, hair, beard and age, so that the person is clearly recognisable. "
          "Change the clothing to a dark formal tunic with a high stiff collar, buttoned to the neck, with small plain collar tabs, "
          "a few rows of small plain ribbon bars on the left chest, and a dark peaked officer's cap with a plain small metal badge, "
          "worn straight on the head with a shiny visor shading the brow. Remove the flight suit, the cooling vest, the hose and the dog tags. "
          "Zoom in to a head and shoulders portrait cropped at the upper chest: the head fills about forty percent of the image height, "
          "the person facing straight at the camera, shoulders square, both eyes looking directly into the lens, "
          "with a warm, gentle, genuine smile: lips together, the corners of the mouth turned up, the cheeks lifted and the eyes friendly. "
          "Same painterly style, same soft lighting, plain dark blue-grey backdrop.")
NEG = ("flag, national insignia, real-world emblem, text, letters, writing, medals on a sash, sunglasses, hat covering the eyes, "
       "looking away, three-quarter view, profile, open mouth, teeth, wide grin, frown, stern, neutral expression, waist-up, full body, blood, scar, bandage, flight suit, helmet, "
       "cooling vest, hose, dog tags, second person, blurry, cartoon, anime, watermark")


def cfg():
    return json.loads(CFG.read_text()) if CFG.exists() else {}


def seed_for(n, bump):
    return zlib.crc32(n.encode()) + 7000 + int(bump)


HAAR = os.environ.get("PORTRAIT_HAAR", "/mnt/nvme1n1p1/StabilityMatrix/linux-x64/Data/Packages/ComfyUI/custom_nodes/was-ns/res/haarcascade_frontalface_default.xml")
FACE_FRAC = 0.38  # the Haar box (brow-to-chin plus margin) is this share of the crop height: about 50% of the frame is the face itself, cap top to just below the collar


def face_box(raw: Image.Image):
    import cv2, numpy as np
    g0 = cv2.cvtColor(np.asarray(raw.convert("RGB")), cv2.COLOR_RGB2GRAY)
    cc = cv2.CascadeClassifier(HAAR)
    f = []
    # several preprocessings: a peaked cap's shadow defeats some of them on some faces
    for im, sf, nb in [(g0, 1.1, 3), (cv2.createCLAHE(3.0, (8, 8)).apply(g0), 1.05, 3), (cv2.equalizeHist(g0), 1.08, 5), (cv2.equalizeHist(g0), 1.03, 1)]:
        f = [r for r in cc.detectMultiScale(im, sf, nb, minSize=(raw.width // 6, raw.width // 6)) if r[1] < raw.height * 0.5]  # the head is in the upper half
        if len(f):
            break
    if len(f) == 0:
        return None
    x, y, w, h = max(f, key=lambda r: r[2] * r[3])
    return [int(x), int(y), int(w), int(h)]


def crop_box(raw: Image.Image, n: str):
    """Head and shoulders, 33:46: face box (stored per name in portraits_v3.json "face_box" so a rerun needs no detector)
    about FACE_FRAC of the frame height, cap top in frame, cut just below the collar. "crop" overrides by hand [x, y, h]."""
    c = cfg()
    if n in c.get("crop", {}):
        x, y, h = c["crop"][n]
    else:
        fb = c.get("face_box", {}).get(n) or face_box(raw)
        if fb is None:
            raise RuntimeError(f"no face found in the memorial edit for {n}: set crop [x, y, h] by hand")
        fx, fy, fw, fh = fb
        h = fh / FACE_FRAC
        y = fy + fh / 2 - h * 0.46  # face centre a little above the frame centre
        x = fx + fw / 2 - h * 33 / 46 / 2
    w = h * 33 / 46
    x = min(max(x, 0), raw.width - w); y = min(max(y, 0), raw.height - h)
    return (round(x), round(y), round(x + w), round(y + h))


def finish(raw: Image.Image, n: str = "") -> Image.Image:
    """Head-and-shoulders crop, greyscale and black border at the installed size, so every memorial is the same."""
    im = raw.convert("RGB").crop(crop_box(raw, n))
    g = ImageOps.autocontrast(ImageOps.grayscale(im), cutoff=0.5)
    out = Image.new("L", SIZE, 0)
    inner = (SIZE[0] - 2 * BORDER, SIZE[1] - 2 * BORDER)
    out.paste(g.resize(inner, Image.LANCZOS), (BORDER, BORDER))
    d = ImageDraw.Draw(out)
    d.rectangle((BORDER - 1, BORDER - 1, SIZE[0] - BORDER, SIZE[1] - BORDER), outline=70, width=1)  # hairline keeps the picture edge readable on black
    return out.convert("RGB")


def plausible(im):
    import numpy as np
    a = np.asarray(im.convert("L"), dtype=np.float32)
    return a.std() > 20 and a.mean() > 8  # dress blues are dark: only reject a flat or black draw


def prompt_for(n):
    """The shared prompt plus the pilot's own identity words (portraits_v3.json "memorial_extra"), for faces the edit softens."""
    extra = cfg().get("memorial_extra", {}).get(n, "")
    return PROMPT + (" " + extra if extra else "")


def run(n, bump):
    seed = seed_for(n, bump)
    raw = BASE / "memorial_raw" / f"{n}_s{seed}.png"
    if not raw.exists():
        src = GAME / f"{n}.png"
        up = comfy.upload(src)
        for t in range(3):
            im = comfy.images(comfy.run(comfy.edit_graph(up, prompt_for(n), NEG, seed + t * 1000)))[0].convert("RGB")
            im.save(BASE / "memorial_raw" / f"{n}_try{t}.png")  # keep every try: a rejected draw is evidence
            if plausible(im):
                break
            print(n, "try", t, "rejected as flat", flush=True)
        im.save(raw)
    (BASE / "masters").mkdir(exist_ok=True)
    master = BASE / "masters" / f"{n}_memorial_colour.png"  # the uncropped colour edit: re-crop later without GPU time
    shutil.copy(raw, master)  # always the raw of the current seed (a redraw replaces the old master)
    img = Image.open(master)
    c = cfg()
    if n not in c.get("face_box", {}) and n not in c.get("crop", {}):
        fb = face_box(img)
        if fb:
            c.setdefault("face_box", {})[n] = fb
            CFG.write_text(json.dumps(c, indent=1) + "\n")
    dst = BASE / "memorial" / f"{n}_memorial.png"
    finish(img, n).save(dst, optimize=True)
    print(n, seed, flush=True)
    return dst


def sheet(names, out):
    """Clean portrait | colour edit | finished memorial, one row per pilot."""
    cw, ch = 220, 307
    W = Image.new("RGB", (cw * 3 + 40, (ch + 10) * len(names) + 10), (20, 22, 26))
    c = cfg().get("memorial_bump", {})
    for i, n in enumerate(names):
        y = 10 + i * (ch + 10)
        seed = seed_for(n, c.get(n, 0))
        for j, p in enumerate([GAME / f"{n}.png", BASE / "memorial_raw" / f"{n}_s{seed}.png", BASE / "memorial" / f"{n}_memorial.png"]):
            if p.exists():
                W.paste(Image.open(p).convert("RGB").resize((cw, ch), Image.LANCZOS), (10 + j * (cw + 10), y))
    W.save(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=""); ap.add_argument("--bump", type=int); ap.add_argument("--install", action="store_true")
    ap.add_argument("--sheet", default="")
    a = ap.parse_args()
    c = cfg(); bumps = c.setdefault("memorial_bump", {})
    names = [x for x in a.only.split(",") if x] or sorted(p.stem for p in GAME.glob("pmw*.png") if not p.stem.endswith(("_wounded", "_memorial")))
    for n in names:
        if a.bump is not None:
            bumps[n] = a.bump
            CFG.write_text(json.dumps(c, indent=1) + "\n")
        dst = run(n, bumps.get(n, 0))
        if a.install:
            shutil.copy(dst, GAME / dst.name)
    if a.sheet:
        sheet(names, a.sheet)

if __name__ == "__main__":
    main()
