"""
Tests for services.analytics.volatility.

These tests validate:

- Periodic volatility
- Annualised volatility
- Portfolio volatility
- Fund-wise volatility
- Batch processing
- Risk classification
- Value-to-return conversion
- Defensive validation
- Result rounding
- Immutable dataclasses
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from math import sqrt
from statistics import stdev

import pytest

from services.analytics.volatility import (
    FundVolatilityInput,
    RiskLevel,
    VolatilityInput,
    VolatilityResult,
    VolatilityValidationError,
    calculate_fund_volatility,
    calculate_fund_wise_volatility,
    calculate_periodic_returns,
    calculate_portfolio_volatility,
    calculate_volatility,
    classify_volatility_risk,
    round_volatility_result,
    validate_fund_volatility_input,
    validate_volatility_input,
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
    )


@pytest.fixture
def standard_volatility_input(
    monthly_returns: tuple[float, ...],
) -> VolatilityInput:
    """
    Return a valid monthly volatility input.
    """

    return VolatilityInput(
        returns=monthly_returns,
        periods_per_year=12,
    )


@pytest.fixture
def standard_fund_input(
    monthly_returns: tuple[float, ...],
) -> FundVolatilityInput:
    """
    Return a valid fund-level volatility input.
    """

    return FundVolatilityInput(
        fund_name="UTI Nifty 50 Index Fund",
        returns=monthly_returns,
        periods_per_year=12,
        scheme_code="120716",
        source="Unit test",
    )


# ============================================================
# Core Volatility Tests
# ============================================================


def test_calculate_volatility_returns_expected_result(
    standard_volatility_input: VolatilityInput,
) -> None:
    """
    Periodic and annualised volatility should match the standard formula.
    """

    result = calculate_volatility(
        standard_volatility_input
    )

    expected_periodic_volatility = stdev(
        standard_volatility_input.returns
    )

    expected_annualised_volatility = (
        expected_periodic_volatility
        * sqrt(standard_volatility_input.periods_per_year)
    )

    expected_mean = (
        sum(standard_volatility_input.returns)
        / len(standard_volatility_input.returns)
    )

    assert isinstance(result, VolatilityResult)

    assert result.observation_count == 6
    assert result.periods_per_year == 12

    assert result.periodic_volatility_decimal == pytest.approx(
        expected_periodic_volatility,
        rel=1e-12,
    )

    assert result.periodic_volatility_percent == pytest.approx(
        expected_periodic_volatility * 100.0,
        rel=1e-12,
    )

    assert result.annualised_volatility_decimal == pytest.approx(
        expected_annualised_volatility,
        rel=1e-12,
    )

    assert result.annualised_volatility_percent == pytest.approx(
        expected_annualised_volatility * 100.0,
        rel=1e-12,
    )

    assert result.mean_periodic_return_decimal == pytest.approx(
        expected_mean,
        rel=1e-12,
    )

    assert result.mean_periodic_return_percent == pytest.approx(
        expected_mean * 100.0,
        rel=1e-12,
    )

    assert result.minimum_return_decimal == pytest.approx(
        -0.020
    )

    assert result.maximum_return_decimal == pytest.approx(
        0.030
    )


def test_calculate_volatility_for_constant_returns() -> None:
    """
    Constant returns should produce zero volatility.
    """

    result = calculate_volatility(
        VolatilityInput(
            returns=(0.01, 0.01, 0.01, 0.01),
            periods_per_year=12,
        )
    )

    assert result.periodic_volatility_decimal == pytest.approx(
        0.0
    )

    assert result.annualised_volatility_decimal == pytest.approx(
        0.0
    )

    assert result.risk_level == "very_low"


def test_calculate_volatility_with_negative_returns() -> None:
    """
    Negative returns should still produce valid volatility.
    """

    result = calculate_volatility(
        VolatilityInput(
            returns=(-0.01, -0.02, -0.03, -0.015),
            periods_per_year=12,
        )
    )

    assert result.periodic_volatility_decimal > 0.0
    assert result.annualised_volatility_decimal > 0.0
    assert result.mean_periodic_return_decimal < 0.0


def test_calculate_volatility_rejects_wrong_input_type() -> None:
    """
    Core API should reject unsupported input objects.
    """

    with pytest.raises(
        TypeError,
        match="VolatilityInput",
    ):
        calculate_volatility(  # type: ignore[arg-type]
            {
                "returns": (0.01, 0.02),
            }
        )


# ============================================================
# Input Validation Tests
# ============================================================


def test_validate_volatility_input_preserves_values(
    standard_volatility_input: VolatilityInput,
) -> None:
    """
    Valid input should be returned as a normalised immutable model.
    """

    validated = validate_volatility_input(
        standard_volatility_input
    )

    assert validated.returns == (
        0.020,
        -0.010,
        0.015,
        0.005,
        -0.020,
        0.030,
    )

    assert validated.periods_per_year == 12


def test_validate_volatility_input_converts_numeric_values() -> None:
    """
    Integer return observations should be converted to floats.
    """

    validated = validate_volatility_input(
        VolatilityInput(
            returns=(1, 2, 3),
            periods_per_year=12,
        )
    )

    assert validated.returns == (
        1.0,
        2.0,
        3.0,
    )


def test_validate_volatility_input_requires_two_observations() -> None:
    """
    Sample volatility requires at least two return observations.
    """

    with pytest.raises(
        VolatilityValidationError,
        match="At least two return observations",
    ):
        validate_volatility_input(
            VolatilityInput(
                returns=(0.01,),
                periods_per_year=12,
            )
        )


def test_validate_volatility_input_rejects_empty_returns() -> None:
    """
    Empty return sequences should be rejected.
    """

    with pytest.raises(
        VolatilityValidationError,
        match="At least two return observations",
    ):
        validate_volatility_input(
            VolatilityInput(
                returns=(),
                periods_per_year=12,
            )
        )


def test_validate_volatility_input_rejects_string_iterable() -> None:
    """
    Strings must not be treated as return sequences.
    """

    with pytest.raises(
        VolatilityValidationError,
        match="returns must be an iterable",
    ):
        validate_volatility_input(
            VolatilityInput(
                returns="invalid",  # type: ignore[arg-type]
                periods_per_year=12,
            )
        )


def test_validate_volatility_input_rejects_non_iterable() -> None:
    """
    Non-iterable return inputs should be rejected.
    """

    with pytest.raises(
        VolatilityValidationError,
        match="returns must be an iterable",
    ):
        validate_volatility_input(
            VolatilityInput(
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
    ],
)
def test_validate_volatility_input_rejects_invalid_returns(
    return_value: float,
) -> None:
    """
    Return observations must be finite non-boolean numbers.
    """

    with pytest.raises(VolatilityValidationError):
        validate_volatility_input(
            VolatilityInput(
                returns=(
                    0.01,
                    return_value,
                ),
                periods_per_year=12,
            )
        )


def test_validate_volatility_input_rejects_non_numeric_return() -> None:
    """
    Non-numeric return observations should be rejected.
    """

    with pytest.raises(
        VolatilityValidationError,
        match=r"returns\[1\] must be a valid numeric value",
    ):
        validate_volatility_input(
            VolatilityInput(
                returns=(
                    0.01,
                    "invalid",  # type: ignore[arg-type]
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
def test_validate_volatility_input_rejects_invalid_periods_per_year(
    periods_per_year: object,
) -> None:
    """
    periods_per_year must be a strict positive integer.
    """

    with pytest.raises(VolatilityValidationError):
        validate_volatility_input(
            VolatilityInput(
                returns=(0.01, 0.02),
                periods_per_year=periods_per_year,  # type: ignore[arg-type]
            )
        )


# ============================================================
# Risk Classification Tests
# ============================================================


@pytest.mark.parametrize(
    ("volatility", "expected_level"),
    [
        (0.00, "very_low"),
        (0.0499, "very_low"),
        (0.05, "low"),
        (0.0999, "low"),
        (0.10, "moderate"),
        (0.1499, "moderate"),
        (0.15, "high"),
        (0.2499, "high"),
        (0.25, "very_high"),
        (0.50, "very_high"),
    ],
)
def test_classify_volatility_risk(
    volatility: float,
    expected_level: RiskLevel,
) -> None:
    """
    Annualised volatility should map to the correct risk band.
    """

    result = classify_volatility_risk(
        volatility
    )

    assert result == expected_level


def test_classify_volatility_risk_rejects_negative_value() -> None:
    """
    Volatility cannot be negative.
    """

    with pytest.raises(
        VolatilityValidationError,
        match="cannot be negative",
    ):
        classify_volatility_risk(-0.01)


@pytest.mark.parametrize(
    "value",
    [
        True,
        float("nan"),
        float("inf"),
        "invalid",
    ],
)
def test_classify_volatility_risk_rejects_invalid_values(
    value: object,
) -> None:
    """
    Risk classification should reject invalid inputs.
    """

    with pytest.raises(VolatilityValidationError):
        classify_volatility_risk(  # type: ignore[arg-type]
            value
        )


# ============================================================
# Portfolio Volatility Tests
# ============================================================


def test_calculate_portfolio_volatility(
    monthly_returns: tuple[float, ...],
) -> None:
    """
    Portfolio API should delegate to the core calculation.
    """

    result = calculate_portfolio_volatility(
        monthly_returns,
        periods_per_year=12,
    )

    assert result.observation_count == len(
        monthly_returns
    )

    assert result.periods_per_year == 12
    assert result.annualised_volatility_decimal > 0.0


def test_calculate_portfolio_volatility_accepts_generator() -> None:
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

    result = calculate_portfolio_volatility(
        returns,
        periods_per_year=12,
    )

    assert result.observation_count == 3


def test_calculate_portfolio_volatility_rejects_string() -> None:
    """
    Strings must not be accepted as return iterables.
    """

    with pytest.raises(
        VolatilityValidationError,
        match="returns must be an iterable",
    ):
        calculate_portfolio_volatility(
            "invalid",  # type: ignore[arg-type]
            periods_per_year=12,
        )


def test_calculate_portfolio_volatility_rejects_non_iterable() -> None:
    """
    Non-iterable portfolio returns should be rejected.
    """

    with pytest.raises(
        VolatilityValidationError,
        match="returns must be an iterable",
    ):
        calculate_portfolio_volatility(
            123,  # type: ignore[arg-type]
            periods_per_year=12,
        )


# ============================================================
# Fund Volatility Tests
# ============================================================


def test_validate_fund_volatility_input(
    standard_fund_input: FundVolatilityInput,
) -> None:
    """
    Fund input validation should preserve metadata.
    """

    validated = validate_fund_volatility_input(
        standard_fund_input
    )

    assert validated.fund_name == "UTI Nifty 50 Index Fund"
    assert validated.scheme_code == "120716"
    assert validated.source == "Unit test"
    assert validated.periods_per_year == 12


def test_calculate_fund_volatility(
    standard_fund_input: FundVolatilityInput,
) -> None:
    """
    Fund API should return metadata and volatility metrics.
    """

    result = calculate_fund_volatility(
        standard_fund_input
    )

    assert result.fund_name == "UTI Nifty 50 Index Fund"
    assert result.scheme_code == "120716"
    assert result.source == "Unit test"
    assert result.result.observation_count == 6
    assert result.result.annualised_volatility_decimal > 0.0


def test_calculate_fund_volatility_strips_metadata() -> None:
    """
    Fund metadata should be trimmed.
    """

    result = calculate_fund_volatility(
        FundVolatilityInput(
            fund_name="  Example Fund  ",
            returns=(0.01, -0.01, 0.02),
            periods_per_year=12,
            scheme_code="  ABC123  ",
            source="  Unit test  ",
        )
    )

    assert result.fund_name == "Example Fund"
    assert result.scheme_code == "ABC123"
    assert result.source == "Unit test"


def test_calculate_fund_volatility_converts_blank_metadata_to_none() -> None:
    """
    Blank optional metadata should be normalised to None.
    """

    result = calculate_fund_volatility(
        FundVolatilityInput(
            fund_name="Example Fund",
            returns=(0.01, -0.01, 0.02),
            periods_per_year=12,
            scheme_code="   ",
            source="",
        )
    )

    assert result.scheme_code is None
    assert result.source is None


def test_calculate_fund_volatility_rejects_empty_name() -> None:
    """
    Fund names cannot be empty.
    """

    with pytest.raises(
        VolatilityValidationError,
        match="fund_name cannot be empty",
    ):
        calculate_fund_volatility(
            FundVolatilityInput(
                fund_name="   ",
                returns=(0.01, 0.02),
                periods_per_year=12,
            )
        )


def test_calculate_fund_volatility_rejects_wrong_input_type() -> None:
    """
    Fund API must reject unsupported objects.
    """

    with pytest.raises(
        TypeError,
        match="FundVolatilityInput",
    ):
        calculate_fund_volatility(  # type: ignore[arg-type]
            VolatilityInput(
                returns=(0.01, 0.02),
                periods_per_year=12,
            )
        )


# ============================================================
# Fund Batch Tests
# ============================================================


def test_calculate_fund_wise_volatility_all_successful() -> None:
    """
    All valid fund records should be successful.
    """

    funds = (
        FundVolatilityInput(
            fund_name="Fund A",
            returns=(0.01, -0.01, 0.02),
            periods_per_year=12,
        ),
        FundVolatilityInput(
            fund_name="Fund B",
            returns=(0.02, 0.01, -0.02),
            periods_per_year=12,
        ),
    )

    result = calculate_fund_wise_volatility(
        funds
    )

    assert result.total_received == 2
    assert result.successful_count == 2
    assert result.failed_count == 0
    assert len(result.successful) == 2
    assert result.failed == ()


def test_calculate_fund_wise_volatility_collects_invalid_fund() -> None:
    """
    Invalid fund records should not block valid records.
    """

    funds = (
        FundVolatilityInput(
            fund_name="Valid Fund",
            returns=(0.01, -0.01, 0.02),
            periods_per_year=12,
        ),
        FundVolatilityInput(
            fund_name="Invalid Fund",
            returns=(0.01,),
            periods_per_year=12,
            scheme_code="INVALID",
        ),
    )

    result = calculate_fund_wise_volatility(
        funds,
        fail_fast=False,
    )

    assert result.total_received == 2
    assert result.successful_count == 1
    assert result.failed_count == 1

    assert result.successful[0].fund_name == "Valid Fund"
    assert result.failed[0].fund_name == "Invalid Fund"
    assert result.failed[0].scheme_code == "INVALID"

    assert "At least two return observations" in (
        result.failed[0].error
    )


def test_calculate_fund_wise_volatility_fail_fast() -> None:
    """
    fail_fast=True should raise the first validation error.
    """

    funds = (
        FundVolatilityInput(
            fund_name="Invalid Fund",
            returns=(0.01,),
            periods_per_year=12,
        ),
    )

    with pytest.raises(
        VolatilityValidationError,
        match="At least two return observations",
    ):
        calculate_fund_wise_volatility(
            funds,
            fail_fast=True,
        )


def test_calculate_fund_wise_volatility_collects_wrong_record_type() -> None:
    """
    Unsupported records should be represented as failures.
    """

    records = (
        FundVolatilityInput(
            fund_name="Valid Fund",
            returns=(0.01, -0.01, 0.02),
            periods_per_year=12,
        ),
        "invalid record",
    )

    result = calculate_fund_wise_volatility(  # type: ignore[arg-type]
        records,
        fail_fast=False,
    )

    assert result.total_received == 2
    assert result.successful_count == 1
    assert result.failed_count == 1
    assert "Record at index 1" in result.failed[0].error


def test_calculate_fund_wise_volatility_rejects_invalid_fail_fast() -> None:
    """
    fail_fast must be a strict boolean.
    """

    with pytest.raises(
        VolatilityValidationError,
        match="fail_fast must be a boolean",
    ):
        calculate_fund_wise_volatility(
            (),
            fail_fast=1,  # type: ignore[arg-type]
        )


def test_calculate_fund_wise_volatility_rejects_string_iterable() -> None:
    """
    Strings must not be accepted as fund collections.
    """

    with pytest.raises(
        TypeError,
        match="iterable of FundVolatilityInput",
    ):
        calculate_fund_wise_volatility(
            "invalid",  # type: ignore[arg-type]
        )


def test_calculate_fund_wise_volatility_rejects_non_iterable() -> None:
    """
    Non-iterable fund input should be rejected.
    """

    with pytest.raises(
        TypeError,
        match="iterable of FundVolatilityInput",
    ):
        calculate_fund_wise_volatility(
            123,  # type: ignore[arg-type]
        )


# ============================================================
# Periodic Return Construction Tests
# ============================================================


def test_calculate_periodic_returns() -> None:
    """
    Value series should be converted to percentage returns.
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


def test_calculate_periodic_returns_accepts_generator() -> None:
    """
    Value conversion should accept valid iterables.
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


def test_calculate_periodic_returns_requires_three_values() -> None:
    """
    Three values are required to produce two return observations.
    """

    with pytest.raises(
        VolatilityValidationError,
        match="At least three values",
    ):
        calculate_periodic_returns(
            (
                100.0,
                110.0,
            )
        )


def test_calculate_periodic_returns_rejects_zero_previous_value() -> None:
    """
    A previous value of zero cannot be used as a return denominator.
    """

    with pytest.raises(
        VolatilityValidationError,
        match=r"values\[0\] must be greater than zero",
    ):
        calculate_periodic_returns(
            (
                0.0,
                100.0,
                110.0,
            )
        )


def test_calculate_periodic_returns_rejects_negative_previous_value() -> None:
    """
    Negative previous values cannot be used as return denominators.
    """

    with pytest.raises(
        VolatilityValidationError,
        match=r"values\[0\] must be greater than zero",
    ):
        calculate_periodic_returns(
            (
                -100.0,
                100.0,
                110.0,
            )
        )


def test_calculate_periodic_returns_allows_zero_final_value() -> None:
    """
    A final value of zero represents a valid -100% return.

    Zero is allowed only as the final observation because it is never
    used as the denominator for a subsequent return calculation.
    """

    result = calculate_periodic_returns(
        (
            100.0,
            50.0,
            0.0,
        )
    )

    def test_calculate_periodic_returns_allows_zero_final_value() -> None:
        """
         A final value of zero represents a valid -100% return.

        Zero is allowed only as the final observation because it is never
        used as the denominator for a subsequent return calculation.
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


def test_calculate_periodic_returns_rejects_string_iterable() -> None:
    """
    Strings must not be treated as value sequences.
    """

    with pytest.raises(
        VolatilityValidationError,
        match="values must be an iterable",
    ):
        calculate_periodic_returns(
            "invalid"  # type: ignore[arg-type]
        )


def test_calculate_periodic_returns_rejects_non_iterable() -> None:
    """
    Non-iterable values should be rejected.
    """

    with pytest.raises(
        VolatilityValidationError,
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
def test_calculate_periodic_returns_rejects_invalid_values(
    invalid_value: object,
) -> None:
    """
    Value observations must be finite non-boolean numbers.
    """

    with pytest.raises(VolatilityValidationError):
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


def test_round_volatility_result() -> None:
    """
    Result rounding should preserve non-numeric metadata.
    """

    original = VolatilityResult(
        observation_count=6,
        periods_per_year=12,
        periodic_volatility_decimal=0.012345,
        periodic_volatility_percent=1.2345,
        annualised_volatility_decimal=0.042765,
        annualised_volatility_percent=4.2765,
        mean_periodic_return_decimal=0.006789,
        mean_periodic_return_percent=0.6789,
        minimum_return_decimal=-0.023456,
        maximum_return_decimal=0.034567,
        risk_level="very_low",
    )

    rounded = round_volatility_result(
        original,
        decimal_places=2,
    )

    assert rounded.observation_count == 6
    assert rounded.periods_per_year == 12

    assert rounded.periodic_volatility_decimal == 0.01
    assert rounded.periodic_volatility_percent == 1.23

    assert rounded.annualised_volatility_decimal == 0.04
    assert rounded.annualised_volatility_percent == 4.28

    assert rounded.mean_periodic_return_decimal == 0.01
    assert rounded.mean_periodic_return_percent == 0.68

    assert rounded.minimum_return_decimal == -0.02
    assert rounded.maximum_return_decimal == 0.03

    assert rounded.risk_level == "very_low"

    assert original.periodic_volatility_decimal == 0.012345


def test_round_volatility_result_rejects_wrong_result_type() -> None:
    """
    Rounding should only accept VolatilityResult instances.
    """

    with pytest.raises(
        TypeError,
        match="VolatilityResult",
    ):
        round_volatility_result(  # type: ignore[arg-type]
            {
                "annualised_volatility_percent": 10.0,
            }
        )


def test_round_volatility_result_rejects_negative_decimal_places() -> None:
    """
    Decimal places cannot be negative.
    """

    result = calculate_volatility(
        VolatilityInput(
            returns=(0.01, -0.01, 0.02),
            periods_per_year=12,
        )
    )

    with pytest.raises(
        VolatilityValidationError,
        match="decimal_places cannot be negative",
    ):
        round_volatility_result(
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
def test_round_volatility_result_rejects_invalid_decimal_places(
    decimal_places: object,
) -> None:
    """
    decimal_places must be a strict integer.
    """

    result = calculate_volatility(
        VolatilityInput(
            returns=(0.01, -0.01, 0.02),
            periods_per_year=12,
        )
    )

    with pytest.raises(
        TypeError,
        match="decimal_places must be an integer",
    ):
        round_volatility_result(
            result,
            decimal_places=decimal_places,  # type: ignore[arg-type]
        )


# ============================================================
# Dataclass Immutability Tests
# ============================================================


def test_volatility_input_is_immutable() -> None:
    """
    VolatilityInput should be immutable.
    """

    input_data = VolatilityInput(
        returns=(0.01, 0.02),
        periods_per_year=12,
    )

    with pytest.raises(FrozenInstanceError):
        input_data.periods_per_year = 52  # type: ignore[misc]


def test_fund_volatility_input_is_immutable() -> None:
    """
    FundVolatilityInput should be immutable.
    """

    input_data = FundVolatilityInput(
        fund_name="Example Fund",
        returns=(0.01, 0.02),
        periods_per_year=12,
    )

    with pytest.raises(FrozenInstanceError):
        input_data.fund_name = "Changed Fund"  # type: ignore[misc]


def test_volatility_result_is_immutable() -> None:
    """
    VolatilityResult should be immutable.
    """

    result = calculate_volatility(
        VolatilityInput(
            returns=(0.01, -0.01, 0.02),
            periods_per_year=12,
        )
    )

    with pytest.raises(FrozenInstanceError):
        result.risk_level = "high"  # type: ignore[misc]


# ============================================================
# Consistency Tests
# ============================================================


def test_decimal_and_percent_metrics_are_consistent(
    standard_volatility_input: VolatilityInput,
) -> None:
    """
    Percentage metrics should equal decimal metrics multiplied by 100.
    """

    result = calculate_volatility(
        standard_volatility_input
    )

    assert result.periodic_volatility_percent == pytest.approx(
        result.periodic_volatility_decimal * 100.0,
        rel=1e-12,
    )

    assert result.annualised_volatility_percent == pytest.approx(
        result.annualised_volatility_decimal * 100.0,
        rel=1e-12,
    )

    assert result.mean_periodic_return_percent == pytest.approx(
        result.mean_periodic_return_decimal * 100.0,
        rel=1e-12,
    )


def test_risk_level_matches_annualised_volatility(
    standard_volatility_input: VolatilityInput,
) -> None:
    """
    Result risk level should match the public classification function.
    """

    result = calculate_volatility(
        standard_volatility_input
    )

    assert result.risk_level == classify_volatility_risk(
        result.annualised_volatility_decimal
    )