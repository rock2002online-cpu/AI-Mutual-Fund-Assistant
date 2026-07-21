"""
Professional Reports page.

This page integrates the Version 8.0 reporting architecture.

Responsibilities
----------------
- Retrieve the current portfolio through PortfolioService.
- Calculate performance through PortfolioPerformanceService.
- Retrieve and calculate historical analytics through existing services.
- Calculate advanced analytics through AdvancedAnalyticsService.
- Build AI presentation content from PortfolioInsights.
- Assemble the immutable PortfolioReport.
- Prepare professional PDF and Excel downloads.
- Render report previews and status information.

This page performs no portfolio, history, risk, or AI calculations directly.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import pandas as pd
import streamlit as st

# ============================================================
# Project Root
# ============================================================

PROJECT_ROOT = Path(
    __file__
).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(
        str(PROJECT_ROOT)
    )


# ============================================================
# Service Imports
# ============================================================

from dashboard.reports.ai_report import (
    AIReportView,
    build_ai_report_view,
    get_ai_metric_cards,
    get_ai_recommendation_rows,
    get_ai_report_summary,
    get_ai_summary_rows,
)
from dashboard.reports.historical_report import (
    HistoricalReportView,
    build_historical_report_view,
    get_historical_availability_rows,
    get_historical_metric_cards,
    get_historical_summary_rows,
)
from dashboard.reports.portfolio_report import (
    PortfolioReportBundle,
    build_portfolio_report_bundle,
)
from services.advanced_analytics_service import (
    AdvancedAnalyticsService,
    AdvancedAnalyticsServiceInput,
    AdvancedAnalyticsServiceResult,
)
from services.ai.insights import (
    PortfolioInsights,
)
from services.analytics.history_analytics import (
    HistoryAnalyticsInput,
    HistoryAnalyticsResult,
    HistoryAnalyticsService,
)
from services.analytics.performance import (
    PortfolioPerformanceMetrics,
    PortfolioPerformanceService,
)
from services.history.portfolio_history_service import (
    PortfolioHistoryService,
)
from services.portfolio_service import (
    PortfolioService,
)
from services.reporting.report_assets import (
    APPLICATION_NAME,
    DEFAULT_REPORT_TITLE,
)


# ============================================================
# Page Constants
# ============================================================

PAGE_TITLE: Final[str] = (
    "Professional Reports"
)

PAGE_ICON: Final[str] = "📄"

REPORT_CAPTION: Final[str] = (
    "Generate professional PDF and Excel portfolio reports "
    "using the application's existing analytics services."
)

DEFAULT_REPORT_NOTE: Final[str] = (
    "Portfolio values are based on the latest available NAV data."
)

DEFAULT_REPORT_WARNING: Final[str] = (
    "Mutual fund investments are subject to market risks."
)


# ============================================================
# Exceptions
# ============================================================


class ReportsPageError(
    RuntimeError
):
    """
    Base exception raised by Reports page orchestration.
    """


class ReportsPageDataError(
    ReportsPageError
):
    """
    Raised when required report data is unavailable.
    """


# ============================================================
# Page Result Model
# ============================================================


@dataclass(
    frozen=True,
    slots=True,
)
class ReportsPageData:
    """
    Complete Reports page data.

    Attributes:
        portfolio:
            Current portfolio dataframe.

        performance:
            Existing portfolio-performance result.

        history:
            Optional historical analytics result.

        history_view:
            Optional historical presentation model.

        advanced_analytics:
            Advanced analytics service result.

        ai_view:
            AI reporting presentation model.

        report_bundle:
            PDF and Excel report download bundle.
    """

    portfolio: pd.DataFrame
    performance: PortfolioPerformanceMetrics
    history: HistoryAnalyticsResult | None
    history_view: HistoricalReportView | None
    advanced_analytics: AdvancedAnalyticsServiceResult
    ai_view: AIReportView
    report_bundle: PortfolioReportBundle


# ============================================================
# Portfolio Adapter
# ============================================================


class _ResolvedPortfolioService:
    """
    PortfolioService-compatible adapter for an already loaded portfolio.

    The portfolio is still sourced from PortfolioService. This adapter prevents
    AdvancedAnalyticsService from performing a second portfolio retrieval
    during a single page render.
    """

    def __init__(
        self,
        portfolio: pd.DataFrame,
    ) -> None:
        if not isinstance(
            portfolio,
            pd.DataFrame,
        ):
            raise TypeError(
                "portfolio must be a pandas DataFrame."
            )

        self._portfolio = (
            portfolio.copy()
        )

    def get_portfolio(
        self,
    ) -> pd.DataFrame:
        """
        Return a defensive copy of the resolved portfolio.
        """

        return self._portfolio.copy()


# ============================================================
# Data Loading Helpers
# ============================================================


def _load_current_portfolio() -> pd.DataFrame:
    """
    Retrieve and validate the current portfolio.
    """

    portfolio_service = (
        PortfolioService()
    )

    portfolio = (
        portfolio_service
        .get_portfolio()
    )

    if not isinstance(
        portfolio,
        pd.DataFrame,
    ):
        raise ReportsPageDataError(
            "PortfolioService did not return a pandas DataFrame."
        )

    if portfolio.empty:
        raise ReportsPageDataError(
            "No portfolio holdings are available for reporting."
        )

    return portfolio


def _calculate_performance(
    portfolio: pd.DataFrame,
) -> PortfolioPerformanceMetrics:
    """
    Calculate performance through PortfolioPerformanceService.
    """

    service = (
        PortfolioPerformanceService()
    )

    return service.calculate(
        portfolio
    )


def _load_history_analytics() -> (
    HistoryAnalyticsResult | None
):
    """
    Load optional portfolio history and calculate historical analytics.

    Missing or insufficient history is treated as optional so current
    portfolio reporting can continue.
    """

    history_service = (
        PortfolioHistoryService()
    )

    try:
        history_data = (
            history_service
            .get_history(
                allow_missing=True
            )
        )

    except Exception:
        return None

    if history_data is None:
        return None

    empty_attribute = getattr(
        history_data,
        "empty",
        None,
    )

    if empty_attribute is True:
        return None

    try:
        observation_count = len(
            history_data
        )

    except TypeError:
        return None

    if observation_count == 0:
        return None

    analytics_service = (
        HistoryAnalyticsService()
    )

    try:
        return analytics_service.calculate(
            HistoryAnalyticsInput(
                history=history_data
            )
        )

    except Exception:
        return None


def _calculate_advanced_analytics(
    portfolio: pd.DataFrame,
    history: HistoryAnalyticsResult | None,
) -> AdvancedAnalyticsServiceResult:
    """
    Calculate advanced analytics through AdvancedAnalyticsService.

    Historical source data is left to PortfolioHistoryService. The completed
    HistoryAnalyticsResult is not converted back into source rows.
    """

    portfolio_provider = (
        _ResolvedPortfolioService(
            portfolio
        )
    )

    service = (
        AdvancedAnalyticsService(
            portfolio_service=(
                portfolio_provider
            )
        )
    )

    return service.calculate(
        AdvancedAnalyticsServiceInput()
    )


def _build_ai_view(
    portfolio: pd.DataFrame,
) -> AIReportView:
    """
    Build AI reporting content from PortfolioInsights.
    """

    insights = PortfolioInsights(
        portfolio
    )

    return build_ai_report_view(
        insights
    )


# ============================================================
# Notes and Warnings
# ============================================================


def _combine_messages(
    *collections: tuple[str, ...],
) -> tuple[str, ...]:
    """
    Combine message collections while preserving order and uniqueness.
    """

    combined: list[str] = []

    for collection in collections:
        for message in collection:
            normalized = str(
                message
            ).strip()

            if (
                normalized
                and normalized
                not in combined
            ):
                combined.append(
                    normalized
                )

    return tuple(
        combined
    )


def _get_advanced_warnings(
    result: AdvancedAnalyticsServiceResult,
) -> tuple[str, ...]:
    """
    Convert advanced service failures into report warnings.
    """

    warnings: list[str] = []

    for failure in result.failures:
        message = str(
            failure.message
        ).strip()

        if message:
            warnings.append(
                (
                    f"Advanced analytics "
                    f"({failure.stage}): "
                    f"{message}"
                )
            )

    if (
        result.status
        in {
            "partial",
            "unavailable",
            "failed",
        }
        and result.unavailable_metrics
    ):
        warnings.append(
            (
                "Unavailable advanced metrics: "
                f"{', '.join(result.unavailable_metrics)}."
            )
        )

    return tuple(
        warnings
    )


def _get_history_notes(
    view: HistoricalReportView | None,
) -> tuple[str, ...]:
    """
    Return historical-report notes when history is available.
    """

    if view is None:
        return (
            "Historical analytics were not available.",
        )

    return view.notes


def _get_history_warnings(
    view: HistoricalReportView | None,
) -> tuple[str, ...]:
    """
    Return historical-report warnings when history is available.
    """

    if view is None:
        return (
            "Historical analytics were not included because no "
            "usable portfolio history was available.",
        )

    return view.warnings


# ============================================================
# Report Assembly
# ============================================================


def _build_reports_page_data() -> ReportsPageData:
    """
    Build all report data using existing services.
    """

    portfolio = (
        _load_current_portfolio()
    )

    performance = (
        _calculate_performance(
            portfolio
        )
    )

    history = (
        _load_history_analytics()
    )

    history_view = (
        build_historical_report_view(
            history
        )
        if history is not None
        else None
    )

    advanced_analytics = (
        _calculate_advanced_analytics(
            portfolio,
            history,
        )
    )

    ai_view = _build_ai_view(
        portfolio
    )

    notes = _combine_messages(
        (
            DEFAULT_REPORT_NOTE,
        ),
        ai_view.notes,
        _get_history_notes(
            history_view
        ),
    )

    warnings = _combine_messages(
        (
            DEFAULT_REPORT_WARNING,
        ),
        ai_view.warnings,
        _get_history_warnings(
            history_view
        ),
        _get_advanced_warnings(
            advanced_analytics
        ),
    )

    report_bundle = (
        build_portfolio_report_bundle(
            performance,
            history=history,
            advanced_analytics=(
                advanced_analytics
            ),
            ai_summary=(
                get_ai_report_summary(
                    ai_view
                )
            ),
            notes=notes,
            warnings=warnings,
            title=DEFAULT_REPORT_TITLE,
            application_name=(
                APPLICATION_NAME
            ),
        )
    )

    return ReportsPageData(
        portfolio=portfolio,
        performance=performance,
        history=history,
        history_view=history_view,
        advanced_analytics=(
            advanced_analytics
        ),
        ai_view=ai_view,
        report_bundle=report_bundle,
    )


# ============================================================
# Streamlit Rendering Helpers
# ============================================================


def _render_metric_cards(
    rows: tuple[
        tuple[str, str],
        ...,
    ],
    *,
    columns_per_row: int = 4,
) -> None:
    """
    Render metric cards in responsive rows.
    """

    if columns_per_row <= 0:
        columns_per_row = 4

    for start_index in range(
        0,
        len(rows),
        columns_per_row,
    ):
        current_rows = rows[
            start_index:
            start_index
            + columns_per_row
        ]

        columns = st.columns(
            len(current_rows)
        )

        for column, (
            label,
            value,
        ) in zip(
            columns,
            current_rows,
        ):
            with column:
                st.metric(
                    label,
                    value,
                )


def _render_summary_table(
    rows: tuple[
        tuple[str, str],
        ...,
    ],
) -> None:
    """
    Render key-value rows as a dataframe.
    """

    dataframe = pd.DataFrame(
        rows,
        columns=[
            "Metric",
            "Value",
        ],
    )

    st.dataframe(
        dataframe,
        hide_index=True,
        width="stretch",
    )


def _render_download_section(
    bundle: PortfolioReportBundle,
) -> None:
    """
    Render PDF and Excel download buttons.
    """

    st.subheader(
        "⬇️ Download Reports"
    )

    st.caption(
        "Both exports contain the same assembled report data. "
        "PDF is optimized for presentation; Excel is optimized "
        "for further analysis."
    )

    pdf_column, excel_column = (
        st.columns(2)
    )

    with pdf_column:
        st.download_button(
            label="📕 Download PDF Report",
            data=bundle.pdf.data,
            file_name=(
                bundle.pdf.filename
            ),
            mime=bundle.pdf.mime_type,
            width="stretch",
            key="download_portfolio_pdf",
        )

        st.caption(
            "Professional print-ready portfolio report."
        )

    with excel_column:
        st.download_button(
            label="📗 Download Excel Report",
            data=bundle.excel.data,
            file_name=(
                bundle.excel.filename
            ),
            mime=bundle.excel.mime_type,
            width="stretch",
            key="download_portfolio_excel",
        )

        st.caption(
            "Structured workbook with dedicated analytics sheets."
        )


def _render_portfolio_section(
    data: ReportsPageData,
) -> None:
    """
    Render current portfolio reporting preview.
    """

    st.subheader(
        "📊 Portfolio Performance"
    )

    performance = data.performance

    rows = (
        (
            "Total Investment",
            f"₹{performance.total_investment:,.2f}",
        ),
        (
            "Current Value",
            f"₹{performance.current_value:,.2f}",
        ),
        (
            "Total Gain / Loss",
            f"₹{performance.total_gain:,.2f}",
        ),
        (
            "Absolute Return",
            (
                f"{performance.absolute_return_percentage:+,.2f}%"
            ),
        ),
        (
            "Total Holdings",
            f"{performance.total_holdings:,}",
        ),
        (
            "Profitable Holdings",
            f"{performance.profitable_holdings:,}",
        ),
        (
            "Loss-Making Holdings",
            f"{performance.loss_making_holdings:,}",
        ),
    )

    _render_metric_cards(
        rows
    )

    with st.expander(
        "View portfolio holdings",
        expanded=False,
    ):
        st.dataframe(
            data.portfolio,
            hide_index=True,
            width="stretch",
        )


def _render_historical_section(
    data: ReportsPageData,
) -> None:
    """
    Render historical analytics preview.
    """

    st.subheader(
        "📈 Historical Analytics"
    )

    if data.history_view is None:
        st.info(
            "Historical analytics are not currently available. "
            "The PDF and Excel reports still include current "
            "portfolio and AI sections."
        )

        return

    view = data.history_view

    _render_metric_cards(
        get_historical_metric_cards(
            view
        )
    )

    with st.expander(
        "Historical analytics details",
        expanded=False,
    ):
        _render_summary_table(
            get_historical_summary_rows(
                view
            )
        )

    with st.expander(
        "Metric availability",
        expanded=False,
    ):
        _render_summary_table(
            get_historical_availability_rows(
                view
            )
        )

    for warning in view.warnings:
        st.warning(
            warning
        )


def _render_ai_section(
    data: ReportsPageData,
) -> None:
    """
    Render AI portfolio reporting preview.
    """

    view = data.ai_view

    st.subheader(
        "🤖 AI Portfolio Insights"
    )

    st.markdown(
        "#### Executive Summary"
    )

    st.info(
        view.executive_summary
    )

    _render_metric_cards(
        get_ai_metric_cards(
            view
        )
    )

    holding_column, review_column = (
        st.columns(2)
    )

    with holding_column:
        st.markdown(
            "#### 🏆 Largest Holding"
        )

        st.write(
            view.top_holding.fund_name
        )

    with review_column:
        st.markdown(
            "#### 🔍 Fund to Review"
        )

        st.write(
            view.worst_holding.fund_name
        )

    with st.expander(
        "AI portfolio details",
        expanded=False,
    ):
        _render_summary_table(
            get_ai_summary_rows(
                view
            )
        )

    st.markdown(
        "#### AI Recommendations"
    )

    recommendation_rows = (
        get_ai_recommendation_rows(
            view
        )
    )

    if not recommendation_rows:
        st.info(
            "No AI recommendations were generated."
        )

    for icon, label, message in (
        recommendation_rows
    ):
        content = (
            f"{icon} **{label}** — "
            f"{message}"
        )

        if label == "Positive":
            st.success(
                content
            )

        elif label == "Critical":
            st.error(
                content
            )

        elif label == "Review":
            st.warning(
                content
            )

        else:
            st.info(
                content
            )


def _render_advanced_section(
    data: ReportsPageData,
) -> None:
    """
    Render advanced analytics availability.
    """

    result = (
        data.advanced_analytics
    )

    st.subheader(
        "🧮 Advanced Analytics"
    )

    status_columns = st.columns(
        4
    )

    status_columns[0].metric(
        "Status",
        result.status.title(),
    )

    status_columns[1].metric(
        "Available Metrics",
        len(
            result.available_metrics
        ),
    )

    status_columns[2].metric(
        "Unavailable Metrics",
        len(
            result.unavailable_metrics
        ),
    )

    status_columns[3].metric(
        "Service Failures",
        len(
            result.failures
        ),
    )

    with st.expander(
        "Advanced analytics availability",
        expanded=False,
    ):
        rows = (
            (
                "Status",
                result.status.title(),
            ),
            (
                "Available Metrics",
                (
                    ", ".join(
                        result.available_metrics
                    )
                    if result.available_metrics
                    else "None"
                ),
            ),
            (
                "Unavailable Metrics",
                (
                    ", ".join(
                        result.unavailable_metrics
                    )
                    if result.unavailable_metrics
                    else "None"
                ),
            ),
        )

        _render_summary_table(
            rows
        )

        for failure in result.failures:
            st.error(
                (
                    f"{failure.stage}: "
                    f"{failure.message}"
                )
            )


# ============================================================
# Main Page Renderer
# ============================================================


def render_reports_page() -> None:
    """
    Render the complete professional Reports page.
    """

    st.title(
        f"{PAGE_ICON} {PAGE_TITLE}"
    )

    st.caption(
        REPORT_CAPTION
    )

    st.divider()

    try:
        with st.spinner(
            "Preparing portfolio reports..."
        ):
            data = (
                _build_reports_page_data()
            )

    except ReportsPageDataError as error:
        st.error(
            str(error)
        )

        st.info(
            "Ensure the portfolio file and NAV data are available, "
            "then refresh the page."
        )

        return

    except Exception as error:
        st.error(
            "Unable to prepare the professional reports."
        )

        with st.expander(
            "Technical details",
            expanded=False,
        ):
            st.exception(
                error
            )

        return

    st.success(
        "Reports generated successfully."
    )

    _render_download_section(
        data.report_bundle
    )

    st.divider()

    tabs = st.tabs(
        [
            "Portfolio",
            "Historical Analytics",
            "AI Insights",
            "Advanced Analytics",
        ]
    )

    with tabs[0]:
        _render_portfolio_section(
            data
        )

    with tabs[1]:
        _render_historical_section(
            data
        )

    with tabs[2]:
        _render_ai_section(
            data
        )

    with tabs[3]:
        _render_advanced_section(
            data
        )

    st.divider()

    with st.expander(
        "Report notes and limitations",
        expanded=False,
    ):
        st.markdown(
            "#### Notes"
        )

        for note in (
            data
            .report_bundle
            .report
            .notes
        ):
            st.write(
                f"• {note}"
            )

        st.markdown(
            "#### Warnings"
        )

        for warning in (
            data
            .report_bundle
            .report
            .warnings
        ):
            st.warning(
                warning
            )

        st.caption(
            "Reports are generated for informational and "
            "analytical purposes only."
        )


# ============================================================
# Streamlit Entry Point
# ============================================================

render_reports_page()