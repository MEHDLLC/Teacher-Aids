"""The Platonic solids, their faces and their frames."""

import unittest

import numpy as np

import _support  # noqa: F401
from teacheraids import geom, polyhedra

EXPECTED = {
    "tetrahedron": (4, 6, 4),
    "cube": (6, 12, 8),
    "octahedron": (8, 12, 6),
    "dodecahedron": (12, 30, 20),
    "icosahedron": (20, 30, 12),
}


class TestPolyhedra(unittest.TestCase):
    def test_faces_edges_and_vertices_are_read_back_correctly(self):
        for name, counts in EXPECTED.items():
            solid = polyhedra.build(name, 20.0)
            self.assertEqual(solid.counts, counts, name)
            self.assertTrue(solid.check_euler(), name)

    def test_every_solid_stands_on_a_face(self):
        for name in EXPECTED:
            solid = polyhedra.build(name, 20.0)
            heights = solid.vertices[:, 2]
            self.assertAlmostEqual(heights.min(), 0.0, places=6, msg=name)
            # A face on the bed means all of that face's corners on the bed,
            # which is at least three of them.
            on_bed = int((heights < 1e-4).sum())
            self.assertGreaterEqual(on_bed, 3, name)

    def test_faces_are_regular_and_the_right_shape(self):
        sides = {"tetrahedron": 3, "cube": 4, "octahedron": 3,
                 "dodecahedron": 5, "icosahedron": 3}
        for name, count in sides.items():
            for face in polyhedra.build(name, 20.0).faces:
                self.assertEqual(face.sides, count, name)

    def test_frames_are_printable_meshes(self):
        for name in EXPECTED:
            solid = polyhedra.build(name, 22.0).solid()
            for rib in (2.0, 3.5, 5.0):
                frame = polyhedra.build(name, 22.0).frame(rib)
                self.assertTrue(geom.is_one_piece(frame),
                                f"{name} at rib {rib} came apart")
                self.assertTrue(geom.edge_manifold(frame),
                                f"{name} at rib {rib} is not edge-manifold")
                self.assertLess(frame.volume(), solid.volume(), name)

    def test_a_thin_rib_leaves_a_frame_that_is_mostly_air(self):
        for name in EXPECTED:
            model = polyhedra.build(name, 22.0)
            self.assertLess(model.frame(2.0).volume(),
                            model.solid().volume() * 0.5, name)

    def test_from_points_frames_anything_convex(self):
        cases = {
            "cuboid": [(x, y, z) for z in (0, 60) for y in (0, 30)
                       for x in (0, 50)],
            "square pyramid": [(0, 0, 0), (40, 0, 0), (40, 40, 0), (0, 40, 0),
                               (20, 20, 45)],
            "triangular prism": [(0, 0, 0), (30, 0, 0), (15, 26, 0),
                                 (0, 0, 40), (30, 0, 40), (15, 26, 40)],
        }
        for name, points in cases.items():
            frame = polyhedra.from_points(np.array(points, dtype=float)).frame(3.5)
            self.assertTrue(geom.is_one_piece(frame), name)
            self.assertTrue(geom.edge_manifold(frame), name)

    def test_a_rib_thicker_than_the_solid_is_refused_clearly(self):
        with self.assertRaises(ValueError) as caught:
            polyhedra.build("cube", 8.0).frame(20.0)
        self.assertIn("rib", str(caught.exception))

    def test_place_on_face_lands_on_the_face(self):
        for name in EXPECTED:
            solid = polyhedra.build(name, 20.0)
            for face in solid.faces:
                marker = geom.extrude(geom.circle(0.4), 0.5, at_z=-0.25)
                placed = polyhedra.place_on_face(marker, face)
                centre = np.array(geom.centre_of(placed))
                self.assertLess(float(np.linalg.norm(centre - face.centre)),
                                0.05, f"{name}: marker missed its face")

    def test_unknown_solid_names_the_ones_it_knows(self):
        with self.assertRaises(KeyError) as caught:
            polyhedra.build("rhombicuboctahedron")
        self.assertIn("tetrahedron", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
