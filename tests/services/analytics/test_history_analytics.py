"""
Tests for services.analytics.history_analytics.

These tests verify:

- Input validation.
- History preparation.
- Summary statistics.
- Growth calculations.
- Reuse of existing CAGR, drawdown, return, and volatility analytics.
- Graceful handling of short historical series.
- Service and convenience-function behavior.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from services.analytics.history_analytics import (
    DATE_COLUMN,
    VALUE_COLUMN,
    HistoryAnalyticsCalculationError,
    HistoryAnalyticsInput,
    HistoryAnalyticsResult,
    HistoryAnalyticsService,
    HistoryAnalyticsValidationError,
    calculate_history_analytics,
    prepare_history_for_analytics,
)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def valid_history() -> pd.DataFrame:
    """
    Return a valid chronological portfolio-history dataframe.
    """

    return pd.DataFrame(
        {
            DATE_COLUMN: [
                "2024-01-01",
                "2024-04-01",
                "2024-07-01",
                "2025-01-01",
            ],
            VALUE_COLUMN: [
                100_000.0,
                110_000.0,
                105_000.0,
                125_000.0,
            ],
        }
    )


@pytest.fixture
def service() -> HistoryAnalyticsService:
    """
    Return a HistoryAnalyticsService instance.
    """

    return HistoryAnalyticsService()


# ============================================================
# Input Model Tests
# ============================================================


def test_history_analytics_input_stores_values(
    valid_history: pd.DataFrame,
) -> None:
    """
    HistoryAnalyticsInput should preserve its configured values.
    """

    input_data = HistoryAnalyticsInput(
        history=valid_history,
        periods_per_year=12,
    )

    assert input_data.history is valid_history
    assert input_data.periods_per_year == 12


# ============================================================
# prepare_history_for_analytics Tests
# ============================================================


def test_prepare_history_rejects_non_dataframe() -> None:
    """
    History preparation should reject unsupported input types.
    """

    with pytest.raises(
        TypeError,
        match="history must be a pandas DataFrame",
    ):
        prepare_history_for_analytics(
            []  # type: ignore[arg-type]
        )


def test_prepare_history_rejects_empty_dataframe() -> None:
    """
    Empty history should not be accepted.
    """

    with pytest.raises(
        HistoryAnalyticsValidationError,
        match="at least one observation",
    ):
        prepare_history_for_analytics(
            pd.DataFrame()
        )


@pytest.mark.parametrize(
    "missing_column",
    [
        DATE_COLUMN,
        VALUE_COLUMN,
    ],
)
def test_prepare_history_rejects_missing_required_columns(
    missing_column: str,
) -> None:
    """
    Canonical Date and Value columns are required.
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
        HistoryAnalyticsValidationError,
        match="missing required column",
    ):
        prepare_history_for_analytics(
            history
        )


def test_prepare_history_does_not_mutate_input() -> None:
    """
    History preparation should leave the caller's dataframe unchanged.
    """

    history = pd.DataFrame(
        {
            DATE_COLUMN: [
                "2025-02-01",
                "2025-01-01",
            ],
            VALUE_COLUMN: [
                "120000",
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

    prepare_history_for_analytics(
        history
    )

    pd.testing.assert_frame_equal(
        history,
        original,
    )


def test_prepare_history_returns_only_canonical_columns() -> None:
    """
    Extra source columns should not leak into the analytics dataframe.
    """

    history = pd.DataFrame(
        {
            DATE_COLUMN: ["2025-01-01"],
            VALUE_COLUMN: [100_000.0],
            "Extra": ["ignored"],
        }
    )

    result = prepare_history_for_analytics(
        history
    )

    assert list(result.columns) == [
        DATE_COLUMN,
        VALUE_COLUMN,
    ]


def test_prepare_history_converts_dates_and_values() -> None:
    """
    Date and Value fields should be normalized to analytics-friendly types.
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

    result = prepare_history_for_analytics(
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
    Invalid dates, invalid values, and non-positive values should be removed.
    """

    history = pd.DataFrame(
        {
            DATE_COLUMN: [
                "2025-01-01",
                "invalid-date",
                "2025-03-01",
                "2025-04-01",
                "2025-05-01",
            ],
            VALUE_COLUMN: [
                100_000.0,
                110_000.0,
                "invalid-value",
                0.0,
                -5_000.0,
            ],
        }
    )

    result = prepare_history_for_analytics(
        history
    )

    assert len(result) == 1
    assert result.iloc[0][VALUE_COLUMN] == 100_000.0


def test_prepare_history_rejects_when_no_valid_rows_remain() -> None:
    """
    Preparation should fail when all observations are unusable.
    """

    history = pd.DataFrame(
        {
            DATE_COLUMN: [
                "invalid",
                None,
            ],
            VALUE_COLUMN: [
                0,
                -1,
            ],
        }
    )

    with pytest.raises(
        HistoryAnalyticsValidationError,
        match="no valid positive",
    ):
        prepare_history_for_analytics(
            history
        )


def test_prepare_history_sorts_chronologically() -> None:
    """
    Prepared observations should be ordered by Date.
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

    result = prepare_history_for_analytics(
        history
    )

    assert result[DATE_COLUMN].dt.date.tolist() == [
        date(2025, 1, 1),
        date(2025, 2, 1),
        date(2025, 3, 1),
    ]


def test_prepare_history_keeps_last_duplicate_date() -> None:
    """
    The final record for a duplicate date should be retained.
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

    result = prepare_history_for_analytics(
        history
    )

    assert len(result) == 2
    assert result.iloc[0][VALUE_COLUMN] == 105_000.0


# ============================================================
# Service Validation Tests
# ============================================================


def test_service_rejects_invalid_input_model(
    service: HistoryAnalyticsService,
) -> None:
    """
    calculate() should require HistoryAnalyticsInput.
    """

    with pytest.raises(
        TypeError,
        match="HistoryAnalyticsInput",
    ):
        service.calculate(
            pd.DataFrame()  # type: ignore[arg-type]
        )


def test_service_rejects_boolean_periods_per_year(
    service: HistoryAnalyticsService,
    valid_history: pd.DataFrame,
) -> None:
    """
    Boolean values should not be accepted as integer frequencies.
    """

    with pytest.raises(
        TypeError,
        match="periods_per_year must be an integer",
    ):
        service.calculate(
            HistoryAnalyticsInput(
                history=valid_history,
                periods_per_year=True,  # type: ignore[arg-type]
            )
        )


def test_service_rejects_non_integer_periods_per_year(
    service: HistoryAnalyticsService,
    valid_history: pd.DataFrame,
) -> None:
    """
    Annualisation frequency must be an integer.
    """

    with pytest.raises(
        TypeError,
        match="periods_per_year must be an integer",
    ):
        service.calculate(
            HistoryAnalyticsInput(
                history=valid_history,
                periods_per_year=12.5,  # type: ignore[arg-type]
            )
        )


@pytest.mark.parametrize(
    "periods_per_year",
    [
        0,
        -1,
    ],
)
def test_service_rejects_non_positive_periods_per_year(
    service: HistoryAnalyticsService,
    valid_history: pd.DataFrame,
    periods_per_year: int,
) -> None:
    """
    Annualisation frequency must be greater than zero.
    """

    with pytest.raises(
        HistoryAnalyticsValidationError,
        match="greater than zero",
    ):
        service.calculate(
            HistoryAnalyticsInput(
                history=valid_history,
                periods_per_year=periods_per_year,
            )
        )


# ============================================================
# Service Calculation Tests
# ============================================================


def test_service_returns_history_analytics_result(
    service: HistoryAnalyticsService,
    valid_history: pd.DataFrame,
) -> None:
    """
    Valid history should produce an immutable typed result.
    """

    result = service.calculate(
        HistoryAnalyticsInput(
            history=valid_history,
        )
    )

    assert isinstance(
        result,
        HistoryAnalyticsResult,
    )


def test_service_calculates_history_metadata(
    service: HistoryAnalyticsService,
    valid_history: pd.DataFrame,
) -> None:
    """
    Observation count, dates, and duration should be correct.
    """

    result = service.calculate(
        HistoryAnalyticsInput(
            history=valid_history,
        )
    )

    assert result.observation_count == 4
    assert result.start_date == date(2024, 1, 1)
    assert result.end_date == date(2025, 1, 1)
    assert result.duration_days == 366


def test_service_calculates_value_statistics(
    service: HistoryAnalyticsService,
    valid_history: pd.DataFrame,
) -> None:
    """
    Historical minimum, maximum, average, and endpoint values should match.
    """

    result = service.calculate(
        HistoryAnalyticsInput(
            history=valid_history,
        )
    )

    assert result.starting_value == pytest.approx(
        100_000.0
    )

    assert result.latest_value == pytest.approx(
        125_000.0
    )

    assert result.minimum_value == pytest.approx(
        100_000.0
    )

    assert result.maximum_value == pytest.approx(
        125_000.0
    )

    assert result.average_value == pytest.approx(
        110_000.0
    )


def test_service_calculates_growth_statistics(
    service: HistoryAnalyticsService,
    valid_history: pd.DataFrame,
) -> None:
    """
    Absolute and percentage growth should be calculated correctly.
    """

    result = service.calculate(
        HistoryAnalyticsInput(
            history=valid_history,
        )
    )

    assert result.absolute_growth == pytest.approx(
        25_000.0
    )

    assert result.total_growth_percent == pytest.approx(
        25.0
    )


def test_service_calculates_periodic_returns(
    service: HistoryAnalyticsService,
    valid_history: pd.DataFrame,
) -> None:
    """
    Periodic returns should be derived in chronological order.
    """

    result = service.calculate(
        HistoryAnalyticsInput(
            history=valid_history,
        )
    )

    assert result.periodic_returns == pytest.approx(
        (
            0.10,
            (105_000.0 / 110_000.0) - 1.0,
            (125_000.0 / 105_000.0) - 1.0,
        )
    )


def test_service_reuses_cagr_analytics(
    service: HistoryAnalyticsService,
    valid_history: pd.DataFrame,
) -> None:
    """
    A multi-date history should include the existing CAGR result.
    """

    result = service.calculate(
        HistoryAnalyticsInput(
            history=valid_history,
        )
    )

    assert result.cagr is not None
    assert result.cagr.initial_value == pytest.approx(
        100_000.0
    )
    assert result.cagr.final_value == pytest.approx(
        125_000.0
    )
    assert result.cagr.absolute_gain == pytest.approx(
        25_000.0
    )
    assert result.cagr.total_return_percent == pytest.approx(
        25.0
    )


def test_service_reuses_drawdown_analytics(
    service: HistoryAnalyticsService,
    valid_history: pd.DataFrame,
) -> None:
    """
    A multi-observation history should include drawdown analytics.
    """

    result = service.calculate(
        HistoryAnalyticsInput(
            history=valid_history,
        )
    )

    assert result.drawdown is not None
    assert result.drawdown.observation_count == 4
    assert result.drawdown.starting_value == pytest.approx(
        100_000.0
    )
    assert result.drawdown.ending_value == pytest.approx(
        125_000.0
    )

    assert (
        result.drawdown.maximum_drawdown_percent
        == pytest.approx(
            ((105_000.0 / 110_000.0) - 1.0)
            * 100.0
        )
    )


def test_service_reuses_volatility_analytics(
    service: HistoryAnalyticsService,
    valid_history: pd.DataFrame,
) -> None:
    """
    Three or more values should produce volatility analytics.
    """

    result = service.calculate(
        HistoryAnalyticsInput(
            history=valid_history,
            periods_per_year=12,
        )
    )

    assert result.volatility is not None
    assert result.volatility.observation_count == 3
    assert result.volatility.periods_per_year == 12
    assert result.periods_per_year == 12


def test_single_observation_produces_summary_only(
    service: HistoryAnalyticsService,
) -> None:
    """
    One observation should return summary data without risk metrics.
    """

    history = pd.DataFrame(
        {
            DATE_COLUMN: [
                "2025-01-01",
            ],
            VALUE_COLUMN: [
                100_000.0,
            ],
        }
    )

    result = service.calculate(
        HistoryAnalyticsInput(
            history=history,
        )
    )

    assert result.observation_count == 1
    assert result.start_date == date(2025, 1, 1)
    assert result.end_date == date(2025, 1, 1)
    assert result.duration_days == 0

    assert result.starting_value == pytest.approx(
        100_000.0
    )
    assert result.latest_value == pytest.approx(
        100_000.0
    )
    assert result.absolute_growth == pytest.approx(
        0.0
    )
    assert result.total_growth_percent == pytest.approx(
        0.0
    )

    assert result.periodic_returns == ()
    assert result.cagr is None
    assert result.drawdown is None
    assert result.volatility is None


def test_two_observations_produce_cagr_and_drawdown_but_no_volatility(
    service: HistoryAnalyticsService,
) -> None:
    """
    Two values produce one return, which is insufficient for sample
    volatility but sufficient for CAGR and drawdown.
    """

    history = pd.DataFrame(
        {
            DATE_COLUMN: [
                "2024-01-01",
                "2025-01-01",
            ],
            VALUE_COLUMN: [
                100_000.0,
                110_000.0,
            ],
        }
    )

    result = service.calculate(
        HistoryAnalyticsInput(
            history=history,
        )
    )

    assert result.periodic_returns == ()

    assert result.cagr is not None
    assert result.drawdown is not None
    assert result.volatility is None


def test_same_day_duplicates_are_reduced_before_calculation(
    service: HistoryAnalyticsService,
) -> None:
    """
    Duplicate dates should not inflate observation counts.
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

    result = service.calculate(
        HistoryAnalyticsInput(
            history=history,
        )
    )

    assert result.observation_count == 2
    assert result.starting_value == pytest.approx(
        105_000.0
    )
    assert result.latest_value == pytest.approx(
        110_000.0
    )


# ============================================================
# Dependency Failure Tests
# ============================================================


def test_service_wraps_unexpected_dependency_error(
    monkeypatch: pytest.MonkeyPatch,
    service: HistoryAnalyticsService,
    valid_history: pd.DataFrame,
) -> None:
    """
    Unexpected downstream analytics failures should be wrapped.
    """

    def raise_error(
        values: object,
    ) -> tuple[float, ...]:
        raise RuntimeError(
            "dependency failed"
        )

    monkeypatch.setattr(
        "services.analytics.history_analytics."
        "calculate_periodic_returns",
        raise_error,
    )

    with pytest.raises(
        HistoryAnalyticsCalculationError,
        match="dependency failed",
    ):
        service.calculate(
            HistoryAnalyticsInput(
                history=valid_history,
            )
        )


# ============================================================
# Convenience API Tests
# ============================================================


def test_calculate_history_analytics_returns_result(
    valid_history: pd.DataFrame,
) -> None:
    """
    Convenience API should delegate to HistoryAnalyticsService.
    """

    result = calculate_history_analytics(
        valid_history,
        periods_per_year=12,
    )

    assert isinstance(
        result,
        HistoryAnalyticsResult,
    )

    assert result.periods_per_year == 12


def test_calculate_history_analytics_validates_history() -> None:
    """
    Convenience API should expose service validation errors.
    """

    with pytest.raises(
        HistoryAnalyticsValidationError,
        match="at least one observation",
    ):
        calculate_history_analytics(
            pd.DataFrame()
        )