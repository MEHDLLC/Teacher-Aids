"""What actually gets written: STL, 3MF, plate layout, and the checks on them."""

import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import _support  # noqa: F401
from teacheraids import geom, mesh_io, plate, verify
from teacheraids.mesh_io import Part, PartSet

NS = {"c": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}


class TestStl(unittest.TestCase):
    def test_binary_stl_round_trips(self):
        part = Part("block", geom.box([10, 20, 30]))
        with tempfile.TemporaryDirectory() as tmp:
            path = mesh_io.write_stl(Path(tmp) / "block.stl", part)
            data = path.read_bytes()
            declared = struct.unpack("<I", data[80:84])[0]
            self.assertEqual(len(data), 84 + 50 * declared)
            report = verify.verify_file(path)[0]
            self.assertTrue(report.ok, report.problems)
            self.assertAlmostEqual(report.volume_mm3, 6000.0, places=1)
            self.assertEqual([round(v) for v in report.size_mm], [10, 20, 30])

    def test_parts_are_dropped_onto_the_bed(self):
        part = Part("floater", geom.box([10, 10, 10], at=[5, -30, 17]))
        with tempfile.TemporaryDirectory() as tmp:
            path = mesh_io.write_stl(Path(tmp) / "f.stl", part)
            report = verify.verify_file(path)[0]
            self.assertTrue(report.ok)
        # The origin shift is in the writer, not the model.
        self.assertAlmostEqual(geom.bounds(part.solid)[2], 17.0)


class TestThreeMf(unittest.TestCase):
    def _write(self, parts, **kwargs):
        tmp = tempfile.mkdtemp()
        return mesh_io.write_3mf(Path(tmp) / "set.3mf", parts,
                                 {"Title": "A set"}, **kwargs)

    def test_declares_millimetres_and_names_every_object(self):
        parts = [Part("alpha", geom.box([10, 10, 10])),
                 Part("beta", geom.box([20, 10, 10]))]
        path, _ = self._write(parts)
        with zipfile.ZipFile(path) as archive:
            model = ElementTree.fromstring(archive.read("3D/3dmodel.model"))
        self.assertEqual(model.get("unit"), "millimeter")
        names = [o.get("name") for o in model.findall(".//c:object", NS)]
        self.assertEqual(names, ["alpha", "beta"])

    def test_a_part_wanted_ten_times_is_placed_ten_times_stored_once(self):
        parts = [Part("frame", geom.box([40, 20, 4])),
                 Part("counter", geom.box([8, 8, 3]), copies=10)]
        path, layout = self._write(parts)
        with zipfile.ZipFile(path) as archive:
            model = ElementTree.fromstring(archive.read("3D/3dmodel.model"))
        self.assertEqual(len(model.findall(".//c:object", NS)), 2)
        self.assertEqual(len(model.findall(".//c:item", NS)), 11)
        self.assertEqual(len(layout.placements), 11)

    def test_items_do_not_overlap_on_the_plate(self):
        parts = [Part(f"tile_{i}", geom.box([40, 40, 4])) for i in range(12)]
        _, layout = self._write(parts)
        boxes = [(p.x, p.y, p.x + 40, p.y + 40) for p in layout.placements]
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                apart = (a[2] <= b[0] + 1e-6 or b[2] <= a[0] + 1e-6
                         or a[3] <= b[1] + 1e-6 or b[3] <= a[1] + 1e-6)
                self.assertTrue(apart, f"{a} overlaps {b}")

    def test_the_same_options_give_the_same_bytes(self):
        parts = [Part("alpha", geom.box([10, 10, 10]))]
        first, _ = self._write(parts)
        second, _ = self._write(parts)
        self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_verify_reads_the_3mf_back(self):
        parts = [Part("alpha", geom.box([10, 10, 10])),
                 Part("beta", geom.cylinder_z(6, 0, 12))]
        path, _ = self._write(parts)
        reports = verify.verify_file(path)
        self.assertEqual(len(reports), 2)
        for report in reports:
            self.assertTrue(report.ok, report.problems)

    def test_nothing_to_export_is_an_error_not_an_empty_file(self):
        with self.assertRaises(ValueError):
            self._write([Part("nothing", geom.empty())])


class TestPlate(unittest.TestCase):
    def test_rows_wrap_at_the_plate_edge(self):
        layout = plate.arrange([(60.0, 60.0)] * 9, gap=5.0,
                               plate_size=(220.0, 220.0))
        rows = {round(p.y, 3) for p in layout.placements}
        self.assertEqual(len(rows), 3)
        self.assertLessEqual(layout.used[0], 220.0)

    def test_an_oversized_part_is_reported_not_refused(self):
        layout = plate.arrange([(400.0, 40.0)], plate_size=(220.0, 220.0))
        self.assertEqual(layout.oversized, [0])
        self.assertEqual(len(layout.placements), 1)

    def test_single_plate_never_starts_a_second(self):
        layout = plate.arrange([(60.0, 60.0)] * 40, single_plate=True)
        self.assertEqual(layout.plates, 1)


class TestVerifyCatchesRealFaults(unittest.TestCase):
    def _write_raw(self, corners):
        import numpy as np
        tmp = Path(tempfile.mkdtemp()) / "raw.stl"
        record = np.zeros(len(corners), dtype=np.dtype(
            [("n", "<f4", 3), ("v", "<f4", (3, 3)), ("attr", "<u2")]))
        record["v"] = corners
        with tmp.open("wb") as handle:
            handle.write(b"\0" * 80)
            handle.write(struct.pack("<I", len(corners)))
            handle.write(record.tobytes())
        return tmp

    def test_a_hole_is_caught(self):
        import numpy as np
        part = Part("box", geom.box([10, 10, 10]))
        verts, tris = part.mesh()
        corners = verts[tris][:-1]          # drop a triangle
        report = verify.verify_file(self._write_raw(np.array(corners)))[0]
        self.assertFalse(report.ok)
        self.assertTrue(any("not watertight" in p for p in report.problems))

    def test_an_inside_out_mesh_is_caught(self):
        import numpy as np
        part = Part("box", geom.box([10, 10, 10]))
        verts, tris = part.mesh()
        corners = np.array(verts[tris])[:, ::-1]     # reverse every winding
        report = verify.verify_file(self._write_raw(corners))[0]
        self.assertFalse(report.ok)
        self.assertTrue(any("inside out" in p for p in report.problems))

    def test_a_truncated_file_is_caught(self):
        part = Part("box", geom.box([10, 10, 10]))
        with tempfile.TemporaryDirectory() as tmp:
            path = mesh_io.write_stl(Path(tmp) / "box.stl", part)
            path.write_bytes(path.read_bytes()[:-40])
            with self.assertRaises(ValueError) as caught:
                verify.verify_file(path)
            self.assertIn("Truncated", str(caught.exception))

    def test_two_loose_pieces_are_caught(self):
        part = Part("apart", geom.union([
            geom.box([10, 10, 10]), geom.box([10, 10, 10], at=[40, 0, 0])]))
        with tempfile.TemporaryDirectory() as tmp:
            path = mesh_io.write_stl(Path(tmp) / "a.stl", part)
            report = verify.verify_file(path, expect_one_piece=True)[0]
            self.assertFalse(report.ok)
            self.assertEqual(report.components, 2)


if __name__ == "__main__":
    unittest.main()
