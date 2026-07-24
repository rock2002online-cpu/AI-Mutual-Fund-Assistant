"""Repository for reconciliation exceptions."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.reconciliation_exception import (
    ReconciliationException,
)
from repositories.base_repository import (
    BaseRepository,
)


class ReconciliationExceptionRepository(
    BaseRepository[ReconciliationException]
):
    """Persist and retrieve reconciliation exceptions."""

    def __init__(
        self,
        session: Session,
    ) -> None:
        super().__init__(
            session=session,
            model=ReconciliationException,
        )

    def get_by_audit_item_id(
        self,
        audit_item_id: int,
    ) -> ReconciliationException | None:
        """Return the exception linked to an audit item."""

        statement = (
            select(ReconciliationException)
            .where(
                ReconciliationException.audit_item_id
                == audit_item_id
            )
        )

        return self.session.scalars(
            statement
        ).first()

    def get_for_portfolio(
        self,
        portfolio_id: int,
        *,
        status: str | None = None,
    ) -> list[ReconciliationException]:
        """Return portfolio exceptions newest first."""

        statement = select(
            ReconciliationException
        ).where(
            ReconciliationException.portfolio_id
            == portfolio_id
        )

        if status is not None:
            statement = statement.where(
                ReconciliationException.status
                == status
            )

        statement = statement.order_by(
            ReconciliationException.opened_at.desc(),
            ReconciliationException.id.desc(),
        )

        return list(
            self.session.scalars(
                statement
            )
        )


__all__ = [
    "ReconciliationExceptionRepository",
]