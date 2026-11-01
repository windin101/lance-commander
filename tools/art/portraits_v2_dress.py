"""Wounded variants for portraits v2: Qwen-Image-Edit 2509 adds one clean dressing to a finished portrait
(never over an eye, no blood). Placement rotates by crc32(name). Reads scratch/new/<n>.png, writes scratch/dress/<n>.png.
    COMFY_SERVER=http://127.0.0.1:8188 python3 tools/art/portraits_v2_dress.py [--only a,b] [--reseed N]
"""
import argparse, json, os, sys, zlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import comfy
BASE = Path(os.environ.get("PORTRAIT_BASE", "/mnt/nvme1n1p1/claude-scratch/portraits2"))
STYLES = [  # rotated by roster index so no two neighbours match; plain gauze, no crossed tape
    "a large plain rectangular white gauze pad taped over the {side} temple and forehead, with a thin border of tape along its edges",
    "a strip of white gauze wrapped around the head over the forehead and one temple",
    "a plain rectangular white gauze pad on the {side} cheekbone and jaw edge, well clear of the mouth and nose, with a thin border of tape along its edges",
    "a plain white gauze pad with a thin border of tape on the {side} brow ridge, above the eyebrow and clear of the eye",
]
PROMPT = ("Make this pilot look wounded and exhausted, keeping exactly the same person, face, hair, clothing, pose, framing, lighting and background. "
          "Add: {style}; "
          "dark bruising and swelling around the {other} cheekbone, with that eye still wide open and clearly visible; "
          "smudges of soot and grime on the face and a light sheen of sweat; a tired, strained, pained expression with the mouth closed. "
          "No blood spatter, no pooled blood, and nothing at all covering the eyes, the nose or the mouth.")
EXTRA = {"pmwclaymore": "Make the dressing large and the bruising heavy, dark purple-black and swollen.", "pmwrooster": "Make the dressing large and the bruising heavy, dark purple-black and swollen."}
NEG = ("crossed tape, X-shaped plaster, criss-cross tape, blood splatter, blood pool, covering the eye, covering the eyes, eyepatch, mask, surgical mask, covering the mouth, covering the nose, "
       "scarf over the face, smiling, grin, blurry, text, watermark")

def white_added(orig, new):
    """Fraction of the image where a bright, unsaturated patch appears that was not there before (a dressing)."""
    import numpy as np
    from PIL import Image
    o = np.asarray(orig.convert("RGB").resize((330, 460)), dtype=np.float32); n = np.asarray(new.convert("RGB").resize((330, 460)), dtype=np.float32)
    nb, ob = n.min(axis=2), o.max(axis=2)
    m = (nb > 150) & ((n.max(axis=2) - nb) < 45) & (nb - ob > 40)
    low = float(m[int(0.29 * m.shape[0]):].sum()) / max(1.0, float(m.sum()))  # share of the change below the eye line: nose/mouth zone
    return float(m.mean()), low

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--only", default=""); ap.add_argument("--reseed", type=int, default=0)
    a = ap.parse_args()
    names = [n for n in a.only.split(",") if n] or sorted(p.stem for p in (BASE / "new").glob("*.png"))
    out = BASE / "dress"; out.mkdir(exist_ok=True)
    for n in names:
        dst = out / f"{n}.png"
        if dst.exists() and not a.reseed: continue
        k = zlib.crc32(n.encode()); sides = [("left", "right"), ("right", "left")][k % 2]; spot = f"{sides[0]} temple pad + {sides[1]} cheek bruise"; seed = k + a.reseed
        roster = sorted(p.stem for p in (BASE / "new").glob("*.png")); style_t = STYLES[int(dict(x.split("=") for x in os.environ.get("STYLE_OVERRIDE", "").split(",") if x).get(n, roster.index(n) % 4))]; style = style_t.format(side=sides[0])
        prompt = PROMPT.format(style=style, side=sides[0], other=sides[1]) + (" " + EXTRA[n] if n in EXTRA else ""); extra = EXTRA.get(n, ""); spot = style[:40] + " / bruise " + sides[1]
        name = comfy.upload(BASE / "new" / f"{n}.png")
        for t in range(3):
            im = comfy.images(comfy.run(comfy.edit_graph(name, prompt, NEG, seed + t * 1000)))[0].convert("RGB")
            from PIL import Image
            frac, low = white_added(Image.open(BASE / "new" / f"{n}.png"), im)
            print(f"  try {t} white-added {frac:.4f} below-eyeline share {low:.2f}", flush=True)
            if im.getextrema()[0][1] > 60: break  # the white-added check is only logged: it is biased to white dressings, so every result is checked by eye
        im.save(dst); print(n, seed, spot, flush=True)
main()
