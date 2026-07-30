"""Tests for reconciliation SLA scheduler job-state persistence."""

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
    7,
    31,
    10,
    0,
    tzinfo=timezone.utc,
)


def test_register_job_persists_registered_job_state() -> None:
    """Registration should persist the complete observable job state."""

    repository = Mock(
        spec=ReconciliationSLAJobStateRepository,
    )
    repository.load_job_statuses.return_value = ()

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=POLL_INTERVAL,
        ),
        job_state_repository=repository,
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

    repository.save_job_statuses.assert_called_once_with(
        scheduler.job_statuses
    )


def test_register_job_restores_persisted_job_state() -> None:
    """Registration should restore matching state after a restart."""

    persisted_interval = timedelta(minutes=45)
    persisted_next_run_at = datetime(
        2026,
        8,
        1,
        12,
        0,
        tzinfo=timezone.utc,
    )
    persisted_status = ReconciliationSLAJobStatus(
        job_id="portfolio-901-sla",
        interval=persisted_interval,
        next_run_at=persisted_next_run_at,
        is_paused=True,
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
    job = Mock(
        spec=ReconciliationSLAScheduledJob,
    )

    scheduler.register_job(
        job_id="portfolio-901-sla",
        job=job,
        interval=JOB_INTERVAL,
        next_run_at=NEXT_RUN_AT,
    )

    status = scheduler.get_job_status(
        job_id="portfolio-901-sla",
    )

    assert status.interval == persisted_interval
    assert status.next_run_at == persisted_next_run_at
    assert status.is_paused is True


def test_pause_job_persists_paused_state() -> None:
    """Pausing should persist the updated job state."""

    repository = Mock(
        spec=ReconciliationSLAJobStateRepository,
    )
    repository.load_job_statuses.return_value = ()

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=POLL_INTERVAL,
        ),
        job_state_repository=repository,
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
    repository.reset_mock()

    scheduler.pause_job(
        job_id="portfolio-901-sla",
    )

    repository.save_job_statuses.assert_called_once_with(
        scheduler.job_statuses
    )
    assert scheduler.get_job_status(
        job_id="portfolio-901-sla",
    ).is_paused is True


def test_reschedule_job_persists_updated_schedule() -> None:
    """Rescheduling should persist the replacement schedule."""

    repository = Mock(
        spec=ReconciliationSLAJobStateRepository,
    )
    repository.load_job_statuses.return_value = ()

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=POLL_INTERVAL,
        ),
        job_state_repository=repository,
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
    repository.reset_mock()

    updated_interval = timedelta(minutes=30)
    updated_next_run_at = datetime(
        2026,
        7,
        31,
        11,
        0,
        tzinfo=timezone.utc,
    )
    scheduler.reschedule_job(
        job_id="portfolio-901-sla",
        interval=updated_interval,
        next_run_at=updated_next_run_at,
    )

    repository.save_job_statuses.assert_called_once_with(
        scheduler.job_statuses
    )
    status = scheduler.get_job_status(
        job_id="portfolio-901-sla",
    )
    assert status.interval == updated_interval
    assert status.next_run_at == updated_next_run_at


def test_resume_job_persists_resumed_state() -> None:
    """Resuming should persist the updated job state."""

    repository = Mock(
        spec=ReconciliationSLAJobStateRepository,
    )
    repository.load_job_statuses.return_value = ()

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=POLL_INTERVAL,
        ),
        job_state_repository=repository,
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
    repository.reset_mock()

    scheduler.resume_job(
        job_id="portfolio-901-sla",
    )

    repository.save_job_statuses.assert_called_once_with(
        scheduler.job_statuses
    )
    assert scheduler.get_job_status(
        job_id="portfolio-901-sla",
    ).is_paused is False
def test_unregister_job_persists_removal() -> None:
    """Unregistering should remove the job from persisted state."""

    repository = Mock(
        spec=ReconciliationSLAJobStateRepository,
    )
    repository.load_job_statuses.return_value = ()

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=POLL_INTERVAL,
        ),
        job_state_repository=repository,
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
    repository.reset_mock()

    scheduler.unregister_job(
        job_id="portfolio-901-sla",
    )

    repository.save_job_statuses.assert_called_once_with(())
    assert scheduler.registered_job_count == 0
def test_due_job_persists_advanced_next_run() -> None:
    """A successful due run should persist its advanced schedule."""

    repository = Mock(
        spec=ReconciliationSLAJobStateRepository,
    )
    repository.load_job_statuses.return_value = ()

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=POLL_INTERVAL,
        ),
        job_state_repository=repository,
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
    repository.reset_mock()

    scheduler.run_due_jobs(
        as_of=NEXT_RUN_AT,
    )

    repository.save_job_statuses.assert_called_once_with(
        scheduler.job_statuses
    )
    assert scheduler.get_job_status(
        job_id="portfolio-901-sla",
    ).next_run_at == NEXT_RUN_AT + JOB_INTERVAL
def test_register_job_preserves_unregistered_persisted_states() -> None:
    """Restoring one job must not erase other persisted job states."""

    first_status = ReconciliationSLAJobStatus(
        job_id="portfolio-901-sla",
        interval=JOB_INTERVAL,
        next_run_at=NEXT_RUN_AT,
        is_paused=False,
    )
    second_status = ReconciliationSLAJobStatus(
        job_id="portfolio-902-sla",
        interval=timedelta(minutes=30),
        next_run_at=datetime(
            2026,
            7,
            31,
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
        first_status,
        second_status,
    )

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=POLL_INTERVAL,
        ),
        job_state_repository=repository,
    )
    job = Mock(
        spec=ReconciliationSLAScheduledJob,
    )

    scheduler.register_job(
        job_id=first_status.job_id,
        job=job,
        interval=timedelta(minutes=5),
        next_run_at=datetime(
            2026,
            7,
            31,
            9,
            0,
            tzinfo=timezone.utc,
        ),
    )

    repository.save_job_statuses.assert_called_once_with(
        (
            first_status,
            second_status,
        )
    )