"""Institutional tail-risk KPI presentation component."""

from __future__ import annotations

from math import isfinite

import streamlit as st

from dashboard.components.analytics.advanced_kpis import (
    AdvancedKPI,
)
from models.portfolio_risk_metrics import PortfolioRiskMetrics
from services.advanced_analytics_service import (
    AdvancedAnalyticsServiceResult,
)
from services.portfolio_risk_service import PortfolioRiskService


def _format_ratio(
    value: float,
) -> str:
    """Format a finite dimensionless ratio."""

    if not isfinite(value):
        return "N/A"

    return f"{value:,.2f}"


def _format_decimal_percentage(
    value: float,
) -> str:
    """Format a decimal return as a percentage."""

    if not isfinite(value):
        return "N/A"

    return f"{value * 100.0:,.2f}%"


def build_institutional_risk_kpis(
    metrics: PortfolioRiskMetrics,
) -> tuple[AdvancedKPI, ...]:
    """Build institutional tail-risk KPI presentation models."""

    if not isinstance(
        metrics,
        PortfolioRiskMetrics,
    ):
        raise TypeError(
            "metrics must be an instance of PortfolioRiskMetrics."
        )

    return (
        AdvancedKPI(
            label="Calmar Ratio",
            value=_format_ratio(
                metrics.calmar_ratio
            ),
            delta="Annualised return per unit of drawdown",
            help_text=(
                "Annualised compounded return divided by the absolute "
                "maximum drawdown."
            ),
            status="neutral",
        ),
        AdvancedKPI(
            label="Omega Ratio",
            value=_format_ratio(
                metrics.omega_ratio
            ),
            delta="Probability-weighted gains versus losses",
            help_text=(
                "Returns above the selected threshold relative to "
                "returns below it."
            ),
            status="neutral",
        ),
        AdvancedKPI(
            label="Value at Risk",
            value=_format_decimal_percentage(
                metrics.value_at_risk
            ),
            delta="Historical loss threshold",
            help_text=(
                "Historical loss magnitude at the configured confidence "
                "level."
            ),
            status="neutral",
        ),
        AdvancedKPI(
            label="Conditional Value at Risk",
            value=_format_decimal_percentage(
                metrics.conditional_value_at_risk
            ),
            delta="Average loss beyond VaR",
            help_text=(
                "Average historical loss within the tail beyond the "
                "Value at Risk threshold."
            ),
            status="neutral",
        ),
    )


def calculate_institutional_risk_metrics(
    service_result: AdvancedAnalyticsServiceResult,
    *,
    risk_service: PortfolioRiskService | None = None,
) -> PortfolioRiskMetrics | None:
    """Calculate institutional metrics from normalized adapter returns."""

    if not isinstance(
        service_result,
        AdvancedAnalyticsServiceResult,
    ):
        raise TypeError(
            "service_result must be an instance of "
            "AdvancedAnalyticsServiceResult."
        )

    adapter_result = service_result.adapter_result

    if adapter_result is None:
        return None

    benchmark_input = (
        adapter_result
        .analytics_input
        .benchmark
    )

    if benchmark_input is None:
        return None

    resolved_risk_service = (
        risk_service
        if risk_service is not None
        else PortfolioRiskService()
    )

    return resolved_risk_service.calculate(
        portfolio_returns=benchmark_input.portfolio_returns,
        benchmark_returns=benchmark_input.benchmark_returns,
        risk_free_rate=benchmark_input.annual_risk_free_rate,
        periods_per_year=benchmark_input.periods_per_year,
    )


def render_institutional_risk_kpis(
    metrics: PortfolioRiskMetrics,
    *,
    source_label: str | None = None,
) -> None:
    """Render institutional tail-risk KPI cards in one row."""

    if not isinstance(
        metrics,
        PortfolioRiskMetrics,
    ):
        raise TypeError(
            "metrics must be an instance of PortfolioRiskMetrics."
        )

    st.subheader(
        "Institutional Tail-Risk Analytics"
    )

    caption = (
        "Review drawdown efficiency, gain-loss asymmetry, and "
        "historical loss-tail exposure."
    )

    if source_label:
        caption += (
            f" Source: {source_label}. "
            "This is not actual transaction-based portfolio history."
        )

    st.caption(
        caption
    )

    kpis = build_institutional_risk_kpis(
        metrics
    )

    columns = st.columns(4)

    for column, kpi in zip(
        columns,
        kpis,
        strict=True,
    ):
        with column:
            st.metric(
                label=kpi.label,
                value=kpi.value,
                delta=kpi.delta,
                delta_color="off",
                help=kpi.help_text,
                border=True,
            )


__all__ = [
    "build_institutional_risk_kpis",
    "calculate_institutional_risk_metrics",
    "render_institutional_risk_kpis",
]