"""
Tests for services.analytics.rolling_returns.

These tests validate:

- Rolling total returns
- Rolling annualised returns
- Best and worst rolling periods
- Positive-return consistency
- Target-return achievement
- Portfolio rolling returns
- Fund-wise rolling returns
- Batch processing
- Observation construction
- Defensive validation
- Result rounding
- Immutable dataclasses
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date, datetime

import pytest

from services.analytics.rolling_returns import (
    FundRollingReturnsInput,
    RollingReturnPoint,
    RollingReturnsInput,
    RollingReturnsResult,
    RollingReturnsValidationError,
    ValueObservation,
    calculate_fund_rolling_returns,
    calculate_fund_wise_rolling_returns,
    calculate_portfolio_rolling_returns,
    calculate_rolling_return_series,
    calculate_rolling_returns,
    classify_rolling_return_consistency,
    create_value_observations,
    round_rolling_returns_result,
    validate_fund_rolling_returns_input,
    validate_rolling_returns_input,
)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def monthly_observations() -> tuple[ValueObservation, ...]:
    """
    Return a representative monthly value series.
    """

    return (
        ValueObservation(
            observation_date=date(2024, 1, 1),
            value=100.0,
        ),
        ValueObservation(
            observation_date=date(2024, 2, 1),
            value=105.0,
        ),
        ValueObservation(
            observation_date=date(2024, 3, 1),
            value=110.0,
        ),
        ValueObservation(
            observation_date=date(2024, 4, 1),
            value=108.0,
        ),
        ValueObservation(
            observation_date=date(2024, 5, 1),
            value=115.0,
        ),
        ValueObservation(
            observation_date=date(2024, 6, 1),
            value=120.0,
        ),
    )


@pytest.fixture
def standard_input(
    monthly_observations: tuple[ValueObservation, ...],
) -> RollingReturnsInput:
    """
    Return a valid rolling-return input.
    """

    return RollingReturnsInput(
        observations=monthly_observations,
        window_size=2,
        annualise=False,
        target_return=0.05,
    )


@pytest.fixture
def standard_fund_input(
    monthly_observations: tuple[ValueObservation, ...],
) -> FundRollingReturnsInput:
    """
    Return a valid fund-level rolling-return input.
    """

    return FundRollingReturnsInput(
        fund_name="UTI Nifty 50 Index Fund",
        observations=monthly_observations,
        window_size=2,
        annualise=False,
        target_return=0.05,
        scheme_code="120716",
        source="Unit test",
    )


# ============================================================
# Rolling Return Series Tests
# ============================================================


def test_calculate_rolling_return_series(
    monthly_observations: tuple[ValueObservation, ...],
) -> None:
    """
    Rolling-return series should compare values separated by the window.
    """

    result = calculate_rolling_return_series(
        monthly_observations,
        window_size=2,
        annualise=False,
    )

    assert len(result) == 4

    first = result[0]

    assert first.start_date == date(2024, 1, 1)
    assert first.end_date == date(2024, 3, 1)

    assert first.start_value == pytest.approx(100.0)
    assert first.end_value == pytest.approx(110.0)

    assert first.total_return_decimal == pytest.approx(
        0.10
    )

    assert first.total_return_percent == pytest.approx(
        10.0
    )

    assert first.annualised_return_decimal is None
    assert first.annualised_return_percent is None


def test_rolling_series_annualised_return() -> None:
    """
    Annualised rolling return should use the actual date duration.
    """

    observations = (
        ValueObservation(
            observation_date=date(2023, 1, 1),
            value=100.0,
        ),
        ValueObservation(
            observation_date=date(2024, 1, 1),
            value=121.0,
        ),
    )

    result = calculate_rolling_return_series(
        observations,
        window_size=1,
        annualise=True,
    )

    assert len(result) == 1

    expected_years = 365 / 365.25

    expected_return = (
        121.0 / 100.0
    ) ** (1.0 / expected_years) - 1.0

    assert result[0].duration_days == 365

    assert result[0].duration_years == pytest.approx(
        expected_years
    )

    assert result[0].annualised_return_decimal == pytest.approx(
        expected_return,
        rel=1e-12,
    )


def test_rolling_series_sorts_observations() -> None:
    """
    Unordered observations should be processed chronologically.
    """

    observations = (
        ValueObservation(
            observation_date=date(2024, 3, 1),
            value=110.0,
        ),
        ValueObservation(
            observation_date=date(2024, 1, 1),
            value=100.0,
        ),
        ValueObservation(
            observation_date=date(2024, 2, 1),
            value=105.0,
        ),
    )

    result = calculate_rolling_return_series(
        observations,
        window_size=1,
        annualise=False,
    )

    assert result[0].start_date == date(
        2024,
        1,
        1,
    )

    assert result[0].end_date == date(
        2024,
        2,
        1,
    )


def test_rolling_series_rejects_window_equal_to_observation_count(
    monthly_observations: tuple[ValueObservation, ...],
) -> None:
    """
    Window size must be smaller than the observation count.
    """

    with pytest.raises(
        RollingReturnsValidationError,
        match="window_size must be smaller",
    ):
        calculate_rolling_return_series(
            monthly_observations,
            window_size=len(monthly_observations),
        )


def test_rolling_series_rejects_zero_window(
    monthly_observations: tuple[ValueObservation, ...],
) -> None:
    """
    Window size must be positive.
    """

    with pytest.raises(
        RollingReturnsValidationError,
        match="window_size must be greater than zero",
    ):
        calculate_rolling_return_series(
            monthly_observations,
            window_size=0,
        )


def test_rolling_series_rejects_invalid_annualise(
    monthly_observations: tuple[ValueObservation, ...],
) -> None:
    """
    annualise must be a strict boolean.
    """

    with pytest.raises(
        RollingReturnsValidationError,
        match="annualise must be a boolean",
    ):
        calculate_rolling_return_series(
            monthly_observations,
            window_size=2,
            annualise=1,  # type: ignore[arg-type]
        )


# ============================================================
# Core Rolling Return Tests
# ============================================================


def test_calculate_rolling_returns(
    standard_input: RollingReturnsInput,
) -> None:
    """
    Core rolling-return metrics should be calculated correctly.
    """

    result = calculate_rolling_returns(
        standard_input
    )

    expected_returns = (
        0.10,
        (108.0 / 105.0) - 1.0,
        (115.0 / 110.0) - 1.0,
        (120.0 / 108.0) - 1.0,
    )

    assert isinstance(result, RollingReturnsResult)

    assert result.observation_count == 6
    assert result.rolling_period_count == 4
    assert result.window_size == 2
    assert result.annualised is False

    assert result.average_return_decimal == pytest.approx(
        sum(expected_returns) / len(expected_returns)
    )

    assert result.best_return_decimal == pytest.approx(
        max(expected_returns)
    )

    assert result.worst_return_decimal == pytest.approx(
        min(expected_returns)
    )

    assert result.best_period in result.rolling_returns
    assert result.worst_period in result.rolling_returns


def test_calculate_rolling_returns_positive_counts() -> None:
    """
    Positive, negative, and zero periods should be counted.
    """

    observations = (
        ValueObservation(
            observation_date=date(2024, 1, 1),
            value=100.0,
        ),
        ValueObservation(
            observation_date=date(2024, 2, 1),
            value=110.0,
        ),
        ValueObservation(
            observation_date=date(2024, 3, 1),
            value=100.0,
        ),
        ValueObservation(
            observation_date=date(2024, 4, 1),
            value=100.0,
        ),
    )

    result = calculate_rolling_returns(
        RollingReturnsInput(
            observations=observations,
            window_size=1,
            annualise=False,
        )
    )

    assert result.positive_period_count == 1
    assert result.negative_period_count == 1
    assert result.zero_period_count == 1

    assert result.positive_period_frequency == pytest.approx(
        1 / 3
    )

    assert result.negative_period_frequency == pytest.approx(
        1 / 3
    )


def test_target_return_achievement() -> None:
    """
    Target-return success frequency should be calculated.
    """

    observations = (
        ValueObservation(
            observation_date=date(2024, 1, 1),
            value=100.0,
        ),
        ValueObservation(
            observation_date=date(2024, 2, 1),
            value=110.0,
        ),
        ValueObservation(
            observation_date=date(2024, 3, 1),
            value=115.0,
        ),
        ValueObservation(
            observation_date=date(2024, 4, 1),
            value=120.0,
        ),
    )

    result = calculate_rolling_returns(
        RollingReturnsInput(
            observations=observations,
            window_size=1,
            annualise=False,
            target_return=0.05,
        )
    )

    assert result.target_achieved_count == 1

    assert result.target_achieved_frequency == pytest.approx(
        1 / 3
    )


def test_target_fields_none_when_no_target(
    monthly_observations: tuple[ValueObservation, ...],
) -> None:
    """
    Target fields should remain None when no target is provided.
    """

    result = calculate_rolling_returns(
        RollingReturnsInput(
            observations=monthly_observations,
            window_size=2,
            annualise=False,
            target_return=None,
        )
    )

    assert result.target_return_decimal is None
    assert result.target_return_percent is None
    assert result.target_achieved_count is None
    assert result.target_achieved_frequency is None


def test_annualised_summary_uses_annualised_returns() -> None:
    """
    Summary metrics should use annualised returns when enabled.
    """

    observations = (
        ValueObservation(
            observation_date=date(2021, 1, 1),
            value=100.0,
        ),
        ValueObservation(
            observation_date=date(2022, 1, 1),
            value=110.0,
        ),
        ValueObservation(
            observation_date=date(2023, 1, 1),
            value=121.0,
        ),
    )

    result = calculate_rolling_returns(
        RollingReturnsInput(
            observations=observations,
            window_size=1,
            annualise=True,
        )
    )

    selected = tuple(
        point.annualised_return_decimal
        for point in result.rolling_returns
    )

    assert all(
        value is not None
        for value in selected
    )

    annualised_values = tuple(
        value
        for value in selected
        if value is not None
    )

    assert result.average_return_decimal == pytest.approx(
        sum(annualised_values) / len(annualised_values)
    )


def test_calculate_rolling_returns_rejects_wrong_input_type() -> None:
    """
    Core API should reject unsupported objects.
    """

    with pytest.raises(
        TypeError,
        match="RollingReturnsInput",
    ):
        calculate_rolling_returns(  # type: ignore[arg-type]
            {
                "observations": (),
            }
        )


# ============================================================
# Input Validation Tests
# ============================================================


def test_validate_rolling_returns_input(
    standard_input: RollingReturnsInput,
) -> None:
    """
    Valid input should be normalised and preserved.
    """

    validated = validate_rolling_returns_input(
        standard_input
    )

    assert validated.window_size == 2
    assert validated.annualise is False
    assert validated.target_return == pytest.approx(
        0.05
    )

    assert len(validated.observations) == 6


def test_validation_sorts_observations() -> None:
    """
    Observations should be sorted chronologically.
    """

    validated = validate_rolling_returns_input(
        RollingReturnsInput(
            observations=(
                ValueObservation(
                    observation_date=date(2024, 2, 1),
                    value=105.0,
                ),
                ValueObservation(
                    observation_date=date(2024, 1, 1),
                    value=100.0,
                ),
                ValueObservation(
                    observation_date=date(2024, 3, 1),
                    value=110.0,
                ),
            ),
            window_size=1,
        )
    )

    assert validated.observations[0].observation_date == date(
        2024,
        1,
        1,
    )


def test_validation_normalises_datetime() -> None:
    """
    datetime values should be converted to date instances.
    """

    validated = validate_rolling_returns_input(
        RollingReturnsInput(
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
                        2,
                        1,
                        10,
                        0,
                    ),
                    value=105.0,
                ),
            ),
            window_size=1,
        )
    )

    assert type(
        validated.observations[0].observation_date
    ) is date


def test_validation_requires_two_observations() -> None:
    """
    At least two observations are required.
    """

    with pytest.raises(
        RollingReturnsValidationError,
        match="At least two value observations",
    ):
        validate_rolling_returns_input(
            RollingReturnsInput(
                observations=(
                    ValueObservation(
                        observation_date=date(2024, 1, 1),
                        value=100.0,
                    ),
                ),
                window_size=1,
            )
        )


def test_validation_rejects_duplicate_dates() -> None:
    """
    Duplicate observation dates should be rejected.
    """

    with pytest.raises(
        RollingReturnsValidationError,
        match="Duplicate observation date",
    ):
        validate_rolling_returns_input(
            RollingReturnsInput(
                observations=(
                    ValueObservation(
                        observation_date=date(2024, 1, 1),
                        value=100.0,
                    ),
                    ValueObservation(
                        observation_date=date(2024, 1, 1),
                        value=110.0,
                    ),
                ),
                window_size=1,
            )
        )


@pytest.mark.parametrize(
    "value",
    [
        0.0,
        -1.0,
        float("nan"),
        float("inf"),
        True,
    ],
)
def test_validation_rejects_invalid_values(
    value: float,
) -> None:
    """
    Observation values must be finite and strictly positive.
    """

    with pytest.raises(RollingReturnsValidationError):
        validate_rolling_returns_input(
            RollingReturnsInput(
                observations=(
                    ValueObservation(
                        observation_date=date(2024, 1, 1),
                        value=value,
                    ),
                    ValueObservation(
                        observation_date=date(2024, 2, 1),
                        value=110.0,
                    ),
                ),
                window_size=1,
            )
        )


def test_validation_rejects_invalid_date() -> None:
    """
    Observation dates must be date or datetime values.
    """

    with pytest.raises(
        RollingReturnsValidationError,
        match="date or datetime",
    ):
        validate_rolling_returns_input(
            RollingReturnsInput(
                observations=(
                    ValueObservation(
                        observation_date="2024-01-01",  # type: ignore[arg-type]
                        value=100.0,
                    ),
                    ValueObservation(
                        observation_date=date(2024, 2, 1),
                        value=110.0,
                    ),
                ),
                window_size=1,
            )
        )


def test_validation_rejects_wrong_observation_type() -> None:
    """
    Every observation must be a ValueObservation instance.
    """

    with pytest.raises(
        TypeError,
        match=r"observations\[1\].*ValueObservation",
    ):
        validate_rolling_returns_input(
            RollingReturnsInput(
                observations=(
                    ValueObservation(
                        observation_date=date(2024, 1, 1),
                        value=100.0,
                    ),
                    {
                        "observation_date": date(2024, 2, 1),
                        "value": 110.0,
                    },
                ),  # type: ignore[arg-type]
                window_size=1,
            )
        )


def test_validation_rejects_string_observations() -> None:
    """
    Strings must not be interpreted as observation collections.
    """

    with pytest.raises(
        RollingReturnsValidationError,
        match="observations must be an iterable",
    ):
        validate_rolling_returns_input(
            RollingReturnsInput(
                observations="invalid",  # type: ignore[arg-type]
                window_size=1,
            )
        )


def test_validation_rejects_non_iterable_observations() -> None:
    """
    Non-iterable observations should be rejected.
    """

    with pytest.raises(
        RollingReturnsValidationError,
        match="observations must be an iterable",
    ):
        validate_rolling_returns_input(
            RollingReturnsInput(
                observations=123,  # type: ignore[arg-type]
                window_size=1,
            )
        )


@pytest.mark.parametrize(
    "window_size",
    [
        0,
        -1,
        True,
        1.5,
        "2",
    ],
)
def test_validation_rejects_invalid_window_size(
    window_size: object,
    monthly_observations: tuple[ValueObservation, ...],
) -> None:
    """
    window_size must be a strict positive integer.
    """

    with pytest.raises(RollingReturnsValidationError):
        validate_rolling_returns_input(
            RollingReturnsInput(
                observations=monthly_observations,
                window_size=window_size,  # type: ignore[arg-type]
            )
        )


def test_validation_rejects_large_window(
    monthly_observations: tuple[ValueObservation, ...],
) -> None:
    """
    Window must be smaller than the observation count.
    """

    with pytest.raises(
        RollingReturnsValidationError,
        match="window_size must be smaller",
    ):
        validate_rolling_returns_input(
            RollingReturnsInput(
                observations=monthly_observations,
                window_size=6,
            )
        )


@pytest.mark.parametrize(
    "annualise",
    [
        1,
        0,
        "true",
        None,
    ],
)
def test_validation_rejects_invalid_annualise(
    annualise: object,
    monthly_observations: tuple[ValueObservation, ...],
) -> None:
    """
    annualise must be a strict boolean.
    """

    with pytest.raises(
        RollingReturnsValidationError,
        match="annualise must be a boolean",
    ):
        validate_rolling_returns_input(
            RollingReturnsInput(
                observations=monthly_observations,
                window_size=2,
                annualise=annualise,  # type: ignore[arg-type]
            )
        )


@pytest.mark.parametrize(
    "target_return",
    [
        -1.0,
        -2.0,
        float("nan"),
        float("inf"),
        True,
    ],
)
def test_validation_rejects_invalid_target(
    target_return: object,
    monthly_observations: tuple[ValueObservation, ...],
) -> None:
    """
    Target return must be finite and greater than negative one.
    """

    with pytest.raises(RollingReturnsValidationError):
        validate_rolling_returns_input(
            RollingReturnsInput(
                observations=monthly_observations,
                window_size=2,
                target_return=target_return,  # type: ignore[arg-type]
            )
        )


# ============================================================
# Consistency Classification Tests
# ============================================================


@pytest.mark.parametrize(
    ("frequency", "expected_rating"),
    [
        (0.0, "poor"),
        (0.3999, "poor"),
        (0.40, "weak"),
        (0.5499, "weak"),
        (0.55, "moderate"),
        (0.6999, "moderate"),
        (0.70, "good"),
        (0.8499, "good"),
        (0.85, "excellent"),
        (1.0, "excellent"),
    ],
)
def test_classify_rolling_return_consistency(
    frequency: float,
    expected_rating: str,
) -> None:
    """
    Positive-period frequency should map to the expected rating.
    """

    assert classify_rolling_return_consistency(
        frequency
    ) == expected_rating


@pytest.mark.parametrize(
    "frequency",
    [
        -0.01,
        1.01,
        True,
        float("nan"),
        float("inf"),
        "invalid",
    ],
)
def test_classification_rejects_invalid_frequency(
    frequency: object,
) -> None:
    """
    Frequency must be finite and between zero and one.
    """

    with pytest.raises(RollingReturnsValidationError):
        classify_rolling_return_consistency(  # type: ignore[arg-type]
            frequency
        )


# ============================================================
# Portfolio API Tests
# ============================================================


def test_calculate_portfolio_rolling_returns(
    monthly_observations: tuple[ValueObservation, ...],
) -> None:
    """
    Portfolio API should delegate to the core calculation.
    """

    result = calculate_portfolio_rolling_returns(
        monthly_observations,
        window_size=2,
        annualise=False,
        target_return=0.05,
    )

    assert result.observation_count == 6
    assert result.rolling_period_count == 4
    assert result.window_size == 2


def test_portfolio_api_accepts_generator() -> None:
    """
    Portfolio API should accept valid iterables.
    """

    observations = (
        observation
        for observation in (
            ValueObservation(
                observation_date=date(2024, 1, 1),
                value=100.0,
            ),
            ValueObservation(
                observation_date=date(2024, 2, 1),
                value=105.0,
            ),
            ValueObservation(
                observation_date=date(2024, 3, 1),
                value=110.0,
            ),
        )
    )

    result = calculate_portfolio_rolling_returns(
        observations,
        window_size=1,
        annualise=False,
    )

    assert result.rolling_period_count == 2


def test_portfolio_api_rejects_string() -> None:
    """
    Strings must not be accepted as observation collections.
    """

    with pytest.raises(
        RollingReturnsValidationError,
        match="observations must be an iterable",
    ):
        calculate_portfolio_rolling_returns(
            "invalid",  # type: ignore[arg-type]
            window_size=1,
        )


def test_portfolio_api_rejects_non_iterable() -> None:
    """
    Non-iterable observations should be rejected.
    """

    with pytest.raises(
        RollingReturnsValidationError,
        match="observations must be an iterable",
    ):
        calculate_portfolio_rolling_returns(
            123,  # type: ignore[arg-type]
            window_size=1,
        )


# ============================================================
# Fund API Tests
# ============================================================


def test_validate_fund_rolling_returns_input(
    standard_fund_input: FundRollingReturnsInput,
) -> None:
    """
    Fund validation should preserve metadata.
    """

    validated = validate_fund_rolling_returns_input(
        standard_fund_input
    )

    assert validated.fund_name == "UTI Nifty 50 Index Fund"
    assert validated.scheme_code == "120716"
    assert validated.source == "Unit test"

    assert validated.window_size == 2
    assert validated.annualise is False


def test_calculate_fund_rolling_returns(
    standard_fund_input: FundRollingReturnsInput,
) -> None:
    """
    Fund API should return metadata and rolling metrics.
    """

    result = calculate_fund_rolling_returns(
        standard_fund_input
    )

    assert result.fund_name == "UTI Nifty 50 Index Fund"
    assert result.scheme_code == "120716"
    assert result.source == "Unit test"

    assert result.result.rolling_period_count == 4


def test_fund_api_strips_metadata(
    monthly_observations: tuple[ValueObservation, ...],
) -> None:
    """
    Fund metadata should be trimmed.
    """

    result = calculate_fund_rolling_returns(
        FundRollingReturnsInput(
            fund_name="  Example Fund  ",
            observations=monthly_observations,
            window_size=2,
            annualise=False,
            scheme_code="  ABC123  ",
            source="  Unit test  ",
        )
    )

    assert result.fund_name == "Example Fund"
    assert result.scheme_code == "ABC123"
    assert result.source == "Unit test"


def test_fund_api_converts_blank_metadata_to_none(
    monthly_observations: tuple[ValueObservation, ...],
) -> None:
    """
    Blank optional metadata should become None.
    """

    result = calculate_fund_rolling_returns(
        FundRollingReturnsInput(
            fund_name="Example Fund",
            observations=monthly_observations,
            window_size=2,
            annualise=False,
            scheme_code="   ",
            source="",
        )
    )

    assert result.scheme_code is None
    assert result.source is None


def test_fund_api_rejects_empty_name(
    monthly_observations: tuple[ValueObservation, ...],
) -> None:
    """
    Fund names cannot be empty.
    """

    with pytest.raises(
        RollingReturnsValidationError,
        match="fund_name cannot be empty",
    ):
        calculate_fund_rolling_returns(
            FundRollingReturnsInput(
                fund_name="   ",
                observations=monthly_observations,
                window_size=2,
            )
        )


def test_fund_api_rejects_wrong_type() -> None:
    """
    Fund API should reject unsupported input objects.
    """

    with pytest.raises(
        TypeError,
        match="FundRollingReturnsInput",
    ):
        calculate_fund_rolling_returns(  # type: ignore[arg-type]
            RollingReturnsInput(
                observations=(),
            )
        )


# ============================================================
# Fund Batch Tests
# ============================================================


def test_fund_batch_all_successful(
    monthly_observations: tuple[ValueObservation, ...],
) -> None:
    """
    All valid fund records should succeed.
    """

    funds = (
        FundRollingReturnsInput(
            fund_name="Fund A",
            observations=monthly_observations,
            window_size=2,
            annualise=False,
        ),
        FundRollingReturnsInput(
            fund_name="Fund B",
            observations=monthly_observations,
            window_size=1,
            annualise=False,
        ),
    )

    result = calculate_fund_wise_rolling_returns(
        funds
    )

    assert result.total_received == 2
    assert result.successful_count == 2
    assert result.failed_count == 0
    assert result.failed == ()


def test_fund_batch_collects_invalid_fund(
    monthly_observations: tuple[ValueObservation, ...],
) -> None:
    """
    Invalid records should not block valid fund calculations.
    """

    funds = (
        FundRollingReturnsInput(
            fund_name="Valid Fund",
            observations=monthly_observations,
            window_size=2,
            annualise=False,
        ),
        FundRollingReturnsInput(
            fund_name="Invalid Fund",
            observations=monthly_observations,
            window_size=6,
            annualise=False,
            scheme_code="INVALID",
        ),
    )

    result = calculate_fund_wise_rolling_returns(
        funds,
        fail_fast=False,
    )

    assert result.total_received == 2
    assert result.successful_count == 1
    assert result.failed_count == 1

    assert result.failed[0].fund_name == "Invalid Fund"
    assert result.failed[0].scheme_code == "INVALID"

    assert "window_size must be smaller" in (
        result.failed[0].error
    )


def test_fund_batch_fail_fast(
    monthly_observations: tuple[ValueObservation, ...],
) -> None:
    """
    fail_fast=True should raise the first validation error.
    """

    funds = (
        FundRollingReturnsInput(
            fund_name="Invalid Fund",
            observations=monthly_observations,
            window_size=6,
        ),
    )

    with pytest.raises(
        RollingReturnsValidationError,
        match="window_size must be smaller",
    ):
        calculate_fund_wise_rolling_returns(
            funds,
            fail_fast=True,
        )


def test_fund_batch_collects_wrong_record_type(
    monthly_observations: tuple[ValueObservation, ...],
) -> None:
    """
    Unsupported records should be represented as failures.
    """

    records = (
        FundRollingReturnsInput(
            fund_name="Valid Fund",
            observations=monthly_observations,
            window_size=2,
            annualise=False,
        ),
        "invalid record",
    )

    result = calculate_fund_wise_rolling_returns(  # type: ignore[arg-type]
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
        RollingReturnsValidationError,
        match="fail_fast must be a boolean",
    ):
        calculate_fund_wise_rolling_returns(
            (),
            fail_fast=1,  # type: ignore[arg-type]
        )


def test_fund_batch_rejects_string_iterable() -> None:
    """
    Strings must not be accepted as fund collections.
    """

    with pytest.raises(
        TypeError,
        match="iterable of FundRollingReturnsInput",
    ):
        calculate_fund_wise_rolling_returns(
            "invalid"  # type: ignore[arg-type]
        )


def test_fund_batch_rejects_non_iterable() -> None:
    """
    Non-iterable fund collections should be rejected.
    """

    with pytest.raises(
        TypeError,
        match="iterable of FundRollingReturnsInput",
    ):
        calculate_fund_wise_rolling_returns(
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
                date(2024, 2, 1),
                105.0,
            ),
            (
                date(2024, 1, 1),
                100.0,
            ),
        )
    )

    assert result == (
        ValueObservation(
            observation_date=date(2024, 1, 1),
            value=100.0,
        ),
        ValueObservation(
            observation_date=date(2024, 2, 1),
            value=105.0,
        ),
    )


def test_create_value_observations_accepts_datetime() -> None:
    """
    datetime values should be normalised to dates.
    """

    result = create_value_observations(
        (
            (
                datetime(2024, 1, 1, 10, 0),
                100.0,
            ),
            (
                datetime(2024, 2, 1, 10, 0),
                105.0,
            ),
        )
    )

    assert type(result[0].observation_date) is date


def test_create_value_observations_rejects_invalid_pair() -> None:
    """
    Every record must be a two-item tuple.
    """

    with pytest.raises(
        RollingReturnsValidationError,
        match=r"values\[1\] must be a two-item tuple",
    ):
        create_value_observations(
            (
                (
                    date(2024, 1, 1),
                    100.0,
                ),
                (
                    date(2024, 2, 1),
                    105.0,
                    "extra",
                ),
            )  # type: ignore[arg-type]
        )


def test_create_value_observations_rejects_list_pair() -> None:
    """
    The helper requires tuple pairs.
    """

    with pytest.raises(
        RollingReturnsValidationError,
        match="must be a two-item tuple",
    ):
        create_value_observations(
            (
                [
                    date(2024, 1, 1),
                    100.0,
                ],
                (
                    date(2024, 2, 1),
                    105.0,
                ),
            )  # type: ignore[arg-type]
        )


# ============================================================
# Result Rounding Tests
# ============================================================


def test_round_rolling_returns_result(
    standard_input: RollingReturnsInput,
) -> None:
    """
    Rounding should preserve metadata and rolling-period identity.
    """

    original = calculate_rolling_returns(
        standard_input
    )

    rounded = round_rolling_returns_result(
        original,
        decimal_places=2,
    )

    assert rounded.observation_count == (
        original.observation_count
    )

    assert rounded.rolling_period_count == (
        original.rolling_period_count
    )

    assert rounded.window_size == original.window_size
    assert rounded.annualised == original.annualised
    assert rounded.rating == original.rating

    assert rounded.average_return_percent == round(
        original.average_return_percent,
        2,
    )

    assert len(rounded.rolling_returns) == len(
        original.rolling_returns
    )


def test_round_preserves_optional_none_values(
    monthly_observations: tuple[ValueObservation, ...],
) -> None:
    """
    Optional target and annualised fields should remain None.
    """

    result = calculate_rolling_returns(
        RollingReturnsInput(
            observations=monthly_observations,
            window_size=2,
            annualise=False,
            target_return=None,
        )
    )

    rounded = round_rolling_returns_result(
        result,
        decimal_places=2,
    )

    assert rounded.target_return_decimal is None
    assert rounded.target_return_percent is None
    assert rounded.target_achieved_frequency is None

    assert all(
        point.annualised_return_decimal is None
        for point in rounded.rolling_returns
    )


def test_round_rejects_wrong_result_type() -> None:
    """
    Rounding should accept only RollingReturnsResult.
    """

    with pytest.raises(
        TypeError,
        match="RollingReturnsResult",
    ):
        round_rolling_returns_result(  # type: ignore[arg-type]
            {
                "average_return_percent": 10.0,
            }
        )


def test_round_rejects_negative_decimal_places(
    standard_input: RollingReturnsInput,
) -> None:
    """
    Decimal places cannot be negative.
    """

    result = calculate_rolling_returns(
        standard_input
    )

    with pytest.raises(
        RollingReturnsValidationError,
        match="decimal_places cannot be negative",
    ):
        round_rolling_returns_result(
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
def test_round_rejects_invalid_decimal_places(
    decimal_places: object,
    standard_input: RollingReturnsInput,
) -> None:
    """
    decimal_places must be a strict integer.
    """

    result = calculate_rolling_returns(
        standard_input
    )

    with pytest.raises(
        TypeError,
        match="decimal_places must be an integer",
    ):
        round_rolling_returns_result(
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


def test_rolling_return_point_is_immutable() -> None:
    """
    RollingReturnPoint should be immutable.
    """

    point = RollingReturnPoint(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 2, 1),
        start_value=100.0,
        end_value=110.0,
        duration_days=31,
        duration_years=31 / 365.25,
        total_return_decimal=0.10,
        total_return_percent=10.0,
        annualised_return_decimal=None,
        annualised_return_percent=None,
    )

    with pytest.raises(FrozenInstanceError):
        point.end_value = 120.0  # type: ignore[misc]


def test_rolling_returns_input_is_immutable(
    monthly_observations: tuple[ValueObservation, ...],
) -> None:
    """
    RollingReturnsInput should be immutable.
    """

    input_data = RollingReturnsInput(
        observations=monthly_observations,
        window_size=2,
    )

    with pytest.raises(FrozenInstanceError):
        input_data.window_size = 3  # type: ignore[misc]


def test_rolling_returns_result_is_immutable(
    standard_input: RollingReturnsInput,
) -> None:
    """
    RollingReturnsResult should be immutable.
    """

    result = calculate_rolling_returns(
        standard_input
    )

    with pytest.raises(FrozenInstanceError):
        result.rating = "excellent"  # type: ignore[misc]


# ============================================================
# Consistency Tests
# ============================================================


def test_decimal_and_percent_fields_are_consistent(
    standard_input: RollingReturnsInput,
) -> None:
    """
    Percentage fields should equal decimal fields multiplied by 100.
    """

    result = calculate_rolling_returns(
        standard_input
    )

    assert result.average_return_percent == pytest.approx(
        result.average_return_decimal * 100.0
    )

    assert result.median_return_percent == pytest.approx(
        result.median_return_decimal * 100.0
    )

    assert result.best_return_percent == pytest.approx(
        result.best_return_decimal * 100.0
    )

    assert result.worst_return_percent == pytest.approx(
        result.worst_return_decimal * 100.0
    )

    for point in result.rolling_returns:
        assert point.total_return_percent == pytest.approx(
            point.total_return_decimal * 100.0
        )

        if point.annualised_return_decimal is not None:
            assert (
                point.annualised_return_percent
                == pytest.approx(
                    point.annualised_return_decimal * 100.0
                )
            )


def test_rating_matches_public_classifier(
    standard_input: RollingReturnsInput,
) -> None:
    """
    Result rating should match the public classification function.
    """

    result = calculate_rolling_returns(
        standard_input
    )

    assert result.rating == (
        classify_rolling_return_consistency(
            result.positive_period_frequency
        )
    )


def test_best_and_worst_periods_match_summary(
    standard_input: RollingReturnsInput,
) -> None:
    """
    Best and worst period values should match summary values.
    """

    result = calculate_rolling_returns(
        standard_input
    )

    assert result.best_period.total_return_decimal == pytest.approx(
        result.best_return_decimal
    )

    assert result.worst_period.total_return_decimal == pytest.approx(
        result.worst_return_decimal
    )