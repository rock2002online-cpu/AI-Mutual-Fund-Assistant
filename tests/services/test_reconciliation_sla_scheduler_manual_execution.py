"""Tests for manual reconciliation SLA scheduler execution."""

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
NEXT_RUN_AT = datetime(
    2026,
    7,
    31,
    11,
    0,
    tzinfo=timezone.utc,
)
MANUAL_RUN_AT = datetime(
    2026,
    7,
    31,
    10,
    0,
    tzinfo=timezone.utc,
)


def test_run_job_now_executes_registered_job_immediately() -> None:
    """Manual execution should run a job before its recurring due time."""

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
        next_run_at=NEXT_RUN_AT,
    )

    returned_result = scheduler.run_job_now(
        job_id="portfolio-901-sla",
        as_of=MANUAL_RUN_AT,
    )

    assert returned_result is result
    job.run_once.assert_called_once_with(
        scheduled_at=MANUAL_RUN_AT,
    )
def test_run_job_now_rejects_unknown_job_id() -> None:
    """Manual execution should reject an unknown scheduler job."""

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=POLL_INTERVAL,
        )
    )

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="job_id is not registered",
    ):
        scheduler.run_job_now(
            job_id="portfolio-999-sla",
            as_of=MANUAL_RUN_AT,
        )
def test_run_job_now_rejects_naive_as_of() -> None:
    """Manual execution should require a timezone-aware timestamp."""

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
        next_run_at=NEXT_RUN_AT,
    )

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="as_of must be timezone-aware",
    ):
        scheduler.run_job_now(
            job_id="portfolio-901-sla",
            as_of=datetime(
                2026,
                7,
                31,
                10,
                0,
            ),
        )

    job.run_once.assert_not_called()
def test_run_job_now_rejects_paused_job() -> None:
    """Manual execution should not bypass an explicit job pause."""

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
        next_run_at=NEXT_RUN_AT,
    )
    scheduler.pause_job(
        job_id="portfolio-901-sla",
    )

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="job_id is paused",
    ):
        scheduler.run_job_now(
            job_id="portfolio-901-sla",
            as_of=MANUAL_RUN_AT,
        )

    job.run_once.assert_not_called()
def test_run_job_now_records_successful_execution() -> None:
    """A successful manual run should be added to execution history."""

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
        next_run_at=NEXT_RUN_AT,
    )

    scheduler.run_job_now(
        job_id="portfolio-901-sla",
        as_of=MANUAL_RUN_AT,
    )

    history = scheduler.execution_history

    assert len(history) == 1
    assert history[0].job_id == "portfolio-901-sla"
    assert history[0].scheduled_at == MANUAL_RUN_AT
    assert history[0].completed_at == MANUAL_RUN_AT
    assert history[0].succeeded is True
    assert history[0].error_message is None
def test_run_job_now_records_failure_and_reraises_error() -> None:
    """A failed manual run should be recorded before its error is reraised."""

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=POLL_INTERVAL,
        )
    )
    failure = RuntimeError(
        "manual SLA execution failed"
    )
    job = Mock(
        spec=ReconciliationSLAScheduledJob,
    )
    job.run_once.side_effect = failure

    scheduler.register_job(
        job_id="portfolio-901-sla",
        job=job,
        interval=JOB_INTERVAL,
        next_run_at=NEXT_RUN_AT,
    )

    with pytest.raises(
        RuntimeError,
        match="manual SLA execution failed",
    ) as raised:
        scheduler.run_job_now(
            job_id="portfolio-901-sla",
            as_of=MANUAL_RUN_AT,
        )

    history = scheduler.execution_history

    assert raised.value is failure
    assert len(history) == 1
    assert history[0].job_id == "portfolio-901-sla"
    assert history[0].scheduled_at == MANUAL_RUN_AT
    assert history[0].completed_at == MANUAL_RUN_AT
    assert history[0].succeeded is False
    assert history[0].error_message == (
        "manual SLA execution failed"
    )
def test_run_job_now_preserves_recurring_next_run() -> None:
    """A manual run should not consume or advance the recurring schedule."""

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
        next_run_at=NEXT_RUN_AT,
    )

    scheduler.run_job_now(
        job_id="portfolio-901-sla",
        as_of=MANUAL_RUN_AT,
    )

    status = scheduler.get_job_status(
        job_id="portfolio-901-sla",
    )

    assert status.interval == JOB_INTERVAL
    assert status.next_run_at == NEXT_RUN_AT
    assert status.is_paused is False