"""Turning a list of wanted products into a list of runs.

A catalogue file names the things worth building. It holds two kinds of entry:
`items`, which are one variant each, and `sweeps`, which expand a few axes into
their full combination. Both end up as the same thing -- a name, a generator,
and a set of options.

There is one catalogue per category, in `catalogues/`, because the categories
are built by separate workflows and a teacher after maths manipulatives should
not wait on the alphabet.  `load_all` stitches them back together for the
commands that want the whole shop.

Every variant is validated against its generator's own option declaration as
soon as the catalogue is read. A typo in a catalogue of two hundred entries
should fail in the second it takes to expand it, not two hundred jobs later.
"""

from __future__ import annotations

import itertools
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from . import generator as registry
from .options import OptionError

CATALOGUE_DIR = Path("catalogues")


@dataclass(frozen=True)
class Variant:
    """One run: what to build, with which options, called what."""

    name: str
    generator: str
    options: dict[str, Any] = field(default_factory=dict)
    source: str = ""

    @property
    def category(self) -> str:
        return registry.get(self.generator).category

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "generator": self.generator,
                "category": self.category, "options": dict(self.options)}


# A release name is used as a git tag and a file name, so keep it to the
# characters that are safe in both.
_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


@dataclass(frozen=True)
class Release:
    """What to call the thing this catalogue produces, when publishing it."""

    name: str
    version: str
    title: str
    summary: str = ""

    @property
    def tag(self) -> str:
        return f"{self.name}-v{self.version}"

    @property
    def display(self) -> str:
        return f"{self.title} v{self.version}"

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "version": self.version,
                "title": self.title, "summary": self.summary,
                "tag": self.tag, "display": self.display}


@dataclass(frozen=True)
class Catalogue:
    """Everything a catalogue file says: what to build, and what to call it."""

    variants: list[Variant]
    release: Release | None = None

    def __iter__(self):
        return iter(self.variants)

    def __len__(self) -> int:
        return len(self.variants)


class CatalogueError(ValueError):
    """Raised when a catalogue cannot be turned into runnable variants."""


def path_for(category: str, root: Path = CATALOGUE_DIR) -> Path:
    if category not in registry.CATEGORIES:
        raise CatalogueError(
            f"unknown category {category!r}; available: "
            + ", ".join(registry.CATEGORIES)
        )
    return root / f"{category}.json"


def load(path: Path) -> Catalogue:
    """Read a catalogue file and expand it into validated variants."""
    try:
        raw = json.loads(Path(path).read_text())
    except FileNotFoundError:
        raise CatalogueError(f"no catalogue at {path}") from None
    except json.JSONDecodeError as exc:
        raise CatalogueError(f"{path}: not valid JSON ({exc})") from None
    return expand(raw, source=str(path))


def load_category(category: str, root: Path = CATALOGUE_DIR) -> Catalogue:
    catalogue = load(path_for(category, root))
    wrong = [v.name for v in catalogue.variants if v.category != category]
    if wrong:
        raise CatalogueError(
            f"{path_for(category, root)}: these are not {category} generators: "
            + ", ".join(wrong)
            + ". Each catalogue holds one category, because each category is "
            "built by its own workflow."
        )
    return catalogue


def load_all(root: Path = CATALOGUE_DIR) -> Catalogue:
    """Every category's catalogue, in category order."""
    variants: list[Variant] = []
    for category in registry.CATEGORIES:
        path = path_for(category, root)
        if path.exists():
            variants.extend(load_category(category, root).variants)
    if not variants:
        raise CatalogueError(f"no catalogue files found under {root}/")
    _check_unique(variants, str(root))
    return Catalogue(variants, None)


def expand(raw: dict[str, Any], source: str = "catalogue") -> Catalogue:
    if not isinstance(raw, dict):
        raise CatalogueError(f"{source}: expected an object at the top level")

    variants: list[Variant] = []
    for index, item in enumerate(raw.get("items", [])):
        variants.append(_one_item(item, index, source))
    for index, sweep in enumerate(raw.get("sweeps", [])):
        variants.extend(_one_sweep(sweep, index, source))

    if not variants:
        raise CatalogueError(f"{source}: no items and no sweeps")

    _check_unique(variants, source)
    for variant in variants:
        validate(variant, source)
    return Catalogue(variants, _one_release(raw.get("release"), source))


def _check_unique(variants: Sequence[Variant], source: str) -> None:
    seen: dict[str, int] = {}
    for variant in variants:
        seen[variant.name] = seen.get(variant.name, 0) + 1
    clashes = sorted(name for name, count in seen.items() if count > 1)
    if clashes:
        raise CatalogueError(
            f"{source}: duplicate variant name(s): " + ", ".join(clashes)
            + ". Names become directory names, so they have to be unique."
        )


def _one_release(block: Any, source: str) -> Release | None:
    if block is None:
        return None
    if not isinstance(block, dict):
        raise CatalogueError(f"{source}: 'release' must be an object")

    missing = [k for k in ("name", "version", "title") if not block.get(k)]
    if missing:
        raise CatalogueError(f"{source}: release is missing " + ", ".join(missing))
    name, version = str(block["name"]), str(block["version"])
    if not _NAME_RE.match(name):
        raise CatalogueError(
            f"{source}: release name {name!r} becomes a git tag and a file "
            "name; use lower-case words joined by hyphens, like "
            "'teacher-aids-alphabet'."
        )
    if not _VERSION_RE.match(version):
        raise CatalogueError(
            f"{source}: release version {version!r} should be three numbers, "
            "like '0.1.0'."
        )
    return Release(name=name, version=version, title=str(block["title"]),
                   summary=str(block.get("summary", "")))


def validate(variant: Variant, source: str = "catalogue") -> None:
    """Check a variant against its generator's declared options."""
    try:
        generator = registry.get(variant.generator)
    except KeyError as exc:
        raise CatalogueError(f"{source}: {variant.name}: {exc}") from None
    try:
        generator.options.resolve(variant.options)
    except OptionError as exc:
        raise CatalogueError(f"{source}: {variant.name}: {exc}") from None


def select(variants: Sequence[Variant], generator: str | None = None,
           category: str | None = None, only: Iterable[str] | None = None,
           limit: int | None = None, pick: str = "spread",
           chunk: int | None = None, chunks: int | None = None
           ) -> list[Variant]:
    """Narrow a catalogue down to the runs a particular job should do."""
    chosen = list(variants)

    if category:
        if category not in registry.CATEGORIES:
            raise CatalogueError(
                f"unknown category {category!r}; available: "
                + ", ".join(registry.CATEGORIES)
            )
        chosen = [v for v in chosen if v.category == category]
        if not chosen:
            raise CatalogueError(f"no variants in category {category!r}")

    if generator:
        chosen = [v for v in chosen if v.generator == generator]
        if not chosen:
            raise CatalogueError(f"no variants use generator {generator!r}")

    if only:
        wanted = list(only)
        index = {v.name: v for v in chosen}
        missing = [name for name in wanted if name not in index]
        if missing:
            raise CatalogueError("no such variant(s): " + ", ".join(missing))
        chosen = [index[name] for name in wanted]

    if limit is not None:
        if limit < 1:
            raise CatalogueError("--limit has to be at least 1")
        chosen = _take(chosen, limit, pick)

    if chunks is not None:
        if chunks < 1:
            raise CatalogueError("--chunks has to be at least 1")
        if chunk is None:
            raise CatalogueError("--chunks needs --chunk to say which one")
        if not 0 <= chunk < chunks:
            raise CatalogueError(f"--chunk {chunk} is outside 0..{chunks - 1}")
        # Round robin rather than contiguous slices: variants differ in cost --
        # a 26-tile alphabet against a single bookmark -- and dealing them out
        # keeps every chunk about the same size of job.
        chosen = chosen[chunk::chunks]

    return chosen


def _take(variants: list[Variant], limit: int, pick: str) -> list[Variant]:
    if limit >= len(variants):
        return variants
    if pick == "first":
        return variants[:limit]
    if pick != "spread":
        raise CatalogueError(f"unknown --pick {pick!r}; use first or spread")
    # Evenly spaced, so a small limit still covers the range of the catalogue
    # instead of every result sharing the first axis value.
    step = len(variants) / limit
    return [variants[int(i * step)] for i in range(limit)]


def chunk_count(total: int, chunk_size: int, cap: int = 200) -> int:
    """How many jobs to split `total` variants across."""
    if total <= 0:
        return 1
    return max(1, min(cap, -(-total // max(chunk_size, 1))))


def _one_item(item: Any, index: int, source: str) -> Variant:
    where = f"{source}: items[{index}]"
    if not isinstance(item, dict):
        raise CatalogueError(f"{where}: expected an object")
    for required in ("name", "generator"):
        if not item.get(required):
            raise CatalogueError(f"{where}: missing {required!r}")
    options = item.get("options", {})
    if not isinstance(options, dict):
        raise CatalogueError(f"{where}: 'options' must be an object")
    return Variant(str(item["name"]), str(item["generator"]), dict(options),
                   source)


def _one_sweep(sweep: Any, index: int, source: str) -> list[Variant]:
    where = f"{source}: sweeps[{index}]"
    if not isinstance(sweep, dict):
        raise CatalogueError(f"{where}: expected an object")
    generator = sweep.get("generator")
    template = sweep.get("name")
    axes = sweep.get("axes")
    if not generator:
        raise CatalogueError(f"{where}: missing 'generator'")
    if not template:
        raise CatalogueError(
            f"{where}: missing 'name', the template each variant is named from")
    if not isinstance(axes, dict) or not axes:
        raise CatalogueError(
            f"{where}: 'axes' must be an object of option name to list of values")
    for axis, values in axes.items():
        if not isinstance(values, list) or not values:
            raise CatalogueError(
                f"{where}: axis {axis!r} must be a non-empty list of values")

    base = sweep.get("options", {})
    if not isinstance(base, dict):
        raise CatalogueError(f"{where}: 'options' must be an object")

    # A sweep is a combinatorial explosion by design. `cap` is how a catalogue
    # says "these axes multiply out to more than anyone wants; take a spread".
    cap = sweep.get("cap")
    if cap is not None and (not isinstance(cap, int) or cap < 1):
        raise CatalogueError(f"{where}: 'cap' must be a positive whole number")

    names = list(axes)
    out = []
    for combination in itertools.product(*(axes[name] for name in names)):
        chosen = dict(zip(names, combination))
        options = {**base, **chosen}
        try:
            name = template.format(**chosen)
        except KeyError as exc:
            raise CatalogueError(
                f"{where}: name template refers to {exc} which is not an axis"
            ) from None
        out.append(Variant(name, str(generator), options, source))

    if cap is not None and len(out) > cap:
        out = _take(out, cap, "spread")
    return out
