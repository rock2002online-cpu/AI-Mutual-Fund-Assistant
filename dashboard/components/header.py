from datetime import datetime
import streamlit as st


def show_header(df):

    left, right = st.columns([4, 1])

    with left:
        st.title("📈 AI Mutual Fund Assistant")
        st.caption("Production Portfolio Analytics Dashboard")

    with right:
        st.metric(
            "Last Updated",
            datetime.now().strftime("%d %b %Y\n%H:%M")
        )