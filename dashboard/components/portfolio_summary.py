"""Portfolio summary metric component."""

import pandas as pd
import streamlit as st


def show_portfolio_summary(
    portfolio: pd.DataFrame,
) -> None:
    """Render aggregate Portfolio summary metrics."""

    required_columns = [
        "Investment",
        "Current Value",
        "Profit/Loss",
        "Return %",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in portfolio.columns
    ]

    if missing_columns:
        st.error(
            f"Missing columns: {missing_columns}"
        )
        return

    investment = portfolio["Investment"].sum()
    current_value = portfolio["Current Value"].sum()
    profit = portfolio["Profit/Loss"].sum()

    return_percentage = (
        profit / investment * 100.0
        if investment
        else 0.0
    )

    total_funds = len(portfolio)
    average_return = portfolio["Return %"].mean()

    first_row = st.columns(3)

    first_row[0].metric(
        "Investment",
        f"₹{investment:,.2f}",
    )
    first_row[1].metric(
        "Current Value",
        f"₹{current_value:,.2f}",
    )
    first_row[2].metric(
        "Profit",
        f"₹{profit:,.2f}",
    )

    st.divider()

    second_row = st.columns(3)

    second_row[0].metric(
        "Return %",
        f"{return_percentage:.2f}%",
    )
    second_row[1].metric(
        "Funds",
        total_funds,
    )
    second_row[2].metric(
        "Average Return",
        f"{average_return:.2f}%",
    )