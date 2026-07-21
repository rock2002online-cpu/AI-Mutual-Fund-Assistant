"""Tests for PortfolioRiskService Omega Ratio calculation."""

import pytest

from services.portfolio_risk_service import PortfolioRiskService


def test_calculate_omega_ratio() -> None:
    """Calculate gains relative to losses above a zero threshold."""

    service = PortfolioRiskService()

    result = service.calculate_omega_ratio(
        periodic_returns=[
            0.02,
            -0.01,
            0.03,
            -0.02,
        ],
        threshold_return=0.0,
    )

    expected_gain = (
        0.02
        + 0.03
    )

    expected_loss = (
        0.01
        + 0.02
    )

    assert result == pytest.approx(
        expected_gain / expected_loss,
    )

def test_calculate_includes_omega_ratio() -> None:
    """Include Omega Ratio in aggregate portfolio risk metrics."""

    service = PortfolioRiskService()

    result = service.calculate(
        portfolio_returns=[
            0.02,
            -0.01,
            0.03,
            -0.02,
        ],
    )

    assert result.omega_ratio == pytest.approx(
        0.05 / 0.03,
    )