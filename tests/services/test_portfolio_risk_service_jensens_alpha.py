"""Tests for PortfolioRiskService Jensen's Alpha calculation."""

import pytest

from services.portfolio_risk_service import PortfolioRiskService


def test_calculate_jensens_alpha() -> None:
    """Calculate annualized Jensen's Alpha relative to a benchmark."""

    service = PortfolioRiskService()

    result = service.calculate_jensens_alpha(
        portfolio_returns=[
            0.020,
            0.030,
            0.010,
            0.040,
        ],
        benchmark_returns=[
            0.010,
            0.020,
            0.005,
            0.025,
        ],
        risk_free_rate=0.02,
        periods_per_year=12,
    )

    assert result == pytest.approx(
        0.056,
    )

def test_calculate_includes_jensens_alpha() -> None:
    """Include Jensen's Alpha in aggregate portfolio risk metrics."""

    service = PortfolioRiskService()

    result = service.calculate(
        portfolio_returns=[
            0.020,
            0.030,
            0.010,
            0.040,
        ],
        benchmark_returns=[
            0.010,
            0.020,
            0.005,
            0.025,
        ],
        risk_free_rate=0.02,
        periods_per_year=12,
    )

    assert result.jensens_alpha == pytest.approx(
        0.056,
    )