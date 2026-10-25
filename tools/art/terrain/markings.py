#!/usr/bin/env python3
"""T7b (LAN-72): vector road and runway markings for the v3 terrain, rasterised to signed distance fields.

    python3 -I tools/art/terrain/markings.py [--px 384]

For every overlay tile any map uses (game/data/maps/*/terrain.json overlay_texture -> overlays_hd.json slots), a
layout is derived from the tile and written to tools/art/terrain/markings/<cell>.json, then drawn as vectors:

  edge lines   procedural: a band inset from the asphalt outline (the outline's own SDF, smoothed, with the tile
               edges extended so the asphalt runs on across a seam: lines join tile to tile instead of stopping at
               quad borders). Roads 0.35 m in, 0.2 m wide; runways (asphalt wider than 10 m) 0.6 m in, 0.4 m wide.
  marks        every other white or yellow mark of the old tile (lane dashes, threshold piano keys, chevrons, stop
               bars, the yellow runway-side marks) as a polygon: a fitted rectangle where the mark is one (>= 78 % of
               its rotated bounding box), else a simplified outline. The old tile's own edge lines are dropped
               (they are replaced by the procedural ones).
  designators  runway numbers redrawn in Source Sans 3 Bold (SIL OFL 1.1, Adobe), from hand entries in
               DESIGNATORS (text, centre, height, rotation, read off the old tiles), replacing the old glyph pixels.

Output: game/assets/terrain/v3/markings.png, a compact atlas (cells of --px + 2 x 8 px padding, 6.7 cm per texel at
384) with R = white SDF, G = yellow SDF, B = asphalt coverage SDF, A = gravel-track coverage (from the old tile's
alpha); SDF 128 = edge, +-0.3 m over 0..255. markings.json maps old atlas cell -> new cell.
"""
import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import distance_transform_edt, gaussian_filter, label, binary_opening, binary_closing, binary_dilation

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DST = ROOT / "game/assets/terrain/v3"
FONT = "/usr/share/fonts/adobe-source-sans/SourceSans3-Bold.otf"
TILE_M = 25.6
PAD = 8
SPREAD_M = 0.3
# runway designators, read off the old tiles (cell: text, centre (u, v in 0..1 of the tile), glyph height m, rotation
# deg counter-clockwise as it reads in the tile)
DESIGNATORS = {
    77: {"text": "15W", "c": [0.50, 0.66], "h": 4.6, "rot": 180},
    78: {"text": "17N", "c": [0.66, 0.50], "h": 4.6, "rot": 90},
    79: {"text": "72G", "c": [0.50, 0.33], "h": 4.6, "rot": 0},
    80: {"text": "22T", "c": [0.33, 0.50], "h": 4.6, "rot": -90},
}
TAPERED = {396: "v", 397: "h", 398: "v", 399: "h"}   # runway-end tapers: hatched wedges, stripes across the axis
HATCH_PERIOD_M, HATCH_WIDTH_M, HATCH_BORDER_M = 0.9, 0.42, 0.18
IMPORT = """[remap]

importer="texture"
type="CompressedTexture2D"

[params]

compress/mode=2
compress/high_quality=true
mipmaps/generate=true
process/fix_alpha_border=false
detect_3d/compress_to=0
"""


def sdf(mask, m_per_px):
    inside = distance_transform_edt(mask); outside = distance_transform_edt(~mask)
    return np.where(mask, inside - 0.5, -(outside - 0.5)) * m_per_px


def enc(d):
    return np.clip(128 + d / SPREAD_M * 127, 0, 255).astype(np.uint8)


def old_tile(atlas, info, k):
    t, pad, cols = info["tile"], info["pad"], info["cols"]; cell = t + 2 * pad
    x0 = (k % cols) * cell + pad; y0 = (k // cols) * cell + pad
    return atlas[y0:y0 + t, x0:x0 + t].astype(float)


def classify(T):
    al = T[..., 3] / 255; rgb = T[..., :3]; lum = rgb.mean(-1); sat = rgb.max(-1) - rgb.min(-1)
    opaque = al > 0.5
    grey = opaque & (sat < 45)
    asph = binary_opening(binary_closing(grey, iterations=3), iterations=3) & (al > 0.3)
    lb, nl = label(asph)
    if nl:
        sz = np.bincount(lb.ravel()); keep = sz >= 0.02 * asph.size; keep[0] = False; asph = keep[lb]
    base = np.median(lum[asph]) if asph.any() else 80.0
    near = binary_dilation(asph, iterations=3)
    white = near & opaque & (lum > base + 40) & (sat < 70)
    yellow = near & opaque & (rgb[..., 0] > 120) & (rgb[..., 1] > 90) & (rgb[..., 2] < 0.65 * rgb[..., 0])
    asph |= binary_closing(white | yellow, iterations=2) & near
    track = (al > 0.05) & ~binary_dilation(asph, iterations=2)
    return asph, white, yellow, np.where(track, al, 0.0)


def polygons(mask, m_per_px, exclude=None, min_px=6):
    """Marks as polygons (tile metres)."""
    out = []
    lb, n = label(mask)
    for i in range(1, n + 1):
        comp = lb == i
        if comp.sum() < min_px:
            continue
        if exclude is not None and (comp & exclude).sum() > 0.5 * comp.sum():
            continue
        cs, _ = cv2.findContours(comp.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        c = max(cs, key=cv2.contourArea)
        rect = cv2.minAreaRect(c)
        (w_, h_) = rect[1]
        if w_ * h_ > 0 and comp.sum() / (w_ * h_ + 1e-9) >= 0.78:
            pts = cv2.boxPoints(rect)
        else:
            pts = cv2.approxPolyDP(c, 1.1, True)[:, 0, :]
        out.append([[float((x + 0.5) * m_per_px), float((y + 0.5) * m_per_px)] for x, y in pts])
    return out


def layout(atlas, info, k):
    T = old_tile(atlas, info, k)
    t = T.shape[0]; mpp = TILE_M / t
    asph, white, yellow, track = classify(T)
    # the old edge lines: white within 1.0 m of the asphalt outline
    d_in = distance_transform_edt(np.pad(asph, 24, mode="edge"))[24:-24, 24:-24] * mpp
    edge_zone = asph & (d_in < 1.0) | ~asph
    des = DESIGNATORS.get(k)
    excl = edge_zone.copy()
    if des:   # the old glyphs: a box around the designator
        cu, cv_ = des["c"]; hw = des["h"] * 1.2 / TILE_M
        yy, xx = np.mgrid[0:t, 0:t] / t
        r = math.radians(des["rot"]); along = abs(math.cos(r)) * 1.6 + abs(math.sin(r)) * 0.8
        across = abs(math.sin(r)) * 1.6 + abs(math.cos(r)) * 0.8
        excl |= (np.abs(xx - cu) < hw * along) & (np.abs(yy - cv_) < hw * across)
    wide = d_in.max() > 5.0
    # straight tiles: asphalt that crosses the tile from one border to the opposite with a constant width
    straight = None
    for axis in ((0, 1) if not des else ()):   # 0: runs vertically, 1: horizontally (threshold tiles keep their end)
        m = (asph if axis == 0 else asph.T)[8:-8]       # the old tiles stop a few px short of their borders
        cover = m.sum(1)   # asphalt width per row (px)
        if (m[:, :3].any() or m[:, -3:].any()):
            continue        # touches the side borders: a junction or curve
        if cover.min() > 0 and cover.std() < 0.08 * cover.mean():
            cols = np.nonzero(m.any(0))[0]
            straight = {"axis": axis, "width_m": float(np.median(cover) * mpp), "centre_m": float((cols.min() + cols.max() + 1) / 2 * mpp)}
    return {"cell": k, "runway": bool(wide), "white": polygons(white, mpp, excl), "yellow": polygons(yellow, mpp, edge_zone & ~asph),
            "designator": des, "straight": straight, "taper": TAPERED.get(k),
            "edge": None if des else {"inset": 0.6 if wide else 0.35, "width": 0.4 if wide else 0.2}}, asph, track


def raster(lay, asph_old, track_old, px):
    S = 4 * px                       # draw at 4x, SDF there, then box down: straight crisp edges
    mpp = TILE_M / S
    sc = S / TILE_M
    W = Image.new("L", (S, S), 0); Y = Image.new("L", (S, S), 0)
    dw, dy = ImageDraw.Draw(W), ImageDraw.Draw(Y)
    for poly in lay["white"]:
        pts = [(x * sc, y * sc) for x, y in poly]
        area = abs(0.5 * sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1])))
        if lay.get("taper") and area > 3.0:   # a hatched wedge: border plus stripes across the runway axis
            Hm = Image.new("L", (S, S), 0); hd = ImageDraw.Draw(Hm); hd.polygon(pts, fill=255)
            hm = np.asarray(Hm) > 127
            yy, xx = np.mgrid[0:S, 0:S] * mpp
            along = yy if lay["taper"] == "v" else xx
            stripes = (np.mod(along, HATCH_PERIOD_M) < HATCH_WIDTH_M)
            border = hm & (distance_transform_edt(hm) * mpp < HATCH_BORDER_M)
            W = Image.fromarray(np.maximum(np.asarray(W), ((hm & stripes) | border).astype(np.uint8) * 255)); dw = ImageDraw.Draw(W)
        else:
            dw.polygon(pts, fill=255)
    for poly in lay["yellow"]:
        dy.polygon([(x * sc, y * sc) for x, y in poly], fill=255)
    if lay["designator"]:
        de = lay["designator"]
        font = ImageFont.truetype(FONT, int(de["h"] * sc * 1.3))
        tw = int(de["h"] * sc * 3.2)
        g = Image.new("L", (tw, tw), 0); gd = ImageDraw.Draw(g)
        gd.text((tw / 2, tw / 2), de["text"], font=font, fill=255, anchor="mm")
        g = g.rotate(de["rot"], resample=Image.BICUBIC)
        W.paste(255, (int(de["c"][0] * S - tw / 2), int(de["c"][1] * S - tw / 2)), g)
    # asphalt: the old outline, upsampled and smoothed (the source steps are 10 cm), tile edges extended for the seams
    ao = asph_old.copy()
    g = 6   # the old tiles stop a few px short of their borders: run asphalt that nears a border out to it (seams)
    ao[:g] |= ao[g]; ao[-g:] |= ao[-g - 1]; ao[:, :g] |= ao[:, g:g + 1]; ao[:, -g:] |= ao[:, -g - 1:-g]
    A = np.asarray(Image.fromarray((ao * 255).astype(np.uint8)).resize((S, S), Image.BILINEAR)).astype(float) / 255
    sig = 60.0 if lay["runway"] else 14.0      # runway outlines are wavy in the old art: straighten them more
    A = gaussian_filter(np.pad(A.astype(float), 192, mode="edge"), sig)[96:-96, 96:-96] > 0.5
    A = A[96:-96, 96:-96]; A = np.pad(A, 96, mode="edge")
    da = sdf(A, mpp)[96:-96, 96:-96]
    st = lay.get("straight")
    if st and lay.get("canon"):   # exact band at the canonical width for its class, so edges meet tile to tile
        yy, xx = np.mgrid[0:S, 0:S] * mpp + mpp / 2
        across = xx if st["axis"] == 0 else yy
        da = lay["canon"] / 2 - np.abs(across - TILE_M / 2)
    e = lay["edge"]
    edge = (da > e["inset"]) & (da < e["inset"] + e["width"]) if e else np.zeros(da.shape, bool)
    wm = (np.asarray(W) > 127) | edge
    ym = np.asarray(Y) > 127
    dW = sdf(wm, mpp); dY = sdf(ym, mpp)
    # down to px: sample the SDF at the cell centres (keeps distances in metres)
    f = S // px
    pick = lambda d: d[f // 2::f, f // 2::f][:px, :px]
    tr = np.asarray(Image.fromarray((track_old * 255).astype(np.uint8)).resize((px, px), Image.BILINEAR))
    return np.dstack([enc(pick(dW)), enc(pick(dY)), enc(pick(da)), tr])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--px", type=int, default=384); a = ap.parse_args()
    info = json.loads((ROOT / "game/assets/terrain/overlays_hd.json").read_text())
    atlas = np.asarray(Image.open(ROOT / "game/assets/terrain/overlays_hd.webp").convert("RGBA"))
    used = set()
    for f in sorted((ROOT / "game/data/maps").glob("*/terrain.json")):
        for v in json.loads(f.read_text())["overlay_texture"]:
            c = info["slots"].get(str(int(v)))
            if c is not None:
                used.add(c)
    used = sorted(used)
    (HERE / "markings").mkdir(exist_ok=True)
    cols = math.ceil(math.sqrt(len(used))); cellpx = a.px + 2 * PAD
    out = np.zeros((cols * cellpx, cols * cellpx, 4), np.uint8); out[..., :3] = 0
    remap = {}
    lays = {k: layout(atlas, info, k) for k in used}
    # canonical widths: the median straight width per class (road / runway), centred on the tile like the old art
    for cls in (False, True):
        ws = [l["straight"]["width_m"] for l, _, _ in lays.values() if l["straight"] and l["runway"] == cls
              and abs(l["straight"]["centre_m"] - TILE_M / 2) < 1.0]
        if ws:
            cw = float(np.median(ws))
            for l, _, _ in lays.values():
                st = l["straight"]
                if st and l["runway"] == cls and abs(st["centre_m"] - TILE_M / 2) < 1.0 and abs(st["width_m"] - cw) < 0.15 * cw:
                    l["canon"] = cw
            print(("runway" if cls else "road"), "canonical width", round(cw, 2), "m")
    for n, k in enumerate(used):
        lay, asph, track = lays[k]
        (HERE / "markings" / f"{k}.json").write_text(json.dumps(lay))
        img = raster(lay, asph, track, a.px)
        img = np.pad(img, ((PAD, PAD), (PAD, PAD), (0, 0)), mode="edge")
        x0 = (n % cols) * cellpx; y0 = (n // cols) * cellpx
        out[y0:y0 + cellpx, x0:x0 + cellpx] = img
        remap[str(k)] = n
    Image.fromarray(out, "RGBA").save(DST / "markings.png")
    (DST / "markings.png.import").write_text(IMPORT)
    (DST / "markings.json").write_text(json.dumps({"cols": cols, "tile": a.px, "pad": PAD, "spread_m": SPREAD_M, "remap": remap,
                                                   "font": "Source Sans 3 Bold (Adobe), SIL Open Font License 1.1"}, indent=0))
    print(f"markings: {len(used)} tiles, {cols}x{cols} cells of {cellpx} px -> {out.shape}")


if __name__ == "__main__":
    main()
