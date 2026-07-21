"""Tests for the institutional Rolling Risk Metrics chart."""

import importlib

import plotly.graph_objects as go

from models.portfolio_risk_metrics import PortfolioRiskMetrics
from unittest.mock import MagicMock, patch
from services.advanced_analytics_service import (
    AdvancedAnalyticsServiceResult,
)
from services.analytics.benchmark import BenchmarkInput
from services.portfolio_risk_service import PortfolioRiskService


def test_build_rolling_risk_chart() -> None:
    """Plot volatility, Sharpe, and Sortino across rolling windows."""

    rolling_risk_chart = importlib.import_module(
        "dashboard.components.analytics.rolling_risk_chart"
    )

    metrics = (
        PortfolioRiskMetrics(
            volatility=8.0,
            sharpe_ratio=0.80,
            sortino_ratio=1.10,
        ),
        PortfolioRiskMetrics(
            volatility=9.0,
            sharpe_ratio=0.90,
            sortino_ratio=1.20,
        ),
        PortfolioRiskMetrics(
            volatility=10.0,
            sharpe_ratio=1.00,
            sortino_ratio=1.30,
        ),
    )

    figure = rolling_risk_chart.build_rolling_risk_chart(
        metrics
    )

    assert isinstance(
        figure,
        go.Figure,
    )

    assert len(figure.data) == 3

    assert tuple(
        trace.name
        for trace in figure.data
    ) == (
        "Annualised Volatility",
        "Sharpe Ratio",
        "Sortino Ratio",
    )

    assert tuple(figure.data[0].y) == (
        8.0,
        9.0,
        10.0,
    )

@patch(
    "dashboard.components.analytics.rolling_risk_chart.st",
    create=True,
)
def test_render_rolling_risk_chart(
    mock_st: MagicMock,
) -> None:
    """Render the rolling chart with a stable Streamlit key."""

    rolling_risk_chart = importlib.import_module(
        "dashboard.components.analytics.rolling_risk_chart"
    )

    metrics = (
        PortfolioRiskMetrics(
            volatility=8.0,
            sharpe_ratio=0.80,
            sortino_ratio=1.10,
        ),
        PortfolioRiskMetrics(
            volatility=9.0,
            sharpe_ratio=0.90,
            sortino_ratio=1.20,
        ),
    )

    rolling_risk_chart.render_rolling_risk_chart(
        metrics
    )

    mock_st.subheader.assert_called_once_with(
        "Rolling Institutional Risk Trends"
    )

    mock_st.plotly_chart.assert_called_once()

    chart_call = mock_st.plotly_chart.call_args

    assert isinstance(
        chart_call.args[0],
        go.Figure,
    )

    assert (
        chart_call.kwargs["key"]
        == "institutional_rolling_risk_metrics_chart"
    )

    assert chart_call.kwargs["width"] == "stretch"
    assert "use_container_width" not in chart_call.kwargs

def test_calculate_rolling_risk_metrics_uses_adapter_returns() -> None:
    """Reuse normalized returns for rolling institutional metrics."""

    rolling_risk_chart = importlib.import_module(
        "dashboard.components.analytics.rolling_risk_chart"
    )

    benchmark_input = BenchmarkInput(
        portfolio_returns=(
            0.02,
            -0.01,
            0.03,
            0.01,
        ),
        benchmark_returns=(
            0.01,
            -0.02,
            0.02,
            0.01,
        ),
        periods_per_year=12,
        annual_risk_free_rate=0.06,
        benchmark_name="Nifty 50 TRI",
    )

    adapter_result = MagicMock()
    adapter_result.analytics_input.benchmark = benchmark_input

    service_result = AdvancedAnalyticsServiceResult(
        status="complete",
        portfolio=(),
        portfolio_totals=None,
        adapter_result=adapter_result,
        analytics=None,
        available_metrics=("benchmark",),
        unavailable_metrics=(),
        failures=(),
    )

    expected = (
        PortfolioRiskMetrics(
            volatility=8.0,
        ),
        PortfolioRiskMetrics(
            volatility=9.0,
        ),
        PortfolioRiskMetrics(
            volatility=10.0,
        ),
    )

    risk_service = MagicMock(
        spec=PortfolioRiskService,
    )

    risk_service.calculate_rolling_risk_metrics.return_value = (
        expected
    )

    result = rolling_risk_chart.calculate_rolling_risk_metrics(
        service_result,
        window_size=2,
        risk_service=risk_service,
    )

    assert result == expected

    risk_service.calculate_rolling_risk_metrics.assert_called_once_with(
        portfolio_returns=benchmark_input.portfolio_returns,
        benchmark_returns=benchmark_input.benchmark_returns,
        risk_free_rate=benchmark_input.annual_risk_free_rate,
        periods_per_year=benchmark_input.periods_per_year,
        window_size=2,
    )