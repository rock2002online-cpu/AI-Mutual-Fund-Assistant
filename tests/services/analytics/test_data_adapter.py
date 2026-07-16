"""
Tests for services.analytics.data_adapter.

These tests validate:

- Portfolio snapshot aggregation
- Mapping and DataFrame-like record conversion
- Dated value construction
- Periodic return construction
- CAGR input construction
- XIRR cash-flow construction
- Drawdown input construction
- Volatility input construction
- Risk-metric input construction
- Benchmark input construction
- Rolling-return input construction
- Advanced analytics input orchestration
- Defensive validation
- Immutable dataclasses
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date, datetime

import pytest

from services.analytics.advanced_analytics import (
    AdvancedAnalyticsInput,
)
from services.analytics.benchmark import BenchmarkInput
from services.analytics.cagr import DateBasedCAGRInput
from services.analytics.data_adapter import (
    AlignedReturnSeries,
    AnalyticsAdapterResult,
    AnalyticsDataAdapterError,
    DatedCashFlow,
    DatedValue,
    PortfolioSnapshotTotals,
    calculate_periodic_returns_from_dated_values,
    calculate_periodic_returns_from_history,
    calculate_portfolio_snapshot_totals,
    create_advanced_analytics_input,
    create_aligned_return_series,
    create_benchmark_input,
    create_benchmark_input_from_records,
    create_cagr_input_from_history,
    create_cagr_input_from_values,
    create_dated_cash_flows,
    create_dated_values,
    create_drawdown_input,
    create_risk_metrics_input,
    create_risk_metrics_input_from_history,
    create_rolling_returns_input,
    create_volatility_input,
    create_volatility_input_from_history,
    create_xirr_input,
)
from services.analytics.drawdown import DrawdownInput
from services.analytics.risk_metrics import RiskMetricsInput
from services.analytics.rolling_returns import RollingReturnsInput
from services.analytics.volatility import VolatilityInput
from services.analytics.xirr import XIRRInput


# ============================================================
# Test Helpers
# ============================================================


class FakeDataFrame:
    """
    Minimal DataFrame-like test object exposing to_dict("records").
    """

    def __init__(
        self,
        records: list[dict[str, object]],
    ) -> None:
        self._records = records

    def to_dict(
        self,
        orient: str,
    ) -> list[dict[str, object]]:
        if orient != "records":
            raise ValueError("Unsupported orientation.")

        return self._records


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def portfolio_records() -> tuple[dict[str, float], ...]:
    """
    Return a representative portfolio snapshot.
    """

    return (
        {
            "Fund": "Fund A",
            "Investment": 100_000.0,
            "Current Value": 125_000.0,
        },
        {
            "Fund": "Fund B",
            "Investment": 50_000.0,
            "Current Value": 45_000.0,
        },
    )


@pytest.fixture
def history_records() -> tuple[dict[str, object], ...]:
    """
    Return chronological portfolio history records.
    """

    return (
        {
            "Date": date(2024, 1, 1),
            "Value": 100.0,
        },
        {
            "Date": date(2024, 2, 1),
            "Value": 110.0,
        },
        {
            "Date": date(2024, 3, 1),
            "Value": 99.0,
        },
        {
            "Date": date(2024, 4, 1),
            "Value": 108.9,
        },
    )


@pytest.fixture
def cash_flow_records() -> tuple[dict[str, object], ...]:
    """
    Return representative investment cash-flow records.
    """

    return (
        {
            "Date": date(2023, 1, 1),
            "Amount": -50_000.0,
        },
        {
            "Date": date(2023, 6, 1),
            "Amount": -25_000.0,
        },
    )


@pytest.fixture
def aligned_return_records() -> tuple[dict[str, float], ...]:
    """
    Return aligned portfolio and benchmark returns.
    """

    return (
        {
            "Portfolio Return": 0.02,
            "Benchmark Return": 0.018,
        },
        {
            "Portfolio Return": -0.01,
            "Benchmark Return": -0.012,
        },
        {
            "Portfolio Return": 0.015,
            "Benchmark Return": 0.012,
        },
    )


# ============================================================
# Portfolio Snapshot Tests
# ============================================================


def test_calculate_portfolio_snapshot_totals(
    portfolio_records: tuple[dict[str, float], ...],
) -> None:
    """
    Portfolio totals should aggregate investment and current value.
    """

    result = calculate_portfolio_snapshot_totals(
        portfolio_records
    )

    assert isinstance(result, PortfolioSnapshotTotals)
    assert result.row_count == 2

    assert result.total_investment == pytest.approx(
        150_000.0
    )

    assert result.total_current_value == pytest.approx(
        170_000.0
    )

    assert result.total_profit_loss == pytest.approx(
        20_000.0
    )

    assert result.total_return_decimal == pytest.approx(
        (170_000.0 / 150_000.0) - 1.0
    )

    assert result.total_return_percent == pytest.approx(
        result.total_return_decimal * 100.0
    )


def test_portfolio_snapshot_accepts_dataframe_like_object(
    portfolio_records: tuple[dict[str, float], ...],
) -> None:
    """
    DataFrame-like objects exposing to_dict("records") should be accepted.
    """

    fake_dataframe = FakeDataFrame(
        list(portfolio_records)
    )

    result = calculate_portfolio_snapshot_totals(
        fake_dataframe
    )

    assert result.row_count == 2


def test_portfolio_snapshot_supports_custom_columns() -> None:
    """
    Custom snapshot column names should be supported.
    """

    records = (
        {
            "Invested": 100.0,
            "Market": 120.0,
        },
        {
            "Invested": 50.0,
            "Market": 60.0,
        },
    )

    result = calculate_portfolio_snapshot_totals(
        records,
        investment_column="Invested",
        current_value_column="Market",
    )

    assert result.total_investment == pytest.approx(150.0)
    assert result.total_current_value == pytest.approx(180.0)


def test_portfolio_snapshot_rejects_empty_data() -> None:
    """
    Empty portfolio data should be rejected.
    """

    with pytest.raises(
        AnalyticsDataAdapterError,
        match="at least one record",
    ):
        calculate_portfolio_snapshot_totals(())


def test_portfolio_snapshot_rejects_missing_column() -> None:
    """
    Missing required portfolio columns should be rejected.
    """

    with pytest.raises(
        AnalyticsDataAdapterError,
        match="Missing required column",
    ):
        calculate_portfolio_snapshot_totals(
            (
                {
                    "Investment": 100.0,
                },
            )
        )


def test_portfolio_snapshot_rejects_zero_total_investment() -> None:
    """
    Aggregate investment must be greater than zero.
    """

    with pytest.raises(
        AnalyticsDataAdapterError,
        match="Total portfolio investment must be greater than zero",
    ):
        calculate_portfolio_snapshot_totals(
            (
                {
                    "Investment": 0.0,
                    "Current Value": 0.0,
                },
            )
        )


@pytest.mark.parametrize(
    "invalid_value",
    [
        -1.0,
        float("nan"),
        float("inf"),
        True,
        "invalid",
    ],
)
def test_portfolio_snapshot_rejects_invalid_investment(
    invalid_value: object,
) -> None:
    """
    Investment values must be finite and non-negative.
    """

    with pytest.raises(AnalyticsDataAdapterError):
        calculate_portfolio_snapshot_totals(
            (
                {
                    "Investment": invalid_value,
                    "Current Value": 100.0,
                },
            )
        )


# ============================================================
# Dated Value Tests
# ============================================================


def test_create_dated_values(
    history_records: tuple[dict[str, object], ...],
) -> None:
    """
    History records should become chronological dated values.
    """

    result = create_dated_values(history_records)

    assert result == (
        DatedValue(
            observation_date=date(2024, 1, 1),
            value=100.0,
        ),
        DatedValue(
            observation_date=date(2024, 2, 1),
            value=110.0,
        ),
        DatedValue(
            observation_date=date(2024, 3, 1),
            value=99.0,
        ),
        DatedValue(
            observation_date=date(2024, 4, 1),
            value=108.9,
        ),
    )


def test_create_dated_values_sorts_records() -> None:
    """
    Unordered history should be sorted chronologically.
    """

    records = (
        {
            "Date": date(2024, 2, 1),
            "Value": 110.0,
        },
        {
            "Date": date(2024, 1, 1),
            "Value": 100.0,
        },
    )

    result = create_dated_values(records)

    assert result[0].observation_date == date(
        2024,
        1,
        1,
    )


def test_create_dated_values_accepts_iso_date_strings() -> None:
    """
    ISO-format date strings should be accepted.
    """

    result = create_dated_values(
        (
            {
                "Date": "2024-01-01",
                "Value": 100.0,
            },
            {
                "Date": "2024-02-01",
                "Value": 110.0,
            },
        )
    )

    assert result[0].observation_date == date(
        2024,
        1,
        1,
    )


def test_create_dated_values_accepts_datetime() -> None:
    """
    datetime values should be converted to date.
    """

    result = create_dated_values(
        (
            {
                "Date": datetime(2024, 1, 1, 10, 30),
                "Value": 100.0,
            },
            {
                "Date": datetime(2024, 2, 1, 10, 30),
                "Value": 110.0,
            },
        )
    )

    assert type(result[0].observation_date) is date


def test_create_dated_values_supports_custom_columns() -> None:
    """
    Custom date and value columns should be supported.
    """

    result = create_dated_values(
        (
            {
                "NAV Date": date(2024, 1, 1),
                "NAV": 10.0,
            },
            {
                "NAV Date": date(2024, 2, 1),
                "NAV": 11.0,
            },
        ),
        date_column="NAV Date",
        value_column="NAV",
    )

    assert result[-1].value == pytest.approx(11.0)


def test_create_dated_values_requires_two_records() -> None:
    """
    At least two historical records are required.
    """

    with pytest.raises(
        AnalyticsDataAdapterError,
        match="at least two records",
    ):
        create_dated_values(
            (
                {
                    "Date": date(2024, 1, 1),
                    "Value": 100.0,
                },
            )
        )


def test_create_dated_values_rejects_duplicate_dates() -> None:
    """
    Duplicate historical dates should be rejected.
    """

    with pytest.raises(
        AnalyticsDataAdapterError,
        match="Duplicate historical date",
    ):
        create_dated_values(
            (
                {
                    "Date": date(2024, 1, 1),
                    "Value": 100.0,
                },
                {
                    "Date": date(2024, 1, 1),
                    "Value": 110.0,
                },
            )
        )


def test_create_dated_values_rejects_invalid_date() -> None:
    """
    Invalid date strings should be rejected.
    """

    with pytest.raises(
        AnalyticsDataAdapterError,
        match="valid ISO-format date",
    ):
        create_dated_values(
            (
                {
                    "Date": "not-a-date",
                    "Value": 100.0,
                },
                {
                    "Date": "2024-02-01",
                    "Value": 110.0,
                },
            )
        )


@pytest.mark.parametrize(
    "value",
    [
        0.0,
        -1.0,
        True,
        float("nan"),
        float("inf"),
    ],
)
def test_create_dated_values_rejects_invalid_values(
    value: object,
) -> None:
    """
    Historical values must be finite and strictly positive.
    """

    with pytest.raises(AnalyticsDataAdapterError):
        create_dated_values(
            (
                {
                    "Date": date(2024, 1, 1),
                    "Value": value,
                },
                {
                    "Date": date(2024, 2, 1),
                    "Value": 110.0,
                },
            )
        )


# ============================================================
# Periodic Return Tests
# ============================================================


def test_calculate_periodic_returns_from_dated_values() -> None:
    """
    Dated values should convert to periodic returns.
    """

    values = (
        DatedValue(
            observation_date=date(2024, 1, 1),
            value=100.0,
        ),
        DatedValue(
            observation_date=date(2024, 2, 1),
            value=110.0,
        ),
        DatedValue(
            observation_date=date(2024, 3, 1),
            value=99.0,
        ),
    )

    result = calculate_periodic_returns_from_dated_values(
        values
    )

    assert result == pytest.approx(
        (
            0.10,
            -0.10,
        )
    )


def test_calculate_periodic_returns_from_history(
    history_records: tuple[dict[str, object], ...],
) -> None:
    """
    History records should convert directly to returns.
    """

    result = calculate_periodic_returns_from_history(
        history_records
    )

    assert result == pytest.approx(
        (
            0.10,
            -0.10,
            0.10,
        )
    )


def test_periodic_returns_require_three_dated_values() -> None:
    """
    Three values are required to produce two returns.
    """

    with pytest.raises(
        AnalyticsDataAdapterError,
        match="At least three dated values",
    ):
        calculate_periodic_returns_from_dated_values(
            (
                DatedValue(
                    observation_date=date(2024, 1, 1),
                    value=100.0,
                ),
                DatedValue(
                    observation_date=date(2024, 2, 1),
                    value=110.0,
                ),
            )
        )


# ============================================================
# CAGR Adapter Tests
# ============================================================


def test_create_cagr_input_from_values() -> None:
    """
    Explicit values should create a date-based CAGR input.
    """

    result = create_cagr_input_from_values(
        initial_value=100.0,
        final_value=121.0,
        start_date="2023-01-01",
        end_date="2025-01-01",
    )

    assert isinstance(result, DateBasedCAGRInput)
    assert result.initial_value == pytest.approx(100.0)
    assert result.final_value == pytest.approx(121.0)
    assert result.start_date == date(2023, 1, 1)
    assert result.end_date == date(2025, 1, 1)


def test_create_cagr_input_from_history(
    history_records: tuple[dict[str, object], ...],
) -> None:
    """
    CAGR history adapter should use first and final values.
    """

    result = create_cagr_input_from_history(
        history_records
    )

    assert result.initial_value == pytest.approx(100.0)
    assert result.final_value == pytest.approx(108.9)
    assert result.start_date == date(2024, 1, 1)
    assert result.end_date == date(2024, 4, 1)


def test_create_cagr_input_rejects_zero_initial_value() -> None:
    """
    CAGR initial value must be positive.
    """

    with pytest.raises(
        AnalyticsDataAdapterError,
        match="initial_value must be greater than zero",
    ):
        create_cagr_input_from_values(
            initial_value=0.0,
            final_value=100.0,
            start_date=date(2024, 1, 1),
            end_date=date(2025, 1, 1),
        )


def test_create_cagr_input_allows_zero_final_value() -> None:
    """
    A complete loss should allow a zero final value.
    """

    result = create_cagr_input_from_values(
        initial_value=100.0,
        final_value=0.0,
        start_date=date(2024, 1, 1),
        end_date=date(2025, 1, 1),
    )

    assert result.final_value == pytest.approx(0.0)


# ============================================================
# Cash Flow and XIRR Adapter Tests
# ============================================================


def test_create_dated_cash_flows(
    cash_flow_records: tuple[dict[str, object], ...],
) -> None:
    """
    Transaction records should become sorted dated cash flows.
    """

    result = create_dated_cash_flows(
        cash_flow_records
    )

    assert result == (
        DatedCashFlow(
            flow_date=date(2023, 1, 1),
            amount=-50_000.0,
        ),
        DatedCashFlow(
            flow_date=date(2023, 6, 1),
            amount=-25_000.0,
        ),
    )


def test_create_dated_cash_flows_sorts_records() -> None:
    """
    Cash-flow records should be sorted chronologically.
    """

    result = create_dated_cash_flows(
        (
            {
                "Date": date(2024, 1, 1),
                "Amount": 120.0,
            },
            {
                "Date": date(2023, 1, 1),
                "Amount": -100.0,
            },
        )
    )

    assert result[0].amount == pytest.approx(-100.0)


def test_create_dated_cash_flows_supports_custom_columns() -> None:
    """
    Custom transaction column names should be supported.
    """

    result = create_dated_cash_flows(
        (
            {
                "Transaction Date": date(2023, 1, 1),
                "Cash": -100.0,
            },
            {
                "Transaction Date": date(2024, 1, 1),
                "Cash": 120.0,
            },
        ),
        date_column="Transaction Date",
        amount_column="Cash",
    )

    assert len(result) == 2


def test_create_dated_cash_flows_requires_two_records() -> None:
    """
    At least two cash-flow records are required.
    """

    with pytest.raises(
        AnalyticsDataAdapterError,
        match="at least two records",
    ):
        create_dated_cash_flows(
            (
                {
                    "Date": date(2023, 1, 1),
                    "Amount": -100.0,
                },
            )
        )


def test_create_xirr_input_without_terminal_value() -> None:
    """
    Existing complete cash-flow history should create XIRR input.
    """

    result = create_xirr_input(
        (
            {
                "Date": date(2023, 1, 1),
                "Amount": -100.0,
            },
            {
                "Date": date(2024, 1, 1),
                "Amount": 120.0,
            },
        )
    )

    assert isinstance(result, XIRRInput)
    assert len(result.cash_flows) == 2
    assert result.cash_flows[-1].amount == pytest.approx(
        120.0
    )


def test_create_xirr_input_appends_current_value(
    cash_flow_records: tuple[dict[str, object], ...],
) -> None:
    """
    Current value should be appended as a positive terminal cash flow.
    """

    result = create_xirr_input(
        cash_flow_records,
        current_value=90_000.0,
        valuation_date=date(2024, 1, 1),
    )

    assert len(result.cash_flows) == 3
    assert result.cash_flows[-1].amount == pytest.approx(
        90_000.0
    )

    assert result.cash_flows[-1].flow_date == date(
        2024,
        1,
        1,
    )


def test_create_xirr_input_requires_valuation_date(
    cash_flow_records: tuple[dict[str, object], ...],
) -> None:
    """
    valuation_date is required when current_value is supplied.
    """

    with pytest.raises(
        AnalyticsDataAdapterError,
        match="valuation_date is required",
    ):
        create_xirr_input(
            cash_flow_records,
            current_value=90_000.0,
        )


def test_create_xirr_input_requires_current_value(
    cash_flow_records: tuple[dict[str, object], ...],
) -> None:
    """
    current_value is required when valuation_date is supplied.
    """

    with pytest.raises(
        AnalyticsDataAdapterError,
        match="current_value is required",
    ):
        create_xirr_input(
            cash_flow_records,
            valuation_date=date(2024, 1, 1),
        )


@pytest.mark.parametrize(
    "max_iterations",
    [
        0,
        -1,
        True,
        10.5,
    ],
)
def test_create_xirr_input_rejects_invalid_max_iterations(
    max_iterations: object,
    cash_flow_records: tuple[dict[str, object], ...],
) -> None:
    """
    max_iterations must be a strict positive integer.
    """

    with pytest.raises(AnalyticsDataAdapterError):
        create_xirr_input(
            cash_flow_records,
            max_iterations=max_iterations,  # type: ignore[arg-type]
        )


# ============================================================
# Drawdown Adapter Tests
# ============================================================


def test_create_drawdown_input(
    history_records: tuple[dict[str, object], ...],
) -> None:
    """
    Historical values should create DrawdownInput.
    """

    result = create_drawdown_input(
        history_records
    )

    assert isinstance(result, DrawdownInput)
    assert len(result.observations) == 4

    assert result.observations[0].observation_date == date(
        2024,
        1,
        1,
    )


# ============================================================
# Volatility Adapter Tests
# ============================================================


def test_create_volatility_input() -> None:
    """
    Return sequence should create VolatilityInput.
    """

    result = create_volatility_input(
        (
            0.01,
            -0.02,
            0.03,
        ),
        periods_per_year=12,
    )

    assert isinstance(result, VolatilityInput)
    assert result.returns == (
        0.01,
        -0.02,
        0.03,
    )

    assert result.periods_per_year == 12


def test_create_volatility_input_from_history(
    history_records: tuple[dict[str, object], ...],
) -> None:
    """
    Historical values should create volatility input.
    """

    result = create_volatility_input_from_history(
        history_records,
        periods_per_year=12,
    )

    assert result.returns == pytest.approx(
        (
            0.10,
            -0.10,
            0.10,
        )
    )


def test_create_volatility_input_rejects_one_return() -> None:
    """
    At least two return observations are required.
    """

    with pytest.raises(
        AnalyticsDataAdapterError,
        match="at least two observations",
    ):
        create_volatility_input(
            (0.01,),
            periods_per_year=12,
        )


def test_create_volatility_input_rejects_string() -> None:
    """
    Strings should not be treated as return sequences.
    """

    with pytest.raises(
        AnalyticsDataAdapterError,
        match="iterable of numeric values",
    ):
        create_volatility_input(
            "invalid",  # type: ignore[arg-type]
            periods_per_year=12,
        )


# ============================================================
# Risk Metrics Adapter Tests
# ============================================================


def test_create_risk_metrics_input() -> None:
    """
    Return sequence should create RiskMetricsInput.
    """

    result = create_risk_metrics_input(
        (
            0.01,
            -0.02,
            0.03,
        ),
        periods_per_year=12,
        annual_risk_free_rate=0.06,
        annual_minimum_acceptable_return=0.04,
    )

    assert isinstance(result, RiskMetricsInput)
    assert result.periods_per_year == 12
    assert result.annual_risk_free_rate == pytest.approx(
        0.06
    )

    assert (
        result.annual_minimum_acceptable_return
        == pytest.approx(0.04)
    )


def test_create_risk_metrics_input_from_history(
    history_records: tuple[dict[str, object], ...],
) -> None:
    """
    Historical values should create risk-metric input.
    """

    result = create_risk_metrics_input_from_history(
        history_records,
        periods_per_year=12,
    )

    assert result.returns == pytest.approx(
        (
            0.10,
            -0.10,
            0.10,
        )
    )


# ============================================================
# Rolling Return Adapter Tests
# ============================================================


def test_create_rolling_returns_input(
    history_records: tuple[dict[str, object], ...],
) -> None:
    """
    Historical values should create RollingReturnsInput.
    """

    result = create_rolling_returns_input(
        history_records,
        window_size=2,
        annualise=False,
        target_return=0.05,
    )

    assert isinstance(result, RollingReturnsInput)
    assert len(result.observations) == 4
    assert result.window_size == 2
    assert result.annualise is False
    assert result.target_return == pytest.approx(0.05)


def test_create_rolling_returns_input_rejects_invalid_annualise(
    history_records: tuple[dict[str, object], ...],
) -> None:
    """
    annualise must be a strict boolean.
    """

    with pytest.raises(
        AnalyticsDataAdapterError,
        match="annualise must be a boolean",
    ):
        create_rolling_returns_input(
            history_records,
            window_size=2,
            annualise=1,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "window_size",
    [
        0,
        -1,
        True,
        2.5,
    ],
)
def test_create_rolling_returns_input_rejects_invalid_window(
    window_size: object,
    history_records: tuple[dict[str, object], ...],
) -> None:
    """
    window_size must be a strict positive integer.
    """

    with pytest.raises(AnalyticsDataAdapterError):
        create_rolling_returns_input(
            history_records,
            window_size=window_size,  # type: ignore[arg-type]
        )


# ============================================================
# Benchmark Adapter Tests
# ============================================================


def test_create_aligned_return_series(
    aligned_return_records: tuple[dict[str, float], ...],
) -> None:
    """
    Aligned return records should create two return sequences.
    """

    result = create_aligned_return_series(
        aligned_return_records
    )

    assert isinstance(result, AlignedReturnSeries)
    assert result.observation_count == 3

    assert result.portfolio_returns == (
        0.02,
        -0.01,
        0.015,
    )

    assert result.benchmark_returns == (
        0.018,
        -0.012,
        0.012,
    )


def test_create_aligned_return_series_supports_custom_columns() -> None:
    """
    Custom aligned return columns should be supported.
    """

    result = create_aligned_return_series(
        (
            {
                "Portfolio": 0.01,
                "Index": 0.008,
            },
            {
                "Portfolio": -0.01,
                "Index": -0.012,
            },
        ),
        portfolio_return_column="Portfolio",
        benchmark_return_column="Index",
    )

    assert result.observation_count == 2


def test_create_aligned_return_series_requires_two_records() -> None:
    """
    At least two aligned records are required.
    """

    with pytest.raises(
        AnalyticsDataAdapterError,
        match="at least two records",
    ):
        create_aligned_return_series(
            (
                {
                    "Portfolio Return": 0.01,
                    "Benchmark Return": 0.008,
                },
            )
        )


def test_create_benchmark_input() -> None:
    """
    Aligned return sequences should create BenchmarkInput.
    """

    result = create_benchmark_input(
        (
            0.01,
            -0.01,
            0.02,
        ),
        (
            0.008,
            -0.012,
            0.015,
        ),
        periods_per_year=12,
        annual_risk_free_rate=0.06,
        benchmark_name="Nifty 50 TRI",
    )

    assert isinstance(result, BenchmarkInput)
    assert result.benchmark_name == "Nifty 50 TRI"
    assert result.periods_per_year == 12


def test_create_benchmark_input_requires_equal_lengths() -> None:
    """
    Portfolio and benchmark sequences must align.
    """

    with pytest.raises(
        AnalyticsDataAdapterError,
        match="same number of observations",
    ):
        create_benchmark_input(
            (
                0.01,
                0.02,
                0.03,
            ),
            (
                0.01,
                0.02,
            ),
        )


def test_create_benchmark_input_from_records(
    aligned_return_records: tuple[dict[str, float], ...],
) -> None:
    """
    Tabular aligned returns should create BenchmarkInput.
    """

    result = create_benchmark_input_from_records(
        aligned_return_records,
        periods_per_year=12,
        benchmark_name="Nifty 50 TRI",
    )

    assert result.portfolio_returns == (
        0.02,
        -0.01,
        0.015,
    )

    assert result.benchmark_returns == (
        0.018,
        -0.012,
        0.012,
    )


# ============================================================
# Advanced Analytics Adapter Tests
# ============================================================


def test_create_complete_advanced_analytics_input(
    history_records: tuple[dict[str, object], ...],
    cash_flow_records: tuple[dict[str, object], ...],
    aligned_return_records: tuple[dict[str, float], ...],
) -> None:
    """
    All supplied datasets should create all advanced metric inputs.
    """

    result = create_advanced_analytics_input(
        portfolio_history=history_records,
        cash_flow_history=cash_flow_records,
        aligned_benchmark_returns=aligned_return_records,
        current_value=90_000.0,
        valuation_date=date(2024, 1, 1),
        periods_per_year=12,
        benchmark_name="Nifty 50 TRI",
        rolling_window_size=2,
        rolling_annualise=False,
    )

    assert isinstance(result, AnalyticsAdapterResult)
    assert isinstance(
        result.analytics_input,
        AdvancedAnalyticsInput,
    )

    assert result.analytics_input.cagr is not None
    assert result.analytics_input.xirr is not None
    assert result.analytics_input.volatility is not None
    assert result.analytics_input.drawdown is not None
    assert result.analytics_input.risk_metrics is not None
    assert result.analytics_input.benchmark is not None
    assert result.analytics_input.rolling_returns is not None

    assert result.available_metrics == (
        "cagr",
        "volatility",
        "drawdown",
        "risk_metrics",
        "rolling_returns",
        "xirr",
        "benchmark",
    )

    assert result.unavailable_metrics == ()


def test_create_advanced_input_with_only_history(
    history_records: tuple[dict[str, object], ...],
) -> None:
    """
    Portfolio history should create five supported metric inputs.
    """

    result = create_advanced_analytics_input(
        portfolio_history=history_records,
        periods_per_year=12,
        rolling_window_size=2,
    )

    assert result.analytics_input.cagr is not None
    assert result.analytics_input.volatility is not None
    assert result.analytics_input.drawdown is not None
    assert result.analytics_input.risk_metrics is not None
    assert result.analytics_input.rolling_returns is not None

    assert result.analytics_input.xirr is None
    assert result.analytics_input.benchmark is None

    assert result.unavailable_metrics == (
        "xirr",
        "benchmark",
    )


def test_create_advanced_input_with_no_data() -> None:
    """
    Missing datasets should produce an empty analytics input.
    """

    result = create_advanced_analytics_input()

    assert result.analytics_input.cagr is None
    assert result.analytics_input.xirr is None
    assert result.analytics_input.volatility is None
    assert result.analytics_input.drawdown is None
    assert result.analytics_input.risk_metrics is None
    assert result.analytics_input.benchmark is None
    assert result.analytics_input.rolling_returns is None

    assert result.available_metrics == ()

    assert result.unavailable_metrics == (
        "cagr",
        "volatility",
        "drawdown",
        "risk_metrics",
        "rolling_returns",
        "xirr",
        "benchmark",
    )


def test_create_advanced_input_preserves_fail_fast(
    history_records: tuple[dict[str, object], ...],
) -> None:
    """
    fail_fast should be preserved in the orchestration input.
    """

    result = create_advanced_analytics_input(
        portfolio_history=history_records,
        rolling_window_size=2,
        fail_fast=True,
    )

    assert result.analytics_input.fail_fast is True


def test_create_advanced_input_rejects_invalid_fail_fast() -> None:
    """
    fail_fast must be a strict boolean.
    """

    with pytest.raises(
        AnalyticsDataAdapterError,
        match="fail_fast must be a boolean",
    ):
        create_advanced_analytics_input(
            fail_fast=1,  # type: ignore[arg-type]
        )


def test_create_advanced_input_requires_enough_history() -> None:
    """
    Portfolio history must contain enough values to generate returns.
    """

    history = (
        {
            "Date": date(2024, 1, 1),
            "Value": 100.0,
        },
        {
            "Date": date(2024, 2, 1),
            "Value": 110.0,
        },
    )

    with pytest.raises(
        AnalyticsDataAdapterError,
        match="At least three dated values",
    ):
        create_advanced_analytics_input(
            portfolio_history=history,
            rolling_window_size=1,
        )


# ============================================================
# Generic Source Validation Tests
# ============================================================


def test_adapter_rejects_none_source() -> None:
    """
    Direct adapter functions should reject None source data.
    """

    with pytest.raises(
        AnalyticsDataAdapterError,
        match="cannot be None",
    ):
        create_dated_values(None)


def test_adapter_rejects_string_source() -> None:
    """
    Strings should not be treated as record collections.
    """

    with pytest.raises(
        AnalyticsDataAdapterError,
        match="tabular data or an iterable of mappings",
    ):
        create_dated_values(
            "invalid"  # type: ignore[arg-type]
        )


def test_adapter_rejects_non_mapping_records() -> None:
    """
    Every tabular record must be a mapping.
    """

    with pytest.raises(
        AnalyticsDataAdapterError,
        match=r"history_data\[1\] must be a mapping",
    ):
        create_dated_values(
            (
                {
                    "Date": date(2024, 1, 1),
                    "Value": 100.0,
                },
                "invalid record",
            )
        )


def test_adapter_rejects_non_iterable_source() -> None:
    """
    Unsupported non-iterable sources should be rejected.
    """

    with pytest.raises(
        AnalyticsDataAdapterError,
        match="tabular data or an iterable of mappings",
    ):
        create_dated_values(
            123  # type: ignore[arg-type]
        )


# ============================================================
# Dataclass Immutability Tests
# ============================================================


def test_portfolio_snapshot_totals_is_immutable() -> None:
    """
    PortfolioSnapshotTotals should be immutable.
    """

    result = PortfolioSnapshotTotals(
        row_count=1,
        total_investment=100.0,
        total_current_value=120.0,
        total_profit_loss=20.0,
        total_return_decimal=0.20,
        total_return_percent=20.0,
    )

    with pytest.raises(FrozenInstanceError):
        result.row_count = 2  # type: ignore[misc]


def test_dated_value_is_immutable() -> None:
    """
    DatedValue should be immutable.
    """

    value = DatedValue(
        observation_date=date(2024, 1, 1),
        value=100.0,
    )

    with pytest.raises(FrozenInstanceError):
        value.value = 120.0  # type: ignore[misc]


def test_dated_cash_flow_is_immutable() -> None:
    """
    DatedCashFlow should be immutable.
    """

    cash_flow = DatedCashFlow(
        flow_date=date(2024, 1, 1),
        amount=-100.0,
    )

    with pytest.raises(FrozenInstanceError):
        cash_flow.amount = -200.0  # type: ignore[misc]


def test_aligned_return_series_is_immutable() -> None:
    """
    AlignedReturnSeries should be immutable.
    """

    result = AlignedReturnSeries(
        portfolio_returns=(0.01, 0.02),
        benchmark_returns=(0.01, 0.015),
        observation_count=2,
    )

    with pytest.raises(FrozenInstanceError):
        result.observation_count = 3  # type: ignore[misc]


def test_analytics_adapter_result_is_immutable() -> None:
    """
    AnalyticsAdapterResult should be immutable.
    """

    result = AnalyticsAdapterResult(
        analytics_input=AdvancedAnalyticsInput(),
        available_metrics=(),
        unavailable_metrics=("cagr",),
    )

    with pytest.raises(FrozenInstanceError):
        result.available_metrics = ("cagr",)  # type: ignore[misc]


# ============================================================
# Consistency Tests
# ============================================================


def test_snapshot_percentage_matches_decimal(
    portfolio_records: tuple[dict[str, float], ...],
) -> None:
    """
    Snapshot percentage return should equal decimal return times 100.
    """

    result = calculate_portfolio_snapshot_totals(
        portfolio_records
    )

    assert result.total_return_percent == pytest.approx(
        result.total_return_decimal * 100.0
    )


def test_advanced_available_and_unavailable_metrics_are_disjoint(
    history_records: tuple[dict[str, object], ...],
) -> None:
    """
    A metric cannot be both available and unavailable.
    """

    result = create_advanced_analytics_input(
        portfolio_history=history_records,
        rolling_window_size=2,
    )

    assert set(result.available_metrics).isdisjoint(
        result.unavailable_metrics
    )


def test_advanced_metric_inventory_is_complete(
    history_records: tuple[dict[str, object], ...],
) -> None:
    """
    Available and unavailable metrics should cover all seven metrics.
    """

    result = create_advanced_analytics_input(
        portfolio_history=history_records,
        rolling_window_size=2,
    )

    combined = (
        result.available_metrics
        + result.unavailable_metrics
    )

    assert set(combined) == {
        "cagr",
        "xirr",
        "volatility",
        "drawdown",
        "risk_metrics",
        "benchmark",
        "rolling_returns",
    }