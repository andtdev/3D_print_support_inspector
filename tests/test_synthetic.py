"""The checks on small hand-written G-code, in every slicer's comment style."""
import pytest

from gcode_maker import STYLES, Gcode
from support_inspector.cli import analyse, options


def areas(path, *args):
    return analyse(options().parse_args([path, *args]))[3]


def kinds(path, *args):
    return sorted(r["kind"] for r in areas(path, *args))


@pytest.fixture(params=sorted(STYLES))
def g(request):
    return Gcode(request.param)


def test_cube_is_clean(g, tmp_path):
    for n in range(20):
        g.layer(n)
        g.box("wall", 0, 0, 10, 10)
    assert kinds(g.write(tmp_path / "a.gcode")) == []


def ledge(g, support):
    """A 10 mm tower with a ledge reaching 8 mm out from layer 20 on."""
    for n in range(25):
        g.layer(n)
        g.box("wall", 0, 0, 10, 10)
        if n >= 20:
            g.box("wall", 10, 0, 18, 10)
        elif support and n < 20:
            g.box("support", 10.5, 0, 18, 10)


def test_ledge_hangs(g, tmp_path):
    ledge(g, support=False)
    found = areas(g.write(tmp_path / "a.gcode"))
    assert [r["kind"] for r in found] == ["hanging"]
    assert found[0]["z"][0] == pytest.approx(4.2)
    assert 10 < found[0]["center"][0] < 18


def test_supported_ledge_is_clean(g, tmp_path):
    ledge(g, support=True)
    assert kinds(g.write(tmp_path / "a.gcode")) == []


def bridge(g, span):
    for n in range(12):
        g.layer(n)
        g.box("wall", 0, 0, 5, 6)
        g.box("wall", 5 + span, 0, 10 + span, 6)
        if n >= 10:
            y = 0.0
            while y <= 6:
                g.path("bridge", [(0.5, y), (9.5 + span, y)])
                y += 0.42


def test_long_bridge(g, tmp_path):
    bridge(g, 14)
    assert kinds(g.write(tmp_path / "a.gcode")) == ["bridge"]


def test_short_bridge_is_fine(g, tmp_path):
    bridge(g, 4)
    assert kinds(g.write(tmp_path / "a.gcode")) == []


def test_longer_bridges_can_be_allowed(g, tmp_path):
    bridge(g, 14)
    assert kinds(g.write(tmp_path / "a.gcode"), "--max-bridge", "20") == []


def leaning_wall(g, degrees):
    """A wall that leans out along x by the angle from vertical, 4 mm tall."""
    import math
    step = 0.2 * math.tan(math.radians(degrees))
    for n in range(30):
        g.layer(n)
        x = max(0, n - 10) * step
        g.path("wall", [(x, 0), (x, 20)])
        g.path("wall", [(x - 0.42, 0), (x - 0.42, 20)])


def test_steep_wall(g, tmp_path):
    leaning_wall(g, 55)
    assert kinds(g.write(tmp_path / "a.gcode")) == ["steep"]


def test_gentle_wall_is_fine(g, tmp_path):
    leaning_wall(g, 35)
    assert kinds(g.write(tmp_path / "a.gcode")) == []


def test_steep_can_be_ignored(g, tmp_path):
    leaning_wall(g, 55)
    assert kinds(g.write(tmp_path / "a.gcode"), "--ignore-steep") == []
