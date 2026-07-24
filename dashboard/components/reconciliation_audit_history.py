"""Dashboard presentation for reconciliation audit history."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
import streamlit as st
from models.reconciliation_audit import (
    ReconciliationAuditSnapshot,
)


_AUDIT_HISTORY_COLUMNS = [
    "Recorded At",
    "Status",
    "Total Funds",
    "Matched",
    "Unit Mismatches",
    "Missing Positions",
    "Missing Tax Lots",
    "Cost-Basis Variances",
]


def _build_audit_history_dataframe(
    snapshots: Sequence[
        ReconciliationAuditSnapshot
    ],
) -> pd.DataFrame:
    """Convert audit snapshots into display-ready rows."""

    rows = [
        {
            "Recorded At": snapshot.recorded_at,
            "Status": (
                "Reconciled"
                if snapshot.is_reconciled
                else "Unreconciled"
            ),
            "Total Funds": snapshot.total_count,
            "Matched": snapshot.matched_count,
            "Unit Mismatches": (
                snapshot.unit_mismatch_count
            ),
            "Missing Positions": (
                snapshot.missing_position_count
            ),
            "Missing Tax Lots": (
                snapshot.missing_tax_lot_count
            ),
            "Cost-Basis Variances": (
                snapshot.cost_basis_variance_count
            ),
        }
        for snapshot in snapshots
    ]

    return pd.DataFrame(
        rows,
        columns=_AUDIT_HISTORY_COLUMNS,
    )
def render_reconciliation_audit_history(
    snapshots: Sequence[
        ReconciliationAuditSnapshot
    ],
) -> None:
    """Render persisted reconciliation audit history."""

    st.subheader(
        "🕘 Reconciliation Audit History"
    )
    if not snapshots:
        st.info(
            "No reconciliation audit history is available."
        )
        return
    st.dataframe(
        _build_audit_history_dataframe(
            snapshots
        ),
        width="stretch",
        hide_index=True,
    )


__all__ = [
    "_build_audit_history_dataframe",
    "render_reconciliation_audit_history",
]