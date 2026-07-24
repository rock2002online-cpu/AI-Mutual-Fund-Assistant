"""Tests for reconciliation audit repository operations."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from models.fund import Fund
from models.portfolio import Portfolio
from models.reconciliation_audit import (
    ReconciliationAuditItem,
    ReconciliationAuditSnapshot,
)
from repositories.reconciliation_audit_repository import (
    ReconciliationAuditRepository,
)


def test_add_and_get_latest_snapshot(
    session: Session,
) -> None:
    """Persist an audit aggregate and retrieve its latest snapshot."""

    portfolio = Portfolio(
        name="Audit Portfolio",
        description="Portfolio used for audit testing.",
        owner_reference="audit-owner",
        base_currency="INR",
        is_active=True,
    )
    fund = Fund(
        scheme_code="AUDIT001",
        name="Audit Equity Fund",
        amc="Audit AMC",
        category="Equity",
        plan="Direct",
        option="Growth",
    )

    session.add_all(
        [
            portfolio,
            fund,
        ]
    )
    session.flush()

    snapshot = ReconciliationAuditSnapshot(
        portfolio_id=portfolio.id,
        recorded_at=datetime(
            2026,
            7,
            24,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        is_reconciled=False,
        total_count=1,
        matched_count=0,
        unit_mismatch_count=1,
        missing_position_count=0,
        missing_tax_lot_count=0,
        cost_basis_variance_count=0,
        items=[
            ReconciliationAuditItem(
                fund_id=fund.id,
                fund_name=fund.name,
                position_units=Decimal("100.000000"),
                transaction_units=Decimal("95.000000"),
                unit_variance=Decimal("5.000000"),
                position_cost_basis=Decimal("1000.00"),
                transaction_cost_basis=Decimal("950.00"),
                cost_basis_variance=Decimal("50.00"),
                status="unit_mismatch",
            )
        ],
    )

    repository = ReconciliationAuditRepository(
        session
    )

    saved = repository.add(
        snapshot
    )

    latest = repository.get_latest_for_portfolio(
        portfolio.id
    )

    assert saved.id is not None
    assert latest is saved
    assert len(latest.items) == 1
    assert latest.items[0].status == "unit_mismatch"
def test_get_for_portfolio_returns_newest_first(
    session: Session,
) -> None:
    """Portfolio audit history should be ordered newest first."""

    portfolio = Portfolio(
        name="Historical Audit Portfolio",
        description="Portfolio with audit history.",
        owner_reference="audit-history-owner",
        base_currency="INR",
        is_active=True,
    )

    session.add(
        portfolio
    )
    session.flush()

    repository = ReconciliationAuditRepository(
        session
    )

    older = repository.add(
        ReconciliationAuditSnapshot(
            portfolio_id=portfolio.id,
            recorded_at=datetime(
                2026,
                7,
                23,
                12,
                0,
                tzinfo=timezone.utc,
            ),
            is_reconciled=False,
            total_count=1,
            matched_count=0,
            unit_mismatch_count=1,
            missing_position_count=0,
            missing_tax_lot_count=0,
            cost_basis_variance_count=0,
            items=[],
        )
    )

    newer = repository.add(
        ReconciliationAuditSnapshot(
            portfolio_id=portfolio.id,
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
    )

    history = repository.get_for_portfolio(
        portfolio.id
    )

    assert history == [
        newer,
        older,
    ]