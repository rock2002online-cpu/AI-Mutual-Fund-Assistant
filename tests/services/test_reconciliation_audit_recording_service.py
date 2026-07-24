"""Tests for reconciliation audit recording orchestration."""

from datetime import datetime, timezone
from unittest.mock import Mock

from models.reconciliation_audit import (
    ReconciliationAuditSnapshot,
)
from repositories.reconciliation_audit_repository import (
    ReconciliationAuditRepository,
)
from services.portfolio_reconciliation_service import (
    PortfolioReconciliationResult,
)
from services.reconciliation_audit_recording_service import (
    ReconciliationAuditRecordingService,
)
from services.reconciliation_audit_service import (
    ReconciliationAuditService,
)


def test_record_snapshot_builds_and_persists_audit() -> None:
    """Recording should delegate construction and repository persistence."""

    recorded_at = datetime(
        2026,
        7,
        24,
        12,
        0,
        tzinfo=timezone.utc,
    )
    result = PortfolioReconciliationResult(
        items=[],
        is_reconciled=True,
    )
    snapshot = Mock(
        spec=ReconciliationAuditSnapshot,
    )

    audit_service = Mock(
        spec=ReconciliationAuditService,
    )
    audit_service.build_snapshot.return_value = (
        snapshot
    )

    repository = Mock(
        spec=ReconciliationAuditRepository,
    )
    repository.add.return_value = snapshot

    service = ReconciliationAuditRecordingService(
        audit_service=audit_service,
        repository=repository,
    )

    saved = service.record_snapshot(
        portfolio_id=10,
        result=result,
        recorded_at=recorded_at,
    )

    assert saved is snapshot

    audit_service.build_snapshot.assert_called_once_with(
        portfolio_id=10,
        result=result,
        recorded_at=recorded_at,
    )
    repository.add.assert_called_once_with(
        snapshot
    )