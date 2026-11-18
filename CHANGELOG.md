# Changelog

All notable changes to the 3D print support inspector. How it works and its settings are in `README.md`.

## [Unreleased]

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
