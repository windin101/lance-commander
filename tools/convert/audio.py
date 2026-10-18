"""Audio for the slice: weapon fire sounds, effects, music, voice-overs, Betty.

Weapon fire sound chain (verified against the data):
  component special_fx -> Objects/Effects.csv row (first column = effect id)
  -> weapon-bolt object number -> object FIT FiringSoundFX
  -> line N of Sound/Sound.rsp (line 0 is <NULL>) -> Sound/SoundFX/<file>.
Music tune N is Sound/Music/musicNN.wav (Missions/sndconst.abi names them).
Everything is transcoded to Ogg Vorbis with ffmpeg (MS-ADPCM music is not a
format Godot imports).
"""

import csv
import os
import shutil
import subprocess

import fit

GENERAL_SFX = {
    "laser_hit": "sfx_lazers_mechhits", "ballistic_hit": "sfx_ac5_mechhit", "heavy_hit": "sfx_ac20_mechhit",
    "missile_hit": "sfx_explo_short", "mech_explode": "sfx_mech_explodes2", "vehicle_explode": "sfx_explo_large",
    "building_explode": "sfx_explo_britedebris", "footstep": "sfx_mech_footfall.big", "fall": "sfx_mech_collide",
    "ui_select": "sfx_button5", "ui_order": "sfx_button7", "alarm": "sfx_alarm",
}
BETTY = {"objective_new": "cmp_mis_obj", "objective_done": "cmp_res_obj_1", "win": "cmp_res_win", "lose": "cmp_res_lose",
         "powerup": "cmp_powerup"}


def _index(dirs):
    idx = {}
    for d in dirs:
        if os.path.isdir(d):
            for f in os.listdir(d):
                idx.setdefault(f.lower(), os.path.join(d, f))
    return idx


def _find(idx, name):
    name = name.lower().replace("\\", "/").split("/")[-1]
    if not name.endswith(".wav"):
        name += ".wav"
    return idx.get(name)


def transcode(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
        return dst
    if shutil.which("ffmpeg"):
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", src, "-c:a", "libvorbis", "-q:a", "5", dst], check=True)
        return dst
    wav = os.path.splitext(dst)[0] + ".wav"
    shutil.copyfile(src, wav)
    return wav


def weapon_fire_sounds(data_dir, components, sound_list, idx):
    objects = os.path.join(data_dir, "Objects")
    with open(os.path.join(objects, "Effects.csv"), encoding="cp1252", newline="") as fh:
        rows = list(csv.reader(fh))
    effect_obj = {}
    for r in rows[1:]:
        if len(r) > 4 and r[0].strip().isdigit() and r[4].strip().lstrip("-").isdigit():
            effect_obj.setdefault(int(r[0]), int(r[4]))
    rsp = [l.strip() for l in open(os.path.join(objects, "object2.rsp"), encoding="cp1252")]
    files = {f.lower(): f for f in os.listdir(objects)}
    out = {}
    for c in components:
        w = c.get("weapon")
        if not w:
            continue
        obj = effect_obj.get(int(w.get("special_fx", 0)))
        if not obj or obj >= len(rsp) or rsp[obj].lower() not in files:
            continue
        f = fit.parse_file(os.path.join(objects, files[rsp[obj].lower()]))
        sid = None
        for block in f.values():
            if "FiringSoundFX" in block:
                sid = int(block["FiringSoundFX"])
        if sid is not None and 0 < sid < len(sound_list):
            path = _find(idx, sound_list[sid])
            if path:
                out[c["id"]] = path
    return out


def convert(data_dir, components, out_assets, tunes, voice):
    sound = os.path.join(data_dir, "Sound")
    idx = _index([os.path.join(sound, "SoundFX"), sound, os.path.join(sound, "Betty"), os.path.join(sound, "Music")])
    sound_list = [l.strip() for l in open(os.path.join(sound, "Sound.rsp"), encoding="cp1252")]
    manifest = {"weapons": {}, "sfx": {}, "music": {}, "vo": {}, "betty": {}}
    missing = []

    def put(category, key, src, name):
        if not src:
            missing.append(f"{category}:{key}")
            return
        dst = transcode(src, os.path.join(out_assets, category, name + ".ogg"))
        manifest[category][str(key)] = "res://" + os.path.relpath(dst, os.path.dirname(os.path.dirname(out_assets))).replace(os.sep, "/").split("game/", 1)[-1]

    for cid, src in weapon_fire_sounds(data_dir, components, sound_list, idx).items():
        put("weapons", cid, src, os.path.splitext(os.path.basename(src))[0].lower().replace(" ", "_").replace("&", "and"))
    for key, name in GENERAL_SFX.items():
        put("sfx", key, _find(idx, name), key)
    for tune in tunes:
        put("music", tune, _find(idx, "music%02d" % tune), "music%02d" % tune)
    for name in voice:
        put("vo", name, _find(idx, name), name.lower())
    for key, name in BETTY.items():
        put("betty", key, _find(idx, name), key)
    return manifest, missing
