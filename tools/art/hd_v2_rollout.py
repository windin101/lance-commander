#!/usr/bin/env python3
"""Roll the HD rework (v2) pipeline over many assets: build, pose-test, measure, and table the results.

    python3 -I tools/art/hd_v2_rollout.py mechs [names...] [--install] [--table swarm/gallery/hd_v2_rollout.json]
    python3 -I tools/art/hd_v2_rollout.py vehicles [names...] [--install]

Per asset:
- the v2 config: tools/art/hd_v2/<name>.json, made on first use from the v1 fit (mechs:
  ~/craft/solid/mc2/stl/<name>/joints.json; vehicles: original/hd/<name>/provenance.json "joints") with an empty
  "v2" block for per-asset overrides;
- the source: mechs ~/craft/solid/mc2/stl/<name>/<source.json "file">; vehicles the first STL named in the provenance,
  found under /mnt/nvme1n1p1/mc2-sources/vehicle/<name>/;
- then hd_v2.py's stages into /mnt/nvme1n1p1/mc2-rework/work/<name>/ (installed into game/assets/v2/ only with
  --install), tools/art/pose_test.py on the result, and the texture budget from the PNG sizes as Godot will hold them
  (BPTC 1 byte/px, mipmaps x4/3). One JSON row per asset in --table; a failing asset is logged and the run goes on.
"""
import argparse
import json
import subprocess
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "tools/art/hd_v2"
STL = Path.home() / "craft/solid/mc2/stl"
SRC = Path("/mnt/nvme1n1p1/mc2-sources")
WORK = Path("/mnt/nvme1n1p1/mc2-rework/work")
BUDGET_MB = {"mechs": 16.0, "vehicles": 4.0}


def mech_source(name):
    """The sculpt and joints the installed v1 model was built from. source.json names the first sculpt tried, which
    is not always the one that shipped (Zeus and Uller moved to other kits; Flea and Thor were pre-turned by a prep
    script), so v2.stl in the config wins, then the v1 provenance's "stl" and "joints", then source.json."""
    cfg = CFG / f"{name}.json"
    prov_p = ROOT / f"original/hd/{name}/provenance.json"
    prov = json.loads(prov_p.read_text()) if prov_p.exists() else {}
    if not cfg.exists():
        jp = Path(prov.get("joints") or STL / name / "joints.json")
        j = json.loads(jp.read_text())
        j.setdefault("v2", {})
        j["_from"] = f"~/craft/solid/mc2/stl/{name}/{jp.name} (the v1 fit), copied by hd_v2_rollout.py"
        cfg.write_text(json.dumps(j, indent=1) + "\n")
    v2 = json.loads(cfg.read_text()).get("v2", {})
    f = v2.get("stl") or (Path(prov["stl"]).name if prov.get("stl") else None) or \
        json.loads((STL / name / "source.json").read_text())["file"]
    return STL / name / f, cfg


def vehicle_source(name):
    prov = json.loads((ROOT / f"original/hd/{name}/provenance.json").read_text())
    cfg = CFG / f"{name}.json"
    if not cfg.exists():
        j = dict(prov.get("joints", {}))
        j["v2"] = {}
        j["_from"] = f"original/hd/{name}/provenance.json joints (the v1 fit), copied by hd_v2_rollout.py"
        cfg.write_text(json.dumps(j, indent=1) + "\n")
    want = prov.get("stl", [None])[0]
    hits = [p for p in (SRC / "vehicle" / name).rglob("*") if p.suffix.lower() == ".stl" and (want is None or p.name == want)]
    if not hits:
        raise SystemExit(f"{name}: no source STL {want} under {SRC / 'vehicle' / name}")
    return hits[0], cfg


HUNYUAN = {"bloodasp", "enfield", "hollander", "menshen", "starslayer"}   # rigged by hd_rig.py from Hunyuan3D meshes


def tex_mb(work, kind):
    from PIL import Image
    tot = 0.0
    for k in ("mask", "detail", "normal", "zones", "camo"):
        p = work / f"{k}.png"
        if p.exists():
            w, h = Image.open(p).size
            tot += w * h * 4 / 3 / 1e6
    return round(tot, 1)


def v1_baseline(kind, name, samples):
    """The installed v1 model's pose test (the penetration baseline), cached in <work>/pose_v1.json."""
    folder = "mechs" if kind == "mechs" else "vehicles"
    v1 = ROOT / f"game/assets/{folder}/{name}_hd.glb"
    out = WORK / name / "pose_v1.json"
    if out.exists() or not v1.exists():
        return out if out.exists() else None
    tail = 0
    prov = ROOT / f"original/hd/{name}/provenance.json"
    if prov.exists() and "stl_rig" in json.loads(prov.read_text()).get("tool", ""):
        import hd_rig as R
        g, _ = R.load_glb(str(ROOT / f"game/assets/{folder}/{name}.glb"))
        mid = any(n.get("name", "").endswith("mleg") for n in g["nodes"])
        tail = 64 * (8 if mid else 6)   # stl_rig's leg joint caps: one 16-sided drum (64 tris) per leg joint, written last
    subprocess.run([sys.executable, "-I", str(ROOT / "tools/art/pose_test.py"), str(v1), "--samples", str(samples),
                    "--json", str(out)] + (["--filler-tail", str(tail)] if tail else []), capture_output=True, text=True, cwd=ROOT)
    return out if out.exists() else None


def run(kind, name, install, samples):
    t0 = time.time()
    folder = "mechs" if kind == "mechs" else "vehicles"
    if kind == "mechs" and name in HUNYUAN:
        stl, cfg = ROOT / f"game/assets/mechs/{name}_hd.glb", CFG / f"{name}.json"
        if not cfg.exists():
            cfg.write_text(json.dumps({"v2": {}, "_from": "the installed Hunyuan _hd.glb (hd_rig.py), copied by hd_v2_rollout.py"}, indent=1) + "\n")
        steps = "fitglb,segment,glass,bake,paint,write"
    else:
        stl, cfg = mech_source(name) if kind == "mechs" else vehicle_source(name)
        steps = "fit,segment,glass,bake,paint,write" if kind == "mechs" else "fitveh,lowpoly,bake,paint,write"
    if install:
        steps += ",install"
    cmd = [sys.executable, "-I", str(ROOT / "tools/art/hd_v2.py"), name, "--folder", folder, "--stl", str(stl),
           "--joints", str(cfg), "--steps", steps] + (["--tex", "1024", "--faces", "150000"] if kind == "vehicles" else [])
    log = WORK / name / "rollout.log"
    (WORK / name).mkdir(parents=True, exist_ok=True)
    with open(log, "w") as f:
        r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=ROOT)
    row = {"asset": name, "kind": kind, "build_ok": r.returncode == 0, "log": str(log)}
    if r.returncode != 0:
        row["error"] = log.read_text().strip().splitlines()[-1][:300]
        return row
    glb = WORK / name / f"{name}.glb"
    pj = WORK / name / "pose.json"
    base = v1_baseline(kind, name, samples)
    pr = subprocess.run([sys.executable, "-I", str(ROOT / "tools/art/pose_test.py"), str(glb), "--samples", str(samples),
                         "--json", str(pj)] + (["--baseline", str(base)] if base else []), capture_output=True, text=True, cwd=ROOT)
    pose = json.loads(pj.read_text()) if pj.exists() else {}
    js = pose.get("joints", {})
    row.update({
        "pose_pass": pr.returncode == 0, "fail_parts": pose.get("fail", []),
        "hole_p95": round(max([v.get("loco_gap_p95", 0) for v in js.values()] or [0]), 3),
        "sep_p95": round(max([v.get("loco_sep_p95", 0) for v in js.values()] or [0]), 3),
        "joint_sep_p95": round(max([v.get("loco_joint_sep_p95", 0) for v in js.values()] or [0]), 3),
        "pen_p95": round(max([v.get("loco_pen_p95", 0) for v in js.values()] or [0]), 3),
        "tris": pose.get("tris"), "tex_mb": tex_mb(WORK / name, kind), "budget_mb": BUDGET_MB[kind],
        "seconds": round(time.time() - t0),
    })
    row["budget_ok"] = row["tex_mb"] <= row["budget_mb"]
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["mechs", "vehicles"])
    ap.add_argument("names", nargs="*")
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--samples", type=int, default=12)
    ap.add_argument("--table", default=str(ROOT / "swarm/gallery/hd_v2_rollout.json"))
    a = ap.parse_args()
    names = a.names
    if not names:
        names = sorted(p.name for p in STL.iterdir() if (p / "joints.json").exists()) if a.kind == "mechs" else \
            sorted(p.stem[:-3] for p in (ROOT / "game/assets/vehicles").glob("*_hd.glb"))
    table = json.loads(Path(a.table).read_text()) if Path(a.table).exists() else {}
    for n in names:
        try:
            row = run(a.kind, n, a.install, a.samples)
        except Exception as e:   # one asset's failure doesn't stop the rollout
            row = {"asset": n, "kind": a.kind, "build_ok": False, "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-800:]}
        table[n] = row
        Path(a.table).write_text(json.dumps(table, indent=1) + "\n")
        print(json.dumps({k: row.get(k) for k in ("asset", "build_ok", "pose_pass", "hole_p95", "sep_p95", "joint_sep_p95",
                                                  "pen_p95", "tris", "tex_mb", "error")}), flush=True)


if __name__ == "__main__":
    main()
