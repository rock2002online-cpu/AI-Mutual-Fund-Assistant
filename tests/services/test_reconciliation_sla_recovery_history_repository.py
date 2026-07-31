"""Tests for persistent reconciliation SLA recovery history."""

from datetime import datetime, timezone

import pytest

from services.reconciliation_sla_recovery_history_repository import (
    JSONReconciliationSLARecoveryHistoryRepository,
    ReconciliationSLARecoveryHistoryRepositoryError,
)
from services.reconciliation_sla_scheduler import (
    ReconciliationSLARecoveryReport,
)


def test_json_repository_round_trips_recovery_history(
    tmp_path,
) -> None:
    """Saved recovery reports should load without data loss."""

    repository = JSONReconciliationSLARecoveryHistoryRepository(
        file_path=tmp_path / "recovery-history.json",
    )
    report = ReconciliationSLARecoveryReport(
        recovered_job_ids=(
            "portfolio-901-sla",
            "portfolio-902-sla",
        ),
        missing_job_ids=("portfolio-999-sla",),
        pending_job_ids=("portfolio-903-sla",),
        recorded_at=datetime(
            2026,
            8,
            4,
            10,
            0,
            tzinfo=timezone.utc,
        ),
    )

    repository.save_history((report,))

    assert repository.load_history() == (report,)


def test_json_repository_rejects_invalid_recovery_history(
    tmp_path,
) -> None:
    """Invalid recovery history should raise the repository error."""

    file_path = tmp_path / "recovery-history.json"
    file_path.write_text(
        '[{"recorded_at": "2026-08-04T10:00:00+00:00"}]',
        encoding="utf-8",
    )
    repository = JSONReconciliationSLARecoveryHistoryRepository(
        file_path=file_path,
    )

    with pytest.raises(
        ReconciliationSLARecoveryHistoryRepositoryError,
        match="recovery history file is invalid",
    ):
        repository.load_history()