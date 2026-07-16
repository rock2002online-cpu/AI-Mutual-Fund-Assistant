"""
Advanced portfolio analytics orchestration.

This module coordinates the independently tested analytics services:

- CAGR
- XIRR
- Volatility
- Drawdown
- Risk-adjusted metrics
- Benchmark-relative metrics
- Rolling returns

The module does not retrieve portfolio data directly.

PortfolioService remains the single source of portfolio data. Calling
services should retrieve and transform portfolio history, cash flows,
benchmark returns, and valuation observations before constructing the typed
input models defined here.

The module contains no Streamlit, Plotly, or pandas dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from services.analytics.benchmark import (
    BenchmarkInput,
    BenchmarkResult,
    calculate_benchmark_metrics,
)
from services.analytics.cagr import (
    CAGRResult,
    DateBasedCAGRInput,
    calculate_date_based_cagr,
)
from services.analytics.drawdown import (
    DrawdownInput,
    DrawdownResult,
    calculate_drawdown,
)
from services.analytics.risk_metrics import (
    RiskMetricsInput,
    RiskMetricsResult,
    calculate_risk_metrics,
)
from services.analytics.rolling_returns import (
    RollingReturnsInput,
    RollingReturnsResult,
    calculate_rolling_returns,
)
from services.analytics.volatility import (
    VolatilityInput,
    VolatilityResult,
    calculate_volatility,
)
from services.analytics.xirr import (
    XIRRInput,
    XIRRResult,
    calculate_xirr,
)


# ============================================================
# Type Aliases
# ============================================================

AnalyticsStatus = Literal[
    "complete",
    "partial",
    "unavailable",
]

MetricName = Literal[
    "cagr",
    "xirr",
    "volatility",
    "drawdown",
    "risk_metrics",
    "benchmark",
    "rolling_returns",
]


# ============================================================
# Exceptions
# ============================================================


class AdvancedAnalyticsValidationError(ValueError):
    """
    Raised when advanced analytics input is invalid.
    """


class AdvancedAnalyticsCalculationError(RuntimeError):
    """
    Raised when strict advanced analytics calculation fails.
    """


# ============================================================
# Input Models
# ============================================================


@dataclass(frozen=True, slots=True)
class AdvancedAnalyticsInput:
    """
    Typed input for advanced portfolio analytics.

    Every metric input is optional because historical data availability may
    differ between portfolios.

    Attributes:
        cagr:
            Date-based beginning and ending portfolio values.

        xirr:
            Dated portfolio cash flows.

        volatility:
            Periodic portfolio returns.

        drawdown:
            Historical portfolio value observations.

        risk_metrics:
            Periodic returns and risk-adjusted calculation settings.

        benchmark:
            Aligned portfolio and benchmark returns.

        rolling_returns:
            Dated historical portfolio values and rolling-window settings.

        fail_fast:
            When True, the first metric error is raised immediately.

            When False, metric failures are captured in the result and other
            available metrics continue processing.
    """

    cagr: DateBasedCAGRInput | None = None
    xirr: XIRRInput | None = None
    volatility: VolatilityInput | None = None
    drawdown: DrawdownInput | None = None
    risk_metrics: RiskMetricsInput | None = None
    benchmark: BenchmarkInput | None = None
    rolling_returns: RollingReturnsInput | None = None
    fail_fast: bool = False


# ============================================================
# Failure and Result Models
# ============================================================


@dataclass(frozen=True, slots=True)
class AnalyticsFailure:
    """
    Represents one unavailable or failed metric.

    Attributes:
        metric:
            Analytics metric that could not be calculated.

        error_type:
            Exception class name or unavailable-data classification.

        message:
            Human-readable failure explanation.
    """

    metric: MetricName
    error_type: str
    message: str


@dataclass(frozen=True, slots=True)
class AdvancedAnalyticsResult:
    """
    Combined advanced portfolio analytics result.

    Attributes:
        status:
            complete:
                Every requested metric succeeded.

            partial:
                At least one metric succeeded and at least one requested
                metric failed.

            unavailable:
                No metric was requested or no requested metric succeeded.

        requested_metric_count:
            Number of non-None metric inputs supplied.

        successful_metric_count:
            Number of metrics successfully calculated.

        failed_metric_count:
            Number of requested metrics that failed.

        cagr:
            Portfolio CAGR result when available.

        xirr:
            Portfolio XIRR result when available.

        volatility:
            Portfolio volatility result when available.

        drawdown:
            Portfolio drawdown result when available.

        risk_metrics:
            Portfolio risk-adjusted metric result when available.

        benchmark:
            Portfolio benchmark-relative result when available.

        rolling_returns:
            Portfolio rolling-return result when available.

        failures:
            Captured failures when fail_fast is disabled.
    """

    status: AnalyticsStatus

    requested_metric_count: int
    successful_metric_count: int
    failed_metric_count: int

    cagr: CAGRResult | None
    xirr: XIRRResult | None
    volatility: VolatilityResult | None
    drawdown: DrawdownResult | None
    risk_metrics: RiskMetricsResult | None
    benchmark: BenchmarkResult | None
    rolling_returns: RollingReturnsResult | None

    failures: tuple[AnalyticsFailure, ...]


# ============================================================
# Validation
# ============================================================


def validate_advanced_analytics_input(
    input_data: AdvancedAnalyticsInput,
) -> AdvancedAnalyticsInput:
    """
    Validate the advanced analytics orchestration input.

    Metric-specific validation remains inside each specialised analytics
    module. This function validates only orchestration-level types.
    """

    if not isinstance(input_data, AdvancedAnalyticsInput):
        raise TypeError(
            "input_data must be an instance of AdvancedAnalyticsInput."
        )

    if not isinstance(input_data.fail_fast, bool):
        raise AdvancedAnalyticsValidationError(
            "fail_fast must be a boolean."
        )

    expected_types: tuple[
        tuple[
            str,
            object,
            type[object],
        ],
        ...,
    ] = (
        (
            "cagr",
            input_data.cagr,
            DateBasedCAGRInput,
        ),
        (
            "xirr",
            input_data.xirr,
            XIRRInput,
        ),
        (
            "volatility",
            input_data.volatility,
            VolatilityInput,
        ),
        (
            "drawdown",
            input_data.drawdown,
            DrawdownInput,
        ),
        (
            "risk_metrics",
            input_data.risk_metrics,
            RiskMetricsInput,
        ),
        (
            "benchmark",
            input_data.benchmark,
            BenchmarkInput,
        ),
        (
            "rolling_returns",
            input_data.rolling_returns,
            RollingReturnsInput,
        ),
    )

    for field_name, value, expected_type in expected_types:
        if value is None:
            continue

        if not isinstance(value, expected_type):
            raise AdvancedAnalyticsValidationError(
                f"{field_name} must be an instance of "
                f"{expected_type.__name__} or None."
            )

    return input_data


# ============================================================
# Status Helper
# ============================================================


def _determine_status(
    *,
    requested_count: int,
    successful_count: int,
    failed_count: int,
) -> AnalyticsStatus:
    """
    Determine the aggregate analytics status.
    """

    if requested_count == 0 or successful_count == 0:
        return "unavailable"

    if failed_count > 0:
        return "partial"

    return "complete"


# ============================================================
# Metric Execution Helper
# ============================================================


def _capture_calculation(
    *,
    metric: MetricName,
    calculation: object,
    failures: list[AnalyticsFailure],
    fail_fast: bool,
) -> object | None:
    """
    Execute one analytics calculation and capture failures.

    Args:
        metric:
            Name of the metric being calculated.

        calculation:
            Zero-argument callable performing the calculation.

        failures:
            Mutable internal failure accumulator.

        fail_fast:
            Whether the original exception should immediately propagate.

    Returns:
        Calculation result or None when a failure is captured.
    """

    if not callable(calculation):
        raise AdvancedAnalyticsValidationError(
            "calculation must be callable."
        )

    try:
        return calculation()

    except Exception as exc:
        if fail_fast:
            raise AdvancedAnalyticsCalculationError(
                f"Unable to calculate {metric}: {exc}"
            ) from exc

        failures.append(
            AnalyticsFailure(
                metric=metric,
                error_type=type(exc).__name__,
                message=str(exc),
            )
        )

        return None


# ============================================================
# Main Orchestration API
# ============================================================


def calculate_advanced_analytics(
    input_data: AdvancedAnalyticsInput,
) -> AdvancedAnalyticsResult:
    """
    Calculate all requested advanced portfolio metrics.

    Only metrics whose input models are supplied are attempted. A missing
    input is treated as not requested and is not recorded as a failure.

    By default, individual metric failures are captured so one unavailable
    historical dataset does not block all portfolio analytics.

    Args:
        input_data:
            Typed advanced analytics input.

    Returns:
        Combined AdvancedAnalyticsResult.

    Raises:
        TypeError:
            If input_data has an unsupported type.

        AdvancedAnalyticsValidationError:
            If orchestration-level validation fails.

        AdvancedAnalyticsCalculationError:
            If fail_fast=True and a requested calculation fails.
    """

    validated_input = validate_advanced_analytics_input(
        input_data
    )

    requested_metric_count = sum(
        value is not None
        for value in (
            validated_input.cagr,
            validated_input.xirr,
            validated_input.volatility,
            validated_input.drawdown,
            validated_input.risk_metrics,
            validated_input.benchmark,
            validated_input.rolling_returns,
        )
    )

    failures: list[AnalyticsFailure] = []

    cagr_result: CAGRResult | None = None
    xirr_result: XIRRResult | None = None
    volatility_result: VolatilityResult | None = None
    drawdown_result: DrawdownResult | None = None
    risk_metrics_result: RiskMetricsResult | None = None
    benchmark_result: BenchmarkResult | None = None
    rolling_returns_result: RollingReturnsResult | None = None

    if validated_input.cagr is not None:
        result = _capture_calculation(
            metric="cagr",
            calculation=lambda: calculate_date_based_cagr(
                validated_input.cagr
            ),
            failures=failures,
            fail_fast=validated_input.fail_fast,
        )

        if isinstance(result, CAGRResult):
            cagr_result = result

    if validated_input.xirr is not None:
        result = _capture_calculation(
            metric="xirr",
            calculation=lambda: calculate_xirr(
                validated_input.xirr
            ),
            failures=failures,
            fail_fast=validated_input.fail_fast,
        )

        if isinstance(result, XIRRResult):
            xirr_result = result

    if validated_input.volatility is not None:
        result = _capture_calculation(
            metric="volatility",
            calculation=lambda: calculate_volatility(
                validated_input.volatility
            ),
            failures=failures,
            fail_fast=validated_input.fail_fast,
        )

        if isinstance(result, VolatilityResult):
            volatility_result = result

    if validated_input.drawdown is not None:
        result = _capture_calculation(
            metric="drawdown",
            calculation=lambda: calculate_drawdown(
                validated_input.drawdown
            ),
            failures=failures,
            fail_fast=validated_input.fail_fast,
        )

        if isinstance(result, DrawdownResult):
            drawdown_result = result

    if validated_input.risk_metrics is not None:
        result = _capture_calculation(
            metric="risk_metrics",
            calculation=lambda: calculate_risk_metrics(
                validated_input.risk_metrics
            ),
            failures=failures,
            fail_fast=validated_input.fail_fast,
        )

        if isinstance(result, RiskMetricsResult):
            risk_metrics_result = result

    if validated_input.benchmark is not None:
        result = _capture_calculation(
            metric="benchmark",
            calculation=lambda: calculate_benchmark_metrics(
                validated_input.benchmark
            ),
            failures=failures,
            fail_fast=validated_input.fail_fast,
        )

        if isinstance(result, BenchmarkResult):
            benchmark_result = result

    if validated_input.rolling_returns is not None:
        result = _capture_calculation(
            metric="rolling_returns",
            calculation=lambda: calculate_rolling_returns(
                validated_input.rolling_returns
            ),
            failures=failures,
            fail_fast=validated_input.fail_fast,
        )

        if isinstance(result, RollingReturnsResult):
            rolling_returns_result = result

    successful_metric_count = sum(
        value is not None
        for value in (
            cagr_result,
            xirr_result,
            volatility_result,
            drawdown_result,
            risk_metrics_result,
            benchmark_result,
            rolling_returns_result,
        )
    )

    failed_metric_count = len(failures)

    status = _determine_status(
        requested_count=requested_metric_count,
        successful_count=successful_metric_count,
        failed_count=failed_metric_count,
    )

    return AdvancedAnalyticsResult(
        status=status,
        requested_metric_count=requested_metric_count,
        successful_metric_count=successful_metric_count,
        failed_metric_count=failed_metric_count,
        cagr=cagr_result,
        xirr=xirr_result,
        volatility=volatility_result,
        drawdown=drawdown_result,
        risk_metrics=risk_metrics_result,
        benchmark=benchmark_result,
        rolling_returns=rolling_returns_result,
        failures=tuple(failures),
    )


# ============================================================
# Utility APIs
# ============================================================


def get_successful_metric_names(
    result: AdvancedAnalyticsResult,
) -> tuple[MetricName, ...]:
    """
    Return the names of successfully calculated metrics.
    """

    if not isinstance(result, AdvancedAnalyticsResult):
        raise TypeError(
            "result must be an instance of AdvancedAnalyticsResult."
        )

    successful: list[MetricName] = []

    if result.cagr is not None:
        successful.append("cagr")

    if result.xirr is not None:
        successful.append("xirr")

    if result.volatility is not None:
        successful.append("volatility")

    if result.drawdown is not None:
        successful.append("drawdown")

    if result.risk_metrics is not None:
        successful.append("risk_metrics")

    if result.benchmark is not None:
        successful.append("benchmark")

    if result.rolling_returns is not None:
        successful.append("rolling_returns")

    return tuple(successful)


def get_failed_metric_names(
    result: AdvancedAnalyticsResult,
) -> tuple[MetricName, ...]:
    """
    Return the names of metrics that failed.
    """

    if not isinstance(result, AdvancedAnalyticsResult):
        raise TypeError(
            "result must be an instance of AdvancedAnalyticsResult."
        )

    return tuple(
        failure.metric
        for failure in result.failures
    )


def has_metric(
    result: AdvancedAnalyticsResult,
    metric: MetricName,
) -> bool:
    """
    Return whether a metric was calculated successfully.
    """

    if not isinstance(result, AdvancedAnalyticsResult):
        raise TypeError(
            "result must be an instance of AdvancedAnalyticsResult."
        )

    supported_metrics: tuple[MetricName, ...] = (
        "cagr",
        "xirr",
        "volatility",
        "drawdown",
        "risk_metrics",
        "benchmark",
        "rolling_returns",
    )

    if metric not in supported_metrics:
        raise AdvancedAnalyticsValidationError(
            f"Unsupported analytics metric: {metric!r}."
        )

    return getattr(result, metric) is not None


# ============================================================
# Module Exports
# ============================================================


__all__ = [
    "AdvancedAnalyticsCalculationError",
    "AdvancedAnalyticsInput",
    "AdvancedAnalyticsResult",
    "AdvancedAnalyticsValidationError",
    "AnalyticsFailure",
    "AnalyticsStatus",
    "MetricName",
    "calculate_advanced_analytics",
    "get_failed_metric_names",
    "get_successful_metric_names",
    "has_metric",
    "validate_advanced_analytics_input",
]