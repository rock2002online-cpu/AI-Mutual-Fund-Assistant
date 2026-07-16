import streamlit as st

from services.portfolio_service import PortfolioService

from dashboard.components.portfolio_summary import show_portfolio_summary
from dashboard.components.portfolio import show_portfolio
from dashboard.components.history import show_history


def render_portfolio():

    st.title("📂 Portfolio")

    st.error("VIEW LOADED")

    service = PortfolioService()

    df = service.get_portfolio()

    st.write(df.head())

    show_portfolio_summary(df)

    st.success("SUMMARY FINISHED")

    show_portfolio(df)

    show_history(service.loader.project_root)