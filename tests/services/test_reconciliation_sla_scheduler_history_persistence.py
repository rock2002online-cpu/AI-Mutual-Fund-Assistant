"""Tests for scheduler execution-history persistence integration."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from services.reconciliation_sla_scheduled_job import (
    ReconciliationSLAScheduledJob,
    ReconciliationSLAScheduledJobResult,
)
from services.reconciliation_sla_scheduler import (
    ReconciliationSLAJobExecution,
    ReconciliationSLAScheduler,
    ReconciliationSLASchedulerConfig,
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


def make_successful_execution(
    *,
    job_id: str = "portfolio-901-sla",
) -> ReconciliationSLAJobExecution:
    """Return a valid persisted scheduler execution."""

    return ReconciliationSLAJobExecution(
        job_id=job_id,
        scheduled_at=SCHEDULED_AT,
        succeeded=True,
        completed_at=COMPLETED_AT,
        attempts_used=2,
    )


def make_repository(
    history: tuple[ReconciliationSLAJobExecution, ...] = (),
) -> Mock:
    """Return an execution-history repository mock."""

    repository = Mock()
    repository.load_history.return_value = history

    return repository


def make_scheduler(
    repository: Mock,
) -> ReconciliationSLAScheduler:
    """Return a scheduler using the supplied repository."""

    return ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=timedelta(seconds=30),
        ),
        execution_history_repository=repository,
    )


def test_scheduler_restores_persisted_execution_history() -> None:
    """A scheduler should restore history supplied by its repository."""

    execution = make_successful_execution()
    repository = make_repository((execution,))

    scheduler = make_scheduler(repository)

    assert scheduler.execution_history == (execution,)
    repository.load_history.assert_called_once_with()


def test_scheduler_persists_new_successful_execution() -> None:
    """Recording a successful run should persist the updated history."""

    repository = make_repository()
    scheduler = make_scheduler(repository)
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

    repository.save_history.assert_called_once_with(
        (make_successful_execution(),)
    )


def test_clear_execution_history_persists_empty_history() -> None:
    """Clearing scheduler history should also clear persisted history."""

    execution = make_successful_execution()
    repository = make_repository((execution,))
    scheduler = make_scheduler(repository)

    scheduler.clear_execution_history()

    assert scheduler.execution_history == ()
    repository.save_history.assert_called_once_with(())


def test_remove_execution_history_persists_remaining_jobs() -> None:
    """Removing one job's history should persist the remaining records."""

    removed_execution = make_successful_execution(
        job_id="portfolio-901-sla",
    )
    remaining_execution = make_successful_execution(
        job_id="portfolio-902-sla",
    )
    repository = make_repository(
        (
            removed_execution,
            remaining_execution,
        )
    )
    scheduler = make_scheduler(repository)

    scheduler.remove_execution_history(
        job_id="portfolio-901-sla",
    )

    assert scheduler.execution_history == (
        remaining_execution,
    )
    repository.save_history.assert_called_once_with(
        (remaining_execution,)
    )
def test_scheduler_applies_retention_to_restored_history() -> None:
    """Restored history should respect the configured retention limit."""

    older_execution = make_successful_execution(
        job_id="portfolio-901-sla",
    )
    newer_execution = ReconciliationSLAJobExecution(
        job_id="portfolio-902-sla",
        scheduled_at=SCHEDULED_AT + timedelta(minutes=15),
        succeeded=True,
        completed_at=COMPLETED_AT + timedelta(minutes=15),
        attempts_used=1,
    )
    repository = make_repository(
        (
            older_execution,
            newer_execution,
        )
    )

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=timedelta(seconds=30),
            execution_history_limit=1,
        ),
        execution_history_repository=repository,
    )

    assert scheduler.execution_history == (
        newer_execution,
    )