"""Runs in CI with Streamlit installed. Exercises widget changes and all charts."""
import subprocess
import sys
from pathlib import Path

import pytest


def test_three_chart_dashboard_loads_and_filters():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest
    from src.config import DB

    if not DB.exists():
        subprocess.run([sys.executable, "-m", "src.pipeline", "--synthetic"], check=True)
    at = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=90).run()
    assert not at.exception, [str(x.message) for x in at.exception]
    assert len(at.get("plotly_chart")) == 3
    assert len(at.selectbox) >= 3
    at.radio[0].set_value("visit").run()
    assert not at.exception
    at.selectbox[0].set_value("Womens E-Mail").run()
    assert not at.exception
    at.slider[0].set_value(20).run()
    assert not at.exception
    assert len(at.get("plotly_chart")) == 3
