"""
Portfolio performance KPI components.

This module contains reusable Streamlit presentation components for
portfolio performance analytics.
"""

from __future__ import annotations

import streamlit as st

from services.analytics.performance import PortfolioPerformanceMetrics


def format_currency(value: float) -> str:
    """
    Format a number as Indian rupee currency.

    Args:
        value:
            Numeric currency value.

    Returns:
        Currency-formatted string.
    """
    sign = "-" if value < 0 else ""
    absolute_value = abs(value)

    return f"{sign}₹{absolute_value:,.2f}"


def format_percentage(value: float) -> str:
    """
    Format a number as a percentage.

    Args:
        value:
            Percentage value.

    Returns:
        Percentage-formatted string.
    """
    return f"{value:,.2f}%"


def _gain_delta(metrics: PortfolioPerformanceMetrics) -> str:
    """
    Build the gain delta displayed below the current-value KPI.

    Args:
        metrics:
            Calculated portfolio performance metrics.

    Returns:
        Formatted gain delta.
    """
    return format_currency(metrics.total_gain)


def _return_delta(metrics: PortfolioPerformanceMetrics) -> str:
    """
    Build a descriptive return delta.

    Args:
        metrics:
            Calculated portfolio performance metrics.

    Returns:
        Human-readable portfolio return status.
    """
    if metrics.is_profitable:
        return "Portfolio gain"

    if metrics.is_at_loss:
        return "Portfolio loss"

    return "No gain or loss"


def render_performance_kpis(
    metrics: PortfolioPerformanceMetrics,
) -> None:
    """
    Render professional portfolio performance KPI cards.

    Args:
        metrics:
            Calculated portfolio performance metrics.
    """
    st.subheader("Portfolio Performance Analytics")

    st.caption(
        "A consolidated view of portfolio value, gains, returns, "
        "and holding-level performance."
    )

    first_row = st.columns(4)

    with first_row[0]:
        st.metric(
            label="Total Investment",
            value=format_currency(metrics.total_investment),
            help="Total capital invested across all portfolio holdings.",
        )

    with first_row[1]:
        st.metric(
            label="Current Portfolio Value",
            value=format_currency(metrics.current_value),
            delta=_gain_delta(metrics),
            help=(
                "Current market value of the portfolio. "
                "The delta shows the total gain or loss."
            ),
        )

    with first_row[2]:
        st.metric(
            label="Total Gain / Loss",
            value=format_currency(metrics.total_gain),
            delta=format_percentage(
                metrics.absolute_return_percentage
            ),
            help=(
                "Difference between current portfolio value "
                "and total investment."
            ),
        )

    with first_row[3]:
        st.metric(
            label="Absolute Return",
            value=format_percentage(
                metrics.absolute_return_percentage
            ),
            delta=_return_delta(metrics),
            delta_color=(
                "normal"
                if metrics.absolute_return_percentage != 0
                else "off"
            ),
            help=(
                "Total portfolio gain divided by total investment, "
                "expressed as a percentage."
            ),
        )

    st.markdown("#### Holding Performance")

    second_row = st.columns(3)

    with second_row[0]:
        st.metric(
            label="Total Holdings",
            value=str(metrics.total_holdings),
            help="Total number of funds in the portfolio.",
        )

    with second_row[1]:
        st.metric(
            label="Profitable Holdings",
            value=str(metrics.profitable_holdings),
            help="Number of holdings currently generating a positive gain.",
        )

    with second_row[2]:
        st.metric(
            label="Holdings at Loss",
            value=str(metrics.loss_making_holdings),
            help="Number of holdings currently showing a negative gain.",
        )