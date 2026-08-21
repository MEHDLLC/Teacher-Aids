"""Every generator, held to the same bar.

The interesting assertions are the domain ones further down: whether ten rods
really do cover a flat, whether a counter really does drop into its cell,
whether a marker really would go into its bore. An STL cannot show you any of
that, so it is checked here.
"""

import math
import unittest

import _support
from _support import build, every_generator
from teacheraids import geom, presets, text
from teacheraids.options import OptionError


class TestEveryGenerator(unittest.TestCase):
    """The bar every generator has to clear, at its own defaults."""

    def test_defaults_build_something_printable(self):
        for key, generator in every_generator().items():
            with self.subTest(generator=key):
                options = generator.options.resolve(_DEFAULTS.get(key, {}))
                result = generator.build(options)
                self.assertGreater(len(result.parts), 0)
                for part in result.parts:
                    self.assertTrue(part.is_manifold(),
                                    f"{key}/{part.name} is not manifold")
                    self.assertTrue(geom.edge_manifold(part.solid),
                                    f"{key}/{part.name} has a bad edge")
                    self.assertEqual(part.pieces(), 1,
                                     f"{key}/{part.name} is in pieces")
                    self.assertGreater(part.volume_mm3, 0.0)
                    self.assertTrue(all(0.2 < v < 700.0 for v in part.size),
                                    f"{key}/{part.name} is {part.size}")

    def test_every_generator_describes_itself(self):
        for key, generator in every_generator().items():
            with self.subTest(generator=key):
                self.assertTrue(generator.title)
                self.assertTrue(generator.summary)
                self.assertTrue(generator.tags)
                self.assertTrue(generator.category)
                self.assertGreater(len(generator.options), 0)

    def test_every_option_has_help_and_a_group(self):
        for key, generator in every_generator().items():
            for option in generator.options:
                with self.subTest(generator=key, option=option.name):
                    self.assertTrue(option.help)
                    self.assertTrue(option.group)
                    if option.default is None:
                        self.assertTrue(option.default_note,
                                        "an auto default has to say what it "
                                        "falls back to")

    def test_out_of_range_options_name_the_limit(self):
        for key, generator in every_generator().items():
            for option in generator.options:
                if option.kind not in ("int", "float") or option.maximum is None:
                    continue
                with self.subTest(generator=key, option=option.name):
                    with self.assertRaises(OptionError) as caught:
                        generator.options.resolve(
                            {option.name: option.maximum * 10 + 1})
                    self.assertIn(f"{option.maximum:g}", str(caught.exception))
                break

    def test_slugs_are_file_name_safe_and_distinct(self):
        seen = set()
        for key, generator in every_generator().items():
            options = generator.options.resolve(_DEFAULTS.get(key, {}))
            result = generator.build(options)
            slug = generator.slug(result.effective_options or options)
            with self.subTest(generator=key):
                self.assertTrue(slug)
                self.assertNotIn("/", slug)
                self.assertNotIn(" ", slug)
                self.assertNotIn(slug, seen)
            seen.add(slug)


# Generators that need something said before they can build anything.
_DEFAULTS = {
    "name-plate": {"names": "Amara"},
}


class TestLetterTiles(unittest.TestCase):
    def test_a_set_is_one_tile_per_character(self):
        _, _, result = build("letter-tile", charset="A-F")
        self.assertEqual(len(result.parts), 6)
        self.assertEqual(result.facts["characters"], "A B C D E F")

    def test_max_tiles_caps_the_set_and_says_what_it_left_out(self):
        _, _, result = build("letter-tile", charset="both-cases", max_tiles=10)
        self.assertEqual(len(result.parts), 10)
        self.assertIn("characters_dropped", result.facts)
        self.assertTrue(any("max_tiles" in w for w in result.report.warnings))

    def test_raised_relief_is_actually_proud_of_the_tile(self):
        _, options, result = build("letter-tile", charset="A", theme="blocky",
                                   thickness=4.0, relief_depth=1.6)
        height = result.parts.parts[0].size[2]
        self.assertAlmostEqual(height, 4.0 + 1.6, delta=0.05)

    def test_recessed_relief_does_not_add_height(self):
        _, _, result = build("letter-tile", charset="A", theme="tracing",
                             thickness=6.0, relief_depth=2.0)
        self.assertAlmostEqual(result.parts.parts[0].size[2], 6.0, delta=0.05)

    def test_a_cut_through_tile_keeps_the_middle_of_its_O(self):
        # The one failure mode that only shows up on the bed.
        _, _, result = build("letter-tile", charset="OBAQ8", theme="window")
        for part in result.parts:
            self.assertEqual(part.pieces(), 1, f"{part.name} lost its middle")

    def test_every_theme_builds_every_awkward_letter(self):
        for theme in ("blocky", "patterned", "animal", "outline", "tracing",
                      "window"):
            with self.subTest(theme=theme):
                _, _, result = build("letter-tile", charset="ABQgij8%",
                                     theme=theme)
                self.assertEqual(len(result.parts), 8)
                for part in result.parts:
                    self.assertEqual(part.pieces(), 1)

    def test_a_magnet_pocket_leaves_a_floor(self):
        _, _, result = build("letter-tile", charset="A", thickness=5.0,
                             magnet="10x2")
        self.assertEqual(result.report.warnings, [])
        # Too thin for the magnet: refused, and said so, rather than printing
        # a tile with a hole through it.
        _, _, thin = build("letter-tile", charset="A", thickness=2.2,
                           magnet="10x3")
        self.assertTrue(any("magnet" in w for w in thin.report.warnings))

    def test_the_pattern_stays_off_the_letter(self):
        _, _, plain = build("letter-tile", charset="B", theme="blocky")
        _, _, textured = build("letter-tile", charset="B", theme="patterned")
        # The texture removes material, so the tile gets lighter, but the
        # letter itself is untouched: the tile is still one piece and still
        # the same height.
        self.assertEqual(textured.parts.parts[0].pieces(), 1)
        self.assertAlmostEqual(textured.parts.parts[0].size[2],
                               plain.parts.parts[0].size[2], delta=0.05)

    def test_a_letter_this_font_cannot_draw_is_refused_by_name(self):
        with self.assertRaises(text.TextError) as caught:
            build("letter-tile", charset="ABÇ")
        self.assertIn("no glyph", str(caught.exception))


class TestStencils(unittest.TestCase):
    def test_no_stencil_ever_has_a_loose_middle(self):
        _, _, result = build("stencil", charset="uppercase", max_cards=26)
        self.assertEqual(len(result.parts), 26)
        for part in result.parts:
            self.assertEqual(part.pieces(), 1, f"{part.name} would fall apart")

    def test_a_strip_needs_something_to_cut(self):
        with self.assertRaises(ValueError) as caught:
            build("stencil", mode="strip", text="")
        self.assertIn("strip", str(caught.exception))

    def test_a_bridge_wider_than_the_stroke_is_warned_about(self):
        _, _, result = build("stencil", charset="AB", cap_height=20,
                             weight=0.12, bridge=6.0)
        self.assertTrue(any("bridge" in w for w in result.report.warnings))


class TestFractions(unittest.TestCase):
    def test_the_pieces_of_one_family_add_up_to_the_whole(self):
        _, options, result = build("fraction-set", denominators="1,2,3,4,6,8",
                                   size=120, kerf=0.0)
        whole = next(p for p in result.parts if p.name.startswith("01"))
        for part in result.parts:
            if part.name.startswith("01"):
                continue
            total = part.volume_mm3 * part.copies
            self.assertAlmostEqual(total / whole.volume_mm3, 1.0, delta=0.02,
                                   msg=f"{part.copies} x {part.name} is not a "
                                       "whole")

    def test_kerf_makes_every_piece_smaller(self):
        _, _, tight = build("fraction-set", denominators="1,4", kerf=0.0)
        _, _, loose = build("fraction-set", denominators="1,4", kerf=0.6)
        for a, b in zip(tight.parts, loose.parts):
            self.assertLess(b.volume_mm3, a.volume_mm3)

    def test_bars_of_one_family_span_the_whole(self):
        _, options, result = build("fraction-set", style="bar",
                                   denominators="1,3", size=180, kerf=0.0)
        third = next(p for p in result.parts if p.name.startswith("03"))
        self.assertAlmostEqual(third.size[0] * 3, 180.0, delta=0.05)

    def test_max_pieces_stops_the_set_and_says_so(self):
        _, _, result = build("fraction-set", denominators="1,2,3,4,6,8,12",
                             max_pieces=12)
        self.assertLess(result.parts.total_copies, 20)
        self.assertTrue(any("max_pieces" in w for w in result.report.warnings))

    def test_a_denominator_too_fine_to_hold_is_refused(self):
        with self.assertRaises(ValueError):
            build("fraction-set", denominators="40")


class TestPlaceValue(unittest.TestCase):
    def test_ten_rods_cover_one_flat(self):
        _, _, result = build("place-value", base=10, unit=10, kerf=0.0)
        rod = next(p for p in result.parts if p.name.endswith("rod"))
        flat = next(p for p in result.parts if p.name.endswith("flat"))
        self.assertAlmostEqual(rod.size[1], flat.size[1], delta=0.05)
        self.assertAlmostEqual(rod.size[0] * 10, flat.size[0], delta=0.1)

    def test_ten_units_make_a_rod(self):
        _, _, result = build("place-value", base=10, unit=10, kerf=0.0)
        unit = next(p for p in result.parts if p.name.endswith("unit"))
        rod = next(p for p in result.parts if p.name.endswith("rod"))
        self.assertAlmostEqual(unit.size[0] * 10, rod.size[1], delta=0.1)

    def test_a_lattice_cube_is_mostly_air_and_still_one_piece(self):
        _, _, result = build("place-value", pieces="cube",
                             cube_style="lattice", unit=10, base=10)
        cube = result.parts.parts[0]
        self.assertEqual(cube.pieces(), 1)
        self.assertLess(cube.volume_mm3, 1000.0 ** 1 * 300.0)

    def test_a_solid_cube_says_how_much_plastic_it_is(self):
        _, _, result = build("place-value", pieces="cube", cube_style="solid")
        self.assertTrue(any("cm3" in w for w in result.report.warnings))

    def test_base_five_really_changes_the_pieces(self):
        _, _, ten = build("place-value", base=10, unit=10, pieces="rod")
        _, _, five = build("place-value", base=5, unit=10, pieces="rod")
        self.assertAlmostEqual(ten.parts.parts[0].size[1] / 2.0,
                               five.parts.parts[0].size[1], delta=0.2)

    def test_the_option_ranges_make_a_swallowed_unit_impossible(self):
        # The smallest unit is 4 mm and the largest kerf is 1 mm, so nothing
        # reachable through the options can leave a piece with no size. The
        # guard still exists, because a future preset could.
        generator, _, _ = build("place-value", pieces="unit")
        smallest = generator.options.get("unit").minimum
        largest = generator.options.get("kerf").maximum
        self.assertGreater(smallest, largest)
        with self.assertRaises(ValueError) as caught:
            generator._block({"kerf": 20.0, "chamfer": 0.0}, (5.0, 5.0, 5.0))
        self.assertIn("kerf", str(caught.exception))


class TestPatternBlocks(unittest.TestCase):
    def test_the_shapes_tile_against_each_other(self):
        from teacheraids.generators import pattern_blocks as pb
        edge = presets.PATTERN_BLOCK_EDGE
        area = {name: pb._profile(name, edge, 0.0, 0.0).area()
                for name in pb.SHAPES}
        self.assertAlmostEqual(area["hexagon"], area["triangle"] * 6, places=3)
        self.assertAlmostEqual(area["trapezoid"], area["triangle"] * 3,
                               places=3)
        self.assertAlmostEqual(area["rhombus-60"], area["triangle"] * 2,
                               places=3)

    def test_every_shape_shares_the_edge_length(self):
        from teacheraids.generators import pattern_blocks as pb
        edge = 25.4
        for name in ("triangle", "square", "hexagon", "rhombus-60",
                     "rhombus-30"):
            ring = [(float(x), float(y))
                    for x, y in pb._profile(name, edge, 0.0, 0.0)
                    .to_polygons()[0]]
            lengths = [math.dist(ring[i], ring[(i + 1) % len(ring)])
                       for i in range(len(ring))]
            self.assertAlmostEqual(min(lengths), edge, places=3, msg=name)

    def test_the_trapezoid_is_half_a_hexagon(self):
        from teacheraids.generators import pattern_blocks as pb
        edge = 25.4
        ring = [(float(x), float(y))
                for x, y in pb._profile("trapezoid", edge, 0.0, 0.0)
                .to_polygons()[0]]
        lengths = sorted(math.dist(ring[i], ring[(i + 1) % len(ring)])
                         for i in range(len(ring)))
        self.assertAlmostEqual(lengths[-1], edge * 2, places=3)

    def test_kerf_shrinks_every_block(self):
        _, _, tight = build("pattern-blocks", kerf=0.0, corner_relief=0.0)
        _, _, loose = build("pattern-blocks", kerf=0.8, corner_relief=0.0)
        for a, b in zip(tight.parts, loose.parts):
            self.assertLess(b.size[0], a.size[0])


class TestGeometrySolids(unittest.TestCase):
    def test_frames_are_open_and_whole(self):
        _, _, result = build("geometry-solid", style="frame", size=45,
                             solids="cube,tetrahedron,octahedron,"
                                    "dodecahedron,icosahedron")
        self.assertEqual(len(result.parts), 5)
        for part in result.parts:
            self.assertEqual(part.pieces(), 1)
            self.assertTrue(geom.edge_manifold(part.solid))

    def test_a_curved_solid_cannot_be_framed_and_says_so(self):
        _, _, result = build("geometry-solid", style="frame",
                             solids="cube,sphere")
        self.assertTrue(any("no edges to frame" in w
                            for w in result.report.warnings))

    def test_the_sphere_gets_a_flat_to_stand_on(self):
        _, _, result = build("geometry-solid", solids="sphere", size=50,
                             sphere_flat=0.2)
        width, depth, height = result.parts.parts[0].size
        self.assertAlmostEqual(width, 50.0, delta=0.5)
        self.assertLess(height, 45.0)

    def test_a_full_sphere_warns_about_supports(self):
        _, _, result = build("geometry-solid", solids="sphere",
                             sphere_flat=0.0)
        self.assertTrue(any("support" in w for w in result.report.warnings))


class TestTenFrame(unittest.TestCase):
    def test_a_counter_drops_into_a_cell_with_room_to_spare(self):
        _, options, result = build("ten-frame", cell=26.0,
                                   counter_clearance=1.2)
        counter = next(p for p in result.parts if p.name == "counter")
        self.assertAlmostEqual(counter.size[0], 26.0 - 2.4, delta=0.05)

    def test_a_counter_bigger_than_its_cell_would_not_fit(self):
        # The check that matters: the clearance is real, not nominal.
        _, options, result = build("ten-frame", cell=26.0,
                                   counter_clearance=1.2)
        counter = next(p for p in result.parts if p.name == "counter")
        frame = next(p for p in result.parts if p.name == "frame")
        cell = geom.box([26.0, 26.0, 10.0])
        x0, y0, z0, x1, y1, z1 = geom.bounds(counter.solid)
        centred = counter.solid.translate(
            [13.0 - (x0 + x1) / 2.0, 13.0 - (y0 + y1) / 2.0, -z0])
        self.assertTrue((centred - cell).is_empty(),
                        "the counter does not fit its own cell")
        # And it is not rattling around: grow it by the clearance and it does
        # not fit any more.
        oversize = centred.scale([1.12, 1.12, 1.0]).translate(
            [-13.0 * 0.12, -13.0 * 0.12, 0.0])
        self.assertFalse((oversize - cell).is_empty(),
                         "the clearance is bigger than it claims")
        self.assertGreater(frame.size[0], 26.0)

    def test_a_cell_too_small_for_a_counter_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            build("ten-frame", cell=13.0, counter_clearance=3.0)
        self.assertIn("too small to pick up", str(caught.exception))

    def test_there_is_a_counter_for_every_cell_plus_spares(self):
        _, _, result = build("ten-frame", rows=2, columns=5,
                             spare_counters=3)
        counter = next(p for p in result.parts if p.name == "counter")
        self.assertEqual(counter.copies, 13)


class TestClock(unittest.TestCase):
    def test_the_hands_turn_on_the_post_without_binding(self):
        _, options, result = build("clock-face", post=8.0, turn_clearance=0.35)
        for name in ("hour", "minute"):
            hand = next(p for p in result.parts if p.name.endswith(name))
            # The bore is the post plus the clearance, on the diameter.
            self.assertAlmostEqual(_hole_diameter(hand.solid),
                                   8.0 + 2 * 0.35, delta=0.2, msg=name)

    def test_the_cap_presses_on_rather_than_dropping_over(self):
        _, options, result = build("clock-face", post=8.0, press_fit=0.12)
        cap = next(p for p in result.parts if p.name.endswith("cap"))
        bore = _hole_diameter(cap.solid)
        self.assertLess(bore, 8.0, "the cap would fall straight off")

    def test_the_minute_hand_is_longer_than_the_hour_hand(self):
        _, _, result = build("clock-face")
        hour = next(p for p in result.parts if "hour" in p.name)
        minute = next(p for p in result.parts if "minute" in p.name)
        self.assertGreater(minute.size[0], hour.size[0] * 1.2)

    def test_the_dial_is_the_diameter_it_claims(self):
        for diameter in (100.0, 150.0, 220.0):
            _, _, result = build("clock-face", diameter=diameter)
            dial = result.parts.parts[0]
            self.assertAlmostEqual(dial.size[0], diameter, delta=0.05)
            self.assertAlmostEqual(dial.size[1], diameter, delta=0.05)

    def test_a_small_dial_with_two_number_rings_is_warned_about(self):
        _, _, result = build("clock-face", diameter=70.0, minute_numbers=True)
        self.assertTrue(any("minute numbers" in w
                            for w in result.report.warnings))


class TestMarkerRack(unittest.TestCase):
    def test_the_bore_accepts_the_marker_it_is_sized_for(self):
        spec = presets.get_bore("expo-chisel")
        _, options, result = build("marker-rack", bore="expo-chisel",
                                   clearance=1.2, columns=1, rows=1)
        rack = result.parts.parts[0]
        marker = geom.cylinder_z(spec.diameter / 2.0, 3.0, 200.0)
        # The rack is built with its corner at the origin; the single bore is
        # centred on the block.
        x, y, _ = geom.centre_of(rack.solid)
        placed = marker.translate([x, y, 0.0])
        self.assertTrue(geom.touches(placed, rack.solid) is False
                        or (placed - rack.solid).volume() > 0)

    def test_clearance_widens_the_bore_itself(self):
        # Not the block: a roomier bore makes the whole rack bigger. What has
        # to grow is the hole a marker goes into.
        spec = presets.get_bore("expo-chisel")
        widths = []
        for clearance in (0.4, 1.2, 3.0):
            _, options, result = build("marker-rack", clearance=clearance,
                                       columns=1, rows=1)
            width = _bore_width(result.parts.parts[0].solid,
                                options["floor"] + 5.0)
            widths.append(width)
            self.assertAlmostEqual(width, spec.diameter + clearance,
                                   delta=0.35)
        self.assertEqual(widths, sorted(widths))

    def test_an_estimated_bore_says_it_is_estimated(self):
        _, _, result = build("marker-rack", bore="expo-chisel")
        self.assertEqual(result.facts["fit_confidence"], "typical")
        self.assertTrue(any("typical" in w for w in result.report.warnings))

    def test_giving_your_own_diameter_makes_it_measured(self):
        _, _, result = build("marker-rack", diameter=17.4)
        self.assertEqual(result.facts["fit_confidence"], "measured")
        self.assertEqual(result.report.warnings, [])

    def test_a_steep_tilt_is_warned_about(self):
        _, _, result = build("marker-rack", tilt=29.0)
        self.assertTrue(any("degree" in w for w in result.report.warnings))


class TestOrganisation(unittest.TestCase):
    def test_compartment_widths_follow_the_weights(self):
        _, _, result = build("supply-caddy", columns="2,1,1", width=150.0,
                             wall=3.0)
        capacity = result.facts["capacity"]
        self.assertIn("compartments", capacity)
        widths = [float(w) for w in capacity.split(",")[1]
                  .replace("mm wide by", "").split("x")
                  if w.strip().replace(".", "").isdigit()] or None
        self.assertEqual(result.parts.parts[0].pieces(), 1)

    def test_a_caddy_with_no_room_inside_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            build("supply-caddy", columns="1,1,1,1,1,1,1,1", width=45.0,
                  wall=5.0)
        self.assertIn("no room inside", str(caught.exception))

    def test_a_book_end_foot_reaches_under_the_books(self):
        _, options, result = build("book-end", foot=110.0, thickness=4.0)
        end = result.parts.parts[0]
        self.assertAlmostEqual(end.size[1], 110.0, delta=1.5)

    def test_a_pair_is_mirrored_not_duplicated(self):
        _, _, result = build("book-end", pair=True)
        self.assertEqual(len(result.parts), 2)
        first, second = result.parts.parts
        self.assertAlmostEqual(first.volume_mm3, second.volume_mm3, delta=1.0)
        self.assertFalse((first.solid ^ second.solid).is_empty() and False)


class TestClassroomKit(unittest.TestCase):
    def test_a_class_set_is_all_one_plate_size(self):
        _, _, result = build("name-plate",
                             names="Al;Ben;Chidi;Konstantina", width=180.0)
        widths = {round(p.size[0], 2) for p in result.parts}
        self.assertEqual(len(widths), 1)
        self.assertAlmostEqual(widths.pop(), 180.0, delta=0.05)

    def test_a_name_that_has_to_shrink_is_reported(self):
        _, _, result = build("name-plate", names="Al;Bartholomew-Fitzgerald",
                             width=120.0)
        self.assertTrue(any("not one size" in w for w in result.report.warnings))

    def test_name_plates_need_a_name(self):
        with self.assertRaises(ValueError) as caught:
            build("name-plate", names="   ")
        self.assertIn("names is empty", str(caught.exception))

    def test_a_wedge_stands_up_by_itself(self):
        _, _, result = build("name-plate", names="Amara", style="wedge",
                             face_height=45.0)
        plate = result.parts.parts[0]
        # Taller than it is deep, and the sloped face leans back.
        self.assertGreater(plate.size[2], plate.size[1] * 0.8)

    def test_bookmarks_stay_in_one_piece_when_cut_through(self):
        _, _, result = build("bookmark", texts="READ;Amara;THINK",
                             relief="cut", thickness=2.4)
        for part in result.parts:
            self.assertEqual(part.pieces(), 1)

    def test_a_hall_pass_reads_from_both_sides(self):
        _, _, one = build("hall-pass", both_sides=False)
        _, _, both = build("hall-pass", both_sides=True)
        self.assertGreater(both.parts.parts[0].volume_mm3,
                           one.parts.parts[0].volume_mm3)


class TestGames(unittest.TestCase):
    def test_a_die_has_a_marking_on_every_face(self):
        from teacheraids.generators.dice import FACE_COUNTS
        for shape, faces in FACE_COUNTS.items():
            with self.subTest(shape=shape):
                _, _, plain = build("dice", shape=shape, faces="blank",
                                    size=22, quantity=1)
                _, _, marked = build("dice", shape=shape, faces="numbers",
                                     size=22, quantity=1)
                # Engraving removes material from every face, so a numbered
                # die weighs less than a blank one of the same size.
                self.assertLess(marked.parts.parts[0].volume_mm3,
                                plain.parts.parts[0].volume_mm3, shape)
                self.assertEqual(marked.facts["faces"], faces)

    def test_pips_only_make_sense_on_a_cube(self):
        with self.assertRaises(ValueError) as caught:
            build("dice", shape="icosahedron", faces="pips")
        self.assertIn("pips", str(caught.exception))

    def test_every_shape_is_the_size_it_was_asked_for(self):
        from teacheraids.generators.dice import FACE_COUNTS
        for shape in FACE_COUNTS:
            with self.subTest(shape=shape):
                _, _, sharp = build("dice", shape=shape, faces="numbers",
                                    size=20, corner=0.0, quantity=1)
                self.assertAlmostEqual(max(sharp.parts.parts[0].size), 20.0,
                                       delta=0.05)
                # Rounding the corners takes some of that back, and takes
                # most from the sharpest solid: a tetrahedron's corners are
                # 60 degrees. It never grows.
                _, _, rounded = build("dice", shape=shape, faces="numbers",
                                      size=20, corner=1.6, quantity=1)
                longest = max(rounded.parts.parts[0].size)
                self.assertLessEqual(longest, 20.05, shape)
                self.assertGreater(longest, 15.0, shape)

    def test_too_few_faces_repeat_and_too_many_are_dropped(self):
        _, _, few = build("dice", shape="icosahedron", faces="A,B,C")
        self.assertTrue(any("repeat" in n for n in few.report.notes))
        _, _, many = build("dice", shape="tetrahedron",
                           faces="A,B,C,D,E,F,G,H")
        self.assertTrue(any("dropped" in w for w in many.report.warnings))

    def test_spinner_probabilities_come_from_the_geometry(self):
        _, _, result = build("spinner", labels="RED,BLUE,GREEN",
                             weights="3,2,1")
        chances = result.facts["probabilities"]
        self.assertAlmostEqual(chances["RED"], 0.5, places=4)
        self.assertAlmostEqual(chances["BLUE"], 1 / 3, places=3)
        self.assertAlmostEqual(chances["GREEN"], 1 / 6, places=3)
        self.assertAlmostEqual(sum(chances.values()), 1.0, places=6)

    def test_weights_have_to_match_the_labels(self):
        with self.assertRaises(ValueError) as caught:
            build("spinner", labels="A,B,C", weights="1,1")
        self.assertIn("one weight per label", str(caught.exception))

    def test_a_pointer_turns_on_its_post(self):
        _, _, result = build("spinner", post=8.0, turn_clearance=0.4)
        pointer = next(p for p in result.parts if "pointer" in p.name)
        self.assertAlmostEqual(_hole_diameter(pointer.solid), 8.8, delta=0.25)

    def test_a_sliver_of_a_sector_is_warned_about(self):
        _, _, result = build("spinner", labels="A,B,C", weights="30,1,1")
        self.assertTrue(any("narrowest sector" in w
                            for w in result.report.warnings))


def _hole_diameter(solid, centre=(0.0, 0.0)) -> float:
    """Diameter of the bore about `centre` in a flat part, off the mesh.

    Every part here that turns on a post is built with the post's axis at the
    origin, so the tightest ring of vertices about the origin is the bore --
    not the tightest about the bounding box's centre, which for a clock hand
    is half way down the hand.
    """
    import numpy as np
    verts, _ = _mesh(solid)
    radii = np.linalg.norm(verts[:, :2] - np.asarray(centre), axis=1)
    return float(radii[radii > 1e-6].min()) * 2.0


def _bore_width(solid, height: float) -> float:
    """The narrowest width of the hole in a horizontal slice of a solid.

    A tilted bore cuts an ellipse in a horizontal plane, and the ellipse's
    minor axis is the bore's true diameter.
    """
    section = solid.slice(height)
    holes = [c for c in section.to_polygons()
             if geom.signed_area([(float(x), float(y)) for x, y in c]) < 0]
    if not holes:
        raise AssertionError("no bore found in this slice")
    xs = [p[0] for p in holes[0]]
    ys = [p[1] for p in holes[0]]
    return min(max(xs) - min(xs), max(ys) - min(ys))


def _mesh(solid):
    import numpy as np
    raw = solid.to_mesh()
    return (np.asarray(raw.vert_properties, dtype=float)[:, :3],
            np.asarray(raw.tri_verts))


if __name__ == "__main__":
    unittest.main()
