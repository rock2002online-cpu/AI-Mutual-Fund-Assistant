"""Create and manage actionable reconciliation exceptions."""

from __future__ import annotations

from datetime import datetime

from models.reconciliation_audit import (
    ReconciliationAuditSnapshot,
)
from models.reconciliation_exception import (
    ReconciliationException,
)
from repositories.reconciliation_exception_repository import (
    ReconciliationExceptionRepository,
)


ACTIONABLE_RECONCILIATION_STATUSES = frozenset(
    {
        "unit_mismatch",
        "missing_position",
        "missing_tax_lots",
    }
)


class ReconciliationExceptionValidationError(
    ValueError
):
    """Raised when an exception operation is invalid."""


class ReconciliationExceptionService:
    """Create and manage operational reconciliation exceptions."""

    def __init__(
        self,
        *,
        repository: ReconciliationExceptionRepository,
    ) -> None:
        self._repository = repository

    def open_for_snapshot(
        self,
        *,
        snapshot: ReconciliationAuditSnapshot,
        opened_at: datetime,
    ) -> list[ReconciliationException]:
        """Create exceptions for actionable audit items."""

        created: list[
            ReconciliationException
        ] = []

        for item in snapshot.items:
            if (
                item.status
                not in ACTIONABLE_RECONCILIATION_STATUSES
            ):
                continue

            existing = (
                self._repository
                .get_by_audit_item_id(
                    item.id
                )
            )

            if existing is not None:
                continue

            exception = ReconciliationException(
                audit_item_id=item.id,
                portfolio_id=snapshot.portfolio_id,
                fund_id=item.fund_id,
                exception_type=item.status,
                status="open",
                opened_at=opened_at,
            )

            created.append(
                self._repository.add(
                    exception
                )
            )

        return created

    def start_investigation(
        self,
        *,
        exception_id: int,
        started_at: datetime,
    ) -> ReconciliationException:
        """Transition an open exception to investigating."""

        exception = self._repository.get_by_id(
            exception_id
        )

        if exception.status != "open":
            raise ReconciliationExceptionValidationError(
                "only open exceptions can be "
                "moved to investigating."
            )

        exception.status = "investigating"
        exception.investigation_started_at = (
            started_at
        )

        return self._repository.update(
            exception
        )

    def resolve(
        self,
        *,
        exception_id: int,
        resolved_at: datetime,
        resolution_notes: str,
    ) -> ReconciliationException:
        """Transition an investigating exception to resolved."""

        if not resolution_notes.strip():
            raise ReconciliationExceptionValidationError(
                "resolution_notes cannot be empty."
            )

        exception = self._repository.get_by_id(
            exception_id
        )

        if exception.status != "investigating":
            raise ReconciliationExceptionValidationError(
                "only investigating exceptions "
                "can be resolved."
            )

        exception.status = "resolved"
        exception.resolved_at = resolved_at
        exception.resolution_notes = (
            resolution_notes
        )

        return self._repository.update(
            exception
        )


__all__ = [
    "ACTIONABLE_RECONCILIATION_STATUSES",
    "ReconciliationExceptionService",
    "ReconciliationExceptionValidationError",
]