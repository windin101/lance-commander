"""Review sheet for portraits v2: each new portrait beside the current one (the silhouette
placeholder for the tac officer), then one pilot's normal / wounded / dead states mocked up per
STYLE-GUIDE 7 (red tint on the bottom edge + dressing variant; desaturate + slash).
The wounded/dead states are NOT in pilot_portraits.gd yet: this is a PIL mock-up of the guide text.

    python3 tools/art/portraits_v2_sheet.py OUT.png [--old DIR] [--state-pilot pmwflash] [--bandage FILE]
"""
import argparse, json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

ROOT = Path(__file__).resolve().parents[2]
NEW = Path("/mnt/nvme1n1p1/claude-scratch/portraits2/new")  # draws stay out of the game folder until approved
WELL, STEEL, CYAN = (14, 29, 40), (58, 72, 84), (63, 198, 224)
TW, TH = 240, 335


def font(n):
    return ImageFont.truetype(str(ROOT / "game/assets/fonts/chakra_petch/ChakraPetch-SemiBold.ttf"), n)


def placeholder():
    im = Image.new("RGB", (132, 184), WELL); d = ImageDraw.Draw(im)
    fg = (44, 74, 90); d.ellipse([66 - 30, 68 - 30, 66 + 30, 68 + 30], fill=fg)
    d.pieslice([12, 116, 120, 300], 180, 360, fill=fg)
    return im


def wounded(im):
    im = im.copy().convert("RGBA"); w, h = im.size
    g = Image.new("RGBA", im.size, (0, 0, 0, 0)); px = g.load()
    for y in range(int(h * 0.62), h):
        a = int(150 * max(0.0, (y - h * 0.62) / (h * 0.38)) ** 1.6)
        for x in range(w): px[x, y] = (255, 90, 78, a)
    return Image.alpha_composite(im, g).convert("RGB")


def dead(im):
    im = ImageEnhance.Color(im).enhance(0.0)
    im = ImageEnhance.Brightness(im).enhance(0.55).convert("RGB")
    d = ImageDraw.Draw(im); w, h = im.size
    d.line([(w * 0.08, h * 0.92), (w * 0.92, h * 0.08)], fill=(255, 90, 78), width=max(4, w // 40))
    return im


def tile(im, label, border=STEEL, sub=None):
    t = Image.new("RGB", (TW + 4, TH + 40), (9, 20, 30)); d = ImageDraw.Draw(t)
    d.rectangle([0, 0, TW + 3, TH + 3], fill=border)
    t.paste(im.convert("RGB").resize((TW, TH), Image.LANCZOS), (2, 2))
    d.text((2, TH + 8), label, fill=(232, 241, 244), font=font(17))
    if sub: d.text((2, TH + 26), sub, fill=(140, 160, 170), font=font(12))
    return t


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("--old", default="/mnt/nvme1n1p1/claude-scratch/portraits2/old")
    ap.add_argument("--state-pilot", default="pmwflash"); ap.add_argument("--state-pilot2", default="pmwsteel"); ap.add_argument("--bandage")
    a = ap.parse_args()
    cfg = json.loads((Path(__file__).with_name("portraits_v2.json")).read_text())
    pil = json.loads((ROOT / "game/data/pilots.json").read_text())
    names = list(cfg["pilots"])
    cell = TW + 4; pad = 14
    cols = 3; pair_w = 2 * cell + pad
    W = cols * (pair_w + pad) + pad
    rows = 2
    H = rows * (TH + 40 + pad) + pad + 2 * (TH + 40 + pad) + 40
    s = Image.new("RGB", (W, H), (9, 20, 30)); d = ImageDraw.Draw(s)
    for i, n in enumerate(names):
        x = pad + (i % cols) * (pair_w + pad); y = pad + (i // cols) * (TH + 40 + pad)
        op = Path(a.old) / f"{n}.png"
        old = Image.open(op) if op.exists() else placeholder()
        title = "TAC OFFICER" if n == "tacofficer" else pil[n]["General"]["Callsign"]
        s.paste(tile(old, f"{title}  current"), (x, y))
        s.paste(tile(Image.open(NEW / f"{n}.png"), f"{title}  new", CYAN), (x + cell + pad, y))
    y = pad + 2 * (TH + 40 + pad) + 6
    d.text((pad, y - 4), "STATES (mock-up of guide 7, not in pilot_portraits.gd yet): normal | wounded | dead", fill=(242, 162, 31), font=font(15))
    y += 22
    for r, pn in enumerate([a.state_pilot, a.state_pilot2]):
        base = Image.open(NEW / f"{pn}.png")
        items = [(f"{pn[3:].upper()} normal", base), ("wounded: red edge tint", wounded(base))]
        if a.bandage and r == 0: items.append(("wounded: dressing variant", wounded(Image.open(a.bandage))))
        items.append(("dead: desaturate + slash", dead(base)))
        for k, (lab, im) in enumerate(items):
            s.paste(tile(im, lab), (pad + (k + r * 0) * (cell + pad) + (0 if r == 0 else 0), y + r * (TH + 40 + pad)))
    s.save(a.out); print(a.out, s.size)

main()
