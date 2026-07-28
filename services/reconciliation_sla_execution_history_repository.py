"""Persistent storage for reconciliation SLA execution history."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from services.reconciliation_sla_scheduler import (
    ReconciliationSLAJobExecution,
)


class ReconciliationSLAExecutionHistoryRepositoryError(
    ValueError
):
    """Raised when persistent execution history is invalid."""


class JSONReconciliationSLAExecutionHistoryRepository:
    """Store scheduler execution history in a JSON file."""

    def __init__(
        self,
        *,
        file_path: str | Path,
    ) -> None:
        self._file_path = Path(file_path)

    def save_history(
        self,
        executions: tuple[
            ReconciliationSLAJobExecution,
            ...,
        ],
    ) -> None:
        """Atomically replace stored execution history."""

        payload = [
            {
                "job_id": execution.job_id,
                "scheduled_at": execution.scheduled_at.isoformat(),
                "succeeded": execution.succeeded,
                "error_message": execution.error_message,
                "completed_at": (
                    execution.completed_at.isoformat()
                    if execution.completed_at is not None
                    else None
                ),
                "attempts_used": execution.attempts_used,
            }
            for execution in executions
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

    def load_history(
        self,
    ) -> tuple[ReconciliationSLAJobExecution, ...]:
        """Return stored execution history."""

        if not self._file_path.exists():
            return ()

        try:
            payload = json.loads(
                self._file_path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as error:
            raise (
                ReconciliationSLAExecutionHistoryRepositoryError(
                    "execution history file is invalid."
                )
            ) from error

        return tuple(
            ReconciliationSLAJobExecution(
                job_id=item["job_id"],
                scheduled_at=(
                    self._parse_datetime(item["scheduled_at"])
                ),
                succeeded=item["succeeded"],
                error_message=item["error_message"],
                completed_at=(
                    self._parse_datetime(item["completed_at"])
                    if item["completed_at"] is not None
                    else None
                ),
                attempts_used=item["attempts_used"],
            )
            for item in payload
        )

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        """Parse an ISO-formatted datetime value."""

        return datetime.fromisoformat(value)


__all__ = [
    "JSONReconciliationSLAExecutionHistoryRepository",
    "ReconciliationSLAExecutionHistoryRepositoryError",
]