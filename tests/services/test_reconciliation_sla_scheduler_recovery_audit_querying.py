"""Tests for scheduler recovery-audit querying."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from services.reconciliation_sla_scheduler import (
    ReconciliationSLAScheduler,
    ReconciliationSLASchedulerConfig,
    ReconciliationSLASchedulerValidationError,
    ReconciliationSLARecoveryHistoryRepository,
    ReconciliationSLARecoveryReport,
)


FIRST_RECORDED_AT = datetime(
    2026,
    8,
    5,
    10,
    0,
    tzinfo=timezone.utc,
)
SECOND_RECORDED_AT = datetime(
    2026,
    8,
    5,
    10,
    5,
    tzinfo=timezone.utc,
)


def test_get_latest_recovery_report_returns_newest_report() -> None:
    """Latest recovery lookup should return the newest audit report."""

    clock = Mock(
        side_effect=(
            FIRST_RECORDED_AT,
            SECOND_RECORDED_AT,
        )
    )
    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=timedelta(seconds=30),
        ),
        clock=clock,
    )
    scheduler.recover_jobs_with_report(
        jobs_by_id={},
    )
    expected_report = scheduler.recover_jobs_with_report(
        jobs_by_id={},
    )

    assert scheduler.get_latest_recovery_report() == (
        expected_report
    )


def test_get_latest_recovery_report_rejects_empty_history() -> None:
    """Latest recovery lookup should reject an empty audit trail."""

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=timedelta(seconds=30),
        ),
    )

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="recovery history is empty",
    ):
        scheduler.get_latest_recovery_report()


def test_get_recovery_history_filters_incomplete_reports() -> None:
    """Recovery history should support filtering by completion outcome."""

    complete_report = ReconciliationSLARecoveryReport(
        recovered_job_ids=("portfolio-901-sla",),
        missing_job_ids=(),
        pending_job_ids=(),
        recorded_at=FIRST_RECORDED_AT,
    )
    incomplete_report = ReconciliationSLARecoveryReport(
        recovered_job_ids=("portfolio-902-sla",),
        missing_job_ids=("portfolio-999-sla",),
        pending_job_ids=(),
        recorded_at=SECOND_RECORDED_AT,
    )
    repository = Mock(
        spec=ReconciliationSLARecoveryHistoryRepository,
    )
    repository.load_history.return_value = (
        complete_report,
        incomplete_report,
    )
    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=timedelta(seconds=30),
        ),
        recovery_history_repository=repository,
    )

    assert scheduler.get_recovery_history(
        is_complete=False,
    ) == (incomplete_report,)


def test_get_recovery_history_filters_reports_by_job_id() -> None:
    """Job lookup should match recovered, missing, or pending job IDs."""

    matching_report = ReconciliationSLARecoveryReport(
        recovered_job_ids=("portfolio-901-sla",),
        missing_job_ids=(),
        pending_job_ids=("portfolio-902-sla",),
        recorded_at=FIRST_RECORDED_AT,
    )
    unrelated_report = ReconciliationSLARecoveryReport(
        recovered_job_ids=("portfolio-903-sla",),
        missing_job_ids=(),
        pending_job_ids=(),
        recorded_at=SECOND_RECORDED_AT,
    )
    repository = Mock(
        spec=ReconciliationSLARecoveryHistoryRepository,
    )
    repository.load_history.return_value = (
        matching_report,
        unrelated_report,
    )
    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=timedelta(seconds=30),
        ),
        recovery_history_repository=repository,
    )

    assert scheduler.get_recovery_history(
        job_id="portfolio-902-sla",
    ) == (matching_report,)


def test_get_recovery_history_rejects_blank_job_id() -> None:
    """Job-specific recovery queries should reject blank identifiers."""

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=timedelta(seconds=30),
        ),
    )

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="job_id must not be blank",
    ):
        scheduler.get_recovery_history(
            job_id="   ",
        )


def test_get_recovery_history_rejects_non_boolean_outcome() -> None:
    """Recovery outcome filtering should accept only booleans."""

    scheduler = ReconciliationSLAScheduler(
        config=ReconciliationSLASchedulerConfig(
            poll_interval=timedelta(seconds=30),
        ),
    )

    with pytest.raises(
        ReconciliationSLASchedulerValidationError,
        match="is_complete must be a boolean",
    ):
        scheduler.get_recovery_history(
            is_complete="false",
        )