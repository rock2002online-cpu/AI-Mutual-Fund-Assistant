"""
Historical portfolio analytics orchestration service.

This module converts normalized portfolio valuation history into a reusable,
immutable historical analytics result.

Architecture
------------
PortfolioHistoryService remains responsible for:

- Loading historical portfolio valuation data.
- Validating the source CSV schema.
- Returning canonical ``Date`` and ``Value`` columns.

Existing analytics modules remain responsible for:

- CAGR calculation.
- Periodic-return calculation.
- Volatility calculation.
- Drawdown calculation.

HistoryAnalyticsService coordinates those existing analytics APIs and adds
only basic descriptive statistics that do not belong to another analytics
module.

This module contains no Streamlit, Plotly, file access, or dashboard logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final

import pandas as pd

from services.analytics.cagr import (
    CAGRResult,
    calculate_portfolio_cagr,
)
from services.analytics.drawdown import (
    DrawdownResult,
    ValueObservation,
    calculate_portfolio_drawdown,
)
from services.analytics.volatility import (
    DEFAULT_PERIODS_PER_YEAR,
    VolatilityResult,
    calculate_periodic_returns,
    calculate_portfolio_volatility,
)


# ============================================================
# Canonical History Schema
# ============================================================

DATE_COLUMN: Final[str] = "Date"
VALUE_COLUMN: Final[str] = "Value"

REQUIRED_HISTORY_COLUMNS: Final[frozenset[str]] = frozenset(
    {
        DATE_COLUMN,
        VALUE_COLUMN,
    }
)

MINIMUM_CAGR_OBSERVATIONS: Final[int] = 2
MINIMUM_DRAWDOWN_OBSERVATIONS: Final[int] = 2
MINIMUM_VOLATILITY_VALUES: Final[int] = 3


# ============================================================
# Exceptions
# ============================================================


class HistoryAnalyticsError(RuntimeError):
    """
    Base exception raised by historical analytics orchestration.
    """


class HistoryAnalyticsValidationError(
    HistoryAnalyticsError
):
    """
    Raised when historical analytics input is invalid.
    """


class HistoryAnalyticsCalculationError(
    HistoryAnalyticsError
):
    """
    Raised when historical analytics cannot be calculated.
    """


# ============================================================
# Input and Result Models
# ============================================================


@dataclass(frozen=True, slots=True)
class HistoryAnalyticsInput:
    """
    Input model for historical portfolio analytics.

    Attributes:
        history:
            Normalized portfolio valuation history containing canonical
            ``Date`` and ``Value`` columns.

        periods_per_year:
            Number of return periods used when annualising volatility.

            The default is inherited from the existing volatility analytics
            module.
    """

    history: pd.DataFrame
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR


@dataclass(frozen=True, slots=True)
class HistoryAnalyticsResult:
    """
    Immutable result containing historical portfolio analytics.

    Attributes:
        observation_count:
            Number of validated historical valuation observations.

        start_date:
            Earliest portfolio valuation date.

        end_date:
            Latest portfolio valuation date.

        duration_days:
            Number of calendar days between the first and last observation.

        starting_value:
            Portfolio value at the first observation.

        latest_value:
            Portfolio value at the final observation.

        minimum_value:
            Lowest portfolio value in the historical period.

        maximum_value:
            Highest portfolio value in the historical period.

        average_value:
            Arithmetic mean of historical portfolio values.

        absolute_growth:
            Difference between latest and starting values.

        total_growth_percent:
            Total portfolio-value change across the historical period.

        periodic_returns:
            Chronological periodic returns derived from portfolio values.

        cagr:
            Existing CAGR analytics result.

            None when there are insufficient observations or the first and
            final dates do not form a valid annualisation period.

        drawdown:
            Existing drawdown analytics result.

            None when fewer than two valid observations are available.

        volatility:
            Existing volatility analytics result.

            None when there are insufficient returns for sample volatility.

        periods_per_year:
            Annualisation frequency supplied to volatility analytics.
    """

    observation_count: int

    start_date: date
    end_date: date
    duration_days: int

    starting_value: float
    latest_value: float

    minimum_value: float
    maximum_value: float
    average_value: float

    absolute_growth: float
    total_growth_percent: float

    periodic_returns: tuple[float, ...]

    cagr: CAGRResult | None
    drawdown: DrawdownResult | None
    volatility: VolatilityResult | None

    periods_per_year: int


# ============================================================
# Validation Helpers
# ============================================================


def _validate_periods_per_year(
    periods_per_year: int,
) -> int:
    """
    Validate volatility annualisation frequency.

    Args:
        periods_per_year:
            Number of return periods in one year.

    Returns:
        Validated integer.

    Raises:
        TypeError:
            When periods_per_year is not an integer.

        HistoryAnalyticsValidationError:
            When periods_per_year is not positive.
    """

    if isinstance(periods_per_year, bool) or not isinstance(
        periods_per_year,
        int,
    ):
        raise TypeError(
            "periods_per_year must be an integer."
        )

    if periods_per_year <= 0:
        raise HistoryAnalyticsValidationError(
            "periods_per_year must be greater than zero."
        )

    return periods_per_year


def _get_missing_columns(
    history: pd.DataFrame,
) -> tuple[str, ...]:
    """
    Return canonical history columns missing from the dataframe.
    """

    return tuple(
        sorted(
            REQUIRED_HISTORY_COLUMNS.difference(
                history.columns
            )
        )
    )


def _validate_history_dataframe(
    history: pd.DataFrame,
) -> None:
    """
    Validate the historical dataframe input boundary.

    Args:
        history:
            Expected normalized portfolio-history dataframe.

    Raises:
        TypeError:
            When history is not a pandas DataFrame.

        HistoryAnalyticsValidationError:
            When the dataframe is empty or missing canonical columns.
    """

    if not isinstance(history, pd.DataFrame):
        raise TypeError(
            "history must be a pandas DataFrame."
        )

    if history.empty:
        raise HistoryAnalyticsValidationError(
            "history must contain at least one observation."
        )

    missing_columns = _get_missing_columns(
        history
    )

    if missing_columns:
        raise HistoryAnalyticsValidationError(
            "history is missing required column(s): "
            f"{', '.join(missing_columns)}."
        )


# ============================================================
# History Normalization
# ============================================================


def prepare_history_for_analytics(
    history: pd.DataFrame,
) -> pd.DataFrame:
    """
    Prepare normalized portfolio history for analytics calculations.

    PortfolioHistoryService should already return validated canonical data.
    This function protects the analytics service boundary when callers provide
    custom dataframes or test fixtures.

    Processing performed:

    - Select Date and Value.
    - Convert Date to pandas datetime.
    - Convert Value to numeric.
    - Remove invalid dates and values.
    - Remove non-positive portfolio values.
    - Sort chronologically.
    - Keep the final observation for duplicate dates.
    - Reset the dataframe index.

    The caller's dataframe is never mutated.

    Args:
        history:
            Portfolio-history dataframe containing Date and Value.

    Returns:
        Analytics-ready dataframe.

    Raises:
        TypeError:
            When history is not a pandas DataFrame.

        HistoryAnalyticsValidationError:
            When required columns are missing or no valid records remain.
    """

    _validate_history_dataframe(
        history
    )

    prepared = history.loc[
        :,
        [
            DATE_COLUMN,
            VALUE_COLUMN,
        ],
    ].copy()

    prepared[DATE_COLUMN] = pd.to_datetime(
        prepared[DATE_COLUMN],
        errors="coerce",
    )

    prepared[VALUE_COLUMN] = pd.to_numeric(
        prepared[VALUE_COLUMN],
        errors="coerce",
    )

    prepared = prepared.dropna(
        subset=[
            DATE_COLUMN,
            VALUE_COLUMN,
        ]
    )

    prepared = prepared.loc[
        prepared[VALUE_COLUMN] > 0
    ]

    prepared = prepared.sort_values(
        by=DATE_COLUMN,
        kind="stable",
    )

    prepared = prepared.drop_duplicates(
        subset=[DATE_COLUMN],
        keep="last",
    )

    prepared = prepared.reset_index(
        drop=True
    )

    if prepared.empty:
        raise HistoryAnalyticsValidationError(
            "history contains no valid positive portfolio-value "
            "observations."
        )

    return prepared


# ============================================================
# Analytics Input Adapters
# ============================================================


def _build_value_observations(
    prepared_history: pd.DataFrame,
) -> tuple[ValueObservation, ...]:
    """
    Convert prepared history into drawdown value observations.
    """

    return tuple(
        ValueObservation(
            observation_date=row.Date.date(),
            value=float(row.Value),
        )
        for row in prepared_history.itertuples(
            index=False
        )
    )


def _calculate_periodic_history_returns(
    prepared_history: pd.DataFrame,
) -> tuple[float, ...]:
    """
    Calculate periodic returns.

    Fewer than three historical values cannot produce the minimum number of
    return observations required by the existing volatility analytics module.
    In that case, simply return an empty tuple.
    """

    values = tuple(
        float(value)
        for value in prepared_history[
            VALUE_COLUMN
        ].tolist()
    )

    # Existing volatility module requires at least 3 values.
    if len(values) < 3:
        return ()

    return calculate_periodic_returns(values)

def _calculate_history_cagr(
    prepared_history: pd.DataFrame,
) -> CAGRResult | None:
    """
    Calculate historical CAGR using the existing CAGR module.

    CAGR is unavailable when fewer than two observations exist or when the
    first and final observations occur on the same date.
    """

    if len(prepared_history) < MINIMUM_CAGR_OBSERVATIONS:
        return None

    first_row = prepared_history.iloc[0]
    last_row = prepared_history.iloc[-1]

    start_date = first_row[DATE_COLUMN].date()
    end_date = last_row[DATE_COLUMN].date()

    if end_date <= start_date:
        return None

    return calculate_portfolio_cagr(
        initial_value=float(
            first_row[VALUE_COLUMN]
        ),
        final_value=float(
            last_row[VALUE_COLUMN]
        ),
        start_date=start_date,
        end_date=end_date,
    )


def _calculate_history_drawdown(
    observations: tuple[ValueObservation, ...],
) -> DrawdownResult | None:
    """
    Calculate drawdown through the existing drawdown module.
    """

    if len(observations) < MINIMUM_DRAWDOWN_OBSERVATIONS:
        return None

    return calculate_portfolio_drawdown(
        observations
    )


def _calculate_history_volatility(
    periodic_returns: tuple[float, ...],
    *,
    periods_per_year: int,
) -> VolatilityResult | None:
    """
    Calculate annualised volatility through the existing volatility module.

    Sample volatility requires at least two periodic returns. Therefore,
    at least three historical values are required.
    """

    minimum_returns = (
        MINIMUM_VOLATILITY_VALUES - 1
    )

    if len(periodic_returns) < minimum_returns:
        return None

    return calculate_portfolio_volatility(
        periodic_returns,
        periods_per_year=periods_per_year,
    )


# ============================================================
# Service
# ============================================================


class HistoryAnalyticsService:
    """
    Orchestrate historical portfolio analytics.

    The service consumes normalized Date and Value history and reuses existing
    CAGR, drawdown, periodic-return, and volatility analytics functions.

    It performs no file access and has no dependency on Streamlit or Plotly.
    """

    def calculate(
        self,
        input_data: HistoryAnalyticsInput,
    ) -> HistoryAnalyticsResult:
        """
        Calculate historical portfolio analytics.

        Args:
            input_data:
                Typed historical analytics input.

        Returns:
            Immutable HistoryAnalyticsResult.

        Raises:
            TypeError:
                When input_data or one of its typed fields has an unsupported
                type.

            HistoryAnalyticsValidationError:
                When history cannot be normalized into valid observations.

            HistoryAnalyticsCalculationError:
                When an existing analytics dependency fails unexpectedly.
        """

        if not isinstance(
            input_data,
            HistoryAnalyticsInput,
        ):
            raise TypeError(
                "input_data must be a HistoryAnalyticsInput."
            )

        periods_per_year = (
            _validate_periods_per_year(
                input_data.periods_per_year
            )
        )

        prepared_history = (
            prepare_history_for_analytics(
                input_data.history
            )
        )

        observation_count = len(
            prepared_history
        )

        first_row = prepared_history.iloc[0]
        last_row = prepared_history.iloc[-1]

        start_date = first_row[
            DATE_COLUMN
        ].date()

        end_date = last_row[
            DATE_COLUMN
        ].date()

        starting_value = float(
            first_row[VALUE_COLUMN]
        )

        latest_value = float(
            last_row[VALUE_COLUMN]
        )

        minimum_value = float(
            prepared_history[
                VALUE_COLUMN
            ].min()
        )

        maximum_value = float(
            prepared_history[
                VALUE_COLUMN
            ].max()
        )

        average_value = float(
            prepared_history[
                VALUE_COLUMN
            ].mean()
        )

        absolute_growth = (
            latest_value - starting_value
        )

        total_growth_percent = (
            absolute_growth
            / starting_value
            * 100.0
        )

        duration_days = (
            end_date - start_date
        ).days

        observations = (
            _build_value_observations(
                prepared_history
            )
        )

        try:
            periodic_returns = (
                _calculate_periodic_history_returns(
                    prepared_history
                )
            )

            cagr_result = (
                _calculate_history_cagr(
                    prepared_history
                )
            )

            drawdown_result = (
                _calculate_history_drawdown(
                    observations
                )
            )

            volatility_result = (
                _calculate_history_volatility(
                    periodic_returns,
                    periods_per_year=periods_per_year,
                )
            )

        except HistoryAnalyticsError:
            raise

        except Exception as error:
            raise HistoryAnalyticsCalculationError(
                "Historical portfolio analytics could not be "
                f"calculated: {error}"
            ) from error

        return HistoryAnalyticsResult(
            observation_count=observation_count,
            start_date=start_date,
            end_date=end_date,
            duration_days=duration_days,
            starting_value=starting_value,
            latest_value=latest_value,
            minimum_value=minimum_value,
            maximum_value=maximum_value,
            average_value=average_value,
            absolute_growth=absolute_growth,
            total_growth_percent=total_growth_percent,
            periodic_returns=periodic_returns,
            cagr=cagr_result,
            drawdown=drawdown_result,
            volatility=volatility_result,
            periods_per_year=periods_per_year,
        )


# ============================================================
# Convenience API
# ============================================================


def calculate_history_analytics(
    history: pd.DataFrame,
    *,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
) -> HistoryAnalyticsResult:
    """
    Calculate historical portfolio analytics through a convenience function.

    Args:
        history:
            Normalized Date and Value portfolio-history dataframe.

        periods_per_year:
            Annualisation frequency used by volatility analytics.

    Returns:
        Immutable HistoryAnalyticsResult.
    """

    service = HistoryAnalyticsService()

    return service.calculate(
        HistoryAnalyticsInput(
            history=history,
            periods_per_year=periods_per_year,
        )
    )


__all__ = [
    "DATE_COLUMN",
    "HistoryAnalyticsCalculationError",
    "HistoryAnalyticsError",
    "HistoryAnalyticsInput",
    "HistoryAnalyticsResult",
    "HistoryAnalyticsService",
    "HistoryAnalyticsValidationError",
    "MINIMUM_CAGR_OBSERVATIONS",
    "MINIMUM_DRAWDOWN_OBSERVATIONS",
    "MINIMUM_VOLATILITY_VALUES",
    "REQUIRED_HISTORY_COLUMNS",
    "VALUE_COLUMN",
    "calculate_history_analytics",
    "prepare_history_for_analytics",
]