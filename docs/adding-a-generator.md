# Adding a generator

A generator declares its options once and implements `build`. Everything else —
CLI flags, validation, STL and 3MF export, previews, the listing, the manifest —
comes from that one declaration.

## The shape of one

```python
# src/teacheraids/generators/number_line.py
from .. import common, geom, text
from ..generator import BuildResult, Generator, register
from ..mesh_io import PartSet
from ..options import Option, OptionSet, Report


OPTIONS = OptionSet([
    Option("length", 300.0, "Overall length", unit=" mm", minimum=80.0,
           maximum=600.0, group="Size"),
    Option("steps", 10, "How many divisions", kind="int", minimum=2,
           maximum=100, group="Layout"),
    Option("label", True, "Number every division", kind="bool",
           group="Layout"),
    common.material_option(),
])


class NumberLineGenerator(Generator):
    key = "number-line"
    category = "math"
    title = "Number line"
    summary = "One sentence a teacher would recognise the product from."
    tags = ("number line", "counting", "math", "manipulative", "classroom")
    ages = "5-9"
    options = OPTIONS

    def build(self, opt):
        report = Report()
        parts = PartSet()
        body = common.plate(opt["length"], 30.0, 4.0)
        parts.add("line", body, note="the whole line")
        return BuildResult(
            parts=parts,
            effective_options=opt,
            report=report,
            facts={"outside_mm": [opt["length"], 30.0, 4.0],
                   "pieces": 1, "supports": "none"},
            highlights=["What makes it worth printing"],
            teaching_notes=["What to do with it in a lesson"],
            print_notes=["How to print it"],
        )

    def slug(self, opt):
        return f"number-line_{opt['length']:g}mm_{opt['steps']}"


register(NumberLineGenerator())
```

Then three things, each of which has a test that fails if you forget it:

1. Import it in `src/teacheraids/generators/__init__.py` — importing the module
   is what registers it.
2. Add at least one entry to its category's catalogue.
   `tests/test_catalogue.py` fails if a generator appears in no catalogue.
3. Add its module to the `push: paths:` filter in its category's workflow, so
   changing it rebuilds that category. `tests/test_workflows.py` reads those
   filters back and compares them against the registry, because a missing line
   there fails silently: the category simply stops rebuilding, and nothing goes
   red to tell you.

`tests/test_generators.py` then builds every registered generator at its
defaults and holds it to the same bar as the rest.

## What the framework gives you

- **Options.** `kind` is one of `float`, `int`, `bool`, `choice`, `str`.
  `minimum`/`maximum` are enforced with a message naming the limit. A `default`
  of `None` means "filled in from something else", and then `default_note` has
  to say what from. `group` becomes the CLI help section and `listed=False`
  keeps a knob out of the customer-facing options table.
- **Geometry.** `teacheraids.geom` wraps manifold3d, so every boolean returns a
  watertight solid. Work in 2-D as long as you can: `rounded_rect`, `sector`,
  `regular_polygon_by_edge`, `capsule`, `stroke`, then one `extrude` at the end.
  `extrude(..., taper=)` drafts the walls and will quietly reduce the draft
  rather than let a profile pinch.
- **Shared pieces.** `common.plate`, `common.face_relief` (raised, recessed, cut
  or flat from one option), `common.apply_magnet`, `common.hang_hole`,
  `common.check_features`, `common.check_small_parts`.
- **Text.** `text.line_shape`, `text.fitted_line` (the largest cap height that
  fits a given width), `text.block_shape`, `text.stencil_cut` (bridges the
  counters so nothing falls out). See [font.md](font.md).
- **Polyhedra.** `polyhedra.build(name, r)` for the five Platonic solids with
  faces, edges, dihedral angles and a `frame()`; `polyhedra.from_points` for
  anything else convex.
- **Export, previews, copy, manifest.** All handled by the runner.

## What to hold yourself to

The tests in `tests/` are the standard, not decoration. The ones that earn their
keep are the ones checking things an STL cannot show you.

- **Is it one connected solid?** Assert it inside `build`, not just in a test.
- **Does the thing it holds actually fit?** Model it, subtract it from the part,
  and assert nothing is left over.
- **Is it actually held?** Zero overlap alone also describes an object floating
  in a hole. Grow it by the clearance and assert it now collides.
- **Do the relationships hold?** Six triangles have to have exactly the area of
  one hexagon; ten rods have to be the length of one flat. Assert the
  relationship, not the number.
- **Is the mesh one a slicer will take?** `geom.edge_manifold` catches a solid
  that touches itself along an edge, which manifold3d calls valid.
- **Say what you do not know.** If a dimension is an estimate rather than a
  specification, record it as one — `facts["fit_confidence"]` — and let it
  surface in the listing.

## Adding a category

Categories are declared in `src/teacheraids/generator.py`. A new one needs:

1. an entry in `CATEGORIES` and `CATEGORY_TITLES`,
2. a `catalogues/<name>.json` with a `release` block,
3. a `.github/workflows/<name>.yml` copied from any of the existing five — they
   differ only in the category they pass to `build-category.yml` and the paths
   they watch,
4. the category added to the smoke-build loop in `ci.yml`.

A category workflow watches its own catalogue and its own generators, so a
change to one generator rebuilds one category. It also watches
`src/teacheraids/*.py`, which is deliberately *not* narrowed: a change to
`font.py` redraws every letterform in the repo and a change to `geom.py` or
`mesh_io.py` changes every mesh, so those have to rebuild all five or the
published sets quietly go stale. The single `*` does not match a slash, so that
entry covers the top-level modules and not the generators directory.
