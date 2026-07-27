"""Monitor reconciliation exceptions for SLA breaches."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from models.reconciliation_exception import (
    ReconciliationException,
)
from repositories.reconciliation_exception_repository import (
    ReconciliationExceptionRepository,
)

class ReconciliationSLAMonitoringValidationError(
    ValueError
):
    """Raised when SLA monitoring input is invalid."""


@dataclass(frozen=True, slots=True)
class ReconciliationSLAMonitoringResult:
    """Result of a reconciliation SLA monitoring run."""

    as_of: datetime
    assignment_breaches: list[
        ReconciliationException
    ]
    investigation_breaches: list[
        ReconciliationException
    ]
    resolution_breaches: list[
        ReconciliationException
    ]
    @property
    def total_breaches(self) -> int:
        """Return the total number of detected SLA breaches."""

        return (
            len(self.assignment_breaches)
            + len(self.investigation_breaches)
            + len(self.resolution_breaches)
        )
    @property
    def has_breaches(self) -> bool:
        """Return whether the monitoring run detected any breach."""

        return self.total_breaches > 0

class ReconciliationSLAMonitoringService:
    """Detect SLA breaches among reconciliation exceptions."""
    def __init__(
        self,
        *,
        repository: (
            ReconciliationExceptionRepository | None
        ) = None,
    ) -> None:
        self._repository = repository

    def find_assignment_breaches(
        self,
        *,
        exceptions: list[ReconciliationException],
        as_of: datetime,
        assignment_sla: timedelta,
    ) -> list[ReconciliationException]:
        """Return active unassigned exceptions ordered oldest first."""

        if assignment_sla <= timedelta(0):
            raise ReconciliationSLAMonitoringValidationError(
                "assignment_sla must be positive."
            )

        breached = [
            exception
            for exception in exceptions
            if exception.status in {
                "open",
                "investigating",
            }
            and exception.assigned_to is None
            and as_of - exception.opened_at
            >= assignment_sla
        ]

        return sorted(
            breached,
            key=lambda exception: exception.opened_at,
        )

    def find_investigation_breaches(
        self,
        *,
        exceptions: list[ReconciliationException],
        as_of: datetime,
        investigation_sla: timedelta,
    ) -> list[ReconciliationException]:
        """Return overdue investigations ordered by assignment time."""

        if investigation_sla <= timedelta(0):
            raise ReconciliationSLAMonitoringValidationError(
                "investigation_sla must be positive."
            )

        breached = [
            exception
            for exception in exceptions
            if exception.status == "open"
            and exception.assigned_to is not None
            and exception.assigned_at is not None
            and exception.investigation_started_at is None
            and as_of - exception.assigned_at
            >= investigation_sla
        ]

        return sorted(
            breached,
            key=lambda exception: exception.assigned_at,
        )

    def find_resolution_breaches(
        self,
        *,
        exceptions: list[ReconciliationException],
        as_of: datetime,
        resolution_sla: timedelta,
    ) -> list[ReconciliationException]:
        """Return overdue resolutions ordered by investigation start time."""

        if resolution_sla <= timedelta(0):
            raise ReconciliationSLAMonitoringValidationError(
                "resolution_sla must be positive."
            )

        breached = [
            exception
            for exception in exceptions
            if exception.status == "investigating"
            and exception.investigation_started_at is not None
            and exception.resolved_at is None
            and as_of - exception.investigation_started_at
            >= resolution_sla
        ]

        return sorted(
            breached,
            key=lambda exception: (
                exception.investigation_started_at
            ),
        )

    def monitor(
        self,
        *,
        exceptions: list[ReconciliationException],
        as_of: datetime,
        assignment_sla: timedelta,
        investigation_sla: timedelta,
        resolution_sla: timedelta,
    ) -> ReconciliationSLAMonitoringResult:
        """Evaluate all reconciliation SLA stages."""

        return ReconciliationSLAMonitoringResult(
            as_of=as_of,
            assignment_breaches=(
                self.find_assignment_breaches(
                    exceptions=exceptions,
                    as_of=as_of,
                    assignment_sla=assignment_sla,
                )
            ),
            investigation_breaches=(
                self.find_investigation_breaches(
                    exceptions=exceptions,
                    as_of=as_of,
                    investigation_sla=investigation_sla,
                )
            ),
            resolution_breaches=(
                self.find_resolution_breaches(
                    exceptions=exceptions,
                    as_of=as_of,
                    resolution_sla=resolution_sla,
                )
            ),
        )
    def monitor_portfolio(
        self,
        *,
        portfolio_id: int,
        as_of: datetime,
        assignment_sla: timedelta,
        investigation_sla: timedelta,
        resolution_sla: timedelta,
    ) -> ReconciliationSLAMonitoringResult:
        """Load and monitor active exceptions for a portfolio."""

        if portfolio_id <= 0:
            raise ReconciliationSLAMonitoringValidationError(
                "portfolio_id must be positive."
            )

        if self._repository is None:
            raise ReconciliationSLAMonitoringValidationError(
                "repository is required for portfolio monitoring."
            )

        exceptions = (
            self._repository.get_active_for_portfolio(
                portfolio_id
            )
        )

        return self.monitor(
            exceptions=exceptions,
            as_of=as_of,
            assignment_sla=assignment_sla,
            investigation_sla=investigation_sla,
            resolution_sla=resolution_sla,
        )

__all__ = [
    "ReconciliationSLAMonitoringResult",
    "ReconciliationSLAMonitoringService",
    "ReconciliationSLAMonitoringValidationError",
]