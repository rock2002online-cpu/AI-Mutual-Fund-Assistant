"""Record reconciliation SLA automation history."""

from __future__ import annotations

from models.reconciliation_sla_audit import (
    ReconciliationSLAAudit,
)
from repositories.reconciliation_sla_audit_repository import (
    ReconciliationSLAAuditRepository,
)
from services.reconciliation_sla_automation_service import (
    ReconciliationSLAAutomationResult,
)


class ReconciliationSLAAuditValidationError(
    ValueError
):
    """Raised when an SLA audit operation is invalid."""


class ReconciliationSLAAuditService:
    """Persist summaries of reconciliation SLA automation runs."""

    def __init__(
        self,
        *,
        repository: ReconciliationSLAAuditRepository,
    ) -> None:
        self._repository = repository

    def record(
        self,
        *,
        portfolio_id: int,
        automation_result: (
            ReconciliationSLAAutomationResult
        ),
    ) -> ReconciliationSLAAudit:
        """Persist the summary of an SLA automation run."""

        if portfolio_id <= 0:
            raise ReconciliationSLAAuditValidationError(
                "portfolio_id must be positive."
            )

        monitoring_result = (
            automation_result.monitoring_result
        )

        audit = ReconciliationSLAAudit(
            portfolio_id=portfolio_id,
            monitored_at=monitoring_result.as_of,
            assignment_breach_count=len(
                monitoring_result.assignment_breaches
            ),
            investigation_breach_count=len(
                monitoring_result.investigation_breaches
            ),
            resolution_breach_count=len(
                monitoring_result.resolution_breaches
            ),
            escalated_count=len(
                automation_result.escalated_exceptions
            ),
        )

        return self._repository.add(
            audit
        )


__all__ = [
    "ReconciliationSLAAuditService",
    "ReconciliationSLAAuditValidationError",
]