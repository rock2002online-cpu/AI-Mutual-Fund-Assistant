"""Scheduled execution adapter for reconciliation SLA automation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from time import sleep
from typing import Callable, Literal

from services.reconciliation_sla_automation_service import (
    ReconciliationSLAAutomationResult,
    ReconciliationSLAAutomationService,
)
from services.reconciliation_sla_notifier import (
    ReconciliationSLANotifier,
)


class ReconciliationSLAScheduledJobValidationError(
    ValueError
):
    """Raised when scheduled SLA job configuration is invalid."""


def _validate_positive_integer(
    value: int,
    *,
    field_name: str,
) -> None:
    """Require a positive integer configuration value."""

    if value <= 0:
        raise (
            ReconciliationSLAScheduledJobValidationError(
                f"{field_name} must be positive."
            )
        )


def _validate_positive_duration(
    value: timedelta,
    *,
    field_name: str,
) -> None:
    """Require a positive duration configuration value."""

    if value <= timedelta(0):
        raise (
            ReconciliationSLAScheduledJobValidationError(
                f"{field_name} must be positive."
            )
        )


def _validate_scheduled_at(
    scheduled_at: datetime,
) -> None:
    """Require a timezone-aware scheduled execution timestamp."""

    if (
        scheduled_at.tzinfo is None
        or scheduled_at.utcoffset() is None
    ):
        raise (
            ReconciliationSLAScheduledJobValidationError(
                "scheduled_at must be timezone-aware."
            )
        )


class ReconciliationSLANotificationDeliveryError(
    RuntimeError
):
    """Raised when an SLA job notification cannot be delivered."""

    def __init__(
        self,
        message: str,
        *,
        notification_type: Literal[
            "escalation",
            "failure",
        ],
        portfolio_id: int,
        scheduled_at: datetime,
        attempt_number: int,
        max_attempts: int,
        automation_error: Exception | None = None,
    ) -> None:
        _validate_positive_integer(
            portfolio_id,
            field_name="portfolio_id",
        )

        _validate_scheduled_at(scheduled_at)

        _validate_positive_integer(
            attempt_number,
            field_name="attempt_number",
        )
        _validate_positive_integer(
            max_attempts,
            field_name="max_attempts",
        )

        if attempt_number > max_attempts:
            raise (
                ReconciliationSLAScheduledJobValidationError(
                    "attempt_number cannot exceed max_attempts."
                )
            )

        super().__init__(message)
        self.notification_type = notification_type
        self.portfolio_id = portfolio_id
        self.scheduled_at = scheduled_at
        self.attempt_number = attempt_number
        self.max_attempts = max_attempts
        self.automation_error = automation_error

    @property
    def delivery_error(self) -> BaseException | None:
        """Return the underlying notification-provider error."""

        return self.__cause__

    @property
    def retries_used(self) -> int:
        """Return the number of retries already consumed."""

        return self.attempt_number - 1

    @property
    def retries_remaining(self) -> int:
        """Return the configured attempts still remaining."""

        return self.max_attempts - self.attempt_number


@dataclass(frozen=True, slots=True)
class ReconciliationSLAScheduledJobResult:
    """Result of a successful scheduled SLA job execution."""

    automation_result: ReconciliationSLAAutomationResult
    attempts_used: int

    def __post_init__(self) -> None:
        """Validate scheduled job result invariants."""

        _validate_positive_integer(
            self.attempts_used,
            field_name="attempts_used",
        )

    @property
    def total_breaches(self) -> int:
        """Return the detected SLA breach count."""

        return self.automation_result.total_breaches

    @property
    def escalated_count(self) -> int:
        """Return the escalated exception count."""

        return self.automation_result.escalated_count

    @property
    def was_retried(self) -> bool:
        """Return whether success required more than one attempt."""

        return self.attempts_used > 1

    @property
    def succeeded_on_first_attempt(self) -> bool:
        """Return whether the first execution attempt succeeded."""

        return self.attempts_used == 1


class ReconciliationSLAScheduledJob:
    """Execute a configured portfolio SLA automation run."""

    def __init__(
        self,
        *,
        automation_service: (
            ReconciliationSLAAutomationService
        ),
        notifier: ReconciliationSLANotifier | None = None,
        portfolio_id: int,
        assignment_sla: timedelta,
        investigation_sla: timedelta,
        resolution_sla: timedelta,
        max_attempts: int = 1,
        retry_delay: timedelta = timedelta(0),
        delay: Callable[[float], None] = sleep,
    ) -> None:
        _validate_positive_integer(
            portfolio_id,
            field_name="portfolio_id",
        )

        _validate_positive_duration(
            assignment_sla,
            field_name="assignment_sla",
        )
        _validate_positive_duration(
            investigation_sla,
            field_name="investigation_sla",
        )
        _validate_positive_duration(
            resolution_sla,
            field_name="resolution_sla",
        )

        _validate_positive_integer(
            max_attempts,
            field_name="max_attempts",
        )

        if retry_delay < timedelta(0):
            raise (
                ReconciliationSLAScheduledJobValidationError(
                    "retry_delay cannot be negative."
                )
            )

        self._automation_service = automation_service
        self._notifier = notifier
        self._portfolio_id = portfolio_id
        self._assignment_sla = assignment_sla
        self._investigation_sla = investigation_sla
        self._resolution_sla = resolution_sla
        self._max_attempts = max_attempts
        self._retry_delay = retry_delay
        self._delay = delay

    def _wait_before_retry(self) -> None:
        """Apply the configured delay before another attempt."""

        if self._retry_delay <= timedelta(0):
            return

        self._delay(
            self._retry_delay.total_seconds()
        )

    def _run_automation(
        self,
        *,
        scheduled_at: datetime,
    ) -> ReconciliationSLAAutomationResult:
        """Execute one reconciliation SLA automation attempt."""

        return self._automation_service.run_portfolio(
            portfolio_id=self._portfolio_id,
            as_of=scheduled_at,
            assignment_sla=self._assignment_sla,
            investigation_sla=self._investigation_sla,
            resolution_sla=self._resolution_sla,
        )

    def _notify_failure(
        self,
        *,
        scheduled_at: datetime,
        error: Exception,
        attempt_number: int,
    ) -> None:
        """Deliver a terminal job-failure notification."""

        if self._notifier is None:
            return

        try:
            self._notifier.notify_failure(
                portfolio_id=self._portfolio_id,
                scheduled_at=scheduled_at,
                error=error,
                attempt_number=attempt_number,
                max_attempts=self._max_attempts,
            )
        except Exception as delivery_error:
            raise (
                ReconciliationSLANotificationDeliveryError(
                    "Notification delivery failed for "
                    "reconciliation SLA job failure.",
                    notification_type="failure",
                    portfolio_id=self._portfolio_id,
                    scheduled_at=scheduled_at,
                    attempt_number=attempt_number,
                    max_attempts=self._max_attempts,
                    automation_error=error,
                )
            ) from delivery_error

    def _notify_escalations(
        self,
        *,
        scheduled_at: datetime,
        automation_result: (
            ReconciliationSLAAutomationResult
        ),
        attempts_used: int,
    ) -> None:
        """Deliver successful SLA escalation notifications."""

        if (
            self._notifier is None
            or not automation_result.has_escalations
        ):
            return

        try:
            self._notifier.notify_escalations(
                portfolio_id=self._portfolio_id,
                scheduled_at=scheduled_at,
                automation_result=automation_result,
                attempts_used=attempts_used,
            )
        except Exception as delivery_error:
            raise (
                ReconciliationSLANotificationDeliveryError(
                    "Notification delivery failed for "
                    "reconciliation SLA escalations.",
                    notification_type="escalation",
                    portfolio_id=self._portfolio_id,
                    scheduled_at=scheduled_at,
                    attempt_number=attempts_used,
                    max_attempts=self._max_attempts,
                )
            ) from delivery_error

    def _execute_with_retries(
        self,
        *,
        scheduled_at: datetime,
    ) -> tuple[
        ReconciliationSLAAutomationResult,
        int,
    ]:
        """Execute automation until success or retry exhaustion."""

        for attempt in range(
            1,
            self._max_attempts + 1,
        ):
            try:
                automation_result = (
                    self._run_automation(
                        scheduled_at=scheduled_at,
                    )
                )
                return automation_result, attempt
            except Exception as error:
                if attempt < self._max_attempts:
                    self._wait_before_retry()
                    continue

                self._notify_failure(
                    scheduled_at=scheduled_at,
                    error=error,
                    attempt_number=attempt,
                )
                raise

        raise AssertionError(
            "Positive max_attempts must execute an attempt."
        )

    def run_once(
        self,
        *,
        scheduled_at: datetime,
    ) -> ReconciliationSLAScheduledJobResult:
        """Execute and return one scheduled portfolio SLA run."""

        _validate_scheduled_at(scheduled_at)

        (
            automation_result,
            attempts_used,
        ) = self._execute_with_retries(
            scheduled_at=scheduled_at,
        )

        self._notify_escalations(
            scheduled_at=scheduled_at,
            automation_result=automation_result,
            attempts_used=attempts_used,
        )

        return ReconciliationSLAScheduledJobResult(
            automation_result=automation_result,
            attempts_used=attempts_used,
        )


__all__ = [
    "ReconciliationSLANotificationDeliveryError",
    "ReconciliationSLAScheduledJob",
    "ReconciliationSLAScheduledJobResult",
    "ReconciliationSLAScheduledJobValidationError",
]
