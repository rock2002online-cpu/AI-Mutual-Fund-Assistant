"""
Advanced analytics risk-chart presentation component.

This component renders:

- Portfolio drawdown history
- Rolling-return history
- Portfolio versus benchmark return comparison
- Active-return distribution
- Positive and negative return frequency
- Risk and performance summary charts

The component contains presentation logic only.

Portfolio retrieval, data preparation, and financial calculations remain in:

- PortfolioService
- AdvancedAnalyticsService
- services.analytics modules
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal

import plotly.graph_objects as go
import streamlit as st

from services.advanced_analytics_service import (
    AdvancedAnalyticsServiceResult,
)


# ============================================================
# Constants and Type Aliases
# ============================================================

ChartAvailability = Literal[
    "available",
    "unavailable",
]

DRAW_DOWN_CHART_KEY = "advanced_analytics_drawdown_chart"
ROLLING_RETURNS_CHART_KEY = "advanced_analytics_rolling_returns_chart"
BENCHMARK_COMPARISON_CHART_KEY = (
    "advanced_analytics_benchmark_comparison_chart"
)
ACTIVE_RETURNS_CHART_KEY = (
    "advanced_analytics_active_returns_chart"
)
RETURN_FREQUENCY_CHART_KEY = (
    "advanced_analytics_return_frequency_chart"
)


# ============================================================
# Presentation Models
# ============================================================


@dataclass(frozen=True, slots=True)
class ChartMessage:
    """
    Presentation model for unavailable chart content.

    Attributes:
        title:
            User-facing chart title.

        message:
            Explanation shown when chart data is unavailable.

        availability:
            Stable chart availability classification.
    """

    title: str
    message: str
    availability: ChartAvailability = "unavailable"


# ============================================================
# Generic Formatting Helpers
# ============================================================


def _format_percentage(
    value: float | None,
    *,
    decimal_places: int = 2,
) -> str:
    """
    Format an already percentage-based value.
    """

    if value is None or not isfinite(value):
        return "N/A"

    return f"{value:,.{decimal_places}f}%"


def _safe_float(
    value: float | None,
) -> float | None:
    """
    Return a finite float or None.
    """

    if value is None:
        return None

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None

    if not isfinite(numeric_value):
        return None

    return numeric_value


def _empty_figure(
    *,
    title: str,
    message: str,
) -> go.Figure:
    """
    Build a stable empty-state Plotly figure.
    """

    figure = go.Figure()

    figure.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        align="center",
        font={
            "size": 14,
        },
    )

    figure.update_layout(
        title=title,
        height=360,
        margin={
            "l": 30,
            "r": 30,
            "t": 60,
            "b": 30,
        },
        xaxis={
            "visible": False,
        },
        yaxis={
            "visible": False,
        },
        showlegend=False,
    )

    return figure


def _base_layout(
    figure: go.Figure,
    *,
    title: str,
    xaxis_title: str | None = None,
    yaxis_title: str | None = None,
    height: int = 420,
    showlegend: bool = True,
) -> go.Figure:
    """
    Apply shared professional chart layout.
    """

    figure.update_layout(
        title=title,
        height=height,
        margin={
            "l": 45,
            "r": 25,
            "t": 65,
            "b": 45,
        },
        hovermode="x unified",
        showlegend=showlegend,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
        },
        xaxis_title=xaxis_title,
        yaxis_title=yaxis_title,
    )

    return figure


# ============================================================
# Drawdown Chart
# ============================================================


def build_drawdown_chart(
    service_result: AdvancedAnalyticsServiceResult,
) -> go.Figure:
    """
    Build the historical portfolio drawdown chart.

    The chart plots percentage decline from each running portfolio peak.
    """

    if not isinstance(
        service_result,
        AdvancedAnalyticsServiceResult,
    ):
        raise TypeError(
            "service_result must be an instance of "
            "AdvancedAnalyticsServiceResult."
        )

    analytics = service_result.analytics

    if (
        analytics is None
        or analytics.drawdown is None
        or not analytics.drawdown.drawdown_series
    ):
        return _empty_figure(
            title="Portfolio Drawdown",
            message=(
                "Portfolio valuation history is required to display "
                "drawdown analysis."
            ),
        )

    drawdown_result = analytics.drawdown

    dates = tuple(
        point.observation_date
        for point in drawdown_result.drawdown_series
    )

    drawdowns = tuple(
        point.drawdown_percent
        for point in drawdown_result.drawdown_series
    )

    figure = go.Figure()

    figure.add_trace(
        go.Scatter(
            x=dates,
            y=drawdowns,
            mode="lines",
            name="Drawdown",
            fill="tozeroy",
            customdata=tuple(
                (
                    point.value,
                    point.running_peak,
                )
                for point in drawdown_result.drawdown_series
            ),
            hovertemplate=(
                "Date: %{x}<br>"
                "Drawdown: %{y:.2f}%<br>"
                "Portfolio Value: %{customdata[0]:,.2f}<br>"
                "Running Peak: %{customdata[1]:,.2f}"
                "<extra></extra>"
            ),
        )
    )

    figure.add_hline(
        y=0.0,
        line_dash="dash",
        annotation_text="Portfolio Peak",
        annotation_position="top left",
    )

    minimum_drawdown = min(drawdowns)

    figure.add_hline(
        y=minimum_drawdown,
        line_dash="dot",
        annotation_text=(
            "Maximum Drawdown "
            f"{_format_percentage(minimum_drawdown)}"
        ),
        annotation_position="bottom right",
    )

    return _base_layout(
        figure,
        title="Portfolio Drawdown",
        xaxis_title="Date",
        yaxis_title="Drawdown (%)",
        showlegend=False,
    )


# ============================================================
# Rolling Returns Chart
# ============================================================


def build_rolling_returns_chart(
    service_result: AdvancedAnalyticsServiceResult,
) -> go.Figure:
    """
    Build the rolling-return history chart.
    """

    if not isinstance(
        service_result,
        AdvancedAnalyticsServiceResult,
    ):
        raise TypeError(
            "service_result must be an instance of "
            "AdvancedAnalyticsServiceResult."
        )

    analytics = service_result.analytics

    if (
        analytics is None
        or analytics.rolling_returns is None
        or not analytics.rolling_returns.rolling_returns
    ):
        return _empty_figure(
            title="Rolling Portfolio Returns",
            message=(
                "Sufficient portfolio valuation history is required "
                "to display rolling returns."
            ),
        )

    result = analytics.rolling_returns

    end_dates = tuple(
        point.end_date
        for point in result.rolling_returns
    )

    if result.annualised:
        return_values = tuple(
            (
                point.annualised_return_percent
                if point.annualised_return_percent is not None
                else point.total_return_percent
            )
            for point in result.rolling_returns
        )

        trace_name = "Annualised Rolling Return"
        yaxis_title = "Annualised Return (%)"

    else:
        return_values = tuple(
            point.total_return_percent
            for point in result.rolling_returns
        )

        trace_name = "Rolling Return"
        yaxis_title = "Rolling Return (%)"

    figure = go.Figure()

    figure.add_trace(
        go.Scatter(
            x=end_dates,
            y=return_values,
            mode="lines+markers",
            name=trace_name,
            customdata=tuple(
                (
                    point.start_date,
                    point.start_value,
                    point.end_value,
                    point.duration_days,
                )
                for point in result.rolling_returns
            ),
            hovertemplate=(
                "Period End: %{x}<br>"
                "Return: %{y:.2f}%<br>"
                "Period Start: %{customdata[0]}<br>"
                "Start Value: %{customdata[1]:,.2f}<br>"
                "End Value: %{customdata[2]:,.2f}<br>"
                "Duration: %{customdata[3]} days"
                "<extra></extra>"
            ),
        )
    )

    figure.add_hline(
        y=0.0,
        line_dash="dash",
        annotation_text="Break-even",
        annotation_position="top left",
    )

    if result.target_return_percent is not None:
        figure.add_hline(
            y=result.target_return_percent,
            line_dash="dot",
            annotation_text=(
                "Target "
                f"{_format_percentage(result.target_return_percent)}"
            ),
            annotation_position="top right",
        )

    title = (
        "Annualised Rolling Portfolio Returns"
        if result.annualised
        else "Rolling Portfolio Returns"
    )

    return _base_layout(
        figure,
        title=title,
        xaxis_title="Period End Date",
        yaxis_title=yaxis_title,
    )


# ============================================================
# Benchmark Comparison Chart
# ============================================================


def build_benchmark_comparison_chart(
    service_result: AdvancedAnalyticsServiceResult,
) -> go.Figure:
    """
    Build annualised portfolio-versus-benchmark comparison.
    """

    if not isinstance(
        service_result,
        AdvancedAnalyticsServiceResult,
    ):
        raise TypeError(
            "service_result must be an instance of "
            "AdvancedAnalyticsServiceResult."
        )

    analytics = service_result.analytics

    if (
        analytics is None
        or analytics.benchmark is None
    ):
        return _empty_figure(
            title="Portfolio vs Benchmark",
            message=(
                "Aligned portfolio and benchmark return history is "
                "required for comparative analysis."
            ),
        )

    benchmark = analytics.benchmark

    benchmark_name = (
        benchmark.benchmark_name
        or "Benchmark"
    )

    labels = (
        "Portfolio",
        benchmark_name,
        "Excess Return",
        "Alpha",
        "Tracking Error",
    )

    values = (
        benchmark.annualised_portfolio_return_percent,
        benchmark.annualised_benchmark_return_percent,
        benchmark.annualised_excess_return_percent,
        (
            benchmark.alpha_percent
            if benchmark.alpha_percent is not None
            else 0.0
        ),
        benchmark.tracking_error_percent,
    )

    customdata = (
        "Annualised portfolio return",
        "Annualised benchmark return",
        "Portfolio return above benchmark",
        (
            "Risk-adjusted portfolio alpha"
            if benchmark.alpha_percent is not None
            else "Alpha unavailable"
        ),
        "Annualised active-return volatility",
    )

    figure = go.Figure()

    figure.add_trace(
        go.Bar(
            x=labels,
            y=values,
            name="Performance",
            customdata=customdata,
            hovertemplate=(
                "%{x}<br>"
                "%{y:.2f}%<br>"
                "%{customdata}"
                "<extra></extra>"
            ),
        )
    )

    figure.add_hline(
        y=0.0,
        line_dash="dash",
    )

    return _base_layout(
        figure,
        title="Portfolio vs Benchmark",
        yaxis_title="Annualised Value (%)",
        showlegend=False,
    )


# ============================================================
# Active Return Distribution Chart
# ============================================================


def build_active_return_chart(
    service_result: AdvancedAnalyticsServiceResult,
) -> go.Figure:
    """
    Build active-return frequency and range chart.

    This chart uses aggregate active-return statistics exposed by the
    benchmark analytics result.
    """

    if not isinstance(
        service_result,
        AdvancedAnalyticsServiceResult,
    ):
        raise TypeError(
            "service_result must be an instance of "
            "AdvancedAnalyticsServiceResult."
        )

    analytics = service_result.analytics

    if (
        analytics is None
        or analytics.benchmark is None
    ):
        return _empty_figure(
            title="Active Return Analysis",
            message=(
                "Benchmark-relative return data is unavailable."
            ),
        )

    benchmark = analytics.benchmark

    best_active_return = (
        benchmark.best_active_return_decimal * 100.0
    )

    worst_active_return = (
        benchmark.worst_active_return_decimal * 100.0
    )

    annualised_excess_return = (
        benchmark.annualised_excess_return_percent
    )

    values = (
        worst_active_return,
        annualised_excess_return,
        best_active_return,
    )

    labels = (
        "Worst Period",
        "Annualised Excess",
        "Best Period",
    )

    figure = go.Figure()

    figure.add_trace(
        go.Bar(
            x=labels,
            y=values,
            name="Active Return",
            hovertemplate=(
                "%{x}<br>"
                "Active Return: %{y:.2f}%"
                "<extra></extra>"
            ),
        )
    )

    figure.add_hline(
        y=0.0,
        line_dash="dash",
        annotation_text="Benchmark Return",
        annotation_position="top left",
    )

    return _base_layout(
        figure,
        title="Active Return Analysis",
        yaxis_title="Active Return (%)",
        showlegend=False,
    )


# ============================================================
# Return Frequency Chart
# ============================================================


def build_return_frequency_chart(
    service_result: AdvancedAnalyticsServiceResult,
) -> go.Figure:
    """
    Build positive, negative, and flat portfolio-return frequencies.
    """

    if not isinstance(
        service_result,
        AdvancedAnalyticsServiceResult,
    ):
        raise TypeError(
            "service_result must be an instance of "
            "AdvancedAnalyticsServiceResult."
        )

    analytics = service_result.analytics

    if (
        analytics is None
        or analytics.risk_metrics is None
    ):
        return _empty_figure(
            title="Return Frequency",
            message=(
                "Periodic portfolio return history is required to "
                "display return-frequency analysis."
            ),
        )

    risk_metrics = analytics.risk_metrics

    counts = (
        risk_metrics.positive_return_count,
        risk_metrics.negative_return_count,
        risk_metrics.zero_return_count,
    )

    labels = (
        "Positive Periods",
        "Negative Periods",
        "Flat Periods",
    )

    frequencies = (
        risk_metrics.positive_return_frequency * 100.0,
        risk_metrics.negative_return_frequency * 100.0,
        (
            risk_metrics.zero_return_count
            / risk_metrics.observation_count
            * 100.0
            if risk_metrics.observation_count > 0
            else 0.0
        ),
    )

    figure = go.Figure()

    figure.add_trace(
        go.Bar(
            x=labels,
            y=counts,
            customdata=frequencies,
            name="Observation Count",
            hovertemplate=(
                "%{x}<br>"
                "Periods: %{y}<br>"
                "Frequency: %{customdata:.2f}%"
                "<extra></extra>"
            ),
        )
    )

    return _base_layout(
        figure,
        title="Return Frequency",
        yaxis_title="Number of Periods",
        showlegend=False,
    )


# ============================================================
# Chart Availability
# ============================================================


def get_risk_chart_messages(
    service_result: AdvancedAnalyticsServiceResult,
) -> tuple[ChartMessage, ...]:
    """
    Return unavailable-chart messages for the supplied service result.
    """

    if not isinstance(
        service_result,
        AdvancedAnalyticsServiceResult,
    ):
        raise TypeError(
            "service_result must be an instance of "
            "AdvancedAnalyticsServiceResult."
        )

    analytics = service_result.analytics
    messages: list[ChartMessage] = []

    if analytics is None or analytics.drawdown is None:
        messages.append(
            ChartMessage(
                title="Portfolio Drawdown",
                message="Portfolio valuation history is unavailable.",
            )
        )

    if analytics is None or analytics.rolling_returns is None:
        messages.append(
            ChartMessage(
                title="Rolling Portfolio Returns",
                message="Rolling-return history is unavailable.",
            )
        )

    if analytics is None or analytics.benchmark is None:
        messages.append(
            ChartMessage(
                title="Portfolio vs Benchmark",
                message="Benchmark comparison data is unavailable.",
            )
        )

        messages.append(
            ChartMessage(
                title="Active Return Analysis",
                message="Active-return data is unavailable.",
            )
        )

    if analytics is None or analytics.risk_metrics is None:
        messages.append(
            ChartMessage(
                title="Return Frequency",
                message="Periodic portfolio returns are unavailable.",
            )
        )

    return tuple(messages)


# ============================================================
# Rendering Helpers
# ============================================================


def _render_chart(
    figure: go.Figure,
    *,
    key: str,
) -> None:
    """
    Render a Plotly chart with a stable unique Streamlit key.
    """

    if not isinstance(figure, go.Figure):
        raise TypeError(
            "figure must be an instance of plotly.graph_objects.Figure."
        )

    if not isinstance(key, str) or not key.strip():
        raise TypeError(
            "key must be a non-empty string."
        )

    st.plotly_chart(
        figure,
        use_container_width=True,
        key=key,
        config={
            "displayModeBar": False,
            "responsive": True,
        },
    )


# ============================================================
# Public Rendering API
# ============================================================


def render_risk_charts(
    service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Render the complete advanced risk-chart section.

    The component uses multiple independent chart rows and stable unique keys
    to prevent duplicate Plotly element errors.
    """

    if not isinstance(
        service_result,
        AdvancedAnalyticsServiceResult,
    ):
        raise TypeError(
            "service_result must be an instance of "
            "AdvancedAnalyticsServiceResult."
        )

    st.subheader("Advanced Risk & Benchmark Analysis")

    st.caption(
        "Explore drawdowns, rolling performance, benchmark-relative "
        "returns, active performance, and return consistency."
    )

    first_row = st.columns(2)

    with first_row[0]:
        _render_chart(
            build_drawdown_chart(service_result),
            key=DRAW_DOWN_CHART_KEY,
        )

    with first_row[1]:
        _render_chart(
            build_rolling_returns_chart(
                service_result
            ),
            key=ROLLING_RETURNS_CHART_KEY,
        )

    second_row = st.columns(2)

    with second_row[0]:
        _render_chart(
            build_benchmark_comparison_chart(
                service_result
            ),
            key=BENCHMARK_COMPARISON_CHART_KEY,
        )

    with second_row[1]:
        _render_chart(
            build_active_return_chart(
                service_result
            ),
            key=ACTIVE_RETURNS_CHART_KEY,
        )

    _render_chart(
        build_return_frequency_chart(
            service_result
        ),
        key=RETURN_FREQUENCY_CHART_KEY,
    )

    if service_result.status == "partial":
        st.warning(
            "Some charts are unavailable because one or more advanced "
            "analytics metrics could not be calculated."
        )

    elif service_result.status == "failed":
        st.error(
            "Advanced risk charts could not be prepared. Existing "
            "portfolio analytics remain unaffected."
        )

    elif service_result.status == "unavailable":
        st.info(
            "Advanced charts will become available after historical "
            "portfolio, transaction, and benchmark datasets are connected."
        )


# ============================================================
# Compatibility Alias
# ============================================================


def show_risk_charts(
    service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Backwards-friendly alias for render_risk_charts().
    """

    render_risk_charts(
        service_result
    )


# ============================================================
# Module Exports
# ============================================================


__all__ = [
    "ACTIVE_RETURNS_CHART_KEY",
    "BENCHMARK_COMPARISON_CHART_KEY",
    "ChartAvailability",
    "ChartMessage",
    "DRAW_DOWN_CHART_KEY",
    "RETURN_FREQUENCY_CHART_KEY",
    "ROLLING_RETURNS_CHART_KEY",
    "build_active_return_chart",
    "build_benchmark_comparison_chart",
    "build_drawdown_chart",
    "build_return_frequency_chart",
    "build_rolling_returns_chart",
    "get_risk_chart_messages",
    "render_risk_charts",
    "show_risk_charts",
]