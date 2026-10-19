#!/usr/bin/env python3
"""Shrink glb textures: opaque ones to JPEG, cut-outs to lossy WebP with alpha (glTF EXT_texture_webp,
which Godot imports). Same geometry and look; about a seventh of the size.

    python3 -I tools/art/glb_webp.py game/assets/objects/*_hdtex.glb
"""
import io
import json
import struct
import sys
from pathlib import Path
from PIL import Image
def load_glb(path):
    data = Path(path).read_bytes(); jl = struct.unpack_from("<I", data, 12)[0]
    g = json.loads(data[20:20 + jl]); off = 20 + jl; bl = struct.unpack_from("<I", data, off)[0]
    return g, bytearray(data[off + 8:off + 8 + bl])
def write_glb(path, g, b):
    while len(b) % 4: b.append(0)
    g["buffers"] = [{"byteLength": len(b)}]; js = json.dumps(g, separators=(",", ":")).encode(); js += b" " * (-len(js) % 4)
    Path(path).write_bytes(struct.pack("<III", 0x46546C67, 2, 28 + len(js) + len(b)) + struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(b), 0x004E4942) + bytes(b))

# PNG cut-outs -> WebP (lossy, alpha kept) through EXT_texture_webp
n = 0
files = sys.argv[1:]
for p in files:
    g, b = load_glb(p); blobs = {}; changed = False
    for k, img in enumerate(g.get("images", [])):
        v = g["bufferViews"][img["bufferView"]]; o = v.get("byteOffset", 0); raw = bytes(b[o:o + v["byteLength"]])
        if img.get("mimeType") == "image/png":
            im = Image.open(io.BytesIO(raw)); im.load(); out = io.BytesIO(); im.convert("RGBA").save(out, "WEBP", quality=90, method=6, alpha_quality=100); raw = out.getvalue(); img["mimeType"] = "image/webp"; changed = True
        blobs[k] = raw
    if not changed: continue
    for t in g.get("textures", []):
        src = t.get("source")
        if src is not None and g["images"][src]["mimeType"] == "image/webp":
            t.pop("source"); t.setdefault("extensions", {})["EXT_texture_webp"] = {"source": src}
    if any(i["mimeType"] == "image/webp" for i in g["images"]):
        g["extensionsUsed"] = sorted(set(g.get("extensionsUsed", [])) | {"EXT_texture_webp"})
        g["extensionsRequired"] = sorted(set(g.get("extensionsRequired", [])) | {"EXT_texture_webp"})
    out = bytearray(); views = []; vmap = {}
    for k in sorted({a["bufferView"] for a in g["accessors"] if "bufferView" in a}):
        v = dict(g["bufferViews"][k]); o = v.get("byteOffset", 0); d = bytes(b[o:o + v["byteLength"]])
        while len(out) % 4: out.append(0)
        v["byteOffset"] = len(out); out.extend(d); vmap[k] = len(views); views.append(v)
    for k, img in enumerate(g["images"]):
        while len(out) % 4: out.append(0)
        views.append({"buffer": 0, "byteOffset": len(out), "byteLength": len(blobs[k])}); out.extend(blobs[k]); img["bufferView"] = len(views) - 1
    for a in g["accessors"]:
        if "bufferView" in a: a["bufferView"] = vmap[a["bufferView"]]
    g["bufferViews"] = views; write_glb(p, g, out); n += 1
print("webp", n)
