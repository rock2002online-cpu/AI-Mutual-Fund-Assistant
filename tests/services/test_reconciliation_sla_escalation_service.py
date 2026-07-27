"""Tests for automated reconciliation SLA escalation."""

from datetime import datetime, timezone
from unittest.mock import Mock, call

from models.reconciliation_exception import (
    ReconciliationException,
)
from services.reconciliation_exception_service import (
    ReconciliationExceptionService,
)
from services.reconciliation_sla_escalation_service import (
    ReconciliationSLAEscalationService,
)
from services.reconciliation_sla_monitoring_service import (
    ReconciliationSLAMonitoringResult,
)


def create_exception(
    *,
    exception_id: int,
    status: str,
    escalated_at: datetime | None = None,
) -> ReconciliationException:
    """Create an exception for SLA escalation testing."""

    recorded_at = datetime(
        2026,
        7,
        27,
        9,
        0,
        tzinfo=timezone.utc,
    )

    return ReconciliationException(
        id=exception_id,
        audit_item_id=exception_id + 100,
        portfolio_id=exception_id + 200,
        fund_id=exception_id + 300,
        exception_type="unit_mismatch",
        status=status,
        priority=(
            "high"
            if escalated_at is not None
            else "normal"
        ),
        opened_at=recorded_at,
        assigned_to="operations-owner",
        assigned_at=recorded_at,
        investigation_started_at=(
            recorded_at
            if status == "investigating"
            else None
        ),
        resolved_at=None,
        escalated_at=escalated_at,
        escalation_reason=(
            "Previously escalated."
            if escalated_at is not None
            else None
        ),
    )


def test_escalate_escalates_investigation_sla_breach(
) -> None:
    """An investigation SLA breach should be escalated automatically."""

    escalated_at = datetime(
        2026,
        7,
        27,
        10,
        0,
        tzinfo=timezone.utc,
    )
    exception = create_exception(
        exception_id=601,
        status="open",
    )
    monitoring_result = ReconciliationSLAMonitoringResult(
        as_of=escalated_at,
        assignment_breaches=[],
        investigation_breaches=[exception],
        resolution_breaches=[],
    )
    exception_service = Mock(
        spec=ReconciliationExceptionService,
    )
    exception_service.escalate.return_value = exception

    service = ReconciliationSLAEscalationService(
        exception_service=exception_service,
    )

    escalated = service.escalate(
        monitoring_result=monitoring_result,
        escalated_at=escalated_at,
    )

    assert escalated == [exception]
    exception_service.escalate.assert_called_once_with(
        exception_id=exception.id,
        escalated_at=escalated_at,
        reason="Investigation SLA breached.",
    )


def test_escalate_escalates_resolution_sla_breach(
) -> None:
    """A resolution SLA breach should be escalated automatically."""

    escalated_at = datetime(
        2026,
        7,
        27,
        11,
        0,
        tzinfo=timezone.utc,
    )
    exception = create_exception(
        exception_id=602,
        status="investigating",
    )
    monitoring_result = ReconciliationSLAMonitoringResult(
        as_of=escalated_at,
        assignment_breaches=[],
        investigation_breaches=[],
        resolution_breaches=[exception],
    )
    exception_service = Mock(
        spec=ReconciliationExceptionService,
    )
    exception_service.escalate.return_value = exception

    service = ReconciliationSLAEscalationService(
        exception_service=exception_service,
    )

    escalated = service.escalate(
        monitoring_result=monitoring_result,
        escalated_at=escalated_at,
    )

    assert escalated == [exception]
    exception_service.escalate.assert_called_once_with(
        exception_id=exception.id,
        escalated_at=escalated_at,
        reason="Resolution SLA breached.",
    )


def test_escalate_escalates_multiple_sla_breach_types(
) -> None:
    """Investigation and resolution breaches should be escalated."""

    escalated_at = datetime(
        2026,
        7,
        27,
        12,
        0,
        tzinfo=timezone.utc,
    )
    investigation_exception = create_exception(
        exception_id=603,
        status="open",
    )
    resolution_exception = create_exception(
        exception_id=604,
        status="investigating",
    )
    monitoring_result = ReconciliationSLAMonitoringResult(
        as_of=escalated_at,
        assignment_breaches=[],
        investigation_breaches=[
            investigation_exception,
        ],
        resolution_breaches=[
            resolution_exception,
        ],
    )
    exception_service = Mock(
        spec=ReconciliationExceptionService,
    )
    exception_service.escalate.side_effect = [
        investigation_exception,
        resolution_exception,
    ]

    service = ReconciliationSLAEscalationService(
        exception_service=exception_service,
    )

    escalated = service.escalate(
        monitoring_result=monitoring_result,
        escalated_at=escalated_at,
    )

    assert escalated == [
        investigation_exception,
        resolution_exception,
    ]
    assert exception_service.escalate.call_count == 2
    exception_service.escalate.assert_has_calls(
        [
            call(
                exception_id=(
                    investigation_exception.id
                ),
                escalated_at=escalated_at,
                reason=(
                    "Investigation SLA breached."
                ),
            ),
            call(
                exception_id=(
                    resolution_exception.id
                ),
                escalated_at=escalated_at,
                reason="Resolution SLA breached.",
            ),
        ]
    )


def test_escalate_does_not_escalate_assignment_breach(
) -> None:
    """Unassigned assignment breaches cannot be escalated."""

    escalated_at = datetime(
        2026,
        7,
        27,
        13,
        0,
        tzinfo=timezone.utc,
    )
    exception = create_exception(
        exception_id=605,
        status="open",
    )
    exception.assigned_to = None
    exception.assigned_at = None

    monitoring_result = ReconciliationSLAMonitoringResult(
        as_of=escalated_at,
        assignment_breaches=[exception],
        investigation_breaches=[],
        resolution_breaches=[],
    )
    exception_service = Mock(
        spec=ReconciliationExceptionService,
    )

    service = ReconciliationSLAEscalationService(
        exception_service=exception_service,
    )

    escalated = service.escalate(
        monitoring_result=monitoring_result,
        escalated_at=escalated_at,
    )

    assert escalated == []
    exception_service.escalate.assert_not_called()


def test_escalate_skips_already_escalated_exception(
) -> None:
    """Automated escalation must be safe to run repeatedly."""

    previous_escalated_at = datetime(
        2026,
        7,
        27,
        12,
        0,
        tzinfo=timezone.utc,
    )
    monitoring_time = datetime(
        2026,
        7,
        27,
        14,
        0,
        tzinfo=timezone.utc,
    )
    exception = create_exception(
        exception_id=606,
        status="open",
        escalated_at=previous_escalated_at,
    )
    monitoring_result = ReconciliationSLAMonitoringResult(
        as_of=monitoring_time,
        assignment_breaches=[],
        investigation_breaches=[exception],
        resolution_breaches=[],
    )
    exception_service = Mock(
        spec=ReconciliationExceptionService,
    )

    service = ReconciliationSLAEscalationService(
        exception_service=exception_service,
    )

    escalated = service.escalate(
        monitoring_result=monitoring_result,
        escalated_at=monitoring_time,
    )

    assert escalated == []
    exception_service.escalate.assert_not_called()


def test_escalate_does_not_escalate_same_exception_twice(
) -> None:
    """A monitoring run must escalate each exception at most once."""

    escalated_at = datetime(
        2026,
        7,
        27,
        15,
        0,
        tzinfo=timezone.utc,
    )
    exception = create_exception(
        exception_id=607,
        status="investigating",
    )
    monitoring_result = ReconciliationSLAMonitoringResult(
        as_of=escalated_at,
        assignment_breaches=[],
        investigation_breaches=[exception],
        resolution_breaches=[exception],
    )
    exception_service = Mock(
        spec=ReconciliationExceptionService,
    )
    exception_service.escalate.return_value = exception

    service = ReconciliationSLAEscalationService(
        exception_service=exception_service,
    )

    escalated = service.escalate(
        monitoring_result=monitoring_result,
        escalated_at=escalated_at,
    )

    assert escalated == [exception]
    exception_service.escalate.assert_called_once_with(
        exception_id=exception.id,
        escalated_at=escalated_at,
        reason="Investigation SLA breached.",
    )