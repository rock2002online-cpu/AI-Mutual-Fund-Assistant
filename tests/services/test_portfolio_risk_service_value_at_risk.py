"""Tests for PortfolioRiskService historical Value at Risk."""

import pytest

from services.portfolio_risk_service import PortfolioRiskService


def test_calculate_value_at_risk() -> None:
    """Calculate historical VaR as a positive loss value."""

    service = PortfolioRiskService()

    result = service.calculate_value_at_risk(
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
        0.05,
    )

def test_calculate_includes_value_at_risk() -> None:
    """Include historical VaR in aggregate portfolio risk metrics."""

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

    assert result.value_at_risk == pytest.approx(
        0.10,
    )