# How a run works

One command, one directory of output, and four things that cannot disagree with
each other because they all come from the same place.

```
options  ->  build  ->  export  ->  verify
                    \->  render
                    \->  describe
                    \->  record
```

## 1. Options

Every generator declares its options once, as an `OptionSet`. That single
declaration produces:

- the CLI flags, their types, their ranges and their help,
- the validation a catalogue entry is checked against,
- the `options` block in `manifest.json`,
- the "Options used" table in `listing.md`.

There is no second copy of the variable list anywhere, so those four cannot
drift apart. `teachergen schema` prints the whole declaration as JSON, which is
how a pipeline discovers the variables rather than restating them.

An option whose default is `None` is *automatic*: it gets filled in from
something else — a theme, a preset, the size of the thing it sits on — and its
`default_note` says what from. Whatever it ends up as is what the manifest and
the listing report, because the runner uses `effective_options` rather than what
was asked for.

```python
Option("cap_height", None, "Letter height", unit=" mm", minimum=4.0,
       maximum=180.0, group="Size",
       default_note="62% of the tile, or 52% when a word is on it")
```

## 2. Build

`Generator.build(options)` returns a `BuildResult`: the parts, the options it
actually used, facts about the result, highlights, teaching notes, print notes,
and a `Report` of anything worth warning about.

Warnings are how this repo handles "you probably do not want that". A magnet
pocket deeper than the tile is left out and reported. A rib thick enough that a
frame stops looking like a frame is built and reported. A stencil bridge wider
than the stroke it crosses is built and reported. The only things that raise are
the ones where there is no sensible object to hand back at all — a set with no
characters in it, a caddy with no room inside, a piece that would arrive in
several pieces.

That last one is asserted inside `build`, not only in the tests:

```python
if not geom.is_one_piece(solid):
    raise ValueError(...)
```

An option that severs a part is an easy thing to add and a silent way to ship a
model that comes off the bed as a handful of fragments.

## 3. Export

- **STL** per part, binary, dropped onto Z=0 at the origin.
- **3MF** holding every part of the set, with millimetre units declared in the
  file, every object *named*, and the parts packed into rows that fit a real
  build plate. A part wanted ten times is stored once and *placed* ten times, so
  a ten-frame's counters open as ten counters rather than as ten copies of one
  mesh.

Both writers are hand-rolled. 3MF is the format that carries what a teacher
needs and the general-purpose libraries either skip it or flatten the object
names and the copies away. The zip timestamp is fixed, so identical options
produce identical bytes and a re-download does not look like a change.

## 4. Render

A software rasteriser — no GPU, no display, no extra dependency, PNG written
through zlib. Three views: a plan, a three-quarter and an elevation. Sets are
laid out on a plate in the order they were made, so A-Z previews as A-Z.

The plan view is at 72 degrees rather than straight down. At 90 the top of a
1.6 mm embossed letter and the top of the tile it sits on both face straight up,
get the same lambert term and come out the same colour — the letter disappears
in exactly the view meant to show it. Backing off, and tinting by world height,
puts the relief back.

## 5. Describe

`listing.md` and `listing.json`, generated from `result.facts` — the same numbers
the geometry was built from. The copy cannot claim a size the model does not
have, a piece count it did not produce, or a fit it was never checked for.

Where a dimension is an estimate rather than a published figure, the listing
says which, and says what to do about it:

> That figure is **typical**, not published. Measure the one on your desk and
> pass it in if the fit matters: every dimension here is an option.

## 6. Record

`manifest.json`: every option, a stable hash of them, the derived facts, every
part's size, volume, triangle count and piece count, the plate layout, the
estimated weight, and every file written.

The hash is over the generator key and the resolved options, so the same request
always produces the same hash — which is how a build system knows whether
anything actually changed.

## 7. Verify

`teachergen verify` reads the bytes back off disk and works out the topology
from scratch.

STL carries no topology at all — three unshared float32 corners per triangle —
so any reader has to weld coincident vertices before it can say anything about
watertightness. That is exactly what a slicer does when it opens the file, so
welding here is not a workaround, it is the test. The weld snaps to a fixed grid
rather than using a scale-dependent tolerance, so the same file always gives the
same answer.

What it checks: watertight, consistently wound, positive volume, one connected
piece, no degenerate triangles, and — cross-checked against the manifest sitting
next to it — the volume and the bounding box the manifest claims.

Deliberately not included: mesh repair. If something here fails, the geometry is
wrong upstream and the fix belongs there. Repairing a hole would ship a model
whose shape nobody chose.

There is also an in-memory version, `geom.edge_manifold`, for use during a
build. manifold3d's own validity check is about its half-edge structure and will
call a solid valid when two parts of it meet along a single edge; written out to
a mesh, that edge belongs to four triangles and the file is not manifold.
Generators use it to catch that before writing anything.

## Catalogues and batches

A catalogue names the variants worth building.

```json
{
  "release": { "name": "teacher-aids-math", "version": "0.1.0",
               "title": "Teacher Aids: Maths Manipulatives" },
  "items": [
    { "name": "clock_150mm", "generator": "clock-face",
      "options": { "diameter": 150 } }
  ],
  "sweeps": [
    { "generator": "dice", "name": "dice_{shape}_20mm",
      "options": { "faces": "numbers", "size": 20 },
      "axes": { "shape": ["tetrahedron", "octahedron", "icosahedron"] } }
  ]
}
```

There is one per category, in `catalogues/`, because the categories are built by
separate workflows. `teachergen plan` expands and validates without building
anything; `teachergen batch` builds, verifies each written file, and writes
`INDEX.md` and `index.json` over everything on disk — not over what the process
happened to make, so a job that merges chunks from several machines indexes them
the same way a single run does.

A sweep can carry `cap`, which takes an evenly spread subset rather than every
combination. `--limit N --pick spread` does the same at the command line; a
small limit still covers the range of the catalogue instead of every result
sharing the first axis value.

`--chunk I --chunks K` splits a catalogue across parallel jobs. The split is
round robin rather than contiguous, because variants differ enormously in cost —
a twenty-six tile alphabet against a single bookmark — and dealing them out
keeps every chunk about the same size of job.
