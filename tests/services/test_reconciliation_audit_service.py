"""Tests for reconciliation audit snapshot construction."""
import pytest
from datetime import datetime, timezone
from decimal import Decimal

from services.portfolio_reconciliation_service import (
    PortfolioReconciliationItem,
    PortfolioReconciliationResult,
)
from services.reconciliation_audit_service import (
    ReconciliationAuditService,
)


def test_build_snapshot_preserves_reconciliation_evidence() -> None:
    """Build an immutable snapshot and its fund-level evidence."""

    recorded_at = datetime(
        2026,
        7,
        24,
        12,
        0,
        tzinfo=timezone.utc,
    )

    result = PortfolioReconciliationResult(
        items=[
            PortfolioReconciliationItem(
                portfolio_id=10,
                fund_id=20,
                fund_name="Example Equity Fund",
                position_units=Decimal("100.000000"),
                transaction_units=Decimal("95.000000"),
                unit_variance=Decimal("5.000000"),
                position_cost_basis=Decimal("1000.00"),
                transaction_cost_basis=Decimal("950.00"),
                cost_basis_variance=Decimal("50.00"),
                status="unit_mismatch",
            )
        ],
        is_reconciled=False,
    )

    snapshot = ReconciliationAuditService().build_snapshot(
        portfolio_id=10,
        result=result,
        recorded_at=recorded_at,
    )

    assert snapshot.portfolio_id == 10
    assert snapshot.recorded_at is recorded_at
    assert snapshot.is_reconciled is False
    assert snapshot.total_count == 1
    assert snapshot.matched_count == 0
    assert snapshot.unit_mismatch_count == 1
    assert snapshot.missing_position_count == 0
    assert snapshot.missing_tax_lot_count == 0
    assert snapshot.cost_basis_variance_count == 0

    assert len(snapshot.items) == 1

    item = snapshot.items[0]

    assert item.fund_id == 20
    assert item.fund_name == "Example Equity Fund"
    assert item.position_units == Decimal("100.000000")
    assert item.transaction_units == Decimal("95.000000")
    assert item.unit_variance == Decimal("5.000000")
    assert item.position_cost_basis == Decimal("1000.00")
    assert item.transaction_cost_basis == Decimal("950.00")
    assert item.cost_basis_variance == Decimal("50.00")
    assert item.status == "unit_mismatch"
def test_build_snapshot_rejects_items_from_another_portfolio() -> None:
    """Every audit item must belong to the snapshot portfolio."""

    result = PortfolioReconciliationResult(
        items=[
            PortfolioReconciliationItem(
                portfolio_id=11,
                fund_id=20,
                fund_name="Wrong Portfolio Fund",
                position_units=Decimal("10.000000"),
                transaction_units=Decimal("10.000000"),
                unit_variance=Decimal("0.000000"),
                position_cost_basis=Decimal("100.00"),
                transaction_cost_basis=Decimal("100.00"),
                cost_basis_variance=Decimal("0.00"),
                status="matched",
            )
        ],
        is_reconciled=True,
    )

    with pytest.raises(
        ValueError,
        match=(
            "all reconciliation items must match "
            "portfolio_id"
        ),
    ):
        ReconciliationAuditService().build_snapshot(
            portfolio_id=10,
            result=result,
            recorded_at=datetime(
                2026,
                7,
                24,
                12,
                0,
                tzinfo=timezone.utc,
            ),
        )
def test_build_snapshot_rejects_non_positive_portfolio_id() -> None:
    """Audit snapshots require a positive portfolio identifier."""

    result = PortfolioReconciliationResult(
        items=[],
        is_reconciled=True,
    )

    with pytest.raises(
        ValueError,
        match="portfolio_id must be positive",
    ):
        ReconciliationAuditService().build_snapshot(
            portfolio_id=0,
            result=result,
            recorded_at=datetime(
                2026,
                7,
                24,
                12,
                0,
                tzinfo=timezone.utc,
            ),
        )
def test_build_snapshot_rejects_naive_recorded_at() -> None:
    """Audit timestamps must identify an absolute point in time."""

    result = PortfolioReconciliationResult(
        items=[],
        is_reconciled=True,
    )

    with pytest.raises(
        ValueError,
        match="recorded_at must be timezone-aware",
    ):
        ReconciliationAuditService().build_snapshot(
            portfolio_id=10,
            result=result,
            recorded_at=datetime(
                2026,
                7,
                24,
                12,
                0,
            ),
        )