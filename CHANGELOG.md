# Changelog

All notable changes to the 3D print support inspector. How it works and its settings are in `README.md`.

## [Unreleased]

### Added

- Examples of supports that miss a spot: a picture of a real part with tree supports, and
  `examples/report_prusaslicer_supports.html`, the test piece sliced in PrusaSlicer with supports on.
- The README says what selecting and labelling areas is for.

## [0.3.2] - 2026-11-18

### Added

- Tests on real slices of the test piece from Cura 5.14.0, with and without supports.

### Fixed

- Cura's slices: it fills a bridge with lines that end on the walls spanning the gap, not on the
  layer below, so the fill of every bridge counted as hanging. A line's end now also counts as held
  when it lies against a held line of its own layer.

## [0.3.1] - 2026-11-18

### Added

- Tests on real slices of the test piece from OrcaSlicer 2.5.1 and PrusaSlicer 2.9.7, with and
  without supports.

### Fixed

- PrusaSlicer's slices: its bridges ("Bridge infill") were skipped as infill, and a layer with thick
  bridges was compared with the wrong height below it, so everything on that layer counted as
  hanging. A layer is now checked against the model's layer before it, whatever height its lines
  claim. This also makes G-code without height comments (Cura's) work at any layer height.
- A file that does not exist gives a one-line error, not a traceback.

## [0.3.0] - 2026-11-18

### Added

- The MIT licence.
- A Python package with the `support-inspector` command (`pipx install git+https://...`), and `--version`.
- Tests: hand-written G-code in the comment styles of Bambu Studio, PrusaSlicer, OrcaSlicer and Cura,
  and two real Bambu Studio slices of the new test piece, `examples/test_piece.stl` (a ledge, a long
  and a short bridge, walls leaning 40° and 65°).
- `examples/report.html`, the report on the test piece sliced without supports.

### Changed

- The slicer for a project that is not sliced is looked up in the usual places of Bambu Studio and
  OrcaSlicer on macOS and Windows and on the PATH; the viewer opens in the default browser on any
  system.
- The code moved into the `support_inspector` package; `./inspect` still works.

### Fixed

- A wall that changed feature on the way (inner wall, overhang wall, inner wall) was cut into
  separate paths, so its overhang stretch counted as held at no end: short bridges and held
  overhangs were reported as hanging. A change of feature no longer ends the path.

## [0.2.0] - 2026-11-18

### Added

- Selecting areas in the viewer: drag a box over the model, or take a risk area with its "+", give the selection a label, and save all of them as
  `NAME.selections.json` or copy them. The file names the inspected file and gives each labelled
  area's box, centre, line length, the risk areas it touches and sample points.

### Changed

- A selection box now takes exactly the surface seen inside it: the model's lines are cut into
  0.4 mm pieces and each is taken only if a ray from the eye reaches it first, within a settable
  reach (200 mm). Before, a whole printed line was taken when its middle was in the box, so
  selections spread far outside it. "Through the model" is gone.

### Fixed

- Only the first selection box worked: the following ones were tested against the first one's view.

## [0.1.0] - 2026-11-18

### Added

- The inspector: reads a slicer's G-code (or a sliced or unsliced 3MF, which Bambu Studio slices first)
  and checks every printed line of the model against the model's layer below and the supports under it.
- Three kinds of risk area: hanging (nothing below), bridge (held at both ends, longer than
  `--max-bridge`) and steep (leaning out beyond `--max-overhang-angle` with no support).
- Settings for the overhang angle, the longest bridge, the support gap and reach, and the smallest
  area reported.
- A numbered list of the areas on the terminal, optionally as JSON, and exit code 1 when there are any.
- A single-file 3D viewer of the model, the supports and the risk areas: click an area to go to it,
  risks show through what is in front of them, layer cuts, model opacity, `#area=N` links.
- `./inspect`, which sets up the Python environment on its first run.
