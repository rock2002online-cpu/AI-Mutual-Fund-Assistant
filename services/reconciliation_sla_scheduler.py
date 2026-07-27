"""Scheduler orchestration for reconciliation SLA jobs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import sleep
from typing import Callable

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

    def __post_init__(self) -> None:
        """Validate scheduler configuration."""

        if self.poll_interval <= timedelta(0):
            raise ReconciliationSLASchedulerValidationError(
                "poll_interval must be positive."
            )


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
    ) -> None:
        self._config = config
        self._clock = clock
        self._delay = delay
        self._registered_jobs: dict[
            str,
            _RegisteredReconciliationSLAJob,
        ] = {}
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

            results[registration.job_id] = (
                registration.job.run_once(
                    scheduled_at=registration.next_run_at,
                )
            )

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


__all__ = [
    "ReconciliationSLAScheduler",
    "ReconciliationSLASchedulerConfig",
    "ReconciliationSLASchedulerValidationError",
]