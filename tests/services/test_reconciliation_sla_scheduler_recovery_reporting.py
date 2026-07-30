"""Tests for reconciliation SLA scheduler recovery reporting."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from services.reconciliation_sla_scheduled_job import (
    ReconciliationSLAScheduledJob,
)
from services.reconciliation_sla_scheduler import (
    ReconciliationSLAJobStateRepository,
    ReconciliationSLAJobStatus,
    ReconciliationSLAScheduler,
    ReconciliationSLASchedulerConfig,
)


POLL_INTERVAL = timedelta(seconds=30)
JOB_INTERVAL = timedelta(minutes=15)
NEXT_RUN_AT = datetime(
    2026,
    8,
    2,
    10,
    0,
    tzinfo=timezone.utc,
)


def test_recover_jobs_with_report_identifies_recovered_and_pending_jobs(
) -> None:
    """Recovery reporting should distinguish recovered and pending jobs."""

    recovered_status = ReconciliationSLAJobStatus(
        job_id="portfolio-901-sla",
        interval=JOB_INTERVAL,
        next_run_at=NEXT_RUN_AT,
        is_paused=False,
    )
    pending_status = ReconciliationSLAJobStatus(
        job_id="portfolio-902-sla",
        interval=timedelta(minutes=30),
        next_run_at=datetime(
            2026,
            8,
            2,
            11,
            0,
            tzinfo=timezone.utc,
        ),
        is_paused=True,
    )
    repository = Mock(
        spec=ReconciliationSLAJobStateRepository,
    )
    repository.load_job_statuses.return_value = (
        recovered_status,
        pending_status,
    )
    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=POLL_INTERVAL,
        ),
        job_state_repository=repository,
    )

    report = scheduler.recover_jobs_with_report(
        jobs_by_id={
            recovered_status.job_id: Mock(
                spec=ReconciliationSLAScheduledJob,
            ),
        },
    )

    assert report.recovered_job_ids == (
        recovered_status.job_id,
    )
    assert report.pending_job_ids == (
        pending_status.job_id,
    )


def test_recovery_report_identifies_jobs_without_persisted_state() -> None:
    """Runtime jobs without stored state should be reported as missing."""

    persisted_status = ReconciliationSLAJobStatus(
        job_id="portfolio-901-sla",
        interval=JOB_INTERVAL,
        next_run_at=NEXT_RUN_AT,
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
            poll_interval=POLL_INTERVAL,
        ),
        job_state_repository=repository,
    )

    report = scheduler.recover_jobs_with_report(
        jobs_by_id={
            persisted_status.job_id: Mock(
                spec=ReconciliationSLAScheduledJob,
            ),
            "portfolio-999-sla": Mock(
                spec=ReconciliationSLAScheduledJob,
            ),
        },
    )

    assert report.recovered_job_ids == (
        persisted_status.job_id,
    )
    assert report.missing_job_ids == (
        "portfolio-999-sla",
    )
    assert report.pending_job_ids == ()
    assert report.recovered_job_count == 1
    assert report.missing_job_count == 1
    assert report.pending_job_count == 0


def test_recovery_report_is_complete_when_no_jobs_are_missing_or_pending(
) -> None:
    """A report should be complete when every persisted job is recovered."""

    persisted_status = ReconciliationSLAJobStatus(
        job_id="portfolio-901-sla",
        interval=JOB_INTERVAL,
        next_run_at=NEXT_RUN_AT,
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
            poll_interval=POLL_INTERVAL,
        ),
        job_state_repository=repository,
    )

    report = scheduler.recover_jobs_with_report(
        jobs_by_id={
            persisted_status.job_id: Mock(
                spec=ReconciliationSLAScheduledJob,
            ),
        },
    )

    assert report.is_complete is True