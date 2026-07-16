"""
Advanced analytics application service.

This service coordinates:

- Portfolio retrieval through PortfolioService
- Portfolio valuation history retrieval through PortfolioHistoryService
- Portfolio snapshot aggregation
- Analytics data preparation
- Advanced analytics execution
- Availability and failure reporting

The service does not contain Streamlit, Plotly, chart, or view logic.

PortfolioService remains the single source of current portfolio data.

PortfolioHistoryService remains the source of historical portfolio values when
history is not explicitly supplied by the caller.

Cash-flow history and benchmark returns may be supplied by callers until
dedicated transaction-history and benchmark services are added.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal, Protocol, runtime_checkable

from services.analytics.advanced_analytics import (
    AdvancedAnalyticsResult,
    calculate_advanced_analytics,
)
from services.analytics.data_adapter import (
    AnalyticsAdapterResult,
    AnalyticsDataAdapterError,
    PortfolioSnapshotTotals,
    calculate_portfolio_snapshot_totals,
    create_advanced_analytics_input,
)
from services.history.portfolio_history_service import (
    PortfolioHistoryService,
)
from services.portfolio_service import PortfolioService


# ============================================================
# Constants and Type Aliases
# ============================================================

DEFAULT_PERIODS_PER_YEAR = 252
DEFAULT_ROLLING_WINDOW_SIZE = 12
DEFAULT_RISK_FREE_RATE = 0.0
DEFAULT_MINIMUM_ACCEPTABLE_RETURN = 0.0

DEFAULT_INVESTMENT_COLUMN = "Investment"
DEFAULT_CURRENT_VALUE_COLUMN = "Current Value"

DEFAULT_HISTORY_DATE_COLUMN = "Date"
DEFAULT_HISTORY_VALUE_COLUMN = "Value"

DEFAULT_CASH_FLOW_DATE_COLUMN = "Date"
DEFAULT_CASH_FLOW_AMOUNT_COLUMN = "Amount"

DEFAULT_PORTFOLIO_RETURN_COLUMN = "Portfolio Return"
DEFAULT_BENCHMARK_RETURN_COLUMN = "Benchmark Return"

ALL_ADVANCED_METRICS: tuple[str, ...] = (
    "cagr",
    "xirr",
    "volatility",
    "drawdown",
    "risk_metrics",
    "benchmark",
    "rolling_returns",
)

AdvancedAnalyticsServiceStatus = Literal[
    "complete",
    "partial",
    "unavailable",
    "failed",
]


# ============================================================
# Exceptions
# ============================================================


class AdvancedAnalyticsServiceError(RuntimeError):
    """
    Base exception raised by the advanced analytics service.
    """


class AdvancedAnalyticsServiceValidationError(
    AdvancedAnalyticsServiceError
):
    """
    Raised when service-level inputs fail validation.
    """


class PortfolioDataUnavailableError(
    AdvancedAnalyticsServiceError
):
    """
    Raised when current portfolio data cannot be retrieved or is empty.
    """


class AdvancedAnalyticsExecutionError(
    AdvancedAnalyticsServiceError
):
    """
    Raised when analytics preparation or execution fails.
    """


# ============================================================
# Service Protocols
# ============================================================


@runtime_checkable
class PortfolioServiceProtocol(Protocol):
    """
    Minimal interface required from PortfolioService.

    The protocol allows the production service to be replaced by a test
    double without modifying PortfolioService.
    """

    def get_portfolio(self) -> Any:
        """
        Return the current portfolio dataset.
        """


@runtime_checkable
class PortfolioHistoryServiceProtocol(Protocol):
    """
    Minimal interface required from PortfolioHistoryService.

    The protocol allows historical data retrieval to be replaced by a test
    double without placing file-loading logic in the analytics view.
    """

    def get_history(
        self,
        *,
        allow_missing: bool = True,
    ) -> Any:
        """
        Return normalized portfolio valuation history.
        """


# ============================================================
# Service Input Model
# ============================================================


@dataclass(frozen=True, slots=True)
class AdvancedAnalyticsServiceInput:
    """
    Input model for advanced analytics service execution.

    Attributes:
        portfolio_history:
            Optional historical portfolio value records.

            Expected default columns:
                Date
                Value

            When omitted, AdvancedAnalyticsService attempts to retrieve
            history through PortfolioHistoryService.

        cash_flow_history:
            Optional investment, redemption, and transaction records.

            Expected default columns:
                Date
                Amount

            Sign convention:
                Investment or purchase: negative
                Redemption or withdrawal: positive

        aligned_benchmark_returns:
            Optional aligned portfolio and benchmark return records.

            Expected default columns:
                Portfolio Return
                Benchmark Return

        current_value:
            Optional terminal portfolio value appended to cash flows for XIRR.

            When omitted and automatic current portfolio valuation is enabled,
            the service uses the total current portfolio value.

        valuation_date:
            Date associated with the terminal XIRR value.

            When automatic terminal valuation is enabled and this is omitted,
            the current date is used.

        periods_per_year:
            Annualisation frequency.

            Common values:
                252 for daily returns
                52 for weekly returns
                12 for monthly returns

        annual_risk_free_rate:
            Annual risk-free rate represented as a decimal.

        annual_minimum_acceptable_return:
            Annual target used for downside-risk calculations.

        benchmark_name:
            Optional benchmark display name.

        rolling_window_size:
            Number of observation intervals in each rolling-return window.

        rolling_annualise:
            Whether rolling returns should be annualised.

        rolling_target_return:
            Optional rolling-return target represented as a decimal.

        fail_fast:
            When True, raise immediately if analytics preparation or
            execution fails.

        use_current_portfolio_value_for_xirr:
            When True and cash-flow history is supplied, automatically append
            the total current portfolio value when current_value is omitted.

        Column-name attributes:
            Allow alternate source schemas without placing transformation
            logic in views.
    """

    portfolio_history: Any | None = None
    cash_flow_history: Any | None = None
    aligned_benchmark_returns: Any | None = None

    current_value: float | None = None
    valuation_date: date | datetime | str | None = None

    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR

    annual_risk_free_rate: float = DEFAULT_RISK_FREE_RATE

    annual_minimum_acceptable_return: float = (
        DEFAULT_MINIMUM_ACCEPTABLE_RETURN
    )

    benchmark_name: str | None = None

    rolling_window_size: int = DEFAULT_ROLLING_WINDOW_SIZE
    rolling_annualise: bool = True
    rolling_target_return: float | None = None

    fail_fast: bool = False

    use_current_portfolio_value_for_xirr: bool = True

    investment_column: str = DEFAULT_INVESTMENT_COLUMN
    current_value_column: str = DEFAULT_CURRENT_VALUE_COLUMN

    history_date_column: str = DEFAULT_HISTORY_DATE_COLUMN
    history_value_column: str = DEFAULT_HISTORY_VALUE_COLUMN

    cash_flow_date_column: str = DEFAULT_CASH_FLOW_DATE_COLUMN
    cash_flow_amount_column: str = DEFAULT_CASH_FLOW_AMOUNT_COLUMN

    portfolio_return_column: str = DEFAULT_PORTFOLIO_RETURN_COLUMN
    benchmark_return_column: str = DEFAULT_BENCHMARK_RETURN_COLUMN


# ============================================================
# Service Failure and Result Models
# ============================================================


@dataclass(frozen=True, slots=True)
class AdvancedAnalyticsServiceFailure:
    """
    Represents a service-level failure.

    Attributes:
        stage:
            Service stage where the failure occurred.

        error_type:
            Exception class name.

        message:
            Human-readable error message.
    """

    stage: str
    error_type: str
    message: str


@dataclass(frozen=True, slots=True)
class AdvancedAnalyticsServiceResult:
    """
    Combined result exposed to the view layer.

    Attributes:
        status:
            complete:
                Every requested advanced metric succeeded.

            partial:
                At least one requested metric succeeded and another failed.

            unavailable:
                No advanced metric was requested or successfully calculated.

            failed:
                Analytics preparation or service-level execution failed.

        portfolio:
            Current portfolio data returned by PortfolioService.

        portfolio_totals:
            Aggregated current portfolio totals.

        adapter_result:
            Prepared typed analytics inputs and availability information.

        analytics:
            Executed advanced analytics result.

        available_metrics:
            Metrics whose required source data was available.

        unavailable_metrics:
            Metrics omitted because required source data was unavailable.

        failures:
            Service-level failures. Individual metric calculation failures
            remain available under analytics.failures.
    """

    status: AdvancedAnalyticsServiceStatus

    portfolio: Any

    portfolio_totals: PortfolioSnapshotTotals | None

    adapter_result: AnalyticsAdapterResult | None

    analytics: AdvancedAnalyticsResult | None

    available_metrics: tuple[str, ...]

    unavailable_metrics: tuple[str, ...]

    failures: tuple[AdvancedAnalyticsServiceFailure, ...]


# ============================================================
# Validation Helpers
# ============================================================


def _validate_boolean(
    value: object,
    field_name: str,
) -> bool:
    """
    Validate a strict boolean value.
    """

    if not isinstance(value, bool):
        raise AdvancedAnalyticsServiceValidationError(
            f"{field_name} must be a boolean."
        )

    return value


def _validate_positive_integer(
    value: object,
    field_name: str,
) -> int:
    """
    Validate a strict positive integer.
    """

    if isinstance(value, bool) or not isinstance(value, int):
        raise AdvancedAnalyticsServiceValidationError(
            f"{field_name} must be an integer."
        )

    if value <= 0:
        raise AdvancedAnalyticsServiceValidationError(
            f"{field_name} must be greater than zero."
        )

    return value


def _validate_required_column_name(
    value: object,
    field_name: str,
) -> str:
    """
    Validate and normalize a required column name.
    """

    if not isinstance(value, str):
        raise AdvancedAnalyticsServiceValidationError(
            f"{field_name} must be a string."
        )

    normalized_value = value.strip()

    if not normalized_value:
        raise AdvancedAnalyticsServiceValidationError(
            f"{field_name} cannot be empty."
        )

    return normalized_value


def _normalize_optional_text(
    value: object,
    field_name: str,
) -> str | None:
    """
    Normalize optional text and convert blank strings to None.
    """

    if value is None:
        return None

    if not isinstance(value, str):
        raise AdvancedAnalyticsServiceValidationError(
            f"{field_name} must be a string or None."
        )

    normalized_value = value.strip()

    return normalized_value or None


# ============================================================
# Public Input Validation
# ============================================================


def validate_advanced_analytics_service_input(
    input_data: AdvancedAnalyticsServiceInput,
) -> AdvancedAnalyticsServiceInput:
    """
    Validate and normalize service-level input.

    Metric-specific numeric and source-data validation remains inside the
    analytics adapter and specialized analytics modules.
    """

    if not isinstance(
        input_data,
        AdvancedAnalyticsServiceInput,
    ):
        raise TypeError(
            "input_data must be an instance of "
            "AdvancedAnalyticsServiceInput."
        )

    periods_per_year = _validate_positive_integer(
        input_data.periods_per_year,
        "periods_per_year",
    )

    rolling_window_size = _validate_positive_integer(
        input_data.rolling_window_size,
        "rolling_window_size",
    )

    rolling_annualise = _validate_boolean(
        input_data.rolling_annualise,
        "rolling_annualise",
    )

    fail_fast = _validate_boolean(
        input_data.fail_fast,
        "fail_fast",
    )

    use_current_portfolio_value_for_xirr = _validate_boolean(
        input_data.use_current_portfolio_value_for_xirr,
        "use_current_portfolio_value_for_xirr",
    )

    investment_column = _validate_required_column_name(
        input_data.investment_column,
        "investment_column",
    )

    current_value_column = _validate_required_column_name(
        input_data.current_value_column,
        "current_value_column",
    )

    history_date_column = _validate_required_column_name(
        input_data.history_date_column,
        "history_date_column",
    )

    history_value_column = _validate_required_column_name(
        input_data.history_value_column,
        "history_value_column",
    )

    cash_flow_date_column = _validate_required_column_name(
        input_data.cash_flow_date_column,
        "cash_flow_date_column",
    )

    cash_flow_amount_column = _validate_required_column_name(
        input_data.cash_flow_amount_column,
        "cash_flow_amount_column",
    )

    portfolio_return_column = _validate_required_column_name(
        input_data.portfolio_return_column,
        "portfolio_return_column",
    )

    benchmark_return_column = _validate_required_column_name(
        input_data.benchmark_return_column,
        "benchmark_return_column",
    )

    benchmark_name = _normalize_optional_text(
        input_data.benchmark_name,
        "benchmark_name",
    )

    if (
        input_data.current_value is None
        and input_data.valuation_date is not None
        and input_data.cash_flow_history is not None
        and not use_current_portfolio_value_for_xirr
    ):
        raise AdvancedAnalyticsServiceValidationError(
            "current_value is required when valuation_date is supplied "
            "and automatic current portfolio valuation is disabled."
        )

    return AdvancedAnalyticsServiceInput(
        portfolio_history=input_data.portfolio_history,
        cash_flow_history=input_data.cash_flow_history,
        aligned_benchmark_returns=(
            input_data.aligned_benchmark_returns
        ),
        current_value=input_data.current_value,
        valuation_date=input_data.valuation_date,
        periods_per_year=periods_per_year,
        annual_risk_free_rate=(
            input_data.annual_risk_free_rate
        ),
        annual_minimum_acceptable_return=(
            input_data.annual_minimum_acceptable_return
        ),
        benchmark_name=benchmark_name,
        rolling_window_size=rolling_window_size,
        rolling_annualise=rolling_annualise,
        rolling_target_return=input_data.rolling_target_return,
        fail_fast=fail_fast,
        use_current_portfolio_value_for_xirr=(
            use_current_portfolio_value_for_xirr
        ),
        investment_column=investment_column,
        current_value_column=current_value_column,
        history_date_column=history_date_column,
        history_value_column=history_value_column,
        cash_flow_date_column=cash_flow_date_column,
        cash_flow_amount_column=cash_flow_amount_column,
        portfolio_return_column=portfolio_return_column,
        benchmark_return_column=benchmark_return_column,
    )


# ============================================================
# Dataset Helpers
# ============================================================


def _is_empty_dataset(data: Any) -> bool:
    """
    Determine whether a supported dataset is empty.

    Supports pandas-like objects, sequences, and sized collections. Unknown
    iterable types are treated as non-empty and validated later by the data
    adapter.
    """

    if data is None:
        return True

    empty_attribute = getattr(
        data,
        "empty",
        None,
    )

    if isinstance(empty_attribute, bool):
        return empty_attribute

    try:
        return len(data) == 0
    except (TypeError, AttributeError):
        return False


def _get_portfolio(
    portfolio_service: PortfolioServiceProtocol,
) -> Any:
    """
    Retrieve and validate current portfolio data.
    """

    try:
        portfolio = portfolio_service.get_portfolio()
    except Exception as exc:
        raise PortfolioDataUnavailableError(
            f"Unable to retrieve portfolio data: {exc}"
        ) from exc

    if portfolio is None:
        raise PortfolioDataUnavailableError(
            "PortfolioService returned no portfolio data."
        )

    if _is_empty_dataset(portfolio):
        raise PortfolioDataUnavailableError(
            "PortfolioService returned an empty portfolio."
        )

    return portfolio


# ============================================================
# Status Helper
# ============================================================


def _resolve_service_status(
    analytics: AdvancedAnalyticsResult,
) -> AdvancedAnalyticsServiceStatus:
    """
    Convert analytics status into the corresponding service status.
    """

    if analytics.status == "complete":
        return "complete"

    if analytics.status == "partial":
        return "partial"

    return "unavailable"


# ============================================================
# Advanced Analytics Service
# ============================================================


class AdvancedAnalyticsService:
    """
    Application service for advanced portfolio analytics.

    The service:

    - Retrieves current portfolio data through PortfolioService
    - Retrieves optional valuation history through PortfolioHistoryService
    - Prepares datasets through the analytics adapter
    - Executes the advanced analytics orchestrator

    Explicit history supplied through AdvancedAnalyticsServiceInput always
    takes precedence over automatically loaded history.
    """

    def __init__(
        self,
        portfolio_service: PortfolioServiceProtocol | None = None,
        portfolio_history_service: (
            PortfolioHistoryServiceProtocol | None
        ) = None,
    ) -> None:
        """
        Initialize the advanced analytics service.

        Args:
            portfolio_service:
                Optional PortfolioService-compatible dependency.

                When omitted, the production PortfolioService is created.

            portfolio_history_service:
                Optional PortfolioHistoryService-compatible dependency.

                When omitted, the production PortfolioHistoryService is
                created. Missing history remains optional.
        """

        resolved_portfolio_service = (
            portfolio_service
            if portfolio_service is not None
            else PortfolioService()
        )

        if not isinstance(
            resolved_portfolio_service,
            PortfolioServiceProtocol,
        ):
            raise TypeError(
                "portfolio_service must provide a callable "
                "get_portfolio() method."
            )

        resolved_history_service = (
            portfolio_history_service
            if portfolio_history_service is not None
            else PortfolioHistoryService()
        )

        if not isinstance(
            resolved_history_service,
            PortfolioHistoryServiceProtocol,
        ):
            raise TypeError(
                "portfolio_history_service must provide a callable "
                "get_history() method."
            )

        self._portfolio_service = resolved_portfolio_service
        self._portfolio_history_service = resolved_history_service

    def get_current_portfolio(self) -> Any:
        """
        Return validated current portfolio data.
        """

        return _get_portfolio(
            self._portfolio_service
        )

    def get_portfolio_history(self) -> Any | None:
        """
        Return optional normalized portfolio valuation history.

        Automatically discovered history is optional.

        Missing, invalid, empty, or insufficient history returns None so
        analytics that use cash flows, benchmark returns, or current portfolio
        totals can continue independently.

        At least two historical portfolio observations are required before
        valuation history is supplied to the analytics adapter.

        Explicit portfolio history supplied through
        AdvancedAnalyticsServiceInput is not handled here and remains subject
        to normal adapter validation.
        """

        try:
            history = self._portfolio_history_service.get_history(
                allow_missing=True
            )
        except Exception:
            return None

        if history is None or _is_empty_dataset(history):
            return None

        try:
            observation_count = len(history)
        except TypeError:
            return None

        if observation_count < 3:
            return None

        return history

    def calculate(
        self,
        input_data: AdvancedAnalyticsServiceInput | None = None,
    ) -> AdvancedAnalyticsServiceResult:
        """
        Calculate advanced portfolio analytics.

        When portfolio history is not explicitly supplied, the service
        attempts to load it through PortfolioHistoryService.

        When no historical datasets are available, the service still returns
        current portfolio totals and marks the relevant advanced analytics as
        unavailable.
        """

        service_input = validate_advanced_analytics_service_input(
            input_data
            if input_data is not None
            else AdvancedAnalyticsServiceInput()
        )

        portfolio = self.get_current_portfolio()

        try:
            portfolio_totals = calculate_portfolio_snapshot_totals(
                portfolio,
                investment_column=(
                    service_input.investment_column
                ),
                current_value_column=(
                    service_input.current_value_column
                ),
            )
        except AnalyticsDataAdapterError as exc:
            raise AdvancedAnalyticsExecutionError(
                "Unable to calculate current portfolio totals: "
                f"{exc}"
            ) from exc

        try:
            resolved_portfolio_history = (
                service_input.portfolio_history
            )

            if resolved_portfolio_history is None:
                resolved_portfolio_history = (
                    self.get_portfolio_history()
                )

        except Exception as exc:
            if service_input.fail_fast:
                if isinstance(
                    exc,
                    AdvancedAnalyticsExecutionError,
                ):
                    raise

                raise AdvancedAnalyticsExecutionError(
                    "Unable to resolve portfolio valuation history: "
                    f"{exc}"
                ) from exc

            failure = AdvancedAnalyticsServiceFailure(
                stage="portfolio_history",
                error_type=type(exc).__name__,
                message=str(exc),
            )

            return AdvancedAnalyticsServiceResult(
                status="failed",
                portfolio=portfolio,
                portfolio_totals=portfolio_totals,
                adapter_result=None,
                analytics=None,
                available_metrics=(),
                unavailable_metrics=ALL_ADVANCED_METRICS,
                failures=(failure,),
            )

        resolved_current_value = service_input.current_value
        resolved_valuation_date = service_input.valuation_date

        if (
            service_input.cash_flow_history is not None
            and resolved_current_value is None
            and service_input.use_current_portfolio_value_for_xirr
        ):
            resolved_current_value = (
                portfolio_totals.total_current_value
            )

            if resolved_valuation_date is None:
                resolved_valuation_date = date.today()

        try:
            adapter_result = create_advanced_analytics_input(
                portfolio_history=(
                    resolved_portfolio_history
                ),
                cash_flow_history=(
                    service_input.cash_flow_history
                ),
                aligned_benchmark_returns=(
                    service_input.aligned_benchmark_returns
                ),
                history_date_column=(
                    service_input.history_date_column
                ),
                history_value_column=(
                    service_input.history_value_column
                ),
                cash_flow_date_column=(
                    service_input.cash_flow_date_column
                ),
                cash_flow_amount_column=(
                    service_input.cash_flow_amount_column
                ),
                portfolio_return_column=(
                    service_input.portfolio_return_column
                ),
                benchmark_return_column=(
                    service_input.benchmark_return_column
                ),
                current_value=resolved_current_value,
                valuation_date=resolved_valuation_date,
                periods_per_year=(
                    service_input.periods_per_year
                ),
                annual_risk_free_rate=(
                    service_input.annual_risk_free_rate
                ),
                annual_minimum_acceptable_return=(
                    service_input
                    .annual_minimum_acceptable_return
                ),
                benchmark_name=service_input.benchmark_name,
                rolling_window_size=(
                    service_input.rolling_window_size
                ),
                rolling_annualise=(
                    service_input.rolling_annualise
                ),
                rolling_target_return=(
                    service_input.rolling_target_return
                ),
                fail_fast=service_input.fail_fast,
            )

            analytics = calculate_advanced_analytics(
                adapter_result.analytics_input
            )

        except Exception as exc:
            if service_input.fail_fast:
                raise AdvancedAnalyticsExecutionError(
                    f"Advanced analytics execution failed: {exc}"
                ) from exc

            failure = AdvancedAnalyticsServiceFailure(
                stage="analytics_execution",
                error_type=type(exc).__name__,
                message=str(exc),
            )

            return AdvancedAnalyticsServiceResult(
                status="failed",
                portfolio=portfolio,
                portfolio_totals=portfolio_totals,
                adapter_result=None,
                analytics=None,
                available_metrics=(),
                unavailable_metrics=ALL_ADVANCED_METRICS,
                failures=(failure,),
            )

        return AdvancedAnalyticsServiceResult(
            status=_resolve_service_status(
                analytics
            ),
            portfolio=portfolio,
            portfolio_totals=portfolio_totals,
            adapter_result=adapter_result,
            analytics=analytics,
            available_metrics=(
                adapter_result.available_metrics
            ),
            unavailable_metrics=(
                adapter_result.unavailable_metrics
            ),
            failures=(),
        )


# ============================================================
# Functional Convenience API
# ============================================================


def calculate_advanced_portfolio_analytics(
    input_data: AdvancedAnalyticsServiceInput | None = None,
    *,
    portfolio_service: PortfolioServiceProtocol | None = None,
    portfolio_history_service: (
        PortfolioHistoryServiceProtocol | None
    ) = None,
) -> AdvancedAnalyticsServiceResult:
    """
    Calculate advanced portfolio analytics through a convenience function.
    """

    service = AdvancedAnalyticsService(
        portfolio_service=portfolio_service,
        portfolio_history_service=(
            portfolio_history_service
        ),
    )

    return service.calculate(
        input_data
    )


# ============================================================
# Result Utility APIs
# ============================================================


def get_service_failure_messages(
    result: AdvancedAnalyticsServiceResult,
) -> tuple[str, ...]:
    """
    Return service-level failure messages.
    """

    if not isinstance(
        result,
        AdvancedAnalyticsServiceResult,
    ):
        raise TypeError(
            "result must be an instance of "
            "AdvancedAnalyticsServiceResult."
        )

    return tuple(
        failure.message
        for failure in result.failures
    )


def has_advanced_analytics(
    result: AdvancedAnalyticsServiceResult,
) -> bool:
    """
    Return whether at least one advanced metric was calculated.
    """

    if not isinstance(
        result,
        AdvancedAnalyticsServiceResult,
    ):
        raise TypeError(
            "result must be an instance of "
            "AdvancedAnalyticsServiceResult."
        )

    return (
        result.analytics is not None
        and result.analytics.successful_metric_count > 0
    )


def has_portfolio_totals(
    result: AdvancedAnalyticsServiceResult,
) -> bool:
    """
    Return whether current portfolio totals are available.
    """

    if not isinstance(
        result,
        AdvancedAnalyticsServiceResult,
    ):
        raise TypeError(
            "result must be an instance of "
            "AdvancedAnalyticsServiceResult."
        )

    return result.portfolio_totals is not None


# ============================================================
# Module Exports
# ============================================================


__all__ = [
    "ALL_ADVANCED_METRICS",
    "AdvancedAnalyticsExecutionError",
    "AdvancedAnalyticsService",
    "AdvancedAnalyticsServiceError",
    "AdvancedAnalyticsServiceFailure",
    "AdvancedAnalyticsServiceInput",
    "AdvancedAnalyticsServiceResult",
    "AdvancedAnalyticsServiceStatus",
    "AdvancedAnalyticsServiceValidationError",
    "DEFAULT_BENCHMARK_RETURN_COLUMN",
    "DEFAULT_CASH_FLOW_AMOUNT_COLUMN",
    "DEFAULT_CASH_FLOW_DATE_COLUMN",
    "DEFAULT_CURRENT_VALUE_COLUMN",
    "DEFAULT_HISTORY_DATE_COLUMN",
    "DEFAULT_HISTORY_VALUE_COLUMN",
    "DEFAULT_INVESTMENT_COLUMN",
    "DEFAULT_MINIMUM_ACCEPTABLE_RETURN",
    "DEFAULT_PERIODS_PER_YEAR",
    "DEFAULT_PORTFOLIO_RETURN_COLUMN",
    "DEFAULT_RISK_FREE_RATE",
    "DEFAULT_ROLLING_WINDOW_SIZE",
    "PortfolioDataUnavailableError",
    "PortfolioHistoryServiceProtocol",
    "PortfolioServiceProtocol",
    "calculate_advanced_portfolio_analytics",
    "get_service_failure_messages",
    "has_advanced_analytics",
    "has_portfolio_totals",
    "validate_advanced_analytics_service_input",
]