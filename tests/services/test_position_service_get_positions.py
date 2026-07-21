"""Tests for PositionService.get_positions()."""

from __future__ import annotations

from datetime import date
from dataclasses import dataclass

import pytest

from models.transaction import Transaction
from services.position_service import PositionService


@dataclass
class FakeFund:
    id: int
    name: str
    latest_nav: float


class FakeTransactionRepository:
    def __init__(self, items=None):
        self.items = items or []

    def get_for_portfolio(self, portfolio_id: int):
        return [
            t
            for t in self.items
            if t.portfolio_id == portfolio_id
        ]


class FakeFundRepository:
    def __init__(self, funds=None):
        self.funds = {
            fund.id: fund
            for fund in (funds or [])
        }

    def get_by_id(self, fund_id: int):
        return self.funds[fund_id]


class FakeUnitOfWork:
    def __init__(
        self,
        *,
        transactions=None,
        funds=None,
    ):
        self.transactions = FakeTransactionRepository(
            transactions
        )
        self.funds = FakeFundRepository(
            funds
        )

        self.enter_called = False
        self.exit_called = False

    def __enter__(self):
        self.enter_called = True
        return self

    def __exit__(self, exc_type, exc, tb):
        self.exit_called = True
        return False


def make_transaction(
    *,
    portfolio_id=1,
    fund_id=1,
    transaction_type="BUY",
    units=10.0,
    nav=20.0,
):
    return Transaction(
        portfolio_id=portfolio_id,
        fund_id=fund_id,
        transaction_type=transaction_type,
        nav=nav,
        units=units,
        amount=units * nav,
        transaction_date=date(2026, 7, 19),
    )


def make_service(
    transactions,
    funds,
):
    uow = FakeUnitOfWork(
        transactions=transactions,
        funds=funds,
    )

    service = PositionService(
        unit_of_work_factory=lambda: uow
    )

    return service, uow


def test_empty_portfolio_returns_empty_list():
    service, _ = make_service(
        [],
        [],
    )

    positions = service.get_positions(
        portfolio_id=1
    )

    assert positions == []


def test_single_fund_returns_single_position():
    service, _ = make_service(
        [
            make_transaction(fund_id=1),
        ],
        [
            FakeFund(
                1,
                "Alpha",
                25.0,
            ),
        ],
    )

    positions = service.get_positions(
        portfolio_id=1
    )

    assert len(positions) == 1
    assert positions[0].fund_id == 1


def test_multiple_funds_return_multiple_positions():
    service, _ = make_service(
        [
            make_transaction(fund_id=1),
            make_transaction(fund_id=2),
            make_transaction(fund_id=3),
        ],
        [
            FakeFund(1, "Alpha", 10),
            FakeFund(2, "Bravo", 20),
            FakeFund(3, "Charlie", 30),
        ],
    )

    positions = service.get_positions(
        portfolio_id=1
    )

    assert len(positions) == 3


def test_other_portfolios_are_ignored():
    service, _ = make_service(
        [
            make_transaction(
                portfolio_id=1,
                fund_id=1,
            ),
            make_transaction(
                portfolio_id=99,
                fund_id=2,
            ),
        ],
        [
            FakeFund(1, "Alpha", 10),
            FakeFund(2, "Bravo", 20),
        ],
    )

    positions = service.get_positions(
        portfolio_id=1
    )

    assert len(positions) == 1
    assert positions[0].fund_id == 1


def test_duplicate_transactions_produce_single_position():
    service, _ = make_service(
        [
            make_transaction(fund_id=1),
            make_transaction(fund_id=1),
            make_transaction(fund_id=1),
        ],
        [
            FakeFund(
                1,
                "Alpha",
                10,
            ),
        ],
    )

    positions = service.get_positions(
        portfolio_id=1
    )

    assert len(positions) == 1


def test_positions_are_sorted_by_fund_name():
    service, _ = make_service(
        [
            make_transaction(fund_id=3),
            make_transaction(fund_id=1),
            make_transaction(fund_id=2),
        ],
        [
            FakeFund(3, "Zulu", 10),
            FakeFund(1, "Alpha", 10),
            FakeFund(2, "Bravo", 10),
        ],
    )

    positions = service.get_positions(
        portfolio_id=1
    )

    assert [
        p.fund_name
        for p in positions
    ] == [
        "Alpha",
        "Bravo",
        "Zulu",
    ]


def test_get_positions_uses_unit_of_work():
    service, uow = make_service(
        [],
        [],
    )

    service.get_positions(
        portfolio_id=1
    )

    assert uow.enter_called
    assert uow.exit_called