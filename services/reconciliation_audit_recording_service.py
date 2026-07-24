"""Persist portfolio reconciliation audit snapshots."""

from __future__ import annotations

from datetime import datetime

from models.reconciliation_audit import (
    ReconciliationAuditSnapshot,
)
from repositories.reconciliation_audit_repository import (
    ReconciliationAuditRepository,
)
from services.portfolio_reconciliation_service import (
    PortfolioReconciliationResult,
)
from services.reconciliation_audit_service import (
    ReconciliationAuditService,
)


class ReconciliationAuditRecordingService:
    """Coordinate audit construction and persistence."""

    def __init__(
        self,
        *,
        audit_service: ReconciliationAuditService,
        repository: ReconciliationAuditRepository,
    ) -> None:
        self._audit_service = audit_service
        self._repository = repository

    def record_snapshot(
        self,
        *,
        portfolio_id: int,
        result: PortfolioReconciliationResult,
        recorded_at: datetime,
    ) -> ReconciliationAuditSnapshot:
        """Build and persist one reconciliation audit snapshot."""

        snapshot = (
            self._audit_service.build_snapshot(
                portfolio_id=portfolio_id,
                result=result,
                recorded_at=recorded_at,
            )
        )

        return self._repository.add(
            snapshot
        )


__all__ = [
    "ReconciliationAuditRecordingService",
]