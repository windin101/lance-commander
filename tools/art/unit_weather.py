#!/usr/bin/env python3
"""Per-mission dust and snow for the v2 unit shader (HD rework, 2026-10-23), read off each map's colour map.

    python3 -I tools/art/unit_weather.py      # writes game/data/unit_weather.json

snow: share of the colour map that is bright and grey (snowfields), scaled so a third of the map in snow is a
full cover on the units' upward faces; dust: 0.25 everywhere, up to 0.7 on bright sandy maps; dust_colour: the
map's median ground colour lifted to a mid tone (a unit picks up the ground it walks on). Hand overrides go in
OVERRIDES below.
"""
import colorsys
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OVERRIDES = {"mc2_13": {"snow": 0.0, "dust": 0.55, "_why": "lunar regolith, grey but not snow"},
             # snow read by eye off the colour-map sheet (the burn-in's shading hides most snowfields from the test)
             "mc2_02": {"snow": 0.25}, "mc2_06": {"snow": 0.6}, "mc2_15": {"snow": 0.35}, "mc2_18": {"snow": 0.45},
             "mc2_20": {"snow": 0.2}}


def main():
    out = {}
    for p in sorted((ROOT / "game/assets/maps").glob("mc2_*/burnin.jpg")):
        a = np.asarray(Image.open(p).convert("RGB").resize((256, 256)), float) / 255.0
        mx, mn = a.max(2), a.min(2)
        snow_px = ((mn > 0.55) & (mx - mn < 0.12)).mean()
        med = np.median(a.reshape(-1, 3), 0)
        h, l, s = colorsys.rgb_to_hls(*med)
        sandy = float(np.clip((l - 0.25) * 3, 0, 1) * np.clip(s * 2.5, 0, 1))
        col = colorsys.hls_to_rgb(h, 0.46, min(s, 0.35))
        m = {"snow": round(float(np.clip(snow_px * 3.0, 0, 1)), 2), "dust": round(0.25 + 0.45 * sandy, 2),
             "dust_colour": "#%02x%02x%02x" % tuple(int(c * 255) for c in col)}
        m.update(OVERRIDES.get(p.parent.name, {}))
        out[p.parent.name] = m
    dst = ROOT / "game/data/unit_weather.json"
    dst.write_text(json.dumps(out, indent=1) + "\n")
    for k, v in out.items():
        print(k, v)


if __name__ == "__main__":
    main()
