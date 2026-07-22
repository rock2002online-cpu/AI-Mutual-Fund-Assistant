"""
Tests for TransactionRepository persistence operations.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from models.fund import Fund
from models.portfolio import Portfolio
from models.transaction import Transaction
from repositories.transaction_repository import TransactionRepository


def create_portfolio(session: Session) -> Portfolio:
    """
    Create and persist a portfolio for repository tests.
    """

    portfolio = Portfolio(
        name="Test Portfolio",
        description="Portfolio used for repository testing.",
        owner_reference="test-owner",
        base_currency="INR",
        is_active=True,
    )

    session.add(portfolio)
    session.flush()
    session.refresh(portfolio)

    return portfolio


def create_fund(session: Session) -> Fund:
    """
    Create and persist a fund for repository tests.
    """

    fund = Fund(
        scheme_code="TEST001",
        name="Test Mutual Fund - Direct Growth",
        amc="Test AMC",
        category="Equity",
        plan="Direct",
        option="Growth",
    )

    session.add(fund)
    session.flush()
    session.refresh(fund)

    return fund


def create_transaction(
    *,
    portfolio_id: int,
    fund_id: int,
    transaction_type: str = "PURCHASE",
    transaction_date: date = date(2026, 1, 15),
    units: Decimal = Decimal("10.123456"),
    nav: Decimal = Decimal("123.4567"),
    amount: Decimal = Decimal("1249.81"),
) -> Transaction:
    """
    Build a transaction entity for repository tests.
    """

    return Transaction(
        portfolio_id=portfolio_id,
        fund_id=fund_id,
        transaction_date=transaction_date,
        transaction_type=transaction_type,
        units=units,
        nav=nav,
        amount=amount,
    )


def test_add_transaction_assigns_id(
    session: Session,
) -> None:
    """
    Adding a transaction should persist it and assign an ID.
    """

    portfolio = create_portfolio(session)
    fund = create_fund(session)

    repository = TransactionRepository(session)

    transaction = create_transaction(
        portfolio_id=portfolio.id,
        fund_id=fund.id,
    )

    saved_transaction = repository.add(transaction)

    assert saved_transaction.id is not None
    assert saved_transaction.id > 0


def test_transaction_repository_count(
    session: Session,
) -> None:
    """
    Repository count should return the number of transactions.
    """

    portfolio = create_portfolio(session)
    fund = create_fund(session)

    repository = TransactionRepository(session)

    repository.add(
        create_transaction(
            portfolio_id=portfolio.id,
            fund_id=fund.id,
        )
    )

    assert repository.count() == 1


def test_get_transaction_by_id(
    session: Session,
) -> None:
    """
    A persisted transaction should be retrievable by primary key.
    """

    portfolio = create_portfolio(session)
    fund = create_fund(session)

    repository = TransactionRepository(session)

    saved_transaction = repository.add(
        create_transaction(
            portfolio_id=portfolio.id,
            fund_id=fund.id,
        )
    )

    result = repository.get_by_id(
        saved_transaction.id
    )

    assert result.id == saved_transaction.id
    assert result.portfolio_id == portfolio.id
    assert result.fund_id == fund.id
    assert result.transaction_date == date(2026, 1, 15)
    assert result.transaction_type == "PURCHASE"
    assert result.units == Decimal("10.123456")
    assert result.nav == Decimal("123.4567")
    assert result.amount == Decimal("1249.81")


def test_transaction_relationships(
    session: Session,
) -> None:
    """
    A transaction should be linked to its portfolio and fund.
    """

    portfolio = create_portfolio(session)
    fund = create_fund(session)

    repository = TransactionRepository(session)

    saved_transaction = repository.add(
        create_transaction(
            portfolio_id=portfolio.id,
            fund_id=fund.id,
        )
    )

    assert saved_transaction.portfolio.id == portfolio.id
    assert saved_transaction.portfolio.name == "Test Portfolio"

    assert saved_transaction.fund.id == fund.id
    assert saved_transaction.fund.scheme_code == "TEST001"
    assert (
        saved_transaction.fund.name
        == "Test Mutual Fund - Direct Growth"
    )
def test_get_for_portfolio_returns_only_matching_transactions(
    session: Session,
) -> None:
    repository = TransactionRepository(session)

    portfolio1 = create_portfolio(session)
    portfolio2 = create_portfolio(session)

    fund = create_fund(session)

    repository.add(
        create_transaction(
            portfolio_id=portfolio1.id,
            fund_id=fund.id,
        )
    )

    repository.add(
        create_transaction(
            portfolio_id=portfolio2.id,
            fund_id=fund.id,
        )
    )

    transactions = repository.get_for_portfolio(
        portfolio1.id
    )

    assert len(transactions) == 1
    assert transactions[0].portfolio_id == portfolio1.id

def test_get_for_fund_returns_only_matching_transactions(
    session: Session,
) -> None:
    repository = TransactionRepository(session)

    portfolio = create_portfolio(session)

    fund1 = create_fund(session)

    fund2 = Fund(
        scheme_code="TEST002",
        name="Another Fund",
        amc="AMC",
        category="Debt",
        plan="Direct",
        option="Growth",
    )

    session.add(fund2)
    session.flush()
    session.refresh(fund2)

    repository.add(
        create_transaction(
            portfolio_id=portfolio.id,
            fund_id=fund1.id,
        )
    )

    repository.add(
        create_transaction(
            portfolio_id=portfolio.id,
            fund_id=fund2.id,
        )
    )

    transactions = repository.get_for_fund(
        fund1.id
    )

    assert len(transactions) == 1
    assert transactions[0].fund_id == fund1.id

def test_get_between_dates_returns_expected_transactions(
    session: Session,
) -> None:
    repository = TransactionRepository(session)

    portfolio = create_portfolio(session)
    fund = create_fund(session)

    repository.add(
        create_transaction(
            portfolio_id=portfolio.id,
            fund_id=fund.id,
            transaction_date=date(2026, 1, 1),
        )
    )

    repository.add(
        create_transaction(
            portfolio_id=portfolio.id,
            fund_id=fund.id,
            transaction_date=date(2026, 2, 1),
        )
    )

    repository.add(
        create_transaction(
            portfolio_id=portfolio.id,
            fund_id=fund.id,
            transaction_date=date(2026, 3, 1),
        )
    )

    results = repository.get_between_dates(
        date(2026, 1, 15),
        date(2026, 2, 15),
    )

    assert len(results) == 1
    assert results[0].transaction_date == date(2026, 2, 1)

def test_transactions_are_returned_in_chronological_order(
    session: Session,
) -> None:
    repository = TransactionRepository(session)

    portfolio = create_portfolio(session)
    fund = create_fund(session)

    repository.add(
        create_transaction(
            portfolio_id=portfolio.id,
            fund_id=fund.id,
            transaction_date=date(2026, 3, 1),
        )
    )

    repository.add(
        create_transaction(
            portfolio_id=portfolio.id,
            fund_id=fund.id,
            transaction_date=date(2026, 1, 1),
        )
    )

    repository.add(
        create_transaction(
            portfolio_id=portfolio.id,
            fund_id=fund.id,
            transaction_date=date(2026, 2, 1),
        )
    )

    transactions = repository.get_for_portfolio(
        portfolio.id
    )

    assert [
        t.transaction_date
        for t in transactions
    ] == [
        date(2026, 1, 1),
        date(2026, 2, 1),
        date(2026, 3, 1),
    ]
def test_transactions_are_returned_in_chronological_order(
    session: Session,
) -> None:
    repository = TransactionRepository(session)

    portfolio = create_portfolio(session)
    fund = create_fund(session)

    repository.add(
        create_transaction(
            portfolio_id=portfolio.id,
            fund_id=fund.id,
            transaction_date=date(2026, 3, 1),
        )
    )

    repository.add(
        create_transaction(
            portfolio_id=portfolio.id,
            fund_id=fund.id,
            transaction_date=date(2026, 1, 1),
        )
    )

    repository.add(
        create_transaction(
            portfolio_id=portfolio.id,
            fund_id=fund.id,
            transaction_date=date(2026, 2, 1),
        )
    )

    transactions = repository.get_for_portfolio(
        portfolio.id
    )

    assert [
        t.transaction_date
        for t in transactions
    ] == [
        date(2026, 1, 1),
        date(2026, 2, 1),
        date(2026, 3, 1),
    ]
def test_get_for_portfolio_through_date_is_inclusive(
    session: Session,
) -> None:
    """Point-in-time query should be portfolio-scoped and inclusive."""

    repository = TransactionRepository(session)

    portfolio = create_portfolio(session)
    other_portfolio = create_portfolio(session)
    fund = create_fund(session)

    repository.add(
        create_transaction(
            portfolio_id=portfolio.id,
            fund_id=fund.id,
            transaction_date=date(2026, 1, 1),
        )
    )
    repository.add(
        create_transaction(
            portfolio_id=portfolio.id,
            fund_id=fund.id,
            transaction_date=date(2026, 2, 1),
        )
    )
    repository.add(
        create_transaction(
            portfolio_id=portfolio.id,
            fund_id=fund.id,
            transaction_date=date(2026, 3, 1),
        )
    )
    repository.add(
        create_transaction(
            portfolio_id=other_portfolio.id,
            fund_id=fund.id,
            transaction_date=date(2026, 1, 15),
        )
    )

    results = repository.get_for_portfolio_through_date(
        portfolio_id=portfolio.id,
        end_date=date(2026, 2, 1),
    )

    assert [
        transaction.transaction_date
        for transaction in results
    ] == [
        date(2026, 1, 1),
        date(2026, 2, 1),
    ]
    assert all(
        transaction.portfolio_id == portfolio.id
        for transaction in results
    )