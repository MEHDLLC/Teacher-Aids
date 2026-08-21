#!/usr/bin/env python3
"""Render every pattern, cut through a panel, onto one sheet.

Patterns are chosen so a vertical panel prints without support. That rule is
easy to state and easy to break, and a picture is the fastest way to see that
a cell has grown a flat roof.

    python tools/pattern_sheet.py --out proofs
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from teacheraids import geom, patterns, preview            # noqa: E402
from teacheraids.mesh_io import Part                       # noqa: E402


def panel(style: str, width: float = 90.0, height: float = 90.0,
          thickness: float = 4.0) -> Part:
    cell = patterns.default_cell(style)
    rib = patterns.default_rib(style)
    profiles = patterns.tile(style, (6.0, 6.0, width - 6.0, height - 6.0),
                             cell, rib)
    body = geom.prism_y([(0, 0), (width, 0), (width, height), (0, height)],
                        0.0, thickness)
    cutters = [geom.prism_y(p, -1.0, thickness + 1.0) for p in profiles]
    return Part(style, geom.difference(body, cutters))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="proofs", metavar="DIR")
    args = parser.parse_args()

    root = Path(args.out)
    root.mkdir(parents=True, exist_ok=True)
    # One tile per pattern, composed by hand. Letting the previewer lay them
    # out would stand eight panels in a row and photograph them edge on,
    # which is a picture of the first two.
    tiles = [preview.scene_pixels([panel(style)], size=300, azimuth=0.0,
                                  elevation=4.0, spread=False)
             for style in patterns.PATTERNS]
    rows = [tiles[i:i + 4] for i in range(0, len(tiles), 4)]
    while len(rows[-1]) < len(rows[0]):
        rows[-1].append(tiles[0] * 0 + 250)          # pad with background
    path = preview.write_sheet(root / "patterns.png", rows)
    print(f"wrote {path}")
    for style in patterns.PATTERNS:
        print(f"  {style:10s} {patterns.describe(style, patterns.default_cell(style), patterns.default_rib(style))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
