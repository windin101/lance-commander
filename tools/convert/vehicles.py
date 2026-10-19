"""Ground vehicles (object FIT ObjectTypeNum = 3) used by missions -> JSON + .glb.

GroundVehicleType::init / GroundVehicle::init (Code/gvehicl.cpp:292, 985):
[General] Chassis (0 wheeled, 1 tracked, 2 hover), HoverCraft, ExplosionDamage/
Radius, PathLocks, CurTonnage, BattleRating; [InternalStructure] and per-section
[Front]/[Left]/[Right]/[Rear]/[Turret] armour; [VehicleDynamics] MaxVelocity,
MaxTurretYaw(Rate); [InventoryInfo] + [Item:N] MasterID, numbered others,
weapons, then ammo. Items have no body location.
"""

import os

import fit
import mech_model

SECTIONS = ["Front", "Left", "Right", "Rear", "Turret"]
VEHICLE_CLASS = 3


def object_fit_for(objects_dir, object_number):
    lines = [l.strip() for l in open(os.path.join(objects_dir, "object2.rsp"), encoding="cp1252")]
    files = {f.lower(): f for f in os.listdir(objects_dir)}
    name = lines[object_number] if 0 < object_number < len(lines) else ""
    real = files.get(name.lower())
    return (real, fit.parse_file(os.path.join(objects_dir, real))) if real else (None, {})


def parse_vehicle(f):
    general = f.get("General", {})
    dyn = f.get("VehicleDynamics", {})
    inv = f.get("InventoryInfo", {})
    n_items = int(inv.get("NumOther", 0)) + int(inv.get("NumWeapons", 0)) + int(inv.get("NumAmmo", 0))
    items = []
    for i in range(n_items):
        mid = f.get(f"Item:{i}", {}).get("MasterID")
        if mid is not None:
            items.append(int(mid))
    return {
        "name": f.get("ObjectType", {}).get("Name", ""),
        "appearance": str(f.get("ObjectType", {}).get("AppearanceName", "")).lower(),
        "chassis": int(general.get("Chassis", 0)),
        "hover": bool(general.get("HoverCraft", False)) or int(general.get("Chassis", 0)) == 2,
        "path_locks": bool(general.get("PathLocks", True)),
        "tonnage": float(general.get("CurTonnage", 0.0)),
        "battle_rating": int(general.get("BattleRating", -1)),
        "explosion_damage": float(general.get("ExplosionDamage", 0.0)),
        "explosion_radius": float(general.get("ExplosionRadius", 0.0)),
        # gvehicl.cpp:1241: RefitPoints become the repair pool; ResourcePoints pay out on capture
        "refit_points": float(general.get("RefitPoints", 0)),
        "resource_points": int(general.get("ResourcePoints", 0)),
        "max_velocity": float(dyn.get("MaxVelocity", 10.0)),
        "max_turret_yaw": float(dyn.get("MaxTurretYaw", 0)),
        "max_turret_yaw_rate": float(dyn.get("MaxTurretYawRate", 0)),
        "armor": {s.lower(): float(f.get(s, {}).get("MaxArmorPoints", 0)) for s in SECTIONS},
        "internal": {s.lower(): float(f.get(s, {}).get("CurInternalStructure",
                                       f.get("InternalStructure", {}).get(s, 1))) for s in SECTIONS},
        "items": items,
        "num_other": int(inv.get("NumOther", 0)),
        "num_weapons": int(inv.get("NumWeapons", 0)),
        "num_ammo": int(inv.get("NumAmmo", 0)),
    }


def convert_for_mission(mission_fit, data_dir, out_data, out_assets, known_chassis):
    """Convert every vehicle type a mission's Parts use. Returns {csv_name_lower: json_stem}."""
    objects_dir = os.path.join(data_dir, "Objects")
    tgl = os.path.join(data_dir, "TGL")
    os.makedirs(out_data, exist_ok=True)
    os.makedirs(out_assets, exist_ok=True)
    out = {}
    nparts = int(mission_fit.get("Parts", {}).get("NumParts", 0))
    for i in range(1, nparts + 1):
        part = mission_fit.get(f"Part{i}", {})
        csv_name = str(part.get("CSVFile", "")).lower()
        if not part or csv_name in known_chassis or csv_name in out:
            continue
        fname, f = object_fit_for(objects_dir, int(part.get("ObjectNumber", 0)))
        if f.get("ObjectClass", {}).get("ObjectTypeNum") != VEHICLE_CLASS:
            continue
        v = parse_vehicle(f)
        stem = os.path.splitext(fname)[0].lower()
        import json
        with open(os.path.join(out_data, stem + ".json"), "w", encoding="utf-8") as fh:
            json.dump(v, fh, indent=1)
        glb = os.path.join(out_assets, v["appearance"] + ".glb")
        base_ase = mech_model._find(tgl, v["appearance"] + ".ase", required=False)
        if base_ase:
            mech_model.build(tgl, v["appearance"], glb, gestures=["Walk", "Run"])
            # Vehicle textures are paint masks too: keep a lossless copy for MechPaint.
            import ase
            tex = mech_model.material_texture(ase.parse_file(base_ase), tgl)
            if tex:
                with open(tex, "rb") as fh, open(os.path.join(out_assets, v["appearance"] + "_paint.bin"), "wb") as out_bin:
                    out_bin.write(mech_model.tga_to_png(fh.read()))
            wreck = mech_model._find(tgl, v["appearance"] + "Dam.ase", required=False)
            if wreck:
                mech_model.build(tgl, v["appearance"] + "Dam", os.path.join(out_assets, v["appearance"] + "_wreck.glb"), gestures=[])
        out[csv_name] = stem
    return out
