"""Read-only reporting for reconciliation exceptions."""

from __future__ import annotations

from dataclasses import dataclass

from models.reconciliation_exception import (
    ReconciliationException,
)
from repositories.reconciliation_exception_repository import (
    ReconciliationExceptionRepository,
)


@dataclass(frozen=True)
class ReconciliationExceptionSummary:
    """Lifecycle counts for portfolio exceptions."""

    total_count: int
    open_count: int
    investigating_count: int
    resolved_count: int

    @property
    def active_count(self) -> int:
        """Return exceptions requiring operational attention."""

        return (
            self.open_count
            + self.investigating_count
        )


class ReconciliationExceptionReportingService:
    """Build read-only reconciliation exception reports."""

    def __init__(
        self,
        *,
        repository: ReconciliationExceptionRepository,
    ) -> None:
        self._repository = repository

    def summarize(
        self,
        *,
        portfolio_id: int,
    ) -> ReconciliationExceptionSummary:
        """Return lifecycle counts for a portfolio."""

        exceptions = (
            self._repository.get_for_portfolio(
                portfolio_id
            )
        )

        return ReconciliationExceptionSummary(
            total_count=len(exceptions),
            open_count=sum(
                exception.status == "open"
                for exception in exceptions
            ),
            investigating_count=sum(
                exception.status == "investigating"
                for exception in exceptions
            ),
            resolved_count=sum(
                exception.status == "resolved"
                for exception in exceptions
            ),
        )

    def get_active(
        self,
        *,
        portfolio_id: int,
    ) -> list[ReconciliationException]:
        """Return the portfolio's operational exception queue."""

        return (
            self._repository
            .get_active_for_portfolio(
                portfolio_id
            )
        )


__all__ = [
    "ReconciliationExceptionReportingService",
    "ReconciliationExceptionSummary",
]