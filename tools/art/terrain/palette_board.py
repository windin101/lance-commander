#!/usr/bin/env python3
"""Palette boards for the v3 terrain biomes (T2): each layer's albedo at real scale (a 6 x 6 m patch at 48 px/m, tiled
by the material's physical size; ambientCG's size where it gives one, else an assumed size, marked "~"), its roughness
strip, mean value, and per-map palette proposals scored on colour against the map's original colour map.

    python3 -I tools/art/terrain/palette_board.py [--maps mc2_01 mc2_14]
"""
import argparse, json, os
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import sys
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE)); import delight as D  # noqa
M = Path("/mnt/nvme1n1p1/mc2-rework/terrain/materials"); OUT = Path("/mnt/nvme1n1p1/mc2-rework/terrain/palettes")
PPM, PATCH = 48, 6.0
ASSUME = {"Rock": 300, "Snow": 250, "Ground": 200, "Gravel": 150, "Grass": 140, "Moss": 150, "Concrete": 200}


def layer(i, meta):
    d = M / "1k" / i
    col = next(d / f for f in meta[i]["files"] if "_Color" in f)
    rgh = next((d / f for f in meta[i]["files"] if "_Roughness" in f), None)
    cm = meta[i]["dim_cm"][0]
    known = cm > 0
    if not known:
        cm = next(v for k, v in ASSUME.items() if i.startswith(k))
    return Image.open(col).convert("RGB"), (Image.open(rgh).convert("L") if rgh else None), cm, known


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--maps", nargs="*", default=["mc2_01", "mc2_14"]); a = ap.parse_args()
    P = json.loads((HERE / "palettes.json").read_text()); meta = json.loads((M / "palette_meta.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    side = int(PATCH * PPM); stats = {}
    for b, slots in P["biomes"].items():
        W = 8 * (side + 12) + 12; Hh = side + 120
        s = Image.new("RGB", (W, Hh), (24, 24, 28)); dr = ImageDraw.Draw(s)
        dr.text((12, 6), f"{b}: 6 x 6 m patches at real scale (48 px/m); ambientCG, CC0 1.0", fill=(255, 255, 255))
        bs = {}
        for k, slot in enumerate(P["slots"]):
            i = slots[slot]; col, rgh, cm, known = layer(i, meta)
            tpx = max(8, int(round(cm / 100 * PPM)))
            tile = col.resize((tpx, tpx), Image.LANCZOS)
            patch = Image.new("RGB", (side, side))
            for y in range(0, side, tpx):
                for x in range(0, side, tpx):
                    patch.paste(tile, (x, y))
            x0 = 12 + k * (side + 12); s.paste(patch, (x0, 30))
            arr = np.asarray(col.resize((256, 256))).astype(float); lab = D.srgb_to_lab(arr).reshape(-1, 3).mean(0)
            rv = float(np.asarray(rgh).mean() / 255) if rgh else None
            if rgh:
                s.paste(rgh.resize((side, 14)).convert("RGB"), (x0, 30 + side + 2))
            dr.text((x0, 30 + side + 20), f"{slot}: {i}", fill=(255, 255, 255))
            dr.text((x0, 30 + side + 36), f"tile {'' if known else '~'}{cm / 100:.1f} m  L {lab[0]:.0f}  rough {rv:.2f}" if rv is not None else f"tile {cm/100:.1f} m L {lab[0]:.0f}", fill=(200, 200, 200))
            dr.text((x0, 30 + side + 52), meta[i]["name"], fill=(160, 160, 160))
            bs[slot] = {"id": i, "lab": lab.round(1).tolist(), "rough": round(rv, 3) if rv else None, "tile_m": cm / 100, "tile_known": known}
        s.save(OUT / f"board_{b}.jpg", quality=90); stats[b] = bs
    # proposals: expected visible colour of each palette (class shares from splat_stats) against the original colour map
    props = {}
    for m in a.maps:
        sp = json.loads(Path(f"/mnt/nvme1n1p1/mc2-rework/terrain/{m}/splat_stats.json").read_text())
        # night maps were burnt dark and blue: score them on the de-lit colour (T1 low-pass), daylight maps on the original
        cam = json.loads((ROOT / f"game/data/missions/{m}.json").read_text())["Cameras"]
        night = not (5.0 < float(cam.get("LightDirPitch", 50)) < 175.0) or max(cam.get("LightRed", 255), cam.get("LightGreen", 255)) < 140
        src_img = Path(f"/mnt/nvme1n1p1/mc2-rework/terrain/{m}/albedo_macro_lowfreq.png") if night else ROOT / f"game/assets/maps/{m}/burnin.jpg"
        orig = np.asarray(Image.open(src_img).convert("RGB").resize((256, 256))).astype(float)
        olab = D.srgb_to_lab(orig).reshape(-1, 3).mean(0)
        wx = json.loads((ROOT / "game/data/unit_weather.json").read_text()).get(m, {})
        sc = {}
        for b, bs in stats.items():
            exp = sum(sp["classes_share"][sl] * np.array(bs[sl]["lab"]) for sl in P["slots"])
            dab = float(np.hypot(exp[1] - olab[1], exp[2] - olab[2]))       # hue/chroma distance (value is relit anyway)
            pen = 0.0
            if b == "snow" and wx.get("snow", 0) < 0.2: pen += 40
            if b != "snow" and wx.get("snow", 0) >= 0.5: pen += 40
            sc[b] = round(dab + pen, 1)
        rk = sorted(sc, key=sc.get)
        props[m] = {"night": bool(night), "original_lab": olab.round(1).tolist(), "score_ab_distance": sc, "proposed": rk[0], "runner_up": rk[1]}
    (OUT / "boards_stats.json").write_text(json.dumps({"layers": stats, "proposals": props}, indent=1))
    src = {i: {"source": f"{meta[i]['name']} ({i}) by ambientCG.com (CC0 1.0), https://ambientcg.com/view?id={i}", "tile_cm": meta[i]["dim_cm"][0] or None}
           for i in sorted({v for b in P["biomes"].values() for v in b.values()})}
    (M / "sources.json").write_text(json.dumps(src, indent=1))
    print(json.dumps(props, indent=1))


if __name__ == "__main__":
    main()
