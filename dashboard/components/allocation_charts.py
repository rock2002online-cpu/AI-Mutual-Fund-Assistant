from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st


# ============================================================
# COLUMN CONSTANTS
# ============================================================

FUND_COLUMN = "Fund"
INVESTMENT_COLUMN = "Investment"
CURRENT_VALUE_COLUMN = "Current Value"


# ============================================================
# DATA PREPARATION
# ============================================================

def _prepare_allocation_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate and prepare portfolio data for allocation charts.

    The original DataFrame is not modified.
    """

    if df is None or df.empty:
        return pd.DataFrame()

    required_columns = [
        FUND_COLUMN,
        INVESTMENT_COLUMN,
        CURRENT_VALUE_COLUMN,
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        return pd.DataFrame()

    chart_df = df[required_columns].copy()

    chart_df[INVESTMENT_COLUMN] = pd.to_numeric(
        chart_df[INVESTMENT_COLUMN],
        errors="coerce",
    ).fillna(0.0)

    chart_df[CURRENT_VALUE_COLUMN] = pd.to_numeric(
        chart_df[CURRENT_VALUE_COLUMN],
        errors="coerce",
    ).fillna(0.0)

    chart_df[FUND_COLUMN] = (
        chart_df[FUND_COLUMN]
        .fillna("Unknown Fund")
        .astype(str)
        .str.strip()
    )

    chart_df = chart_df[
        chart_df[CURRENT_VALUE_COLUMN] > 0
    ].copy()

    total_current_value = chart_df[CURRENT_VALUE_COLUMN].sum()

    if total_current_value <= 0:
        return pd.DataFrame()

    chart_df["Allocation %"] = (
        chart_df[CURRENT_VALUE_COLUMN]
        / total_current_value
        * 100
    )

    chart_df["Profit/Loss"] = (
        chart_df[CURRENT_VALUE_COLUMN]
        - chart_df[INVESTMENT_COLUMN]
    )

    chart_df = chart_df.sort_values(
        by=CURRENT_VALUE_COLUMN,
        ascending=False,
    ).reset_index(drop=True)

    return chart_df


# ============================================================
# DONUT CHART
# ============================================================

def _show_allocation_donut(chart_df: pd.DataFrame) -> None:
    """
    Display current portfolio allocation as a donut chart.
    """

    figure = px.pie(
        chart_df,
        names=FUND_COLUMN,
        values=CURRENT_VALUE_COLUMN,
        hole=0.55,
        title="Current Portfolio Allocation",
    )

    figure.update_traces(
        textposition="inside",
        textinfo="percent",
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Current Value: ₹%{value:,.2f}<br>"
            "Allocation: %{percent}<extra></extra>"
        ),
    )

    figure.update_layout(
        margin=dict(
            l=20,
            r=20,
            t=60,
            b=20,
        ),
        legend_title_text="Mutual Funds",
        height=470,
    )

    st.plotly_chart(
        figure,
        use_container_width=True,
        config={
            "displayModeBar": False,
            "responsive": True,
        },
    )


# ============================================================
# BAR CHART
# ============================================================

def _show_value_comparison_chart(chart_df: pd.DataFrame) -> None:
    """
    Compare invested amount with current value by mutual fund.
    """

    comparison_df = chart_df.melt(
        id_vars=[FUND_COLUMN],
        value_vars=[
            INVESTMENT_COLUMN,
            CURRENT_VALUE_COLUMN,
        ],
        var_name="Value Type",
        value_name="Amount",
    )

    figure = px.bar(
        comparison_df,
        x="Amount",
        y=FUND_COLUMN,
        color="Value Type",
        orientation="h",
        barmode="group",
        title="Investment vs Current Value",
        labels={
            "Amount": "Amount (₹)",
            FUND_COLUMN: "Mutual Fund",
        },
    )

    figure.update_traces(
        hovertemplate=(
            "<b>%{y}</b><br>"
            "%{fullData.name}: ₹%{x:,.2f}"
            "<extra></extra>"
        ),
    )

    figure.update_layout(
        margin=dict(
            l=20,
            r=20,
            t=60,
            b=20,
        ),
        legend_title_text="",
        yaxis={
            "categoryorder": "total ascending",
        },
        height=max(
            420,
            len(chart_df) * 65,
        ),
    )

    figure.update_xaxes(
        tickprefix="₹",
        separatethousands=True,
    )

    st.plotly_chart(
        figure,
        use_container_width=True,
        config={
            "displayModeBar": False,
            "responsive": True,
        },
    )


# ============================================================
# ALLOCATION TABLE
# ============================================================

def _show_allocation_table(chart_df: pd.DataFrame) -> None:
    """
    Display allocation details in a formatted table.
    """

    table_df = chart_df[
        [
            FUND_COLUMN,
            INVESTMENT_COLUMN,
            CURRENT_VALUE_COLUMN,
            "Profit/Loss",
            "Allocation %",
        ]
    ].copy()

    st.dataframe(
        table_df.style.format(
            {
                INVESTMENT_COLUMN: "₹{:,.2f}",
                CURRENT_VALUE_COLUMN: "₹{:,.2f}",
                "Profit/Loss": "₹{:,.2f}",
                "Allocation %": "{:.2f}%",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# PUBLIC COMPONENT
# ============================================================

def show_allocation_charts(df: pd.DataFrame) -> None:
    """
    Render all portfolio allocation visualisations.

    This component operates independently and does not change
    the portfolio DataFrame or existing AI advisor calculations.
    """

    st.subheader("📊 Portfolio Allocation")

    st.caption(
        "Understand how your portfolio is distributed across "
        "mutual funds and compare invested value with current value."
    )

    chart_df = _prepare_allocation_data(df)

    if chart_df.empty:
        st.info(
            "Portfolio allocation charts are unavailable because "
            "the required portfolio values are missing."
        )
        return

    left_column, right_column = st.columns(
        [1, 1],
        gap="large",
    )

    with left_column:
        _show_allocation_donut(chart_df)

    with right_column:
        _show_value_comparison_chart(chart_df)

    with st.expander(
        "View detailed allocation",
        expanded=False,
    ):
        _show_allocation_table(chart_df)