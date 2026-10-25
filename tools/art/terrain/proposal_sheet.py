#!/usr/bin/env python3
"""One combined palette proposal sheet for a rollout batch (for Lee's sign-off): per map a row with the original
colour map, the class map (terrain_splat.py splat_debug.png), and the proposed and runner-up palette boards
(palette_board.py), with the colour scores.

    python3 -I tools/art/terrain/proposal_sheet.py OUT.jpg mc2_04 mc2_05 ... [--picks picks.json]

The automatic colour score (Lab a/b distance) picks wrong on grassy and dark maps, so --picks gives the reviewer's
own choice per map: {"mc2_02": {"proposed": "temperate_muted", "palette2": "snow", "runner_up": "...",
"note": "one line why"}}. A pick with palette2 also shows the snow mask (terrain_pack.mask2 preview, written to
<work>/<map>/mask2_preview/mask2.png) in place of a third board. The auto pick is always printed beside it."""
import argparse, json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT = Path(__file__).resolve().parents[3]; T = Path("/mnt/nvme1n1p1/mc2-rework/terrain")
ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("maps", nargs="+"); ap.add_argument("--picks")
a = ap.parse_args()
st = json.loads((T / "palettes/boards_stats.json").read_text())["proposals"]
picks = json.loads(Path(a.picks).read_text()) if a.picks else {}
S = 560; BW = 1500


def font(sz):
    for f in ("/usr/share/fonts/TTF/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf"):
        if Path(f).exists():
            return ImageFont.truetype(f, sz)
    return ImageFont.load_default()


F1, F2 = font(22), font(17)


def board(name):
    b = Image.open(T / f"palettes/board_{name}.jpg")
    return b.resize((BW, int(b.height * BW / b.width)))


rows = []
for m in a.maps:
    p = st[m]; pk = picks.get(m, {})
    prop, run = pk.get("proposed", p["proposed"]), pk.get("runner_up", p["runner_up"])
    pal2 = pk.get("palette2")
    sc = p["score_ab_distance"]
    o = Image.open(ROOT / f"game/assets/maps/{m}/burnin.jpg").convert("RGB").resize((S, S))
    c = Image.open(T / m / "splat_debug.png").convert("RGB").resize((S, S))
    boards = [("proposed: " + prop, board(prop))]
    if pal2:
        boards.append((f"second palette (mask2 = snow): {pal2}", board(pal2)))
    boards.append(("runner-up: " + run, board(run)))
    head = 74
    H = max(S + 30, sum(b.height + 28 for _, b in boards), (2 * S + 60) if pal2 else 0) + head + 10
    r = Image.new("RGB", (2 * S + BW + 40, H), (22, 22, 26)); d = ImageDraw.Draw(r)
    wx = json.loads((ROOT / "game/data/unit_weather.json").read_text()).get(m, {})
    title = f"{m}   PROPOSED: {prop}{' + ' + pal2 + ' (mixed)' if pal2 else ''}   runner-up: {run}"
    d.text((10, 6), title, fill=(255, 255, 255), font=F1)
    auto = (f"auto colour score: {p['proposed']} {sc[p['proposed']]}, {p['runner_up']} {sc[p['runner_up']]}"
            f"{'' if not pk else f'; my pick {prop} scored {sc.get(prop)}'}   snow {wx.get('snow')}, dust {wx.get('dust')}"
            f"{'   NIGHT key: scored on de-lit colour' if p.get('night') else ''}")
    d.text((10, 34), auto, fill=(190, 190, 190), font=F2)
    if pk.get("note"):
        d.text((10, 54), pk["note"], fill=(255, 220, 120), font=F2)
    y0 = head
    r.paste(o, (10, y0)); r.paste(c, (S + 20, y0))
    d.text((10, y0 + S + 4), "original colour map", fill=(200, 200, 200), font=F2)
    d.text((S + 20, y0 + S + 4), "class map", fill=(200, 200, 200), font=F2)
    if pal2:
        mk = T / m / "mask2_preview/mask2.png"
        if mk.exists():
            # the snow mask over the original, under it
            ms = Image.open(mk).convert("RGB").getchannel("R").resize((S, S))
            ov = Image.composite(Image.new("RGB", (S, S), (80, 170, 255)), o, ms.point(lambda v: int(v * 0.7)))
            if H >= y0 + 2 * S + 60:
                r.paste(ov, (10, y0 + S + 30)); d.text((10, y0 + 2 * S + 32), "snow mask2 (blue) over the original", fill=(200, 200, 200), font=F2)
    x, y = 2 * S + 30, y0
    for lab, b in boards:
        d.text((x, y), lab, fill=(255, 220, 120), font=F2); r.paste(b, (x, y + 22)); y += b.height + 28
    rows.append(r)
W = max(r.width for r in rows); sheet = Image.new("RGB", (W, sum(r.height for r in rows) + 4 * len(rows)), (60, 60, 66)); y = 0
for r in rows:
    sheet.paste(r, (0, y)); y += r.height + 4
sheet.save(a.out, quality=88); print(a.out, sheet.size)
