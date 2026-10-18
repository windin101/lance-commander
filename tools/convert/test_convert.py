"""Converter tests. Run: python3 -I -m unittest discover -s tools/convert

Unit tests use inline samples; the reference tests check values read straight
from the source release and are skipped when reference/ is absent.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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

    def test_strings(self):
        s = strings_rc.load(os.path.join(SRC, "Script1.rc"), os.path.join(SRC, "resource.h"))
        self.assertIn("Fusion Engine", s[32001])
        self.assertEqual(s[28919], "ATLAS")


if __name__ == "__main__":
    unittest.main()
