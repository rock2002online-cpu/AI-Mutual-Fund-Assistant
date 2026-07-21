"""Tests for historical Conditional Value at Risk."""

import pytest

from services.portfolio_risk_service import PortfolioRiskService


def test_calculate_conditional_value_at_risk() -> None:
    """Calculate CVaR as the average loss in the historical tail."""

    service = PortfolioRiskService()

    result = service.calculate_conditional_value_at_risk(
        periodic_returns=[
            -0.10,
            -0.05,
            -0.02,
            -0.01,
            0.00,
            0.01,
            0.02,
            0.03,
            0.04,
            0.05,
        ],
        confidence_level=0.80,
    )

    assert result == pytest.approx(
        0.075,
    )

def test_calculate_includes_conditional_value_at_risk() -> None:
    """Include historical CVaR in aggregate portfolio risk metrics."""

    service = PortfolioRiskService()

    result = service.calculate(
        portfolio_returns=[
            -0.10,
            -0.05,
            -0.02,
            -0.01,
            0.00,
            0.01,
            0.02,
            0.03,
            0.04,
            0.05,
        ],
    )

    assert result.conditional_value_at_risk == pytest.approx(
        0.10,
    )