"""Automatically escalate reconciliation SLA breaches."""

from __future__ import annotations

from datetime import datetime

from models.reconciliation_exception import (
    ReconciliationException,
)
from services.reconciliation_exception_service import (
    ReconciliationExceptionService,
)
from services.reconciliation_sla_monitoring_service import (
    ReconciliationSLAMonitoringResult,
)


class ReconciliationSLAEscalationService:
    """Escalate assigned exceptions that breached their SLA."""

    def __init__(
        self,
        *,
        exception_service: ReconciliationExceptionService,
    ) -> None:
        self._exception_service = exception_service

    def escalate(
        self,
        *,
        monitoring_result: (
            ReconciliationSLAMonitoringResult
        ),
        escalated_at: datetime,
    ) -> list[ReconciliationException]:
        """Escalate eligible investigation and resolution breaches."""

        escalated: list[
            ReconciliationException
        ] = []
        processed_exception_ids: set[int] = set()

        breach_groups = (
            (
                monitoring_result.investigation_breaches,
                "Investigation SLA breached.",
            ),
            (
                monitoring_result.resolution_breaches,
                "Resolution SLA breached.",
            ),
        )

        for exceptions, reason in breach_groups:
            for exception in exceptions:
                if exception.escalated_at is not None:
                    continue

                if exception.id in processed_exception_ids:
                    continue

                processed_exception_ids.add(
                    exception.id
                )

                escalated.append(
                    self._exception_service.escalate(
                        exception_id=exception.id,
                        escalated_at=escalated_at,
                        reason=reason,
                    )
                )

        return escalated


__all__ = [
    "ReconciliationSLAEscalationService",
]