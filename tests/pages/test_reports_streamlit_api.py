from pathlib import Path


def test_reports_page_uses_current_streamlit_width_api() -> None:
    reports_path = next(
        Path("pages").glob("7_*_Reports.py")
    )

    source = reports_path.read_text(
        encoding="utf-8"
    )

    assert "use_container_width" not in source
    assert source.count('width="stretch"') == 4