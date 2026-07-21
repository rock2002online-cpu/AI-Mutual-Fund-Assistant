from pathlib import Path


def test_gain_distribution_uses_current_streamlit_width_api() -> None:
    source = Path(
        "dashboard/components/analytics/gain_distribution.py"
    ).read_text(encoding="utf-8")

    assert "use_container_width" not in source
    assert 'width="stretch"' in source