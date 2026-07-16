"""
Tests for services.analytics.risk_metrics.

These tests validate:

- Annual rate conversion
- Arithmetic return annualisation
- Downside deviation
- Sharpe ratio
- Sortino ratio
- Portfolio risk metrics
- Fund-wise risk metrics
- Batch fund processing
- Risk-adjusted ratio classification
- Value-to-return conversion
- Defensive validation
- Result rounding
- Immutable dataclasses
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from math import sqrt
from statistics import mean, stdev

import pytest

from services.analytics.risk_metrics import (
    FundRiskMetricsInput,
    RiskMetricsInput,
    RiskMetricsResult,
    RiskMetricsValidationError,
    annual_rate_to_periodic_rate,
    annualise_periodic_return,
    calculate_downside_deviation,
    calculate_fund_risk_metrics,
    calculate_fund_wise_risk_metrics,
    calculate_periodic_returns,
    calculate_portfolio_risk_metrics,
    calculate_risk_metrics,
    classify_risk_adjusted_ratio,
    round_risk_metrics_result,
    validate_fund_risk_metrics_input,
    validate_risk_metrics_input,
)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def monthly_returns() -> tuple[float, ...]:
    """
    Return a representative monthly return sequence.
    """

    return (
        0.020,
        -0.010,
        0.015,
        0.005,
        -0.020,
        0.030,
        0.010,
        -0.005,
    )


@pytest.fixture
def standard_input(
    monthly_returns: tuple[float, ...],
) -> RiskMetricsInput:
    """
    Return a valid monthly risk-metric input.
    """

    return RiskMetricsInput(
        returns=monthly_returns,
        periods_per_year=12,
        annual_risk_free_rate=0.06,
        annual_minimum_acceptable_return=0.04,
    )


@pytest.fixture
def standard_fund_input(
    monthly_returns: tuple[float, ...],
) -> FundRiskMetricsInput:
    """
    Return a valid fund-level risk-metric input.
    """

    return FundRiskMetricsInput(
        fund_name="UTI Nifty 50 Index Fund",
        returns=monthly_returns,
        periods_per_year=12,
        annual_risk_free_rate=0.06,
        annual_minimum_acceptable_return=0.04,
        scheme_code="120716",
        source="Unit test",
    )


# ============================================================
# Annual Rate Conversion Tests
# ============================================================


def test_annual_rate_to_periodic_rate() -> None:
    """
    Annual effective rate should convert to an effective periodic rate.
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
    A zero annual rate should produce a zero periodic rate.
    """

    assert annual_rate_to_periodic_rate(
        0.0,
        12,
    ) == pytest.approx(0.0)


def test_annual_rate_to_periodic_rate_negative() -> None:
    """
    A valid negative annual rate should produce a negative periodic rate.
    """

    result = annual_rate_to_periodic_rate(
        -0.10,
        12,
    )

    assert result < 0.0


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
    Annual rates must remain above negative 100%.
    """

    with pytest.raises(
        RiskMetricsValidationError,
        match="annual_rate must be greater than -1.0",
    ):
        annual_rate_to_periodic_rate(
            annual_rate,
            12,
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
def test_annual_rate_to_periodic_rate_rejects_invalid_periods(
    periods_per_year: object,
) -> None:
    """
    periods_per_year must be a strict positive integer.
    """

    with pytest.raises(RiskMetricsValidationError):
        annual_rate_to_periodic_rate(
            0.10,
            periods_per_year,  # type: ignore[arg-type]
        )


# ============================================================
# Arithmetic Annualisation Tests
# ============================================================


def test_annualise_periodic_return() -> None:
    """
    Arithmetic annualisation should multiply by periods per year.
    """

    result = annualise_periodic_return(
        0.01,
        12,
    )

    assert result == pytest.approx(0.12)


def test_annualise_negative_periodic_return() -> None:
    """
    Negative mean periodic returns should annualise correctly.
    """

    result = annualise_periodic_return(
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
    ],
)
def test_annualise_periodic_return_rejects_invalid_periods(
    periods_per_year: object,
) -> None:
    """
    Annualisation frequency must be a strict positive integer.
    """

    with pytest.raises(RiskMetricsValidationError):
        annualise_periodic_return(
            0.01,
            periods_per_year,  # type: ignore[arg-type]
        )


# ============================================================
# Downside Deviation Tests
# ============================================================


def test_calculate_downside_deviation() -> None:
    """
    Downside deviation should use returns below the periodic target.
    """

    returns = (
        0.02,
        -0.01,
        0.03,
        -0.02,
    )

    result = calculate_downside_deviation(
        returns,
        periods_per_year=12,
        annual_minimum_acceptable_return=0.0,
    )

    expected_periodic = sqrt(
        (
            0.0**2
            + (-0.01) ** 2
            + 0.0**2
            + (-0.02) ** 2
        )
        / 4
    )

    expected_annualised = (
        expected_periodic * sqrt(12)
    )

    assert result == pytest.approx(
        expected_annualised,
        rel=1e-12,
    )


def test_downside_deviation_zero_when_all_returns_above_target() -> None:
    """
    Returns entirely above the target should produce zero downside deviation.
    """

    result = calculate_downside_deviation(
        (
            0.02,
            0.03,
            0.01,
        ),
        periods_per_year=12,
        annual_minimum_acceptable_return=0.0,
    )

    assert result == pytest.approx(0.0)


def test_downside_deviation_uses_full_observation_count() -> None:
    """
    Downside deviation denominator should include all observations.
    """

    returns = (
        -0.02,
        0.01,
        0.01,
        0.01,
    )

    result = calculate_downside_deviation(
        returns,
        periods_per_year=1,
        annual_minimum_acceptable_return=0.0,
    )

    expected = sqrt(
        ((-0.02) ** 2) / 4
    )

    assert result == pytest.approx(expected)


def test_downside_deviation_rejects_one_return() -> None:
    """
    At least two observations are required.
    """

    with pytest.raises(
        RiskMetricsValidationError,
        match="At least two return observations",
    ):
        calculate_downside_deviation(
            (0.01,),
            periods_per_year=12,
        )


# ============================================================
# Ratio Classification Tests
# ============================================================


@pytest.mark.parametrize(
    ("ratio", "expected_rating"),
    [
        (-1.0, "poor"),
        (-0.01, "poor"),
        (0.0, "weak"),
        (0.49, "weak"),
        (0.50, "acceptable"),
        (0.99, "acceptable"),
        (1.0, "good"),
        (1.99, "good"),
        (2.0, "excellent"),
        (4.0, "excellent"),
    ],
)
def test_classify_risk_adjusted_ratio(
    ratio: float,
    expected_rating: str,
) -> None:
    """
    Sharpe and Sortino ratios should map to the correct rating.
    """

    assert classify_risk_adjusted_ratio(
        ratio
    ) == expected_rating


@pytest.mark.parametrize(
    "invalid_ratio",
    [
        True,
        float("nan"),
        float("inf"),
        "invalid",
    ],
)
def test_classify_ratio_rejects_invalid_values(
    invalid_ratio: object,
) -> None:
    """
    Ratio classification should reject invalid values.
    """

    with pytest.raises(RiskMetricsValidationError):
        classify_risk_adjusted_ratio(  # type: ignore[arg-type]
            invalid_ratio
        )


# ============================================================
# Core Risk Metrics Tests
# ============================================================


def test_calculate_risk_metrics(
    standard_input: RiskMetricsInput,
) -> None:
    """
    Core risk metrics should match their standard formulas.
    """

    result = calculate_risk_metrics(
        standard_input
    )

    expected_mean = mean(
        standard_input.returns
    )

    expected_periodic_volatility = stdev(
        standard_input.returns
    )

    expected_annualised_return = (
        expected_mean
        * standard_input.periods_per_year
    )

    expected_annualised_volatility = (
        expected_periodic_volatility
        * sqrt(standard_input.periods_per_year)
    )

    expected_excess_return = (
        expected_annualised_return
        - standard_input.annual_risk_free_rate
    )

    expected_sharpe = (
        expected_excess_return
        / expected_annualised_volatility
    )

    assert isinstance(result, RiskMetricsResult)
    assert result.observation_count == 8
    assert result.periods_per_year == 12

    assert result.mean_periodic_return_decimal == pytest.approx(
        expected_mean,
        rel=1e-12,
    )

    assert result.annualised_return_decimal == pytest.approx(
        expected_annualised_return,
        rel=1e-12,
    )

    assert result.periodic_volatility_decimal == pytest.approx(
        expected_periodic_volatility,
        rel=1e-12,
    )

    assert result.annualised_volatility_decimal == pytest.approx(
        expected_annualised_volatility,
        rel=1e-12,
    )

    assert result.annual_excess_return_decimal == pytest.approx(
        expected_excess_return,
        rel=1e-12,
    )

    assert result.sharpe_ratio == pytest.approx(
        expected_sharpe,
        rel=1e-12,
    )

    assert result.sortino_ratio is not None
    assert result.downside_deviation_decimal > 0.0


def test_calculate_risk_metrics_counts_return_directions() -> None:
    """
    Positive, negative, and zero observations should be counted.
    """

    result = calculate_risk_metrics(
        RiskMetricsInput(
            returns=(
                0.01,
                -0.01,
                0.0,
                0.02,
                -0.02,
            ),
            periods_per_year=12,
        )
    )

    assert result.positive_return_count == 2
    assert result.negative_return_count == 2
    assert result.zero_return_count == 1

    assert result.positive_return_frequency == pytest.approx(
        2 / 5
    )

    assert result.negative_return_frequency == pytest.approx(
        2 / 5
    )


def test_calculate_risk_metrics_best_and_worst_returns() -> None:
    """
    Best and worst periodic returns should be preserved.
    """

    result = calculate_risk_metrics(
        RiskMetricsInput(
            returns=(
                0.01,
                -0.05,
                0.08,
                0.02,
            ),
            periods_per_year=12,
        )
    )

    assert result.best_period_return_decimal == pytest.approx(
        0.08
    )

    assert result.worst_period_return_decimal == pytest.approx(
        -0.05
    )


def test_zero_volatility_returns_none_sharpe() -> None:
    """
    Constant returns should produce no finite Sharpe ratio.
    """

    result = calculate_risk_metrics(
        RiskMetricsInput(
            returns=(
                0.01,
                0.01,
                0.01,
                0.01,
            ),
            periods_per_year=12,
            annual_risk_free_rate=0.0,
        )
    )

    assert result.annualised_volatility_decimal == pytest.approx(
        0.0
    )

    assert result.sharpe_ratio is None
    assert result.sharpe_rating is None


def test_zero_downside_deviation_returns_none_sortino() -> None:
    """
    No downside observations should produce no finite Sortino ratio.
    """

    result = calculate_risk_metrics(
        RiskMetricsInput(
            returns=(
                0.01,
                0.02,
                0.03,
            ),
            periods_per_year=12,
            annual_minimum_acceptable_return=0.0,
        )
    )

    assert result.downside_deviation_decimal == pytest.approx(
        0.0
    )

    assert result.sortino_ratio is None
    assert result.sortino_rating is None


def test_negative_excess_return_produces_negative_sharpe() -> None:
    """
    Return below the risk-free rate should produce a negative Sharpe ratio.
    """

    result = calculate_risk_metrics(
        RiskMetricsInput(
            returns=(
                0.001,
                -0.001,
                0.0015,
                -0.0005,
            ),
            periods_per_year=12,
            annual_risk_free_rate=0.10,
        )
    )

    assert result.sharpe_ratio is not None
    assert result.sharpe_ratio < 0.0
    assert result.sharpe_rating == "poor"


def test_calculate_risk_metrics_rejects_wrong_type() -> None:
    """
    Core API should reject unsupported objects.
    """

    with pytest.raises(
        TypeError,
        match="RiskMetricsInput",
    ):
        calculate_risk_metrics(  # type: ignore[arg-type]
            {
                "returns": (0.01, 0.02),
            }
        )


# ============================================================
# Input Validation Tests
# ============================================================


def test_validate_risk_metrics_input(
    standard_input: RiskMetricsInput,
) -> None:
    """
    Valid input should be normalised and preserved.
    """

    validated = validate_risk_metrics_input(
        standard_input
    )

    assert validated.returns == standard_input.returns
    assert validated.periods_per_year == 12
    assert validated.annual_risk_free_rate == pytest.approx(
        0.06
    )

    assert (
        validated.annual_minimum_acceptable_return
        == pytest.approx(0.04)
    )


def test_validate_input_converts_numeric_returns() -> None:
    """
    Integer return values should be converted to floats.
    """

    validated = validate_risk_metrics_input(
        RiskMetricsInput(
            returns=(1, 2, 3),
            periods_per_year=12,
        )
    )

    assert validated.returns == (
        1.0,
        2.0,
        3.0,
    )


def test_validate_input_requires_two_returns() -> None:
    """
    At least two return observations are required.
    """

    with pytest.raises(
        RiskMetricsValidationError,
        match="At least two return observations",
    ):
        validate_risk_metrics_input(
            RiskMetricsInput(
                returns=(0.01,),
                periods_per_year=12,
            )
        )


def test_validate_input_rejects_string_returns() -> None:
    """
    Strings must not be interpreted as return sequences.
    """

    with pytest.raises(
        RiskMetricsValidationError,
        match="returns must be an iterable",
    ):
        validate_risk_metrics_input(
            RiskMetricsInput(
                returns="invalid",  # type: ignore[arg-type]
                periods_per_year=12,
            )
        )


def test_validate_input_rejects_non_iterable_returns() -> None:
    """
    Non-iterable return inputs should be rejected.
    """

    with pytest.raises(
        RiskMetricsValidationError,
        match="returns must be an iterable",
    ):
        validate_risk_metrics_input(
            RiskMetricsInput(
                returns=123,  # type: ignore[arg-type]
                periods_per_year=12,
            )
        )


@pytest.mark.parametrize(
    "return_value",
    [
        True,
        False,
        float("nan"),
        float("inf"),
        float("-inf"),
        "invalid",
    ],
)
def test_validate_input_rejects_invalid_returns(
    return_value: object,
) -> None:
    """
    Returns must be finite, numeric, and non-boolean.
    """

    with pytest.raises(RiskMetricsValidationError):
        validate_risk_metrics_input(
            RiskMetricsInput(
                returns=(
                    0.01,
                    return_value,  # type: ignore[arg-type]
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

    with pytest.raises(RiskMetricsValidationError):
        validate_risk_metrics_input(
            RiskMetricsInput(
                returns=(0.01, 0.02),
                periods_per_year=periods_per_year,  # type: ignore[arg-type]
            )
        )


@pytest.mark.parametrize(
    "risk_free_rate",
    [
        -1.0,
        -2.0,
        float("nan"),
        float("inf"),
        True,
    ],
)
def test_validate_input_rejects_invalid_risk_free_rate(
    risk_free_rate: object,
) -> None:
    """
    Risk-free rate must be finite and greater than negative one.
    """

    with pytest.raises(RiskMetricsValidationError):
        validate_risk_metrics_input(
            RiskMetricsInput(
                returns=(0.01, 0.02),
                periods_per_year=12,
                annual_risk_free_rate=risk_free_rate,  # type: ignore[arg-type]
            )
        )


@pytest.mark.parametrize(
    "minimum_return",
    [
        -1.0,
        -2.0,
        float("nan"),
        float("inf"),
        True,
    ],
)
def test_validate_input_rejects_invalid_minimum_return(
    minimum_return: object,
) -> None:
    """
    Minimum acceptable return must be finite and above negative one.
    """

    with pytest.raises(RiskMetricsValidationError):
        validate_risk_metrics_input(
            RiskMetricsInput(
                returns=(0.01, 0.02),
                periods_per_year=12,
                annual_minimum_acceptable_return=minimum_return,  # type: ignore[arg-type]
            )
        )


# ============================================================
# Portfolio Risk Metrics Tests
# ============================================================


def test_calculate_portfolio_risk_metrics(
    monthly_returns: tuple[float, ...],
) -> None:
    """
    Portfolio API should delegate to the core calculation.
    """

    result = calculate_portfolio_risk_metrics(
        monthly_returns,
        periods_per_year=12,
        annual_risk_free_rate=0.06,
        annual_minimum_acceptable_return=0.04,
    )

    assert result.observation_count == len(
        monthly_returns
    )

    assert result.periods_per_year == 12
    assert result.sharpe_ratio is not None


def test_portfolio_api_accepts_generator() -> None:
    """
    Portfolio API should accept valid iterables.
    """

    returns = (
        value
        for value in (
            0.01,
            -0.01,
            0.02,
        )
    )

    result = calculate_portfolio_risk_metrics(
        returns,
        periods_per_year=12,
    )

    assert result.observation_count == 3


def test_portfolio_api_rejects_string() -> None:
    """
    Strings must not be accepted as return sequences.
    """

    with pytest.raises(
        RiskMetricsValidationError,
        match="returns must be an iterable",
    ):
        calculate_portfolio_risk_metrics(
            "invalid",  # type: ignore[arg-type]
            periods_per_year=12,
        )


def test_portfolio_api_rejects_non_iterable() -> None:
    """
    Non-iterable portfolio returns should be rejected.
    """

    with pytest.raises(
        RiskMetricsValidationError,
        match="returns must be an iterable",
    ):
        calculate_portfolio_risk_metrics(
            123,  # type: ignore[arg-type]
            periods_per_year=12,
        )


# ============================================================
# Fund Risk Metrics Tests
# ============================================================


def test_validate_fund_risk_metrics_input(
    standard_fund_input: FundRiskMetricsInput,
) -> None:
    """
    Fund input validation should preserve metadata.
    """

    validated = validate_fund_risk_metrics_input(
        standard_fund_input
    )

    assert validated.fund_name == "UTI Nifty 50 Index Fund"
    assert validated.scheme_code == "120716"
    assert validated.source == "Unit test"
    assert validated.periods_per_year == 12


def test_calculate_fund_risk_metrics(
    standard_fund_input: FundRiskMetricsInput,
) -> None:
    """
    Fund API should return metadata and risk metrics.
    """

    result = calculate_fund_risk_metrics(
        standard_fund_input
    )

    assert result.fund_name == "UTI Nifty 50 Index Fund"
    assert result.scheme_code == "120716"
    assert result.source == "Unit test"

    assert result.result.observation_count == 8
    assert result.result.sharpe_ratio is not None


def test_fund_api_strips_metadata() -> None:
    """
    Fund metadata should be trimmed.
    """

    result = calculate_fund_risk_metrics(
        FundRiskMetricsInput(
            fund_name="  Example Fund  ",
            returns=(
                0.01,
                -0.01,
                0.02,
            ),
            periods_per_year=12,
            scheme_code="  ABC123  ",
            source="  Unit test  ",
        )
    )

    assert result.fund_name == "Example Fund"
    assert result.scheme_code == "ABC123"
    assert result.source == "Unit test"


def test_fund_api_converts_blank_metadata_to_none() -> None:
    """
    Blank optional metadata should be normalised to None.
    """

    result = calculate_fund_risk_metrics(
        FundRiskMetricsInput(
            fund_name="Example Fund",
            returns=(
                0.01,
                -0.01,
                0.02,
            ),
            periods_per_year=12,
            scheme_code="   ",
            source="",
        )
    )

    assert result.scheme_code is None
    assert result.source is None


def test_fund_api_rejects_empty_name() -> None:
    """
    Fund names cannot be empty.
    """

    with pytest.raises(
        RiskMetricsValidationError,
        match="fund_name cannot be empty",
    ):
        calculate_fund_risk_metrics(
            FundRiskMetricsInput(
                fund_name="   ",
                returns=(0.01, 0.02),
                periods_per_year=12,
            )
        )


def test_fund_api_rejects_wrong_input_type() -> None:
    """
    Fund API should reject unsupported objects.
    """

    with pytest.raises(
        TypeError,
        match="FundRiskMetricsInput",
    ):
        calculate_fund_risk_metrics(  # type: ignore[arg-type]
            RiskMetricsInput(
                returns=(0.01, 0.02),
            )
        )


# ============================================================
# Fund Batch Tests
# ============================================================


def test_calculate_fund_wise_risk_metrics_all_successful() -> None:
    """
    All valid fund records should be successful.
    """

    funds = (
        FundRiskMetricsInput(
            fund_name="Fund A",
            returns=(
                0.01,
                -0.01,
                0.02,
            ),
            periods_per_year=12,
        ),
        FundRiskMetricsInput(
            fund_name="Fund B",
            returns=(
                0.02,
                0.01,
                -0.02,
            ),
            periods_per_year=12,
        ),
    )

    result = calculate_fund_wise_risk_metrics(
        funds
    )

    assert result.total_received == 2
    assert result.successful_count == 2
    assert result.failed_count == 0
    assert result.failed == ()


def test_fund_batch_collects_invalid_fund() -> None:
    """
    Invalid funds should not block valid calculations.
    """

    funds = (
        FundRiskMetricsInput(
            fund_name="Valid Fund",
            returns=(
                0.01,
                -0.01,
                0.02,
            ),
            periods_per_year=12,
        ),
        FundRiskMetricsInput(
            fund_name="Invalid Fund",
            returns=(0.01,),
            periods_per_year=12,
            scheme_code="INVALID",
        ),
    )

    result = calculate_fund_wise_risk_metrics(
        funds,
        fail_fast=False,
    )

    assert result.total_received == 2
    assert result.successful_count == 1
    assert result.failed_count == 1

    assert result.failed[0].fund_name == "Invalid Fund"
    assert result.failed[0].scheme_code == "INVALID"

    assert "At least two return observations" in (
        result.failed[0].error
    )


def test_fund_batch_fail_fast() -> None:
    """
    fail_fast=True should raise the first validation error.
    """

    funds = (
        FundRiskMetricsInput(
            fund_name="Invalid Fund",
            returns=(0.01,),
            periods_per_year=12,
        ),
    )

    with pytest.raises(
        RiskMetricsValidationError,
        match="At least two return observations",
    ):
        calculate_fund_wise_risk_metrics(
            funds,
            fail_fast=True,
        )


def test_fund_batch_collects_wrong_record_type() -> None:
    """
    Unsupported records should be represented as failures.
    """

    records = (
        FundRiskMetricsInput(
            fund_name="Valid Fund",
            returns=(
                0.01,
                -0.01,
                0.02,
            ),
            periods_per_year=12,
        ),
        "invalid record",
    )

    result = calculate_fund_wise_risk_metrics(  # type: ignore[arg-type]
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
        RiskMetricsValidationError,
        match="fail_fast must be a boolean",
    ):
        calculate_fund_wise_risk_metrics(
            (),
            fail_fast=1,  # type: ignore[arg-type]
        )


def test_fund_batch_rejects_string_iterable() -> None:
    """
    Strings must not be accepted as fund collections.
    """

    with pytest.raises(
        TypeError,
        match="iterable of FundRiskMetricsInput",
    ):
        calculate_fund_wise_risk_metrics(
            "invalid"  # type: ignore[arg-type]
        )


def test_fund_batch_rejects_non_iterable() -> None:
    """
    Non-iterable fund collections should be rejected.
    """

    with pytest.raises(
        TypeError,
        match="iterable of FundRiskMetricsInput",
    ):
        calculate_fund_wise_risk_metrics(
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
    Three values are required to produce two return observations.
    """

    with pytest.raises(
        RiskMetricsValidationError,
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
        RiskMetricsValidationError,
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
        RiskMetricsValidationError,
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
    Strings must not be treated as value sequences.
    """

    with pytest.raises(
        RiskMetricsValidationError,
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
        RiskMetricsValidationError,
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
    Values must be finite numeric observations.
    """

    with pytest.raises(RiskMetricsValidationError):
        calculate_periodic_returns(
            (
                100.0,
                invalid_value,  # type: ignore[arg-type]
                110.0,
            )
        )


# ============================================================
# Rounding Tests
# ============================================================


def test_round_risk_metrics_result() -> None:
    """
    Result rounding should preserve counts and ratings.
    """

    original = RiskMetricsResult(
        observation_count=4,
        periods_per_year=12,
        mean_periodic_return_decimal=0.012345,
        mean_periodic_return_percent=1.2345,
        annualised_return_decimal=0.14814,
        annualised_return_percent=14.814,
        periodic_volatility_decimal=0.023456,
        periodic_volatility_percent=2.3456,
        annualised_volatility_decimal=0.081234,
        annualised_volatility_percent=8.1234,
        annual_risk_free_rate_decimal=0.06,
        annual_risk_free_rate_percent=6.0,
        annual_minimum_acceptable_return_decimal=0.04,
        annual_minimum_acceptable_return_percent=4.0,
        annual_excess_return_decimal=0.08814,
        annual_excess_return_percent=8.814,
        downside_deviation_decimal=0.045678,
        downside_deviation_percent=4.5678,
        sharpe_ratio=1.08543,
        sortino_ratio=2.36789,
        positive_return_count=2,
        negative_return_count=1,
        zero_return_count=1,
        positive_return_frequency=0.5,
        negative_return_frequency=0.25,
        best_period_return_decimal=0.04,
        worst_period_return_decimal=-0.02,
        sharpe_rating="good",
        sortino_rating="excellent",
    )

    rounded = round_risk_metrics_result(
        original,
        decimal_places=2,
    )

    assert rounded.mean_periodic_return_decimal == 0.01
    assert rounded.mean_periodic_return_percent == 1.23
    assert rounded.annualised_return_percent == 14.81

    assert rounded.sharpe_ratio == 1.09
    assert rounded.sortino_ratio == 2.37

    assert rounded.positive_return_count == 2
    assert rounded.sharpe_rating == "good"
    assert rounded.sortino_rating == "excellent"

    assert original.sharpe_ratio == 1.08543


def test_round_result_preserves_none_ratios() -> None:
    """
    Undefined ratios should remain None after rounding.
    """

    result = calculate_risk_metrics(
        RiskMetricsInput(
            returns=(
                0.01,
                0.01,
                0.01,
            ),
            periods_per_year=12,
        )
    )

    rounded = round_risk_metrics_result(
        result,
        decimal_places=2,
    )

    assert rounded.sharpe_ratio is None
    assert rounded.sortino_ratio is None


def test_round_result_rejects_wrong_type() -> None:
    """
    Rounding should accept only RiskMetricsResult.
    """

    with pytest.raises(
        TypeError,
        match="RiskMetricsResult",
    ):
        round_risk_metrics_result(  # type: ignore[arg-type]
            {
                "sharpe_ratio": 1.0,
            }
        )


def test_round_result_rejects_negative_decimal_places(
    standard_input: RiskMetricsInput,
) -> None:
    """
    Decimal places cannot be negative.
    """

    result = calculate_risk_metrics(
        standard_input
    )

    with pytest.raises(
        RiskMetricsValidationError,
        match="decimal_places cannot be negative",
    ):
        round_risk_metrics_result(
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
    standard_input: RiskMetricsInput,
) -> None:
    """
    decimal_places must be a strict integer.
    """

    result = calculate_risk_metrics(
        standard_input
    )

    with pytest.raises(
        TypeError,
        match="decimal_places must be an integer",
    ):
        round_risk_metrics_result(
            result,
            decimal_places=decimal_places,  # type: ignore[arg-type]
        )


# ============================================================
# Dataclass Immutability Tests
# ============================================================


def test_risk_metrics_input_is_immutable() -> None:
    """
    RiskMetricsInput should be immutable.
    """

    input_data = RiskMetricsInput(
        returns=(0.01, 0.02),
        periods_per_year=12,
    )

    with pytest.raises(FrozenInstanceError):
        input_data.periods_per_year = 52  # type: ignore[misc]


def test_fund_risk_metrics_input_is_immutable() -> None:
    """
    FundRiskMetricsInput should be immutable.
    """

    input_data = FundRiskMetricsInput(
        fund_name="Example Fund",
        returns=(0.01, 0.02),
        periods_per_year=12,
    )

    with pytest.raises(FrozenInstanceError):
        input_data.fund_name = "Changed Fund"  # type: ignore[misc]


def test_risk_metrics_result_is_immutable(
    standard_input: RiskMetricsInput,
) -> None:
    """
    RiskMetricsResult should be immutable.
    """

    result = calculate_risk_metrics(
        standard_input
    )

    with pytest.raises(FrozenInstanceError):
        result.sharpe_ratio = 2.0  # type: ignore[misc]


# ============================================================
# Consistency Tests
# ============================================================


def test_decimal_and_percent_metrics_are_consistent(
    standard_input: RiskMetricsInput,
) -> None:
    """
    Percentage fields should equal decimal fields multiplied by 100.
    """

    result = calculate_risk_metrics(
        standard_input
    )

    assert result.mean_periodic_return_percent == pytest.approx(
        result.mean_periodic_return_decimal * 100.0
    )

    assert result.annualised_return_percent == pytest.approx(
        result.annualised_return_decimal * 100.0
    )

    assert result.periodic_volatility_percent == pytest.approx(
        result.periodic_volatility_decimal * 100.0
    )

    assert result.annualised_volatility_percent == pytest.approx(
        result.annualised_volatility_decimal * 100.0
    )

    assert result.annual_excess_return_percent == pytest.approx(
        result.annual_excess_return_decimal * 100.0
    )

    assert result.downside_deviation_percent == pytest.approx(
        result.downside_deviation_decimal * 100.0
    )


def test_ratio_ratings_match_public_classifier(
    standard_input: RiskMetricsInput,
) -> None:
    """
    Result ratings should match the public classification function.
    """

    result = calculate_risk_metrics(
        standard_input
    )

    if result.sharpe_ratio is not None:
        assert result.sharpe_rating == (
            classify_risk_adjusted_ratio(
                result.sharpe_ratio
            )
        )

    if result.sortino_ratio is not None:
        assert result.sortino_rating == (
            classify_risk_adjusted_ratio(
                result.sortino_ratio
            )
        )