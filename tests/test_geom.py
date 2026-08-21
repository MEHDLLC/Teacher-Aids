"""The geometry layer. Mostly about the failures that are silent."""

import math
import unittest

import _support  # noqa: F401
from teacheraids import geom


class TestProfiles(unittest.TestCase):
    def test_clockwise_profile_is_rewound(self):
        # A clockwise loop reads as a hole and extrudes to nothing, silently.
        # Every helper normalises the winding, so both orders give a solid.
        clockwise = [(0, 0), (0, 10), (10, 10), (10, 0)]
        counter = list(reversed(clockwise))
        self.assertLess(geom.signed_area(clockwise), 0)
        for profile in (clockwise, counter):
            solid = geom.prism_z(profile, 0, 5)
            self.assertAlmostEqual(solid.volume(), 500.0, places=3)

    def test_degenerate_profile_is_rejected(self):
        with self.assertRaises(ValueError):
            geom.ensure_ccw([(0, 0), (1, 1), (2, 2)])
        with self.assertRaises(ValueError):
            geom.ensure_ccw([(0, 0), (1, 1)])

    def test_dedupe_drops_the_wrap_around(self):
        points = geom.dedupe([(0, 0), (1, 0), (1, 0), (1, 1), (0, 0)])
        self.assertEqual(points, [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)])

    def test_rounded_rect_keeps_its_size(self):
        for radius in (0.0, 2.0, 8.0, 40.0):
            shape = geom.rounded_rect(40, 30, radius)
            width, depth = geom.shape_size(shape)
            self.assertAlmostEqual(width, 40.0, places=3)
            self.assertAlmostEqual(depth, 30.0, places=3)

    def test_regular_polygon_by_edge(self):
        # A hexagon built on a 25.4 mm edge has 25.4 mm edges.
        shape = geom.regular_polygon_by_edge(6, 25.4)
        ring = [(float(x), float(y)) for x, y in shape.to_polygons()[0]]
        for index in range(len(ring)):
            a, b = ring[index], ring[(index + 1) % len(ring)]
            self.assertAlmostEqual(math.dist(a, b), 25.4, places=3)

    def test_sector_area_matches_the_angle(self):
        full = geom.circle(20.0).area()
        quarter = geom.sector(20.0, 0.0, 90.0).area()
        self.assertAlmostEqual(quarter / full, 0.25, places=2)


class TestExtrude(unittest.TestCase):
    def test_taper_narrows_the_top(self):
        solid = geom.extrude(geom.rect(20, 20), 2.0, taper=0.4)
        mesh = solid.to_mesh()
        import numpy as np
        verts = np.asarray(mesh.vert_properties)[:, :3]
        top = verts[verts[:, 2] > 1.9]
        bottom = verts[verts[:, 2] < 0.1]
        self.assertAlmostEqual(np.ptp(bottom[:, 0]), 20.0, places=2)
        self.assertAlmostEqual(np.ptp(top[:, 0]), 19.2, places=2)

    def test_taper_backs_off_rather_than_pinching(self):
        # A taper wide enough to close the counter of an A would extrude into
        # a solid that touches itself along an edge. The result must still be
        # edge-manifold; losing some draft is the acceptable outcome.
        from teacheraids import text
        glyph = text.glyph_shape("A", 20.0, 18.0)
        for taper in (0.1, 0.4, 0.9, 1.4):
            solid = geom.extrude(glyph, 1.6, taper=taper)
            self.assertFalse(solid.is_empty())
            self.assertTrue(geom.edge_manifold(solid),
                            f"taper {taper} left a non-manifold edge")

    def test_zero_height_is_empty_not_an_error(self):
        self.assertTrue(geom.extrude(geom.rect(10, 10), 0.0).is_empty())


class TestSolids(unittest.TestCase):
    def test_is_one_piece(self):
        joined = geom.union([geom.box([10, 10, 10]),
                             geom.box([10, 10, 10], at=[5, 0, 0])])
        apart = geom.union([geom.box([10, 10, 10]),
                            geom.box([10, 10, 10], at=[30, 0, 0])])
        self.assertTrue(geom.is_one_piece(joined))
        self.assertFalse(geom.is_one_piece(apart))

    def test_edge_manifold_catches_a_self_touching_solid(self):
        # Two boxes meeting along exactly one edge: valid to manifold, and a
        # mesh no slicer will accept.
        pinched = geom.union([geom.box([10, 10, 10]),
                              geom.box([10, 10, 10], at=[10, 10, 0])])
        self.assertFalse(geom.edge_manifold(pinched))
        self.assertTrue(geom.edge_manifold(geom.box([10, 10, 10])))

    def test_touches(self):
        a = geom.box([10, 10, 10])
        self.assertTrue(geom.touches(a, geom.box([10, 10, 10], at=[5, 0, 0])))
        self.assertFalse(geom.touches(a, geom.box([10, 10, 10], at=[11, 0, 0])))


if __name__ == "__main__":
    unittest.main()
