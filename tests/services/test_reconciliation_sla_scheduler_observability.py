"""Tests for reconciliation SLA scheduler observability."""

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from services.reconciliation_sla_scheduled_job import (
    ReconciliationSLAScheduledJob,
)
from services.reconciliation_sla_scheduler import (
    ReconciliationSLAJobStatus,
    ReconciliationSLAScheduler,
    ReconciliationSLASchedulerConfig,
    ReconciliationSLASchedulerValidationError,
)


POLL_INTERVAL = timedelta(seconds=30)
JOB_INTERVAL = timedelta(minutes=15)
DUE_AT = datetime(
    2026,
    7,
    28,
    10,
    0,
    tzinfo=timezone.utc,
)


def make_scheduler() -> ReconciliationSLAScheduler:
    """Return a scheduler configured for observability tests."""

    return ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=POLL_INTERVAL,
        ),
    )


def register_test_job(
    scheduler: ReconciliationSLAScheduler,
    *,
    job_id: str = "portfolio-901-sla",
    interval: timedelta = JOB_INTERVAL,
    next_run_at: datetime = DUE_AT,
) -> Mock:
    """Register and return a mock scheduled job."""

    job = Mock(spec=ReconciliationSLAScheduledJob)

    scheduler.register_job(
        job_id=job_id,
        job=job,
        interval=interval,
        next_run_at=next_run_at,
    )

    return job


def test_job_status_is_immutable() -> None:
    """A published scheduler job status should be immutable."""

    status = ReconciliationSLAJobStatus(
        job_id="portfolio-901-sla",
        interval=JOB_INTERVAL,
        next_run_at=DUE_AT,
    )

    with pytest.raises(FrozenInstanceError):
        status.job_id = "portfolio-902-sla"


def test_job_statuses_are_empty_without_registered_jobs() -> None:
    """An empty scheduler should publish no job statuses."""

    scheduler = make_scheduler()

    assert scheduler.job_statuses == ()


def test_job_statuses_describe_registered_jobs() -> None:
    """Published statuses should describe jobs in registration order."""

    scheduler = make_scheduler()
    register_test_job(scheduler)
    register_test_job(
        scheduler,
        job_id="portfolio-902-sla",
        interval=timedelta(minutes=30),
        next_run_at=DUE_AT + timedelta(minutes=5),
    )

    assert scheduler.job_statuses == (
        ReconciliationSLAJobStatus(
            job_id="portfolio-901-sla",
            interval=JOB_INTERVAL,
            next_run_at=DUE_AT,
        ),
        ReconciliationSLAJobStatus(
            job_id="portfolio-902-sla",
            interval=timedelta(minutes=30),
            next_run_at=DUE_AT + timedelta(minutes=5),
        ),
    )


def test_get_job_status_returns_requested_job() -> None:
    """A caller should be able to inspect one registered job."""

    scheduler = make_scheduler()
    register_test_job(scheduler)

    assert scheduler.get_job_status(
        job_id="portfolio-901-sla",
    ) == ReconciliationSLAJobStatus(
        job_id="portfolio-901-sla",
        interval=JOB_INTERVAL,
        next_run_at=DUE_AT,
    )


def test_get_job_status_rejects_unknown_job_id() -> None:
    """Looking up an unknown job should raise a domain error."""

    scheduler = make_scheduler()

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="job_id is not registered",
    ):
        scheduler.get_job_status(
            job_id="portfolio-999-sla",
        )


def test_job_status_reflects_advanced_next_run_time() -> None:
    """A status should show the next occurrence after execution."""

    scheduler = make_scheduler()
    job = register_test_job(scheduler)
    job.run_once.return_value = Mock()

    scheduler.run_due_jobs(
        as_of=DUE_AT,
    )

    assert scheduler.get_job_status(
        job_id="portfolio-901-sla",
    ).next_run_at == DUE_AT + JOB_INTERVAL


def test_unregister_job_removes_its_observable_status() -> None:
    """An unregistered job should no longer have a published status."""

    scheduler = make_scheduler()
    register_test_job(scheduler)

    scheduler.unregister_job(
        job_id="portfolio-901-sla",
    )

    assert scheduler.job_statuses == ()