"""Tests for reconciliation SLA scheduler misfire handling."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from services.reconciliation_sla_scheduled_job import (
    ReconciliationSLAScheduledJob,
)
from services.reconciliation_sla_scheduler import (
    ReconciliationSLAScheduler,
    ReconciliationSLASchedulerConfig,
)


POLL_INTERVAL = timedelta(seconds=30)
JOB_INTERVAL = timedelta(minutes=15)
FIRST_DUE_AT = datetime(
    2026,
    7,
    28,
    10,
    0,
    tzinfo=timezone.utc,
)
LATE_AS_OF = datetime(
    2026,
    7,
    28,
    10,
    47,
    tzinfo=timezone.utc,
)


def test_scheduler_config_can_enable_missed_run_coalescing() -> None:
    """Scheduler configuration should allow overdue runs to be coalesced."""

    config = ReconciliationSLASchedulerConfig(
        poll_interval=POLL_INTERVAL,
        coalesce_missed_runs=True,
    )

    assert config.coalesce_missed_runs is True


@pytest.mark.parametrize(
    "coalesce_missed_runs",
    [
        1,
        "yes",
        None,
    ],
)
def test_scheduler_config_rejects_non_boolean_coalescing_policy(
    coalesce_missed_runs: object,
) -> None:
    """Missed-run coalescing configuration should require a boolean."""

    with pytest.raises(
        ValueError,
        match="coalesce_missed_runs must be a boolean",
    ):
        ReconciliationSLASchedulerConfig(
            poll_interval=POLL_INTERVAL,
            coalesce_missed_runs=coalesce_missed_runs,
        )


def test_coalescing_advances_overdue_job_beyond_as_of() -> None:
    """A coalesced overdue job should not remain immediately due."""

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=POLL_INTERVAL,
            coalesce_missed_runs=True,
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
        next_run_at=FIRST_DUE_AT,
    )

    scheduler.run_due_jobs(
        as_of=LATE_AS_OF,
    )

    status = scheduler.get_job_status(
        job_id="portfolio-901-sla",
    )

    job.run_once.assert_called_once_with(
        scheduled_at=FIRST_DUE_AT,
    )
    assert status.next_run_at == datetime(
        2026,
        7,
        28,
        11,
        0,
        tzinfo=timezone.utc,
    )
def test_scheduler_does_not_coalesce_missed_runs_by_default() -> None:
    """Default scheduling should preserve one-interval advancement."""

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
        next_run_at=FIRST_DUE_AT,
    )

    scheduler.run_due_jobs(
        as_of=LATE_AS_OF,
    )

    status = scheduler.get_job_status(
        job_id="portfolio-901-sla",
    )

    assert status.next_run_at == datetime(
        2026,
        7,
        28,
        10,
        15,
        tzinfo=timezone.utc,
    )
def test_coalescing_advances_isolated_failed_job_beyond_as_of() -> None:
    """An isolated failed job should also coalesce missed intervals."""

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=POLL_INTERVAL,
            continue_on_job_failure=True,
            coalesce_missed_runs=True,
        )
    )
    job = Mock(
        spec=ReconciliationSLAScheduledJob,
    )
    job.run_once.side_effect = RuntimeError(
        "temporary SLA failure"
    )

    scheduler.register_job(
        job_id="portfolio-901-sla",
        job=job,
        interval=JOB_INTERVAL,
        next_run_at=FIRST_DUE_AT,
    )

    results = scheduler.run_due_jobs(
        as_of=LATE_AS_OF,
    )
    status = scheduler.get_job_status(
        job_id="portfolio-901-sla",
    )

    assert results == {}
    job.run_once.assert_called_once_with(
        scheduled_at=FIRST_DUE_AT,
    )
    assert status.next_run_at == datetime(
        2026,
        7,
        28,
        11,
        0,
        tzinfo=timezone.utc,
    )