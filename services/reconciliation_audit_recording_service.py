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
from services.reconciliation_exception_service import (
    ReconciliationExceptionService,
)


class ReconciliationAuditRecordingService:
    """Coordinate audit construction and persistence."""

    def __init__(
        self,
        *,
        audit_service: ReconciliationAuditService,
        repository: ReconciliationAuditRepository,
        exception_service: (
            ReconciliationExceptionService | None
        ) = None,
    ) -> None:
        self._audit_service = audit_service
        self._repository = repository
        self._exception_service = (
            exception_service
        )

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

        saved = self._repository.add(
            snapshot
        )

        if self._exception_service is not None:
            self._exception_service.open_for_snapshot(
                snapshot=saved,
                opened_at=recorded_at,
            )

        return saved


__all__ = [
    "ReconciliationAuditRecordingService",
]