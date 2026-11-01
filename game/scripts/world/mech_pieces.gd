class_name MechPieces
## Scrap on the map (mechpiece_* objects, LANCE-39): torn-off torsos, arms and legs built at load from the committed v3 mech wreck parts
## (assets/v3/mechs/<mech>_wreck.glb, one mesh per part), re-centred on the ground, yawed and tilted per placement, painted with the mech's own v3
## textures. No new files: the piece kinds map to part-name suffixes below.

const MECHS := ["atlas", "bushwacker"]   # the wrecks the scrap is cut from, picked by placement index
const KINDS := {
	"mechpiece_torso1": ["torso"], "mechpiece_torso2": ["torso", "hip"],
	"mechpiece_arm1": ["luarm", "llarm", "lgun"], "mechpiece_arm2": ["ruarm", "rgun"],
	"mechpiece_leg1": ["luleg", "llleg", "lfoot"], "mechpiece_leg2": ["ruleg", "rlleg", "rfoot"],
	"mechpiece_legs": ["luleg", "llleg", "lfoot", "ruleg", "rlleg", "rfoot", "hip"],
}


## The AABB of a mesh in the root's frame, from local transforms only (the nodes are not in a tree here).
static func rel_transform(n: Node, root: Node) -> Transform3D:
	var t := Transform3D.IDENTITY
	var cur: Node = n
	while cur != null and cur != root:
		if cur is Node3D:
			t = (cur as Node3D).transform * t
		cur = cur.get_parent()
	return t


static func piece(app: String, index: int) -> Node3D:
	if not KINDS.has(app):
		return null
	var mech: String = MECHS[index % MECHS.size()]
	var path := ArtV3.model_path("mechs", mech + "_wreck")
	if path == "":
		return null
	var wreck: Node3D = (load(path) as PackedScene).instantiate()
	var want: Array = KINDS[app]
	var keep: Array[MeshInstance3D] = []
	for m in wreck.find_children("*", "MeshInstance3D", true, false):
		var nm := String(m.name)
		var us := nm.find("_")
		if us < 0:
			continue
		if nm.substr(us + 1) in want:
			keep.append(m as MeshInstance3D)
	if keep.is_empty():
		wreck.free()
		return null
	var root := Node3D.new()
	var low := 1e9
	var lo := Vector3(1e9, 1e9, 1e9)
	var hi := Vector3(-1e9, -1e9, -1e9)
	for m in keep:
		var bb := rel_transform(m, wreck) * m.mesh.get_aabb()
		lo = lo.min(bb.position)
		hi = hi.max(bb.end)
	var centre := (lo + hi) * 0.5
	var tilt := Basis(Vector3.UP, float(hash(index) % 628) / 100.0) * Basis(Vector3.RIGHT, deg_to_rad(float((hash(index) >> 3) % 17) - 8.0))
	for m in keep:
		var c := MeshInstance3D.new()
		c.mesh = m.mesh
		c.transform = Transform3D(tilt, Vector3.ZERO) * Transform3D(Basis.IDENTITY, -Vector3(centre.x, lo.y, centre.z)) * rel_transform(m, wreck)
		root.add_child(c)
	wreck.free()
	ArtV3.apply(root, mech, {"mode": "mask", "base": "#6a6a58", "hl1": "#8a7a5a", "hl2": "#3f4338"}, "mechs")
	var bot := 1e9
	for c in root.get_children():
		var mi := c as MeshInstance3D
		bot = minf(bot, ((mi.transform) * mi.mesh.get_aabb()).position.y)
	root.position.y = -bot if bot < 1e8 else 0.0
	var wrap := Node3D.new()
	wrap.add_child(root)
	return wrap
