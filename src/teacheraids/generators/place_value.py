"""Base-ten blocks: units, rods, flats and the thousand cube.

The set only teaches anything if the four pieces are *exactly* related -- ten
units laid in a line have to be the length of one rod, and ten rods have to
cover one flat.  So every piece is derived from a single `unit` dimension and
nothing here is allowed a nominal size of its own.

The thousand cube is the awkward one.  A hundred cubic centimetres of solid
plastic is not a thing anyone should print, and hollowing it leaves a top face
bridging a hundred millimetres.  The lattice option resolves that: cut the
grid through in all three directions and the cube becomes an open frame whose
longest unsupported span is one cell.
"""

from __future__ import annotations

from typing import Any

from .. import common, geom, presets
from ..generator import BuildResult, Generator, register
from ..mesh_io import PartSet
from ..options import Option, OptionSet, Report

PIECES = ("unit", "rod", "flat", "cube")

OPTIONS = OptionSet([
    Option("pieces", "unit,rod,flat,cube",
           "Which of the four to build, comma separated", kind="str",
           group="Content"),
    Option("base", 10,
           "How many units make the next piece up. Ten is the point of the "
           "set; five and four exist for teaching that place value is not "
           "about the number ten",
           kind="int", minimum=2, maximum=12, group="Content"),
    Option("quantity", "9,9,9,1",
           "How many of each of unit, rod, flat, cube to place on the plate",
           kind="str", group="Content"),

    Option("unit", presets.BASE_TEN_UNIT,
           "Edge of the single unit cube. Ten millimetres is what makes a "
           "thousand of them a litre, which is a lesson in itself",
           unit=" mm", minimum=4.0, maximum=25.0, group="Size"),
    Option("kerf", 0.2,
           "Shaved off every piece, so ten printed rods still fit across a "
           "printed flat", unit=" mm", minimum=0.0, maximum=1.0, group="Fit"),

    Option("grooves", True,
           "Engrave the unit divisions, so a rod visibly is ten units",
           kind="bool", group="Detail"),
    Option("groove_width", 1.0, "Width of an engraved division", unit=" mm",
           minimum=0.3, maximum=4.0, group="Detail"),
    Option("groove_depth", 0.7, "Depth of an engraved division", unit=" mm",
           minimum=0.2, maximum=3.0, group="Detail"),
    Option("cube_style", "lattice",
           "The thousand cube as an open lattice, or as a solid block",
           kind="choice", choices=("lattice", "solid"), group="Detail"),
    Option("lattice_rib", 2.4,
           "Thickness of the bars in a lattice cube", unit=" mm",
           minimum=1.0, maximum=8.0, group="Detail"),
    Option("chamfer", 0.4,
           "Break the edges of every piece by this much, so a bin of them "
           "does not shed sharp corners", unit=" mm", minimum=0.0,
           maximum=2.0, group="Detail"),
    common.material_option(),
])


class PlaceValueGenerator(Generator):
    key = "place-value"
    category = "math"
    title = "Base-ten place value blocks"
    summary = (
        "Units, rods, flats and the thousand cube, all derived from one unit "
        "dimension so ten of each really do make the next. The thousand cube "
        "prints as an open lattice instead of a kilogram of plastic."
    )
    tags = ("place value", "base ten", "math", "manipulative", "numeracy",
            "dienes blocks", "classroom", "teaching aid", "parametric")
    ages = "5-11"
    options = OPTIONS

    def build(self, opt: dict[str, Any]) -> BuildResult:
        report = Report()
        wanted = _parse_list(opt["pieces"], PIECES)
        quantity = _parse_quantity(opt["quantity"])
        unit = opt["unit"]
        base = opt["base"]

        common.check_features(report, unit, opt["groove_depth"],
                              opt["lattice_rib"] if "cube" in wanted else unit)

        builders = {
            "unit": self._unit, "rod": self._rod,
            "flat": self._flat, "cube": self._cube,
        }
        counts = {"unit": (1, "1"), "rod": (base, f"{base}"),
                  "flat": (base ** 2, f"{base}^2 = {base ** 2}"),
                  "cube": (base ** 3, f"{base}^3 = {base ** 3}")}

        parts = PartSet()
        for name in wanted:
            solid = builders[name](opt, report)
            value, label = counts[name]
            parts.add(f"{PIECES.index(name) + 1}_{name}", solid,
                      note=f"worth {label} units",
                      copies=max(quantity.get(name, 1), 1))

        common.check_small_parts(report, parts)
        if "cube" in wanted and opt["cube_style"] == "solid":
            report.warn(
                f"a solid {base}-cube is {(unit * base) ** 3 / 1000:.0f} cm3 "
                "of model. Slice it at low infill, or use cube_style=lattice "
                "and print an open frame instead."
            )

        return BuildResult(
            parts=parts,
            effective_options=opt,
            report=report,
            facts={
                "pieces": parts.total_copies,
                "unit_mm": unit,
                "base": base,
                "piece_mm": [unit, unit, unit],
                "outside_mm": [unit * base, unit * base, unit * base],
                "supports": "none",
            },
            highlights=[
                f"Everything comes off one number: a {unit:g} mm unit cube. "
                f"The rod is {base} of them, the flat is {base ** 2}, the "
                f"cube is {base ** 3}.",
                f"Base {base}."
                + (" Ten, so a thousand unit cubes are a litre and a "
                   "kilogram of water -- worth saying out loud."
                   if base == 10 else
                   f" Not ten, which is the point: place value works the same "
                   f"in base {base} and a child who can see that has "
                   "understood it."),
                f"Unit divisions engraved {opt['groove_depth']:.1f} mm deep, "
                "so a rod is visibly ten units and not just a long block."
                if opt["grooves"] else
                "Plain faces, for a set where the pieces are counted rather "
                "than read.",
                f"Every piece is {opt['kerf']:.2f} mm under nominal, so "
                f"{base} printed rods still lie across one printed flat.",
            ],
            teaching_notes=[
                "Exchange: ten units for a rod, ten rods for a flat. The "
                "whole of carrying and borrowing is that one move.",
                "Build a number, then say it: three flats, four rods and two "
                "units is 342, and you can see why.",
                "Volume: the thousand cube is a litre. Fill a milk carton "
                "with it and the number stops being abstract.",
            ],
            print_notes=[
                "Flat on the bed, no supports.",
                "The lattice cube's longest unsupported span is one cell "
                f"({unit:g} mm), which every printer bridges without help."
                if opt["cube_style"] == "lattice" and "cube" in wanted else
                "0.2 mm layers, 3 perimeters.",
                "Print each denomination in its own colour. Colour is how the "
                "exchange gets spotted across a table.",
                "Units are small: print them in a batch and expect to lose "
                "some down the back of a radiator.",
            ],
        )

    # -- the four pieces --------------------------------------------------

    def _block(self, opt, sizes) -> geom.Solid:
        """A rectangular piece with its edges broken and the kerf taken off."""
        kerf = opt["kerf"]
        width, depth, height = (s - kerf for s in sizes)
        if min(width, depth, height) <= 0:
            raise ValueError(
                f"kerf {kerf:.2f} mm is larger than a {min(sizes):.2f} mm "
                "piece. Reduce the kerf or raise the unit size."
            )
        chamfer = min(opt["chamfer"], width / 3.0, depth / 3.0, height / 3.0)
        if chamfer <= 0:
            return geom.box([width, depth, height])
        # Chamfer the four vertical edges with a profile, and the top and
        # bottom by intersecting with a solid that is drafted from both ends.
        profile = geom.polygon(
            geom.chamfered_rect(0, width, 0, depth, chamfer))
        body = geom.extrude(profile, height)
        cap_bottom = geom.extrude(profile, chamfer, taper=chamfer,
                                  step=chamfer).mirror([0, 0, 1]).translate(
                                      [0, 0, chamfer])
        cap_top = geom.extrude(profile, chamfer, taper=chamfer,
                               step=chamfer).translate([0, 0, height - chamfer])
        middle = geom.box([width, depth, max(height - 2 * chamfer, 1e-3)],
                          at=[0, 0, chamfer])
        return geom.intersection(body, geom.union([cap_bottom, middle, cap_top]))

    def _unit(self, opt, report: Report) -> geom.Solid:
        unit = opt["unit"]
        return self._block(opt, (unit, unit, unit))

    def _rod(self, opt, report: Report) -> geom.Solid:
        unit, base = opt["unit"], opt["base"]
        solid = self._block(opt, (unit, unit * base, unit))
        if opt["grooves"]:
            solid = geom.difference(solid, [
                self._groove_y(opt, unit, unit, index * unit)
                for index in range(1, base)
            ])
        return solid

    def _flat(self, opt, report: Report) -> geom.Solid:
        unit, base = opt["unit"], opt["base"]
        span = unit * base
        solid = self._block(opt, (span, span, unit))
        if opt["grooves"]:
            cuts = []
            for index in range(1, base):
                cuts.append(self._groove_y(opt, span, unit, index * unit))
                cuts.append(self._groove_x(opt, span, unit, index * unit))
            solid = geom.difference(solid, cuts)
        return solid

    def _cube(self, opt, report: Report) -> geom.Solid:
        unit, base = opt["unit"], opt["base"]
        span = unit * base
        solid = self._block(opt, (span, span, span))
        if opt["cube_style"] == "solid":
            if opt["grooves"]:
                cuts = []
                for index in range(1, base):
                    cuts.append(self._groove_y(opt, span, span, index * unit))
                    cuts.append(self._groove_x(opt, span, span, index * unit))
                solid = geom.difference(solid, cuts)
            return solid

        rib = opt["lattice_rib"]
        window = unit - rib
        if window <= 0.8:
            raise ValueError(
                f"a {rib:.1f} mm rib in a {unit:g} mm cell leaves a "
                f"{window:.1f} mm window. Thin the rib or grow the unit."
            )
        cutters = []
        for row in range(base):
            for column in range(base):
                a = rib / 2.0 + row * unit
                b = rib / 2.0 + column * unit
                # One cutter per axis per cell: their intersection hollows the
                # inside, and what is left is the bars along every grid line.
                cutters.append(geom.box([span + 2, window, window],
                                        at=[-1, a, b]))
                cutters.append(geom.box([window, span + 2, window],
                                        at=[a, -1, b]))
                cutters.append(geom.box([window, window, span + 2],
                                        at=[a, b, -1]))
        solid = geom.difference(solid, cutters)
        if not geom.is_one_piece(solid):
            raise ValueError(
                "the lattice cube came apart. Thicken `lattice_rib`.")
        return solid

    def _groove_y(self, opt, width: float, height: float, at: float):
        """A cut across the piece at `at` along Y, on the top and both sides."""
        w = opt["groove_width"]
        d = opt["groove_depth"]
        return geom.union([
            geom.box([width + 2, w, d], at=[-1, at - w / 2, height - d]),
            geom.box([d, w, height + 2], at=[-1 + 1 - d, at - w / 2, -1]),
            geom.box([d, w, height + 2], at=[width - d, at - w / 2, -1]),
        ])

    def _groove_x(self, opt, depth: float, height: float, at: float):
        w = opt["groove_width"]
        d = opt["groove_depth"]
        return geom.union([
            geom.box([w, depth + 2, d], at=[at - w / 2, -1, height - d]),
            geom.box([w, d, height + 2], at=[at - w / 2, 0, -1]),
            geom.box([w, d, height + 2], at=[at - w / 2, depth - d, -1]),
        ])

    def slug(self, opt: dict[str, Any]) -> str:
        return (f"place-value_base{opt['base']}_{opt['unit']:g}mm"
                f"_{opt['cube_style']}")

    def listing_title(self, opt: dict[str, Any], result: BuildResult) -> str:
        return (f"Base-{opt['base']} place value blocks - {opt['unit']:g} mm "
                f"unit, {result.facts['pieces']} pieces")


def _parse_list(raw: str, allowed: tuple[str, ...]) -> list[str]:
    wanted = [c.strip().lower() for c in str(raw).split(",") if c.strip()]
    unknown = [c for c in wanted if c not in allowed]
    if unknown:
        raise ValueError(
            "pieces: " + ", ".join(unknown) + " is not one of "
            + ", ".join(allowed)
        )
    if not wanted:
        raise ValueError("pieces is empty; try unit,rod,flat,cube")
    return [name for name in allowed if name in wanted]


def _parse_quantity(raw: str) -> dict[str, int]:
    chunks = [c.strip() for c in str(raw).split(",") if c.strip()]
    if len(chunks) != len(PIECES):
        raise ValueError(
            f"quantity needs {len(PIECES)} numbers, one each for "
            + ", ".join(PIECES) + f"; got {len(chunks)}"
        )
    out = {}
    for name, chunk in zip(PIECES, chunks):
        try:
            value = int(chunk)
        except ValueError:
            raise ValueError(f"quantity: {chunk!r} is not a whole number") from None
        if not 0 < value <= 100:
            raise ValueError(f"quantity: {value} for {name} is outside 1..100")
        out[name] = value
    return out


register(PlaceValueGenerator())
