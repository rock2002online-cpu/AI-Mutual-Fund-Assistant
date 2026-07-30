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
    recovery_history_limit: int | None = None
    continue_on_job_failure: bool = False
    coalesce_missed_runs: bool = False

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

        if type(self.coalesce_missed_runs) is not bool:
            raise ReconciliationSLASchedulerValidationError(
                "coalesce_missed_runs must be a boolean."
            )

        if (
            self.execution_history_limit is not None
            and self.execution_history_limit <= 0
        ):
            raise ReconciliationSLASchedulerValidationError(
                "execution_history_limit must be positive."
            )

        if (
            self.recovery_history_limit is not None
            and self.recovery_history_limit <= 0
        ):
            raise ReconciliationSLASchedulerValidationError(
                "recovery_history_limit must be positive."
            )


@dataclass(frozen=True, slots=True)
class ReconciliationSLAJobStatus:
    """Immutable observable status for a registered SLA job."""

    job_id: str
    interval: timedelta
    next_run_at: datetime
    is_paused: bool = False


@dataclass(frozen=True, slots=True)
class ReconciliationSLARecoveryReport:
    """Immutable result of one scheduler recovery operation."""

    recovered_job_ids: tuple[str, ...]
    missing_job_ids: tuple[str, ...]
    pending_job_ids: tuple[str, ...]
    recorded_at: datetime

    def __post_init__(self) -> None:
        """Validate recovery audit report data."""

        if (
            self.recorded_at.tzinfo is None
            or self.recorded_at.utcoffset() is None
        ):
            raise ReconciliationSLASchedulerValidationError(
                "recorded_at must be timezone-aware."
            )

    @property
    def recovered_job_count(self) -> int:
        """Return the number of successfully recovered jobs."""

        return len(self.recovered_job_ids)

    @property
    def missing_job_count(self) -> int:
        """Return the number of runtime jobs without persisted state."""

        return len(self.missing_job_ids)

    @property
    def pending_job_count(self) -> int:
        """Return the number of persisted jobs still awaiting recovery."""

        return len(self.pending_job_ids)

    @property
    def is_complete(self) -> bool:
        """Return whether recovery has no missing or pending jobs."""

        return (
            not self.missing_job_ids
            and not self.pending_job_ids
        )


class ReconciliationSLAJobStateRepository(Protocol):
    """Persistence contract for scheduler job states."""

    def load_job_statuses(
        self,
    ) -> tuple[ReconciliationSLAJobStatus, ...]:
        """Return persisted scheduler job states."""

        ...

    def save_job_statuses(
        self,
        statuses: tuple[ReconciliationSLAJobStatus, ...],
    ) -> None:
        """Replace persisted scheduler job states."""

        ...


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
    is_paused: bool = False


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
        job_state_repository: (
            ReconciliationSLAJobStateRepository | None
        ) = None,
    ) -> None:
        self._config = config
        self._clock = clock
        self._delay = delay
        self._execution_history_repository = (
            execution_history_repository
        )
        self._job_state_repository = job_state_repository
        if self._job_state_repository is None:
            self._persisted_job_statuses: dict[
                str,
                ReconciliationSLAJobStatus,
            ] = {}
        else:
            self._persisted_job_statuses = {
                status.job_id: status
                for status
                in self._job_state_repository.load_job_statuses()
            }
        self._registered_jobs: dict[
            str,
            _RegisteredReconciliationSLAJob,
        ] = {}

        self._recovery_history: list[
            ReconciliationSLARecoveryReport
        ] = []

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

        self._validate_job_schedule(
            interval=interval,
            next_run_at=next_run_at,
        )
        persisted_status = self._persisted_job_statuses.get(
            job_id
        )

        if persisted_status is not None:
            self._validate_job_schedule(
                interval=persisted_status.interval,
                next_run_at=persisted_status.next_run_at,
            )
            interval = persisted_status.interval
            next_run_at = persisted_status.next_run_at
            is_paused = persisted_status.is_paused
        else:
            is_paused = False

        self._registered_jobs[job_id] = (
            _RegisteredReconciliationSLAJob(
                job_id=job_id,
                job=job,
                interval=interval,
                next_run_at=next_run_at,
                is_paused=is_paused,
            )
        )

        self._persist_job_statuses()

    def recover_job(
        self,
        *,
        job_id: str,
        job: ReconciliationSLAScheduledJob,
    ) -> None:
        """Register a runtime job using its persisted scheduler state."""

        try:
            persisted_status = self._persisted_job_statuses[
                job_id
            ]
        except KeyError as error:
            raise ReconciliationSLASchedulerValidationError(
                "job_id is not pending recovery."
            ) from error

        if job_id in self._registered_jobs:
            raise ReconciliationSLASchedulerValidationError(
                "job_id is already registered."
            )

        self.register_job(
            job_id=job_id,
            job=job,
            interval=persisted_status.interval,
            next_run_at=persisted_status.next_run_at,
        )

    def recover_jobs(
        self,
        *,
        jobs_by_id: dict[
            str,
            ReconciliationSLAScheduledJob,
        ],
    ) -> tuple[str, ...]:
        """Atomically register runtime jobs from persisted states."""

        pending_job_ids = set(
            self.pending_recovery_job_ids
        )

        for job_id in jobs_by_id:
            if job_id not in pending_job_ids:
                raise ReconciliationSLASchedulerValidationError(
                    "job_id is not pending recovery."
                )

        recovered_job_ids: list[str] = []

        for job_id, job in jobs_by_id.items():
            self.recover_job(
                job_id=job_id,
                job=job,
            )
            recovered_job_ids.append(job_id)

        return tuple(recovered_job_ids)

    def recover_jobs_with_report(
        self,
        *,
        jobs_by_id: dict[
            str,
            ReconciliationSLAScheduledJob,
        ],
    ) -> ReconciliationSLARecoveryReport:
        """Recover jobs and report missing and pending states."""

        pending_job_ids = set(
            self.pending_recovery_job_ids
        )
        recoverable_jobs = {
            job_id: job
            for job_id, job in jobs_by_id.items()
            if job_id in pending_job_ids
        }
        missing_job_ids = tuple(
            job_id
            for job_id in jobs_by_id
            if job_id not in pending_job_ids
        )

        recovered_job_ids = self.recover_jobs(
            jobs_by_id=recoverable_jobs,
        )

        report = ReconciliationSLARecoveryReport(
            recovered_job_ids=recovered_job_ids,
            missing_job_ids=missing_job_ids,
            pending_job_ids=self.pending_recovery_job_ids,
            recorded_at=self._clock(),
        )
        self._recovery_history.append(report)
        limit = self._config.recovery_history_limit

        if (
            limit is not None
            and len(self._recovery_history) > limit
        ):
            del self._recovery_history[:-limit]

        return report

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
        self._persisted_job_statuses.pop(
            job_id,
            None,
        )

        self._persist_job_statuses()

    def discard_pending_recovery(
        self,
        *,
        job_id: str,
    ) -> None:
        """Remove an obsolete persisted state awaiting recovery."""

        if job_id in self._registered_jobs:
            raise ReconciliationSLASchedulerValidationError(
                "job_id is already registered."
            )

        if job_id not in self._persisted_job_statuses:
            raise ReconciliationSLASchedulerValidationError(
                "job_id is not pending recovery."
            )

        del self._persisted_job_statuses[job_id]

        self._persist_job_statuses()

    def pause_job(
        self,
        *,
        job_id: str,
    ) -> None:
        """Pause a registered reconciliation SLA job."""

        self._set_job_paused(
            job_id=job_id,
            is_paused=True,
        )

    def resume_job(
        self,
        *,
        job_id: str,
    ) -> None:
        """Resume a paused reconciliation SLA job."""

        self._set_job_paused(
            job_id=job_id,
            is_paused=False,
        )
    def reschedule_job(
        self,
        *,
        job_id: str,
        interval: timedelta,
        next_run_at: datetime,
    ) -> None:
        """Update the schedule of a registered reconciliation SLA job."""

        try:
            registration = self._registered_jobs[job_id]
        except KeyError as error:
            raise ReconciliationSLASchedulerValidationError(
                "job_id is not registered."
            ) from error
        self._validate_job_schedule(
            interval=interval,
            next_run_at=next_run_at,
        )

        self._registered_jobs[job_id] = (
            _RegisteredReconciliationSLAJob(
                job_id=registration.job_id,
                job=registration.job,
                interval=interval,
                next_run_at=next_run_at,
                is_paused=registration.is_paused,
            )
        )
        self._persist_job_statuses()
    def run_job_now(
        self,
        *,
        job_id: str,
        as_of: datetime,
    ) -> ReconciliationSLAScheduledJobResult:
        """Execute one registered reconciliation SLA job immediately."""

        try:
            registration = self._registered_jobs[job_id]
        except KeyError as error:
            raise ReconciliationSLASchedulerValidationError(
                "job_id is not registered."
            ) from error
        if registration.is_paused:
            raise ReconciliationSLASchedulerValidationError(
                "job_id is paused."
            )

        self._validate_as_of(as_of)

        try:
            result = registration.job.run_once(
                scheduled_at=as_of,
            )
        except Exception as error:
            self._record_execution(
                ReconciliationSLAJobExecution(
                    job_id=registration.job_id,
                    scheduled_at=as_of,
                    succeeded=False,
                    error_message=str(error),
                    completed_at=as_of,
                )
            )
            raise

        self._record_execution(
            ReconciliationSLAJobExecution(
                job_id=registration.job_id,
                scheduled_at=as_of,
                succeeded=True,
                completed_at=as_of,
                attempts_used=(
                    self._attempts_used_from_result(result)
                ),
            )
        )

        return result
    def _set_job_paused(
        self,
        *,
        job_id: str,
        is_paused: bool,
    ) -> None:
        """Replace a registration with updated paused state."""

        try:
            registration = self._registered_jobs[job_id]
        except KeyError as error:
            raise ReconciliationSLASchedulerValidationError(
                "job_id is not registered."
            ) from error

        self._registered_jobs[job_id] = (
            _RegisteredReconciliationSLAJob(
                job_id=registration.job_id,
                job=registration.job,
                interval=registration.interval,
                next_run_at=registration.next_run_at,
                is_paused=is_paused,
            )
        )
        self._persist_job_statuses()

    def run_due_jobs(
        self,
        *,
        as_of: datetime,
    ) -> dict[
        str,
        ReconciliationSLAScheduledJobResult,
    ]:
        """Execute due jobs and advance successful schedules."""

        self._validate_as_of(as_of)
        results: dict[
            str,
            ReconciliationSLAScheduledJobResult,
        ] = {}

        for registration in tuple(
            self._registered_jobs.values()
        ):
            if registration.is_paused:
                continue

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
                    self._advance_job_schedule(
                        registration,
                        as_of=as_of,
                    )
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

            self._advance_job_schedule(
                registration,
                as_of=as_of,
            )

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

    @property
    def pending_recovery_job_ids(self) -> tuple[str, ...]:
        """Return persisted job IDs awaiting runtime registration."""

        return tuple(
            job_id
            for job_id in self._persisted_job_statuses
            if job_id not in self._registered_jobs
        )

    @property
    def pending_recovery_job_statuses(
        self,
    ) -> tuple[ReconciliationSLAJobStatus, ...]:
        """Return persisted job states awaiting runtime registration."""

        return tuple(
            status
            for job_id, status
            in self._persisted_job_statuses.items()
            if job_id not in self._registered_jobs
        )

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
    @staticmethod
    def _validate_as_of(
        as_of: datetime,
    ) -> None:
        """Validate a scheduler execution timestamp."""

        if (
            as_of.tzinfo is None
            or as_of.utcoffset() is None
        ):
            raise ReconciliationSLASchedulerValidationError(
                "as_of must be timezone-aware."
            )
    @staticmethod
    def _validate_job_schedule(
        *,
        interval: timedelta,
        next_run_at: datetime,
    ) -> None:
        """Validate recurring scheduler timing values."""

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
    def _advance_job_schedule(
        self,
        registration: _RegisteredReconciliationSLAJob,
        *,
        as_of: datetime,
    ) -> None:
        """Advance a registered job to its next occurrence."""

        next_run_at = (
            registration.next_run_at
            + registration.interval
        )

        if (
            self._config.coalesce_missed_runs
            and next_run_at <= as_of
        ):
            missed_intervals = (
                (as_of - next_run_at)
                // registration.interval
                + 1
            )
            next_run_at += (
                registration.interval
                * missed_intervals
            )

        self._registered_jobs[registration.job_id] = (
            _RegisteredReconciliationSLAJob(
                job_id=registration.job_id,
                job=registration.job,
                interval=registration.interval,
                next_run_at=next_run_at,
                is_paused=registration.is_paused,
            )
        )
        self._persist_job_statuses()
    def _persist_job_statuses(self) -> None:
        """Persist registered and pending restored job states."""

        if self._job_state_repository is None:
            return

        for status in self.job_statuses:
            self._persisted_job_statuses[
                status.job_id
            ] = status

        self._job_state_repository.save_job_statuses(
            tuple(self._persisted_job_statuses.values())
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

    @property
    def recovery_history(
        self,
    ) -> tuple[ReconciliationSLARecoveryReport, ...]:
        """Return immutable snapshots of recovery reports."""

        return tuple(self._recovery_history)

    def clear_recovery_history(self) -> None:
        """Remove all in-memory scheduler recovery audit reports."""

        self._recovery_history.clear()

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
            is_paused=registration.is_paused,
        )


__all__ = [
    "ReconciliationSLAExecutionHistoryRepository",
    "ReconciliationSLAJobExecution",
    "ReconciliationSLAJobStatus",
    "ReconciliationSLAScheduler",
    "ReconciliationSLASchedulerConfig",
    "ReconciliationSLASchedulerValidationError",
    "ReconciliationSLARecoveryReport",
]
