"""
Advanced analytics KPI presentation component.

This component renders advanced portfolio metrics including:

- CAGR
- XIRR
- Annualised volatility
- Maximum drawdown
- Sharpe ratio
- Sortino ratio
- Benchmark excess return
- Information ratio

The component contains presentation logic only.

Portfolio retrieval and financial calculations remain in:

- PortfolioService
- AdvancedAnalyticsService
- services.analytics modules
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal

import streamlit as st

from services.advanced_analytics_service import (
    AdvancedAnalyticsServiceResult,
)


# ============================================================
# Type Aliases
# ============================================================

KPIStatus = Literal[
    "positive",
    "negative",
    "neutral",
    "unavailable",
]


# ============================================================
# Presentation Models
# ============================================================


@dataclass(frozen=True, slots=True)
class AdvancedKPI:
    """
    Presentation model for one advanced analytics KPI.

    Attributes:
        label:
            User-facing KPI title.

        value:
            Formatted primary KPI value.

        delta:
            Optional supplementary text shown below the value.

        help_text:
            Optional tooltip explaining the metric.

        status:
            Semantic presentation classification.
    """

    label: str
    value: str
    delta: str | None = None
    help_text: str | None = None
    status: KPIStatus = "neutral"


# ============================================================
# Formatting Helpers
# ============================================================


def _format_percentage(
    value: float | None,
    *,
    decimal_places: int = 2,
) -> str:
    """
    Format an already percentage-based value.

    Example:
        12.345 becomes "12.35%".
    """

    if value is None:
        return "N/A"

    if not isfinite(value):
        return "N/A"

    return f"{value:,.{decimal_places}f}%"


def _format_ratio(
    value: float | None,
    *,
    decimal_places: int = 2,
) -> str:
    """
    Format a dimensionless financial ratio.
    """

    if value is None:
        return "N/A"

    if not isfinite(value):
        return "N/A"

    return f"{value:,.{decimal_places}f}"


def _format_days(
    value: int | None,
) -> str:
    """
    Format an optional duration in days.
    """

    if value is None:
        return "N/A"

    suffix = "day" if value == 1 else "days"

    return f"{value:,} {suffix}"


def _classify_signed_value(
    value: float | None,
    *,
    zero_tolerance: float = 1e-12,
) -> KPIStatus:
    """
    Classify a signed metric for presentation.
    """

    if value is None or not isfinite(value):
        return "unavailable"

    if value > zero_tolerance:
        return "positive"

    if value < -zero_tolerance:
        return "negative"

    return "neutral"


def _classify_risk_value(
    value: float | None,
) -> KPIStatus:
    """
    Classify a risk value.

    Lower risk values are not automatically labelled positive because risk
    interpretation depends on portfolio objectives.
    """

    if value is None or not isfinite(value):
        return "unavailable"

    return "neutral"


def _status_icon(
    status: KPIStatus,
) -> str:
    """
    Return a compact semantic icon.
    """

    icons: dict[KPIStatus, str] = {
        "positive": "🟢",
        "negative": "🔴",
        "neutral": "🟡",
        "unavailable": "⚪",
    }

    return icons[status]


# ============================================================
# KPI Construction
# ============================================================


def build_advanced_kpis(
    service_result: AdvancedAnalyticsServiceResult,
) -> tuple[AdvancedKPI, ...]:
    """
    Build presentation-ready advanced KPI models.

    Missing analytics metrics are represented as N/A rather than raising
    rendering errors.

    Args:
        service_result:
            Result returned by AdvancedAnalyticsService.

    Returns:
        Stable tuple of KPI presentation models.
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

    if analytics is None:
        return (
            AdvancedKPI(
                label="Portfolio CAGR",
                value="N/A",
                delta="Historical data unavailable",
                help_text=(
                    "Compound annual growth rate based on the beginning "
                    "and ending portfolio values."
                ),
                status="unavailable",
            ),
            AdvancedKPI(
                label="Portfolio XIRR",
                value="N/A",
                delta="Cash-flow history unavailable",
                help_text=(
                    "Money-weighted annual return accounting for the timing "
                    "of investments and withdrawals."
                ),
                status="unavailable",
            ),
            AdvancedKPI(
                label="Annualised Volatility",
                value="N/A",
                delta="Return history unavailable",
                help_text=(
                    "Annualised variability of periodic portfolio returns."
                ),
                status="unavailable",
            ),
            AdvancedKPI(
                label="Maximum Drawdown",
                value="N/A",
                delta="Valuation history unavailable",
                help_text=(
                    "Largest historical decline from a portfolio peak "
                    "to a subsequent trough."
                ),
                status="unavailable",
            ),
            AdvancedKPI(
                label="Sharpe Ratio",
                value="N/A",
                delta="Risk metrics unavailable",
                help_text=(
                    "Annual excess return earned per unit of total risk."
                ),
                status="unavailable",
            ),
            AdvancedKPI(
                label="Sortino Ratio",
                value="N/A",
                delta="Risk metrics unavailable",
                help_text=(
                    "Annual excess return earned per unit of downside risk."
                ),
                status="unavailable",
            ),
            AdvancedKPI(
                label="Benchmark Excess Return",
                value="N/A",
                delta="Benchmark data unavailable",
                help_text=(
                    "Annualised portfolio return minus annualised "
                    "benchmark return."
                ),
                status="unavailable",
            ),
            AdvancedKPI(
                label="Information Ratio",
                value="N/A",
                delta="Benchmark data unavailable",
                help_text=(
                    "Annualised benchmark excess return divided by "
                    "tracking error."
                ),
                status="unavailable",
            ),
        )

    cagr_percent = (
        analytics.cagr.cagr_percent
        if analytics.cagr is not None
        else None
    )

    xirr_percent = (
        analytics.xirr.annual_return_percent
        if analytics.xirr is not None
        else None
    )

    volatility_percent = (
        analytics.volatility.annualised_volatility_percent
        if analytics.volatility is not None
        else None
    )

    maximum_drawdown_percent = (
        analytics.drawdown.maximum_drawdown_percent
        if analytics.drawdown is not None
        else None
    )

    drawdown_duration = (
        analytics.drawdown.underwater_duration_days
        if analytics.drawdown is not None
        else None
    )

    sharpe_ratio = (
        analytics.risk_metrics.sharpe_ratio
        if analytics.risk_metrics is not None
        else None
    )

    sharpe_rating = (
        analytics.risk_metrics.sharpe_rating
        if analytics.risk_metrics is not None
        else None
    )

    sortino_ratio = (
        analytics.risk_metrics.sortino_ratio
        if analytics.risk_metrics is not None
        else None
    )

    sortino_rating = (
        analytics.risk_metrics.sortino_rating
        if analytics.risk_metrics is not None
        else None
    )

    benchmark_excess_return = (
        analytics.benchmark.annualised_excess_return_percent
        if analytics.benchmark is not None
        else None
    )

    benchmark_rating = (
        analytics.benchmark.rating
        if analytics.benchmark is not None
        else None
    )

    information_ratio = (
        analytics.benchmark.information_ratio
        if analytics.benchmark is not None
        else None
    )

    benchmark_name = (
        analytics.benchmark.benchmark_name
        if analytics.benchmark is not None
        else None
    )

    return (
        AdvancedKPI(
            label="Portfolio CAGR",
            value=_format_percentage(cagr_percent),
            delta=(
                "Annualised portfolio growth"
                if cagr_percent is not None
                else "Historical data unavailable"
            ),
            help_text=(
                "Compound annual growth rate based on the portfolio's "
                "beginning and ending values."
            ),
            status=_classify_signed_value(cagr_percent),
        ),
        AdvancedKPI(
            label="Portfolio XIRR",
            value=_format_percentage(xirr_percent),
            delta=(
                "Money-weighted return"
                if xirr_percent is not None
                else "Cash-flow history unavailable"
            ),
            help_text=(
                "Money-weighted annual return accounting for the timing "
                "of investments, withdrawals, and current value."
            ),
            status=_classify_signed_value(xirr_percent),
        ),
        AdvancedKPI(
            label="Annualised Volatility",
            value=_format_percentage(volatility_percent),
            delta=(
                analytics.volatility.risk_level.replace(
                    "_",
                    " ",
                ).title()
                + " risk"
                if analytics.volatility is not None
                else "Return history unavailable"
            ),
            help_text=(
                "Annualised standard deviation of periodic portfolio "
                "returns. Higher values indicate greater variability."
            ),
            status=_classify_risk_value(
                volatility_percent
            ),
        ),
        AdvancedKPI(
            label="Maximum Drawdown",
            value=_format_percentage(
                maximum_drawdown_percent
            ),
            delta=(
                f"Underwater: {_format_days(drawdown_duration)}"
                if maximum_drawdown_percent is not None
                else "Valuation history unavailable"
            ),
            help_text=(
                "Largest historical peak-to-trough decline in portfolio "
                "value."
            ),
            status=(
                "negative"
                if maximum_drawdown_percent is not None
                and maximum_drawdown_percent < 0.0
                else _classify_risk_value(
                    maximum_drawdown_percent
                )
            ),
        ),
        AdvancedKPI(
            label="Sharpe Ratio",
            value=_format_ratio(sharpe_ratio),
            delta=(
                sharpe_rating.replace("_", " ").title()
                if sharpe_rating is not None
                else "Risk metric unavailable"
            ),
            help_text=(
                "Annual excess return divided by annualised portfolio "
                "volatility."
            ),
            status=_classify_signed_value(sharpe_ratio),
        ),
        AdvancedKPI(
            label="Sortino Ratio",
            value=_format_ratio(sortino_ratio),
            delta=(
                sortino_rating.replace("_", " ").title()
                if sortino_rating is not None
                else "Downside metric unavailable"
            ),
            help_text=(
                "Annual excess return divided by annualised downside "
                "deviation."
            ),
            status=_classify_signed_value(sortino_ratio),
        ),
        AdvancedKPI(
            label="Benchmark Excess Return",
            value=_format_percentage(
                benchmark_excess_return
            ),
            delta=(
                (
                    benchmark_rating.replace(
                        "_",
                        " ",
                    ).title()
                    + (
                        f" vs {benchmark_name}"
                        if benchmark_name
                        else ""
                    )
                )
                if benchmark_rating is not None
                else "Benchmark data unavailable"
            ),
            help_text=(
                "Annualised portfolio return minus annualised benchmark "
                "return."
            ),
            status=_classify_signed_value(
                benchmark_excess_return
            ),
        ),
        AdvancedKPI(
            label="Information Ratio",
            value=_format_ratio(information_ratio),
            delta=(
                (
                    f"Relative to {benchmark_name}"
                    if benchmark_name
                    else "Risk-adjusted active return"
                )
                if information_ratio is not None
                else "Benchmark metric unavailable"
            ),
            help_text=(
                "Annualised benchmark excess return divided by tracking "
                "error."
            ),
            status=_classify_signed_value(
                information_ratio
            ),
        ),
    )


# ============================================================
# Rendering Helpers
# ============================================================


def _render_kpi(
    kpi: AdvancedKPI,
) -> None:
    """
    Render one KPI using Streamlit's metric component.
    """

    if not isinstance(kpi, AdvancedKPI):
        raise TypeError(
            "kpi must be an instance of AdvancedKPI."
        )

    delta_text = (
        f"{_status_icon(kpi.status)} {kpi.delta}"
        if kpi.delta
        else None
    )

    st.metric(
        label=kpi.label,
        value=kpi.value,
        delta=delta_text,
        delta_color="off",
        help=kpi.help_text,
        border=True,
    )


# ============================================================
# Public Rendering API
# ============================================================


def render_advanced_kpis(
    service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Render the advanced analytics KPI section.

    The component uses two rows of four cards to avoid overcrowding the
    analytics page.

    Args:
        service_result:
            Result returned by AdvancedAnalyticsService.
    """

    if not isinstance(
        service_result,
        AdvancedAnalyticsServiceResult,
    ):
        raise TypeError(
            "service_result must be an instance of "
            "AdvancedAnalyticsServiceResult."
        )

    st.subheader("Advanced Performance & Risk Metrics")

    st.caption(
        "Review annualised performance, portfolio risk, drawdowns, "
        "risk-adjusted returns, and benchmark-relative performance."
    )

    kpis = build_advanced_kpis(
        service_result
    )

    first_row = st.columns(4)

    for column, kpi in zip(
        first_row,
        kpis[:4],
        strict=True,
    ):
        with column:
            _render_kpi(kpi)

    second_row = st.columns(4)

    for column, kpi in zip(
        second_row,
        kpis[4:],
        strict=True,
    ):
        with column:
            _render_kpi(kpi)

    if service_result.status == "partial":
        st.warning(
            "Some advanced metrics could not be calculated because "
            "required historical data was incomplete or invalid."
        )

    elif service_result.status == "failed":
        st.error(
            "Advanced analytics could not be prepared. Existing portfolio "
            "features remain unaffected."
        )

    elif service_result.status == "unavailable":
        st.info(
            "Advanced metrics will become available after portfolio "
            "valuation history, cash-flow history, or benchmark data is "
            "connected."
        )


# ============================================================
# Compatibility Alias
# ============================================================


def show_advanced_kpis(
    service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Backwards-friendly alias for render_advanced_kpis().
    """

    render_advanced_kpis(
        service_result
    )


# ============================================================
# Module Exports
# ============================================================


__all__ = [
    "AdvancedKPI",
    "KPIStatus",
    "build_advanced_kpis",
    "render_advanced_kpis",
    "show_advanced_kpis",
]