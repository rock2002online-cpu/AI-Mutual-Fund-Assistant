"""Persistent storage for reconciliation SLA recovery history."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from services.reconciliation_sla_scheduler import (
    ReconciliationSLARecoveryReport,
)


class ReconciliationSLARecoveryHistoryRepositoryError(
    ValueError
):
    """Raised when persistent recovery history is invalid."""


class JSONReconciliationSLARecoveryHistoryRepository:
    """Store scheduler recovery history in a JSON file."""

    def __init__(
        self,
        *,
        file_path: str | Path,
    ) -> None:
        self._file_path = Path(file_path)

    def save_history(
        self,
        reports: tuple[
            ReconciliationSLARecoveryReport,
            ...,
        ],
    ) -> None:
        """Atomically replace stored recovery history."""

        payload = [
            {
                "recovered_job_ids": list(
                    report.recovered_job_ids
                ),
                "missing_job_ids": list(
                    report.missing_job_ids
                ),
                "pending_job_ids": list(
                    report.pending_job_ids
                ),
                "recorded_at": report.recorded_at.isoformat(),
            }
            for report in reports
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
    ) -> tuple[ReconciliationSLARecoveryReport, ...]:
        """Return stored recovery history."""

        if not self._file_path.exists():
            return ()

        try:
            payload = json.loads(
                self._file_path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as error:
            raise (
                ReconciliationSLARecoveryHistoryRepositoryError(
                    "recovery history file is invalid."
                )
            ) from error

        try:
            return tuple(
                ReconciliationSLARecoveryReport(
                    recovered_job_ids=tuple(
                        item["recovered_job_ids"]
                    ),
                    missing_job_ids=tuple(
                        item["missing_job_ids"]
                    ),
                    pending_job_ids=tuple(
                        item["pending_job_ids"]
                    ),
                    recorded_at=datetime.fromisoformat(
                        item["recorded_at"]
                    ),
                )
                for item in payload
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            OverflowError,
        ) as error:
            raise (
                ReconciliationSLARecoveryHistoryRepositoryError(
                    "recovery history file is invalid."
                )
            ) from error


__all__ = [
    "JSONReconciliationSLARecoveryHistoryRepository",
    "ReconciliationSLARecoveryHistoryRepositoryError",
]