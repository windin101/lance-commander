"""Tests for hd_rig helpers. Run: python3 -I -m unittest discover -s tools/art"""

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hd_rig  # noqa: E402


class HdRigTests(unittest.TestCase):
    def test_umeyama_recovers_similarity(self):
        rng = np.random.default_rng(0)
        src = rng.normal(size=(200, 3))
        r = hd_rig.yaw(37.0)
        dst = 2.5 * src @ r.T + np.array([1.0, -2.0, 0.5])
        rr, s, t = hd_rig.umeyama(src, dst)
        self.assertAlmostEqual(s, 2.5, places=6)
        np.testing.assert_allclose(rr, r, atol=1e-6)
        np.testing.assert_allclose(t, [1.0, -2.0, 0.5], atol=1e-6)

    def test_rigid_icp_keeps_scale(self):
        rng = np.random.default_rng(1)
        p = rng.normal(size=(500, 3))
        q = p @ hd_rig.yaw(8.0).T + 0.2
        fitted, (_, s, _) = hd_rig.icp(q, p, iters=40)
        self.assertEqual(s, 1.0)
        self.assertLess(np.linalg.norm(fitted - p, axis=1).mean(), 0.05)

    def test_purify_snaps_blurred_paint_to_pure_channels(self):
        arr = np.array([[[39, 39, 114], [100, 100, 110], [0, 0, 200], [150, 20, 30]]], dtype=np.uint8)
        out = hd_rig.purify(arr)
        self.assertEqual(out[0, 0].tolist(), [0, 0, 114])     # blue mixed with dark detail -> pure blue
        self.assertEqual(out[0, 1].tolist(), [100, 100, 110])  # grey stays grey
        self.assertEqual(out[0, 2].tolist(), [0, 0, 200])
        self.assertEqual(out[0, 3].tolist(), [150, 0, 0])

    def test_smooth_owners_fixes_isolated_vertex(self):
        # a fan of triangles around vertex 0; all neighbours belong to part 5, vertex 0 to part 9
        tris = np.array([[0, i, i + 1] for i in range(1, 6)] + [[0, 6, 1]])
        owner = np.array([9, 5, 5, 5, 5, 5, 5])
        out = hd_rig.smooth_owners(owner, tris, 7)
        self.assertEqual(out[0], 5)


class FragmentTests(unittest.TestCase):
    def test_drop_fragments_keeps_main_body(self):
        rng = np.random.default_rng(2)
        body = rng.normal(size=(100, 3))
        tris = [[i, i + 1, i + 2] for i in range(0, 98)]
        shard = rng.normal(size=(3, 3)) + 10
        pos = np.vstack([body, shard])
        tris.append([100, 101, 102])
        uv = np.zeros((103, 2))
        p, u, t = hd_rig.drop_fragments(pos, uv, np.array(tris))
        self.assertEqual(len(p), 100)
        self.assertEqual(t.max(), 99)


if __name__ == "__main__":
    unittest.main()
