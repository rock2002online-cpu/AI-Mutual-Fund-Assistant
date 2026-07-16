"""
Tests for services.analytics.advanced_analytics.

These tests validate:

- Orchestration-level input validation
- Complete analytics execution
- Partial analytics execution
- Unavailable analytics state
- Failure capture
- fail_fast behaviour
- Successful and failed metric discovery
- Metric availability checks
- Result counts and status consistency
- Immutable dataclasses
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from services.analytics.advanced_analytics import (
    AdvancedAnalyticsCalculationError,
    AdvancedAnalyticsInput,
    AdvancedAnalyticsResult,
    AdvancedAnalyticsValidationError,
    AnalyticsFailure,
    calculate_advanced_analytics,
    get_failed_metric_names,
    get_successful_metric_names,
    has_metric,
    validate_advanced_analytics_input,
)
from services.analytics.benchmark import BenchmarkInput
from services.analytics.cagr import DateBasedCAGRInput
from services.analytics.drawdown import (
    DrawdownInput,
    ValueObservation as DrawdownObservation,
)
from services.analytics.risk_metrics import RiskMetricsInput
from services.analytics.rolling_returns import (
    RollingReturnsInput,
    ValueObservation as RollingObservation,
)
from services.analytics.volatility import VolatilityInput
from services.analytics.xirr import (
    CashFlow,
    XIRRInput,
)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def valid_cagr_input() -> DateBasedCAGRInput:
    """
    Return valid portfolio CAGR input.
    """

    return DateBasedCAGRInput(
        initial_value=100_000.0,
        final_value=150_000.0,
        start_date=date(2023, 1, 1),
        end_date=date(2026, 1, 1),
    )


@pytest.fixture
def valid_xirr_input() -> XIRRInput:
    """
    Return valid portfolio XIRR input.
    """

    return XIRRInput(
        cash_flows=(
            CashFlow(
                amount=-100_000.0,
                flow_date=date(2023, 1, 1),
            ),
            CashFlow(
                amount=120_000.0,
                flow_date=date(2024, 1, 1),
            ),
        )
    )


@pytest.fixture
def valid_volatility_input() -> VolatilityInput:
    """
    Return valid monthly volatility input.
    """

    return VolatilityInput(
        returns=(
            0.02,
            -0.01,
            0.015,
            0.005,
            -0.02,
            0.03,
        ),
        periods_per_year=12,
    )


@pytest.fixture
def valid_drawdown_input() -> DrawdownInput:
    """
    Return valid historical drawdown input.
    """

    return DrawdownInput(
        observations=(
            DrawdownObservation(
                observation_date=date(2024, 1, 1),
                value=100.0,
            ),
            DrawdownObservation(
                observation_date=date(2024, 2, 1),
                value=120.0,
            ),
            DrawdownObservation(
                observation_date=date(2024, 3, 1),
                value=90.0,
            ),
            DrawdownObservation(
                observation_date=date(2024, 4, 1),
                value=125.0,
            ),
        )
    )


@pytest.fixture
def valid_risk_metrics_input() -> RiskMetricsInput:
    """
    Return valid risk-adjusted metric input.
    """

    return RiskMetricsInput(
        returns=(
            0.02,
            -0.01,
            0.015,
            0.005,
            -0.02,
            0.03,
        ),
        periods_per_year=12,
        annual_risk_free_rate=0.06,
        annual_minimum_acceptable_return=0.04,
    )


@pytest.fixture
def valid_benchmark_input() -> BenchmarkInput:
    """
    Return valid benchmark-relative input.
    """

    return BenchmarkInput(
        portfolio_returns=(
            0.02,
            -0.01,
            0.015,
            0.005,
        ),
        benchmark_returns=(
            0.018,
            -0.012,
            0.012,
            0.004,
        ),
        periods_per_year=12,
        annual_risk_free_rate=0.06,
        benchmark_name="Nifty 50 TRI",
    )


@pytest.fixture
def valid_rolling_returns_input() -> RollingReturnsInput:
    """
    Return valid rolling-return input.
    """

    return RollingReturnsInput(
        observations=(
            RollingObservation(
                observation_date=date(2024, 1, 1),
                value=100.0,
            ),
            RollingObservation(
                observation_date=date(2024, 2, 1),
                value=105.0,
            ),
            RollingObservation(
                observation_date=date(2024, 3, 1),
                value=110.0,
            ),
            RollingObservation(
                observation_date=date(2024, 4, 1),
                value=115.0,
            ),
        ),
        window_size=1,
        annualise=False,
        target_return=0.03,
    )


@pytest.fixture
def complete_input(
    valid_cagr_input: DateBasedCAGRInput,
    valid_xirr_input: XIRRInput,
    valid_volatility_input: VolatilityInput,
    valid_drawdown_input: DrawdownInput,
    valid_risk_metrics_input: RiskMetricsInput,
    valid_benchmark_input: BenchmarkInput,
    valid_rolling_returns_input: RollingReturnsInput,
) -> AdvancedAnalyticsInput:
    """
    Return a complete valid advanced analytics input.
    """

    return AdvancedAnalyticsInput(
        cagr=valid_cagr_input,
        xirr=valid_xirr_input,
        volatility=valid_volatility_input,
        drawdown=valid_drawdown_input,
        risk_metrics=valid_risk_metrics_input,
        benchmark=valid_benchmark_input,
        rolling_returns=valid_rolling_returns_input,
        fail_fast=False,
    )


# ============================================================
# Input Validation Tests
# ============================================================


def test_validate_advanced_analytics_input(
    complete_input: AdvancedAnalyticsInput,
) -> None:
    """
    Valid orchestration input should be returned unchanged.
    """

    validated = validate_advanced_analytics_input(
        complete_input
    )

    assert validated is complete_input


def test_validate_input_rejects_wrong_input_type() -> None:
    """
    Validation should reject unsupported top-level input objects.
    """

    with pytest.raises(
        TypeError,
        match="AdvancedAnalyticsInput",
    ):
        validate_advanced_analytics_input(  # type: ignore[arg-type]
            {
                "cagr": None,
            }
        )


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("cagr", "invalid"),
        ("xirr", "invalid"),
        ("volatility", "invalid"),
        ("drawdown", "invalid"),
        ("risk_metrics", "invalid"),
        ("benchmark", "invalid"),
        ("rolling_returns", "invalid"),
    ],
)
def test_validate_input_rejects_invalid_metric_type(
    field_name: str,
    invalid_value: object,
) -> None:
    """
    Every supplied metric must use its expected input dataclass.
    """

    values = {
        "cagr": None,
        "xirr": None,
        "volatility": None,
        "drawdown": None,
        "risk_metrics": None,
        "benchmark": None,
        "rolling_returns": None,
    }

    values[field_name] = invalid_value

    with pytest.raises(
        AdvancedAnalyticsValidationError,
        match=field_name,
    ):
        validate_advanced_analytics_input(
            AdvancedAnalyticsInput(
                **values,  # type: ignore[arg-type]
            )
        )


@pytest.mark.parametrize(
    "fail_fast",
    [
        1,
        0,
        "true",
        None,
    ],
)
def test_validate_input_rejects_invalid_fail_fast(
    fail_fast: object,
) -> None:
    """
    fail_fast must be a strict boolean.
    """

    with pytest.raises(
        AdvancedAnalyticsValidationError,
        match="fail_fast must be a boolean",
    ):
        validate_advanced_analytics_input(
            AdvancedAnalyticsInput(
                fail_fast=fail_fast,  # type: ignore[arg-type]
            )
        )


def test_validate_input_accepts_all_metrics_as_none() -> None:
    """
    Empty orchestration input is valid and produces unavailable status.
    """

    validated = validate_advanced_analytics_input(
        AdvancedAnalyticsInput()
    )

    assert validated.cagr is None
    assert validated.xirr is None
    assert validated.fail_fast is False


# ============================================================
# Complete Calculation Tests
# ============================================================


def test_calculate_complete_advanced_analytics(
    complete_input: AdvancedAnalyticsInput,
) -> None:
    """
    All valid supplied metrics should calculate successfully.
    """

    result = calculate_advanced_analytics(
        complete_input
    )

    assert isinstance(result, AdvancedAnalyticsResult)

    assert result.status == "complete"
    assert result.requested_metric_count == 7
    assert result.successful_metric_count == 7
    assert result.failed_metric_count == 0

    assert result.cagr is not None
    assert result.xirr is not None
    assert result.volatility is not None
    assert result.drawdown is not None
    assert result.risk_metrics is not None
    assert result.benchmark is not None
    assert result.rolling_returns is not None

    assert result.failures == ()


def test_complete_result_metric_values(
    complete_input: AdvancedAnalyticsInput,
) -> None:
    """
    Combined result should preserve specialised metric outputs.
    """

    result = calculate_advanced_analytics(
        complete_input
    )

    assert result.cagr is not None
    assert result.cagr.cagr_percent > 0.0

    assert result.xirr is not None
    assert result.xirr.converged is True

    assert result.volatility is not None
    assert result.volatility.observation_count == 6

    assert result.drawdown is not None
    assert result.drawdown.maximum_drawdown_percent < 0.0

    assert result.risk_metrics is not None
    assert result.risk_metrics.sharpe_ratio is not None

    assert result.benchmark is not None
    assert result.benchmark.benchmark_name == "Nifty 50 TRI"

    assert result.rolling_returns is not None
    assert result.rolling_returns.rolling_period_count == 3


# ============================================================
# Partial Calculation Tests
# ============================================================


def test_calculate_subset_of_metrics(
    valid_cagr_input: DateBasedCAGRInput,
    valid_volatility_input: VolatilityInput,
) -> None:
    """
    A valid subset should still produce complete status.
    """

    result = calculate_advanced_analytics(
        AdvancedAnalyticsInput(
            cagr=valid_cagr_input,
            volatility=valid_volatility_input,
        )
    )

    assert result.status == "complete"
    assert result.requested_metric_count == 2
    assert result.successful_metric_count == 2
    assert result.failed_metric_count == 0

    assert result.cagr is not None
    assert result.volatility is not None

    assert result.xirr is None
    assert result.drawdown is None
    assert result.risk_metrics is None
    assert result.benchmark is None
    assert result.rolling_returns is None


def test_partial_status_when_one_metric_fails(
    valid_cagr_input: DateBasedCAGRInput,
) -> None:
    """
    A failed requested metric should produce partial status when another
    metric succeeds.
    """

    invalid_volatility = VolatilityInput(
        returns=(0.01,),
        periods_per_year=12,
    )

    result = calculate_advanced_analytics(
        AdvancedAnalyticsInput(
            cagr=valid_cagr_input,
            volatility=invalid_volatility,
            fail_fast=False,
        )
    )

    assert result.status == "partial"
    assert result.requested_metric_count == 2
    assert result.successful_metric_count == 1
    assert result.failed_metric_count == 1

    assert result.cagr is not None
    assert result.volatility is None

    assert len(result.failures) == 1
    assert result.failures[0].metric == "volatility"


def test_multiple_failures_are_captured() -> None:
    """
    Multiple metric failures should be captured independently.
    """

    invalid_cagr = DateBasedCAGRInput(
        initial_value=0.0,
        final_value=120.0,
        start_date=date(2024, 1, 1),
        end_date=date(2025, 1, 1),
    )

    invalid_xirr = XIRRInput(
        cash_flows=(
            CashFlow(
                amount=-100.0,
                flow_date=date(2024, 1, 1),
            ),
        )
    )

    result = calculate_advanced_analytics(
        AdvancedAnalyticsInput(
            cagr=invalid_cagr,
            xirr=invalid_xirr,
            fail_fast=False,
        )
    )

    assert result.status == "unavailable"
    assert result.requested_metric_count == 2
    assert result.successful_metric_count == 0
    assert result.failed_metric_count == 2

    assert result.cagr is None
    assert result.xirr is None

    assert get_failed_metric_names(result) == (
        "cagr",
        "xirr",
    )


# ============================================================
# Unavailable Status Tests
# ============================================================


def test_no_requested_metrics_returns_unavailable() -> None:
    """
    Empty input should produce an unavailable result without failures.
    """

    result = calculate_advanced_analytics(
        AdvancedAnalyticsInput()
    )

    assert result.status == "unavailable"
    assert result.requested_metric_count == 0
    assert result.successful_metric_count == 0
    assert result.failed_metric_count == 0

    assert result.failures == ()

    assert get_successful_metric_names(result) == ()
    assert get_failed_metric_names(result) == ()


def test_all_failed_metrics_returns_unavailable() -> None:
    """
    Status should be unavailable when every requested metric fails.
    """

    invalid_drawdown = DrawdownInput(
        observations=(
            DrawdownObservation(
                observation_date=date(2024, 1, 1),
                value=100.0,
            ),
        )
    )

    result = calculate_advanced_analytics(
        AdvancedAnalyticsInput(
            drawdown=invalid_drawdown,
            fail_fast=False,
        )
    )

    assert result.status == "unavailable"
    assert result.requested_metric_count == 1
    assert result.successful_metric_count == 0
    assert result.failed_metric_count == 1

    assert result.drawdown is None
    assert result.failures[0].metric == "drawdown"


# ============================================================
# Failure Capture Tests
# ============================================================


def test_failure_contains_exception_information() -> None:
    """
    Captured failure should include metric, exception type, and message.
    """

    invalid_input = VolatilityInput(
        returns=(0.01,),
        periods_per_year=12,
    )

    result = calculate_advanced_analytics(
        AdvancedAnalyticsInput(
            volatility=invalid_input,
            fail_fast=False,
        )
    )

    failure = result.failures[0]

    assert isinstance(failure, AnalyticsFailure)
    assert failure.metric == "volatility"
    assert failure.error_type == "VolatilityValidationError"

    assert "At least two return observations" in (
        failure.message
    )


def test_metric_failure_does_not_block_following_metrics(
    valid_drawdown_input: DrawdownInput,
) -> None:
    """
    A failed earlier metric should not prevent later valid metrics.
    """

    invalid_cagr = DateBasedCAGRInput(
        initial_value=0.0,
        final_value=100.0,
        start_date=date(2024, 1, 1),
        end_date=date(2025, 1, 1),
    )

    result = calculate_advanced_analytics(
        AdvancedAnalyticsInput(
            cagr=invalid_cagr,
            drawdown=valid_drawdown_input,
            fail_fast=False,
        )
    )

    assert result.cagr is None
    assert result.drawdown is not None

    assert result.status == "partial"
    assert result.successful_metric_count == 1
    assert result.failed_metric_count == 1


# ============================================================
# fail_fast Tests
# ============================================================


def test_fail_fast_raises_calculation_error() -> None:
    """
    fail_fast=True should stop on the first failed calculation.
    """

    invalid_cagr = DateBasedCAGRInput(
        initial_value=0.0,
        final_value=100.0,
        start_date=date(2024, 1, 1),
        end_date=date(2025, 1, 1),
    )

    with pytest.raises(
        AdvancedAnalyticsCalculationError,
        match="Unable to calculate cagr",
    ):
        calculate_advanced_analytics(
            AdvancedAnalyticsInput(
                cagr=invalid_cagr,
                fail_fast=True,
            )
        )


def test_fail_fast_preserves_original_exception_as_cause() -> None:
    """
    Orchestration error should retain the specialised exception as its cause.
    """

    invalid_volatility = VolatilityInput(
        returns=(0.01,),
        periods_per_year=12,
    )

    with pytest.raises(
        AdvancedAnalyticsCalculationError,
    ) as exc_info:
        calculate_advanced_analytics(
            AdvancedAnalyticsInput(
                volatility=invalid_volatility,
                fail_fast=True,
            )
        )

    assert exc_info.value.__cause__ is not None
    assert type(
        exc_info.value.__cause__
    ).__name__ == "VolatilityValidationError"


# ============================================================
# Successful Metric Discovery Tests
# ============================================================


def test_get_successful_metric_names_complete(
    complete_input: AdvancedAnalyticsInput,
) -> None:
    """
    Utility should list successful metrics in stable module order.
    """

    result = calculate_advanced_analytics(
        complete_input
    )

    assert get_successful_metric_names(result) == (
        "cagr",
        "xirr",
        "volatility",
        "drawdown",
        "risk_metrics",
        "benchmark",
        "rolling_returns",
    )


def test_get_successful_metric_names_subset(
    valid_cagr_input: DateBasedCAGRInput,
    valid_drawdown_input: DrawdownInput,
) -> None:
    """
    Utility should list only successfully calculated metrics.
    """

    result = calculate_advanced_analytics(
        AdvancedAnalyticsInput(
            cagr=valid_cagr_input,
            drawdown=valid_drawdown_input,
        )
    )

    assert get_successful_metric_names(result) == (
        "cagr",
        "drawdown",
    )


def test_get_successful_metric_names_rejects_wrong_type() -> None:
    """
    Utility should reject unsupported result objects.
    """

    with pytest.raises(
        TypeError,
        match="AdvancedAnalyticsResult",
    ):
        get_successful_metric_names(  # type: ignore[arg-type]
            {}
        )


# ============================================================
# Failed Metric Discovery Tests
# ============================================================


def test_get_failed_metric_names() -> None:
    """
    Utility should list failed metrics in execution order.
    """

    invalid_cagr = DateBasedCAGRInput(
        initial_value=0.0,
        final_value=100.0,
        start_date=date(2024, 1, 1),
        end_date=date(2025, 1, 1),
    )

    invalid_volatility = VolatilityInput(
        returns=(0.01,),
        periods_per_year=12,
    )

    result = calculate_advanced_analytics(
        AdvancedAnalyticsInput(
            cagr=invalid_cagr,
            volatility=invalid_volatility,
        )
    )

    assert get_failed_metric_names(result) == (
        "cagr",
        "volatility",
    )


def test_get_failed_metric_names_rejects_wrong_type() -> None:
    """
    Utility should reject unsupported result objects.
    """

    with pytest.raises(
        TypeError,
        match="AdvancedAnalyticsResult",
    ):
        get_failed_metric_names(  # type: ignore[arg-type]
            {}
        )


# ============================================================
# has_metric Tests
# ============================================================


@pytest.mark.parametrize(
    "metric",
    [
        "cagr",
        "xirr",
        "volatility",
        "drawdown",
        "risk_metrics",
        "benchmark",
        "rolling_returns",
    ],
)
def test_has_metric_complete_result(
    metric: str,
    complete_input: AdvancedAnalyticsInput,
) -> None:
    """
    Every supported metric should be available in a complete result.
    """

    result = calculate_advanced_analytics(
        complete_input
    )

    assert has_metric(
        result,
        metric,  # type: ignore[arg-type]
    ) is True


def test_has_metric_returns_false_for_missing_metric(
    valid_cagr_input: DateBasedCAGRInput,
) -> None:
    """
    Utility should return False for a metric that was not calculated.
    """

    result = calculate_advanced_analytics(
        AdvancedAnalyticsInput(
            cagr=valid_cagr_input,
        )
    )

    assert has_metric(result, "cagr") is True
    assert has_metric(result, "xirr") is False


def test_has_metric_returns_false_for_failed_metric() -> None:
    """
    Utility should return False when a requested metric failed.
    """

    invalid_volatility = VolatilityInput(
        returns=(0.01,),
        periods_per_year=12,
    )

    result = calculate_advanced_analytics(
        AdvancedAnalyticsInput(
            volatility=invalid_volatility,
        )
    )

    assert has_metric(
        result,
        "volatility",
    ) is False


def test_has_metric_rejects_unsupported_metric() -> None:
    """
    Unsupported metric names should be rejected.
    """

    result = calculate_advanced_analytics(
        AdvancedAnalyticsInput()
    )

    with pytest.raises(
        AdvancedAnalyticsValidationError,
        match="Unsupported analytics metric",
    ):
        has_metric(
            result,
            "invalid_metric",  # type: ignore[arg-type]
        )


def test_has_metric_rejects_wrong_result_type() -> None:
    """
    Utility should reject unsupported result objects.
    """

    with pytest.raises(
        TypeError,
        match="AdvancedAnalyticsResult",
    ):
        has_metric(  # type: ignore[arg-type]
            {},
            "cagr",
        )


# ============================================================
# Result Count Consistency Tests
# ============================================================


def test_result_counts_are_consistent(
    complete_input: AdvancedAnalyticsInput,
) -> None:
    """
    Requested count should equal successful plus failed counts.
    """

    result = calculate_advanced_analytics(
        complete_input
    )

    assert result.requested_metric_count == (
        result.successful_metric_count
        + result.failed_metric_count
    )


def test_partial_result_counts_are_consistent(
    valid_cagr_input: DateBasedCAGRInput,
) -> None:
    """
    Count consistency should also hold for partial results.
    """

    invalid_volatility = VolatilityInput(
        returns=(0.01,),
        periods_per_year=12,
    )

    result = calculate_advanced_analytics(
        AdvancedAnalyticsInput(
            cagr=valid_cagr_input,
            volatility=invalid_volatility,
        )
    )

    assert result.requested_metric_count == 2

    assert result.requested_metric_count == (
        result.successful_metric_count
        + result.failed_metric_count
    )


def test_failed_count_matches_failure_collection() -> None:
    """
    failed_metric_count should equal the number of failure objects.
    """

    invalid_cagr = DateBasedCAGRInput(
        initial_value=0.0,
        final_value=100.0,
        start_date=date(2024, 1, 1),
        end_date=date(2025, 1, 1),
    )

    result = calculate_advanced_analytics(
        AdvancedAnalyticsInput(
            cagr=invalid_cagr,
        )
    )

    assert result.failed_metric_count == len(
        result.failures
    )


def test_success_count_matches_successful_metric_utility(
    complete_input: AdvancedAnalyticsInput,
) -> None:
    """
    successful_metric_count should match discovered successful metrics.
    """

    result = calculate_advanced_analytics(
        complete_input
    )

    assert result.successful_metric_count == len(
        get_successful_metric_names(result)
    )


# ============================================================
# Status Consistency Tests
# ============================================================


def test_complete_status_requires_no_failures(
    complete_input: AdvancedAnalyticsInput,
) -> None:
    """
    Complete status should contain only successful requested metrics.
    """

    result = calculate_advanced_analytics(
        complete_input
    )

    assert result.status == "complete"
    assert result.successful_metric_count > 0
    assert result.failed_metric_count == 0


def test_partial_status_requires_success_and_failure(
    valid_cagr_input: DateBasedCAGRInput,
) -> None:
    """
    Partial status should contain at least one success and one failure.
    """

    result = calculate_advanced_analytics(
        AdvancedAnalyticsInput(
            cagr=valid_cagr_input,
            volatility=VolatilityInput(
                returns=(0.01,),
                periods_per_year=12,
            ),
        )
    )

    assert result.status == "partial"
    assert result.successful_metric_count > 0
    assert result.failed_metric_count > 0


def test_unavailable_status_has_no_successful_metrics() -> None:
    """
    Unavailable status should not contain successful metrics.
    """

    result = calculate_advanced_analytics(
        AdvancedAnalyticsInput()
    )

    assert result.status == "unavailable"
    assert result.successful_metric_count == 0


# ============================================================
# Dataclass Immutability Tests
# ============================================================


def test_advanced_analytics_input_is_immutable() -> None:
    """
    AdvancedAnalyticsInput should be immutable.
    """

    input_data = AdvancedAnalyticsInput()

    with pytest.raises(FrozenInstanceError):
        input_data.fail_fast = True  # type: ignore[misc]


def test_analytics_failure_is_immutable() -> None:
    """
    AnalyticsFailure should be immutable.
    """

    failure = AnalyticsFailure(
        metric="cagr",
        error_type="ValueError",
        message="Example",
    )

    with pytest.raises(FrozenInstanceError):
        failure.message = "Changed"  # type: ignore[misc]


def test_advanced_analytics_result_is_immutable(
    complete_input: AdvancedAnalyticsInput,
) -> None:
    """
    AdvancedAnalyticsResult should be immutable.
    """

    result = calculate_advanced_analytics(
        complete_input
    )

    with pytest.raises(FrozenInstanceError):
        result.status = "partial"  # type: ignore[misc]