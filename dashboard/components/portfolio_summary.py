import streamlit as st


def show_portfolio_summary(df):

    # DEBUG
    st.success("✅ Portfolio Summary Component Loaded")

    st.write("Columns in DataFrame:")
    st.write(df.columns.tolist())

    required_columns = [
        "Investment",
        "Current Value",
        "Profit/Loss",
        "Return %"
    ]

    missing = [col for col in required_columns if col not in df.columns]

    if missing:
        st.error(f"Missing columns: {missing}")
        return

    investment = df["Investment"].sum()
    current = df["Current Value"].sum()
    profit = df["Profit/Loss"].sum()

    returns = (profit / investment) * 100 if investment else 0

    total_funds = len(df)

    avg_return = df["Return %"].mean()

    c1, c2, c3 = st.columns(3)

    c1.metric("Investment", f"₹{investment:,.2f}")

    c2.metric("Current Value", f"₹{current:,.2f}")

    c3.metric("Profit", f"₹{profit:,.2f}")

    st.divider()

    c4, c5, c6 = st.columns(3)

    c4.metric("Return %", f"{returns:.2f}%")

    c5.metric("Funds", total_funds)

    c6.metric("Average Return", f"{avg_return:.2f}%")