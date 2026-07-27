"""Tests for reconciliation SLA scheduler orchestration."""

from dataclasses import FrozenInstanceError
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
    28,
    10,
    0,
    tzinfo=timezone.utc,
)


def make_scheduler(
    *,
    clock: Mock | None = None,
    delay: Mock | None = None,
) -> ReconciliationSLAScheduler:
    """Return a scheduler configured for focused unit tests."""

    arguments: dict[str, object] = {
        "config": ReconciliationSLASchedulerConfig(
            poll_interval=POLL_INTERVAL,
        ),
    }

    if clock is not None:
        arguments["clock"] = clock

    if delay is not None:
        arguments["delay"] = delay

    return ReconciliationSLAScheduler(**arguments)


def register_test_job(
    scheduler: ReconciliationSLAScheduler,
    *,
    job: Mock | None = None,
    job_id: str = "portfolio-901-sla",
    interval: timedelta = JOB_INTERVAL,
    next_run_at: datetime = DUE_AT,
) -> Mock:
    """Register and return a mock scheduled job."""

    scheduled_job = job or Mock(
        spec=ReconciliationSLAScheduledJob,
    )

    scheduler.register_job(
        job_id=job_id,
        job=scheduled_job,
        interval=interval,
        next_run_at=next_run_at,
    )

    return scheduled_job


def test_scheduler_config_is_immutable() -> None:
    """Scheduler configuration should not change after creation."""

    config = ReconciliationSLASchedulerConfig(
        poll_interval=POLL_INTERVAL,
    )

    with pytest.raises(FrozenInstanceError):
        config.poll_interval = timedelta(seconds=60)


@pytest.mark.parametrize(
    "poll_interval",
    [
        timedelta(0),
        timedelta(seconds=-1),
    ],
)
def test_scheduler_config_rejects_non_positive_poll_interval(
    poll_interval: timedelta,
) -> None:
    """Scheduler polling should require a positive interval."""

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="poll_interval must be positive",
    ):
        ReconciliationSLASchedulerConfig(
            poll_interval=poll_interval,
        )


def test_register_job_adds_job_to_scheduler() -> None:
    """A scheduler should retain a registered recurring job."""

    scheduler = make_scheduler()

    register_test_job(scheduler)

    assert scheduler.registered_job_count == 1
    assert scheduler.registered_job_ids == (
        "portfolio-901-sla",
    )


@pytest.mark.parametrize(
    "job_id",
    [
        "",
        "   ",
    ],
)
def test_register_job_rejects_blank_job_id(
    job_id: str,
) -> None:
    """A registered job should require a meaningful identifier."""

    scheduler = make_scheduler()

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="job_id must not be blank",
    ):
        register_test_job(
            scheduler,
            job_id=job_id,
        )

    assert scheduler.registered_job_count == 0


@pytest.mark.parametrize(
    "interval",
    [
        timedelta(0),
        timedelta(seconds=-1),
    ],
)
def test_register_job_rejects_non_positive_interval(
    interval: timedelta,
) -> None:
    """A recurring job should require a positive interval."""

    scheduler = make_scheduler()

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="interval must be positive",
    ):
        register_test_job(
            scheduler,
            interval=interval,
        )

    assert scheduler.registered_job_count == 0


def test_register_job_rejects_naive_next_run_at() -> None:
    """A job's next execution timestamp should be timezone-aware."""

    scheduler = make_scheduler()

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="next_run_at must be timezone-aware",
    ):
        register_test_job(
            scheduler,
            next_run_at=datetime(
                2026,
                7,
                28,
                10,
                0,
            ),
        )

    assert scheduler.registered_job_count == 0


def test_register_job_rejects_duplicate_job_id() -> None:
    """A scheduler should not replace an existing registration."""

    scheduler = make_scheduler()
    register_test_job(scheduler)

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="job_id is already registered",
    ):
        register_test_job(scheduler)

    assert scheduler.registered_job_count == 1
    assert scheduler.registered_job_ids == (
        "portfolio-901-sla",
    )


def test_run_due_jobs_executes_job_due_at_as_of() -> None:
    """A scheduler should execute a job whose run time has arrived."""

    scheduler = make_scheduler()
    scheduled_result = Mock()
    job = Mock(
        spec=ReconciliationSLAScheduledJob,
    )
    job.run_once.return_value = scheduled_result
    register_test_job(
        scheduler,
        job=job,
    )

    results = scheduler.run_due_jobs(
        as_of=DUE_AT,
    )

    assert results == {
        "portfolio-901-sla": scheduled_result,
    }
    job.run_once.assert_called_once_with(
        scheduled_at=DUE_AT,
    )


def test_run_due_jobs_does_not_repeat_completed_occurrence() -> None:
    """A completed scheduled occurrence should run only once."""

    scheduler = make_scheduler()
    scheduled_result = Mock()
    job = Mock(
        spec=ReconciliationSLAScheduledJob,
    )
    job.run_once.return_value = scheduled_result
    register_test_job(
        scheduler,
        job=job,
    )

    first_results = scheduler.run_due_jobs(
        as_of=DUE_AT,
    )
    duplicate_results = scheduler.run_due_jobs(
        as_of=DUE_AT,
    )

    assert first_results == {
        "portfolio-901-sla": scheduled_result,
    }
    assert duplicate_results == {}
    job.run_once.assert_called_once_with(
        scheduled_at=DUE_AT,
    )


def test_run_due_jobs_skips_future_job() -> None:
    """A scheduler should not execute a job before its due time."""

    scheduler = make_scheduler()
    job = register_test_job(scheduler)

    results = scheduler.run_due_jobs(
        as_of=DUE_AT - timedelta(seconds=1),
    )

    assert results == {}
    job.run_once.assert_not_called()


def test_run_due_jobs_rejects_naive_as_of() -> None:
    """Scheduler execution should require a timezone-aware timestamp."""

    scheduler = make_scheduler()

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="as_of must be timezone-aware",
    ):
        scheduler.run_due_jobs(
            as_of=datetime(
                2026,
                7,
                28,
                10,
                0,
            ),
        )


def test_start_marks_scheduler_as_running() -> None:
    """Starting a stopped scheduler should activate its lifecycle."""

    scheduler = make_scheduler()

    assert scheduler.is_running is False

    scheduler.start()

    assert scheduler.is_running is True


def test_stop_marks_scheduler_as_not_running() -> None:
    """Stopping a running scheduler should end its lifecycle."""

    scheduler = make_scheduler()
    scheduler.start()

    assert scheduler.is_running is True

    scheduler.stop()

    assert scheduler.is_running is False


def test_run_cycle_executes_due_jobs_while_running() -> None:
    """A running scheduler cycle should execute due jobs."""

    scheduler = make_scheduler()
    scheduled_result = Mock()
    job = Mock(
        spec=ReconciliationSLAScheduledJob,
    )
    job.run_once.return_value = scheduled_result
    register_test_job(
        scheduler,
        job=job,
    )
    scheduler.start()

    results = scheduler.run_cycle(
        as_of=DUE_AT,
    )

    assert results == {
        "portfolio-901-sla": scheduled_result,
    }
    job.run_once.assert_called_once_with(
        scheduled_at=DUE_AT,
    )


def test_run_cycle_does_not_execute_jobs_while_stopped() -> None:
    """A stopped scheduler cycle should not execute due jobs."""

    scheduler = make_scheduler()
    job = register_test_job(scheduler)

    results = scheduler.run_cycle(
        as_of=DUE_AT,
    )

    assert results == {}
    job.run_once.assert_not_called()


def test_wait_for_next_cycle_uses_poll_interval() -> None:
    """Scheduler waiting should use its configured polling interval."""

    delay = Mock()
    scheduler = make_scheduler(
        delay=delay,
    )

    scheduler.wait_for_next_cycle()

    delay.assert_called_once_with(30.0)


def test_run_forever_executes_cycles_until_stopped() -> None:
    """The lifecycle loop should run and poll until stopped."""

    scheduled_result = Mock()
    job = Mock(
        spec=ReconciliationSLAScheduledJob,
    )
    job.run_once.return_value = scheduled_result
    clock = Mock(
        return_value=DUE_AT,
    )
    delay = Mock()
    scheduler = make_scheduler(
        clock=clock,
        delay=delay,
    )
    register_test_job(
        scheduler,
        job=job,
    )
    delay.side_effect = lambda _: scheduler.stop()

    scheduler.run_forever()

    assert scheduler.is_running is False
    clock.assert_called_once_with()
    job.run_once.assert_called_once_with(
        scheduled_at=DUE_AT,
    )
    delay.assert_called_once_with(30.0)


def test_run_forever_stops_after_unhandled_job_failure() -> None:
    """An unhandled job failure should leave the scheduler stopped."""

    error = RuntimeError(
        "Scheduled SLA job failed."
    )
    job = Mock(
        spec=ReconciliationSLAScheduledJob,
    )
    job.run_once.side_effect = error
    clock = Mock(
        return_value=DUE_AT,
    )
    delay = Mock()
    scheduler = make_scheduler(
        clock=clock,
        delay=delay,
    )
    register_test_job(
        scheduler,
        job=job,
    )

    with pytest.raises(
        RuntimeError,
        match="Scheduled SLA job failed",
    ) as raised:
        scheduler.run_forever()

    assert raised.value is error
    assert scheduler.is_running is False
    job.run_once.assert_called_once_with(
        scheduled_at=DUE_AT,
    )
    delay.assert_not_called()


def test_unregister_job_removes_registered_job() -> None:
    """An unregistered job should no longer be scheduled."""

    scheduler = make_scheduler()
    register_test_job(scheduler)

    scheduler.unregister_job(
        job_id="portfolio-901-sla",
    )

    assert scheduler.registered_job_count == 0
    assert scheduler.registered_job_ids == ()


def test_unregister_job_rejects_unknown_job_id() -> None:
    """Unregistering an unknown job should raise a domain error."""

    scheduler = make_scheduler()

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="job_id is not registered",
    ):
        scheduler.unregister_job(
            job_id="portfolio-999-sla",
        )

    assert scheduler.registered_job_count == 0