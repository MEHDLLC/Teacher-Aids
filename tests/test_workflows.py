"""The workflows, checked against the registry.

A path filter is the kind of thing that rots silently: add a generator, forget
its line here, and that category simply stops rebuilding when the generator
changes. Nothing fails, nothing warns, and the published set drifts out of
date behind a wall of green ticks. So the filters are checked against the
registry rather than trusted.
"""

import unittest
from pathlib import Path

import yaml

import _support  # noqa: F401
from teacheraids import generator as registry

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"
SHARED = "src/teacheraids/*.py"


def load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text())


def triggers(document: dict) -> dict:
    # `on:` is the YAML 1.1 boolean True once parsed, which is a trap worth
    # handling rather than tripping over.
    return document.get("on", document.get(True, {}))


def modules_for(category: str) -> set[str]:
    return {type(g).__module__.rsplit(".", 1)[-1]
            for g in registry.by_category(category).values()}


class TestEveryCategoryHasAWorkflow(unittest.TestCase):
    def test_one_workflow_per_category(self):
        for category in registry.CATEGORIES:
            path = WORKFLOWS / f"{category}.yml"
            self.assertTrue(path.exists(), f"no workflow for {category}")

    def test_each_one_builds_its_own_category(self):
        for category in registry.CATEGORIES:
            job = load(f"{category}.yml")["jobs"]["build"]
            self.assertEqual(job["uses"],
                             "./.github/workflows/build-category.yml")
            self.assertEqual(job["with"]["category"], category)

    def test_publishing_needs_write_and_defaults_to_off(self):
        for category in registry.CATEGORIES:
            document = load(f"{category}.yml")
            job = document["jobs"]["build"]
            self.assertEqual(job["permissions"]["contents"], "write",
                             f"{category} could not cut a release")
            # A push must never publish: only a deliberate dispatch may.
            self.assertIn("|| 'no'", job["with"]["publish"], category)
            options = triggers(document)["workflow_dispatch"]["inputs"]
            self.assertEqual(options["publish"]["default"], "no", category)


class TestPathFilters(unittest.TestCase):
    def test_a_category_watches_exactly_its_own_generators(self):
        for category in registry.CATEGORIES:
            paths = triggers(load(f"{category}.yml"))["push"]["paths"]
            watched = {
                Path(p).stem for p in paths
                if p.startswith("src/teacheraids/generators/")
                and not p.endswith("__init__.py")
            }
            self.assertEqual(
                watched, modules_for(category),
                f"{category}.yml watches {sorted(watched)} but its generators "
                f"are {sorted(modules_for(category))}")

    def test_a_category_watches_its_own_catalogue(self):
        for category in registry.CATEGORIES:
            paths = triggers(load(f"{category}.yml"))["push"]["paths"]
            self.assertIn(f"catalogues/{category}.json", paths)
            others = [f"catalogues/{c}.json" for c in registry.CATEGORIES
                      if c != category]
            for other in others:
                self.assertNotIn(other, paths,
                                 f"{category}.yml rebuilds on {other}")

    def test_every_generator_is_watched_by_exactly_one_category(self):
        seen: dict[str, list[str]] = {}
        for category in registry.CATEGORIES:
            paths = triggers(load(f"{category}.yml"))["push"]["paths"]
            for path in paths:
                if (path.startswith("src/teacheraids/generators/")
                        and not path.endswith("__init__.py")):
                    seen.setdefault(Path(path).stem, []).append(category)
        every = {m for c in registry.CATEGORIES for m in modules_for(c)}
        self.assertEqual(set(seen), every)
        for module, owners in seen.items():
            self.assertEqual(len(owners), 1,
                             f"{module} is watched by {owners}")

    def test_the_shared_engine_rebuilds_everything(self):
        # font.py redraws every letterform; geom.py changes every mesh. If a
        # category stops watching those, its published set goes stale.
        for category in registry.CATEGORIES:
            paths = triggers(load(f"{category}.yml"))["push"]["paths"]
            self.assertIn(SHARED, paths,
                          f"{category}.yml ignores the shared engine")

    def test_the_shared_filter_does_not_swallow_the_generators(self):
        # `*` does not match a slash in a GitHub path filter, so the shared
        # entry covers the top-level modules only. If that ever became `**`
        # the per-category narrowing would be silently undone.
        self.assertNotIn("**", SHARED)

    def test_a_pipeline_change_rebuilds_everything(self):
        for category in registry.CATEGORIES:
            paths = triggers(load(f"{category}.yml"))["push"]["paths"]
            self.assertIn(".github/workflows/build-category.yml", paths,
                          category)
            self.assertIn(f".github/workflows/{category}.yml", paths, category)


class TestActionVersions(unittest.TestCase):
    def test_no_action_is_left_on_a_node_20_major(self):
        # Each of these reached Node 24 at a different major, and
        # download-artifact's v5 and v6 are still Node 20, so the floors are
        # not uniform. Anything at or below these is the old runtime.
        floors = {
            "actions/checkout": 6,
            "actions/setup-python": 7,
            "actions/upload-artifact": 7,
            "actions/download-artifact": 7,
        }
        found = 0
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for line in path.read_text().splitlines():
                line = line.strip()
                if not line.startswith("- uses: actions/"):
                    continue
                ref = line.split("uses:", 1)[1].strip()
                action, _, version = ref.partition("@")
                if action not in floors:
                    continue
                found += 1
                self.assertTrue(version.startswith("v"), ref)
                self.assertGreaterEqual(
                    int(version[1:].split(".")[0]), floors[action],
                    f"{path.name}: {ref} still runs on Node 20")
        self.assertGreater(found, 0, "no action references found to check")


if __name__ == "__main__":
    unittest.main()
