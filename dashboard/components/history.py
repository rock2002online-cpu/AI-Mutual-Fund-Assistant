import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path


def show_history(project_root):
    """
    Display portfolio history and growth chart.
    """

    history_file = project_root / "data" / "portfolio_history.csv"

    if not history_file.exists():
        return

    history = pd.read_csv(history_file)

    st.divider()
    st.subheader("📈 Portfolio History")

    st.dataframe(
        history,
        width="stretch"
    )

    history["Date"] = pd.to_datetime(history["Date"])

    fig = px.line(
        history,
        x="Date",
        y="Current Value",
        markers=True,
        title="Portfolio Growth"
    )

    st.plotly_chart(
        fig,
        width="stretch"
    )