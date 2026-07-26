"""Create and manage actionable reconciliation exceptions."""

from __future__ import annotations

from datetime import datetime

from models.reconciliation_audit import (
    ReconciliationAuditSnapshot,
)
from models.reconciliation_exception import (
    ReconciliationException,
)
from models.reconciliation_exception_assignment import (
    ReconciliationExceptionAssignment,
)
from repositories.reconciliation_exception_assignment_repository import (
    ReconciliationExceptionAssignmentRepository,
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
        assignment_repository: (
            ReconciliationExceptionAssignmentRepository
            | None
        ) = None,
    ) -> None:
        self._repository = repository
        self._assignment_repository = (
            assignment_repository
        )

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

    def assign(
        self,
        *,
        exception_id: int,
        assigned_to: str,
        assigned_at: datetime,
    ) -> ReconciliationException:
        """Assign an unassigned exception to an operational owner."""

        if not assigned_to.strip():
            raise ReconciliationExceptionValidationError(
                "assigned_to cannot be empty."
            )

        exception = self._repository.get_by_id(
            exception_id
        )

        if exception.status == "resolved":
            raise ReconciliationExceptionValidationError(
                "resolved exceptions cannot be assigned."
            )

        if exception.assigned_to is not None:
            raise ReconciliationExceptionValidationError(
                "exception is already assigned."
            )

        exception.assigned_to = assigned_to
        exception.assigned_at = assigned_at

        updated = self._repository.update(
            exception
        )

        if self._assignment_repository is not None:
            self._assignment_repository.add(
                ReconciliationExceptionAssignment(
                    exception_id=exception.id,
                    previous_assigned_to=None,
                    assigned_to=assigned_to,
                    assigned_at=assigned_at,
                    reason=None,
                )
            )

        return updated
    def reassign(
        self,
        *,
        exception_id: int,
        assigned_to: str,
        reassigned_at: datetime,
        reason: str,
    ) -> ReconciliationException:
        """Transfer ownership and preserve assignment history."""

        if not assigned_to.strip():
            raise ReconciliationExceptionValidationError(
                "assigned_to cannot be empty."
            )

        if not reason.strip():
            raise ReconciliationExceptionValidationError(
                "reason cannot be empty."
            )

        exception = self._repository.get_by_id(
            exception_id
        )

        if exception.status == "resolved":
            raise ReconciliationExceptionValidationError(
                "resolved exceptions cannot be reassigned."
            )

        if exception.assigned_to is None:
            raise ReconciliationExceptionValidationError(
                "exception is not currently assigned."
            )

        if exception.assigned_to == assigned_to:
            raise ReconciliationExceptionValidationError(
                "new owner must be different."
            )

        previous_assigned_to = (
            exception.assigned_to
        )

        exception.assigned_to = assigned_to
        exception.assigned_at = reassigned_at

        updated = self._repository.update(
            exception
        )

        if self._assignment_repository is not None:
            self._assignment_repository.add(
                ReconciliationExceptionAssignment(
                    exception_id=exception.id,
                    previous_assigned_to=(
                        previous_assigned_to
                    ),
                    assigned_to=assigned_to,
                    assigned_at=reassigned_at,
                    reason=reason,
                )
            )

        return updated
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