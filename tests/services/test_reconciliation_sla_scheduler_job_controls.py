"""Tests for reconciliation SLA scheduler job controls."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
import pytest
from services.reconciliation_sla_scheduled_job import (
    ReconciliationSLAScheduledJob,
)
from services.reconciliation_sla_scheduler import (
    ReconciliationSLAScheduler,
    ReconciliationSLASchedulerConfig,
    ReconciliationSLASchedulerValidationError,
)


POLL_INTERVAL = timedelta(seconds=30)
JOB_INTERVAL = timedelta(minutes=15)
DUE_AT = datetime(
    2026,
    7,
    29,
    10,
    0,
    tzinfo=timezone.utc,
)


def test_registered_job_starts_unpaused() -> None:
    """A newly registered scheduler job should be active."""

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=POLL_INTERVAL,
        )
    )
    job = Mock(
        spec=ReconciliationSLAScheduledJob,
    )

    scheduler.register_job(
        job_id="portfolio-901-sla",
        job=job,
        interval=JOB_INTERVAL,
        next_run_at=DUE_AT,
    )

    status = scheduler.get_job_status(
        job_id="portfolio-901-sla",
    )

    assert status.is_paused is False
def test_pause_job_marks_registered_job_as_paused() -> None:
    """Pausing a registered job should update its observable status."""

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=POLL_INTERVAL,
        )
    )
    job = Mock(
        spec=ReconciliationSLAScheduledJob,
    )

    scheduler.register_job(
        job_id="portfolio-901-sla",
        job=job,
        interval=JOB_INTERVAL,
        next_run_at=DUE_AT,
    )

    scheduler.pause_job(
        job_id="portfolio-901-sla",
    )

    status = scheduler.get_job_status(
        job_id="portfolio-901-sla",
    )

    assert status.is_paused is True
def test_run_due_jobs_skips_paused_job() -> None:
    """A paused job should not execute even when it is due."""

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=POLL_INTERVAL,
        )
    )
    job = Mock(
        spec=ReconciliationSLAScheduledJob,
    )
    job.run_once.return_value = Mock()

    scheduler.register_job(
        job_id="portfolio-901-sla",
        job=job,
        interval=JOB_INTERVAL,
        next_run_at=DUE_AT,
    )
    scheduler.pause_job(
        job_id="portfolio-901-sla",
    )

    results = scheduler.run_due_jobs(
        as_of=DUE_AT,
    )
    status = scheduler.get_job_status(
        job_id="portfolio-901-sla",
    )

    assert results == {}
    job.run_once.assert_not_called()
    assert status.next_run_at == DUE_AT
def test_resume_job_reactivates_paused_job() -> None:
    """Resuming a paused job should allow it to execute again."""

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=POLL_INTERVAL,
        )
    )
    result = Mock()
    job = Mock(
        spec=ReconciliationSLAScheduledJob,
    )
    job.run_once.return_value = result

    scheduler.register_job(
        job_id="portfolio-901-sla",
        job=job,
        interval=JOB_INTERVAL,
        next_run_at=DUE_AT,
    )
    scheduler.pause_job(
        job_id="portfolio-901-sla",
    )

    scheduler.resume_job(
        job_id="portfolio-901-sla",
    )
    results = scheduler.run_due_jobs(
        as_of=DUE_AT,
    )
    status = scheduler.get_job_status(
        job_id="portfolio-901-sla",
    )

    assert status.is_paused is False
    assert results == {
        "portfolio-901-sla": result,
    }
    job.run_once.assert_called_once_with(
        scheduled_at=DUE_AT,
    )
def test_pause_job_rejects_unknown_job_id() -> None:
    """Pausing an unknown job should raise a domain error."""

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=POLL_INTERVAL,
        )
    )

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="job_id is not registered",
    ):
        scheduler.pause_job(
            job_id="portfolio-999-sla",
        )


def test_resume_job_rejects_unknown_job_id() -> None:
    """Resuming an unknown job should raise a domain error."""

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=POLL_INTERVAL,
        )
    )

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="job_id is not registered",
    ):
        scheduler.resume_job(
            job_id="portfolio-999-sla",
        )