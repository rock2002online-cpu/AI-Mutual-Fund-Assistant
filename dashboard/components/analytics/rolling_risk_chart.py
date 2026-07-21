"""Institutional rolling risk-metrics chart component."""

from __future__ import annotations

from collections.abc import Iterable

import plotly.graph_objects as go
import streamlit as st

from models.portfolio_risk_metrics import PortfolioRiskMetrics
from services.advanced_analytics_service import (
    AdvancedAnalyticsServiceResult,
)
from services.portfolio_risk_service import PortfolioRiskService


ROLLING_RISK_CHART_KEY = (
    "institutional_rolling_risk_metrics_chart"
)


def calculate_rolling_risk_metrics(
    service_result: AdvancedAnalyticsServiceResult,
    *,
    window_size: int = 12,
    risk_service: PortfolioRiskService | None = None,
) -> tuple[PortfolioRiskMetrics, ...]:
    """Calculate rolling metrics from normalized benchmark returns."""

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
        return ()

    benchmark_input = (
        adapter_result
        .analytics_input
        .benchmark
    )

    if benchmark_input is None:
        return ()

    resolved_risk_service = (
        risk_service
        if risk_service is not None
        else PortfolioRiskService()
    )

    return resolved_risk_service.calculate_rolling_risk_metrics(
        portfolio_returns=benchmark_input.portfolio_returns,
        benchmark_returns=benchmark_input.benchmark_returns,
        risk_free_rate=benchmark_input.annual_risk_free_rate,
        periods_per_year=benchmark_input.periods_per_year,
        window_size=window_size,
    )


def build_rolling_risk_chart(
    rolling_metrics: Iterable[PortfolioRiskMetrics],
) -> go.Figure:
    """Build rolling volatility, Sharpe, and Sortino trend lines."""

    normalized_metrics = tuple(
        rolling_metrics
    )

    if not all(
        isinstance(metric, PortfolioRiskMetrics)
        for metric in normalized_metrics
    ):
        raise TypeError(
            "rolling_metrics must contain only "
            "PortfolioRiskMetrics instances."
        )

    window_numbers = tuple(
        range(
            1,
            len(normalized_metrics) + 1,
        )
    )

    figure = go.Figure()

    figure.add_trace(
        go.Scatter(
            x=window_numbers,
            y=tuple(
                metric.volatility
                for metric in normalized_metrics
            ),
            mode="lines+markers",
            name="Annualised Volatility",
            hovertemplate=(
                "Window %{x}<br>"
                "Volatility: %{y:.2f}%"
                "<extra></extra>"
            ),
        )
    )

    figure.add_trace(
        go.Scatter(
            x=window_numbers,
            y=tuple(
                metric.sharpe_ratio
                for metric in normalized_metrics
            ),
            mode="lines+markers",
            name="Sharpe Ratio",
            yaxis="y2",
            hovertemplate=(
                "Window %{x}<br>"
                "Sharpe: %{y:.2f}"
                "<extra></extra>"
            ),
        )
    )

    figure.add_trace(
        go.Scatter(
            x=window_numbers,
            y=tuple(
                metric.sortino_ratio
                for metric in normalized_metrics
            ),
            mode="lines+markers",
            name="Sortino Ratio",
            yaxis="y2",
            hovertemplate=(
                "Window %{x}<br>"
                "Sortino: %{y:.2f}"
                "<extra></extra>"
            ),
        )
    )

    figure.update_layout(
        title="Rolling Risk Metrics",
        height=420,
        margin={
            "l": 45,
            "r": 45,
            "t": 65,
            "b": 45,
        },
        hovermode="x unified",
        xaxis_title="Rolling Window",
        yaxis={
            "title": "Annualised Volatility (%)",
        },
        yaxis2={
            "title": "Risk-Adjusted Ratio",
            "overlaying": "y",
            "side": "right",
        },
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
        },
    )

    return figure


def render_rolling_risk_chart(
    rolling_metrics: Iterable[PortfolioRiskMetrics],
    *,
    source_label: str | None = None,
) -> None:
    """Render institutional rolling risk trends in Streamlit."""

    normalized_metrics = tuple(
        rolling_metrics
    )

    st.subheader(
        "Rolling Institutional Risk Trends"
    )

    caption = (
        "Monitor how portfolio volatility and risk-adjusted performance "
        "change across consecutive rolling windows."
    )

    if source_label:
        caption += (
            f" Source: {source_label}. "
            "This is not actual transaction-based portfolio history."
        )

    st.caption(
        caption
    )

    st.plotly_chart(
        build_rolling_risk_chart(
            normalized_metrics
        ),
        width="stretch",
        key=ROLLING_RISK_CHART_KEY,
        config={
            "displayModeBar": False,
            "responsive": True,
        },
    )


__all__ = [
    "ROLLING_RISK_CHART_KEY",
    "build_rolling_risk_chart",
    "calculate_rolling_risk_metrics",
    "render_rolling_risk_chart",
]