"""Tests for ValuationService."""

from __future__ import annotations

import pytest

from models.position import Position
from services.valuation_service import ValuationService


class FakePositionService:
    """Test double for PositionService."""

    def __init__(
        self,
        positions: list[Position] | None = None,
    ) -> None:
        self.positions = positions or []
        self.requested_portfolio_ids: list[int] = []

    def get_positions(
        self,
        *,
        portfolio_id: int,
    ) -> list[Position]:
        self.requested_portfolio_ids.append(
            portfolio_id
        )
        return self.positions


def make_position(
    *,
    portfolio_id: int = 1,
    fund_id: int = 1,
    fund_name: str = "Test Fund",
    invested_amount: float = 1000.0,
    current_value: float = 1200.0,
) -> Position:
    """Create a valid Position for valuation tests."""

    unrealized_gain = (
        current_value - invested_amount
    )

    unrealized_return_pct = (
        unrealized_gain / invested_amount * 100.0
        if invested_amount > 0
        else 0.0
    )

    return Position(
        portfolio_id=portfolio_id,
        fund_id=fund_id,
        fund_name=fund_name,
        units=10.0,
        average_nav=invested_amount / 10.0,
        invested_amount=invested_amount,
        latest_nav=current_value / 10.0,
        current_value=current_value,
        unrealized_gain=unrealized_gain,
        unrealized_return_pct=unrealized_return_pct,
    )


def test_get_portfolio_valuation_returns_zero_for_empty_portfolio() -> None:
    """An empty portfolio should produce a zero valuation."""

    position_service = FakePositionService()

    service = ValuationService(
        position_service=position_service
    )

    valuation = service.get_portfolio_valuation(
        portfolio_id=1
    )

    assert valuation.portfolio_id == 1
    assert valuation.invested_amount == pytest.approx(0.0)
    assert valuation.current_value == pytest.approx(0.0)
    assert valuation.unrealized_gain == pytest.approx(0.0)
    assert valuation.unrealized_return_pct == pytest.approx(0.0)
    assert valuation.number_of_positions == 0


def test_get_portfolio_valuation_aggregates_single_position() -> None:
    """A single position should be reflected directly."""

    position_service = FakePositionService(
        [
            make_position(
                invested_amount=1000.0,
                current_value=1250.0,
            )
        ]
    )

    service = ValuationService(
        position_service=position_service
    )

    valuation = service.get_portfolio_valuation(
        portfolio_id=1
    )

    assert valuation.invested_amount == pytest.approx(1000.0)
    assert valuation.current_value == pytest.approx(1250.0)
    assert valuation.unrealized_gain == pytest.approx(250.0)
    assert valuation.unrealized_return_pct == pytest.approx(25.0)
    assert valuation.number_of_positions == 1


def test_get_portfolio_valuation_aggregates_multiple_positions() -> None:
    """All positions should be summed into one valuation."""

    position_service = FakePositionService(
        [
            make_position(
                fund_id=1,
                fund_name="Alpha",
                invested_amount=1000.0,
                current_value=1200.0,
            ),
            make_position(
                fund_id=2,
                fund_name="Bravo",
                invested_amount=2000.0,
                current_value=2500.0,
            ),
            make_position(
                fund_id=3,
                fund_name="Charlie",
                invested_amount=500.0,
                current_value=400.0,
            ),
        ]
    )

    service = ValuationService(
        position_service=position_service
    )

    valuation = service.get_portfolio_valuation(
        portfolio_id=1
    )

    assert valuation.invested_amount == pytest.approx(3500.0)
    assert valuation.current_value == pytest.approx(4100.0)
    assert valuation.unrealized_gain == pytest.approx(600.0)

    assert valuation.unrealized_return_pct == pytest.approx(
        (600.0 / 3500.0) * 100.0
    )

    assert valuation.number_of_positions == 3


def test_get_portfolio_valuation_uses_aggregate_return_not_average_return() -> None:
    """
    Portfolio return must be calculated from aggregate totals.

    It must not be the arithmetic average of each position's return.
    """

    position_service = FakePositionService(
        [
            make_position(
                fund_id=1,
                invested_amount=100.0,
                current_value=200.0,
            ),
            make_position(
                fund_id=2,
                invested_amount=900.0,
                current_value=900.0,
            ),
        ]
    )

    service = ValuationService(
        position_service=position_service
    )

    valuation = service.get_portfolio_valuation(
        portfolio_id=1
    )

    assert valuation.unrealized_gain == pytest.approx(100.0)
    assert valuation.unrealized_return_pct == pytest.approx(10.0)


def test_get_portfolio_valuation_handles_zero_total_investment() -> None:
    """Zero investment should not cause division by zero."""

    position_service = FakePositionService(
        [
            make_position(
                invested_amount=0.0,
                current_value=0.0,
            )
        ]
    )

    service = ValuationService(
        position_service=position_service
    )

    valuation = service.get_portfolio_valuation(
        portfolio_id=1
    )

    assert valuation.unrealized_return_pct == pytest.approx(0.0)


def test_get_portfolio_valuation_requests_correct_portfolio() -> None:
    """ValuationService should delegate using the requested portfolio ID."""

    position_service = FakePositionService()

    service = ValuationService(
        position_service=position_service
    )

    service.get_portfolio_valuation(
        portfolio_id=42
    )

    assert position_service.requested_portfolio_ids == [42]