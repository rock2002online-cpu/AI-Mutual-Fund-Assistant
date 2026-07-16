"""
Tests for dashboard.components.analytics.advanced_kpis.

These tests validate:

- Advanced KPI presentation-model construction
- Percentage and ratio formatting
- Complete analytics rendering
- Partial analytics rendering
- Missing metric handling
- Unavailable analytics handling
- Status icons and semantic classifications
- Streamlit metric rendering
- Component status messages
- Compatibility alias behaviour
- Defensive validation
- Immutable dataclasses
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from dashboard.components.analytics.advanced_kpis import (
    AdvancedKPI,
    build_advanced_kpis,
    render_advanced_kpis,
    show_advanced_kpis,
)
from services.advanced_analytics_service import (
    AdvancedAnalyticsServiceFailure,
    AdvancedAnalyticsServiceResult,
)
from services.analytics.advanced_analytics import (
    AdvancedAnalyticsResult,
    AnalyticsFailure,
)
from services.analytics.benchmark import BenchmarkResult
from services.analytics.cagr import CAGRResult
from services.analytics.drawdown import (
    DrawdownPoint,
    DrawdownResult,
)
from services.analytics.risk_metrics import (
    RiskMetricsResult,
)
from services.analytics.volatility import (
    VolatilityResult,
)
from services.analytics.xirr import XIRRResult


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def cagr_result() -> CAGRResult:
    """
    Return a representative CAGR result.
    """

    return CAGRResult(
        initial_value=100_000.0,
        final_value=150_000.0,
        years=3.0,
        cagr_decimal=0.144714,
        cagr_percent=14.4714,
        absolute_gain=50_000.0,
        total_return_percent=50.0,
    )


@pytest.fixture
def xirr_result() -> XIRRResult:
    """
    Return a representative XIRR result.
    """

    return XIRRResult(
        annual_return_decimal=0.182345,
        annual_return_percent=18.2345,
        iterations=7,
        converged=True,
        solver="newton_raphson",
    )


@pytest.fixture
def volatility_result() -> VolatilityResult:
    """
    Return a representative volatility result.
    """

    return VolatilityResult(
        observation_count=12,
        periods_per_year=12,
        periodic_volatility_decimal=0.025,
        periodic_volatility_percent=2.5,
        annualised_volatility_decimal=0.086603,
        annualised_volatility_percent=8.6603,
        mean_periodic_return_decimal=0.012,
        mean_periodic_return_percent=1.2,
        minimum_return_decimal=-0.04,
        maximum_return_decimal=0.05,
        risk_level="low",
    )


@pytest.fixture
def drawdown_result() -> DrawdownResult:
    """
    Return a representative recovered drawdown result.
    """

    drawdown_series = (
        DrawdownPoint(
            observation_date=date(2024, 1, 1),
            value=100.0,
            running_peak=100.0,
            drawdown_decimal=0.0,
            drawdown_percent=0.0,
        ),
        DrawdownPoint(
            observation_date=date(2024, 2, 1),
            value=120.0,
            running_peak=120.0,
            drawdown_decimal=0.0,
            drawdown_percent=0.0,
        ),
        DrawdownPoint(
            observation_date=date(2024, 3, 1),
            value=90.0,
            running_peak=120.0,
            drawdown_decimal=-0.25,
            drawdown_percent=-25.0,
        ),
        DrawdownPoint(
            observation_date=date(2024, 4, 1),
            value=125.0,
            running_peak=125.0,
            drawdown_decimal=0.0,
            drawdown_percent=0.0,
        ),
    )

    return DrawdownResult(
        observation_count=4,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 4, 1),
        starting_value=100.0,
        ending_value=125.0,
        current_peak_value=125.0,
        current_peak_date=date(2024, 4, 1),
        current_drawdown_decimal=0.0,
        current_drawdown_percent=0.0,
        maximum_drawdown_decimal=-0.25,
        maximum_drawdown_percent=-25.0,
        maximum_drawdown_peak_value=120.0,
        maximum_drawdown_peak_date=date(2024, 2, 1),
        maximum_drawdown_trough_value=90.0,
        maximum_drawdown_trough_date=date(2024, 3, 1),
        maximum_drawdown_duration_days=29,
        recovery_date=date(2024, 4, 1),
        recovery_duration_days=31,
        underwater_duration_days=60,
        recovered=True,
        risk_level="high",
        drawdown_series=drawdown_series,
    )


@pytest.fixture
def risk_metrics_result() -> RiskMetricsResult:
    """
    Return representative risk-adjusted metrics.
    """

    return RiskMetricsResult(
        observation_count=12,
        periods_per_year=12,
        mean_periodic_return_decimal=0.012,
        mean_periodic_return_percent=1.2,
        annualised_return_decimal=0.144,
        annualised_return_percent=14.4,
        periodic_volatility_decimal=0.025,
        periodic_volatility_percent=2.5,
        annualised_volatility_decimal=0.086603,
        annualised_volatility_percent=8.6603,
        annual_risk_free_rate_decimal=0.06,
        annual_risk_free_rate_percent=6.0,
        annual_minimum_acceptable_return_decimal=0.04,
        annual_minimum_acceptable_return_percent=4.0,
        annual_excess_return_decimal=0.084,
        annual_excess_return_percent=8.4,
        downside_deviation_decimal=0.04,
        downside_deviation_percent=4.0,
        sharpe_ratio=0.96995,
        sortino_ratio=2.10,
        positive_return_count=8,
        negative_return_count=4,
        zero_return_count=0,
        positive_return_frequency=8 / 12,
        negative_return_frequency=4 / 12,
        best_period_return_decimal=0.05,
        worst_period_return_decimal=-0.04,
        sharpe_rating="acceptable",
        sortino_rating="excellent",
    )


@pytest.fixture
def benchmark_result() -> BenchmarkResult:
    """
    Return representative benchmark-relative metrics.
    """

    return BenchmarkResult(
        observation_count=12,
        periods_per_year=12,
        benchmark_name="Nifty 50 TRI",
        mean_portfolio_return_decimal=0.012,
        mean_portfolio_return_percent=1.2,
        mean_benchmark_return_decimal=0.010,
        mean_benchmark_return_percent=1.0,
        annualised_portfolio_return_decimal=0.144,
        annualised_portfolio_return_percent=14.4,
        annualised_benchmark_return_decimal=0.12,
        annualised_benchmark_return_percent=12.0,
        annualised_excess_return_decimal=0.024,
        annualised_excess_return_percent=2.4,
        tracking_error_decimal=0.03,
        tracking_error_percent=3.0,
        information_ratio=0.80,
        beta=0.95,
        alpha_decimal=0.018,
        alpha_percent=1.8,
        correlation=0.92,
        r_squared=0.8464,
        upside_capture_ratio=105.0,
        downside_capture_ratio=90.0,
        active_return_positive_count=8,
        active_return_negative_count=4,
        active_return_zero_count=0,
        active_return_positive_frequency=8 / 12,
        active_return_negative_frequency=4 / 12,
        best_active_return_decimal=0.02,
        worst_active_return_decimal=-0.01,
        rating="outperforming",
    )


@pytest.fixture
def complete_analytics_result(
    cagr_result: CAGRResult,
    xirr_result: XIRRResult,
    volatility_result: VolatilityResult,
    drawdown_result: DrawdownResult,
    risk_metrics_result: RiskMetricsResult,
    benchmark_result: BenchmarkResult,
) -> AdvancedAnalyticsResult:
    """
    Return a complete advanced analytics result.
    """

    return AdvancedAnalyticsResult(
        status="complete",
        requested_metric_count=6,
        successful_metric_count=6,
        failed_metric_count=0,
        cagr=cagr_result,
        xirr=xirr_result,
        volatility=volatility_result,
        drawdown=drawdown_result,
        risk_metrics=risk_metrics_result,
        benchmark=benchmark_result,
        rolling_returns=None,
        failures=(),
    )


@pytest.fixture
def complete_service_result(
    complete_analytics_result: AdvancedAnalyticsResult,
) -> AdvancedAnalyticsServiceResult:
    """
    Return a complete service result.
    """

    return AdvancedAnalyticsServiceResult(
        status="complete",
        portfolio=(),
        portfolio_totals=None,
        adapter_result=None,
        analytics=complete_analytics_result,
        available_metrics=(
            "cagr",
            "xirr",
            "volatility",
            "drawdown",
            "risk_metrics",
            "benchmark",
        ),
        unavailable_metrics=("rolling_returns",),
        failures=(),
    )


@pytest.fixture
def unavailable_service_result() -> AdvancedAnalyticsServiceResult:
    """
    Return a service result without analytics.
    """

    return AdvancedAnalyticsServiceResult(
        status="unavailable",
        portfolio=(),
        portfolio_totals=None,
        adapter_result=None,
        analytics=None,
        available_metrics=(),
        unavailable_metrics=(
            "cagr",
            "xirr",
            "volatility",
            "drawdown",
            "risk_metrics",
            "benchmark",
            "rolling_returns",
        ),
        failures=(),
    )


# ============================================================
# AdvancedKPI Dataclass Tests
# ============================================================


def test_advanced_kpi_creation() -> None:
    """
    AdvancedKPI should preserve presentation values.
    """

    kpi = AdvancedKPI(
        label="Portfolio CAGR",
        value="14.47%",
        delta="Annualised portfolio growth",
        help_text="Compound annual growth rate.",
        status="positive",
    )

    assert kpi.label == "Portfolio CAGR"
    assert kpi.value == "14.47%"
    assert kpi.delta == "Annualised portfolio growth"
    assert kpi.help_text == "Compound annual growth rate."
    assert kpi.status == "positive"


def test_advanced_kpi_default_status() -> None:
    """
    Default KPI status should be neutral.
    """

    kpi = AdvancedKPI(
        label="Example",
        value="10.00",
    )

    assert kpi.status == "neutral"
    assert kpi.delta is None
    assert kpi.help_text is None


def test_advanced_kpi_is_immutable() -> None:
    """
    AdvancedKPI should be immutable.
    """

    kpi = AdvancedKPI(
        label="Portfolio CAGR",
        value="14.47%",
    )

    with pytest.raises(FrozenInstanceError):
        kpi.value = "20.00%"  # type: ignore[misc]


# ============================================================
# Complete KPI Construction Tests
# ============================================================


def test_build_advanced_kpis_returns_eight_cards(
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Complete analytics should produce eight KPI cards.
    """

    result = build_advanced_kpis(
        complete_service_result
    )

    assert len(result) == 8

    assert tuple(
        kpi.label
        for kpi in result
    ) == (
        "Portfolio CAGR",
        "Portfolio XIRR",
        "Annualised Volatility",
        "Maximum Drawdown",
        "Sharpe Ratio",
        "Sortino Ratio",
        "Benchmark Excess Return",
        "Information Ratio",
    )


def test_build_cagr_kpi(
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    CAGR KPI should be formatted as a percentage.
    """

    kpis = build_advanced_kpis(
        complete_service_result
    )

    cagr = kpis[0]

    assert cagr.label == "Portfolio CAGR"
    assert cagr.value == "14.47%"
    assert cagr.delta == "Annualised portfolio growth"
    assert cagr.status == "positive"
    assert cagr.help_text is not None


def test_build_xirr_kpi(
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    XIRR KPI should display the money-weighted return.
    """

    xirr = build_advanced_kpis(
        complete_service_result
    )[1]

    assert xirr.label == "Portfolio XIRR"
    assert xirr.value == "18.23%"
    assert xirr.delta == "Money-weighted return"
    assert xirr.status == "positive"


def test_build_volatility_kpi(
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Volatility KPI should display annualised volatility and risk level.
    """

    volatility = build_advanced_kpis(
        complete_service_result
    )[2]

    assert volatility.label == "Annualised Volatility"
    assert volatility.value == "8.66%"
    assert volatility.delta == "Low risk"
    assert volatility.status == "neutral"


def test_build_drawdown_kpi(
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Drawdown KPI should display decline and underwater duration.
    """

    drawdown = build_advanced_kpis(
        complete_service_result
    )[3]

    assert drawdown.label == "Maximum Drawdown"
    assert drawdown.value == "-25.00%"
    assert drawdown.delta == "Underwater: 60 days"
    assert drawdown.status == "negative"


def test_build_sharpe_kpi(
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Sharpe KPI should display ratio and rating.
    """

    sharpe = build_advanced_kpis(
        complete_service_result
    )[4]

    assert sharpe.label == "Sharpe Ratio"
    assert sharpe.value == "0.97"
    assert sharpe.delta == "Acceptable"
    assert sharpe.status == "positive"


def test_build_sortino_kpi(
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Sortino KPI should display ratio and rating.
    """

    sortino = build_advanced_kpis(
        complete_service_result
    )[5]

    assert sortino.label == "Sortino Ratio"
    assert sortino.value == "2.10"
    assert sortino.delta == "Excellent"
    assert sortino.status == "positive"


def test_build_benchmark_excess_return_kpi(
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Benchmark KPI should include rating and benchmark name.
    """

    benchmark = build_advanced_kpis(
        complete_service_result
    )[6]

    assert benchmark.label == "Benchmark Excess Return"
    assert benchmark.value == "2.40%"

    assert benchmark.delta == (
        "Outperforming vs Nifty 50 TRI"
    )

    assert benchmark.status == "positive"


def test_build_information_ratio_kpi(
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Information ratio should include benchmark context.
    """

    information_ratio = build_advanced_kpis(
        complete_service_result
    )[7]

    assert information_ratio.label == "Information Ratio"
    assert information_ratio.value == "0.80"

    assert information_ratio.delta == (
        "Relative to Nifty 50 TRI"
    )

    assert information_ratio.status == "positive"


# ============================================================
# Negative and Neutral KPI Tests
# ============================================================


def test_negative_cagr_is_classified_negative(
    complete_analytics_result: AdvancedAnalyticsResult,
) -> None:
    """
    Negative CAGR should produce negative presentation status.
    """

    negative_cagr = CAGRResult(
        initial_value=100.0,
        final_value=80.0,
        years=2.0,
        cagr_decimal=-0.105573,
        cagr_percent=-10.5573,
        absolute_gain=-20.0,
        total_return_percent=-20.0,
    )

    analytics = AdvancedAnalyticsResult(
        status="complete",
        requested_metric_count=1,
        successful_metric_count=1,
        failed_metric_count=0,
        cagr=negative_cagr,
        xirr=None,
        volatility=None,
        drawdown=None,
        risk_metrics=None,
        benchmark=None,
        rolling_returns=None,
        failures=(),
    )

    service_result = AdvancedAnalyticsServiceResult(
        status="complete",
        portfolio=(),
        portfolio_totals=None,
        adapter_result=None,
        analytics=analytics,
        available_metrics=("cagr",),
        unavailable_metrics=(),
        failures=(),
    )

    cagr = build_advanced_kpis(
        service_result
    )[0]

    assert cagr.value == "-10.56%"
    assert cagr.status == "negative"


def test_zero_xirr_is_classified_neutral() -> None:
    """
    A zero XIRR should produce neutral status.
    """

    analytics = AdvancedAnalyticsResult(
        status="complete",
        requested_metric_count=1,
        successful_metric_count=1,
        failed_metric_count=0,
        cagr=None,
        xirr=XIRRResult(
            annual_return_decimal=0.0,
            annual_return_percent=0.0,
            iterations=1,
            converged=True,
            solver="newton_raphson",
        ),
        volatility=None,
        drawdown=None,
        risk_metrics=None,
        benchmark=None,
        rolling_returns=None,
        failures=(),
    )

    service_result = AdvancedAnalyticsServiceResult(
        status="complete",
        portfolio=(),
        portfolio_totals=None,
        adapter_result=None,
        analytics=analytics,
        available_metrics=("xirr",),
        unavailable_metrics=(),
        failures=(),
    )

    xirr = build_advanced_kpis(
        service_result
    )[1]

    assert xirr.value == "0.00%"
    assert xirr.status == "neutral"


def test_zero_drawdown_is_neutral(
    drawdown_result: DrawdownResult,
) -> None:
    """
    A portfolio without drawdown should use neutral status.
    """

    zero_drawdown = DrawdownResult(
        observation_count=2,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 2, 1),
        starting_value=100.0,
        ending_value=110.0,
        current_peak_value=110.0,
        current_peak_date=date(2024, 2, 1),
        current_drawdown_decimal=0.0,
        current_drawdown_percent=0.0,
        maximum_drawdown_decimal=0.0,
        maximum_drawdown_percent=0.0,
        maximum_drawdown_peak_value=100.0,
        maximum_drawdown_peak_date=date(2024, 1, 1),
        maximum_drawdown_trough_value=100.0,
        maximum_drawdown_trough_date=date(2024, 1, 1),
        maximum_drawdown_duration_days=0,
        recovery_date=None,
        recovery_duration_days=None,
        underwater_duration_days=0,
        recovered=False,
        risk_level="very_low",
        drawdown_series=drawdown_result.drawdown_series[:2],
    )

    analytics = AdvancedAnalyticsResult(
        status="complete",
        requested_metric_count=1,
        successful_metric_count=1,
        failed_metric_count=0,
        cagr=None,
        xirr=None,
        volatility=None,
        drawdown=zero_drawdown,
        risk_metrics=None,
        benchmark=None,
        rolling_returns=None,
        failures=(),
    )

    service_result = AdvancedAnalyticsServiceResult(
        status="complete",
        portfolio=(),
        portfolio_totals=None,
        adapter_result=None,
        analytics=analytics,
        available_metrics=("drawdown",),
        unavailable_metrics=(),
        failures=(),
    )

    drawdown = build_advanced_kpis(
        service_result
    )[3]

    assert drawdown.value == "0.00%"
    assert drawdown.delta == "Underwater: 0 days"
    assert drawdown.status == "neutral"


def test_negative_sharpe_is_classified_negative(
    risk_metrics_result: RiskMetricsResult,
) -> None:
    """
    Negative Sharpe ratio should use negative status.
    """

    negative_risk_metrics = RiskMetricsResult(
        observation_count=risk_metrics_result.observation_count,
        periods_per_year=risk_metrics_result.periods_per_year,
        mean_periodic_return_decimal=-0.001,
        mean_periodic_return_percent=-0.1,
        annualised_return_decimal=-0.012,
        annualised_return_percent=-1.2,
        periodic_volatility_decimal=0.025,
        periodic_volatility_percent=2.5,
        annualised_volatility_decimal=0.086603,
        annualised_volatility_percent=8.6603,
        annual_risk_free_rate_decimal=0.06,
        annual_risk_free_rate_percent=6.0,
        annual_minimum_acceptable_return_decimal=0.04,
        annual_minimum_acceptable_return_percent=4.0,
        annual_excess_return_decimal=-0.072,
        annual_excess_return_percent=-7.2,
        downside_deviation_decimal=0.04,
        downside_deviation_percent=4.0,
        sharpe_ratio=-0.83,
        sortino_ratio=-1.80,
        positive_return_count=4,
        negative_return_count=8,
        zero_return_count=0,
        positive_return_frequency=4 / 12,
        negative_return_frequency=8 / 12,
        best_period_return_decimal=0.02,
        worst_period_return_decimal=-0.05,
        sharpe_rating="poor",
        sortino_rating="poor",
    )

    analytics = AdvancedAnalyticsResult(
        status="complete",
        requested_metric_count=1,
        successful_metric_count=1,
        failed_metric_count=0,
        cagr=None,
        xirr=None,
        volatility=None,
        drawdown=None,
        risk_metrics=negative_risk_metrics,
        benchmark=None,
        rolling_returns=None,
        failures=(),
    )

    service_result = AdvancedAnalyticsServiceResult(
        status="complete",
        portfolio=(),
        portfolio_totals=None,
        adapter_result=None,
        analytics=analytics,
        available_metrics=("risk_metrics",),
        unavailable_metrics=(),
        failures=(),
    )

    kpis = build_advanced_kpis(
        service_result
    )

    assert kpis[4].value == "-0.83"
    assert kpis[4].status == "negative"

    assert kpis[5].value == "-1.80"
    assert kpis[5].status == "negative"


# ============================================================
# Missing Metric Tests
# ============================================================


def test_missing_individual_metrics_show_na() -> None:
    """
    Missing metrics should display N/A without failing the component.
    """

    analytics = AdvancedAnalyticsResult(
        status="complete",
        requested_metric_count=0,
        successful_metric_count=0,
        failed_metric_count=0,
        cagr=None,
        xirr=None,
        volatility=None,
        drawdown=None,
        risk_metrics=None,
        benchmark=None,
        rolling_returns=None,
        failures=(),
    )

    service_result = AdvancedAnalyticsServiceResult(
        status="complete",
        portfolio=(),
        portfolio_totals=None,
        adapter_result=None,
        analytics=analytics,
        available_metrics=(),
        unavailable_metrics=(),
        failures=(),
    )

    result = build_advanced_kpis(
        service_result
    )

    assert len(result) == 8
    assert all(kpi.value == "N/A" for kpi in result)
    assert all(
        kpi.status == "unavailable"
        for kpi in result
    )


def test_missing_benchmark_name_uses_generic_delta(
    benchmark_result: BenchmarkResult,
) -> None:
    """
    Missing benchmark name should use generic information-ratio text.
    """

    benchmark_without_name = BenchmarkResult(
        observation_count=benchmark_result.observation_count,
        periods_per_year=benchmark_result.periods_per_year,
        benchmark_name=None,
        mean_portfolio_return_decimal=(
            benchmark_result.mean_portfolio_return_decimal
        ),
        mean_portfolio_return_percent=(
            benchmark_result.mean_portfolio_return_percent
        ),
        mean_benchmark_return_decimal=(
            benchmark_result.mean_benchmark_return_decimal
        ),
        mean_benchmark_return_percent=(
            benchmark_result.mean_benchmark_return_percent
        ),
        annualised_portfolio_return_decimal=(
            benchmark_result.annualised_portfolio_return_decimal
        ),
        annualised_portfolio_return_percent=(
            benchmark_result.annualised_portfolio_return_percent
        ),
        annualised_benchmark_return_decimal=(
            benchmark_result.annualised_benchmark_return_decimal
        ),
        annualised_benchmark_return_percent=(
            benchmark_result.annualised_benchmark_return_percent
        ),
        annualised_excess_return_decimal=(
            benchmark_result.annualised_excess_return_decimal
        ),
        annualised_excess_return_percent=(
            benchmark_result.annualised_excess_return_percent
        ),
        tracking_error_decimal=(
            benchmark_result.tracking_error_decimal
        ),
        tracking_error_percent=(
            benchmark_result.tracking_error_percent
        ),
        information_ratio=benchmark_result.information_ratio,
        beta=benchmark_result.beta,
        alpha_decimal=benchmark_result.alpha_decimal,
        alpha_percent=benchmark_result.alpha_percent,
        correlation=benchmark_result.correlation,
        r_squared=benchmark_result.r_squared,
        upside_capture_ratio=(
            benchmark_result.upside_capture_ratio
        ),
        downside_capture_ratio=(
            benchmark_result.downside_capture_ratio
        ),
        active_return_positive_count=(
            benchmark_result.active_return_positive_count
        ),
        active_return_negative_count=(
            benchmark_result.active_return_negative_count
        ),
        active_return_zero_count=(
            benchmark_result.active_return_zero_count
        ),
        active_return_positive_frequency=(
            benchmark_result.active_return_positive_frequency
        ),
        active_return_negative_frequency=(
            benchmark_result.active_return_negative_frequency
        ),
        best_active_return_decimal=(
            benchmark_result.best_active_return_decimal
        ),
        worst_active_return_decimal=(
            benchmark_result.worst_active_return_decimal
        ),
        rating=benchmark_result.rating,
    )

    analytics = AdvancedAnalyticsResult(
        status="complete",
        requested_metric_count=1,
        successful_metric_count=1,
        failed_metric_count=0,
        cagr=None,
        xirr=None,
        volatility=None,
        drawdown=None,
        risk_metrics=None,
        benchmark=benchmark_without_name,
        rolling_returns=None,
        failures=(),
    )

    service_result = AdvancedAnalyticsServiceResult(
        status="complete",
        portfolio=(),
        portfolio_totals=None,
        adapter_result=None,
        analytics=analytics,
        available_metrics=("benchmark",),
        unavailable_metrics=(),
        failures=(),
    )

    kpis = build_advanced_kpis(
        service_result
    )

    assert kpis[6].delta == "Outperforming"
    assert kpis[7].delta == "Risk-adjusted active return"


# ============================================================
# Unavailable Analytics Tests
# ============================================================


def test_build_kpis_without_analytics(
    unavailable_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Missing analytics object should produce stable unavailable cards.
    """

    result = build_advanced_kpis(
        unavailable_service_result
    )

    assert len(result) == 8
    assert all(kpi.value == "N/A" for kpi in result)

    assert result[0].delta == "Historical data unavailable"
    assert result[1].delta == "Cash-flow history unavailable"
    assert result[2].delta == "Return history unavailable"
    assert result[3].delta == "Valuation history unavailable"
    assert result[4].delta == "Risk metrics unavailable"
    assert result[5].delta == "Risk metrics unavailable"
    assert result[6].delta == "Benchmark data unavailable"
    assert result[7].delta == "Benchmark data unavailable"

    assert all(
        kpi.status == "unavailable"
        for kpi in result
    )


def test_build_kpis_rejects_wrong_result_type() -> None:
    """
    KPI construction should reject unsupported objects.
    """

    with pytest.raises(
        TypeError,
        match="AdvancedAnalyticsServiceResult",
    ):
        build_advanced_kpis(  # type: ignore[arg-type]
            {}
        )


# ============================================================
# Streamlit Rendering Tests
# ============================================================


@patch(
    "dashboard.components.analytics.advanced_kpis.st"
)
def test_render_advanced_kpis_complete(
    mock_st: MagicMock,
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Complete results should render two rows containing four cards each.
    """

    first_row = tuple(
        MagicMock()
        for _ in range(4)
    )

    second_row = tuple(
        MagicMock()
        for _ in range(4)
    )

    mock_st.columns.side_effect = (
        first_row,
        second_row,
    )

    render_advanced_kpis(
        complete_service_result
    )

    mock_st.subheader.assert_called_once_with(
        "Advanced Performance & Risk Metrics"
    )

    mock_st.caption.assert_called_once()

    assert mock_st.columns.call_count == 2

    mock_st.columns.assert_any_call(4)

    assert mock_st.metric.call_count == 8

    mock_st.warning.assert_not_called()
    mock_st.error.assert_not_called()
    mock_st.info.assert_not_called()


@patch(
    "dashboard.components.analytics.advanced_kpis.st"
)
def test_render_metrics_have_border(
    mock_st: MagicMock,
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Each KPI card should request Streamlit metric borders.
    """

    mock_st.columns.side_effect = (
        tuple(MagicMock() for _ in range(4)),
        tuple(MagicMock() for _ in range(4)),
    )

    render_advanced_kpis(
        complete_service_result
    )

    for call in mock_st.metric.call_args_list:
        assert call.kwargs["border"] is True
        assert call.kwargs["delta_color"] == "off"


@patch(
    "dashboard.components.analytics.advanced_kpis.st"
)
def test_render_complete_kpi_values(
    mock_st: MagicMock,
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Streamlit metric calls should contain formatted KPI values.
    """

    mock_st.columns.side_effect = (
        tuple(MagicMock() for _ in range(4)),
        tuple(MagicMock() for _ in range(4)),
    )

    render_advanced_kpis(
        complete_service_result
    )

    metric_values = tuple(
        call.kwargs["value"]
        for call in mock_st.metric.call_args_list
    )

    assert metric_values == (
        "14.47%",
        "18.23%",
        "8.66%",
        "-25.00%",
        "0.97",
        "2.10",
        "2.40%",
        "0.80",
    )


@patch(
    "dashboard.components.analytics.advanced_kpis.st"
)
def test_render_status_icons(
    mock_st: MagicMock,
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Metric deltas should include semantic status icons.
    """

    mock_st.columns.side_effect = (
        tuple(MagicMock() for _ in range(4)),
        tuple(MagicMock() for _ in range(4)),
    )

    render_advanced_kpis(
        complete_service_result
    )

    deltas = tuple(
        call.kwargs["delta"]
        for call in mock_st.metric.call_args_list
    )

    assert deltas[0].startswith("🟢")
    assert deltas[1].startswith("🟢")
    assert deltas[2].startswith("🟡")
    assert deltas[3].startswith("🔴")
    assert deltas[4].startswith("🟢")
    assert deltas[5].startswith("🟢")
    assert deltas[6].startswith("🟢")
    assert deltas[7].startswith("🟢")


@patch(
    "dashboard.components.analytics.advanced_kpis.st"
)
def test_render_partial_status_warning(
    mock_st: MagicMock,
    complete_analytics_result: AdvancedAnalyticsResult,
) -> None:
    """
    Partial service results should display a warning.
    """

    partial_result = AdvancedAnalyticsServiceResult(
        status="partial",
        portfolio=(),
        portfolio_totals=None,
        adapter_result=None,
        analytics=complete_analytics_result,
        available_metrics=("cagr",),
        unavailable_metrics=("benchmark",),
        failures=(),
    )

    mock_st.columns.side_effect = (
        tuple(MagicMock() for _ in range(4)),
        tuple(MagicMock() for _ in range(4)),
    )

    render_advanced_kpis(
        partial_result
    )

    mock_st.warning.assert_called_once()
    mock_st.error.assert_not_called()
    mock_st.info.assert_not_called()


@patch(
    "dashboard.components.analytics.advanced_kpis.st"
)
def test_render_failed_status_error(
    mock_st: MagicMock,
) -> None:
    """
    Failed service results should display an error.
    """

    failed_result = AdvancedAnalyticsServiceResult(
        status="failed",
        portfolio=(),
        portfolio_totals=None,
        adapter_result=None,
        analytics=None,
        available_metrics=(),
        unavailable_metrics=(),
        failures=(
            AdvancedAnalyticsServiceFailure(
                stage="analytics_execution",
                error_type="ValueError",
                message="Unable to prepare analytics.",
            ),
        ),
    )

    mock_st.columns.side_effect = (
        tuple(MagicMock() for _ in range(4)),
        tuple(MagicMock() for _ in range(4)),
    )

    render_advanced_kpis(
        failed_result
    )

    mock_st.error.assert_called_once()
    mock_st.warning.assert_not_called()
    mock_st.info.assert_not_called()


@patch(
    "dashboard.components.analytics.advanced_kpis.st"
)
def test_render_unavailable_status_info(
    mock_st: MagicMock,
    unavailable_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Unavailable results should display an informational message.
    """

    mock_st.columns.side_effect = (
        tuple(MagicMock() for _ in range(4)),
        tuple(MagicMock() for _ in range(4)),
    )

    render_advanced_kpis(
        unavailable_service_result
    )

    mock_st.info.assert_called_once()
    mock_st.warning.assert_not_called()
    mock_st.error.assert_not_called()


@patch(
    "dashboard.components.analytics.advanced_kpis.st"
)
def test_render_rejects_wrong_service_result_type(
    mock_st: MagicMock,
) -> None:
    """
    Renderer should reject unsupported service result objects.
    """

    with pytest.raises(
        TypeError,
        match="AdvancedAnalyticsServiceResult",
    ):
        render_advanced_kpis(  # type: ignore[arg-type]
            {}
        )

    mock_st.subheader.assert_not_called()
    mock_st.metric.assert_not_called()


@patch(
    "dashboard.components.analytics.advanced_kpis.render_advanced_kpis"
)
def test_show_advanced_kpis_alias(
    mock_render: MagicMock,
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Compatibility alias should delegate to the main renderer.
    """

    show_advanced_kpis(
        complete_service_result
    )

    mock_render.assert_called_once_with(
        complete_service_result
    )


# ============================================================
# Partial Metric Tests
# ============================================================


def test_partial_analytics_only_cagr(
    cagr_result: CAGRResult,
) -> None:
    """
    A result containing only CAGR should preserve one available KPI.
    """

    analytics = AdvancedAnalyticsResult(
        status="complete",
        requested_metric_count=1,
        successful_metric_count=1,
        failed_metric_count=0,
        cagr=cagr_result,
        xirr=None,
        volatility=None,
        drawdown=None,
        risk_metrics=None,
        benchmark=None,
        rolling_returns=None,
        failures=(),
    )

    service_result = AdvancedAnalyticsServiceResult(
        status="complete",
        portfolio=(),
        portfolio_totals=None,
        adapter_result=None,
        analytics=analytics,
        available_metrics=("cagr",),
        unavailable_metrics=(
            "xirr",
            "volatility",
            "drawdown",
            "risk_metrics",
            "benchmark",
        ),
        failures=(),
    )

    kpis = build_advanced_kpis(
        service_result
    )

    assert kpis[0].value == "14.47%"

    for kpi in kpis[1:]:
        assert kpi.value == "N/A"
        assert kpi.status == "unavailable"


def test_partial_analytics_failure_does_not_break_kpis(
    cagr_result: CAGRResult,
) -> None:
    """
    Captured metric failures should not prevent available KPI construction.
    """

    analytics = AdvancedAnalyticsResult(
        status="partial",
        requested_metric_count=2,
        successful_metric_count=1,
        failed_metric_count=1,
        cagr=cagr_result,
        xirr=None,
        volatility=None,
        drawdown=None,
        risk_metrics=None,
        benchmark=None,
        rolling_returns=None,
        failures=(
            AnalyticsFailure(
                metric="xirr",
                error_type="XIRRValidationError",
                message="Invalid cash flows.",
            ),
        ),
    )

    service_result = AdvancedAnalyticsServiceResult(
        status="partial",
        portfolio=(),
        portfolio_totals=None,
        adapter_result=None,
        analytics=analytics,
        available_metrics=("cagr",),
        unavailable_metrics=(),
        failures=(),
    )

    kpis = build_advanced_kpis(
        service_result
    )

    assert kpis[0].value == "14.47%"
    assert kpis[1].value == "N/A"
    assert kpis[1].status == "unavailable"


# ============================================================
# Formatting Edge-Case Tests
# ============================================================


def test_large_percentage_uses_thousands_separator() -> None:
    """
    Large percentage values should use grouped formatting.
    """

    analytics = AdvancedAnalyticsResult(
        status="complete",
        requested_metric_count=1,
        successful_metric_count=1,
        failed_metric_count=0,
        cagr=CAGRResult(
            initial_value=1.0,
            final_value=101.0,
            years=1.0,
            cagr_decimal=100.0,
            cagr_percent=10_000.0,
            absolute_gain=100.0,
            total_return_percent=10_000.0,
        ),
        xirr=None,
        volatility=None,
        drawdown=None,
        risk_metrics=None,
        benchmark=None,
        rolling_returns=None,
        failures=(),
    )

    service_result = AdvancedAnalyticsServiceResult(
        status="complete",
        portfolio=(),
        portfolio_totals=None,
        adapter_result=None,
        analytics=analytics,
        available_metrics=("cagr",),
        unavailable_metrics=(),
        failures=(),
    )

    assert build_advanced_kpis(
        service_result
    )[0].value == "10,000.00%"


def test_undefined_ratios_show_na(
    risk_metrics_result: RiskMetricsResult,
) -> None:
    """
    Undefined Sharpe and Sortino ratios should display N/A.
    """

    undefined_ratios = RiskMetricsResult(
        observation_count=risk_metrics_result.observation_count,
        periods_per_year=risk_metrics_result.periods_per_year,
        mean_periodic_return_decimal=(
            risk_metrics_result.mean_periodic_return_decimal
        ),
        mean_periodic_return_percent=(
            risk_metrics_result.mean_periodic_return_percent
        ),
        annualised_return_decimal=(
            risk_metrics_result.annualised_return_decimal
        ),
        annualised_return_percent=(
            risk_metrics_result.annualised_return_percent
        ),
        periodic_volatility_decimal=0.0,
        periodic_volatility_percent=0.0,
        annualised_volatility_decimal=0.0,
        annualised_volatility_percent=0.0,
        annual_risk_free_rate_decimal=(
            risk_metrics_result.annual_risk_free_rate_decimal
        ),
        annual_risk_free_rate_percent=(
            risk_metrics_result.annual_risk_free_rate_percent
        ),
        annual_minimum_acceptable_return_decimal=(
            risk_metrics_result
            .annual_minimum_acceptable_return_decimal
        ),
        annual_minimum_acceptable_return_percent=(
            risk_metrics_result
            .annual_minimum_acceptable_return_percent
        ),
        annual_excess_return_decimal=(
            risk_metrics_result.annual_excess_return_decimal
        ),
        annual_excess_return_percent=(
            risk_metrics_result.annual_excess_return_percent
        ),
        downside_deviation_decimal=0.0,
        downside_deviation_percent=0.0,
        sharpe_ratio=None,
        sortino_ratio=None,
        positive_return_count=(
            risk_metrics_result.positive_return_count
        ),
        negative_return_count=(
            risk_metrics_result.negative_return_count
        ),
        zero_return_count=(
            risk_metrics_result.zero_return_count
        ),
        positive_return_frequency=(
            risk_metrics_result.positive_return_frequency
        ),
        negative_return_frequency=(
            risk_metrics_result.negative_return_frequency
        ),
        best_period_return_decimal=(
            risk_metrics_result.best_period_return_decimal
        ),
        worst_period_return_decimal=(
            risk_metrics_result.worst_period_return_decimal
        ),
        sharpe_rating=None,
        sortino_rating=None,
    )

    analytics = AdvancedAnalyticsResult(
        status="complete",
        requested_metric_count=1,
        successful_metric_count=1,
        failed_metric_count=0,
        cagr=None,
        xirr=None,
        volatility=None,
        drawdown=None,
        risk_metrics=undefined_ratios,
        benchmark=None,
        rolling_returns=None,
        failures=(),
    )

    service_result = AdvancedAnalyticsServiceResult(
        status="complete",
        portfolio=(),
        portfolio_totals=None,
        adapter_result=None,
        analytics=analytics,
        available_metrics=("risk_metrics",),
        unavailable_metrics=(),
        failures=(),
    )

    kpis = build_advanced_kpis(
        service_result
    )

    assert kpis[4].value == "N/A"
    assert kpis[4].status == "unavailable"
    assert kpis[4].delta == "Risk metric unavailable"

    assert kpis[5].value == "N/A"
    assert kpis[5].status == "unavailable"
    assert kpis[5].delta == "Downside metric unavailable"


# ============================================================
# Result Stability Tests
# ============================================================


def test_build_advanced_kpis_returns_tuple(
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    KPI construction should return an immutable tuple.
    """

    result = build_advanced_kpis(
        complete_service_result
    )

    assert isinstance(result, tuple)


def test_kpi_order_is_stable(
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    KPI order should remain stable for predictable dashboard layout.
    """

    first_result = build_advanced_kpis(
        complete_service_result
    )

    second_result = build_advanced_kpis(
        complete_service_result
    )

    assert first_result == second_result