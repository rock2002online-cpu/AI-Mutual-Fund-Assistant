import streamlit as st


def render_sip_calculator():

    st.title("💰 SIP Calculator")

    st.info(
        "SIP Calculator module is under development."
    )

    amount = st.number_input(
        "Monthly SIP",
        min_value=500,
        value=5000,
        step=500
    )

    years = st.slider(
        "Investment Period (Years)",
        1,
        40,
        10
    )

    expected_return = st.slider(
        "Expected Annual Return (%)",
        1.0,
        20.0,
        12.0
    )

    st.write("Calculator logic will be connected in the next milestone.")