"""
Portfolio and fund volatility analytics.

This module provides framework-independent volatility calculations for:

- Periodic return volatility
- Annualised portfolio volatility
- Fund-wise annualised volatility
- Batch fund volatility calculations
- Risk classification based on annualised volatility

The module contains no Streamlit, Plotly, or pandas dependencies.

PortfolioService remains the single source of portfolio data. Data retrieved
through PortfolioService or authorised market-data services should be
transformed into the typed inputs defined in this module before volatility
calculations are performed.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from statistics import StatisticsError, stdev
from typing import Iterable, Literal, Sequence


# ============================================================
# Constants and Type Aliases
# ============================================================

DEFAULT_PERIODS_PER_YEAR = 252
MINIMUM_RETURN_OBSERVATIONS = 2

RiskLevel = Literal[
    "very_low",
    "low",
    "moderate",
    "high",
    "very_high",
]


# ============================================================
# Exceptions
# ============================================================


class VolatilityValidationError(ValueError):
    """
    Raised when volatility calculation inputs fail validation.
    """


class VolatilityCalculationError(RuntimeError):
    """
    Raised when volatility cannot be calculated from validated inputs.
    """


# ============================================================
# Input Dataclasses
# ============================================================


@dataclass(frozen=True, slots=True)
class VolatilityInput:
    """
    Input model for portfolio or generic volatility calculation.

    Attributes:
        returns:
            Periodic returns represented as decimals.

            Examples:
                0.01 means 1%.
                -0.02 means -2%.

        periods_per_year:
            Number of return periods used for annualisation.

            Common values:
                252 for daily trading returns
                52 for weekly returns
                12 for monthly returns
                4 for quarterly returns
    """

    returns: tuple[float, ...]
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR


@dataclass(frozen=True, slots=True)
class FundVolatilityInput:
    """
    Input model for one fund's volatility calculation.

    Attributes:
        fund_name:
            Human-readable mutual fund name.

        returns:
            Periodic fund returns represented as decimals.

        periods_per_year:
            Number of periods used for annualisation.

        scheme_code:
            Optional mutual fund scheme identifier.

        source:
            Optional source description for the return data.
    """

    fund_name: str
    returns: tuple[float, ...]
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR
    scheme_code: str | None = None
    source: str | None = None


# ============================================================
# Result Dataclasses
# ============================================================


@dataclass(frozen=True, slots=True)
class VolatilityResult:
    """
    Result of a volatility calculation.

    Attributes:
        observation_count:
            Number of periodic returns used.

        periods_per_year:
            Annualisation frequency.

        periodic_volatility_decimal:
            Sample standard deviation of periodic returns as a decimal.

        periodic_volatility_percent:
            Sample standard deviation of periodic returns as a percentage.

        annualised_volatility_decimal:
            Annualised volatility represented as a decimal.

        annualised_volatility_percent:
            Annualised volatility represented as a percentage.

        mean_periodic_return_decimal:
            Arithmetic mean periodic return as a decimal.

        mean_periodic_return_percent:
            Arithmetic mean periodic return as a percentage.

        minimum_return_decimal:
            Lowest periodic return.

        maximum_return_decimal:
            Highest periodic return.

        risk_level:
            Descriptive annualised volatility classification.
    """

    observation_count: int
    periods_per_year: int
    periodic_volatility_decimal: float
    periodic_volatility_percent: float
    annualised_volatility_decimal: float
    annualised_volatility_percent: float
    mean_periodic_return_decimal: float
    mean_periodic_return_percent: float
    minimum_return_decimal: float
    maximum_return_decimal: float
    risk_level: RiskLevel


@dataclass(frozen=True, slots=True)
class FundVolatilityResult:
    """
    Volatility result for one mutual fund.
    """

    fund_name: str
    scheme_code: str | None
    result: VolatilityResult
    source: str | None = None


@dataclass(frozen=True, slots=True)
class FundVolatilityFailure:
    """
    Represents a failed fund volatility calculation.
    """

    fund_name: str
    scheme_code: str | None
    error: str


@dataclass(frozen=True, slots=True)
class FundVolatilityBatchResult:
    """
    Aggregate result from fund-wise volatility calculations.
    """

    successful: tuple[FundVolatilityResult, ...]
    failed: tuple[FundVolatilityFailure, ...]
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
        raise VolatilityValidationError(
            f"{field_name} must be numeric and cannot be a boolean."
        )

    try:
        numeric_value = float(value)
    except (TypeError, ValueError) as exc:
        raise VolatilityValidationError(
            f"{field_name} must be a valid numeric value."
        ) from exc

    if not isfinite(numeric_value):
        raise VolatilityValidationError(
            f"{field_name} must be finite and cannot be NaN or infinite."
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
        raise VolatilityValidationError(
            f"{field_name} must be an integer."
        )

    if value <= 0:
        raise VolatilityValidationError(
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
        raise VolatilityValidationError(
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
        raise VolatilityValidationError(
            f"{field_name} must be a string."
        )

    normalised_value = value.strip()

    if not normalised_value:
        raise VolatilityValidationError(
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
        raise VolatilityValidationError(
            f"{field_name} must be a string or None."
        )

    normalised_value = value.strip()

    return normalised_value or None


# ============================================================
# Return Validation
# ============================================================


def _validate_returns(
    returns: Iterable[float | int],
) -> tuple[float, ...]:
    """
    Validate a sequence of periodic returns.

    At least two observations are required because this module uses sample
    standard deviation, which applies Bessel's correction.
    """

    if isinstance(returns, (str, bytes)):
        raise VolatilityValidationError(
            "returns must be an iterable of numeric values."
        )

    try:
        normalised_returns = tuple(
            _validate_finite_number(
                value,
                f"returns[{index}]",
            )
            for index, value in enumerate(returns)
        )
    except TypeError as exc:
        raise VolatilityValidationError(
            "returns must be an iterable of numeric values."
        ) from exc

    if len(normalised_returns) < MINIMUM_RETURN_OBSERVATIONS:
        raise VolatilityValidationError(
            "At least two return observations are required."
        )

    return normalised_returns


# ============================================================
# Public Input Validation
# ============================================================


def validate_volatility_input(
    input_data: VolatilityInput,
) -> VolatilityInput:
    """
    Validate and normalise generic volatility input.
    """

    if not isinstance(input_data, VolatilityInput):
        raise TypeError(
            "input_data must be an instance of VolatilityInput."
        )

    returns = _validate_returns(input_data.returns)

    periods_per_year = _validate_positive_integer(
        input_data.periods_per_year,
        "periods_per_year",
    )

    return VolatilityInput(
        returns=returns,
        periods_per_year=periods_per_year,
    )


def validate_fund_volatility_input(
    input_data: FundVolatilityInput,
) -> FundVolatilityInput:
    """
    Validate and normalise fund-level volatility input.
    """

    if not isinstance(input_data, FundVolatilityInput):
        raise TypeError(
            "input_data must be an instance of FundVolatilityInput."
        )

    fund_name = _validate_required_text(
        input_data.fund_name,
        "fund_name",
    )

    returns = _validate_returns(input_data.returns)

    periods_per_year = _validate_positive_integer(
        input_data.periods_per_year,
        "periods_per_year",
    )

    scheme_code = _normalise_optional_text(
        input_data.scheme_code,
        "scheme_code",
    )

    source = _normalise_optional_text(
        input_data.source,
        "source",
    )

    return FundVolatilityInput(
        fund_name=fund_name,
        returns=returns,
        periods_per_year=periods_per_year,
        scheme_code=scheme_code,
        source=source,
    )


# ============================================================
# Risk Classification
# ============================================================


def classify_volatility_risk(
    annualised_volatility_decimal: float,
) -> RiskLevel:
    """
    Classify annualised volatility into a descriptive risk band.

    Thresholds:
        Below 5%:
            very_low

        5% to below 10%:
            low

        10% to below 15%:
            moderate

        15% to below 25%:
            high

        25% and above:
            very_high

    These thresholds are generic analytics bands and are not investment
    recommendations.
    """

    volatility = _validate_finite_number(
        annualised_volatility_decimal,
        "annualised_volatility_decimal",
    )

    if volatility < 0:
        raise VolatilityValidationError(
            "annualised_volatility_decimal cannot be negative."
        )

    if volatility < 0.05:
        return "very_low"

    if volatility < 0.10:
        return "low"

    if volatility < 0.15:
        return "moderate"

    if volatility < 0.25:
        return "high"

    return "very_high"


# ============================================================
# Core Volatility Calculation
# ============================================================


def calculate_volatility(
    input_data: VolatilityInput,
) -> VolatilityResult:
    """
    Calculate periodic and annualised volatility.

    Formula:
        Periodic volatility =
            sample standard deviation of periodic returns

        Annualised volatility =
            periodic volatility × sqrt(periods_per_year)

    Args:
        input_data:
            Typed volatility calculation input.

    Returns:
        VolatilityResult containing periodic and annualised metrics.

    Raises:
        TypeError:
            If input_data is not a VolatilityInput instance.

        VolatilityValidationError:
            If input values are invalid.

        VolatilityCalculationError:
            If standard deviation cannot be calculated.

    Example:
        >>> result = calculate_volatility(
        ...     VolatilityInput(
        ...         returns=(0.01, -0.02, 0.015, 0.005),
        ...         periods_per_year=12,
        ...     )
        ... )
        >>> result.observation_count
        4
    """

    validated_input = validate_volatility_input(input_data)

    returns = validated_input.returns

    try:
        periodic_volatility = stdev(returns)
    except StatisticsError as exc:
        raise VolatilityCalculationError(
            "Unable to calculate volatility from the supplied returns."
        ) from exc

    if not isfinite(periodic_volatility):
        raise VolatilityCalculationError(
            "The supplied returns produced non-finite periodic volatility."
        )

    annualised_volatility = periodic_volatility * sqrt(
        validated_input.periods_per_year
    )

    if not isfinite(annualised_volatility):
        raise VolatilityCalculationError(
            "The supplied returns produced non-finite annualised volatility."
        )

    mean_return = sum(returns) / len(returns)

    if not isfinite(mean_return):
        raise VolatilityCalculationError(
            "The supplied returns produced a non-finite mean return."
        )

    risk_level = classify_volatility_risk(
        annualised_volatility
    )

    return VolatilityResult(
        observation_count=len(returns),
        periods_per_year=validated_input.periods_per_year,
        periodic_volatility_decimal=periodic_volatility,
        periodic_volatility_percent=periodic_volatility * 100.0,
        annualised_volatility_decimal=annualised_volatility,
        annualised_volatility_percent=annualised_volatility * 100.0,
        mean_periodic_return_decimal=mean_return,
        mean_periodic_return_percent=mean_return * 100.0,
        minimum_return_decimal=min(returns),
        maximum_return_decimal=max(returns),
        risk_level=risk_level,
    )


# ============================================================
# Portfolio Volatility
# ============================================================


def calculate_portfolio_volatility(
    returns: Iterable[float | int],
    *,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
) -> VolatilityResult:
    """
    Calculate volatility for the complete portfolio.

    The caller should obtain portfolio valuation history through
    PortfolioService or another authorised service and convert that history
    into periodic portfolio returns before calling this function.

    Args:
        returns:
            Periodic portfolio returns represented as decimals.

        periods_per_year:
            Number of observations used for annualisation.

    Returns:
        Portfolio volatility metrics.
    """

    if isinstance(returns, (str, bytes)):
        raise VolatilityValidationError(
            "returns must be an iterable of numeric values."
        )

    try:
        return_values = tuple(returns)
    except TypeError as exc:
        raise VolatilityValidationError(
            "returns must be an iterable of numeric values."
        ) from exc

    return calculate_volatility(
        VolatilityInput(
            returns=return_values,
            periods_per_year=periods_per_year,
        )
    )


# ============================================================
# Fund-Wise Volatility
# ============================================================


def calculate_fund_volatility(
    input_data: FundVolatilityInput,
) -> FundVolatilityResult:
    """
    Calculate annualised volatility for one fund.
    """

    validated_input = validate_fund_volatility_input(
        input_data
    )

    result = calculate_volatility(
        VolatilityInput(
            returns=validated_input.returns,
            periods_per_year=validated_input.periods_per_year,
        )
    )

    return FundVolatilityResult(
        fund_name=validated_input.fund_name,
        scheme_code=validated_input.scheme_code,
        result=result,
        source=validated_input.source,
    )


def calculate_fund_wise_volatility(
    funds: Iterable[FundVolatilityInput],
    *,
    fail_fast: bool = False,
) -> FundVolatilityBatchResult:
    """
    Calculate volatility for multiple funds.

    By default, invalid funds are collected as failures while valid funds
    continue processing.

    Args:
        funds:
            Iterable of FundVolatilityInput records.

        fail_fast:
            When True, raise the first encountered error.
            When False, collect failures and continue.

    Returns:
        FundVolatilityBatchResult containing successful and failed results.
    """

    _validate_boolean(
        fail_fast,
        "fail_fast",
    )

    if isinstance(funds, (str, bytes)):
        raise TypeError(
            "funds must be an iterable of FundVolatilityInput instances."
        )

    try:
        fund_records: Sequence[FundVolatilityInput] = tuple(funds)
    except TypeError as exc:
        raise TypeError(
            "funds must be an iterable of FundVolatilityInput instances."
        ) from exc

    successful: list[FundVolatilityResult] = []
    failed: list[FundVolatilityFailure] = []

    for index, fund in enumerate(fund_records):
        if not isinstance(fund, FundVolatilityInput):
            error_message = (
                f"Record at index {index} must be an instance "
                "of FundVolatilityInput."
            )

            if fail_fast:
                raise TypeError(error_message)

            failed.append(
                FundVolatilityFailure(
                    fund_name=f"Unknown fund at index {index}",
                    scheme_code=None,
                    error=error_message,
                )
            )
            continue

        try:
            successful.append(
                calculate_fund_volatility(fund)
            )

        except (
            VolatilityValidationError,
            VolatilityCalculationError,
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
                FundVolatilityFailure(
                    fund_name=fund_name,
                    scheme_code=scheme_code,
                    error=str(exc),
                )
            )

    return FundVolatilityBatchResult(
        successful=tuple(successful),
        failed=tuple(failed),
        total_received=len(fund_records),
        successful_count=len(successful),
        failed_count=len(failed),
    )


# ============================================================
# Return Construction Utility
# ============================================================


def calculate_periodic_returns(
    values: Iterable[float | int],
) -> tuple[float, ...]:
    """
    Convert an ordered value series into periodic percentage returns.

    Formula:
        return = (current_value / previous_value) - 1

    Args:
        values:
            Chronologically ordered portfolio or fund values.

    Returns:
        Tuple of periodic returns represented as decimals.

    Raises:
        VolatilityValidationError:
            If fewer than three values are provided, a value is invalid, or a
            previous value is zero or negative.

    Notes:
        At least three values are required to produce the minimum two return
        observations needed for sample volatility.
    """

    if isinstance(values, (str, bytes)):
        raise VolatilityValidationError(
            "values must be an iterable of numeric values."
        )

    try:
        normalised_values = tuple(
            _validate_finite_number(
                value,
                f"values[{index}]",
            )
            for index, value in enumerate(values)
        )
    except TypeError as exc:
        raise VolatilityValidationError(
            "values must be an iterable of numeric values."
        ) from exc

    if len(normalised_values) < 3:
        raise VolatilityValidationError(
            "At least three values are required to calculate volatility."
        )

    periodic_returns: list[float] = []

    for index in range(1, len(normalised_values)):
        previous_value = normalised_values[index - 1]
        current_value = normalised_values[index]

        if previous_value <= 0:
            raise VolatilityValidationError(
                f"values[{index - 1}] must be greater than zero."
            )

        periodic_return = (
            current_value / previous_value
        ) - 1.0

        if not isfinite(periodic_return):
            raise VolatilityCalculationError(
                f"Unable to calculate return for values[{index}]."
            )

        periodic_returns.append(periodic_return)

    return tuple(periodic_returns)


# ============================================================
# Result Utility
# ============================================================


def round_volatility_result(
    result: VolatilityResult,
    decimal_places: int = 2,
) -> VolatilityResult:
    """
    Return a rounded copy of a volatility result.

    Core calculations preserve full precision. Rounding should normally occur
    only at the presentation boundary.
    """

    if not isinstance(result, VolatilityResult):
        raise TypeError(
            "result must be an instance of VolatilityResult."
        )

    if isinstance(decimal_places, bool) or not isinstance(
        decimal_places,
        int,
    ):
        raise TypeError(
            "decimal_places must be an integer."
        )

    if decimal_places < 0:
        raise VolatilityValidationError(
            "decimal_places cannot be negative."
        )

    return VolatilityResult(
        observation_count=result.observation_count,
        periods_per_year=result.periods_per_year,
        periodic_volatility_decimal=round(
            result.periodic_volatility_decimal,
            decimal_places,
        ),
        periodic_volatility_percent=round(
            result.periodic_volatility_percent,
            decimal_places,
        ),
        annualised_volatility_decimal=round(
            result.annualised_volatility_decimal,
            decimal_places,
        ),
        annualised_volatility_percent=round(
            result.annualised_volatility_percent,
            decimal_places,
        ),
        mean_periodic_return_decimal=round(
            result.mean_periodic_return_decimal,
            decimal_places,
        ),
        mean_periodic_return_percent=round(
            result.mean_periodic_return_percent,
            decimal_places,
        ),
        minimum_return_decimal=round(
            result.minimum_return_decimal,
            decimal_places,
        ),
        maximum_return_decimal=round(
            result.maximum_return_decimal,
            decimal_places,
        ),
        risk_level=result.risk_level,
    )


# ============================================================
# Module Exports
# ============================================================


__all__ = [
    "DEFAULT_PERIODS_PER_YEAR",
    "FundVolatilityBatchResult",
    "FundVolatilityFailure",
    "FundVolatilityInput",
    "FundVolatilityResult",
    "RiskLevel",
    "VolatilityCalculationError",
    "VolatilityInput",
    "VolatilityResult",
    "VolatilityValidationError",
    "calculate_fund_volatility",
    "calculate_fund_wise_volatility",
    "calculate_periodic_returns",
    "calculate_portfolio_volatility",
    "calculate_volatility",
    "classify_volatility_risk",
    "round_volatility_result",
    "validate_fund_volatility_input",
    "validate_volatility_input",
]