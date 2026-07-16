import streamlit as st


def highlight_status(row):
    """
    Color rows based on portfolio status.
    """

    if row["Status"] == "OK":
        color = "#d4edda"      # Light Green
    else:
        color = "#f8d7da"      # Light Red

    return [f"background-color: {color}"] * len(row)


def show_portfolio(df):
    """
    Display portfolio table.
    """

    st.divider()
    st.subheader("📋 Portfolio")

    st.dataframe(
        df.style.apply(
            highlight_status,
            axis=1
        ),
        width="stretch"
    )