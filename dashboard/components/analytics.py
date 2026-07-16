import streamlit as st


def show_analytics(df):

    st.divider()
    st.subheader("📊 Portfolio Analytics")

    total_funds = len(df)

    avg_return = df["Return %"].mean()

    best = df.loc[df["Return %"].idxmax()]

    worst = df.loc[df["Return %"].idxmin()]

    flagged = len(df[df["Status"] != "OK"])

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Funds",
        total_funds
    )

    c2.metric(
        "Average Return",
        f"{avg_return:.2f}%"
    )

    c3.metric(
        "Best Performer",
        f"{best['Return %']:.2f}%"
    )

    c4.metric(
        "Worst Performer",
        f"{worst['Return %']:.2f}%"
    )

    c5.metric(
        "Flagged Funds",
        flagged
    )

    st.success(f"🏆 Best Fund: {best['Fund']}")

    st.warning(f"📉 Lowest Return: {worst['Fund']}")