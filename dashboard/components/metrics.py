import streamlit as st


def show_metrics(df):
    """Display executive KPI metrics."""

    investment = df["Investment"].sum()
    current = df["Current Value"].sum()
    profit = df["Profit/Loss"].sum()
    returns = (profit / investment * 100) if investment else 0

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        label="💰 Investment",
        value=f"₹{investment:,.2f}",
    )

    c2.metric(
        label="📈 Current Value",
        value=f"₹{current:,.2f}",
        delta=f"{returns:.2f}%"
    )

    c3.metric(
        label="💹 Profit / Loss",
        value=f"₹{profit:,.2f}",
    )

    c4.metric(
        label="📊 Portfolio Return",
        value=f"{returns:.2f}%"
    )