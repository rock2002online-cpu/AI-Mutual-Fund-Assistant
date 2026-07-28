"""Tests for reconciliation SLA scheduler job rescheduling."""

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
INITIAL_INTERVAL = timedelta(minutes=15)
UPDATED_INTERVAL = timedelta(minutes=30)
INITIAL_RUN_AT = datetime(
    2026,
    7,
    30,
    10,
    0,
    tzinfo=timezone.utc,
)
UPDATED_RUN_AT = datetime(
    2026,
    7,
    30,
    11,
    0,
    tzinfo=timezone.utc,
)


def test_reschedule_job_updates_interval_and_next_run() -> None:
    """Rescheduling should atomically update a job's schedule."""

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
        interval=INITIAL_INTERVAL,
        next_run_at=INITIAL_RUN_AT,
    )

    scheduler.reschedule_job(
        job_id="portfolio-901-sla",
        interval=UPDATED_INTERVAL,
        next_run_at=UPDATED_RUN_AT,
    )

    status = scheduler.get_job_status(
        job_id="portfolio-901-sla",
    )

    assert status.interval == UPDATED_INTERVAL
    assert status.next_run_at == UPDATED_RUN_AT
def test_reschedule_job_rejects_unknown_job_id() -> None:
    """Rescheduling an unknown job should raise a domain error."""

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=POLL_INTERVAL,
        )
    )

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="job_id is not registered",
    ):
        scheduler.reschedule_job(
            job_id="portfolio-999-sla",
            interval=UPDATED_INTERVAL,
            next_run_at=UPDATED_RUN_AT,
        )
@pytest.mark.parametrize(
    "interval",
    [
        timedelta(0),
        timedelta(seconds=-1),
    ],
)
def test_reschedule_job_rejects_non_positive_interval(
    interval: timedelta,
) -> None:
    """A replacement schedule should require a positive interval."""

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
        interval=INITIAL_INTERVAL,
        next_run_at=INITIAL_RUN_AT,
    )

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="interval must be positive",
    ):
        scheduler.reschedule_job(
            job_id="portfolio-901-sla",
            interval=interval,
            next_run_at=UPDATED_RUN_AT,
        )

    status = scheduler.get_job_status(
        job_id="portfolio-901-sla",
    )

    assert status.interval == INITIAL_INTERVAL
    assert status.next_run_at == INITIAL_RUN_AT
def test_reschedule_job_rejects_naive_next_run_at() -> None:
    """A replacement next-run timestamp should be timezone-aware."""

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
        interval=INITIAL_INTERVAL,
        next_run_at=INITIAL_RUN_AT,
    )

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="next_run_at must be timezone-aware",
    ):
        scheduler.reschedule_job(
            job_id="portfolio-901-sla",
            interval=UPDATED_INTERVAL,
            next_run_at=datetime(
                2026,
                7,
                30,
                11,
                0,
            ),
        )

    status = scheduler.get_job_status(
        job_id="portfolio-901-sla",
    )

    assert status.interval == INITIAL_INTERVAL
    assert status.next_run_at == INITIAL_RUN_AT
def test_reschedule_job_preserves_paused_state() -> None:
    """Rescheduling should not reactivate a paused job."""

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
        interval=INITIAL_INTERVAL,
        next_run_at=INITIAL_RUN_AT,
    )
    scheduler.pause_job(
        job_id="portfolio-901-sla",
    )

    scheduler.reschedule_job(
        job_id="portfolio-901-sla",
        interval=UPDATED_INTERVAL,
        next_run_at=UPDATED_RUN_AT,
    )
    results = scheduler.run_due_jobs(
        as_of=UPDATED_RUN_AT,
    )
    status = scheduler.get_job_status(
        job_id="portfolio-901-sla",
    )

    assert status.is_paused is True
    assert status.interval == UPDATED_INTERVAL
    assert status.next_run_at == UPDATED_RUN_AT
    assert results == {}
    job.run_once.assert_not_called()
def test_rescheduled_job_executes_using_updated_schedule() -> None:
    """A rescheduled job should execute only at its replacement time."""

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
        interval=INITIAL_INTERVAL,
        next_run_at=INITIAL_RUN_AT,
    )
    scheduler.reschedule_job(
        job_id="portfolio-901-sla",
        interval=UPDATED_INTERVAL,
        next_run_at=UPDATED_RUN_AT,
    )

    early_results = scheduler.run_due_jobs(
        as_of=UPDATED_RUN_AT - timedelta(seconds=1),
    )
    due_results = scheduler.run_due_jobs(
        as_of=UPDATED_RUN_AT,
    )
    status = scheduler.get_job_status(
        job_id="portfolio-901-sla",
    )

    assert early_results == {}
    assert due_results == {
        "portfolio-901-sla": result,
    }
    job.run_once.assert_called_once_with(
        scheduled_at=UPDATED_RUN_AT,
    )
    assert status.next_run_at == (
        UPDATED_RUN_AT + UPDATED_INTERVAL
    )