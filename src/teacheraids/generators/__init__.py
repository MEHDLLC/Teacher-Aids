"""Every generator in the repo. Importing a module is what registers it.

Grouped by the category each belongs to, which is also the catalogue it is
listed in and the workflow that builds it.
"""

from . import (                                                  # noqa: F401
    # alphabet
    letter_tile, stencil,
    # math
    fraction_set, place_value, pattern_blocks, geometry_solid, ten_frame,
    clock_face,
    # organization
    supply_caddy, marker_rack, book_end,
    # classroom
    name_plate, bookmark, hall_pass,
    # games
    dice, spinner,
)
