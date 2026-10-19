#!/usr/bin/env python3
"""Contact sheet of STL files: three-quarter flat-shaded renders with sizes, for picking third-party sculpts.

    python3 -I tools/art/stl_sheet.py out.png "label=path.stl" [...]

Raw STL frame (mm, Z up). Keeps the 120k largest triangles of big files so it stays quick.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stl_rig as S  # noqa: E402


def main():
    out, specs = sys.argv[1], sys.argv[2:]
    tiles = []
    for sp in specs:
        lab, f = sp.split("=", 1)
        T = S.load_stl(f)
        if len(T) > 120000:
            a = np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1)
            T = T[np.argsort(-a)[:120000]]
        ext = np.ptp(T.reshape(-1, 3), 0)
        T = T - T.reshape(-1, 3).min(0) - ext / 2
        a, b = np.radians(35), np.radians(25)
        Rz = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
        Rx = np.array([[1, 0, 0], [0, np.cos(b), -np.sin(b)], [0, np.sin(b), np.cos(b)]])
        P = (T.reshape(-1, 3) @ (Rx @ Rz).T).reshape(-1, 3, 3)
        lo, hi = P.reshape(-1, 3).min(0), P.reshape(-1, 3).max(0)
        k = 380 / max(hi[0] - lo[0], hi[2] - lo[2])
        P[:, :, 2] -= lo[2]
        im, _ = S.shade_render(P, 0, 2, 1, -1, lo[0], hi[0], hi[2] - lo[2], k, int((hi[2] - lo[2]) * k) + 20)
        tile = Image.new("RGB", (420, 440), "white")
        im.thumbnail((400, 400))
        tile.paste(im, (10, 10))
        ImageDraw.Draw(tile).text((8, 418), f"{lab}  {ext[0]:.0f}x{ext[1]:.0f}x{ext[2]:.0f} mm", fill="black")
        tiles.append(tile)
    cols = 5
    sheet = Image.new("RGB", (420 * cols, 440 * ((len(tiles) + cols - 1) // cols)), "white")
    for i, t in enumerate(tiles):
        sheet.paste(t, (420 * (i % cols), 440 * (i // cols)))
    sheet.save(out)
    print(out, len(tiles))


if __name__ == "__main__":
    main()
