"""Tests for persistent reconciliation SLA scheduler job states."""

from datetime import datetime, timedelta, timezone
import pytest
from pathlib import Path
from services.reconciliation_sla_job_state_repository import (
    JSONReconciliationSLAJobStateRepository,
    ReconciliationSLAJobStateRepositoryError,
)
from services.reconciliation_sla_scheduler import (
    ReconciliationSLAJobStatus,
)


NEXT_RUN_AT = datetime(
    2026,
    8,
    1,
    10,
    0,
    tzinfo=timezone.utc,
)


def test_new_repository_has_no_job_states(
    tmp_path,
) -> None:
    """A repository without a storage file should contain no states."""

    repository = JSONReconciliationSLAJobStateRepository(
        file_path=tmp_path / "scheduler_job_states.json",
    )

    assert repository.load_job_statuses() == ()


def test_repository_saves_and_reloads_job_states(
    tmp_path,
) -> None:
    """Saved job states should survive repository recreation."""

    file_path = tmp_path / "scheduler_job_states.json"
    status = ReconciliationSLAJobStatus(
        job_id="portfolio-901-sla",
        interval=timedelta(minutes=15),
        next_run_at=NEXT_RUN_AT,
        is_paused=True,
    )
    repository = JSONReconciliationSLAJobStateRepository(
        file_path=file_path,
    )

    repository.save_job_statuses((status,))

    reloaded_repository = JSONReconciliationSLAJobStateRepository(
        file_path=file_path,
    )

    assert reloaded_repository.load_job_statuses() == (status,)
def test_repository_rejects_malformed_json(
    tmp_path,
) -> None:
    """Malformed persisted state should raise a repository error."""

    file_path = tmp_path / "scheduler_job_states.json"
    file_path.write_text(
        "{not-valid-json",
        encoding="utf-8",
    )
    repository = JSONReconciliationSLAJobStateRepository(
        file_path=file_path,
    )

    with pytest.raises(
        ReconciliationSLAJobStateRepositoryError,
        match="job state file is invalid",
    ):
        repository.load_job_statuses()
def test_repository_replaces_job_state_file_atomically(
    tmp_path,
    monkeypatch,
) -> None:
    """Saving states should replace the target from a temporary file."""

    file_path = tmp_path / "scheduler_job_states.json"
    repository = JSONReconciliationSLAJobStateRepository(
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
    status = ReconciliationSLAJobStatus(
        job_id="portfolio-901-sla",
        interval=timedelta(minutes=15),
        next_run_at=NEXT_RUN_AT,
    )

    repository.save_job_statuses((status,))

    assert len(replacements) == 1
    temporary_path, replacement_target = replacements[0]
    assert temporary_path != file_path
    assert replacement_target == file_path
    assert not temporary_path.exists()
def test_repository_rejects_invalid_job_state_structure(
    tmp_path,
) -> None:
    """Structurally invalid state should raise a repository error."""

    file_path = tmp_path / "scheduler_job_states.json"
    file_path.write_text(
        '[{"job_id": "portfolio-901-sla"}]',
        encoding="utf-8",
    )
    repository = JSONReconciliationSLAJobStateRepository(
        file_path=file_path,
    )

    with pytest.raises(
        ReconciliationSLAJobStateRepositoryError,
        match="job state file is invalid",
    ):
        repository.load_job_statuses()
def test_repository_rejects_non_positive_interval(
    tmp_path,
) -> None:
    """Persisted job states must contain a positive interval."""

    file_path = tmp_path / "scheduler_job_states.json"
    file_path.write_text(
        (
            "["
            "{"
            '"job_id": "portfolio-901-sla",'
            '"interval_seconds": 0,'
            f'"next_run_at": "{NEXT_RUN_AT.isoformat()}",'
            '"is_paused": false'
            "}"
            "]"
        ),
        encoding="utf-8",
    )
    repository = JSONReconciliationSLAJobStateRepository(
        file_path=file_path,
    )

    with pytest.raises(
        ReconciliationSLAJobStateRepositoryError,
        match="job state file is invalid",
    ):
        repository.load_job_statuses()
def test_repository_rejects_duplicate_job_ids(
    tmp_path,
) -> None:
    """Persisted job IDs must be unique."""

    file_path = tmp_path / "scheduler_job_states.json"
    state = (
        "{"
        '"job_id": "portfolio-901-sla",'
        '"interval_seconds": 900,'
        f'"next_run_at": "{NEXT_RUN_AT.isoformat()}",'
        '"is_paused": false'
        "}"
    )
    file_path.write_text(
        f"[{state},{state}]",
        encoding="utf-8",
    )
    repository = JSONReconciliationSLAJobStateRepository(
        file_path=file_path,
    )

    with pytest.raises(
        ReconciliationSLAJobStateRepositoryError,
        match="job state file is invalid",
    ):
        repository.load_job_statuses()