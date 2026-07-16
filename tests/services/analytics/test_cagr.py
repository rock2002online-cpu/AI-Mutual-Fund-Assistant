"""
Tests for services.analytics.cagr.

These tests validate:

- Explicit year-based CAGR
- Date-based CAGR
- Portfolio CAGR
- Fund-level CAGR
- Batch fund CAGR processing
- Defensive validation
- Result rounding
- Immutable dataclass behaviour
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date, datetime
from math import isclose

import pytest

from services.analytics.cagr import (
    CAGRInput,
    CAGRResult,
    CAGRValidationError,
    DateBasedCAGRInput,
    FundCAGRInput,
    calculate_cagr,
    calculate_date_based_cagr,
    calculate_fund_cagr,
    calculate_fund_wise_cagr,
    calculate_portfolio_cagr,
    round_cagr_result,
)


# ============================================================
# Shared Test Data
# ============================================================


@pytest.fixture
def standard_cagr_input() -> CAGRInput:
    """
    Return a standard three-year CAGR input.
    """

    return CAGRInput(
        initial_value=100_000.0,
        final_value=150_000.0,
        years=3.0,
    )


@pytest.fixture
def standard_fund_input() -> FundCAGRInput:
    """
    Return a valid fund-level CAGR input.
    """

    return FundCAGRInput(
        fund_name="UTI Nifty 50 Index Fund",
        initial_value=100_000.0,
        final_value=150_000.0,
        start_date=date(2023, 1, 1),
        end_date=date(2026, 1, 1),
        scheme_code="120716",
        source="Test data",
    )


# ============================================================
# Core CAGR Tests
# ============================================================


def test_calculate_cagr_returns_expected_result(
    standard_cagr_input: CAGRInput,
) -> None:
    """
    CAGR should match the standard compound-growth formula.
    """

    result = calculate_cagr(standard_cagr_input)

    expected_cagr = (
        standard_cagr_input.final_value
        / standard_cagr_input.initial_value
    ) ** (1.0 / standard_cagr_input.years) - 1.0

    assert isinstance(result, CAGRResult)

    assert isclose(
        result.cagr_decimal,
        expected_cagr,
        rel_tol=1e-12,
    )

    assert isclose(
        result.cagr_percent,
        expected_cagr * 100.0,
        rel_tol=1e-12,
    )

    assert result.absolute_gain == 50_000.0
    assert result.total_return_percent == 50.0
    assert result.initial_value == 100_000.0
    assert result.final_value == 150_000.0
    assert result.years == 3.0


def test_calculate_cagr_for_no_growth() -> None:
    """
    Equal initial and final values should produce zero CAGR.
    """

    result = calculate_cagr(
        CAGRInput(
            initial_value=100_000.0,
            final_value=100_000.0,
            years=5.0,
        )
    )

    assert result.cagr_decimal == pytest.approx(0.0)
    assert result.cagr_percent == pytest.approx(0.0)
    assert result.absolute_gain == pytest.approx(0.0)
    assert result.total_return_percent == pytest.approx(0.0)


def test_calculate_cagr_for_complete_loss() -> None:
    """
    A final value of zero should produce a CAGR of negative 100%.
    """

    result = calculate_cagr(
        CAGRInput(
            initial_value=100_000.0,
            final_value=0.0,
            years=2.0,
        )
    )

    assert result.cagr_decimal == pytest.approx(-1.0)
    assert result.cagr_percent == pytest.approx(-100.0)
    assert result.absolute_gain == pytest.approx(-100_000.0)
    assert result.total_return_percent == pytest.approx(-100.0)


def test_calculate_cagr_for_declining_investment() -> None:
    """
    A lower final value should produce a negative CAGR.
    """

    result = calculate_cagr(
        CAGRInput(
            initial_value=100_000.0,
            final_value=81_000.0,
            years=2.0,
        )
    )

    assert result.cagr_decimal == pytest.approx(-0.10)
    assert result.cagr_percent == pytest.approx(-10.0)


def test_calculate_cagr_for_one_year() -> None:
    """
    One-year CAGR should equal the total return.
    """

    result = calculate_cagr(
        CAGRInput(
            initial_value=100_000.0,
            final_value=125_000.0,
            years=1.0,
        )
    )

    assert result.cagr_decimal == pytest.approx(0.25)
    assert result.cagr_percent == pytest.approx(25.0)
    assert result.total_return_percent == pytest.approx(25.0)


def test_calculate_cagr_rejects_wrong_input_type() -> None:
    """
    The public API must reject unsupported input objects.
    """

    with pytest.raises(
        TypeError,
        match="CAGRInput",
    ):
        calculate_cagr(  # type: ignore[arg-type]
            {
                "initial_value": 100,
                "final_value": 120,
                "years": 1,
            }
        )


# ============================================================
# Date-Based CAGR Tests
# ============================================================


def test_calculate_date_based_cagr() -> None:
    """
    Date-based CAGR should annualise using the date interval.
    """

    result = calculate_date_based_cagr(
        DateBasedCAGRInput(
            initial_value=100_000.0,
            final_value=121_000.0,
            start_date=date(2023, 1, 1),
            end_date=date(2025, 1, 1),
        )
    )

    expected_years = 731 / 365.25

    expected_cagr = (
        121_000.0 / 100_000.0
    ) ** (1.0 / expected_years) - 1.0

    assert result.years == pytest.approx(expected_years)

    assert result.cagr_decimal == pytest.approx(
        expected_cagr,
        rel=1e-12,
    )


def test_date_based_cagr_accepts_datetime_values() -> None:
    """
    datetime inputs should be normalised to dates.
    """

    result = calculate_date_based_cagr(
        DateBasedCAGRInput(
            initial_value=100.0,
            final_value=110.0,
            start_date=datetime(2024, 1, 1, 9, 30),
            end_date=datetime(2025, 1, 1, 18, 45),
        )
    )

    assert result.cagr_percent > 0.0


def test_date_based_cagr_rejects_equal_dates() -> None:
    """
    Start and end dates cannot be identical.
    """

    with pytest.raises(
        CAGRValidationError,
        match="end_date must be later than start_date",
    ):
        calculate_date_based_cagr(
            DateBasedCAGRInput(
                initial_value=100.0,
                final_value=110.0,
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 1),
            )
        )


def test_date_based_cagr_rejects_reversed_dates() -> None:
    """
    End date cannot occur before the start date.
    """

    with pytest.raises(
        CAGRValidationError,
        match="end_date must be later than start_date",
    ):
        calculate_date_based_cagr(
            DateBasedCAGRInput(
                initial_value=100.0,
                final_value=110.0,
                start_date=date(2025, 1, 2),
                end_date=date(2025, 1, 1),
            )
        )


def test_date_based_cagr_rejects_invalid_date_type() -> None:
    """
    Strings should not be silently accepted as dates.
    """

    with pytest.raises(
        CAGRValidationError,
        match="start_date must be a date or datetime",
    ):
        calculate_date_based_cagr(
            DateBasedCAGRInput(
                initial_value=100.0,
                final_value=110.0,
                start_date="2024-01-01",  # type: ignore[arg-type]
                end_date=date(2025, 1, 1),
            )
        )


# ============================================================
# Portfolio CAGR Tests
# ============================================================


def test_calculate_portfolio_cagr() -> None:
    """
    Portfolio API should delegate to date-based CAGR calculation.
    """

    result = calculate_portfolio_cagr(
        initial_value=200_000.0,
        final_value=242_000.0,
        start_date=date(2023, 1, 1),
        end_date=date(2025, 1, 1),
    )

    assert result.initial_value == pytest.approx(200_000.0)
    assert result.final_value == pytest.approx(242_000.0)
    assert result.cagr_percent > 0.0


# ============================================================
# Fund CAGR Tests
# ============================================================


def test_calculate_fund_cagr(
    standard_fund_input: FundCAGRInput,
) -> None:
    """
    Fund-level calculation should preserve normalised metadata.
    """

    result = calculate_fund_cagr(
        standard_fund_input
    )

    assert result.fund_name == "UTI Nifty 50 Index Fund"
    assert result.scheme_code == "120716"
    assert result.source == "Test data"
    assert result.start_date == date(2023, 1, 1)
    assert result.end_date == date(2026, 1, 1)
    assert result.result.cagr_percent > 0.0


def test_calculate_fund_cagr_strips_text_fields() -> None:
    """
    Text metadata should be trimmed.
    """

    result = calculate_fund_cagr(
        FundCAGRInput(
            fund_name="  Example Fund  ",
            initial_value=100.0,
            final_value=120.0,
            start_date=date(2024, 1, 1),
            end_date=date(2025, 1, 1),
            scheme_code="  ABC123  ",
            source="  Unit test  ",
        )
    )

    assert result.fund_name == "Example Fund"
    assert result.scheme_code == "ABC123"
    assert result.source == "Unit test"


def test_calculate_fund_cagr_converts_blank_optional_text_to_none() -> None:
    """
    Blank optional metadata should be normalised to None.
    """

    result = calculate_fund_cagr(
        FundCAGRInput(
            fund_name="Example Fund",
            initial_value=100.0,
            final_value=120.0,
            start_date=date(2024, 1, 1),
            end_date=date(2025, 1, 1),
            scheme_code="   ",
            source="",
        )
    )

    assert result.scheme_code is None
    assert result.source is None


def test_calculate_fund_cagr_rejects_empty_fund_name() -> None:
    """
    Fund names cannot be empty.
    """

    with pytest.raises(
        CAGRValidationError,
        match="fund_name cannot be empty",
    ):
        calculate_fund_cagr(
            FundCAGRInput(
                fund_name="   ",
                initial_value=100.0,
                final_value=120.0,
                start_date=date(2024, 1, 1),
                end_date=date(2025, 1, 1),
            )
        )


def test_calculate_fund_cagr_rejects_wrong_input_type() -> None:
    """
    Fund API should reject unsupported input objects.
    """

    with pytest.raises(
        TypeError,
        match="FundCAGRInput",
    ):
        calculate_fund_cagr(  # type: ignore[arg-type]
            CAGRInput(
                initial_value=100.0,
                final_value=120.0,
                years=1.0,
            )
        )


# ============================================================
# Fund Batch Tests
# ============================================================


def test_calculate_fund_wise_cagr_all_successful() -> None:
    """
    Valid fund inputs should all be returned as successful.
    """

    funds = (
        FundCAGRInput(
            fund_name="Fund A",
            initial_value=100.0,
            final_value=120.0,
            start_date=date(2024, 1, 1),
            end_date=date(2025, 1, 1),
        ),
        FundCAGRInput(
            fund_name="Fund B",
            initial_value=200.0,
            final_value=242.0,
            start_date=date(2023, 1, 1),
            end_date=date(2025, 1, 1),
        ),
    )

    result = calculate_fund_wise_cagr(funds)

    assert result.total_received == 2
    assert result.successful_count == 2
    assert result.failed_count == 0
    assert len(result.successful) == 2
    assert result.failed == ()


def test_calculate_fund_wise_cagr_collects_invalid_funds() -> None:
    """
    Invalid funds should be collected without blocking valid calculations.
    """

    funds = (
        FundCAGRInput(
            fund_name="Valid Fund",
            initial_value=100.0,
            final_value=120.0,
            start_date=date(2024, 1, 1),
            end_date=date(2025, 1, 1),
        ),
        FundCAGRInput(
            fund_name="Invalid Fund",
            initial_value=0.0,
            final_value=120.0,
            start_date=date(2024, 1, 1),
            end_date=date(2025, 1, 1),
            scheme_code="INVALID",
        ),
    )

    result = calculate_fund_wise_cagr(
        funds,
        fail_fast=False,
    )

    assert result.total_received == 2
    assert result.successful_count == 1
    assert result.failed_count == 1

    assert result.successful[0].fund_name == "Valid Fund"
    assert result.failed[0].fund_name == "Invalid Fund"
    assert result.failed[0].scheme_code == "INVALID"
    assert "initial_value must be greater than zero" in (
        result.failed[0].error
    )


def test_calculate_fund_wise_cagr_fail_fast() -> None:
    """
    fail_fast=True should raise the first validation error.
    """

    funds = (
        FundCAGRInput(
            fund_name="Invalid Fund",
            initial_value=0.0,
            final_value=120.0,
            start_date=date(2024, 1, 1),
            end_date=date(2025, 1, 1),
        ),
    )

    with pytest.raises(
        CAGRValidationError,
        match="initial_value must be greater than zero",
    ):
        calculate_fund_wise_cagr(
            funds,
            fail_fast=True,
        )


def test_calculate_fund_wise_cagr_collects_wrong_record_type() -> None:
    """
    Unsupported records should be represented as batch failures.
    """

    records = (
        FundCAGRInput(
            fund_name="Valid Fund",
            initial_value=100.0,
            final_value=110.0,
            start_date=date(2024, 1, 1),
            end_date=date(2025, 1, 1),
        ),
        "invalid record",
    )

    result = calculate_fund_wise_cagr(  # type: ignore[arg-type]
        records,
        fail_fast=False,
    )

    assert result.total_received == 2
    assert result.successful_count == 1
    assert result.failed_count == 1
    assert "Record at index 1" in result.failed[0].error


def test_calculate_fund_wise_cagr_rejects_string_iterable() -> None:
    """
    Strings must not be treated as fund iterables.
    """

    with pytest.raises(
        TypeError,
        match="iterable of FundCAGRInput",
    ):
        calculate_fund_wise_cagr(  # type: ignore[arg-type]
            "not a fund collection"
        )


def test_calculate_fund_wise_cagr_rejects_non_iterable() -> None:
    """
    Non-iterable fund input should raise TypeError.
    """

    with pytest.raises(
        TypeError,
        match="iterable of FundCAGRInput",
    ):
        calculate_fund_wise_cagr(  # type: ignore[arg-type]
            123
        )


# ============================================================
# Validation Tests
# ============================================================


@pytest.mark.parametrize(
    ("initial_value", "expected_message"),
    [
        (0.0, "initial_value must be greater than zero"),
        (-100.0, "initial_value must be greater than zero"),
        (float("nan"), "initial_value must be finite"),
        (float("inf"), "initial_value must be finite"),
    ],
)
def test_invalid_initial_values(
    initial_value: float,
    expected_message: str,
) -> None:
    """
    Invalid initial values should be rejected.
    """

    with pytest.raises(
        CAGRValidationError,
        match=expected_message,
    ):
        calculate_cagr(
            CAGRInput(
                initial_value=initial_value,
                final_value=120.0,
                years=1.0,
            )
        )


@pytest.mark.parametrize(
    "final_value",
    [
        -1.0,
        -100.0,
    ],
)
def test_negative_final_values_are_rejected(
    final_value: float,
) -> None:
    """
    Final value cannot be negative.
    """

    with pytest.raises(
        CAGRValidationError,
        match="final_value cannot be negative",
    ):
        calculate_cagr(
            CAGRInput(
                initial_value=100.0,
                final_value=final_value,
                years=1.0,
            )
        )


@pytest.mark.parametrize(
    "years",
    [
        0.0,
        -1.0,
        -10.0,
    ],
)
def test_non_positive_years_are_rejected(
    years: float,
) -> None:
    """
    Investment period must be positive.
    """

    with pytest.raises(
        CAGRValidationError,
        match="years must be greater than zero",
    ):
        calculate_cagr(
            CAGRInput(
                initial_value=100.0,
                final_value=120.0,
                years=years,
            )
        )


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
    ],
)
def test_boolean_numeric_values_are_rejected(
    value: bool,
) -> None:
    """
    Python booleans must not be accepted as numeric values.
    """

    with pytest.raises(
        CAGRValidationError,
        match="cannot be a boolean",
    ):
        calculate_cagr(
            CAGRInput(
                initial_value=value,
                final_value=120.0,
                years=1.0,
            )
        )


def test_non_numeric_value_is_rejected() -> None:
    """
    Non-numeric text must not be converted silently.
    """

    with pytest.raises(
        CAGRValidationError,
        match="initial_value must be a valid numeric value",
    ):
        calculate_cagr(
            CAGRInput(
                initial_value="invalid",  # type: ignore[arg-type]
                final_value=120.0,
                years=1.0,
            )
        )


# ============================================================
# Rounding Tests
# ============================================================


def test_round_cagr_result() -> None:
    """
    Result utility should return a rounded immutable copy.
    """

    original = CAGRResult(
        initial_value=100.12345,
        final_value=150.98765,
        years=3.12345,
        cagr_decimal=0.1409876,
        cagr_percent=14.09876,
        absolute_gain=50.8642,
        total_return_percent=50.80231,
    )

    rounded = round_cagr_result(
        original,
        decimal_places=2,
    )

    assert rounded.initial_value == 100.12
    assert rounded.final_value == 150.99
    assert rounded.years == 3.12
    assert rounded.cagr_decimal == 0.14
    assert rounded.cagr_percent == 14.10
    assert rounded.absolute_gain == 50.86
    assert rounded.total_return_percent == 50.80

    assert original.initial_value == 100.12345


def test_round_cagr_result_rejects_wrong_result_type() -> None:
    """
    Rounding should only accept CAGRResult instances.
    """

    with pytest.raises(
        TypeError,
        match="CAGRResult",
    ):
        round_cagr_result(  # type: ignore[arg-type]
            {"cagr_percent": 10.0}
        )


def test_round_cagr_result_rejects_negative_decimal_places() -> None:
    """
    Decimal places cannot be negative.
    """

    result = calculate_cagr(
        CAGRInput(
            initial_value=100.0,
            final_value=120.0,
            years=1.0,
        )
    )

    with pytest.raises(
        CAGRValidationError,
        match="decimal_places cannot be negative",
    ):
        round_cagr_result(
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
def test_round_cagr_result_rejects_invalid_decimal_place_types(
    decimal_places: object,
) -> None:
    """
    decimal_places must be a strict integer.
    """

    result = calculate_cagr(
        CAGRInput(
            initial_value=100.0,
            final_value=120.0,
            years=1.0,
        )
    )

    with pytest.raises(
        TypeError,
        match="decimal_places must be an integer",
    ):
        round_cagr_result(
            result,
            decimal_places=decimal_places,  # type: ignore[arg-type]
        )


# ============================================================
# Dataclass Immutability Tests
# ============================================================


def test_cagr_input_is_immutable() -> None:
    """
    Input dataclasses should not be mutable after creation.
    """

    input_data = CAGRInput(
        initial_value=100.0,
        final_value=120.0,
        years=1.0,
    )

    with pytest.raises(FrozenInstanceError):
        input_data.initial_value = 200.0  # type: ignore[misc]


def test_cagr_result_is_immutable() -> None:
    """
    Result dataclasses should not be mutable after creation.
    """

    result = calculate_cagr(
        CAGRInput(
            initial_value=100.0,
            final_value=120.0,
            years=1.0,
        )
    )

    with pytest.raises(FrozenInstanceError):
        result.cagr_percent = 50.0  # type: ignore[misc]