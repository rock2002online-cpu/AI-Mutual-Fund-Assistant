"""Tests for PortfolioRiskService Calmar Ratio calculation."""

import pytest

from services.portfolio_risk_service import PortfolioRiskService


def test_calculate_calmar_ratio() -> None:
    """Calculate Calmar Ratio using annualized return and drawdown."""

    service = PortfolioRiskService()

    result = service.calculate_calmar_ratio(
        periodic_returns=[
            0.10,
            -0.20,
            0.05,
            0.15,
        ],
        periods_per_year=4,
    )

    expected_annualized_return = (
        (1.10 * 0.80 * 1.05 * 1.15)
        ** (4 / 4)
        - 1.0
    )

    expected_maximum_drawdown = 0.20

    assert result == pytest.approx(
        expected_annualized_return
        / expected_maximum_drawdown,
    )

def test_calculate_includes_calmar_ratio() -> None:
    """Include Calmar Ratio in aggregate portfolio risk metrics."""

    service = PortfolioRiskService()

    result = service.calculate(
        portfolio_returns=[
            0.10,
            -0.20,
            0.05,
            0.15,
        ],
        periods_per_year=4,
    )

    expected_annualized_return = (
        (1.10 * 0.80 * 1.05 * 1.15)
        ** (4 / 4)
        - 1.0
    )

    assert result.calmar_ratio == pytest.approx(
        expected_annualized_return / 0.20,
    )