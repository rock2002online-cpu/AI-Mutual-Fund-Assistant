"""Persistent storage for reconciliation SLA scheduler job states."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from services.reconciliation_sla_scheduler import (
    ReconciliationSLAJobStatus,
)


class ReconciliationSLAJobStateRepositoryError(ValueError):
    """Raised when persisted scheduler job state is invalid."""


class JSONReconciliationSLAJobStateRepository:
    """Store scheduler job states in a JSON file."""

    def __init__(
        self,
        *,
        file_path: str | Path,
    ) -> None:
        self._file_path = Path(file_path)

    def save_job_statuses(
        self,
        statuses: tuple[ReconciliationSLAJobStatus, ...],
    ) -> None:
        """Atomically replace stored scheduler job states."""

        payload = [
            {
                "job_id": status.job_id,
                "interval_seconds": (
                    status.interval.total_seconds()
                ),
                "next_run_at": status.next_run_at.isoformat(),
                "is_paused": status.is_paused,
            }
            for status in statuses
        ]

        self._file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = self._file_path.with_name(
            f".{self._file_path.name}.tmp"
        )

        try:
            temporary_path.write_text(
                json.dumps(payload),
                encoding="utf-8",
            )
            temporary_path.replace(self._file_path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    def load_job_statuses(
        self,
    ) -> tuple[ReconciliationSLAJobStatus, ...]:
        """Return stored scheduler job states."""

        if not self._file_path.exists():
            return ()

        try:
            payload = json.loads(
                self._file_path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as error:
            raise ReconciliationSLAJobStateRepositoryError(
                "job state file is invalid."
            ) from error

        try:
            statuses = tuple(
                self._status_from_item(item)
                for item in payload
            )

            job_ids = tuple(
                status.job_id
                for status in statuses
            )

            if len(set(job_ids)) != len(job_ids):
                raise ValueError(
                    "job_id values must be unique."
                )

            return statuses
        except (
            KeyError,
            TypeError,
            ValueError,
            OverflowError,
        ) as error:
            raise ReconciliationSLAJobStateRepositoryError(
                "job state file is invalid."
            ) from error

    @staticmethod
    def _status_from_item(
        item: dict[str, object],
    ) -> ReconciliationSLAJobStatus:
        """Deserialize and validate one persisted job state."""

        job_id = item["job_id"]
        interval = timedelta(
            seconds=item["interval_seconds"],
        )
        next_run_at = datetime.fromisoformat(
            item["next_run_at"]
        )
        is_paused = item["is_paused"]

        if (
            not isinstance(job_id, str)
            or not job_id.strip()
        ):
            raise ValueError("job_id must not be blank.")

        if interval <= timedelta(0):
            raise ValueError("interval must be positive.")

        if (
            next_run_at.tzinfo is None
            or next_run_at.utcoffset() is None
        ):
            raise ValueError(
                "next_run_at must be timezone-aware."
            )

        if type(is_paused) is not bool:
            raise ValueError("is_paused must be a boolean.")

        return ReconciliationSLAJobStatus(
            job_id=job_id,
            interval=interval,
            next_run_at=next_run_at,
            is_paused=is_paused,
        )


__all__ = [
    "JSONReconciliationSLAJobStateRepository",
    "ReconciliationSLAJobStateRepositoryError",
]