import streamlit as st

from dashboard.styles import load_css

from dashboard.components.header import show_header
from dashboard.components.metrics import show_metrics
from dashboard.components.health import show_health
from dashboard.components.charts import show_charts
from dashboard.components.holdings import show_holdings


def render_dashboard(df):

    load_css()

    show_header(df)

    st.divider()

    show_metrics(df)

    st.divider()

    show_health(df)

    st.divider()

    show_charts(df)

    st.divider()

    show_holdings(df)