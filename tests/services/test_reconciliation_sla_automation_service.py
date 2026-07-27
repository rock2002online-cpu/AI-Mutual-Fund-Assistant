"""Tests for automated reconciliation SLA workflow."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from models.reconciliation_exception import (
    ReconciliationException,
)
from services.reconciliation_sla_automation_service import (
    ReconciliationSLAAutomationService,
)
from services.reconciliation_sla_escalation_service import (
    ReconciliationSLAEscalationService,
)
from services.reconciliation_sla_monitoring_service import (
    ReconciliationSLAMonitoringResult,
    ReconciliationSLAMonitoringService,
)
from unittest.mock import ANY

from models.reconciliation_sla_audit import (
    ReconciliationSLAAudit,
)
from services.reconciliation_sla_audit_service import (
    ReconciliationSLAAuditService,
)

def create_exception(
    *,
    exception_id: int,
    as_of: datetime,
) -> ReconciliationException:
    """Create an exception for SLA automation testing."""

    return ReconciliationException(
        id=exception_id,
        audit_item_id=exception_id + 100,
        portfolio_id=exception_id + 200,
        fund_id=exception_id + 300,
        exception_type="unit_mismatch",
        status="open",
        priority="normal",
        opened_at=as_of - timedelta(hours=5),
        assigned_to="operations-owner",
        assigned_at=as_of - timedelta(hours=3),
        investigation_started_at=None,
        resolved_at=None,
        escalated_at=None,
        escalation_reason=None,
    )


def test_run_portfolio_monitors_and_escalates_breaches(
) -> None:
    """A portfolio run should monitor and escalate SLA breaches."""

    as_of = datetime(
        2026,
        7,
        27,
        16,
        0,
        tzinfo=timezone.utc,
    )
    exception = create_exception(
        exception_id=701,
        as_of=as_of,
    )
    monitoring_result = ReconciliationSLAMonitoringResult(
        as_of=as_of,
        assignment_breaches=[],
        investigation_breaches=[exception],
        resolution_breaches=[],
    )

    monitoring_service = Mock(
        spec=ReconciliationSLAMonitoringService,
    )
    monitoring_service.monitor_portfolio.return_value = (
        monitoring_result
    )

    escalation_service = Mock(
        spec=ReconciliationSLAEscalationService,
    )
    escalation_service.escalate.return_value = [
        exception
    ]

    service = ReconciliationSLAAutomationService(
        monitoring_service=monitoring_service,
        escalation_service=escalation_service,
    )

    result = service.run_portfolio(
        portfolio_id=901,
        as_of=as_of,
        assignment_sla=timedelta(hours=2),
        investigation_sla=timedelta(hours=2),
        resolution_sla=timedelta(hours=24),
    )

    assert result.monitoring_result is monitoring_result
    assert result.escalated_exceptions == [
        exception,
    ]
    assert result.total_breaches == 1
    assert result.escalated_count == 1
    assert result.has_escalations is True

    monitoring_service.monitor_portfolio.assert_called_once_with(
        portfolio_id=901,
        as_of=as_of,
        assignment_sla=timedelta(hours=2),
        investigation_sla=timedelta(hours=2),
        resolution_sla=timedelta(hours=24),
    )
    escalation_service.escalate.assert_called_once_with(
        monitoring_result=monitoring_result,
        escalated_at=as_of,
    )


def test_run_portfolio_returns_empty_result_without_breaches(
) -> None:
    """A breach-free portfolio run should return empty automation results."""

    as_of = datetime(
        2026,
        7,
        27,
        17,
        0,
        tzinfo=timezone.utc,
    )
    monitoring_result = ReconciliationSLAMonitoringResult(
        as_of=as_of,
        assignment_breaches=[],
        investigation_breaches=[],
        resolution_breaches=[],
    )

    monitoring_service = Mock(
        spec=ReconciliationSLAMonitoringService,
    )
    monitoring_service.monitor_portfolio.return_value = (
        monitoring_result
    )

    escalation_service = Mock(
        spec=ReconciliationSLAEscalationService,
    )
    escalation_service.escalate.return_value = []

    service = ReconciliationSLAAutomationService(
        monitoring_service=monitoring_service,
        escalation_service=escalation_service,
    )

    result = service.run_portfolio(
        portfolio_id=902,
        as_of=as_of,
        assignment_sla=timedelta(hours=2),
        investigation_sla=timedelta(hours=4),
        resolution_sla=timedelta(hours=24),
    )

    assert result.monitoring_result is monitoring_result
    assert result.escalated_exceptions == []
    assert result.total_breaches == 0
    assert result.escalated_count == 0
    assert result.has_escalations is False

    monitoring_service.monitor_portfolio.assert_called_once_with(
        portfolio_id=902,
        as_of=as_of,
        assignment_sla=timedelta(hours=2),
        investigation_sla=timedelta(hours=4),
        resolution_sla=timedelta(hours=24),
    )
    escalation_service.escalate.assert_called_once_with(
        monitoring_result=monitoring_result,
        escalated_at=as_of,
    )
def test_run_portfolio_persists_sla_audit(
) -> None:
    """An automated portfolio run should persist its audit summary."""

    as_of = datetime(
        2026,
        7,
        27,
        18,
        0,
        tzinfo=timezone.utc,
    )
    monitoring_result = ReconciliationSLAMonitoringResult(
        as_of=as_of,
        assignment_breaches=[],
        investigation_breaches=[],
        resolution_breaches=[],
    )
    audit = ReconciliationSLAAudit(
        id=1,
        portfolio_id=903,
        monitored_at=as_of,
        assignment_breach_count=0,
        investigation_breach_count=0,
        resolution_breach_count=0,
        escalated_count=0,
    )

    monitoring_service = Mock(
        spec=ReconciliationSLAMonitoringService,
    )
    monitoring_service.monitor_portfolio.return_value = (
        monitoring_result
    )

    escalation_service = Mock(
        spec=ReconciliationSLAEscalationService,
    )
    escalation_service.escalate.return_value = []

    audit_service = Mock(
        spec=ReconciliationSLAAuditService,
    )
    audit_service.record.return_value = audit

    service = ReconciliationSLAAutomationService(
        monitoring_service=monitoring_service,
        escalation_service=escalation_service,
        audit_service=audit_service,
    )

    result = service.run_portfolio(
        portfolio_id=903,
        as_of=as_of,
        assignment_sla=timedelta(hours=2),
        investigation_sla=timedelta(hours=4),
        resolution_sla=timedelta(hours=24),
    )

    assert result.audit_record is audit
    audit_service.record.assert_called_once_with(
        portfolio_id=903,
        automation_result=ANY,
    )

    recorded_result = (
        audit_service.record.call_args.kwargs[
            "automation_result"
        ]
    )

    assert (
        recorded_result.monitoring_result
        is monitoring_result
    )
    assert (
        recorded_result.escalated_exceptions
        == []
    )