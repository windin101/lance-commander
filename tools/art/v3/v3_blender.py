"""Blender (headless bpy) half of the v3 HD pipeline (tools/art/v3/v3_mech.py). CPU only: Workbench for previews,
Cycles on the CPU device for bakes. Run by v3_mech.py:

    blender -b --factory-startup --python tools/art/v3/v3_blender.py -- views IN.npz OUTPREFIX [--size 1400]
        [--views front,side,back,top,q34] [--span MM] [--centre x,y,z]

IN.npz: P (n, 3) game mm Z up (forward -Y), F (nf, 3), optional col (nf, 3) 0..1 face colours.
views: orthographic Workbench renders, one PNG per view, plus OUTPREFIX.json with each view's camera mapping
(pixel = (world . right - r0) * ppm, (top - world . up) * ppm) so callers can draw a millimetre grid.
"""
import json
import math
import sys

import bpy
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
mode, src, out = argv[0], argv[1], argv[2]
opt = {argv[i][2:]: argv[i + 1] for i in range(3, len(argv) - 1, 2) if argv[i].startswith("--")}

VIEWS = {  # name: (camera direction from the target, up); rts<yaw>: the game camera's pitch from yaw (deg)
    "front": ((0, -1, 0), (0, 0, 1)),     # the mech faces -Y: seen from the front
    "back": ((0, 1, 0), (0, 0, 1)),
    "side": ((1, 0, 0), (0, 0, 1)),       # from +X (the mech's left side)
    "rside": ((-1, 0, 0), (0, 0, 1)),
    "top": ((0, 0, 1), (0, -1, 0)),
    "bottom": ((0, 0, -1), (0, 1, 0)),
    "q34": ((0.62, -0.62, 0.48), (0, 0, 1)),
    "q34b": ((-0.62, 0.62, 0.48), (0, 0, 1)),
}


def mesh_from(z, name="m"):
    me = bpy.data.meshes.new(name)
    me.from_pydata((z["P"] / 1000.0).tolist(), [], z["F"].tolist())
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if "col" in z.files:
        c = np.repeat(np.c_[z["col"], np.ones(len(z["col"]))], 3, axis=0)
        ca = me.color_attributes.new("col", "FLOAT_COLOR", "CORNER")
        ca.data.foreach_set("color", c.astype(np.float32).ravel())
        me.color_attributes.active_color = ca
    return ob, me


def views():
    z = np.load(src)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scn = bpy.context.scene
    ob, me = mesh_from(z)
    scn.render.engine = "BLENDER_WORKBENCH"
    sh = scn.display.shading
    flat = bool(int(opt.get("flat", 0)))
    sh.light = "FLAT" if flat else "STUDIO"
    sh.color_type = "VERTEX" if "col" in z.files else "MATERIAL"
    sh.show_cavity = not flat
    if flat:
        scn.view_settings.view_transform = "Standard"
        scn.render.dither_intensity = 0.0
        scn.display.render_aa = "OFF"
        scn.render.image_settings.color_depth = "8"
    sh.cavity_type = "BOTH"
    sh.show_backface_culling = bool(int(opt.get("cull", 1)))
    scn.world = bpy.data.worlds.new("w")
    size = int(opt.get("size", 1400))
    scn.render.resolution_x = scn.render.resolution_y = size
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scn.collection.objects.link(cam)
    scn.camera = cam
    cam.data.type = "ORTHO"
    P = z["P"] / 1000.0
    lo, hi = P.min(0), P.max(0)
    ctr = np.array([float(v) for v in opt["centre"].split(",")]) / 1000.0 if "centre" in opt else (lo + hi) / 2
    span = float(opt.get("span", 0)) / 1000.0 or float((hi - lo).max()) * 1.08
    cam.data.ortho_scale = span
    cam.data.clip_end = 1000
    meta = {}
    for name in opt.get("views", "front,side,back,top,q34").split(","):
        if name.startswith("rts"):
            yw = float(name[3:]); pt = float(opt.get("pitch", 50))
            d = (math.sin(math.radians(yw)) * math.cos(math.radians(pt)), -math.cos(math.radians(yw)) * math.cos(math.radians(pt)), math.sin(math.radians(pt)))
            up = (0, 0, 1)
        else:
            d, up = VIEWS[name]
        d = Vector(d).normalized()
        pos = Vector(ctr.tolist()) + d * 60.0
        cam.location = pos
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y" if name != "top" else "Y").to_euler()
        if name == "top":
            cam.rotation_euler = (0, 0, 0)   # looking down -Z, image up = +Y
        if name == "bottom":
            cam.rotation_euler = (math.pi, 0, 0)
        scn.render.filepath = f"{out}_{name}.png"
        bpy.ops.render.render(write_still=True)
        bpy.context.view_layer.update()
        mw = cam.matrix_world
        right = (mw.to_3x3() @ Vector((1, 0, 0))).normalized()
        upv = (mw.to_3x3() @ Vector((0, 1, 0))).normalized()
        c = Vector(ctr.tolist())
        meta[name] = {"right": list(right), "up": list(upv), "centre_mm": [v * 1000 for v in c], "span_mm": span * 1000,
                      "size": size}
    json.dump(meta, open(f"{out}.json", "w"), indent=1)
    print("VIEWS", out)


if mode == "views":
    views()


# --- lowpoly + UV atlas ---------------------------------------------------------------------------------------

def lowpoly():
    """IN.npz: P (mm), F, part (int), kind (int: 0 sculpt/deck, 1 contact cap, 2 actuator), budget (per part int
    target faces). One object per part and kind: merge, planar dissolve, triangulate, collapse to budget; Smart UV
    Project; then all join: islands at one texel density (average scale), caps and actuators at --minor_scale of it,
    packed into one atlas. OUT.npz: P, F, part, kind, uv (per corner)."""
    import bmesh
    z = np.load(src)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scn = bpy.context.scene
    P = z["P"] / 1000.0
    F, part, kind = z["F"], z["part"], z["kind"]
    budget = {int(k): int(v) for k, v in zip(z["budget_part"], z["budget_faces"])}
    objs = []
    for p in np.unique(part):
        for k in np.unique(kind[part == p]):
            m = (part == p) & (kind == k)
            used = np.unique(F[m]); remap = -np.ones(len(P), int); remap[used] = np.arange(len(used))
            me = bpy.data.meshes.new(f"p{p}k{k}")
            me.from_pydata(P[used].tolist(), [], remap[F[m]].tolist())
            ob = bpy.data.objects.new(f"p{p}k{k}", me)
            scn.collection.objects.link(ob)
            ob["part"] = int(p); ob["kind"] = int(k)
            for o in scn.objects:
                o.select_set(False)
            bpy.context.view_layer.objects.active = ob; ob.select_set(True)
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.remove_doubles(threshold=0.0002)
            bpy.ops.mesh.dissolve_limited(angle_limit=math.radians(float(opt.get("planar_deg", 1.0))), delimit={"NORMAL"})
            bpy.ops.mesh.quads_convert_to_tris(quad_method="BEAUTY", ngon_method="BEAUTY")
            bpy.ops.object.mode_set(mode="OBJECT")
            # the part's budget goes to its sculpt surface; caps get a small fixed share (film caps are dense but
            # flat, so counting their faces would starve the armour: Urbanmech, 2026-10-24)
            target = int(budget.get(int(p), 3000)) if k == 0 else max(60, int(budget.get(int(p), 3000) * 0.08))
            if k == 2:
                target = len(ob.data.polygons)   # actuators are already game density
            n_ = len(ob.data.polygons)
            if n_ > target:
                md = ob.modifiers.new("dec", "DECIMATE")
                md.decimate_type = "COLLAPSE"; md.ratio = target / n_; md.use_collapse_triangulate = True
                bpy.ops.object.modifier_apply(modifier="dec")
            if opt.get("uv", "smart") == "none":
                print("PART", p, "kind", k, n_, "->", len(ob.data.polygons))
                objs.append(ob)
                continue
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.uv.smart_project(angle_limit=math.radians(float(opt.get("uv_angle", 50))), island_margin=0.0,
                                     area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
            bpy.ops.object.mode_set(mode="OBJECT")
            print("PART", p, "kind", k, n_, "->", len(ob.data.polygons))
            objs.append(ob)
    if opt.get("uv", "smart") == "none":   # geometry only: UVs come from tools/art/v3/v3_xatlas.py
        Ps, Fs, pts, kds, off = [], [], [], [], 0
        for o in objs:
            me = o.data
            V = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get("co", V)
            nl = np.zeros(len(me.polygons), np.int32); me.polygons.foreach_get("loop_total", nl)
            assert (nl == 3).all()
            Fi = np.zeros(len(me.loops), np.int32); me.loops.foreach_get("vertex_index", Fi)
            Ps.append(V.reshape(-1, 3) * 1000.0); Fs.append(Fi.reshape(-1, 3) + off); off += len(me.vertices)
            pts.append(np.full(len(me.polygons), o["part"])); kds.append(np.full(len(me.polygons), o["kind"]))
        np.savez_compressed(out, P=np.concatenate(Ps), F=np.concatenate(Fs), part=np.concatenate(pts), kind=np.concatenate(kds))
        print("LOWPOLY", off, "verts")
        return
    # join, one density, minor islands smaller, pack
    for o in scn.objects:
        o.select_set(False)
    for o in objs:
        me = o.data
        a = me.attributes.new("part", "INT", "FACE"); a.data.foreach_set("value", np.full(len(me.polygons), o["part"], np.int32))
        a = me.attributes.new("kind", "INT", "FACE"); a.data.foreach_set("value", np.full(len(me.polygons), o["kind"], np.int32))
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    print("AVG", bpy.ops.uv.average_islands_scale())
    bm = bmesh.from_edit_mesh(ob.data)
    uvl = bm.loops.layers.uv.active
    kl = bm.faces.layers.int.get("kind")
    minor = float(opt.get("minor_scale", 0.5))
    # islands: connected faces in UV space (flood over edges whose UVs agree)
    seen = set()
    for f in bm.faces:
        if f.index in seen or f[kl] == 0:
            continue
        stack, isl = [f], []
        seen.add(f.index)
        while stack:
            g = stack.pop(); isl.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index in seen or h[kl] != g[kl]:
                        continue
                    # same island if the shared edge's UVs match
                    def uvs(face):
                        return {l.vert.index: l[uvl].uv.copy() for l in face.loops}
                    ug, uh = uvs(g), uvs(h)
                    ok = all((ug[v.index] - uh[v.index]).length < 1e-6 for v in e.verts)
                    if ok:
                        seen.add(h.index); stack.append(h)
        cs = [l[uvl].uv.copy() for g in isl for l in g.loops]
        c = sum(cs, cs[0] * 0) / len(cs)
        for g in isl:
            for l in g.loops:
                l[uvl].uv = c + (l[uvl].uv - c) * minor
    bmesh.update_edit_mesh(ob.data)
    print("PACK", bpy.ops.uv.pack_islands(rotate=True, rotate_method=opt.get("rotate_method", "ANY"), scale=True,
                            margin_method="FRACTION", margin=float(opt.get("margin", 0.0025)),
                            shape_method=opt.get("shape_method", "CONCAVE")))
    bpy.ops.object.mode_set(mode="OBJECT")
    me = ob.data
    V = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get("co", V)
    nl = np.zeros(len(me.polygons), np.int32); me.polygons.foreach_get("loop_total", nl)
    assert (nl == 3).all()
    Fi = np.zeros(len(me.loops), np.int32); me.loops.foreach_get("vertex_index", Fi)
    uv = np.zeros(len(me.loops) * 2, np.float32); me.uv_layers.active.data.foreach_get("uv", uv)
    pt = np.zeros(len(me.polygons), np.int32); me.attributes["part"].data.foreach_get("value", pt)
    kd = np.zeros(len(me.polygons), np.int32); me.attributes["kind"].data.foreach_get("value", kd)
    np.savez_compressed(out, P=V.reshape(-1, 3) * 1000.0, F=Fi.reshape(-1, 3), part=pt, kind=kd, uv=uv.reshape(-1, 2))
    print("LOWPOLY", len(pt), "faces")


if mode == "lowpoly":
    lowpoly()


# --- bakes ------------------------------------------------------------------------------------------------------

def bake():
    """IN = low.npz (P mm, F, part, kind, uv per corner), OUT = directory; --hi rest.npz (the full-detail sculpt in
    the rest pose). Cycles on the CPU. Writes normal.png (tangent space, the sculpt with rounded edges, MikkTSpace on
    the low mesh's own split normals), ao.png, edge.npy (convex/concave edge strength from the bevel), and float
    data bakes pos.npy (rest position mm), nrm.npy (object normal), fid.npy (low face id), cover.npy; plus
    low_shading.npz: per-corner normals and tangents (with bitangent sign) for the game mesh."""
    from pathlib import Path
    z = np.load(src)
    outd = Path(out); outd.mkdir(parents=True, exist_ok=True)
    tex = int(opt.get("tex", 2048))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scn = bpy.context.scene
    P = z["P"] / 1000.0
    me = bpy.data.meshes.new("low")
    me.from_pydata(P.tolist(), [], z["F"].tolist())
    assert len(me.polygons) == len(z["F"])
    uvl = me.uv_layers.new(name="UV")
    uvl.data.foreach_set("uv", z["uv"].astype(np.float32).ravel())
    fa = me.attributes.new("fid", "INT", "FACE"); fa.data.foreach_set("value", np.arange(len(z["F"]), dtype=np.int32))
    lo = bpy.data.objects.new("low", me); scn.collection.objects.link(lo)
    bpy.context.view_layer.objects.active = lo; lo.select_set(True)
    # split normals: smooth within --smooth_deg, hard across sharper edges and between parts/kinds (UV seams too)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(float(opt.get("smooth_deg", 33))))
    me.calc_tangents(uvmap="UV")
    nl = np.zeros(len(me.loops) * 3, np.float32); me.loops.foreach_get("normal", nl)
    tl = np.zeros(len(me.loops) * 3, np.float32); me.loops.foreach_get("tangent", tl)
    bs = np.zeros(len(me.loops), np.float32); me.loops.foreach_get("bitangent_sign", bs)
    np.savez_compressed(outd / "low_shading.npz", normal=nl.reshape(-1, 3), tangent=tl.reshape(-1, 3), sign=bs)
    # the high: the rest-pose sculpt, flat faces (a printed kit is hard surface)
    zh = np.load(opt["hi"])
    mh = bpy.data.meshes.new("hi"); mh.from_pydata((zh["P"] / 1000.0).tolist(), [], zh["F"].tolist())
    hi = bpy.data.objects.new("hi", mh); scn.collection.objects.link(hi)
    ha = mh.attributes.new("hid", "INT", "FACE"); ha.data.foreach_set("value", np.arange(len(zh["F"]), dtype=np.int32))
    # curved armour (the skull dome, round housings) is faceted in the print: shade it smooth below --hi_smooth_deg,
    # so the normal map carries the curve, not the facets; box edges stay sharp
    for o in scn.objects:
        o.select_set(False)
    hi.select_set(True); bpy.context.view_layer.objects.active = hi
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(float(opt.get("hi_smooth_deg", 20))))
    hi.select_set(False); bpy.context.view_layer.objects.active = lo; lo.select_set(True)
    scn.render.engine = "CYCLES"; scn.cycles.device = "CPU"
    scn.cycles.samples = int(opt.get("samples", 64))
    scn.render.bake.margin = int(opt.get("margin", 8)); scn.render.bake.margin_type = "EXTEND"
    world = bpy.data.worlds.new("w"); scn.world = world
    world.light_settings.distance = float(opt.get("ao_dist", 1.2))
    # materials: low gets the image target; high gets the bevel shading
    ml = bpy.data.materials.new("low_m"); ml.use_nodes = True; me.materials.append(ml)
    ntl = ml.node_tree
    img = ntl.nodes.new("ShaderNodeTexImage"); ntl.nodes.active = img
    mhm = bpy.data.materials.new("hi_m"); mhm.use_nodes = True; mh.materials.append(mhm)
    nth = mhm.node_tree
    bsdf_h = nth.nodes["Principled BSDF"]
    bev = nth.nodes.new("ShaderNodeBevel"); bev.samples = int(opt.get("bevel_samples", 12))
    bev.inputs["Radius"].default_value = float(opt.get("bevel", 0.035))
    nth.links.new(bev.outputs["Normal"], bsdf_h.inputs["Normal"])

    def new_img(name, is_float=False):
        im = bpy.data.images.new(name, tex, tex, alpha=False, float_buffer=is_float)
        if not is_float:
            im.colorspace_settings.name = "Non-Color"
        img.image = im
        return im

    def grab(im):
        a = np.zeros(tex * tex * 4, np.float32); im.pixels.foreach_get(a)
        return a.reshape(tex, tex, 4)[::-1]

    def save(im, name):
        im.filepath_raw = str(outd / name); im.file_format = "PNG"; im.save()

    def sel_to_active(on):
        for o in scn.objects:
            o.select_set(False)
        lo.select_set(True); bpy.context.view_layer.objects.active = lo
        hi.select_set(on)
        hi.hide_render = not on
        scn.render.bake.use_selected_to_active = on
        if on:
            scn.render.bake.cage_extrusion = float(opt.get("cage", 0.04))
            scn.render.bake.max_ray_distance = float(opt.get("ray", 0.15))
    import time
    t0 = time.time()
    # 1. tangent-space normal from the bevelled sculpt
    sel_to_active(True)
    scn.cycles.samples = int(opt.get("normal_samples", 16))
    im = new_img("normal"); bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT"); save(im, "normal.png")
    print("BAKE normal", round(time.time() - t0)); t0 = time.time()
    # 2. ambient occlusion of the sculpt (the whole mech at rest occludes itself)
    scn.cycles.samples = int(opt.get("ao_samples", 128))
    im = new_img("ao"); bpy.ops.object.bake(type="AO"); save(im, "ao.png")
    print("BAKE ao", round(time.time() - t0)); t0 = time.time()
    # 3. edge strength: 1 - dot(bevelled normal, true normal) on the sculpt, signed by convexity below
    emit_h = nth.nodes.new("ShaderNodeEmission")
    geo_h = nth.nodes.new("ShaderNodeNewGeometry")
    dot = nth.nodes.new("ShaderNodeVectorMath"); dot.operation = "DOT_PRODUCT"
    nth.links.new(bev.outputs["Normal"], dot.inputs[0]); nth.links.new(geo_h.outputs["True Normal"], dot.inputs[1])
    sub = nth.nodes.new("ShaderNodeMath"); sub.operation = "SUBTRACT"; sub.inputs[0].default_value = 1.0
    nth.links.new(dot.outputs["Value"], sub.inputs[1])
    nth.links.new(sub.outputs[0], emit_h.inputs["Color"])
    nth.links.new(emit_h.outputs["Emission"], nth.nodes["Material Output"].inputs["Surface"])
    scn.cycles.samples = int(opt.get("edge_samples", 16))
    im = new_img("edge", True); bpy.ops.object.bake(type="EMIT")
    np.save(outd / "edge.npy", grab(im)[..., 0].astype(np.float16))
    bev.inputs["Radius"].default_value = float(opt.get("bevel_wide", 0.09))
    im = new_img("edge_wide", True); bpy.ops.object.bake(type="EMIT")
    np.save(outd / "edge_wide.npy", grab(im)[..., 0].astype(np.float16))
    bev.inputs["Radius"].default_value = float(opt.get("bevel", 0.035))
    print("BAKE edge", round(time.time() - t0)); t0 = time.time()
    # the high's face id under each texel (rest.npz face index): panels and mask rules follow the sculpt's own faces
    attr_h = nth.nodes.new("ShaderNodeAttribute"); attr_h.attribute_name = "hid"; attr_h.attribute_type = "GEOMETRY"
    comb_h = nth.nodes.new("ShaderNodeCombineXYZ")
    nth.links.new(attr_h.outputs["Fac"], comb_h.inputs["X"]); comb_h.inputs["Y"].default_value = 1.0
    nth.links.new(comb_h.outputs["Vector"], emit_h.inputs["Color"])
    scn.cycles.samples = 1
    scn.render.bake.margin = 0
    im = new_img("hid", True); bpy.ops.object.bake(type="EMIT")
    hb = grab(im)
    np.save(outd / "hid.npy", np.where(hb[..., 1] > 0.5, np.round(hb[..., 0]), -1).astype(np.int32))
    scn.render.bake.margin = int(opt.get("margin", 8))
    # short-range AO: tells a convex edge (open) from a concave one (crease)
    sel_to_active(True)
    world.light_settings.distance = float(opt.get("ao_short", 0.15))
    scn.cycles.samples = int(opt.get("ao_samples", 128)) // 2
    nth.links.new(bsdf_h.outputs["BSDF"], nth.nodes["Material Output"].inputs["Surface"])
    im = new_img("ao_short"); bpy.ops.object.bake(type="AO"); save(im, "ao_short.png")
    print("BAKE hid+ao_short", round(time.time() - t0)); t0 = time.time()
    # 4. data bakes on the low itself
    sel_to_active(False)
    scn.render.bake.margin = 0
    scn.cycles.samples = 1
    emit = ntl.nodes.new("ShaderNodeEmission")
    ntl.links.new(emit.outputs["Emission"], ntl.nodes["Material Output"].inputs["Surface"])
    geo = ntl.nodes.new("ShaderNodeNewGeometry")

    def bake_emit(socket, name):
        ntl.links.new(socket, emit.inputs["Color"])
        im = new_img(name, True); bpy.ops.object.bake(type="EMIT")
        return grab(im)
    np.save(outd / "pos.npy", (bake_emit(geo.outputs["Position"], "pos")[..., :3] * 1000.0).astype(np.float32))
    np.save(outd / "nrm.npy", bake_emit(geo.outputs["Normal"], "nrm")[..., :3].astype(np.float16))
    attr = ntl.nodes.new("ShaderNodeAttribute"); attr.attribute_name = "fid"; attr.attribute_type = "GEOMETRY"
    comb = ntl.nodes.new("ShaderNodeCombineXYZ")
    ntl.links.new(attr.outputs["Fac"], comb.inputs["X"]); comb.inputs["Y"].default_value = 1.0
    fb = bake_emit(comb.outputs["Vector"], "fid")
    np.save(outd / "fid.npy", np.where(fb[..., 1] > 0.5, np.round(fb[..., 0]), -1).astype(np.int32))
    print("BAKE data", round(time.time() - t0))
    print("BAKED", outd)


if mode == "bake":
    bake()


# --- look-dev renders (Cycles CPU) ------------------------------------------------------------------------------

def lookdev():
    """IN = low.npz, OUT = prefix; --maps DIR with albedo.png (RGB colour, A paint coverage ignored here), orm.png,
    normal.png (any missing: grey / flat). --pose NPZ (P per vertex) poses the mesh. Views as `views`, Cycles CPU
    with a sun and a sky, --samples. Writes OUT_<view>.png."""
    from pathlib import Path
    z = np.load(src)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scn = bpy.context.scene
    P = (np.load(opt["pose"])["P"] if "pose" in opt else z["P"]) / 1000.0
    me = bpy.data.meshes.new("low"); me.from_pydata(P.tolist(), [], z["F"].tolist())
    uvl = me.uv_layers.new(name="UV"); uvl.data.foreach_set("uv", z["uv"].astype(np.float32).ravel())
    ob = bpy.data.objects.new("low", me); scn.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob; ob.select_set(True)
    if "shading" in opt and "pose" not in opt:
        sh = np.load(opt["shading"])
        me.normals_split_custom_set(sh["normal"].tolist())
    else:
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(float(opt.get("smooth_deg", 33))))
    mat = bpy.data.materials.new("m"); mat.use_nodes = True; me.materials.append(mat)
    nt = mat.node_tree; bsdf = nt.nodes["Principled BSDF"]
    maps = Path(opt.get("maps", "."))
    def tex(name, colour):
        p = maps / name
        if not p.exists():
            return None
        n = nt.nodes.new("ShaderNodeTexImage"); n.image = bpy.data.images.load(str(p))
        n.image.colorspace_settings.name = "sRGB" if colour else "Non-Color"
        return n
    a = tex("albedo.png", True)
    if a:
        nt.links.new(a.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (0.42, 0.42, 0.42, 1)
    o = tex("orm.png", False)
    if o:
        sep = nt.nodes.new("ShaderNodeSeparateColor"); nt.links.new(o.outputs["Color"], sep.inputs["Color"])
        nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"]); nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
        if not a:
            mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"
            mul.inputs["Factor"].default_value = 1.0
            mul.inputs["A"].default_value = (0.5, 0.5, 0.5, 1)
            nt.links.new(sep.outputs["Red"], mul.inputs["B"])
            nt.links.new(mul.outputs["Result"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Roughness"].default_value = 0.6
        aot = tex("ao.png", False)
        if aot and not a:
            nt.links.new(aot.outputs["Color"], bsdf.inputs["Base Color"])
    n = tex("normal.png", False)
    if n:
        nm = nt.nodes.new("ShaderNodeNormalMap"); nm.uv_map = "UV"
        nt.links.new(n.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    scn.render.engine = "CYCLES"; scn.cycles.device = "CPU"; scn.cycles.samples = int(opt.get("samples", 32))
    scn.cycles.use_denoising = True
    scn.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.new("w"); scn.world = world; world.use_nodes = True
    sky = world.node_tree.nodes.new("ShaderNodeTexSky")
    try:
        sky.sky_type = "HOSEK_WILKIE"
    except Exception:
        pass
    world.node_tree.links.new(sky.outputs["Color"], world.node_tree.nodes["Background"].inputs["Color"])
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = float(opt.get("sky", 0.35))
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); scn.collection.objects.link(sun)
    sun.data.energy = float(opt.get("sun", 3.5)); sun.rotation_euler = (math.radians(50), 0, math.radians(35))
    size = int(opt.get("size", 900)); scn.render.resolution_x = scn.render.resolution_y = size
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); scn.collection.objects.link(cam); scn.camera = cam
    cam.data.type = "ORTHO"
    lo_, hi_ = P.min(0), P.max(0)
    ctr = np.array([float(v) for v in opt["centre"].split(",")]) / 1000.0 if "centre" in opt else (lo_ + hi_) / 2
    cam.data.ortho_scale = float(opt.get("span", 0)) / 1000.0 or float((hi_ - lo_).max()) * 1.08
    for name in opt.get("views", "q34").split(","):
        if name.startswith("rts"):
            yw = float(name[3:]); pt = float(opt.get("pitch", 35))
            d = Vector((math.sin(math.radians(yw)) * math.cos(math.radians(pt)), -math.cos(math.radians(yw)) * math.cos(math.radians(pt)), math.sin(math.radians(pt))))
        else:
            d = Vector(VIEWS[name][0]).normalized()
        cam.location = Vector(ctr.tolist()) + d * 60.0
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        scn.render.filepath = f"{out}_{name}.png"
        bpy.ops.render.render(write_still=True)
    print("LOOKDEV", out)


if mode == "lookdev":
    lookdev()
