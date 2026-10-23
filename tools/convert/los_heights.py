"""Line-of-sight heights (metres above the ground) for mechs, vehicles and turrets -> los_heights.json.

The original sights from `getLOSPosition` (Code/mover.cpp:3442-3498): a mover's position raised by
`lowestWeaponNodeZ`, the height above the terrain of its lowest weapon node (found by
`getLowestWeaponNode`, MCLib/Gvactor.cpp:554-576 and the mech appearance), or 15 world units when
it has none. A turret sights from its first weapon node's height (Code/turret.cpp:1235-1241,
the node named by WeaponNodeId0 in the appearance INI, MCLib/bdactor.cpp:350-376).

The node heights here are the shapes' static (bind-pose) node positions from the ASE files, which
is the standing pose the original measures in (mover.cpp:3454: gestures 2, 4 and 7).
"""

import glob
import json
import os
import re

import mech_model

METRES_PER_WU = 0.2
FALLBACK_WU = 15.0  # mover.cpp:3490


def node_positions(ase_path):
    """{node name (lower case): (x, y, z)} from the ASE NODE_TM blocks (z is up, world units)."""
    text = open(ase_path, encoding="cp1252", errors="replace").read()
    out = {}
    for m in re.finditer(r'\*NODE_TM \{\s*\*NODE_NAME "([^"]+)"(.*?)\}', text, re.S):
        p = re.search(r"\*TM_POS\s+(\S+)\s+(\S+)\s+(\S+)", m.group(2))
        if p:
            out[m.group(1).lower()] = tuple(float(v) for v in p.groups())
    return out


def _lowest(nodes, names):
    zs = [nodes[n][2] for n in names if n in nodes and nodes[n][2] != 0.0]
    return round((min(zs) if zs else FALLBACK_WU) * METRES_PER_WU, 2)


def table(data_dir, out_data, out_assets):
    tgl = os.path.join(data_dir, "TGL")
    out = {"mechs": {}, "vehicles": {}, "turrets": {}}
    for path in sorted(glob.glob(os.path.join(out_assets, "mechs", "*.json"))):
        side = json.load(open(path))
        if "lods" not in side:
            continue
        ase = mech_model._find(tgl, side["lods"][0] + ".ase", required=False)
        if ase:
            names = [w["node"].lower() for w in side.get("weapon_nodes", [])]
            out["mechs"][os.path.splitext(os.path.basename(path))[0]] = _lowest(node_positions(ase), names)
    for path in sorted(glob.glob(os.path.join(out_data, "vehicles", "*.json"))):
        app = json.load(open(path))["appearance"]
        ase = mech_model._find(tgl, app + ".ase", required=False)
        if ase:
            out["vehicles"][app] = _lowest(node_positions(ase), [f"weapon_0{i}" for i in range(1, 5)])
    turret_apps = set()
    for path in glob.glob(os.path.join(out_data, "maps", "*", "objects.json")):
        for t in json.load(open(path))["types"].values():
            if t.get("class") == 21 and t.get("appearance"):
                turret_apps.add(t["appearance"])
    for app in sorted(turret_apps):
        ase = mech_model._find(tgl, app + ".ase", required=False)
        ini = mech_model._find(tgl, app + ".ini", required=False)
        if not ase:
            continue
        node = "weapon1"
        if ini:
            m = re.search(r'WeaponNodeId0\s*=\s*"([^"]+)"', open(ini, encoding="cp1252", errors="replace").read())
            node = m.group(1).lower() if m else ""
        nodes = node_positions(ase)
        z = nodes[node][2] if node in nodes else FALLBACK_WU
        # Pop-up and camouflaged turrets keep their guns below ground in the bind pose and raise
        # them in the pop-up gesture (turret.cpp:444-520), which is not converted: use the
        # mover fallback height for those.
        out["turrets"][app] = round((z if z > 0.0 else FALLBACK_WU) * METRES_PER_WU, 2)
    return out


if __name__ == "__main__":
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    data = os.path.join(root, "reference", "mc2-source", "Source", "Data")
    t = table(data, os.path.join(root, "game", "data"), os.path.join(root, "game", "assets"))
    with open(os.path.join(root, "game", "data", "los_heights.json"), "w", encoding="utf-8") as fh:
        json.dump(t, fh, indent=1)
        fh.write("\n")
    print({k: len(v) for k, v in t.items()})
