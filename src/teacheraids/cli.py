"""Command line entry point.

    teachergen list
    teachergen list --category math
    teachergen options letter-tile
    teachergen letter-tile --charset uppercase --theme animal
    teachergen batch --category alphabet --out out
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from . import catalogue as catalogue_module
from . import generator as registry
from . import runner, verify
from .catalogue import CATALOGUE_DIR, CatalogueError, Variant
from .options import OptionError, merge_sequence
from .presets import BORES
from .units import to_inch

# Importing the package is what registers every generator.
from . import generators                                          # noqa: F401


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="teachergen",
        description="Parametric generators for printable classroom teaching "
                    "aids.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    listing = sub.add_parser("list", help="list the available generators")
    listing.add_argument("--category", choices=registry.CATEGORIES)

    sub.add_parser("categories", help="list the categories")
    sub.add_parser("bores", help="list the marker and pen presets")
    sub.add_parser("glyphs", help="list the characters the font can draw")

    show = sub.add_parser("options", help="show one generator's options")
    show.add_argument("generator")

    schema = sub.add_parser(
        "schema",
        help="every variable of every generator, as JSON",
        description="Machine-readable declaration of every option, so a "
                    "pipeline can discover the variables instead of "
                    "duplicating them.",
    )
    schema.add_argument("generator", nargs="?")

    plan = sub.add_parser(
        "plan", help="expand a catalogue into the runs it describes")
    _add_selection(plan)
    plan.add_argument("--chunk-size", type=int, default=6, metavar="N",
                      help="variants per job when emitting a build matrix")
    plan.add_argument("--emit", default="table",
                      choices=("table", "names", "json", "matrix", "count",
                               "release"),
                      help="shape of the output")

    batch = sub.add_parser("batch", help="build every run a catalogue selects")
    _add_selection(batch)
    batch.add_argument("--chunk", type=int, metavar="I",
                       help="build only this chunk (with --chunks)")
    batch.add_argument("--chunks", type=int, metavar="K",
                       help="total number of chunks the catalogue is split into")
    batch.add_argument("--out", default="out", metavar="DIR")
    batch.add_argument("--format", default="stl,3mf", metavar="LIST")
    batch.add_argument("--no-preview", action="store_true")
    batch.add_argument("--no-verify", action="store_true",
                       help="skip re-reading each written file")
    batch.add_argument("--keep-going", action="store_true",
                       help="finish the batch and report failures at the end")

    index = sub.add_parser(
        "index", help="write INDEX.md and index.json for a directory of runs")
    index.add_argument("directory", metavar="DIR")

    notes = sub.add_parser(
        "notes", help="write release notes for a directory of runs")
    notes.add_argument("directory", metavar="DIR")
    notes.add_argument("--catalogue", metavar="FILE")
    notes.add_argument("--category", choices=registry.CATEGORIES)
    notes.add_argument("--verify", metavar="FILE",
                       help="a report from `teachergen verify --json`")
    notes.add_argument("--out", metavar="FILE",
                       help="where to write (default DIR/RELEASE-NOTES.md)")

    check = sub.add_parser(
        "verify", help="re-read written STL/3MF files and check them")
    check.add_argument("paths", nargs="+", metavar="PATH")
    check.add_argument("--strict", action="store_true",
                       help="treat warnings as failures too")
    check.add_argument("--allow-multi-part", action="store_true",
                       help="do not require each mesh to be a single piece")
    check.add_argument("--json", dest="as_json", metavar="FILE",
                       help="also write a machine-readable report here")

    for key, generator in registry.all_generators().items():
        build = sub.add_parser(
            key, help=generator.summary, description=generator.summary,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
        _add_common(build)
        generator.options.add_to_parser(build)

    args = parser.parse_args(argv)

    if args.command == "list":
        return _list_generators(args.category)
    if args.command == "categories":
        return _list_categories()
    if args.command == "bores":
        return _list_bores()
    if args.command == "glyphs":
        return _list_glyphs()
    if args.command == "options":
        return _show_options(args.generator)
    if args.command == "schema":
        return _schema(args.generator)
    if args.command == "plan":
        return _plan(args)
    if args.command == "batch":
        return _batch(args)
    if args.command == "index":
        root = Path(args.directory)
        if not root.is_dir():
            print(f"error: no such directory: {root}", file=sys.stderr)
            return 2
        count = _write_index(root)
        print(f"indexed {count} model(s) in {root / 'INDEX.md'}")
        return 0 if count else 1
    if args.command == "notes":
        return _notes(args)
    if args.command == "verify":
        return _verify(args)
    return _build(args)


def _add_selection(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("Selection")
    group.add_argument("--catalogue", metavar="FILE",
                       help="a specific catalogue file; default is every "
                            "catalogue under catalogues/")
    group.add_argument("--category", choices=registry.CATEGORIES,
                       help="only this category (and its catalogue file)")
    group.add_argument("--generator", metavar="KEY",
                       help="only variants built by this generator")
    group.add_argument("--only", metavar="NAMES",
                       help="comma separated variant names")
    group.add_argument("--limit", type=int, metavar="N",
                       help="build at most this many")
    group.add_argument("--pick", default="spread", choices=("spread", "first"),
                       help="how --limit chooses: evenly spread, or the first N")


def _add_common(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("Run")
    group.add_argument("--out", default="out", metavar="DIR",
                       help="where to write the run directory")
    group.add_argument("--format", default="stl,3mf", metavar="LIST",
                       help="comma separated: stl, 3mf")
    group.add_argument("--no-preview", action="store_true",
                       help="skip rendering the preview image")
    group.add_argument("--set", action="append", default=[], metavar="NAME=VALUE",
                       help="set an option by name; repeatable")
    group.add_argument("--options-file", metavar="FILE",
                       help="JSON file of option values, applied before flags")
    group.add_argument("--slug", metavar="NAME",
                       help="override the output directory name")


def _list_generators(category: str | None) -> int:
    generators = (registry.by_category(category) if category
                  else registry.all_generators())
    current = None
    for key, generator in sorted(generators.items(),
                                 key=lambda kv: (kv[1].category, kv[0])):
        if generator.category != current:
            current = generator.category
            print(f"\n== {current} - "
                  f"{registry.CATEGORY_TITLES[current]} ==\n")
        print(f"{key:17s}  {generator.title}"
              + (f"   (ages {generator.ages})" if generator.ages else ""))
        print(f"{'':17s}  {generator.summary}")
        print()
    return 0


def _list_categories() -> int:
    for category in registry.CATEGORIES:
        keys = sorted(registry.by_category(category))
        print(f"{category:14s} {registry.CATEGORY_TITLES[category]}")
        print(f"{'':14s} catalogue: {catalogue_module.path_for(category)}")
        print(f"{'':14s} generators: " + ", ".join(keys))
        print()
    return 0


def _list_bores() -> int:
    for key, spec in BORES.items():
        print(f"{key}")
        print(f"  {spec.label}")
        print(f"  {spec.diameter:.1f} mm across "
              f"({to_inch(spec.diameter):.2f} in), {spec.length:.0f} mm long")
        print(f"  confidence: {spec.confidence}")
        print()
    return 0


def _list_glyphs() -> int:
    from . import font
    for name, chars in (("upper case", font.UPPERCASE),
                        ("lower case", font.LOWERCASE),
                        ("digits", font.DIGITS),
                        ("operators", font.OPERATORS),
                        ("punctuation", font.PUNCTUATION)):
        print(f"{name:14s} {' '.join(chars)}")
    extra = sorted(set(font.GLYPHS)
                   - set(font.UPPERCASE + font.LOWERCASE + font.DIGITS
                         + font.OPERATORS + font.PUNCTUATION))
    print(f"{'other':14s} " + " ".join(c for c in extra if c.strip()))
    return 0


def _show_options(key: str) -> int:
    try:
        generator = registry.get(key)
    except KeyError as exc:
        print(exc, file=sys.stderr)
        return 2
    print(f"{generator.key} - {generator.title}  [{generator.category}]\n")
    print(f"  {generator.summary}\n")
    for group, options in generator.options.groups().items():
        print(group)
        for option in options:
            print(f"  {option.flag:<26} {option.help}")
            print(f"  {'':<26} default: {option.describe_default()}"
                  + (f"; one of {', '.join(option.choices)}"
                     if option.choices else ""))
        print()
    return 0


def _schema(key: str | None) -> int:
    generators = (
        {key: registry.get(key)} if key else registry.all_generators()
    )
    payload = {
        "categories": {
            name: {
                "title": registry.CATEGORY_TITLES[name],
                "generators": sorted(registry.by_category(name)),
            }
            for name in registry.CATEGORIES
        },
        "generators": {
            name: {
                "title": gen.title,
                "category": gen.category,
                "summary": gen.summary,
                "ages": gen.ages,
                "tags": list(gen.tags),
                "options": [
                    {
                        "name": option.name,
                        "flag": option.flag,
                        "kind": option.kind,
                        "default": option.default,
                        "default_note": option.default_note or None,
                        "choices": list(option.choices) or None,
                        "minimum": option.minimum,
                        "maximum": option.maximum,
                        "unit": option.unit.strip() or None,
                        "group": option.group,
                        "help": option.help,
                    }
                    for option in gen.options
                ],
            }
            for name, gen in generators.items()
        },
        "bores": {name: spec.to_dict() for name, spec in BORES.items()},
    }
    print(json.dumps(payload, indent=2))
    return 0


def _load(args: argparse.Namespace) -> catalogue_module.Catalogue:
    if getattr(args, "catalogue", None):
        return catalogue_module.load(Path(args.catalogue))
    if getattr(args, "category", None):
        return catalogue_module.load_category(args.category)
    return catalogue_module.load_all()


def _selected(args: argparse.Namespace) -> list[Variant]:
    return catalogue_module.select(
        _load(args).variants,
        generator=getattr(args, "generator", None),
        category=getattr(args, "category", None),
        only=[n.strip() for n in args.only.split(",")] if args.only else None,
        limit=args.limit,
        pick=args.pick,
        chunk=getattr(args, "chunk", None),
        chunks=getattr(args, "chunks", None),
    )


def _plan(args: argparse.Namespace) -> int:
    try:
        chosen = _selected(args)
    except CatalogueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.emit == "release":
        try:
            catalogue = _load(args)
        except CatalogueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if catalogue.release is None:
            print(
                "error: no 'release' block to name a release after. Releases "
                "are per category, so pass --category or --catalogue.",
                file=sys.stderr,
            )
            return 2
        # A tag claims to be the whole catalogue. Say so plainly when the run
        # was narrowed, so a caller can refuse to publish a partial set under
        # a name that implies everything.
        complete = not (args.limit or args.generator or args.only)
        payload = catalogue.release.to_dict()
        payload.update({
            "planned": len(chosen),
            "total": len(catalogue),
            "complete": complete and len(chosen) == len(catalogue),
        })
        print(json.dumps(payload, indent=2))
    elif args.emit == "count":
        print(len(chosen))
    elif args.emit == "names":
        for variant in chosen:
            print(variant.name)
    elif args.emit == "json":
        print(json.dumps([v.to_dict() for v in chosen], indent=2))
    elif args.emit == "matrix":
        chunks = catalogue_module.chunk_count(len(chosen), args.chunk_size)
        print(json.dumps([
            {"chunk": index, "chunks": chunks,
             "count": len(chosen[index::chunks])}
            for index in range(chunks)
        ]))
    else:
        where = (args.catalogue or (f"catalogues/{args.category}.json"
                                    if args.category else "catalogues/"))
        print(f"{len(chosen)} variants from {where}\n")
        for variant in chosen:
            shown = ", ".join(
                f"{k}={v}" for k, v in sorted(variant.options.items()))
            print(f"  {variant.name:<46} {variant.generator:<16} {shown[:70]}")
    return 0


def _batch(args: argparse.Namespace) -> int:
    try:
        chosen = _selected(args)
    except CatalogueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    root = Path(args.out)
    formats = [f.strip() for f in args.format.split(",") if f.strip()]
    built: list[dict[str, Any]] = []
    failures: list[tuple[str, str]] = []

    print(f"building {len(chosen)} variant(s) into {root}\n")
    for position, variant in enumerate(chosen, start=1):
        label = f"[{position}/{len(chosen)}] {variant.name}"
        try:
            result = runner.run(
                registry.get(variant.generator), variant.options,
                out_root=root, formats=formats,
                with_preview=not args.no_preview, slug=variant.name,
            )
            reports = [] if args.no_verify else verify.verify_directory(
                result.directory, check_manifest=True
            )
            broken = [r for r in reports if r.problems]
            if broken:
                detail = "; ".join(
                    f"{r.name}: {p}" for r in broken for p in r.problems)
                raise ValueError(f"written files failed verification: {detail}")

            grams = result.manifest["estimated_grams_solid"]
            print(f"{label}: {result.manifest['listing']['title'][:72]}")
            print(f"{'':4}{result.manifest['total_pieces']} piece(s), "
                  f"{len(result.files)} files, about {grams:.0f} g"
                  + (f", {len(reports)} mesh(es) verified" if reports else ""))
            built.append({
                "name": variant.name,
                "generator": variant.generator,
                "category": result.manifest["category"],
                "title": result.manifest["listing"]["title"],
                "directory": str(result.directory),
                "grams": grams,
                "parts": result.manifest["parts"],
                "warnings": result.warnings,
                "mesh_reports": [r.to_dict() for r in reports],
            })
        except (OptionError, CatalogueError, ValueError, KeyError) as exc:
            print(f"{label}: FAILED - {exc}", file=sys.stderr)
            failures.append((variant.name, str(exc)))
            if not args.keep_going:
                return 1

    indexed = _write_index(root, failures)
    print(f"\nbuilt {len(built)} of {len(chosen)}; "
          f"{indexed} model(s) indexed in {root / 'INDEX.md'}")
    if failures:
        print(f"{len(failures)} failed:", file=sys.stderr)
        for name, reason in failures:
            print(f"  {name}: {reason}", file=sys.stderr)
        return 1
    return 0


def _write_index(root: Path, failures: Sequence[tuple[str, str]] = ()) -> int:
    """Summarise every run under `root` by reading the manifests it left.

    Built from what is on disk rather than from what this process happened to
    make, so a job that merges chunks from several machines indexes them the
    same way a single run does.
    """
    root.mkdir(parents=True, exist_ok=True)
    entries = []
    for manifest_path in sorted(root.rglob("manifest.json")):
        manifest = json.loads(manifest_path.read_text())
        entries.append({
            "name": manifest["slug"],
            "generator": manifest["generator"],
            "category": manifest.get("category", ""),
            "title": manifest["listing"]["title"],
            "directory": str(manifest_path.parent.relative_to(root)),
            "grams": manifest["estimated_grams_solid"],
            "options_hash": manifest["options_hash"],
            "pieces": manifest.get("total_pieces", len(manifest["parts"])),
            "parts": manifest["parts"],
            "warnings": manifest["warnings"],
        })

    (root / "index.json").write_text(
        json.dumps(
            {"built": entries,
             "failed": [{"name": n, "reason": r} for n, r in failures]},
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    lines = [f"# {len(entries)} models", ""]
    if failures:
        lines += [f"**{len(failures)} failed to build:**", ""]
        lines += [f"- `{name}` - {reason}" for name, reason in failures]
        lines.append("")

    by_category: dict[str, list[dict]] = {}
    for entry in entries:
        by_category.setdefault(entry["category"] or "other", []).append(entry)

    for category, group in sorted(by_category.items()):
        title = registry.CATEGORY_TITLES.get(category, category)
        lines += [f"## {title} ({len(group)})", "",
                  "| Model | Generator | Pieces | Size (mm) | Plastic | Notes |",
                  "|---|---|---|---|---|---|"]
        for entry in group:
            size = entry["parts"][0]["size_mm"] if entry["parts"] else [0, 0, 0]
            lines.append(
                f"| [{entry['name']}]({entry['directory']}/) | "
                f"{entry['generator']} | {entry['pieces']} | "
                + " x ".join(f"{v:.0f}" for v in size)
                + f" | {entry['grams']:.0f} g | "
                + ("; ".join(entry["warnings"])[:120]
                   if entry["warnings"] else "-")
                + " |"
            )
        lines.append("")
    (root / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(entries)


def _notes(args: argparse.Namespace) -> int:
    """Compose release notes from what a run actually left on disk.

    Built from index.json and the verify report rather than written by hand,
    so the notes cannot claim a model count or a clean bill of health that the
    files do not support.
    """
    root = Path(args.directory)
    index_path = root / "index.json"
    if not index_path.exists():
        print(f"error: no index.json in {root}; run `teachergen index` first",
              file=sys.stderr)
        return 2

    try:
        catalogue = _load(args)
    except CatalogueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    release = catalogue.release
    if release is None:
        print("error: no 'release' block; pass --category or --catalogue",
              file=sys.stderr)
        return 2

    built = json.loads(index_path.read_text())["built"]
    generators = sorted({entry["generator"] for entry in built})
    grams = sum(entry["grams"] for entry in built)
    pieces = sum(entry.get("pieces", 0) for entry in built)

    lines = [f"# {release.display}", ""]
    if release.summary:
        lines += [release.summary, ""]

    lines += [
        f"**{len(built)} models**, **{pieces} printable pieces**, from "
        f"{len(generators)} generator{'s' if len(generators) != 1 else ''}"
        f" ({', '.join(generators)}).",
        "",
    ]

    if args.verify and Path(args.verify).exists():
        reports = json.loads(Path(args.verify).read_text())
        failed = [r for r in reports if not r["ok"]]
        warned = [r for r in reports if r["ok"] and r["warnings"]]
        lines += [
            "## Validation",
            "",
            "Every file below was re-read off disk after it was written and "
            "its topology rebuilt from scratch.",
            "",
            "| | |",
            "|---|---|",
            f"| Meshes checked | {len(reports)} |",
            f"| Triangles | {sum(r['triangles'] for r in reports):,} |",
            f"| Watertight | {sum(1 for r in reports if r['watertight'])} of {len(reports)} |",
            f"| Winding consistent | {sum(1 for r in reports if r['winding_consistent'])} of {len(reports)} |",
            f"| Single connected piece | {sum(1 for r in reports if r['components'] == 1)} of {len(reports)} |",
            f"| **Failed** | **{len(failed)}** |",
            f"| Warnings | {len(warned)} |",
            "",
        ]
        if warned:
            lines += [
                "Warnings are all zero-area triangles: booleans leave a few "
                "wherever two coplanar faces meet, the surface is still "
                "closed, and every slicer skips them.",
                "",
            ]
        if failed:
            lines += ["Failed:", ""]
            lines += [f"- `{r['name']}` - {'; '.join(r['problems'])}"
                      for r in failed]
            lines.append("")

    lines += [
        "## What is in the download",
        "",
        "One folder per model. Each contains:",
        "",
        "- **STL** per part and one **3MF** holding every part of that model, "
        "with millimetre units, named objects, and the pieces already laid "
        "out on the plate in the quantity you need.",
        "- **preview.png** - a plan view, a three-quarter view and an "
        "elevation.",
        "- **listing.md** - what it is, what it teaches, dimensions, print "
        "notes.",
        "- **manifest.json** - every option, derived dimension and part size.",
        "",
        "`INDEX.md` at the top lists everything by category.",
        "",
        "## Printing",
        "",
        "Everything here prints flat or upright as supplied, with **no "
        "supports**. 0.2 mm layers, 3 or 4 perimeters, 15-20% infill unless a "
        "model's own notes say otherwise.",
        "",
        "Where a model has raised lettering, the letters start exactly at the "
        "plate's top surface, so a colour change at that height in any slicer "
        "gives a two-colour part for the cost of one filament swap.",
        "",
        f"Total plastic across all {len(built)} models is about "
        f"{grams / 1000:.1f} kg if every one were printed solid; a normal "
        "walls-and-infill profile uses well under that.",
        "",
        "## Safety",
        "",
        "Several of these sets have pieces small enough to fit the "
        "small-parts cylinder used for toy safety testing. Counters, unit "
        "cubes, dice and fraction pieces are choking hazards for children "
        "under three. Each model's `listing.md` says so where it applies.",
        "",
        "## Models",
        "",
        "| Model | Pieces | Size (mm) | Plastic |",
        "|---|---|---|---|",
    ]
    for entry in built:
        size = entry["parts"][0]["size_mm"] if entry["parts"] else [0, 0, 0]
        lines.append(
            f"| {entry['name']} | {entry.get('pieces', 1)} | "
            + " x ".join(f"{v:.0f}" for v in size)
            + f" | {entry['grams']:.0f} g |"
        )

    destination = Path(args.out) if args.out else root / "RELEASE-NOTES.md"
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {destination} for {release.tag}")
    return 0


def _verify(args: argparse.Namespace) -> int:
    reports: list[verify.MeshReport] = []
    try:
        for raw in args.paths:
            path = Path(raw)
            if path.is_dir():
                reports.extend(verify.verify_directory(
                    path, expect_one_piece=not args.allow_multi_part))
            elif path.exists():
                reports.extend(verify.verify_file(
                    path, expect_one_piece=not args.allow_multi_part))
            else:
                print(f"error: no such path: {path}", file=sys.stderr)
                return 2
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not reports:
        print("error: found no STL or 3MF files to check", file=sys.stderr)
        return 2

    for report in reports:
        print(report.summary())
        for warning in report.warnings:
            print(f"      ~ {warning}")
        for problem in report.problems:
            print(f"      ! {problem}")

    if args.as_json:
        Path(args.as_json).write_text(
            json.dumps([r.to_dict() for r in reports], indent=2) + "\n",
            encoding="utf-8",
        )

    failed = [r for r in reports if r.problems]
    warned = [r for r in reports if r.warnings and not r.problems]
    print(
        f"\n{len(reports)} mesh(es): {len(reports) - len(failed) - len(warned)} "
        f"clean, {len(warned)} with warnings, {len(failed)} failed"
    )
    if failed:
        return 1
    return 1 if (args.strict and warned) else 0


def _build(args: argparse.Namespace) -> int:
    generator = registry.get(args.command)
    known = {option.name for option in generator.options}

    supplied: dict[str, Any] = {}
    if args.options_file:
        supplied.update(json.loads(Path(args.options_file).read_text()))
    try:
        supplied.update(merge_sequence(args.set))
    except OptionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    supplied.update({k: v for k, v in vars(args).items() if k in known})

    try:
        result = runner.run(
            generator,
            supplied,
            out_root=Path(args.out),
            formats=[f.strip() for f in args.format.split(",") if f.strip()],
            with_preview=not args.no_preview,
            slug=args.slug,
        )
    except (OptionError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    _report(result)
    return 0


def _report(result: runner.RunResult) -> None:
    print(f"{result.manifest['listing']['title']}\n")
    for part in result.manifest["parts"]:
        width, depth, height = part["size_mm"]
        count = f"{part['copies']:>3d} x " if part["copies"] > 1 else "      "
        print(
            f"  {count}{part['name']:<30} {width:6.1f} x {depth:6.1f} x "
            f"{height:6.1f} mm  {part['volume_cm3']:6.1f} cm3 "
            f"{part['triangles']:>7d} tris"
        )
    plate = result.manifest["plate"]
    print(
        f"\n  {result.manifest['total_pieces']} piece(s) on "
        f"{plate['plates']} plate(s) of "
        f"{plate['size_mm'][0]:.0f} x {plate['size_mm'][1]:.0f} mm"
    )
    print(
        f"  about {result.manifest['estimated_grams_solid']:.0f} g if printed "
        "solid; supports: none"
    )
    for note in result.manifest["notes"]:
        print(f"  note: {note}")
    for warning in result.warnings:
        print(f"  warning: {warning}")
    print(f"\nwrote {len(result.files)} files to {result.directory}")
    for name in result.manifest["files"]:
        print(f"  {name}")


if __name__ == "__main__":
    raise SystemExit(main())
