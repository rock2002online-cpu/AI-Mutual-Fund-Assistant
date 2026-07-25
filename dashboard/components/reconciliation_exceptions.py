"""Dashboard presentation for reconciliation exceptions."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
import streamlit as st

from models.reconciliation_exception import (
    ReconciliationException,
)


_RECONCILIATION_EXCEPTION_COLUMNS = [
    "Exception ID",
    "Fund",
    "Type",
    "Status",
    "Unit Variance",
    "Opened At",
    "Investigation Started At",
]


def _format_label(
    value: str,
) -> str:
    """Convert an internal identifier into a display label."""

    return value.replace(
        "_",
        " ",
    ).title()


def _build_reconciliation_exceptions_dataframe(
    exceptions: Sequence[
        ReconciliationException
    ],
) -> pd.DataFrame:
    """Convert reconciliation exceptions into work-queue rows."""

    rows = [
        {
            "Exception ID": exception.id,
            "Fund": (
                exception.audit_item.fund_name
                if exception.audit_item.fund_name
                else f"Fund {exception.fund_id}"
            ),
            "Type": _format_label(
                exception.exception_type
            ),
            "Status": _format_label(
                exception.status
            ),
            "Unit Variance": (
                exception.audit_item.unit_variance
            ),
            "Opened At": exception.opened_at,
            "Investigation Started At": (
                exception.investigation_started_at
            ),
        }
        for exception in exceptions
    ]

    return pd.DataFrame(
        rows,
        columns=_RECONCILIATION_EXCEPTION_COLUMNS,
    )


def render_reconciliation_exceptions(
    exceptions: Sequence[
        ReconciliationException
    ],
) -> None:
    """Render the active reconciliation exception queue."""

    st.subheader(
        "🧭 Reconciliation Exception Queue"
    )

    if not exceptions:
        st.success(
            "No active reconciliation exceptions."
        )
        return

    st.dataframe(
        _build_reconciliation_exceptions_dataframe(
            exceptions
        ),
        width="stretch",
        hide_index=True,
    )