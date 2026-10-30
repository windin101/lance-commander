#!/usr/bin/env python3
"""Pin an edited render's outline to its source render (image-to-3D input prep).
    python3 -I tools/art/v3/silhouette_lock.py SRC.png EDIT.png OUT.png
Edit models (Qwen-Image-Edit) keep the layout but drift the outline by 10-25 %. Outside the source silhouette the
result is white; inside it, pixels the edit left white keep the source render. Prints the IoU before pinning."""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi


def mask(a):
    m = ndi.binary_opening(a < 238, iterations=2)
    return ndi.binary_fill_holes(m)


src = Image.open(sys.argv[1]).convert("RGB")
ed = Image.open(sys.argv[2]).convert("RGB").resize(src.size, Image.LANCZOS)
s, e = np.asarray(src, float), np.asarray(ed, float)
ms, me = mask(s.mean(2)), mask(e.mean(2))
print("IoU before pinning", round((ms & me).sum() / (ms | me).sum(), 3))
out = e.copy()
hole = ms & (e.mean(2) >= 238)
out[hole] = s[hole]      # where the edit left a gap inside the silhouette, keep the source render's pixels
soft = ndi.gaussian_filter(ms.astype(float), 1.0)[..., None]
out = out * soft + 255 * (1 - soft)
Image.fromarray(out.clip(0, 255).astype(np.uint8)).save(sys.argv[3])
