import streamlit as st


def show_health(df):
    """
    Display portfolio health summary.
    """

    st.subheader("🏥 Portfolio Health")

    if df.empty:
        st.info("No portfolio data available.")
        return

    total = len(df)
    ok = len(df[df["Status"] == "OK"])
    attention = total - ok

    score = round((ok / total) * 100)

    # ----------------------------------------------------
    # Health Score
    # ----------------------------------------------------

    st.progress(score / 100)

    if score >= 90:
        st.success(f"Portfolio Health: Excellent ({score}%)")

    elif score >= 70:
        st.info(f"Portfolio Health: Good ({score}%)")

    elif score >= 50:
        st.warning(f"Portfolio Health: Needs Attention ({score}%)")

    else:
        st.error(f"Portfolio Health: Critical ({score}%)")

    # ----------------------------------------------------
    # Summary Metrics
    # ----------------------------------------------------

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Health Score", f"{score}%")

    with col2:
        st.metric("Healthy Funds", ok)

    with col3:
        st.metric("Needs Attention", attention)

    # ----------------------------------------------------
    # Portfolio Insight
    # ----------------------------------------------------

    if attention == 0:
        st.success(
            "All mutual funds have healthy NAV status. No immediate action is required."
        )

    else:
        st.warning(
            f"{attention} fund(s) require your attention. Review recent NAV updates and portfolio allocation."
        )