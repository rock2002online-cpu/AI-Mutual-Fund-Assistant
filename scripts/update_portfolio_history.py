"""
Update the master portfolio valuation history.

This script:

- Retrieves the latest portfolio through PortfolioService
- Calculates total investment and current portfolio value
- Calculates total profit and portfolio return percentage
- Loads the existing portfolio history CSV when available
- Keeps one portfolio snapshot per calendar day
- Replaces the current day's earlier snapshot with the latest valuation
- Sorts history chronologically
- Saves the master history CSV

Output schema:

    Date
    Investment
    Current Value
    Profit
    Return %

PortfolioService remains the single source of current portfolio data.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite
from pathlib import Path
from typing import Final

import pandas as pd


# ============================================================
# Project Path Setup
# ============================================================

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from services.portfolio_service import PortfolioService


# ============================================================
# Constants
# ============================================================

DEFAULT_HISTORY_PATH: Final[Path] = (
    PROJECT_ROOT
    / "data"
    / "portfolio_history.csv"
)

DATE_COLUMN: Final[str] = "Date"
INVESTMENT_COLUMN: Final[str] = "Investment"
CURRENT_VALUE_COLUMN: Final[str] = "Current Value"
PROFIT_COLUMN: Final[str] = "Profit"
RETURN_PERCENT_COLUMN: Final[str] = "Return %"

HISTORY_COLUMNS: Final[tuple[str, ...]] = (
    DATE_COLUMN,
    INVESTMENT_COLUMN,
    CURRENT_VALUE_COLUMN,
    PROFIT_COLUMN,
    RETURN_PERCENT_COLUMN,
)


# ============================================================
# Exceptions
# ============================================================


class PortfolioHistoryUpdateError(RuntimeError):
    """
    Base exception raised during portfolio-history updates.
    """


class PortfolioSnapshotValidationError(
    PortfolioHistoryUpdateError
):
    """
    Raised when current portfolio data cannot produce a valid snapshot.
    """


class PortfolioHistoryReadError(
    PortfolioHistoryUpdateError
):
    """
    Raised when an existing history file cannot be read.
    """


class PortfolioHistoryWriteError(
    PortfolioHistoryUpdateError
):
    """
    Raised when the updated history cannot be saved.
    """


# ============================================================
# Snapshot Model
# ============================================================


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    """
    One portfolio valuation snapshot.

    Attributes:
        snapshot_date:
            Calendar date represented by the snapshot.

        investment:
            Total amount invested across all holdings.

        current_value:
            Total current value across all holdings.

        profit:
            Current value minus total investment.

        return_percent:
            Portfolio profit expressed as a percentage of investment.
    """

    snapshot_date: date
    investment: float
    current_value: float
    profit: float
    return_percent: float

    def to_record(self) -> dict[str, object]:
        """
        Convert the snapshot into the master history schema.
        """

        return {
            DATE_COLUMN: self.snapshot_date.isoformat(),
            INVESTMENT_COLUMN: self.investment,
            CURRENT_VALUE_COLUMN: self.current_value,
            PROFIT_COLUMN: self.profit,
            RETURN_PERCENT_COLUMN: self.return_percent,
        }


# ============================================================
# Validation Helpers
# ============================================================


def _validate_history_path(
    history_path: str | Path,
) -> Path:
    """
    Validate and resolve the history output path.
    """

    if not isinstance(
        history_path,
        (str, Path),
    ):
        raise TypeError(
            "history_path must be a string or pathlib.Path."
        )

    resolved_path = Path(
        history_path
    ).expanduser()

    if not resolved_path.is_absolute():
        resolved_path = PROJECT_ROOT / resolved_path

    return resolved_path.resolve()


def _validate_snapshot_date(
    snapshot_date: date | datetime | None,
) -> date:
    """
    Validate and normalize the snapshot date.
    """

    if snapshot_date is None:
        return date.today()

    if isinstance(snapshot_date, datetime):
        return snapshot_date.date()

    if isinstance(snapshot_date, date):
        return snapshot_date

    raise TypeError(
        "snapshot_date must be a date, datetime, or None."
    )


def _require_finite_number(
    value: object,
    *,
    field_name: str,
) -> float:
    """
    Convert a value to a finite float.
    """

    if isinstance(value, bool):
        raise PortfolioSnapshotValidationError(
            f"{field_name} must be numeric."
        )

    try:
        numeric_value = float(value)
    except (TypeError, ValueError) as error:
        raise PortfolioSnapshotValidationError(
            f"{field_name} must be numeric."
        ) from error

    if not isfinite(numeric_value):
        raise PortfolioSnapshotValidationError(
            f"{field_name} must be finite."
        )

    return numeric_value


# ============================================================
# Portfolio Loading
# ============================================================


def load_current_portfolio(
    portfolio_service: PortfolioService | None = None,
) -> pd.DataFrame:
    """
    Load the current portfolio through PortfolioService.

    Args:
        portfolio_service:
            Optional PortfolioService dependency.

    Returns:
        Non-empty portfolio dataframe.
    """

    service = (
        portfolio_service
        if portfolio_service is not None
        else PortfolioService()
    )

    get_portfolio = getattr(
        service,
        "get_portfolio",
        None,
    )

    if not callable(get_portfolio):
        raise TypeError(
            "portfolio_service must provide a callable "
            "get_portfolio() method."
        )

    try:
        portfolio = get_portfolio()
    except Exception as error:
        raise PortfolioHistoryUpdateError(
            "Unable to retrieve the current portfolio: "
            f"{error}"
        ) from error

    if not isinstance(portfolio, pd.DataFrame):
        raise PortfolioSnapshotValidationError(
            "PortfolioService must return a pandas DataFrame."
        )

    if portfolio.empty:
        raise PortfolioSnapshotValidationError(
            "The current portfolio is empty."
        )

    required_columns = (
        INVESTMENT_COLUMN,
        CURRENT_VALUE_COLUMN,
    )

    missing_columns = tuple(
        column
        for column in required_columns
        if column not in portfolio.columns
    )

    if missing_columns:
        formatted_columns = ", ".join(
            missing_columns
        )

        raise PortfolioSnapshotValidationError(
            "The current portfolio is missing required column(s): "
            f"{formatted_columns}."
        )

    return portfolio


# ============================================================
# Snapshot Calculation
# ============================================================


def build_portfolio_snapshot(
    portfolio: pd.DataFrame,
    *,
    snapshot_date: date | datetime | None = None,
) -> PortfolioSnapshot:
    """
    Calculate one portfolio snapshot from the current portfolio.

    Args:
        portfolio:
            Portfolio dataframe returned by PortfolioService.

        snapshot_date:
            Optional date assigned to the snapshot.

    Returns:
        Validated PortfolioSnapshot.
    """

    if not isinstance(portfolio, pd.DataFrame):
        raise TypeError(
            "portfolio must be a pandas DataFrame."
        )

    if portfolio.empty:
        raise PortfolioSnapshotValidationError(
            "The portfolio cannot be empty."
        )

    missing_columns = tuple(
        column
        for column in (
            INVESTMENT_COLUMN,
            CURRENT_VALUE_COLUMN,
        )
        if column not in portfolio.columns
    )

    if missing_columns:
        formatted_columns = ", ".join(
            missing_columns
        )

        raise PortfolioSnapshotValidationError(
            "The portfolio is missing required column(s): "
            f"{formatted_columns}."
        )

    investments = pd.to_numeric(
        portfolio[INVESTMENT_COLUMN],
        errors="coerce",
    )

    current_values = pd.to_numeric(
        portfolio[CURRENT_VALUE_COLUMN],
        errors="coerce",
    )

    if investments.isna().any():
        raise PortfolioSnapshotValidationError(
            "Investment contains invalid or missing numeric values."
        )

    if current_values.isna().any():
        raise PortfolioSnapshotValidationError(
            "Current Value contains invalid or missing numeric values."
        )

    total_investment = _require_finite_number(
        investments.sum(),
        field_name="total investment",
    )

    total_current_value = _require_finite_number(
        current_values.sum(),
        field_name="total current value",
    )

    if total_investment < 0.0:
        raise PortfolioSnapshotValidationError(
            "Total investment cannot be negative."
        )

    if total_current_value < 0.0:
        raise PortfolioSnapshotValidationError(
            "Total current value cannot be negative."
        )

    total_profit = total_current_value - total_investment

    return_percent = (
        total_profit
        / total_investment
        * 100.0
        if total_investment > 0.0
        else 0.0
    )

    return PortfolioSnapshot(
        snapshot_date=_validate_snapshot_date(
            snapshot_date
        ),
        investment=round(
            total_investment,
            2,
        ),
        current_value=round(
            total_current_value,
            2,
        ),
        profit=round(
            total_profit,
            2,
        ),
        return_percent=round(
            return_percent,
            2,
        ),
    )


# ============================================================
# History DataFrame Helpers
# ============================================================


def create_empty_history() -> pd.DataFrame:
    """
    Create an empty master history dataframe.
    """

    return pd.DataFrame(
        {
            DATE_COLUMN: pd.Series(
                dtype="datetime64[ns]"
            ),
            INVESTMENT_COLUMN: pd.Series(
                dtype="float64"
            ),
            CURRENT_VALUE_COLUMN: pd.Series(
                dtype="float64"
            ),
            PROFIT_COLUMN: pd.Series(
                dtype="float64"
            ),
            RETURN_PERCENT_COLUMN: pd.Series(
                dtype="float64"
            ),
        }
    )


def normalize_master_history(
    history: pd.DataFrame,
) -> pd.DataFrame:
    """
    Normalize the master portfolio-history dataframe.

    Invalid rows are removed. Multiple snapshots for the same calendar date
    are collapsed to the final snapshot for that date.
    """

    if not isinstance(history, pd.DataFrame):
        raise TypeError(
            "history must be a pandas DataFrame."
        )

    if history.empty:
        return create_empty_history()

    normalized_history = history.copy()

    for column in HISTORY_COLUMNS:
        if column not in normalized_history.columns:
            normalized_history[column] = pd.NA

    normalized_history = normalized_history.loc[
        :,
        list(HISTORY_COLUMNS),
    ]

    normalized_history[DATE_COLUMN] = pd.to_datetime(
        normalized_history[DATE_COLUMN],
        errors="coerce",
    )

    for column in (
        INVESTMENT_COLUMN,
        CURRENT_VALUE_COLUMN,
        PROFIT_COLUMN,
        RETURN_PERCENT_COLUMN,
    ):
        normalized_history[column] = pd.to_numeric(
            normalized_history[column],
            errors="coerce",
        )

    normalized_history = normalized_history.dropna(
        subset=list(HISTORY_COLUMNS)
    )

    normalized_history = normalized_history[
        (
            normalized_history[INVESTMENT_COLUMN]
            >= 0.0
        )
        & (
            normalized_history[CURRENT_VALUE_COLUMN]
            >= 0.0
        )
    ]

    normalized_history[DATE_COLUMN] = (
        normalized_history[DATE_COLUMN].dt.normalize()
    )

    normalized_history = (
        normalized_history
        .sort_values(
            by=DATE_COLUMN,
            kind="stable",
        )
        .drop_duplicates(
            subset=[DATE_COLUMN],
            keep="last",
        )
        .sort_values(
            by=DATE_COLUMN,
            kind="stable",
        )
        .reset_index(drop=True)
    )

    for column in (
        INVESTMENT_COLUMN,
        CURRENT_VALUE_COLUMN,
        PROFIT_COLUMN,
        RETURN_PERCENT_COLUMN,
    ):
        normalized_history[column] = (
            normalized_history[column]
            .astype(float)
            .round(2)
        )

    return normalized_history


def load_existing_history(
    history_path: str | Path = DEFAULT_HISTORY_PATH,
) -> pd.DataFrame:
    """
    Load the existing master history file.

    A missing file returns an empty dataframe.
    """

    resolved_path = _validate_history_path(
        history_path
    )

    if not resolved_path.exists():
        return create_empty_history()

    if not resolved_path.is_file():
        raise PortfolioHistoryReadError(
            "The history path is not a file: "
            f"{resolved_path}"
        )

    try:
        raw_history = pd.read_csv(
            resolved_path
        )
    except Exception as error:
        raise PortfolioHistoryReadError(
            "Unable to read portfolio history from "
            f"{resolved_path}: {error}"
        ) from error

    try:
        return normalize_master_history(
            raw_history
        )
    except Exception as error:
        raise PortfolioHistoryReadError(
            "Unable to normalize existing portfolio history: "
            f"{error}"
        ) from error


# ============================================================
# History Update
# ============================================================


def merge_snapshot_into_history(
    history: pd.DataFrame,
    snapshot: PortfolioSnapshot,
) -> pd.DataFrame:
    """
    Insert or replace one daily portfolio snapshot.

    If history already contains a snapshot for the same calendar date, the
    existing row is replaced.
    """

    if not isinstance(snapshot, PortfolioSnapshot):
        raise TypeError(
            "snapshot must be a PortfolioSnapshot."
        )

    normalized_history = normalize_master_history(
        history
    )

    snapshot_frame = pd.DataFrame(
        [
            snapshot.to_record()
        ]
    )

    combined_history = pd.concat(
        [
            normalized_history,
            snapshot_frame,
        ],
        ignore_index=True,
    )

    return normalize_master_history(
        combined_history
    )


def save_portfolio_history(
    history: pd.DataFrame,
    history_path: str | Path = DEFAULT_HISTORY_PATH,
) -> Path:
    """
    Save normalized master history to CSV.
    """

    resolved_path = _validate_history_path(
        history_path
    )

    normalized_history = normalize_master_history(
        history
    )

    try:
        resolved_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_history = normalized_history.copy()

        output_history[DATE_COLUMN] = (
            output_history[DATE_COLUMN]
            .dt.strftime("%Y-%m-%d")
        )

        output_history.to_csv(
            resolved_path,
            index=False,
        )

    except Exception as error:
        raise PortfolioHistoryWriteError(
            "Unable to save portfolio history to "
            f"{resolved_path}: {error}"
        ) from error

    return resolved_path


def update_portfolio_history(
    *,
    portfolio_service: PortfolioService | None = None,
    history_path: str | Path = DEFAULT_HISTORY_PATH,
    snapshot_date: date | datetime | None = None,
) -> PortfolioSnapshot:
    """
    Update the master portfolio history with the latest portfolio snapshot.

    Args:
        portfolio_service:
            Optional PortfolioService dependency.

        history_path:
            Master history CSV path.

        snapshot_date:
            Optional snapshot date. Defaults to today.

    Returns:
        Snapshot written to the history file.
    """

    portfolio = load_current_portfolio(
        portfolio_service
    )

    snapshot = build_portfolio_snapshot(
        portfolio,
        snapshot_date=snapshot_date,
    )

    existing_history = load_existing_history(
        history_path
    )

    updated_history = merge_snapshot_into_history(
        existing_history,
        snapshot,
    )

    save_portfolio_history(
        updated_history,
        history_path,
    )

    return snapshot


# ============================================================
# Command-Line Entry Point
# ============================================================


def main() -> int:
    """
    Run the portfolio-history update from the command line.
    """

    try:
        snapshot = update_portfolio_history()

    except PortfolioHistoryUpdateError as error:
        print(
            "Portfolio history update failed:"
        )
        print(
            str(error)
        )
        return 1

    except Exception as error:
        print(
            "An unexpected error occurred while updating "
            "portfolio history:"
        )
        print(
            str(error)
        )
        return 1

    print(
        "Portfolio history updated successfully."
    )

    print(
        f"Date: {snapshot.snapshot_date.isoformat()}"
    )

    print(
        f"Investment: {snapshot.investment:,.2f}"
    )

    print(
        f"Current Value: {snapshot.current_value:,.2f}"
    )

    print(
        f"Profit: {snapshot.profit:,.2f}"
    )

    print(
        f"Return: {snapshot.return_percent:,.2f}%"
    )

    print(
        f"History file: {DEFAULT_HISTORY_PATH}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )