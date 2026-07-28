"""Tests for reconciliation SLA scheduler execution history."""

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from services.reconciliation_sla_scheduled_job import (
    ReconciliationSLAScheduledJob,
    ReconciliationSLAScheduledJobResult,
)
from services.reconciliation_sla_scheduler import (
    ReconciliationSLAJobExecution,
    ReconciliationSLAScheduler,
    ReconciliationSLASchedulerConfig,
    ReconciliationSLASchedulerValidationError,
)


SCHEDULED_AT = datetime(
    2026,
    7,
    28,
    10,
    0,
    tzinfo=timezone.utc,
)
COMPLETED_AT = SCHEDULED_AT + timedelta(seconds=5)


def make_scheduler() -> ReconciliationSLAScheduler:
    """Return a scheduler configured for execution-history tests."""

    return ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=timedelta(seconds=30),
        ),
    )


def test_job_execution_is_immutable() -> None:
    """A published scheduler execution record should be immutable."""

    execution = ReconciliationSLAJobExecution(
        job_id="portfolio-901-sla",
        scheduled_at=SCHEDULED_AT,
        succeeded=True,
    )

    with pytest.raises(FrozenInstanceError):
        execution.job_id = "portfolio-902-sla"


def test_job_execution_rejects_blank_job_id() -> None:
    """An execution record should require a meaningful job ID."""

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="job_id must not be blank",
    ):
        ReconciliationSLAJobExecution(
            job_id="   ",
            scheduled_at=SCHEDULED_AT,
            succeeded=True,
        )


def test_job_execution_rejects_naive_scheduled_at() -> None:
    """An execution record should require a timezone-aware timestamp."""

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="scheduled_at must be timezone-aware",
    ):
        ReconciliationSLAJobExecution(
            job_id="portfolio-901-sla",
            scheduled_at=datetime(
                2026,
                7,
                28,
                10,
                0,
            ),
            succeeded=True,
        )


def test_job_execution_exposes_successful_outcome() -> None:
    """An execution record should identify a successful run."""

    execution = ReconciliationSLAJobExecution(
        job_id="portfolio-901-sla",
        scheduled_at=SCHEDULED_AT,
        succeeded=True,
    )

    assert execution.succeeded is True


def test_successful_execution_rejects_error_message() -> None:
    """A successful execution should not contain failure details."""

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="successful execution cannot have an error message",
    ):
        ReconciliationSLAJobExecution(
            job_id="portfolio-901-sla",
            scheduled_at=SCHEDULED_AT,
            succeeded=True,
            error_message="Unexpected failure details.",
        )


def test_failed_execution_requires_error_message() -> None:
    """A failed execution should contain meaningful failure details."""

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="failed execution must have an error message",
    ):
        ReconciliationSLAJobExecution(
            job_id="portfolio-901-sla",
            scheduled_at=SCHEDULED_AT,
            succeeded=False,
        )


def test_job_execution_exposes_completion_time() -> None:
    """An execution record should expose when the run completed."""

    execution = ReconciliationSLAJobExecution(
        job_id="portfolio-901-sla",
        scheduled_at=SCHEDULED_AT,
        succeeded=True,
        completed_at=COMPLETED_AT,
    )

    assert execution.completed_at == COMPLETED_AT


def test_job_execution_rejects_naive_completed_at() -> None:
    """Completion time should be timezone-aware when provided."""

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="completed_at must be timezone-aware",
    ):
        ReconciliationSLAJobExecution(
            job_id="portfolio-901-sla",
            scheduled_at=SCHEDULED_AT,
            succeeded=True,
            completed_at=datetime(
                2026,
                7,
                28,
                10,
                0,
                5,
            ),
        )


def test_job_execution_rejects_completion_before_scheduled_time() -> None:
    """An execution cannot complete before its scheduled occurrence."""

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="completed_at cannot be before scheduled_at",
    ):
        ReconciliationSLAJobExecution(
            job_id="portfolio-901-sla",
            scheduled_at=SCHEDULED_AT,
            succeeded=True,
            completed_at=SCHEDULED_AT - timedelta(seconds=1),
        )


def test_job_execution_exposes_attempts_used() -> None:
    """An execution record should expose how many attempts were used."""

    execution = ReconciliationSLAJobExecution(
        job_id="portfolio-901-sla",
        scheduled_at=SCHEDULED_AT,
        succeeded=True,
        completed_at=COMPLETED_AT,
        attempts_used=2,
    )

    assert execution.attempts_used == 2


@pytest.mark.parametrize(
    "attempts_used",
    [
        0,
        -1,
    ],
)
def test_job_execution_rejects_non_positive_attempts_used(
    attempts_used: int,
) -> None:
    """An execution attempts count should be positive when provided."""

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="attempts_used must be positive",
    ):
        ReconciliationSLAJobExecution(
            job_id="portfolio-901-sla",
            scheduled_at=SCHEDULED_AT,
            succeeded=True,
            completed_at=COMPLETED_AT,
            attempts_used=attempts_used,
        )


def test_execution_history_is_empty_before_any_job_runs() -> None:
    """A new scheduler should expose no execution records."""

    scheduler = make_scheduler()

    assert scheduler.execution_history == ()


def test_successful_due_job_is_added_to_execution_history() -> None:
    """A successful scheduled run should create an execution record."""

    scheduler = make_scheduler()
    job = Mock(spec=ReconciliationSLAScheduledJob)
    job.run_once.return_value = Mock()

    scheduler.register_job(
        job_id="portfolio-901-sla",
        job=job,
        interval=timedelta(minutes=15),
        next_run_at=SCHEDULED_AT,
    )

    scheduler.run_due_jobs(as_of=COMPLETED_AT)

    assert scheduler.execution_history == (
        ReconciliationSLAJobExecution(
            job_id="portfolio-901-sla",
            scheduled_at=SCHEDULED_AT,
            succeeded=True,
            completed_at=COMPLETED_AT,
        ),
    )


def test_successful_due_job_records_attempts_used() -> None:
    """Successful history should preserve the scheduled-job attempts."""

    scheduler = make_scheduler()
    result = Mock(spec=ReconciliationSLAScheduledJobResult)
    result.attempts_used = 2
    job = Mock(spec=ReconciliationSLAScheduledJob)
    job.run_once.return_value = result

    scheduler.register_job(
        job_id="portfolio-901-sla",
        job=job,
        interval=timedelta(minutes=15),
        next_run_at=SCHEDULED_AT,
    )

    scheduler.run_due_jobs(as_of=COMPLETED_AT)

    assert scheduler.execution_history == (
        ReconciliationSLAJobExecution(
            job_id="portfolio-901-sla",
            scheduled_at=SCHEDULED_AT,
            succeeded=True,
            completed_at=COMPLETED_AT,
            attempts_used=2,
        ),
    )


def test_failed_due_job_is_added_to_execution_history() -> None:
    """A failed scheduled run should create a failed execution record."""

    scheduler = make_scheduler()
    error = RuntimeError("Scheduled SLA job failed.")
    job = Mock(spec=ReconciliationSLAScheduledJob)
    job.run_once.side_effect = error

    scheduler.register_job(
        job_id="portfolio-901-sla",
        job=job,
        interval=timedelta(minutes=15),
        next_run_at=SCHEDULED_AT,
    )

    with pytest.raises(
        RuntimeError,
        match="Scheduled SLA job failed",
    ) as raised:
        scheduler.run_due_jobs(as_of=COMPLETED_AT)

    assert raised.value is error
    assert scheduler.execution_history == (
        ReconciliationSLAJobExecution(
            job_id="portfolio-901-sla",
            scheduled_at=SCHEDULED_AT,
            succeeded=False,
            error_message="Scheduled SLA job failed.",
            completed_at=COMPLETED_AT,
        ),
    )


def test_get_execution_history_returns_requested_job_records() -> None:
    """A caller should retrieve execution records for one job."""

    scheduler = make_scheduler()
    first_job = Mock(spec=ReconciliationSLAScheduledJob)
    first_job.run_once.return_value = Mock()
    second_job = Mock(spec=ReconciliationSLAScheduledJob)
    second_job.run_once.return_value = Mock()

    scheduler.register_job(
        job_id="portfolio-901-sla",
        job=first_job,
        interval=timedelta(minutes=15),
        next_run_at=SCHEDULED_AT,
    )
    scheduler.register_job(
        job_id="portfolio-902-sla",
        job=second_job,
        interval=timedelta(minutes=15),
        next_run_at=SCHEDULED_AT,
    )

    scheduler.run_due_jobs(as_of=COMPLETED_AT)

    assert scheduler.get_execution_history(
        job_id="portfolio-901-sla",
    ) == (
        ReconciliationSLAJobExecution(
            job_id="portfolio-901-sla",
            scheduled_at=SCHEDULED_AT,
            succeeded=True,
            completed_at=COMPLETED_AT,
        ),
    )


def test_get_execution_history_rejects_blank_job_id() -> None:
    """History filtering should require a meaningful job ID."""

    scheduler = make_scheduler()

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="job_id must not be blank",
    ):
        scheduler.get_execution_history(job_id="   ")


def test_clear_execution_history_removes_all_records() -> None:
    """A caller should be able to remove all execution records."""

    scheduler = make_scheduler()
    job = Mock(spec=ReconciliationSLAScheduledJob)
    job.run_once.return_value = Mock()

    scheduler.register_job(
        job_id="portfolio-901-sla",
        job=job,
        interval=timedelta(minutes=15),
        next_run_at=SCHEDULED_AT,
    )
    scheduler.run_due_jobs(as_of=COMPLETED_AT)

    scheduler.clear_execution_history()

    assert scheduler.execution_history == ()


def test_remove_execution_history_removes_only_requested_job() -> None:
    """Removing one job's history should preserve other records."""

    scheduler = make_scheduler()
    first_job = Mock(spec=ReconciliationSLAScheduledJob)
    first_job.run_once.return_value = Mock()
    second_job = Mock(spec=ReconciliationSLAScheduledJob)
    second_job.run_once.return_value = Mock()

    scheduler.register_job(
        job_id="portfolio-901-sla",
        job=first_job,
        interval=timedelta(minutes=15),
        next_run_at=SCHEDULED_AT,
    )
    scheduler.register_job(
        job_id="portfolio-902-sla",
        job=second_job,
        interval=timedelta(minutes=15),
        next_run_at=SCHEDULED_AT,
    )
    scheduler.run_due_jobs(as_of=COMPLETED_AT)

    scheduler.remove_execution_history(
        job_id="portfolio-901-sla",
    )

    assert scheduler.execution_history == (
        ReconciliationSLAJobExecution(
            job_id="portfolio-902-sla",
            scheduled_at=SCHEDULED_AT,
            succeeded=True,
            completed_at=COMPLETED_AT,
        ),
    )


def test_remove_execution_history_rejects_blank_job_id() -> None:
    """History removal should require a meaningful job ID."""

    scheduler = make_scheduler()

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="job_id must not be blank",
    ):
        scheduler.remove_execution_history(job_id="   ")


def test_scheduler_config_accepts_execution_history_limit() -> None:
    """Scheduler configuration should expose a history retention limit."""

    config = ReconciliationSLASchedulerConfig(
        poll_interval=timedelta(seconds=30),
        execution_history_limit=100,
    )

    assert config.execution_history_limit == 100


@pytest.mark.parametrize(
    "execution_history_limit",
    [
        0,
        -1,
    ],
)
def test_scheduler_config_rejects_non_positive_history_limit(
    execution_history_limit: int,
) -> None:
    """Execution-history retention should require a positive limit."""

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="execution_history_limit must be positive",
    ):
        ReconciliationSLASchedulerConfig(
            poll_interval=timedelta(seconds=30),
            execution_history_limit=execution_history_limit,
        )


def test_execution_history_keeps_only_most_recent_records() -> None:
    """History should discard oldest records beyond its limit."""

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=timedelta(seconds=30),
            execution_history_limit=1,
        ),
    )
    job = Mock(spec=ReconciliationSLAScheduledJob)
    job.run_once.return_value = Mock()
    interval = timedelta(minutes=15)

    scheduler.register_job(
        job_id="portfolio-901-sla",
        job=job,
        interval=interval,
        next_run_at=SCHEDULED_AT,
    )

    scheduler.run_due_jobs(as_of=SCHEDULED_AT)
    scheduler.run_due_jobs(
        as_of=SCHEDULED_AT + interval,
    )

    assert scheduler.execution_history == (
        ReconciliationSLAJobExecution(
            job_id="portfolio-901-sla",
            scheduled_at=SCHEDULED_AT + interval,
            succeeded=True,
            completed_at=SCHEDULED_AT + interval,
        ),
    )
def test_get_latest_execution_returns_most_recent_job_record() -> None:
    """A caller should retrieve the latest execution for one job."""

    scheduler = make_scheduler()
    job = Mock(spec=ReconciliationSLAScheduledJob)
    job.run_once.return_value = Mock()
    interval = timedelta(minutes=15)

    scheduler.register_job(
        job_id="portfolio-901-sla",
        job=job,
        interval=interval,
        next_run_at=SCHEDULED_AT,
    )

    scheduler.run_due_jobs(as_of=SCHEDULED_AT)
    scheduler.run_due_jobs(
        as_of=SCHEDULED_AT + interval,
    )

    assert scheduler.get_latest_execution(
        job_id="portfolio-901-sla",
    ) == ReconciliationSLAJobExecution(
        job_id="portfolio-901-sla",
        scheduled_at=SCHEDULED_AT + interval,
        succeeded=True,
        completed_at=SCHEDULED_AT + interval,
    )
def test_get_latest_execution_rejects_job_without_history() -> None:
    """Latest execution lookup should reject a job without history."""

    scheduler = make_scheduler()

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="job_id has no execution history",
    ):
        scheduler.get_latest_execution(
            job_id="portfolio-999-sla",
        )