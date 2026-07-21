from math import sqrt
from statistics import stdev

import pytest

from services.portfolio_risk_service import PortfolioRiskService


def test_empty_returns_produce_zero_volatility() -> None:
    service = PortfolioRiskService()

    metrics = service.calculate(
        portfolio_returns=[],
    )

    assert metrics.volatility == 0.0


def test_single_return_produces_zero_volatility() -> None:
    service = PortfolioRiskService()

    metrics = service.calculate(
        portfolio_returns=[0.01],
    )

    assert metrics.volatility == 0.0


def test_daily_returns_produce_annualized_volatility() -> None:
    returns = [
        0.01,
        -0.01,
        0.02,
        -0.02,
    ]

    service = PortfolioRiskService()

    metrics = service.calculate(
        portfolio_returns=returns,
    )

    expected = (
        stdev(returns)
        * sqrt(252)
        * 100.0
    )

    assert metrics.volatility == pytest.approx(
        expected
    )


def test_input_values_are_converted_to_float() -> None:
    service = PortfolioRiskService()

    metrics = service.calculate(
        portfolio_returns=[
            1,
            -1,
            2,
        ],
    )

    expected = (
        stdev([1.0, -1.0, 2.0])
        * sqrt(252)
        * 100.0
    )

    assert metrics.volatility == pytest.approx(
        expected
    )


def test_unimplemented_metrics_default_to_zero() -> None:
    service = PortfolioRiskService()

    metrics = service.calculate(
        portfolio_returns=[
            0.01,
            0.02,
        ],
    )

    assert metrics.sharpe_ratio != 0.0
    assert metrics.max_drawdown == 0.0
    assert metrics.beta == 0.0

def test_calculate_returns_sharpe_ratio() -> None:
    """Risk metrics should expose Sharpe ratio as a float."""

    service = PortfolioRiskService()

    metrics = service.calculate(
        portfolio_returns=[
            0.01,
            0.02,
            -0.005,
            0.015,
            0.01,
        ],
    )

    assert isinstance(
        metrics.sharpe_ratio,
        float,
    )

def test_calculate_populates_sharpe_ratio() -> None:
    """Calculate should populate Sharpe ratio from portfolio returns."""

    service = PortfolioRiskService()

    metrics = service.calculate(
        portfolio_returns=[
            0.01,
            0.02,
            -0.005,
            0.015,
            0.01,
        ],
    )

    assert metrics.sharpe_ratio != 0.0