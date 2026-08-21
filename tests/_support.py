"""Shared setup: make `src` importable without installing the package."""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from teacheraids import generator as registry      # noqa: E402
from teacheraids import generators                 # noqa: E402,F401


def build(key: str, **options):
    """Resolve options and build, the way the runner does."""
    generator = registry.get(key)
    resolved = generator.options.resolve(options)
    return generator, resolved, generator.build(resolved)


def every_generator():
    return registry.all_generators()
