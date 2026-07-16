"""
Compound Annual Growth Rate analytics.

This module provides reusable, framework-independent CAGR calculations for:

- Overall portfolio CAGR
- Fund-wise CAGR
- Date-based investment periods
- Explicit year-based investment periods
- Architecture-ready batch calculations

The module contains no Streamlit or Plotly dependencies.

PortfolioService remains the single source of portfolio data. Data retrieved
through PortfolioService should be transformed into the typed inputs defined
in this module before CAGR calculations are performed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite
from typing import Iterable, Sequence


# ============================================================
# Constants
# ============================================================

DAYS_PER_YEAR = 365.25
MINIMUM_VALID_YEARS = 1.0 / DAYS_PER_YEAR


# ============================================================
# Exceptions
# ============================================================


class CAGRValidationError(ValueError):
    """
    Raised when CAGR calculation inputs fail validation.

    Examples:
    - Initial value is zero or negative
    - Final value is negative
    - Investment period is zero or negative
    - A numeric value is NaN or infinite
    - End date occurs before the start date
    """


# ============================================================
# Input Dataclasses
# ============================================================


@dataclass(frozen=True, slots=True)
class CAGRInput:
    """
    Input model for an explicit year-based CAGR calculation.

    Attributes:
        initial_value:
            Investment value at the beginning of the period.

        final_value:
            Investment value at the end of the period.

        years:
            Duration of the investment period in years.
    """

    initial_value: float
    final_value: float
    years: float


@dataclass(frozen=True, slots=True)
class DateBasedCAGRInput:
    """
    Input model for a date-based CAGR calculation.

    Attributes:
        initial_value:
            Investment value at the beginning of the period.

        final_value:
            Investment value at the end of the period.

        start_date:
            Beginning date of the investment period.

        end_date:
            Ending date of the investment period.
    """

    initial_value: float
    final_value: float
    start_date: date | datetime
    end_date: date | datetime


@dataclass(frozen=True, slots=True)
class FundCAGRInput:
    """
    Input model for a fund-level CAGR calculation.

    This model is architecture-ready for integration with portfolio,
    transaction, NAV-history, or fund-history services.

    Attributes:
        fund_name:
            Human-readable fund name.

        initial_value:
            Fund value at the beginning of the measurement period.

        final_value:
            Fund value at the end of the measurement period.

        start_date:
            Beginning date of the measurement period.

        end_date:
            Ending date of the measurement period.

        scheme_code:
            Optional scheme identifier.

        source:
            Optional description of the source of the values.
    """

    fund_name: str
    initial_value: float
    final_value: float
    start_date: date | datetime
    end_date: date | datetime
    scheme_code: str | None = None
    source: str | None = None


# ============================================================
# Result Dataclasses
# ============================================================


@dataclass(frozen=True, slots=True)
class CAGRResult:
    """
    Result of a CAGR calculation.

    Attributes:
        initial_value:
            Validated beginning value.

        final_value:
            Validated ending value.

        years:
            Investment duration in years.

        cagr_decimal:
            CAGR represented as a decimal.

            Example:
                0.125 means 12.5%.

        cagr_percent:
            CAGR represented as a percentage.

            Example:
                12.5 means 12.5%.

        absolute_gain:
            Difference between final and initial values.

        total_return_percent:
            Total return across the entire period, without annualisation.
    """

    initial_value: float
    final_value: float
    years: float
    cagr_decimal: float
    cagr_percent: float
    absolute_gain: float
    total_return_percent: float


@dataclass(frozen=True, slots=True)
class FundCAGRResult:
    """
    CAGR result for an individual fund.

    Attributes:
        fund_name:
            Human-readable fund name.

        scheme_code:
            Optional scheme identifier.

        start_date:
            Normalised beginning date.

        end_date:
            Normalised ending date.

        result:
            Calculated CAGR metrics.

        source:
            Optional description of the source of the values.
    """

    fund_name: str
    scheme_code: str | None
    start_date: date
    end_date: date
    result: CAGRResult
    source: str | None = None


@dataclass(frozen=True, slots=True)
class FundCAGRFailure:
    """
    Represents a fund-level CAGR calculation that could not be completed.

    Batch fund calculations return failures separately so that one invalid
    fund does not prevent valid funds from being calculated.

    Attributes:
        fund_name:
            Fund associated with the validation failure.

        scheme_code:
            Optional scheme identifier.

        error:
            Human-readable validation message.
    """

    fund_name: str
    scheme_code: str | None
    error: str


@dataclass(frozen=True, slots=True)
class FundCAGRBatchResult:
    """
    Aggregate result from a fund-wise CAGR batch calculation.

    Attributes:
        successful:
            Successfully calculated fund CAGR results.

        failed:
            Funds that could not be calculated because of invalid data.

        total_received:
            Total number of fund inputs received.

        successful_count:
            Number of successfully calculated funds.

        failed_count:
            Number of failed fund calculations.
    """

    successful: tuple[FundCAGRResult, ...]
    failed: tuple[FundCAGRFailure, ...]
    total_received: int
    successful_count: int
    failed_count: int


# ============================================================
# Validation Helpers
# ============================================================


def _validate_finite_number(
    value: float | int,
    field_name: str,
) -> float:
    """
    Validate and convert a numeric value to float.

    Args:
        value:
            Numeric value to validate.

        field_name:
            Name used in validation messages.

    Returns:
        Validated float value.

    Raises:
        CAGRValidationError:
            If the value is boolean, non-numeric, NaN, or infinite.
    """

    if isinstance(value, bool):
        raise CAGRValidationError(
            f"{field_name} must be numeric and cannot be a boolean."
        )

    try:
        numeric_value = float(value)
    except (TypeError, ValueError) as exc:
        raise CAGRValidationError(
            f"{field_name} must be a valid numeric value."
        ) from exc

    if not isfinite(numeric_value):
        raise CAGRValidationError(
            f"{field_name} must be finite and cannot be NaN or infinite."
        )

    return numeric_value


def _validate_initial_value(value: float | int) -> float:
    """
    Validate the initial investment value.

    CAGR cannot be calculated when the initial value is zero or negative.
    """

    initial_value = _validate_finite_number(value, "initial_value")

    if initial_value <= 0:
        raise CAGRValidationError(
            "initial_value must be greater than zero."
        )

    return initial_value


def _validate_final_value(value: float | int) -> float:
    """
    Validate the final investment value.

    A final value of zero is accepted because an investment may lose its
    entire value. Negative investment values are not valid for CAGR.
    """

    final_value = _validate_finite_number(value, "final_value")

    if final_value < 0:
        raise CAGRValidationError(
            "final_value cannot be negative."
        )

    return final_value


def _validate_years(value: float | int) -> float:
    """
    Validate an investment duration expressed in years.
    """

    years = _validate_finite_number(value, "years")

    if years <= 0:
        raise CAGRValidationError(
            "years must be greater than zero."
        )

    return years


def _validate_required_text(
    value: str,
    field_name: str,
) -> str:
    """
    Validate and normalise a required text field.
    """

    if not isinstance(value, str):
        raise CAGRValidationError(
            f"{field_name} must be a string."
        )

    normalised_value = value.strip()

    if not normalised_value:
        raise CAGRValidationError(
            f"{field_name} cannot be empty."
        )

    return normalised_value


def _normalise_optional_text(value: str | None) -> str | None:
    """
    Strip optional text and convert empty strings to None.
    """

    if value is None:
        return None

    if not isinstance(value, str):
        raise CAGRValidationError(
            "Optional text values must be strings or None."
        )

    normalised_value = value.strip()

    return normalised_value or None


def _normalise_date(
    value: date | datetime,
    field_name: str,
) -> date:
    """
    Convert a date or datetime value to a date.

    datetime is checked before date because datetime is a subclass of date.
    """

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    raise CAGRValidationError(
        f"{field_name} must be a date or datetime instance."
    )


def _calculate_years_between_dates(
    start_date: date | datetime,
    end_date: date | datetime,
) -> tuple[date, date, float]:
    """
    Validate dates and calculate the fractional number of years between them.

    Returns:
        Tuple containing:
        - Normalised start date
        - Normalised end date
        - Duration in fractional years
    """

    normalised_start = _normalise_date(start_date, "start_date")
    normalised_end = _normalise_date(end_date, "end_date")

    day_count = (normalised_end - normalised_start).days

    if day_count <= 0:
        raise CAGRValidationError(
            "end_date must be later than start_date."
        )

    years = day_count / DAYS_PER_YEAR

    if years < MINIMUM_VALID_YEARS:
        raise CAGRValidationError(
            "The investment period is too short for CAGR calculation."
        )

    return normalised_start, normalised_end, years


# ============================================================
# Core CAGR Calculation
# ============================================================


def calculate_cagr(input_data: CAGRInput) -> CAGRResult:
    """
    Calculate Compound Annual Growth Rate using an explicit year period.

    Formula:
        CAGR = (final_value / initial_value) ** (1 / years) - 1

    Args:
        input_data:
            Validated CAGR input model.

    Returns:
        CAGRResult containing annualised and non-annualised metrics.

    Raises:
        TypeError:
            If input_data is not a CAGRInput instance.

        CAGRValidationError:
            If any input value is invalid.

    Example:
        >>> result = calculate_cagr(
        ...     CAGRInput(
        ...         initial_value=100_000,
        ...         final_value=150_000,
        ...         years=3,
        ...     )
        ... )
        >>> round(result.cagr_percent, 2)
        14.47
    """

    if not isinstance(input_data, CAGRInput):
        raise TypeError(
            "input_data must be an instance of CAGRInput."
        )

    initial_value = _validate_initial_value(input_data.initial_value)
    final_value = _validate_final_value(input_data.final_value)
    years = _validate_years(input_data.years)

    value_ratio = final_value / initial_value

    if final_value == 0:
        cagr_decimal = -1.0
    else:
        cagr_decimal = (value_ratio ** (1.0 / years)) - 1.0

    if not isfinite(cagr_decimal):
        raise CAGRValidationError(
            "The supplied values produced a non-finite CAGR result."
        )

    absolute_gain = final_value - initial_value
    total_return_decimal = value_ratio - 1.0

    return CAGRResult(
        initial_value=initial_value,
        final_value=final_value,
        years=years,
        cagr_decimal=cagr_decimal,
        cagr_percent=cagr_decimal * 100.0,
        absolute_gain=absolute_gain,
        total_return_percent=total_return_decimal * 100.0,
    )


def calculate_date_based_cagr(
    input_data: DateBasedCAGRInput,
) -> CAGRResult:
    """
    Calculate CAGR using start and end dates.

    The investment period is annualised using 365.25 days per year.

    Args:
        input_data:
            Date-based CAGR input model.

    Returns:
        CAGRResult containing calculated CAGR metrics.

    Raises:
        TypeError:
            If input_data is not a DateBasedCAGRInput instance.

        CAGRValidationError:
            If values or dates are invalid.
    """

    if not isinstance(input_data, DateBasedCAGRInput):
        raise TypeError(
            "input_data must be an instance of DateBasedCAGRInput."
        )

    _, _, years = _calculate_years_between_dates(
        start_date=input_data.start_date,
        end_date=input_data.end_date,
    )

    return calculate_cagr(
        CAGRInput(
            initial_value=input_data.initial_value,
            final_value=input_data.final_value,
            years=years,
        )
    )


# ============================================================
# Portfolio CAGR
# ============================================================


def calculate_portfolio_cagr(
    initial_value: float,
    final_value: float,
    start_date: date | datetime,
    end_date: date | datetime,
) -> CAGRResult:
    """
    Calculate CAGR for the complete portfolio.

    This function is the preferred portfolio-facing API. The caller should
    obtain portfolio values through PortfolioService or another authorised
    business service before calling this function.

    Args:
        initial_value:
            Portfolio value at the beginning of the period.

        final_value:
            Portfolio value at the end of the period.

        start_date:
            Beginning date of the measurement period.

        end_date:
            Ending date of the measurement period.

    Returns:
        CAGRResult containing portfolio CAGR metrics.
    """

    return calculate_date_based_cagr(
        DateBasedCAGRInput(
            initial_value=initial_value,
            final_value=final_value,
            start_date=start_date,
            end_date=end_date,
        )
    )


# ============================================================
# Fund-Wise CAGR
# ============================================================


def calculate_fund_cagr(
    input_data: FundCAGRInput,
) -> FundCAGRResult:
    """
    Calculate CAGR for a single fund.

    Args:
        input_data:
            Typed fund CAGR input.

    Returns:
        FundCAGRResult containing fund metadata and calculated metrics.

    Raises:
        TypeError:
            If input_data is not a FundCAGRInput instance.

        CAGRValidationError:
            If fund metadata, dates, or values are invalid.
    """

    if not isinstance(input_data, FundCAGRInput):
        raise TypeError(
            "input_data must be an instance of FundCAGRInput."
        )

    fund_name = _validate_required_text(
        input_data.fund_name,
        "fund_name",
    )

    scheme_code = _normalise_optional_text(input_data.scheme_code)
    source = _normalise_optional_text(input_data.source)

    start_date, end_date, years = _calculate_years_between_dates(
        start_date=input_data.start_date,
        end_date=input_data.end_date,
    )

    result = calculate_cagr(
        CAGRInput(
            initial_value=input_data.initial_value,
            final_value=input_data.final_value,
            years=years,
        )
    )

    return FundCAGRResult(
        fund_name=fund_name,
        scheme_code=scheme_code,
        start_date=start_date,
        end_date=end_date,
        result=result,
        source=source,
    )


def calculate_fund_wise_cagr(
    funds: Iterable[FundCAGRInput],
    *,
    fail_fast: bool = False,
) -> FundCAGRBatchResult:
    """
    Calculate CAGR for multiple funds.

    By default, invalid funds are collected as failures while valid funds
    continue to be processed. This is useful for enterprise dashboards where
    one malformed record should not prevent all analytics from rendering.

    Args:
        funds:
            Iterable of FundCAGRInput records.

        fail_fast:
            When True, the first validation error is raised immediately.
            When False, invalid records are collected in the failed results.

    Returns:
        FundCAGRBatchResult containing successful and failed calculations.

    Raises:
        TypeError:
            If funds is not iterable or contains an unsupported record type.

        CAGRValidationError:
            When fail_fast is True and a record fails validation.
    """

    if isinstance(funds, (str, bytes)):
        raise TypeError(
            "funds must be an iterable of FundCAGRInput instances."
        )

    try:
        fund_records: Sequence[FundCAGRInput] = tuple(funds)
    except TypeError as exc:
        raise TypeError(
            "funds must be an iterable of FundCAGRInput instances."
        ) from exc

    successful: list[FundCAGRResult] = []
    failed: list[FundCAGRFailure] = []

    for index, fund in enumerate(fund_records):
        if not isinstance(fund, FundCAGRInput):
            error_message = (
                f"Record at index {index} must be an instance "
                "of FundCAGRInput."
            )

            if fail_fast:
                raise TypeError(error_message)

            failed.append(
                FundCAGRFailure(
                    fund_name=f"Unknown fund at index {index}",
                    scheme_code=None,
                    error=error_message,
                )
            )
            continue

        try:
            successful.append(calculate_fund_cagr(fund))

        except CAGRValidationError as exc:
            if fail_fast:
                raise

            raw_fund_name = (
                fund.fund_name.strip()
                if isinstance(fund.fund_name, str)
                and fund.fund_name.strip()
                else f"Unknown fund at index {index}"
            )

            raw_scheme_code = (
                fund.scheme_code.strip()
                if isinstance(fund.scheme_code, str)
                and fund.scheme_code.strip()
                else None
            )

            failed.append(
                FundCAGRFailure(
                    fund_name=raw_fund_name,
                    scheme_code=raw_scheme_code,
                    error=str(exc),
                )
            )

    return FundCAGRBatchResult(
        successful=tuple(successful),
        failed=tuple(failed),
        total_received=len(fund_records),
        successful_count=len(successful),
        failed_count=len(failed),
    )


# ============================================================
# Utility Functions
# ============================================================


def round_cagr_result(
    result: CAGRResult,
    decimal_places: int = 2,
) -> CAGRResult:
    """
    Return a rounded copy of a CAGR result.

    Core calculation functions intentionally preserve full precision.
    Rounding should generally occur only at presentation boundaries.

    Args:
        result:
            CAGR result to round.

        decimal_places:
            Number of decimal places to retain.

    Returns:
        New CAGRResult containing rounded values.
    """

    if not isinstance(result, CAGRResult):
        raise TypeError(
            "result must be an instance of CAGRResult."
        )

    if isinstance(decimal_places, bool) or not isinstance(
        decimal_places,
        int,
    ):
        raise TypeError(
            "decimal_places must be an integer."
        )

    if decimal_places < 0:
        raise CAGRValidationError(
            "decimal_places cannot be negative."
        )

    return CAGRResult(
        initial_value=round(result.initial_value, decimal_places),
        final_value=round(result.final_value, decimal_places),
        years=round(result.years, decimal_places),
        cagr_decimal=round(result.cagr_decimal, decimal_places),
        cagr_percent=round(result.cagr_percent, decimal_places),
        absolute_gain=round(result.absolute_gain, decimal_places),
        total_return_percent=round(
            result.total_return_percent,
            decimal_places,
        ),
    )


__all__ = [
    "CAGRInput",
    "CAGRResult",
    "CAGRValidationError",
    "DateBasedCAGRInput",
    "FundCAGRBatchResult",
    "FundCAGRFailure",
    "FundCAGRInput",
    "FundCAGRResult",
    "calculate_cagr",
    "calculate_date_based_cagr",
    "calculate_fund_cagr",
    "calculate_fund_wise_cagr",
    "calculate_portfolio_cagr",
    "round_cagr_result",
]