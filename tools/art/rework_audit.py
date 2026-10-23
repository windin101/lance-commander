#!/usr/bin/env python3
"""Phase 0 audit of every HD mech, vehicle and map object (HD model and texture rework, 2026-10-23).

    python3 -I tools/art/rework_audit.py [--out swarm/gallery/rework_audit.json] [--md docs/art/rework-audit.md]

For each asset the game would load (the same order as mech_view.gd, mech_stage.gd and objects_view.gd):
source pipeline, source URL and licence, triangle count, UV status, texture sizes, how often it appears
in the 24 missions, whether the source sculpt is on disk, and a priority score. The markdown tables in
docs/art/rework-audit.md between the `audit:begin` / `audit:end` markers are generated; edit the prose
around them by hand. Read-only: nothing under game/ is written.
"""
import argparse
import collections
import io
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hd_rig as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "game" / "assets"
DATA = ROOT / "game" / "data"
HD = ROOT / "original" / "hd"
SOURCES = Path("/mnt/nvme1n1p1/mc2-sources")
OBJECT_ORDER = ["_cad", "_hdtex", "_hd", ""]  # objects_view.gd


def glb_stats(path):
    """Triangles, UV status and texture sizes of one .glb."""
    from PIL import Image
    g, b = R.load_glb(str(path))
    tris = 0
    uv_status = "none"
    uv_unique = 0
    uv_verts = 0
    skinned = bool(g.get("skins"))
    used_meshes = {n["mesh"] for n in g.get("nodes", []) if "mesh" in n}
    lo = np.full(3, np.inf); hi = -lo
    for mi in used_meshes:
        for pr in g["meshes"][mi]["primitives"]:
            acc = g["accessors"][pr["attributes"]["POSITION"]]
            if "min" in acc:
                lo = np.minimum(lo, acc["min"]); hi = np.maximum(hi, acc["max"])
    size_m = float(np.max(hi - lo)) if np.isfinite(lo).all() else 0.0
    for mi, mesh in enumerate(g.get("meshes", [])):
        if mi not in used_meshes:
            continue
        for pr in mesh["primitives"]:
            if "indices" in pr:
                tris += g["accessors"][pr["indices"]]["count"] // 3
            else:
                tris += g["accessors"][pr["attributes"]["POSITION"]]["count"] // 3
            if "TEXCOORD_0" in pr["attributes"]:
                U = R.read_accessor(g, b, pr["attributes"]["TEXCOORD_0"])
                uv_verts += len(U)
                uv_unique += len(np.unique(np.round(U, 4), axis=0))
    if uv_verts:
        # Palette UVs (stl_rig/stl_hd): thousands of triangles, every vertex on one of a few colour cells.
        uv_status = "palette" if (uv_unique < 64 and tris > 2000) else "unwrapped"
    tex = []
    for im in g.get("images", []):
        try:
            if "bufferView" in im:
                bv = g["bufferViews"][im["bufferView"]]
                data = b[bv.get("byteOffset", 0): bv.get("byteOffset", 0) + bv["byteLength"]]
                w, h = Image.open(io.BytesIO(data)).size
            else:
                w, h = Image.open(path.parent / im["uri"]).size
            tex.append(max(w, h))
        except Exception:
            tex.append(0)
    return {"tris": int(tris), "uv": uv_status, "uv_unique": int(uv_unique), "skinned": skinned,
            "textures": sorted(tex, reverse=True), "anims": len(g.get("animations", [])), "size_m": round(size_m, 1),
            "bytes": path.stat().st_size}


def licence_of(path):
    """(title by author, url, licence) from a <name>_hd.LICENSE.md, else Nones."""
    if not path.exists():
        return None, None, None
    t = path.read_text()
    m = re.search(r"> \*\*(.+?)\*\* by \*\*(.+?)\*\*, (\S+)", t)
    lic = re.search(r"licensed under \*\*(.+?)\*\*", t)
    urls = re.findall(r"https://www\.(?:thingiverse|printables)\.com/\S+", t)
    title = f"{m.group(1)} by {m.group(2)}" if m else None
    url = (m.group(3).rstrip(",") if m else (urls[0].rstrip(",.)") if urls else None))
    l2 = re.search(r"\((CC [A-Z\-]+ \d\.\d)\)", t)
    return title, url, (l2.group(1) if l2 else (lic.group(1) if lic else None))


def mission_counts():
    """Placements per unit model and per object appearance across the 24 missions."""
    chassis = {p.stem.lower() for p in (DATA / "chassis").glob("*.json")}
    unit_parts = collections.Counter()
    unit_missions = collections.defaultdict(set)
    obj_place = collections.Counter()
    obj_missions = collections.defaultdict(set)
    for mp in sorted((DATA / "missions").glob("mc2_[0-9][0-9].json")):
        mis = mp.stem
        fit = json.loads(mp.read_text())
        vpath = DATA / "missions" / f"{mis}_vehicles.json"
        vmap = json.loads(vpath.read_text()) if vpath.exists() else {}
        for i in range(1, int(fit.get("Parts", {}).get("NumParts", 0)) + 1):
            part = fit.get(f"Part{i}")
            if not part:
                continue
            key = str(part.get("CSVFile", "")).lower()
            model = None
            if key in chassis:
                model = ("mech", key)
            elif key in vmap:
                vj = DATA / "vehicles" / f"{vmap[key]}.json"
                if vj.exists():
                    model = ("vehicle", json.loads(vj.read_text()).get("appearance", key))
            if model:
                unit_parts[model] += 1
                unit_missions[model].add(mis)
        op = DATA / "maps" / mis / "objects.json"
        if op.exists():
            od = json.loads(op.read_text())
            types = od.get("types", {})
            for o in od.get("objects", []):
                t = types.get(str(int(o["type"])), {})
                app = str(t.get("appearance", "")).lower()
                if app:
                    obj_place[app] += 1
                    obj_missions[app].add(mis)
    return unit_parts, unit_missions, obj_place, obj_missions


def unit_rows(kind, counts, missions):
    folder = ASSETS / ("mechs" if kind == "mech" else "vehicles")
    rows = []
    for p in sorted(folder.glob("*_hd.glb")):
        name = p.stem[:-3]
        prov = {}
        pp = HD / name / "provenance.json"
        if pp.exists():
            prov = json.loads(pp.read_text())
        title, url, lic = licence_of(folder / f"{name}_hd.LICENSE.md")
        if prov.get("kind") == "adapted":
            tool = prov.get("tool", "")
            pipe = "STL sculpt (stl_rig)" if "stl_rig" in tool else "STL sculpt (stl_hd)" if "stl_hd" in tool else "STL sculpt"
            if "vulture" in tool:
                pipe = "STL sculpt (stl_rig_vulture)"
        elif (folder / f"{name}_hd.LICENSE.md").exists():
            pipe = "STL sculpt"
        else:
            pipe = "Hunyuan3D"
            lic = "MC2 Shared Source (NC)"
        st = glb_stats(p)
        n_parts = counts.get((kind, name), 0)
        n_mis = len(missions.get((kind, name), ()))
        rows.append(dict(kind=kind, name=name, file=str(p.relative_to(ROOT)), pipeline=pipe, source=title,
                         url=url or prov.get("source"), licence=lic or prov.get("licence"), placements=n_parts,
                         missions=n_mis, **st))
    return rows


def object_rows(place, missions):
    folder = ASSETS / "objects"
    names = set()
    for p in folder.glob("*.glb"):
        s = p.stem
        if s.endswith("_dam") or s.endswith("_dam_hdtex"):
            continue
        for suf in ("_cad", "_hdtex", "_hd"):
            if s.endswith(suf):
                s = s[: -len(suf)]
                break
        names.add(s)
    rows = []
    for name in sorted(names):
        chosen = None
        for suf in OBJECT_ORDER:
            p = folder / f"{name}{suf}.glb"
            if p.exists():
                chosen = (suf, p)
                break
        suf, p = chosen
        pipe = {"_cad": "SolidCraft CAD + baked original texture", "_hdtex": "original mesh + upscaled texture",
                "_hd": "Hunyuan3D", "": "original mesh + texture"}[suf]
        title, url, lic = licence_of(folder / f"{name}_hd.LICENSE.md")
        if suf == "_hd" and title:
            pipe = "STL sculpt (stl_hd)"
        if (ASSETS / "trees" / f"{name}.glb").exists():
            pipe = "HD tree (trees.py, MultiMesh)"
            p = ASSETS / "trees" / f"{name}.glb"
        shadowed = suf in ("_cad", "_hdtex") and (folder / f"{name}_hd.glb").exists()
        if shadowed:
            pipe += "; **sculpt _hd.glb shadowed**"
        st = glb_stats(p)
        rows.append(dict(kind="object", name=name, file=str(p.relative_to(ROOT)), pipeline=pipe, source=title,
                         url=url, licence=lic or "MC2 Shared Source (NC)", placements=place.get(name, 0),
                         missions=len(missions.get(name, ())), **st))
    return rows


def sculpt_on_disk(row):
    if row["kind"] == "object" and not row.get("source"):
        return None
    d = SOURCES / row["kind"] / row["name"]
    if not row.get("source") and not d.exists():
        return None  # Hunyuan or original: no third-party source
    return d.exists() and any(p.suffix.lower() in (".stl", ".zip", ".3mf") for p in d.rglob("*"))


VIS = {"mech": 3.0, "vehicle": 2.0, "object": 1.0}


def priority(row):
    """Visibility x frequency x quality deficit. Higher = rework sooner."""
    freq = math.log2(1 + row["placements"]) + 0.5 * row["missions"] ** 0.5
    deficit = 1.0
    if row["uv"] in ("palette", "none"):
        deficit += 1.0  # flat palette paint, no detail
    if row["pipeline"].startswith("STL sculpt (stl_rig"):
        deficit += 1.0  # plane cuts at every joint, caps, gaps
    elif row["pipeline"].startswith("Hunyuan"):
        deficit += 0.8  # soft AI mesh
    elif row["pipeline"].startswith("original mesh"):
        deficit += 0.6  # 2001 boxes and 128 px textures
    tex = row["textures"][0] if row["textures"] else 0
    if row["kind"] == "object" and tex and tex < 512:
        deficit += 0.4
    if row["pipeline"].startswith("HD tree"):
        return 0.0  # trees have their own pipeline (trees.py); out of scope
    if row["kind"] == "object":
        # a big building fills the mission camera; a fence post does not (glb units are metres)
        deficit *= min(2.0, max(0.35, math.log2(1 + row.get("size_m", 4) / 6)))
    if row["kind"] == "mech":
        freq += 3.0  # every mech is in the bay, the lab and the purchase screen
    return round(VIS[row["kind"]] * freq * deficit, 1)


def table(rows, kind, limit=None):
    out = ["| # | Asset | Pipeline | Source / licence | Tris | UV | Textures | Placed (missions) | Sculpt on disk | Priority |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    rs = [r for r in rows if r["kind"] == kind]
    rs.sort(key=lambda r: -r["priority"])
    for i, r in enumerate(rs[:limit] if limit else rs, 1):
        src = f"[{r['source']}]({r['url']}), {r['licence']}" if r.get("source") and r.get("url") else (r["licence"] or "")
        tex = ", ".join(str(t) for t in r["textures"][:4]) or "-"
        disk = {True: "yes", False: "**no**", None: "n/a"}[r["sculpt_on_disk"]]
        out.append(f"| {i} | `{r['name']}` | {r['pipeline']} | {src} | {r['tris']} | {r['uv']} | {tex} | "
                   f"{r['placements']} ({r['missions']}) | {disk} | {r['priority']} |")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "swarm" / "gallery" / "rework_audit.json"))
    ap.add_argument("--md", default=str(ROOT / "docs" / "art" / "rework-audit.md"))
    a = ap.parse_args()
    up, um, op, om = mission_counts()
    rows = unit_rows("mech", up, um) + unit_rows("vehicle", up, um) + object_rows(op, om)
    for r in rows:
        r["sculpt_on_disk"] = sculpt_on_disk(r)
        r["priority"] = priority(r)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(rows, indent=1))
    md = Path(a.md)
    gen = "\n\n".join([
        f"Generated by `tools/art/rework_audit.py` from the installed assets and the 24 missions' parts and objects.json. "
        f"{sum(r['kind'] == 'mech' for r in rows)} mechs, {sum(r['kind'] == 'vehicle' for r in rows)} vehicles, "
        f"{sum(r['kind'] == 'object' for r in rows)} objects. Full data: `swarm/gallery/rework_audit.json`.",
        "### Mechs\n\n" + table(rows, "mech"),
        "### Vehicles\n\n" + table(rows, "vehicle"),
        "### Objects (top 60 by priority; the rest are in the JSON)\n\n" + table(rows, "object", 60),
    ])
    if md.exists():
        t = md.read_text()
        t = re.sub(r"(<!-- audit:begin -->\n).*?(\n<!-- audit:end -->)", lambda m: m.group(1) + gen + m.group(2), t, flags=re.S)
    else:
        t = "# HD rework audit\n\n<!-- audit:begin -->\n" + gen + "\n<!-- audit:end -->\n"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(t)
    print(f"{len(rows)} assets -> {a.out}, {md}")


if __name__ == "__main__":
    main()
