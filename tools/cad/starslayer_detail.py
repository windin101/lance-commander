"""Starslayer in-house model, step 2 (Blender, headless): the detail pass.   LANCE-36
    blender -b --factory-startup --python tools/cad/starslayer_detail.py -- HULLS.npz OUT.npz
HULLS.npz comes from tools/cad/starslayer_blockout.py.  Per part: dissolve each hull to flat polygons, bevel it,
raise armour plates (inset + extrude on the big flat faces), union the hulls into one shell (exact booleans),
cut vent slots, and write the welded triangles with one label per part.  Metres inside Blender, mm in the file.
"""
import sys, math
import numpy as np
import bpy, bmesh
from mathutils import Vector

hp, outp = sys.argv[sys.argv.index("--") + 1:][:2]
Z = np.load(hp)
n = int(Z["n"][0]); names = [str(x) for x in Z["names"]]
bpy.ops.wm.read_factory_settings(use_empty=True)
S = 0.001
BEVEL = 0.032
SLOTS = {   # part: list of (x0, x1, y0, y1, z0, z1) cutters in mm (depth ~60 into the surface)
    "ss_torso": [(-650, 650, 2290, 2420, 6850 + 260 * i, 6850 + 260 * i + 100) for i in range(5)]
              + [(1990 + dx, 2070 + dx, -300, 1100, 7450 + 250 * i, 7450 + 250 * i + 80) for i in range(3) for dx in (0,)]
              + [(-2070, -1990, -300, 1100, 7450 + 250 * i, 7450 + 250 * i + 80) for i in range(3)],
    "ss_ruarm": [(-3300, -3200, -2100 + 280 * i, -2100 + 280 * i + 90, 6800, 7600) for i in range(4)],
    "ss_gun": [(-1760, -1740, -1400 + 300 * i, -1400 + 300 * i + 90, 8250, 8800) for i in range(4)]
            + [(-830, -810, -1400 + 300 * i, -1400 + 300 * i + 90, 8250, 8800) for i in range(4)],
    "ss_lgun": [(3090, 3170, -1200 + 260 * i, -1200 + 260 * i + 80, 6400, 6900) for i in range(4)],
    "ss_luleg": [(2190, 2230, -700 + 250 * i, -700 + 250 * i + 80, 3700, 4700) for i in range(3)],
    "ss_ruleg": [(-2230, -2190, -700 + 250 * i, -700 + 250 * i + 80, 3700, 4700) for i in range(3)],
}


def mk(name, V, F):
    me = bpy.data.meshes.new(name)
    me.from_pydata((np.asarray(V) * S).tolist(), [], [list(map(int, f)) for f in F])
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def apply_mod(ob, mod):
    bpy.context.view_layer.objects.active = ob
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.ops.object.modifier_apply(modifier=mod.name)


def prep(ob, plates):
    bm = bmesh.new(); bm.from_mesh(ob.data)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(1.0), verts=bm.verts, edges=bm.edges)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data); bm.free()
    m = ob.modifiers.new("bev", "BEVEL")
    m.width = BEVEL; m.segments = 2; m.limit_method = "ANGLE"; m.angle_limit = math.radians(20); m.profile = 0.6
    apply_mod(ob, m)
    if not plates:
        return
    bm = bmesh.new(); bm.from_mesh(ob.data)
    big = [f for f in bm.faces if f.calc_area() > 0.3 and len(f.verts) <= 8]
    if big:
        r = bmesh.ops.inset_region(bm, faces=big, thickness=0.09, depth=0.025, use_even_offset=True, use_boundary=True)
        top = [f for f in big if f.is_valid and f.calc_area() > 0.35]      # second tier on the roomy plates
        if top:
            bmesh.ops.inset_region(bm, faces=top, thickness=0.10, depth=-0.02, use_even_offset=True, use_boundary=True)
    bm.to_mesh(ob.data); bm.free()


def boolean(a, b, op):
    m = a.modifiers.new("b", "BOOLEAN")
    m.object = b; m.operation = op; m.solver = "EXACT"
    apply_mod(a, m)
    bpy.data.objects.remove(b, do_unlink=True)


groups = {}
for i in range(n):
    groups.setdefault(names[i], []).append(i)
Pall, Fall, lab, pn, off = [], [], [], [], 0
for ci, (part, ids) in enumerate(groups.items()):
    obs = []
    for i in ids:
        ob = mk(f"{part}_{i}", Z[f"V{i}"], Z[f"F{i}"])
        prep(ob, plates=not part.startswith("toe"))
        obs.append(ob)
    main = obs[0]
    for o in obs[1:]:
        boolean(main, o, "UNION")
    for (x0, x1, y0, y1, z0, z1) in SLOTS.get(part, []):
        c = mk("cut", [[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)],
               [[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5], [0, 4, 5], [0, 5, 1], [2, 3, 7], [2, 7, 6], [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]])
        bm = bmesh.new(); bm.from_mesh(c.data); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(c.data); bm.free()
        boolean(main, c, "DIFFERENCE")
    bm = bmesh.new(); bm.from_mesh(main.data)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    V = np.array([v.co[:] for v in bm.verts]) / S
    F = np.array([[v.index for v in f.verts] for f in bm.faces])
    bm.free()
    print(part, "hulls", len(ids), "tris", len(F), flush=True)
    Pall.append(V); Fall.append(F + off); lab += [ci] * len(F); off += len(V); pn.append(part)
np.savez(outp, P=np.concatenate(Pall), F=np.concatenate(Fall), part=np.array(lab), names=np.array(pn))
print("done", off, "verts")
