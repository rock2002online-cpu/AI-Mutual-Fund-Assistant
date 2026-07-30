"""Tests for reconciliation SLA scheduler state recovery."""

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


POLL_INTERVAL = timedelta(seconds=30)
JOB_INTERVAL = timedelta(minutes=15)
NEXT_RUN_AT = datetime(
    2026,
    8,
    1,
    10,
    0,
    tzinfo=timezone.utc,
)


def test_scheduler_exposes_job_ids_pending_recovery() -> None:
    """Persisted jobs should remain visible until runtime registration."""

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

    assert scheduler.pending_recovery_job_ids == (
        "portfolio-901-sla",
    )


def test_registered_job_is_removed_from_pending_recovery() -> None:
    """Registering a persisted job should complete its recovery."""

    persisted_status = ReconciliationSLAJobStatus(
        job_id="portfolio-901-sla",
        interval=JOB_INTERVAL,
        next_run_at=NEXT_RUN_AT,
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
        job_id=persisted_status.job_id,
        job=job,
        interval=timedelta(minutes=5),
        next_run_at=datetime(
            2026,
            8,
            1,
            9,
            0,
            tzinfo=timezone.utc,
        ),
    )

    assert scheduler.pending_recovery_job_ids == ()
    assert scheduler.get_job_status(
        job_id=persisted_status.job_id,
    ) == persisted_status


def test_discard_pending_recovery_removes_persisted_job_state() -> None:
    """An obsolete pending recovery should be removable and persisted."""

    persisted_status = ReconciliationSLAJobStatus(
        job_id="obsolete-portfolio-sla",
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
    repository.reset_mock()

    scheduler.discard_pending_recovery(
        job_id=persisted_status.job_id,
    )

    assert scheduler.pending_recovery_job_ids == ()
    repository.save_job_statuses.assert_called_once_with(())


def test_scheduler_exposes_complete_states_pending_recovery() -> None:
    """Recovery inspection should expose immutable persisted states."""

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
            8,
            1,
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

    assert scheduler.pending_recovery_job_statuses == (
        first_status,
        second_status,
    )


def test_recover_job_registers_job_using_persisted_state() -> None:
    """Recovery should register a runtime job from persisted scheduling data."""

    persisted_status = ReconciliationSLAJobStatus(
        job_id="portfolio-901-sla",
        interval=JOB_INTERVAL,
        next_run_at=NEXT_RUN_AT,
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

    scheduler.recover_job(
        job_id=persisted_status.job_id,
        job=job,
    )

    assert scheduler.get_job_status(
        job_id=persisted_status.job_id,
    ) == persisted_status
    assert scheduler.pending_recovery_job_ids == ()


def test_recover_jobs_registers_multiple_persisted_jobs() -> None:
    """Bulk recovery should restore all supplied runtime jobs."""

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
            8,
            1,
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
    first_job = Mock(
        spec=ReconciliationSLAScheduledJob,
    )
    second_job = Mock(
        spec=ReconciliationSLAScheduledJob,
    )

    recovered_job_ids = scheduler.recover_jobs(
        jobs_by_id={
            first_status.job_id: first_job,
            second_status.job_id: second_job,
        },
    )

    assert recovered_job_ids == (
        first_status.job_id,
        second_status.job_id,
    )
    assert scheduler.registered_job_count == 2
    assert scheduler.pending_recovery_job_ids == ()
    assert scheduler.get_job_status(
        job_id=second_status.job_id,
    ).is_paused is True


def test_recover_jobs_is_atomic_when_any_job_is_not_pending() -> None:
    """Invalid bulk recovery must not leave partially recovered jobs."""

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
    repository.reset_mock()

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="job_id is not pending recovery",
    ):
        scheduler.recover_jobs(
            jobs_by_id={
                persisted_status.job_id: Mock(
                    spec=ReconciliationSLAScheduledJob,
                ),
                "unknown-portfolio-sla": Mock(
                    spec=ReconciliationSLAScheduledJob,
                ),
            },
        )

    assert scheduler.registered_job_count == 0
    assert scheduler.pending_recovery_job_ids == (
        persisted_status.job_id,
    )
    repository.save_job_statuses.assert_not_called()