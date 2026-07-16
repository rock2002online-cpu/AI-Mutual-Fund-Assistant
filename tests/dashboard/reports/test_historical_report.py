"""
Unit tests for historical report presentation helpers.

Coverage includes:

- Validation helpers
- Formatting helpers
- Metric view models
- Availability summaries
- Notes and warning generation
- Historical report view construction
- Dashboard metric-card adapters
- Summary and availability row adapters
- Convenience API behavior
- Immutable result models

The tests isolate presentation logic from historical analytics calculations.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date
from types import SimpleNamespace

import pytest

import dashboard.reports.historical_report as historical_report_module

from dashboard.reports.historical_report import (
    AVAILABLE_STATUS,
    HISTORICAL_REPORT_TITLE,
    PARTIAL_STATUS,
    SUPPORTED_AVAILABILITY_STATUSES,
    UNAVAILABLE_STATUS,
    UNAVAILABLE_VALUE,
    HistoricalAvailabilityView,
    HistoricalMetricView,
    HistoricalReportValidationError,
    HistoricalReportView,
    _build_availability_view,
    _build_cagr_metric,
    _build_drawdown_metric,
    _build_notes,
    _build_unavailable_metric,
    _build_volatility_metric,
    _build_warnings,
    _format_count,
    _format_currency_value,
    _format_date,
    _format_duration,
    _format_percentage_value,
    _validate_availability_status,
    _validate_finite_number,
    _validate_history_result,
    _validate_non_blank_text,
    _validate_non_negative_integer,
    _validate_positive_integer,
    _validate_string_tuple,
    build_historical_report_view,
    get_historical_availability_rows,
    get_historical_metric_cards,
    get_historical_summary_rows,
    prepare_historical_report,
)


# ============================================================
# Test Doubles
# ============================================================


class FakeHistoryAnalyticsResult:
    """
    Lightweight historical analytics result matching the presentation
    module's required contract.
    """

    def __init__(
        self,
        *,
        observation_count: int = 25,
        start_date: date = date(
            2024,
            1,
            1,
        ),
        end_date: date = date(
            2026,
            1,
            1,
        ),
        duration_days: int = 731,
        starting_value: float = 90_000.0,
        latest_value: float = 125_000.0,
        minimum_value: float = 85_000.0,
        maximum_value: float = 130_000.0,
        average_value: float = 108_000.0,
        absolute_growth: float = 35_000.0,
        total_growth_percent: float = 38.89,
        periodic_returns: tuple[float, ...] = (
            0.02,
            -0.01,
            0.03,
        ),
        cagr: object | None = None,
        drawdown: object | None = None,
        volatility: object | None = None,
        periods_per_year: int = 12,
    ) -> None:
        self.observation_count = (
            observation_count
        )
        self.start_date = start_date
        self.end_date = end_date
        self.duration_days = duration_days
        self.starting_value = (
            starting_value
        )
        self.latest_value = latest_value
        self.minimum_value = (
            minimum_value
        )
        self.maximum_value = (
            maximum_value
        )
        self.average_value = (
            average_value
        )
        self.absolute_growth = (
            absolute_growth
        )
        self.total_growth_percent = (
            total_growth_percent
        )
        self.periodic_returns = (
            periodic_returns
        )
        self.cagr = cagr
        self.drawdown = drawdown
        self.volatility = volatility
        self.periods_per_year = (
            periods_per_year
        )


@pytest.fixture
def patch_history_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Replace the imported result type with a lightweight test double.
    """

    monkeypatch.setattr(
        historical_report_module,
        "HistoryAnalyticsResult",
        FakeHistoryAnalyticsResult,
    )


@pytest.fixture
def complete_history(
    patch_history_type: None,
) -> FakeHistoryAnalyticsResult:
    """
    Return a history result with all optional analytics available.
    """

    return FakeHistoryAnalyticsResult(
        cagr=SimpleNamespace(
            cagr_percent=17.85,
        ),
        drawdown=SimpleNamespace(
            maximum_drawdown_percent=-12.5,
        ),
        volatility=SimpleNamespace(
            annualised_volatility_percent=14.25,
        ),
    )


@pytest.fixture
def partial_history(
    patch_history_type: None,
) -> FakeHistoryAnalyticsResult:
    """
    Return a history result with only CAGR available.
    """

    return FakeHistoryAnalyticsResult(
        cagr=SimpleNamespace(
            cagr_percent=17.85,
        ),
        drawdown=None,
        volatility=None,
    )


@pytest.fixture
def minimal_history(
    patch_history_type: None,
) -> FakeHistoryAnalyticsResult:
    """
    Return a one-observation result without optional analytics.
    """

    return FakeHistoryAnalyticsResult(
        observation_count=1,
        start_date=date(
            2026,
            1,
            1,
        ),
        end_date=date(
            2026,
            1,
            1,
        ),
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
    )


# ============================================================
# Non-Blank Text Validation
# ============================================================


def test_validate_non_blank_text_returns_trimmed_value() -> None:
    assert (
        _validate_non_blank_text(
            "  Historical Report  ",
            parameter_name="title",
        )
        == "Historical Report"
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        " ",
        "\t",
        "\n",
    ],
)
def test_validate_non_blank_text_rejects_blank(
    value: str,
) -> None:
    with pytest.raises(
        HistoricalReportValidationError,
        match="title cannot be blank",
    ):
        _validate_non_blank_text(
            value,
            parameter_name="title",
        )


@pytest.mark.parametrize(
    "value",
    [
        None,
        123,
        object(),
    ],
)
def test_validate_non_blank_text_rejects_invalid_type(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="title must be a string",
    ):
        _validate_non_blank_text(
            value,  # type: ignore[arg-type]
            parameter_name="title",
        )


def test_validate_non_blank_text_rejects_blank_parameter_name() -> None:
    with pytest.raises(
        HistoricalReportValidationError,
        match="parameter_name cannot be blank",
    ):
        _validate_non_blank_text(
            "value",
            parameter_name=" ",
        )


# ============================================================
# Integer Validation
# ============================================================


@pytest.mark.parametrize(
    "value",
    [
        1,
        12,
        365,
    ],
)
def test_validate_positive_integer_accepts_positive_value(
    value: int,
) -> None:
    assert (
        _validate_positive_integer(
            value,
            parameter_name="periods",
        )
        == value
    )


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
        -100,
    ],
)
def test_validate_positive_integer_rejects_non_positive(
    value: int,
) -> None:
    with pytest.raises(
        HistoricalReportValidationError,
        match="periods must be greater than zero",
    ):
        _validate_positive_integer(
            value,
            parameter_name="periods",
        )


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        1.5,
        "12",
        None,
    ],
)
def test_validate_positive_integer_rejects_invalid_type(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="periods must be an integer",
    ):
        _validate_positive_integer(
            value,  # type: ignore[arg-type]
            parameter_name="periods",
        )


@pytest.mark.parametrize(
    "value",
    [
        0,
        1,
        100,
    ],
)
def test_validate_non_negative_integer_accepts_value(
    value: int,
) -> None:
    assert (
        _validate_non_negative_integer(
            value,
            parameter_name="count",
        )
        == value
    )


def test_validate_non_negative_integer_rejects_negative() -> None:
    with pytest.raises(
        HistoricalReportValidationError,
        match="count cannot be negative",
    ):
        _validate_non_negative_integer(
            -1,
            parameter_name="count",
        )


# ============================================================
# String Tuple Validation
# ============================================================


def test_validate_string_tuple_accepts_valid_tuple() -> None:
    values = (
        "CAGR",
        "Drawdown",
    )

    assert (
        _validate_string_tuple(
            values,
            parameter_name="metrics",
        )
        is values
    )


@pytest.mark.parametrize(
    "value",
    [
        [],
        "CAGR",
        None,
        123,
    ],
)
def test_validate_string_tuple_rejects_non_tuple(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="metrics must be a tuple",
    ):
        _validate_string_tuple(
            value,  # type: ignore[arg-type]
            parameter_name="metrics",
        )


def test_validate_string_tuple_rejects_blank_item() -> None:
    with pytest.raises(
        HistoricalReportValidationError,
        match=r"metrics\[1\] cannot be blank",
    ):
        _validate_string_tuple(
            (
                "CAGR",
                " ",
            ),
            parameter_name="metrics",
        )


# ============================================================
# Availability Status Validation
# ============================================================


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "available",
            AVAILABLE_STATUS,
        ),
        (
            " AVAILABLE ",
            AVAILABLE_STATUS,
        ),
        (
            "partial",
            PARTIAL_STATUS,
        ),
        (
            "unavailable",
            UNAVAILABLE_STATUS,
        ),
    ],
)
def test_validate_availability_status_accepts_supported_value(
    value: str,
    expected: str,
) -> None:
    assert (
        _validate_availability_status(
            value
        )
        == expected
    )


@pytest.mark.parametrize(
    "value",
    [
        "complete",
        "failed",
        "unknown",
    ],
)
def test_validate_availability_status_rejects_unsupported_value(
    value: str,
) -> None:
    with pytest.raises(
        HistoricalReportValidationError,
        match="Unsupported availability status",
    ):
        _validate_availability_status(
            value
        )


def test_supported_availability_statuses_are_complete() -> None:
    assert (
        SUPPORTED_AVAILABILITY_STATUSES
        == (
            AVAILABLE_STATUS,
            PARTIAL_STATUS,
            UNAVAILABLE_STATUS,
        )
    )


# ============================================================
# Date and Duration Formatting
# ============================================================


def test_format_date_returns_expected_text() -> None:
    assert (
        _format_date(
            date(
                2026,
                7,
                16,
            )
        )
        == "16 Jul 2026"
    )


def test_format_date_rejects_invalid_type() -> None:
    with pytest.raises(
        TypeError,
        match="value must be a date",
    ):
        _format_date(
            "2026-07-16"  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            0,
            "0 days",
        ),
        (
            1,
            "1 day",
        ),
        (
            364,
            "364 days",
        ),
        (
            365,
            "1 year",
        ),
        (
            366,
            "1 year, 1 day",
        ),
        (
            730,
            "2 years",
        ),
        (
            731,
            "2 years, 1 day",
        ),
    ],
)
def test_format_duration_returns_readable_value(
    value: int,
    expected: str,
) -> None:
    assert (
        _format_duration(value)
        == expected
    )


def test_format_duration_rejects_negative_value() -> None:
    with pytest.raises(
        HistoricalReportValidationError,
        match="duration_days cannot be negative",
    ):
        _format_duration(
            -1
        )


# ============================================================
# Count and Number Formatting
# ============================================================


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            0,
            "0",
        ),
        (
            1,
            "1",
        ),
        (
            1_000,
            "1,000",
        ),
        (
            1_234_567,
            "1,234,567",
        ),
    ],
)
def test_format_count_returns_grouped_integer(
    value: int,
    expected: str,
) -> None:
    assert (
        _format_count(value)
        == expected
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            0,
            0.0,
        ),
        (
            1,
            1.0,
        ),
        (
            -12.5,
            -12.5,
        ),
    ],
)
def test_validate_finite_number_accepts_numeric_value(
    value: int | float,
    expected: float,
) -> None:
    assert (
        _validate_finite_number(
            value,
            parameter_name="metric",
        )
        == expected
    )


@pytest.mark.parametrize(
    "value",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_validate_finite_number_rejects_non_finite_value(
    value: float,
) -> None:
    with pytest.raises(
        HistoricalReportValidationError,
        match="metric must be finite",
    ):
        _validate_finite_number(
            value,
            parameter_name="metric",
        )


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        None,
        "10",
        object(),
    ],
)
def test_validate_finite_number_rejects_invalid_type(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="metric must be numeric",
    ):
        _validate_finite_number(
            value,  # type: ignore[arg-type]
            parameter_name="metric",
        )


def test_format_currency_value_uses_report_formatter() -> None:
    assert (
        _format_currency_value(
            125_000,
            parameter_name="value",
        )
        == "₹125,000.00"
    )


def test_format_percentage_value_supports_sign() -> None:
    assert (
        _format_percentage_value(
            12.5,
            parameter_name="return",
            include_sign=True,
        )
        == "+12.50%"
    )


def test_format_percentage_value_rejects_invalid_include_sign() -> None:
    with pytest.raises(
        TypeError,
        match="include_sign must be a boolean",
    ):
        _format_percentage_value(
            12.5,
            parameter_name="return",
            include_sign=1,  # type: ignore[arg-type]
        )


# ============================================================
# History Result Validation
# ============================================================


def test_validate_history_result_accepts_valid_history(
    complete_history: FakeHistoryAnalyticsResult,
) -> None:
    assert (
        _validate_history_result(
            complete_history  # type: ignore[arg-type]
        )
        is complete_history
    )


def test_validate_history_result_rejects_invalid_type(
    patch_history_type: None,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "history must be a "
            "HistoryAnalyticsResult"
        ),
    ):
        _validate_history_result(
            object()  # type: ignore[arg-type]
        )


def test_validate_history_result_rejects_zero_observations(
    patch_history_type: None,
) -> None:
    history = FakeHistoryAnalyticsResult(
        observation_count=0,
    )

    with pytest.raises(
        HistoricalReportValidationError,
        match=(
            "history.observation_count "
            "must be at least one"
        ),
    ):
        _validate_history_result(
            history  # type: ignore[arg-type]
        )


def test_validate_history_result_rejects_reversed_dates(
    patch_history_type: None,
) -> None:
    history = FakeHistoryAnalyticsResult(
        start_date=date(
            2026,
            1,
            2,
        ),
        end_date=date(
            2026,
            1,
            1,
        ),
    )

    with pytest.raises(
        HistoricalReportValidationError,
        match=(
            "history.end_date cannot be earlier "
            "than history.start_date"
        ),
    ):
        _validate_history_result(
            history  # type: ignore[arg-type]
        )


def test_validate_history_result_rejects_invalid_periods_per_year(
    patch_history_type: None,
) -> None:
    history = FakeHistoryAnalyticsResult(
        periods_per_year=0,
    )

    with pytest.raises(
        HistoricalReportValidationError,
        match=(
            "history.periods_per_year "
            "must be greater than zero"
        ),
    ):
        _validate_history_result(
            history  # type: ignore[arg-type]
        )


# ============================================================
# Metric View Models
# ============================================================


def test_historical_metric_view_accepts_valid_data() -> None:
    metric = HistoricalMetricView(
        label="Historical CAGR",
        value="+12.50%",
        available=True,
        description="Annualised growth.",
    )

    assert metric.label == (
        "Historical CAGR"
    )

    assert metric.available is True


def test_historical_metric_view_rejects_invalid_available_type() -> None:
    with pytest.raises(
        TypeError,
        match="available must be a boolean",
    ):
        HistoricalMetricView(
            label="Historical CAGR",
            value="+12.50%",
            available=1,  # type: ignore[arg-type]
        )


def test_historical_metric_view_is_immutable() -> None:
    metric = HistoricalMetricView(
        label="Historical CAGR",
        value="+12.50%",
        available=True,
    )

    with pytest.raises(
        FrozenInstanceError,
    ):
        metric.value = (  # type: ignore[misc]
            "Changed"
        )


def test_build_unavailable_metric_returns_expected_view() -> None:
    result = _build_unavailable_metric(
        label="Maximum Drawdown",
        description="Insufficient history.",
    )

    assert result == HistoricalMetricView(
        label="Maximum Drawdown",
        value=UNAVAILABLE_VALUE,
        available=False,
        description="Insufficient history.",
    )


# ============================================================
# Optional Metric Builders
# ============================================================


def test_build_cagr_metric_returns_available_metric(
    complete_history: FakeHistoryAnalyticsResult,
) -> None:
    result = _build_cagr_metric(
        complete_history  # type: ignore[arg-type]
    )

    assert result.available is True
    assert result.label == (
        "Historical CAGR"
    )

    assert result.value == "+17.85%"


def test_build_cagr_metric_returns_unavailable_metric(
    minimal_history: FakeHistoryAnalyticsResult,
) -> None:
    result = _build_cagr_metric(
        minimal_history  # type: ignore[arg-type]
    )

    assert result.available is False
    assert result.value == (
        UNAVAILABLE_VALUE
    )


def test_build_drawdown_metric_returns_available_metric(
    complete_history: FakeHistoryAnalyticsResult,
) -> None:
    result = _build_drawdown_metric(
        complete_history  # type: ignore[arg-type]
    )

    assert result.available is True
    assert result.value == "-12.50%"


def test_build_volatility_metric_returns_available_metric(
    complete_history: FakeHistoryAnalyticsResult,
) -> None:
    result = _build_volatility_metric(
        complete_history  # type: ignore[arg-type]
    )

    assert result.available is True
    assert result.value == "14.25%"


# ============================================================
# Availability View
# ============================================================


def test_build_availability_view_returns_available_status() -> None:
    result = _build_availability_view(
        cagr=HistoricalMetricView(
            label="CAGR",
            value="10%",
            available=True,
        ),
        maximum_drawdown=HistoricalMetricView(
            label="Drawdown",
            value="-5%",
            available=True,
        ),
        annualised_volatility=HistoricalMetricView(
            label="Volatility",
            value="12%",
            available=True,
        ),
    )

    assert result.status == (
        AVAILABLE_STATUS
    )

    assert result.unavailable_metrics == ()


def test_build_availability_view_returns_partial_status() -> None:
    result = _build_availability_view(
        cagr=HistoricalMetricView(
            label="CAGR",
            value="10%",
            available=True,
        ),
        maximum_drawdown=HistoricalMetricView(
            label="Drawdown",
            value=UNAVAILABLE_VALUE,
            available=False,
        ),
        annualised_volatility=HistoricalMetricView(
            label="Volatility",
            value=UNAVAILABLE_VALUE,
            available=False,
        ),
    )

    assert result.status == (
        PARTIAL_STATUS
    )

    assert result.available_metrics == (
        "CAGR",
    )


def test_build_availability_view_returns_unavailable_status() -> None:
    result = _build_availability_view(
        cagr=HistoricalMetricView(
            label="CAGR",
            value=UNAVAILABLE_VALUE,
            available=False,
        ),
        maximum_drawdown=HistoricalMetricView(
            label="Drawdown",
            value=UNAVAILABLE_VALUE,
            available=False,
        ),
        annualised_volatility=HistoricalMetricView(
            label="Volatility",
            value=UNAVAILABLE_VALUE,
            available=False,
        ),
    )

    assert result.status == (
        UNAVAILABLE_STATUS
    )


def test_historical_availability_view_requires_normalized_status() -> None:
    with pytest.raises(
        HistoricalReportValidationError,
        match="status must already be normalized",
    ):
        HistoricalAvailabilityView(
            status=" AVAILABLE ",
            available_metrics=(),
            unavailable_metrics=(),
            message="Metrics available.",
        )


# ============================================================
# Notes and Warnings
# ============================================================


def test_build_notes_describes_history(
    complete_history: FakeHistoryAnalyticsResult,
) -> None:
    cagr = _build_cagr_metric(
        complete_history  # type: ignore[arg-type]
    )

    drawdown = _build_drawdown_metric(
        complete_history  # type: ignore[arg-type]
    )

    volatility = _build_volatility_metric(
        complete_history  # type: ignore[arg-type]
    )

    notes = _build_notes(
        complete_history,  # type: ignore[arg-type]
        cagr=cagr,
        maximum_drawdown=drawdown,
        annualised_volatility=volatility,
    )

    assert any(
        "25 validated portfolio valuation observations"
        in note
        for note in notes
    )

    assert any(
        "3 periodic return observations"
        in note
        for note in notes
    )


def test_build_warnings_reports_unavailable_metrics(
    minimal_history: FakeHistoryAnalyticsResult,
) -> None:
    cagr = _build_cagr_metric(
        minimal_history  # type: ignore[arg-type]
    )

    drawdown = _build_drawdown_metric(
        minimal_history  # type: ignore[arg-type]
    )

    volatility = _build_volatility_metric(
        minimal_history  # type: ignore[arg-type]
    )

    warnings = _build_warnings(
        minimal_history,  # type: ignore[arg-type]
        cagr=cagr,
        maximum_drawdown=drawdown,
        annualised_volatility=volatility,
    )

    assert any(
        "Historical CAGR is unavailable"
        in warning
        for warning in warnings
    )

    assert any(
        "same calendar date"
        in warning
        for warning in warnings
    )


def test_build_warnings_reports_negative_growth(
    patch_history_type: None,
) -> None:
    history = FakeHistoryAnalyticsResult(
        total_growth_percent=-5.0,
        cagr=None,
        drawdown=None,
        volatility=None,
    )

    warnings = _build_warnings(
        history,  # type: ignore[arg-type]
        cagr=_build_cagr_metric(
            history  # type: ignore[arg-type]
        ),
        maximum_drawdown=(
            _build_drawdown_metric(
                history  # type: ignore[arg-type]
            )
        ),
        annualised_volatility=(
            _build_volatility_metric(
                history  # type: ignore[arg-type]
            )
        ),
    )

    assert any(
        "portfolio value declined"
        in warning
        for warning in warnings
    )


def test_build_warnings_reports_material_drawdown(
    patch_history_type: None,
) -> None:
    history = FakeHistoryAnalyticsResult(
        drawdown=SimpleNamespace(
            maximum_drawdown_percent=-25.0,
        ),
    )

    warnings = _build_warnings(
        history,  # type: ignore[arg-type]
        cagr=_build_cagr_metric(
            history  # type: ignore[arg-type]
        ),
        maximum_drawdown=(
            _build_drawdown_metric(
                history  # type: ignore[arg-type]
            )
        ),
        annualised_volatility=(
            _build_volatility_metric(
                history  # type: ignore[arg-type]
            )
        ),
    )

    assert any(
        "exceeded 20 percent"
        in warning
        for warning in warnings
    )


# ============================================================
# Historical Report View Builder
# ============================================================


def test_build_historical_report_view_formats_complete_history(
    complete_history: FakeHistoryAnalyticsResult,
) -> None:
    result = build_historical_report_view(
        complete_history,  # type: ignore[arg-type]
        title=" Historical Summary ",
    )

    assert isinstance(
        result,
        HistoricalReportView,
    )

    assert result.title == (
        "Historical Summary"
    )

    assert result.start_date == (
        "01 Jan 2024"
    )

    assert result.end_date == (
        "01 Jan 2026"
    )

    assert result.duration == (
        "2 years, 1 day"
    )

    assert result.starting_value == (
        "₹90,000.00"
    )

    assert result.latest_value == (
        "₹125,000.00"
    )

    assert result.absolute_growth == (
        "₹35,000.00"
    )

    assert result.total_growth == (
        "+38.89%"
    )

    assert result.availability.status == (
        AVAILABLE_STATUS
    )

    assert result.periodic_return_count == 3


def test_build_historical_report_view_handles_partial_history(
    partial_history: FakeHistoryAnalyticsResult,
) -> None:
    result = build_historical_report_view(
        partial_history  # type: ignore[arg-type]
    )

    assert result.availability.status == (
        PARTIAL_STATUS
    )

    assert result.cagr.available is True

    assert (
        result.maximum_drawdown.available
        is False
    )

    assert (
        result.annualised_volatility.available
        is False
    )


def test_build_historical_report_view_uses_default_title(
    complete_history: FakeHistoryAnalyticsResult,
) -> None:
    result = build_historical_report_view(
        complete_history  # type: ignore[arg-type]
    )

    assert result.title == (
        HISTORICAL_REPORT_TITLE
    )


def test_build_historical_report_view_rejects_non_finite_value(
    patch_history_type: None,
) -> None:
    history = FakeHistoryAnalyticsResult(
        latest_value=float("nan"),
    )

    with pytest.raises(
        HistoricalReportValidationError,
        match=(
            "history.latest_value must be finite"
        ),
    ):
        build_historical_report_view(
            history  # type: ignore[arg-type]
        )


def test_historical_report_view_is_immutable(
    complete_history: FakeHistoryAnalyticsResult,
) -> None:
    view = build_historical_report_view(
        complete_history  # type: ignore[arg-type]
    )

    with pytest.raises(
        FrozenInstanceError,
    ):
        view.title = (  # type: ignore[misc]
            "Changed"
        )


# ============================================================
# Dashboard Adapters
# ============================================================


def test_get_historical_metric_cards_returns_expected_metrics(
    complete_history: FakeHistoryAnalyticsResult,
) -> None:
    view = build_historical_report_view(
        complete_history  # type: ignore[arg-type]
    )

    result = get_historical_metric_cards(
        view
    )

    assert (
        "Starting Value",
        "₹90,000.00",
    ) in result

    assert (
        "Historical CAGR",
        "+17.85%",
    ) in result

    assert (
        "Observations",
        "25",
    ) in result


def test_get_historical_summary_rows_returns_expected_rows(
    complete_history: FakeHistoryAnalyticsResult,
) -> None:
    view = build_historical_report_view(
        complete_history  # type: ignore[arg-type]
    )

    result = get_historical_summary_rows(
        view
    )

    assert (
        "Duration",
        "2 years, 1 day",
    ) in result

    assert (
        "Periods Per Year",
        "12",
    ) in result


def test_get_historical_availability_rows_returns_expected_rows(
    partial_history: FakeHistoryAnalyticsResult,
) -> None:
    view = build_historical_report_view(
        partial_history  # type: ignore[arg-type]
    )

    result = (
        get_historical_availability_rows(
            view
        )
    )

    assert (
        "Status",
        "Partial",
    ) in result

    assert any(
        label == "Unavailable Metrics"
        and "Maximum Drawdown" in value
        for label, value in result
    )


@pytest.mark.parametrize(
    "function",
    [
        get_historical_metric_cards,
        get_historical_summary_rows,
        get_historical_availability_rows,
    ],
)
def test_dashboard_adapter_rejects_invalid_view(
    function: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "view must be a "
            "HistoricalReportView"
        ),
    ):
        function(  # type: ignore[operator]
            object()
        )


# ============================================================
# Convenience API
# ============================================================


def test_prepare_historical_report_delegates_to_builder(
    complete_history: FakeHistoryAnalyticsResult,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = object()

    builder = pytest.MonkeyPatch()

    monkeypatch.setattr(
        historical_report_module,
        "build_historical_report_view",
        lambda history, title: expected,
    )

    result = prepare_historical_report(
        complete_history,  # type: ignore[arg-type]
        title="Custom",
    )

    assert result is expected


def test_prepare_historical_report_uses_default_title(
    complete_history: FakeHistoryAnalyticsResult,
) -> None:
    result = prepare_historical_report(
        complete_history  # type: ignore[arg-type]
    )

    assert result.title == (
        HISTORICAL_REPORT_TITLE
    )