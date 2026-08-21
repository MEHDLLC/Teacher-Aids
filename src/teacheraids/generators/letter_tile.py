"""Letter and number tiles: the alphabet set this repo exists for.

One generator covers what a classroom actually wants, because the differences
between a letter-recognition tile, a spelling tile, a tracing card and a
magnetic board letter are all *settings* -- how thick the letter is, whether it
stands off the face or sinks into it, what is around it -- not different
objects.  Making them one generator with a `theme` means a school can print a
matched set where the tracing cards and the spelling tiles are the same
letterforms at the same size, which is the entire point of a matched set.

A run builds a whole character set at once: one STL per tile and one 3MF with
every tile already laid out on the plate.
"""

from __future__ import annotations

from typing import Any

from .. import common, geom, patterns, presets, text
from ..generator import BuildResult, Generator, register
from ..mesh_io import PartSet
from ..options import Option, OptionSet, Report

THEMES = ("blocky", "patterned", "animal", "outline", "tracing", "window")

# What each theme means, as the defaults it fills in for any option left on
# "auto".  A theme is a starting point, never a lock: every one of these can be
# overridden on the command line, and the listing reports what was actually
# used rather than what the theme asked for.
THEME_DEFAULTS: dict[str, dict[str, Any]] = {
    "blocky": {
        "relief": "raised", "weight": 0.22, "pattern": "none",
        "corner": "round", "word": False, "guide_dot": False,
    },
    "patterned": {
        "relief": "raised", "weight": 0.18, "pattern": "honeycomb",
        "corner": "round", "word": False, "guide_dot": False,
    },
    "animal": {
        "relief": "raised", "weight": 0.20, "pattern": "none",
        "corner": "round", "word": True, "guide_dot": False,
    },
    "outline": {
        "relief": "raised", "weight": 0.26, "pattern": "none",
        "corner": "round", "word": False, "guide_dot": False,
    },
    "tracing": {
        "relief": "recessed", "weight": 0.20, "pattern": "none",
        "corner": "round", "word": False, "guide_dot": True,
    },
    "window": {
        "relief": "cut", "weight": 0.22, "pattern": "none",
        "corner": "round", "word": False, "guide_dot": False,
    },
}

OPTIONS = OptionSet([
    Option("charset", "uppercase",
           "Which characters to make. A named set (uppercase, lowercase, "
           "both-cases, digits, operators, vowels, consonants, "
           "numbers-and-operators), a range like A-M, or the literal "
           "characters themselves",
           kind="str", group="Content"),
    Option("max_tiles", 30,
           "Stop after this many tiles. A whole set is one run, and "
           "both-cases is fifty-two of them",
           kind="int", minimum=1, maximum=120, group="Content"),
    Option("theme", "blocky", "Which family of tile this is",
           kind="choice", choices=THEMES, group="Content"),
    Option("word", None,
           "Emboss a word for the letter under it (Bear for B)",
           kind="bool", group="Content", default_note="from the theme"),

    Option("tile_size", 40.0, "Tile width and height", unit=" mm",
           minimum=15.0, maximum=200.0, group="Size"),
    Option("thickness", 4.0, "Tile thickness", unit=" mm", minimum=1.0,
           maximum=30.0, group="Size"),
    Option("cap_height", None, "Letter height", unit=" mm", minimum=4.0,
           maximum=180.0, group="Size",
           default_note="62% of the tile, or 52% when a word is on it"),
    Option("weight", None,
           "How thick the letter's strokes are, as a fraction of its height",
           minimum=0.05, maximum=0.40, group="Size",
           default_note="from the theme"),

    Option("relief", None, "Whether the letter stands off, sinks in, or cuts through",
           kind="choice", choices=common.RELIEF_MODES, group="Letter",
           default_note="from the theme"),
    Option("relief_depth", 1.6, "How far the letter stands off or sinks in",
           unit=" mm", minimum=0.2, maximum=12.0, group="Letter"),
    Option("draft", 0.35,
           "How much narrower the top of a raised letter is than its base, "
           "per side. Loses the flare at the letter's foot and makes it "
           "pleasanter under a fingertip",
           unit=" mm", minimum=0.0, maximum=2.0, group="Letter"),
    Option("outline_width", 2.2,
           "Rim thickness when the outline theme hollows the letter out",
           unit=" mm", minimum=0.6, maximum=8.0, group="Letter"),
    Option("bridge", 3.0,
           "Width of the tabs that hold the middle of an O in place when the "
           "letter is cut through", unit=" mm", minimum=0.0, maximum=10.0,
           group="Letter"),
    Option("guide_dot", None,
           "Mark where a pencil starts the letter, for tracing",
           kind="bool", group="Letter", default_note="from the theme"),
    Option("orientation_bar", False,
           "A raised bar along the bottom edge, so b, d, p and q cannot be "
           "picked up the wrong way round",
           kind="bool", group="Letter"),

    Option("pattern", None, "Texture engraved into the face around the letter",
           kind="choice", choices=("none",) + patterns.PATTERNS,
           group="Pattern", default_note="from the theme"),
    Option("pattern_cell", None, "How big one repeat of the pattern is",
           unit=" mm", minimum=2.0, maximum=60.0, group="Pattern",
           default_note="per pattern"),
    Option("pattern_rib", None, "Gap between pattern cells", unit=" mm",
           minimum=0.5, maximum=20.0, group="Pattern", default_note="per pattern"),
    Option("pattern_depth", 0.6, "How deep the pattern is engraved",
           unit=" mm", minimum=0.2, maximum=4.0, group="Pattern"),

    *common.corner_options(5.0),
    Option("margin", 3.0, "Clear border kept around everything on the face",
           unit=" mm", minimum=0.0, maximum=30.0, group="Shape"),

    *common.magnet_options(),
    Option("hole", 0.0,
           "Diameter of a hole through the corner, for a ring or a lace. "
           "Zero leaves it out", unit=" mm", minimum=0.0, maximum=20.0,
           group="Mounting"),

    common.material_option(),
])


class LetterTileGenerator(Generator):
    key = "letter-tile"
    category = "alphabet"
    title = "Letter and number tiles"
    summary = (
        "A whole character set as printable tiles, in six themes -- chunky "
        "blocks, textured faces, animal tiles, hollow outlines, finger-tracing "
        "cards and cut-through windows."
    )
    tags = ("alphabet", "letters", "literacy", "phonics", "montessori",
            "classroom", "teaching aid", "parametric", "3d printing")
    ages = "3-8"
    options = OPTIONS

    def build(self, opt: dict[str, Any]) -> BuildResult:
        report = Report()
        opt = _apply_theme(opt)

        characters = text.expand_charset(opt["charset"])
        dropped = ""
        if len(characters) > opt["max_tiles"]:
            dropped = characters[opt["max_tiles"]:]
            characters = characters[: opt["max_tiles"]]
            report.warn(
                f"charset {opt['charset']!r} is {len(characters) + len(dropped)} "
                f"characters and max_tiles is {opt['max_tiles']}, so this set "
                f"stops at {characters[-1]!r} and leaves out "
                f"{_quote(dropped)}. Raise max_tiles to build the rest."
            )

        size = opt["tile_size"]
        thickness = opt["thickness"]
        cap = opt["cap_height"] or (
            size * (0.52 if opt["word"] else 0.62))
        weight_mm = cap * opt["weight"]

        face = size - 2.0 * opt["margin"]
        if cap > face:
            cap = face
            report.warn(
                f"the letter was taller than the {face:.0f} mm of clear face "
                f"a {size:.0f} mm tile has, so it was reduced to {cap:.1f} mm."
            )
            weight_mm = cap * opt["weight"]

        common.check_features(report, thickness, opt["relief_depth"],
                              weight_mm, "letter")
        if opt["relief"] == "cut" and opt["bridge"] <= 0:
            report.warn(
                "cutting the letter through with no bridges drops the middle "
                "of every O, A, B and 8 out of the tile as a loose disc."
            )
        if opt["relief"] == "recessed" and opt["relief_depth"] >= thickness:
            report.warn(
                f"a {opt['relief_depth']:.1f} mm groove in a "
                f"{thickness:.1f} mm tile has no floor left under it."
            )

        parts = PartSet()
        for char in characters:
            solid, note = self._one_tile(char, opt, cap, weight_mm, report)
            parts.add(_part_name(char), solid, note=note)

        common.check_small_parts(report, parts)

        facts = {
            "characters": " ".join(characters),
            "pieces": len(characters),
            "piece_mm": list(parts.parts[0].size) if len(parts) else [0, 0, 0],
            "cap_height_mm": round(cap, 2),
            "stroke_mm": round(weight_mm, 2),
            "relief_mm": opt["relief_depth"],
            "theme": opt["theme"],
            "supports": "none",
        }
        if dropped:
            facts["characters_dropped"] = " ".join(dropped)

        return BuildResult(
            parts=parts,
            effective_options=opt,
            report=report,
            facts=facts,
            highlights=self._highlights(opt, characters, cap, weight_mm),
            teaching_notes=_TEACHING[opt["theme"]],
            print_notes=self._print_notes(opt),
        )

    # -- geometry ---------------------------------------------------------

    def _one_tile(self, char: str, opt: dict[str, Any], cap: float,
                  weight_mm: float, report: Report):
        size = opt["tile_size"]
        thickness = opt["thickness"]
        weight_units = opt["weight"] * 100.0

        body = common.plate(size, size, thickness, opt["corner"],
                            opt["corner_size"])

        # The letter sits on a baseline shared by the whole set, so a row of
        # tiles spelling a word lines up. Centring each glyph's own ink would
        # put the crossbar of an "e" where the top of an "l" is.
        glyph = text.line_shape(char, cap, weight_units, align="centre")
        x0, _, x1, _ = geom.shape_bounds(glyph)
        baseline = -cap / 2.0 + (cap * 0.16 if opt["word"] else 0.0)
        glyph = glyph.translate([-(x0 + x1) / 2.0, baseline])

        if opt["theme"] == "outline":
            glyph = text.outline(glyph, opt["outline_width"])

        cutters = []
        additions = []

        pattern_shape = self._pattern(opt, glyph, size)
        if not pattern_shape.is_empty():
            cutters.append(geom.extrude(
                pattern_shape, opt["pattern_depth"] + 0.01,
                at_z=thickness - opt["pattern_depth"]))

        ink = glyph
        if opt["relief"] == "cut":
            ink = text.stencil_cut(glyph, opt["bridge"])

        word = ""
        if opt["word"]:
            word = self._word_shape(char, opt, cap, size, thickness,
                                    additions, cutters, report)

        if opt["orientation_bar"]:
            bar_h = max(size * 0.055, 1.6)
            bar = geom.rect(size - 2.0 * opt["corner_size"], bar_h).translate(
                [0.0, -size / 2.0 + opt["margin"] * 0.6 + bar_h / 2.0])
            additions.append(
                geom.extrude(bar, opt["relief_depth"] * 0.6, at_z=thickness,
                             taper=opt["draft"] * 0.5))

        solid = geom.difference(geom.union([body] + additions), cutters)
        solid = common.face_relief(solid, ink, opt["relief"],
                                   opt["relief_depth"], thickness,
                                   opt["draft"] if opt["relief"] == "raised"
                                   else 0.0)

        # The start dot goes on last, because it has to sit on the letter
        # rather than under it. Added before the groove was cut it would be
        # the first thing the groove removed, and the tile would come off the
        # bed with a loose pip in it.
        if opt["guide_dot"] and opt["relief"] in ("raised", "recessed"):
            spot = text.start_point(char, cap, weight_units)
            if spot is not None:
                at = (spot[0] - (x0 + x1) / 2.0, spot[1] + baseline)
                dot = geom.circle(max(weight_mm * 0.42, 0.8)).translate(list(at))
                if opt["relief"] == "recessed":
                    # A pip standing up out of the groove floor: a finger
                    # tracing the groove meets it and knows to start there.
                    floor = thickness - opt["relief_depth"]
                    solid = geom.union([
                        solid,
                        geom.extrude(dot, opt["relief_depth"] * 0.65,
                                     at_z=floor),
                    ])
                else:
                    # A dimple in the top of a raised letter, which reads the
                    # same way round without adding anything to catch on.
                    top = thickness + opt["relief_depth"]
                    sink = min(opt["relief_depth"] * 0.5, 0.8)
                    solid = geom.difference(
                        solid, geom.extrude(dot, sink + 0.01, at_z=top - sink))

        if opt["hole"] > 0:
            inset = opt["hole"] / 2.0 + max(opt["margin"], 2.0)
            solid = geom.difference(solid, common.hang_hole(
                opt["hole"], thickness,
                (-size / 2.0 + inset, size / 2.0 - inset)))

        if opt["magnet"] != "none":
            if opt["relief"] == "cut":
                report.warn(
                    "a magnet pocket in the back of a cut-through tile would "
                    "break into the letter, so it was left out. Use the "
                    "blocky or patterned theme for board magnets."
                )
            else:
                solid, _ = common.apply_magnet(
                    solid, opt["magnet"], thickness, opt["magnet_clearance"],
                    report)

        if not geom.is_one_piece(solid):
            raise ValueError(
                f"the tile for {char!r} came out as "
                f"{len(solid.decompose())} loose pieces. Widen `bridge`, or "
                "reduce `relief_depth` so the cut does not sever the tile."
            )

        note = f"the letter {char}"
        if word:
            note += f", with {word} under it"
        return solid, note

    def _pattern(self, opt: dict[str, Any], glyph, size: float):
        if opt["pattern"] == "none":
            return geom.empty_shape()
        half = size / 2.0 - opt["margin"]
        profiles = patterns.tile(
            opt["pattern"], (-half, -half, half, half),
            opt["pattern_cell"], opt["pattern_rib"])
        if not profiles:
            return geom.empty_shape()
        field = geom.shape_union([geom.polygon(p) for p in profiles])
        # Keep the texture off the letter itself: a honeycomb running through
        # the middle of a B makes it unreadable, which is the opposite of what
        # a letter tile is for.
        keep_clear = glyph.offset(max(opt["pattern_rib"] * 0.6, 1.2),
                                 text.geom_join(), 2.0, 16)
        return field - keep_clear

    def _word_shape(self, char: str, opt: dict[str, Any], cap: float,
                    size: float, thickness: float, additions, cutters,
                    report: Report) -> str:
        word = _word_for(char)
        if not word:
            return ""
        available = size - 2.0 * opt["margin"]
        shape, used_cap = text.fitted_line(
            word.upper(), available, cap * 0.30, opt["weight"] * 100.0,
            min_cap=2.5)
        if shape.is_empty():
            return ""
        shape = shape.translate([0.0, -size / 2.0 + opt["margin"] + used_cap * 0.4])
        depth = min(opt["relief_depth"] * 0.7, 1.0)
        if opt["relief"] == "recessed":
            cutters.append(
                geom.extrude(shape, depth + 0.01, at_z=thickness - depth))
        else:
            additions.append(
                geom.extrude(shape, depth, at_z=thickness,
                             taper=min(opt["draft"], depth * 0.4)))
        return word

    # -- copy -------------------------------------------------------------

    def _highlights(self, opt, characters, cap, weight_mm) -> list[str]:
        out = [
            f"{len(characters)} tiles: {text.describe_charset(characters)}.",
            f"{opt['tile_size']:.0f} mm square, {opt['thickness']:.1f} mm "
            f"thick, with a {cap:.0f} mm letter in {weight_mm:.1f} mm strokes.",
            _THEME_BLURB[opt["theme"]],
        ]
        if opt["pattern"] != "none":
            out.append(
                patterns.describe(opt["pattern"], opt["pattern_cell"],
                                  opt["pattern_rib"])
                + f", engraved {opt['pattern_depth']:.1f} mm into the face "
                "and held clear of the letter."
            )
        if opt["orientation_bar"]:
            out.append(
                "A raised bar along the bottom edge, so b and d cannot be "
                "picked up as each other."
            )
        if opt["magnet"] != "none":
            diameter, depth = presets.MAGNET_SIZES[opt["magnet"]]
            out.append(
                f"A {diameter:.0f} x {depth:.0f} mm magnet pocket in the back, "
                "for the whiteboard."
            )
        if opt["hole"] > 0:
            out.append(
                f"A {opt['hole']:.0f} mm hole in the corner for a ring or a "
                "lace."
            )
        return out

    def _print_notes(self, opt) -> list[str]:
        notes = [
            "Flat on the bed, no supports. 0.2 mm layers is plenty.",
            "Print the tile and the letter in two colours by adding a filament "
            f"change at {opt['thickness']:.1f} mm -- the letter starts exactly "
            "there, so any slicer's colour-change-at-height does it with no "
            "extra work."
            if opt["relief"] == "raised" else
            "The letter is sunk into the face, so a contrasting colour can be "
            "wiped or brushed into the groove after printing.",
        ]
        if opt["relief"] == "cut":
            notes.append(
                f"The {opt['bridge']:.0f} mm bridges holding the middle of O, "
                "A, B, D, P, Q, R, 0, 4, 6, 8 and 9 in place are part of the "
                "model. Cutting them off after printing loses the piece."
            )
        if opt["theme"] == "tracing":
            notes.append(
                "Print in a light colour: a groove reads by shadow, and a "
                "black tile hides it."
            )
        notes.append(
            "Four perimeters and 15% infill. These get dropped, stood on and "
            "posted through gaps in furniture."
        )
        return notes

    def slug(self, opt: dict[str, Any]) -> str:
        charset = str(opt["charset"]).lower().replace(" ", "")
        safe = "".join(c if c.isalnum() or c == "-" else "x" for c in charset)
        return (f"letter-tile_{safe[:16]}_{opt['theme']}"
                f"_{opt['tile_size']:g}mm")

    def listing_title(self, opt: dict[str, Any], result: BuildResult) -> str:
        count = result.facts["pieces"]
        what = text.describe_charset(result.facts["characters"].replace(" ", ""))
        return (f"{_THEME_TITLE[opt['theme']]} - {count} tiles, {what}, "
                f"{opt['tile_size']:.0f} mm")

    def listing_body(self, opt: dict[str, Any], result: BuildResult) -> list[str]:
        return [
            _THEME_BLURB[opt["theme"]],
            "",
            "Every tile in the set is the same size, the same thickness and "
            "the same letterforms on the same baseline, so they line up when "
            "a child spells with them and stack when they are put away.",
        ]


_THEME_TITLE = {
    "blocky": "Chunky letter tiles",
    "patterned": "Textured letter tiles",
    "animal": "Animal alphabet tiles",
    "outline": "Outline letter tiles",
    "tracing": "Finger-tracing letter cards",
    "window": "Cut-through letter tiles",
}

_THEME_BLURB = {
    "blocky": (
        "Heavy strokes and rounded corners: the letter reads across a "
        "classroom and the tile survives being dropped on a hard floor."
    ),
    "patterned": (
        "The face is textured around the letter, so the letter is what your "
        "fingers find first. The texture stops short of the letter itself, "
        "which keeps it readable."
    ),
    "animal": (
        "Each letter carries the animal that starts with its sound, embossed "
        "underneath: B is for Bear, not for Bee-then-a-picture-of-something."
    ),
    "outline": (
        "The letter is hollow -- a raised rim with an open middle. Fill it "
        "with dough, beads, chalk or a finger, or use it as a shape to draw "
        "around."
    ),
    "tracing": (
        "The letter is a groove, wide enough for a fingertip, with a raised "
        "dot where the pencil starts. Trace it, then write it."
    ),
    "window": (
        "The letter is cut clean through the tile. Hold it to the light, "
        "spray-chalk through it, or press it into dough."
    ),
}

_TEACHING = {
    "blocky": [
        "Letter recognition: spread them face up and name them.",
        "Spelling: lay them in a row to build a word, then take one away.",
        "Matching: print the capitals and the lower case and pair them off.",
    ],
    "patterned": [
        "Sorting by feel: put a set in a bag and identify letters by touch.",
        "The texture gives a child something to talk about that is not the "
        "letter, which is often how a reluctant one gets started.",
    ],
    "animal": [
        "Initial sounds: match the letter to the animal, then to a picture.",
        "X carries Fox rather than a word starting with X, which is how every "
        "alphabet chart handles it -- worth saying out loud to the class.",
    ],
    "outline": [
        "Fill with play dough to make a solid letter, then pull it out.",
        "Trace around the outside with a pencil to write the letter large.",
    ],
    "tracing": [
        "Trace with a finger before writing with a pencil: the groove stops "
        "the finger wandering, and the dot settles which end to start.",
        "Works with eyes closed, which is the point -- the shape goes in "
        "through the hand.",
    ],
    "window": [
        "Chalk or paint through the opening to print the letter on paper.",
        "Press into dough or sand to leave the letter behind.",
    ],
}


def _apply_theme(opt: dict[str, Any]) -> dict[str, Any]:
    """Fill in every option left on auto from the chosen theme."""
    resolved = dict(opt)
    for name, value in THEME_DEFAULTS[opt["theme"]].items():
        if resolved.get(name) is None:
            resolved[name] = value
    if resolved.get("pattern_cell") is None:
        resolved["pattern_cell"] = patterns.default_cell(resolved["pattern"])
    if resolved.get("pattern_rib") is None:
        resolved["pattern_rib"] = patterns.default_rib(resolved["pattern"])
    return resolved


def _word_for(char: str) -> str:
    from .. import font
    return font.word_for(char)


def _part_name(char: str) -> str:
    """A file name for a tile.

    Case matters and file systems do not always agree that it does, so an
    upper-case A and a lower-case a are spelled out rather than left to
    collide on a case-insensitive disk.
    """
    if char.isalpha():
        return f"tile_{char.upper()}_{'upper' if char.isupper() else 'lower'}"
    if char.isdigit():
        return f"tile_{char}"
    names = {
        "+": "plus", "−": "minus", "-": "hyphen", "×": "times", "÷": "divide",
        "=": "equals", "<": "less", ">": "greater", ".": "dot",
        ",": "comma", "!": "bang", "?": "question", "'": "apostrophe",
        '"': "quote", ":": "colon", "/": "slash", "%": "percent",
        "&": "ampersand", "#": "hash", "*": "star", "_": "underscore",
        "(": "open-paren", ")": "close-paren", " ": "space",
        "≤": "at-most", "≥": "at-least",
    }
    return "tile_" + names.get(char, f"u{ord(char):04x}")


def _quote(chars: str) -> str:
    return " ".join(chars)


register(LetterTileGenerator())
