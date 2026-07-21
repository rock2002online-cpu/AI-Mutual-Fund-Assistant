
"""Tests for portfolio Treynor ratio calculation."""

from __future__ import annotations

import math

import pytest

from services.portfolio_risk_service import PortfolioRiskService


def test_calculate_treynor_ratio_positive() -> None:
    """Positive excess return with positive beta should be positive."""

    service = PortfolioRiskService()

    treynor = service.calculate_treynor_ratio(
        portfolio_returns=[
            0.01,
            0.02,
            -0.01,
            0.03,
            -0.02,
        ],
        benchmark_returns=[
            0.008,
            0.015,
            -0.008,
            0.025,
            -0.015,
        ],
    )

    assert isinstance(treynor, float)
    assert treynor > 0.0


def test_calculate_treynor_ratio_empty_returns() -> None:
    """Empty return series should produce zero."""

    service = PortfolioRiskService()

    treynor = service.calculate_treynor_ratio(
        portfolio_returns=[],
        benchmark_returns=[],
    )

    assert treynor == 0.0


def test_calculate_treynor_ratio_single_observation() -> None:
    """A single observation should produce zero."""

    service = PortfolioRiskService()

    treynor = service.calculate_treynor_ratio(
        portfolio_returns=[
            0.01,
        ],
        benchmark_returns=[
            0.008,
        ],
    )

    assert treynor == 0.0


def test_calculate_treynor_ratio_zero_beta() -> None:
    """Zero benchmark variance should produce zero Treynor ratio."""

    service = PortfolioRiskService()

    treynor = service.calculate_treynor_ratio(
        portfolio_returns=[
            0.01,
            0.02,
            0.03,
        ],
        benchmark_returns=[
            0.01,
            0.01,
            0.01,
        ],
    )

    assert treynor == 0.0


def test_calculate_treynor_ratio_negative_beta() -> None:
    """Positive excess return with negative beta should be negative."""

    service = PortfolioRiskService()

    treynor = service.calculate_treynor_ratio(
        portfolio_returns=[
            0.04,
            0.02,
            0.00,
            -0.02,
        ],
        benchmark_returns=[
            -0.03,
            -0.01,
            0.01,
            0.03,
        ],
    )

    assert treynor < 0.0


def test_calculate_treynor_ratio_custom_risk_free_rate() -> None:
    """A higher risk-free rate should reduce the ratio."""

    service = PortfolioRiskService()

    portfolio_returns = [
        0.01,
        0.02,
        -0.01,
        0.03,
        -0.02,
    ]

    benchmark_returns = [
        0.008,
        0.015,
        -0.008,
        0.025,
        -0.015,
    ]

    without_risk_free_rate = service.calculate_treynor_ratio(
        portfolio_returns=portfolio_returns,
        benchmark_returns=benchmark_returns,
        risk_free_rate=0.0,
    )

    with_risk_free_rate = service.calculate_treynor_ratio(
        portfolio_returns=portfolio_returns,
        benchmark_returns=benchmark_returns,
        risk_free_rate=0.10,
    )

    assert (
        with_risk_free_rate
        < without_risk_free_rate
    )


def test_calculate_treynor_ratio_custom_periods_per_year() -> None:
    """The annualization period should affect the result."""

    service = PortfolioRiskService()

    portfolio_returns = [
        0.01,
        0.02,
        -0.01,
        0.03,
        -0.02,
    ]

    benchmark_returns = [
        0.008,
        0.015,
        -0.008,
        0.025,
        -0.015,
    ]

    daily_treynor = service.calculate_treynor_ratio(
        portfolio_returns=portfolio_returns,
        benchmark_returns=benchmark_returns,
        periods_per_year=252,
    )

    monthly_treynor = service.calculate_treynor_ratio(
        portfolio_returns=portfolio_returns,
        benchmark_returns=benchmark_returns,
        periods_per_year=12,
    )

    assert daily_treynor != pytest.approx(
        monthly_treynor,
    )


def test_calculate_treynor_ratio_accepts_numeric_strings() -> None:
    """Numeric strings should be normalized to floats."""

    service = PortfolioRiskService()

    treynor = service.calculate_treynor_ratio(
        portfolio_returns=[
            "0.01",
            "0.02",
            "-0.01",
            "0.03",
            "-0.02",
        ],
        benchmark_returns=[
            "0.008",
            "0.015",
            "-0.008",
            "0.025",
            "-0.015",
        ],
    )

    assert isinstance(treynor, float)
    assert math.isfinite(treynor)


def test_calculate_treynor_ratio_rejects_unequal_lengths() -> None:
    """Portfolio and benchmark series must have equal lengths."""

    service = PortfolioRiskService()

    with pytest.raises(
        ValueError,
        match=(
            "portfolio_returns and benchmark_returns "
            "must have the same length"
        ),
    ):
        service.calculate_treynor_ratio(
            portfolio_returns=[
                0.01,
                0.02,
            ],
            benchmark_returns=[
                0.01,
            ],
        )


def test_calculate_treynor_ratio_rejects_invalid_periods() -> None:
    """Periods per year must be greater than zero."""

    service = PortfolioRiskService()

    with pytest.raises(
        ValueError,
        match="periods_per_year must be greater than zero",
    ):
        service.calculate_treynor_ratio(
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


def test_calculate_populates_treynor_ratio() -> None:
    """Aggregate calculation should populate the Treynor ratio."""

    service = PortfolioRiskService()

    metrics = service.calculate(
        portfolio_returns=[
            0.01,
            0.02,
            -0.01,
            0.03,
            -0.02,
        ],
        benchmark_returns=[
            0.008,
            0.015,
            -0.008,
            0.025,
            -0.015,
        ],
    )

    assert metrics.treynor_ratio > 0.0
    assert math.isfinite(
        metrics.treynor_ratio,
    )


def test_calculate_defaults_treynor_ratio_without_benchmark() -> None:
    """Aggregate calculation should default Treynor ratio to zero."""

    service = PortfolioRiskService()

    metrics = service.calculate(
        portfolio_returns=[
            0.01,
            0.02,
            -0.01,
        ],
    )

    assert metrics.treynor_ratio == 0.0
