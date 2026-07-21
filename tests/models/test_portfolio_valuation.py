"""Tests for PortfolioValuation."""

from dataclasses import FrozenInstanceError

import pytest

from models.portfolio_valuation import PortfolioValuation


def make_valuation() -> PortfolioValuation:
    return PortfolioValuation(
        portfolio_id=1,
        invested_amount=10000.0,
        current_value=12500.0,
        unrealized_gain=2500.0,
        unrealized_return_pct=25.0,
        number_of_positions=4,
    )


def test_portfolio_valuation_stores_fields() -> None:
    valuation = make_valuation()

    assert valuation.portfolio_id == 1
    assert valuation.invested_amount == pytest.approx(10000.0)
    assert valuation.current_value == pytest.approx(12500.0)
    assert valuation.unrealized_gain == pytest.approx(2500.0)
    assert valuation.unrealized_return_pct == pytest.approx(25.0)
    assert valuation.number_of_positions == 4


def test_portfolio_valuation_is_immutable() -> None:
    valuation = make_valuation()

    with pytest.raises(FrozenInstanceError):
        valuation.current_value = 1.0  # type: ignore[misc]


def test_equal_instances_compare_equal() -> None:
    assert make_valuation() == make_valuation()


def test_portfolio_valuation_supports_hashing() -> None:
    valuation = make_valuation()

    assert valuation in {valuation}


def test_portfolio_valuation_uses_slots() -> None:
    valuation = make_valuation()

    assert not hasattr(valuation, "__dict__")