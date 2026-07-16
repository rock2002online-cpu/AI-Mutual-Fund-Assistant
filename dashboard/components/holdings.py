import streamlit as st


def show_holdings(df):

    st.subheader("Top Holdings")

    preview = df.copy()

    if "Current Value" in preview.columns:
        preview = preview.sort_values(
            by="Current Value",
            ascending=False
        )

    st.dataframe(
        preview.head(10),
        width="stretch",
        hide_index=True
    )