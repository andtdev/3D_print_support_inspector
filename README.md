# 3D print support inspector

Finds the parts of a sliced print that nothing holds up, and shows them in a 3D viewer.

Painting an area for support, or switching supports on, does not mean a support ends up under it: the
slicer decides where the supports really go. So the inspector reads the slicer's result, the G-code,
and checks every printed line of the model against what lies directly below it.

## Use

    ./inspect plate.gcode
    ./inspect project.gcode.3mf      a sliced project exported from the slicer
    ./inspect project.3mf            not sliced yet: Bambu Studio slices it first

The first run sets up a Python environment with numpy and scipy in `.venv`. A four-part, 8-hour plate
takes about 10 seconds.

It prints the risk areas, writes `NAME.support_report.html` next to the input, opens it, and exits
with 1 when it found any area (0 when it found none), so a build script can stop on it:

    ./inspect print/module_print.3mf --no-open || echo "something hangs"

## What it reports

Every line of the model is cut into 0.2 mm pieces. A piece is held when the model's previous layer
lies under it, or a support layer does within the support gap. The rest falls into three kinds:

| Kind | Colour | Meaning |
| --- | --- | --- |
| hanging | red | Nothing below: the line is printed into the air. |
| bridge | orange | Held at both ends, but spanning more than `--max-bridge`. |
| steep | yellow | Leans out over the layer below by more than `--max-overhang-angle`, with no support under it. |

Not reported: the first layer, bridges up to `--max-bridge` held at both ends, the infill and the skin
that lies on the infill inside the part, steep overhangs less than `--min-steep-height` tall (rounded
edges), and areas with less than `--min-length` of risky line.

## The viewer

One HTML file, no installation; it needs a browser with WebGL 2. It shows the model's walls and
surfaces, the supports and the risk areas, each with its number from the list.

- Click an area in the list or its number in the view to go to it, seen from below.
- Drag turns, shift-drag or right-drag moves, the wheel zooms.
- "Risks show through" draws the risk areas through everything in front of them.
- "Cut above z" and "Cut below z" hide layers; "Model opacity" makes the model see-through.
- `report.html#area=3` opens on area 3.

## Settings

| Option | Default | |
| --- | --- | --- |
| `--max-overhang-angle` | 45 | Degrees from vertical a wall may lean out before it counts as steep. 40 also reports unsupported 45° chamfers. |
| `--max-bridge` | 5 | mm a line may span through the air when both ends are held. |
| `--support-gap` | 0.35 | mm a support's top may lie below a line and still hold it. Set it a little above the slicer's top z distance. |
| `--support-reach` | 0.6 | mm a line may lie beside the nearest support line and still be held. |
| `--hang-fraction` | 0.8 | A line hangs when it lies this fraction of its width, or more, beside the nearest line below. |
| `--min-length` | 3 | mm of risky line an area needs to be reported. |
| `--min-steep-height` | 0.6 | mm of height a steep overhang needs to be reported. |
| `--ignore-steep` | | Report only hanging lines and long bridges. |
| `--check-infill` | | Check the infill too. |
| `--resolution` | 0.2 | mm, the length of the pieces. |
| `--plate` | 1 | Plate of a 3MF. |
| `--slicer` | Bambu Studio in /Applications | The executable that slices a project that is not sliced. |
| `-o`, `--json`, `--no-open`, `--no-viewer`, `--viewer-infill` | | Output. |

`./inspect --help` lists them all.

## Limits

- Tested with Bambu Studio's G-code only. The comments of PrusaSlicer, OrcaSlicer and Cura are read
  too, but that is untested.
- It judges geometry, not printing: a line that is held may still print badly, for example on a
  support with a large z distance.
- The model in the viewer is drawn from the print's lines, without the infill.
