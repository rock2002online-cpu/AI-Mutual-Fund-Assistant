"""
Tests for services.analytics.xirr.

These tests validate:

- XNPV calculations
- Standard XIRR calculations
- Portfolio XIRR
- Fund-wise XIRR
- Batch processing
- Input validation
- Solver metadata
- Cash-flow normalisation
- Valuation cash-flow construction
- Result rounding
- Immutable dataclasses
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date, datetime
from math import isclose

import pytest

from services.analytics.xirr import (
    CashFlow,
    FundXIRRInput,
    XIRRConvergenceError,
    XIRRInput,
    XIRRResult,
    XIRRValidationError,
    calculate_fund_wise_xirr,
    calculate_fund_xirr,
    calculate_portfolio_xirr,
    calculate_xirr,
    calculate_xnpv,
    create_valuation_cash_flow,
    round_xirr_result,
    validate_fund_xirr_input,
    validate_xirr_input,
)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def one_year_cash_flows() -> tuple[CashFlow, ...]:
    """
    Return a simple one-year investment and redemption sequence.
    """

    return (
        CashFlow(
            amount=-100_000.0,
            flow_date=date(2023, 1, 1),
        ),
        CashFlow(
            amount=120_000.0,
            flow_date=date(2024, 1, 1),
        ),
    )


@pytest.fixture
def sip_cash_flows() -> tuple[CashFlow, ...]:
    """
    Return a simple SIP-style irregular cash-flow sequence.
    """

    return (
        CashFlow(
            amount=-10_000.0,
            flow_date=date(2023, 1, 1),
        ),
        CashFlow(
            amount=-10_000.0,
            flow_date=date(2023, 2, 1),
        ),
        CashFlow(
            amount=-10_000.0,
            flow_date=date(2023, 3, 1),
        ),
        CashFlow(
            amount=-10_000.0,
            flow_date=date(2023, 4, 1),
        ),
        CashFlow(
            amount=44_000.0,
            flow_date=date(2024, 1, 1),
        ),
    )


@pytest.fixture
def standard_fund_input(
    sip_cash_flows: tuple[CashFlow, ...],
) -> FundXIRRInput:
    """
    Return a valid fund-level XIRR input.
    """

    return FundXIRRInput(
        fund_name="UTI Nifty 50 Index Fund",
        cash_flows=sip_cash_flows,
        scheme_code="120716",
        source="Unit test",
    )


# ============================================================
# XNPV Tests
# ============================================================


def test_calculate_xnpv_at_zero_rate() -> None:
    """
    At a zero discount rate, XNPV should equal the sum of cash flows.
    """

    cash_flows = (
        CashFlow(
            amount=-100.0,
            flow_date=date(2023, 1, 1),
        ),
        CashFlow(
            amount=40.0,
            flow_date=date(2023, 6, 1),
        ),
        CashFlow(
            amount=70.0,
            flow_date=date(2024, 1, 1),
        ),
    )

    result = calculate_xnpv(
        0.0,
        cash_flows,
    )

    assert result == pytest.approx(10.0)


def test_calculate_xnpv_near_solved_rate(
    one_year_cash_flows: tuple[CashFlow, ...],
) -> None:
    """
    XNPV should be close to zero at the calculated XIRR.
    """

    result = calculate_xirr(
        XIRRInput(
            cash_flows=one_year_cash_flows,
        )
    )

    xnpv = calculate_xnpv(
        result.annual_return_decimal,
        one_year_cash_flows,
    )

    assert abs(xnpv) < 0.05


def test_calculate_xnpv_rejects_rate_below_negative_one(
    one_year_cash_flows: tuple[CashFlow, ...],
) -> None:
    """
    Rates at or below negative 100% are invalid.
    """

    with pytest.raises(
        XIRRValidationError,
        match="rate must be greater than -1.0",
    ):
        calculate_xnpv(
            -1.0,
            one_year_cash_flows,
        )


def test_calculate_xnpv_rejects_invalid_cash_flow_iterable() -> None:
    """
    Strings must not be treated as cash-flow collections.
    """

    with pytest.raises(
        TypeError,
        match="iterable of CashFlow",
    ):
        calculate_xnpv(
            0.10,
            "invalid",  # type: ignore[arg-type]
        )


# ============================================================
# Core XIRR Tests
# ============================================================


def test_calculate_xirr_for_one_year_growth(
    one_year_cash_flows: tuple[CashFlow, ...],
) -> None:
    """
    A one-year investment growing from 100,000 to 120,000 should
    produce approximately a 20% annual return.
    """

    result = calculate_xirr(
        XIRRInput(
            cash_flows=one_year_cash_flows,
        )
    )

    assert isinstance(result, XIRRResult)
    assert result.converged is True
    assert result.iterations > 0

    assert result.solver in {
        "newton_raphson",
        "bisection",
    }

    assert result.annual_return_decimal == pytest.approx(
        0.20015,
        abs=0.001,
    )

    assert result.annual_return_percent == pytest.approx(
        20.015,
        abs=0.1,
    )


def test_calculate_xirr_for_no_growth() -> None:
    """
    Equal investment and terminal values over one year should produce
    approximately zero XIRR.
    """

    result = calculate_xirr(
        XIRRInput(
            cash_flows=(
                CashFlow(
                    amount=-100_000.0,
                    flow_date=date(2023, 1, 1),
                ),
                CashFlow(
                    amount=100_000.0,
                    flow_date=date(2024, 1, 1),
                ),
            )
        )
    )

    assert result.annual_return_decimal == pytest.approx(
        0.0,
        abs=1e-6,
    )

    assert result.annual_return_percent == pytest.approx(
        0.0,
        abs=1e-4,
    )


def test_calculate_xirr_for_loss() -> None:
    """
    A lower final value should produce a negative annual return.
    """

    result = calculate_xirr(
        XIRRInput(
            cash_flows=(
                CashFlow(
                    amount=-100_000.0,
                    flow_date=date(2023, 1, 1),
                ),
                CashFlow(
                    amount=90_000.0,
                    flow_date=date(2024, 1, 1),
                ),
            )
        )
    )

    assert result.annual_return_decimal < 0.0
    assert result.annual_return_percent < 0.0

    assert result.annual_return_percent == pytest.approx(
        -10.0,
        abs=0.1,
    )


def test_calculate_xirr_for_multiple_cash_flows(
    sip_cash_flows: tuple[CashFlow, ...],
) -> None:
    """
    SIP-style irregular cash flows should produce a finite result.
    """

    result = calculate_xirr(
        XIRRInput(
            cash_flows=sip_cash_flows,
        )
    )

    assert result.converged is True
    assert result.iterations > 0
    assert result.annual_return_decimal > -1.0
    assert result.annual_return_percent > 0.0


def test_calculate_xirr_accepts_datetime_values() -> None:
    """
    datetime cash-flow values should be normalised to dates.
    """

    result = calculate_xirr(
        XIRRInput(
            cash_flows=(
                CashFlow(
                    amount=-100.0,
                    flow_date=datetime(
                        2023,
                        1,
                        1,
                        9,
                        30,
                    ),
                ),
                CashFlow(
                    amount=110.0,
                    flow_date=datetime(
                        2024,
                        1,
                        1,
                        16,
                        0,
                    ),
                ),
            )
        )
    )

    assert result.converged is True
    assert result.annual_return_percent > 0.0


def test_calculate_xirr_rejects_wrong_input_type() -> None:
    """
    The public API must reject unsupported input objects.
    """

    with pytest.raises(
        TypeError,
        match="XIRRInput",
    ):
        calculate_xirr(  # type: ignore[arg-type]
            {
                "cash_flows": [],
            }
        )


# ============================================================
# Validation Tests
# ============================================================


def test_validate_xirr_input_sorts_cash_flows() -> None:
    """
    Cash flows should be normalised into chronological order.
    """

    input_data = XIRRInput(
        cash_flows=(
            CashFlow(
                amount=120.0,
                flow_date=date(2024, 1, 1),
            ),
            CashFlow(
                amount=-100.0,
                flow_date=date(2023, 1, 1),
            ),
        )
    )

    validated = validate_xirr_input(input_data)

    assert validated.cash_flows[0].flow_date == date(
        2023,
        1,
        1,
    )

    assert validated.cash_flows[1].flow_date == date(
        2024,
        1,
        1,
    )


def test_validate_xirr_input_normalises_datetime() -> None:
    """
    datetime values should be converted to date values.
    """

    validated = validate_xirr_input(
        XIRRInput(
            cash_flows=(
                CashFlow(
                    amount=-100.0,
                    flow_date=datetime(
                        2023,
                        1,
                        1,
                        10,
                        0,
                    ),
                ),
                CashFlow(
                    amount=120.0,
                    flow_date=datetime(
                        2024,
                        1,
                        1,
                        10,
                        0,
                    ),
                ),
            )
        )
    )

    assert type(validated.cash_flows[0].flow_date) is date
    assert type(validated.cash_flows[1].flow_date) is date


def test_validate_xirr_input_rejects_one_cash_flow() -> None:
    """
    At least two cash flows are required.
    """

    with pytest.raises(
        XIRRValidationError,
        match="At least two cash flows",
    ):
        validate_xirr_input(
            XIRRInput(
                cash_flows=(
                    CashFlow(
                        amount=-100.0,
                        flow_date=date(2024, 1, 1),
                    ),
                )
            )
        )


def test_validate_xirr_input_requires_negative_cash_flow() -> None:
    """
    At least one investment cash flow must be negative.
    """

    with pytest.raises(
        XIRRValidationError,
        match="negative cash flow",
    ):
        validate_xirr_input(
            XIRRInput(
                cash_flows=(
                    CashFlow(
                        amount=100.0,
                        flow_date=date(2023, 1, 1),
                    ),
                    CashFlow(
                        amount=120.0,
                        flow_date=date(2024, 1, 1),
                    ),
                )
            )
        )


def test_validate_xirr_input_requires_positive_cash_flow() -> None:
    """
    At least one cash flow must be positive.
    """

    with pytest.raises(
        XIRRValidationError,
        match="positive cash flow",
    ):
        validate_xirr_input(
            XIRRInput(
                cash_flows=(
                    CashFlow(
                        amount=-100.0,
                        flow_date=date(2023, 1, 1),
                    ),
                    CashFlow(
                        amount=-20.0,
                        flow_date=date(2024, 1, 1),
                    ),
                )
            )
        )


def test_validate_xirr_input_requires_multiple_dates() -> None:
    """
    Cash flows must span at least two different dates.
    """

    with pytest.raises(
        XIRRValidationError,
        match="span at least two dates",
    ):
        validate_xirr_input(
            XIRRInput(
                cash_flows=(
                    CashFlow(
                        amount=-100.0,
                        flow_date=date(2024, 1, 1),
                    ),
                    CashFlow(
                        amount=120.0,
                        flow_date=date(2024, 1, 1),
                    ),
                )
            )
        )


@pytest.mark.parametrize(
    "guess",
    [
        -1.0,
        -2.0,
        float("-inf"),
        float("nan"),
    ],
)
def test_validate_xirr_input_rejects_invalid_guess(
    guess: float,
    one_year_cash_flows: tuple[CashFlow, ...],
) -> None:
    """
    Initial guesses must be finite and greater than negative one.
    """

    with pytest.raises(XIRRValidationError):
        validate_xirr_input(
            XIRRInput(
                cash_flows=one_year_cash_flows,
                guess=guess,
            )
        )


@pytest.mark.parametrize(
    "tolerance",
    [
        0.0,
        -1e-7,
        float("nan"),
        float("inf"),
    ],
)
def test_validate_xirr_input_rejects_invalid_tolerance(
    tolerance: float,
    one_year_cash_flows: tuple[CashFlow, ...],
) -> None:
    """
    Tolerance must be finite and greater than zero.
    """

    with pytest.raises(XIRRValidationError):
        validate_xirr_input(
            XIRRInput(
                cash_flows=one_year_cash_flows,
                tolerance=tolerance,
            )
        )


@pytest.mark.parametrize(
    "max_iterations",
    [
        0,
        -1,
        True,
        10.5,
        "100",
    ],
)
def test_validate_xirr_input_rejects_invalid_max_iterations(
    max_iterations: object,
    one_year_cash_flows: tuple[CashFlow, ...],
) -> None:
    """
    max_iterations must be a strict positive integer.
    """

    with pytest.raises(XIRRValidationError):
        validate_xirr_input(
            XIRRInput(
                cash_flows=one_year_cash_flows,
                max_iterations=max_iterations,  # type: ignore[arg-type]
            )
        )


@pytest.mark.parametrize(
    "amount",
    [
        True,
        False,
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_validate_xirr_input_rejects_invalid_amount(
    amount: float,
) -> None:
    """
    Cash-flow amounts must be finite non-boolean numbers.
    """

    with pytest.raises(XIRRValidationError):
        validate_xirr_input(
            XIRRInput(
                cash_flows=(
                    CashFlow(
                        amount=amount,
                        flow_date=date(2023, 1, 1),
                    ),
                    CashFlow(
                        amount=120.0,
                        flow_date=date(2024, 1, 1),
                    ),
                )
            )
        )


def test_validate_xirr_input_rejects_invalid_date_type() -> None:
    """
    Cash-flow dates must be date or datetime instances.
    """

    with pytest.raises(
        XIRRValidationError,
        match="flow_date must be a date or datetime",
    ):
        validate_xirr_input(
            XIRRInput(
                cash_flows=(
                    CashFlow(
                        amount=-100.0,
                        flow_date="2023-01-01",  # type: ignore[arg-type]
                    ),
                    CashFlow(
                        amount=120.0,
                        flow_date=date(2024, 1, 1),
                    ),
                )
            )
        )


def test_validate_xirr_input_rejects_wrong_cash_flow_type() -> None:
    """
    Every cash-flow record must be a CashFlow instance.
    """

    with pytest.raises(
        TypeError,
        match="instance of CashFlow",
    ):
        validate_xirr_input(
            XIRRInput(
                cash_flows=(
                    CashFlow(
                        amount=-100.0,
                        flow_date=date(2023, 1, 1),
                    ),
                    {
                        "amount": 120.0,
                        "flow_date": date(2024, 1, 1),
                    },
                )  # type: ignore[arg-type]
            )
        )


# ============================================================
# Portfolio XIRR Tests
# ============================================================


def test_calculate_portfolio_xirr(
    one_year_cash_flows: tuple[CashFlow, ...],
) -> None:
    """
    Portfolio API should delegate to the core XIRR calculation.
    """

    result = calculate_portfolio_xirr(
        one_year_cash_flows
    )

    assert result.converged is True
    assert result.annual_return_percent == pytest.approx(
        20.015,
        abs=0.1,
    )


def test_calculate_portfolio_xirr_accepts_generator() -> None:
    """
    Portfolio API should accept any valid cash-flow iterable.
    """

    cash_flow_generator = (
        cash_flow
        for cash_flow in (
            CashFlow(
                amount=-100.0,
                flow_date=date(2023, 1, 1),
            ),
            CashFlow(
                amount=110.0,
                flow_date=date(2024, 1, 1),
            ),
        )
    )

    result = calculate_portfolio_xirr(
        cash_flow_generator
    )

    assert result.converged is True


def test_calculate_portfolio_xirr_rejects_string() -> None:
    """
    Strings must not be accepted as cash-flow iterables.
    """

    with pytest.raises(
        TypeError,
        match="iterable of CashFlow",
    ):
        calculate_portfolio_xirr(
            "invalid",  # type: ignore[arg-type]
        )


def test_calculate_portfolio_xirr_rejects_non_iterable() -> None:
    """
    Non-iterable input should raise TypeError.
    """

    with pytest.raises(
        TypeError,
        match="iterable of CashFlow",
    ):
        calculate_portfolio_xirr(
            123,  # type: ignore[arg-type]
        )


# ============================================================
# Fund XIRR Tests
# ============================================================


def test_validate_fund_xirr_input_normalises_metadata(
    standard_fund_input: FundXIRRInput,
) -> None:
    """
    Fund metadata should be preserved after validation.
    """

    validated = validate_fund_xirr_input(
        standard_fund_input
    )

    assert validated.fund_name == "UTI Nifty 50 Index Fund"
    assert validated.scheme_code == "120716"
    assert validated.source == "Unit test"


def test_calculate_fund_xirr(
    standard_fund_input: FundXIRRInput,
) -> None:
    """
    Fund API should return metadata and a successful XIRR result.
    """

    result = calculate_fund_xirr(
        standard_fund_input
    )

    assert result.fund_name == "UTI Nifty 50 Index Fund"
    assert result.scheme_code == "120716"
    assert result.source == "Unit test"
    assert result.result.converged is True
    assert result.result.annual_return_decimal > -1.0


def test_calculate_fund_xirr_strips_metadata() -> None:
    """
    Text metadata should be trimmed.
    """

    result = calculate_fund_xirr(
        FundXIRRInput(
            fund_name="  Example Fund  ",
            cash_flows=(
                CashFlow(
                    amount=-100.0,
                    flow_date=date(2023, 1, 1),
                ),
                CashFlow(
                    amount=110.0,
                    flow_date=date(2024, 1, 1),
                ),
            ),
            scheme_code="  ABC123  ",
            source="  Unit test  ",
        )
    )

    assert result.fund_name == "Example Fund"
    assert result.scheme_code == "ABC123"
    assert result.source == "Unit test"


def test_calculate_fund_xirr_converts_blank_optional_text_to_none() -> None:
    """
    Blank optional text should be normalised to None.
    """

    result = calculate_fund_xirr(
        FundXIRRInput(
            fund_name="Example Fund",
            cash_flows=(
                CashFlow(
                    amount=-100.0,
                    flow_date=date(2023, 1, 1),
                ),
                CashFlow(
                    amount=110.0,
                    flow_date=date(2024, 1, 1),
                ),
            ),
            scheme_code="   ",
            source="",
        )
    )

    assert result.scheme_code is None
    assert result.source is None


def test_calculate_fund_xirr_rejects_empty_fund_name(
    one_year_cash_flows: tuple[CashFlow, ...],
) -> None:
    """
    Fund names cannot be empty.
    """

    with pytest.raises(
        XIRRValidationError,
        match="fund_name cannot be empty",
    ):
        calculate_fund_xirr(
            FundXIRRInput(
                fund_name="   ",
                cash_flows=one_year_cash_flows,
            )
        )


def test_calculate_fund_xirr_rejects_wrong_input_type() -> None:
    """
    Fund API must reject unsupported objects.
    """

    with pytest.raises(
        TypeError,
        match="FundXIRRInput",
    ):
        calculate_fund_xirr(  # type: ignore[arg-type]
            XIRRInput(
                cash_flows=(),
            )
        )


# ============================================================
# Batch Fund XIRR Tests
# ============================================================


def test_calculate_fund_wise_xirr_all_successful() -> None:
    """
    All valid funds should be returned as successful.
    """

    funds = (
        FundXIRRInput(
            fund_name="Fund A",
            cash_flows=(
                CashFlow(
                    amount=-100.0,
                    flow_date=date(2023, 1, 1),
                ),
                CashFlow(
                    amount=110.0,
                    flow_date=date(2024, 1, 1),
                ),
            ),
        ),
        FundXIRRInput(
            fund_name="Fund B",
            cash_flows=(
                CashFlow(
                    amount=-200.0,
                    flow_date=date(2023, 1, 1),
                ),
                CashFlow(
                    amount=240.0,
                    flow_date=date(2024, 1, 1),
                ),
            ),
        ),
    )

    result = calculate_fund_wise_xirr(funds)

    assert result.total_received == 2
    assert result.successful_count == 2
    assert result.failed_count == 0
    assert len(result.successful) == 2
    assert result.failed == ()


def test_calculate_fund_wise_xirr_collects_invalid_fund() -> None:
    """
    Invalid fund records should not block valid fund calculations.
    """

    funds = (
        FundXIRRInput(
            fund_name="Valid Fund",
            cash_flows=(
                CashFlow(
                    amount=-100.0,
                    flow_date=date(2023, 1, 1),
                ),
                CashFlow(
                    amount=110.0,
                    flow_date=date(2024, 1, 1),
                ),
            ),
        ),
        FundXIRRInput(
            fund_name="Invalid Fund",
            cash_flows=(
                CashFlow(
                    amount=-100.0,
                    flow_date=date(2023, 1, 1),
                ),
                CashFlow(
                    amount=-50.0,
                    flow_date=date(2024, 1, 1),
                ),
            ),
            scheme_code="INVALID",
        ),
    )

    result = calculate_fund_wise_xirr(
        funds,
        fail_fast=False,
    )

    assert result.total_received == 2
    assert result.successful_count == 1
    assert result.failed_count == 1

    assert result.successful[0].fund_name == "Valid Fund"
    assert result.failed[0].fund_name == "Invalid Fund"
    assert result.failed[0].scheme_code == "INVALID"

    assert "positive cash flow" in result.failed[0].error


def test_calculate_fund_wise_xirr_fail_fast() -> None:
    """
    fail_fast=True should raise the first validation error.
    """

    funds = (
        FundXIRRInput(
            fund_name="Invalid Fund",
            cash_flows=(
                CashFlow(
                    amount=-100.0,
                    flow_date=date(2023, 1, 1),
                ),
                CashFlow(
                    amount=-50.0,
                    flow_date=date(2024, 1, 1),
                ),
            ),
        ),
    )

    with pytest.raises(
        XIRRValidationError,
        match="positive cash flow",
    ):
        calculate_fund_wise_xirr(
            funds,
            fail_fast=True,
        )


def test_calculate_fund_wise_xirr_collects_wrong_record_type() -> None:
    """
    Unsupported records should be represented as failures.
    """

    records = (
        FundXIRRInput(
            fund_name="Valid Fund",
            cash_flows=(
                CashFlow(
                    amount=-100.0,
                    flow_date=date(2023, 1, 1),
                ),
                CashFlow(
                    amount=110.0,
                    flow_date=date(2024, 1, 1),
                ),
            ),
        ),
        "invalid record",
    )

    result = calculate_fund_wise_xirr(  # type: ignore[arg-type]
        records,
        fail_fast=False,
    )

    assert result.total_received == 2
    assert result.successful_count == 1
    assert result.failed_count == 1
    assert "Record at index 1" in result.failed[0].error


def test_calculate_fund_wise_xirr_rejects_invalid_fail_fast() -> None:
    """
    fail_fast must be a strict boolean.
    """

    with pytest.raises(
        XIRRValidationError,
        match="fail_fast must be boolean",
    ):
        calculate_fund_wise_xirr(
            (),
            fail_fast=1,  # type: ignore[arg-type]
        )


def test_calculate_fund_wise_xirr_rejects_string_iterable() -> None:
    """
    Strings must not be treated as fund collections.
    """

    with pytest.raises(
        TypeError,
        match="iterable of FundXIRRInput",
    ):
        calculate_fund_wise_xirr(
            "invalid",  # type: ignore[arg-type]
        )


def test_calculate_fund_wise_xirr_rejects_non_iterable() -> None:
    """
    Non-iterable input should raise TypeError.
    """

    with pytest.raises(
        TypeError,
        match="iterable of FundXIRRInput",
    ):
        calculate_fund_wise_xirr(
            123,  # type: ignore[arg-type]
        )


# ============================================================
# Valuation Cash-Flow Tests
# ============================================================


def test_create_valuation_cash_flow() -> None:
    """
    Current portfolio value should become a positive terminal cash flow.
    """

    cash_flow = create_valuation_cash_flow(
        current_value=150_000.0,
        valuation_date=date(2026, 1, 1),
    )

    assert cash_flow.amount == pytest.approx(150_000.0)
    assert cash_flow.flow_date == date(2026, 1, 1)


def test_create_valuation_cash_flow_accepts_datetime() -> None:
    """
    datetime valuation dates should be normalised to date.
    """

    cash_flow = create_valuation_cash_flow(
        current_value=150_000.0,
        valuation_date=datetime(
            2026,
            1,
            1,
            15,
            30,
        ),
    )

    assert type(cash_flow.flow_date) is date


@pytest.mark.parametrize(
    "current_value",
    [
        0.0,
        -1.0,
        -100.0,
    ],
)
def test_create_valuation_cash_flow_rejects_non_positive_value(
    current_value: float,
) -> None:
    """
    Terminal valuation must be strictly positive.
    """

    with pytest.raises(
        XIRRValidationError,
        match="current_value must be greater than zero",
    ):
        create_valuation_cash_flow(
            current_value=current_value,
            valuation_date=date(2026, 1, 1),
        )


def test_create_valuation_cash_flow_rejects_invalid_date() -> None:
    """
    Unsupported valuation date types should be rejected.
    """

    with pytest.raises(
        XIRRValidationError,
        match="valuation_date must be a date or datetime",
    ):
        create_valuation_cash_flow(
            current_value=100.0,
            valuation_date="2026-01-01",  # type: ignore[arg-type]
        )


# ============================================================
# Convergence Tests
# ============================================================


def test_xirr_raises_convergence_error_when_no_root_exists() -> None:
    """
    Some cash-flow patterns contain both signs but no valid XIRR root.
    """

    cash_flows = (
        CashFlow(
            amount=-100.0,
            flow_date=date(2023, 1, 1),
        ),
        CashFlow(
            amount=10.0,
            flow_date=date(2024, 1, 1),
        ),
        CashFlow(
            amount=-100.0,
            flow_date=date(2025, 1, 1),
        ),
    )

    with pytest.raises(XIRRConvergenceError):
        calculate_xirr(
            XIRRInput(
                cash_flows=cash_flows,
            )
        )


def test_xirr_with_low_iteration_limit_may_fail() -> None:
    """
    An intentionally tiny iteration limit should not silently report
    successful convergence for a difficult sequence.
    """

    cash_flows = (
        CashFlow(
            amount=-100_000.0,
            flow_date=date(2020, 1, 1),
        ),
        CashFlow(
            amount=-25_000.0,
            flow_date=date(2021, 6, 15),
        ),
        CashFlow(
            amount=180_000.0,
            flow_date=date(2025, 12, 31),
        ),
    )

    with pytest.raises(XIRRConvergenceError):
        calculate_xirr(
            XIRRInput(
                cash_flows=cash_flows,
                tolerance=1e-14,
                max_iterations=1,
            )
        )


# ============================================================
# Rounding Tests
# ============================================================


def test_round_xirr_result() -> None:
    """
    Rounding should return a new rounded result.
    """

    original = XIRRResult(
        annual_return_decimal=0.123456,
        annual_return_percent=12.3456,
        iterations=7,
        converged=True,
        solver="newton_raphson",
    )

    rounded = round_xirr_result(
        original,
        decimal_places=2,
    )

    assert rounded.annual_return_decimal == 0.12
    assert rounded.annual_return_percent == 12.35
    assert rounded.iterations == 7
    assert rounded.converged is True
    assert rounded.solver == "newton_raphson"

    assert original.annual_return_decimal == 0.123456


def test_round_xirr_result_rejects_wrong_result_type() -> None:
    """
    Rounding should accept only XIRRResult instances.
    """

    with pytest.raises(
        TypeError,
        match="XIRRResult",
    ):
        round_xirr_result(  # type: ignore[arg-type]
            {
                "annual_return_percent": 10.0,
            }
        )


def test_round_xirr_result_rejects_negative_decimal_places() -> None:
    """
    Decimal places cannot be negative.
    """

    result = XIRRResult(
        annual_return_decimal=0.10,
        annual_return_percent=10.0,
        iterations=5,
        converged=True,
        solver="newton_raphson",
    )

    with pytest.raises(
        XIRRValidationError,
        match="decimal_places cannot be negative",
    ):
        round_xirr_result(
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
def test_round_xirr_result_rejects_invalid_decimal_place_type(
    decimal_places: object,
) -> None:
    """
    decimal_places must be a strict integer.
    """

    result = XIRRResult(
        annual_return_decimal=0.10,
        annual_return_percent=10.0,
        iterations=5,
        converged=True,
        solver="newton_raphson",
    )

    with pytest.raises(
        TypeError,
        match="decimal_places must be an integer",
    ):
        round_xirr_result(
            result,
            decimal_places=decimal_places,  # type: ignore[arg-type]
        )


# ============================================================
# Dataclass Immutability Tests
# ============================================================


def test_cash_flow_is_immutable() -> None:
    """
    CashFlow should be immutable.
    """

    cash_flow = CashFlow(
        amount=-100.0,
        flow_date=date(2024, 1, 1),
    )

    with pytest.raises(FrozenInstanceError):
        cash_flow.amount = -200.0  # type: ignore[misc]


def test_xirr_input_is_immutable(
    one_year_cash_flows: tuple[CashFlow, ...],
) -> None:
    """
    XIRRInput should be immutable.
    """

    input_data = XIRRInput(
        cash_flows=one_year_cash_flows,
    )

    with pytest.raises(FrozenInstanceError):
        input_data.guess = 0.20  # type: ignore[misc]


def test_xirr_result_is_immutable() -> None:
    """
    XIRRResult should be immutable.
    """

    result = XIRRResult(
        annual_return_decimal=0.10,
        annual_return_percent=10.0,
        iterations=5,
        converged=True,
        solver="newton_raphson",
    )

    with pytest.raises(FrozenInstanceError):
        result.annual_return_percent = 20.0  # type: ignore[misc]


# ============================================================
# Precision Tests
# ============================================================


def test_xirr_result_satisfies_xnpv_equation(
    sip_cash_flows: tuple[CashFlow, ...],
) -> None:
    """
    The solved XIRR should make XNPV approximately zero.
    """

    result = calculate_xirr(
        XIRRInput(
            cash_flows=sip_cash_flows,
            tolerance=1e-9,
            max_iterations=200,
        )
    )

    residual = calculate_xnpv(
        result.annual_return_decimal,
        sip_cash_flows,
    )

    cash_flow_scale = sum(
        abs(cash_flow.amount)
        for cash_flow in sip_cash_flows
    )

    assert abs(residual) <= cash_flow_scale * 1e-7


def test_decimal_and_percent_results_are_consistent(
    one_year_cash_flows: tuple[CashFlow, ...],
) -> None:
    """
    Percentage result should always equal decimal result multiplied by 100.
    """

    result = calculate_xirr(
        XIRRInput(
            cash_flows=one_year_cash_flows,
        )
    )

    assert isclose(
        result.annual_return_percent,
        result.annual_return_decimal * 100.0,
        rel_tol=1e-12,
        abs_tol=1e-12,
    )