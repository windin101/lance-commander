"""Placed map objects (trees, buildings, props) from a mission .pak packet 1.

Packet 1 (Code/objmgr.cpp:781): i32 count, then per object 40 bytes:
    i32 objTypeNum, f32 x, y, z, f32 rotation, i32 damage, i32 teamId,
    i32 parentId, i32 pad, i32 pad
objTypeNum is the line index in Data/Objects/object2.rsp (line 0 is <NULL>),
which names the object's FIT; its [ObjectType] AppearanceName is the TGL model.
Positions are world units from the map centre, as for mission parts.
"""

import os
import struct

import fit
import mech_model
from packet import PacketFile

RECORD = struct.Struct("<i4fiiiii")


def read_objects(pak_path):
    data = PacketFile.open(pak_path).read(1)
    count = struct.unpack_from("<i", data, 0)[0]
    out = []
    for i in range(count):
        t, x, y, z, rot, dmg, team, parent, _a, _b = RECORD.unpack_from(data, 4 + i * RECORD.size)
        out.append({"type": t, "x": round(x, 3), "y": round(y, 3), "z": round(z, 3),
                    "rotation": round(rot, 3), "damage": dmg, "team": team})
    return out


def type_table(objects_dir, types):
    lines = [l.strip() for l in open(os.path.join(objects_dir, "object2.rsp"), encoding="cp1252")]
    files = {f.lower(): f for f in os.listdir(objects_dir)}
    table = {}
    for t in sorted(types):
        fname = files.get(lines[t].lower()) if 0 < t < len(lines) else None
        f = fit.parse_file(os.path.join(objects_dir, fname)) if fname else {}
        ot = f.get("ObjectType", {})
        table[t] = {
            "file": lines[t] if t < len(lines) else "",
            "class": f.get("ObjectClass", {}).get("ObjectTypeNum", -1),
            "name": ot.get("Name", ""),
            "appearance": str(ot.get("AppearanceName", "")).lower(),
            "extent_radius": ot.get("ExtentRadius", 0.0),
        }
    return table


def convert(pak_path, data_dir, out_assets):
    """Returns (objects.json payload, report). Builds missing appearance .glb files."""
    objs = read_objects(pak_path)
    table = type_table(os.path.join(data_dir, "Objects"), {o["type"] for o in objs})
    tgl = os.path.join(data_dir, "TGL")
    os.makedirs(out_assets, exist_ok=True)
    built, missing = [], []
    for app in sorted({v["appearance"] for v in table.values() if v["appearance"]}):
        out = os.path.join(out_assets, app + ".glb")
        if mech_model._find(tgl, app + ".ase", required=False) is None:
            missing.append(app)
            continue
        if not os.path.exists(out):
            mech_model.build(tgl, app, out, gestures=[])
        built.append(app)
    return {"types": {str(k): v for k, v in table.items()}, "objects": objs}, {"objects": len(objs), "appearances": len(built), "missing": missing}
