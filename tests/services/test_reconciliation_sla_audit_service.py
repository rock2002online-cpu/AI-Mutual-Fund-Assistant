"""Tests for reconciliation SLA audit recording."""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from models.reconciliation_exception import (
    ReconciliationException,
)
from repositories.reconciliation_sla_audit_repository import (
    ReconciliationSLAAuditRepository,
)
from services.reconciliation_sla_audit_service import (
    ReconciliationSLAAuditService,
    ReconciliationSLAAuditValidationError,
)
from services.reconciliation_sla_automation_service import (
    ReconciliationSLAAutomationResult,
)
from services.reconciliation_sla_monitoring_service import (
    ReconciliationSLAMonitoringResult,
)


def create_automation_result(
    *,
    monitored_at: datetime,
    assignment_breach_count: int = 0,
    investigation_breach_count: int = 0,
    resolution_breach_count: int = 0,
    escalated_count: int = 0,
) -> ReconciliationSLAAutomationResult:
    """Create an automation result with requested totals."""

    return ReconciliationSLAAutomationResult(
        monitoring_result=(
            ReconciliationSLAMonitoringResult(
                as_of=monitored_at,
                assignment_breaches=[
                    Mock(
                        spec=ReconciliationException,
                    )
                    for _ in range(
                        assignment_breach_count
                    )
                ],
                investigation_breaches=[
                    Mock(
                        spec=ReconciliationException,
                    )
                    for _ in range(
                        investigation_breach_count
                    )
                ],
                resolution_breaches=[
                    Mock(
                        spec=ReconciliationException,
                    )
                    for _ in range(
                        resolution_breach_count
                    )
                ],
            )
        ),
        escalated_exceptions=[
            Mock(
                spec=ReconciliationException,
            )
            for _ in range(
                escalated_count
            )
        ],
    )


def test_record_persists_automation_summary(
) -> None:
    """An automation run should create a persistent SLA audit."""

    monitored_at = datetime(
        2026,
        7,
        27,
        18,
        0,
        tzinfo=timezone.utc,
    )
    automation_result = create_automation_result(
        monitored_at=monitored_at,
        assignment_breach_count=1,
        investigation_breach_count=2,
        resolution_breach_count=3,
        escalated_count=4,
    )

    repository = Mock(
        spec=ReconciliationSLAAuditRepository,
    )
    repository.add.side_effect = (
        lambda audit: audit
    )

    service = ReconciliationSLAAuditService(
        repository=repository,
    )

    audit = service.record(
        portfolio_id=501,
        automation_result=automation_result,
    )

    assert audit.portfolio_id == 501
    assert audit.monitored_at == monitored_at
    assert audit.assignment_breach_count == 1
    assert audit.investigation_breach_count == 2
    assert audit.resolution_breach_count == 3
    assert audit.escalated_count == 4
    repository.add.assert_called_once_with(
        audit
    )


def test_record_persists_breach_free_run(
) -> None:
    """A breach-free monitoring run should still be audited."""

    monitored_at = datetime(
        2026,
        7,
        27,
        19,
        0,
        tzinfo=timezone.utc,
    )
    automation_result = create_automation_result(
        monitored_at=monitored_at,
    )

    repository = Mock(
        spec=ReconciliationSLAAuditRepository,
    )
    repository.add.side_effect = (
        lambda audit: audit
    )

    service = ReconciliationSLAAuditService(
        repository=repository,
    )

    audit = service.record(
        portfolio_id=502,
        automation_result=automation_result,
    )

    assert audit.portfolio_id == 502
    assert audit.monitored_at == monitored_at
    assert audit.assignment_breach_count == 0
    assert audit.investigation_breach_count == 0
    assert audit.resolution_breach_count == 0
    assert audit.escalated_count == 0
    repository.add.assert_called_once_with(
        audit
    )


@pytest.mark.parametrize(
    "portfolio_id",
    [
        0,
        -1,
    ],
)
def test_record_rejects_non_positive_portfolio_id(
    portfolio_id: int,
) -> None:
    """Audit recording requires a positive portfolio identifier."""

    repository = Mock(
        spec=ReconciliationSLAAuditRepository,
    )
    service = ReconciliationSLAAuditService(
        repository=repository,
    )
    automation_result = create_automation_result(
        monitored_at=datetime(
            2026,
            7,
            27,
            20,
            0,
            tzinfo=timezone.utc,
        ),
    )

    with pytest.raises(
        ReconciliationSLAAuditValidationError,
        match="portfolio_id must be positive",
    ):
        service.record(
            portfolio_id=portfolio_id,
            automation_result=automation_result,
        )

    repository.add.assert_not_called()