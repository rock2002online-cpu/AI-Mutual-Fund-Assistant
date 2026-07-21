"""Tests for PortfolioAnalytics."""

from dataclasses import FrozenInstanceError

import pytest

from models.portfolio_analytics import PortfolioAnalytics


def test_portfolio_analytics_stores_values() -> None:
    analytics = PortfolioAnalytics(
        portfolio_id=1,
        invested_amount=100000.0,
        current_value=125000.0,
        unrealized_gain=25000.0,
        unrealized_return_pct=25.0,
        number_of_positions=8,
        diversification_score=82.5,
        concentration_score=21.3,
    )

    assert analytics.portfolio_id == 1
    assert analytics.invested_amount == 100000.0
    assert analytics.current_value == 125000.0
    assert analytics.unrealized_gain == 25000.0
    assert analytics.unrealized_return_pct == 25.0
    assert analytics.number_of_positions == 8
    assert analytics.diversification_score == 82.5
    assert analytics.concentration_score == 21.3


def test_portfolio_analytics_is_frozen() -> None:
    analytics = PortfolioAnalytics(
        portfolio_id=1,
        invested_amount=0.0,
        current_value=0.0,
        unrealized_gain=0.0,
        unrealized_return_pct=0.0,
        number_of_positions=0,
        diversification_score=0.0,
        concentration_score=0.0,
    )

    with pytest.raises(FrozenInstanceError):
        analytics.current_value = 10.0


def test_portfolio_analytics_uses_slots() -> None:
    analytics = PortfolioAnalytics(
        portfolio_id=1,
        invested_amount=0.0,
        current_value=0.0,
        unrealized_gain=0.0,
        unrealized_return_pct=0.0,
        number_of_positions=0,
        diversification_score=0.0,
        concentration_score=0.0,
    )

    assert not hasattr(analytics, "__dict__")