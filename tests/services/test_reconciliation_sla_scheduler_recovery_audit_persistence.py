"""Tests for scheduler recovery-audit persistence integration."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from services.reconciliation_sla_scheduler import (
    ReconciliationSLARecoveryHistoryRepository,
    ReconciliationSLARecoveryReport,
    ReconciliationSLAScheduler,
    ReconciliationSLASchedulerConfig,
)


RECORDED_AT = datetime(
    2026,
    8,
    4,
    10,
    0,
    tzinfo=timezone.utc,
)


def test_scheduler_loads_persisted_recovery_history() -> None:
    """Scheduler startup should restore persisted recovery reports."""

    persisted_report = ReconciliationSLARecoveryReport(
        recovered_job_ids=("portfolio-901-sla",),
        missing_job_ids=(),
        pending_job_ids=("portfolio-902-sla",),
        recorded_at=RECORDED_AT,
    )
    repository = Mock()
    repository.load_history.return_value = (
        persisted_report,
    )

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=timedelta(seconds=30),
        ),
        recovery_history_repository=repository,
    )

    assert scheduler.recovery_history == (
        persisted_report,
    )
    repository.load_history.assert_called_once_with()


def test_recovery_report_is_persisted_after_creation() -> None:
    """Each generated recovery report should persist the retained history."""

    repository = Mock(
        spec=ReconciliationSLARecoveryHistoryRepository,
    )
    repository.load_history.return_value = ()
    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=timedelta(seconds=30),
        ),
        clock=lambda: RECORDED_AT,
        recovery_history_repository=repository,
    )

    report = scheduler.recover_jobs_with_report(
        jobs_by_id={},
    )

    repository.save_history.assert_called_once_with(
        (report,)
    )


def test_clear_recovery_history_persists_empty_history() -> None:
    """Clearing recovery history should also clear persisted reports."""

    persisted_report = ReconciliationSLARecoveryReport(
        recovered_job_ids=("portfolio-901-sla",),
        missing_job_ids=(),
        pending_job_ids=(),
        recorded_at=RECORDED_AT,
    )
    repository = Mock(
        spec=ReconciliationSLARecoveryHistoryRepository,
    )
    repository.load_history.return_value = (
        persisted_report,
    )
    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=timedelta(seconds=30),
        ),
        recovery_history_repository=repository,
    )
    repository.reset_mock()

    scheduler.clear_recovery_history()

    assert scheduler.recovery_history == ()
    repository.save_history.assert_called_once_with(())