"""Tests for persistent reconciliation SLA execution history."""

from datetime import datetime, timezone
from pathlib import Path
import pytest

from services.reconciliation_sla_execution_history_repository import (
    JSONReconciliationSLAExecutionHistoryRepository,
    ReconciliationSLAExecutionHistoryRepositoryError,
)
from services.reconciliation_sla_scheduler import (
    ReconciliationSLAJobExecution,
)


SCHEDULED_AT = datetime(
    2026,
    7,
    28,
    10,
    0,
    tzinfo=timezone.utc,
)
COMPLETED_AT = datetime(
    2026,
    7,
    28,
    10,
    0,
    5,
    tzinfo=timezone.utc,
)


def make_successful_execution() -> ReconciliationSLAJobExecution:
    """Return a valid successful scheduler execution."""

    return ReconciliationSLAJobExecution(
        job_id="portfolio-901-sla",
        scheduled_at=SCHEDULED_AT,
        succeeded=True,
        completed_at=COMPLETED_AT,
        attempts_used=2,
    )


def test_new_repository_has_empty_execution_history(
    tmp_path,
) -> None:
    """A repository without a storage file should contain no history."""

    repository = JSONReconciliationSLAExecutionHistoryRepository(
        file_path=tmp_path / "scheduler_execution_history.json",
    )

    assert repository.load_history() == ()


def test_repository_saves_and_reloads_successful_execution(
    tmp_path,
) -> None:
    """A saved successful execution should survive repository recreation."""

    file_path = tmp_path / "scheduler_execution_history.json"
    execution = make_successful_execution()
    repository = JSONReconciliationSLAExecutionHistoryRepository(
        file_path=file_path,
    )

    repository.save_history((execution,))

    reloaded_repository = (
        JSONReconciliationSLAExecutionHistoryRepository(
            file_path=file_path,
        )
    )

    assert reloaded_repository.load_history() == (execution,)


def test_repository_saves_and_reloads_failed_execution(
    tmp_path,
) -> None:
    """A failed execution should retain its error details."""

    file_path = tmp_path / "scheduler_execution_history.json"
    execution = ReconciliationSLAJobExecution(
        job_id="portfolio-902-sla",
        scheduled_at=SCHEDULED_AT,
        succeeded=False,
        error_message="Notification delivery failed.",
        completed_at=COMPLETED_AT,
    )
    repository = JSONReconciliationSLAExecutionHistoryRepository(
        file_path=file_path,
    )

    repository.save_history((execution,))

    reloaded_repository = (
        JSONReconciliationSLAExecutionHistoryRepository(
            file_path=file_path,
        )
    )

    assert reloaded_repository.load_history() == (execution,)


def test_repository_creates_missing_parent_directories(
    tmp_path,
) -> None:
    """Saving history should create its storage directory when absent."""

    file_path = (
        tmp_path
        / "runtime"
        / "scheduler"
        / "execution_history.json"
    )
    repository = JSONReconciliationSLAExecutionHistoryRepository(
        file_path=file_path,
    )
    execution = make_successful_execution()

    repository.save_history((execution,))

    assert file_path.exists()
    assert repository.load_history() == (execution,)


def test_repository_rejects_malformed_json(
    tmp_path,
) -> None:
    """Malformed persistent history should raise a repository error."""

    file_path = tmp_path / "scheduler_execution_history.json"
    file_path.write_text(
        "{not-valid-json",
        encoding="utf-8",
    )
    repository = JSONReconciliationSLAExecutionHistoryRepository(
        file_path=file_path,
    )

    with pytest.raises(
        ReconciliationSLAExecutionHistoryRepositoryError,
        match="execution history file is invalid",
    ):
        repository.load_history()
def test_repository_replaces_history_file_atomically(
    tmp_path,
    monkeypatch,
) -> None:
    """Saving history should replace the target from a temporary file."""

    file_path = tmp_path / "scheduler_execution_history.json"
    repository = JSONReconciliationSLAExecutionHistoryRepository(
        file_path=file_path,
    )
    replacements: list[tuple[Path, Path]] = []
    original_replace = Path.replace

    def tracking_replace(
        source: Path,
        target: Path,
    ) -> Path:
        replacements.append(
            (
                source,
                Path(target),
            )
        )
        return original_replace(source, target)

    monkeypatch.setattr(
        Path,
        "replace",
        tracking_replace,
    )

    repository.save_history(
        (make_successful_execution(),)
    )

    assert len(replacements) == 1
    temporary_path, replacement_target = replacements[0]
    assert temporary_path != file_path
    assert replacement_target == file_path
    assert not temporary_path.exists()