"""Tests for PortfolioRiskService Upside Capture Ratio."""

import pytest

from services.portfolio_risk_service import PortfolioRiskService


def test_calculate_upside_capture_ratio() -> None:
    """Calculate capture during periods when the benchmark is positive."""

    service = PortfolioRiskService()

    result = service.calculate_upside_capture_ratio(
        portfolio_returns=[
            0.02,
            -0.01,
            0.04,
            -0.02,
        ],
        benchmark_returns=[
            0.01,
            -0.02,
            0.02,
            -0.01,
        ],
        periods_per_year=12,
    )

    portfolio_upside_return = (
        (1.02 * 1.04)
        ** (12 / 2)
        - 1.0
    )

    benchmark_upside_return = (
        (1.01 * 1.02)
        ** (12 / 2)
        - 1.0
    )

    assert result == pytest.approx(
        portfolio_upside_return
        / benchmark_upside_return
        * 100.0,
    )

def test_calculate_includes_upside_capture_ratio() -> None:
    """Include Upside Capture Ratio in aggregate risk metrics."""

    service = PortfolioRiskService()

    result = service.calculate(
        portfolio_returns=[
            0.02,
            -0.01,
            0.04,
            -0.02,
        ],
        benchmark_returns=[
            0.01,
            -0.02,
            0.02,
            -0.01,
        ],
        periods_per_year=12,
    )

    portfolio_upside_return = (
        (1.02 * 1.04)
        ** (12 / 2)
        - 1.0
    )

    benchmark_upside_return = (
        (1.01 * 1.02)
        ** (12 / 2)
        - 1.0
    )

    assert result.upside_capture_ratio == pytest.approx(
        portfolio_upside_return
        / benchmark_upside_return
        * 100.0,
    )