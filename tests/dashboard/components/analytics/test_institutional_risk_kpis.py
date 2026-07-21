"""Tests for institutional tail-risk KPI presentation."""

import importlib
from unittest.mock import MagicMock, patch

from models.portfolio_risk_metrics import PortfolioRiskMetrics
from services.advanced_analytics_service import (
    AdvancedAnalyticsServiceResult,
)
from services.analytics.benchmark import BenchmarkInput
from services.portfolio_risk_service import PortfolioRiskService


def _build_metrics() -> PortfolioRiskMetrics:
    """Return representative institutional risk metrics."""

    return PortfolioRiskMetrics(
        calmar_ratio=0.75,
        omega_ratio=1.80,
        value_at_risk=0.04,
        conditional_value_at_risk=0.06,
    )


def test_build_institutional_risk_kpis() -> None:
    """Build Calmar, Omega, VaR, and CVaR institutional cards."""

    institutional_risk_kpis = importlib.import_module(
        "dashboard.components.analytics.institutional_risk_kpis"
    )

    result = (
        institutional_risk_kpis
        .build_institutional_risk_kpis(
            _build_metrics()
        )
    )

    assert tuple(
        kpi.label
        for kpi in result
    ) == (
        "Calmar Ratio",
        "Omega Ratio",
        "Value at Risk",
        "Conditional Value at Risk",
    )

    assert tuple(
        kpi.value
        for kpi in result
    ) == (
        "0.75",
        "1.80",
        "4.00%",
        "6.00%",
    )


@patch(
    "dashboard.components.analytics.institutional_risk_kpis.st",
)
def test_render_institutional_risk_kpis(
    mock_st: MagicMock,
) -> None:
    """Render four institutional tail-risk KPI cards."""

    institutional_risk_kpis = importlib.import_module(
        "dashboard.components.analytics.institutional_risk_kpis"
    )

    mock_st.columns.return_value = tuple(
        MagicMock()
        for _ in range(4)
    )

    institutional_risk_kpis.render_institutional_risk_kpis(
        _build_metrics()
    )

    mock_st.subheader.assert_called_once_with(
        "Institutional Tail-Risk Analytics"
    )

    mock_st.columns.assert_called_once_with(4)

    assert mock_st.metric.call_count == 4


def test_calculate_institutional_risk_metrics_uses_adapter_returns() -> None:
    """Reuse normalized benchmark returns from the analytics adapter."""

    institutional_risk_kpis = importlib.import_module(
        "dashboard.components.analytics.institutional_risk_kpis"
    )

    benchmark_input = BenchmarkInput(
        portfolio_returns=(
            0.02,
            -0.01,
            0.03,
        ),
        benchmark_returns=(
            0.01,
            -0.02,
            0.02,
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

    expected_metrics = _build_metrics()

    risk_service = MagicMock(
        spec=PortfolioRiskService,
    )

    risk_service.calculate.return_value = expected_metrics

    result = (
        institutional_risk_kpis
        .calculate_institutional_risk_metrics(
            service_result,
            risk_service=risk_service,
        )
    )

    assert result is expected_metrics

    risk_service.calculate.assert_called_once_with(
        portfolio_returns=benchmark_input.portfolio_returns,
        benchmark_returns=benchmark_input.benchmark_returns,
        risk_free_rate=benchmark_input.annual_risk_free_rate,
        periods_per_year=benchmark_input.periods_per_year,
    )