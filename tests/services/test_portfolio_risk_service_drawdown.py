"""Tests for maximum drawdown calculation."""

from __future__ import annotations

import pytest

from services.portfolio_risk_service import PortfolioRiskService


def test_calculate_maximum_drawdown_returns_negative_value() -> None:
    """Maximum drawdown should be negative when losses occur."""

    service = PortfolioRiskService()

    returns = [
        0.10,
        -0.05,
        -0.10,
        0.08,
        -0.02,
    ]

    drawdown = service.calculate_maximum_drawdown(
        periodic_returns=returns,
    )

    assert isinstance(drawdown, float)
    assert drawdown < 0.0


def test_calculate_maximum_drawdown_empty_returns() -> None:
    """Empty returns should produce zero drawdown."""

    service = PortfolioRiskService()

    drawdown = service.calculate_maximum_drawdown(
        periodic_returns=[],
    )

    assert drawdown == 0.0


def test_calculate_maximum_drawdown_all_positive_returns() -> None:
    """A continuously rising portfolio should have no drawdown."""

    service = PortfolioRiskService()

    drawdown = service.calculate_maximum_drawdown(
        periodic_returns=[
            0.05,
            0.03,
            0.02,
        ],
    )

    assert drawdown == 0.0


def test_calculate_maximum_drawdown_single_loss() -> None:
    """A single loss should become the maximum drawdown."""

    service = PortfolioRiskService()

    drawdown = service.calculate_maximum_drawdown(
        periodic_returns=[
            -0.20,
        ],
    )

    assert drawdown == pytest.approx(
        -0.20,
    )


def test_calculate_maximum_drawdown_uses_compounded_values() -> None:
    """Drawdown should be calculated using compounded portfolio values."""

    service = PortfolioRiskService()

    drawdown = service.calculate_maximum_drawdown(
        periodic_returns=[
            0.10,
            -0.10,
            -0.10,
        ],
    )

    assert drawdown == pytest.approx(
        -0.19,
    )


def test_calculate_maximum_drawdown_recovers_after_loss() -> None:
    """A later recovery should not erase the historical drawdown."""

    service = PortfolioRiskService()

    drawdown = service.calculate_maximum_drawdown(
        periodic_returns=[
            0.20,
            -0.25,
            0.50,
        ],
    )

    assert drawdown == pytest.approx(
        -0.25,
    )


def test_calculate_populates_maximum_drawdown() -> None:
    """Aggregate risk calculation should populate maximum drawdown."""

    service = PortfolioRiskService()

    metrics = service.calculate(
        portfolio_returns=[
            0.10,
            -0.10,
            -0.10,
        ],
    )

    assert metrics.max_drawdown == pytest.approx(
        -0.19,
    )