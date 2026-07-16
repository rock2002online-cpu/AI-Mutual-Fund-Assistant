"""
Tests for PortfolioHistoryService.

These tests verify:

- Canonical output-column behavior
- Master source-schema support
- Custom source-column support
- Date and value normalization
- Invalid-row removal
- Duplicate-date handling
- Chronological sorting
- Missing-file behavior
- CSV loading
- Availability metadata
- Convenience API behavior

Default master source schema:

    Date
    Investment
    Current Value
    Profit
    Return %

Canonical analytics output schema:

    Date
    Value
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from services.history.portfolio_history_service import (
    DEFAULT_DATE_COLUMN,
    DEFAULT_SOURCE_DATE_COLUMN,
    DEFAULT_SOURCE_VALUE_COLUMN,
    DEFAULT_VALUE_COLUMN,
    PortfolioHistoryFileNotFoundError,
    PortfolioHistoryResult,
    PortfolioHistoryService,
    PortfolioHistoryValidationError,
    load_portfolio_history,
    normalize_portfolio_history,
)


# ============================================================
# Test Data Helpers
# ============================================================


def _build_canonical_history() -> pd.DataFrame:
    """
    Return history using the canonical analytics schema.
    """

    return pd.DataFrame(
        {
            "Date": [
                "2025-01-01",
                "2025-02-01",
                "2025-03-01",
            ],
            "Value": [
                100000.0,
                105000.0,
                110000.0,
            ],
        }
    )


def _build_master_history() -> pd.DataFrame:
    """
    Return history using the default master source schema.
    """

    return pd.DataFrame(
        {
            "Date": [
                "2025-01-01",
                "2025-02-01",
                "2025-03-01",
            ],
            "Investment": [
                90000.0,
                92000.0,
                94000.0,
            ],
            "Current Value": [
                100000.0,
                105000.0,
                110000.0,
            ],
            "Profit": [
                10000.0,
                13000.0,
                16000.0,
            ],
            "Return %": [
                11.11,
                14.13,
                17.02,
            ],
        }
    )


def _write_history_csv(
    path: Path,
    dataframe: pd.DataFrame,
) -> Path:
    """
    Write a test history dataframe to CSV.
    """

    dataframe.to_csv(
        path,
        index=False,
    )

    return path


# ============================================================
# Constant Tests
# ============================================================


def test_default_source_columns_match_master_schema() -> None:
    """
    Default source columns should match the master history CSV.
    """

    assert DEFAULT_SOURCE_DATE_COLUMN == "Date"
    assert DEFAULT_SOURCE_VALUE_COLUMN == "Current Value"


def test_canonical_output_columns_remain_stable() -> None:
    """
    Analytics output columns should remain Date and Value.
    """

    assert DEFAULT_DATE_COLUMN == "Date"
    assert DEFAULT_VALUE_COLUMN == "Value"


# ============================================================
# normalize_portfolio_history Tests
# ============================================================


def test_normalize_portfolio_history_returns_expected_columns() -> None:
    """
    Normalized history should expose canonical Date and Value columns.
    """

    result = normalize_portfolio_history(
        _build_canonical_history()
    )

    assert list(result.columns) == [
        DEFAULT_DATE_COLUMN,
        DEFAULT_VALUE_COLUMN,
    ]


def test_normalize_portfolio_history_converts_dates() -> None:
    """
    Date values should be converted to pandas datetime values.
    """

    result = normalize_portfolio_history(
        _build_canonical_history()
    )

    assert pd.api.types.is_datetime64_any_dtype(
        result[DEFAULT_DATE_COLUMN]
    )


def test_normalize_portfolio_history_converts_values_to_float() -> None:
    """
    Portfolio values should be normalized as floating-point values.
    """

    history = pd.DataFrame(
        {
            "Date": [
                "2025-01-01",
                "2025-02-01",
            ],
            "Value": [
                "100000",
                "105000.50",
            ],
        }
    )

    result = normalize_portfolio_history(
        history
    )

    assert pd.api.types.is_float_dtype(
        result[DEFAULT_VALUE_COLUMN]
    )

    assert result[DEFAULT_VALUE_COLUMN].tolist() == [
        100000.0,
        105000.5,
    ]


def test_normalize_portfolio_history_supports_master_schema() -> None:
    """
    The master Current Value source column should normalize to Value.
    """

    result = normalize_portfolio_history(
        _build_master_history(),
        date_column="Date",
        value_column="Current Value",
    )

    assert list(result.columns) == [
        DEFAULT_DATE_COLUMN,
        DEFAULT_VALUE_COLUMN,
    ]

    assert result[DEFAULT_VALUE_COLUMN].tolist() == [
        100000.0,
        105000.0,
        110000.0,
    ]


def test_normalize_portfolio_history_ignores_extra_columns() -> None:
    """
    Master columns not required for analytics should be ignored.
    """

    result = normalize_portfolio_history(
        _build_master_history(),
        date_column="Date",
        value_column="Current Value",
    )

    assert "Investment" not in result.columns
    assert "Profit" not in result.columns
    assert "Return %" not in result.columns


def test_normalize_portfolio_history_sorts_chronologically() -> None:
    """
    History should be sorted from earliest to latest.
    """

    history = pd.DataFrame(
        {
            "Date": [
                "2025-03-01",
                "2025-01-01",
                "2025-02-01",
            ],
            "Value": [
                110000.0,
                100000.0,
                105000.0,
            ],
        }
    )

    result = normalize_portfolio_history(
        history
    )

    assert result[DEFAULT_DATE_COLUMN].tolist() == [
        pd.Timestamp("2025-01-01"),
        pd.Timestamp("2025-02-01"),
        pd.Timestamp("2025-03-01"),
    ]


def test_normalize_portfolio_history_removes_invalid_dates() -> None:
    """
    Rows with invalid dates should be removed.
    """

    history = pd.DataFrame(
        {
            "Date": [
                "2025-01-01",
                "invalid-date",
                "2025-03-01",
            ],
            "Value": [
                100000.0,
                105000.0,
                110000.0,
            ],
        }
    )

    result = normalize_portfolio_history(
        history
    )

    assert len(result) == 2

    assert result[DEFAULT_DATE_COLUMN].tolist() == [
        pd.Timestamp("2025-01-01"),
        pd.Timestamp("2025-03-01"),
    ]


def test_normalize_portfolio_history_removes_invalid_values() -> None:
    """
    Rows with non-numeric portfolio values should be removed.
    """

    history = pd.DataFrame(
        {
            "Date": [
                "2025-01-01",
                "2025-02-01",
                "2025-03-01",
            ],
            "Value": [
                100000.0,
                "invalid-value",
                110000.0,
            ],
        }
    )

    result = normalize_portfolio_history(
        history
    )

    assert len(result) == 2

    assert result[DEFAULT_VALUE_COLUMN].tolist() == [
        100000.0,
        110000.0,
    ]


def test_normalize_portfolio_history_removes_zero_values() -> None:
    """
    Zero portfolio values should be removed.
    """

    history = pd.DataFrame(
        {
            "Date": [
                "2025-01-01",
                "2025-02-01",
            ],
            "Value": [
                100000.0,
                0.0,
            ],
        }
    )

    result = normalize_portfolio_history(
        history
    )

    assert len(result) == 1
    assert result.iloc[0][DEFAULT_VALUE_COLUMN] == 100000.0


def test_normalize_portfolio_history_removes_negative_values() -> None:
    """
    Negative portfolio values should be removed.
    """

    history = pd.DataFrame(
        {
            "Date": [
                "2025-01-01",
                "2025-02-01",
            ],
            "Value": [
                100000.0,
                -5000.0,
            ],
        }
    )

    result = normalize_portfolio_history(
        history
    )

    assert len(result) == 1
    assert result.iloc[0][DEFAULT_VALUE_COLUMN] == 100000.0


def test_normalize_portfolio_history_keeps_last_duplicate_date() -> None:
    """
    The final observation should be retained for duplicate timestamps.
    """

    history = pd.DataFrame(
        {
            "Date": [
                "2025-01-01",
                "2025-01-01",
                "2025-02-01",
            ],
            "Value": [
                100000.0,
                101000.0,
                105000.0,
            ],
        }
    )

    result = normalize_portfolio_history(
        history
    )

    assert len(result) == 2
    assert result.iloc[0][DEFAULT_VALUE_COLUMN] == 101000.0


def test_normalize_portfolio_history_accepts_custom_columns() -> None:
    """
    Alternate source-column names should be supported.
    """

    history = pd.DataFrame(
        {
            "Valuation Date": [
                "2025-01-01",
                "2025-02-01",
            ],
            "Portfolio Value": [
                100000.0,
                105000.0,
            ],
        }
    )

    result = normalize_portfolio_history(
        history,
        date_column="Valuation Date",
        value_column="Portfolio Value",
    )

    assert list(result.columns) == [
        DEFAULT_DATE_COLUMN,
        DEFAULT_VALUE_COLUMN,
    ]

    assert result[DEFAULT_VALUE_COLUMN].tolist() == [
        100000.0,
        105000.0,
    ]


def test_normalize_portfolio_history_rejects_non_dataframe() -> None:
    """
    Non-dataframe inputs should be rejected.
    """

    with pytest.raises(
        TypeError,
        match="history must be a pandas DataFrame",
    ):
        normalize_portfolio_history(
            [
                {
                    "Date": "2025-01-01",
                    "Value": 100000.0,
                }
            ]
        )


def test_normalize_portfolio_history_rejects_missing_date_column() -> None:
    """
    Missing date columns should raise a validation error.
    """

    history = pd.DataFrame(
        {
            "Value": [
                100000.0,
            ]
        }
    )

    with pytest.raises(
        PortfolioHistoryValidationError,
        match="Date",
    ):
        normalize_portfolio_history(
            history
        )


def test_normalize_portfolio_history_rejects_missing_value_column() -> None:
    """
    Missing value columns should raise a validation error.
    """

    history = pd.DataFrame(
        {
            "Date": [
                "2025-01-01",
            ]
        }
    )

    with pytest.raises(
        PortfolioHistoryValidationError,
        match="Value",
    ):
        normalize_portfolio_history(
            history
        )


def test_normalize_portfolio_history_rejects_blank_date_column() -> None:
    """
    Blank date-column names should be rejected.
    """

    with pytest.raises(
        ValueError,
        match="date_column cannot be empty",
    ):
        normalize_portfolio_history(
            _build_canonical_history(),
            date_column=" ",
        )


def test_normalize_portfolio_history_rejects_blank_value_column() -> None:
    """
    Blank value-column names should be rejected.
    """

    with pytest.raises(
        ValueError,
        match="value_column cannot be empty",
    ):
        normalize_portfolio_history(
            _build_canonical_history(),
            value_column=" ",
        )


# ============================================================
# PortfolioHistoryService Construction Tests
# ============================================================


def test_service_uses_master_source_columns_by_default() -> None:
    """
    Service defaults should target Date and Current Value.
    """

    service = PortfolioHistoryService()

    assert service.date_column == "Date"
    assert service.value_column == "Current Value"


def test_service_resolves_explicit_source_path(
    tmp_path: Path,
) -> None:
    """
    Explicit source paths should be resolved correctly.
    """

    source_path = tmp_path / "history.csv"

    service = PortfolioHistoryService(
        source_path=source_path
    )

    assert service.source_path == source_path.resolve()


def test_service_resolves_relative_path_against_project_root(
    tmp_path: Path,
) -> None:
    """
    Relative paths should resolve from the configured project root.
    """

    service = PortfolioHistoryService(
        source_path="custom/history.csv",
        project_root=tmp_path,
    )

    assert service.source_path == (
        tmp_path / "custom" / "history.csv"
    ).resolve()


def test_service_supports_explicit_legacy_value_column(
    tmp_path: Path,
) -> None:
    """
    A legacy Date and Value source should remain configurable.
    """

    source_path = _write_history_csv(
        tmp_path / "history.csv",
        _build_canonical_history(),
    )

    service = PortfolioHistoryService(
        source_path=source_path,
        value_column="Value",
    )

    result = service.load_history()

    assert len(result) == 3
    assert list(result.columns) == [
        DEFAULT_DATE_COLUMN,
        DEFAULT_VALUE_COLUMN,
    ]


def test_service_rejects_invalid_minimum_observations() -> None:
    """
    Minimum observations must be a positive integer.
    """

    with pytest.raises(
        ValueError,
        match="minimum_observations must be greater than zero",
    ):
        PortfolioHistoryService(
            minimum_observations=0
        )


def test_service_rejects_boolean_minimum_observations() -> None:
    """
    Boolean values should not be accepted as integers.
    """

    with pytest.raises(
        TypeError,
        match="minimum_observations must be an integer",
    ):
        PortfolioHistoryService(
            minimum_observations=True
        )


# ============================================================
# File Existence and Loading Tests
# ============================================================


def test_exists_returns_false_for_missing_file(
    tmp_path: Path,
) -> None:
    """
    exists() should return False when the file is absent.
    """

    service = PortfolioHistoryService(
        source_path=tmp_path / "missing.csv"
    )

    assert service.exists() is False


def test_exists_returns_true_for_existing_file(
    tmp_path: Path,
) -> None:
    """
    exists() should return True for an existing CSV file.
    """

    source_path = _write_history_csv(
        tmp_path / "history.csv",
        _build_master_history(),
    )

    service = PortfolioHistoryService(
        source_path=source_path
    )

    assert service.exists() is True


def test_load_history_reads_master_schema_and_normalizes_csv(
    tmp_path: Path,
) -> None:
    """
    load_history() should normalize Current Value into Value.
    """

    source_path = _write_history_csv(
        tmp_path / "history.csv",
        _build_master_history(),
    )

    service = PortfolioHistoryService(
        source_path=source_path
    )

    result = service.load_history()

    assert len(result) == 3

    assert list(result.columns) == [
        DEFAULT_DATE_COLUMN,
        DEFAULT_VALUE_COLUMN,
    ]

    assert pd.api.types.is_datetime64_any_dtype(
        result[DEFAULT_DATE_COLUMN]
    )

    assert pd.api.types.is_float_dtype(
        result[DEFAULT_VALUE_COLUMN]
    )

    assert result[DEFAULT_VALUE_COLUMN].tolist() == [
        100000.0,
        105000.0,
        110000.0,
    ]


def test_load_history_raises_when_file_missing(
    tmp_path: Path,
) -> None:
    """
    load_history() should raise for a missing source file.
    """

    service = PortfolioHistoryService(
        source_path=tmp_path / "missing.csv"
    )

    with pytest.raises(
        PortfolioHistoryFileNotFoundError,
        match="Portfolio history file was not found",
    ):
        service.load_history()


def test_load_history_raises_when_current_value_missing(
    tmp_path: Path,
) -> None:
    """
    Default service loading requires the Current Value source column.
    """

    source_path = _write_history_csv(
        tmp_path / "legacy.csv",
        _build_canonical_history(),
    )

    service = PortfolioHistoryService(
        source_path=source_path
    )

    with pytest.raises(
        PortfolioHistoryValidationError,
        match="Current Value",
    ):
        service.load_history()


def test_load_history_raises_for_invalid_schema(
    tmp_path: Path,
) -> None:
    """
    Invalid CSV schemas should raise validation errors.
    """

    invalid_history = pd.DataFrame(
        {
            "Unexpected": [
                1,
                2,
            ]
        }
    )

    source_path = _write_history_csv(
        tmp_path / "invalid.csv",
        invalid_history,
    )

    service = PortfolioHistoryService(
        source_path=source_path
    )

    with pytest.raises(
        PortfolioHistoryValidationError,
        match="missing required column",
    ):
        service.load_history()


# ============================================================
# get_history Tests
# ============================================================


def test_get_history_returns_empty_dataframe_when_missing_allowed(
    tmp_path: Path,
) -> None:
    """
    Missing files should produce an empty canonical dataframe when allowed.
    """

    service = PortfolioHistoryService(
        source_path=tmp_path / "missing.csv"
    )

    result = service.get_history(
        allow_missing=True
    )

    assert result.empty

    assert list(result.columns) == [
        DEFAULT_DATE_COLUMN,
        DEFAULT_VALUE_COLUMN,
    ]

    assert pd.api.types.is_datetime64_any_dtype(
        result[DEFAULT_DATE_COLUMN]
    )

    assert pd.api.types.is_float_dtype(
        result[DEFAULT_VALUE_COLUMN]
    )


def test_get_history_raises_when_missing_not_allowed(
    tmp_path: Path,
) -> None:
    """
    Missing files should raise when allow_missing is False.
    """

    service = PortfolioHistoryService(
        source_path=tmp_path / "missing.csv"
    )

    with pytest.raises(
        PortfolioHistoryFileNotFoundError,
    ):
        service.get_history(
            allow_missing=False
        )


def test_get_history_rejects_non_boolean_allow_missing(
    tmp_path: Path,
) -> None:
    """
    allow_missing must be a strict boolean.
    """

    service = PortfolioHistoryService(
        source_path=tmp_path / "missing.csv"
    )

    with pytest.raises(
        TypeError,
        match="allow_missing must be a boolean",
    ):
        service.get_history(
            allow_missing=1
        )


# ============================================================
# Result Metadata Tests
# ============================================================


def test_get_result_returns_result_model(
    tmp_path: Path,
) -> None:
    """
    get_result() should return PortfolioHistoryResult.
    """

    source_path = _write_history_csv(
        tmp_path / "history.csv",
        _build_master_history(),
    )

    service = PortfolioHistoryService(
        source_path=source_path
    )

    result = service.get_result()

    assert isinstance(
        result,
        PortfolioHistoryResult,
    )


def test_get_result_returns_summary_metadata(
    tmp_path: Path,
) -> None:
    """
    Result metadata should describe normalized master history.
    """

    source_path = _write_history_csv(
        tmp_path / "history.csv",
        _build_master_history(),
    )

    service = PortfolioHistoryService(
        source_path=source_path
    )

    result = service.get_result()

    assert result.observation_count == 3

    assert result.first_date == pd.Timestamp(
        "2025-01-01"
    )

    assert result.last_date == pd.Timestamp(
        "2025-03-01"
    )

    assert result.first_value == 100000.0
    assert result.last_value == 110000.0
    assert result.available is True


def test_get_result_marks_insufficient_history_unavailable(
    tmp_path: Path,
) -> None:
    """
    Results below the minimum threshold should be unavailable.
    """

    history = pd.DataFrame(
        {
            "Date": [
                "2025-01-01",
            ],
            "Investment": [
                90000.0,
            ],
            "Current Value": [
                100000.0,
            ],
            "Profit": [
                10000.0,
            ],
            "Return %": [
                11.11,
            ],
        }
    )

    source_path = _write_history_csv(
        tmp_path / "history.csv",
        history,
    )

    service = PortfolioHistoryService(
        source_path=source_path,
        minimum_observations=2,
    )

    result = service.get_result()

    assert result.observation_count == 1
    assert result.available is False


def test_get_result_returns_empty_metadata_for_missing_file(
    tmp_path: Path,
) -> None:
    """
    Missing optional history should produce empty metadata.
    """

    service = PortfolioHistoryService(
        source_path=tmp_path / "missing.csv"
    )

    result = service.get_result(
        allow_missing=True
    )

    assert result.history.empty
    assert result.observation_count == 0
    assert result.first_date is None
    assert result.last_date is None
    assert result.first_value is None
    assert result.last_value is None
    assert result.available is False


def test_has_history_returns_true_for_sufficient_history(
    tmp_path: Path,
) -> None:
    """
    has_history() should return True when enough records exist.
    """

    source_path = _write_history_csv(
        tmp_path / "history.csv",
        _build_master_history(),
    )

    service = PortfolioHistoryService(
        source_path=source_path
    )

    assert service.has_history() is True


def test_has_history_returns_false_for_missing_history(
    tmp_path: Path,
) -> None:
    """
    has_history() should return False when the file is missing.
    """

    service = PortfolioHistoryService(
        source_path=tmp_path / "missing.csv"
    )

    assert service.has_history() is False


# ============================================================
# Convenience API Tests
# ============================================================


def test_load_portfolio_history_convenience_function(
    tmp_path: Path,
) -> None:
    """
    The convenience function should use the master schema by default.
    """

    source_path = _write_history_csv(
        tmp_path / "history.csv",
        _build_master_history(),
    )

    result = load_portfolio_history(
        source_path=source_path
    )

    assert len(result) == 3

    assert list(result.columns) == [
        DEFAULT_DATE_COLUMN,
        DEFAULT_VALUE_COLUMN,
    ]

    assert result[DEFAULT_VALUE_COLUMN].tolist() == [
        100000.0,
        105000.0,
        110000.0,
    ]


def test_load_portfolio_history_supports_legacy_source_column(
    tmp_path: Path,
) -> None:
    """
    The convenience API should support an explicit Value source.
    """

    source_path = _write_history_csv(
        tmp_path / "history.csv",
        _build_canonical_history(),
    )

    result = load_portfolio_history(
        source_path=source_path,
        value_column="Value",
    )

    assert len(result) == 3

    assert result[DEFAULT_VALUE_COLUMN].tolist() == [
        100000.0,
        105000.0,
        110000.0,
    ]


def test_load_portfolio_history_allows_missing_file(
    tmp_path: Path,
) -> None:
    """
    The convenience function should support optional missing history.
    """

    result = load_portfolio_history(
        source_path=tmp_path / "missing.csv",
        allow_missing=True,
    )

    assert result.empty


def test_load_portfolio_history_raises_when_missing_disallowed(
    tmp_path: Path,
) -> None:
    """
    The convenience function should raise when missing data is disallowed.
    """

    with pytest.raises(
        PortfolioHistoryFileNotFoundError,
    ):
        load_portfolio_history(
            source_path=tmp_path / "missing.csv",
            allow_missing=False,
        )