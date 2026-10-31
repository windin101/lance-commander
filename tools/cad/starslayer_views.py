"""Starslayer Tripo prep: untextured mid-grey orthographic views on white (our own art only).
    blender -b --factory-startup --python tools/cad/starslayer_views.py -- MESH.npz OUTDIR [size]
Views: front, left, back, q34 (same span, same centre), Workbench studio light, grey single colour."""
import sys, math
import numpy as np
import bpy
from mathutils import Vector
a = sys.argv[sys.argv.index("--") + 1:]
src, out = a[0], a[1]; size = int(a[2]) if len(a) > 2 else 1024
z = np.load(src)
bpy.ops.wm.read_factory_settings(use_empty=True)
scn = bpy.context.scene
P = z["P"] / 1000.0
me = bpy.data.meshes.new("m"); me.from_pydata(P.tolist(), [], z["F"].tolist()); me.update()
ob = bpy.data.objects.new("m", me); scn.collection.objects.link(ob)
for p in me.polygons: p.use_smooth = False
scn.render.engine = "BLENDER_WORKBENCH"
sh = scn.display.shading
sh.light = "STUDIO"; sh.color_type = "SINGLE"; sh.single_color = (0.55, 0.55, 0.56)
sh.show_cavity = True; sh.cavity_type = "BOTH"; sh.cavity_ridge_factor = 0.6; sh.cavity_valley_factor = 0.8
sh.show_shadows = False; sh.show_object_outline = False
sh.background_type = "WORLD"
w = bpy.data.worlds.new("w"); w.color = (1, 1, 1); scn.world = w
scn.view_settings.view_transform = "Standard"
scn.render.resolution_x = scn.render.resolution_y = size
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); scn.collection.objects.link(cam); scn.camera = cam
cam.data.type = "ORTHO"; cam.data.ortho_scale = float(a[3]) if len(a) > 3 else 11.6; cam.data.clip_end = 1000
ctr = Vector(tuple(float(v) for v in a[4].split(","))) if len(a) > 4 else Vector((0, 0.1, 4.95))   # metres
V = {"front": (0, -1, 0), "left": (1, 0, 0), "back": (0, 1, 0), "q34": (0.62, -0.62, 0.42)}
for n, d in V.items():
    d = Vector(d).normalized()
    cam.location = ctr + d * 40
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    scn.render.filepath = f"{out}/{n}.png"
    bpy.ops.render.render(write_still=True)
