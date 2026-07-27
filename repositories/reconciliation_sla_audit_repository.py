"""Repository for reconciliation SLA monitoring audits."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.reconciliation_sla_audit import (
    ReconciliationSLAAudit,
)
from repositories.base_repository import (
    BaseRepository,
)


class ReconciliationSLAAuditRepository(
    BaseRepository[
        ReconciliationSLAAudit
    ]
):
    """Persist reconciliation SLA monitoring history."""

    def __init__(
        self,
        session: Session,
    ) -> None:
        super().__init__(
            session=session,
            model=ReconciliationSLAAudit,
        )

    def get_for_portfolio(
        self,
        portfolio_id: int,
    ) -> list[ReconciliationSLAAudit]:
        """Return portfolio SLA audits newest first."""

        statement = (
            select(
                ReconciliationSLAAudit
            )
            .where(
                ReconciliationSLAAudit.portfolio_id
                == portfolio_id
            )
            .order_by(
                ReconciliationSLAAudit.monitored_at.desc(),
                ReconciliationSLAAudit.id.desc(),
            )
        )

        return list(
            self.session.scalars(
                statement
            )
        )

    def get_latest_for_portfolio(
        self,
        portfolio_id: int,
    ) -> ReconciliationSLAAudit | None:
        """Return the portfolio's latest SLA audit."""

        statement = (
            select(
                ReconciliationSLAAudit
            )
            .where(
                ReconciliationSLAAudit.portfolio_id
                == portfolio_id
            )
            .order_by(
                ReconciliationSLAAudit.monitored_at.desc(),
                ReconciliationSLAAudit.id.desc(),
            )
        )

        return self.session.scalars(
            statement
        ).first()


__all__ = [
    "ReconciliationSLAAuditRepository",
]