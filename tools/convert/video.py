"""Videos from the user's retail MechCommander 2 disc -> Ogg Theora for Godot.

The retail disc is NOT covered by the Shared Source EULA: output goes to
game/assets/retail/ (gitignored) and must never be committed or distributed.

Disc image: an Alcohol .mdf (raw 2352-byte Mode 1 sectors) is unwrapped to a
plain ISO by keeping bytes 16..2064 of each sector. Mission comms clips
(V1A.BIK etc., 128x72) carry their audio in DATA/SOUND/<name>.WAV; it is
muxed in here. Cinematics carry their own Bink audio.
"""

import os
import shutil
import subprocess

SECTOR_RAW = 2352


def mdf_to_iso(mdf, iso):
    if os.path.exists(iso) and os.path.getmtime(iso) >= os.path.getmtime(mdf):
        return iso
    with open(mdf, "rb") as f, open(iso, "wb") as o:
        while True:
            s = f.read(SECTOR_RAW)
            if len(s) < SECTOR_RAW:
                break
            if s[15] != 1:
                raise ValueError("not a Mode 1 data sector")
            o.write(s[16:2064])
    return iso


def extract(iso, dest, paths):
    os.makedirs(dest, exist_ok=True)
    subprocess.run(["7z", "x", "-y", "-o" + dest, iso, *paths], check=True, capture_output=True)


def to_theora(src, dst, audio=None, scale_width=None):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
        return dst
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-i", src]
    if audio:
        cmd += ["-i", audio, "-map", "0:v:0", "-map", "1:a:0"]
    vf = []
    if scale_width:
        vf.append(f"scale={scale_width}:-2:flags=lanczos")
    if vf:
        cmd += ["-vf", ",".join(vf)]
    cmd += ["-c:v", "libtheora", "-q:v", "8", "-c:a", "libvorbis", "-q:a", "5", "-ar", "44100", dst]
    subprocess.run(cmd, check=True)
    return dst


def convert(root, mdf, comms, cinematics):
    """Returns {name: res path} for converted videos, or {} when no disc image."""
    if not mdf or not os.path.exists(mdf) or not shutil.which("ffmpeg") or not shutil.which("7z"):
        return {}
    original = os.path.join(root, "original")
    iso = mdf_to_iso(mdf, os.path.join(original, "MC2.iso"))
    disc = os.path.join(original, "disc")
    names = [f"DATA/MOVIES/{n.upper()}.BIK" for n in comms + cinematics] + [f"DATA/SOUND/{n.upper()}.WAV" for n in comms]
    extract(iso, disc, names)
    out_dir = os.path.join(root, "game", "assets", "retail", "video")
    out = {}
    for n in comms:
        src = os.path.join(disc, "DATA", "MOVIES", n.upper() + ".BIK")
        wav = os.path.join(disc, "DATA", "SOUND", n.upper() + ".WAV")
        # 128x72 talking heads: upscale for a crisp comms window.
        to_theora(src, os.path.join(out_dir, n.lower() + ".ogv"), wav if os.path.exists(wav) else None, scale_width=512)
        out[n.lower()] = f"res://assets/retail/video/{n.lower()}.ogv"
    for n in cinematics:
        src = os.path.join(disc, "DATA", "MOVIES", n.upper() + ".BIK")
        to_theora(src, os.path.join(out_dir, n.lower() + ".ogv"), scale_width=1280)
        out[n.lower()] = f"res://assets/retail/video/{n.lower()}.ogv"
    return out
