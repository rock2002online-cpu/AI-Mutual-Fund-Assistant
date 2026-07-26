"""Tests for reconciliation exception assignment history persistence."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from models.fund import Fund
from models.portfolio import Portfolio
from models.reconciliation_audit import (
    ReconciliationAuditItem,
    ReconciliationAuditSnapshot,
)
from models.reconciliation_exception import (
    ReconciliationException,
)
from models.reconciliation_exception_assignment import (
    ReconciliationExceptionAssignment,
)
from repositories.reconciliation_exception_assignment_repository import (
    ReconciliationExceptionAssignmentRepository,
)


def test_add_and_get_for_exception(
    session: Session,
) -> None:
    """Persist and retrieve immutable assignment history."""

    portfolio = Portfolio(
        name="Assignment History Portfolio",
        description="Portfolio used for ownership-history testing.",
        owner_reference="assignment-history-owner",
        base_currency="INR",
        is_active=True,
    )
    fund = Fund(
        scheme_code="ASSIGNMENT001",
        name="Assignment History Fund",
        amc="Assignment AMC",
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

    audit_item = ReconciliationAuditItem(
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
    snapshot = ReconciliationAuditSnapshot(
        portfolio_id=portfolio.id,
        recorded_at=datetime(
            2026,
            7,
            26,
            9,
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
            audit_item,
        ],
    )

    session.add(snapshot)
    session.flush()

    exception = ReconciliationException(
        audit_item_id=audit_item.id,
        portfolio_id=portfolio.id,
        fund_id=fund.id,
        exception_type="unit_mismatch",
        status="open",
        opened_at=datetime(
            2026,
            7,
            26,
            9,
            5,
            tzinfo=timezone.utc,
        ),
        assigned_to="reconciliation-manager",
        assigned_at=datetime(
            2026,
            7,
            26,
            10,
            0,
            tzinfo=timezone.utc,
        ),
    )

    session.add(exception)
    session.flush()

    repository = (
        ReconciliationExceptionAssignmentRepository(
            session
        )
    )

    assignment = ReconciliationExceptionAssignment(
        exception_id=exception.id,
        previous_assigned_to="operations-team",
        assigned_to="reconciliation-manager",
        assigned_at=datetime(
            2026,
            7,
            26,
            10,
            0,
            tzinfo=timezone.utc,
        ),
        reason="Escalated for supervisory review.",
    )

    saved = repository.add(assignment)
    results = repository.get_for_exception(
        exception.id
    )

    assert saved.id is not None
    assert results == [
        assignment,
    ]