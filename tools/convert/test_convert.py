"""Converter tests. Run: python3 -I -m unittest discover -s tools/convert

Unit tests use inline samples; the reference tests check values read straight
from the source release and are skipped when reference/ is absent.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audio  # noqa: E402
import chassis  # noqa: E402
import components  # noqa: E402
import convert_all  # noqa: E402
import fit  # noqa: E402
import strings_rc  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "reference", "mc2-source", "Source")
HAVE_REF = os.path.isdir(SRC)


class FitTests(unittest.TestCase):
    def test_types_and_comments(self):
        b = fit.parse_text(
            'FITini\n[General]\nf Range = 45 //70  // comment\n'
            'st Name = "a // not a comment"\nb Ready = TRUE\nul Neg = -1358954496\n'
            'uc Small = 7\nFITend\n'
        )["General"]
        self.assertEqual(b["Range"], 45.0)
        self.assertEqual(b["Name"], "a // not a comment")
        self.assertIs(b["Ready"], True)
        self.assertIs(fit.parse_text("[A]\nb HoverCraft = t\n")["A"]["HoverCraft"], True)
        self.assertEqual(b["Neg"], -1358954496)
        self.assertEqual(b["Small"], 7)

    def test_arrays_span_lines_and_trailing_comma(self):
        b = fit.parse_text(
            "[A]\nf[3] LOD = 1.00, 0.50, 0.30,\nl[4] T =\n  1,2,\n  3,4\nl After = 9\n"
        )["A"]
        self.assertEqual(b["LOD"], [1.0, 0.5, 0.3])
        self.assertEqual(b["T"], [1, 2, 3, 4])
        self.assertEqual(b["After"], 9)

    def test_array_with_first_value_on_same_line_then_more(self):
        b = fit.parse_text("[W]\nuc[2] WeaponTypes =\t10,\n\t\t15\n[Next]\n")["W"]
        self.assertEqual(b["WeaponTypes"], [10, 15])


class StringTests(unittest.TestCase):
    def test_entry_on_next_line_and_doubled_quotes(self):
        ids = strings_rc.parse_defines("#define IDS_A 10\n#define IDS_B 11\n")
        out = strings_rc.parse_stringtables(
            'STRINGTABLE DISCARDABLE\nBEGIN\n  IDS_A "say ""hi""\\nnow"\n  IDS_B\n'
            '      "wrapped"\nEND\n', ids)
        self.assertEqual(out[10], 'say "hi"\nnow')
        self.assertEqual(out[11], "wrapped")


class ComponentTests(unittest.TestCase):
    def test_removed_and_undefined_rows_are_skipped(self):
        self.assertIsNone(components.parse_row("2,Removed,XL Fusion Engine,12".split(",")))
        self.assertIsNone(components.parse_row("0,undefined,undefined,0".split(",")))


class MechModelMathTests(unittest.TestCase):
    def test_max_angle_axis_matches_node_tm_convention(self):
        import mech_model
        # BushwackerWalk.ase joint_root: TM rows show +10 deg about +Z for axis (0,0,-1), 0.1745 rad.
        q = mech_model.max_angle_axis(0.0, 0.0, -1.0, 0.1745)
        rows = [[0.9848, 0.1736, 0.0], [-0.1736, 0.9848, 0.0], [0.0, 0.0, 1.0], [0.0, 0.0, 25.0]]
        q2 = mech_model.mat_to_quat(rows)
        for a, b in zip(q, q2):
            self.assertAlmostEqual(a, b, places=3)

    def test_axis_swap_is_a_rotation(self):
        import mech_model
        self.assertEqual(mech_model.dir_gl([0, 0, 1]), [0, 1, 0])  # Max up -> glTF up
        self.assertEqual(mech_model.dir_gl([0, 1, 0]), [0, 0, -1])

    def test_tga_to_png_roundtrip_header(self):
        import mech_model
        tga = bytes([0, 0, 2]) + bytes(9) + struct_pack_wh(2, 1) + bytes([24, 0]) + bytes([0, 0, 255, 0, 255, 0])
        png = mech_model.tga_to_png(tga)
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")


def struct_pack_wh(w, h):
    import struct
    return struct.pack("<HH", w, h)


@unittest.skipUnless(HAVE_REF, "reference/ not cloned")
class ReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.comps = components.load(os.path.join(SRC, "Data", "Objects", "compbas.csv"))
        cls.by_id = {c["id"]: c for c in cls.comps}
        cls.atlas = chassis.load(os.path.join(SRC, "Data", "Objects", "atlas.csv"), cls.by_id)

    def test_component_known_rows(self):
        self.assertEqual(self.by_id[1]["form"], "Engine")
        self.assertEqual(self.by_id[1]["locations"]["ctorso"], 6)
        self.assertEqual(self.by_id[13]["sensor"]["range_factor"], 1.0)
        # ER Laser, as listed in atlas.csv item 22: medium range, heat 5
        er = self.by_id[143]
        self.assertEqual(er["weapon"]["range"], "medium")
        self.assertEqual(er["weapon"]["heat"], 5)

    def test_atlas_chassis(self):
        a = self.atlas
        self.assertEqual(a["name"], "Atlas")
        self.assertEqual(a["tonnage"], 100)
        self.assertEqual(a["max_run_speed"], 15)
        self.assertEqual(a["heat_index"], 43)
        self.assertEqual(a["max_internal"],
                         {"head": 3, "ctorso": 31, "ltorso": 21, "rtorso": 21,
                          "larm": 17, "rarm": 17, "lleg": 21, "rleg": 21})
        self.assertEqual(a["base_armor"]["rctorso"], 4)

    def test_atlas_prime_variant(self):
        v = self.atlas["variants"][0]
        self.assertEqual(v["name"], "Atlas Prime")
        self.assertEqual(v["items"][22], 143)  # ER Laser, left arm
        self.assertIsNone(v["items"][13])  # EMPTY! (255)
        self.assertEqual(v["crit_slots"]["head"], [6, 7, 12, None, None, None])
        self.assertEqual(v["crit_slots"]["larm"][4], 22)
        self.assertGreater(v["armor_plates"], 0)
        self.assertEqual(self.atlas["variants"][1]["name"], "Claymore's Atlas")
        self.assertTrue(self.atlas["variants"][1]["hidden"])

    def test_gamesys_tables(self):
        g = fit.parse_file(os.path.join(SRC, "Data", "Missions", "gamesys.fit"))
        self.assertEqual(g["General"]["WeaponRange"], [60.0, 140.0, 200.0])
        self.assertEqual(len(g["General"]["VisualRangeTable"]), 256)
        self.assertEqual(g["DifficultySettings"]["EnemySkills"], [50, 100, 125, 150])
        # Declared c[131]; the reader stops at the declared count (Inifile.cpp)
        self.assertEqual(len(g["Mech:FireWeapon"]["HitLocationTable"]), 131)
        padded = convert_all.gamesys(os.path.join(SRC, "Data", "Missions", "gamesys.fit"))
        self.assertEqual(len(padded["Mech:FireWeapon"]["HitLocationTable"]), 132)

    def test_mc2_01_terrain_and_cells(self):
        import terrain
        mfit = fit.parse_file(os.path.join(SRC, "Data", "Missions", "mc2_01.fit"))
        meta, cells, tac = terrain.convert(os.path.join(SRC, "Data", "Missions", "mc2_01.pak"), mfit)
        self.assertEqual(meta["vertices_per_side"], 100)
        self.assertEqual(meta["cells_per_side"], 300)
        self.assertEqual(len(cells), 300 * 300 * 4)
        self.assertEqual(meta["water_elevation"], 350.0)
        self.assertEqual(tac[:3], bytes([0, 0, 2]))  # uncompressed true-colour TGA header
        # Vertices flagged as water (bit 0) lie below the waterline.
        wet = [e for e, w in zip(meta["elevation"], meta["water"]) if w & 1]
        self.assertGreater(len(wet), 1000)
        self.assertTrue(all(e < 350.0 for e in wet))

    def test_bushwacker_model(self):
        import json as _json
        import struct
        import tempfile
        import mech_model
        tgl = os.path.join(SRC, "Data", "TGL")
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "bw.glb")
            rep = mech_model.build(tgl, "Bushwacker", out, os.path.join(tgl, "128", "BushwackerRGB.tga"))
            data = open(out, "rb").read()
        magic, version, length = struct.unpack_from("<III", data, 0)
        self.assertEqual((magic, version, length), (0x46546C67, 2, len(data)))
        jlen = struct.unpack_from("<I", data, 12)[0]
        gltf = _json.loads(data[20:20 + jlen])
        names = [n["name"] for n in gltf["nodes"]]
        self.assertIn("joint_root", names)
        self.assertNotIn("Spotlight_BW", [m["name"] for m in gltf["meshes"]])
        self.assertEqual(rep["meshes"], 13)
        self.assertEqual(rep["animations"]["Walk"], 1.0)

    def test_walk_cycle_loops(self):
        import mech_model
        tracks, duration = mech_model.read_animation(os.path.join(SRC, "Data", "TGL", "BushwackerWalk.ase"))
        root = tracks["joint_root"]["t"]
        for a, b in zip(root[0][1], root[-1][1]):
            self.assertAlmostEqual(a, b, places=2)
        for node, tr in tracks.items():
            if "r" in tr:
                q0, q1 = tr["r"][0][1], tr["r"][-1][1]
                dot = abs(sum(x * y for x, y in zip(q0, q1)))
                self.assertGreater(dot, 0.995, node)

    def test_strings(self):
        s = strings_rc.load(os.path.join(SRC, "Script1.rc"), os.path.join(SRC, "resource.h"))
        self.assertIn("Fusion Engine", s[32001])
        self.assertEqual(s[28919], "ATLAS")


class AudioEffectIdTests(unittest.TestCase):
    def test_effect_id_is_row_index_not_first_cell(self):
        rows = [
            ["3", "PP2K Effect Name", "Flash", "Hit", "Object Number", "Miss", "Weapon Name"],
            ["3", "NONE", "NONE", "NONE", "0", "NONE", "No Weapon Here"],
            ["1", "a", "b", "c", "461", "d", "Medium ER Clan Laser"],
            ["2", "a", "b", "c", "462", "d", "Large ER Clan Laser"],
            ["3", "flamer_trail", "b", "c", "188", "d", "Flamer"],
        ]
        self.assertEqual(audio.effect_objects(rows), {0: 0, 1: 461, 2: 462, 3: 188})


@unittest.skipUnless(HAVE_REF, "reference/ not cloned")
class WeaponFireSoundReferenceTests(unittest.TestCase):
    def test_every_weapon_resolves_its_own_fire_sound(self):
        data = os.path.join(SRC, "Data")
        comps = components.load(os.path.join(data, "Objects", "compbas.csv"))
        sound = os.path.join(data, "Sound")
        idx = audio._index([os.path.join(sound, "SoundFX"), sound])
        sound_list = [l.strip() for l in open(os.path.join(sound, "Sound.rsp"), encoding="cp1252")]
        got = {cid: os.path.basename(p).lower() for cid, p in
               audio.weapon_fire_sounds(data, comps, sound_list, idx).items()}
        names = {c["id"]: c["name"] for c in comps}
        by_name = {names[cid]: f for cid, f in got.items()}
        self.assertEqual(by_name["Flamer Array"], "sfx_flamer_fire.wav")
        self.assertEqual(by_name["Laser"], "sfx_lazer_fire(rate).wav")
        self.assertEqual(by_name["MG Array"], "sfx_mgun_fire.wav")
        self.assertEqual(by_name["Thunderbolt Missile"], "sfx_thunderbolt_fire.wav")
        self.assertEqual(by_name["Swarm LRM5 Rack"], "sfx_lrm_salvo.wav")
        # Light Gauss's bolt FIT says FiringSoundFX 0 (<NULL>) in the original data: silent.
        self.assertNotIn("Light Gauss Rifle", by_name)
        weapons = [c for c in comps if c.get("weapon")]
        self.assertEqual(len(got), len(weapons) - 1)


@unittest.skipUnless(HAVE_REF, "reference/ not cloned")
class PilotRadioReferenceTests(unittest.TestCase):
    def test_radio_table_and_voice_packets(self):
        sound = os.path.join(SRC, "Data", "Sound")
        msgs = audio.radio_messages(sound)
        self.assertEqual(len(msgs), 31)  # RadioMessageType RADIO_ACK .. RADIO_ARMORHOLE (dradio.h)
        by = {m["name"]: m for m in msgs}
        self.assertEqual(by["RADIO_UNDER_ATTACK"]["map"], 19)
        self.assertEqual(by["RADIO_UNDER_ATTACK"]["priority"], 1)
        self.assertTrue(by["RADIO_UNDER_ATTACK"]["pilot_id"])
        self.assertEqual(by["RADIO_EJECTING"]["priority"], 0)
        self.assertEqual(by["RADIO_ACK"]["chances"], [33, 33, 34])
        for n in range(1, 27):
            lines = audio.pilot_voice_files(sound, n)
            self.assertEqual(len(lines), 42)
            self.assertEqual(lines[19][0], "underattacka")  # packet = mapping + style
            self.assertEqual(lines[37][0], "callsigna")
        # a voice that spells the salvage stem differently on disk is still found
        self.assertIsNotNone(audio.pilot_voice_files(sound, 26)[14][1])
        # and one that never recorded it has no file (the original never plays RADIO_MECH_SALVAGE)
        self.assertIsNone(audio.pilot_voice_files(sound, 2)[14][1])


if __name__ == "__main__":
    unittest.main()
