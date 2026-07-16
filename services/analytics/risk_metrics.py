"""
Portfolio and fund risk-adjusted performance analytics.

This module provides framework-independent calculations for:

- Annualised return
- Annualised volatility
- Downside deviation
- Sharpe ratio
- Sortino ratio
- Excess return
- Positive and negative return frequency
- Portfolio-level risk metrics
- Fund-wise risk metrics
- Batch fund calculations

The module contains no Streamlit, Plotly, or pandas dependencies.

PortfolioService remains the single source of portfolio data. Historical
portfolio or fund values retrieved through PortfolioService or an authorised
market-data service should be transformed into periodic returns before the
functions in this module are called.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from statistics import StatisticsError, mean, stdev
from typing import Iterable, Literal, Sequence


# ============================================================
# Constants and Type Aliases
# ============================================================

DEFAULT_PERIODS_PER_YEAR = 252
DEFAULT_RISK_FREE_RATE = 0.0
DEFAULT_MINIMUM_ACCEPTABLE_RETURN = 0.0
MINIMUM_RETURN_OBSERVATIONS = 2
ZERO_TOLERANCE = 1e-15

RiskAdjustedRating = Literal[
    "poor",
    "weak",
    "acceptable",
    "good",
    "excellent",
]


# ============================================================
# Exceptions
# ============================================================


class RiskMetricsValidationError(ValueError):
    """
    Raised when risk-metric inputs fail validation.
    """


class RiskMetricsCalculationError(RuntimeError):
    """
    Raised when a risk-adjusted metric cannot be calculated.
    """


# ============================================================
# Input Dataclasses
# ============================================================


@dataclass(frozen=True, slots=True)
class RiskMetricsInput:
    """
    Input model for portfolio or generic risk-metric calculations.

    Attributes:
        returns:
            Periodic returns represented as decimals.

            Examples:
                0.01 means 1%.
                -0.02 means -2%.

        periods_per_year:
            Number of return periods used for annualisation.

            Common values:
                252 for daily returns
                52 for weekly returns
                12 for monthly returns
                4 for quarterly returns

        annual_risk_free_rate:
            Annual risk-free rate represented as a decimal.

            Example:
                0.07 means 7%.

        annual_minimum_acceptable_return:
            Annual target return used in Sortino-ratio and downside-deviation
            calculations.

            Example:
                0.10 means a 10% annual target.
    """

    returns: tuple[float, ...]
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR
    annual_risk_free_rate: float = DEFAULT_RISK_FREE_RATE
    annual_minimum_acceptable_return: float = (
        DEFAULT_MINIMUM_ACCEPTABLE_RETURN
    )


@dataclass(frozen=True, slots=True)
class FundRiskMetricsInput:
    """
    Input model for one mutual fund's risk-adjusted metrics.

    Attributes:
        fund_name:
            Human-readable mutual fund name.

        returns:
            Periodic fund returns represented as decimals.

        periods_per_year:
            Number of periods used for annualisation.

        annual_risk_free_rate:
            Annual risk-free rate represented as a decimal.

        annual_minimum_acceptable_return:
            Annual target return used for downside-risk calculations.

        scheme_code:
            Optional mutual fund scheme identifier.

        source:
            Optional description of the historical return source.
    """

    fund_name: str
    returns: tuple[float, ...]
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR
    annual_risk_free_rate: float = DEFAULT_RISK_FREE_RATE
    annual_minimum_acceptable_return: float = (
        DEFAULT_MINIMUM_ACCEPTABLE_RETURN
    )
    scheme_code: str | None = None
    source: str | None = None


# ============================================================
# Result Dataclasses
# ============================================================


@dataclass(frozen=True, slots=True)
class RiskMetricsResult:
    """
    Result of a risk-adjusted performance calculation.

    Attributes:
        observation_count:
            Number of periodic return observations used.

        periods_per_year:
            Annualisation frequency.

        mean_periodic_return_decimal:
            Arithmetic mean periodic return.

        mean_periodic_return_percent:
            Arithmetic mean periodic return expressed as a percentage.

        annualised_return_decimal:
            Arithmetic annualised return.

        annualised_return_percent:
            Arithmetic annualised return expressed as a percentage.

        periodic_volatility_decimal:
            Sample standard deviation of periodic returns.

        periodic_volatility_percent:
            Periodic volatility expressed as a percentage.

        annualised_volatility_decimal:
            Annualised sample volatility.

        annualised_volatility_percent:
            Annualised volatility expressed as a percentage.

        annual_risk_free_rate_decimal:
            Annual risk-free rate used in the calculation.

        annual_risk_free_rate_percent:
            Annual risk-free rate expressed as a percentage.

        annual_excess_return_decimal:
            Annualised return minus annual risk-free rate.

        annual_excess_return_percent:
            Annual excess return expressed as a percentage.

        downside_deviation_decimal:
            Annualised downside deviation relative to the minimum acceptable
            return.

        downside_deviation_percent:
            Annualised downside deviation expressed as a percentage.

        sharpe_ratio:
            Annual excess return divided by annualised volatility.

        sortino_ratio:
            Annual excess return over the minimum acceptable return divided
            by annualised downside deviation.

        positive_return_count:
            Number of periodic returns greater than zero.

        negative_return_count:
            Number of periodic returns below zero.

        zero_return_count:
            Number of periodic returns equal to zero.

        positive_return_frequency:
            Proportion of observations with positive returns.

        negative_return_frequency:
            Proportion of observations with negative returns.

        best_period_return_decimal:
            Highest periodic return.

        worst_period_return_decimal:
            Lowest periodic return.

        sharpe_rating:
            Descriptive Sharpe-ratio classification.

        sortino_rating:
            Descriptive Sortino-ratio classification.
    """

    observation_count: int
    periods_per_year: int
    mean_periodic_return_decimal: float
    mean_periodic_return_percent: float
    annualised_return_decimal: float
    annualised_return_percent: float
    periodic_volatility_decimal: float
    periodic_volatility_percent: float
    annualised_volatility_decimal: float
    annualised_volatility_percent: float
    annual_risk_free_rate_decimal: float
    annual_risk_free_rate_percent: float
    annual_minimum_acceptable_return_decimal: float
    annual_minimum_acceptable_return_percent: float
    annual_excess_return_decimal: float
    annual_excess_return_percent: float
    downside_deviation_decimal: float
    downside_deviation_percent: float
    sharpe_ratio: float | None
    sortino_ratio: float | None
    positive_return_count: int
    negative_return_count: int
    zero_return_count: int
    positive_return_frequency: float
    negative_return_frequency: float
    best_period_return_decimal: float
    worst_period_return_decimal: float
    sharpe_rating: RiskAdjustedRating | None
    sortino_rating: RiskAdjustedRating | None


@dataclass(frozen=True, slots=True)
class FundRiskMetricsResult:
    """
    Risk-adjusted performance result for one mutual fund.
    """

    fund_name: str
    scheme_code: str | None
    result: RiskMetricsResult
    source: str | None = None


@dataclass(frozen=True, slots=True)
class FundRiskMetricsFailure:
    """
    Represents a failed fund risk-metric calculation.
    """

    fund_name: str
    scheme_code: str | None
    error: str


@dataclass(frozen=True, slots=True)
class FundRiskMetricsBatchResult:
    """
    Aggregate result from fund-wise risk-metric calculations.
    """

    successful: tuple[FundRiskMetricsResult, ...]
    failed: tuple[FundRiskMetricsFailure, ...]
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
        raise RiskMetricsValidationError(
            f"{field_name} must be numeric and cannot be a boolean."
        )

    try:
        numeric_value = float(value)
    except (TypeError, ValueError) as exc:
        raise RiskMetricsValidationError(
            f"{field_name} must be a valid numeric value."
        ) from exc

    if not isfinite(numeric_value):
        raise RiskMetricsValidationError(
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
        raise RiskMetricsValidationError(
            f"{field_name} must be an integer."
        )

    if value <= 0:
        raise RiskMetricsValidationError(
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
        raise RiskMetricsValidationError(
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
        raise RiskMetricsValidationError(
            f"{field_name} must be a string."
        )

    normalised_value = value.strip()

    if not normalised_value:
        raise RiskMetricsValidationError(
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
        raise RiskMetricsValidationError(
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

    At least two observations are required because the module uses sample
    standard deviation.
    """

    if isinstance(returns, (str, bytes)):
        raise RiskMetricsValidationError(
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
        raise RiskMetricsValidationError(
            "returns must be an iterable of numeric values."
        ) from exc

    if len(normalised_returns) < MINIMUM_RETURN_OBSERVATIONS:
        raise RiskMetricsValidationError(
            "At least two return observations are required."
        )

    return normalised_returns


# ============================================================
# Public Input Validation
# ============================================================


def validate_risk_metrics_input(
    input_data: RiskMetricsInput,
) -> RiskMetricsInput:
    """
    Validate and normalise generic risk-metric input.
    """

    if not isinstance(input_data, RiskMetricsInput):
        raise TypeError(
            "input_data must be an instance of RiskMetricsInput."
        )

    returns = _validate_returns(input_data.returns)

    periods_per_year = _validate_positive_integer(
        input_data.periods_per_year,
        "periods_per_year",
    )

    annual_risk_free_rate = _validate_finite_number(
        input_data.annual_risk_free_rate,
        "annual_risk_free_rate",
    )

    annual_minimum_acceptable_return = _validate_finite_number(
        input_data.annual_minimum_acceptable_return,
        "annual_minimum_acceptable_return",
    )

    if annual_risk_free_rate <= -1.0:
        raise RiskMetricsValidationError(
            "annual_risk_free_rate must be greater than -1.0."
        )

    if annual_minimum_acceptable_return <= -1.0:
        raise RiskMetricsValidationError(
            "annual_minimum_acceptable_return must be greater than -1.0."
        )

    return RiskMetricsInput(
        returns=returns,
        periods_per_year=periods_per_year,
        annual_risk_free_rate=annual_risk_free_rate,
        annual_minimum_acceptable_return=(
            annual_minimum_acceptable_return
        ),
    )


def validate_fund_risk_metrics_input(
    input_data: FundRiskMetricsInput,
) -> FundRiskMetricsInput:
    """
    Validate and normalise fund-level risk-metric input.
    """

    if not isinstance(input_data, FundRiskMetricsInput):
        raise TypeError(
            "input_data must be an instance of FundRiskMetricsInput."
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

    annual_risk_free_rate = _validate_finite_number(
        input_data.annual_risk_free_rate,
        "annual_risk_free_rate",
    )

    annual_minimum_acceptable_return = _validate_finite_number(
        input_data.annual_minimum_acceptable_return,
        "annual_minimum_acceptable_return",
    )

    if annual_risk_free_rate <= -1.0:
        raise RiskMetricsValidationError(
            "annual_risk_free_rate must be greater than -1.0."
        )

    if annual_minimum_acceptable_return <= -1.0:
        raise RiskMetricsValidationError(
            "annual_minimum_acceptable_return must be greater than -1.0."
        )

    scheme_code = _normalise_optional_text(
        input_data.scheme_code,
        "scheme_code",
    )

    source = _normalise_optional_text(
        input_data.source,
        "source",
    )

    return FundRiskMetricsInput(
        fund_name=fund_name,
        returns=returns,
        periods_per_year=periods_per_year,
        annual_risk_free_rate=annual_risk_free_rate,
        annual_minimum_acceptable_return=(
            annual_minimum_acceptable_return
        ),
        scheme_code=scheme_code,
        source=source,
    )


# ============================================================
# Rate Conversion Utilities
# ============================================================


def annual_rate_to_periodic_rate(
    annual_rate: float | int,
    periods_per_year: int,
) -> float:
    """
    Convert an effective annual rate into an effective periodic rate.

    Formula:
        periodic_rate =
            (1 + annual_rate) ** (1 / periods_per_year) - 1
    """

    normalised_annual_rate = _validate_finite_number(
        annual_rate,
        "annual_rate",
    )

    normalised_periods = _validate_positive_integer(
        periods_per_year,
        "periods_per_year",
    )

    if normalised_annual_rate <= -1.0:
        raise RiskMetricsValidationError(
            "annual_rate must be greater than -1.0."
        )

    periodic_rate = (
        (1.0 + normalised_annual_rate)
        ** (1.0 / normalised_periods)
    ) - 1.0

    if not isfinite(periodic_rate):
        raise RiskMetricsCalculationError(
            "Unable to convert annual rate to a periodic rate."
        )

    return periodic_rate


def annualise_periodic_return(
    periodic_return: float | int,
    periods_per_year: int,
) -> float:
    """
    Arithmetic annualisation of a periodic mean return.

    Formula:
        annualised_return =
            periodic_return × periods_per_year

    This arithmetic method is consistent with standard Sharpe-ratio
    annualisation.
    """

    normalised_return = _validate_finite_number(
        periodic_return,
        "periodic_return",
    )

    normalised_periods = _validate_positive_integer(
        periods_per_year,
        "periods_per_year",
    )

    annualised_return = normalised_return * normalised_periods

    if not isfinite(annualised_return):
        raise RiskMetricsCalculationError(
            "Unable to annualise the periodic return."
        )

    return annualised_return


# ============================================================
# Ratio Classification
# ============================================================


def classify_risk_adjusted_ratio(
    ratio: float | int,
) -> RiskAdjustedRating:
    """
    Classify a Sharpe or Sortino ratio.

    Thresholds:
        Below 0:
            poor

        0 to below 0.5:
            weak

        0.5 to below 1.0:
            acceptable

        1.0 to below 2.0:
            good

        2.0 and above:
            excellent

    These classifications are generic analytics labels and are not
    investment recommendations.
    """

    normalised_ratio = _validate_finite_number(
        ratio,
        "ratio",
    )

    if normalised_ratio < 0.0:
        return "poor"

    if normalised_ratio < 0.5:
        return "weak"

    if normalised_ratio < 1.0:
        return "acceptable"

    if normalised_ratio < 2.0:
        return "good"

    return "excellent"


# ============================================================
# Downside Deviation
# ============================================================


def calculate_downside_deviation(
    returns: Iterable[float | int],
    *,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
    annual_minimum_acceptable_return: float = (
        DEFAULT_MINIMUM_ACCEPTABLE_RETURN
    ),
) -> float:
    """
    Calculate annualised downside deviation.

    Only returns below the periodic minimum acceptable return contribute to
    downside deviation.

    Formula:
        downside_difference =
            min(periodic_return - periodic_target, 0)

        periodic_downside_deviation =
            sqrt(mean(downside_difference²))

        annualised_downside_deviation =
            periodic_downside_deviation × sqrt(periods_per_year)

    The denominator is the full observation count rather than only the number
    of negative deviations.
    """

    normalised_returns = _validate_returns(returns)

    normalised_periods = _validate_positive_integer(
        periods_per_year,
        "periods_per_year",
    )

    periodic_target = annual_rate_to_periodic_rate(
        annual_minimum_acceptable_return,
        normalised_periods,
    )

    squared_downside_differences = tuple(
        min(periodic_return - periodic_target, 0.0) ** 2
        for periodic_return in normalised_returns
    )

    mean_squared_downside = (
        sum(squared_downside_differences)
        / len(squared_downside_differences)
    )

    periodic_downside_deviation = sqrt(
        mean_squared_downside
    )

    annualised_downside_deviation = (
        periodic_downside_deviation
        * sqrt(normalised_periods)
    )

    if not isfinite(annualised_downside_deviation):
        raise RiskMetricsCalculationError(
            "The supplied returns produced non-finite downside deviation."
        )

    return annualised_downside_deviation


# ============================================================
# Core Risk-Metric Calculation
# ============================================================


def calculate_risk_metrics(
    input_data: RiskMetricsInput,
) -> RiskMetricsResult:
    """
    Calculate annualised return, volatility, Sharpe ratio, and Sortino ratio.

    Sharpe ratio:
        (annualised return - annual risk-free rate)
        / annualised volatility

    Sortino ratio:
        (annualised return - annual minimum acceptable return)
        / annualised downside deviation

    When the relevant denominator is effectively zero, the corresponding
    ratio is returned as None rather than infinity.
    """

    validated_input = validate_risk_metrics_input(
        input_data
    )

    returns = validated_input.returns
    observation_count = len(returns)

    mean_periodic_return = mean(returns)

    try:
        periodic_volatility = stdev(returns)
    except StatisticsError as exc:
        raise RiskMetricsCalculationError(
            "Unable to calculate volatility from the supplied returns."
        ) from exc

    annualised_return = annualise_periodic_return(
        mean_periodic_return,
        validated_input.periods_per_year,
    )

    annualised_volatility = periodic_volatility * sqrt(
        validated_input.periods_per_year
    )

    annual_excess_return = (
        annualised_return
        - validated_input.annual_risk_free_rate
    )

    downside_deviation = calculate_downside_deviation(
        returns,
        periods_per_year=validated_input.periods_per_year,
        annual_minimum_acceptable_return=(
            validated_input.annual_minimum_acceptable_return
        ),
    )

    if not all(
        isfinite(value)
        for value in (
            mean_periodic_return,
            periodic_volatility,
            annualised_return,
            annualised_volatility,
            annual_excess_return,
            downside_deviation,
        )
    ):
        raise RiskMetricsCalculationError(
            "The supplied returns produced non-finite risk metrics."
        )

    sharpe_ratio: float | None

    if abs(annualised_volatility) <= ZERO_TOLERANCE:
        sharpe_ratio = None
    else:
        sharpe_ratio = (
            annual_excess_return
            / annualised_volatility
        )

        if not isfinite(sharpe_ratio):
            raise RiskMetricsCalculationError(
                "The supplied values produced a non-finite Sharpe ratio."
            )

    sortino_excess_return = (
        annualised_return
        - validated_input.annual_minimum_acceptable_return
    )

    sortino_ratio: float | None

    if abs(downside_deviation) <= ZERO_TOLERANCE:
        sortino_ratio = None
    else:
        sortino_ratio = (
            sortino_excess_return
            / downside_deviation
        )

        if not isfinite(sortino_ratio):
            raise RiskMetricsCalculationError(
                "The supplied values produced a non-finite Sortino ratio."
            )

    positive_return_count = sum(
        periodic_return > 0.0
        for periodic_return in returns
    )

    negative_return_count = sum(
        periodic_return < 0.0
        for periodic_return in returns
    )

    zero_return_count = (
        observation_count
        - positive_return_count
        - negative_return_count
    )

    positive_return_frequency = (
        positive_return_count / observation_count
    )

    negative_return_frequency = (
        negative_return_count / observation_count
    )

    sharpe_rating = (
        classify_risk_adjusted_ratio(sharpe_ratio)
        if sharpe_ratio is not None
        else None
    )

    sortino_rating = (
        classify_risk_adjusted_ratio(sortino_ratio)
        if sortino_ratio is not None
        else None
    )

    return RiskMetricsResult(
        observation_count=observation_count,
        periods_per_year=validated_input.periods_per_year,
        mean_periodic_return_decimal=mean_periodic_return,
        mean_periodic_return_percent=mean_periodic_return * 100.0,
        annualised_return_decimal=annualised_return,
        annualised_return_percent=annualised_return * 100.0,
        periodic_volatility_decimal=periodic_volatility,
        periodic_volatility_percent=periodic_volatility * 100.0,
        annualised_volatility_decimal=annualised_volatility,
        annualised_volatility_percent=annualised_volatility * 100.0,
        annual_risk_free_rate_decimal=(
            validated_input.annual_risk_free_rate
        ),
        annual_risk_free_rate_percent=(
            validated_input.annual_risk_free_rate * 100.0
        ),
        annual_minimum_acceptable_return_decimal=(
            validated_input.annual_minimum_acceptable_return
        ),
        annual_minimum_acceptable_return_percent=(
            validated_input.annual_minimum_acceptable_return
            * 100.0
        ),
        annual_excess_return_decimal=annual_excess_return,
        annual_excess_return_percent=annual_excess_return * 100.0,
        downside_deviation_decimal=downside_deviation,
        downside_deviation_percent=downside_deviation * 100.0,
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=sortino_ratio,
        positive_return_count=positive_return_count,
        negative_return_count=negative_return_count,
        zero_return_count=zero_return_count,
        positive_return_frequency=positive_return_frequency,
        negative_return_frequency=negative_return_frequency,
        best_period_return_decimal=max(returns),
        worst_period_return_decimal=min(returns),
        sharpe_rating=sharpe_rating,
        sortino_rating=sortino_rating,
    )


# ============================================================
# Portfolio Risk Metrics
# ============================================================


def calculate_portfolio_risk_metrics(
    returns: Iterable[float | int],
    *,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
    annual_risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    annual_minimum_acceptable_return: float = (
        DEFAULT_MINIMUM_ACCEPTABLE_RETURN
    ),
) -> RiskMetricsResult:
    """
    Calculate risk-adjusted metrics for the complete portfolio.

    The caller should obtain portfolio valuation history through
    PortfolioService or another authorised service and convert it into
    periodic portfolio returns before calling this function.
    """

    if isinstance(returns, (str, bytes)):
        raise RiskMetricsValidationError(
            "returns must be an iterable of numeric values."
        )

    try:
        return_values = tuple(returns)
    except TypeError as exc:
        raise RiskMetricsValidationError(
            "returns must be an iterable of numeric values."
        ) from exc

    return calculate_risk_metrics(
        RiskMetricsInput(
            returns=return_values,
            periods_per_year=periods_per_year,
            annual_risk_free_rate=annual_risk_free_rate,
            annual_minimum_acceptable_return=(
                annual_minimum_acceptable_return
            ),
        )
    )


# ============================================================
# Fund-Wise Risk Metrics
# ============================================================


def calculate_fund_risk_metrics(
    input_data: FundRiskMetricsInput,
) -> FundRiskMetricsResult:
    """
    Calculate risk-adjusted performance metrics for one mutual fund.
    """

    validated_input = validate_fund_risk_metrics_input(
        input_data
    )

    result = calculate_risk_metrics(
        RiskMetricsInput(
            returns=validated_input.returns,
            periods_per_year=validated_input.periods_per_year,
            annual_risk_free_rate=(
                validated_input.annual_risk_free_rate
            ),
            annual_minimum_acceptable_return=(
                validated_input.annual_minimum_acceptable_return
            ),
        )
    )

    return FundRiskMetricsResult(
        fund_name=validated_input.fund_name,
        scheme_code=validated_input.scheme_code,
        result=result,
        source=validated_input.source,
    )


def calculate_fund_wise_risk_metrics(
    funds: Iterable[FundRiskMetricsInput],
    *,
    fail_fast: bool = False,
) -> FundRiskMetricsBatchResult:
    """
    Calculate risk-adjusted metrics for multiple mutual funds.

    By default, invalid fund records are collected as failures while valid
    records continue processing.
    """

    _validate_boolean(
        fail_fast,
        "fail_fast",
    )

    if isinstance(funds, (str, bytes)):
        raise TypeError(
            "funds must be an iterable of FundRiskMetricsInput instances."
        )

    try:
        fund_records: Sequence[FundRiskMetricsInput] = tuple(funds)
    except TypeError as exc:
        raise TypeError(
            "funds must be an iterable of FundRiskMetricsInput instances."
        ) from exc

    successful: list[FundRiskMetricsResult] = []
    failed: list[FundRiskMetricsFailure] = []

    for index, fund in enumerate(fund_records):
        if not isinstance(fund, FundRiskMetricsInput):
            error_message = (
                f"Record at index {index} must be an instance "
                "of FundRiskMetricsInput."
            )

            if fail_fast:
                raise TypeError(error_message)

            failed.append(
                FundRiskMetricsFailure(
                    fund_name=f"Unknown fund at index {index}",
                    scheme_code=None,
                    error=error_message,
                )
            )
            continue

        try:
            successful.append(
                calculate_fund_risk_metrics(fund)
            )

        except (
            RiskMetricsValidationError,
            RiskMetricsCalculationError,
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
                FundRiskMetricsFailure(
                    fund_name=fund_name,
                    scheme_code=scheme_code,
                    error=str(exc),
                )
            )

    return FundRiskMetricsBatchResult(
        successful=tuple(successful),
        failed=tuple(failed),
        total_received=len(fund_records),
        successful_count=len(successful),
        failed_count=len(failed),
    )


# ============================================================
# Value-to-Return Utility
# ============================================================


def calculate_periodic_returns(
    values: Iterable[float | int],
) -> tuple[float, ...]:
    """
    Convert a chronological value series into periodic returns.

    Formula:
        return = (current_value / previous_value) - 1

    At least three values are required to generate the minimum two return
    observations needed for sample volatility and risk-adjusted metrics.
    """

    if isinstance(values, (str, bytes)):
        raise RiskMetricsValidationError(
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
        raise RiskMetricsValidationError(
            "values must be an iterable of numeric values."
        ) from exc

    if len(normalised_values) < 3:
        raise RiskMetricsValidationError(
            "At least three values are required."
        )

    periodic_returns: list[float] = []

    for index in range(1, len(normalised_values)):
        previous_value = normalised_values[index - 1]
        current_value = normalised_values[index]

        if previous_value <= 0:
            raise RiskMetricsValidationError(
                f"values[{index - 1}] must be greater than zero."
            )

        periodic_return = (
            current_value / previous_value
        ) - 1.0

        if not isfinite(periodic_return):
            raise RiskMetricsCalculationError(
                f"Unable to calculate return for values[{index}]."
            )

        periodic_returns.append(periodic_return)

    return tuple(periodic_returns)


# ============================================================
# Result Utility
# ============================================================


def round_risk_metrics_result(
    result: RiskMetricsResult,
    decimal_places: int = 2,
) -> RiskMetricsResult:
    """
    Return a rounded copy of a risk-metric result.

    Core calculations preserve full precision. Rounding should normally occur
    only at the presentation boundary.
    """

    if not isinstance(result, RiskMetricsResult):
        raise TypeError(
            "result must be an instance of RiskMetricsResult."
        )

    if isinstance(decimal_places, bool) or not isinstance(
        decimal_places,
        int,
    ):
        raise TypeError(
            "decimal_places must be an integer."
        )

    if decimal_places < 0:
        raise RiskMetricsValidationError(
            "decimal_places cannot be negative."
        )

    def round_optional(value: float | None) -> float | None:
        if value is None:
            return None

        return round(value, decimal_places)

    return RiskMetricsResult(
        observation_count=result.observation_count,
        periods_per_year=result.periods_per_year,
        mean_periodic_return_decimal=round(
            result.mean_periodic_return_decimal,
            decimal_places,
        ),
        mean_periodic_return_percent=round(
            result.mean_periodic_return_percent,
            decimal_places,
        ),
        annualised_return_decimal=round(
            result.annualised_return_decimal,
            decimal_places,
        ),
        annualised_return_percent=round(
            result.annualised_return_percent,
            decimal_places,
        ),
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
        annual_risk_free_rate_decimal=round(
            result.annual_risk_free_rate_decimal,
            decimal_places,
        ),
        annual_risk_free_rate_percent=round(
            result.annual_risk_free_rate_percent,
            decimal_places,
        ),
        annual_minimum_acceptable_return_decimal=round(
            result.annual_minimum_acceptable_return_decimal,
            decimal_places,
        ),
        annual_minimum_acceptable_return_percent=round(
            result.annual_minimum_acceptable_return_percent,
            decimal_places,
        ),
        annual_excess_return_decimal=round(
            result.annual_excess_return_decimal,
            decimal_places,
        ),
        annual_excess_return_percent=round(
            result.annual_excess_return_percent,
            decimal_places,
        ),
        downside_deviation_decimal=round(
            result.downside_deviation_decimal,
            decimal_places,
        ),
        downside_deviation_percent=round(
            result.downside_deviation_percent,
            decimal_places,
        ),
        sharpe_ratio=round_optional(result.sharpe_ratio),
        sortino_ratio=round_optional(result.sortino_ratio),
        positive_return_count=result.positive_return_count,
        negative_return_count=result.negative_return_count,
        zero_return_count=result.zero_return_count,
        positive_return_frequency=round(
            result.positive_return_frequency,
            decimal_places,
        ),
        negative_return_frequency=round(
            result.negative_return_frequency,
            decimal_places,
        ),
        best_period_return_decimal=round(
            result.best_period_return_decimal,
            decimal_places,
        ),
        worst_period_return_decimal=round(
            result.worst_period_return_decimal,
            decimal_places,
        ),
        sharpe_rating=result.sharpe_rating,
        sortino_rating=result.sortino_rating,
    )


# ============================================================
# Module Exports
# ============================================================


__all__ = [
    "DEFAULT_MINIMUM_ACCEPTABLE_RETURN",
    "DEFAULT_PERIODS_PER_YEAR",
    "DEFAULT_RISK_FREE_RATE",
    "FundRiskMetricsBatchResult",
    "FundRiskMetricsFailure",
    "FundRiskMetricsInput",
    "FundRiskMetricsResult",
    "RiskAdjustedRating",
    "RiskMetricsCalculationError",
    "RiskMetricsInput",
    "RiskMetricsResult",
    "RiskMetricsValidationError",
    "annual_rate_to_periodic_rate",
    "annualise_periodic_return",
    "calculate_downside_deviation",
    "calculate_fund_risk_metrics",
    "calculate_fund_wise_risk_metrics",
    "calculate_periodic_returns",
    "calculate_portfolio_risk_metrics",
    "calculate_risk_metrics",
    "classify_risk_adjusted_ratio",
    "round_risk_metrics_result",
    "validate_fund_risk_metrics_input",
    "validate_risk_metrics_input",
]