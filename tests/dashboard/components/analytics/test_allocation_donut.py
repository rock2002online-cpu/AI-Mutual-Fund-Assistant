from pathlib import Path


def test_allocation_donut_uses_current_streamlit_width_api() -> None:
    source = Path(
        "dashboard/components/analytics/allocation_donut.py"
    ).read_text(encoding="utf-8")

    assert "use_container_width" not in source
    assert 'width="stretch"' in source