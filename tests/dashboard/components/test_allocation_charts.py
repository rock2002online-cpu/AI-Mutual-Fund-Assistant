from pathlib import Path


def test_allocation_charts_use_current_streamlit_width_api() -> None:
    source = Path(
        "dashboard/components/allocation_charts.py"
    ).read_text(encoding="utf-8")

    assert "use_container_width" not in source
    assert source.count('width="stretch"') == 3