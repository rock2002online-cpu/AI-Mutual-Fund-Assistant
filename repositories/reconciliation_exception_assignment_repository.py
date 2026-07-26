"""Repository for reconciliation exception assignment history."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.reconciliation_exception_assignment import (
    ReconciliationExceptionAssignment,
)
from repositories.base_repository import (
    BaseRepository,
)


class ReconciliationExceptionAssignmentRepository(
    BaseRepository[
        ReconciliationExceptionAssignment
    ]
):
    """Persist immutable exception ownership history."""

    def __init__(
        self,
        session: Session,
    ) -> None:
        super().__init__(
            session=session,
            model=ReconciliationExceptionAssignment,
        )

    def get_for_exception(
        self,
        exception_id: int,
    ) -> list[
        ReconciliationExceptionAssignment
    ]:
        """Return assignment history in chronological order."""

        statement = (
            select(
                ReconciliationExceptionAssignment
            )
            .where(
                ReconciliationExceptionAssignment.exception_id
                == exception_id
            )
            .order_by(
                ReconciliationExceptionAssignment.assigned_at.asc(),
                ReconciliationExceptionAssignment.id.asc(),
            )
        )

        return list(
            self.session.scalars(
                statement
            )
        )


__all__ = [
    "ReconciliationExceptionAssignmentRepository",
]