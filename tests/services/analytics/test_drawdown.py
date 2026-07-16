"""
Tests for services.analytics.drawdown.

These tests validate:

- Drawdown-series generation
- Current drawdown
- Maximum drawdown
- Peak and trough identification
- Recovery detection
- Drawdown duration
- Portfolio drawdown
- Fund-wise drawdown
- Batch processing
- Observation construction utilities
- Defensive validation
- Result rounding
- Immutable dataclasses
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date, datetime

import pytest

from services.analytics.drawdown import (
    DrawdownInput,
    DrawdownPoint,
    DrawdownResult,
    DrawdownValidationError,
    FundDrawdownInput,
    ValueObservation,
    calculate_drawdown,
    calculate_drawdown_series,
    calculate_fund_drawdown,
    calculate_fund_wise_drawdown,
    calculate_portfolio_drawdown,
    classify_drawdown_risk,
    create_indexed_value_observations,
    create_value_observations,
    round_drawdown_result,
    validate_drawdown_input,
    validate_fund_drawdown_input,
)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def recovered_observations() -> tuple[ValueObservation, ...]:
    """
    Return a value series containing a recovered drawdown.
    """

    return (
        ValueObservation(
            observation_date=date(2024, 1, 1),
            value=100.0,
        ),
        ValueObservation(
            observation_date=date(2024, 1, 2),
            value=120.0,
        ),
        ValueObservation(
            observation_date=date(2024, 1, 3),
            value=90.0,
        ),
        ValueObservation(
            observation_date=date(2024, 1, 4),
            value=110.0,
        ),
        ValueObservation(
            observation_date=date(2024, 1, 5),
            value=120.0,
        ),
        ValueObservation(
            observation_date=date(2024, 1, 6),
            value=130.0,
        ),
    )


@pytest.fixture
def unrecovered_observations() -> tuple[ValueObservation, ...]:
    """
    Return a value series containing an unrecovered drawdown.
    """

    return (
        ValueObservation(
            observation_date=date(2024, 1, 1),
            value=100.0,
        ),
        ValueObservation(
            observation_date=date(2024, 1, 2),
            value=125.0,
        ),
        ValueObservation(
            observation_date=date(2024, 1, 3),
            value=100.0,
        ),
        ValueObservation(
            observation_date=date(2024, 1, 4),
            value=90.0,
        ),
        ValueObservation(
            observation_date=date(2024, 1, 5),
            value=105.0,
        ),
    )


@pytest.fixture
def standard_fund_input(
    recovered_observations: tuple[ValueObservation, ...],
) -> FundDrawdownInput:
    """
    Return a valid fund-level drawdown input.
    """

    return FundDrawdownInput(
        fund_name="UTI Nifty 50 Index Fund",
        observations=recovered_observations,
        scheme_code="120716",
        source="Unit test",
    )


# ============================================================
# Drawdown Series Tests
# ============================================================


def test_calculate_drawdown_series() -> None:
    """
    Drawdown series should track running peaks and declines.
    """

    observations = (
        ValueObservation(
            observation_date=date(2024, 1, 1),
            value=100.0,
        ),
        ValueObservation(
            observation_date=date(2024, 1, 2),
            value=120.0,
        ),
        ValueObservation(
            observation_date=date(2024, 1, 3),
            value=90.0,
        ),
        ValueObservation(
            observation_date=date(2024, 1, 4),
            value=110.0,
        ),
    )

    result = calculate_drawdown_series(
        observations
    )

    assert len(result) == 4

    assert result[0].running_peak == pytest.approx(100.0)
    assert result[0].drawdown_decimal == pytest.approx(0.0)

    assert result[1].running_peak == pytest.approx(120.0)
    assert result[1].drawdown_decimal == pytest.approx(0.0)

    assert result[2].running_peak == pytest.approx(120.0)
    assert result[2].drawdown_decimal == pytest.approx(-0.25)
    assert result[2].drawdown_percent == pytest.approx(-25.0)

    assert result[3].running_peak == pytest.approx(120.0)
    assert result[3].drawdown_decimal == pytest.approx(
        (110.0 / 120.0) - 1.0
    )


def test_drawdown_series_sorts_observations() -> None:
    """
    Unordered observations should be processed chronologically.
    """

    observations = (
        ValueObservation(
            observation_date=date(2024, 1, 3),
            value=90.0,
        ),
        ValueObservation(
            observation_date=date(2024, 1, 1),
            value=100.0,
        ),
        ValueObservation(
            observation_date=date(2024, 1, 2),
            value=120.0,
        ),
    )

    result = calculate_drawdown_series(
        observations
    )

    assert result[0].observation_date == date(
        2024,
        1,
        1,
    )

    assert result[-1].observation_date == date(
        2024,
        1,
        3,
    )


def test_drawdown_series_for_continuously_rising_values() -> None:
    """
    A continuously rising series should contain zero drawdowns.
    """

    observations = (
        ValueObservation(
            observation_date=date(2024, 1, 1),
            value=100.0,
        ),
        ValueObservation(
            observation_date=date(2024, 1, 2),
            value=110.0,
        ),
        ValueObservation(
            observation_date=date(2024, 1, 3),
            value=120.0,
        ),
    )

    result = calculate_drawdown_series(
        observations
    )

    assert all(
        point.drawdown_decimal == pytest.approx(0.0)
        for point in result
    )


# ============================================================
# Core Drawdown Tests
# ============================================================


def test_calculate_drawdown_recovered(
    recovered_observations: tuple[ValueObservation, ...],
) -> None:
    """
    Recovered drawdown should identify peak, trough, and recovery.
    """

    result = calculate_drawdown(
        DrawdownInput(
            observations=recovered_observations,
        )
    )

    assert isinstance(result, DrawdownResult)
    assert result.observation_count == 6

    assert result.start_date == date(2024, 1, 1)
    assert result.end_date == date(2024, 1, 6)

    assert result.starting_value == pytest.approx(100.0)
    assert result.ending_value == pytest.approx(130.0)

    assert result.maximum_drawdown_decimal == pytest.approx(
        -0.25
    )

    assert result.maximum_drawdown_percent == pytest.approx(
        -25.0
    )

    assert result.maximum_drawdown_peak_value == pytest.approx(
        120.0
    )

    assert result.maximum_drawdown_peak_date == date(
        2024,
        1,
        2,
    )

    assert result.maximum_drawdown_trough_value == pytest.approx(
        90.0
    )

    assert result.maximum_drawdown_trough_date == date(
        2024,
        1,
        3,
    )

    assert result.maximum_drawdown_duration_days == 1

    assert result.recovered is True
    assert result.recovery_date == date(2024, 1, 5)
    assert result.recovery_duration_days == 2
    assert result.underwater_duration_days == 3

    assert result.current_drawdown_decimal == pytest.approx(
        0.0
    )

    assert result.current_peak_value == pytest.approx(
        130.0
    )

    assert result.current_peak_date == date(
        2024,
        1,
        6,
    )

    assert result.risk_level == "high"


def test_calculate_drawdown_unrecovered(
    unrecovered_observations: tuple[ValueObservation, ...],
) -> None:
    """
    An unrecovered drawdown should report no recovery date.
    """

    result = calculate_drawdown(
        DrawdownInput(
            observations=unrecovered_observations,
        )
    )

    assert result.maximum_drawdown_decimal == pytest.approx(
        (90.0 / 125.0) - 1.0
    )

    assert result.maximum_drawdown_percent == pytest.approx(
        -28.0
    )

    assert result.maximum_drawdown_peak_date == date(
        2024,
        1,
        2,
    )

    assert result.maximum_drawdown_trough_date == date(
        2024,
        1,
        4,
    )

    assert result.recovered is False
    assert result.recovery_date is None
    assert result.recovery_duration_days is None

    assert result.underwater_duration_days == 3

    assert result.current_drawdown_decimal == pytest.approx(
        (105.0 / 125.0) - 1.0
    )


def test_calculate_drawdown_for_rising_series() -> None:
    """
    A rising series should have zero maximum drawdown.
    """

    observations = (
        ValueObservation(
            observation_date=date(2024, 1, 1),
            value=100.0,
        ),
        ValueObservation(
            observation_date=date(2024, 1, 2),
            value=110.0,
        ),
        ValueObservation(
            observation_date=date(2024, 1, 3),
            value=120.0,
        ),
    )

    result = calculate_drawdown(
        DrawdownInput(
            observations=observations,
        )
    )

    assert result.maximum_drawdown_decimal == pytest.approx(
        0.0
    )

    assert result.maximum_drawdown_percent == pytest.approx(
        0.0
    )

    assert result.current_drawdown_decimal == pytest.approx(
        0.0
    )

    assert result.recovered is False
    assert result.risk_level == "very_low"


def test_calculate_drawdown_for_flat_series() -> None:
    """
    A flat series should have zero drawdown.
    """

    observations = (
        ValueObservation(
            observation_date=date(2024, 1, 1),
            value=100.0,
        ),
        ValueObservation(
            observation_date=date(2024, 1, 2),
            value=100.0,
        ),
        ValueObservation(
            observation_date=date(2024, 1, 3),
            value=100.0,
        ),
    )

    result = calculate_drawdown(
        DrawdownInput(
            observations=observations,
        )
    )

    assert result.maximum_drawdown_decimal == pytest.approx(
        0.0
    )

    assert result.current_drawdown_decimal == pytest.approx(
        0.0
    )


def test_calculate_drawdown_rejects_wrong_input_type() -> None:
    """
    Core API should reject unsupported input objects.
    """

    with pytest.raises(
        TypeError,
        match="DrawdownInput",
    ):
        calculate_drawdown(  # type: ignore[arg-type]
            {
                "observations": (),
            }
        )


# ============================================================
# Input Validation Tests
# ============================================================


def test_validate_drawdown_input_sorts_observations() -> None:
    """
    Observations should be normalised into chronological order.
    """

    validated = validate_drawdown_input(
        DrawdownInput(
            observations=(
                ValueObservation(
                    observation_date=date(2024, 1, 2),
                    value=110.0,
                ),
                ValueObservation(
                    observation_date=date(2024, 1, 1),
                    value=100.0,
                ),
            )
        )
    )

    assert validated.observations[0].observation_date == date(
        2024,
        1,
        1,
    )


def test_validate_drawdown_input_normalises_datetime() -> None:
    """
    datetime observations should be converted to dates.
    """

    validated = validate_drawdown_input(
        DrawdownInput(
            observations=(
                ValueObservation(
                    observation_date=datetime(
                        2024,
                        1,
                        1,
                        10,
                        0,
                    ),
                    value=100.0,
                ),
                ValueObservation(
                    observation_date=datetime(
                        2024,
                        1,
                        2,
                        10,
                        0,
                    ),
                    value=110.0,
                ),
            )
        )
    )

    assert type(
        validated.observations[0].observation_date
    ) is date


def test_validate_drawdown_input_requires_two_observations() -> None:
    """
    At least two observations are required.
    """

    with pytest.raises(
        DrawdownValidationError,
        match="At least two value observations",
    ):
        validate_drawdown_input(
            DrawdownInput(
                observations=(
                    ValueObservation(
                        observation_date=date(2024, 1, 1),
                        value=100.0,
                    ),
                )
            )
        )


def test_validate_drawdown_input_rejects_empty_observations() -> None:
    """
    Empty observation collections should be rejected.
    """

    with pytest.raises(
        DrawdownValidationError,
        match="At least two value observations",
    ):
        validate_drawdown_input(
            DrawdownInput(
                observations=(),
            )
        )


def test_validate_drawdown_input_rejects_duplicate_dates() -> None:
    """
    Duplicate dates should be rejected.
    """

    with pytest.raises(
        DrawdownValidationError,
        match="Duplicate observation date",
    ):
        validate_drawdown_input(
            DrawdownInput(
                observations=(
                    ValueObservation(
                        observation_date=date(2024, 1, 1),
                        value=100.0,
                    ),
                    ValueObservation(
                        observation_date=date(2024, 1, 1),
                        value=110.0,
                    ),
                )
            )
        )


@pytest.mark.parametrize(
    "value",
    [
        0.0,
        -1.0,
        -100.0,
        float("nan"),
        float("inf"),
        True,
    ],
)
def test_validate_drawdown_input_rejects_invalid_values(
    value: float,
) -> None:
    """
    Observation values must be finite, non-boolean, and positive.
    """

    with pytest.raises(DrawdownValidationError):
        validate_drawdown_input(
            DrawdownInput(
                observations=(
                    ValueObservation(
                        observation_date=date(2024, 1, 1),
                        value=value,
                    ),
                    ValueObservation(
                        observation_date=date(2024, 1, 2),
                        value=110.0,
                    ),
                )
            )
        )


def test_validate_drawdown_input_rejects_invalid_date_type() -> None:
    """
    Observation dates must be date or datetime instances.
    """

    with pytest.raises(
        DrawdownValidationError,
        match="must be a date or datetime",
    ):
        validate_drawdown_input(
            DrawdownInput(
                observations=(
                    ValueObservation(
                        observation_date="2024-01-01",  # type: ignore[arg-type]
                        value=100.0,
                    ),
                    ValueObservation(
                        observation_date=date(2024, 1, 2),
                        value=110.0,
                    ),
                )
            )
        )


def test_validate_drawdown_input_rejects_wrong_observation_type() -> None:
    """
    Every observation must be a ValueObservation instance.
    """

    with pytest.raises(
        TypeError,
        match=r"observations\[1\].*ValueObservation",
    ):
        validate_drawdown_input(
            DrawdownInput(
                observations=(
                    ValueObservation(
                        observation_date=date(2024, 1, 1),
                        value=100.0,
                    ),
                    {
                        "observation_date": date(2024, 1, 2),
                        "value": 110.0,
                    },
                )  # type: ignore[arg-type]
            )
        )


def test_validate_drawdown_input_rejects_string_iterable() -> None:
    """
    Strings must not be treated as observation collections.
    """

    with pytest.raises(
        DrawdownValidationError,
        match="observations must be an iterable",
    ):
        validate_drawdown_input(
            DrawdownInput(
                observations="invalid",  # type: ignore[arg-type]
            )
        )


def test_validate_drawdown_input_rejects_non_iterable() -> None:
    """
    Non-iterable observations should be rejected.
    """

    with pytest.raises(
        DrawdownValidationError,
        match="observations must be an iterable",
    ):
        validate_drawdown_input(
            DrawdownInput(
                observations=123,  # type: ignore[arg-type]
            )
        )


# ============================================================
# Risk Classification Tests
# ============================================================


@pytest.mark.parametrize(
    ("drawdown", "expected_level"),
    [
        (0.0, "very_low"),
        (-0.0499, "very_low"),
        (-0.05, "low"),
        (-0.0999, "low"),
        (-0.10, "moderate"),
        (-0.1999, "moderate"),
        (-0.20, "high"),
        (-0.3499, "high"),
        (-0.35, "very_high"),
        (-0.60, "very_high"),
        (0.25, "high"),
    ],
)
def test_classify_drawdown_risk(
    drawdown: float,
    expected_level: str,
) -> None:
    """
    Drawdown magnitude should map to the expected risk band.
    """

    assert classify_drawdown_risk(
        drawdown
    ) == expected_level


@pytest.mark.parametrize(
    "invalid_value",
    [
        True,
        float("nan"),
        float("inf"),
        "invalid",
    ],
)
def test_classify_drawdown_risk_rejects_invalid_values(
    invalid_value: object,
) -> None:
    """
    Risk classification should reject invalid values.
    """

    with pytest.raises(DrawdownValidationError):
        classify_drawdown_risk(  # type: ignore[arg-type]
            invalid_value
        )


# ============================================================
# Portfolio Drawdown Tests
# ============================================================


def test_calculate_portfolio_drawdown(
    recovered_observations: tuple[ValueObservation, ...],
) -> None:
    """
    Portfolio API should delegate to the core calculation.
    """

    result = calculate_portfolio_drawdown(
        recovered_observations
    )

    assert result.observation_count == 6
    assert result.maximum_drawdown_percent == pytest.approx(
        -25.0
    )


def test_calculate_portfolio_drawdown_accepts_generator() -> None:
    """
    Portfolio API should accept valid observation iterables.
    """

    observations = (
        observation
        for observation in (
            ValueObservation(
                observation_date=date(2024, 1, 1),
                value=100.0,
            ),
            ValueObservation(
                observation_date=date(2024, 1, 2),
                value=90.0,
            ),
        )
    )

    result = calculate_portfolio_drawdown(
        observations
    )

    assert result.maximum_drawdown_percent == pytest.approx(
        -10.0
    )


def test_calculate_portfolio_drawdown_rejects_string() -> None:
    """
    Strings must not be accepted as observation collections.
    """

    with pytest.raises(
        DrawdownValidationError,
        match="observations must be an iterable",
    ):
        calculate_portfolio_drawdown(
            "invalid"  # type: ignore[arg-type]
        )


def test_calculate_portfolio_drawdown_rejects_non_iterable() -> None:
    """
    Non-iterable observations should be rejected.
    """

    with pytest.raises(
        DrawdownValidationError,
        match="observations must be an iterable",
    ):
        calculate_portfolio_drawdown(
            123  # type: ignore[arg-type]
        )


# ============================================================
# Fund Drawdown Tests
# ============================================================


def test_validate_fund_drawdown_input(
    standard_fund_input: FundDrawdownInput,
) -> None:
    """
    Fund validation should preserve metadata.
    """

    validated = validate_fund_drawdown_input(
        standard_fund_input
    )

    assert validated.fund_name == "UTI Nifty 50 Index Fund"
    assert validated.scheme_code == "120716"
    assert validated.source == "Unit test"


def test_calculate_fund_drawdown(
    standard_fund_input: FundDrawdownInput,
) -> None:
    """
    Fund API should return metadata and drawdown metrics.
    """

    result = calculate_fund_drawdown(
        standard_fund_input
    )

    assert result.fund_name == "UTI Nifty 50 Index Fund"
    assert result.scheme_code == "120716"
    assert result.source == "Unit test"

    assert result.result.maximum_drawdown_percent == pytest.approx(
        -25.0
    )


def test_calculate_fund_drawdown_strips_metadata(
    recovered_observations: tuple[ValueObservation, ...],
) -> None:
    """
    Fund metadata should be trimmed.
    """

    result = calculate_fund_drawdown(
        FundDrawdownInput(
            fund_name="  Example Fund  ",
            observations=recovered_observations,
            scheme_code="  ABC123  ",
            source="  Unit test  ",
        )
    )

    assert result.fund_name == "Example Fund"
    assert result.scheme_code == "ABC123"
    assert result.source == "Unit test"


def test_calculate_fund_drawdown_converts_blank_metadata_to_none(
    recovered_observations: tuple[ValueObservation, ...],
) -> None:
    """
    Blank optional metadata should be normalised to None.
    """

    result = calculate_fund_drawdown(
        FundDrawdownInput(
            fund_name="Example Fund",
            observations=recovered_observations,
            scheme_code="   ",
            source="",
        )
    )

    assert result.scheme_code is None
    assert result.source is None


def test_calculate_fund_drawdown_rejects_empty_name(
    recovered_observations: tuple[ValueObservation, ...],
) -> None:
    """
    Fund names cannot be empty.
    """

    with pytest.raises(
        DrawdownValidationError,
        match="fund_name cannot be empty",
    ):
        calculate_fund_drawdown(
            FundDrawdownInput(
                fund_name="   ",
                observations=recovered_observations,
            )
        )


def test_calculate_fund_drawdown_rejects_wrong_input_type() -> None:
    """
    Fund API should reject unsupported objects.
    """

    with pytest.raises(
        TypeError,
        match="FundDrawdownInput",
    ):
        calculate_fund_drawdown(  # type: ignore[arg-type]
            DrawdownInput(
                observations=(),
            )
        )


# ============================================================
# Fund Batch Tests
# ============================================================


def test_calculate_fund_wise_drawdown_all_successful(
    recovered_observations: tuple[ValueObservation, ...],
    unrecovered_observations: tuple[ValueObservation, ...],
) -> None:
    """
    All valid fund records should be successful.
    """

    funds = (
        FundDrawdownInput(
            fund_name="Fund A",
            observations=recovered_observations,
        ),
        FundDrawdownInput(
            fund_name="Fund B",
            observations=unrecovered_observations,
        ),
    )

    result = calculate_fund_wise_drawdown(
        funds
    )

    assert result.total_received == 2
    assert result.successful_count == 2
    assert result.failed_count == 0
    assert result.failed == ()


def test_calculate_fund_wise_drawdown_collects_invalid_fund(
    recovered_observations: tuple[ValueObservation, ...],
) -> None:
    """
    Invalid funds should not block valid calculations.
    """

    funds = (
        FundDrawdownInput(
            fund_name="Valid Fund",
            observations=recovered_observations,
        ),
        FundDrawdownInput(
            fund_name="Invalid Fund",
            observations=(
                ValueObservation(
                    observation_date=date(2024, 1, 1),
                    value=100.0,
                ),
            ),
            scheme_code="INVALID",
        ),
    )

    result = calculate_fund_wise_drawdown(
        funds,
        fail_fast=False,
    )

    assert result.total_received == 2
    assert result.successful_count == 1
    assert result.failed_count == 1

    assert result.failed[0].fund_name == "Invalid Fund"
    assert result.failed[0].scheme_code == "INVALID"

    assert "At least two value observations" in (
        result.failed[0].error
    )


def test_calculate_fund_wise_drawdown_fail_fast() -> None:
    """
    fail_fast=True should raise the first error.
    """

    funds = (
        FundDrawdownInput(
            fund_name="Invalid Fund",
            observations=(
                ValueObservation(
                    observation_date=date(2024, 1, 1),
                    value=100.0,
                ),
            ),
        ),
    )

    with pytest.raises(
        DrawdownValidationError,
        match="At least two value observations",
    ):
        calculate_fund_wise_drawdown(
            funds,
            fail_fast=True,
        )


def test_calculate_fund_wise_drawdown_collects_wrong_record_type(
    recovered_observations: tuple[ValueObservation, ...],
) -> None:
    """
    Unsupported records should be represented as failures.
    """

    records = (
        FundDrawdownInput(
            fund_name="Valid Fund",
            observations=recovered_observations,
        ),
        "invalid record",
    )

    result = calculate_fund_wise_drawdown(  # type: ignore[arg-type]
        records,
        fail_fast=False,
    )

    assert result.total_received == 2
    assert result.successful_count == 1
    assert result.failed_count == 1

    assert "Record at index 1" in result.failed[0].error


def test_calculate_fund_wise_drawdown_rejects_invalid_fail_fast() -> None:
    """
    fail_fast must be a strict boolean.
    """

    with pytest.raises(
        DrawdownValidationError,
        match="fail_fast must be a boolean",
    ):
        calculate_fund_wise_drawdown(
            (),
            fail_fast=1,  # type: ignore[arg-type]
        )


def test_calculate_fund_wise_drawdown_rejects_string_iterable() -> None:
    """
    Strings must not be accepted as fund collections.
    """

    with pytest.raises(
        TypeError,
        match="iterable of FundDrawdownInput",
    ):
        calculate_fund_wise_drawdown(
            "invalid"  # type: ignore[arg-type]
        )


def test_calculate_fund_wise_drawdown_rejects_non_iterable() -> None:
    """
    Non-iterable fund collections should be rejected.
    """

    with pytest.raises(
        TypeError,
        match="iterable of FundDrawdownInput",
    ):
        calculate_fund_wise_drawdown(
            123  # type: ignore[arg-type]
        )


# ============================================================
# Observation Construction Tests
# ============================================================


def test_create_value_observations() -> None:
    """
    Date-value pairs should become sorted observations.
    """

    result = create_value_observations(
        (
            (
                date(2024, 1, 2),
                110.0,
            ),
            (
                date(2024, 1, 1),
                100.0,
            ),
        )
    )

    assert len(result) == 2

    assert result[0] == ValueObservation(
        observation_date=date(2024, 1, 1),
        value=100.0,
    )


def test_create_value_observations_accepts_datetime() -> None:
    """
    datetime inputs should be normalised to dates.
    """

    result = create_value_observations(
        (
            (
                datetime(2024, 1, 1, 10, 0),
                100.0,
            ),
            (
                datetime(2024, 1, 2, 10, 0),
                110.0,
            ),
        )
    )

    assert type(result[0].observation_date) is date


def test_create_value_observations_rejects_invalid_pair() -> None:
    """
    Every record must be a two-item tuple.
    """

    with pytest.raises(
        DrawdownValidationError,
        match=r"values\[1\] must be a two-item tuple",
    ):
        create_value_observations(
            (
                (
                    date(2024, 1, 1),
                    100.0,
                ),
                (
                    date(2024, 1, 2),
                    110.0,
                    "extra",
                ),
            )  # type: ignore[arg-type]
        )


def test_create_value_observations_rejects_list_pair() -> None:
    """
    The production helper requires tuple pairs.
    """

    with pytest.raises(
        DrawdownValidationError,
        match="must be a two-item tuple",
    ):
        create_value_observations(
            (
                [
                    date(2024, 1, 1),
                    100.0,
                ],
                (
                    date(2024, 1, 2),
                    110.0,
                ),
            )  # type: ignore[arg-type]
        )


def test_create_indexed_value_observations() -> None:
    """
    Indexed helper should create consecutive dates.
    """

    result = create_indexed_value_observations(
        (
            100.0,
            90.0,
            110.0,
        ),
        start_date=date(2024, 1, 1),
    )

    assert result == (
        ValueObservation(
            observation_date=date(2024, 1, 1),
            value=100.0,
        ),
        ValueObservation(
            observation_date=date(2024, 1, 2),
            value=90.0,
        ),
        ValueObservation(
            observation_date=date(2024, 1, 3),
            value=110.0,
        ),
    )


def test_create_indexed_value_observations_accepts_datetime() -> None:
    """
    Indexed start datetime should be normalised.
    """

    result = create_indexed_value_observations(
        (
            100.0,
            110.0,
        ),
        start_date=datetime(
            2024,
            1,
            1,
            12,
            30,
        ),
    )

    assert type(result[0].observation_date) is date


def test_create_indexed_value_observations_requires_two_values() -> None:
    """
    At least two values are required.
    """

    with pytest.raises(
        DrawdownValidationError,
        match="At least two value observations",
    ):
        create_indexed_value_observations(
            (100.0,),
            start_date=date(2024, 1, 1),
        )


# ============================================================
# Rounding Tests
# ============================================================


def test_round_drawdown_result(
    recovered_observations: tuple[ValueObservation, ...],
) -> None:
    """
    Rounding should return a rounded copy and preserve metadata.
    """

    result = calculate_drawdown(
        DrawdownInput(
            observations=recovered_observations,
        )
    )

    rounded = round_drawdown_result(
        result,
        decimal_places=2,
    )

    assert rounded.observation_count == result.observation_count
    assert rounded.start_date == result.start_date
    assert rounded.end_date == result.end_date
    assert rounded.risk_level == result.risk_level
    assert rounded.recovered == result.recovered

    assert rounded.maximum_drawdown_percent == round(
        result.maximum_drawdown_percent,
        2,
    )

    assert len(rounded.drawdown_series) == len(
        result.drawdown_series
    )


def test_round_drawdown_result_rejects_wrong_result_type() -> None:
    """
    Rounding should accept only DrawdownResult instances.
    """

    with pytest.raises(
        TypeError,
        match="DrawdownResult",
    ):
        round_drawdown_result(  # type: ignore[arg-type]
            {
                "maximum_drawdown_percent": -10.0,
            }
        )


def test_round_drawdown_result_rejects_negative_decimal_places(
    recovered_observations: tuple[ValueObservation, ...],
) -> None:
    """
    Decimal places cannot be negative.
    """

    result = calculate_drawdown(
        DrawdownInput(
            observations=recovered_observations,
        )
    )

    with pytest.raises(
        DrawdownValidationError,
        match="decimal_places cannot be negative",
    ):
        round_drawdown_result(
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
def test_round_drawdown_result_rejects_invalid_decimal_places(
    decimal_places: object,
    recovered_observations: tuple[ValueObservation, ...],
) -> None:
    """
    decimal_places must be a strict integer.
    """

    result = calculate_drawdown(
        DrawdownInput(
            observations=recovered_observations,
        )
    )

    with pytest.raises(
        TypeError,
        match="decimal_places must be an integer",
    ):
        round_drawdown_result(
            result,
            decimal_places=decimal_places,  # type: ignore[arg-type]
        )


# ============================================================
# Dataclass Immutability Tests
# ============================================================


def test_value_observation_is_immutable() -> None:
    """
    ValueObservation should be immutable.
    """

    observation = ValueObservation(
        observation_date=date(2024, 1, 1),
        value=100.0,
    )

    with pytest.raises(FrozenInstanceError):
        observation.value = 120.0  # type: ignore[misc]


def test_drawdown_point_is_immutable() -> None:
    """
    DrawdownPoint should be immutable.
    """

    point = DrawdownPoint(
        observation_date=date(2024, 1, 1),
        value=100.0,
        running_peak=100.0,
        drawdown_decimal=0.0,
        drawdown_percent=0.0,
    )

    with pytest.raises(FrozenInstanceError):
        point.value = 90.0  # type: ignore[misc]


def test_drawdown_result_is_immutable(
    recovered_observations: tuple[ValueObservation, ...],
) -> None:
    """
    DrawdownResult should be immutable.
    """

    result = calculate_drawdown(
        DrawdownInput(
            observations=recovered_observations,
        )
    )

    with pytest.raises(FrozenInstanceError):
        result.recovered = False  # type: ignore[misc]


# ============================================================
# Consistency Tests
# ============================================================


def test_drawdown_percent_matches_decimal(
    recovered_observations: tuple[ValueObservation, ...],
) -> None:
    """
    Percentage drawdown should equal decimal drawdown multiplied by 100.
    """

    result = calculate_drawdown(
        DrawdownInput(
            observations=recovered_observations,
        )
    )

    assert result.maximum_drawdown_percent == pytest.approx(
        result.maximum_drawdown_decimal * 100.0
    )

    assert result.current_drawdown_percent == pytest.approx(
        result.current_drawdown_decimal * 100.0
    )


def test_result_series_matches_observation_count(
    recovered_observations: tuple[ValueObservation, ...],
) -> None:
    """
    Drawdown series should contain one point per observation.
    """

    result = calculate_drawdown(
        DrawdownInput(
            observations=recovered_observations,
        )
    )

    assert len(result.drawdown_series) == (
        result.observation_count
    )