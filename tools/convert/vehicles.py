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
MAX_WEAPON_NODES = 4  # Gvactor.cpp:91


def count_weapon_nodes(ase_path):
    """Weapon_01..Weapon_04 nodes the shape has (names match case-insensitively, msl.h:510).
    GVAppearanceType always looks for 4 and drops the missing ones (Gvactor.cpp:311-321, 466-474);
    GroundVehicle::fireWeapon only fires from the first two (gvehicl.cpp:4610), so with 3 or 4
    the least-used choice gets stuck (combat-rules.md O1)."""
    import re
    text = open(ase_path, encoding="cp1252", errors="replace").read()
    names = {m.lower() for m in re.findall(r'\*NODE_NAME\s+"(weapon_0[1-4])"', text, re.I)}
    return len(names)
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
        # gvehicl.cpp:317, 344-347: sight factor (artillery piece 1.2) and the minelayer's mine
        # stock, which becomes its turret armour (gvehicl.cpp:1254-1258)
        "los_factor": float(general.get("LOSFactor", 1.0)),
        "mine_layer": int(general.get("MineLayer", 0) or 0),
        "mine_sweeper": bool(general.get("MineSweeper", False)),
        "max_velocity": float(dyn.get("MaxVelocity", 10.0)),
        # gvehicl.cpp:934, 2977-2993: the speed changes by MaxAccel per second
        "max_accel": float(dyn.get("MaxAccel", 0.0)),
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


# The vehicles the support tab delivers (controlGui.cpp:101-108): repair truck 182, minelayer
# 120, artillery piece 415 (GuardTower.fit, "ArtilleryPiece"). Converted even when no mission
# places them.
SUPPORT_OBJECTS = {"repairtruck": 182, "minelayer": 120, "guardtower": 415}


def convert_support(data_dir, out_data, out_assets):
    """Convert the support-power vehicles. Returns their JSON stems."""
    objects_dir = os.path.join(data_dir, "Objects")
    out = []
    for stem, number in SUPPORT_OBJECTS.items():
        fname, f = object_fit_for(objects_dir, number)
        if f.get("ObjectClass", {}).get("ObjectTypeNum") != VEHICLE_CLASS:
            continue
        _write_vehicle(parse_vehicle(f), os.path.splitext(fname)[0].lower(), data_dir, out_data, out_assets)
        out.append(os.path.splitext(fname)[0].lower())
    return out


def _write_vehicle(v, stem, data_dir, out_data, out_assets):
    import json
    tgl = os.path.join(data_dir, "TGL")
    os.makedirs(out_data, exist_ok=True)
    os.makedirs(out_assets, exist_ok=True)
    glb = os.path.join(out_assets, v["appearance"] + ".glb")
    base_ase = mech_model._find(tgl, v["appearance"] + ".ase", required=False)
    v["weapon_nodes"] = count_weapon_nodes(base_ase) if base_ase else -1
    with open(os.path.join(out_data, stem + ".json"), "w", encoding="utf-8") as fh:
        json.dump(v, fh, indent=1)
    if base_ase and not os.path.exists(glb):
        mech_model.build(tgl, v["appearance"], glb, gestures=["Walk", "Run"])
        import ase
        tex = mech_model.material_texture(ase.parse_file(base_ase), tgl)
        if tex:
            with open(tex, "rb") as fh, open(os.path.join(out_assets, v["appearance"] + "_paint.bin"), "wb") as out_bin:
                out_bin.write(mech_model.tga_to_png(fh.read()))
        wreck = mech_model._find(tgl, v["appearance"] + "Dam.ase", required=False)
        if wreck:
            mech_model.build(tgl, v["appearance"] + "Dam", os.path.join(out_assets, v["appearance"] + "_wreck.glb"), gestures=[])


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
        glb = os.path.join(out_assets, v["appearance"] + ".glb")
        base_ase = mech_model._find(tgl, v["appearance"] + ".ase", required=False)
        v["weapon_nodes"] = count_weapon_nodes(base_ase) if base_ase else -1
        with open(os.path.join(out_data, stem + ".json"), "w", encoding="utf-8") as fh:
            json.dump(v, fh, indent=1)
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
