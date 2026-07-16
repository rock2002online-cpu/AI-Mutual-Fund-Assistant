import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT))

from services.portfolio_service import PortfolioService
from views.dashboard_view import render_dashboard


st.set_page_config(
    page_title="AI Mutual Fund Assistant",
    page_icon="📈",
    layout="wide"
)


def main():

    service = PortfolioService()

    df = service.get_portfolio()

    render_dashboard(df)


if __name__ == "__main__":
    main()