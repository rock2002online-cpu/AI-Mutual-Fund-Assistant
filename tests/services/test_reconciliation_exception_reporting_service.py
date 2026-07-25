"""Tests for reconciliation exception reporting."""

from datetime import datetime, timezone
from unittest.mock import Mock

from models.reconciliation_exception import (
    ReconciliationException,
)
from repositories.reconciliation_exception_repository import (
    ReconciliationExceptionRepository,
)
from services.reconciliation_exception_reporting_service import (
    ReconciliationExceptionReportingService,
)


def test_summarize_returns_lifecycle_counts() -> None:
    """Exception summaries should count every lifecycle status."""

    opened_at = datetime(
        2026,
        7,
        25,
        10,
        0,
        tzinfo=timezone.utc,
    )
    exceptions = [
        ReconciliationException(
            id=1,
            audit_item_id=101,
            portfolio_id=10,
            fund_id=201,
            exception_type="unit_mismatch",
            status="open",
            opened_at=opened_at,
        ),
        ReconciliationException(
            id=2,
            audit_item_id=102,
            portfolio_id=10,
            fund_id=202,
            exception_type="missing_position",
            status="investigating",
            opened_at=opened_at,
            investigation_started_at=opened_at,
        ),
        ReconciliationException(
            id=3,
            audit_item_id=103,
            portfolio_id=10,
            fund_id=203,
            exception_type="missing_tax_lots",
            status="resolved",
            opened_at=opened_at,
            investigation_started_at=opened_at,
            resolved_at=opened_at,
            resolution_notes="Tax lots were rebuilt.",
        ),
    ]

    repository = Mock(
        spec=ReconciliationExceptionRepository,
    )
    repository.get_for_portfolio.return_value = (
        exceptions
    )

    service = ReconciliationExceptionReportingService(
        repository=repository,
    )

    summary = service.summarize(
        portfolio_id=10
    )

    assert summary.total_count == 3
    assert summary.open_count == 1
    assert summary.investigating_count == 1
    assert summary.resolved_count == 1
    assert summary.active_count == 2

    repository.get_for_portfolio.assert_called_once_with(
        10
    )
def test_get_active_returns_operational_work_queue() -> None:
    """Reporting should expose unresolved exceptions as a work queue."""

    exception = ReconciliationException(
        id=4,
        audit_item_id=104,
        portfolio_id=10,
        fund_id=204,
        exception_type="unit_mismatch",
        status="open",
        opened_at=datetime(
            2026,
            7,
            25,
            11,
            0,
            tzinfo=timezone.utc,
        ),
    )

    repository = Mock(
        spec=ReconciliationExceptionRepository,
    )
    repository.get_active_for_portfolio.return_value = [
        exception,
    ]

    service = ReconciliationExceptionReportingService(
        repository=repository,
    )

    results = service.get_active(
        portfolio_id=10
    )

    assert results == [
        exception,
    ]

    repository.get_active_for_portfolio.assert_called_once_with(
        10
    )