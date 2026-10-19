"""Mech model + gesture animations (ASE) -> glTF binary (.glb).

Source conventions (3ds Max ASE, as MC2 reads them in MCLib/msl.cpp):
- NODE_TM rows are the node's *world* matrix, row-vector convention.
- Mesh vertices and normals are exported in world space.
- CONTROL_POS_SAMPLE is the node's position in its parent's space.
- CONTROL_ROT_SAMPLE is angle-axis; the first key is absolute (parent space)
  and every later key is a delta composed onto the previous one
  (msl.cpp: quat[j] = quat[j-1] * key, in MC2's own quaternion convention).
  With standard Hamilton products and the sign convention below, that is
  q_j = delta_j * q_{j-1}: the only order under which every walk-cycle node
  returns to its start pose (test_walk_cycle_loops). Missing keys mean
  "unchanged".
- Max angle-axis turns the opposite way to the right-hand rule: NODE_TM rows
  for axis (0,0,-1), +10 deg show a +10 deg turn about +Z. So q = (cos a/2,
  -axis sin a/2).
- 30 fps, 160 ticks per frame.

Output: glTF, Y-up, metres. Max (x, y, z) Z-up -> glTF (x, z, -y), scaled by
0.2 m per unit (MC2 world units; Terrain.cpp:64).
"""

import json
import math
import os
import struct
import zlib

import ase

METERS_PER_UNIT = 0.2
TICKS_PER_SECOND = 160 * 30
# Gesture animation files per mech (Data/TGL/<Mech><Suffix>.ase).
GESTURES = [
    "Idle", "Walk", "Run", "STtoWK", "WKtoST", "WKtoRN", "RNtoWK", "LimpLeft", "LimpRight",
    "ParkToStand", "StandToPark", "Jump", "FallForward", "FallBackward", "GetUpFront",
    "GetUpBack", "HitFront", "HitBack", "HitLeft", "HitRight",
]
# Destroyed-state wrecks are separate static meshes, not animations (mech3d.cpp:169).
WRECKS = {"FallForwardDam": "wreck_forward", "FallBackwardDam": "wreck_backward"}
# MechAnimationNames (MCLib/mech3d.cpp:143): gesture index -> animation file suffix.
GESTURE_TABLE = [
    "StandToPark", "ParkToStand", "", "STtoWK", "Walk", "StandToPark", "WKtoRN", "Run", "RNtoWK",
    "Walk", "WKtoST", "LimpLeft", "LimpRight", "Idle", "FallBackward", "FallForward", "HitFront",
    "HitBack", "HitLeft", "HitRight", "Jump", "GetUpBack", "GetUpFront", "FallForward", "FallBackward",
]
GESTURE_IDS = [
    "park", "park_to_stand", "stand", "stand_to_walk", "walk", "stand_to_park", "walk_to_run", "run",
    "run_to_walk", "reverse", "stand_to_reverse", "limp_left", "limp_right", "idle", "fall_backward",
    "fall_forward", "hit_front", "hit_back", "hit_left", "hit_right", "jump", "getup_back",
    "getup_front", "fallen_forward", "fallen_backward",
]
# Light-cone meshes the original only draws as night spotlights (mech3d.cpp:3072).
HIDDEN_MESH_PREFIXES = ("spotlight", "slcircle")


# --- math (row-vector 4x3 affine matrices, quaternions as (x, y, z, w)) -------

def mat_mul(a, b):
    """Row-vector convention: (v * a) * b."""
    out = []
    for i in range(3):
        out.append([sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)])
    t = [sum(a[3][k] * b[k][j] for k in range(3)) + b[3][j] for j in range(3)]
    return out + [t]


def mat_inv(m):
    r = [[m[j][i] for j in range(3)] for i in range(3)]  # transpose; assumes orthonormal
    # undo scale per axis
    for i in range(3):
        s2 = sum(m[i][k] ** 2 for k in range(3))
        for j in range(3):
            r[j][i] /= s2
    t = [-sum(m[3][k] * r[k][j] for k in range(3)) for j in range(3)]
    return r + [t]


def xform_point(v, m):
    return [sum(v[k] * m[k][j] for k in range(3)) + m[3][j] for j in range(3)]


def xform_dir(v, m):
    return [sum(v[k] * m[k][j] for k in range(3)) for j in range(3)]


def mat_to_quat(m):
    # Row-vector matrix rows are the images of the axes; build column matrix R = m^T.
    r = [[m[j][i] for j in range(3)] for i in range(3)]
    # strip scale
    for j in range(3):
        n = math.sqrt(sum(r[i][j] ** 2 for i in range(3))) or 1.0
        for i in range(3):
            r[i][j] /= n
    tr = r[0][0] + r[1][1] + r[2][2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        return [(r[2][1] - r[1][2]) / s, (r[0][2] - r[2][0]) / s, (r[1][0] - r[0][1]) / s, 0.25 * s]
    if r[0][0] > r[1][1] and r[0][0] > r[2][2]:
        s = math.sqrt(1.0 + r[0][0] - r[1][1] - r[2][2]) * 2
        return [0.25 * s, (r[0][1] + r[1][0]) / s, (r[0][2] + r[2][0]) / s, (r[2][1] - r[1][2]) / s]
    if r[1][1] > r[2][2]:
        s = math.sqrt(1.0 + r[1][1] - r[0][0] - r[2][2]) * 2
        return [(r[0][1] + r[1][0]) / s, 0.25 * s, (r[1][2] + r[2][1]) / s, (r[0][2] - r[2][0]) / s]
    s = math.sqrt(1.0 + r[2][2] - r[0][0] - r[1][1]) * 2
    return [(r[0][2] + r[2][0]) / s, (r[1][2] + r[2][1]) / s, 0.25 * s, (r[1][0] - r[0][1]) / s]


def quat_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return [aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz]


def quat_norm(q):
    n = math.sqrt(sum(c * c for c in q)) or 1.0
    return [c / n for c in q]


def max_angle_axis(ax, ay, az, angle):
    s = math.sin(angle / 2.0)
    return quat_norm([-ax * s, -ay * s, -az * s, math.cos(angle / 2.0)])


# Max space -> glTF space
def pos_gl(v):
    return [v[0] * METERS_PER_UNIT, v[2] * METERS_PER_UNIT, -v[1] * METERS_PER_UNIT]


def dir_gl(v):
    return [v[0], v[2], -v[1]]


def quat_gl(q):
    return [q[0], q[2], -q[1], q[3]]


# --- scene graph ------------------------------------------------------------

def collect_nodes(tree):
    nodes = {}
    order = []
    for obj in tree.children:
        if obj.key not in ("HELPEROBJECT", "GEOMOBJECT"):
            continue
        name = obj.first("NODE_NAME")
        nodes[name] = {"obj": obj, "parent": obj.first("NODE_PARENT"), "world": ase.node_tm(obj)}
        order.append(name)
    for name in order:
        n = nodes[name]
        parent = nodes.get(n["parent"])
        n["local"] = mat_mul(n["world"], mat_inv(parent["world"])) if parent else n["world"]
    return nodes, order


def local_trs(m):
    t = m[3]
    q = mat_to_quat(m)
    s = [math.sqrt(sum(m[i][k] ** 2 for k in range(3))) for i in range(3)]
    return t, q, s


def mesh_primitive(obj, world):
    """Un-indexed triangles in node-local space: positions, normals, uvs."""
    mesh = obj.find("MESH")
    if mesh is None:
        return None
    inv = mat_inv(world)
    verts = [ase.floats(v.values[1:4]) for v in mesh.find("MESH_VERTEX_LIST").find_all("MESH_VERTEX")]
    faces = [ase.mesh_face(f.values) for f in mesh.find("MESH_FACE_LIST").find_all("MESH_FACE")]
    tverts, tfaces = [], []
    if mesh.find("MESH_TVERTLIST") is not None:
        tverts = [ase.floats(t.values[1:3]) for t in mesh.find("MESH_TVERTLIST").find_all("MESH_TVERT")]
        tfaces = [[int(x) for x in t.values[1:4]] for t in mesh.find("MESH_TFACELIST").find_all("MESH_TFACE")]
    normals = []
    nblock = mesh.find("MESH_NORMALS")
    if nblock is not None:
        for fn in nblock.find_all("MESH_FACENORMAL"):
            normals.append([ase.floats(vn.values[1:4]) for vn in fn.children or []])
    pos, nrm, uv = [], [], []
    mtl = []  # per-triangle submaterial id (*MESH_MTLID), for multi/sub-object materials
    for f in mesh.find("MESH_FACE_LIST").find_all("MESH_FACE"):
        vals = list(f.values)
        mtl.append(int(vals[vals.index("*MESH_MTLID") + 1]) if "*MESH_MTLID" in vals else 0)
    for fi, face in enumerate(faces):
        corners = [0, 1, 2]  # (x,y,z)->(x,z,-y) is a proper rotation, so winding is kept
        for ci in corners:
            p = xform_point(verts[face[ci]], inv)
            pos.append(pos_gl(p))
            if fi < len(normals) and ci < len(normals[fi]):
                n = xform_dir(normals[fi][ci], inv)
            else:
                n = [0.0, 0.0, 1.0]
            ln = math.sqrt(sum(c * c for c in n)) or 1.0
            nrm.append(dir_gl([c / ln for c in n]))
            if tfaces and fi < len(tfaces):
                u, v = tverts[tfaces[fi][ci]]
                uv.append([u, 1.0 - v])
            else:
                uv.append([0.0, 0.0])
    return {"position": pos, "normal": nrm, "uv": uv, "mtl": mtl}


# --- animation ----------------------------------------------------------------

def read_animation(path):
    """{node: {"t": [(time, pos_gl)], "r": [(time, quat_gl)]}} plus duration."""
    tree = ase.parse_file(path)
    scene = tree.find("SCENE")
    first = int(scene.first("SCENE_FIRSTFRAME"))
    last = int(scene.first("SCENE_LASTFRAME"))
    tpf = int(scene.first("SCENE_TICKSPERFRAME"))
    fps = int(scene.first("SCENE_FRAMESPEED"))
    tracks = {}
    for obj in tree.children:
        anim = obj.find("TM_ANIMATION") if obj.children else None
        if anim is None:
            continue
        name = anim.first("NODE_NAME")
        out = {}
        pos_track = anim.find("CONTROL_POS_TRACK")
        if pos_track is not None:
            keys = {int(s.values[0]): ase.floats(s.values[1:4]) for s in pos_track.find_all("CONTROL_POS_SAMPLE")}
            samples, cur = [], None
            for frame in range(first, last + 1):
                cur = keys.get(frame * tpf, cur)
                if cur is not None:
                    samples.append(((frame - first) / fps, pos_gl(cur)))
            out["t"] = samples
        rot_track = anim.find("CONTROL_ROT_TRACK")
        if rot_track is not None:
            keys = {int(s.values[0]): ase.floats(s.values[1:5]) for s in rot_track.find_all("CONTROL_ROT_SAMPLE")}
            samples, q = [], None
            for frame in range(first, last + 1):
                k = keys.get(frame * tpf)
                d = max_angle_axis(*k) if k else [0.0, 0.0, 0.0, 1.0]
                q = d if q is None else quat_norm(quat_mul(d, q))
                samples.append(((frame - first) / fps, quat_gl(q)))
            out["r"] = samples
        if out:
            tracks[name] = out
    return tracks, (last - first) / fps


# --- TGA -> PNG (stdlib) --------------------------------------------------------

def tga_to_png(data):
    id_len, cmap_type, img_type = data[0], data[1], data[2]
    w, h = struct.unpack_from("<HH", data, 12)
    bpp, desc = data[16], data[17]
    if img_type not in (2, 10) or cmap_type != 0 or bpp not in (24, 32):
        raise ValueError(f"unsupported TGA (type {img_type}, {bpp} bpp)")
    px = bpp // 8
    off = 18 + id_len
    raw = bytearray()
    if img_type == 2:
        raw = data[off:off + w * h * px]
    else:  # RLE
        i = off
        while len(raw) < w * h * px:
            hdr = data[i]
            i += 1
            n = (hdr & 0x7F) + 1
            if hdr & 0x80:
                raw += data[i:i + px] * n
                i += px
            else:
                raw += data[i:i + n * px]
                i += n * px
    rows = []
    top_down = bool(desc & 0x20)
    for y in range(h):
        sy = y if top_down else h - 1 - y
        row = bytearray([0])
        for x in range(w):
            p = raw[(sy * w + x) * px:(sy * w + x + 1) * px]
            row += bytes([p[2], p[1], p[0]]) + (bytes([p[3]]) if px == 4 else b"")
        rows.append(bytes(row))
    color_type = 6 if px == 4 else 2

    def chunk(tag, body):
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, color_type, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b""))


# --- glTF writer --------------------------------------------------------------

class GltfBuilder:
    def __init__(self):
        self.bin = bytearray()
        self.gltf = {"asset": {"version": "2.0", "generator": "lance-commander mech_model.py"},
                     "scenes": [{"nodes": []}], "scene": 0, "nodes": [], "meshes": [],
                     "buffers": [], "bufferViews": [], "accessors": [], "animations": []}

    def _view(self, data, target=None):
        while len(self.bin) % 4:
            self.bin += b"\0"
        view = {"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(data)}
        if target:
            view["target"] = target
        self.bin += data
        self.gltf["bufferViews"].append(view)
        return len(self.gltf["bufferViews"]) - 1

    def accessor(self, rows, kind, target=None, minmax=False):
        width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[kind]
        flat = [c for r in rows for c in (r if width > 1 else [r])]
        view = self._view(struct.pack(f"<{len(flat)}f", *flat), target)
        acc = {"bufferView": view, "componentType": 5126, "count": len(rows), "type": kind}
        if minmax:
            cols = list(zip(*rows)) if width > 1 else [rows]
            acc["min"] = [min(c) for c in cols]
            acc["max"] = [max(c) for c in cols]
        self.gltf["accessors"].append(acc)
        return len(self.gltf["accessors"]) - 1

    def image(self, png, alpha=False):
        """Adds an image, texture and material; returns the material index."""
        view = self._view(png)
        self.gltf.setdefault("images", []).append({"bufferView": view, "mimeType": "image/png"})
        if not self.gltf.get("samplers"):
            self.gltf["samplers"] = [{"magFilter": 9729, "minFilter": 9987}]
        self.gltf.setdefault("textures", []).append({"source": len(self.gltf["images"]) - 1, "sampler": 0})
        tex = len(self.gltf["textures"]) - 1
        mat = {"name": "mech", "pbrMetallicRoughness": {
            "baseColorTexture": {"index": tex}, "metallicFactor": 0.3, "roughnessFactor": 0.6}}
        if alpha:  # foliage, fences: cut out and draw both sides
            mat.update({"alphaMode": "MASK", "alphaCutoff": 0.5, "doubleSided": True})
        self.gltf.setdefault("materials", []).append(mat)
        return len(self.gltf["materials"]) - 1

    def write(self, path):
        self.gltf["buffers"] = [{"byteLength": len(self.bin)}]
        if not self.gltf["animations"]:
            del self.gltf["animations"]
        js = json.dumps(self.gltf, separators=(",", ":")).encode()
        js += b" " * ((4 - len(js) % 4) % 4)
        binp = bytes(self.bin) + b"\0" * ((4 - len(self.bin) % 4) % 4)
        total = 12 + 8 + len(js) + 8 + len(binp)
        with open(path, "wb") as fh:
            fh.write(struct.pack("<III", 0x46546C67, 2, total))
            fh.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
            fh.write(struct.pack("<II", len(binp), 0x004E4942) + binp)


def build(tgl_dir, mech, out_path, texture_path=None, gestures=GESTURES):
    """Build <mech>.glb from Data/TGL/<mech>.ase plus gesture files. Returns a report dict."""
    base = _find(tgl_dir, mech + ".ase")
    tree = ase.parse_file(base)
    nodes, order = collect_nodes(tree)
    g = GltfBuilder()
    has_tex = False
    multi = None if texture_path else material_table(tree, tgl_dir)
    if multi is not None:  # some material is multi/sub-object (buildings): one glTF material per texture
        mat_of = {}
        for path in sorted({p for subs in multi for p in subs if p}):
            with open(path, "rb") as fh:
                tga = fh.read()
            mat_of[path] = g.image(tga_to_png(tga), alpha=tga[16] == 32)
    if multi is None and not texture_path:
        texture_path = material_texture(tree, tgl_dir)
    if multi is None and texture_path and os.path.exists(texture_path):
        with open(texture_path, "rb") as fh:
            tga = fh.read()
        g.image(tga_to_png(tga), alpha=tga[16] == 32)
        has_tex = True
    index = {}
    for name in order:
        n = nodes[name]
        t, q, s = local_trs(n["local"])
        gn = {"name": name, "translation": pos_gl(t), "rotation": quat_gl(q)}
        if any(abs(c - 1.0) > 1e-4 for c in s):
            gn["scale"] = [s[0], s[2], s[1]]
        if n["obj"].key == "GEOMOBJECT" and not name.lower().startswith(HIDDEN_MESH_PREFIXES):
            prim = mesh_primitive(n["obj"], n["world"])
            if prim and prim["position"] and multi is not None:
                ref = int(n["obj"].first("MATERIAL_REF", 0) or 0)
                subs = multi[ref] if ref < len(multi) else [None]
                groups = {}
                for t, m in enumerate(prim["mtl"]):
                    path = subs[m % len(subs)] if subs else None
                    groups.setdefault(mat_of.get(path), []).append(t)
                prims = []
                for mi, tris in sorted(groups.items(), key=lambda kv: (kv[0] is None, kv[0] or 0)):
                    sel = [3 * t + c for t in tris for c in range(3)]
                    p = {"attributes": {
                        "POSITION": g.accessor([prim["position"][k] for k in sel], "VEC3", 34962, minmax=True),
                        "NORMAL": g.accessor([prim["normal"][k] for k in sel], "VEC3", 34962),
                        "TEXCOORD_0": g.accessor([prim["uv"][k] for k in sel], "VEC2", 34962)}}
                    if mi is not None:
                        p["material"] = mi
                    prims.append(p)
                g.gltf["meshes"].append({"name": name, "primitives": prims})
                gn["mesh"] = len(g.gltf["meshes"]) - 1
            elif prim and prim["position"]:
                p = {"attributes": {
                    "POSITION": g.accessor(prim["position"], "VEC3", 34962, minmax=True),
                    "NORMAL": g.accessor(prim["normal"], "VEC3", 34962),
                    "TEXCOORD_0": g.accessor(prim["uv"], "VEC2", 34962)}}
                if has_tex:
                    p["material"] = 0
                g.gltf["meshes"].append({"name": name, "primitives": [p]})
                gn["mesh"] = len(g.gltf["meshes"]) - 1
        index[name] = len(g.gltf["nodes"])
        g.gltf["nodes"].append(gn)
    for name in order:
        parent = nodes[name]["parent"]
        if parent in index:
            g.gltf["nodes"][index[parent]].setdefault("children", []).append(index[name])
        else:
            g.gltf["scenes"][0]["nodes"].append(index[name])
    report = {"nodes": len(order), "meshes": len(g.gltf["meshes"]), "animations": {}}
    for gesture in gestures:
        path = _find(tgl_dir, mech + gesture + ".ase", required=False)
        if not path:
            continue
        tracks, duration = read_animation(path)
        channels, samplers = [], []
        for node_name, tr in tracks.items():
            if node_name not in index:
                continue
            for key, path_name, kind in (("t", "translation", "VEC3"), ("r", "rotation", "VEC4")):
                if key not in tr or not tr[key]:
                    continue
                times = [s[0] for s in tr[key]]
                vals = [s[1] for s in tr[key]]
                samplers.append({"input": g.accessor(times, "SCALAR", minmax=True),
                                 "output": g.accessor(vals, kind), "interpolation": "LINEAR"})
                channels.append({"sampler": len(samplers) - 1,
                                 "target": {"node": index[node_name], "path": path_name}})
        if channels:
            g.gltf["animations"].append({"name": gesture, "channels": channels, "samplers": samplers})
            report["animations"][gesture] = round(duration, 3)
    g.write(out_path)
    return report


def material_table(tree, tgl_dir):
    """Per top-level ASE material, the TGL/128 texture of each submaterial ([own texture] for a plain one).
    None when no material is multi/sub-object, so single-material models (mechs) build exactly as before.
    Buildings use multi/sub-object materials (e.g. D_HQ: A_D_HQ + A_D_HQ2), picked per face by *MESH_MTLID;
    reading only the first diffuse left them untextured (I62)."""
    mats = tree.find("MATERIAL_LIST")
    out, any_multi = [], False

    def tex(m):
        d = m.find("MAP_DIFFUSE")
        b = d.first("BITMAP") if d else None
        return _find(os.path.join(tgl_dir, "128"), b.replace("\\", "/").split("/")[-1], required=False) if b else None
    for mat in (mats.find_all("MATERIAL") if mats else []):
        subs = mat.find_all("SUBMATERIAL")
        if subs:
            any_multi = True
            out.append([tex(sm) for sm in subs])
        else:
            out.append([tex(mat)])
    return out if any_multi else None


def material_texture(tree, tgl_dir):
    """First diffuse bitmap of the ASE material list, looked up in TGL/128."""
    mats = tree.find("MATERIAL_LIST")
    for mat in (mats.find_all("MATERIAL") if mats else []):
        diffuse = mat.find("MAP_DIFFUSE")
        bitmap = diffuse.first("BITMAP") if diffuse else None
        if bitmap:
            name = bitmap.replace("\\", "/").split("/")[-1]
            return _find(os.path.join(tgl_dir, "128"), name, required=False)
    return None


def sidecar(ini, report):
    """Model metadata from the mech's .ini (FIT): LODs, nodes, footprints, gestures."""
    gestures = []
    for i, gid in enumerate(GESTURE_IDS):
        g = ini.get(f"Gestures{i}", {})
        feet = {k: v for k, v in g.items() if k.startswith(("LeftFootDown", "RightFootDown"))}
        anim = GESTURE_TABLE[i]
        gestures.append({
            "id": gid, "animation": anim if anim in report["animations"] else "",
            "start_velocity": g.get("StartVel", 0.0), "end_velocity": g.get("EndVel", 0.0),
            "start_frame": g.get("StartFrame", 0), "reverse": g.get("Reverse", False), "foot_down": feet,
        })
    weapons = []
    for i in range(int(ini.get("Nodes", {}).get("NumWeapon", 0))):
        w = ini.get(f"WeaponNode{i}", {})
        weapons.append({"node": w.get("WeaponNodeName", ""), "type": w.get("WeaponType", 0)})
    def names(prefix, key, count_key):
        return [ini.get(f"{prefix}{i}", {}).get(key, "") for i in range(int(ini.get("Nodes", {}).get(count_key, 0)))]
    return {
        "lods": [ini["TGLData"].get(f"FileName{i}") for i in range(4) if f"FileName{i}" in ini.get("TGLData", {})],
        "shadow": ini.get("TGLData", {}).get("ShadowName", ""),
        "weapon_nodes": weapons,
        "smoke_nodes": names("SmokeNode", "SmokeNodeName", "NumSmoke"),
        "jumpjet_nodes": names("JumpJetNode", "JumpNodeName", "NumJumpJet"),
        "foot_nodes": names("FootNode", "FootNodeName", "NumFeet"),
        "gestures": gestures,
        "animations": report["animations"],
        "meters_per_unit": METERS_PER_UNIT,
        "forward": "+Z",
    }


def _find(directory, filename, required=True):
    """Case-insensitive file lookup (the data mixes BushWacker/Bushwacker)."""
    want = filename.lower()
    for f in os.listdir(directory):
        if f.lower() == want:
            return os.path.join(directory, f)
    if required:
        raise FileNotFoundError(os.path.join(directory, filename))
    return None
