"""Minimal ComfyUI API client for the HD-art pipeline (after race-into-space's
tools/comfy_batch.py). Server: $COMFY_SERVER or http://127.0.0.1:8189."""

import io
import json
import os
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from PIL import Image

SERVER = os.environ.get("COMFY_SERVER", "http://127.0.0.1:8189")
CLIENT = str(uuid.uuid4())
QWEN = {"edit": "qwen_image_edit_2509_fp8_e4m3fn.safetensors", "clip": "qwen_2.5_vl_7b_fp8_scaled.safetensors",
        "vae": "qwen_image_vae.safetensors"}
SAMPLING = {"steps": 20, "cfg": 2.5, "sampler": "euler", "scheduler": "simple", "shift": 3.0}


def api(path, data=None, timeout=60):
    url = SERVER + path
    if data is None:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read())
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def upload(path):
    path = Path(path)
    b = uuid.uuid4().hex
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{path.name}\"\r\nContent-Type: image/png\r\n\r\n").encode() \
        + path.read_bytes() + f"\r\n--{b}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(SERVER + "/upload/image", data=body, headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["name"]


def run(graph, timeout=1800):
    """Submit a graph; return the history entry's outputs once done."""
    pid = api("/prompt", {"prompt": graph, "client_id": CLIENT})["prompt_id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        hist = api(f"/history/{pid}")
        if pid in hist:
            entry = hist[pid]
            st = entry.get("status", {})
            if st.get("status_str") == "error":
                raise RuntimeError("ComfyUI error: " + json.dumps(st.get("messages", []))[:1500])
            if st.get("completed"):
                return entry.get("outputs", {})
        time.sleep(2.0)
    raise TimeoutError("ComfyUI job did not finish")


def fetch(file_info):
    q = urllib.parse.urlencode({"filename": file_info["filename"], "subfolder": file_info.get("subfolder", ""),
                                "type": file_info.get("type", "output")})
    with urllib.request.urlopen(f"{SERVER}/view?{q}", timeout=300) as r:
        return r.read()


def images(outputs):
    out = []
    for node in outputs.values():
        for im in node.get("images", []):
            out.append(Image.open(io.BytesIO(fetch(im))).convert("RGBA"))
    return out


def edit_graph(image_name, prompt, negative, seed, size=1024):
    m, s = QWEN, SAMPLING
    mp = round(size * size / 1e6, 2)
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": m["edit"], "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": m["clip"], "type": "qwen_image"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": m["vae"]}},
        "4": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "5": {"class_type": "ImageScaleToTotalPixels", "inputs": {"image": ["4", 0], "upscale_method": "lanczos", "megapixels": mp, "resolution_steps": 16}},
        "6": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {"clip": ["2", 0], "prompt": prompt, "vae": ["3", 0], "image1": ["5", 0]}},
        "7": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {"clip": ["2", 0], "prompt": negative, "vae": ["3", 0], "image1": ["5", 0]}},
        "8": {"class_type": "VAEEncode", "inputs": {"pixels": ["5", 0], "vae": ["3", 0]}},
        "9": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["1", 0], "shift": s["shift"]}},
        "10": {"class_type": "CFGNorm", "inputs": {"model": ["9", 0], "strength": 1.0}},
        "11": {"class_type": "KSampler", "inputs": {"model": ["10", 0], "seed": seed, "steps": s["steps"], "cfg": s["cfg"],
               "sampler_name": s["sampler"], "scheduler": s["scheduler"], "positive": ["6", 0], "negative": ["7", 0],
               "latent_image": ["8", 0], "denoise": 1.0}},
        "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["3", 0]}},
        "13": {"class_type": "SaveImage", "inputs": {"images": ["12", 0], "filename_prefix": "lc/edit"}},
    }


def hunyuan3d_graph(image_name, seed, prefix="lc/mesh", steps=30, cfg=5.0, octree=256, threshold=0.6):
    """Image -> mesh with Hunyuan3D 2.1 (ComfyUI's 'Image to Model' blueprint settings)."""
    return {
        "1": {"class_type": "ImageOnlyCheckpointLoader", "inputs": {"ckpt_name": "hunyuan_3d_v2.1.safetensors"}},
        "2": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "3": {"class_type": "CLIPVisionEncode", "inputs": {"clip_vision": ["1", 1], "image": ["2", 0], "crop": "center"}},
        "4": {"class_type": "Hunyuan3Dv2Conditioning", "inputs": {"clip_vision_output": ["3", 0]}},
        "5": {"class_type": "EmptyLatentHunyuan3Dv2", "inputs": {"resolution": 4096, "batch_size": 1}},
        "6": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["1", 0], "shift": 1.0}},
        "7": {"class_type": "KSampler", "inputs": {"model": ["6", 0], "seed": seed, "steps": steps, "cfg": cfg,
              "sampler_name": "euler", "scheduler": "normal", "positive": ["4", 0], "negative": ["4", 1],
              "latent_image": ["5", 0], "denoise": 1.0}},
        "8": {"class_type": "VAEDecodeHunyuan3D", "inputs": {"samples": ["7", 0], "vae": ["1", 2], "num_chunks": 8000, "octree_resolution": octree}},
        "9": {"class_type": "VoxelToMesh", "inputs": {"voxel": ["8", 0], "algorithm": "surface net", "threshold": threshold}},
        "10": {"class_type": "SaveGLB", "inputs": {"mesh": ["9", 0], "filename_prefix": prefix}},
    }


def hd_mesh_graph(image_name, seed, prefix="lc/hd", faces=20000, tex=2048):
    """Hunyuan3D 2.1 high-poly -> decimated, unwrapped game mesh plus baked normal and AO maps."""
    g = hunyuan3d_graph(image_name, seed, prefix=prefix + "_high")
    del g["10"]  # don't save the 300k-triangle source
    g.update({
        "11": {"class_type": "DecimateMesh", "inputs": {"mesh": ["9", 0], "target_face_count": faces, "placement_mode": "midpoint"}},
        "12": {"class_type": "MeshSmoothNormals", "inputs": {"mesh": ["11", 0], "crease_angle": 50.0}},
        "13": {"class_type": "UnwrapMesh", "inputs": {"mesh": ["12", 0], "segmenter": "pec", "resolution": tex, "padding": 4, "weld_distance": 0.001}},
        "14": {"class_type": "BakeNormalMapFromMesh", "inputs": {"low_poly": ["13", 0], "high_poly": ["9", 0], "resolution": tex,
               "cage_distance": 0.02, "ignore_backfaces": True}},
        "15": {"class_type": "BakeAmbientOcclusion", "inputs": {"low_poly": ["13", 0], "high_poly": ["9", 0], "resolution": tex,
               "samples": 64, "max_distance": 0.25, "strength": 1.0, "bias": 0.001}},
        "16": {"class_type": "SaveImage", "inputs": {"images": ["14", 0], "filename_prefix": prefix + "_normal"}},
        "17": {"class_type": "SaveImage", "inputs": {"images": ["15", 0], "filename_prefix": prefix + "_ao"}},
        "18": {"class_type": "SaveGLB", "inputs": {"mesh": ["13", 0], "filename_prefix": prefix + "_low"}},
    })
    return g
