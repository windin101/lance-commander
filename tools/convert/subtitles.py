"""Comms subtitles: local Whisper transcripts of the original's voice audio -> game/data/subtitles.json.

The audio is the MechCommander 2 Shared Source release's own (reference/mc2-source, under
docs/MC2-SOURCE-EULA.md, like every other converted asset):
  - the mission voice-overs the mission scripts play (playWave): every "vo" key of
    game/data/audio.json, from Source/Data/Sound/<name>.wav (FinalBuild/data/sound as a fallback);
  - the pilot radio lines: Source/Data/Sound/Pilots/Pilot1..26/*.wav. A pilot profile's pilotAudio
    "pilot<letter>" opens pilot<letter>.pak (radio.cpp:78), which holds Pilot<n>'s WAVs with
    n = the letter's place in the alphabet (checked packet by packet against the WAVs).

Two steps, so the slow one runs once:
  transcribe   Whisper large-v3 on the GPU -> tools/convert/subtitles_raw.json (text, segments,
               duration per file). Needs torch + openai-whisper; on this machine:
                 PYTHONPATH=/mnt/nvme1n1p1/whisper-pkgs/_shim:/mnt/nvme1n1p1/whisper-pkgs \
                 HIP_VISIBLE_DEVICES=1 swarm lock gpu1 -- \
                 /mnt/nvme1n1p1/StabilityMatrix/linux-x64/Data/Packages/ComfyUI/venv/bin/python \
                 tools/convert/subtitles.py transcribe
               (models in /mnt/nvme1n1p1/whisper-cache; the _shim stands in for numba, which the
               venv's NumPy is too new for and which only word timestamps need).
  second       (review aid) medium.en with beam search -> subtitles_raw2.json, to diff against.
  build        raw transcripts + tools/convert/subtitles_edits.json (speakers, reviewed
               corrections, proper-noun spellings) -> game/data/subtitles.json. Stdlib only.

subtitles.json: {"_provenance": ..., "vo": {name: {speaker, text, duration, segments}},
"pilots": {"pilot<n>/<wav name>": {speaker, voice, text, duration}}}; names are lower case
without the extension, as audio.json keys them. segments are [start s, end s, text, speaker?]
(the speaker only where one line holds two voices). Death screams carry no text and are left out.
"""

import glob
import json
import os
import re
import sys
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(ROOT, "reference", "mc2-source")
SOUND = os.path.join(SRC, "Source", "Data", "Sound")
FINAL = os.path.join(SRC, "FinalBuild", "data", "sound")
RAW = os.path.join(HERE, "subtitles_raw.json")
EDITS = os.path.join(HERE, "subtitles_edits.json")
OUT = os.path.join(ROOT, "game", "data", "subtitles.json")
CACHE = "/mnt/nvme1n1p1/whisper-cache"
MODEL = "large-v3"

# The game's own spellings (strings.json, briefings, pilot callsigns): a prompt biases Whisper to them.
NAMES = ("Carver V, Xin Sheng, Mandrissa, Colonel Renard, Renard, Jason Cho, Captain Cho, Lady Cho, "
         "Steiner, Liao, Davion, Bandits, Cash, Diaz, Baxter, Commander, 'Mech, 'Mechs, BattleMech, "
         "Mech Bay, LRM, SRM, PPC, autocannon, dropship, HQ, nav point, resource building, sensor tower")


def vo_sources():
    vo = json.load(open(os.path.join(ROOT, "game", "data", "audio.json")))["vo"]
    found = {}
    for d in (FINAL, SOUND):  # Source/Data/Sound wins
        for p in glob.glob(os.path.join(d, "*.[wW][aA][vV]")):
            found[os.path.splitext(os.path.basename(p))[0].lower()] = p
    return {k: found[k] for k in sorted(vo) if k in found}


def pilot_sources():
    out = {}
    for n in range(1, 27):
        for p in sorted(glob.glob(os.path.join(SOUND, "Pilots", "Pilot%d" % n, "*.[wW][aA][vV]"))):
            out["pilot%d/%s" % (n, os.path.splitext(os.path.basename(p))[0].lower())] = p
    return out


def voice_callsigns():
    """pilot<n> -> [callsigns] of the profiles whose pilotAudio opens that voice."""
    pilots = json.load(open(os.path.join(ROOT, "game", "data", "pilots.json")))
    out = {}
    for prof, fit in pilots.items():
        g = fit.get("General", {})
        a = str(g.get("pilotAudio", "")).lower()
        m = re.fullmatch(r"pilot([a-z])", a)
        if m and prof.startswith("pmw"):
            out.setdefault("pilot%d" % (ord(m.group(1)) - 96), []).append(str(g.get("Callsign", g.get("Name", prof))).upper())
    return out


def duration(path):
    try:
        with wave.open(path) as w:
            d = w.getnframes() / float(w.getframerate())
            if d > 0.0:
                return round(d, 2)
    except Exception:
        pass
    try:  # ADPCM and odd headers: ask ffprobe
        import subprocess
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                           capture_output=True, text=True, check=True)
        return round(float(r.stdout.strip()), 2)
    except Exception:
        return 0.0


def transcribe():
    import torch
    import whisper
    os.makedirs(CACHE, exist_ok=True)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = whisper.load_model(MODEL, device=dev, download_root=CACHE)
    raw = json.load(open(RAW)) if os.path.exists(RAW) else {}
    calls = voice_callsigns()
    jobs = [("vo", k, p) for k, p in vo_sources().items()] + [("pilots", k, p) for k, p in pilot_sources().items()]
    for i, (kind, key, path) in enumerate(jobs):
        if key in raw.get(kind, {}):
            continue
        prompt = NAMES
        if kind == "pilots":
            prompt = ", ".join(calls.get(key.split("/")[0], [])) + ". " + NAMES
        r = model.transcribe(path, language="en", initial_prompt=prompt, fp16=(dev == "cuda"),
                             condition_on_previous_text=False, temperature=0.0)
        raw.setdefault(kind, {})[key] = {
            "text": r["text"].strip(), "duration": duration(path),
            "segments": [[round(s["start"], 2), round(s["end"], 2), s["text"].strip()] for s in r["segments"]],
        }
        if i % 25 == 0:
            json.dump(raw, open(RAW, "w"), indent=1, sort_keys=True)
            print(f"{i + 1}/{len(jobs)} {key}: {raw[kind][key]['text'][:70]}", flush=True)
    json.dump(raw, open(RAW, "w"), indent=1, sort_keys=True)
    print("transcribed", sum(len(v) for v in raw.values()))


def second_opinion():
    """A second transcript with another model and beam search (subtitles_raw2.json): where the
    two disagree is where the review starts."""
    import torch
    import whisper
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = whisper.load_model("medium.en", device=dev, download_root=CACHE)
    raw = json.load(open(RAW))
    out = {}
    for kind in raw:
        srcs = vo_sources() if kind == "vo" else pilot_sources()
        for key in raw[kind]:
            r = model.transcribe(srcs[key], language="en", fp16=(dev == "cuda"), beam_size=5,
                                 condition_on_previous_text=False, temperature=0.0)
            out.setdefault(kind, {})[key] = r["text"].strip()
    json.dump(out, open(RAW.replace(".json", "2.json"), "w"), indent=1, sort_keys=True)


def _fix(text, fixes):
    for a, b in fixes:
        text = re.sub(a, b, text)
    return text.strip()


def build():
    raw = json.load(open(RAW))
    edits = json.load(open(EDITS)) if os.path.exists(EDITS) else {}
    fixes = [(a, b) for a, b in edits.get("spellings", [])]
    calls = voice_callsigns()
    out = {"_provenance": {
        "source": "MechCommander 2 Shared Source release audio (reference/mc2-source, docs/MC2-SOURCE-EULA.md)",
        "method": f"local Whisper {MODEL} transcripts (tools/convert/subtitles.py), reviewed; corrections and "
                  "speakers in tools/convert/subtitles_edits.json. The original showed no subtitles.",
        "speakers": "pilot lines: the callsign(s) of the profiles using that voice; voice-overs: from the "
                    "mission scripts' comments and the briefings, blank when unknown"},
        "vo": {}, "pilots": {}}
    vo_src = vo_sources()
    for key, r in sorted(raw.get("vo", {}).items()):
        e = edits.get("vo", {}).get(key, {})
        text = _fix(e.get("text", r["text"]), fixes)
        segs = [] if "text" in e else [[s[0], s[1], _fix(s[2], fixes)] for s in r["segments"]]
        who = e.get("segment_speakers", [])
        for i, s in enumerate(segs):  # a line with two voices: each segment names its own speaker
            if i < len(who) and who[i]:
                s.append(who[i])
        d = r["duration"] or duration(vo_src.get(key, ""))
        out["vo"][key] = {"speaker": e.get("speaker", ""), "text": text, "duration": d, "segments": [s for s in segs if s[2]]}
    for key, r in sorted(raw.get("pilots", {}).items()):
        e = edits.get("pilots", {}).get(key, {})
        voice = key.split("/")[0]
        text = _fix(e.get("text", r["text"]), fixes)
        if not text or e.get("drop") or key.endswith("_deathscream"):
            continue  # screams and breaths: nothing to read
        out["pilots"][key] = {"speaker": " / ".join(calls.get(voice, [])), "voice": voice, "text": text,
                              "duration": r["duration"]}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    print("vo", len(out["vo"]), "pilot lines", len(out["pilots"]))


if __name__ == "__main__":
    {"transcribe": transcribe, "second": second_opinion, "build": build}[sys.argv[1] if len(sys.argv) > 1 else "build"]()
