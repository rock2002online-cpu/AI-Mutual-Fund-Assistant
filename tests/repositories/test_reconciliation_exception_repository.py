"""Tests for reconciliation exception repository operations."""

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
from repositories.reconciliation_exception_repository import (
    ReconciliationExceptionRepository,
)


def test_add_and_get_by_audit_item_id(
    session: Session,
) -> None:
    """Persist an exception and retrieve it by audit evidence."""

    portfolio = Portfolio(
        name="Exception Portfolio",
        description="Portfolio used for exception testing.",
        owner_reference="exception-owner",
        base_currency="INR",
        is_active=True,
    )
    fund = Fund(
        scheme_code="EXCEPTION001",
        name="Exception Equity Fund",
        amc="Exception AMC",
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
            audit_item,
        ],
    )

    session.add(
        snapshot
    )
    session.flush()

    repository = ReconciliationExceptionRepository(
        session
    )

    exception = ReconciliationException(
        audit_item_id=audit_item.id,
        portfolio_id=portfolio.id,
        fund_id=fund.id,
        exception_type="unit_mismatch",
        status="open",
        opened_at=datetime(
            2026,
            7,
            24,
            12,
            5,
            tzinfo=timezone.utc,
        ),
    )

    saved = repository.add(
        exception
    )
    found = repository.get_by_audit_item_id(
        audit_item.id
    )

    assert saved.id is not None
    assert found is saved
    assert found.audit_item is audit_item
def test_get_for_portfolio_filters_by_status(
    session: Session,
) -> None:
    """Portfolio exception queries should support lifecycle filtering."""

    portfolio = Portfolio(
        name="Filtered Exception Portfolio",
        description="Portfolio with multiple exceptions.",
        owner_reference="filtered-exception-owner",
        base_currency="INR",
        is_active=True,
    )
    fund = Fund(
        scheme_code="EXCEPTION002",
        name="Filtered Exception Fund",
        amc="Exception AMC",
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

    open_item = ReconciliationAuditItem(
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
    resolved_item = ReconciliationAuditItem(
        fund_id=fund.id,
        fund_name=fund.name,
        position_units=Decimal("100.000000"),
        transaction_units=Decimal("0.000000"),
        unit_variance=Decimal("100.000000"),
        position_cost_basis=Decimal("1000.00"),
        transaction_cost_basis=Decimal("0.00"),
        cost_basis_variance=Decimal("1000.00"),
        status="missing_tax_lots",
    )
    snapshot = ReconciliationAuditSnapshot(
        portfolio_id=portfolio.id,
        recorded_at=datetime(
            2026,
            7,
            24,
            13,
            0,
            tzinfo=timezone.utc,
        ),
        is_reconciled=False,
        total_count=2,
        matched_count=0,
        unit_mismatch_count=1,
        missing_position_count=0,
        missing_tax_lot_count=1,
        cost_basis_variance_count=0,
        items=[
            open_item,
            resolved_item,
        ],
    )

    session.add(
        snapshot
    )
    session.flush()

    repository = ReconciliationExceptionRepository(
        session
    )

    open_exception = repository.add(
        ReconciliationException(
            audit_item_id=open_item.id,
            portfolio_id=portfolio.id,
            fund_id=fund.id,
            exception_type="unit_mismatch",
            status="open",
            opened_at=datetime(
                2026,
                7,
                24,
                13,
                5,
                tzinfo=timezone.utc,
            ),
        )
    )
    repository.add(
        ReconciliationException(
            audit_item_id=resolved_item.id,
            portfolio_id=portfolio.id,
            fund_id=fund.id,
            exception_type="missing_tax_lots",
            status="resolved",
            opened_at=datetime(
                2026,
                7,
                24,
                13,
                10,
                tzinfo=timezone.utc,
            ),
            resolved_at=datetime(
                2026,
                7,
                24,
                14,
                0,
                tzinfo=timezone.utc,
            ),
            resolution_notes="Missing tax lots were rebuilt.",
        )
    )

    results = repository.get_for_portfolio(
        portfolio.id,
        status="open",
    )

    assert results == [
        open_exception,
    ]
    active_results = (
        repository.get_active_for_portfolio(
            portfolio.id
        )
    )

    assert active_results == [
        open_exception,
    ]