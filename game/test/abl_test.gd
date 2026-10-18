extends GdUnitTestSuite
## ABL interpreter: every campaign script parses, and the execution rules the 2001
## scripts depend on (FSM transitions, order completion, storage classes, arithmetic).

const TMP := "user://abl_test"


func _write(name: String, src: String) -> String:
	DirAccess.make_dir_recursive_absolute(TMP)
	var path := TMP.path_join(name)
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_string(src)
	f.close()
	return path


func _runtime() -> AblRuntime:
	var rt := AblRuntime.new("res://data/abl", 1)
	return rt


func test_libraries_load() -> void:
	var rt := _runtime()
	assert_array(rt.errors).is_empty()
	assert_int(rt._libs.size()).is_equal(3)
	assert_int(int(rt._const_value(rt._libs[2], "pilot_event_targeted"))).is_equal(0)


func test_every_campaign_script_parses() -> void:
	var failures: Array[String] = []
	var count := 0
	for dir in ["res://data/abl", "res://data/abl/warriors"]:
		for f in DirAccess.get_files_at(dir):
			if not (f.ends_with(".abl") or f.ends_with(".abx")):
				continue
			count += 1
			var u := AblParser.parse_file(dir.path_join(f))
			if u.has("error"):
				failures.append(u["error"])
	assert_int(count).is_greater(630)
	assert_array(failures.slice(0, 10)).is_empty()


func test_every_campaign_brain_instantiates() -> void:
	var rt := _runtime()
	for f in DirAccess.get_files_at("res://data/abl/warriors"):
		if f.ends_with(".abl"):
			assert_object(rt.instantiate("warriors/" + f)).is_not_null()
	assert_array(rt.errors.slice(0, 10)).is_empty()


func test_arithmetic_follows_abl_rules() -> void:
	var path := _write("arith.abl", """
module arith : integer;
	var
		static integer i;
		static real r;
		static boolean b;
		static integer[2, 3] grid;
	code
		i = 7 / 2;
		r = 7.0 / 2;
		b = (i == 3) and (r == 3.5);
		grid[1, 2] = 5;
		i = i + grid[1, 2] + (10 div 0) + (10 mod 4);
		return(i);
endmodule.
""")
	var rt := _runtime()
	var inst := rt.instantiate(path)
	assert_int(int(inst.execute())).is_equal(3 + 5 + 0 + 2)
	assert_bool(inst.statics["b"]).is_true()
	assert_float(inst.statics["r"]).is_equal(3.5)
	assert_int(inst.statics["grid"][5]).is_equal(5)


func test_trans_inside_a_function_aborts_and_runs_the_new_state_now() -> void:
	var path := _write("fsm.abl", """
fsm tfsm;
	var
		static integer log;
function bail;
	code
		trans second;
		log = log + 1000;
endfunction;
state second;
	code
		log = log + 10;
endstate;
state start;
	code
		log = log + 1;
		bail;
		log = log + 100;
endstate;
endfsm.
""")
	var inst := _runtime().instantiate(path)
	inst.execute()
	assert_int(inst.statics["log"]).is_equal(11)
	assert_str(inst.state).is_equal("second")
	assert_str(inst.prev_state).is_equal("start")


func test_orders_block_until_done_then_are_skipped_until_reset() -> void:
	var path := _write("orders.abl", """
fsm torders;
	var
		static integer calls;
		static integer after;
		static integer ready;
order step : integer;
	code
		calls = calls + 1;
		return(ready);
endorder;
state start;
	code
		step;
		after = after + 1;
		if (after == 2) then
			resetOrders(0);
		endif;
endstate;
endfsm.
""")
	var inst := _runtime().instantiate(path)
	inst.execute()  # step returns 0: the state stops before "after"
	assert_int(inst.statics["calls"]).is_equal(1)
	assert_int(inst.statics["after"]).is_equal(0)
	inst.statics["ready"] = 1
	inst.execute()  # done: marked, the state continues
	inst.execute()  # skipped, the state continues and resets the orders
	assert_int(inst.statics["calls"]).is_equal(2)
	assert_int(inst.statics["after"]).is_equal(2)
	inst.execute()  # after the reset, step runs again
	assert_int(inst.statics["calls"]).is_equal(3)


func test_statics_are_per_instance_and_eternals_per_file() -> void:
	var path := _write("share.abl", """
fsm tshare;
	var
		static integer mine;
		eternal integer shared;
state start;
	code
		mine = mine + 1;
		shared = shared + 1;
endstate;
endfsm.
""")
	var rt := _runtime()
	var a := rt.instantiate(path)
	var b := rt.instantiate(path)
	a.execute()
	b.execute()
	assert_int(a.statics["mine"]).is_equal(1)
	assert_int(a.unit["_eternals"]["shared"]).is_equal(2)


func test_ref_params_and_library_types() -> void:
	var path := _write("refs.abl", """
fsm trefs;
	var
		static WorldPosition pos;
		static integer counter;
function bump (@integer n, real[3] copy, @WorldPosition p);
	code
		n = n + 1;
		copy[0] = 99.0;
		p[1] = 4.5;
endfunction;
state start;
	code
		bump(counter, pos, pos);
endstate;
endfsm.
""")
	var inst := _runtime().instantiate(path)
	inst.execute()
	assert_int(inst.statics["counter"]).is_equal(1)
	assert_float(inst.statics["pos"][0]).is_equal(0.0)  # value array param is a copy
	assert_float(inst.statics["pos"][1]).is_equal(4.5)  # @ array param is shared


func test_natives_receive_arrays_by_reference_and_unknowns_are_counted() -> void:
	var path := _write("natives.abl", """
fsm tnat;
	var
		static real[3] here;
		static real t;
state start;
	code
		getObjectPosition(-1, here);
		t = getTime;
		frobnicate(1);
endstate;
endfsm.
""")
	var rt := _runtime()
	rt.register_native("getObjectPosition", func(_i, args): args[1][0] = 12.5; return 0)
	rt.register_native("getTime", func(_i, _args): return 42.0)
	var inst := rt.instantiate(path)
	inst.execute()
	assert_float(inst.statics["here"][0]).is_equal(12.5)
	assert_float(inst.statics["t"]).is_equal(42.0)
	assert_int(rt.unknown.get("frobnicate", 0)).is_equal(1)


func test_brains_see_the_mission_scripts_eternals() -> void:
	var mission := _write("tmission.abl", """
module tmission : integer;
	var
		eternal boolean alarm;
	code
		alarm = true;
endmodule.
""")
	var brain := _write("tbrain.abl", """
fsm tbrain;
	var
		static integer heard;
state start;
	code
		if (alarm) then
			heard = 1;
		endif;
endstate;
endfsm.
""")
	var rt := _runtime()
	var m := rt.instantiate(mission)
	var b := rt.instantiate(brain)
	m.execute()
	b.execute()
	assert_int(b.statics["heard"]).is_equal(1)
	assert_dict(rt.unknown).is_empty()


func test_brains_can_set_library_statics() -> void:
	var brain := _write("tcorerun.abl", """
fsm tcorerun;
state start;
	code
		CoreRun = true;
endstate;
endfsm.
""")
	var rt := _runtime()
	rt.instantiate(brain).execute()
	assert_array(rt.errors).is_empty()
	assert_bool(rt._lib_inst["corebrain"].statics["corerun"]).is_true()
