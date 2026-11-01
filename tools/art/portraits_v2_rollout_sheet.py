"""Rollout sheets for portraits v2: v1 (git HEAD copy in scratch/v1) vs new, and the dressing variants.
    python3 tools/art/portraits_v2_rollout_sheet.py OUTPREFIX   -> OUTPREFIX_a.png, _b.png (old|new) and _dress.png
"""
import json, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT = Path(__file__).resolve().parents[2]
BASE = Path("/mnt/nvme1n1p1/claude-scratch/portraits2")
TW, TH = 200, 279
F = ImageFont.truetype(str(ROOT / "game/assets/fonts/chakra_petch/ChakraPetch-SemiBold.ttf"), 15)
pil = json.loads((ROOT / "game/data/pilots.json").read_text())
names = [n for n in json.loads((Path(__file__).with_name("portraits_v2.json")).read_text())["pilots"]]
v1 = BASE / "v1"; v1.mkdir(exist_ok=True)
for n in names:
    if n.startswith("pmw") and not (v1 / f"{n}.png").exists():
        (v1 / f"{n}.png").write_bytes(subprocess.run(["git", "-C", str(ROOT), "show", f"HEAD:game/assets/ui/portraits/{n}.png"], capture_output=True).stdout)

def lab(n): return "TAC OFFICER" if n == "tacofficer" else pil[n]["General"]["Callsign"]
def tile(d, im, x, y, text, col):
    d.rectangle([x - 2, y - 2, x + TW + 1, y + TH + 1], outline=col, width=2)
    return im.convert("RGB").resize((TW, TH), Image.LANCZOS)

def sheet(items, out, pair):
    cols = 4 if pair else 8
    cw = (2 * (TW + 8) + 14) if pair else (TW + 8)
    rows = (len(items) + cols - 1) // cols
    W, H = cols * cw + 14, rows * (TH + 40) + 14
    s = Image.new("RGB", (W, H), (9, 20, 30)); d = ImageDraw.Draw(s)
    for i, n in enumerate(items):
        x = 14 + (i % cols) * cw; y = 14 + (i // cols) * (TH + 40)
        if pair:
            if (v1 / f"{n}.png").exists() and (v1 / f"{n}.png").stat().st_size:
                o = Image.open(v1 / f"{n}.png")
            else:
                o = Image.new("RGB", (132, 184), (14, 29, 40))
            s.paste(tile(d, o, x, y, "", (58, 72, 84)), (x, y)); x += TW + 12
        p = BASE / ("dress" if not pair else "new") / f"{n}.png"
        s.paste(tile(d, Image.open(p), x, y, "", (63, 198, 224)), (x, y))
        d.text((x - (TW + 12 if pair else 0), y + TH + 6), lab(n) + ("  v1 | new" if pair else "  dressing"), fill=(232, 241, 244), font=F)
    s.save(out); print(out, s.size)

if __name__ == "__main__":
    pre = sys.argv[1]
    sheet(names[:14], pre + "_a.png", True); sheet(names[14:], pre + "_b.png", True)
    sheet([n for n in names if (BASE / "dress" / f"{n}.png").exists()], pre + "_dress.png", False)
