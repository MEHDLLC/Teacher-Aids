"""Runs a generator end to end: build, export, render, describe, record."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from . import mesh_io, plate, preview
from .generator import MATERIAL_DENSITY, BuildResult, Generator
from .listing import Listing, build_listing

DEFAULT_FORMATS = ("stl", "3mf")
APPLICATION = "teacher-aids"


@dataclass
class RunResult:
    generator: str
    slug: str
    directory: Path
    files: list[Path] = field(default_factory=list)
    build: BuildResult | None = None
    listing: Listing | None = None
    manifest: dict[str, Any] = field(default_factory=dict)

    @property
    def warnings(self) -> list[str]:
        return list(self.build.report.warnings) if self.build else []


def run(generator: Generator, supplied: dict[str, Any] | None = None,
        out_root: Path = Path("out"), formats: Iterable[str] = DEFAULT_FORMATS,
        with_preview: bool = True, slug: str | None = None,
        plate_size: tuple[float, float] = plate.DEFAULT_PLATE) -> RunResult:
    formats = tuple(dict.fromkeys(f.lower() for f in formats))
    unknown = set(formats) - {"stl", "3mf"}
    if unknown:
        raise ValueError(
            "unsupported format(s): " + ", ".join(sorted(unknown))
            + ". Supported: stl, 3mf"
        )

    opt = generator.options.resolve(supplied)
    result = generator.build(opt)
    if not len(result.parts):
        raise ValueError(f"{generator.key} produced no parts")
    # Describe what was built, which is not always what was asked for.
    opt = result.effective_options or opt

    slug = slug or generator.slug(opt)
    directory = out_root / slug
    directory.mkdir(parents=True, exist_ok=True)

    files: list[Path] = []
    if "stl" in formats:
        for part in result.parts:
            files.append(mesh_io.write_stl(directory / f"{part.name}.stl", part))

    _warn_oversized(result, plate_size)
    listing = build_listing(generator, opt, result)

    layout = None
    if "3mf" in formats:
        path, layout = mesh_io.write_3mf(
            directory / f"{slug}.3mf",
            list(result.parts),
            {
                "Title": listing.title,
                "Designer": APPLICATION,
                "Description": listing.summary,
                "Application": APPLICATION,
            },
            plate_size=plate_size,
        )
        files.append(path)

    if with_preview and len(result.parts):
        files.append(
            preview.render_scene(directory / "preview.png", result.parts.parts)
        )
        if result.context_parts:
            files.append(
                preview.render_scene(
                    directory / "preview-in-use.png",
                    result.parts.parts,
                    result.context_parts,
                )
            )

    files += listing.write(directory)

    manifest_path = directory / "manifest.json"
    files.append(manifest_path)
    manifest = _manifest(generator, opt, result, listing, slug, files,
                         directory, layout, plate_size)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return RunResult(
        generator=generator.key,
        slug=slug,
        directory=directory,
        files=files,
        build=result,
        listing=listing,
        manifest=manifest,
    )


def _warn_oversized(result: BuildResult, plate_size) -> None:
    """Say so when a part will not fit the plate it is being laid out on.

    Checked here rather than in each generator because it is the same check
    every time, and because a generator has no business refusing to make a
    600 mm number line -- someone with a big printer, or a willingness to cut
    it in half, is a legitimate user. This is a warning, never an error.
    """
    width_limit, depth_limit = plate_size
    for part in result.parts:
        width, depth, height = part.size
        # Rotating 90 degrees on the plate is free, so only the pair that
        # cannot be made to fit either way is actually too big.
        fits = ((width <= width_limit and depth <= depth_limit)
                or (depth <= width_limit and width <= depth_limit))
        if not fits:
            result.report.warn(
                f"{part.name} is {width:.0f} x {depth:.0f} mm, larger than "
                f"the {width_limit:.0f} x {depth_limit:.0f} mm plate this run "
                "laid out for. It is still exported; print it on a bigger "
                "machine, or rerun with a smaller size."
            )


def _manifest(generator: Generator, opt: dict[str, Any], result: BuildResult,
              listing: Listing, slug: str, files: list[Path],
              directory: Path, layout, plate_size) -> dict[str, Any]:
    density = MATERIAL_DENSITY.get(opt.get("material", "pla"), 1.24)
    volume = result.total_volume_cm3
    return {
        "generator": generator.key,
        "generator_title": generator.title,
        "category": generator.category,
        "slug": slug,
        "options": _jsonable(opt),
        "options_hash": _options_hash(generator.key, opt),
        "facts": _jsonable(result.facts),
        "parts": [
            {
                "name": part.name,
                "copies": part.copies,
                "size_mm": [round(v, 3) for v in part.size],
                "volume_cm3": round(part.volume_mm3 / 1000.0, 3),
                "triangles": part.triangle_count,
                "watertight_manifold": part.is_manifold(),
                "pieces": part.pieces(),
                "note": part.note,
            }
            for part in result.parts
        ],
        "distinct_parts": len(result.parts),
        "total_pieces": result.parts.total_copies,
        "plate": {
            "size_mm": list(plate_size),
            "plates": layout.plates if layout else None,
            "used_mm": [round(v, 1) for v in layout.used] if layout else None,
            "oversized": [
                list(result.parts)[min(i, len(result.parts) - 1)].name
                for i in (layout.oversized if layout else [])
            ],
        },
        "estimated_grams_solid": round(volume * density, 1),
        "listing": {"title": listing.title, "summary": listing.summary,
                    "tags": listing.tags},
        "warnings": result.report.warnings,
        "notes": result.report.notes,
        "print_notes": result.print_notes,
        "teaching_notes": result.teaching_notes,
        "files": sorted(str(f.relative_to(directory)) for f in files),
    }


def _options_hash(key: str, opt: dict[str, Any]) -> str:
    payload = json.dumps({"generator": key, "options": _jsonable(opt)},
                         sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, float):
        return round(value, 4)
    return value
