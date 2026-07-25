"""Tests for the reconciliation exceptions dashboard."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch
from dashboard.components.reconciliation_exceptions import (
    _build_reconciliation_exceptions_dataframe,
)
from models.reconciliation_audit import (
    ReconciliationAuditItem,
)
from models.reconciliation_exception import (
    ReconciliationException,
)
from dashboard.components.reconciliation_exceptions import (
    _build_reconciliation_exceptions_dataframe,
    render_reconciliation_exceptions,
)

def test_build_exception_dataframe_creates_work_queue_rows() -> None:
    """Convert active exceptions into display-ready rows."""

    opened_at = datetime(
        2026,
        7,
        25,
        10,
        0,
        tzinfo=timezone.utc,
    )
    started_at = datetime(
        2026,
        7,
        25,
        11,
        0,
        tzinfo=timezone.utc,
    )
    audit_item = ReconciliationAuditItem(
        id=101,
        snapshot_id=50,
        fund_id=201,
        fund_name="Exception Equity Fund",
        position_units=Decimal("100.000000"),
        transaction_units=Decimal("95.000000"),
        unit_variance=Decimal("5.000000"),
        position_cost_basis=Decimal("1000.00"),
        transaction_cost_basis=Decimal("950.00"),
        cost_basis_variance=Decimal("50.00"),
        status="unit_mismatch",
    )
    exception = ReconciliationException(
        id=1,
        audit_item_id=audit_item.id,
        portfolio_id=10,
        fund_id=audit_item.fund_id,
        exception_type="unit_mismatch",
        status="investigating",
        opened_at=opened_at,
        investigation_started_at=started_at,
        audit_item=audit_item,
    )

    dataframe = (
        _build_reconciliation_exceptions_dataframe(
            [
                exception,
            ]
        )
    )

    assert dataframe.to_dict("records") == [
        {
            "Exception ID": 1,
            "Fund": "Exception Equity Fund",
            "Type": "Unit Mismatch",
            "Status": "Investigating",
            "Unit Variance": Decimal("5.000000"),
            "Opened At": opened_at,
            "Investigation Started At": started_at,
        }
    ]
@patch(
    "dashboard.components.reconciliation_exceptions.st.dataframe"
)
@patch(
    "dashboard.components.reconciliation_exceptions.st.subheader"
)
def test_render_reconciliation_exceptions_displays_work_queue(
    mock_subheader,
    mock_dataframe,
) -> None:
    """Active reconciliation exceptions should render as a table."""

    audit_item = ReconciliationAuditItem(
        id=102,
        snapshot_id=51,
        fund_id=202,
        fund_name="Rendered Exception Fund",
        position_units=Decimal("80.000000"),
        transaction_units=Decimal("75.000000"),
        unit_variance=Decimal("5.000000"),
        position_cost_basis=Decimal("800.00"),
        transaction_cost_basis=Decimal("750.00"),
        cost_basis_variance=Decimal("50.00"),
        status="unit_mismatch",
    )
    exception = ReconciliationException(
        id=2,
        audit_item_id=audit_item.id,
        portfolio_id=10,
        fund_id=audit_item.fund_id,
        exception_type="unit_mismatch",
        status="open",
        opened_at=datetime(
            2026,
            7,
            25,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        audit_item=audit_item,
    )

    render_reconciliation_exceptions(
        [
            exception,
        ]
    )

    mock_subheader.assert_called_once_with(
        "🧭 Reconciliation Exception Queue"
    )
    mock_dataframe.assert_called_once()

    dataframe = mock_dataframe.call_args.args[0]

    assert len(dataframe) == 1
    assert mock_dataframe.call_args.kwargs == {
        "width": "stretch",
        "hide_index": True,
    }
@patch(
    "dashboard.components.reconciliation_exceptions.st.dataframe"
)
@patch(
    "dashboard.components.reconciliation_exceptions.st.success"
)
def test_render_reconciliation_exceptions_handles_empty_queue(
    mock_success,
    mock_dataframe,
) -> None:
    """An empty active queue should confirm operational health."""

    render_reconciliation_exceptions(
        []
    )

    mock_success.assert_called_once_with(
        "No active reconciliation exceptions."
    )
    mock_dataframe.assert_not_called()