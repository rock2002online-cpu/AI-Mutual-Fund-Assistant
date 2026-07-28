"""Scheduler orchestration for reconciliation SLA jobs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import sleep
from typing import Callable, Protocol

from services.reconciliation_sla_scheduled_job import (
    ReconciliationSLAScheduledJob,
    ReconciliationSLAScheduledJobResult,
)


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


class ReconciliationSLASchedulerValidationError(ValueError):
    """Raised when scheduler configuration is invalid."""


@dataclass(frozen=True, slots=True)
class ReconciliationSLASchedulerConfig:
    """Immutable scheduler runtime configuration."""

    poll_interval: timedelta
    execution_history_limit: int | None = None
    continue_on_job_failure: bool = False

    def __post_init__(self) -> None:
        """Validate scheduler configuration."""

        if self.poll_interval <= timedelta(0):
            raise ReconciliationSLASchedulerValidationError(
                "poll_interval must be positive."
            )
        if type(self.continue_on_job_failure) is not bool:
            raise ReconciliationSLASchedulerValidationError(
                "continue_on_job_failure must be a boolean."
            )

        if (
            self.execution_history_limit is not None
            and self.execution_history_limit <= 0
        ):
            raise ReconciliationSLASchedulerValidationError(
                "execution_history_limit must be positive."
            )


@dataclass(frozen=True, slots=True)
class ReconciliationSLAJobStatus:
    """Immutable observable status for a registered SLA job."""

    job_id: str
    interval: timedelta
    next_run_at: datetime


@dataclass(frozen=True, slots=True)
class ReconciliationSLAJobExecution:
    """Immutable record of one scheduler job execution."""

    job_id: str
    scheduled_at: datetime
    succeeded: bool
    error_message: str | None = None
    completed_at: datetime | None = None
    attempts_used: int | None = None

    def __post_init__(self) -> None:
        """Validate execution record data."""

        if not self.job_id.strip():
            raise ReconciliationSLASchedulerValidationError(
                "job_id must not be blank."
            )

        if (
            self.scheduled_at.tzinfo is None
            or self.scheduled_at.utcoffset() is None
        ):
            raise ReconciliationSLASchedulerValidationError(
                "scheduled_at must be timezone-aware."
            )

        if (
            self.completed_at is not None
            and (
                self.completed_at.tzinfo is None
                or self.completed_at.utcoffset() is None
            )
        ):
            raise ReconciliationSLASchedulerValidationError(
                "completed_at must be timezone-aware."
            )

        if (
            self.completed_at is not None
            and self.completed_at < self.scheduled_at
        ):
            raise ReconciliationSLASchedulerValidationError(
                "completed_at cannot be before scheduled_at."
            )

        if self.succeeded and self.error_message is not None:
            raise ReconciliationSLASchedulerValidationError(
                "successful execution cannot have an error message."
            )

        if (
            not self.succeeded
            and (
                self.error_message is None
                or not self.error_message.strip()
            )
        ):
            raise ReconciliationSLASchedulerValidationError(
                "failed execution must have an error message."
            )

        if (
            self.attempts_used is not None
            and self.attempts_used <= 0
        ):
            raise ReconciliationSLASchedulerValidationError(
                "attempts_used must be positive."
            )

class ReconciliationSLAExecutionHistoryRepository(
    Protocol
):
    """Persistence contract for scheduler execution history."""

    def load_history(
        self,
    ) -> tuple[ReconciliationSLAJobExecution, ...]:
        """Return persisted scheduler executions."""

        ...

    def save_history(
        self,
        executions: tuple[
            ReconciliationSLAJobExecution,
            ...,
        ],
    ) -> None:
        """Replace persisted scheduler executions."""

        ...
@dataclass(frozen=True, slots=True)
class _RegisteredReconciliationSLAJob:
    """Internal registration record for a recurring SLA job."""

    job_id: str
    job: ReconciliationSLAScheduledJob
    interval: timedelta
    next_run_at: datetime


class ReconciliationSLAScheduler:
    """Register and coordinate recurring reconciliation SLA jobs."""

    def __init__(
        self,
        *,
        config: ReconciliationSLASchedulerConfig,
        clock: Callable[[], datetime] = _utc_now,
        delay: Callable[[float], None] = sleep,
        execution_history_repository: (
            ReconciliationSLAExecutionHistoryRepository | None
        ) = None,
    ) -> None:
        self._config = config
        self._clock = clock
        self._delay = delay
        self._execution_history_repository = (
            execution_history_repository
        )
        self._registered_jobs: dict[
            str,
            _RegisteredReconciliationSLAJob,
        ] = {}

        if self._execution_history_repository is None:
            self._execution_history: list[
                ReconciliationSLAJobExecution
            ] = []
        else:
            self._execution_history = list(
                self._execution_history_repository.load_history()
            )

        limit = self._config.execution_history_limit

        if (
            limit is not None
            and len(self._execution_history) > limit
        ):
            del self._execution_history[:-limit]

        self._is_running = False

    def register_job(
        self,
        *,
        job_id: str,
        job: ReconciliationSLAScheduledJob,
        interval: timedelta,
        next_run_at: datetime,
    ) -> None:
        """Register a recurring reconciliation SLA job."""

        if not job_id.strip():
            raise ReconciliationSLASchedulerValidationError(
                "job_id must not be blank."
            )

        if job_id in self._registered_jobs:
            raise ReconciliationSLASchedulerValidationError(
                "job_id is already registered."
            )

        if interval <= timedelta(0):
            raise ReconciliationSLASchedulerValidationError(
                "interval must be positive."
            )

        if (
            next_run_at.tzinfo is None
            or next_run_at.utcoffset() is None
        ):
            raise ReconciliationSLASchedulerValidationError(
                "next_run_at must be timezone-aware."
            )

        self._registered_jobs[job_id] = (
            _RegisteredReconciliationSLAJob(
                job_id=job_id,
                job=job,
                interval=interval,
                next_run_at=next_run_at,
            )
        )

    def unregister_job(
        self,
        *,
        job_id: str,
    ) -> None:
        """Remove a registered reconciliation SLA job."""

        if job_id not in self._registered_jobs:
            raise ReconciliationSLASchedulerValidationError(
                "job_id is not registered."
            )

        del self._registered_jobs[job_id]

    def run_due_jobs(
        self,
        *,
        as_of: datetime,
    ) -> dict[
        str,
        ReconciliationSLAScheduledJobResult,
    ]:
        """Execute due jobs and advance successful schedules."""

        if (
            as_of.tzinfo is None
            or as_of.utcoffset() is None
        ):
            raise ReconciliationSLASchedulerValidationError(
                "as_of must be timezone-aware."
            )

        results: dict[
            str,
            ReconciliationSLAScheduledJobResult,
        ] = {}

        for registration in tuple(
            self._registered_jobs.values()
        ):
            if registration.next_run_at > as_of:
                continue

            try:
                result = registration.job.run_once(
                    scheduled_at=registration.next_run_at,
                )
            except Exception as error:
                self._record_execution(
                    ReconciliationSLAJobExecution(
                        job_id=registration.job_id,
                        scheduled_at=registration.next_run_at,
                        succeeded=False,
                        error_message=str(error),
                        completed_at=as_of,
                    )
                )

                if self._config.continue_on_job_failure:
                    self._advance_job_schedule(registration)
                    continue

                raise

            results[registration.job_id] = result

            self._record_execution(
                ReconciliationSLAJobExecution(
                    job_id=registration.job_id,
                    scheduled_at=registration.next_run_at,
                    succeeded=True,
                    completed_at=as_of,
                    attempts_used=(
                        self._attempts_used_from_result(result)
                    ),
                )
            )

            self._advance_job_schedule(registration)

        return results

    def run_forever(self) -> None:
        """Run scheduler cycles until stopped or execution fails."""

        self.start()

        try:
            while self._is_running:
                self.run_cycle(
                    as_of=self._clock(),
                )

                if self._is_running:
                    self.wait_for_next_cycle()
        finally:
            self.stop()

    def wait_for_next_cycle(self) -> None:
        """Wait for the configured scheduler polling interval."""

        self._delay(
            self._config.poll_interval.total_seconds()
        )

    def run_cycle(
        self,
        *,
        as_of: datetime,
    ) -> dict[
        str,
        ReconciliationSLAScheduledJobResult,
    ]:
        """Execute one cycle only while the scheduler is running."""

        if not self._is_running:
            return {}

        return self.run_due_jobs(
            as_of=as_of,
        )

    def start(self) -> None:
        """Mark the scheduler lifecycle as running."""

        self._is_running = True

    def stop(self) -> None:
        """Mark the scheduler lifecycle as stopped."""

        self._is_running = False

    @property
    def is_running(self) -> bool:
        """Return whether the scheduler lifecycle is running."""

        return self._is_running

    @property
    def registered_job_count(self) -> int:
        """Return the number of registered jobs."""

        return len(self._registered_jobs)

    @property
    def registered_job_ids(self) -> tuple[str, ...]:
        """Return registered job identifiers in registration order."""

        return tuple(self._registered_jobs)

    @staticmethod
    def _attempts_used_from_result(
        result: ReconciliationSLAScheduledJobResult,
    ) -> int | None:
        """Return a concrete attempts count when the result exposes one."""

        attempts_used = getattr(
            result,
            "attempts_used",
            None,
        )

        if type(attempts_used) is not int:
            return None

        return attempts_used
    def _advance_job_schedule(
        self,
        registration: _RegisteredReconciliationSLAJob,
    ) -> None:
        """Advance a registered job to its next occurrence."""

        self._registered_jobs[registration.job_id] = (
            _RegisteredReconciliationSLAJob(
                job_id=registration.job_id,
                job=registration.job,
                interval=registration.interval,
                next_run_at=(
                    registration.next_run_at
                    + registration.interval
                ),
            )
        )

    def _record_execution(
        self,
        execution: ReconciliationSLAJobExecution,
    ) -> None:
        """Record, retain, and persist a scheduler execution."""

        self._execution_history.append(execution)

        limit = self._config.execution_history_limit

        if (
            limit is not None
            and len(self._execution_history) > limit
        ):
            del self._execution_history[:-limit]

        if self._execution_history_repository is not None:
            self._execution_history_repository.save_history(
                tuple(self._execution_history)
            )

    @property
    def execution_history(
        self,
    ) -> tuple[ReconciliationSLAJobExecution, ...]:
        """Return immutable snapshots of recorded executions."""

        return tuple(self._execution_history)

    def get_execution_history(
        self,
        *,
        job_id: str,
    ) -> tuple[ReconciliationSLAJobExecution, ...]:
        """Return execution records for one job."""

        if not job_id.strip():
            raise ReconciliationSLASchedulerValidationError(
                "job_id must not be blank."
            )

        return tuple(
            execution
            for execution in self._execution_history
            if execution.job_id == job_id
        )
    def get_latest_execution(
        self,
        *,
        job_id: str,
    ) -> ReconciliationSLAJobExecution:
        """Return the most recent execution record for one job."""

        history = self.get_execution_history(
            job_id=job_id,
        )

        if not history:
            raise ReconciliationSLASchedulerValidationError(
                "job_id has no execution history."
            )

        return history[-1]

    def clear_execution_history(self) -> None:
        """Remove all recorded and persisted scheduler executions."""

        self._execution_history.clear()

        if self._execution_history_repository is not None:
            self._execution_history_repository.save_history(())

    def remove_execution_history(
        self,
        *,
        job_id: str,
    ) -> None:
        """Remove and persist execution history for one job."""

        if not job_id.strip():
            raise ReconciliationSLASchedulerValidationError(
                "job_id must not be blank."
            )

        self._execution_history[:] = [
            execution
            for execution in self._execution_history
            if execution.job_id != job_id
        ]

        if self._execution_history_repository is not None:
            self._execution_history_repository.save_history(
                tuple(self._execution_history)
            )
    @property
    def job_statuses(
        self,
    ) -> tuple[ReconciliationSLAJobStatus, ...]:
        """Return immutable snapshots for all registered jobs."""

        return tuple(
            self._status_from_registration(registration)
            for registration in self._registered_jobs.values()
        )

    def get_job_status(
        self,
        *,
        job_id: str,
    ) -> ReconciliationSLAJobStatus:
        """Return an immutable snapshot for one registered job."""

        try:
            registration = self._registered_jobs[job_id]
        except KeyError as error:
            raise ReconciliationSLASchedulerValidationError(
                "job_id is not registered."
            ) from error

        return self._status_from_registration(registration)

    @staticmethod
    def _status_from_registration(
        registration: _RegisteredReconciliationSLAJob,
    ) -> ReconciliationSLAJobStatus:
        """Build a public status without exposing scheduler internals."""

        return ReconciliationSLAJobStatus(
            job_id=registration.job_id,
            interval=registration.interval,
            next_run_at=registration.next_run_at,
        )


__all__ = [
    "ReconciliationSLAExecutionHistoryRepository",
    "ReconciliationSLAJobExecution",
    "ReconciliationSLAJobStatus",
    "ReconciliationSLAScheduler",
    "ReconciliationSLASchedulerConfig",
    "ReconciliationSLASchedulerValidationError",
]