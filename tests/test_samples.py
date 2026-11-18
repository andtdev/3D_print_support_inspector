"""The checks on real slices of examples/test_piece.stl, kept gzipped in tests/samples."""
import gzip
import shutil
from pathlib import Path

from support_inspector.cli import analyse, options

SAMPLES = Path(__file__).parent / "samples"


def areas(name, tmp_path, *args):
    gcode = tmp_path / name
    with gzip.open(SAMPLES / (name + ".gz")) as src, open(gcode, "wb") as dst:
        shutil.copyfileobj(src, dst)
    return analyse(options().parse_args([str(gcode), *args]))[3]


def test_bambu_studio_without_supports(tmp_path):
    """The ledge hangs and the 16 mm bridge is too long; the 4 mm bridge and the 40° wall are fine."""
    found = areas("bambu_studio_supports_off.gcode", tmp_path, "--ignore-steep")
    assert sorted(r["kind"] for r in found) == ["bridge", "hanging"]
    assert all(abs(r["z"][0] - 9.2) < 0.01 for r in found)


def test_bambu_studio_with_supports(tmp_path):
    assert areas("bambu_studio_supports_on.gcode", tmp_path) == []


def test_orcaslicer_without_supports(tmp_path):
    found = areas("orcaslicer_supports_off.gcode", tmp_path, "--ignore-steep")
    assert sorted(r["kind"] for r in found) == ["bridge", "hanging"]
    assert all(abs(r["z"][0] - 9.2) < 0.01 for r in found)


def test_orcaslicer_with_supports(tmp_path):
    assert areas("orcaslicer_supports_on.gcode", tmp_path) == []


def test_prusaslicer_without_supports(tmp_path):
    """0.3 mm layers and thick bridges. The ledge's fill goes out and back as one bridge path, so
    the ledge counts as a bridge too."""
    found = areas("prusaslicer_supports_off.gcode", tmp_path, "--ignore-steep")
    assert [r["kind"] for r in found] == ["bridge", "bridge"]
    assert all(abs(r["z"][0] - 9.35) < 0.01 for r in found)


def test_prusaslicer_with_supports(tmp_path):
    """PrusaSlicer puts no support under what it prints as a bridge ("don't support bridges"): the
    long bridge stays in the air, and so does the middle of the ledge."""
    found = areas("prusaslicer_supports_on.gcode", tmp_path, "--ignore-steep")
    assert [r["kind"] for r in found] == ["bridge", "bridge"]
    assert found[0]["length"] > 200 and found[1]["length"] < 100


def test_cura_without_supports(tmp_path):
    """Cura fills a bridge with diagonal lines that end on the walls spanning the gap. Across the
    4 mm gap they are 5.7 mm long: over the default limit, within a limit of 6."""
    found = areas("cura_supports_off.gcode", tmp_path, "--ignore-steep")
    assert [(r["kind"], round(r["z"][0], 1)) for r in found] == [("hanging", 9.1), ("hanging", 9.1), ("bridge", 6.1)]
    found = areas("cura_supports_off.gcode", tmp_path, "--ignore-steep", "--max-bridge", "6")
    assert [r["kind"] for r in found] == ["hanging", "hanging"]


def test_cura_with_supports(tmp_path):
    assert areas("cura_supports_on.gcode", tmp_path) == []
