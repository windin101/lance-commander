#!/usr/bin/env python3
"""Build the fidelity probe: a copy of game/tools/autoplay.gd with variant hooks.

usage: python3 make_variant.py <repo>/game/tools/autoplay.gd <out.gd>
Then: godot --headless --path game -s <out.gd> -- <seed> 1800 --mission=<m> --damage [--v-nodes] [--v-heatoff]
--v-nodes   original vehicle weapon-node rule: Partisan and Legion fire weapon 1 and 2 once each, then never
--v-heatoff SimRules.heat_enabled = false (the original has no heat)
Prints FID lines: shots, hits and hit rate per side and unit kind.
"""
import sys
src = open(sys.argv[1]).read()
a = "\tvar sm := SimMission.load_mission(data, mission, seed_value, true, force)\n"
b = "\t\tprint(\"enemy pilots that moved >20 m: %d / %d\" % [moved, sm.abl.pilots.size()])\n"
c = "\t\t\t\t\"shot\":  # --shots=N"
for k in (a, b, c):
    assert k in src, k
src = src.replace(a, a + "\t_fid_setup(sm, args)\n", 1)
src = src.replace(b, b + "\t_fid_report(sm)\n", 1)
src = src.replace(c, "\t\t\t\t\"shot\" when _fid_shot(w, e) and false:\n\t\t\t\t\tpass\n" + c, 1)
src += "\n\n" + '# --- fidelity probe (scratchpad copy only) ------------------------------------------------\nvar _fid_nodes := false\nvar _fid_stats := {}  # key -> [shots, hits]\nvar _fid_node_units := {}  # unit id -> shots left\nvar _fid_dmg_t := {}  # "lance_taken"/"lance_dealt" by 60 s bucket\n\nfunc _fid_setup(sm: SimMission, args: PackedStringArray) -> void:\n\tvar w := sm.world\n\tif "--v-heatoff" in args:\n\t\tw.rules.heat_enabled = false\n\t\tprint("VARIANT heat off")\n\tif "--v-nodes" in args:\n\t\t_fid_nodes = true\n\t\tprint("VARIANT original weapon-node rule: Partisan and Legion fire weapon_01/02 once each, then never")\n\t\tfor u in w.units:\n\t\t\tif u is SimVehicle and u.model in ["partisan", "legion"]:\n\t\t\t\tvar ws := u.weapon_indices()\n\t\t\t\tfor i in ws.size():\n\t\t\t\t\tif i >= 2:\n\t\t\t\t\t\tu.items[ws[i]]["ready_time"] = INF\n\t\t\t\t_fid_node_units[u.id] = true\n\nfunc _fid_key(u: SimUnit) -> String:\n\tvar side := "lance" if (u.team == 0 and u.commander == 0) else ("ally" if u.team == 0 else "enemy")\n\treturn "%s_%s" % [side, "mech" if u is SimMech else "vehicle"]\n\nfunc _fid_shot(w: SimWorld, e: Dictionary) -> bool:\n\tvar a: SimUnit = w.units[e["from"]]\n\tvar b: SimUnit = w.units[e["to"]]\n\tvar k := _fid_key(a) + "->" + _fid_key(b)\n\tvar s: Array = _fid_stats.get(k, [0, 0])\n\ts[0] += 1\n\tif e["hit"]:\n\t\ts[1] += 1\n\t_fid_stats[k] = s\n\tif a.team == 0 and a.commander == 0 and a.uses_heat:\n\t\tvar hk := "lance_heat_level_sum"\n\t\t_fid_stats[hk] = [_fid_stats.get(hk, [0, 0])[0] + a.heat_level(), _fid_stats.get(hk, [0, 0])[1] + 1]\n\tif _fid_nodes and _fid_node_units.has(a.id):\n\t\ta.items[int(e["weapon"])]["ready_time"] = INF\n\treturn false\n\nfunc _fid_report(sm: SimMission) -> void:\n\tvar keys := _fid_stats.keys()\n\tkeys.sort()\n\tfor k in keys:\n\t\tvar s: Array = _fid_stats[k]\n\t\tif k == "lance_heat_level_sum":\n\t\t\tprint("FID mean lance heat level at fire: %.1f over %d shots" % [float(s[0]) / maxf(s[1], 1), s[1]])\n\t\telse:\n\t\t\tprint("FID %-32s shots %5d hits %5d rate %.2f" % [k, s[0], s[1], float(s[1]) / maxf(s[0], 1)])\n'
open(sys.argv[2], "w").write(src)
