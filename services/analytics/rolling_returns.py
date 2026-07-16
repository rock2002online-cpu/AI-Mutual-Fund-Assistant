"""
Portfolio and fund rolling-return analytics.

This module provides framework-independent calculations for:

- Rolling total returns
- Rolling annualised returns
- Best and worst rolling periods
- Average and median rolling returns
- Positive and negative return consistency
- Target-return success frequency
- Portfolio-level rolling-return analytics
- Fund-wise rolling-return analytics
- Batch fund calculations

The module contains no Streamlit, Plotly, or pandas dependencies.

PortfolioService remains the single source of portfolio data. Historical
portfolio or fund values retrieved through PortfolioService or an authorised
market-data service should be transformed into the typed observations defined
in this module before rolling-return calculations are performed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite
from statistics import mean, median
from typing import Iterable, Literal, Sequence


# ============================================================
# Constants and Type Aliases
# ============================================================

DAYS_PER_YEAR = 365.25
MINIMUM_VALUE_OBSERVATIONS = 2
DEFAULT_WINDOW_SIZE = 12

RollingReturnRating = Literal[
    "poor",
    "weak",
    "moderate",
    "good",
    "excellent",
]


# ============================================================
# Exceptions
# ============================================================


class RollingReturnsValidationError(ValueError):
    """
    Raised when rolling-return inputs fail validation.
    """


class RollingReturnsCalculationError(RuntimeError):
    """
    Raised when rolling returns cannot be calculated.
    """


# ============================================================
# Input Dataclasses
# ============================================================


@dataclass(frozen=True, slots=True)
class ValueObservation:
    """
    Represents one dated portfolio or fund value.

    Attributes:
        observation_date:
            Date associated with the portfolio value or fund NAV.

        value:
            Positive portfolio value or fund NAV.
    """

    observation_date: date | datetime
    value: float


@dataclass(frozen=True, slots=True)
class RollingReturnsInput:
    """
    Input model for portfolio or generic rolling-return calculation.

    Attributes:
        observations:
            Historical value observations.

        window_size:
            Number of observation intervals included in each rolling window.

            Example:
                For monthly observations, window_size=12 represents a
                rolling 12-month period.

        annualise:
            Whether each rolling return should be annualised.

        target_return:
            Optional target return represented as a decimal.

            Example:
                0.10 means 10%.
    """

    observations: tuple[ValueObservation, ...]
    window_size: int = DEFAULT_WINDOW_SIZE
    annualise: bool = True
    target_return: float | None = None


@dataclass(frozen=True, slots=True)
class FundRollingReturnsInput:
    """
    Input model for one mutual fund's rolling-return calculation.

    Attributes:
        fund_name:
            Human-readable mutual fund name.

        observations:
            Historical fund value or NAV observations.

        window_size:
            Number of observation intervals in each rolling window.

        annualise:
            Whether returns should be annualised.

        target_return:
            Optional target return represented as a decimal.

        scheme_code:
            Optional mutual fund scheme identifier.

        source:
            Optional historical-data source description.
    """

    fund_name: str
    observations: tuple[ValueObservation, ...]
    window_size: int = DEFAULT_WINDOW_SIZE
    annualise: bool = True
    target_return: float | None = None
    scheme_code: str | None = None
    source: str | None = None


# ============================================================
# Result Dataclasses
# ============================================================


@dataclass(frozen=True, slots=True)
class RollingReturnPoint:
    """
    Represents one rolling-return period.

    Attributes:
        start_date:
            First observation date in the rolling period.

        end_date:
            Final observation date in the rolling period.

        start_value:
            Portfolio or fund value at the start of the period.

        end_value:
            Portfolio or fund value at the end of the period.

        duration_days:
            Number of calendar days in the rolling period.

        duration_years:
            Fractional number of years in the rolling period.

        total_return_decimal:
            Total rolling-period return represented as a decimal.

        total_return_percent:
            Total rolling-period return expressed as a percentage.

        annualised_return_decimal:
            Annualised rolling return, when annualisation is enabled.

        annualised_return_percent:
            Annualised rolling return expressed as a percentage.
    """

    start_date: date
    end_date: date
    start_value: float
    end_value: float
    duration_days: int
    duration_years: float
    total_return_decimal: float
    total_return_percent: float
    annualised_return_decimal: float | None
    annualised_return_percent: float | None


@dataclass(frozen=True, slots=True)
class RollingReturnsResult:
    """
    Result of a rolling-return calculation.

    Attributes:
        observation_count:
            Number of historical observations used.

        rolling_period_count:
            Number of rolling periods generated.

        window_size:
            Number of observation intervals per rolling period.

        annualised:
            Whether annualised returns were calculated.

        target_return_decimal:
            Optional target return used for consistency calculations.

        average_return_decimal:
            Arithmetic mean rolling return.

        median_return_decimal:
            Median rolling return.

        best_return_decimal:
            Highest rolling return.

        worst_return_decimal:
            Lowest rolling return.

        positive_period_count:
            Number of rolling periods with return above zero.

        negative_period_count:
            Number of rolling periods with return below zero.

        zero_period_count:
            Number of rolling periods with return equal to zero.

        positive_period_frequency:
            Proportion of rolling periods with positive returns.

        negative_period_frequency:
            Proportion of rolling periods with negative returns.

        target_achieved_count:
            Number of periods meeting or exceeding target_return.

        target_achieved_frequency:
            Proportion of periods meeting or exceeding target_return.

        best_period:
            RollingReturnPoint with the highest return.

        worst_period:
            RollingReturnPoint with the lowest return.

        rating:
            Descriptive consistency rating.

        rolling_returns:
            Complete chronological rolling-return series.
    """

    observation_count: int
    rolling_period_count: int
    window_size: int
    annualised: bool

    target_return_decimal: float | None
    target_return_percent: float | None

    average_return_decimal: float
    average_return_percent: float

    median_return_decimal: float
    median_return_percent: float

    best_return_decimal: float
    best_return_percent: float

    worst_return_decimal: float
    worst_return_percent: float

    positive_period_count: int
    negative_period_count: int
    zero_period_count: int

    positive_period_frequency: float
    negative_period_frequency: float

    target_achieved_count: int | None
    target_achieved_frequency: float | None

    best_period: RollingReturnPoint
    worst_period: RollingReturnPoint

    rating: RollingReturnRating

    rolling_returns: tuple[RollingReturnPoint, ...]


@dataclass(frozen=True, slots=True)
class FundRollingReturnsResult:
    """
    Rolling-return result for one mutual fund.
    """

    fund_name: str
    scheme_code: str | None
    result: RollingReturnsResult
    source: str | None = None


@dataclass(frozen=True, slots=True)
class FundRollingReturnsFailure:
    """
    Represents a failed fund rolling-return calculation.
    """

    fund_name: str
    scheme_code: str | None
    error: str


@dataclass(frozen=True, slots=True)
class FundRollingReturnsBatchResult:
    """
    Aggregate result from fund-wise rolling-return calculations.
    """

    successful: tuple[FundRollingReturnsResult, ...]
    failed: tuple[FundRollingReturnsFailure, ...]
    total_received: int
    successful_count: int
    failed_count: int


# ============================================================
# Numeric Validation Helpers
# ============================================================


def _validate_finite_number(
    value: float | int,
    field_name: str,
) -> float:
    """
    Validate and convert a numeric value to float.
    """

    if isinstance(value, bool):
        raise RollingReturnsValidationError(
            f"{field_name} must be numeric and cannot be a boolean."
        )

    try:
        numeric_value = float(value)
    except (TypeError, ValueError) as exc:
        raise RollingReturnsValidationError(
            f"{field_name} must be a valid numeric value."
        ) from exc

    if not isfinite(numeric_value):
        raise RollingReturnsValidationError(
            f"{field_name} must be finite and cannot be NaN or infinite."
        )

    return numeric_value


def _validate_positive_value(
    value: float | int,
    field_name: str,
) -> float:
    """
    Validate a strictly positive numeric value.
    """

    numeric_value = _validate_finite_number(
        value,
        field_name,
    )

    if numeric_value <= 0:
        raise RollingReturnsValidationError(
            f"{field_name} must be greater than zero."
        )

    return numeric_value


def _validate_positive_integer(
    value: int,
    field_name: str,
) -> int:
    """
    Validate a strictly positive integer.
    """

    if isinstance(value, bool) or not isinstance(value, int):
        raise RollingReturnsValidationError(
            f"{field_name} must be an integer."
        )

    if value <= 0:
        raise RollingReturnsValidationError(
            f"{field_name} must be greater than zero."
        )

    return value


def _validate_boolean(
    value: bool,
    field_name: str,
) -> bool:
    """
    Validate a strict boolean value.
    """

    if not isinstance(value, bool):
        raise RollingReturnsValidationError(
            f"{field_name} must be a boolean."
        )

    return value


# ============================================================
# Text Validation Helpers
# ============================================================


def _validate_required_text(
    value: str,
    field_name: str,
) -> str:
    """
    Validate and normalise required text.
    """

    if not isinstance(value, str):
        raise RollingReturnsValidationError(
            f"{field_name} must be a string."
        )

    normalised_value = value.strip()

    if not normalised_value:
        raise RollingReturnsValidationError(
            f"{field_name} cannot be empty."
        )

    return normalised_value


def _normalise_optional_text(
    value: str | None,
    field_name: str,
) -> str | None:
    """
    Normalise optional text and convert blank strings to None.
    """

    if value is None:
        return None

    if not isinstance(value, str):
        raise RollingReturnsValidationError(
            f"{field_name} must be a string or None."
        )

    normalised_value = value.strip()

    return normalised_value or None


# ============================================================
# Observation Validation
# ============================================================


def _normalise_date(
    value: date | datetime,
    field_name: str,
) -> date:
    """
    Convert a date or datetime instance to date.
    """

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    raise RollingReturnsValidationError(
        f"{field_name} must be a date or datetime instance."
    )


def _validate_observation(
    observation: ValueObservation,
    index: int,
) -> ValueObservation:
    """
    Validate and normalise one historical observation.
    """

    if not isinstance(observation, ValueObservation):
        raise TypeError(
            f"observations[{index}] must be a ValueObservation instance."
        )

    observation_date = _normalise_date(
        observation.observation_date,
        f"observations[{index}].observation_date",
    )

    value = _validate_positive_value(
        observation.value,
        f"observations[{index}].value",
    )

    return ValueObservation(
        observation_date=observation_date,
        value=value,
    )


def _validate_observations(
    observations: Iterable[ValueObservation],
) -> tuple[ValueObservation, ...]:
    """
    Validate, normalise, and chronologically sort observations.

    Duplicate dates are rejected because they would make rolling-period
    boundaries ambiguous.
    """

    if isinstance(observations, (str, bytes)):
        raise RollingReturnsValidationError(
            "observations must be an iterable of ValueObservation instances."
        )

    try:
        normalised_observations = tuple(
            _validate_observation(observation, index)
            for index, observation in enumerate(observations)
        )
    except TypeError as exc:
        if str(exc).startswith("observations["):
            raise

        raise RollingReturnsValidationError(
            "observations must be an iterable of ValueObservation instances."
        ) from exc

    if len(normalised_observations) < MINIMUM_VALUE_OBSERVATIONS:
        raise RollingReturnsValidationError(
            "At least two value observations are required."
        )

    sorted_observations = tuple(
        sorted(
            normalised_observations,
            key=lambda observation: observation.observation_date,
        )
    )

    for index in range(1, len(sorted_observations)):
        previous_date = (
            sorted_observations[index - 1].observation_date
        )

        current_date = (
            sorted_observations[index].observation_date
        )

        if current_date == previous_date:
            raise RollingReturnsValidationError(
                "Duplicate observation date detected: "
                f"{current_date.isoformat()}."
            )

    return sorted_observations


# ============================================================
# Public Input Validation
# ============================================================


def validate_rolling_returns_input(
    input_data: RollingReturnsInput,
) -> RollingReturnsInput:
    """
    Validate and normalise generic rolling-return input.
    """

    if not isinstance(input_data, RollingReturnsInput):
        raise TypeError(
            "input_data must be an instance of RollingReturnsInput."
        )

    observations = _validate_observations(
        input_data.observations
    )

    window_size = _validate_positive_integer(
        input_data.window_size,
        "window_size",
    )

    annualise = _validate_boolean(
        input_data.annualise,
        "annualise",
    )

    if window_size >= len(observations):
        raise RollingReturnsValidationError(
            "window_size must be smaller than the number of observations."
        )

    target_return: float | None

    if input_data.target_return is None:
        target_return = None
    else:
        target_return = _validate_finite_number(
            input_data.target_return,
            "target_return",
        )

        if target_return <= -1.0:
            raise RollingReturnsValidationError(
                "target_return must be greater than -1.0."
            )

    return RollingReturnsInput(
        observations=observations,
        window_size=window_size,
        annualise=annualise,
        target_return=target_return,
    )


def validate_fund_rolling_returns_input(
    input_data: FundRollingReturnsInput,
) -> FundRollingReturnsInput:
    """
    Validate and normalise fund-level rolling-return input.
    """

    if not isinstance(input_data, FundRollingReturnsInput):
        raise TypeError(
            "input_data must be an instance of FundRollingReturnsInput."
        )

    fund_name = _validate_required_text(
        input_data.fund_name,
        "fund_name",
    )

    observations = _validate_observations(
        input_data.observations
    )

    window_size = _validate_positive_integer(
        input_data.window_size,
        "window_size",
    )

    annualise = _validate_boolean(
        input_data.annualise,
        "annualise",
    )

    if window_size >= len(observations):
        raise RollingReturnsValidationError(
            "window_size must be smaller than the number of observations."
        )

    target_return: float | None

    if input_data.target_return is None:
        target_return = None
    else:
        target_return = _validate_finite_number(
            input_data.target_return,
            "target_return",
        )

        if target_return <= -1.0:
            raise RollingReturnsValidationError(
                "target_return must be greater than -1.0."
            )

    scheme_code = _normalise_optional_text(
        input_data.scheme_code,
        "scheme_code",
    )

    source = _normalise_optional_text(
        input_data.source,
        "source",
    )

    return FundRollingReturnsInput(
        fund_name=fund_name,
        observations=observations,
        window_size=window_size,
        annualise=annualise,
        target_return=target_return,
        scheme_code=scheme_code,
        source=source,
    )


# ============================================================
# Return Helpers
# ============================================================


def _calculate_total_return(
    start_value: float,
    end_value: float,
) -> float:
    """
    Calculate total return between two positive values.
    """

    total_return = (
        end_value / start_value
    ) - 1.0

    if not isfinite(total_return):
        raise RollingReturnsCalculationError(
            "The supplied values produced a non-finite total return."
        )

    return total_return


def _calculate_annualised_return(
    start_value: float,
    end_value: float,
    duration_years: float,
) -> float:
    """
    Calculate annualised return between two values.

    Formula:
        annualised_return =
            (end_value / start_value) ** (1 / duration_years) - 1
    """

    if duration_years <= 0:
        raise RollingReturnsValidationError(
            "duration_years must be greater than zero."
        )

    try:
        annualised_return = (
            end_value / start_value
        ) ** (1.0 / duration_years) - 1.0
    except (OverflowError, ValueError, ZeroDivisionError) as exc:
        raise RollingReturnsCalculationError(
            "Unable to calculate annualised rolling return."
        ) from exc

    if not isfinite(annualised_return):
        raise RollingReturnsCalculationError(
            "The supplied values produced a non-finite annualised return."
        )

    return annualised_return


def _select_return(
    point: RollingReturnPoint,
    *,
    annualised: bool,
) -> float:
    """
    Select the return used for summary calculations.
    """

    if annualised:
        if point.annualised_return_decimal is None:
            raise RollingReturnsCalculationError(
                "Annualised return is unavailable for a rolling period."
            )

        return point.annualised_return_decimal

    return point.total_return_decimal


# ============================================================
# Consistency Rating
# ============================================================


def classify_rolling_return_consistency(
    positive_period_frequency: float | int,
) -> RollingReturnRating:
    """
    Classify rolling-return consistency.

    Thresholds:

        Below 40%:
            poor

        40% to below 55%:
            weak

        55% to below 70%:
            moderate

        70% to below 85%:
            good

        85% and above:
            excellent

    These labels are generic analytics classifications and are not
    investment recommendations.
    """

    frequency = _validate_finite_number(
        positive_period_frequency,
        "positive_period_frequency",
    )

    if not 0.0 <= frequency <= 1.0:
        raise RollingReturnsValidationError(
            "positive_period_frequency must be between 0.0 and 1.0."
        )

    if frequency < 0.40:
        return "poor"

    if frequency < 0.55:
        return "weak"

    if frequency < 0.70:
        return "moderate"

    if frequency < 0.85:
        return "good"

    return "excellent"


# ============================================================
# Rolling Series Calculation
# ============================================================


def calculate_rolling_return_series(
    observations: Iterable[ValueObservation],
    *,
    window_size: int,
    annualise: bool = True,
) -> tuple[RollingReturnPoint, ...]:
    """
    Calculate a chronological rolling-return series.

    A window_size of 12 means each result compares an observation with the
    observation 12 positions later.

    Args:
        observations:
            Historical value observations.

        window_size:
            Number of observation intervals in each rolling period.

        annualise:
            Whether annualised return should also be calculated.

    Returns:
        Chronological tuple of RollingReturnPoint objects.
    """

    validated_observations = _validate_observations(
        observations
    )

    validated_window_size = _validate_positive_integer(
        window_size,
        "window_size",
    )

    validated_annualise = _validate_boolean(
        annualise,
        "annualise",
    )

    if validated_window_size >= len(
        validated_observations
    ):
        raise RollingReturnsValidationError(
            "window_size must be smaller than the number of observations."
        )

    rolling_points: list[RollingReturnPoint] = []

    for end_index in range(
        validated_window_size,
        len(validated_observations),
    ):
        start_index = end_index - validated_window_size

        start_observation = validated_observations[
            start_index
        ]

        end_observation = validated_observations[
            end_index
        ]

        duration_days = (
            end_observation.observation_date
            - start_observation.observation_date
        ).days

        if duration_days <= 0:
            raise RollingReturnsValidationError(
                "Rolling periods must span at least one calendar day."
            )

        duration_years = duration_days / DAYS_PER_YEAR

        total_return = _calculate_total_return(
            start_observation.value,
            end_observation.value,
        )

        annualised_return: float | None

        if validated_annualise:
            annualised_return = _calculate_annualised_return(
                start_observation.value,
                end_observation.value,
                duration_years,
            )
        else:
            annualised_return = None

        rolling_points.append(
            RollingReturnPoint(
                start_date=start_observation.observation_date,
                end_date=end_observation.observation_date,
                start_value=start_observation.value,
                end_value=end_observation.value,
                duration_days=duration_days,
                duration_years=duration_years,
                total_return_decimal=total_return,
                total_return_percent=total_return * 100.0,
                annualised_return_decimal=annualised_return,
                annualised_return_percent=(
                    annualised_return * 100.0
                    if annualised_return is not None
                    else None
                ),
            )
        )

    if not rolling_points:
        raise RollingReturnsCalculationError(
            "No rolling-return periods could be generated."
        )

    return tuple(rolling_points)


# ============================================================
# Core Rolling-Return Calculation
# ============================================================


def calculate_rolling_returns(
    input_data: RollingReturnsInput,
) -> RollingReturnsResult:
    """
    Calculate rolling-return metrics and consistency statistics.

    When annualise=True, annualised returns are used for summary metrics,
    rankings, and target comparisons. Otherwise, total-period returns are
    used.
    """

    validated_input = validate_rolling_returns_input(
        input_data
    )

    rolling_returns = calculate_rolling_return_series(
        validated_input.observations,
        window_size=validated_input.window_size,
        annualise=validated_input.annualise,
    )

    selected_returns = tuple(
        _select_return(
            point,
            annualised=validated_input.annualise,
        )
        for point in rolling_returns
    )

    if not all(
        isfinite(return_value)
        for return_value in selected_returns
    ):
        raise RollingReturnsCalculationError(
            "The rolling series contains non-finite returns."
        )

    average_return = mean(selected_returns)
    median_return = median(selected_returns)

    best_index = max(
        range(len(selected_returns)),
        key=selected_returns.__getitem__,
    )

    worst_index = min(
        range(len(selected_returns)),
        key=selected_returns.__getitem__,
    )

    best_return = selected_returns[best_index]
    worst_return = selected_returns[worst_index]

    positive_period_count = sum(
        return_value > 0.0
        for return_value in selected_returns
    )

    negative_period_count = sum(
        return_value < 0.0
        for return_value in selected_returns
    )

    zero_period_count = (
        len(selected_returns)
        - positive_period_count
        - negative_period_count
    )

    positive_period_frequency = (
        positive_period_count
        / len(selected_returns)
    )

    negative_period_frequency = (
        negative_period_count
        / len(selected_returns)
    )

    target_achieved_count: int | None
    target_achieved_frequency: float | None

    if validated_input.target_return is None:
        target_achieved_count = None
        target_achieved_frequency = None
    else:
        target_achieved_count = sum(
            return_value >= validated_input.target_return
            for return_value in selected_returns
        )

        target_achieved_frequency = (
            target_achieved_count
            / len(selected_returns)
        )

    return RollingReturnsResult(
        observation_count=len(
            validated_input.observations
        ),
        rolling_period_count=len(rolling_returns),
        window_size=validated_input.window_size,
        annualised=validated_input.annualise,
        target_return_decimal=validated_input.target_return,
        target_return_percent=(
            validated_input.target_return * 100.0
            if validated_input.target_return is not None
            else None
        ),
        average_return_decimal=average_return,
        average_return_percent=average_return * 100.0,
        median_return_decimal=median_return,
        median_return_percent=median_return * 100.0,
        best_return_decimal=best_return,
        best_return_percent=best_return * 100.0,
        worst_return_decimal=worst_return,
        worst_return_percent=worst_return * 100.0,
        positive_period_count=positive_period_count,
        negative_period_count=negative_period_count,
        zero_period_count=zero_period_count,
        positive_period_frequency=(
            positive_period_frequency
        ),
        negative_period_frequency=(
            negative_period_frequency
        ),
        target_achieved_count=target_achieved_count,
        target_achieved_frequency=(
            target_achieved_frequency
        ),
        best_period=rolling_returns[best_index],
        worst_period=rolling_returns[worst_index],
        rating=classify_rolling_return_consistency(
            positive_period_frequency
        ),
        rolling_returns=rolling_returns,
    )


# ============================================================
# Portfolio Rolling Returns
# ============================================================


def calculate_portfolio_rolling_returns(
    observations: Iterable[ValueObservation],
    *,
    window_size: int = DEFAULT_WINDOW_SIZE,
    annualise: bool = True,
    target_return: float | None = None,
) -> RollingReturnsResult:
    """
    Calculate rolling returns for the complete portfolio.

    Historical portfolio values should be retrieved through PortfolioService
    or another authorised historical-data service.
    """

    if isinstance(observations, (str, bytes)):
        raise RollingReturnsValidationError(
            "observations must be an iterable of ValueObservation instances."
        )

    try:
        observation_values = tuple(observations)
    except TypeError as exc:
        raise RollingReturnsValidationError(
            "observations must be an iterable of ValueObservation instances."
        ) from exc

    return calculate_rolling_returns(
        RollingReturnsInput(
            observations=observation_values,
            window_size=window_size,
            annualise=annualise,
            target_return=target_return,
        )
    )


# ============================================================
# Fund-Wise Rolling Returns
# ============================================================


def calculate_fund_rolling_returns(
    input_data: FundRollingReturnsInput,
) -> FundRollingReturnsResult:
    """
    Calculate rolling returns for one mutual fund.
    """

    validated_input = validate_fund_rolling_returns_input(
        input_data
    )

    result = calculate_rolling_returns(
        RollingReturnsInput(
            observations=validated_input.observations,
            window_size=validated_input.window_size,
            annualise=validated_input.annualise,
            target_return=validated_input.target_return,
        )
    )

    return FundRollingReturnsResult(
        fund_name=validated_input.fund_name,
        scheme_code=validated_input.scheme_code,
        result=result,
        source=validated_input.source,
    )


def calculate_fund_wise_rolling_returns(
    funds: Iterable[FundRollingReturnsInput],
    *,
    fail_fast: bool = False,
) -> FundRollingReturnsBatchResult:
    """
    Calculate rolling returns for multiple mutual funds.

    By default, invalid fund records are collected as failures while valid
    records continue processing.
    """

    _validate_boolean(
        fail_fast,
        "fail_fast",
    )

    if isinstance(funds, (str, bytes)):
        raise TypeError(
            "funds must be an iterable of "
            "FundRollingReturnsInput instances."
        )

    try:
        fund_records: Sequence[
            FundRollingReturnsInput
        ] = tuple(funds)
    except TypeError as exc:
        raise TypeError(
            "funds must be an iterable of "
            "FundRollingReturnsInput instances."
        ) from exc

    successful: list[FundRollingReturnsResult] = []
    failed: list[FundRollingReturnsFailure] = []

    for index, fund in enumerate(fund_records):
        if not isinstance(
            fund,
            FundRollingReturnsInput,
        ):
            error_message = (
                f"Record at index {index} must be an instance "
                "of FundRollingReturnsInput."
            )

            if fail_fast:
                raise TypeError(error_message)

            failed.append(
                FundRollingReturnsFailure(
                    fund_name=f"Unknown fund at index {index}",
                    scheme_code=None,
                    error=error_message,
                )
            )
            continue

        try:
            successful.append(
                calculate_fund_rolling_returns(fund)
            )

        except (
            RollingReturnsValidationError,
            RollingReturnsCalculationError,
            TypeError,
        ) as exc:
            if fail_fast:
                raise

            fund_name = (
                fund.fund_name.strip()
                if isinstance(fund.fund_name, str)
                and fund.fund_name.strip()
                else f"Unknown fund at index {index}"
            )

            scheme_code = (
                fund.scheme_code.strip()
                if isinstance(fund.scheme_code, str)
                and fund.scheme_code.strip()
                else None
            )

            failed.append(
                FundRollingReturnsFailure(
                    fund_name=fund_name,
                    scheme_code=scheme_code,
                    error=str(exc),
                )
            )

    return FundRollingReturnsBatchResult(
        successful=tuple(successful),
        failed=tuple(failed),
        total_received=len(fund_records),
        successful_count=len(successful),
        failed_count=len(failed),
    )


# ============================================================
# Observation Construction Utility
# ============================================================


def create_value_observations(
    values: Iterable[
        tuple[date | datetime, float | int]
    ],
) -> tuple[ValueObservation, ...]:
    """
    Convert date-value pairs into validated observations.

    Args:
        values:
            Iterable containing:
                (observation_date, value)

    Returns:
        Validated chronological ValueObservation tuple.
    """

    if isinstance(values, (str, bytes)):
        raise RollingReturnsValidationError(
            "values must be an iterable of date-value pairs."
        )

    observations: list[ValueObservation] = []

    try:
        for index, item in enumerate(values):
            if (
                not isinstance(item, tuple)
                or len(item) != 2
            ):
                raise RollingReturnsValidationError(
                    f"values[{index}] must be a two-item tuple."
                )

            observation_date, value = item

            observations.append(
                ValueObservation(
                    observation_date=observation_date,
                    value=value,
                )
            )

    except TypeError as exc:
        raise RollingReturnsValidationError(
            "values must be an iterable of date-value pairs."
        ) from exc

    return _validate_observations(observations)


# ============================================================
# Result Utility
# ============================================================


def round_rolling_returns_result(
    result: RollingReturnsResult,
    decimal_places: int = 2,
) -> RollingReturnsResult:
    """
    Return a rounded copy of a rolling-return result.

    Core calculations preserve full precision. Rounding should normally occur
    only at the presentation boundary.
    """

    if not isinstance(result, RollingReturnsResult):
        raise TypeError(
            "result must be an instance of RollingReturnsResult."
        )

    if isinstance(decimal_places, bool) or not isinstance(
        decimal_places,
        int,
    ):
        raise TypeError(
            "decimal_places must be an integer."
        )

    if decimal_places < 0:
        raise RollingReturnsValidationError(
            "decimal_places cannot be negative."
        )

    def round_optional(
        value: float | None,
    ) -> float | None:
        if value is None:
            return None

        return round(value, decimal_places)

    def round_point(
        point: RollingReturnPoint,
    ) -> RollingReturnPoint:
        return RollingReturnPoint(
            start_date=point.start_date,
            end_date=point.end_date,
            start_value=round(
                point.start_value,
                decimal_places,
            ),
            end_value=round(
                point.end_value,
                decimal_places,
            ),
            duration_days=point.duration_days,
            duration_years=round(
                point.duration_years,
                decimal_places,
            ),
            total_return_decimal=round(
                point.total_return_decimal,
                decimal_places,
            ),
            total_return_percent=round(
                point.total_return_percent,
                decimal_places,
            ),
            annualised_return_decimal=round_optional(
                point.annualised_return_decimal
            ),
            annualised_return_percent=round_optional(
                point.annualised_return_percent
            ),
        )

    rounded_series = tuple(
        round_point(point)
        for point in result.rolling_returns
    )

    best_period_index = result.rolling_returns.index(
        result.best_period
    )

    worst_period_index = result.rolling_returns.index(
        result.worst_period
    )

    return RollingReturnsResult(
        observation_count=result.observation_count,
        rolling_period_count=result.rolling_period_count,
        window_size=result.window_size,
        annualised=result.annualised,
        target_return_decimal=round_optional(
            result.target_return_decimal
        ),
        target_return_percent=round_optional(
            result.target_return_percent
        ),
        average_return_decimal=round(
            result.average_return_decimal,
            decimal_places,
        ),
        average_return_percent=round(
            result.average_return_percent,
            decimal_places,
        ),
        median_return_decimal=round(
            result.median_return_decimal,
            decimal_places,
        ),
        median_return_percent=round(
            result.median_return_percent,
            decimal_places,
        ),
        best_return_decimal=round(
            result.best_return_decimal,
            decimal_places,
        ),
        best_return_percent=round(
            result.best_return_percent,
            decimal_places,
        ),
        worst_return_decimal=round(
            result.worst_return_decimal,
            decimal_places,
        ),
        worst_return_percent=round(
            result.worst_return_percent,
            decimal_places,
        ),
        positive_period_count=result.positive_period_count,
        negative_period_count=result.negative_period_count,
        zero_period_count=result.zero_period_count,
        positive_period_frequency=round(
            result.positive_period_frequency,
            decimal_places,
        ),
        negative_period_frequency=round(
            result.negative_period_frequency,
            decimal_places,
        ),
        target_achieved_count=result.target_achieved_count,
        target_achieved_frequency=round_optional(
            result.target_achieved_frequency
        ),
        best_period=rounded_series[best_period_index],
        worst_period=rounded_series[worst_period_index],
        rating=result.rating,
        rolling_returns=rounded_series,
    )


# ============================================================
# Module Exports
# ============================================================


__all__ = [
    "DEFAULT_WINDOW_SIZE",
    "FundRollingReturnsBatchResult",
    "FundRollingReturnsFailure",
    "FundRollingReturnsInput",
    "FundRollingReturnsResult",
    "RollingReturnPoint",
    "RollingReturnRating",
    "RollingReturnsCalculationError",
    "RollingReturnsInput",
    "RollingReturnsResult",
    "RollingReturnsValidationError",
    "ValueObservation",
    "calculate_fund_rolling_returns",
    "calculate_fund_wise_rolling_returns",
    "calculate_portfolio_rolling_returns",
    "calculate_rolling_return_series",
    "calculate_rolling_returns",
    "classify_rolling_return_consistency",
    "create_value_observations",
    "round_rolling_returns_result",
    "validate_fund_rolling_returns_input",
    "validate_rolling_returns_input",
]