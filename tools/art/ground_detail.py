#!/usr/bin/env python3
"""Ground detail layers for the terrain shader (world-rendering step 2) from CC0 ambientCG materials.

    python3 -I tools/art/ground_detail.py [--src ~/craft/solid/mc2/ground_cc0]

The colour map keeps every map's own colour; these layers only add fine structure up close. For each ground
class (grass, dirt, rock, sand, snow) this writes game/assets/terrain/detail/<class>_l.png (the material's
luminance high-passed against a wide blur, so 128 = no change: brighter and darker grain only) and
<class>_n.jpg (its OpenGL normal map), 1024 px, tiling. Sources are CC0 1.0 (ambientCG.com); credited in
CREDITS.md anyway.
"""
import argparse
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
CLASSES = {"grass": "Grass004", "dirt": "Ground037", "rock": "Rock058", "sand": "Ground054", "snow": "Snow006"}


def tile_blur(a, r):
    """Gaussian blur of a tiling image (wrap-around edges)."""
    from scipy.ndimage import gaussian_filter
    return gaussian_filter(a, r, mode="wrap")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.expanduser("~/craft/solid/mc2/ground_cc0"))
    ap.add_argument("--size", type=int, default=1024)
    a = ap.parse_args()
    out = ROOT / "game/assets/terrain/detail"
    out.mkdir(parents=True, exist_ok=True)
    meta = {}
    for cls, asset in CLASSES.items():
        col = Image.open(f"{a.src}/{asset}/{asset}_1K-JPG_Color.jpg").convert("RGB").resize((a.size, a.size), Image.LANCZOS)
        nrm = Image.open(f"{a.src}/{asset}/{asset}_1K-JPG_NormalGL.jpg").convert("RGB").resize((a.size, a.size), Image.LANCZOS)
        c = np.asarray(col).astype(np.float32) / 255.0
        L = 0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]
        low = tile_blur(L, a.size / 16)
        hp = L / np.maximum(low, 1e-3) - 1.0  # relative grain: -0.3 .. +0.3 typically
        k = 0.35 / max(1e-3, np.percentile(np.abs(hp), 98))  # normalise each class to a similar strength
        v = np.clip(128 + hp * k * 255, 0, 255).astype(np.uint8)
        Image.fromarray(v, "L").save(out / f"{cls}_l.png")
        nrm.save(out / f"{cls}_n.jpg", quality=92)
        meta[cls] = {"source": f"{asset} by ambientCG.com (CC0 1.0), https://ambientcg.com/view?id={asset}"}
        print(cls, asset, "grain sd", round(float(hp.std()), 3))
    (out / "sources.json").write_text(json.dumps(meta, indent=1) + "\n")


if __name__ == "__main__":
    main()
