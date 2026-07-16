"""
Portfolio valuation history service.

This module provides validated historical portfolio valuation data for
advanced analytics.

Responsibilities:

- Resolve the portfolio-history data source
- Load historical valuation records
- Validate required source columns
- Normalize dates and portfolio values
- Remove invalid and duplicate observations
- Return records in chronological order
- Report whether sufficient history is available

The master history source may contain columns such as:

- Date
- Investment
- Current Value
- Profit
- Return %

Only Date and Current Value are required by this service.

The normalized output supplied to the analytics layer always uses:

- Date
- Value

Financial calculations remain in services.analytics modules.

Current portfolio retrieval remains the responsibility of PortfolioService.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pandas as pd


# ============================================================
# Constants
# ============================================================

DEFAULT_HISTORY_RELATIVE_PATH: Final[Path] = (
    Path("data") / "portfolio_history.csv"
)

# Canonical analytics output columns.
DEFAULT_DATE_COLUMN: Final[str] = "Date"
DEFAULT_VALUE_COLUMN: Final[str] = "Value"

# Default source columns used by the master history CSV.
DEFAULT_SOURCE_DATE_COLUMN: Final[str] = "Date"
DEFAULT_SOURCE_VALUE_COLUMN: Final[str] = "Current Value"

MINIMUM_HISTORY_OBSERVATIONS: Final[int] = 2


# ============================================================
# Exceptions
# ============================================================


class PortfolioHistoryServiceError(RuntimeError):
    """
    Base exception raised by PortfolioHistoryService.
    """


class PortfolioHistoryFileNotFoundError(
    PortfolioHistoryServiceError
):
    """
    Raised when the configured portfolio-history file does not exist.
    """


class PortfolioHistoryValidationError(
    PortfolioHistoryServiceError
):
    """
    Raised when portfolio-history data fails validation.
    """


class PortfolioHistoryLoadError(
    PortfolioHistoryServiceError
):
    """
    Raised when portfolio-history data cannot be loaded.
    """


# ============================================================
# Result Model
# ============================================================


@dataclass(frozen=True, slots=True)
class PortfolioHistoryResult:
    """
    Result returned by PortfolioHistoryService.

    Attributes:
        history:
            Validated historical portfolio values using canonical Date and
            Value columns.

        source_path:
            File path used to load the history.

        observation_count:
            Number of valid valuation observations.

        first_date:
            Earliest valuation date.

        last_date:
            Latest valuation date.

        first_value:
            Portfolio value on the earliest date.

        last_value:
            Portfolio value on the latest date.

        available:
            Whether enough observations exist for basic historical analytics.
    """

    history: pd.DataFrame
    source_path: Path
    observation_count: int
    first_date: pd.Timestamp | None
    last_date: pd.Timestamp | None
    first_value: float | None
    last_value: float | None
    available: bool


# ============================================================
# Validation Helpers
# ============================================================


def _validate_column_name(
    value: object,
    field_name: str,
) -> str:
    """
    Validate and normalize a required column name.
    """

    if not isinstance(value, str):
        raise TypeError(
            f"{field_name} must be a string."
        )

    normalized_value = value.strip()

    if not normalized_value:
        raise ValueError(
            f"{field_name} cannot be empty."
        )

    return normalized_value


def _validate_minimum_observations(
    value: object,
) -> int:
    """
    Validate the minimum required observation count.
    """

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(
            "minimum_observations must be an integer."
        )

    if value <= 0:
        raise ValueError(
            "minimum_observations must be greater than zero."
        )

    return value


def _validate_source_dataframe(
    history: pd.DataFrame,
    *,
    date_column: str,
    value_column: str,
) -> None:
    """
    Validate the raw portfolio-history dataframe.
    """

    if not isinstance(history, pd.DataFrame):
        raise TypeError(
            "history must be a pandas DataFrame."
        )

    missing_columns = tuple(
        column
        for column in (
            date_column,
            value_column,
        )
        if column not in history.columns
    )

    if missing_columns:
        formatted_columns = ", ".join(
            missing_columns
        )

        raise PortfolioHistoryValidationError(
            "Portfolio history is missing required column(s): "
            f"{formatted_columns}."
        )


# ============================================================
# Empty DataFrame Factory
# ============================================================


def _create_empty_history_dataframe() -> pd.DataFrame:
    """
    Create an empty canonical portfolio-history dataframe.

    Returns:
        Empty dataframe with:

        - Date as datetime64[ns]
        - Value as float64
    """

    return pd.DataFrame(
        {
            DEFAULT_DATE_COLUMN: pd.Series(
                dtype="datetime64[ns]"
            ),
            DEFAULT_VALUE_COLUMN: pd.Series(
                dtype="float64"
            ),
        }
    )


# ============================================================
# Data Normalization
# ============================================================


def normalize_portfolio_history(
    history: pd.DataFrame,
    *,
    date_column: str = DEFAULT_DATE_COLUMN,
    value_column: str = DEFAULT_VALUE_COLUMN,
) -> pd.DataFrame:
    """
    Validate and normalize historical portfolio valuation data.

    This function accepts configurable source-column names while always
    returning the canonical analytics schema:

    - Date
    - Value

    Processing rules:

    - Retain only the configured date and value columns
    - Convert dates to pandas datetime values
    - Convert portfolio values to numeric values
    - Remove rows with invalid dates or values
    - Remove zero and negative portfolio values
    - Keep the final observation for duplicate timestamps
    - Sort observations chronologically
    - Rename output columns to Date and Value

    Args:
        history:
            Raw historical valuation dataframe.

        date_column:
            Source column containing valuation dates.

        value_column:
            Source column containing current portfolio values.

    Returns:
        Clean dataframe with canonical Date and Value columns.
    """

    normalized_date_column = _validate_column_name(
        date_column,
        "date_column",
    )

    normalized_value_column = _validate_column_name(
        value_column,
        "value_column",
    )

    _validate_source_dataframe(
        history,
        date_column=normalized_date_column,
        value_column=normalized_value_column,
    )

    normalized_history = history.loc[
        :,
        [
            normalized_date_column,
            normalized_value_column,
        ],
    ].copy()

    normalized_history = normalized_history.rename(
        columns={
            normalized_date_column: DEFAULT_DATE_COLUMN,
            normalized_value_column: DEFAULT_VALUE_COLUMN,
        }
    )

    normalized_history[DEFAULT_DATE_COLUMN] = (
        pd.to_datetime(
            normalized_history[DEFAULT_DATE_COLUMN],
            errors="coerce",
        )
    )

    normalized_history[DEFAULT_VALUE_COLUMN] = (
        pd.to_numeric(
            normalized_history[DEFAULT_VALUE_COLUMN],
            errors="coerce",
        )
    )

    normalized_history = normalized_history.dropna(
        subset=[
            DEFAULT_DATE_COLUMN,
            DEFAULT_VALUE_COLUMN,
        ]
    )

    normalized_history = normalized_history[
        normalized_history[DEFAULT_VALUE_COLUMN] > 0.0
    ]

        # Sort timestamps so the latest snapshot for each calendar day appears
    # last before daily duplicate removal.
    normalized_history = normalized_history.sort_values(
        by=DEFAULT_DATE_COLUMN,
        kind="stable",
    )

    # Advanced analytics operate on one portfolio valuation per calendar day.
    # Multiple intraday refresh snapshots are collapsed to the final snapshot
    # recorded for that date.
    normalized_history["_valuation_day"] = (
        normalized_history[DEFAULT_DATE_COLUMN].dt.normalize()
    )

    normalized_history = (
        normalized_history
        .drop_duplicates(
            subset=["_valuation_day"],
            keep="last",
        )
        .drop(columns=["_valuation_day"])
        .sort_values(
            by=DEFAULT_DATE_COLUMN,
            kind="stable",
        )
        .reset_index(drop=True)
    )

    # Expose calendar dates rather than intraday timestamps to the analytics
    # adapter so every observation has a unique valuation date.
    normalized_history[DEFAULT_DATE_COLUMN] = (
        normalized_history[DEFAULT_DATE_COLUMN].dt.normalize()
    )

    normalized_history[DEFAULT_VALUE_COLUMN] = (
        normalized_history[DEFAULT_VALUE_COLUMN]
        .astype(float)
    )

    return normalized_history


# ============================================================
# Portfolio History Service
# ============================================================


class PortfolioHistoryService:
    """
    Service for loading and validating portfolio valuation history.

    The default data source is:

        data/portfolio_history.csv

    The default master source schema is:

        Date
        Investment
        Current Value
        Profit
        Return %

    Only these source columns are required:

        Date
        Current Value

    The service normalizes them for the analytics layer as:

        Date
        Value

    A custom source path or alternate source-column names can be supplied for
    testing or different storage formats.
    """

    def __init__(
        self,
        source_path: str | Path | None = None,
        *,
        project_root: str | Path | None = None,
        date_column: str = DEFAULT_SOURCE_DATE_COLUMN,
        value_column: str = DEFAULT_SOURCE_VALUE_COLUMN,
        minimum_observations: int = (
            MINIMUM_HISTORY_OBSERVATIONS
        ),
    ) -> None:
        """
        Initialize the portfolio-history service.

        Args:
            source_path:
                Optional explicit CSV file path.

            project_root:
                Optional project root used when source_path is omitted.

                When omitted, the project root is inferred from this file.

            date_column:
                Source CSV date-column name.

                Default:
                    Date

            value_column:
                Source CSV portfolio-value column name.

                Default:
                    Current Value

            minimum_observations:
                Minimum number of valid records required for history to be
                marked available.
        """

        self._date_column = _validate_column_name(
            date_column,
            "date_column",
        )

        self._value_column = _validate_column_name(
            value_column,
            "value_column",
        )

        self._minimum_observations = (
            _validate_minimum_observations(
                minimum_observations
            )
        )

        resolved_project_root = (
            Path(project_root).expanduser().resolve()
            if project_root is not None
            else Path(__file__).resolve().parents[2]
        )

        if source_path is None:
            resolved_source_path = (
                resolved_project_root
                / DEFAULT_HISTORY_RELATIVE_PATH
            )
        else:
            candidate_path = Path(
                source_path
            ).expanduser()

            resolved_source_path = (
                candidate_path
                if candidate_path.is_absolute()
                else resolved_project_root / candidate_path
            )

        self._project_root = resolved_project_root

        self._source_path = (
            resolved_source_path.resolve()
        )

    @property
    def project_root(self) -> Path:
        """
        Return the resolved project root.
        """

        return self._project_root

    @property
    def source_path(self) -> Path:
        """
        Return the resolved portfolio-history file path.
        """

        return self._source_path

    @property
    def date_column(self) -> str:
        """
        Return the configured source date column.
        """

        return self._date_column

    @property
    def value_column(self) -> str:
        """
        Return the configured source portfolio-value column.
        """

        return self._value_column

    @property
    def minimum_observations(self) -> int:
        """
        Return the minimum observation requirement.
        """

        return self._minimum_observations

    def exists(self) -> bool:
        """
        Return whether the configured history file exists.
        """

        return (
            self._source_path.exists()
            and self._source_path.is_file()
        )

    def load_history(
        self,
    ) -> pd.DataFrame:
        """
        Load and normalize portfolio valuation history.

        Returns:
            Validated dataframe using canonical Date and Value columns.

        Raises:
            PortfolioHistoryFileNotFoundError:
                When the configured CSV file does not exist.

            PortfolioHistoryLoadError:
                When pandas cannot read the CSV file.

            PortfolioHistoryValidationError:
                When the loaded data fails schema validation.
        """

        if not self.exists():
            raise PortfolioHistoryFileNotFoundError(
                "Portfolio history file was not found: "
                f"{self._source_path}"
            )

        try:
            raw_history = pd.read_csv(
                self._source_path
            )

        except Exception as error:
            raise PortfolioHistoryLoadError(
                "Unable to load portfolio history from "
                f"{self._source_path}: {error}"
            ) from error

        try:
            return normalize_portfolio_history(
                raw_history,
                date_column=self._date_column,
                value_column=self._value_column,
            )

        except PortfolioHistoryValidationError:
            raise

        except Exception as error:
            raise PortfolioHistoryValidationError(
                "Portfolio history could not be normalized: "
                f"{error}"
            ) from error

    def get_history(
        self,
        *,
        allow_missing: bool = True,
    ) -> pd.DataFrame:
        """
        Return historical portfolio valuations.

        Args:
            allow_missing:
                When True, a missing source file returns an empty canonical
                dataframe.

                When False, a missing source file raises
                PortfolioHistoryFileNotFoundError.

        Returns:
            Normalized dataframe with Date and Value columns.
        """

        if not isinstance(allow_missing, bool):
            raise TypeError(
                "allow_missing must be a boolean."
            )

        try:
            return self.load_history()

        except PortfolioHistoryFileNotFoundError:
            if not allow_missing:
                raise

            return _create_empty_history_dataframe()

    def get_result(
        self,
        *,
        allow_missing: bool = True,
    ) -> PortfolioHistoryResult:
        """
        Return portfolio history and availability metadata.

        Args:
            allow_missing:
                Whether a missing history file should produce an empty result.

        Returns:
            PortfolioHistoryResult containing normalized history and summary
            metadata.
        """

        history = self.get_history(
            allow_missing=allow_missing
        )

        observation_count = len(history)

        if history.empty:
            first_date = None
            last_date = None
            first_value = None
            last_value = None

        else:
            first_row = history.iloc[0]
            last_row = history.iloc[-1]

            first_date = first_row[
                DEFAULT_DATE_COLUMN
            ]

            last_date = last_row[
                DEFAULT_DATE_COLUMN
            ]

            first_value = float(
                first_row[DEFAULT_VALUE_COLUMN]
            )

            last_value = float(
                last_row[DEFAULT_VALUE_COLUMN]
            )

        return PortfolioHistoryResult(
            history=history,
            source_path=self._source_path,
            observation_count=observation_count,
            first_date=first_date,
            last_date=last_date,
            first_value=first_value,
            last_value=last_value,
            available=(
                observation_count
                >= self._minimum_observations
            ),
        )

    def has_history(
        self,
    ) -> bool:
        """
        Return whether sufficient valid history is available.
        """

        return self.get_result(
            allow_missing=True
        ).available


# ============================================================
# Convenience API
# ============================================================


def load_portfolio_history(
    source_path: str | Path | None = None,
    *,
    project_root: str | Path | None = None,
    date_column: str = DEFAULT_SOURCE_DATE_COLUMN,
    value_column: str = DEFAULT_SOURCE_VALUE_COLUMN,
    allow_missing: bool = True,
) -> pd.DataFrame:
    """
    Load portfolio history through a convenience function.

    The default source schema uses Date and Current Value, while the returned
    dataframe always uses Date and Value.
    """

    service = PortfolioHistoryService(
        source_path=source_path,
        project_root=project_root,
        date_column=date_column,
        value_column=value_column,
    )

    return service.get_history(
        allow_missing=allow_missing
    )


# ============================================================
# Module Exports
# ============================================================


__all__ = [
    "DEFAULT_DATE_COLUMN",
    "DEFAULT_HISTORY_RELATIVE_PATH",
    "DEFAULT_SOURCE_DATE_COLUMN",
    "DEFAULT_SOURCE_VALUE_COLUMN",
    "DEFAULT_VALUE_COLUMN",
    "MINIMUM_HISTORY_OBSERVATIONS",
    "PortfolioHistoryFileNotFoundError",
    "PortfolioHistoryLoadError",
    "PortfolioHistoryResult",
    "PortfolioHistoryService",
    "PortfolioHistoryServiceError",
    "PortfolioHistoryValidationError",
    "load_portfolio_history",
    "normalize_portfolio_history",
]