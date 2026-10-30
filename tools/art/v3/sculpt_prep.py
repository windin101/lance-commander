"""Prepare a dense image-to-3D sculpt (npz P, F in game mm, already aligned) for Pipeline A.   (Blender, headless)
    blender -b --factory-startup --python tools/art/v3/sculpt_prep.py -- IN.npz OUT.npz [--faces 350000] [--floor 0]
Weld by distance (0.5 mm), clip everything below z = FLOOR with a capped cut (flat soles), merge coplanar faces
(dissolve 2 deg), triangulate, then collapse-decimate in passes of at most 35 % to the face budget (one big collapse
crumples a fused shell soup).  Prints the face counts."""
import sys, math
import numpy as np
import bpy, bmesh
a = sys.argv[sys.argv.index("--") + 1:]
src, out = a[0], a[1]
faces = int(a[a.index("--faces") + 1]) if "--faces" in a else 350000
floor = float(a[a.index("--floor") + 1]) if "--floor" in a else 0.0
z = np.load(src)
bpy.ops.wm.read_factory_settings(use_empty=True)
me = bpy.data.meshes.new("s"); me.from_pydata((z["P"] / 1000.0).tolist(), [], z["F"].tolist()); me.update()
ob = bpy.data.objects.new("s", me); bpy.context.scene.collection.objects.link(ob)
bm = bmesh.new(); bm.from_mesh(me)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
print("welded", len(bm.faces), "faces", flush=True)
g = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, floor / 1000.0), plane_no=(0, 0, 1),
                           clear_inner=True, use_snap_center=False)
cut = [e for e in g["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
try:
    bmesh.ops.holes_fill(bm, edges=cut, sides=64)
except Exception as e:
    print("cap failed:", e)
bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(2.0), verts=bm.verts, edges=bm.edges)
bmesh.ops.triangulate(bm, faces=bm.faces)
bm.to_mesh(me); bm.free()
n = len(me.polygons); print("before decimate", n, flush=True)
bpy.context.view_layer.objects.active = ob
while n > faces:
    ratio = max(faces / n, 0.65)
    m = ob.modifiers.new("d", "DECIMATE"); m.decimate_type = "COLLAPSE"; m.ratio = ratio; m.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=m.name)
    n = len(ob.data.polygons); print("  ->", n, flush=True)
me = ob.data
P = np.array([v.co[:] for v in me.vertices]) * 1000.0
F = np.array([p.vertices[:] for p in me.polygons])
np.savez(out, P=P, F=F)
print("done", len(F), "faces, z", P[:, 2].min().round(1), P[:, 2].max().round(1))
