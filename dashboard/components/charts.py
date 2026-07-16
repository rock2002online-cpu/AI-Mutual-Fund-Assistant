import streamlit as st
import plotly.express as px


def show_charts(df):
    """
    Render responsive dashboard charts.
    """

    st.subheader("📊 Portfolio Analytics")

    if df.empty:
        st.info("No portfolio data available.")
        return

    left, right = st.columns(2)

    # ---------------------------------------------------
    # Portfolio Allocation
    # ---------------------------------------------------

    with left:

        pie = px.pie(
            df,
            names="Fund",
            values="Current Value",
            hole=0.45,
            title="Portfolio Allocation"
        )

        pie.update_traces(
            textposition="inside",
            textinfo="percent+label"
        )

        pie.update_layout(
            margin=dict(l=10, r=10, t=50, b=10),
            legend_title=None,
            height=450
        )

        st.plotly_chart(
            pie,
            width="stretch"
        )

    # ---------------------------------------------------
    # Current Value Distribution
    # ---------------------------------------------------

    with right:

        chart_df = df.sort_values(
            "Current Value",
            ascending=True
        )

        bar = px.bar(
            chart_df,
            x="Current Value",
            y="Fund",
            orientation="h",
            text_auto=".2s",
            title="Fund-wise Current Value"
        )

        bar.update_layout(
            margin=dict(l=10, r=10, t=50, b=10),
            xaxis_title="Current Value (₹)",
            yaxis_title="",
            height=450,
            showlegend=False
        )

        st.plotly_chart(
            bar,
            width="stretch"
        )