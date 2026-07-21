
"""Tests for portfolio Information Ratio and tracking error."""

from __future__ import annotations

import math

import pytest

from services.portfolio_risk_service import PortfolioRiskService


def test_calculate_information_ratio_positive() -> None:
    """Outperformance with non-zero tracking error should be positive."""

    service = PortfolioRiskService()

    information_ratio = service.calculate_information_ratio(
        portfolio_returns=[
            0.012,
            0.018,
            -0.005,
            0.025,
            0.010,
        ],
        benchmark_returns=[
            0.010,
            0.015,
            -0.008,
            0.020,
            0.008,
        ],
    )

    assert isinstance(information_ratio, float)
    assert information_ratio > 0.0


def test_calculate_information_ratio_empty_returns() -> None:
    """Empty return series should produce zero."""

    service = PortfolioRiskService()

    information_ratio = service.calculate_information_ratio(
        portfolio_returns=[],
        benchmark_returns=[],
    )

    assert information_ratio == 0.0


def test_calculate_information_ratio_single_observation() -> None:
    """A single observation should produce zero."""

    service = PortfolioRiskService()

    information_ratio = service.calculate_information_ratio(
        portfolio_returns=[
            0.01,
        ],
        benchmark_returns=[
            0.008,
        ],
    )

    assert information_ratio == 0.0


def test_calculate_information_ratio_zero_tracking_error() -> None:
    """Constant active returns should produce zero."""

    service = PortfolioRiskService()

    information_ratio = service.calculate_information_ratio(
        portfolio_returns=[
            0.02,
            0.03,
            0.01,
        ],
        benchmark_returns=[
            0.01,
            0.02,
            0.00,
        ],
    )

    assert information_ratio == 0.0


def test_calculate_information_ratio_negative() -> None:
    """Underperformance should produce a negative ratio."""

    service = PortfolioRiskService()

    information_ratio = service.calculate_information_ratio(
        portfolio_returns=[
            0.008,
            0.010,
            -0.012,
            0.015,
            0.003,
        ],
        benchmark_returns=[
            0.010,
            0.015,
            -0.008,
            0.020,
            0.008,
        ],
    )

    assert information_ratio < 0.0


def test_calculate_information_ratio_custom_periods_per_year() -> None:
    """Changing the annualization period should change the ratio."""

    service = PortfolioRiskService()

    portfolio_returns = [
        0.012,
        0.018,
        -0.005,
        0.025,
        0.010,
    ]

    benchmark_returns = [
        0.010,
        0.015,
        -0.008,
        0.020,
        0.008,
    ]

    daily_ratio = service.calculate_information_ratio(
        portfolio_returns=portfolio_returns,
        benchmark_returns=benchmark_returns,
        periods_per_year=252,
    )

    monthly_ratio = service.calculate_information_ratio(
        portfolio_returns=portfolio_returns,
        benchmark_returns=benchmark_returns,
        periods_per_year=12,
    )

    assert daily_ratio != pytest.approx(
        monthly_ratio,
    )


def test_calculate_information_ratio_accepts_numeric_strings() -> None:
    """Numeric strings should be converted to floats."""

    service = PortfolioRiskService()

    information_ratio = service.calculate_information_ratio(
        portfolio_returns=[
            "0.012",
            "0.018",
            "-0.005",
            "0.025",
            "0.010",
        ],
        benchmark_returns=[
            "0.010",
            "0.015",
            "-0.008",
            "0.020",
            "0.008",
        ],
    )

    assert isinstance(information_ratio, float)
    assert math.isfinite(information_ratio)


def test_calculate_information_ratio_rejects_unequal_lengths() -> None:
    """Portfolio and benchmark returns must have equal lengths."""

    service = PortfolioRiskService()

    with pytest.raises(
        ValueError,
        match=(
            "portfolio_returns and benchmark_returns "
            "must have the same length"
        ),
    ):
        service.calculate_information_ratio(
            portfolio_returns=[
                0.01,
                0.02,
            ],
            benchmark_returns=[
                0.01,
            ],
        )


def test_calculate_information_ratio_rejects_invalid_periods() -> None:
    """Periods per year must be greater than zero."""

    service = PortfolioRiskService()

    with pytest.raises(
        ValueError,
        match="periods_per_year must be greater than zero",
    ):
        service.calculate_information_ratio(
            portfolio_returns=[
                0.01,
                0.02,
            ],
            benchmark_returns=[
                0.008,
                0.015,
            ],
            periods_per_year=0,
        )


def test_calculate_tracking_error_positive() -> None:
    """Varying active returns should produce positive tracking error."""

    service = PortfolioRiskService()

    tracking_error = service.calculate_tracking_error(
        portfolio_returns=[
            0.012,
            0.018,
            -0.005,
            0.025,
            0.010,
        ],
        benchmark_returns=[
            0.010,
            0.015,
            -0.008,
            0.020,
            0.008,
        ],
    )

    assert isinstance(tracking_error, float)
    assert tracking_error > 0.0


def test_calculate_tracking_error_empty_returns() -> None:
    """Empty return series should produce zero tracking error."""

    service = PortfolioRiskService()

    tracking_error = service.calculate_tracking_error(
        portfolio_returns=[],
        benchmark_returns=[],
    )

    assert tracking_error == 0.0


def test_calculate_tracking_error_single_observation() -> None:
    """A single observation should produce zero tracking error."""

    service = PortfolioRiskService()

    tracking_error = service.calculate_tracking_error(
        portfolio_returns=[
            0.01,
        ],
        benchmark_returns=[
            0.008,
        ],
    )

    assert tracking_error == 0.0


def test_calculate_tracking_error_zero_for_constant_active_returns() -> None:
    """Constant active returns should have zero tracking error."""

    service = PortfolioRiskService()

    tracking_error = service.calculate_tracking_error(
        portfolio_returns=[
            0.02,
            0.03,
            0.01,
        ],
        benchmark_returns=[
            0.01,
            0.02,
            0.00,
        ],
    )

    assert tracking_error == pytest.approx(
        0.0,
    )


def test_calculate_tracking_error_accepts_numeric_strings() -> None:
    """Tracking error should accept numeric strings."""

    service = PortfolioRiskService()

    tracking_error = service.calculate_tracking_error(
        portfolio_returns=[
            "0.012",
            "0.018",
            "-0.005",
        ],
        benchmark_returns=[
            "0.010",
            "0.015",
            "-0.008",
        ],
    )

    assert isinstance(tracking_error, float)
    assert math.isfinite(tracking_error)


def test_calculate_tracking_error_rejects_unequal_lengths() -> None:
    """Tracking Error requires return series of equal length."""

    service = PortfolioRiskService()

    with pytest.raises(
        ValueError,
        match=(
            "portfolio_returns and benchmark_returns "
            "must have the same length"
        ),
    ):
        service.calculate_tracking_error(
            portfolio_returns=[
                0.01,
                0.02,
            ],
            benchmark_returns=[
                0.01,
            ],
        )


def test_calculate_tracking_error_rejects_invalid_periods() -> None:
    """Tracking Error should reject invalid annualization periods."""

    service = PortfolioRiskService()

    with pytest.raises(
        ValueError,
        match="periods_per_year must be greater than zero",
    ):
        service.calculate_tracking_error(
            portfolio_returns=[
                0.01,
                0.02,
            ],
            benchmark_returns=[
                0.008,
                0.015,
            ],
            periods_per_year=0,
        )
