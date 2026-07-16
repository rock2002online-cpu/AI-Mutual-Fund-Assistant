"""
Tests for scripts.update_portfolio_history.

These tests verify:

- Portfolio snapshot calculation
- Master history normalization
- Same-day snapshot replacement
- Historical record preservation
- CSV loading and saving
- End-to-end update behavior
- Validation and failure handling
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from scripts.update_portfolio_history import (
    CURRENT_VALUE_COLUMN,
    DATE_COLUMN,
    HISTORY_COLUMNS,
    INVESTMENT_COLUMN,
    PROFIT_COLUMN,
    RETURN_PERCENT_COLUMN,
    PortfolioHistoryReadError,
    PortfolioSnapshot,
    PortfolioSnapshotValidationError,
    build_portfolio_snapshot,
    create_empty_history,
    load_existing_history,
    merge_snapshot_into_history,
    normalize_master_history,
    save_portfolio_history,
    update_portfolio_history,
)


# ============================================================
# Test Doubles
# ============================================================


class FakePortfolioService:
    """
    Simple PortfolioService-compatible test double.
    """

    def __init__(
        self,
        portfolio: pd.DataFrame,
    ) -> None:
        self._portfolio = portfolio
        self.call_count = 0

    def get_portfolio(self) -> pd.DataFrame:
        """
        Return the configured portfolio.
        """

        self.call_count += 1

        return self._portfolio


# ============================================================
# Test Data
# ============================================================


def _build_portfolio() -> pd.DataFrame:
    """
    Return a valid two-holding portfolio.
    """

    return pd.DataFrame(
        {
            "Fund": [
                "Fund A",
                "Fund B",
            ],
            "Investment": [
                10000.0,
                5000.0,
            ],
            "Current Value": [
                12500.0,
                5500.0,
            ],
        }
    )


def _build_history() -> pd.DataFrame:
    """
    Return valid master history.
    """

    return pd.DataFrame(
        {
            "Date": [
                "2026-07-14",
                "2026-07-15",
            ],
            "Investment": [
                14000.0,
                14500.0,
            ],
            "Current Value": [
                16000.0,
                17000.0,
            ],
            "Profit": [
                2000.0,
                2500.0,
            ],
            "Return %": [
                14.29,
                17.24,
            ],
        }
    )


# ============================================================
# Empty History Tests
# ============================================================


def test_create_empty_history_returns_expected_columns() -> None:
    """
    Empty history should expose the stable master schema.
    """

    result = create_empty_history()

    assert result.empty

    assert tuple(result.columns) == HISTORY_COLUMNS


def test_create_empty_history_uses_expected_data_types() -> None:
    """
    Empty history should use predictable data types.
    """

    result = create_empty_history()

    assert pd.api.types.is_datetime64_any_dtype(
        result[DATE_COLUMN]
    )

    for column in (
        INVESTMENT_COLUMN,
        CURRENT_VALUE_COLUMN,
        PROFIT_COLUMN,
        RETURN_PERCENT_COLUMN,
    ):
        assert pd.api.types.is_float_dtype(
            result[column]
        )


# ============================================================
# Snapshot Calculation Tests
# ============================================================


def test_build_portfolio_snapshot_calculates_totals() -> None:
    """
    Snapshot totals should equal the sum of portfolio holdings.
    """

    snapshot = build_portfolio_snapshot(
        _build_portfolio(),
        snapshot_date=date(2026, 7, 16),
    )

    assert snapshot.investment == 15000.0
    assert snapshot.current_value == 18000.0
    assert snapshot.profit == 3000.0
    assert snapshot.return_percent == 20.0


def test_build_portfolio_snapshot_uses_supplied_date() -> None:
    """
    The supplied date should be retained.
    """

    snapshot = build_portfolio_snapshot(
        _build_portfolio(),
        snapshot_date=date(2026, 7, 16),
    )

    assert snapshot.snapshot_date == date(
        2026,
        7,
        16,
    )


def test_build_portfolio_snapshot_returns_model() -> None:
    """
    Snapshot construction should return PortfolioSnapshot.
    """

    snapshot = build_portfolio_snapshot(
        _build_portfolio()
    )

    assert isinstance(
        snapshot,
        PortfolioSnapshot,
    )


def test_snapshot_to_record_uses_master_schema() -> None:
    """
    Snapshot records should match the master history schema.
    """

    snapshot = PortfolioSnapshot(
        snapshot_date=date(2026, 7, 16),
        investment=15000.0,
        current_value=18000.0,
        profit=3000.0,
        return_percent=20.0,
    )

    record = snapshot.to_record()

    assert tuple(record.keys()) == HISTORY_COLUMNS

    assert record[DATE_COLUMN] == "2026-07-16"
    assert record[INVESTMENT_COLUMN] == 15000.0
    assert record[CURRENT_VALUE_COLUMN] == 18000.0
    assert record[PROFIT_COLUMN] == 3000.0
    assert record[RETURN_PERCENT_COLUMN] == 20.0


def test_build_portfolio_snapshot_rejects_empty_portfolio() -> None:
    """
    Empty portfolios should not produce a snapshot.
    """

    with pytest.raises(
        PortfolioSnapshotValidationError,
        match="portfolio cannot be empty",
    ):
        build_portfolio_snapshot(
            pd.DataFrame()
        )


def test_build_portfolio_snapshot_rejects_missing_investment() -> None:
    """
    Investment is required.
    """

    portfolio = pd.DataFrame(
        {
            "Current Value": [
                10000.0,
            ]
        }
    )

    with pytest.raises(
        PortfolioSnapshotValidationError,
        match="Investment",
    ):
        build_portfolio_snapshot(
            portfolio
        )


def test_build_portfolio_snapshot_rejects_missing_current_value() -> None:
    """
    Current Value is required.
    """

    portfolio = pd.DataFrame(
        {
            "Investment": [
                10000.0,
            ]
        }
    )

    with pytest.raises(
        PortfolioSnapshotValidationError,
        match="Current Value",
    ):
        build_portfolio_snapshot(
            portfolio
        )


def test_build_portfolio_snapshot_rejects_invalid_numeric_values() -> None:
    """
    Invalid numeric data should be rejected.
    """

    portfolio = pd.DataFrame(
        {
            "Investment": [
                "invalid",
            ],
            "Current Value": [
                10000.0,
            ],
        }
    )

    with pytest.raises(
        PortfolioSnapshotValidationError,
        match="Investment contains invalid",
    ):
        build_portfolio_snapshot(
            portfolio
        )


def test_build_portfolio_snapshot_handles_zero_investment() -> None:
    """
    A zero-investment portfolio should return zero percentage return.
    """

    portfolio = pd.DataFrame(
        {
            "Investment": [
                0.0,
            ],
            "Current Value": [
                0.0,
            ],
        }
    )

    snapshot = build_portfolio_snapshot(
        portfolio,
        snapshot_date=date(2026, 7, 16),
    )

    assert snapshot.return_percent == 0.0


# ============================================================
# History Normalization Tests
# ============================================================


def test_normalize_master_history_returns_expected_columns() -> None:
    """
    Normalized history should retain the master schema.
    """

    result = normalize_master_history(
        _build_history()
    )

    assert tuple(result.columns) == HISTORY_COLUMNS


def test_normalize_master_history_converts_dates() -> None:
    """
    Date values should be converted to datetime values.
    """

    result = normalize_master_history(
        _build_history()
    )

    assert pd.api.types.is_datetime64_any_dtype(
        result[DATE_COLUMN]
    )


def test_normalize_master_history_sorts_dates() -> None:
    """
    History should be sorted chronologically.
    """

    history = _build_history().iloc[::-1]

    result = normalize_master_history(
        history
    )

    assert result[DATE_COLUMN].tolist() == [
        pd.Timestamp("2026-07-14"),
        pd.Timestamp("2026-07-15"),
    ]


def test_normalize_master_history_keeps_latest_same_day_record() -> None:
    """
    Multiple intraday snapshots should collapse to the latest record.
    """

    history = pd.DataFrame(
        {
            "Date": [
                "2026-07-16 09:00:00",
                "2026-07-16 18:00:00",
            ],
            "Investment": [
                15000.0,
                15000.0,
            ],
            "Current Value": [
                17500.0,
                18000.0,
            ],
            "Profit": [
                2500.0,
                3000.0,
            ],
            "Return %": [
                16.67,
                20.0,
            ],
        }
    )

    result = normalize_master_history(
        history
    )

    assert len(result) == 1
    assert result.iloc[0][CURRENT_VALUE_COLUMN] == 18000.0


def test_normalize_master_history_removes_invalid_rows() -> None:
    """
    Rows with invalid dates or numeric values should be removed.
    """

    history = pd.DataFrame(
        {
            "Date": [
                "2026-07-14",
                "invalid-date",
            ],
            "Investment": [
                14000.0,
                15000.0,
            ],
            "Current Value": [
                16000.0,
                "invalid",
            ],
            "Profit": [
                2000.0,
                0.0,
            ],
            "Return %": [
                14.29,
                0.0,
            ],
        }
    )

    result = normalize_master_history(
        history
    )

    assert len(result) == 1
    assert result.iloc[0][DATE_COLUMN] == pd.Timestamp(
        "2026-07-14"
    )


# ============================================================
# Merge Tests
# ============================================================


def test_merge_snapshot_appends_new_date() -> None:
    """
    A snapshot for a new date should be appended.
    """

    snapshot = PortfolioSnapshot(
        snapshot_date=date(2026, 7, 16),
        investment=15000.0,
        current_value=18000.0,
        profit=3000.0,
        return_percent=20.0,
    )

    result = merge_snapshot_into_history(
        _build_history(),
        snapshot,
    )

    assert len(result) == 3

    assert result.iloc[-1][DATE_COLUMN] == pd.Timestamp(
        "2026-07-16"
    )


def test_merge_snapshot_replaces_same_date() -> None:
    """
    A newer same-day snapshot should replace the previous row.
    """

    snapshot = PortfolioSnapshot(
        snapshot_date=date(2026, 7, 15),
        investment=15000.0,
        current_value=19000.0,
        profit=4000.0,
        return_percent=26.67,
    )

    result = merge_snapshot_into_history(
        _build_history(),
        snapshot,
    )

    assert len(result) == 2

    latest = result[
        result[DATE_COLUMN]
        == pd.Timestamp("2026-07-15")
    ].iloc[0]

    assert latest[CURRENT_VALUE_COLUMN] == 19000.0
    assert latest[PROFIT_COLUMN] == 4000.0
    assert latest[RETURN_PERCENT_COLUMN] == 26.67


def test_merge_snapshot_rejects_invalid_snapshot() -> None:
    """
    Snapshot must use PortfolioSnapshot.
    """

    with pytest.raises(
        TypeError,
        match="snapshot must be a PortfolioSnapshot",
    ):
        merge_snapshot_into_history(
            _build_history(),
            object(),
        )


# ============================================================
# File Loading and Saving Tests
# ============================================================


def test_load_existing_history_returns_empty_when_missing(
    tmp_path: Path,
) -> None:
    """
    Missing history files should return an empty dataframe.
    """

    result = load_existing_history(
        tmp_path / "missing.csv"
    )

    assert result.empty
    assert tuple(result.columns) == HISTORY_COLUMNS


def test_load_existing_history_reads_csv(
    tmp_path: Path,
) -> None:
    """
    Existing CSV history should be loaded and normalized.
    """

    history_path = tmp_path / "history.csv"

    _build_history().to_csv(
        history_path,
        index=False,
    )

    result = load_existing_history(
        history_path
    )

    assert len(result) == 2

    assert result.iloc[0][DATE_COLUMN] == pd.Timestamp(
        "2026-07-14"
    )


def test_load_existing_history_rejects_directory_path(
    tmp_path: Path,
) -> None:
    """
    A directory cannot be used as the history file.
    """

    with pytest.raises(
        PortfolioHistoryReadError,
        match="history path is not a file",
    ):
        load_existing_history(
            tmp_path
        )


def test_save_portfolio_history_creates_csv(
    tmp_path: Path,
) -> None:
    """
    Saving should create the CSV file.
    """

    history_path = tmp_path / "nested" / "history.csv"

    result_path = save_portfolio_history(
        _build_history(),
        history_path,
    )

    assert result_path == history_path.resolve()
    assert history_path.exists()


def test_save_portfolio_history_writes_expected_schema(
    tmp_path: Path,
) -> None:
    """
    Saved CSV should preserve the master column order.
    """

    history_path = tmp_path / "history.csv"

    save_portfolio_history(
        _build_history(),
        history_path,
    )

    saved = pd.read_csv(
        history_path
    )

    assert tuple(saved.columns) == HISTORY_COLUMNS


# ============================================================
# End-to-End Update Tests
# ============================================================


def test_update_portfolio_history_creates_first_snapshot(
    tmp_path: Path,
) -> None:
    """
    End-to-end update should create the first history record.
    """

    service = FakePortfolioService(
        _build_portfolio()
    )

    history_path = tmp_path / "history.csv"

    snapshot = update_portfolio_history(
        portfolio_service=service,
        history_path=history_path,
        snapshot_date=date(2026, 7, 16),
    )

    assert service.call_count == 1
    assert snapshot.current_value == 18000.0
    assert history_path.exists()

    saved = pd.read_csv(
        history_path
    )

    assert len(saved) == 1
    assert saved.iloc[0][DATE_COLUMN] == "2026-07-16"


def test_update_portfolio_history_replaces_same_day_snapshot(
    tmp_path: Path,
) -> None:
    """
    Running twice for the same date should keep one record.
    """

    history_path = tmp_path / "history.csv"

    first_service = FakePortfolioService(
        _build_portfolio()
    )

    update_portfolio_history(
        portfolio_service=first_service,
        history_path=history_path,
        snapshot_date=date(2026, 7, 16),
    )

    updated_portfolio = _build_portfolio()

    updated_portfolio.loc[
        0,
        "Current Value",
    ] = 13500.0

    second_service = FakePortfolioService(
        updated_portfolio
    )

    update_portfolio_history(
        portfolio_service=second_service,
        history_path=history_path,
        snapshot_date=date(2026, 7, 16),
    )

    saved = pd.read_csv(
        history_path
    )

    assert len(saved) == 1

    assert saved.iloc[0][CURRENT_VALUE_COLUMN] == 19000.0


def test_update_portfolio_history_preserves_previous_days(
    tmp_path: Path,
) -> None:
    """
    Updating a later date should preserve earlier snapshots.
    """

    history_path = tmp_path / "history.csv"

    _build_history().to_csv(
        history_path,
        index=False,
    )

    service = FakePortfolioService(
        _build_portfolio()
    )

    update_portfolio_history(
        portfolio_service=service,
        history_path=history_path,
        snapshot_date=date(2026, 7, 16),
    )

    saved = pd.read_csv(
        history_path
    )

    assert len(saved) == 3

    assert saved[DATE_COLUMN].tolist() == [
        "2026-07-14",
        "2026-07-15",
        "2026-07-16",
    ]