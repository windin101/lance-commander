"""Copy the campaign's ABL scripts into game/data/abl/ for the in-game interpreter.

Copied: the brain libraries the game loads for every mission (orders, miscfunc,
corebrain .abx; mission.cpp loads them in that order), the include files (.abi), each
campaign mission's script, and every per-unit brain a campaign mission's FIT names.
File names are lowercased so the interpreter's case-insensitive lookups are plain
path joins. The scripts are Shared Source data: non-commercial, see the EULA.
"""

import os
import re
import shutil

import fit

LIBRARIES = ["orders", "miscfunc", "corebrain"]


def _index(folder):
    return {f.lower(): os.path.join(folder, f) for f in os.listdir(folder)}


def convert(missions_dir, out_dir, missions):
    """Returns {"missions": n, "brains": n, "libraries": [...], "missing": [...]}."""
    warriors_dir = os.path.join(missions_dir, "Warriors")
    top = _index(missions_dir)
    warriors = _index(warriors_dir)
    os.makedirs(os.path.join(out_dir, "warriors"), exist_ok=True)
    missing = []

    def copy(index, name, dest):
        src = index.get(name.lower())
        if src is None:
            missing.append(name)
            return False
        shutil.copyfile(src, os.path.join(dest, name.lower()))
        return True

    for f in top:
        if f.endswith(".abi"):
            copy(top, f, out_dir)
    for f in warriors:
        if f.endswith(".abi"):
            copy(warriors, f, os.path.join(out_dir, "warriors"))
    for lib in LIBRARIES:
        copy(top, lib + ".abx", out_dir)

    brains = set()
    for m in missions:
        copy(top, m + ".abl", out_dir)
        mission_fit = fit.parse_file(top[m.lower() + ".fit"])
        for key, block in mission_fit.items():
            if re.fullmatch(r"Warrior\d+", key) and isinstance(block, dict) and block.get("Brain"):
                name = block["Brain"].lower()
                brains.add(name[:-4] if name.endswith(".abl") else name)  # mc2_12 names one with its extension
    for b in sorted(brains):
        copy(warriors, b + ".abl", os.path.join(out_dir, "warriors"))
    return {"missions": len(missions), "brains": len(brains), "libraries": LIBRARIES, "missing": missing}
