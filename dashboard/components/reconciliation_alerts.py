"""Dashboard rendering for portfolio reconciliation alerts."""

from __future__ import annotations

from collections.abc import Sequence

import streamlit as st

from services.reconciliation_alert_service import (
    ReconciliationAlert,
)


def render_reconciliation_alerts(
    alerts: Sequence[ReconciliationAlert],
) -> None:
    """Render reconciliation alerts by severity."""
    if not alerts:
        st.success(
            "No reconciliation alerts detected."
        )
        return
    for alert in alerts:
        fund_label = (
            alert.fund_name
            if alert.fund_name
            else f"Fund {alert.fund_id}"
        )

        content = (
            f"{fund_label} — "
            f"{alert.message}"
        )

        if alert.severity == "critical":
            st.error(
                content
            )
        elif alert.severity == "info":
            st.info(
                content
            )

__all__ = [
    "render_reconciliation_alerts",
]