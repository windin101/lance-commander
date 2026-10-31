extends SceneTree
func _init() -> void:
	var bad := 0
	for app in "chemicalplant processingplant purificationplant wasteprocessor industrialplant industrialcomplex heavyindustrial factorysm factorymd factorylg powergenerator transformerstation valvestation relaystation straightpipe1 straightpipe2 straightpipe3 cornerpipe endpipe threewaypipe fourwaypipe crane gantry".split(" "):
		for st in ["", "_damaged", "_destroyed"]:
			var p := BuildingV3.model_path(app, st)
			var ps = load(p) if p != "" else null
			if ps == null: bad += 1; print("BAD ", app, st); continue
			var n: Node3D = ps.instantiate()
			if n.find_child("lod0", true, false) == null or n.find_child("lod1", true, false) == null: bad += 1; print("NOLOD ", app, st)
			n.free()
	print("LOADED bad=", bad)
	quit()
