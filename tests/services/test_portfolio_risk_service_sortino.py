
"""Tests for portfolio Sortino ratio calculation."""

from __future__ import annotations

import math

import pytest

from services.portfolio_risk_service import PortfolioRiskService


def test_calculate_sortino_ratio_positive_returns() -> None:
    """A healthy return stream should produce a positive Sortino ratio."""

    service = PortfolioRiskService()

    sortino = service.calculate_sortino_ratio(
        periodic_returns=[
            0.01,
            0.02,
            -0.01,
            0.03,
            -0.02,
        ],
    )

    assert isinstance(sortino, float)
    assert sortino > 0.0


def test_calculate_sortino_ratio_empty_returns() -> None:
    """Empty returns should produce zero Sortino ratio."""

    service = PortfolioRiskService()

    sortino = service.calculate_sortino_ratio(
        periodic_returns=[],
    )

    assert sortino == 0.0


def test_calculate_sortino_ratio_single_return() -> None:
    """A single return should produce zero Sortino ratio."""

    service = PortfolioRiskService()

    sortino = service.calculate_sortino_ratio(
        periodic_returns=[
            0.01,
        ],
    )

    assert sortino == 0.0


def test_calculate_sortino_ratio_no_downside_returns() -> None:
    """Returns without downside deviation should produce zero."""

    service = PortfolioRiskService()

    sortino = service.calculate_sortino_ratio(
        periodic_returns=[
            0.01,
            0.02,
            0.03,
        ],
    )

    assert sortino == 0.0


def test_calculate_sortino_ratio_negative_returns() -> None:
    """A poor return stream should produce a negative Sortino ratio."""

    service = PortfolioRiskService()

    sortino = service.calculate_sortino_ratio(
        periodic_returns=[
            -0.01,
            -0.02,
            0.005,
            -0.03,
        ],
    )

    assert sortino < 0.0


def test_calculate_sortino_ratio_custom_risk_free_rate() -> None:
    """A higher risk-free rate should reduce the Sortino ratio."""

    service = PortfolioRiskService()

    returns = [
        0.01,
        0.02,
        -0.01,
        0.03,
        -0.02,
    ]

    without_risk_free_rate = service.calculate_sortino_ratio(
        periodic_returns=returns,
        risk_free_rate=0.0,
    )

    with_risk_free_rate = service.calculate_sortino_ratio(
        periodic_returns=returns,
        risk_free_rate=0.10,
    )

    assert (
        with_risk_free_rate
        < without_risk_free_rate
    )


def test_calculate_sortino_ratio_custom_periods_per_year() -> None:
    """The annualization period should affect the Sortino ratio."""

    service = PortfolioRiskService()

    returns = [
        0.01,
        0.02,
        -0.01,
        0.03,
        -0.02,
    ]

    daily_sortino = service.calculate_sortino_ratio(
        periodic_returns=returns,
        periods_per_year=252,
    )

    monthly_sortino = service.calculate_sortino_ratio(
        periodic_returns=returns,
        periods_per_year=12,
    )

    assert daily_sortino != pytest.approx(
        monthly_sortino,
    )


def test_calculate_sortino_ratio_converts_values_to_float() -> None:
    """Numeric string values should be converted to floats."""

    service = PortfolioRiskService()

    sortino = service.calculate_sortino_ratio(
        periodic_returns=[
            "0.01",
            "0.02",
            "-0.01",
            "0.03",
            "-0.02",
        ],
    )

    assert isinstance(sortino, float)
    assert math.isfinite(sortino)


def test_calculate_sortino_ratio_rejects_invalid_periods() -> None:
    """Periods per year must be greater than zero."""

    service = PortfolioRiskService()

    with pytest.raises(
        ValueError,
        match="periods_per_year must be greater than zero",
    ):
        service.calculate_sortino_ratio(
            periodic_returns=[
                0.01,
                -0.01,
            ],
            periods_per_year=0,
        )


def test_calculate_populates_sortino_ratio() -> None:
    """Aggregate calculation should populate the Sortino ratio."""

    service = PortfolioRiskService()

    metrics = service.calculate(
        portfolio_returns=[
            0.01,
            0.02,
            -0.01,
            0.03,
            -0.02,
        ],
    )

    assert metrics.sortino_ratio > 0.0
    assert math.isfinite(
        metrics.sortino_ratio,
    )
