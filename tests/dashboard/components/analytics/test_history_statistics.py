"""
Tests for dashboard.components.analytics.history_statistics.

These tests verify:

- Date, currency, percentage, integer, and duration formatting.
- Optional CAGR, drawdown, and volatility display values.
- Positive, negative, and zero growth deltas.
- Component input validation.
- Streamlit KPI rendering.
- Graceful display of unavailable optional analytics.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from dashboard.components.analytics.history_statistics import (
    CURRENCY_SYMBOL,
    HISTORY_STATISTICS_CAPTION,
    HISTORY_STATISTICS_TITLE,
    UNAVAILABLE_VALUE,
    _format_currency,
    _format_date,
    _format_duration,
    _format_integer,
    _format_percentage,
    _get_annualised_volatility_value,
    _get_cagr_value,
    _get_growth_delta,
    _get_maximum_drawdown_value,
    _render_history_coverage_row,
    _render_performance_risk_row,
    _render_value_summary_row,
    _validate_result,
    render_history_statistics,
)
from services.analytics.history_analytics import (
    HistoryAnalyticsResult,
)


# ============================================================
# Fixtures and Test Helpers
# ============================================================


@pytest.fixture
def complete_result() -> HistoryAnalyticsResult:
    """
    Return a complete historical analytics result.

    SimpleNamespace objects are sufficient for optional nested analytics
    because the presentation component only consumes their documented
    attributes.
    """

    return HistoryAnalyticsResult(
        observation_count=5,
        start_date=date(2024, 1, 1),
        end_date=date(2025, 1, 1),
        duration_days=366,
        starting_value=100_000.0,
        latest_value=125_000.0,
        minimum_value=95_000.0,
        maximum_value=130_000.0,
        average_value=110_000.0,
        absolute_growth=25_000.0,
        total_growth_percent=25.0,
        periodic_returns=(
            0.10,
            -0.05,
            0.12,
            0.08,
        ),
        cagr=SimpleNamespace(
            cagr_percent=24.91
        ),
        drawdown=SimpleNamespace(
            maximum_drawdown_percent=-8.75
        ),
        volatility=SimpleNamespace(
            annualised_volatility_percent=13.42
        ),
        periods_per_year=252,
    )


@pytest.fixture
def summary_only_result() -> HistoryAnalyticsResult:
    """
    Return a result without optional CAGR, drawdown, or volatility metrics.
    """

    return HistoryAnalyticsResult(
        observation_count=1,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 1),
        duration_days=0,
        starting_value=100_000.0,
        latest_value=100_000.0,
        minimum_value=100_000.0,
        maximum_value=100_000.0,
        average_value=100_000.0,
        absolute_growth=0.0,
        total_growth_percent=0.0,
        periodic_returns=(),
        cagr=None,
        drawdown=None,
        volatility=None,
        periods_per_year=252,
    )


def _create_streamlit_columns(
    count: int = 4,
) -> list[MagicMock]:
    """
    Create mocked Streamlit column context managers.
    """

    columns: list[MagicMock] = []

    for _ in range(count):
        column = MagicMock()
        column.__enter__.return_value = column
        column.__exit__.return_value = False
        columns.append(column)

    return columns


# ============================================================
# Constant Tests
# ============================================================


def test_display_constants_are_defined() -> None:
    """
    Public display constants should remain stable.
    """

    assert CURRENCY_SYMBOL == "₹"

    assert (
        HISTORY_STATISTICS_TITLE
        == "📊 Historical Portfolio Summary"
    )

    assert "performance" in (
        HISTORY_STATISTICS_CAPTION.lower()
    )

    assert UNAVAILABLE_VALUE == "Unavailable"


# ============================================================
# Date Formatting Tests
# ============================================================


def test_format_date_returns_human_readable_date() -> None:
    """
    Dates should use DD Mon YYYY format.
    """

    result = _format_date(
        date(2025, 7, 16)
    )

    assert result == "16 Jul 2025"


@pytest.mark.parametrize(
    "invalid_value",
    [
        "2025-01-01",
        20250101,
        None,
    ],
)
def test_format_date_rejects_non_date(
    invalid_value: object,
) -> None:
    """
    Unsupported date values should be rejected.
    """

    with pytest.raises(
        TypeError,
        match="value must be a date",
    ):
        _format_date(
            invalid_value  # type: ignore[arg-type]
        )


# ============================================================
# Currency Formatting Tests
# ============================================================


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1000, "₹1,000.00"),
        (123456.789, "₹123,456.79"),
        (0.0, "₹0.00"),
        (-2500.5, "₹-2,500.50"),
    ],
)
def test_format_currency(
    value: float,
    expected: str,
) -> None:
    """
    Numeric values should be formatted as rupee currency.
    """

    assert _format_currency(value) == expected


@pytest.mark.parametrize(
    "invalid_value",
    [
        True,
        False,
        "1000",
        None,
        [],
    ],
)
def test_format_currency_rejects_non_numeric(
    invalid_value: object,
) -> None:
    """
    Unsupported currency values should be rejected.
    """

    with pytest.raises(
        TypeError,
        match="value must be numeric",
    ):
        _format_currency(
            invalid_value  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "invalid_value",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_format_currency_rejects_non_finite(
    invalid_value: float,
) -> None:
    """
    NaN and infinite amounts should be rejected.
    """

    with pytest.raises(
        ValueError,
        match="value must be finite",
    ):
        _format_currency(
            invalid_value
        )


# ============================================================
# Percentage Formatting Tests
# ============================================================


@pytest.mark.parametrize(
    ("value", "include_sign", "expected"),
    [
        (12.345, False, "12.35%"),
        (12.345, True, "+12.35%"),
        (-4.5, False, "-4.50%"),
        (-4.5, True, "-4.50%"),
        (0.0, False, "0.00%"),
        (0.0, True, "+0.00%"),
    ],
)
def test_format_percentage(
    value: float,
    include_sign: bool,
    expected: str,
) -> None:
    """
    Percentage values should be formatted to two decimal places.
    """

    assert (
        _format_percentage(
            value,
            include_sign=include_sign,
        )
        == expected
    )


@pytest.mark.parametrize(
    "invalid_value",
    [
        True,
        "12.5",
        None,
        {},
    ],
)
def test_format_percentage_rejects_non_numeric(
    invalid_value: object,
) -> None:
    """
    Unsupported percentage values should be rejected.
    """

    with pytest.raises(
        TypeError,
        match="value must be numeric",
    ):
        _format_percentage(
            invalid_value  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "invalid_value",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_format_percentage_rejects_non_finite(
    invalid_value: float,
) -> None:
    """
    Non-finite percentage values should be rejected.
    """

    with pytest.raises(
        ValueError,
        match="value must be finite",
    ):
        _format_percentage(
            invalid_value
        )


# ============================================================
# Integer Formatting Tests
# ============================================================


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "0"),
        (1, "1"),
        (1000, "1,000"),
        (1_000_000, "1,000,000"),
        (-5000, "-5,000"),
    ],
)
def test_format_integer(
    value: int,
    expected: str,
) -> None:
    """
    Integers should use thousands separators.
    """

    assert _format_integer(value) == expected


@pytest.mark.parametrize(
    "invalid_value",
    [
        True,
        1.0,
        "1",
        None,
    ],
)
def test_format_integer_rejects_non_integer(
    invalid_value: object,
) -> None:
    """
    Integer formatting should reject unsupported types.
    """

    with pytest.raises(
        TypeError,
        match="value must be an integer",
    ):
        _format_integer(
            invalid_value  # type: ignore[arg-type]
        )


# ============================================================
# Duration Formatting Tests
# ============================================================


@pytest.mark.parametrize(
    ("duration_days", "expected"),
    [
        (0, "0 days"),
        (1, "1 day"),
        (2, "2 days"),
        (364, "364 days"),
        (365, "1 year"),
        (366, "1 year, 1 day"),
        (730, "2 years"),
        (731, "2 years, 1 day"),
        (800, "2 years, 70 days"),
    ],
)
def test_format_duration(
    duration_days: int,
    expected: str,
) -> None:
    """
    Durations should be formatted into readable years and days.
    """

    assert (
        _format_duration(
            duration_days
        )
        == expected
    )


@pytest.mark.parametrize(
    "invalid_value",
    [
        True,
        365.0,
        "365",
        None,
    ],
)
def test_format_duration_rejects_non_integer(
    invalid_value: object,
) -> None:
    """
    Duration formatting should require an integer.
    """

    with pytest.raises(
        TypeError,
        match="duration_days must be an integer",
    ):
        _format_duration(
            invalid_value  # type: ignore[arg-type]
        )


def test_format_duration_rejects_negative_value() -> None:
    """
    Negative historical durations are invalid.
    """

    with pytest.raises(
        ValueError,
        match="cannot be negative",
    ):
        _format_duration(
            -1
        )


# ============================================================
# Optional Analytics Formatting Tests
# ============================================================


def test_get_cagr_value_returns_formatted_percentage(
    complete_result: HistoryAnalyticsResult,
) -> None:
    """
    Available CAGR should be formatted with a sign.
    """

    assert (
        _get_cagr_value(
            complete_result
        )
        == "+24.91%"
    )


def test_get_cagr_value_returns_unavailable(
    summary_only_result: HistoryAnalyticsResult,
) -> None:
    """
    Missing CAGR should use the unavailable label.
    """

    assert (
        _get_cagr_value(
            summary_only_result
        )
        == UNAVAILABLE_VALUE
    )


def test_get_maximum_drawdown_value_returns_percentage(
    complete_result: HistoryAnalyticsResult,
) -> None:
    """
    Available drawdown should be formatted as a percentage.
    """

    assert (
        _get_maximum_drawdown_value(
            complete_result
        )
        == "-8.75%"
    )


def test_get_maximum_drawdown_value_returns_unavailable(
    summary_only_result: HistoryAnalyticsResult,
) -> None:
    """
    Missing drawdown should use the unavailable label.
    """

    assert (
        _get_maximum_drawdown_value(
            summary_only_result
        )
        == UNAVAILABLE_VALUE
    )


def test_get_annualised_volatility_value_returns_percentage(
    complete_result: HistoryAnalyticsResult,
) -> None:
    """
    Available annualised volatility should be formatted.
    """

    assert (
        _get_annualised_volatility_value(
            complete_result
        )
        == "13.42%"
    )


def test_get_annualised_volatility_value_returns_unavailable(
    summary_only_result: HistoryAnalyticsResult,
) -> None:
    """
    Missing volatility should use the unavailable label.
    """

    assert (
        _get_annualised_volatility_value(
            summary_only_result
        )
        == UNAVAILABLE_VALUE
    )


# ============================================================
# Growth Delta Tests
# ============================================================


def test_get_growth_delta_adds_positive_sign(
    complete_result: HistoryAnalyticsResult,
) -> None:
    """
    Positive growth should include an explicit plus sign.
    """

    assert (
        _get_growth_delta(
            complete_result
        )
        == "+₹25,000.00"
    )


def test_get_growth_delta_formats_zero_without_plus(
    summary_only_result: HistoryAnalyticsResult,
) -> None:
    """
    Zero growth should not include a positive sign.
    """

    assert (
        _get_growth_delta(
            summary_only_result
        )
        == "₹0.00"
    )


def test_get_growth_delta_formats_negative_value() -> None:
    """
    Negative growth should retain the currency formatter's minus sign.
    """

    result = HistoryAnalyticsResult(
        observation_count=2,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 2, 1),
        duration_days=31,
        starting_value=100_000.0,
        latest_value=90_000.0,
        minimum_value=90_000.0,
        maximum_value=100_000.0,
        average_value=95_000.0,
        absolute_growth=-10_000.0,
        total_growth_percent=-10.0,
        periodic_returns=(),
        cagr=None,
        drawdown=None,
        volatility=None,
        periods_per_year=252,
    )

    assert (
        _get_growth_delta(result)
        == "₹-10,000.00"
    )


# ============================================================
# Input Validation Tests
# ============================================================


def test_validate_result_accepts_history_result(
    complete_result: HistoryAnalyticsResult,
) -> None:
    """
    A valid HistoryAnalyticsResult should be accepted.
    """

    assert (
        _validate_result(
            complete_result
        )
        is None
    )


@pytest.mark.parametrize(
    "invalid_result",
    [
        None,
        {},
        [],
        SimpleNamespace(),
    ],
)
def test_validate_result_rejects_invalid_type(
    invalid_result: object,
) -> None:
    """
    Unsupported result objects should be rejected.
    """

    with pytest.raises(
        TypeError,
        match="HistoryAnalyticsResult",
    ):
        _validate_result(
            invalid_result  # type: ignore[arg-type]
        )


# ============================================================
# KPI Row Rendering Tests
# ============================================================


def test_render_history_coverage_row_renders_four_metrics(
    monkeypatch: pytest.MonkeyPatch,
    complete_result: HistoryAnalyticsResult,
) -> None:
    """
    Coverage row should render four correctly labelled KPI cards.
    """

    columns = _create_streamlit_columns()

    columns_mock = MagicMock(
        return_value=columns
    )
    metric_mock = MagicMock()

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_statistics.st.columns",
        columns_mock,
    )

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_statistics.st.metric",
        metric_mock,
    )

    _render_history_coverage_row(
        complete_result
    )

    columns_mock.assert_called_once_with(4)

    assert metric_mock.call_count == 4

    metric_mock.assert_any_call(
        label="First Snapshot",
        value="01 Jan 2024",
    )

    metric_mock.assert_any_call(
        label="Latest Snapshot",
        value="01 Jan 2025",
    )

    metric_mock.assert_any_call(
        label="Observations",
        value="5",
    )

    metric_mock.assert_any_call(
        label="History Duration",
        value="1 year, 1 day",
    )


def test_render_value_summary_row_renders_four_metrics(
    monkeypatch: pytest.MonkeyPatch,
    complete_result: HistoryAnalyticsResult,
) -> None:
    """
    Value summary row should render four portfolio-value KPI cards.
    """

    columns = _create_streamlit_columns()

    columns_mock = MagicMock(
        return_value=columns
    )
    metric_mock = MagicMock()

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_statistics.st.columns",
        columns_mock,
    )

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_statistics.st.metric",
        metric_mock,
    )

    _render_value_summary_row(
        complete_result
    )

    columns_mock.assert_called_once_with(4)

    assert metric_mock.call_count == 4

    metric_mock.assert_any_call(
        label="Latest Value",
        value="₹125,000.00",
        delta="+₹25,000.00",
    )

    metric_mock.assert_any_call(
        label="Highest Value",
        value="₹130,000.00",
    )

    metric_mock.assert_any_call(
        label="Lowest Value",
        value="₹95,000.00",
    )

    metric_mock.assert_any_call(
        label="Average Value",
        value="₹110,000.00",
    )


def test_render_performance_risk_row_renders_four_metrics(
    monkeypatch: pytest.MonkeyPatch,
    complete_result: HistoryAnalyticsResult,
) -> None:
    """
    Performance row should render growth and risk KPI cards.
    """

    columns = _create_streamlit_columns()

    columns_mock = MagicMock(
        return_value=columns
    )
    metric_mock = MagicMock()

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_statistics.st.columns",
        columns_mock,
    )

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_statistics.st.metric",
        metric_mock,
    )

    _render_performance_risk_row(
        complete_result
    )

    columns_mock.assert_called_once_with(4)

    assert metric_mock.call_count == 4

    metric_mock.assert_any_call(
        label="Total Growth",
        value="+25.00%",
        delta="+₹25,000.00",
    )

    cagr_call = next(
        call
        for call in metric_mock.call_args_list
        if call.kwargs.get("label")
        == "Historical CAGR"
    )

    assert cagr_call.kwargs["value"] == "+24.91%"
    assert "Annualised" in cagr_call.kwargs["help"]

    drawdown_call = next(
        call
        for call in metric_mock.call_args_list
        if call.kwargs.get("label")
        == "Maximum Drawdown"
    )

    assert drawdown_call.kwargs["value"] == "-8.75%"
    assert "decline" in drawdown_call.kwargs["help"]

    volatility_call = next(
        call
        for call in metric_mock.call_args_list
        if call.kwargs.get("label")
        == "Annualised Volatility"
    )

    assert volatility_call.kwargs["value"] == "13.42%"
    assert "variability" in volatility_call.kwargs["help"]


def test_render_performance_risk_row_displays_unavailable_metrics(
    monkeypatch: pytest.MonkeyPatch,
    summary_only_result: HistoryAnalyticsResult,
) -> None:
    """
    Optional analytics should display unavailable for short history.
    """

    columns = _create_streamlit_columns()

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_statistics.st.columns",
        MagicMock(
            return_value=columns
        ),
    )

    metric_mock = MagicMock()

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_statistics.st.metric",
        metric_mock,
    )

    _render_performance_risk_row(
        summary_only_result
    )

    optional_values = {
        call.kwargs["label"]: call.kwargs["value"]
        for call in metric_mock.call_args_list
        if call.kwargs["label"]
        in {
            "Historical CAGR",
            "Maximum Drawdown",
            "Annualised Volatility",
        }
    }

    assert optional_values == {
        "Historical CAGR": UNAVAILABLE_VALUE,
        "Maximum Drawdown": UNAVAILABLE_VALUE,
        "Annualised Volatility": UNAVAILABLE_VALUE,
    }


# ============================================================
# Public Renderer Tests
# ============================================================


def test_render_history_statistics_rejects_invalid_result() -> None:
    """
    Public renderer should validate its input before rendering.
    """

    with pytest.raises(
        TypeError,
        match="HistoryAnalyticsResult",
    ):
        render_history_statistics(
            None  # type: ignore[arg-type]
        )


def test_render_history_statistics_orchestrates_complete_section(
    monkeypatch: pytest.MonkeyPatch,
    complete_result: HistoryAnalyticsResult,
) -> None:
    """
    Public renderer should display its heading, caption, rows, and dividers.
    """

    subheader_mock = MagicMock()
    caption_mock = MagicMock()
    divider_mock = MagicMock()
    coverage_mock = MagicMock()
    value_mock = MagicMock()
    risk_mock = MagicMock()

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_statistics.st.subheader",
        subheader_mock,
    )

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_statistics.st.caption",
        caption_mock,
    )

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_statistics.st.divider",
        divider_mock,
    )

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_statistics."
        "_render_history_coverage_row",
        coverage_mock,
    )

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_statistics."
        "_render_value_summary_row",
        value_mock,
    )

    monkeypatch.setattr(
        "dashboard.components.analytics."
        "history_statistics."
        "_render_performance_risk_row",
        risk_mock,
    )

    result = render_history_statistics(
        complete_result
    )

    assert result is None

    subheader_mock.assert_called_once_with(
        HISTORY_STATISTICS_TITLE
    )

    caption_mock.assert_called_once_with(
        HISTORY_STATISTICS_CAPTION
    )

    coverage_mock.assert_called_once_with(
        complete_result
    )

    value_mock.assert_called_once_with(
        complete_result
    )

    risk_mock.assert_called_once_with(
        complete_result
    )

    assert divider_mock.call_count == 2