"""Repository for reconciliation audit snapshots."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.reconciliation_audit import (
    ReconciliationAuditSnapshot,
)
from repositories.base_repository import (
    BaseRepository,
)


class ReconciliationAuditRepository(
    BaseRepository[ReconciliationAuditSnapshot]
):
    """Persist and retrieve reconciliation audit snapshots."""

    def __init__(
        self,
        session: Session,
    ) -> None:
        super().__init__(
            session=session,
            model=ReconciliationAuditSnapshot,
        )

    def get_latest_for_portfolio(
        self,
        portfolio_id: int,
    ) -> ReconciliationAuditSnapshot | None:
        """Return the latest audit snapshot for a portfolio."""

        statement = (
            select(ReconciliationAuditSnapshot)
            .where(
                ReconciliationAuditSnapshot.portfolio_id
                == portfolio_id
            )
            .order_by(
                ReconciliationAuditSnapshot
                .recorded_at
                .desc(),
                ReconciliationAuditSnapshot.id.desc(),
            )
        )

        return self.session.scalars(
            statement
        ).first()
    def get_for_portfolio(
        self,
        portfolio_id: int,
    ) -> list[ReconciliationAuditSnapshot]:
        """Return portfolio audit history newest first."""

        statement = (
            select(ReconciliationAuditSnapshot)
            .where(
                ReconciliationAuditSnapshot.portfolio_id
                == portfolio_id
            )
            .order_by(
                ReconciliationAuditSnapshot
                .recorded_at
                .desc(),
                ReconciliationAuditSnapshot.id.desc(),
            )
        )

        return list(
            self.session.scalars(
                statement
            )
        )

__all__ = [
    "ReconciliationAuditRepository",
]