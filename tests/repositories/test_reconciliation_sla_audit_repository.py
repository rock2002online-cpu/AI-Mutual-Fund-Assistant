"""Tests for reconciliation SLA audit persistence."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models.portfolio import Portfolio
from models.reconciliation_sla_audit import (
    ReconciliationSLAAudit,
)
from repositories.reconciliation_sla_audit_repository import (
    ReconciliationSLAAuditRepository,
)


def create_portfolio(
    session: Session,
    *,
    name: str,
    owner_reference: str,
) -> Portfolio:
    """Create a portfolio for SLA audit testing."""

    portfolio = Portfolio(
        name=name,
        description=(
            "Portfolio used for SLA audit testing."
        ),
        owner_reference=owner_reference,
        base_currency="INR",
        is_active=True,
    )

    session.add(portfolio)
    session.flush()

    return portfolio


def create_audit(
    *,
    portfolio_id: int,
    monitored_at: datetime,
    assignment_breach_count: int = 0,
    investigation_breach_count: int = 0,
    resolution_breach_count: int = 0,
    escalated_count: int = 0,
) -> ReconciliationSLAAudit:
    """Create an SLA audit entity."""

    return ReconciliationSLAAudit(
        portfolio_id=portfolio_id,
        monitored_at=monitored_at,
        assignment_breach_count=(
            assignment_breach_count
        ),
        investigation_breach_count=(
            investigation_breach_count
        ),
        resolution_breach_count=(
            resolution_breach_count
        ),
        escalated_count=escalated_count,
    )


def test_add_and_get_for_portfolio(
    session: Session,
) -> None:
    """Persist and retrieve SLA monitoring history."""

    portfolio = create_portfolio(
        session,
        name="SLA Audit Portfolio",
        owner_reference="sla-audit-owner",
    )
    repository = (
        ReconciliationSLAAuditRepository(
            session
        )
    )
    audit = create_audit(
        portfolio_id=portfolio.id,
        monitored_at=datetime(
            2026,
            7,
            27,
            18,
            0,
            tzinfo=timezone.utc,
        ),
        assignment_breach_count=1,
        investigation_breach_count=2,
        resolution_breach_count=3,
        escalated_count=4,
    )

    saved = repository.add(audit)
    results = repository.get_for_portfolio(
        portfolio.id
    )

    assert saved.id is not None
    assert results == [
        audit,
    ]


def test_get_for_portfolio_returns_newest_audit_first(
    session: Session,
) -> None:
    """Portfolio SLA history should be ordered newest first."""

    portfolio = create_portfolio(
        session,
        name="Ordered SLA Audit Portfolio",
        owner_reference="ordered-sla-owner",
    )
    repository = (
        ReconciliationSLAAuditRepository(
            session
        )
    )

    older_audit = create_audit(
        portfolio_id=portfolio.id,
        monitored_at=datetime(
            2026,
            7,
            27,
            9,
            0,
            tzinfo=timezone.utc,
        ),
        assignment_breach_count=1,
    )
    newer_audit = create_audit(
        portfolio_id=portfolio.id,
        monitored_at=datetime(
            2026,
            7,
            27,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        investigation_breach_count=1,
    )

    repository.add(older_audit)
    repository.add(newer_audit)

    results = repository.get_for_portfolio(
        portfolio.id
    )

    assert results == [
        newer_audit,
        older_audit,
    ]


def test_get_for_portfolio_excludes_other_portfolios(
    session: Session,
) -> None:
    """Portfolio history must not include another portfolio's audit."""

    first_portfolio = create_portfolio(
        session,
        name="First SLA Portfolio",
        owner_reference="first-sla-owner",
    )
    second_portfolio = create_portfolio(
        session,
        name="Second SLA Portfolio",
        owner_reference="second-sla-owner",
    )
    repository = (
        ReconciliationSLAAuditRepository(
            session
        )
    )

    first_audit = create_audit(
        portfolio_id=first_portfolio.id,
        monitored_at=datetime(
            2026,
            7,
            27,
            10,
            0,
            tzinfo=timezone.utc,
        ),
    )
    second_audit = create_audit(
        portfolio_id=second_portfolio.id,
        monitored_at=datetime(
            2026,
            7,
            27,
            11,
            0,
            tzinfo=timezone.utc,
        ),
    )

    repository.add(first_audit)
    repository.add(second_audit)

    results = repository.get_for_portfolio(
        first_portfolio.id
    )

    assert results == [
        first_audit,
    ]


def test_get_latest_for_portfolio_returns_latest_audit(
    session: Session,
) -> None:
    """Return the most recent SLA monitoring run."""

    portfolio = create_portfolio(
        session,
        name="Latest SLA Audit Portfolio",
        owner_reference="latest-sla-owner",
    )
    repository = (
        ReconciliationSLAAuditRepository(
            session
        )
    )

    older_audit = create_audit(
        portfolio_id=portfolio.id,
        monitored_at=datetime(
            2026,
            7,
            27,
            8,
            0,
            tzinfo=timezone.utc,
        ),
    )
    latest_audit = create_audit(
        portfolio_id=portfolio.id,
        monitored_at=datetime(
            2026,
            7,
            27,
            14,
            0,
            tzinfo=timezone.utc,
        ),
        escalated_count=2,
    )

    repository.add(older_audit)
    repository.add(latest_audit)

    result = (
        repository.get_latest_for_portfolio(
            portfolio.id
        )
    )

    assert result is latest_audit


def test_get_latest_for_portfolio_returns_none_without_history(
    session: Session,
) -> None:
    """A portfolio without monitoring history should return None."""

    portfolio = create_portfolio(
        session,
        name="Empty SLA Audit Portfolio",
        owner_reference="empty-sla-owner",
    )
    repository = (
        ReconciliationSLAAuditRepository(
            session
        )
    )

    result = (
        repository.get_latest_for_portfolio(
            portfolio.id
        )
    )

    assert result is None