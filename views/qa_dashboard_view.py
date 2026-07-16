import time
import streamlit as st

from services.portfolio_service import PortfolioService
from services.system_checks import SystemChecks
from dashboard.qa.data_checks import validate_portfolio


def render_qa_dashboard():
    """
    AI Mutual Fund Assistant
    QA Dashboard
    """

    start = time.perf_counter()

    # =====================================================
    # HEADER
    # =====================================================

    st.title("🧪 QA Dashboard")

    st.caption(
        "AI Mutual Fund Assistant • Development & Validation"
    )

    st.success("Application Running Successfully")

    # =====================================================
    # APPLICATION INFORMATION
    # =====================================================

    st.divider()

    st.subheader("📋 Application Information")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "Version",
            "2.1.0"
        )

    with c2:
        st.metric(
            "Environment",
            "Development"
        )

    with c3:
        st.metric(
            "Status",
            "Running"
        )

    # =====================================================
    # PORTFOLIO VALIDATION
    # =====================================================

    st.divider()

    st.subheader("📊 Portfolio Validation")

    try:

        service = PortfolioService()

        df = service.get_portfolio()

        results = validate_portfolio(df)

        c1, c2 = st.columns(2)

        with c1:
            st.metric(
                "Passed",
                results["passed"]
            )

        with c2:
            st.metric(
                "Failed",
                results["failed"]
            )

        score = (
            results["passed"]
            / (results["passed"] + results["failed"])
        ) * 100

        st.progress(score / 100)

        st.caption(
            f"Validation Score : {score:.1f}%"
        )

        st.divider()

        for name, status in results["checks"]:

            if status:

                st.success(f"✅ {name}")

            else:

                st.error(f"❌ {name}")

    except Exception as e:

        st.error("Portfolio Validation Failed")

        st.exception(e)

        return

    # =====================================================
    # PORTFOLIO STATISTICS
    # =====================================================

    st.divider()

    st.subheader("📈 Portfolio Statistics")

    invested = df["Investment"].sum()

    current = df["Current Value"].sum()

    profit = current - invested

    returns = (
        profit / invested * 100
        if invested > 0
        else 0
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "Funds",
            len(df)
        )

    with c2:
        st.metric(
            "Investment",
            f"₹{invested:,.2f}"
        )

    with c3:
        st.metric(
            "Current Value",
            f"₹{current:,.2f}"
        )

    c4, c5 = st.columns(2)

    with c4:
        st.metric(
            "Profit / Loss",
            f"₹{profit:,.2f}",
            delta=f"{returns:.2f}%"
        )

    with c5:

        if returns >= 0:

            st.success(
                f"Overall Return : {returns:.2f}%"
            )

        else:

            st.error(
                f"Overall Return : {returns:.2f}%"
            )

    # =====================================================
    # BACKEND HEALTH
    # =====================================================

    st.divider()

    st.subheader("⚙ Backend System Health")

    try:

        system = SystemChecks()

        system.run()

        health = system.summary()

        c1, c2, c3 = st.columns(3)

        with c1:
            st.metric(
                "Passed",
                health["passed"]
            )

        with c2:
            st.metric(
                "Failed",
                health["failed"]
            )

        with c3:
            st.metric(
                "Health Score",
                f"{health['score']}%"
            )

        st.progress(
            health["score"] / 100
        )

        st.divider()

        for name, status in health["checks"]:

            if status:

                st.success(
                    f"✅ {name}"
                )

            else:

                st.error(
                    f"❌ {name}"
                )

    except Exception as e:

        st.error("Backend Health Check Failed")

        st.exception(e)

    # =====================================================
    # DASHBOARD PERFORMANCE
    # =====================================================

    elapsed = time.perf_counter() - start

    st.divider()

    st.subheader("⚡ Dashboard Performance")

    c1, c2 = st.columns(2)

    with c1:

        st.metric(
            "Render Time",
            f"{elapsed:.3f} sec"
        )

    with c2:

        if elapsed < 1:

            st.success("Excellent Performance")

        elif elapsed < 3:

            st.warning("Average Performance")

        else:

            st.error("Slow Performance")

    st.caption(
        "AI Mutual Fund Assistant QA Dashboard v2.1"
    )