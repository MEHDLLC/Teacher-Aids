"""A single-stroke geometric font, as data.

Why a stroke font and not an outline font: a classroom letter is *thick*.
It gets embossed 1.5 mm proud of a tile, cut clean through a stencil, or sunk
as a 2 mm groove a five-year-old drags a finger along, and all three want the
same skeleton at different weights.  Storing the skeleton and inflating it
means one number -- `weight` -- turns a delicate letter into a chunky one, and
the same letter can be raised, recessed or cut through without redrawing it.

An outline font would fix the weight at design time and make `weight` a lie.

Everything is drawn on a body 100 units tall, and scaled to the caller's cap
height at use.  The metrics below are the whole contract:

    baseline    0
    x-height    62
    cap height  100
    ascender    100      (b d f h k l, and every capital)
    descender  -24       (g j p q y)

A glyph is `(advance, strokes)`.  A stroke is a list of items, each either a
point `(x, y)` or an arc `("arc", cx, cy, rx, ry, start_deg, end_deg)` swept
from `start_deg` to `end_deg` on the ellipse.  Consecutive items are joined by
straight lines, so a stroke can mix the two freely; arcs are elliptical
because a capital O on this body is 74 wide and 100 tall, and sampling that as
a circle would give a short round letter instead of the intended one.
"""

from __future__ import annotations

CAP_HEIGHT = 100.0
X_HEIGHT = 62.0
BASELINE = 0.0
ASCENDER = 100.0
DESCENDER = -24.0

# Gap between glyphs, on the same 100-unit body.
DEFAULT_TRACKING = 14.0

# The default stroke weight, again on the 100-unit body.  A shade under a
# fifth of the cap height: heavy enough to read across a classroom, light
# enough that the counters in B, R and 8 stay open.
DEFAULT_WEIGHT = 18.0

Item = tuple  # (x, y) | ("arc", cx, cy, rx, ry, a0, a1)
Glyph = tuple[float, list[list[Item]]]


def _arc(cx, cy, rx, ry, a0, a1):
    return ("arc", cx, cy, rx, ry, a0, a1)


GLYPHS: dict[str, Glyph] = {
    " ": (40.0, []),

    # ---- capitals -------------------------------------------------------
    "A": (70.0, [[(0, 0), (35, 100), (70, 0)], [(10.5, 30), (59.5, 30)]]),
    "B": (66.0, [
        [(0, 0), (0, 100)],
        [(0, 100), (36, 100), _arc(36, 75, 26, 25, 90, -90), (0, 50)],
        [(0, 50), (38, 50), _arc(38, 25, 28, 25, 90, -90), (0, 0)],
    ]),
    "C": (70.0, [[_arc(35, 50, 35, 50, 55, 305)]]),
    "D": (70.0, [
        [(0, 0), (0, 100), (30, 100), _arc(30, 50, 40, 50, 90, -90), (0, 0)],
    ]),
    "E": (60.0, [
        [(0, 0), (0, 100)], [(0, 100), (58, 100)],
        [(0, 50), (48, 50)], [(0, 0), (58, 0)],
    ]),
    "F": (58.0, [[(0, 0), (0, 100)], [(0, 100), (56, 100)], [(0, 52), (46, 52)]]),
    "G": (74.0, [
        [_arc(36, 50, 36, 50, 55, 360)],
        [(72, 50), (44, 50)],
    ]),
    "H": (68.0, [[(0, 0), (0, 100)], [(68, 0), (68, 100)], [(0, 50), (68, 50)]]),
    # Serifed, so a capital I cannot be read as a lower-case l.
    "I": (34.0, [[(0, 100), (34, 100)], [(0, 0), (34, 0)], [(17, 0), (17, 100)]]),
    "J": (52.0, [[(46, 100), (46, 26), _arc(23, 26, 23, 26, 0, -180)]]),
    "K": (66.0, [
        [(0, 0), (0, 100)], [(66, 100), (0, 45)], [(24, 65), (66, 0)],
    ]),
    "L": (56.0, [[(0, 100), (0, 0), (56, 0)]]),
    "M": (84.0, [[(0, 0), (0, 100), (42, 38), (84, 100), (84, 0)]]),
    "N": (70.0, [[(0, 0), (0, 100), (70, 0), (70, 100)]]),
    "O": (74.0, [[_arc(37, 50, 37, 50, 0, 360)]]),
    "P": (64.0, [
        [(0, 0), (0, 100), (34, 100), _arc(34, 74, 30, 26, 90, -90), (0, 48)],
    ]),
    "Q": (74.0, [[_arc(37, 50, 37, 50, 0, 360)], [(44, 24), (72, 0)]]),
    "R": (66.0, [
        [(0, 0), (0, 100), (34, 100), _arc(34, 74, 30, 26, 90, -90), (0, 48)],
        [(30, 48), (66, 0)],
    ]),
    "S": (64.0, [[
        _arc(32, 75, 32, 25, 38, 270), _arc(32, 25, 32, 25, 90, -140),
    ]]),
    "T": (62.0, [[(0, 100), (62, 100)], [(31, 100), (31, 0)]]),
    "U": (68.0, [[
        (0, 100), (0, 34), _arc(34, 34, 34, 34, 180, 360), (68, 100),
    ]]),
    "V": (68.0, [[(0, 100), (34, 0), (68, 100)]]),
    "W": (96.0, [[(0, 100), (20, 0), (48, 72), (76, 0), (96, 100)]]),
    "X": (66.0, [[(0, 100), (66, 0)], [(0, 0), (66, 100)]]),
    "Y": (66.0, [[(0, 100), (33, 52)], [(66, 100), (33, 52)], [(33, 52), (33, 0)]]),
    "Z": (64.0, [[(0, 100), (64, 100), (0, 0), (64, 0)]]),

    # ---- lower case -----------------------------------------------------
    # Single-storey a and g: this is a font for someone learning to write,
    # and the two-storey forms are not the ones they are taught to draw.
    "a": (58.0, [[_arc(26, 31, 26, 31, 0, 360)], [(52, 62), (52, 0)]]),
    "b": (58.0, [[(0, 0), (0, 100)], [_arc(30, 31, 28, 31, 0, 360)]]),
    "c": (56.0, [[_arc(28, 31, 28, 31, 55, 305)]]),
    "d": (58.0, [[(58, 0), (58, 100)], [_arc(28, 31, 28, 31, 0, 360)]]),
    "e": (56.0, [[(0, 31), (56, 31), _arc(28, 31, 28, 31, 0, 305)]]),
    "f": (52.0, [
        [(26, 0), (26, 84), _arc(40, 84, 14, 14, 180, 90)],
        [(4, 62), (48, 62)],
    ]),
    "g": (58.0, [
        [_arc(28, 31, 28, 31, 0, 360)],
        [(56, 62), (56, -6), _arc(30, -6, 26, 18, 0, -180)],
    ]),
    "h": (56.0, [
        [(0, 0), (0, 100)],
        [_arc(28, 34, 28, 28, 180, 0), (56, 0)],
    ]),
    # The dot is a single point, not a small circle, and the stem stops short
    # of the x-height: at the weights a classroom tile uses, the pen is 20-odd
    # units wide and any closer would weld the dot to the stem into one blob.
    "i": (20.0, [[(10, 0), (10, 60)], [(10, 90)]]),
    "j": (32.0, [
        [(22, 60), (22, -6), _arc(11, -6, 11, 16, 0, -180)],
        [(22, 90)],
    ]),
    "k": (54.0, [[(0, 0), (0, 100)], [(50, 62), (6, 26)], [(22, 39), (54, 0)]]),
    "l": (20.0, [[(10, 0), (10, 100)]]),
    "m": (90.0, [
        [(0, 0), (0, 62)],
        [_arc(22, 34, 22, 28, 180, 0), (44, 0)],
        [_arc(66, 34, 22, 28, 180, 0), (88, 0)],
    ]),
    "n": (56.0, [[(0, 0), (0, 62)], [_arc(28, 34, 28, 28, 180, 0), (56, 0)]]),
    "o": (58.0, [[_arc(29, 31, 29, 31, 0, 360)]]),
    "p": (58.0, [[(0, -24), (0, 62)], [_arc(30, 31, 28, 31, 0, 360)]]),
    "q": (58.0, [[(58, -24), (58, 62)], [_arc(28, 31, 28, 31, 0, 360)]]),
    "r": (42.0, [[(0, 0), (0, 62)], [_arc(24, 38, 24, 24, 180, 60)]]),
    "s": (50.0, [[
        _arc(25, 46.5, 25, 15.5, 38, 270), _arc(25, 15.5, 25, 15.5, 90, -140),
    ]]),
    "t": (46.0, [
        [(20, 100), (20, 14), _arc(32, 14, 12, 14, 180, 0)],
        [(2, 62), (42, 62)],
    ]),
    "u": (56.0, [[(0, 62), (0, 28), _arc(28, 28, 28, 28, 180, 360), (56, 62)]]),
    "v": (54.0, [[(0, 62), (27, 0), (54, 62)]]),
    "w": (78.0, [[(0, 62), (16, 0), (39, 44), (62, 0), (78, 62)]]),
    "x": (52.0, [[(0, 62), (52, 0)], [(0, 0), (52, 62)]]),
    "y": (54.0, [[(0, 62), (30, 0)], [(54, 62), (16, -24)]]),
    "z": (50.0, [[(0, 62), (50, 62), (0, 0), (50, 0)]]),

    # ---- digits ---------------------------------------------------------
    "0": (64.0, [[_arc(32, 50, 32, 50, 0, 360)]]),
    "1": (42.0, [[(6, 76), (22, 100), (22, 0)], [(2, 0), (42, 0)]]),
    "2": (62.0, [[_arc(31, 68, 31, 32, 170, -50), (0, 0), (62, 0)]]),
    "3": (62.0, [[
        _arc(31, 75, 31, 25, 160, -90), _arc(31, 25, 31, 25, 90, -160),
    ]]),
    "4": (66.0, [[(48, 0), (48, 100), (0, 30), (66, 30)]]),
    "5": (60.0, [[(58, 100), (6, 100), (6, 56), _arc(30, 32, 30, 26, 120, -140)]]),
    "6": (62.0, [
        [_arc(31, 70, 31, 30, 60, 180), (0, 30)],
        [_arc(31, 30, 31, 30, 0, 360)],
    ]),
    "7": (58.0, [[(0, 100), (58, 100), (18, 0)]]),
    "8": (62.0, [
        [_arc(31, 75, 29, 25, 0, 360)], [_arc(31, 25, 31, 25, 0, 360)],
    ]),
    "9": (62.0, [
        [_arc(31, 30, 31, 30, 240, 360), (62, 70)],
        [_arc(31, 70, 31, 30, 0, 360)],
    ]),

    # ---- punctuation and arithmetic -------------------------------------
    ".": (26.0, [[_arc(13, 8, 8, 8, 0, 360)]]),
    ",": (26.0, [[(17, 12), (14, 2), (4, -16)]]),
    "!": (24.0, [[(12, 100), (12, 28)], [_arc(12, 8, 8, 8, 0, 360)]]),
    "?": (56.0, [
        [_arc(28, 74, 26, 26, 190, -60), (28, 30)],
        [_arc(28, 8, 8, 8, 0, 360)],
    ]),
    "'": (22.0, [[(11, 100), (11, 74)]]),
    '"': (38.0, [[(11, 100), (11, 74)], [(27, 100), (27, 74)]]),
    ":": (24.0, [[_arc(12, 8, 8, 8, 0, 360)], [_arc(12, 46, 8, 8, 0, 360)]]),
    "-": (48.0, [[(6, 50), (42, 50)]]),
    "_": (56.0, [[(0, -8), (56, -8)]]),
    "+": (64.0, [[(8, 50), (56, 50)], [(32, 26), (32, 74)]]),
    "=": (64.0, [[(8, 62), (56, 62)], [(8, 38), (56, 38)]]),
    "*": (52.0, [
        [(26, 30), (26, 78)], [(5, 42), (47, 66)], [(5, 66), (47, 42)],
    ]),
    "x": None,  # placeholder, replaced below so the multiply sign can borrow it
    "/": (44.0, [[(2, 0), (42, 100)]]),
    "(": (34.0, [[_arc(30, 50, 28, 54, 150, 210)]]),
    ")": (34.0, [[_arc(4, 50, 28, 54, 30, -30)]]),
    "<": (54.0, [[(46, 82), (8, 50), (46, 18)]]),
    ">": (54.0, [[(8, 82), (46, 50), (8, 18)]]),
    "%": (78.0, [
        [(12, 0), (66, 100)],
        [_arc(19, 79, 17, 17, 0, 360)], [_arc(59, 21, 17, 17, 0, 360)],
    ]),
    "#": (72.0, [
        [(18, 0), (28, 100)], [(44, 0), (54, 100)],
        [(4, 32), (66, 32)], [(8, 68), (70, 68)],
    ]),
    "&": (74.0, [[
        (70, 0), (16, 72), _arc(30, 82, 14, 18, 180, 0),
        (16, 60), (56, 22), _arc(38, 22, 18, 22, 0, 180),
        (22, 4), (48, 18),
    ]]),
    # The arithmetic signs a maths set needs, kept distinct from the letters
    # that look like them: x is a letter, multiply is a symbol, and a child
    # sorting tiles needs them to be different objects.
    "×": (56.0, [[(10, 68), (46, 32)], [(10, 32), (46, 68)]]),
    "÷": (64.0, [
        [(8, 50), (56, 50)],
        [_arc(32, 76, 8, 8, 0, 360)], [_arc(32, 24, 8, 8, 0, 360)],
    ]),
    "−": (48.0, [[(6, 50), (42, 50)]]),
    "≤": (54.0, [[(46, 88), (8, 58), (46, 28)], [(8, 8), (46, 8)]]),
    "≥": (54.0, [[(8, 88), (46, 58), (8, 28)], [(8, 8), (46, 8)]]),
}

del GLYPHS["x"]
GLYPHS["x"] = (52.0, [[(0, 62), (52, 0)], [(0, 0), (52, 62)]])


# Which characters this font can actually draw, in a sensible teaching order.
UPPERCASE = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LOWERCASE = "abcdefghijklmnopqrstuvwxyz"
DIGITS = "0123456789"
OPERATORS = "+−×÷=<>"
PUNCTUATION = ".,!?'\"-:"


def supported() -> str:
    return "".join(sorted(GLYPHS))


def missing(text: str) -> list[str]:
    """Characters in `text` this font has no glyph for."""
    return sorted({c for c in text if c not in GLYPHS})


def glyph(char: str) -> Glyph:
    try:
        return GLYPHS[char]
    except KeyError:
        raise KeyError(
            f"no glyph for {char!r}. This font draws: "
            + " ".join(repr(c) for c in sorted(GLYPHS))
        ) from None


# ---------------------------------------------------------------------------
# Words that go with letters
# ---------------------------------------------------------------------------

# One word per letter for the themes that pair a letter with a thing.  Chosen
# so the letter is the word's *initial sound*, not just its initial spelling:
# the point of the tile is phonics, so no "Cheetah" for C and no "Gnu" for G.
ANIMALS: dict[str, str] = {
    "A": "Alligator", "B": "Bear", "C": "Cat", "D": "Dog", "E": "Elephant",
    "F": "Fox", "G": "Goat", "H": "Horse", "I": "Iguana", "J": "Jellyfish",
    "K": "Kangaroo", "L": "Lion", "M": "Monkey", "N": "Newt", "O": "Otter",
    "P": "Penguin", "Q": "Quail", "R": "Rabbit", "S": "Snake", "T": "Turtle",
    "U": "Urchin", "V": "Vulture", "W": "Walrus", "X": "Fox", "Y": "Yak",
    "Z": "Zebra",
}

# X gets a word that ends in the sound instead of starting with it, which is
# how every alphabet chart handles it.  Say so rather than pretending.
TRAILING_SOUND = ("X",)


def word_for(char: str, table: dict[str, str] = ANIMALS) -> str:
    return table.get(char.upper(), "")
