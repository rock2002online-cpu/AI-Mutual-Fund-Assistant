"""Tests for rolling PortfolioRiskService calculations."""

import math

import pytest

from services.portfolio_risk_service import PortfolioRiskService


def test_calculate_rolling_risk_metrics() -> None:
    """Calculate one risk-metrics result for each rolling window."""

    service = PortfolioRiskService()

    results = service.calculate_rolling_risk_metrics(
        portfolio_returns=[
            0.01,
            0.02,
            0.03,
            0.04,
            0.05,
        ],
        window_size=3,
        periods_per_year=12,
    )

    assert len(results) == 3

    expected_first_volatility = (
        0.01
        * math.sqrt(12)
        * 100.0
    )

    assert results[0].volatility == pytest.approx(
        expected_first_volatility,
    )