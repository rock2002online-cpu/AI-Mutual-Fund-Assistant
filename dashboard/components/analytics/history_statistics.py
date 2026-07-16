"""
Historical portfolio analytics KPI components.

This module renders summary statistics produced by
HistoryAnalyticsService.

Responsibilities
----------------
- Accept a validated HistoryAnalyticsResult.
- Format dates, currency values, percentages, and durations.
- Render historical KPI cards through Streamlit.
- Gracefully represent analytics that are not yet available.

This module performs no portfolio calculations, reads no files, and does not
retrieve data from PortfolioService or PortfolioHistoryService.
"""

from __future__ import annotations

from datetime import date
from math import isfinite
from typing import Final

import streamlit as st

from services.analytics.history_analytics import (
    HistoryAnalyticsResult,
)


# ============================================================
# Display Constants
# ============================================================

HISTORY_STATISTICS_TITLE: Final[str] = (
    "📊 Historical Portfolio Summary"
)

HISTORY_STATISTICS_CAPTION: Final[str] = (
    "Key performance, growth, risk, and coverage metrics derived from "
    "recorded portfolio valuations."
)

CURRENCY_SYMBOL: Final[str] = "₹"
UNAVAILABLE_VALUE: Final[str] = "Unavailable"


# ============================================================
# Formatting Helpers
# ============================================================


def _format_date(
    value: date,
) -> str:
    """
    Format a date for dashboard display.

    Args:
        value:
            Date value to format.

    Returns:
        Human-readable date in ``DD Mon YYYY`` format.

    Raises:
        TypeError:
            When value is not a date.
    """

    if not isinstance(value, date):
        raise TypeError(
            "value must be a date."
        )

    return value.strftime(
        "%d %b %Y"
    )


def _format_currency(
    value: float,
) -> str:
    """
    Format a numeric value as Indian-rupee currency.

    Args:
        value:
            Numeric amount.

    Returns:
        Currency-formatted string.

    Raises:
        TypeError:
            When value is not numeric.

        ValueError:
            When value is not finite.
    """

    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise TypeError(
            "value must be numeric."
        )

    numeric_value = float(
        value
    )

    if not isfinite(
        numeric_value
    ):
        raise ValueError(
            "value must be finite."
        )

    return (
        f"{CURRENCY_SYMBOL}"
        f"{numeric_value:,.2f}"
    )


def _format_percentage(
    value: float,
    *,
    include_sign: bool = False,
) -> str:
    """
    Format a percentage value.

    Args:
        value:
            Percentage-point value.

            Example:
                ``12.5`` represents ``12.5%``.

        include_sign:
            Whether positive values should include a leading plus sign.

    Returns:
        Percentage-formatted string.

    Raises:
        TypeError:
            When value is not numeric.

        ValueError:
            When value is not finite.
    """

    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise TypeError(
            "value must be numeric."
        )

    numeric_value = float(
        value
    )

    if not isfinite(
        numeric_value
    ):
        raise ValueError(
            "value must be finite."
        )

    format_specifier = (
        "+.2f"
        if include_sign
        else ".2f"
    )

    return (
        f"{numeric_value:{format_specifier}}%"
    )


def _format_integer(
    value: int,
) -> str:
    """
    Format an integer with thousands separators.

    Args:
        value:
            Integer value.

    Returns:
        Formatted integer string.

    Raises:
        TypeError:
            When value is not an integer.
    """

    if isinstance(value, bool) or not isinstance(
        value,
        int,
    ):
        raise TypeError(
            "value must be an integer."
        )

    return f"{value:,}"


def _format_duration(
    duration_days: int,
) -> str:
    """
    Format historical coverage duration.

    Durations below one year are shown in days. Longer durations include
    approximate years and remaining days, using 365 days per display year.

    This is presentation formatting only; analytics calculations continue to
    use the exact duration returned by HistoryAnalyticsService.

    Args:
        duration_days:
            Number of calendar days in the historical period.

    Returns:
        Human-readable duration string.

    Raises:
        TypeError:
            When duration_days is not an integer.

        ValueError:
            When duration_days is negative.
    """

    if isinstance(duration_days, bool) or not isinstance(
        duration_days,
        int,
    ):
        raise TypeError(
            "duration_days must be an integer."
        )

    if duration_days < 0:
        raise ValueError(
            "duration_days cannot be negative."
        )

    if duration_days < 365:
        unit = (
            "day"
            if duration_days == 1
            else "days"
        )

        return (
            f"{duration_days:,} {unit}"
        )

    years, remaining_days = divmod(
        duration_days,
        365,
    )

    year_unit = (
        "year"
        if years == 1
        else "years"
    )

    if remaining_days == 0:
        return (
            f"{years:,} {year_unit}"
        )

    day_unit = (
        "day"
        if remaining_days == 1
        else "days"
    )

    return (
        f"{years:,} {year_unit}, "
        f"{remaining_days:,} {day_unit}"
    )


# ============================================================
# Optional Analytics Formatting
# ============================================================


def _get_cagr_value(
    result: HistoryAnalyticsResult,
) -> str:
    """
    Return formatted CAGR or an unavailable label.
    """

    if result.cagr is None:
        return UNAVAILABLE_VALUE

    return _format_percentage(
        result.cagr.cagr_percent,
        include_sign=True,
    )


def _get_maximum_drawdown_value(
    result: HistoryAnalyticsResult,
) -> str:
    """
    Return formatted maximum drawdown or an unavailable label.
    """

    if result.drawdown is None:
        return UNAVAILABLE_VALUE

    return _format_percentage(
        result.drawdown.maximum_drawdown_percent
    )


def _get_annualised_volatility_value(
    result: HistoryAnalyticsResult,
) -> str:
    """
    Return formatted annualised volatility or an unavailable label.
    """

    if result.volatility is None:
        return UNAVAILABLE_VALUE

    return _format_percentage(
        result.volatility.annualised_volatility_percent
    )


def _get_growth_delta(
    result: HistoryAnalyticsResult,
) -> str:
    """
    Return the formatted absolute portfolio-value change.
    """

    prefix = (
        "+"
        if result.absolute_growth > 0
        else ""
    )

    return (
        f"{prefix}"
        f"{_format_currency(result.absolute_growth)}"
    )


# ============================================================
# Input Validation
# ============================================================


def _validate_result(
    result: HistoryAnalyticsResult,
) -> None:
    """
    Validate the component input boundary.

    Args:
        result:
            Expected HistoryAnalyticsResult.

    Raises:
        TypeError:
            When result is not a HistoryAnalyticsResult.
    """

    if not isinstance(
        result,
        HistoryAnalyticsResult,
    ):
        raise TypeError(
            "result must be a HistoryAnalyticsResult."
        )


# ============================================================
# KPI Row Renderers
# ============================================================


def _render_history_coverage_row(
    result: HistoryAnalyticsResult,
) -> None:
    """
    Render historical date-range and coverage metrics.
    """

    columns = st.columns(
        4
    )

    with columns[0]:
        st.metric(
            label="First Snapshot",
            value=_format_date(
                result.start_date
            ),
        )

    with columns[1]:
        st.metric(
            label="Latest Snapshot",
            value=_format_date(
                result.end_date
            ),
        )

    with columns[2]:
        st.metric(
            label="Observations",
            value=_format_integer(
                result.observation_count
            ),
        )

    with columns[3]:
        st.metric(
            label="History Duration",
            value=_format_duration(
                result.duration_days
            ),
        )


def _render_value_summary_row(
    result: HistoryAnalyticsResult,
) -> None:
    """
    Render historical portfolio-value summary metrics.
    """

    columns = st.columns(
        4
    )

    with columns[0]:
        st.metric(
            label="Latest Value",
            value=_format_currency(
                result.latest_value
            ),
            delta=_get_growth_delta(
                result
            ),
        )

    with columns[1]:
        st.metric(
            label="Highest Value",
            value=_format_currency(
                result.maximum_value
            ),
        )

    with columns[2]:
        st.metric(
            label="Lowest Value",
            value=_format_currency(
                result.minimum_value
            ),
        )

    with columns[3]:
        st.metric(
            label="Average Value",
            value=_format_currency(
                result.average_value
            ),
        )


def _render_performance_risk_row(
    result: HistoryAnalyticsResult,
) -> None:
    """
    Render growth, CAGR, drawdown, and volatility metrics.
    """

    columns = st.columns(
        4
    )

    with columns[0]:
        st.metric(
            label="Total Growth",
            value=_format_percentage(
                result.total_growth_percent,
                include_sign=True,
            ),
            delta=_get_growth_delta(
                result
            ),
        )

    with columns[1]:
        st.metric(
            label="Historical CAGR",
            value=_get_cagr_value(
                result
            ),
            help=(
                "Annualised portfolio-value growth between the first "
                "and latest recorded valuation."
            ),
        )

    with columns[2]:
        st.metric(
            label="Maximum Drawdown",
            value=_get_maximum_drawdown_value(
                result
            ),
            help=(
                "Largest recorded decline from a historical portfolio "
                "peak to a subsequent trough."
            ),
        )

    with columns[3]:
        st.metric(
            label="Annualised Volatility",
            value=_get_annualised_volatility_value(
                result
            ),
            help=(
                "Annualised variability of periodic portfolio-value "
                "returns."
            ),
        )


# ============================================================
# Public Component API
# ============================================================


def render_history_statistics(
    result: HistoryAnalyticsResult,
) -> None:
    """
    Render historical portfolio summary KPI cards.

    The component displays three KPI rows:

    1. Historical coverage
       - First snapshot
       - Latest snapshot
       - Observation count
       - History duration

    2. Portfolio-value statistics
       - Latest value
       - Highest value
       - Lowest value
       - Average value

    3. Historical performance and risk
       - Total growth
       - CAGR
       - Maximum drawdown
       - Annualised volatility

    Optional metrics are displayed as unavailable when the historical series
    does not contain enough observations for the corresponding analytics
    calculation.

    Args:
        result:
            Immutable result produced by HistoryAnalyticsService.

    Raises:
        TypeError:
            When result is not a HistoryAnalyticsResult.
    """

    _validate_result(
        result
    )

    st.subheader(
        HISTORY_STATISTICS_TITLE
    )

    st.caption(
        HISTORY_STATISTICS_CAPTION
    )

    _render_history_coverage_row(
        result
    )

    st.divider()

    _render_value_summary_row(
        result
    )

    st.divider()

    _render_performance_risk_row(
        result
    )


__all__ = [
    "CURRENCY_SYMBOL",
    "HISTORY_STATISTICS_CAPTION",
    "HISTORY_STATISTICS_TITLE",
    "UNAVAILABLE_VALUE",
    "render_history_statistics",
]