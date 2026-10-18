class_name AblRuntime
extends RefCounted
## Executes parsed ABL units (AblParser). One runtime per mission: it loads the brain
## libraries (orders, miscfunc, corebrain; their consts, types and routines are global),
## caches compiled units by file, and creates an Instance per running module or FSM.
##
## Semantics, as the 2001 scripts rely on them:
## - static vars are per instance; eternal vars are per compiled file (shared by every
##   unit running the same brain) and also visible by name to every other script: the
##   brains read the mission script's eternal flags (mc2_01_pat1 reads patrol1_triggered)
##   without declaring them. A script's own declarations win; otherwise the first file
##   loaded that declares the name (the mission script) owns it. Library statics are
##   global the same way (mc2_06_wv1_guard2 sets corebrain's CoreRun). Plain vars are
##   fresh per call.
## - An FSM runs its init function once, then the current state's code each execute().
##   trans / setState abort the rest of the running code at once (even from inside a
##   called function) and the new state runs in the same execute(), up to 50 times.
## - Orders: an order called as a statement inside a state or order stops that block
##   when it returns 0 (not finished). When it returns non-zero, that call site is
##   marked done for the instance and skipped on later executes until resetOrders.
##   Call sites in library code are never marked.
## - Integer / integer is integer division and x / 0 gives 0. and/or don't short-circuit.
##
## Game functions are natives: register_native(name, Callable(instance, args) -> value).
## Arrays arrive by reference (natives fill out-parameters in place). Calls to unknown
## routines return 0 and are counted in `unknown` (the coverage list for phase 10).

const LIBRARIES := ["orders", "miscfunc", "corebrain"]
const MAX_TRANSITIONS := 50

var base_dir: String
var natives: Dictionary = {}  # lowercase name -> Callable(inst: Instance, args: Array) -> Variant
var unknown: Dictionary = {}  # routine name -> call count
var log_lines: Array[String] = []
var rng := RandomNumberGenerator.new()
var errors: Array[String] = []

var _units: Dictionary = {}  # path -> unit
var _libs: Array = []  # library units in load order
var _lib_inst: Dictionary = {}  # library name -> Instance
var _global_consts: Dictionary = {}  # name -> [unit, expr]
var _global_types: Dictionary = {}  # name -> [unit, typespec]
var _global_routines: Dictionary = {}  # name -> [unit, routine]
var _global_eternals: Dictionary = {}  # name -> unit that owns the storage


class Ref:
	## A by-reference scalar parameter: reads and writes go to the caller's slot.
	var vals
	var key
	var rtype: Dictionary

	func _init(v, k, t: Dictionary) -> void:
		vals = v
		key = k
		rtype = t


class Frame:
	var vals: Dictionary = {}
	var types: Dictionary = {}
	var unit: Dictionary
	var owner: Instance
	var routine: Dictionary
	var ret: Variant = 0
	var done := false


class Instance:
	var runtime: AblRuntime
	var unit: Dictionary
	var statics: Dictionary = {}
	var static_types: Dictionary = {}
	var module_vals: Dictionary = {}
	var module_types: Dictionary = {}
	var state := ""
	var prev_state := ""
	var init_called := false
	var new_state_set := false
	var order_flags: Dictionary = {}
	var host: Variant = null  # the game object this brain drives (natives use it)
	var return_value: Variant = 0

	func execute() -> Variant:
		return runtime._execute(self)

	func state_handle() -> int:
		return unit["states"].find(state) + 1


func _init(abl_dir: String = "res://data/abl", seed := 0) -> void:
	base_dir = abl_dir
	rng.seed = seed
	for lib in LIBRARIES:
		var u := load_unit(base_dir.path_join(lib + ".abx"))
		if u.has("error"):
			errors.append(u["error"])
			continue
		_libs.append(u)
		for n in u["consts"]:
			_global_consts[n] = [u, u["consts"][n]]
		for n in u["types"]:
			_global_types[n] = [u, u["types"][n]]
		for n in u["routines"]:
			if u["routines"][n]["kind"] != "state":
				_global_routines[n] = [u, u["routines"][n]]
		_lib_inst[u["name"]] = _new_instance(u)


func register_native(name: String, fn: Callable) -> void:
	natives[name.to_lower()] = fn


## Parse (cached by path) without instancing. Returns the unit or {"error": ...}.
func load_unit(path: String) -> Dictionary:
	if _units.has(path):
		return _units[path]
	var u := AblParser.parse_file(path)
	if not u.has("error"):
		u["_eternals"] = {}
		u["_eternal_types"] = {}
		u["_const_cache"] = {}
		for n in u["var_order"]:
			var v: Dictionary = u["vars"][n]
			if v["storage"] == "eternal":
				var rt := resolve_type(u, v["type"])
				u["_eternals"][n] = default_value(rt)
				u["_eternal_types"][n] = rt
				if not _global_eternals.has(n):
					_global_eternals[n] = u
	_units[path] = u
	return u


## A running copy of a module or FSM (e.g. one per warrior). path is relative to base_dir.
func instantiate(rel_path: String) -> Instance:
	var dir := rel_path.get_base_dir() if rel_path.contains("://") else base_dir.path_join(rel_path.get_base_dir())
	var path := AblParser.resolve_path(dir, rel_path.get_file())
	if path == "":
		errors.append("%s: not found" % rel_path)
		return null
	var u := load_unit(path)
	if u.has("error"):
		errors.append(u["error"])
		return null
	return _new_instance(u)


func _new_instance(u: Dictionary) -> Instance:
	var inst := Instance.new()
	inst.runtime = self
	inst.unit = u
	for n in u["var_order"]:
		var v: Dictionary = u["vars"][n]
		if v["storage"] == "static":
			var rt := resolve_type(u, v["type"])
			inst.statics[n] = default_value(rt)
			inst.static_types[n] = rt
	if u["kind"] == "fsm":
		inst.state = "start" if u["routines"].has("start") else (u["states"][0] if u["states"].size() > 0 else "")
	return inst


# --- types and values ----------------------------------------------------------------

func resolve_type(u: Dictionary, spec: Dictionary) -> Dictionary:
	if spec.has("_r"):
		return spec["_r"]
	var base: String = spec["base"]
	var dims: Array = []
	for d in spec["dims"]:
		dims.append(int(_const_eval(u, d)))
	var r: Dictionary
	if base in ["integer", "real", "boolean", "char"]:
		r = {"base": base, "dims": dims}
	else:
		var alias = u["types"].get(base)
		var owner := u
		if alias == null and _global_types.has(base):
			owner = _global_types[base][0]
			alias = _global_types[base][1]
		if alias == null:
			errors.append("%s: unknown type %s" % [u["file"], base])
			r = {"base": "integer", "dims": dims}
		else:
			var inner := resolve_type(owner, alias)
			r = {"base": inner["base"], "dims": dims + inner["dims"]}
	spec["_r"] = r
	return r


static func default_value(rt: Dictionary) -> Variant:
	var base: String = rt["base"]
	var dims: Array = rt["dims"]
	if base == "char":
		dims = dims.slice(0, dims.size() - 1)  # char[n] is a string
	if dims.is_empty():
		return _zero(base)
	var n := 1
	for d in dims:
		n *= maxi(int(d), 1)
	var a := []
	a.resize(n)
	a.fill(_zero(base))
	return a


static func _zero(base: String) -> Variant:
	match base:
		"real":
			return 0.0
		"boolean":
			return false
		"char":
			return ""
	return 0


static func coerce(base: String, v: Variant) -> Variant:
	match base:
		"integer":
			if v is float:
				return int(v)
			if v is bool:
				return 1 if v else 0
			return v if v is int else 0
		"real":
			return float(v) if (v is int or v is float or v is bool) else 0.0
		"boolean":
			if v is bool:
				return v
			return v != 0 if (v is int or v is float) else false
		"char":
			return str(v)
	return v


func _const_eval(u: Dictionary, e: Dictionary) -> Variant:
	match e["k"]:
		"num", "str":
			return e["v"]
		"name":
			return _const_value(u, e["name"])
		"neg":
			return -_num(_const_eval(u, e["a"]))
		"bin":
			return _binop(e["op"], _const_eval(u, e["a"]), _const_eval(u, e["b"]))
	return 0


func _const_value(u: Dictionary, name: String) -> Variant:
	if name == "true":
		return true
	if name == "false":
		return false
	var cache: Dictionary = u.get("_const_cache", {})
	if cache.has(name):
		return cache[name]
	var owner := u
	var e = u["consts"].get(name)
	if e == null and _global_consts.has(name):
		owner = _global_consts[name][0]
		e = _global_consts[name][1]
	if e == null:
		return null
	var v = _const_eval(owner, e)
	cache[name] = v
	return v


# --- execution ------------------------------------------------------------------------

func _execute(inst: Instance) -> Variant:
	var u := inst.unit
	inst.module_vals = {}
	inst.module_types = {}
	for n in u["var_order"]:
		var v: Dictionary = u["vars"][n]
		if v["storage"] == "local":
			var rt := resolve_type(u, v["type"])
			inst.module_vals[n] = default_value(rt)
			inst.module_types[n] = rt
	inst.new_state_set = false
	if not inst.init_called:
		inst.init_called = true
		if u["routines"].has("init"):
			_call_declared(inst, null, u, u["routines"]["init"], [], [])
	if u["kind"] == "fsm":
		inst.new_state_set = true
		var n := 0
		while inst.new_state_set and n < MAX_TRANSITIONS:
			inst.new_state_set = false
			n += 1
			var st = u["routines"].get(inst.state)
			if st == null:
				errors.append("%s: no state %s" % [u["file"], inst.state])
				break
			_call_declared(inst, null, u, st, [], [])
		inst.new_state_set = false
		return 0
	var f := Frame.new()
	f.unit = u
	f.owner = inst
	f.routine = {"kind": "module", "site_lo": 0, "site_hi": u["sites"]}
	_exec_block(inst, f, u["code"])
	inst.return_value = f.ret
	return f.ret


func _exec_block(inst: Instance, f: Frame, stmts: Array) -> void:
	for s in stmts:
		if f.done or inst.new_state_set:
			return
		_exec(inst, f, s)


func _exec(inst: Instance, f: Frame, s: Dictionary) -> void:
	match s["k"]:
		"assign":
			_assign(inst, f, s["name"], s["idx"], _eval(inst, f, s["e"]))
		"call":
			_call_stmt(inst, f, s)
		"if":
			for arm in s["arms"]:
				if _truthy(_eval(inst, f, arm[0])):
					_exec_block(inst, f, arm[1])
					return
			_exec_block(inst, f, s["else"])
		"while":
			var guard := 0
			while _truthy(_eval(inst, f, s["c"])):
				_exec_block(inst, f, s["body"])
				if f.done or inst.new_state_set:
					return
				guard += 1
				if guard > 100000:
					errors.append("%s:%d: loop limit" % [f.unit["file"], s["line"]])
					return
		"repeat":
			var guard := 0
			while true:
				_exec_block(inst, f, s["body"])
				if f.done or inst.new_state_set:
					return
				if _truthy(_eval(inst, f, s["c"])):
					return
				guard += 1
				if guard > 100000:
					errors.append("%s:%d: loop limit" % [f.unit["file"], s["line"]])
					return
		"for":
			var a := int(_num(_eval(inst, f, s["from"])))
			var b := int(_num(_eval(inst, f, s["to"])))
			for i in range(a, b + 1):
				_assign(inst, f, s["var"], [], i)
				_exec_block(inst, f, s["body"])
				if f.done or inst.new_state_set:
					return
		"switch":
			var v = _eval(inst, f, s["e"])
			for c in s["cases"]:
				for cv in c[0]:
					if _equal(v, _eval(inst, f, cv)):
						_exec_block(inst, f, c[1])
						return
		"trans":
			_trans(inst, s["state"])
		"transback":
			_trans(inst, inst.prev_state)


func _trans(inst: Instance, state: String) -> void:
	if inst.unit["kind"] != "fsm" or state == "":
		return
	inst.prev_state = inst.state
	inst.state = state
	inst.new_state_set = true


func _call_stmt(inst: Instance, f: Frame, s: Dictionary) -> void:
	var name: String = s["name"]
	var target := _find_routine(f.unit, name)
	var is_order: bool = not target.is_empty() and target[1]["kind"] == "order"
	var own_code: bool = f.unit == inst.unit  # library call sites are never marked
	var site: int = s["site"]
	if is_order and own_code and inst.order_flags.has(site):
		return  # finished earlier: skip until resetOrders
	var v = _call(inst, f, name, s["args"], target)
	if is_order and f.routine["kind"] in ["state", "order"]:
		if int(_num(v)) == 0:
			# Not finished: stop this state for now, or return 0 from this order.
			f.ret = 0
			f.done = true
		elif own_code:
			inst.order_flags[site] = true


func _find_routine(u: Dictionary, name: String) -> Array:
	var r = u["routines"].get(name)
	if r != null and r["kind"] != "state":
		return [u, r]
	if _global_routines.has(name):
		return _global_routines[name]
	return []


func _call(inst: Instance, f: Frame, name: String, args: Array, target: Array = []) -> Variant:
	if target.is_empty():
		target = _find_routine(f.unit, name)
	if not target.is_empty():
		return _call_declared(inst, f, target[0], target[1], args, [])
	var std = _std(inst, f, name, args)
	if not (std is StringName and std == &"__none"):
		return std
	if natives.has(name):
		var vals := []
		for a in args:
			vals.append(_eval(inst, f, a))
		return natives[name].call(inst, vals)
	unknown[name] = unknown.get(name, 0) + 1
	for a in args:
		_eval(inst, f, a)
	return 0


func _call_declared(inst: Instance, caller: Frame, u: Dictionary, r: Dictionary, args: Array, _unused: Array) -> Variant:
	var f := Frame.new()
	f.unit = u
	f.routine = r
	f.owner = inst if u == inst.unit else _lib_inst.get(u["name"], inst)
	var params: Array = r["params"]
	for i in params.size():
		var p: Dictionary = params[i]
		var rt := resolve_type(u, p["type"])
		f.types[p["name"]] = rt
		if i >= args.size():
			f.vals[p["name"]] = default_value(rt)
			continue
		var a: Dictionary = args[i]
		if p["ref"] and a["k"] == "name" and caller != null:
			var slot = _slot(inst, caller, a["name"])
			if slot != null:
				var cur = slot[0][slot[2]]
				if cur is Ref:
					f.vals[p["name"]] = cur
				elif cur is Array:
					f.vals[p["name"]] = cur  # arrays are shared by reference
				else:
					f.vals[p["name"]] = Ref.new(slot[0], slot[2], slot[1].get(slot[2], rt))
				continue
		var v = _eval(inst, caller, a) if caller != null else 0
		if v is Array:
			f.vals[p["name"]] = v if p["ref"] else v.duplicate()
		else:
			f.vals[p["name"]] = coerce(rt["base"], v)
	for n in r["var_order"]:
		var rt := resolve_type(u, r["vars"][n]["type"])
		f.types[n] = rt
		f.vals[n] = default_value(rt)
	_exec_block(inst, f, r["body"])
	if r["ret"] != null:
		return coerce(resolve_type(u, r["ret"])["base"], f.ret)
	return f.ret


## [vals dict, types dict, key] for a variable visible from frame f, or null.
func _slot(inst: Instance, f: Frame, name: String) -> Variant:
	if f.vals.has(name):
		return [f.vals, f.types, name]
	if f.unit == inst.unit and inst.module_vals.has(name):
		return [inst.module_vals, inst.module_types, name]
	var owner: Instance = f.owner if f.owner != null else inst
	if owner.statics.has(name):
		return [owner.statics, owner.static_types, name]
	if f.unit["_eternals"].has(name):
		return [f.unit["_eternals"], f.unit["_eternal_types"], name]
	var g = _global_eternals.get(name)
	if g != null:
		return [g["_eternals"], g["_eternal_types"], name]
	for lib in _lib_inst.values():  # library statics are global too (brains set CoreRun)
		if lib.statics.has(name):
			return [lib.statics, lib.static_types, name]
	return null


func _read(inst: Instance, f: Frame, name: String) -> Variant:
	var slot = _slot(inst, f, name)
	if slot != null:
		var v = slot[0][slot[2]]
		if v is Ref:
			return v.vals[v.key]
		return v
	var c = _const_value(f.unit, name)
	if c != null:
		return c
	return _call(inst, f, name, [])  # a routine called without parentheses (getTime)


func _assign(inst: Instance, f: Frame, name: String, idx: Array, value: Variant) -> void:
	var slot = _slot(inst, f, name)
	if slot == null:
		errors.append("%s: assignment to unknown %s" % [f.unit["file"], name])
		return
	var vals = slot[0]
	var key = slot[2]
	var rt: Dictionary = slot[1].get(key, {"base": "integer", "dims": []})
	var cur = vals[key]
	if cur is Ref:
		vals = cur.vals
		key = cur.key
		rt = cur.rtype
		cur = vals[key]
	if idx.is_empty():
		if cur is Array and value is Array:
			vals[key] = value.duplicate()
		else:
			vals[key] = coerce(rt["base"], value)
		return
	if not (cur is Array):
		return  # indexing a char string: not used by the scripts
	var at := _flat_index(inst, f, rt, idx)
	if at >= 0 and at < cur.size():
		cur[at] = coerce(rt["base"], value)


func _flat_index(inst: Instance, f: Frame, rt: Dictionary, idx: Array) -> int:
	var dims: Array = rt["dims"]
	if rt["base"] == "char":
		dims = dims.slice(0, dims.size() - 1)
	var at := 0
	for k in idx.size():
		var i := int(_num(_eval(inst, f, idx[k])))
		var stride := 1
		for d in range(k + 1, dims.size()):
			stride *= int(dims[d])
		at += i * stride
	return at


func _eval(inst: Instance, f: Frame, e: Dictionary) -> Variant:
	match e["k"]:
		"num", "str":
			return e["v"]
		"name":
			return _read(inst, f, e["name"])
		"elem":
			var slot = _slot(inst, f, e["name"])
			if slot == null:
				return 0
			var arr = slot[0][slot[2]]
			var rt: Dictionary = slot[1].get(slot[2], {"base": "integer", "dims": []})
			if arr is Ref:
				rt = arr.rtype
				arr = arr.vals[arr.key]
			if not (arr is Array):
				return 0
			var at := _flat_index(inst, f, rt, e["idx"])
			return arr[at] if at >= 0 and at < arr.size() else 0
		"fcall":
			return _call(inst, f, e["name"], e["args"])
		"bin":
			return _binop(e["op"], _eval(inst, f, e["a"]), _eval(inst, f, e["b"]))
		"not":
			return not _truthy(_eval(inst, f, e["a"]))
		"neg":
			return -_num(_eval(inst, f, e["a"]))
	return 0


static func _num(v: Variant) -> Variant:
	if v is bool:
		return 1 if v else 0
	if v is int or v is float:
		return v
	return 0


static func _truthy(v: Variant) -> bool:
	if v is bool:
		return v
	if v is int or v is float:
		return v != 0
	return v != null and str(v) != ""


static func _equal(a: Variant, b: Variant) -> bool:
	if a is String or b is String:
		return str(a) == str(b)
	return _num(a) == _num(b)


static func _binop(op: String, a: Variant, b: Variant) -> Variant:
	match op:
		"and":
			return _truthy(a) and _truthy(b)
		"or":
			return _truthy(a) or _truthy(b)
		"==":
			return _equal(a, b)
		"<>":
			return not _equal(a, b)
	if a is String or b is String:
		if op == "+":
			return str(a) + str(b)
		match op:
			"<":
				return str(a) < str(b)
			">":
				return str(a) > str(b)
		return 0
	a = _num(a)
	b = _num(b)
	match op:
		"+":
			return a + b
		"-":
			return a - b
		"*":
			return a * b
		"/":
			if a is int and b is int:
				return 0 if b == 0 else a / b
			return 0.0 if float(b) == 0.0 else float(a) / float(b)
		"div":
			return 0 if int(b) == 0 else int(a) / int(b)
		"mod":
			return 0 if int(b) == 0 else int(a) % int(b)
		"<":
			return a < b
		"<=":
			return a <= b
		">":
			return a > b
		">=":
			return a >= b
	return 0


# --- standard routines ------------------------------------------------------------------

func _std(inst: Instance, f: Frame, name: String, args: Array) -> Variant:
	match name:
		"return":
			f.ret = _eval(inst, f, args[0]) if args.size() > 0 else 0
			f.done = true
			return f.ret
		"print", "mcprint":
			var parts := []
			for a in args:
				parts.append(str(_eval(inst, f, a)))
			log_lines.append(" ".join(parts))
			return 0
		"concat":
			# concat(dest, value): append to a char-array variable
			if args.size() >= 2 and args[0]["k"] == "name":
				var cur = _read(inst, f, args[0]["name"])
				_assign(inst, f, args[0]["name"], [], str(cur) + str(_eval(inst, f, args[1])))
			return 0
		"getstatehandle":
			var s := str(_eval(inst, f, args[0])).to_lower()
			return inst.unit["states"].find(s) + 1
		"getcurrentstatehandle":
			return inst.state_handle()
		"setstate":
			var h := int(_num(_eval(inst, f, args[0])))
			if h > 0 and h <= inst.unit["states"].size():
				_trans(inst, inst.unit["states"][h - 1])
			return 0
		"resetorders":
			var scope := int(_num(_eval(inst, f, args[0]))) if args.size() > 0 else 0
			if scope == 0:
				inst.order_flags.clear()
			else:
				for site in inst.order_flags.keys():
					if site >= f.routine.get("site_lo", 0) and site < f.routine.get("site_hi", 0):
						inst.order_flags.erase(site)
			return 0
		"abs":
			return absf(float(_num(_eval(inst, f, args[0]))))
		"sqrt":
			return sqrt(maxf(float(_num(_eval(inst, f, args[0]))), 0.0))
		"round":
			return int(round(float(_num(_eval(inst, f, args[0])))))
		"trunc":
			return int(float(_num(_eval(inst, f, args[0]))))
		"random":
			var n := int(_num(_eval(inst, f, args[0])))
			return rng.randi_range(0, n - 1) if n > 0 else 0
		"seedrandom", "setmaxloops", "fileclose", "filewrite", "fatal", "assert":
			for a in args:
				_eval(inst, f, a)
			return 0
		"fileopen", "getmodule", "getfunctionhandle", "callfunction":
			return 0
		"setflag":
			var flags := int(_num(_eval(inst, f, args[0])))
			var bit := int(_num(_eval(inst, f, args[1])))
			return (flags | (1 << bit)) if _truthy(_eval(inst, f, args[2])) else (flags & ~(1 << bit))
		"getflag":
			return (int(_num(_eval(inst, f, args[0]))) & (1 << int(_num(_eval(inst, f, args[1]))))) != 0
	return &"__none"
