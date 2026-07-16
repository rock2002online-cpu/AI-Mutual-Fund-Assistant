from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from dashboard.components.allocation_charts import (
    show_allocation_charts,
)
from services.ai.insights import PortfolioInsights
from services.portfolio_service import PortfolioService


# ============================================================
# FORMATTING HELPERS
# ============================================================

def _to_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Safely convert a value to float.
    """

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _format_currency(value: Any) -> str:
    """
    Format a value as Indian rupees.
    """

    amount = _to_float(value)

    return f"₹{amount:,.2f}"


# ============================================================
# PORTFOLIO VALIDATION
# ============================================================

def _validate_portfolio(
    df: pd.DataFrame | None,
) -> bool:
    """
    Validate portfolio data before analysis.
    """

    if df is None or df.empty:
        st.warning(
            "Portfolio data is unavailable. "
            "Please verify your portfolio file."
        )
        return False

    required_columns = {
        "Fund",
        "Current Value",
    }

    missing_columns = required_columns.difference(
        df.columns
    )

    if missing_columns:
        missing_text = ", ".join(
            sorted(missing_columns)
        )

        st.error(
            "The portfolio is missing required columns: "
            f"{missing_text}"
        )
        return False

    has_investment_column = (
        "Investment" in df.columns
        or "Invested Amount" in df.columns
    )

    if not has_investment_column:
        st.error(
            "The portfolio must contain either the "
            "'Investment' or 'Invested Amount' column."
        )
        return False

    return True


# ============================================================
# PORTFOLIO HEALTH
# ============================================================

def _render_portfolio_health(
    summary: dict[str, Any],
) -> None:
    """
    Render portfolio health metrics.
    """

    st.subheader("Portfolio Health")

    health_score = _to_float(
        summary.get("health_score")
    )

    overall_return = _to_float(
        summary.get("gain_percent")
    )

    diversification_score = _to_float(
        summary.get("diversification_score")
    )

    concentration = _to_float(
        summary.get("concentration")
    )

    risk_level = str(
        summary.get(
            "risk_level",
            "N/A",
        )
    )

    first_row = st.columns(3)

    with first_row[0]:
        st.metric(
            label="Portfolio Health",
            value=f"{health_score:.0f}/100",
        )

    with first_row[1]:
        st.metric(
            label="Overall Return",
            value=f"{overall_return:.2f}%",
        )

    with first_row[2]:
        st.metric(
            label="Risk Level",
            value=risk_level,
        )

    second_row = st.columns(2)

    with second_row[0]:
        st.metric(
            label="Diversification",
            value=(
                f"{diversification_score:.1f}/100"
            ),
        )

    with second_row[1]:
        st.metric(
            label="Largest Holding",
            value=f"{concentration:.2f}%",
        )


# ============================================================
# EXECUTIVE SUMMARY
# ============================================================

def _render_executive_summary(
    summary: dict[str, Any],
) -> None:
    """
    Render the executive summary.
    """

    st.subheader("🧠 AI Executive Summary")

    executive_summary = str(
        summary.get(
            "executive_summary",
            (
                "Portfolio summary is currently "
                "unavailable."
            ),
        )
    )

    st.info(executive_summary)


# ============================================================
# PORTFOLIO INSIGHTS
# ============================================================

def _render_portfolio_insights(
    summary: dict[str, Any],
    insights: dict[str, Any],
) -> None:
    """
    Render portfolio financial metrics and holdings.
    """

    st.subheader("📊 Portfolio Insights")

    invested_value = _to_float(
        summary.get("invested_value")
    )

    current_value = _to_float(
        summary.get("portfolio_value")
    )

    profit_loss = _to_float(
        summary.get("gain_loss")
    )

    metric_columns = st.columns(3)

    with metric_columns[0]:
        st.metric(
            label="Total Investment",
            value=_format_currency(
                invested_value
            ),
        )

    with metric_columns[1]:
        st.metric(
            label="Current Value",
            value=_format_currency(
                current_value
            ),
        )

    with metric_columns[2]:
        st.metric(
            label="Total Profit / Loss",
            value=_format_currency(
                profit_loss
            ),
        )

    holding_columns = st.columns(2)

    with holding_columns[0]:
        st.markdown("#### 🏆 Largest Holding")

        st.write(
            insights.get(
                "best_fund",
                "N/A",
            )
        )

    with holding_columns[1]:
        st.markdown("#### 🔍 Fund to Review")

        st.write(
            insights.get(
                "worst_fund",
                "N/A",
            )
        )


# ============================================================
# RECOMMENDATIONS
# ============================================================

def _render_recommendation(
    recommendation: Any,
) -> None:
    """
    Render one portfolio recommendation.
    """

    if isinstance(recommendation, dict):
        recommendation_type = str(
            recommendation.get(
                "type",
                "info",
            )
        ).lower()

        message = str(
            recommendation.get(
                "message",
                "Recommendation unavailable.",
            )
        )

    else:
        recommendation_type = "info"
        message = str(recommendation)

    if recommendation_type == "success":
        st.success(message)

    elif recommendation_type == "warning":
        st.warning(message)

    elif recommendation_type == "error":
        st.error(message)

    else:
        st.info(message)


def _render_recommendations(
    summary: dict[str, Any],
) -> None:
    """
    Render the AI recommendation section.
    """

    st.subheader("🤖 AI Recommendation Engine")

    recommendations = summary.get(
        "recommendations",
        [],
    )

    if isinstance(recommendations, str):
        recommendations = [recommendations]

    if not recommendations:
        st.info(
            "No portfolio recommendations are "
            "currently available."
        )
        return

    for recommendation in recommendations:
        _render_recommendation(
            recommendation
        )


# ============================================================
# MAIN VIEW
# ============================================================

def render_ai_advisor() -> None:
    """
    Render the complete AI Portfolio Advisor page.
    """

    st.title("🤖 AI Portfolio Advisor")

    st.caption(
        "AI-powered portfolio health, allocation "
        "analysis and actionable investment insights."
    )

    # --------------------------------------------------------
    # LOAD PORTFOLIO
    # --------------------------------------------------------

    try:
        service = PortfolioService()
        df = service.get_portfolio()

    except Exception as error:
        st.error(
            "The portfolio could not be loaded."
        )

        with st.expander(
            "View technical details"
        ):
            st.exception(error)

        return

    if not _validate_portfolio(df):
        return

    # --------------------------------------------------------
    # GENERATE INSIGHTS
    # --------------------------------------------------------

    try:
        engine = PortfolioInsights(df)

        summary = engine.summary()

        portfolio_insights = (
            engine.portfolio_insights()
        )

    except Exception as error:
        st.error(
            "Portfolio insights could not be "
            "generated."
        )

        with st.expander(
            "View technical details"
        ):
            st.exception(error)

        return

    # --------------------------------------------------------
    # PORTFOLIO HEALTH
    # --------------------------------------------------------

    _render_portfolio_health(summary)

    # --------------------------------------------------------
    # EXECUTIVE SUMMARY
    # --------------------------------------------------------

    st.divider()

    _render_executive_summary(summary)

    # --------------------------------------------------------
    # PORTFOLIO INSIGHTS
    # --------------------------------------------------------

    st.divider()

    _render_portfolio_insights(
        summary,
        portfolio_insights,
    )

    # --------------------------------------------------------
    # PORTFOLIO ALLOCATION
    # --------------------------------------------------------

    st.divider()

    show_allocation_charts(df)

    # --------------------------------------------------------
    # AI RECOMMENDATIONS
    # --------------------------------------------------------

    st.divider()

    _render_recommendations(summary)


if __name__ == "__main__":
    render_ai_advisor()