# Changelog

All notable changes to the 3D print support inspector. How it works and its settings are in `README.md`.

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
