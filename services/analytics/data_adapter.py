"""
Analytics data-preparation adapter.

This module converts portfolio, transaction, valuation, and benchmark data
into the strongly typed models required by the analytics engine.

Supported transformations include:

- Portfolio snapshot totals
- CAGR inputs
- XIRR cash flows
- Historical value observations
- Periodic returns
- Volatility inputs
- Drawdown inputs
- Risk-metric inputs
- Benchmark-relative inputs
- Rolling-return inputs
- Complete AdvancedAnalyticsInput construction

The module contains no Streamlit or Plotly dependencies.

PortfolioService remains the single source of portfolio data. Calling
services should retrieve data through PortfolioService and pass it into the
adapter functions defined here.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite
from typing import Any

from services.analytics.advanced_analytics import (
    AdvancedAnalyticsInput,
)
from services.analytics.benchmark import (
    BenchmarkInput,
)
from services.analytics.cagr import (
    DateBasedCAGRInput,
)
from services.analytics.drawdown import (
    DrawdownInput,
    ValueObservation as DrawdownObservation,
)
from services.analytics.risk_metrics import (
    RiskMetricsInput,
)
from services.analytics.rolling_returns import (
    RollingReturnsInput,
    ValueObservation as RollingObservation,
)
from services.analytics.volatility import (
    VolatilityInput,
)
from services.analytics.xirr import (
    CashFlow,
    XIRRInput,
)


# ============================================================
# Constants
# ============================================================

DEFAULT_PERIODS_PER_YEAR = 252
DEFAULT_ROLLING_WINDOW_SIZE = 12
DEFAULT_RISK_FREE_RATE = 0.0
DEFAULT_MINIMUM_ACCEPTABLE_RETURN = 0.0

DEFAULT_INVESTMENT_COLUMN = "Investment"
DEFAULT_CURRENT_VALUE_COLUMN = "Current Value"

DEFAULT_DATE_COLUMN = "Date"
DEFAULT_VALUE_COLUMN = "Value"

DEFAULT_CASH_FLOW_DATE_COLUMN = "Date"
DEFAULT_CASH_FLOW_AMOUNT_COLUMN = "Amount"

DEFAULT_PORTFOLIO_RETURN_COLUMN = "Portfolio Return"
DEFAULT_BENCHMARK_RETURN_COLUMN = "Benchmark Return"


# ============================================================
# Exceptions
# ============================================================


class AnalyticsDataAdapterError(ValueError):
    """
    Raised when source data cannot be converted into analytics inputs.
    """


# ============================================================
# Adapter Result Models
# ============================================================


@dataclass(frozen=True, slots=True)
class PortfolioSnapshotTotals:
    """
    Aggregate totals calculated from a portfolio snapshot.

    Attributes:
        row_count:
            Number of portfolio records processed.

        total_investment:
            Sum of invested values.

        total_current_value:
            Sum of current market values.

        total_profit_loss:
            Current value minus investment.

        total_return_decimal:
            Total portfolio return represented as a decimal.

        total_return_percent:
            Total portfolio return represented as a percentage.
    """

    row_count: int
    total_investment: float
    total_current_value: float
    total_profit_loss: float
    total_return_decimal: float
    total_return_percent: float


@dataclass(frozen=True, slots=True)
class DatedValue:
    """
    Normalised dated value used by adapter functions.
    """

    observation_date: date
    value: float


@dataclass(frozen=True, slots=True)
class DatedCashFlow:
    """
    Normalised dated cash flow used by adapter functions.
    """

    flow_date: date
    amount: float


@dataclass(frozen=True, slots=True)
class AlignedReturnSeries:
    """
    Aligned portfolio and benchmark return series.
    """

    portfolio_returns: tuple[float, ...]
    benchmark_returns: tuple[float, ...]
    observation_count: int


@dataclass(frozen=True, slots=True)
class AnalyticsAdapterResult:
    """
    Result of building an advanced analytics input.

    Attributes:
        analytics_input:
            Complete or partial AdvancedAnalyticsInput.

        available_metrics:
            Metrics whose typed inputs were successfully created.

        unavailable_metrics:
            Metrics omitted because required source data was not supplied.
    """

    analytics_input: AdvancedAnalyticsInput
    available_metrics: tuple[str, ...]
    unavailable_metrics: tuple[str, ...]


# ============================================================
# Generic Validation Helpers
# ============================================================


def _validate_finite_number(
    value: Any,
    field_name: str,
) -> float:
    """
    Validate and convert a finite numeric value.
    """

    if isinstance(value, bool):
        raise AnalyticsDataAdapterError(
            f"{field_name} must be numeric and cannot be a boolean."
        )

    try:
        numeric_value = float(value)
    except (TypeError, ValueError) as exc:
        raise AnalyticsDataAdapterError(
            f"{field_name} must be a valid numeric value."
        ) from exc

    if not isfinite(numeric_value):
        raise AnalyticsDataAdapterError(
            f"{field_name} must be finite and cannot be NaN or infinite."
        )

    return numeric_value


def _validate_positive_number(
    value: Any,
    field_name: str,
) -> float:
    """
    Validate a strictly positive numeric value.
    """

    numeric_value = _validate_finite_number(
        value,
        field_name,
    )

    if numeric_value <= 0:
        raise AnalyticsDataAdapterError(
            f"{field_name} must be greater than zero."
        )

    return numeric_value


def _validate_non_negative_number(
    value: Any,
    field_name: str,
) -> float:
    """
    Validate a non-negative numeric value.
    """

    numeric_value = _validate_finite_number(
        value,
        field_name,
    )

    if numeric_value < 0:
        raise AnalyticsDataAdapterError(
            f"{field_name} cannot be negative."
        )

    return numeric_value


def _validate_positive_integer(
    value: Any,
    field_name: str,
) -> int:
    """
    Validate a strict positive integer.
    """

    if isinstance(value, bool) or not isinstance(value, int):
        raise AnalyticsDataAdapterError(
            f"{field_name} must be an integer."
        )

    if value <= 0:
        raise AnalyticsDataAdapterError(
            f"{field_name} must be greater than zero."
        )

    return value


def _validate_boolean(
    value: Any,
    field_name: str,
) -> bool:
    """
    Validate a strict boolean value.
    """

    if not isinstance(value, bool):
        raise AnalyticsDataAdapterError(
            f"{field_name} must be a boolean."
        )

    return value


def _normalise_date(
    value: Any,
    field_name: str,
) -> date:
    """
    Convert date, datetime, or ISO-format text into a date.
    """

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        normalised_value = value.strip()

        if not normalised_value:
            raise AnalyticsDataAdapterError(
                f"{field_name} cannot be empty."
            )

        try:
            return date.fromisoformat(normalised_value)
        except ValueError:
            try:
                return datetime.fromisoformat(
                    normalised_value
                ).date()
            except ValueError as exc:
                raise AnalyticsDataAdapterError(
                    f"{field_name} must be a valid ISO-format date."
                ) from exc

    raise AnalyticsDataAdapterError(
        f"{field_name} must be a date, datetime, or ISO-format string."
    )


# ============================================================
# Record Conversion Helpers
# ============================================================


def _to_records(
    data: Any,
    *,
    source_name: str,
) -> tuple[Mapping[str, Any], ...]:
    """
    Convert supported tabular data into mapping records.

    Supported sources:

    - pandas DataFrame-like objects exposing ``to_dict("records")``
    - Iterable of mapping objects
    """

    if data is None:
        raise AnalyticsDataAdapterError(
            f"{source_name} cannot be None."
        )

    if isinstance(data, (str, bytes)):
        raise AnalyticsDataAdapterError(
            f"{source_name} must be tabular data or an iterable of mappings."
        )

    to_dict = getattr(data, "to_dict", None)

    if callable(to_dict):
        try:
            raw_records = to_dict("records")
        except (TypeError, ValueError):
            raw_records = None

        if raw_records is not None:
            return _validate_mapping_records(
                raw_records,
                source_name=source_name,
            )

    try:
        return _validate_mapping_records(
            data,
            source_name=source_name,
        )
    except TypeError as exc:
        raise AnalyticsDataAdapterError(
            f"{source_name} must be tabular data or an iterable of mappings."
        ) from exc


def _validate_mapping_records(
    records: Iterable[Any],
    *,
    source_name: str,
) -> tuple[Mapping[str, Any], ...]:
    """
    Validate an iterable of mapping records.
    """

    normalised_records: list[Mapping[str, Any]] = []

    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise AnalyticsDataAdapterError(
                f"{source_name}[{index}] must be a mapping."
            )

        normalised_records.append(record)

    return tuple(normalised_records)


def _require_column(
    record: Mapping[str, Any],
    column_name: str,
    *,
    record_index: int,
    source_name: str,
) -> Any:
    """
    Retrieve a required column from one record.
    """

    if column_name not in record:
        raise AnalyticsDataAdapterError(
            f"Missing required column {column_name!r} "
            f"in {source_name}[{record_index}]."
        )

    return record[column_name]


# ============================================================
# Portfolio Snapshot Adapter
# ============================================================


def calculate_portfolio_snapshot_totals(
    portfolio_data: Any,
    *,
    investment_column: str = DEFAULT_INVESTMENT_COLUMN,
    current_value_column: str = DEFAULT_CURRENT_VALUE_COLUMN,
) -> PortfolioSnapshotTotals:
    """
    Calculate aggregate totals from a portfolio snapshot.

    The default column names match the established portfolio schema:

    - Investment
    - Current Value
    """

    records = _to_records(
        portfolio_data,
        source_name="portfolio_data",
    )

    if not records:
        raise AnalyticsDataAdapterError(
            "portfolio_data must contain at least one record."
        )

    total_investment = 0.0
    total_current_value = 0.0

    for index, record in enumerate(records):
        investment = _validate_non_negative_number(
            _require_column(
                record,
                investment_column,
                record_index=index,
                source_name="portfolio_data",
            ),
            f"portfolio_data[{index}].{investment_column}",
        )

        current_value = _validate_non_negative_number(
            _require_column(
                record,
                current_value_column,
                record_index=index,
                source_name="portfolio_data",
            ),
            f"portfolio_data[{index}].{current_value_column}",
        )

        total_investment += investment
        total_current_value += current_value

    if total_investment <= 0:
        raise AnalyticsDataAdapterError(
            "Total portfolio investment must be greater than zero."
        )

    total_profit_loss = (
        total_current_value - total_investment
    )

    total_return_decimal = (
        total_current_value / total_investment
    ) - 1.0

    return PortfolioSnapshotTotals(
        row_count=len(records),
        total_investment=total_investment,
        total_current_value=total_current_value,
        total_profit_loss=total_profit_loss,
        total_return_decimal=total_return_decimal,
        total_return_percent=total_return_decimal * 100.0,
    )


# ============================================================
# Dated Value Adapters
# ============================================================


def create_dated_values(
    history_data: Any,
    *,
    date_column: str = DEFAULT_DATE_COLUMN,
    value_column: str = DEFAULT_VALUE_COLUMN,
) -> tuple[DatedValue, ...]:
    """
    Convert historical tabular records into dated values.

    Records are sorted chronologically. Duplicate dates are rejected.
    """

    records = _to_records(
        history_data,
        source_name="history_data",
    )

    if len(records) < 2:
        raise AnalyticsDataAdapterError(
            "history_data must contain at least two records."
        )

    values: list[DatedValue] = []

    for index, record in enumerate(records):
        observation_date = _normalise_date(
            _require_column(
                record,
                date_column,
                record_index=index,
                source_name="history_data",
            ),
            f"history_data[{index}].{date_column}",
        )

        value = _validate_positive_number(
            _require_column(
                record,
                value_column,
                record_index=index,
                source_name="history_data",
            ),
            f"history_data[{index}].{value_column}",
        )

        values.append(
            DatedValue(
                observation_date=observation_date,
                value=value,
            )
        )

    sorted_values = tuple(
        sorted(
            values,
            key=lambda item: item.observation_date,
        )
    )

    for index in range(1, len(sorted_values)):
        if (
            sorted_values[index].observation_date
            == sorted_values[index - 1].observation_date
        ):
            duplicate_date = (
                sorted_values[index].observation_date
            )

            raise AnalyticsDataAdapterError(
                "Duplicate historical date detected: "
                f"{duplicate_date.isoformat()}."
            )

    return sorted_values


def calculate_periodic_returns_from_dated_values(
    dated_values: Sequence[DatedValue],
) -> tuple[float, ...]:
    """
    Convert ordered dated values into periodic returns.
    """

    if len(dated_values) < 3:
        raise AnalyticsDataAdapterError(
            "At least three dated values are required to produce "
            "two periodic returns."
        )

    periodic_returns: list[float] = []

    for index in range(1, len(dated_values)):
        previous_value = _validate_positive_number(
            dated_values[index - 1].value,
            f"dated_values[{index - 1}].value",
        )

        current_value = _validate_non_negative_number(
            dated_values[index].value,
            f"dated_values[{index}].value",
        )

        periodic_return = (
            current_value / previous_value
        ) - 1.0

        if not isfinite(periodic_return):
            raise AnalyticsDataAdapterError(
                f"Unable to calculate return at index {index}."
            )

        periodic_returns.append(periodic_return)

    return tuple(periodic_returns)


def calculate_periodic_returns_from_history(
    history_data: Any,
    *,
    date_column: str = DEFAULT_DATE_COLUMN,
    value_column: str = DEFAULT_VALUE_COLUMN,
) -> tuple[float, ...]:
    """
    Convert historical tabular data directly into periodic returns.
    """

    dated_values = create_dated_values(
        history_data,
        date_column=date_column,
        value_column=value_column,
    )

    return calculate_periodic_returns_from_dated_values(
        dated_values
    )


# ============================================================
# CAGR Adapter
# ============================================================


def create_cagr_input_from_values(
    *,
    initial_value: float,
    final_value: float,
    start_date: date | datetime | str,
    end_date: date | datetime | str,
) -> DateBasedCAGRInput:
    """
    Create a validated date-based CAGR input.
    """

    return DateBasedCAGRInput(
        initial_value=_validate_positive_number(
            initial_value,
            "initial_value",
        ),
        final_value=_validate_non_negative_number(
            final_value,
            "final_value",
        ),
        start_date=_normalise_date(
            start_date,
            "start_date",
        ),
        end_date=_normalise_date(
            end_date,
            "end_date",
        ),
    )


def create_cagr_input_from_history(
    history_data: Any,
    *,
    date_column: str = DEFAULT_DATE_COLUMN,
    value_column: str = DEFAULT_VALUE_COLUMN,
) -> DateBasedCAGRInput:
    """
    Create CAGR input from the first and final historical observations.
    """

    dated_values = create_dated_values(
        history_data,
        date_column=date_column,
        value_column=value_column,
    )

    first = dated_values[0]
    last = dated_values[-1]

    return create_cagr_input_from_values(
        initial_value=first.value,
        final_value=last.value,
        start_date=first.observation_date,
        end_date=last.observation_date,
    )


# ============================================================
# Cash-Flow and XIRR Adapters
# ============================================================


def create_dated_cash_flows(
    cash_flow_data: Any,
    *,
    date_column: str = DEFAULT_CASH_FLOW_DATE_COLUMN,
    amount_column: str = DEFAULT_CASH_FLOW_AMOUNT_COLUMN,
) -> tuple[DatedCashFlow, ...]:
    """
    Convert transaction records into normalised dated cash flows.

    Sign convention:

    - Investments and purchases: negative
    - Redemptions and withdrawals: positive
    - Current value: positive terminal cash flow
    """

    records = _to_records(
        cash_flow_data,
        source_name="cash_flow_data",
    )

    if len(records) < 2:
        raise AnalyticsDataAdapterError(
            "cash_flow_data must contain at least two records."
        )

    cash_flows: list[DatedCashFlow] = []

    for index, record in enumerate(records):
        flow_date = _normalise_date(
            _require_column(
                record,
                date_column,
                record_index=index,
                source_name="cash_flow_data",
            ),
            f"cash_flow_data[{index}].{date_column}",
        )

        amount = _validate_finite_number(
            _require_column(
                record,
                amount_column,
                record_index=index,
                source_name="cash_flow_data",
            ),
            f"cash_flow_data[{index}].{amount_column}",
        )

        cash_flows.append(
            DatedCashFlow(
                flow_date=flow_date,
                amount=amount,
            )
        )

    return tuple(
        sorted(
            cash_flows,
            key=lambda item: item.flow_date,
        )
    )


def create_xirr_input(
    cash_flow_data: Any,
    *,
    date_column: str = DEFAULT_CASH_FLOW_DATE_COLUMN,
    amount_column: str = DEFAULT_CASH_FLOW_AMOUNT_COLUMN,
    current_value: float | None = None,
    valuation_date: date | datetime | str | None = None,
    guess: float = 0.10,
    tolerance: float = 1e-7,
    max_iterations: int = 100,
) -> XIRRInput:
    """
    Create an XIRR input from transaction records.

    When current_value is provided, valuation_date must also be supplied.
    The current value is appended as a positive terminal cash flow.
    """

    dated_cash_flows = list(
        create_dated_cash_flows(
            cash_flow_data,
            date_column=date_column,
            amount_column=amount_column,
        )
    )

    if current_value is not None:
        if valuation_date is None:
            raise AnalyticsDataAdapterError(
                "valuation_date is required when current_value is supplied."
            )

        terminal_value = _validate_positive_number(
            current_value,
            "current_value",
        )

        terminal_date = _normalise_date(
            valuation_date,
            "valuation_date",
        )

        dated_cash_flows.append(
            DatedCashFlow(
                flow_date=terminal_date,
                amount=terminal_value,
            )
        )

    elif valuation_date is not None:
        raise AnalyticsDataAdapterError(
            "current_value is required when valuation_date is supplied."
        )

    sorted_cash_flows = tuple(
        sorted(
            dated_cash_flows,
            key=lambda item: item.flow_date,
        )
    )

    return XIRRInput(
        cash_flows=tuple(
            CashFlow(
                amount=flow.amount,
                flow_date=flow.flow_date,
            )
            for flow in sorted_cash_flows
        ),
        guess=_validate_finite_number(
            guess,
            "guess",
        ),
        tolerance=_validate_positive_number(
            tolerance,
            "tolerance",
        ),
        max_iterations=_validate_positive_integer(
            max_iterations,
            "max_iterations",
        ),
    )


# ============================================================
# Observation Input Adapters
# ============================================================


def create_drawdown_input(
    history_data: Any,
    *,
    date_column: str = DEFAULT_DATE_COLUMN,
    value_column: str = DEFAULT_VALUE_COLUMN,
) -> DrawdownInput:
    """
    Create drawdown input from historical values.
    """

    dated_values = create_dated_values(
        history_data,
        date_column=date_column,
        value_column=value_column,
    )

    return DrawdownInput(
        observations=tuple(
            DrawdownObservation(
                observation_date=item.observation_date,
                value=item.value,
            )
            for item in dated_values
        )
    )


def create_rolling_returns_input(
    history_data: Any,
    *,
    date_column: str = DEFAULT_DATE_COLUMN,
    value_column: str = DEFAULT_VALUE_COLUMN,
    window_size: int = DEFAULT_ROLLING_WINDOW_SIZE,
    annualise: bool = True,
    target_return: float | None = None,
) -> RollingReturnsInput:
    """
    Create rolling-return input from historical values.
    """

    dated_values = create_dated_values(
        history_data,
        date_column=date_column,
        value_column=value_column,
    )

    normalised_target: float | None

    if target_return is None:
        normalised_target = None
    else:
        normalised_target = _validate_finite_number(
            target_return,
            "target_return",
        )

    return RollingReturnsInput(
        observations=tuple(
            RollingObservation(
                observation_date=item.observation_date,
                value=item.value,
            )
            for item in dated_values
        ),
        window_size=_validate_positive_integer(
            window_size,
            "window_size",
        ),
        annualise=_validate_boolean(
            annualise,
            "annualise",
        ),
        target_return=normalised_target,
    )


# ============================================================
# Return-Based Input Adapters
# ============================================================


def create_volatility_input(
    returns: Iterable[float | int],
    *,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
) -> VolatilityInput:
    """
    Create volatility input from periodic returns.
    """

    normalised_returns = _normalise_return_sequence(
        returns,
        field_name="returns",
    )

    return VolatilityInput(
        returns=normalised_returns,
        periods_per_year=_validate_positive_integer(
            periods_per_year,
            "periods_per_year",
        ),
    )


def create_volatility_input_from_history(
    history_data: Any,
    *,
    date_column: str = DEFAULT_DATE_COLUMN,
    value_column: str = DEFAULT_VALUE_COLUMN,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
) -> VolatilityInput:
    """
    Create volatility input directly from historical values.
    """

    returns = calculate_periodic_returns_from_history(
        history_data,
        date_column=date_column,
        value_column=value_column,
    )

    return create_volatility_input(
        returns,
        periods_per_year=periods_per_year,
    )


def create_risk_metrics_input(
    returns: Iterable[float | int],
    *,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
    annual_risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    annual_minimum_acceptable_return: float = (
        DEFAULT_MINIMUM_ACCEPTABLE_RETURN
    ),
) -> RiskMetricsInput:
    """
    Create risk-adjusted metrics input from periodic returns.
    """

    return RiskMetricsInput(
        returns=_normalise_return_sequence(
            returns,
            field_name="returns",
        ),
        periods_per_year=_validate_positive_integer(
            periods_per_year,
            "periods_per_year",
        ),
        annual_risk_free_rate=_validate_finite_number(
            annual_risk_free_rate,
            "annual_risk_free_rate",
        ),
        annual_minimum_acceptable_return=(
            _validate_finite_number(
                annual_minimum_acceptable_return,
                "annual_minimum_acceptable_return",
            )
        ),
    )


def create_risk_metrics_input_from_history(
    history_data: Any,
    *,
    date_column: str = DEFAULT_DATE_COLUMN,
    value_column: str = DEFAULT_VALUE_COLUMN,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
    annual_risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    annual_minimum_acceptable_return: float = (
        DEFAULT_MINIMUM_ACCEPTABLE_RETURN
    ),
) -> RiskMetricsInput:
    """
    Create risk-metric input directly from historical values.
    """

    returns = calculate_periodic_returns_from_history(
        history_data,
        date_column=date_column,
        value_column=value_column,
    )

    return create_risk_metrics_input(
        returns,
        periods_per_year=periods_per_year,
        annual_risk_free_rate=annual_risk_free_rate,
        annual_minimum_acceptable_return=(
            annual_minimum_acceptable_return
        ),
    )


def _normalise_return_sequence(
    returns: Iterable[float | int],
    *,
    field_name: str,
) -> tuple[float, ...]:
    """
    Validate and normalise a return sequence.
    """

    if isinstance(returns, (str, bytes)):
        raise AnalyticsDataAdapterError(
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
        raise AnalyticsDataAdapterError(
            f"{field_name} must be an iterable of numeric values."
        ) from exc

    if len(normalised_returns) < 2:
        raise AnalyticsDataAdapterError(
            f"{field_name} must contain at least two observations."
        )

    return normalised_returns


# ============================================================
# Benchmark Adapters
# ============================================================


def create_aligned_return_series(
    aligned_return_data: Any,
    *,
    portfolio_return_column: str = (
        DEFAULT_PORTFOLIO_RETURN_COLUMN
    ),
    benchmark_return_column: str = (
        DEFAULT_BENCHMARK_RETURN_COLUMN
    ),
) -> AlignedReturnSeries:
    """
    Create aligned portfolio and benchmark return sequences.
    """

    records = _to_records(
        aligned_return_data,
        source_name="aligned_return_data",
    )

    if len(records) < 2:
        raise AnalyticsDataAdapterError(
            "aligned_return_data must contain at least two records."
        )

    portfolio_returns: list[float] = []
    benchmark_returns: list[float] = []

    for index, record in enumerate(records):
        portfolio_returns.append(
            _validate_finite_number(
                _require_column(
                    record,
                    portfolio_return_column,
                    record_index=index,
                    source_name="aligned_return_data",
                ),
                (
                    f"aligned_return_data[{index}]."
                    f"{portfolio_return_column}"
                ),
            )
        )

        benchmark_returns.append(
            _validate_finite_number(
                _require_column(
                    record,
                    benchmark_return_column,
                    record_index=index,
                    source_name="aligned_return_data",
                ),
                (
                    f"aligned_return_data[{index}]."
                    f"{benchmark_return_column}"
                ),
            )
        )

    return AlignedReturnSeries(
        portfolio_returns=tuple(portfolio_returns),
        benchmark_returns=tuple(benchmark_returns),
        observation_count=len(records),
    )


def create_benchmark_input(
    portfolio_returns: Iterable[float | int],
    benchmark_returns: Iterable[float | int],
    *,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
    annual_risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    benchmark_name: str | None = None,
) -> BenchmarkInput:
    """
    Create benchmark-relative input from aligned return sequences.
    """

    normalised_portfolio_returns = (
        _normalise_return_sequence(
            portfolio_returns,
            field_name="portfolio_returns",
        )
    )

    normalised_benchmark_returns = (
        _normalise_return_sequence(
            benchmark_returns,
            field_name="benchmark_returns",
        )
    )

    if len(normalised_portfolio_returns) != len(
        normalised_benchmark_returns
    ):
        raise AnalyticsDataAdapterError(
            "portfolio_returns and benchmark_returns must contain "
            "the same number of observations."
        )

    return BenchmarkInput(
        portfolio_returns=normalised_portfolio_returns,
        benchmark_returns=normalised_benchmark_returns,
        periods_per_year=_validate_positive_integer(
            periods_per_year,
            "periods_per_year",
        ),
        annual_risk_free_rate=_validate_finite_number(
            annual_risk_free_rate,
            "annual_risk_free_rate",
        ),
        benchmark_name=benchmark_name,
    )


def create_benchmark_input_from_records(
    aligned_return_data: Any,
    *,
    portfolio_return_column: str = (
        DEFAULT_PORTFOLIO_RETURN_COLUMN
    ),
    benchmark_return_column: str = (
        DEFAULT_BENCHMARK_RETURN_COLUMN
    ),
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
    annual_risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    benchmark_name: str | None = None,
) -> BenchmarkInput:
    """
    Create benchmark input from aligned tabular return records.
    """

    aligned_returns = create_aligned_return_series(
        aligned_return_data,
        portfolio_return_column=portfolio_return_column,
        benchmark_return_column=benchmark_return_column,
    )

    return create_benchmark_input(
        aligned_returns.portfolio_returns,
        aligned_returns.benchmark_returns,
        periods_per_year=periods_per_year,
        annual_risk_free_rate=annual_risk_free_rate,
        benchmark_name=benchmark_name,
    )


# ============================================================
# Advanced Analytics Adapter
# ============================================================


def create_advanced_analytics_input(
    *,
    portfolio_history: Any | None = None,
    cash_flow_history: Any | None = None,
    aligned_benchmark_returns: Any | None = None,
    history_date_column: str = DEFAULT_DATE_COLUMN,
    history_value_column: str = DEFAULT_VALUE_COLUMN,
    cash_flow_date_column: str = (
        DEFAULT_CASH_FLOW_DATE_COLUMN
    ),
    cash_flow_amount_column: str = (
        DEFAULT_CASH_FLOW_AMOUNT_COLUMN
    ),
    portfolio_return_column: str = (
        DEFAULT_PORTFOLIO_RETURN_COLUMN
    ),
    benchmark_return_column: str = (
        DEFAULT_BENCHMARK_RETURN_COLUMN
    ),
    current_value: float | None = None,
    valuation_date: date | datetime | str | None = None,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
    annual_risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    annual_minimum_acceptable_return: float = (
        DEFAULT_MINIMUM_ACCEPTABLE_RETURN
    ),
    benchmark_name: str | None = None,
    rolling_window_size: int = DEFAULT_ROLLING_WINDOW_SIZE,
    rolling_annualise: bool = True,
    rolling_target_return: float | None = None,
    fail_fast: bool = False,
) -> AnalyticsAdapterResult:
    """
    Construct a complete or partial AdvancedAnalyticsInput.

    Data availability rules:

    portfolio_history provides:
        - CAGR
        - Volatility
        - Drawdown
        - Risk metrics
        - Rolling returns

    cash_flow_history provides:
        - XIRR

    aligned_benchmark_returns provides:
        - Benchmark-relative metrics

    Missing datasets are treated as unavailable rather than as failures.
    """

    _validate_boolean(
        fail_fast,
        "fail_fast",
    )

    available_metrics: list[str] = []
    unavailable_metrics: list[str] = []

    cagr_input: DateBasedCAGRInput | None = None
    xirr_input: XIRRInput | None = None
    volatility_input: VolatilityInput | None = None
    drawdown_input: DrawdownInput | None = None
    risk_metrics_input: RiskMetricsInput | None = None
    benchmark_input: BenchmarkInput | None = None
    rolling_returns_input: RollingReturnsInput | None = None

    if portfolio_history is not None:
        dated_values = create_dated_values(
            portfolio_history,
            date_column=history_date_column,
            value_column=history_value_column,
        )

        periodic_returns = (
            calculate_periodic_returns_from_dated_values(
                dated_values
            )
        )

        cagr_input = create_cagr_input_from_values(
            initial_value=dated_values[0].value,
            final_value=dated_values[-1].value,
            start_date=dated_values[0].observation_date,
            end_date=dated_values[-1].observation_date,
        )

        volatility_input = create_volatility_input(
            periodic_returns,
            periods_per_year=periods_per_year,
        )

        drawdown_input = DrawdownInput(
            observations=tuple(
                DrawdownObservation(
                    observation_date=item.observation_date,
                    value=item.value,
                )
                for item in dated_values
            )
        )

        risk_metrics_input = create_risk_metrics_input(
            periodic_returns,
            periods_per_year=periods_per_year,
            annual_risk_free_rate=annual_risk_free_rate,
            annual_minimum_acceptable_return=(
                annual_minimum_acceptable_return
            ),
        )

        rolling_returns_input = RollingReturnsInput(
            observations=tuple(
                RollingObservation(
                    observation_date=item.observation_date,
                    value=item.value,
                )
                for item in dated_values
            ),
            window_size=_validate_positive_integer(
                rolling_window_size,
                "rolling_window_size",
            ),
            annualise=_validate_boolean(
                rolling_annualise,
                "rolling_annualise",
            ),
            target_return=rolling_target_return,
        )

        available_metrics.extend(
            (
                "cagr",
                "volatility",
                "drawdown",
                "risk_metrics",
                "rolling_returns",
            )
        )

    else:
        unavailable_metrics.extend(
            (
                "cagr",
                "volatility",
                "drawdown",
                "risk_metrics",
                "rolling_returns",
            )
        )

    if cash_flow_history is not None:
        xirr_input = create_xirr_input(
            cash_flow_history,
            date_column=cash_flow_date_column,
            amount_column=cash_flow_amount_column,
            current_value=current_value,
            valuation_date=valuation_date,
        )

        available_metrics.append("xirr")

    else:
        unavailable_metrics.append("xirr")

    if aligned_benchmark_returns is not None:
        benchmark_input = create_benchmark_input_from_records(
            aligned_benchmark_returns,
            portfolio_return_column=portfolio_return_column,
            benchmark_return_column=benchmark_return_column,
            periods_per_year=periods_per_year,
            annual_risk_free_rate=annual_risk_free_rate,
            benchmark_name=benchmark_name,
        )

        available_metrics.append("benchmark")

    else:
        unavailable_metrics.append("benchmark")

    analytics_input = AdvancedAnalyticsInput(
        cagr=cagr_input,
        xirr=xirr_input,
        volatility=volatility_input,
        drawdown=drawdown_input,
        risk_metrics=risk_metrics_input,
        benchmark=benchmark_input,
        rolling_returns=rolling_returns_input,
        fail_fast=fail_fast,
    )

    return AnalyticsAdapterResult(
        analytics_input=analytics_input,
        available_metrics=tuple(available_metrics),
        unavailable_metrics=tuple(unavailable_metrics),
    )


# ============================================================
# Module Exports
# ============================================================


__all__ = [
    "AlignedReturnSeries",
    "AnalyticsAdapterResult",
    "AnalyticsDataAdapterError",
    "DEFAULT_BENCHMARK_RETURN_COLUMN",
    "DEFAULT_CASH_FLOW_AMOUNT_COLUMN",
    "DEFAULT_CASH_FLOW_DATE_COLUMN",
    "DEFAULT_CURRENT_VALUE_COLUMN",
    "DEFAULT_DATE_COLUMN",
    "DEFAULT_INVESTMENT_COLUMN",
    "DEFAULT_MINIMUM_ACCEPTABLE_RETURN",
    "DEFAULT_PERIODS_PER_YEAR",
    "DEFAULT_PORTFOLIO_RETURN_COLUMN",
    "DEFAULT_RISK_FREE_RATE",
    "DEFAULT_ROLLING_WINDOW_SIZE",
    "DEFAULT_VALUE_COLUMN",
    "DatedCashFlow",
    "DatedValue",
    "PortfolioSnapshotTotals",
    "calculate_periodic_returns_from_dated_values",
    "calculate_periodic_returns_from_history",
    "calculate_portfolio_snapshot_totals",
    "create_advanced_analytics_input",
    "create_aligned_return_series",
    "create_benchmark_input",
    "create_benchmark_input_from_records",
    "create_cagr_input_from_history",
    "create_cagr_input_from_values",
    "create_dated_cash_flows",
    "create_dated_values",
    "create_drawdown_input",
    "create_risk_metrics_input",
    "create_risk_metrics_input_from_history",
    "create_rolling_returns_input",
    "create_volatility_input",
    "create_volatility_input_from_history",
    "create_xirr_input",
]