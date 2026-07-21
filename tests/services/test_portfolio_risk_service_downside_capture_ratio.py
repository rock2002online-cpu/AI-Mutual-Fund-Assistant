"""Tests for PortfolioRiskService Downside Capture Ratio."""

import pytest

from services.portfolio_risk_service import PortfolioRiskService


def test_calculate_downside_capture_ratio() -> None:
    """Calculate capture during periods when the benchmark is negative."""

    service = PortfolioRiskService()

    result = service.calculate_downside_capture_ratio(
        portfolio_returns=[
            0.02,
            -0.03,
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

    portfolio_downside_return = (
        (0.97 * 0.98)
        ** (12 / 2)
        - 1.0
    )

    benchmark_downside_return = (
        (0.98 * 0.99)
        ** (12 / 2)
        - 1.0
    )

    assert result == pytest.approx(
        portfolio_downside_return
        / benchmark_downside_return
        * 100.0,
    )
def test_calculate_includes_downside_capture_ratio() -> None:
    """Include Downside Capture Ratio in aggregate risk metrics."""

    service = PortfolioRiskService()

    result = service.calculate(
        portfolio_returns=[
            0.02,
            -0.03,
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

    portfolio_downside_return = (
        (0.97 * 0.98)
        ** (12 / 2)
        - 1.0
    )

    benchmark_downside_return = (
        (0.98 * 0.99)
        ** (12 / 2)
        - 1.0
    )

    assert result.downside_capture_ratio == pytest.approx(
        portfolio_downside_return
        / benchmark_downside_return
        * 100.0,
    )
