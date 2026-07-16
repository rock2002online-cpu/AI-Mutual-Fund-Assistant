"""
Professional Portfolio Analytics page.

This module coordinates:

Phase 1:
- Portfolio data retrieval through PortfolioService
- Portfolio performance calculations
- Portfolio allocation calculations
- Reusable performance KPI components
- Portfolio allocation donut chart
- Gain distribution chart
- Investment versus current value chart

Phase 2:
- Advanced analytics service orchestration
- Advanced performance and risk KPI cards
- Drawdown and rolling-return charts
- Benchmark and active-return charts
- Return-frequency analysis

Phase 3:
- Portfolio valuation-history retrieval
- Historical portfolio-value growth chart

PortfolioService remains the single source of current portfolio data.
PortfolioHistoryService remains the single source of historical valuation data.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.components.analytics.advanced_kpis import (
    render_advanced_kpis,
)
from dashboard.components.analytics.allocation_donut import (
    render_allocation_donut,
)
from dashboard.components.analytics.gain_distribution import (
    render_gain_distribution,
)
from dashboard.components.analytics.history_charts import (
    render_history_charts,
)
from dashboard.components.analytics.history_statistics import (
    render_history_statistics,
)
from dashboard.components.analytics.investment_vs_current import (
    render_investment_vs_current,
)
from dashboard.components.analytics.performance_kpis import (
    render_performance_kpis,
)
from dashboard.components.analytics.risk_charts import (
    render_risk_charts,
)
from services.advanced_analytics_service import (
    AdvancedAnalyticsService,
    AdvancedAnalyticsServiceInput,
    AdvancedAnalyticsServiceResult,
)
from services.analytics.allocation import (
    PortfolioAllocationService,
)
from services.analytics.performance import (
    PortfolioPerformanceService,
)
from services.analytics.history_analytics import (
    HistoryAnalyticsResult,
    calculate_history_analytics,
)
from services.history.portfolio_history_service import (
    PortfolioHistoryService,
)
from services.portfolio_service import PortfolioService


# ============================================================
# Portfolio Snapshot Adapter
# ============================================================


class _LoadedPortfolioProvider:
    """
    Provide an already-loaded portfolio to AdvancedAnalyticsService.

    The analytics page retrieves current portfolio data once through
    PortfolioService. This lightweight provider allows the advanced analytics
    service to reuse that exact portfolio snapshot without making a second
    portfolio retrieval.

    PortfolioService therefore remains the single source of current portfolio
    data while both Phase 1 and Phase 2 operate on the same snapshot.
    """

    def __init__(
        self,
        portfolio: pd.DataFrame,
    ) -> None:
        """
        Initialise the provider with a validated portfolio dataframe.

        Args:
            portfolio:
                Portfolio dataframe originally returned by PortfolioService.

        Raises:
            TypeError:
                When portfolio is not a pandas DataFrame.
        """

        if not isinstance(portfolio, pd.DataFrame):
            raise TypeError(
                "portfolio must be a pandas DataFrame."
            )

        self._portfolio = portfolio

    def get_portfolio(self) -> pd.DataFrame:
        """
        Return the previously loaded portfolio snapshot.

        Returns:
            Portfolio dataframe originally returned by PortfolioService.
        """

        return self._portfolio


# ============================================================
# Current Portfolio Loading
# ============================================================


def _load_portfolio(
    portfolio_service: PortfolioService,
) -> pd.DataFrame | None:
    """
    Load current portfolio data through PortfolioService.

    Args:
        portfolio_service:
            PortfolioService instance used as the page's single source of
            current portfolio data.

    Returns:
        Portfolio dataframe when loading succeeds.
        None when loading or validation fails.
    """

    try:
        portfolio = portfolio_service.get_portfolio()

    except Exception as error:
        st.error(
            "The portfolio could not be loaded for analytics."
        )

        with st.expander(
            "Technical details"
        ):
            st.exception(error)

        return None

    if not isinstance(portfolio, pd.DataFrame):
        st.error(
            "PortfolioService returned an unsupported data format. "
            "A pandas DataFrame is required."
        )
        return None

    if portfolio.empty:
        st.info(
            "No portfolio holdings are currently available for analytics."
        )
        return None

    return portfolio


# ============================================================
# Historical Portfolio Loading
# ============================================================


def _load_portfolio_history(
    history_service: PortfolioHistoryService,
) -> pd.DataFrame | None:
    """
    Load normalized portfolio valuation history.

    PortfolioHistoryService owns file access, source-schema validation, and
    normalization. The view consumes only its public ``get_history`` method.

    A missing history file is not treated as an application failure because
    the service returns an empty canonical dataframe when ``allow_missing``
    is enabled.

    Args:
        history_service:
            PortfolioHistoryService instance used as the page's single source
            of historical portfolio valuations.

    Returns:
        Normalized dataframe containing Date and Value columns when loading
        succeeds.

        None when an unexpected loading or validation error occurs.
    """

    try:
        history = history_service.get_history(
            allow_missing=True
        )

    except Exception as error:
        st.error(
            "Historical portfolio data could not be loaded. "
            "Existing portfolio analytics remain available."
        )

        with st.expander(
            "Historical data technical details"
        ):
            st.exception(error)

        return None

    if not isinstance(history, pd.DataFrame):
        st.error(
            "PortfolioHistoryService returned an unsupported data format. "
            "A pandas DataFrame is required."
        )
        return None

    return history


# ============================================================
# Phase 1: Performance KPIs
# ============================================================


def _render_performance_section(
    portfolio: pd.DataFrame,
) -> bool:
    """
    Calculate and render portfolio performance KPI cards.

    Args:
        portfolio:
            Portfolio dataframe returned by PortfolioService.

    Returns:
        True when rendering succeeds.
        False when calculation or rendering fails.
    """

    performance_service = PortfolioPerformanceService()

    try:
        metrics = performance_service.calculate(
            portfolio
        )

    except (TypeError, ValueError) as error:
        st.error(
            str(error)
        )
        return False

    except Exception as error:
        st.error(
            "An unexpected error occurred while calculating "
            "portfolio performance analytics."
        )

        with st.expander(
            "Technical details"
        ):
            st.exception(error)

        return False

    try:
        render_performance_kpis(
            metrics
        )

    except Exception as error:
        st.error(
            "The portfolio performance KPI cards could not be displayed."
        )

        with st.expander(
            "Technical details"
        ):
            st.exception(error)

        return False

    return True


# ============================================================
# Phase 1: Allocation
# ============================================================


def _render_allocation_section(
    portfolio: pd.DataFrame,
) -> None:
    """
    Calculate and render the portfolio allocation section.

    Args:
        portfolio:
            Portfolio dataframe returned by PortfolioService.
    """

    try:
        allocation_service = PortfolioAllocationService()

        allocation = allocation_service.calculate(
            portfolio
        )

        render_allocation_donut(
            allocation
        )

    except (TypeError, ValueError) as error:
        st.error(
            str(error)
        )

    except Exception as error:
        st.error(
            "The portfolio allocation chart could not be displayed."
        )

        with st.expander(
            "Technical details"
        ):
            st.exception(error)


# ============================================================
# Phase 1: Gain Distribution
# ============================================================


def _render_gain_distribution_section(
    portfolio: pd.DataFrame,
) -> None:
    """
    Render the portfolio gain-distribution chart.

    Args:
        portfolio:
            Portfolio dataframe returned by PortfolioService.
    """

    try:
        render_gain_distribution(
            portfolio
        )

    except Exception as error:
        st.error(
            "The gain distribution chart could not be displayed."
        )

        with st.expander(
            "Technical details"
        ):
            st.exception(error)


# ============================================================
# Phase 1: Investment vs Current Value
# ============================================================


def _render_investment_vs_current_section(
    portfolio: pd.DataFrame,
) -> None:
    """
    Render the investment-versus-current-value chart.

    Args:
        portfolio:
            Portfolio dataframe returned by PortfolioService.
    """

    try:
        render_investment_vs_current(
            portfolio
        )

    except Exception as error:
        st.error(
            "The investment versus current value chart "
            "could not be displayed."
        )

        with st.expander(
            "Technical details"
        ):
            st.exception(error)


# ============================================================
# Phase 2: Advanced Analytics Calculation
# ============================================================


def _calculate_advanced_analytics(
    portfolio: pd.DataFrame,
) -> AdvancedAnalyticsServiceResult | None:
    """
    Calculate advanced analytics from the current portfolio snapshot.

    The same portfolio dataframe already retrieved through PortfolioService
    is supplied to AdvancedAnalyticsService through a lightweight provider
    adapter. This prevents duplicate current-portfolio retrieval and ensures
    Phase 1 and Phase 2 operate on an identical snapshot.

    AdvancedAnalyticsService remains responsible for obtaining any optional
    historical, cash-flow, or benchmark datasets required by its analytics
    pipeline.

    Args:
        portfolio:
            Portfolio dataframe returned by PortfolioService.

    Returns:
        AdvancedAnalyticsServiceResult when calculation completes.
        None when a service-level error prevents calculation.
    """

    portfolio_provider = _LoadedPortfolioProvider(
        portfolio
    )

    try:
        advanced_service = AdvancedAnalyticsService(
            portfolio_service=portfolio_provider
        )

        service_input = AdvancedAnalyticsServiceInput()

        return advanced_service.calculate(
            service_input
        )

    except (TypeError, ValueError) as error:
        st.error(
            "Advanced analytics could not be prepared."
        )

        with st.expander(
            "Advanced analytics technical details"
        ):
            st.exception(error)

        return None

    except Exception as error:
        st.error(
            "An unexpected error occurred while preparing "
            "advanced analytics. Existing Phase 1 analytics "
            "remain available."
        )

        with st.expander(
            "Advanced analytics technical details"
        ):
            st.exception(error)

        return None


# ============================================================
# Phase 2: Advanced KPI Rendering
# ============================================================


def _render_advanced_kpi_section(
    service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Render advanced performance and risk KPI cards.

    A rendering failure is isolated so it does not prevent Phase 1 analytics
    or the remaining Phase 2 charts from being displayed.

    Args:
        service_result:
            Result returned by AdvancedAnalyticsService.
    """

    try:
        render_advanced_kpis(
            service_result
        )

    except Exception as error:
        st.error(
            "The advanced analytics KPI cards could not be displayed."
        )

        with st.expander(
            "Advanced KPI technical details"
        ):
            st.exception(error)


# ============================================================
# Phase 2: Risk Chart Rendering
# ============================================================


def _render_risk_chart_section(
    service_result: AdvancedAnalyticsServiceResult,
) -> None:
    """
    Render advanced risk and benchmark charts.

    The risk-chart component owns its unique Streamlit Plotly keys. The view
    deliberately does not define, reuse, or override those keys.

    Args:
        service_result:
            Result returned by AdvancedAnalyticsService.
    """

    try:
        render_risk_charts(
            service_result
        )

    except Exception as error:
        st.error(
            "The advanced risk and benchmark charts "
            "could not be displayed."
        )

        with st.expander(
            "Advanced chart technical details"
        ):
            st.exception(error)


# ============================================================
# Phase 2: Section Orchestration
# ============================================================


def _render_advanced_analytics_section(
    portfolio: pd.DataFrame,
) -> None:
    """
    Calculate and render the complete Phase 2 analytics section.

    AdvancedAnalyticsService is executed exactly once. The resulting immutable
    service result is reused by both the advanced KPI and risk-chart
    components.

    Args:
        portfolio:
            Portfolio dataframe returned by PortfolioService.
    """

    service_result = _calculate_advanced_analytics(
        portfolio
    )

    if service_result is None:
        return

    _render_advanced_kpi_section(
        service_result
    )

    st.divider()

    _render_risk_chart_section(
        service_result
    )


# ============================================================
# Phase 3: Historical Analytics Rendering
# ============================================================
def _calculate_history_analytics(
    history: pd.DataFrame,
) -> HistoryAnalyticsResult | None:
    """
    Calculate historical portfolio summary and risk analytics.

    The calculation is isolated from rendering so failures in the historical
    analytics service do not affect the existing Phase 1 or Phase 2 sections.

    Args:
        history:
            Normalized Date and Value dataframe returned by
            PortfolioHistoryService.

    Returns:
        HistoryAnalyticsResult when calculation succeeds.
        None when historical analytics cannot be calculated.
    """

    if history.empty:
        return None

    try:
        return calculate_history_analytics(
            history
        )

    except (TypeError, ValueError) as error:
        st.warning(
            "Historical portfolio statistics are unavailable because "
            "the recorded history could not be validated."
        )

        with st.expander(
            "Historical calculation technical details"
        ):
            st.exception(error)

        return None

    except Exception as error:
        st.error(
            "Historical portfolio statistics could not be calculated. "
            "The existing analytics sections remain available."
        )

        with st.expander(
            "Historical calculation technical details"
        ):
            st.exception(error)

        return None

def _render_history_statistics_section(
    result: HistoryAnalyticsResult,
) -> None:
    """
    Render historical portfolio KPI cards.

    Args:
        result:
            Historical analytics result produced by
            calculate_history_analytics.
    """

    try:
        render_history_statistics(
            result
        )

    except Exception as error:
        st.error(
            "The historical portfolio summary could not be displayed."
        )

        with st.expander(
            "Historical summary technical details"
        ):
            st.exception(error)

def _render_history_statistics_section(
    result: HistoryAnalyticsResult,
) -> None:
    """
    Render historical portfolio KPI cards.

    Args:
        result:
            Historical analytics result produced by
            calculate_history_analytics.
    """

    try:
        render_history_statistics(
            result
        )

    except Exception as error:
        st.error(
            "The historical portfolio summary could not be displayed."
        )

        with st.expander(
            "Historical summary technical details"
        ):
            st.exception(error)
def _render_historical_analytics_section(
    history: pd.DataFrame,
) -> None:
    """
    Render historical portfolio analytics.

    The history-chart component owns input-boundary validation, Plotly figure
    construction, and its unique Streamlit chart key.

    A rendering error is isolated so it does not affect existing Phase 1 or
    Phase 2 analytics.

    Args:
        history:
            Normalized Date and Value dataframe returned by
            PortfolioHistoryService.
    """

    try:
        render_history_charts(
            history
        )

    except TypeError as error:
        st.error(
            "Historical portfolio analytics received invalid data."
        )

        with st.expander(
            "Historical analytics technical details"
        ):
            st.exception(error)

    except Exception as error:
        st.error(
            "The historical portfolio analytics section "
            "could not be displayed."
        )

        with st.expander(
            "Historical analytics technical details"
        ):
            st.exception(error)


# ============================================================
# Public Page API
# ============================================================


def render_analytics() -> None:
    """
    Render the complete Professional Portfolio Analytics page.

    Phase 1 sections:

    - Portfolio performance KPI cards
    - Holding performance KPI cards
    - Portfolio allocation donut chart
    - Gain distribution chart
    - Investment versus current value chart

    Phase 2 sections:

    - Advanced performance and risk KPI cards
    - Portfolio drawdown analysis
    - Rolling portfolio returns
    - Portfolio versus benchmark comparison
    - Active-return analysis
    - Positive, negative, and flat return frequency

    Phase 3 sections:

    - Historical portfolio-value growth timeline

    PortfolioService remains the single source of current portfolio data.
    PortfolioHistoryService remains the single source of historical
    portfolio-valuation data.
    """

    st.title(
        "📊 Portfolio Analytics"
    )

    st.caption(
        "Professional portfolio performance, return, risk, "
        "benchmark, investment, and historical analytics."
    )

    # -----------------------------------------------------
    # Single Current Portfolio Source
    # -----------------------------------------------------

    portfolio_service = PortfolioService()

    portfolio = _load_portfolio(
        portfolio_service
    )

    if portfolio is None:
        return

    # -----------------------------------------------------
    # Phase 1: Portfolio Performance KPIs
    # -----------------------------------------------------

    performance_rendered = _render_performance_section(
        portfolio
    )

    if not performance_rendered:
        return

    # -----------------------------------------------------
    # Phase 1: Portfolio Allocation
    # -----------------------------------------------------

    st.divider()

    _render_allocation_section(
        portfolio
    )

    # -----------------------------------------------------
    # Phase 1: Gain Distribution
    # -----------------------------------------------------

    st.divider()

    _render_gain_distribution_section(
        portfolio
    )

    # -----------------------------------------------------
    # Phase 1: Investment vs Current Value
    # -----------------------------------------------------

    st.divider()

    _render_investment_vs_current_section(
        portfolio
    )

    # -----------------------------------------------------
    # Phase 2: Advanced Analytics
    # -----------------------------------------------------

    st.divider()

    _render_advanced_analytics_section(
        portfolio
    )

    # -----------------------------------------------------
    # Phase 3: Historical Portfolio Analytics
    # -----------------------------------------------------

    history_service = PortfolioHistoryService()

    history = _load_portfolio_history(
    history_service
    )

    if history is None:
        return

    st.divider()

    history_result = _calculate_history_analytics(
    history
    )

    if history_result is not None:
        _render_history_statistics_section(
        history_result
    )

    st.divider()

    _render_historical_analytics_section(
    history
    )