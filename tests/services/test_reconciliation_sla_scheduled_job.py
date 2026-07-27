"""Tests for scheduled reconciliation SLA jobs."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from services.reconciliation_sla_automation_service import (
    ReconciliationSLAAutomationResult,
    ReconciliationSLAAutomationService,
)
from services.reconciliation_sla_monitoring_service import (
    ReconciliationSLAMonitoringResult,
)
from services.reconciliation_sla_notifier import (
    ReconciliationSLANotifier,
)
from services.reconciliation_sla_scheduled_job import (
    ReconciliationSLANotificationDeliveryError,
    ReconciliationSLAScheduledJob,
    ReconciliationSLAScheduledJobResult,
    ReconciliationSLAScheduledJobValidationError,
)


def test_run_once_executes_configured_portfolio_sla_run(
) -> None:
    """A scheduled job should execute one configured SLA run."""

    scheduled_at = datetime(
        2026,
        7,
        27,
        19,
        0,
        tzinfo=timezone.utc,
    )
    monitoring_result = ReconciliationSLAMonitoringResult(
        as_of=scheduled_at,
        assignment_breaches=[],
        investigation_breaches=[],
        resolution_breaches=[],
    )
    automation_result = ReconciliationSLAAutomationResult(
        monitoring_result=monitoring_result,
        escalated_exceptions=[],
    )
    automation_service = Mock(
        spec=ReconciliationSLAAutomationService,
    )
    automation_service.run_portfolio.return_value = (
        automation_result
    )

    job = ReconciliationSLAScheduledJob(
        automation_service=automation_service,
        portfolio_id=901,
        assignment_sla=timedelta(hours=2),
        investigation_sla=timedelta(hours=4),
        resolution_sla=timedelta(hours=24),
    )

    result = job.run_once(
        scheduled_at=scheduled_at,
    )

    assert result == ReconciliationSLAScheduledJobResult(
        automation_result=automation_result,
        attempts_used=1,
    )
    automation_service.run_portfolio.assert_called_once_with(
        portfolio_id=901,
        as_of=scheduled_at,
        assignment_sla=timedelta(hours=2),
        investigation_sla=timedelta(hours=4),
        resolution_sla=timedelta(hours=24),
    )


@pytest.mark.parametrize(
    "portfolio_id",
    [
        0,
        -1,
    ],
)
def test_init_rejects_non_positive_portfolio_id(
    portfolio_id: int,
) -> None:
    """A scheduled job should require a positive portfolio ID."""

    automation_service = Mock(
        spec=ReconciliationSLAAutomationService,
    )

    with pytest.raises(
        ReconciliationSLAScheduledJobValidationError,
        match="portfolio_id must be positive",
    ):
        ReconciliationSLAScheduledJob(
            automation_service=automation_service,
            portfolio_id=portfolio_id,
            assignment_sla=timedelta(hours=2),
            investigation_sla=timedelta(hours=4),
            resolution_sla=timedelta(hours=24),
        )


@pytest.mark.parametrize(
    "assignment_sla",
    [
        timedelta(0),
        timedelta(seconds=-1),
    ],
)
def test_init_rejects_non_positive_assignment_sla(
    assignment_sla: timedelta,
) -> None:
    """A scheduled job should require a positive assignment SLA."""

    automation_service = Mock(
        spec=ReconciliationSLAAutomationService,
    )

    with pytest.raises(
        ReconciliationSLAScheduledJobValidationError,
        match="assignment_sla must be positive",
    ):
        ReconciliationSLAScheduledJob(
            automation_service=automation_service,
            portfolio_id=901,
            assignment_sla=assignment_sla,
            investigation_sla=timedelta(hours=4),
            resolution_sla=timedelta(hours=24),
        )


@pytest.mark.parametrize(
    "investigation_sla",
    [
        timedelta(0),
        timedelta(seconds=-1),
    ],
)
def test_init_rejects_non_positive_investigation_sla(
    investigation_sla: timedelta,
) -> None:
    """A scheduled job should require a positive investigation SLA."""

    automation_service = Mock(
        spec=ReconciliationSLAAutomationService,
    )

    with pytest.raises(
        ReconciliationSLAScheduledJobValidationError,
        match="investigation_sla must be positive",
    ):
        ReconciliationSLAScheduledJob(
            automation_service=automation_service,
            portfolio_id=901,
            assignment_sla=timedelta(hours=2),
            investigation_sla=investigation_sla,
            resolution_sla=timedelta(hours=24),
        )


@pytest.mark.parametrize(
    "resolution_sla",
    [
        timedelta(0),
        timedelta(seconds=-1),
    ],
)
def test_init_rejects_non_positive_resolution_sla(
    resolution_sla: timedelta,
) -> None:
    """A scheduled job should require a positive resolution SLA."""

    automation_service = Mock(
        spec=ReconciliationSLAAutomationService,
    )

    with pytest.raises(
        ReconciliationSLAScheduledJobValidationError,
        match="resolution_sla must be positive",
    ):
        ReconciliationSLAScheduledJob(
            automation_service=automation_service,
            portfolio_id=901,
            assignment_sla=timedelta(hours=2),
            investigation_sla=timedelta(hours=4),
            resolution_sla=resolution_sla,
        )


def test_run_once_rejects_naive_scheduled_at(
) -> None:
    """A scheduled run should require a timezone-aware timestamp."""

    automation_service = Mock(
        spec=ReconciliationSLAAutomationService,
    )
    job = ReconciliationSLAScheduledJob(
        automation_service=automation_service,
        portfolio_id=901,
        assignment_sla=timedelta(hours=2),
        investigation_sla=timedelta(hours=4),
        resolution_sla=timedelta(hours=24),
    )

    with pytest.raises(
        ReconciliationSLAScheduledJobValidationError,
        match="scheduled_at must be timezone-aware",
    ):
        job.run_once(
            scheduled_at=datetime(
                2026,
                7,
                27,
                19,
                0,
            ),
        )

    automation_service.run_portfolio.assert_not_called()


def test_run_once_notifies_successful_escalations(
) -> None:
    """A successful run should notify when it escalates exceptions."""

    scheduled_at = datetime(
        2026,
        7,
        27,
        20,
        0,
        tzinfo=timezone.utc,
    )
    monitoring_result = ReconciliationSLAMonitoringResult(
        as_of=scheduled_at,
        assignment_breaches=[],
        investigation_breaches=[],
        resolution_breaches=[],
    )
    automation_result = ReconciliationSLAAutomationResult(
        monitoring_result=monitoring_result,
        escalated_exceptions=[
            Mock(),
        ],
    )
    automation_service = Mock(
        spec=ReconciliationSLAAutomationService,
    )
    automation_service.run_portfolio.return_value = (
        automation_result
    )
    notifier = Mock(
        spec=ReconciliationSLANotifier,
    )
    job = ReconciliationSLAScheduledJob(
        automation_service=automation_service,
        notifier=notifier,
        portfolio_id=901,
        assignment_sla=timedelta(hours=2),
        investigation_sla=timedelta(hours=4),
        resolution_sla=timedelta(hours=24),
    )

    result = job.run_once(
        scheduled_at=scheduled_at,
    )

    assert result == ReconciliationSLAScheduledJobResult(
        automation_result=automation_result,
        attempts_used=1,
    )
    notifier.notify_escalations.assert_called_once_with(
        portfolio_id=901,
        scheduled_at=scheduled_at,
        automation_result=automation_result,
        attempts_used=1,
    )


def test_run_once_does_not_notify_without_escalations(
) -> None:
    """A successful breach-free run should not send notifications."""

    scheduled_at = datetime(
        2026,
        7,
        27,
        21,
        0,
        tzinfo=timezone.utc,
    )
    monitoring_result = ReconciliationSLAMonitoringResult(
        as_of=scheduled_at,
        assignment_breaches=[],
        investigation_breaches=[],
        resolution_breaches=[],
    )
    automation_result = ReconciliationSLAAutomationResult(
        monitoring_result=monitoring_result,
        escalated_exceptions=[],
    )
    automation_service = Mock(
        spec=ReconciliationSLAAutomationService,
    )
    automation_service.run_portfolio.return_value = (
        automation_result
    )
    notifier = Mock(
        spec=ReconciliationSLANotifier,
    )
    job = ReconciliationSLAScheduledJob(
        automation_service=automation_service,
        notifier=notifier,
        portfolio_id=901,
        assignment_sla=timedelta(hours=2),
        investigation_sla=timedelta(hours=4),
        resolution_sla=timedelta(hours=24),
    )

    result = job.run_once(
        scheduled_at=scheduled_at,
    )

    assert result == ReconciliationSLAScheduledJobResult(
        automation_result=automation_result,
        attempts_used=1,
    )
    notifier.notify_escalations.assert_not_called()


def test_run_once_notifies_and_reraises_automation_failure(
) -> None:
    """An automation failure should be notified and propagated."""

    scheduled_at = datetime(
        2026,
        7,
        27,
        22,
        0,
        tzinfo=timezone.utc,
    )
    error = RuntimeError(
        "SLA automation failed."
    )
    automation_service = Mock(
        spec=ReconciliationSLAAutomationService,
    )
    automation_service.run_portfolio.side_effect = error
    notifier = Mock(
        spec=ReconciliationSLANotifier,
    )
    job = ReconciliationSLAScheduledJob(
        automation_service=automation_service,
        notifier=notifier,
        portfolio_id=901,
        assignment_sla=timedelta(hours=2),
        investigation_sla=timedelta(hours=4),
        resolution_sla=timedelta(hours=24),
    )

    with pytest.raises(
        RuntimeError,
        match="SLA automation failed",
    ) as raised:
        job.run_once(
            scheduled_at=scheduled_at,
        )

    assert raised.value is error
    notifier.notify_failure.assert_called_once_with(
        portfolio_id=901,
        scheduled_at=scheduled_at,
        error=error,
        attempt_number=1,
        max_attempts=1,
    )
    notifier.notify_escalations.assert_not_called()


def test_run_once_reraises_failure_without_notifier(
) -> None:
    """A job without a notifier should still propagate failures."""

    scheduled_at = datetime(
        2026,
        7,
        27,
        23,
        0,
        tzinfo=timezone.utc,
    )
    error = RuntimeError(
        "SLA automation failed without notifier."
    )
    automation_service = Mock(
        spec=ReconciliationSLAAutomationService,
    )
    automation_service.run_portfolio.side_effect = error
    job = ReconciliationSLAScheduledJob(
        automation_service=automation_service,
        portfolio_id=901,
        assignment_sla=timedelta(hours=2),
        investigation_sla=timedelta(hours=4),
        resolution_sla=timedelta(hours=24),
    )

    with pytest.raises(
        RuntimeError,
        match="SLA automation failed without notifier",
    ) as raised:
        job.run_once(
            scheduled_at=scheduled_at,
        )

    assert raised.value is error


@pytest.mark.parametrize(
    "max_attempts",
    [
        0,
        -1,
    ],
)
def test_init_rejects_non_positive_max_attempts(
    max_attempts: int,
) -> None:
    """A scheduled job should require at least one attempt."""

    automation_service = Mock(
        spec=ReconciliationSLAAutomationService,
    )

    with pytest.raises(
        ReconciliationSLAScheduledJobValidationError,
        match="max_attempts must be positive",
    ):
        ReconciliationSLAScheduledJob(
            automation_service=automation_service,
            portfolio_id=901,
            assignment_sla=timedelta(hours=2),
            investigation_sla=timedelta(hours=4),
            resolution_sla=timedelta(hours=24),
            max_attempts=max_attempts,
        )


def test_run_once_retries_after_initial_automation_failure(
) -> None:
    """A scheduled job should return a successful retry result."""

    scheduled_at = datetime(
        2026,
        7,
        28,
        0,
        0,
        tzinfo=timezone.utc,
    )
    monitoring_result = ReconciliationSLAMonitoringResult(
        as_of=scheduled_at,
        assignment_breaches=[],
        investigation_breaches=[],
        resolution_breaches=[],
    )
    automation_result = ReconciliationSLAAutomationResult(
        monitoring_result=monitoring_result,
        escalated_exceptions=[
            Mock(),
        ],
    )
    automation_service = Mock(
        spec=ReconciliationSLAAutomationService,
    )
    automation_service.run_portfolio.side_effect = [
        RuntimeError("Temporary automation failure."),
        automation_result,
    ]
    notifier = Mock(
        spec=ReconciliationSLANotifier,
    )
    job = ReconciliationSLAScheduledJob(
        automation_service=automation_service,
        notifier=notifier,
        portfolio_id=901,
        assignment_sla=timedelta(hours=2),
        investigation_sla=timedelta(hours=4),
        resolution_sla=timedelta(hours=24),
        max_attempts=2,
    )

    result = job.run_once(
        scheduled_at=scheduled_at,
    )

    assert result == ReconciliationSLAScheduledJobResult(
        automation_result=automation_result,
        attempts_used=2,
    )
    assert automation_service.run_portfolio.call_count == 2
    notifier.notify_failure.assert_not_called()
    notifier.notify_escalations.assert_called_once_with(
        portfolio_id=901,
        scheduled_at=scheduled_at,
        automation_result=automation_result,
        attempts_used=2,
    )


def test_run_once_notifies_final_failure_after_retries_exhausted(
) -> None:
    """Retry exhaustion should notify and propagate the final error."""

    scheduled_at = datetime(
        2026,
        7,
        28,
        1,
        0,
        tzinfo=timezone.utc,
    )
    first_error = RuntimeError(
        "First automation failure."
    )
    final_error = RuntimeError(
        "Final automation failure."
    )
    automation_service = Mock(
        spec=ReconciliationSLAAutomationService,
    )
    automation_service.run_portfolio.side_effect = [
        first_error,
        final_error,
    ]
    notifier = Mock(
        spec=ReconciliationSLANotifier,
    )
    job = ReconciliationSLAScheduledJob(
        automation_service=automation_service,
        notifier=notifier,
        portfolio_id=901,
        assignment_sla=timedelta(hours=2),
        investigation_sla=timedelta(hours=4),
        resolution_sla=timedelta(hours=24),
        max_attempts=2,
    )

    with pytest.raises(
        RuntimeError,
        match="Final automation failure",
    ) as raised:
        job.run_once(
            scheduled_at=scheduled_at,
        )

    assert raised.value is final_error
    assert automation_service.run_portfolio.call_count == 2
    notifier.notify_failure.assert_called_once_with(
        portfolio_id=901,
        scheduled_at=scheduled_at,
        error=final_error,
        attempt_number=2,
        max_attempts=2,
    )
    notifier.notify_escalations.assert_not_called()


def test_init_rejects_negative_retry_delay(
) -> None:
    """A scheduled job should reject a negative retry delay."""

    automation_service = Mock(
        spec=ReconciliationSLAAutomationService,
    )

    with pytest.raises(
        ReconciliationSLAScheduledJobValidationError,
        match="retry_delay cannot be negative",
    ):
        ReconciliationSLAScheduledJob(
            automation_service=automation_service,
            portfolio_id=901,
            assignment_sla=timedelta(hours=2),
            investigation_sla=timedelta(hours=4),
            resolution_sla=timedelta(hours=24),
            retry_delay=timedelta(seconds=-1),
        )


def test_run_once_waits_between_failed_attempts(
) -> None:
    """A scheduled job should apply its delay before retrying."""

    scheduled_at = datetime(
        2026,
        7,
        28,
        2,
        0,
        tzinfo=timezone.utc,
    )
    monitoring_result = ReconciliationSLAMonitoringResult(
        as_of=scheduled_at,
        assignment_breaches=[],
        investigation_breaches=[],
        resolution_breaches=[],
    )
    automation_result = ReconciliationSLAAutomationResult(
        monitoring_result=monitoring_result,
        escalated_exceptions=[],
    )
    automation_service = Mock(
        spec=ReconciliationSLAAutomationService,
    )
    automation_service.run_portfolio.side_effect = [
        RuntimeError("Temporary automation failure."),
        automation_result,
    ]
    delay = Mock()
    job = ReconciliationSLAScheduledJob(
        automation_service=automation_service,
        portfolio_id=901,
        assignment_sla=timedelta(hours=2),
        investigation_sla=timedelta(hours=4),
        resolution_sla=timedelta(hours=24),
        max_attempts=2,
        retry_delay=timedelta(seconds=5),
        delay=delay,
    )

    result = job.run_once(
        scheduled_at=scheduled_at,
    )

    assert result == ReconciliationSLAScheduledJobResult(
        automation_result=automation_result,
        attempts_used=2,
    )
    delay.assert_called_once_with(5.0)


def test_run_once_does_not_wait_after_final_failure(
) -> None:
    """A scheduled job should not delay after retries are exhausted."""

    scheduled_at = datetime(
        2026,
        7,
        28,
        3,
        0,
        tzinfo=timezone.utc,
    )
    final_error = RuntimeError(
        "Final automation failure."
    )
    automation_service = Mock(
        spec=ReconciliationSLAAutomationService,
    )
    automation_service.run_portfolio.side_effect = [
        RuntimeError("First automation failure."),
        final_error,
    ]
    delay = Mock()
    job = ReconciliationSLAScheduledJob(
        automation_service=automation_service,
        portfolio_id=901,
        assignment_sla=timedelta(hours=2),
        investigation_sla=timedelta(hours=4),
        resolution_sla=timedelta(hours=24),
        max_attempts=2,
        retry_delay=timedelta(seconds=5),
        delay=delay,
    )

    with pytest.raises(
        RuntimeError,
        match="Final automation failure",
    ) as raised:
        job.run_once(
            scheduled_at=scheduled_at,
        )

    assert raised.value is final_error
    delay.assert_called_once_with(5.0)


def test_run_once_does_not_wait_for_zero_retry_delay(
) -> None:
    """A zero-delay retry should not invoke the delay function."""

    scheduled_at = datetime(
        2026,
        7,
        28,
        4,
        0,
        tzinfo=timezone.utc,
    )
    monitoring_result = ReconciliationSLAMonitoringResult(
        as_of=scheduled_at,
        assignment_breaches=[],
        investigation_breaches=[],
        resolution_breaches=[],
    )
    automation_result = ReconciliationSLAAutomationResult(
        monitoring_result=monitoring_result,
        escalated_exceptions=[],
    )
    automation_service = Mock(
        spec=ReconciliationSLAAutomationService,
    )
    automation_service.run_portfolio.side_effect = [
        RuntimeError("Temporary automation failure."),
        automation_result,
    ]
    delay = Mock()
    job = ReconciliationSLAScheduledJob(
        automation_service=automation_service,
        portfolio_id=901,
        assignment_sla=timedelta(hours=2),
        investigation_sla=timedelta(hours=4),
        resolution_sla=timedelta(hours=24),
        max_attempts=2,
        retry_delay=timedelta(0),
        delay=delay,
    )

    result = job.run_once(
        scheduled_at=scheduled_at,
    )

    assert result == ReconciliationSLAScheduledJobResult(
        automation_result=automation_result,
        attempts_used=2,
    )
    assert automation_service.run_portfolio.call_count == 2
    delay.assert_not_called()


def test_scheduled_job_result_exposes_operational_summary(
) -> None:
    """A job result should expose breach, escalation, and retry facts."""

    as_of = datetime(
        2026,
        7,
        28,
        5,
        0,
        tzinfo=timezone.utc,
    )
    monitoring_result = ReconciliationSLAMonitoringResult(
        as_of=as_of,
        assignment_breaches=[
            Mock(),
        ],
        investigation_breaches=[],
        resolution_breaches=[],
    )
    automation_result = ReconciliationSLAAutomationResult(
        monitoring_result=monitoring_result,
        escalated_exceptions=[
            Mock(),
        ],
    )
    result = ReconciliationSLAScheduledJobResult(
        automation_result=automation_result,
        attempts_used=2,
    )

    assert result.total_breaches == 1
    assert result.escalated_count == 1
    assert result.was_retried is True
    assert result.succeeded_on_first_attempt is False

    first_attempt_result = (
        ReconciliationSLAScheduledJobResult(
            automation_result=automation_result,
            attempts_used=1,
        )
    )

    assert (
        first_attempt_result.succeeded_on_first_attempt
        is True
    )


@pytest.mark.parametrize(
    "attempts_used",
    [
        0,
        -1,
    ],
)
def test_scheduled_job_result_rejects_non_positive_attempts(
    attempts_used: int,
) -> None:
    """A job result should require at least one used attempt."""

    as_of = datetime(
        2026,
        7,
        28,
        6,
        0,
        tzinfo=timezone.utc,
    )
    monitoring_result = ReconciliationSLAMonitoringResult(
        as_of=as_of,
        assignment_breaches=[],
        investigation_breaches=[],
        resolution_breaches=[],
    )
    automation_result = ReconciliationSLAAutomationResult(
        monitoring_result=monitoring_result,
        escalated_exceptions=[],
    )

    with pytest.raises(
        ReconciliationSLAScheduledJobValidationError,
        match="attempts_used must be positive",
    ):
        ReconciliationSLAScheduledJobResult(
            automation_result=automation_result,
            attempts_used=attempts_used,
        )


def test_run_once_does_not_retry_completed_work_when_notification_fails(
) -> None:
    """A notification failure should not rerun completed automation."""

    scheduled_at = datetime(
        2026,
        7,
        28,
        7,
        0,
        tzinfo=timezone.utc,
    )
    monitoring_result = ReconciliationSLAMonitoringResult(
        as_of=scheduled_at,
        assignment_breaches=[],
        investigation_breaches=[],
        resolution_breaches=[],
    )
    automation_result = ReconciliationSLAAutomationResult(
        monitoring_result=monitoring_result,
        escalated_exceptions=[
            Mock(),
        ],
    )
    automation_service = Mock(
        spec=ReconciliationSLAAutomationService,
    )
    automation_service.run_portfolio.return_value = (
        automation_result
    )
    notifier = Mock(
        spec=ReconciliationSLANotifier,
    )
    notification_error = RuntimeError(
        "Notification delivery failed."
    )
    notifier.notify_escalations.side_effect = (
        notification_error
    )
    job = ReconciliationSLAScheduledJob(
        automation_service=automation_service,
        notifier=notifier,
        portfolio_id=901,
        assignment_sla=timedelta(hours=2),
        investigation_sla=timedelta(hours=4),
        resolution_sla=timedelta(hours=24),
        max_attempts=3,
    )

    with pytest.raises(
        ReconciliationSLANotificationDeliveryError,
        match="Notification delivery failed",
    ) as raised:
        job.run_once(
            scheduled_at=scheduled_at,
        )

    assert raised.value.__cause__ is notification_error
    assert raised.value.delivery_error is notification_error
    assert raised.value.notification_type == "escalation"
    assert raised.value.portfolio_id == 901
    assert raised.value.scheduled_at == scheduled_at
    assert raised.value.attempt_number == 1
    assert raised.value.max_attempts == 3
    assert raised.value.retries_used == 0
    assert raised.value.retries_remaining == 2
    automation_service.run_portfolio.assert_called_once()
    notifier.notify_escalations.assert_called_once()
    notifier.notify_failure.assert_not_called()


def test_run_once_wraps_failure_notification_delivery_error(
) -> None:
    """A failure-notification error should be wrapped after exhaustion."""

    scheduled_at = datetime(
        2026,
        7,
        28,
        8,
        0,
        tzinfo=timezone.utc,
    )
    automation_error = RuntimeError(
        "SLA automation failed."
    )
    delivery_error = RuntimeError(
        "Failure notification provider unavailable."
    )
    automation_service = Mock(
        spec=ReconciliationSLAAutomationService,
    )
    automation_service.run_portfolio.side_effect = (
        automation_error
    )
    notifier = Mock(
        spec=ReconciliationSLANotifier,
    )
    notifier.notify_failure.side_effect = delivery_error
    job = ReconciliationSLAScheduledJob(
        automation_service=automation_service,
        notifier=notifier,
        portfolio_id=901,
        assignment_sla=timedelta(hours=2),
        investigation_sla=timedelta(hours=4),
        resolution_sla=timedelta(hours=24),
        max_attempts=2,
    )

    with pytest.raises(
        ReconciliationSLANotificationDeliveryError,
        match="Notification delivery failed",
    ) as raised:
        job.run_once(
            scheduled_at=scheduled_at,
        )

    assert raised.value.__cause__ is delivery_error
    assert raised.value.delivery_error is delivery_error
    assert raised.value.automation_error is automation_error
    assert raised.value.notification_type == "failure"
    assert raised.value.portfolio_id == 901
    assert raised.value.scheduled_at == scheduled_at
    assert raised.value.attempt_number == 2
    assert raised.value.max_attempts == 2
    assert raised.value.retries_used == 1
    assert raised.value.retries_remaining == 0
    assert automation_service.run_portfolio.call_count == 2
    notifier.notify_failure.assert_called_once_with(
        portfolio_id=901,
        scheduled_at=scheduled_at,
        error=automation_error,
        attempt_number=2,
        max_attempts=2,
    )
    notifier.notify_escalations.assert_not_called()


def test_notification_delivery_error_rejects_attempt_over_limit(
) -> None:
    """Delivery error attempt context should not exceed its limit."""

    with pytest.raises(
        ReconciliationSLAScheduledJobValidationError,
        match="attempt_number cannot exceed max_attempts",
    ):
        ReconciliationSLANotificationDeliveryError(
            "Notification delivery failed.",
            notification_type="escalation",
            portfolio_id=901,
            scheduled_at=datetime(
                2026,
                7,
                28,
                9,
                0,
                tzinfo=timezone.utc,
            ),
            attempt_number=2,
            max_attempts=1,
        )


@pytest.mark.parametrize(
    (
        "attempt_number",
        "max_attempts",
        "message",
    ),
    [
        (
            0,
            1,
            "attempt_number must be positive",
        ),
        (
            1,
            0,
            "max_attempts must be positive",
        ),
    ],
)
def test_notification_delivery_error_requires_positive_attempts(
    attempt_number: int,
    max_attempts: int,
    message: str,
) -> None:
    """Delivery error attempt values should both be positive."""

    with pytest.raises(
        ReconciliationSLAScheduledJobValidationError,
        match=message,
    ):
        ReconciliationSLANotificationDeliveryError(
            "Notification delivery failed.",
            notification_type="escalation",
            portfolio_id=901,
            scheduled_at=datetime(
                2026,
                7,
                28,
                10,
                0,
                tzinfo=timezone.utc,
            ),
            attempt_number=attempt_number,
            max_attempts=max_attempts,
        )


@pytest.mark.parametrize(
    "portfolio_id",
    [
        0,
        -1,
    ],
)
def test_notification_delivery_error_requires_positive_portfolio_id(
    portfolio_id: int,
) -> None:
    """A delivery error should require a positive portfolio ID."""

    with pytest.raises(
        ReconciliationSLAScheduledJobValidationError,
        match="portfolio_id must be positive",
    ):
        ReconciliationSLANotificationDeliveryError(
            "Notification delivery failed.",
            notification_type="escalation",
            portfolio_id=portfolio_id,
            scheduled_at=datetime(
                2026,
                7,
                28,
                11,
                0,
                tzinfo=timezone.utc,
            ),
            attempt_number=1,
            max_attempts=1,
        )


def test_notification_delivery_error_rejects_naive_scheduled_at(
) -> None:
    """A delivery error should require a timezone-aware timestamp."""

    with pytest.raises(
        ReconciliationSLAScheduledJobValidationError,
        match="scheduled_at must be timezone-aware",
    ):
        ReconciliationSLANotificationDeliveryError(
            "Notification delivery failed.",
            notification_type="escalation",
            portfolio_id=901,
            scheduled_at=datetime(
                2026,
                7,
                28,
                12,
                0,
            ),
            attempt_number=1,
            max_attempts=1,
        )
