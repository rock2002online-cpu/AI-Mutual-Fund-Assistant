from pathlib import Path


def test_investment_vs_current_uses_current_streamlit_width_api() -> None:
    source = Path(
        "dashboard/components/analytics/investment_vs_current.py"
    ).read_text(encoding="utf-8")

    assert "use_container_width" not in source
    assert 'width="stretch"' in source