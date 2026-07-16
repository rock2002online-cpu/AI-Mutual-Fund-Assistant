"""
Tests for services.analytics.benchmark.

These tests validate:

- Mean and annualised benchmark-relative returns
- Active returns
- Tracking error
- Information ratio
- Beta
- Alpha
- Correlation
- R-squared
- Upside capture ratio
- Downside capture ratio
- Portfolio benchmark metrics
- Fund-wise benchmark metrics
- Batch processing
- Defensive validation
- Value-to-return conversion
- Result rounding
- Immutable dataclasses
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from math import sqrt
from statistics import mean, stdev

import pytest

from services.analytics.benchmark import (
    BenchmarkInput,
    BenchmarkResult,
    BenchmarkValidationError,
    FundBenchmarkInput,
    annual_rate_to_periodic_rate,
    annualise_mean_return,
    calculate_benchmark_metrics,
    calculate_fund_benchmark_metrics,
    calculate_fund_wise_benchmark_metrics,
    calculate_periodic_returns,
    calculate_portfolio_benchmark_metrics,
    classify_benchmark_performance,
    round_benchmark_result,
    validate_benchmark_input,
    validate_fund_benchmark_input,
)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def portfolio_returns() -> tuple[float, ...]:
    """
    Return a representative monthly portfolio return sequence.
    """

    return (
        0.025,
        -0.010,
        0.020,
        0.005,
        -0.015,
        0.030,
        0.012,
        -0.004,
    )


@pytest.fixture
def benchmark_returns() -> tuple[float, ...]:
    """
    Return an aligned monthly benchmark return sequence.
    """

    return (
        0.020,
        -0.012,
        0.015,
        0.008,
        -0.020,
        0.025,
        0.010,
        -0.006,
    )


@pytest.fixture
def standard_input(
    portfolio_returns: tuple[float, ...],
    benchmark_returns: tuple[float, ...],
) -> BenchmarkInput:
    """
    Return a valid benchmark-analysis input.
    """

    return BenchmarkInput(
        portfolio_returns=portfolio_returns,
        benchmark_returns=benchmark_returns,
        periods_per_year=12,
        annual_risk_free_rate=0.06,
        benchmark_name="Nifty 50 TRI",
    )


@pytest.fixture
def standard_fund_input(
    portfolio_returns: tuple[float, ...],
    benchmark_returns: tuple[float, ...],
) -> FundBenchmarkInput:
    """
    Return a valid fund-level benchmark input.
    """

    return FundBenchmarkInput(
        fund_name="UTI Nifty 50 Index Fund",
        fund_returns=portfolio_returns,
        benchmark_returns=benchmark_returns,
        periods_per_year=12,
        annual_risk_free_rate=0.06,
        benchmark_name="Nifty 50 TRI",
        scheme_code="120716",
        source="Unit test",
    )


# ============================================================
# Annualisation Utility Tests
# ============================================================


def test_annualise_mean_return() -> None:
    """
    Arithmetic annualisation should multiply by periods per year.
    """

    result = annualise_mean_return(
        0.01,
        12,
    )

    assert result == pytest.approx(0.12)


def test_annualise_negative_mean_return() -> None:
    """
    Negative periodic returns should annualise correctly.
    """

    result = annualise_mean_return(
        -0.01,
        12,
    )

    assert result == pytest.approx(-0.12)


@pytest.mark.parametrize(
    "periods_per_year",
    [
        0,
        -1,
        True,
        12.5,
        "12",
    ],
)
def test_annualise_mean_return_rejects_invalid_periods(
    periods_per_year: object,
) -> None:
    """
    periods_per_year must be a strict positive integer.
    """

    with pytest.raises(BenchmarkValidationError):
        annualise_mean_return(
            0.01,
            periods_per_year,  # type: ignore[arg-type]
        )


def test_annual_rate_to_periodic_rate() -> None:
    """
    Effective annual rate should convert to an effective periodic rate.
    """

    result = annual_rate_to_periodic_rate(
        0.12,
        12,
    )

    expected = (1.12 ** (1.0 / 12.0)) - 1.0

    assert result == pytest.approx(
        expected,
        rel=1e-12,
    )


def test_annual_rate_to_periodic_rate_zero() -> None:
    """
    Zero annual rate should produce zero periodic rate.
    """

    assert annual_rate_to_periodic_rate(
        0.0,
        12,
    ) == pytest.approx(0.0)


@pytest.mark.parametrize(
    "annual_rate",
    [
        -1.0,
        -2.0,
    ],
)
def test_annual_rate_to_periodic_rate_rejects_invalid_rate(
    annual_rate: float,
) -> None:
    """
    Annual rate must remain greater than negative one.
    """

    with pytest.raises(
        BenchmarkValidationError,
        match="annual_rate must be greater than -1.0",
    ):
        annual_rate_to_periodic_rate(
            annual_rate,
            12,
        )


# ============================================================
# Performance Classification Tests
# ============================================================


@pytest.mark.parametrize(
    ("excess_return", "expected_rating"),
    [
        (-0.10, "significantly_underperforming"),
        (-0.0501, "significantly_underperforming"),
        (-0.05, "underperforming"),
        (-0.0101, "underperforming"),
        (-0.01, "neutral"),
        (0.0, "neutral"),
        (0.0099, "neutral"),
        (0.01, "outperforming"),
        (0.0499, "outperforming"),
        (0.05, "significantly_outperforming"),
        (0.10, "significantly_outperforming"),
    ],
)
def test_classify_benchmark_performance(
    excess_return: float,
    expected_rating: str,
) -> None:
    """
    Annualised excess return should map to the expected rating.
    """

    assert classify_benchmark_performance(
        excess_return
    ) == expected_rating


@pytest.mark.parametrize(
    "invalid_value",
    [
        True,
        float("nan"),
        float("inf"),
        "invalid",
    ],
)
def test_classify_benchmark_performance_rejects_invalid_values(
    invalid_value: object,
) -> None:
    """
    Classification should reject invalid numeric values.
    """

    with pytest.raises(BenchmarkValidationError):
        classify_benchmark_performance(  # type: ignore[arg-type]
            invalid_value
        )


# ============================================================
# Core Benchmark Metric Tests
# ============================================================


def test_calculate_benchmark_metrics(
    standard_input: BenchmarkInput,
) -> None:
    """
    Core benchmark metrics should match their standard formulas.
    """

    result = calculate_benchmark_metrics(
        standard_input
    )

    expected_portfolio_mean = mean(
        standard_input.portfolio_returns
    )

    expected_benchmark_mean = mean(
        standard_input.benchmark_returns
    )

    expected_annualised_portfolio_return = (
        expected_portfolio_mean
        * standard_input.periods_per_year
    )

    expected_annualised_benchmark_return = (
        expected_benchmark_mean
        * standard_input.periods_per_year
    )

    expected_excess_return = (
        expected_annualised_portfolio_return
        - expected_annualised_benchmark_return
    )

    active_returns = tuple(
        portfolio_return - benchmark_return
        for portfolio_return, benchmark_return in zip(
            standard_input.portfolio_returns,
            standard_input.benchmark_returns,
            strict=True,
        )
    )

    expected_tracking_error = (
        stdev(active_returns)
        * sqrt(standard_input.periods_per_year)
    )

    expected_information_ratio = (
        expected_excess_return
        / expected_tracking_error
    )

    assert isinstance(result, BenchmarkResult)
    assert result.observation_count == 8
    assert result.periods_per_year == 12
    assert result.benchmark_name == "Nifty 50 TRI"

    assert result.mean_portfolio_return_decimal == pytest.approx(
        expected_portfolio_mean,
        rel=1e-12,
    )

    assert result.mean_benchmark_return_decimal == pytest.approx(
        expected_benchmark_mean,
        rel=1e-12,
    )

    assert result.annualised_portfolio_return_decimal == pytest.approx(
        expected_annualised_portfolio_return,
        rel=1e-12,
    )

    assert result.annualised_benchmark_return_decimal == pytest.approx(
        expected_annualised_benchmark_return,
        rel=1e-12,
    )

    assert result.annualised_excess_return_decimal == pytest.approx(
        expected_excess_return,
        rel=1e-12,
    )

    assert result.tracking_error_decimal == pytest.approx(
        expected_tracking_error,
        rel=1e-12,
    )

    assert result.information_ratio == pytest.approx(
        expected_information_ratio,
        rel=1e-12,
    )

    assert result.beta is not None
    assert result.alpha_decimal is not None
    assert result.correlation is not None
    assert result.r_squared is not None


def test_identical_returns_produce_beta_one() -> None:
    """
    Identical portfolio and benchmark returns should produce beta one.
    """

    returns = (
        0.01,
        -0.02,
        0.03,
        0.005,
    )

    result = calculate_benchmark_metrics(
        BenchmarkInput(
            portfolio_returns=returns,
            benchmark_returns=returns,
            periods_per_year=12,
            annual_risk_free_rate=0.0,
        )
    )

    assert result.beta == pytest.approx(
        1.0,
        rel=1e-12,
    )

    assert result.correlation == pytest.approx(
        1.0,
        rel=1e-12,
    )

    assert result.r_squared == pytest.approx(
        1.0,
        rel=1e-12,
    )

    assert result.alpha_decimal == pytest.approx(
        0.0,
        abs=1e-12,
    )

    assert result.annualised_excess_return_decimal == pytest.approx(
        0.0,
        abs=1e-12,
    )

    assert result.tracking_error_decimal == pytest.approx(
        0.0,
        abs=1e-12,
    )

    assert result.information_ratio is None


def test_constant_benchmark_returns_produce_none_beta() -> None:
    """
    Benchmark series with zero variance should produce undefined beta.
    """

    result = calculate_benchmark_metrics(
        BenchmarkInput(
            portfolio_returns=(
                0.01,
                0.02,
                -0.01,
                0.03,
            ),
            benchmark_returns=(
                0.01,
                0.01,
                0.01,
                0.01,
            ),
            periods_per_year=12,
        )
    )

    assert result.beta is None
    assert result.alpha_decimal is None
    assert result.alpha_percent is None
    assert result.correlation is None
    assert result.r_squared is None


def test_constant_portfolio_returns_produce_none_correlation() -> None:
    """
    A portfolio series with zero volatility should have undefined correlation.
    """

    result = calculate_benchmark_metrics(
        BenchmarkInput(
            portfolio_returns=(
                0.01,
                0.01,
                0.01,
                0.01,
            ),
            benchmark_returns=(
                0.02,
                -0.01,
                0.03,
                -0.02,
            ),
            periods_per_year=12,
        )
    )

    assert result.correlation is None
    assert result.r_squared is None
    assert result.beta == pytest.approx(0.0)


def test_active_return_counts() -> None:
    """
    Positive, negative, and zero active returns should be counted.
    """

    result = calculate_benchmark_metrics(
        BenchmarkInput(
            portfolio_returns=(
                0.02,
                0.01,
                -0.01,
                0.03,
            ),
            benchmark_returns=(
                0.01,
                0.02,
                -0.01,
                0.01,
            ),
            periods_per_year=12,
        )
    )

    assert result.active_return_positive_count == 2
    assert result.active_return_negative_count == 1
    assert result.active_return_zero_count == 1

    assert result.active_return_positive_frequency == pytest.approx(
        0.5
    )

    assert result.active_return_negative_frequency == pytest.approx(
        0.25
    )

    assert result.best_active_return_decimal == pytest.approx(
        0.02
    )

    assert result.worst_active_return_decimal == pytest.approx(
        -0.01
    )


def test_upside_capture_ratio() -> None:
    """
    Upside capture should compare returns in positive benchmark periods.
    """

    result = calculate_benchmark_metrics(
        BenchmarkInput(
            portfolio_returns=(
                0.03,
                -0.01,
                0.02,
                -0.03,
            ),
            benchmark_returns=(
                0.02,
                -0.02,
                0.01,
                -0.04,
            ),
            periods_per_year=12,
        )
    )

    expected_upside_capture = (
        mean((0.03, 0.02))
        / mean((0.02, 0.01))
    ) * 100.0

    assert result.upside_capture_ratio == pytest.approx(
        expected_upside_capture,
        rel=1e-12,
    )


def test_downside_capture_ratio() -> None:
    """
    Downside capture should compare returns in negative benchmark periods.
    """

    result = calculate_benchmark_metrics(
        BenchmarkInput(
            portfolio_returns=(
                0.03,
                -0.01,
                0.02,
                -0.03,
            ),
            benchmark_returns=(
                0.02,
                -0.02,
                0.01,
                -0.04,
            ),
            periods_per_year=12,
        )
    )

    expected_downside_capture = (
        mean((-0.01, -0.03))
        / mean((-0.02, -0.04))
    ) * 100.0

    assert result.downside_capture_ratio == pytest.approx(
        expected_downside_capture,
        rel=1e-12,
    )


def test_capture_ratio_none_when_no_positive_benchmark_periods() -> None:
    """
    Upside capture should be undefined without positive benchmark periods.
    """

    result = calculate_benchmark_metrics(
        BenchmarkInput(
            portfolio_returns=(
                -0.01,
                -0.02,
                0.01,
            ),
            benchmark_returns=(
                -0.02,
                -0.03,
                -0.01,
            ),
            periods_per_year=12,
        )
    )

    assert result.upside_capture_ratio is None


def test_capture_ratio_none_when_no_negative_benchmark_periods() -> None:
    """
    Downside capture should be undefined without negative benchmark periods.
    """

    result = calculate_benchmark_metrics(
        BenchmarkInput(
            portfolio_returns=(
                0.01,
                0.02,
                0.03,
            ),
            benchmark_returns=(
                0.02,
                0.01,
                0.04,
            ),
            periods_per_year=12,
        )
    )

    assert result.downside_capture_ratio is None


def test_calculate_benchmark_metrics_rejects_wrong_input_type() -> None:
    """
    Core API should reject unsupported input objects.
    """

    with pytest.raises(
        TypeError,
        match="BenchmarkInput",
    ):
        calculate_benchmark_metrics(  # type: ignore[arg-type]
            {
                "portfolio_returns": (),
                "benchmark_returns": (),
            }
        )


# ============================================================
# Input Validation Tests
# ============================================================


def test_validate_benchmark_input(
    standard_input: BenchmarkInput,
) -> None:
    """
    Valid benchmark input should preserve normalised values.
    """

    validated = validate_benchmark_input(
        standard_input
    )

    assert validated.portfolio_returns == (
        standard_input.portfolio_returns
    )

    assert validated.benchmark_returns == (
        standard_input.benchmark_returns
    )

    assert validated.periods_per_year == 12
    assert validated.annual_risk_free_rate == pytest.approx(
        0.06
    )

    assert validated.benchmark_name == "Nifty 50 TRI"


def test_validate_input_converts_numeric_returns() -> None:
    """
    Numeric return values should be converted to floats.
    """

    validated = validate_benchmark_input(
        BenchmarkInput(
            portfolio_returns=(1, 2, 3),
            benchmark_returns=(1, 1, 2),
            periods_per_year=12,
        )
    )

    assert validated.portfolio_returns == (
        1.0,
        2.0,
        3.0,
    )

    assert validated.benchmark_returns == (
        1.0,
        1.0,
        2.0,
    )


def test_validate_input_requires_aligned_lengths() -> None:
    """
    Portfolio and benchmark returns must have equal lengths.
    """

    with pytest.raises(
        BenchmarkValidationError,
        match="same number of observations",
    ):
        validate_benchmark_input(
            BenchmarkInput(
                portfolio_returns=(
                    0.01,
                    0.02,
                    0.03,
                ),
                benchmark_returns=(
                    0.01,
                    0.02,
                ),
                periods_per_year=12,
            )
        )


def test_validate_input_requires_two_portfolio_returns() -> None:
    """
    Portfolio sequence must contain at least two observations.
    """

    with pytest.raises(
        BenchmarkValidationError,
        match="portfolio_returns must contain at least two",
    ):
        validate_benchmark_input(
            BenchmarkInput(
                portfolio_returns=(0.01,),
                benchmark_returns=(0.01,),
                periods_per_year=12,
            )
        )


def test_validate_input_requires_two_benchmark_returns() -> None:
    """
    Benchmark sequence must contain at least two observations.
    """

    with pytest.raises(
        BenchmarkValidationError,
        match="benchmark_returns must contain at least two",
    ):
        validate_benchmark_input(
            BenchmarkInput(
                portfolio_returns=(
                    0.01,
                    0.02,
                ),
                benchmark_returns=(0.01,),
                periods_per_year=12,
            )
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "portfolio",
        "benchmark",
    ],
)
def test_validate_input_rejects_string_returns(
    field_name: str,
) -> None:
    """
    Strings must not be interpreted as return sequences.
    """

    portfolio: object = (
        "invalid"
        if field_name == "portfolio"
        else (0.01, 0.02)
    )

    benchmark: object = (
        "invalid"
        if field_name == "benchmark"
        else (0.01, 0.02)
    )

    with pytest.raises(
        BenchmarkValidationError,
        match="must be an iterable",
    ):
        validate_benchmark_input(
            BenchmarkInput(
                portfolio_returns=portfolio,  # type: ignore[arg-type]
                benchmark_returns=benchmark,  # type: ignore[arg-type]
                periods_per_year=12,
            )
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "portfolio",
        "benchmark",
    ],
)
def test_validate_input_rejects_non_iterable_returns(
    field_name: str,
) -> None:
    """
    Non-iterable return inputs should be rejected.
    """

    portfolio: object = (
        123
        if field_name == "portfolio"
        else (0.01, 0.02)
    )

    benchmark: object = (
        123
        if field_name == "benchmark"
        else (0.01, 0.02)
    )

    with pytest.raises(
        BenchmarkValidationError,
        match="must be an iterable",
    ):
        validate_benchmark_input(
            BenchmarkInput(
                portfolio_returns=portfolio,  # type: ignore[arg-type]
                benchmark_returns=benchmark,  # type: ignore[arg-type]
                periods_per_year=12,
            )
        )


@pytest.mark.parametrize(
    "invalid_return",
    [
        True,
        False,
        float("nan"),
        float("inf"),
        float("-inf"),
        "invalid",
    ],
)
def test_validate_input_rejects_invalid_portfolio_return(
    invalid_return: object,
) -> None:
    """
    Portfolio returns must be finite non-boolean numbers.
    """

    with pytest.raises(BenchmarkValidationError):
        validate_benchmark_input(
            BenchmarkInput(
                portfolio_returns=(
                    0.01,
                    invalid_return,  # type: ignore[arg-type]
                ),
                benchmark_returns=(
                    0.01,
                    0.02,
                ),
                periods_per_year=12,
            )
        )


@pytest.mark.parametrize(
    "invalid_return",
    [
        True,
        False,
        float("nan"),
        float("inf"),
        float("-inf"),
        "invalid",
    ],
)
def test_validate_input_rejects_invalid_benchmark_return(
    invalid_return: object,
) -> None:
    """
    Benchmark returns must be finite non-boolean numbers.
    """

    with pytest.raises(BenchmarkValidationError):
        validate_benchmark_input(
            BenchmarkInput(
                portfolio_returns=(
                    0.01,
                    0.02,
                ),
                benchmark_returns=(
                    0.01,
                    invalid_return,  # type: ignore[arg-type]
                ),
                periods_per_year=12,
            )
        )


@pytest.mark.parametrize(
    "periods_per_year",
    [
        0,
        -1,
        True,
        12.5,
        "12",
    ],
)
def test_validate_input_rejects_invalid_periods_per_year(
    periods_per_year: object,
) -> None:
    """
    Annualisation frequency must be a strict positive integer.
    """

    with pytest.raises(BenchmarkValidationError):
        validate_benchmark_input(
            BenchmarkInput(
                portfolio_returns=(0.01, 0.02),
                benchmark_returns=(0.01, 0.02),
                periods_per_year=periods_per_year,  # type: ignore[arg-type]
            )
        )


@pytest.mark.parametrize(
    "risk_free_rate",
    [
        -1.0,
        -2.0,
        True,
        float("nan"),
        float("inf"),
    ],
)
def test_validate_input_rejects_invalid_risk_free_rate(
    risk_free_rate: object,
) -> None:
    """
    Risk-free rate must be finite and greater than negative one.
    """

    with pytest.raises(BenchmarkValidationError):
        validate_benchmark_input(
            BenchmarkInput(
                portfolio_returns=(0.01, 0.02),
                benchmark_returns=(0.01, 0.02),
                periods_per_year=12,
                annual_risk_free_rate=risk_free_rate,  # type: ignore[arg-type]
            )
        )


def test_validate_input_strips_benchmark_name() -> None:
    """
    Benchmark name should be trimmed.
    """

    validated = validate_benchmark_input(
        BenchmarkInput(
            portfolio_returns=(0.01, 0.02),
            benchmark_returns=(0.01, 0.02),
            benchmark_name="  Nifty 50 TRI  ",
        )
    )

    assert validated.benchmark_name == "Nifty 50 TRI"


def test_validate_input_converts_blank_benchmark_name_to_none() -> None:
    """
    Blank benchmark name should be normalised to None.
    """

    validated = validate_benchmark_input(
        BenchmarkInput(
            portfolio_returns=(0.01, 0.02),
            benchmark_returns=(0.01, 0.02),
            benchmark_name="   ",
        )
    )

    assert validated.benchmark_name is None


# ============================================================
# Portfolio Benchmark API Tests
# ============================================================


def test_calculate_portfolio_benchmark_metrics(
    portfolio_returns: tuple[float, ...],
    benchmark_returns: tuple[float, ...],
) -> None:
    """
    Portfolio API should delegate to the core benchmark calculation.
    """

    result = calculate_portfolio_benchmark_metrics(
        portfolio_returns,
        benchmark_returns,
        periods_per_year=12,
        annual_risk_free_rate=0.06,
        benchmark_name="Nifty 50 TRI",
    )

    assert result.observation_count == len(
        portfolio_returns
    )

    assert result.periods_per_year == 12
    assert result.benchmark_name == "Nifty 50 TRI"


def test_portfolio_api_accepts_generators() -> None:
    """
    Portfolio API should accept valid iterables.
    """

    portfolio = (
        value
        for value in (
            0.01,
            -0.01,
            0.02,
        )
    )

    benchmark = (
        value
        for value in (
            0.008,
            -0.012,
            0.015,
        )
    )

    result = calculate_portfolio_benchmark_metrics(
        portfolio,
        benchmark,
        periods_per_year=12,
    )

    assert result.observation_count == 3


def test_portfolio_api_rejects_string_portfolio_returns() -> None:
    """
    Portfolio return strings should be rejected.
    """

    with pytest.raises(
        BenchmarkValidationError,
        match="portfolio_returns must be an iterable",
    ):
        calculate_portfolio_benchmark_metrics(
            "invalid",  # type: ignore[arg-type]
            (0.01, 0.02),
        )


def test_portfolio_api_rejects_string_benchmark_returns() -> None:
    """
    Benchmark return strings should be rejected.
    """

    with pytest.raises(
        BenchmarkValidationError,
        match="benchmark_returns must be an iterable",
    ):
        calculate_portfolio_benchmark_metrics(
            (0.01, 0.02),
            "invalid",  # type: ignore[arg-type]
        )


def test_portfolio_api_rejects_non_iterable_portfolio_returns() -> None:
    """
    Non-iterable portfolio returns should be rejected.
    """

    with pytest.raises(
        BenchmarkValidationError,
        match="portfolio_returns must be an iterable",
    ):
        calculate_portfolio_benchmark_metrics(
            123,  # type: ignore[arg-type]
            (0.01, 0.02),
        )


def test_portfolio_api_rejects_non_iterable_benchmark_returns() -> None:
    """
    Non-iterable benchmark returns should be rejected.
    """

    with pytest.raises(
        BenchmarkValidationError,
        match="benchmark_returns must be an iterable",
    ):
        calculate_portfolio_benchmark_metrics(
            (0.01, 0.02),
            123,  # type: ignore[arg-type]
        )


# ============================================================
# Fund Benchmark Tests
# ============================================================


def test_validate_fund_benchmark_input(
    standard_fund_input: FundBenchmarkInput,
) -> None:
    """
    Fund validation should preserve metadata.
    """

    validated = validate_fund_benchmark_input(
        standard_fund_input
    )

    assert validated.fund_name == "UTI Nifty 50 Index Fund"
    assert validated.scheme_code == "120716"
    assert validated.source == "Unit test"
    assert validated.benchmark_name == "Nifty 50 TRI"


def test_calculate_fund_benchmark_metrics(
    standard_fund_input: FundBenchmarkInput,
) -> None:
    """
    Fund API should return metadata and benchmark metrics.
    """

    result = calculate_fund_benchmark_metrics(
        standard_fund_input
    )

    assert result.fund_name == "UTI Nifty 50 Index Fund"
    assert result.scheme_code == "120716"
    assert result.source == "Unit test"

    assert result.result.observation_count == 8
    assert result.result.benchmark_name == "Nifty 50 TRI"


def test_fund_api_strips_metadata() -> None:
    """
    Fund metadata should be trimmed.
    """

    result = calculate_fund_benchmark_metrics(
        FundBenchmarkInput(
            fund_name="  Example Fund  ",
            fund_returns=(
                0.01,
                -0.01,
                0.02,
            ),
            benchmark_returns=(
                0.008,
                -0.012,
                0.015,
            ),
            periods_per_year=12,
            benchmark_name="  Nifty 50 TRI  ",
            scheme_code="  ABC123  ",
            source="  Unit test  ",
        )
    )

    assert result.fund_name == "Example Fund"
    assert result.scheme_code == "ABC123"
    assert result.source == "Unit test"
    assert result.result.benchmark_name == "Nifty 50 TRI"


def test_fund_api_converts_blank_metadata_to_none() -> None:
    """
    Blank optional metadata should be normalised to None.
    """

    result = calculate_fund_benchmark_metrics(
        FundBenchmarkInput(
            fund_name="Example Fund",
            fund_returns=(
                0.01,
                -0.01,
                0.02,
            ),
            benchmark_returns=(
                0.008,
                -0.012,
                0.015,
            ),
            periods_per_year=12,
            benchmark_name="   ",
            scheme_code="   ",
            source="",
        )
    )

    assert result.scheme_code is None
    assert result.source is None
    assert result.result.benchmark_name is None


def test_fund_api_rejects_empty_name() -> None:
    """
    Fund names cannot be empty.
    """

    with pytest.raises(
        BenchmarkValidationError,
        match="fund_name cannot be empty",
    ):
        calculate_fund_benchmark_metrics(
            FundBenchmarkInput(
                fund_name="   ",
                fund_returns=(0.01, 0.02),
                benchmark_returns=(0.01, 0.02),
            )
        )


def test_fund_api_rejects_wrong_input_type() -> None:
    """
    Fund API should reject unsupported objects.
    """

    with pytest.raises(
        TypeError,
        match="FundBenchmarkInput",
    ):
        calculate_fund_benchmark_metrics(  # type: ignore[arg-type]
            BenchmarkInput(
                portfolio_returns=(0.01, 0.02),
                benchmark_returns=(0.01, 0.02),
            )
        )


# ============================================================
# Fund Batch Tests
# ============================================================


def test_calculate_fund_wise_benchmark_metrics_all_successful() -> None:
    """
    All valid fund records should be successful.
    """

    funds = (
        FundBenchmarkInput(
            fund_name="Fund A",
            fund_returns=(
                0.01,
                -0.01,
                0.02,
            ),
            benchmark_returns=(
                0.008,
                -0.012,
                0.015,
            ),
            periods_per_year=12,
        ),
        FundBenchmarkInput(
            fund_name="Fund B",
            fund_returns=(
                0.02,
                0.01,
                -0.02,
            ),
            benchmark_returns=(
                0.015,
                0.008,
                -0.025,
            ),
            periods_per_year=12,
        ),
    )

    result = calculate_fund_wise_benchmark_metrics(
        funds
    )

    assert result.total_received == 2
    assert result.successful_count == 2
    assert result.failed_count == 0
    assert result.failed == ()


def test_fund_batch_collects_invalid_fund() -> None:
    """
    Invalid fund records should not block valid calculations.
    """

    funds = (
        FundBenchmarkInput(
            fund_name="Valid Fund",
            fund_returns=(
                0.01,
                -0.01,
                0.02,
            ),
            benchmark_returns=(
                0.008,
                -0.012,
                0.015,
            ),
            periods_per_year=12,
        ),
        FundBenchmarkInput(
            fund_name="Invalid Fund",
            fund_returns=(
                0.01,
                0.02,
            ),
            benchmark_returns=(0.01,),
            periods_per_year=12,
            scheme_code="INVALID",
        ),
    )

    result = calculate_fund_wise_benchmark_metrics(
        funds,
        fail_fast=False,
    )

    assert result.total_received == 2
    assert result.successful_count == 1
    assert result.failed_count == 1

    assert result.failed[0].fund_name == "Invalid Fund"
    assert result.failed[0].scheme_code == "INVALID"

    assert (
        "same number of observations"
        in result.failed[0].error
        or "at least two observations"
        in result.failed[0].error
    )


def test_fund_batch_fail_fast() -> None:
    """
    fail_fast=True should raise the first validation error.
    """

    funds = (
        FundBenchmarkInput(
            fund_name="Invalid Fund",
            fund_returns=(
                0.01,
                0.02,
            ),
            benchmark_returns=(0.01,),
            periods_per_year=12,
        ),
    )

    with pytest.raises(BenchmarkValidationError):
        calculate_fund_wise_benchmark_metrics(
            funds,
            fail_fast=True,
        )


def test_fund_batch_collects_wrong_record_type() -> None:
    """
    Unsupported records should be represented as failures.
    """

    records = (
        FundBenchmarkInput(
            fund_name="Valid Fund",
            fund_returns=(
                0.01,
                -0.01,
                0.02,
            ),
            benchmark_returns=(
                0.008,
                -0.012,
                0.015,
            ),
            periods_per_year=12,
        ),
        "invalid record",
    )

    result = calculate_fund_wise_benchmark_metrics(  # type: ignore[arg-type]
        records,
        fail_fast=False,
    )

    assert result.total_received == 2
    assert result.successful_count == 1
    assert result.failed_count == 1

    assert "Record at index 1" in result.failed[0].error


def test_fund_batch_rejects_invalid_fail_fast() -> None:
    """
    fail_fast must be a strict boolean.
    """

    with pytest.raises(
        BenchmarkValidationError,
        match="fail_fast must be a boolean",
    ):
        calculate_fund_wise_benchmark_metrics(
            (),
            fail_fast=1,  # type: ignore[arg-type]
        )


def test_fund_batch_rejects_string_iterable() -> None:
    """
    Strings must not be accepted as fund collections.
    """

    with pytest.raises(
        TypeError,
        match="iterable of FundBenchmarkInput",
    ):
        calculate_fund_wise_benchmark_metrics(
            "invalid"  # type: ignore[arg-type]
        )


def test_fund_batch_rejects_non_iterable() -> None:
    """
    Non-iterable fund collections should be rejected.
    """

    with pytest.raises(
        TypeError,
        match="iterable of FundBenchmarkInput",
    ):
        calculate_fund_wise_benchmark_metrics(
            123  # type: ignore[arg-type]
        )


# ============================================================
# Periodic Return Construction Tests
# ============================================================


def test_calculate_periodic_returns() -> None:
    """
    Historical values should convert to periodic returns.
    """

    result = calculate_periodic_returns(
        (
            100.0,
            110.0,
            99.0,
            108.9,
        )
    )

    assert result == pytest.approx(
        (
            0.10,
            -0.10,
            0.10,
        )
    )


def test_periodic_returns_accepts_generator() -> None:
    """
    Return construction should accept valid iterables.
    """

    values = (
        value
        for value in (
            100.0,
            110.0,
            121.0,
        )
    )

    result = calculate_periodic_returns(values)

    assert result == pytest.approx(
        (
            0.10,
            0.10,
        )
    )


def test_periodic_returns_requires_three_values() -> None:
    """
    Three values are needed to produce two return observations.
    """

    with pytest.raises(
        BenchmarkValidationError,
        match="At least three values",
    ):
        calculate_periodic_returns(
            (
                100.0,
                110.0,
            )
        )


def test_periodic_returns_rejects_zero_previous_value() -> None:
    """
    Zero cannot be used as a return denominator.
    """

    with pytest.raises(
        BenchmarkValidationError,
        match=r"values\[0\] must be greater than zero",
    ):
        calculate_periodic_returns(
            (
                0.0,
                100.0,
                110.0,
            )
        )


def test_periodic_returns_rejects_intermediate_zero() -> None:
    """
    Intermediate zero cannot be used for a subsequent return.
    """

    with pytest.raises(
        BenchmarkValidationError,
        match=r"values\[1\] must be greater than zero",
    ):
        calculate_periodic_returns(
            (
                100.0,
                0.0,
                50.0,
            )
        )


def test_periodic_returns_allows_zero_final_value() -> None:
    """
    Final zero represents a valid negative 100% return.
    """

    result = calculate_periodic_returns(
        (
            100.0,
            50.0,
            0.0,
        )
    )

    assert result == pytest.approx(
        (
            -0.50,
            -1.00,
        )
    )


def test_periodic_returns_rejects_string() -> None:
    """
    Strings must not be interpreted as value sequences.
    """

    with pytest.raises(
        BenchmarkValidationError,
        match="values must be an iterable",
    ):
        calculate_periodic_returns(
            "invalid"  # type: ignore[arg-type]
        )


def test_periodic_returns_rejects_non_iterable() -> None:
    """
    Non-iterable values should be rejected.
    """

    with pytest.raises(
        BenchmarkValidationError,
        match="values must be an iterable",
    ):
        calculate_periodic_returns(
            123  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "invalid_value",
    [
        True,
        float("nan"),
        float("inf"),
        "invalid",
    ],
)
def test_periodic_returns_rejects_invalid_values(
    invalid_value: object,
) -> None:
    """
    Historical values must be finite non-boolean numbers.
    """

    with pytest.raises(BenchmarkValidationError):
        calculate_periodic_returns(
            (
                100.0,
                invalid_value,  # type: ignore[arg-type]
                110.0,
            )
        )


# ============================================================
# Result Rounding Tests
# ============================================================


def test_round_benchmark_result(
    standard_input: BenchmarkInput,
) -> None:
    """
    Rounding should preserve counts, labels, and optional values.
    """

    original = calculate_benchmark_metrics(
        standard_input
    )

    rounded = round_benchmark_result(
        original,
        decimal_places=2,
    )

    assert rounded.observation_count == (
        original.observation_count
    )

    assert rounded.periods_per_year == (
        original.periods_per_year
    )

    assert rounded.benchmark_name == (
        original.benchmark_name
    )

    assert rounded.rating == original.rating

    assert rounded.annualised_excess_return_percent == round(
        original.annualised_excess_return_percent,
        2,
    )

    if original.beta is not None:
        assert rounded.beta == round(
            original.beta,
            2,
        )

    if original.alpha_percent is not None:
        assert rounded.alpha_percent == round(
            original.alpha_percent,
            2,
        )


def test_round_result_preserves_none_metrics() -> None:
    """
    Undefined metrics should remain None after rounding.
    """

    result = calculate_benchmark_metrics(
        BenchmarkInput(
            portfolio_returns=(
                0.01,
                0.01,
                0.01,
            ),
            benchmark_returns=(
                0.01,
                0.01,
                0.01,
            ),
            periods_per_year=12,
        )
    )

    rounded = round_benchmark_result(
        result,
        decimal_places=2,
    )

    assert rounded.information_ratio is None
    assert rounded.beta is None
    assert rounded.alpha_decimal is None
    assert rounded.correlation is None
    assert rounded.r_squared is None


def test_round_result_rejects_wrong_type() -> None:
    """
    Rounding should accept only BenchmarkResult objects.
    """

    with pytest.raises(
        TypeError,
        match="BenchmarkResult",
    ):
        round_benchmark_result(  # type: ignore[arg-type]
            {
                "beta": 1.0,
            }
        )


def test_round_result_rejects_negative_decimal_places(
    standard_input: BenchmarkInput,
) -> None:
    """
    Decimal places cannot be negative.
    """

    result = calculate_benchmark_metrics(
        standard_input
    )

    with pytest.raises(
        BenchmarkValidationError,
        match="decimal_places cannot be negative",
    ):
        round_benchmark_result(
            result,
            decimal_places=-1,
        )


@pytest.mark.parametrize(
    "decimal_places",
    [
        True,
        2.5,
        "2",
    ],
)
def test_round_result_rejects_invalid_decimal_places(
    decimal_places: object,
    standard_input: BenchmarkInput,
) -> None:
    """
    decimal_places must be a strict integer.
    """

    result = calculate_benchmark_metrics(
        standard_input
    )

    with pytest.raises(
        TypeError,
        match="decimal_places must be an integer",
    ):
        round_benchmark_result(
            result,
            decimal_places=decimal_places,  # type: ignore[arg-type]
        )


# ============================================================
# Dataclass Immutability Tests
# ============================================================


def test_benchmark_input_is_immutable() -> None:
    """
    BenchmarkInput should be immutable.
    """

    input_data = BenchmarkInput(
        portfolio_returns=(0.01, 0.02),
        benchmark_returns=(0.01, 0.02),
        periods_per_year=12,
    )

    with pytest.raises(FrozenInstanceError):
        input_data.periods_per_year = 52  # type: ignore[misc]


def test_fund_benchmark_input_is_immutable() -> None:
    """
    FundBenchmarkInput should be immutable.
    """

    input_data = FundBenchmarkInput(
        fund_name="Example Fund",
        fund_returns=(0.01, 0.02),
        benchmark_returns=(0.01, 0.02),
    )

    with pytest.raises(FrozenInstanceError):
        input_data.fund_name = "Changed Fund"  # type: ignore[misc]


def test_benchmark_result_is_immutable(
    standard_input: BenchmarkInput,
) -> None:
    """
    BenchmarkResult should be immutable.
    """

    result = calculate_benchmark_metrics(
        standard_input
    )

    with pytest.raises(FrozenInstanceError):
        result.beta = 2.0  # type: ignore[misc]


# ============================================================
# Consistency Tests
# ============================================================


def test_decimal_and_percent_metrics_are_consistent(
    standard_input: BenchmarkInput,
) -> None:
    """
    Percentage fields should equal decimal fields multiplied by 100.
    """

    result = calculate_benchmark_metrics(
        standard_input
    )

    assert result.mean_portfolio_return_percent == pytest.approx(
        result.mean_portfolio_return_decimal * 100.0
    )

    assert result.mean_benchmark_return_percent == pytest.approx(
        result.mean_benchmark_return_decimal * 100.0
    )

    assert result.annualised_portfolio_return_percent == pytest.approx(
        result.annualised_portfolio_return_decimal * 100.0
    )

    assert result.annualised_benchmark_return_percent == pytest.approx(
        result.annualised_benchmark_return_decimal * 100.0
    )

    assert result.annualised_excess_return_percent == pytest.approx(
        result.annualised_excess_return_decimal * 100.0
    )

    assert result.tracking_error_percent == pytest.approx(
        result.tracking_error_decimal * 100.0
    )

    if result.alpha_decimal is not None:
        assert result.alpha_percent == pytest.approx(
            result.alpha_decimal * 100.0
        )


def test_r_squared_matches_correlation_squared(
    standard_input: BenchmarkInput,
) -> None:
    """
    R-squared should equal squared correlation.
    """

    result = calculate_benchmark_metrics(
        standard_input
    )

    assert result.correlation is not None
    assert result.r_squared is not None

    assert result.r_squared == pytest.approx(
        result.correlation**2,
        rel=1e-12,
    )


def test_rating_matches_public_classifier(
    standard_input: BenchmarkInput,
) -> None:
    """
    Result rating should match the public classification function.
    """

    result = calculate_benchmark_metrics(
        standard_input
    )

    assert result.rating == classify_benchmark_performance(
        result.annualised_excess_return_decimal
    )