"""Turning a string into a 2-D profile you can extrude, sink or cut.

Everything here works on `geom.Shape` (a manifold3d cross-section), not on
solids, because a letter is wanted in three different ways and only the last
step differs:

    raised     extrude the profile up off the tile face
    recessed   extrude it and subtract -- a groove to trace with a finger
    cut        extrude it through the whole plate -- a stencil

The font is a skeleton (see `font.py`); this module inflates it to a weight,
scales it to a cap height, lays glyphs out on a baseline, and knows how to
fit a name into the space a name plate actually has.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from . import font, geom
from .geom import Point2, Shape

# How wide a stencil bridge is by default, in millimetres of finished part.
DEFAULT_BRIDGE = 3.0


class TextError(ValueError):
    """Raised when a string cannot be set: no glyph, or no room."""


@dataclass(frozen=True)
class TextMetrics:
    """What a set line of text measures, before it is drawn."""

    width: float           # advance width, including tracking between glyphs
    cap_height: float
    top: float             # highest ink above the baseline
    bottom: float          # lowest ink below the baseline (negative)
    glyph_count: int

    @property
    def height(self) -> float:
        return self.top - self.bottom


def _flatten_stroke(items: Sequence[font.Item]) -> list[Point2]:
    """Resolve one stroke's mixed points and arcs into a polyline."""
    points: list[Point2] = []
    for item in items:
        if isinstance(item, tuple) and item and item[0] == "arc":
            _, cx, cy, rx, ry, a0, a1 = item
            arc = geom.arc_points(cx, cy, rx, ry, a0, a1)
            # An arc that continues a stroke starts where the last point left
            # off; dropping the duplicate keeps zero-length capsules out.
            if points and _close(points[-1], arc[0]):
                arc = arc[1:]
            points.extend(arc)
        else:
            point = (float(item[0]), float(item[1]))
            if not points or not _close(points[-1], point):
                points.append(point)
    return points


def _close(a: Point2, b: Point2) -> bool:
    return abs(a[0] - b[0]) < 1e-9 and abs(a[1] - b[1]) < 1e-9


def glyph_shape(char: str, cap_height: float = font.CAP_HEIGHT,
                weight: float = font.DEFAULT_WEIGHT) -> Shape:
    """One character, baseline on y=0, left side bearing at x=0.

    `weight` is given on the font's own 100-unit body, so it means the same
    proportion of the letter whatever `cap_height` is.
    """
    _, strokes = font.glyph(char)
    scale = cap_height / font.CAP_HEIGHT
    pen = weight * scale
    if pen <= 0:
        raise TextError("weight must be positive")
    drawn = [
        geom.stroke([(x * scale, y * scale) for x, y in _flatten_stroke(s)], pen)
        for s in strokes
    ]
    return geom.shape_union(drawn)


def advance(char: str, cap_height: float = font.CAP_HEIGHT,
            weight: float = font.DEFAULT_WEIGHT) -> float:
    """How far the pen moves after drawing `char`.

    The font's advances are skeleton-to-skeleton, so a heavy weight has to add
    its own thickness back or the letters overlap.
    """
    width, _ = font.glyph(char)
    scale = cap_height / font.CAP_HEIGHT
    return width * scale + weight * scale


def measure(text: str, cap_height: float = font.CAP_HEIGHT,
            weight: float = font.DEFAULT_WEIGHT,
            tracking: float = font.DEFAULT_TRACKING) -> TextMetrics:
    """Set width and vertical extent, without building any geometry."""
    if not text:
        return TextMetrics(0.0, cap_height, 0.0, 0.0, 0)
    unknown = font.missing(text)
    if unknown:
        raise TextError(
            "no glyph for " + ", ".join(repr(c) for c in unknown)
            + ". This font draws: " + " ".join(sorted(font.GLYPHS))
        )
    scale = cap_height / font.CAP_HEIGHT
    total = sum(advance(c, cap_height, weight) for c in text)
    total += tracking * scale * (len(text) - 1)

    # Vertical extent from the metrics, not from the geometry: a line of "ooo"
    # is x-height tall, but a plate laid out from that would jump as soon as
    # someone typed a capital, and every tile in a set has to be the same.
    half_pen = weight * scale / 2.0
    has_descender = any(c in "gjpqyQ,()" for c in text)
    top = font.ASCENDER * scale + half_pen
    bottom = (font.DESCENDER * scale if has_descender else 0.0) - half_pen
    return TextMetrics(total, cap_height, top, bottom, len(text))


def line_shape(text: str, cap_height: float = font.CAP_HEIGHT,
               weight: float = font.DEFAULT_WEIGHT,
               tracking: float = font.DEFAULT_TRACKING,
               align: str = "centre") -> Shape:
    """One line of text as a profile.

    Returned centred on the origin horizontally when `align` is "centre", so a
    caller can drop it onto the middle of a tile without measuring anything;
    "left" puts the first glyph's origin at x=0.  Vertically the baseline is
    always y=0, which is what lets several lines share one coordinate system.
    """
    if not text:
        return geom.empty_shape()
    metrics = measure(text, cap_height, weight, tracking)
    scale = cap_height / font.CAP_HEIGHT
    gap = tracking * scale

    pieces: list[Shape] = []
    cursor = 0.0
    for char in text:
        step = advance(char, cap_height, weight)
        if char != " ":
            # Half the weight of side bearing on each side, so the ink of a
            # glyph sits inside the advance its skeleton was drawn for.
            pieces.append(
                glyph_shape(char, cap_height, weight).translate(
                    [cursor + weight * scale / 2.0, 0.0])
            )
        cursor += step + gap

    shape = geom.shape_union(pieces)
    if shape.is_empty():
        return shape
    if align == "centre":
        return shape.translate([-metrics.width / 2.0, 0.0])
    if align == "right":
        return shape.translate([-metrics.width, 0.0])
    if align != "left":
        raise TextError(f"unknown align {align!r}; use left, centre or right")
    return shape


def block_shape(lines: Sequence[str], cap_height: float = font.CAP_HEIGHT,
                weight: float = font.DEFAULT_WEIGHT,
                tracking: float = font.DEFAULT_TRACKING,
                leading: float = 1.45, align: str = "centre") -> Shape:
    """Several lines, centred as a block on the origin in both directions."""
    rows = [line for line in lines]
    if not rows:
        return geom.empty_shape()
    step = cap_height * leading
    drawn = [
        line_shape(row, cap_height, weight, tracking, align).translate(
            [0.0, -index * step])
        for index, row in enumerate(rows)
    ]
    block = geom.shape_union(drawn)
    if block.is_empty():
        return block
    x0, y0, x1, y1 = geom.shape_bounds(block)
    return block.translate([0.0, -(y0 + y1) / 2.0])


def fit_cap_height(text: str, max_width: float, max_cap: float,
                   weight: float = font.DEFAULT_WEIGHT,
                   tracking: float = font.DEFAULT_TRACKING,
                   min_cap: float = 3.0) -> float:
    """The largest cap height at which `text` still fits `max_width`.

    Width scales linearly with cap height, so this is one division rather than
    a search.  Names on a desk plate are the reason it exists: "Al" and
    "Konstantina" have to come off the same generator at the same plate size.
    """
    if not text:
        return max_cap
    reference = measure(text, 100.0, weight, tracking).width
    if reference <= 0:
        return max_cap
    fitted = 100.0 * max_width / reference
    return max(min(fitted, max_cap), min_cap)


def fitted_line(text: str, max_width: float, max_cap: float,
                weight: float = font.DEFAULT_WEIGHT,
                tracking: float = font.DEFAULT_TRACKING,
                min_cap: float = 3.0, align: str = "centre"
                ) -> tuple[Shape, float]:
    """`line_shape` at whatever cap height fits, and that cap height."""
    cap = fit_cap_height(text, max_width, max_cap, weight, tracking, min_cap)
    return line_shape(text, cap, weight, tracking, align), cap


# ---------------------------------------------------------------------------
# outlines and stencils
# ---------------------------------------------------------------------------


def outline(shape: Shape, thickness: float) -> Shape:
    """The rim of a shape: what is left after hollowing it out.

    Used for the outline theme, where a child colours or fills the letter in,
    and for stencil frames.
    """
    if thickness <= 0 or shape.is_empty():
        return geom.empty_shape()
    inner = shape.offset(-thickness, geom_join(), 2.0, 24)
    if inner.is_empty():
        return shape
    return shape - inner


def geom_join():
    import manifold3d as m3
    return m3.JoinType.Round


def counters(shape: Shape) -> list[list[Point2]]:
    """The enclosed holes in a profile -- the middle of an O, both eyes of a B.

    manifold hands back outer contours wound counter-clockwise and holes wound
    clockwise, so the sign of the area is the test.
    """
    holes = []
    for contour in shape.to_polygons():
        points = [(float(x), float(y)) for x, y in contour]
        if len(points) >= 3 and geom.signed_area(points) < 0:
            holes.append(points)
    return holes


def bridges(shape: Shape, width: float = DEFAULT_BRIDGE) -> Shape:
    """Tabs that stop a stencil's counters from falling out.

    Every enclosed hole gets a channel cut from its centre straight up and out
    past the top of the glyph.  Upwards rather than sideways because a stroke
    is at its thinnest where it is horizontal, so a vertical channel crosses
    the least ink; and a channel that runs from a lower counter into an upper
    one (the two eyes of a B, of an 8) is not a problem, because the upper
    one's channel carries on out to the plate and the chain holds.
    """
    holes = counters(shape)
    if not holes or width <= 0:
        return geom.empty_shape()
    _, _, _, top = geom.shape_bounds(shape)
    cutters = []
    for hole in holes:
        xs = [p[0] for p in hole]
        ys = [p[1] for p in hole]
        centre_x = (min(xs) + max(xs)) / 2.0
        start_y = (min(ys) + max(ys)) / 2.0
        cutters.append(
            geom.rect(width, top - start_y + width, center=False).translate(
                [centre_x - width / 2.0, start_y])
        )
    return geom.shape_union(cutters)


def fill_slivers(shape: Shape, smallest: float) -> Shape:
    """Fill in any counter too narrow to be worth keeping.

    A stroked letter picks up crescents where two strokes nearly meet -- the
    half-millimetre sliver between the bowl and the tail of a `g` is the
    clearest -- and they are drawing artefacts, not features. In a stencil
    they are worse than useless: too narrow to bridge, too narrow to get a
    pencil into, and a loose splinter of plastic on the bed. Filling them
    leaves the letter looking exactly the same and the stencil printable.
    """
    if smallest <= 0 or shape.is_empty():
        return shape
    patches = []
    for hole in counters(shape):
        xs = [p[0] for p in hole]
        ys = [p[1] for p in hole]
        if min(max(xs) - min(xs), max(ys) - min(ys)) < smallest:
            patches.append(geom.polygon(hole))
    return geom.shape_union([shape] + patches) if patches else shape


def stencil_cut(shape: Shape, bridge_width: float = DEFAULT_BRIDGE) -> Shape:
    """The profile to subtract from a plate to leave a usable stencil.

    Slivers are filled, real counters are bridged, and anything that survives
    both -- a shape nobody anticipated -- is filled as well rather than left
    to fall out of the print. What comes back never contains an island.
    """
    if bridge_width <= 0:
        return shape
    cleaned = fill_slivers(shape, bridge_width)
    cut = cleaned - bridges(cleaned, bridge_width)
    stubborn = counters(cut)
    if stubborn:
        cut = geom.shape_union([cut] + [geom.polygon(h) for h in stubborn])
    return cut


def start_point(char: str, cap_height: float = font.CAP_HEIGHT,
                weight: float = font.DEFAULT_WEIGHT) -> Point2 | None:
    """Where a pencil starts this letter, in the glyph's own coordinates.

    The first point of the first stroke, which is how the font is drawn and
    how the letter is taught: a tracing card puts a raised dot here so a child
    knows where to begin rather than guessing.
    """
    _, strokes = font.glyph(char)
    if not strokes:
        return None
    points = _flatten_stroke(strokes[0])
    if not points:
        return None
    scale = cap_height / font.CAP_HEIGHT
    return (points[0][0] * scale + weight * scale / 2.0, points[0][1] * scale)


def describe_charset(text: str) -> str:
    """A short human phrase for a set of characters, for listing copy."""
    chars = list(dict.fromkeys(text))
    if not chars:
        return "nothing"
    if "".join(chars) == font.UPPERCASE:
        return "the capitals A-Z"
    if "".join(chars) == font.LOWERCASE:
        return "the lower-case letters a-z"
    if "".join(chars) == font.DIGITS:
        return "the digits 0-9"
    if len(chars) <= 12:
        return " ".join(chars)
    return f"{len(chars)} characters, {chars[0]} to {chars[-1]}"


def expand_charset(spec: str) -> str:
    """Turn a charset option into the characters it means.

    Accepts the named sets a teacher would ask for by name, ranges like `A-M`,
    and a literal string.  Named sets first, because `uppercase` as a literal
    would otherwise quietly build nine tiles spelling the word.
    """
    named = {
        "uppercase": font.UPPERCASE,
        "lowercase": font.LOWERCASE,
        "digits": font.DIGITS,
        "operators": font.OPERATORS,
        "alphabet": font.UPPERCASE,
        "both-cases": font.UPPERCASE + font.LOWERCASE,
        "vowels": "AEIOU",
        "consonants": "".join(c for c in font.UPPERCASE if c not in "AEIOU"),
        "numbers-and-operators": font.DIGITS + font.OPERATORS,
    }
    key = spec.strip().lower()
    if key in named:
        return named[key]

    text = spec.strip()
    if len(text) == 3 and text[1] == "-" and text[0].isalnum() and text[2].isalnum():
        start, end = ord(text[0]), ord(text[2])
        if start > end:
            raise TextError(f"range {spec!r} runs backwards")
        return "".join(chr(c) for c in range(start, end + 1))

    if not text:
        raise TextError("charset is empty")
    unknown = font.missing(text)
    if unknown:
        raise TextError(
            "no glyph for " + ", ".join(repr(c) for c in unknown)
            + ". Named sets: " + ", ".join(sorted(named))
        )
    return "".join(dict.fromkeys(text))
