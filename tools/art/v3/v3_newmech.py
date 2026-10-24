"""Write tools/art/v3/<mech>.json for a mech with a v2 work dir (hd_v2.py): from_v2 fit and labels, regions from
the MC2 part names, joint actuators sized to the mech, default wear and mask. Weapons and canopy are added by hand
after the checks.   python3 -I tools/art/v3/v3_newmech.py <mech> [source.json]"""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
mech = sys.argv[1]
work = Path(f"/mnt/nvme1n1p1/mc2-rework/work/{mech}")
f = json.loads((work / "fit.json").read_text())
stl = Path(f["stl"])
src = {}
for cand in (stl.parent / "source.json", Path(sys.argv[2]) if len(sys.argv) > 2 else None):
    if cand and cand.exists():
        src = json.loads(cand.read_text()); break
d = {"_doc": f"v3 settings for the {mech} (tools/art/v3/v3_mech.py), fit and labels from the v2 work on the same sculpt.",
     "name": mech, "folder": "mechs", "stl": str(stl), "source": {k: src.get(k, "") for k in ("title", "author", "url", "licence", "file")},
     "k": f["k"], "base_glb": f"game/assets/mechs/{mech}.glb", "max_edge_mm": 120, "pivots": {}, "from_v2": str(work),
     "glass_from_v2": (work / "glass_faces.npy").exists(), "auto_actuators": True, "caps": "none",
     "seg": {"patch_majority": 0.85, "min_island": 300}, "lowpoly": {"faces": 40000, "padding": 4, "minor_scale": 0.5},
     "wear": {"seed": 17, "chips": 1.0, "grime": 1.25, "grime_opacity": 0.9, "dirt_patches": 0.35, "dust_colour": [0.34, 0.30, 0.24],
              "dust_opacity": 0.55, "edge_lighten": 0.22, "dust_height_mm": int(f["H"] * 0.25), "chip_scale_mm": 180},
     "mask": {"patch_deg": 25, "panel_deg": 12, "rules": [{"set": "piping", "level": "panel", "max_width_mm": 220, "min_aspect": 3.5, "min_area_m2": 0.05}]}}
import v3_mech as M
d["_path_tmp"] = True
(HERE / f"{mech}.json").write_text(json.dumps(d, indent=1))
cfg = M.load_cfg(mech)
H = f["H"]
reg, feet, joints, exp = {}, [], {}, {}
for part, p in M.PARTS.items():
    j = p["joint"]; n = part.lower() + " " + j
    if "ankle" in j or "toe" in n or "foot" in n:
        reg[part] = "feet"; feet.append(part); exp[part] = 1.0
    elif "lleg" in j or "mleg" in j:
        reg[part] = "lower_legs"; exp[part] = 1.0
    elif "uleg" in j:
        reg[part] = "upper_legs"
    elif "launcher" in n or "missile" in n:
        reg[part] = "weapons"
    elif "arm" in j or "gun" in j or "arm" in part:
        reg[part] = "arms"; exp[part] = 0.95
    else:
        reg[part] = "body"
    r = H * 0.045
    if j == "joint_hip":
        continue
    if j == "joint_torso":
        joints[j] = {"kind": "sphere", "r": round(H * 0.07)}
    elif "lleg" in j or "mleg" in j or "ankle" in j or "toe" in j:
        joints[j] = {"kind": "cyl", "r": round(r), "half": round(r * 1.3)}
    else:
        joints[j] = {"kind": "sphere", "r": round(r * 1.1)}
d.pop("_path_tmp")
d.update({"part_region": reg, "feet": feet, "joints": joints})
d["wear"]["exposure"] = exp
(HERE / f"{mech}.json").write_text(json.dumps(d, indent=1))
print(mech, "parts", list(M.PARTS), "feet", feet)
