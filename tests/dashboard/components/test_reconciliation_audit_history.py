"""Tests for the reconciliation audit-history dashboard."""

from datetime import datetime, timezone

from models.reconciliation_audit import (
    ReconciliationAuditSnapshot,
)
from dashboard.components.reconciliation_audit_history import (
    _build_audit_history_dataframe,
    render_reconciliation_audit_history,
)
from unittest.mock import patch

def test_build_audit_history_dataframe_creates_display_rows() -> None:
    """Convert persisted snapshots into chronological display rows."""

    recorded_at = datetime(
        2026,
        7,
        24,
        12,
        0,
        tzinfo=timezone.utc,
    )

    snapshot = ReconciliationAuditSnapshot(
        portfolio_id=10,
        recorded_at=recorded_at,
        is_reconciled=False,
        total_count=4,
        matched_count=1,
        unit_mismatch_count=1,
        missing_position_count=1,
        missing_tax_lot_count=1,
        cost_basis_variance_count=1,
        items=[],
    )

    dataframe = _build_audit_history_dataframe(
        [snapshot]
    )

    assert dataframe.to_dict("records") == [
        {
            "Recorded At": recorded_at,
            "Status": "Unreconciled",
            "Total Funds": 4,
            "Matched": 1,
            "Unit Mismatches": 1,
            "Missing Positions": 1,
            "Missing Tax Lots": 1,
            "Cost-Basis Variances": 1,
        }
    ]
@patch(
    "dashboard.components.reconciliation_audit_history.st.dataframe"
)
@patch(
    "dashboard.components.reconciliation_audit_history.st.subheader"
)
def test_render_reconciliation_audit_history_displays_table(
    mock_subheader,
    mock_dataframe,
) -> None:
    """Render persisted reconciliation history as a table."""

    snapshot = ReconciliationAuditSnapshot(
        portfolio_id=10,
        recorded_at=datetime(
            2026,
            7,
            24,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        is_reconciled=True,
        total_count=1,
        matched_count=1,
        unit_mismatch_count=0,
        missing_position_count=0,
        missing_tax_lot_count=0,
        cost_basis_variance_count=0,
        items=[],
    )

    render_reconciliation_audit_history(
        [snapshot]
    )

    mock_subheader.assert_called_once_with(
        "🕘 Reconciliation Audit History"
    )
    mock_dataframe.assert_called_once()

    dataframe = mock_dataframe.call_args.args[0]

    assert len(dataframe) == 1
    assert mock_dataframe.call_args.kwargs == {
        "width": "stretch",
        "hide_index": True,
    }
@patch(
    "dashboard.components.reconciliation_audit_history.st.dataframe"
)
@patch(
    "dashboard.components.reconciliation_audit_history.st.info"
)
def test_render_reconciliation_audit_history_handles_empty_history(
    mock_info,
    mock_dataframe,
) -> None:
    """Explain when no reconciliation snapshots have been recorded."""

    render_reconciliation_audit_history(
        []
    )

    mock_info.assert_called_once_with(
        "No reconciliation audit history is available."
    )
    mock_dataframe.assert_not_called()