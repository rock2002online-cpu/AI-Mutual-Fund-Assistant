"""Tests for PositionService."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from models.transaction import Transaction
from services.position_service import PositionService


@dataclass
class FakeFund:
    """Minimal fund model used by PositionService tests."""

    id: int
    name: str
    latest_nav: float


class FakeTransactionRepository:
    """In-memory transaction repository for tests."""

    def __init__(
        self,
        items: list[Transaction] | None = None,
    ) -> None:
        self.items = items or []

    def get_for_portfolio(
        self,
        portfolio_id: int,
    ) -> list[Transaction]:
        return [
            transaction
            for transaction in self.items
            if transaction.portfolio_id == portfolio_id
        ]


class FakeFundRepository:
    """In-memory fund repository for tests."""

    def __init__(
        self,
        funds: list[FakeFund] | None = None,
    ) -> None:
        self.funds = {
            fund.id: fund
            for fund in (funds or [])
        }

    def get_by_id(
        self,
        fund_id: int,
    ) -> FakeFund:
        return self.funds[fund_id]


class FakeUnitOfWork:
    """Minimal Unit of Work used by PositionService tests."""

    def __init__(
        self,
        *,
        transactions: list[Transaction] | None = None,
        funds: list[FakeFund] | None = None,
    ) -> None:
        self.transactions = FakeTransactionRepository(
            transactions
        )
        self.funds = FakeFundRepository(
            funds
        )
        self.enter_called = False
        self.exit_called = False

    def __enter__(self) -> "FakeUnitOfWork":
        self.enter_called = True
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> bool:
        self.exit_called = True
        return False


def make_transaction(
    *,
    portfolio_id: int = 1,
    fund_id: int = 2,
    transaction_type: str = "BUY",
    units: float = 10.0,
    nav: float = 20.0,
    amount: float | None = None,
) -> Transaction:
    """Create a transaction for PositionService tests."""

    effective_amount = (
        amount
        if amount is not None
        else units * nav
    )

    return Transaction(
        portfolio_id=portfolio_id,
        fund_id=fund_id,
        transaction_type=transaction_type,
        nav=nav,
        units=units,
        amount=effective_amount,
        transaction_date=date(2026, 7, 19),
    )


def test_get_position_builds_position_from_buy_transactions() -> None:
    """BUY transactions should produce a complete position."""

    unit_of_work = FakeUnitOfWork(
        transactions=[
            make_transaction(
                units=10.0,
                nav=20.0,
            ),
            make_transaction(
                units=5.0,
                nav=30.0,
            ),
        ],
        funds=[
            FakeFund(
                id=2,
                name="Test Equity Fund",
                latest_nav=40.0,
            )
        ],
    )

    service = PositionService(
        unit_of_work_factory=lambda: unit_of_work
    )

    position = service.get_position(
        portfolio_id=1,
        fund_id=2,
    )

    assert position.portfolio_id == 1
    assert position.fund_id == 2
    assert position.fund_name == "Test Equity Fund"

    assert position.units == pytest.approx(15.0)
    assert position.invested_amount == pytest.approx(350.0)
    assert position.average_nav == pytest.approx(
        350.0 / 15.0
    )

    assert position.latest_nav == pytest.approx(40.0)
    assert position.current_value == pytest.approx(600.0)
    assert position.unrealized_gain == pytest.approx(250.0)
    assert position.unrealized_return_pct == pytest.approx(
        (250.0 / 350.0) * 100.0
    )


def test_get_position_ignores_other_funds() -> None:
    """Transactions for other funds must not affect the position."""

    unit_of_work = FakeUnitOfWork(
        transactions=[
            make_transaction(
                fund_id=2,
                units=10.0,
                nav=20.0,
            ),
            make_transaction(
                fund_id=3,
                units=100.0,
                nav=50.0,
            ),
        ],
        funds=[
            FakeFund(
                id=2,
                name="Selected Fund",
                latest_nav=30.0,
            ),
            FakeFund(
                id=3,
                name="Other Fund",
                latest_nav=60.0,
            ),
        ],
    )

    service = PositionService(
        unit_of_work_factory=lambda: unit_of_work
    )

    position = service.get_position(
        portfolio_id=1,
        fund_id=2,
    )

    assert position.units == pytest.approx(10.0)
    assert position.invested_amount == pytest.approx(200.0)


def test_get_position_ignores_other_portfolios() -> None:
    """Transactions from another portfolio must be ignored."""

    unit_of_work = FakeUnitOfWork(
        transactions=[
            make_transaction(
                portfolio_id=1,
                units=10.0,
                nav=20.0,
            ),
            make_transaction(
                portfolio_id=99,
                units=100.0,
                nav=50.0,
            ),
        ],
        funds=[
            FakeFund(
                id=2,
                name="Selected Fund",
                latest_nav=30.0,
            )
        ],
    )

    service = PositionService(
        unit_of_work_factory=lambda: unit_of_work
    )

    position = service.get_position(
        portfolio_id=1,
        fund_id=2,
    )

    assert position.units == pytest.approx(10.0)
    assert position.invested_amount == pytest.approx(200.0)


def test_get_position_subtracts_sell_units() -> None:
    """SELL transactions should reduce the current units."""

    unit_of_work = FakeUnitOfWork(
        transactions=[
            make_transaction(
                transaction_type="BUY",
                units=10.0,
                nav=20.0,
                amount=200.0,
            ),
            make_transaction(
                transaction_type="SELL",
                units=4.0,
                nav=30.0,
                amount=120.0,
            ),
        ],
        funds=[
            FakeFund(
                id=2,
                name="Balanced Fund",
                latest_nav=35.0,
            )
        ],
    )

    service = PositionService(
        unit_of_work_factory=lambda: unit_of_work
    )

    position = service.get_position(
        portfolio_id=1,
        fund_id=2,
    )

    assert position.units == pytest.approx(6.0)
    assert position.current_value == pytest.approx(210.0)


def test_get_position_returns_zero_return_when_investment_is_zero() -> None:
    """Zero invested amount should not cause division by zero."""

    unit_of_work = FakeUnitOfWork(
        transactions=[],
        funds=[
            FakeFund(
                id=2,
                name="Empty Fund",
                latest_nav=25.0,
            )
        ],
    )

    service = PositionService(
        unit_of_work_factory=lambda: unit_of_work
    )

    position = service.get_position(
        portfolio_id=1,
        fund_id=2,
    )

    assert position.units == pytest.approx(0.0)
    assert position.average_nav == pytest.approx(0.0)
    assert position.invested_amount == pytest.approx(0.0)
    assert position.current_value == pytest.approx(0.0)
    assert position.unrealized_gain == pytest.approx(0.0)
    assert position.unrealized_return_pct == pytest.approx(0.0)


def test_get_position_handles_transaction_type_case_insensitively() -> None:
    """Transaction types should be normalized before calculation."""

    unit_of_work = FakeUnitOfWork(
        transactions=[
            make_transaction(
                transaction_type="buy",
                units=10.0,
                nav=20.0,
            ),
            make_transaction(
                transaction_type="Sell",
                units=2.0,
                nav=25.0,
            ),
        ],
        funds=[
            FakeFund(
                id=2,
                name="Case Fund",
                latest_nav=30.0,
            )
        ],
    )

    service = PositionService(
        unit_of_work_factory=lambda: unit_of_work
    )

    position = service.get_position(
        portfolio_id=1,
        fund_id=2,
    )

    assert position.units == pytest.approx(8.0)


def test_get_position_uses_unit_of_work_context_manager() -> None:
    """PositionService should use the Unit of Work context manager."""

    unit_of_work = FakeUnitOfWork(
        funds=[
            FakeFund(
                id=2,
                name="Context Fund",
                latest_nav=10.0,
            )
        ]
    )

    service = PositionService(
        unit_of_work_factory=lambda: unit_of_work
    )

    service.get_position(
        portfolio_id=1,
        fund_id=2,
    )

    assert unit_of_work.enter_called is True
    assert unit_of_work.exit_called is True