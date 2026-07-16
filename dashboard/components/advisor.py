import streamlit as st

from services.ai.advisor import PortfolioAdvisor


def show_ai_advisor(df):
    """
    Render the AI Portfolio Advisor dashboard.
    """

    if df is None or df.empty:
        st.warning("No portfolio data available.")
        return

    advisor = PortfolioAdvisor(df)
    result = advisor.analyze()

    summary = result.get("summary", {})
    insights = result.get("insights", {})
    executive_summary = result.get("executive_summary", "")
    recommendations = result.get("recommendations", [])

    health_score = summary.get("health_score", 0)
    gain_percent = summary.get("gain_percent", 0)
    risk_level = summary.get("risk_level", "Not Available")
    diversification_score = summary.get("diversification_score", 0)
    concentration = summary.get("concentration", 0)

    investment = insights.get("investment", 0)
    current_value = insights.get("current_value", 0)
    profit = insights.get("profit", 0)
    largest_fund = insights.get("best_fund", "N/A")
    worst_fund = insights.get("worst_fund", "N/A")

    # --------------------------------------------------
    # Main Portfolio Metrics
    # --------------------------------------------------

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            label="Portfolio Health",
            value=f"{health_score:.0f}/100",
        )

    with col2:
        st.metric(
            label="Overall Return",
            value=f"{gain_percent:.2f}%",
        )

    with col3:
        st.metric(
            label="Risk Level",
            value=risk_level,
        )

    with col4:
        st.metric(
            label="Diversification",
            value=f"{diversification_score:.1f}/100",
        )

    with col5:
        st.metric(
            label="Largest Holding",
            value=f"{concentration:.2f}%",
        )

    st.divider()

    # --------------------------------------------------
    # AI Executive Summary
    # --------------------------------------------------

    st.subheader("🧠 AI Executive Summary")

    if executive_summary:
        st.info(executive_summary)
    else:
        st.info("Executive summary is not available.")

    st.divider()

    # --------------------------------------------------
    # Portfolio Insights
    # --------------------------------------------------

    st.subheader("📊 Portfolio Insights")

    insight_col1, insight_col2, insight_col3 = st.columns(3)

    with insight_col1:
        st.metric(
            label="Total Investment",
            value=f"₹{investment:,.2f}",
        )

    with insight_col2:
        st.metric(
            label="Current Value",
            value=f"₹{current_value:,.2f}",
        )

    with insight_col3:
        st.metric(
            label="Total Profit / Loss",
            value=f"₹{profit:,.2f}",
        )

    fund_col1, fund_col2 = st.columns(2)

    with fund_col1:
        st.success(
            f"🏆 Largest Holding\n\n{largest_fund}"
        )

    with fund_col2:
        st.warning(
            f"🔍 Fund to Review\n\n{worst_fund}"
        )

    st.divider()

    # --------------------------------------------------
    # AI Recommendation Engine
    # --------------------------------------------------

    st.subheader("🤖 AI Recommendation Engine")

    if not recommendations:
        st.info("No recommendations available.")
        return

    for recommendation in recommendations:
        st.info(recommendation)