"""
Portfolio and fund benchmark-relative analytics.

This module provides framework-independent calculations for:

- Portfolio return versus benchmark return
- Excess return
- Tracking error
- Information ratio
- Beta
- Alpha
- Correlation
- R-squared
- Upside capture ratio
- Downside capture ratio
- Portfolio-level benchmark analytics
- Fund-wise benchmark analytics
- Batch fund calculations

The module contains no Streamlit, Plotly, or pandas dependencies.

PortfolioService remains the single source of portfolio data. Historical
portfolio or fund returns and benchmark returns should be retrieved through
PortfolioService or authorised market-data services, aligned by observation
period, and transformed into the typed inputs defined in this module.
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
MINIMUM_RETURN_OBSERVATIONS = 2
ZERO_TOLERANCE = 1e-15

BenchmarkRating = Literal[
    "significantly_underperforming",
    "underperforming",
    "neutral",
    "outperforming",
    "significantly_outperforming",
]


# ============================================================
# Exceptions
# ============================================================


class BenchmarkValidationError(ValueError):
    """
    Raised when benchmark-analysis inputs fail validation.
    """


class BenchmarkCalculationError(RuntimeError):
    """
    Raised when benchmark-relative metrics cannot be calculated.
    """


# ============================================================
# Input Dataclasses
# ============================================================


@dataclass(frozen=True, slots=True)
class BenchmarkInput:
    """
    Input model for portfolio or generic benchmark-relative calculations.

    Attributes:
        portfolio_returns:
            Periodic portfolio or fund returns represented as decimals.

        benchmark_returns:
            Periodic benchmark returns represented as decimals.

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

        benchmark_name:
            Optional human-readable benchmark name.
    """

    portfolio_returns: tuple[float, ...]
    benchmark_returns: tuple[float, ...]
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR
    annual_risk_free_rate: float = DEFAULT_RISK_FREE_RATE
    benchmark_name: str | None = None


@dataclass(frozen=True, slots=True)
class FundBenchmarkInput:
    """
    Input model for one mutual fund's benchmark-relative calculations.

    Attributes:
        fund_name:
            Human-readable mutual fund name.

        fund_returns:
            Periodic mutual fund returns represented as decimals.

        benchmark_returns:
            Periodic benchmark returns represented as decimals.

        periods_per_year:
            Number of periods used for annualisation.

        annual_risk_free_rate:
            Annual risk-free rate represented as a decimal.

        benchmark_name:
            Optional human-readable benchmark name.

        scheme_code:
            Optional mutual fund scheme identifier.

        source:
            Optional description of the historical data source.
    """

    fund_name: str
    fund_returns: tuple[float, ...]
    benchmark_returns: tuple[float, ...]
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR
    annual_risk_free_rate: float = DEFAULT_RISK_FREE_RATE
    benchmark_name: str | None = None
    scheme_code: str | None = None
    source: str | None = None


# ============================================================
# Result Dataclasses
# ============================================================


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """
    Result of a benchmark-relative performance calculation.

    Attributes:
        observation_count:
            Number of aligned periodic observations.

        periods_per_year:
            Annualisation frequency.

        benchmark_name:
            Optional benchmark name.

        mean_portfolio_return_decimal:
            Arithmetic mean periodic portfolio return.

        mean_benchmark_return_decimal:
            Arithmetic mean periodic benchmark return.

        annualised_portfolio_return_decimal:
            Arithmetic annualised portfolio return.

        annualised_benchmark_return_decimal:
            Arithmetic annualised benchmark return.

        annualised_excess_return_decimal:
            Annualised portfolio return minus annualised benchmark return.

        tracking_error_decimal:
            Annualised standard deviation of active returns.

        information_ratio:
            Annualised excess return divided by tracking error.

        beta:
            Portfolio covariance with benchmark divided by benchmark variance.

        alpha_decimal:
            Annualised Jensen-style alpha.

        correlation:
            Pearson correlation between portfolio and benchmark returns.

        r_squared:
            Squared correlation.

        upside_capture_ratio:
            Portfolio performance during positive benchmark periods relative
            to benchmark performance during those periods.

        downside_capture_ratio:
            Portfolio performance during negative benchmark periods relative
            to benchmark performance during those periods.

        active_return_positive_frequency:
            Proportion of periods in which portfolio return exceeded
            benchmark return.

        best_active_return_decimal:
            Highest periodic active return.

        worst_active_return_decimal:
            Lowest periodic active return.

        rating:
            Descriptive annualised excess-return classification.
    """

    observation_count: int
    periods_per_year: int
    benchmark_name: str | None

    mean_portfolio_return_decimal: float
    mean_portfolio_return_percent: float

    mean_benchmark_return_decimal: float
    mean_benchmark_return_percent: float

    annualised_portfolio_return_decimal: float
    annualised_portfolio_return_percent: float

    annualised_benchmark_return_decimal: float
    annualised_benchmark_return_percent: float

    annualised_excess_return_decimal: float
    annualised_excess_return_percent: float

    tracking_error_decimal: float
    tracking_error_percent: float

    information_ratio: float | None
    beta: float | None

    alpha_decimal: float | None
    alpha_percent: float | None

    correlation: float | None
    r_squared: float | None

    upside_capture_ratio: float | None
    downside_capture_ratio: float | None

    active_return_positive_count: int
    active_return_negative_count: int
    active_return_zero_count: int

    active_return_positive_frequency: float
    active_return_negative_frequency: float

    best_active_return_decimal: float
    worst_active_return_decimal: float

    rating: BenchmarkRating


@dataclass(frozen=True, slots=True)
class FundBenchmarkResult:
    """
    Benchmark-relative result for one mutual fund.
    """

    fund_name: str
    scheme_code: str | None
    result: BenchmarkResult
    source: str | None = None


@dataclass(frozen=True, slots=True)
class FundBenchmarkFailure:
    """
    Represents a failed fund benchmark calculation.
    """

    fund_name: str
    scheme_code: str | None
    error: str


@dataclass(frozen=True, slots=True)
class FundBenchmarkBatchResult:
    """
    Aggregate result from fund-wise benchmark calculations.
    """

    successful: tuple[FundBenchmarkResult, ...]
    failed: tuple[FundBenchmarkFailure, ...]
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
        raise BenchmarkValidationError(
            f"{field_name} must be numeric and cannot be a boolean."
        )

    try:
        numeric_value = float(value)
    except (TypeError, ValueError) as exc:
        raise BenchmarkValidationError(
            f"{field_name} must be a valid numeric value."
        ) from exc

    if not isfinite(numeric_value):
        raise BenchmarkValidationError(
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
        raise BenchmarkValidationError(
            f"{field_name} must be an integer."
        )

    if value <= 0:
        raise BenchmarkValidationError(
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
        raise BenchmarkValidationError(
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
        raise BenchmarkValidationError(
            f"{field_name} must be a string."
        )

    normalised_value = value.strip()

    if not normalised_value:
        raise BenchmarkValidationError(
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
        raise BenchmarkValidationError(
            f"{field_name} must be a string or None."
        )

    normalised_value = value.strip()

    return normalised_value or None


# ============================================================
# Return Validation
# ============================================================


def _validate_returns(
    returns: Iterable[float | int],
    field_name: str,
) -> tuple[float, ...]:
    """
    Validate one sequence of periodic returns.
    """

    if isinstance(returns, (str, bytes)):
        raise BenchmarkValidationError(
            f"{field_name} must be an iterable of numeric values."
        )

    try:
        normalised_returns = tuple(
            _validate_finite_number(
                value,
                f"{field_name}[{index}]",
            )
            for index, value in enumerate(returns)
        )
    except TypeError as exc:
        raise BenchmarkValidationError(
            f"{field_name} must be an iterable of numeric values."
        ) from exc

    if len(normalised_returns) < MINIMUM_RETURN_OBSERVATIONS:
        raise BenchmarkValidationError(
            f"{field_name} must contain at least two observations."
        )

    return normalised_returns


def _validate_aligned_returns(
    portfolio_returns: Iterable[float | int],
    benchmark_returns: Iterable[float | int],
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """
    Validate portfolio and benchmark return sequences.

    The two sequences must contain the same number of observations because
    benchmark-relative metrics require period-by-period alignment.
    """

    normalised_portfolio_returns = _validate_returns(
        portfolio_returns,
        "portfolio_returns",
    )

    normalised_benchmark_returns = _validate_returns(
        benchmark_returns,
        "benchmark_returns",
    )

    if len(normalised_portfolio_returns) != len(
        normalised_benchmark_returns
    ):
        raise BenchmarkValidationError(
            "portfolio_returns and benchmark_returns must contain "
            "the same number of observations."
        )

    return (
        normalised_portfolio_returns,
        normalised_benchmark_returns,
    )


# ============================================================
# Public Input Validation
# ============================================================


def validate_benchmark_input(
    input_data: BenchmarkInput,
) -> BenchmarkInput:
    """
    Validate and normalise generic benchmark input.
    """

    if not isinstance(input_data, BenchmarkInput):
        raise TypeError(
            "input_data must be an instance of BenchmarkInput."
        )

    portfolio_returns, benchmark_returns = _validate_aligned_returns(
        input_data.portfolio_returns,
        input_data.benchmark_returns,
    )

    periods_per_year = _validate_positive_integer(
        input_data.periods_per_year,
        "periods_per_year",
    )

    annual_risk_free_rate = _validate_finite_number(
        input_data.annual_risk_free_rate,
        "annual_risk_free_rate",
    )

    if annual_risk_free_rate <= -1.0:
        raise BenchmarkValidationError(
            "annual_risk_free_rate must be greater than -1.0."
        )

    benchmark_name = _normalise_optional_text(
        input_data.benchmark_name,
        "benchmark_name",
    )

    return BenchmarkInput(
        portfolio_returns=portfolio_returns,
        benchmark_returns=benchmark_returns,
        periods_per_year=periods_per_year,
        annual_risk_free_rate=annual_risk_free_rate,
        benchmark_name=benchmark_name,
    )


def validate_fund_benchmark_input(
    input_data: FundBenchmarkInput,
) -> FundBenchmarkInput:
    """
    Validate and normalise fund-level benchmark input.
    """

    if not isinstance(input_data, FundBenchmarkInput):
        raise TypeError(
            "input_data must be an instance of FundBenchmarkInput."
        )

    fund_name = _validate_required_text(
        input_data.fund_name,
        "fund_name",
    )

    fund_returns, benchmark_returns = _validate_aligned_returns(
        input_data.fund_returns,
        input_data.benchmark_returns,
    )

    periods_per_year = _validate_positive_integer(
        input_data.periods_per_year,
        "periods_per_year",
    )

    annual_risk_free_rate = _validate_finite_number(
        input_data.annual_risk_free_rate,
        "annual_risk_free_rate",
    )

    if annual_risk_free_rate <= -1.0:
        raise BenchmarkValidationError(
            "annual_risk_free_rate must be greater than -1.0."
        )

    benchmark_name = _normalise_optional_text(
        input_data.benchmark_name,
        "benchmark_name",
    )

    scheme_code = _normalise_optional_text(
        input_data.scheme_code,
        "scheme_code",
    )

    source = _normalise_optional_text(
        input_data.source,
        "source",
    )

    return FundBenchmarkInput(
        fund_name=fund_name,
        fund_returns=fund_returns,
        benchmark_returns=benchmark_returns,
        periods_per_year=periods_per_year,
        annual_risk_free_rate=annual_risk_free_rate,
        benchmark_name=benchmark_name,
        scheme_code=scheme_code,
        source=source,
    )


# ============================================================
# Statistical Helpers
# ============================================================


def _sample_covariance(
    values_a: Sequence[float],
    values_b: Sequence[float],
) -> float:
    """
    Calculate sample covariance between two aligned sequences.
    """

    if len(values_a) != len(values_b):
        raise BenchmarkValidationError(
            "Covariance inputs must contain the same number of observations."
        )

    if len(values_a) < MINIMUM_RETURN_OBSERVATIONS:
        raise BenchmarkValidationError(
            "At least two observations are required for covariance."
        )

    mean_a = mean(values_a)
    mean_b = mean(values_b)

    covariance = sum(
        (value_a - mean_a) * (value_b - mean_b)
        for value_a, value_b in zip(
            values_a,
            values_b,
            strict=True,
        )
    ) / (len(values_a) - 1)

    if not isfinite(covariance):
        raise BenchmarkCalculationError(
            "The supplied returns produced non-finite covariance."
        )

    return covariance


def _sample_variance(
    values: Sequence[float],
) -> float:
    """
    Calculate sample variance.
    """

    try:
        standard_deviation = stdev(values)
    except StatisticsError as exc:
        raise BenchmarkCalculationError(
            "Unable to calculate sample variance."
        ) from exc

    variance = standard_deviation**2

    if not isfinite(variance):
        raise BenchmarkCalculationError(
            "The supplied returns produced non-finite variance."
        )

    return variance


def _calculate_correlation(
    portfolio_returns: Sequence[float],
    benchmark_returns: Sequence[float],
) -> float | None:
    """
    Calculate Pearson correlation.

    Returns None when either return series has effectively zero volatility.
    """

    try:
        portfolio_volatility = stdev(portfolio_returns)
        benchmark_volatility = stdev(benchmark_returns)
    except StatisticsError as exc:
        raise BenchmarkCalculationError(
            "Unable to calculate correlation."
        ) from exc

    if (
        abs(portfolio_volatility) <= ZERO_TOLERANCE
        or abs(benchmark_volatility) <= ZERO_TOLERANCE
    ):
        return None

    covariance = _sample_covariance(
        portfolio_returns,
        benchmark_returns,
    )

    correlation = covariance / (
        portfolio_volatility * benchmark_volatility
    )

    if not isfinite(correlation):
        raise BenchmarkCalculationError(
            "The supplied returns produced non-finite correlation."
        )

    return max(-1.0, min(1.0, correlation))


# ============================================================
# Annualisation Helpers
# ============================================================


def annualise_mean_return(
    periodic_mean_return: float | int,
    periods_per_year: int,
) -> float:
    """
    Annualise an arithmetic mean periodic return.

    Formula:
        annualised_return =
            periodic_mean_return × periods_per_year
    """

    normalised_return = _validate_finite_number(
        periodic_mean_return,
        "periodic_mean_return",
    )

    normalised_periods = _validate_positive_integer(
        periods_per_year,
        "periods_per_year",
    )

    annualised_return = normalised_return * normalised_periods

    if not isfinite(annualised_return):
        raise BenchmarkCalculationError(
            "Unable to annualise the mean periodic return."
        )

    return annualised_return


def annual_rate_to_periodic_rate(
    annual_rate: float | int,
    periods_per_year: int,
) -> float:
    """
    Convert an effective annual rate into an effective periodic rate.
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
        raise BenchmarkValidationError(
            "annual_rate must be greater than -1.0."
        )

    periodic_rate = (
        (1.0 + normalised_annual_rate)
        ** (1.0 / normalised_periods)
    ) - 1.0

    if not isfinite(periodic_rate):
        raise BenchmarkCalculationError(
            "Unable to convert annual rate to periodic rate."
        )

    return periodic_rate


# ============================================================
# Rating
# ============================================================


def classify_benchmark_performance(
    annualised_excess_return_decimal: float | int,
) -> BenchmarkRating:
    """
    Classify annualised benchmark-relative performance.

    Thresholds:
        Below -5%:
            significantly_underperforming

        -5% to below -1%:
            underperforming

        -1% to below 1%:
            neutral

        1% to below 5%:
            outperforming

        5% and above:
            significantly_outperforming

    These labels are generic analytics classifications and are not
    investment recommendations.
    """

    excess_return = _validate_finite_number(
        annualised_excess_return_decimal,
        "annualised_excess_return_decimal",
    )

    if excess_return < -0.05:
        return "significantly_underperforming"

    if excess_return < -0.01:
        return "underperforming"

    if excess_return < 0.01:
        return "neutral"

    if excess_return < 0.05:
        return "outperforming"

    return "significantly_outperforming"


# ============================================================
# Capture Ratio Helpers
# ============================================================


def _calculate_capture_ratio(
    portfolio_returns: Sequence[float],
    benchmark_returns: Sequence[float],
    *,
    positive_benchmark_periods: bool,
) -> float | None:
    """
    Calculate upside or downside capture ratio.

    The ratio compares the arithmetic mean portfolio return with the
    arithmetic mean benchmark return during selected benchmark periods.

    Returns None when no qualifying benchmark periods exist or when the mean
    benchmark return is effectively zero.
    """

    selected_pairs = tuple(
        (portfolio_return, benchmark_return)
        for portfolio_return, benchmark_return in zip(
            portfolio_returns,
            benchmark_returns,
            strict=True,
        )
        if (
            benchmark_return > 0.0
            if positive_benchmark_periods
            else benchmark_return < 0.0
        )
    )

    if not selected_pairs:
        return None

    selected_portfolio_returns = tuple(
        pair[0]
        for pair in selected_pairs
    )

    selected_benchmark_returns = tuple(
        pair[1]
        for pair in selected_pairs
    )

    mean_portfolio_return = mean(
        selected_portfolio_returns
    )

    mean_benchmark_return = mean(
        selected_benchmark_returns
    )

    if abs(mean_benchmark_return) <= ZERO_TOLERANCE:
        return None

    capture_ratio = (
        mean_portfolio_return
        / mean_benchmark_return
    ) * 100.0

    if not isfinite(capture_ratio):
        raise BenchmarkCalculationError(
            "The supplied returns produced a non-finite capture ratio."
        )

    return capture_ratio


# ============================================================
# Core Benchmark Calculation
# ============================================================


def calculate_benchmark_metrics(
    input_data: BenchmarkInput,
) -> BenchmarkResult:
    """
    Calculate benchmark-relative portfolio metrics.

    Formulas:

        Active return:
            portfolio_return - benchmark_return

        Tracking error:
            sample standard deviation of active returns
            × sqrt(periods_per_year)

        Information ratio:
            annualised excess return / tracking error

        Beta:
            covariance(portfolio, benchmark)
            / variance(benchmark)

        Alpha:
            annualised portfolio return
            - [
                annual risk-free rate
                + beta × (
                    annualised benchmark return
                    - annual risk-free rate
                )
              ]

        R-squared:
            correlation²

    Metrics whose denominators are effectively zero are returned as None
    rather than infinity.
    """

    validated_input = validate_benchmark_input(
        input_data
    )

    portfolio_returns = validated_input.portfolio_returns
    benchmark_returns = validated_input.benchmark_returns

    observation_count = len(portfolio_returns)

    mean_portfolio_return = mean(
        portfolio_returns
    )

    mean_benchmark_return = mean(
        benchmark_returns
    )

    annualised_portfolio_return = annualise_mean_return(
        mean_portfolio_return,
        validated_input.periods_per_year,
    )

    annualised_benchmark_return = annualise_mean_return(
        mean_benchmark_return,
        validated_input.periods_per_year,
    )

    annualised_excess_return = (
        annualised_portfolio_return
        - annualised_benchmark_return
    )

    active_returns = tuple(
        portfolio_return - benchmark_return
        for portfolio_return, benchmark_return in zip(
            portfolio_returns,
            benchmark_returns,
            strict=True,
        )
    )

    try:
        periodic_tracking_error = stdev(
            active_returns
        )
    except StatisticsError as exc:
        raise BenchmarkCalculationError(
            "Unable to calculate tracking error."
        ) from exc

    tracking_error = periodic_tracking_error * sqrt(
        validated_input.periods_per_year
    )

    if not isfinite(tracking_error):
        raise BenchmarkCalculationError(
            "The supplied returns produced non-finite tracking error."
        )

    information_ratio: float | None

    if abs(tracking_error) <= ZERO_TOLERANCE:
        information_ratio = None
    else:
        information_ratio = (
            annualised_excess_return
            / tracking_error
        )

        if not isfinite(information_ratio):
            raise BenchmarkCalculationError(
                "The supplied returns produced a non-finite "
                "information ratio."
            )

    benchmark_variance = _sample_variance(
        benchmark_returns
    )

    beta: float | None

    if abs(benchmark_variance) <= ZERO_TOLERANCE:
        beta = None
    else:
        covariance = _sample_covariance(
            portfolio_returns,
            benchmark_returns,
        )

        beta = covariance / benchmark_variance

        if not isfinite(beta):
            raise BenchmarkCalculationError(
                "The supplied returns produced a non-finite beta."
            )

    alpha: float | None

    if beta is None:
        alpha = None
    else:
        alpha = (
            annualised_portfolio_return
            - (
                validated_input.annual_risk_free_rate
                + beta
                * (
                    annualised_benchmark_return
                    - validated_input.annual_risk_free_rate
                )
            )
        )

        if not isfinite(alpha):
            raise BenchmarkCalculationError(
                "The supplied returns produced a non-finite alpha."
            )

    correlation = _calculate_correlation(
        portfolio_returns,
        benchmark_returns,
    )

    r_squared = (
        correlation**2
        if correlation is not None
        else None
    )

    upside_capture_ratio = _calculate_capture_ratio(
        portfolio_returns,
        benchmark_returns,
        positive_benchmark_periods=True,
    )

    downside_capture_ratio = _calculate_capture_ratio(
        portfolio_returns,
        benchmark_returns,
        positive_benchmark_periods=False,
    )

    active_return_positive_count = sum(
        active_return > 0.0
        for active_return in active_returns
    )

    active_return_negative_count = sum(
        active_return < 0.0
        for active_return in active_returns
    )

    active_return_zero_count = (
        observation_count
        - active_return_positive_count
        - active_return_negative_count
    )

    active_return_positive_frequency = (
        active_return_positive_count
        / observation_count
    )

    active_return_negative_frequency = (
        active_return_negative_count
        / observation_count
    )

    return BenchmarkResult(
        observation_count=observation_count,
        periods_per_year=validated_input.periods_per_year,
        benchmark_name=validated_input.benchmark_name,
        mean_portfolio_return_decimal=mean_portfolio_return,
        mean_portfolio_return_percent=(
            mean_portfolio_return * 100.0
        ),
        mean_benchmark_return_decimal=mean_benchmark_return,
        mean_benchmark_return_percent=(
            mean_benchmark_return * 100.0
        ),
        annualised_portfolio_return_decimal=(
            annualised_portfolio_return
        ),
        annualised_portfolio_return_percent=(
            annualised_portfolio_return * 100.0
        ),
        annualised_benchmark_return_decimal=(
            annualised_benchmark_return
        ),
        annualised_benchmark_return_percent=(
            annualised_benchmark_return * 100.0
        ),
        annualised_excess_return_decimal=(
            annualised_excess_return
        ),
        annualised_excess_return_percent=(
            annualised_excess_return * 100.0
        ),
        tracking_error_decimal=tracking_error,
        tracking_error_percent=tracking_error * 100.0,
        information_ratio=information_ratio,
        beta=beta,
        alpha_decimal=alpha,
        alpha_percent=(
            alpha * 100.0
            if alpha is not None
            else None
        ),
        correlation=correlation,
        r_squared=r_squared,
        upside_capture_ratio=upside_capture_ratio,
        downside_capture_ratio=downside_capture_ratio,
        active_return_positive_count=(
            active_return_positive_count
        ),
        active_return_negative_count=(
            active_return_negative_count
        ),
        active_return_zero_count=active_return_zero_count,
        active_return_positive_frequency=(
            active_return_positive_frequency
        ),
        active_return_negative_frequency=(
            active_return_negative_frequency
        ),
        best_active_return_decimal=max(active_returns),
        worst_active_return_decimal=min(active_returns),
        rating=classify_benchmark_performance(
            annualised_excess_return
        ),
    )


# ============================================================
# Portfolio Benchmark API
# ============================================================


def calculate_portfolio_benchmark_metrics(
    portfolio_returns: Iterable[float | int],
    benchmark_returns: Iterable[float | int],
    *,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
    annual_risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    benchmark_name: str | None = None,
) -> BenchmarkResult:
    """
    Calculate benchmark-relative metrics for the complete portfolio.

    The caller should retrieve and align historical portfolio and benchmark
    return series before calling this function.
    """

    if isinstance(portfolio_returns, (str, bytes)):
        raise BenchmarkValidationError(
            "portfolio_returns must be an iterable of numeric values."
        )

    if isinstance(benchmark_returns, (str, bytes)):
        raise BenchmarkValidationError(
            "benchmark_returns must be an iterable of numeric values."
        )

    try:
        portfolio_return_values = tuple(
            portfolio_returns
        )
    except TypeError as exc:
        raise BenchmarkValidationError(
            "portfolio_returns must be an iterable of numeric values."
        ) from exc

    try:
        benchmark_return_values = tuple(
            benchmark_returns
        )
    except TypeError as exc:
        raise BenchmarkValidationError(
            "benchmark_returns must be an iterable of numeric values."
        ) from exc

    return calculate_benchmark_metrics(
        BenchmarkInput(
            portfolio_returns=portfolio_return_values,
            benchmark_returns=benchmark_return_values,
            periods_per_year=periods_per_year,
            annual_risk_free_rate=annual_risk_free_rate,
            benchmark_name=benchmark_name,
        )
    )


# ============================================================
# Fund-Wise Benchmark API
# ============================================================


def calculate_fund_benchmark_metrics(
    input_data: FundBenchmarkInput,
) -> FundBenchmarkResult:
    """
    Calculate benchmark-relative metrics for one mutual fund.
    """

    validated_input = validate_fund_benchmark_input(
        input_data
    )

    result = calculate_benchmark_metrics(
        BenchmarkInput(
            portfolio_returns=validated_input.fund_returns,
            benchmark_returns=validated_input.benchmark_returns,
            periods_per_year=validated_input.periods_per_year,
            annual_risk_free_rate=(
                validated_input.annual_risk_free_rate
            ),
            benchmark_name=validated_input.benchmark_name,
        )
    )

    return FundBenchmarkResult(
        fund_name=validated_input.fund_name,
        scheme_code=validated_input.scheme_code,
        result=result,
        source=validated_input.source,
    )


def calculate_fund_wise_benchmark_metrics(
    funds: Iterable[FundBenchmarkInput],
    *,
    fail_fast: bool = False,
) -> FundBenchmarkBatchResult:
    """
    Calculate benchmark-relative metrics for multiple mutual funds.

    By default, invalid records are collected as failures while valid records
    continue processing.
    """

    _validate_boolean(
        fail_fast,
        "fail_fast",
    )

    if isinstance(funds, (str, bytes)):
        raise TypeError(
            "funds must be an iterable of FundBenchmarkInput instances."
        )

    try:
        fund_records: Sequence[FundBenchmarkInput] = tuple(
            funds
        )
    except TypeError as exc:
        raise TypeError(
            "funds must be an iterable of FundBenchmarkInput instances."
        ) from exc

    successful: list[FundBenchmarkResult] = []
    failed: list[FundBenchmarkFailure] = []

    for index, fund in enumerate(fund_records):
        if not isinstance(fund, FundBenchmarkInput):
            error_message = (
                f"Record at index {index} must be an instance "
                "of FundBenchmarkInput."
            )

            if fail_fast:
                raise TypeError(error_message)

            failed.append(
                FundBenchmarkFailure(
                    fund_name=f"Unknown fund at index {index}",
                    scheme_code=None,
                    error=error_message,
                )
            )
            continue

        try:
            successful.append(
                calculate_fund_benchmark_metrics(fund)
            )

        except (
            BenchmarkValidationError,
            BenchmarkCalculationError,
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
                FundBenchmarkFailure(
                    fund_name=fund_name,
                    scheme_code=scheme_code,
                    error=str(exc),
                )
            )

    return FundBenchmarkBatchResult(
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
    observations needed for benchmark-relative calculations.
    """

    if isinstance(values, (str, bytes)):
        raise BenchmarkValidationError(
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
        raise BenchmarkValidationError(
            "values must be an iterable of numeric values."
        ) from exc

    if len(normalised_values) < 3:
        raise BenchmarkValidationError(
            "At least three values are required."
        )

    periodic_returns: list[float] = []

    for index in range(1, len(normalised_values)):
        previous_value = normalised_values[index - 1]
        current_value = normalised_values[index]

        if previous_value <= 0:
            raise BenchmarkValidationError(
                f"values[{index - 1}] must be greater than zero."
            )

        periodic_return = (
            current_value / previous_value
        ) - 1.0

        if not isfinite(periodic_return):
            raise BenchmarkCalculationError(
                f"Unable to calculate return for values[{index}]."
            )

        periodic_returns.append(periodic_return)

    return tuple(periodic_returns)


# ============================================================
# Result Utility
# ============================================================


def round_benchmark_result(
    result: BenchmarkResult,
    decimal_places: int = 2,
) -> BenchmarkResult:
    """
    Return a rounded copy of a benchmark result.

    Core calculations preserve full precision. Rounding should normally occur
    only at the presentation boundary.
    """

    if not isinstance(result, BenchmarkResult):
        raise TypeError(
            "result must be an instance of BenchmarkResult."
        )

    if isinstance(decimal_places, bool) or not isinstance(
        decimal_places,
        int,
    ):
        raise TypeError(
            "decimal_places must be an integer."
        )

    if decimal_places < 0:
        raise BenchmarkValidationError(
            "decimal_places cannot be negative."
        )

    def round_optional(
        value: float | None,
    ) -> float | None:
        if value is None:
            return None

        return round(value, decimal_places)

    return BenchmarkResult(
        observation_count=result.observation_count,
        periods_per_year=result.periods_per_year,
        benchmark_name=result.benchmark_name,
        mean_portfolio_return_decimal=round(
            result.mean_portfolio_return_decimal,
            decimal_places,
        ),
        mean_portfolio_return_percent=round(
            result.mean_portfolio_return_percent,
            decimal_places,
        ),
        mean_benchmark_return_decimal=round(
            result.mean_benchmark_return_decimal,
            decimal_places,
        ),
        mean_benchmark_return_percent=round(
            result.mean_benchmark_return_percent,
            decimal_places,
        ),
        annualised_portfolio_return_decimal=round(
            result.annualised_portfolio_return_decimal,
            decimal_places,
        ),
        annualised_portfolio_return_percent=round(
            result.annualised_portfolio_return_percent,
            decimal_places,
        ),
        annualised_benchmark_return_decimal=round(
            result.annualised_benchmark_return_decimal,
            decimal_places,
        ),
        annualised_benchmark_return_percent=round(
            result.annualised_benchmark_return_percent,
            decimal_places,
        ),
        annualised_excess_return_decimal=round(
            result.annualised_excess_return_decimal,
            decimal_places,
        ),
        annualised_excess_return_percent=round(
            result.annualised_excess_return_percent,
            decimal_places,
        ),
        tracking_error_decimal=round(
            result.tracking_error_decimal,
            decimal_places,
        ),
        tracking_error_percent=round(
            result.tracking_error_percent,
            decimal_places,
        ),
        information_ratio=round_optional(
            result.information_ratio
        ),
        beta=round_optional(result.beta),
        alpha_decimal=round_optional(
            result.alpha_decimal
        ),
        alpha_percent=round_optional(
            result.alpha_percent
        ),
        correlation=round_optional(
            result.correlation
        ),
        r_squared=round_optional(
            result.r_squared
        ),
        upside_capture_ratio=round_optional(
            result.upside_capture_ratio
        ),
        downside_capture_ratio=round_optional(
            result.downside_capture_ratio
        ),
        active_return_positive_count=(
            result.active_return_positive_count
        ),
        active_return_negative_count=(
            result.active_return_negative_count
        ),
        active_return_zero_count=(
            result.active_return_zero_count
        ),
        active_return_positive_frequency=round(
            result.active_return_positive_frequency,
            decimal_places,
        ),
        active_return_negative_frequency=round(
            result.active_return_negative_frequency,
            decimal_places,
        ),
        best_active_return_decimal=round(
            result.best_active_return_decimal,
            decimal_places,
        ),
        worst_active_return_decimal=round(
            result.worst_active_return_decimal,
            decimal_places,
        ),
        rating=result.rating,
    )


# ============================================================
# Module Exports
# ============================================================


__all__ = [
    "BenchmarkCalculationError",
    "BenchmarkInput",
    "BenchmarkRating",
    "BenchmarkResult",
    "BenchmarkValidationError",
    "DEFAULT_PERIODS_PER_YEAR",
    "DEFAULT_RISK_FREE_RATE",
    "FundBenchmarkBatchResult",
    "FundBenchmarkFailure",
    "FundBenchmarkInput",
    "FundBenchmarkResult",
    "annual_rate_to_periodic_rate",
    "annualise_mean_return",
    "calculate_benchmark_metrics",
    "calculate_fund_benchmark_metrics",
    "calculate_fund_wise_benchmark_metrics",
    "calculate_periodic_returns",
    "calculate_portfolio_benchmark_metrics",
    "classify_benchmark_performance",
    "round_benchmark_result",
    "validate_benchmark_input",
    "validate_fund_benchmark_input",
]