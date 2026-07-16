import streamlit as st


def render_fund_explorer():

    st.title("🔍 Fund Explorer")

    st.info(
        "Fund Explorer will allow you to search and analyze any mutual fund."
    )

    st.markdown("### Planned Features")

    st.checkbox("Latest NAV", disabled=True)
    st.checkbox("Historical NAV", disabled=True)
    st.checkbox("Fund Category", disabled=True)
    st.checkbox("Fund Manager", disabled=True)
    st.checkbox("Returns Analysis", disabled=True)
    st.checkbox("Risk Metrics", disabled=True)