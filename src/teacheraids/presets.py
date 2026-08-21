"""Measured sizes this repo builds around, and where each number came from.

Provenance matters: a marker rack whose bore is a millimetre small is scrap,
and a fraction set that does not match the school's existing one is worse than
no set at all.  Every entry says whether it is a published figure, a measured
one, or a typical value that the user should check against the thing on their
own desk.  `confidence` is carried into the manifest and the listing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .units import inch


@dataclass(frozen=True)
class Bore:
    """A round thing a holder has to accept: pen, marker, brush, glue stick."""

    key: str
    label: str
    diameter: float          # mm, at the widest point of the barrel
    length: float            # mm, overall
    source: str
    confidence: str          # "published" | "measured" | "typical"

    def to_dict(self) -> dict:
        return asdict(self)


BORES: dict[str, Bore] = {
    b.key: b for b in (
        Bore("expo-chisel", "Dry-erase marker, chisel tip (Expo-size)", 18.0,
             136.0,
             "Barrel of a standard chisel-tip dry-erase marker. Widely quoted "
             "as 17-18 mm; taken at the top of that range so the marker drops "
             "in rather than wedges.",
             "typical"),
        Bore("expo-fine", "Dry-erase marker, fine tip", 13.5, 130.0,
             "Fine-tip dry-erase barrel, typical value.", "typical"),
        Bore("crayola-marker", "Broad-line classroom marker", 15.5, 140.0,
             "Broad-line washable classroom marker barrel, typical value.",
             "typical"),
        Bore("pencil", "Hexagonal wooden pencil", 8.0, 190.0,
             "A #2 hex pencil measures 7.5 mm across the flats and about "
             "8.2 mm across the corners; 8.0 mm plus the clearance below "
             "takes either orientation.",
             "typical"),
        Bore("pen", "Ballpoint pen", 11.0, 145.0, "Typical stick-pen barrel.",
             "typical"),
        Bore("glue-stick", "Glue stick", 27.0, 95.0,
             "Standard large glue stick body, typical value.", "typical"),
        Bore("paintbrush", "School paintbrush handle", 9.0, 195.0,
             "Typical wooden school brush handle.", "typical"),
        Bore("scissors", "Blunt-tip school scissors", 22.0, 130.0,
             "Slot width for a pair of closed blunt-tip school scissors, "
             "typical value.", "typical"),
    )
}

DEFAULT_BORE = "expo-chisel"


def get_bore(key: str) -> Bore:
    try:
        return BORES[key]
    except KeyError:
        raise KeyError(
            f"unknown bore preset {key!r}; known presets: "
            + ", ".join(sorted(BORES))
        ) from None


def bore_keys() -> tuple[str, ...]:
    return tuple(BORES)


# ---------------------------------------------------------------------------
# Sizes that come from how classroom sets are already made
# ---------------------------------------------------------------------------

# Standard pattern blocks are built on a one-inch edge: the green triangle, the
# orange square, the blue and tan rhombi, the red trapezoid and the yellow
# hexagon all share it, which is the entire point of the set -- six shapes that
# tile against each other. Change the edge and they still tile; mix two edges
# and nothing does.
PATTERN_BLOCK_EDGE = inch(1.0)
PATTERN_BLOCK_THICKNESS = inch(1.0 / 4.0)

# Base-ten blocks are built on a one-centimetre unit cube, which is why a
# thousand of them make a litre. That is a teaching point, not a coincidence,
# so 10 mm is the default and the option that changes it says what it costs.
BASE_TEN_UNIT = 10.0

# Interlocking cubes (Unifix / Multilink and their kin) are 2 cm.
LINKING_CUBE = 20.0

# What a slicer will actually resolve. Used to warn rather than to refuse: a
# 0.3 mm feature still prints on a 0.4 nozzle, it just prints as 0.4.
NOZZLE = 0.4
MIN_FEATURE = 0.8          # two extrusion widths: the thinnest honest wall
MIN_EMBOSS_DEPTH = 0.4     # two 0.2 mm layers, or it reads as a texture
MIN_TILE_SIZE = 30.0       # below this a tile is a choking hazard, not a toy

# A round magnet sunk in the back of a tile so it lives on a whiteboard.
MAGNET_SIZES = {
    "6x2": (6.0, 2.0),
    "8x2": (8.0, 2.0),
    "10x2": (10.0, 2.0),
    "10x3": (10.0, 3.0),
    "12x3": (12.0, 3.0),
}
DEFAULT_MAGNET = "10x2"
