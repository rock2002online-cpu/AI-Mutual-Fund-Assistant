"""Tests for HoldingsService."""

from __future__ import annotations

from datetime import date
from typing import Optional

import pytest

from models.transaction import Transaction
from services.holdings_service import HoldingsService


class FakeTransactionRepository:
    """In-memory transaction repository."""

    def __init__(self) -> None:
        self.items: list[Transaction] = []

    def get_for_portfolio(
        self,
        portfolio_id: int,
    ) -> list[Transaction]:
        """Return transactions belonging to a portfolio."""

        return [
            transaction
            for transaction in self.items
            if transaction.portfolio_id == portfolio_id
        ]

    def add(
        self,
        transaction: Transaction,
    ) -> Transaction:
        """Store and return a transaction."""

        self.items.append(transaction)
        return transaction


class FakeUnitOfWork:
    """Minimal UnitOfWork for HoldingsService tests."""

    def __init__(
        self,
        transactions: Optional[
            FakeTransactionRepository
        ] = None,
    ) -> None:
        self.transactions = (
            transactions
            if transactions is not None
            else FakeTransactionRepository()
        )

    def __enter__(self) -> "FakeUnitOfWork":
        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        tb: object,
    ) -> bool:
        return False


def make_transaction(
    *,
    portfolio_id: int,
    fund_id: int,
    transaction_type: str,
    units: float,
    amount: float = 100.0,
) -> Transaction:
    """Create a transaction for HoldingsService tests."""

    return Transaction(
        portfolio_id=portfolio_id,
        fund_id=fund_id,
        transaction_type=transaction_type,
        units=units,
        nav=amount / units,
        amount=amount,
        transaction_date=date(2026, 7, 18),
    )


def test_get_current_units_returns_zero_without_transactions() -> None:
    """No matching transactions should produce zero current units."""

    unit_of_work = FakeUnitOfWork()

    service = HoldingsService(
        unit_of_work_factory=lambda: unit_of_work
    )

    result = service.get_current_units(
        portfolio_id=1,
        fund_id=2,
    )

    assert result == pytest.approx(0.0)


def test_get_current_units_sums_buy_transactions() -> None:
    """BUY transactions should increase current units."""

    repository = FakeTransactionRepository()

    repository.items.extend(
        [
            make_transaction(
                portfolio_id=1,
                fund_id=2,
                transaction_type="BUY",
                units=10.0,
            ),
            make_transaction(
                portfolio_id=1,
                fund_id=2,
                transaction_type="BUY",
                units=5.5,
            ),
        ]
    )

    unit_of_work = FakeUnitOfWork(
        transactions=repository
    )

    service = HoldingsService(
        unit_of_work_factory=lambda: unit_of_work
    )

    result = service.get_current_units(
        portfolio_id=1,
        fund_id=2,
    )

    assert result == pytest.approx(15.5)


def test_get_current_units_subtracts_sell_transactions() -> None:
    """SELL transactions should reduce current units."""

    repository = FakeTransactionRepository()

    repository.items.extend(
        [
            make_transaction(
                portfolio_id=1,
                fund_id=2,
                transaction_type="BUY",
                units=20.0,
            ),
            make_transaction(
                portfolio_id=1,
                fund_id=2,
                transaction_type="SELL",
                units=6.0,
            ),
            make_transaction(
                portfolio_id=1,
                fund_id=2,
                transaction_type="SELL",
                units=1.5,
            ),
        ]
    )

    unit_of_work = FakeUnitOfWork(
        transactions=repository
    )

    service = HoldingsService(
        unit_of_work_factory=lambda: unit_of_work
    )

    result = service.get_current_units(
        portfolio_id=1,
        fund_id=2,
    )

    assert result == pytest.approx(12.5)


def test_get_current_units_ignores_other_funds() -> None:
    """Transactions for other funds should not affect the result."""

    repository = FakeTransactionRepository()

    repository.items.extend(
        [
            make_transaction(
                portfolio_id=1,
                fund_id=2,
                transaction_type="BUY",
                units=10.0,
            ),
            make_transaction(
                portfolio_id=1,
                fund_id=3,
                transaction_type="BUY",
                units=100.0,
            ),
            make_transaction(
                portfolio_id=1,
                fund_id=3,
                transaction_type="SELL",
                units=25.0,
            ),
        ]
    )

    unit_of_work = FakeUnitOfWork(
        transactions=repository
    )

    service = HoldingsService(
        unit_of_work_factory=lambda: unit_of_work
    )

    result = service.get_current_units(
        portfolio_id=1,
        fund_id=2,
    )

    assert result == pytest.approx(10.0)


def test_get_current_units_ignores_other_portfolios() -> None:
    """Transactions for other portfolios should not affect the result."""

    repository = FakeTransactionRepository()

    repository.items.extend(
        [
            make_transaction(
                portfolio_id=1,
                fund_id=2,
                transaction_type="BUY",
                units=10.0,
            ),
            make_transaction(
                portfolio_id=99,
                fund_id=2,
                transaction_type="BUY",
                units=100.0,
            ),
            make_transaction(
                portfolio_id=99,
                fund_id=2,
                transaction_type="SELL",
                units=20.0,
            ),
        ]
    )

    unit_of_work = FakeUnitOfWork(
        transactions=repository
    )

    service = HoldingsService(
        unit_of_work_factory=lambda: unit_of_work
    )

    result = service.get_current_units(
        portfolio_id=1,
        fund_id=2,
    )

    assert result == pytest.approx(10.0)


@pytest.mark.parametrize(
    ("transaction_type", "expected_units"),
    [
        ("buy", 10.0),
        ("Buy", 10.0),
        ("BUY", 10.0),
        ("sell", -10.0),
        ("Sell", -10.0),
        ("SELL", -10.0),
    ],
)
def test_get_current_units_handles_transaction_type_case_insensitively(
    transaction_type: str,
    expected_units: float,
) -> None:
    """Transaction type matching should be case-insensitive."""

    repository = FakeTransactionRepository()

    repository.items.append(
        make_transaction(
            portfolio_id=1,
            fund_id=2,
            transaction_type=transaction_type,
            units=10.0,
        )
    )

    unit_of_work = FakeUnitOfWork(
        transactions=repository
    )

    service = HoldingsService(
        unit_of_work_factory=lambda: unit_of_work
    )

    result = service.get_current_units(
        portfolio_id=1,
        fund_id=2,
    )

    assert result == pytest.approx(expected_units)


def test_get_current_units_uses_unit_of_work_context_manager() -> None:
    """The service should use the UnitOfWork context manager."""

    class TrackingUnitOfWork(FakeUnitOfWork):
        def __init__(self) -> None:
            super().__init__()
            self.enter_called = False
            self.exit_called = False

        def __enter__(self) -> "TrackingUnitOfWork":
            self.enter_called = True
            return self

        def __exit__(
            self,
            exc_type: object,
            exc: object,
            tb: object,
        ) -> bool:
            self.exit_called = True
            return False

    unit_of_work = TrackingUnitOfWork()

    service = HoldingsService(
        unit_of_work_factory=lambda: unit_of_work
    )

    service.get_current_units(
        portfolio_id=1,
        fund_id=2,
    )

    assert unit_of_work.enter_called is True
    assert unit_of_work.exit_called is True