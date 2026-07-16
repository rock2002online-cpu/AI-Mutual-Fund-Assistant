"""
Tests for services.advanced_analytics_service.

These tests validate:

- Service input validation
- PortfolioService dependency handling
- Current portfolio retrieval
- Portfolio snapshot totals
- Advanced analytics execution
- Automatic XIRR terminal valuation
- Complete, partial, unavailable, and failed statuses
- fail_fast behaviour
- Custom column support
- Functional convenience API
- Result utility functions
- Service-level failure reporting
- Immutable dataclasses
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date
from typing import Any

import pytest

from services.advanced_analytics_service import (
    AdvancedAnalyticsExecutionError,
    AdvancedAnalyticsService,
    AdvancedAnalyticsServiceFailure,
    AdvancedAnalyticsServiceInput,
    AdvancedAnalyticsServiceResult,
    AdvancedAnalyticsServiceValidationError,
    PortfolioDataUnavailableError,
    calculate_advanced_portfolio_analytics,
    get_service_failure_messages,
    has_advanced_analytics,
    has_portfolio_totals,
    validate_advanced_analytics_service_input,
)


# ============================================================
# Test Doubles
# ============================================================


class FakePortfolioService:
    """
    Minimal PortfolioService-compatible test double.
    """

    def __init__(
        self,
        portfolio: Any,
    ) -> None:
        self._portfolio = portfolio
        self.call_count = 0

    def get_portfolio(self) -> Any:
        """
        Return the configured portfolio.
        """

        self.call_count += 1
        return self._portfolio


class FailingPortfolioService:
    """
    PortfolioService-compatible test double that raises an error.
    """

    def get_portfolio(self) -> Any:
        """
        Simulate a portfolio retrieval failure.
        """

        raise RuntimeError("Portfolio source unavailable.")


class InvalidPortfolioService:
    """
    Object that does not provide get_portfolio().
    """


class FakeDataFrame:
    """
    Minimal DataFrame-like object used by adapter tests.
    """

    def __init__(
        self,
        records: list[dict[str, object]],
    ) -> None:
        self._records = records
        self.empty = len(records) == 0

    def to_dict(
        self,
        orient: str,
    ) -> list[dict[str, object]]:
        """
        Return mapping records.
        """

        if orient != "records":
            raise ValueError("Unsupported orientation.")

        return self._records

    def __len__(self) -> int:
        return len(self._records)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def portfolio_records() -> tuple[dict[str, object], ...]:
    """
    Return a representative current portfolio.
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
def portfolio_history() -> tuple[dict[str, object], ...]:
    """
    Return historical portfolio value records.
    """

    return (
        {
            "Date": date(2024, 1, 1),
            "Value": 150_000.0,
        },
        {
            "Date": date(2024, 2, 1),
            "Value": 155_000.0,
        },
        {
            "Date": date(2024, 3, 1),
            "Value": 148_000.0,
        },
        {
            "Date": date(2024, 4, 1),
            "Value": 162_000.0,
        },
        {
            "Date": date(2024, 5, 1),
            "Value": 170_000.0,
        },
    )


@pytest.fixture
def cash_flow_history() -> tuple[dict[str, object], ...]:
    """
    Return historical investment cash flows.
    """

    return (
        {
            "Date": date(2023, 1, 1),
            "Amount": -100_000.0,
        },
        {
            "Date": date(2023, 6, 1),
            "Amount": -40_000.0,
        },
    )


@pytest.fixture
def aligned_benchmark_returns() -> tuple[
    dict[str, object],
    ...,
]:
    """
    Return aligned portfolio and benchmark returns.
    """

    return (
        {
            "Portfolio Return": 0.020,
            "Benchmark Return": 0.018,
        },
        {
            "Portfolio Return": -0.010,
            "Benchmark Return": -0.012,
        },
        {
            "Portfolio Return": 0.015,
            "Benchmark Return": 0.012,
        },
        {
            "Portfolio Return": 0.025,
            "Benchmark Return": 0.020,
        },
    )


@pytest.fixture
def fake_portfolio_service(
    portfolio_records: tuple[dict[str, object], ...],
) -> FakePortfolioService:
    """
    Return a valid PortfolioService test double.
    """

    return FakePortfolioService(
        portfolio_records
    )


@pytest.fixture
def complete_service_input(
    portfolio_history: tuple[dict[str, object], ...],
    cash_flow_history: tuple[dict[str, object], ...],
    aligned_benchmark_returns: tuple[
        dict[str, object],
        ...,
    ],
) -> AdvancedAnalyticsServiceInput:
    """
    Return complete service input for all metrics.
    """

    return AdvancedAnalyticsServiceInput(
        portfolio_history=portfolio_history,
        cash_flow_history=cash_flow_history,
        aligned_benchmark_returns=(
            aligned_benchmark_returns
        ),
        valuation_date=date(2024, 5, 1),
        periods_per_year=12,
        annual_risk_free_rate=0.06,
        annual_minimum_acceptable_return=0.04,
        benchmark_name="Nifty 50 TRI",
        rolling_window_size=2,
        rolling_annualise=False,
        rolling_target_return=0.05,
        fail_fast=False,
    )


# ============================================================
# Service Input Validation Tests
# ============================================================


def test_validate_service_input() -> None:
    """
    Valid service input should be normalised and returned.
    """

    input_data = AdvancedAnalyticsServiceInput(
        periods_per_year=12,
        benchmark_name="  Nifty 50 TRI  ",
        rolling_window_size=3,
        rolling_annualise=False,
        fail_fast=True,
    )

    result = validate_advanced_analytics_service_input(
        input_data
    )

    assert result.periods_per_year == 12
    assert result.benchmark_name == "Nifty 50 TRI"
    assert result.rolling_window_size == 3
    assert result.rolling_annualise is False
    assert result.fail_fast is True


def test_validate_service_input_rejects_wrong_type() -> None:
    """
    Input validation should reject unsupported objects.
    """

    with pytest.raises(
        TypeError,
        match="AdvancedAnalyticsServiceInput",
    ):
        validate_advanced_analytics_service_input(  # type: ignore[arg-type]
            {}
        )


@pytest.mark.parametrize(
    "periods_per_year",
    [
        0,
        -1,
        True,
        12.5,
        "12",
    ],
)
def test_validate_service_input_rejects_invalid_periods(
    periods_per_year: object,
) -> None:
    """
    periods_per_year must be a strict positive integer.
    """

    with pytest.raises(
        AdvancedAnalyticsServiceValidationError,
    ):
        validate_advanced_analytics_service_input(
            AdvancedAnalyticsServiceInput(
                periods_per_year=periods_per_year,  # type: ignore[arg-type]
            )
        )


@pytest.mark.parametrize(
    "window_size",
    [
        0,
        -1,
        True,
        2.5,
        "2",
    ],
)
def test_validate_service_input_rejects_invalid_window(
    window_size: object,
) -> None:
    """
    rolling_window_size must be a strict positive integer.
    """

    with pytest.raises(
        AdvancedAnalyticsServiceValidationError,
    ):
        validate_advanced_analytics_service_input(
            AdvancedAnalyticsServiceInput(
                rolling_window_size=window_size,  # type: ignore[arg-type]
            )
        )


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("rolling_annualise", 1),
        ("rolling_annualise", "true"),
        ("fail_fast", 1),
        ("fail_fast", "false"),
        (
            "use_current_portfolio_value_for_xirr",
            1,
        ),
        (
            "use_current_portfolio_value_for_xirr",
            "yes",
        ),
    ],
)
def test_validate_service_input_rejects_invalid_booleans(
    field_name: str,
    field_value: object,
) -> None:
    """
    Service boolean fields must use strict bool values.
    """

    values: dict[str, object] = {
        "rolling_annualise": True,
        "fail_fast": False,
        "use_current_portfolio_value_for_xirr": True,
    }

    values[field_name] = field_value

    with pytest.raises(
        AdvancedAnalyticsServiceValidationError,
        match="must be a boolean",
    ):
        validate_advanced_analytics_service_input(
            AdvancedAnalyticsServiceInput(
                rolling_annualise=values[
                    "rolling_annualise"
                ],  # type: ignore[arg-type]
                fail_fast=values[
                    "fail_fast"
                ],  # type: ignore[arg-type]
                use_current_portfolio_value_for_xirr=values[
                    "use_current_portfolio_value_for_xirr"
                ],  # type: ignore[arg-type]
            )
        )


@pytest.mark.parametrize(
    "column_field",
    [
        "investment_column",
        "current_value_column",
        "history_date_column",
        "history_value_column",
        "cash_flow_date_column",
        "cash_flow_amount_column",
        "portfolio_return_column",
        "benchmark_return_column",
    ],
)
def test_validate_service_input_rejects_empty_column_names(
    column_field: str,
) -> None:
    """
    Required column names cannot be empty.
    """

    values = {
        "investment_column": "Investment",
        "current_value_column": "Current Value",
        "history_date_column": "Date",
        "history_value_column": "Value",
        "cash_flow_date_column": "Date",
        "cash_flow_amount_column": "Amount",
        "portfolio_return_column": "Portfolio Return",
        "benchmark_return_column": "Benchmark Return",
    }

    values[column_field] = "   "

    with pytest.raises(
        AdvancedAnalyticsServiceValidationError,
        match="cannot be empty",
    ):
        validate_advanced_analytics_service_input(
            AdvancedAnalyticsServiceInput(
                investment_column=values[
                    "investment_column"
                ],
                current_value_column=values[
                    "current_value_column"
                ],
                history_date_column=values[
                    "history_date_column"
                ],
                history_value_column=values[
                    "history_value_column"
                ],
                cash_flow_date_column=values[
                    "cash_flow_date_column"
                ],
                cash_flow_amount_column=values[
                    "cash_flow_amount_column"
                ],
                portfolio_return_column=values[
                    "portfolio_return_column"
                ],
                benchmark_return_column=values[
                    "benchmark_return_column"
                ],
            )
        )


def test_validate_service_input_requires_current_value_with_valuation_date() -> None:
    """
    Explicit valuation_date requires explicit current_value only when
    automatic portfolio valuation for XIRR is disabled.
    """

    with pytest.raises(
        AdvancedAnalyticsServiceValidationError,
        match="current_value is required",
    ):
        validate_advanced_analytics_service_input(
            AdvancedAnalyticsServiceInput(
                cash_flow_history=(
                    {
                        "Date": date(2023, 1, 1),
                        "Amount": -100.0,
                    },
                    {
                        "Date": date(2024, 1, 1),
                        "Amount": 120.0,
                    },
                ),
                valuation_date=date(2024, 1, 1),
                current_value=None,
                use_current_portfolio_value_for_xirr=False,
            )
        )

def test_validate_service_input_converts_blank_benchmark_name_to_none() -> None:
    """
    Blank optional benchmark name should become None.
    """

    result = validate_advanced_analytics_service_input(
        AdvancedAnalyticsServiceInput(
            benchmark_name="   ",
        )
    )

    assert result.benchmark_name is None


# ============================================================
# Service Construction Tests
# ============================================================


def test_service_accepts_compatible_dependency(
    fake_portfolio_service: FakePortfolioService,
) -> None:
    """
    A PortfolioService-compatible object should be accepted.
    """

    service = AdvancedAnalyticsService(
        portfolio_service=fake_portfolio_service
    )

    assert service.get_current_portfolio() is not None


def test_service_rejects_incompatible_dependency() -> None:
    """
    Dependencies without get_portfolio() should be rejected.
    """

    with pytest.raises(
        TypeError,
        match="get_portfolio",
    ):
        AdvancedAnalyticsService(
            portfolio_service=InvalidPortfolioService(),  # type: ignore[arg-type]
        )


# ============================================================
# Portfolio Retrieval Tests
# ============================================================


def test_get_current_portfolio(
    fake_portfolio_service: FakePortfolioService,
    portfolio_records: tuple[dict[str, object], ...],
) -> None:
    """
    Service should retrieve the current portfolio once.
    """

    service = AdvancedAnalyticsService(
        portfolio_service=fake_portfolio_service
    )

    result = service.get_current_portfolio()

    assert result == portfolio_records
    assert fake_portfolio_service.call_count == 1


def test_get_current_portfolio_rejects_none() -> None:
    """
    None portfolio data should be treated as unavailable.
    """

    service = AdvancedAnalyticsService(
        portfolio_service=FakePortfolioService(None)
    )

    with pytest.raises(
        PortfolioDataUnavailableError,
        match="no portfolio data",
    ):
        service.get_current_portfolio()


def test_get_current_portfolio_rejects_empty_sequence() -> None:
    """
    Empty portfolio sequences should be rejected.
    """

    service = AdvancedAnalyticsService(
        portfolio_service=FakePortfolioService(())
    )

    with pytest.raises(
        PortfolioDataUnavailableError,
        match="empty portfolio",
    ):
        service.get_current_portfolio()


def test_get_current_portfolio_rejects_empty_dataframe_like_object() -> None:
    """
    Empty DataFrame-like portfolio data should be rejected.
    """

    service = AdvancedAnalyticsService(
        portfolio_service=FakePortfolioService(
            FakeDataFrame([])
        )
    )

    with pytest.raises(
        PortfolioDataUnavailableError,
        match="empty portfolio",
    ):
        service.get_current_portfolio()


def test_get_current_portfolio_wraps_source_error() -> None:
    """
    Portfolio retrieval exceptions should be wrapped.
    """

    service = AdvancedAnalyticsService(
        portfolio_service=FailingPortfolioService()
    )

    with pytest.raises(
        PortfolioDataUnavailableError,
        match="Unable to retrieve portfolio data",
    ) as exc_info:
        service.get_current_portfolio()

    assert isinstance(
        exc_info.value.__cause__,
        RuntimeError,
    )


# ============================================================
# Portfolio Totals Tests
# ============================================================


def test_calculate_without_history_returns_portfolio_totals(
    fake_portfolio_service: FakePortfolioService,
) -> None:
    """
    Current portfolio totals should be available without historical data.
    """

    service = AdvancedAnalyticsService(
        portfolio_service=fake_portfolio_service
    )

    result = service.calculate()

    assert isinstance(
        result,
        AdvancedAnalyticsServiceResult,
    )

    assert result.status == "unavailable"
    assert result.portfolio_totals is not None

    assert (
        result.portfolio_totals.total_investment
        == pytest.approx(150_000.0)
    )

    assert (
        result.portfolio_totals.total_current_value
        == pytest.approx(170_000.0)
    )

    assert result.analytics is not None
    assert result.analytics.status == "unavailable"

    assert result.available_metrics == ()

    assert set(result.unavailable_metrics) == {
        "cagr",
        "xirr",
        "volatility",
        "drawdown",
        "risk_metrics",
        "benchmark",
        "rolling_returns",
    }


def test_calculate_supports_dataframe_like_portfolio(
    portfolio_records: tuple[dict[str, object], ...],
) -> None:
    """
    Portfolio totals should support DataFrame-like data.
    """

    portfolio = FakeDataFrame(
        list(portfolio_records)
    )

    service = AdvancedAnalyticsService(
        portfolio_service=FakePortfolioService(
            portfolio
        )
    )

    result = service.calculate()

    assert result.portfolio_totals is not None
    assert result.portfolio_totals.row_count == 2


def test_calculate_raises_when_portfolio_columns_missing() -> None:
    """
    Invalid current portfolio schema should raise an execution error.
    """

    service = AdvancedAnalyticsService(
        portfolio_service=FakePortfolioService(
            (
                {
                    "Fund": "Fund A",
                    "Investment": 100.0,
                },
            )
        )
    )

    with pytest.raises(
        AdvancedAnalyticsExecutionError,
        match="Unable to calculate current portfolio totals",
    ):
        service.calculate()


# ============================================================
# Complete Analytics Tests
# ============================================================


def test_calculate_complete_analytics(
    fake_portfolio_service: FakePortfolioService,
    complete_service_input: AdvancedAnalyticsServiceInput,
) -> None:
    """
    Complete source data should produce all analytics metrics.
    """

    service = AdvancedAnalyticsService(
        portfolio_service=fake_portfolio_service
    )

    result = service.calculate(
        complete_service_input
    )

    assert result.status == "complete"
    assert result.portfolio_totals is not None
    assert result.adapter_result is not None
    assert result.analytics is not None

    assert result.analytics.status == "complete"
    assert result.analytics.requested_metric_count == 7
    assert result.analytics.successful_metric_count == 7
    assert result.analytics.failed_metric_count == 0

    assert result.analytics.cagr is not None
    assert result.analytics.xirr is not None
    assert result.analytics.volatility is not None
    assert result.analytics.drawdown is not None
    assert result.analytics.risk_metrics is not None
    assert result.analytics.benchmark is not None
    assert result.analytics.rolling_returns is not None

    assert result.failures == ()
    assert len(result.available_metrics) == 7
    assert result.unavailable_metrics == ()


def test_complete_result_preserves_benchmark_name(
    fake_portfolio_service: FakePortfolioService,
    complete_service_input: AdvancedAnalyticsServiceInput,
) -> None:
    """
    Benchmark metadata should flow through the complete service.
    """

    result = AdvancedAnalyticsService(
        portfolio_service=fake_portfolio_service
    ).calculate(
        complete_service_input
    )

    assert result.analytics is not None
    assert result.analytics.benchmark is not None

    assert (
        result.analytics.benchmark.benchmark_name
        == "Nifty 50 TRI"
    )


# ============================================================
# Automatic XIRR Terminal Value Tests
# ============================================================


def test_service_uses_current_portfolio_value_for_xirr(
    fake_portfolio_service: FakePortfolioService,
    cash_flow_history: tuple[dict[str, object], ...],
) -> None:
    """
    Current portfolio value should be automatically appended for XIRR.
    """

    service = AdvancedAnalyticsService(
        portfolio_service=fake_portfolio_service
    )

    result = service.calculate(
        AdvancedAnalyticsServiceInput(
            cash_flow_history=cash_flow_history,
            current_value=None,
            valuation_date=None,
            use_current_portfolio_value_for_xirr=True,
        )
    )

    assert result.adapter_result is not None

    xirr_input = (
        result.adapter_result.analytics_input.xirr
    )

    assert xirr_input is not None

    assert xirr_input.cash_flows[-1].amount == pytest.approx(
        170_000.0
    )


def test_explicit_current_value_overrides_portfolio_total(
    fake_portfolio_service: FakePortfolioService,
    cash_flow_history: tuple[dict[str, object], ...],
) -> None:
    """
    Explicit current_value should override automatic portfolio totals.
    """

    result = AdvancedAnalyticsService(
        portfolio_service=fake_portfolio_service
    ).calculate(
        AdvancedAnalyticsServiceInput(
            cash_flow_history=cash_flow_history,
            current_value=180_000.0,
            valuation_date=date(2024, 1, 1),
        )
    )

    assert result.adapter_result is not None

    xirr_input = (
        result.adapter_result.analytics_input.xirr
    )

    assert xirr_input is not None

    assert xirr_input.cash_flows[-1].amount == pytest.approx(
        180_000.0
    )


def test_service_does_not_append_current_value_when_disabled(
    fake_portfolio_service: FakePortfolioService,
) -> None:
    """
    Automatic terminal valuation can be disabled for complete cash-flow
    histories.
    """

    complete_cash_flows = (
        {
            "Date": date(2023, 1, 1),
            "Amount": -100_000.0,
        },
        {
            "Date": date(2024, 1, 1),
            "Amount": 120_000.0,
        },
    )

    result = AdvancedAnalyticsService(
        portfolio_service=fake_portfolio_service
    ).calculate(
        AdvancedAnalyticsServiceInput(
            cash_flow_history=complete_cash_flows,
            use_current_portfolio_value_for_xirr=False,
        )
    )

    assert result.adapter_result is not None

    xirr_input = (
        result.adapter_result.analytics_input.xirr
    )

    assert xirr_input is not None
    assert len(xirr_input.cash_flows) == 2


# ============================================================
# Partial and Unavailable Analytics Tests
# ============================================================


def test_calculate_with_only_portfolio_history(
    fake_portfolio_service: FakePortfolioService,
    portfolio_history: tuple[dict[str, object], ...],
) -> None:
    """
    Portfolio history alone should produce five metrics.
    """

    result = AdvancedAnalyticsService(
        portfolio_service=fake_portfolio_service
    ).calculate(
        AdvancedAnalyticsServiceInput(
            portfolio_history=portfolio_history,
            periods_per_year=12,
            rolling_window_size=2,
            rolling_annualise=False,
        )
    )

    assert result.status == "complete"
    assert result.analytics is not None

    assert result.analytics.requested_metric_count == 5
    assert result.analytics.successful_metric_count == 5

    assert set(result.available_metrics) == {
        "cagr",
        "volatility",
        "drawdown",
        "risk_metrics",
        "rolling_returns",
    }

    assert set(result.unavailable_metrics) == {
        "xirr",
        "benchmark",
    }


def test_calculate_with_only_benchmark_returns(
    fake_portfolio_service: FakePortfolioService,
    aligned_benchmark_returns: tuple[
        dict[str, object],
        ...,
    ],
) -> None:
    """
    Benchmark source alone should calculate benchmark-relative metrics.
    """

    result = AdvancedAnalyticsService(
        portfolio_service=fake_portfolio_service
    ).calculate(
        AdvancedAnalyticsServiceInput(
            aligned_benchmark_returns=(
                aligned_benchmark_returns
            ),
            periods_per_year=12,
            benchmark_name="Nifty 50 TRI",
        )
    )

    assert result.status == "complete"
    assert result.analytics is not None

    assert result.analytics.requested_metric_count == 1
    assert result.analytics.benchmark is not None


# ============================================================
# Failed Execution Tests
# ============================================================


def test_non_fail_fast_returns_failed_service_result(
    fake_portfolio_service: FakePortfolioService,
) -> None:
    """
    Adapter preparation failures should return a failed result when
    fail_fast is disabled.
    """

    invalid_history = (
        {
            "Date": date(2024, 1, 1),
            "Value": 100.0,
        },
        {
            "Date": date(2024, 2, 1),
            "Value": 110.0,
        },
    )

    result = AdvancedAnalyticsService(
        portfolio_service=fake_portfolio_service
    ).calculate(
        AdvancedAnalyticsServiceInput(
            portfolio_history=invalid_history,
            rolling_window_size=1,
            fail_fast=False,
        )
    )

    assert result.status == "failed"
    assert result.portfolio_totals is not None
    assert result.adapter_result is None
    assert result.analytics is None

    assert len(result.failures) == 1

    assert (
        result.failures[0].stage
        == "analytics_execution"
    )

    assert "At least three dated values" in (
        result.failures[0].message
    )


def test_fail_fast_raises_execution_error(
    fake_portfolio_service: FakePortfolioService,
) -> None:
    """
    Adapter preparation failures should raise when fail_fast is enabled.
    """

    invalid_history = (
        {
            "Date": date(2024, 1, 1),
            "Value": 100.0,
        },
        {
            "Date": date(2024, 2, 1),
            "Value": 110.0,
        },
    )

    service = AdvancedAnalyticsService(
        portfolio_service=fake_portfolio_service
    )

    with pytest.raises(
        AdvancedAnalyticsExecutionError,
        match="Advanced analytics execution failed",
    ):
        service.calculate(
            AdvancedAnalyticsServiceInput(
                portfolio_history=invalid_history,
                rolling_window_size=1,
                fail_fast=True,
            )
        )


def test_fail_fast_execution_error_preserves_cause(
    fake_portfolio_service: FakePortfolioService,
) -> None:
    """
    Execution error should preserve the original adapter exception.
    """

    invalid_history = (
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
        AdvancedAnalyticsExecutionError,
    ) as exc_info:
        AdvancedAnalyticsService(
            portfolio_service=fake_portfolio_service
        ).calculate(
            AdvancedAnalyticsServiceInput(
                portfolio_history=invalid_history,
                rolling_window_size=1,
                fail_fast=True,
            )
        )

    assert exc_info.value.__cause__ is not None


# ============================================================
# Custom Column Tests
# ============================================================


def test_service_supports_custom_portfolio_columns() -> None:
    """
    Alternate current portfolio column names should be supported.
    """

    portfolio = (
        {
            "Scheme": "Fund A",
            "Invested": 100.0,
            "Market": 120.0,
        },
        {
            "Scheme": "Fund B",
            "Invested": 50.0,
            "Market": 55.0,
        },
    )

    result = AdvancedAnalyticsService(
        portfolio_service=FakePortfolioService(
            portfolio
        )
    ).calculate(
        AdvancedAnalyticsServiceInput(
            investment_column="Invested",
            current_value_column="Market",
        )
    )

    assert result.portfolio_totals is not None
    assert result.portfolio_totals.total_investment == pytest.approx(
        150.0
    )

    assert result.portfolio_totals.total_current_value == pytest.approx(
        175.0
    )


def test_service_supports_custom_history_columns(
    fake_portfolio_service: FakePortfolioService,
) -> None:
    """
    Alternate historical value columns should be supported.
    """

    history = (
        {
            "Valuation Date": date(2024, 1, 1),
            "Portfolio NAV": 100.0,
        },
        {
            "Valuation Date": date(2024, 2, 1),
            "Portfolio NAV": 105.0,
        },
        {
            "Valuation Date": date(2024, 3, 1),
            "Portfolio NAV": 110.0,
        },
        {
            "Valuation Date": date(2024, 4, 1),
            "Portfolio NAV": 115.0,
        },
    )

    result = AdvancedAnalyticsService(
        portfolio_service=fake_portfolio_service
    ).calculate(
        AdvancedAnalyticsServiceInput(
            portfolio_history=history,
            history_date_column="Valuation Date",
            history_value_column="Portfolio NAV",
            periods_per_year=12,
            rolling_window_size=1,
            rolling_annualise=False,
        )
    )

    assert result.analytics is not None
    assert result.analytics.cagr is not None
    assert result.analytics.drawdown is not None


def test_service_supports_custom_cash_flow_columns(
    fake_portfolio_service: FakePortfolioService,
) -> None:
    """
    Alternate cash-flow column names should be supported.
    """

    cash_flows = (
        {
            "Transaction Date": date(2023, 1, 1),
            "Cash": -100_000.0,
        },
        {
            "Transaction Date": date(2023, 6, 1),
            "Cash": -50_000.0,
        },
    )

    result = AdvancedAnalyticsService(
        portfolio_service=fake_portfolio_service
    ).calculate(
        AdvancedAnalyticsServiceInput(
            cash_flow_history=cash_flows,
            cash_flow_date_column="Transaction Date",
            cash_flow_amount_column="Cash",
            current_value=180_000.0,
            valuation_date=date(2024, 1, 1),
        )
    )

    assert result.analytics is not None
    assert result.analytics.xirr is not None


def test_service_supports_custom_benchmark_columns(
    fake_portfolio_service: FakePortfolioService,
) -> None:
    """
    Alternate benchmark return columns should be supported.
    """

    records = (
        {
            "Portfolio": 0.02,
            "Index": 0.018,
        },
        {
            "Portfolio": -0.01,
            "Index": -0.012,
        },
        {
            "Portfolio": 0.015,
            "Index": 0.012,
        },
    )

    result = AdvancedAnalyticsService(
        portfolio_service=fake_portfolio_service
    ).calculate(
        AdvancedAnalyticsServiceInput(
            aligned_benchmark_returns=records,
            portfolio_return_column="Portfolio",
            benchmark_return_column="Index",
            periods_per_year=12,
        )
    )

    assert result.analytics is not None
    assert result.analytics.benchmark is not None


# ============================================================
# Functional Convenience API Tests
# ============================================================


def test_calculate_advanced_portfolio_analytics_function(
    fake_portfolio_service: FakePortfolioService,
    portfolio_history: tuple[dict[str, object], ...],
) -> None:
    """
    Functional wrapper should return the same service result.
    """

    result = calculate_advanced_portfolio_analytics(
        AdvancedAnalyticsServiceInput(
            portfolio_history=portfolio_history,
            periods_per_year=12,
            rolling_window_size=2,
            rolling_annualise=False,
        ),
        portfolio_service=fake_portfolio_service,
    )

    assert isinstance(
        result,
        AdvancedAnalyticsServiceResult,
    )

    assert result.analytics is not None
    assert result.analytics.cagr is not None


def test_functional_api_without_input(
    fake_portfolio_service: FakePortfolioService,
) -> None:
    """
    Functional wrapper should support default input.
    """

    result = calculate_advanced_portfolio_analytics(
        portfolio_service=fake_portfolio_service
    )

    assert result.status == "unavailable"
    assert result.portfolio_totals is not None


# ============================================================
# Result Utility Tests
# ============================================================


def test_has_advanced_analytics_true(
    fake_portfolio_service: FakePortfolioService,
    portfolio_history: tuple[dict[str, object], ...],
) -> None:
    """
    Utility should return True when metrics were calculated.
    """

    result = AdvancedAnalyticsService(
        portfolio_service=fake_portfolio_service
    ).calculate(
        AdvancedAnalyticsServiceInput(
            portfolio_history=portfolio_history,
            periods_per_year=12,
            rolling_window_size=2,
            rolling_annualise=False,
        )
    )

    assert has_advanced_analytics(result) is True


def test_has_advanced_analytics_false(
    fake_portfolio_service: FakePortfolioService,
) -> None:
    """
    Utility should return False when no advanced metric succeeded.
    """

    result = AdvancedAnalyticsService(
        portfolio_service=fake_portfolio_service
    ).calculate()

    assert has_advanced_analytics(result) is False


def test_has_portfolio_totals_true(
    fake_portfolio_service: FakePortfolioService,
) -> None:
    """
    Portfolio totals should be available after successful retrieval.
    """

    result = AdvancedAnalyticsService(
        portfolio_service=fake_portfolio_service
    ).calculate()

    assert has_portfolio_totals(result) is True


@pytest.mark.parametrize(
    "utility",
    [
        has_advanced_analytics,
        has_portfolio_totals,
        get_service_failure_messages,
    ],
)
def test_result_utilities_reject_wrong_type(
    utility: object,
) -> None:
    """
    Result utilities should reject unsupported result objects.
    """

    with pytest.raises(
        TypeError,
        match="AdvancedAnalyticsServiceResult",
    ):
        utility({})  # type: ignore[operator]


def test_get_service_failure_messages() -> None:
    """
    Failure utility should return messages in stored order.
    """

    result = AdvancedAnalyticsServiceResult(
        status="failed",
        portfolio=(),
        portfolio_totals=None,
        adapter_result=None,
        analytics=None,
        available_metrics=(),
        unavailable_metrics=(),
        failures=(
            AdvancedAnalyticsServiceFailure(
                stage="portfolio",
                error_type="ValueError",
                message="First failure.",
            ),
            AdvancedAnalyticsServiceFailure(
                stage="analytics",
                error_type="RuntimeError",
                message="Second failure.",
            ),
        ),
    )

    assert get_service_failure_messages(result) == (
        "First failure.",
        "Second failure.",
    )


def test_get_service_failure_messages_empty(
    fake_portfolio_service: FakePortfolioService,
) -> None:
    """
    Successful service results should expose no failure messages.
    """

    result = AdvancedAnalyticsService(
        portfolio_service=fake_portfolio_service
    ).calculate()

    assert get_service_failure_messages(result) == ()


# ============================================================
# Dataclass Immutability Tests
# ============================================================


def test_service_input_is_immutable() -> None:
    """
    AdvancedAnalyticsServiceInput should be immutable.
    """

    input_data = AdvancedAnalyticsServiceInput()

    with pytest.raises(FrozenInstanceError):
        input_data.fail_fast = True  # type: ignore[misc]


def test_service_failure_is_immutable() -> None:
    """
    AdvancedAnalyticsServiceFailure should be immutable.
    """

    failure = AdvancedAnalyticsServiceFailure(
        stage="analytics",
        error_type="ValueError",
        message="Example failure.",
    )

    with pytest.raises(FrozenInstanceError):
        failure.message = "Changed."  # type: ignore[misc]


def test_service_result_is_immutable() -> None:
    """
    AdvancedAnalyticsServiceResult should be immutable.
    """

    result = AdvancedAnalyticsServiceResult(
        status="unavailable",
        portfolio=(),
        portfolio_totals=None,
        adapter_result=None,
        analytics=None,
        available_metrics=(),
        unavailable_metrics=(),
        failures=(),
    )

    with pytest.raises(FrozenInstanceError):
        result.status = "complete"  # type: ignore[misc]


# ============================================================
# Result Consistency Tests
# ============================================================


def test_available_metrics_match_adapter(
    fake_portfolio_service: FakePortfolioService,
    complete_service_input: AdvancedAnalyticsServiceInput,
) -> None:
    """
    Service metric availability should match adapter output.
    """

    result = AdvancedAnalyticsService(
        portfolio_service=fake_portfolio_service
    ).calculate(
        complete_service_input
    )

    assert result.adapter_result is not None

    assert result.available_metrics == (
        result.adapter_result.available_metrics
    )

    assert result.unavailable_metrics == (
        result.adapter_result.unavailable_metrics
    )


def test_complete_service_status_matches_analytics(
    fake_portfolio_service: FakePortfolioService,
    complete_service_input: AdvancedAnalyticsServiceInput,
) -> None:
    """
    Service status should match complete analytics status.
    """

    result = AdvancedAnalyticsService(
        portfolio_service=fake_portfolio_service
    ).calculate(
        complete_service_input
    )

    assert result.analytics is not None
    assert result.analytics.status == "complete"
    assert result.status == "complete"


def test_unavailable_service_status_matches_analytics(
    fake_portfolio_service: FakePortfolioService,
) -> None:
    """
    Service should be unavailable when no advanced metric is requested.
    """

    result = AdvancedAnalyticsService(
        portfolio_service=fake_portfolio_service
    ).calculate()

    assert result.analytics is not None
    assert result.analytics.status == "unavailable"
    assert result.status == "unavailable"


def test_portfolio_total_return_consistency(
    fake_portfolio_service: FakePortfolioService,
) -> None:
    """
    Portfolio percentage return should equal decimal return times 100.
    """

    result = AdvancedAnalyticsService(
        portfolio_service=fake_portfolio_service
    ).calculate()

    assert result.portfolio_totals is not None

    assert (
        result.portfolio_totals.total_return_percent
        == pytest.approx(
            result.portfolio_totals.total_return_decimal
            * 100.0
        )
    )