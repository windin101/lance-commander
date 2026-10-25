#!/usr/bin/env python3
"""One combined palette proposal sheet for a rollout batch (for Lee's sign-off): per map a row with the original
colour map, the class map (terrain_splat.py splat_debug.png), and the proposed and runner-up palette boards
(palette_board.py), with the colour scores. python3 -I tools/art/terrain/proposal_sheet.py OUT.jpg mc2_04 mc2_05 ..."""
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw
ROOT = Path(__file__).resolve().parents[3]; T = Path("/mnt/nvme1n1p1/mc2-rework/terrain")
out, maps = sys.argv[1], sys.argv[2:]
st = json.loads((T / "palettes/boards_stats.json").read_text())["proposals"]
S = 560; BW = 1500
rows = []
for m in maps:
    p = st[m]
    o = Image.open(ROOT / f"game/assets/maps/{m}/burnin.jpg").convert("RGB").resize((S, S))
    c = Image.open(T / m / "splat_debug.png").convert("RGB").resize((S, S))
    b1 = Image.open(T / f"palettes/board_{p['proposed']}.jpg"); b2 = Image.open(T / f"palettes/board_{p['runner_up']}.jpg")
    b1 = b1.resize((BW, int(b1.height * BW / b1.width))); b2 = b2.resize((BW, int(b2.height * BW / b2.width)))
    H = max(S, b1.height + b2.height + 40) + 40
    r = Image.new("RGB", (2 * S + BW + 40, H), (22, 22, 26)); d = ImageDraw.Draw(r)
    wx = json.loads((ROOT / "game/data/unit_weather.json").read_text()).get(m, {})
    d.text((10, 8), f"{m}   proposed: {p['proposed']}   runner-up: {p['runner_up']}   (colour score {p['score_ab_distance'][p['proposed']]} vs "
           f"{p['score_ab_distance'][p['runner_up']]}; snow {wx.get('snow')}, dust {wx.get('dust')}{', NIGHT map: scored on de-lit colour' if p.get('night') else ''})", fill=(255, 255, 255))
    r.paste(o, (10, 34)); r.paste(c, (S + 20, 34))
    d.text((10, 34 + S + 2), "original colour map", fill=(200, 200, 200)); d.text((S + 20, 34 + S + 2), "class map", fill=(200, 200, 200))
    r.paste(b1, (2 * S + 30, 34)); d.text((2 * S + 30, 34 + b1.height + 2), "runner-up:", fill=(255, 220, 120))
    r.paste(b2, (2 * S + 30, 54 + b1.height))
    rows.append(r)
W = max(r.width for r in rows); sheet = Image.new("RGB", (W, sum(r.height for r in rows)), (22, 22, 26)); y = 0
for r in rows:
    sheet.paste(r, (0, y)); y += r.height
sheet.save(out, quality=88); print(out, sheet.size)
