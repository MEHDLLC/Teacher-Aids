"""Base class and registry for generators."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .mesh_io import Part, PartSet
from .options import OptionSet, Report

# The categories this repo is organised by. Each one has its own catalogue and
# its own workflow, so a teacher who only wants maths manipulatives can build
# those without waiting for the alphabet.
CATEGORIES: tuple[str, ...] = (
    "alphabet",
    "math",
    "organization",
    "classroom",
    "games",
)

CATEGORY_TITLES = {
    "alphabet": "Letters and literacy",
    "math": "Maths manipulatives",
    "organization": "Classroom organisation",
    "classroom": "Classroom kit",
    "games": "Games and probability",
}


@dataclass
class BuildResult:
    """Everything a single generator run produced, before it hits disk."""

    parts: PartSet
    # What the generator actually built with. Some options imply others -- a
    # stencil has to be cut clean through whatever depth was asked for -- and
    # the manifest and listing must describe the model, not the request.
    effective_options: dict[str, Any] = field(default_factory=dict)
    # Things the printed parts sit in or hold, rendered into the previews so a
    # listing shows the aid in use. Never exported.
    context_parts: list[Part] = field(default_factory=list)
    report: Report = field(default_factory=Report)
    facts: dict[str, Any] = field(default_factory=dict)
    highlights: list[str] = field(default_factory=list)
    print_notes: list[str] = field(default_factory=list)
    # How the thing is actually used in a classroom. Kept separate from
    # `highlights` because a listing wants both "what it is" and "what to do
    # with it", and a teacher scanning a page reads the second one first.
    teaching_notes: list[str] = field(default_factory=list)

    @property
    def total_volume_cm3(self) -> float:
        return sum(p.volume_mm3 * p.copies for p in self.parts) / 1000.0


class Generator:
    """One product family.

    Subclasses declare `key`, `category`, `title`, `summary`, `options`, and
    implement `build`.  Everything else -- CLI wiring, validation, export,
    listing copy, manifest -- is handled by the shared runner.
    """

    key: str = ""
    category: str = ""
    title: str = ""
    summary: str = ""
    tags: tuple[str, ...] = ()
    # Who it is for, as a school would say it. Purely descriptive; it ends up
    # in the listing and nowhere else.
    ages: str = ""
    options: OptionSet = OptionSet([])

    def build(self, opts: dict[str, Any]) -> BuildResult:  # pragma: no cover
        raise NotImplementedError

    def slug(self, opts: dict[str, Any]) -> str:
        return self.key

    def listing_title(self, opts: dict[str, Any], result: BuildResult) -> str:
        return self.title

    def listing_body(self, opts: dict[str, Any], result: BuildResult) -> list[str]:
        """Generator-specific paragraphs inserted near the top of the listing."""
        return [self.summary]


_REGISTRY: dict[str, Generator] = {}


def register(generator: Generator) -> Generator:
    if not generator.key:
        raise ValueError("generator needs a key")
    if generator.category not in CATEGORIES:
        raise ValueError(
            f"{generator.key}: category {generator.category!r} is not one of "
            + ", ".join(CATEGORIES)
        )
    _REGISTRY[generator.key] = generator
    return generator


def get(key: str) -> Generator:
    try:
        return _REGISTRY[key]
    except KeyError:
        raise KeyError(
            f"unknown generator {key!r}; available: " + ", ".join(sorted(_REGISTRY))
        ) from None


def all_generators() -> dict[str, Generator]:
    return dict(sorted(_REGISTRY.items()))


def by_category(category: str) -> dict[str, Generator]:
    if category not in CATEGORIES:
        raise KeyError(
            f"unknown category {category!r}; available: " + ", ".join(CATEGORIES)
        )
    return {k: g for k, g in all_generators().items() if g.category == category}


MATERIAL_DENSITY = {   # g/cm^3
    "pla": 1.24,
    "petg": 1.27,
    "abs": 1.04,
    "asa": 1.07,
    "tpu": 1.21,
}
