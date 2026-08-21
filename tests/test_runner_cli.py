"""End to end: the runner writes what the manifest says it wrote."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import _support  # noqa: F401
from teacheraids import cli, generator as registry, runner, verify


class TestRunner(unittest.TestCase):
    def test_a_run_writes_a_complete_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = runner.run(
                registry.get("dice"),
                {"shape": "cube", "faces": "pips", "size": 16, "quantity": 2},
                out_root=Path(tmp))
            names = {Path(f).name for f in result.files}
            self.assertIn("listing.md", names)
            self.assertIn("manifest.json", names)
            self.assertIn("preview.png", names)
            self.assertTrue(any(n.endswith(".stl") for n in names))
            self.assertTrue(any(n.endswith(".3mf") for n in names))
            for path in result.files:
                self.assertTrue(path.exists(), path)
                self.assertGreater(path.stat().st_size, 0, path)

    def test_the_manifest_describes_the_files_next_to_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = runner.run(registry.get("ten-frame"), {"cell": 24.0},
                                out_root=Path(tmp))
            reports = verify.verify_directory(result.directory,
                                              check_manifest=True)
            self.assertTrue(reports)
            for report in reports:
                self.assertTrue(report.ok, f"{report.name}: {report.problems}")

    def test_the_manifest_records_the_options_actually_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = runner.run(registry.get("letter-tile"),
                                {"charset": "A-C", "theme": "animal"},
                                out_root=Path(tmp))
            options = result.manifest["options"]
            # `word` is auto by default and the animal theme turns it on; the
            # manifest has to say what was built, not what was asked for.
            self.assertTrue(options["word"])
            self.assertEqual(result.manifest["category"], "alphabet")
            self.assertEqual(result.manifest["total_pieces"], 3)

    def test_the_same_options_give_the_same_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = runner.run(registry.get("spinner"), {"diameter": 100.0},
                               out_root=Path(tmp), slug="a", with_preview=False)
            second = runner.run(registry.get("spinner"), {"diameter": 100.0},
                                out_root=Path(tmp), slug="b",
                                with_preview=False)
            self.assertEqual(first.manifest["options_hash"],
                             second.manifest["options_hash"])

    def test_an_oversized_part_is_warned_about_not_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = runner.run(
                registry.get("stencil"),
                {"mode": "strip", "text": "READING CORNER IS OVER THERE",
                 "cap_height": 60},
                out_root=Path(tmp), with_preview=False)
            self.assertTrue(any("larger than" in w for w in result.warnings))
            self.assertTrue(result.files)

    def test_an_unknown_format_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError) as caught:
                runner.run(registry.get("dice"), {}, out_root=Path(tmp),
                           formats=["obj"])
            self.assertIn("obj", str(caught.exception))


class TestCli(unittest.TestCase):
    def _run(self, *argv) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main(list(argv))
        return code, buffer.getvalue()

    def test_list_and_categories(self):
        code, out = self._run("list")
        self.assertEqual(code, 0)
        for key in registry.all_generators():
            self.assertIn(key, out)
        code, out = self._run("categories")
        self.assertEqual(code, 0)
        for category in registry.CATEGORIES:
            self.assertIn(category, out)

    def test_list_by_category(self):
        code, out = self._run("list", "--category", "games")
        self.assertEqual(code, 0)
        self.assertIn("dice", out)
        self.assertNotIn("book-end", out)

    def test_schema_declares_every_option_of_every_generator(self):
        code, out = self._run("schema")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(sorted(payload["generators"]),
                         sorted(registry.all_generators()))
        for key, generator in registry.all_generators().items():
            names = {o["name"] for o in payload["generators"][key]["options"]}
            self.assertEqual(names, {o.name for o in generator.options})

    def test_options_for_an_unknown_generator_fails_helpfully(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main(["options", "teleporter"])
        self.assertEqual(code, 2)

    def test_plan_counts_the_shipped_catalogue(self):
        code, out = self._run("plan", "--emit", "count")
        self.assertEqual(code, 0)
        self.assertGreater(int(out.strip()), 40)

    def test_plan_emits_a_build_matrix_that_covers_everything(self):
        _, total = self._run("plan", "--emit", "count")
        _, matrix = self._run("plan", "--emit", "matrix", "--chunk-size", "6")
        chunks = json.loads(matrix)
        self.assertEqual(sum(c["count"] for c in chunks), int(total.strip()))
        self.assertTrue(all(c["chunks"] == len(chunks) for c in chunks))

    def test_plan_release_refuses_a_partial_run(self):
        _, out = self._run("plan", "--category", "games", "--emit", "release")
        self.assertTrue(json.loads(out)["complete"])
        _, out = self._run("plan", "--category", "games", "--limit", "2",
                           "--emit", "release")
        self.assertFalse(json.loads(out)["complete"])

    def test_build_writes_and_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self._run("dice", "--shape", "cube", "--faces",
                                  "numbers", "--size", "16", "--out", tmp,
                                  "--no-preview")
            self.assertEqual(code, 0)
            self.assertIn("wrote", out)
            self.assertTrue(list(Path(tmp).rglob("*.3mf")))

    def test_set_and_flags_agree(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._run("spinner", "--set", "diameter=110", "--out", tmp,
                      "--slug", "viaset", "--no-preview", "--format", "stl")
            self._run("spinner", "--diameter", "110", "--out", tmp,
                      "--slug", "viaflag", "--no-preview", "--format", "stl")
            first = json.loads(
                (Path(tmp) / "viaset" / "manifest.json").read_text())
            second = json.loads(
                (Path(tmp) / "viaflag" / "manifest.json").read_text())
            self.assertEqual(first["options_hash"], second["options_hash"])

    def test_a_bad_option_value_fails_with_a_message(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main(["spinner", "--set", "diameter=nonsense",
                             "--out", tempfile.mkdtemp()])
        self.assertEqual(code, 1)

    def test_batch_builds_indexes_and_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self._run("batch", "--category", "games", "--limit",
                                  "2", "--out", tmp, "--no-preview")
            self.assertEqual(code, 0, out)
            index = json.loads((Path(tmp) / "index.json").read_text())
            self.assertEqual(len(index["built"]), 2)
            self.assertEqual(index["failed"], [])
            self.assertTrue((Path(tmp) / "INDEX.md").exists())

    def test_notes_are_built_from_what_is_on_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._run("batch", "--category", "games", "--limit", "2",
                      "--out", tmp, "--no-preview")
            code, _ = self._run("notes", tmp, "--category", "games")
            self.assertEqual(code, 0)
            notes = (Path(tmp) / "RELEASE-NOTES.md").read_text()
            self.assertIn("Games and Probability", notes)
            self.assertIn("2 models", notes)

    def test_verify_reports_on_a_built_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._run("batch", "--category", "games", "--limit", "1",
                      "--out", tmp, "--no-preview")
            code, out = self._run("verify", tmp)
            self.assertEqual(code, 0)
            self.assertIn("0 failed", out)


if __name__ == "__main__":
    unittest.main()
