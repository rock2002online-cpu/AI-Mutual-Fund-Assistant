"""
Extended Internal Rate of Return (XIRR) analytics.

This module provides framework-independent XIRR calculations for portfolios
and individual mutual funds with irregular cash flows.

Supported scenarios include:

- SIP investments
- Multiple purchases
- Partial or full redemptions
- A terminal current-value cash flow
- Portfolio-level and fund-level calculations

Sign convention:

- Investments and purchases are negative cash flows.
- Redemptions, withdrawals, and terminal valuations are positive cash flows.

PortfolioService remains the single source of portfolio data. Calling code
must transform service data into the typed models defined in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite
from typing import Iterable, Literal, Sequence


# ==========================================================
# Constants
# ==========================================================

DAYS_PER_YEAR = 365.25
DEFAULT_GUESS = 0.10
DEFAULT_TOLERANCE = 1e-7
DEFAULT_MAX_ITERATIONS = 100
MINIMUM_RATE = -0.999999999
MAXIMUM_BRACKET_RATE = 1_000_000.0
DERIVATIVE_EPSILON = 1e-14

SolverName = Literal["newton_raphson", "bisection"]


# ==========================================================
# Exceptions
# ==========================================================


class XIRRValidationError(ValueError):
    """Raised when XIRR input data fails validation."""


class XIRRConvergenceError(RuntimeError):
    """Raised when the numerical solver cannot find a valid XIRR root."""


# ==========================================================
# Input Models
# ==========================================================


@dataclass(frozen=True, slots=True)
class CashFlow:
    """A dated cash flow used in an XIRR calculation."""

    amount: float
    flow_date: date | datetime


@dataclass(frozen=True, slots=True)
class XIRRInput:
    """Input for a portfolio or generic XIRR calculation."""

    cash_flows: tuple[CashFlow, ...]
    guess: float = DEFAULT_GUESS
    tolerance: float = DEFAULT_TOLERANCE
    max_iterations: int = DEFAULT_MAX_ITERATIONS


@dataclass(frozen=True, slots=True)
class FundXIRRInput:
    """Input for one mutual fund's XIRR calculation."""

    fund_name: str
    cash_flows: tuple[CashFlow, ...]
    scheme_code: str | None = None
    source: str | None = None


# ==========================================================
# Result Models
# ==========================================================


@dataclass(frozen=True, slots=True)
class XIRRResult:
    """Result returned by a successful XIRR calculation."""

    annual_return_decimal: float
    annual_return_percent: float
    iterations: int
    converged: bool
    solver: SolverName


@dataclass(frozen=True, slots=True)
class FundXIRRResult:
    """XIRR result for one mutual fund."""

    fund_name: str
    scheme_code: str | None
    result: XIRRResult
    source: str | None = None


@dataclass(frozen=True, slots=True)
class FundXIRRFailure:
    """A failed fund-level XIRR calculation."""

    fund_name: str
    scheme_code: str | None
    error: str


@dataclass(frozen=True, slots=True)
class FundXIRRBatchResult:
    """Aggregate result from fund-wise XIRR processing."""

    successful: tuple[FundXIRRResult, ...]
    failed: tuple[FundXIRRFailure, ...]
    total_received: int
    successful_count: int
    failed_count: int


# ==========================================================
# Validation Helpers
# ==========================================================


def _validate_number(value: float | int, field_name: str) -> float:
    """Validate a finite numeric value and return it as ``float``."""

    if isinstance(value, bool):
        raise XIRRValidationError(f"{field_name} cannot be boolean.")

    try:
        numeric_value = float(value)
    except (TypeError, ValueError) as exc:
        raise XIRRValidationError(f"{field_name} must be numeric.") from exc

    if not isfinite(numeric_value):
        raise XIRRValidationError(f"{field_name} must be finite.")

    return numeric_value


def _validate_positive_integer(value: int, field_name: str) -> int:
    """Validate a positive integer while rejecting booleans."""

    if isinstance(value, bool) or not isinstance(value, int):
        raise XIRRValidationError(f"{field_name} must be an integer.")

    if value <= 0:
        raise XIRRValidationError(f"{field_name} must be greater than zero.")

    return value


def _normalize_date(value: date | datetime, field_name: str) -> date:
    """Normalize ``datetime`` to ``date`` and reject unsupported values."""

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    raise XIRRValidationError(
        f"{field_name} must be a date or datetime instance."
    )


def _validate_required_text(value: str, field_name: str) -> str:
    """Validate and normalize a required text field."""

    if not isinstance(value, str):
        raise XIRRValidationError(f"{field_name} must be a string.")

    normalized_value = value.strip()
    if not normalized_value:
        raise XIRRValidationError(f"{field_name} cannot be empty.")

    return normalized_value


def _normalize_optional_text(value: str | None, field_name: str) -> str | None:
    """Normalize optional text and convert blank strings to ``None``."""

    if value is None:
        return None

    if not isinstance(value, str):
        raise XIRRValidationError(f"{field_name} must be a string or None.")

    normalized_value = value.strip()
    return normalized_value or None


def _validate_cash_flow(cash_flow: CashFlow) -> CashFlow:
    """Validate and normalize one cash flow."""

    if not isinstance(cash_flow, CashFlow):
        raise TypeError("Each cash flow must be an instance of CashFlow.")

    return CashFlow(
        amount=_validate_number(cash_flow.amount, "amount"),
        flow_date=_normalize_date(cash_flow.flow_date, "flow_date"),
    )


def _validate_cash_flows(
    cash_flows: Iterable[CashFlow],
) -> tuple[CashFlow, ...]:
    """Validate, normalize, and chronologically sort XIRR cash flows."""

    if isinstance(cash_flows, (str, bytes)):
        raise TypeError("cash_flows must be an iterable of CashFlow instances.")

    try:
        raw_flows = tuple(cash_flows)
    except TypeError as exc:
        raise TypeError(
            "cash_flows must be an iterable of CashFlow instances."
        ) from exc

    flows = tuple(_validate_cash_flow(flow) for flow in raw_flows)

    if len(flows) < 2:
        raise XIRRValidationError("At least two cash flows are required.")

    if not any(flow.amount < 0.0 for flow in flows):
        raise XIRRValidationError(
            "At least one investment (negative cash flow) is required."
        )

    if not any(flow.amount > 0.0 for flow in flows):
        raise XIRRValidationError(
            "At least one positive cash flow is required."
        )

    sorted_flows = tuple(sorted(flows, key=lambda flow: flow.flow_date))

    if sorted_flows[0].flow_date >= sorted_flows[-1].flow_date:
        raise XIRRValidationError("Cash flows must span at least two dates.")

    return sorted_flows


def _validate_rate(rate: float | int, field_name: str = "rate") -> float:
    """Validate a rate that is strictly greater than -100%."""

    validated_rate = _validate_number(rate, field_name)
    if validated_rate <= -1.0:
        raise XIRRValidationError(f"{field_name} must be greater than -1.0.")

    return validated_rate


# ==========================================================
# Public Validation API
# ==========================================================


def validate_xirr_input(input_data: XIRRInput) -> XIRRInput:
    """Validate and normalize a generic XIRR input model."""

    if not isinstance(input_data, XIRRInput):
        raise TypeError("input_data must be an instance of XIRRInput.")

    guess = _validate_rate(input_data.guess, "guess")
    tolerance = _validate_number(input_data.tolerance, "tolerance")
    if tolerance <= 0.0:
        raise XIRRValidationError("tolerance must be greater than zero.")

    max_iterations = _validate_positive_integer(
        input_data.max_iterations,
        "max_iterations",
    )

    return XIRRInput(
        cash_flows=_validate_cash_flows(input_data.cash_flows),
        guess=guess,
        tolerance=tolerance,
        max_iterations=max_iterations,
    )


def validate_fund_xirr_input(input_data: FundXIRRInput) -> FundXIRRInput:
    """Validate and normalize a fund-level XIRR input model."""

    if not isinstance(input_data, FundXIRRInput):
        raise TypeError("input_data must be an instance of FundXIRRInput.")

    return FundXIRRInput(
        fund_name=_validate_required_text(input_data.fund_name, "fund_name"),
        cash_flows=_validate_cash_flows(input_data.cash_flows),
        scheme_code=_normalize_optional_text(
            input_data.scheme_code,
            "scheme_code",
        ),
        source=_normalize_optional_text(input_data.source, "source"),
    )


# ==========================================================
# Numerical Helpers
# ==========================================================


def _year_fraction(flow_date: date, base_date: date) -> float:
    """Return the year fraction between two normalized dates."""

    return (flow_date - base_date).days / DAYS_PER_YEAR


def _xnpv(rate: float, cash_flows: Sequence[CashFlow]) -> float:
    """Calculate XNPV for already validated and sorted cash flows."""

    discount_base = 1.0 + rate
    base_date = cash_flows[0].flow_date
    total = 0.0

    for flow in cash_flows:
        years = _year_fraction(flow.flow_date, base_date)
        try:
            discount_factor = discount_base**years
            discounted_amount = flow.amount / discount_factor
        except (OverflowError, ValueError, ZeroDivisionError) as exc:
            raise XIRRConvergenceError(
                "The candidate rate produced an invalid discount factor."
            ) from exc

        if not isfinite(discount_factor) or discount_factor <= 0.0:
            raise XIRRConvergenceError(
                "The candidate rate produced a non-finite discount factor."
            )

        if not isfinite(discounted_amount):
            raise XIRRConvergenceError(
                "The candidate rate produced a non-finite discounted value."
            )

        total += discounted_amount

    if not isfinite(total):
        raise XIRRConvergenceError("The XNPV result is non-finite.")

    return total


def calculate_xnpv(rate: float, cash_flows: Iterable[CashFlow]) -> float:
    """Calculate XNPV for a validated sequence of irregular cash flows."""

    validated_rate = _validate_rate(rate)
    validated_flows = _validate_cash_flows(cash_flows)
    return _xnpv(validated_rate, validated_flows)


def _xnpv_derivative(rate: float, cash_flows: Sequence[CashFlow]) -> float:
    """Calculate the first derivative of XNPV for validated cash flows."""

    discount_base = 1.0 + rate
    base_date = cash_flows[0].flow_date
    derivative = 0.0

    for flow in cash_flows:
        years = _year_fraction(flow.flow_date, base_date)
        if years == 0.0:
            continue

        try:
            denominator = discount_base ** (years + 1.0)
            term = -(years * flow.amount) / denominator
        except (OverflowError, ValueError, ZeroDivisionError) as exc:
            raise XIRRConvergenceError(
                "The candidate rate produced an invalid XNPV derivative."
            ) from exc

        if not isfinite(term):
            raise XIRRConvergenceError("The XNPV derivative is non-finite.")

        derivative += term

    if not isfinite(derivative):
        raise XIRRConvergenceError("The XNPV derivative is non-finite.")

    return derivative


def _residual_tolerance(
    cash_flows: Sequence[CashFlow],
    tolerance: float,
) -> float:
    """Scale residual tolerance to the magnitude of the cash flows."""

    scale = max(1.0, sum(abs(flow.amount) for flow in cash_flows))
    return tolerance * scale


# ==========================================================
# Newton-Raphson Solver
# ==========================================================


def _solve_xirr_newton_raphson(
    cash_flows: Sequence[CashFlow],
    *,
    guess: float,
    tolerance: float,
    max_iterations: int,
) -> tuple[float, int]:
    """Solve XIRR using Newton-Raphson iteration."""

    current_rate = guess
    residual_limit = _residual_tolerance(cash_flows, tolerance)

    for iteration in range(1, max_iterations + 1):
        current_value = _xnpv(current_rate, cash_flows)
        if abs(current_value) <= residual_limit:
            return current_rate, iteration

        derivative = _xnpv_derivative(current_rate, cash_flows)
        if abs(derivative) <= DERIVATIVE_EPSILON:
            raise XIRRConvergenceError(
                "Newton-Raphson derivative became too small."
            )

        next_rate = current_rate - (current_value / derivative)
        if not isfinite(next_rate):
            raise XIRRConvergenceError(
                "Newton-Raphson produced a non-finite rate."
            )

        if next_rate <= -1.0:
            raise XIRRConvergenceError(
                "Newton-Raphson crossed the minimum valid rate."
            )

        if abs(next_rate - current_rate) <= tolerance:
            final_value = _xnpv(next_rate, cash_flows)
            if abs(final_value) <= residual_limit:
                return next_rate, iteration

        current_rate = next_rate

    raise XIRRConvergenceError(
        "Newton-Raphson did not converge within max_iterations."
    )


# ==========================================================
# Root Bracketing and Bisection
# ==========================================================


def _candidate_rates(guess: float) -> tuple[float, ...]:
    """Build an ordered set of candidate rates for root bracketing."""

    fixed_rates = [
        MINIMUM_RATE,
        -0.999,
        -0.99,
        -0.90,
        -0.75,
        -0.50,
        -0.25,
        -0.10,
        0.0,
        0.10,
        0.25,
        0.50,
        1.0,
        2.0,
        5.0,
        10.0,
        25.0,
        50.0,
        100.0,
        1_000.0,
        10_000.0,
        100_000.0,
        MAXIMUM_BRACKET_RATE,
    ]

    if -1.0 < guess <= MAXIMUM_BRACKET_RATE:
        fixed_rates.append(guess)

    return tuple(sorted(set(fixed_rates)))


def _find_rate_bracket(
    cash_flows: Sequence[CashFlow],
    *,
    guess: float,
) -> tuple[float, float]:
    """Find a sign-changing rate interval, preferring one near ``guess``."""

    evaluated: list[tuple[float, float]] = []

    for rate in _candidate_rates(guess):
        try:
            value = _xnpv(rate, cash_flows)
        except XIRRConvergenceError:
            continue

        if value == 0.0:
            return rate, rate

        evaluated.append((rate, value))

    brackets: list[tuple[float, float]] = []
    for (left_rate, left_value), (right_rate, right_value) in zip(
        evaluated,
        evaluated[1:],
    ):
        if left_value * right_value < 0.0:
            brackets.append((left_rate, right_rate))

    if not brackets:
        raise XIRRConvergenceError(
            "Unable to find a sign-changing interval for XIRR."
        )

    return min(
        brackets,
        key=lambda bounds: abs(((bounds[0] + bounds[1]) / 2.0) - guess),
    )


def _solve_xirr_bisection(
    cash_flows: Sequence[CashFlow],
    *,
    guess: float,
    tolerance: float,
    max_iterations: int,
) -> tuple[float, int]:
    """Solve XIRR using a bracketed bisection method."""

    lower_rate, upper_rate = _find_rate_bracket(cash_flows, guess=guess)
    if lower_rate == upper_rate:
        return lower_rate, 1

    lower_value = _xnpv(lower_rate, cash_flows)
    residual_limit = _residual_tolerance(cash_flows, tolerance)

    for iteration in range(1, max_iterations + 1):
        midpoint_rate = (lower_rate + upper_rate) / 2.0
        midpoint_value = _xnpv(midpoint_rate, cash_flows)

        if abs(midpoint_value) <= residual_limit:
            return midpoint_rate, iteration

        if abs(upper_rate - lower_rate) <= tolerance:
            return midpoint_rate, iteration

        if lower_value * midpoint_value < 0.0:
            upper_rate = midpoint_rate
        else:
            lower_rate = midpoint_rate
            lower_value = midpoint_value

    raise XIRRConvergenceError(
        "Bisection did not converge within max_iterations."
    )


# ==========================================================
# Combined Solver
# ==========================================================


def _solve_xirr(
    cash_flows: Sequence[CashFlow],
    *,
    guess: float,
    tolerance: float,
    max_iterations: int,
) -> tuple[float, int, SolverName]:
    """Use Newton-Raphson first and bisection as a safe fallback."""

    try:
        rate, iterations = _solve_xirr_newton_raphson(
            cash_flows,
            guess=guess,
            tolerance=tolerance,
            max_iterations=max_iterations,
        )
        return rate, iterations, "newton_raphson"
    except XIRRConvergenceError as newton_error:
        try:
            rate, iterations = _solve_xirr_bisection(
                cash_flows,
                guess=guess,
                tolerance=tolerance,
                max_iterations=max_iterations,
            )
            return rate, iterations, "bisection"
        except XIRRConvergenceError as bisection_error:
            raise XIRRConvergenceError(
                "XIRR calculation failed with both Newton-Raphson and "
                "bisection. "
                f"Newton-Raphson: {newton_error} "
                f"Bisection: {bisection_error}"
            ) from bisection_error


# ==========================================================
# Public XIRR API
# ==========================================================


def calculate_xirr(input_data: XIRRInput) -> XIRRResult:
    """Calculate XIRR for a typed sequence of irregular cash flows."""

    validated_input = validate_xirr_input(input_data)
    rate, iterations, solver = _solve_xirr(
        validated_input.cash_flows,
        guess=validated_input.guess,
        tolerance=validated_input.tolerance,
        max_iterations=validated_input.max_iterations,
    )

    if not isfinite(rate):
        raise XIRRConvergenceError("The solver returned a non-finite rate.")

    return XIRRResult(
        annual_return_decimal=rate,
        annual_return_percent=rate * 100.0,
        iterations=iterations,
        converged=True,
        solver=solver,
    )


def calculate_portfolio_xirr(
    cash_flows: Iterable[CashFlow],
    *,
    guess: float = DEFAULT_GUESS,
    tolerance: float = DEFAULT_TOLERANCE,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> XIRRResult:
    """Calculate XIRR for complete portfolio cash flows."""

    if isinstance(cash_flows, (str, bytes)):
        raise TypeError("cash_flows must be an iterable of CashFlow instances.")

    try:
        normalized_cash_flows = tuple(cash_flows)
    except TypeError as exc:
        raise TypeError(
            "cash_flows must be an iterable of CashFlow instances."
        ) from exc

    return calculate_xirr(
        XIRRInput(
            cash_flows=normalized_cash_flows,
            guess=guess,
            tolerance=tolerance,
            max_iterations=max_iterations,
        )
    )


def calculate_fund_xirr(
    input_data: FundXIRRInput,
    *,
    guess: float = DEFAULT_GUESS,
    tolerance: float = DEFAULT_TOLERANCE,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> FundXIRRResult:
    """Calculate XIRR for one mutual fund."""

    validated_input = validate_fund_xirr_input(input_data)
    result = calculate_xirr(
        XIRRInput(
            cash_flows=validated_input.cash_flows,
            guess=guess,
            tolerance=tolerance,
            max_iterations=max_iterations,
        )
    )

    return FundXIRRResult(
        fund_name=validated_input.fund_name,
        scheme_code=validated_input.scheme_code,
        result=result,
        source=validated_input.source,
    )


def calculate_fund_wise_xirr(
    funds: Iterable[FundXIRRInput],
    *,
    guess: float = DEFAULT_GUESS,
    tolerance: float = DEFAULT_TOLERANCE,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    fail_fast: bool = False,
) -> FundXIRRBatchResult:
    """Calculate XIRR for multiple funds without one failure blocking all."""

    if not isinstance(fail_fast, bool):
        raise XIRRValidationError("fail_fast must be boolean.")

    if isinstance(funds, (str, bytes)):
        raise TypeError("funds must be an iterable of FundXIRRInput instances.")

    try:
        fund_records: Sequence[FundXIRRInput] = tuple(funds)
    except TypeError as exc:
        raise TypeError(
            "funds must be an iterable of FundXIRRInput instances."
        ) from exc

    successful: list[FundXIRRResult] = []
    failed: list[FundXIRRFailure] = []

    for index, fund in enumerate(fund_records):
        if not isinstance(fund, FundXIRRInput):
            error = (
                f"Record at index {index} must be an instance of FundXIRRInput."
            )
            if fail_fast:
                raise TypeError(error)

            failed.append(
                FundXIRRFailure(
                    fund_name=f"Unknown fund at index {index}",
                    scheme_code=None,
                    error=error,
                )
            )
            continue

        try:
            successful.append(
                calculate_fund_xirr(
                    fund,
                    guess=guess,
                    tolerance=tolerance,
                    max_iterations=max_iterations,
                )
            )
        except (TypeError, XIRRValidationError, XIRRConvergenceError) as exc:
            if fail_fast:
                raise

            fund_name = (
                fund.fund_name.strip()
                if isinstance(fund.fund_name, str) and fund.fund_name.strip()
                else f"Unknown fund at index {index}"
            )
            scheme_code = (
                fund.scheme_code.strip()
                if isinstance(fund.scheme_code, str) and fund.scheme_code.strip()
                else None
            )
            failed.append(
                FundXIRRFailure(
                    fund_name=fund_name,
                    scheme_code=scheme_code,
                    error=str(exc),
                )
            )

    return FundXIRRBatchResult(
        successful=tuple(successful),
        failed=tuple(failed),
        total_received=len(fund_records),
        successful_count=len(successful),
        failed_count=len(failed),
    )


# ==========================================================
# Construction and Presentation Utilities
# ==========================================================


def create_valuation_cash_flow(
    current_value: float,
    valuation_date: date | datetime,
) -> CashFlow:
    """Create a positive terminal cash flow for a current market value."""

    normalized_value = _validate_number(current_value, "current_value")
    if normalized_value <= 0.0:
        raise XIRRValidationError("current_value must be greater than zero.")

    return CashFlow(
        amount=normalized_value,
        flow_date=_normalize_date(valuation_date, "valuation_date"),
    )


def round_xirr_result(
    result: XIRRResult,
    decimal_places: int = 2,
) -> XIRRResult:
    """Return a rounded copy of an XIRR result for presentation use."""

    if not isinstance(result, XIRRResult):
        raise TypeError("result must be an instance of XIRRResult.")

    if isinstance(decimal_places, bool) or not isinstance(decimal_places, int):
        raise TypeError("decimal_places must be an integer.")

    if decimal_places < 0:
        raise XIRRValidationError("decimal_places cannot be negative.")

    return XIRRResult(
        annual_return_decimal=round(
            result.annual_return_decimal,
            decimal_places,
        ),
        annual_return_percent=round(
            result.annual_return_percent,
            decimal_places,
        ),
        iterations=result.iterations,
        converged=result.converged,
        solver=result.solver,
    )


# ==========================================================
# Module Exports
# ==========================================================


__all__ = [
    "CashFlow",
    "FundXIRRBatchResult",
    "FundXIRRFailure",
    "FundXIRRInput",
    "FundXIRRResult",
    "SolverName",
    "XIRRConvergenceError",
    "XIRRInput",
    "XIRRResult",
    "XIRRValidationError",
    "calculate_fund_wise_xirr",
    "calculate_fund_xirr",
    "calculate_portfolio_xirr",
    "calculate_xirr",
    "calculate_xnpv",
    "create_valuation_cash_flow",
    "round_xirr_result",
    "validate_fund_xirr_input",
    "validate_xirr_input",
]