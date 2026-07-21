"""
Investment versus current value chart.

This reusable Streamlit component displays a grouped Plotly bar chart
comparing the invested amount and current market value of each holding.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


REQUIRED_COLUMNS: tuple[str, ...] = (
    "Fund",
    "Investment",
    "Current Value",
)


def render_investment_vs_current(
    portfolio: pd.DataFrame,
) -> None:
    """
    Render the investment versus current value chart.

    Args:
        portfolio:
            Portfolio dataframe returned by PortfolioService.
    """
    st.subheader("💰 Investment vs Current Value")

    st.caption(
        "Compare the invested capital with the current market value "
        "of every portfolio holding."
    )

    if not isinstance(portfolio, pd.DataFrame):
        st.error(
            "Investment comparison requires a pandas DataFrame."
        )
        return

    if portfolio.empty:
        st.info(
            "No portfolio data is available for investment comparison."
        )
        return

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in portfolio.columns
    ]

    if missing_columns:
        st.error(
            "Investment comparison cannot be displayed because the "
            "following columns are missing: "
            f"{', '.join(missing_columns)}."
        )
        return

    chart_df = portfolio.loc[
        :,
        list(REQUIRED_COLUMNS),
    ].copy()

    chart_df["Investment"] = pd.to_numeric(
        chart_df["Investment"],
        errors="coerce",
    )

    chart_df["Current Value"] = pd.to_numeric(
        chart_df["Current Value"],
        errors="coerce",
    )

    chart_df = chart_df.dropna(
        subset=[
            "Fund",
            "Investment",
            "Current Value",
        ]
    )

    if chart_df.empty:
        st.info(
            "No valid portfolio values are available for comparison."
        )
        return

    chart_df = chart_df.sort_values(
        by="Current Value",
        ascending=False,
    )

    figure = go.Figure()

    figure.add_trace(
        go.Bar(
            name="Investment",
            x=chart_df["Fund"],
            y=chart_df["Investment"],
            marker_color="#3B82F6",
            customdata=chart_df[
                [
                    "Current Value",
                ]
            ],
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Investment: ₹%{y:,.2f}<br>"
                "Current Value: ₹%{customdata[0]:,.2f}"
                "<extra></extra>"
            ),
        )
    )

    figure.add_trace(
        go.Bar(
            name="Current Value",
            x=chart_df["Fund"],
            y=chart_df["Current Value"],
            marker_color="#16A34A",
            customdata=chart_df[
                [
                    "Investment",
                ]
            ],
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Current Value: ₹%{y:,.2f}<br>"
                "Investment: ₹%{customdata[0]:,.2f}"
                "<extra></extra>"
            ),
        )
    )

    figure.update_layout(
        barmode="group",
        template="plotly_white",
        height=520,
        margin={
            "l": 30,
            "r": 30,
            "t": 30,
            "b": 150,
        },
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
        },
        xaxis_title="",
        yaxis_title="Amount (₹)",
        hovermode="x unified",
    )

    figure.update_xaxes(
        tickangle=-25,
        automargin=True,
    )

    figure.update_yaxes(
        tickprefix="₹",
        separatethousands=True,
        gridcolor="rgba(0, 0, 0, 0.08)",
    )

    st.plotly_chart(
        figure,
        width="stretch",
        config={
            "displayModeBar": False,
            "responsive": True,
        },
        key="analytics_investment_vs_current_chart",
    )