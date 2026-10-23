"""Audio for the slice: weapon fire sounds, effects, music, voice-overs, Betty.

Weapon fire sound chain (verified against the data):
  component special_fx -> Objects/Effects.csv data row (the effect id is the row's index; row 0,
  "No Weapon Here", says 3 in its first cell, which must not shadow the flamer's id 3)
  -> weapon-bolt object number -> object FIT FiringSoundFX
  -> line N of Sound/Sound.rsp (line 0 is <NULL>) -> Sound/SoundFX/<file>.
Pilot radio (Code/radio.cpp, gamesound.cpp, warrior.cpp radioMessage): Sound/radio.csv holds one row per
RadioMessageType (priority, shelf life, styles and their chances, pilot-identifies-self, packet mapping); a
message plays packet mapping+style of the pilot's PilotN.pak, whose packets are the lines of Sound/pilotN.rsp in
order (the same 42 roles for every voice; a few voices spell the salvage stem differently on disk).
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


def effect_objects(rows):
    """Effect id -> weapon-bolt object number from Effects.csv rows (header included).

    The id is the data row's index, as tools/art/weapon_fx_original.py reads it. The first
    cell is not the id: row 0 ("No Weapon Here") carries 3 there, and keying by it made the
    flamer (id 3) resolve to object 0 and lose its firing sound."""
    out = {}
    for sid, r in enumerate(rows[1:]):
        if len(r) > 4 and r[4].strip().lstrip("-").isdigit():
            out[sid] = int(r[4])
    return out


RADIO_FIELDS = ["priority", "shelf_life", "movie", "styles", "chance1", "chance2", "chance3", "pilot_id", "map"]


def radio_messages(sound):
    """Sound/radio.csv in RadioMessageType order: [{name, priority, shelf_life, styles, chances, pilot_id, map}]."""
    with open(os.path.join(sound, "radio.csv"), encoding="cp1252", newline="") as fh:
        rows = [r for r in csv.reader(fh) if r and r[0].strip()]
    out = []
    for r in rows[1:]:
        f = dict(zip(RADIO_FIELDS, [c.strip() for c in r[1:]]))
        out.append({"name": r[0].strip(), "priority": int(f["priority"]), "shelf_life": float(f["shelf_life"]),
                    "styles": int(f["styles"]),
                    "chances": [int(f["chance1"]), int(f["chance2"]), int(f["chance3"])],
                    "pilot_id": f["pilot_id"].lower().startswith("y"), "map": int(f["map"])})
    return out


def _norm_stem(stem):
    return stem.lower().replace("salvageable", "salvagable").replace("savageable", "salvagable")


def pilot_voice_files(sound, n):
    """Voice n's radio packets in order: [(stem as on disk, wav path)], from Sound/pilot<n>.rsp. A packet whose
    file is spelt differently on disk (mechsalvageable / mechsavageable) is matched by its normalised stem."""
    folder = os.path.join(sound, "Pilots", "Pilot%d" % n)
    on_disk = {}
    for f in os.listdir(folder):
        if f.lower().endswith(".wav"):
            stem = os.path.splitext(f)[0].split("_", 1)[1]
            on_disk[_norm_stem(stem)] = (stem.lower(), os.path.join(folder, f))
    out = []
    for line in open(os.path.join(sound, "pilot%d.rsp" % n), encoding="cp1252"):
        line = line.strip()
        if not line:
            continue
        stem = os.path.splitext(line.replace("\\", "/").split("/")[-1])[0].split("_", 1)[1]
        out.append(on_disk.get(_norm_stem(stem), (stem.lower(), None)))
    return out


def weapon_fire_sounds(data_dir, components, sound_list, idx):
    objects = os.path.join(data_dir, "Objects")
    with open(os.path.join(objects, "Effects.csv"), encoding="cp1252", newline="") as fh:
        rows = list(csv.reader(fh))
    effect_obj = effect_objects(rows)
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
    # Pilot radio voices 1-26 (a profile's pilotAudio letter a-z), by packet index; and the message table.
    manifest["radio"] = radio_messages(sound)
    manifest["pilots"] = {}
    for n in range(1, 27):
        lines = []
        for stem, src in pilot_voice_files(sound, n):
            if not src:
                missing.append(f"pilots:{n}/{stem}")
                lines.append([stem, ""])
                continue
            dst = transcode(src, os.path.join(out_assets, "pilots", "pilot%d" % n, stem + ".ogg"))
            lines.append([stem, "res://" + os.path.relpath(dst, os.path.dirname(os.path.dirname(out_assets))).replace(os.sep, "/").split("game/", 1)[-1]])
        manifest["pilots"][str(n)] = lines
    return manifest, missing
