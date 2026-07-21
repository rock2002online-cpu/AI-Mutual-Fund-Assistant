"""
Tests for dashboard.components.analytics.history_charts.

These tests verify:

- Required schema validation.
- Chart-data preparation.
- Plotly figure construction.
- Streamlit rendering behavior.
- Empty and invalid history handling.
- Unique Streamlit chart keys.
- Graceful handling of figure-building and rendering failures.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import plotly.graph_objects as go
import pytest

from dashboard.components.analytics.history_charts import (
    DATE_COLUMN,
    HISTORY_SECTION_TITLE,
    PORTFOLIO_GROWTH_CHART_KEY,
    PORTFOLIO_GROWTH_CHART_TITLE,
    REQUIRED_HISTORY_COLUMNS,
    VALUE_COLUMN,
    _get_missing_columns,
    _prepare_history_for_chart,
    _validate_history_dataframe,
    build_portfolio_growth_figure,
    render_history_charts,
    render_portfolio_growth_chart,
)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def valid_history() -> pd.DataFrame:
    """
    Return valid normalized portfolio history.
    """

    return pd.DataFrame(
        {
            DATE_COLUMN: [
                "2025-01-01",
                "2025-02-01",
                "2025-03-01",
            ],
            VALUE_COLUMN: [
                100_000.0,
                110_000.0,
                105_000.0,
            ],
        }
    )


@pytest.fixture
def mocked_expander() -> MagicMock:
    """
    Return a mocked Streamlit expander context manager.
    """

    expander = MagicMock()
    expander.__enter__.return_value = expander
    expander.__exit__.return_value = False

    return expander


# ============================================================
# Constant Tests
# ============================================================


def test_history_chart_constants() -> None:
    """
    Public chart constants should remain stable.
    """

    assert DATE_COLUMN == "Date"
    assert VALUE_COLUMN == "Value"

    assert REQUIRED_HISTORY_COLUMNS == frozenset(
        {
            DATE_COLUMN,
            VALUE_COLUMN,
        }
    )

    assert (
        PORTFOLIO_GROWTH_CHART_KEY
        == "analytics_history_portfolio_growth_chart"
    )

    assert (
        PORTFOLIO_GROWTH_CHART_TITLE
        == "Portfolio Value Growth"
    )

    assert (
        HISTORY_SECTION_TITLE
        == "📈 Historical Portfolio Analytics"
    )


# ============================================================
# Missing Column Helper Tests
# ============================================================


def test_get_missing_columns_returns_empty_tuple() -> None:
    """
    No columns should be reported missing for a complete dataframe.
    """

    dataframe = pd.DataFrame(
        {
            DATE_COLUMN: [],
            VALUE_COLUMN: [],
        }
    )

    result = _get_missing_columns(
        dataframe,
        REQUIRED_HISTORY_COLUMNS,
    )

    assert result == ()


def test_get_missing_columns_returns_sorted_columns() -> None:
    """
    Missing columns should be returned alphabetically.
    """

    dataframe = pd.DataFrame(
        {
            "Other": [],
        }
    )

    result = _get_missing_columns(
        dataframe,
        {
            VALUE_COLUMN,
            DATE_COLUMN,
        },
    )

    assert result == (
        DATE_COLUMN,
        VALUE_COLUMN,
    )


# ============================================================
# Validation Tests
# ============================================================


def test_validate_history_rejects_non_dataframe() -> None:
    """
    History validation should reject unsupported input types.
    """

    with pytest.raises(
        TypeError,
        match="history must be a pandas DataFrame",
    ):
        _validate_history_dataframe(
            []  # type: ignore[arg-type]
        )


def test_validate_history_handles_empty_dataframe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Empty history should display an informational message.
    """

    info_mock = MagicMock()

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_charts.st.info",
        info_mock,
    )

    result = _validate_history_dataframe(
        pd.DataFrame()
    )

    assert result is False
    info_mock.assert_called_once()

    assert "No historical portfolio data" in (
        info_mock.call_args.args[0]
    )


@pytest.mark.parametrize(
    "missing_column",
    [
        DATE_COLUMN,
        VALUE_COLUMN,
    ],
)
def test_validate_history_handles_missing_column(
    monkeypatch: pytest.MonkeyPatch,
    missing_column: str,
) -> None:
    """
    Missing required columns should display a warning.
    """

    history = pd.DataFrame(
        {
            DATE_COLUMN: ["2025-01-01"],
            VALUE_COLUMN: [100_000.0],
        }
    ).drop(
        columns=[missing_column]
    )

    warning_mock = MagicMock()

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_charts.st.warning",
        warning_mock,
    )

    result = _validate_history_dataframe(
        history
    )

    assert result is False
    warning_mock.assert_called_once()

    assert missing_column in (
        warning_mock.call_args.args[0]
    )


def test_validate_history_rejects_all_missing_dates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    History containing no valid date values should not render.
    """

    history = pd.DataFrame(
        {
            DATE_COLUMN: [
                None,
                None,
            ],
            VALUE_COLUMN: [
                100_000.0,
                110_000.0,
            ],
        }
    )

    warning_mock = MagicMock()

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_charts.st.warning",
        warning_mock,
    )

    result = _validate_history_dataframe(
        history
    )

    assert result is False
    warning_mock.assert_called_once()

    assert "no valid dates" in (
        warning_mock.call_args.args[0].lower()
    )


def test_validate_history_rejects_all_missing_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    History containing no valid portfolio values should not render.
    """

    history = pd.DataFrame(
        {
            DATE_COLUMN: [
                "2025-01-01",
                "2025-02-01",
            ],
            VALUE_COLUMN: [
                None,
                None,
            ],
        }
    )

    warning_mock = MagicMock()

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_charts.st.warning",
        warning_mock,
    )

    result = _validate_history_dataframe(
        history
    )

    assert result is False
    warning_mock.assert_called_once()

    assert "no valid portfolio values" in (
        warning_mock.call_args.args[0].lower()
    )


def test_validate_history_accepts_valid_dataframe(
    valid_history: pd.DataFrame,
) -> None:
    """
    Valid normalized history should pass validation.
    """

    assert (
        _validate_history_dataframe(
            valid_history
        )
        is True
    )


# ============================================================
# Chart Preparation Tests
# ============================================================


def test_prepare_history_does_not_mutate_input() -> None:
    """
    Chart preparation should leave the caller's dataframe unchanged.
    """

    history = pd.DataFrame(
        {
            DATE_COLUMN: [
                "2025-02-01",
                "2025-01-01",
            ],
            VALUE_COLUMN: [
                "110000",
                "100000",
            ],
            "Extra": [
                "second",
                "first",
            ],
        }
    )

    original = history.copy(
        deep=True
    )

    _prepare_history_for_chart(
        history
    )

    pd.testing.assert_frame_equal(
        history,
        original,
    )


def test_prepare_history_selects_canonical_columns() -> None:
    """
    Extra source columns should not appear in chart data.
    """

    history = pd.DataFrame(
        {
            DATE_COLUMN: ["2025-01-01"],
            VALUE_COLUMN: [100_000.0],
            "Extra": ["ignored"],
        }
    )

    result = _prepare_history_for_chart(
        history
    )

    assert list(result.columns) == [
        DATE_COLUMN,
        VALUE_COLUMN,
    ]


def test_prepare_history_converts_types() -> None:
    """
    Dates and values should be converted into chart-compatible types.
    """

    history = pd.DataFrame(
        {
            DATE_COLUMN: [
                "2025-01-01",
                "2025-02-01",
            ],
            VALUE_COLUMN: [
                "100000.50",
                "110000.75",
            ],
        }
    )

    result = _prepare_history_for_chart(
        history
    )

    assert pd.api.types.is_datetime64_any_dtype(
        result[DATE_COLUMN]
    )

    assert pd.api.types.is_numeric_dtype(
        result[VALUE_COLUMN]
    )

    assert result[VALUE_COLUMN].tolist() == [
        100_000.50,
        110_000.75,
    ]


def test_prepare_history_removes_invalid_rows() -> None:
    """
    Rows with invalid dates or values should be removed.
    """

    history = pd.DataFrame(
        {
            DATE_COLUMN: [
                "2025-01-01",
                "invalid-date",
                "2025-03-01",
            ],
            VALUE_COLUMN: [
                100_000.0,
                110_000.0,
                "invalid-value",
            ],
        }
    )

    result = _prepare_history_for_chart(
        history
    )

    assert len(result) == 1
    assert result.iloc[0][VALUE_COLUMN] == 100_000.0


def test_prepare_history_sorts_chronologically() -> None:
    """
    Chart records should be sorted by date.
    """

    history = pd.DataFrame(
        {
            DATE_COLUMN: [
                "2025-03-01",
                "2025-01-01",
                "2025-02-01",
            ],
            VALUE_COLUMN: [
                130_000.0,
                100_000.0,
                120_000.0,
            ],
        }
    )

    result = _prepare_history_for_chart(
        history
    )

    assert result[DATE_COLUMN].dt.date.tolist() == [
        date(2025, 1, 1),
        date(2025, 2, 1),
        date(2025, 3, 1),
    ]


def test_prepare_history_keeps_last_duplicate_date() -> None:
    """
    The final record for each duplicate date should be retained.
    """

    history = pd.DataFrame(
        {
            DATE_COLUMN: [
                "2025-01-01",
                "2025-01-01",
                "2025-02-01",
            ],
            VALUE_COLUMN: [
                100_000.0,
                105_000.0,
                110_000.0,
            ],
        }
    )

    result = _prepare_history_for_chart(
        history
    )

    assert len(result) == 2
    assert result.iloc[0][VALUE_COLUMN] == 105_000.0


def test_prepare_history_raises_when_no_records_remain() -> None:
    """
    Chart preparation should fail when no plottable data remains.
    """

    history = pd.DataFrame(
        {
            DATE_COLUMN: [
                "invalid",
                None,
            ],
            VALUE_COLUMN: [
                "invalid",
                None,
            ],
        }
    )

    with pytest.raises(
        ValueError,
        match="no plottable records",
    ):
        _prepare_history_for_chart(
            history
        )


# ============================================================
# Figure Construction Tests
# ============================================================


def test_build_figure_rejects_non_dataframe() -> None:
    """
    Figure construction should require a pandas DataFrame.
    """

    with pytest.raises(
        TypeError,
        match="history must be a pandas DataFrame",
    ):
        build_portfolio_growth_figure(
            []  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "missing_column",
    [
        DATE_COLUMN,
        VALUE_COLUMN,
    ],
)
def test_build_figure_rejects_missing_columns(
    missing_column: str,
) -> None:
    """
    Figure construction should reject incomplete history schemas.
    """

    history = pd.DataFrame(
        {
            DATE_COLUMN: ["2025-01-01"],
            VALUE_COLUMN: [100_000.0],
        }
    ).drop(
        columns=[missing_column]
    )

    with pytest.raises(
        ValueError,
        match="missing required column",
    ):
        build_portfolio_growth_figure(
            history
        )


def test_build_figure_returns_plotly_figure(
    valid_history: pd.DataFrame,
) -> None:
    """
    Valid history should produce a Plotly figure.
    """

    figure = build_portfolio_growth_figure(
        valid_history
    )

    assert isinstance(
        figure,
        go.Figure,
    )


def test_build_figure_contains_one_trace(
    valid_history: pd.DataFrame,
) -> None:
    """
    The portfolio-growth figure should contain one series.
    """

    figure = build_portfolio_growth_figure(
        valid_history
    )

    assert len(figure.data) == 1


def test_build_figure_trace_configuration(
    valid_history: pd.DataFrame,
) -> None:
    """
    The chart trace should use the expected name and display mode.
    """

    figure = build_portfolio_growth_figure(
        valid_history
    )

    trace = figure.data[0]

    assert trace.name == "Portfolio Value"
    assert trace.mode == "lines+markers"
    assert trace.line.width == 3
    assert trace.marker.size == 7


def test_build_figure_uses_chronological_data() -> None:
    """
    Figure coordinates should be sorted chronologically.
    """

    history = pd.DataFrame(
        {
            DATE_COLUMN: [
                "2025-03-01",
                "2025-01-01",
                "2025-02-01",
            ],
            VALUE_COLUMN: [
                130_000.0,
                100_000.0,
                120_000.0,
            ],
        }
    )

    figure = build_portfolio_growth_figure(
        history
    )

    trace = figure.data[0]

    assert list(
        pd.to_datetime(trace.x).date
    ) == [
        date(2025, 1, 1),
        date(2025, 2, 1),
        date(2025, 3, 1),
    ]

    assert list(trace.y) == [
        100_000.0,
        120_000.0,
        130_000.0,
    ]


def test_build_figure_layout(
    valid_history: pd.DataFrame,
) -> None:
    """
    Chart title, axes, height, and hover mode should be configured.
    """

    figure = build_portfolio_growth_figure(
        valid_history
    )

    assert (
        figure.layout.title.text
        == PORTFOLIO_GROWTH_CHART_TITLE
    )

    assert (
        figure.layout.xaxis.title.text
        == "Date"
    )

    assert (
        figure.layout.yaxis.title.text
        == "Portfolio Value (₹)"
    )

    assert figure.layout.height == 460
    assert figure.layout.hovermode == "x unified"


def test_build_figure_currency_axis_formatting(
    valid_history: pd.DataFrame,
) -> None:
    """
    The y-axis should use rupee currency formatting.
    """

    figure = build_portfolio_growth_figure(
        valid_history
    )

    assert figure.layout.yaxis.tickprefix == "₹"
    assert figure.layout.yaxis.tickformat == ",.2f"
    assert figure.layout.yaxis.rangemode == "tozero"


# ============================================================
# Individual Renderer Tests
# ============================================================


def test_render_portfolio_growth_chart_returns_false_for_empty_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Empty history should not attempt Plotly rendering.
    """

    info_mock = MagicMock()
    plotly_mock = MagicMock()

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_charts.st.info",
        info_mock,
    )

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_charts.st.plotly_chart",
        plotly_mock,
    )

    result = render_portfolio_growth_chart(
        pd.DataFrame()
    )

    assert result is False
    info_mock.assert_called_once()
    plotly_mock.assert_not_called()


def test_render_portfolio_growth_chart_renders_valid_figure(
    monkeypatch: pytest.MonkeyPatch,
    valid_history: pd.DataFrame,
) -> None:
    """
    Valid history should render one Plotly chart with its unique key.
    """

    plotly_mock = MagicMock()

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_charts.st.plotly_chart",
        plotly_mock,
    )

    result = render_portfolio_growth_chart(
        valid_history
    )

    assert result is True
    plotly_mock.assert_called_once()

    call = plotly_mock.call_args

    assert isinstance(
        call.args[0],
        go.Figure,
    )

    assert call.kwargs["width"] == "stretch"
    assert "use_container_width" not in call.kwargs

    assert (
        call.kwargs["key"]
        == PORTFOLIO_GROWTH_CHART_KEY
    )


def test_render_portfolio_growth_chart_handles_build_error(
    monkeypatch: pytest.MonkeyPatch,
    valid_history: pd.DataFrame,
) -> None:
    """
    Invalid chart preparation should display a warning and return False.
    """

    warning_mock = MagicMock()

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_charts.build_portfolio_growth_figure",
        MagicMock(
            side_effect=ValueError(
                "no chart data"
            )
        ),
    )

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_charts.st.warning",
        warning_mock,
    )

    result = render_portfolio_growth_chart(
        valid_history
    )

    assert result is False
    warning_mock.assert_called_once()


def test_render_portfolio_growth_chart_handles_unexpected_build_error(
    monkeypatch: pytest.MonkeyPatch,
    valid_history: pd.DataFrame,
    mocked_expander: MagicMock,
) -> None:
    """
    Unexpected figure-building errors should be displayed safely.
    """

    error_mock = MagicMock()
    exception_mock = MagicMock()

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_charts.build_portfolio_growth_figure",
        MagicMock(
            side_effect=RuntimeError(
                "build failed"
            )
        ),
    )

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_charts.st.error",
        error_mock,
    )

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_charts.st.expander",
        MagicMock(
            return_value=mocked_expander
        ),
    )

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_charts.st.exception",
        exception_mock,
    )

    result = render_portfolio_growth_chart(
        valid_history
    )

    assert result is False
    error_mock.assert_called_once()
    exception_mock.assert_called_once()


def test_render_portfolio_growth_chart_handles_streamlit_error(
    monkeypatch: pytest.MonkeyPatch,
    valid_history: pd.DataFrame,
    mocked_expander: MagicMock,
) -> None:
    """
    Plotly rendering failures should be isolated and reported.
    """

    error_mock = MagicMock()
    exception_mock = MagicMock()

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_charts.st.plotly_chart",
        MagicMock(
            side_effect=RuntimeError(
                "render failed"
            )
        ),
    )

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_charts.st.error",
        error_mock,
    )

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_charts.st.expander",
        MagicMock(
            return_value=mocked_expander
        ),
    )

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_charts.st.exception",
        exception_mock,
    )

    result = render_portfolio_growth_chart(
        valid_history
    )

    assert result is False
    error_mock.assert_called_once()
    exception_mock.assert_called_once()


# ============================================================
# Composite Renderer Tests
# ============================================================


def test_render_history_charts_rejects_invalid_type() -> None:
    """
    Composite renderer should validate its input.
    """

    with pytest.raises(
        TypeError,
        match="history must be a pandas DataFrame",
    ):
        render_history_charts(
            None  # type: ignore[arg-type]
        )


def test_render_history_charts_returns_false_for_empty_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Empty history should not render the section heading or chart.
    """

    info_mock = MagicMock()
    subheader_mock = MagicMock()
    chart_mock = MagicMock()

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_charts.st.info",
        info_mock,
    )

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_charts.st.subheader",
        subheader_mock,
    )

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_charts.render_portfolio_growth_chart",
        chart_mock,
    )

    result = render_history_charts(
        pd.DataFrame()
    )

    assert result is False
    info_mock.assert_called_once()
    subheader_mock.assert_not_called()
    chart_mock.assert_not_called()


def test_render_history_charts_orchestrates_section(
    monkeypatch: pytest.MonkeyPatch,
    valid_history: pd.DataFrame,
) -> None:
    """
    Composite renderer should display the section and delegate chart rendering.
    """

    subheader_mock = MagicMock()
    caption_mock = MagicMock()
    chart_mock = MagicMock(
        return_value=True
    )

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_charts.st.subheader",
        subheader_mock,
    )

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_charts.st.caption",
        caption_mock,
    )

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_charts.render_portfolio_growth_chart",
        chart_mock,
    )

    result = render_history_charts(
        valid_history
    )

    assert result is True

    subheader_mock.assert_called_once_with(
        HISTORY_SECTION_TITLE
    )

    caption_mock.assert_called_once()

    assert "Track how the total portfolio value" in (
        caption_mock.call_args.args[0]
    )

    chart_mock.assert_called_once_with(
        valid_history
    )


def test_render_history_charts_returns_chart_status(
    monkeypatch: pytest.MonkeyPatch,
    valid_history: pd.DataFrame,
) -> None:
    """
    Composite renderer should return the individual chart renderer's status.
    """

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_charts.st.subheader",
        MagicMock(),
    )

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_charts.st.caption",
        MagicMock(),
    )

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_charts.render_portfolio_growth_chart",
        MagicMock(
            return_value=False
        ),
    )

    result = render_history_charts(
        valid_history
    )

    assert result is False