"""Tests for reconciliation SLA scheduler recovery audit trail."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from services.reconciliation_sla_scheduled_job import (
    ReconciliationSLAScheduledJob,
)
from services.reconciliation_sla_scheduler import (
    ReconciliationSLAJobStateRepository,
    ReconciliationSLAJobStatus,
    ReconciliationSLAScheduler,
    ReconciliationSLASchedulerConfig,
    ReconciliationSLASchedulerValidationError,
)


RECOVERY_RECORDED_AT = datetime(
    2026,
    8,
    3,
    10,
    5,
    tzinfo=timezone.utc,
)


def test_scheduler_starts_with_empty_recovery_history() -> None:
    """A new scheduler should expose an empty recovery audit trail."""

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=timedelta(seconds=30),
        ),
    )

    assert scheduler.recovery_history == ()


def test_recover_jobs_with_report_records_recovery_history() -> None:
    """Each reported recovery should be retained in the audit trail."""

    persisted_status = ReconciliationSLAJobStatus(
        job_id="portfolio-901-sla",
        interval=timedelta(minutes=15),
        next_run_at=datetime(
            2026,
            8,
            3,
            10,
            0,
            tzinfo=timezone.utc,
        ),
        is_paused=False,
    )
    repository = Mock(
        spec=ReconciliationSLAJobStateRepository,
    )
    repository.load_job_statuses.return_value = (
        persisted_status,
    )
    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=timedelta(seconds=30),
        ),
        clock=lambda: RECOVERY_RECORDED_AT,
        job_state_repository=repository,
    )

    report = scheduler.recover_jobs_with_report(
        jobs_by_id={
            persisted_status.job_id: Mock(
                spec=ReconciliationSLAScheduledJob,
            ),
        },
    )

    assert scheduler.recovery_history == (report,)
    assert report.recorded_at == RECOVERY_RECORDED_AT


def test_recovery_report_rejects_naive_audit_timestamp() -> None:
    """Recovery audit timestamps must be timezone-aware."""

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=timedelta(seconds=30),
        ),
        clock=lambda: datetime(
            2026,
            8,
            3,
            10,
            5,
        ),
    )

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="recorded_at must be timezone-aware",
    ):
        scheduler.recover_jobs_with_report(
            jobs_by_id={},
        )


def test_clear_recovery_history_removes_all_audit_reports() -> None:
    """Recovery audit history should support explicit cleanup."""

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=timedelta(seconds=30),
        ),
        clock=lambda: RECOVERY_RECORDED_AT,
    )
    scheduler.recover_jobs_with_report(
        jobs_by_id={},
    )
    assert len(scheduler.recovery_history) == 1

    scheduler.clear_recovery_history()

    assert scheduler.recovery_history == ()


def test_recovery_history_respects_configured_retention_limit() -> None:
    """Recovery audit history should retain only the newest reports."""

    clock = Mock(
        side_effect=(
            datetime(
                2026,
                8,
                3,
                10,
                5,
                tzinfo=timezone.utc,
            ),
            datetime(
                2026,
                8,
                3,
                10,
                6,
                tzinfo=timezone.utc,
            ),
            datetime(
                2026,
                8,
                3,
                10,
                7,
                tzinfo=timezone.utc,
            ),
        )
    )
    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=timedelta(seconds=30),
            recovery_history_limit=2,
        ),
        clock=clock,
    )

    first_report = scheduler.recover_jobs_with_report(
        jobs_by_id={},
    )
    second_report = scheduler.recover_jobs_with_report(
        jobs_by_id={},
    )
    third_report = scheduler.recover_jobs_with_report(
        jobs_by_id={},
    )

    assert scheduler.recovery_history == (
        second_report,
        third_report,
    )
    assert first_report not in scheduler.recovery_history