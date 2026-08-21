"""Catalogue expansion and validation.

A typo in a catalogue of eighty entries has to fail in the second it takes to
expand it, not in the eightieth build job an hour later.
"""

import json
import tempfile
import unittest
from pathlib import Path

import _support  # noqa: F401
from teacheraids import catalogue, generator as registry

ROOT = Path(__file__).resolve().parents[1] / "catalogues"


class TestShippedCatalogues(unittest.TestCase):
    def test_every_category_has_a_catalogue_that_expands(self):
        for category in registry.CATEGORIES:
            path = catalogue.path_for(category, ROOT)
            self.assertTrue(path.exists(), f"no catalogue for {category}")
            expanded = catalogue.load_category(category, ROOT)
            self.assertGreater(len(expanded), 0, category)

    def test_every_variant_validates_against_its_generator(self):
        for variant in catalogue.load_all(ROOT):
            catalogue.validate(variant, "shipped")

    def test_variant_names_are_unique_across_every_catalogue(self):
        names = [v.name for v in catalogue.load_all(ROOT)]
        self.assertEqual(len(names), len(set(names)))

    def test_every_generator_appears_in_its_category_catalogue(self):
        used = {v.generator for v in catalogue.load_all(ROOT)}
        for key in registry.all_generators():
            self.assertIn(key, used, f"{key} is in no catalogue")

    def test_every_catalogue_names_a_release(self):
        for category in registry.CATEGORIES:
            release = catalogue.load_category(category, ROOT).release
            self.assertIsNotNone(release, category)
            self.assertTrue(release.tag.endswith(release.version))


class TestExpansion(unittest.TestCase):
    def test_a_sweep_expands_to_every_combination(self):
        expanded = catalogue.expand({
            "sweeps": [{
                "generator": "dice",
                "name": "dice_{shape}_{size}",
                "axes": {"shape": ["cube", "octahedron"], "size": [16, 20]},
            }]
        })
        self.assertEqual(len(expanded), 4)
        self.assertIn("dice_cube_16", [v.name for v in expanded])

    def test_a_cap_takes_an_even_spread(self):
        expanded = catalogue.expand({
            "sweeps": [{
                "generator": "dice",
                "name": "dice_{size}",
                "options": {"shape": "cube"},
                "axes": {"size": [10, 12, 14, 16, 18, 20, 22, 24]},
                "cap": 3,
            }]
        })
        self.assertEqual(len(expanded), 3)
        # Spread, not the first three: the last value has to be represented.
        sizes = [v.options["size"] for v in expanded]
        self.assertGreater(max(sizes), 16)

    def test_a_bad_option_value_is_caught_at_expansion(self):
        with self.assertRaises(catalogue.CatalogueError) as caught:
            catalogue.expand({"items": [{
                "name": "bad", "generator": "dice",
                "options": {"size": 500},
            }]})
        self.assertIn("above the maximum", str(caught.exception))

    def test_an_unknown_option_is_caught_at_expansion(self):
        with self.assertRaises(catalogue.CatalogueError) as caught:
            catalogue.expand({"items": [{
                "name": "bad", "generator": "dice",
                "options": {"colour": "red"},
            }]})
        self.assertIn("unknown option", str(caught.exception))

    def test_an_unknown_generator_is_caught(self):
        with self.assertRaises(catalogue.CatalogueError):
            catalogue.expand({"items": [
                {"name": "bad", "generator": "teleporter"}]})

    def test_duplicate_names_are_refused(self):
        with self.assertRaises(catalogue.CatalogueError) as caught:
            catalogue.expand({"items": [
                {"name": "same", "generator": "dice"},
                {"name": "same", "generator": "spinner"},
            ]})
        self.assertIn("duplicate", str(caught.exception))

    def test_a_name_template_naming_a_missing_axis_is_caught(self):
        with self.assertRaises(catalogue.CatalogueError) as caught:
            catalogue.expand({"sweeps": [{
                "generator": "dice", "name": "dice_{colour}",
                "axes": {"size": [16]},
            }]})
        self.assertIn("not an axis", str(caught.exception))

    def test_a_catalogue_holding_the_wrong_category_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "math.json").write_text(json.dumps({
                "items": [{"name": "x", "generator": "dice"}]}))
            with self.assertRaises(catalogue.CatalogueError) as caught:
                catalogue.load_category("math", root)
            self.assertIn("not math generators", str(caught.exception))


class TestSelection(unittest.TestCase):
    def setUp(self):
        self.variants = catalogue.load_all(ROOT).variants

    def test_by_category(self):
        chosen = catalogue.select(self.variants, category="math")
        self.assertTrue(all(v.category == "math" for v in chosen))

    def test_limit_spreads_rather_than_truncating(self):
        chosen = catalogue.select(self.variants, limit=5, pick="spread")
        first = catalogue.select(self.variants, limit=5, pick="first")
        self.assertEqual(len(chosen), 5)
        self.assertNotEqual([v.name for v in chosen], [v.name for v in first])

    def test_chunks_cover_everything_exactly_once(self):
        seen = []
        for chunk in range(4):
            seen += [v.name for v in catalogue.select(
                self.variants, chunk=chunk, chunks=4)]
        self.assertEqual(sorted(seen), sorted(v.name for v in self.variants))

    def test_a_chunk_outside_the_range_is_refused(self):
        with self.assertRaises(catalogue.CatalogueError):
            catalogue.select(self.variants, chunk=9, chunks=4)

    def test_chunk_count(self):
        self.assertEqual(catalogue.chunk_count(0, 6), 1)
        self.assertEqual(catalogue.chunk_count(6, 6), 1)
        self.assertEqual(catalogue.chunk_count(7, 6), 2)


if __name__ == "__main__":
    unittest.main()
