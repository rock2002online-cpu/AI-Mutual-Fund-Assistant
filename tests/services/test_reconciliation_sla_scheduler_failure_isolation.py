"""Tests for reconciliation SLA scheduler failure isolation."""

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


def test_scheduler_config_can_enable_failure_isolation() -> None:
    """Scheduler configuration should allow isolated job failures."""

    config = ReconciliationSLASchedulerConfig(
        poll_interval=POLL_INTERVAL,
        continue_on_job_failure=True,
    )

    assert config.continue_on_job_failure is True


def test_failure_isolation_allows_remaining_due_jobs_to_run() -> None:
    """One failed job should not prevent another due job from running."""

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=POLL_INTERVAL,
            continue_on_job_failure=True,
        )
    )
    failing_job = Mock(
        spec=ReconciliationSLAScheduledJob,
    )
    succeeding_job = Mock(
        spec=ReconciliationSLAScheduledJob,
    )
    failure = RuntimeError("temporary SLA failure")
    successful_result = Mock()

    failing_job.run_once.side_effect = failure
    succeeding_job.run_once.return_value = successful_result

    scheduler.register_job(
        job_id="failing-job",
        job=failing_job,
        interval=JOB_INTERVAL,
        next_run_at=DUE_AT,
    )
    scheduler.register_job(
        job_id="succeeding-job",
        job=succeeding_job,
        interval=JOB_INTERVAL,
        next_run_at=DUE_AT,
    )

    results = scheduler.run_due_jobs(
        as_of=DUE_AT,
    )

    failing_job.run_once.assert_called_once_with(
        scheduled_at=DUE_AT,
    )
    succeeding_job.run_once.assert_called_once_with(
        scheduled_at=DUE_AT,
    )
    assert results == {
        "succeeding-job": successful_result,
    }
def test_failure_isolation_advances_failed_job_schedule() -> None:
    """An isolated failure should not leave the job immediately due."""

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=POLL_INTERVAL,
            continue_on_job_failure=True,
        )
    )
    failing_job = Mock(
        spec=ReconciliationSLAScheduledJob,
    )
    failing_job.run_once.side_effect = RuntimeError(
        "temporary SLA failure"
    )

    scheduler.register_job(
        job_id="failing-job",
        job=failing_job,
        interval=JOB_INTERVAL,
        next_run_at=DUE_AT,
    )

    scheduler.run_due_jobs(
        as_of=DUE_AT,
    )

    status = scheduler.get_job_status(
        job_id="failing-job",
    )

    assert status.next_run_at == DUE_AT + JOB_INTERVAL
@pytest.mark.parametrize(
    "continue_on_job_failure",
    [
        1,
        "yes",
        None,
    ],
)
def test_scheduler_config_rejects_non_boolean_failure_policy(
    continue_on_job_failure: object,
) -> None:
    """Failure isolation configuration should require a boolean."""

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="continue_on_job_failure must be a boolean",
    ):
        ReconciliationSLASchedulerConfig(
            poll_interval=POLL_INTERVAL,
            continue_on_job_failure=continue_on_job_failure,
        )