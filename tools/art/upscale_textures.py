#!/usr/bin/env python3
"""HD textures for the original map objects and road tiles: 4x RealESRGAN upscales of the original art.

    <ComfyUI venv>/bin/python tools/art/upscale_textures.py [--only a,b] [--tiles]
    (needs torch + spandrel: run it with ComfyUI's venv; the swarm GPU lock is taken by the caller)

The original buildings, props and walls are faithful, boxy shapes; what reads as low-res is their 128 px
textures. For every converted object (game/assets/objects/<app>.glb and <app>_dam.glb, not trees, not the
Hunyuan *_hd models) this upscales each embedded texture 4x with RealESRGAN x4plus (BSD-3, by Xintao Wang et
al.), the alpha channel separately (bicubic, so cut-outs keep their shape), and writes <app>_hdtex.glb (and
<app>_dam_hdtex.glb) with the same geometry. objects_view.gd prefers it. --tiles does the same to the road /
runway / cement overlay atlas (assets/terrain/overlays.png -> overlays_hd.webp, 64 -> 256 px tiles; cut-out textures are then converted to WebP (EXT_texture_webp) by the
same pass the session used, see docs/terrain-rendering.md).
The outputs derive from the Shared Source art and stay under its non-commercial terms.
"""
import argparse
import io
import json
import struct
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
MODEL = "/mnt/nvme1n1p1/StabilityMatrix/linux-x64/Data/Models/RealESRGAN/RealESRGAN_x4plus.pth"


def load_glb(path):
    data = Path(path).read_bytes()
    jl = struct.unpack_from("<I", data, 12)[0]
    gltf = json.loads(data[20:20 + jl])
    off = 20 + jl
    bl = struct.unpack_from("<I", data, off)[0]
    return gltf, bytearray(data[off + 8:off + 8 + bl])


def write_glb(path, gltf, binary):
    while len(binary) % 4:
        binary.append(0)
    gltf["buffers"] = [{"byteLength": len(binary)}]
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    Path(path).write_bytes(struct.pack("<III", 0x46546C67, 2, 28 + len(js) + len(binary)) + struct.pack("<II", len(js), 0x4E4F534A)
                           + js + struct.pack("<II", len(binary), 0x004E4942) + bytes(binary))


class Upscaler:
    def __init__(self):
        import spandrel
        self.m = spandrel.ModelLoader().load_from_file(MODEL).model.eval().cuda().half()

    @torch.no_grad()
    def rgb(self, im):
        a = torch.from_numpy(np.asarray(im.convert("RGB"))).float().div(255).permute(2, 0, 1)[None].cuda().half()
        # pad by reflection so tiling textures keep clean edges, then crop back
        p = 8
        a = torch.nn.functional.pad(a, (p, p, p, p), mode="circular")
        out = self.m(a)[0, :, 4 * p:-4 * p, 4 * p:-4 * p].clamp(0, 1).float().permute(1, 2, 0).cpu().numpy()
        return Image.fromarray((out * 255 + 0.5).astype(np.uint8))

    def image(self, im):
        big = self.rgb(im)
        if im.mode in ("RGBA", "LA") or "transparency" in im.info:
            a = im.convert("RGBA").getchannel("A").resize(big.size, Image.BICUBIC)
            big.putalpha(a)
        return big


def upscale_glb(up, src, dst):
    gltf, binary = load_glb(src)
    if not gltf.get("images"):
        return False
    new_bin = bytearray(binary)
    for img in gltf["images"]:
        v = gltf["bufferViews"][img["bufferView"]]
        o = v.get("byteOffset", 0)
        im = Image.open(io.BytesIO(bytes(binary[o:o + v["byteLength"]])))
        im.load()
        big = up.image(im)
        b = io.BytesIO()
        if big.mode == "RGBA" and big.getchannel("A").getextrema()[0] < 250:  # cut-outs keep PNG; opaque textures go JPEG (glTF image/jpeg): a fifth the size
            big.save(b, "PNG", optimize=True)
            mime = "image/png"
        else:
            big.save(b, "JPEG", quality=90, optimize=True)
            mime = "image/jpeg"
        data = b.getvalue()
        while len(new_bin) % 4:
            new_bin.append(0)
        gltf["bufferViews"].append({"buffer": 0, "byteOffset": len(new_bin), "byteLength": len(data)})
        new_bin.extend(data)
        img["bufferView"] = len(gltf["bufferViews"]) - 1
        img["mimeType"] = mime
    write_glb(dst, gltf, new_bin)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--tiles", action="store_true")
    a = ap.parse_args()
    up = Upscaler()
    trees = set(json.loads((ROOT / "game/assets/trees/trees.json").read_text())["types"])
    only = set(a.only.split(",")) if a.only else None
    n = 0
    for p in sorted((ROOT / "game/assets/objects").glob("*.glb")):
        stem = p.stem
        if stem.endswith(("_hd", "_hdtex")) or stem in trees:
            continue
        base = stem[:-4] if stem.endswith("_dam") else stem
        if only and base not in only:
            continue
        dst = p.with_name(stem + "_hdtex.glb")
        if dst.exists() and dst.stat().st_mtime > p.stat().st_mtime:
            continue
        if upscale_glb(up, p, dst):
            n += 1
    print(f"objects: {n} upscaled")
    if a.tiles:
        src = ROOT / "game/assets/terrain/overlays.png"
        info = json.loads((ROOT / "game/assets/terrain/overlays.json").read_text())
        atlas = Image.open(src).convert("RGBA")
        cell = info["tile"] + 2 * info["pad"]
        cols, rows = info["cols"], info["rows"]
        T, P = info["tile"] * 4, info["pad"] * 4
        out = Image.new("RGBA", (cols * (T + 2 * P), rows * (T + 2 * P)), (0, 0, 0, 0))
        for r in range(rows):
            for c in range(cols):
                tile = atlas.crop((c * cell + info["pad"], r * cell + info["pad"], c * cell + info["pad"] + info["tile"], r * cell + info["pad"] + info["tile"]))
                if not np.asarray(tile).any():  # empty cell (cement tiles have alpha 0 but colour)
                    continue
                big = up.image(tile)
                padded = Image.fromarray(np.pad(np.asarray(big), ((P, P), (P, P), (0, 0)), mode="edge"))
                out.paste(padded, (c * (T + 2 * P), r * (T + 2 * P)))
        out.save(ROOT / "game/assets/terrain/overlays_hd.webp", "WEBP", quality=90, method=6, alpha_quality=100)
        info_hd = dict(info, tile=T, pad=P)
        (ROOT / "game/assets/terrain/overlays_hd.json").write_text(json.dumps(info_hd, indent=0))
        print("tiles:", out.size)


if __name__ == "__main__":
    main()
