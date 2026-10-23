class_name SystemsMonitor
extends PanelContainer
## Systems monitor (bottom right; the original's info tab, restyled to the approved mock-up):
## shown only while a unit is selected. Front and rear paper dolls, armour and heat gauges
## (heat with the shutdown line from the rules, HeatShutdown), the per-location armour and
## structure table, pilot skills, and the weapons grouped by type with range colour, ammo
## and recycle bar.

const MECH_LOCS := ["HD", "CT", "LT", "RT", "LA", "RA", "LL", "RL"]  # SimMech.Body order
const VEHICLE_LOCS := ["FR", "LS", "RS", "RR", "TU"]  # SimVehicle.Section order
const WIDTH_EM := 31.8

var kit: HudKit
var world: SimWorld
var unit: SimUnit
var title: Label
var small: Label
var front: DollView
var rear: DollView
var armor_bar: HudKit.Bar
var armor_val: Label
var heat_row: Control
var heat_bar: HudKit.Bar
var heat_val: Label
var locs: GridContainer
var pilot_grid: GridContainer
var weapons: GridContainer
var _loc_cells: Array = []  # [armour Label, structure Label] per location
var _weapon_rows: Array = []  # [name Label, ammo Label, Bar, group]


func _init(hud_kit: HudKit, sim_world: SimWorld) -> void:
	kit = hud_kit
	world = sim_world
	visible = false
	add_theme_stylebox_override("panel", UiStyle.HudFrame.make(kit.u))
	custom_minimum_size.x = kit.em(WIDTH_EM)
	mouse_filter = Control.MOUSE_FILTER_STOP
	var p := kit.panel("Systems", "")
	# reuse the panel builder's body but not its frame: take its children
	var v: VBoxContainer = p["body"]
	p["panel"].remove_child(v)
	p["panel"].free()
	add_child(v)
	title = p["title"]
	small = p["small"]
	var body := kit.margin(0.8, 0.7, 0.8, 0.4)
	v.add_child(body)
	var cols := kit.hbox(0.6)
	body.add_child(cols)
	for is_rear in [false, true]:
		var col := kit.vbox(0.1)
		col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		col.size_flags_stretch_ratio = 0.9
		cols.add_child(col)
		var d := DollView.new(null, is_rear)
		d.custom_minimum_size = Vector2(kit.em(7.6), kit.em(10.0))
		d.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		col.add_child(d)
		var cap := kit.label("REAR" if is_rear else "FRONT", "mono", 0.8, UiStyle.HUD_DIM)
		cap.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		col.add_child(cap)
		if is_rear:
			rear = d
		else:
			front = d
	var g := kit.vbox(0.5)
	g.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	g.size_flags_stretch_ratio = 1.35
	cols.add_child(g)
	var a := _gauge("Armor", "ok")
	g.add_child(a[0])
	armor_bar = a[1]
	armor_val = a[2]
	var h := _gauge("Heat", "heat")
	heat_row = h[0]
	g.add_child(heat_row)
	heat_bar = h[1]
	heat_val = h[2]
	heat_bar.mark = float(world.rules.heat.get("shutdown_level", 25)) / 30.0 if world else 25.0 / 30.0
	locs = GridContainer.new()
	locs.columns = 3
	locs.add_theme_constant_override("h_separation", roundi(kit.em(0.5)))
	locs.add_theme_constant_override("v_separation", 0)
	g.add_child(locs)
	pilot_grid = GridContainer.new()
	pilot_grid.columns = 2
	pilot_grid.add_theme_constant_override("h_separation", roundi(kit.em(0.6)))
	pilot_grid.add_theme_constant_override("v_separation", 0)
	g.add_child(pilot_grid)
	var wm := kit.margin(0.8, 0.0, 0.8, 0.8)
	v.add_child(wm)
	weapons = GridContainer.new()
	weapons.columns = 3
	weapons.add_theme_constant_override("h_separation", roundi(kit.em(0.6)))
	weapons.add_theme_constant_override("v_separation", roundi(kit.em(0.2)))
	wm.add_child(weapons)


func _gauge(caption: String, mode: String) -> Array:
	var box := kit.vbox(0.15)
	var lbl := kit.hbox(0.5)
	box.add_child(lbl)
	var t := kit.label(caption, "display600", 0.85 * 0.95, UiStyle.HUD_DIM, true, 0.1)
	t.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	lbl.add_child(t)
	var val := kit.label("", "mono", 0.95 * 0.95, UiStyle.HUD_INK)
	lbl.add_child(val)
	var b := kit.bar(0.45, mode)
	box.add_child(b)
	return [box, b, val]


## Show the systems of a unit (null hides the monitor).
func show_unit(u: SimUnit) -> void:
	visible = u != null
	if u == unit:
		return
	unit = u
	if u == null:
		return
	title.text = "Systems · %s" % u.name
	small.text = "%s · %d t" % [(u.pilot.name if u.pilot else u.name), roundi(u.tonnage)] if u.tonnage > 0.0 else (u.pilot.name if u.pilot else "")
	front.set_unit(u)
	rear.set_unit(u)
	rear.get_parent().visible = u is SimMech
	heat_row.visible = u.uses_heat
	_build_locs()
	_build_pilot()
	_build_weapons()
	refresh()


func _cell(text: String, colour := UiStyle.HUD_INK, right := true) -> Label:
	var l := kit.label(text, "mono", 0.82 * 0.95, colour)
	if right:
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	return l


func _build_locs() -> void:
	for c in locs.get_children():
		c.queue_free()
	_loc_cells.clear()
	var names: Array = MECH_LOCS if unit is SimMech else VEHICLE_LOCS
	for i in names.size():
		locs.add_child(_cell(names[i], UiStyle.HUD_DIM, false))
		var a := _cell("")
		var s := _cell("")
		locs.add_child(a)
		locs.add_child(s)
		_loc_cells.append([a, s])


func _build_pilot() -> void:
	for c in pilot_grid.get_children():
		c.queue_free()
	var p: SimPilot = unit.pilot
	if p == null:
		return
	var skills: Dictionary = GameData.pilots.get(unit.pilot_profile, {}).get("Skills", {}) if GameData else {}
	var rows := [["GUNNERY", p.gunnery], ["PILOTING", p.piloting]]
	if skills.has("Sensors"):
		rows.append(["SENSORS", skills["Sensors"]])
	rows.append(["WOUNDS", p.wounds])
	for r in rows:
		var rt := RichTextLabel.new()
		rt.bbcode_enabled = true
		rt.fit_content = true
		rt.scroll_active = false
		rt.autowrap_mode = TextServer.AUTOWRAP_OFF
		rt.mouse_filter = Control.MOUSE_FILTER_IGNORE
		rt.add_theme_font_override("normal_font", UiStyle.font("mono"))
		rt.add_theme_font_size_override("normal_font_size", kit.px(0.85 * 0.95))
		rt.add_theme_color_override("default_color", UiStyle.HUD_DIM)
		rt.text = "%s [color=#%s]%d[/color]" % [r[0], UiStyle.HUD_INK.to_html(false), roundi(float(r[1]))]
		pilot_grid.add_child(rt)


## Weapons grouped by component, as the original's info tab: [{label, range, items}].
static func weapon_groups(u: SimUnit) -> Array:
	var order: Array = []
	var by_name := {}
	for inv in u.weapon_indices():
		var n: String = u.items[inv]["component"]["name"]
		if not by_name.has(n):
			by_name[n] = {"name": n, "range": String(u.weapon(inv).get("range", "")), "items": []}
			order.append(n)
		by_name[n]["items"].append(inv)
	var out := []
	for n in order:
		var g: Dictionary = by_name[n]
		var short := String(g["name"]).replace(" Pack", "").replace(" Rack", "").replace("Autocannon (AC10)", "AC/10")
		g["label"] = short if g["items"].size() == 1 else "%s ×%d" % [short, g["items"].size()]
		out.append(g)
	return out


func _build_weapons() -> void:
	for c in weapons.get_children():
		c.queue_free()
	_weapon_rows.clear()
	for h in [["Weapon", true], ["Ammo", false], ["Cooldown", false]]:
		var l := kit.label(h[0], "display600", 0.78 * 0.95, UiStyle.HUD_DIM, true, 0.12)
		if h[1]:
			l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		weapons.add_child(l)
	for g in weapon_groups(unit):
		var name_row := kit.hbox(0.35)
		name_row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var sw := ColorRect.new()
		sw.color = UiStyle.RANGE_COLOURS.get(g["range"], UiStyle.HUD_DIM)
		sw.custom_minimum_size = Vector2(kit.em(0.65), kit.em(0.65))
		sw.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		sw.mouse_filter = Control.MOUSE_FILTER_IGNORE
		name_row.add_child(sw)
		var nm := kit.label(g["label"], "body400", 0.95, UiStyle.HUD_INK)
		name_row.add_child(nm)
		weapons.add_child(name_row)
		var am := kit.label("", "mono", 0.9, UiStyle.HUD_INK)
		am.custom_minimum_size.x = kit.em(3.0)
		weapons.add_child(am)
		var b := kit.bar(0.45, "cool")
		b.custom_minimum_size.x = kit.em(5.5)
		weapons.add_child(b)
		_weapon_rows.append([nm, am, b, g])


func _process(_delta: float) -> void:
	if visible and unit:
		refresh()


func refresh() -> void:
	var a := PaperDoll.armor_fraction(unit)
	armor_bar.value = a
	armor_val.text = "%d%%" % roundi(a * 100.0)
	if unit.uses_heat:
		heat_bar.value = unit.heat / maxf(unit.heat_capacity, 0.01)
		heat_val.text = "%d / %d" % [roundi(unit.heat), roundi(unit.heat_capacity)]
	var internal: Array = unit.get("internal") if unit.get("internal") != null else []
	var max_internal: Array = unit.get("max_internal") if unit.get("max_internal") != null else []
	for i in _loc_cells.size():
		var ar: float = unit.armor[i]
		var am: float = unit.max_armor[i]
		_set_cell(_loc_cells[i][0], ar, am)
		if i < internal.size():
			_set_cell(_loc_cells[i][1], internal[i], max_internal[i])
	var now := world.time if world else 0.0
	for r in _weapon_rows:
		var g: Dictionary = r[3]
		var best := 0.0
		var dead := true
		var shots := -1
		var energy := true
		for inv in g["items"]:
			var item: Dictionary = unit.items[inv]
			if item["disabled"]:
				continue
			dead = false
			var recycle := float(unit.weapon(inv).get("recycle", 1.0))
			best = maxf(best, 1.0 - clampf((float(item["ready_time"]) - now) / maxf(recycle, 0.01), 0.0, 1.0))
			shots = unit.weapon_shots(inv)
			energy = not unit.uses_ammo(inv)
		r[0].add_theme_color_override("font_color", UiStyle.HUD_DIM if dead else UiStyle.HUD_INK)
		r[1].text = ("—" if energy else "∞") if shots < 0 else str(shots)  # ∞: unlimited ammo (O2)
		r[2].value = 0.0 if dead else best


func _set_cell(l: Label, cur: float, mx: float) -> void:
	l.text = "%d/%d" % [roundi(cur), roundi(mx)]
	var f := cur / mx if mx > 0.0 else 1.0
	l.add_theme_color_override("font_color", UiStyle.HUD_CRIT if f < 0.3 else (UiStyle.HUD_WARN if f < 0.75 else UiStyle.HUD_INK))
