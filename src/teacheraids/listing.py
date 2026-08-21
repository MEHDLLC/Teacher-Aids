"""Turns a finished build into the words that go with it.

Every run drops a title and a full description next to the models, generated
from the same numbers the geometry was built from, so the copy cannot claim a
size the model does not have, a piece count it did not produce, or a fit it
was never checked for.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .generator import MATERIAL_DENSITY, BuildResult, Generator
from .units import mm_in


@dataclass
class Listing:
    title: str
    summary: str
    highlights: list[str] = field(default_factory=list)
    teaching_notes: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    body_markdown: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write(self, directory: Path) -> list[Path]:
        directory.mkdir(parents=True, exist_ok=True)
        md = directory / "listing.md"
        md.write_text(self.body_markdown, encoding="utf-8")
        js = directory / "listing.json"
        js.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")
        return [md, js]


def build_listing(generator: Generator, opt: dict[str, Any],
                  result: BuildResult) -> Listing:
    facts = result.facts
    title = generator.listing_title(opt, result)

    sections: list[str] = [f"# {title}", ""]
    sections += generator.listing_body(opt, result)
    sections.append("")

    if result.highlights:
        sections.append("## Highlights")
        sections += [f"- {item}" for item in result.highlights]
        sections.append("")

    if result.teaching_notes:
        sections.append("## In the classroom")
        sections += [f"- {item}" for item in result.teaching_notes]
        sections.append("")

    sections.append("## What you get")
    for part in result.parts:
        width, depth, height = part.size
        count = f"{part.copies} x " if part.copies > 1 else ""
        sections.append(
            f"- **{count}{part.name}** - {width:.1f} x {depth:.1f} x "
            f"{height:.1f} mm" + (f". {part.note}" if part.note else "")
        )
    sections.append(
        "- An STL per part, and one 3MF holding every part of the set with "
        "millimetre units, named objects, and the pieces already arranged on "
        "the plate in the quantity you need."
    )
    sections.append("- A rendered preview and this description.")
    sections.append("")

    sections.append("## Dimensions")
    sections.append(_dimension_table(facts, result, opt))
    sections.append("")

    if result.print_notes:
        sections.append("## Printing")
        sections += [f"- {note}" for note in result.print_notes]
        sections.append("")

    fit = _fit_section(facts)
    if fit:
        sections.append("## Fit")
        sections.append(fit)
        sections.append("")

    if result.report.warnings:
        sections.append("## Check before you print")
        sections += [f"- {w}" for w in result.report.warnings]
        sections.append("")

    sections.append("## Options used")
    sections.append(_options_table(generator, opt))
    sections.append("")

    sections.append("## Tags")
    sections.append(", ".join(generator.tags))
    sections.append("")

    return Listing(
        title=title,
        summary=generator.summary,
        highlights=list(result.highlights),
        teaching_notes=list(result.teaching_notes),
        tags=list(generator.tags),
        body_markdown="\n".join(sections).rstrip() + "\n",
    )


def _dimension_table(facts: dict[str, Any], result: BuildResult,
                     opt: dict[str, Any]) -> str:
    rows: list[tuple[str, str]] = []
    if "piece_mm" in facts:
        width, depth, height = facts["piece_mm"]
        rows.append(("One piece", f"{mm_in(width)} x {mm_in(depth)} x "
                                  f"{mm_in(height)}"))
    if "outside_mm" in facts:
        width, depth, height = facts["outside_mm"]
        rows.append(("Outside width", mm_in(width)))
        rows.append(("Outside depth", mm_in(depth)))
        rows.append(("Outside height", mm_in(height)))
    if "pieces" in facts:
        rows.append(("Pieces in the set", str(facts["pieces"])))
    if "characters" in facts:
        rows.append(("Characters", facts["characters"]))
    if "cap_height_mm" in facts:
        rows.append(("Letter height", mm_in(facts["cap_height_mm"])))
    if "relief_mm" in facts:
        rows.append(("Relief depth", f"{facts['relief_mm']:.1f} mm"))
    if "capacity" in facts:
        rows.append(("Holds", str(facts["capacity"])))
    if "plates" in facts:
        rows.append(
            ("Build plates",
             f"{facts['plates']} at "
             f"{facts.get('plate_size_mm', [220, 220])[0]:.0f} x "
             f"{facts.get('plate_size_mm', [220, 220])[1]:.0f} mm")
        )

    density = MATERIAL_DENSITY.get(opt.get("material", "pla"), 1.24)
    volume = result.total_volume_cm3
    rows.append(
        (
            "Plastic",
            f"{volume:.0f} cm3 solid, about {volume * density:.0f} g of "
            f"{opt.get('material', 'pla').upper()} if printed solid; a normal "
            "walls-and-infill profile uses less",
        )
    )
    rows.append(("Supports", facts.get("supports", "none")))
    rows.append(("Units", "millimetres"))

    lines = ["| | |", "|---|---|"]
    lines += [f"| {name} | {value} |" for name, value in rows]
    return "\n".join(lines)


def _fit_section(facts: dict[str, Any]) -> str:
    """What this was sized against, and how sure that number is."""
    if "fit_source" not in facts:
        return ""
    parts = [facts["fit_source"]]
    confidence = facts.get("fit_confidence")
    if confidence and confidence != "published":
        parts.append(
            f"That figure is **{confidence}**, not published. Measure the one "
            "on your desk and pass it in if the fit matters: every dimension "
            "here is an option."
        )
    if facts.get("fit_notes"):
        parts.append(facts["fit_notes"])
    return "\n\n".join(parts)


def _options_table(generator: Generator, opt: dict[str, Any]) -> str:
    lines = ["| Option | Value | What it does |", "|---|---|---|"]
    for option in generator.options:
        if not option.listed:
            continue
        value = opt.get(option.name)
        if value is None:
            continue
        if option.kind == "bool":
            shown = "yes" if value else "no"
        elif option.kind in ("int", "float"):
            shown = f"{value:g}{option.unit}"
        else:
            shown = str(value)
        lines.append(f"| `{option.name}` | {shown} | {option.help} |")
    return "\n".join(lines)
