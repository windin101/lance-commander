"""Blender (headless bpy) half of tools/art/hd_v2.py. Run by hd_v2.py, not by hand:

    blender -b --factory-startup --python tools/art/hd_v2_blender.py -- preview REST.npz OUT.png [--key P] [--size 900]
    blender -b --factory-startup --python tools/art/hd_v2_blender.py -- bake REST.npz OUTDIR [--tex 2048] [--samples 64]

REST.npz: P (n, 3) game mm Z up, F (nf, 3), part (nf,), kind (nf,) 0 sculpt 1 cap 2 sleeve 3 actuator, N (nf, 3, 3)
per-corner normals. preview: Workbench renders coloured by part (fillers grey, actuators red) from four yaws.
bake: Smart UV Project (islands never cross parts: parts share no vertices), one atlas packed at a shared texel
density, then Cycles bakes at --tex: ambient occlusion, a tangent-space normal map of the corner normals with a
Bevel node (rounded machined edges), object-space position and corner normal (float), part index. Writes
uv.npz (uv per corner, v up as Blender has it) and bake_ao.png, bake_normal.png, bake_pos.npy, bake_nrm.npy,
bake_part.npy, bake_cover.npy (texels inside an island).
"""
import math
import sys
from pathlib import Path

import bpy
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
mode, src, out = argv[0], argv[1], argv[2]
opt = {argv[i][2:]: argv[i + 1] for i in range(3, len(argv) - 1, 2) if argv[i].startswith("--")}
z = np.load(src)
if mode == "decimate":
    bpy.ops.wm.read_factory_settings(use_empty=True)
    me = bpy.data.meshes.new("hi")
    me.from_pydata((z["P"] / 1000.0).tolist(), [], z["F"].tolist())
    a_ = me.attributes.new("part", "INT", "FACE"); a_.data.foreach_set("value", z["part"].astype(np.int32))
    ob = bpy.data.objects.new("hi", me); bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob; ob.select_set(True)
    # A printed kit is a fused soup of shells: collapse alone crumples it (2026-10-23, LRM carrier). Merge by
    # distance, dissolve coplanar faces (flat panels carry most of a kit's triangles), triangulate, then collapse
    # only what is still over budget, at most to 35 % per pass.
    bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=float(opt.get("merge", 0.0005)))
    bpy.ops.mesh.dissolve_limited(angle_limit=math.radians(float(opt.get("planar_deg", 2.0))), delimit={"NORMAL"})
    bpy.ops.mesh.quads_convert_to_tris(quad_method="BEAUTY", ngon_method="BEAUTY")
    bpy.ops.object.mode_set(mode="OBJECT")
    target = float(opt.get("faces", 24000))
    print("PLANAR", len(z["F"]), "->", len(ob.data.polygons))
    for _ in range(4):
        n_ = len(ob.data.polygons)
        if n_ <= target * 1.05:
            break
        md = ob.modifiers.new("dec", "DECIMATE")
        md.decimate_type = "COLLAPSE"; md.ratio = max(0.35, target / n_); md.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier="dec")
    me = ob.data
    V = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get("co", V)
    nl = np.zeros(len(me.polygons), np.int32); me.polygons.foreach_get("loop_total", nl)
    assert (nl == 3).all(), "decimate left non-triangles"
    Fi = np.zeros(len(me.loops), np.int32); me.loops.foreach_get("vertex_index", Fi)
    pt = np.zeros(len(me.polygons), np.int32); me.attributes["part"].data.foreach_get("value", pt)
    np.savez_compressed(out, P=V.reshape(-1, 3) * 1000.0, F=Fi.reshape(-1, 3), part=pt)
    print("DECIMATED", len(z["F"]), "->", len(pt))
    sys.exit(0)
P = z[opt.get("key", "P")] / 1000.0 if opt.get("key", "P") in z.files else z["P"] / 1000.0
F, part, kind, N = z["F"], z["part"], z["kind"], z["N"]

bpy.ops.wm.read_factory_settings(use_empty=True)
scn = bpy.context.scene
me = bpy.data.meshes.new("hd")
me.from_pydata(P.tolist(), [], F.tolist())
assert len(me.polygons) == len(F), "from_pydata dropped faces"
me.normals_split_custom_set(N.reshape(-1, 3).tolist())
ob = bpy.data.objects.new("hd", me)
scn.collection.objects.link(ob)
bpy.context.view_layer.objects.active = ob
ob.select_set(True)
pa = me.attributes.new("part", "INT", "FACE")
pa.data.foreach_set("value", part.astype(np.int32))


def corner_colours(name, rgb_per_face):
    ca = me.color_attributes.new(name, "FLOAT_COLOR", "CORNER")
    c = np.repeat(np.c_[rgb_per_face, np.ones(len(rgb_per_face))], 3, axis=0)
    ca.data.foreach_set("color", c.astype(np.float32).ravel())
    return ca


if mode == "preview":
    ids = np.unique(part)
    base = [(0.9, 0.3, 0.3), (0.3, 0.8, 0.3), (0.3, 0.4, 0.95), (0.95, 0.85, 0.2), (0.85, 0.3, 0.9), (0.2, 0.85, 0.85),
            (0.95, 0.55, 0.15), (0.55, 0.3, 0.15), (0.6, 0.6, 0.6), (0.98, 0.98, 0.98), (0.4, 0.15, 0.6), (0.1, 0.45, 0.2),
            (0.95, 0.6, 0.7), (0.5, 0.7, 0.3), (0.2, 0.2, 0.5), (0.7, 0.5, 0.4)]
    pal = {p: np.array(base[i % len(base)]) for i, p in enumerate(ids)}
    print("LEGEND", " ".join(f"{p}:{','.join(str(int(c * 255)) for c in pal[p])}" for p in ids))
    rgb = np.array([pal[p] for p in part])
    rgb[kind == 1] = (0.25, 0.25, 0.28)
    rgb[kind == 2] = (0.4, 0.4, 0.42)
    rgb[kind == 3] = (0.05, 0.05, 0.05)
    ca = corner_colours("col", rgb)
    me.color_attributes.active_color = ca
    scn.render.engine = "BLENDER_WORKBENCH"
    sh = scn.display.shading
    sh.light = "STUDIO"
    sh.color_type = "VERTEX"
    sh.show_cavity = True
    sh.show_backface_culling = True
    scn.render.film_transparent = False
    world = bpy.data.worlds.new("w"); scn.world = world
    size = int(opt.get("size", 900))
    scn.render.resolution_x = scn.render.resolution_y = size
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scn.collection.objects.link(cam); scn.camera = cam
    cam.data.lens = 70
    lo, hi = P.min(0), P.max(0)
    ctr = (lo + hi) / 2
    h = float(hi[2] - lo[2])
    dist = h * 2.6
    from mathutils import Vector
    tiles = []
    yaws = [float(y) for y in opt.get("yaws", "-35,55,145,235").split(",")]
    for k, yaw in enumerate(yaws):
        a = math.radians(yaw)
        pos = Vector((ctr[0] + dist * math.sin(a), ctr[1] - dist * math.cos(a), ctr[2] + h * 0.25))
        cam.location = pos
        d = Vector(ctr.tolist()) - pos
        cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        fn = f"{out}.{k}.png"
        scn.render.filepath = fn
        bpy.ops.render.render(write_still=True)
        tiles.append(fn)
    print("PREVIEW", " ".join(tiles))

elif mode == "bakeao":   # buildings: AO only, on the UV set given in REST.npz["UV"] (per corner)
    tex = int(opt.get("tex", 1024))
    outd = Path(out); outd.mkdir(parents=True, exist_ok=True)
    uvl = me.uv_layers.new(name="ao")
    uvl.data.foreach_set("uv", z["UV"].astype(np.float32).ravel())
    scn.render.engine = "CYCLES"; scn.cycles.device = "CPU"; scn.cycles.samples = int(opt.get("samples", 96))
    scn.render.bake.margin = 6; scn.render.bake.margin_type = "EXTEND"
    world = bpy.data.worlds.new("w"); scn.world = world
    world.light_settings.distance = float(opt.get("ao_dist", 3.0))
    # a ground plane, so walls darken where they meet the ground
    gp = bpy.data.meshes.new("ground"); lo_, hi_ = P.min(0), P.max(0); m_ = 20.0
    gp.from_pydata([(lo_[0] - m_, lo_[1] - m_, 0), (hi_[0] + m_, lo_[1] - m_, 0), (hi_[0] + m_, hi_[1] + m_, 0), (lo_[0] - m_, hi_[1] + m_, 0)], [], [(0, 1, 2, 3)])
    gob = bpy.data.objects.new("ground", gp); scn.collection.objects.link(gob)
    mat = bpy.data.materials.new("bake"); mat.use_nodes = True; me.materials.append(mat)
    nt = mat.node_tree
    img_node = nt.nodes.new("ShaderNodeTexImage"); nt.nodes.active = img_node
    im = bpy.data.images.new("ao", tex, tex, alpha=False); im.colorspace_settings.name = "Non-Color"; img_node.image = im
    bpy.context.view_layer.objects.active = ob; ob.select_set(True); gob.select_set(False)
    bpy.ops.object.bake(type="AO")
    im.filepath_raw = str(outd / "bake_ao.png"); im.file_format = "PNG"; im.save()
    emit = nt.nodes.new("ShaderNodeEmission"); nt.links.new(emit.outputs["Emission"], nt.nodes["Material Output"].inputs["Surface"])
    emit.inputs["Color"].default_value = (1, 1, 1, 1)
    im2 = bpy.data.images.new("cov", tex, tex, alpha=False, float_buffer=True); img_node.image = im2
    scn.cycles.samples = 1; scn.render.bake.margin = 0
    bpy.ops.object.bake(type="EMIT")
    a_ = np.zeros(tex * tex * 4, np.float32); im2.pixels.foreach_get(a_)
    np.save(outd / "bake_cover.npy", a_.reshape(tex, tex, 4)[::-1][..., 0] > 0.5)
    print("BAKED AO", outd)

elif mode == "bake":
    tex = int(opt.get("tex", 2048))
    outd = Path(out); outd.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    # Smart UV Project packs the islands itself at one scale (shared texel density). A separate pack_islands shrank
    # this atlas to 2 % coverage (one outlier island sets the scale), so it is not used.
    bpy.ops.uv.smart_project(angle_limit=math.radians(float(opt.get("angle", 66))), island_margin=float(opt.get("margin", 0.0003)),
                             area_weight=0.0, correct_aspect=True, scale_to_bounds=True)  # island_margin is per island: 0.003 shrank 4000 islands to 3 % coverage
    bpy.ops.object.mode_set(mode="OBJECT")
    uv = np.zeros(len(me.loops) * 2, np.float32)
    me.uv_layers.active.data.foreach_get("uv", uv)
    np.savez_compressed(outd / "uv.npz", uv=uv.reshape(-1, 2))
    print("UV islands packed", tex)

    scn.render.engine = "CYCLES"
    scn.cycles.device = "CPU"
    scn.cycles.samples = int(opt.get("samples", 64))
    scn.render.bake.margin = 8
    scn.render.bake.margin_type = "EXTEND"
    world = bpy.data.worlds.new("w"); scn.world = world
    world.light_settings.distance = float(opt.get("ao_dist", 0.8))
    mat = bpy.data.materials.new("bake")
    mat.use_nodes = True
    me.materials.append(mat)
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    img_node = nt.nodes.new("ShaderNodeTexImage")
    nt.nodes.active = img_node

    def new_img(name, is_float=False):
        im = bpy.data.images.new(name, tex, tex, alpha=False, float_buffer=is_float)
        if not is_float:
            im.colorspace_settings.name = "Non-Color"
        img_node.image = im
        return im

    def grab(im):
        a = np.zeros(tex * tex * 4, np.float32)
        im.pixels.foreach_get(a)
        return a.reshape(tex, tex, 4)[::-1]  # top row first, as a PNG

    def save_png(im, path):
        im.filepath_raw = str(path); im.file_format = "PNG"; im.save()

    hi = None
    if "hi" in opt:   # bake AO and normals from the full-resolution sculpt onto this game mesh
        zh = np.load(opt["hi"])
        mh = bpy.data.meshes.new("hi"); mh.from_pydata((zh["P"] / 1000.0).tolist(), [], zh["F"].tolist())
        mh.shade_smooth() if hasattr(mh, "shade_smooth") else None
        hi = bpy.data.objects.new("hi", mh); scn.collection.objects.link(hi)
        hm = bpy.data.materials.new("hi_mat"); hm.use_nodes = True; mh.materials.append(hm)
        hi.select_set(True); ob.select_set(True); bpy.context.view_layer.objects.active = ob
        scn.render.bake.use_selected_to_active = True
        scn.render.bake.cage_extrusion = float(opt.get("cage", 0.03))
        scn.render.bake.max_ray_distance = float(opt.get("ray", 0.12))
    # 1. ambient occlusion
    im = new_img("ao")
    bpy.ops.object.bake(type="AO")
    save_png(im, outd / "bake_ao.png")
    if hi is not None:
        im = new_img("normal")
        scn.cycles.samples = 16
        bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT")
        save_png(im, outd / "bake_normal.png")
        tn = outd / "bake_normal_true.png"
        if tn.exists():
            tn.unlink()
        scn.render.bake.use_selected_to_active = False
        hi.hide_render = True; hi.select_set(False)
    if hi is None:
        # 2. normal map with rounded edges (game mesh = sculpt; with a hi-poly source the map above is the detail)
        bev = nt.nodes.new("ShaderNodeBevel")
        bev.samples = 8
        bev.inputs["Radius"].default_value = float(opt.get("bevel", 0.012))
        nt.links.new(bev.outputs["Normal"], bsdf.inputs["Normal"])
        im = new_img("normal")
        scn.cycles.samples = 16
        bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT")
        save_png(im, outd / "bake_normal.png")
        # the Bevel node works from the flat geometric normal, so its map also carries every facet; bake the true
        # (flat) normal too: hd_v2.py keeps only bevel minus true, the rounded edges, on top of the smooth normals
        geo_t = nt.nodes.new("ShaderNodeNewGeometry")
        nt.links.new(geo_t.outputs["True Normal"], bsdf.inputs["Normal"])
        im = new_img("normal_true")
        bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT")
        save_png(im, outd / "bake_normal_true.png")
        nt.links.remove(bsdf.inputs["Normal"].links[0])
    # 3. emission bakes of data: position, corner normal, part index, coverage
    emit = nt.nodes.new("ShaderNodeEmission")
    outn = nt.nodes["Material Output"]
    nt.links.new(emit.outputs["Emission"], outn.inputs["Surface"])
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    scn.cycles.samples = 1
    scn.render.bake.margin = 0

    def bake_emit(socket, name):
        nt.links.new(socket, emit.inputs["Color"])
        im = new_img(name, is_float=True)
        bpy.ops.object.bake(type="EMIT")
        return grab(im)
    np.save(outd / "bake_pos.npy", bake_emit(geo.outputs["Position"], "pos")[..., :3].astype(np.float32))
    np.save(outd / "bake_nrm.npy", bake_emit(geo.outputs["Normal"], "nrm")[..., :3].astype(np.float16))
    attr = nt.nodes.new("ShaderNodeAttribute"); attr.attribute_name = "part"; attr.attribute_type = "GEOMETRY"
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(attr.outputs["Fac"], comb.inputs["X"])
    comb.inputs["Y"].default_value = 1.0
    np.save(outd / "bake_part.npy", bake_emit(comb.outputs["Vector"], "part")[..., :2].astype(np.float32))
    ka = me.attributes.new("kind", "INT", "FACE")
    ka.data.foreach_set("value", kind.astype(np.int32))
    attr.attribute_name = "kind"
    kb = bake_emit(comb.outputs["Vector"], "kind")
    np.save(outd / "bake_kind.npy", kb[..., 0].astype(np.float32))
    np.save(outd / "bake_cover.npy", (kb[..., 1] > 0.5))
    fa_ = me.attributes.new("fid", "INT", "FACE")
    fa_.data.foreach_set("value", np.arange(len(F), dtype=np.int32))
    attr.attribute_name = "fid"
    np.save(outd / "bake_fid.npy", np.round(bake_emit(comb.outputs["Vector"], "fid")[..., 0]).astype(np.int32))
    print("BAKED", outd)
