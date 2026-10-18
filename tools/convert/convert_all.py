"""Convert the MC2 source release's text data into JSON under game/data/.

Usage: python3 -I tools/convert/convert_all.py [--src reference/mc2-source/Source]

Output is derived from Microsoft's Shared Source release and stays under its
EULA (docs/MC2-SOURCE-EULA.md): non-commercial use only.
"""

import argparse
import csv
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chassis  # noqa: E402
import components  # noqa: E402
import fit  # noqa: E402
import map_objects  # noqa: E402
import mech_model  # noqa: E402
import strings_rc  # noqa: E402
import terrain  # noqa: E402
import vehicles  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "game", "data")
SLICE_MISSIONS = ["mc2_01"]
ASSETS = os.path.join(ROOT, "game", "assets")
# Per-mission textures (Terrain.cpp:425-433, TerrainColorMap, water and detail maps).
MISSION_TEXTURES = [".burnin.jpg", ".detail.tga", ".water.tga"]
# Mech appearances used by the slice missions (object FIT AppearanceName).
MECH_MODELS = ["bushwacker", "werewolf", "starslayer", "urbanmech"]


def write(rel, data):
    path = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False, sort_keys=False)
        fh.write("\n")
    return path


def heat_table(path):
    with open(path, encoding="cp1252", newline="") as fh:
        rows = [r for r in csv.reader(fh) if r and not r[0].startswith("//")]
    keys = ["heat", "shutdown_pct", "ammo_explosion_pct", "move_mod", "fire_mod", "injuries"]
    return [dict(zip(keys, (float(c) if "." in c else int(c) for c in r[:6]))) for r in rows]


HIT_TABLE_SIZE = 3 * 4 * 11  # sections x arcs x armour locations (mech.cpp:568)


def gamesys(path):
    g = fit.parse_file(path)
    # gamesys.fit declares c[131] but the code reads 132 entries. The game's reader
    # stops at the declared count, so the last slot keeps the global array's 0.
    table = g["Mech:FireWeapon"]["HitLocationTable"]
    g["Mech:FireWeapon"]["HitLocationTable"] = table + [0] * (HIT_TABLE_SIZE - len(table))
    return g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(ROOT, "reference", "mc2-source", "Source"))
    src = ap.parse_args().src
    data = os.path.join(src, "Data")
    objects = os.path.join(data, "Objects")
    missions = os.path.join(data, "Missions")
    report = []

    comps = components.load(os.path.join(objects, "compbas.csv"))
    by_id = {c["id"]: c for c in comps}
    write("components.json", comps)
    report.append(f"components: {len(comps)}")

    n = 0
    chassis_names = []
    for name in sorted(os.listdir(objects)):
        path = os.path.join(objects, name)
        if name.lower().endswith(".csv") and chassis.is_chassis_csv(path):
            ch = chassis.load(path, by_id)
            write(f"chassis/{os.path.splitext(name)[0].lower()}.json", ch)
            chassis_names.append(os.path.splitext(name)[0].lower())
            n += 1
    report.append(f"chassis: {n}")

    write("heat.json", heat_table(os.path.join(objects, "heat.csv")))
    write("gamesys.json", gamesys(os.path.join(missions, "gamesys.fit")))
    write("campaign.json", fit.parse_file(os.path.join(data, "Campaign", "campaign.fit")))

    for m in SLICE_MISSIONS:
        mission_fit = fit.parse_file(os.path.join(missions, m + ".fit"))
        write(f"missions/{m}.json", mission_fit)
        meta, cells, tac = terrain.convert(os.path.join(missions, m + ".pak"), mission_fit)
        write(f"maps/{m}/terrain.json", meta)
        with open(os.path.join(OUT, "maps", m, "cells.bin"), "wb") as fh:
            fh.write(cells)
        vmap = vehicles.convert_for_mission(mission_fit, data, os.path.join(OUT, "vehicles"),
                                            os.path.join(ASSETS, "vehicles"), set(chassis_names))
        write(f"missions/{m}_vehicles.json", vmap)
        report.append(f"{m} vehicles: {sorted(vmap)}")
        objs, orep = map_objects.convert(os.path.join(missions, m + ".pak"), data, os.path.join(ASSETS, "objects"))
        write(f"maps/{m}/objects.json", objs)
        report.append(f"{m} objects: {orep['objects']} placed, {orep['appearances']} models, missing {orep['missing']}")
        tex_out = os.path.join(ASSETS, "maps", m)
        os.makedirs(tex_out, exist_ok=True)
        with open(os.path.join(tex_out, "tacmap.tga"), "wb") as fh:
            fh.write(tac)
        for suffix in MISSION_TEXTURES:
            src_tex = os.path.join(data, "Textures", m + suffix)
            if os.path.exists(src_tex):
                shutil.copyfile(src_tex, os.path.join(tex_out, suffix.lstrip(".")))
    report.append(f"missions: {', '.join(SLICE_MISSIONS)}")

    tgl = os.path.join(data, "TGL")
    os.makedirs(os.path.join(ASSETS, "mechs"), exist_ok=True)
    for name in MECH_MODELS:
        tex = mech_model._find(os.path.join(tgl, "128"), name + "RGB.tga", required=False)
        rep = mech_model.build(tgl, name, os.path.join(ASSETS, "mechs", name + ".glb"), tex)
        if tex:
            # Lossless paint mask for team recolouring (raw PNG bytes; .bin so Godot
            # does not VRAM-compress it the way it does textures inside the .glb).
            with open(tex, "rb") as fh, open(os.path.join(ASSETS, "mechs", name + "_paint.bin"), "wb") as out:
                out.write(mech_model.tga_to_png(fh.read()))
        ini = fit.parse_file(mech_model._find(tgl, name + ".ini"))
        with open(os.path.join(ASSETS, "mechs", name + ".json"), "w", encoding="utf-8") as fh:
            json.dump(mech_model.sidecar(ini, rep), fh, indent=1)
        for suffix, tag in mech_model.WRECKS.items():
            if mech_model._find(tgl, name + suffix + ".ase", required=False):
                mech_model.build(tgl, name + suffix, os.path.join(ASSETS, "mechs", f"{name}_{tag}.glb"), tex, gestures=[])
        report.append(f"model {name}: {rep['meshes']} meshes, {len(rep['animations'])} animations")

    warriors = os.path.join(missions, "Warriors")
    pilots = {}
    for name in sorted(os.listdir(warriors)):
        if name.lower().endswith(".fit"):
            pilots[os.path.splitext(name)[0].lower()] = fit.parse_file(os.path.join(warriors, name))
    write("pilots.json", pilots)
    report.append(f"pilot files: {len(pilots)}")

    strings = strings_rc.load(os.path.join(src, "Script1.rc"), os.path.join(src, "resource.h"))
    write("strings.json", {str(k): v for k, v in sorted(strings.items())})
    report.append(f"strings: {len(strings)}")

    print("\n".join(report))


if __name__ == "__main__":
    main()
