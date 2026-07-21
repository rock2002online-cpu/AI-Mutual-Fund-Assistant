
"""Tests for portfolio beta calculation."""

from __future__ import annotations

import pytest

from services.portfolio_risk_service import PortfolioRiskService


def test_calculate_beta_equal_market_returns() -> None:
    """A portfolio identical to its benchmark should have beta one."""

    service = PortfolioRiskService()

    portfolio_returns = [
        0.01,
        0.02,
        -0.01,
        0.03,
        -0.02,
    ]

    benchmark_returns = [
        0.01,
        0.02,
        -0.01,
        0.03,
        -0.02,
    ]

    beta = service.calculate_beta(
        portfolio_returns=portfolio_returns,
        benchmark_returns=benchmark_returns,
    )

    assert beta == pytest.approx(1.0)


def test_calculate_beta_empty_returns() -> None:
    """Empty return series should produce zero beta."""

    service = PortfolioRiskService()

    beta = service.calculate_beta(
        portfolio_returns=[],
        benchmark_returns=[],
    )

    assert beta == 0.0


def test_calculate_beta_single_observation() -> None:
    """A single observation cannot produce beta."""

    service = PortfolioRiskService()

    beta = service.calculate_beta(
        portfolio_returns=[
            0.01,
        ],
        benchmark_returns=[
            0.02,
        ],
    )

    assert beta == 0.0


def test_calculate_beta_zero_benchmark_variance() -> None:
    """Constant benchmark returns should produce zero beta."""

    service = PortfolioRiskService()

    beta = service.calculate_beta(
        portfolio_returns=[
            0.01,
            0.02,
            0.03,
        ],
        benchmark_returns=[
            0.01,
            0.01,
            0.01,
        ],
    )

    assert beta == 0.0


def test_calculate_beta_rejects_unequal_lengths() -> None:
    """Portfolio and benchmark return series must have equal lengths."""

    service = PortfolioRiskService()

    with pytest.raises(
        ValueError,
        match="must have the same length",
    ):
        service.calculate_beta(
            portfolio_returns=[
                0.01,
                0.02,
            ],
            benchmark_returns=[
                0.01,
            ],
        )


def test_calculate_beta_double_market_sensitivity() -> None:
    """A portfolio moving twice as much as the benchmark has beta two."""

    service = PortfolioRiskService()

    benchmark_returns = [
        0.01,
        0.02,
        -0.01,
        0.03,
        -0.02,
    ]

    portfolio_returns = [
        benchmark_return * 2.0
        for benchmark_return in benchmark_returns
    ]

    beta = service.calculate_beta(
        portfolio_returns=portfolio_returns,
        benchmark_returns=benchmark_returns,
    )

    assert beta == pytest.approx(2.0)


def test_calculate_beta_inverse_market_sensitivity() -> None:
    """An inversely moving portfolio should have negative beta."""

    service = PortfolioRiskService()

    benchmark_returns = [
        0.01,
        0.02,
        -0.01,
        0.03,
        -0.02,
    ]

    portfolio_returns = [
        -benchmark_return
        for benchmark_return in benchmark_returns
    ]

    beta = service.calculate_beta(
        portfolio_returns=portfolio_returns,
        benchmark_returns=benchmark_returns,
    )

    assert beta == pytest.approx(-1.0)


def test_calculate_beta_converts_values_to_float() -> None:
    """Numeric string values should be converted to floats."""

    service = PortfolioRiskService()

    beta = service.calculate_beta(
        portfolio_returns=[
            "0.01",
            "0.02",
            "-0.01",
        ],
        benchmark_returns=[
            "0.01",
            "0.02",
            "-0.01",
        ],
    )

    assert beta == pytest.approx(1.0)


def test_calculate_populates_beta() -> None:
    """Aggregate risk calculation should populate portfolio beta."""

    service = PortfolioRiskService()

    benchmark_returns = [
        0.01,
        0.02,
        -0.01,
        0.03,
        -0.02,
    ]

    portfolio_returns = [
        benchmark_return * 2.0
        for benchmark_return in benchmark_returns
    ]

    metrics = service.calculate(
        portfolio_returns=portfolio_returns,
        benchmark_returns=benchmark_returns,
    )

    assert metrics.beta == pytest.approx(2.0)


def test_calculate_defaults_beta_to_zero_without_benchmark() -> None:
    """Beta should remain zero when no benchmark is supplied."""

    service = PortfolioRiskService()

    metrics = service.calculate(
        portfolio_returns=[
            0.01,
            0.02,
            -0.01,
        ],
    )

    assert metrics.beta == 0.0
