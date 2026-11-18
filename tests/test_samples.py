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
