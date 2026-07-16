"""
Portfolio and fund drawdown analytics.

This module provides framework-independent drawdown calculations for:

- Current drawdown
- Maximum drawdown
- Peak and trough identification
- Drawdown duration
- Recovery identification
- Underwater duration
- Drawdown-series generation
- Portfolio-level drawdown
- Fund-wise drawdown
- Batch fund drawdown calculations

The module contains no Streamlit, Plotly, or pandas dependencies.

PortfolioService remains the single source of portfolio data. Historical
portfolio or fund values retrieved through PortfolioService or an authorised
market-data service should be transformed into the typed inputs defined in
this module before drawdown calculations are performed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import isfinite
from typing import Iterable, Literal, Sequence


# ============================================================
# Constants and Type Aliases
# ============================================================

MINIMUM_VALUE_OBSERVATIONS = 2

DrawdownRiskLevel = Literal[
    "very_low",
    "low",
    "moderate",
    "high",
    "very_high",
]


# ============================================================
# Exceptions
# ============================================================


class DrawdownValidationError(ValueError):
    """
    Raised when drawdown calculation inputs fail validation.
    """


class DrawdownCalculationError(RuntimeError):
    """
    Raised when drawdown metrics cannot be calculated.
    """


# ============================================================
# Input Dataclasses
# ============================================================


@dataclass(frozen=True, slots=True)
class ValueObservation:
    """
    Represents one chronological portfolio or fund value observation.

    Attributes:
        observation_date:
            Date associated with the value.

        value:
            Portfolio or fund value on the observation date.
    """

    observation_date: date | datetime
    value: float


@dataclass(frozen=True, slots=True)
class DrawdownInput:
    """
    Input model for generic or portfolio drawdown calculation.

    Attributes:
        observations:
            Chronologically sortable portfolio or fund value observations.
    """

    observations: tuple[ValueObservation, ...]


@dataclass(frozen=True, slots=True)
class FundDrawdownInput:
    """
    Input model for one mutual fund's drawdown calculation.

    Attributes:
        fund_name:
            Human-readable mutual fund name.

        observations:
            Historical fund value or NAV observations.

        scheme_code:
            Optional mutual fund scheme identifier.

        source:
            Optional description of the historical data source.
    """

    fund_name: str
    observations: tuple[ValueObservation, ...]
    scheme_code: str | None = None
    source: str | None = None


# ============================================================
# Result Dataclasses
# ============================================================


@dataclass(frozen=True, slots=True)
class DrawdownPoint:
    """
    Represents one point in a calculated drawdown series.

    Attributes:
        observation_date:
            Date associated with the observation.

        value:
            Portfolio or fund value on the date.

        running_peak:
            Highest value observed up to and including the date.

        drawdown_decimal:
            Percentage decline from the running peak as a decimal.

            Example:
                -0.20 means a 20% decline.

        drawdown_percent:
            Percentage decline from the running peak.

            Example:
                -20.0 means a 20% decline.
    """

    observation_date: date
    value: float
    running_peak: float
    drawdown_decimal: float
    drawdown_percent: float


@dataclass(frozen=True, slots=True)
class DrawdownResult:
    """
    Result of a drawdown calculation.

    Attributes:
        observation_count:
            Number of historical observations used.

        start_date:
            First observation date.

        end_date:
            Last observation date.

        starting_value:
            Value at the beginning of the series.

        ending_value:
            Value at the end of the series.

        current_peak_value:
            Running peak as of the final observation.

        current_peak_date:
            Date on which the current running peak was established.

        current_drawdown_decimal:
            Final observation's drawdown from the current peak.

        current_drawdown_percent:
            Final observation's drawdown percentage.

        maximum_drawdown_decimal:
            Largest peak-to-trough decline as a decimal.

        maximum_drawdown_percent:
            Largest peak-to-trough decline as a percentage.

        maximum_drawdown_peak_value:
            Peak value preceding the maximum drawdown trough.

        maximum_drawdown_peak_date:
            Date of the peak preceding the maximum drawdown.

        maximum_drawdown_trough_value:
            Lowest value reached during the maximum drawdown.

        maximum_drawdown_trough_date:
            Date of the maximum drawdown trough.

        maximum_drawdown_duration_days:
            Number of days from the maximum drawdown peak to its trough.

        recovery_date:
            First date after the trough on which the prior peak was regained.

        recovery_duration_days:
            Number of days from the trough to recovery.

        underwater_duration_days:
            Number of days from peak to recovery. When no recovery occurred,
            this is measured from peak to the final observation.

        recovered:
            Whether the portfolio or fund recovered to its previous peak.

        risk_level:
            Descriptive risk classification based on maximum drawdown.

        drawdown_series:
            Complete chronological drawdown series.
    """

    observation_count: int
    start_date: date
    end_date: date
    starting_value: float
    ending_value: float

    current_peak_value: float
    current_peak_date: date
    current_drawdown_decimal: float
    current_drawdown_percent: float

    maximum_drawdown_decimal: float
    maximum_drawdown_percent: float
    maximum_drawdown_peak_value: float
    maximum_drawdown_peak_date: date
    maximum_drawdown_trough_value: float
    maximum_drawdown_trough_date: date
    maximum_drawdown_duration_days: int

    recovery_date: date | None
    recovery_duration_days: int | None
    underwater_duration_days: int
    recovered: bool

    risk_level: DrawdownRiskLevel
    drawdown_series: tuple[DrawdownPoint, ...]


@dataclass(frozen=True, slots=True)
class FundDrawdownResult:
    """
    Drawdown result for one mutual fund.
    """

    fund_name: str
    scheme_code: str | None
    result: DrawdownResult
    source: str | None = None


@dataclass(frozen=True, slots=True)
class FundDrawdownFailure:
    """
    Represents a failed fund drawdown calculation.
    """

    fund_name: str
    scheme_code: str | None
    error: str


@dataclass(frozen=True, slots=True)
class FundDrawdownBatchResult:
    """
    Aggregate result from fund-wise drawdown calculations.
    """

    successful: tuple[FundDrawdownResult, ...]
    failed: tuple[FundDrawdownFailure, ...]
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
        raise DrawdownValidationError(
            f"{field_name} must be numeric and cannot be a boolean."
        )

    try:
        numeric_value = float(value)
    except (TypeError, ValueError) as exc:
        raise DrawdownValidationError(
            f"{field_name} must be a valid numeric value."
        ) from exc

    if not isfinite(numeric_value):
        raise DrawdownValidationError(
            f"{field_name} must be finite and cannot be NaN or infinite."
        )

    return numeric_value


def _validate_positive_value(
    value: float | int,
    field_name: str,
) -> float:
    """
    Validate a value that must be strictly greater than zero.
    """

    numeric_value = _validate_finite_number(
        value,
        field_name,
    )

    if numeric_value <= 0:
        raise DrawdownValidationError(
            f"{field_name} must be greater than zero."
        )

    return numeric_value


def _validate_boolean(
    value: bool,
    field_name: str,
) -> bool:
    """
    Validate a strict boolean value.
    """

    if not isinstance(value, bool):
        raise DrawdownValidationError(
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
        raise DrawdownValidationError(
            f"{field_name} must be a string."
        )

    normalised_value = value.strip()

    if not normalised_value:
        raise DrawdownValidationError(
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
        raise DrawdownValidationError(
            f"{field_name} must be a string or None."
        )

    normalised_value = value.strip()

    return normalised_value or None


# ============================================================
# Date and Observation Validation
# ============================================================


def _normalise_date(
    value: date | datetime,
    field_name: str,
) -> date:
    """
    Convert a date or datetime instance to a date.
    """

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    raise DrawdownValidationError(
        f"{field_name} must be a date or datetime instance."
    )


def _validate_observation(
    observation: ValueObservation,
    index: int,
) -> ValueObservation:
    """
    Validate and normalise one value observation.
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
    Validate, normalise, and sort historical value observations.

    Duplicate dates are rejected because multiple values for the same date
    would make drawdown sequencing ambiguous.
    """

    if isinstance(observations, (str, bytes)):
        raise DrawdownValidationError(
            "observations must be an iterable of ValueObservation instances."
        )

    try:
        normalised_observations = tuple(
            _validate_observation(
                observation,
                index,
            )
            for index, observation in enumerate(observations)
        )
    except TypeError as exc:
        if str(exc).startswith("observations["):
            raise

        raise DrawdownValidationError(
            "observations must be an iterable of ValueObservation instances."
        ) from exc

    if len(normalised_observations) < MINIMUM_VALUE_OBSERVATIONS:
        raise DrawdownValidationError(
            "At least two value observations are required."
        )

    sorted_observations = tuple(
        sorted(
            normalised_observations,
            key=lambda item: item.observation_date,
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
            raise DrawdownValidationError(
                "Duplicate observation date detected: "
                f"{current_date.isoformat()}."
            )

    return sorted_observations


# ============================================================
# Public Input Validation
# ============================================================


def validate_drawdown_input(
    input_data: DrawdownInput,
) -> DrawdownInput:
    """
    Validate and normalise generic drawdown input.
    """

    if not isinstance(input_data, DrawdownInput):
        raise TypeError(
            "input_data must be an instance of DrawdownInput."
        )

    observations = _validate_observations(
        input_data.observations
    )

    return DrawdownInput(
        observations=observations,
    )


def validate_fund_drawdown_input(
    input_data: FundDrawdownInput,
) -> FundDrawdownInput:
    """
    Validate and normalise fund-level drawdown input.
    """

    if not isinstance(input_data, FundDrawdownInput):
        raise TypeError(
            "input_data must be an instance of FundDrawdownInput."
        )

    fund_name = _validate_required_text(
        input_data.fund_name,
        "fund_name",
    )

    observations = _validate_observations(
        input_data.observations
    )

    scheme_code = _normalise_optional_text(
        input_data.scheme_code,
        "scheme_code",
    )

    source = _normalise_optional_text(
        input_data.source,
        "source",
    )

    return FundDrawdownInput(
        fund_name=fund_name,
        observations=observations,
        scheme_code=scheme_code,
        source=source,
    )


# ============================================================
# Risk Classification
# ============================================================


def classify_drawdown_risk(
    maximum_drawdown_decimal: float,
) -> DrawdownRiskLevel:
    """
    Classify maximum drawdown into a descriptive risk band.

    The function accepts either a negative drawdown or its positive
    magnitude.

    Thresholds based on absolute drawdown magnitude:

        Below 5%:
            very_low

        5% to below 10%:
            low

        10% to below 20%:
            moderate

        20% to below 35%:
            high

        35% and above:
            very_high

    These thresholds are generic analytics bands and are not investment
    recommendations.
    """

    drawdown = _validate_finite_number(
        maximum_drawdown_decimal,
        "maximum_drawdown_decimal",
    )

    magnitude = abs(drawdown)

    if magnitude < 0.05:
        return "very_low"

    if magnitude < 0.10:
        return "low"

    if magnitude < 0.20:
        return "moderate"

    if magnitude < 0.35:
        return "high"

    return "very_high"


# ============================================================
# Internal Drawdown-Series Calculation
# ============================================================


def _build_drawdown_series(
    observations: Sequence[ValueObservation],
) -> tuple[DrawdownPoint, ...]:
    """
    Build a drawdown series from already validated observations.

    This internal helper avoids validating the same observations multiple
    times during a single drawdown calculation.
    """

    if not observations:
        raise DrawdownCalculationError(
            "Cannot calculate drawdown from an empty observation sequence."
        )

    running_peak = observations[0].value
    drawdown_points: list[DrawdownPoint] = []

    for observation in observations:
        if observation.value > running_peak:
            running_peak = observation.value

        drawdown_decimal = (
            observation.value / running_peak
        ) - 1.0

        if not isfinite(drawdown_decimal):
            raise DrawdownCalculationError(
                "The supplied values produced a non-finite drawdown."
            )

        drawdown_points.append(
            DrawdownPoint(
                observation_date=observation.observation_date,
                value=observation.value,
                running_peak=running_peak,
                drawdown_decimal=drawdown_decimal,
                drawdown_percent=drawdown_decimal * 100.0,
            )
        )

    return tuple(drawdown_points)


# ============================================================
# Public Drawdown-Series API
# ============================================================


def calculate_drawdown_series(
    observations: Iterable[ValueObservation],
) -> tuple[DrawdownPoint, ...]:
    """
    Calculate a chronological drawdown series.

    Formula:
        drawdown = (current_value / running_peak) - 1

    Args:
        observations:
            Historical portfolio or fund values.

    Returns:
        Chronological tuple of DrawdownPoint instances.
    """

    validated_observations = _validate_observations(
        observations
    )

    return _build_drawdown_series(
        validated_observations
    )


# ============================================================
# Maximum Drawdown Helpers
# ============================================================


def _find_maximum_drawdown(
    observations: Sequence[ValueObservation],
) -> tuple[
    float,
    float,
    date,
    float,
    date,
]:
    """
    Identify the maximum peak-to-trough drawdown.

    Returns:
        Tuple containing:
        - Maximum drawdown decimal
        - Peak value
        - Peak date
        - Trough value
        - Trough date
    """

    running_peak_value = observations[0].value
    running_peak_date = observations[0].observation_date

    maximum_drawdown_decimal = 0.0

    maximum_peak_value = running_peak_value
    maximum_peak_date = running_peak_date

    maximum_trough_value = observations[0].value
    maximum_trough_date = observations[0].observation_date

    for observation in observations:
        if observation.value > running_peak_value:
            running_peak_value = observation.value
            running_peak_date = observation.observation_date

        drawdown_decimal = (
            observation.value / running_peak_value
        ) - 1.0

        if not isfinite(drawdown_decimal):
            raise DrawdownCalculationError(
                "Unable to calculate maximum drawdown."
            )

        if drawdown_decimal < maximum_drawdown_decimal:
            maximum_drawdown_decimal = drawdown_decimal

            maximum_peak_value = running_peak_value
            maximum_peak_date = running_peak_date

            maximum_trough_value = observation.value
            maximum_trough_date = observation.observation_date

    return (
        maximum_drawdown_decimal,
        maximum_peak_value,
        maximum_peak_date,
        maximum_trough_value,
        maximum_trough_date,
    )


def _find_recovery_date(
    observations: Sequence[ValueObservation],
    *,
    maximum_drawdown_decimal: float,
    peak_value: float,
    trough_date: date,
) -> date | None:
    """
    Find the first date after the trough when the previous peak is regained.

    A zero maximum drawdown has no recovery event because the series was
    never underwater.
    """

    if maximum_drawdown_decimal >= 0.0:
        return None

    for observation in observations:
        if observation.observation_date <= trough_date:
            continue

        if observation.value >= peak_value:
            return observation.observation_date

    return None


def _find_current_peak(
    observations: Sequence[ValueObservation],
) -> tuple[float, date]:
    """
    Find the latest running peak value and the date it was established.

    Equal values do not replace the existing peak date. This preserves the
    first date on which the current peak level was reached.
    """

    current_peak_value = observations[0].value
    current_peak_date = observations[0].observation_date

    for observation in observations:
        if observation.value > current_peak_value:
            current_peak_value = observation.value
            current_peak_date = observation.observation_date

    return current_peak_value, current_peak_date


# ============================================================
# Core Drawdown Calculation
# ============================================================


def calculate_drawdown(
    input_data: DrawdownInput,
) -> DrawdownResult:
    """
    Calculate current and maximum drawdown metrics.

    Maximum drawdown is the largest decline from a historical running peak
    to a subsequent trough.

    Args:
        input_data:
            Typed historical value observations.

    Returns:
        DrawdownResult containing current drawdown, maximum drawdown,
        duration, recovery, underwater duration, and drawdown-series metrics.

    Raises:
        TypeError:
            If input_data is not a DrawdownInput instance.

        DrawdownValidationError:
            If observations are invalid.

        DrawdownCalculationError:
            If drawdown metrics cannot be calculated.
    """

    validated_input = validate_drawdown_input(
        input_data
    )

    observations = validated_input.observations

    drawdown_series = _build_drawdown_series(
        observations
    )

    (
        maximum_drawdown_decimal,
        maximum_peak_value,
        maximum_peak_date,
        maximum_trough_value,
        maximum_trough_date,
    ) = _find_maximum_drawdown(
        observations
    )

    recovery_date = _find_recovery_date(
        observations,
        maximum_drawdown_decimal=maximum_drawdown_decimal,
        peak_value=maximum_peak_value,
        trough_date=maximum_trough_date,
    )

    recovered = recovery_date is not None

    maximum_drawdown_duration_days = (
        maximum_trough_date
        - maximum_peak_date
    ).days

    if maximum_drawdown_decimal == 0.0:
        recovery_duration_days: int | None = None
        underwater_duration_days = 0

    elif recovery_date is not None:
        recovery_duration_days = (
            recovery_date
            - maximum_trough_date
        ).days

        underwater_duration_days = (
            recovery_date
            - maximum_peak_date
        ).days

    else:
        recovery_duration_days = None

        underwater_duration_days = (
            observations[-1].observation_date
            - maximum_peak_date
        ).days

    (
        current_peak_value,
        current_peak_date,
    ) = _find_current_peak(
        observations
    )

    current_drawdown_decimal = (
        observations[-1].value
        / current_peak_value
    ) - 1.0

    if not isfinite(current_drawdown_decimal):
        raise DrawdownCalculationError(
            "Unable to calculate the current drawdown."
        )

    return DrawdownResult(
        observation_count=len(observations),
        start_date=observations[0].observation_date,
        end_date=observations[-1].observation_date,
        starting_value=observations[0].value,
        ending_value=observations[-1].value,
        current_peak_value=current_peak_value,
        current_peak_date=current_peak_date,
        current_drawdown_decimal=current_drawdown_decimal,
        current_drawdown_percent=(
            current_drawdown_decimal * 100.0
        ),
        maximum_drawdown_decimal=(
            maximum_drawdown_decimal
        ),
        maximum_drawdown_percent=(
            maximum_drawdown_decimal * 100.0
        ),
        maximum_drawdown_peak_value=(
            maximum_peak_value
        ),
        maximum_drawdown_peak_date=(
            maximum_peak_date
        ),
        maximum_drawdown_trough_value=(
            maximum_trough_value
        ),
        maximum_drawdown_trough_date=(
            maximum_trough_date
        ),
        maximum_drawdown_duration_days=(
            maximum_drawdown_duration_days
        ),
        recovery_date=recovery_date,
        recovery_duration_days=recovery_duration_days,
        underwater_duration_days=underwater_duration_days,
        recovered=recovered,
        risk_level=classify_drawdown_risk(
            maximum_drawdown_decimal
        ),
        drawdown_series=drawdown_series,
    )


# ============================================================
# Portfolio Drawdown
# ============================================================


def calculate_portfolio_drawdown(
    observations: Iterable[ValueObservation],
) -> DrawdownResult:
    """
    Calculate drawdown metrics for the complete portfolio.

    The caller should retrieve portfolio valuation history through
    PortfolioService or another authorised service before calling this
    function.
    """

    if isinstance(observations, (str, bytes)):
        raise DrawdownValidationError(
            "observations must be an iterable of ValueObservation instances."
        )

    try:
        observation_values = tuple(observations)
    except TypeError as exc:
        raise DrawdownValidationError(
            "observations must be an iterable of ValueObservation instances."
        ) from exc

    return calculate_drawdown(
        DrawdownInput(
            observations=observation_values,
        )
    )


# ============================================================
# Fund-Wise Drawdown
# ============================================================


def calculate_fund_drawdown(
    input_data: FundDrawdownInput,
) -> FundDrawdownResult:
    """
    Calculate drawdown metrics for one mutual fund.
    """

    validated_input = validate_fund_drawdown_input(
        input_data
    )

    result = calculate_drawdown(
        DrawdownInput(
            observations=validated_input.observations,
        )
    )

    return FundDrawdownResult(
        fund_name=validated_input.fund_name,
        scheme_code=validated_input.scheme_code,
        result=result,
        source=validated_input.source,
    )


def calculate_fund_wise_drawdown(
    funds: Iterable[FundDrawdownInput],
    *,
    fail_fast: bool = False,
) -> FundDrawdownBatchResult:
    """
    Calculate drawdown metrics for multiple mutual funds.

    By default, invalid funds are collected as failures while valid funds
    continue processing.

    Args:
        funds:
            Iterable of FundDrawdownInput records.

        fail_fast:
            When True, raise the first encountered error.
            When False, collect failures and continue.

    Returns:
        FundDrawdownBatchResult containing successful and failed results.
    """

    _validate_boolean(
        fail_fast,
        "fail_fast",
    )

    if isinstance(funds, (str, bytes)):
        raise TypeError(
            "funds must be an iterable of FundDrawdownInput instances."
        )

    try:
        fund_records: Sequence[FundDrawdownInput] = tuple(
            funds
        )
    except TypeError as exc:
        raise TypeError(
            "funds must be an iterable of FundDrawdownInput instances."
        ) from exc

    successful: list[FundDrawdownResult] = []
    failed: list[FundDrawdownFailure] = []

    for index, fund in enumerate(fund_records):
        if not isinstance(fund, FundDrawdownInput):
            error_message = (
                f"Record at index {index} must be an instance "
                "of FundDrawdownInput."
            )

            if fail_fast:
                raise TypeError(error_message)

            failed.append(
                FundDrawdownFailure(
                    fund_name=f"Unknown fund at index {index}",
                    scheme_code=None,
                    error=error_message,
                )
            )

            continue

        try:
            successful.append(
                calculate_fund_drawdown(fund)
            )

        except (
            DrawdownValidationError,
            DrawdownCalculationError,
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
                FundDrawdownFailure(
                    fund_name=fund_name,
                    scheme_code=scheme_code,
                    error=str(exc),
                )
            )

    return FundDrawdownBatchResult(
        successful=tuple(successful),
        failed=tuple(failed),
        total_received=len(fund_records),
        successful_count=len(successful),
        failed_count=len(failed),
    )


# ============================================================
# Value Construction Utilities
# ============================================================


def create_value_observations(
    values: Iterable[
        tuple[date | datetime, float | int]
    ],
) -> tuple[ValueObservation, ...]:
    """
    Convert date-value pairs into validated ValueObservation objects.

    Args:
        values:
            Iterable containing:
                (observation_date, value)

    Returns:
        Validated chronological ValueObservation tuple.
    """

    if isinstance(values, (str, bytes)):
        raise DrawdownValidationError(
            "values must be an iterable of date-value pairs."
        )

    observations: list[ValueObservation] = []

    try:
        for index, item in enumerate(values):
            if (
                not isinstance(item, tuple)
                or len(item) != 2
            ):
                raise DrawdownValidationError(
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
        raise DrawdownValidationError(
            "values must be an iterable of date-value pairs."
        ) from exc

    return _validate_observations(
        observations
    )


def create_indexed_value_observations(
    values: Iterable[float | int],
    *,
    start_date: date | datetime,
) -> tuple[ValueObservation, ...]:
    """
    Create observations from values when only sequential ordering is known.

    Each observation is assigned a consecutive calendar date beginning with
    start_date. This helper is intended primarily for testing or synthetic
    data. Real portfolio analytics should use actual observation dates.
    """

    normalised_start_date = _normalise_date(
        start_date,
        "start_date",
    )

    if isinstance(values, (str, bytes)):
        raise DrawdownValidationError(
            "values must be an iterable of numeric values."
        )

    try:
        observations = tuple(
            ValueObservation(
                observation_date=(
                    normalised_start_date
                    + timedelta(days=index)
                ),
                value=_validate_positive_value(
                    value,
                    f"values[{index}]",
                ),
            )
            for index, value in enumerate(values)
        )
    except TypeError as exc:
        raise DrawdownValidationError(
            "values must be an iterable of numeric values."
        ) from exc

    return _validate_observations(
        observations
    )


# ============================================================
# Result Utility
# ============================================================


def round_drawdown_result(
    result: DrawdownResult,
    decimal_places: int = 2,
) -> DrawdownResult:
    """
    Return a rounded copy of a drawdown result.

    Core calculations preserve full precision. Rounding should normally occur
    only at the presentation boundary.
    """

    if not isinstance(result, DrawdownResult):
        raise TypeError(
            "result must be an instance of DrawdownResult."
        )

    if isinstance(decimal_places, bool) or not isinstance(
        decimal_places,
        int,
    ):
        raise TypeError(
            "decimal_places must be an integer."
        )

    if decimal_places < 0:
        raise DrawdownValidationError(
            "decimal_places cannot be negative."
        )

    rounded_series = tuple(
        DrawdownPoint(
            observation_date=point.observation_date,
            value=round(
                point.value,
                decimal_places,
            ),
            running_peak=round(
                point.running_peak,
                decimal_places,
            ),
            drawdown_decimal=round(
                point.drawdown_decimal,
                decimal_places,
            ),
            drawdown_percent=round(
                point.drawdown_percent,
                decimal_places,
            ),
        )
        for point in result.drawdown_series
    )

    return DrawdownResult(
        observation_count=result.observation_count,
        start_date=result.start_date,
        end_date=result.end_date,
        starting_value=round(
            result.starting_value,
            decimal_places,
        ),
        ending_value=round(
            result.ending_value,
            decimal_places,
        ),
        current_peak_value=round(
            result.current_peak_value,
            decimal_places,
        ),
        current_peak_date=result.current_peak_date,
        current_drawdown_decimal=round(
            result.current_drawdown_decimal,
            decimal_places,
        ),
        current_drawdown_percent=round(
            result.current_drawdown_percent,
            decimal_places,
        ),
        maximum_drawdown_decimal=round(
            result.maximum_drawdown_decimal,
            decimal_places,
        ),
        maximum_drawdown_percent=round(
            result.maximum_drawdown_percent,
            decimal_places,
        ),
        maximum_drawdown_peak_value=round(
            result.maximum_drawdown_peak_value,
            decimal_places,
        ),
        maximum_drawdown_peak_date=(
            result.maximum_drawdown_peak_date
        ),
        maximum_drawdown_trough_value=round(
            result.maximum_drawdown_trough_value,
            decimal_places,
        ),
        maximum_drawdown_trough_date=(
            result.maximum_drawdown_trough_date
        ),
        maximum_drawdown_duration_days=(
            result.maximum_drawdown_duration_days
        ),
        recovery_date=result.recovery_date,
        recovery_duration_days=(
            result.recovery_duration_days
        ),
        underwater_duration_days=(
            result.underwater_duration_days
        ),
        recovered=result.recovered,
        risk_level=result.risk_level,
        drawdown_series=rounded_series,
    )


# ============================================================
# Module Exports
# ============================================================


__all__ = [
    "DrawdownCalculationError",
    "DrawdownInput",
    "DrawdownPoint",
    "DrawdownResult",
    "DrawdownRiskLevel",
    "DrawdownValidationError",
    "FundDrawdownBatchResult",
    "FundDrawdownFailure",
    "FundDrawdownInput",
    "FundDrawdownResult",
    "MINIMUM_VALUE_OBSERVATIONS",
    "ValueObservation",
    "calculate_drawdown",
    "calculate_drawdown_series",
    "calculate_fund_drawdown",
    "calculate_fund_wise_drawdown",
    "calculate_portfolio_drawdown",
    "classify_drawdown_risk",
    "create_indexed_value_observations",
    "create_value_observations",
    "round_drawdown_result",
    "validate_drawdown_input",
    "validate_fund_drawdown_input",
]