"""Orchestrate reconciliation SLA monitoring and escalation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from models.reconciliation_exception import (
    ReconciliationException,
)
from models.reconciliation_sla_audit import (
    ReconciliationSLAAudit,
)
from services.reconciliation_sla_escalation_service import (
    ReconciliationSLAEscalationService,
)
from services.reconciliation_sla_monitoring_service import (
    ReconciliationSLAMonitoringResult,
    ReconciliationSLAMonitoringService,
)

if TYPE_CHECKING:
    from services.reconciliation_sla_audit_service import (
        ReconciliationSLAAuditService,
    )


@dataclass(frozen=True, slots=True)
class ReconciliationSLAAutomationResult:
    """Result of an automated reconciliation SLA run."""

    monitoring_result: (
        ReconciliationSLAMonitoringResult
    )
    escalated_exceptions: list[
        ReconciliationException
    ]
    audit_record: (
        ReconciliationSLAAudit | None
    ) = None

    @property
    def total_breaches(self) -> int:
        """Return the total detected SLA breach count."""

        return (
            self.monitoring_result.total_breaches
        )

    @property
    def escalated_count(self) -> int:
        """Return the number of escalated exceptions."""

        return len(
            self.escalated_exceptions
        )

    @property
    def has_escalations(self) -> bool:
        """Return whether any exception was escalated."""

        return self.escalated_count > 0


class ReconciliationSLAAutomationService:
    """Coordinate monitoring, escalation, and audit persistence."""

    def __init__(
        self,
        *,
        monitoring_service: (
            ReconciliationSLAMonitoringService
        ),
        escalation_service: (
            ReconciliationSLAEscalationService
        ),
        audit_service: (
            ReconciliationSLAAuditService | None
        ) = None,
    ) -> None:
        self._monitoring_service = monitoring_service
        self._escalation_service = escalation_service
        self._audit_service = audit_service

    def run_portfolio(
        self,
        *,
        portfolio_id: int,
        as_of: datetime,
        assignment_sla: timedelta,
        investigation_sla: timedelta,
        resolution_sla: timedelta,
    ) -> ReconciliationSLAAutomationResult:
        """Monitor, escalate, and audit a portfolio SLA run."""

        monitoring_result = (
            self._monitoring_service.monitor_portfolio(
                portfolio_id=portfolio_id,
                as_of=as_of,
                assignment_sla=assignment_sla,
                investigation_sla=investigation_sla,
                resolution_sla=resolution_sla,
            )
        )

        escalated_exceptions = (
            self._escalation_service.escalate(
                monitoring_result=monitoring_result,
                escalated_at=as_of,
            )
        )

        automation_result = (
            ReconciliationSLAAutomationResult(
                monitoring_result=(
                    monitoring_result
                ),
                escalated_exceptions=(
                    escalated_exceptions
                ),
            )
        )

        if self._audit_service is None:
            return automation_result

        audit_record = (
            self._audit_service.record(
                portfolio_id=portfolio_id,
                automation_result=(
                    automation_result
                ),
            )
        )

        return ReconciliationSLAAutomationResult(
            monitoring_result=monitoring_result,
            escalated_exceptions=(
                escalated_exceptions
            ),
            audit_record=audit_record,
        )


__all__ = [
    "ReconciliationSLAAutomationResult",
    "ReconciliationSLAAutomationService",
]