class_name AblParser
extends RefCounted
## Scanner and parser for ABL, MechCommander 2's mission and pilot-brain language
## (Pascal-like: fsm / module / library units with const, type and var sections,
## function / order / state routines). Produces a plain Dictionary AST that AblRuntime
## executes. Names are case-insensitive, so identifiers are lowercased here.
##
## Unit:  {kind, name, consts: {name: expr}, types: {name: type}, vars: {name: var},
##         var_order: [names], routines: {name: routine}, states: [names], code: [stmts],
##         sites: int (order call sites, numbered per unit), file}
## Type:  {base: "integer"|"real"|"boolean"|"char"|<alias>, dims: [exprs]}
## Var:   {type, storage: "static"|"eternal"|"local"}
## Routine: {kind: "function"|"order"|"state", name, params: [{name, type, ref}],
##           ret: type or null, vars, var_order, body: [stmts], site_lo, site_hi}
## Expressions and statements are Dictionaries keyed by "k" (see _statement/_factor).

const KEYWORDS := {
	"and": true, "case": true, "code": true, "const": true, "div": true, "do": true, "else": true,
	"elsif": true, "endcase": true, "endfor": true, "endfsm": true, "endfunction": true, "endif": true,
	"endlibrary": true, "endmodule": true, "endorder": true, "endstate": true, "endswitch": true,
	"endwhile": true, "eternal": true, "for": true, "fsm": true, "function": true, "if": true,
	"library": true, "mod": true, "module": true, "not": true, "or": true, "order": true, "repeat": true,
	"state": true, "static": true, "switch": true, "then": true, "to": true, "trans": true,
	"transback": true, "type": true, "until": true, "var": true, "while": true, "ref": true,
}
const ROUTINE_END := {"function": "endfunction", "order": "endorder", "state": "endstate"}

# Token: [kind, value, line, file]; kind is "id", "kw", "num", "str", "op" or "eof".
var _toks: Array = []
var _i := 0
var _unit: Dictionary
var _routine: Dictionary = {}


static func parse_file(path: String) -> Dictionary:
	var p := AblParser.new()
	return p.parse(path)


## Returns the unit, or {"error": "file:line: message"}.
func parse(path: String) -> Dictionary:
	_toks = []
	var err := _scan_file(path, 0)
	if err != "":
		return {"error": err}
	_toks.append(["eof", "", 0, path])
	_i = 0
	_unit = {"kind": "", "name": "", "consts": {}, "types": {}, "vars": {}, "var_order": [],
		"routines": {}, "states": [], "code": [], "sites": 0, "file": path}
	var result = _unit_decl()
	if result is String:
		return {"error": result}
	return _unit


# --- scanner -----------------------------------------------------------------

static func resolve_path(dir: String, name: String) -> String:
	## Case-insensitive file lookup (the scripts' #include_ names vary in case).
	var direct := dir.path_join(name)
	if FileAccess.file_exists(direct):
		return direct
	var lower := dir.path_join(name.to_lower())
	if FileAccess.file_exists(lower):
		return lower
	var d := DirAccess.open(dir)
	if d:
		for f in d.get_files():
			if f.to_lower() == name.to_lower():
				return dir.path_join(f)
	return ""


func _scan_file(path: String, depth: int) -> String:
	if depth > 8:
		return "%s: include nesting too deep" % path
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		return "%s: cannot open" % path
	var src := f.get_buffer(f.get_length()).get_string_from_ascii()
	var n := src.length()
	var i := 0
	var line := 1
	while i < n:
		var c := src[i]
		if c == "\n":
			line += 1
			i += 1
		elif c == " " or c == "\t" or c == "\r":
			i += 1
		elif c == "/" and i + 1 < n and src[i + 1] == "/":
			while i < n and src[i] != "\n":
				i += 1
		elif c == "/" and i + 1 < n and src[i + 1] == "*":
			i += 2
			while i + 1 < n and not (src[i] == "*" and src[i + 1] == "/"):
				if src[i] == "\n":
					line += 1
				i += 1
			i += 2
		elif c == "#":
			# #include_ "file" (also #include)
			var j := i + 1
			while j < n and (_is_ident(src[j])):
				j += 1
			var directive := src.substr(i + 1, j - i - 1).to_lower()
			if not directive.begins_with("include"):
				return "%s:%d: unknown directive #%s" % [path, line, directive]
			var q1 := src.find("\"", j)
			var q2 := src.find("\"", q1 + 1)
			if q1 < 0 or q2 < 0:
				return "%s:%d: bad #include" % [path, line]
			var inc := resolve_path(path.get_base_dir(), src.substr(q1 + 1, q2 - q1 - 1))
			if inc == "":
				return "%s:%d: include not found: %s" % [path, line, src.substr(q1 + 1, q2 - q1 - 1)]
			var e := _scan_file(inc, depth + 1)
			if e != "":
				return e
			i = q2 + 1
		elif _is_ident_start(c):
			var j := i + 1
			while j < n and _is_ident(src[j]):
				j += 1
			var word := src.substr(i, j - i).to_lower()
			_toks.append(["kw" if KEYWORDS.has(word) else "id", word, line, path])
			i = j
		elif (c >= "0" and c <= "9") or (c == "." and i + 1 < n and src[i + 1] >= "0" and src[i + 1] <= "9"):
			var j := i
			var real := false
			while j < n and ((src[j] >= "0" and src[j] <= "9") or src[j] == "."):
				if src[j] == ".":
					# "1." followed by a letter or end is a number then a period (e.g. "endfsm.")
					if j + 1 >= n or not (src[j + 1] >= "0" and src[j + 1] <= "9"):
						break
					real = true
				j += 1
			if j < n and (src[j] == "e" or src[j] == "E") and j + 1 < n and (src[j + 1].is_valid_int() or src[j + 1] == "-" or src[j + 1] == "+"):
				real = true
				j += 2
				while j < n and src[j] >= "0" and src[j] <= "9":
					j += 1
			var text := src.substr(i, j - i)
			_toks.append(["num", text.to_float() if real else text.to_int(), line, path])
			i = j
		elif c == "\"":
			var j := src.find("\"", i + 1)
			if j < 0:
				return "%s:%d: unterminated string" % [path, line]
			_toks.append(["str", src.substr(i + 1, j - i - 1), line, path])
			i = j + 1
		else:
			var two := src.substr(i, 2)
			if two in ["==", "<>", "<=", ">=", "!="]:
				_toks.append(["op", "<>" if two == "!=" else two, line, path])
				i += 2
			elif c in "()[],;:.+-*/=<>@":
				_toks.append(["op", c, line, path])
				i += 1
			else:
				return "%s:%d: unexpected character '%s'" % [path, line, c]
	return ""


static func _is_ident_start(c: String) -> bool:
	return (c >= "a" and c <= "z") or (c >= "A" and c <= "Z") or c == "_"


static func _is_ident(c: String) -> bool:
	return _is_ident_start(c) or (c >= "0" and c <= "9")


# --- token helpers -------------------------------------------------------------

func _peek(o := 0) -> Array:
	return _toks[mini(_i + o, _toks.size() - 1)]


func _is(value: String, o := 0) -> bool:
	var t := _peek(o)
	return (t[0] == "kw" or t[0] == "op") and t[1] == value


func _accept(value: String) -> bool:
	if _is(value):
		_i += 1
		return true
	return false


func _err(msg: String) -> String:
	var t := _peek()
	return "%s:%d: %s (at '%s')" % [t[3], t[2], msg, str(t[1])]


func _expect(value: String):
	if _accept(value):
		return null
	return _err("expected '%s'" % value)


func _ident():
	var t := _peek()
	if t[0] != "id":
		return _err("expected a name")
	_i += 1
	return t[1]


# --- declarations ----------------------------------------------------------------

func _unit_decl():
	var t := _peek()
	if not (t[0] == "kw" and t[1] in ["fsm", "module", "library"]):
		return _err("expected fsm, module or library")
	_unit["kind"] = t[1]
	_i += 1
	var name = _ident()
	if name is String and name.contains(":"):
		return name
	_unit["name"] = name
	if _accept(":"):
		var rt = _type_spec()
		if rt is String:
			return rt
	_accept(";")
	var r = _sections(_unit, true)
	if r is String:
		return r
	while true:
		var k := _peek()
		if k[0] == "kw" and k[1] in ["function", "order", "state"]:
			r = _routine_decl()
			if r is String:
				return r
		elif _accept("code"):
			_routine = {"kind": "module", "site_lo": _unit["sites"]}
			var body = _statements(["end" + _unit["kind"]])
			if body is String:
				return body
			_unit["code"] = body
		elif _is("end" + _unit["kind"]):
			_i += 1
			_accept(".")
			return null
		elif k[0] == "eof":
			return _err("missing end%s" % _unit["kind"])
		elif _accept(";"):
			pass
		else:
			r = _sections(_unit, true)
			if r is String:
				return r
			if _peek() == k:
				return _err("unexpected token")
	return null


## const / type / var sections (repeatable, any order). Unit-level sections may
## declare static and eternal variables; plain ones are per-execution locals.
func _sections(owner: Dictionary, unit_level: bool):
	while true:
		if _accept("const"):
			while _peek()[0] == "id" and _is("=", 1):
				var n: String = _peek()[1]
				_i += 2
				var e = _expr()
				if e is String:
					return e
				_unit["consts"][n] = e
				var r = _expect(";")
				if r is String:
					return r
		elif _accept("type"):
			while _peek()[0] == "id" and _is("=", 1):
				var n: String = _peek()[1]
				_i += 2
				var ty = _type_spec()
				if ty is String:
					return ty
				_unit["types"][n] = ty
				var r = _expect(";")
				if r is String:
					return r
		elif _accept("var"):
			while _peek()[0] == "id" or _is("static") or _is("eternal"):
				var storage := "local"
				if _accept("static"):
					storage = "static"
				elif _accept("eternal"):
					storage = "eternal"
				# Routine-level static/eternal vars persist like unit-level ones: hoist them.
				var into: Dictionary = owner if (unit_level or storage == "local") else _unit
				var ty = _type_spec()
				if ty is String:
					return ty
				while true:
					var n = _ident()
					if n is String and n.contains(":"):
						return n
					into["vars"][n] = {"type": ty, "storage": storage}
					into["var_order"].append(n)
					if not _accept(","):
						break
				var r = _expect(";")
				if r is String:
					return r
		else:
			return null
	return null


func _type_spec():
	var base = _ident()
	if base is String and base.contains(":"):
		return base
	var dims := []
	if _accept("["):
		while true:
			var e = _expr()
			if e is String:
				return e
			dims.append(e)
			if not _accept(","):
				break
		var r = _expect("]")
		if r is String:
			return r
	return {"base": base, "dims": dims}


func _routine_decl():
	var kind: String = _peek()[1]
	_i += 1
	var name = _ident()
	if name is String and name.contains(":"):
		return name
	var rt := {"kind": kind, "name": name, "params": [], "ret": null, "vars": {}, "var_order": [],
		"body": [], "site_lo": _unit["sites"], "site_hi": _unit["sites"], "line": _peek()[2]}
	if _accept("("):
		while not _is(")"):
			var is_ref := _accept("@") or _accept("ref")
			var ty = _type_spec()
			if ty is String:
				return ty
			var pn = _ident()
			if pn is String and pn.contains(":"):
				return pn
			rt["params"].append({"name": pn, "type": ty, "ref": is_ref})
			if not _accept(","):
				break
		var r = _expect(")")
		if r is String:
			return r
	if _accept(":"):
		var ty = _type_spec()
		if ty is String:
			return ty
		rt["ret"] = ty
	_accept(";")
	var r2 = _sections(rt, false)
	if r2 is String:
		return r2
	var r3 = _expect("code")
	if r3 is String:
		return r3
	_routine = rt
	var body = _statements([ROUTINE_END[kind]])
	if body is String:
		return body
	_i += 1  # the end keyword
	_accept(";")
	rt["body"] = body
	rt["site_hi"] = _unit["sites"]
	_unit["routines"][name] = rt
	if kind == "state":
		_unit["states"].append(name)
	return null


# --- statements --------------------------------------------------------------------

func _statements(ends: Array):
	var out := []
	while true:
		var t := _peek()
		if t[0] == "eof":
			return _err("unexpected end of file")
		if t[0] == "kw" and t[1] in ends:
			return out
		if _accept(";"):
			continue
		var s = _statement()
		if s is String:
			return s
		out.append(s)
	return out


func _statement():
	var t := _peek()
	var line: int = t[2]
	if t[0] == "id":
		_i += 1
		var name: String = t[1]
		if _is("=") or _is("["):
			var idx := []
			if _accept("["):
				var r = _index_list(idx)
				if r is String:
					return r
				while _accept("["):
					r = _index_list(idx)
					if r is String:
						return r
			var r2 = _expect("=")
			if r2 is String:
				return r2
			var e = _expr()
			if e is String:
				return e
			return {"k": "assign", "name": name, "idx": idx, "e": e, "line": line}
		var args := []
		if _accept("("):
			var r = _arg_list(args)
			if r is String:
				return r
		var site: int = _unit["sites"]
		_unit["sites"] += 1
		return {"k": "call", "name": name, "args": args, "site": site, "line": line}
	if t[0] != "kw":
		return _err("expected a statement")
	_i += 1
	match t[1]:
		"if":
			var arms := []
			var c = _expr()
			if c is String:
				return c
			var r = _expect("then")
			if r is String:
				return r
			var body = _statements(["elsif", "else", "endif"])
			if body is String:
				return body
			arms.append([c, body])
			var els := []
			while true:
				if _accept("elsif"):
					c = _expr()
					if c is String:
						return c
					r = _expect("then")
					if r is String:
						return r
					body = _statements(["elsif", "else", "endif"])
					if body is String:
						return body
					arms.append([c, body])
				elif _accept("else"):
					var eb = _statements(["endif"])
					if eb is String:
						return eb
					els = eb
				else:
					break
			r = _expect("endif")
			if r is String:
				return r
			return {"k": "if", "arms": arms, "else": els, "line": line}
		"while":
			var c = _expr()
			if c is String:
				return c
			var r = _expect("do")
			if r is String:
				return r
			var body = _statements(["endwhile"])
			if body is String:
				return body
			_i += 1
			return {"k": "while", "c": c, "body": body, "line": line}
		"repeat":
			var body = _statements(["until"])
			if body is String:
				return body
			_i += 1
			var c = _expr()
			if c is String:
				return c
			return {"k": "repeat", "c": c, "body": body, "line": line}
		"for":
			var v = _ident()
			if v is String and v.contains(":"):
				return v
			var r = _expect("=")
			if r is String:
				return r
			var a = _expr()
			if a is String:
				return a
			r = _expect("to")
			if r is String:
				return r
			var b = _expr()
			if b is String:
				return b
			r = _expect("do")
			if r is String:
				return r
			var body = _statements(["endfor"])
			if body is String:
				return body
			_i += 1
			return {"k": "for", "var": v, "from": a, "to": b, "body": body, "line": line}
		"switch":
			var e = _expr()
			if e is String:
				return e
			var cases := []
			while not _is("endswitch"):
				if _accept(";"):
					continue
				var r = _expect("case")
				if r is String:
					return r
				var vals := []
				while true:
					var v = _expr()
					if v is String:
						return v
					vals.append(v)
					if not _accept(","):
						break
				r = _expect(":")
				if r is String:
					return r
				var body = _statements(["endcase"])
				if body is String:
					return body
				_i += 1
				cases.append([vals, body])
			_i += 1
			return {"k": "switch", "e": e, "cases": cases, "line": line}
		"trans":
			var n = _ident()
			if n is String and n.contains(":"):
				return n
			return {"k": "trans", "state": n, "line": line}
		"transback":
			return {"k": "transback", "line": line}
	_i -= 1
	return _err("unexpected keyword")


func _index_list(idx: Array):
	while true:
		var e = _expr()
		if e is String:
			return e
		idx.append(e)
		if not _accept(","):
			break
	return _expect("]")


func _arg_list(args: Array):
	while not _is(")"):
		var e = _expr()
		if e is String:
			return e
		args.append(e)
		if not _accept(","):
			break
	return _expect(")")


# --- expressions (Pascal precedence: relational < additive/or < multiplicative/and) -----

func _expr():
	var a = _simple()
	if a is String:
		return a
	for op in ["==", "<>", "<", "<=", ">", ">="]:
		if _is(op):
			_i += 1
			var b = _simple()
			if b is String:
				return b
			return {"k": "bin", "op": op, "a": a, "b": b}
	return a


func _simple():
	var neg := false
	if _accept("-"):
		neg = true
	else:
		_accept("+")
	var a = _term()
	if a is String:
		return a
	if neg:
		a = {"k": "neg", "a": a} if not (a["k"] == "num") else {"k": "num", "v": -a["v"]}
	while _is("+") or _is("-") or _is("or"):
		var op: String = _peek()[1]
		_i += 1
		var b = _term()
		if b is String:
			return b
		a = {"k": "bin", "op": op, "a": a, "b": b}
	return a


func _term():
	var a = _factor()
	if a is String:
		return a
	while _is("*") or _is("/") or _is("div") or _is("mod") or _is("and"):
		var op: String = _peek()[1]
		_i += 1
		var b = _factor()
		if b is String:
			return b
		a = {"k": "bin", "op": op, "a": a, "b": b}
	return a


func _factor():
	var t := _peek()
	match t[0]:
		"num":
			_i += 1
			return {"k": "num", "v": t[1]}
		"str":
			_i += 1
			return {"k": "str", "v": t[1]}
		"id":
			_i += 1
			if _accept("("):
				var args := []
				var r = _arg_list(args)
				if r is String:
					return r
				return {"k": "fcall", "name": t[1], "args": args, "line": t[2]}
			if _is("["):
				var idx := []
				while _accept("["):
					var r = _index_list(idx)
					if r is String:
						return r
				return {"k": "elem", "name": t[1], "idx": idx}
			return {"k": "name", "name": t[1], "line": t[2]}
	if _accept("not"):
		var a = _factor()
		if a is String:
			return a
		return {"k": "not", "a": a}
	if _accept("("):
		var e = _expr()
		if e is String:
			return e
		var r = _expect(")")
		if r is String:
			return r
		return e
	if _accept("-"):
		var a = _factor()
		if a is String:
			return a
		return {"k": "neg", "a": a}
	return _err("expected an expression")
