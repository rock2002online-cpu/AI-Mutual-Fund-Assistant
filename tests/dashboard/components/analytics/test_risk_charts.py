"""
Tests for dashboard.components.analytics.risk_charts.

These tests validate:

- Drawdown chart construction
- Rolling-return chart construction
- Benchmark comparison chart construction
- Active-return chart construction
- Return-frequency chart construction
- Empty-state figures
- Chart availability messages
- Stable Streamlit chart keys
- Streamlit rendering calls
- Partial, failed, and unavailable status messages
- Compatibility alias behaviour
- Defensive validation
- Immutable dataclasses
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date
from unittest.mock import MagicMock, patch

import plotly.graph_objects as go
import pytest

from dashboard.components.analytics.risk_charts import (
    ACTIVE_RETURNS_CHART_KEY,
    BENCHMARK_COMPARISON_CHART_KEY,
    DRAW_DOWN_CHART_KEY,
    RETURN_FREQUENCY_CHART_KEY,
    ROLLING_RETURNS_CHART_KEY,
    ChartMessage,
    build_active_return_chart,
    build_benchmark_comparison_chart,
    build_drawdown_chart,
    build_return_frequency_chart,
    build_rolling_returns_chart,
    get_risk_chart_messages,
    render_risk_charts,
    show_risk_charts,
)
from services.advanced_analytics_service import (
    AdvancedAnalyticsServiceFailure,
    AdvancedAnalyticsServiceResult,
)
from services.analytics.advanced_analytics import (
    AdvancedAnalyticsResult,
)
from services.analytics.benchmark import BenchmarkResult
from services.analytics.drawdown import (
    DrawdownPoint,
    DrawdownResult,
)
from services.analytics.risk_metrics import (
    RiskMetricsResult,
)
from services.analytics.rolling_returns import (
    RollingReturnPoint,
    RollingReturnsResult,
)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def drawdown_result() -> DrawdownResult:
    """
    Return a representative portfolio drawdown result.
    """

    series = (
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
            value=110.0,
            running_peak=120.0,
            drawdown_decimal=(110.0 / 120.0) - 1.0,
            drawdown_percent=((110.0 / 120.0) - 1.0) * 100.0,
        ),
        DrawdownPoint(
            observation_date=date(2024, 5, 1),
            value=125.0,
            running_peak=125.0,
            drawdown_decimal=0.0,
            drawdown_percent=0.0,
        ),
    )

    return DrawdownResult(
        observation_count=5,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 5, 1),
        starting_value=100.0,
        ending_value=125.0,
        current_peak_value=125.0,
        current_peak_date=date(2024, 5, 1),
        current_drawdown_decimal=0.0,
        current_drawdown_percent=0.0,
        maximum_drawdown_decimal=-0.25,
        maximum_drawdown_percent=-25.0,
        maximum_drawdown_peak_value=120.0,
        maximum_drawdown_peak_date=date(2024, 2, 1),
        maximum_drawdown_trough_value=90.0,
        maximum_drawdown_trough_date=date(2024, 3, 1),
        maximum_drawdown_duration_days=29,
        recovery_date=date(2024, 5, 1),
        recovery_duration_days=61,
        underwater_duration_days=90,
        recovered=True,
        risk_level="high",
        drawdown_series=series,
    )


@pytest.fixture
def rolling_returns_result() -> RollingReturnsResult:
    """
    Return representative non-annualised rolling returns.
    """

    rolling_returns = (
        RollingReturnPoint(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 1),
            start_value=100.0,
            end_value=110.0,
            duration_days=60,
            duration_years=60 / 365.25,
            total_return_decimal=0.10,
            total_return_percent=10.0,
            annualised_return_decimal=None,
            annualised_return_percent=None,
        ),
        RollingReturnPoint(
            start_date=date(2024, 2, 1),
            end_date=date(2024, 4, 1),
            start_value=105.0,
            end_value=108.0,
            duration_days=60,
            duration_years=60 / 365.25,
            total_return_decimal=(108.0 / 105.0) - 1.0,
            total_return_percent=((108.0 / 105.0) - 1.0) * 100.0,
            annualised_return_decimal=None,
            annualised_return_percent=None,
        ),
        RollingReturnPoint(
            start_date=date(2024, 3, 1),
            end_date=date(2024, 5, 1),
            start_value=110.0,
            end_value=115.0,
            duration_days=61,
            duration_years=61 / 365.25,
            total_return_decimal=(115.0 / 110.0) - 1.0,
            total_return_percent=((115.0 / 110.0) - 1.0) * 100.0,
            annualised_return_decimal=None,
            annualised_return_percent=None,
        ),
    )

    return RollingReturnsResult(
        observation_count=5,
        rolling_period_count=3,
        window_size=2,
        annualised=False,
        target_return_decimal=0.05,
        target_return_percent=5.0,
        average_return_decimal=0.059,
        average_return_percent=5.9,
        median_return_decimal=0.045,
        median_return_percent=4.5,
        best_return_decimal=0.10,
        best_return_percent=10.0,
        worst_return_decimal=(108.0 / 105.0) - 1.0,
        worst_return_percent=((108.0 / 105.0) - 1.0) * 100.0,
        best_period=rolling_returns[0],
        worst_period=rolling_returns[1],
        positive_period_count=3,
        negative_period_count=0,
        zero_period_count=0,
        positive_period_frequency=1.0,
        negative_period_frequency=0.0,
        target_achieved_count=1,
        target_achieved_frequency=1 / 3,
        rating="excellent",
        rolling_returns=rolling_returns,
    )


@pytest.fixture
def annualised_rolling_returns_result() -> RollingReturnsResult:
    """
    Return representative annualised rolling returns.
    """

    points = (
        RollingReturnPoint(
            start_date=date(2022, 1, 1),
            end_date=date(2023, 1, 1),
            start_value=100.0,
            end_value=110.0,
            duration_days=365,
            duration_years=365 / 365.25,
            total_return_decimal=0.10,
            total_return_percent=10.0,
            annualised_return_decimal=0.10007,
            annualised_return_percent=10.007,
        ),
        RollingReturnPoint(
            start_date=date(2023, 1, 1),
            end_date=date(2024, 1, 1),
            start_value=110.0,
            end_value=121.0,
            duration_days=365,
            duration_years=365 / 365.25,
            total_return_decimal=0.10,
            total_return_percent=10.0,
            annualised_return_decimal=0.10007,
            annualised_return_percent=10.007,
        ),
    )

    return RollingReturnsResult(
        observation_count=3,
        rolling_period_count=2,
        window_size=1,
        annualised=True,
        target_return_decimal=None,
        target_return_percent=None,
        average_return_decimal=0.10007,
        average_return_percent=10.007,
        median_return_decimal=0.10007,
        median_return_percent=10.007,
        best_return_decimal=0.10007,
        best_return_percent=10.007,
        worst_return_decimal=0.10007,
        worst_return_percent=10.007,
        best_period=points[0],
        worst_period=points[0],
        positive_period_count=2,
        negative_period_count=0,
        zero_period_count=0,
        positive_period_frequency=1.0,
        negative_period_frequency=0.0,
        target_achieved_count=None,
        target_achieved_frequency=None,
        rating="excellent",
        rolling_returns=points,
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
        active_return_negative_count=3,
        active_return_zero_count=1,
        active_return_positive_frequency=8 / 12,
        active_return_negative_frequency=3 / 12,
        best_active_return_decimal=0.02,
        worst_active_return_decimal=-0.01,
        rating="outperforming",
    )


@pytest.fixture
def risk_metrics_result() -> RiskMetricsResult:
    """
    Return representative portfolio risk metrics.
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
        negative_return_count=3,
        zero_return_count=1,
        positive_return_frequency=8 / 12,
        negative_return_frequency=3 / 12,
        best_period_return_decimal=0.05,
        worst_period_return_decimal=-0.04,
        sharpe_rating="acceptable",
        sortino_rating="excellent",
    )


@pytest.fixture
def complete_analytics_result(
    drawdown_result: DrawdownResult,
    rolling_returns_result: RollingReturnsResult,
    benchmark_result: BenchmarkResult,
    risk_metrics_result: RiskMetricsResult,
) -> AdvancedAnalyticsResult:
    """
    Return analytics containing every chart dependency.
    """

    return AdvancedAnalyticsResult(
        status="complete",
        requested_metric_count=4,
        successful_metric_count=4,
        failed_metric_count=0,
        cagr=None,
        xirr=None,
        volatility=None,
        drawdown=drawdown_result,
        risk_metrics=risk_metrics_result,
        benchmark=benchmark_result,
        rolling_returns=rolling_returns_result,
        failures=(),
    )


@pytest.fixture
def complete_service_result(
    complete_analytics_result: AdvancedAnalyticsResult,
) -> AdvancedAnalyticsServiceResult:
    """
    Return a complete chart service result.
    """

    return AdvancedAnalyticsServiceResult(
        status="complete",
        portfolio=(),
        portfolio_totals=None,
        adapter_result=None,
        analytics=complete_analytics_result,
        available_metrics=(
            "drawdown",
            "risk_metrics",
            "benchmark",
            "rolling_returns",
        ),
        unavailable_metrics=(),
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
            "drawdown",
            "risk_metrics",
            "benchmark",
            "rolling_returns",
        ),
        failures=(),
    )


# ============================================================
# ChartMessage Tests
# ============================================================


def test_chart_message_creation() -> None:
    """
    ChartMessage should preserve its presentation values.
    """

    message = ChartMessage(
        title="Portfolio Drawdown",
        message="History unavailable.",
    )

    assert message.title == "Portfolio Drawdown"
    assert message.message == "History unavailable."
    assert message.availability == "unavailable"


def test_chart_message_is_immutable() -> None:
    """
    ChartMessage should be immutable.
    """

    message = ChartMessage(
        title="Example",
        message="Unavailable.",
    )

    with pytest.raises(FrozenInstanceError):
        message.message = "Changed."  # type: ignore[misc]


# ============================================================
# Drawdown Chart Tests
# ============================================================


def test_build_drawdown_chart(
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Drawdown chart should contain a filled line trace.
    """

    figure = build_drawdown_chart(
        complete_service_result
    )

    assert isinstance(figure, go.Figure)
    assert len(figure.data) == 1

    trace = figure.data[0]

    assert isinstance(trace, go.Scatter)
    assert trace.name == "Drawdown"
    assert trace.mode == "lines"
    assert trace.fill == "tozeroy"

    assert tuple(trace.y) == pytest.approx(
        (
            0.0,
            0.0,
            -25.0,
            ((110.0 / 120.0) - 1.0) * 100.0,
            0.0,
        )
    )


def test_drawdown_chart_uses_dates(
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Drawdown chart x-axis should use observation dates.
    """

    figure = build_drawdown_chart(
        complete_service_result
    )

    assert tuple(figure.data[0].x) == (
        date(2024, 1, 1),
        date(2024, 2, 1),
        date(2024, 3, 1),
        date(2024, 4, 1),
        date(2024, 5, 1),
    )


def test_drawdown_chart_contains_reference_lines(
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Drawdown chart should include peak and maximum-drawdown lines.
    """

    figure = build_drawdown_chart(
        complete_service_result
    )

    assert len(figure.layout.shapes) == 2

    y_values = tuple(
        shape.y0
        for shape in figure.layout.shapes
    )

    assert 0.0 in y_values
    assert -25.0 in y_values


def test_drawdown_chart_layout(
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Drawdown chart should use the expected professional layout.
    """

    figure = build_drawdown_chart(
        complete_service_result
    )

    assert figure.layout.title.text == "Portfolio Drawdown"
    assert figure.layout.xaxis.title.text == "Date"
    assert figure.layout.yaxis.title.text == "Drawdown (%)"
    assert figure.layout.height == 420
    assert figure.layout.showlegend is False


def test_drawdown_chart_empty_state(
    unavailable_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Missing drawdown data should return an annotated empty figure.
    """

    figure = build_drawdown_chart(
        unavailable_service_result
    )

    assert isinstance(figure, go.Figure)
    assert len(figure.data) == 0
    assert len(figure.layout.annotations) == 1

    assert (
        "Portfolio valuation history"
        in figure.layout.annotations[0].text
    )


def test_drawdown_chart_rejects_wrong_type() -> None:
    """
    Drawdown builder should reject unsupported result objects.
    """

    with pytest.raises(
        TypeError,
        match="AdvancedAnalyticsServiceResult",
    ):
        build_drawdown_chart(  # type: ignore[arg-type]
            {}
        )


# ============================================================
# Rolling Returns Chart Tests
# ============================================================


def test_build_rolling_returns_chart(
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Non-annualised rolling returns should use total-return values.
    """

    figure = build_rolling_returns_chart(
        complete_service_result
    )

    assert isinstance(figure, go.Figure)
    assert len(figure.data) == 1

    trace = figure.data[0]

    assert isinstance(trace, go.Scatter)
    assert trace.mode == "lines+markers"
    assert trace.name == "Rolling Return"

    assert tuple(trace.y) == pytest.approx(
        (
            10.0,
            ((108.0 / 105.0) - 1.0) * 100.0,
            ((115.0 / 110.0) - 1.0) * 100.0,
        )
    )


def test_rolling_returns_chart_contains_target_line(
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Target return should be shown as a reference line.
    """

    figure = build_rolling_returns_chart(
        complete_service_result
    )

    assert len(figure.layout.shapes) == 2

    y_values = tuple(
        shape.y0
        for shape in figure.layout.shapes
    )

    assert 0.0 in y_values
    assert 5.0 in y_values


def test_rolling_returns_chart_layout(
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Rolling chart should expose expected titles.
    """

    figure = build_rolling_returns_chart(
        complete_service_result
    )

    assert (
        figure.layout.title.text
        == "Rolling Portfolio Returns"
    )

    assert (
        figure.layout.xaxis.title.text
        == "Period End Date"
    )

    assert (
        figure.layout.yaxis.title.text
        == "Rolling Return (%)"
    )


def test_annualised_rolling_returns_chart(
    annualised_rolling_returns_result: RollingReturnsResult,
) -> None:
    """
    Annualised results should use annualised percentage values.
    """

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
        benchmark=None,
        rolling_returns=annualised_rolling_returns_result,
        failures=(),
    )

    service_result = AdvancedAnalyticsServiceResult(
        status="complete",
        portfolio=(),
        portfolio_totals=None,
        adapter_result=None,
        analytics=analytics,
        available_metrics=("rolling_returns",),
        unavailable_metrics=(),
        failures=(),
    )

    figure = build_rolling_returns_chart(
        service_result
    )

    assert (
        figure.layout.title.text
        == "Annualised Rolling Portfolio Returns"
    )

    assert (
        figure.layout.yaxis.title.text
        == "Annualised Return (%)"
    )

    assert figure.data[0].name == "Annualised Rolling Return"

    assert tuple(figure.data[0].y) == pytest.approx(
        (
            10.007,
            10.007,
        )
    )


def test_rolling_chart_without_target_has_one_reference_line(
    annualised_rolling_returns_result: RollingReturnsResult,
) -> None:
    """
    Missing target return should omit the target reference line.
    """

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
        benchmark=None,
        rolling_returns=annualised_rolling_returns_result,
        failures=(),
    )

    service_result = AdvancedAnalyticsServiceResult(
        status="complete",
        portfolio=(),
        portfolio_totals=None,
        adapter_result=None,
        analytics=analytics,
        available_metrics=("rolling_returns",),
        unavailable_metrics=(),
        failures=(),
    )

    figure = build_rolling_returns_chart(
        service_result
    )

    assert len(figure.layout.shapes) == 1
    assert figure.layout.shapes[0].y0 == 0.0


def test_rolling_returns_chart_empty_state(
    unavailable_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Missing rolling-return data should produce an empty figure.
    """

    figure = build_rolling_returns_chart(
        unavailable_service_result
    )

    assert len(figure.data) == 0
    assert len(figure.layout.annotations) == 1

    assert (
        "Sufficient portfolio valuation history"
        in figure.layout.annotations[0].text
    )


def test_rolling_returns_chart_rejects_wrong_type() -> None:
    """
    Rolling-return builder should reject unsupported objects.
    """

    with pytest.raises(
        TypeError,
        match="AdvancedAnalyticsServiceResult",
    ):
        build_rolling_returns_chart(  # type: ignore[arg-type]
            {}
        )


# ============================================================
# Benchmark Comparison Chart Tests
# ============================================================


def test_build_benchmark_comparison_chart(
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Benchmark comparison should contain one bar trace.
    """

    figure = build_benchmark_comparison_chart(
        complete_service_result
    )

    assert isinstance(figure, go.Figure)
    assert len(figure.data) == 1

    trace = figure.data[0]

    assert isinstance(trace, go.Bar)

    assert tuple(trace.x) == (
        "Portfolio",
        "Nifty 50 TRI",
        "Excess Return",
        "Alpha",
        "Tracking Error",
    )

    assert tuple(trace.y) == pytest.approx(
        (
            14.4,
            12.0,
            2.4,
            1.8,
            3.0,
        )
    )


def test_benchmark_comparison_layout(
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Benchmark comparison should use annualised percentage axis.
    """

    figure = build_benchmark_comparison_chart(
        complete_service_result
    )

    assert figure.layout.title.text == "Portfolio vs Benchmark"

    assert (
        figure.layout.yaxis.title.text
        == "Annualised Value (%)"
    )

    assert figure.layout.showlegend is False


def test_benchmark_chart_uses_generic_name_when_missing(
    benchmark_result: BenchmarkResult,
) -> None:
    """
    Missing benchmark name should fall back to Benchmark.
    """

    generic_benchmark = BenchmarkResult(
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
        benchmark=generic_benchmark,
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

    figure = build_benchmark_comparison_chart(
        service_result
    )

    assert tuple(figure.data[0].x)[1] == "Benchmark"


def test_benchmark_comparison_uses_zero_when_alpha_missing(
    benchmark_result: BenchmarkResult,
) -> None:
    """
    Undefined alpha should produce a stable zero-height bar.
    """

    undefined_alpha = BenchmarkResult(
        observation_count=benchmark_result.observation_count,
        periods_per_year=benchmark_result.periods_per_year,
        benchmark_name=benchmark_result.benchmark_name,
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
        beta=None,
        alpha_decimal=None,
        alpha_percent=None,
        correlation=None,
        r_squared=None,
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
        benchmark=undefined_alpha,
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

    figure = build_benchmark_comparison_chart(
        service_result
    )

    assert tuple(figure.data[0].y)[3] == 0.0


def test_benchmark_comparison_empty_state(
    unavailable_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Missing benchmark metrics should return an empty figure.
    """

    figure = build_benchmark_comparison_chart(
        unavailable_service_result
    )

    assert len(figure.data) == 0
    assert len(figure.layout.annotations) == 1

    assert (
        "Aligned portfolio and benchmark"
        in figure.layout.annotations[0].text
    )


def test_benchmark_comparison_rejects_wrong_type() -> None:
    """
    Benchmark builder should reject unsupported objects.
    """

    with pytest.raises(
        TypeError,
        match="AdvancedAnalyticsServiceResult",
    ):
        build_benchmark_comparison_chart(  # type: ignore[arg-type]
            {}
        )


# ============================================================
# Active Return Chart Tests
# ============================================================


def test_build_active_return_chart(
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Active return chart should expose worst, annualised, and best values.
    """

    figure = build_active_return_chart(
        complete_service_result
    )

    assert len(figure.data) == 1
    assert isinstance(figure.data[0], go.Bar)

    assert tuple(figure.data[0].x) == (
        "Worst Period",
        "Annualised Excess",
        "Best Period",
    )

    assert tuple(figure.data[0].y) == pytest.approx(
        (
            -1.0,
            2.4,
            2.0,
        )
    )


def test_active_return_chart_layout(
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Active-return chart should expose the expected labels.
    """

    figure = build_active_return_chart(
        complete_service_result
    )

    assert figure.layout.title.text == "Active Return Analysis"
    assert figure.layout.yaxis.title.text == "Active Return (%)"
    assert figure.layout.showlegend is False


def test_active_return_chart_has_zero_line(
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Active-return chart should contain a benchmark zero line.
    """

    figure = build_active_return_chart(
        complete_service_result
    )

    assert len(figure.layout.shapes) == 1
    assert figure.layout.shapes[0].y0 == 0.0


def test_active_return_chart_empty_state(
    unavailable_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Missing benchmark data should return an empty active-return figure.
    """

    figure = build_active_return_chart(
        unavailable_service_result
    )

    assert len(figure.data) == 0
    assert len(figure.layout.annotations) == 1

    assert (
        "Benchmark-relative return data"
        in figure.layout.annotations[0].text
    )


def test_active_return_chart_rejects_wrong_type() -> None:
    """
    Active-return builder should reject unsupported objects.
    """

    with pytest.raises(
        TypeError,
        match="AdvancedAnalyticsServiceResult",
    ):
        build_active_return_chart(  # type: ignore[arg-type]
            {}
        )


# ============================================================
# Return Frequency Chart Tests
# ============================================================


def test_build_return_frequency_chart(
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Return-frequency chart should display direction counts.
    """

    figure = build_return_frequency_chart(
        complete_service_result
    )

    assert len(figure.data) == 1
    assert isinstance(figure.data[0], go.Bar)

    assert tuple(figure.data[0].x) == (
        "Positive Periods",
        "Negative Periods",
        "Flat Periods",
    )

    assert tuple(figure.data[0].y) == (
        8,
        3,
        1,
    )


def test_return_frequency_customdata(
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Return-frequency hover data should contain percentages.
    """

    figure = build_return_frequency_chart(
        complete_service_result
    )

    assert tuple(
        figure.data[0].customdata
    ) == pytest.approx(
        (
            (8 / 12) * 100.0,
            (3 / 12) * 100.0,
            (1 / 12) * 100.0,
        )
    )


def test_return_frequency_chart_layout(
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Frequency chart should use period-count axis.
    """

    figure = build_return_frequency_chart(
        complete_service_result
    )

    assert figure.layout.title.text == "Return Frequency"

    assert (
        figure.layout.yaxis.title.text
        == "Number of Periods"
    )

    assert figure.layout.showlegend is False


def test_return_frequency_empty_state(
    unavailable_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Missing risk metrics should return an empty figure.
    """

    figure = build_return_frequency_chart(
        unavailable_service_result
    )

    assert len(figure.data) == 0
    assert len(figure.layout.annotations) == 1

    assert (
        "Periodic portfolio return history"
        in figure.layout.annotations[0].text
    )


def test_return_frequency_rejects_wrong_type() -> None:
    """
    Return-frequency builder should reject unsupported objects.
    """

    with pytest.raises(
        TypeError,
        match="AdvancedAnalyticsServiceResult",
    ):
        build_return_frequency_chart(  # type: ignore[arg-type]
            {}
        )


# ============================================================
# Chart Availability Message Tests
# ============================================================


def test_get_risk_chart_messages_complete(
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Complete analytics should not produce unavailable messages.
    """

    assert get_risk_chart_messages(
        complete_service_result
    ) == ()


def test_get_risk_chart_messages_unavailable(
    unavailable_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Missing analytics should report all five chart unavailability states.
    """

    messages = get_risk_chart_messages(
        unavailable_service_result
    )

    assert len(messages) == 5

    assert tuple(
        message.title
        for message in messages
    ) == (
        "Portfolio Drawdown",
        "Rolling Portfolio Returns",
        "Portfolio vs Benchmark",
        "Active Return Analysis",
        "Return Frequency",
    )


def test_get_risk_chart_messages_partial(
    drawdown_result: DrawdownResult,
) -> None:
    """
    Partial analytics should omit messages for available charts.
    """

    analytics = AdvancedAnalyticsResult(
        status="complete",
        requested_metric_count=1,
        successful_metric_count=1,
        failed_metric_count=0,
        cagr=None,
        xirr=None,
        volatility=None,
        drawdown=drawdown_result,
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

    messages = get_risk_chart_messages(
        service_result
    )

    assert len(messages) == 4

    assert all(
        message.title != "Portfolio Drawdown"
        for message in messages
    )


def test_get_risk_chart_messages_rejects_wrong_type() -> None:
    """
    Availability helper should reject unsupported objects.
    """

    with pytest.raises(
        TypeError,
        match="AdvancedAnalyticsServiceResult",
    ):
        get_risk_chart_messages(  # type: ignore[arg-type]
            {}
        )


# ============================================================
# Stable Key Tests
# ============================================================


def test_chart_keys_are_unique() -> None:
    """
    Every Plotly chart must use a unique Streamlit key.
    """

    keys = (
        DRAW_DOWN_CHART_KEY,
        ROLLING_RETURNS_CHART_KEY,
        BENCHMARK_COMPARISON_CHART_KEY,
        ACTIVE_RETURNS_CHART_KEY,
        RETURN_FREQUENCY_CHART_KEY,
    )

    assert len(keys) == len(set(keys))


def test_chart_keys_are_non_empty_strings() -> None:
    """
    Chart keys should be stable non-empty strings.
    """

    keys = (
        DRAW_DOWN_CHART_KEY,
        ROLLING_RETURNS_CHART_KEY,
        BENCHMARK_COMPARISON_CHART_KEY,
        ACTIVE_RETURNS_CHART_KEY,
        RETURN_FREQUENCY_CHART_KEY,
    )

    assert all(
        isinstance(key, str) and key.strip()
        for key in keys
    )


# ============================================================
# Streamlit Rendering Tests
# ============================================================


@patch(
    "dashboard.components.analytics.risk_charts.st"
)
def test_render_risk_charts_complete(
    mock_st: MagicMock,
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Complete results should render five Plotly charts.
    """

    first_row = (
        MagicMock(),
        MagicMock(),
    )

    second_row = (
        MagicMock(),
        MagicMock(),
    )

    mock_st.columns.side_effect = (
        first_row,
        second_row,
    )

    render_risk_charts(
        complete_service_result
    )

    mock_st.subheader.assert_called_once_with(
        "Advanced Risk & Benchmark Analysis"
    )

    mock_st.caption.assert_called_once()

    assert mock_st.columns.call_count == 2
    assert mock_st.plotly_chart.call_count == 5

    mock_st.warning.assert_not_called()
    mock_st.error.assert_not_called()
    mock_st.info.assert_not_called()


@patch(
    "dashboard.components.analytics.risk_charts.st"
)
def test_render_risk_charts_uses_unique_keys(
    mock_st: MagicMock,
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Renderer should pass all stable keys exactly once.
    """

    mock_st.columns.side_effect = (
        (
            MagicMock(),
            MagicMock(),
        ),
        (
            MagicMock(),
            MagicMock(),
        ),
    )

    render_risk_charts(
        complete_service_result
    )

    rendered_keys = tuple(
        call.kwargs["key"]
        for call in mock_st.plotly_chart.call_args_list
    )

    assert rendered_keys == (
        DRAW_DOWN_CHART_KEY,
        ROLLING_RETURNS_CHART_KEY,
        BENCHMARK_COMPARISON_CHART_KEY,
        ACTIVE_RETURNS_CHART_KEY,
        RETURN_FREQUENCY_CHART_KEY,
    )

    assert len(rendered_keys) == len(set(rendered_keys))


@patch(
    "dashboard.components.analytics.risk_charts.st"
)
def test_render_risk_charts_configuration(
    mock_st: MagicMock,
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Every chart should use responsive display configuration.
    """

    mock_st.columns.side_effect = (
        (
            MagicMock(),
            MagicMock(),
        ),
        (
            MagicMock(),
            MagicMock(),
        ),
    )

    render_risk_charts(
        complete_service_result
    )

    for chart_call in mock_st.plotly_chart.call_args_list:
        assert chart_call.kwargs["use_container_width"] is True

        assert chart_call.kwargs["config"] == {
            "displayModeBar": False,
            "responsive": True,
        }


@patch(
    "dashboard.components.analytics.risk_charts.st"
)
def test_render_partial_status_warning(
    mock_st: MagicMock,
    complete_analytics_result: AdvancedAnalyticsResult,
) -> None:
    """
    Partial service status should render one warning.
    """

    service_result = AdvancedAnalyticsServiceResult(
        status="partial",
        portfolio=(),
        portfolio_totals=None,
        adapter_result=None,
        analytics=complete_analytics_result,
        available_metrics=("drawdown",),
        unavailable_metrics=("benchmark",),
        failures=(),
    )

    mock_st.columns.side_effect = (
        (
            MagicMock(),
            MagicMock(),
        ),
        (
            MagicMock(),
            MagicMock(),
        ),
    )

    render_risk_charts(
        service_result
    )

    mock_st.warning.assert_called_once()
    mock_st.error.assert_not_called()
    mock_st.info.assert_not_called()


@patch(
    "dashboard.components.analytics.risk_charts.st"
)
def test_render_failed_status_error(
    mock_st: MagicMock,
) -> None:
    """
    Failed service status should render one error.
    """

    service_result = AdvancedAnalyticsServiceResult(
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
        (
            MagicMock(),
            MagicMock(),
        ),
        (
            MagicMock(),
            MagicMock(),
        ),
    )

    render_risk_charts(
        service_result
    )

    mock_st.error.assert_called_once()
    mock_st.warning.assert_not_called()
    mock_st.info.assert_not_called()


@patch(
    "dashboard.components.analytics.risk_charts.st"
)
def test_render_unavailable_status_info(
    mock_st: MagicMock,
    unavailable_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Unavailable service status should render one information message.
    """

    mock_st.columns.side_effect = (
        (
            MagicMock(),
            MagicMock(),
        ),
        (
            MagicMock(),
            MagicMock(),
        ),
    )

    render_risk_charts(
        unavailable_service_result
    )

    mock_st.info.assert_called_once()
    mock_st.warning.assert_not_called()
    mock_st.error.assert_not_called()


@patch(
    "dashboard.components.analytics.risk_charts.st"
)
def test_render_risk_charts_rejects_wrong_type(
    mock_st: MagicMock,
) -> None:
    """
    Renderer should reject unsupported result objects.
    """

    with pytest.raises(
        TypeError,
        match="AdvancedAnalyticsServiceResult",
    ):
        render_risk_charts(  # type: ignore[arg-type]
            {}
        )

    mock_st.subheader.assert_not_called()
    mock_st.plotly_chart.assert_not_called()


@patch(
    "dashboard.components.analytics.risk_charts.render_risk_charts"
)
def test_show_risk_charts_alias(
    mock_render: MagicMock,
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Compatibility alias should delegate to the main renderer.
    """

    show_risk_charts(
        complete_service_result
    )

    mock_render.assert_called_once_with(
        complete_service_result
    )


# ============================================================
# Empty Figure Stability Tests
# ============================================================


@pytest.mark.parametrize(
    "builder",
    [
        build_drawdown_chart,
        build_rolling_returns_chart,
        build_benchmark_comparison_chart,
        build_active_return_chart,
        build_return_frequency_chart,
    ],
)
def test_empty_figures_have_hidden_axes(
    builder: object,
    unavailable_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Empty chart states should hide both chart axes.
    """

    figure = builder(  # type: ignore[operator]
        unavailable_service_result
    )

    assert figure.layout.xaxis.visible is False
    assert figure.layout.yaxis.visible is False
    assert figure.layout.height == 360


@pytest.mark.parametrize(
    "builder",
    [
        build_drawdown_chart,
        build_rolling_returns_chart,
        build_benchmark_comparison_chart,
        build_active_return_chart,
        build_return_frequency_chart,
    ],
)
def test_chart_builders_return_new_figures(
    builder: object,
    complete_service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Repeated chart construction should return independent figures.
    """

    first = builder(  # type: ignore[operator]
        complete_service_result
    )

    second = builder(  # type: ignore[operator]
        complete_service_result
    )

    assert isinstance(first, go.Figure)
    assert isinstance(second, go.Figure)
    assert first is not second