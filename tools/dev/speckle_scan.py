"""Speckle-square scanner (phase 8). Usage:
  python3 -I tools/dev/speckle_scan.py <clip.avi | png dir> [B]
B is the square size in output pixels: 8 for a 1920x1080 render, 12 for a 1280x720 render recorded into a
1920x1080 movie. Pair with game/tools/speckle_probe.tscn. Validated on the 2026-10-23 fx-range clips (13 % of
frames flagged in v3np/idle.avi) and clean on 2026-10-24 captures of the same code.

Find grid-aligned solid squares (B x B px, B = 8 or 12) whose colour differs sharply from the pixels just
outside them: the signature of the speckle squares. Input: an AVI (decoded with ffmpeg) or a PNG directory.
Prints per-clip totals and the worst frames."""
import sys, glob, os, subprocess
import numpy as np
from PIL import Image

def frames(src, w=1920, h=1080):
    if os.path.isdir(src):
        for f in sorted(glob.glob(os.path.join(src, "*.png"))):
            yield os.path.basename(f), np.asarray(Image.open(f).convert("RGB")).astype(np.float32)
        return
    p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-i", src, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    i = 0
    while True:
        b = p.stdout.read(w * h * 3)
        if len(b) < w * h * 3: break
        yield i, np.frombuffer(b, np.uint8).reshape(h, w, 3).astype(np.float32); i += 1

def squares(a, B):
    h, w, _ = a.shape
    H, W = h // B, w // B
    t = a[:H * B, :W * B].reshape(H, B, W, B, 3)
    inner = t[:, 2:B - 2, :, 2:B - 2]            # core of the block
    mean = inner.mean((1, 3))
    std = inner.std((1, 3)).max(-1)
    # ring: the mean of the 4 neighbouring blocks' cores
    pad = np.pad(mean, ((1, 1), (1, 1), (0, 0)), mode="edge")
    ring = (pad[:-2, 1:-1] + pad[2:, 1:-1] + pad[1:-1, :-2] + pad[1:-1, 2:]) / 4
    nstd = np.pad(std, 1, mode="edge")
    calm = np.maximum.reduce([nstd[:-2, 1:-1], nstd[2:, 1:-1], nstd[1:-1, :-2], nstd[1:-1, 2:]])
    nb = [pad[:-2, 1:-1], pad[2:, 1:-1], pad[1:-1, :-2], pad[1:-1, 2:]]
    diff = np.minimum.reduce([np.abs(mean - q).max(-1) for q in nb])  # isolated: unlike every neighbour
    r, g, b = mean[..., 0], mean[..., 1], mean[..., 2]
    green = (g > r + 40) & (g > b + 40)
    yellow = (r > b + 60) & (g > b + 60) & (np.abs(r - g) < 50)
    black = mean.max(-1) < 25
    hit = (std < 12) & (calm < 20) & (diff > 45) & (green | yellow | black)
    return hit

src = sys.argv[1]
B = int(sys.argv[2]) if len(sys.argv) > 2 else 8
res = []
for k, a in frames(src):
    res.append((k, int(squares(a, B).sum())))
n = np.array([c for _, c in res])
bad = [(k, c) for k, c in res if c >= 3]
print(f"{src} B={B}: {len(res)} frames, {len(bad)} with >=3 squares ({100*len(bad)/max(len(res),1):.1f}%), max {n.max() if len(n) else 0}")
print("  worst", sorted(bad, key=lambda x: -x[1])[:10])
