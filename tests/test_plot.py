"""Plot tool tests: hermetic codegen; render test skips if matplotlib/pandas absent."""

from __future__ import annotations

import pytest

from tools.plot import core


def test_build_code_bar() -> None:
    code = core._build_code("/tmp/a.csv", "cultivar", "yield", "bar", "/tmp/o.png")
    assert 'matplotlib.use("Agg")' in code
    assert "ax.bar(" in code
    assert "dpi=300" in code


def test_build_code_scatter() -> None:
    code = core._build_code("a.csv", "x", "y", "scatter", "o.png")
    assert "ax.scatter(" in code


def test_render_bar(tmp_path) -> None:
    pytest.importorskip("pandas")
    pytest.importorskip("matplotlib")
    csv = tmp_path / "d.csv"
    csv.write_text("cultivar,yield\nA,10\nB,20\nC,15\n", encoding="utf-8")
    res = core.render(str(csv), "cultivar", "yield", out_dir=str(tmp_path))
    assert res["ok"] is True
    assert (tmp_path / "d_bar.png").exists()
    assert (tmp_path / "d_bar.py").exists()
