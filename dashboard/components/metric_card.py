import streamlit as st


def show_metrics(df):
    """
    Display executive KPI metrics.
    """

    if df.empty:
        st.info("No portfolio data available.")
        return

    investment = df["Investment"].sum()
    current = df["Current Value"].sum()
    profit = df["Profit/Loss"].sum()

    returns = (profit / investment * 100) if investment else 0

    total_funds = len(df)

    healthy_funds = (
        len(df[df["Status"] == "OK"])
        if "Status" in df.columns
        else total_funds
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            label="💰 Total Investment",
            value=f"₹{investment:,.2f}",
        )

    with c2:
        st.metric(
            label="📈 Current Value",
            value=f"₹{current:,.2f}",
            delta=f"{returns:.2f}%"
        )

    with c3:
        st.metric(
            label="💹 Overall Gain/Loss",
            value=f"₹{profit:,.2f}",
            delta=f"₹{profit:,.2f}",
            delta_color="normal"
        )

    with c4:
        st.metric(
            label="📊 Active Funds",
            value=total_funds,
            delta=f"{healthy_funds}/{total_funds} Healthy",
            delta_color="off"
        )